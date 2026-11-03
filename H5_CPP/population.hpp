#pragma once

#include "market.hpp"

namespace hoi5 {

template<class Tile>
double populationCapacity(const Tile& tile) {
    constexpr std::array<double,buildingCount> rates{
        10000000,2200000,90000,80000,320000,70000,180000,110000,520000,180000,130000
    };
    double capacity = tile.water ? 0 : 55000;
    for (int i = 0; i < buildingCount; ++i) capacity += tile.buildings[i].area*rates[i];
    return capacity;
}

template<class Tile>
double populationWeight(const Tile& tile) {
    if (tile.water) return .05;
    const auto type = biome(tile.natural);
    double weight = type == "mountains" || type == "snowy_mountains" || type == "desert" || type == "tundra"
        ? .45 : type == "hills" ? .7 : 1.;
    weight *= .6 + tile.natural.grass*.7 + tile.natural.trees*.25;
    return std::max(.05,weight + tile.buildings[city].area*8 + tile.buildings[village].area*3 + tile.buildings[farms].area*1.5);
}

template<class Tile>
double enforcePopulation(std::vector<Tile>& tiles,const std::vector<int>& territory) {
    double excess = 0;
    for (int i : territory) {
        auto& tile = tiles[i];
        const double max = populationCapacity(tile)*1.20;
        if (tile.population <= max) continue;
        excess += tile.population-max;
        tile.population = max;
    }
    struct Candidate { int tile; double free, weight; };
    for (int pass = 0; pass < 3 && excess > 0; ++pass) {
        std::vector<Candidate> candidates;
        double total = 0;
        for (int i : territory) {
            const auto& tile = tiles[i];
            const double free = populationCapacity(tile)*1.20-tile.population;
            if (free <= 1) continue;
            const double weight = free*(.35+populationWeight(tile));
            candidates.push_back({i,free,weight});
            total += weight;
        }
        if (total <= 0) break;
        double added = 0;
        for (const auto& candidate : candidates) {
            const double delta = std::min(candidate.free,excess*candidate.weight/total);
            tiles[candidate.tile].population += delta;
            added += delta;
        }
        excess -= added;
        if (added <= 0) break;
    }
    double total = 0;
    for (int i : territory) total += tiles[i].population;
    return total;
}

template<class Tile>
double runPopulationMonth(std::vector<Tile>& tiles,const std::vector<int>& territory,
                          const Production& production,const Stockpile& stock,double months) {
    const double population = enforcePopulation(tiles,territory);
    if (population <= 0) return 0;
    const auto resourceRatio = [&](std::string_view key) {
        double input = 0, output = 0;
        for (const auto& stage : production) {
            input += value(stage.inputs,key);
            output += value(stage.outputs,key);
        }
        return input > 0 ? std::clamp((value(stock,key)+output)/input,0.,1.25) : 1.25;
    };
    const double welfare = std::min(resourceRatio("food"),resourceRatio("consumer_goods"));
    const double welfareFactor = welfare >= 1 ? std::min(1.15,.95+(welfare-1)*.2) :
        welfare >= .70 ? (welfare-.70)/.30 : -std::min(2.,(.70-welfare)/.70*1.8);
    int land = 0;
    double supply = 0;
    for (int i : territory) if (!tiles[i].water) {
        ++land;
        supply += tiles[i].supply;
    }
    const double multiplier = welfareFactor*(.45+.55*supply/std::max(1,land));
    for (int i : territory) {
        auto& tile = tiles[i];
        const double capacity = populationCapacity(tile);
        if (tile.population <= 0) continue;
        if (multiplier > 0 && capacity > 0) {
            const double free = std::max(0.,1.20*capacity-tile.population);
            const double pressure = std::max(0.,.10+.90*(1.20*capacity-tile.population)/tile.population);
            tile.population += std::min(free,tile.population*.001*months*multiplier*pressure);
        } else if (multiplier <= 0) tile.population *= std::max(0.,1+.001*months*multiplier);
        if (capacity <= 0 || tile.population <= capacity) continue;
        const double overcrowding = std::clamp((tile.population/capacity-1)/.20,0.,1.);
        for (const auto [building,rate,maximum] : std::array{
            std::tuple{city,.015,.72},std::tuple{village,.025,.30}
        }) {
            auto& area = tile.buildings[building].area;
            if (area > 0 && area < maximum) area = std::min(maximum,area*(1+rate/12*months*overcrowding));
        }
    }
    return enforcePopulation(tiles,territory);
}

}
