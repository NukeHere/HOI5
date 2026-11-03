#pragma once

#include "starting_infrastructure.hpp"
#include <set>
#include <deque>
#include <map>
#include <string>

namespace hoi5 {

enum class ForeignAction { mission, embargo, trade, alliance, nonaggression, transit,
    revokeTransit, justify, cancelJustification, peace, war, breakTreaties };

struct ForeignActionInfo {
    ForeignAction action;
    std::string_view label;
    double money, capital, opinion, trust;
    int cooldown;
};

inline constexpr ForeignActionInfo foreignActions[] = {
    {ForeignAction::mission,"Дипломатическая миссия",1e6,1,8,.04,30},
    {ForeignAction::embargo,"Ввести / снять эмбарго",0,3,-10,0,7},
    {ForeignAction::trade,"Торговый договор",0,0,0,0,7},
    {ForeignAction::alliance,"Союз",0,3,0,0,7},
    {ForeignAction::nonaggression,"Пакт о ненападении",0,2,0,0,7},
    {ForeignAction::transit,"Запросить проход войск",0,1,0,0,7},
    {ForeignAction::revokeTransit,"Отозвать разрешение на проход",0,0,0,0,7},
    {ForeignAction::justify,"Подготовить цель войны",2e6,15,-10,-.02,30},
    {ForeignAction::cancelJustification,"Отменить подготовку войны",0,0,0,0,7},
    {ForeignAction::peace,"Предложить мир",0,0,0,0,7},
    {ForeignAction::war,"Объявить войну",0,20,-60,0,30},
    {ForeignAction::breakTreaties,"Расторгнуть договоры",0,8,-20,-.2,7},
};

struct CountryPolitics {
    double capital = 50, support = .61, legitimacy = .61, stability = .72, warSupport = .50;
    double reliability = .5, reputation = .5;
    bool externalAccess = true;
    double exportLimit = 1;
    std::array<int,3> taxes{}, taxReady{};
    std::array<double,11> groups{.61,.61,.61,.61,.61,.61,.61,.61,.61,.61,.61};
    std::array<double,11> programHours{}, programFunded{};
    double food = 1, goods = 1, foodPrice = 1, goodsPrice = 1, supply = 1;

    void refreshSupport() {
        const double social = groups[3]*.45 + groups[4]*.25 + groups[5]*.28 + groups[6]*.02;
        const double factions = (groups[7]+groups[8]+groups[9]+groups[10])*.25;
        support = (.50*groups[0]+.30*social+.20*factions)*.85 + groups[1]*.12 + groups[2]*.03;
    }
    std::map<std::pair<ForeignAction,int>,int> cooldowns;
};

struct Relation {
    std::map<int,double> opinion, grievance, respect, fear;
    double trust = .5, crisis{};
    bool war{};
    int truceUntil{}, warStarted{};
    std::set<ForeignAction> treaties;
    std::set<int> embargoes, transitGrantors;
};

struct ForeignOffer { int actor, target, due; ForeignAction action; };

struct Diplomacy {
    std::vector<CountryPolitics> countries;
    std::map<std::pair<int,int>,Relation> relations;
    std::map<std::pair<int,int>,int> goals;
    std::vector<ForeignOffer> offers;
    std::deque<std::string> history;
    int day{};
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
        record("Изменена налоговая ставка");
        return {};
    }

    std::string_view changeMarketPolicy(bool external) {
        auto& state = countries[0];
        auto& ready = marketCooldown[external];
        if (ready > day) return "Действие на перезарядке";
        if (state.capital < 2) return "Недостаточно политического капитала";
        state.capital -= 2;
        ready = day+7;
        if (external) state.externalAccess = !state.externalAccess;
        else state.exportLimit = state.exportLimit < 1 ? 1. : .5;
        return {};
    }

    std::string_view changeProgram(int country,int group,double hours,const StartingProfile& profile) {
        auto& state = countries[country];
        if (state.programHours[group] != 0) {
            state.programHours[group] = 0;
            state.programFunded[group] = 0;
            record("Программа поддержки завершена");
            return {};
        }
        if (state.capital < 2 || profile.budget < 1000000) return "Недостаточно средств или политического капитала";
        state.capital -= 2;
        state.programHours[group] = hours;
        record("Начата программа поддержки");
        return {};
    }

