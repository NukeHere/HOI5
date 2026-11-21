#pragma once
#include <SFML/Graphics.hpp>
#include "production.hpp"
#include "format_amount.hpp"
#include <optional>

namespace hoi5 {

// Native vector pictograms: no dependency on Python UI assets.
inline void productionGlyph(sf::RenderTarget& target,sf::Vector2f p,float size,std::string_view key,
                            sf::Color color = {210,193,137}) {
    const float u = size/32;
    const auto rect = [&](float x,float y,float w,float h,sf::Color c) {
        sf::RectangleShape shape({w*u,h*u}); shape.setPosition(p+sf::Vector2f{x*u,y*u});
        shape.setFillColor(c); target.draw(shape);
    };
    if (key == "factory") {
        rect(4,15,24,13,color); rect(6,5,5,14,color); rect(22,9,4,10,color);
        for (int i=0;i<4;++i) rect(7+5*i,20,3,4,{38,49,61});
        sf::ConvexShape roof(5); roof.setPoint(0,{12*u,16*u}); roof.setPoint(1,{19*u,10*u});
        roof.setPoint(2,{19*u,15*u}); roof.setPoint(3,{27*u,10*u}); roof.setPoint(4,{27*u,18*u});
        roof.setPosition(p); roof.setFillColor(color); target.draw(roof);
    } else if (key == "attack_helicopter") {
        rect(2,5,28,2,color); rect(15,7,2,8,color); rect(8,14,17,9,color); rect(2,17,9,3,color);
        rect(8,26,19,2,color); rect(12,22,2,5,color); rect(22,22,2,5,color);
    } else if (key.find("fighter") != key.npos || key.find("bomber") != key.npos || key == "cas_aircraft") {
        rect(14,3,4,27,color); rect(3,13,26,5,color); rect(8,25,16,3,color); rect(15,1,2,5,color);
    } else if (key == "ships") {
        rect(4,18,24,7,color); rect(10,10,13,8,color); rect(14,5,3,6,color); rect(7,26,18,2,color);
    } else if (key.find("bomb") != key.npos) {
        rect(12,8,9,19,color); rect(14,4,5,7,color); rect(8,22,5,7,color); rect(21,22,5,7,color);
    } else if (key.find("artillery") != key.npos || key.find("range_aa") != key.npos || key.find("sam") != key.npos || key == "manpads_team") {
        rect(5,22,23,4,color); rect(10,12,11,10,color); rect(15,7,14,3,color); rect(6,25,5,5,color); rect(23,25,5,5,color);
    } else if (key == "quartz" || key == "bauxite") {
        sf::ConvexShape crystal(6); crystal.setPoint(0,{16*u,2*u}); crystal.setPoint(1,{25*u,10*u});
        crystal.setPoint(2,{24*u,25*u}); crystal.setPoint(3,{16*u,30*u}); crystal.setPoint(4,{7*u,25*u}); crystal.setPoint(5,{6*u,10*u});
        crystal.setPosition(p); crystal.setFillColor(color); target.draw(crystal); rect(15,7,2,18,{51,69,79});
    } else if (key == "tank" || key == "old_ifv" || key == "vehicles") {
        rect(3,20,27,7,color); rect(7,13,17,8,color); rect(13,8,8,6,color); rect(20,9,11,2,color);
        for(int i=0;i<5;++i) rect(5+5*i,22,3,3,{38,49,61});
    } else if (key.find("ammo") != key.npos || key.find("missile") != key.npos || key.find("rockets") != key.npos) {
        for(int i=0;i<3;++i) { rect(6+i*8,10,4,17,color); rect(7+i*8,6,2,5,color); rect(6+i*8,24,4,2,{242,202,119}); }
    } else if (key == "old_assault_rifles") {
        rect(3,13,26,4,color); rect(6,17,4,6,color); rect(14,17,5,8,color); rect(1,12,5,8,color);
    } else if (key == "food" || key == "fertilizer") {
        rect(15,7,2,23,color);
        for(int i=0;i<3;++i) { rect(8,6+i*6,7,4,color); rect(17,9+i*6,7,4,color); }
    } else if (key.find("fuel") != key.npos || key == "chemicals" || key == "oil" || key == "natural_gas") {
        rect(9,12,15,16,color); rect(12,5,9,10,color); rect(12,20,3,5,{38,49,61});
    } else if (key == "electronics" || key == "copper_wire") {
        rect(8,8,17,17,color); rect(12,12,9,9,{38,49,61});
        for(int i=0;i<4;++i) { rect(4,9+i*5,5,2,color); rect(24,9+i*5,5,2,color); }
    } else if (key == "steel" || key.find("ore") != key.npos || key == "coal") {
        rect(4,20,24,7,color); rect(7,11,19,7,color); rect(12,3,12,6,color);
    } else {
        rect(5,6,23,23,color); rect(8,9,17,17,{48,61,73}); rect(15,7,3,21,color); rect(6,15,21,3,color);
    }
}

struct ProductionPanel {
    struct Hit { sf::FloatRect bounds; std::function<void()> action; std::string help; };
    struct Slider { sf::FloatRect bounds; int line; double maximum; };
    std::vector<Hit> hits;
    std::vector<Slider> sliders;
    ProductionPlan* plan{};
    std::function<void()> changed;
    std::function<void()> close;
    std::function<std::string(std::string_view)> name;
    float scroll{}, catalogScroll{}, maximumScroll{}, catalogMaximumScroll{};
    bool catalogOpen{}, confirmDuplicate{};
    std::string_view selected;
    double previewPower = 10, totalPower{};
    sf::FloatRect bounds, listBounds, catalogBounds, scrollTrack, catalogTrack;
    std::optional<Slider> draggingSlider;
    bool draggingScroll{}, draggingCatalog{};
    sf::Vector2f pointer{};
    static constexpr float rowHeight = 184;
    static constexpr sf::Color green{144,215,161}, yellow{240,202,115}, red{239,139,124}, muted{158,176,193};

