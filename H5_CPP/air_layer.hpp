#pragma once

#include "air_data.hpp"
#include <string>
#include <map>
#include <deque>
#include "starting_infrastructure.hpp"

namespace hoi5 {

struct Airbase {
    int owner, tile, runway, aircraftCapacity, helicopterCapacity;
    double fuelStorage, munitionStorage, repairCapacity;
    bool hardened;
};
struct AirWing {
    int owner, base, type, count;
    int target = -1;
    double cooldown{};
    std::array<bool,2> enabledMissions{};
    std::vector<int> operationArea;
    std::array<int,2> lastMissionTarget{-1,-1};
    std::array<std::map<int,double>,2> missionTargetCooldowns;
    std::array<double,2> missionCooldowns{};
    double sortieIntensity = .5;
    AirRisk risk = AirRisk::normal;
    bool airSuperiority = false;
    bool intercept = false, patrol = false;
    int interceptorAmmo = -1;
    int damaged = 0;
    double defensiveHours = 0, abortedHours = 0;
    std::vector<std::pair<int,int>> composition;
    std::vector<std::string_view> targetPriorities;

    int readyCount() const { return std::max(0,count-damaged); }
    int typeCount(int aircraft) const {
        if (composition.empty()) return aircraft == type ? count : 0;
        const auto item = std::ranges::find(composition,aircraft,&std::pair<int,int>::first);
        return item == composition.end() ? 0 : item->second;
    }
    int roleCount(bool helicopter) const {
        int total = 0;
        for (int i = 0; i < int(std::size(aircraftTypes)); ++i)
            if (aircraftTypes[i].helicopter == helicopter) total += typeCount(i);
        return total;
    }
    int interceptorCapacity() const {
        constexpr std::array perAircraft{4,3,1,1,0,0};
        int total = 0;
        for (int i = 0; i < int(perAircraft.size()); ++i) total += typeCount(i)*perAircraft[i];
        return total;
    }

    void changeComposition(int aircraft,int delta) {
        if (composition.empty() && count > 0) composition.emplace_back(type,count);
        auto item = std::ranges::find(composition,aircraft,&std::pair<int,int>::first);
        if (item == composition.end()) composition.emplace_back(aircraft,delta);
        else if ((item->second += delta) <= 0) composition.erase(item);
        count += delta;
        if (!composition.empty()) type = std::ranges::max_element(composition,{},&std::pair<int,int>::second)->first;
        for (bool strategic : {false,true})
            if (!missionAllowed(strategic)) enabledMissions[strategic] = false;
        if (missionType(2) < 0) intercept = airSuperiority = patrol = false;
    }

    bool missionAllowed(bool strategic) const {
        return missionType(strategic ? 1 : 0) >= 0;
    }

    int missionType(int mission) const {
        constexpr int priority[][6]{{0,3,2,5,5,0},{0,4,5,2,0,6},{5,4,0,0,0,0}};
        int best = -1;
        std::tuple<int,int,std::string_view> rank{};
        for (int i = 0; i < int(std::size(aircraftTypes)); ++i) {
            const int available = typeCount(i);
            if (!available || !priority[mission][i]) continue;
            const auto candidate = std::tuple{priority[mission][i],available,aircraftTypes[i].key};
            if (candidate > rank) { rank = candidate; best = i; }
        }
        return best;
    }

    int readyForType(int aircraft) const {
        return aircraft < 0 || count <= 0 ? 0 : int(std::nearbyint(typeCount(aircraft)*double(readyCount())/count));
    }
};
struct AirDefense {
    int owner, tile, type, ammo;
    double reloadCredit{};
    int ammoCapacity{}, lastAmmoReceived{};
    std::string resupplyStatus;
    double health = 1;
    std::deque<int> route;
    double progress{}, visualProgress{};
    double readinessLimit = 1.;
    double readiness() const { return std::min(readinessLimit,defenseClasses[type].readiness); }
    bool operational() const { return route.empty() && health > 0 && readiness() > 0; }
};

struct AirLayer {
    std::vector<Airbase> bases;
    std::vector<AirWing> wings;
    std::vector<AirDefense> defense;
    std::vector<std::array<int,std::size(aircraftTypes)>> reserves;
    struct DefenseReplacement { int type,remaining; };
    std::map<int,DefenseReplacement> defenseReplacements;

    template<class Stockpile>
    std::string_view enqueueDefense(int owner,int type,double& budget,Stockpile& stock) {
        if (defenseReplacements.contains(owner)) return "ПВО уже производится";
        constexpr std::array prices{500000.,1200000.,2500000.,5000000.,1000000.};
        if (type < 0 || type >= int(prices.size()) || budget < prices[type])
            return "Недостаточно средств или неизвестный тип ПВО";
        Stockpile materials{{"steel",80},{"construction_goods",200},{"electronics",40},{"machinery",15},{"vehicles",2}};
        const auto& unit = defenseClasses[type];
        if (unit.ammo > 0) materials[unit.key == "short_range_aa" ? "light_aa_ammo" : "anti_air_ammo"] = unit.ammo;
        if (unit.key == "short_range_aa") materials["old_light_aa_artillery"] = 2;
        for (const auto& [key,amount] : materials) {
            const auto available = stock.find(key);
            if (available == stock.end() || available->second < amount)
                return "Не хватает материалов и оснащения для ПВО";
        }
        defenseReplacements.emplace(owner,DefenseReplacement{type,48});
        budget -= prices[type];
        for (const auto& [key,amount] : materials) stock.at(key) -= amount;
        return "Оплачено производство ПВО: 48 часов";
    }

