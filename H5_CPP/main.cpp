#include <SFML/Graphics.hpp>
#include "terrain_color.hpp"
#include <future>
#include "simulation_clock.hpp"
#include "market.hpp"
#include "diplomacy.hpp"
#include "combat.hpp"
#include "air_missions.hpp"
#include "construction.hpp"
#include "treasury.hpp"
#include "division_data.hpp"
#include "country_names.hpp"
#include "music.hpp"
#include "population.hpp"

#include <algorithm>
#include <array>
#include <deque>
#include <queue>
#include <limits>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <numbers>
#include <stdexcept>
#include <string_view>
#include <sstream>
#include <random>
#include <chrono>
#include <vector>

struct Tile {
    int owner{};
    int water{};
    double supply{};
    double population{};
    std::array<hoi5::BuildingCoverage, hoi5::buildingCount> buildings{};
    double movementCost{1};
    sf::Color terrain, border;
    hoi5::Terrain natural{};
    std::vector<std::string_view> industries;
    std::vector<hoi5::Deposit> deposits;
};

struct Division {
    int owner{};
    int q{};
    int r{};
    double speed{}, organization{}, maxOrganization{}, progress{};
    double visualProgress{};
    bool captureRoute{};
    std::deque<int> route;
    std::string icon;
    hoi5::CombatStats combat;
    int battle = -1;
    int manpower = 10000;
    const hoi5::DivisionTemplate* design = &hoi5::divisionTemplates[0];
    hoi5::Stockpile supplies = design->capacity;

    double consume(std::string_view key,double amount) {
        auto& stock = supplies[key];
        const double used = std::min(stock,amount);
        stock -= used;
        return used;
    }

    void loseStrength(double damage) {
        damage = std::clamp(damage,0.,combat.strength);
        const double ratio = damage/std::max(1.,design->combat.strength);
        manpower = std::max(0,int(std::nearbyint(manpower-design->manpower*ratio)));
        for (auto key : hoi5::DIVISION_EQUIPMENT_LOSS_KEYS)
            consume(key,hoi5::value(design->capacity,key)*ratio*hoi5::DIVISION_EQUIPMENT_STRENGTH_LOSS_MULT);
        for (auto key : hoi5::DIVISION_COMBAT_STOCK_LOSS_KEYS)
            consume(key,hoi5::value(design->capacity,key)*ratio*hoi5::DIVISION_COMBAT_STOCK_STRENGTH_LOSS_MULT);
        combat.strength -= damage;
    }

    std::array<double,3> attackSupplies(int hours) {
        std::array<hoi5::Stockpile,4> needs;
        const auto add = [&](int channel,std::string_view key,double perHour) {
            if (perHour > 0) needs[channel][key] = std::max(needs[channel][key],perHour*hours);
        };
        const auto supported = [&](std::string_view key) {
            return hoi5::value(design->capacity,key)>0 || hoi5::value(design->use,key)>0 || hoi5::value(supplies,key)>0;
        };
        const auto addAmmo = [&](int channel,std::string_view key,double amount) {
            if (supported(key)) add(channel,key,amount);
        };
        addAmmo(0,"small_arms_ammo",combat.softAttack*.62);
        addAmmo(0,"light_artillery_ammo",combat.softAttack*.08);
        addAmmo(0,"autocannon_ammo",combat.softAttack*.05);
        addAmmo(1,"old_at_missiles",combat.frontAttack*.075);
        addAmmo(1,"autocannon_ammo",combat.frontAttack*.070);
        addAmmo(1,"tank_ammo",combat.frontAttack*.095);
        addAmmo(2,"light_artillery_ammo",combat.topAttack*.18);
        addAmmo(2,"tank_ammo",combat.topAttack*.030);
        for (const auto& [key,amount] : design->use) {
            if (key == "light_aa_ammo" || key == "anti_air_ammo") continue;
            const int channel = key == "small_arms_ammo" ? 0 :
                key == "old_at_missiles" || key == "autocannon_ammo" || key == "tank_ammo" ? 1 :
                key == "light_artillery_ammo" || key == "artillery_ammo" ? 2 : 3;
            add(channel,key,amount);
        }
        add(3,"field_supplies",.35+std::max(1.,combat.width)/20*.22+
            (combat.softAttack+combat.frontAttack+combat.topAttack)*.010);
        addAmmo(3,"refined_fuel",combat.vehicles*std::max(.1,speed)*2.2);
        std::array ratios{1.,1.,1.,1.};
        for (int i = 0; i < 4; ++i)
            for (const auto& [key,amount] : needs[i]) ratios[i] = std::min(ratios[i],consume(key,amount)/amount);
        const auto factor = [&](int i) {
            return hoi5::DIVISION_AMMO_ATTACK_FLOOR + (1-hoi5::DIVISION_AMMO_ATTACK_FLOOR)*std::min(ratios[i],ratios[3]);
        };
        return {factor(0),factor(1),factor(2)};
    }
};

struct TrainingProject {
    int country, tile, type, hours{};
    double cost;
};

struct World {
    int size{};
    int capitalQ{}, capitalR{};
    std::vector<std::string> status;
    std::vector<Tile> tiles;
    std::vector<Division> divisions;
    bool bordersChanged{};
    std::vector<int> capitals;
    std::array<std::string_view,30> countryNames{}, rulers{};
    std::vector<hoi5::StartingProfile> profiles;
    std::vector<hoi5::Stockpile> stockpiles, capacities;
    std::vector<double> manpowerReserve;
    std::vector<TrainingProject> training;
    int populationHours{};
    std::vector<hoi5::Production> production;
    std::vector<hoi5::TreasuryFlows> treasury;
    hoi5::Market market;
    hoi5::Diplomacy diplomacy;
    hoi5::AirLayer air;
    std::vector<hoi5::AirSalvo> salvos;
    hoi5::Construction construction;
    std::map<int,hoi5::Battle> battles;
    std::mt19937 combatRandom;
    int difficulty = 1;

    World() = default;

    explicit World(const std::filesystem::path& path) {
        std::ifstream input(path);
        int count{};
        if (!(input >> size >> count) || size < 1 || size > 150 || count < 0 || count > 10000)
            throw std::runtime_error("Invalid reference scenario header");
        if (!(input >> capitalQ >> capitalR) || !contains(capitalQ, capitalR))
            throw std::runtime_error("Invalid capital");
        std::string line;
        std::getline(input, line);
        std::getline(input, line);
        std::istringstream fields(line);
        while (std::getline(fields, line, '|')) status.push_back(line);
        if (status.size() != 7) throw std::runtime_error("Invalid country status");
        tiles.resize(size * size);
        for (auto& tile : tiles) {
            int r, g, b, br, bg, bb;
            if (!(input >> tile.owner >> tile.water >> tile.supply >> tile.movementCost >> r >> g >> b >> br >> bg >> bb) || tile.owner < -1
                || tile.water < 0 || tile.water > 1 || tile.supply < 0 || tile.supply > 100
                || !std::isfinite(tile.movementCost) || tile.movementCost <= 0)
                throw std::runtime_error("Invalid reference tile");
            tile.supply /= 100;
            tile.terrain = sf::Color(r, g, b);
            tile.border = sf::Color(br, bg, bb);
        }
        divisions.resize(count);
        for (auto& unit : divisions)
            if (!(input >> unit.owner >> unit.q >> unit.r >> unit.speed >> unit.organization >> unit.maxOrganization >> unit.icon)
                || !contains(unit.q, unit.r) || unit.speed <= 0 || unit.maxOrganization <= 0)
                throw std::runtime_error("Invalid division position");
    }

    bool contains(int q, int r) const { return q >= 0 && r >= 0 && q < size && r < size; }
    const Tile& at(int q, int r) const { return tiles[r * size + q]; }

    bool orderMove(Division& unit, int destination) const {
        if (unit.battle >= 0 || unit.combat.strength <= 0 || unit.organization < unit.maxOrganization * .30) return false;
        if (destination < 0 || destination >= static_cast<int>(tiles.size())) return false;
        const int origin = unit.r * size + unit.q;
        const bool capture = tiles[destination].owner < 0 || diplomacy.hostile(unit.owner,tiles[destination].owner);
        std::vector<int> parent(tiles.size(), -1);
        std::vector<double> distance(tiles.size(), std::numeric_limits<double>::infinity());
        using Node = std::pair<double, int>;
        std::priority_queue<Node, std::vector<Node>, std::greater<>> frontier;
        frontier.emplace(0, origin);
        distance[origin] = 0;
        while (!frontier.empty()) {
            const auto [cost, cell] = frontier.top();
            frontier.pop();
            if (cost != distance[cell]) continue;
            if (cell == destination) {
                std::deque<int> route;
                for (int step = cell; step != origin; step = parent[step]) route.push_front(step);
                unit.route = std::move(route);
                unit.progress = 0;
                unit.visualProgress = 0;
                unit.captureRoute = capture;
                return true;
            }
            const int q = cell % size, r = cell / size;
            const int shift = r % 2;
            const std::array<std::pair<int, int>, 6> offsets{{
                {shift, 1}, {shift - 1, 1}, {-1, 0}, {shift - 1, -1}, {shift, -1}, {1, 0}
            }};
            for (const auto [dq, dr] : offsets) {
                if (!contains(q + dq, r + dr)) continue;
                const int next = (r + dr) * size + q + dq;
                const int owner = tiles[next].owner;
                const bool allowed = owner < 0 ? capture : diplomacy.canTransit(unit.owner,owner)
                    || (capture && diplomacy.hostile(unit.owner,owner));
                if (tiles[next].water || !allowed) continue;
                const double nextCost = cost + tiles[next].movementCost;
                if (nextCost >= distance[next]) continue;
                distance[next] = nextCost;
                parent[next] = cell;
                frontier.emplace(nextCost, next);
            }
        }
        return false;
    }

    void updateStatus() {
        if (stockpiles.empty()) return;
        const auto amount = [](double number) {
            std::ostringstream out;
            if (number >= 1e6) out << std::fixed << std::setprecision(1) << number / 1e6 << "M";
            else if (number >= 1e3) out << std::fixed << std::setprecision(1) << number / 1e3 << "K";
            else out << std::fixed << std::setprecision(0) << number;
            return out.str();
        };
        auto& stocks = stockpiles.front();
        const auto sum = [&](std::initializer_list<std::string_view> names) {
            double total = 0;
            for (auto name : names) total += stocks.at(name);
            return total;
        };
        const double metals = sum({"iron_ore","copper_ore","bauxite","lead","zinc","nickel",
            "gold","silver","rare_earth_metals","alloying_additives"});
        const double fuel = sum({"coal","oil","natural_gas","peat","uranium"});
        status = {"Player", "Нас: " + amount(profiles.front().population),
            "$" + amount(profiles.front().budget) + (treasury.front().balance() >= 0 ? "  +$" : "  −$")
                + amount(std::abs(treasury.front().balance())) + "/мес",
            "Металлы " + amount(metals) + "  Топливо " + amount(fuel) + "  Товары " + amount(stocks.at("consumer_goods")),
            "Стаб: " + std::to_string(int(std::lround(diplomacy.countries[0].stability*100))) + "%",
            "Легит: " + std::to_string(int(std::lround(diplomacy.countries[0].legitimacy*100))) + "%",
            "Подд. войны: " + std::to_string(int(std::lround(diplomacy.countries[0].warSupport*100))) + "%"};
    }

