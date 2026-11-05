#pragma once

#include "debug_profiler.hpp"

#include "construction_data.hpp"

#include <optional>

namespace hoi5 {

enum class ConstructionStatus { queued, paused, waitingMoney, waitingResources, waitingPower, building, repairing };

inline std::string_view constructionStatusLabel(ConstructionStatus status) {
    switch (status) {
        case ConstructionStatus::paused: return "Пауза";
        case ConstructionStatus::waitingMoney: return "Не хватает денег";
        case ConstructionStatus::waitingResources: return "Не хватает ресурсов";
        case ConstructionStatus::waitingPower: return "Нет строительной мощности";
        case ConstructionStatus::building: return "Строится";
        case ConstructionStatus::repairing: return "Ремонт";
        case ConstructionStatus::queued: return "Ждет очереди";
    }
    return {};
}

struct ConstructionProject {
    int tile;
    int spec;
    double from, target, work, money;
    Stockpile resources;
    double progress{};
    bool paid{}, paused{};
    bool repair{};
    Stockpile resourcesSpent;
    Stockpile missingResources;
    double missingMoney{};
    ConstructionStatus status = ConstructionStatus::queued;
};

struct Construction {
    std::vector<std::vector<ConstructionProject>> queues;

    template<class Tile>
    static double buildPower(const std::vector<Tile>& tiles,int owner,const StartingProfile& profile) {
        double industryCoverage = 0, settlementCoverage = 0;
        for (const auto& tile : tiles) {
            if (tile.owner != owner) continue;
            const auto effective = [&](Building type) {
                const auto& b = tile.buildings[type];
                return b.area*b.health;
            };
            industryCoverage += effective(industry);
            settlementCoverage += effective(city)+effective(village)*.5;
        }
        return std::max(0.,100*(industryCoverage*profile.industryEfficiency+
            settlementCoverage*profile.cityBuildMultiplier)+profile.buildTechBonus);
    }

    static bool applyRepairProgress(BuildingCoverage& building,const ConstructionProject& project,
                                    double oldProgress,double newProgress) {
        if (!project.repair || building.area <= 0) return false;
        const double from = std::clamp(project.from,0.,1.);
        const double target = std::clamp(project.target,from,1.);
        const double gain = std::max(0.,newProgress-oldProgress)*(target-from);
        const double next = std::clamp(building.health+gain,0.,1.);
        if (gain <= 0 || std::abs(next-building.health) < .0005) return false;
        building.health = next >= .999 ? 1. : next;
        return true;
    }

    static constexpr double speedMultiplier(bool inBattle) { return inBattle ? .22 : 1.; }

    static double progressDelta(const ConstructionProject& project,double power,double months) {
        const double progress = std::clamp(project.progress,0.,1.);
        return std::min(1-progress,std::max(0.,power)*std::max(0.,months)/std::max(1.,project.work));
    }

    static std::optional<double> remainingMonths(const ConstructionProject& project,double power) {
        if (power <= 0) return std::nullopt;
        return std::max(0.,project.work)*(1-std::clamp(project.progress,0.,1.))/power;
    }

    static Stockpile projectNeeds(const ConstructionProject& project,double delta) {
        const double progress = std::clamp(project.progress,0.,1.);
        const double next = std::min(1.,progress+std::max(0.,delta));
        Stockpile needs;
        for (const auto& [key,total] : project.resources) {
            const double amount = total*next-value(project.resourcesSpent,key);
            if (total > 0 && amount > 0) needs[key] = amount;
        }
        return needs;
    }

    template<class Tile,class InBattle>
    Stockpile monthlyNeeds(const std::vector<Tile>& tiles,int owner,const StartingProfile& profile,const Stockpile& stock,
                           InBattle inBattle) const {
        const auto& queue = queues[owner];
        const int active = std::min(3,int(std::ranges::count_if(queue,[](const auto& p) { return !p.paused; })));
        Stockpile result;
        if (!active) return result;
        const double power = buildPower(tiles,owner,profile)/active;
        int used = 0;
        for (const auto& project : queue) {
            if (project.paused) continue;
            if (++used > active) break;
            if ((!project.paid && profile.budget < project.money) || power <= 0 || project.progress >= .999) continue;
            const double speed = power*speedMultiplier(inBattle(project.tile));
            const auto required = projectNeeds(project,progressDelta(project,speed,1./30.));
            if (std::ranges::any_of(required,[&](const auto& entry) {
                return value(stock,entry.first)+.001 < entry.second;
            })) continue;
            for (const auto& [key,amount] : projectNeeds(project,progressDelta(project,speed,1.))) result[key] += amount;
        }
        return result;
    }

    struct Group { int first, end; };

