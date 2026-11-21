#pragma once
#include <SFML/Graphics.hpp>
#include <algorithm>
#include <string_view>
#include <span>

namespace hoi5 {
// The native application currently has no network session. Keep this gate explicit.
struct DeveloperMenu {
    bool open{}, countries{};
    int scroll{};
    static constexpr bool singlePlayerSession = true;
    sf::FloatRect panel(sf::Vector2u size) const {
        return {{std::max(8.f,float(size.x)-610.f),100.f},{600.f,std::max(150.f,float(size.y)-120.f)}};
    }
    int rows(sf::Vector2u size) const { return std::max(1,int((panel(size).size.y-60)/34)); }
    // -1: no selection. All events are consumed by the caller while open.
    int event(const sf::Event& event,sf::Vector2u size,int count) {
        if (const auto* key = event.getIf<sf::Event::KeyPressed>())
            if (key->code == sf::Keyboard::Key::Escape) open = false;
        if (const auto* wheel = event.getIf<sf::Event::MouseWheelScrolled>())
            scroll = std::clamp(scroll-int(wheel->delta*3),0,std::max(0,count-rows(size)));
        if (const auto* click = event.getIf<sf::Event::MouseButtonPressed>(); click && click->button == sf::Mouse::Button::Left) {
            const auto p = panel(size).position;
            const sf::Vector2f mouse(click->position);
            if (sf::FloatRect(p+sf::Vector2f{12,52},{180,36}).contains(mouse)) countries = true;
            if (countries && mouse.x >= p.x+210 && mouse.x < p.x+588 && mouse.y >= p.y+52) {
                const int row = int((mouse.y-p.y-52)/34);
                if (row < rows(size) && row+scroll < count) return row+scroll;
            }
        }
        return -1;
    }
    void draw(sf::RenderWindow& window,const sf::Font& font,std::span<const std::string_view> names,int current) const {
        if (!open) return;
        const auto bounds = panel(window.getSize());
        const auto p = bounds.position;
        const auto box = [&](sf::FloatRect rect,sf::Color color) {
            sf::RectangleShape shape(rect.size); shape.setPosition(rect.position); shape.setFillColor(color); window.draw(shape);
        };
        const auto text = [&](std::string_view value,sf::Vector2f position,unsigned size) {
            sf::Text label(font,sf::String::fromUtf8(value.begin(),value.end()),size);
            label.setPosition(position); window.draw(label);
        };
        box(bounds,{20,28,38,250});
        text("Разработчик · одиночная игра · F4",p+sf::Vector2f{12,12},19);
        box({p+sf::Vector2f{12,52},{180,36}},{55,75,95});
        text("Сменить игрока",p+sf::Vector2f{20,60},17);
        if (!countries) return;
        for (int row = 0; row < rows(window.getSize()) && row+scroll < int(names.size()); ++row) {
            const int id = row+scroll;
            const auto point = p+sf::Vector2f{210,52+34.f*row};
            box({point,{378,31}},id == current ? sf::Color{48,108,82} : sf::Color{42,57,74});
            text(names[id],point+sf::Vector2f{8,5},16);
        }
    }
};
}
