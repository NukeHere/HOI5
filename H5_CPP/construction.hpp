#pragma once

#include "construction_data.hpp"

namespace hoi5 {

struct ConstructionProject {
    int tile;
    int spec;
    double from, target, work, money;
    Stockpile resources;
    double progress{};
    bool paid{}, paused{};
};

struct Construction {
    std::vector<std::vector<ConstructionProject>> queues;

    template<class Tile>
    std::string_view enqueue(const std::vector<Tile>& tiles,int size,int owner,int index,int spec) {
        if (tiles[index].owner != owner) return "Чужая клетка";
        if (tiles[index].water) return "Нужна суша";
        const auto& data = constructionSpecs[spec];
        if (data.building == port) {
            bool coastal = false;
            ownedNeighbors(tiles,size,index,&coastal);
            if (!coastal) return "Порт только рядом с водой";
        }
        constexpr ResourceWeight solid[] = {{"coal",1},{"peat",.55},{"iron_ore",1},{"copper_ore",.82},
            {"bauxite",.64},{"sulfur",.42},{"phosphorite",.40},{"apatite",.36}};
        constexpr ResourceWeight oil[] = {{"oil",1},{"natural_gas",.95}};
        if (data.building == mine && resourceScore(tiles[index].deposits,solid) <= 0) return "Нужны твёрдые залежи";
        if (data.building == oilGasRig && resourceScore(tiles[index].deposits,oil) <= 0) return "Нужна нефть или газ";
        double current = tiles[index].buildings[data.building].area;
        auto& queue = queues[owner];
        for (const auto& project : queue)
            if (project.tile == index && project.spec == spec) current = std::max(current,project.target);
        if (current >= 1) return "Уже максимум";
        const double target = std::min(1.,(std::floor(current/.05+1e-9)+1)*.05);
        const double factor = (target-current)*std::pow(1.10,std::floor(current/.05));
        auto resources = data.resources;
        for (auto& [key,amount] : resources) amount *= factor;
        queue.push_back({index,spec,current,target,data.work*factor,data.money*factor,std::move(resources)});
        return {};
    }

    template<class Tile,class Complete,class InBattle>
    bool advance(std::vector<Tile>& tiles,std::vector<StartingProfile>& countries,
                 std::vector<Stockpile>& stocks,int hours,Complete complete,InBattle inBattle) {
        bool changed = false;
        for (std::size_t country = 0; country < queues.size(); ++country) {
            auto& queue = queues[country];
            std::erase_if(queue,[&](const auto& project) { return tiles[project.tile].owner != int(country); });
            if (queue.empty()) continue;
            double power = 0;
            for (const auto& tile : tiles) {
                if (tile.owner != int(country)) continue;
                const auto effective = [&](Building type) {
                    const auto& b = tile.buildings[type];
                    return b.area*b.health;
                };
                power += 100*(effective(industry)+effective(city)+effective(village)*.5);
            }
            const int active = std::min(3,int(std::count_if(queue.begin(),queue.end(),[](const auto& p) { return !p.paused; })));
            if (!active) continue;
            int used = 0;
            for (auto& project : queue) {
                if (project.paused) continue;
                if (++used > active) break;
                auto& tile = tiles[project.tile];
                const auto building = constructionSpecs[project.spec].building;
                auto& area = tile.buildings[building].area;
                if (area + 1e-8 < project.from) continue;
                if (!project.paid) {
                    if (countries[country].budget < project.money) continue;
                    countries[country].budget -= project.money;
                    project.paid = true;
                }
                const double speed = inBattle(project.tile) ? .22 : 1.;
                const double delta = std::min(1-project.progress,power/active*speed*hours/720./std::max(1.,project.work));
                if (delta <= 0) continue;
                auto& stock = stocks[country];
                if (std::any_of(project.resources.begin(),project.resources.end(),[&](const auto& r) {
                    return value(stock,r.first)+.001 < r.second*delta;
                })) continue;
                for (const auto& [resource,amount] : project.resources)
                    stock[resource] = std::max(0.,stock[resource]-amount*delta);
                project.progress += delta;
                if (project.progress >= .999) {
                    area = std::max(area,project.target);
                    complete(int(country),project.tile,building);
                    changed = true;
                }
            }
            std::erase_if(queue,[](const auto& project) { return project.progress >= .999; });
        }
        return changed;
    }
};

}