    void cancelPointerCapture() {
        draggingSlider.reset(); draggingScroll=draggingCatalog=false;
    }

    void updateSlider(float x) {
        if (!draggingSlider) return;
        const auto s = *draggingSlider;
        const double amount = std::nearbyint(std::clamp((x-s.bounds.position.x)/s.bounds.size.x,0.f,1.f)*s.maximum);
        if (s.line == -1) previewPower = amount;
        else if (plan && s.line >= 0 && s.line < int(plan->size()) && (*plan)[s.line].power != amount) {
            (*plan)[s.line].power = amount; if (changed) changed();
        }
    }
    void updateScroll(float y,bool catalog) {
        const auto track = catalog ? catalogTrack : scrollTrack;
        const float max = catalog ? catalogMaximumScroll : maximumScroll;
        const float visible = catalog ? catalogBounds.size.y : listBounds.size.y;
        const float thumb = std::min(track.size.y,std::max(36.f,track.size.y*visible/(visible+max)));
        const float fraction = std::clamp((y-track.position.y-thumb*.5f)/std::max(1.f,track.size.y-thumb),0.f,1.f);
        (catalog ? catalogScroll : scroll) = max*fraction;
    }
    bool event(const sf::Event& e) {
        if (const auto* m=e.getIf<sf::Event::MouseMoved>()) {
            pointer=sf::Vector2f(m->position);
            if(draggingSlider) { updateSlider(pointer.x); return true; }
            if(draggingScroll || draggingCatalog) { updateScroll(pointer.y,draggingCatalog); return true; }
            return catalogOpen || bounds.contains(pointer);
        }
        if (const auto* release=e.getIf<sf::Event::MouseButtonReleased>(); release && release->button==sf::Mouse::Button::Left) {
            const bool captured=draggingSlider.has_value() || draggingScroll || draggingCatalog;
            draggingSlider.reset(); draggingScroll=draggingCatalog=false;
            return captured || catalogOpen || bounds.contains(sf::Vector2f(release->position));
        }
        if (const auto* wheel=e.getIf<sf::Event::MouseWheelScrolled>()) {
            if(catalogOpen) {
                if(catalogBounds.contains(sf::Vector2f(wheel->position))) catalogScroll=std::clamp(catalogScroll-wheel->delta*72,0.f,catalogMaximumScroll);
                return true;
            }
            if(bounds.contains(sf::Vector2f(wheel->position))) { scroll=std::clamp(scroll-wheel->delta*80,0.f,maximumScroll); return true; }
        }
        if (const auto* key=e.getIf<sf::Event::KeyPressed>(); key && key->code==sf::Keyboard::Key::Escape && catalogOpen) {
            if(confirmDuplicate) confirmDuplicate=false; else catalogOpen=false;
            return true;
        }
        if (const auto* click=e.getIf<sf::Event::MouseButtonPressed>()) {
            pointer=sf::Vector2f(click->position);
            if(click->button != sf::Mouse::Button::Left) return catalogOpen || bounds.contains(pointer);
            for(const auto& s:sliders) if(s.bounds.contains(pointer)) { draggingSlider=s; updateSlider(pointer.x); return true; }
            if(!confirmDuplicate && catalogOpen && catalogTrack.contains(pointer)) { draggingCatalog=true; updateScroll(pointer.y,true); return true; }
            if(!catalogOpen && scrollTrack.contains(pointer)) { draggingScroll=true; updateScroll(pointer.y,false); return true; }
            for(auto it=hits.rbegin();it!=hits.rend();++it) if(it->bounds.contains(pointer)) { auto action=it->action; action(); return true; }
            return catalogOpen || bounds.contains(pointer);
        }
        return false;
    }

