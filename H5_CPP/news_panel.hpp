#pragma once

#include "news.hpp"
#include <SFML/Graphics.hpp>
#include <chrono>
#include <iomanip>
#include <sstream>

namespace hoi5 {

class NewsPanel {
    int seen{}, popup{}, archiveScroll{}, popupScroll{};
    std::size_t tickerIndex{};
    float tickerPosition{};
    bool archive{};
    std::deque<int> pending;
    std::vector<const NewsItem*> items;
    std::vector<std::pair<sf::FloatRect,int>> archiveHits;
    sf::FloatRect tickerRect, archiveRect, popupRect;
    std::vector<sf::String> bodyLines;

    static sf::String utf8(std::string_view value) {
        return sf::String::fromUtf8(value.begin(),value.end());
    }

    static void text(sf::RenderWindow& window,const sf::Font& font,const sf::String& value,
                     sf::Vector2f point,unsigned size = 12,sf::Color color = {222,233,242}) {
        sf::Text label(font,value,size);
        const auto bounds = label.getLocalBounds();
        label.setOrigin({0,bounds.position.y+bounds.size.y*.5f});
        label.setPosition(point);
        label.setFillColor(color);
        window.draw(label);
    }

    static void box(sf::RenderWindow& window,sf::FloatRect rect,sf::Color fill,
                    sf::Color border = sf::Color::Transparent,float thickness = 1) {
        sf::RectangleShape shape(rect.size);
        shape.setPosition(rect.position);
        shape.setFillColor(fill);
        shape.setOutlineColor(border);
        shape.setOutlineThickness(-thickness);
        window.draw(shape);
    }

    static sf::Color color(const NewsItem& item) {
        constexpr std::array colors{sf::Color(170,188,202),sf::Color(170,210,235),
            sf::Color(242,190,105),sf::Color(242,112,104)};
        return colors[static_cast<int>(item.priority)];
    }

    static sf::String dateAndPriority(const NewsItem& item) {
        using namespace std::chrono;
        const year_month_day date{sys_days{year{2000}/1/1}+days{item.day}};
        std::ostringstream out;
        constexpr std::array labels{"В мире","Новости","Важно","Срочно"};
        out << int(date.year()) << '-' << std::setfill('0') << std::setw(2) << unsigned(date.month())
            << '-' << std::setw(2) << unsigned(date.day()) << " · " << labels[static_cast<int>(item.priority)];
        return utf8(out.str());
    }

    static std::vector<sf::String> wrap(std::string_view value,std::size_t width) {
        std::vector<sf::String> lines;
        auto remaining = utf8(value);
        remaining.replace(U"\n",U" ");
        while (remaining.getSize() > width) {
            std::size_t end = width;
            while (end > 0 && remaining[end] != U' ') --end;
            if (!end) end = width;
            lines.push_back(remaining.substring(0,end));
            const auto start = end+(remaining[end] == U' ' ? 1 : 0);
            remaining = remaining.substring(start);
        }
        lines.push_back(std::move(remaining));
        return lines;
    }

    const NewsItem* find(int id) const {
        const auto it = std::ranges::find_if(items,[&](auto item) { return item->id == id; });
        return it == items.end() ? nullptr : *it;
    }

    int popupRows() const { return std::max(1,int((popupRect.size.y-122)/21)); }
    int archiveRows() const { return std::max(1,int((archiveRect.size.y-65)/48)); }

public:
    sf::FloatRect tickerBounds() const { return tickerRect; }
    sf::FloatRect popupBounds() const { return popupRect; }
    const NewsItem* activeItem() const { return find(popup); }

    bool openItem(int id) {
        if (!find(id)) return false;
        archive = false;
        popup = id;
        popupScroll = 0;
        std::erase(pending,id);
        return true;
    }

