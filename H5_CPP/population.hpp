#pragma once

#include "market.hpp"

namespace hoi5 {

inline double populationResourceRatio(const Production& production,const Stockpile& stock,std::string_view key) {
    double input = 0, output = 0;
    for (const auto& stage : production) {
        input += value(stage.inputs,key);
        output += value(stage.outputs,key);
    }
    return input > 0 ? std::clamp((value(stock,key)+output)/input,0.,1.25) : 1.25;
}

inline double populationGrowthMultiplier(double food,double goods,double supply) {
    const double welfare = std::min(food,goods);
    const double welfareFactor = welfare >= 1 ? std::min(1.15,.95+(welfare-1)*.2) :
        welfare >= .70 ? (welfare-.70)/.30 : -std::min(2.,(.70-welfare)/.70*1.8);
    return welfareFactor*(.45+.55*std::clamp(supply,0.,1.));
}

template<class Tile>
double populationCapacity(const Tile& tile) {
    constexpr std::array<double,buildingCount> rates{
        10000000,2200000,90000,80000,320000,70000,180000,110000,520000,180000,130000
    };
    double capacity = tile.water ? 0 : 55000;
    for (int i = 0; i < buildingCount; ++i) capacity += std::max(0.,tile.buildings[i].area)*rates[i];
    return capacity;
}

inline double tilePopulationGrowthDelta(double population,double capacity,double months,double multiplier) {
    if (population <= 0 || capacity <= 0 || multiplier <= 0) return 0.;
    const double free = std::max(0.,1.20*capacity-population);
    const double pressure = std::max(0.,.10+.90*(1.20*capacity-population)/population);
    return std::min(free,population*.001*months*multiplier*pressure);
}

template<class Tile>
double populationWeight(const Tile& tile) {
    if (tile.water) return .05;
    const auto type = biome(tile.natural);
    double weight = type == "mountains" || type == "snowy_mountains" || type == "desert" || type == "tundra"
        ? .45 : type == "hills" || type == "swamp" || type == "bog" ? .7 : 1.;
    weight *= .6 + tile.natural.grass*.7 + tile.natural.trees*.25;
    return std::max(.05,weight + tile.buildings[city].area*8 + tile.buildings[village].area*3 + tile.buildings[farms].area*1.5);
}

template<class Tile>
double populationGrowthMultiplier(const std::vector<Tile>& tiles,const std::vector<int>& territory,
                                  double food,double goods) {
    int land = 0;
    double supply = 0;
    for (int i : territory) if (!tiles[i].water) {
        ++land;
        supply += tiles[i].supply;
    }
    return populationGrowthMultiplier(food,goods,supply/std::max(1,land));
}

template<class Tile>
double populationMonthlyForecast(const std::vector<Tile>& tiles,const std::vector<int>& territory,double multiplier) {
    double total = 0.;
    for (int i : territory) {
        const auto& tile = tiles[i];
        const double population = std::max(0.,tile.population);
        total += multiplier > 0 ? tilePopulationGrowthDelta(population,populationCapacity(tile),1.,multiplier) : population;
    }
    return multiplier > 0 ? total : std::max(-total,total*.001*multiplier);
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
    const double multiplier = populationGrowthMultiplier(tiles,territory,
        populationResourceRatio(production,stock,"food"),populationResourceRatio(production,stock,"consumer_goods"));
    for (int i : territory) {
        auto& tile = tiles[i];
        const double capacity = populationCapacity(tile);
        if (tile.population <= 0) continue;
        if (multiplier > 0) tile.population += tilePopulationGrowthDelta(tile.population,capacity,months,multiplier);
        else tile.population *= std::max(0.,1+.001*months*multiplier);
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