    static void box(sf::RenderTarget& target,sf::FloatRect r,sf::Color fill,sf::Color border={}) {
        sf::RectangleShape shape(r.size); shape.setPosition(r.position); shape.setFillColor(fill);
        shape.setOutlineColor(border); shape.setOutlineThickness(-1); target.draw(shape);
    }
    static void text(sf::RenderTarget& target,const sf::Font& font,std::string value,sf::Vector2f p,unsigned size,
                     sf::Color color=sf::Color::White,float width=10000) {
        sf::Text label(font,sf::String::fromUtf8(value.begin(),value.end()),size); label.setPosition(p); label.setFillColor(color);
        if(label.getLocalBounds().size.x>width) label.setScale({width/label.getLocalBounds().size.x,1}); target.draw(label);
    }
    static void resourceLabel(sf::RenderTarget& target,const sf::Font& font,std::string_view key,std::string caption,
                              sf::FloatRect bounds,unsigned points=17,sf::Color color={220,230,240}) {
        productionGlyph(target,bounds.position+sf::Vector2f{0,(bounds.size.y-30)/2},30,key,{197,192,148});
        const auto unicode=sf::String::fromUtf8(caption.begin(),caption.end());
        std::vector<sf::String> lines;
        sf::Text measure(font,"",points);
        for(std::size_t start=0;start<unicode.getSize();) {
            std::size_t end=start,space=start;
            while(end<unicode.getSize()) {
                measure.setString(unicode.substring(start,end-start+1));
                if(measure.getLocalBounds().size.x>bounds.size.x-42 && end>start) break;
                if(unicode[end]==U' ') space=end;
                if(unicode[end]==U'-') space=end+1;
                ++end;
            }
            if(end<unicode.getSize() && space>start) end=space;
            lines.push_back(unicode.substring(start,std::max(std::size_t(1),end-start)));
            start=std::max(start+1,end);
            while(start<unicode.getSize() && unicode[start]==U' ') ++start;
        }
        const float pitch=float(points+3), y=bounds.position.y+(bounds.size.y-pitch*lines.size())/2;
        for(std::size_t i=0;i<lines.size();++i) {
            sf::Text label(font,lines[i],points); label.setPosition({bounds.position.x+42,y+pitch*i});
            label.setFillColor(color); target.draw(label);
        }
    }
    void button(sf::RenderTarget& target,const sf::Font& font,std::string caption,sf::FloatRect r,
                std::function<void()> action,std::string help={}) {
        const bool hover=r.contains(pointer);
        box(target,r,hover ? sf::Color(66,88,109) : sf::Color(40,55,70),{105,128,150});
        text(target,font,caption,r.position+sf::Vector2f{7,4},16,{226,234,242},r.size.x-12);
        hits.push_back({r,std::move(action),std::move(help)});
    }
    void slider(sf::RenderTarget& target,sf::FloatRect r,int line,double amount,double maximum) {
        box(target,{{r.position.x,r.position.y+11},{r.size.x,6}},{53,70,85});
        const float fraction=float(std::clamp(amount/std::max(1.,maximum),0.,1.));
        box(target,{{r.position.x,r.position.y+11},{r.size.x*fraction,6}},{175,192,133});
        box(target,{{r.position.x+r.size.x*fraction-5,r.position.y+4},{10,20}},{226,208,151},{255,237,185});
        sliders.push_back({r,line,maximum});
    }
    void scrollbar(sf::RenderTarget& target,sf::FloatRect track,float value,float maximum,float visible) {
        box(target,track,{27,38,48});
        const float height=std::min(track.size.y,std::max(36.f,track.size.y*visible/(visible+maximum)));
        const float y=track.position.y+(track.size.y-height)*(maximum>0 ? value/maximum : 0);
        box(target,{{track.position.x+2,y},{track.size.x-4,height}},{115,141,163},{160,181,199});
    }
    static sf::View clip(sf::RenderWindow& window,sf::FloatRect r) {
        const auto previous=window.getView(); sf::View view(r);
        const auto size=sf::Vector2f(window.getSize());
        view.setViewport({{r.position.x/size.x,r.position.y/size.y},{r.size.x/size.x,r.size.y/size.y}});
        window.setView(view); return previous;
    }
    sf::Color availability(double stock,double need) const {
        return need<=0 || stock>=need ? green : stock<need/120. ? red : yellow;
    }
    void chip(sf::RenderTarget& target,const sf::Font& font,std::string_view key,double amount,
              sf::Vector2f p,float width,sf::Color color) {
        box(target,{p,{width,48}},{34,46,58},{66,85,101}); productionGlyph(target,p+sf::Vector2f{6,8},30,key,color);
        text(target,font,name(key),p+sf::Vector2f{42,3},16,{216,227,237},width-47);
        text(target,font,formatAmount(amount)+" / мес.",p+sf::Vector2f{42,25},16,color,width-47);
    }
    void appendSelected() {
        if(!plan) return;
        const auto* recipe=productionRecipe(selected);
        if(!recipe || recipe->building!=industry) return;
        plan->push_back({recipe->id,previewPower});
        catalogOpen=confirmDuplicate=false; scroll=maximumScroll+rowHeight;
        if(changed) changed();
    }