    void update(const News& news,float dt,sf::Vector2f size,float left,float minimumBottom = 0.f,
                float rightInset = 0.f,float popupBottom = 0.f) {
        items = news.visible(0);
        const float margin = size.x >= 1100 ? 310 : 74;
        float width = std::min(560.f,size.x-left-margin);
        float bottom = 16;
        if (width < 200) {
            width = std::min(360.f,size.x-left-16);
            bottom = 70;
        }
        tickerRect = {{left,size.y-std::max(bottom,minimumBottom)-38},{std::max(120.f,width),38}};
        const float available = std::max(180.f,size.x-rightInset-24);
        const float aw = std::min(400.f,available), ah = std::clamp(size.y-215,260.f,440.f);
        const float pw = std::min(350.f,available), ph = std::clamp(size.y-260,155.f,220.f);
        const float overlayBottom = std::max(104.f,popupBottom);
        archiveRect = {{std::max(10.f,size.x-aw-14-rightInset),size.y-ah-std::max(125.f,overlayBottom)},{aw,ah}};
        popupRect = {{std::max(10.f,size.x-pw-14-rightInset),size.y-ph-overlayBottom},{pw,ph}};
        if (popup && !find(popup)) popup = 0;
        if (!items.empty() && items.front()->id > seen) {
            std::erase_if(pending,[&](int id) { return !find(id); });
            int yellow = int(std::ranges::count_if(pending,[&](int id) {
                return find(id)->priority == NewsPriority::important;
            }));
            if (const auto* current = activeItem(); current && current->priority == NewsPriority::important) ++yellow;
            for (auto it = items.rbegin(); it != items.rend(); ++it) {
                const auto& item = **it;
                if (item.id <= seen || !item.important()) continue;
                if (item.priority == NewsPriority::critical) {
                    const auto firstYellow = std::ranges::find_if(pending,[&](int id) {
                        return find(id)->priority == NewsPriority::important;
                    });
                    pending.insert(firstYellow,item.id);
                    if (const auto* current = activeItem(); current && current->priority == NewsPriority::important) {
                        popup = 0;
                        --yellow;
                    } else if (yellow >= 10) {
                        const auto lastYellow = std::find_if(pending.rbegin(),pending.rend(),[&](int id) {
                            return find(id)->priority == NewsPriority::important;
                        });
                        if (lastYellow != pending.rend()) {
                            pending.erase(std::prev(lastYellow.base()));
                            --yellow;
                        }
                    }
                } else if (yellow < 10) {
                    pending.push_back(item.id);
                    ++yellow;
                }
            }
            seen = items.front()->id;
            tickerIndex = 0;
            tickerPosition = 0;
        }
        while (!popup && !archive && !pending.empty()) {
            const int id = pending.front();
            pending.pop_front();
            if (find(id)) { popup = id; popupScroll = 0; }
        }
        if (!items.empty()) {
            tickerIndex %= items.size();
            tickerPosition += std::max(0.f,dt)*9;
            if (tickerPosition >= utf8(items[tickerIndex]->title).getSize()+8) {
                tickerPosition = 0;
                tickerIndex = (tickerIndex+1)%items.size();
            }
        }
    }

    bool click(sf::Vector2f point,bool left) {
        const auto inside = archive ? archiveRect : popup ? popupRect : sf::FloatRect{};
        if (inside.contains(point)) {
            if (!left) return true;
            if (point.x > inside.position.x+inside.size.x-46 && point.y < inside.position.y+48) {
                if (archive) archive = false;
                else popup = 0;
            } else if (archive) {
                for (const auto& [rect,id] : archiveHits)
                    if (rect.contains(point)) {
                        popup = id;
                        popupScroll = 0;
                        archive = false;
                        break;
                    }
            } else if (point.x < inside.position.x+115 && point.y > inside.position.y+inside.size.y-42) {
                popup = 0;
                archive = true;
            }
            return true;
        }
        if (!tickerRect.contains(point)) return false;
        if (left) {
            archive = !archive;
            if (archive) popup = 0;
        }
        return true;
    }