    void fundPrograms(int hours,std::vector<StartingProfile>& profiles) {
        for (std::size_t i = 0; i < countries.size(); ++i) {
            auto& state = countries[i];
            std::array<double,11> active{};
            double required = 0;
            for (std::size_t g = 0; g < active.size(); ++g) {
                const double remaining = state.programHours[g];
                active[g] = remaining < 0 ? hours : std::min(double(hours),remaining);
                required += active[g]*1000000/720.;
            }
            if (required <= 0) continue;
            const double paid = std::min(required,std::max(0.,profiles[i].budget));
            profiles[i].budget -= paid;
            for (std::size_t g = 0; g < active.size(); ++g) {
                state.programFunded[g] += active[g]*paid/required;
                if (state.programHours[g] > 0) state.programHours[g] -= active[g];
            }
        }
    }

    Relation& relation(int a,int b) { return relations[{std::min(a,b),std::max(a,b)}]; }
    const Relation& relation(int a,int b) const {
        static const Relation empty;
        const auto found = relations.find({std::min(a,b),std::max(a,b)});
        return found == relations.end() ? empty : found->second;
    }
    bool hostile(int a,int b) const { return a != b && relation(a,b).war; }
    bool canTransit(int guest,int owner) const {
        const auto& r = relation(guest,owner);
        return guest == owner || (!r.war && (r.treaties.contains(ForeignAction::alliance) || r.transitGrantors.contains(owner)));
    }
    bool tradeAllowed(int a,int b) const { return a != b && !hostile(a,b) && relation(a,b).embargoes.empty(); }
    int tradePriority(int a,int b) const {
        const auto& treaties = relation(a,b).treaties;
        return 2*treaties.contains(ForeignAction::alliance)+treaties.contains(ForeignAction::trade);
    }

