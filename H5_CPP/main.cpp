#include <SFML/Graphics.hpp>
#include "terrain_color.hpp"
#include <future>
#include "simulation_clock.hpp"
#include "market.hpp"
#include "format_amount.hpp"
#include "news.hpp"
#include "news_panel.hpp"
#include "debug_profiler.hpp"
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
#include "python_seed.hpp"
#include "ai_supply.hpp"

#include <algorithm>
#include <array>
#include <deque>
#include <queue>
#include <limits>
#include <memory>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <numbers>
#include <numeric>
#include <stdexcept>
#include <string_view>
#include <sstream>
#include <span>
#include <random>
#include <chrono>
#include <vector>

#ifndef HOI5_VERSION
#define HOI5_VERSION "0.0.9.dev"
#endif

inline constexpr std::string_view gameVersion = HOI5_VERSION;

using hoi5::formatAmount;

std::string resourceAmountLabel(double amount) {
    return (amount < 0 ? "-" : "")+formatAmount(std::abs(amount));
}

std::string formatMoney(double amount) {
    const std::string prefix = amount < 0 ? "-$" : "$";
    const double magnitude = std::abs(amount);
    if (magnitude < 1e9) return prefix+formatAmount(magnitude);
    std::ostringstream text;
    text << prefix << std::fixed << std::setprecision(1) << magnitude/1e9 << 'B';
    return text.str();
}

std::string formatMoneyDelta(double amount) {
    return (amount > 0 ? "+" : "")+formatMoney(amount);
}

std::string formatPopulationDelta(std::optional<double> amount) {
    if (!amount) return "--";
    return std::string(*amount > 0 ? "+" : *amount < 0 ? "-" : "")+formatAmount(std::abs(*amount));
}

int exportSliderPercent(int x,int left = 130,int width = 300) {
    return 5*int(std::nearbyint(std::clamp(double(x-left)/width,0.,1.)*20));
}

constexpr std::array policyGroups{"Население","Малый и средний бизнес","Крупный бизнес","Рабочие (пролетариат)",
    "Сельские жители","Средний класс","Аристократия","Националисты","Социалисты","Либералы","Консерваторы"};

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

std::string_view industrySectorDisplayName(std::string_view key) {
    static constexpr std::pair<std::string_view,std::string_view> names[] = {
        {"metallurgy","Металлургия"},{"construction_materials","Стройматериалы"},
        {"chemicals","Химия"},{"machinery","Машиностроение"},{"vehicles","Транспорт"},
        {"consumer_goods","Товары"},{"electronics","Электроника"},
        {"shipbuilding","Судостроение"},{"weapons","Оружие"}
    };
    const auto found = std::ranges::find_if(names,[&](const auto& item) { return item.first == key; });
    return found == std::end(names) ? key : found->second;
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
    int armyId{};
    int manualFrontHours{};
    int assignedFrontPost = -1;
    int q{};
    int r{};
    double speed{}, organization{}, maxOrganization{}, progress{};
    double visualProgress{};
    double lastSupplyRatio = 1.;

    std::deque<int> route;
    std::deque<int> postBattleRoute;
    std::string icon;
    hoi5::CombatStats combat;
    int battle = -1;
    bool attackRoute = false;
    bool retreating = false;
    bool destructionReported = false;
    int manpower = 10000;
    const hoi5::DivisionTemplate* design = &hoi5::divisionTemplates[0];
    hoi5::Stockpile supplies = design->capacity;
    std::map<int,double> airGroundSuppression;

    double consume(std::string_view key,double amount) {
        if (amount <= 0.) return 0.;
        auto& stock = supplies[key];
        const double used = std::min(stock,amount);
        stock = std::max(0.,stock-used);
        return used;
    }

    double consumeMovementSupplies(int hours) {
        if (hours <= 0) return 1.;
        double ratio = 1.;
        for (const auto& [key,need] : std::array<std::pair<std::string_view,double>,2>{{
            {"refined_fuel",combat.vehicles*speed*1.8*hours},{"field_supplies",.12*hours}
        }})
            if (need > 0.) ratio = std::min(ratio,consume(key,need)/need);
        return .55+.45*std::clamp(ratio,0.,1.);
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
    int id{};
};

struct World {
    struct Army {
        int id, owner;
        std::string name;
        std::vector<int> front;
        int borderOwner = -2, reviewHours{};
        bool automaticLine{}, executing{};
        std::vector<int> offensive;
    };
    static constexpr int armyCapacity = 20;
    std::vector<Army> armies;
    std::vector<hoi5::BotSupplyState> supplyBots;
    hoi5::BotRegionMap botGeography;
    int botHours{}, botMarketTick{};
    std::set<int> botBalanceRefresh;
    std::vector<int> frontOwnershipChanges;
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
    std::vector<std::shared_ptr<const hoi5::SavedDivisionDesign>> playerDesigns;
    int nextTrainingId = 1;
    int populationHours{}, politicsHours{};
    std::vector<hoi5::Production> production;
    std::vector<hoi5::TreasuryFlows> treasury;
    hoi5::Market market;
    hoi5::FlowLedger botLedger;
    hoi5::News news;
    struct EconomySnapshot {
        hoi5::TreasuryFlows flows;
        double population, trade, budget;
    };
    std::vector<EconomySnapshot> economyCurrent, economyPrevious;
    std::chrono::year_month economyMonth{};
    hoi5::Diplomacy diplomacy;
    hoi5::AirLayer air;
    std::vector<hoi5::AirSalvo> salvos;
    struct AirVisual {
        int owner, origin, target, type;
        bool impact, loss;
        std::chrono::steady_clock::time_point start;
    };
    std::deque<AirVisual> airVisuals;
    void addAirVisual(int owner,int origin,int target,int type,bool impact = false,bool loss = false) {
        const auto now = std::chrono::steady_clock::now();
        while (!airVisuals.empty() && (airVisuals.size() >= 128 ||
            now-airVisuals.front().start > std::chrono::seconds(3))) airVisuals.pop_front();
        airVisuals.push_back({owner,origin,target,type,impact,loss,now});
    }
    std::vector<hoi5::AircraftInterceptorSalvo> aircraftInterceptors;
    hoi5::Construction construction;
    std::map<int,hoi5::Battle> battles;
    std::uint64_t nextBattleOrder{};
    hoi5::PythonRandom groundCombatRandom;
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

    std::deque<int> divisionRoute(const Division& unit,int origin,int destination) const {
        const bool capture = tiles[destination].owner < 0 || diplomacy.hostile(unit.owner,tiles[destination].owner);
        return landRoute(origin,destination,[&](int next) {
            const int owner = tiles[next].owner;
            const bool allowed = owner < 0 ? capture : diplomacy.canTransit(unit.owner,owner)
                || canWithdraw(unit,owner,destination) || (capture && diplomacy.hostile(unit.owner,owner));
            return !tiles[next].water && allowed;
        });
    }

    bool orderMove(Division& unit, int destination,bool append = false) const {
        if (unit.battle >= 0 || unit.retreating || unit.combat.strength <= 0 || unit.organization < unit.maxOrganization * .30) return false;
        if (destination < 0 || destination >= static_cast<int>(tiles.size())) return false;
        const bool extend = append && !unit.route.empty();
        const int origin = extend ? unit.route.back() : unit.r*size+unit.q;
        auto route = divisionRoute(unit,origin,destination);
        if (destination != origin && route.empty()) return false;
        if (extend && route.empty()) return false;
        if (extend) unit.route.insert(unit.route.end(),route.begin(),route.end());
        else unit.route = std::move(route);
        unit.retreating = false;
        unit.attackRoute = tiles[destination].owner >= 0 && diplomacy.hostile(unit.owner,tiles[destination].owner);
        if (!extend) unit.progress = unit.visualProgress = 0;
        return true;
    }

    bool airDefenseWater(int tile) const {
        return tiles[tile].water || tiles[tile].natural.water > .55;
    }

    bool airDefenseCanEnter(const hoi5::AirDefense& unit,int tile) const {
        return tiles[tile].owner == unit.owner && !airDefenseWater(tile);
    }

    std::string orderAirDefenseMove(hoi5::AirDefense& unit,int target,bool* accepted = nullptr) const {
        if (accepted) *accepted = false;
        if (target < 0 || target >= int(tiles.size())) return "Нет цели перемещения";
        if (tiles[target].owner != unit.owner) return "ПВО можно двигать только по своей территории";
        if (airDefenseWater(target)) return "ПВО нельзя поставить на воду";
        if (unit.tile == target) {
            unit.route.clear();
            if (accepted) *accepted = true;
            return "ПВО уже здесь";
        }
        auto route = landRoute(unit.tile,target,[&](int next) {
            return airDefenseCanEnter(unit,next);
        },true);
        if (route.empty()) return "Нет маршрута для ПВО";
        unit.route = std::move(route);
        unit.progress = unit.visualProgress = 0.;
        unit.readinessLimit = std::min(unit.readinessLimit,.55);
        if (accepted) *accepted = true;
        return "ПВО выдвигается в "+std::to_string(target%size)+":"+std::to_string(target/size);
    }

    void advanceAirDefense(int hours) {
        if (hours <= 0) return;
        for (auto& unit : air.defense) {
            const auto canEnter = [&](int tile) { return airDefenseCanEnter(unit,tile); };
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
        const auto [incoming,outgoing] = diplomacy.monthlyDebtFlows(country);
        flows.loanRepayments = incoming;
        flows.debtService = outgoing;
        flows.politicalPrograms = diplomacy.programExpenses(country);
        for (const auto& unit : divisions) if (unit.owner == country)
            flows.army += std::max(0,unit.manpower)*8.;
        for (const auto& wing : air.wings) if (wing.owner == country)
            flows.army += std::max(0,wing.count)*18000.;
        for (const auto& unit : air.defense) if (unit.owner == country)
            flows.army += 60000.*std::max(.25,unit.health);
        return flows;
    }

    struct CountryPower {
        std::array<double,5> indices{};
        double total{};
        int rank = 1;
    };

    std::vector<CountryPower> powerRanking() const {
        std::vector<CountryPower> result(profiles.size());
        std::array<double,5> maxima{};
        for (int country = 0; country < int(profiles.size()); ++country) {
            const auto income = taxedTreasury(country);
            const auto& policy = diplomacy.countries[country];
            auto& components = result[country].indices;
            components[0] = std::max(0.,income.population)+std::max(0.,income.companies);
            const double cohesion = (policy.stability+policy.legitimacy+policy.support)/3;
            components[4] = std::max(0.,profiles[country].population)*std::clamp(cohesion,0.,1.);
            for (const auto& tile : tiles) if (tile.owner == country && !tile.water) {
                const auto infantry = hoi5::groundTerrainEffects(tile.natural,false);
                const auto armor = hoi5::groundTerrainEffects(tile.natural,true);
                components[3] += 1.+1.5*hoi5::agricultureScore(tile.natural)+
                    .35*std::max(infantry.defense,armor.defense);
                for (const auto& deposit : tile.deposits)
                    components[3] += .12*std::log1p(std::max(0.,deposit.mass));
            }
        }
        for (const auto& unit : divisions) {
            const double readiness = std::clamp(unit.organization/std::max(1.,unit.maxOrganization),0.,1.);
            const double strength = std::clamp(unit.combat.strength/std::max(1.,unit.design->combat.strength),0.,1.);
            const double equipment = unit.combat.softAttack+unit.combat.frontAttack+unit.combat.topAttack+unit.combat.defense;
            result[unit.owner].indices[1] += std::max(0,unit.manpower)*std::max(0.,equipment)*strength*
                (.25+.75*readiness)*std::clamp(unit.lastSupplyRatio,0.,1.);
        }
        for (const auto& wing : air.wings) if (wing.owner >= 0 && wing.owner < int(result.size())) {
            double quality = 1.;
            for (int type = 0; type < int(std::size(hoi5::aircraftTypes)); ++type)
                if (wing.typeCount(type) > 0)
                    quality = std::max(quality,.65+hoi5::aircraftTypes[type].range*.08);
            result[wing.owner].indices[2] += std::max(0,wing.readyCount())*quality;
        }
        for (const auto& entry : result)
            for (std::size_t i = 0; i < maxima.size(); ++i)
                maxima[i] = std::max(maxima[i],entry.indices[i]);
        constexpr std::array weights{.35,.30,.15,.05,.15};
        for (auto& entry : result)
            for (std::size_t i = 0; i < maxima.size(); ++i) {
                entry.indices[i] = maxima[i] > 0 ? 100*entry.indices[i]/maxima[i] : 0.;
                entry.total += entry.indices[i]*weights[i];
            }
        for (auto& entry : result)
            for (const auto& other : result)
                entry.rank += other.total > entry.total;
        return result;
    }

    static std::string_view relativePower(double target,double own) {
        if (target == 0 && own == 0) return "Сопоставимая мощь";
        if (own <= 0) return "Значительно сильнее нас";
        const double ratio = target/own;
        if (ratio >= 1.5) return "Значительно сильнее нас";
        if (ratio >= 1.15) return "Сильнее нас";
        if (ratio <= .67) return "Значительно слабее нас";
        if (ratio <= .87) return "Слабее нас";
        return "Сопоставимая мощь";
    }

    std::string countryThreat(int country,const std::vector<CountryPower>& ratings) const {
        const auto& relation = diplomacy.relation(0,country);
        const double military = ratings[country].indices[1]*.67+ratings[country].indices[2]*.33;
        const double ownMilitary = ratings[0].indices[1]*.67+ratings[0].indices[2]*.33;
        const auto it = relation.opinion.find(country);
        const double attitude = it == relation.opinion.end() ? 0. : it->second;
        if (relation.war)
            return std::string("Военная угроза: ")+(military >= ownMilitary ? "высокая" : "средняя")+"; идёт война";
        if (relation.treaties.contains(hoi5::ForeignAction::alliance))
            return "Военная угроза: низкая; действует союз";
        const char* level = attitude >= -20 ? "низкая" : military > ownMilitary*1.15 ? "высокая" : "средняя";
        return std::string("Военная угроза: ")+level+"; отношение "+(attitude >= 0 ? "+" : "")+
            std::to_string(int(std::nearbyint(attitude)));
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

    void executeWeeklyMarket(int rotation) {
        market.execute(tiles,profiles,stockpiles,capacities,rotation,
            [&](int a,int b) { return diplomacy.tradeAllowed(a,b); },
            [&](int a,int b) { return diplomacy.tradePriority(a,b); },
            [&](int country) { return diplomacy.countries[country].externalAccess; },
            [&](int country) { return diplomacy.countries[country].exportLimit; });
        ++botMarketTick;
        std::vector<std::array<hoi5::Stockpile,2>> quantities(profiles.size());
        for (const auto& fill : market.last.fills) {
            if (fill.buyer) {
                quantities[*fill.buyer][1][fill.resource] += fill.amount;
                botLedger.record(*fill.buyer,hoi5::FlowKind::import,fill.resource,fill.amount,
                    fill.seller ? *fill.seller : -1);
            }
            if (fill.seller) {
                quantities[*fill.seller][0][fill.resource] += fill.amount;
                botLedger.record(*fill.seller,hoi5::FlowKind::export_,fill.resource,fill.amount,
                    fill.buyer ? *fill.buyer : -1);
            }
            news.recordTrade(diplomacy.day,fill,[&](int i) { return countryNames[i]; },resourceDisplayName);
        }
        std::vector<std::string> missing(profiles.size());
        for (const auto& contract : market.normalizedContracts()) {
            if (contract.country >= int(profiles.size())) continue;
            const double delivered = hoi5::value(quantities[contract.country][contract.buy],contract.resource);
            if (delivered+1e-6 >= contract.amount*hoi5::Market::weeklyFraction) continue;
            auto& description = missing[contract.country];
            if (!description.empty()) description += ", ";
            description += resourceDisplayName(contract.resource);
        }
        for (int i = 0; i < int(profiles.size()); ++i)
            news.reportIncompleteTrade(diplomacy.day,i,countryNames[i],std::move(missing[i]));
    }

    void advanceWorldNews(int day) {
        hoi5::WorldNewsContext context;
        if (market.revision != 0)
            context.oilPressure = hoi5::value(market.demand,"oil")/std::max(1.,hoi5::value(market.supply,"oil"));
        double majorOutput = 0.;
        for (int i = 0; i < int(production.size()); ++i) {
            double output = 0.;
            for (const auto& stage : production[i]) output += hoi5::value(stage.outputs,"oil");
            if (output <= majorOutput) continue;
            majorOutput = output;
            context.majorOilExporterRestricted = diplomacy.countries[i].exportLimit < .1;
        }
        news.advance(day,context);
    }

    std::string performForeignAction(int actor,int target,const hoi5::ForeignActionInfo& action,double amount = 0.) {
        if ((action.action == hoi5::ForeignAction::aid || action.action == hoi5::ForeignAction::loan) &&
            (!std::ranges::any_of(tiles,[&](const auto& tile) { return tile.owner == actor; }) ||
             !std::ranges::any_of(tiles,[&](const auto& tile) { return tile.owner == target; })))
            return "Государство не контролирует территорию";
        const auto error = diplomacy.act(actor,target,action,profiles,amount);
        if (!error.empty()) return error;
        using A = hoi5::ForeignAction;
        using P = hoi5::NewsPriority;
        const std::string source(countryNames[actor]), destination(countryNames[target]);
        const bool leader = !rulers[actor].empty();
        const std::string speaker = leader ? "глава государства "+std::string(rulers[actor]) :
            "правительство страны "+source;
        const int day = diplomacy.day;
        const auto [offerKey,offerName] = hoi5::offerNames(action.action);
        if (!offerKey.empty())
            news.report(day,"offer_received","Предложение от "+source,
                source+" предлагает: "+std::string(offerName)+". Ответ доступен в дипломатии.",P::important,target);
        switch (action.action) {
        case A::war:
            news.report(day,"war",source+" объявила войну стране "+destination,
                "После недель напряжённых заявлений "+speaker+(leader ? " объявил" : " объявило")+
                " о начале войны против "+destination+". Дипломатические каналы ещё работают, однако отношения сторон "
                "перешли в состояние войны. На что пойдут правительства дальше, пока неизвестно.",P::critical);
            break;
        case A::justify:
            news.report(day,"war_justification",source+" готовится к войне с "+destination,
                (leader ? "Глава государства "+std::string(rulers[actor]) : "Правительство страны "+source)+
                (leader ? " выступил" : " выступило")+" с резким заявлением в адрес "+destination+
                ". Действия другой стороны в заявлении названы провокационными; власти предупреждают, что могут принять "
                "решительные меры. Это позиция одной из сторон конфликта: боевые действия пока не начались.",P::important);
            break;
        case A::cancelJustification:
            news.report(day,"war_deescalation",source+" прекращает подготовку войны",
                "Подготовка войны против страны "+destination+" отменена. Напряжённость снизилась.",P::important);
            break;
        case A::embargo:
        case A::breakTreaties: {
            const bool embargo = action.action == A::embargo;
            const bool imposed = embargo && diplomacy.relation(actor,target).embargoes.contains(actor);
            news.report(day,embargo ? "embargo" : "break",source+
                (embargo ? (imposed ? " ввела эмбарго против" : " сняла эмбарго со") : " разорвала договоры со")+
                " страны "+destination,"Дипломатические и торговые отношения сторон изменились.",P::important);
            break;
        }
        case A::mission:
        case A::revokeTransit:
        case A::aid:
            news.report(day,action.action == A::mission ? "mission" : action.action == A::aid ? "aid" : "revoke_transit",
                source+": "+std::string(action.label),"Решение касается отношений со страной "+destination+".",
                P::regular,actor,target);
            break;
        default:
            break;
        }
        return {};
    }

    void reportForeignResponse(const hoi5::ForeignOffer& offer,bool accepted) {
        const auto [key,label] = hoi5::offerNames(offer.action);
        const std::string source(countryNames[offer.actor]), target(countryNames[offer.target]), name(label);
        using P = hoi5::NewsPriority;
        if (!accepted)
            news.report(diplomacy.day,"offer_rejected","Дипломатическое предложение отклонено",
                target+": предложение «"+name+"» не принято либо утратило силу.",P::regular,offer.actor);
        else if (offer.action == hoi5::ForeignAction::transit || offer.action == hoi5::ForeignAction::loan)
            news.report(diplomacy.day,key,"Соглашение: "+name,
                "Страны "+source+" и "+target+" согласовали условия.",P::regular,offer.actor,offer.target);
        else
            news.report(diplomacy.day,key,source+" и "+target+": "+name,
                "Государства "+source+" и "+target+" достигли соглашения.",
                offer.action == hoi5::ForeignAction::peace ? P::critical : P::important);
    }

    const hoi5::ForeignOffer* incomingOffer(int actor,int target,
                                          std::optional<hoi5::ForeignAction> action = {}) const {
        const auto it = std::ranges::find_if(diplomacy.offers,[&](const auto& offer) {
            return offer.actor == actor && offer.target == target && (!action || offer.action == *action);
        });
        return it == diplomacy.offers.end() ? nullptr : &*it;
    }

    bool answerForeignOffer(int actor,int target,bool accept,std::optional<hoi5::ForeignAction> action = {}) {
        const auto* incoming = incomingOffer(actor,target,action);
        if (!incoming) return false;
        const auto offer = *incoming;
        diplomacy.offers.erase(diplomacy.offers.begin()+(incoming-diplomacy.offers.data()));
        if (offer.action == hoi5::ForeignAction::loan)
            accept = accept && std::ranges::any_of(tiles,[&](const auto& tile) { return tile.owner == actor; }) &&
                std::ranges::any_of(tiles,[&](const auto& tile) { return tile.owner == target; });
        const bool accepted = diplomacy.resolve(offer,accept,profiles);
        reportForeignResponse(offer,accepted);
        return accepted;
    }

    void expireSupportPrograms(std::span<const std::pair<int,int>> expired) {
        for (const auto& [country,group] : expired) {
            auto& state = diplomacy.countries[country];
            state.programFunded[group] = state.programFunding[group] = 0.;
            const std::string label(policyGroups[group]);
            diplomacy.record("Программа завершена по сроку: "+label,country);
            news.report(diplomacy.day,"program_expired","Срок поддержки истёк: "+label,
                "Программа поддержки группы «"+label+"» в стране "+std::string(countryNames[country])+
                " завершилась по сроку.",hoi5::NewsPriority::regular,country);
        }
    }

    bool botOfferResponse(const hoi5::ForeignOffer& offer,bool fallback) const {
        const auto bot = std::ranges::find(supplyBots,offer.target,&hoi5::BotSupplyState::owner);
        if (bot == supplyBots.end()) return fallback;
        if (offer.action == hoi5::ForeignAction::peace)
            return profiles[offer.target].budget < 0 || diplomacy.countries[offer.target].warSupport < .45 || fallback;
        if (bot->course == hoi5::BotCourseChoice{hoi5::BotCourse::warPreparation,offer.actor} &&
            (offer.action == hoi5::ForeignAction::alliance ||
             offer.action == hoi5::ForeignAction::nonaggression ||
             offer.action == hoi5::ForeignAction::transit)) return false;
        return fallback;
    }

    void advancePolitics(int day,std::span<const std::pair<int,int>> expired = {},
                         hoi5::DebugProfiler* debug = nullptr) {
        for (int current = diplomacy.day+1; current <= day; ++current) {
            diplomacy.serviceLoans(current,profiles,[&](const auto& loan,bool arrears,bool repaid) {
                const std::string lender(countryNames[loan.lender]), borrower(countryNames[loan.borrower]);
                news.alert(current,loan.borrower,borrower,"loan_arrears:"+std::to_string(loan.lender),arrears,
                    "Не хватает средств на платёж по кредиту",
                    "Обязательства перед "+lender+" оплачены не полностью. Проверьте бюджет и график выплат.",
                    "Просроченные платежи по кредиту погашены");
                if (repaid) news.report(current,"loan_repaid","Кредит полностью погашен",
                    "Расчёты между "+lender+" и "+borrower+" по кредиту завершены.",
                    hoi5::NewsPriority::regular,loan.lender,loan.borrower);
            });
            for (const auto& [pair,relation] : diplomacy.relations) {
                if (relation.truceUntil != current) continue;
                const auto [a,b] = pair;
                news.report(current,"truce_expired","Срок перемирия истёк",
                    "Перемирие между "+std::string(countryNames[a])+" и "+std::string(countryNames[b])+
                    " больше не ограничивает объявление войны. Остальные требования сохраняются.",
                    hoi5::NewsPriority::regular,a,b);
            }
            for (const auto& [pair,ready] : diplomacy.goals) {
                const auto [actor,target] = pair;
                const std::string destination(countryNames[target]);
                if (current == ready)
                    news.report(current,"war_goal_ready","Цель войны подготовлена",
                        "Цель войны против страны "+destination+" готова. Решение об объявлении войны остаётся за вами.",
                        hoi5::NewsPriority::regular,actor);
                else if (current > ready+180)
                    news.report(current,"war_goal_expired","Цель войны утратила силу",
                        "Подготовленная цель войны против страны "+destination+" больше не действует.",
                        hoi5::NewsPriority::regular,actor);
            }
            diplomacy.advance(current,profiles,[&](const auto& offer,bool accepted) {
                reportForeignResponse(offer,accepted);
            },[&](const auto& offer,bool fallback) {
                hoi5::DebugMeasure timing(debug,"ai_offer_response");
                return botOfferResponse(offer,fallback);
            });
            if (current == day) expireSupportPrograms(expired);
            advanceWorldNews(current);
            reportCountryAlerts(current);
        }
    }

    void advancePoliticsHours(int hours,hoi5::DebugProfiler* debug = nullptr) {
        if (profiles.empty() || diplomacy.countries.size() != profiles.size()) return;
        while (hours > 0) {
            const int step = std::min(hours,24-politicsHours);
            const bool midnight = politicsHours+step == 24;
            if (midnight && production.size() == profiles.size() && stockpiles.size() == profiles.size())
                refreshLivingConditions();
            const auto expired = diplomacy.fundPrograms(step,profiles);
            hours -= step;
            politicsHours += step;
            if (midnight) {
                politicsHours = 0;
                advancePolitics(diplomacy.day+1,expired,debug);
            } else expireSupportPrograms(expired);
        }
    }

    void reportDomesticDecision(int country,std::string decision) {
        const std::string name(countryNames[country]);
        news.report(diplomacy.day,"domestic_decision",name+": "+std::move(decision),
            "Правительство страны "+name+" изменило экономическую политику.",hoi5::NewsPriority::regular,country);
    }

    std::string_view changeTax(int country,int group,int delta) {
        const auto error = diplomacy.changeTax(country,group,delta);
        if (error.empty()) reportDomesticDecision(country,"Налоговая ставка: "+std::string(policyGroups[group]));
        return error;
    }

    std::string_view changeMarketPolicy(bool external,double exportPercent = 100.) {
        const auto error = diplomacy.changeMarketPolicy(external,exportPercent);
        if (error.empty()) {
            const auto& state = diplomacy.countries[0];
            reportDomesticDecision(0,external ? (state.externalAccess ? "Внешний рынок открыт" : "Внешний рынок закрыт") :
                "Лимит экспорта: "+std::to_string(int(state.exportLimit*100))+"%");
        }
        return error;
    }

    std::string_view changeSupportProgram(int country,int group,int hours) {
        const bool stopping = diplomacy.countries[country].programHours[group] != 0;
        const auto error = diplomacy.changeProgram(country,group,hours,profiles[country]);
        if (!error.empty()) return error;
        const std::string label(policyGroups[group]), name(countryNames[country]);
        if (stopping)
            news.report(diplomacy.day,"program_stop","Поддержка прекращена: "+label,
                "Программа поддержки группы «"+label+"» в стране "+name+" завершена.",hoi5::NewsPriority::regular,country);
        else
            news.report(diplomacy.day,"program_start","Начата программа: "+label,
                "Правительство страны "+name+" начало поддержку группы «"+label+"».",hoi5::NewsPriority::regular,country);
        return {};
    }

    using ConstructionNoticeKey = std::tuple<int,int,hoi5::ConstructionStatus>;
    struct ConstructionNotice { int newsId{}, clearHours{}; };
    std::map<ConstructionNoticeKey,ConstructionNotice> constructionNotices;

    void reportConstructionAlerts(int hours) {
        using Status = hoi5::ConstructionStatus;
        std::map<ConstructionNoticeKey,std::vector<const hoi5::ConstructionProject*>> stalled;
        for (int country = 0; country < int(construction.queues.size()); ++country)
            for (const auto& project : construction.queues[country])
                if (project.status == Status::waitingMoney || project.status == Status::waitingResources ||
                    project.status == Status::waitingPower)
                    stalled[{country,project.spec,project.status}].push_back(&project);
        for (auto& [key,notice] : constructionNotices)
            if (!stalled.contains(key)) notice.clearHours += hours;
        std::erase_if(constructionNotices,[](const auto& entry) { return entry.second.clearHours >= 24; });
        for (const auto& [key,projects] : stalled) {
            const auto [country,spec,status] = key;
            auto& notice = constructionNotices[key];
            notice.clearHours = 0;
            const std::string name(hoi5::constructionSpecs[spec].label);
            std::string body = "Заявок: "+std::to_string(projects.size())+".";
            if (status == Status::waitingResources) {
                hoi5::Stockpile missing;
                for (const auto* project : projects)
                    for (const auto& [resource,amount] : project->missingResources)
                        missing[resource] = std::max(missing[resource],amount);
                if (!missing.empty()) {
                    body += " Не хватает: ";
                    for (auto it = missing.begin(); it != missing.end(); ++it) {
                        if (it != missing.begin()) body += ", ";
                        body += std::string(resourceDisplayName(it->first));
                    }
                    body += '.';
                }
            } else if (status == Status::waitingMoney) {
                double amount = 0.;
                for (const auto* project : projects) amount = std::max(amount,project->missingMoney);
                body += " Не хватает денег: "+formatMoney(amount)+".";
            }
            body += " Гексы: ";
            for (std::size_t i = 0; i < std::min<std::size_t>(projects.size(),6); ++i) {
                if (i) body += ", ";
                const int tile = projects[i]->tile;
                body += "("+std::to_string(tile%size)+", "+std::to_string(tile/size)+")";
            }
            if (projects.size() > 6) body += " и ещё "+std::to_string(projects.size()-6);
            if (!notice.newsId)
                notice.newsId = news.report(diplomacy.day,"construction_stalled",
                    name+": "+std::string(hoi5::constructionStatusLabel(status)),std::move(body),hoi5::NewsPriority::important,country);
            else news.updateBody(notice.newsId,std::move(body));
        }
    }

    void reportCountryAlerts(int day) {
        std::vector<bool> lowArmySupply(profiles.size());
        for (const auto& unit : divisions)
            if (unit.combat.strength > 0 && unit.lastSupplyRatio < .5)
                lowArmySupply[unit.owner] = true;
        std::vector<double> trade(profiles.size());
        for (const auto& fill : forecastMarketPlan(day < 2 ? 0 : (day-2)/7+1).fills) {
            if (fill.seller) trade[*fill.seller] += fill.amount*fill.price;
            if (fill.buyer) trade[*fill.buyer] -= fill.amount*fill.price;
        }
        for (int country = 0; country < int(stockpiles.size()); ++country) {
            const auto& state = diplomacy.countries[country];
            hoi5::Stockpile used;
            for (const auto& [resource,amount] : stockpiles[country]) used[hoi5::storageBucket(resource)] += amount;
            const bool overflow = std::ranges::any_of(used,[&](const auto& bucket) {
                return bucket.second > hoi5::value(capacities[country],bucket.first);
            });
            const auto alert = [&](std::string_view key,bool active,const char* title,const char* body,const char* recovery) {
                news.alert(day,country,countryNames[country],key,active,title,body,recovery);
            };
            alert("radicalization_unrest",std::max(state.factionRadicalization[1],state.factionRadicalization[2]) >= .7,
                "Высокая радикализация фракций",
                "Радикализация либералов или социалистов достигла 70%. Война разрешена, но недовольство вызовет внутренние последствия.",
                "Радикализация фракций снизилась ниже опасного уровня");
            alert("political_capital_low",state.capital < 20,"Политический капитал на исходе",
                "Осталось менее 20 единиц политического капитала. Часть решений недоступна.","Политический капитал восстановился до 20");
            alert("storage_overflow",overflow,"Склады переполнены",
                "Объём запасов превышает доступное хранилище. Проверьте вместимость складов и экспорт.","Переполнение складов устранено");
            alert("budget_deficit",taxedTreasury(country).balance()+trade[country] < 0,"Бюджет исполняется с дефицитом",
                "Текущие расходы превышают доходы. Проверьте бюджет.","Бюджет вышел из дефицита");
            alert("food_shortage",state.food < .75,"Населению не хватает продовольствия",
                "Обеспечение продовольствием ниже 75% потребности. Проверьте производство и импорт.","Обеспечение продовольствием улучшилось");
            alert("goods_shortage",state.goods < .75,"Нехватка потребительских товаров",
                "Обеспечение населения товарами ниже 75% потребности.","Обеспечение потребительскими товарами улучшилось");
            alert("government_support_low",state.support < .45,"Низкая поддержка правительства",
                "Поддержка власти ниже 45%. Часть политических решений может быть недоступна.","Поддержка правительства восстановилась до 45%");
            alert("legitimacy_low",state.legitimacy < .45,"Легитимность власти снизилась",
                "Легитимность ниже 45%. Проверьте доступность политических решений.","Легитимность восстановилась до 45%");
            alert("army_supply_low",lowArmySupply[country],"Перебои снабжения войск",
                "Часть дивизий обеспечена менее чем наполовину. Проверьте склады и снабжение.","Снабжение войск улучшилось");
            bool underfunded = false;
            for (std::size_t group = 0; group < state.programHours.size(); ++group)
                underfunded |= state.programHours[group] != 0. && state.programFunding[group] < .9;
            alert("program_underfunded",underfunded,"Программы поддержки недофинансированы",
                "На действующие программы не хватает средств. Их эффект снижен.","Финансирование программ поддержки восстановлено");
        }
    }

    void updateEconomyHistory(int hours,int rotation) {
        if (profiles.empty()) return;
        using namespace std::chrono;
        const year_month_day date{sys_days{year{2000}/1/1}+days{hours/24}};
        const auto month = date.year()/date.month();
        if (!economyCurrent.empty() && month != economyMonth) economyPrevious = economyCurrent;
        economyMonth = month;
        economyCurrent.resize(profiles.size());
        for (int i = 0; i < int(profiles.size()); ++i)
            economyCurrent[i] = {taxedTreasury(i),profiles[i].population,0.,profiles[i].budget};
        for (const auto& fill : forecastMarketPlan(rotation).fills) {
            if (fill.buyer) economyCurrent[*fill.buyer].trade -= fill.amount*fill.price;
            if (fill.seller) economyCurrent[*fill.seller].trade += fill.amount*fill.price;
        }
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
                return hoi5::populationResourceRatio(production[country],stockpiles[country],key);
            };
            state.food = ratio("food");
            state.goods = ratio("consumer_goods");
            state.foodPrice = market.price("food") / market.base("food");
            state.goodsPrice = market.price("consumer_goods") / market.base("consumer_goods");
            state.supply = supply[country] / std::max(1,land[country]);
        }
    }

    static std::array<double,3> resourceSummary(const hoi5::Stockpile& stocks) {
        const auto sum = [&](std::initializer_list<std::string_view> keys) {
            double total = 0;
            for (auto key : keys) total += hoi5::value(stocks,key);
            return total;
        };
        return {sum({"iron_ore","copper_ore","bauxite","lead","zinc","nickel","gold","silver",
            "rare_earth_metals","alloying_additives"}),sum({"coal","oil","natural_gas","peat","uranium"}),
            hoi5::value(stocks,"consumer_goods")};
    }

    void updateStatus() {
        if (stockpiles.empty()) return;
        const auto [metals,fuel,goods] = resourceSummary(stockpiles.front());
        status = {countryNames.front().empty() ? "Player" : std::string(countryNames.front()),
            "Нас: " + formatAmount(profiles.front().population),
            formatMoney(profiles.front().budget)+"  "+formatMoneyDelta(taxedTreasury(0).balance()+
                (economyCurrent.empty() ? 0. : economyCurrent.front().trade))+"/мес",
            "Металлы " + resourceAmountLabel(metals) + "  Топливо " + resourceAmountLabel(fuel) + "  Товары " + resourceAmountLabel(goods),
            "Стаб: " + std::to_string(int(std::lround(diplomacy.countries[0].stability*100))) + "%",
            "Легит: " + std::to_string(int(std::lround(diplomacy.countries[0].legitimacy*100))) + "%",
            "Подд. войны: " + std::to_string(int(std::lround(diplomacy.countries[0].warSupport*100))) + "%"};
    }

    struct TileStorageSnapshot {
        hoi5::Stockpile national;
        std::map<int,hoi5::Stockpile> tiles;
    };
    std::vector<std::optional<TileStorageSnapshot>> tileStorageSnapshots;

    const hoi5::Stockpile& stockpileAtTile(int index) {
        static const hoi5::Stockpile empty;
        const int owner = tiles[index].owner;
        if (owner < 0 || owner >= int(stockpiles.size())) return empty;
        auto& snapshot = tileStorageSnapshots[owner];
        auto& stocks = stockpiles[owner];
        if (!snapshot || snapshot->national != stocks) {
            hoi5::enforceStorageCapacity(stocks,capacities[owner]);
            snapshot.emplace();
            snapshot->national = stocks;
        }
        auto [stored,inserted] = snapshot->tiles.try_emplace(index);
        if (inserted) stored->second = hoi5::distributeTileStockpile(stocks,capacities[owner],
            hoi5::tileStorageCapacity(tiles[index]));
        return stored->second;
    }

    void rebuildEconomy() {
        auto previousCapacities = std::move(capacities);
        capacities.clear();
        bool addedStorage = false;
        for (int country = 0; country < int(profiles.size()); ++country) {
            auto capacity = hoi5::storageCapacity(tiles,country);
            const bool warehouseMissing = hoi5::value(capacity,"raw") <= 0. &&
                hoi5::value(capacity,"semi_finished") <= 0. && hoi5::value(capacity,"finished") <= 0.;
            const bool fuelMissing = hoi5::value(capacity,"fuel") <= 0.;
            if (warehouseMissing || fuelMissing) {
                int site = capitals[country];
                if (!frontLand(country,site)) {
                    const auto fallback = std::ranges::find_if(tiles,[&](const auto& tile) {
                        return tile.owner == country && !tile.water;
                    });
                    site = fallback == tiles.end() ? -1 : int(fallback-tiles.begin());
                }
                if (site >= 0) {
                    auto& buildings = tiles[site].buildings;
                    if (warehouseMissing) buildings[hoi5::warehouse].area = std::min(.26,buildings[hoi5::warehouse].area+.12);
                    if (fuelMissing) buildings[hoi5::fuelStorage].area = std::min(.34,buildings[hoi5::fuelStorage].area+.14);
                    capacity = hoi5::storageCapacity(tiles,country);
                    addedStorage = true;
                }
            }
            if (country >= int(previousCapacities.size()) || capacity != previousCapacities[country])
                hoi5::enforceStorageCapacity(stockpiles[country],capacity);
            capacities.push_back(std::move(capacity));
        }
        tileStorageSnapshots.assign(profiles.size(),std::nullopt);
        if (addedStorage) hoi5::recalculateSupply(std::span(tiles),size,capitals);
        humanSupply = {};
        double totalSupply = 0.;
        int suppliedLand = 0;
        for (const auto& tile : tiles) {
            if (tile.owner != 0 || tile.water) continue;
            totalSupply += tile.supply;
            ++suppliedLand;
            if (tile.supply < .25) ++humanSupply.critical;
            else if (tile.supply < .50) ++humanSupply.low;
        }
        humanSupply.average = totalSupply/std::max(1,suppliedLand);
        const auto tradeCapacity = hoi5::Market::monthlyCapacity(tiles,profiles);
        humanTradeCapacity = tradeCapacity.empty() ? 0. : tradeCapacity.front();
        production.clear();
        treasury.clear();
        for (int country = 0; country < static_cast<int>(profiles.size()); ++country) {
            production.push_back(hoi5::buildProduction(tiles, country, profiles[country].population, {}));
            treasury.push_back(hoi5::monthlyTreasury(tiles,country,profiles[country].population));
        }
    }

    struct SupplySummary { double average{}; int critical{}, low{}; };
    SupplySummary humanSupply;
    double humanTradeCapacity{};

    void recover(Division& unit,int hours,double multiplier = 1) {
        if (hours <= 0 || unit.organization >= unit.maxOrganization) return;
        const double ratio = std::clamp(unit.organization / std::max(1., unit.maxOrganization), 0., 1.);
        unit.organization = std::min(unit.maxOrganization,
            unit.organization + unit.design->recovery * (1 + .5 * (1 - ratio)) *
            std::clamp(at(unit.q,unit.r).supply,0.,1.) * multiplier * hours / 24.);
    }

    double supplyRatio(const Division& unit) const {
        const auto& tile = at(unit.q,unit.r);
        return std::clamp(tile.supply,0.,1.)*(tile.owner == unit.owner ? 1. : .25);
    }

    struct ResourceForecast {
        hoi5::Production stages;
        hoi5::Stockpile inputs, required, outputs, imports, exports, building, army;
    };

    ResourceForecast forecastResources(int owner,int rotation) const {
        ResourceForecast forecast;
        auto stock = stockpiles[owner];
        hoi5::Stockpile used;
        for (const auto& [key,amount] : stock) used[hoi5::storageBucket(key)] += amount;
        const auto consume = [&](std::string_view key,double requested,hoi5::Stockpile& category) {
            const double amount = std::min(hoi5::value(stock,key),requested);
            if (amount <= 0) return;
            stock[key] -= amount;
            auto& occupied = used[hoi5::storageBucket(key)];
            occupied = std::max(0.,occupied-amount);
            category[key] += amount;
            forecast.inputs[key] += amount;
        };
        const auto supply = [&](std::string_view key,double requested,hoi5::Stockpile& category) {
            const auto bucket = hoi5::storageBucket(key);
            auto& occupied = used[bucket];
            const double free = std::max(0.,hoi5::value(capacities[owner],bucket)-occupied);
            const double amount = std::min(free,requested);
            if (amount <= 0) return;
            stock[key] += amount;
            occupied += amount;
            category[key] += amount;
            forecast.outputs[key] += amount;
        };
        const auto trade = forecastMarketPlan(rotation);
        hoi5::Stockpile imports, exports;
        for (const auto& fill : trade.fills) {
            if (fill.buyer == owner) imports[fill.resource] += fill.amount;
            if (fill.seller == owner) exports[fill.resource] += fill.amount;
        }
        for (const auto& [key,amount] : imports) supply(key,amount,forecast.imports);
        for (const auto& [key,amount] : exports) {
            forecast.required[key] += amount;
            consume(key,amount,forecast.exports);
        }
        for (int stage = 0; stage < hoi5::productionStages; ++stage) {
            const auto& planned = production[owner][stage];
            auto& actual = forecast.stages[stage];
            for (const auto& [key,amount] : planned.inputs) forecast.required[key] += amount;
            if (stage == hoi5::agriculture) {
                const double fertilizer = hoi5::value(planned.inputs,"fertilizer");
                const double bonusFood = hoi5::value(planned.outputs,"food");
                if (fertilizer > 0 && bonusFood > 0) {
                    consume("fertilizer",fertilizer,actual.inputs);
                    const double ratio = std::clamp(hoi5::value(actual.inputs,"fertilizer")/fertilizer,0.,1.);
                    supply("food",bonusFood*ratio,actual.outputs);
                }
                continue;
            }
            double ratio = 1;
            for (const auto& [key,amount] : planned.inputs)
                if (amount > 0) ratio = std::min(ratio,hoi5::value(stock,key)/amount);
            ratio = std::clamp(ratio,0.,1.);
            for (const auto& [key,amount] : planned.inputs)
                consume(key,amount*(stage == hoi5::upkeep ? 1. : ratio),actual.inputs);
            if (stage != hoi5::upkeep)
                for (const auto& [key,amount] : planned.outputs) supply(key,amount*ratio,actual.outputs);
        }
        for (const auto& [key,amount] : construction.monthlyNeeds(tiles,owner,profiles[owner],stock,
             [&](int tile) { return battles.contains(tile); })) {
            forecast.required[key] += amount;
            consume(key,amount,forecast.building);
        }
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
        for (const auto& [key,amount] : military) {
            forecast.required[key] += amount;
            consume(key,amount,forecast.army);
        }
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
        if (tile < 0 || tile >= int(tiles.size())) return false;
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

    static constexpr int baseDivisionTypes = int(std::size(hoi5::divisionTemplates));

    const hoi5::DivisionTemplate& trainingDesign(int type) const {
        return type < baseDivisionTypes ? hoi5::divisionTemplates[type] : playerDesigns[type-baseDivisionTypes]->design;
    }

    hoi5::DivisionComposition trainingComposition(int type) const {
        if (type >= baseDivisionTypes) return playerDesigns[type-baseDivisionTypes]->composition;
        hoi5::DivisionComposition parts{};
        parts[type] = 10;
        return parts;
    }

    static double trainingCost(const hoi5::DivisionTemplate& design) {
        double cost = design.manpower*80.;
        for (const auto& [key,amount] : design.capacity) cost += amount*hoi5::value(hoi5::TRADE_BASE_PRICES,key,100)*.05;
        return std::nearbyint(cost);
    }

    std::string train(int country,int tile,int type) {
        if (type < 0 || type >= baseDivisionTypes+int(playerDesigns.size()) ||
            (country != 0 && type >= baseDivisionTypes)) return "Чужой или неизвестный шаблон";
        if (!safeTrainingSite(country,tile)) return "Нужна своя снабжаемая клетка вне боя";
        const auto& design = trainingDesign(type);
        const double cost = trainingCost(design);
        if (profiles[country].budget < cost || manpowerReserve[country] < design.manpower)
            return "Недостаточно денег или резерва людей";
        auto& stock = stockpiles[country];
        std::string missing;
        int count = 0;
        for (const auto key : hoi5::divisionEquipmentOrder(trainingComposition(type))) {
            const double amount = hoi5::value(design.capacity,key);
            if (hoi5::value(stock,key)+1e-6 >= amount) continue;
            missing += (count ? ", " : "Не хватает: ")+std::string(resourceDisplayName(key));
            if (++count == 3) break;
        }
        if (!missing.empty()) return missing;
        profiles[country].budget -= cost;
        manpowerReserve[country] -= design.manpower;
        for (const auto& [key,amount] : design.capacity) stock[key] = std::max(0.,stock[key]-amount);
        training.push_back({country,tile,type,0,cost,nextTrainingId++});
        diplomacy.record("Начата подготовка дивизии",country);
        news.report(diplomacy.day,"division_training","Начата подготовка дивизии",
            std::string(countryNames[country])+": "+std::string(design.name)+", "+
            std::to_string(design.manpower)+" человек, срок "+std::to_string(trainingHours(design)/24)+" суток.",
            hoi5::NewsPriority::regular,country);
        return "Подготовка начата";
    }

    void cancelTraining(std::size_t index) {
        const auto project = training[index];
        const auto& design = trainingDesign(project.type);
        const double refund = project.cost*std::max(0.,1-project.hours/double(trainingHours(design)));
        profiles[project.country].budget += refund;
        manpowerReserve[project.country] += design.manpower;
        for (const auto& [key,amount] : design.capacity) stockpiles[project.country][key] += amount;
        training.erase(training.begin()+index);
        diplomacy.record("Подготовка дивизии отменена",project.country);
        news.report(diplomacy.day,"division_training_cancelled","Подготовка дивизии отменена",
            std::string(countryNames[project.country])+": "+std::string(design.name)+
            ". Люди и оснащение возвращены; возврат денег "+std::to_string(static_cast<long long>(std::nearbyint(refund)))+".",
            hoi5::NewsPriority::regular,project.country);
    }

    void updateTraining(int hours) {
        if (training.empty()) return;
        for (std::size_t i = training.size(); i > 0; --i) {
            const auto& project = training[i-1];
            if (tiles[project.tile].owner == project.country) continue;
            if (std::ranges::none_of(tiles,[&](const auto& tile) { return tile.owner == project.country && !tile.water; }))
                cancelTraining(i-1);
        }
        struct Deployment { int type, tile, count; };
        std::vector<std::vector<Deployment>> deployed(profiles.size());
        std::erase_if(training,[&](TrainingProject& project) {
            const auto& design = trainingDesign(project.type);
            const int duration = trainingHours(design);
            project.hours = std::min(duration,project.hours+std::max(0,hours));
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
            diplomacy.record("Дивизия завершила подготовку",project.country);
            auto& groups = deployed[project.country];
            auto group = std::ranges::find_if(groups,[&](const Deployment& entry) {
                return entry.type == project.type && entry.tile == project.tile;
            });
            if (group == groups.end()) groups.push_back({project.type,project.tile,1});
            else ++group->count;
            return true;
        });
        for (int country = 0; country < int(deployed.size()); ++country) {
            const auto& groups = deployed[country];
            if (groups.empty()) continue;
            int total = 0;
            for (const auto& group : groups) total += group.count;
            std::string body;
            for (const auto& [type,tile,count] : groups) {
                if (!body.empty()) body += "; ";
                body += trainingDesign(type).name;
                body += total == 1 ? ". Место развёртывания: " : " ×"+std::to_string(count)+" ";
                body += "("+std::to_string(tile%size)+", "+std::to_string(tile/size)+")";
            }
            news.report(diplomacy.day,"division_deployed",total == 1 ? "Дивизия завершила подготовку" :
                "Подготовку завершили дивизии: "+std::to_string(total),
                (total == 1 ? "" : "Развёрнуты: ")+body+".",hoi5::NewsPriority::regular,country);
        }
    }

    int battleAttackDirectionCount(int target,const hoi5::Battle& battle) const {
        const auto isAdjacent = [&](int origin) {
            if (origin < 0) return false;
            const int dq = origin%size-target%size, dr = origin/size-target/size;
            return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)}) == 1;
        };
        std::set<int> origins;
        for (int i : battle.attackers) {
            const auto& unit = divisions[i];
            const int origin = unit.r*size+unit.q;
            if (isAdjacent(origin)) origins.insert(origin);
        }
        if (origins.empty() && isAdjacent(battle.origin)) origins.insert(battle.origin);
        return std::max(1,int(origins.size()));
    }

    void rebalanceBattle(int target,hoi5::Battle& battle) {
        battle.width = 80.+40.*(battleAttackDirectionCount(target,battle)-1);
        const auto rebalance = [&](const std::vector<int>& side,std::vector<int>& front) {
            std::vector<int> candidates;
            for (int i : side) {
                auto& unit = divisions[i];
                unit.combat.widthEfficiency = 1.;
                if (unit.combat.recovering && unit.organization >= unit.maxOrganization*.30)
                    unit.combat.recovering = false;
                if (unit.combat.strength > 0 && unit.organization > 0 && !unit.combat.recovering)
                    candidates.push_back(i);
            }
            std::ranges::sort(candidates,[&](int a,int b) {
                return std::tuple{-divisions[a].combat.initiative,a} < std::tuple{-divisions[b].combat.initiative,b};
            });
            front.clear();
            double used = 0.;
            for (int i : candidates) {
                auto& stats = divisions[i].combat;
                const double width = std::max(1.,stats.width);
                const double share = std::min(1.,std::max(0.,battle.width-used)/width);
                if (share < .6) continue;
                front.push_back(i);
                stats.widthEfficiency = share;
                used += width*share;
            }
        };
        rebalance(battle.attackers,battle.activeAttackers);
        rebalance(battle.defenders,battle.activeDefenders);
    }

    bool detachDivisionFromBattle(int index) {
        auto& unit = divisions[index];
        if (unit.battle < 0) return false;
        const int target = unit.battle;
        const auto entry = battles.find(target);
        unit.battle = -1;
        unit.combat.recovering = false;
        unit.combat.widthEfficiency = 1.;
        unit.postBattleRoute.clear();
        if (entry == battles.end()) return true;

        auto& battle = entry->second;
        std::erase(battle.attackers,index);
        std::erase(battle.defenders,index);
        if (!battle.attackers.empty()) rebalanceBattle(target,battle);
        else {
            for (int defender : battle.defenders) {
                divisions[defender].battle = -1;
                divisions[defender].combat.recovering = false;
                divisions[defender].combat.widthEfficiency = 1.;
            }
            battles.erase(entry);
        }
        return true;
    }

    bool cancelDivisionOrdersOnTile(const std::set<int>& selection,int tile) {
        bool changed = false;
        for (int index : selection) {
            if (!selectableDivision(0,index)) continue;
            auto& unit = divisions[index];
            if (unit.r*size+unit.q != tile || unit.retreating || unit.combat.strength <= 0) continue;
            if (unit.attackRoute) changed |= detachDivisionFromBattle(index);
            if (unit.route.empty() && unit.postBattleRoute.empty() && !unit.attackRoute) continue;
            unit.route.clear();
            unit.postBattleRoute.clear();
            unit.attackRoute = false;
            unit.progress = unit.visualProgress = 0;
            unit.manualFrontHours = 24;
            unit.assignedFrontPost = -1;
            changed = true;
        }
        return changed;
    }

    bool selectableDivision(int owner,int index) const {
        return index >= 0 && index < int(divisions.size()) && divisions[index].owner == owner &&
            divisions[index].combat.strength > 0;
    }

    std::vector<int> armyMembers(int owner,int armyId) const {
        std::vector<int> members;
        for (int i = 0; i < int(divisions.size()); ++i)
            if (selectableDivision(owner,i) && divisions[i].armyId == armyId) members.push_back(i);
        return members;
    }

    int addDivisionsToArmy(int owner,int armyId,const std::set<int>& selection) {
        const auto army = std::ranges::find(armies,armyId,&Army::id);
        if (army == armies.end() || army->owner != owner) return 0;
        const int free = armyCapacity-int(armyMembers(owner,armyId).size());
        int added = 0;
        for (int index : selection) {
            if (added >= free) break;
            if (!selectableDivision(owner,index) || divisions[index].armyId) continue;
            divisions[index].armyId = armyId;
            ++added;
        }
        return added;
    }

    int createArmy(int owner,const std::set<int>& selection) {
        if (!std::ranges::any_of(selection,[&](int index) {
            return selectableDivision(owner,index) && divisions[index].armyId == 0;
        })) return 0;
        const int id = armies.empty() ? 1 : std::ranges::max(armies,{},&Army::id).id+1;
        const int number = 1+int(std::ranges::count(armies,owner,&Army::owner));
        armies.push_back({id,owner,"Армия "+std::to_string(number)});
        addDivisionsToArmy(owner,id,selection);
        return id;
    }

    void detachDivisionsFromArmy(int owner,const std::set<int>& selection) {
        for (int index : selection) {
            if (!selectableDivision(owner,index)) continue;
            divisions[index].armyId = 0;
            divisions[index].assignedFrontPost = -1;
        }
    }

    void orderSelectedDivisions(const std::set<int>& selection,int tile,bool append) {
        if (tile < 0 || tile >= int(tiles.size()) || cancelDivisionOrdersOnTile(selection,tile)) return;
        for (int index : selection) {
            if (!selectableDivision(0,index)) continue;
            auto& unit = divisions[index];
            if (unit.r*size+unit.q == tile || unit.retreating || unit.combat.strength <= 0 ||
                unit.organization < unit.maxOrganization*.30) continue;
            detachDivisionFromBattle(index);
            if (orderMove(unit,tile,append)) {
                unit.manualFrontHours = 24;
                unit.assignedFrontPost = -1;
            }
        }
    }

    template<class Visit>
    void forFrontNeighbor(int index,Visit visit) const {
        const int q = index%size, r = index/size, shift = r%2;
        for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
            {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
        }})
            if (contains(q+dq,r+dr)) visit((r+dr)*size+q+dq);
    }

    int frontDistance(int a,int b) const {
        const int ar = a/size, br = b/size;
        const int dq = a%size-ar/2-(b%size-br/2), dr = ar-br;
        return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
    }

    bool frontLand(int owner,int index) const {
        return index >= 0 && index < int(tiles.size()) && tiles[index].owner == owner && !tiles[index].water;
    }

    int frontBorderOwner(int owner,int tile) const {
        if (!frontLand(owner,tile)) return -2;
        int result = -2;
        forFrontNeighbor(tile,[&](int neighbor) {
            const auto& other = tiles[neighbor];
            if (other.water || other.owner == owner) return;
            if (result == -2 || (other.owner >= 0 && diplomacy.hostile(owner,other.owner))) result = other.owner;
        });
        return result;
    }

    bool bordersFrontOwner(int owner,int tile,int opponent) const {
        if (!frontLand(owner,tile)) return false;
        bool borders = false;
        forFrontNeighbor(tile,[&](int neighbor) { borders |= !tiles[neighbor].water && tiles[neighbor].owner == opponent; });
        return borders;
    }

    std::vector<int> collectArmyFront(int owner,int seed,int opponent) const {
        if (!bordersFrontOwner(owner,seed,opponent)) return {};
        std::vector<int> line{seed};
        std::set<int> visited{seed};
        for (std::size_t i = 0; i < line.size(); ++i)
            forFrontNeighbor(line[i],[&](int tile) {
                if (bordersFrontOwner(owner,tile,opponent) && visited.insert(tile).second) line.push_back(tile);
            });
        return line;
    }

    bool setArmyFront(int owner,int armyId,std::vector<int> line,bool automatic,bool borderOnly) {
        const auto army = std::ranges::find(armies,armyId,&Army::id);
        if (army == armies.end() || army->owner != owner || line.empty()) return false;
        const int opponent = borderOnly ? frontBorderOwner(owner,line.front()) : -2;
        if (borderOnly && opponent == -2) return false;
        if (automatic) line = collectArmyFront(owner,line.front(),opponent);
        else {
            std::set<int> seen;
            std::erase_if(line,[&](int tile) {
                return !frontLand(owner,tile) || (borderOnly && !bordersFrontOwner(owner,tile,opponent)) ||
                    !seen.insert(tile).second;
            });
        }
        if (line.empty()) return false;
        army->front = std::move(line);
        if (!borderOnly) army->offensive.clear();
        army->automaticLine = automatic;
        army->borderOwner = opponent;
        army->reviewHours = 6;
        army->executing = true;
        return true;
    }

    bool setArmyOffensive(int owner,int armyId,std::vector<int> line) {
        const auto army = std::ranges::find(armies,armyId,&Army::id);
        if (army == armies.end() || army->owner != owner) return false;
        std::set<int> seen;
        std::erase_if(line,[&](int tile) {
            return tile < 0 || tile >= int(tiles.size()) || tiles[tile].water || tiles[tile].owner == owner ||
                !seen.insert(tile).second;
        });
        if (line.empty()) return false;
        if (army->borderOwner == -2) army->front.clear();
        army->offensive = std::move(line);
        army->reviewHours = 6;
        return true;
    }

    void clearArmyFront(int owner,int armyId) {
        const auto army = std::ranges::find(armies,armyId,&Army::id);
        if (army == armies.end() || army->owner != owner) return;
        army->front.clear();
        army->offensive.clear();
        army->executing = false;
        for (int index : armyMembers(owner,armyId)) {
            auto& unit = divisions[index];
            if (unit.assignedFrontPost < 0) continue;
            unit.assignedFrontPost = -1;
            if (unit.battle >= 0 || unit.retreating || unit.manualFrontHours) continue;
            unit.route.clear();
            unit.progress = unit.visualProgress = 0.;
        }
    }

    void toggleArmyFront(int owner,int armyId) {
        const auto army = std::ranges::find(armies,armyId,&Army::id);
        if (army == armies.end() || army->owner != owner || (army->front.empty() && army->offensive.empty())) return;
        army->executing = !army->executing;
        army->reviewHours = 6;
    }

    bool validArmyPost(const Army& army,int tile) const {
        return frontLand(army.owner,tile) && (army.borderOwner == -2 || bordersFrontOwner(army.owner,tile,army.borderOwner));
    }

    void refreshArmyFront(Army& army) {
        const auto valid = [&](int tile) { return validArmyPost(army,tile); };
        if (army.automaticLine) {
            const auto previous = std::ranges::find_if(army.front,valid);
            int seed = previous == army.front.end() ? -1 : *previous;
            if (seed < 0)
                for (int tile : army.front) {
                    forFrontNeighbor(tile,[&](int next) {
                        if (seed < 0 && valid(next)) seed = next;
                    });
                    if (seed >= 0) break;
                }
            if (seed >= 0) army.front = collectArmyFront(army.owner,seed,army.borderOwner);
        }
    }

    void refreshArmyFrontsAfterCapture() {
        if (frontOwnershipChanges.empty()) return;
        std::set<int> impacted(frontOwnershipChanges.begin(),frontOwnershipChanges.end());
        for (int tile : frontOwnershipChanges)
            forFrontNeighbor(tile,[&](int neighbor) { impacted.insert(neighbor); });
        for (auto& army : armies) {
            if (army.borderOwner == -2 || army.front.empty()) continue;
            if (std::ranges::none_of(army.front,[&](int old) {
                return std::ranges::any_of(frontOwnershipChanges,[&](int tile) { return frontDistance(old,tile) <= 3; });
            })) continue;
            const auto valid = [&](int tile) { return validArmyPost(army,tile); };
            std::vector<int> updated;
            if (army.automaticLine) {
                int seed = -1, best = 999;
                const auto consider = [&](int tile) {
                    if (!valid(tile)) return;
                    const int distance = frontDistance(tile,army.front.front());
                    if (distance < best) { seed = tile; best = distance; }
                };
                for (int tile : frontOwnershipChanges) consider(tile);
                if (seed < 0)
                    for (int tile : frontOwnershipChanges) forFrontNeighbor(tile,consider);
                if (seed >= 0) updated = collectArmyFront(army.owner,seed,army.borderOwner);
            } else {
                std::set<int> appended;
                for (int old : army.front) {
                    if (frontLand(army.owner,old) && (!impacted.contains(old) || valid(old)) &&
                        appended.insert(old).second) updated.push_back(old);
                    for (int tile : frontOwnershipChanges)
                        if (frontDistance(old,tile) == 1 && valid(tile) && appended.insert(tile).second)
                            updated.push_back(tile);
                }
            }
            if (!updated.empty() || !army.automaticLine) army.front = std::move(updated);
            army.reviewHours = 6;
        }
        frontOwnershipChanges.clear();
    }

    void distributeArmyFront(Army& army) {
        const auto members = armyMembers(army.owner,army.id);
        if (members.empty() || army.front.empty()) return;
        const auto valid = [&](int tile) { return validArmyPost(army,tile); };
        std::vector<int> component(tiles.size(),-1);
        std::map<int,std::vector<int>> groups;
        for (int seed : army.front) {
            if (!valid(seed)) continue;
            if (component[seed] < 0) {
                std::vector<int> queue{seed};
                component[seed] = seed;
                for (std::size_t i = 0; i < queue.size(); ++i)
                    forFrontNeighbor(queue[i],[&](int next) {
                        if (!frontLand(army.owner,next) || component[next] >= 0) return;
                        component[next] = seed;
                        queue.push_back(next);
                    });
            }
            groups[component[seed]].push_back(seed);
        }
        std::map<int,std::vector<int>> unitsAt;
        for (int index = 0; index < int(divisions.size()); ++index) {
            const auto& unit = divisions[index];
            if (unit.combat.strength > 0.) unitsAt[unit.r*size+unit.q].push_back(index);
        }
        const auto attack = [](const Division& unit) {
            const double strength = std::clamp(unit.combat.strength/std::max(1.,unit.design->combat.strength),0.,1.);
            const double org = std::clamp(unit.organization/std::max(1.,unit.maxOrganization),0.,1.);
            const double supply = std::clamp(unit.lastSupplyRatio,0.,1.);
            return (unit.combat.softAttack+unit.combat.frontAttack+unit.combat.topAttack)*
                strength*(.25+.75*org)*(.35+.65*supply);
        };
        for (const auto& [group,tilesOnFront] : groups) {
            struct Post {
                int tile;
                double priority, threat;
                std::set<int> opponents;
                bool active{};
                int count{}, quota{};
            };
            std::vector<Post> posts;
            for (int tile : tilesOnFront) {
                double threat = 0.;
                const auto nearby = [&](int cell) {
                    for (int index : unitsAt[cell]) {
                        const auto& enemy = divisions[index];
                        if (diplomacy.hostile(army.owner,enemy.owner) || diplomacy.goals.contains({enemy.owner,army.owner}))
                            threat += attack(enemy);
                    }
                };
                nearby(tile);
                forFrontNeighbor(tile,nearby);
                const bool occupied = std::ranges::any_of(unitsAt[tile],[&](int index) { return divisions[index].owner == army.owner; });
                const bool previous = std::ranges::any_of(members,[&](int index) { return divisions[index].assignedFrontPost == tile; });
                const auto& fort = tiles[tile].buildings[hoi5::fortification];
                const double terrain = std::clamp(tiles[tile].movementCost-1.,0.,2.)*.5+fort.area*fort.health;
                Post post{tile,2.+tiles[tile].supply+(occupied ? 2. : 0.)+previous+threat/20+terrain,threat};
                forFrontNeighbor(tile,[&](int neighbor) {
                    const auto& border = tiles[neighbor];
                    if (border.water || border.owner < 0 || border.owner == army.owner) return;
                    const bool hostile = diplomacy.hostile(army.owner,border.owner);
                    if (hostile || diplomacy.goals.contains({border.owner,army.owner})) post.opponents.insert(border.owner);
                    post.active |= hostile;
                });
                posts.push_back(std::move(post));
            }
            std::ranges::sort(posts,[](const Post& a,const Post& b) {
                return a.priority != b.priority ? a.priority > b.priority : a.tile < b.tile;
            });
            std::vector<int> available;
            int unitCount = 0;
            for (int index : members) {
                const auto& unit = divisions[index];
                const int cell = unit.r*size+unit.q;
                if (component[cell] != group || unit.retreating) continue;
                const bool busy = unit.manualFrontHours || unit.battle >= 0 || !unit.route.empty() ||
                    unit.organization < unit.maxOrganization*.30;
                if (busy) {
                    const int tile = !unit.manualFrontHours && !unit.route.empty() ? unit.route.back() : cell;
                    const auto post = std::ranges::find(posts,tile,&Post::tile);
                    if (post == posts.end()) continue;
                    ++post->count;
                } else available.push_back(index);
                ++unitCount;
            }
            if (available.empty()) continue;
            const bool pressured = std::ranges::any_of(posts,[](const Post& post) { return post.threat > 0.; });
            int allocated = 0;
            std::set<int> coveredOpponents;
            for (const bool active : {true,false})
                for (auto& post : posts)
                    if (allocated < unitCount && post.active == active &&
                        std::ranges::any_of(post.opponents,[&](int opponent) { return !coveredOpponents.contains(opponent); })) {
                        post.quota = 1;
                        ++allocated;
                        coveredOpponents.insert(post.opponents.begin(),post.opponents.end());
                    }
            for (auto& post : posts)
                if (allocated < unitCount && !post.quota && (!pressured || post.threat > 0.)) {
                    post.quota = 1;
                    ++allocated;
                }
            const int concentrations = int(std::ranges::count_if(posts,[&](const Post& post) {
                return post.quota && (!pressured || post.threat > 0.);
            }));
            const int cap = concentrations <= 1 ? unitCount : std::max(2,(unitCount+1)/2);
            for (; allocated < unitCount; ++allocated) {
                Post* best = nullptr;
                for (auto& post : posts) {
                    if (!post.quota || post.quota >= cap || (pressured && post.threat <= 0.)) continue;
                    if (!best || post.priority/(1+post.quota) > best->priority/(1+best->quota)) best = &post;
                }
                if (!best) break;
                ++best->quota;
            }
            std::erase_if(available,[&](int index) {
                auto& unit = divisions[index];
                const auto post = std::ranges::find(posts,unit.r*size+unit.q,&Post::tile);
                if (post == posts.end() || post->count >= post->quota) return false;
                ++post->count;
                unit.assignedFrontPost = post->tile;
                return true;
            });
            const auto fill = [&](Post& post) {
                std::vector<int> candidates;
                for (int index : available) {
                    const auto& unit = divisions[index];
                    const auto source = std::ranges::find(posts,unit.r*size+unit.q,&Post::tile);
                    if (source == posts.end() || post.count == 0 ||
                        (source->count > 0 && source->tile != post.tile && post.threat > 1.5*source->threat+10))
                        candidates.push_back(index);
                }
                while (!candidates.empty()) {
                    const auto best = std::ranges::min_element(candidates,{},[&](int index) {
                        const auto& unit = divisions[index];
                        return frontDistance(unit.r*size+unit.q,post.tile)-(unit.assignedFrontPost == post.tile ? 2 : 0);
                    });
                    const int index = *best;
                    auto& unit = divisions[index];
                    candidates.erase(best);
                    if (!orderMove(unit,post.tile)) continue;
                    std::erase(available,index);
                    unit.assignedFrontPost = post.tile;
                    ++post.count;
                    return true;
                }
                return false;
            };
            for (auto& post : posts) if (post.quota && !post.count) fill(post);
            for (auto& post : posts) while (post.count < post.quota && fill(post)) {}
        }
    }

    void executeArmyOffensive(Army& army) {
        std::vector<int> front;
        for (int tile : army.front) if (validArmyPost(army,tile)) front.push_back(tile);
        if (front.empty()) return;
        const auto members = armyMembers(army.owner,army.id);
        std::vector<int> available;
        std::vector<int> sourceCounts(tiles.size()), allied(tiles.size()), enemy(tiles.size()), pressure(tiles.size());
        const auto position = [&](int index) { return divisions[index].r*size+divisions[index].q; };
        for (int index : members) {
            const auto& unit = divisions[index];
            if (!unit.retreating) ++sourceCounts[position(index)];
            if (!unit.retreating && !unit.manualFrontHours && unit.battle < 0 && unit.route.empty() &&
                unit.postBattleRoute.empty() && unit.organization >= unit.maxOrganization*.30)
                available.push_back(index);
        }
        if (available.empty()) return;
        for (int i = 0; i < int(divisions.size()); ++i) {
            const auto& unit = divisions[i];
            if (unit.combat.strength <= 0) continue;
            const int tile = position(i);
            if (unit.owner == army.owner) {
                if (!unit.retreating) ++allied[tile];
            } else {
                ++pressure[tile];
                forFrontNeighbor(tile,[&](int next) { ++pressure[next]; });
                if (diplomacy.hostile(army.owner,unit.owner)) ++enemy[tile];
            }
        }
        const auto weightedTargets = [&](const std::vector<int>& line,int count) {
            if (count >= int(line.size())) return line;
            std::vector<double> cumulative;
            double total = 0.;
            for (int tile : line) {
                total += 1.+std::min(4,pressure[tile])*.65;
                cumulative.push_back(total);
            }
            std::vector<int> selected;
            std::set<int> used;
            for (int i = 0; i < count; ++i) {
                const auto at = std::ranges::lower_bound(cumulative,(i+.5)*total/count);
                const int tile = line[at-cumulative.begin()];
                if (used.insert(tile).second) selected.push_back(tile);
            }
            for (int tile : line) {
                if (int(selected.size()) >= count) break;
                if (used.insert(tile).second) selected.push_back(tile);
            }
            return selected;
        };
        const auto assign = [&](const std::vector<int>& units,const std::vector<int>& targets) {
            std::vector<std::tuple<int,int,int>> pairs;
            for (int index : units)
                for (int i = 0; i < int(targets.size()); ++i)
                    pairs.emplace_back(frontDistance(position(index),targets[i]),index,i);
            std::ranges::sort(pairs);
            std::map<int,int> assignments;
            std::set<int> used;
            for (const auto& [distance,index,target] : pairs)
                if (!assignments.contains(index) && used.insert(target).second) assignments.emplace(index,targets[target]);
            return assignments;
        };
        const auto nearestFront = [&](int tile) {
            return *std::ranges::min_element(front,{},[&](int post) { return frontDistance(tile,post); });
        };
        const auto holders = weightedTargets(front,int(available.size()));
        const auto holderAssignments = assign(available,holders);
        bool ready = true;
        std::vector<int> attacking, staging;
        for (int index : available) {
            const int tile = position(index);
            const bool nearFront = frontDistance(tile,nearestFront(tile)) <= 1;
            if (const auto holder = holderAssignments.find(index); holder != holderAssignments.end()) {
                const int target = holder->second;
                if ((!nearFront || sourceCounts[target] == 0) && frontDistance(tile,target) > 1 &&
                    orderMove(divisions[index],target)) {
                    divisions[index].assignedFrontPost = target;
                    ready = false;
                }
            } else if (!nearFront) staging.push_back(index);
            if (nearFront) attacking.push_back(index);
        }
        if (!ready || attacking.empty()) return;
        for (const auto& [index,target] : assign(staging,holders))
            if (frontDistance(position(index),target) > 1 && orderMove(divisions[index],target))
                divisions[index].assignedFrontPost = target;

        const auto assignments = assign(attacking,weightedTargets(army.offensive,int(attacking.size())));
        struct Order { int index, source, target; bool endpoint, coordinated{}; };
        std::vector<Order> orders;
        for (int index : attacking) {
            const auto assigned = assignments.find(index);
            const auto distance = [&](int tile) {
                if (assigned != assignments.end()) return frontDistance(tile,assigned->second);
                int closest = 999;
                for (int goal : army.offensive) closest = std::min(closest,frontDistance(tile,goal));
                return closest;
            };
            const int source = position(index), currentDistance = distance(source);
            const auto rank = [&](int tile) {
                const int steps = distance(tile);
                return std::tuple{steps >= currentDistance,steps,pressure[tile],tile};
            };
            int target = -1;
            forFrontNeighbor(source,[&](int tile) {
                if (tiles[tile].water || tiles[tile].owner == army.owner ||
                    (tiles[tile].owner >= 0 && !diplomacy.hostile(army.owner,tiles[tile].owner))) return;
                if (target < 0 || rank(tile) < rank(target)) target = tile;
            });
            if (target < 0) continue;
            const int post = nearestFront(source);
            orders.push_back({index,source,target,front.size() >= 2 && (post == front.front() || post == front.back())});
        }
        for (auto& order : orders)
            order.coordinated = std::ranges::any_of(orders,[&](const Order& other) {
                return &other != &order && frontDistance(order.target,other.target) <= 1;
            });
        std::ranges::sort(orders,{},[&](const Order& order) {
            return std::tuple{enemy[order.target] == 0,!order.coordinated,order.index};
        });
        std::map<int,int> sent, planned;
        for (const auto& order : orders) {
            const bool emptyPush = enemy[order.target] == 0;
            const int limit = emptyPush ? 1 : std::min(3,enemy[order.target]+1);
            const int sourceCount = sourceCounts[order.source];
            if (allied[order.target]+planned[order.target] >= limit) continue;
            if (emptyPush && sourceCount <= 1 && (!order.coordinated || order.endpoint)) continue;
            if (sent[order.source] >= std::max(1,sourceCount-int(emptyPush))) continue;
            if (!orderMove(divisions[order.index],order.target)) continue;
            auto& unit = divisions[order.index];
            unit.route.resize(1);
            const int nextOwner = tiles[unit.route.front()].owner;
            unit.attackRoute = nextOwner >= 0 && diplomacy.hostile(unit.owner,nextOwner);
            unit.assignedFrontPost = order.source;
            ++sent[order.source];
            ++planned[order.target];
        }
    }

    void advanceManualFrontTimers(int hours) {
        if (hours <= 0) return;
        for (auto& unit : divisions)
            if (unit.route.empty() && unit.postBattleRoute.empty() && unit.battle < 0)
                unit.manualFrontHours = std::max(0,unit.manualFrontHours-hours);
    }

    void updateArmyFronts(int hours) {
        if (hours <= 0) return;
        for (auto& army : armies) {
            if (!army.executing) continue;
            if (std::ranges::any_of(supplyBots,[&](const auto& bot) { return bot.owner == army.owner; }))
                continue;
            army.reviewHours += hours;
            if (army.reviewHours < 6) continue;
            army.reviewHours = 0;
            refreshArmyFront(army);
            if (army.offensive.empty()) distributeArmyFront(army);
            else executeArmyOffensive(army);
        }
    }

    bool joinBattle(int target,int index) {
        auto& unit = divisions[index];
        if (unit.battle >= 0 || tiles[target].water || !diplomacy.hostile(unit.owner,tiles[target].owner))
            return false;
        auto [entry,created] = battles.try_emplace(target,hoi5::Battle{unit.owner,tiles[target].owner});
        auto& battle = entry->second;
        if (created) {
            battle.origin = unit.r*size+unit.q;
            battle.creationOrder = nextBattleOrder++;
        }
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
            member.combat.recovering = false;
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
        rebalanceBattle(target,battle);
        return true;
    }

    void destroyDivision(Division& unit) {
        unit.combat.strength = 0.;
        if (unit.destructionReported) return;
        unit.destructionReported = true;
        news.batchNotice(diplomacy.day,unit.owner,"division_destroyed","Потеря дивизии",
            "Соединение «"+std::string(unit.design->name)+"» потеряно. Проверьте обстановку на фронте.",true);
    }

    void transferTile(int index,int country) {
        auto& tile = tiles[index];
        const int previous = tile.owner;
        if (previous == country) return;
        air.transferTile(index,previous,country);
        tile.owner = country;
        for (auto& bot : supplyBots)
            if (bot.owner == previous || bot.owner == country) bot.urgent = true;
        frontOwnershipChanges.push_back(index);
        propagateWaterOwnership(index);
        const auto location = "("+std::to_string(index%size)+", "+std::to_string(index/size)+")";
        if (previous >= 0) {
            news.batchNotice(diplomacy.day,previous,"territory_lost","Потеря территории",
                "Участок "+location+" перешёл под контроль "+std::string(countryNames[country])+".",true);
            if (std::ranges::none_of(tiles,[&](const auto& cell) { return cell.owner == previous; }))
                news.report(diplomacy.day,"country_defeated",std::string(countryNames[previous])+" потеряла всю территорию",
                    "У страны "+std::string(countryNames[previous])+" больше нет подконтрольных участков карты.",
                    hoi5::NewsPriority::critical);
        }
        news.batchNotice(diplomacy.day,country,"territory_gained","Получен контроль над территорией",
            "Наши силы контролируют участок "+location+".");
    }

    bool damageBuilding(int index,hoi5::Building building,double amount) {
        auto& tile = tiles[index];
        const double before = tile.buildings[building].health;
        if (!construction.damageBuilding(tile,index,building,amount)) return false;
        const std::string_view name = building == hoi5::supplyDepot ? "пункт снабжения" :
            building == hoi5::fuelStorage ? "топливохранилище" : building == hoi5::port ? "порт" : "";
        if (!name.empty() && tile.owner >= 0) {
            news.recordLogisticsDamage(diplomacy.day,tile.owner,countryNames[tile.owner],index%size,index/size,index,
                name,before,tile.buildings[building].health);
        }
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
            std::array<double,hoi5::buildingCount> cumulative{};
            std::partial_sum(weights.begin(),weights.end(),cumulative.begin());
            const double roll = groundCombatRandom.uniform()*cumulative.back();
            const auto last = std::ranges::lower_bound(cumulative,cumulative.back());
            return static_cast<hoi5::Building>(
                std::upper_bound(cumulative.begin(),last,roll)-cumulative.begin());
        };
        const auto primary = pick();
        bool changed = damageBuilding(target,primary,damage);
        if (available > 1 && groundCombatRandom.uniform() < .25+intensity*.25) {
            weights[primary] = 0;
            changed |= damageBuilding(target,pick(),damage*.45);
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

    bool tickBattles(int hours,bool& infrastructureChanged,hoi5::DebugProfiler* debug) {
        bool changed = false;
        std::vector<decltype(battles)::iterator> ordered;
        ordered.reserve(battles.size());
        for (auto it = battles.begin(); it != battles.end(); ++it) ordered.push_back(it);
        std::ranges::stable_sort(ordered,{},[](auto entry) { return entry->second.creationOrder; });
        for (auto it : ordered) {
            const int target = it->first;
            auto& battle = it->second;
            for (const auto* side : {&battle.attackers,&battle.defenders})
                for (int index : *side) {
                    auto& markers = divisions[index].airGroundSuppression;
                    for (auto& [owner,remaining] : markers) remaining -= hours;
                    std::erase_if(markers,[](const auto& marker) { return marker.second <= 0; });
                }
            const auto alive = [&](int i) { return divisions[i].combat.strength > 0; };
            const bool war = diplomacy.hostile(battle.attacker,battle.defender);
            if (war) {
                {
                    hoi5::DebugMeasure timing(debug,"battle_recover_reinforce");
                    const auto recoverReserves = [&](const auto& side,const auto& front) {
                        for (int i : side)
                            if (alive(i) && std::ranges::find(front,i) == front.end()) recover(divisions[i],hours,.25);
                    };
                    recoverReserves(battle.attackers,battle.activeAttackers);
                    recoverReserves(battle.defenders,battle.activeDefenders);
                    rebalanceBattle(target,battle);
                }
                const auto& attackers = battle.activeAttackers;
                const auto& defenders = battle.activeDefenders;
                const int activeCount = int(attackers.size()+defenders.size());
                battle.organizationDamage = {};
                battle.strengthDamage = {};
                {
                    hoi5::DebugMeasure timing(debug,"battle_attack_phase");
                    const auto attack = [&](const std::vector<int>& side,const std::vector<int>& targets,bool defending) {
                        for (int i : side) {
                            if (targets.empty()) break;
                            auto& attacker = divisions[i];
                            auto& defender = divisions[targets[groundCombatRandom.below(std::uint32_t(targets.size()))]];
                            const auto& fort = tiles[target].buildings[hoi5::fortification];
                            const double armor = attacker.combat.vehicles;
                            const double bonus = defending && tiles[target].owner == defender.owner
                                ? fort.area*fort.health*(.3+.7*tiles[target].supply)*(.60*(1-armor)+.25*armor) : 0;
                            const double airBonus = defending ? 0. : breakthroughAirBonus(battle,defender.owner,target);
                            const auto ammo = attacker.attackSupplies(hours);
                            const auto terrain = hoi5::groundTerrainEffects(tiles[target].natural,armor);
                            const double damage = hoi5::combatDamage(attacker.combat,defender.combat,defending,
                                ammo,supplyRatio(attacker),bonus,airBonus,defending ? terrain.attack : 1.,
                                defending ? terrain.defense : 1.);
                            const double strengthLoss = std::min(defender.combat.strength,damage*.35);
                            defender.organization = std::max(0.,defender.organization-damage);
                            defender.loseStrength(strengthLoss);
                            battle.organizationDamage[defending] += damage;
                            battle.strengthDamage[defending] += strengthLoss;
                        }
                    };
                    attack(attackers,defenders,true);
                    attack(defenders,attackers,false);
                }
                news.recordBattleLoss(diplomacy.day,target,0,battle.attacker,countryNames[battle.attacker],
                    countryNames[battle.defender],battle.strengthDamage[0]);
                news.recordBattleLoss(diplomacy.day,target,1,battle.defender,countryNames[battle.defender],
                    countryNames[battle.attacker],battle.strengthDamage[1]);
                {
                    hoi5::DebugMeasure timing(debug,"battle_collateral");
                    infrastructureChanged |= battleCollateral(target,hours,activeCount,
                        battle.organizationDamage[0]+battle.organizationDamage[1],
                        battle.strengthDamage[0]+battle.strengthDamage[1]);
                }
                {
                    hoi5::DebugMeasure timing(debug,"battle_cleanup");
                    for (const auto* front : {&attackers,&defenders})
                        for (int i : *front)
                            if (alive(i) && divisions[i].organization <= 0)
                                divisions[i].combat.recovering = true;
                    for (auto* side : {&battle.attackers,&battle.defenders})
                        std::erase_if(*side,[&](int i) {
                            if (alive(i)) return false;
                            auto& unit = divisions[i];
                            destroyDivision(unit);
                            unit.battle = -1;
                            unit.postBattleRoute.clear();
                            unit.combat.widthEfficiency = 1.;
                            return true;
                        });
                }
                {
                    hoi5::DebugMeasure timing(debug,"battle_rebalance");
                    rebalanceBattle(target,battle);
                }
                if (!attackers.empty() && defenders.empty()) battle.advance = std::min(1.25,battle.advance+.035*hours);
                if (!attackers.empty() && !defenders.empty()) battle.advance = std::max(0.,battle.advance-.05*hours);
            }
            const bool captured = war && battle.advance >= 1;
            if (war && !captured && std::any_of(battle.attackers.begin(),battle.attackers.end(),alive)) continue;
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
                std::erase(unit.route,target);
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
                unit.attackRoute = false;
                if (!captured || !alive(i)) continue;
                unit.route.clear();
                const int q = target % size, r = target / size, shift = r % 2;
                int retreat = -1;
                for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
                    {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
                }}) {
                    if (!contains(q+dq,r+dr)) continue;
                    const int next = (r+dr)*size+q+dq;
                    if (tiles[next].owner != unit.owner || tiles[next].water || defended(next,unit.owner)) continue;
                    if (retreat < 0 || tiles[next].supply > tiles[retreat].supply) retreat = next;
                }
                if (retreat < 0) destroyDivision(unit);
                else {
                    unit.q = q;
                    unit.r = r;
                    unit.route.push_back(retreat);
                    unit.retreating = true;
                    unit.organization = unit.progress = unit.visualProgress = 0.;
                }
            }
            if (captured) {
                transferTile(target,battle.attacker);
                for (auto& unit : divisions)
                    if (unit.r*size+unit.q == target && unit.owner != battle.attacker &&
                        !unit.retreating && unit.combat.strength > 0) destroyDivision(unit);
                changed = bordersChanged = true;
            }
            battles.erase(it);
        }
        return changed;
    }

    bool advanceBattles(int hours,bool& infrastructureChanged,hoi5::DebugProfiler* debug = nullptr) {
        bool changed = false;
        for (int hour = 0; hour < hours && !battles.empty(); ++hour)
            changed |= tickBattles(1,infrastructureChanged,debug);
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
    double airWingDisplayRange(const hoi5::AirWing& wing) const {
        double range = 0;
        for (int aircraft = 0; aircraft < int(std::size(hoi5::aircraftTypes)); ++aircraft)
            if (wing.typeCount(aircraft) > 0) range = std::max(range,hoi5::aircraftTypes[aircraft].range);
        return range;
    }

    bool airWingCanReach(const hoi5::AirWing& wing,int target,int type = -1) const {
        if (target < 0 || target >= int(tiles.size()) || wing.base < 0 || wing.base >= int(tiles.size()))
            return false;
        const auto x = [&](int tile) { return (tile%size+.5*((tile/size)%2))*std::sqrt(3.); };
        const double range = type >= 0 ? hoi5::aircraftTypes[type].range : airWingDisplayRange(wing);
        return std::hypot(x(wing.base)-x(target),1.5*(wing.base/size-target/size))
            <= range*std::sqrt(3.);
    }

    enum class AirAreaEdit { replace, add, remove };

    bool assignAirWingTarget(hoi5::AirWing& wing,int target,AirAreaEdit edit = AirAreaEdit::replace) const {
        if (target < 0 || target >= int(tiles.size()) || wing.count <= 0) return false;
        if (edit != AirAreaEdit::remove && !airWingCanReach(wing,target)) return false;
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
        addAirVisual(wing.owner,wing.base,flight ? origin : target,type);
        wing.lastMissionTarget[strategic] = target;
        auto& targetCooldown = wing.missionTargetCooldowns[strategic][target];
        targetCooldown = std::max(targetCooldown,strategic ? 18. : 6.);
        return sorties;
    }

    using SortieCounts = std::array<int,std::size(hoi5::aircraftTypes)>;

    int launchAirMission(int wingIndex,bool strategic,int type,SortieCounts& usedAircraft,bool& infrastructureChanged) {
        auto& wing = air.wings[wingIndex];
        const auto unavailable = [&] { return wing.cooldown > 0. || wing.abortedHours > 0.; };
        if (type < 0 || !wing.enabledMissions[strategic] || wing.missionCooldowns[strategic] > 0 || unavailable())
            return 0;
        int candidates = 0;
        int target = strategic ? selectStrategicTarget(wingIndex,&candidates) : selectCasTarget(wingIndex,&candidates);
        const int packages = std::clamp(candidates,1,5);
        int used = 0;
        for (int i = 0; i < packages && !unavailable(); ++i) {
            const int available = wing.readyForType(type)-usedAircraft[type];
            if (available <= 0) break;
            if (i > 0) target = strategic ? selectStrategicTarget(wingIndex) : selectCasTarget(wingIndex);
            const int sorties = launchAirPackage(wingIndex,strategic,type,target,available,infrastructureChanged);
            if (!sorties) break;
            usedAircraft[type] += sorties;
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
        const auto impactBuilding = [&](double scale) {
            const auto type = static_cast<hoi5::Building>(
                std::discrete_distribution<int>(weights.begin(),weights.end())(combatRandom));
            const double damage = hoi5::buildingDamage(salvo,type,scale);
            changed |= damageBuilding(salvo.target,type,damage);
            weights[type] = 0;
        };
        impactBuilding(scale);
        const bool large = weapon.type == "cruise_missile" || weapon.type == "ballistic_missile" ||
            weapon.type == "heavy_strategic_missile";
        const double spread = .20+std::min(.45,std::max(0,salvo.count-1)*.05)+
            ((large || weapon.type == "bunker_buster") ? .20 : 0.);
        const int secondary = std::min(large ? 2 : 1,int(std::ranges::count_if(weights,
            [](double value) { return value > 0; })));
        for (int i = 0; i < secondary; ++i)
            if (std::uniform_real_distribution<double>(0.,1.)(combatRandom) < spread)
                impactBuilding(scale*.42/(i+1));
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
        if (target.combat.strength <= 0) destroyDivision(target);
        if (damage > 0) {
            auto& remaining = target.airGroundSuppression[salvo.owner];
            remaining = std::max(remaining,6.);
            if (salvo.targetObject.empty()) infrastructureChanged |= resolveAirBuildingImpact(salvo,.16);
        }
        return true;
    }

    bool resolveAirImpact(const hoi5::AirSalvo& salvo,bool& infrastructureChanged) {
        if (salvo.count <= 0 || !airTargetValid(salvo.owner,salvo.target,salvo.strategic)) return false;
        const auto impact = [&] {
            addAirVisual(salvo.owner,salvo.target,salvo.target,salvo.sourceAircraft,true);
            return true;
        };
        const auto type = salvo.weapon->type;
        const bool divisionTag = type == "unguided_rocket" || type == "guided_missile" || type == "guided_bomb";
        if (salvo.targetObject.empty() && (!salvo.strategic || divisionTag) &&
            resolveAirDivisionImpact(salvo,infrastructureChanged)) return impact();
        if (salvo.strategic || !salvo.targetObject.empty()) {
            if (resolveAirBuildingImpact(salvo,1.)) {
                infrastructureChanged = true;
                return impact();
            }
        }
        return resolveAirDivisionImpact(salvo,infrastructureChanged) && impact();
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
            aircraftInterceptors.push_back({targetIndex,sorties,{fighter.owner,engaged,candidate.chance,1.},targetType,exposure});
            sorties -= engaged;
            target.defensiveHours = std::max(target.defensiveHours,2.);
        }
    }

    struct AircraftLosses { int destroyed{}, damaged{}, evaded{}; };

    AircraftLosses applyAircraftHits(hoi5::AirWing& wing,int hits,int aircraft,int exposure) {
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
        if (destroyed > 0) {
            const int tile = exposure >= 0 ? exposure : wing.base;
            addAirVisual(wing.owner,tile,tile,aircraft,true,true);
            wing.changeComposition(aircraft,-destroyed);
            news.batchNotice(diplomacy.day,wing.owner,"aircraft_losses","Потери авиации",
                "Авиакрыло потеряло "+std::to_string(destroyed)+
                " самолётов или вертолётов. Проверьте состав и условия выполнения задач.",true,destroyed);
        }
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
            const auto lost = applyAircraftHits(wing,hits,type,tile);
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

    bool updateAir(int hours,hoi5::DebugProfiler* debug = nullptr) {
        bool infrastructureChanged = false;
        {
            hoi5::DebugMeasure timing(debug,"server_air_attack_salvos");
            std::erase_if(aircraftInterceptors,[&](auto& salvo) {
                auto& target = air.wings[salvo.targetWing];
                const int type = salvo.targetAircraft < 0 ? target.type : salvo.targetAircraft;
                if (!target.readyForType(type) || !diplomacy.hostile(salvo.attack.owner,target.owner)) return true;
                salvo.attack.remaining -= hours*2.5;
                if (salvo.attack.remaining > 0) return false;
                const int engaged = std::min(salvo.attack.count,salvo.sorties);
                const double chance = emergencyEvasion(salvo.targetWing,engaged,salvo.attack.chance,type);
                const int hits = std::binomial_distribution<int>(engaged,chance)(combatRandom);
                applyAircraftHits(target,hits,type,salvo.exposure);
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
        }
        {
            hoi5::DebugMeasure timing(debug,"server_air_missions");
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
                SortieCounts usedAircraft{};
                if (reservedStrike) usedAircraft[strikeType] = reservedStrike;
                launchAirMission(wingIndex,false,casType,usedAircraft,infrastructureChanged);
                if (reservedStrike) usedAircraft[strikeType] -= reservedStrike;
                launchAirMission(wingIndex,true,strikeType,usedAircraft,infrastructureChanged);
            }
        }
        {
            hoi5::DebugMeasure timing(debug,"server_air_salvos");
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
        }
        return infrastructureChanged;
    }

    bool updateDivisions(int hours) {
        if (hours <= 0) return false;
        bool ownershipChanged = false;
        for (int index = 0; index < int(divisions.size()); ++index) {
            auto& unit = divisions[index];
            if (unit.combat.strength <= 0) continue;
            const int here = at(unit.q,unit.r).owner;
            if (unit.retreating && unit.route.empty() && here == unit.owner) {
                unit.retreating = false;
                unit.progress = unit.visualProgress = 0.;
            }
            const bool invalidRetreat = unit.retreating && (unit.route.empty() ||
                tiles[unit.route.front()].water || tiles[unit.route.front()].owner != unit.owner);
            if (invalidRetreat || (!unit.retreating && unit.battle < 0 && here >= 0 &&
                diplomacy.hostile(unit.owner,here))) {
                destroyDivision(unit);
                unit.route.clear();
                continue;
            }
            replenish(unit,hours);
            unit.lastSupplyRatio = supplyRatio(unit);
            if (unit.battle >= 0) {
                if (battles.contains(unit.battle)) continue;
                unit.battle = -1;
                unit.combat.recovering = false;
                unit.combat.widthEfficiency = 1.;
            }
            const double ratio = std::clamp(unit.organization / std::max(1., unit.maxOrganization), 0., 1.);
            if (unit.route.empty() || (!unit.retreating && unit.organization < unit.maxOrganization*.30)) {
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
            const auto& destination = tiles[unit.route.front()];
            const double terrainSpeed = hoi5::groundTerrainEffects(destination.natural,unit.combat.vehicles).speed;
            const double progress = unit.speed * terrainSpeed * (unit.retreating ? 2. : 1.) *
                std::max(.35, .35 + .65 * ratio) * unit.consumeMovementSupplies(hours)
                * hours / 24. / std::max(1.,destination.movementCost);
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
                    transferTile(next,unit.owner);
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
        return ownershipChanged;
    }

    void startBots(unsigned seed) {
        for (int owner = 0; owner < int(profiles.size()); ++owner) botLedger.sample(owner,botHours);
        if (profiles.size() > 1)
            botGeography.build(size,[&](int tile) { return airDefenseWater(tile); },
                [&](int tile,auto visit) { forFrontNeighbor(tile,visit); });
        for (int owner = 1; owner < int(profiles.size()); ++owner) {
            hoi5::PythonRandom rng(seed^(owner*1000003u));
            const double nextMicro = 6.*rng.uniform();
            supplyBots.push_back({owner,6.+18.*rng.uniform()});
            auto& bot = supplyBots.back();
            bot.nextMicro = nextMicro;
            bot.nextWeekly = 12.+60.*rng.uniform();
            bot.nextMonthly = 24.+144.*rng.uniform();
            bot.nextRecruitment = 24.+144.*rng.uniform();
            bot.nextAir = 24.+144.*rng.uniform();
            bot.nextEconomy = 12.+60.*rng.uniform();
            bot.nextExpansion = 12.+60.*rng.uniform();
            bot.nextDiplomacy = 12.+60.*rng.uniform();
            bot.aggression = rng.uniform();
            std::vector<std::pair<double,int>> candidates;
            for (int other = 0; other < int(capitals.size()); ++other) {
                if (other == owner || capitals[other] < 0) continue;
                const double score = 1./(1+hoi5::supplyHexDistance(capitals[owner],capitals[other],size));
                candidates.emplace_back(score,other);
            }
            if (const auto* target = hoi5::botChooseClose(rng,candidates,.35)) bot.expansionTarget = *target;
            bot.rng = std::move(rng);
            auto& targets = bot.defenseTargets;
            for (const auto& unit : air.defense) {
                if (unit.owner != owner) continue;
                const auto entry = std::ranges::find(targets,unit.type,&std::pair<int,int>::first);
                if (entry == targets.end()) targets.emplace_back(unit.type,1);
                else ++entry->second;
            }
        }
    }

    bool botAtWar(int owner) const {
        for (int other = 0; other < int(profiles.size()); ++other)
            if (diplomacy.hostile(owner,other)) return true;
        return false;
    }

    static hoi5::BotMilitary botMilitaryVector(const Division& unit) {
        return hoi5::botDivisionVector(unit.combat,unit.manpower,unit.design->combat.strength,
            unit.organization,unit.maxOrganization,unit.lastSupplyRatio,unit.speed);
    }

    void sampleBotMilitary(hoi5::BotSupplyState& bot,int country) const {
        hoi5::BotMilitary total{};
        int count = 0, aircraft = 0;
        double airDefense = 0.;
        for (const auto& unit : divisions) {
            if (unit.owner != country || unit.combat.strength <= 0.) continue;
            ++count;
            const auto values = botMilitaryVector(unit);
            for (std::size_t metric = 0; metric < values.size(); ++metric) total[metric] += values[metric];
        }
        for (const auto& wing : air.wings)
            if (wing.owner == country) aircraft += wing.readyCount();
        for (const auto& unit : air.defense)
            if (unit.owner == country)
                airDefense += unit.readiness()*unit.health*(1+hoi5::defenseClasses[unit.type].fireRange);
        double amplitude = 0., bias = 0.;
        if (country != bot.owner) {
            const auto [entry,inserted] = bot.militaryBias.try_emplace(country);
            if (inserted) entry->second = -1.+2.*bot.rng.uniform();
            bias = entry->second;
            amplitude = .45*(1-std::clamp(bot.intelligence,0.,.95));
        }
        const auto estimate = [&](double value) {
            const double observed = value*(1+bias*amplitude);
            return hoi5::BotEstimate{observed,observed/(1+amplitude),observed/(1-amplitude),botHours};
        };
        auto& report = bot.militaryReports[country];
        for (std::size_t metric = 0; metric < total.size(); ++metric) report.divisions[metric] = estimate(total[metric]);
        report.divisionCount = estimate(count);
        report.aircraft = estimate(aircraft);
        report.airDefense = estimate(airDefense);
    }

    hoi5::BotCourseOptions botCourseCandidates(const hoi5::BotSupplyState& bot) const {
        using Course = hoi5::BotCourse;
        const int owner = bot.owner;
        for (int other = 0; other < int(profiles.size()); ++other)
            if (diplomacy.hostile(owner,other)) return {{100.,{Course::defense,other}}};
        if (profiles[owner].budget < 0. || diplomacy.countries[owner].support < .4)
            return {{100.,{Course::recovery,-1}}};
        const auto power = [&](int country,double fallback) {
            const auto report = bot.militaryReports.find(country);
            return report == bot.militaryReports.end() ? fallback : report->second.divisions[hoi5::attack].value;
        };
        const double ownPower = power(owner,0.);
        hoi5::BotCourseOptions options{{50.,{Course::development,-1}}};
        std::set<int> neighbors;
        for (int tile = 0; tile < int(tiles.size()); ++tile) {
            if (tiles[tile].owner != owner) continue;
            for (const int neighbor : botGeography.adjacent(tile)) {
                const int other = tiles[neighbor].owner;
                if (other >= 0 && other != owner && !airDefenseWater(neighbor)) neighbors.insert(other);
            }
        }
        const auto set = [&](Course course,double score,int target,bool bestOnly = false) {
            const auto option = std::ranges::find_if(options,[&](const auto& row) { return row.second.first == course; });
            if (option == options.end()) options.emplace_back(score,hoi5::BotCourseChoice{course,target});
            else if (!bestOnly || score > option->first) *option = {score,{course,target}};
        };
        for (const int target : neighbors) {
            const auto& relation = diplomacy.relation(owner,target);
            const double enemyPower = power(target,ownPower);
            if (diplomacy.goals.contains({owner,target}) && bot.course == hoi5::BotCourseChoice{Course::warPreparation,target}
                && ownPower >= enemyPower*.75) {
                set(Course::warPreparation,75.,target);
                continue;
            }
            if (enemyPower > ownPower*1.1 || relation.crisis >= 25.)
                set(Course::deterrence,60.+relation.crisis*.2,target);
            else if (ownPower > enemyPower*(1.15-.25*bot.aggression) &&
                !relation.treaties.contains(hoi5::ForeignAction::alliance) &&
                !relation.treaties.contains(hoi5::ForeignAction::nonaggression)) {
                const double score = 48.+bot.aggression*16.+std::min(10.,(ownPower/std::max(1.,enemyPower)-1.15)*8.);
                set(Course::warPreparation,score,target,true);
            }
        }
        return options;
    }

    void selectBotCourse(hoi5::BotSupplyState& bot,hoi5::BotCourseOptions options) const {
        using Course = hoi5::BotCourse;
        auto fresh = botCourseCandidates(bot);
        if (fresh.front().second.first == Course::defense || fresh.front().second.first == Course::recovery)
            options = std::move(fresh);
        for (auto& [score,choice] : options) {
            const auto course = choice.first;
            score += bot.courseBias[std::size_t(course)];
            if (course == bot.course.first) score += 10.;
            else if (botHours-bot.courseSince < 1440 && course != Course::defense && course != Course::recovery)
                score -= 20.;
        }
        if (const auto* choice = hoi5::botChooseClose(bot.rng,options); choice && *choice != bot.course) {
            bot.course = *choice;
            bot.courseSince = botHours;
        }
    }

    void assessBotDependencies(hoi5::BotSupplyState& bot) {
        const int owner = bot.owner;
        bot.dependencies.clear();
        if (owner < 0 || owner >= int(production.size()) || owner >= int(stockpiles.size())) return;
        hoi5::Stockpile required;
        for (const auto& stage : production[owner])
            for (const auto& [key,amount] : stage.inputs) required[key] += amount;
        const auto forecast = forecastResources(owner,botMarketTick);
        for (const auto& [key,amount] : forecast.army) required[key] += amount;
        for (const auto& unit : air.defense) {
            if (unit.owner != owner) continue;
            const auto& type = hoi5::defenseClasses[unit.type];
            const auto key = type.key == "short_range_aa" ? std::string_view("light_aa_ammo") :
                std::string_view("anti_air_ammo");
            required[key] += std::max(0,std::max(unit.ammoCapacity,type.ammo)-unit.ammo)+
                std::max(unit.ammoCapacity,type.ammo);
        }
        const auto [rates,elapsed] = botLedger.rates(owner,botHours);
        for (const auto& [flow,amount] : rates) {
            const auto [kind,resource,partner] = flow;
            if (kind != hoi5::FlowKind::import || partner < 0 || amount <= 0) continue;
            const double need = hoi5::value(required,resource);
            bot.dependencies[{partner,resource}] = {amount/std::max(1.,need),
                30.*hoi5::value(stockpiles[owner],resource)/std::max(1.,amount),botHours};
        }
    }

    void updateBotReviews(hoi5::BotSupplyState& bot,hoi5::DebugProfiler* debug = nullptr) {
        const auto start = [&](bool monthly,double& next,double interval,double jitter) {
            if (botHours < next || std::ranges::any_of(bot.reviews,[&](const auto& review) {
                return review.monthly == monthly;
            })) return;
            bot.reviews.push_back({monthly,double(botHours)});
            next = botHours+interval-jitter+2*jitter*bot.rng.uniform();
        };
        start(false,bot.nextWeekly,168.,12.);
        start(true,bot.nextMonthly,720.,48.);
        for (auto& review : bot.reviews) {
            if (botHours < review.nextHour) continue;
            const bool military = review.stage == (review.monthly ? 1 : 2);
            const bool batched = military || (!review.monthly && review.stage == 1);
            if (batched) {
                const int countries = int(profiles.size());
                const int end = std::min(countries,review.countryCursor+std::max(1,(countries+3)/4));
                if (military)
                    for (int country = review.countryCursor; country < end; ++country) sampleBotMilitary(bot,country);
                review.countryCursor = end;
                if (end < countries) {
                    review.nextHour = botHours+6;
                    continue;
                }
                review.countryCursor = 0;
            }
            if (review.stage == (review.monthly ? 3 : 0)) {
                bot.regions = botGeography.profiles(tiles,bot.owner,capitals[bot.owner],
                    [&](int tile) { return airDefenseWater(tile); });
                updateBotRegionalMilitary(bot);
            } else if (review.stage == (review.monthly ? 2 : 3)) {
                hoi5::DebugMeasure dependencies(debug,"ai_dependencies");
                assessBotDependencies(bot);
            } else if (review.monthly && review.stage == 4) {
                for (const auto course : {hoi5::BotCourse::development,hoi5::BotCourse::deterrence,hoi5::BotCourse::warPreparation})
                    bot.courseBias[std::size_t(course)] = -3.+6.*bot.rng.uniform();
                review.options = botCourseCandidates(bot);
            } else if (review.monthly && review.stage == 5) selectBotCourse(bot,review.options);
            ++review.stage;
            review.nextHour = botHours+(batched ? 6. : 21.+6.*bot.rng.uniform());
        }
        std::erase_if(bot.reviews,[](const auto& review) { return review.stage >= 7; });
    }

    void updateBotRegionalMilitary(hoi5::BotSupplyState& bot) const {
        std::vector<int> regionForTile(tiles.size(),-1);
        for (int index = 0; index < int(bot.regions.size()); ++index) {
            auto& region = bot.regions[index];
            region.military = {};
            region.threat = region.desiredDefense = 0.;
            for (const int tile : region.tiles) regionForTile[tile] = index;
        }
        const bool atWar = botAtWar(bot.owner);
        std::vector<std::vector<int>> enemiesByTile(atWar ? tiles.size() : 0);
        for (int index = 0; index < int(divisions.size()); ++index) {
            const auto& unit = divisions[index];
            if (unit.combat.strength <= 0) continue;
            const int tile = unit.r*size+unit.q;
            if (unit.owner == bot.owner) {
                const int region = regionForTile[tile];
                if (region < 0) continue;
                const auto values = botMilitaryVector(unit);
                for (std::size_t metric = 0; metric < values.size(); ++metric)
                    bot.regions[region].military[metric] += values[metric];
            } else if (atWar && diplomacy.hostile(bot.owner,unit.owner)) {
                enemiesByTile[tile].push_back(index);
            }
        }
        if (!atWar) return;
        for (auto& region : bot.regions) {
            std::set<int> enemies;
            const auto collect = [&](int tile) {
                for (const int index : enemiesByTile[tile])
                    if (enemies.insert(index).second) region.threat += botMilitaryVector(divisions[index])[hoi5::attack];
            };
            for (const int border : region.borders) {
                collect(border);
                for (const int neighbor : botGeography.adjacent(border)) collect(neighbor);
            }
            if (!enemies.empty()) region.desiredDefense = std::max(12.,region.threat*1.15);
        }
    }

    int botPreparationTarget(int owner) const {
        if (botAtWar(owner)) return -1;
        const auto goal = diplomacy.goals.lower_bound({owner,0});
        const auto bot = std::ranges::find(supplyBots,owner,&hoi5::BotSupplyState::owner);
        const int preferred = bot == supplyBots.end() ? -1 : bot->course.second;
        int target = -1;
        if (diplomacy.goals.contains({owner,preferred})) target = preferred;
        else if (goal != diplomacy.goals.end() && goal->first.first == owner) target = goal->first.second;
        else if (bot != supplyBots.end() && bot->course.first == hoi5::BotCourse::warPreparation) target = preferred;
        if (target < 0) return -1;
        return std::ranges::any_of(tiles,[&](const auto& tile) { return tile.owner == target; }) ? target : -1;
    }

    std::map<int,int> botForwardDefenseSites(int owner) const {
        const int target = botPreparationTarget(owner);
        if (target < 0 || !std::ranges::any_of(supplyBots,[&](const auto& bot) { return bot.owner == owner; })) return {};
        std::set<int> front;
        for (int index = 0; index < int(tiles.size()); ++index) {
            if (tiles[index].owner != owner || airDefenseWater(index)) continue;
            if (std::ranges::any_of(botGeography.adjacent(index),[&](int neighbor) {
                return tiles[neighbor].owner == target && !airDefenseWater(neighbor);
            })) front.insert(index);
        }
        std::map<int,int> rear;
        for (const int tile : front) for (const int neighbor : botGeography.adjacent(tile)) {
            if (tiles[neighbor].owner == owner && !front.contains(neighbor))
                rear.emplace(neighbor,-hoi5::supplyHexDistance(neighbor,capitals[target],size));
        }
        return rear;
    }

    std::optional<hoi5::BotSupplyChoice> planBotSupply(const hoi5::BotSupplyState& bot,int spec) const {
        std::vector<int> occupied(tiles.size());
        for (const auto& unit : divisions) {
            if (unit.owner != bot.owner || unit.combat.strength <= 0) continue;
            const int index = unit.r*size+unit.q;
            if (tiles[index].owner != bot.owner) continue;
            ++occupied[index];
        }
        for (const auto& [unit,tile] : bot.hexAssignments) ++occupied[tile];
        for (const auto& unit : divisions) {
            if (unit.owner != bot.owner || unit.combat.strength <= 0 || !unit.route.empty()) continue;
            const int tile = unit.r*size+unit.q;
            if (unit.organization < unit.maxOrganization*.35 && tiles[tile].supply < .3)
                occupied[tile] += 6;
        }
        std::set<int> queued;
        for (const auto& project : construction.queues[bot.owner]) {
            if (project.spec != spec) continue;
            queued.insert(project.tile);
        }
        std::vector<hoi5::BotSupplyPoint> points;
        std::vector<hoi5::BotSupplyCandidate> candidates;
        const int preparationTarget = botPreparationTarget(bot.owner);
        for (int index = 0; index < int(tiles.size()); ++index) {
            const auto& tile = tiles[index];
            if (tile.owner != bot.owner || airDefenseWater(index)) continue;
            bool border = false, hostileBorder = false, mobilizationFront = false;
            for (const int neighbor : botGeography.adjacent(index)) {
                const auto& other = tiles[neighbor];
                if (other.owner < 0 || other.owner == bot.owner) continue;
                border = true;
                hostileBorder |= !airDefenseWater(neighbor) && diplomacy.hostile(bot.owner,other.owner);
                mobilizationFront |= other.owner == preparationTarget;
            }
            const int weight = occupied[index]+(border ? 3 : 0)+(mobilizationFront ? 6 : 0);
            if (weight && tile.supply < .55)
                points.push_back({index,double(weight),1./std::max(1.,tile.movementCost),tile.supply});
            const double coverage = tile.buildings[hoi5::supplyDepot].area;
            if (coverage >= .7 || queued.contains(index)) continue;
            double strength = capitals[bot.owner] == index ? .85 : 0.;
            for (int b = 0; b < hoi5::buildingCount; ++b)
                strength += tile.buildings[b].area*tile.buildings[b].health*hoi5::supplySourceWeights[b];
            strength = std::min(1.,strength+hoi5::supplySourceWeights[hoi5::supplyDepot]*(.7-coverage));
            double multiplier = hostileBorder ? .85 : 1.;
            if (battles.contains(index)) multiplier *= .8;
            if (index == bot.target) multiplier *= 1.2;
            candidates.push_back({index,strength,multiplier});
        }
        return hoi5::bestBotSupplySite(size,points,candidates);
    }

    bool addBotTask(hoi5::BotSupplyState& bot,hoi5::BotTask task) {
        const auto duplicate = [&](const hoi5::BotTask& existing) {
            return existing.active() && existing.kind == task.kind && existing.tile == task.tile &&
                existing.resource == task.resource && existing.amount == task.amount &&
                existing.defenseType == task.defenseType && existing.trainingType == task.trainingType &&
                existing.buildingSpec == task.buildingSpec && existing.sector == task.sector &&
                existing.targetCountry == task.targetCountry && existing.politicalAction == task.politicalAction;
        };
        if (std::ranges::count_if(bot.tasks,&hoi5::BotTask::active) >= 12 ||
            std::ranges::any_of(bot.tasks,duplicate)) return false;
        bot.tasks.push_back(task);
        for (auto it = bot.tasks.begin(); bot.tasks.size() > 60 && it != bot.tasks.end();) {
            if (it->active()) ++it;
            else it = bot.tasks.erase(it);
        }
        return true;
    }

    static constexpr std::array<std::string_view,4> botDepotResources{
        "construction_goods","steel","machinery","refined_fuel"
    };

    void scheduleBotSupply(hoi5::BotSupplyState& bot,int spec) {
        using Task = hoi5::BotTask;
        std::set<int> sites;
        std::vector<int> critical;
        for (const auto& unit : divisions) {
            if (unit.owner != bot.owner || unit.combat.strength <= 0) continue;
            const int index = unit.r*size+unit.q;
            if (tiles[index].owner == bot.owner && tiles[index].supply < .3)
                critical.push_back(index);
        }
        bool protectedProject = false;
        for (const auto& project : construction.queues[bot.owner]) {
            if (project.spec != spec) continue;
            for (const auto key : botDepotResources) {
                const double missing = hoi5::value(project.resources,key)-hoi5::value(project.resourcesSpent,key)-
                    hoi5::value(stockpiles[bot.owner],key);
                if (missing > 0 && !std::ranges::any_of(bot.tasks,[&](const Task& task) {
                    return task.kind == Task::Kind::buy && task.resource == key &&
                        (task.pending() || task.status == hoi5::BotTaskStatus::waitingMarket);
                })) addBotTask(bot,{Task::Kind::buy,botHours,-1,key,missing});
            }
            if (project.repair) continue;
            sites.insert(project.tile);
            protectedProject |= !project.paused && std::ranges::any_of(critical,[&](int tile) {
                return hoi5::supplyHexDistance(project.tile,tile,size) <= 3;
            });
        }
        if (sites.size() >= 2 || protectedProject || (!sites.empty() && critical.empty())) return;
        const auto choice = planBotSupply(bot,spec);
        bot.target = choice ? choice->tile : -1;
        if (!choice || std::ranges::any_of(bot.tasks,[](const Task& task) {
            return task.kind == Task::Kind::supply && task.pending();
        })) return;
        if (std::ranges::count_if(bot.tasks,&Task::active) >= 12) {
            const auto replace = std::ranges::find_if(bot.tasks,[](const Task& task) {
                return task.pending() && task.kind != Task::Kind::supply;
            });
            if (replace != bot.tasks.end()) replace->status = hoi5::BotTaskStatus::cancelled;
        }
        if (addBotTask(bot,{Task::Kind::supply,botHours,choice->tile}))
            bot.tasks.splice(bot.tasks.begin(),bot.tasks,std::prev(bot.tasks.end()));
    }

    bool applyBotSupply(hoi5::BotSupplyState& bot,hoi5::BotTask& task,int spec) {
        auto& queue = construction.queues[bot.owner];
        if (tiles[task.tile].owner != bot.owner || std::ranges::any_of(queue,[&](const auto& project) {
            return project.tile == task.tile && project.spec == spec;
        })) return false;
        if (!construction.enqueue(tiles,size,bot.owner,task.tile,spec,profiles[bot.owner].buildEfficiency).empty())
            return false;
        const auto& project = queue.back();
        if (project.money > std::max(0.,profiles[bot.owner].budget-5000000.)) {
            queue.pop_back();
            return false;
        }
        task.targetCoverage = project.repair ? tiles[task.tile].buildings[hoi5::supplyDepot].area : project.target;
        for (const auto key : botDepotResources) {
            const double missing = hoi5::value(project.resources,key)-hoi5::value(stockpiles[bot.owner],key);
            if (missing > 0) addBotTask(bot,{hoi5::BotTask::Kind::buy,botHours,-1,key,missing});
        }
        std::rotate(queue.begin(),std::prev(queue.end()),queue.end());
        return true;
    }

    double botAvailableMoney(const hoi5::BotSupplyState& bot) const {
        const int owner = bot.owner;
        const double balance = taxedTreasury(owner).balance()+bot.tradeBalance;
        double money = std::max(0.,profiles[owner].budget-std::max(5000000.,std::abs(balance)));
        for (const auto& project : construction.queues[owner])
            if (!project.paid) money -= project.money;
        return std::max(0.,money);
    }

    hoi5::Stockpile botAvailableResources(int owner) const {
        auto resources = stockpiles[owner];
        for (const auto& project : construction.queues[owner])
            for (const auto& [key,amount] : project.resources)
                resources[key] -= std::max(0.,amount-hoi5::value(project.resourcesSpent,key));
        return resources;
    }

    hoi5::Stockpile botMilitaryReserve(int owner,bool preparing,int extraType = -1) const {
        hoi5::Stockpile reserve;
        const auto add = [&](const hoi5::DivisionTemplate& design) {
            for (const auto& [key,amount] : design.capacity)
                reserve[key] += amount*(preparing ? .5 : .15);
            for (const auto& [key,amount] : design.use)
                reserve[key] += amount*(preparing ? 48. : 12.);
        };
        for (const auto& unit : divisions)
            if (unit.owner == owner && unit.combat.strength > 0 && unit.design) add(*unit.design);
        for (const auto& project : training)
            if (project.country == owner) add(trainingDesign(project.type));
        if (extraType >= 0) add(trainingDesign(extraType));
        if (preparing) for (const auto& unit : air.defense) {
            if (unit.owner != owner) continue;
            const auto& type = hoi5::defenseClasses[unit.type];
            const auto key = type.key == "short_range_aa" ? std::string_view("light_aa_ammo") :
                std::string_view("anti_air_ammo");
            reserve[key] += std::max(0,unit.ammoCapacity*2-unit.ammo);
        }
        return reserve;
    }

    void scheduleBotMobilizationStock(hoi5::BotSupplyState& bot) {
        using Task = hoi5::BotTask;
        const int owner = bot.owner;
        const auto reserve = botMilitaryReserve(owner,true);
        const auto contracts = market.contracts;
        const double limit = hoi5::Market::monthlyCapacity(tiles,profiles)[owner];
        for (const auto& order : contracts) {
            if (order.country == owner && !order.buy && hoi5::value(reserve,order.resource) > 0 &&
                market.changeContract(owner,order.resource,false,-order.amount,limit))
                botBalanceRefresh.insert(owner);
        }
        const auto free = botAvailableResources(owner);
        std::vector<std::tuple<double,std::string_view,double>> shortages;
        for (const auto& [key,amount] : reserve) {
            const double available = hoi5::value(free,key);
            if (amount > std::max(0.,available))
                shortages.emplace_back((amount-available)/amount,key,amount-available);
        }
        std::ranges::sort(shortages,std::greater{});
        for (std::size_t i = 0; i < std::min<std::size_t>(4,shortages.size()); ++i) {
            const auto& [priority,key,missing] = shortages[i];
            if (std::ranges::any_of(bot.tasks,[&](const Task& task) {
                return task.kind == Task::Kind::buy && task.resource == key && task.active();
            })) continue;
            addBotTask(bot,{Task::Kind::buy,botHours,-1,key,missing});
        }
    }

    int botTrainingSite(int owner) const {
        int best = -1;
        for (int tile = 0; tile < int(tiles.size()); ++tile)
            if (safeTrainingSite(owner,tile) && (best < 0 || tiles[tile].supply > tiles[best].supply)) best = tile;
        return best;
    }

    void scheduleBotRecruitment(hoi5::BotSupplyState& bot,bool mobilizing = false) {
        if (!mobilizing) {
            if (botHours < bot.nextRecruitment) return;
            bot.nextRecruitment = botHours+168;
        }
        const int owner = bot.owner, site = botTrainingSite(owner);
        if (site < 0 || owner >= int(manpowerReserve.size()) || std::ranges::any_of(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::recruit && task.active();
        })) return;
        const double money = botAvailableMoney(bot);
        const auto free = botAvailableResources(owner);
        std::vector<std::pair<double,int>> options;
        for (int type = 0; type < baseDivisionTypes; ++type) {
            const auto& design = trainingDesign(type);
            if (trainingCost(design) > money || design.manpower > manpowerReserve[owner]) continue;
            const auto reserve = botMilitaryReserve(owner,false,type);
            double coverage = std::numeric_limits<double>::infinity();
            std::set<std::string_view> keys;
            for (const auto& [key,amount] : reserve) keys.insert(key);
            for (const auto& [key,amount] : design.capacity) keys.insert(key);
            for (auto key : keys)
                coverage = std::min(coverage,hoi5::value(free,key)/
                    std::max(1.,hoi5::value(reserve,key)+hoi5::value(design.capacity,key)));
            options.emplace_back(std::isfinite(coverage) ? coverage : 0.,type);
        }
        if (options.empty()) return;
        std::vector<std::pair<double,int>> covered;
        for (const auto& option : options) if (option.first >= 1.) covered.push_back(option);
        const auto* type = hoi5::botChooseClose(bot.rng,covered.empty() ? options : covered);
        if (!type) return;
        const auto reserve = botMilitaryReserve(owner,false,*type);
        std::vector<std::pair<double,std::string_view>> shortages;
        for (const auto& [key,amount] : reserve) {
            const double missing = amount+hoi5::value(trainingDesign(*type).capacity,key)-
                hoi5::value(free,key);
            if (missing > 0) shortages.emplace_back(missing,key);
        }
        std::ranges::sort(shortages,std::greater{});
        for (std::size_t i = 0; i < std::min<std::size_t>(4,shortages.size()); ++i)
            addBotTask(bot,{hoi5::BotTask::Kind::buy,botHours,-1,shortages[i].second,shortages[i].first});
        if (!shortages.empty()) return;
        hoi5::BotTask task{hoi5::BotTask::Kind::recruit,botHours};
        task.tile = site;
        task.trainingType = *type;
        addBotTask(bot,task);
    }

    bool applyBotRecruitment(const hoi5::BotSupplyState& bot,const hoi5::BotTask& task) {
        const int owner = bot.owner, type = task.trainingType;
        if (type < 0 || type >= baseDivisionTypes || !safeTrainingSite(owner,task.tile)) return false;
        const auto& design = trainingDesign(type);
        const auto existing = botMilitaryReserve(owner,false);
        const auto reserve = botMilitaryReserve(owner,false,type);
        const auto free = botAvailableResources(owner);
        int count = std::min(int(botAvailableMoney(bot)/std::max(1.,trainingCost(design))),
            int(manpowerReserve[owner]/std::max(1,design.manpower)));
        std::set<std::string_view> keys;
        for (const auto& [key,amount] : reserve) keys.insert(key);
        for (const auto& [key,amount] : design.capacity) keys.insert(key);
        for (auto key : keys) {
            const double current = hoi5::value(existing,key);
            const double perDivision = hoi5::value(reserve,key)-current+hoi5::value(design.capacity,key);
            const double available = hoi5::value(free,key)-current;
            if (available < 0) count = 0;
            else if (perDivision > 0) count = std::min(count,int((available+1e-8)/perDivision));
        }
        int started = 0;
        while (started < count && train(owner,task.tile,type) == "Подготовка начата") ++started;
        return started > 0;
    }

    bool botAirReach(int base,int tile,int type) const {
        return type >= 0 && type < int(std::size(hoi5::aircraftTypes)) &&
            hoi5::supplyHexDistance(base,tile,size) <= hoi5::aircraftTypes[type].range;
    }

    bool botRearAirbase(int owner,int tile) const {
        if (tiles[tile].owner != owner) return false;
        for (const int near : botGeography.adjacent(tile)) {
            if (tiles[near].owner >= 0 && diplomacy.hostile(owner,tiles[near].owner)) return false;
            for (const int next : botGeography.adjacent(near))
                if (tiles[next].owner >= 0 && diplomacy.hostile(owner,tiles[next].owner)) return false;
        }
        return true;
    }

    void scheduleBotAir(hoi5::BotSupplyState& bot) {
        if (botHours < bot.nextAir || bot.regions.empty()) return;
        bot.nextAir = botHours+168;
        if (std::ranges::any_of(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::air && task.active();
        })) return;
        const auto hostile = [&](const hoi5::BotRegion& region) {
            return std::ranges::any_of(region.borders,[&](int tile) {
                return std::ranges::any_of(botGeography.adjacent(tile),[&](int next) {
                    return tiles[next].owner >= 0 && diplomacy.hostile(bot.owner,tiles[next].owner);
                });
            });
        };
        const auto front = std::ranges::max_element(bot.regions,[&](const auto& a,const auto& b) {
            return std::pair{hostile(a),a.importance} < std::pair{hostile(b),b.importance};
        });
        if (front == bot.regions.end()) return;
        addBotTask(bot,{hoi5::BotTask::Kind::air,botHours,front->anchor});
    }

    bool applyBotAir(hoi5::BotSupplyState& bot,const hoi5::BotTask& task) {
        const int owner = bot.owner;
        if (task.tile < 0 || task.tile >= int(tiles.size()) || tiles[task.tile].owner != owner) return false;
        std::vector<int> rearBases;
        for (const auto& base : air.bases)
            if (base.owner == owner && botRearAirbase(owner,base.tile)) rearBases.push_back(base.tile);
        if (rearBases.empty()) for (const auto& base : air.bases)
            if (base.owner == owner) rearBases.push_back(base.tile);
        if (rearBases.empty()) return false;

        const auto reserve = botMilitaryReserve(owner,botPreparationTarget(owner) >= 0);
        const int fuelSlots = std::max(0,int((hoi5::value(stockpiles[owner],"refined_fuel")-
            hoi5::value(reserve,"refined_fuel"))/100.));
        int based = 0;
        for (const auto& wing : air.wings) if (wing.owner == owner) based += wing.count;
        int slots = std::max(0,fuelSlots-based);
        constexpr std::array order{0,1,3,2,4,5};
        for (const int type : order) {
            int count = air.reserves[owner][type];
            while (count > 0 && slots > 0) {
                int base = -1, load = std::numeric_limits<int>::max();
                for (const int candidate : rearBases) {
                    if (air.freeCapacity(tiles,owner,candidate,type) <= 0) continue;
                    int current = 0;
                    for (const auto& wing : air.wings)
                        if (wing.owner == owner && wing.base == candidate &&
                            hoi5::aircraftTypes[wing.type].helicopter == hoi5::aircraftTypes[type].helicopter)
                            current += wing.count;
                    if (current < load) { load = current; base = candidate; }
                }
                if (base < 0) break;
                const int wing = air.createWing(tiles,owner,type,std::min({8,count,slots}),{},base);
                if (wing < 0) break;
                count -= air.wings[wing].count;
                slots -= air.wings[wing].count;
            }
        }

        std::vector<const hoi5::BotRegion*> fronts;
        for (const auto& region : bot.regions) if (std::ranges::any_of(region.borders,[&](int tile) {
            return std::ranges::any_of(botGeography.adjacent(tile),[&](int next) {
                return tiles[next].owner >= 0 && diplomacy.hostile(owner,tiles[next].owner);
            });
        })) fronts.push_back(&region);
        std::map<int,int> assignments;
        const bool combat = botAtWar(owner);
        for (int wingIndex = 0; wingIndex < int(air.wings.size()); ++wingIndex) {
            auto& wing = air.wings[wingIndex];
            if (wing.owner != owner || wing.count <= 0) continue;
            const hoi5::BotRegion* assigned = nullptr;
            auto rank = std::tuple{std::numeric_limits<int>::max(),0.,0};
            for (const auto* region : fronts) {
                bool reachable = false;
                for (const int tile : region->tiles) for (int type = 0; type < int(std::size(hoi5::aircraftTypes)); ++type)
                    reachable |= wing.typeCount(type) > 0 && botAirReach(wing.base,tile,type);
                if (!reachable) continue;
                const auto candidate = std::tuple{assignments[region->base],-region->importance,region->base};
                if (!assigned || candidate < rank) { assigned = region; rank = candidate; }
            }
            if (!assigned) {
                const auto fallback = std::ranges::find_if(bot.regions,[&](const auto& region) {
                    return std::ranges::find(region.tiles,task.tile) != region.tiles.end();
                });
                if (fallback != bot.regions.end()) assigned = &*fallback;
            }
            if (!assigned) continue;
            ++assignments[assigned->base];
            int center = assigned->tiles[assigned->tiles.size()/2];
            int bestBase = wing.base;
            for (const int base : rearBases)
                if (air.freeCapacity(tiles,owner,base,wing.type,wingIndex) >= wing.count &&
                    hoi5::supplyHexDistance(base,center,size) < hoi5::supplyHexDistance(bestBase,center,size)) bestBase = base;
            if (hoi5::supplyHexDistance(bestBase,center,size)+2 < hoi5::supplyHexDistance(wing.base,center,size))
                air.rebaseWing(tiles,wingIndex,bestBase);

            wing.airSuperiority = wing.missionType(2) >= 0;
            wing.intercept = wing.missionType(2) >= 0;
            wing.patrol = wing.missionType(2) >= 0;
            wing.enabledMissions[0] = combat && wing.missionAllowed(false);
            wing.enabledMissions[1] = combat && wing.missionAllowed(true);
            wing.sortieIntensity = .65+bot.aggression*.25;
            wing.risk = hoi5::AirRisk::normal;
            wing.targetPriorities = {"depot","factory","airbase","infrastructure"};
            std::set<int> area(assigned->tiles.begin(),assigned->tiles.end());
            for (const int tile : assigned->borders) for (const int next : botGeography.adjacent(tile))
                if (tiles[next].owner >= 0 && diplomacy.hostile(owner,tiles[next].owner)) area.insert(next);
            const int casType = wing.missionType(0);
            const auto addSupport = [&](int tile) {
                if (hoi5::supplyHexDistance(center,tile,size) <= 6 && botAirReach(wing.base,tile,casType))
                    area.insert(tile);
            };
            for (const auto& [tile,battle] : battles)
                if (battle.attacker == owner || battle.defender == owner) addSupport(tile);
            for (const auto& unit : divisions)
                if (unit.owner == owner && unit.attackRoute && !unit.route.empty()) addSupport(unit.route.back());
            std::vector<std::pair<double,int>> strategic;
            for (int tile = 0; tile < int(tiles.size()); ++tile) {
                if (tiles[tile].owner < 0 || !diplomacy.hostile(owner,tiles[tile].owner)) continue;
                const auto& b = tiles[tile].buildings;
                const double value = 9*b[hoi5::supplyDepot].area+7*b[hoi5::warehouse].area+
                    7*b[hoi5::fuelStorage].area+7*b[hoi5::refinery].area+6*b[hoi5::industry].area+
                    6*b[hoi5::airbase].area+5*b[hoi5::port].area+4*b[hoi5::oilGasRig].area+3*b[hoi5::mine].area;
                if (value > 0 && botAirReach(wing.base,tile,wing.missionType(1)))
                    strategic.emplace_back(value/(1.+hoi5::supplyHexDistance(center,tile,size)/6.),tile);
            }
            std::ranges::sort(strategic,std::greater{});
            for (std::size_t i = 0; i < std::min<std::size_t>(8,strategic.size()); ++i) area.insert(strategic[i].second);
            wing.operationArea.assign(area.begin(),area.end());
            wing.target = wing.operationArea.empty() ? -1 : wing.operationArea.back();
        }
        return true;
    }

    void scheduleBotEconomy(hoi5::BotSupplyState& bot) {
        if (botHours < bot.nextEconomy) return;
        bot.nextEconomy = botHours+168+int(bot.rng.uniform()*24)-12;
        const int owner = bot.owner;
        if (owner < 0 || owner >= int(production.size()) || owner >= int(stockpiles.size()) ||
            owner >= int(capacities.size()) || owner >= int(construction.queues.size()) ||
            owner >= int(profiles.size())) return;
        hoi5::Stockpile capacity,required;
        for (const auto& stage : production[owner]) {
            for (const auto& [key,amount] : stage.outputs) capacity[key] += amount;
            for (const auto& [key,amount] : stage.inputs) required[key] += amount;
        }
        const auto forecast = forecastResources(owner,botMarketTick);
        for (const auto& [key,amount] : forecast.army) required[key] += amount;
        for (const auto& unit : air.defense) {
            if (unit.owner != owner) continue;
            const auto& type = hoi5::defenseClasses[unit.type];
            const auto key = type.key == "short_range_aa" ? std::string_view("light_aa_ammo") :
                std::string_view("anti_air_ammo");
            required[key] += std::max(0,std::max(unit.ammoCapacity,type.ammo)-unit.ammo)+
                std::max(unit.ammoCapacity,type.ammo);
        }
        std::set<std::string_view> keys;
        for (const auto& [key,amount] : stockpiles[owner]) keys.insert(key);
        for (const auto& [key,amount] : capacity) keys.insert(key);
        for (const auto& [key,amount] : required) keys.insert(key);
        struct TradeChoice { double score; std::string_view key; bool buy; double amount; };
        std::vector<TradeChoice> trades;
        std::vector<std::pair<double,std::string_view>> shortages;
        const bool preparing = botPreparationTarget(owner) >= 0;
        for (const auto key : keys) {
            const double need = hoi5::value(required,key), output = hoi5::value(capacity,key);
            const double stock = hoi5::value(stockpiles[owner],key);
            const double deficit = std::max(0.,need-output);
            if (need > 0 && stock < need*.5) {
                double score = (need*.5-stock)/std::max(1.,need);
                if (key == "food" || key == "refined_fuel" || key == "consumer_goods") score *= 2;
                shortages.emplace_back(score,key);
                trades.push_back({score,key,true,std::max(deficit,need*.5-stock)});
            } else if (stock > std::max(1000.,need*3) && output > need && !preparing) {
                trades.push_back({.1,key,false,std::min((stock-need*3)*.15,output-need)});
            }
        }
        std::ranges::sort(trades,[](const auto& a,const auto& b) { return a.score > b.score; });
        for (std::size_t i = 0; i < std::min<std::size_t>(6,trades.size()); ++i)
            addBotTask(bot,{trades[i].buy ? hoi5::BotTask::Kind::buy : hoi5::BotTask::Kind::sell,
                botHours,-1,trades[i].key,trades[i].amount});
        if (construction.queues[owner].size() >= 4 || botAvailableMoney(bot) <= 0 || bot.regions.empty()) return;

        const auto* shortage = hoi5::botChooseClose(bot.rng,shortages);
        hoi5::Building building = hoi5::industry;
        std::string_view sector;
        if (shortage) {
            if (*shortage == "food") building = hoi5::farms;
            else if (*shortage == "oil" || *shortage == "natural_gas") building = hoi5::oilGasRig;
            else if (*shortage == "refined_fuel") building = hoi5::refinery;
            else for (const auto& recipe : hoi5::recipes) {
                if (hoi5::value(recipe.outputs,*shortage) <= 0) continue;
                building = recipe.building;
                sector = recipe.sector;
                break;
            }
        }
        const int spec = int(std::ranges::find(hoi5::constructionSpecs,building,
            &hoi5::ConstructionSpec::building)-std::begin(hoi5::constructionSpecs));
        if (spec < 0 || spec >= int(std::size(hoi5::constructionSpecs))) return;
        std::vector<std::pair<double,int>> regionChoices;
        for (const auto& region : bot.regions) {
            double score = region.importance+(region.supply < .4 ? 10. : 0.);
            if (botAtWar(owner) && std::ranges::any_of(region.borders,[&](int tile) {
                return std::ranges::any_of(botGeography.adjacent(tile),[&](int next) {
                    return tiles[next].owner >= 0 && diplomacy.hostile(owner,tiles[next].owner);
                });
            })) score += 20.;
            regionChoices.emplace_back(score,region.anchor);
        }
        const auto* region = hoi5::botChooseClose(bot.rng,regionChoices);
        if (!region) return;
        hoi5::BotTask build{hoi5::BotTask::Kind::build,botHours,*region};
        build.buildingSpec = spec;
        build.sector = sector;
        addBotTask(bot,build);
        if (!sector.empty()) {
            hoi5::BotTask specialize{hoi5::BotTask::Kind::specialize,botHours,*region};
            specialize.sector = sector;
            addBotTask(bot,specialize);
        }
    }

    void scheduleBotExpansion(hoi5::BotSupplyState& bot) {
        if (botHours < bot.nextExpansion) return;
        bot.nextExpansion = botHours+168+int(bot.rng.uniform()*24)-12;
        const int owner = bot.owner;
        if (bot.course.first != hoi5::BotCourse::development || owner < 0 ||
            owner >= int(production.size()) || owner >= int(stockpiles.size())) return;
        if (std::ranges::any_of(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::claim && task.active();
        })) return;

        hoi5::Stockpile required;
        for (const auto& stage : production[owner])
            for (const auto& [key,amount] : stage.inputs) required[key] += amount;
        const auto forecast = forecastResources(owner,botMarketTick);
        for (const auto& [key,amount] : forecast.army) required[key] += amount;
        std::map<std::string_view,double> needs;
        for (const auto& [key,amount] : required) {
            const double half = amount*.5;
            needs[key] = std::max(0.,half-hoi5::value(stockpiles[owner],key))/std::max(1.,half);
        }

        std::map<int,double> expansion;
        for (int tile = 0; tile < int(tiles.size()); ++tile) {
            if (tiles[tile].owner != owner) continue;
            for (const int next : botGeography.adjacent(tile)) {
                const auto& candidate = tiles[next];
                if (candidate.owner >= 0 || candidate.water) continue;
                double score = .5+1./std::max(1.,candidate.movementCost)+
                    hoi5::agricultureScore(candidate.natural)*.3;
                for (const auto& deposit : candidate.deposits) {
                    const auto need = needs.find(deposit.resource);
                    if (need == needs.end()) continue;
                    score += std::min(1.,std::log1p(std::max(0.,deposit.mass))/std::log(1000001.))*need->second*4.;
                }
                if (bot.expansionTarget >= 0 && bot.expansionTarget < int(capitals.size()) &&
                    capitals[bot.expansionTarget] >= 0)
                    score += 8./(1+hoi5::supplyHexDistance(next,capitals[bot.expansionTarget],size));
                expansion[next] = score;
            }
        }
        std::vector<std::pair<double,int>> choices;
        for (const auto& [tile,score] : expansion) choices.emplace_back(score,tile);
        const auto* target = hoi5::botChooseClose(bot.rng,choices);
        if (target) addBotTask(bot,{hoi5::BotTask::Kind::claim,botHours,*target});
    }

    bool applyBotClaim(hoi5::BotSupplyState& bot,const hoi5::BotTask& task) {
        if (task.tile < 0 || task.tile >= int(tiles.size()) || tiles[task.tile].owner >= 0 || tiles[task.tile].water)
            return false;
        std::vector<std::pair<int,int>> choices;
        for (int i = 0; i < int(divisions.size()); ++i) {
            const auto& unit = divisions[i];
            if (unit.owner != bot.owner || bot.resting.contains(i) || unit.battle >= 0 || unit.retreating ||
                !unit.route.empty() || unit.organization < unit.maxOrganization*.5 || unit.combat.strength <= 0) continue;
            choices.emplace_back(hoi5::supplyHexDistance(unit.r*size+unit.q,task.tile,size),i);
        }
        std::ranges::sort(choices);
        for (const auto& [distance,index] : choices)
            if (orderMove(divisions[index],task.tile)) return true;
        return false;
    }

    bool applyBotConstruction(hoi5::BotSupplyState& bot,hoi5::BotTask& task) {
        const int owner = bot.owner, anchor = task.tile, spec = task.buildingSpec;
        if (spec < 0 || spec >= int(std::size(hoi5::constructionSpecs))) return false;
        const auto region = std::ranges::find_if(bot.regions,[&](const auto& item) {
            return std::ranges::find(item.tiles,anchor) != item.tiles.end();
        });
        if (region == bot.regions.end()) return false;
        std::vector<std::pair<double,int>> choices;
        for (const int tile : region->tiles) {
            if (!hoi5::Construction::placementBlock(tiles,size,owner,tile,spec,
                tiles[tile].buildings[hoi5::constructionSpecs[spec].building].area).empty()) continue;
            if (std::ranges::any_of(construction.queues[owner],[&](const auto& project) {
                return project.tile == tile && project.spec == spec;
            })) continue;
            double score = tiles[tile].supply+.3/std::max(1.,tiles[tile].movementCost);
            if (hoi5::constructionSpecs[spec].building == hoi5::farms)
                score += hoi5::agricultureScore(tiles[tile].natural);
            choices.emplace_back(score,tile);
        }
        const auto* site = hoi5::botChooseClose(bot.rng,choices);
        if (!site) return false;
        auto& queue = construction.queues[owner];
        if (!construction.enqueue(tiles,size,owner,*site,spec,profiles[owner].buildEfficiency).empty()) return false;
        const auto& project = queue.back();
        const auto resources = botAvailableResources(owner);
        const double availableMoney = botAvailableMoney(bot);
        const auto missing = std::ranges::find_if(project.resources,[&](const auto& item) {
            return hoi5::value(resources,item.first) < item.second;
        });
        if (project.money > availableMoney || missing != project.resources.end()) {
            queue.pop_back();
            return false;
        }
        task.tile = *site;
        task.targetCoverage = project.target;
        return true;
    }

    bool applyBotSpecialization(const hoi5::BotSupplyState& bot,const hoi5::BotTask& task) {
        const auto region = std::ranges::find_if(bot.regions,[&](const auto& item) {
            return std::ranges::find(item.tiles,task.tile) != item.tiles.end();
        });
        if (region == bot.regions.end() || task.sector.empty()) return false;
        for (const int tile : region->tiles) {
            if (tiles[tile].buildings[hoi5::industry].area <= 0) continue;
            tiles[tile].industries = task.sector == "consumer_goods" ? std::vector<std::string_view>{task.sector} :
                std::vector<std::string_view>{task.sector,"consumer_goods"};
            production[bot.owner] = hoi5::buildProduction(tiles,bot.owner,profiles[bot.owner].population,{});
            return true;
        }
        return false;
    }

    bool botWarPreparationReady(const hoi5::BotSupplyState& bot,int target) const {
        const int owner = bot.owner;
        std::vector<int> front;
        for (int tile = 0; tile < int(tiles.size()); ++tile) {
            if (tiles[tile].owner != owner || airDefenseWater(tile)) continue;
            if (std::ranges::any_of(botGeography.adjacent(tile),[&](int next) {
                return tiles[next].owner == target && !airDefenseWater(next);
            })) front.push_back(tile);
        }
        if (front.empty()) return false;
        const auto goal = diplomacy.goals.find({owner,target});
        if (goal != diplomacy.goals.end() && diplomacy.day < goal->second+14 &&
            std::ranges::any_of(training,[&](const auto& project) {
                if (project.country != owner) return false;
                const int remaining = trainingHours(trainingDesign(project.type))-project.hours;
                return remaining > 0 && remaining <= 14*24;
            })) return false;
        std::set<int> near(front.begin(),front.end());
        for (const int tile : front)
            near.insert(botGeography.adjacent(tile).begin(),botGeography.adjacent(tile).end());
        int total = 0;
        std::vector<int> ready;
        for (int index = 0; index < int(divisions.size()); ++index) {
            const auto& unit = divisions[index];
            if (unit.owner != owner || unit.combat.strength <= 0) continue;
            ++total;
            const int tile = unit.r*size+unit.q;
            if (near.contains(tile) && unit.route.empty() && unit.battle < 0 &&
                unit.organization >= unit.maxOrganization*.65 && supplyRatio(unit) >= .25) ready.push_back(tile);
        }
        if (int(ready.size()) < std::max(1,(total+2)/3)) return false;
        const bool covered = std::ranges::any_of(air.defense,[&](const auto& unit) {
            if (unit.owner != owner || unit.ammo <= 0 || !unit.operational()) return false;
            const int range = hoi5::defenseClasses[unit.type].fireRange;
            return range > 0 && std::ranges::any_of(ready,[&](int tile) {
                return hoi5::supplyHexDistance(unit.tile,tile,size) <= range;
            });
        });
        if (!covered) return false;
        const auto reserve = botMilitaryReserve(owner,false);
        return std::ranges::all_of(reserve,[&](const auto& item) {
            return hoi5::value(stockpiles[owner],item.first) >= item.second;
        });
    }

    void scheduleBotDiplomacy(hoi5::BotSupplyState& bot) {
        const int owner = bot.owner;
        const bool urgent = botAtWar(owner) || botPreparationTarget(owner) >= 0;
        if (botHours < bot.nextDiplomacy) return;
        bot.nextDiplomacy = botHours+(urgent ? 24 : 168);
        if (owner < 0 || owner >= int(diplomacy.countries.size()) || owner >= int(profiles.size())) return;
        const auto addPolitics = [&](int target,hoi5::ForeignAction action) {
            hoi5::BotTask task{hoi5::BotTask::Kind::politics,botHours};
            task.targetCountry = target;
            task.politicalAction = int(action);
            addBotTask(bot,task);
        };
        int enemy = -1;
        for (int other = 0; other < int(profiles.size()); ++other)
            if (diplomacy.hostile(owner,other)) { enemy = other; break; }
        if (enemy >= 0) {
            bot.course = {hoi5::BotCourse::defense,enemy};
            const auto& policy = diplomacy.countries[owner];
            if (profiles[owner].budget < 0 || policy.warSupport < .4) {
                const auto& info = *std::ranges::find(hoi5::foreignActions,hoi5::ForeignAction::peace,
                    &hoi5::ForeignActionInfo::action);
                if (diplomacy.reason(owner,enemy,info,profiles).empty()) addPolitics(enemy,hoi5::ForeignAction::peace);
            }
        } else if (const int target = botPreparationTarget(owner); target >= 0) {
            const auto action = diplomacy.goals.contains({owner,target}) ? hoi5::ForeignAction::war :
                hoi5::ForeignAction::justify;
            const auto& info = *std::ranges::find(hoi5::foreignActions,action,&hoi5::ForeignActionInfo::action);
            if (diplomacy.reason(owner,target,info,profiles).empty() &&
                (action != hoi5::ForeignAction::war || botWarPreparationReady(bot,target))) addPolitics(target,action);
        } else {
            std::vector<std::pair<double,int>> candidates;
            for (int other = 0; other < int(profiles.size()); ++other) {
                if (other == owner || !std::ranges::any_of(tiles,[&](const auto& tile) { return tile.owner == other; })) continue;
                const auto& relation = diplomacy.relation(owner,other);
                const auto opinion = relation.opinion.find(owner);
                candidates.emplace_back(50+(opinion == relation.opinion.end() ? 0 : opinion->second),other);
            }
            if (const auto* target = hoi5::botChooseClose(bot.rng,candidates)) {
                const bool depends = !bot.dependencies.empty();
                const auto action = depends ? hoi5::ForeignAction::trade : hoi5::ForeignAction::mission;
                const auto& info = *std::ranges::find(hoi5::foreignActions,action,&hoi5::ForeignActionInfo::action);
                if (diplomacy.reason(owner,*target,info,profiles).empty()) addPolitics(*target,action);
            }
        }
        const auto& policy = diplomacy.countries[owner];
        if (profiles[owner].budget > 10000000. && policy.support < .55 && policy.programHours[0] == 0)
            addBotTask(bot,{hoi5::BotTask::Kind::support,botHours});
        if (taxedTreasury(owner).balance()+bot.tradeBalance < 0 && policy.taxReady[2] <= diplomacy.day && policy.taxes[2] < 2)
            addBotTask(bot,{hoi5::BotTask::Kind::tax,botHours});
        if (profiles[owner].budget > 30000000. && bot.intelligence < .8)
            addBotTask(bot,{hoi5::BotTask::Kind::intelligence,botHours});
    }

    bool applyBotPolitics(hoi5::BotSupplyState& bot,const hoi5::BotTask& task) {
        const int owner = bot.owner;
        if (task.kind == hoi5::BotTask::Kind::support)
            return changeSupportProgram(owner,0,720).empty();
        if (task.kind == hoi5::BotTask::Kind::tax)
            return changeTax(owner,2,1).empty();
        if (task.kind == hoi5::BotTask::Kind::intelligence) {
            const double cost = 2000000.*(1+bot.intelligence*4);
            if (cost > botAvailableMoney(bot) || bot.intelligence >= .8) return false;
            profiles[owner].budget -= cost;
            bot.intelligence = std::min(.8,bot.intelligence+.1);
            return true;
        }
        if (task.targetCountry < 0 || task.targetCountry >= int(profiles.size())) return false;
        const auto action = hoi5::ForeignAction(task.politicalAction);
        const auto info = std::ranges::find(hoi5::foreignActions,action,&hoi5::ForeignActionInfo::action);
        return info != std::end(hoi5::foreignActions) &&
            performForeignAction(owner,task.targetCountry,*info).empty();
    }

    bool applyBotTrade(hoi5::BotSupplyState& bot,const hoi5::BotTask& task) {
        const int owner = bot.owner;
        const bool buy = task.kind == hoi5::BotTask::Kind::buy;
        const double money = botAvailableMoney(bot);
        double committed = 0.;
        for (const auto& order : market.contracts)
            if (order.country == owner && order.buy && order.resource != task.resource)
                committed += order.amount*market.unitPrice(owner,order.resource,true);
        double amount = std::max(0.,task.amount);
        if (buy) amount = std::min({amount,
            std::max(0.,money*.15-committed)/std::max(1.,market.unitPrice(owner,task.resource,true)),
            hoi5::freeStorage(capacities[owner],stockpiles[owner],task.resource)});
        else amount = std::min(amount,hoi5::value(stockpiles[owner],task.resource)*.15);
        const double delta = amount-market.contractAmount(owner,task.resource,buy);
        if (std::abs(delta) < std::max(1.,amount*.1)) return true;
        const double limit = hoi5::Market::monthlyCapacity(tiles,profiles)[owner];
        if (!market.changeContract(owner,task.resource,buy,delta,limit)) return false;
        botBalanceRefresh.insert(owner);
        return true;
    }

    void scheduleBotDefense(hoi5::BotSupplyState& bot,int fortSpec) {
        using Task = hoi5::BotTask;
        const int owner = bot.owner;
        const bool atWar = botAtWar(owner);
        std::vector<int> positions(tiles.size());
        int divisionCount = 0;
        for (const auto& unit : divisions) {
            if (unit.owner != owner || unit.combat.strength <= 0) continue;
            ++divisionCount;
            const int tile = unit.r*size+unit.q;
            if (tiles[tile].owner == owner) ++positions[tile];
        }
        if (!air.defenseReplacements.contains(owner)) {
            auto targets = bot.defenseTargets;
            if (atWar || botPreparationTarget(owner) >= 0) {
                const int manpads = std::ranges::find(hoi5::defenseClasses,"manpads_team",
                    &hoi5::DefenseClass::key)-std::begin(hoi5::defenseClasses);
                const int extra = std::max(1,divisionCount/6);
                const auto entry = std::ranges::find(targets,manpads,&std::pair<int,int>::first);
                if (entry == targets.end()) targets.emplace_back(manpads,extra);
                else entry->second += extra;
            }
            std::array<int,std::size(hoi5::defenseClasses)> counts{};
            for (const auto& unit : air.defense)
                if (unit.owner == owner && unit.health > 0) ++counts[unit.type];
            int replacement = -1;
            double cost = 0.;
            std::vector<std::pair<std::string_view,double>> shortages;
            for (const auto [type,target] : targets) {
                if (counts[type] >= target) continue;
                const auto quote = hoi5::AirLayer::defenseQuote(type);
                std::vector<std::pair<std::string_view,double>> lacks;
                for (const auto& [key,amount] : quote.resources) {
                    const double missing = amount-hoi5::value(stockpiles[owner],key);
                    if (missing > 0) lacks.emplace_back(key,missing);
                }
                if (replacement >= 0 && lacks.size() >= shortages.size()) continue;
                replacement = type;
                cost = quote.money;
                shortages = std::move(lacks);
            }
            for (const auto& [key,amount] : shortages)
                addBotTask(bot,{Task::Kind::buy,botHours,-1,key,amount});
            if (replacement >= 0 && shortages.empty() && profiles[owner].budget >= cost+5000000.) {
                if (std::ranges::count_if(bot.tasks,&Task::active) >= 12) {
                    const auto expendable = std::ranges::find_if(bot.tasks,[](const Task& task) {
                        return task.pending() && task.kind == Task::Kind::fortify;
                    });
                    if (expendable != bot.tasks.end()) expendable->status = hoi5::BotTaskStatus::cancelled;
                }
                Task task{Task::Kind::rebuildDefense,botHours};
                task.defenseType = replacement;
                addBotTask(bot,task);
            }
        }
        if (!atWar || std::ranges::any_of(construction.queues[owner],[&](const auto& project) {
            return project.spec == fortSpec;
        }) || std::ranges::any_of(bot.tasks,[](const Task& task) {
            return task.kind == Task::Kind::fortify && task.active();
        })) return;
        int best = -1;
        double bestScore = 0.;
        for (int index = 0; index < int(tiles.size()); ++index) {
            const auto& tile = tiles[index];
            if (positions[index] == 0 || tile.supply < .25 || airDefenseWater(index) ||
                tile.buildings[hoi5::fortification].area >= .25) continue;
            const bool hostileBorder = std::ranges::any_of(botGeography.adjacent(index),[&](int neighbor) {
                return tiles[neighbor].owner >= 0 && diplomacy.hostile(owner,tiles[neighbor].owner);
            });
            const double score = positions[index]+tile.supply;
            if (hostileBorder && score > bestScore) {
                best = index;
                bestScore = score;
            }
        }
        if (best >= 0) addBotTask(bot,{Task::Kind::fortify,botHours,best});
    }

    bool applyBotFortification(const hoi5::BotSupplyState& bot,hoi5::BotTask& task,int spec) {
        auto& queue = construction.queues[bot.owner];
        if (std::ranges::any_of(queue,[&](const auto& project) {
            return project.tile == task.tile && project.spec == spec;
        })) return false;
        const double money = botAvailableMoney(bot);
        auto resources = stockpiles[bot.owner];
        for (const auto& project : queue)
            for (const auto& [key,amount] : project.resources)
                resources[key] -= std::max(0.,amount-hoi5::value(project.resourcesSpent,key));
        if (!construction.enqueue(tiles,size,bot.owner,task.tile,spec,profiles[bot.owner].buildEfficiency).empty())
            return false;
        const auto& project = queue.back();
        if (project.money > money || std::ranges::any_of(project.resources,[&](const auto& required) {
            return hoi5::value(resources,required.first) < required.second;
        })) {
            queue.pop_back();
            return false;
        }
        task.targetCoverage = project.target;
        return true;
    }

    std::set<int> assignBotFront(hoi5::BotSupplyState& bot,bool atWar,const std::set<int>& excluded = {}) const {
        struct Post {
            double priority{}, threat{};
            bool active{}, mobilization{};
            std::set<int> opponents;
        };
        const int owner = bot.owner;
        const auto key = [&](int tile) { return std::pair{tile%size,tile/size}; };
        const auto distance = [&](int a,int b) { return hoi5::supplyHexDistance(a,b,size); };
        const auto position = [&](int unit) { return divisions[unit].r*size+divisions[unit].q; };
        const auto ownLand = [&](int tile) { return tiles[tile].owner == owner && !airDefenseWater(tile); };
        std::vector<int> land, component(tiles.size(),-1);
        std::vector<int> components;
        for (int q = 0; q < size; ++q) for (int r = 0; r < size; ++r) {
            const int seed = r*size+q;
            if (!ownLand(seed)) continue;
            land.push_back(seed);
            if (component[seed] >= 0) continue;
            components.push_back(seed);
            component[seed] = seed;
            std::deque<int> queue{seed};
            while (!queue.empty()) {
                const int tile = queue.front();
                queue.pop_front();
                for (const int next : botGeography.adjacent(tile)) {
                    if (component[next] >= 0 || !ownLand(next)) continue;
                    component[next] = seed;
                    queue.push_back(next);
                }
            }
        }
        const auto previous = std::move(bot.hexAssignments);
        bot.hexAssignments.clear();
        bot.frontQuotas.clear();
        std::set<int> priorPosts, incoming;
        for (const auto& [unit,tile] : previous) priorPosts.insert(tile);
        for (const auto& [pair,day] : diplomacy.goals)
            if (pair.second == owner) incoming.insert(pair.first);
        std::vector<std::vector<int>> unitsByTile(tiles.size());
        for (int i = 0; i < int(divisions.size()); ++i)
            if (divisions[i].combat.strength > 0) unitsByTile[position(i)].push_back(i);
        const int preparation = atWar ? -1 : botPreparationTarget(owner);
        const int focus = bot.expansionTarget;
        const bool focusExists = focus >= 0 && std::ranges::any_of(tiles,[&](const auto& tile) {
            return tile.owner == focus;
        });
        std::map<int,Post> front;
        for (const int tile : land) {
            Post post;
            bool adjacent = false, warning = false, foreign = false;
            for (const int next : botGeography.adjacent(tile)) {
                const int other = tiles[next].owner;
                if (other == owner || airDefenseWater(next)) continue;
                adjacent = true;
                if (other < 0) continue;
                foreign = true;
                post.mobilization |= other == preparation;
                const bool hostile = diplomacy.hostile(owner,other);
                post.active |= hostile;
                warning |= incoming.contains(other);
                if (hostile || incoming.contains(other)) post.opponents.insert(other);
            }
            if (!adjacent || (atWar && !post.active && !warning)) continue;
            bool occupied = false;
            const auto collect = [&](int nearby) {
                for (const int index : unitsByTile[nearby]) {
                    const int other = divisions[index].owner;
                    if (other != owner && (incoming.contains(other) || (atWar && diplomacy.hostile(owner,other))))
                        post.threat += botMilitaryVector(divisions[index])[hoi5::attack];
                }
            };
            for (const int index : unitsByTile[tile]) occupied |= divisions[index].owner == owner;
            collect(tile);
            for (const int next : botGeography.adjacent(tile)) collect(next);
            post.priority = 2+tiles[tile].supply+(occupied ? 2 : 0)+priorPosts.contains(tile);
            if (atWar) post.priority += post.threat/20.;
            else {
                post.priority += foreign ? 2 : 0;
                if (preparation >= 0) post.priority += (post.mobilization ? 20 : 0)+4*tiles[tile].supply;
                if (focusExists) post.priority += 3./(1+distance(tile,capitals[focus]));
            }
            front.emplace(tile,std::move(post));
        }
        std::set<int> pinned;
        if (front.empty()) return pinned;
        if (!atWar) bot.offensiveFocus = -1;
        else if (!front.contains(bot.offensiveFocus)) {
            bot.offensiveFocus = -1;
            const auto rank = [&](int tile) { return std::pair{tiles[tile].supply,front.at(tile).priority}; };
            for (const int tile : land)
                if (front.contains(tile) && front.at(tile).active &&
                    (bot.offensiveFocus < 0 || rank(tile) > rank(bot.offensiveFocus))) bot.offensiveFocus = tile;
        }
        for (const int group : components) {
            std::vector<int> units, localFront;
            for (int i = 0; i < int(divisions.size()); ++i) {
                const auto& unit = divisions[i];
                if (unit.owner == owner && unit.combat.strength > 0 && unit.battle < 0 &&
                    !unit.retreating && !excluded.contains(i) && component[position(i)] == group) units.push_back(i);
            }
            for (const int tile : land)
                if (component[tile] == group && front.contains(tile)) localFront.push_back(tile);
            if (std::ranges::any_of(localFront,[&](int tile) { return front.at(tile).mobilization; }))
                std::erase_if(localFront,[&](int tile) { return !front.at(tile).mobilization; });
            if (units.empty() || localFront.empty()) continue;
            const int capital = capitals[owner];
            if (capital >= 0 && component[capital] == group && !front.contains(capital) &&
                units.size() >= localFront.size()+3) {
                int reserve = -1;
                for (const int index : units) {
                    const auto& unit = divisions[index];
                    if (unit.attackRoute || (!unit.route.empty() && unit.route.back() != capital)) continue;
                    if (index == bot.reserve) { reserve = index; break; }
                    if (reserve < 0 || distance(position(index),capital) < distance(position(reserve),capital)) reserve = index;
                }
                if (reserve >= 0) {
                    bot.reserve = reserve;
                    bot.hexAssignments[reserve] = capital;
                    if (!divisions[reserve].route.empty()) pinned.insert(reserve);
                    std::erase(units,reserve);
                }
            }
            const auto rank = [&](int tile) { return std::pair{-front.at(tile).priority,key(tile)}; };
            std::ranges::sort(localFront,{},rank);
            auto watchPosts = localFront;
            std::ranges::stable_sort(watchPosts,{},[&](int tile) { return !front.at(tile).active; });
            std::vector<int> selected, pressured;
            std::set<int> covered;
            for (const int tile : watchPosts) {
                const auto& opponents = front.at(tile).opponents;
                if (std::ranges::any_of(opponents,[&](int other) { return !covered.contains(other); })) {
                    selected.push_back(tile);
                    covered.insert(opponents.begin(),opponents.end());
                }
                if (selected.size() == units.size()) break;
            }
            for (const int tile : localFront) if (front.at(tile).threat > 0.) pressured.push_back(tile);
            for (const int tile : pressured.empty() ? localFront : pressured) {
                if (selected.size() == units.size()) break;
                if (std::ranges::find(selected,tile) == selected.end()) selected.push_back(tile);
            }
            std::map<int,int> quota, counts;
            for (const int tile : selected) quota[tile] = 1;
            const int concentrating = pressured.empty() ? int(selected.size()) :
                std::ranges::count_if(selected,[&](int tile) { return front.at(tile).threat > 0.; });
            const int cap = concentrating <= 1 ? int(units.size()) : std::max(2,int((units.size()+1)/2));
            for (std::size_t i = selected.size(); i < units.size(); ++i) {
                int best = -1;
                double bestScore = 0.;
                for (const int tile : selected) {
                    const auto& post = front.at(tile);
                    if (quota[tile] >= cap || (!pressured.empty() && post.threat <= 0.)) continue;
                    const double score = (post.priority+(atWar && tile == bot.offensiveFocus ? 4 : 0))/(1+quota[tile]);
                    if (best < 0 || score > bestScore) { best = tile; bestScore = score; }
                }
                if (best < 0) break;
                ++quota[best];
            }
            bot.frontQuotas.insert(quota.begin(),quota.end());
            std::erase_if(units,[&](int index) {
                const auto& unit = divisions[index];
                if (unit.route.empty()) return false;
                const int target = unit.route.back();
                if (!unit.attackRoute && std::ranges::find(localFront,target) == localFront.end()) return false;
                bot.hexAssignments[index] = target;
                if (quota.contains(target)) ++counts[target];
                pinned.insert(index);
                return true;
            });
            std::erase_if(units,[&](int index) {
                const int tile = position(index);
                if (!quota.contains(tile) || counts[tile] >= quota[tile]) return false;
                bot.hexAssignments[index] = tile;
                ++counts[tile];
                return true;
            });
            std::vector<int> slots;
            for (const int tile : selected) if (counts[tile] == 0) slots.push_back(tile);
            for (const int tile : selected)
                for (int n = std::max(1,counts[tile]); n < quota[tile]; ++n) slots.push_back(tile);
            for (const int tile : slots) {
                const auto score = [&](int index) {
                    const auto old = previous.find(index);
                    return distance(position(index),tile)-(old != previous.end() && old->second == tile ? 2 : 0);
                };
                auto best = units.end();
                for (auto it = units.begin(); it != units.end(); ++it) {
                    const int source = position(*it);
                    const bool onFront = std::ranges::find(localFront,source) != localFront.end();
                    if (onFront && counts[tile] != 0 && !(counts[source] > 0 && source != tile &&
                        front.at(tile).threat > 1.5*front.at(source).threat+10)) continue;
                    if (best == units.end() || score(*it) < score(*best)) best = it;
                }
                if (best == units.end()) continue;
                bot.hexAssignments[*best] = tile;
                ++counts[tile];
                units.erase(best);
            }
        }
        return pinned;
    }

    struct BotMovement { int unit, tile; bool withdraw = false, attack = false; };

    void synchronizeBotArmies(hoi5::BotSupplyState& bot,bool atWar) {
        const int owner = bot.owner;
        const auto position = [&](int index) { return divisions[index].r*size+divisions[index].q; };
        const auto opponentAt = [&](int post) {
            int opponent = -1;
            for (const int neighbor : botGeography.adjacent(post)) {
                const int other = tiles[neighbor].owner;
                if (other < 0 || other == owner) continue;
                if (diplomacy.hostile(owner,other) || diplomacy.goals.contains({owner,other}) ||
                    diplomacy.goals.contains({other,owner})) {
                    opponent = other;
                    if (diplomacy.hostile(owner,other)) break;
                }
            }
            return opponent;
        };
        std::map<int,std::vector<int>> groups;
        for (int index = 0; index < int(divisions.size()); ++index) {
            auto& unit = divisions[index];
            if (unit.owner != owner) continue;
            unit.armyId = 0;
            if (unit.combat.strength <= 0.) continue;
            const auto assigned = bot.hexAssignments.find(index);
            const int opponent = assigned == bot.hexAssignments.end() ? -1 : opponentAt(assigned->second);
            groups[opponent].push_back(index);
        }
        std::set<int> retained;
        std::map<int,int> nextIds;
        int number = 0;
        for (auto& [opponent,members] : groups) {
            std::ranges::sort(members,{},[&](int index) {
                const auto assigned = bot.hexAssignments.find(index);
                return std::tuple{assigned == bot.hexAssignments.end() ? std::numeric_limits<int>::max() :
                    assigned->second,position(index),index};
            });
            for (int offset = 0,chunk = 0; offset < int(members.size()); offset += armyCapacity,++chunk) {
                const int key = (opponent+2)*1000+chunk;
                int id = 0;
                if (const auto existing = bot.armyIds.find(key); existing != bot.armyIds.end() &&
                    std::ranges::any_of(armies,[&](const Army& army) {
                        return army.id == existing->second && army.owner == owner;
                    })) id = existing->second;
                const int end = std::min(offset+armyCapacity,int(members.size()));
                std::set<int> selection(members.begin()+offset,members.begin()+end);
                if (!id) id = createArmy(owner,selection);
                else addDivisionsToArmy(owner,id,selection);
                auto army = std::ranges::find(armies,id,&Army::id);
                if (!id || army == armies.end()) continue;
                retained.insert(id);
                nextIds[key] = id;
                army->name = opponent < 0 ? "Резервная армия "+std::to_string(++number) :
                    "Фронтовая армия "+std::to_string(++number);
                army->front.clear();
                for (int index : selection)
                    if (const auto assigned = bot.hexAssignments.find(index); assigned != bot.hexAssignments.end() &&
                        tiles[assigned->second].owner == owner)
                        army->front.push_back(assigned->second);
                std::ranges::sort(army->front);
                army->front.erase(std::unique(army->front.begin(),army->front.end()),army->front.end());
                army->offensive.clear();
                if (atWar && opponent >= 0) for (int post : army->front)
                    for (int neighbor : botGeography.adjacent(post))
                        if (tiles[neighbor].owner == opponent && !airDefenseWater(neighbor))
                            army->offensive.push_back(neighbor);
                std::ranges::sort(army->offensive);
                army->offensive.erase(std::unique(army->offensive.begin(),army->offensive.end()),army->offensive.end());
                army->borderOwner = opponent;
                army->automaticLine = false;
                army->executing = true;
                army->reviewHours = 0;
            }
        }
        std::erase_if(armies,[&](const Army& army) {
            return army.owner == owner && !retained.contains(army.id);
        });
        bot.armyIds = std::move(nextIds);
    }

    bool applyBotMovement(const BotMovement& order) {
        auto& unit = divisions[order.unit];
        const int origin = unit.r*size+unit.q;
        const int targetOwner = tiles[order.tile].owner;
        const bool validTarget = order.attack ? targetOwner < 0 || diplomacy.hostile(unit.owner,targetOwner)
                                              : targetOwner == unit.owner;
        if (unit.retreating || unit.combat.strength <= 0. || !validTarget ||
            (unit.battle >= 0 && !order.withdraw)) return false;
        if (order.withdraw && (airDefenseWater(order.tile) || defended(order.tile,unit.owner) ||
            std::ranges::find(botGeography.adjacent(origin),order.tile) == botGeography.adjacent(origin).end()))
            return false;
        if (!order.withdraw && !unit.route.empty() && unit.route.back() == order.tile) return true;
        if (order.withdraw) detachDivisionFromBattle(order.unit);
        auto route = divisionRoute(unit,origin,order.tile);
        if (origin != order.tile && route.empty()) return false;
        if (order.attack && route.size() > 1) route.resize(1);
        unit.route = std::move(route);
        unit.attackRoute = order.attack && !unit.route.empty() && tiles[unit.route.front()].owner != unit.owner &&
            (tiles[unit.route.front()].owner < 0 || diplomacy.hostile(unit.owner,tiles[unit.route.front()].owner));
        unit.progress = unit.visualProgress = 0.;
        if (order.withdraw) {
            unit.retreating = true;
            unit.organization *= .8;
        }
        return true;
    }

    std::set<int> planBotRecovery(hoi5::BotSupplyState& bot,bool atWar,std::vector<BotMovement>& orders) const {
        const int owner = bot.owner;
        const auto position = [&](int index) { return divisions[index].r*size+divisions[index].q; };
        std::vector<int> friendly;
        std::vector<std::vector<int>> enemies(tiles.size());
        std::vector<double> localDefense(tiles.size());
        for (int index = 0; index < int(divisions.size()); ++index) {
            const auto& unit = divisions[index];
            if (unit.combat.strength <= 0.) continue;
            const int tile = position(index);
            if (unit.owner == owner) {
                friendly.push_back(index);
                localDefense[tile] += botMilitaryVector(unit)[hoi5::defense];
            } else if (diplomacy.hostile(owner,unit.owner)) enemies[tile].push_back(index);
        }
        const auto nearby = [&](int tile,auto visit) {
            for (const int index : enemies[tile]) visit(index);
            for (const int neighbor : botGeography.adjacent(tile))
                for (const int index : enemies[neighbor]) visit(index);
        };
        const auto enemyCount = [&](int tile) {
            int count = 0;
            nearby(tile,[&](int) { ++count; });
            return count;
        };
        std::set<int> used;
        if (atWar) for (const int index : friendly) {
            const auto& unit = divisions[index];
            if (unit.retreating) continue;
            const int origin = position(index);
            double threat = 0.;
            int enemyUnits = 0, hostileSides = 0;
            nearby(origin,[&](int enemy) { ++enemyUnits; threat += botMilitaryVector(divisions[enemy])[hoi5::attack]; });
            std::vector<int> exits;
            for (const int tile : botGeography.adjacent(origin)) {
                const int other = tiles[tile].owner;
                if (other == owner && !airDefenseWater(tile) && enemies[tile].empty()) exits.push_back(tile);
                if (other >= 0 && diplomacy.hostile(owner,other)) ++hostileSides;
            }
            const bool weak = unit.organization < unit.maxOrganization*.25 || unit.lastSupplyRatio < .12;
            const bool trapped = exits.size() <= 1 && hostileSides >= 3;
            const bool overwhelming = threat > localDefense[origin]*1.8;
            const double pressureLimit = (weak ? botMilitaryVector(unit)[hoi5::defense] : localDefense[origin])*.8;
            if (enemyUnits > 0 && (weak || trapped || overwhelming) && !exits.empty() &&
                threat > pressureLimit && (unit.battle < 0 || trapped || (weak && overwhelming))) {
                const auto rank = [&](int tile) { return std::pair{enemyCount(tile),-tiles[tile].supply}; };
                const int target = *std::ranges::min_element(exits,{},rank);
                orders.push_back({index,target,true});
                used.insert(index);
            } else if (!unit.route.empty() && unit.attackRoute && unit.battle < 0) {
                const int target = unit.route.back();
                double defense = 0., committedAttack = 0.;
                for (const int enemy : enemies[target]) defense += botMilitaryVector(divisions[enemy])[hoi5::defense];
                for (const int ally : friendly) {
                    const auto& other = divisions[ally];
                    const auto battle = battles.find(other.battle);
                    const bool engaged = battle != battles.end() && other.battle == target &&
                        std::ranges::find(battle->second.attackers,ally) != battle->second.attackers.end();
                    if (engaged || (other.attackRoute && !other.route.empty() && other.route.back() == target))
                        committedAttack += botMilitaryVector(other)[hoi5::attack];
                }
                if (weak || defense > committedAttack*1.2) {
                    orders.push_back({index,origin});
                    used.insert(index);
                }
            }
        }
        std::erase_if(bot.resting,[&](int index) { return divisions[index].combat.strength <= 0.; });
        for (const int index : friendly) {
            const auto& unit = divisions[index];
            const double organization = unit.organization/std::max(1.,unit.maxOrganization);
            if (organization < .4 || unit.lastSupplyRatio < .12) bot.resting.insert(index);
            else if (organization >= .8 && unit.lastSupplyRatio >= .25) bot.resting.erase(index);
            if (!bot.resting.contains(index) || !used.insert(index).second) continue;
            if (unit.battle >= 0 || unit.retreating) continue;
            const int origin = position(index);
            if (tiles[origin].owner == owner && unit.route.empty() && supplyRatio(unit) >= .25 &&
                enemyCount(origin) == 0) continue;
            const auto safe = [&](int tile) {
                return tiles[tile].owner == owner && tiles[tile].supply >= .35 && enemyCount(tile) == 0;
            };
            if (!unit.route.empty() && safe(unit.route.back())) continue;
            const auto distance = [&](int tile) { return hoi5::supplyHexDistance(origin,tile,size); };
            std::vector<int> sites;
            for (int q = 0; q < size; ++q) for (int r = 0; r < size; ++r) {
                const int tile = r*size+q;
                if (distance(tile) <= 3 && !airDefenseWater(tile) && safe(tile)) sites.push_back(tile);
            }
            std::ranges::stable_sort(sites,{},[&](int tile) { return distance(tile)-tiles[tile].supply; });
            if (sites.empty() && unit.route.empty() && organization >= .65 && unit.lastSupplyRatio < .12)
                used.erase(index);
            for (std::size_t i = 0; i < std::min<std::size_t>(5,sites.size()); ++i) {
                const int tile = sites[i];
                if (tile == origin && unit.route.empty()) break;
                if (tile == origin || !divisionRoute(unit,origin,tile).empty()) {
                    orders.push_back({index,tile});
                    break;
                }
            }
        }
        return used;
    }

    const std::map<int,int>& botOffensiveDistances(hoi5::BotSupplyState& bot,int enemy,
                                                   const std::vector<int>& targets) const {
        static const std::map<int,int> empty;
        if (targets.empty()) return empty;
        const auto cached = bot.warObjectives.find(enemy);
        if (cached != bot.warObjectives.end() && botHours < cached->second.hour+168 &&
            tiles[cached->second.anchor].owner == enemy &&
            std::ranges::any_of(targets,[&](int tile) { return cached->second.distances.contains(tile); }))
            return cached->second.distances;
        const auto key = [&](int tile) { return std::pair{tile%size,tile/size}; };
        const auto distance = [&](int a,int b) { return hoi5::supplyHexDistance(a,b,size); };
        const auto flood = [&](const std::vector<int>& seeds) {
            std::vector<int> distances(tiles.size(),-1);
            std::deque<int> queue(seeds.begin(),seeds.end());
            for (const int seed : seeds) distances[seed] = 0;
            while (!queue.empty()) {
                const int tile = queue.front();
                queue.pop_front();
                for (const int next : botGeography.adjacent(tile)) {
                    if (distances[next] >= 0 || tiles[next].owner != enemy || !botGeography.hasRegion(next)) continue;
                    distances[next] = distances[tile]+1;
                    queue.push_back(next);
                }
            }
            return distances;
        };
        const auto reachable = flood(targets);
        const int capital = capitals[enemy];
        const auto profiles = botGeography.profiles(tiles,enemy,capital,[&](int tile) { return airDefenseWater(tile); });
        int anchor = -1;
        std::tuple<double,int,std::pair<int,int>> best{};
        for (const auto& region : profiles) {
            if (reachable[region.tiles.front()] < 0) continue;
            const auto rank = [&](int tile) {
                const auto& buildings = tiles[tile].buildings;
                return std::pair{tile == capital,buildings[hoi5::industry].area+
                    buildings[hoi5::supplyDepot].area+buildings[hoi5::city].area};
            };
            const int candidate = *std::ranges::max_element(region.tiles,{},rank);
            int nearest = std::numeric_limits<int>::max();
            for (const int target : targets) nearest = std::min(nearest,distance(candidate,target));
            const auto score = std::tuple{region.importance/(1+nearest),region.base,key(region.anchor)};
            if (anchor < 0 || score > best) { anchor = candidate; best = score; }
        }
        if (anchor < 0) return empty;
        const auto distances = flood({anchor});
        auto starts = targets;
        std::erase_if(starts,[&](int tile) { return distances[tile] < 0; });
        std::ranges::sort(starts,{},[&](int tile) { return std::pair{distances[tile],key(tile)}; });
        std::vector<int> approaches;
        hoi5::BotSupplyState::WarObjective objective{botHours,anchor,{}};
        for (const int start : starts) {
            if (std::ranges::any_of(approaches,[&](int other) { return distance(start,other) < 3; })) continue;
            approaches.push_back(start);
            int tile = start;
            while (true) {
                objective.distances[tile] = distances[tile];
                if (distances[tile] == 0) break;
                int next = -1;
                for (const int neighbor : botGeography.adjacent(tile))
                    if (distances[neighbor] == distances[tile]-1 && (next < 0 || key(neighbor) < key(next))) next = neighbor;
                tile = next;
            }
            if (approaches.size() == 3) break;
        }
        return bot.warObjectives.insert_or_assign(enemy,std::move(objective)).first->second.distances;
    }

    void planBotAttacks(hoi5::BotSupplyState& bot,const std::set<int>& used,std::vector<BotMovement>& orders) const {
        const int owner = bot.owner;
        const auto position = [&](int index) { return divisions[index].r*size+divisions[index].q; };
        const auto stationary = [&](int index) {
            const auto& unit = divisions[index];
            return !used.contains(index) && unit.battle < 0 && unit.route.empty() && !unit.retreating;
        };
        std::vector<int> ready;
        std::vector<int> sourceCounts(tiles.size());
        std::vector<std::vector<int>> unitsByTile(tiles.size());
        std::vector<hoi5::BotMilitary> military(divisions.size());
        int divisionCount = 0;
        for (int index = 0; index < int(divisions.size()); ++index) {
            const auto& unit = divisions[index];
            if (unit.combat.strength <= 0.) continue;
            unitsByTile[position(index)].push_back(index);
            military[index] = botMilitaryVector(unit);
            if (unit.owner != owner) continue;
            ++divisionCount;
            if (!stationary(index)) continue;
            ++sourceCounts[position(index)];
            if (unit.organization >= unit.maxOrganization*.65 && unit.lastSupplyRatio >= .12) ready.push_back(index);
        }
        const int limit = divisionCount-2;
        if (limit <= 0) return;
        const auto enemyLand = [&](int tile) {
            return tiles[tile].owner >= 0 && diplomacy.hostile(owner,tiles[tile].owner) && !airDefenseWater(tile);
        };
        const auto enemyUnits = [&](int tile) {
            return std::ranges::any_of(unitsByTile[tile],[&](int index) {
                return diplomacy.hostile(owner,divisions[index].owner);
            });
        };
        std::set<std::pair<int,int>> coordinates;
        for (const int index : ready) for (const int tile : botGeography.adjacent(position(index)))
            if (enemyLand(tile)) coordinates.emplace(tile%size,tile/size);
        std::map<int,std::vector<int>> byEnemy;
        for (const auto [q,r] : coordinates) byEnemy[tiles[r*size+q].owner].push_back(r*size+q);
        std::map<int,const std::map<int,int>*> corridors;
        for (const auto& [enemy,targets] : byEnemy) corridors[enemy] = &botOffensiveDistances(bot,enemy,targets);
        std::vector<std::pair<double,std::vector<BotMovement>>> choices;
        for (const auto [q,r] : coordinates) {
            const int target = r*size+q;
            std::set<int> friendly;
            int hostile = 0;
            for (const int tile : botGeography.adjacent(target)) {
                if (tiles[tile].owner == owner && !airDefenseWater(tile)) friendly.insert(tile);
                if (enemyLand(tile)) ++hostile;
            }
            if (hostile >= 2 && friendly.size() < 2) continue;
            double defense = 0.;
            for (const int unit : unitsByTile[target])
                if (diplomacy.hostile(owner,divisions[unit].owner)) defense += military[unit][hoi5::defense];
            std::vector<int> pool;
            std::map<int,int> ranksBySource;
            for (const int index : ready)
                if (friendly.contains(position(index)) && (defense <= 0. || divisions[index].lastSupplyRatio >= .25))
                    pool.push_back(index);
            std::ranges::stable_sort(pool,{},[&](int unit) { return -military[unit][hoi5::attack]; });
            std::map<int,int> ranks;
            for (const int index : pool) ranks[index] = ranksBySource[position(index)]++;
            std::ranges::stable_sort(pool,{},[&](int index) { return std::pair{ranks[index],-military[index][hoi5::attack]}; });
            const double widthLimit = (80.+40.*std::max(0,int(ranksBySource.size())-1))*1.5;
            double width = 0., attack = 0.;
            auto counts = sourceCounts;
            std::set<int> protectedUnits, selected;
            std::vector<BotMovement> package;
            for (const int index : pool) {
                const int source = position(index);
                const double unitWidth = divisions[index].combat.width;
                if (protectedUnits.contains(index) || (defense > 0. && !package.empty() && width+unitWidth > widthLimit))
                    continue;
                if (counts[source] <= 1) {
                    const auto& neighbors = botGeography.adjacent(source);
                    if (std::ranges::any_of(neighbors,[&](int tile) {
                        return diplomacy.goals.contains({tiles[tile].owner,owner});
                    })) continue;
                    std::vector<int> support;
                    bool exposed = false;
                    for (const int tile : neighbors) {
                        exposed |= tile != target && enemyUnits(tile);
                        for (const int ally : unitsByTile[tile])
                            if (divisions[ally].owner == owner && stationary(ally) && !selected.contains(ally))
                                support.push_back(ally);
                    }
                    if (source == capitals[owner] || (hostile > 0 && friendly.size() < 2) ||
                        (defense == 0. && exposed) || (defense > 0. && support.size() < 2)) continue;
                    if (!support.empty()) protectedUnits.insert(support.front());
                }
                package.push_back({index,target,false,true});
                selected.insert(index);
                width += unitWidth;
                attack += military[index][hoi5::attack];
                --counts[source];
                if (int(package.size()) >= limit || (defense == 0. && package.size() >= std::max<std::size_t>(1,friendly.size())))
                    break;
            }
            const double threshold = 1.05-.15*bot.aggression;
            if (package.empty() || attack <= std::max(8.,defense*threshold)) continue;
            double value = attack/std::max(8.,defense)+.1*tiles[target].buildings[hoi5::industry].area;
            const auto& corridor = *corridors.at(tiles[target].owner);
            if (const auto entry = corridor.find(target); entry != corridor.end()) value += .6/(1+entry->second);
            choices.emplace_back(value,std::move(package));
        }
        if (const auto* package = hoi5::botChooseClose(bot.rng,choices))
            orders.insert(orders.end(),package->begin(),package->end());
    }

    void planBotFrontMoves(hoi5::BotSupplyState& bot,std::vector<BotMovement>& orders) {
        const bool atWar = botAtWar(bot.owner);
        if (!atWar && botHours < bot.nextPeaceDeployment) return;
        if (!atWar) bot.nextPeaceDeployment = botHours+48;
        if (atWar && bot.course.first != hoi5::BotCourse::defense) {
            for (int other = 0; other < int(profiles.size()); ++other) {
                if (!diplomacy.hostile(bot.owner,other)) continue;
                bot.course = {hoi5::BotCourse::defense,other};
                bot.courseSince = botHours;
                break;
            }
        }
        auto used = planBotRecovery(bot,atWar,orders);
        const auto pinned = assignBotFront(bot,atWar,used);
        synchronizeBotArmies(bot,atWar);
        std::set<int> coveredPosts;
        for (const auto& unit : divisions)
            if (unit.owner == bot.owner && unit.combat.strength > 0 && !unit.retreating)
                coveredPosts.insert(unit.route.empty() ? unit.r*size+unit.q : unit.route.back());
        for (const auto& [index,tile] : bot.hexAssignments) {
            const auto& unit = divisions[index];
            if (pinned.contains(index) || tile == unit.r*size+unit.q ||
                unit.organization < unit.maxOrganization*.65 ||
                (bot.resting.contains(index) && tiles[tile].supply < .25)) continue;
            const auto last = bot.lastOrders.find(index);
            if (last != bot.lastOrders.end() && botHours-last->second < 24) continue;
            // Movement consumes 1.4 organization per hex. Keep a 25% planning margin
            // for optional reinforcements, while still filling uncovered posts.
            if (coveredPosts.contains(tile)) {
                const auto route = divisionRoute(unit,unit.r*size+unit.q,tile);
                if (route.empty() || unit.organization-1.4*1.25*route.size() < unit.maxOrganization*.65)
                    continue;
            }
            orders.push_back({index,tile});
            bot.lastOrders[index] = botHours;
            used.insert(index);
        }
        if (atWar) planBotAttacks(bot,used,orders);
    }

    void updateBots(int hours,hoi5::DebugProfiler* debug) {
        if (supplyBots.empty()) return;
        hoi5::DebugMeasure total(debug,"ai_total");
        botHours += hours;
        const int spec = std::ranges::find(hoi5::constructionSpecs,hoi5::supplyDepot,
            &hoi5::ConstructionSpec::building)-std::begin(hoi5::constructionSpecs);
        const int fortSpec = std::ranges::find(hoi5::constructionSpecs,hoi5::fortification,
            &hoi5::ConstructionSpec::building)-std::begin(hoi5::constructionSpecs);
        using Task = hoi5::BotTask;
        using Status = hoi5::BotTaskStatus;
        std::vector<std::pair<hoi5::BotSupplyState*,Task*>> orders;
        std::vector<BotMovement> movements;
        for (auto& bot : supplyBots) {
            if (std::ranges::none_of(tiles,[&](const auto& tile) { return tile.owner == bot.owner; })) continue;
            {
                hoi5::DebugMeasure reviews(debug,"ai_reviews");
                updateBotReviews(bot,debug);
            }
            if (botHours >= bot.nextDaily || bot.urgent) {
                hoi5::DebugMeasure daily(debug,"ai_daily");
                {
                    hoi5::DebugMeasure regions(debug,"ai_regions");
                    bot.regions = botGeography.profiles(tiles,bot.owner,capitals[bot.owner],
                        [&](int tile) { return airDefenseWater(tile); });
                    updateBotRegionalMilitary(bot);
                    sampleBotMilitary(bot,bot.owner);
                }
                {
                    hoi5::DebugMeasure supply(debug,"ai_supply_planning");
                    scheduleBotSupply(bot,spec);
                }
                {
                    hoi5::DebugMeasure defense(debug,"ai_defense_planning");
                    scheduleBotDefense(bot,fortSpec);
                }
                {
                    hoi5::DebugMeasure recruitment(debug,"ai_recruitment_planning");
                    const bool mobilizing = botPreparationTarget(bot.owner) >= 0;
                    if (mobilizing) scheduleBotMobilizationStock(bot);
                    scheduleBotRecruitment(bot,mobilizing);
                }
                {
                    hoi5::DebugMeasure aviation(debug,"ai_air_planning");
                    scheduleBotAir(bot);
                }
                {
                    hoi5::DebugMeasure economy(debug,"ai_economy_planning");
                    scheduleBotEconomy(bot);
                }
                {
                    hoi5::DebugMeasure expansion(debug,"ai_expansion_planning");
                    scheduleBotExpansion(bot);
                }
                {
                    hoi5::DebugMeasure diplomacyTiming(debug,"ai_diplomacy_planning");
                    scheduleBotDiplomacy(bot);
                }
                bot.nextDaily = botHours+24;
            }
            if (botHours >= bot.nextMicro || bot.urgent) {
                hoi5::DebugMeasure micro(debug,"ai_micro");
                {
                    hoi5::DebugMeasure fronts(debug,"ai_front_planning");
                    planBotFrontMoves(bot,movements);
                }
                bot.nextMicro = botHours+6;
                bot.urgent = false;
            }
            hoi5::DebugMeasure tasks(debug,"ai_tasks");
            for (auto& task : bot.tasks) {
                if (task.status == Status::executing && task.kind == Task::Kind::claim) {
                    if (task.tile < 0 || task.tile >= int(tiles.size())) task.status = Status::failed;
                    else if (tiles[task.tile].owner == bot.owner) task.status = Status::succeeded;
                    else if (tiles[task.tile].owner >= 0 || botHours-task.createdHour > 168)
                        task.status = Status::failed;
                } else if (task.status == Status::executing &&
                    (task.kind == Task::Kind::supply || task.kind == Task::Kind::fortify ||
                     task.kind == Task::Kind::build)) {
                    const auto& tile = tiles[task.tile];
                    const int projectSpec = task.kind == Task::Kind::supply ? spec :
                        task.kind == Task::Kind::fortify ? fortSpec : task.buildingSpec;
                    if (projectSpec < 0 || projectSpec >= int(std::size(hoi5::constructionSpecs))) {
                        task.status = Status::failed;
                        continue;
                    }
                    const auto& building = tile.buildings[hoi5::constructionSpecs[projectSpec].building];
                    if (tile.owner != bot.owner) task.status = Status::cancelled;
                    else if (building.health > .9 && building.area >= task.targetCoverage) task.status = Status::succeeded;
                    else if (std::ranges::none_of(construction.queues[bot.owner],[&](const auto& project) {
                        return project.tile == task.tile && project.spec == projectSpec;
                    })) task.status = Status::failed;
                } else if (task.status == Status::waitingMarket) {
                    if (botMarketTick > task.marketTick)
                        task.status = std::ranges::any_of(market.last.fills,[&](const auto& fill) {
                            return (task.kind == Task::Kind::buy ? fill.buyer : fill.seller) == bot.owner &&
                                fill.resource == task.resource && fill.amount > 0;
                        }) ? Status::succeeded : Status::failed;
                } else if (task.status == Status::waitingOffer) {
                    const auto action = hoi5::ForeignAction(task.politicalAction);
                    const bool waiting = std::ranges::any_of(diplomacy.offers,[&](const auto& offer) {
                        return offer.actor == bot.owner && offer.target == task.targetCountry && offer.action == action;
                    });
                    if (!waiting) {
                        const auto& relation = diplomacy.relation(bot.owner,task.targetCountry);
                        const bool accepted = action == hoi5::ForeignAction::peace ? !relation.war :
                            action == hoi5::ForeignAction::transit ? diplomacy.canTransit(bot.owner,task.targetCountry) :
                            relation.treaties.contains(action);
                        task.status = accepted ? Status::succeeded : Status::failed;
                    }
                } else if (task.pending() && botHours >= task.retryHour) {
                    if (botHours-task.createdHour > 336) task.status = Status::cancelled;
                    else {
                        orders.emplace_back(&bot,&task);
                        task.retryHour = botHours+24;
                    }
                }
            }
        }
        for (const auto& movement : movements) applyBotMovement(movement);
        for (const auto& [bot,task] : orders) {
            if (task->kind == Task::Kind::supply)
                task->status = applyBotSupply(*bot,*task,spec) ? Status::executing : Status::blocked;
            else if (task->kind == Task::Kind::fortify)
                task->status = applyBotFortification(*bot,*task,fortSpec) ? Status::executing : Status::blocked;
            else if (task->kind == Task::Kind::rebuildDefense) {
                const int owner = bot->owner;
                if (air.defenseReplacements.contains(owner)) task->status = Status::blocked;
                else {
                    air.enqueueDefense(owner,task->defenseType,profiles[owner].budget,stockpiles[owner]);
                    task->status = air.defenseReplacements.contains(owner) ? Status::succeeded : Status::blocked;
                }
            } else if (task->kind == Task::Kind::recruit) {
                task->status = applyBotRecruitment(*bot,*task) ? Status::succeeded : Status::blocked;
            } else if (task->kind == Task::Kind::air) {
                task->status = applyBotAir(*bot,*task) ? Status::succeeded : Status::blocked;
            } else if (task->kind == Task::Kind::claim) {
                task->status = applyBotClaim(*bot,*task) ? Status::executing : Status::blocked;
            } else if (task->kind == Task::Kind::build) {
                task->status = applyBotConstruction(*bot,*task) ? Status::executing : Status::blocked;
            } else if (task->kind == Task::Kind::specialize) {
                task->status = applyBotSpecialization(*bot,*task) ? Status::succeeded : Status::blocked;
            } else if (task->kind == Task::Kind::politics || task->kind == Task::Kind::support ||
                       task->kind == Task::Kind::tax || task->kind == Task::Kind::intelligence) {
                if (!applyBotPolitics(*bot,*task)) task->status = Status::blocked;
                else if (task->kind == Task::Kind::politics &&
                    !hoi5::offerNames(hoi5::ForeignAction(task->politicalAction)).first.empty())
                    task->status = Status::waitingOffer;
                else task->status = Status::succeeded;
            } else {
                task->status = applyBotTrade(*bot,*task) ? Status::waitingMarket : Status::blocked;
                if (task->status == Status::waitingMarket) task->marketTick = botMarketTick;
            }
        }
        if (!botBalanceRefresh.empty()) {
            const int owner = *botBalanceRefresh.begin();
            botBalanceRefresh.erase(botBalanceRefresh.begin());
            auto& bot = *std::ranges::find(supplyBots,owner,&hoi5::BotSupplyState::owner);
            bot.tradeBalance = 0.;
            for (const auto& fill : forecastMarketPlan(botMarketTick).fills) {
                if (fill.seller == owner) bot.tradeBalance += fill.amount*fill.price;
                if (fill.buyer == owner) bot.tradeBalance -= fill.amount*fill.price;
            }
        }
    }

    void advance(int hours,hoi5::DebugProfiler* debug = nullptr,std::optional<int> marketRotation = std::nullopt) {
        if (hours <= 0) return;
        using Clock = hoi5::DebugProfiler::Clock;
        {
            hoi5::DebugMeasure timing(debug,"server_politics");
            advancePoliticsHours(hours,debug);
        }
        if (marketRotation && !stockpiles.empty()) {
            hoi5::DebugMeasure timing(debug,"server_market");
            executeWeeklyMarket(*marketRotation);
        }
        for (std::size_t country = 0; country < production.size(); ++country) {
            const auto economyStart = Clock::now();
            auto& stocks = stockpiles[country];
            profiles[country].budget += taxedTreasury(int(country)).operatingBalance()*hours/720.;
            news.alert(diplomacy.day,int(country),countryNames[country],"treasury_empty",profiles[country].budget <= 0,
                "Казна исчерпана","Средств в казне нет. Проверьте расходы, программы поддержки и обязательства.",
                "В казне снова появились средства");
            if (debug) debug->record("server_economy",economyStart);
            const auto productionStart = Clock::now();
            botLedger.advance(int(country),hours);
            const auto stocksBeforeProduction = stocks;
            const auto ratios = hoi5::runProduction(production[country], stocks, hours, [&](auto key, double amount) {
                botLedger.record(int(country),hoi5::FlowKind::output,key,amount);
                stocks[key] += std::min(amount, hoi5::freeStorage(capacities[country], stocks, key));
            });
            const double fraction = hours/720.;
            for (int stage = 0; stage < hoi5::productionStages; ++stage)
                for (const auto& [key,amount] : production[country][stage].inputs) {
                    const double used = stage == hoi5::upkeep
                        ? std::min(hoi5::value(stocksBeforeProduction,key),amount*fraction)
                        : amount*fraction*ratios[stage];
                    botLedger.record(int(country),hoi5::FlowKind::consumption,key,used);
                }
            if (debug) debug->record("server_production",productionStart);
            constexpr std::array<std::string_view,hoi5::productionStages> shortageKeys{
                "production_shortage:raw","production_shortage:semi_finished","",
                "production_shortage:finished","production_shortage:upkeep"};
            constexpr std::array labels{"сырьё","полуфабрикаты","","готовая продукция","содержание населения"};
            for (int stage = 0; stage < hoi5::productionStages; ++stage) {
                if (stage == hoi5::agriculture) continue;
                news.alert(diplomacy.day,int(country),countryNames[country],shortageKeys[stage],ratios[stage] < .5,
                    "Производство ограничено нехваткой ресурсов",std::string(countryNames[country])+": этап «"+
                    labels[stage]+"» обеспечен ресурсами менее чем наполовину. Проверьте ресурсы и торговлю.",
                    "Снабжение производства сырьём восстановлено");
            }
        }
        const auto constructionStart = Clock::now();
        const bool built = construction.advance(tiles,profiles,stockpiles,hours,
            [&](int country,int index,hoi5::Building building,bool repair) {
                auto& tile = tiles[index];
                const auto spec = std::ranges::find(hoi5::constructionSpecs,building,&hoi5::ConstructionSpec::building);
                if (spec != std::end(hoi5::constructionSpecs))
                    news.batchNotice(diplomacy.day,country,"construction_complete",
                        std::string(repair ? "Ремонт завершён: " : "Строительство завершено: ")+std::string(spec->label),
                        "Работы на участке ("+std::to_string(index%size)+", "+std::to_string(index/size)+") завершены.");
                if (repair) return;
                if (building == hoi5::industry && tile.industries.empty()) {
                    double score = 0;
                    tile.industries = hoi5::industryAllocation(tiles,size,index,score);
                }
                if (building == hoi5::airbase)
                    air.registerConstructedBase(country,index,tile.buildings[hoi5::airbase]);
            },[&](int index) { return battles.contains(index); },debug);
        reportConstructionAlerts(hours);
        if (debug) debug->record("server_construction",constructionStart);
        const auto populationStart = Clock::now();
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
        }
        if (debug) debug->record("server_population",populationStart);
        const auto refreshBuildings = [&] {
            hoi5::DebugMeasure timing(debug,"server_building_refresh");
            bordersChanged = true;
            hoi5::recalculateSupply(std::span(tiles),size,capitals);
            rebuildEconomy();
        };
        if ((built || populationTick) && !capitals.empty()) refreshBuildings();
        const auto divisionsStart = Clock::now();
        advanceManualFrontTimers(hours);
        bool ownershipChanged = updateDivisions(hours);
        if (debug) debug->record("server_divisions",divisionsStart);
        {
            hoi5::DebugMeasure timing(debug,"server_training");
            updateTraining(hours);
        }
        bool battleDamage = false;
        const auto battlesStart = Clock::now();
        ownershipChanged |= advanceBattles(hours,battleDamage,debug);
        if (debug) debug->record("server_ground_battles",battlesStart);
        const auto helipadStart = Clock::now();
        const bool helipadBuilt = updateFieldHelipads(hours);
        if (debug) debug->record("server_field_helipads",helipadStart);
        const auto defenseStart = Clock::now();
        air.advanceDefenseReplacements(tiles,capitals,hours,[&](int tile) { return battles.contains(tile); },
            [&](int owner) { return botForwardDefenseSites(owner); },
            [&](int tile,int type) {
                diplomacy.record("ПВО восстановлено: "+std::string(hoi5::defenseClasses[type].key)+" ("+
                    std::to_string(tile%size)+", "+std::to_string(tile/size)+")",tiles[tile].owner);
                news.batchNotice(diplomacy.day,tiles[tile].owner,"air_defense_completed","ПВО восстановлено",
                    "Новая установка "+std::string(hoi5::defenseClasses[type].key)+" развёрнута на ("+
                    std::to_string(tile%size)+", "+std::to_string(tile/size)+").");
            });
        air.replenishDefenseAmmo(tiles,stockpiles,hours);
        advanceAirDefense(hours);
        if (debug) debug->record("server_air_defense",defenseStart);
        const bool airDamage = updateAir(hours,debug);
        {
            hoi5::DebugMeasure timing(debug,"server_army_plans");
            refreshArmyFrontsAfterCapture();
            updateArmyFronts(hours);
        }
        if (ownershipChanged && !profiles.empty()) {
            for (auto& profile : profiles) profile.population = 0;
            for (const auto& tile : tiles)
                if (tile.owner >= 0) profiles[tile.owner].population += tile.population;
        }
        if ((airDamage || battleDamage || helipadBuilt || ownershipChanged) && !capitals.empty()) refreshBuildings();
        updateBots(hours,debug);
        news.flushNotices();
    }

    void updateVisualMotion(double dt) {
        if (dt <= 0.) return;
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
    world.news = hoi5::News(seed);
    world.size = size;
    world.difficulty = difficulty;
    world.combatRandom.seed(seed);
    world.groundCombatRandom.seed(seed);
    std::tie(world.countryNames,world.rulers) = hoi5::countryIdentities(seed);
    world.tiles.resize(size * size);
    hoi5::WorldGenerator generator(size, seed);
    for (int r = 0; r < size; ++r) for (int q = 0; q < size; ++q) {
        const auto terrain = generator.generate(q, r);
        auto& tile = world.tiles[r * size + q];
        tile.natural = terrain;
        tile.owner = -1;
        tile.water = terrain.water > .5;
        tile.movementCost = hoi5::terrainMovementCost(terrain);
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

void drawUnitRoute(sf::RenderTarget& target,const World& world,const auto& cells,sf::Vector2f origin,
                   double progress,const auto& colors,sf::Vector2f offset = {}) {
    if (cells.empty()) return;
    const auto point = [&](int tile) { return center(tile%world.size,tile/world.size)+offset; };
    sf::VertexArray strokes(sf::PrimitiveType::Triangles);
    const auto line = [&](sf::Vector2f from,sf::Vector2f to,sf::Color color,float width) {
        const auto delta = to-from;
        const float length = delta.length();
        if (length <= 0) return;
        const sf::Vector2f side = sf::Vector2f{-delta.y,delta.x}*(width*.5f/length);
        for (const auto vertex : {from-side,from+side,to+side,from-side,to+side,to-side})
            strokes.append({vertex,color});
    };

    auto previous = origin;
    sf::Vector2f arrowOrigin = origin;
    for (int tile : cells) {
        const auto next = point(tile);
        line(previous,next,colors(tile)[0],5);
        arrowOrigin = previous;
        previous = next;
    }
    const auto first = point(cells.front());
    const auto fraction = float(std::clamp(progress,0.,1.));
    line(origin,origin+(first-origin)*fraction,colors(cells.front())[1],6);
    const auto heading = previous-arrowOrigin;
    if (heading.lengthSquared() > 0) {
        for (float offset : {2.55f,-2.55f}) {
            const float angle = std::atan2(heading.y,heading.x)+offset;
            line(previous,previous+sf::Vector2f{std::cos(angle),std::sin(angle)}*16.f,
                colors(cells.back())[1],5);
        }
    }
    target.draw(strokes);
}

void drawDivisionRoute(sf::RenderTarget& target,const World& world,const Division& division) {
    std::vector<int> cells;
    if (division.battle >= 0 && division.attackRoute) {
        cells.push_back(division.battle);
        cells.insert(cells.end(),division.postBattleRoute.begin(),division.postBattleRoute.end());
    } else cells.assign(division.route.begin(),division.route.end());
    constexpr std::array<std::array<sf::Color,2>,3> routeColors{{
        {{{120,94,28,210},{238,196,74,235}}},
        {{{132,42,42,210},{238,92,82,235}}},
        {{{36,76,132,210},{92,164,244,235}}}
    }};
    const auto colors = [&](int tile) {
        if (division.retreating) return routeColors[2];
        const int owner = world.tiles[tile].owner;
        return routeColors[owner >= 0 && owner != division.owner ? 1 : 0];
    };
    drawUnitRoute(target,world,cells,unitPosition(world,division),division.progress,colors);
}

struct DivisionCounter {
    int first;
    int count;
    sf::FloatRect bounds;
    float organization, strength;
    bool selected;
    std::vector<int> members;
};

std::vector<DivisionCounter> divisionCounters(const World& world,const sf::RenderWindow& window,
                                              const sf::View& camera,float zoom,const std::set<int>& selected = {}) {
    struct Group {
        std::vector<int> members;
        double organization{},maxOrganization{},strength{},maxStrength{};
        bool selected{};
    };
    const bool overview = zoom < .45f;
    std::vector<Group> groups;
    std::vector<int> eligible;
    const auto half = camera.getSize()*.5f+sf::Vector2f{spacing,spacing};
    const sf::FloatRect visible(camera.getCenter()-half,half*2.f);
    for (int i = 0; i < int(world.divisions.size()); ++i) {
        const auto& unit = world.divisions[i];
        if (unit.combat.strength > 0 && visible.contains(unitPosition(world,unit))) eligible.push_back(i);
    }
    std::ranges::sort(eligible,[&](int a,int b) {
        const auto& first = world.divisions[a];
        const auto& second = world.divisions[b];
        return std::tie(first.owner,first.r,first.q,a) < std::tie(second.owner,second.r,second.q,b);
    });
    const int neighborRadius = zoom <= .10f ? 12 : zoom <= .25f ? 8 : zoom <= .40f ? 5 : 0;
    std::map<std::pair<int,std::string_view>,std::vector<int>> byIcon;
    if (overview) for (int index : eligible) {
        const auto& unit = world.divisions[index];
        byIcon[{unit.owner,unit.icon}].push_back(index);
    }
    std::vector<bool> assigned(world.divisions.size());
    for (int seed : eligible) {
        if (assigned[seed]) continue;
        auto& group = groups.emplace_back();
        const auto add = [&](int index) {
            const auto& unit = world.divisions[index];
            assigned[index] = true;
            group.members.push_back(index);
            group.organization += unit.organization;
            group.maxOrganization += std::max(1.,unit.maxOrganization);
            group.strength += unit.combat.strength;
            group.maxStrength += std::max(1.,unit.design->combat.strength);
            group.selected |= selected.contains(index);
        };
        const auto& origin = world.divisions[seed];
        if (overview) {
            for (int index : byIcon.at({origin.owner,origin.icon})) {
                if (assigned[index]) continue;
                const auto& unit = world.divisions[index];
                if (hoi5::airHexDistance(origin.r*world.size+origin.q,unit.r*world.size+unit.q,world.size)
                    <= neighborRadius) add(index);
            }
        } else {
            for (int index : eligible) {
                if (assigned[index]) continue;
                const auto& unit = world.divisions[index];
                if (unit.owner == origin.owner && unit.q == origin.q && unit.r == origin.r &&
                    unit.icon == origin.icon) add(index);
            }
        }
    }
    const float iconSize = 30.f/std::clamp(std::pow(zoom,.25f),.35f,1.f);
    const sf::Vector2f size = overview ? sf::Vector2f{54,34} :
        sf::Vector2f{std::max(50.f,iconSize*1.62f),std::max(32.f,iconSize*1.02f)}*zoom;
    std::vector<DivisionCounter> counters;
    struct TileStack { int count{}, next{}; };
    std::map<std::pair<int,int>,TileStack> tileStacks;
    if (!overview) for (const auto& group : groups) {
        const auto& unit = world.divisions[group.members.front()];
        ++tileStacks[{unit.r,unit.q}].count;
    }
    for (auto& group : groups) {
        const auto& unit = world.divisions[group.members.front()];
        auto position = unitPosition(world,unit);
        auto counterSize = size;
        if (overview) {
            position = {};
            for (int index : group.members) position += unitPosition(world,world.divisions[index]);
            position /= float(group.members.size());
            position += {34,22};
        }
        else {
            auto& stack = tileStacks.at({unit.r,unit.q});
            const int columns = int(std::ceil(std::sqrt(stack.count)));
            const int rows = (stack.count+columns-1)/columns;
            const int slot = stack.next++;
            const int row = slot/columns;
            const int rowCount = std::min(columns,stack.count-row*columns);
            const auto pitch = size/zoom+sf::Vector2f{5,5};
            const float scale = std::min({1.f,144.f/(columns*pitch.x),90.f/(rows*pitch.y)});
            position += sf::Vector2f{(slot%columns-(rowCount-1)*.5f)*pitch.x,
                (row-(rows-1)*.5f)*pitch.y}*scale;
            counterSize *= scale;
        }
        auto pixel = sf::Vector2f(window.mapCoordsToPixel(position,camera));
        counters.push_back({group.members.front(),int(group.members.size()),{pixel-counterSize*.5f,counterSize},
            float(std::clamp(group.organization/group.maxOrganization,0.,1.)),
            float(std::clamp(group.strength/group.maxStrength,0.,1.)),group.selected,std::move(group.members)});
    }
    if (overview) {
        std::ranges::stable_sort(counters,[](const auto& a,const auto& b) {
            const auto first = a.bounds.getCenter(), second = b.bounds.getCenter();
            return std::pair{-first.y,first.x} < std::pair{-second.y,second.x};
        });
        struct Stack { sf::Vector2f center; std::vector<DivisionCounter*> rows; };
        std::vector<Stack> stacks;
        for (auto& counter : counters) {
            const auto point = counter.bounds.getCenter();
            const auto stack = std::ranges::find_if(stacks,[&](const auto& candidate) {
                return std::abs(point.x-candidate.center.x) < 54 && std::abs(point.y-candidate.center.y) < 34;
            });
            if (stack == stacks.end()) stacks.push_back({point,{&counter}});
            else stack->rows.push_back(&counter);
        }
        struct Placed { float x,bottom,top; };
        std::vector<Placed> placed;
        for (auto& stack : stacks) {
            std::ranges::stable_sort(stack.rows,[&](const auto* a,const auto* b) {
                const auto& first = world.divisions[a->first].icon;
                const auto& second = world.divisions[b->first].icon;
                return std::pair{first != "infantry",first} < std::pair{second != "infantry",second};
            });
            const float height = 36.f*(stack.rows.size()-1);
            float bottom = -stack.center.y-height*.5f;
            for (const auto& other : placed)
                if (std::abs(stack.center.x-other.x) < 56 && bottom < other.top+36 &&
                    bottom+height > other.bottom-36) bottom = other.top+36;
            for (std::size_t i = 0; i < stack.rows.size(); ++i)
                stack.rows[i]->bounds.position = {stack.center.x-27,-(bottom+36.f*i)-17};
            placed.push_back({stack.center.x,bottom,bottom+height});
            std::ranges::stable_sort(placed,{},&Placed::bottom);
        }
    }
    return counters;
}

std::string wingAreaSummary(const hoi5::AirWing& wing,int mapSize) {
    if (wing.operationArea.size() > 1)
        return "район "+std::to_string(wing.operationArea.size())+" кл.";
    const int tile = wing.operationArea.empty() ? wing.target : wing.operationArea.front();
    if (tile < 0) return "район нет";
    return "район "+std::to_string(tile%mapSize)+":"+std::to_string(tile/mapSize);
}

std::string wingCompositionLabel(const hoi5::AirWing& wing) {
    int primary = -1, count = 0;
    for (const auto& [type,quantity] : wing.composition) {
        if (quantity <= 0) continue;
        ++count;
        if (primary < 0 || quantity > wing.typeCount(primary) ||
            (quantity == wing.typeCount(primary) && hoi5::aircraftNames[type] < hoi5::aircraftNames[primary]))
            primary = type;
    }
    if (primary < 0) return wing.count > 0 ? std::string(hoi5::aircraftNames[wing.type]) : "-";
    auto name = std::string(hoi5::aircraftNames[primary]);
    if (count > 1) name += "+"+std::to_string(count-1);
    return name;
}

constexpr std::array wingMissionNames{"CAS","Перехват","Патруль","Превосходство","Удар"};
constexpr int wingMissionMenuHeight = 38+27*int(wingMissionNames.size());

constexpr std::array wingRiskOptions{
    std::pair{hoi5::AirRisk::cautious,"Осторожно"},
    std::pair{hoi5::AirRisk::normal,"Нормально"},
    std::pair{hoi5::AirRisk::aggressive,"Агрессивно"}
};
constexpr int wingRiskMenuHeight = 38+27*int(wingRiskOptions.size());

bool* wingMission(hoi5::AirWing& wing,int index) {
    if (index == 0 || index == 4) {
        const bool strategic = index == 4;
        return wing.missionAllowed(strategic) ? &wing.enabledMissions[strategic] : nullptr;
    }
    constexpr std::array airMissions{&hoi5::AirWing::intercept,&hoi5::AirWing::patrol,&hoi5::AirWing::airSuperiority};
    return wing.missionType(2) >= 0 ? &(wing.*airMissions[index-1]) : nullptr;
}

void drawDefenseRing(sf::RenderTarget& target,sf::Vector2f position,float radius,sf::Color color,float width) {
    sf::CircleShape ring(radius,64);
    ring.setOrigin({radius,radius});
    ring.setPosition(position);
    ring.setFillColor(sf::Color::Transparent);
    ring.setOutlineColor(color);
    ring.setOutlineThickness(width);
    target.draw(ring);
}

void drawWingAreaOverlay(sf::RenderTarget& target,const World& world,const sf::VertexArray& map,
    const std::set<int>& selectedWings,bool editing) {
    if (selectedWings.empty()) return;
    std::set<int> area;
    int ringIndex = 0;
    for (const int index : selectedWings) {
        const auto& wing = world.air.wings[index];
        if (ringIndex < 6 && wing.base >= 0) {
            const float range = float(world.airWingDisplayRange(wing))*spacing;
            if (range > 0) {
                const auto position = center(wing.base%world.size,wing.base/world.size);
                const int alpha = std::max(44,92-ringIndex*10);
                drawDefenseRing(target,position,range,{255,44,42,std::uint8_t(alpha)},6);
                drawDefenseRing(target,position,range+5,{255,122,118,std::uint8_t(std::max(40,alpha/2))},2);
            }
            ++ringIndex;
        }
        area.insert(wing.operationArea.begin(),wing.operationArea.end());
        if (wing.operationArea.empty() && wing.target >= 0) area.insert(wing.target);
    }

    if (editing) {
        const auto& view = target.getView();
        const auto half = view.getSize()*.5f+sf::Vector2f{radius,radius};
        const sf::FloatRect visible(view.getCenter()-half,half*2.f);
        sf::VertexArray unavailable(sf::PrimitiveType::Triangles);
        for (int tile = 0; tile < int(world.tiles.size()); ++tile) {
            if (!visible.contains(center(tile%world.size,tile/world.size))) continue;
            if (std::ranges::all_of(selectedWings,[&](int index) {
                return world.airWingCanReach(world.air.wings[index],tile);
            })) continue;
            for (int vertex = 0; vertex < 18; ++vertex)
                unavailable.append({map[tile*18+vertex].position,{210,48,52,72}});
        }
        target.draw(unavailable);
    }
    sf::ConvexShape hex(6);
    hex.setFillColor({70,168,230,62});
    hex.setOutlineColor({126,218,255,178});
    hex.setOutlineThickness(-2);
    for (const int tile : area) {
        if (tile < 0 || tile >= int(world.tiles.size())) continue;
        for (int corner = 0; corner < 6; ++corner)
            hex.setPoint(corner,map[tile*18+corner*3+1].position);
        target.draw(hex);
    }
}

void drawDefenseRanges(sf::RenderTarget& target,const hoi5::AirDefense& unit,sf::Vector2f position) {
    const auto& type = hoi5::defenseClasses[unit.type];
    const bool friendly = unit.owner == 0;
    if (type.fireRange > 0) {
        const float range = type.fireRange*spacing;
        auto color = friendly ? sf::Color(120,230,150,150) : sf::Color(248,132,96,150);
        drawDefenseRing(target,position,range,color,4);
        color.a = 85;
        drawDefenseRing(target,position,range+3,color,2);
    }
    if (type.radarActive && type.radarRange > 0)
        drawDefenseRing(target,position,type.radarRange*spacing,
            friendly ? sf::Color(122,196,248,112) : sf::Color(238,150,238,112),3);
}

constexpr sf::Vector2f defenseIconOffset{-17,12};

sf::Vector2f defenseIconPosition(const World& world,const hoi5::AirDefense& unit) {
    const auto position = center(unit.tile%world.size,unit.tile/world.size);
    if (unit.route.empty()) return position+defenseIconOffset;
    const int next = unit.route.front();
    return position+(center(next%world.size,next/world.size)-position)*
        float(std::clamp(unit.visualProgress,0.,1.))+defenseIconOffset;
}

void drawDefenseIcon(sf::RenderTarget& target,const hoi5::AirDefense& unit,sf::Vector2f position) {
    constexpr sf::Color colors[]{{180,224,128},{124,200,220},{236,204,112},{238,150,112},{178,164,238}};
    const auto color = colors[unit.type];
    sf::CircleShape background(8,24);
    background.setOrigin({8,8});
    background.setPosition(position);
    background.setFillColor({18,24,31,225});
    target.draw(background);
    drawDefenseRing(target,position,9,color,2);
    const auto line = [&](sf::Vector2f from,sf::Vector2f to) {
        const auto delta = to-from;
        sf::RectangleShape stroke({delta.length(),2});
        stroke.setOrigin({0,1});
        stroke.setPosition(position+from);
        stroke.setRotation(delta.angle());
        stroke.setFillColor(color);
        target.draw(stroke);
    };
    if (hoi5::defenseClasses[unit.type].key == "radar_unit") {
        line({0,0},{7,-4});
        drawDefenseRing(target,position,13,{color.r,color.g,color.b,130},1);
    } else {
        line({0,-6},{-6,5});
        line({-6,5},{6,5});
        line({6,5},{0,-6});
    }
}

sf::Color supplyColor(const Tile& tile,bool highlighted = false) {
    const auto blend = [](sf::Color a, sf::Color b, double t) {
        return sf::Color(a.r * (1-t) + b.r * t, a.g * (1-t) + b.g * t, a.b * (1-t) + b.b * t);
    };
    if (tile.owner < 0 || tile.water || tile.natural.water > .55) return blend(tile.terrain, {12,16,22}, .62);
    const auto score = std::clamp(tile.supply,0.,1.);
    const auto target = score < .25 ? sf::Color(154,48,44) : score < .50 ? sf::Color(190,142,54)
        : score < .75 ? sf::Color(146,174,74) : sf::Color(62,156,88);
    const auto base = blend({28,34,42}, target, .36 + score * .45);
    return highlighted ? blend(base,{255,255,190},.18) : base;
}

enum class MapLayer { terrain, political, height, climate, resources, supply, weather };
constexpr std::array mapLayerLabels{"Местность", "Политическая", "Высотная", "Климат", "Ресурсы", "Снабжение", "Погодная"};
enum class PoliticalMapFilter { countries, alliances, relations };
constexpr std::array politicalMapLabels{"Страны","Союзы","Отношения к нам"};
constexpr std::array politicalMapSwatches{sf::Color{92,157,211},sf::Color{132,105,187},sf::Color{222,164,92}};

sf::Color blendMapColors(sf::Color a,sf::Color b,double amount);

struct ResourceMapGroup {
    std::string_view label;
    std::span<const std::string_view> resources;
    sf::Color color;
    double scale;
};

constexpr std::string_view fuelResources[]{"coal","oil","natural_gas","peat","uranium"};
constexpr std::string_view metalResources[]{"iron_ore","copper_ore","bauxite","lead","zinc","nickel",
    "gold","silver","rare_earth_metals","alloying_additives"};
constexpr std::string_view chemicalResources[]{"sulfur","potash","phosphorite","apatite","rubber"};
constexpr std::string_view rareResources[]{"gold","silver","rare_earth_metals","uranium","graphite","mica","quartz"};
constexpr ResourceMapGroup resourceMapGroups[]{
    {"Топливо",fuelResources,{222,92,54},1200000},
    {"Сырьевые металлы",metalResources,{214,176,82},350000},
    {"Химсырье",chemicalResources,{112,184,132},250000},
    {"Редкие минералы",rareResources,{156,124,218},80000}
};

sf::FloatRect resourceGroupRect(sf::Vector2u size,int index = -1,float progress = 1.f) {
    const float top = index < 0 ? float(size.y)-62 : float(size.y)-106-40*index+18*(1-progress);
    return {{float(size.x)-260,top},{190,index < 0 ? 44.f : 34.f}};
}

constexpr std::array constructionAirColors{sf::Color{127,199,255,150},sf::Color{94,224,187,150},
    sf::Color{247,163,105,150},sf::Color{255,214,111,150},
    sf::Color{178,244,125,150},sf::Color{217,148,252,150}};

sf::Color resourceGroupColor(const Tile& tile,const ResourceMapGroup& group,bool highlighted = false) {
    double amount = 0;
    for (const auto& deposit : tile.deposits)
        if (std::ranges::find(group.resources,deposit.resource) != group.resources.end()) amount += deposit.mass;
    if (amount <= 0) return blendMapColors(tile.terrain,{20,22,26},.72);
    const double intensity = std::min(1.,std::log10(amount+1)/std::log10(group.scale+1));
    const auto base = blendMapColors({38,42,48},group.color,.28+intensity*.62);
    return highlighted ? blendMapColors(base,{255,255,190},.18) : base;
}

sf::Color mapLayerColor(const World& world,int index,MapLayer layer,int resourceGroup,
                       PoliticalMapFilter politicalFilter,std::span<const sf::Color> allianceColors) {
    const auto& tile = world.tiles[index];
    const auto& terrain = tile.natural;
    const auto blend = [](sf::Color a,sf::Color b,double amount) {
        return blendMapColors(a,b,std::clamp(amount,0.,1.));
    };
    switch (layer) {
    case MapLayer::political: {
        if (tile.owner < 0) return tile.water ? sf::Color{51,77,106} : sf::Color{112,118,112};
        if (politicalFilter == PoliticalMapFilter::relations) {
            if (tile.owner == 0) return {80,145,224};
            const auto& relation = world.diplomacy.relation(0,tile.owner);
            if (relation.war) return {193,63,60};
            if (world.diplomacy.allied(0,tile.owner)) return {87,162,105};
            if (world.diplomacy.day < relation.truceUntil) return {199,157,64};
            return {139,151,163};
        }
        if (tile.owner < int(allianceColors.size())) return allianceColors[tile.owner];
        return tile.border;
    }
    case MapLayer::height: {
        constexpr double waterLevel = .25;
        if (terrain.elevation < waterLevel)
            return blend({20,55,130},{68,155,220},terrain.elevation/waterLevel);
        const double value = std::clamp((terrain.elevation-waterLevel)/(1-waterLevel),0.,1.);
        sf::Color color;
        if (value < .34) color = blend({72,158,72},{180,204,112},value/.34);
        else if (value < .68) color = blend({180,204,112},{132,118,96},(value-.34)/.34);
        else color = blend({132,118,96},{238,242,238},(value-.68)/.32);
        return blend(color,sf::Color::White,terrain.ridge*.18);
    }
    case MapLayer::climate: {
        const sf::Color mild(86,196,118);
        auto color = terrain.temperature < .5 ? blend({64,130,220},mild,terrain.temperature/.5)
            : blend(mild,{230,174,76},(terrain.temperature-.5)/.5);
        color = blend(color,terrain.moisture > .5 ? sf::Color(45,105,215) : sf::Color(220,200,115),
            std::abs(terrain.moisture-.5)*.55);
        return terrain.water > .5 ? blend(color,{50,135,220},.55) : color;
    }
    case MapLayer::resources:
        return resourceGroupColor(tile,resourceMapGroups[resourceGroup]);
    case MapLayer::supply:
        return supplyColor(tile);
    default:
        return tile.terrain;
    }
}

sf::FloatRect mapLayerOption(sf::Vector2u size,int index,float progress) {
    const float gap = index == int(mapLayerLabels.size()) ? 10.f : 0.f;
    return {{float(size.x)-208,float(size.y)-106-40*index-gap+18*(1-progress)},{190,34}};
}

sf::VertexArray makeMap(const World& world, MapLayer layer = MapLayer::terrain,int resourceGroup = 0,
                        PoliticalMapFilter politicalFilter = PoliticalMapFilter::alliances) {
    sf::VertexArray geometry(sf::PrimitiveType::Triangles);
    std::vector<sf::Color> allianceColors;
    if (layer == MapLayer::political && politicalFilter == PoliticalMapFilter::alliances) {
        std::vector<int> allianceLeaders(world.diplomacy.countries.size());
        std::iota(allianceLeaders.begin(),allianceLeaders.end(),0);
        for (const auto& [pair,relation] : world.diplomacy.relations) {
            const auto [a,b] = pair;
            if (!world.diplomacy.allied(a,b)) continue;
            const int first = allianceLeaders[a], second = allianceLeaders[b];
            std::ranges::replace(allianceLeaders,std::max(first,second),std::min(first,second));
        }
        std::vector<std::optional<sf::Color>> countries(allianceLeaders.size()), coalitions(allianceLeaders.size());
        for (const auto& tile : world.tiles)
            if (tile.owner >= 0 && tile.owner < int(countries.size()) && !countries[tile.owner])
                countries[tile.owner] = tile.border;
        for (std::size_t i = 0; i < countries.size(); ++i)
            if (countries[i] && !coalitions[allianceLeaders[i]]) coalitions[allianceLeaders[i]] = countries[i];
        for (int leader : allianceLeaders) allianceColors.push_back(coalitions[leader].value_or(sf::Color::Transparent));
    }
    for (int r = 0; r < world.size; ++r) {
        for (int q = 0; q < world.size; ++q) {
            const auto position = center(q, r);
            const auto color = mapLayerColor(world,r*world.size+q,layer,resourceGroup,politicalFilter,allianceColors);
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
    if (category == 0) return raw;
    return {};
}

bool isRawMapResource(std::string_view key) {
    const auto semi = resourceCategoryKeys(1), finished = resourceCategoryKeys(2);
    return std::ranges::find(semi,key) == semi.end() && std::ranges::find(finished,key) == finished.end();
}


std::optional<double> resourceDurationMonths(std::optional<double> stock,double output,double input) {
    const double deficit = input-output;
    if (!stock || deficit <= 0) return std::nullopt;
    return std::max(0.,*stock)/deficit;
}

int resourceShortageLevel(double stock,double deficit) {
    const auto months = resourceDurationMonths(stock,0.,deficit);
    if (!months) return 0;
    return *months < 1 ? 2 : *months < 3 ? 1 : 0;
}

int storageProblemLevel(double used,double capacity) {
    if (capacity <= 0) return used > 0 ? 2 : 0;
    const double fullness = used/capacity;
    return fullness >= 1 ? 2 : fullness >= .88 ? 1 : 0;
}

sf::Color resourceDurationColor(std::optional<double> months) {
    if (!months) return {170,184,198};
    if (*months < 1) return {238,104,94};
    if (*months < 3) return {238,198,90};
    if (*months < 6) return {176,214,92};
    return {112,214,132};
}

std::string formatResourceDuration(std::optional<double> duration) {
    if (!duration) return "--";
    const double months = *duration;
    if (months <= 0) return "0 дн.";
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

std::string formatBuildDuration(std::optional<double> months) {
    if (!months) return "нет скорости";
    if (*months <= 0) return "0 ч.";
    if (*months >= .1) return formatResourceDuration(months);
    const int hours = int(std::ceil(*months*720));
    if (hours >= 72) return formatResourceDuration(months);
    if (hours < 24) return std::to_string(hours)+" ч.";
    const auto days = std::to_string(hours/24)+" дн.";
    return hours%24 ? days+" "+std::to_string(hours%24)+" ч." : days;
}

std::string resourceDurationLabel(double stock,double output,double input) {
    return formatResourceDuration(resourceDurationMonths(stock,output,input));
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
           sf::Vector2f position, unsigned size = 13,sf::Color color = {224,234,244}) {
    sf::Text text(font, sf::String::fromUtf8(value.begin(), value.end()), size);
    text.setPosition({std::round(position.x),std::round(position.y)});
    text.setFillColor(color);
    window.draw(text);
}

void battleLabel(sf::RenderWindow& window,const sf::Font& font,const std::string& value,
                 sf::Vector2f anchor,unsigned size,sf::Color color = sf::Color::White,float alignment = 0.f) {
    sf::Text text(font,sf::String::fromUtf8(value.begin(),value.end()),size);
    const auto bounds = text.getLocalBounds();
    text.setOrigin(bounds.position+sf::Vector2f(bounds.size.x*alignment,bounds.size.y*.5f));
    text.setPosition({std::round(anchor.x),std::round(anchor.y)});
    text.setFillColor(color);
    window.draw(text);
}

void fittedBattleLabel(sf::RenderWindow& window,const sf::Font& font,const std::string& value,
                       sf::Vector2f anchor,unsigned size,float maxWidth,sf::Color color = sf::Color::White) {
    sf::Text text(font,sf::String::fromUtf8(value.begin(),value.end()),size);
    const auto bounds = text.getLocalBounds();
    text.setOrigin(bounds.position+sf::Vector2f{0,bounds.size.y*.5f});
    text.setPosition({std::round(anchor.x),std::round(anchor.y)});
    text.setFillColor(color);
    if (bounds.size.x > maxWidth) text.setScale({maxWidth/bounds.size.x,1.f});
    window.draw(text);
}

std::vector<std::string> countryTextLines(const std::string& caption,int maxChars) {
    std::istringstream words(caption);
    std::vector<std::string> lines;
    std::string line, word;
    while (words >> word) {
        const auto joined = line.empty() ? word : line+" "+word;
        if (!line.empty() && sf::String::fromUtf8(joined.begin(),joined.end()).getSize() > std::size_t(maxChars)) {
            lines.push_back(std::move(line));
            line = word;
        } else line = joined;
    }
    lines.push_back(std::move(line));
    return lines;
}

std::string formatPopulation(double value) {
    std::ostringstream out;
    out << std::fixed;
    if (value >= 1000000) out << std::setprecision(1) << value/1000000 << 'M';
    else if (value >= 1000) out << std::setprecision(1) << value/1000 << 'K';
    else out << std::setprecision(0) << value;
    return out.str();
}

void drawBudgetSummary(sf::RenderWindow& window,const sf::Font& font,const sf::FloatRect& anchor,
    double budget,const hoi5::TreasuryFlows& flows,double trade) {
    constexpr sf::Color income(190,226,174), expense(236,168,154), detail(206,178,168);
    const auto cost = [](double value) { return "-"+formatMoney(value); };
    struct Row { std::string_view name; std::string value; sf::Color color = sf::Color::White; unsigned points = 14; };
    const double balance = flows.balance()+trade;
    const Row rows[]{
        {"Бюджет",formatMoney(budget)},
        {"Месячный баланс",formatMoneyDelta(balance)+"/мес",balance >= 0 ? sf::Color(174,224,158) : sf::Color(236,148,132)},
        {}, {"Доходы:",{}},
        {"Налоги населения",formatMoneyDelta(flows.population),income,13},
        {"Компании",formatMoneyDelta(flows.companies),income,13},
        {"Возврат кредитов (прогноз)",formatMoneyDelta(flows.loanRepayments),income,13},
        {"Торговля",formatMoneyDelta(trade),trade >= 0 ? income : expense,13},
        {}, {"Расходы:",{}},
        {"Армия",cost(flows.army),expense,13},
        {"Правительство",cost(flows.government),expense,13},
        {"Соц. обеспечение",cost(flows.social),expense,13},
        {"  Пенсии",cost(flows.pensions),detail,12},
        {"  Дети/школы",cost(flows.children),detail,12},
        {"  Инвалиды",cost(flows.disability),detail,12},
        {"  Соцслужбы",cost(flows.localServices),detail,12},
        {"Инфраструктура",cost(flows.infrastructure),expense,13},
        {"Программы поддержки",cost(flows.politicalPrograms),expense,13},
        {"Платежи по кредитам",cost(flows.debtService),expense,13}
    };
    float width = 300, height = 28;
    for (const auto& row : rows) {
        height += row.name.empty() ? 8 : 20;
        if (row.name.empty()) continue;
        const auto name = sf::String::fromUtf8(row.name.begin(),row.name.end());
        const auto value = sf::String::fromUtf8(row.value.begin(),row.value.end());
        const float textWidth = row.value.empty() ? name.getSize()*row.points*.58f
            : name.getSize()*row.points*.52f+value.getSize()*row.points*.58f+46;
        width = std::max(width,std::min(480.f,textWidth+34));
    }
    const float x = std::max(12.f,std::min(anchor.position.x,float(window.getSize().x)-width-12));
    const float top = anchor.position.y+anchor.size.y+8;
    box(window,{x,top},{width,height},{18,24,31,247},{140,160,184});
    float y = top+20;
    for (const auto& row : rows) {
        if (row.name.empty()) { y += 8; continue; }
        battleLabel(window,font,std::string(row.name),{x+14,y},row.points,row.color);
        if (!row.value.empty()) battleLabel(window,font,row.value,{x+width-14,y},row.points,row.color,1.f);
        y += 20;
    }
}

void drawPopulationSummary(sf::RenderWindow& window,const sf::Font& font,const sf::FloatRect& anchor,
    double population,double stability,double legitimacy,double warSupport) {
    population = std::max(0.,population);
    const double workingAge = population*.61;
    const double obligated = workingAge*.54;
    const double willingness = std::clamp(.04+warSupport*.62+stability*.13+legitimacy*.13,0.,.82);
    const auto percent = [](double value) { return std::to_string(int(std::nearbyint(value*100)))+"%"; };
    const std::array<std::pair<std::string_view,std::string>,19> rows{{
        {"Население",formatPopulation(population)}, {},
        {"Возраст:",{}}, {"Дети",formatPopulation(population*.23)},
        {"Рабочий возраст",formatPopulation(workingAge)}, {"Старики",formatPopulation(population*.16)}, {},
        {"Пол:",{}}, {"Мужчины",formatPopulation(population*.52)}, {"Женщины",formatPopulation(population*.48)}, {},
        {"Военный ресурс:",{}}, {"Военнообязанные",formatPopulation(obligated)},
        {"Добровольцы",formatPopulation(obligated*willingness)}, {"Готовность",percent(willingness)}, {},
        {"Стабильность",percent(stability)}, {"Легитимность",percent(legitimacy)}, {"Поддержка войны",percent(warSupport)}
    }};
    const float x = std::max(12.f,std::min(anchor.position.x,float(window.getSize().x)-392));
    const float top = anchor.position.y+anchor.size.y+8;
    box(window,{x,top},{380,359},{18,24,31,247},{140,160,184});
    float y = top+20;
    for (std::size_t i = 0; i < rows.size(); ++i) {
        const auto& [name,value] = rows[i];
        if (name.empty()) { y += 7; continue; }
        const auto color = i == 0 || value.empty() ? sf::Color::White : i == 13 || i == 14
            ? sf::Color(190,226,174) : sf::Color(220,230,240);
        const unsigned points = i == 0 || value.empty() ? 14 : 13;
        battleLabel(window,font,std::string(name),{x+14,y},points,color);
        if (!value.empty()) battleLabel(window,font,value,{x+366,y},points,color,1.f);
        y += 20;
    }
}

void drawFieldHelipad(sf::RenderWindow& target,sf::Vector2f position,sf::Color owner,
    std::optional<double> progress = std::nullopt) {
    position += {16,12};
    sf::CircleShape background(9,24);
    background.setOrigin({9,9});
    background.setPosition(position);
    background.setFillColor({18,24,31,220});
    target.draw(background);
    drawDefenseRing(target,position,10,owner,2);
    box(target,position+sf::Vector2f{-4,-5},{1,10},{230,238,246});
    box(target,position+sf::Vector2f{4,-5},{1,10},{230,238,246});
    box(target,position+sf::Vector2f{-4,0},{8,1},{230,238,246});
    if (progress)
        box(target,position+sf::Vector2f{-9,13},{float(18*std::clamp(*progress,0.,1.)),2},{170,224,144});
}

int main(int argc, char** argv) try {
    const auto directory = std::filesystem::absolute(argv[0]).parent_path();
    const auto& source = directory;
    World world(directory / "reference-map.txt");
    const std::string_view mode = argc > 1 ? argv[1] : "";
    if (mode == "--version") {
        std::cout << gameVersion << '\n';
        return 0;
    }
    if (mode == "--check-settings-write" && argc == 3)
        return hoi5::saveSettings(argv[2],{37,24,false,2}) ? 0 : 1;
    if (mode == "--check-settings-fallback" && argc == 4) {
        const hoi5::SettingsFiles files{argv[2],argv[3]};
        if (!hoi5::saveSettings(files,{37,24,false,2}) || files.latest() != files.portable) return 1;
        const auto loaded = hoi5::loadSettings(files.latest(),5);
        return loaded.soundVolume == 37 && loaded.musicVolume == 24 &&
            !loaded.fullscreen && loaded.resolution == 2 ? 0 : 1;
    }
    if (mode == "--check-construction-training") {
        if (resourceCategoryKeys(0).front() != "coal" || resourceCategoryKeys(1).back() != "copper_wire" ||
            resourceCategoryKeys(2).back() != "ships" || isRawMapResource("steel") ||
            resourceAmountLabel(1250) != "1.2K" || resourceAmountLabel(-1250) != "-1.2K" ||
            resourceAmountLabel(999) != "999" || resourceAmountLabel(1000) != "1.0K" ||
            resourceAmountLabel(-1000000) != "-1.0M" || resourceAmountLabel(-0.0) != "0" || resourceDurationLabel(20,10,110) != "6 дн." ||
            resourceDurationLabel(100,10,10) != "--") return 1;
        const hoi5::ConstructionProject speedProject{0,0,0.,.05,100.,0.,{{"steel",100.}}};
        const auto normalDelta = hoi5::Construction::progressDelta(speedProject,50.,1.);
        const auto battleDelta = hoi5::Construction::progressDelta(speedProject,
            50.*hoi5::Construction::speedMultiplier(true),1.);
        const auto normalNeeds = hoi5::Construction::projectNeeds(speedProject,normalDelta);
        const auto battleNeeds = hoi5::Construction::projectNeeds(speedProject,battleDelta);
        if (normalNeeds.at("steel") != 50. || std::abs(battleNeeds.at("steel")-11.) > 1e-12 ||
            hoi5::Construction::speedMultiplier(false) != 1. ||
            hoi5::Construction::remainingMonths(speedProject,50.) != 2. ||
            hoi5::Construction::remainingMonths(speedProject,0.).has_value()) return 1;
        std::vector<Tile> powerTiles(2);
        powerTiles[0].buildings[hoi5::industry] = {.5,.5};
        powerTiles[0].buildings[hoi5::city] = {.4,.5};
        powerTiles[0].buildings[hoi5::village] = {.2,1.};
        powerTiles[1].owner = 1;
        powerTiles[1].buildings[hoi5::industry] = {1.,1.};
        hoi5::StartingProfile powerProfile{};
        powerProfile.industryEfficiency = 1.2;
        powerProfile.cityBuildMultiplier = 1.5;
        powerProfile.buildTechBonus = 7.;
        if (std::abs(hoi5::Construction::buildPower(powerTiles,0,powerProfile)-82.) > 1e-10) return 1;
        powerProfile.buildTechBonus = -90.;
        if (hoi5::Construction::buildPower(powerTiles,0,powerProfile) != 0.) return 1;
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
        placement.tiles[1].water = false;
        placement.tiles[1].natural.water = .56;
        if (!blocked(6,0).empty() || blocked(-1,0) != "Неизвестное строение") return 1;
        placement.tiles[0].natural.water = .56;
        if (blocked(6,0) != "Порт только рядом с водой" || blocked(0,0) != "Нужна суша") return 1;
        placement.tiles[0].natural.water = 0.;
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
        hoi5::Construction cancellation;
        cancellation.queues.resize(1);
        if (!cancellation.enqueue(placement.tiles,2,0,0,0).empty() ||
            !cancellation.enqueue(placement.tiles,2,0,0,0).empty()) return 1;
        auto& pending = cancellation.queues[0];
        const double firstTarget = pending.front().target;
        pending.back().paid = true;
        if (cancellation.cancel(0,0,0) || pending.size() != 2) return 1;
        pending.back().paid = false;
        if (!cancellation.cancel(0,0,0) || pending.size() != 1 ||
            pending.front().target != firstTarget || cancellation.cancel(0,1,0)) return 1;
        hoi5::AirLayer airbaseCompletion;
        hoi5::BuildingCoverage airbaseCoverage{.05,1.};
        airbaseCompletion.registerConstructedBase(0,0,airbaseCoverage);
        if (airbaseCoverage.area != .10 || airbaseCompletion.bases.size() != 1 ||
            airbaseCompletion.bases.front().aircraftCapacity != 37) return 1;
        airbaseCoverage.area = .15;
        airbaseCompletion.registerConstructedBase(0,0,airbaseCoverage);
        if (airbaseCoverage.area != .15 || airbaseCompletion.bases.size() != 1) return 1;
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
        hoi5::BuildingCoverage damaged{.25,.4};
        if (hoi5::Construction::applyRepairProgress(damaged,queue.front(),0.,.001) || damaged.health != .4 ||
            !hoi5::Construction::applyRepairProgress(damaged,queue.front(),.1,.3) ||
            std::abs(damaged.health-.45) > 1e-12) return 1;
        std::vector<hoi5::StartingProfile> funding(1);
        std::vector<hoi5::Stockpile> materials(1);
        const auto runRepair = [&](int hours) {
            return repairs.advance(sites,funding,materials,hours,[](int,int,hoi5::Building,bool) {},
                [](int) { return false; });
        };
        using Status = hoi5::ConstructionStatus;
        if (runRepair(720) || queue.front().status != Status::waitingMoney ||
            queue.front().missingMoney != queue.front().money) return 1;
        funding[0].budget = 1e7;
        if (runRepair(720) || queue.front().status != Status::waitingResources ||
            queue.front().missingResources.empty() || city.health != .5 || !queue.front().paid ||
            funding[0].budget != 1e7-queue.front().money || !queue.front().resourcesSpent.empty()) return 1;
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
        const auto* builtNews = generated.news.latest(0);
        if (!builtNews || builtNews->key != "construction_complete" ||
            std::ranges::any_of(generated.news.visible(1),[](const auto* item) {
                return item->key == "construction_complete";
            })) return 1;
        const auto units = generated.divisions.size();
        if (generated.train(0,capital,0) != "Подготовка начата") return 1;
        const auto* started = generated.news.latest(0);
        if (!started || started->key != "division_training") return 1;
        generated.cancelTraining(0);
        const auto* cancelled = generated.news.latest(0);
        if (!cancelled || cancelled->key != "division_training_cancelled") return 1;
        generated.playerDesigns.push_back(std::make_shared<hoi5::SavedDivisionDesign>("Смешанная",hoi5::DivisionComposition{6,4}));
        const auto& mixed = generated.trainingDesign(World::baseDivisionTypes);
        if (mixed.manpower != 9200 || std::abs(mixed.combat.softAttack-17.2) > 1e-12 || mixed.speed != 1.35 ||
            World::trainingHours(mixed) != 49*24 || World::trainingCost(mixed) != 829537.) return 1;
        for (const auto& [key,amount] : mixed.capacity) generated.stockpiles[0][key] += amount;
        if (generated.train(0,capital,World::baseDivisionTypes) != "Подготовка начата") return 1;
        generated.updateTraining(World::trainingHours(mixed)-1);
        if (generated.divisions.size() != units) return 1;
        generated.updateTraining(1);
        const auto* deployed = generated.news.latest(0);
        auto stalled = grouped.front();
        stalled.status = Status::waitingResources;
        stalled.spec = int(std::ranges::find(hoi5::constructionSpecs,hoi5::supplyDepot,
            &hoi5::ConstructionSpec::building)-std::begin(hoi5::constructionSpecs));
        stalled.missingResources = {{"steel",1500.}};
        generated.construction.queues[0] = {stalled,stalled,stalled};
        generated.construction.queues[0][1].tile += 1;
        generated.construction.queues[0][2].tile += 2;
        generated.reportConstructionAlerts(6);
        const auto* warning = generated.news.latest(0);
        if (!warning || !warning->important() || !warning->body.starts_with("Заявок: 3.") ||
            warning->body.find(resourceDisplayName("steel")) == std::string::npos) return 1;
        generated.reportConstructionAlerts(6);
        if (generated.news.latest(0) != warning) return 1;
        generated.construction.queues[0].clear();
        generated.reportConstructionAlerts(6);
        generated.construction.queues[0] = {stalled};
        generated.reportConstructionAlerts(6);
        if (generated.news.latest(0) != warning || !warning->body.starts_with("Заявок: 1.")) return 1;
        generated.construction.queues[0].clear();
        generated.reportConstructionAlerts(24);
        generated.construction.queues[0] = {stalled};
        generated.reportConstructionAlerts(6);
        if (generated.news.latest(0) == warning) return 1;
        return generated.divisions.size() == units+1 && generated.divisions.back().organization == 50 &&
            generated.divisions.back().design == &mixed &&
            deployed && deployed->key == "division_deployed" ? 0 : 1;
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
        {
            World packages;
            packages.size = 8;
            packages.tiles.resize(64);
            packages.diplomacy.countries.resize(2);
            packages.diplomacy.relation(0,1).war = true;
            packages.air.wings.push_back({0,0,4,16,3,0,{true,true}});
            auto& wing = packages.air.wings.front();
            wing.composition = {{4,8},{2,8}};
            wing.sortieIntensity = 1.;
            wing.operationArea = {3,4};
            for (int tile : wing.operationArea) {
                packages.tiles[tile].owner = 1;
                packages.tiles[tile].buildings[hoi5::industry].area = .3;
                auto& defender = packages.divisions.emplace_back();
                defender.q = tile;
                defender.owner = 1;
            }
            World::SortieCounts used{};
            bool changed = false;
            if (packages.launchAirMission(0,false,wing.missionType(0),used,changed) != 4 ||
                packages.launchAirMission(0,true,wing.missionType(1),used,changed) != 4 ||
                used[4] != 4 || used[2] != 4 || packages.salvos.size() != 4 ||
                wing.missionCooldowns != std::array{8.,8.}) return 1;
            for (int i = 0; i < 4; i += 2)
                if (packages.salvos[i].target == packages.salvos[i+1].target ||
                    packages.salvos[i].sourceAircraft != (i == 0 ? 4 : 2) ||
                    packages.salvos[i+1].sourceAircraft != packages.salvos[i].sourceAircraft) return 1;
            wing.missionCooldowns = {};
            wing.abortedHours = 2.;
            if (packages.launchAirMission(0,true,wing.missionType(1),used,changed) ||
                packages.salvos.size() != 4 || wing.missionCooldowns[1] != 0.) return 1;
        }
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
        const auto homeDeployment = [](int) { return std::map<int,int>{}; };
        replacements.advanceDefenseReplacements(deployment,capitals,47,[](int) { return false; },homeDeployment,completed);
        if (!replacements.defense.empty()) return 1;
        replacements.advanceDefenseReplacements(deployment,capitals,1,[](int) { return true; },homeDeployment,completed);
        if (!replacements.defense.empty() || replacements.defenseReplacements.empty()) return 1;
        replacements.advanceDefenseReplacements(deployment,capitals,1,[](int) { return false; },homeDeployment,completed);
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
        moving.tiles[1].natural.water = .56;
        if (moving.orderAirDefenseMove(mobile,1) != "ПВО нельзя поставить на воду" ||
            mobile.route != std::deque<int>{1}) return 1;
        moving.tiles[1].natural.water = 0;
        moving.advanceAirDefense(0);
        if (mobile.progress != 0 || mobile.visualProgress != 0) return 1;
        if (moving.orderAirDefenseMove(mobile,0) != "ПВО уже здесь" || !mobile.route.empty()) return 1;
        if (moving.orderAirDefenseMove(mobile,1) != "ПВО выдвигается в 1:0") return 1;
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
    if (mode == "--check-bot-course") {
        using Course = hoi5::BotCourse;
        World test;
        test.size = 2;
        test.tiles.resize(4);
        test.tiles[0].owner = 1;
        test.capitals = {1,0};
        test.profiles.resize(2,{1.,1000000.,20000000.});
        test.diplomacy.countries.resize(2);
        for (const int owner : {1,1,1,0}) {
            auto& unit = test.divisions.emplace_back();
            unit.owner = owner;
            unit.q = owner == 1 ? 0 : 1;
            unit.organization = unit.maxOrganization = 100.;
        }
        test.startBots(7);
        auto& bot = test.supplyBots.front();
        bot.rng.seed(7);
        bot.aggression = .25;
        test.sampleBotMilitary(bot,1);
        test.sampleBotMilitary(bot,0);
        const auto own = bot.militaryReports.at(1).divisions[hoi5::attack];
        const auto enemy = bot.militaryReports.at(0).divisions[hoi5::attack];
        const double expected = 22.*(1.+(2.*.32383276483316237-1.)*.3375);
        if (own.value != 66. || own.low != own.high || std::abs(enemy.value-expected) > 1e-12 ||
            std::abs(enemy.low-expected/1.3375) > 1e-12 ||
            std::abs(enemy.high-expected/.6625) > 1e-12) return 1;
        test.botHours = 24;
        test.sampleBotMilitary(bot,0);
        if (bot.militaryReports.at(0).divisions[hoi5::attack].value != enemy.value ||
            bot.militaryReports.at(0).divisions[hoi5::attack].observedHour != 24) return 1;
        const auto proposal = test.botCourseCandidates(bot);
        if (proposal != hoi5::BotCourseOptions{{50.,{Course::development,-1}},{62.,{Course::warPreparation,0}}}) return 1;
        test.selectBotCourse(bot,proposal);
        if (bot.course.first != Course::development || test.botPreparationTarget(1) != -1) return 1;
        test.botHours = 1440;
        bot.courseBias[std::size_t(Course::development)] = -3.;
        bot.courseBias[std::size_t(Course::warPreparation)] = 3.;
        test.selectBotCourse(bot,proposal);
        if (bot.course != hoi5::BotCourseChoice{Course::warPreparation,0} || test.botPreparationTarget(1) != 0)
            return 1;
        test.profiles[1].budget = -1.;
        test.selectBotCourse(bot,proposal);
        if (bot.course.first != Course::recovery) return 1;
        test.diplomacy.relation(0,1).war = true;
        test.selectBotCourse(bot,proposal);
        if (bot.course != hoi5::BotCourseChoice{Course::defense,0} || test.botPreparationTarget(1) != -1) return 1;

        bot.nextWeekly = bot.nextMonthly = 2000.;
        bot.militaryReports.clear();
        bot.reviews = {{true,1450.,1,0,{}}};
        test.botHours = 1450;
        test.updateBotReviews(bot);
        if (bot.reviews.front().stage != 1 || bot.reviews.front().nextHour != 1456. ||
            bot.militaryReports.size() != 1 || !bot.militaryReports.contains(0)) return 1;
        test.botHours = 1456;
        test.updateBotReviews(bot);
        return bot.reviews.front().stage == 2 && bot.reviews.front().nextHour == 1462. &&
            bot.militaryReports.size() == 2 && bot.militaryReports.contains(1) ? 0 : 1;
    }
    if (mode == "--check-bot-front-posts") {
        World test;
        test.size = 5;
        test.tiles.resize(25);
        for (auto& tile : test.tiles) tile.water = true;
        for (const int tile : {0,1,2,3,4,24}) {
            test.tiles[tile].water = false;
            test.tiles[tile].owner = tile == 3 || tile == 4 ? 0 : 1;
            test.tiles[tile].supply = .7;
        }
        test.capitals = {4,0};
        test.profiles.resize(2);
        test.diplomacy.countries.resize(2);
        test.diplomacy.relation(0,1).war = true;
        for (const int tile : {0,2,1,1,24}) {
            auto& unit = test.divisions.emplace_back();
            unit.owner = 1;
            unit.q = tile%5;
            unit.r = tile/5;
            unit.organization = unit.maxOrganization = 100.;
        }
        test.divisions[2].route = {2};
        test.startBots(7);
        auto& bot = test.supplyBots.front();
        const auto pinned = test.assignBotFront(bot,true);
        if (pinned != std::set<int>{2} || bot.reserve != 0 ||
            bot.frontQuotas != std::map<int,int>{{2,3}} ||
            bot.hexAssignments != std::map<int,int>{{0,0},{1,2},{2,2},{3,2}}) return 1;
        test.updateBots(6,nullptr);
        if (test.divisions[3].route != std::deque<int>{2} ||
            bot.lastOrders != std::map<int,int>{{3,6}} || !test.divisions[4].route.empty()) return 1;
        // A reassessment after the order cooldown must still preserve an in-flight reinforcement.
        {
            auto ongoing = test;
            auto& reinforcement = ongoing.divisions[3];
            reinforcement.progress = .5;
            ongoing.botHours += 24;
            std::vector<World::BotMovement> reassigned;
            auto& controller = ongoing.supplyBots.front();
            ongoing.planBotFrontMoves(controller,reassigned);
            if (std::ranges::any_of(reassigned,[](const auto& order) { return order.unit == 3; }) ||
                controller.hexAssignments.at(3) != 2 || controller.lastOrders.at(3) != 6 ||
                reinforcement.route != std::deque<int>{2} || reinforcement.progress != .5) return 1;
        }
        if (bot.armyIds.size() != 2 || test.armies.size() != 2 ||
            std::ranges::any_of(std::span(test.divisions).first(5),[](const auto& unit) { return unit.armyId == 0; }))
            return 1;
        const auto frontArmy = std::ranges::find_if(test.armies,[](const auto& army) { return army.borderOwner == 0; });
        if (frontArmy == test.armies.end() || !frontArmy->executing || frontArmy->front.empty() ||
            test.armyMembers(1,frontArmy->id).empty()) return 1;
        const auto stableArmyIds = bot.armyIds;
        test.synchronizeBotArmies(bot,true);
        if (bot.armyIds != stableArmyIds || test.armies.size() != 2) return 1;

        World recovery;
        recovery.size = 8;
        recovery.tiles.resize(64);
        for (auto& tile : recovery.tiles) tile.owner = -1;
        for (const int tile : {0,1,32,33,48}) recovery.tiles[tile].owner = 1;
        for (const int tile : {2,51}) recovery.tiles[tile].owner = 0;
        recovery.tiles[0].supply = recovery.tiles[33].supply = .6;
        recovery.profiles.resize(2);
        recovery.capitals = {2,0};
        recovery.diplomacy.countries.resize(2);
        recovery.diplomacy.relation(0,1).war = true;
        for (const int tile : {1,32,48,2}) {
            auto& unit = recovery.divisions.emplace_back();
            unit.owner = recovery.tiles[tile].owner;
            unit.q = tile%8;
            unit.r = tile/8;
            unit.maxOrganization = 100.;
            unit.organization = unit.owner == 1 ? 20. : 100.;
        }
        recovery.divisions[2].route = {49,50,51};
        recovery.divisions[2].attackRoute = true;
        recovery.startBots(7);
        std::vector<World::BotMovement> orders;
        const auto used = recovery.planBotRecovery(recovery.supplyBots.front(),true,orders);
        if (used != std::set<int>{0,1,2} || orders.size() != 3 ||
            orders[0].unit != 0 || orders[0].tile != 0 || !orders[0].withdraw ||
            orders[1].unit != 2 || orders[1].tile != 48 || orders[1].withdraw ||
            orders[2].unit != 1 || orders[2].tile != 33 || orders[2].withdraw) return 1;
        for (const auto& order : orders)
            if (!recovery.applyBotMovement(order)) return 1;
        if (!(recovery.divisions[0].retreating && recovery.divisions[0].organization == 16. &&
            recovery.divisions[0].route == std::deque<int>{0} &&
            recovery.divisions[1].route == std::deque<int>{33} &&
            recovery.divisions[2].route.empty() && !recovery.divisions[2].attackRoute)) return 1;

        World offensive;
        offensive.size = 5;
        offensive.tiles.resize(25);
        for (auto& tile : offensive.tiles) tile.water = true;
        for (int tile : {1,6,2,3,4}) {
            offensive.tiles[tile].water = false;
            offensive.tiles[tile].owner = tile == 1 || tile == 6 ? 1 : 0;
        }
        offensive.capitals = {4,1};
        offensive.profiles.resize(2);
        offensive.diplomacy.countries.resize(2);
        offensive.diplomacy.relation(0,1).war = true;
        for (const int tile : {1,1,6,6,2}) {
            auto& unit = offensive.divisions.emplace_back();
            unit.owner = offensive.tiles[tile].owner;
            unit.q = tile%5;
            unit.r = tile/5;
            unit.organization = unit.maxOrganization = 100.;
            unit.combat.width = 80.;
        }
        offensive.startBots(7);
        auto& attacker = offensive.supplyBots.front();
        orders.clear();
        offensive.planBotAttacks(attacker,{},orders);
        if (attacker.warObjectives.at(0).anchor != 4 ||
            attacker.warObjectives.at(0).distances != std::map<int,int>{{2,2},{3,1},{4,0}} ||
            orders.size() != 2 || orders[0].unit != 0 || orders[1].unit != 2) return 1;
        for (const auto& order : orders)
            if (!order.attack || order.tile != 2 || !offensive.applyBotMovement(order)) return 1;
        return offensive.divisions[0].route == std::deque<int>{2} && offensive.divisions[0].attackRoute &&
            offensive.divisions[2].route == std::deque<int>{2} && offensive.divisions[2].attackRoute &&
            offensive.divisions[1].route.empty() && offensive.divisions[3].route.empty() ? 0 : 1;
    }
    if (mode == "--check-bot-mobilization") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int owner = bot.owner;
        auto design = hoi5::divisionTemplates[0];
        design.capacity = {{"steel",200},{"vehicles",200},{"weapons",200},
            {"field_supplies",200},{"refined_fuel",200},{"small_arms_ammo",200}};
        design.use.clear();
        test.divisions.assign(1,Division{});
        test.divisions.front().owner = owner;
        test.divisions.front().design = &design;
        test.air.defense.clear();
        test.training.clear();
        test.construction.queues[owner].clear();
        test.stockpiles[owner] = {{"steel",10},{"vehicles",20},{"weapons",30},
            {"field_supplies",40},{"refined_fuel",50},{"small_arms_ammo",60}};
        test.market.contracts = {{owner,"steel",false,10},{owner,"coal",false,10}};
        bot.tasks.clear();
        auto& pending = bot.tasks.emplace_back(hoi5::BotTask::Kind::buy,0,-1,"vehicles",12);
        pending.status = hoi5::BotTaskStatus::waitingMarket;
        test.scheduleBotMobilizationStock(bot);
        test.scheduleBotMobilizationStock(bot);
        std::vector<std::pair<std::string_view,double>> purchases;
        for (const auto& task : bot.tasks) purchases.emplace_back(task.resource,task.amount);
        const std::vector<std::pair<std::string_view,double>> expected{
            {"vehicles",12},{"steel",90},{"weapons",70},{"field_supplies",60}};
        return purchases == expected && test.market.contractAmount(owner,"steel",false) == 0 &&
            test.market.contractAmount(owner,"coal",false) == 10 && test.botBalanceRefresh.contains(owner) ? 0 : 1;
    }
    if (mode == "--check-bot-recruitment") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int owner = bot.owner;
        test.profiles[owner].budget = 1000000000.;
        test.manpowerReserve[owner] = 20000.;
        for (const auto& [key,price] : hoi5::TRADE_BASE_PRICES) test.stockpiles[owner][key] = 1000000000.;
        bot.nextRecruitment = 0;
        test.scheduleBotRecruitment(bot);
        const auto recruit = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::recruit;
        });
        if (recruit == bot.tasks.end() || recruit->trainingType < 0 || recruit->tile < 0) return 1;
        const double people = test.manpowerReserve[owner], money = test.profiles[owner].budget;
        if (!test.applyBotRecruitment(bot,*recruit) || test.training.empty() ||
            std::ranges::any_of(test.training,[&](const auto& project) { return project.country != owner; }) ||
            test.manpowerReserve[owner] >= people || test.profiles[owner].budget >= money) return 1;
        test.training.clear();
        bot.tasks.clear();
        for (auto& [key,amount] : test.stockpiles[owner]) amount = 0.;
        test.manpowerReserve[owner] = 20000.;
        bot.nextRecruitment = 168;
        test.scheduleBotRecruitment(bot);
        if (!bot.tasks.empty()) return 1;
        test.scheduleBotRecruitment(bot,true);
        if (bot.nextRecruitment != 168) return 1;
        return std::ranges::any_of(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::buy && task.amount > 0;
        }) && std::ranges::none_of(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::recruit;
        }) ? 0 : 1;
    }
    if (mode == "--check-bot-air") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int owner = bot.owner;
        test.diplomacy.relation(0,owner).war = true;
        test.stockpiles[owner]["refined_fuel"] = 1000000.;
        bot.regions = test.botGeography.profiles(test.tiles,owner,test.capitals[owner],
            [&](int tile) { return test.airDefenseWater(tile); });
        bot.nextAir = 0;
        test.scheduleBotAir(bot);
        const auto task = std::ranges::find_if(bot.tasks,[](const auto& item) {
            return item.kind == hoi5::BotTask::Kind::air;
        });
        if (task == bot.tasks.end() || task->tile < 0 || !test.applyBotAir(bot,*task)) return 1;
        int wings = 0;
        for (const auto& wing : test.air.wings) {
            if (wing.owner != owner) continue;
            ++wings;
            if (wing.operationArea.empty() || wing.sortieIntensity < .65 || wing.risk != hoi5::AirRisk::normal)
                return 1;
            if (wing.missionType(2) >= 0 && (!wing.airSuperiority || !wing.intercept || !wing.patrol)) return 1;
        }
        return wings > 0 ? 0 : 1;
    }
    if (mode == "--check-bot-economy") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int owner = bot.owner;
        test.profiles[owner].budget = 1000000000.;
        for (const auto& [key,price] : hoi5::TRADE_BASE_PRICES) test.stockpiles[owner][key] = 1000000000.;
        test.stockpiles[owner]["machinery"] = 0.;
        test.production[owner] = {};
        test.production[owner][hoi5::finished].inputs["machinery"] = 10000.;
        test.construction.queues[owner].clear();
        bot.regions = test.botGeography.profiles(test.tiles,owner,test.capitals[owner],
            [&](int tile) { return test.airDefenseWater(tile); });
        bot.nextEconomy = 0;
        test.scheduleBotEconomy(bot);
        const auto buy = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::buy && task.resource == "machinery";
        });
        auto build = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::build;
        });
        auto specialize = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::specialize;
        });
        if (buy == bot.tasks.end() || build == bot.tasks.end() || specialize == bot.tasks.end() ||
            build->sector != "machinery" || specialize->sector != "machinery") {
            std::cerr << "bot economy scheduling failed: buy=" << (buy != bot.tasks.end()) <<
                " build=" << (build != bot.tasks.end()) << " specialize=" << (specialize != bot.tasks.end()) << '\n';
            return 1;
        }
        const auto region = std::ranges::find_if(bot.regions,[&](const auto& item) {
            return std::ranges::find(item.tiles,specialize->tile) != item.tiles.end();
        });
        if (region == bot.regions.end()) {
            std::cerr << "bot economy region missing\n";
            return 1;
        }
        test.tiles[region->tiles.front()].buildings[hoi5::industry] = {.2,1.};
        test.tiles[region->tiles.front()].industries = {"consumer_goods"};
        if (test.applyBotConstruction(bot,*build) || !test.construction.queues[owner].empty()) {
            std::cerr << "bot economy ignored the machinery shortage\n";
            return 1;
        }
        test.stockpiles[owner]["machinery"] = 1000000000.;
        const bool built = test.applyBotConstruction(bot,*build);
        const bool specialized = test.applyBotSpecialization(bot,*specialize);
        if (!built || test.construction.queues[owner].empty() || !specialized) {
            std::cerr << "bot economy apply failed: build=" << built << " queue=" <<
                test.construction.queues[owner].size() << " specialize=" << specialized << '\n';
            return 1;
        }
        return test.tiles[region->tiles.front()].industries ==
            std::vector<std::string_view>{"machinery","consumer_goods"} ? 0 : 1;
    }
    if (mode == "--check-bot-claim") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int owner = bot.owner;
        const auto unit = std::ranges::find_if(test.divisions,[&](const auto& division) {
            return division.owner == owner && division.combat.strength > 0;
        });
        if (unit == test.divisions.end()) return 1;
        const int origin = unit->r*test.size+unit->q;
        const auto adjacent = test.botGeography.adjacent(origin);
        if (adjacent.empty()) return 1;
        const int target = adjacent.front();
        for (auto& tile : test.tiles) {
            tile.owner = owner;
            tile.water = 0;
            tile.movementCost = 1.;
            tile.deposits.clear();
        }
        test.tiles[target].owner = -1;
        test.tiles[target].deposits = {{"iron_ore",.1,1000000.}};
        test.production[owner] = {};
        test.production[owner][hoi5::semiFinished].inputs["iron_ore"] = 10000.;
        test.stockpiles[owner]["iron_ore"] = 0.;
        bot.course = {hoi5::BotCourse::development,-1};
        bot.expansionTarget = -1;
        bot.tasks.clear();
        bot.nextExpansion = 0.;
        test.scheduleBotExpansion(bot);
        const auto claim = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::claim;
        });
        if (claim == bot.tasks.end() || claim->tile != target || !test.applyBotClaim(bot,*claim)) return 1;
        const auto ordered = std::ranges::find_if(test.divisions,[&](const auto& division) {
            return division.owner == owner && !division.route.empty() && division.route.back() == target;
        });
        return ordered != test.divisions.end() ? 0 : 1;
    }
    if (mode == "--check-ai-profiler") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        bot.nextDaily = bot.nextMicro = bot.nextAir = bot.nextRecruitment = bot.nextEconomy = bot.nextExpansion =
            bot.nextDiplomacy = 0.;
        hoi5::DebugProfiler profiler;
        test.updateBots(24,&profiler);
        profiler.frame(.5);
        constexpr std::array keys{"ai_total","ai_reviews","ai_daily","ai_regions","ai_supply_planning",
            "ai_defense_planning","ai_recruitment_planning","ai_air_planning","ai_economy_planning",
            "ai_expansion_planning","ai_diplomacy_planning","ai_micro","ai_front_planning","ai_tasks"};
        for (const auto key : keys) {
            const auto row = std::ranges::find_if(hoi5::debugRows,[&](const auto& item) {
                return std::ranges::find(item.keys,key) != item.keys.end();
            });
            if (row == std::end(hoi5::debugRows) || profiler.average(*row) <= 0.) {
                std::cerr << "F3 AI row missing or empty: " << key << '\n';
                return 1;
            }
        }
        return 0;
    }
    if (mode == "--check-bot-diplomacy") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int owner = bot.owner, target = owner == 0 ? 1 : 0;
        test.profiles[owner].budget = 50000000.;
        auto& policy = test.diplomacy.countries[owner];
        policy.support = .5;
        bot.intelligence = .25;
        bot.nextDiplomacy = 0;
        test.scheduleBotDiplomacy(bot);
        auto mission = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::politics &&
                task.politicalAction == int(hoi5::ForeignAction::mission);
        });
        auto support = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::support;
        });
        auto intelligence = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::intelligence;
        });
        if (mission == bot.tasks.end() || support == bot.tasks.end() || intelligence == bot.tasks.end() ||
            !test.applyBotPolitics(bot,*mission) || !test.applyBotPolitics(bot,*support) ||
            !test.applyBotPolitics(bot,*intelligence) || policy.programHours[0] != 720 || bot.intelligence != .35)
            return 1;
        bot.tasks.clear();
        bot.course = {hoi5::BotCourse::warPreparation,target};
        bot.nextDiplomacy = 0;
        policy.support = policy.legitimacy = .7;
        test.scheduleBotDiplomacy(bot);
        const auto justify = std::ranges::find_if(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::politics &&
                task.politicalAction == int(hoi5::ForeignAction::justify);
        });
        if (justify == bot.tasks.end() || !test.applyBotPolitics(bot,*justify) ||
            !test.diplomacy.goals.contains({owner,target})) return 1;
        bot.tasks.clear();
        test.diplomacy.relation(owner,target).war = true;
        policy.warSupport = .3;
        bot.nextDiplomacy = 0;
        test.scheduleBotDiplomacy(bot);
        return std::ranges::any_of(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::politics &&
                task.politicalAction == int(hoi5::ForeignAction::peace);
        }) ? 0 : 1;
    }
    if (mode == "--check-bot-offers") {
        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int target = bot.owner, actor = target == 0 ? 1 : 0;
        bot.course = {hoi5::BotCourse::warPreparation,actor};
        auto& relation = test.diplomacy.relation(actor,target);
        relation.opinion[target] = 100.;
        relation.trust = 1.;
        test.diplomacy.countries[actor].reliability = 1.;
        test.diplomacy.countries[actor].reputation = 1.;
        test.diplomacy.offers.push_back({actor,target,test.diplomacy.day+1,hoi5::ForeignAction::alliance});
        hoi5::DebugProfiler profiler;
        test.advancePolitics(test.diplomacy.day+1,{},&profiler);
        profiler.frame(.5);
        if (relation.treaties.contains(hoi5::ForeignAction::alliance) || !test.diplomacy.offers.empty()) {
            std::cerr << "bot offer rejection failed: treaty=" <<
                relation.treaties.contains(hoi5::ForeignAction::alliance) << " pending=" <<
                test.diplomacy.offers.size() << '\n';
            return 1;
        }
        const auto row = std::ranges::find_if(hoi5::debugRows,[](const auto& item) {
            return std::ranges::find(item.keys,"ai_offer_response") != item.keys.end();
        });
        if (row == std::end(hoi5::debugRows) || !profiler.hasAverage("ai_offer_response")) {
            std::cerr << "bot offer profiler failed\n";
            return 1;
        }

        relation.war = true;
        relation.warStarted = test.diplomacy.day;
        relation.opinion[target] = -100.;
        test.profiles[target].budget = -1.;
        test.diplomacy.countries[target].warSupport = .8;
        test.diplomacy.offers.push_back({actor,target,test.diplomacy.day+1,hoi5::ForeignAction::peace});
        test.advancePolitics(test.diplomacy.day+1);
        if (relation.war || !test.diplomacy.offers.empty()) {
            std::cerr << "bot peace response failed: war=" << relation.war << " pending=" <<
                test.diplomacy.offers.size() << '\n';
            return 1;
        }
        return 0;
    }
    if (mode == "--check-bot-dependencies") {
        hoi5::FlowLedger ledger;
        ledger.sample(1,0);
        for (int day = 1; day < 40; ++day) {
            ledger.advance(1,24);
            ledger.record(1,hoi5::FlowKind::output,"oil",10);
            ledger.record(1,hoi5::FlowKind::import,"food",3,2);
            ledger.sample(1,day*24);
        }
        const auto [rates,hours] = ledger.rates(1,39*24);
        if (rates.at({hoi5::FlowKind::output,"oil",-1}) != 300. ||
            rates.at({hoi5::FlowKind::import,"food",2}) != 90. || hours != 168. ||
            ledger.samples[1].size() > 10) return 1;

        auto test = generateWorld(20,2,918273,1);
        test.startBots(918273);
        auto& bot = test.supplyBots.front();
        const int owner = bot.owner, partner = owner == 0 ? 1 : 0;
        test.production[owner] = {};
        test.production[owner][hoi5::upkeep].inputs["food"] = 180.;
        test.stockpiles[owner]["food"] = 90.;
        test.botLedger.advance(owner,168.);
        test.botLedger.record(owner,hoi5::FlowKind::import,"food",42.,partner);
        test.botHours = 168;
        bot.reviews.clear();
        bot.reviews.push_back({true,0.,2});
        hoi5::DebugProfiler profiler;
        test.updateBotReviews(bot,&profiler);
        profiler.frame(.5);
        const auto dependency = bot.dependencies.find({partner,"food"});
        const auto row = std::ranges::find_if(hoi5::debugRows,[](const auto& item) {
            return std::ranges::find(item.keys,"ai_dependencies") != item.keys.end();
        });
        if (dependency == bot.dependencies.end() || std::abs(dependency->second.share-1.) > 1e-9 ||
            std::abs(dependency->second.stockDays-15.) > 1e-9 || row == std::end(hoi5::debugRows) ||
            !profiler.hasAverage("ai_dependencies")) return 1;
        bot.tasks.clear();
        bot.nextDiplomacy = 0.;
        test.scheduleBotDiplomacy(bot);
        return std::ranges::any_of(bot.tasks,[](const auto& task) {
            return task.kind == hoi5::BotTask::Kind::politics &&
                task.politicalAction == int(hoi5::ForeignAction::trade);
        }) ? 0 : 1;
    }
    if (mode == "--check-bot-regions") {
        World test;
        test.size = 8;
        test.tiles.resize(64);
        test.tiles.back().water = true;
        auto water = [&](int tile) { return test.airDefenseWater(tile); };
        test.botGeography.build(test.size,water,[&](int tile,auto visit) { test.forFrontNeighbor(tile,visit); });
        auto regions = test.botGeography.profiles(test.tiles,0,0,water);
        if (regions.size() != 2 || regions[0].base != 0 || regions[1].base != 1 ||
            regions[0].tiles.size() != 48 || regions[1].tiles.size() != 15) return 1;
        constexpr std::array first{0,8,1,17,16,9,2,25,24,18,10,3};
        constexpr std::array second{60,53,61,45,54};
        if (!std::equal(first.begin(),first.end(),regions[0].tiles.begin()) ||
            !std::equal(second.begin(),second.end(),regions[1].tiles.begin())) return 1;

        for (int index : {0,1,2}) {
            auto& tile = test.tiles[index];
            tile.owner = 1;
            tile.population = 100000;
            tile.supply = .6;
        }
        test.tiles[0].buildings[hoi5::industry] = {.5,.5};
        test.tiles[0].industries = {"metallurgy"};
        regions = test.botGeography.profiles(test.tiles,1,0,water);
        if (regions.size() != 1) return 1;
        const auto& profile = regions.front();
        if (profile.tiles != std::vector<int>{0,1,2} || profile.borders != profile.tiles ||
            profile.population != 300000 || std::abs(profile.supply-.6) > 1e-12 ||
            profile.buildings[hoi5::industry] != .25 || profile.importance != 34.25 ||
            hoi5::value(profile.output,"steel") != 1300.) return 1;

        test.profiles.resize(2);
        test.diplomacy.countries.resize(2);
        test.divisions.resize(2);
        auto& friendly = test.divisions[0];
        friendly.owner = 1;
        friendly.combat.strength = 50.;
        friendly.organization = 50.;
        friendly.maxOrganization = 100.;
        friendly.lastSupplyRatio = .5;
        friendly.speed = 1.35;
        auto& enemy = test.divisions[1];
        enemy.q = enemy.r = 1;
        enemy.organization = enemy.maxOrganization = 100.;
        hoi5::BotSupplyState bot{1,0.};
        bot.regions = regions;
        test.updateBotRegionalMilitary(bot);
        const auto& military = bot.regions.front();
        if (military.military != hoi5::BotMilitary{10000.,4.640625,5.484375,1.6875,1.,.84375,.675,.2109375} ||
            military.threat != 0. || military.desiredDefense != 0.) return 1;
        test.diplomacy.relation(0,1).war = true;
        test.updateBotRegionalMilitary(bot);
        if (military.threat != 22. || std::abs(military.desiredDefense-25.3) > 1e-12) return 1;
        enemy.organization = 0.;
        test.updateBotRegionalMilitary(bot);
        if (military.threat != 5.5 || military.desiredDefense != 12.) return 1;

        test.tiles[1].owner = 0;
        regions = test.botGeography.profiles(test.tiles,1,0,water);
        return regions.size() == 2 && regions[0].base == 0 && regions[1].base == 0 &&
            regions[0].owner == 1 && regions[1].owner == 1 &&
            regions[0].anchor == 0 && regions[1].anchor == 2 &&
            regions[0].tiles == std::vector<int>{0} && regions[1].tiles == std::vector<int>{2} ? 0 : 1;
    }
    if (mode == "--check-supply-parity") {
        constexpr std::array points{hoi5::BotSupplyPoint{2,3.,.5,.1},hoi5::BotSupplyPoint{6,2.,1.,.2}};
        constexpr std::array candidates{hoi5::BotSupplyCandidate{1,.8,1.},hoi5::BotSupplyCandidate{6,.7,.85}};
        const auto choice = hoi5::bestBotSupplySite(4,points,candidates);
        if (!choice || choice->tile != 1 || std::abs(choice->gain-1.60256) > 1e-12) return 1;
        {
            World bot;
            bot.size = 3;
            bot.tiles.resize(9);
            bot.profiles.resize(2,{1.,1000000.,20000000.});
            bot.stockpiles.resize(2);
            bot.capacities.resize(2);
            for (const auto key : World::botDepotResources)
                bot.capacities[1][hoi5::storageBucket(key)] = 100000.;
            bot.treasury.resize(2);
            bot.diplomacy.countries.resize(2);
            bot.construction.queues.resize(2);
            bot.capitals = {0,1};
            bot.tiles[1].owner = 1;
            auto& division = bot.divisions.emplace_back();
            division.q = division.owner = 1;
            bot.startBots(7);
            bot.supplyBots.front().nextDiplomacy = std::numeric_limits<double>::max();
            bot.profiles[1].budget = 5000000.;
            bot.updateBots(24,nullptr);
            auto& tasks = bot.supplyBots.front().tasks;
            if (!bot.construction.queues[1].empty() || tasks.size() != 1 ||
                tasks.front().status != hoi5::BotTaskStatus::blocked || tasks.front().retryHour != 48) return 1;
            bot.profiles[1].budget = 20000000.;
            bot.updateBots(23,nullptr);
            if (!bot.construction.queues[1].empty()) return 1;
            bot.updateBots(1,nullptr);
            if (!bot.construction.queues[0].empty() || bot.construction.queues[1].size() != 1 ||
                bot.construction.queues[1].front().tile != 1 ||
                tasks.front().status != hoi5::BotTaskStatus::executing || tasks.size() < 2) return 1;
            bot.updateBots(1,nullptr);
            if (tasks.size() != 5 || bot.market.contractAmount(1,"construction_goods",true) != 325. ||
                bot.construction.queues[1].size() != 1 ||
                std::next(tasks.begin())->status != hoi5::BotTaskStatus::waitingMarket) return 1;
            ++bot.botMarketTick;
            bot.market.last.fills = {{1,std::nullopt,"construction_goods",10.,1.}};
            bot.updateBots(1,nullptr);
            if (std::next(tasks.begin())->status != hoi5::BotTaskStatus::succeeded ||
                std::next(tasks.begin(),2)->status != hoi5::BotTaskStatus::failed) return 1;
        }
        {
            World bot;
            bot.size = 4;
            bot.tiles.resize(16);
            for (auto& tile : bot.tiles) tile.owner = -1;
            for (int index : {0,1,2}) {
                bot.tiles[index].owner = 1;
                bot.tiles[index].supply = .65;
            }
            bot.tiles[3].owner = 0;
            bot.capitals = {3,0};
            bot.profiles.resize(2,{1.,1000000.,20000000.});
            bot.diplomacy.countries.resize(2);
            bot.stockpiles.resize(2);
            bot.capacities.resize(2);
            bot.treasury.resize(2);
            bot.construction.queues.resize(2);
            for (const auto& [key,price] : hoi5::TRADE_BASE_PRICES) {
                bot.stockpiles[1][key] = 10000.;
                bot.capacities[1][hoi5::storageBucket(key)] = 1000000.;
            }
            bot.air.defense.push_back({1,0,1,16});
            auto& division = bot.divisions.emplace_back();
            division.owner = 1;
            division.q = 2;
            bot.startBots(7);
            bot.supplyBots.front().nextDiplomacy = std::numeric_limits<double>::max();
            bot.air.defense.clear();
            bot.diplomacy.goals[{1,0}] = 30;
            bot.updateBots(24,nullptr);
            const auto project = bot.air.defenseReplacements.find(1);
            if (project == bot.air.defenseReplacements.end() || project->second.type != 1 ||
                bot.profiles[1].budget != 18800000. || bot.stockpiles[1]["old_light_aa_artillery"] != 9998. ||
                !bot.construction.queues[1].empty()) return 1;
            bot.air.advanceDefenseReplacements(bot.tiles,bot.capitals,48,[](int) { return false; },
                [&](int owner) { return bot.botForwardDefenseSites(owner); },[](int,int) {});
            if (bot.air.defense.size() != 1 || bot.air.defense.front().tile != 1) return 1;
            bot.diplomacy.relation(1,0).war = true;
            bot.updateBots(24,nullptr);
            if (bot.construction.queues[1].size() != 1) return 1;
            const auto& fort = bot.construction.queues[1].front();
            if (fort.tile != 2 || hoi5::constructionSpecs[fort.spec].building != hoi5::fortification) return 1;
        }
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
    if (mode == "--check-news-log" && argc == 3) {
        const std::filesystem::path path(argv[2]);
        constexpr std::array<std::string_view,2> countries{"Игрок","Сосед"}, rulers{"Правитель",""};
        const auto read = [&] {
            std::ifstream stream(path);
            return std::string(std::istreambuf_iterator<char>(stream),{});
        };
        hoi5::News news(123);
        news.startLog(path,countries,rulers);
        for (int day = 0; day < 305; ++day)
            news.report(day,"test","Заголовок "+std::to_string(day),"Описание "+std::to_string(day),
                hoi5::NewsPriority::important,0,1);
        news.report(305,"world","Мировая новость","Описание",hoi5::NewsPriority::flavor);
        const auto journal = read();
        if (!journal.starts_with("HOI5 — история новостей новой партии\nСид: 123\nНачало: 2000-01-01\n"
                "Страна 0: Игрок; правитель: Правитель\nСтрана 1: Сосед; правитель: не указан\n\n") ||
            journal.find("[2000-01-01] #1 [important] [страны 0, 1] test\nЗаголовок 0\nОписание 0\n\n") == std::string::npos ||
            journal.find("[2000-10-31] #305 [important] [страны 0, 1] test\nЗаголовок 304\nОписание 304\n\n") == std::string::npos ||
            !journal.ends_with("[2000-11-01] #306 [flavor] [мир] world\nМировая новость\nОписание\n\n") ||
            news.visible(0).size() != 300) return 1;
        hoi5::News restarted(456);
        restarted.startLog(path,countries,rulers);
        const auto reset = read();
        if (reset.find("Сид: 456\n") == std::string::npos || reset.find("Заголовок") != std::string::npos) return 1;
        restarted.startLog(path/"world-news.txt",countries,rulers);
        restarted.report(0,"still_visible","Игра продолжается","Нет доступа к журналу");
        const auto* item = restarted.latest(0);
        return item && item->key == "still_visible" ? 0 : 1;
    }
    if (mode == "--check-news-popup") {
        hoi5::Market steadyMarket;
        const std::vector<hoi5::MarketOrder> coalOrders{{0,"coal",true,10000.}};
        for (int week = 0; week < 60; ++week) steadyMarket.updatePrices(coalOrders,{{"coal",10000.}});
        if (steadyMarket.price("coal") <= steadyMarket.base("coal") ||
            std::abs(steadyMarket.priceChange("coal")) > .0001) return 1;
        steadyMarket.updatePrices({{0,"coal",true,10000.},{1,"coal",false,10000.}},{{"coal",10000.}});
        if (steadyMarket.priceChange("coal") >= 0.) return 1;
        hoi5::News news;
        hoi5::NewsPanel panel;
        const sf::Vector2f size{1200,800};
        const auto update = [&](float inset = 0.f) { panel.update(news,0.f,size,16.f,0.f,inset); };
        for (int i = 0; i < 13; ++i)
            news.report(0,"yellow","Важно",std::to_string(i),hoi5::NewsPriority::important);
        update();
        const float initialX = panel.popupBounds().position.x;
        if (!panel.activeItem() || panel.activeItem()->body != "0") return 1;
        for (int i = 0; i < 12; ++i)
            news.report(0,"red","Срочно",std::to_string(i),hoi5::NewsPriority::critical);
        update(258);
        if (panel.popupBounds().position.x != initialX-258) return 1;
        int yellow = 0, red = 0;
        while (const auto* item = panel.activeItem()) {
            if (item->priority == hoi5::NewsPriority::critical) {
                if (yellow || item->body != std::to_string(red++)) return 1;
            } else ++yellow;
            const auto bounds = panel.popupBounds();
            if (!panel.click(bounds.position+sf::Vector2f{bounds.size.x-12,10},true)) return 1;
            update(258);
        }
        return red == 12 && yellow == 9 ? 0 : 1;
    }
    if (mode == "--check-army-front") {
        {
            World capture;
            capture.size = 6;
            capture.tiles.resize(36);
            capture.armies = {{1,0,"Manual"},{2,0,"Automatic"}};
            std::vector<int> oldLine, expected;
            for (int r = 0; r < 6; ++r) {
                oldLine.push_back(r*6+2);
                expected.push_back(r*6+3);
                for (int q = 0; q < 6; ++q) capture.tiles[r*6+q].owner = q >= 3 ? 1 : 0;
            }
            if (!capture.setArmyFront(0,1,oldLine,false,true) ||
                !capture.setArmyFront(0,2,{oldLine.front()},true,true)) return 1;
            capture.toggleArmyFront(0,1);
            capture.toggleArmyFront(0,2);
            for (int tile : expected) capture.transferTile(tile,0);
            capture.advance(1);
            for (const auto& army : capture.armies) {
                auto actual = army.front;
                std::ranges::sort(actual);
                if (actual != expected || army.executing) return 1;
            }
        }
        World fixture;
        fixture.size = 6;
        fixture.tiles.resize(36);
        for (int i = 0; i < 36; ++i) {
            fixture.tiles[i].owner = i%6 >= 4 ? 1 : 0;
            fixture.tiles[i].supply = 1.;
        }
        fixture.divisions.resize(3);
        auto& unit = fixture.divisions[0];
        unit.q = 1;
        unit.r = 2;
        unit.maxOrganization = unit.organization = 100.;
        auto& enemy = fixture.divisions[1];
        enemy.owner = 1;
        enemy.q = 4;
        enemy.r = 2;
        enemy.maxOrganization = enemy.organization = 100.;
        fixture.divisions[2].combat.strength = 0.;
        fixture.diplomacy.relation(0,1).war = true;
        const int id = fixture.createArmy(0,{0,1,2});
        if (id != 1 || fixture.armyMembers(0,id) != std::vector<int>{0} ||
            fixture.addDivisionsToArmy(1,id,{1}) ||
            fixture.createArmy(0,{0,1,2})) return 1;
        if (!fixture.setArmyFront(0,id,{3+2*6},true,true) || fixture.armies[0].front.size() != 6) return 1;
        if (!fixture.armies[0].executing) return 1;
        fixture.orderSelectedDivisions({0},2+2*6,false);
        if (unit.route.empty() || unit.manualFrontHours != 24) return 1;
        fixture.advanceManualFrontTimers(30);
        fixture.updateArmyFronts(30);
        if (unit.route.back() != 2+2*6 || unit.manualFrontHours != 24) return 1;
        unit.q = 2;
        unit.route.clear();
        fixture.advanceManualFrontTimers(23);
        fixture.updateArmyFronts(23);
        if (!unit.route.empty() || unit.manualFrontHours != 1) return 1;
        fixture.advanceManualFrontTimers(6);
        fixture.updateArmyFronts(6);
        if (unit.route.empty() || unit.route.back()%6 != 3 || unit.assignedFrontPost != unit.route.back() ||
            fixture.frontDistance(unit.route.back(),enemy.r*6+enemy.q) > 1) return 1;
        fixture.clearArmyFront(0,id);
        if (!unit.route.empty() || fixture.armies[0].executing) return 1;
        const int post = 3+2*6, target = 4+2*6;
        unit.q = 3;
        unit.r = 2;
        if (fixture.setArmyOffensive(0,id,{post}) || !fixture.setArmyOffensive(0,id,{target}) ||
            fixture.armies[0].executing) return 1;
        fixture.toggleArmyFront(0,id);
        fixture.advanceManualFrontTimers(6);
        fixture.updateArmyFronts(6);
        if (!unit.route.empty()) return 1;
        if (!fixture.setArmyFront(0,id,{post},false,true)) return 1;
        unit.manualFrontHours = 12;
        fixture.advanceManualFrontTimers(6);
        fixture.updateArmyFronts(6);
        if (!unit.route.empty()) return 1;
        fixture.advanceManualFrontTimers(6);
        fixture.updateArmyFronts(6);
        if (unit.route != std::deque<int>{target} || !unit.attackRoute) return 1;
        fixture.clearArmyFront(0,id);
        if (!unit.route.empty() || !fixture.armies[0].offensive.empty()) return 1;
        unit.q = 0;
        unit.speed = unit.design->speed;
        if (!fixture.setArmyFront(0,id,{post},false,true)) return 1;
        hoi5::DebugProfiler profiler;
        fixture.advance(6,&profiler);
        if (unit.route.empty() || unit.progress != 0. || unit.battle >= 0) return 1;
        profiler.frame(.5);
        if (profiler.average({"",{"server_army_plans"}}) <= 0.) return 1;
        fixture.advance(1);
        if (unit.progress <= 0.) return 1;
        fixture.detachDivisionsFromArmy(0,{0});
        return fixture.armyMembers(0,id).empty() && fixture.createArmy(0,{0}) == 2 ? 0 : 1;
    }
    if (mode == "--check-path-parity") {
        World test;
        const hoi5::Stockpile sparse{{"iron_ore",20},{"gold",5},{"coal",70},{"uranium",10},
            {"consumer_goods",4},{"steel",100},{"refined_fuel",200}};
        if (World::resourceSummary(sparse) != std::array{25.,80.,4.}) return 1;
        test.size = 3;
        test.tiles.resize(9);
        Division unit;
        unit.organization = unit.maxOrganization = 100;
        if (!test.orderMove(unit,4) || unit.route != std::deque<int>{3,4}) return 1;
        test.tiles[3].movementCost = 2;
        if (!test.orderMove(unit,4) || unit.route != std::deque<int>{1,4}) return 1;

        test.divisions.push_back(unit);
        auto& marching = test.divisions.front();
        marching.progress = .4;
        marching.visualProgress = .25;
        test.orderSelectedDivisions({0},5,true);
        if (marching.route != std::deque<int>{1,4,5} || marching.progress != .4 ||
            marching.visualProgress != .25) return 1;
        test.orderSelectedDivisions({0},5,true);
        if (marching.route != std::deque<int>{1,4,5}) return 1;
        test.orderSelectedDivisions({0},2,false);
        if (marching.route != std::deque<int>{1,2} || marching.progress != 0 ||
            marching.visualProgress != 0) return 1;
        test.orderSelectedDivisions({0},0,false);
        if (!marching.route.empty()) return 1;
        marching.retreating = true;
        marching.route = {1};
        test.orderSelectedDivisions({0},2,true);
        test.orderSelectedDivisions({0},0,false);
        if (marching.route != std::deque<int>{1} || !marching.retreating) return 1;

        marching.retreating = false;
        marching.organization = 50.;
        marching.speed = 1.6;
        marching.combat.vehicles = .5;
        marching.progress = marching.visualProgress = .1;
        marching.supplies = {{"refined_fuel",2.16},{"field_supplies",.54}};
        test.tiles[1].movementCost = 2.;
        test.tiles[1].natural.trees = .8;
        test.tiles[1].natural.grass = .2;
        if (test.updateDivisions(6) || marching.route != std::deque<int>{1} ||
            std::abs(marching.progress-.18049375) > 1e-12 ||
            std::abs(marching.organization-49.88730875) > 1e-12 ||
            hoi5::value(marching.supplies,"refined_fuel") != 0. ||
            hoi5::value(marching.supplies,"field_supplies") != 0.) return 1;

        auto design = *marching.design;
        design.capacity = {{"infantry_equipment",100.}};
        marching.design = &design;
        marching.supplies = {{"infantry_equipment",0.}};
        marching.combat.strength = 90.;
        marching.manpower = 9000;
        test.stockpiles = {{{"infantry_equipment",20.}}};
        test.manpowerReserve = {10.};
        test.tiles[0].supply = .5;
        test.replenish(marching,6);
        return std::abs(hoi5::value(marching.supplies,"infantry_equipment")-2.25) < 1e-12 &&
            std::abs(hoi5::value(test.stockpiles[0],"infantry_equipment")-17.708) < 1e-12 &&
            std::abs(marching.combat.strength-90.1) < 1e-12 && marching.manpower == 9010 &&
            test.manpowerReserve[0] == 0. ? 0 : 1;
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
        hoi5::CountryPolitics support;
        support.supply = .8;
        support.taxes[0] = 1;
        support.food = .8;
        support.foodPrice = 1.1;
        support.goodsPrice = 1.2;
        const double effect = support.programSupportEffect(8,20e6,1e6,.5);
        if (std::abs(effect-.00644) > 1e-12 ||
            std::abs(support.supportTarget(8,-1,1,effect,.004)-.40894) > 1e-12) return 1;
        support.factionShares = {.25,.5,.125,.125};
        if (std::abs(support.programSupportEffect(8,20e6,1e6,.5)-.00322) > 1e-12) return 1;
        hoi5::Diplomacy ideology;
        ideology.countries.resize(2);
        ideology.countries[0] = support;
        if (std::abs(ideology.ideologyDistance(0,1)-.25) > 1e-12) return 1;
        World ranking;
        ranking.profiles.resize(2);
        ranking.diplomacy.countries.resize(2);
        ranking.treasury.resize(2);
        ranking.divisions.resize(2);
        for (int i = 0; i < 2; ++i) {
            ranking.profiles[i].population = i == 0 ? 2e6 : 1e6;
            ranking.treasury[i].population = i == 0 ? 2e6 : 1e6;
            auto& unit = ranking.divisions[i];
            unit.owner = i;
            unit.combat = unit.design->combat;
            unit.maxOrganization = 100;
            unit.organization = i == 0 ? 100 : 0;
        }
        const auto ratings = ranking.powerRanking();
        if (std::abs(ratings[0].total-80.) > 1e-10 || std::abs(ratings[1].total-32.5) > 1e-10 ||
            ratings[0].rank != 1 || ratings[1].rank != 2 ||
            World::relativePower(ratings[1].total,ratings[0].total) != "Значительно слабее нас" ||
            World::relativePower(0,0) != "Сопоставимая мощь") return 1;
        hoi5::News combatNews;
        combatNews.recordBattleLoss(1,7,0,0,"Player","Target",11.);
        if (combatNews.latest(0)) return 1;
        combatNews.recordBattleLoss(2,7,0,0,"Player","Target",1.);
        const auto* firstLoss = combatNews.latest(0);
        if (!firstLoss || firstLoss->key != "battle_losses" || combatNews.latest(1)) return 1;
        if (combatNews.latestImportant(0,"battle_losses",2) != firstLoss ||
            combatNews.latestImportant(0,"battle_losses",3) || combatNews.latestImportant(1,"battle_losses",1)) return 1;
        combatNews.recordBattleLoss(31,7,0,0,"Player","Target",12.);
        if (combatNews.latest(0) != firstLoss) return 1;
        combatNews.recordBattleLoss(32,7,0,0,"Player","Target",.1);
        if (combatNews.latest(0)->day != 32) return 1;
        combatNews.recordLogisticsDamage(1,1,"Target",1,0,1,"порт",.6,.5);
        combatNews.recordLogisticsDamage(45,1,"Target",1,0,1,"порт",.6,.5);
        if (!combatNews.latest(1) || combatNews.latest(1)->day != 1) return 1;
        combatNews.recordLogisticsDamage(46,1,"Target",1,0,1,"порт",.6,.5);
        if (combatNews.latest(1)->day != 46 || combatNews.latest(0)->day != 32) return 1;
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
        test.countryNames[0] = "Player";
        test.countryNames[1] = "Target";
        {
            auto finance = test;
            const double a = finance.profiles[0].budget, b = finance.profiles[1].budget;
            if (!finance.performForeignAction(0,1,hoi5::foreignAid,2000).empty() ||
                finance.profiles[0].budget != a-2000 || finance.profiles[1].budget != b+2000) return 1;
            if (!finance.performForeignAction(1,0,hoi5::foreignLoan,12000).empty() ||
                finance.profiles[0].budget != a-2000 || !finance.answerForeignOffer(1,0,true) ||
                finance.profiles[0].budget != a+10000 || finance.diplomacy.loans.size() != 1) return 1;
            finance.profiles[0].budget = 0.;
            finance.advancePolitics(30);
            if (finance.diplomacy.monthlyDebtFlows(0) != std::pair{0.,1050.} ||
                finance.diplomacy.monthlyDebtFlows(1) != std::pair{1050.,0.} ||
                finance.diplomacy.loans.front().principalDue != 1000. ||
                finance.diplomacy.loans.front().interestDue != 50.) return 1;
            finance.profiles[0].budget = 1050.;
            finance.advancePolitics(31);
            if (finance.diplomacy.loans.front().principal != 11000. || finance.profiles[0].budget != 0.) return 1;
        }
        {
            auto offers = test;
            if (!offers.performForeignAction(1,0,action(hoi5::ForeignAction::transit)).empty()) return 1;
            const auto* notice = offers.news.latest(0);
            if (!notice || notice->key != "offer_received" || offers.news.latest(1)) return 1;
            if (!offers.performForeignAction(1,0,action(hoi5::ForeignAction::trade)).empty()) return 1;
            if (offers.answerForeignOffer(1,0,false,hoi5::ForeignAction::trade) ||
                offers.incomingOffer(1,0,hoi5::ForeignAction::trade) ||
                !offers.incomingOffer(1,0,hoi5::ForeignAction::transit)) return 1;
            offers.advancePolitics(3);
            if (!offers.incomingOffer(1,0) || !offers.answerForeignOffer(1,0,true) ||
                offers.incomingOffer(1,0) || !offers.diplomacy.canTransit(1,0) ||
                offers.news.latest(0)->key != "transit" || offers.news.latest(1)->key != "transit") return 1;
            if (!offers.performForeignAction(1,0,action(hoi5::ForeignAction::alliance)).empty()) return 1;
            if (offers.answerForeignOffer(1,0,false) || offers.incomingOffer(1,0) ||
                offers.news.latest(1)->key != "offer_rejected" || offers.news.latest(0)->key != "offer_received") return 1;
        }
        if (!test.performForeignAction(0,1,action(hoi5::ForeignAction::justify)).empty()) return 1;
        const auto* justification = test.news.latest(1);
        if (!justification || justification->key != "war_justification") return 1;
        if (test.performForeignAction(0,1,action(hoi5::ForeignAction::war)).empty()) return 1;
        test.advancePolitics(30);
        const auto hasNews = [](const auto& items,int day,std::string_view key) {
            return std::ranges::any_of(items,[&](const auto* item) { return item->day == day && item->key == key; });
        };
        if (!hasNews(test.news.visible(0),30,"war_goal_ready") || hasNews(test.news.visible(1),30,"war_goal_ready"))
            return 1;
        auto expired = test;
        expired.advancePolitics(211);
        if (!expired.diplomacy.goals.empty() || !hasNews(expired.news.visible(0),211,"war_goal_expired") ||
            hasNews(expired.news.visible(1),211,"war_goal_expired")) return 1;
        test.diplomacy.countries[0].factionRadicalization[2] = .7;
        if (!test.performForeignAction(0,1,action(hoi5::ForeignAction::war)).empty()) return 1;
        const auto* declaration = test.news.latest(1);
        if (!declaration || declaration->key != "war" || declaration->priority != hoi5::NewsPriority::critical) return 1;
        if (test.diplomacy.tradeAllowed(0,1)) return 1;
        {
            auto lines = test;
            lines.divisions.resize(4);
            for (int i = 0; i < 4; ++i) {
                auto& unit = lines.divisions[i];
                unit.organization = unit.maxOrganization = 100.;
                unit.combat.width = 50.;
                unit.combat.initiative = i == 1 ? .08 : .03;
            }
            auto& flank = lines.divisions[3];
            flank.q = flank.r = 1;
            if (!lines.joinBattle(1,0) || !lines.joinBattle(1,1) || !lines.joinBattle(1,2)) return 1;
            auto& battle = lines.battles.at(1);
            if (battle.width != 80. || battle.activeAttackers != std::vector<int>{1,0} ||
                lines.divisions[0].combat.widthEfficiency != .6 ||
                lines.divisions[2].combat.widthEfficiency != 1.) return 1;
            if (!lines.joinBattle(1,3) || battle.width != 120. ||
                battle.activeAttackers != std::vector<int>{1,0}) return 1;
            auto& recovering = lines.divisions[1];
            recovering.organization = 29.;
            recovering.combat.recovering = true;
            lines.rebalanceBattle(1,battle);
            if (battle.activeAttackers != std::vector<int>{0,2} || !recovering.combat.recovering) return 1;
            recovering.organization = 30.;
            lines.rebalanceBattle(1,battle);
            if (battle.activeAttackers != std::vector<int>{1,0} || recovering.combat.recovering) return 1;
        }
        {
            World hourly;
            hourly.size = 2;
            hourly.tiles.resize(4);
            hourly.tiles[0].owner = 0;
            hourly.tiles[1].owner = 1;
            hourly.tiles[0].supply = hourly.tiles[1].supply = .6;
            hourly.diplomacy.relation(0,1).war = true;
            hourly.divisions.resize(2);
            for (int i = 0; i < 2; ++i) {
                auto& unit = hourly.divisions[i];
                unit.q = unit.owner = i;
                unit.organization = unit.maxOrganization = 100.;
                unit.combat = {};
                for (auto& [key,stock] : unit.supplies) stock = 10000.;
            }
            if (!hourly.joinBattle(1,0)) return 1;
            bool damaged = false;
            if (hourly.advanceBattles(4,damaged) || damaged || hourly.battles.at(1).advance != 0.) return 1;
            // Python apply_combat_attack on the same unfortified tile for four hourly rounds.
            if (std::abs(hourly.divisions[0].organization-79.85792) > 1e-9 ||
                std::abs(hourly.divisions[0].combat.strength-92.950272) > 1e-9 ||
                std::abs(hourly.divisions[1].organization-93.51808) > 1e-9 ||
                std::abs(hourly.divisions[1].combat.strength-97.731328) > 1e-9) return 1;
        }
        {
            World concurrent;
            concurrent.size = 3;
            concurrent.tiles.resize(9);
            concurrent.divisions.resize(6);
            concurrent.diplomacy.relation(0,1).war = true;
            concurrent.groundCombatRandom.seed(7);
            constexpr std::array positions{3,4,4,0,1,1};
            for (int i = 0; i < int(positions.size()); ++i) {
                auto& unit = concurrent.divisions[i];
                unit.owner = i%3 != 0;
                unit.q = positions[i]%3;
                unit.r = positions[i]/3;
                unit.organization = unit.maxOrganization = 100.;
                concurrent.tiles[positions[i]].owner = unit.owner;
                concurrent.tiles[positions[i]].supply = .6;
            }
            // Python Random(7) picks the second then first defender, consuming both counterattack draws in between.
            if (!concurrent.joinBattle(4,0) || !concurrent.joinBattle(1,3)) return 1;
            bool damaged = false;
            if (concurrent.advanceBattles(2,damaged) || damaged ||
                concurrent.divisions[1].organization != 100. || concurrent.divisions[5].organization != 100. ||
                std::abs(concurrent.divisions[2].organization-96.75904) > 1e-9 ||
                std::abs(concurrent.divisions[4].organization-96.75904) > 1e-9) return 1;
        }
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
        const int captureDay = test.diplomacy.day;
        if (!hasNews(test.news.visible(0),captureDay,"territory_gained") ||
            !hasNews(test.news.visible(1),captureDay,"territory_lost") ||
            hasNews(test.news.visible(0),captureDay,"territory_lost") ||
            hasNews(test.news.visible(1),captureDay,"territory_gained")) return 1;
        for (int hour = 0; hour < 60 && retreat.retreating; ++hour) test.advance(1);
        return !retreat.retreating && retreat.combat.strength > 0 && retreat.r == 1 ? 0 : 1;
    }
    if (mode == "--check-economy") {
        {
            World storage;
            storage.size = 2;
            storage.tiles.resize(4);
            storage.profiles.resize(1,{1.,1000000.,20000000.});
            storage.capitals = {0};
            storage.stockpiles = {{{"iron_ore",200000.},{"copper_ore",100000.},{"coal",500000.}}};
            storage.tiles[0].buildings[hoi5::warehouse] = {.10,1.};
            storage.tiles[1].buildings[hoi5::warehouse] = {.20,.25};
            storage.rebuildEconomy();
            const auto close = [](double a,double b) { return std::abs(a-b) < 1e-8; };
            if (!close(hoi5::value(storage.stockpiles[0],"coal"),448000.) ||
                !close(hoi5::value(storage.stockpileAtTile(0),"iron_ore"),70000.) ||
                !close(hoi5::value(storage.stockpileAtTile(1),"iron_ore"),35000.) ||
                !close(hoi5::value(storage.stockpileAtTile(0),"copper_ore"),35000.) ||
                !storage.stockpileAtTile(2).empty()) return 1;
            storage.stockpiles[0]["iron_ore"] = 15000.;
            if (!close(hoi5::value(storage.stockpileAtTile(0),"iron_ore"),10000.)) return 1;
            storage.tiles[0].owner = -1;
            storage.rebuildEconomy();
            if (!storage.stockpileAtTile(0).empty() ||
                !close(hoi5::value(storage.stockpileAtTile(1),"iron_ore"),11666.666666666666)) return 1;
        }
        if (exportSliderPercent(100) != 0 || exportSliderPercent(235) != 35 ||
            exportSliderPercent(500) != 100 || exportSliderPercent(137) != 0 ||
            exportSliderPercent(138) != 5) return 1;
        {
            World policy;
            policy.diplomacy.countries.resize(1);
            auto& state = policy.diplomacy.countries[0];
            if (policy.changeMarketPolicy(false,101.).empty() || policy.changeMarketPolicy(false,100.).empty() ||
                state.capital != 50. || !policy.changeMarketPolicy(false,35.).empty() ||
                state.exportLimit != .35 || state.capital != 48. ||
                policy.changeMarketPolicy(false,0.).empty()) return 1;
            policy.diplomacy.day = 7;
            if (!policy.changeMarketPolicy(false,0.).empty() || state.exportLimit != 0. || !state.externalAccess)
                return 1;
        }
        if (resourceDurationColor(std::nullopt) != sf::Color(170,184,198) ||
            resourceDurationColor(0.) != sf::Color(238,104,94) ||
            resourceDurationColor(1.) != sf::Color(238,198,90) ||
            resourceDurationColor(3.) != sf::Color(176,214,92) ||
            resourceDurationColor(6.) != sf::Color(112,214,132)) return 1;
        if (resourceDurationMonths(std::nullopt,0,100) ||
            resourceDurationMonths(50,100,100) || resourceDurationMonths(-5,0,100) != 0. ||
            resourceDurationMonths(50,50,150) != .5 ||
            formatResourceDuration(std::nullopt) != "--" || formatResourceDuration(0.) != "0 дн." ||
            formatResourceDuration(.2) != "6 дн." || formatResourceDuration(.21) != "1 нед." ||
            formatResourceDuration(2.1) != "3 мес." || formatResourceDuration(11.1) != "1 год" ||
            formatResourceDuration(24.1) != "3 г." || formatResourceDuration(60.) != "5 г." ||
            formatResourceDuration(60.1) != "> 5 лет") return 1;
        if (resourceShortageLevel(0,100) != 2 || resourceShortageLevel(100,100) != 1 ||
            resourceShortageLevel(300,100) != 0 || resourceShortageLevel(0,0) != 0 ||
            storageProblemLevel(88,100) != 1 || storageProblemLevel(100,100) != 2 ||
            storageProblemLevel(1,0) != 2 || storageProblemLevel(0,0) != 0) return 1;
        if (formatMoney(-1250000000.) != "-$1.2B" || formatMoney(999.) != "$999" ||
            formatMoneyDelta(12500.) != "+$12.5K" || formatMoneyDelta(0.) != "$0" ||
            formatMoneyDelta(-1200000.) != "-$1.2M") return 1;
        {
            hoi5::Market fuel;
            const std::vector<hoi5::MarketOrder> orders{{0,"refined_fuel",true,7000.}};
            const hoi5::Stockpile background{{"refined_fuel",123000.}};
            fuel.updatePrices(orders,background);
            const double first = fuel.price("refined_fuel")/fuel.base("refined_fuel")-1.;
            if (first < .030 || first > .032) return 1;
            for (int week = 1; week < 60; ++week) fuel.updatePrices(orders,background);
            const double persistent = fuel.price("refined_fuel")/fuel.base("refined_fuel")-1.;
            if (persistent < .13 || persistent > .14 || std::abs(fuel.priceChange("refined_fuel")) > .0001)
                return 1;
        }
        {
            std::vector<Tile> tiles(2);
            tiles[0].owner = 0;
            tiles[1].owner = 1;
            tiles[0].supply = tiles[1].supply = 1.;
            std::vector<hoi5::StartingProfile> profiles(2);
            profiles[0].budget = profiles[1].budget = 1e9;
            std::vector<hoi5::Stockpile> stocks(2), capacities(2);
            stocks[1]["coal"] = 1e6;
            for (auto& capacity : capacities) capacity[hoi5::storageBucket("coal")] = 1e9;
            const std::vector<hoi5::MarketOrder> contracts{{0,"coal",true,8000.},{1,"coal",false,8000.}};
            const auto run = [&](bool access) {
                hoi5::Market result;
                result.contracts = contracts;
                auto countries = profiles;
                auto reserves = stocks;
                result.execute(tiles,countries,reserves,capacities,0,
                    [=](int,int) { return access; },[](int,int) { return 0; },
                    [](int) { return true; },[](int) { return 1.; });
                return result;
            };
            const auto open = run(true);
            if (std::abs(open.countryPrice(0,"coal")-open.price("coal")) > 1e-8 ||
                std::abs(open.countryPrice(1,"coal")-open.price("coal")) > 1e-8) return 1;
            const auto embargo = run(false);
            if (embargo.countryPrice(0,"coal") <= embargo.price("coal") ||
                embargo.countryPrice(1,"coal") >= embargo.price("coal") ||
                hoi5::value(embargo.countrySupply[0],"coal") >= hoi5::value(embargo.supply,"coal") ||
                hoi5::value(embargo.countryDemand[1],"coal") >= hoi5::value(embargo.demand,"coal")) return 1;
        }
        if (formatPopulationDelta(std::nullopt) != "--" || formatPopulationDelta(0.) != "0" ||
            formatPopulationDelta(12500.) != "+12.5K" || formatPopulationDelta(-1200000.) != "-1.2M") return 1;
        {
            Tile tile{};
            tile.owner = 0;
            tile.population = 2000000.;
            tile.buildings[hoi5::city] = {.5,1.};
            tile.buildings[hoi5::industry] = {.25,.5};
            const auto flows = hoi5::monthlyTreasury(std::vector<Tile>{tile},0,2000000.);
            if (std::abs(flows.population-1062331.2883435583) > 1e-8 ||
                flows.companies != 30000. || flows.infrastructure != 95500. ||
                flows.government != 549500. || flows.army != 0.) return 1;
            World upkeep;
            upkeep.profiles.resize(1);
            upkeep.diplomacy.countries.resize(1);
            upkeep.treasury.resize(1);
            upkeep.divisions.resize(1);
            upkeep.divisions[0].owner = 0;
            upkeep.divisions[0].manpower = 100000;
            if (upkeep.taxedTreasury(0).army != 800000. || upkeep.taxedTreasury(0).balance() != -1250000.)
                return 1;
            Tile village{};
            village.owner = 0;
            village.population = 1000000.;
            village.buildings[hoi5::village] = {1.25,.25};
            Tile foreign = village;
            foreign.owner = 1;
            const auto social = hoi5::monthlyTreasury(std::vector<Tile>{tile,village,foreign},0,3000000.);
            if (std::abs(social.pensions-110400.) > 1e-8 ||
                std::abs(social.children-69000.) > 1e-8 || social.disability != 6600. ||
                social.localServices != 98000. || std::abs(social.social-284000.) > 1e-8) return 1;
        }
        {
            World policy;
            policy.diplomacy.countries.resize(1);
            policy.profiles.resize(1,{1,21000000,250000000});
            policy.countryNames[0] = "Player";
            if (!policy.changeSupportProgram(0,3,24).empty()) return 1;
            if (policy.diplomacy.programExpenses(0) != 1000000.) return 1;
            const double beforeFunding = policy.profiles[0].budget;
            const auto* started = policy.news.latest(0);
            if (!started || started->key != "program_start") return 1;
            policy.advance(24);
            if (policy.diplomacy.programExpenses(0) != 0. ||
                std::abs(beforeFunding-policy.profiles[0].budget-1000000./30.) > 1e-7) return 1;
            const auto* expired = policy.news.latest(0);
            if (!expired || expired->key != "program_expired" || expired->day != 1 || policy.news.latest(1)) return 1;
            if (!policy.changeSupportProgram(0,3,24).empty() || !policy.changeSupportProgram(0,3,24).empty() ||
                policy.news.latest(0)->key != "program_stop") return 1;
            if (!policy.changeSupportProgram(0,3,48).empty()) return 1;
            policy.profiles[0].budget = 25000.;
            policy.advancePoliticsHours(18);
            const auto& state = policy.diplomacy.countries[0];
            if (policy.diplomacy.day != 1 || policy.politicsHours != 18 || policy.profiles[0].budget != 0. ||
                state.programFunding[3] != 1.) return 1;
            policy.advancePoliticsHours(6);
            if (policy.diplomacy.day != 2 || policy.politicsHours != 0 || state.programHours[3] != 24. ||
                state.programFunding[3] != .75 || state.programFunded[3] != 0.) return 1;
        }
        {
            hoi5::News alerts;
            const auto warn = [&](int day,bool active) {
                alerts.alert(day,0,"Player","treasury_empty",active,"Казна исчерпана",
                    "Средств в казне нет.","В казне снова появились средства");
            };
            warn(1,false);
            warn(2,true);
            warn(3,true);
            warn(4,false);
            const auto visible = alerts.visible(0);
            if (visible.size() != 2 || visible[0]->day != 4 || visible[0]->important() ||
                visible[1]->day != 2 || !visible[1]->important() || !alerts.visible(1).empty()) return 1;
            hoi5::Production production;
            production[hoi5::semiFinished].inputs["coal"] = 8;
            hoi5::Stockpile stocks{{"coal",3}};
            const auto ratios = hoi5::runProduction(production,stocks,720,[](auto,double) {});
            if (ratios[hoi5::semiFinished] != .375 || stocks.at("coal") != 0.) return 1;
        }
        for (bool restricted : {false,true}) {
            hoi5::News randomNews(921);
            randomNews.advance(500,{restricted ? 2. : 1.,restricted});
            randomNews.advance(1000,{restricted ? 2. : 1.,restricted});
            const auto items = randomNews.visible(0);
            std::uint32_t hash = 2166136261u;
            for (const auto* item : items)
                for (unsigned char ch : std::to_string(item->day)+":"+std::string(item->key)+"\n")
                    hash = (hash^ch)*16777619u;
            if (items.size() != (restricted ? 74 : 66) ||
                hash != (restricted ? 468941039u : 552086983u)) return 1;
        }
        hoi5::News tradeNews;
        tradeNews.recordTrade(2,{0,1,"coal",200000,34},
            [](int country) { return country == 0 ? "Player" : "Seller"; },resourceDisplayName);
        const auto* report = tradeNews.latest(0);
        if (!report || report->body.find("200.0K ед. товара. Стоимость сделки — $6.8M.") == std::string::npos)
            return 1;
        auto generated = generateWorld(50, 2, 823558, 1);
        if (generated.air.bases.empty() || generated.air.defense.empty()) return 1;
        const int reserve = generated.air.reserves[0][0];
        if (generated.air.createWing(generated.tiles,0,0,4) < 0 || generated.air.reserves[0][0] != reserve-4) return 1;
        const double before = generated.stockpiles[0].at("consumer_goods");
        generated.advance(24);
        if (generated.stockpiles[0].at("consumer_goods") == before) return 1;
        const double budget = generated.profiles[0].budget;
        const double monthlyTradeLimit = hoi5::Market::monthlyCapacity(generated.tiles,generated.profiles)[0];
        if (!generated.market.changeContract(0,"coal",false,1500,monthlyTradeLimit*2) ||
            !generated.market.changeContract(0,"coal",true,500,monthlyTradeLimit) ||
            generated.market.contractAmount(0,"coal",false) != 1000 ||
            generated.market.contractAmount(0,"coal",true) != 0) return 1;
        {
            hoi5::Market market;
            auto profiles = generated.profiles;
            auto stocks = generated.stockpiles;
            profiles[0].budget = 2160;
            stocks[0]["coal"] = 0;
            market.prices["coal"] = 68;
            if (!market.changeContract(0,"coal",true,1000,200) ||
                market.contractAmount(0,"coal",true) != 200 ||
                market.changeContract(0,"oil",true,1000,200)) return 1;
            market.execute(generated.tiles,profiles,stocks,generated.capacities,0,
                [](int,int) { return false; },[](int,int) { return 0; },
                [](int) { return true; },[](int) { return 1.; });
            const auto capacities = hoi5::Market::monthlyCapacity(generated.tiles,profiles);
            double total = 0;
            for (double capacity : capacities) total += 3*capacity*hoi5::Market::weeklyFraction;
            const double expectedQuota = std::max(750.,total*std::max(.05,
                hoi5::value(hoi5::MARKET_RESOURCE_RARITY,"coal",.45))*.55);
            if (std::abs(market.externalDemand.at("coal")-expectedQuota) > 1e-8 ||
                (market.price("coal") <= 34 || market.price("coal") >= 68)) return 1;
            const double ordered = 2160/(68*hoi5::Market::buyMarkup);
            if (market.last.fills.size() != 1 || std::abs(market.last.fills.front().amount-ordered) > 1e-8 ||
                std::abs(market.last.fills.front().price-market.unitPrice(0,"coal",true)) > 1e-8 ||
                std::abs(market.demand.at("coal")-market.externalDemand.at("coal")-ordered) > 1e-8 ||
                market.revision != 1 || market.previousPrices.at("coal") != 68 || market.history.at("coal").size() != 1 ||
                !market.unfilled.empty()) return 1;
            hoi5::Market restricted;
            restricted.changeContract(0,"coal",true,1000,200);
            auto restrictedProfiles = generated.profiles;
            auto restrictedStocks = generated.stockpiles;
            restricted.execute(generated.tiles,restrictedProfiles,restrictedStocks,generated.capacities,0,
                [](int,int) { return false; },[](int,int) { return 0; },
                [](int country) { return country == 0; },[](int) { return 1.; });
            if (restricted.externalDemand.at("coal") >= market.externalDemand.at("coal")) return 1;
        }
        const double coal = generated.stockpiles[0].at("coal");
        const auto stocksBeforeForecast = generated.stockpiles;
        const auto forecast = generated.forecastResources(0,0);
        if (hoi5::value(forecast.exports,"coal") <= 0 ||
            hoi5::value(forecast.inputs,"coal") < hoi5::value(forecast.exports,"coal") ||
            generated.stockpiles != stocksBeforeForecast || generated.profiles[0].budget != budget) return 1;
        generated.updateEconomyHistory(31*24-1,0);
        if (generated.economyCurrent.size() != generated.profiles.size() || generated.economyCurrent.front().trade <= 0 ||
            generated.profiles[0].budget != budget || generated.stockpiles[0].at("coal") != coal) return 1;
        const auto january = generated.economyCurrent;
        generated.profiles[1].budget += 1000.;
        generated.updateEconomyHistory(31*24,0);
        if (generated.economyPrevious.size() != january.size() ||
            generated.economyPrevious[0].trade != january[0].trade ||
            generated.economyPrevious[1].budget != january[1].budget ||
            generated.economyCurrent[1].budget != january[1].budget+1000.) return 1;
        generated.diplomacy.countries[0].externalAccess = false;
        generated.executeWeeklyMarket(1);
        const auto* incomplete = generated.news.latest(0);
        if (!generated.market.last.fills.empty() || !incomplete || !incomplete->important() ||
            generated.news.latest(1)) return 1;
        generated.executeWeeklyMarket(2);
        if (generated.news.latest(0) != incomplete) return 1;
        generated.diplomacy.countries[0].externalAccess = true;
        generated.executeWeeklyMarket(3);
        const auto* recovered = generated.news.latest(0);
        return generated.market.last.fills.size() == 1 && generated.profiles[0].budget > budget &&
            recovered && recovered != incomplete && !recovered->important() ? 0 : 1;
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
    if (mode == "--check-map") {
        if (world.size != 50 || world.divisions.size() != 20 || world.status.size() != 7) return 1;
        World politics;
        politics.size = 2;
        politics.tiles.resize(4);
        politics.diplomacy.countries.resize(4);
        const std::array colors{sf::Color::Green,sf::Color::Magenta,sf::Color::Cyan,sf::Color::Yellow};
        for (int i = 0; i < 4; ++i) {
            politics.tiles[i].owner = i;
            politics.tiles[i].border = colors[i];
        }
        politics.diplomacy.relation(0,1).treaties.insert(hoi5::ForeignAction::alliance);
        politics.diplomacy.relation(1,2).treaties.insert(hoi5::ForeignAction::alliance);
        politics.diplomacy.relation(0,3).war = true;
        const auto countries = makeMap(politics,MapLayer::political,0,PoliticalMapFilter::countries);
        const auto alliances = makeMap(politics,MapLayer::political);
        const auto relations = makeMap(politics,MapLayer::political,0,PoliticalMapFilter::relations);
        if (countries[18].color != colors[1] || alliances[18].color != colors[0] ||
            alliances[36].color != colors[0] || alliances[54].color != colors[3] ||
            relations[18].color != sf::Color{87,162,105} || relations[36].color != sf::Color{139,151,163} ||
            relations[54].color != sf::Color{193,63,60} || !politics.diplomacy.canTransit(0,1) ||
            politics.diplomacy.canTransit(0,2)) return 1;
        politics.diplomacy.relation(0,1).treaties.clear();
        return makeMap(politics,MapLayer::political)[18].color == colors[1] ? 0 : 1;
    }
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
    const bool tradeSmoke = mode == "--smoke-trade";
    const bool wingCreationSmoke = mode == "--smoke-wing-creation";
    const bool countrySmoke = mode == "--smoke-diplomacy";
    const bool armySmoke = mode == "--smoke-army";
    const bool warningSmoke = mode == "--smoke-warnings";
    const bool inspectBattle = mode == "--inspect-battle";
    const bool inspectNews = mode == "--inspect-news";
    if (!mode.empty() && !constructionSmoke && !resourcesSmoke && !tradeSmoke && !wingCreationSmoke && !countrySmoke &&
        !armySmoke && !warningSmoke && !inspectBattle && !inspectNews &&
        mode != "--smoke-window" && mode != "--smoke-generation" &&
        !(mode == "--check-settings-window" && argc == 3)) {
        std::cerr << "Unknown or incomplete command: " << mode << '\n';
        return 2;
    }
    if (constructionSmoke || resourcesSmoke || tradeSmoke || wingCreationSmoke || countrySmoke || armySmoke || warningSmoke ||
        inspectBattle || inspectNews)
        world = generateWorld(50,countrySmoke ? 3 : 2,823558,1);
    if (constructionSmoke) {
        auto& queue = world.construction.queues[0];
        queue.clear();
        const int tile = world.capitals[0];
        queue.push_back({tile,0,0.,.2,1800.,1200000.,{{"construction_goods",2400.}},.37,true,false,false,
            {{"construction_goods",888.}}, {},0.,hoi5::ConstructionStatus::building});
        queue.push_back({tile,6,0.,.15,2400.,1800000.,{{"steel",3200.}},.18,true,false,false,
            {{"steel",576.}},{{"steel",400.}},0.,hoi5::ConstructionStatus::waitingResources});
        queue.push_back({tile,10,0.,.25,1500.,900000.,{{"construction_goods",1600.}},0.,false,false,false,
            {},{},250000.,hoi5::ConstructionStatus::waitingMoney});
    }
    if (warningSmoke) {
        world.stockpiles[0].clear();
        world.stockpiles[0]["coal"] = 2*hoi5::value(world.capacities[0],"fuel")+1;
        world.stockpiles[0]["field_supplies"] = 1.;
        for (auto& unit : world.divisions)
            if (unit.owner == 0) unit.supplies["field_supplies"] = 0.;
        world.humanSupply = {.3,2,4};
        world.market.contracts.push_back({0,"steel",true,1e8});
        world.construction.queues[0].push_back({world.capitals[0],0,0.,.05,100.,world.profiles[0].budget+1e6,{}});
        world.news.recordBattleLoss(0,1,0,0,world.countryNames[0],world.countryNames[1],12.);
        world.news.batchNotice(0,0,"aircraft_losses","Потери авиации","Авиакрыло потеряло 4 самолёта.",true,4);
        world.news.flushNotices();
    }
    if (inspectNews) {
        world.news.recordTrade(2,{0,1,"coal",200000,34},
            [&](int i) { return world.countryNames[i]; },resourceDisplayName);
        world.news.reportIncompleteTrade(9,0,world.countryNames[0],"Уголь, нефть");
    }
    if (wingCreationSmoke && world.air.createWing(world.tiles,0,0,2) < 0) return 1;
    if (inspectBattle) {
        const int origin = world.capitalR*world.size+world.capitalQ;
        int destination = -1;
        for (int i = 0; i < int(world.tiles.size()); ++i)
            if (!world.tiles[i].water && hoi5::airHexDistance(i,origin,world.size) == 1) {
                destination = i;
                break;
            }
        if (destination < 0) return 1;
        world.tiles[destination].owner = 1;
        world.diplomacy.relation(0,1).war = true;
        world.divisions.assign(6,{});
        for (int i = 0; i < int(world.divisions.size()); ++i) {
            auto& unit = world.divisions[i];
            unit.owner = i == 5 ? 1 : 0;
            const int position = unit.owner ? destination : origin;
            unit.q = position%world.size;
            unit.r = position/world.size;
            unit.maxOrganization = 100.;
            unit.organization = 85.-5.*i;
        }
        for (int i = 0; i < 5; ++i)
            if (!world.joinBattle(destination,i)) return 1;
    }
    constexpr std::array<sf::Vector2u,5> resolutions{{{1024,768},{1200,800},{1366,768},{1600,900},{1920,1080}}};
    const bool generationSmoke = mode == "--smoke-generation";
    const bool smoke = mode == "--smoke-window" || generationSmoke || constructionSmoke || resourcesSmoke || tradeSmoke ||
        wingCreationSmoke || countrySmoke || armySmoke || warningSmoke;
    const bool settingsCheck = mode == "--check-settings-window" && argc == 3;
    const auto settingsPaths = hoi5::settingsFiles(directory);
    const auto readPath = settingsCheck ? std::filesystem::path(argv[2]) : settingsPaths.latest();
    auto settings = smoke || inspectBattle || inspectNews ? hoi5::Settings{} : hoi5::loadSettings(readPath,int(resolutions.size()));
    const auto createWindow = [&](sf::RenderWindow& target,int resolution,bool fullscreen) {
        const sf::VideoMode video(resolutions[resolution]);
        const std::string title = "HOI5 "+std::string(gameVersion);
        if (fullscreen) {
            target.create(sf::VideoMode::getDesktopMode(),title,sf::Style::Default,sf::State::Fullscreen);
            if (target.isOpen()) return true;
        }
        target.create(video,title);
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
    if (!smoke && !inspectBattle && !inspectNews &&
        (fullscreen != requestedFullscreen || settings.resolution != requestedResolution)) {
        settings.fullscreen = fullscreen;
        if (!hoi5::saveSettings(settingsPaths,settings))
            std::cerr << "Could not save HOI5 settings: " << settingsPaths.preferred << " or " << settingsPaths.portable << '\n';
    }
    if (smoke) window.setVisible(false);
    window.setVerticalSyncEnabled(true);
    sf::Font font;
    const char* windows = std::getenv("WINDIR");
    if (!windows || !font.openFromFile(std::filesystem::path(windows) / "Fonts/segoeui.ttf"))
        throw std::runtime_error("Could not open Segoe UI");
    // Keep one Cyrillic-capable face across the interface. Mixing fonts made
    // adjacent captions look blurred and shifted at the same nominal size.
    const auto& cardFont = font;
    font.setSmooth(true);
    std::array<sf::Texture, 8> icons;
    const std::array names{"politics", "economy", "resources", "trade", "construction", "research", "diplomacy", "military"};
    for (std::size_t i = 0; i < names.size(); ++i) {
        const auto path = source / "assets/ui_icons" / (std::string(names[i]) + ".png");
        if (!icons[i].loadFromFile(path))
            throw std::runtime_error("Could not open navigation icon: "+path.string());
    }
    sf::Texture layers;
    if (!layers.loadFromFile(source / "assets/layers_icon.png")) throw std::runtime_error("Could not open layers icon");
    constexpr std::array terrainFiles{"forest","grassland","desert","mountains","snowfield"};
    constexpr std::array terrainWeights{1.05,.92,1.02,1.12,1.02};
    struct BuildingVisual { hoi5::Building building; const char* file; double weight; };
    constexpr BuildingVisual buildingVisuals[] = {
        {hoi5::city,"city",1.45},{hoi5::village,"village",1.08},{hoi5::warehouse,"warehouse",1.16},
        {hoi5::supplyDepot,"warehouse",1.18},{hoi5::port,"port",1.4},{hoi5::fuelStorage,"fuel_storage",1.14},
        {hoi5::refinery,"refinery",1.15},{hoi5::oilGasRig,"refinery",1.13},{hoi5::industry,"industry",1.3},
        {hoi5::farms,"farms",1.22},{hoi5::mine,"mine",1.2},{hoi5::fortification,"warehouse",1.}
    };
    std::map<std::string_view,sf::Texture> tileTextures;
    const auto loadTileTexture = [&](std::string_view key) {
        if (tileTextures.contains(key)) return;
        auto& texture = tileTextures[key];
        if (!texture.loadFromFile(source/"assets/tile_visuals"/(std::string(key)+".png")))
            throw std::runtime_error("Could not open tile icon: "+std::string(key));
        texture.setSmooth(true);
    };
    for (const auto* key : terrainFiles) loadTileTexture(key);
    for (const auto& visual : buildingVisuals) loadTileTexture(visual.file);
    auto map = makeMap(world);
    auto borders = makeBorders(world);
    float zoom = 1.f;
    sf::View camera = window.getDefaultView();
    auto target = center(world.capitalQ, world.capitalR);
    camera.setCenter(target);
    bool playing = mode == "--smoke-window" || constructionSmoke || resourcesSmoke || tradeSmoke ||
        wingCreationSmoke || countrySmoke || armySmoke || warningSmoke || inspectBattle || inspectNews;
    bool dragging = false;
    bool setup = false, pauseMenu = false;
    sf::FloatRect populationHoverRect,budgetHoverRect,resourceHoverRect;
    std::array<std::vector<std::string_view>,2> resourceProblems;
    enum class WarningAction { resources, supply, trade, construction, news, diplomacy };
    struct TopWarning {
        std::string label, title;
        std::vector<std::string> lines;
        WarningAction action;
        bool critical;
        int newsId{};
        int country{-1};
    };
    std::vector<TopWarning> topWarnings;
    std::vector<sf::IntRect> warningBounds;
    std::array<int,2> acknowledgedLosses{};
    MapLayer mapLayer = MapLayer::terrain;
    auto politicalFilter = PoliticalMapFilter::alliances;
    std::uint64_t mapPoliticsRevision{};
    int mapPoliticsDay = -1;
    const auto mapFilterCount = [&] {
        if (mapLayer == MapLayer::political) return int(politicalMapLabels.size());
        if (mapLayer == MapLayer::resources) return int(std::size(resourceMapGroups));
        return 0;
    };
    bool mapLayerMenu = false, airDefenseOverlay = false;
    float mapLayerProgress = 0;
    int resourceGroup = 0;
    bool resourceGroupMenu = false;
    float resourceGroupProgress = 0;
    sf::Clock weatherMessage;
    bool showWeatherMessage = false;
    bool resumable = false;
    enum class MenuPage { main, settings, help };
    MenuPage menuPage = MenuPage::main;
    float musicVolume = settings.musicVolume, soundVolume = settings.soundVolume;
    int resolution = settings.resolution, pendingResolution = resolution;
    bool pendingFullscreen = fullscreen, resolutionOpen = false;
    int activeSlider = -1;
    hoi5::SimulationClock simulation;
    hoi5::NewsPanel newsPanel;
    auto& paused = simulation.paused;
    auto& speed = simulation.speed;
    std::vector<int> selectedTiles;
    float hexScroll = 0;
    bool hexResourcesExpanded = false;
    sf::FloatRect hexResourcesToggle;
    bool hexSpecializationMode = false;
    sf::FloatRect hexSpecializationButton;
    std::vector<std::pair<sf::FloatRect,std::string_view>> hexSpecializationRows;
    std::vector<std::pair<sf::FloatRect,int>> defenseMoveButtons;
    int movingDefense = -1;
    std::set<int> selectedDefense;
    std::set<int> selectedDivisions;
    std::optional<sf::Vector2i> divisionDragStart;
    bool divisionDragActive = false, pendingHexShift = false;
    int pendingHexTile = -1, lastDivisionClick = -1;
    sf::Clock divisionClickClock;
    const auto divisionDragRect = [](sf::Vector2i start,sf::Vector2i end) {
        return sf::FloatRect({float(std::min(start.x,end.x)),float(std::min(start.y,end.y))},
            {float(std::abs(end.x-start.x)),float(std::abs(end.y-start.y))});
    };
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
    bool tradePanel = tradeSmoke;
    int tradeScroll = 0, tradeCategory = 0;
    constexpr int tradeTop = 94, tradeWidth = 900, tradeRowTop = tradeTop+266, tradeRowHeight = 52;
    constexpr std::array tradeButtons{760,790,830,860};
    const auto tradeRows = [&] { return std::max(1,(int(window.getSize().y)-12-tradeTop-310)/tradeRowHeight); };
    const auto tradeBounds = [&] {
        return sf::IntRect({0,tradeTop},{tradeWidth,std::max(0,int(window.getSize().y)-tradeTop-12)});
    };
    const auto tradeCategoryRect = [](int category) {
        return sf::IntRect({18+230*category,tradeTop+158},{220,40});
    };
    const sf::IntRect tradeClose({tradeWidth-38,tradeTop+10},{28,28});
    std::optional<World::ResourceForecast> tradeForecast;
    double tradeMonthly = 0.;
    bool diplomacyPanel = false, aircraftPanel = wingCreationSmoke;
    int selectedWing = -1;
    int editingWing = -1;
    int targetingWing = -1;
    constexpr std::pair<std::string_view,std::string_view> airTargetOptions[]{
        {"enemy_units","Войска"},{"supply_infrastructure","Снабжение"},{"infrastructure","Инфраструктура"},
        {"civilian_infrastructure","Гражданская"},{"industry","Заводы"},{"bases","Базы"},
        {"airbases","Аэродромы"},{"air_defense","ПВО/РЛС"}
    };
    constexpr int airTargetMenuHeight = 38+27*(1+int(std::size(airTargetOptions)));
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
    const auto wingListBounds = [&](int count) {
        const int top = wingGridTop(count)-34;
        return sf::IntRect({10,top},{420,int(window.getSize().y)-14-top});
    };
    float airDockX = 0.f, airDockScale = 1.f;
    const auto localAirPoint = [&](sf::Vector2i point) {
        const float bottom = float(window.getSize().y);
        return sf::Vector2f{(point.x-airDockX)/airDockScale,bottom+(point.y-bottom)/airDockScale};
    };
    const auto wingCardRect = [&](int index,int count) {
        return sf::FloatRect({20.f+81.f*(index%5),float(wingGridTop(count)+55*(index/5))},{74,48});
    };
    const auto wingCreationBottom = [&] { return wingGridTop(int(wingCards().size()))-42; };
    bool wingCreationOpen = wingCreationSmoke;
    int wingCreationType = -1, wingCreationCount = 1;
    int missionMenuWing = -1, riskMenuWing = -1;
    bool draggingWingCount = false;
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
    bool wingRebaseMode = false, wingAreaMode = false;
    const auto editWingArea = [&](int tile,World::AirAreaEdit edit) {
        if (tile < 0 || selectedWings.empty()) return false;
        if (edit != World::AirAreaEdit::remove && !std::ranges::all_of(selectedWings,[&](int index) {
            return world.airWingCanReach(world.air.wings[index],tile);
        })) return false;
        bool changed = false;
        for (int index : selectedWings)
            changed |= world.assignAirWingTarget(world.air.wings[index],tile,edit);
        return changed;
    };
    bool constructionPanel = constructionSmoke, militaryPanel = false;
    int economicPanel = resourcesSmoke ? 2 : 0, resourceScroll = 0;
    std::optional<World::ResourceForecast> resourceForecast;
    int resourceCategory = 0;
    constexpr int resourceRowsTop = 398, resourceRowHeight = 26;
    const auto resourcePanelBottom = [&] { return std::max(514,int(window.getSize().y)-12); };
    const auto resourceVisibleRows = [&] {
        return std::max(8,(resourcePanelBottom()-26-resourceRowsTop)/resourceRowHeight);
    };
    constexpr int resourceWarningsTop = 304, resourceWarningHeight = 20;
    std::vector<std::pair<int,std::string_view>> resourceWarnings;
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
    const auto resourceCardRect = [&] {
        return sf::FloatRect({528,144},{214,float(resourcePanelBottom()-202)});
    };
    const auto resourceCardClose = [&] {
        const auto card = resourceCardRect();
        return sf::FloatRect(card.position+sf::Vector2f{card.size.x-32,10},{24,24});
    };
    const auto resourceCardTrade = [&] {
        const auto card = resourceCardRect();
        return sf::FloatRect(card.position+sf::Vector2f{12,card.size.y-40},{card.size.x-24,28});
    };
    bool resourceMapDirty = true;
    sf::VertexArray resourceMap(sf::PrimitiveType::Triangles);
    std::vector<double> mapResourceAmounts;
    double mapResourceScale = 500000;
    float economyPanelProgress = 0;
    constexpr std::array supportTerms{"Неделя","30 дней","365 дней","До отмены"};
    constexpr std::array supportHours{7*24,30*24,365*24,-1};
    int supportTerm = 3;
    int pendingExport = -1;
    bool draggingExport = false;
    std::string militaryMessage;
    enum class ArmyTab { overview, designer, recruit };
    ArmyTab armyTab = ArmyTab::overview;
    hoi5::DivisionComposition armyDraft{10};
    sf::String armyDesignName = U"Новая дивизия";
    bool armyNameFocus = false, armyPickingSite = false;
    float armyPanelProgress = 0.;
    int armyType = 0, armySite = -1, armyProject = 0, armyPage = 0, armyScroll = 0, armyScrollMax = 0;
    struct ArmyHit { sf::IntRect rect; std::function<void()> activate; };
    std::vector<ArmyHit> armyHits;
    std::vector<ArmyHit> armyCommandHits;
    std::vector<std::pair<sf::IntRect,int>> divisionListHits;
    sf::IntRect armyCommandBounds, divisionListBounds;
    int activeArmy = -1, divisionListScroll = 0, divisionListScrollMax = 0;
    enum class FrontMode { none, automatic, custom, defense, offensive };
    FrontMode frontMode = FrontMode::none;
    int drawingFrontArmy = 0, previewOpponent = -2;
    bool frontDrag = false;
    std::vector<int> frontPreview;
    const auto cancelFrontDrawing = [&] {
        frontMode = FrontMode::none;
        frontDrag = false;
        frontPreview.clear();
    };
    const auto extendFrontPreview = [&](int tile) {
        const auto allowed = [&](int cell) {
            if (frontMode == FrontMode::offensive)
                return cell >= 0 && cell < int(world.tiles.size()) && !world.tiles[cell].water && world.tiles[cell].owner != 0;
            return world.frontLand(0,cell) &&
                (frontMode == FrontMode::defense || world.bordersFrontOwner(0,cell,previewOpponent));
        };
        if (frontPreview.empty()) {
            previewOpponent = frontMode == FrontMode::custom ? world.frontBorderOwner(0,tile) : -2;
            if (allowed(tile)) frontPreview.push_back(tile);
            return;
        }
        if (!allowed(tile) || std::ranges::find(frontPreview,tile) != frontPreview.end()) return;
        const auto steps = world.landRoute(frontPreview.back(),tile,allowed);
        for (const int step : steps)
            if (std::ranges::find(frontPreview,step) == frontPreview.end()) frontPreview.push_back(step);
    };
    const auto syncArmySelection = [&] {
        selected = selectedDivisions.empty() ? -1 : *selectedDivisions.begin();
        if (!selectedDivisions.empty()) selectedTiles.clear();
        else {
            activeArmy = -1;
            divisionListScroll = 0;
        }
    };
    const auto armyBounds = [&] {
        return sf::IntRect({int((armyPanelProgress-1)*500),94},{500,int(window.getSize().y)-106});
    };
    int buildingSpec = 0;
    bool constructionPlacement = constructionSmoke, constructionQueueExpanded = false;
    bool constructionMapDirty = true;
    const auto refreshMapLayer = [&] {
        map = makeMap(world,mapLayer,resourceGroup,politicalFilter);
        mapPoliticsRevision = world.diplomacy.revision;
        mapPoliticsDay = world.diplomacy.day;
        resourceMapDirty = constructionMapDirty = true;
    };
    const auto setMapLayer = [&](MapLayer layer) {
        mapLayer = layer;
        resourceGroupMenu = false;
        refreshMapLayer();
    };
    sf::VertexArray constructionMap(sf::PrimitiveType::Triangles);
    std::vector<double> constructionCoverage;
    std::vector<sf::String> constructionLabels;
    constexpr int constructionPanelWidth = 580, constructionListTop = 164, constructionRowHeight = 32;
    const auto constructionPriorityButton = [](int row,int direction) {
        return sf::FloatRect({direction < 0 ? 510.f : 536.f,float(constructionListTop+3+constructionRowHeight*row)},{22,22});
    };
    const auto constructionCancelButton = [](int row) {
        return sf::FloatRect({480.f,float(constructionListTop+3+constructionRowHeight*row)},{22,22});
    };
    const auto constructionRows = [&](int groups) {
        const int limit = constructionQueueExpanded ? std::max(4,(int(window.getSize().y)-680)/constructionRowHeight+4) : 4;
        return std::min(groups,limit);
    };
    std::string constructionMessage;
    std::string aviationMessage;
    enum class CountryTab { summary, society, trade, actions, history };
    enum class CountryDetail { none, power, population, support, taxes, programs, exportLimit, externalMarket, taxDecision, programDecision };
    CountryDetail countryDetail = CountryDetail::none;
    int domesticGroup = 0, domesticTaxDelta = 0, savedCountryDialogScroll = 0;
    sf::IntRect countryExportSlider;
    int countryDialogScroll = 0, countryDialogMaxScroll = 0;
    int foreignTarget = 0, countryScroll = 0, countryScrollMax = 0;
    bool countryList = true;
    float countryPanelProgress = 0.f;
    CountryTab countryTab = CountryTab::summary;
    sf::FloatRect countrySummaryButton, hexCountryButton;
    std::string foreignMessage;
    struct CountryHit { sf::IntRect rect; std::function<void()> activate; };
    std::vector<CountryHit> countryHits;
    const auto countryBounds = [&] {
        const auto size = sf::Vector2i(window.getSize());
        const int width = std::min(560,size.x-24);
        return sf::IntRect({int((countryPanelProgress-1)*width),94},{width,std::max(0,size.y-106)});
    };
    const auto sidePanelRight = [&] {
        if (diplomacyPanel) return std::max(0,countryBounds().position.x+countryBounds().size.x);
        if (militaryPanel) return std::max(0,armyBounds().position.x+armyBounds().size.x);
        if (economicPanel == 1) return int(620*economyPanelProgress);
        if (economicPanel == 2 || tradePanel) return 760;
        if (constructionPanel) return 460;
        return 0;
    };
    const auto openCountryList = [&] {
        countryList = true;
        countryScroll = 0;
        countryHits.clear();
        foreignMessage.clear();
    };
    const auto openDiplomacy = [&] {
        diplomacyPanel = true;
        tradePanel = constructionPanel = militaryPanel = false;
        constructionPlacement = false;
        constructionMapDirty = true;
        economicPanel = 0;
        dragging = divisionDragActive = false;
        divisionDragStart.reset();
    };
    const auto openCountry = [&](int country) {
        foreignTarget = country;
        openCountryList();
        countryList = false;
        openDiplomacy();
    };
    const hoi5::ForeignActionInfo* countryDecision = nullptr;
    std::string countryDecisionAmount = "5000000", countryDecisionError;
    std::vector<CountryHit> countryDecisionHits;
    const auto hasDecisionAmount = [&] {
        return countryDecision == &hoi5::foreignAid || countryDecision == &hoi5::foreignLoan;
    };
    const auto countryModalOpen = [&] { return countryDecision || countryDetail != CountryDetail::none; };
    const auto openCountryDetail = [&](CountryDetail detail) {
        countryDetail = detail;
        countryDialogScroll = 0;
        countryDecisionError.clear();
        countryDecisionHits.clear();
        countryExportSlider = {};
        draggingExport = false;
    };
    const auto closeCountryDetail = [&] {
        const auto previous = countryDetail;
        countryDecision = nullptr;
        openCountryDetail(previous == CountryDetail::taxDecision ? CountryDetail::taxes :
            previous == CountryDetail::programDecision ? CountryDetail::programs : CountryDetail::none);
        if (countryDetail != CountryDetail::none) countryDialogScroll = savedCountryDialogScroll;
    };
    const auto updateCountryExport = [&](int mouseX) {
        pendingExport = exportSliderPercent(mouseX,countryExportSlider.position.x,std::max(1,countryExportSlider.size.x));
        countryDecisionHits.clear();
    };
    const auto applyDomesticDecision = [&] {
        switch (countryDetail) {
            case CountryDetail::exportLimit: countryDecisionError = world.changeMarketPolicy(false,pendingExport); break;
            case CountryDetail::externalMarket: countryDecisionError = world.changeMarketPolicy(true); break;
            case CountryDetail::taxDecision: countryDecisionError = world.changeTax(0,domesticGroup,domesticTaxDelta); break;
            case CountryDetail::programDecision:
                countryDecisionError = world.changeSupportProgram(0,domesticGroup,supportHours[supportTerm]);
                break;
            default: return;
        }
        countryDecisionHits.clear();
        if (!countryDecisionError.empty()) return;
        closeCountryDetail();
        foreignMessage = "Решение принято";
        tradeForecast.reset();
        resourceForecast.reset();
        world.updateEconomyHistory(simulation.elapsedHours,simulation.marketTickCount);
        world.updateStatus();
    };
    const auto amountValue = [&] { return countryDecisionAmount.empty() ? 0LL : std::stoll(countryDecisionAmount); };
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
        sf::FloatRect panel({size.x-width-16,size.y-bottom-height},{width,height});
        if (armyCommandBounds.size.x > 0) {
            const sf::FloatRect army(sf::Vector2f(armyCommandBounds.position),sf::Vector2f(armyCommandBounds.size));
            if (const auto overlap = panel.findIntersection(army))
                panel.position.y = std::max(top,panel.position.y-overlap->size.y-8.f);
        }
        return panel;
    };
    const auto hexCloseRect = [](sf::FloatRect panel) {
        return sf::FloatRect(panel.position+sf::Vector2f(panel.size.x-36,12),{24,24});
    };
    const auto defensePixel = [&](const hoi5::AirDefense& unit) {
        return sf::Vector2f(window.mapCoordsToPixel(defenseIconPosition(world,unit),camera));
    };
    const auto canSelectDefense = [](const hoi5::AirDefense& unit) {
        return unit.owner == 0 && unit.id >= 0 && unit.health > 0;
    };
    const auto selectDefense = [&](sf::FloatRect area,bool shift) {
        if (!shift) selectedDefense.clear();
        for (const auto& unit : world.air.defense) {
            if (canSelectDefense(unit) && area.contains(defensePixel(unit)) &&
                (!shift || !selectedDefense.erase(unit.id))) selectedDefense.insert(unit.id);
        }
        if (!selectedDefense.empty()) {
            selectedDivisions.clear();
            selected = -1;
            selectedTiles.clear();
        }
    };
    const auto orderSelectedDefense = [&](int tile) {
        int accepted = 0, total = 0;
        std::string firstError;
        for (auto& unit : world.air.defense) {
            if (!canSelectDefense(unit) || !selectedDefense.contains(unit.id)) continue;
            ++total;
            bool success;
            auto message = world.orderAirDefenseMove(unit,tile,&success);
            accepted += success;
            if (!success && firstError.empty()) firstError = std::move(message);
        }
        aviationMessage = "ПВО: приказ принят "+std::to_string(accepted)+"/"+std::to_string(total);
        if (!firstError.empty()) aviationMessage += " · "+firstError;
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
        generator = std::async(std::launch::async,[=] {
            auto generated = generateWorld(size,countries,seed,difficulty);
            generated.startBots(seed);
            return generated;
        });
    };
    if (generationSmoke) startGame();
    sf::Clock clock;
    sf::Clock startupClock, musicReview;
    std::optional<hoi5::DynamicMusic> music;
    if (!smoke && !inspectBattle && !inspectNews) {
        music.emplace(source / "music");
        music->setVolume(musicVolume);
    }
    const auto openSettings = [&] {
        menuPage = MenuPage::settings;
        pendingResolution = resolution;
        pendingFullscreen = fullscreen;
        resolutionOpen = false;
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
    hoi5::DebugProfiler debug;
    using DebugClock = hoi5::DebugProfiler::Clock;
    int countrySmokeFrame = 0;
    int armySmokeFrame = 0;
    int warningSmokeFrame = 0;
    std::optional<sf::Event> countrySmokeClick;
    while (window.isOpen()) {
        const auto updateStart = DebugClock::now();
        const float frameSeconds = clock.restart().asSeconds();
        debug.frame(frameSeconds);
        const float dt = std::min(.05f,frameSeconds);
        const auto nextEvent = [&] {
            if (countrySmokeClick) return std::exchange(countrySmokeClick,std::nullopt);
            return window.pollEvent();
        };
        while (const auto event = nextEvent()) {
            if (event->is<sf::Event::Closed>()) window.close();
            if (event->is<sf::Event::FocusLost>()) { dragging = draggingExport = false; activeSlider = -1; }
            if (const auto* resize = event->getIf<sf::Event::Resized>())
                camera.setSize(sf::Vector2f(resize->size) / zoom);
            if (const auto* typed = event->getIf<sf::Event::TextEntered>();
                typed && militaryPanel && armyNameFocus && !pauseMenu && !countryModalOpen()) {
                if (typed->unicode >= U' ' && typed->unicode != 127 && armyDesignName.getSize() < 48)
                    armyDesignName += sf::String(typed->unicode);
                continue;
            }
            if (const auto* typed = event->getIf<sf::Event::TextEntered>(); typed && hasDecisionAmount()) {
                if (typed->unicode >= U'0' && typed->unicode <= U'9' && countryDecisionAmount.size() < 13 &&
                    (!countryDecisionAmount.empty() || typed->unicode != U'0')) {
                    countryDecisionAmount.push_back(static_cast<char>(typed->unicode));
                    countryDecisionError.clear();
                    countryDecisionHits.clear();
                }
                continue;
            }
            if (const auto* key = event->getIf<sf::Event::KeyPressed>()) {
                using Key = sf::Keyboard::Key;
                if (frontMode != FrontMode::none && key->code == Key::Escape) {
                    cancelFrontDrawing();
                    continue;
                }
                if (militaryPanel && !pauseMenu && armyNameFocus) {
                    if (key->code == Key::Escape || key->code == Key::Enter) armyNameFocus = false;
                    else if (key->code == Key::Backspace && !armyDesignName.isEmpty()) armyDesignName.erase(armyDesignName.getSize()-1);
                    else if (key->code == Key::Delete || (key->control && key->code == Key::A)) armyDesignName.clear();
                    continue;
                }
                if (militaryPanel && armyPickingSite && key->code == Key::Escape) {
                    armyPickingSite = false;
                    continue;
                }
                if (key->code == Key::F3) debug.visible = !debug.visible;
                if (countryModalOpen()) {
                    if (key->code == Key::Escape) closeCountryDetail();
                    else if (hasDecisionAmount()) {
                        if (key->code == Key::Backspace && !countryDecisionAmount.empty()) countryDecisionAmount.pop_back();
                        else if (key->code == Key::Delete || (key->control && key->code == Key::A)) countryDecisionAmount.clear();
                    }
                    countryDecisionError.clear();
                    countryDecisionHits.clear();
                    continue;
                }
                if (!playing && menuPage == MenuPage::main && !generator.valid() && key->code == Key::Enter) {
                    if (setup) startGame(); else setup = true;
                }
                if (key->code == Key::Escape) {
                    if (menuPage == MenuPage::settings) {
                        if (resolutionOpen) resolutionOpen = false;
                        else { menuPage = MenuPage::main; activeSlider = -1; }
                    } else if (playing && selectedBattle >= 0) selectedBattle = -1;
                    else if (playing && !pauseMenu && (movingDefense >= 0 || !selectedDefense.empty())) {
                        movingDefense = -1;
                        selectedDefense.clear();
                        aviationMessage.clear();
                    } else if (playing) pauseMenu = !pauseMenu;
                    else if (dropdown >= 0) dropdown = -1;
                    else if (!generator.valid()) { setup = false; menuPage = MenuPage::main; }
                }
                if (playing && !pauseMenu && key->code == Key::Space) simulation.togglePause();
                if (playing && key->code >= Key::Num1 && key->code <= Key::Num5)
                    simulation.setSpeed(1 + static_cast<int>(key->code) - static_cast<int>(Key::Num1));
            }
            if (const auto* button = event->getIf<sf::Event::MouseButtonPressed>()) {
                if (countryModalOpen()) {
                    if (button->button == sf::Mouse::Button::Left) {
                        if (countryDetail == CountryDetail::exportLimit && countryExportSlider.contains(button->position)) {
                            draggingExport = true;
                            updateCountryExport(button->position.x);
                            continue;
                        }
                        const auto hit = std::ranges::find_if(countryDecisionHits,[&](const auto& item) {
                            return item.rect.contains(button->position);
                        });
                        if (hit != countryDecisionHits.end()) {
                            const auto activate = hit->activate;
                            activate();
                        }
                    }
                    continue;
                }
                if (playing && !pauseMenu && (armyCommandBounds.contains(button->position) ||
                    divisionListBounds.contains(button->position))) {
                    if (button->button == sf::Mouse::Button::Left) {
                        const auto hit = std::ranges::find_if(armyCommandHits,[&](const auto& item) {
                            return item.rect.contains(button->position);
                        });
                        if (hit != armyCommandHits.end()) {
                            const auto activate = hit->activate;
                            activate();
                        }
                    }
                    if (button->button == sf::Mouse::Button::Right) {
                        const auto hit = std::ranges::find_if(divisionListHits,[&](const auto& item) {
                            return item.first.contains(button->position);
                        });
                        if (hit != divisionListHits.end()) {
                            selectedDivisions.erase(hit->second);
                            syncArmySelection();
                            armyCommandHits.clear();
                        }
                    }
                    continue;
                }
                if (playing && !pauseMenu && frontMode != FrontMode::none) {
                    if (button->button == sf::Mouse::Button::Right) {
                        cancelFrontDrawing();
                        continue;
                    }
                    if (button->button == sf::Mouse::Button::Left && button->position.y >= 94) {
                        const int tile = tileAtWorldPosition(world.size,window.mapPixelToCoords(button->position,camera));
                        if (frontMode == FrontMode::automatic) {
                            if (world.setArmyFront(0,drawingFrontArmy,{tile},true,true)) cancelFrontDrawing();
                        } else {
                            frontPreview.clear();
                            extendFrontPreview(tile);
                            frontDrag = !frontPreview.empty();
                        }
                        continue;
                    }
                }
                if (playing && !pauseMenu && militaryPanel) {
                    if (armyPickingSite && button->button == sf::Mouse::Button::Right) {
                        armyPickingSite = false;
                        continue;
                    }
                    if (button->button == sf::Mouse::Button::Left && armyBounds().contains(button->position)) {
                        armyNameFocus = false;
                        const auto hit = std::ranges::find_if(armyHits,[&](const auto& item) {
                            return item.rect.contains(button->position);
                        });
                        if (hit != armyHits.end()) {
                            const auto activate = hit->activate;
                            activate();
                        }
                        continue;
                    }
                    if (armyPickingSite && button->button == sf::Mouse::Button::Left && button->position.y >= 94) {
                        const int tile = tileAtWorldPosition(world.size,window.mapPixelToCoords(button->position,camera));
                        if (!world.safeTrainingSite(0,tile))
                            militaryMessage = "Нужен свой сухопутный гекс со снабжением от 25%, вне боя";
                        else {
                            if (armyProject) {
                                const auto project = std::ranges::find(world.training,armyProject,&TrainingProject::id);
                                if (project != world.training.end() && project->country == 0) {
                                    project->tile = tile;
                                    militaryMessage = "Гекс развёртывания изменён";
                                } else militaryMessage = "Проект или место развёртывания недоступны";
                            } else {
                                armySite = tile;
                                militaryMessage = "Место развёртывания: ("+std::to_string(tile%world.size)+", "+
                                    std::to_string(tile/world.size)+")";
                            }
                            armyPickingSite = false;
                            selectedTiles = {tile};
                            hexScroll = 0;
                        }
                        continue;
                    }
                    if (!armyBounds().contains(button->position)) armyNameFocus = false;
                }
                if (playing && !pauseMenu && button->button == sf::Mouse::Button::Left) {
                    const auto warning = std::ranges::find_if(warningBounds,[&](const auto& rect) {
                        return rect.contains(button->position);
                    });
                    if (warning != warningBounds.end()) {
                        const auto& item = topWarnings[warning-warningBounds.begin()];
                        if (item.action == WarningAction::news) {
                            if (newsPanel.openItem(item.newsId)) acknowledgedLosses[item.label == "A" ? 0 : 1] = item.newsId;
                        } else if (item.action == WarningAction::diplomacy) {
                            economicPanel = 0;
                            constructionPanel = tradePanel = militaryPanel = false;
                            diplomacyPanel = true;
                            countryList = false;
                            foreignTarget = item.country;
                            countryTab = CountryTab::actions;
                            countryDetail = CountryDetail::none;
                        } else {
                            militaryPanel = diplomacyPanel = false;
                            constructionPanel = item.action == WarningAction::construction;
                            tradePanel = item.action == WarningAction::trade;
                            economicPanel = constructionPanel || tradePanel ? 0 : 2;
                            constructionPlacement = false;
                            if (item.action == WarningAction::supply) setMapLayer(MapLayer::supply);
                            selectedMapResource = {};
                            resourceScroll = 0;
                            resourceMapDirty = constructionMapDirty = true;
                            resourceForecast.reset();
                            tradeForecast.reset();
                        }
                        continue;
                    }
                }
                const auto overFilter = [&] {
                    const auto screen = window.getSize();
                    const auto pointer = sf::Vector2f(button->position);
                    if (mapLayerMenu)
                        for (int i = 0; i <= int(mapLayerLabels.size()); ++i)
                            if (mapLayerOption(screen,i,mapLayerProgress).contains(pointer)) return true;
                    if (resourceGroupMenu)
                        for (int i = 0; i < mapFilterCount(); ++i)
                            if (resourceGroupRect(screen,i,resourceGroupProgress).contains(pointer)) return true;
                    return sf::FloatRect({float(screen.x)-62,float(screen.y)-62},{44,44}).contains(pointer) ||
                        (mapFilterCount() > 0 && resourceGroupRect(screen).contains(pointer));
                };
                const bool overHex = !selectedTiles.empty() && hexPanelRect().contains(sf::Vector2f(button->position));
                if (playing && !pauseMenu && !overFilter() && !overHex &&
                    newsPanel.click(sf::Vector2f(button->position),button->button == sf::Mouse::Button::Left)) continue;
                if (((!playing && !generator.valid() && !setup) ||
                    (playing && pauseMenu && menuPage == MenuPage::settings)) && button->button == sf::Mouse::Button::Left) {
                    const int cx = window.getSize().x/2, cy = window.getSize().y/2;
                    const int x = button->position.x, y = button->position.y;
                    if (menuPage == MenuPage::main) {
                        for (int row = 0; row < 6; ++row) {
                            if (!sf::IntRect({cx-188,cy-186+64*row},{376,52}).contains({x,y})) continue;
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
                                        std::cerr << "Could not apply HOI5 resolution\n";
                                        continue;
                                    }
                                    resolution = pendingResolution;
                                    window.setVerticalSyncEnabled(true);
                                    camera.setSize(sf::Vector2f(window.getSize())/zoom);
                                }
                                pendingFullscreen = fullscreen;
                                const bool saved = hoi5::saveSettings(settingsPaths,{soundVolume,musicVolume,fullscreen,resolution});
                                if (!saved)
                                    std::cerr << "Could not save HOI5 settings: " << settingsPaths.preferred
                                              << " or " << settingsPaths.portable << '\n';
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
                    const auto airPointer = localAirPoint(button->position);
                    const int airX = int(std::floor(airPointer.x)), airY = int(std::floor(airPointer.y));
                    const auto size = window.getSize();
                    const sf::Vector2f pointer(button->position);
                    const sf::FloatRect layerButton({float(size.x)-62,float(size.y)-62},{44,44});
                    if (mapFilterCount() > 0) {
                        if (resourceGroupRect(size).contains(pointer)) {
                            resourceGroupMenu = !resourceGroupMenu;
                            mapLayerMenu = false;
                            continue;
                        }
                        if (resourceGroupMenu && !layerButton.contains(pointer)) {
                            if (resourceGroupProgress >= .8f) {
                                for (int i = 0; i < mapFilterCount(); ++i) {
                                    if (!resourceGroupRect(size,i,resourceGroupProgress).contains(pointer)) continue;
                                    if (mapLayer == MapLayer::political) politicalFilter = static_cast<PoliticalMapFilter>(i);
                                    else resourceGroup = i;
                                    refreshMapLayer();
                                    break;
                                }
                            }
                            resourceGroupMenu = false;
                            continue;
                        }
                    }
                    if (layerButton.contains(pointer)) {
                        resourceGroupMenu = false;
                        mapLayerMenu = !mapLayerMenu;
                        continue;
                    }
                    if (mapLayerMenu) {
                        bool handled = false;
                        if (mapLayerProgress >= .8f) {
                            for (int i = 0; i <= int(mapLayerLabels.size()); ++i) {
                                if (!mapLayerOption(size,i,mapLayerProgress).contains(pointer)) continue;
                                handled = true;
                                if (i == int(mapLayerLabels.size())) {
                                    airDefenseOverlay = !airDefenseOverlay;
                                    mapLayerMenu = false;
                                    selectedDefense.clear();
                                    movingDefense = -1;
                                    aviationMessage.clear();
                                }
                                else if (i == int(MapLayer::weather)) {
                                    showWeatherMessage = true;
                                    (void)weatherMessage.restart();
                                } else {
                                    setMapLayer(static_cast<MapLayer>(i));
                                    mapLayerMenu = false;
                                }
                                break;
                            }
                        }
                        if (!handled) mapLayerMenu = false;
                        continue;
                    }
                    if (world.battles.contains(selectedBattle) &&
                        battlePanel().contains(sf::Vector2f(button->position))) {
                        const auto point = sf::Vector2f(button->position);
                        if (battleClose(battlePanel()).contains(point))
                            selectedBattle = -1;
                        continue;
                    }
                    if (diplomacyPanel && countryBounds().contains(button->position)) {
                        const auto hit = std::ranges::find_if(countryHits,[&](const auto& item) {
                            return item.rect.contains(button->position);
                        });
                        if (hit != countryHits.end()) {
                            const auto activate = hit->activate;
                            activate();
                        }
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
                        if (x < 50) {
                            if (diplomacyPanel && !countryList && foreignTarget == 0) diplomacyPanel = false;
                            else {
                                openCountry(0);
                                countryTab = CountryTab::actions;
                            }
                        } else {
                            const int panelType = x < 100 ? 1 : 2;
                            economicPanel = economicPanel == panelType ? 0 : panelType;
                            if (economicPanel == 2) resourceForecast.reset();
                            militaryPanel = constructionPanel = diplomacyPanel = tradePanel = false;
                        }
                    } else if (economicPanel == 2 && !selectedMapResource.empty() &&
                               resourceCardRect().contains(pointer)) {
                        if (resourceCardClose().contains(sf::Vector2f(button->position))) {
                            selectedMapResource = {};
                            resourceMapDirty = constructionMapDirty = true;
                        } else if (resourceCardTrade().contains(pointer)) {
                            tradePanel = true;
                            economicPanel = 0;
                            tradeForecast.reset();
                        }
                    } else if (economicPanel == 2 && x >= 0 && x < 760 && y >= 90 && y < resourcePanelBottom()) {
                        if (y >= 136 && y < 198 && x >= 18 && x < 522) {
                            resourceCategory = (x-18)/168;
                            resourceScroll = 0;
                            selectedMapResource = {};
                            resourceMapDirty = constructionMapDirty = true;
                        } else if (x >= 42 && x < 402 && y >= resourceWarningsTop &&
                                   y < resourceWarningsTop+resourceWarningHeight*int(resourceWarnings.size())) {
                            const auto [severity,key] = resourceWarnings[(y-resourceWarningsTop)/resourceWarningHeight];
                            for (int category = 0; category < 3; ++category) {
                                const auto keys = resourceCategoryKeys(category);
                                if (std::ranges::find(keys,key) != keys.end()) resourceCategory = category;
                            }
                            selectedMapResource = key;
                            resourceScroll = 0;
                            resourceMapDirty = constructionMapDirty = true;
                        } else if (x >= 12 && x < 507 && y >= resourceRowsTop && y < resourceRowsTop+resourceVisibleRows()*resourceRowHeight) {
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
                    } else if (y >= 40 && y < 78 && x >= 327 && x < 365 && !world.stockpiles.empty()) {
                        militaryPanel = !militaryPanel;
                        armyPickingSite = armyNameFocus = false;
                        economicPanel = 0;
                        constructionPanel = diplomacyPanel = tradePanel = false;
                    } else if (y >= 40 && y < 78 && x >= 192 && x < 230 && !world.construction.queues.empty()) {
                        constructionPanel = !constructionPanel;
                        constructionPlacement = false;
                        economicPanel = 0;
                        diplomacyPanel = tradePanel = militaryPanel = false;
                    } else if (constructionPanel && x >= 20 && x < 20+constructionPanelWidth && y >= 90 &&
                               y < 500+(150+constructionRowHeight*std::max(4,constructionRows(int(hoi5::Construction::groups(world.construction.queues[0]).size()))))) {
                        auto& queue = world.construction.queues[0];
                        const auto groups = hoi5::Construction::groups(queue);
                        const int rows = constructionRows(int(groups.size()));
                        const int offset = 150+constructionRowHeight*std::max(4,rows);
                        if (y >= 132 && y < 160 && !queue.empty()) {
                            auto& project = queue.front();
                            project.paused = !project.paused;
                            project.status = project.paused ? hoi5::ConstructionStatus::paused : hoi5::ConstructionStatus::queued;
                            resourceForecast.reset();
                            tradeForecast.reset();
                        } else if (y >= constructionListTop && y < constructionListTop+constructionRowHeight*rows) {
                            const int row = (y-constructionListTop)/constructionRowHeight;
                            if (constructionCancelButton(row).contains(pointer) && row < int(groups.size())) {
                                const auto project = queue[groups[row].end-1];
                                if (world.construction.cancel(0,project.tile,project.spec)) {
                                    resourceForecast.reset();
                                    tradeForecast.reset();
                                    constructionMapDirty = resourceMapDirty = true;
                                }
                                continue;
                            }
                            for (int direction : {-1,1}) {
                                if (constructionPriorityButton(row,direction).contains(pointer) &&
                                    hoi5::Construction::moveGroup(queue,groups,row,direction)) {
                                    resourceForecast.reset();
                                    tradeForecast.reset();
                                }
                            }
                        } else if (groups.size() > 4 && y >= constructionListTop+constructionRowHeight*rows &&
                                   y < constructionListTop+constructionRowHeight*rows+28) {
                            constructionQueueExpanded = !constructionQueueExpanded;
                        } else if (y >= 238+offset && y < 434+offset) {
                            const int index = 2*((y-238-offset)/28)+(x >= 310);
                            if (index < int(std::size(hoi5::constructionSpecs))) {
                                buildingSpec = index;
                                constructionMapDirty = true;
                            }
                        } else if (y >= 442+offset && y < 474+offset) {
                            constructionPlacement = !constructionPlacement;
                            constructionMapDirty = true;
                        }
                    } else if (!world.air.reserves.empty() && airX >= 10 && airX < 430 &&
                               airY >= wingGridTop(int(wingCards().size())) && airY < int(window.getSize().y)-(selectedWing >= 0 ? 120 : 32)) {
                        const auto cards = wingCards();
                        const int count = int(cards.size());
                        const auto point = airPointer;
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
                                selectedDivisions.clear();
                                hexScroll = 0;
                                hexResourcesExpanded = false;
                            }
                            aircraftPanel = selectedWing >= 0 || wingCreationOpen;
                            editingWing = -1;
                            targetingWing = -1;
                            wingRebaseMode = wingAreaMode = false;
                            break;
                        }
                    } else if (riskMenuWing >= 0 && riskMenuWing == selectedWing && airX >= 10 && airX < 430 &&
                               airY < wingCreationBottom() && airY >= wingCreationBottom()-wingRiskMenuHeight) {
                        const int offset = airY-(wingCreationBottom()-wingRiskMenuHeight+29);
                        if (airX >= 20 && airX < 420 && offset >= 0 && offset/27 < int(wingRiskOptions.size()) && offset%27 < 24) {
                            for (int index : selectedWings)
                                world.air.wings[index].risk = wingRiskOptions[offset/27].first;
                            riskMenuWing = -1;
                        }
                    } else if (missionMenuWing >= 0 && missionMenuWing == selectedWing && airX >= 10 && airX < 430 &&
                               airY < wingCreationBottom() && airY >= wingCreationBottom()-wingMissionMenuHeight) {
                        const int offset = airY-(wingCreationBottom()-wingMissionMenuHeight+29);
                        if (airX >= 20 && airX < 420 && offset >= 0 && offset/27 < int(wingMissionNames.size()) && offset%27 < 24) {
                            const int row = offset/27;
                            if (const auto* enabled = wingMission(world.air.wings[selectedWing],row)) {
                                const bool enable = !*enabled;
                                for (int index : selectedWings)
                                    if (auto* mission = wingMission(world.air.wings[index],row)) *mission = enable;
                            }
                        }
                    } else if (targetingWing >= 0 && targetingWing == selectedWing && airX >= 10 && airX < 430 &&
                               airY < wingCreationBottom() && airY >= wingCreationBottom()-airTargetMenuHeight) {
                        const int offset = airY-(wingCreationBottom()-airTargetMenuHeight+29);
                        const int row = offset/27;
                        if (airX >= 20 && airX < 420 && offset >= 0 && offset%27 < 24 &&
                            row <= int(std::size(airTargetOptions))) {
                            if (row == 0) {
                                for (int index : selectedWings) {
                                    auto& priorities = world.air.wings[index].targetPriorities;
                                    priorities.clear();
                                    for (const auto& [key,name] : airTargetOptions) priorities.push_back(key);
                                }
                            } else {
                                const auto key = airTargetOptions[row-1].first;
                                const auto& primary = world.air.wings[selectedWing].targetPriorities;
                                const bool enable = std::ranges::find(primary,key) == primary.end();
                                for (int index : selectedWings) {
                                    auto& priorities = world.air.wings[index].targetPriorities;
                                    if (!enable) std::erase(priorities,key);
                                    else if (std::ranges::find(priorities,key) == priorities.end()) priorities.push_back(key);
                                }
                            }
                        }
                    } else if (editingWing >= 0 && editingWing == selectedWing && airX >= 10 && airX < 430 &&
                               airY < wingCreationBottom() && airY >= wingCreationBottom()-52-34*int(wingEditRows(editingWing).size())) {
                        const auto rows = wingEditRows(editingWing);
                        const int top = wingCreationBottom()-52-34*int(rows.size());
                        const int row = (airY-top-40)/34;
                        if (airY >= top+40 && row < int(rows.size()) && airX >= 250 && airX < 410)
                            world.air.transferAircraft(world.tiles,editingWing,rows[row],wingEditDeltas[(airX-250)/40]);
                    } else if (wingCreationOpen && airX >= 10 && airX < 430 && airY < wingCreationBottom() &&
                               airY >= wingCreationBottom()-96-30*std::max(1,int(wingCreationRows().size()))) {
                        const auto rows = wingCreationRows();
                        const int bottom = wingCreationBottom();
                        const int top = bottom-96-30*std::max(1,int(rows.size()));
                        const int row = (airY-top-32)/30;
                        if (airY >= top+32 && row < int(rows.size())) wingCreationType = rows[row];
                        const int limit = wingCreationLimit(wingCreationType);
                        if (airY >= bottom-36 && airY < bottom-12) {
                            using Key = sf::Keyboard::Key;
                            const int step = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift) ? 10 : 1;
                            if (airX >= 22 && airX < 50) wingCreationCount -= step;
                            else if (airX >= 108 && airX < 136) wingCreationCount += step;
                            else if (airX >= 150 && airX <= 284 && limit > 1) {
                                draggingWingCount = true;
                                wingCreationCount = int(std::nearbyint(1+(airX-150)/134.*(limit-1)));
                            }
                            else if (airX >= 308 && airX < 418 && limit > 0) {
                                const int preferred = selectedWing >= 0 ? world.air.wings[selectedWing].base : -1;
                                const int wing = world.air.createWing(world.tiles,0,wingCreationType,
                                    wingCreationCount,selectedTiles,preferred);
                                if (wing >= 0) {
                                    selectedWing = wing;
                                    selectedWings = {wing};
                                    selectedTiles = {world.air.wings[wing].base};
                                    selected = -1;
                                    selectedDivisions.clear();
                                    hexScroll = 0;
                                    hexResourcesExpanded = wingRebaseMode = wingCreationOpen = false;
                                }
                            }
                        }
                        wingCreationCount = std::clamp(wingCreationCount,1,std::max(1,limit));
                    } else if (countrySummaryButton.contains(pointer) && !world.profiles.empty()) {
                        openCountry(0);
                    } else if (y >= 40 && y < 78 && x >= 282 && x < 320 && !world.profiles.empty()) {
                        if (diplomacyPanel && countryList) diplomacyPanel = false;
                        else openDiplomacy();
                        openCountryList();
                    } else if (y >= 40 && y < 78 && x >= 147 && x < 185 && !world.stockpiles.empty()) {
                        tradePanel = !tradePanel;
                        tradeForecast.reset();
                        economicPanel = 0;
                        diplomacyPanel = constructionPanel = militaryPanel = false;
                    } else if (tradePanel && tradeBounds().contains({x,y})) {
                        if (tradeClose.contains({x,y})) {
                            tradePanel = false;
                            continue;
                        }
                        for (int i = 0; i < 3; ++i)
                            if (tradeCategoryRect(i).contains({x,y})) {
                                tradeCategory = i;
                                tradeScroll = 0;
                            }
                        if (y >= tradeRowTop && y < tradeRowTop+tradeRowHeight*tradeRows() &&
                            (y-tradeRowTop)%tradeRowHeight >= 15 && (y-tradeRowTop)%tradeRowHeight < 37) {
                            const auto keys = resourceCategoryKeys(tradeCategory);
                            const int row = tradeScroll+(y-tradeRowTop)/tradeRowHeight;
                            for (int i = 0; i < int(tradeButtons.size()) && row < int(keys.size()); ++i) {
                                if (x < tradeButtons[i] || x >= tradeButtons[i]+24) continue;
                                const bool buy = i < 2;
                                const bool shift = sf::Keyboard::isKeyPressed(sf::Keyboard::Key::LShift) ||
                                    sf::Keyboard::isKeyPressed(sf::Keyboard::Key::RShift);
                                const double step = shift ? 10000. : 1000.;
                                const double monthly = hoi5::Market::monthlyCapacity(world.tiles,world.profiles)[0];
                                const double limit = buy ? monthly : monthly*2*world.diplomacy.countries[0].exportLimit;
                                if (world.market.changeContract(0,keys[row],buy,i%2 ? step : -step,limit)) {
                                    tradeForecast.reset();
                                    resourceForecast.reset();
                                    {
                        hoi5::DebugMeasure timing(&debug,"server_economy_history");
                        world.updateEconomyHistory(simulation.elapsedHours,simulation.marketTickCount);
                    }
                                    world.updateStatus();
                                }
                            }
                        }
                    } else if (y >= 92 && y < 164 && x >= panel && x < panel+300) {
                        const int local = x-panel;
                        if (y >= 130 && y < 154) {
                            if (local >= 14 && local < 42) simulation.changeSpeed(-1);
                            if (local >= 48 && local < 86) simulation.togglePause();
                            if (local >= 92 && local < 120) simulation.changeSpeed(1);
                        }
                    } else if (aircraftPanel && selectedWing >= 0 && airX >= 290 && airX < 416 &&
                               airY >= int(window.getSize().y)-79 && airY < int(window.getSize().y)-55) {
                        riskMenuWing = riskMenuWing == selectedWing ? -1 : selectedWing;
                        missionMenuWing = editingWing = targetingWing = -1;
                        wingCreationOpen = false;
                    } else if (aircraftPanel && selectedWing >= 0 && airX >= 290 && airX < 416 &&
                               airY >= int(window.getSize().y)-50 && airY < int(window.getSize().y)-26) {
                        missionMenuWing = missionMenuWing == selectedWing ? -1 : selectedWing;
                        riskMenuWing = editingWing = targetingWing = -1;
                        wingCreationOpen = false;
                    } else if (aircraftPanel && selectedWing >= 0 && airX >= 20 && airX < 100 &&
                               airY >= int(window.getSize().y)-50 && airY < int(window.getSize().y)-26) {
                        editingWing = editingWing == selectedWing ? -1 : selectedWing;
                        targetingWing = -1;
                        wingCreationOpen = false;
                    } else if (aircraftPanel && selectedWing >= 0 && airX >= 205 && airX < 280 &&
                               airY >= int(window.getSize().y)-50 && airY < int(window.getSize().y)-26) {
                        targetingWing = targetingWing == selectedWing ? -1 : selectedWing;
                        editingWing = -1;
                        wingCreationOpen = false;
                    } else if (aircraftPanel && selectedWing >= 0 && airX >= 20 && airX < 100 &&
                               airY >= int(window.getSize().y)-79 && airY < int(window.getSize().y)-55) {
                        wingAreaMode = !wingAreaMode;
                        wingRebaseMode = false;
                    } else if (aircraftPanel && selectedWing >= 0 && airX >= 110 && airX < 200 &&
                               airY >= int(window.getSize().y)-50 && airY < int(window.getSize().y)-26) {
                        wingRebaseMode = !wingRebaseMode;
                        wingAreaMode = false;
                    } else if (!selectedTiles.empty() && hexPanelRect().contains(sf::Vector2f(button->position))) {
                        if (hexCloseRect(hexPanelRect()).contains(sf::Vector2f(button->position))) {
                            selectedTiles.clear();
                            movingDefense = -1;
                            hexSpecializationMode = false;
                        } else if (selectedTiles.size() == 1 && hexCountryButton.contains(pointer)) {
                            const int owner = world.tiles[selectedTiles.front()].owner;
                            if (owner >= 0 && owner < int(world.profiles.size())) openCountry(owner);
                        } else if (const auto move = std::ranges::find_if(defenseMoveButtons,[&](const auto& item) {
                            return item.first.contains(pointer);
                        }); move != defenseMoveButtons.end()) {
                            movingDefense = movingDefense == move->second ? -1 : move->second;
                            selectedDefense.clear();
                            wingAreaMode = wingRebaseMode = false;
                        }
                        else if (hexResourcesToggle.contains(sf::Vector2f(button->position)))
                            hexResourcesExpanded = !hexResourcesExpanded;
                        else if (hexSpecializationButton.contains(pointer))
                            hexSpecializationMode = !hexSpecializationMode;
                        else if (const auto sector = std::ranges::find_if(hexSpecializationRows,[&](const auto& row) {
                            return row.first.contains(pointer);
                        }); sector != hexSpecializationRows.end()) {
                            std::vector<int> industryTiles;
                            for (int cell : selectedTiles)
                                if (world.tiles[cell].owner == 0 && world.tiles[cell].buildings[hoi5::industry].area > 0)
                                    industryTiles.push_back(cell);
                            const bool remove = std::ranges::any_of(industryTiles,[&](int cell) {
                                return std::ranges::find(world.tiles[cell].industries,sector->second) !=
                                    world.tiles[cell].industries.end();
                            });
                            std::map<std::string_view,int> fallback;
                            for (int cell : industryTiles)
                                for (auto key : world.tiles[cell].industries)
                                    if (key != sector->second) ++fallback[key];
                            auto replacement = sector->second == "consumer_goods" ?
                                std::string_view("machinery") : std::string_view("consumer_goods");
                            if (!fallback.empty()) replacement = std::ranges::max_element(fallback,{},&decltype(fallback)::value_type::second)->first;
                            for (int cell : industryTiles) {
                                auto& allocation = world.tiles[cell].industries;
                                if (remove) {
                                    std::erase(allocation,sector->second);
                                    if (allocation.empty()) allocation.push_back(replacement);
                                } else if (std::ranges::find(allocation,sector->second) == allocation.end())
                                    allocation.push_back(sector->second);
                            }
                            resourceForecast.reset();
                            tradeForecast.reset();
                            resourceMapDirty = true;
                        }
                    } else if (constructionPanel && constructionPlacement && y >= 82) {
                        const auto point = window.mapPixelToCoords(button->position,camera);
                        const int cell = tileAtWorldPosition(world.size,point);
                        if (cell >= 0) {
                            using Key = sf::Keyboard::Key;
                            const int steps = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift) ? 5 : 1;
                            int added = 0;
                            for (; added < steps; ++added) {
                                constructionMessage = world.construction.enqueue(world.tiles,world.size,0,cell,buildingSpec,
                                    world.profiles[0].buildEfficiency);
                                if (!constructionMessage.empty()) break;
                            }
                            if (added > 0) {
                                constructionMapDirty = true;
                                constructionMessage = "Добавлено в очередь: "+std::to_string(added);
                                resourceForecast.reset();
                                tradeForecast.reset();
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
                        if (movingDefense >= 0) {
                            const auto unit = std::ranges::find(world.air.defense,movingDefense,&hoi5::AirDefense::id);
                            if (unit == world.air.defense.end() || !canSelectDefense(*unit)) movingDefense = -1;
                            else if (tile >= 0) {
                                bool accepted;
                                aviationMessage = world.orderAirDefenseMove(*unit,tile,&accepted);
                                if (accepted) {
                                    selectedDefense = {unit->id};
                                    movingDefense = -1;
                                    selectedTiles = {tile};
                                }
                            }
                            continue;
                        }
                        if (aircraftPanel && selectedWing >= 0 && (wingAreaMode || wingRebaseMode)) {
                            if (tile < 0) continue;
                            bool changed = false;
                            if (wingAreaMode) {
                                changed = editWingArea(tile,shift ? World::AirAreaEdit::add : World::AirAreaEdit::replace);
                                if (changed && !shift) wingAreaMode = false;
                            } else {
                                for (int index : selectedWings)
                                    changed |= world.air.rebaseWing(world.tiles,index,tile,&aviationMessage);
                                if (changed) {
                                    wingRebaseMode = false;
                                    aviationMessage = "Крыло перебазировано в "+std::to_string(tile%world.size)+":"+
                                        std::to_string(tile/world.size);
                                }
                            }
                            if (changed) selectedTiles = {tile};
                            continue;
                        }
                        if (airDefenseOverlay) {
                            divisionDragStart = button->position;
                            divisionDragActive = false;
                            pendingHexTile = tile;
                            pendingHexShift = shift;
                            continue;
                        }
                        selectedDefense.clear();
                        const auto counters = divisionCounters(world,window,camera,zoom);
                        const auto hit = std::find_if(counters.rbegin(),counters.rend(),[&](const auto& counter) {
                            return world.divisions[counter.first].owner == 0 && counter.bounds.contains(pointer);
                        });
                        if (hit == counters.rend()) {
                            divisionDragStart = button->position;
                            divisionDragActive = false;
                            pendingHexTile = tile;
                            pendingHexShift = shift;
                        } else {
                            if (!shift) selectedDivisions.clear();
                            const bool individual = zoom >= .45f;
                            const bool doubleClick = individual && !shift && lastDivisionClick == hit->first &&
                                divisionClickClock.getElapsedTime().asSeconds() <= .35f;
                            lastDivisionClick = individual ? hit->first : -1;
                            (void)divisionClickClock.restart();
                            if (doubleClick) {
                                const auto* design = world.divisions[hit->first].design;
                                for (const auto& counter : counters) {
                                    const auto& member = world.divisions[counter.first];
                                    if (member.owner == 0 && member.design == design)
                                        selectedDivisions.insert(counter.first);
                                }
                            } else {
                                for (int index : hit->members)
                                    if (!shift || !selectedDivisions.erase(index)) selectedDivisions.insert(index);
                            }
                            selected = selectedDivisions.empty() ? -1 : *selectedDivisions.begin();
                            selectedTiles.clear();
                        }
                    }
                }
                if (playing && !pauseMenu &&
                    (button->button == sf::Mouse::Button::Middle || button->button == sf::Mouse::Button::Right)) {
                    if (button->button == sf::Mouse::Button::Right && (overHex || overFilter())) continue;
                    if (button->button == sf::Mouse::Button::Right && world.battles.contains(selectedBattle) &&
                        battlePanel().contains(sf::Vector2f(button->position))) continue;
                    dragging = true;
                    dragStart = button->position;
                    dragTarget = target;
                }
            }
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>();
                motion && frontDrag && playing && !pauseMenu)
                extendFrontPreview(tileAtWorldPosition(world.size,window.mapPixelToCoords(motion->position,camera)));
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button == sf::Mouse::Button::Left && frontDrag) {
                extendFrontPreview(tileAtWorldPosition(world.size,window.mapPixelToCoords(release->position,camera)));
                if (frontMode == FrontMode::offensive)
                    world.setArmyOffensive(0,drawingFrontArmy,std::move(frontPreview));
                else world.setArmyFront(0,drawingFrontArmy,std::move(frontPreview),false,frontMode == FrontMode::custom);
                cancelFrontDrawing();
                continue;
            }
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>();
                motion && draggingWingCount && wingCreationOpen && !pauseMenu) {
                const int limit = std::max(1,wingCreationLimit(wingCreationType));
                const double ratio = std::clamp((localAirPoint(motion->position).x-150)/134.,0.,1.);
                wingCreationCount = int(std::nearbyint(1+ratio*(limit-1)));
            }
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>(); motion && divisionDragStart) {
                const auto delta = sf::Vector2f(motion->position-*divisionDragStart);
                divisionDragActive |= delta.lengthSquared() >= 36.f;
            }
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button == sf::Mouse::Button::Left && divisionDragStart) {
                using Key = sf::Keyboard::Key;
                const bool shift = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift);
                if (playing && !pauseMenu) {
                    if (airDefenseOverlay) {
                        if (divisionDragActive) {
                            selectDefense(divisionDragRect(*divisionDragStart,release->position),shift);
                        } else {
                            const auto point = sf::Vector2f(release->position);
                            const float reach = std::max(10.f,13.f*zoom);
                            const sf::Vector2f half{reach,reach};
                            const sf::FloatRect hit(point-half,half*2.f);
                            const bool hitBattery = std::ranges::any_of(world.air.defense,[&](const auto& unit) {
                                return canSelectDefense(unit) && hit.contains(defensePixel(unit));
                            });
                            if (hitBattery) selectDefense(hit,pendingHexShift);
                            else {
                                if (!pendingHexShift) {
                                    selectedDefense.clear();
                                    selectedTiles.clear();
                                }
                                if (pendingHexTile >= 0 && std::erase(selectedTiles,pendingHexTile) == 0)
                                    selectedTiles.push_back(pendingHexTile);
                            }
                        }
                    } else if (divisionDragActive) {
                        if (!shift) selectedDivisions.clear();
                        const auto rect = divisionDragRect(*divisionDragStart,release->position);
                        for (const auto& counter : divisionCounters(world,window,camera,zoom)) {
                            if (world.divisions[counter.first].owner != 0 || !rect.contains(counter.bounds.getCenter()))
                                continue;
                            for (int index : counter.members)
                                if (!shift || !selectedDivisions.erase(index)) selectedDivisions.insert(index);
                        }
                        if (!selectedDivisions.empty()) selectedTiles.clear();
                    } else {
                        if (!pendingHexShift) selectedTiles.clear();
                        if (pendingHexTile >= 0 && std::erase(selectedTiles,pendingHexTile) == 0)
                            selectedTiles.push_back(pendingHexTile);
                    }
                    selected = selectedDivisions.empty() ? -1 : *selectedDivisions.begin();
                }
                divisionDragStart.reset();
                divisionDragActive = false;
            }
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button == sf::Mouse::Button::Left)
                draggingWingCount = false;
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button == sf::Mouse::Button::Left) {
                if (draggingExport) updateCountryExport(release->position.x);
                draggingExport = false;
                activeSlider = -1;
            }
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>(); motion && draggingExport)
                updateCountryExport(motion->position.x);
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>();
                motion && activeSlider >= 0 && menuPage == MenuPage::settings)
                updateSlider(motion->position.x);
            if (const auto* release = event->getIf<sf::Event::MouseButtonReleased>();
                release && release->button != sf::Mouse::Button::Left) {
                if (diplomacyPanel && countryBounds().contains(release->position)) {
                    dragging = false;
                    continue;
                }
                if (dragging && release->button == sf::Mouse::Button::Right &&
                    (selected >= 0 || (airDefenseOverlay && !selectedDefense.empty()) ||
                    (aircraftPanel && (selectedWing >= 0 || selectedTiles.size() == 1)) ||
                    (constructionPanel && constructionPlacement))
                    && release->position == dragStart && release->position.y >= 82) {
                    const auto cards = wingCards();
                    const auto p = release->position;
                    const auto airPoint = localAirPoint(p);
                    if (!world.air.reserves.empty() && sf::FloatRect(wingListBounds(int(cards.size()))).contains(airPoint)) {
                        if (selectedWings.size() == 1) {
                            const auto pos = std::ranges::find(cards,selectedWing);
                            if (pos != cards.end() && wingCardRect(int(pos-cards.begin()),int(cards.size())).contains(airPoint)) {
                                selectedWings.clear();
                                selectedWing = -1;
                                wingRebaseMode = wingAreaMode = false;
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
                        if (nearest >= 0 && !(p.x >= 20 && p.x < 20+constructionPanelWidth && p.y >= 90 &&
                            p.y < 500+(150+constructionRowHeight*std::max(4,rows))) &&
                            (selectedTiles.empty() || !hexPanelRect().contains(sf::Vector2f(p))) &&
                            world.construction.cancel(0,nearest,buildingSpec)) {
                            constructionMessage = "Заявка отменена";
                            resourceForecast.reset();
                            tradeForecast.reset();
                            constructionMapDirty = true;
                        }
                    } else if (aircraftPanel && selectedWing >= 0 && (wingAreaMode || wingRebaseMode)) {
                        using Key = sf::Keyboard::Key;
                        const bool shift = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift);
                        if (wingAreaMode && shift && editWingArea(nearest,World::AirAreaEdit::remove)) {
                            selectedTiles = {nearest};
                            hexScroll = 0;
                            hexResourcesExpanded = false;
                        }
                    } else if (airDefenseOverlay && !selectedDefense.empty()) {
                        orderSelectedDefense(nearest);
                    } else if (selected >= 0) {
                        using Key = sf::Keyboard::Key;
                        const bool append = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift);
                        world.orderSelectedDivisions(selectedDivisions,nearest,append);
                    }
                }
                dragging = false;
            }
            if (const auto* motion = event->getIf<sf::Event::MouseMoved>(); motion && dragging)
                target = dragTarget - sf::Vector2f(motion->position - dragStart) / zoom;
            if (const auto* wheel = event->getIf<sf::Event::MouseWheelScrolled>(); wheel && playing) {
                if (!pauseMenu && !countryModalOpen() && divisionListBounds.contains(wheel->position)) {
                    divisionListScroll = std::clamp(divisionListScroll-int(wheel->delta),0,divisionListScrollMax);
                    armyCommandHits.clear();
                    continue;
                }
                if (militaryPanel && !pauseMenu && !countryModalOpen() && armyBounds().contains(wheel->position)) {
                    if (armyTab == ArmyTab::recruit) armyScroll = std::clamp(armyScroll-int(wheel->delta),0,armyScrollMax);
                    continue;
                }
                if (countryModalOpen()) {
                    if (countryDetail != CountryDetail::none) {
                        countryDialogScroll = std::clamp(countryDialogScroll-int(wheel->delta*42),0,countryDialogMaxScroll);
                        countryDecisionHits.clear();
                    }
                    continue;
                }
                if (!pauseMenu && (selectedTiles.empty() || !hexPanelRect().contains(sf::Vector2f(wheel->position))) &&
                    newsPanel.scroll(sf::Vector2f(wheel->position),wheel->delta)) continue;
                if (diplomacyPanel && countryBounds().contains(wheel->position)) {
                    countryScroll = std::clamp(countryScroll-int(wheel->delta),0,countryScrollMax);
                    countryHits.clear();
                    continue;
                }
                if (!selectedTiles.empty() && hexPanelRect().contains(sf::Vector2f(wheel->position))) {
                    hexScroll = std::max(0.f,hexScroll-30*wheel->delta);
                    defenseMoveButtons.clear();
                    continue;
                }
                if (economicPanel == 2 && wheel->position.x >= 0 && wheel->position.x < 528
                    && wheel->position.y >= resourceRowsTop &&
                    wheel->position.y < resourceRowsTop+resourceVisibleRows()*resourceRowHeight) {
                    resourceScroll = std::clamp(resourceScroll - int(wheel->delta),0,
                        std::max(0,int(resourceKeys().size())-resourceVisibleRows()));
                    continue;
                }
                if (tradePanel && tradeBounds().contains(wheel->position)) {
                    tradeScroll = std::clamp(tradeScroll - int(wheel->delta),0,
                        std::max(0,int(resourceCategoryKeys(tradeCategory).size())-tradeRows()));
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
                world.news.startLog(directory/"logs"/"world-news.txt",
                    std::span(world.countryNames).first(world.profiles.size()),
                    std::span(world.rulers).first(world.profiles.size()));
                if (music) music->newWorld();
                (void)musicReview.restart();
                tradePanel = diplomacyPanel = false;
                mapLayer = MapLayer::terrain;
                politicalFilter = PoliticalMapFilter::alliances;
                mapLayerMenu = airDefenseOverlay = showWeatherMessage = false;
                mapLayerProgress = resourceGroupProgress = 0;
                resourceGroup = 0;
                resourceGroupMenu = false;
                aircraftPanel = constructionPanel = militaryPanel = false;
                militaryMessage.clear();
                armyTab = ArmyTab::overview;
                armyDraft = {10};
                armyDesignName = U"Новая дивизия";
                armyType = armyProject = armyPage = armyScroll = 0;
                armySite = -1;
                armyPanelProgress = 0.;
                armyPickingSite = armyNameFocus = false;
                constructionMessage.clear();
                aviationMessage.clear();
                movingDefense = -1;
                selectedDefense.clear();
                defenseMoveButtons.clear();
                selectedWing = -1;
                editingWing = -1;
                targetingWing = -1;
                selectedWings.clear();
                wingCreationOpen = false;
                wingCreationType = -1;
                wingCreationCount = 1;
                missionMenuWing = riskMenuWing = -1;
                draggingWingCount = false;
                wingRebaseMode = wingAreaMode = false;
                foreignTarget = 0;
                countryPanelProgress = 0.f;
                countryTab = CountryTab::summary;
                openCountryList();
                pendingExport = -1;
                draggingExport = false;
                foreignMessage.clear();
                economicPanel = resourceScroll = tradeScroll = 0;
                tradeCategory = 0;
                tradeForecast.reset();
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
                setup = false;
                selected = -1;
                selectedDivisions.clear();
                activeArmy = -1;
                divisionListScroll = 0;
                armyCommandHits.clear();
                divisionListHits.clear();
                armyCommandBounds = divisionListBounds = {};
                cancelFrontDrawing();
                divisionDragStart.reset();
                divisionDragActive = false;
                lastDivisionClick = -1;
                selectedBattle = -1;
                selectedTiles.clear();
                simulation = {};
                newsPanel = {};
                acknowledgedLosses = {};
                warningBounds.clear();
                topWarnings.clear();
            } catch (const std::exception& error) {
                errorMessage = error.what();
                std::cerr << "World generation failed: " << errorMessage << '\n';
            }
        }
        const bool loading = generator.valid();
        const auto size = sf::Vector2f(window.getSize());
        const sf::View gui(sf::FloatRect({0.f, 0.f}, size));
        struct HoverHelp { std::string title; std::vector<std::string> lines; };
        std::optional<HoverHelp> hoverHelp;
        auto drawStart = DebugClock::now();
        window.clear({18,24,31});
        if (playing && !(pauseMenu && menuPage == MenuPage::settings)) {
            if (!pauseMenu) {
                const int previousTick = simulation.tickCount;
                const auto stepsStart = DebugClock::now();
                simulation.update(dt, [&](int hours) {
                    const auto rotation = simulation.pendingMarketTicks
                        ? std::optional{simulation.marketTickCount} : std::nullopt;
                    simulation.pendingMarketTicks = 0;
                    world.advance(hours,&debug,rotation);
                    {
                        hoi5::DebugMeasure timing(&debug,"server_economy_history");
                        world.updateEconomyHistory(simulation.elapsedHours,simulation.marketTickCount);
                    }
                });
                debug.record("server_steps",stepsStart);
                if (simulation.tickCount != previousTick) {
                    resourceForecast.reset();
                    tradeForecast.reset();
                    world.updateStatus();
                }
                if (world.bordersChanged) {
                    hoi5::DebugMeasure timing(&debug,"ownership_refresh");
                    groundResourcesDirty = true;
                    resourceMapDirty = true;
                    constructionMapDirty = true;
                    borders = makeBorders(world);
                    if (mapLayer != MapLayer::terrain) refreshMapLayer();
                    world.bordersChanged = false;
                }
            }
            if (mapLayer == MapLayer::political && (mapPoliticsRevision != world.diplomacy.revision ||
                mapPoliticsDay != world.diplomacy.day)) refreshMapLayer();
            world.updateVisualMotion(dt);
            {
                hoi5::DebugMeasure timing(&debug,"camera");
                using Key = sf::Keyboard::Key;
                if (window.hasFocus() && !countryModalOpen()) {
                    if (sf::Keyboard::isKeyPressed(Key::Left)) target.x -= 300 * dt;
                    if (sf::Keyboard::isKeyPressed(Key::Right)) target.x += 300 * dt;
                    if (sf::Keyboard::isKeyPressed(Key::Up)) target.y -= 300 * dt;
                    if (sf::Keyboard::isKeyPressed(Key::Down)) target.y += 300 * dt;
                }
                target = clampCameraPosition(target);
                camera.move((target - camera.getCenter()) * .3f);
            }
            debug.record("update_total",updateStart);
            drawStart = DebugClock::now();
            window.setView(camera);
            constexpr int verticesPerHex = 18;
            const auto mapResourceKey = selectedMapResource;
            const bool rawMapResource = isRawMapResource(mapResourceKey);
            if ((economicPanel == 2 || constructionPanel) && resourceMapDirty) {
                mapResourceAmounts.assign(world.tiles.size(),0.);
                mapResourceScale = 500000;
                resourceSources = 0;
                if (!mapResourceKey.empty()) {
                    if (!rawMapResource) {
                        double output = 0;
                        for (const auto& stage : world.production[0])
                            output += hoi5::value(stage.outputs,mapResourceKey);
                        mapResourceScale = std::max(1.,output*.18);
                    }
                    resourceMap = map;
                    int deposits = 0;
                    for (int i = 0; i < int(world.tiles.size()); ++i) {
                        const auto& tile = world.tiles[i];
                        const double amount = mapResourceAmounts[i] = mapResourceAmount(tile,mapResourceKey,rawMapResource);
                        if (tile.owner == 0) {
                            const double output = rawMapResource ? tileResourceOutput(tile,mapResourceKey) : amount;
                            resourceSources += output > 0;
                            deposits += rawMapResource && std::ranges::any_of(tile.deposits,[&](const auto& deposit) {
                                return deposit.resource == mapResourceKey && deposit.mass > 0;
                            });
                        }
                        if (amount <= 0) continue;
                        auto color = mapResourceOverlay(amount,mapResourceScale,rawMapResource,
                            map[i*verticesPerHex].color,false);
                        if (rawMapResource) {
                            const double extraction = tileResourceOutput(tile,mapResourceKey);
                            if (extraction > 0) {
                                const double intensity = std::min(1.,std::log10(extraction+1)/4.);
                                const auto active = blendMapColors(sf::Color{72,156,218},
                                    sf::Color{142,228,255},intensity);
                                color = blendMapColors(color,active,.48+intensity*.30);
                            }
                        }
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
                        if (world.tiles[i].owner == 0 && !world.tiles[i].water)
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
                const auto buildType = hoi5::constructionSpecs[buildingSpec].building;
                if (buildType == hoi5::airbase || buildType == hoi5::fieldHelipad) {
                    for (const auto& base : world.air.bases) {
                        if (base.owner != 0) continue;
                        const auto position = center(base.tile%world.size,base.tile/world.size);
                        for (int i = 0; i < int(constructionAirColors.size()); ++i) {
                            const auto& type = hoi5::aircraftTypes[i];
                            if (type.helicopter ? base.helicopterCapacity <= 0 :
                                base.aircraftCapacity <= 0 || base.runway < type.runway) continue;
                            drawDefenseRing(window,position,float(type.range)*spacing,constructionAirColors[i],std::max(2.f,1.f/zoom));
                        }
                    }
                    for (int tile = 0; tile < int(world.tiles.size()); ++tile) {
                        const auto& cell = world.tiles[tile];
                        const auto& helipad = cell.buildings[hoi5::fieldHelipad];
                        if (cell.owner != 0 || helipad.area <= 0 || helipad.health <= 0 ||
                            std::ranges::any_of(world.air.bases,[&](const auto& base) {
                                return base.tile == tile && base.helicopterCapacity > 0;
                            })) continue;
                        drawDefenseRing(window,center(tile%world.size,tile/world.size),
                            float(hoi5::aircraftTypes[4].range)*spacing,constructionAirColors[4],std::max(2.f,1.f/zoom));
                    }
                }
            } else {
                const bool resourceOverlay = (economicPanel == 2 || constructionPanel) && !mapResourceKey.empty();
                auto& geometry = resourceOverlay ? resourceMap : map;
                if (mapLayer == MapLayer::resources || mapLayer == MapLayer::supply) {
                    const auto cursor = sf::Mouse::getPosition(window);
                    const int hovered = tileAtWorldPosition(world.size,window.mapPixelToCoords(cursor,camera));
                    const int selectedTile = selectedTiles.empty() ? -1 : selectedTiles.back();
                    const auto paint = [&](int index,sf::Color color) {
                        for (int i = 0; i < verticesPerHex; ++i) geometry[index*verticesPerHex+i].color = color;
                    };
                    const auto highlight = [&](int index) {
                        const auto previous = geometry[index*verticesPerHex].color;
                        const auto& tile = world.tiles[index];
                        auto color = mapLayer == MapLayer::resources
                            ? resourceGroupColor(tile,resourceMapGroups[resourceGroup],true)
                            : supplyColor(tile,true);
                        if (resourceOverlay)
                            color = mapResourceOverlay(mapResourceAmounts[index],mapResourceScale,rawMapResource,color,false);
                        paint(index,color);
                        return previous;
                    };
                    const bool highlightSelection = selectedTile >= 0 && selectedTile != hovered;
                    const auto previousHover = hovered >= 0 ? highlight(hovered) : sf::Color{};
                    const auto previousSelection = highlightSelection ? highlight(selectedTile) : sf::Color{};
                    window.draw(geometry);
                    if (hovered >= 0) paint(hovered,previousHover);
                    if (highlightSelection) paint(selectedTile,previousSelection);
                } else window.draw(geometry);
            }
            debug.record("world_tiles",drawStart);
            const auto visualsStart = DebugClock::now();
            if (mapLayer == MapLayer::terrain && zoom >= .38f &&
                !(constructionPanel && constructionPlacement)) {
                const auto visibilityStart = DebugClock::now();
                const auto half = camera.getSize()*.5f+sf::Vector2f{radius,radius};
                const auto low = camera.getCenter()-half, high = camera.getCenter()+half;
                const auto origin = center(0,0);
                const int firstRow = std::max(0,int(std::ceil((origin.y-high.y)/(radius*1.5f))));
                const int lastRow = std::min(world.size-1,int(std::floor((origin.y-low.y)/(radius*1.5f))));
                struct VisualTile { int q,r; };
                std::vector<VisualTile> visible;
                for (int r = firstRow; r <= lastRow; ++r) {
                    const float shift = (r%2)*.5f;
                    const int first = std::max(0,int(std::ceil((low.x-origin.x)/spacing-shift)));
                    const int last = std::min(world.size-1,int(std::floor((high.x-origin.x)/spacing-shift)));
                    for (int q = first; q <= last; ++q) visible.push_back({q,r});
                }
                debug.record("visible_tiles_refresh",visibilityStart);
                const bool dense = visible.size() > 260;
                const bool edges = zoom >= .62f && visible.size() <= 140;
                struct Factor { std::string_view key; double coverage,score; int building = -1; };
                struct Mark { sf::Vector2f point; Factor factor; };
                std::vector<Mark> denseMarks;
                const auto drawFactor = [&](const Factor& factor,sf::Vector2f point,float min,float scale,float max,
                                            std::uint8_t alpha) {
                    const auto& texture = tileTextures.at(factor.key);
                    const auto dimensions = sf::Vector2f(texture.getSize());
                    const float width = radius*std::min(max,min+float(std::sqrt(factor.coverage))*scale);
                    sf::Sprite sprite(texture);
                    sprite.setOrigin(dimensions*.5f);
                    sprite.setPosition(point);
                    sprite.setScale({width/dimensions.x,width/dimensions.y});
                    sprite.setColor({255,255,255,alpha});
                    window.draw(sprite);
                };
                const auto neighbors = [](int q,int r) {
                    const int s = r%2;
                    return std::array{sf::Vector2i{q+s,r+1},sf::Vector2i{q+s-1,r+1},sf::Vector2i{q-1,r},
                        sf::Vector2i{q+s-1,r-1},sf::Vector2i{q+s,r-1},sf::Vector2i{q+1,r}};
                };
                const auto factors = [&](int q,int r,bool natural,bool human) {
                    std::vector<Factor> result;
                    const auto& tile = world.at(q,r);
                    if (tile.water) return result;
                    if (natural) {
                        const auto& t = tile.natural;
                        const std::array cover{t.trees,t.grass,t.sand,std::max(t.rock,t.ridge),t.snow};
                        for (int i = 0; i < int(cover.size()); ++i)
                            if (cover[i] >= .03)
                                result.push_back({terrainFiles[i],cover[i],cover[i]*terrainWeights[i]});
                    }
                    if (human) for (const auto& spec : buildingVisuals) {
                        const auto coverage = tile.buildings[spec.building].area;
                        if (coverage < .03) continue;
                        if (spec.building == hoi5::port && !std::ranges::any_of(neighbors(q,r),[&](auto n) {
                            return world.contains(n.x,n.y) && world.at(n.x,n.y).water;
                        })) continue;
                        result.push_back({spec.file,coverage,coverage*spec.weight,spec.building});
                    }
                    std::ranges::stable_sort(result,std::greater{},&Factor::score);
                    return result;
                };
                for (const auto [q,r] : visible) {
                    if (world.at(q,r).water) continue;
                    const auto point = center(q,r);
                    const auto human = factors(q,r,false,true);
                    if (dense) {
                        if (!human.empty()) denseMarks.push_back({point,human.front()});
                        continue;
                    }
                    const auto natural = factors(q,r,true,false);
                    const auto adjacent = neighbors(q,r);
                    const auto edgeOffset = [&](int e) {
                        const auto n = adjacent[e];
                        const int parity = (n.y%2+2)%2;
                        return sf::Vector2f{spacing*(n.x-q+.5f*(parity-r%2)), -1.5f*radius*(n.y-r)};
                    };
                    std::array<std::vector<Factor>,6> nearby;
                    std::array<int,6> reserved{};
                    for (int e = 0; e < 6; ++e)
                        if (world.contains(adjacent[e].x,adjacent[e].y))
                            nearby[e] = factors(adjacent[e].x,adjacent[e].y,true,true);
                    for (int i = 1; i < std::min(7,int(human.size())); ++i) {
                        int best = -1;
                        double value = 0.;
                        for (int e = 0; e < 6; ++e) {
                            if (human[i].key == "port" && world.contains(adjacent[e].x,adjacent[e].y) &&
                                world.at(adjacent[e].x,adjacent[e].y).water) { best = e; break; }
                            for (const auto& candidate : nearby[e])
                                if (candidate.building == human[i].building && candidate.coverage > value) {
                                    value = candidate.coverage;
                                    best = e;
                                }
                        }
                        if (best < 0 || reserved[best])
                            best = int(std::ranges::find(reserved,0)-reserved.begin());
                        reserved[best] = i;
                    }
                    if (edges) for (int e = 0; e < 6; ++e) {
                        if (reserved[e]) continue;
                        const Factor* factor = !nearby[e].empty() ? &nearby[e].front() :
                            natural.size() > 1 ? &natural[1] : nullptr;
                        if (factor) drawFactor(*factor,point+edgeOffset(e)*.36f,
                            .16f,.18f,.36f,145);
                    }
                    if (!natural.empty()) drawFactor(natural.front(),point,.28f,.38f,.86f,175);
                    if (!human.empty()) drawFactor(human.front(),point,.25f,.42f,.74f,255);
                    for (int e = 0; e < 6; ++e) if (reserved[e]) {
                        drawFactor(human[reserved[e]],point+edgeOffset(e)*.25f,
                            .20f,.30f,.50f,248);
                    }
                }
                std::ranges::stable_sort(denseMarks,std::greater{},[](const Mark& mark) { return mark.factor.score; });
                for (int i = 0; i < std::min(520,int(denseMarks.size())); ++i)
                    drawFactor(denseMarks[i].factor,denseMarks[i].point,.22f,.32f,.58f,225);
            }
            debug.record("world_tile_visuals",visualsStart);
            const auto bordersStart = DebugClock::now();
            window.draw(borders);
            debug.record("world_state_borders",bordersStart);
            const auto drawFront = [&](const std::vector<int>& line,sf::Color color,int opponent,bool offensive = false) {
                const auto segment = [&](sf::Vector2f from,sf::Vector2f to) {
                    const auto delta = to-from;
                    sf::RectangleShape stroke({delta.length(),5});
                    stroke.setOrigin({0,2.5f});
                    stroke.setRotation(sf::radians(std::atan2(delta.y,delta.x)));
                    stroke.setPosition(from);
                    stroke.setFillColor(color);
                    window.draw(stroke);
                };
                int previous = -1;
                for (const int tile : line) {
                    if (!offensive && !world.frontLand(0,tile)) { previous = -1; continue; }
                    const auto point = center(tile%world.size,tile/world.size);
                    if (opponent != -2) {
                        world.forFrontNeighbor(tile,[&](int neighbor) {
                            if (world.tiles[neighbor].water || world.tiles[neighbor].owner != opponent) return;
                            const auto delta = center(neighbor%world.size,neighbor/world.size)-point;
                            const auto tangent = sf::Vector2f{-delta.y,delta.x}.normalized()*(radius*.41f);
                            const auto midpoint = point+delta*.43f;
                            segment(midpoint-tangent,midpoint+tangent);
                        });
                        continue;
                    }
                    if (previous >= 0 && world.frontDistance(previous,tile) == 1)
                        segment(center(previous%world.size,previous/world.size),point);
                    previous = tile;
                    sf::CircleShape marker(8.f);
                    marker.setOrigin({marker.getRadius(),marker.getRadius()});
                    marker.setPosition(point);
                    marker.setFillColor(color);
                    window.draw(marker);
                }
            };
            {
                hoi5::DebugMeasure timing(&debug,"world_army_plans");
                for (const auto& army : world.armies)
                    if (army.owner == 0) {
                        drawFront(army.front,army.borderOwner == -2 ? sf::Color{86,188,232,225} : sf::Color{218,184,72,230},
                            army.borderOwner);
                        drawFront(army.offensive,{226,72,62,230},-2,true);
                    }
                drawFront(frontPreview,{246,238,142,230},previewOpponent,frontMode == FrontMode::offensive);
            }
            if (zoom > .200001f && !selectedDivisions.empty()) {
                hoi5::DebugMeasure timing(&debug,"world_divisions");
                for (int index : selectedDivisions)
                    if (world.divisions[index].combat.strength > 0) drawDivisionRoute(window,world,world.divisions[index]);
            }
            if (zoom > .35f) drawWingAreaOverlay(window,world,map,selectedWings,wingAreaMode);
            std::erase_if(selectedDefense,[&](int id) {
                const auto unit = std::ranges::find(world.air.defense,id,&hoi5::AirDefense::id);
                return unit == world.air.defense.end() || !canSelectDefense(*unit);
            });
            if (!selectedDefense.empty()) {
                constexpr std::array<sf::Color,2> routeColors{{{48,130,152,225},{133,230,245,250}}};
                for (const auto& unit : world.air.defense)
                    if (selectedDefense.contains(unit.id))
                        drawUnitRoute(window,world,unit.route,defenseIconPosition(world,unit),unit.progress,
                            [&](int) { return routeColors; },defenseIconOffset);
            }
            const auto airViewHalf = camera.getSize()*.5f+sf::Vector2f{spacing,spacing};
            const sf::FloatRect airVisible(camera.getCenter()-airViewHalf,airViewHalf*2.f);
            const bool showAllDefenseRanges = airDefenseOverlay || !selectedWings.empty() || selectedWing >= 0;
            for (const auto& unit : world.air.defense) {
                const auto position = center(unit.tile%world.size,unit.tile/world.size);
                const bool selectedHex = !selectedTiles.empty() && selectedTiles.back() == unit.tile;
                if (unit.route.empty() &&
                    (showAllDefenseRanges ? unit.health > 0 && unit.readiness() > 0 : selectedHex))
                    drawDefenseRanges(window,unit,position);
            }
            if (!airDefenseOverlay) {
                for (const auto& unit : world.air.defense) {
                    const auto point = defenseIconPosition(world,unit);
                    if (!airVisible.contains(point)) continue;
                    if (zoom <= .35f) {
                        auto color = world.tiles[unit.tile].border;
                        color.a = 200;
                        const float side = 3/zoom;
                        box(window,point-sf::Vector2f{side*.5f,side*.5f},{side,side},color);
                    } else {
                        drawDefenseIcon(window,unit,point);
                    }
                }
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
            if (divisionDragStart && divisionDragActive && !pauseMenu) {
                const auto rect = divisionDragRect(*divisionDragStart,sf::Mouse::getPosition(window));
                box(window,rect.position,rect.size,{110,180,230,42},{135,200,245,220});
            }
            const auto countersStart = DebugClock::now();
            for (const auto& counter : divisionCounters(world,window,camera,zoom,selectedDivisions)) {
                if (!counter.bounds.findIntersection(sf::FloatRect({0,0},size))) continue;
                const auto& unit = world.divisions[counter.first];
                const auto p = counter.bounds.position;
                const auto [w,h] = counter.bounds.size;
                const float sx = w/50.f, sy = h/32.f;
                const auto scaled = [&](float x,float y) { return sf::Vector2f{x*sx,y*sy}; };
                const auto counterBox = [&](float x,float y,float width,float height,sf::Color color) {
                    box(window,p+scaled(x,y),scaled(width,height),color);
                };
                const auto border = world.at(unit.q,unit.r).border;
                const sf::Color fill((border.r*56+32*44)/100, (border.g*56+38*44)/100, (border.b*56+44*44)/100);
                box(window,p,{w,h},fill,counter.selected ? sf::Color(255,246,132) : sf::Color(186,204,220));
                counterBox(2,3,5,26,{30,34,40});
                counterBox(2,29-26*counter.strength,5,26*counter.strength,
                    counter.strength >= .45f ? sf::Color(118,204,238) : sf::Color(236,112,88));
                counterBox(4,26,42,4,{28,34,42});
                counterBox(4,26,42*counter.organization,4,
                    counter.organization >= .45f ? sf::Color(110,214,126) : sf::Color(234,186,72));
                if (unit.icon == "infantry") {
                    sf::CircleShape head(3*sy);
                    head.setPosition(p+scaled(14,5));
                    head.setFillColor({18,24,31});
                    window.draw(head);
                    counterBox(15,11,4,10,{18,24,31});
                    counterBox(11,13,12,3,{18,24,31});
                    counterBox(12,20,10,3,{18,24,31});
                } else {
                    counterBox(10,14,16,5,{18,24,31});
                    counterBox(13,9,7,6,{18,24,31});
                    counterBox(19,10,10,2,{18,24,31});
                    counterBox(10,21,16,3,{18,24,31});
                }
                if (zoom < .45f || counter.count > 1)
                    battleLabel(window,font,std::to_string(counter.count),p+scaled(39,11),
                        unsigned(std::max(8.f,13*sy)),sf::Color::White,.5f);
            }
            debug.record("ui_division_groups",countersStart);
            if (airDefenseOverlay) {
                window.setView(camera);
                for (const auto& unit : world.air.defense) {
                    const auto point = defenseIconPosition(world,unit);
                    if (!airVisible.contains(point)) continue;
                    if (zoom > .35f) drawDefenseIcon(window,unit,point);
                    else {
                        const float half = (canSelectDefense(unit) ? 4.f : 2.f)/zoom;
                        const sf::Vector2f extent{half,half};
                        box(window,point-extent,extent*2.f,
                            canSelectDefense(unit) ? sf::Color(131,220,246) : world.tiles[unit.tile].border);
                    }
                    if (selectedDefense.contains(unit.id) || (unit.id >= 0 && unit.id == movingDefense))
                        drawDefenseRing(window,point,std::max(15.f,7.f/zoom),sf::Color::Yellow,2.f/zoom);
                }
                window.setView(gui);
            }
            const auto aviationStart = DebugClock::now();
            sf::VertexArray flights(sf::PrimitiveType::Triangles);
            const auto now = DebugClock::now();
            for (const auto& effect : world.airVisuals) {
                const float age = std::chrono::duration<float>(now-effect.start).count();
                const float duration = effect.impact ? 1.7f : 1.8f;
                if (age >= duration) continue;
                const auto pixel = [&](int tile) {
                    return sf::Vector2f(window.mapCoordsToPixel(center(tile%world.size,tile/world.size),camera));
                };
                const auto from = pixel(effect.origin), to = pixel(effect.target);
                const auto delta = to-from;
                const float length = std::hypot(delta.x,delta.y);
                const auto forward = length > 0 ? delta/length : sf::Vector2f{1,0};
                const sf::Vector2f side{-forward.y,forward.x};
                const float t = age/duration;
                const auto point = effect.impact ? to : from+delta*(1-std::abs(2*t-1));
                if (point.x < -30 || point.y < -30 || point.x > size.x+30 || point.y > size.y+30) continue;
                const auto triangle = [&](sf::Vector2f a,sf::Vector2f b,sf::Vector2f c,sf::Color color) {
                    for (auto p : {a,b,c}) flights.append({point+forward*p.x+side*p.y,color});
                };
                if (effect.impact) {
                    const auto alpha = static_cast<unsigned char>(210*(1-t));
                    const sf::Color glow = effect.loss ? sf::Color{255,94,48} : sf::Color{255,184,86};
                    const float scale = std::clamp(zoom,.55f,1.6f);
                    const float inner = (4+8*t)*scale, outer = (10+18*t)*scale;
                    for (int i = 0; i < 20; ++i) {
                        const float a = i*.31415927f, b = (i+1)*.31415927f;
                        const sf::Vector2f u{std::cos(a),std::sin(a)}, v{std::cos(b),std::sin(b)};
                        const auto rim = sf::Color(glow.r,glow.g,glow.b,alpha/2);
                        triangle({},u*outer,v*outer,{glow.r,glow.g,glow.b,static_cast<unsigned char>(alpha/4)});
                        triangle(u*outer,v*outer,u*(outer-2*scale),rim);
                        triangle(v*outer,v*(outer-2*scale),u*(outer-2*scale),rim);
                        triangle({},u*inner,v*inner,{255,235,164,static_cast<unsigned char>(alpha/2)});
                    }
                    for (int i = 0; i < 4; ++i) {
                        const float angle = i*1.5707963f+t*.9f;
                        const sf::Vector2f ray{std::cos(angle),std::sin(angle)};
                        const sf::Vector2f tangent = sf::Vector2f{-ray.y,ray.x}*scale;
                        const auto a = ray*(inner*.55f), b = ray*(outer*.92f);
                        const auto spark = sf::Color(glow.r,glow.g,glow.b,alpha/2);
                        triangle(a+tangent,a-tangent,b+tangent,spark);
                        triangle(a-tangent,b-tangent,b+tangent,spark);
                    }
                    continue;
                }
                auto color = world.tiles[effect.origin].border;
                color.a = 245;
                const float d = t < .5f ? 1.f : -1.f;
                const bool helicopter = effect.type >= 0 && hoi5::aircraftTypes[effect.type].helicopter;
                if (helicopter) {
                    triangle({6.6f*d,0},{0,-4.08f},{0,4.08f},color);
                    triangle({0,-4.08f},{-8.88f*d,-2.88f},{0,4.08f},color);
                    triangle({-8.88f*d,-2.88f},{-7.44f*d,2.88f},{0,4.08f},color);
                    const sf::Color rotor{230,240,248,210};
                    triangle({-1.6f,-11.4f},{.4f,-11.4f},{.4f,11.4f},rotor);
                    triangle({-1.6f,-11.4f},{-1.6f,11.4f},{.4f,11.4f},rotor);
                    triangle({-6*d,-1},{-16*d,0},{-6*d,1},color);
                } else {
                    triangle({11.4f*d,0},{1.44f*d,-2.16f},{1.44f*d,2.16f},color);
                    triangle({1.44f*d,-2.16f},{-11.76f*d,0},{1.44f*d,2.16f},color);
                    for (float sign : {-1.f,1.f}) {
                        triangle({1.68f*d,sign*1.2f},{-3.6f*d,sign*10.56f},{-1.44f*d,sign*1.2f},color);
                        triangle({-8.16f*d,sign*.96f},{-12.24f*d,sign*5.76f},{-10.32f*d,sign*.72f},color);
                    }
                }
            }
            window.draw(flights);
            for (const auto& salvo : world.salvos) {
                const auto point = sf::Vector2f(window.mapCoordsToPixel(
                    center(salvo.current%world.size,salvo.current/world.size),camera));
                box(window,point-sf::Vector2f(2,1),{4,2},{243,169,55});
            }
            window.setView(camera);
            for (const auto& base : world.air.bases) {
                const auto& tile = world.tiles[base.tile];
                if (tile.owner != base.owner) continue;
                if (std::ranges::any_of(world.divisions,[&](const auto& unit) {
                    return unit.combat.strength > 0 && unit.r*world.size+unit.q == base.tile;
                })) continue;
                const auto point = center(base.tile%world.size,base.tile/world.size);
                if (!airVisible.contains(point)) continue;
                if (zoom <= .35f) {
                    auto color = tile.border;
                    color.a = 210;
                    const sf::Vector2f marker{5/zoom,3/zoom};
                    box(window,point-marker*.5f,marker,color);
                } else {
                    box(window,point+sf::Vector2f{-18,-16},{36,8},{18,24,31,225},tile.border);
                    box(window,point+sf::Vector2f{-12,-12},{24,1},{228,238,248});
                }
            }
            if (zoom > .35f) {
                const auto half = camera.getSize()*.5f+sf::Vector2f{radius,radius};
                const sf::FloatRect visible(camera.getCenter()-half,half*2.f);
                for (int index = 0; index < int(world.tiles.size()); ++index) {
                    const auto& tile = world.tiles[index];
                    if (tile.buildings[hoi5::fieldHelipad].area <= 0) continue;
                    const auto point = center(index%world.size,index/world.size);
                    if (visible.contains(point)) drawFieldHelipad(window,point,
                        tile.owner >= 0 ? tile.border : sf::Color(180,190,200));
                }
                for (const auto& project : world.helipadProjects) {
                    const auto point = center(project.tile%world.size,project.tile/world.size);
                    if (visible.contains(point))
                        drawFieldHelipad(window,point,world.tiles[project.tile].border,project.progress/18);
                }
            }
            window.setView(gui);
            debug.record("world_air_assets",aviationStart);
            for (const auto& [tile, battle] : world.battles) {
                const auto rect = battleIndicator(tile,battle);
                sf::CircleShape marker(22);
                marker.setPosition(rect.position);
                marker.setFillColor(battle.attacker == 0 ? sf::Color(72,44,38,235) : sf::Color(38,55,76,235));
                marker.setOutlineColor({235,215,150});
                marker.setOutlineThickness(-2);
                window.draw(marker);
                const auto midpoint = rect.position+sf::Vector2f{22,22};
                const auto destination = sf::Vector2f(window.mapCoordsToPixel(center(tile%world.size,tile/world.size),camera));
                const auto delta = destination-midpoint;
                const float angle = std::atan2(delta.y,delta.x);
                const auto direction = [](float a) { return sf::Vector2f(std::cos(a),std::sin(a)); };
                const auto stroke = [&](sf::Vector2f start,float a,float length) {
                    sf::RectangleShape line({length,3});
                    line.setOrigin({0,1.5f});
                    line.setPosition(start);
                    line.setRotation(sf::radians(a));
                    line.setFillColor({230,92,82});
                    window.draw(line);
                };
                stroke(midpoint,angle,16);
                const auto tip = midpoint+direction(angle)*16.f;
                for (float offset : {2.55f,-2.55f}) stroke(tip,angle+offset,7);
                if (!world.battles.contains(selectedBattle))
                    battleLabel(window,font,std::to_string(int(world.battleWinRatio(battle)*100))+"%",
                        midpoint+sf::Vector2f{0,5},10,sf::Color::White,.5f);
            }
            if (constructionPanel && constructionPlacement) {
                window.setView(camera);
                const auto half = camera.getSize()*.5f;
                const auto lower = camera.getCenter()-half-sf::Vector2f{52,11};
                const auto upper = camera.getCenter()+half+sf::Vector2f{52,11};
                const auto origin = center(0,0);
                const int firstRow = std::max(0,int(std::ceil((origin.y-upper.y)/(radius*1.5f))));
                const int lastRow = std::min(world.size-1,int(std::floor((origin.y-lower.y)/(radius*1.5f))));
                const float labelScale = std::max(1.f,.65f/zoom);
                const bool supplyLabels = hoi5::constructionSpecs[buildingSpec].building == hoi5::supplyDepot;
                sf::Text text(font,"",17);
                text.setScale({labelScale,labelScale});
                text.setStyle(sf::Text::Bold);
                text.setFillColor({232,252,144});
                int drawnLabels = 0;
                for (int r = firstRow; r <= lastRow; ++r) {
                    const float shift = (r%2)*.5f;
                    const int firstCol = std::max(0,int(std::ceil((lower.x-origin.x)/spacing-shift)));
                    const int lastCol = std::min(world.size-1,int(std::floor((upper.x-origin.x)/spacing-shift)));
                    for (int q = firstCol; q <= lastCol; ++q) {
                        const auto& value = constructionLabels[r*world.size+q];
                        if (value.isEmpty()) continue;
                        const auto position = center(q,r);
                        box(window,position+sf::Vector2f{-31,-12}*labelScale,
                            sf::Vector2f{62,supplyLabels ? 42.f : 24.f}*labelScale,{18,27,22,210},{206,238,140,190});
                        text.setString(value);
                        const auto bounds = text.getLocalBounds();
                        text.setOrigin(bounds.position+bounds.size*.5f);
                        text.setPosition(position+sf::Vector2f{0,1});
                        window.draw(text);
                        ++drawnLabels;
                        if (supplyLabels) {
                            const auto percent = int(std::nearbyint(world.tiles[r*world.size+q].supply*100));
                            const auto summary = std::to_string(percent)+"%";
                            text.setString(summary);
                            const auto supplyBounds = text.getLocalBounds();
                            text.setOrigin(supplyBounds.position+supplyBounds.size*.5f);
                            text.setPosition(position+sf::Vector2f{0,20}*labelScale);
                            text.setFillColor({133,205,250});
                            window.draw(text);
                            text.setFillColor({232,252,144});
                        }
                    }
                }
                if (constructionSmoke && drawnLabels == 0) return 1;
                window.setView(gui);
            }
            const auto ui_top_statusStart = DebugClock::now();
            box(window,{0,0},{size.x,36},{18,24,31,245});
            box(window,{0,35},{size.x,2},{88,106,128});
            box(window,{0,36},{size.x,46},{24,31,40,238});
            box(window,{0,81},{size.x,2},{70,88,108});
            const auto mouse = sf::Mouse::getPosition(window);
            const auto statusWidth = [&](const std::string& field) {
                const sf::Text text(font,sf::String::fromUtf8(field.begin(),field.end()),14);
                return text.getLocalBounds().size.x;
            };
            const auto statusText = [&](const std::string& field,float left,sf::Color color,float maxWidth = 10000.f) {
                sf::Text text(font,sf::String::fromUtf8(field.begin(),field.end()),14);
                const auto bounds = text.getLocalBounds();
                text.setPosition({std::round(left),std::round(18-bounds.position.y-bounds.size.y/2)});
                text.setFillColor(color);
                if (bounds.size.x > maxWidth) text.setScale({maxWidth/bounds.size.x,1.f});
                window.draw(text);
            };
            float x = 10;
            for (int index = 0; index < 3; ++index) {
                const auto& field = world.status[index];
                const float width = std::max(88.f,statusWidth(field)+22);
                const sf::FloatRect rect({x-6,5},{width-8,26});
                if (index == 1) populationHoverRect = rect;
                if (index == 2) budgetHoverRect = rect;
                if (index == 0) {
                    countrySummaryButton = rect;
                    box(window,rect.position,rect.size,sf::Color::Transparent,{118,146,176});
                }
                else if (rect.contains(sf::Vector2f(mouse)))
                    box(window,rect.position,rect.size,{36,48,62,210},{118,146,176,180});
                statusText(field,x,index == 0 ? sf::Color(238,244,250) : sf::Color(210,220,232));
                x += width;
            }
            const auto& resources = world.status[3];
            const auto* policy = world.diplomacy.countries.empty() ? nullptr : &world.diplomacy.countries.front();
            const bool compactPolitics = size.x < 1366;
            const std::array policyValues{world.status[4],world.status[5],
                compactPolitics && policy ? "Война: "+std::to_string(int(std::lround(policy->warSupport*100)))+"%" : world.status[6],
                std::string(compactPolitics ? "Полит. кап.: " : "Полит. капитал: ")+(policy ? formatAmount(policy->capital) : "—")};
            const auto policyWidth = [&](const std::string& value) {
                const sf::Text text(font,sf::String::fromUtf8(value.begin(),value.end()),14);
                return text.getLocalBounds().size.x+16.f;
            };
            float politicsWidth = 0.f;
            for (const auto& value : policyValues) politicsWidth += policyWidth(value);
            const float available = std::max(70.f,size.x-x-185.f-14.f-politicsWidth);
            const float resourceWidth = std::min(available,std::max(360.f,statusWidth(resources)+38));
            resourceHoverRect = {{x,5},{resourceWidth,26}};
            for (auto& items : resourceProblems) items.clear();
            topWarnings.clear();
            warningBounds.clear();
            int problem = 0;
            if (!world.stockpiles.empty()) {
                hoi5::Stockpile used;
                for (const auto& [key,stock] : world.stockpiles[0])
                    used[hoi5::storageBucket(key)] += stock;
                if (!resourceForecast) resourceForecast = world.forecastResources(0,simulation.marketTickCount);
                const auto& forecast = *resourceForecast;
                std::vector<std::string> shortageLines;
                for (int category = 0; category < 3; ++category) {
                    const std::array start{resourceProblems[0].size(),resourceProblems[1].size()};
                    for (const auto key : resourceCategoryKeys(category)) {
                        const int severity = resourceShortageLevel(hoi5::value(world.stockpiles[0],key),
                            hoi5::value(forecast.required,key)-hoi5::value(forecast.outputs,key));
                        if (severity > 0) resourceProblems[2-severity].push_back(key);
                    }
                    for (int level = 0; level < int(start.size()); ++level)
                        for (auto j = start[level]; j < std::min(start[level]+3,resourceProblems[level].size()) &&
                            shortageLines.size() < 6; ++j)
                            shortageLines.push_back(std::string(level == 0 ? "Критично: " : "Мало: ")+
                                std::string(resourceDisplayName(resourceProblems[level][j])));
                }
                problem = !resourceProblems[0].empty() ? 2 : !resourceProblems[1].empty() ? 1 : 0;
                if (problem) topWarnings.push_back({"!","Проблемы ресурсов",std::move(shortageLines),WarningAction::resources,problem == 2});
                std::vector<std::string> storageLines;
                bool full = false;
                constexpr std::pair<std::string_view,std::string_view> buckets[]{
                    {"raw","Сырье"},{"semi_finished","Полуфабрикаты"},{"finished","Готовая продукция"},{"fuel","Топливо"}
                };
                for (int severity = 2; severity >= 1; --severity)
                    for (const auto [key,label] : buckets) {
                        const double stock = hoi5::value(used,key), capacity = hoi5::value(world.capacities[0],key);
                        if (storageProblemLevel(stock,capacity) != severity) continue;
                        full |= severity == 2;
                        problem = std::max(problem,severity);
                        storageLines.push_back(std::string(label)+": "+resourceAmountLabel(stock)+"/"+resourceAmountLabel(capacity));
                    }
                if (!storageLines.empty()) topWarnings.push_back({"S",full ? "Склады заполнены" : "Склады почти заполнены",
                    std::move(storageLines),WarningAction::resources,full});
                const auto& supply = world.humanSupply;
                if (supply.critical || supply.low)
                    topWarnings.push_back({"L","Проблемы снабжения",
                        {"Среднее снабжение: "+std::to_string(int(std::nearbyint(100*supply.average)))+"%",
                         "Критичных клеток: "+std::to_string(supply.critical),
                         "Слабых клеток: "+std::to_string(supply.low)},WarningAction::supply,supply.critical > 0});
                const auto& living = world.diplomacy.countries[0];
                if (living.food < .75 || living.goods < .75) {
                    std::vector<std::string> lines;
                    if (living.food < .75) lines.push_back("Продовольствие: "+
                        std::to_string(int(std::lround(living.food*100)))+"%");
                    if (living.goods < .75) lines.push_back("Потребительские товары: "+
                        std::to_string(int(std::lround(living.goods*100)))+"%");
                    topWarnings.push_back({"P","Дефицит товаров для населения",std::move(lines),
                        WarningAction::resources,living.food < .5 || living.goods < .5});
                }
                for (const auto& [goal,ready] : world.diplomacy.goals) {
                    if (goal.first != 0 || simulation.elapsedHours/24 < ready ||
                        simulation.elapsedHours/24 > ready+180) continue;
                    topWarnings.push_back({"W","Цель войны готова",
                        {"Цель: "+std::string(world.countryNames[goal.second]),"ЛКМ — открыть решения страны"},
                        WarningAction::diplomacy,true,0,goal.second});
                }
                double buy = 0., sell = 0.;
                for (const auto& contract : world.market.contracts) {
                    if (contract.country != 0 || contract.amount <= 0 || !std::isfinite(contract.amount)) continue;
                    (contract.buy ? buy : sell) += contract.amount;
                }
                const double buyCapacity = world.humanTradeCapacity;
                const double sellCapacity = buyCapacity*2*world.diplomacy.countries[0].exportLimit;
                if (buy > buyCapacity+.001 || sell > sellCapacity+.001)
                    topWarnings.push_back({"T","Торговля уперлась в лимит",
                        {"Покупка: "+resourceAmountLabel(buy)+"/"+resourceAmountLabel(buyCapacity)+"/мес",
                         "Продажа: "+resourceAmountLabel(sell)+"/"+resourceAmountLabel(sellCapacity)+"/мес",
                         "Нужны порты, склады, логистика или снабжение."},WarningAction::trade,false});
                if (!world.construction.queues.empty()) {
                    using Status = hoi5::ConstructionStatus;
                    const auto& queue = world.construction.queues[0];
                    const auto first = std::ranges::find(queue,false,&hoi5::ConstructionProject::paused);
                    if (first != queue.end()) {
                        auto status = Status::queued;
                        std::vector<std::string> lines;
                        const double budget = world.profiles[0].budget;
                        if (!first->paid && budget < first->money) {
                            status = Status::waitingMoney;
                            lines.push_back("Не хватает денег "+formatMoney(first->money-budget));
                        } else {
                            const double speed = hoi5::Construction::buildPower(world.tiles,0,world.profiles[0])*
                                hoi5::Construction::speedMultiplier(world.battles.contains(first->tile));
                            if (speed <= 0) {
                                status = Status::waitingPower;
                                lines.emplace_back("Нет строительной мощности");
                            } else {
                                const auto delta = hoi5::Construction::progressDelta(*first,speed,1./30.);
                                const auto needed = hoi5::Construction::projectNeeds(*first,delta);
                                std::vector<std::pair<std::string_view,double>> missing;
                                for (const auto& [key,amount] : needed) {
                                    const double deficit = amount-hoi5::value(world.stockpiles[0],key);
                                    if (deficit > .001) missing.emplace_back(key,deficit);
                                }
                                std::ranges::stable_sort(missing,std::greater{},&std::pair<std::string_view,double>::second);
                                for (int i = 0; i < std::min(5,int(missing.size())); ++i)
                                    lines.push_back("Нет "+std::string(resourceDisplayName(missing[i].first))+
                                        " "+resourceAmountLabel(missing[i].second));
                                if (!lines.empty()) status = Status::waitingResources;
                            }
                        }
                        if (!lines.empty()) {
                            lines.insert(lines.begin(),std::string(hoi5::constructionSpecs[first->spec].label)+" ("+
                                std::to_string(first->tile%world.size)+", "+std::to_string(first->tile/world.size)+")");
                            topWarnings.push_back({"C","Стройка: "+std::string(hoi5::constructionStatusLabel(status)),
                                std::move(lines),WarningAction::construction,true});
                        }
                    }
                }
                constexpr std::array lossKeys{"aircraft_losses","battle_losses"};
                for (int i = 0; i < int(lossKeys.size()); ++i) {
                    const auto* loss = world.news.latestImportant(0,lossKeys[i],simulation.elapsedHours/24-6);
                    if (!loss || loss->id <= acknowledgedLosses[i]) continue;
                    auto lines = countryTextLines(loss->body,40);
                    if (lines.size() > 5) lines.resize(5);
                    lines.emplace_back("ЛКМ — открыть новость");
                    topWarnings.push_back({i == 0 ? "A" : "Б",i == 0 ? "Потери авиации" : "Тяжёлые потери на фронте",
                        std::move(lines),WarningAction::news,true,loss->id});
                }
            }
            auto fill = std::array{sf::Color(38,82,54,215),sf::Color(112,92,42,225),sf::Color(112,42,42,225)}[problem];
            if (resourceHoverRect.contains(sf::Vector2f(mouse))) {
                fill.r = int(fill.r*.88+255*.12);
                fill.g = int(fill.g*.88+255*.12);
                fill.b = int(fill.b*.88+255*.12);
            }
            box(window,{x,5},{resourceWidth,26},fill,{116,140,162,180});
            statusText(resources,x+10,{238,244,250},resourceWidth-20);
            x += resourceWidth+14;
            constexpr std::array policyTitles{"Стабильность","Легитимность","Поддержка войны","Политический капитал"};
            constexpr std::array policyHelp{
                "Устойчивость государства. Влияет на налоговую отдачу предприятий, готовность населения служить и оценку мощи страны.",
                "Доверие к праву правительства управлять страной. Влияет на доступность политических решений, эффективность программ поддержки, набор людей и прирост политического капитала.",
                "Готовность населения поддерживать войну. Влияет на набор людей, реакцию общества на войну и возможность её объявления.",
                "Ресурс для внутренних и внешних решений. Расходуется на налоги, программы поддержки и дипломатию. Восстанавливается ежедневно в зависимости от поддержки правительства и легитимности. Война снижает прирост."
            };
            for (std::size_t index = 0; index < policyValues.size(); ++index) {
                const float width = policyWidth(policyValues[index]);
                const sf::FloatRect bounds({x-4,5},{width-4,26});
                if (bounds.contains(sf::Vector2f(mouse))) {
                    box(window,bounds.position,bounds.size,{36,48,62,210},{118,146,176,180});
                    hoverHelp = HoverHelp{policyTitles[index],countryTextLines(policyHelp[index],36)};
                }
                statusText(policyValues[index],x,{210,220,232});
                x += width;
            }

            debug.record("ui_top_status",ui_top_statusStart);
            const auto ui_top_navigationStart = DebugClock::now();
            const bool domesticPanel = diplomacyPanel && !countryList && foreignTarget == 0;
            const std::array active{domesticPanel,economicPanel == 1,economicPanel == 2,
                tradePanel,constructionPanel,false,diplomacyPanel && !domesticPanel,militaryPanel};
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
            for (int i = 0; i < int(topWarnings.size()); ++i) {
                const sf::IntRect rect({381+36*i,45},{28,28});
                warningBounds.push_back(rect);
                auto color = topWarnings[i].critical ? sf::Color{128,48,42,235} : sf::Color{138,104,38,235};
                if (rect.contains(mouse)) {
                    color.r = int(color.r*.86+255*.14);
                    color.g = int(color.g*.86+255*.14);
                    color.b = int(color.b*.86+255*.14);
                }
                box(window,sf::Vector2f(rect.position),sf::Vector2f(rect.size),color,{214,222,232});
                battleLabel(window,cardFont,topWarnings[i].label,sf::Vector2f(rect.getCenter()),17,sf::Color::White,.5f);
            }
            debug.record("ui_top_navigation",ui_top_navigationStart);
            const auto ui_time_hudStart = DebugClock::now();
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
            debug.record("ui_time_hud",ui_time_hudStart);
            if (!selectedTiles.empty()) {
                hoi5::DebugMeasure timing(&debug,"ui_hex_panel");
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
                const auto hex_buildings_lookupStart = DebugClock::now();
                for (int cell : selectedTiles) {
                    for (int i = 0; i < hoi5::buildingCount; ++i) {
                        const auto& building = world.tiles[cell].buildings[i];
                        coverage[i] += building.area;
                        damage[i] += building.area*(1-std::clamp(building.health,0.,1.));
                    }
                }
                debug.record("hex_buildings_lookup",hex_buildings_lookupStart);
                constexpr std::array order{hoi5::airbase,hoi5::city,hoi5::farms,hoi5::fieldHelipad,
                    hoi5::fortification,hoi5::fuelStorage,hoi5::industry,hoi5::mine,hoi5::oilGasRig,
                    hoi5::port,hoi5::refinery,hoi5::supplyDepot,hoi5::village,hoi5::warehouse};
                hoi5::Stockpile ground, localStock, localCapacity, localUsed;
                const auto hex_storage_lookupStart = DebugClock::now();
                for (int cell : selectedTiles) {
                    const auto& selected = world.tiles[cell];
                    const auto capacity = hoi5::tileStorageCapacity(selected);
                    for (const auto& [bucket,amount] : capacity) localCapacity[bucket] += amount;
                    for (const auto& [key,amount] : world.stockpileAtTile(cell)) localStock[key] += amount;
                }
                debug.record("hex_storage_lookup",hex_storage_lookupStart);
                const auto hex_resources_lookupStart = DebugClock::now();
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
                debug.record("hex_resources_lookup",hex_resources_lookupStart);
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
                const bool editableIndustry = coverage[hoi5::industry] > 0 &&
                    std::ranges::all_of(selectedTiles,[&](int cell) { return world.tiles[cell].owner == 0; });
                const float bottom = panel.size.y-(editableIndustry ? 96.f : 58.f);
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
                const auto hex_aviation_lookupStart = DebugClock::now();
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
                std::map<std::size_t,int> defenseRows;
                for (const auto& unit : world.air.defense) {
                    if (!containsTile(unit.tile)) continue;
                    const auto& type = hoi5::defenseClasses[unit.type];
                    if (multiple) ++defenseCounts[type.key];
                    else {
                        if (canSelectDefense(unit)) defenseRows.emplace(aviation.size(),unit.id);
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
                debug.record("hex_aviation_lookup",hex_aviation_lookupStart);
                const float aviationY = buildingsY+28+16*std::max<std::ptrdiff_t>(1,count);
                std::map<std::string_view,double> industryAllocation;
                int industryTileCount = 0;
                for (int cell : selectedTiles) {
                    const auto& selected = world.tiles[cell];
                    if (selected.buildings[hoi5::industry].area <= 0 || selected.industries.empty()) continue;
                    ++industryTileCount;
                    for (auto sector : selected.industries)
                        industryAllocation[sector] += 1./selected.industries.size();
                }
                const float productionY = aviationY+(aviation.empty() ? 0.f : 28.f+16.f*aviation.size());
                const float productionHeight = industryTileCount == 0 ? 0.f :
                    48.f+16.f*industryAllocation.size()+(hexSpecializationMode && editableIndustry ?
                        16.f+29.f*(std::size(hoi5::sectors)+1) : 0.f);
                const float climateY = productionY+productionHeight;
                const bool showGroundEffects = !multiple && !tile.water;
                const float contentEnd = climateY+20+4*16+12+(showGroundEffects ? 76 : 0);
                const float maxScroll = std::max(0.f,contentEnd-bottom);
                hexScroll = std::min(hexScroll,maxScroll);
                const auto panelLine = [&](std::string value,float y,unsigned points,float x = 16) {
                    y -= hexScroll;
                    if (y >= 52 && y+points <= bottom)
                        label(window,font,value,panel.position+sf::Vector2f(x,y),points);
                };
                hexCountryButton = {};
                if (!multiple && tile.owner >= 0 && tile.owner < int(world.profiles.size()) && hexScroll <= 1.f) {
                    hexCountryButton = {panel.position+sf::Vector2f{12,51-hexScroll},{panel.size.x-24,18}};
                    box(window,hexCountryButton.position,hexCountryButton.size,sf::Color::Transparent,{118,146,176});
                }
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
                defenseMoveButtons.clear();
                if (!aviation.empty()) {
                    panelLine("Авиация/ПВО",aviationY,14);
                    rowY = aviationY+20;
                    for (std::size_t row = 0; row < aviation.size(); ++row) {
                        panelLine(aviation[row],rowY,11);
                        const auto button = defenseRows.find(row);
                        if (button != defenseRows.end() && rowY-hexScroll >= 52 && rowY-hexScroll+16 <= bottom) {
                            const sf::FloatRect rect(panel.position+sf::Vector2f{panel.size.x-110,
                                std::round(rowY-hexScroll)},{90,16});
                            box(window,rect.position,rect.size,movingDefense == button->second ?
                                sf::Color(58,82,108) : sf::Color(32,42,54),{92,112,136});
                            battleLabel(window,font,"Переместить",rect.position+sf::Vector2f{45,8},10,sf::Color::White,.5f);
                            defenseMoveButtons.emplace_back(rect,button->second);
                        }
                        rowY += 16;
                    }
                }
                hexSpecializationRows.clear();
                hexSpecializationButton = {};
                if (industryTileCount > 0) {
                    panelLine("Производство",productionY,14);
                    rowY = productionY+20;
                    double efficiency = 0;
                    for (int cell : selectedTiles) {
                        const auto& selected = world.tiles[cell];
                        if (selected.buildings[hoi5::industry].area > 0 && !selected.industries.empty())
                            efficiency += std::pow(.9,selected.industries.size()-1);
                    }
                    panelLine("Эффективность: "+percent(efficiency/industryTileCount),rowY,11);
                    rowY += 16;
                    for (const auto& [sector,share] : industryAllocation) {
                        panelLine(std::string(industrySectorDisplayName(sector))+": "+
                            percent(share/industryTileCount),rowY,11);
                        rowY += 16;
                    }
                    if (hexSpecializationMode && editableIndustry) {
                        rowY += 6;
                        panelLine("Выбор категории",rowY,10);
                        rowY += 18;
                        const auto drawSector = [&](std::string_view sector) {
                            const float visibleY = rowY-hexScroll;
                            if (visibleY >= 52 && visibleY+24 <= bottom) {
                                const sf::FloatRect rect(panel.position+sf::Vector2f{16,visibleY},{panel.size.x-32,24});
                                const bool active = industryAllocation.contains(sector);
                                box(window,rect.position,rect.size,active ? sf::Color(54,76,96,190) :
                                    sf::Color(32,42,54,160),{84,108,132});
                                label(window,font,std::string(industrySectorDisplayName(sector)),rect.position+sf::Vector2f{8,4},11);
                                hexSpecializationRows.emplace_back(rect,sector);
                            }
                            rowY += 29;
                        };
                        for (const auto& sector : hoi5::sectors) drawSector(sector.name);
                        drawSector("consumer_goods");
                    }
                } else hexSpecializationMode = false;
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
                if (showGroundEffects) {
                    const auto delta = [](double factor) {
                        const int change = int(std::lround((factor-1.)*100));
                        return (change > 0 ? "+" : "")+std::to_string(change)+"%";
                    };
                    panelLine("Местность",rowY+6,13);
                    panelLine("Атака",rowY+25,10,152);
                    panelLine("Оборона",rowY+25,10,218);
                    panelLine("Скорость",rowY+25,10,292);
                    const auto show = [&](std::string name,double vehicles,float y) {
                        const auto effects = hoi5::groundTerrainEffects(tile.natural,vehicles);
                        panelLine(std::move(name),y,11);
                        panelLine(delta(effects.attack),y,11,152);
                        panelLine(delta(effects.defense),y,11,218);
                        panelLine(delta(effects.speed),y,11,292);
                    };
                    show("Пехота",0.,rowY+43);
                    show("Техника",1.,rowY+61);
                }
                if (editableIndustry) {
                    hexSpecializationButton = {panel.position+sf::Vector2f{16,panel.size.y-80},
                        {panel.size.x-32,28}};
                    box(window,hexSpecializationButton.position,hexSpecializationButton.size,
                        hexSpecializationMode ? sf::Color(64,92,118) : sf::Color(38,50,66),{95,118,145});
                    battleLabel(window,font,hexSpecializationMode ? "Закрыть специализацию" :
                        "Изменить специализацию",hexSpecializationButton.getCenter(),12,sf::Color::White,.5f);
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
            airDockX = float(sidePanelRight());
            airDockScale = std::clamp((size.x-airDockX-70.f)/430.f,.35f,1.f);
            auto airView = gui;
            airView.setViewport({{airDockX/size.x,1.f-airDockScale},{airDockScale,airDockScale}});
            window.setView(airView);
            if (!world.air.reserves.empty()) {
                hoi5::DebugMeasure timing(&debug,"ui_air_wing_list");
                const int count = int(cards.size());
                const auto wingBounds = wingListBounds(count);
                const float top = float(wingBounds.position.y);
                box(window,sf::Vector2f(wingBounds.position),sf::Vector2f(wingBounds.size),{17,24,34,238},{86,116,150});
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
                    const auto name = wingCompositionLabel(wing);
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
                label(window,font,wingCompositionLabel(wing)+"  "+
                    std::to_string(wing.readyCount())+"/"+std::to_string(wing.count),{110,size.y-105},12);
                label(window,font,"база "+std::to_string(wing.base%world.size)+":"+
                    std::to_string(wing.base/world.size)+" | "+wingAreaSummary(wing,world.size),{110,size.y-75},11);
            }
            if (aircraftPanel && selectedWing >= 0) {
                box(window,{20,size.y-79},{80,24},wingAreaMode ? sf::Color(60,78,98) :
                    sf::Color(30,39,50),{92,112,136});
                battleLabel(window,font,"Район",{60,size.y-67},12,sf::Color::White,.5f);
                box(window,{20,size.y-50},{80,24},editingWing == selectedWing ?
                    sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                label(window,font,"Ред.",{42,size.y-47},13);
                box(window,{110,size.y-50},{90,24},wingRebaseMode ? sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                label(window,font,"База",{131,size.y-47},13);
                box(window,{205,size.y-50},{75,24},targetingWing == selectedWing ?
                    sf::Color(60,78,98) : sf::Color(30,39,50),{92,112,136});
                label(window,font,"Цели",{223,size.y-47},13);
                const auto& wing = world.air.wings[selectedWing];
                using Risk = hoi5::AirRisk;
                const char* risk = wing.risk == Risk::cautious ? "Осторожно" :
                    wing.risk == Risk::aggressive ? "Агрессивно" : "Нормально";
                box(window,{290,size.y-79},{126,24},riskMenuWing == selectedWing
                    ? sf::Color(58,82,108) : sf::Color(32,42,54),{92,112,136});
                label(window,font,risk,{298,size.y-76},13);
                box(window,{290,size.y-50},{126,24},missionMenuWing == selectedWing
                    ? sf::Color(58,82,108) : sf::Color(32,42,54),{92,112,136});
                battleLabel(window,font,"Миссии",{353,size.y-38},12,sf::Color::White,.5f);
            }
            if (!aircraftPanel || selectedWing != missionMenuWing || targetingWing >= 0 ||
                editingWing >= 0 || wingCreationOpen) missionMenuWing = -1;
            if (!aircraftPanel || selectedWing != riskMenuWing || targetingWing >= 0 ||
                editingWing >= 0 || wingCreationOpen) riskMenuWing = -1;
            if (riskMenuWing >= 0) {
                const auto risk = world.air.wings[riskMenuWing].risk;
                const float top = wingCreationBottom()-wingRiskMenuHeight;
                box(window,{10,top},{420,float(wingRiskMenuHeight)},{18,24,32,244},{96,122,150});
                label(window,font,"Режим риска",{22,top+6},13);
                for (int i = 0; i < int(wingRiskOptions.size()); ++i) {
                    const auto [value,name] = wingRiskOptions[i];
                    const float y = top+29+27*i;
                    const bool selected = risk == value;
                    box(window,{20,y},{400,24},selected ? sf::Color(48,72,58,230) :
                        sf::Color(30,42,54,220),{78,102,128});
                    if (selected) battleLabel(window,font,"✓",{35,y+12},11,{180,238,166},.5f);
                    battleLabel(window,font,name,{52,y+12},10);
                }
            }
            if (missionMenuWing >= 0) {
                auto& wing = world.air.wings[missionMenuWing];
                const float top = wingCreationBottom()-wingMissionMenuHeight;
                box(window,{10,top},{420,float(wingMissionMenuHeight)},{18,24,32,244},{96,122,150});
                label(window,font,"Автоматические миссии",{22,top+6},13);
                for (int i = 0; i < int(wingMissionNames.size()); ++i) {
                    const auto* mission = wingMission(wing,i);
                    const bool checked = mission && *mission;
                    const float y = top+29+27*i;
                    box(window,{20,y},{400,24},checked ? sf::Color(48,82,60,230) :
                        mission ? sf::Color(42,62,78,220) : sf::Color(34,36,40,180),{78,102,128});
                    box(window,{28,y+5},{14,14},sf::Color::Transparent,
                        mission ? sf::Color(190,206,220) : sf::Color(104,112,122));
                    if (checked) battleLabel(window,font,"✓",{35,y+12},11,{180,238,166},.5f);
                    battleLabel(window,font,wingMissionNames[i],{50,y+12},10,
                        mission ? sf::Color::White : sf::Color(128,136,145));
                    if (!mission) battleLabel(window,font,"недоступно",{412,y+12},9,{150,158,168},1.f);
                }
            }
            if (!aviationMessage.empty())
                label(window,font,aviationMessage,{25,float(wingCreationBottom()-21)},14);
            if (targetingWing >= 0 && targetingWing == selectedWing) {
                const auto& priorities = world.air.wings[targetingWing].targetPriorities;
                const float top = wingCreationBottom()-airTargetMenuHeight;
                box(window,{10,top},{420,float(airTargetMenuHeight)},{18,24,32,244},{96,122,150});
                label(window,font,"Список целей для миссии Удар",{22,top+6},13);
                const bool allSelected = std::ranges::all_of(airTargetOptions,[&](const auto& option) {
                    return std::ranges::find(priorities,option.first) != priorities.end();
                });
                box(window,{20,top+29},{400,24},allSelected ? sf::Color(50,70,92,230) :
                    sf::Color(36,50,66,225),{102,136,170});
                battleLabel(window,font,"Выбрать все",{32,top+41},10);
                battleLabel(window,font,"все категории",{412,top+41},9,{174,194,212},1.f);
                for (int i = 0; i < int(std::size(airTargetOptions)); ++i) {
                    const auto [key,name] = airTargetOptions[i];
                    const bool enabled = std::ranges::find(priorities,key) != priorities.end();
                    const float y = top+29+27*(i+1);
                    box(window,{20,y},{400,24},enabled ? sf::Color(48,72,58,230) :
                        sf::Color(30,42,54,220),{78,102,128});
                    box(window,{28,y+5},{14,14},sf::Color::Transparent,{190,206,220});
                    if (enabled) battleLabel(window,font,"✓",{35,y+12},11,{180,238,166},.5f);
                    battleLabel(window,font,std::string(name),{50,y+12},10);
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
            window.setView(gui);
            box(window,{size.x-62,size.y-62},{44,44},{18,24,31,235},{92,112,136});
            sf::Sprite sprite(layers);
            sprite.setPosition({size.x-56,size.y-56});
            sprite.setScale({32.f/layers.getSize().x,32.f/layers.getSize().y});
            window.draw(sprite);
            if (constructionPanel && constructionPlacement &&
                (hoi5::constructionSpecs[buildingSpec].building == hoi5::airbase ||
                 hoi5::constructionSpecs[buildingSpec].building == hoi5::fieldHelipad)) {
                const float x = size.x-294;
                box(window,{x,172},{282,142},{18,24,31,235},{92,112,136});
                battleLabel(window,cardFont,"Дальность авиации",{x+12,186},17);
                for (int i = 0; i < int(constructionAirColors.size()); ++i) {
                    auto color = constructionAirColors[i];
                    color.a = 255;
                    const float y = 206+17.f*i;
                    box(window,{x+12,y-3},{12,6},color);
                    battleLabel(window,cardFont,std::string(hoi5::aircraftNames[i]),{x+34,y},14,color);
                }
            }
            const float economyTarget = economicPanel == 1 ? 1.f : 0.f;
            economyPanelProgress += (economyTarget-economyPanelProgress)*std::min(1.f,dt*12);
            if (std::abs(economyPanelProgress-economyTarget) < .01f) economyPanelProgress = economyTarget;
            if (economyPanelProgress > 0) {
                hoi5::DebugMeasure timing(&debug,"ui_side_panel");
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
                    points += 2;
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
                const double trade = world.economyCurrent.empty() ? 0. : world.economyCurrent.front().trade;
                const double budget = world.profiles[0].budget, balance = flows.balance()+trade;
                const auto* previous = world.economyPrevious.empty() ? nullptr : &world.economyPrevious.front();
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
                item("Возврат кредитов",flows.loanRepayments,false,prior([](const auto& p) { return p.flows.loanRepayments; }));
                item("Всего доходов",flows.population+flows.companies+trade+flows.loanRepayments,false,
                    prior([](const auto& p) { return p.flows.population+p.flows.companies+p.trade+p.flows.loanRepayments; }));
                row += 8;
                section("Расходы");
                item("Армия",flows.army,true);
                item("Правительство",flows.government,true,prior([](const auto& p) { return p.flows.government; }));
                item("Соц. обеспечение",flows.social,true,prior([](const auto& p) { return p.flows.social; }));
                const double millions = world.profiles[0].population/1e6;
                item("  Пенсии",flows.pensions,true,prior([](const auto& p) { return p.flows.pensions; }));
                item("  Дети/школы",flows.children,true,prior([](const auto& p) { return p.flows.children; }));
                item("  Инвалиды",flows.disability,true,prior([](const auto& p) { return p.flows.disability; }));
                item("  Соцслужбы",flows.localServices,true,prior([](const auto& p) { return p.flows.localServices; }));
                item("Инфраструктура",flows.infrastructure,true,prior([](const auto& p) { return p.flows.infrastructure; }));
                item("Программы поддержки",flows.politicalPrograms,true,
                    prior([](const auto& p) { return p.flows.politicalPrograms; }));
                item("Платежи по кредитам",flows.debtService,true,prior([](const auto& p) { return p.flows.debtService; }));
                item("Всего расходов",flows.expenses(),true,prior([](const auto& p) { return p.flows.expenses(); }));
                row += 8;
                section("Итог и показатели");
                item("Месячный баланс",balance,false,prior([](const auto& p) { return p.flows.balance()+p.trade; }));
                text("Население",content+8,row,11,{214,224,234});
                const double population = world.profiles[0].population;
                const auto populationDelta = previous ? std::optional(population-previous->population) : std::nullopt;
                text(formatAmount(population),width-178,row,11,{210,222,234},true);
                text(formatPopulationDelta(populationDelta),width-18,row,11,
                    populationDelta.value_or(0.) >= 0. ? good : bad,true);
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
            if (economicPanel == 2) {
                hoi5::DebugMeasure timing(&debug,"panel_resources");
                if (!resourceForecast) resourceForecast = world.forecastResources(0,simulation.marketTickCount);
                const auto& forecast = *resourceForecast;
                if (groundResourcesDirty) {
                    groundResources.clear();
                    for (const auto& tile : world.tiles)
                        if (tile.owner == 0)
                            for (const auto& deposit : tile.deposits) groundResources[deposit.resource] += deposit.mass;
                    groundResourcesDirty = false;
                }
                box(window,{0,90},{760,float(resourcePanelBottom()-90)},{18,24,31,250},{92,112,136});
                label(window,font,"Ресурсы",{18,103},22);
                const auto& stocks = world.stockpiles[0];
                std::array<std::vector<std::string_view>,2> warnings;
                for (int i = 0; i < int(resourceCategories.size()); ++i) {
                    int severity = 0, shortage = 0, surplus = 0;
                    for (const auto key : resourceCategoryKeys(i)) {
                        const double stock = hoi5::value(stocks,key);
                        const double input = hoi5::value(forecast.required,key);
                        const double output = hoi5::value(forecast.outputs,key);
                        const int level = resourceShortageLevel(stock,input-output);
                        severity = std::max(severity,level);
                        shortage += level > 0;
                        if (level > 0) warnings[2-level].push_back(key);
                        surplus += input > 0 && stock/input >= 6;
                    }
                    const float x = 18+i*168.f;
                    auto fill = std::array{sf::Color(38,82,54,215),sf::Color(112,92,42,225),
                        sf::Color(112,42,42,225)}[severity];
                    if (i == resourceCategory) {
                        const auto alpha = fill.a;
                        fill = blendMapColors(fill,sf::Color::White,.12);
                        fill.a = alpha;
                    }
                    box(window,{x,136},{162,62},fill,{120,142,166});
                    label(window,cardFont,resourceCategories[i],{x+8,139},18);
                    battleLabel(window,cardFont,"Недостаток: "+std::to_string(shortage),{x+8,168},14,{226,234,242});
                    battleLabel(window,cardFont,"Избыток: "+std::to_string(surplus),{x+8,185},14,{180,222,166});
                }
                label(window,cardFont,"Склады и снабжение",{18,204},18);
                hoi5::Stockpile used;
                for (const auto& [key,amount] : stocks) used[hoi5::storageBucket(key)] += amount;
                constexpr std::pair<std::string_view,std::string_view> buckets[]{
                    {"raw","Сырье"},{"semi_finished","Полуфабрикаты"},{"finished","Готовая продукция"},{"fuel","Топливо"}
                };
                const auto storageLine = [&](int i) {
                    const auto [key,name] = buckets[i];
                    const double stock = hoi5::value(used,key);
                    const double capacity = hoi5::value(world.capacities[0],key);
                    const double fullness = capacity > 0 ? stock/capacity : double(stock > 0);
                    return std::string(name)+" "+resourceAmountLabel(stock)+"/"+resourceAmountLabel(capacity)+
                        " ("+std::to_string(int(std::nearbyint(fullness*100)))+"%)";
                };
                for (int i = 0; i < 4; ++i)
                    battleLabel(window,cardFont,storageLine(i),{18.f+252.f*(i%2),238.f+18.f*(i/2)},14,{190,210,224});
                double supply = 0;
                int land = 0, low = 0, critical = 0;
                for (const auto& tile : world.tiles) {
                    if (tile.owner != 0 || tile.water || tile.natural.water > .55) continue;
                    ++land;
                    supply += tile.supply;
                    if (tile.supply < .25) ++critical;
                    else if (tile.supply < .50) ++low;
                }
                battleLabel(window,font,"Снабжение: "+std::to_string(int(std::nearbyint(supply*100/std::max(1,land))))+
                    "% | слабых: "+std::to_string(low)+" | крит.: "+std::to_string(critical),
                    {18,278},14,{190,210,224});
                resourceWarnings.clear();
                for (int severity : {2,1})
                    for (auto key : warnings[2-severity])
                        if (resourceWarnings.size() < 3) resourceWarnings.emplace_back(severity,key);
                if (resourceWarnings.empty())
                    battleLabel(window,font,"Все спокойно",{48,resourceWarningsTop+8},11,{180,192,205});
                for (std::size_t row = 0; row < resourceWarnings.size(); ++row) {
                    const auto [severity,key] = resourceWarnings[row];
                    const float y = resourceWarningsTop+row*resourceWarningHeight;
                    box(window,{42,y},{360,resourceWarningHeight},severity == 2 ? sf::Color(92,42,42,145) :
                        sf::Color(92,76,34,135));
                    battleLabel(window,font,(severity == 2 ? "Критично: " : "Внимание: ")+
                        std::string(resourceDisplayName(key)),{48,y+8},11,{238,198,90});
                }
                constexpr std::array columns{18.f,184.f,266.f,326.f,384.f,446.f};
                constexpr std::array headers{"Ресурс","В земле","Склад","+/мес","-/мес","Хватит"};
                for (std::size_t column = 0; column < columns.size(); ++column)
                    battleLabel(window,cardFont,headers[column],{columns[column],384},13,{150,166,184});
                const auto keys = resourceKeys();
                const int visibleRows = resourceVisibleRows();
                resourceScroll = std::clamp(resourceScroll,0,std::max(0,int(keys.size())-visibleRows));
                for (int row = 0; row < visibleRows && row+resourceScroll < int(keys.size()); ++row) {
                    const auto key = keys[row+resourceScroll];
                    const double amount = hoi5::value(stocks,key);
                    const double output = hoi5::value(forecast.outputs,key);
                    const double input = hoi5::value(forecast.required,key);
                    const float y = resourceRowsTop+row*resourceRowHeight;
                    const auto fill = key == selectedMapResource ? sf::Color(44,58,74,180) :
                        (row+resourceScroll)%2 == 0 ? sf::Color(24,32,42,120) : sf::Color(30,38,48,120);
                    box(window,{12,y},{495,float(resourceRowHeight)},fill);
                    const auto duration = resourceDurationMonths(amount,output,input);
                    const std::array values{std::string(resourceDisplayName(key)),
                        resourceCategory == 0 ? resourceAmountLabel(hoi5::value(groundResources,key)) : "--",
                        resourceAmountLabel(amount),resourceAmountLabel(output),resourceAmountLabel(input),
                        formatResourceDuration(duration)};
                    for (std::size_t column = 0; column < columns.size(); ++column)
                        battleLabel(window,cardFont,values[column],{columns[column],y+13},column == 0 ? 16 : 13,
                            column == 5 ? resourceDurationColor(duration) : sf::Color(220,230,240));
                }
                if (int(keys.size()) > visibleRows) {
                    const float track = visibleRows*resourceRowHeight;
                    const float thumb = std::max(24.f,track*visibleRows/keys.size());
                    const float offset = (track-thumb)*resourceScroll/(keys.size()-visibleRows);
                    box(window,{515,resourceRowsTop},{4,track},{42,52,64,180});
                    box(window,{513,resourceRowsTop+offset},{8,thumb},{130,154,184,220});
                }
                if (!selectedMapResource.empty()) {
                    const auto card = resourceCardRect();
                    const float left = card.position.x;
                    const float top = card.position.y;
                    box(window,card.position,card.size,{22,29,38,230},{100,126,155});
                    const auto close = resourceCardClose();
                    box(window,close.position,close.size,{50,58,68},{150,166,184});
                    label(window,font,"X",close.position+sf::Vector2f{7,3},12);
                    label(window,font,std::string(resourceDisplayName(selectedMapResource)),{left+14,top+26},15);
                    label(window,font,"Источники: "+std::to_string(resourceSources)+" клетки",{left+14,top+62},12);
                    const auto& production = forecast.stages;
                    const auto flow = [&](hoi5::ProductionStage stage,bool output) {
                        return hoi5::value(output ? production[stage].outputs : production[stage].inputs,
                            selectedMapResource);
                    };
                    float y = top+92;
                    sf::Text measure(font,"",13);
                    const auto wrapped = [&](const std::string& text,float x,sf::Color color,int maxChars = 0,
                                             int maxLines = 0,unsigned points = 13) {
                        measure.setCharacterSize(points);
                        std::istringstream words(text);
                        std::string line, word;
                        int lines = 0;
                        const auto drawLine = [&] {
                            battleLabel(window,font,line,{x,y+6},points,color);
                            ++lines;
                            y += points+6;
                        };
                        while (words >> word) {
                            const auto candidate = line.empty() ? word : line+" "+word;
                            const auto text = sf::String::fromUtf8(candidate.begin(),candidate.end());
                            measure.setString(text);
                            const bool tooWide = measure.getLocalBounds().size.x > left+card.size.x-x-12;
                            if (!line.empty() && (tooWide || (maxChars > 0 && int(text.getSize()) > maxChars))) {
                                drawLine();
                                if (maxLines > 0 && lines >= maxLines) return;
                                line = word;
                            } else line = candidate;
                        }
                        if (!line.empty()) drawLine();
                    };
                    const auto breakdown = [&](std::string_view title,std::string_view empty,const auto& entries,
                                               bool showEmptyConstruction = false) {
                        label(window,font,std::string(title),{left+14,y},12);
                        y += 20;
                        double total = 0;
                        for (const auto& [name,amount] : entries) total += amount;
                        if (total <= 0) wrapped(std::string(empty),left+20,{180,192,205});
                        else for (const auto& [name,amount] : entries) {
                            if (amount <= 0 && !(showEmptyConstruction && name == "Стройки")) continue;
                            const auto percent = std::to_string(int(std::nearbyint(amount/total*100)));
                            wrapped(std::string(name)+": "+percent+"% ("+resourceAmountLabel(amount)+"/мес)",
                                left+20,{206,218,230});
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
                        Entry{"Экспорт",hoi5::value(forecast.exports,selectedMapResource)}},true);
                    label(window,font,"Описание",{left+14,y},15);
                    y += 24;
                    wrapped(std::string(hoi5::resourceUsageDescription(selectedMapResource)),left+14,
                        {196,208,220},29,6,15);
                    const auto trade = resourceCardTrade();
                    box(window,trade.position,trade.size,{48,72,94},{132,170,206});
                    battleLabel(window,font,"Перейти в торговлю",trade.position+sf::Vector2f{trade.size.x*.5f,14},
                        13,{228,238,247},.5f);
                }
            }
            const float armyTarget = militaryPanel ? 1.f : 0.f;
            armyPanelProgress += (armyTarget-armyPanelProgress)*std::min(1.f,dt*12);
            if (armySmoke || std::abs(armyPanelProgress-armyTarget) < .01f ||
                (!militaryPanel && (economicPanel || constructionPanel || diplomacyPanel || tradePanel)))
                armyPanelProgress = armyTarget;
            if (armyPanelProgress > 0.) {
                const auto bounds = armyBounds();
                hoi5::DebugMeasure timing(&debug,"ui_side_panel");
                const float top = float(bounds.position.y), bottom = top+bounds.size.y;
                const float left = 18, right = bounds.size.x-18.f;
                auto armyView = gui;
                armyView.move({-float(bounds.position.x),0});
                window.setView(armyView);
                const auto utf8 = [](const sf::String& text) {
                    const auto value = text.toUtf8();
                    return std::string(value.begin(),value.end());
                };
                const auto shortText = [&](std::string_view text,std::size_t count) {
                    return utf8(sf::String::fromUtf8(text.begin(),text.end()).substring(0,count));
                };
                const auto decimal = [](double value,int precision = 0) {
                    std::ostringstream out;
                    out << std::fixed << std::setprecision(precision) << value;
                    return out.str();
                };
                const auto coordinates = [&](int tile) {
                    return "("+std::to_string(tile%world.size)+", "+std::to_string(tile/world.size)+")";
                };
                constexpr sf::Color ink{210,224,236}, muted{150,166,184}, gold{240,203,130}, green{160,223,170}, red{241,151,125};
                armyHits.clear();
                box(window,{0,top},sf::Vector2f(bounds.size),{18,24,31,244},{110,130,154});
                battleLabel(window,cardFont,"Армия",{18,top+28},24,{238,244,250});
                const auto button = [&](std::string caption,int x,int y,int width,std::function<void()> activate,
                                        int height = 22,bool selectedTab = false,unsigned points = 13) {
                    if (y < top || y+height > bottom) return;
                    box(window,{float(x),float(y)},{float(width),float(height)},
                        selectedTab ? sf::Color(66,94,120) : sf::Color(42,57,72),
                        selectedTab ? sf::Color(176,211,240) : sf::Color(110,130,154));
                    battleLabel(window,cardFont,caption,{x+6.f,y+height*.5f},points,{225,234,244});
                    armyHits.push_back({{{x+bounds.position.x,y},{width,height}},std::move(activate)});
                };
                button("X",382,int(top)+10,28,[&] {
                    militaryPanel = armyPickingSite = armyNameFocus = false;
                    armyHits.clear();
                },28);
                constexpr std::array tabs{"Сводка","Конструктор","Набор"};
                for (int i = 0; i < int(tabs.size()); ++i)
                    button(tabs[i],18+128*i,int(top)+62,126,[&,i] {
                        armyTab = ArmyTab(i);
                        armyPickingSite = false;
                        armyHits.clear();
                    },28,armyTab == ArmyTab(i),16);
                float y = top+108;
                    const auto line = [&](std::string caption,sf::Color color = {210,224,236},unsigned points = 16) {
                    if (y+12 < bottom) battleLabel(window,cardFont,caption,{left,y},points,color);
                    y += 20;
                };
                const auto& stock = world.stockpiles[0];
                if (armyTab == ArmyTab::overview) {
                    int divisions = 0;
                    double org = 0., strength = 0.;
                    hoi5::Stockpile equipment, capacity;
                    for (const auto& unit : world.divisions) {
                        if (unit.owner != 0 || unit.combat.strength <= 0.) continue;
                        ++divisions;
                        org += unit.organization;
                        strength += unit.combat.strength;
                        for (const auto& [key,amount] : unit.supplies) equipment[key] += std::max(0.,amount);
                        for (const auto& [key,amount] : unit.design->capacity) capacity[key] += std::max(0.,amount);
                    }
                    y -= 8;
                    line("Сводка армии",sf::Color::White,20);
                    y += 4;
                    const std::array<std::pair<std::string_view,std::string>,6> stats{{
                        {"Дивизии",std::to_string(divisions)},{"Армии",std::to_string(std::ranges::count(world.armies,0,&World::Army::owner))},
                        {"Выбрано",std::to_string(selectedDivisions.size())},{"Резерв людей",resourceAmountLabel(world.manpowerReserve[0])},
                        {"Средняя орг.",decimal(org/std::max(1,divisions))+"%"},
                        {"Средняя прочн.",decimal(strength/std::max(1,divisions))+"%"}
                    }};
                    for (int i = 0; i < int(stats.size()); ++i) {
                        const float x = left+(i%2)*222;
                        const float row = y+(i/2)*22;
                        battleLabel(window,cardFont,std::string(stats[i].first),{x,row},14,muted);
                        battleLabel(window,cardFont,stats[i].second,{x+205,row+16},14,ink,1.f);
                    }
                    y += 82;
                    box(window,{left,y-14},{right-left,1},{72,92,112,180});
                    line("Армейские ресурсы",sf::Color::White,20);
                    y += 14;
                    const auto columns = [&](std::string a,std::string b,std::string c,sf::Color color = {210,224,236}) {
                        if (y+12 < bottom) {
                            battleLabel(window,cardFont,a,{left,y},16,ink);
                            battleLabel(window,cardFont,b,{left+246,y},16,ink,1.f);
                            battleLabel(window,cardFont,c,{right,y},16,color,1.f);
                        }
                        y += 19;
                    };
                    columns("Ресурс","Склад","В дивизиях",muted);
                    constexpr std::array<std::string_view,18> resources{"weapons","infantry_equipment","old_assault_rifles","small_arms_ammo",
                        "old_light_artillery","light_artillery_ammo","old_light_aa_artillery","light_aa_ammo","old_ifv","old_at_missiles",
                        "autocannon_ammo","artillery_ammo","tank_ammo","anti_air_ammo","vehicles","refined_fuel","spare_parts","field_supplies"};
                    for (const auto key : resources) {
                        const double stored = hoi5::value(stock,key), held = hoi5::value(equipment,key), max = hoi5::value(capacity,key);
                        if (stored <= 0 && held <= 0 && max <= 0 && key.find("ammo") == std::string_view::npos &&
                            key != "refined_fuel" && key != "field_supplies") continue;
                        const double ratio = max > 0 ? held/max : 1.;
                        columns(std::string(resourceDisplayName(key)),resourceAmountLabel(stored),
                            resourceAmountLabel(held)+"/"+resourceAmountLabel(max),ratio >= .65 ? green : ratio >= .30 ? gold : red);
                    }
                    if (!world.air.reserves.empty()) {
                        const auto& reserves = world.air.reserves[0];
                        decltype(world.air.reserves)::value_type based{};
                        for (const auto& wing : world.air.wings)
                            if (wing.owner == 0)
                                for (int i = 0; i < int(based.size()); ++i) based[i] += wing.typeCount(i);
                        if (std::ranges::any_of(based,[](int count) { return count > 0; }) ||
                            std::ranges::any_of(reserves,[](int count) { return count > 0; })) {
                            y += 8;
                            box(window,{left,y-14},{right-left,1},{72,92,112,180});
                            line("Авиационный парк",sf::Color::White,20);
                            y += 14;
                            columns("Тип","На базах","Резерв",muted);
                            std::array<int,std::size(hoi5::aircraftTypes)> order{};
                            std::iota(order.begin(),order.end(),0);
                            std::ranges::sort(order,{},[](int i) { return hoi5::aircraftTypes[i].key; });
                            for (const int i : order)
                                if (based[i] || reserves[i])
                                    columns(shortText(hoi5::aircraftNames[i],25),std::to_string(based[i]),std::to_string(reserves[i]));
                        }
                    }
                } else if (armyTab == ArmyTab::designer) {
                    button(utf8(armyDesignName)+(armyNameFocus ? " |" : " (изменить)"),18,int(y)-12,444,[&] { armyNameFocus = true; },30,false,16);
                    y += 34;
                    line("Батальоны: от 1 до 20; 10 одного типа = готовый тип");
                    for (int i = 0; i < World::baseDivisionTypes; ++i) {
                        auto caption = std::string(hoi5::divisionTemplates[i].name);
                        if (const auto suffix = caption.find(" дивизия"); suffix != std::string::npos) caption.erase(suffix);
                        battleLabel(window,cardFont,shortText(caption,25),{left,y},15,ink);
                        if (sf::IntRect({int(left)+bounds.position.x,int(y)-12},{280,24}).contains(sf::Mouse::getPosition(window))) {
                            constexpr std::array descriptions{
                                "Основа пехотного строя. Хорошая оборона и меньшая зависимость от бронетехники.",
                                "Броня, прорыв и атака по броне. Требует больше топлива и запчастей.",
                                "Быстрее остальных типов. Мобильная пехота уступает танкам в броне и прорыве.",
                                "Противотанковые средства повышают атаку по броне и пробитие. Меньше атака по пехоте.",
                                "Зенитное прикрытие дивизии. Повышает атаку по верхней проекции и требует зенитных боеприпасов."
                            };
                            hoi5::DivisionComposition part{};
                            part[i] = 1;
                            const auto stats = hoi5::composeDivision(part,{});
                            const auto& c = stats.combat;
                            auto lines = countryTextLines(descriptions[i],52);
                            lines.push_back("Люди: "+std::to_string(stats.manpower)+" · ширина "+decimal(c.width,1)+
                                " · скорость "+decimal(stats.speed,2));
                            lines.push_back("Атака по пехоте / броне / сверху: "+decimal(c.softAttack,1)+"/"+
                                decimal(c.frontAttack,1)+"/"+decimal(c.topAttack,1));
                            lines.push_back("Оборона: "+decimal(c.defense,1)+" · прорыв: "+decimal(c.breakthrough,1));
                            lines.push_back("Броня: "+decimal(c.frontArmor,1)+" · пробитие: "+decimal(c.frontPiercing,1));
                            hoverHelp = HoverHelp{caption,std::move(lines)};
                        }
                        button("−",302,int(y)-11,26,[&,i] { if (armyDraft[i] > 0) --armyDraft[i]; });
                        battleLabel(window,cardFont,std::to_string(armyDraft[i]),{340,y},15,gold);
                        button("+",374,int(y)-11,26,[&,i] {
                            if (std::accumulate(armyDraft.begin(),armyDraft.end(),0) < 20) ++armyDraft[i];
                        });
                        y += 28;
                    }
                    const auto preview = hoi5::composeDivision(armyDraft,{});
                    if (preview.manpower <= 0) line("В дивизии должно быть от 1 до 20 батальонов",red);
                    else {
                        const auto& c = preview.combat;
                        line("Люди: "+std::to_string(preview.manpower)+"  Ширина: "+decimal(c.width,1)+"  Скорость: "+decimal(preview.speed,2));
                        line("Пехотная атака: "+decimal(c.softAttack,1)+"  Защита: "+decimal(c.defense,1));
                        line("Прорыв: "+decimal(c.breakthrough,1)+"  Броня: "+decimal(c.frontArmor,1));
                        line("Атака брони: "+decimal(c.frontAttack,1)+"  Пробитие: "+decimal(c.frontPiercing,1));
                        line("Организация: "+decimal(preview.organization)+"  Восстановление: "+decimal(preview.recovery,1));
                        line("Подготовка: "+std::to_string(World::trainingHours(preview)/24)+" суток; "+formatMoney(World::trainingCost(preview)));
                        button("Сохранить шаблон и перейти к набору",18,int(y)-10,384,[&] {
                            if (world.playerDesigns.size() >= 64) {
                                militaryMessage = "Достигнут предел 64 шаблона";
                                return;
                            }
                            if (std::accumulate(armyDraft.begin(),armyDraft.end(),0) == 0) return;
                            auto name = armyDesignName.toUtf8();
                            const auto first = name.find_first_not_of(' ');
                            if (first != decltype(name)::npos) name = name.substr(first,name.find_last_not_of(' ')-first+1);
                            else name.clear();
                            world.playerDesigns.push_back(std::make_shared<hoi5::SavedDivisionDesign>(
                                name.empty() ? "Смешанная дивизия" : std::string(name.begin(),name.end()),armyDraft));
                            armyType = World::baseDivisionTypes+int(world.playerDesigns.size())-1;
                            armyTab = ArmyTab::recruit;
                            armyScroll = 0;
                            militaryMessage = "Шаблон сохранён";
                            armyHits.clear();
                        });
                        y += 42;
                        line(shortText(militaryMessage,65),gold);
                    }
                } else {
                    const auto& design = world.trainingDesign(armyType);
                    line(shortText(design.name,44),ink,17);
                    for (const int direction : {-1,1})
                        button(direction < 0 ? "< Шаблон" : "Шаблон >",direction < 0 ? 18 : 138,int(y)-10,110,[&,direction] {
                            const int count = World::baseDivisionTypes+int(world.playerDesigns.size());
                            armyType = (armyType+direction+count)%count;
                            armyScroll = 0;
                            armyHits.clear();
                        });
                    button("Изменить",308,int(y)-10,94,[&] {
                        const auto name = world.trainingDesign(armyType).name;
                        armyDesignName = sf::String::fromUtf8(name.begin(),name.end());
                        armyDraft = world.trainingComposition(armyType);
                        armyTab = ArmyTab::designer;
                        armyPickingSite = false;
                        armyHits.clear();
                    });
                    y += 34;
                    auto reserve = decimal(world.manpowerReserve[0]);
                    for (int i = int(reserve.size())-3; i > 0; i -= 3) reserve.insert(std::size_t(i)," ");
                    line(std::to_string(design.manpower)+" человек; резерв "+reserve);
                    line("Цена: "+formatMoney(World::trainingCost(design))+"; срок: "+std::to_string(World::trainingHours(design)/24)+" суток");
                    line(armySite < 0 ? "Гекс развёртывания не выбран" : "Развёртывание: "+coordinates(armySite));
                    const auto beginSite = [&](int project) {
                        return [&,project] {
                            armyProject = project;
                            armyPickingSite = true;
                            wingAreaMode = wingRebaseMode = false;
                            divisionDragStart.reset();
                            divisionDragActive = dragging = false;
                            selectedTiles.clear();
                            militaryMessage = "Укажите свою снабжаемую клетку: ЛКМ; отмена — ESC / ПКМ";
                        };
                    };
                    button(armyPickingSite ? "ЛКМ по гексу; ESC / ПКМ — отмена" : "Выбрать гекс на карте (ЛКМ)",
                        18,int(y)-10,384,beginSite(0));
                    y += 30;
                    button("Начать подготовку",18,int(y)-10,384,[&] {
                        if (armySite < 0) militaryMessage = "Сначала выберите гекс развёртывания на карте";
                        else {
                            militaryMessage = world.train(0,armySite,armyType);
                            if (militaryMessage == "Подготовка начата")
                                militaryMessage = "Подготовка начата; люди, деньги и оснащение зарезервированы";
                            world.updateStatus();
                        }
                    });
                    y += 32;
                    line(shortText(militaryMessage,65),gold);
                    std::vector<const TrainingProject*> projects;
                    for (const auto& project : world.training)
                        if (project.country == 0) projects.push_back(&project);
                    const int lastPage = std::max(0,(int(projects.size())-1)/3);
                    armyPage = std::clamp(armyPage,0,lastPage);
                    if (lastPage)
                        for (const int direction : {-1,1})
                            button(direction < 0 ? "<" : ">",direction < 0 ? 342 : 374,int(y)-10,26,[&,direction,lastPage] {
                                armyPage = std::clamp(armyPage+direction,0,lastPage);
                                armyHits.clear();
                            });
                    line("Параллельная подготовка: "+std::to_string(projects.size())+"  ·  "+
                        std::to_string(armyPage+1)+"/"+std::to_string(lastPage+1));
                    for (int i = armyPage*3; i < std::min(int(projects.size()),armyPage*3+3); ++i) {
                        const auto& project = *projects[i];
                        const auto& trained = world.trainingDesign(project.type);
                        const int duration = World::trainingHours(trained);
                        auto caption = shortText(trained.name,22)+": "+decimal(100.*project.hours/duration)+"%";
                        if (project.hours >= duration && !world.safeTrainingSite(0,project.tile)) caption += " — нет места";
                        battleLabel(window,cardFont,caption,{left,y},13,ink);
                        button("Гекс",282,int(y)-11,48,beginSite(project.id));
                        button("Отмена",336,int(y)-11,66,[&,id=project.id] {
                            const auto item = std::ranges::find(world.training,id,&TrainingProject::id);
                            if (item == world.training.end() || item->country != 0) return;
                            world.cancelTraining(std::size_t(item-world.training.begin()));
                            militaryMessage = "Набор отменён; люди, оснащение и неистраченные деньги возвращены";
                            world.updateStatus();
                            armyHits.clear();
                        });
                        y += 18;
                        line("Место: "+coordinates(project.tile),muted,12);
                        y += 4;
                    }
                    line("Оснащение: нужно / склад (прокрутка колесом)");
                    const int visible = std::max(1,1+int((bottom-y-18)/20));
                    const auto equipment = hoi5::divisionEquipmentOrder(world.trainingComposition(armyType));
                    armyScrollMax = std::max(0,int(equipment.size())-visible);
                    armyScroll = std::clamp(armyScroll,0,armyScrollMax);
                    for (int i = armyScroll; i < int(equipment.size()) && y <= bottom-18; ++i) {
                        const auto key = equipment[i];
                        const double needed = hoi5::value(design.capacity,key);
                        const double available = hoi5::value(stock,key);
                        line(shortText(resourceDisplayName(key),25)+": "+decimal(needed)+" / "+decimal(available),
                            available+1e-6 >= needed ? green : red);
                    }
                }
                window.setView(gui);
            }
            if (constructionPanel) {
                hoi5::DebugMeasure timing(&debug,"panel_construction");
                const auto& queue = world.construction.queues[0];
                const auto groups = hoi5::Construction::groups(queue);
                const int rows = constructionRows(int(groups.size()));
                const float offset = 150+constructionRowHeight*std::max(4,rows);
                box(window,{20,90},{float(constructionPanelWidth),410+offset},{18,24,31,250},{92,112,136});
                label(window,font,"Строительство",{30,98},25);
                box(window,{30,132},{constructionPanelWidth-44.f,28},{30,39,50},{82,108,132});
                label(window,font,!queue.empty() && queue.front().paused ? "Возобновить" : "Приостановить",
                    {38,134},19);
                if (queue.empty()) label(window,font,"Пока пусто",{38,170},19);
                for (int i = 0; i < rows; ++i) {
                    const auto [first,end] = groups[i];
                    const auto& project = queue[first];
                    const float y = constructionListTop+i*constructionRowHeight;
                    const bool active = project.status != hoi5::ConstructionStatus::queued;
                    box(window,{30,y},{constructionPanelWidth-44.f,28},active ? sf::Color(46,70,58,190) :
                        sf::Color(30,40,52,160),{82,108,132});
                    const auto title = std::string(active ? hoi5::constructionStatusLabel(project.status) : "Ждет")+
                        ": "+(project.repair ? "Ремонт: " : "")+
                        std::string(hoi5::constructionSpecs[project.spec].label)+" "+
                        std::to_string(project.tile%world.size)+":"+std::to_string(project.tile/world.size);
                    fittedBattleLabel(window,font,title+(end-first > 1 ? " x"+std::to_string(end-first) : ""),
                        {38,y+14.f},15,400,{226,236,244});
                    const auto percent = [](double value) { return std::to_string(int(std::nearbyint(value*100)))+"%"; };
                    const double coverage = std::lerp(project.from,project.target,std::clamp(project.progress,0.,1.));
                    const double target = project.repair ? 1. : queue[end-1].target;
                    battleLabel(window,font,percent(coverage)+"->"+percent(target),{470,y+14.f},
                        14,{226,236,244},1.f);
                    const auto cancel = constructionCancelButton(i);
                    const bool cancelable = !queue[end-1].paid && queue[end-1].progress <= 0;
                    box(window,cancel.position,cancel.size,cancelable ? sf::Color(92,48,52,220) :
                        sf::Color(42,45,50,160),cancelable ? sf::Color(214,130,130) : sf::Color(80,84,90));
                    battleLabel(window,font,"X",cancel.getCenter(),11,cancelable ? sf::Color(248,224,224) :
                        sf::Color(120,124,130),.5f);
                    for (int direction : {-1,1}) {
                        const auto rect = constructionPriorityButton(i,direction);
                        const bool enabled = hoi5::Construction::canMoveGroup(queue,groups,i,direction);
                        box(window,rect.position,rect.size,enabled ? sf::Color(52,70,88,210) :
                            sf::Color(34,40,48,150),enabled ? sf::Color(128,156,184,220) :
                            sf::Color(70,82,96,150));
                        battleLabel(window,font,direction < 0 ? "^" : "v",rect.getCenter(),12,
                            enabled ? sf::Color(232,240,248) : sf::Color(128,138,148),.5f);
                    }
                }
                if (groups.size() > 4)
                    label(window,font,constructionQueueExpanded ? "Свернуть очередь" :
                        "Показать еще "+std::to_string(groups.size()-rows),
                        {36,float(constructionListTop+rows*constructionRowHeight+3)},18);
                const double power = hoi5::Construction::buildPower(world.tiles,0,world.profiles[0]);
                const int activeCount = std::min(3,int(std::ranges::count_if(queue,[](const auto& project) {
                    return !project.paused;
                })));
                const auto firstActive = std::ranges::find_if(queue,[](const auto& project) { return !project.paused; });
                float detailY = 78+offset;
                if (!queue.empty()) {
                    const auto& project = firstActive == queue.end() ? queue.front() : *firstActive;
                    const bool contested = world.battles.contains(project.tile);
                    const double speed = power/std::max(1,activeCount)*hoi5::Construction::speedMultiplier(contested);
                    const auto duration = hoi5::Construction::remainingMonths(project,speed);
                    using Status = hoi5::ConstructionStatus;
                    Status status = project.repair ? Status::repairing : Status::building;
                    hoi5::Stockpile missing;
                    const double missingMoney = project.paid ? 0. : project.money-world.profiles[0].budget;
                    if (project.paused) status = Status::paused;
                    else if (missingMoney > 0) status = Status::waitingMoney;
                    else if (speed <= 0) status = Status::waitingPower;
                    else {
                        const auto delta = hoi5::Construction::progressDelta(project,speed,1./30.);
                        for (const auto& [key,amount] : hoi5::Construction::projectNeeds(project,delta)) {
                            const double shortage = amount-hoi5::value(world.stockpiles[0],key);
                            if (shortage > .001) missing[key] = shortage;
                        }
                        if (!missing.empty()) status = Status::waitingResources;
                    }
                    label(window,font,"Статус: "+std::string(hoi5::constructionStatusLabel(status)),{38,detailY},16);
                    label(window,font,"Осталось: "+formatBuildDuration(duration),{38,detailY+22},16);
                    const auto formatNeeds = [&](const hoi5::Stockpile& amounts,int limit) {
                        std::vector<std::pair<std::string_view,double>> sorted;
                        for (const auto& [key,amount] : amounts)
                            if (amount > 0) sorted.emplace_back(key,amount);
                        std::stable_sort(sorted.begin(),sorted.end(),[](const auto& a,const auto& b) {
                            return a.second > b.second;
                        });
                        std::string text;
                        const int count = std::min(limit,int(sorted.size()));
                        for (int i = 0; i < count; ++i) {
                            if (i > 0) text += ", ";
                            text += std::string(resourceDisplayName(sorted[i].first))+" "+resourceAmountLabel(sorted[i].second);
                        }
                        if (int(sorted.size()) > limit) text += ", еще "+std::to_string(sorted.size()-limit);
                        return text;
                    };
                    std::string reason;
                    if (status == Status::paused) reason = "Стройка остановлена вручную";
                    else if (status == Status::waitingMoney) reason = "Не хватает: "+formatMoney(missingMoney);
                    else if (status == Status::waitingResources) reason = "Не хватает: "+formatNeeds(missing,3);
                    else if (status == Status::waitingPower) reason = "Нет строительной мощности";
                    if (!reason.empty()) battleLabel(window,font,reason,{38,detailY+52},13,{236,178,154});
                    else {
                        if (contested) label(window,font,"Работы замедлены: бой на клетке",{38,detailY+48},13);
                        const auto delta = hoi5::Construction::progressDelta(project,speed,1.);
                        const auto needs = formatNeeds(hoi5::Construction::projectNeeds(project,delta),2);
                        if (!needs.empty()) label(window,font,"Расход/мес: "+needs,
                            {38,detailY+(contested ? 66.f : 48.f)},13);
                    }
                }
                label(window,font,"Скорость строительства",{30,detailY+82},20);
                label(window,font,std::to_string(int(std::nearbyint(power)))+" строй-очков в месяц",
                    {38,detailY+110},17);
                label(window,font,"До 3 проектов делят строймощность между собой.",{38,detailY+136},15);
                for (int i = 0; i < int(std::size(hoi5::constructionSpecs)); ++i) {
                    const float x = i%2 ? 310.f : 30.f, y = 238+offset+(i/2)*28.f;
                    box(window,{x,y},{260,26},i == buildingSpec ? sf::Color(47,71,88) : sf::Color(30,39,50));
                    label(window,font,std::string(hoi5::constructionSpecs[i].label),{x+5,y+2},15);
                }
                box(window,{30,442+offset},{540,32},constructionPlacement ? sf::Color(47,71,88) :
                    sf::Color(30,39,50),{82,108,132});
                label(window,font,constructionPlacement ? "Завершить размещение" : "Начать строительство",
                    {38,446+offset},18);
                label(window,font,constructionMessage,{30,482+offset},17);
            }
            const float countryPanelTarget = diplomacyPanel ? 1.f : 0.f;
            countryPanelProgress += (countryPanelTarget-countryPanelProgress)*std::min(1.f,dt*12);
            if (std::abs(countryPanelProgress-countryPanelTarget) < .01f ||
                (!diplomacyPanel && (economicPanel || tradePanel || constructionPanel || militaryPanel)))
                countryPanelProgress = countryPanelTarget;
            if (countryPanelProgress > 0.f) {
                const auto bounds = countryBounds();
                hoi5::DebugMeasure timing(&debug,"ui_side_panel");
                const int left = bounds.position.x;
                const float top = float(bounds.position.y), width = float(bounds.size.x);
                const auto& diplomacy = std::as_const(world.diplomacy);
                using Action = hoi5::ForeignAction;
                const auto name = [&](int country) { return std::string(world.countryNames[country]); };
                const auto status = [](const hoi5::Relation& relation) {
                    return relation.war ? "Война" : relation.treaties.contains(Action::alliance) ? "Союз" : "Мир";
                };
                const auto opinion = [](const auto& values,int country) {
                    const auto it = values.find(country);
                    return it == values.end() ? 0 : int(std::nearbyint(it->second));
                };
                const auto relationText = [&](const hoi5::Relation& relation,int country) {
                    const auto value = opinion(relation.opinion,country);
                    return std::string(value >= 0 ? "+" : "")+std::to_string(value)+
                        "; доверие "+std::to_string(int(std::nearbyint(relation.trust*100)))+"%";
                };
                const auto percent = [](double value) {
                    return std::to_string(int(std::nearbyint(value*100)))+"%";
                };
                const auto date = hoi5::politicalDate;
                const auto treatyName = [](Action treaty) -> std::string_view {
                    switch (treaty) {
                        case Action::trade: return "Торговый договор";
                        case Action::peace: return "Мирный договор";
                        case Action::alliance: return "Союз";
                        case Action::nonaggression: return "Пакт о ненападении";
                        case Action::transit: return "Разрешение на проход войск";
                        case Action::loan: return "Кредит";
                        default: return {};
                    }
                };
                countryHits.clear();
                box(window,sf::Vector2f(bounds.position),sf::Vector2f(bounds.size),{18,24,31,244},{110,130,154});
                battleLabel(window,cardFont,countryList ? "Дипломатия" : name(foreignTarget),
                    {left+18.f,top+28},24,{238,244,250});
                const auto drawButton = [&](std::string caption,sf::IntRect rect,std::function<void()> activate) {
                    box(window,sf::Vector2f(rect.position),sf::Vector2f(rect.size),{38,50,66},{95,118,145});
                    battleLabel(window,cardFont,caption,sf::Vector2f(rect.position)+sf::Vector2f(rect.size)*.5f,
                        15,{224,234,244},.5f);
                    countryHits.push_back({rect,std::move(activate)});
                };
                drawButton("X",{{left+bounds.size.x-38,int(top)+10},{28,28}},[&] {
                    diplomacyPanel = false;
                    countryHits.clear();
                });
                if (!countryList) {
                    drawButton("Страны",{{left+bounds.size.x-130,int(top)+10},{82,28}},openCountryList);
                    constexpr std::array tabs{"Сводка","Общество","Торговля","Решения","События"};
                    const int tabWidth = (bounds.size.x-24)/int(tabs.size());
                    for (int i = 0; i < int(tabs.size()); ++i) {
                        const int x = left+12+i*tabWidth;
                        drawButton(tabs[i],{{x,int(top)+50},{tabWidth-3,28}},[&,i] {
                            countryTab = CountryTab(i);
                            countryScroll = 0;
                            countryHits.clear();
                        });
                        if (int(countryTab) == i)
                            box(window,{float(x),top+76},{float(tabWidth-3),2},{110,210,155});
                    }
                }
                struct CountryRow {
                    std::string text;
                    std::function<void()> activate;
                    sf::Color ink;
                    std::string icon, help;
                };
                std::vector<CountryRow> rows;
                const auto add = [&](std::string caption,std::function<void()> activate = {},
                    sf::Color ink = {224,234,244},std::string icon = {},std::string help = {}) {
                    const float space = icon.empty() ? 40.f : 74.f;
                    for (auto& line : countryTextLines(caption,std::max(20,int((width-space)/8.f))))
                        rows.push_back({std::move(line),activate,ink,icon,help});
                };
                if (countryList) {
                    const auto ratings = world.powerRanking();
                    int wars = 0, alliances = 0, treaties = 0;
                    for (int i = 1; i < int(world.profiles.size()); ++i) {
                        const auto& relation = diplomacy.relation(0,i);
                        wars += relation.war;
                        alliances += relation.treaties.contains(Action::alliance);
                        treaties += relation.treaties.contains(Action::trade);
                    }
                    add("Государств: "+std::to_string(world.profiles.size())+"; войн: "+std::to_string(wars)+
                        "; наше место по мощи: "+std::to_string(ratings[0].rank));
                    add("Союзов: "+std::to_string(alliances)+"; торговых договоров: "+std::to_string(treaties));
                    const auto countryRow = [&](int i) {
                        const auto select = [&,i] { openCountry(i); };
                        const auto& relation = diplomacy.relation(0,i);
                        const bool warning = i != 0 && !relation.war &&
                            (diplomacy.goals.contains({0,i}) || diplomacy.goals.contains({i,0}));
                        const sf::Color color = warning ? sf::Color{246,215,130} : relation.war ?
                            sf::Color{244,148,143} : sf::Color{224,234,244};
                        add(name(i)+"   |   "+(i == 0 ? "Ваше государство" : status(relation)),select,color,
                            warning ? "!" : "Г",warning ? "Одна из сторон готовит цель войны." : "");
                        if (i != 0) add("Отношение "+relationText(diplomacy.relation(0,i),i)+". "+
                            std::string(World::relativePower(ratings[i].total,ratings[0].total)),select,color);
                    };
                    countryRow(0);
                    for (const bool war : {true,false}) {
                        if ((war ? wars : int(world.profiles.size())-1-wars) == 0) continue;
                        add(war ? "Страны в состоянии войны" : "Страны в мире",{}, {151,186,214});
                        for (int i = 1; i < int(world.profiles.size()); ++i)
                            if (diplomacy.relation(0,i).war == war) countryRow(i);
                    }
                } else {
                    const int country = foreignTarget;
                    const bool own = country == 0;
                    const auto& policy = diplomacy.countries[country];
                    const auto& relation = diplomacy.relation(0,country);
                    if (countryTab == CountryTab::summary) {
                        if (!world.rulers[country].empty()) add("Правитель: "+std::string(world.rulers[country]));
                        const std::string population = "Население: "+formatPopulation(world.profiles[country].population);
                        if (own) add(population,[&] { openCountryDetail(CountryDetail::population); });
                        else add(population);
                        if (own) {
                            add("Бюджет",[&] { diplomacyPanel = false; economicPanel = 1; });
                            const double balance = world.taxedTreasury(0).balance()+world.economyCurrent[0].trade;
                            add("Баланс: "+formatMoneyDelta(balance)+"/мес");
                            add("Поддержка правительства: "+percent(policy.support),
                                [&] { openCountryDetail(CountryDetail::support); });
                            add("Устойчивость: "+percent(policy.stability)+"; легитимность: "+percent(policy.legitimacy));
                            if (balance < 0) add("Дефицит бюджета",[&] {
                                countryTab = CountryTab::actions;
                                countryScroll = 0;
                                countryHits.clear();
                            });
                        } else {
                            add(std::string("Статус: ")+status(relation));
                            add("Отношение к нам: "+relationText(relation,country));
                            std::string agreements;
                            for (const auto treaty : relation.treaties) {
                                if (!agreements.empty()) agreements += ", ";
                                agreements += treatyName(treaty);
                            }
                            add("Договоры: "+(agreements.empty() ? "нет" : agreements));
                            add(std::string("Проход наших войск: ")+(diplomacy.canTransit(0,country) ? "разрешён" : "запрещён"));
                            add(std::string("Проход их войск: ")+(diplomacy.canTransit(country,0) ? "разрешён" : "запрещён"));
                            add("Претензии к нам: "+std::to_string(opinion(relation.grievance,country))+"/100; страх: "+
                                std::to_string(opinion(relation.fear,country))+"/100; уважение: "+
                                std::to_string(opinion(relation.respect,country))+"/100");
                            add("Дипломатическая напряжённость: "+formatAmount(relation.crisis)+"/100");
                            add("Идеологическое расхождение: "+percent(diplomacy.ideologyDistance(0,country))+
                                "; их репутация: "+percent(policy.reputation)+"; надёжность: "+percent(policy.reliability));
                            add("Внутренняя поддержка и бюджет: нет достоверных сведений");
                            if (const auto goal = diplomacy.goals.find({0,country}); goal != diplomacy.goals.end())
                                add(std::string("Цель войны: ")+(goal->second <= diplomacy.day ? "готова" : "готовится")+
                                    " с "+date(goal->second)+"; действует до "+date(goal->second+180));
                        }
                        const auto ratings = world.powerRanking();
                        add("Мощь государства: место "+std::to_string(ratings[country].rank)+" из "+
                            std::to_string(ratings.size()),[&] {
                                openCountryDetail(CountryDetail::power);
                            });
                        if (!own) add(world.countryThreat(country,ratings));
                        add("");
                        add("Войны и договорённости");
                        const auto firstAgreement = rows.size();
                        for (int other = 0; other < int(world.profiles.size()); ++other) {
                            if (other == country) continue;
                            const auto& ties = diplomacy.relation(country,other);
                            std::string events;
                            const auto event = [&](std::string_view caption) {
                                if (!events.empty()) events += ", ";
                                events += caption;
                            };
                            if (ties.war) event("Война");
                            for (const auto treaty : ties.treaties)
                                if (treaty != Action::transit) event(treatyName(treaty));
                            if (ties.truceUntil > diplomacy.day) event("Перемирие до "+date(ties.truceUntil));
                            if (ties.transitGrantors.contains(country)) event("Их войска могут проходить по территории страны");
                            if (ties.transitGrantors.contains(other)) event("Войска страны могут проходить по их территории");
                            if (ties.embargoes.contains(country)) event("Эмбарго против партнёра");
                            if (ties.embargoes.contains(other)) event("Эмбарго со стороны партнёра");
                            for (const int actor : {country,other}) {
                                const int target = actor == country ? other : country;
                                const auto goal = diplomacy.goals.find({actor,target});
                                if (goal == diplomacy.goals.end() || diplomacy.day > goal->second+180) continue;
                                event(std::string(actor == country ? "Цель войны против партнёра" : "Партнёр готовит войну против страны")+
                                    (goal->second <= diplomacy.day ? " (готова с " : " (будет готова ")+date(goal->second)+")");
                            }
                            if (!events.empty()) add(name(other)+" — "+events);
                        }
                        if (rows.size() == firstAgreement) add("Нет действующих войн и договорённостей");
                    } else if (countryTab == CountryTab::society) {
                        if (own) {
                            add("Поддержка правительства: "+percent(policy.support));
                            add("Устойчивость: "+percent(policy.stability)+"; легитимность: "+percent(policy.legitimacy));
                            add("Поддержка войны: "+percent(policy.warSupport));
                            std::ostringstream capital;
                            capital << std::fixed << std::setprecision(1) << policy.capital;
                            add("Политический капитал: "+capital.str()+"/100; репутация: "+
                                percent(policy.reputation)+"; надёжность: "+percent(policy.reliability));
                            add("Обеспеченность: еда "+percent(policy.food)+"; товары "+percent(policy.goods));
                            add("Цены к базовым: еда "+percent(policy.foodPrice)+"; товары "+percent(policy.goodsPrice));
                            add("Налоговая отдача компаний: "+percent(std::clamp(1+.5*(policy.stability-.72),.65,1.05)));
                            add("Демография",[&] { openCountryDetail(CountryDetail::population); });
                            add("Программы поддержки",[&] { openCountryDetail(CountryDetail::programs); });
                            const bool atWar = std::ranges::any_of(diplomacy.relations,[](const auto& entry) {
                                return entry.first.first == 0 && entry.second.war;
                            });
                            const auto demands = policy.factionDemands(atWar,world.profiles[0].budget);
                            constexpr std::array demandText{"Поддержка обороны не ниже 50%",
                                "Социальная программа или сниженный налог населения",
                                "Открытый внешний рынок и отсутствие войны",
                                "Положительный бюджет и легитимность не ниже 50%"};
                            for (int group = 0; group < int(policyGroups.size()); ++group) {
                                if (group == 0) { add(""); add("Экономические группы",{}, {151,186,214}); }
                                if (group == 3) { add(""); add("Социальные группы населения",{}, {151,186,214}); }
                                if (group == 7) { add(""); add("Политические фракции",{}, {151,186,214}); }
                                std::string detail = std::string(policyGroups[group])+": поддержка "+percent(policy.groups[group]);
                                if (group >= 3) detail += "; оценочная доля "+
                                    percent(group < 7 ? policy.socialShares[group-3] : policy.factionShares[group-7]);
                                constexpr std::array factionHelp{
                                    "Сторонники сильной обороны. В мирное время следят, чтобы поддержка войны оставалась не ниже 50%.",
                                    "Выступают за поддержку населения. Их требование выполняет социальная программа или снижение налога населения.",
                                    "Выступают за открытый внешний рынок и мир. Во время войны их требование не выполняется.",
                                    "Ценят устойчивость государственных институтов. Требуют неотрицательную казну и легитимность не ниже 50%."
                                };
                                if (group >= 7) add(std::move(detail),{}, {239,209,146},"Ф",factionHelp[group-7]);
                                else add(std::move(detail));
                                if (group >= 7) {
                                    const int faction = group-7;
                                    add(std::string("Требование: ")+demandText[faction]+" — "+
                                        (demands[faction] ? "выполнено" : "не выполнено"));
                                    add("Терпение "+percent(policy.factionPatience[faction])+
                                        "; радикализация "+percent(policy.factionRadicalization[faction]));
                                }
                            }
                        } else add("Нет достоверных сведений о настроениях групп");
                    } else if (countryTab == CountryTab::trade) {
                        add(std::string("Внешний рынок: ")+(policy.externalAccess ? "открыт" : "закрыт"));
                        add("Экспорт: "+percent(policy.exportLimit)+" базовой мощности");
                        if (!own) add(std::string("Прямая торговля: ")+
                            (diplomacy.tradeAllowed(0,country) ? "разрешена" : "заблокирована"));
                        else {
                            if (!tradeForecast) tradeForecast = world.forecastResources(0,simulation.marketTickCount);
                            const auto total = [](const hoi5::Stockpile& entries) {
                                double value = 0.;
                                for (const auto& entry : entries) value += entry.second;
                                return value;
                            };
                            add("Прогноз импорта: "+resourceAmountLabel(total(tradeForecast->imports))+
                                "/мес.; экспорта: "+resourceAmountLabel(total(tradeForecast->exports))+"/мес.");
                            add("Торговый баланс (прогноз): "+formatMoneyDelta(world.economyCurrent[0].trade)+"/мес.");
                            add("Управление контрактами",[&] {
                                diplomacyPanel = false;
                                tradePanel = true;
                                tradeForecast.reset();
                            });
                            int contracts = 0;
                            for (const auto& contract : world.market.contracts) contracts += contract.country == 0;
                            add("Контракты: "+std::to_string(contracts));
                            for (const auto& contract : world.market.contracts)
                                if (contract.country == 0)
                                    add(std::string(contract.buy ? "Закупка: " : "Продажа: ")+
                                        std::string(resourceDisplayName(contract.resource))+", "+
                                        resourceAmountLabel(contract.amount)+"/мес.");
                        }
                        add("Последние исполненные сделки:");
                        for (const auto& fill : world.market.last.fills) {
                            if (fill.buyer != 0 && fill.seller != 0) continue;
                            if (!own && fill.buyer != country && fill.seller != country) continue;
                            add((fill.seller ? name(*fill.seller) : "Внешний рынок")+" > "+
                                (fill.buyer ? name(*fill.buyer) : "Внешний рынок")+": "+
                                std::string(resourceDisplayName(fill.resource))+", "+resourceAmountLabel(fill.amount)+
                                ", $"+formatAmount(fill.price)+"/ед.");
                        }
                    } else if (countryTab == CountryTab::actions && own) {
                        add(policy.exportLimit < .999 ? "Открыть экспорт" : "Ограничить экспорт",[&] {
                            pendingExport = int(std::nearbyint(world.diplomacy.countries[0].exportLimit*100));
                            openCountryDetail(CountryDetail::exportLimit);
                        },{224,234,244},"Э");
                        add(policy.externalAccess ? "Закрыть внешний рынок" : "Открыть внешний рынок",
                            [&] { openCountryDetail(CountryDetail::externalMarket); },{224,234,244},"Р");
                        add("Налоги",[&] { openCountryDetail(CountryDetail::taxes); },{224,234,244},"Н");
                        add("Программы поддержки групп",[&] { openCountryDetail(CountryDetail::programs); },{224,234,244},"П");
                    } else if (countryTab == CountryTab::actions) {
                        const auto addDecision = [&](const hoi5::ForeignActionInfo& action) {
                            const auto* selected = &action;
                            const bool granted = relation.transitGrantors.contains(0);
                            if ((action.action == Action::revokeTransit && !granted) ||
                                (action.action == Action::transit && granted) ||
                                (action.action == Action::peace && !relation.war) ||
                                (action.action == Action::cancelJustification && !diplomacy.goals.contains({0,country}))) return;
                            std::string caption(action.label);
                            if (action.action == Action::embargo)
                                caption = relation.embargoes.contains(0) ? "Снять эмбарго" : "Ввести эмбарго";
                            const auto reason = diplomacy.reason(0,country,action,world.profiles,double(amountValue()));
                            if (!reason.empty()) {
                                add(std::move(caption),{}, {146,153,160},"–",reason);
                                return;
                            }
                            add(std::move(caption),[&,selected] {
                                countryDecision = selected;
                                countryDecisionHits.clear();
                                countryDecisionError.clear();
                                foreignMessage.clear();
                            },{224,234,244},"›",std::string(action.description));
                        };
                        for (const auto& action : hoi5::foreignActions) {
                            addDecision(action);
                            if (action.action == Action::mission) {
                                addDecision(hoi5::foreignAid);
                                addDecision(hoi5::foreignLoan);
                            }
                        }
                    } else if (countryTab == CountryTab::history) {
                        for (const auto& offer : diplomacy.offers) {
                            if (offer.actor != 0 && offer.target != 0) continue;
                            if (!own && offer.actor != country && offer.target != country) continue;
                            add(std::string(treatyName(offer.action))+": "+name(offer.actor)+" > "+
                                name(offer.target)+"; ожидаемый ответ: "+date(offer.due));
                            if (offer.action == Action::loan) add("Сумма: $"+formatAmount(offer.amount));
                            if (offer.target == 0) {
                                for (const bool accept : {true,false})
                                    add(accept ? "Принять" : "Отклонить",[&,actor=offer.actor,action=offer.action,accept] {
                                        foreignMessage = world.answerForeignOffer(actor,0,accept,action)
                                            ? "Соглашение принято" : "Предложение отклонено";
                                        tradeForecast.reset();
                                        world.updateStatus();
                                        countryHits.clear();
                                    });
                            }
                        }
                        for (const auto& loan : diplomacy.loans) {
                            if (loan.lender != 0 && loan.borrower != 0) continue;
                            if (!own && loan.lender != country && loan.borrower != country) continue;
                            add("Кредит: "+name(loan.lender)+" > "+name(loan.borrower));
                            add("Долг $"+formatAmount(loan.principal)+"; следующий платёж: "+date(loan.nextDue));
                        }
                        for (const auto& event : diplomacy.history) {
                            if (event.actor != 0 && event.target != 0) continue;
                            if (!own && event.actor != country && event.target != country) continue;
                            add(date(event.day)+": "+name(event.actor)+": "+event.message);
                        }
                    }
                    if (!foreignMessage.empty()) add(foreignMessage);
                    if (rows.empty()) add("Нет событий");
                }
                constexpr int rowPitch = 29;
                const int visible = std::max(1,(bounds.size.y-132)/rowPitch);
                countryScrollMax = std::max(0,int(rows.size())-visible);
                countryScroll = std::clamp(countryScroll,0,countryScrollMax);
                for (int i = countryScroll; i < int(rows.size()) && i < countryScroll+visible; ++i) {
                    const int y = int(top)+86+(i-countryScroll)*rowPitch;
                    const auto& row = rows[i];
                    const sf::IntRect rowBounds({left+12,y},{bounds.size.x-24,rowPitch-2});
                    const bool hovered = rowBounds.contains(sf::Mouse::getPosition(window));
                    if (row.activate || !row.icon.empty()) {
                        box(window,sf::Vector2f(rowBounds.position),sf::Vector2f(rowBounds.size),
                            hovered && row.activate ? sf::Color{49,69,81} : row.activate ?
                                sf::Color{35,48,57} : sf::Color{33,39,48},{81,100,120});
                        if (row.activate) countryHits.push_back({rowBounds,row.activate});
                    }
                    if (!row.icon.empty()) {
                        box(window,{left+17.f,y+3.f},{21,21},{52,65,79},{103,127,151});
                        battleLabel(window,cardFont,row.icon,{left+27.5f,y+13.f},16,row.ink,.5f);
                    }
                    const float textX = left+(row.icon.empty() ? 18.f : 44.f);
                    fittedBattleLabel(window,cardFont,row.text,{textX,y+13.f},17,
                        left+width-14.f-textX,row.ink);
                    if (hovered && !row.help.empty()) hoverHelp = HoverHelp{row.text,countryTextLines(row.help,48)};
                }
                if (countryScrollMax) {
                    const float track = float(visible*rowPitch);
                    const float thumb = std::max(24.f,track*visible/rows.size());
                    box(window,{left+width-8,top+86},{4,track},{48,62,78,180});
                    box(window,{left+width-8,top+86+(track-thumb)*countryScroll/countryScrollMax},{4,thumb},{132,156,184,220});
                }
            }
            if (tradePanel) {
                hoi5::DebugMeasure timing(&debug,"panel_trade");
                const auto bounds = tradeBounds();
                const auto& policy = world.diplomacy.countries[0];
                const auto& stocks = world.stockpiles.front();
                if (!tradeForecast) {
                    hoi5::DebugMeasure timing(&debug,"trade_snapshot");
                    tradeForecast = world.forecastResources(0,simulation.marketTickCount);
                    tradeMonthly = hoi5::Market::monthlyCapacity(world.tiles,world.profiles)[0];
                }
                const auto total = [](const hoi5::Stockpile& quantities) {
                    double amount = 0;
                    for (const auto& [key,value] : quantities) amount += value;
                    return amount;
                };
                const double sellLimit = tradeMonthly*2*policy.exportLimit;
                const auto trade_headerStart = DebugClock::now();
                box(window,sf::Vector2f(bounds.position),sf::Vector2f(bounds.size),{18,24,31,250},{92,112,136});
                label(window,font,"Торговля",{18,tradeTop+12},23);
                box(window,sf::Vector2f(tradeClose.position),sf::Vector2f(tradeClose.size),{44,54,66},{120,142,164});
                label(window,font,"X",{tradeWidth-28,tradeTop+15},13);
                label(window,font,policy.externalAccess ? "Торговля: внешний рынок открыт" :
                    "Внешний рынок закрыт. Доступны только сделки со странами",{18,tradeTop+60},18);
                label(window,font,"Покупка: "+resourceAmountLabel(total(tradeForecast->imports))+"/"+
                    resourceAmountLabel(tradeMonthly)+" ед./мес",{18,tradeTop+87},16);
                label(window,font,"Продажа: "+resourceAmountLabel(total(tradeForecast->exports))+"/"+
                    resourceAmountLabel(sellLimit)+" ед./мес",{18,tradeTop+109},16);
                const double balance = world.economyCurrent.empty() ? 0. : world.economyCurrent.front().trade;
                label(window,font,"Деньги от торговли: "+std::string(balance < 0 ? "−$" : "$")+
                    formatAmount(std::abs(balance))+"/мес",{400,tradeTop+87},16);
                const year_month_day nextTrade{sys_days{year{2000}/1/1}+days{simulation.nextMarketExecutionHour()/24}};
                std::ostringstream execution;
                execution << "Исполнение: понедельник 00:00, раз в неделю. След.: " << int(nextTrade.year())
                          << '-' << std::setfill('0') << std::setw(2) << unsigned(nextTrade.month())
                          << '-' << std::setw(2) << unsigned(nextTrade.day()) << " 00:00";
                label(window,font,execution.str(),{18,tradeTop+139},12);
                for (int i = 0; i < 3; ++i) {
                    const auto rect = tradeCategoryRect(i);
                    box(window,sf::Vector2f(rect.position),sf::Vector2f(rect.size),
                        tradeCategory == i ? sf::Color(58,88,112,220) : sf::Color(30,40,52,175),
                        tradeCategory == i ? sf::Color(170,202,232) : sf::Color(86,108,132));
                    label(window,font,resourceCategories[i],sf::Vector2f(rect.position)+sf::Vector2f{10,6},19);
                }
                constexpr std::array columns{18.f,176.f,252.f,324.f,396.f,554.f,680.f};
                constexpr std::array headings{"Ресурс","Склад","Баланс","Мир","Покупка / продажа","Доступно","Контракт"};
                for (int i = 0; i < int(columns.size()); ++i)
                    battleLabel(window,font,headings[i],{columns[i],tradeTop+254},14,{150,166,184});
                battleLabel(window,font,"Изменить",{760,tradeTop+254},14,{150,166,184});
                debug.record("trade_header",trade_headerStart);
                const auto keys = resourceCategoryKeys(tradeCategory);
                const int visible = tradeRows(), maxScroll = std::max(0,int(keys.size())-visible);
                tradeScroll = std::clamp(tradeScroll,0,maxScroll);
                for (int row = 0; row < visible && tradeScroll+row < int(keys.size()); ++row) {
                    hoi5::DebugMeasure rowTiming(&debug,"trade_rows");
                    const auto key = keys[tradeScroll+row];
                    const float y = float(tradeRowTop+row*tradeRowHeight);
                    box(window,{18,y-2},{864,52},(tradeScroll+row)%2 == 0 ?
                        sf::Color(24,32,42,118) : sf::Color(30,38,48,118));
                    const double amount = hoi5::value(stocks,key);
                    const double net = hoi5::value(tradeForecast->outputs,key)-hoi5::value(tradeForecast->required,key);
                    if (sf::FloatRect({260,y-2},{304,42}).contains(sf::Vector2f(sf::Mouse::getPosition(window)))) {
                        std::ostringstream week;
                        week << std::showpos << std::fixed << std::setprecision(2) << world.market.priceChange(key)*100 << '%';
                        std::ostringstream local;
                        local << std::showpos << std::fixed << std::setprecision(2)
                              << (world.market.countryPrice(0,key)/world.market.price(key)-1)*100 << '%';
                        hoverHelp = HoverHelp{std::string(resourceDisplayName(key)),
                            {"Мировая цена к прошлой неделе: "+week.str(),
                             "Наш рынок к мировой цене: "+local.str(),
                             "Наша покупка / продажа: "+formatMoney(world.market.unitPrice(0,key,true))+" / "+
                             formatMoney(world.market.unitPrice(0,key,false))}};
                    }
                    const double buyOrder = world.market.contractAmount(0,key,true);
                    const bool buy = buyOrder > 0;
                    const double ordered = buy ? buyOrder : world.market.contractAmount(0,key,false);
                    const double filled = hoi5::value(buy ? tradeForecast->imports : tradeForecast->exports,key);
                    const bool ready = filled >= ordered-1e-6;
                    const bool partial = !ready && filled > 1e-6;
                    const sf::Color orderColor = ready ? sf::Color(220,230,240) :
                        partial ? sf::Color(238,198,90) : sf::Color(236,148,132);
                    const std::array values{std::string(resourceDisplayName(key)),resourceAmountLabel(amount),
                        resourceAmountLabel(net),formatMoney(world.market.price(key)),
                        formatMoney(world.market.unitPrice(0,key,true))+" / "+
                            formatMoney(world.market.unitPrice(0,key,false)),
                        world.market.revision == 0 || world.market.countryDemand.empty() ? std::string("--") :
                            resourceAmountLabel(hoi5::value(world.market.countryDemand[0],key))+"/"+
                            resourceAmountLabel(hoi5::value(world.market.countrySupply[0],key)),
                        ordered <= 0 ? std::string("--") : (buy ? "Покупка " : "Продажа ")+resourceAmountLabel(ordered)};
                    for (int i = 0; i < int(values.size()); ++i) {
                        const sf::Color color = i == 6 ? orderColor : i == 2 ?
                            (net >= 0 ? sf::Color(174,224,158) : sf::Color(236,168,154)) :
                            sf::Color(220,230,240);
                        battleLabel(window,font,values[i],{columns[i],y+13},i == 0 ? 17 : 15,color);
                    }
                    {
                        hoi5::DebugMeasure timing(&debug,"trade_buttons");
                        for (int i = 0; i < int(tradeButtons.size()); ++i) {
                            const float x = float(tradeButtons[i]);
                            box(window,{x,y+15},{24,22},{42,62,82,210},i < 2 ? sf::Color(124,178,232) : sf::Color(180,210,128));
                            box(window,{x+7,y+25},{10,2},sf::Color::White);
                            if (i%2) box(window,{x+11,y+21},{2,10},sf::Color::White);
                        }
                    }
                    if (ordered <= 0) continue;
                    std::string status = "К исполнению";
                    if (!ready) {
                        status = partial ? "Частично ("+resourceAmountLabel(filled)+"): " : "Не исполняется: ";
                        if (!policy.externalAccess) status += "Внешний рынок закрыт. ";
                        if (buy && world.profiles[0].budget <= 0) status += "Нет средств";
                        else if (buy && hoi5::freeStorage(world.capacities[0],stocks,key) <= 0) status += "Нет места на складе";
                        else if (!buy && amount <= 0) status += "Нет товара на складе";
                        else if ((buy ? tradeMonthly : sellLimit) <= 0) status += "Нет торговой пропускной способности";
                        else if (!buy && policy.exportLimit < 1) status += "Экспорт ограничен";
                        else {
                            bool partners = false, eligible = false;
                            for (const auto& contract : world.market.contracts) {
                                if (contract.country <= 0 || contract.country >= int(world.profiles.size()) ||
                                    contract.resource != key || contract.buy == buy || contract.amount <= 0 ||
                                    !std::isfinite(contract.amount)) continue;
                                partners = true;
                                eligible |= world.diplomacy.tradeAllowed(0,contract.country);
                            }
                            if (!policy.externalAccess && !eligible)
                                status += partners ? "Война / эмбарго с контрагентами" : "Нет встречных заявок стран";
                            else if (buy && world.profiles[0].budget < ordered*world.market.unitPrice(0,key,true))
                                status += "Недостаточно средств на весь объём";
                            else status += "Недостаточно доступного объёма / лимита";
                        }
                    }
                    battleLabel(window,font,status,{22,y+41},14,ready ? sf::Color(170,210,180) : orderColor);
                }
                if (maxScroll > 0) {
                    const float track = std::max(40.f,float(visible*tradeRowHeight-16));
                    const float thumb = std::max(24.f,track*visible/keys.size());
                    box(window,{888,tradeRowTop+4},{4,track},{42,52,64,180});
                    box(window,{886,tradeRowTop+4+(track-thumb)*tradeScroll/maxScroll},{8,thumb},{130,154,184,220});
                }
                label(window,font,world.market.revision == 0 ?
                    "Спрос/предложение появятся после первых торгов. Контракты ожидают исполнения." :
                    "Спрос/предложение: итоги последних торгов. Объём контракта не гарантирован.",
                    {18,size.y-36},12);
            }
            if (const auto found = world.battles.find(selectedBattle); found != world.battles.end()) {
                const auto& battle = found->second;
                const auto panel = battlePanel();
                const auto close = battleClose(panel);
                const auto [x,y] = panel.position;
                const float width = panel.size.x;
                const auto rounded = [](double value) { return std::to_string(int(std::nearbyint(value))); };
                const auto precise = [](double value) {
                    std::ostringstream out;
                    out << std::fixed << std::setprecision(1) << value;
                    return out.str();
                };
                const auto ratio = world.battleWinRatio(battle);
                const double attack = world.battlePower(battle.attackers), defense = world.battlePower(battle.defenders);
                const double pressure = std::max(.08,std::abs(attack-defense)/std::max(1.,attack+defense));
                const double hours = (1-std::clamp(battle.advance,0.,1.))/.035+
                    (defense > 0 ? (1-pressure)*36 : 0);
                const std::string duration = formatBuildDuration(hours/720.);
                box(window,panel.position,panel.size,{16,24,30,238},{112,142,174});
                box(window,close.position,close.size,{44,54,66,240},{120,142,164});
                battleLabel(window,font,"X",close.position+sf::Vector2f{12,12},11,sf::Color::White,.5f);
                battleLabel(window,font,"Сражение",{x+20,y+32},19);
                box(window,{x+20,y+54},{width-40,16},{48,42,42,230});
                if (ratio > 0) box(window,{x+20,y+54},{float((width-40)*ratio),16},{72,126,76,235});
                box(window,{x+20,y+54},{width-40,16},sf::Color::Transparent,{128,148,168});
                battleLabel(window,font,"Ход сражения: "+rounded(ratio*100)+"%",{x+width*.5f,y+62},11,sf::Color::White,.5f);
                battleLabel(window,font,"Соотношение сил: "+rounded(attack)+" / "+rounded(defense)+
                    "   ШФ: "+rounded(battle.width)+" ("+std::to_string(world.battleAttackDirectionCount(found->first,battle))+
                    ")",{x+20,y+94},12,{210,222,232});
                battleLabel(window,font,"Осталось: "+(battle.advance >= 1 ? std::string("сейчас") : duration),
                    {x+width-20,y+94},12,{210,222,232},1.f);
                battleLabel(window,font,"Потери",{x+width*.5f,y+128},15,sf::Color::White,.5f);
                const bool playerAttacks = battle.attacker == 0;
                const bool playerDefends = battle.defender == 0;
                for (int column = 0; column < 2; ++column) {
                    const bool attacking = column == (playerDefends ? 1 : 0);
                    const int incoming = column != int(playerAttacks) ? 0 : 1;
                    const float left = column ? x+width*.5f+18 : x+20;
                    const float right = left+width*.5f-46;
                    const auto& participants = attacking ? battle.attackers : battle.defenders;
                    const auto& active = attacking ? battle.activeAttackers : battle.activeDefenders;
                    battleLabel(window,font,std::string(column ? "Враг: орг " : "Наши: орг ")+
                        precise(battle.organizationDamage[incoming])+", хп "+precise(battle.strengthDamage[incoming]),
                        {column ? x+width-20 : x+20,y+152},12,{224,190,150},float(column));
                    battleLabel(window,font,playerAttacks || playerDefends ? (column ? "Враг" : "Наши") :
                        (attacking ? "Атакующие" : "Защитники"),{left,y+186},16);
                    float row = y+214;
                    constexpr std::array groups{"В бою","В резерве","Восстановление"};
                    for (int group = 0; group < int(groups.size()); ++group) {
                        battleLabel(window,font,groups[group],{left,row},13,{220,230,240});
                        row += 22;
                        int count = 0;
                        for (int index : (group == 0 ? active : participants)) {
                            const auto& unit = world.divisions[index];
                            if (unit.combat.strength <= 0 ||
                                (group != 0 && (std::ranges::find(active,index) != active.end() ||
                                 unit.combat.recovering != (group == 2)))) continue;
                            if (++count > 8) continue;
                            const double org = std::clamp(unit.organization/std::max(1.,unit.maxOrganization),0.,1.);
                            const double hp = std::clamp(unit.combat.strength/std::max(1.,unit.design->combat.strength),0.,1.);
                            battleLabel(window,font,std::to_string(index+1)+". "+std::string(unit.design->name),{left,row},11);
                            battleLabel(window,font,"орг "+rounded(org*100)+"%  хп "+rounded(hp*100)+"%",
                                {right,row},11,{168,214,166},1.f);
                            row += 18;
                        }
                        if (count == 0) {
                            battleLabel(window,font,"-",{left,row},12,{130,145,160});
                            row += 20;
                        } else {
                            if (count > 8) {
                                battleLabel(window,font,"Еще "+std::to_string(count-8),{left,row},11,{150,166,184});
                                row += 18;
                            }
                            row += 8;
                        }
                    }
                }
            } else selectedBattle = -1;
            if (!pauseMenu) {
                const float side = float(sidePanelRight());
                const float airRight = airDockX+430.f*airDockScale;
                const bool stackNews = !world.air.reserves.empty() && airRight+154 > size.x;
                const float newsLeft = std::max(side+16.f,world.air.reserves.empty() || stackNews ? 16.f : airRight+10.f);
                const auto wingBounds = wingListBounds(int(wingCards().size()));
                const float filtersInset = (mapLayerMenu || mapLayerProgress > .01f || resourceGroupMenu ||
                    resourceGroupProgress > .01f) ? 258.f : 0.f;
                const float hexInset = selectedTiles.empty() ? 0.f : size.x-hexPanelRect().position.x;
                const float armyInset = armyCommandBounds.size.x > 0
                    ? size.y-armyCommandBounds.position.y+8.f : 0.f;
                newsPanel.update(world.news,dt,size,newsLeft,stackNews ?
                    (size.y-wingBounds.position.y)*airDockScale+8.f : 0.f,
                    std::max(filtersInset,hexInset),armyInset);
                newsPanel.draw(window,font);
            }
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
            else if (!playing && setup) {
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
                    const float y=size.y/2-186+64*i;
                    box(window,{size.x/2-188,y},{376,52},{30,39,50},{92,112,136});
                    const auto value = sf::String::fromUtf8(buttons[i].begin(),buttons[i].end());
                    sf::Text text(font,value,20);
                    if (i==2 || (i==1 && !resumable)) text.setFillColor({152,164,180});
                    const auto bounds=text.getLocalBounds();
                    text.setPosition({std::round(size.x/2-bounds.size.x/2-bounds.position.x),
                                      std::round(y+26-bounds.size.y/2-bounds.position.y)});
                    window.draw(text);
                }
                if (!errorMessage.empty()) label(window,font,errorMessage,{80,size.y-60});
            }
        }
        armyCommandHits.clear();
        divisionListHits.clear();
        armyCommandBounds = divisionListBounds = {};
        if (playing && !pauseMenu) {
            window.setView(gui);
            std::erase_if(selectedDivisions,[&](int index) { return !world.selectableDivision(0,index); });
            if (selected >= 0 && !world.selectableDivision(0,selected)) syncArmySelection();
            std::vector<const World::Army*> armies;
            for (const auto& army : world.armies) if (army.owner == 0) armies.push_back(&army);
            const bool canCreate = std::ranges::any_of(selectedDivisions,[&](int index) {
                return world.divisions[index].armyId == 0;
            });
            if (!armies.empty() || canCreate) {
                const auto active = std::ranges::find(armies,activeArmy,[](const auto* army) { return army->id; });
                if (active == armies.end()) activeArmy = -1;
                if (activeArmy < 0)
                    for (int index : selectedDivisions)
                        if (const int id = world.divisions[index].armyId; id) { activeArmy = id; break; }
                const auto windowSize = sf::Vector2i(window.getSize());
                int panelRight = sidePanelRight();
                const int divisionLeft = std::max(10,std::min(panelRight+10,windowSize.x-365));
                if (!world.air.reserves.empty()) {
                    panelRight = std::max(panelRight,int(airDockX+430.f*airDockScale));
                }
                const int width = std::min(360,std::max(250,windowSize.x-88-panelRight));
                const int left = std::max(10,std::min({panelRight+10,windowSize.x-78-width,windowSize.x-365}));
                const int columns = std::max(1,(width-52)/63);
                const int cards = int(armies.size())+int(canCreate);
                const int height = 10+79*((cards+columns-1)/columns)-7;
                const auto ticker = newsPanel.tickerBounds();
                const bool aboveTicker = left < ticker.position.x+ticker.size.x && left+width > ticker.position.x;
                const int bottom = aboveTicker ? int(ticker.position.y)-8 : windowSize.y-14;
                const int top = bottom-height;
                armyCommandBounds = {{left,top},{width,height}};
                box(window,{float(left),float(top)},{float(width),float(height)},{14,19,22,232},{62,80,88});
                box(window,{left+5.f,top+5.f},{42,float(height-10)},{28,38,42,238},{74,92,98});
                battleLabel(window,cardFont,"ТВД",{left+26.f,top+17.f},12,{214,226,232},.5f);
                battleLabel(window,cardFont,"1",{left+26.f,top+height*.5f+8},21,sf::Color::White,.5f);
                const auto button = [&](std::string caption,sf::IntRect rect,std::function<void()> action,
                    sf::Color fill = {38,48,58,230},sf::Color border = {110,132,154}) {
                    box(window,sf::Vector2f(rect.position),sf::Vector2f(rect.size),fill,border);
                    battleLabel(window,cardFont,caption,sf::Vector2f(rect.getCenter()),14,{220,226,232},.5f);
                    armyCommandHits.push_back({rect,std::move(action)});
                };
                const auto selectArmy = [&](int id) {
                    return [&,id] {
                        using Key = sf::Keyboard::Key;
                        const bool shift = sf::Keyboard::isKeyPressed(Key::LShift) || sf::Keyboard::isKeyPressed(Key::RShift);
                        if (!shift) {
                            world.addDivisionsToArmy(0,id,selectedDivisions);
                            selectedDivisions.clear();
                        }
                        const auto members = world.armyMembers(0,id);
                        const bool allSelected = !members.empty() && std::ranges::all_of(members,[&](int index) {
                            return selectedDivisions.contains(index);
                        });
                        for (int index : members) {
                            if (shift && allSelected) selectedDivisions.erase(index);
                            else selectedDivisions.insert(index);
                        }
                        activeArmy = id;
                        divisionListScroll = 0;
                        cancelFrontDrawing();
                        syncArmySelection();
                        armyCommandHits.clear();
                    };
                };
                for (int i = 0; i < cards; ++i) {
                    const int x = left+53+63*(i%columns), y = top+5+79*(i/columns);
                    const bool add = i == int(armies.size());
                    const int id = add ? 0 : armies[i]->id;
                    const auto members = add ? std::vector<int>{} : world.armyMembers(0,id);
                    const bool highlighted = add || std::ranges::any_of(members,[&](int index) { return selectedDivisions.contains(index); });
                    box(window,{float(x),float(y)},{56,72},highlighted ? sf::Color{34,45,37,238} : sf::Color{24,31,38,235},
                        highlighted ? sf::Color{148,138,82} : sf::Color{70,88,104});
                    box(window,{x+3.f,y+3.f},{50,13},{18,24,27,235});
                    constexpr std::array status{sf::Color{122,54,58},sf::Color{56,116,68},sf::Color{78,110,70}};
                    for (int j = 0; j < int(status.size()); ++j) box(window,{x+7.f+16*j,y+6.f},{12,8},status[j],{24,31,34});
                    constexpr float portraitSize = 32.f;
                    const sf::Vector2f portrait{x+6.f,y+20.f};
                    if (add) {
                        box(window,portrait,{portraitSize,portraitSize},{34,42,48,230},{92,108,122});
                        battleLabel(window,cardFont,"+",portrait+sf::Vector2f{16,15},24,{210,220,226},.5f);
                    } else {
                        const std::array<std::array<sf::Color,3>,3> palettes{{
                            {{{116,91,68},{214,182,145},{36,42,34}}},
                            {{{64,70,74},{204,166,126},{82,28,28}}},
                            {{{70,62,54},{190,148,112},{44,34,28}}}
                        }};
                        const auto& [background,skin,uniform] = palettes[i%palettes.size()];
                        box(window,portrait,{portraitSize,portraitSize},background,{34,42,44});
                        sf::CircleShape face(portraitSize*.20f);
                        face.setOrigin({face.getRadius(),face.getRadius()});
                        face.setPosition(portrait+sf::Vector2f{.50f,.38f}*portraitSize);
                        face.setFillColor(skin);
                        window.draw(face);
                        box(window,portrait+sf::Vector2f{.28f,.58f}*portraitSize,
                            sf::Vector2f{.44f,.30f}*portraitSize,uniform);
                        box(window,portrait+sf::Vector2f{.30f,.16f}*portraitSize,
                            sf::Vector2f{.40f,.10f}*portraitSize,uniform);
                        box(window,portrait+sf::Vector2f{.43f,.36f}*portraitSize,{.04f*portraitSize,1},{32,30,26});
                        box(window,portrait+sf::Vector2f{.53f,.36f}*portraitSize,{.04f*portraitSize,1},{32,30,26});
                        box(window,portrait+sf::Vector2f{.44f,.46f}*portraitSize,{.12f*portraitSize,1},{96,54,42});
                    }
                    box(window,{x+5.f,y+54.f},{46,15},{12,17,19,235});
                    if (add) armyCommandHits.push_back({{{x,y},{56,72}},[&] {
                        const int id = world.createArmy(0,selectedDivisions);
                        if (!id) return;
                        const auto members = world.armyMembers(0,id);
                        selectedDivisions = std::set<int>(members.begin(),members.end());
                        activeArmy = id;
                        divisionListScroll = 0;
                        syncArmySelection();
                        armyCommandHits.clear();
                    }});
                    else {
                        battleLabel(window,cardFont,std::to_string(members.size())+"/"+std::to_string(World::armyCapacity),
                            {x+28.f,y+61.f},13,sf::Color::White,.5f);
                        armyCommandHits.push_back({{{x,y},{56,72}},selectArmy(id)});
                    }
                }
                int listBottom = top-10;
                if (activeArmy > 0) {
                    const auto army = std::ranges::find(world.armies,activeArmy,&World::Army::id);
                    const int controlY = top-32;
                    constexpr std::array labels{"Ф","П","О","Н"};
                    constexpr std::array modes{FrontMode::automatic,FrontMode::custom,FrontMode::defense,FrontMode::offensive};
                    for (int i = 0; i < int(labels.size()); ++i)
                        button(labels[i],{{left+53+33*i,controlY},{28,24}},[&,mode=modes[i]] {
                            cancelFrontDrawing();
                            drawingFrontArmy = activeArmy;
                            frontMode = mode;
                            armyPickingSite = wingRebaseMode = wingAreaMode = false;
                            dragging = divisionDragActive = false;
                            divisionDragStart.reset();
                        },frontMode == modes[i] ? sf::Color{76,105,76} : sf::Color{38,48,58,230});
                    button(army->executing ? "II" : ">",{{left+185,controlY},{28,24}},[&] {
                        world.toggleArmyFront(0,activeArmy);
                    });
                    button("×",{{left+218,controlY},{28,24}},[&] {
                        world.clearArmyFront(0,activeArmy);
                        cancelFrontDrawing();
                    });
                    constexpr std::array frontHelp{
                        "ЛКМ по своему гексу на границе. Армия займёт связанный участок фронта.",
                        "Зажмите ЛКМ и проведите вдоль границы, чтобы выбрать участок фронта.",
                        "Зажмите ЛКМ и проведите по своим гексам, чтобы задать рубеж обороны.",
                        "Зажмите ЛКМ и проведите по чужим гексам. Армия начнёт наступать, когда займёт фронт.",
                        "Пауза или возобновление автоматических приказов армии.",
                        "Удаляет рубеж и останавливает автоматические маршруты."
                    };
                    constexpr std::array frontTitles{"Линия фронта","Участок фронта","Линия обороны","Линия наступления",
                        "Выполнение плана","Очистить план"};
                    for (int i = 0; i < int(frontHelp.size()); ++i)
                        if (sf::IntRect({left+53+33*i,controlY},{28,24}).contains(sf::Mouse::getPosition(window))) {
                            auto lines = countryTextLines(frontHelp[i],48);
                            if (i < 4) lines.emplace_back("Esc или ПКМ — отменить разметку.");
                            hoverHelp = HoverHelp{frontTitles[i],std::move(lines)};
                        }
                    armyCommandBounds.position.y = controlY;
                    armyCommandBounds.size.y += top-controlY;
                    listBottom = controlY-10;
                }
                struct DivisionGroup { int id; std::string name; std::vector<int> rows; };
                std::vector<DivisionGroup> groups;
                for (const auto* army : armies) {
                    auto members = world.armyMembers(0,army->id);
                    if (std::ranges::any_of(members,[&](int index) { return selectedDivisions.contains(index); }))
                        groups.push_back({army->id,army->name,std::move(members)});
                }
                std::vector<int> free;
                for (int index : selectedDivisions) if (!world.divisions[index].armyId) free.push_back(index);
                if (!free.empty()) groups.push_back({0,"Без армии",std::move(free)});
                if (!groups.empty() && listBottom >= 172) {
                    hoi5::DebugMeasure timing(&debug,"ui_division_list");
                    const int left = divisionLeft;
                    const auto selectedGroup = std::ranges::find(groups,activeArmy,&DivisionGroup::id);
                    if (selectedGroup == groups.end()) {
                        activeArmy = groups.front().id;
                        divisionListScroll = 0;
                    } else std::rotate(groups.begin(),selectedGroup,std::next(selectedGroup));
                    auto& rows = groups.front().rows;
                    std::ranges::stable_sort(rows,{},[&](int index) { return world.divisions[index].design->key; });
                    const int collapsed = (int(groups.size())-1)*42;
                    const int listWidth = 355, listTop = 92;
                    const int panelHeight = std::min({520,listBottom-listTop,96+40*int(rows.size())+collapsed});
                    const int expanded = std::max(78,panelHeight-collapsed);
                    const int visible = std::max(0,(expanded-96)/40);
                    divisionListScrollMax = std::max(0,int(rows.size())-visible);
                    divisionListScroll = std::clamp(divisionListScroll,0,divisionListScrollMax);
                    const int totalHeight = expanded+collapsed;
                    divisionListBounds = {{left,listTop},{listWidth,totalHeight}};
                    int y = listTop;
                    for (const auto& group : groups) {
                        const bool opened = group.id == activeArmy;
                        const int h = opened ? expanded : 36;
                        box(window,{float(left),float(y)},{float(listWidth),float(h)},
                            opened ? sf::Color{18,24,31,238} : sf::Color{26,34,43,236},
                            opened ? sf::Color{116,142,170} : sf::Color{78,96,116});
                        const int count = int(std::ranges::count_if(group.rows,[&](int index) { return selectedDivisions.contains(index); }));
                        battleLabel(window,cardFont,group.name,{left+14.f,y+18.f},20,{210,222,234});
                        battleLabel(window,cardFont,std::to_string(count)+"/"+std::to_string(group.rows.size()),
                            {left+311.f,y+18.f},16,{216,228,240},1.f);
                        button("X",{{left+321,y+8},{24,22}},[&,id=group.id] {
                            std::erase_if(selectedDivisions,[&](int index) { return world.divisions[index].armyId == id; });
                            if (activeArmy == id) activeArmy = -1;
                            syncArmySelection();
                            armyCommandHits.clear();
                        },{70,50,54,235});
                        armyCommandHits.push_back({{{left,y},{310,36}},[&,id=group.id] {
                            activeArmy = id;
                            divisionListScroll = 0;
                            armyCommandHits.clear();
                        }});
                        if (opened) {
                            double org = 0., people = 0.;
                            for (int index : group.rows) {
                                org += world.divisions[index].organization;
                                people += world.divisions[index].manpower;
                            }
                            battleLabel(window,cardFont,"Командир: нет",{left+14.f,y+43.f},14,{170,184,200});
                            battleLabel(window,cardFont,"Люди "+resourceAmountLabel(people)+"  Орг. "+
                                std::to_string(int(std::nearbyint(org/group.rows.size())))+"%",
                                {left+14.f,y+63.f},14,{170,184,200});
                            button("–",{{left+320,y+36},{26,26}},[&] {
                                world.detachDivisionsFromArmy(0,selectedDivisions);
                                activeArmy = -1;
                                divisionListScroll = 0;
                                armyCommandHits.clear();
                            });
                            if (sf::IntRect({left+320,y+36},{26,26}).contains(sf::Mouse::getPosition(window)))
                                hoverHelp = HoverHelp{"Исключить из армии",{"Выбранные дивизии станут свободными."}};
                            for (int i = 0; i < visible && i+divisionListScroll < int(group.rows.size()); ++i) {
                                const int index = group.rows[i+divisionListScroll];
                                const auto& unit = world.divisions[index];
                                const sf::IntRect row({left+12,y+86+i*40},{listWidth-24,36});
                                box(window,sf::Vector2f(row.position),sf::Vector2f(row.size),selectedDivisions.contains(index) ?
                                    sf::Color{40,61,77} : sf::Color{29,39,50},{73,93,112});
                                battleLabel(window,cardFont,std::string(unit.design->name),{left+21.f,row.position.y+10.f},14,{220,230,240});
                                for (int bar = 0; bar < 3; ++bar) {
                                    const float ratio = float(std::clamp(bar == 0 ? unit.organization/std::max(1.,unit.maxOrganization) :
                                        bar == 1 ? unit.combat.strength/std::max(1.,unit.design->combat.strength) : unit.lastSupplyRatio,0.,1.));
                                    const sf::Vector2f point{left+21.f+106*bar,row.position.y+24.f};
                                    box(window,point,{96,5},{16,23,30});
                                    if (ratio > 0) box(window,point,{96*ratio,5},bar == 0 ? sf::Color{104,186,122} :
                                        bar == 1 ? sf::Color{209,164,81} : sf::Color{108,166,208});
                                }
                                divisionListHits.push_back({row,index});
                                armyCommandHits.push_back({row,[&,index] {
                                    if (!selectedDivisions.erase(index)) selectedDivisions.insert(index);
                                    syncArmySelection();
                                    armyCommandHits.clear();
                                }});
                            }
                        }
                        y += h+6;
                    }
                }
            }
        }
        if (playing && countryModalOpen()) {
            window.setView(gui);
            const auto windowSize = sf::Vector2i(window.getSize());
            const sf::Vector2i dialog{std::min(840,windowSize.x-40),std::min(720,windowSize.y-108)};
            const auto origin = (windowSize-dialog)/2;
            const auto p = sf::Vector2f(origin);
            box(window,{0,0},size,{0,0,0,95});
            box(window,p,sf::Vector2f(dialog),{20,28,36},{116,144,163});
            countryDecisionHits.clear();
            const auto button = [&](std::string caption,sf::IntRect rect,std::function<void()> activate,bool fullRow = false) {
                rect.position += origin;
                const auto position = sf::Vector2f(rect.position);
                box(window,position,sf::Vector2f(rect.size),
                    fullRow ? sf::Color{35,55,63} : sf::Color{36,52,64},
                    fullRow ? sf::Color::Transparent : sf::Color{116,144,163});
                    battleLabel(window,cardFont,caption,
                    position+sf::Vector2f{fullRow ? 10.f : rect.size.x/2.f,rect.size.y/2.f},
                    18,{170,220,195},fullRow ? 0.f : .5f);
                countryDecisionHits.push_back({rect,std::move(activate)});
            };
            button("X",{{dialog.x-50,18},{30,30}},closeCountryDetail);
            box(window,p+sf::Vector2f{20,78},{float(dialog.x-40),1},{70,91,108});
            int y = 90 - (countryDetail != CountryDetail::none ? countryDialogScroll : 0);
            const auto rowVisible = [&](int height) { return y >= 85 && y+height <= dialog.y-26; };
            const auto textRow = [&](std::string caption,sf::Color color = {224,234,244}) {
                std::vector<std::string> lines;
                std::istringstream words(caption);
                std::string line,word;
                sf::Text measure(cardFont,"",18);
                const float available = float(dialog.x-56);
                while (words >> word) {
                    const auto candidate = line.empty() ? word : line+" "+word;
                    const auto utf = sf::String::fromUtf8(candidate.begin(),candidate.end());
                    measure.setString(utf);
                    if (!line.empty() && measure.getLocalBounds().size.x > available) {
                        lines.push_back(std::move(line));
                        line = word;
                    } else line = candidate;
                }
                if (!line.empty()) lines.push_back(std::move(line));
                if (lines.empty()) lines.emplace_back();
                const int height = std::max(42,int(lines.size())*23+12);
                if (rowVisible(height))
                    for (int i = 0; i < int(lines.size()); ++i)
                        battleLabel(window,cardFont,lines[i],p+sf::Vector2f{28,float(y+16+i*23)},18,color);
                y += height;
            };
            constexpr sf::Color muted{163,184,202}, gold{238,199,111}, blue{126,186,235}, green{133,213,169};
            constexpr sf::Color red{237,127,128};
            const auto titleRow = [&](std::string title) {
                fittedBattleLabel(window,cardFont,title,p+sf::Vector2f{24,28},23,dialog.x-88,{224,234,244});
            };
            const auto section = [&](std::string_view title) {
                if (rowVisible(44)) {
                    box(window,p+sf::Vector2f{28,float(y+12)},{float(dialog.x-56),1},{56,76,91});
                    battleLabel(window,cardFont,std::string(title),p+sf::Vector2f{28,float(y+31)},19,gold);
                }
                y += 44;
            };
            const auto metric = [&](std::string name,std::string value,sf::Color color) {
                if (rowVisible(32)) {
                    battleLabel(window,cardFont,name,p+sf::Vector2f{28,float(y+15)},18,{224,234,244});
                    battleLabel(window,cardFont,value,p+sf::Vector2f{float(dialog.x-28),float(y+15)},18,color,1.f);
                }
                y += 32;
            };
            const auto actionRow = [&](std::string caption,std::function<void()> action) {
                if (rowVisible(36)) button(std::move(caption),{{28,y+4},{dialog.x-56,28}},std::move(action),true);
                y += 36;
            };
            const auto percent = [](double value) { return std::to_string(int(std::nearbyint(value*100)))+"%"; };
            const auto capitalRow = [&](double cost) {
                std::ostringstream capital;
                capital << "Политический капитал: −" << cost << "; сейчас " << std::fixed <<
                    std::setprecision(1) << world.diplomacy.countries[0].capital << "/100";
                textRow(capital.str());
            };
            const auto hero = [&](std::string name,std::string value,sf::Color color) {
                if (rowVisible(66)) {
                    battleLabel(window,cardFont,name,p+sf::Vector2f{28,float(y+15)},19,muted);
                    battleLabel(window,cardFont,value,p+sf::Vector2f{28,float(y+44)},32,color);
                }
                y += 66;
            };
            const auto bar = [&](std::string name,std::string value,double fraction,sf::Color color) {
                if (rowVisible(53)) {
                    battleLabel(window,cardFont,name,p+sf::Vector2f{28,float(y+15)},18,{224,234,244});
                    battleLabel(window,cardFont,value,p+sf::Vector2f{float(dialog.x-28),float(y+15)},18,color,1.f);
                    box(window,p+sf::Vector2f{28,float(y+29)},{float(dialog.x-56),8},{49,65,80});
                    if (fraction > 0)
                        box(window,p+sf::Vector2f{28,float(y+29)},{float((dialog.x-56)*std::min(1.,fraction)),8},color);
                }
                y += 53;
            };
            if (countryDetail == CountryDetail::power) {
                const auto ratings = world.powerRanking();
                const auto& rating = ratings[foreignTarget];
                titleRow("Мощь государства");
                hero("Место в мире",std::to_string(rating.rank)+" / "+std::to_string(ratings.size()),gold);
                if (foreignTarget != 0) {
                    textRow(std::string(World::relativePower(rating.total,ratings[0].total)),green);
                    textRow(world.countryThreat(foreignTarget,ratings),gold);
                }
                section("Сравнение с лидерами");
                constexpr std::array names{"Экономика","Сухопутные силы","Авиация","География","Общество"};
                constexpr std::array explanations{"Вес в общем рейтинге: 35%. Налоговая база населения и предприятий.",
                    "Вес в общем рейтинге: 30%. Личный состав, вооружение, состояние, организация и снабжение.",
                    "Вес в общем рейтинге: 15%. Численность, готовность и дальность авиации.",
                    "Вес в общем рейтинге: 5%. Территория, ресурсы, сельское хозяйство и защитный рельеф.",
                    "Вес в общем рейтинге: 15%. Население, устойчивость, легитимность и поддержка правительства."};
                for (int i = 0; i < int(names.size()); ++i) {
                    bar(names[i],std::to_string(int(std::nearbyint(rating.indices[i])))+"% от лидера",rating.indices[i]/100,blue);
                    textRow(explanations[i],muted);
                }
                section("Итоговая оценка");
                std::ostringstream score;
                score << std::fixed << std::setprecision(1) << rating.total << " из 100";
                bar("Сводный индекс",score.str(),rating.total/100,gold);
                textRow("100% в категории означает уровень сильнейшей страны именно в этой категории. Лидеры категорий могут различаться.",muted);
                textRow("Рейтинг оценивает потенциал страны и не предсказывает исход конкретной войны.",muted);
            } else if (countryDetail != CountryDetail::none) {
                const auto& policy = world.diplomacy.countries[0];
                const int day = world.diplomacy.day;
                const auto ready = [&](int available,double cost) -> std::string {
                    if (available > day) return "Доступно с "+hoi5::politicalDate(available);
                    if (policy.capital < cost) return "Недостаточно политического капитала (нужно 2)";
                    return {};
                };
                const auto confirm = [&](std::string caption,std::string reason = {}) {
                    if (!countryDecisionError.empty()) textRow(countryDecisionError,gold);
                    else if (!reason.empty()) textRow(std::move(reason),gold);
                    else actionRow(std::move(caption),applyDomesticDecision);
                };
                if (countryDetail == CountryDetail::population) {
                    titleRow("Население");
                    const double population = std::max(0.,world.profiles[0].population);
                    const auto& production = world.production[0];
                    const auto& stocks = world.stockpiles[0];
                    std::vector<int> territory;
                    double capacity = 0.;
                    for (int i = 0; i < int(world.tiles.size()); ++i) {
                        if (world.tiles[i].owner != 0) continue;
                        territory.push_back(i);
                        capacity += hoi5::populationCapacity(world.tiles[i])*1.20;
                    }
                    const double food = hoi5::populationResourceRatio(production,stocks,"food");
                    const double goods = hoi5::populationResourceRatio(production,stocks,"consumer_goods");
                    const double multiplier = hoi5::populationGrowthMultiplier(world.tiles,territory,food,goods);
                    const double forecast = hoi5::populationMonthlyForecast(world.tiles,territory,multiplier);
                    hero("Население",formatPopulation(population),blue);
                    auto change = std::to_string(std::llround(std::abs(forecast)));
                    for (int i = int(change.size())-3; i > 0; i -= 3) change.insert(std::size_t(i),",");
                    metric("Ожидаемое изменение за месяц",(forecast < 0 ? "-" : "+")+change,forecast < 0 ? red : green);
                    textRow("Прогноз при текущем снабжении и вместимости поселений. Без боевых потерь и изменения границ.",muted);
                    section("Возрастной состав");
                    const std::array ages{std::tuple{"Дети",.23,blue},std::tuple{"Рабочий возраст",.61,green},std::tuple{"Пожилые",.16,gold}};
                    for (const auto& [name,share,color] : ages) {
                        std::ostringstream value;
                        value << formatPopulation(population*share) << "  /  " << std::fixed <<
                            std::setprecision(1) << (population > 0 ? share*100 : 0.) << '%';
                        bar(name,value.str(),population > 0 ? share : 0.,color);
                    }
                    section("Пол и военный ресурс");
                    metric("Мужчины",formatPopulation(population*.52),blue);
                    metric("Женщины",formatPopulation(population*.48),blue);
                    const double obligated = population*.61*.54;
                    const double willingness = std::clamp(.04+policy.warSupport*.62+policy.stability*.13+policy.legitimacy*.13,0.,.82);
                    metric("Военнообязанные",formatPopulation(obligated),gold);
                    metric("Доступно добровольцев",formatPopulation(obligated*willingness),gold);
                    section("Условия жизни");
                    bar("Обеспеченность продовольствием",percent(food),food,food >= 1 ? green : red);
                    bar("Обеспеченность потребительскими товарами",percent(goods),goods,goods >= 1 ? green : red);
                    metric("Предельная вместимость поселений",formatPopulation(capacity),{224,234,244});
                } else if (countryDetail == CountryDetail::support) {
                    titleRow("Общественная поддержка");
                    hero("Поддержка правительства",percent(policy.support),green);
                    bar("Устойчивость",percent(policy.stability),policy.stability,blue);
                    bar("Легитимность",percent(policy.legitimacy),policy.legitimacy,gold);
                    const int wars = int(std::ranges::count_if(world.diplomacy.relations,[](const auto& entry) {
                        return entry.first.first == 0 && entry.second.war;
                    }));
                    const auto effect = [&](int group) {
                        return policy.programHours[group] == 0 ? 0. :
                            policy.programSupportEffect(group,world.profiles[0].population,hoi5::Diplomacy::monthlySupportCost,
                                policy.programFunding[group]);
                    };
                    for (int group = 0; group < int(policyGroups.size()); ++group) {
                        if (group == 0) section("Экономические группы");
                        if (group == 3) section("Социальные группы населения");
                        if (group == 7) section("Политические фракции");
                        const double support = policy.groups[group];
                        const double target = policy.supportTarget(group,world.profiles[0].budget,wars,effect(group),effect(0));
                        std::ostringstream value;
                        value << std::fixed << std::setprecision(1) << 100*support << "%  /  ориентир " << 100*target << '%';
                        bar(policyGroups[group],value.str(),support,target >= support ? green : gold);
                    }
                } else if (countryDetail == CountryDetail::taxes) {
                    titleRow("Налоги");
                    textRow("Изменение относительно базовых налоговых поступлений. Это не процентная ставка налога.",muted);
                    for (int group = 0; group < 3; ++group) {
                        section(policyGroups[group]);
                        if (rowVisible(40)) {
                            battleLabel(window,cardFont,std::to_string(100+10*policy.taxes[group])+"% базового уровня",
                                p+sf::Vector2f{28,float(y+20)},18,gold);
                            for (const int delta : {-1,1})
                                button(delta < 0 ? "−" : "+",{{dialog.x-(delta < 0 ? 112 : 68),y+7},{38,28}},[&,group,delta] {
                                    domesticGroup = group;
                                    domesticTaxDelta = delta;
                                    savedCountryDialogScroll = countryDialogScroll;
                                    openCountryDetail(CountryDetail::taxDecision);
                                });
                        }
                        y += 40;
                        textRow("Поддержка группы: "+percent(policy.groups[group]),muted);
                    }
                } else if (countryDetail == CountryDetail::programs) {
                    titleRow("Программы поддержки");
                    for (int group = 0; group < int(policyGroups.size()); ++group) {
                        if (group == 0) section("Общие и деловые программы");
                        if (group == 3) section("Социальные группы");
                        if (group == 7) section("Политическое представительство");
                        const double hours = policy.programHours[group];
                        if (rowVisible(66)) {
                            const bool active = hours != 0;
                            std::string value = formatMoney(hoi5::Diplomacy::monthlySupportCost)+"/мес.";
                            if (active) {
                                value = (hours < 0 ? "До отмены" : "До "+hoi5::politicalDate(day+int(std::ceil(hours/24))))+
                                    " | "+value;
                                if (policy.programFunding[group] < .999)
                                    value += " | финансирование "+percent(policy.programFunding[group]);
                            }
                            battleLabel(window,cardFont,policyGroups[group],p+sf::Vector2f{28,float(y+18)},18);
                            battleLabel(window,cardFont,value,p+sf::Vector2f{28,float(y+46)},17,active ? green : muted);
                            button(active ? "Завершить" : "Начать",{{dialog.x-124,y+23},{96,28}},[&,group] {
                                domesticGroup = group;
                                savedCountryDialogScroll = countryDialogScroll;
                                supportTerm = 3;
                                openCountryDetail(CountryDetail::programDecision);
                            });
                        }
                        y += 66;
                    }
                } else if (countryDetail == CountryDetail::exportLimit) {
                    titleRow(policy.exportLimit < .999 ? "Открыть экспорт" : "Ограничить экспорт");
                    metric("Текущий лимит",percent(policy.exportLimit)+" базовой мощности",muted);
                    metric("Новый лимит",std::to_string(pendingExport)+"%",gold);
                    if (rowVisible(56)) {
                        countryExportSlider = {origin+sf::Vector2i{28,y+16},{dialog.x-56,24}};
                        const auto track = sf::Vector2f(countryExportSlider.position)+sf::Vector2f{0,9};
                        const float width = float(countryExportSlider.size.x);
                        box(window,track,{width,6},{61,78,92});
                        if (pendingExport > 0) box(window,track,{width*pendingExport/100,6},gold);
                        sf::CircleShape knob(8);
                        knob.setPosition(track+sf::Vector2f{width*pendingExport/100-8,-5});
                        knob.setFillColor(gold);
                        window.draw(knob);
                    }
                    y += 56;
                    textRow("0%: экспорт остановлен. 100%: полная торговая мощность. Лимит не гарантирует наличие покупателей.",muted);
                    section("Последствия");
                    textRow("Меняется пропускная способность экспортных контрактов. Снижение лимита может уменьшить продажи и поддержку бизнеса.");
                    textRow("Импорт не ограничивается этим решением.",muted);
                    confirm("Применить лимит",std::abs(policy.exportLimit*100-pendingExport) < 1e-6 ?
                        "Лимит не изменён" : ready(world.diplomacy.marketCooldown[0],2));
                } else if (countryDetail == CountryDetail::externalMarket) {
                    const std::string title = policy.externalAccess ? "Закрыть внешний рынок" : "Открыть внешний рынок";
                    titleRow(title);
                    textRow(title);
                    textRow(std::string("Прямые сделки со странами сохраняются. ")+(policy.externalAccess ?
                        "Заявки внешнему рынку перестанут исполняться." : "Заявки внешнему рынку снова смогут исполняться."));
                    textRow("Расход сейчас: $0; повтор с "+hoi5::politicalDate(day+7));
                    capitalRow(2);
                    confirm("Подтвердить решение",ready(world.diplomacy.marketCooldown[1],2));
                } else if (countryDetail == CountryDetail::taxDecision) {
                    constexpr std::array names{"население","малый и средний бизнес","крупный бизнес"};
                    const auto title = std::string(domesticTaxDelta < 0 ? "Снизить налог: " : "Повысить налог: ")+
                        names[domesticGroup];
                    titleRow(title);
                    textRow(title);
                    textRow("Изменение налоговых поступлений группы на 10% базового уровня. Отношение меняется постепенно.");
                    textRow("Расход сейчас: $0; повтор с "+hoi5::politicalDate(day+30));
                    capitalRow(2);
                    auto reason = ready(policy.taxReady[domesticGroup],2);
                    if (reason.empty() && std::abs(policy.taxes[domesticGroup]+domesticTaxDelta) > 2)
                        reason = "Достигнут предел ставки";
                    confirm("Подтвердить решение",std::move(reason));
                } else if (countryDetail == CountryDetail::programDecision) {
                    const bool active = policy.programHours[domesticGroup] != 0;
                    titleRow(std::string(active ? "Завершить поддержку: " : "Поддержка: ")+policyGroups[domesticGroup]);
                    if (active) {
                        textRow("Прекращает регулярные расходы; поддержка группы постепенно меняется.");
                        textRow("Регулярные расходы прекратятся. Эффект программы на лояльность постепенно исчезнет.");
                        confirm("Подтвердить решение");
                    } else {
                        metric("Бюджет программы",formatMoney(hoi5::Diplomacy::monthlySupportCost)+"/мес.",gold);
                        section("Срок действия");
                        const int width = (dialog.x-56)/int(supportTerms.size());
                        if (rowVisible(44))
                            for (int i = 0; i < int(supportTerms.size()); ++i)
                                button(supportTerms[i],{{28+i*width,y+6},{width-4,30}},[&,i] {
                                    supportTerm = i;
                                    countryDecisionHits.clear();
                                });
                        y += 44;
                        textRow(supportHours[supportTerm] < 0 ? "До ручного завершения" :
                            "Завершится "+hoi5::politicalDate(day+supportHours[supportTerm]/24),blue);
                        section("Ожидаемый эффект");
                        metric("Текущая поддержка группы",percent(policy.groups[domesticGroup]),green);
                        std::ostringstream effect;
                        effect << "При полном финансировании: до +" << std::fixed << std::setprecision(2)
                               << 100*policy.programSupportEffect(domesticGroup,world.profiles[0].population,hoi5::Diplomacy::monthlySupportCost)
                               << " п.п. к долгосрочному ориентиру.";
                        textRow(effect.str());
                        textRow("Изменения накапливаются месяцами. Эффект зависит от размера страны и группы, финансирования, снабжения и легитимности.",muted);
                        textRow("Расходы списываются за время действия. При нехватке средств финансирование снижается; программа не исчезает.",muted);
                        confirm("Начать программу",world.profiles[0].budget < hoi5::Diplomacy::monthlySupportCost ?
                            "Недостаточно средств" : ready(day,2));
                    }
                }
            } else {
                using Action = hoi5::ForeignAction;
                const auto& action = *countryDecision;
                const auto& diplomacy = std::as_const(world.diplomacy);
                const auto& relation = diplomacy.relation(0,foreignTarget);
                const auto date = hoi5::politicalDate;
                const bool removeEmbargo = action.action == Action::embargo && relation.embargoes.contains(0);
                const auto title = action.action == Action::embargo ?
                    (removeEmbargo ? "Снять эмбарго" : "Ввести эмбарго") : action.label;
                battleLabel(window,cardFont,std::string(title),p+sf::Vector2f{24,28},21,{224,234,244});
                textRow(std::string(title));
                textRow(std::string(action.description));
                if (hasDecisionAmount()) {
                    box(window,p+sf::Vector2f{28,float(y+4)},{float(dialog.x-152),28},{35,55,63});
                    label(window,cardFont,"Сумма: "+(countryDecisionAmount.empty() ? "0" : countryDecisionAmount)+" |",
                        p+sf::Vector2f{38,float(y+6)},15,{170,220,195});
                    for (const long long step : {-1000000LL,1000000LL}) {
                        button(step < 0 ? "-" : "+",{{dialog.x-(step < 0 ? 116 : 68),y+4},{38,28}},[&,step] {
                            countryDecisionAmount = std::to_string(std::clamp(amountValue()+step,1000LL,1000000000000LL));
                            countryDecisionError.clear();
                            countryDecisionHits.clear();
                        });
                    }
                    y += 36;
                }
                const double amount = hasDecisionAmount() ? double(amountValue()) : 0.;
                const double cost = action.action == Action::aid ? amount : action.money;
                textRow("Расход сейчас: $"+formatAmount(cost)+"; повтор с "+date(diplomacy.day+action.cooldown));
                if (action.capital > 0) capitalRow(action.capital);
                const double opinion = removeEmbargo ? 0. : action.opinion;
                const double trust = action.action == Action::war ? -relation.trust : action.trust;
                if (opinion != 0 || trust != 0) {
                    std::ostringstream effects;
                    effects << "Отношение: " << std::showpos << opinion << "; доверие: "
                            << std::fixed << std::setprecision(0) << trust*100 << '%';
                    textRow(effects.str());
                }
                if (action.action == Action::loan) textRow("Срок: 12 мес.; ставка: 5.0% годовых");
                if (!hoi5::offerNames(action.action).first.empty())
                    textRow("Ожидаемый ответ: "+date(diplomacy.day+3));
                if (action.action == Action::peace) textRow("Перемирие: 30 дн.");
                if (action.action == Action::justify) textRow("Завершение подготовки: "+date(diplomacy.day+30));
                if (action.action == Action::war) textRow("Война ухудшит репутацию и отношение другой страны.");
                const auto reason = diplomacy.reason(0,foreignTarget,action,world.profiles,amount);
                if (!countryDecisionError.empty()) textRow(countryDecisionError);
                else if (!reason.empty()) textRow(std::string(reason));
                if (reason.empty())
                    button("Подтвердить решение",{{28,y+4},{dialog.x-56,28}},[&] {
                        const double sum = hasDecisionAmount() ? double(amountValue()) : 0.;
                        countryDecisionError = world.performForeignAction(0,foreignTarget,*countryDecision,sum);
                        if (!countryDecisionError.empty()) return;
                        countryDecision = nullptr;
                        foreignMessage = "Решение принято";
                        tradeForecast.reset();
                        resourceForecast.reset();
                        {
                        hoi5::DebugMeasure timing(&debug,"server_economy_history");
                        world.updateEconomyHistory(simulation.elapsedHours,simulation.marketTickCount);
                    }
                        world.updateStatus();
                    },true);
            }
            if (countryDetail != CountryDetail::none) {
                countryDialogMaxScroll = std::max(0,y+countryDialogScroll-(dialog.y-26));
                if (countryDialogMaxScroll > 0) {
                    const float track = dialog.y-120.f, thumb = std::max(24.f,track*track/(track+countryDialogMaxScroll));
                    box(window,p+sf::Vector2f{dialog.x-12.f,92},{4,track},{47,64,79});
                    box(window,p+sf::Vector2f{dialog.x-12.f,92+(track-thumb)*countryDialogScroll/countryDialogMaxScroll},
                        {4,thumb},{132,156,184});
                }
            }
        }
        if (playing) {
            window.setView(gui);
            mapLayerProgress = std::clamp(mapLayerProgress+(mapLayerMenu ? dt : -dt)*8,0.f,1.f);
            if (mapLayerProgress > .01f && !pauseMenu) {
                const auto pointer = sf::Vector2f(sf::Mouse::getPosition(window));
                const auto alpha = static_cast<std::uint8_t>(235*mapLayerProgress);
                for (int i = 0; i <= int(mapLayerLabels.size()); ++i) {
                    const auto rect = mapLayerOption(window.getSize(),i,mapLayerProgress);
                    const bool filter = i == int(mapLayerLabels.size());
                    const bool active = filter ? airDefenseOverlay : i == int(mapLayer);
                    const bool hovered = rect.contains(pointer);
                    const bool disabled = i == int(MapLayer::weather);
                    const auto fill = disabled ? sf::Color(38,43,49,alpha) : active ? sf::Color(58,92,128,alpha)
                        : hovered ? sf::Color(50,64,82,alpha) : sf::Color(24,32,42,alpha);
                    const auto border = disabled ? sf::Color(88,94,102,alpha) : active ? sf::Color(120,210,255,alpha)
                        : hovered ? sf::Color(150,178,210,alpha) : sf::Color(92,112,136,alpha);
                    box(window,rect.position,rect.size,fill,border);
                    battleLabel(window,font,filter ? "ПВО" : mapLayerLabels[i],rect.position+sf::Vector2f{14,17},13,
                        disabled ? sf::Color(128,136,145,alpha) : sf::Color(232,238,245,alpha));
                }
            }
            resourceGroupProgress = std::clamp(resourceGroupProgress+(resourceGroupMenu ? dt : -dt)*8,0.f,1.f);
            if (mapFilterCount() > 0 && !pauseMenu) {
                const auto pointer = sf::Vector2f(sf::Mouse::getPosition(window));
                const auto button = resourceGroupRect(window.getSize());
                const bool political = mapLayer == MapLayer::political;
                const int selectedFilter = political ? int(politicalFilter) : resourceGroup;
                const auto labelFor = [&](int index) -> std::string_view {
                    return political ? politicalMapLabels[index] : resourceMapGroups[index].label;
                };
                const auto colorFor = [&](int index) {
                    return political ? politicalMapSwatches[index] : resourceMapGroups[index].color;
                };
                box(window,button.position,button.size,button.contains(pointer) || resourceGroupMenu
                    ? sf::Color(58,82,108) : sf::Color(30,40,52),{140,170,205});
                box(window,button.position+sf::Vector2f{11,15},{14,14},colorFor(selectedFilter));
                battleLabel(window,font,std::string(labelFor(selectedFilter)),button.position+sf::Vector2f{34,22},11);
                if (political && politicalFilter == PoliticalMapFilter::relations && button.contains(pointer) && !resourceGroupMenu)
                    hoverHelp = HoverHelp{"Отношения к нам",
                        {"Синий — наша страна. Зелёный — союз.", "Красный — война. Жёлтый — перемирие.", "Серый — мир."}};
                if (resourceGroupProgress > .01f) {
                    const auto alpha = static_cast<std::uint8_t>(235*resourceGroupProgress);
                    for (int i = 0; i < mapFilterCount(); ++i) {
                        const auto option = resourceGroupRect(window.getSize(),i,resourceGroupProgress);
                        const auto color = colorFor(i);
                        const auto fill = i == selectedFilter ? sf::Color(58,92,128,alpha)
                            : option.contains(pointer) ? sf::Color(50,64,82,alpha) : sf::Color(24,32,42,alpha);
                        const auto border = i == selectedFilter ? sf::Color(120,210,255,alpha)
                            : option.contains(pointer) ? sf::Color(150,178,210,alpha) : sf::Color(92,112,136,alpha);
                        box(window,option.position,option.size,fill,border);
                        box(window,option.position+sf::Vector2f{10,10},{14,14},{color.r,color.g,color.b,alpha});
                        battleLabel(window,font,std::string(labelFor(i)),option.position+sf::Vector2f{32,17},11,{220,230,240,alpha});
                    }
                }
            }
            if (showWeatherMessage && weatherMessage.getElapsedTime().asSeconds() < 2 && !pauseMenu)
                battleLabel(window,font,"Погодный слой будет добавлен позже",{size.x-74,size.y-40},13,sf::Color::White,1.f);
            if (!pauseMenu && !world.profiles.empty() && !world.diplomacy.countries.empty() &&
                populationHoverRect.contains(sf::Vector2f(sf::Mouse::getPosition(window)))) {
                const auto& policy = world.diplomacy.countries.front();
                drawPopulationSummary(window,font,populationHoverRect,world.profiles.front().population,
                    policy.stability,policy.legitimacy,policy.warSupport);
            }
            if (!pauseMenu && !world.profiles.empty() && !world.treasury.empty() &&
                budgetHoverRect.contains(sf::Vector2f(sf::Mouse::getPosition(window)))) {
                const double trade = world.economyCurrent.empty() ? 0. : world.economyCurrent.front().trade;
                drawBudgetSummary(window,font,budgetHoverRect,world.profiles.front().budget,world.taxedTreasury(0),trade);
            }
            if (!pauseMenu && resourceHoverRect.contains(sf::Vector2f(sf::Mouse::getPosition(window))) &&
                (!resourceProblems[0].empty() || !resourceProblems[1].empty())) {
                const float x = std::min(resourceHoverRect.position.x,size.x-332);
                const float top = resourceHoverRect.position.y+resourceHoverRect.size.y+8;
                const float height = 76+16.f*(resourceProblems[0].size()+resourceProblems[1].size());
                box(window,{x,top},{320,height},{18,24,31,245},{140,160,184});
                battleLabel(window,font,"Проблемы ресурсов",{x+12,top+20},12);
                float y = top+38;
                constexpr std::array names{"Красные:","Желтые:"};
                constexpr sf::Color colors[]{{240,108,98},{238,198,90}};
                for (std::size_t severity = 0; severity < resourceProblems.size(); ++severity) {
                    const auto& items = resourceProblems[severity];
                    if (items.empty()) continue;
                    battleLabel(window,font,names[severity],{x+12,y},11,colors[severity]);
                    y += 16;
                    for (std::size_t i = 0; i < std::min<std::size_t>(5,items.size()); ++i) {
                        battleLabel(window,font,"- "+std::string(resourceDisplayName(items[i])),
                            {x+22,y},11,{220,230,240});
                        y += 15;
                    }
                }
            }
            if (!pauseMenu && !countryModalOpen()) {
                const auto warning = std::ranges::find_if(warningBounds,[&](const auto& rect) {
                    return rect.contains(sf::Mouse::getPosition(window));
                });
                if (warning != warningBounds.end()) {
                    const auto& item = topWarnings[warning-warningBounds.begin()];
                    const float x = std::min(float(warning->position.x),size.x-312);
                    const float y = float(warning->position.y+warning->size.y+8);
                    box(window,{x,y},{300,48+16.f*item.lines.size()},{18,24,31,246},{150,170,194});
                    battleLabel(window,cardFont,item.title,{x+12,y+20},16);
                    for (std::size_t i = 0; i < item.lines.size(); ++i)
                        battleLabel(window,cardFont,item.lines[i],{x+18,y+38+16.f*i},14,{220,230,240});
                }
            }
            if (hoverHelp && !pauseMenu && !countryModalOpen()) {
                const auto mouse = sf::Vector2f(sf::Mouse::getPosition(window));
                constexpr float width = 358;
                const float height = 42+20.f*hoverHelp->lines.size();
                const float x = std::clamp(mouse.x+14,8.f,size.x-width-8);
                const float y = std::clamp(mouse.y+17,86.f,size.y-height-8);
                box(window,{x,y},{width,height},{18,24,31,248},{150,170,194});
                battleLabel(window,cardFont,hoverHelp->title,{x+12,y+17},17,{238,244,250});
                for (std::size_t i = 0; i < hoverHelp->lines.size(); ++i)
                    battleLabel(window,cardFont,hoverHelp->lines[i],{x+12,y+38+20.f*i},15,{220,230,240});
            }
            std::ostringstream status;
            status << "FPS: " << debug.fps << " | Zoom: " << std::fixed << std::setprecision(2) << zoom;
            box(window,{size.x-176,5},{170,23},{12,18,24,222});
            battleLabel(window,font,status.str(),{size.x-12,16},13,sf::Color::White,1.f);
            if (debug.visible) {
                const auto overlayStart = DebugClock::now();
                const float pitch = std::min(14.f,(size.y-28)/float(std::size(hoi5::debugRows)));
                box(window,{12,12},{360,12+pitch*std::size(hoi5::debugRows)},{12,18,24,222},{100,126,155,210});
                for (std::size_t i = 0; i < std::size(hoi5::debugRows); ++i) {
                    const auto& row = hoi5::debugRows[i];
                    const float y = 18+pitch*(i+.5f);
                    battleLabel(window,font,std::string(row.label),{20,y},11);
                    if (row.keys[0].empty()) continue;
                    std::ostringstream value;
                    value << std::fixed << std::setprecision(2) << debug.average(row) << " ms";
                    battleLabel(window,font,value.str(),{364,y},11,sf::Color::White,1.f);
                }
                debug.record("profiler_overlay",overlayStart);
            }
        }
        debug.record("draw_total",drawStart);
        if (music) {
            if (musicReview.getElapsedTime().asSeconds() >= 1) {
                musicCategory = playing ? music->category(world) : hoi5::economyMusic;
                (void)musicReview.restart();
            }
            music->update(musicCategory);
        }
        if ((countrySmoke || armySmoke) && argc == 3) {
            constexpr std::array countryScreenshots{"","","countries.png","summary.png","decisions.png","mission.png","",
                "domestic.png","taxes.png","tax-confirmation.png"};
            constexpr std::array armyScreenshots{"","overview.png","designer.png","","recruit.png","","","queue.png",
                "","","","command.png","","front.png"};
            const auto screenshots = countrySmoke ? std::span<const char* const>(countryScreenshots) :
                std::span<const char* const>(armyScreenshots);
            const int frame = countrySmoke ? countrySmokeFrame : armySmokeFrame;
            if (frame < int(screenshots.size()) && *screenshots[frame]) {
                sf::Texture capture(window.getSize());
                capture.update(window);
                if (!capture.copyToImage().saveToFile(std::filesystem::path(argv[2])/screenshots[frame]))
                    return 1;
            }
        }
        if (argc == 3 && ((warningSmoke && warningSmokeFrame == 0) || constructionSmoke || tradeSmoke)) {
            sf::Texture capture(window.getSize());
            capture.update(window);
            if (!capture.copyToImage().saveToFile(argv[2])) return 1;
        }
        window.display();
        if (countrySmoke) {
            const auto click = [&](sf::Vector2i position) {
                countrySmokeClick = sf::Event::MouseButtonPressed{sf::Mouse::Button::Left,position};
            };
            switch (countrySmokeFrame++) {
                case 0: click({300,59}); break;
                case 1:
                    if (!diplomacyPanel || !countryList) return 1;
                    countryPanelProgress = 1.f;
                    break;
                case 2: click({28,306}); break;
                case 3:
                    if (countryList || foreignTarget != 1 || countryTab != CountryTab::summary) return 1;
                    click({365,155});
                    break;
                case 4:
                    if (countryTab != CountryTab::actions) return 1;
                    click({28,186});
                    break;
                case 5:
                    if (countryDecision != &hoi5::foreignActions[0] || countryDecisionHits.size() != 2) return 1;
                    click(countryDecisionHits.back().rect.getCenter());
                    break;
                case 6:
                    if (countryDecision || world.diplomacy.history.empty() ||
                        world.diplomacy.history.front().target != 1 ||
                        world.diplomacy.history.front().message != hoi5::foreignActions[0].label) return 1;
                    click({30,59});
                    break;
                case 7:
                    if (countryList || foreignTarget != 0 || countryTab != CountryTab::actions) return 1;
                    click({28,246});
                    break;
                case 8:
                    if (countryDetail != CountryDetail::taxes || countryDecisionHits.size() < 3) return 1;
                    click(countryDecisionHits[2].rect.getCenter());
                    break;
                case 9:
                    if (countryDetail != CountryDetail::taxDecision || countryDecisionHits.size() != 2) return 1;
                    click(countryDecisionHits.back().rect.getCenter());
                    break;
                default:
                    return countryDetail == CountryDetail::taxes &&
                        world.diplomacy.countries[0].taxes[0] == 1 ? 0 : 1;
            }
        } else if (armySmoke) {
            const auto click = [&](sf::Vector2i position) {
                countrySmokeClick = sf::Event::MouseButtonPressed{sf::Mouse::Button::Left,position};
            };
            switch (armySmokeFrame++) {
                case 0: click({346,59}); break;
                case 1:
                    if (!militaryPanel || armyTab != ArmyTab::overview) return 1;
                    click({160,165});
                    break;
                case 2:
                    if (armyTab != ArmyTab::designer) return 1;
                    click({386,278});
                    break;
                case 3:
                    if (armyDraft[1] != 1) return 1;
                    click({42,510});
                    break;
                case 4:
                    if (armyTab != ArmyTab::recruit || world.playerDesigns.size() != 1) return 1;
                    click({42,316});
                    break;
                case 5: {
                    if (!armyPickingSite) return 1;
                    const int capital = world.capitals[0];
                    const auto point = window.mapCoordsToPixel(center(capital%world.size,capital/world.size),camera);
                    if (armyBounds().contains(point) || !world.safeTrainingSite(0,capital)) return 1;
                    click(point);
                    break;
                }
                case 6:
                    if (armyPickingSite || armySite != world.capitals[0]) return 1;
                    for (const auto& [key,amount] : world.trainingDesign(armyType).capacity)
                        world.stockpiles[0][key] += amount;
                    click({42,346});
                    break;
                case 7:
                    if (world.training.size() != 1 || world.training.front().type != armyType) return 1;
                    click({360,418});
                    break;
                case 8:
                    if (!world.training.empty()) return 1;
                    click({346,59});
                    break;
                case 9:
                    if (militaryPanel || !world.selectableDivision(0,0)) return 1;
                    selectedDivisions = {0};
                    syncArmySelection();
                    break;
                case 10:
                    if (armyCommandBounds.size.x == 0) return 1;
                    click(armyCommandBounds.position+sf::Vector2i{80,42});
                    break;
                case 11:
                    if (world.armies.size() != 1 || activeArmy != 1 || world.armyMembers(0,1) != std::vector<int>{0}) return 1;
                    if (armyCommandBounds.findIntersection(wingListBounds(int(wingCards().size())))) return 1;
                    click(armyCommandBounds.position+sf::Vector2i{66,12});
                    zoom = .42f;
                    camera.setSize(sf::Vector2f(window.getSize())/zoom);
                    break;
                case 12: {
                    if (frontMode != FrontMode::automatic) return 1;
                    const auto size = sf::Vector2i(window.getSize());
                    bool found = false;
                    for (int tile = 0; tile < int(world.tiles.size()); ++tile) {
                        if (world.frontBorderOwner(0,tile) == -2) continue;
                        const auto point = window.mapCoordsToPixel(center(tile%world.size,tile/world.size),camera);
                        if (point.x < 10 || point.x >= size.x-10 || point.y < 94 || point.y >= size.y-14 ||
                            armyCommandBounds.contains(point) || divisionListBounds.contains(point)) continue;
                        click(point);
                        found = true;
                        break;
                    }
                    if (!found) return 1;
                    break;
                }
                case 13:
                    if (world.armies[0].front.empty() || !world.armies[0].executing || frontMode != FrontMode::none) return 1;
                    click(armyCommandBounds.position+sf::Vector2i{199,12});
                    break;
                case 14:
                    if (world.armies[0].executing) return 1;
                    click(armyCommandBounds.position+sf::Vector2i{199,12});
                    break;
                case 15:
                    if (!world.armies[0].executing) return 1;
                    click(armyCommandBounds.position+sf::Vector2i{166,12});
                    break;
                case 16: {
                    if (frontMode != FrontMode::offensive) return 1;
                    const auto size = sf::Vector2i(window.getSize());
                    bool found = false;
                    for (int tile = 0; tile < int(world.tiles.size()); ++tile) {
                        if (world.tiles[tile].water || world.tiles[tile].owner == 0) continue;
                        const auto point = window.mapCoordsToPixel(center(tile%world.size,tile/world.size),camera);
                        if (point.x < 10 || point.x >= size.x-85 || point.y < 94 || point.y >= size.y-60 ||
                            armyCommandBounds.contains(point) || divisionListBounds.contains(point)) continue;
                        click(point);
                        found = true;
                        break;
                    }
                    if (!found) return 1;
                    break;
                }
                case 17: {
                    if (!frontDrag || frontPreview.empty()) return 1;
                    const int tile = frontPreview.back();
                    const auto point = window.mapCoordsToPixel(center(tile%world.size,tile/world.size),camera);
                    countrySmokeClick = sf::Event::MouseButtonReleased{sf::Mouse::Button::Left,point};
                    break;
                }
                default: return !world.armies[0].offensive.empty() && frontMode == FrontMode::none ? 0 : 1;
            }
        } else if (warningSmoke) {
            const auto click = [&](std::string_view label) {
                const auto item = std::ranges::find(topWarnings,label,&TopWarning::label);
                if (item == topWarnings.end()) return false;
                const auto point = warningBounds[item-topWarnings.begin()].getCenter();
                countrySmokeClick = sf::Event::MouseButtonPressed{sf::Mouse::Button::Left,point};
                return true;
            };
            switch (warningSmokeFrame++) {
                case 0:
                    if (topWarnings.size() != 7 || !click("L")) {
                        for (const auto& item : topWarnings) std::cerr << item.label << ' ';
                        std::cerr << '\n';
                        return 1;
                    }
                    break;
                case 1:
                    if (mapLayer != MapLayer::supply || economicPanel != 2 || !click("S")) return 1;
                    for (std::size_t tile = 0; tile < world.tiles.size(); ++tile)
                        for (std::size_t vertex = 0; vertex < 18; ++vertex)
                            if (map[tile*18+vertex].color != supplyColor(world.tiles[tile])) return 1;
                    break;
                case 2:
                    if (economicPanel != 2 || !click("T")) return 1;
                    break;
                case 3:
                    if (!tradePanel || !click("C")) return 1;
                    break;
                case 4:
                    if (!constructionPanel || !click("A")) return 1;
                    break;
                case 5:
                    if (!acknowledgedLosses[0] || !click("Б")) return 1;
                    break;
                default: return acknowledgedLosses[1] && topWarnings.size() == 5 ? 0 : 1;
            }
        } else if (smoke && playing) window.close();
        if (generationSmoke && (!errorMessage.empty() || startupClock.getElapsedTime().asSeconds() > 60))
            throw std::runtime_error(errorMessage.empty() ? "Generation timed out" : errorMessage);
    }
} catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
}
