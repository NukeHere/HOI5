#pragma once

#include "starting_infrastructure.hpp"
#include <set>
#include <deque>
#include <map>
#include <string>
#include <functional>
#include <chrono>

namespace hoi5 {

inline std::string politicalDate(int day) {
    using namespace std::chrono;
    const year_month_day date{sys_days{year{2000}/1/1}+days{day}};
    const auto padded = [](unsigned value) { return (value < 10 ? "0" : "")+std::to_string(value); };
    return std::to_string(int(date.year()))+"-"+padded(unsigned(date.month()))+"-"+padded(unsigned(date.day()));
}

enum class ForeignAction { mission, embargo, trade, alliance, nonaggression, transit,
    revokeTransit, justify, cancelJustification, peace, war, breakTreaties, aid, loan };

struct ForeignActionInfo {
    ForeignAction action;
    std::string_view label;
    double money, capital, opinion, trust;
    int cooldown;
    std::string_view description;
};

inline constexpr ForeignActionInfo foreignActions[] = {
    {ForeignAction::mission,"Дипломатическая миссия",1e6,1,8,.04,30,"Переговоры об улучшении отношений."},
    {ForeignAction::embargo,"Ввести / снять эмбарго",0,3,-10,0,7,"Блокирует прямые сделки в обоих направлениях; внешние рынки сохраняются."},
    {ForeignAction::trade,"Предложить торговый договор",0,0,0,0,7,"Договор даёт приоритет сопоставления заявок."},
    {ForeignAction::alliance,"Предложить союз",0,3,0,0,7,"Запрет взаимных атак и приоритет торговли; без автоматического вступления в войны."},
    {ForeignAction::nonaggression,"Предложить пакт о ненападении",0,2,0,0,7,"Обе стороны обязуются не объявлять войну, пока пакт действует."},
    {ForeignAction::transit,"Запросить проход войск",0,1,0,0,7,"Разрешает проход через территорию другой страны без смены владельца."},
    {ForeignAction::revokeTransit,"Отозвать проход войск",0,0,0,0,7,"Отзывает выданное другой стране разрешение на проход."},
    {ForeignAction::justify,"Подготовить цель войны",2e6,15,-10,-.02,30,"Начинает 30-дневное обоснование войны; требует политической поддержки."},
    {ForeignAction::cancelJustification,"Отменить подготовку войны",0,0,0,0,7,"Снижает дипломатическую напряжённость; потраченные ресурсы не возвращаются."},
    {ForeignAction::peace,"Предложить мир",0,0,0,0,7,"Прекращение войны по текущим границам с временным запретом новой войны."},
    {ForeignAction::war,"Объявить войну",0,20,-60,0,30,"Требует подготовленной цели войны, поддержки общества и политического капитала."},
    {ForeignAction::breakTreaties,"Расторгнуть договоры",0,8,-20,-.2,7,"Прекращает союз и торговый договор; срок перемирия сохраняется."},
};
inline constexpr ForeignActionInfo foreignAid{ForeignAction::aid,"Безвозмездная помощь",0,0,5,0,30,
    "Выбранная сумма перечисляется сразу, без возврата."};
inline constexpr ForeignActionInfo foreignLoan{ForeignAction::loan,"Предложить кредит",0,0,0,0,30,
    "Деньги перечисляются после согласия; условия фиксируются при отправке предложения."};

struct CountryPolitics {
    static constexpr std::array baselineSocialShares{.45,.25,.28,.02};
    double capital = 50, support = .61, legitimacy = .61, stability = .72, warSupport = .50;
    double reliability = .5, reputation = .5;
    bool externalAccess = true;
    double exportLimit = 1;
    std::array<int,3> taxes{}, taxReady{};
    std::array<double,11> groups{.61,.61,.61,.61,.61,.61,.61,.61,.61,.61,.61};
    std::array<double,4> socialShares = baselineSocialShares, factionShares{.25,.25,.25,.25};
    std::array<double,4> factionPatience{.7,.7,.7,.7}, factionRadicalization{};
    std::array<double,11> programHours{}, programFunded{}, programFunding{};
    double food = 1, goods = 1, foodPrice = 1, goodsPrice = 1, supply = 1;