    void rebuildEconomy() {
        production.clear();
        capacities.clear();
        treasury.clear();
        for (int country = 0; country < static_cast<int>(profiles.size()); ++country) {
            production.push_back(hoi5::buildProduction(tiles, country, profiles[country].population, {}));
            capacities.push_back(hoi5::storageCapacity(tiles, country));
            treasury.push_back(hoi5::monthlyTreasury(tiles,country,profiles[country].population,
                diplomacy.countries[country].stability));
        }
    }

    void recover(Division& unit,int hours,double multiplier = 1) {
        const double ratio = std::clamp(unit.organization / std::max(1., unit.maxOrganization), 0., 1.);
        unit.organization = std::min(unit.maxOrganization,
            unit.organization + unit.design->recovery * (1 + .5 * (1 - ratio)) * at(unit.q,unit.r).supply * multiplier * hours / 24.);
    }

    double supplyRatio(const Division& unit) const {
        const auto& tile = at(unit.q,unit.r);
        return tile.supply*(tile.owner == unit.owner ? 1. : .25);
    }

    void replenish(Division& unit,int hours) {
        if (stockpiles.empty()) return;
        auto& stock = stockpiles[unit.owner];
        auto& reserve = manpowerReserve[unit.owner];
        const double fraction = supplyRatio(unit)*hours/24.*
            (unit.battle >= 0 ? hoi5::DIVISION_COMBAT_REINFORCEMENT_MULT : 1.);
        if (fraction <= 0) return;
        for (const auto& [key,capacity] : unit.design->capacity) {
            auto& held = unit.supplies[key];
            const double used = std::min({std::max(0.,capacity-held),capacity*.18*fraction,stock[key]});
            stock[key] -= used;
            held += used;
        }
        const double maximum = std::max(1.,unit.design->combat.strength);
        const int maxManpower = std::max(1,unit.design->manpower);
        const double missingStrength = std::max(0.,maximum-unit.combat.strength);
        const int missingManpower = std::max(0,maxManpower-unit.manpower);
        const double equivalent = std::min(hoi5::DIVISION_REINFORCEMENT_STRENGTH_PER_DAY*fraction,
            std::max(missingStrength,missingManpower/double(maxManpower)*maximum));
        const double strength = std::min(equivalent,missingStrength);
        const double manpower = std::min(double(missingManpower),maxManpower*equivalent/maximum);
        double ratio = manpower > 0 ? std::min(1.,reserve/manpower) : 1.;
        hoi5::Stockpile equipment;
        for (auto key : hoi5::DIVISION_EQUIPMENT_LOSS_KEYS) {
            const double needed = hoi5::value(unit.design->capacity,key)*strength/maximum*.42;
            if (needed > 0) {
                equipment[key] = needed;
                ratio = std::min(ratio,stock[key]/needed);
            }
        }
        ratio = std::clamp(ratio,0.,1.);
        if (strength*ratio <= 0 && manpower*ratio < 1) return;
        const int people = int(std::min(reserve,manpower*ratio)+1e-9);
        reserve -= people;
        unit.manpower += people;
        for (const auto& [key,needed] : equipment) stock[key] = std::max(0.,stock[key]-needed*ratio);
        unit.combat.strength += strength*ratio;
    }

    bool defended(int target,int country) const {
        return std::any_of(divisions.begin(),divisions.end(),[&](const Division& other) {
            return other.r*size+other.q == target && other.combat.strength > 0 && diplomacy.hostile(country,other.owner);
        });
    }

