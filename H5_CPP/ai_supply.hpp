#pragma once

#include "ai_regions.hpp"
#include "ai_flow.hpp"
#include "ai_scheduler.hpp"
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

struct BotSupplyPoint { int tile; double weight, passability, current; double target = .6; };
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

inline double botSustainmentTarget(double recoveryAtFull,double dailyLoss,double enemyRecovery,int difficulty) {
    if(recoveryAtFull<=0 || (dailyLoss<=0 && enemyRecovery<=0)) return .5;
    const double margin=difficulty==3?1.15:difficulty==2?1.05:1.;
    return std::clamp((dailyLoss+enemyRecovery*margin)/recoveryAtFull,.5,difficulty==3?.9:.75);
}

struct BotSupplyState {
    int owner;
    double nextDaily;
    double nextSupplyPlan{},nextDefensePlan{};
    int dailyPlansRun{},economyPlansRun{};
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
    struct FrontPlan {
        int enemy = -1, diversion = -1, staging = -1, attackPost = -1;
        int reserve = -1, expires = 0, enemyAtDiversion = 0;
    };
    FrontPlan frontPlan;
    int nextFrontPlan = 0, nextCoalitionSupport = 0;
    std::vector<std::pair<int,int>> recentAirRaids;
    std::vector<std::pair<int,int>> recentBreakthroughs;
    double nextWeekly{}, nextMonthly{};
    double nextRecruitment{};
    double nextAir{};
    int nextWartimeAirRefresh{};
    int nextAirDefenseMove{};
    double nextEconomy{};
    CompiledProductionBalance planningBalance;
    int nextFiscalReview{},demobilizedDivisions{},parkedAircraft{};
    Stockpile importTargets,exportTargets,exportFloors,commercialDemand;
    double sustainableExportIncome{},recurringImportCost{};
    std::string_view commercialRecipe;
    std::map<std::string_view,int> deficitSince;
    Stockpile sovereignNeeds;
    ProductionPlan sovereignFullPlan;
    std::array<ProductionFlows,productionStages> sovereignPassive;
    Stockpile sovereignUses;
    int nextSovereigntyReview{};
    double sovereignPower{};
    int sovereignClaim=-1,sovereignDeposit=-1,sovereignEnemy=-1;
    std::map<int,int> supplyPresenceSince;
    struct OrgObservation { int owner,tile,hour;double organization; };
    struct Sustainment { double dailyLoss{},enemyRecovery{},target=.5;int hour{}; };
    std::map<int,OrgObservation> orgObservations;
    std::map<int,Sustainment> sustainment;
    std::map<int,int> frontHoldSince;
    std::map<std::pair<int,int>,std::pair<double,int>> projectProgress;
    std::set<std::pair<int,int>> deferredProjects;
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
    static const auto falloff = [] {
        std::array<double,8> values{};
        for (int distance = 0; distance < int(values.size()); ++distance)
            values[distance] = std::pow(.78,distance);
        return values;
    }();
    // Only points within seven hexes can contribute. Index fixed-size map
    // blocks, then retain original point order for identical floating-point sums.
    constexpr int block=8;
    const int columns=(width+block-1)/block;
    const bool indexed=width>0 && points.size()>32 && std::ranges::all_of(points,[&](const auto& p){return p.tile>=0 && p.tile<width*width;});
    std::vector<std::vector<std::size_t>> buckets(indexed?columns*columns:0);
    if(indexed) for(std::size_t i=0;i<points.size();++i) {
        const int tile=points[i].tile;
        buckets[(tile/width/block)*columns+tile%width/block].push_back(i);
    }
    std::vector<std::size_t> nearby;
    std::optional<BotSupplyChoice> best;
    for (const auto& candidate : candidates) {
        double gain = 0.;
        const auto add=[&](const auto& point) {
            const int distance = supplyHexDistance(candidate.tile,point.tile,width);
            if (distance > 7) return;
            const double expected = candidate.strength*falloff[distance]*(.42+.58*point.passability);
            gain += std::max(0.,std::min(point.target,expected)-point.current)*point.weight;
        };
        if(indexed && candidate.tile>=0 && candidate.tile<width*width) {
            nearby.clear();const int q=candidate.tile%width,r=candidate.tile/width;
            for(int y=std::max(0,(r-7)/block);y<=std::min(columns-1,(r+7)/block);++y)
                for(int x=std::max(0,(q-7)/block);x<=std::min(columns-1,(q+7)/block);++x) {
                    const auto& bucket=buckets[y*columns+x];nearby.insert(nearby.end(),bucket.begin(),bucket.end());
                }
            std::ranges::sort(nearby);
            for(auto i:nearby) add(points[i]);
        } else {
            for(const auto& point:points) add(point);
        }
        gain *= candidate.multiplier;
        if (gain > .05 && (!best || gain > best->gain)) best = BotSupplyChoice{gain,candidate.tile};
    }
    return best;
}

}
