#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <span>
#include <vector>
#include "simulation_workers.hpp"

namespace hoi5 {

enum Building { city, village, warehouse, supplyDepot, port, fuelStorage, refinery, oilGasRig, industry, farms, mine, airbase, fortification, fieldHelipad, buildingCount };

struct BuildingCoverage {
    double area{};
    double health = 1;
};

inline constexpr std::array<double,buildingCount> supplySourceWeights{1.,.48,.50,.92,.46,.22,.30,.18,.18};

template<class Tile>
double supplySourceStrength(const Tile& tile,bool capital) {
    double strength = capital ? .85 : 0.;
    for (int b = 0; b < buildingCount; ++b)
        strength += tile.buildings[b].area*tile.buildings[b].health*supplySourceWeights[b];
    return std::clamp(strength,0.,1.);
}

template<class Tile>
void recalculateSupply(std::span<Tile> tiles, int size, const std::vector<int>& capitals,
                       SimulationWorkers* workers=nullptr,const std::vector<std::vector<int>>* territory=nullptr,
                       const std::vector<unsigned char>* changed=nullptr) {
    constexpr std::array<double,buildingCount> relayWeights{0., 0., .28, .72, .22, 0., 0., 0., 0., 0., 0., 0.};
    struct SupplyOffset { int q, r; double factor; };
    static const auto offsets = [] {
        std::array<double,8> decay{};
        for (int d = 0; d <= 7; ++d) decay[d] = std::pow(.78,d);
        std::array<SupplyOffset,169> result{};
        std::size_t i = 0;
        for (int dq = -7; dq <= 7; ++dq)
            for (int dr = -7; dr <= 7; ++dr) {
                const int distance = std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
                if (distance <= 7) result[i++] = {dq,dr,decay[distance]};
            }
        return result;
    }();
    for (auto& tile : tiles) if(!changed || tile.owner<0 || tile.owner>=int(changed->size()) || (*changed)[tile.owner]) tile.supply = 0;
    const auto effective = [](const BuildingCoverage& building) {
        return building.area * building.health;
    };
    const auto spread = [&](int index,int country,double strength) {
        const int q = index % size, r = index / size;
        for (const auto [dq,dr,factor] : offsets) {
            if (q + dq < 0 || q + dq >= size || r + dr < 0 || r + dr >= size) continue;
            auto& tile = tiles[(r + dr) * size + q + dq];
            if (tile.owner == country && !tile.water)
                tile.supply = std::max(tile.supply, strength * factor);
        }
    };
    std::vector<std::vector<int>> grouped;
    if(!territory) {
        grouped.resize(capitals.size());
        for(int i=0;i<int(tiles.size());++i) if(tiles[i].owner>=0 && tiles[i].owner<int(grouped.size())) grouped[tiles[i].owner].push_back(i);
    }
    const auto& owned=territory?*territory:grouped;
    std::vector<double> updates(tiles.size());
    const auto countryWork=[&](std::size_t country) {
    bool hasSource=false;
    for (int index:owned[country]) {
        const auto& source = tiles[index];
        if (source.water || source.owner < 0) continue;
        const double strength = supplySourceStrength(source,index == capitals[source.owner]);
        if (strength <= 0) continue;
        hasSource = true;
        spread(index,source.owner,std::clamp(strength,0.,1.));
    }
        if (!hasSource && capitals[country] >= 0)
            spread(capitals[country],country,.65);
    const auto passability = [](const Tile& tile) { return std::clamp(1. / tile.movementCost, 0., 1.); };
    for (int index:owned[country]) tiles[index].supply *= .42 + passability(tiles[index]) * .58;

    for (int pass = 0; pass < 2; ++pass) {
        for(int index:owned[country]) updates[index]=0.;
        for (int index:owned[country]) {
            const auto& tile = tiles[index];
            if (tile.owner < 0 || tile.water) continue;
            double relay = 0;
            for (int b = 0; b < buildingCount; ++b) relay += effective(tile.buildings[b]) * relayWeights[b];
            if (relay <= 0) continue;
            const int q = index % size, r = index / size, shift = r % 2;
            const std::array<std::pair<int, int>, 6> offsets{{
                {shift, 1}, {shift - 1, 1}, {-1, 0}, {shift - 1, -1}, {shift, -1}, {1, 0}
            }};
            for (const auto [dq, dr] : offsets) {
                if (q + dq < 0 || q + dq >= size || r + dr < 0 || r + dr >= size) continue;
                const int next = (r + dr) * size + q + dq;
                const auto& neighbor = tiles[next];
                if (neighbor.owner != tile.owner || neighbor.water) continue;
                const double inbound = neighbor.supply * (.46 + relay * .38) * (.62 + passability(tile) * .28);
                if (inbound > tile.supply + .001) updates[index] = std::max(updates[index], std::min(1., inbound));
                if (tile.supply <= .35) continue;
                const double candidate = std::min(1., tile.supply * (.42 + relay)) * (.58 + passability(neighbor) * .30);
                if (candidate > neighbor.supply + .001) updates[next] = std::max(updates[next], std::min(1., candidate));
            }
        }
        for (int i:owned[country])
            tiles[i].supply = std::max(tiles[i].supply, updates[i]);
    }
    };
    std::vector<std::size_t> activeCountries;
    for(std::size_t country=0;country<capitals.size();++country) if(!changed || (*changed)[country]) activeCountries.push_back(country);
    if(workers) workers->forEach(activeCountries.size(),[&](std::size_t i){countryWork(activeCountries[i]);});
    else for(auto country:activeCountries) countryWork(country);
}

}