    static std::vector<Group> groups(const std::vector<ConstructionProject>& queue) {
        std::vector<Group> result;
        for (int i = 0; i < int(queue.size()); ++i) {
            const auto key = [](const auto& project) { return std::tuple{project.repair,project.tile,project.spec}; };
            if (i > 0 && key(queue[i-1]) == key(queue[i])) result.back().end = i+1;
            else result.push_back({i,i+1});
        }
        return result;
    }

    static bool canMoveGroup(const std::vector<ConstructionProject>& queue,
                             const std::vector<Group>& groups,int index,int direction) {
        const int neighbor = index+direction;
        if (index < 0 || index >= int(groups.size()) || neighbor < 0 || neighbor >= int(groups.size()) ||
            std::abs(direction) != 1) return false;
        const int first = groups[std::min(index,neighbor)].first;
        const int end = groups[std::max(index,neighbor)].end;
        return std::none_of(queue.begin()+first,queue.begin()+end,[](const auto& project) {
            return project.paid || project.progress > 0;
        });
    }

    static bool moveGroup(std::vector<ConstructionProject>& queue,const std::vector<Group>& groups,
                          int index,int direction) {
        if (!canMoveGroup(queue,groups,index,direction)) return false;
        const int first = std::min(index,index+direction);
        std::rotate(queue.begin()+groups[first].first,queue.begin()+groups[first].end,
            queue.begin()+groups[first+1].end);
        return true;
    }

    bool cancel(int owner,int tile,int spec) {
        auto& queue = queues[owner];
        for (auto it = queue.rbegin(); it != queue.rend(); ++it) {
            if (it->tile != tile || it->spec != spec) continue;
            if (it->paid || it->progress > 0) return false;
            queue.erase(std::prev(it.base()));
            return true;
        }
        return false;
    }

    template<class Tile>
    void enqueueRepair(const Tile& tile,int index,int spec) {
        if (tile.owner < 0 || tile.owner >= int(queues.size())) return;
        const auto& data = constructionSpecs[spec];
        const auto& building = tile.buildings[data.building];
        const double damage = 1-building.health;
        if (building.area <= 0 || damage <= .001) return;
        auto& queue = queues[tile.owner];
        if (std::ranges::any_of(queue,[&](const auto& p) { return p.repair && p.tile == index && p.spec == spec; }))
            return;
        const double scale = building.area*damage*std::pow(1.10,std::floor(building.area/.05));
        auto resources = data.resources;
        for (auto& [key,amount] : resources) amount *= scale*.35;
        queue.push_back({index,spec,building.health,1.,std::max(1.,data.work*scale*.45),
            data.money*scale*.10,std::move(resources),0.,false,false,true});
    }

    template<class Tile>
    bool damageBuilding(Tile& tile,int index,Building building,double damage) {
        auto& health = tile.buildings[building].health;
        if (damage <= 0 || health <= 0) return false;
        health = std::max(0.,health-damage);
        const auto spec = std::ranges::find(constructionSpecs,building,&ConstructionSpec::building);
        if (spec != std::end(constructionSpecs)) enqueueRepair(tile,index,int(spec-std::begin(constructionSpecs)));
        return true;
    }

    template<class Tile>
    static std::string_view placementBlock(const std::vector<Tile>& tiles,int size,int owner,int index,int spec,double coverage) {
        if (owner < 0) return "Нет страны";
        if (index < 0 || index >= int(tiles.size()) || tiles[index].owner != owner) return "Чужая клетка";
        if (spec < 0 || spec >= int(std::size(constructionSpecs))) return "Неизвестное строение";
        const auto& tile = tiles[index];
        const bool water = tile.water || tile.natural.water > .55;
        if (coverage >= 1) return "Уже максимум";
        const auto& data = constructionSpecs[spec];
        if (data.building == port) {
            bool coastal = false;
            ownedNeighbors(tiles,size,index,&coastal);
            if (water || !coastal) return "Порт только рядом с водой";
        }
        if (water) return "Нужна суша";
        constexpr ResourceWeight solid[] = {{"coal",1},{"peat",.55},{"iron_ore",1},{"copper_ore",.82},
            {"bauxite",.64},{"sulfur",.42},{"phosphorite",.40},{"apatite",.36}};
        constexpr ResourceWeight oil[] = {{"oil",1},{"natural_gas",.95}};
        if (data.building == mine && resourceScore(tile.deposits,solid) <= 0) return "Нужны твердые залежи";
        if (data.building == oilGasRig && resourceScore(tile.deposits,oil) <= 0) return "Нужна нефть или газ";
        return {};
    }