    void refreshSupport() {
        double social = 0., factions = 0.;
        for (int i = 0; i < 4; ++i) {
            social += groups[3+i]*socialShares[i];
            factions += groups[7+i]*factionShares[i];
        }
        support = (.50*groups[0]+.30*social+.20*factions)*.85 + groups[1]*.12 + groups[2]*.03;
    }
    std::map<std::pair<ForeignAction,int>,int> cooldowns;

    bool warReadiness() const {
        return support >= .45 && legitimacy >= .45 && warSupport >= .35 && capital >= 20 &&
            std::max(factionRadicalization[1],factionRadicalization[2]) < .7;
    }

    double programSupportEffect(int group,double population,double monthlyCost,double funding = 1.) const {
        const double relativeSize = group < 3 ? 1. : group < 7 ? socialShares[group-3]/baselineSocialShares[group-3] :
            factionShares[group-7]/.25;
        const double need = std::max(1e6,population*.1*relativeSize);
        const double intensity = std::min(1.,monthlyCost/need);
        return .04*intensity*funding*(.5+.5*std::clamp(legitimacy,0.,1.))*std::clamp(supply,0.,1.);
    }

    double supportTarget(int group,double budget,int wars,double ownEffect,double populationEffect) const {
        double target = .61-taxes[group < 3 ? group : 0]*.04+ownEffect;
        if (group >= 3) target += populationEffect*.5;
        if (budget < 0) target -= .12;
        if ((group == 1 || group == 2) && exportLimit < 1) target -= .03;
        const double shortage = std::max(0.,1-std::min(food,goods));
        const double pressure = std::max(0.,foodPrice-1)*.60 + std::max(0.,goodsPrice-1)*.40;
        const double exposure = group == 0 || group == 3 || group == 4 || group == 8 ? 1. : .5;
        target -= exposure*(.18*shortage+.025*std::min(2.,pressure));
        if (group == 7) target += .025*std::min(2,wars);
        if (group == 0 || group == 3 || group == 8 || group == 9)
            target -= .02*std::min(2,wars)*(1-std::clamp(warSupport,0.,1.));
        return std::clamp(target,0.,1.);
    }

    std::array<bool,4> factionDemands(bool war,double budget) const {
        return {war || warSupport >= .5, programHours[0] != 0 || programHours[3] != 0 ||
            programHours[8] != 0 || taxes[0] < 0, externalAccess && !war, budget >= 0 && legitimacy >= .5};
    }

    void advanceFactions(bool war,double budget) {
        const auto met = factionDemands(war,budget);
        for (int faction = 0; faction < int(met.size()); ++faction) {
            const double wartime = war ? (faction == 0 ? .05 : faction < 3 ? -.08 : 0.) : 0.;
            const double target = std::clamp(.7+1.5*(groups[7+faction]-.61)+wartime+(met[faction] ? .08 : -.35),0.,1.);
            auto& patience = factionPatience[faction];
            patience = std::clamp(patience+(target-patience)/90.,0.,1.);
            auto& radical = factionRadicalization[faction];
            radical = std::clamp(radical+std::max(0.,.4-patience)*.005-std::max(0.,patience-.55)*.001,0.,1.);
        }
    }
};

struct Relation {
    std::map<int,double> opinion, grievance, respect, fear;
    double trust = .5, crisis{};
    bool war{};
    int truceUntil{}, warStarted{};
    std::set<ForeignAction> treaties;
    std::set<int> embargoes, transitGrantors;
};

struct ForeignOffer { int actor, target, due; ForeignAction action; double amount{}; };
struct GovernmentLoan {
    int lender, borrower;
    double original, principal;
    int nextDue;
    double principalDue{}, interestDue{};
    double annualRate = .05;
    int termMonths = 12, paymentsDue = 0;
};

inline std::pair<std::string_view,std::string_view> offerNames(ForeignAction action) {
    using A = ForeignAction;
    switch (action) {
        case A::trade: return {"trade","торговый договор"};
        case A::alliance: return {"alliance","союз"};
        case A::nonaggression: return {"nonaggression","пакт о ненападении"};
        case A::transit: return {"transit","разрешение на проход войск"};
        case A::peace: return {"peace","мирный договор"};
        case A::loan: return {"loan","кредит"};
        default: return {};
    }
}

struct Diplomacy {
    static constexpr double monthlySupportCost = 1000000.;
    std::vector<CountryPolitics> countries;
    std::map<std::pair<int,int>,Relation> relations;
    std::map<std::pair<int,int>,int> goals;
    std::vector<ForeignOffer> offers;
    std::vector<GovernmentLoan> loans;
    struct HistoryEntry { int day, actor, target; std::string message; };
    std::deque<HistoryEntry> history;
    int day{};
    std::uint64_t revision{};
    std::array<int,2> marketCooldown{};

