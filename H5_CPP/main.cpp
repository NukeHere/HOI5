#include <SFML/Graphics.hpp>
#include "terrain_color.hpp"
#include <future>
#include "simulation_clock.hpp"
#include "market.hpp"
#include "diplomacy.hpp"
#include "combat.hpp"
#include "air_missions.hpp"
#include "construction.hpp"
#include "settings.hpp"
#include "resource_descriptions.hpp"
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

std::string formatAmount(double number) {
    std::ostringstream out;
    if (number >= 1e6) out << std::fixed << std::setprecision(1) << number/1e6 << "M";
    else if (number >= 1e3) out << std::fixed << std::setprecision(1) << number/1e3 << "K";
    else out << std::fixed << std::setprecision(0) << number;
    return out.str();
}

std::string_view terrainDisplayName(std::string_view terrain) {
    constexpr std::pair<std::string_view,std::string_view> names[] = {
        {"deep_ocean","Глубокий океан"},
        {"ocean","Океан"},
        {"shallow_water","Мелководье"},
        {"lake","Озеро"},
        {"river","Река"},
        {"swamp","Болото"},
        {"bog","Торфяник"},
        {"mangrove","Мангры"},
        {"mountains","Горы"},
        {"snowy_mountains","Снежные горы"},
        {"hills","Холмы"},
        {"desert","Пустыня"},
        {"plains","Равнины"},
        {"tundra","Тундра"},
        {"taiga","Тайга"},
        {"temperate_forest","Умеренный лес"},
        {"jungle","Джунгли"},
        {"tropical_rainforest","Тропический лес"},
        {"savanna","Саванна"},
        {"forest","Лес"},
        {"grassland","Степь"},
    };
    for (const auto& [key,name] : names)
        if (key == terrain) return name;
    return terrain.empty() ? "--" : terrain;
}

