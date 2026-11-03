#pragma once

#include "air_data.hpp"
#include "starting_infrastructure.hpp"

namespace hoi5 {

struct Airbase {
    int owner, tile, runway, aircraftCapacity, helicopterCapacity;
    double fuelStorage, munitionStorage, repairCapacity;
    bool hardened;
};
struct AirWing { int owner, base, type, count; int target = -1; double cooldown{}; bool strategic{}; };
struct AirDefense { int owner, tile, type, ammo; };

struct AirLayer {
    std::vector<Airbase> bases;
    std::vector<AirWing> wings;
    std::vector<AirDefense> defense;
    std::vector<std::array<int,std::size(aircraftTypes)>> reserves;

    template<class Tile>
    void initialize(std::vector<Tile>& tiles,int size,const std::vector<int>& capitals,
                    const std::vector<StartingProfile>& profiles) {
        reserves.resize(capitals.size());
        for (int country = 0; country < int(capitals.size()); ++country) {
            const int capital = capitals[country];
            int best = -1;
            auto bestRank = std::tuple{true,0.,0,0};
            std::vector<std::pair<int,double>> important;
            for (int index = 0; index < int(tiles.size()); ++index) {
                const auto& tile = tiles[index];
                if (tile.owner != country || tile.water) continue;
                const int dq = index%size-capital%size, dr = index/size-capital/size;
                const int distance = std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
                const auto& b = tile.buildings;
                const double score = .30/tile.movementCost + b[city].area*.34 + b[industry].area*.22
                    + b[fuelStorage].area*.12 + b[warehouse].area*.08 - distance*.025;
                const auto rank = std::tuple{distance > 4,-score,index/size,index%size};
                if (best < 0 || rank < bestRank) {
                    best = index;
                    bestRank = rank;
                }
            }
            if (best >= 0) {
                constexpr double coverage = .20;
                tiles[best].buildings[airbase].area = coverage;
                bases.push_back({country,best,1,int(28+coverage*90),int(8+coverage*38),
                    8000+coverage*38000,4000+coverage*18000,.8+coverage*1.4,false});
                const double scale = std::clamp(profiles[country].scale,.55,1.20);
                for (std::size_t i = 0; i < std::size(aircraftTypes); ++i) {
                    if (!aircraftTypes[i].starting) continue;
                    const int count = std::max(1,int(std::nearbyint(aircraftTypes[i].starting*scale)));
                    reserves[country][i] = count+std::max(1,int(std::nearbyint(count*.25)));
                }
            }
            const auto deploy = [&](int tile,std::string_view name) {
                const auto type = std::find_if(std::begin(defenseClasses),std::end(defenseClasses),
                    [&](const auto& entry) { return entry.key == name; });
                if (tile >= 0 && !tiles[tile].water && type != std::end(defenseClasses))
                    defense.push_back({country,tile,int(type-std::begin(defenseClasses)),type->ammo});
            };
            deploy(capital,"medium_range_sam");
            deploy(capital,"radar_unit");
            deploy(best,"short_range_aa");
            for (int index = 0; index < int(tiles.size()); ++index) {
                const auto& tile = tiles[index];
                if (tile.owner != country || tile.water) continue;
                const auto& b = tile.buildings;
                const int q = index%size, r = index/size, shift = r%2;
                int border = 0;
                for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
                    {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
                }}) {
                    if (q+dq < 0 || q+dq >= size || r+dr < 0 || r+dr >= size) continue;
                    const auto& neighbor = tiles[(r+dr)*size+q+dq];
                    border += neighbor.owner >= 0 && neighbor.owner != country && !neighbor.water;
                }
                const double score = b[city].area*.50 + b[industry].area*.28 + b[supplyDepot].area*.22
                    + b[airbase].area*.30 + border*.18 + (index == capital ? .45 : 0) + (index == best ? .25 : 0);
                if (score > 0) important.emplace_back(index,score);
            }
            std::sort(important.begin(),important.end(),[](const auto& a,const auto& b) {
                return std::tuple{-a.second,a.first} < std::tuple{-b.second,b.first};
            });
            for (std::size_t i = 0; i < std::min(std::size_t(3),important.size()); ++i) {
                const int tile = important[i].first;
                if (tile != capital && tile != best) deploy(tile,i == 0 ? "short_range_aa" : "manpads_team");
            }
            if (profiles[country].scale >= 1.85) deploy(capital,"long_range_sam");
        }
    }

    template<class Tile>
    int freeCapacity(const std::vector<Tile>& tiles,int country,int tile,int type,int excluded = -1) const {
        if (tiles[tile].owner != country || tiles[tile].water || tiles[tile].buildings[airbase].health <= .15) return 0;
        const auto base = std::find_if(bases.begin(),bases.end(),[&](const auto& b) {
            return b.tile == tile && b.owner == country;
        });
        if (base == bases.end()) return 0;
        const auto& aircraft = aircraftTypes[type];
        if (!aircraft.helicopter && base->runway < aircraft.runway) return 0;
        int free = aircraft.helicopter ? base->helicopterCapacity : base->aircraftCapacity;
        for (int i = 0; i < int(wings.size()); ++i)
            if (i != excluded && wings[i].base == tile && aircraftTypes[wings[i].type].helicopter == aircraft.helicopter)
                free -= wings[i].count;
        return std::max(0,free);
    }

    template<class Tile>
    int createWing(const std::vector<Tile>& tiles,int country,int type,int requested) {
        if (country < 0 || country >= int(reserves.size()) || type < 0 || type >= int(std::size(aircraftTypes))) return -1;
        auto& reserve = reserves[country][type];
        for (const auto& base : bases) {
            if (base.owner != country) continue;
            const int count = std::min({std::max(1,requested),reserve,freeCapacity(tiles,country,base.tile,type)});
            if (count <= 0) continue;
            wings.push_back({country,base.tile,type,count});
            reserve -= count;
            return int(wings.size())-1;
        }
        return -1;
    }
};

}