    std::string_view changeTax(int country,int group,int delta) {
        auto& state = countries[country];
        if (state.taxReady[group] > day) return "Ставку пока нельзя изменить";
        if (state.capital < 2) return "Недостаточно политического капитала";
        const int next = state.taxes[group]+delta;
        if (next < -2 || next > 2) return "Достигнут предел ставки";
        state.capital -= 2;
        state.taxes[group] = next;
        state.taxReady[group] = day+30;
        record("Изменена налоговая ставка",country);
        return {};
    }

    std::string_view changeMarketPolicy(bool external,double exportPercent = 100.) {
        auto& state = countries[0];
        if (!external) {
            if (!std::isfinite(exportPercent) || exportPercent < 0. || exportPercent > 100.)
                return "Выберите лимит экспорта от 0 до 100%";
            if (std::abs(state.exportLimit*100.-exportPercent) < 1e-6) return "Лимит не изменён";
        }
        auto& ready = marketCooldown[external];
        if (ready > day) return "Действие на перезарядке";
        if (state.capital < 2) return "Недостаточно политического капитала";
        state.capital -= 2;
        ready = day+7;
        if (external) state.externalAccess = !state.externalAccess;
        else state.exportLimit = exportPercent/100.;
        return {};
    }

    std::string_view changeProgram(int country,int group,double hours,const StartingProfile& profile) {
        auto& state = countries[country];
        if (state.programHours[group] != 0) {
            state.programHours[group] = 0;
            state.programFunded[group] = 0;
            state.programFunding[group] = 0;
            record("Программа поддержки завершена",country);
            return {};
        }
        if (state.capital < 2 || profile.budget < monthlySupportCost) return "Недостаточно средств или политического капитала";
        state.capital -= 2;
        state.programHours[group] = hours;
        state.programFunding[group] = 1.;
        record("Начата программа поддержки",country);
        return {};
    }

    double programExpenses(int country) const {
        return monthlySupportCost*std::ranges::count_if(countries[country].programHours,
            [](double hours) { return hours != 0.; });
    }

    std::vector<std::pair<int,int>> fundPrograms(int hours,std::vector<StartingProfile>& profiles) {
        std::vector<std::pair<int,int>> expired;
        for (std::size_t i = 0; i < countries.size(); ++i) {
            auto& state = countries[i];
            std::array<double,11> active{};
            double required = 0;
            for (std::size_t g = 0; g < active.size(); ++g) {
                const double remaining = state.programHours[g];
                active[g] = remaining < 0 ? hours : std::min(double(hours),remaining);
                required += active[g]*monthlySupportCost/720.;
            }
            if (required <= 0) continue;
            const double paid = std::min(required,std::max(0.,profiles[i].budget));
            profiles[i].budget -= paid;
            const double ratio = paid/required;
            for (std::size_t g = 0; g < active.size(); ++g) {
                if (active[g] > 0) state.programFunding[g] = ratio;
                state.programFunded[g] += active[g]*ratio;
                if (state.programHours[g] > 0) {
                    state.programHours[g] -= active[g];
                    if (state.programHours[g] <= 0) expired.emplace_back(int(i),int(g));
                }
            }
        }
        return expired;
    }

