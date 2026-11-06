#pragma once

#include "starting_infrastructure.hpp"
#include <map>

namespace hoi5 {

using Stockpile = std::map<std::string_view, double>;

inline double value(const Stockpile& values, std::string_view name, double fallback = 0) {
    const auto it = values.find(name);
    return it == values.end() ? fallback : it->second;
}

inline Stockpile startingStockpile(unsigned seed, double scale) {
    struct Entry { std::string_view name; int minimum, maximum; double multiplier; };
    constexpr Entry entries[] = {
        {"coal", 20000, 70000, 1.35},
        {"oil", 20000, 70000, 1.7},
        {"natural_gas", 20000, 70000, 1.7},
        {"peat", 20000, 70000, 1.0},
        {"uranium", 20000, 70000, 0.16},
        {"iron_ore", 20000, 70000, 1.0},
        {"copper_ore", 20000, 70000, 1.0},
        {"bauxite", 20000, 70000, 1.0},
        {"lead", 20000, 70000, 1.0},
        {"zinc", 20000, 70000, 1.0},
        {"nickel", 20000, 70000, 1.0},
        {"gold", 20000, 70000, 0.08},
        {"silver", 20000, 70000, 0.18},
        {"rare_earth_metals", 20000, 70000, 0.12},
        {"alloying_additives", 20000, 70000, 1.0},
        {"sulfur", 20000, 70000, 1.0},
        {"potash", 20000, 70000, 1.0},
        {"phosphorite", 20000, 70000, 1.0},
        {"apatite", 20000, 70000, 1.0},
        {"rubber", 20000, 70000, 1.0},
        {"graphite", 20000, 70000, 1.0},
        {"mica", 20000, 70000, 1.0},
        {"quartz", 20000, 70000, 1.0},
        {"steel", 5000, 18000, 1.0},
        {"refined_fuel", 5000, 18000, 6},
        {"chemicals", 5000, 18000, 1.0},
        {"food", 5000, 18000, 15.0},
        {"fertilizer", 5000, 18000, 2.2},
        {"copper_wire", 5000, 18000, 1.0},
        {"consumer_goods", 1500, 8000, 12.0},
        {"machinery", 1500, 8000, 1.0},
        {"vehicles", 1500, 8000, 1.0},
        {"electronics", 1500, 8000, 0.65},
        {"construction_goods", 1500, 8000, 12.0},
        {"weapons", 1500, 8000, 0.55},
        {"infantry_equipment", 1500, 8000, 1.35},
        {"old_assault_rifles", 1500, 8000, 1.25},
        {"small_arms_ammo", 1500, 8000, 5.0},
        {"old_light_artillery", 1500, 8000, 0.35},
        {"light_artillery_ammo", 1500, 8000, 1.35},
        {"old_light_aa_artillery", 1500, 8000, 0.28},
        {"light_aa_ammo", 1500, 8000, 1.25},
        {"old_ifv", 1500, 8000, 0.32},
        {"old_at_missiles", 1500, 8000, 0.75},
        {"autocannon_ammo", 1500, 8000, 1.3},
        {"artillery_ammo", 1500, 8000, 1.45},
        {"tank_ammo", 1500, 8000, 0.7},
        {"anti_air_ammo", 1500, 8000, 0.6},
        {"spare_parts", 1500, 8000, 1.4},
        {"field_supplies", 1500, 8000, 2.25},
        {"ships", 1500, 8000, 0.25},
    };
    PythonSeed input{(std::uint64_t(seed) + 1) * 1009};
    std::mt19937 rng(input);
    Stockpile result;
    for (const auto& entry : entries) {
        const auto high = rng() >> 5;
        const auto low = rng() >> 6;
        const double draw = (high * 67108864. + low) / 9007199254740992.;
        result.emplace(entry.name, (entry.minimum + (entry.maximum-entry.minimum)*draw) * entry.multiplier * scale);
    }
    return result;
}

template<class Tile>
void compensateStartingResources(const std::vector<Tile>& tiles, int owner, const std::vector<int>& land,
                                 double unspent, StartingProfile& profile, Stockpile& stocks) {
    double bonus = std::max(0., unspent) * 30000000;
    Stockpile deposits;
    for (const auto& tile : tiles)
        if (tile.owner == owner)
            for (const auto& deposit : tile.deposits) deposits[deposit.resource] += deposit.mass;
    const auto shortage = [&](std::initializer_list<std::string_view> names, double target) {
        double total = 0;
        for (auto name : names) total += deposits[name];
        return std::clamp(1-total/target,0.,1.);
    };
    const auto add = [&](std::string_view name, double amount, double price) {
        stocks[name] += amount;
        bonus += amount * price;
    };
    const double fuel = shortage({"coal","oil","natural_gas","peat"},650000);
    bonus += 14000000 * fuel;
    add("coal",55000*fuel,180);
    const double metal = shortage({"iron_ore","copper_ore","bauxite"},450000);
    bonus += 18000000 * metal;
    add("iron_ore",45000*metal,280);
    add("copper_ore",20000*metal,420);

    double farmCoverage = 0, best = 0;
    std::vector<double> agriculture;
    for (int i : land) {
        farmCoverage += tiles[i].buildings[farms].area;
        agriculture.push_back(agricultureScore(tiles[i].natural));
    }
    std::sort(agriculture.begin(), agriculture.end(), std::greater<>());
    for (std::size_t i = 0; i < std::min(std::size_t(6),agriculture.size()); ++i) best += agriculture[i];
    const double food = std::clamp(std::max(1-farmCoverage/1.05,1-best/2.4),0.,1.);
    if (food > .15) {
        bonus += 10000000 * food;
        add("food",90000*food,260);
        add("fertilizer",22000*food,320);
    }
    profile.budget += std::min(bonus,120000000.);
}

}