    template<class Tile>
    std::string_view enqueue(const std::vector<Tile>& tiles,int size,int owner,int index,int spec,double buildEfficiency = 1.) {
        if (owner < 0 || owner >= int(queues.size())) return "Нет страны";
        if (index < 0 || index >= int(tiles.size()) || tiles[index].owner != owner) return "Чужая клетка";
        if (spec < 0 || spec >= int(std::size(constructionSpecs))) return "Неизвестное строение";
        const auto& data = constructionSpecs[spec];
        double current = tiles[index].buildings[data.building].area;
        auto& queue = queues[owner];
        for (const auto& project : queue)
            if (!project.repair && project.tile == index && project.spec == spec) current = std::max(current,project.target);
        if (const auto reason = placementBlock(tiles,size,owner,index,spec,current); !reason.empty()) return reason;
        current = std::clamp(current,0.,1.);
        const double target = std::min(1.,(std::floor(current/.05+1e-9)+1)*.05);
        const double factor = (target-current)*std::pow(1.10,std::floor(current/.05));
        auto resources = data.resources;
        const double costFactor = factor*std::max(.05,buildEfficiency);
        for (auto& [key,amount] : resources) amount *= costFactor;
        queue.push_back({index,spec,current,target,data.work*factor,data.money*costFactor,std::move(resources)});
        return {};
    }

    template<class Tile,class Complete,class InBattle>
    bool advance(std::vector<Tile>& tiles,std::vector<StartingProfile>& countries,
                 std::vector<Stockpile>& stocks,int hours,Complete complete,InBattle inBattle,DebugProfiler* debug = nullptr) {
        bool changed = false;
        {
            DebugMeasure timing(debug,"construction_auto_repairs");
            for (int index = 0; index < int(tiles.size()); ++index)
                for (int spec = 0; spec < int(std::size(constructionSpecs)); ++spec)
                    if (tiles[index].buildings[constructionSpecs[spec].building].health < .999)
                        enqueueRepair(tiles[index],index,spec);
        }
        DebugMeasure projects(debug,"construction_projects");
        for (std::size_t country = 0; country < queues.size(); ++country) {
            auto& queue = queues[country];
            std::erase_if(queue,[&](const auto& project) {
                const auto& tile = tiles[project.tile];
                return tile.owner != int(country) ||
                    (project.repair && 1-tile.buildings[constructionSpecs[project.spec].building].health <= .001);
            });
            if (queue.empty() || hours <= 0) continue;
            const double power = buildPower(tiles,int(country),countries[country]);
            const int active = std::min(3,int(std::count_if(queue.begin(),queue.end(),[](const auto& p) { return !p.paused; })));
            int used = 0;
            for (auto& project : queue) {
                project.missingResources.clear();
                project.missingMoney = 0;
                project.status = project.paused ? ConstructionStatus::paused : ConstructionStatus::queued;
                if (project.paused || ++used > active) continue;
                auto& tile = tiles[project.tile];
                const auto building = constructionSpecs[project.spec].building;
                auto& state = tile.buildings[building];
                if (!project.paid) {
                    if (countries[country].budget < project.money) {
                        project.status = ConstructionStatus::waitingMoney;
                        project.missingMoney = project.money-countries[country].budget;
                        continue;
                    }
                    countries[country].budget -= project.money;
                    project.paid = true;
                }
                if (power <= 0) {
                    project.status = ConstructionStatus::waitingPower;
                    continue;
                }
                const double speed = power/active*speedMultiplier(inBattle(project.tile));
                const double delta = progressDelta(project,speed,hours/720.);
                if (delta <= 0) continue;
                auto& stock = stocks[country];
                const double next = std::min(1.,project.progress+delta);
                const auto needs = projectNeeds(project,delta);
                {
                    DebugMeasure timing(debug,"construction_status_eval");
                    for (const auto& [resource,amount] : needs) {
                        const double available = value(stock,resource);
                        if (available+.001 < amount) project.missingResources[resource] = amount-available;
                    }
                }
                if (!project.missingResources.empty()) {
                    project.status = ConstructionStatus::waitingResources;
                    continue;
                }
                {
                    DebugMeasure timing(debug,"construction_consume_resources");
                    for (const auto& [resource,amount] : needs) {
                        const double consumed = std::clamp(stock[resource],0.,amount);
                        stock[resource] -= consumed;
                        project.resourcesSpent[resource] += consumed;
                    }
                }
                project.status = project.repair ? ConstructionStatus::repairing : ConstructionStatus::building;
                const double previousProgress = project.progress;
                project.progress = next;
                changed |= applyRepairProgress(state,project,previousProgress,next);
                if (project.progress >= .999) {
                    if (project.repair) state.health = project.target;
                    else state.area = std::min(1.,std::max(state.area,project.target));
                    complete(int(country),project.tile,building,project.repair);
                    changed = true;
                }
            }
            std::erase_if(queue,[](const auto& project) { return project.progress >= .999; });
        }
        return changed;
    }
};

}