    bool safeTrainingSite(int country,int tile) const {
        const auto& site = tiles[tile];
        if (site.owner != country || site.water || site.supply < .25 || defended(tile,country)) return false;
        const int q = tile%size, r = tile/size, shift = r%2;
        for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
            {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
        }})
            if (contains(q+dq,r+dr) && defended((r+dr)*size+q+dq,country)) return false;
        return true;
    }

    static int trainingHours(const hoi5::DivisionTemplate& design) {
        return (30+int(std::ceil(design.combat.width*.5+design.combat.vehicles*20)))*24;
    }

    std::string train(int country,int tile,int type) {
        if (!safeTrainingSite(country,tile)) return "Нужна своя снабжаемая клетка вне боя";
        const auto& design = hoi5::divisionTemplates[type];
        double cost = design.manpower*80.;
        for (const auto& [key,amount] : design.capacity) cost += amount*hoi5::value(hoi5::TRADE_BASE_PRICES,key,100)*.05;
        cost = std::nearbyint(cost);
        if (profiles[country].budget < cost || manpowerReserve[country] < design.manpower)
            return "Недостаточно денег или резерва людей";
        auto& stock = stockpiles[country];
        for (const auto& [key,amount] : design.capacity)
            if (hoi5::value(stock,key)+1e-6 < amount) return "Не хватает: "+std::string(key);
        profiles[country].budget -= cost;
        manpowerReserve[country] -= design.manpower;
        for (const auto& [key,amount] : design.capacity) stock[key] = std::max(0.,stock[key]-amount);
        training.push_back({country,tile,type,0,cost});
        diplomacy.record("Начата подготовка дивизии");
        return "Подготовка начата";
    }

    void cancelTraining(std::size_t index) {
        const auto project = training[index];
        const auto& design = hoi5::divisionTemplates[project.type];
        profiles[project.country].budget += project.cost*std::max(0.,1-project.hours/double(trainingHours(design)));
        manpowerReserve[project.country] += design.manpower;
        for (const auto& [key,amount] : design.capacity) stockpiles[project.country][key] += amount;
        training.erase(training.begin()+index);
        diplomacy.record("Подготовка дивизии отменена");
    }

    void updateTraining(int hours) {
        std::erase_if(training,[&](TrainingProject& project) {
            const auto& design = hoi5::divisionTemplates[project.type];
            const int duration = trainingHours(design);
            project.hours = std::min(duration,project.hours+hours);
            if (project.hours < duration || !safeTrainingSite(project.country,project.tile)) return false;
            Division unit;
            unit.owner = project.country;
            unit.q = project.tile%size;
            unit.r = project.tile/size;
            unit.design = &design;
            unit.supplies = design.capacity;
            unit.combat = design.combat;
            unit.manpower = design.manpower;
            unit.maxOrganization = design.organization;
            unit.organization = design.organization*.5;
            unit.speed = design.speed;
            unit.icon = design.icon;
            divisions.push_back(std::move(unit));
            diplomacy.record("Дивизия завершила подготовку");
            return true;
        });
    }

    void joinBattle(int target,int index) {
        auto& unit = divisions[index];
        auto [entry,created] = battles.try_emplace(target,hoi5::Battle{unit.owner,tiles[target].owner});
        auto& battle = entry->second;
        if (created) {
            for (int i = 0; i < int(divisions.size()); ++i) {
                auto& defender = divisions[i];
                if (defender.battle >= 0 || defender.r*size+defender.q != target || defender.combat.strength <= 0
                    || defender.owner != battle.defender) continue;
                defender.battle = target;
                defender.progress = defender.visualProgress = 0;
                battle.defenders.push_back(i);
            }
        }
        if (unit.owner != battle.attacker) return;
        unit.battle = target;
        unit.progress = unit.visualProgress = 0;
        battle.attackers.push_back(index);
    }

    bool advanceBattles(int hours) {
        bool changed = false;
        for (auto it = battles.begin(); it != battles.end();) {
            const int target = it->first;
            auto& battle = it->second;
            const auto alive = [&](int i) { return divisions[i].combat.strength > 0; };
            const auto ready = [&](int i) { return alive(i) && divisions[i].organization > 0; };
            std::set<int> origins;
            for (int i : battle.attackers)
                if (alive(i)) origins.insert(divisions[i].r*size+divisions[i].q);
            const double width = 80+40*std::max(0,int(origins.size())-1);
            const auto active = [&](std::vector<int>& side,bool recoverReserve) {
                std::vector<int> result;
                std::stable_sort(side.begin(),side.end(),[&](int a,int b) {
                    return std::tuple{-divisions[a].combat.initiative,a} < std::tuple{-divisions[b].combat.initiative,b};
                });
                double remaining = width;
                for (int i : side) {
                    auto& unit = divisions[i];
                    if (!alive(i)) continue;
                    if (unit.organization <= 0) unit.combat.recovering = true;
                    const double share = std::min(1.,remaining/std::max(1.,unit.combat.width));
                    if (recoverReserve && (unit.combat.recovering || share < .6)) recover(unit,hours,.25);
                    if (unit.combat.recovering && unit.organization >= unit.maxOrganization*.30)
                        unit.combat.recovering = false;
                    if (!ready(i) || unit.combat.recovering || share < .6) continue;
                    unit.combat.widthEfficiency = share;
                    remaining = std::max(0.,remaining-unit.combat.width*share);
                    result.push_back(i);
                }
                return result;
            };
            const bool war = diplomacy.hostile(battle.attacker,battle.defender);
            if (war) {
                auto attackers = active(battle.attackers,true), defenders = active(battle.defenders,true);
                const auto attack = [&](const std::vector<int>& side,std::vector<int>& targets,bool defending) {
                    for (int i : side) {
                        std::erase_if(targets,[&](int j) { return !ready(j); });
                        if (targets.empty()) break;
                        if (!ready(i)) continue;
                        auto& attacker = divisions[i];
                        auto& defender = divisions[targets[std::uniform_int_distribution<std::size_t>(0,targets.size()-1)(combatRandom)]];
                        const auto& fort = tiles[target].buildings[hoi5::fortification];
                        const double armor = attacker.combat.vehicles;
                        const double bonus = defending && tiles[target].owner == defender.owner
                            ? fort.area*fort.health*(.3+.7*tiles[target].supply)*(.60*(1-armor)+.25*armor) : 0;
                        const double damage = hoi5::combatDamage(attacker.combat,defender.combat,defending,
                            attacker.attackSupplies(hours),supplyRatio(attacker),bonus);
                        defender.organization = std::max(0.,defender.organization-damage);
                        defender.loseStrength(damage*.35);
                    }
                };
                attack(attackers,defenders,true);
                attack(defenders,attackers,false);
                attackers = active(battle.attackers,false);
                defenders = active(battle.defenders,false);
                if (!attackers.empty() && defenders.empty()) battle.advance += .035*hours;
                if (!attackers.empty() && !defenders.empty()) battle.advance = std::max(0.,battle.advance-.05*hours);
            }
            const bool captured = war && battle.advance >= 1;
            if (war && !captured && std::any_of(battle.attackers.begin(),battle.attackers.end(),alive)) {
                ++it;
                continue;
            }
            for (int i : battle.attackers) {
                auto& unit = divisions[i];
                unit.battle = -1;
                unit.combat.recovering = false;
                if (!captured || !alive(i)) { unit.route.clear(); continue; }
                tiles[target].border = at(unit.q,unit.r).border;
                unit.q = target % size;
                unit.r = target / size;
                if (!unit.route.empty() && unit.route.front() == target) unit.route.pop_front();
            }
            for (int i : battle.defenders) {
                auto& unit = divisions[i];
                unit.battle = -1;
                unit.combat.recovering = false;
                if (!captured || !alive(i)) continue;
                unit.route.clear();
                const int q = unit.q, r = unit.r, shift = r % 2;
                for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
                    {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
                }}) {
                    if (!contains(q+dq,r+dr)) continue;
                    const auto& next = at(q+dq,r+dr);
                    if (next.owner != unit.owner || next.water) continue;
                    unit.q = q+dq;
                    unit.r = r+dr;
                    break;
                }
                if (unit.q == q && unit.r == r) unit.combat.strength = 0;
            }
            if (captured) {
                tiles[target].owner = battle.attacker;
                changed = bordersChanged = true;
            }
            it = battles.erase(it);
        }
        return changed;
    }

    bool airTargetValid(int owner,int tile,bool strategic) const {
        return strategic ? tiles[tile].owner >= 0 && diplomacy.hostile(owner,tiles[tile].owner) : defended(tile,owner);
    }

    bool updateAir(int hours) {
        bool infrastructureChanged = false;
        for (auto& wing : air.wings) {
            wing.cooldown = std::max(0.,wing.cooldown-hours);
            if (wing.cooldown > 0 || wing.count <= 0 || wing.target < 0 || tiles[wing.base].owner != wing.owner
                || !airTargetValid(wing.owner,wing.target,wing.strategic)) continue;
            const auto* weapon = hoi5::missionWeapon(wing.type,wing.strategic);
            if (!weapon || weapon->maxRange <= 0) continue;
            const int distance = hoi5::airHexDistance(wing.base,wing.target,size);
            const auto x = [&](int tile) { return (tile%size+.5*((tile/size)%2))*std::sqrt(3.); };
            if (std::hypot(x(wing.base)-x(wing.target),1.5*(wing.base/size-wing.target/size))
                > hoi5::aircraftTypes[wing.type].range*std::sqrt(3.)) continue;
            int danger = 0;
            for (const auto& battery : air.defense) {
                const auto& type = hoi5::defenseClasses[battery.type];
                if (diplomacy.hostile(wing.owner,battery.owner) && type.fireRange > 0
                    && hoi5::airHexDistance(battery.tile,wing.target,size) <= type.fireRange+1)
                    danger = std::max(danger,type.fireRange);
            }
            double desired = std::max(weapon->optimal,double(danger));
            if (!wing.strategic) desired = std::min(desired,weapon->maxRange*.62);
            const double launch = std::max(weapon->minRange,std::min({weapon->maxRange,double(distance),desired}));
            const bool flight = weapon->interceptable && launch > std::max(.15,weapon->terminalRange);
            const int origin = flight ? hoi5::airTileBetween(wing.target,wing.base,size,launch/std::max(1,distance)) : wing.target;
            const int sorties = std::max(1,int(std::ceil(wing.count*.5*.25)));
            salvos.push_back({wing.owner,origin,wing.target,origin,sorties*hoi5::munitionsPerSortie(*weapon),weapon,
                flight ? launch : 0,flight ? launch : 0,hoi5::weaponInterceptability(*weapon,launch),wing.strategic});
            wing.cooldown = 16;
        }
        std::erase_if(salvos,[&](hoi5::AirSalvo& salvo) {
            if (!airTargetValid(salvo.owner,salvo.target,salvo.strategic)) return true;
            const auto& weapon = *salvo.weapon;
            const double speed = salvo.remaining <= 1 ? weapon.terminal : weapon.cruise;
            salvo.remaining = std::max(0.,salvo.remaining-hours*speed);
            salvo.current = hoi5::airTileBetween(salvo.origin,salvo.target,size,
                salvo.distance > 0 ? 1-salvo.remaining/salvo.distance : 1);
            if (salvo.distance > 0) for (auto& battery : air.defense) {
                if (!diplomacy.hostile(battery.owner,salvo.owner) || tiles[battery.tile].owner != battery.owner) continue;
                const auto& type = hoi5::defenseClasses[battery.type];
                if (!type.fireRange || battery.ammo <= 0) continue;
                const int distance = hoi5::airHexDistance(battery.tile,salvo.current,size);
                if (distance < type.minimumRange || distance > type.fireRange) continue;
                const auto [maximum,escape] = hoi5::interceptorRanges[battery.type];
                const double range = distance <= escape ? 1. : std::max(.28,1-(distance-escape)/std::max(.001,maximum-escape)*.55);
                double radar = 0;
                for (const auto& support : air.defense)
                    if (support.owner == battery.owner && tiles[support.tile].owner == support.owner
                        && hoi5::defenseClasses[support.type].key == "radar_unit" &&
                        hoi5::airHexDistance(support.tile,salvo.current,size) <= hoi5::defenseClasses[support.type].radarRange)
                        radar += .06;
                const double signature = std::clamp(.42+weapon.rcs*.45+weapon.infrared*.20+std::min(.18,radar),0.,1.);
                const double tracking = std::clamp(type.trackingQuality*.58+type.detectionPower*.42,0.,1.);
                const double probability = std::clamp(salvo.interceptability*(.32+tracking*.68)*range*signature
                    *std::max(.42,1-std::max(0.,weapon.terminal-1)*.14)*std::max(.55,1-weapon.maneuver*.28)
                    *std::max(.35,1-weapon.difficulty*.38)*type.readiness,0.,1.);
                const int engaged = std::min({salvo.count,battery.ammo/type.interceptors,type.fireChannels,
                    type.trackingChannels,type.maxTargets});
                if (engaged <= 0) continue;
                battery.ammo -= engaged*type.interceptors;
                salvo.count -= std::binomial_distribution<int>(engaged,probability)(combatRandom);
                if (salvo.count <= 0) return true;
            }
            if (salvo.remaining > 0) return false;
            bool hitDivision = false;
            if (!salvo.strategic) {
                std::vector<int> targets;
                for (int i = 0; i < int(divisions.size()); ++i) {
                    const auto& unit = divisions[i];
                    if (unit.r*size+unit.q == salvo.target && unit.combat.strength > 0 && diplomacy.hostile(unit.owner,salvo.owner))
                        targets.push_back(i);
                }
                if (!targets.empty()) {
                    auto& target = divisions[targets[std::uniform_int_distribution<std::size_t>(0,targets.size()-1)(combatRandom)]];
                    const double damage = salvo.count*std::max(.05,weapon.warhead)*std::clamp(weapon.accuracy,0.,1.);
                    target.organization = std::max(0.,target.organization-damage*.70);
                    target.loseStrength(damage*.11);
                    hitDivision = true;
                }
            }
            auto& tile = tiles[salvo.target];
            std::array<double,hoi5::buildingCount> weights{};
            for (int i = 0; i < hoi5::buildingCount; ++i) {
                const auto& building = tile.buildings[i];
                if (building.area > 0 && building.health > 0)
                    weights[i] = std::max(.02,building.area)*building.health*hoi5::buildingValue[i];
            }
            if (std::any_of(weights.begin(),weights.end(),[](double weight) { return weight > 0; })) {
                const auto type = static_cast<hoi5::Building>(std::discrete_distribution<int>(weights.begin(),weights.end())(combatRandom));
                auto& building = tile.buildings[type];
                const double damage = hoi5::buildingDamage(salvo,type,hitDivision ? .16 : 1.);
                building.health = std::max(0.,building.health-damage);
                infrastructureChanged |= damage > 0;
            }
            return true;
        });
        return infrastructureChanged;
    }

    void advance(int hours) {
        if (hours <= 0) return;
        for (std::size_t country = 0; country < production.size(); ++country) {
            auto& stocks = stockpiles[country];
            profiles[country].budget += treasury[country].balance()*hours/720.;
            hoi5::runProduction(production[country], stocks, hours, [&](auto key, double amount) {
                stocks[key] += std::min(amount, hoi5::freeStorage(capacities[country], stocks, key));
            });
        }
        const bool airDamage = updateAir(hours);
        const bool built = construction.advance(tiles,profiles,stockpiles,hours,
            [&](int country,int index,hoi5::Building building) {
                auto& tile = tiles[index];
                if (building == hoi5::industry && tile.industries.empty()) {
                    double score = 0;
                    tile.industries = hoi5::industryAllocation(tiles,size,index,score);
                }
                if (building == hoi5::airbase) {
                    const auto& b = tile.buildings[hoi5::airbase];
                    const double coverage = b.area*b.health;
                    const hoi5::Airbase replacement{country,index,1+int(coverage>=.32),int(28+coverage*90),
                        int(8+coverage*38),8000+coverage*38000,4000+coverage*18000,.8+coverage*1.4,coverage>=.30};
                    auto base = std::find_if(air.bases.begin(),air.bases.end(),[&](const auto& item) {
                        return item.tile == index;
                    });
                    if (base == air.bases.end()) air.bases.push_back(replacement);
                    else *base = replacement;
                }
            },[&](int index) { return battles.contains(index); });
        bool ownershipChanged = advanceBattles(hours);
        for (auto& unit : divisions)
            if (unit.combat.strength > 0) replenish(unit,hours);
        for (int index = 0; index < int(divisions.size()); ++index) {
            auto& unit = divisions[index];
            if (unit.battle >= 0 || unit.combat.strength <= 0) continue;
            const double ratio = std::clamp(unit.organization / std::max(1., unit.maxOrganization), 0., 1.);
            if (unit.route.empty() || ratio < .30) {
                recover(unit,hours);
                continue;
            }
            const auto canEnter = [&](int index) {
                const auto& tile = tiles[index];
                return !tile.water && (tile.owner < 0 ? unit.captureRoute : diplomacy.canTransit(unit.owner,tile.owner)
                    || (unit.captureRoute && diplomacy.hostile(unit.owner,tile.owner)));
            };
            if (!canEnter(unit.route.front())) {
                unit.route.clear();
                unit.progress = unit.visualProgress = 0;
                continue;
            }
            if (defended(unit.route.front(),unit.owner)) {
                joinBattle(unit.route.front(),index);
                continue;
            }
            double supplies = 1;
            for (const auto& [key,need] : std::array<std::pair<std::string_view,double>,2>{{
                {"refined_fuel",unit.combat.vehicles*unit.speed*1.8*hours},{"field_supplies",.12*hours}
            }})
                if (need > 0) supplies = std::min(supplies,unit.consume(key,need)/need);
            const double progress = unit.speed * std::max(.35, .35 + .65 * ratio) * (.55+.45*supplies)
                * hours / 24. / tiles[unit.route.front()].movementCost;
            unit.progress += progress;
            unit.organization = std::max(0., unit.organization - 1.4 * progress);
            while (!unit.route.empty() && unit.progress >= 1) {
                const int next = unit.route.front();
                if (!canEnter(next)) {
                    unit.route.clear();
                    break;
                }
                if (defended(next,unit.owner)) {
                    joinBattle(next,index);
                    unit.progress = unit.visualProgress = 0;
                    break;
                }
                unit.route.pop_front();
                auto& tile = tiles[next];
                if (tile.owner < 0 || diplomacy.hostile(unit.owner,tile.owner)) {
                    tile.border = at(unit.q, unit.r).border;
                    tile.owner = unit.owner;
                    bordersChanged = true;
                    ownershipChanged = true;
                }
                unit.q = next % size;
                unit.r = next / size;
                unit.progress -= 1;
                unit.visualProgress = std::clamp(unit.progress, 0., 1.);
            }
            if (unit.route.empty()) unit.progress = unit.visualProgress = 0;
        }
        updateTraining(hours);
        populationHours += hours;
        const bool populationTick = populationHours >= 720 && !profiles.empty() && profiles.size() == production.size();
        if (populationTick) {
            const double months = populationHours/720.;
            populationHours = 0;
            std::vector<std::vector<int>> territory(profiles.size());
            for (int i = 0; i < int(tiles.size()); ++i)
                if (tiles[i].owner >= 0) territory[tiles[i].owner].push_back(i);
            for (std::size_t i = 0; i < profiles.size(); ++i)
                profiles[i].population = hoi5::runPopulationMonth(tiles,territory[i],production[i],stockpiles[i],months);
        } else if (ownershipChanged && !profiles.empty()) {
            for (auto& profile : profiles) profile.population = 0;
            for (const auto& tile : tiles)
                if (tile.owner >= 0) profiles[tile.owner].population += tile.population;
        }
        if ((airDamage || built || ownershipChanged || populationTick) && !capitals.empty()) {
            bordersChanged = true;
            hoi5::recalculateSupply(std::span(tiles), size, capitals);
            rebuildEconomy();
        }
    }

    void updateVisualMotion(double dt) {
        const double smoothing = std::min(1., dt * 12.);
        for (auto& unit : divisions) {
            const double target = unit.route.empty() ? 0. : std::clamp(unit.progress, 0., 1.);
            unit.visualProgress += (target - unit.visualProgress) * smoothing;
            if (std::abs(unit.visualProgress - target) < .002) unit.visualProgress = target;
        }
    }
};

