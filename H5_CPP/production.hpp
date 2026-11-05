#pragma once

#include "production_data.hpp"
#include <set>

namespace hoi5 {

template<class Tile>
std::vector<std::string_view> industryAllocation(const std::vector<Tile>& tiles, int size, int index,
                                                 double& consumerScore) {
    const auto& tile = tiles[index];
    const int q = index % size, r = index / size;
    const auto nearby = [&](int radius, auto value) {
        double total = 0;
        for (int dq = -radius; dq <= radius; ++dq) for (int dr = -radius; dr <= radius; ++dr) {
            const int distance = std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
            if (distance > radius || q+dq < 0 || q+dq >= size || r+dr < 0 || r+dr >= size) continue;
            const auto& other = tiles[(r+dr)*size+q+dq];
            if (other.owner == tile.owner) total += value(other) / std::max(1,distance);
        }
        return std::clamp(total,0.,1.);
    };
    const auto coverage = [&](int radius, Building building) {
        return nearby(radius,[&](const Tile& other) { return other.buildings[building].area; });
    };
    std::vector<ResourceWeight> scores;
    for (const auto& sector : sectors) {
        const auto score = [&](const Tile& other) { return resourceScore(other.deposits, sector.weights); };
        scores.emplace_back(sector.name, std::clamp(score(tile)+nearby(3,score)*.75,0.,1.));
    }
    scores.emplace_back("consumer_goods",0.);
    const auto score = [&](std::string_view key) -> double& {
        return std::find_if(scores.begin(),scores.end(),[&](const auto& item) { return item.first == key; })->second;
    };
    const double cityScore = coverage(3,city), villageScore = coverage(2,village);
    const double portScore = coverage(3,port), mineScore = coverage(2,mine), refineryScore = coverage(2,refinery);
    const double pass = 1 / tile.movementCost;
    score("consumer_goods") = consumerScore = std::clamp(.16+cityScore*.82+villageScore*.34+pass*.20,0.,1.);
    score("machinery") += cityScore*.28+mineScore*.24+pass*.14;
    score("vehicles") += cityScore*.20+portScore*.18+refineryScore*.14+pass*.12;
    score("metallurgy") += mineScore*.18;
    score("construction_materials") += cityScore*.16+mineScore*.10;
    score("chemicals") += refineryScore*.24+cityScore*.10;
    score("electronics") += cityScore*.30+pass*.08;
    score("shipbuilding") += portScore*.65;
    score("weapons") += cityScore*.12+score("metallurgy")*.14;
    for (auto& [key,value] : scores) value = std::clamp(value,0.,1.);
    std::stable_sort(scores.begin(),scores.end(),[](const auto& a,const auto& b) { return a.second > b.second; });
    std::vector allocation{scores.front().first};
    if (scores[1].second >= scores[0].second*.72) allocation.push_back(scores[1].first);
    if (scores[2].second >= scores[0].second*.88) allocation.push_back(scores[2].first);
    return allocation;
}

template<class Tile>
void assignStartingIndustry(std::vector<Tile>& tiles, int size, const std::vector<int>& land) {
    std::vector<std::pair<int,double>> industrial;
    double total = 0, consumer = 0;
    const auto consumerCoverage = [](const Tile& tile) {
        const auto& sectors = tile.industries;
        return std::find(sectors.begin(),sectors.end(),"consumer_goods") == sectors.end()
            ? 0. : tile.buildings[industry].area / sectors.size();
    };
    for (int index : land) {
        auto& tile = tiles[index];
        if (tile.buildings[industry].area <= 0) continue;
        double score = 0;
        tile.industries = industryAllocation(tiles,size,index,score);
        industrial.emplace_back(index,score);
        total += tile.buildings[industry].area;
        consumer += consumerCoverage(tile);
    }
    std::sort(industrial.begin(),industrial.end(),[&](const auto& a,const auto& b) {
        return std::tuple{-a.second,-tiles[a.first].buildings[industry].area,a.first%size,a.first/size}
             < std::tuple{-b.second,-tiles[b.first].buildings[industry].area,b.first%size,b.first/size};
    });
    for (const auto& [index,score] : industrial) {
        if (consumer >= total*.30) break;
        auto& tile = tiles[index];
        const double previous = consumerCoverage(tile);
        if (previous >= tile.buildings[industry].area*.45) continue;
        auto& allocation = tile.industries;
        std::erase(allocation,std::string_view("consumer_goods"));
        allocation.insert(allocation.begin(),"consumer_goods");
        if (allocation.size() > 2) allocation.resize(2);
        consumer += consumerCoverage(tile)-previous;
    }
}

template<class Tile>
void accumulateTileProduction(Production& result,const Tile& tile,
                              const std::set<std::string_view>& technologies) {
    const auto effective = [&](Building building) {
        const auto& b = tile.buildings[building];
        return b.area * b.health;
    };
    for (const auto& deposit : tile.deposits) {
        const bool liquid = deposit.resource == "oil" || deposit.resource == "natural_gas";
        const double area = effective(liquid ? oilGasRig : mine);
        if (area <= 0) continue;
        const double abundance = std::min(1.,std::log10(deposit.mass+1)/std::log10(1500001.));
        const auto found = mineWeights.find(deposit.resource);
        const double weight = found == mineWeights.end() ? .35 : found->second;
        result[raw].outputs[deposit.resource] += area * abundance *
            (liquid ? (.62+weight)*5600 : (.55+weight)*5200);
    }
    const double farmCoverage = effective(farms);
    if (farmCoverage > 0) {
        const double food = farmCoverage * agricultureScore(tile.natural) * 30000;
        result[raw].outputs["food"] += food;
        result[agriculture].inputs["fertilizer"] += farmCoverage*950;
        result[agriculture].outputs["food"] += food*.30;
    }
    for (const auto& recipe : recipes) {
        if (!recipe.technology.empty() && !technologies.contains(recipe.technology)) continue;
        double units = recipe.rate * effective(recipe.building);
        if (units <= 0) continue;
        if (recipe.building == industry) {
            const auto& allocation = tile.industries;
            if (std::find(allocation.begin(),allocation.end(),recipe.sector) == allocation.end()) continue;
            units *= std::pow(.9, allocation.size()-1) / allocation.size();
        }
        for (const auto& [name,amount] : recipe.inputs) result[recipe.stage].inputs[name] += amount*units;
        for (const auto& [name,amount] : recipe.outputs) result[recipe.stage].outputs[name] += amount*units;
    }
    for (const auto& [name,amount] : cityUpkeep) result[upkeep].inputs[name] += effective(city)*amount;
    for (const auto& [name,amount] : villageUpkeep) result[upkeep].inputs[name] += effective(village)*amount;
}

template<class Tile>
Production buildProduction(const std::vector<Tile>& tiles, int country, double population,
                           const std::set<std::string_view>& technologies) {
    Production result;
    for (const auto& tile : tiles)
        if (tile.owner == country) accumulateTileProduction(result,tile,technologies);
    for (const auto& [name,amount] : lifeSupport) result[upkeep].inputs[name] += population/1e6*amount;
    return result;
}

template<class AddStock>
std::array<double,productionStages> runProduction(const Production& production, Stockpile& stock,
                                                  int hours, AddStock addStock) {
    std::array<double,productionStages> ratios{};
    const double fraction = hours / 720.;
    for (int stage = 0; stage < productionStages; ++stage) {
        const auto& [inputs,outputs] = production[stage];
        double ratio = 1;
        for (const auto& [name,amount] : inputs)
            if (amount > 0) ratio = std::min(ratio,stock[name]/(amount*fraction));
        ratio = std::clamp(ratio,0.,1.);
        ratios[stage] = ratio;
        for (const auto& [name,amount] : inputs) {
            auto& stored = stock[name];
            stored = std::max(0.,stored-amount*fraction*(stage == upkeep ? 1. : ratio));
        }
        for (const auto& [name,amount] : outputs) addStock(name,amount*fraction*ratio);
    }
    return ratios;
}

}