    Relation& relation(int a,int b) { return relations[{std::min(a,b),std::max(a,b)}]; }
    const Relation& relation(int a,int b) const {
        static const Relation empty;
        const auto found = relations.find({std::min(a,b),std::max(a,b)});
        return found == relations.end() ? empty : found->second;
    }
    bool hostile(int a,int b) const { return a != b && relation(a,b).war; }
    bool allied(int a,int b) const {
        return a != b && !hostile(a,b) && relation(a,b).treaties.contains(ForeignAction::alliance);
    }
    bool canTransit(int guest,int owner) const {
        const auto& r = relation(guest,owner);
        return guest == owner || (!r.war && (r.treaties.contains(ForeignAction::alliance) || r.transitGrantors.contains(owner)));
    }
    bool tradeAllowed(int a,int b) const { return a != b && !hostile(a,b) && relation(a,b).embargoes.empty(); }
    double ideologyDistance(int a,int b) const {
        const auto factions = [&](int country) {
            std::array<double,4> weights{};
            double sum = 0.;
            const auto& state = countries[country];
            for (int i = 0; i < 4; ++i) {
                weights[i] = state.groups[7+i]*state.factionShares[i];
                sum += weights[i];
            }
            if (sum > 0.) for (auto& weight : weights) weight /= sum;
            return weights;
        };
        const auto first = factions(a), second = factions(b);
        double distance = 0.;
        for (int i = 0; i < 4; ++i) distance += std::abs(first[i]-second[i]);
        return distance/2;
    }
    int tradePriority(int a,int b) const {
        const auto& treaties = relation(a,b).treaties;
        return 2*treaties.contains(ForeignAction::alliance)+treaties.contains(ForeignAction::trade);
    }

    std::string reason(int actor,int target,const ForeignActionInfo& info,
                       const std::vector<StartingProfile>& profiles,double amount = 0.) const {
        using A = ForeignAction;
        if (actor == target || actor < 0 || target < 0 ||
            actor >= int(countries.size()) || target >= int(countries.size())) return "Недоступная страна";
        const auto action = info.action;
        const auto& state = countries[actor];
        const auto& r = relation(actor,target);
        const auto key = std::pair{actor,target};
        const bool financial = action == A::aid || action == A::loan;
        if (financial && (!std::isfinite(amount) || amount < 1000. || amount > 1e12))
            return "Введите сумму от 1 тыс. до 1 трлн";
        if (financial && profiles[actor].budget < amount) return "Недостаточно средств для выбранной суммы";
        const bool offer = !offerNames(action).first.empty();
        if (const auto cooldown = state.cooldowns.find({action,target});
            cooldown != state.cooldowns.end() && cooldown->second > day) return "Доступно с "+politicalDate(cooldown->second);
        if (info.money > 0 && profiles[actor].budget < info.money) return "Недостаточно средств";
        if (state.capital < info.capital)
            return "Недостаточно политического капитала (нужно "+std::to_string(int(info.capital))+")";
        if (r.war && (action == A::mission || action == A::aid || action == A::justify || (offer && action != A::peace))) return "Сначала заключите мир";
        if (offer) {
            if (r.treaties.contains(action)) return "Договор уже действует";
            if (action == A::transit && canTransit(actor,target)) return "Проход уже разрешён";
            if (std::any_of(offers.begin(),offers.end(),[&](const auto& o) {
                return o.action == action && ((o.actor == actor && o.target == target) || (o.actor == target && o.target == actor));
            })) return "Предложение ожидает ответа";
            if (action == A::peace && !r.war) return "Войны нет";
            if ((action == A::trade || action == A::alliance || action == A::transit) && !r.embargoes.empty())
                return "Сначала снимите эмбарго";
        }
        if (action == A::war || action == A::justify) {
            if (r.war || r.treaties.contains(A::alliance) || r.treaties.contains(A::nonaggression) || day < r.truceUntil)
                return "Война уже идёт, действует пакт, союз или перемирие";
        }
        if (action == A::justify) {
            if (goals.contains(key)) return "Цель войны уже готовится или подготовлена";
            if (state.support < .45 || state.legitimacy < .45) return "Недостаточно поддержки власти или легитимности";
        }
        if (action == A::cancelJustification && !goals.contains(key)) return "Нет подготовки войны против этой страны";
        if (action == A::war) {
            const auto goal = goals.find(key);
            if (goal == goals.end()) return "Сначала подготовьте цель войны";
            if (day < goal->second) return "Цель войны будет готова "+politicalDate(goal->second);
            if (day > goal->second+180) return "Срок подготовленной цели войны истёк";
            if (!state.warReadiness())
                return "Нужно 45% поддержки, 45% легитимности, 35% поддержки войны, 20 политического капитала и отсутствие сильного сопротивления фракций";
        }
        if (action == A::revokeTransit && !r.transitGrantors.contains(actor))
            return "Вы не выдавали этой стране разрешение на проход";
        if (action == A::breakTreaties && r.treaties.empty()) return "Нет действующих договоров";
        return {};
    }