std::string_view resourceDisplayName(std::string_view key) {
    constexpr std::pair<std::string_view,std::string_view> names[] = {
        {"coal","Уголь"},
        {"peat","Торф"},
        {"oil","Нефть"},
        {"natural_gas","Газ"},
        {"uranium","Уран"},
        {"iron_ore","Железная руда"},
        {"alloying_additives","Легир. добавки"},
        {"bauxite","Бокситы"},
        {"copper_ore","Медная руда"},
        {"lead","Свинец"},
        {"nickel","Никель"},
        {"zinc","Цинк"},
        {"gold","Золото"},
        {"silver","Серебро"},
        {"rare_earth_metals","Редкоземы"},
        {"potash","Калийные соли"},
        {"phosphorite","Фосфориты"},
        {"apatite","Апатиты"},
        {"sulfur","Сера"},
        {"rubber","Каучук"},
        {"graphite","Графит"},
        {"mica","Слюда"},
        {"quartz","Кварц"},
        {"steel","Сталь"},
        {"refined_fuel","Топливо"},
        {"chemicals","Химикаты"},
        {"food","Еда"},
        {"fertilizer","Удобрения"},
        {"copper_wire","Медная проволока"},
        {"consumer_goods","Потреб. товары"},
        {"machinery","Оборудование"},
        {"vehicles","Транспорт"},
        {"electronics","Электроника"},
        {"construction_goods","Стройтовары"},
        {"weapons","Оружие"},
        {"infantry_equipment","Пехотное оснащ."},
        {"old_assault_rifles","Старые штурм. винт."},
        {"small_arms_ammo","Патроны"},
        {"old_light_artillery","Старая малая арт."},
        {"light_artillery_ammo","Малые арт. БК"},
        {"old_light_aa_artillery","Старая малая ПВО"},
        {"light_aa_ammo","Малые ПВО БК"},
        {"old_ifv","Старые БМП"},
        {"old_at_missiles","Старые ПТУР"},
        {"autocannon_ammo","БК автопушек"},
        {"artillery_ammo","Арт. боеприпасы"},
        {"tank_ammo","Танк. боеприпасы"},
        {"anti_air_ammo","ПВО боеприпасы"},
        {"spare_parts","Запчасти"},
        {"field_supplies","Полевое снабж."},
        {"ships","Корабли"},
    };
    for (const auto& [resource,name] : names)
        if (resource == key) return name;
    return key;
}

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

    std::deque<int> route;
    std::deque<int> postBattleRoute;
    std::string icon;
    hoi5::CombatStats combat;
    int battle = -1;
    bool attackRoute = false;
    bool retreating = false;
    int manpower = 10000;
    const hoi5::DivisionTemplate* design = &hoi5::divisionTemplates[0];
    hoi5::Stockpile supplies = design->capacity;
    std::map<int,double> airGroundSuppression;

    double consume(std::string_view key,double amount) {
        auto& stock = supplies[key];
        const double used = std::min(stock,amount);
        stock -= used;
        return used;
    }

    void loseStrength(double damage,double equipmentMultiplier = 1.) {
        damage = std::clamp(damage,0.,combat.strength);
        const double ratio = damage/std::max(1.,design->combat.strength);
        manpower = std::max(0,int(std::nearbyint(manpower-design->manpower*ratio)));
        for (auto key : hoi5::DIVISION_EQUIPMENT_LOSS_KEYS)
            consume(key,hoi5::value(design->capacity,key)*ratio*hoi5::DIVISION_EQUIPMENT_STRENGTH_LOSS_MULT*equipmentMultiplier);
        for (auto key : hoi5::DIVISION_COMBAT_STOCK_LOSS_KEYS)
            consume(key,hoi5::value(design->capacity,key)*ratio*hoi5::DIVISION_COMBAT_STOCK_STRENGTH_LOSS_MULT*equipmentMultiplier);
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
    struct EconomySnapshot {
        hoi5::TreasuryFlows flows;
        double population, trade;
    };
    std::optional<EconomySnapshot> economyCurrent, economyPrevious;
    std::chrono::year_month economyMonth{};
    hoi5::Diplomacy diplomacy;
    hoi5::AirLayer air;
    std::vector<hoi5::AirSalvo> salvos;
    std::vector<hoi5::AircraftInterceptorSalvo> aircraftInterceptors;
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

    void propagateWaterOwnership(int land) {
        const auto neighbors = [&](int index,auto visit) {
            const int q = index%size, r = index/size, shift = r%2;
            for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
                {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
            }})
                if (contains(q+dq,r+dr)) visit((r+dr)*size+q+dq);
        };
        std::deque<int> queue;
        const auto enqueue = [&](int index) { if (tiles[index].water) queue.push_back(index); };
        neighbors(land,enqueue);
        std::set<int> seen;
        while (!queue.empty()) {
            const int index = queue.front();
            queue.pop_front();
            if (!seen.insert(index).second) continue;
            sf::Color border;
            int landOwner = -1;
            bool hasLand = false, mixed = false;
            std::map<int,std::pair<int,sf::Color>> waterOwners;
            neighbors(index,[&](int neighbor) {
                const auto& tile = tiles[neighbor];
                if (!tile.water) {
                    mixed |= hasLand && landOwner != tile.owner;
                    if (!hasLand) landOwner = tile.owner;
                    hasLand = true;
                    if (tile.owner == landOwner) border = tile.border;
                } else if (tile.owner >= 0) {
                    auto& [count,color] = waterOwners[tile.owner];
                    ++count;
                    color = tile.border;
                }
            });
            int owner = mixed ? -1 : landOwner;
            if (!hasLand) {
                int best = 0;
                for (const auto& [country,entry] : waterOwners) {
                    if (entry.first == best) owner = -1;
                    if (entry.first <= best) continue;
                    owner = country;
                    best = entry.first;
                    border = entry.second;
                }
            }
            auto& tile = tiles[index];
            if (owner < 0 || tile.owner == owner) continue;
            tile.owner = owner;
            tile.border = border;
            neighbors(index,enqueue);
        }
    }
    bool canWithdraw(const Division& unit,int owner,int destination) const {
        return owner >= 0 && owner != unit.owner && tiles[destination].owner == unit.owner
            && owner == at(unit.q,unit.r).owner && !diplomacy.hostile(unit.owner,owner);
    }

    template<class CanEnter>
    std::deque<int> landRoute(int origin,int destination,CanEnter canEnter,bool axialHeuristic = false) const {
        std::vector<int> parent(tiles.size(), -1);
        std::vector<double> distance(tiles.size(), std::numeric_limits<double>::infinity());
        using Node = std::tuple<double, int, int>;
        std::priority_queue<Node, std::vector<Node>, std::greater<>> frontier;
        int counter = 0, expansions = 0;
        frontier.emplace(0,counter,origin);
        distance[origin] = 0;
        const int dq = origin%size-destination%size, dr = origin/size-destination/size;
        const int limit = std::min(int(tiles.size()),std::max(2000,90*std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)})));
        while (!frontier.empty() && expansions < limit) {
            const int cell = std::get<2>(frontier.top());
            frontier.pop();
            ++expansions;
            if (cell == destination) break;
            const double cost = distance[cell];
            const int q = cell % size, r = cell / size;
            const int shift = r % 2;
            const std::array<std::pair<int, int>, 6> offsets{{
                {shift, 1}, {shift - 1, 1}, {-1, 0}, {shift - 1, -1}, {shift, -1}, {1, 0}
            }};
            for (const auto [dq, dr] : offsets) {
                if (!contains(q + dq, r + dr)) continue;
                const int next = (r + dr) * size + q + dq;
                if (!canEnter(next)) continue;
                const double nextCost = cost + std::max(1.,tiles[next].movementCost);
                if (nextCost >= distance[next]) continue;
                distance[next] = nextCost;
                parent[next] = cell;
                const int heuristic = axialHeuristic ? hoi5::airHexDistance(next,destination,size) :
                    std::max(std::abs(next%size-destination%size),std::abs(next/size-destination/size));
                frontier.emplace(nextCost+heuristic,++counter,next);
            }
        }
        if (destination != origin && parent[destination] < 0) return {};
        std::deque<int> route;
        for (int step = destination; step != origin; step = parent[step]) route.push_front(step);
        return route;
    }

    bool orderMove(Division& unit, int destination) const {
        if (unit.battle >= 0 || unit.combat.strength <= 0 || unit.organization < unit.maxOrganization * .30) return false;
        if (destination < 0 || destination >= static_cast<int>(tiles.size())) return false;
        const int origin = unit.r * size + unit.q;
        const bool capture = tiles[destination].owner < 0 || diplomacy.hostile(unit.owner,tiles[destination].owner);
        auto route = landRoute(origin,destination,[&](int next) {
            const int owner = tiles[next].owner;
            const bool allowed = owner < 0 ? capture : diplomacy.canTransit(unit.owner,owner)
                || canWithdraw(unit,owner,destination) || (capture && diplomacy.hostile(unit.owner,owner));
            return !tiles[next].water && allowed;
        });
        if (destination != origin && route.empty()) return false;
        unit.route = std::move(route);
        unit.retreating = false;
        unit.attackRoute = tiles[destination].owner >= 0 && diplomacy.hostile(unit.owner,tiles[destination].owner);
        unit.progress = unit.visualProgress = 0;
        return true;
    }

    std::string orderAirDefenseMove(hoi5::AirDefense& unit,int target) const {
        if (target < 0 || target >= int(tiles.size())) return "Нет цели перемещения";
        if (tiles[target].owner != unit.owner) return "ПВО можно двигать только по своей территории";
        if (tiles[target].water) return "ПВО нельзя поставить на воду";
        auto route = landRoute(unit.tile,target,[&](int next) {
            return tiles[next].owner == unit.owner && !tiles[next].water;
        },true);
        if (route.empty() && unit.tile != target) return "Нет маршрута для ПВО";
        unit.route = std::move(route);
        unit.progress = unit.visualProgress = 0.;
        if (unit.tile == target) return "ПВО уже здесь";
        unit.readinessLimit = std::min(unit.readinessLimit,.55);
        return "ПВО выдвигается в "+std::to_string(target%size)+":"+std::to_string(target/size);
    }

    void advanceAirDefense(int hours) {
        for (auto& unit : air.defense) {
            const auto canEnter = [&](int tile) { return tiles[tile].owner == unit.owner && !tiles[tile].water; };
            if (!unit.route.empty() && canEnter(unit.route.front())) {
                const auto& next = tiles[unit.route.front()];
                const double speed = .55*std::max(.35,next.supply);
                unit.progress += hours*speed/(18*std::max(1.,next.movementCost));
                while (!unit.route.empty() && unit.progress >= 1.) {
                    unit.progress -= 1.;
                    unit.tile = unit.route.front();
                    unit.route.pop_front();
                    if (!unit.route.empty() && !canEnter(unit.route.front())) unit.route.clear();
                }
                unit.visualProgress += (std::clamp(unit.progress,0.,1.)-unit.visualProgress)*.35;
            } else unit.route.clear();
            if (unit.route.empty()) unit.progress = unit.visualProgress = 0.;
        }
    }

    hoi5::TreasuryFlows taxedTreasury(int country) const {
        auto flows = treasury[country];
        const auto& policy = diplomacy.countries[country];
        const auto& taxes = policy.taxes;
        flows.companies *= std::clamp(1+.5*(std::clamp(policy.stability,0.,1.)-.72),.65,1.05);
        flows.population *= 1 + .1*taxes[0];
        flows.companies *= 1 + .1*(.65*taxes[1]+.35*taxes[2]);
        return flows;
    }

    hoi5::MarketPlan forecastMarketPlan(int rotation) const {
        if (market.contracts.empty()) return {};
        auto forecastMarket = market;
        auto forecastProfiles = profiles;
        auto forecastStocks = stockpiles;
        forecastMarket.execute(tiles,forecastProfiles,forecastStocks,capacities,rotation,
            [&](int a,int b) { return diplomacy.tradeAllowed(a,b); },
            [&](int a,int b) { return diplomacy.tradePriority(a,b); },
            [&](int i) { return diplomacy.countries[i].externalAccess; },
            [&](int i) { return diplomacy.countries[i].exportLimit; },1.,false);
        return std::move(forecastMarket.last);
    }

    void updateEconomyHistory(int hours,int rotation) {
        if (profiles.empty()) return;
        using namespace std::chrono;
        const year_month_day date{sys_days{year{2000}/1/1}+days{hours/24}};
        const auto month = date.year()/date.month();
        if (economyCurrent && month != economyMonth) economyPrevious = economyCurrent;
        economyMonth = month;
        double trade = 0;
        for (const auto& fill : forecastMarketPlan(rotation).fills) {
            if (fill.buyer == 0) trade -= fill.amount*fill.price;
            if (fill.seller == 0) trade += fill.amount*fill.price;
        }
        economyCurrent = EconomySnapshot{taxedTreasury(0),profiles[0].population,trade};
    }

    void refreshLivingConditions() {
        std::vector<int> land(profiles.size());
        std::vector<double> supply(profiles.size());
        for (const auto& tile : tiles) {
            if (tile.owner < 0 || tile.water) continue;
            ++land[tile.owner];
            supply[tile.owner] += tile.supply;
        }
        for (std::size_t country = 0; country < profiles.size(); ++country) {
            auto& state = diplomacy.countries[country];
            const auto ratio = [&](std::string_view key) {
                double input = 0, output = 0;
                for (const auto& stage : production[country]) {
                    input += hoi5::value(stage.inputs,key);
                    output += hoi5::value(stage.outputs,key);
                }
                return input > 0 ? std::clamp((hoi5::value(stockpiles[country],key)+output)/input,0.,1.25) : 1.25;
            };
            state.food = ratio("food");
            state.goods = ratio("consumer_goods");
            state.foodPrice = market.price("food") / market.base("food");
            state.goodsPrice = market.price("consumer_goods") / market.base("consumer_goods");
            state.supply = supply[country] / std::max(1,land[country]);
        }
    }

    void updateStatus() {
        if (stockpiles.empty()) return;
        auto& stocks = stockpiles.front();
        const auto sum = [&](std::initializer_list<std::string_view> names) {
            double total = 0;
            for (auto name : names) total += stocks.at(name);
            return total;
        };
        const double metals = sum({"iron_ore","copper_ore","bauxite","lead","zinc","nickel",
            "gold","silver","rare_earth_metals","alloying_additives"});
        const double fuel = sum({"coal","oil","natural_gas","peat","uranium"});
        status = {"Player", "Нас: " + formatAmount(profiles.front().population),
            "$" + formatAmount(profiles.front().budget) + ((taxedTreasury(0).balance()+(economyCurrent ? economyCurrent->trade : 0)) >= 0 ? "  +$" : "  −$")
                + formatAmount(std::abs(taxedTreasury(0).balance()+(economyCurrent ? economyCurrent->trade : 0))) + "/мес",
            "Металлы " + formatAmount(metals) + "  Топливо " + formatAmount(fuel) + "  Товары " + formatAmount(stocks.at("consumer_goods")),
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
            treasury.push_back(hoi5::monthlyTreasury(tiles,country,profiles[country].population));
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

    struct ResourceForecast {
        hoi5::Production stages;
        hoi5::Stockpile inputs, outputs, imports, exports, building, army;
    };

    ResourceForecast forecastResources(int owner,int rotation) const {
        ResourceForecast forecast;
        auto stock = stockpiles[owner];
        const auto consume = [&](std::string_view key,double requested,hoi5::Stockpile& category) {
            const double amount = std::min(hoi5::value(stock,key),requested);
            if (amount <= 0) return;
            stock[key] -= amount;
            category[key] += amount;
            forecast.inputs[key] += amount;
        };
        const auto supply = [&](std::string_view key,double requested,hoi5::Stockpile& category) {
            const double amount = std::min(hoi5::freeStorage(capacities[owner],stock,key),requested);
            if (amount <= 0) return;
            stock[key] += amount;
            category[key] += amount;
            forecast.outputs[key] += amount;
        };
        const auto trade = forecastMarketPlan(rotation);
        for (const auto& fill : trade.fills)
            if (fill.buyer == owner) supply(fill.resource,fill.amount,forecast.imports);
        for (const auto& fill : trade.fills)
            if (fill.seller == owner) consume(fill.resource,fill.amount,forecast.exports);
        for (int stage = 0; stage < hoi5::productionStages; ++stage) {
            const auto& planned = production[owner][stage];
            auto& actual = forecast.stages[stage];
            double ratio = 1;
            for (const auto& [key,amount] : planned.inputs)
                if (amount > 0) ratio = std::min(ratio,hoi5::value(stock,key)/amount);
            ratio = std::clamp(ratio,0.,1.);
            for (const auto& [key,amount] : planned.inputs)
                consume(key,amount*(stage == hoi5::upkeep ? 1. : ratio),actual.inputs);
            if (stage != hoi5::upkeep)
                for (const auto& [key,amount] : planned.outputs) supply(key,amount*ratio,actual.outputs);
        }
        for (const auto& [key,amount] : construction.monthlyNeeds(tiles,owner,profiles[owner].budget,stock,
             [&](int tile) { return battles.contains(tile); }))
            consume(key,amount,forecast.building);
        hoi5::Stockpile military;
        for (const auto& unit : divisions) {
            if (unit.owner != owner || unit.combat.strength <= 0) continue;
            const double ratio = supplyRatio(unit);
            if (ratio <= 0) continue;
            const double days = 30*ratio*(unit.battle >= 0 ? hoi5::DIVISION_COMBAT_REINFORCEMENT_MULT : 1.);
            const double maximum = std::max(1.,unit.design->combat.strength);
            const double strength = std::clamp(maximum-unit.combat.strength,0.,hoi5::DIVISION_REINFORCEMENT_STRENGTH_PER_DAY*days);
            for (const auto& [key,capacity] : unit.design->capacity)
                military[key] += std::min(std::max(0.,capacity-hoi5::value(unit.supplies,key)),capacity*.18*days);
            if (unit.battle >= 0)
                for (const auto& [key,amount] : unit.design->use) military[key] += amount*720;
            for (auto key : hoi5::DIVISION_EQUIPMENT_LOSS_KEYS)
                military[key] += hoi5::value(unit.design->capacity,key)*strength/maximum*.42;
        }
        for (const auto& [key,amount] : military) consume(key,amount,forecast.army);
        return forecast;
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

    bool joinBattle(int target,int index) {
        auto& unit = divisions[index];
        if (unit.battle >= 0 || tiles[target].water || !diplomacy.hostile(unit.owner,tiles[target].owner))
            return false;
        auto [entry,created] = battles.try_emplace(target,hoi5::Battle{unit.owner,tiles[target].owner});
        auto& battle = entry->second;
        if (created) battle.origin = unit.r*size+unit.q;
        const auto enroll = [&](int participant,bool attacking) {
            auto& member = divisions[participant];
            member.postBattleRoute.clear();
            if (attacking) {
                const auto step = std::ranges::find(member.route,target);
                if (step != member.route.end())
                    member.postBattleRoute.assign(std::next(step),member.route.end());
            }
            member.route.clear();
            member.attackRoute = attacking;
            member.retreating = false;
            member.battle = target;
            member.progress = member.visualProgress = 0.;
            (attacking ? battle.attackers : battle.defenders).push_back(participant);
        };
        if (created) {
            for (int i = 0; i < int(divisions.size()); ++i) {
                auto& defender = divisions[i];
                if (defender.battle >= 0 || defender.r*size+defender.q != target || defender.combat.strength <= 0
                    || !diplomacy.hostile(defender.owner,battle.attacker)) continue;
                enroll(i,false);
            }
        }
        enroll(index,unit.owner == battle.attacker);
        return true;
    }

    bool battleCollateral(int target,int hours,int active,double organizationDamage,double strengthDamage) {
        if (hours <= 0 || active <= 0) return false;
        auto& tile = tiles[target];
        std::array<double,hoi5::buildingCount> weights{};
        for (const auto& spec : hoi5::constructionSpecs) {
            const double coverage = tile.buildings[spec.building].area;
            if (coverage > 0) weights[spec.building] = std::max(.02,coverage);
        }
        const auto available = std::ranges::count_if(weights,[](double weight) { return weight > 0; });
        if (!available) return false;
        const double intensity = std::clamp(organizationDamage/18.+strengthDamage/7.,0.,1.);
        const double activeFactor = std::min(1.,active/6.);
        const double damage = hours*std::min(.0022,.0008*(.45+intensity*.85)*(.65+activeFactor));
        const auto pick = [&] {
            return static_cast<hoi5::Building>(std::discrete_distribution<int>(weights.begin(),weights.end())(combatRandom));
        };
        const auto primary = pick();
        bool changed = construction.damageBuilding(tile,target,primary,damage);
        if (available > 1 && std::uniform_real_distribution<double>(0.,1.)(combatRandom) < .25+intensity*.25) {
            weights[primary] = 0;
            changed |= construction.damageBuilding(tile,target,pick(),damage*.45);
        }
        return changed;
    }

    bool airSuperioritySupport(int owner,int tile) const {
        return std::ranges::any_of(air.wings,[&](const auto& wing) {
            const int type = wing.missionType(2);
            return wing.owner == owner && wing.readyCount() > 0 && wing.airSuperiority &&
                type >= 0 && airWingCanReach(wing,tile,type) &&
                (wing.operationArea.empty() || std::ranges::find(wing.operationArea,tile) != wing.operationArea.end());
        });
    }

    double breakthroughAirBonus(const hoi5::Battle& battle,int owner,int tile) const {
        const bool suppressed = std::ranges::any_of(battle.defenders,[&](int index) {
            const auto& unit = divisions[index];
            return unit.combat.strength > 0 && diplomacy.hostile(unit.owner,owner) &&
                unit.airGroundSuppression.contains(owner);
        });
        return (suppressed ? .10 : 0.)+(airSuperioritySupport(owner,tile) ? .05 : 0.);
    }

    bool advanceBattles(int hours,bool& infrastructureChanged) {
        bool changed = false;
        for (auto it = battles.begin(); it != battles.end();) {
            const int target = it->first;
            auto& battle = it->second;
            for (const auto* side : {&battle.attackers,&battle.defenders})
                for (int index : *side) {
                    auto& markers = divisions[index].airGroundSuppression;
                    for (auto& [owner,remaining] : markers) remaining -= hours;
                    std::erase_if(markers,[](const auto& marker) { return marker.second <= 0; });
                }
            const auto alive = [&](int i) { return divisions[i].combat.strength > 0; };
            const auto ready = [&](int i) { return alive(i) && divisions[i].organization > 0; };
            std::set<int> origins;
            for (int i : battle.attackers) {
                const int origin = divisions[i].r*size+divisions[i].q;
                if (alive(i) && hoi5::airHexDistance(origin,target,size) == 1) origins.insert(origin);
            }
            const double width = 80+40*std::max(0,int(origins.size())-1);
            battle.width = width;
            const auto active = [&](std::vector<int>& side) {
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
                    if (unit.combat.recovering && unit.organization >= unit.maxOrganization*.30)
                        unit.combat.recovering = false;
                    if (!ready(i) || unit.combat.recovering || share < .6) {
                        unit.combat.widthEfficiency = 1.;
                        continue;
                    }
                    unit.combat.widthEfficiency = share;
                    remaining = std::max(0.,remaining-unit.combat.width*share);
                    result.push_back(i);
                }
                return result;
            };
            const bool war = diplomacy.hostile(battle.attacker,battle.defender);
            if (war) {
                const auto recoverReserves = [&](const auto& side,const auto& front) {
                    for (int i : side)
                        if (alive(i) && std::ranges::find(front,i) == front.end()) recover(divisions[i],hours,.25);
                };
                recoverReserves(battle.attackers,active(battle.attackers));
                recoverReserves(battle.defenders,active(battle.defenders));
                auto attackers = active(battle.attackers), defenders = active(battle.defenders);
                const int activeCount = int(attackers.size()+defenders.size());
                battle.organizationDamage = {};
                battle.strengthDamage = {};
                const auto attack = [&](const std::vector<int>& side,std::vector<int>& targets,bool defending) {
                    for (int i : side) {
                        if (targets.empty()) break;
                        auto& attacker = divisions[i];
                        auto& defender = divisions[targets[std::uniform_int_distribution<std::size_t>(0,targets.size()-1)(combatRandom)]];
                        const auto& fort = tiles[target].buildings[hoi5::fortification];
                        const double armor = attacker.combat.vehicles;
                        const double bonus = defending && tiles[target].owner == defender.owner
                            ? fort.area*fort.health*(.3+.7*tiles[target].supply)*(.60*(1-armor)+.25*armor) : 0;
                        const double airBonus = defending ? 0. : breakthroughAirBonus(battle,defender.owner,target);
                        const double damage = hoi5::combatDamage(attacker.combat,defender.combat,defending,
                            attacker.attackSupplies(hours),supplyRatio(attacker),bonus,airBonus);
                        const double strengthLoss = std::min(defender.combat.strength,damage*.35);
                        defender.organization = std::max(0.,defender.organization-damage);
                        defender.loseStrength(strengthLoss);
                        battle.organizationDamage[defending] += damage;
                        battle.strengthDamage[defending] += strengthLoss;
                    }
                };
                attack(attackers,defenders,true);
                attack(defenders,attackers,false);
                infrastructureChanged |= battleCollateral(target,hours,activeCount,
                    battle.organizationDamage[0]+battle.organizationDamage[1],
                    battle.strengthDamage[0]+battle.strengthDamage[1]);
                attackers = active(battle.attackers);
                defenders = active(battle.defenders);
                if (!attackers.empty() && defenders.empty()) battle.advance = std::min(1.25,battle.advance+.035*hours);
                if (!attackers.empty() && !defenders.empty()) battle.advance = std::max(0.,battle.advance-.05*hours);
                battle.activeAttackers = std::move(attackers);
                battle.activeDefenders = std::move(defenders);
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
                unit.combat.widthEfficiency = 1.;
                if (!captured || !alive(i)) {
                    unit.postBattleRoute.clear();
                    unit.attackRoute = false;
                    continue;
                }
                tiles[target].border = at(unit.q,unit.r).border;
                unit.q = target % size;
                unit.r = target / size;
                unit.route = std::move(unit.postBattleRoute);
                unit.postBattleRoute.clear();
                unit.attackRoute = !unit.route.empty() && tiles[unit.route.back()].owner >= 0 &&
                    tiles[unit.route.back()].owner != unit.owner;
                unit.progress = unit.visualProgress = 0.;
            }
            for (int i : battle.defenders) {
                auto& unit = divisions[i];
                unit.battle = -1;
                unit.combat.recovering = false;
                unit.combat.widthEfficiency = 1.;
                unit.postBattleRoute.clear();
                if (!captured || !alive(i)) continue;
                unit.route.clear();
                const int q = unit.q, r = unit.r, shift = r % 2;
                int retreat = -1;
                for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
                    {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
                }}) {
                    if (!contains(q+dq,r+dr)) continue;
                    const int next = (r+dr)*size+q+dq;
                    if (tiles[next].owner != unit.owner || tiles[next].water || defended(next,unit.owner)) continue;
                    if (retreat < 0 || tiles[next].supply > tiles[retreat].supply) retreat = next;
                }
                if (retreat < 0) unit.combat.strength = 0;
                else {
                    unit.route.push_back(retreat);
                    unit.attackRoute = false;
                    unit.retreating = true;
                    unit.organization = unit.progress = unit.visualProgress = 0.;
                }
            }
            if (captured) {
                air.transferTile(target,tiles[target].owner,battle.attacker);
                tiles[target].owner = battle.attacker;
                for (auto& unit : divisions)
                    if (unit.r*size+unit.q == target && unit.owner != battle.attacker && !unit.retreating)
                        unit.combat.strength = 0.;
                propagateWaterOwnership(target);
                changed = bordersChanged = true;
            }
            it = battles.erase(it);
        }
        return changed;
    }

    bool airTargetValid(int owner,int tile,bool strategic) const {
        return strategic ? tiles[tile].owner >= 0 && diplomacy.hostile(owner,tiles[tile].owner) : defended(tile,owner);
    }

    double battlePower(const std::vector<int>& participants) const {
        double score = 0.;
        for (int index : participants) {
            const auto& unit = divisions[index];
            if (unit.combat.strength <= 0) continue;
            const double org = std::clamp(unit.organization/std::max(1.,unit.maxOrganization),0.,1.);
            const double hp = std::clamp(unit.combat.strength/std::max(1.,unit.design->combat.strength),0.,1.);
            score += (unit.combat.softAttack+unit.combat.defense+unit.combat.breakthrough)*.25*(.35+org*.45+hp*.20);
        }
        return score;
    }

    double battleWinRatio(const hoi5::Battle& battle) const {
        const double attack = battlePower(battle.attackers), defense = battlePower(battle.defenders);
        const double ratio = attack/std::max(1.,attack+defense);
        if (battle.attacker == 0) return std::clamp(battle.advance*.55+ratio*.45,0.,1.);
        if (battle.defender == 0) return std::clamp((1-battle.advance)*.55+(1-ratio)*.45,0.,1.);
        return ratio;
    }

    struct HelipadProject { int owner,tile; double progress{}; };
    std::vector<HelipadProject> helipadProjects;

    bool updateFieldHelipads(int hours) {
        const auto distance = [&](int a,int b) { return hoi5::airHexDistance(a,b,size); };
        for (const auto& [front,battle] : battles) {
            const auto start = [&](int owner,const std::vector<int>& participants) {
                if (participants.empty() || std::none_of(air.wings.begin(),air.wings.end(),[&](const auto& wing) {
                    return wing.owner == owner && wing.typeCount(4) > 0;
                })) return;
                for (const auto& base : air.bases)
                    if (base.owner == owner && tiles[base.tile].owner == owner &&
                        tiles[base.tile].buildings[hoi5::airbase].health > .15 && distance(base.tile,front) <= 3) return;
                for (const auto& project : helipadProjects)
                    if (project.owner == owner && distance(project.tile,front) <= 3) return;
                int best = -1;
                std::tuple<double,int,int> rank{};
                for (int i = 0; i < int(tiles.size()); ++i) {
                    const auto& tile = tiles[i];
                    if (tile.owner != owner) continue;
                    const int range = distance(i,front);
                    if (range <= 3 && tile.buildings[hoi5::fieldHelipad].area > 0) return;
                    if (tile.water || tile.supply < .30 || (i != front && !adjacentTiles(i,front))) continue;
                    if (std::any_of(helipadProjects.begin(),helipadProjects.end(),[&](auto p) { return p.tile == i; })) continue;
                    if (std::none_of(participants.begin(),participants.end(),[&](int index) {
                        const auto& unit = divisions[index];
                        return unit.combat.strength > 0 && unit.organization > 0 && distance(unit.r*size+unit.q,i) <= 1;
                    })) continue;
                    bool exposed = i == front;
                    for (int q = std::max(0,i%size-1); q <= std::min(size-1,i%size+1); ++q)
                        for (int r = std::max(0,i/size-1); r <= std::min(size-1,i/size+1); ++r) {
                            const int n = r*size+q;
                            if (adjacentTiles(i,n) && !tiles[n].water && tiles[n].owner >= 0 &&
                                diplomacy.hostile(owner,tiles[n].owner)) exposed = true;
                        }
                    const auto candidate = std::tuple{-(tile.supply-(exposed ? .15 : 0)),range,i};
                    if (best < 0 || candidate < rank) { best = i; rank = candidate; }
                }
                if (best >= 0) helipadProjects.push_back({owner,best});
            };
            start(battle.attacker,battle.attackers);
            start(battle.defender,battle.defenders);
        }
        bool changed = false;
        std::erase_if(helipadProjects,[&](HelipadProject& project) {
            auto& tile = tiles[project.tile];
            if (tile.owner != project.owner) return true;
            const double supply = std::clamp(tile.supply,0.,1.);
            if (supply < .25 || std::none_of(divisions.begin(),divisions.end(),[&](const auto& unit) {
                return unit.owner == project.owner && unit.combat.strength > 0 &&
                    distance(unit.r*size+unit.q,project.tile) <= 1;
            })) return false;
            project.progress += hours*(.45+supply*.55);
            if (project.progress < 18) return false;
            auto& pad = tile.buildings[hoi5::fieldHelipad];
            pad.area = std::min(.18,pad.area+std::max(.06,pad.area));
            changed = true;
            return true;
        });
        return changed;
    }

    bool adjacentTiles(int a,int b) const {
        const int dr = b/size-a/size, dq = b%size-a%size, shift = (a/size)%2;
        return dr == 0 ? std::abs(dq) == 1 : std::abs(dr) == 1 && (dq == shift || dq == shift-1);
    }
    bool airWingCanReach(const hoi5::AirWing& wing,int target,int type = -1) const {
        const auto x = [&](int tile) { return (tile%size+.5*((tile/size)%2))*std::sqrt(3.); };
        double range = type >= 0 ? hoi5::aircraftTypes[type].range : 0.;
        if (type < 0)
            for (int aircraft = 0; aircraft < int(std::size(hoi5::aircraftTypes)); ++aircraft)
                if (wing.typeCount(aircraft) > 0) range = std::max(range,hoi5::aircraftTypes[aircraft].range);
        return std::hypot(x(wing.base)-x(target),1.5*(wing.base/size-target/size))
            <= range*std::sqrt(3.);
    }

    enum class AirAreaEdit { replace, add, remove };

    bool assignAirWingTarget(hoi5::AirWing& wing,int target,AirAreaEdit edit = AirAreaEdit::replace) const {
        if (target < 0 || target >= int(tiles.size()) || wing.count <= 0) return false;
        if (edit != AirAreaEdit::remove && !airWingCanReach(wing,target)) return false;
        if (edit == AirAreaEdit::replace && tiles[target].water) return false;
        if (wing.operationArea.empty() && wing.target >= 0) wing.operationArea.push_back(wing.target);
        if (edit == AirAreaEdit::replace) wing.operationArea = {target};
        else if (edit == AirAreaEdit::remove) std::erase(wing.operationArea,target);
        else if (std::find(wing.operationArea.begin(),wing.operationArea.end(),target) == wing.operationArea.end())
            wing.operationArea.push_back(target);
        wing.target = wing.operationArea.empty() ? -1 : wing.operationArea.back();
        return true;
    }
    double airTargetRepeatFactor(int wingIndex,bool strategic,int tile) const {
        const auto& wing = air.wings[wingIndex];
        double factor = 1.;
        if (wing.lastMissionTarget[strategic] == tile) factor *= .50;
        if (wing.lastMissionTarget[!strategic] == tile) factor *= .62;
        if (wing.missionTargetCooldowns[strategic].contains(tile)) factor *= .38;
        if (wing.missionTargetCooldowns[!strategic].contains(tile)) factor *= .62;
        if (strategic) {
            const auto battle = battles.find(tile);
            const auto enemyPresent = [&](const std::vector<int>& side) {
                return std::ranges::any_of(side,[&](int index) {
                    const auto& division = divisions[index];
                    return division.combat.strength > 0 && diplomacy.hostile(division.owner,wing.owner);
                });
            };
            if (battle != battles.end() &&
                (enemyPresent(battle->second.attackers) || enemyPresent(battle->second.defenders))) factor *= .55;
        }
        for (const auto& salvo : salvos) {
            if (salvo.owner == wing.owner && salvo.sourceWing == wingIndex &&
                salvo.target == tile && salvo.count > 0)
                factor *= salvo.strategic == strategic ? .28 : .58;
        }
        return factor;
    }

    std::pair<double,int> strategicTileScore(const hoi5::AirWing& wing,int cell) const {
        constexpr std::array defaults{hoi5::airbase,hoi5::supplyDepot,hoi5::warehouse,hoi5::fuelStorage,
            hoi5::industry,hoi5::refinery,hoi5::port,hoi5::city,hoi5::village};
        std::vector<hoi5::Building> preferred;
        for (auto tag : wing.targetPriorities)
            for (auto building : hoi5::buildingsForAirTarget(tag))
                if (std::ranges::find(preferred,building) == preferred.end()) preferred.push_back(building);
        const std::span<const hoi5::Building> priorities = preferred.empty() ?
            std::span<const hoi5::Building>(defaults) : std::span<const hoi5::Building>(preferred);
        double score = 0;
        int building = -1;
        for (int i = 0; i < hoi5::buildingCount; ++i) {
            const auto& b = tiles[cell].buildings[i];
            if (b.area <= 0 || b.health <= 0) continue;
            const auto pos = std::ranges::find(priorities,i);
            if (pos == priorities.end() && !wing.targetPriorities.empty()) continue;
            const double priority = pos == priorities.end() ? 1. : 2.8/std::pow(pos-priorities.begin()+1,.35);
            const double value = std::max(.02,b.area)*b.health*hoi5::buildingValue[i]*priority;
            if (value > score) {
                score = value;
                building = i;
            }
        }
        return {score/(1+hoi5::airHexDistance(wing.base,cell,size)*.12),building};
    }

    int selectStrategicTarget(int wingIndex,int* candidateCount = nullptr) const {
        const auto& wing = air.wings[wingIndex];
        const int type = wing.missionType(1);
        if (type < 0) return -1;
        int target = -1, bestDistance = 0;
        double bestScore = 0, bestBaseScore = 0;
        for (int cell : wing.operationArea) {
            if (!airWingCanReach(wing,cell,type) || !airTargetValid(wing.owner,cell,true)) continue;
            const int distance = hoi5::airHexDistance(wing.base,cell,size);
            const double baseScore = strategicTileScore(wing,cell).first;
            if (baseScore <= 0) continue;
            if (candidateCount) ++*candidateCount;
            const double score = baseScore*airTargetRepeatFactor(wingIndex,true,cell);
            if (target < 0 || std::tuple{score,-distance,baseScore} >
                std::tuple{bestScore,-bestDistance,bestBaseScore}) {
                target = cell;
                bestScore = score;
                bestDistance = distance;
                bestBaseScore = baseScore;
            }
        }
        if (target >= 0) return target;
        const int fallback = wing.target >= 0 ? wing.target :
            (wing.operationArea.empty() ? -1 : wing.operationArea.back());
        return fallback >= 0 && airTargetValid(wing.owner,fallback,true) ? fallback : -1;
    }
    double casBattleScore(int wingIndex,int tile,const hoi5::Battle& battle) const {
        const auto& wing = air.wings[wingIndex];
        const auto enemies = [&](const std::vector<int>& side) {
            return std::ranges::count_if(side,[&](int index) {
                const auto& unit = divisions[index];
                return unit.combat.strength > 0 && diplomacy.hostile(unit.owner,wing.owner);
            });
        };
        const auto present = enemies(battle.attackers)+enemies(battle.defenders);
        if (!present) return 0;
        const auto active = enemies(battle.activeAttackers)+enemies(battle.activeDefenders);
        const int distance = hoi5::airHexDistance(wing.base,tile,size);
        return (1+present*.55+active*.35)*airTargetRepeatFactor(wingIndex,false,tile)/(1+distance*.10);
    }

    int selectCasTarget(int wingIndex,int* candidateCount = nullptr) const {
        const auto& wing = air.wings[wingIndex];
        const int type = wing.missionType(0);
        if (type < 0) return -1;
        std::vector<int> candidates;
        const auto addCandidate = [&](int tile) {
            if (airWingCanReach(wing,tile,type) && std::ranges::find(candidates,tile) == candidates.end())
                candidates.push_back(tile);
        };
        for (int tile : wing.operationArea) addCandidate(tile);
        const auto inArea = candidates;
        for (const auto& [tile,battle] : battles) {
            if ((battle.attacker != wing.owner && battle.defender != wing.owner) ||
                std::ranges::find(inArea,tile) == inArea.end()) continue;
            for (const auto* side : {&battle.attackers,&battle.defenders})
                for (int index : *side) {
                    const auto& unit = divisions[index];
                    if (diplomacy.hostile(wing.owner,unit.owner)) addCandidate(unit.r*size+unit.q);
                }
        }
        int target = -1, bestDistance = 0;
        double bestScore = 0;
        for (int tile : candidates) {
            int enemyCount = 0;
            bool planned = false, supporting = false;
            double supportScore = 0;
            for (const auto& unit : divisions) {
                if (unit.owner == wing.owner && unit.attackRoute) {
                    const int destination = unit.battle >= 0 ?
                        (unit.postBattleRoute.empty() ? unit.battle : unit.postBattleRoute.back()) :
                        (unit.route.empty() ? -1 : unit.route.back());
                    planned |= destination == tile;
                }
                if (unit.r*size+unit.q != tile || unit.combat.strength <= 0 ||
                    !diplomacy.hostile(unit.owner,wing.owner)) continue;
                ++enemyCount;
                const auto battle = battles.find(unit.battle);
                if (battle == battles.end() ||
                    (battle->second.attacker != wing.owner && battle->second.defender != wing.owner)) continue;
                supporting = true;
                supportScore = std::max(supportScore,casBattleScore(wingIndex,battle->first,battle->second));
            }
            if (!enemyCount) continue;
            if (candidateCount) ++*candidateCount;
            double score = 1+enemyCount*2;
            if (supporting) score += 12+supportScore;
            if (planned) score += 6;
            const int distance = hoi5::airHexDistance(wing.base,tile,size);
            score *= airTargetRepeatFactor(wingIndex,false,tile)/(1+distance*.10);
            if (score > bestScore || (score == bestScore && distance < bestDistance)) {
                target = tile;
                bestScore = score;
                bestDistance = distance;
            }
        }
        return target;
    }

    int launchAirPackage(int wingIndex,bool strategic,int type,int target,int available,bool& infrastructureChanged) {
        auto& wing = air.wings[wingIndex];
        if (target < 0 || !airTargetValid(wing.owner,target,strategic) || !airWingCanReach(wing,target,type)) return 0;
        const auto* weapon = hoi5::missionWeapon(type,strategic);
        if (!weapon) return 0;
        const int distance = hoi5::airHexDistance(wing.base,target,size);
        int danger = 0;
        for (const auto& battery : air.defense) {
            const auto& type = hoi5::defenseClasses[battery.type];
            if (diplomacy.hostile(battery.owner,wing.owner) && type.fireRange > 0
                && hoi5::airHexDistance(battery.tile,target,size) <= type.fireRange+1)
                danger = std::max(danger,type.fireRange);
        }
        const auto launchDistance = hoi5::airMissionLaunchDistance(distance,*weapon,danger,wing.risk,strategic);
        if (!launchDistance) return 0;
        const double launch = *launchDistance;
        const bool flight = weapon->interceptable && launch > std::max(.15,weapon->terminalRange);
        const double progress = std::clamp(1-launch/std::max(.001,double(distance)),0.,1.);
        const int origin = flight ? hoi5::airTileBetween(wing.base,target,size,progress,wing.base) : target;
        const int packageSize = std::max(1,int(std::ceil(wing.readyForType(type)*std::clamp(wing.sortieIntensity,0.,1.)*.25)));
        const int sorties = std::min(available,packageSize);
        if (flight && wing.risk == hoi5::AirRisk::cautious &&
            groundAirDefense(wing,origin,sorties,true,type).hits > 0) {
            wing.abortedHours = std::max(wing.abortedHours,2.);
            return 0;
        }
        const auto defense = groundAirDefense(wing,origin,sorties,false,type);
        if (defense.aborted) return 0;
        const int delivered = flight ? sorties : std::max(0,sorties-defense.hits);
        if (!delivered) return 0;
        interceptAircraft(wingIndex,origin,delivered,type);
        const auto object = strategic ? hoi5::airTargetObject(strategicTileScore(wing,target).second) : std::string_view{};
        hoi5::AirSalvo salvo{wing.owner,origin,target,origin,delivered*hoi5::munitionsPerSortie(*weapon),weapon,
            flight ? launch : 0,flight ? launch : 0,hoi5::weaponInterceptability(*weapon,flight ? launch : 0),
            strategic,wingIndex,object};
        salvo.sourceAircraft = type;
        if (flight) salvos.push_back(salvo);
        else if (!resolveAirImpact(salvo,infrastructureChanged)) return 0;
        wing.lastMissionTarget[strategic] = target;
        auto& targetCooldown = wing.missionTargetCooldowns[strategic][target];
        targetCooldown = std::max(targetCooldown,strategic ? 18. : 6.);
        return sorties;
    }

    int launchAirMission(int wingIndex,bool strategic,int type,int reserved,bool& infrastructureChanged) {
        auto& wing = air.wings[wingIndex];
        if (type < 0 || !wing.enabledMissions[strategic] || wing.missionCooldowns[strategic] > 0)
            return 0;
        int candidates = 0;
        int target = strategic ? selectStrategicTarget(wingIndex,&candidates) : selectCasTarget(wingIndex,&candidates);
        const int packages = std::clamp(candidates,1,5);
        int used = 0;
        for (int i = 0; i < packages && used+reserved < wing.readyForType(type); ++i) {
            if (i > 0) target = strategic ? selectStrategicTarget(wingIndex) : selectCasTarget(wingIndex);
            const int sorties = launchAirPackage(wingIndex,strategic,type,target,wing.readyForType(type)-used-reserved,
                infrastructureChanged);
            if (!sorties) break;
            used += sorties;
        }
        if (used > 0) wing.missionCooldowns[strategic] = std::max(2.,8./std::clamp(wing.sortieIntensity,.1,1.));
        return used;
    }

    void applyAirEquipmentLosses(const hoi5::AirSalvo& salvo,Division& target,double strengthLost) const {
        if (strengthLost <= 0) return;
        const auto& weapon = *salvo.weapon;
        double airRecon = 0, groundRecon = 0;
        if (salvo.sourceWing >= 0 && salvo.sourceWing < int(air.wings.size()) && air.wings[salvo.sourceWing].count > 0)
            airRecon = hoi5::aircraftTypes[salvo.sourceAircraft >= 0 ? salvo.sourceAircraft :
                air.wings[salvo.sourceWing].type].recon;
        int allies = 0;
        for (const auto& unit : divisions) {
            if (unit.owner != salvo.owner || unit.q != target.q || unit.r != target.r || unit.combat.strength <= 0) continue;
            groundRecon += unit.design->recon;
            ++allies;
        }
        if (allies > 0) groundRecon /= allies;
        const double intel = airRecon*2+groundRecon*.25-target.design->camouflage;
        const double focus = std::clamp(.62+std::clamp(weapon.accuracy,0.,1.)*.25+
            std::clamp(weapon.guidance,0.,1.)*.45+intel*.18,.45,1.45);
        const double baseLoss = strengthLost/std::max(1.,target.design->combat.strength);
        for (const auto& [key,weight] : hoi5::airEquipmentTargetProfile(weapon.type)) {
            if (std::ranges::find(hoi5::DIVISION_EQUIPMENT_LOSS_KEYS,key) ==
                std::end(hoi5::DIVISION_EQUIPMENT_LOSS_KEYS)) continue;
            const double capacity = hoi5::value(target.design->capacity,key);
            if (capacity <= 0 || hoi5::value(target.supplies,key) <= 0) continue;
            target.consume(key,capacity*std::min(.045,baseLoss*.85*focus*weight));
        }
    }

    bool resolveAirBuildingImpact(const hoi5::AirSalvo& salvo,double scale) {
        const auto& weapon = *salvo.weapon;
        bool changed = false;
        auto& tile = tiles[salvo.target];
        std::array<double,hoi5::buildingCount> weights{};
        std::span<const std::string_view> priorities;
        if (salvo.strategic && salvo.sourceWing >= 0 && salvo.sourceWing < int(air.wings.size()) &&
            air.wings[salvo.sourceWing].count > 0) priorities = air.wings[salvo.sourceWing].targetPriorities;
        const auto preferred = hoi5::airImpactPreferences(salvo,priorities);
        const auto object = hoi5::buildingsForAirTarget(salvo.targetObject);
        const auto weight = [&](int i) {
            const auto& building = tile.buildings[i];
            if (building.area <= 0 || building.health <= 0) return 0.;
            const auto rank = std::ranges::find(preferred,i);
            const double priority = rank == preferred.end() ? 1. : 2.4/std::pow(rank-preferred.begin()+1,.35);
            const double targeted = std::ranges::find(object,i) != object.end() ? 2. : 1.;
            return std::max(.02,building.area)*building.health*hoi5::buildingValue[i]*priority*targeted;
        };
        for (auto building : preferred) weights[building] = weight(building);
        if (std::ranges::none_of(weights,[](double value) { return value > 0; }))
            for (int i = 0; i < hoi5::buildingCount; ++i) weights[i] = weight(i);
        if (std::ranges::none_of(weights,[](double weight) { return weight > 0; })) return false;
        const auto damageBuilding = [&](double scale) {
            const auto type = static_cast<hoi5::Building>(
                std::discrete_distribution<int>(weights.begin(),weights.end())(combatRandom));
            const double damage = hoi5::buildingDamage(salvo,type,scale);
            changed |= construction.damageBuilding(tile,salvo.target,type,damage);
            weights[type] = 0;
        };
        damageBuilding(scale);
        const bool large = weapon.type == "cruise_missile" || weapon.type == "ballistic_missile" ||
            weapon.type == "heavy_strategic_missile";
        const double spread = .20+std::min(.45,std::max(0,salvo.count-1)*.05)+
            ((large || weapon.type == "bunker_buster") ? .20 : 0.);
        const int secondary = std::min(large ? 2 : 1,int(std::ranges::count_if(weights,
            [](double value) { return value > 0; })));
        for (int i = 0; i < secondary; ++i)
            if (std::uniform_real_distribution<double>(0.,1.)(combatRandom) < spread)
                damageBuilding(scale*.42/(i+1));
        return changed;
    }

    bool resolveAirDivisionImpact(const hoi5::AirSalvo& salvo,bool& infrastructureChanged) {
        std::vector<int> targets;
        for (int i = 0; i < int(divisions.size()); ++i) {
            const auto& unit = divisions[i];
            if (unit.r*size+unit.q == salvo.target && unit.combat.strength > 0 && diplomacy.hostile(unit.owner,salvo.owner))
                targets.push_back(i);
        }
        if (targets.empty()) return false;
        auto& target = divisions[targets[std::uniform_int_distribution<std::size_t>(0,targets.size()-1)(combatRandom)]];
        const auto& weapon = *salvo.weapon;
        const double damage = salvo.count*std::max(.05,weapon.warhead)*std::clamp(weapon.accuracy,0.,1.);
        target.organization = std::max(0.,target.organization-damage*.70);
        const double strengthLost = std::min(target.combat.strength,damage*.11);
        target.loseStrength(strengthLost,.45);
        applyAirEquipmentLosses(salvo,target,strengthLost);
        if (damage > 0) {
            auto& remaining = target.airGroundSuppression[salvo.owner];
            remaining = std::max(remaining,6.);
            if (salvo.targetObject.empty()) infrastructureChanged |= resolveAirBuildingImpact(salvo,.16);
        }
        return true;
    }

    bool resolveAirImpact(const hoi5::AirSalvo& salvo,bool& infrastructureChanged) {
        if (salvo.count <= 0 || !airTargetValid(salvo.owner,salvo.target,salvo.strategic)) return false;
        const auto type = salvo.weapon->type;
        const bool divisionTag = type == "unguided_rocket" || type == "guided_missile" || type == "guided_bomb";
        if (salvo.targetObject.empty() && (!salvo.strategic || divisionTag) &&
            resolveAirDivisionImpact(salvo,infrastructureChanged)) return true;
        if (salvo.strategic || !salvo.targetObject.empty()) {
            if (resolveAirBuildingImpact(salvo,1.)) {
                infrastructureChanged = true;
                return true;
            }
        }
        return resolveAirDivisionImpact(salvo,infrastructureChanged);
    }

    int fighterEngagement(hoi5::AirWing& wing,int enemy,int tile,int targets) const {
        const int type = wing.missionType(2);
        const int ready = wing.readyForType(type);
        if (!(wing.intercept || wing.airSuperiority || wing.patrol) ||
            ready <= 0 || wing.cooldown > 0 || wing.abortedHours > 0 || !diplomacy.hostile(wing.owner,enemy) ||
            !airWingCanReach(wing,tile,type) ||
            (!wing.operationArea.empty() && std::ranges::find(wing.operationArea,tile) == wing.operationArea.end()))
            return 0;
        const int capacity = wing.interceptorCapacity();
        wing.interceptorAmmo = wing.interceptorAmmo < 0 ? capacity : std::min(wing.interceptorAmmo,capacity);
        const int sorties = std::max(1,int(std::ceil(ready*std::clamp(wing.sortieIntensity,0.,1.)*.18)));
        return std::min({targets,wing.interceptorAmmo,2*sorties});
    }

    void interceptAircraft(int targetIndex,int exposure,int sorties,int targetType = -1) {
        constexpr auto missile = std::ranges::find(hoi5::munitions,"medium_air_to_air_missile",&hoi5::Munition::key);
        auto& target = air.wings[targetIndex];
        if (targetType < 0) targetType = target.type;
        struct Candidate { int wing,engaged,distance; double chance; };
        std::vector<Candidate> candidates;
        for (int i = 0; i < int(air.wings.size()); ++i) {
            auto& fighter = air.wings[i];
            const int engaged = fighterEngagement(fighter,target.owner,exposure,sorties);
            if (!engaged) continue;
            const double chance = hoi5::fighterAircraftHitChance(fighter.missionType(2),targetType,*missile,target.defensiveHours > 0);
            if (chance >= .03*(fighter.interceptorAmmo <= engaged*2 ? 1.25 : 1.))
                candidates.push_back({i,engaged,hoi5::airHexDistance(fighter.base,exposure,size),chance});
        }
        std::stable_sort(candidates.begin(),candidates.end(),[](const auto& a,const auto& b) {
            return std::tuple{-a.chance,a.distance} < std::tuple{-b.chance,b.distance};
        });
        for (const auto& candidate : candidates) {
            const int engaged = std::min(candidate.engaged,sorties);
            if (!engaged) break;
            auto& fighter = air.wings[candidate.wing];
            fighter.interceptorAmmo -= engaged;
            aircraftInterceptors.push_back({targetIndex,sorties,{fighter.owner,engaged,candidate.chance,1.},targetType});
            sorties -= engaged;
            target.defensiveHours = std::max(target.defensiveHours,2.);
        }
    }

    struct AircraftLosses { int destroyed{}, damaged{}, evaded{}; };

    AircraftLosses applyAircraftHits(hoi5::AirWing& wing,int hits,int aircraft) {
        const auto& type = hoi5::aircraftTypes[aircraft];
        const double survival = hoi5::aircraftSignatures[aircraft].survivability;
        const double destroy = .32*(type.helicopter ? 1.25 : 1.)*std::max(.55,1.15-survival*.55);
        const double damage = .58*(type.helicopter ? 1.12 : 1.)*std::max(.65,1.10-survival*.35);
        AircraftLosses losses;
        for (int i = 0; i < hits; ++i) {
            const double roll = std::uniform_real_distribution<double>(0.,1.)(combatRandom);
            if (roll < destroy) ++losses.destroyed;
            else if (roll < destroy+damage) ++losses.damaged;
            else ++losses.evaded;
        }
        const int destroyed = std::min({wing.readyCount(),wing.typeCount(aircraft),losses.destroyed});
        if (destroyed > 0) wing.changeComposition(aircraft,-destroyed);
        wing.damaged += std::min(wing.readyCount(),losses.damaged);
        return losses;
    }

    double groundAircraftHitChance(const hoi5::AirDefense& battery,const hoi5::AirWing& wing,int tile,
                                  double readinessScale = 1.,double sensorScale = 1.,int type = -1) const {
        if (type < 0) type = wing.type;
        const auto& unit = hoi5::defenseClasses[battery.type];
        const auto& aircraft = hoi5::aircraftSignatures[type];
        const bool helicopter = hoi5::aircraftTypes[type].helicopter;
        const bool low = helicopter || type == 3;
        const bool high = type == 0 || type == 1 || type == 5;
        const int distance = hoi5::airHexDistance(battery.tile,tile,size);
        if (!battery.operational() || distance < unit.minimumRange || distance > unit.fireRange) return 0.;
        const auto [maximum,escape,rcs] = hoi5::interceptorProfiles[battery.type];
        const double range = distance <= escape ? 1. : std::max(.28,1-(distance-escape)/std::max(.001,maximum-escape)*.55);
        const double radar = air.radarSupport(battery.owner,tile,size);
        const double detection = std::clamp(.18+unit.detectionPower*sensorScale*.52+
            aircraft.rcs*rcs*.34+radar-aircraft.stealth*.22,0.,1.);
        const double tracking = std::clamp(unit.trackingQuality*sensorScale*.75+detection*.25,0.,1.);
        double altitude = 1.;
        if (low && battery.type <= 1) altitude = 1.14;
        else if (low && battery.type == 3) altitude = .72;
        else if (high && (battery.type == 2 || battery.type == 3)) altitude = 1.10;
        else if (high && battery.type == 0) altitude = .45;
        const double defensive = wing.defensiveHours > 0 ? (helicopter ? .68 : .48) : (helicopter ? 1.12 : 1.);
        constexpr std::array risk{.82,1.,1.18,1.32};
        double classFactor = 1.;
        if (battery.type == 0 && helicopter) classFactor = 1.85;
        else if (battery.type == 1 && low) classFactor = 1.55;
        else if (battery.type == 3 && helicopter) classFactor = .70;
        return std::clamp(.66*detection*tracking*range*std::max(.42,1-std::max(0.,aircraft.speed-1)*.17)*
            altitude*std::max(.35,1-aircraft.survivability*.42)*defensive*std::clamp(battery.readiness()*readinessScale,0.,1.)*
            std::clamp(battery.health,0.,1.)*risk[static_cast<int>(wing.risk)]*classFactor,0.,1.);
    }

    struct GroundAirResult { int hits{}; bool aborted{}; };

    template<class Add>
    void visitDivisionAirDefense(int owner,int tile,Add add) {
        for (int index = 0; index < int(divisions.size()); ++index) {
            auto& division = divisions[index];
            if (division.owner == owner || division.combat.strength <= 0) continue;
            if (division.r*size+division.q != tile) {
                const auto battle = battles.find(division.battle);
                const bool attacking = battle != battles.end() &&
                    std::ranges::find(battle->second.attackers,index) != battle->second.attackers.end();
                if (attacking ? division.battle != tile :
                    (!division.attackRoute || division.route.empty() || division.route.back() != tile)) continue;
            }
            const double strength = std::clamp(division.combat.strength/std::max(1.,division.design->combat.strength),0.,1.);
            const double org = std::clamp(division.organization/std::max(1.,division.maxOrganization),0.,1.);
            const double readiness = std::clamp((.25+org*.55+supplyRatio(division)*.20)*strength,0.,1.);
            const auto addThreat = [&](int type,std::string_view key,int ammo,int perTarget,double scale) {
                const auto& unit = hoi5::defenseClasses[type];
                const auto channelsAt = [&](int count) { return std::clamp(int(std::nearbyint(count*scale)),1,count); };
                const int channels = std::min({channelsAt(unit.trackingChannels),channelsAt(unit.fireChannels),
                    channelsAt(unit.maxTargets)});
                hoi5::AirDefense threat{division.owner,tile,type,ammo};
                threat.health = strength;
                add(threat,division,key,perTarget,channels,readiness,.75+scale*.25);
            };
            const int missiles = int(hoi5::value(division.supplies,"anti_air_ammo"));
            if (missiles > 0) addThreat(0,"anti_air_ammo",missiles,1,std::clamp(missiles/8.,.45,1.));
            const double guns = hoi5::value(division.supplies,"old_light_aa_artillery");
            const int shells = int(hoi5::value(division.supplies,"light_aa_ammo"));
            if (guns > 0 && shells >= 8)
                addThreat(1,"light_aa_ammo",shells,8,std::clamp(guns/(hoi5::defenseClasses[1].fireChannels*6.),.25,1.));
        }
    }

    GroundAirResult groundAirDefense(hoi5::AirWing& wing,int tile,int sorties,bool preview,int type = -1) {
        if (type < 0) type = wing.type;
        struct Candidate {
            hoi5::AirDefense* battery;
            Division* division;
            std::string_view ammoKey;
            double chance;
            int distance,ammo,perTarget,channels;
        };
        std::vector<Candidate> candidates;
        for (auto& battery : air.defense) {
            if (!diplomacy.hostile(battery.owner,wing.owner)) continue;
            const auto& unit = hoi5::defenseClasses[battery.type];
            const int channels = std::min({unit.trackingChannels,unit.fireChannels,unit.maxTargets});
            const int engaged = std::min({sorties,battery.ammo/unit.interceptors,channels});
            if (engaged <= 0) continue;
            const double chance = groundAircraftHitChance(battery,wing,tile,1.,1.,type);
            if (chance >= .03*(battery.ammo <= engaged*unit.interceptors*2 ? 1.25 : 1.))
                candidates.push_back({&battery,nullptr,{},chance,hoi5::airHexDistance(battery.tile,tile,size),
                    battery.ammo,unit.interceptors,channels});
        }
        visitDivisionAirDefense(wing.owner,tile,[&](const auto& threat,auto& division,auto key,int perTarget,
                                                    int channels,double readiness,double sensors) {
            const double chance = groundAircraftHitChance(threat,wing,tile,readiness,sensors,type);
            if (chance > .03) candidates.push_back({nullptr,&division,key,chance,0,threat.ammo,perTarget,channels});
        });
        std::stable_sort(candidates.begin(),candidates.end(),[](const auto& a,const auto& b) {
            return std::tuple{-a.chance,a.distance} < std::tuple{-b.chance,b.distance};
        });
        GroundAirResult result;
        int engagedTotal = 0;
        AircraftLosses losses;
        for (const auto& candidate : candidates) {
            const int engaged = std::min({preview ? sorties : sorties-result.hits,
                candidate.ammo/candidate.perTarget,candidate.channels});
            if (engaged <= 0) break;
            engagedTotal += engaged;
            if (preview) {
                result.hits += int(engaged*candidate.chance+.5);
                continue;
            }
            const int spent = engaged*candidate.perTarget;
            if (candidate.battery) candidate.battery->ammo -= spent;
            else candidate.division->consume(candidate.ammoKey,spent);
            const int hits = std::binomial_distribution<int>(engaged,candidate.chance)(combatRandom);
            result.hits += hits;
            const auto lost = applyAircraftHits(wing,hits,type);
            losses.destroyed += lost.destroyed;
            losses.damaged += lost.damaged;
            losses.evaded += lost.evaded;
        }
        if (preview || engagedTotal == 0) return result;
        const auto policy = static_cast<int>(wing.risk);
        constexpr std::array threshold{.01,.34,.56,.78}, abortChance{.24,.08,.02,0.};
        const double pressure = (losses.destroyed+losses.damaged*.65+losses.evaded*.25)/sorties;
        result.aborted = !wing.readyCount() ||
            (result.hits > 0 && (wing.risk == hoi5::AirRisk::cautious || pressure >= threshold[policy] ||
            (losses.destroyed > 0 && wing.risk == hoi5::AirRisk::normal && result.hits >= sorties*.25))) ||
            (result.hits == 0 && policy < 3 && std::uniform_real_distribution<double>(0.,1.)(combatRandom) <
                abortChance[policy]*std::min(1.,engagedTotal/double(sorties)));
        if (result.aborted) {
            wing.abortedHours = std::max(wing.abortedHours,6.);
            wing.cooldown = std::max(wing.cooldown,6.);
        } else if (result.hits > 0 || policy < 3) wing.defensiveHours = std::max(wing.defensiveHours,2.);
        return result;
    }

    void launchFighterInterceptors(hoi5::AirSalvo& salvo) {
        constexpr auto interceptor = std::ranges::find(hoi5::munitions,"medium_air_to_air_missile",&hoi5::Munition::key);
        struct Candidate { int wing,engaged,distance; double chance; };
        std::vector<Candidate> candidates;
        for (int i = 0; i < int(air.wings.size()); ++i) {
            auto& wing = air.wings[i];
            const int engaged = fighterEngagement(wing,salvo.owner,salvo.current,salvo.count);
            if (!engaged) continue;
            const int type = wing.missionType(2);
            const auto& aircraft = hoi5::aircraftTypes[type];
            const auto& profile = hoi5::fighterInterceptors[type];
            const double chance = hoi5::fighterSalvoInterceptChance(profile,aircraft.recon,*interceptor,*salvo.weapon);
            if (chance > .03) candidates.push_back({i,engaged,hoi5::airHexDistance(wing.base,salvo.current,size),chance});
        }
        std::stable_sort(candidates.begin(),candidates.end(),[](const auto& a,const auto& b) {
            return std::tuple{-a.chance,a.distance} < std::tuple{-b.chance,b.distance};
        });
        for (const auto& candidate : candidates) {
            air.wings[candidate.wing].interceptorAmmo -= candidate.engaged;
            salvo.inbound.push_back({air.wings[candidate.wing].owner,candidate.engaged,candidate.chance,1.});
            if (salvo.remaining <= 0) salvo.terminalReactionSpent = true;
        }
    }

    double emergencyEvasion(int targetIndex,int engaged,double chance,int type = -1) {
        auto& target = air.wings[targetIndex];
        constexpr std::array thresholds{.16,.34,.56,.82};
        const bool helicopter = hoi5::aircraftTypes[type < 0 ? target.type : type].helicopter;
        const double threshold = thresholds[static_cast<int>(target.risk)]*(helicopter ? .85 : 1.);
        if (engaged <= 0 || target.abortedHours > 0 || target.defensiveHours > 0 || engaged*chance < threshold)
            return chance;
        for (auto& outgoing : salvos) {
            if (outgoing.sourceWing != targetIndex || outgoing.count <= 0) continue;
            const double loss = hoi5::emergencyGuidanceLoss(outgoing.weapon->type);
            if (loss <= 0) continue;
            int remaining = int(outgoing.count*(1-loss)+.5);
            if (remaining == outgoing.count && loss >= .45) --remaining;
            outgoing.count = remaining;
        }
        target.defensiveHours = 2.;
        return chance*(helicopter ? .80 : .74);
    }

    void resolveGroundSalvoDefense(hoi5::AirSalvo& salvo) {
        struct Candidate {
            hoi5::AirDefense* battery;
            Division* division;
            std::string_view ammoKey;
            int type,owner,ammo,perTarget,channels,distance;
            double readiness,health,sensors;
        };
        std::vector<Candidate> defenders;
        for (auto& battery : air.defense) {
            const auto& type = hoi5::defenseClasses[battery.type];
            if (!diplomacy.hostile(battery.owner,salvo.owner) || !battery.operational() || type.fireRange <= 0) continue;
            const int distance = hoi5::airHexDistance(battery.tile,salvo.current,size);
            if (distance < type.minimumRange || distance > type.fireRange) continue;
            defenders.push_back({&battery,nullptr,{},battery.type,battery.owner,battery.ammo,type.interceptors,
                std::min({type.fireChannels,type.trackingChannels,type.maxTargets}),distance,battery.readiness(),battery.health,1.});
        }
        // Python enables ground interception inside fixed battery coverage, even when that battery is empty.
        if (defenders.empty()) return;
        visitDivisionAirDefense(salvo.owner,salvo.current,[&](const auto& threat,auto& division,auto key,int perTarget,
                                                             int channels,double readiness,double sensors) {
            defenders.push_back({nullptr,&division,key,threat.type,threat.owner,threat.ammo,perTarget,channels,0,
                hoi5::defenseClasses[threat.type].readiness*readiness,threat.health,sensors});
        });
        const auto priority = [](const Candidate& candidate) {
            const auto& type = hoi5::defenseClasses[candidate.type];
            return std::tuple{-type.fireRange,-type.trackingQuality*candidate.sensors,candidate.distance};
        };
        std::stable_sort(defenders.begin(),defenders.end(),[&](const auto& a,const auto& b) {
            return priority(a) < priority(b);
        });
        const auto& weapon = *salvo.weapon;
        for (const auto& defender : defenders) {
            if (salvo.count <= 0) break;
            const int engaged = std::min({salvo.count,defender.ammo/defender.perTarget,defender.channels});
            if (engaged <= 0) continue;
            const auto& type = hoi5::defenseClasses[defender.type];
            const auto [maximum,escape,rcsSensitivity] = hoi5::interceptorProfiles[defender.type];
            const double range = defender.distance <= escape ? 1. :
                std::max(.28,1-(defender.distance-escape)/std::max(.001,maximum-escape)*.55);
            const double radar = air.radarSupport(defender.owner,salvo.current,size);
            const double signature = std::clamp(.42+weapon.rcs*rcsSensitivity+weapon.infrared*.20+radar,0.,1.);
            const double tracking = std::clamp((type.trackingQuality*.58+type.detectionPower*.42)*defender.sensors,0.,1.);
            const double probability = std::clamp(salvo.interceptability*(.32+tracking*.68)*range*signature
                *std::max(.42,1-std::max(0.,weapon.terminal-1)*.14)*std::max(.55,1-weapon.maneuver*.28)
                *std::max(.35,1-weapon.difficulty*.38)*std::clamp(defender.readiness,0.,1.)*
                std::clamp(defender.health,0.,1.),0.,1.);
            const int spent = engaged*defender.perTarget;
            const double scarcity = defender.ammo <= spent*2 ? 1.25 : 1.;
            if (probability < .03*scarcity) continue;
            if (defender.battery) defender.battery->ammo -= spent;
            else defender.division->consume(defender.ammoKey,spent);
            salvo.count -= std::binomial_distribution<int>(engaged,probability)(combatRandom);
        }
    }

    bool updateAir(int hours) {
        bool infrastructureChanged = false;
        std::erase_if(aircraftInterceptors,[&](auto& salvo) {
            auto& target = air.wings[salvo.targetWing];
            const int type = salvo.targetAircraft < 0 ? target.type : salvo.targetAircraft;
            if (!target.readyForType(type) || !diplomacy.hostile(salvo.attack.owner,target.owner)) return true;
            salvo.attack.remaining -= hours*2.5;
            if (salvo.attack.remaining > 0) return false;
            const int engaged = std::min(salvo.attack.count,salvo.sorties);
            const double chance = emergencyEvasion(salvo.targetWing,engaged,salvo.attack.chance,type);
            const int hits = std::binomial_distribution<int>(engaged,chance)(combatRandom);
            applyAircraftHits(target,hits,type);
            if (hits > 0) {
                target.abortedHours = std::max(target.abortedHours,6.);
                target.cooldown = std::max(target.cooldown,6.);
            }
            return true;
        });
        for (auto& salvo : salvos) {
            std::erase_if(salvo.inbound,[&](auto& interceptor) {
                interceptor.remaining -= hours*2.5;
                if (interceptor.remaining > 0) return false;
                if (salvo.count > 0 && diplomacy.hostile(interceptor.owner,salvo.owner))
                    salvo.count -= std::binomial_distribution<int>(std::min(salvo.count,interceptor.count),
                        interceptor.chance)(combatRandom);
                return true;
            });
        }
        for (int wingIndex = 0; wingIndex < int(air.wings.size()); ++wingIndex) {
            auto& wing = air.wings[wingIndex];
            wing.abortedHours = std::max(0.,wing.abortedHours-hours);
            wing.defensiveHours = std::max(0.,wing.defensiveHours-hours);
            const int ready = wing.readyCount();
            if (ready <= 0 || (!wing.enabledMissions[0] && !wing.enabledMissions[1] &&
                !wing.intercept && !wing.airSuperiority && !wing.patrol) ||
                tiles[wing.base].owner != wing.owner) continue;
            for (auto& cooldown : wing.missionCooldowns) cooldown = std::max(0.,cooldown-hours);
            for (auto& byTile : wing.missionTargetCooldowns) {
                for (auto it = byTile.begin(); it != byTile.end();) {
                    it->second -= hours;
                    if (it->second <= 0) it = byTile.erase(it);
                    else ++it;
                }
            }
            wing.cooldown = std::max(0.,wing.cooldown-hours);
            if (wing.cooldown > 0 || wing.abortedHours > 0) continue;
            const int casType = wing.missionType(0), strikeType = wing.missionType(1);
            const bool shared = casType >= 0 && casType == strikeType;
            const int strikeReady = wing.readyForType(strikeType);
            int reservedStrike = 0;
            if (shared && strikeReady >= 2 && wing.enabledMissions[0] && wing.enabledMissions[1] &&
                wing.missionCooldowns[1] <= 0 && selectStrategicTarget(wingIndex) >= 0)
                reservedStrike = std::max(1,int(strikeReady*.4));
            const int used = launchAirMission(wingIndex,false,casType,reservedStrike,infrastructureChanged);
            launchAirMission(wingIndex,true,strikeType,shared ? used : 0,infrastructureChanged);
        }
        std::erase_if(salvos,[&](hoi5::AirSalvo& salvo) {
            if (salvo.count <= 0 || !airTargetValid(salvo.owner,salvo.target,salvo.strategic)) return true;
            const auto& weapon = *salvo.weapon;
            const double speed = salvo.remaining <= 1 ? weapon.terminal : weapon.cruise;
            salvo.remaining = std::max(0.,salvo.remaining-hours*speed);
            salvo.current = hoi5::airTileBetween(salvo.origin,salvo.target,size,
                salvo.distance > 0 ? 1-salvo.remaining/salvo.distance : 1);
            if (salvo.remaining <= 0 && salvo.terminalReactionSpent && salvo.inbound.empty()) {
                resolveAirImpact(salvo,infrastructureChanged);
                return true;
            }
            if (salvo.distance > 0) resolveGroundSalvoDefense(salvo);
            if (salvo.count <= 0) return true;
            if (salvo.distance > 0) launchFighterInterceptors(salvo);
            if (salvo.remaining > 0 || !salvo.inbound.empty()) return false;
            resolveAirImpact(salvo,infrastructureChanged);
            return true;
        });
        return infrastructureChanged;
    }

    void advance(int hours) {
        if (hours <= 0) return;
        for (std::size_t country = 0; country < production.size(); ++country) {
            auto& stocks = stockpiles[country];
            profiles[country].budget += taxedTreasury(int(country)).balance()*hours/720.;
            hoi5::runProduction(production[country], stocks, hours, [&](auto key, double amount) {
                stocks[key] += std::min(amount, hoi5::freeStorage(capacities[country], stocks, key));
            });
        }
        diplomacy.fundPrograms(hours,profiles);
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
                }
            },[&](int index) { return battles.contains(index); });
        bool ownershipChanged = false;
        for (int index = 0; index < int(divisions.size()); ++index) {
            auto& unit = divisions[index];
            if (unit.combat.strength <= 0) continue;
            const int here = at(unit.q,unit.r).owner;
            if (unit.retreating && unit.route.empty() && here == unit.owner) unit.retreating = false;
            const bool invalidRetreat = unit.retreating && (unit.route.empty() ||
                tiles[unit.route.front()].water || tiles[unit.route.front()].owner != unit.owner);
            if (invalidRetreat || (!unit.retreating && unit.battle < 0 && here >= 0 &&
                diplomacy.hostile(unit.owner,here))) {
                unit.combat.strength = 0.;
                unit.route.clear();
                continue;
            }
            replenish(unit,hours);
            if (unit.battle >= 0) continue;
            const double ratio = std::clamp(unit.organization / std::max(1., unit.maxOrganization), 0., 1.);
            if (unit.route.empty() || (!unit.retreating && ratio < .30)) {
                recover(unit,hours);
                continue;
            }
            const auto canEnter = [&](int index) {
                const auto& tile = tiles[index];
                if (unit.retreating) return !tile.water && tile.owner == unit.owner;
                return !tile.water && (tile.owner < 0 || diplomacy.canTransit(unit.owner,tile.owner)
                    || diplomacy.hostile(unit.owner,tile.owner) || canWithdraw(unit,tile.owner,unit.route.back()));
            };
            if (!canEnter(unit.route.front())) {
                unit.route.clear();
                unit.progress = unit.visualProgress = 0;
                continue;
            }
            if (!unit.retreating && tiles[unit.route.front()].owner >= 0 &&
                tiles[unit.route.front()].owner != unit.owner && defended(unit.route.front(),unit.owner)) {
                if (joinBattle(unit.route.front(),index)) continue;
            }
            double supplies = 1;
            for (const auto& [key,need] : std::array<std::pair<std::string_view,double>,2>{{
                {"refined_fuel",unit.combat.vehicles*unit.speed*1.8*hours},{"field_supplies",.12*hours}
            }})
                if (need > 0) supplies = std::min(supplies,unit.consume(key,need)/need);
            const double progress = unit.speed * (unit.retreating ? 2. : 1.) *
                std::max(.35, .35 + .65 * ratio) * (.55+.45*supplies)
                * hours / 24. / std::max(1.,tiles[unit.route.front()].movementCost);
            unit.progress += progress;
            unit.organization = std::max(0., unit.organization - 1.4 * progress);
            while (!unit.route.empty() && unit.progress >= 1) {
                const int next = unit.route.front();
                if (!canEnter(next)) {
                    unit.route.clear();
                    break;
                }
                if (!unit.retreating && tiles[next].owner >= 0 && tiles[next].owner != unit.owner && defended(next,unit.owner)) {
                    if (joinBattle(next,index)) break;
                }
                unit.route.pop_front();
                auto& tile = tiles[next];
                if (tile.owner < 0 || diplomacy.hostile(unit.owner,tile.owner)) {
                    tile.border = at(unit.q, unit.r).border;
                    air.transferTile(next,tile.owner,unit.owner);
                    tile.owner = unit.owner;
                    propagateWaterOwnership(next);
                    bordersChanged = true;
                    ownershipChanged = true;
                }
                unit.q = next % size;
                unit.r = next / size;
                unit.progress -= 1;
                unit.visualProgress = std::clamp(unit.progress, 0., 1.);
            }
            if (unit.route.empty() && unit.battle < 0) {
                unit.retreating = false;
                unit.attackRoute = false;
                unit.progress = unit.visualProgress = 0;
            }
        }
        updateTraining(hours);
        bool battleDamage = false;
        ownershipChanged |= advanceBattles(hours,battleDamage);
        const bool helipadBuilt = updateFieldHelipads(hours);
        air.advanceDefenseReplacements(tiles,capitals,hours,[&](int tile) { return battles.contains(tile); },
            [&](int tile,int type) {
                diplomacy.record("ПВО восстановлено: "+std::string(hoi5::defenseClasses[type].key)+" ("+
                    std::to_string(tile%size)+", "+std::to_string(tile/size)+")");
            });
        air.replenishDefenseAmmo(tiles,stockpiles,hours);
        advanceAirDefense(hours);
        const bool airDamage = updateAir(hours);
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
        if ((airDamage || battleDamage || built || helipadBuilt || ownershipChanged || populationTick) && !capitals.empty()) {
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

int tileAtWorldPosition(int size,sf::Vector2f point) {
    const int row = int(std::floor((center(0,0).y-point.y)/(1.5f*radius)));
    for (int r = std::max(0,row-1); r <= std::min(size-1,row+1); ++r) {
        const int column = int(std::floor((point.x-center(0,r).x)/spacing));
        for (int q = std::max(0,column-1); q <= std::min(size-1,column+1); ++q) {
            const auto offset = point-center(q,r);
            const float x = std::abs(offset.x), y = std::abs(offset.y);
            if (x <= spacing/2 && y <= radius-x*radius/spacing) return r*size+q;
        }
    }
    return -1;
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
    world.updateEconomyHistory(0,0);
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

sf::Color blendMapColors(sf::Color a,sf::Color b,double amount) {
    const auto channel = [&](int first,int second) {
        return static_cast<std::uint8_t>(first*(1-amount)+second*amount);
    };
    return {channel(a.r,b.r),channel(a.g,b.g),channel(a.b,b.b)};
}

std::span<const std::string_view> resourceCategoryKeys(int category) {
    static constexpr std::string_view raw[]{"coal","oil","natural_gas","peat","uranium","iron_ore",
        "copper_ore","bauxite","lead","zinc","nickel","gold","silver","rare_earth_metals",
        "alloying_additives","sulfur","potash","phosphorite","apatite","rubber","graphite","mica","quartz"};
    static constexpr std::string_view semi[]{"steel","refined_fuel","chemicals","food","fertilizer","copper_wire"};
    static constexpr std::string_view finished[]{"consumer_goods","machinery","vehicles","electronics",
        "construction_goods","weapons","infantry_equipment","old_assault_rifles","small_arms_ammo",
        "old_light_artillery","light_artillery_ammo","old_light_aa_artillery","light_aa_ammo","old_ifv",
        "old_at_missiles","autocannon_ammo","artillery_ammo","tank_ammo","anti_air_ammo","spare_parts",
        "field_supplies","ships"};
    if (category == 1) return semi;
    if (category == 2) return finished;
    return raw;
}

bool isRawMapResource(std::string_view key) {
    const auto semi = resourceCategoryKeys(1), finished = resourceCategoryKeys(2);
    return std::ranges::find(semi,key) == semi.end() && std::ranges::find(finished,key) == finished.end();
}

std::string resourceAmountLabel(double amount) {
    std::ostringstream label;
    const double magnitude = std::abs(amount);
    label << std::fixed;
    if (magnitude >= 1e6) label << std::setprecision(1) << amount/1e6 << 'M';
    else if (magnitude >= 1000) label << std::setprecision(1) << amount/1000 << 'K';
    else label << std::setprecision(0) << amount;
    return label.str();
}

std::string resourceDurationLabel(double stock,double output,double input) {
    if (input <= output) return "--";
    if (stock <= 0) return "0 дн.";
    const double months = stock/(input-output);
    if (months > 60) return "> 5 лет";
    const int days = std::max(1,int(std::ceil(months*30)));
    if (days < 7) return std::to_string(days)+" дн.";
    const int weeks = (days+6)/7;
    if (weeks < 5) return std::to_string(weeks)+" нед.";
    const int wholeMonths = int(std::ceil(months));
    if (wholeMonths < 12) return std::to_string(wholeMonths)+" мес.";
    if (months < 24) return "1 год";
    return std::to_string(int(std::ceil(months/12)))+" г.";
}

double tileResourceOutput(const Tile& tile,std::string_view resource) {
    hoi5::Production flows;
    hoi5::accumulateTileProduction(flows,tile,{});
    double amount = 0;
    for (const auto& stage : flows) amount += hoi5::value(stage.outputs,resource);
    return amount;
}

double mapResourceAmount(const Tile& tile,std::string_view resource,bool raw) {
    if (resource.empty()) return 0;
    double amount = 0;
    if (raw) {
        for (const auto& deposit : tile.deposits)
            if (deposit.resource == resource) amount += deposit.mass;
    } else if (tile.owner == 0) amount = tileResourceOutput(tile,resource);
    return amount;
}

sf::Color mapResourceOverlay(double amount,double scale,bool raw,sf::Color base,bool construction) {
    if (amount <= 0) return base;
    const double intensity = std::min(1.,std::log10(amount+1)/std::log10(scale+1));
    const auto glow = raw ? blendMapColors({214,176,82},{255,245,140},intensity) :
        blendMapColors({82,172,214},{154,238,255},intensity);
    return blendMapColors(base,glow,construction ? .18+intensity*.22 : .42+intensity*.36);
}

sf::Color constructionOverlayColor(const World& world,int tile,int spec,double coverage,sf::Color base,bool hovered,
                                   double resourceAmount = 0,double resourceScale = 500000,bool raw = true) {
    if (world.tiles[tile].owner != 0) return blendMapColors(base,{18,22,26},.62);
    const bool allowed = hoi5::Construction::placementBlock(world.tiles,world.size,0,tile,spec,coverage).empty();
    auto overlay = allowed ? blendMapColors({36,154,72},{180,235,86},coverage) : sf::Color(176,58,58);
    double amount = allowed ? .60+coverage*.18 : .66;
    if (hovered) {
        overlay = blendMapColors(overlay,{245,255,150},allowed ? .22 : .08);
        amount = std::min(.86,amount+.10);
    }
    return mapResourceOverlay(resourceAmount,resourceScale,raw,blendMapColors(base,overlay,amount),true);
}

std::string constructionPlacementLabel(double coverage,double planned) {
    const auto percent = [](double amount) {
        return std::to_string(int(std::nearbyint(amount*100)))+"%";
    };
    auto result = percent(coverage);
    if (planned > coverage) result += "+"+percent(planned-coverage);
    return result;
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
    if (mode == "--check-settings-write" && argc == 3)
        return hoi5::saveSettings(argv[2],{37,24,false,2}) ? 0 : 1;
    if (mode == "--check-construction-training") {
        if (resourceCategoryKeys(0).front() != "coal" || resourceCategoryKeys(1).back() != "copper_wire" ||
            resourceCategoryKeys(2).back() != "ships" || isRawMapResource("steel") ||
            resourceAmountLabel(1250) != "1.2K" || resourceDurationLabel(20,10,110) != "6 дн." ||
            resourceDurationLabel(100,10,10) != "--") return 1;
        World placement;
        placement.size = 2;
        placement.tiles.resize(4);
        placement.tiles[0].owner = 0;
        placement.tiles[1].water = true;
        const auto blocked = [&](int spec,double coverage) {
            return hoi5::Construction::placementBlock(placement.tiles,2,0,0,spec,coverage);
        };
        if (!blocked(6,0).empty() || blocked(6,1) != "Уже максимум" ||
            blocked(3,0) != "Нужны твердые залежи" || blocked(4,0) != "Нужна нефть или газ") return 1;
        if (constructionOverlayColor(placement,0,6,0,{100,100,100},false) != sf::Color(61,132,83) ||
            constructionOverlayColor(placement,0,6,1,{100,100,100},false) != sf::Color(150,72,72)) return 1;
        if (constructionPlacementLabel(.20,.35) != "20%+15%" ||
            constructionPlacementLabel(.20,.20) != "20%") return 1;
        placement.tiles[0].deposits = {{"coal",.1,200000},{"coal",.3,300000}};
        const double coal = mapResourceAmount(placement.tiles[0],"coal",true);
        if (mapResourceOverlay(coal,500000,true,{100,100,100},false) != sf::Color(220,213,131) ||
            constructionOverlayColor(placement,0,6,0,{100,100,100},false,coal) != sf::Color(138,177,105) ||
            mapResourceAmount(placement.tiles[0],"oil",true) != 0 ||
            mapResourceOverlay(180,180,false,{100,100,100},false) != sf::Color(142,207,220)) return 1;
        hoi5::Construction repairs;
        repairs.queues.resize(1);
        std::vector<Tile> sites(1);
        sites[0].owner = 0;
        auto& city = sites[0].buildings[hoi5::city];
        city.area = .25;
        World collateral;
        collateral.tiles = sites;
        collateral.construction.queues.resize(1);
        if (!collateral.battleCollateral(0,6,3,9,1.75) ||
            std::abs(collateral.tiles[0].buildings[hoi5::city].health-.993997) > 1e-9 ||
            collateral.construction.queues[0].size() != 1) return 1;
        repairs.damageBuilding(sites[0],0,hoi5::city,.25);
        repairs.damageBuilding(sites[0],0,hoi5::city,.25);
        const auto& queue = repairs.queues[0];
        if (queue.size() != 1 || !queue.front().repair || queue.front().from != .75 ||
            std::abs(queue.front().work-23.55370875) > 1e-8) return 1;
        std::vector<hoi5::StartingProfile> funding(1);
        std::vector<hoi5::Stockpile> materials(1);
        const auto runRepair = [&](int hours) {
            return repairs.advance(sites,funding,materials,hours,[](int,int,hoi5::Building) {},
                [](int) { return false; });
        };
        using Status = hoi5::ConstructionStatus;
        if (runRepair(720) || queue.front().status != Status::waitingMoney ||
            queue.front().missingMoney != queue.front().money) return 1;
        funding[0].budget = 1e7;
        if (runRepair(720) || queue.front().status != Status::waitingResources ||
            queue.front().missingResources.empty() || city.health != .5) return 1;
        const double paidBudget = funding[0].budget;
        for (const auto& [key,amount] : queue.front().resources) materials[0][key] = amount*2;
        if (!runRepair(720) || city.health <= .5 || city.health >= .75 ||
            queue.front().status != Status::repairing || funding[0].budget != paidBudget ||
            !runRepair(7200) || city.health != 1. || !queue.empty() || city.area != .25) return 1;
        auto generated = generateWorld(50,2,823558,1);
        const int capital = generated.capitals[0];
        if (!generated.construction.enqueue(generated.tiles,generated.size,0,capital,8).empty()) return 1;
        auto grouped = generated.construction.queues[0];
        grouped.push_back(grouped.front());
        grouped.push_back(grouped.front());
        grouped.back().spec = 7;
        auto groups = hoi5::Construction::groups(grouped);
        if (groups.size() != 2 || groups.front().end != 2 ||
            !hoi5::Construction::moveGroup(grouped,groups,1,-1) || grouped.front().spec != 7) return 1;
        groups = hoi5::Construction::groups(grouped);
        grouped.front().paid = true;
        if (hoi5::Construction::moveGroup(grouped,groups,0,1)) return 1;
        for (int i = 0; i < 720 && !generated.construction.queues[0].empty(); i += 6) generated.advance(6);
        if (generated.tiles[capital].buildings[hoi5::supplyDepot].area <= 0) return 1;
        const auto units = generated.divisions.size();
        if (generated.train(0,capital,0) != "Подготовка начата") return 1;
        generated.updateTraining(World::trainingHours(hoi5::divisionTemplates[0]));
        return generated.divisions.size() == units+1 && generated.divisions.back().organization == 50 ? 0 : 1;
    }
    if (mode == "--check-air-rebase") {
        hoi5::AirLayer air;
        std::vector<Tile> tiles(3);
        tiles[1].buildings[hoi5::fieldHelipad].area = .06;
        tiles[2].owner = 1;
        const auto type = std::find_if(std::begin(hoi5::aircraftTypes),std::end(hoi5::aircraftTypes),
            [](const auto& aircraft) { return aircraft.key == "attack_helicopter"; });
        if (type == std::end(hoi5::aircraftTypes)) return 1;
        const int helicopter = int(type-std::begin(hoi5::aircraftTypes));
        air.wings.push_back({0,0,helicopter,4,2,.5});
        air.wings.push_back({0,1,helicopter,2});
        air.wings.push_back({0,0,0,1});
        air.wings[0].operationArea = {2};
        std::string rejection;
        if (air.rebaseWing(tiles,0,1,&rejection) || rejection != "Не хватает вертолетных мест: 3/4" ||
            air.rebaseWing(tiles,0,2,&rejection) || rejection != "Нужна своя клетка" ||
            air.rebaseWing(tiles,2,1,&rejection) || rejection != "База не принимает Легкий истребитель") return 1;
        if (air.wings[0].base != 0 || air.wings[0].target != 2 || air.wings[0].cooldown != .5) return 1;
        air.wings[1].count = 1;
        if (!air.rebaseWing(tiles,0,1)) return 1;
        air.bases.push_back({0,1,1,46,15});
        tiles[1].buildings[hoi5::airbase].health = .15;
        if (air.baseCapacity(tiles,0,1,0) != 0 || air.baseCapacity(tiles,0,1,helicopter) != 5) return 1;
        tiles[1].buildings[hoi5::airbase].health = .16;
        if (air.baseCapacity(tiles,0,1,0) != 46 || air.baseCapacity(tiles,0,1,helicopter) != 15) return 1;
        tiles[1].buildings[hoi5::airbase].health = .15;
        hoi5::AirLayer creation;
        creation.reserves.resize(1);
        creation.reserves[0][helicopter] = 7;
        creation.bases.push_back({0,0,1,46,15});
        const std::array selectedSites{2,1};
        if (creation.creationBase(tiles,0,helicopter,selectedSites,0) != 1) return 1;
        if (creation.createWing(tiles,0,helicopter,6,selectedSites,0) != 0 ||
            creation.wings[0].base != 1 || creation.wings[0].count != 5 ||
            creation.reserves[0][helicopter] != 2) return 1;
        creation.reserves[0][0] = 4;
        if (creation.transferAircraft(tiles,0,0,2) != 0 || !creation.rebaseWing(tiles,0,0)) return 1;
        creation.wings[0].damaged = 1;
        if (creation.transferAircraft(tiles,0,0,2) != 2 || creation.wings[0].readyCount() != 6 ||
            creation.wings[0].typeCount(0) != 2 || creation.wings[0].roleCount(true) != 5 ||
            creation.freeCapacity(tiles,0,0,0) != 44 || creation.reserves[0][0] != 2) return 1;
        const auto& mixed = creation.wings[0];
        if (mixed.missionType(0) != helicopter || mixed.missionType(1) != -1 || mixed.missionType(2) != 0 ||
            mixed.readyForType(helicopter) != 4 || mixed.readyForType(0) != 2) return 1;
        if (creation.transferAircraft(tiles,0,helicopter,-10) != -5 || creation.wings[0].type != 0 ||
            creation.transferAircraft(tiles,0,0,-10) != -1 || creation.wings[0].count != 1 ||
            creation.reserves[0][0] != 3) return 1;
        return air.wings[0].base == 1 && air.wings[0].target == -1 &&
            air.wings[0].operationArea == std::vector<int>{2} && air.wings[0].cooldown == 1 &&
            air.freeCapacity(tiles,0,1,helicopter) == 0 ? 0 : 1;
    }
    if (mode == "--check-field-helipad") {
        World test;
        test.size = 3;
        test.tiles.resize(9);
        for (auto& tile : test.tiles) tile.owner = -1;
        test.tiles[0].owner = 0;
        test.tiles[0].supply = .5;
        test.tiles[1].owner = 1;
        const auto type = std::find_if(std::begin(hoi5::aircraftTypes),std::end(hoi5::aircraftTypes),
            [](const auto& aircraft) { return aircraft.key == "attack_helicopter"; });
        if (type == std::end(hoi5::aircraftTypes)) return 1;
        test.air.wings.push_back({0,0,int(type-std::begin(hoi5::aircraftTypes)),1});
        test.divisions.emplace_back().organization = 100;
        test.battles.emplace(1,hoi5::Battle{0,1,0,{0},{}});
        if (test.updateFieldHelipads(10) || test.helipadProjects.size() != 1 ||
            test.helipadProjects[0].tile != 0 || std::abs(test.helipadProjects[0].progress-7.25) > 1e-12) return 1;
        test.tiles[0].supply = .24;
        if (test.updateFieldHelipads(18) || std::abs(test.helipadProjects[0].progress-7.25) > 1e-12) return 1;
        test.tiles[0].supply = .5;
        return test.updateFieldHelipads(15) && test.helipadProjects.empty() &&
            test.tiles[0].buildings[hoi5::fieldHelipad].area == .06 ? 0 : 1;
    }
    if (mode == "--check-defense-reload") {
        hoi5::AirLayer layer;
        std::vector<Tile> tiles(1);
        std::vector<hoi5::Stockpile> stocks(1);
        stocks[0]["light_aa_ammo"] = 3;
        stocks[0]["anti_air_ammo"] = 10;
        layer.defense.push_back({0,0,1,0});
        auto& battery = layer.defense.front();
        tiles[0].supply = .14;
        layer.replenishDefenseAmmo(tiles,stocks,1);
        if (battery.ammo != 0 || battery.reloadCredit != 0) return 1;
        tiles[0].supply = .20;
        layer.replenishDefenseAmmo(tiles,stocks,1);
        if (battery.ammo != 0 || std::abs(battery.reloadCredit-.8) > 1e-12) return 1;
        layer.replenishDefenseAmmo(tiles,stocks,1);
        if (battery.ammo != 1 || std::abs(battery.reloadCredit-.6) > 1e-12) return 1;
        battery.health = 0;
        layer.replenishDefenseAmmo(tiles,stocks,6);
        if (battery.ammo != 1 || stocks[0].at("light_aa_ammo") != 2) return 1;
        battery.health = 1;
        layer.replenishDefenseAmmo(tiles,stocks,6);
        return battery.ammo == 3 && stocks[0].at("light_aa_ammo") == 0 &&
            stocks[0].at("anti_air_ammo") == 10 ? 0 : 1;
    }
    if (mode == "--check-airbase-capture") {
        World test;
        test.size = 2;
        test.tiles.resize(4);
        test.tiles[1].owner = 1;
        test.tiles[1].buildings[hoi5::airbase].area = .2;
        test.diplomacy.relation(0,1).war = true;
        test.air.bases.push_back({1,1,1,46,15,15600,7600,1.08,false});
        test.air.wings.push_back({1,1,0,8});
        test.air.defense.push_back({1,1,0,10});
        test.air.defense.push_back({1,3,0,10});
        auto& unit = test.divisions.emplace_back();
        unit.speed = 1.35;
        unit.organization = unit.maxOrganization = 100;
        if (!test.orderMove(unit,1)) return 1;
        for (int i = 0; i < 48 && test.tiles[1].owner == 1; ++i) test.advance(1);
        return test.tiles[1].owner == 0 && test.air.bases[0].owner == 0 &&
            test.air.wings[0].count == 0 && test.air.defense.size() == 1 &&
            test.air.defense[0].tile == 3 && test.air.freeCapacity(test.tiles,0,1,0) == 46 ? 0 : 1;
    }
    if (mode == "--check-air-strike") {
        World priorities;
        priorities.size = 2;
        priorities.tiles.resize(4);
        priorities.tiles[1].buildings[hoi5::city].area = .9;
        priorities.tiles[1].buildings[hoi5::industry].area = .2;
        priorities.air.wings.push_back({0,0,1,4});
        auto& prioritized = priorities.air.wings[0];
        if (priorities.strategicTileScore(prioritized,1).second != hoi5::city) return 1;
        prioritized.targetPriorities = {"industry","supply_infrastructure"};
        if (priorities.strategicTileScore(prioritized,1).second != hoi5::industry ||
            priorities.strategicTileScore(prioritized,2).first != 0) return 1;
        const hoi5::AirSalvo prioritizedSalvo{0,0,1,0,2,hoi5::missionWeapon(1,true),1,1,0,true,0,"depot"};
        const auto targets = hoi5::airImpactPreferences(prioritizedSalvo,prioritized.targetPriorities);
        if (targets.size() < 4 || targets[0] != hoi5::supplyDepot || targets[1] != hoi5::warehouse ||
            targets[2] != hoi5::fuelStorage || targets[3] != hoi5::industry) return 1;
        hoi5::AirLayer replacements;
        std::vector<Tile> deployment(2);
        deployment[0].supply = .25;
        deployment[1].supply = 1.;
        double budget = 3e6;
        hoi5::Stockpile materiel{{"steel",80},{"construction_goods",200},{"electronics",40},
            {"machinery",15},{"vehicles",2},{"anti_air_ammo",18}};
        if (replacements.enqueueDefense(0,2,budget,materiel) != "Оплачено производство ПВО: 48 часов" ||
            budget != 5e5 || hoi5::value(materiel,"anti_air_ammo") != 0 ||
            replacements.enqueueDefense(0,2,budget,materiel) != "ПВО уже производится") return 1;
        const std::vector capitals{0};
        const auto completed = [](int,int) {};
        replacements.advanceDefenseReplacements(deployment,capitals,47,[](int) { return false; },completed);
        if (!replacements.defense.empty()) return 1;
        replacements.advanceDefenseReplacements(deployment,capitals,1,[](int) { return true; },completed);
        if (!replacements.defense.empty() || replacements.defenseReplacements.empty()) return 1;
        replacements.advanceDefenseReplacements(deployment,capitals,1,[](int) { return false; },completed);
        if (replacements.defense.size() != 1 || !replacements.defenseReplacements.empty() ||
            replacements.defense[0].tile != 0 || replacements.defense[0].ammo != 18) return 1;
        World moving;
        moving.size = 2;
        moving.tiles.resize(4);
        moving.tiles[1].supply = 1.;
        moving.air.defense.push_back({0,0,2,18});
        auto& mobile = moving.air.defense.front();
        if (moving.orderAirDefenseMove(mobile,1) != "ПВО выдвигается в 1:0" ||
            mobile.route != std::deque<int>{1} || mobile.operational()) return 1;
        moving.advanceAirDefense(32);
        if (mobile.tile != 0 || mobile.operational()) return 1;
        moving.advanceAirDefense(1);
        if (mobile.tile != 1 || !mobile.operational() || mobile.readiness() != .55) return 1;
        moving.orderAirDefenseMove(mobile,0);
        moving.tiles[0].owner = 1;
        moving.advanceAirDefense(1);
        if (mobile.tile != 1 || !mobile.route.empty()) return 1;
        const auto& glide = *hoi5::missionWeapon(1,true);
        World interception;
        interception.size = 2;
        interception.tiles.resize(4);
        interception.tiles[1].owner = 1;
        interception.diplomacy.countries.resize(2);
        interception.diplomacy.relation(0,1).war = true;
        interception.air.wings.push_back({1,1,0,8});
        interception.air.wings[0].intercept = true;
        interception.air.defense.push_back({0,0,2,18});
        auto& battery = interception.air.defense[0];
        auto& fighter = interception.air.wings[0];
        if (std::abs(interception.groundAircraftHitChance(battery,fighter,1)-.13046859994541427) > 1e-9 ||
            interception.groundAircraftHitChance(battery,fighter,0) != 0 ||
            interception.groundAirDefense(fighter,1,4,true).hits != 1 ||
            battery.ammo != 18 || fighter.readyCount() != 8) return 1;
        interception.groundAirDefense(fighter,1,4,false);
        if (battery.ammo != 14) return 1;
        interception.air.defense.clear();
        interception.divisions.resize(1);
        auto& tactical = interception.divisions[0];
        tactical.owner = 0;
        tactical.organization = tactical.maxOrganization = 100;
        tactical.attackRoute = true;
        tactical.route = {1};
        tactical.supplies["light_aa_ammo"] = 8;
        tactical.supplies["anti_air_ammo"] = 0;
        hoi5::AirWing helicopter{1,1,4,8};
        interception.groundAirDefense(helicopter,2,4,false);
        interception.groundAirDefense(helicopter,1,4,true);
        if (hoi5::value(tactical.supplies,"light_aa_ammo") != 8) return 1;
        interception.groundAirDefense(helicopter,1,4,false);
        if (hoi5::value(tactical.supplies,"light_aa_ammo") != 0) return 1;
        tactical.supplies["light_aa_ammo"] = 8;
        hoi5::AirSalvo tacticalTarget{1,0,1,1,3,&glide,1,.5,1.,true};
        interception.resolveGroundSalvoDefense(tacticalTarget);
        if (hoi5::value(tactical.supplies,"light_aa_ammo") != 8) return 1;
        interception.air.defense.push_back({0,1,0,0});
        interception.resolveGroundSalvoDefense(tacticalTarget);
        if (hoi5::value(tactical.supplies,"light_aa_ammo") != 0) return 1;
        interception.air.defense.clear();
        interception.divisions.clear();
        fighter = {1,1,0,8};
        fighter.intercept = true;
        interception.combatRandom.seed(42);
        interception.salvos.push_back({0,0,1,0,3,&glide,1,.5,0,true});
        interception.updateAir(1);
        if (interception.salvos.size() != 1 || interception.salvos[0].inbound.size() != 1 ||
            interception.air.wings[0].interceptorAmmo != 30 || !interception.salvos[0].terminalReactionSpent ||
            std::abs(interception.salvos[0].inbound[0].chance-.237119329869791) > 1e-9) return 1;
        interception.updateAir(1);
        if (!interception.salvos.empty() || interception.air.wings[0].interceptorAmmo != 30) return 1;
        interception.air.wings.push_back({0,0,3,8});
        interception.interceptAircraft(1,1,2);
        if (interception.aircraftInterceptors.size() != 1 ||
            interception.air.wings[0].interceptorAmmo != 28 ||
            interception.air.wings[1].defensiveHours != 2 ||
            std::abs(interception.aircraftInterceptors[0].attack.chance-.28726751470859) > 1e-9) return 1;
        interception.aircraftInterceptors[0].attack.chance = 1.;
        interception.updateAir(1);
        if (!interception.aircraftInterceptors.empty() ||
            interception.air.wings[1].abortedHours != 5 || interception.air.wings[1].readyCount() > 8) return 1;
        const auto& ballistic = *std::ranges::find(hoi5::munitions,"small_ballistic_missile",&hoi5::Munition::key);
        interception.salvos = {{0,0,1,0,1,&glide,1,1,0,true,1},
            {0,0,1,0,5,&glide,1,1,0,true,1},
            {0,0,1,0,5,&ballistic,1,1,0,true,1},
            {1,1,0,1,5,&glide,1,1,0,true,0}};
        auto& evading = interception.air.wings[1];
        evading.abortedHours = evading.defensiveHours = 0;
        if (interception.emergencyEvasion(1,1,.30) != .30 ||
            interception.salvos[0].count != 1) return 1;
        if (std::abs(interception.emergencyEvasion(1,2,.30)-.222) > 1e-9 ||
            interception.salvos[0].count != 0 || interception.salvos[1].count != 3 ||
            interception.salvos[2].count != 5 || interception.salvos[3].count != 5 ||
            evading.defensiveHours != 2) return 1;
        const auto launch = [&](hoi5::AirRisk risk,bool strategic,double distance = 8.) {
            return hoi5::airMissionLaunchDistance(distance,glide,4,risk,strategic).value();
        };
        using Risk = hoi5::AirRisk;
        if (std::abs(launch(Risk::cautious,true)-4.1) > 1e-9 ||
            std::abs(launch(Risk::normal,true)-4.) > 1e-9 ||
            std::abs(launch(Risk::aggressive,true)-1.95) > 1e-9 ||
            std::abs(launch(Risk::allOut,true)-.7) > 1e-9 ||
            std::abs(launch(Risk::cautious,false)-3.1) > 1e-9 ||
            std::abs(launch(Risk::normal,true,.5)-.7) > 1e-9) return 1;
        World test;
        test.size = 2;
        test.tiles.resize(4);
        test.tiles[0].owner = 0;
        test.tiles[1].owner = 1;
        test.tiles[1].buildings[hoi5::industry].area = .3;
        test.diplomacy.countries.resize(2);
        test.diplomacy.relation(0,1).war = true;
        test.air.wings.push_back({0,0,1,8,1,0,{false,true}});
        for (int i = 0; i < 8 && test.tiles[1].buildings[hoi5::industry].health == 1; ++i) test.updateAir(1);
        if (test.tiles[1].buildings[hoi5::industry].health >= 1 || test.air.wings[0].missionCooldowns[1] <= 0) return 1;
        auto& wing = test.air.wings[0];
        wing.operationArea = {1,2};
        test.divisions.resize(3);
        for (auto& unit : test.divisions) {
            unit.owner = 1;
            unit.combat.strength = 100;
        }
        test.divisions[0].q = 1;
        test.divisions[1].r = test.divisions[2].r = 1;
        if (test.selectCasTarget(0) != 2) return 1;
        wing.lastMissionTarget[false] = 2;
        wing.missionTargetCooldowns[false][2] = 6;
        if (test.selectCasTarget(0) != 1) return 1;
        wing.enabledMissions[0] = true;
        test.updateAir(1);
        if (wing.missionCooldowns[0] != 16 || wing.missionCooldowns[1] >= 16) return 1;
        test.tiles[2].owner = 1;
        auto& city = test.tiles[2].buildings[hoi5::city];
        city.area = .3;
        test.divisions[2].combat.strength = 0;
        auto& division = test.divisions[1];
        const double strength = division.combat.strength;
        bool infrastructureChanged = false;
        hoi5::AirSalvo ordered{0,2,2,2,1,hoi5::missionWeapon(1,false),0,0,0,true,-1,"city"};
        if (!test.resolveAirImpact(ordered,infrastructureChanged) || !infrastructureChanged ||
            city.health >= 1 || division.combat.strength != strength) return 1;
        ordered.targetObject = {};
        infrastructureChanged = false;
        const double health = city.health;
        return test.resolveAirImpact(ordered,infrastructureChanged) && infrastructureChanged &&
            division.combat.strength < strength && city.health < health ? 0 : 1;
    }
    if (mode == "--check-supply-parity") {
        std::vector<Tile> tiles(4);
        tiles[0].owner = 1;
        tiles[1].owner = 0;
        tiles[1].movementCost = 2;
        tiles[2].water = true;
        tiles[3].owner = -1;
        const std::vector<int> capitals{0,0};
        hoi5::recalculateSupply(std::span(tiles),2,capitals);
        if (std::abs(tiles[1].supply-.35997) > 1e-12 || tiles[2].supply != 0 || tiles[3].supply != 0) return 1;
        tiles[1].buildings[hoi5::city].area = .1;
        hoi5::recalculateSupply(std::span(tiles),2,capitals);
        return std::abs(tiles[1].supply-.071) < 1e-12 ? 0 : 1;
    }
    if (mode == "--check-path-parity") {
        World test;
        test.size = 3;
        test.tiles.resize(9);
        Division unit;
        unit.organization = unit.maxOrganization = 100;
        if (!test.orderMove(unit,4) || unit.route != std::deque<int>{3,4}) return 1;
        test.tiles[3].movementCost = 2;
        return test.orderMove(unit,4) && unit.route == std::deque<int>{1,4} ? 0 : 1;
    }
    if (mode == "--check-withdrawal") {
        World test;
        test.size = 3;
        test.tiles.resize(9);
        for (auto& tile : test.tiles) tile.water = true;
        for (int q = 0; q < 3; ++q) {
            test.tiles[q].water = false;
            test.tiles[q].owner = q == 2 ? 0 : 1;
        }
        test.diplomacy.countries.resize(2);
        test.diplomacy.relation(0,1).transitGrantors.insert(1);
        auto& unit = test.divisions.emplace_back();
        unit.speed = 1.35;
        unit.organization = unit.maxOrganization = 100;
        if (!test.orderMove(unit,1)) return 1;
        test.diplomacy.relation(0,1).transitGrantors.clear();
        test.advance(1);
        if (!unit.route.empty() || unit.q != 0) return 1;
        if (!test.orderMove(unit,2) || unit.route.size() != 2 || unit.route.front() != 1) return 1;
        for (int i = 0; i < 100 && !unit.route.empty(); ++i) test.advance(1);
        return unit.q == 2 && unit.route.empty() && test.tiles[1].owner == 1 ? 0 : 1;
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
        test.divisions[0].route.push_back(2);
        test.divisions[1].route = {3};
        test.advance(1);
        if (!test.battles.contains(1) || !test.divisions[0].route.empty() ||
            test.divisions[0].postBattleRoute != std::deque<int>{2} ||
            !test.divisions[1].route.empty() || !test.divisions[1].postBattleRoute.empty()) return 1;
        const auto* weapon = hoi5::missionWeapon(1,false);
        test.air.wings.push_back({0,0,1,1});
        const double vehicles = hoi5::value(test.divisions[1].supplies,"vehicles");
        test.salvos.push_back({0,1,1,1,1,weapon,0,0,0,false,0});
        test.updateAir(1);
        if (std::abs(vehicles-hoi5::value(test.divisions[1].supplies,"vehicles")-.4893369624) > 1e-8)
            return 1;
        if (test.breakthroughAirBonus(test.battles.at(1),0,1) != .10 ||
            test.breakthroughAirBonus(test.battles.at(1),1,1) != 0) return 1;
        auto& wing = test.air.wings[0];
        wing.airSuperiority = true;
        if (std::abs(test.breakthroughAirBonus(test.battles.at(1),0,1)-.15) > 1e-9) return 1;
        wing.operationArea = {2};
        if (test.breakthroughAirBonus(test.battles.at(1),0,1) != .10) return 1;
        wing.operationArea = {1};
        test.advance(5);
        if (std::abs(test.breakthroughAirBonus(test.battles.at(1),0,1)-.15) > 1e-9) return 1;
        test.advance(1);
        if (test.breakthroughAirBonus(test.battles.at(1),0,1) != .05) return 1;
        for (int hour = 0; hour < 60 && test.tiles[1].owner != 0; ++hour) test.advance(1);
        auto& retreat = test.divisions[1];
        if (test.tiles[1].owner != 0 || test.divisions[0].q != 1 ||
            test.divisions[0].route != std::deque<int>{2} || retreat.r != 0 ||
            !retreat.retreating || retreat.organization != 0 || retreat.route != std::deque<int>{3}) return 1;
        for (int hour = 0; hour < 60 && retreat.retreating; ++hour) test.advance(1);
        return !retreat.retreating && retreat.combat.strength > 0 && retreat.r == 1 ? 0 : 1;
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
        const double coal = generated.stockpiles[0].at("coal");
        const auto stocksBeforeForecast = generated.stockpiles;
        const auto forecast = generated.forecastResources(0,0);
        if (hoi5::value(forecast.exports,"coal") <= 0 ||
            hoi5::value(forecast.inputs,"coal") < hoi5::value(forecast.exports,"coal") ||
            generated.stockpiles != stocksBeforeForecast || generated.profiles[0].budget != budget) return 1;
        generated.updateEconomyHistory(31*24-1,0);
        if (!generated.economyCurrent || generated.economyCurrent->trade <= 0 ||
            generated.profiles[0].budget != budget || generated.stockpiles[0].at("coal") != coal) return 1;
        const double januaryTrade = generated.economyCurrent->trade;
        generated.updateEconomyHistory(31*24,0);
        if (!generated.economyPrevious || generated.economyPrevious->trade != januaryTrade) return 1;
        generated.market.execute(generated.tiles,generated.profiles,generated.stockpiles,generated.capacities,
            1,[](int a,int b) { return a != b; },[](int,int) { return 0; },[](int) { return true; },[](int) { return 1.; });
        return generated.market.last.fills.size() == 1 && generated.profiles[0].budget > budget ? 0 : 1;
    }
    if (mode == "--check-clock") {
        hoi5::SimulationClock clock;
        const auto step = [](int) {};
        clock.togglePause();
        clock.update(.20,step);
        clock.togglePause();
        clock.togglePause();
        clock.update(.05,step);
        if (clock.elapsedHours != 0) return 1;
        clock.update(.20,step);
        if (clock.elapsedHours != 1) return 1;
        clock.setSpeed(20);
        for (int i = 0; i < 8; ++i) clock.update(.0625,step);
        return clock.speed == 5 && clock.elapsedHours == 49 && clock.marketTickCount == 1 ? 0 : 1;
    }
    if (mode == "--check-hex-picking") {
        for (int r = 0; r < 5; ++r) for (int q = 0; q < 5; ++q)
            if (tileAtWorldPosition(5,center(q,r)) != r*5+q) return 1;
        const auto origin = center(0,0);
        if (tileAtWorldPosition(5,origin+sf::Vector2f(-radius*.95f,0)) != -1) return 1;
        if (tileAtWorldPosition(5,origin+sf::Vector2f(spacing*.51f,0)) != 1) return 1;
        return tileAtWorldPosition(5,origin+sf::Vector2f(0,radius*.99f)) == 0 ? 0 : 1;
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
    const bool constructionSmoke = mode == "--smoke-construction";
    const bool resourcesSmoke = mode == "--smoke-resources";
    const bool wingCreationSmoke = mode == "--smoke-wing-creation";
    if (constructionSmoke || resourcesSmoke || wingCreationSmoke) world = generateWorld(50,2,823558,1);
    if (wingCreationSmoke && world.air.createWing(world.tiles,0,0,2) < 0) return 1;
    constexpr std::array<sf::Vector2u,5> resolutions{{{1024,768},{1200,800},{1366,768},{1600,900},{1920,1080}}};
    const bool generationSmoke = mode == "--smoke-generation";
    const bool smoke = mode == "--smoke-window" || generationSmoke || constructionSmoke || resourcesSmoke || wingCreationSmoke;
    const bool settingsCheck = mode == "--check-settings-window" && argc == 3;
    const auto settingsPath = settingsCheck ? std::filesystem::path(argv[2]) : hoi5::settingsFile(directory);
    const auto legacySettingsPath = directory / "user_settings.json";
    const auto readPath = !settingsCheck && !std::filesystem::exists(settingsPath)
        ? legacySettingsPath : settingsPath;
    auto settings = smoke ? hoi5::Settings{} : hoi5::loadSettings(readPath,int(resolutions.size()));
    const auto createWindow = [&](sf::RenderWindow& target,int resolution,bool fullscreen) {
        const sf::VideoMode video(resolutions[resolution]);
        if (fullscreen) {
            target.create(sf::VideoMode::getDesktopMode(),"HOI5",sf::Style::Default,sf::State::Fullscreen);
            if (target.isOpen()) return true;
        }
        target.create(video,"HOI5");
        return false;
    };
    sf::RenderWindow window;
    bool fullscreen = createWindow(window,settings.resolution,settings.fullscreen);
    const bool requestedFullscreen = settings.fullscreen;
    const int requestedResolution = settings.resolution;
    for (const int fallback : {hoi5::Settings{}.resolution,0}) {
        if (window.isOpen()) break;
        settings.resolution = fallback;
        fullscreen = createWindow(window,fallback,false);
    }
    if (!window.isOpen()) throw std::runtime_error("Could not open HOI5 window");
    if (settingsCheck)
        return settings.soundVolume == 37 && settings.musicVolume == 24 && !fullscreen &&
            window.getSize() == sf::Vector2u{1366,768} ? 0 : 1;
    if (!smoke && (fullscreen != requestedFullscreen || settings.resolution != requestedResolution ||
                   (readPath != settingsPath && std::filesystem::exists(readPath)))) {
        settings.fullscreen = fullscreen;
        if (!hoi5::saveSettings(settingsPath,settings))
            std::cerr << "Could not save HOI5 settings: " << settingsPath << '\n';
    }
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
    bool playing = mode == "--smoke-window" || constructionSmoke || resourcesSmoke || wingCreationSmoke, dragging = false;
    bool setup = false, pauseMenu = false, showSupply = false;
    bool resumable = false;
    enum class MenuPage { main, settings, help };
    MenuPage menuPage = MenuPage::main;
    float musicVolume = settings.musicVolume, soundVolume = settings.soundVolume;
    int resolution = settings.resolution, pendingResolution = resolution;
    bool pendingFullscreen = fullscreen, resolutionOpen = false;
    std::string settingsMessage;
    int activeSlider = -1;
    hoi5::SimulationClock simulation;
    auto& paused = simulation.paused;
    auto& speed = simulation.speed;
    std::vector<int> selectedTiles;
    float hexScroll = 0;
    bool hexResourcesExpanded = false;
    sf::FloatRect hexResourcesToggle;
    int selected = -1, sizeChoice = 2, countries = 4;
    int selectedBattle = -1;
    const auto battleIndicator = [&](int tile,const hoi5::Battle& battle) {
        const auto destination = center(tile%world.size,tile/world.size);
        const auto position = battle.origin >= 0 && battle.origin != tile ?
            (destination+center(battle.origin%world.size,battle.origin/world.size))*.5f :
            destination+sf::Vector2f{0,-radius*.45f};
        const auto pixel = sf::Vector2f(window.mapCoordsToPixel(position,camera));
        return sf::FloatRect(pixel-sf::Vector2f{22,22},{44,44});
    };
    const auto battlePanel = [&] {
        const auto windowSize = sf::Vector2f(window.getSize());
        const sf::Vector2f size{std::min(760.f,windowSize.x-80),std::min(560.f,windowSize.y-110)};
        return sf::FloatRect((windowSize-size)*.5f,size);
    };
    const auto battleClose = [&](sf::FloatRect panel) {
        return sf::FloatRect(panel.position+sf::Vector2f{panel.size.x-36,12},{24,24});
    };
    int difficulty = 1, dropdown = -1;
    bool tradePanel = false;
    int tradeScroll = 0;
    bool diplomacyPanel = false, aircraftPanel = wingCreationSmoke;
    int selectedWing = -1;
    int editingWing = -1;
    int targetingWing = -1;
    constexpr std::pair<std::string_view,std::string_view> airTargetOptions[]{
        {"enemy_units","Войска"},{"supply_infrastructure","Снабжение"},{"infrastructure","Инфраструктура"},
        {"civilian_infrastructure","Гражданская"},{"industry","Заводы"},{"bases","Базы"},
        {"airbases","Аэродромы"},{"air_defense","ПВО/РЛС"}
    };
    constexpr int airTargetMenuHeight = 32+24*int(std::size(airTargetOptions))+8;
    constexpr std::array wingEditDeltas{-10,-1,1,10};
    const auto wingEditRows = [&](int index) {
        std::vector<int> rows;
        if (index < 0 || world.air.reserves.empty()) return rows;
        const auto& wing = world.air.wings[index];
        for (int type = 0; type < int(std::size(hoi5::aircraftTypes)); ++type)
            if (wing.typeCount(type) > 0 || world.air.reserves[wing.owner][type] > 0) rows.push_back(type);
        std::ranges::sort(rows,{},[](int type) { return hoi5::aircraftNames[type]; });
        return rows;
    };
    std::set<int> selectedWings;
    const auto wingCards = [&] {
        std::vector<int> cards;
        for (int i = 0; i < int(world.air.wings.size()); ++i)
            if (world.air.wings[i].owner == 0 && world.air.wings[i].count > 0) cards.push_back(i);
        std::ranges::sort(cards,{},[&](int i) {
            const auto& wing = world.air.wings[i];
            return std::tuple{wing.base,hoi5::aircraftTypes[wing.type].key,i};
        });
        return cards;
    };
    const auto wingGridTop = [&](int count) {
        return int(window.getSize().y)-(selectedWing >= 0 ? 120 : 32)-55*(count/5+1)+7;
    };
    const auto wingCardRect = [&](int index,int count) {
        return sf::FloatRect({20.f+81.f*(index%5),float(wingGridTop(count)+55*(index/5))},{74,48});
    };
    const auto wingCreationBottom = [&] { return wingGridTop(int(wingCards().size()))-42; };
    bool wingCreationOpen = wingCreationSmoke;
    int wingCreationType = -1, wingCreationCount = 1;
    const auto wingCreationRows = [&] {
        std::vector<int> rows;
        if (world.air.reserves.empty()) return rows;
        for (int type = 0; type < int(std::size(hoi5::aircraftTypes)); ++type)
            if (world.air.reserves[0][type] > 0) rows.push_back(type);
        std::ranges::sort(rows,{},[](int type) { return hoi5::aircraftNames[type]; });
        return rows;
    };
    const auto wingCreationLimit = [&](int type) {
        if (type < 0 || world.air.reserves.empty()) return 0;
        const int preferred = selectedWing >= 0 ? world.air.wings[selectedWing].base : -1;
        const int base = world.air.creationBase(world.tiles,0,type,selectedTiles,preferred);
        return base < 0 ? 0 : std::min(world.air.reserves[0][type],world.air.freeCapacity(world.tiles,0,base,type));
    };
    if (wingCreationSmoke) {
        const auto rows = wingCreationRows();
        if (!rows.empty()) wingCreationType = rows.front();
    }
    bool wingRebaseMode = false;
    bool constructionPanel = constructionSmoke, militaryPanel = false;
    int economicPanel = resourcesSmoke ? 2 : 0, resourceScroll = 0;
    std::optional<World::ResourceForecast> resourceForecast;
    int resourceCategory = 0;
    constexpr int resourceRowsTop = 156, resourceRowHeight = 23, resourceVisibleRows = 17;
    constexpr std::array resourceCategories{"Сырьё","Полуфабрикаты","Готовая продукция"};
    hoi5::Stockpile groundResources;
    bool groundResourcesDirty = true;
    const auto resourceKeys = [&] {
        const auto names = resourceCategoryKeys(resourceCategory);
        std::vector<std::string_view> keys(names.begin(),names.end());
        if (resourceCategory == 0) {
            std::set<std::string_view> additional;
            const auto add = [&](const hoi5::Stockpile& values) {
                for (const auto& [key,amount] : values)
                    if (isRawMapResource(key) && std::ranges::find(names,key) == names.end()) additional.insert(key);
            };
            add(world.stockpiles[0]);
            add(groundResources);
            for (const auto& stage : world.production[0]) {
                add(stage.inputs);
                add(stage.outputs);
            }
            keys.insert(keys.end(),additional.begin(),additional.end());
        }
        return keys;
    };
    std::string_view selectedMapResource = resourcesSmoke ? "coal" : "";
    int resourceSources = 0;
    const auto resourceCardClose = [&] {
        return sf::FloatRect({float(window.getSize().x)-42,105},{24,24});
    };
    bool resourceMapDirty = true;
    sf::VertexArray resourceMap(sf::PrimitiveType::Triangles);
    std::vector<double> mapResourceAmounts;
    double mapResourceScale = 500000;
    float economyPanelProgress = 0;
    std::string policyMessage;
    const std::array policyGroups{"Население","Малый и средний бизнес","Крупный бизнес","Рабочие",
        "Сельские жители","Средний класс","Аристократия","Националисты","Социалисты","Либералы","Консерваторы"};
    std::string militaryMessage;
    int buildingSpec = 0;
    bool constructionPlacement = constructionSmoke, constructionQueueExpanded = false;
    bool constructionMapDirty = true;
    sf::VertexArray constructionMap(sf::PrimitiveType::Triangles);
    std::vector<double> constructionCoverage;
    std::vector<sf::String> constructionLabels;
    const auto constructionRows = [&](int groups) {
        const int limit = constructionQueueExpanded ? std::max(4,(int(window.getSize().y)-500)/26+4) : 4;
        return std::min(groups,limit);
    };
    std::string constructionMessage;
    std::string aviationMessage;
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
    const auto hexPanelRect = [&] {
        const auto size = sf::Vector2f(window.getSize());
        const float width = std::min(380.f,std::max(320.f,size.x-32));
        const float top = 174;
        const float height = std::min(560.f,std::max(240.f,size.y-top-78));
        const float bottom = height < 300 ? std::max(12.f,size.y-top-height) : 78.f;
        return sf::FloatRect({size.x-width-16,size.y-bottom-height},{width,height});
    };
    const auto hexCloseRect = [](sf::FloatRect panel) {
        return sf::FloatRect(panel.position+sf::Vector2f(panel.size.x-36,12),{24,24});
    };
    const auto clampCameraPosition = [&](sf::Vector2f position) {
        position.x = std::clamp(position.x,center(0,0).x-spacing/2,
            center(world.size-1,world.size > 1 ? 1 : 0).x+spacing/2);
        position.y = std::clamp(position.y,center(0,world.size-1).y-radius,center(0,0).y+radius);
        return position;
    };
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
    if (!smoke) {
        music.emplace(source / "music");
        music->setVolume(musicVolume);
    }
    const auto openSettings = [&] {
        menuPage = MenuPage::settings;
        pendingResolution = resolution;
        pendingFullscreen = fullscreen;
        resolutionOpen = false;
        settingsMessage.clear();
    };
    const auto updateSlider = [&](int mouseX) {
        const float left = window.getSize().x/2.f-230;
        const float volume = std::clamp((mouseX-left)/460.f,0.f,1.f)*100.f;
        if (activeSlider == 0) soundVolume = volume;
        else if (activeSlider == 1) {
            musicVolume = volume;
            if (music) music->setVolume(volume);
        }
    };
    auto musicCategory = hoi5::economyMusic;
    while (window.isOpen()) {
        const float dt = std::min(.05f, clock.restart().asSeconds());
        while (const auto event = window.pollEvent()) {
            if (event->is<sf::Event::Closed>()) window.close();
            if (event->is<sf::Event::FocusLost>()) { dragging = false; activeSlider = -1; }
            if (const auto* resize = event->getIf<sf::Event::Resized>())
                camera.setSize(sf::Vector2f(resize->size) / zoom);
            if (const auto* key = event->getIf<sf::Event::KeyPressed>()) {
                using Key = sf::Keyboard::Key;
                if (!playing && menuPage == MenuPage::main && !generator.valid() && key->code == Key::Enter) {
                    if (setup) startGame(); else setup = true;
                }
                if (key->code == Key::Escape) {
                    if (menuPage == MenuPage::settings) {
                        if (resolutionOpen) resolutionOpen = false;
                        else { menuPage = MenuPage::main; activeSlider = -1; }
                    } else if (playing && selectedBattle >= 0) selectedBattle = -1;
                    else if (playing) pauseMenu = !pauseMenu;
                    else if (dropdown >= 0) dropdown = -1;
                    else if (!generator.valid()) { setup = false; menuPage = MenuPage::main; }
                }
                if (playing && !pauseMenu && key->code == Key::Space) simulation.togglePause();
                if (playing && key->code >= Key::Num1 && key->code <= Key::Num5)
                    simulation.setSpeed(1 + static_cast<int>(key->code) - static_cast<int>(Key::Num1));
            }
            if (const auto* button = event->getIf<sf::Event::MouseButtonPressed>()) {
                if (((!playing && !generator.valid() && !setup) ||
                    (playing && pauseMenu && menuPage == MenuPage::settings)) && button->button == sf::Mouse::Button::Left) {
                    const int cx = window.getSize().x/2, cy = window.getSize().y/2;
                    const int x = button->position.x, y = button->position.y;
                    if (menuPage == MenuPage::main) {
                        for (int row = 0; row < 6; ++row) {
                            if (!sf::IntRect({cx-150,cy-152+54*row},{300,42}).contains({x,y})) continue;
                            if (row == 0) setup = true;
                            if (row == 1 && resumable) playing = true;
                            if (row == 3) openSettings();
                            if (row == 4) menuPage = MenuPage::help;
                            if (row == 5) window.close();
                        }
                    } else if (menuPage == MenuPage::settings) {
                        if (resolutionOpen) {
                            if (x >= cx+10 && x < cx+230 && y >= cy+80 && y < cy+205)
                                pendingResolution = (y-cy-80)/25;
                            resolutionOpen = false;
                        } else if (x < cx-230 || x >= cx+230) {
                            continue;
                        } else if (std::abs(y-(cy-74)) <= 14 || std::abs(y-(cy-4)) <= 14) {
                            activeSlider = y < cy-39 ? 0 : 1;
                            updateSlider(x);
                        } else if (y >= cy+38 && y < cy+80) {
                            if (x < cx-10) pendingFullscreen = !pendingFullscreen;
                            else if (x >= cx+10) resolutionOpen = true;
                        } else if (y >= cy+111 && y < cy+155) {
                            if (x >= cx+10) menuPage = MenuPage::main;
                            else if (x < cx-10) {
                                if (pendingResolution != resolution || pendingFullscreen != fullscreen) {
                                    const bool previousFullscreen = fullscreen;
                                    fullscreen = createWindow(window,pendingResolution,pendingFullscreen);
                                    if (!window.isOpen()) {
                                        fullscreen = createWindow(window,resolution,previousFullscreen);
                                        window.setVerticalSyncEnabled(true);
                                        settingsMessage = "Не удалось применить разрешение.";
                                        continue;
                                    }
                                    resolution = pendingResolution;
                                    window.setVerticalSyncEnabled(true);
                                    camera.setSize(sf::Vector2f(window.getSize())/zoom);
                                }
                                const bool fallback = pendingFullscreen && !fullscreen;
                                pendingFullscreen = fullscreen;
                                const bool saved = hoi5::saveSettings(settingsPath,{soundVolume,musicVolume,fullscreen,resolution});
                                settingsMessage = !saved ? "Не удалось сохранить настройки." :
                                    fallback ? "Сохранён оконный режим." : "Настройки применены и сохранены.";
                            }
                        }
                        continue;
                    } else if (menuPage == MenuPage::help &&
                               sf::IntRect({cx-150,cy+100},{300,42}).contains({x,y})) {
                        menuPage = MenuPage::main;
                    }
                } else if (!playing && !generator.valid() && setup && button->button == sf::Mouse::Button::Left) {
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
                            if (x < cx-10) startGame(); else if (x >= cx+10) setup = false;
                        }
                    }
                }
                if (playing && pauseMenu && button->button == sf::Mouse::Button::Left) {
                    const int cx = window.getSize().x / 2, cy = window.getSize().y / 2;
                    if (std::abs(button->position.x-cx) < 150) {
                        if (button->position.y >= cy-55 && button->position.y < cy-13) pauseMenu = false;
                        if (button->position.y >= cy && button->position.y < cy+42) openSettings();
                        if (button->position.y >= cy+55 && button->position.y < cy+97) {
                            playing = pauseMenu = setup = false;
                            dragging = false;
                            menuPage = MenuPage::main;
                        }
                    }
                } else if (playing && button->button == sf::Mouse::Button::Left) {
                    const int x = button->position.x, y = button->position.y;
                    const int panel = static_cast<int>(window.getSize().x)-312;
                    if (selectedBattle >= 0 && world.battles.contains(selectedBattle)) {
                        const auto point = sf::Vector2f(button->position);
                        if (battleClose(battlePanel()).contains(point) || !battlePanel().contains(point))
                            selectedBattle = -1;
                        continue;
                    }
                    if (y >= 82) {
                        const auto picked = std::ranges::find_if(world.battles,[&](const auto& item) {
                            return battleIndicator(item.first,item.second).contains(sf::Vector2f(button->position));
                        });
                        if (picked != world.battles.end()) {
                            selectedBattle = picked->first;
                            continue;
                        }
                    }
                    if (y >= 40 && y < 78 && ((x >= 12 && x < 50) || (x >= 57 && x < 95) || (x >= 102 && x < 140))
                        && !world.stockpiles.empty()) {
                        const int panelType = x < 50 ? 3 : x < 100 ? 1 : 2;
                        economicPanel = economicPanel == panelType ? 0 : panelType;
                        if (economicPanel == 2) resourceForecast.reset();
                        militaryPanel = constructionPanel = diplomacyPanel = tradePanel = false;
                    } else if (economicPanel == 2 && !selectedMapResource.empty() &&
                               x >= 720 && y >= 90 && y < 555) {
                        if (resourceCardClose().contains(sf::Vector2f(button->position))) {
                            selectedMapResource = {};
                            resourceMapDirty = constructionMapDirty = true;
                        }
                    } else if (economicPanel == 2 && x >= 20 && x < 710 && y >= 90 && y < 555) {
                        if (y >= 115 && y < 139 && x >= 30 && x < 450) {
                            resourceCategory = (x-30)/140;
                            resourceScroll = 0;
                            selectedMapResource = {};
                            resourceMapDirty = constructionMapDirty = true;
                        } else if (y >= resourceRowsTop && y < resourceRowsTop+resourceVisibleRows*resourceRowHeight) {
                            const auto keys = resourceKeys();
                            const int row = resourceScroll+(y-resourceRowsTop)/resourceRowHeight;
                            if (row < int(keys.size())) {
                                selectedMapResource = keys[row];
                                resourceMapDirty = constructionMapDirty = true;
                            }
                        }
                    } else if (economyPanelProgress > 0 && x < 620*economyPanelProgress &&
                               y >= 94 && y < int(window.getSize().y)-12) {
                        const float localX = x+620*(1-economyPanelProgress);
                        if (localX >= 582 && localX < 610 && y >= 104 && y < 132) economicPanel = 0;
                    } else if (economicPanel && x >= 20 && x < 630 && y >= 90 && y < 550) {
                        if (economicPanel == 3 && y >= 130 && y < 405) {
                            const int group = (y-130)/25;
                            if (x >= 440 && x < 540 && group < 3)
                                policyMessage = world.diplomacy.changeTax(0,group,x < 490 ? -1 : 1);
                            else if (x >= 540 && x < 625)
                                policyMessage = world.diplomacy.changeProgram(0,group,30*24,world.profiles[0]);
                            world.updateStatus();
                        } else if (economicPanel == 3 && y >= 410 && y < 440) {
                            policyMessage = world.diplomacy.changeMarketPolicy(x < 310);
                        }
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
                        constructionPlacement = false;
                        economicPanel = 0;
                        diplomacyPanel = tradePanel = militaryPanel = false;
                    } else if (constructionPanel && x >= 20 && x < 390 && y >= 90 &&
                               y < 414+26*std::max(4,constructionRows(int(hoi5::Construction::groups(world.construction.queues[0]).size())))) {
                        auto& queue = world.construction.queues[0];
                        const auto groups = hoi5::Construction::groups(queue);
                        const int rows = constructionRows(int(groups.size()));
                        const int offset = 26*std::max(4,rows);
                        if (y >= 119 && y < 142 && !queue.empty()) {
                            auto& project = queue.front();
                            project.paused = !project.paused;
                            project.status = project.paused ? hoi5::ConstructionStatus::paused : hoi5::ConstructionStatus::queued;
                        } else if (y >= 148 && y < 148+26*rows && x >= 326 && x < 376) {
                            hoi5::Construction::moveGroup(queue,groups,(y-148)/26,x < 351 ? -1 : 1);
                        } else if (groups.size() > 4 && y >= 148+26*rows && y < 170+26*rows) {
                            constructionQueueExpanded = !constructionQueueExpanded;
                        } else if (y >= 190+offset && y < 351+offset) {
                            const int index = 2*((y-190-offset)/23)+(x >= 205);
                            if (index < int(std::size(hoi5::constructionSpecs))) {
                                buildingSpec = index;
                                constructionMapDirty = true;
                            }
                        } else if (y >= 355+offset && y < 381+offset) {
                            constructionPlacement = !constructionPlacement;
                            constructionMapDirty = true;
                        }
                    } else if (!world.air.reserves.empty() && x >= 10 && x < 430 &&
                               y >= wingGridTop(int(wingCards().size())) && y < int(window.getSize().y)-(selectedWing >= 0 ? 120 : 32)) {
                        const auto cards = wingCards();
                        const int count = int(cards.size());
                        const auto point = sf::Vector2f(button->position);
                        if (wingCardRect(count,count).contains(point)) {
                            editingWing = -1;
                            targetingWing = -1;
                            wingCreationOpen = !wingCreationOpen;
                            aircraftPanel = wingCreationOpen || selectedWing >= 0;
                            const auto rows = wingCreationRows();
                            if (std::ranges::find(rows,wingCreationType) == rows.end())
                                wingCreationType = rows.empty() ? -1 : rows.front();
                        } else for (int i = 0; i < count; ++i) {
                            if (!wingCardRect(i,count).contains(point)) continue;
                            const int wing = cards[i];
                            using Key = sf::Keyboard::Key;
                            const bool shift = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift);
                            if (shift) {
                                if (selectedWings.erase(wing)) {
                                    if (selectedWing == wing) selectedWing = selectedWings.empty() ? -1 : *selectedWings.begin();
                                } else {
                                    selectedWings.insert(wing);
                                    selectedWing = wing;
                                }
                            } else if (selectedWings.size() == 1 && selectedWings.contains(wing)) {
                                selectedWings.clear();
                                selectedWing = -1;
                            } else {
                                selectedWings = {wing};
                                selectedWing = wing;
                                selectedTiles = {world.air.wings[wing].base};
                                selected = -1;
                                hexScroll = 0;
                                hexResourcesExpanded = false;
                            }
                            aircraftPanel = selectedWing >= 0 || wingCreationOpen;
                            editingWing = -1;
                            targetingWing = -1;
                            wingRebaseMode = false;
                            break;
                        }
                    } else if (targetingWing >= 0 && targetingWing == selectedWing && x >= 10 && x < 430 &&
                               y < wingCreationBottom() && y >= wingCreationBottom()-airTargetMenuHeight) {
                        const int offset = y-(wingCreationBottom()-airTargetMenuHeight+32);
                        if (offset >= 0 && offset < 24*int(std::size(airTargetOptions))) {
                            const auto key = airTargetOptions[offset/24].first;
                            const auto& primary = world.air.wings[selectedWing].targetPriorities;
                            const bool enable = std::ranges::find(primary,key) == primary.end();
                            for (int index : selectedWings) {
                                auto& priorities = world.air.wings[index].targetPriorities;
                                if (!enable) std::erase(priorities,key);
                                else if (std::ranges::find(priorities,key) == priorities.end()) priorities.push_back(key);
                            }
                        }
                    } else if (editingWing >= 0 && editingWing == selectedWing && x >= 10 && x < 430 &&
                               y < wingCreationBottom() && y >= wingCreationBottom()-52-34*int(wingEditRows(editingWing).size())) {
                        const auto rows = wingEditRows(editingWing);
                        const int top = wingCreationBottom()-52-34*int(rows.size());
                        const int row = (y-top-40)/34;
                        if (y >= top+40 && row < int(rows.size()) && x >= 250 && x < 410)
                            world.air.transferAircraft(world.tiles,editingWing,rows[row],wingEditDeltas[(x-250)/40]);
                    } else if (wingCreationOpen && x >= 10 && x < 430 && y < wingCreationBottom() &&
                               y >= wingCreationBottom()-96-30*std::max(1,int(wingCreationRows().size()))) {
                        const auto rows = wingCreationRows();
                        const int bottom = wingCreationBottom();
                        const int top = bottom-96-30*std::max(1,int(rows.size()));
                        const int row = (y-top-32)/30;
                        if (y >= top+32 && row < int(rows.size())) wingCreationType = rows[row];
                        const int limit = wingCreationLimit(wingCreationType);
                        if (y >= bottom-36 && y < bottom-12) {
                            using Key = sf::Keyboard::Key;
                            const int step = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift) ? 10 : 1;
                            if (x >= 22 && x < 50) wingCreationCount -= step;
                            else if (x >= 108 && x < 136) wingCreationCount += step;
                            else if (x >= 150 && x < 284 && limit > 1)
                                wingCreationCount = int(std::nearbyint(1+(x-150)/134.*(limit-1)));
                            else if (x >= 308 && x < 418 && limit > 0) {
                                const int preferred = selectedWing >= 0 ? world.air.wings[selectedWing].base : -1;
                                const int wing = world.air.createWing(world.tiles,0,wingCreationType,
                                    wingCreationCount,selectedTiles,preferred);
                                if (wing >= 0) {
                                    selectedWing = wing;
                                    selectedWings = {wing};
                                    selectedTiles = {world.air.wings[wing].base};
                                    selected = -1;
                                    hexScroll = 0;
                                    hexResourcesExpanded = wingRebaseMode = wingCreationOpen = false;
                                }
                            }
                        }
                        wingCreationCount = std::clamp(wingCreationCount,1,std::max(1,limit));
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
                                world.updateEconomyHistory(simulation.elapsedHours,simulation.marketTickCount);
                                world.updateStatus();
                            }
                        }
                    } else if (x >= int(window.getSize().x) - 62 && x < int(window.getSize().x) - 18
                        && y >= int(window.getSize().y) - 62 && y < int(window.getSize().y) - 18) {
                        showSupply = !showSupply;
                        map = makeMap(world, showSupply);
                        resourceMapDirty = true;
                        constructionMapDirty = true;
                    } else if (y >= 92 && y < 164 && x >= panel && x < panel+300) {
                        const int local = x-panel;
                        if (y >= 130 && y < 154) {
                            if (local >= 14 && local < 42) simulation.changeSpeed(-1);
                            if (local >= 48 && local < 86) simulation.togglePause();
                            if (local >= 92 && local < 120) simulation.changeSpeed(1);
                        }
                    } else if (aircraftPanel && selectedWing >= 0 && x >= 116 && x < 416 &&
                               y >= int(window.getSize().y)-111 && y < int(window.getSize().y)-87) {
                        auto& wing = world.air.wings[selectedWing];
                        if (wing.missionType(2) >= 0) {
                            constexpr std::array missions{&hoi5::AirWing::intercept,&hoi5::AirWing::airSuperiority,
                                &hoi5::AirWing::patrol};
                            const auto mission = missions[(x-116)/100];
                            const bool enable = !(wing.*mission);
                            for (int index : selectedWings) {
                                auto& member = world.air.wings[index];
                                if (member.missionType(2) >= 0) member.*mission = enable;
                            }
                        }
                    } else if (aircraftPanel && selectedWing >= 0 && x >= 290 && x < 416 &&
                               y >= int(window.getSize().y)-79 && y < int(window.getSize().y)-55) {
                        auto& risk = world.air.wings[selectedWing].risk;
                        using Risk = hoi5::AirRisk;
                        if (risk == Risk::cautious) risk = Risk::normal;
                        else if (risk == Risk::aggressive) risk = Risk::cautious;
                        else risk = Risk::aggressive;
                    } else if (aircraftPanel && selectedWing >= 0 && x >= 290 && x < 416 &&
                               y >= int(window.getSize().y)-50 && y < int(window.getSize().y)-26) {
                        auto& wing = world.air.wings[selectedWing];
                        const bool strategic = x >= 353;
                        if (wing.missionAllowed(strategic)) {
                            const bool enable = !wing.enabledMissions[strategic];
                            for (int index : selectedWings) {
                                auto& member = world.air.wings[index];
                                if (member.missionAllowed(strategic)) member.enabledMissions[strategic] = enable;
                            }
                        }
                    } else if (aircraftPanel && selectedWing >= 0 && x >= 20 && x < 100 &&
                               y >= int(window.getSize().y)-50 && y < int(window.getSize().y)-26) {
                        editingWing = editingWing == selectedWing ? -1 : selectedWing;
                        targetingWing = -1;
                        wingCreationOpen = false;
                    } else if (aircraftPanel && selectedWing >= 0 && x >= 205 && x < 280 &&
                               y >= int(window.getSize().y)-50 && y < int(window.getSize().y)-26) {
                        targetingWing = targetingWing == selectedWing ? -1 : selectedWing;
                        editingWing = -1;
                        wingCreationOpen = false;
                    } else if (aircraftPanel && selectedWing >= 0 && x >= 110 && x < 200 &&
                               y >= int(window.getSize().y)-50 && y < int(window.getSize().y)-26) {
                        wingRebaseMode = !wingRebaseMode;
                    } else if (!selectedTiles.empty() && hexPanelRect().contains(sf::Vector2f(button->position))) {
                        if (hexCloseRect(hexPanelRect()).contains(sf::Vector2f(button->position))) selectedTiles.clear();
                        else if (hexResourcesToggle.contains(sf::Vector2f(button->position)))
                            hexResourcesExpanded = !hexResourcesExpanded;
                    } else if (constructionPanel && constructionPlacement && y >= 82) {
                        const auto point = window.mapPixelToCoords(button->position,camera);
                        const int cell = tileAtWorldPosition(world.size,point);
                        if (cell >= 0) {
                            using Key = sf::Keyboard::Key;
                            const int steps = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift) ? 5 : 1;
                            int added = 0;
                            for (; added < steps; ++added) {
                                constructionMessage = world.construction.enqueue(world.tiles,world.size,0,cell,buildingSpec);
                                if (!constructionMessage.empty()) break;
                            }
                            if (added > 0) {
                                constructionMapDirty = true;
                                constructionMessage = "Добавлено в очередь: "+std::to_string(added);
                            }
                        }
                    } else if (y >= 82) {
                        const auto clicked = window.mapPixelToCoords(button->position, camera);
                        const int tile = tileAtWorldPosition(world.size,clicked);
                        using Key = sf::Keyboard::Key;
                        const bool shift = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift);
                        hexScroll = 0;
                        hexResourcesExpanded = false;
                        hexResourcesToggle = {};
                        if (!shift) selectedTiles.clear();
                        if (tile >= 0 && std::erase(selectedTiles,tile) == 0) selectedTiles.push_back(tile);
                        if (aircraftPanel && !shift && std::ranges::any_of(world.air.defense,[&](const auto& unit) {
                            return unit.owner == 0 && unit.tile == tile;
                        })) {
                            selectedWing = -1;
                            selectedWings.clear();
                            wingRebaseMode = false;
                        }
                        if (shift) {
                            if (aircraftPanel && selectedWing >= 0 && !wingRebaseMode && tile >= 0 &&
                                std::ranges::all_of(selectedWings,[&](int index) {
                                    return world.airWingCanReach(world.air.wings[index],tile);
                                }))
                                for (int index : selectedWings)
                                    world.assignAirWingTarget(world.air.wings[index],tile,World::AirAreaEdit::add);
                            continue;
                        }
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
                if (playing && !pauseMenu && selectedBattle < 0 &&
                    (button->button == sf::Mouse::Button::Middle || button->button == sf::Mouse::Button::Right)) {
                    dragging = true;
                    dragStart = button->position;
                    dragTarget = target;
                }
            }
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button == sf::Mouse::Button::Left) activeSlider = -1;
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>();
                motion && activeSlider >= 0 && menuPage == MenuPage::settings)
                updateSlider(motion->position.x);
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button != sf::Mouse::Button::Left) {
                if (dragging && release->button == sf::Mouse::Button::Right &&
                    (selected >= 0 || (aircraftPanel && (selectedWing >= 0 || selectedTiles.size() == 1)) ||
                    (constructionPanel && constructionPlacement))
                    && release->position == dragStart && release->position.y >= 82) {
                    const auto cards = wingCards();
                    const auto p = release->position;
                    if (!world.air.reserves.empty() && p.x >= 10 && p.x < 430 &&
                        p.y >= wingGridTop(int(cards.size()))-34 && p.y < int(window.getSize().y)-14) {
                        if (selectedWings.size() == 1) {
                            const auto pos = std::ranges::find(cards,selectedWing);
                            if (pos != cards.end() && wingCardRect(int(pos-cards.begin()),int(cards.size())).contains(sf::Vector2f(p))) {
                                selectedWings.clear();
                                selectedWing = -1;
                                wingRebaseMode = false;
                                aircraftPanel = wingCreationOpen;
                            }
                        }
                        dragging = false;
                        continue;
                    }
                    const auto clicked = window.mapPixelToCoords(release->position, camera);
                    const int nearest = tileAtWorldPosition(world.size,clicked);
                    if (constructionPanel && constructionPlacement) {
                        const int rows = constructionRows(int(hoi5::Construction::groups(world.construction.queues[0]).size()));
                        const auto p = release->position;
                        if (nearest >= 0 && !(p.x >= 20 && p.x < 390 && p.y >= 90 && p.y < 414+26*std::max(4,rows)) &&
                            (selectedTiles.empty() || !hexPanelRect().contains(sf::Vector2f(p))) &&
                            world.construction.cancel(0,nearest,buildingSpec)) {
                            constructionMessage = "Заявка отменена";
                            constructionMapDirty = true;
                        }
                    } else if (nearest >= 0 && selectedWing >= 0 && aircraftPanel) {
                        if (wingRebaseMode) {
                            bool changed = false;
                            for (int index : selectedWings)
                                changed |= world.air.rebaseWing(world.tiles,index,nearest,&aviationMessage);
                            if (changed) {
                                wingRebaseMode = false;
                                aviationMessage = "Крыло перебазировано в "+std::to_string(nearest%world.size)+":"+
                                    std::to_string(nearest/world.size);
                                selectedTiles = {nearest};
                                hexScroll = 0;
                                hexResourcesExpanded = false;
                            }
                        } else {
                            using Key = sf::Keyboard::Key;
                            const bool shift = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift);
                            if (shift || std::ranges::all_of(selectedWings,[&](int index) {
                                return world.airWingCanReach(world.air.wings[index],nearest);
                            }))
                                for (int index : selectedWings)
                                    world.assignAirWingTarget(world.air.wings[index],nearest,
                                        shift ? World::AirAreaEdit::remove : World::AirAreaEdit::replace);
                        }
                    } else if (nearest >= 0 && aircraftPanel && selectedTiles.size() == 1) {
                        const auto defense = std::ranges::find_if(world.air.defense,[&](const auto& unit) {
                            return unit.owner == 0 && unit.tile == selectedTiles.front();
                        });
                        if (defense != world.air.defense.end()) aviationMessage = world.orderAirDefenseMove(*defense,nearest);
                        else if (selected >= 0) world.orderMove(world.divisions[selected],nearest);
                    } else if (selected >= 0) world.orderMove(world.divisions[selected],nearest);
                }
                dragging = false;
            }
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>(); motion && dragging)
                target = dragTarget - sf::Vector2f(motion->position - dragStart) / zoom;
            if (const auto* wheel = event->getIf<sf::Event::MouseWheelScrolled>(); wheel && playing) {
                if (!selectedTiles.empty() && hexPanelRect().contains(sf::Vector2f(wheel->position))) {
                    hexScroll = std::max(0.f,hexScroll-30*wheel->delta);
                    continue;
                }
                if (economicPanel == 2 && wheel->position.x >= 20 && wheel->position.x < 710
                    && wheel->position.y >= 90 && wheel->position.y < 555) {
                    resourceScroll = std::clamp(resourceScroll - int(wheel->delta),0,
                        std::max(0,int(resourceKeys().size())-resourceVisibleRows));
                    continue;
                }
                if (tradePanel && wheel->position.x >= 20 && wheel->position.x < 660
                    && wheel->position.y >= 90 && wheel->position.y < 550) {
                    tradeScroll = std::clamp(tradeScroll - int(wheel->delta),0,
                        std::max(0,int(world.stockpiles.front().size())-17));
                    continue;
                }
                const auto anchor = window.mapPixelToCoords(wheel->position, camera);
                const float newZoom = std::clamp(zoom + .05f * wheel->delta, .05f, 2.5f);
                if (newZoom == zoom) continue;
                zoom = newZoom;
                camera.setSize(sf::Vector2f(window.getSize()) / zoom);
                camera.move(anchor - window.mapPixelToCoords(wheel->position, camera));
                target = clampCameraPosition(camera.getCenter());
                camera.setCenter(target);
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
                aviationMessage.clear();
                selectedWing = -1;
                editingWing = -1;
                targetingWing = -1;
                selectedWings.clear();
                wingCreationOpen = false;
                wingCreationType = -1;
                wingCreationCount = 1;
                wingRebaseMode = false;
                foreignTarget = 1;
                foreignMessage.clear();
                economicPanel = resourceScroll = tradeScroll = 0;
                resourceForecast.reset();
                resourceCategory = 0;
                groundResources.clear();
                groundResourcesDirty = true;
                selectedMapResource = {};
                resourceMapDirty = true;
                economyPanelProgress = 0;
                map = makeMap(world);
                constructionMapDirty = true;
                borders = makeBorders(world);
                zoom = 1.f;
                target = center(world.capitalQ, world.capitalR);
                camera.setCenter(target);
                camera.setSize(sf::Vector2f(window.getSize()));
                playing = resumable = true;
                selected = -1;
                selectedBattle = -1;
                selectedTiles.clear();
                simulation = {};
            } catch (const std::exception& error) { errorMessage = error.what(); }
        }
        const bool loading = generator.valid();
        const auto size = sf::Vector2f(window.getSize());
        const sf::View gui(sf::FloatRect({0.f, 0.f}, size));
        window.clear({18, 24, 31});
        if (playing && !(pauseMenu && menuPage == MenuPage::settings)) {
            if (!pauseMenu) {
                const int previousTick = simulation.tickCount;
                simulation.update(dt, [&](int hours) {
                    world.advance(hours);
                    const int day = simulation.elapsedHours/24;
                    if (day > world.diplomacy.day && !world.profiles.empty()) {
                        world.refreshLivingConditions();
                        world.diplomacy.advance(day,world.profiles);
                    }
                    if (simulation.pendingMarketTicks && !world.stockpiles.empty()) {
                        simulation.pendingMarketTicks = 0;
                        world.market.execute(world.tiles,world.profiles,world.stockpiles,world.capacities,
                            simulation.marketTickCount,[&](int a,int b) { return world.diplomacy.tradeAllowed(a,b); },
                            [&](int a,int b) { return world.diplomacy.tradePriority(a,b); },
                            [&](int country) { return world.diplomacy.countries[country].externalAccess; },
                            [&](int country) { return world.diplomacy.countries[country].exportLimit; });
                    }
                });
                if (simulation.tickCount != previousTick) {
                    resourceForecast.reset();
                    world.updateEconomyHistory(simulation.elapsedHours,simulation.marketTickCount);
                    world.updateStatus();
                }
                if (world.bordersChanged) {
                    groundResourcesDirty = true;
                    resourceMapDirty = true;
                    constructionMapDirty = true;
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
            target = clampCameraPosition(target);
            camera.move((target - camera.getCenter()) * .3f);
            window.setView(camera);
            constexpr int verticesPerHex = 18;
            const bool rawMapResource = isRawMapResource(selectedMapResource);
            if ((economicPanel == 2 || constructionPanel) && resourceMapDirty) {
                mapResourceAmounts.assign(world.tiles.size(),0.);
                mapResourceScale = 500000;
                resourceSources = 0;
                if (!selectedMapResource.empty()) {
                    if (!rawMapResource) {
                        double output = 0;
                        for (const auto& stage : world.production[0])
                            output += hoi5::value(stage.outputs,selectedMapResource);
                        mapResourceScale = std::max(1.,output*.18);
                    }
                    resourceMap = map;
                    int deposits = 0;
                    for (int i = 0; i < int(world.tiles.size()); ++i) {
                        const auto& tile = world.tiles[i];
                        const double amount = mapResourceAmounts[i] = mapResourceAmount(tile,selectedMapResource,rawMapResource);
                        if (tile.owner == 0) {
                            const double output = rawMapResource ? (amount > 0 ? tileResourceOutput(tile,selectedMapResource) : 0.) : amount;
                            resourceSources += output > 0;
                            deposits += rawMapResource && amount > 0;
                        }
                        if (amount <= 0) continue;
                        const auto color = mapResourceOverlay(amount,mapResourceScale,rawMapResource,
                            map[i*verticesPerHex].color,false);
                        for (int j = 0; j < verticesPerHex; ++j)
                            resourceMap[i*verticesPerHex+j].color = color;
                    }
                    if (resourceSources == 0 && rawMapResource) resourceSources = deposits;
                }
                resourceMapDirty = false;
            }
            if (constructionPanel && constructionPlacement) {
                const auto paint = [&](int tile,sf::Color color) {
                    for (int vertex = 0; vertex < verticesPerHex; ++vertex)
                        constructionMap[tile*verticesPerHex+vertex].color = color;
                };
                if (constructionMapDirty) {
                    constructionMap = map;
                    constructionCoverage.resize(world.tiles.size());
                    constructionLabels.assign(world.tiles.size(),{});
                    const auto building = hoi5::constructionSpecs[buildingSpec].building;
                    for (int i = 0; i < int(world.tiles.size()); ++i)
                        constructionCoverage[i] = std::clamp(world.tiles[i].buildings[building].area,0.,1.);
                    for (const auto& project : world.construction.queues[0])
                        if (!project.repair && project.spec == buildingSpec)
                            constructionCoverage[project.tile] = std::max(constructionCoverage[project.tile],project.target);
                    for (int i = 0; i < int(world.tiles.size()); ++i) {
                        paint(i,constructionOverlayColor(world,i,buildingSpec,constructionCoverage[i],
                            world.tiles[i].terrain,false,mapResourceAmounts[i],mapResourceScale,rawMapResource));
                        if (hoi5::Construction::placementBlock(world.tiles,world.size,0,i,buildingSpec,
                            constructionCoverage[i]).empty())
                            constructionLabels[i] = constructionPlacementLabel(world.tiles[i].buildings[building].area,
                                constructionCoverage[i]);
                    }
                    constructionMapDirty = false;
                }
                const auto cursor = sf::Mouse::getPosition(window);
                const int hovered = tileAtWorldPosition(world.size,window.mapPixelToCoords(cursor,camera));
                if (hovered >= 0) {
                    const auto previous = constructionMap[hovered*verticesPerHex].color;
                    paint(hovered,constructionOverlayColor(world,hovered,buildingSpec,constructionCoverage[hovered],
                        world.tiles[hovered].terrain,true,mapResourceAmounts[hovered],mapResourceScale,rawMapResource));
                    window.draw(constructionMap);
                    paint(hovered,previous);
                } else window.draw(constructionMap);
                if (zoom > .200001f) {
                    const auto half = camera.getSize()*.5f;
                    const auto lower = camera.getCenter()-half-sf::Vector2f{52,11};
                    const auto upper = camera.getCenter()+half+sf::Vector2f{52,11};
                    const int firstRow = std::max(0,int(std::floor(lower.y/(radius*1.5f))));
                    const int lastRow = std::min(world.size-1,int(std::ceil(upper.y/(radius*1.5f))));
                    sf::Text text(font,"",15);
                    text.setStyle(sf::Text::Bold);
                    text.setFillColor({232,252,144});
                    for (int r = firstRow; r <= lastRow; ++r) {
                        const float shift = (r%2)*.5f;
                        const int firstCol = std::max(0,int(std::floor(lower.x/spacing-shift)));
                        const int lastCol = std::min(world.size-1,int(std::ceil(upper.x/spacing-shift)));
                        for (int q = firstCol; q <= lastCol; ++q) {
                            const auto& value = constructionLabels[r*world.size+q];
                            if (value.isEmpty()) continue;
                            const auto position = center(q,r);
                            box(window,position+sf::Vector2f{-52,-9},{104,22},{18,27,22,210},{206,238,140,190});
                            text.setString(value);
                            const auto bounds = text.getLocalBounds();
                            text.setOrigin(bounds.position+bounds.size*.5f);
                            text.setPosition(position+sf::Vector2f{0,1});
                            window.draw(text);
                        }
                    }
                }
            } else if ((economicPanel == 2 || constructionPanel) && !selectedMapResource.empty()) {
                window.draw(resourceMap);
            } else window.draw(map);
            window.draw(borders);
            if (aircraftPanel) for (const auto& unit : world.air.defense) {
                auto position = center(unit.tile%world.size,unit.tile/world.size);
                if (!unit.route.empty()) {
                    const int next = unit.route.front();
                    position += (center(next%world.size,next/world.size)-position)*float(unit.visualProgress);
                }
                box(window,position+sf::Vector2f{-23,25},{46,22},{26,36,48,235},
                    unit.owner == 0 ? sf::Color(113,182,236) : sf::Color(235,115,113));
                label(window,font,"ПВО",position+sf::Vector2f{-17,26},14);
            }
            if (!selectedTiles.empty()) {
                sf::ConvexShape outline(6);
                outline.setFillColor(sf::Color::Transparent);
                outline.setOutlineColor(sf::Color::Yellow);
                outline.setOutlineThickness(-4.f);
                for (int i = 0; i < 6; ++i) {
                    const float angle = std::numbers::pi_v<float>*(i/3.f+1.f/6.f);
                    outline.setPoint(i,{radius*std::cos(angle),radius*std::sin(angle)});
                }
                for (int tile : selectedTiles) {
                    outline.setPosition(center(tile%world.size,tile/world.size));
                    window.draw(outline);
                }
            }
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
                const auto rect = battleIndicator(tile,battle);
                sf::CircleShape marker(22);
                marker.setPosition(rect.position);
                marker.setFillColor(battle.attacker == 0 ? sf::Color(72,44,38,235) : sf::Color(38,55,76,235));
                marker.setOutlineColor({235,215,150});
                marker.setOutlineThickness(-2);
                window.draw(marker);
                label(window,font,std::to_string(int(std::nearbyint(world.battleWinRatio(battle)*100)))+"%",
                    rect.position+sf::Vector2f{8,12},13);
            }
            box(window,{0,0},{size.x,36},{18,24,31,245});
            box(window,{0,35},{size.x,2},{88,106,128});
            box(window,{0,36},{size.x,46},{24,31,40,238});
            box(window,{0,81},{size.x,2},{70,88,108});
            const auto mouse = sf::Mouse::getPosition(window);
            const auto statusWidth = [](const std::string& field) {
                return float(sf::String::fromUtf8(field.begin(),field.end()).getSize())*7;
            };
            const auto statusText = [&](const std::string& field,float left,sf::Color color) {
                sf::Text text(font,sf::String::fromUtf8(field.begin(),field.end()),12);
                const auto bounds = text.getLocalBounds();
                text.setPosition({left,18-bounds.position.y-bounds.size.y/2});
                text.setFillColor(color);
                window.draw(text);
            };
            float x = 10;
            for (int index = 0; index < 3; ++index) {
                const auto& field = world.status[index];
                const float width = std::max(88.f,statusWidth(field)+22);
                const sf::FloatRect rect({x-6,5},{width-8,26});
                if (index == 0) box(window,rect.position,rect.size,sf::Color::Transparent,{118,146,176});
                else if (rect.contains(sf::Vector2f(mouse)))
                    box(window,rect.position,rect.size,{36,48,62,210},{118,146,176,180});
                statusText(field,x,index == 0 ? sf::Color(238,244,250) : sf::Color(210,220,232));
                x += width;
            }
            const auto& resources = world.status[3];
            const float available = std::max(280.f,size.x-x-300);
            const float resourceWidth = std::min(available,std::max(360.f,statusWidth(resources)+38));
            int problem = 0;
            if (!world.stockpiles.empty()) {
                hoi5::Stockpile used;
                for (const auto& [key,stock] : world.stockpiles[0]) {
                    used[hoi5::storageBucket(key)] += stock;
                    double deficit = 0;
                    for (const auto& stage : world.production[0])
                        deficit += hoi5::value(stage.inputs,key)-hoi5::value(stage.outputs,key);
                    if (deficit > 0) {
                        const double months = stock/deficit;
                        problem = std::max(problem,months < 1 ? 2 : months < 3 ? 1 : 0);
                    }
                }
                for (const auto& [key,capacity] : world.capacities[0]) {
                    const double stock = hoi5::value(used,key);
                    if (capacity <= 0) problem = std::max(problem,stock > 0 ? 2 : 0);
                    else problem = std::max(problem,stock >= capacity ? 2 : stock >= .88*capacity ? 1 : 0);
                }
            }
            auto fill = std::array{sf::Color(38,82,54,215),sf::Color(112,92,42,225),sf::Color(112,42,42,225)}[problem];
            if (sf::FloatRect({x,5},{resourceWidth,26}).contains(sf::Vector2f(mouse))) {
                fill.r = int(fill.r*.88+255*.12);
                fill.g = int(fill.g*.88+255*.12);
                fill.b = int(fill.b*.88+255*.12);
            }
            box(window,{x,5},{resourceWidth,26},fill,{116,140,162,180});
            statusText(resources,x+10,{238,244,250});
            x += resourceWidth+14;
            for (int index = 4; index < 7 && x <= size.x-330; ++index) {
                statusText(world.status[index],x,{210,220,232});
                x += std::max(88.f,statusWidth(world.status[index])+22);
            }

            const std::array active{economicPanel == 3,economicPanel == 1,economicPanel == 2,
                tradePanel,constructionPanel,false,diplomacyPanel,militaryPanel};
            for (std::size_t i = 0; i < icons.size(); ++i) {
                const float left = 12+45.f*i;
                const bool hovered = sf::FloatRect({left,40},{38,38}).contains(sf::Vector2f(mouse));
                const auto fill = active[i] ? sf::Color(60,78,98) : hovered ? sf::Color(48,62,78) : sf::Color(30,39,50);
                const auto border = active[i] || hovered ? sf::Color(190,206,224) : sf::Color(92,112,136);
                box(window,{left,40},{38,38},fill,border);
                sf::Sprite sprite(icons[i]);
                sprite.setPosition({left+4,44});
                sprite.setScale({30.f/icons[i].getSize().x,30.f/icons[i].getSize().y});
                sprite.setColor({255,255,255,245});
                window.draw(sprite);
            }
            const float timeX=size.x-312;
            box(window,{timeX,92},{300,72},{20,29,38,235},{100,126,155});
            using namespace std::chrono;
            const year_month_day date{sys_days{year{2000}/1/1} + days{simulation.elapsedHours/24}};
            const std::array<std::string,12> months{"янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"};
            const int hour=simulation.elapsedHours%24;
            const auto centered = [&](std::string value,float x,float y,unsigned points) {
                sf::Text text(font,sf::String::fromUtf8(value.begin(),value.end()),points);
                const auto bounds = text.getLocalBounds();
                text.setPosition({x-bounds.position.x-bounds.size.x/2,y-bounds.position.y-bounds.size.y/2});
                window.draw(text);
            };
            centered(std::to_string(unsigned(date.day()))+" "+months[unsigned(date.month())-1]
                  +" "+std::to_string(int(date.year()))+"  "+(hour<10?"0":"")+std::to_string(hour)+":00",timeX+150,110,17);
            constexpr std::array offsets{14,48,92}, widths{28,38,28};
            const std::array<std::string,3> captions{"-",paused ? ">" : "II","+"};
            for (int i=0;i<3;++i) {
                const sf::FloatRect button({timeX+offsets[i],130},{float(widths[i]),24});
                const bool hovered = button.contains(sf::Vector2f(mouse));
                box(window,button.position,button.size,hovered ? sf::Color(48,62,78) : sf::Color(30,39,50),{92,112,136});
                centered(captions[i],button.position.x+button.size.x/2,142,14);
            }
            centered(std::string(paused?"Пауза  |  ":"")+"Скорость "+std::to_string(speed)+"/5",timeX+210,142,14);
            if (!selectedTiles.empty()) {
                const auto panel = hexPanelRect();
                const auto close = hexCloseRect(panel);
                box(window,panel.position,panel.size,{18,24,31,244},{110,130,154});
                box(window,close.position,close.size,close.contains(sf::Vector2f(mouse))
                    ? sf::Color(96,56,58) : sf::Color(50,58,68),{150,166,184});
                centered("X",close.position.x+12,close.position.y+12,13);
                const int index = selectedTiles.back();
                const auto& tile = world.tiles[index];
                const bool multiple = selectedTiles.size() > 1;
                const auto title = multiple ? "Гексов "+std::to_string(selectedTiles.size())
                    : "Гекс "+std::to_string(index%world.size)+":"+std::to_string(index/world.size);
                label(window,font,title,panel.position+sf::Vector2f(16,17),18);
                const auto owner = [&](int id) -> std::string {
                    if (id < 0) return "Нейтральная территория";
                    if (id < int(world.countryNames.size()) && !world.countryNames[id].empty())
                        return std::string(world.countryNames[id]);
                    return std::to_string(id);
                };
                double population = 0, passability = 0, supply = 0;
                double temperature = 0, moisture = 0, elevation = 0;
                bool sameOwner = true, sameTerrain = true;
                const auto terrain = hoi5::biome(tile.natural);
                for (int selected : selectedTiles) {
                    const auto& cell = world.tiles[selected];
                    population += cell.population;
                    passability += cell.water ? 0 : 1/cell.movementCost;
                    supply += cell.supply;
                    temperature += cell.natural.temperature;
                    moisture += cell.natural.moisture;
                    elevation += cell.natural.elevation;
                    sameOwner &= cell.owner == tile.owner;
                    sameTerrain &= hoi5::biome(cell.natural) == terrain;
                }
                const auto percent = [](double value) { return std::to_string(int(std::nearbyint(std::clamp(value,0.,1.)*100)))+"%"; };
                const std::array<std::pair<std::string,std::string>,5> rows{{
                    {"Владелец",sameOwner ? owner(tile.owner) : "Разные владельцы"},
                    {"Население",formatAmount(population)},
                    {"Местность",sameTerrain ? std::string(terrainDisplayName(terrain)) : "Разная"},
                    {"Проходимость",percent(passability/selectedTiles.size())},
                    {"Снабжение",percent(supply/selectedTiles.size())}
                }};
                std::array<double,hoi5::buildingCount> coverage{}, damage{};
                for (int cell : selectedTiles) {
                    for (int i = 0; i < hoi5::buildingCount; ++i) {
                        const auto& building = world.tiles[cell].buildings[i];
                        coverage[i] += building.area;
                        damage[i] += building.area*(1-std::clamp(building.health,0.,1.));
                    }
                }
                constexpr std::array order{hoi5::airbase,hoi5::city,hoi5::farms,hoi5::fieldHelipad,
                    hoi5::fortification,hoi5::fuelStorage,hoi5::industry,hoi5::mine,hoi5::oilGasRig,
                    hoi5::port,hoi5::refinery,hoi5::supplyDepot,hoi5::village,hoi5::warehouse};
                hoi5::Stockpile ground, localStock, localCapacity, localUsed;
                for (int cell : selectedTiles) {
                    const auto& selected = world.tiles[cell];
                    if (selected.owner < 0 || selected.owner >= int(world.stockpiles.size())) continue;
                    const auto capacity = hoi5::tileStorageCapacity(selected);
                    for (const auto& [bucket,amount] : capacity) localCapacity[bucket] += amount;
                    const auto& total = world.capacities[selected.owner];
                    for (const auto& [key,amount] : world.stockpiles[selected.owner]) {
                        const auto bucket = hoi5::storageBucket(key);
                        const double whole = hoi5::value(total,bucket);
                        const double part = hoi5::value(capacity,bucket);
                        if (whole > 0 && part > 0 && amount > 0) localStock[key] += amount*part/whole;
                    }
                }
                std::vector<std::pair<std::string_view,double>> deposits;
                const auto addDeposit = [&](std::string_view key,double mass) {
                    if (!multiple) {
                        deposits.emplace_back(key,mass);
                        return;
                    }
                    const auto existing = std::find_if(deposits.begin(),deposits.end(),
                        [&](const auto& row) { return row.first == key; });
                    if (existing != deposits.end()) existing->second += mass;
                    else deposits.emplace_back(key,mass);
                };
                for (int cell : selectedTiles) {
                    for (const auto& deposit : world.tiles[cell].deposits) {
                        const double mass = std::max(0.,deposit.mass);
                        if (mass <= 0 && hoi5::value(localStock,deposit.resource) <= 0) continue;
                        addDeposit(deposit.resource,mass);
                        ground.try_emplace(deposit.resource,0);
                    }
                }
                for (const auto& [key,amount] : localStock) {
                    if (!ground.contains(key)) addDeposit(key,0);
                    localUsed[hoi5::storageBucket(key)] += amount;
                }
                if (multiple) std::stable_sort(deposits.begin(),deposits.end(),[&](const auto& a,const auto& b) {
                    return a.second+hoi5::value(localStock,a.first) > b.second+hoi5::value(localStock,b.first);
                });
                constexpr std::pair<std::string_view,std::string_view> storageRows[] = {
                    {"raw","Сырье"},{"semi_finished","Полуфабрикаты"},{"finished","Готовая продукция"},{"fuel","Топливо"}
                };
                int storageCount = 0;
                for (const auto& [key,label] : storageRows)
                    if (hoi5::value(localCapacity,key) > 0 || hoi5::value(localUsed,key) > 0) ++storageCount;
                const auto shown = hexResourcesExpanded ? deposits.size() : std::min(std::size_t(5),deposits.size());
                const bool expandable = deposits.size() > 5;
                const float storageY = 205.f + (shown ? 16.f*shown : 18.f) + (expandable ? 16.f : 0.f);
                const float buildingsY = storageY+28+16*storageCount;
                const auto count = std::count_if(coverage.begin(),coverage.end(),[](double area) { return area > 0; });
                const float bottom = panel.size.y-(coverage[hoi5::industry] > 0 ? 96.f : 58.f);
                const auto containsTile = [&](int index) {
                    return std::find(selectedTiles.begin(),selectedTiles.end(),index) != selectedTiles.end();
                };
                constexpr std::pair<std::string_view,std::string_view> airNames[] = {
                    {"light_fighter","Легкий истребитель"},
                    {"multirole_fighter","Многоцелевой истребитель"},
                    {"fighter_bomber","Истребитель-бомбардировщик"},
                    {"cas_aircraft","Штурмовик"},
                    {"attack_helicopter","Ударный вертолет"},
                    {"strategic_bomber","Стратегический бомбардировщик"},
                    {"manpads_team","Расчет ПЗРК"},
                    {"short_range_aa","Ближняя ПВО"},
                    {"medium_range_sam","Средний ЗРК"},
                    {"long_range_sam","Дальний ЗРК"},
                    {"radar_unit","РЛС"},
                    {"unguided_rockets","НАР"},
                    {"light_guided_missile","Легкая управляемая ракета"},
                    {"guided_bomb","Управляемая бомба"},
                    {"glide_bomb","Планирующая бомба"},
                    {"tactical_cruise_missile","Тактическая крылатая ракета"},
                    {"small_ballistic_missile","Малая баллистическая ракета"},
                    {"heavy_strategic_missile","Тяжелая стратегическая ракета"},
                    {"bunker_buster","Противобункерная бомба"},
                    {"short_air_to_air_missile","Ближняя УРВВ"},
                    {"medium_air_to_air_missile","Средняя УРВВ"},
                };
                const auto airName = [&](std::string_view key) {
                    for (const auto& [id,name] : airNames) if (id == key) return std::string(name);
                    return std::string(key);
                };
                std::vector<std::string> aviation;
                int airbases = 0;
                std::map<std::string_view,int> aircraftCounts, salvoCounts, defenseCounts;
                for (const auto& wing : world.air.wings)
                    if (wing.count > 0 && containsTile(wing.base))
                        for (int type = 0; type < int(std::size(hoi5::aircraftTypes)); ++type)
                            if (const int count = wing.typeCount(type); count > 0)
                                aircraftCounts[hoi5::aircraftTypes[type].key] += count;
                for (const auto& base : world.air.bases) {
                    if (!containsTile(base.tile)) continue;
                    ++airbases;
                    if (multiple) continue;
                    const double health = world.tiles[base.tile].buildings[hoi5::airbase].health;
                    aviation.push_back("Аэродром: ВПП "+std::to_string(base.runway)+", сост. "+percent(health));
                    int fixed = 0, helicopters = 0;
                    for (const auto& wing : world.air.wings) {
                        if (wing.base != base.tile || wing.count <= 0) continue;
                        helicopters += wing.roleCount(true);
                        fixed += wing.roleCount(false);
                    }
                    aviation.push_back("Места: сам. "+std::to_string(fixed)+"/"+std::to_string(base.aircraftCapacity)
                        +" | верт. "+std::to_string(helicopters)+"/"+std::to_string(base.helicopterCapacity));
                }
                if (multiple && airbases) aviation.push_back("Аэродромы: "+std::to_string(airbases));
                if (coverage[hoi5::fieldHelipad] > 0)
                    aviation.push_back("Полевые площадки: "+std::to_string(int(std::nearbyint(100*coverage[hoi5::fieldHelipad])))+"%");
                for (const auto& project : world.helipadProjects)
                    if (containsTile(project.tile)) aviation.push_back("Площадка строится: "+percent(project.progress/18));
                for (const auto& [key,count] : aircraftCounts)
                    aviation.push_back(airName(key)+": "+std::to_string(count)+" на базе");
                for (const auto& salvo : world.salvos)
                    if (salvo.count > 0 && containsTile(salvo.current)) salvoCounts[salvo.weapon->key] += salvo.count;
                for (const auto& [key,count] : salvoCounts)
                    aviation.push_back("Залп: "+airName(key)+" x"+std::to_string(count));
                for (const auto& unit : world.air.defense) {
                    if (!containsTile(unit.tile)) continue;
                    const auto& type = hoi5::defenseClasses[unit.type];
                    if (multiple) ++defenseCounts[type.key];
                    else {
                        aviation.push_back(airName(type.key)+" | БК "+std::to_string(unit.ammo)
                            +"/"+std::to_string(std::max(unit.ammoCapacity,type.ammo)));
                        if (!unit.resupplyStatus.empty()) aviation.push_back(unit.resupplyStatus);
                        if (!unit.route.empty()) {
                            const int target = unit.route.back();
                            aviation.push_back("На марше → "+std::to_string(target%world.size)+":"+std::to_string(target/world.size));
                        }
                    }
                }
                for (const auto& [key,count] : defenseCounts)
                    aviation.push_back(airName(key)+": "+std::to_string(count));
                const float aviationY = buildingsY+28+16*std::max<std::ptrdiff_t>(1,count);
                const float climateY = aviationY+(aviation.empty() ? 0.f : 28.f+16.f*aviation.size());
                const float contentEnd = climateY+20+4*16+12;
                const float maxScroll = std::max(0.f,contentEnd-bottom);
                hexScroll = std::min(hexScroll,maxScroll);
                const auto panelLine = [&](std::string value,float y,unsigned points,float x = 16) {
                    y -= hexScroll;
                    if (y >= 52 && y+points <= bottom)
                        label(window,font,value,panel.position+sf::Vector2f(x,y),points);
                };
                for (std::size_t row = 0; row < rows.size(); ++row)
                    panelLine(rows[row].first+": "+rows[row].second,53+20.f*row,12);
                panelLine("Ресурсы",161,14);
                panelLine("В земле",181,10,174);
                panelLine("Склад",181,10,270);
                float rowY = 197;
                hexResourcesToggle = {};
                const float listTop = rowY;
                for (std::size_t i = 0; i < shown; ++i) {
                    const auto& [key,mass] = deposits[i];
                    const auto name = resourceDisplayName(key);
                    auto text = sf::String::fromUtf8(name.begin(),name.end());
                    if (text.getSize() > 21) text = text.substring(0,20) + sf::String("...");
                    const auto utf8 = text.toUtf8();
                    panelLine(std::string(utf8.begin(),utf8.end()),rowY,11);
                    panelLine(mass > 0 ? formatAmount(mass) : "-",rowY,11,174);
                    const double stored = hoi5::value(localStock,key);
                    panelLine(stored > 0 ? formatAmount(stored) : "-",rowY,11,270);
                    rowY += 16;
                }
                if (!shown) panelLine("Нет доступных залежей и запасов",rowY,11);
                if (expandable) {
                    panelLine(hexResourcesExpanded ? "Скрыть" : "Еще "+std::to_string(deposits.size()-5),rowY,10);
                    const float first = std::max(52.f,listTop-hexScroll);
                    const float last = std::min(bottom,rowY+16-hexScroll);
                    if (first < last) hexResourcesToggle = sf::FloatRect(
                        panel.position+sf::Vector2f(12,first),{panel.size.x-24,last-first});
                }
                panelLine("Емкость",storageY,14);
                rowY = storageY+20;
                for (const auto& [key,name] : storageRows) {
                    const double capacity = hoi5::value(localCapacity,key), used = hoi5::value(localUsed,key);
                    if (capacity <= 0 && used <= 0) continue;
                    panelLine(std::string(name)+": "+formatAmount(used)+"/"+formatAmount(capacity),rowY,11);
                    rowY += 16;
                }
                panelLine("Строения",buildingsY,14);
                rowY = buildingsY+20;
                for (auto building : order) {
                    if (coverage[building] <= 0) continue;
                    const auto spec = std::find_if(std::begin(hoi5::constructionSpecs),std::end(hoi5::constructionSpecs),
                        [&](const auto& entry) { return entry.building == building; });
                    if (spec == std::end(hoi5::constructionSpecs)) continue;
                    std::string value;
                    if (multiple && coverage[building] >= 1) {
                        std::ostringstream out;
                        out << std::fixed << std::setprecision(1) << coverage[building] << " клет.";
                        value = out.str();
                    } else value = percent(coverage[building]);
                    const double fraction = damage[building]/std::max(.001,coverage[building]);
                    if (damage[building] > .001 && fraction > .001) value += " | разрушено "+percent(fraction);
                    panelLine(std::string(spec->label)+": "+value,rowY,11);
                    rowY += 16;
                }
                if (!count) panelLine("Пока нет",rowY,11);
                if (!aviation.empty()) {
                    panelLine("Авиация/ПВО",aviationY,14);
                    rowY = aviationY+20;
                    for (const auto& line : aviation) {
                        panelLine(line,rowY,11);
                        rowY += 16;
                    }
                }
                const double tilesCount = double(selectedTiles.size());
                temperature = std::clamp(temperature/tilesCount,0.,1.);
                moisture = std::clamp(moisture/tilesCount,0.,1.);
                elevation = std::clamp(elevation/tilesCount,0.,1.);
                const char* heat = temperature < .22 ? "холодный" : temperature > .68 ? "жаркий" : "умеренный";
                const char* humidity = moisture < .28 ? "сухой" : moisture > .62 ? "влажный" : "нормальный";
                const int meters = int(std::nearbyint(elevation >= .25 ? (elevation-.25)/.75*3000 : -( .25-elevation)/.25*350));
                const std::array<std::pair<std::string,std::string>,4> climate{{
                    {"Тип",multiple ? "Среднее по выбору" : std::string(heat)+", "+humidity},
                    {"Температура",std::to_string(int(std::nearbyint(-20+temperature*70)))+"°C"},
                    {"Влажность",percent(moisture)},
                    {"Высота",std::to_string(meters)+" м"}
                }};
                panelLine("Климат",climateY,14);
                rowY = climateY+20;
                for (const auto& [key,value] : climate) {
                    panelLine(key,rowY,11);
                    panelLine(value,rowY,11,122);
                    rowY += 16;
                }
                if (maxScroll > 2) {
                    const float track = std::max(1.f,bottom-52);
                    const float thumb = std::max(28.f,track*track/(track+maxScroll));
                    const auto position = panel.position+sf::Vector2f(panel.size.x-10,52);
                    box(window,position,{4,track},{48,62,78,180});
                    box(window,position+sf::Vector2f(0,(track-thumb)*hexScroll/maxScroll),{4,thumb},{132,156,184,220});
                }
            }
            std::erase_if(selectedWings,[&](int index) { return world.air.wings[index].count <= 0; });
            if (selectedWing >= 0 && !selectedWings.contains(selectedWing))
                selectedWing = selectedWings.empty() ? -1 : *selectedWings.begin();
            const auto cards = wingCards();
            if (!world.air.reserves.empty()) {
                const int count = int(cards.size());
                const float top = wingGridTop(count)-34.f;
                box(window,{10,top},{420,size.y-14-top},{17,24,34,238},{86,116,150});
                label(window,font,"Авиакрылья",{22,top+7},13);
                label(window,font,selectedWings.size() > 1 ? "выбрано "+std::to_string(selectedWings.size()) :
                    "Shift: несколько",{312,top+8},10);
                for (int i = 0; i < count; ++i) {
                    const int index = cards[i];
                    const auto rect = wingCardRect(i,count);
                    const auto& wing = world.air.wings[index];
                    const bool chosen = selectedWings.contains(index);
                    box(window,rect.position,rect.size,chosen ? sf::Color(48,76,104,230) : sf::Color(28,39,52,224),
                        chosen ? sf::Color(128,180,220) : sf::Color(74,96,122));
                    const auto name = hoi5::aircraftNames[wing.type];
                    auto shortName = sf::String::fromUtf8(name.begin(),name.end());
                    if (shortName.getSize() > 11) shortName = shortName.substring(0,10)+".";
                    const auto utf8 = shortName.toUtf8();
                    label(window,font,std::string(utf8.begin(),utf8.end()),rect.position+sf::Vector2f{5,3},9);
                    label(window,font,std::to_string(wing.readyCount())+"/"+std::to_string(wing.count),
                        rect.position+sf::Vector2f{5,17},11);
                    label(window,font,std::to_string(wing.base%world.size)+":"+std::to_string(wing.base/world.size),
                        rect.position+sf::Vector2f{5,32},10);
                }
                const auto add = wingCardRect(count,count);
                box(window,add.position,add.size,wingCreationOpen ? sf::Color(42,58,74,235) :
                    sf::Color(28,39,48,225),{86,108,128});
                label(window,font,"+",add.position+sf::Vector2f{29,4},24);
            }
            if (selectedWing >= 0) {
                const auto& wing = world.air.wings[selectedWing];
                label(window,font,std::string(hoi5::aircraftNames[wing.type])+"  "+
                    std::to_string(wing.readyCount())+"/"+std::to_string(wing.count),{110,size.y-75},12);
            }
            if (aircraftPanel && selectedWing >= 0) {
                box(window,{20,size.y-50},{80,24},editingWing == selectedWing ?
                    sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                label(window,font,"Ред.",{42,size.y-47},13);
                box(window,{110,size.y-50},{90,24},wingRebaseMode ? sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                label(window,font,"База",{131,size.y-47},13);
                box(window,{205,size.y-50},{75,24},targetingWing == selectedWing ?
                    sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                label(window,font,"Цели",{223,size.y-47},13);
                const auto& wing = world.air.wings[selectedWing];
                if (wing.missionType(2) >= 0) {
                    constexpr std::array names{"Перехват","Превосходство","Патруль"};
                    const std::array enabled{wing.intercept,wing.airSuperiority,wing.patrol};
                    for (int i = 0; i < int(names.size()); ++i) {
                        const float x = 116+i*100.f;
                        box(window,{x,size.y-111},{98,24},enabled[i] ?
                            sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                        label(window,font,names[i],{x+5,size.y-108},11);
                    }
                }
                using Risk = hoi5::AirRisk;
                const char* risk = wing.risk == Risk::cautious ? "Осторожно" :
                    wing.risk == Risk::aggressive ? "Агрессивно" : "Нормально";
                box(window,{290,size.y-79},{126,24},{30,39,50},{92,112,136});
                label(window,font,risk,{298,size.y-76},13);
                for (bool strategic : {false,true}) {
                    if (!wing.missionAllowed(strategic)) continue;
                    const float x = strategic ? 353.f : 290.f;
                    box(window,{x,size.y-50},{60,24},wing.enabledMissions[strategic] ?
                        sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                    label(window,font,strategic ? "Удар" : "CAS",{x+8,size.y-47},13);
                }
            }
            if (aircraftPanel && !aviationMessage.empty())
                label(window,font,aviationMessage,{25,float(wingCreationBottom()-21)},14);
            if (targetingWing >= 0 && targetingWing == selectedWing) {
                const auto& priorities = world.air.wings[targetingWing].targetPriorities;
                const float top = wingCreationBottom()-airTargetMenuHeight;
                box(window,{10,top},{420,float(airTargetMenuHeight)},{18,24,32,244},{96,122,150});
                label(window,font,"Приоритеты целей",{22,top+8},13);
                for (int i = 0; i < int(std::size(airTargetOptions)); ++i) {
                    const auto [key,name] = airTargetOptions[i];
                    const auto position = std::ranges::find(priorities,key);
                    const bool enabled = position != priorities.end();
                    const float y = top+32+24.f*i;
                    box(window,{20,y},{400,22},enabled ? sf::Color(50,72,94) :
                        sf::Color(28,38,50),{78,102,128});
                    label(window,font,std::string(name),{28,y+2},12);
                    if (enabled) label(window,font,std::to_string(position-priorities.begin()+1),{392,y+2},12);
                }
            }
            if (editingWing >= 0 && editingWing == selectedWing) {
                const auto& wing = world.air.wings[editingWing];
                const auto rows = wingEditRows(editingWing);
                const float height = 52+34.f*rows.size();
                const float top = wingCreationBottom()-height;
                box(window,{10,top},{420,height},{18,24,32,244},{96,122,150});
                label(window,font,"Редактирование состава крыла",{22,top+8},13);
                label(window,font,"Всего в крыле: "+std::to_string(wing.count),{315,top+9},10);
                for (int i = 0; i < int(rows.size()); ++i) {
                    const int type = rows[i];
                    const float y = top+40+i*34.f;
                    const int free = world.air.freeCapacity(world.tiles,wing.owner,wing.base,type);
                    box(window,{20,y},{400,30},{28,38,50,220},{78,102,128});
                    label(window,font,std::string(hoi5::aircraftNames[type]),{28,y+1},10);
                    label(window,font,"в крыле "+std::to_string(wing.typeCount(type))+" | рез. "+
                        std::to_string(world.air.reserves[wing.owner][type])+" | мест "+std::to_string(free),{28,y+15},9);
                    for (int button = 0; button < int(wingEditDeltas.size()); ++button) {
                        const int delta = wingEditDeltas[button];
                        const bool enabled = delta > 0 ? free > 0 && world.air.reserves[wing.owner][type] > 0 :
                            wing.count > 1 && wing.typeCount(type) > 0;
                        const float x = 250+40.f*button;
                        box(window,{x,y+5},{36,20},enabled ? sf::Color(52,72,88) : sf::Color(34,40,48),{78,102,128});
                        label(window,font,(delta > 0 ? "+" : "")+std::to_string(delta),{x+8,y+6},11);
                    }
                }
            }
            if (wingCreationOpen) {
                const auto rows = wingCreationRows();
                const float bottom = wingCreationBottom();
                const float height = 96+30.f*std::max(1,int(rows.size()));
                const float top = bottom-height;
                box(window,{10,top},{420,height},{18,24,32,242},{96,122,150});
                label(window,font,"Создать авиакрыло",{22,top+8},13);
                if (rows.empty()) label(window,font,"Нет самолетов в резерве",{22,top+32},12);
                for (int i = 0; i < int(rows.size()); ++i) {
                    const int type = rows[i];
                    const float y = top+32+i*30.f;
                    box(window,{20,y},{400,25},type == wingCreationType ? sf::Color(50,72,94,225) :
                        sf::Color(28,38,50,210),{78,102,128});
                    label(window,font,std::string(hoi5::aircraftNames[type]),{28,y+4},12);
                    label(window,font,"рез. "+std::to_string(world.air.reserves[0][type])+" | мест "+
                        std::to_string(wingCreationLimit(type)),{306,y+5},11);
                }
                if (!rows.empty()) {
                    const int limit = wingCreationLimit(wingCreationType);
                    wingCreationCount = std::clamp(wingCreationCount,1,std::max(1,limit));
                    const float y = bottom-36;
                    for (float x : {22.f,108.f}) box(window,{x,y},{28,24},{34,46,58,230},{92,112,136});
                    label(window,font,"-",{31,y+2},14);
                    label(window,font,"+",{116,y+2},14);
                    label(window,font,std::to_string(wingCreationCount),{75,y+3},12);
                    const float ratio = limit <= 1 ? 0.f : float(wingCreationCount-1)/(limit-1);
                    box(window,{150,y+9},{134,6},{46,58,70,230});
                    if (ratio > 0) box(window,{150,y+9},{134*ratio,6},{98,146,190,235});
                    sf::CircleShape knob(6);
                    knob.setPosition({144+134*ratio,y+6});
                    knob.setFillColor({218,232,242});
                    window.draw(knob);
                    label(window,font,limit > 0 ? "1-"+std::to_string(limit) : "нет мест",{203,y-8},9);
                    box(window,{308,y},{110,24},limit > 0 ? sf::Color(52,78,60,235) :
                        sf::Color(54,55,58,210),{116,152,120});
                    label(window,font,"Создать",{337,y+3},12);
                }
            }
            box(window,{440,size.y-54},{560,38},{18,24,31,235},{92,112,136});
            label(window,font,"Мировые новости",{450,size.y-46});
            box(window,{size.x-62,size.y-62},{44,44},{18,24,31,235},{92,112,136});
            sf::Sprite sprite(layers);
            sprite.setPosition({size.x-56,size.y-56});
            sprite.setScale({32.f/layers.getSize().x,32.f/layers.getSize().y});
            window.draw(sprite);
            const float economyTarget = economicPanel == 1 ? 1.f : 0.f;
            economyPanelProgress += (economyTarget-economyPanelProgress)*std::min(1.f,dt*12);
            if (std::abs(economyPanelProgress-economyTarget) < .01f) economyPanelProgress = economyTarget;
            if (economyPanelProgress > 0) {
                const float offset = 620*(1-economyPanelProgress);
                auto panelView = gui;
                panelView.move({offset,0});
                window.setView(panelView);
                constexpr float top = 94, width = 620, content = 18;
                box(window,{0,top},{width,size.y-top-12},{18,24,31,244},{110,130,154});
                const auto close = sf::FloatRect({582,104},{28,28});
                box(window,close.position,close.size,close.contains(sf::Vector2f(mouse)+sf::Vector2f(offset,0))
                    ? sf::Color(96,56,58) : sf::Color(50,58,68),{150,166,184});
                label(window,font,"X",{591,109},14);
                const auto text = [&](std::string value,float x,float y,unsigned points,sf::Color color,bool right = false) {
                    sf::Text line(font,sf::String::fromUtf8(value.begin(),value.end()),points);
                    const auto bounds = line.getLocalBounds();
                    line.setPosition({right ? x-bounds.position.x-bounds.size.x : x,
                        y-bounds.position.y-bounds.size.y});
                    line.setFillColor(color);
                    window.draw(line);
                };
                const auto money = [](double amount,bool delta = false) {
                    const double value = std::abs(amount);
                    std::ostringstream out;
                    if (amount < 0) out << "-";
                    else if (delta && amount > 0) out << "+";
                    out << "$" << std::fixed;
                    if (value >= 1e9) out << std::setprecision(1) << value/1e9 << "B";
                    else if (value >= 1e6) out << std::setprecision(1) << value/1e6 << "M";
                    else if (value >= 1e3) out << std::setprecision(1) << value/1e3 << "K";
                    else out << std::setprecision(0) << value;
                    return out.str();
                };
                const auto flows = world.taxedTreasury(0);
                const double trade = world.economyCurrent ? world.economyCurrent->trade : 0;
                const double budget = world.profiles[0].budget, balance = flows.balance()+trade;
                const auto previous = world.economyPrevious;
                const auto good = sf::Color(178,226,158), bad = sf::Color(238,150,132);
                text("Экономика",18,top+36,18,sf::Color::White);
                constexpr float cardWidth = (width-36-10)/2;
                for (int i = 0; i < 2; ++i) {
                    const float left = content+i*(cardWidth+10);
                    box(window,{left,top+68},{cardWidth,82},{28,40,52,220},{86,112,138});
                    text(i == 0 ? "Бюджет" : "Прогноз",left+12,top+90,10,{164,180,198});
                    text(i == 0 ? money(budget) : "1 мес: "+money(budget+balance),left+12,top+114,15,sf::Color::White);
                    text(i == 0 ? money(balance,true)+"/мес" : "3 мес: "+money(budget+balance*3),left+12,top+134,11,
                        i == 0 ? (balance >= 0 ? good : bad) : sf::Color(210,222,236));
                }
                float row = top+178;
                const auto section = [&](std::string title) {
                    text(title,content,row,14,sf::Color::White);
                    box(window,{content,row+7},{width-36,1},{72,92,112,180});
                    text("Сейчас",width-178,row,10,{150,166,184},true);
                    text("К прошл. мес.",width-18,row,10,{150,166,184},true);
                    row += 24;
                };
                const auto item = [&](std::string title,double amount,bool expense = false,std::optional<double> old = {}) {
                    text(title,content+8,row,11,{214,224,234});
                    text(expense ? "-"+money(amount) : money(amount,true),width-178,row,11,
                        expense || amount < 0 ? sf::Color(236,168,154) :
                        amount > 0 ? sf::Color(190,226,174) : sf::Color(210,222,234),true);
                    const double delta = old ? amount-*old : 0;
                    const auto deltaColor = !old ? sf::Color(150,164,180) : std::abs(delta) < 1
                        ? sf::Color(170,184,198) : (expense ? delta <= 0 : delta >= 0) ? good : bad;
                    text(old ? money(delta,true) : "--",width-18,row,11,deltaColor,true);
                    row += 18;
                };
                const auto prior = [&](auto value) -> std::optional<double> {
                    if (!previous) return {};
                    return value(*previous);
                };
                section("Доходы");
                item("Налоги населения",flows.population,false,prior([](const auto& p) { return p.flows.population; }));
                item("Компании",flows.companies,false,prior([](const auto& p) { return p.flows.companies; }));
                item("Торговля",trade,false,prior([](const auto& p) { return p.trade; }));
                item("Всего доходов",flows.population+flows.companies+trade,false,prior([](const auto& p) { return p.flows.population+p.flows.companies+p.trade; }));
                row += 8;
                section("Расходы");
                item("Армия",0,true);
                item("Правительство",flows.government,true,prior([](const auto& p) { return p.flows.government; }));
                item("Соц. обеспечение",flows.social,true,prior([](const auto& p) { return p.flows.social; }));
                const double millions = world.profiles[0].population/1e6;
                item("  Пенсии",flows.pensions,true,prior([](const auto& p) { return p.flows.pensions; }));
                item("  Дети/школы",flows.children,true,prior([](const auto& p) { return p.flows.children; }));
                item("  Инвалиды",flows.disability,true,prior([](const auto& p) { return p.flows.disability; }));
                item("  Соцслужбы",flows.localServices,true,prior([](const auto& p) { return p.flows.localServices; }));
                item("Инфраструктура",flows.infrastructure,true,prior([](const auto& p) { return p.flows.infrastructure; }));
                item("Всего расходов",flows.expenses(),true,prior([](const auto& p) { return p.flows.expenses(); }));
                row += 8;
                section("Итог и показатели");
                item("Месячный баланс",balance,false,prior([](const auto& p) { return p.flows.balance()+p.trade; }));
                text("Население",content+8,row,11,{214,224,234});
                text(world.status[1].substr(std::string("Нас: ").size()),width-178,row,11,{210,222,234},true);
                text("--",width-18,row,11,{150,164,180},true);
                row += 18;
                const auto land = std::count_if(world.tiles.begin(),world.tiles.end(),[](const Tile& tile) {
                    return tile.owner == 0 && !tile.water;
                });
                text("Территория",content+8,row,11,{214,224,234});
                text(std::to_string(land)+" клеток",width-178,row,11,{210,222,234},true);
                row += 18;
                item("Налогов на 1M жителей",flows.population/std::max(.001,millions));
                item("Компании - инфраструктура",flows.companies-flows.infrastructure);
                window.setView(gui);
            }
            if (economicPanel == 3) {
                box(window,{20,90},{610,380},{18,24,31,250},{92,112,136});
                const auto& policy = world.diplomacy.countries[0];
                label(window,font,"Политический капитал: "+std::to_string(int(policy.capital)),{30,98},18);
                for (int group = 0; group < int(policyGroups.size()); ++group) {
                    const float y = 130+group*25.f;
                    label(window,font,policyGroups[group],{30,y},15);
                    label(window,font,std::to_string(int(std::lround(policy.groups[group]*100)))+"%",{322,y},15);
                    if (group < 3) {
                        label(window,font,std::to_string(100+10*policy.taxes[group])+"%",{380,y},15);
                        box(window,{440,y},{48,21},{30,39,50});
                        box(window,{490,y},{48,21},{30,39,50});
                        label(window,font,"−",{458,y},15);
                        label(window,font,"+",{508,y},15);
                    }
                    box(window,{540,y},{85,21},{30,39,50});
                    label(window,font,policy.programHours[group] ? "Отменить" : "30 дней",{546,y},15);
                }
                label(window,font,policy.externalAccess ? "Закрыть внешний рынок" : "Открыть внешний рынок",{30,414},15);
                label(window,font,policy.exportLimit < 1 ? "Снять лимит экспорта" : "Ограничить экспорт",{320,414},15);
                label(window,font,policyMessage,{30,444},15);
            }
            if (economicPanel == 2) {
                if (!resourceForecast) resourceForecast = world.forecastResources(0,simulation.marketTickCount);
                const auto& forecast = *resourceForecast;
                if (groundResourcesDirty) {
                    groundResources.clear();
                    for (const auto& tile : world.tiles)
                        if (tile.owner == 0)
                            for (const auto& deposit : tile.deposits) groundResources[deposit.resource] += deposit.mass;
                    groundResourcesDirty = false;
                }
                box(window,{20,90},{690,465},{18,24,31,250},{92,112,136});
                label(window,font,"Ресурсы",{30,96},18);
                for (int i = 0; i < int(resourceCategories.size()); ++i) {
                    const float x = 30+i*140.f;
                    box(window,{x,115},{137,23},i == resourceCategory ? sf::Color(47,71,88) :
                        sf::Color(30,39,50),{82,108,132});
                    label(window,font,resourceCategories[i],{x+5,117},13);
                }
                label(window,font,"В земле      Запас       Выпуск/мес      Расход/мес      Хватит на",{240,138},13);
                const auto& stocks = world.stockpiles[0];
                const auto keys = resourceKeys();
                resourceScroll = std::clamp(resourceScroll,0,std::max(0,int(keys.size())-resourceVisibleRows));
                for (int row = 0; row < resourceVisibleRows && row+resourceScroll < int(keys.size()); ++row) {
                    const auto key = keys[row+resourceScroll];
                    const double amount = hoi5::value(stocks,key);
                    const double output = hoi5::value(forecast.outputs,key);
                    const double input = hoi5::value(forecast.inputs,key);
                    const float y = resourceRowsTop+row*resourceRowHeight;
                    if (key == selectedMapResource) box(window,{25,y},{675,22},{63,59,35},{172,150,80});
                    label(window,font,std::string(resourceDisplayName(key)),{30,y},14);
                    label(window,font,resourceCategory == 0 ? resourceAmountLabel(hoi5::value(groundResources,key)) : "--",{240,y},14);
                    label(window,font,resourceAmountLabel(amount),{321,y},14);
                    label(window,font,resourceAmountLabel(output),{397,y},14);
                    label(window,font,resourceAmountLabel(input),{494,y},14);
                    label(window,font,resourceDurationLabel(amount,output,input),{601,y},14);
                }
                if (!selectedMapResource.empty()) {
                    const float width = size.x-732;
                    box(window,{720,90},{width,465},{22,29,38,230},{100,126,155});
                    const auto close = resourceCardClose();
                    box(window,close.position,close.size,{50,58,68},{150,166,184});
                    label(window,font,"X",close.position+sf::Vector2f{7,3},12);
                    label(window,font,std::string(resourceDisplayName(selectedMapResource)),{734,105},15);
                    label(window,font,"Источники: "+std::to_string(resourceSources)+" клетки",{734,141},12);
                    const auto& production = forecast.stages;
                    const auto flow = [&](hoi5::ProductionStage stage,bool output) {
                        return hoi5::value(output ? production[stage].outputs : production[stage].inputs,
                            selectedMapResource);
                    };
                    float y = 170;
                    const auto breakdown = [&](std::string_view title,std::string_view empty,const auto& entries) {
                        label(window,font,std::string(title),{734,y},12);
                        y += 20;
                        double total = 0;
                        for (const auto& [name,amount] : entries) total += amount;
                        if (total <= 0) {
                            label(window,font,std::string(empty),{740,y},11);
                            y += 16;
                        } else for (const auto& [name,amount] : entries) {
                            if (amount <= 0) continue;
                            const auto percent = std::to_string(int(std::nearbyint(amount/total*100)));
                            label(window,font,std::string(name)+": "+percent+"% ("+resourceAmountLabel(amount)+"/мес)",{740,y},11);
                            y += 16;
                        }
                        y += 6;
                    };
                    using Entry = std::pair<std::string_view,double>;
                    breakdown("Производство","Текущего прихода нет",std::array{
                        Entry{"Добыча/фермы",flow(hoi5::raw,true)},Entry{"Удобрения",flow(hoi5::agriculture,true)},
                        Entry{"Промышленность",flow(hoi5::semiFinished,true)+flow(hoi5::finished,true)},
                        Entry{"Импорт",hoi5::value(forecast.imports,selectedMapResource)}});
                    breakdown("Потребление","Текущего расхода нет",std::array{
                        Entry{"Армия",hoi5::value(forecast.army,selectedMapResource)},
                        Entry{"Стройки",hoi5::value(forecast.building,selectedMapResource)},
                        Entry{"Производство",flow(hoi5::semiFinished,false)+flow(hoi5::agriculture,false)+flow(hoi5::finished,false)},
                        Entry{"Поддержание",flow(hoi5::upkeep,false)},
                        Entry{"Экспорт",hoi5::value(forecast.exports,selectedMapResource)}});
                    label(window,font,"Описание",{734,y},12);
                    y += 20;
                    std::istringstream words(std::string(hoi5::resourceUsageDescription(selectedMapResource)));
                    sf::Text measure(font,"",11);
                    std::string line, word;
                    while (words >> word) {
                        const auto candidate = line.empty() ? word : line+" "+word;
                        measure.setString(sf::String::fromUtf8(candidate.begin(),candidate.end()));
                        if (!line.empty() && measure.getLocalBounds().size.x > width-28) {
                            label(window,font,line,{734,y},11);
                            y += 16;
                            line = word;
                        } else line = candidate;
                    }
                    if (!line.empty()) label(window,font,line,{734,y},11);
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
                const auto& queue = world.construction.queues[0];
                const auto groups = hoi5::Construction::groups(queue);
                const int rows = constructionRows(int(groups.size()));
                const float offset = 26.f*std::max(4,rows);
                box(window,{20,90},{370,324+offset},{18,24,31,250},{92,112,136});
                label(window,font,"Строительство",{30,96},18);
                box(window,{30,119},{346,23},{30,39,50},{82,108,132});
                label(window,font,!queue.empty() && queue.front().paused ? "Возобновить" : "Приостановить",
                    {38,121},14);
                if (queue.empty()) label(window,font,"Пока пусто",{38,151},14);
                for (int i = 0; i < rows; ++i) {
                    const auto [first,end] = groups[i];
                    const auto& project = queue[first];
                    const float y = 148+i*26.f;
                    box(window,{30,y},{346,23},{30,39,50},{82,108,132});
                    const auto title = std::string(hoi5::constructionStatusLabel(project.status))+
                        " · "+std::string(hoi5::constructionSpecs[project.spec].label);
                    label(window,font,title+(end-first > 1 ? " ×"+std::to_string(end-first) : ""),{36,y+3},11);
                    const auto percent = [](double value) { return std::to_string(int(std::nearbyint(value*100)))+"%"; };
                    label(window,font,percent(std::lerp(project.from,project.target,project.progress))+" → "+
                        percent(queue[end-1].target),{250,y+3},11);
                    for (int direction : {-1,1}) {
                        const float x = direction < 0 ? 326.f : 351.f;
                        const bool enabled = hoi5::Construction::canMoveGroup(queue,groups,i,direction);
                        box(window,{x,y+2},{22,19},enabled ? sf::Color(52,70,88) : sf::Color(34,40,48),{82,108,132});
                        label(window,font,direction < 0 ? "^" : "v",{x+7,y+2},12);
                    }
                }
                if (groups.size() > 4)
                    label(window,font,constructionQueueExpanded ? "Свернуть очередь" :
                        "Показать еще "+std::to_string(groups.size()-rows),{36,151+rows*26.f},13);
                for (int i = 0; i < int(std::size(hoi5::constructionSpecs)); ++i) {
                    const float x = i%2 ? 205.f : 30.f, y = 190+offset+(i/2)*23.f;
                    box(window,{x,y},{171,21},i == buildingSpec ? sf::Color(47,71,88) : sf::Color(30,39,50));
                    label(window,font,std::string(hoi5::constructionSpecs[i].label),{x+3,y+2},10);
                }
                box(window,{30,355+offset},{346,26},constructionPlacement ? sf::Color(47,71,88) :
                    sf::Color(30,39,50),{82,108,132});
                label(window,font,constructionPlacement ? "Завершить размещение" : "Начать строительство",
                    {38,358+offset},15);
                label(window,font,constructionMessage,{30,386+offset},14);
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
            if (const auto found = world.battles.find(selectedBattle); found != world.battles.end()) {
                const auto& battle = found->second;
                const auto panel = battlePanel();
                const auto close = battleClose(panel);
                const auto [x,y] = panel.position;
                const auto [width,height] = panel.size;
                const auto rounded = [](double value) { return std::to_string(int(std::nearbyint(value))); };
                const auto precise = [](double value) {
                    std::ostringstream out;
                    out << std::fixed << std::setprecision(1) << value;
                    return out.str();
                };
                const auto ratio = world.battleWinRatio(battle);
                const double attack = world.battlePower(battle.attackers), defense = world.battlePower(battle.defenders);
                const double pressure = std::max(.08,std::abs(attack-defense)/std::max(1.,attack+defense));
                const int hours = int(std::ceil((1-std::clamp(battle.advance,0.,1.))/.035+
                    (defense > 0 ? (1-pressure)*36 : 0)));
                const std::string duration = hours < 24 ? std::to_string(hours)+" ч." :
                    std::to_string(hours/24)+" дн."+(hours%24 ? " "+std::to_string(hours%24)+" ч." : "");
                box(window,panel.position,panel.size,{16,24,30,238},{112,142,174});
                box(window,close.position,close.size,{44,54,66,240},{120,142,164});
                label(window,font,"X",close.position+sf::Vector2f{8,3},13);
                label(window,font,"Сражение",{x+20,y+12},19);
                box(window,{x+20,y+54},{width-40,16},{48,42,42,230},{128,148,168});
                if (ratio > 0) box(window,{x+20,y+54},{float((width-40)*ratio),16},{72,126,76,235});
                label(window,font,"Ход сражения: "+rounded(ratio*100)+"%",{x+width*.5f-75,y+53},12);
                label(window,font,"Соотношение сил: "+rounded(attack)+" / "+rounded(defense)+
                    "   ШФ: "+rounded(battle.width)+" ("+rounded(1+(battle.width-80)/40)+")",{x+20,y+79},13);
                label(window,font,"Осталось: "+duration,{x+width-188,y+79},13);
                label(window,font,"Потери",{x+width*.5f-27,y+112},15);
                const bool playerAttacks = battle.attacker == 0;
                const bool playerDefends = battle.defender == 0;
                for (int column = 0; column < 2; ++column) {
                    const bool attacking = column == (playerDefends ? 1 : 0);
                    const int incoming = attacking ? 0 : 1;
                    const float left = x+20+column*width*.5f;
                    const auto& participants = attacking ? battle.attackers : battle.defenders;
                    const auto& active = attacking ? battle.activeAttackers : battle.activeDefenders;
                    label(window,font,std::string(playerAttacks || playerDefends ? (column ? "Враг" : "Наши") :
                        (attacking ? "Атакующие" : "Защитники"))+" — орг "+precise(battle.organizationDamage[incoming])+
                        ", хп "+precise(battle.strengthDamage[incoming]),{left,y+139},13);
                    float row = y+171;
                    constexpr std::array groups{"В бою","В резерве","Восстановление"};
                    for (int group = 0; group < int(groups.size()); ++group) {
                        if (row+20 > y+height-12) break;
                        label(window,font,groups[group],{left,row},13);
                        row += 22;
                        for (int index : participants) {
                            const auto& unit = world.divisions[index];
                            const bool fighting = std::ranges::find(active,index) != active.end();
                            const int status = fighting ? 0 : unit.combat.recovering ? 2 : 1;
                            if (unit.combat.strength <= 0 || status != group || row+20 > y+height-12) continue;
                            box(window,{left,row},{width*.5f-40,19},{30,39,50});
                            label(window,font,std::string(unit.design->name)+"  "+rounded(unit.organization)+
                                " / "+rounded(unit.combat.strength),{left+5,row+1},11);
                            row += 21;
                        }
                        row += 6;
                    }
                }
            } else selectedBattle = -1;
            if (pauseMenu) {
                box(window,{0,0},size,{8,12,17,170});
                const float x=size.x/2-150, y=size.y/2;
                box(window,{x,y-55},{300,42},{30,39,50},{92,112,136});
                box(window,{x,y},{300,42},{30,39,50},{92,112,136});
                box(window,{x,y+55},{300,42},{30,39,50},{92,112,136});
                label(window,font,"Вернуться в игру",{x+18,y-46},18);
                label(window,font,"Настройки",{x+18,y+9},18);
                label(window,font,"Выйти в главное меню",{x+18,y+64},18);
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
            } else if (menuPage == MenuPage::settings) {
                const float x = size.x/2-230, y = size.y/2;
                label(window,font,"Настройки",{x,32},36);
                const auto slider = [&](std::string caption,float row,float value) {
                    label(window,font,caption,{x,row-42},16);
                    label(window,font,std::to_string(int(value))+"%",{x+415,row-42},16);
                    box(window,{x,row-3},{460,6},{55,66,78});
                    box(window,{x,row-3},{4.6f*value,6},{109,155,210});
                    sf::CircleShape knob(10);
                    knob.setPosition({x+4.6f*value-10,row-10});
                    knob.setFillColor({230,238,248});
                    window.draw(knob);
                };
                slider("Громкость звука",y-74,soundVolume);
                slider("Громкость музыки",y-4,musicVolume);
                box(window,{x,y+38},{220,42},{30,39,50},{92,112,136});
                box(window,{x+240,y+38},{220,42},{30,39,50},{92,112,136});
                label(window,font,pendingFullscreen ? "Полный экран: Вкл" : "Полный экран: Выкл",{x+12,y+47},18);
                const auto mode = resolutions[pendingResolution];
                label(window,font,"Разрешение",{x+240,y+16},16);
                label(window,font,std::to_string(mode.x)+"x"+std::to_string(mode.y),{x+252,y+47},18);
                box(window,{x,y+111},{220,44},{30,39,50},{92,112,136});
                box(window,{x+240,y+111},{220,44},{30,39,50},{92,112,136});
                label(window,font,"Применить",{x+12,y+121},18);
                label(window,font,"Назад",{x+252,y+121},18);
                if (resolutionOpen) for (int i = 0; i < int(resolutions.size()); ++i) {
                    const float row = y+80+25*i;
                    box(window,{x+240,row},{220,25},{30,39,50},{92,112,136});
                    label(window,font,std::to_string(resolutions[i].x)+"x"+std::to_string(resolutions[i].y),{x+252,row+3},16);
                }
                label(window,font,settingsMessage,{x,y+218},16);
            } else if (menuPage == MenuPage::help) {
                const float x = size.x/2-235, y = size.y/2;
                label(window,font,"Управление",{x,32},36);
                label(window,font,"Стрелки или перетаскивание — камера",{x,y-90},18);
                label(window,font,"Колесо мыши — масштаб",{x,y-57},18);
                label(window,font,"ЛКМ — выбрать дивизию, ПКМ — приказ",{x,y-24},18);
                label(window,font,"Пробел — пауза, 1–5 — скорость, Esc — меню",{x,y+9},18);
                box(window,{size.x/2-150,y+100},{300,42},{30,39,50},{92,112,136});
                label(window,font,"Назад",{size.x/2-132,y+109},18);            } else {
                label(window,font,"HOI 5",{size.x/2-48,32},36);
                const std::array<std::string,6> buttons{"Новая игра", "Продолжить игру",
                    "Мультиплеер", "Настройки", "Помощь", "Выход из игры"};
                for (std::size_t i=0;i<buttons.size();++i) {
                    const float y=size.y/2-152+54*i;
                    box(window,{size.x/2-150,y},{300,42},{30,39,50},{92,112,136});
                    const auto value = sf::String::fromUtf8(buttons[i].begin(),buttons[i].end());
                    sf::Text text(font,value,18);
                    if (i==2 || (i==1 && !resumable)) text.setFillColor({152,164,180});
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
