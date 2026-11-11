#pragma once

#include "combat.hpp"
#include "production.hpp"
#include <algorithm>
#include <deque>
#include <vector>

namespace hoi5 {

enum BotMilitaryMetric { personnel, attack, defense, breakthrough, armor, piercing, mobility, readiness, militaryMetrics };
using BotMilitary = std::array<double,militaryMetrics>;

inline BotMilitary botDivisionVector(const CombatStats& combat,int manpower,double maxStrength,
                                     double organization,double maxOrganization,double supply,double speed) {
    const double strength = std::clamp(combat.strength/std::max(1.,maxStrength),0.,1.);
    const double org = std::clamp(organization/std::max(1.,maxOrganization),0.,1.);
    const double factor = strength*(.25+.75*org)*(.35+.65*std::clamp(supply,0.,1.));
    return {double(std::max(0,manpower)),(combat.softAttack+combat.frontAttack+combat.topAttack)*factor,
        combat.defense*factor,combat.breakthrough*factor,std::max(combat.frontArmor,combat.topArmor)*strength,
        std::max(combat.frontPiercing,combat.topPiercing)*factor,speed*org,factor};
}

struct BotRegion {
    int base, owner, anchor;
    std::vector<int> tiles;
    std::vector<int> borders;
    double population{}, supply{}, importance{};
    std::array<double,buildingCount> buildings{};
    Stockpile output;
    BotMilitary military{};
    double threat{}, desiredDefense{};
};

class BotRegionMap {
    static constexpr int maxTiles = 48;
    std::vector<int> tileOrder;
    std::vector<int> baseRegion;
    std::vector<std::vector<int>> neighbors;

public:
    template<class Water,class VisitNeighbors>
    void build(int width,Water water,VisitNeighbors visitNeighbors) {
        const int count = width*width;
        tileOrder.clear();
        baseRegion.assign(count,-1);
        neighbors.assign(count,{});
        for (int q = 0; q < width; ++q) for (int r = 0; r < width; ++r) {
            const int index = r*width+q;
            if (!water(index)) tileOrder.push_back(index);
            visitNeighbors(index,[&](int neighbor) { neighbors[index].push_back(neighbor); });
        }
        std::vector<int> queued(count,-1);
        int region = 0;
        for (const int seed : tileOrder) {
            if (baseRegion[seed] >= 0) continue;
            std::deque<int> queue{seed};
            queued[seed] = region;
            for (int members = 0; !queue.empty() && members < maxTiles; ++members) {
                const int tile = queue.front();
                queue.pop_front();
                baseRegion[tile] = region;
                for (const int neighbor : neighbors[tile]) {
                    if (baseRegion[neighbor] >= 0 || queued[neighbor] == region || water(neighbor)) continue;
                    queued[neighbor] = region;
                    queue.push_back(neighbor);
                }
            }
            ++region;
        }
    }

    const std::vector<int>& adjacent(int tile) const { return neighbors[tile]; }
    bool hasRegion(int tile) const { return baseRegion[tile] >= 0; }

    template<class Tile,class Water>
    std::vector<BotRegion> profiles(const std::vector<Tile>& tiles,int owner,int capital,Water water) const {
        std::vector<bool> remaining(tiles.size());
        for (const int index : tileOrder) remaining[index] = tiles[index].owner == owner;
        std::vector<BotRegion> profiles;
        for (const int seed : tileOrder) {
            if (!remaining[seed]) continue;
            auto& profile = profiles.emplace_back(BotRegion{baseRegion[seed],owner,seed});
            std::deque<int> queue{seed};
            remaining[seed] = false;
            while (!queue.empty()) {
                const int index = queue.front();
                queue.pop_front();
                const auto& tile = tiles[index];
                profile.tiles.push_back(index);
                profile.population += tile.population;
                profile.supply += tile.supply;
                for (int building = 0; building < buildingCount; ++building) {
                    const auto& coverage = tile.buildings[building];
                    profile.buildings[building] += coverage.area*coverage.health;
                }
                Production production;
                accumulateTileProduction(production,tile,{});
                for (const auto& stage : production)
                    for (const auto& [key,amount] : stage.outputs) profile.output[key] += amount;
                bool border = false;
                for (const int neighbor : neighbors[index]) {
                    border |= tiles[neighbor].owner != owner && !water(neighbor);
                    if (!remaining[neighbor] || baseRegion[neighbor] != profile.base) continue;
                    remaining[neighbor] = false;
                    queue.push_back(neighbor);
                }
                if (border) profile.borders.push_back(index);
            }
            profile.supply /= profile.tiles.size();
            const auto& buildings = profile.buildings;
            profile.importance = profile.population/100000. + 5*buildings[industry] + 6*buildings[refinery] +
                4*buildings[oilGasRig] + 3*buildings[supplyDepot];
            if (std::ranges::find(profile.tiles,capital) != profile.tiles.end()) profile.importance += 30.;
        }
        return profiles;
    }
};

}