    std::string_view act(int actor,int target,const ForeignActionInfo& info,std::vector<StartingProfile>& profiles) {
        using A = ForeignAction;
        if (actor == target || actor < 0 || target < 0 ||
            actor >= int(countries.size()) || target >= int(countries.size())) return "Недоступная страна";
        const auto action = info.action;
        auto& state = countries[actor];
        auto& r = relation(actor,target);
        const auto key = std::pair{actor,target};
        const auto opposite = std::pair{target,actor};
        const bool offer = action == A::trade || action == A::alliance || action == A::nonaggression
            || action == A::transit || action == A::peace;
        if (state.cooldowns[{action,target}] > day) return "Действие на перезарядке";
        if (profiles[actor].budget < info.money || state.capital < info.capital) return "Недостаточно средств или политического капитала";
        if (r.war && (action == A::mission || action == A::justify || (offer && action != A::peace))) return "Сначала заключите мир";
        if (offer) {
            if (r.treaties.contains(action) || (action == A::transit && canTransit(actor,target))) return "Договор уже действует";
            if (std::any_of(offers.begin(),offers.end(),[&](const auto& o) {
                return o.action == action && ((o.actor == actor && o.target == target) || (o.actor == target && o.target == actor));
            })) return "Предложение ожидает ответа";
            if (action == A::peace && !r.war) return "Войны нет";
            if ((action == A::trade || action == A::alliance || action == A::transit) && !r.embargoes.empty())
                return "Сначала снимите эмбарго";
        }
        if (action == A::war || action == A::justify) {
            if (r.war || r.treaties.contains(A::alliance) || r.treaties.contains(A::nonaggression) || day < r.truceUntil)
                return "Действует война, союз, пакт или перемирие";
            if (state.support < .45 || state.legitimacy < .45) return "Недостаточно поддержки или легитимности";
        }
        if (action == A::justify && goals.contains(key)) return "Цель войны уже готовится";
        if (action == A::cancelJustification && !goals.contains(key)) return "Цель войны отсутствует";
        if (action == A::war && (!goals.contains(key) || day < goals.at(key) || day > goals.at(key)+180 || state.warSupport < .35))
            return "Требуется подготовленная цель и поддержка войны";
        if (action == A::revokeTransit && !r.transitGrantors.contains(actor)) return "Разрешение на проход отсутствует";
        if (action == A::breakTreaties && r.treaties.empty()) return "Нет действующих договоров";
        profiles[actor].budget -= info.money;
        state.capital -= info.capital;
        state.cooldowns[{action,target}] = day + info.cooldown;
        if (offer) offers.push_back({actor,target,day+3,action});
        else {
            double opinion = info.opinion;
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
        record(std::string(info.label));
        return {};
    }

    void record(std::string message) {
        history.push_front(std::move(message));
        if (history.size() > 40) history.pop_back();
    }

    void advance(int currentDay,const std::vector<StartingProfile>& profiles) {
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
            const double pressure = std::max(0.,state.foodPrice-1)*.60 + std::max(0.,state.goodsPrice-1)*.40;
            const auto effect = [&](int group) {
                const double intensity = std::min(1.,1000000/std::max(1000000.,profiles[i].population*.1));
                return .04*intensity*std::min(1.,state.programFunded[group]/24)*(.5+state.legitimacy*.5)*state.supply;
            };
            for (int g = 0; g < int(state.groups.size()); ++g) {
                double target = .61-state.taxes[g < 3 ? g : 0]*.04+effect(g);
                if (g >= 3) target += effect(0)*.5;
                if (profiles[i].budget < 0) target -= .12;
                if ((g == 1 || g == 2) && state.exportLimit < 1) target -= .03;
                const double exposure = g == 0 || g == 3 || g == 4 || g == 8 ? 1. : .5;
                target -= exposure*(.18*shortage+.025*std::min(2.,pressure));
                if (g == 7) target += .025*std::min(2,wars);
                if (g == 0 || g == 3 || g == 8 || g == 9) target -= .02*std::min(2,wars)*(1-state.warSupport);
                auto& current = state.groups[g];
                current += std::clamp((std::clamp(target,0.,1.)-current)*(-std::expm1(-1./180)),-.0005,.0005);
            }
            state.programFunded.fill(0);
            state.refreshSupport();
            const double supportGap = state.support-.61;
            const auto approach = [](double current,double target,int days) {
                return std::clamp(current+std::clamp((std::clamp(target,0.,1.)-current)/days,-.0015,.0015),0.,1.);
            };
            state.stability = approach(state.stability,.72+.70*supportGap-.25*shortage,90);
            state.legitimacy = approach(state.legitimacy,.61+.40*supportGap-.10*shortage,180);
            const double recovery = std::clamp((.5-state.warSupport)/180,-.0002,.0002);
            state.warSupport = std::clamp(state.warSupport+(war ? -.0002 : recovery),0.,1.);
            if (!war && state.reputation < .5) state.reputation = std::min(.5,state.reputation+.00005);
            state.capital = std::clamp(state.capital+.05*(state.support+state.legitimacy)/1.22-(war ? .04 : 0.),0.,100.);
        }
        for (auto& [pair, relation] : relations) {
            for (auto& [country, amount] : relation.grievance) amount = std::max(0.,amount-.02);
            for (auto& [country, amount] : relation.fear) amount = std::max(0.,amount-.01);
            if (!relation.war && relation.crisis > 0) relation.crisis = std::min(60.,relation.crisis+.5);
        }
        std::erase_if(goals,[&](const auto& goal) {
            if (day == goal.second) record("Цель войны подготовлена");
            if (day <= goal.second+180) return false;
            if (!goals.contains({goal.first.second,goal.first.first})) relation(goal.first.first,goal.first.second).crisis = 0;
            record("Срок цели войны истёк");
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
            resolve(offer,accept);
            return true;
        });
    }

    void resolve(const ForeignOffer& offer,bool accepted) {
        using A = ForeignAction;
        auto& r = relation(offer.actor,offer.target);
        const auto action = offer.action;
        accepted = accepted && (action == A::peace ? r.war : !r.war && r.embargoes.empty());
        if (!accepted) {
            record("Предложение отклонено");
            return;
        }
        if (action == A::transit) r.transitGrantors.insert(offer.target);
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
        record("Соглашение принято");
    }
};

}