    void draw(sf::RenderWindow& window,const sf::Font& font,const Production& model,ProductionPlan& assignments,
              const Stockpile& stock,const std::vector<ProductionLine>& preview) {
        plan=&assignments; totalPower=model.totalPower; pointer=sf::Vector2f(sf::Mouse::getPosition(window));
        hits.clear(); sliders.clear();
        const float width=std::min(940.f,float(window.getSize().x)-12), bottom=float(window.getSize().y)-12;
        bounds={{0,90},{width,bottom-90}}; listBounds={{12,205},{width-36,std::max(60.f,bottom-217)}};
        box(window,bounds,{19,27,35,252},{100,123,144}); productionGlyph(window,{20,105},36,"factory");
        text(window,font,"Производство",{68,105},26);
        text(window,font,"Всего "+formatAmount(model.totalPower)+" ПМ    Свободно "+formatAmount(model.unusedPower)+" ПМ",{22,149},20,{218,204,157});
        text(window,font,"Приоритет сверху вниз",{22,179},16,muted);
        text(window,font,"На месяц",{292,179},15,green);
        text(window,font,"Запас меньше месяца",{386,179},15,yellow);
        text(window,font,"Не хватает на тик",{574,179},15,red);
        button(window,font,"+ Добавить рецепт",{{width-247,143},{205,34}},[this] { catalogOpen=true; catalogScroll=0; confirmDuplicate=false; },"Открыть каталог рецептов");
        button(window,font,"X",{{width-38,102},{28,28}},[this] { if(close) close(); },"Закрыть производство");
        maximumScroll=std::max(0.f,float(model.lines.size())*rowHeight-listBounds.size.y);
        scroll=std::clamp(scroll,0.f,maximumScroll); scrollTrack={{width-20,205},{14,listBounds.size.y}};
        const auto headerHits=hits.size();
        auto oldView=clip(window,listBounds);
        for(int index=0;index<int(model.lines.size());++index) {
            const auto& line=model.lines[index]; const float y=205+index*rowHeight-scroll;
            if(y+rowHeight<listBounds.position.y || y>bottom) continue;
            const float right=width-32;
            box(window,{{16,y},{width-48,rowHeight-10}},{27,38,49},{58,78,96});
            double ratio=line.plannedUnits>0 && index<int(preview.size()) ? preview[index].actualUnits*120/line.plannedUnits : 1.;
            const auto status=ratio<.01 ? red : ratio<.999 || line.availablePower<line.assignedPower ? yellow : green;
            box(window,{{16,y},{4,rowHeight-10}},status);
            productionGlyph(window,{28,y+9},34,line.recipe,status);
            text(window,font,std::to_string(index+1)+". "+name(line.recipe),{74,y+12},22,{230,236,242},right-290);
            button(window,font,"Вверх",{{right-179,y+10},{64,28}},[this,index] { if(plan && index>0) { moveProductionLine(*plan,index,index-1); if(changed) changed(); } },"Повысить приоритет");
            button(window,font,"Вниз",{{right-109,y+10},{64,28}},[this,index] { if(plan && index+1<int(plan->size())) { moveProductionLine(*plan,index,index+1); if(changed) changed(); } },"Понизить приоритет");
            button(window,font,"X",{{right-39,y+10},{28,28}},[this,index] { if(plan && index<int(plan->size())) { plan->erase(plan->begin()+index); if(changed) changed(); } },"Удалить рецепт");
            for(int n=0;n<4;++n) {
                const int delta=std::array{-10,-1,1,10}[n];
                button(window,font,delta>0 ? "+"+std::to_string(delta) : std::to_string(delta),{{28+42.f*n,y+54},{38,28}},[this,index,delta] {
                    if(plan && index<int(plan->size())) { auto& power=(*plan)[index].power; power=std::max(0.,power+delta); if(changed) changed(); }
                });
            }
            slider(window,{{212,y+54},{std::max(80.f,width-510),28}},index,line.assignedPower,std::max({1.,model.totalPower,line.assignedPower}));
            text(window,font,formatAmount(line.availablePower)+" / "+formatAmount(line.assignedPower)+" ПМ",{width-278,y+57},19,status,240);
            text(window,font,"Вход",{28,y+91},16,muted); text(window,font,"Выход",{width-214,y+91},16,muted);
            const float chipWidth=(width-278)/4; int column=0;
            if(const auto* recipe=productionRecipe(line.recipe))
                for(auto [key,coefficient]:recipe->inputs) if(coefficient>0) {
                    const double amount=value(line.inputs,key);
                    chip(window,font,key,amount,{28+column++*(chipWidth+4),y+116},chipWidth,availability(value(stock,key),amount));
                }
            if(column==0) text(window,font,"Не требуется сырьё",{28,y+128},17,muted);
            for(auto [key,amount]:line.outputs) chip(window,font,key,amount,{width-214,y+116},174,status);
        }
        window.setView(oldView);
        // Hit rectangles are clipped too: hidden cards cannot intercept header/footer clicks.
        for(std::size_t i=headerHits;i<hits.size();++i) { auto& hit=hits[i];
            if(auto intersection=hit.bounds.findIntersection(listBounds)) hit.bounds=*intersection; else hit.bounds={};
        }
        for(auto& s:sliders) if(auto intersection=s.bounds.findIntersection(listBounds)) s.bounds=*intersection; else s.bounds={};
        scrollbar(window,scrollTrack,scroll,maximumScroll,listBounds.size.y);
        if(model.lines.empty()) text(window,font,"Добавьте рецепт, чтобы распределить мощность.",{32,242},22,muted);
        if(catalogOpen) drawCatalog(window,font,stock);
        if(!draggingSlider && !draggingScroll && !draggingCatalog) {
            for(auto it=hits.rbegin();it!=hits.rend();++it) if(!it->help.empty() && it->bounds.contains(pointer)) {
                const float x=std::min(pointer.x+14,float(window.getSize().x)-270), y=std::min(pointer.y+20,bottom-36);
                box(window,{{x,y},{260,32}},{13,20,28,250},{119,145,168}); text(window,font,it->help,{x+8,y+5},16); break;
            }
        }
    }

