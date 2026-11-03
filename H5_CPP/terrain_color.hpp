#pragma once

#include "map_data.hpp"
#include <SFML/Graphics/Color.hpp>

namespace hoi5 {

inline sf::Color terrainColor(const Terrain& tile) {
    using Rgb = std::array<int, 3>;
    const auto blend = [](Rgb from, Rgb to, double amount) {
        amount = std::clamp(amount, 0., 1.);
        for (int i = 0; i < 3; ++i)
            from[i] = std::clamp(int(from[i] * (1 - amount) + to[i] * amount), 0, 255);
        return from;
    };
    const auto type = biome(tile);
    Rgb color;
    if (tile.water > .5) {
        color = type == "deep_ocean" ? Rgb{22, 55, 126} : type == "ocean" ? Rgb{36, 92, 168}
            : type == "shallow_water" ? Rgb{65, 151, 205} : Rgb{76, 165, 214};
        color = blend(color, {255, 255, 255}, tile.moisture * .18 + tile.temperature * .08);
    } else {
        static constexpr std::pair<std::string_view, Rgb> baseColors[] = {
            {"grassland", {100, 180, 100}}, {"plains", {150, 200, 100}}, {"savanna", {210, 180, 140}},
            {"tundra", {200, 220, 200}}, {"desert", {238, 203, 173}}, {"temperate_forest", {34, 139, 34}},
            {"tropical_rainforest", {20, 150, 20}}, {"jungle", {30, 120, 30}}, {"taiga", {60, 90, 60}},
            {"hills", {139, 119, 101}}, {"mountains", {120, 120, 120}}, {"snowy_mountains", {220, 240, 255}}
        };
        for (const auto& [name, rgb] : baseColors)
            if (name == type) color = rgb;
        const std::array weights{tile.rock, tile.sand, tile.snow, tile.trees, tile.grass};
        constexpr std::array<Rgb, 5> components{{{120,120,120}, {238,203,173}, {240,248,255}, {34,139,34}, {100,180,100}}};
        for (int channel = 0; channel < 3; ++channel) {
            double sum = color[channel] * .5, weight = .5;
            for (int i = 0; i < 5; ++i) {
                sum += components[i][channel] * weights[i];
                weight += weights[i];
            }
            color[channel] = static_cast<int>(sum / weight);
        }
        if (tile.snow > .18) color = blend(color, {240, 248, 255}, std::min(.35, tile.snow * .5));
        const double shade = (tile.elevation - .48) * .28 + tile.ridge * .08;
        color = blend(color, shade >= 0 ? Rgb{255, 255, 255} : Rgb{0, 0, 0}, std::abs(shade));
    }
    return sf::Color(color[0], color[1], color[2]);
}

}