constexpr float radius = 90.f;
constexpr float spacing = 1.7320508f * radius;

sf::Vector2f center(int q, int r) {
    return {100.f + spacing * (q + .5f * (r % 2)), -100.f - 1.5f * radius * r};
}

World generateWorld(int size, int countries, unsigned seed, int difficulty) {
    World world;
    world.size = size;
    world.difficulty = difficulty;
    world.combatRandom.seed(seed);
    std::tie(world.countryNames,world.rulers) = hoi5::countryIdentities(seed);
    world.tiles.resize(size * size);
    hoi5::WorldGenerator generator(size, seed);
    for (int r = 0; r < size; ++r) for (int q = 0; q < size; ++q) {
        const auto terrain = generator.generate(q, r);
        auto& tile = world.tiles[r * size + q];
        tile.natural = terrain;
        tile.owner = -1;
        tile.water = terrain.water > .5;
        tile.movementCost = tile.water ? 1 : terrain.movementCost();
        tile.terrain = hoi5::terrainColor(terrain);
        tile.deposits = hoi5::generateDeposits(terrain, seed, q, r);
    }
    constexpr std::array<sf::Color, 12> colors{{
        {255,30,20}, {255,230,0}, {0,220,255}, {255,0,210}, {80,255,40}, {255,135,0},
        {190,65,255}, {0,255,215}, {255,255,80}, {40,105,255}, {255,75,135}, {215,255,55}
    }};
    const int radiusInTiles = std::clamp(int(std::nearbyint(double(size) / std::max(8, countries * 2))), 3, 12);
    const int minDistance = std::max(2, int(std::nearbyint(
        (2 * radiusInTiles + 1) * std::clamp(8. / countries, .45, 1.))));
    const auto hexDistance = [&](int a, int b) {
        const int ar = a / size, br = b / size;
        const int dq = a % size - b % size;
        const int dr = ar - br;
        return std::max({std::abs(dq), std::abs(dr), std::abs(dq + dr)});
    };
    const auto first = center(0, 0), last = center(size - 1, size - 1);
    const auto middle = sf::Vector2f{(first.x + center(size - 1, 1).x) / 2, (first.y + last.y) / 2};
    std::vector<int> starts;
    for (int country = 0; country < countries; ++country) {
        const double angle = 2 * std::numbers::pi * country / countries - std::numbers::pi / 2;
        const double x = middle.x + std::cos(angle) * (middle.x - first.x) * .62;
        const double y = middle.y - std::sin(angle) * (first.y - middle.y) * .62;
        int best = -1, fallback = -1;
        double distance = std::numeric_limits<double>::infinity(), fallbackDistance = distance;
        for (int q = 0; q < size; ++q) for (int r = 0; r < size; ++r) {
            const int index = r * size + q;
            const auto position = center(q, r);
            const double score = std::hypot(position.x - x, position.y - y);
            if (score < fallbackDistance) {
                fallbackDistance = score;
                fallback = index;
            }
            if (score < distance && !world.tiles[index].water &&
                std::none_of(starts.begin(), starts.end(), [&](int other) {
                    return hexDistance(index, other) < minDistance;
                })) {
                best = index;
                distance = score;
            }
        }
        starts.push_back(best >= 0 ? best : fallback);
    }

    const double claimRadius = (radiusInTiles + .5) * (spacing + radius * 1.5) / 2;
    for (int country = 0; country < countries; ++country) {
        const int capital = starts[country];
        const auto origin = center(capital % size, capital / size);
        for (int r = 0; r < size; ++r) for (int q = 0; q < size; ++q) {
            const auto offset = center(q, r) - origin;
            if (std::hypot(offset.x, offset.y) > claimRadius) continue;
            auto& tile = world.tiles[r * size + q];
            tile.owner = country;
            tile.border = colors[country % colors.size()];
        }
    }
    world.capitals = starts;
    world.diplomacy.countries.resize(countries);
    world.construction.queues.resize(countries);
    std::vector<std::vector<int>> land(countries);
    for (int index = 0; index < size * size; ++index) {
        const auto& tile = world.tiles[index];
        if (tile.owner >= 0 && !tile.water) land[tile.owner].push_back(index);
    }
    for (int country = 0; country < countries; ++country) {
        auto profile = hoi5::startingProfile(size, static_cast<int>(land[country].size()));

        hoi5::placeStartingCities(world.tiles, size, starts[country], land[country], profile);
        const double unspent = land[country].empty() ? 14.85
            : hoi5::placeStartingBuildings(world.tiles, size, starts[country], land[country], profile.scale);
        auto stocks = hoi5::startingStockpile(seed, profile.scale);
        hoi5::compensateStartingResources(world.tiles, country, land[country], unspent, profile, stocks);
        world.profiles.push_back(profile);
        world.stockpiles.push_back(std::move(stocks));
        hoi5::assignStartingIndustry(world.tiles, size, land[country]);
        hoi5::distributeStartingPopulation(world.tiles, land[country], profile.population);
    }
    world.air.initialize(world.tiles,size,world.capitals,world.profiles);
    hoi5::recalculateSupply(std::span(world.tiles), size, world.capitals);
    for (int country = 0; country < countries; ++country) {
        auto& candidates = land[country];
        if (candidates.empty()) continue;
        std::stable_sort(candidates.begin(), candidates.end(), [&](int a, int b) {
            const auto score = [&](int index) {
                const auto& tile = world.tiles[index];
                const int capital = starts[country];
                const int distance = std::abs(index % size - capital % size) + std::abs(index / size - capital / size);
                return tile.buildings[hoi5::city].area * 1.6 + tile.buildings[hoi5::village].area * .8
                    + tile.supply * .5 + hoi5::ownedNeighbors(world.tiles, size, index) * .08 - distance * .015;
            };
            return std::tuple{-score(a), a % size, a / size} < std::tuple{-score(b), b % size, b / size};
        });
        for (int i = 0; i < 10; ++i) {
            const int index = candidates[i % candidates.size()];
            Division unit;
            unit.owner = country;
            unit.q = index % size;
            unit.r = index / size;
            unit.speed = 1.35;
            unit.organization = unit.maxOrganization = 100;
            unit.icon = "infantry";
            world.divisions.push_back(std::move(unit));
        }
    }
    world.manpowerReserve.resize(countries);
    for (int country = 0; country < countries; ++country) {
        const auto& state = world.diplomacy.countries[country];
        const double volunteers = std::clamp(.04+.62*state.warSupport+.13*state.stability+.13*state.legitimacy,0.,.82);
        world.manpowerReserve[country] = world.profiles[country].population*.61*.54*volunteers;
    }
    for (const auto& unit : world.divisions) {
        auto& reserve = world.manpowerReserve[unit.owner];
        reserve = std::max(0.,reserve-unit.manpower);
        for (const auto& [key,amount] : unit.design->capacity) world.stockpiles[unit.owner][key] += amount*2.5;
    }
    world.rebuildEconomy();
    world.capitalQ = world.capitals.front() % size;
    world.capitalR = world.capitals.front() / size;
    world.updateStatus();
    return world;
}
sf::Vector2f unitPosition(const World& world, const Division& unit) {
    const auto origin = center(unit.q, unit.r);
    if (unit.route.empty()) return origin;
    const int next = unit.route.front();
    return origin + (center(next % world.size, next / world.size) - origin)
        * static_cast<float>(unit.visualProgress);
}

sf::Color supplyColor(const Tile& tile) {
    const auto blend = [](sf::Color a, sf::Color b, double t) {
        return sf::Color(a.r * (1-t) + b.r * t, a.g * (1-t) + b.g * t, a.b * (1-t) + b.b * t);
    };
    if (tile.owner < 0 || tile.water) return blend(tile.terrain, {12,16,22}, .62);
    const auto score = tile.supply;
    const auto target = score < .25 ? sf::Color(154,48,44) : score < .50 ? sf::Color(190,142,54)
        : score < .75 ? sf::Color(146,174,74) : sf::Color(62,156,88);
    return blend({28,34,42}, target, .36 + score * .45);
}