    std::string act(int actor,int target,const ForeignActionInfo& info,std::vector<StartingProfile>& profiles,
                    double amount = 0.) {
        if (const auto error = reason(actor,target,info,profiles,amount); !error.empty()) return error;
        using A = ForeignAction;
        const auto action = info.action;
        auto& state = countries[actor];
        auto& r = relation(actor,target);
        const auto key = std::pair{actor,target};
        const auto opposite = std::pair{target,actor};
        const bool offer = !offerNames(action).first.empty();
        profiles[actor].budget -= action == A::aid ? amount : info.money;
        state.capital -= info.capital;
        state.cooldowns[{action,target}] = day + info.cooldown;
        if (offer) offers.push_back({actor,target,day+3,action,amount});
        else {
            double opinion = info.opinion;
            if (action == A::aid) profiles[target].budget += amount;
            if (action == A::embargo) {
                if (r.embargoes.erase(actor)) opinion = 0;
                else {
                    r.embargoes.insert(actor);
                    r.grievance[target] = std::min(100.,r.grievance[target]+10);
                }
            } else if (action == A::mission) {
                r.respect[target] = std::min(100.,r.respect[target]+2);
                r.grievance[target] = std::max(0.,r.grievance[target]-2);
            } else if (action == A::justify) {
                goals[key] = day+30;
                r.crisis = std::max(r.crisis,25.);
                r.grievance[target] = std::min(100.,r.grievance[target]+10);
            } else if (action == A::cancelJustification) {
                goals.erase(key);
                r.crisis = goals.contains(opposite) ? 25 : 0;
            } else if (action == A::revokeTransit) r.transitGrantors.erase(actor);
            else if (action == A::war) {
                state.factionPatience[0] = std::min(1.,state.factionPatience[0]+.04);
                for (int faction : {1,2}) state.factionPatience[faction] = std::max(0.,state.factionPatience[faction]-.06);
                state.reputation = std::max(0.,state.reputation-.05);
                state.reliability = std::max(0.,state.reliability-.02);
                goals.erase(key);
                goals.erase(opposite);
                r.war = true;
                r.warStarted = day;
                r.crisis = 100;
                r.trust = 0;
                r.treaties.clear();
                r.transitGrantors.clear();
                r.grievance[target] = std::min(100.,r.grievance[target]+50);
                r.fear[target] = std::min(100.,r.fear[target]+20);
            } else if (action == A::breakTreaties) {
                r.treaties.clear();
                r.transitGrantors.clear();
                state.reliability = std::max(0.,state.reliability-.04);
            }
            r.trust = std::clamp(r.trust+info.trust,0.,1.);
            r.opinion[target] = std::clamp(r.opinion[target]+opinion,-100.,100.);
        }
        record(std::string(info.label),actor,target);
        return {};
    }