    void drawCatalog(sf::RenderWindow& window,const sf::Font& font,const Stockpile& stock) {
        hits.clear(); sliders.clear();
        box(window,{{0,90},{float(window.getSize().x),float(window.getSize().y)-90}},{8,13,19,180});
        const float left=36, top=112, width=std::min(860.f,float(window.getSize().x)-72), bottom=float(window.getSize().y)-30;
        box(window,{{left,top},{width,bottom-top}},{25,36,47},{133,153,172});
        text(window,font,"Добавить рецепт",{left+20,top+15},26);
        button(window,font,"X",{{left+width-40,top+14},{28,28}},[this] { catalogOpen=confirmDuplicate=false; },"Закрыть каталог");
        text(window,font,"Доступные • уже добавленные — серым",{left+20,top+58},17,muted,width-40);
        std::vector<const Recipe*> catalog;
        for(const auto& recipe:recipes) if(recipe.building==industry) catalog.push_back(&recipe);
        const auto exists=[this](std::string_view id) { return plan && std::ranges::any_of(*plan,[&](auto line) { return line.recipe==id; }); };
        std::stable_sort(catalog.begin(),catalog.end(),[&](auto a,auto b) { return exists(a->id)<exists(b->id); });
        if(selected.empty()) selected=catalog.front()->id;
        catalogBounds={{left+12,top+94},{width*.46f-28,std::max(80.f,bottom-top-112)}};
        catalogTrack={{catalogBounds.position.x+catalogBounds.size.x+2,catalogBounds.position.y},{12,catalogBounds.size.y}};
        catalogMaximumScroll=std::max(0.f,float(catalog.size())*54-catalogBounds.size.y);
        catalogScroll=std::clamp(catalogScroll,0.f,catalogMaximumScroll);
        auto old=clip(window,catalogBounds);
        for(int i=0;i<int(catalog.size());++i) {
            const auto* recipe=catalog[i]; const float y=catalogBounds.position.y+i*54-catalogScroll;
            if(y+50<catalogBounds.position.y || y>bottom) continue;
            const sf::FloatRect rect{{catalogBounds.position.x,y},{catalogBounds.size.x,50}};
            const bool added=exists(recipe->id); const auto color=added ? sf::Color(129,144,157) : green;
            box(window,rect,selected==recipe->id ? sf::Color(51,73,91) : sf::Color(31,44,56),selected==recipe->id ? sf::Color(185,200,164) : sf::Color(66,84,100));
            productionGlyph(window,rect.position+sf::Vector2f{7,9},32,recipe->id,color);
            text(window,font,name(recipe->id),rect.position+sf::Vector2f{48,12},19,color,rect.size.x-56);
            if(auto clipped=rect.findIntersection(catalogBounds)) hits.push_back({*clipped,[this,id=recipe->id] { selected=id; confirmDuplicate=false; },added ? "Рецепт уже есть в производстве" : "Посмотреть рецепт"});
        }
        window.setView(old); scrollbar(window,catalogTrack,catalogScroll,catalogMaximumScroll,catalogBounds.size.y);
        const auto* recipe=productionRecipe(selected); if(!recipe) return;
        const float x=left+width*.49f, detailWidth=width*.49f-20;
        productionGlyph(window,{x,top+100},46,selected);
        text(window,font,name(selected),{x+54,top+103},23,sf::Color::White,detailWidth-54);
        text(window,font,"Назначить: "+formatAmount(previewPower)+" ПМ",{x,top+160},21,yellow);
        slider(window,{{x,top+195},{detailWidth,28}},-1,previewPower,std::max({1.,totalPower,previewPower}));
        text(window,font,"Вход за месяц",{x,top+239},19,muted);
        float y=top+270;
        for(auto [key,amount]:recipe->inputs) if(amount>0) {
            const double need=amount*recipe->rate*previewPower/recipe->powerCost;
            chip(window,font,key,need,{x,y},detailWidth,availability(value(stock,key),need)); y+=54;
        }
        if(recipe->inputs.empty()) { text(window,font,"Не требуется сырьё",{x,y},18,muted); y+=35; }
        text(window,font,"Выход за месяц",{x,y+4},19,muted); y+=34;
        for(auto [key,amount]:recipe->outputs) { chip(window,font,key,amount*recipe->rate*previewPower/recipe->powerCost,{x,y},detailWidth,green); y+=54; }
        button(window,font,"Добавить рецепт",{{x,bottom-58},{detailWidth,36}},[this] {
            if(plan && std::ranges::any_of(*plan,[this](auto line) { return line.recipe==selected; })) confirmDuplicate=true;
            else appendSelected();
        },"Добавить в конец списка — низший приоритет");
        if(confirmDuplicate) {
            hits.clear(); sliders.clear();
            box(window,{{left,top},{width,bottom-top}},{8,13,19,210});
            const float y=top+190;
            box(window,{{left+80,y},{width-160,180}},{31,44,57},{181,157,104});
            text(window,font,"Такой рецепт уже существует",{left+104,y+20},24,yellow,width-210);
            text(window,font,"Добавить ещё одну отдельную строку?",{left+104,y+65},20,sf::Color::White,width-210);
            button(window,font,"Да, добавить",{{left+104,y+118},{190,36}},[this] { appendSelected(); });
            button(window,font,"Нет",{{left+310,y+118},{100,36}},[this] { confirmDuplicate=false; });
        }
    }
};
}