    bool scroll(sf::Vector2f point,float delta) {
        if (archive && archiveRect.contains(point)) {
            archiveScroll = std::clamp(archiveScroll-int(delta*2),0,std::max(0,int(items.size())-archiveRows()));
            return true;
        }
        if (popup && popupRect.contains(point)) {
            popupScroll = std::clamp(popupScroll-int(delta*2),0,std::max(0,int(bodyLines.size())-popupRows()));
            return true;
        }
        return false;
    }

    void draw(sf::RenderWindow& window,const sf::Font& font) {
        const auto [tx,ty] = tickerRect.position;
        const float width = tickerRect.size.x;
        const bool compact = width < 360;
        const float offset = compact ? 96 : 155;
        box(window,tickerRect,{20,29,39,240},{96,122,148});
        text(window,font,utf8(compact ? "Новости" : "Мировые новости"),{tx+10,ty+19},14,{235,239,244});
        if (items.empty()) {
            text(window,font,utf8("Пока нет сообщений"),{tx+offset,ty+19},13);
        } else {
            const auto& item = *items[tickerIndex];
            const auto message = utf8("  •  "+item.title+"  •  ");
            const auto start = std::size_t(tickerPosition)%message.getSize();
            sf::String snippet;
            const auto count = std::max(8,int((width-offset-5)/7));
            for (int i = 0; i < count; ++i) snippet += message[(start+i)%message.getSize()];
            text(window,font,snippet,{tx+offset,ty+19},13,color(item));
        }
        if (archive) {
            const auto [x,y] = archiveRect.position;
            const auto [w,h] = archiveRect.size;
            box(window,archiveRect,{21,29,39,248},{110,137,165},2);
            text(window,font,utf8("Мировые новости и события"),{x+14,y+25},17);
            text(window,font,"X",{x+w-26,y+25},15);
            const int count = archiveRows();
            archiveScroll = std::clamp(archiveScroll,0,std::max(0,int(items.size())-count));
            archiveHits.clear();
            for (int i = 0; i < count && archiveScroll+i < int(items.size()); ++i) {
                const auto& item = *items[archiveScroll+i];
                const float row = y+72+48*i;
                const sf::FloatRect hit({x+10,row-28},{w-20,42});
                box(window,hit,{35,46,59,235});
                text(window,font,dateAndPriority(item),{x+18,row-15},11,color(item));
                text(window,font,utf8(item.title).substring(0,std::max(20,int((w-40)/7))),{x+18,row+4},13);
                archiveHits.emplace_back(hit,item.id);
            }
            if (int(items.size()) > count)
                text(window,font,utf8(std::to_string(archiveScroll+1)+"–"+std::to_string(archiveScroll+count)+
                    " из "+std::to_string(items.size())+" · колесо мыши"),{x+14,y+h-18},10,{170,188,202});
        } else if (const auto* item = find(popup)) {
            const auto [x,y] = popupRect.position;
            const auto [w,h] = popupRect.size;
            box(window,popupRect,{24,32,43,248},color(*item),2);
            text(window,font,dateAndPriority(*item),{x+14,y+24},12,color(*item));
            text(window,font,"X",{x+w-25,y+24},15);
            const auto lineWidth = std::max(25,int((w-30)/7.5));
            const auto title = wrap(item->title,lineWidth);
            for (int i = 0; i < 2 && i < int(title.size()); ++i)
                text(window,font,title[i],{x+14,y+52+20*i},15);
            bodyLines = wrap(item->body,lineWidth);
            const int count = popupRows();
            popupScroll = std::clamp(popupScroll,0,std::max(0,int(bodyLines.size())-count));
            for (int i = 0; i < count && popupScroll+i < int(bodyLines.size()); ++i)
                text(window,font,bodyLines[popupScroll+i],{x+14,y+102+21*i},13,{205,219,232});
            text(window,font,utf8("Все новости"),{x+14,y+h-19},13,{150,204,241});
            if (int(bodyLines.size()) > count)
                text(window,font,utf8(std::to_string(popupScroll+1)+"/"+
                    std::to_string(bodyLines.size()-count+1)+" ↓"),{x+w-76,y+h-19},10,{170,188,202});
        }
    }
};

}