    template<class Tile,class InBattle,class Completed>
    void advanceDefenseReplacements(const std::vector<Tile>& tiles,const std::vector<int>& capitals,int hours,
                                    InBattle inBattle,Completed completed) {
        for (auto it = defenseReplacements.begin(); it != defenseReplacements.end();) {
            const int owner = it->first;
            auto& project = it->second;
            project.remaining = std::max(0,project.remaining-hours);
            if (project.remaining > 0) {
                ++it;
                continue;
            }
            int site = -1;
            double best = 0;
            for (int i = 0; i < int(tiles.size()); ++i) {
                const auto& tile = tiles[i];
                if (tile.owner != owner || tile.water || tile.supply < .25 || inBattle(i)) continue;
                const double score = tile.supply+(owner < int(capitals.size()) && capitals[owner] == i);
                if (score > best) {
                    best = score;
                    site = i;
                }
            }
            if (site < 0) {
                ++it;
                continue;
            }
            defense.push_back({owner,site,project.type,defenseClasses[project.type].ammo});
            completed(site,project.type);
            it = defenseReplacements.erase(it);
        }
    }

    double radarSupport(int owner,int tile,int size) const {
        int count = 0;
        for (const auto& radar : defense) {
            const auto& type = defenseClasses[radar.type];
            if (radar.owner != owner || !radar.operational() || type.key != "radar_unit" || !type.radarActive) continue;
            const int dq = radar.tile%size-tile%size, dr = radar.tile/size-tile/size;
            if (std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)}) <= type.radarRange) ++count;
        }
        return std::min(.18,.06*count);
    }
    template<class Tile,class Stockpile>
    void replenishDefenseAmmo(const std::vector<Tile>& tiles,std::vector<Stockpile>& stockpiles,int hours) {
        for (auto& unit : defense) {
            const auto& type = defenseClasses[unit.type];
            unit.lastAmmoReceived = 0;
            const int capacity = unit.ammoCapacity = std::max(unit.ammoCapacity,type.ammo);
            if (!capacity || unit.ammo >= capacity) {
                unit.reloadCredit = 0;
                unit.resupplyStatus = capacity ? "БК полный" : "Боеприпасы не требуются";
                continue;
            }
            const auto& tile = tiles[unit.tile];
            if (tile.owner != unit.owner || !unit.operational() ||
                unit.owner < 0 || unit.owner >= int(stockpiles.size())) {
                unit.resupplyStatus = "Пополнение недоступно: движение/не своя позиция/небоеспособность";
                continue;
            }
            if (tile.supply < .15) {
                unit.resupplyStatus = "Недостаточное снабжение клетки";
                continue;
            }
            const auto key = type.key == "short_range_aa" ? "light_aa_ammo" : "anti_air_ammo";
            auto& stock = stockpiles[unit.owner][key];
            unit.reloadCredit = std::min(double(capacity),unit.reloadCredit+capacity*hours/6.*tile.supply);
            const int available = std::max(0,int(stock));
            const int count = std::min({capacity-unit.ammo,int(unit.reloadCredit+1e-9),available});
            stock -= count;
            unit.ammo += count;
            unit.reloadCredit = std::max(0.,unit.reloadCredit-count);
            unit.lastAmmoReceived = count;
            unit.resupplyStatus = available ? "Пополнение: +"+std::to_string(count)+" ("+key+")"
                : std::string("Нет ")+key+" на складах";
        }
    }
    void transferTile(int tile,int oldOwner,int newOwner) {
        if (oldOwner == newOwner) return;
        const auto base = std::find_if(bases.begin(),bases.end(),[&](const auto& item) { return item.tile == tile; });
        if (base != bases.end()) {
            base->owner = newOwner;
            for (auto& wing : wings) {
                if (wing.base != tile || wing.owner != oldOwner) continue;
                // Keep indices stable for the UI selection.
                wing.count = 0;
                wing.composition.clear();
                wing.operationArea.clear();
                wing.target = -1;
            }
        }
        std::erase_if(defense,[&](const auto& unit) { return unit.tile == tile && unit.owner != newOwner; });
    }
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
    int baseCapacity(const std::vector<Tile>& tiles,int country,int tile,int type) const {
        if (tiles[tile].owner != country || tiles[tile].water) return 0;
        const auto base = std::find_if(bases.begin(),bases.end(),[&](const auto& b) {
            return b.tile == tile && b.owner == country;
        });
        const auto& aircraft = aircraftTypes[type];
        if (base != bases.end() && tiles[tile].buildings[airbase].health > .15) {
            if (!aircraft.helicopter && base->runway < aircraft.runway) return 0;
            return aircraft.helicopter ? base->helicopterCapacity : base->aircraftCapacity;
        }
        const auto& pad = tiles[tile].buildings[fieldHelipad];
        if (!aircraft.helicopter || pad.area <= 0 || pad.health <= .15) return 0;
        return std::max(1,int(std::nearbyint(pad.area*80)));
    }

    template<class Tile>
    int freeCapacity(const std::vector<Tile>& tiles,int country,int tile,int type,int excluded = -1) const {
        int free = baseCapacity(tiles,country,tile,type);
        for (int i = 0; i < int(wings.size()); ++i)
            if (i != excluded && wings[i].base == tile)
                free -= wings[i].roleCount(aircraftTypes[type].helicopter);
        return std::max(0,free);
    }

    template<class Tile>
    int transferAircraft(const std::vector<Tile>& tiles,int index,int type,int delta) {
        if (index < 0 || index >= int(wings.size()) || type < 0 || type >= int(std::size(aircraftTypes))) return 0;
        auto& wing = wings[index];
        if (wing.count <= 0 || wing.owner < 0 || wing.owner >= int(reserves.size())) return 0;
        auto& reserve = reserves[wing.owner][type];
        const int changed = delta >= 0 ? std::min({delta,reserve,freeCapacity(tiles,wing.owner,wing.base,type)}) :
            -std::min({-delta,wing.typeCount(type),wing.count-1});
        if (!changed) return 0;
        const int ready = wing.readyCount();
        const int oldAmmoCapacity = wing.interceptorCapacity();
        wing.changeComposition(type,changed);
        wing.damaged = wing.count-std::clamp(ready+changed,0,wing.count);
        reserve -= changed;
        if (wing.interceptorAmmo >= 0) {
            const int capacity = wing.interceptorCapacity();
            wing.interceptorAmmo = std::min(capacity,wing.interceptorAmmo+std::max(0,capacity-oldAmmoCapacity));
        }
        return changed;
    }

    template<class Tile>
    bool rebaseWing(const std::vector<Tile>& tiles,int index,int target,std::string* message = nullptr) {
        const auto fail = [&](std::string reason) {
            if (message) *message = std::move(reason);
            return false;
        };
        if (index < 0 || index >= int(wings.size()) || target < 0 || target >= int(tiles.size()))
            return fail("Нет цели перебазирования");
        auto& wing = wings[index];
        if (tiles[target].owner != wing.owner) return fail("Нужна своя клетка");
        if (tiles[target].water) return fail("Нельзя базироваться на воде");
        if (wing.count <= 0) return fail("Крыло пустое");
        int fixed = -1;
        for (int type = 0; type < int(std::size(aircraftTypes)); ++type) {
            if (aircraftTypes[type].helicopter || !wing.typeCount(type)) continue;
            if (baseCapacity(tiles,wing.owner,target,type) <= 0)
                return fail("База не принимает "+std::string(aircraftNames[type]));
            fixed = type;
        }
        for (int type : {fixed,4}) {
            if (type < 0) continue;
            const bool helicopter = aircraftTypes[type].helicopter;
            const int count = wing.roleCount(helicopter);
            const int free = freeCapacity(tiles,wing.owner,target,type,index);
            if (free < count)
                return fail(std::string(helicopter ? "Не хватает вертолетных мест: " : "Не хватает самолетных мест: ")+
                    std::to_string(free)+"/"+std::to_string(count));
        }
        wing.base = target;
        wing.target = -1;
        if (std::ranges::max(wing.missionCooldowns) < 1.) wing.cooldown = std::max(1.,wing.cooldown);
        if (message) message->clear();
        return true;
    }
    template<class Tile>
    int creationBase(const std::vector<Tile>& tiles,int country,int type,std::span<const int> selectedTiles,
                     int wingBase) const {
        const auto available = [&](int tile) {
            return tile >= 0 && tile < int(tiles.size()) && freeCapacity(tiles,country,tile,type) > 0;
        };
        for (int tile : selectedTiles)
            if (available(tile)) return tile;
        if (available(wingBase)) return wingBase;
        for (const auto& base : bases)
            if (base.owner == country && available(base.tile)) return base.tile;
        return -1;
    }

    template<class Tile>
    int createWing(const std::vector<Tile>& tiles,int country,int type,int requested,std::span<const int> selectedTiles = {},int wingBase = -1) {
        if (country < 0 || country >= int(reserves.size()) || type < 0 || type >= int(std::size(aircraftTypes))) return -1;
        auto& reserve = reserves[country][type];
        if (reserve <= 0) return -1;
        const int tile = creationBase(tiles,country,type,selectedTiles,wingBase);
        if (tile < 0) return -1;
        const int count = std::min({std::max(1,requested),reserve,freeCapacity(tiles,country,tile,type)});
        wings.push_back({country,tile,type,count});
        reserve -= count;
        return int(wings.size())-1;
    }
};

}