sf::VertexArray makeMap(const World& world, bool showSupply = false) {
    sf::VertexArray geometry(sf::PrimitiveType::Triangles);
    for (int r = 0; r < world.size; ++r) {
        for (int q = 0; q < world.size; ++q) {
            const auto position = center(q, r);
            const auto color = showSupply ? supplyColor(world.at(q, r)) : world.at(q, r).terrain;
            const auto corner = [&](int i) {
                float angle = std::numbers::pi_v<float> * (i / 3.f + 1.f / 6.f);
                return position + sf::Vector2f(std::cos(angle), std::sin(angle)) * (radius - .4f);
            };
            for (int side = 0; side < 6; ++side) {
                geometry.append({position, color});
                geometry.append({corner(side), color});
                geometry.append({corner(side + 1), color});
            }
        }
    }
    return geometry;
}

sf::VertexArray makeBorders(const World& world) {
    sf::VertexArray lines(sf::PrimitiveType::Triangles);
    for (int r = 0; r < world.size; ++r) for (int q = 0; q < world.size; ++q) {
        const auto& tile = world.at(q, r);
        if (tile.owner < 0) continue;
        const auto position = center(q, r);
        const int shift = r % 2;
        const std::array<std::pair<int, int>, 6> neighbors{{
            {1, 0}, {shift, 1}, {shift - 1, 1}, {-1, 0}, {shift - 1, -1}, {shift, -1}
        }};
        for (int edge = 0; edge < 6; ++edge) {
            const auto [dq, dr] = neighbors[edge];
            if (world.contains(q+dq, r+dr) && world.at(q+dq, r+dr).owner == tile.owner) continue;
            const float angle = -edge * std::numbers::pi_v<float> / 3;
            const auto point = [&](float offset) {
                return position + sf::Vector2f(std::cos(angle+offset), std::sin(angle+offset)) * radius;
            };
            const auto a = point(-std::numbers::pi_v<float>/6), b = point(std::numbers::pi_v<float>/6);
            const sf::Vector2f thickness(std::cos(angle)*3.5f, std::sin(angle)*3.5f);
            for (auto v : {a-thickness, b-thickness, b+thickness, a-thickness, b+thickness, a+thickness})
                lines.append({v, tile.border});
        }
    }
    return lines;
}

#include <map>
#include <tuple>
void box(sf::RenderWindow& window, sf::Vector2f position, sf::Vector2f size,
         sf::Color fill, sf::Color border = sf::Color::Transparent) {
    sf::RectangleShape shape(size);
    shape.setPosition(position);
    shape.setFillColor(fill);
    shape.setOutlineColor(border);
    shape.setOutlineThickness(-1.f);
    window.draw(shape);
}

void label(sf::RenderWindow& window, const sf::Font& font, const std::string& value,
           sf::Vector2f position, unsigned size = 13) {
    sf::Text text(font, sf::String::fromUtf8(value.begin(), value.end()), size);
    text.setPosition(position);
    text.setFillColor({224, 234, 244});
    window.draw(text);
}