    void record(std::string message,int actor,int target = -1) {
        ++revision;
        history.push_front({day,actor,target,std::move(message)});
        if (history.size() > 40) history.pop_back();
    }

    void advance(int currentDay,std::vector<StartingProfile>& profiles,
                 const std::function<void(const ForeignOffer&,bool)>& onResponse = {}) {
        using A = ForeignAction;
        if (currentDay <= day) return;
        day = currentDay;
        for (int i = 0; i < int(countries.size()); ++i) {
            auto& state = countries[i];
            const int wars = int(std::count_if(relations.begin(),relations.end(),[&](const auto& pair) {
                return pair.second.war && (pair.first.first == i || pair.first.second == i);
            }));
            const bool war = wars > 0;
            const double shortage = std::max(0.,1-std::min(state.food,state.goods));
            for (std::size_t g = 0; g < state.programFunding.size(); ++g)
                state.programFunding[g] = std::min(1.,state.programFunded[g]/24);
            const auto effect = [&](int group) {
                return state.programSupportEffect(group,profiles[i].population,monthlySupportCost,state.programFunding[group]);
            };
            for (int g = 0; g < int(state.groups.size()); ++g) {
                const double target = state.supportTarget(g,profiles[i].budget,wars,effect(g),effect(0));
                auto& current = state.groups[g];
                current += std::clamp((target-current)*(-std::expm1(-1./180)),-.0005,.0005);
            }
            state.programFunded.fill(0);
            state.refreshSupport();
            const double supportGap = state.support-.61;
            const auto approach = [](double current,double target,int days) {
                return std::clamp(current+std::clamp((std::clamp(target,0.,1.)-current)/days,-.0015,.0015),0.,1.);
            };
            const double recovery = std::clamp((.5-state.warSupport)/180,-.0002,.0002);
            state.warSupport = std::clamp(state.warSupport+(war ? -.0002 : recovery),0.,1.);
            if (!war && state.reputation < .5) state.reputation = std::min(.5,state.reputation+.00005);
            state.capital = std::clamp(state.capital+.05*(state.support+state.legitimacy)/1.22-(war ? .04 : 0.),0.,100.);
            state.advanceFactions(war,profiles[i].budget);
            state.stability = approach(state.stability,.72+.70*supportGap-.25*shortage,90);
            state.legitimacy = approach(state.legitimacy,.61+.40*supportGap-.10*shortage,180);
        }
        for (auto& [pair, relation] : relations) {
            for (auto& [country, amount] : relation.grievance) amount = std::max(0.,amount-.02);
            for (auto& [country, amount] : relation.fear) amount = std::max(0.,amount-.01);
            if (!relation.war && relation.crisis > 0) relation.crisis = std::min(60.,relation.crisis+.5);
        }
        std::erase_if(goals,[&](const auto& goal) {
            if (day == goal.second) record("Цель войны подготовлена",goal.first.first,goal.first.second);
            if (day <= goal.second+180) return false;
            if (!goals.contains({goal.first.second,goal.first.first})) relation(goal.first.first,goal.first.second).crisis = 0;
            record("Срок цели войны истёк",goal.first.first,goal.first.second);
            return true;
        });
        std::erase_if(offers,[&](const ForeignOffer& offer) {
            if (offer.due > day || offer.target == 0) return false;
            auto& r = relation(offer.actor,offer.target);
            const int target = offer.target;
            const double threshold = (offer.action == A::alliance ? 30 : offer.action == A::transit ? 0 : -10)
                + r.grievance[target]*.3 - r.respect[target]*.2 + r.crisis*.2;
            const bool accept = offer.action == A::peace
                ? profiles[target].budget < 0 || r.opinion[target] >= -20 ||
                    (day-r.warStarted >= 90 && countries[target].warSupport < .5)
                : r.opinion[target] >= threshold && r.trust >= .35 &&
                    ((offer.action != A::alliance && offer.action != A::nonaggression && offer.action != A::transit)
                     || (countries[offer.actor].reliability >= .25 && countries[offer.actor].reputation >= .2
                         && r.grievance[target] <= 40));
            const bool accepted = resolve(offer,accept,profiles);
            if (onResponse) onResponse(offer,accepted);
            return true;
        });
    }

