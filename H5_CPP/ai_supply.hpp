#pragma once

#include "ai_regions.hpp"
#include "ai_flow.hpp"
#include "python_seed.hpp"
#include <algorithm>
#include <cmath>
#include <list>
#include <map>
#include <optional>
#include <set>
#include <span>
#include <string_view>
#include <utility>
#include <vector>

namespace hoi5 {

struct BotSupplyPoint { int tile; double weight, passability, current; };
struct BotSupplyCandidate { int tile; double strength, multiplier; };
struct BotSupplyChoice { double gain; int tile; };

enum class BotTaskStatus { planned, blocked, executing, waitingMarket, waitingOffer, succeeded, failed, cancelled };

struct BotTask {
    enum class Kind { supply, buy, sell, build, specialize, fortify, rebuildDefense, recruit, air, claim,
        politics, support, tax, intelligence };
    Kind kind;
    int createdHour;
    int tile = -1;
    std::string_view resource;
    double amount = 0.;
    BotTaskStatus status = BotTaskStatus::planned;
    int retryHour = 0, marketTick = 0;
    double targetCoverage = 0.;
    int defenseType = -1;
    int trainingType = -1;
    int buildingSpec = -1;
    std::string_view sector;
    int targetCountry = -1;
    int politicalAction = -1;
    bool exactSite = false;
    bool constructionPurchase = false;

    bool pending() const { return status == BotTaskStatus::planned || status == BotTaskStatus::blocked; }
    bool active() const { return pending() || status == BotTaskStatus::executing ||
        status == BotTaskStatus::waitingMarket || status == BotTaskStatus::waitingOffer; }
};

enum class BotCourse { development, deterrence, warPreparation, defense, recovery };
enum class BotPersonality { cautious, merchant, opportunist };
using BotCourseChoice = std::pair<BotCourse,int>;
using BotCourseOptions = std::vector<std::pair<double,BotCourseChoice>>;

struct BotEstimate { double value, low, high; int observedHour; };
struct BotMilitaryReport {
    std::array<BotEstimate,militaryMetrics> divisions;
    BotEstimate divisionCount, aircraft, airDefense;
};

struct BotReview {
    bool monthly;
    double nextHour;
    int stage = 0, countryCursor = 0;
    BotCourseOptions options;
};

struct BotSupplyState {
    int owner;
    double nextDaily;
    int target = -1;
    std::list<BotTask> tasks;
    double tradeBalance = 0.;
    std::vector<std::pair<int,int>> defenseTargets;
    std::vector<BotRegion> regions;
    double nextMicro = 0.;
    int nextPeaceDeployment = 0;
    int expansionTarget = -1, offensiveFocus = -1, reserve = -1;
    bool urgent = false;
    std::map<int,int> hexAssignments, frontQuotas, lastOrders;
    std::map<int,int> armyIds;
    std::set<int> resting;
    PythonRandom rng{0};
    double aggression{};
    BotPersonality personality = BotPersonality::cautious;
    double intelligence = .25;
    int nextEmergencyDay = 0;
    double emergencyDebt = 0.;
    double nextWeekly{}, nextMonthly{};
    double nextRecruitment{};
    double nextAir{};
    int nextWartimeAirRefresh{};
    int nextAirDefenseMove{};
    double nextEconomy{};
    double nextExpansion{};
    double nextDiplomacy{};
    BotCourseChoice course{BotCourse::development,-1};
    int courseSince{};
    std::array<double,5> courseBias{};
    std::map<int,double> militaryBias;
    std::map<int,BotMilitaryReport> militaryReports;
    std::map<std::pair<int,std::string_view>,BotDependency> dependencies;
    std::vector<BotReview> reviews;
    struct WarObjective { int hour, anchor; std::map<int,int> distances; };
    std::map<int,WarObjective> warObjectives;
};

template<class T>
const T* botChooseClose(PythonRandom& rng,const std::vector<std::pair<double,T>>& candidates,double margin = .12) {
    if (candidates.empty()) return nullptr;
    const double best = std::ranges::max_element(candidates,{},&std::pair<double,T>::first)->first;
    const double tolerance = std::max(1e-9,std::abs(best)*margin);
    std::vector<std::pair<double,const T*>> pool;
    double total = 0.;
    for (const auto& [score,value] : candidates) {
        if (score < best-tolerance) continue;
        total += std::exp((score-best)/tolerance);
        pool.emplace_back(total,&value);
    }
    if (pool.size() == 1) return pool.front().second;
    const double draw = rng.uniform()*total;
    const auto selected = std::ranges::upper_bound(pool,draw,{},&std::pair<double,const T*>::first);
    return selected == pool.end() ? pool.back().second : selected->second;
}

inline int supplyHexDistance(int first,int second,int width) {
    const int dq = first%width-second%width, dr = first/width-second/width;
    return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
}

inline std::optional<BotSupplyChoice> bestBotSupplySite(int width,std::span<const BotSupplyPoint> points,
                                                     std::span<const BotSupplyCandidate> candidates) {
    std::optional<BotSupplyChoice> best;
    for (const auto& candidate : candidates) {
        double gain = 0.;
        for (const auto& point : points) {
            const int distance = supplyHexDistance(candidate.tile,point.tile,width);
            if (distance > 7) continue;
            const double expected = candidate.strength*std::pow(.78,distance)*(.42+.58*point.passability);
            gain += std::max(0.,std::min(.6,expected)-point.current)*point.weight;
        }
        gain *= candidate.multiplier;
        if (gain > .05 && (!best || gain > best->gain)) best = BotSupplyChoice{gain,candidate.tile};
    }
    return best;
}

}