int main(int argc, char** argv) try {
    const auto directory = std::filesystem::absolute(argv[0]).parent_path();
    const std::filesystem::path source = HOI5_PYTHON_DIR;
    World world(directory / "reference-map.txt");
    const std::string_view mode = argc > 1 ? argv[1] : "";
    if (mode == "--check-construction-training") {
        auto generated = generateWorld(50,2,823558,1);
        const int capital = generated.capitals[0];
        if (!generated.construction.enqueue(generated.tiles,generated.size,0,capital,8).empty()) return 1;
        for (int i = 0; i < 720 && !generated.construction.queues[0].empty(); i += 6) generated.advance(6);
        if (generated.tiles[capital].buildings[hoi5::supplyDepot].area <= 0) return 1;
        const auto units = generated.divisions.size();
        if (generated.train(0,capital,0) != "Подготовка начата") return 1;
        generated.updateTraining(World::trainingHours(hoi5::divisionTemplates[0]));
        return generated.divisions.size() == units+1 && generated.divisions.back().organization == 50 ? 0 : 1;
    }
    if (mode == "--check-air-strike") {
        World test;
        test.size = 2;
        test.tiles.resize(4);
        test.tiles[0].owner = 0;
        test.tiles[1].owner = 1;
        test.tiles[1].buildings[hoi5::industry].area = .3;
        test.diplomacy.countries.resize(2);
        test.diplomacy.relation(0,1).war = true;
        test.air.wings.push_back({0,0,1,8,1,0,true});
        for (int i = 0; i < 8 && test.tiles[1].buildings[hoi5::industry].health == 1; ++i) test.updateAir(1);
        return test.tiles[1].buildings[hoi5::industry].health < 1 && test.air.wings[0].cooldown > 0 ? 0 : 1;
    }
    if (mode == "--check-battle") {
        World test;
        test.size = 2;
        test.tiles.resize(4);
        test.tiles[0].owner = 0;
        test.tiles[1].owner = 1;
        test.tiles[2].owner = 0;
        test.tiles[3].owner = 1;
        test.diplomacy.countries.resize(2);
        test.profiles.resize(2,{1,21000000,250000000});
        const auto action = [](hoi5::ForeignAction wanted) -> const hoi5::ForeignActionInfo& {
            return *std::find_if(std::begin(hoi5::foreignActions),std::end(hoi5::foreignActions),
                [&](const auto& item) { return item.action == wanted; });
        };
        if (!test.diplomacy.act(0,1,action(hoi5::ForeignAction::justify),test.profiles).empty()) return 1;
        if (test.diplomacy.act(0,1,action(hoi5::ForeignAction::war),test.profiles).empty()) return 1;
        test.diplomacy.advance(30,test.profiles);
        if (!test.diplomacy.act(0,1,action(hoi5::ForeignAction::war),test.profiles).empty()) return 1;
        if (test.diplomacy.tradeAllowed(0,1)) return 1;
        test.divisions.resize(2);
        for (int i = 0; i < 2; ++i) {
            auto& unit = test.divisions[i];
            unit.owner = unit.q = i;
            unit.organization = unit.maxOrganization = 100;
            unit.speed = 1.35;
        }
        test.divisions[1].organization = 1;
        if (!test.orderMove(test.divisions[0],1)) return 1;
        test.advance(1);
        if (!test.battles.contains(1)) return 1;
        for (int hour = 0; hour < 60 && test.tiles[1].owner != 0; ++hour) test.advance(1);
        return test.tiles[1].owner == 0 && test.divisions[0].q == 1 && test.divisions[1].r == 1 ? 0 : 1;
    }
    if (mode == "--check-economy") {
        auto generated = generateWorld(50, 2, 823558, 1);
        if (generated.air.bases.empty() || generated.air.defense.empty()) return 1;
        const int reserve = generated.air.reserves[0][0];
        if (generated.air.createWing(generated.tiles,0,0,4) < 0 || generated.air.reserves[0][0] != reserve-4) return 1;
        const double before = generated.stockpiles[0].at("consumer_goods");
        generated.advance(24);
        if (generated.stockpiles[0].at("consumer_goods") == before) return 1;
        const double budget = generated.profiles[0].budget;
        generated.market.changeContract(0,"coal",false,1000);
        generated.market.execute(generated.tiles,generated.profiles,generated.stockpiles,generated.capacities,
            1,[](int a,int b) { return a != b; },[](int,int) { return 0; },[](int) { return true; });
        return generated.market.last.fills.size() == 1 && generated.profiles[0].budget > budget ? 0 : 1;
    }
    if (mode == "--check-map")
        return world.size == 50 && world.divisions.size() == 20 && world.status.size() == 7 ? 0 : 1;
    if (mode == "--check-capture") {
        auto& unit = world.divisions.front();
        for (int destination=0; destination<static_cast<int>(world.tiles.size()); ++destination) {
            if (world.tiles[destination].owner >= 0 || world.tiles[destination].water
                || !world.orderMove(unit,destination)) continue;
            for (int i=0;i<1000 && !unit.route.empty();++i) world.advance(1);
            return world.tiles[destination].owner == unit.owner && world.bordersChanged ? 0 : 1;
        }
        return 1;
    }
    if (mode == "--check-movement") {
        auto& unit = world.divisions.front();
        const int origin = unit.r * world.size + unit.q;
        for (int target = 0; target < static_cast<int>(world.tiles.size()); ++target) {
            if (target == origin || !world.orderMove(unit, target)) continue;
            const auto originalOrganization = unit.organization;
            for (int i = 0; i < 1000 && !unit.route.empty(); ++i) world.advance(1);
            return unit.route.empty() && unit.r * world.size + unit.q == target
                && unit.organization < originalOrganization ? 0 : 1;
        }
        return 1;
    }
    sf::RenderWindow window(sf::VideoMode({1280, 800}), "HOI5");
    const bool generationSmoke = mode == "--smoke-generation";
    const bool smoke = mode == "--smoke-window" || generationSmoke;
    if (smoke) window.setVisible(false);
    window.setVerticalSyncEnabled(true);
    sf::Font font;
    const char* windows = std::getenv("WINDIR");
    if (!windows || !font.openFromFile(std::filesystem::path(windows) / "Fonts/segoeui.ttf"))
        throw std::runtime_error("Could not open Segoe UI");
    std::array<sf::Texture, 8> icons;
    const std::array names{"politics", "economy", "resources", "trade", "construction", "research", "diplomacy", "military"};
    for (std::size_t i = 0; i < names.size(); ++i)
        if (!icons[i].loadFromFile(source / "assets/ui_icons" / (std::string(names[i]) + ".png")))
            throw std::runtime_error("Could not open navigation icon");
    sf::Texture layers;
    if (!layers.loadFromFile(source / "assets/layers_icon.png")) throw std::runtime_error("Could not open layers icon");
    auto map = makeMap(world);
    auto borders = makeBorders(world);
    float zoom = 1.f;
    sf::View camera = window.getDefaultView();
    auto target = center(world.capitalQ, world.capitalR);
    camera.setCenter(target);
    bool playing = mode == "--smoke-window", dragging = false;
    bool setup = false, pauseMenu = false, showSupply = false;
    hoi5::SimulationClock simulation;
    auto& paused = simulation.paused;
    auto& speed = simulation.speed;
    int selected = -1, sizeChoice = 2, countries = 4;
    int difficulty = 1, dropdown = -1;
    bool tradePanel = false;
    int tradeScroll = 0;
    bool diplomacyPanel = false, aircraftPanel = false;
    int selectedWing = -1;
    bool constructionPanel = false, militaryPanel = false;
    int economicPanel = 0, resourceScroll = 0;
    std::string militaryMessage;
    int buildingSpec = 0;
    std::string constructionMessage;
    int foreignTarget = 1;
    std::string foreignMessage;
    constexpr std::array sizes{50,75,100,125,150};
    const std::array<std::string,3> difficulties{"Легкая","Обычная","Сложная"};
    const auto option = [&](int field, int index) -> std::string {
        if (field == 0) return difficulties[index];
        if (field == 1) return std::to_string(index);
        const auto value = std::to_string(sizes[index]);
        return value + " × " + value;
    };
    const auto optionCount = [](int field) { return field == 0 ? 3 : field == 1 ? 12 : 5; };
    const auto optionTop = [&](int field) {
        const int header = static_cast<int>(window.getSize().y/2) - 117 + 75*field;
        return std::min(header+42, static_cast<int>(window.getSize().y)-8-25*optionCount(field));
    };
    sf::Vector2i dragStart;
    sf::Vector2f dragTarget;
    std::string errorMessage;
    std::future<World> generator;
    const auto startGame = [&] {
        if (generator.valid()) return;
        errorMessage.clear();
        dropdown = -1;
        const int size = sizes[sizeChoice];
        const unsigned seed = 1 + std::random_device{}() % 999999;
        generator = std::async(std::launch::async, generateWorld, size, countries, seed, difficulty);
    };
    if (generationSmoke) startGame();
    sf::Clock clock;
    sf::Clock startupClock, musicReview;
    std::optional<hoi5::DynamicMusic> music;
    if (!smoke) music.emplace(source / "music");
    auto musicCategory = hoi5::economyMusic;
    while (window.isOpen()) {
        const float dt = std::min(.05f, clock.restart().asSeconds());
        while (const auto event = window.pollEvent()) {
            if (event->is<sf::Event::Closed>()) window.close();
            if (event->is<sf::Event::FocusLost>()) dragging = false;
            if (const auto* resize = event->getIf<sf::Event::Resized>())
                camera.setSize(sf::Vector2f(resize->size) / zoom);
            if (const auto* key = event->getIf<sf::Event::KeyPressed>()) {
                using Key = sf::Keyboard::Key;
                if (!playing && key->code == Key::Enter) {
                    if (setup) startGame(); else setup = true;
                }
                if (key->code == Key::Escape) {
                    if (playing) pauseMenu = !pauseMenu;
                    else if (dropdown >= 0) dropdown = -1;
                    else setup = false;
                }
                if (playing && !pauseMenu && key->code == Key::Space) paused = !paused;
                if (playing && key->code >= Key::Num1 && key->code <= Key::Num5)
                    speed = 1 + static_cast<int>(key->code) - static_cast<int>(Key::Num1);
            }
            if (const auto* button = event->getIf<sf::Event::MouseButtonPressed>()) {
                if (!playing && button->button == sf::Mouse::Button::Left
                    && sf::IntRect({static_cast<int>(window.getSize().x / 2) - 150,
                                    static_cast<int>(window.getSize().y / 2) - 152}, {300, 42})
                           .contains(button->position) && !setup) setup = true;
                else if (!playing && setup && button->button == sf::Mouse::Button::Left) {
                    const int cx = window.getSize().x / 2, cy = window.getSize().y / 2;
                    const int x = button->position.x, y = button->position.y;
                    if (dropdown >= 0) {
                        const int offset = y - optionTop(dropdown);
                        if (std::abs(x-cx) < 230 && offset >= 0 && offset < 25*optionCount(dropdown)) {
                            const int choice = offset/25;
                            if (dropdown == 0) difficulty = choice;
                            if (dropdown == 1) countries = choice+1;
                            if (dropdown == 2) sizeChoice = choice;
                        }
                        dropdown = -1;
                    } else if (std::abs(x-cx) < 230) {
                        for (int field=0;field<3;++field) {
                            const int top = cy-117+75*field;
                            if (y>=top && y<top+42) dropdown=field;
                        }
                        if (y >= cy+124 && y < cy+170) {
                            if (x < cx) startGame(); else setup = false;
                        }
                    }
                }
                if (playing && pauseMenu && button->button == sf::Mouse::Button::Left) {
                    const int cx = window.getSize().x / 2, cy = window.getSize().y / 2;
                    if (std::abs(button->position.x-cx) < 150) {
                        if (button->position.y >= cy-55 && button->position.y < cy-13) pauseMenu = false;
                        if (button->position.y >= cy && button->position.y < cy+42) {
                            playing = pauseMenu = setup = false;
                        }
                    }
                } else if (playing && button->button == sf::Mouse::Button::Left) {
                    const int x = button->position.x, y = button->position.y;
                    const int panel = static_cast<int>(window.getSize().x)-312;
                    if (y >= 40 && y < 78 && ((x >= 57 && x < 95) || (x >= 102 && x < 140))
                        && !world.stockpiles.empty()) {
                        const int panelType = x < 100 ? 1 : 2;
                        economicPanel = economicPanel == panelType ? 0 : panelType;
                        militaryPanel = constructionPanel = diplomacyPanel = tradePanel = false;
                    } else if (economicPanel && x >= 20 && x < 630 && y >= 90 && y < 550) {
                        // Panel clicks must not issue map orders.
                    } else if (y >= 40 && y < 78 && x >= 327 && x < 365 && !world.stockpiles.empty()) {
                        militaryPanel = !militaryPanel;
                        economicPanel = 0;
                        constructionPanel = diplomacyPanel = tradePanel = false;
                    } else if (militaryPanel && x >= 20 && x < 430 && y >= 90 && y < 340) {
                        if (y >= 124 && y < 124 + int(std::size(hoi5::divisionTemplates))*28) {
                            const int type = (y-124)/28;
                            const auto capital = world.capitals[0];
                            militaryMessage = world.train(0,capital,type);
                            world.updateStatus();
                        } else if (y >= 272 && y < 295 && !world.training.empty()) {
                            world.cancelTraining(world.training.size()-1);
                            world.updateStatus();
                        }
                    } else if (y >= 40 && y < 78 && x >= 192 && x < 230 && !world.construction.queues.empty()) {
                        constructionPanel = !constructionPanel;
                        economicPanel = 0;
                        diplomacyPanel = tradePanel = militaryPanel = false;
                    } else if (constructionPanel && x >= 20 && x < 300 && y >= 90 && y < 515) {
                        if (y >= 122 && y < 122 + int(std::size(hoi5::constructionSpecs))*23)
                            buildingSpec = (y-122)/23;
                        else if (y >= 455 && y < 485 && !world.construction.queues[0].empty())
                            world.construction.queues[0].back().paused = !world.construction.queues[0].back().paused;
                    } else if (x >= 20 && x < 94 && y >= int(window.getSize().y)-82 && y < int(window.getSize().y)-34
                        && !world.air.reserves.empty()) {
                        aircraftPanel = !aircraftPanel;
                    } else if (aircraftPanel && x >= 20 && x < 405 && y >= int(window.getSize().y)-290
                        && y < int(window.getSize().y)-140) {
                        const int type = (y-(int(window.getSize().y)-290))/25;
                        const int wing = world.air.createWing(world.tiles,0,type,12);
                        if (wing >= 0) selectedWing = wing;
                    } else if (y >= 40 && y < 78 && x >= 282 && x < 320 && world.profiles.size() > 1) {
                        diplomacyPanel = !diplomacyPanel;
                        economicPanel = 0;
                        tradePanel = constructionPanel = militaryPanel = false;
                    } else if (diplomacyPanel && x >= 20 && x < 445 && y >= 90 && y < 510) {
                        if (y < 127) {
                            foreignTarget = foreignTarget + 1 < int(world.profiles.size()) ? foreignTarget + 1 : 1;
                            foreignMessage.clear();
                        } else if (y < 127 + int(std::size(hoi5::foreignActions))*25) {
                            const auto& action = hoi5::foreignActions[(y-127)/25];
                            foreignMessage = world.diplomacy.act(0,foreignTarget,action,world.profiles);
                            if (foreignMessage.empty()) foreignMessage = "Решение принято";
                            world.updateStatus();
                        }
                    } else if (y >= 40 && y < 78 && x >= 147 && x < 185 && !world.stockpiles.empty()) {
                        tradePanel = !tradePanel;
                        economicPanel = 0;
                        diplomacyPanel = constructionPanel = militaryPanel = false;
                    } else if (tradePanel && x >= 20 && x < 660 && y >= 90 && y < 550) {
                        if (x >= 440 && y >= 120) {
                            const auto& stocks = world.stockpiles.front();
                            const auto row = std::size_t(tradeScroll + (y-120)/25);
                            if (row < stocks.size()) {
                                const auto resource = std::next(stocks.begin(),row)->first;
                                const bool buy = x < 550;
                                const bool plus = x < 490 || (x >= 550 && x < 600);
                                world.market.changeContract(0,resource,buy,plus ? 1000. : -1000.);
                            }
                        }
                    } else if (x >= int(window.getSize().x) - 62 && x < int(window.getSize().x) - 18
                        && y >= int(window.getSize().y) - 62 && y < int(window.getSize().y) - 18) {
                        showSupply = !showSupply;
                        map = makeMap(world, showSupply);
                    } else if (y >= 130 && y < 154 && x >= panel+14 && x < panel+122) {
                        const int control = (x-panel-14)/39;
                        if (control == 1) paused = !paused;
                        else speed = std::clamp(speed + (control == 0 ? -1 : 1),1,5);
                    } else if (constructionPanel && y >= 82) {
                        const auto point = window.mapPixelToCoords(button->position,camera);
                        int cell = -1;
                        float distance = radius*radius;
                        for (int r = std::max(0,int((-point.y-100)/(1.5f*radius))-1);
                             r < std::min(world.size,int((-point.y-100)/(1.5f*radius))+3); ++r) {
                            const int approximate = int((point.x-100)/spacing-.5f*(r%2));
                            for (int q = std::max(0,approximate-1); q < std::min(world.size,approximate+3); ++q) {
                                const auto d = center(q,r)-point;
                                const float squared = d.x*d.x+d.y*d.y;
                                if (squared < distance) { distance = squared; cell = r*world.size+q; }
                            }
                        }
                        if (cell >= 0) {
                            constructionMessage = world.construction.enqueue(world.tiles,world.size,0,cell,buildingSpec);
                            if (constructionMessage.empty()) constructionMessage = "Добавлено в очередь";
                        }
                    } else if (y >= 82) {
                        const auto clicked = window.mapPixelToCoords(button->position, camera);
                        selected = -1;
                        float best = radius * radius * .25f;
                        for (int i=0; i<static_cast<int>(world.divisions.size()); ++i) {
                            const auto& unit = world.divisions[i];
                            const auto delta = clicked-unitPosition(world,unit);
                            const float d = delta.x*delta.x+delta.y*delta.y;
                            if (unit.owner == 0 && unit.combat.strength > 0 && d < best) { best=d; selected=i; }
                        }
                    }
                }
                if (playing && !pauseMenu && (button->button == sf::Mouse::Button::Middle || button->button == sf::Mouse::Button::Right)) {
                    dragging = true;
                    dragStart = button->position;
                    dragTarget = target;
                }
            }
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button != sf::Mouse::Button::Left) {
                if (dragging && release->button == sf::Mouse::Button::Right && (selected >= 0 || (selectedWing >= 0 && aircraftPanel))
                    && release->position == dragStart && release->position.y >= 82) {
                    const auto clicked = window.mapPixelToCoords(release->position, camera);
                    int nearest = -1;
                    float best = radius*radius;
                    for (int r=0;r<world.size;++r) for(int q=0;q<world.size;++q) {
                        const auto delta = clicked-center(q,r);
                        const float d = delta.x*delta.x+delta.y*delta.y;
                        if(d<best) { best=d; nearest=r*world.size+q; }
                    }
                    if (nearest >= 0 && selectedWing >= 0 && aircraftPanel) {
                        auto& wing = world.air.wings[selectedWing];
                        if (world.air.freeCapacity(world.tiles,wing.owner,nearest,wing.type,selectedWing) >= wing.count
                            && nearest != wing.base) {
                            wing.base = nearest;
                            wing.target = -1;
                            wing.cooldown = std::max(1.,wing.cooldown);
                        } else {
                            wing.target = nearest;
                            wing.strategic = !world.defended(nearest,wing.owner);
                        }
                    } else if (selected >= 0) world.orderMove(world.divisions[selected],nearest);
                }
                dragging = false;
            }
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>(); motion && dragging)
                target = dragTarget - sf::Vector2f(motion->position - dragStart) / zoom;
            if (const auto* wheel = event->getIf<sf::Event::MouseWheelScrolled>(); wheel && playing) {
                if (economicPanel == 2 && wheel->position.x >= 20 && wheel->position.x < 630
                    && wheel->position.y >= 90 && wheel->position.y < 550) {
                    resourceScroll = std::clamp(resourceScroll - int(std::copysign(3.f,wheel->delta)),0,
                        std::max(0,int(world.stockpiles.front().size())-17));
                    continue;
                }
                if (tradePanel && wheel->position.x >= 20 && wheel->position.x < 660
                    && wheel->position.y >= 90 && wheel->position.y < 550) {
                    tradeScroll = std::clamp(tradeScroll - int(std::copysign(3.f,wheel->delta)),0,
                        std::max(0,int(world.stockpiles.front().size())-17));
                    continue;
                }
                const auto anchor = window.mapPixelToCoords(wheel->position, camera);
                zoom = std::clamp(zoom + .05f * wheel->delta, .05f, 2.5f);
                camera.setSize(sf::Vector2f(window.getSize()) / zoom);
                camera.move(anchor - window.mapPixelToCoords(wheel->position, camera));
                target = camera.getCenter();
            }
        }
        if (!window.isOpen()) break;
        if (generator.valid() && generator.wait_for(std::chrono::seconds(0)) == std::future_status::ready) {
            try {
                world = generator.get();
                if (music) music->newWorld();
                (void)musicReview.restart();
                showSupply = tradePanel = diplomacyPanel = false;
                aircraftPanel = constructionPanel = militaryPanel = false;
                militaryMessage.clear();
                constructionMessage.clear();
                selectedWing = -1;
                foreignTarget = 1;
                foreignMessage.clear();
                economicPanel = resourceScroll = tradeScroll = 0;
                map = makeMap(world);
                borders = makeBorders(world);
                zoom = 1.f;
                target = center(world.capitalQ, world.capitalR);
                camera.setCenter(target);
                camera.setSize(sf::Vector2f(window.getSize()));
                playing = true;
                selected = -1;
                simulation = {};
            } catch (const std::exception& error) { errorMessage = error.what(); }
        }
        const bool loading = generator.valid();
        const auto size = sf::Vector2f(window.getSize());
        const sf::View gui(sf::FloatRect({0.f, 0.f}, size));
        window.clear({18, 24, 31});
        if (playing) {
            if (!pauseMenu) {
                const int previousTick = simulation.tickCount;
                simulation.update(dt, [&](int hours) {
                    world.advance(hours);
                    world.diplomacy.advance(simulation.elapsedHours/24,world.profiles);
                    if (simulation.pendingMarketTicks && !world.stockpiles.empty()) {
                        simulation.pendingMarketTicks = 0;
                        world.market.execute(world.tiles,world.profiles,world.stockpiles,world.capacities,
                            simulation.marketTickCount,[&](int a,int b) { return world.diplomacy.tradeAllowed(a,b); },
                            [&](int a,int b) { return world.diplomacy.tradePriority(a,b); },
                            [&](int country) { return world.diplomacy.countries[country].externalAccess; });
                    }
                });
                if (simulation.tickCount != previousTick) world.updateStatus();
                if (world.bordersChanged) {
                    borders = makeBorders(world);
                    if (showSupply) map = makeMap(world, true);
                    world.bordersChanged = false;
                }
            }
            world.updateVisualMotion(dt);
            using Key = sf::Keyboard::Key;
            if (window.hasFocus()) {
                if (sf::Keyboard::isKeyPressed(Key::Left)) target.x -= 300 * dt;
                if (sf::Keyboard::isKeyPressed(Key::Right)) target.x += 300 * dt;
                if (sf::Keyboard::isKeyPressed(Key::Up)) target.y -= 300 * dt;
                if (sf::Keyboard::isKeyPressed(Key::Down)) target.y += 300 * dt;
            }
            target.x = std::clamp(target.x, 100.f - radius, center(world.size - 1, 1).x + radius);
            target.y = std::clamp(target.y, center(0, world.size - 1).y - radius, -100.f + radius);
            camera.move((target - camera.getCenter()) * .3f);
            window.setView(camera);
            window.draw(map);
            window.draw(borders);
            window.setView(gui);
            std::map<std::tuple<int,int,int,std::string>, int> groups;
            for (const auto& unit : world.divisions)
                if (unit.combat.strength > 0) ++groups[{unit.q, unit.r, unit.owner, unit.icon}];
            std::map<std::pair<int,int>, int> rows;
            for (const auto& [key, count] : groups) {
                const auto& [q, r, owner, icon] = key;
                const auto point = sf::Vector2f(window.mapCoordsToPixel(center(q,r), camera));
                if (point.x < -54 || point.x > size.x+54 || point.y < -50 || point.y > size.y+50) continue;
                const float w = zoom < .45f ? 54.f : std::max(32.f, 50.f * zoom);
                const float h = zoom < .45f ? 34.f : std::max(24.f, 32.f * zoom);
                const int row = rows[{q,r}]++;
                const sf::Vector2f p(point.x-w*.5f, point.y-h*.5f-row*(h+2));
                const auto border = world.at(q,r).border;
                const sf::Color fill((border.r*56+32*44)/100, (border.g*56+38*44)/100, (border.b*56+44*44)/100);
                const bool highlighted = selected >= 0 && world.divisions[selected].q == q
                    && world.divisions[selected].r == r && world.divisions[selected].owner == owner
                    && world.divisions[selected].icon == icon;
                box(window,p,{w,h},fill,highlighted ? sf::Color::Yellow : sf::Color(186,204,220));
                box(window,p+sf::Vector2f(2,3),{5,h-6},{118,204,238});
                box(window,p+sf::Vector2f(7,h-6),{w-10,4},{110,214,126});
                if (icon == "infantry") {
                    sf::CircleShape head(3);
                    head.setPosition(p+sf::Vector2f(14,5));
                    head.setFillColor({18,24,31});
                    window.draw(head);
                    box(window,p+sf::Vector2f(15,11),{4,10},{18,24,31});
                    box(window,p+sf::Vector2f(11,13),{12,3},{18,24,31});
                    box(window,p+sf::Vector2f(12,20),{10,3},{18,24,31});
                } else {
                    box(window,p+sf::Vector2f(10,14),{16,5},{18,24,31});
                    box(window,p+sf::Vector2f(13,9),{7,6},{18,24,31});
                    box(window,p+sf::Vector2f(19,10),{10,2},{18,24,31});
                    box(window,p+sf::Vector2f(10,21),{16,3},{18,24,31});
                }
                label(window,font,std::to_string(count),p+sf::Vector2f(w-16,6));
            }
            for (const auto& salvo : world.salvos) {
                const auto point = sf::Vector2f(window.mapCoordsToPixel(
                    center(salvo.current%world.size,salvo.current/world.size),camera));
                box(window,point-sf::Vector2f(4,4),{8,8},{243,169,55});
            }
            for (const auto& base : world.air.bases) {
                if (world.tiles[base.tile].owner != base.owner) continue;
                const auto point = sf::Vector2f(window.mapCoordsToPixel(
                    center(base.tile%world.size,base.tile/world.size),camera));
                box(window,point+sf::Vector2f(-9,19),{18,15},{43,88,131},{103,168,228});
                label(window,font,"A",point+sf::Vector2f(-4,17),13);
            }
            for (const auto& [tile, battle] : world.battles) {
                const auto p = sf::Vector2f(window.mapCoordsToPixel(center(tile%world.size,tile/world.size),camera));
                box(window,p+sf::Vector2f(-30,-42),{60,16},{105,37,36},{194,111,85});
                box(window,p+sf::Vector2f(-29,-41),{58*float(std::clamp(battle.advance,0.,1.)),14},{76,150,87});
                label(window,font,"Бой",p+sf::Vector2f(-12,-43),13);
            }
            box(window,{0,0},{size.x,36},{18,24,31,245},{88,106,128});
            box(window,{0,36},{size.x,46},{24,31,40,238},{70,88,108});
            float x=10;
            for (const auto& field : world.status) {
                const auto string = sf::String::fromUtf8(field.begin(),field.end());
                const float width = std::max(88.f, string.getSize()*7.f+22.f);
                if (x+width > size.x-8) break;
                if (field == world.status.front() || field == world.status[3])
                    box(window,{x-5,5},{width-8,26},field == world.status[3] ? sf::Color(112,92,42,225) : sf::Color::Transparent,{118,146,176});
                label(window,font,field,{x,9});
                x+=width;
            }
            for (std::size_t i=0; i<icons.size(); ++i) {
                const float left=12+45.f*i;
                box(window,{left,40},{38,38},{30,39,50},{92,112,136});
                sf::Sprite sprite(icons[i]);
                sprite.setPosition({left+4,44});
                sprite.setScale({30.f/icons[i].getSize().x,30.f/icons[i].getSize().y});
                window.draw(sprite);
            }
            const float timeX=size.x-312;
            box(window,{timeX,92},{300,72},{20,29,38,235},{100,126,155});
            using namespace std::chrono;
            const year_month_day date{sys_days{year{2000}/1/1} + days{simulation.elapsedHours/24}};
            const std::array<std::string,12> months{"янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"};
            const int hour=simulation.elapsedHours%24;
            label(window,font,std::to_string(unsigned(date.day()))+" "+months[unsigned(date.month())-1]
                  +" "+std::to_string(int(date.year()))+"  "+(hour<10?"0":"")+std::to_string(hour)+":00",{timeX+72,98},17);
            for (int i=0;i<3;++i) {
                const float bx=timeX+14+i*39;
                box(window,{bx,130},{30,24},{30,39,50},{92,112,136});
                label(window,font,std::array<std::string,3>{"−",paused ? ">" : "II","+"}[i],{bx+10,133});
            }
            label(window,font,std::string(paused?"Пауза  |  ":"")+"Скорость "+std::to_string(speed)+"/5",{timeX+146,133});
            box(window,{10,size.y-116},{420,102},{18,24,31,235},{92,112,136});
            label(window,font,"Авиакрылья",{21,size.y-113});
            box(window,{20,size.y-82},{74,48},{24,31,40},{92,112,136});
            label(window,font,"+",{49,size.y-78},24);
            if (selectedWing >= 0) {
                const auto& wing = world.air.wings[selectedWing];
                label(window,font,std::string(hoi5::aircraftTypes[wing.type].key)+"  ×"+std::to_string(wing.count),{110,size.y-75},16);
            }
            if (aircraftPanel) {
                box(window,{20,size.y-324},{385,185},{18,24,31,250},{92,112,136});
                label(window,font,"Авиакрылья  |  ПКМ — цель",{30,size.y-319},18);
                for (int type = 0; type < int(std::size(hoi5::aircraftTypes)); ++type) {
                    const float y = size.y-290+type*25;
                    box(window,{25,y},{375,23},{30,39,50});
                    label(window,font,std::string(hoi5::aircraftTypes[type].key),{32,y+2},15);
                    label(window,font,std::to_string(world.air.reserves[0][type]),{335,y+2},15);
                }
            }
            box(window,{440,size.y-54},{560,38},{18,24,31,235},{92,112,136});
            label(window,font,"Мировые новости",{450,size.y-46});
            box(window,{size.x-62,size.y-62},{44,44},{18,24,31,235},{92,112,136});
            sf::Sprite sprite(layers);
            sprite.setPosition({size.x-56,size.y-56});
            sprite.setScale({32.f/layers.getSize().x,32.f/layers.getSize().y});
            window.draw(sprite);
            if (economicPanel == 1) {
                box(window,{20,90},{400,275},{18,24,31,250},{92,112,136});
                label(window,font,"Экономика",{30,97},19);
                const auto& flows = world.treasury.front();
                const std::array<std::pair<std::string_view,double>,7> rows{{
                    {"Казна",world.profiles[0].budget},{"Налоги населения",flows.population},
                    {"Налоги компаний",flows.companies},{"Государственные расходы",-flows.government},
                    {"Социальные расходы",-flows.social},{"Содержание инфраструктуры",-flows.infrastructure},
                    {"Баланс в месяц",flows.balance()}
                }};
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    const auto [name,amount] = rows[i];
                    const float y = 130+i*29.f;
                    std::ostringstream text;
                    text << std::fixed << std::setprecision(2) << amount/1e6 << " M";
                    label(window,font,std::string(name),{32,y},16);
                    label(window,font,text.str(),{314,y},16);
                }
            }
            if (economicPanel == 2) {
                box(window,{20,90},{610,460},{18,24,31,250},{92,112,136});
                label(window,font,"Ресурсы",{30,96},18);
                label(window,font,"Запас            Выпуск/мес           Расход/мес",{250,98},15);
                const auto& stocks = world.stockpiles[0];
                auto item = std::next(stocks.begin(),resourceScroll);
                for (int row = 0; row < 17 && item != stocks.end(); ++row,++item) {
                    const auto [key,amount] = *item;
                    double output = 0, input = 0;
                    for (const auto& stage : world.production[0]) {
                        output += hoi5::value(stage.outputs,key);
                        input += hoi5::value(stage.inputs,key);
                    }
                    const float y = 120+row*25.f;
                    label(window,font,std::string(key),{30,y},15);
                    label(window,font,std::to_string(int(amount)),{250,y},15);
                    label(window,font,std::to_string(int(output)),{385,y},15);
                    label(window,font,std::to_string(int(input)),{525,y},15);
                }
            }
            if (militaryPanel) {
                box(window,{20,90},{410,250},{18,24,31,250},{92,112,136});
                label(window,font,"Подготовка дивизий     Резерв: "+std::to_string(int(world.manpowerReserve[0])),{30,97},17);
                for (int i = 0; i < int(std::size(hoi5::divisionTemplates)); ++i) {
                    const float y = 124+i*28.f;
                    box(window,{27,y},{394,25},{30,39,50});
                    label(window,font,std::string(hoi5::divisionTemplates[i].name),{34,y+2},16);
                }
                label(window,font,"В очереди: "+std::to_string(world.training.size())+"  |  Отменить последнюю",{30,272},15);
                label(window,font,militaryMessage,{30,302},15);
            }
            if (constructionPanel) {
                box(window,{20,90},{280,425},{18,24,31,250},{92,112,136});
                label(window,font,"Строительство",{30,96},18);
                for (int i = 0; i < int(std::size(hoi5::constructionSpecs)); ++i) {
                    const float y = 122+i*23.f;
                    box(window,{26,y},{268,21},i == buildingSpec ? sf::Color(47,71,88) : sf::Color(30,39,50));
                    label(window,font,std::string(hoi5::constructionSpecs[i].label),{32,y+1},15);
                }
                const auto& queue = world.construction.queues[0];
                label(window,font,"В очереди: "+std::to_string(queue.size())+"  |  Пауза последнего",{30,460},15);
                label(window,font,constructionMessage,{30,485},15);
            }
            if (diplomacyPanel) {
                box(window,{20,90},{425,420},{18,24,31,250},{92,112,136});
                const auto& relation = world.diplomacy.relation(0,foreignTarget);
                label(window,font,std::string(world.countryNames[foreignTarget])+"  >   "+
                    (relation.war ? "Война" : "Мир"),{30,97},18);
                for (std::size_t i = 0; i < std::size(hoi5::foreignActions); ++i) {
                    const float y = 127+i*25.f;
                    box(window,{27,y},{411,22},{30,39,50});
                    label(window,font,std::string(hoi5::foreignActions[i].label),{33,y+2},16);
                }
                label(window,font,foreignMessage,{30,442},15);
                if (!world.diplomacy.history.empty())
                    label(window,font,world.diplomacy.history.front(),{30,469},15);
            }
            if (tradePanel) {
                box(window,{20,90},{640,460},{18,24,31,250},{92,112,136});
                label(window,font,"Торговля     Запас       Цена       Покупка / Продажа в месяц",{30,96},16);
                const auto& stocks = world.stockpiles.front();
                auto item = std::next(stocks.begin(),tradeScroll);
                for (int row = 0; row < 17 && item != stocks.end(); ++row,++item) {
                    const auto [key, amount] = *item;
                    const float y = 120 + row*25.f;
                    label(window,font,std::string(key),{30,y},15);
                    label(window,font,std::to_string(static_cast<int>(amount)),{240,y},15);
                    label(window,font,std::to_string(static_cast<int>(world.market.price(key))),{326,y},15);
                    for (bool buy : {true,false}) {
                        const float x = buy ? 440.f : 550.f;
                        double order = 0;
                        for (const auto& contract : world.market.contracts)
                            if (contract.country == 0 && contract.resource == key && contract.buy == buy)
                                order = contract.amount;
                        box(window,{x,y},{48,21},{30,53,66});
                        box(window,{x+50,y},{48,21},{49,38,48});
                        label(window,font,"+"+std::to_string(static_cast<int>(order)),{x+3,y},14);
                        label(window,font,"−",{x+66,y},14);
                    }
                }
            }
            if (pauseMenu) {
                box(window,{0,0},size,{8,12,17,170});
                const float x=size.x/2-150, y=size.y/2;
                box(window,{x,y-55},{300,42},{30,39,50},{92,112,136});
                box(window,{x,y},{300,42},{30,39,50},{92,112,136});
                label(window,font,"Вернуться в игру",{x+18,y-46},18);
                label(window,font,"Выйти в главное меню",{x+18,y+9},18);
            }
        } else {
            window.setView(gui);
            box(window,{0,0},size,{13,18,24});
            box(window,{0,0},{size.x,96},{20,29,38});
            box(window,{0,size.y-88},{size.x,88},{20,29,38});
            if (loading) label(window,font,"Мир генерируется",{size.x/2-130,size.y/2-16},30);
            else if (setup) {
                label(window,font,"Новая игра",{size.x/2-100,32},36);
                const float x=size.x/2-230, y=size.y/2;
                const std::array<std::string,3> captions{"Сложность","Количество ботов","Размер карты"};
                const std::array chosen{difficulty,countries-1,sizeChoice};
                for (int field=0;field<3;++field) {
                    const float top=y-117+75*field;
                    label(window,font,captions[field],{x,top-24},16);
                    box(window,{x,top},{460,42},{30,39,50},{92,112,136});
                    label(window,font,option(field,chosen[field]),{x+12,top+10},18);
                    label(window,font,"v",{x+433,top+10},18);
                }
                box(window,{x,y+124},{220,46},{30,39,50},{92,112,136});
                box(window,{x+240,y+124},{220,46},{30,39,50},{92,112,136});
                label(window,font,"Начать игру",{x+14,y+135},18);
                label(window,font,"Назад",{x+254,y+135},18);
                if (dropdown >= 0) for (int i=0;i<optionCount(dropdown);++i) {
                    const float top = optionTop(dropdown)+25*i;
                    box(window,{x,top},{460,25},i == chosen[dropdown] ? sf::Color(60,78,98)
                                                                     : sf::Color(30,39,50),{92,112,136});
                    label(window,font,option(dropdown,i),{x+12,top+3},16);
                }
                if (!errorMessage.empty()) label(window,font,errorMessage,{80,size.y-60});
            } else {
                label(window,font,"HOI 5",{size.x/2-48,32},36);
                const std::array<std::string,6> buttons{"Новая игра", "Продолжить игру",
                    "Мультиплеер", "Настройки", "Помощь", "Выход из игры"};
                for (std::size_t i=0;i<buttons.size();++i) {
                    const float y=size.y/2-152+54*i;
                    box(window,{size.x/2-150,y},{300,42},{30,39,50},{92,112,136});
                    const auto value = sf::String::fromUtf8(buttons[i].begin(),buttons[i].end());
                    sf::Text text(font,value,18);
                    if (i!=0) text.setFillColor({152,164,180});
                    const auto bounds=text.getLocalBounds();
                    text.setPosition({size.x/2-bounds.size.x/2-bounds.position.x,
                                      y+21-bounds.size.y/2-bounds.position.y});
                    window.draw(text);
                }
                if (!errorMessage.empty()) label(window,font,errorMessage,{80,size.y-60});
            }
        }
        if (music) {
            if (musicReview.getElapsedTime().asSeconds() >= 1) {
                musicCategory = playing ? music->category(world) : hoi5::economyMusic;
                (void)musicReview.restart();
            }
            music->update(musicCategory);
        }
        window.display();
        if (smoke && playing) window.close();
        if (generationSmoke && (!errorMessage.empty() || startupClock.getElapsedTime().asSeconds() > 60))
            throw std::runtime_error(errorMessage.empty() ? "Generation timed out" : errorMessage);
    }
} catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
}
