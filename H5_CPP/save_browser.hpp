#pragma once
namespace hoi5::save {
inline std::string filenameText(const std::filesystem::path& path) {
    const auto value=path.stem().u8string();return {value.begin(),value.end()};
}
inline std::filesystem::path namedPath(const std::filesystem::path& directory,const sf::String& name) {
    const auto utf8=name.toUtf8();std::string text(utf8.begin(),utf8.end());
    if(text.empty() || text.size()>180 || text.back()=='.' || text.back()==' ' || text=="." || text==".." ||
       text.find_first_of("<>:\"/\\|?*")!=std::string::npos || std::ranges::any_of(text,[](unsigned char c){return c<32;}))
        throw std::runtime_error("Недопустимое имя сохранения");
    auto first=text.substr(0,text.find('.'));for(auto& c:first)if(c>='a' && c<='z')c-=32;
    if(first=="CON" || first=="PRN" || first=="AUX" || first=="NUL" ||
       (first.size()==4 && (first.starts_with("COM") || first.starts_with("LPT")) && first[3]>='1' && first[3]<='9'))
        throw std::runtime_error("Это имя зарезервировано системой");
    return directory/std::filesystem::path(std::u8string(utf8.begin(),utf8.end())+u8".h5save");
}
struct Browser {
    enum class Mode { load,save };
    enum class Dialog { none,newName,rename,overwrite };
    enum class Action { none,back,load };
    std::filesystem::path directory,pendingPath;
    std::vector<Info> files;
    Mode mode=Mode::load;
    Dialog dialog=Dialog::none;
    sf::String name;
    int page=0,selection=-1;
    std::string message;
    bool validSelection() const {return selection>=0 && selection<int(files.size());}
    bool conflict() const {return validSelection() && (files[selection].version!=gameVersion || files[selection].format!=formatVersion);}
    void refresh(const std::filesystem::path& selected={}) {
        files=list(directory);selection=-1;
        for(int i=0;i<int(files.size());++i)if(files[i].path==selected)selection=i;
        if(selection>=0)page=selection/6;else page=std::clamp(page,0,std::max(0,(int(files.size())-1)/6));
    }
    void open(Mode next,const std::filesystem::path& folder) {mode=next;directory=folder;page=0;dialog=Dialog::none;name.clear();pendingPath.clear();message.clear();refresh();}
    static sf::IntRect rect(sf::Vector2u size,int x,int y,int w,int h) {return {{int(size.x/2)+x,int(size.y/2)+y},{w,h}};}
    void write(World& world,SimulationClock& clock,const std::filesystem::path& path,bool overwrite) {
        writeGame(path,world,clock,overwrite);dialog=Dialog::none;refresh(path);message="Игра сохранена";
    }
    void confirm(World& world,SimulationClock& clock) {
        try {
            if(dialog==Dialog::overwrite) {write(world,clock,pendingPath,true);return;}
            const auto path=namedPath(directory,name);
            if(dialog==Dialog::rename) {
                const auto old=files.at(selection).path;
                if(path!=old) {if(std::filesystem::exists(path))throw std::runtime_error("Сохранение с таким именем уже существует");std::filesystem::rename(old,path);}
                dialog=Dialog::none;refresh(path);message="Сохранение переименовано";
            } else if(dialog==Dialog::newName) {
                if(std::filesystem::exists(path)) {pendingPath=path;dialog=Dialog::overwrite;message.clear();}
                else write(world,clock,path,false);
            }
        } catch(const std::exception& e) {message=e.what();}
    }
    Action event(const sf::Event& event,sf::Vector2u size,World& world,SimulationClock& clock) {
        using Key=sf::Keyboard::Key;
        if(const auto* key=event.getIf<sf::Event::KeyPressed>()) {
            if(key->code==Key::Escape) {if(dialog!=Dialog::none){dialog=Dialog::none;message.clear();return Action::none;}return Action::back;}
            if(dialog!=Dialog::none && key->code==Key::Enter) {confirm(world,clock);return Action::none;}
        }
        if(const auto* typed=event.getIf<sf::Event::TextEntered>();typed && (dialog==Dialog::newName || dialog==Dialog::rename)) {
            if(typed->unicode==8) {if(!name.isEmpty())name.erase(name.getSize()-1);}
            else if(typed->unicode>=32 && typed->unicode!=127 && name.getSize()<60)name+=typed->unicode;
            return Action::none;
        }
        const auto* click=event.getIf<sf::Event::MouseButtonPressed>();
        if(!click || click->button!=sf::Mouse::Button::Left)return Action::none;
        const auto hit=[&](int x,int y,int w,int h){return rect(size,x,y,w,h).contains(click->position);};
        if(dialog!=Dialog::none) {
            if(hit(-280,70,180,42)) {dialog=Dialog::none;message.clear();}
            else if(hit(60,70,220,42))confirm(world,clock);
            return Action::none;
        }
        for(int row=0;row<6;++row)if(hit(-350,-190+56*row,700,50) && page*6+row<int(files.size())) {selection=page*6+row;message.clear();return Action::none;}
        if(hit(-350,165,90,38)) {page=std::max(0,page-1);selection=-1;return Action::none;}
        if(hit(260,165,90,38)) {if((page+1)*6<int(files.size()))++page;selection=-1;return Action::none;}
        if(hit(-350,270,135,42))return Action::back;
        if(hit(-205,270,170,42) && validSelection()) {
            const auto text=filenameText(files[selection].path);name=sf::String::fromUtf8(text.begin(),text.end());
            dialog=Dialog::rename;message.clear();return Action::none;
        }
        if(mode==Mode::save && hit(-25,270,170,42)) {name.clear();dialog=Dialog::newName;message.clear();return Action::none;}
        if(hit(155,270,195,42) && validSelection()) {
            if(mode==Mode::load) {if(files[selection].error.empty())return Action::load;message="Не удалось прочитать файл сохранения";}
            else {pendingPath=files[selection].path;dialog=Dialog::overwrite;message.clear();}
        }
        return Action::none;
    }
    void draw(sf::RenderWindow& window,const sf::Font& font,const std::string& error) const {
        const auto size=window.getSize();const float cx=size.x/2.f,cy=size.y/2.f;
        const auto button=[&](int x,int y,int w,const std::string& text,bool enabled=true) {
            box(window,{cx+x,cy+y},{float(w),42},{30,39,50},{92,112,136});
            label(window,font,text,{cx+x+12,cy+y+11},16,enabled?sf::Color{224,234,244}:sf::Color{125,137,150});
        };
        label(window,font,mode==Mode::save?"Сохранить игру":"Загрузить игру",{cx-145,32},32);
        label(window,font,"AppData / Local / HOI5 / saves",{cx-350,cy-225},16);
        if(files.empty())label(window,font,"Сохранений пока нет",{cx-140,cy-80},22);
        for(int row=0;row<6 && page*6+row<int(files.size());++row) {
            const int index=page*6+row;const auto& info=files[index];const float y=cy-190+56*row;
            box(window,{cx-350,y},{700,50},index==selection?sf::Color{48,69,88}:sf::Color{30,39,50},{92,112,136});
            const auto title=filenameText(info.path)+"  "+info.country;
            sf::Text text(font,sf::String::fromUtf8(title.begin(),title.end()),16);text.setPosition({cx-338,y+3});
            if(text.getLocalBounds().size.x>674)text.setScale({674/text.getLocalBounds().size.x,1});window.draw(text);
            label(window,font,info.error.empty()?"Час: "+std::to_string(info.hours)+"   Сид: "+std::to_string(info.seed)+"   Версия: "+info.version:"Повреждённый файл",{cx-338,y+27},14);
        }
        button(-350,165,90,"<");button(260,165,90,">");
        label(window,font,std::to_string(page+1)+" / "+std::to_string(std::max(1,(int(files.size())+5)/6)),{cx-25,cy+177},16);
        if(mode==Mode::load && conflict())label(window,font,"Другая версия: возможны конфликты при загрузке.",{cx-350,cy+215},17,{240,190,100});
        if(!message.empty() && dialog==Dialog::none)label(window,font,message,{cx-350,cy+243},15);
        if(!error.empty())label(window,font,error,{40,float(size.y)-45},15);
        button(-350,270,135,"Назад");button(-205,270,170,"Переименовать",validSelection());
        if(mode==Mode::save)button(-25,270,170,"Новое сохранение");
        button(155,270,195,mode==Mode::save?"Перезаписать":conflict()?"Загрузить всё равно":"Загрузить",validSelection());
        if(dialog!=Dialog::none) {
            box(window,{0,0},sf::Vector2f(size),{0,0,0,175});box(window,{cx-310,cy-130},{620,270},{24,33,44},{110,133,156});
            label(window,font,dialog==Dialog::overwrite?"Перезаписать сохранение?":dialog==Dialog::rename?"Переименовать сохранение":"Новое сохранение",{cx-280,cy-108},24);
            if(dialog==Dialog::overwrite) {
                label(window,font,"Текущая партия заменит выбранное сохранение.",{cx-280,cy-55},18);
                label(window,font,filenameText(pendingPath),{cx-280,cy-23},18);
            } else {
                label(window,font,"Имя сохранения",{cx-280,cy-65},16);box(window,{cx-280,cy-35},{560,46},{13,20,28},{116,151,184});
                sf::Text text(font,name+"|",19);text.setPosition({cx-268,cy-24});if(text.getLocalBounds().size.x>530)text.setScale({530/text.getLocalBounds().size.x,1});window.draw(text);
            }
            if(!message.empty())label(window,font,message,{cx-280,cy+32},15,{240,190,100});
            button(-280,70,180,"Отмена");button(60,70,220,dialog==Dialog::overwrite?"Да, перезаписать":dialog==Dialog::rename?"Переименовать":"Сохранить");
        }
    }
};
}