    bool resolve(const ForeignOffer& offer,bool accepted,std::vector<StartingProfile>& profiles) {
        using A = ForeignAction;
        auto& r = relation(offer.actor,offer.target);
        const auto action = offer.action;
        accepted = accepted && (action == A::peace ? r.war : !r.war && (action == A::loan || r.embargoes.empty()));
        if (action == A::loan)
            accepted = accepted && offer.amount > 0 && profiles[offer.actor].budget >= offer.amount;
        if (!accepted) {
            record("Предложение отклонено",offer.actor,offer.target);
            return false;
        }
        if (action == A::loan) {
            profiles[offer.actor].budget -= offer.amount;
            profiles[offer.target].budget += offer.amount;
            loans.push_back({offer.actor,offer.target,offer.amount,offer.amount,day+30});
        } else if (action == A::transit) r.transitGrantors.insert(offer.target);
        else r.treaties.insert(action);
        if (action == A::trade || action == A::alliance || action == A::nonaggression || action == A::transit)
            for (int country : {offer.actor,offer.target}) countries[country].reliability = std::min(1.,countries[country].reliability+.01);
        if (action == A::peace || action == A::alliance || action == A::nonaggression) {
            goals.erase({offer.actor,offer.target});
            goals.erase({offer.target,offer.actor});
            r.crisis = 0;
        }
        if (action == A::peace) {
            r.war = false;
            r.truceUntil = day+30;
        }
        record("Соглашение принято",offer.actor,offer.target);
        return true;
    }

    std::pair<double,double> monthlyDebtFlows(int country) const {
        double incoming = 0., outgoing = 0.;
        for (const auto& loan : loans) {
            const double payment = std::min(loan.principal,loan.original/loan.termMonths)+loan.principal*loan.annualRate/12.;
            if (loan.lender == country) incoming += payment;
            if (loan.borrower == country) outgoing += payment;
        }
        return {incoming,outgoing};
    }

    void serviceLoans(int current,std::vector<StartingProfile>& profiles,
                      const std::function<void(const GovernmentLoan&,bool,bool)>& report) {
        for (auto it = loans.begin(); it != loans.end();) {
            auto& loan = *it;
            if (current >= loan.nextDue) {
                loan.interestDue += loan.principal*loan.annualRate/12.;
                loan.principalDue = std::min(loan.principal,loan.principalDue+loan.original/loan.termMonths);
                loan.nextDue += 30;
                ++loan.paymentsDue;
                record("Платёж по кредиту: "+std::to_string(std::llround(loan.principalDue+loan.interestDue)),
                    loan.borrower,loan.lender);
            }
            auto& borrower = profiles[loan.borrower].budget;
            const double payment = std::min(std::max(0.,borrower),loan.principalDue+loan.interestDue);
            borrower -= payment;
            profiles[loan.lender].budget += payment;
            const double interest = std::min(payment,loan.interestDue);
            loan.interestDue -= interest;
            loan.principal -= payment-interest;
            loan.principalDue = std::max(0.,loan.principalDue-(payment-interest));
            const bool repaid = loan.principal <= 1e-6 && loan.interestDue <= 1e-6;
            const bool arrears = std::ranges::any_of(loans,[&](const auto& other) {
                return other.lender == loan.lender && other.borrower == loan.borrower &&
                    other.principalDue+other.interestDue > 1e-6;
            });
            report(loan,arrears,repaid);
            if (repaid) it = loans.erase(it);
            else ++it;
        }
    }
};

}
