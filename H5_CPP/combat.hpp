#pragma once

#include <algorithm>
#include <array>
#include <vector>

namespace hoi5 {

struct CombatStats {
    double strength = 100, width = 20, initiative = .03;
    double softAttack = 18, frontAttack = 3, topAttack = 1;
    double defense = 26, breakthrough = 8;
    double frontPiercing = 4, topPiercing = 1, frontArmor = 2, topArmor = 1;
    double infantry = .92, vehicles = .08;
    double widthEfficiency = 1;
    bool recovering{};
};

struct Battle {
    int attacker, defender;
    double advance{};
    std::vector<int> attackers, defenders;
    std::vector<int> activeAttackers, activeDefenders;
};

inline double combatDamage(const CombatStats& attacker, const CombatStats& target, bool defending, std::array<double,3> ammo = {1,1,1}, double supply = 1, double fort = 0, double airBonus = 0) {
    const double defense = (defending ? target.defense*(1+fort) : target.breakthrough*(1+airBonus))
        * std::max(.2,target.widthEfficiency);
    const auto damage = [&](double attack) {
        attack *= std::max(.2,attacker.widthEfficiency)*(.90+.10*supply);
        return attack*.10+std::max(0.,attack-defense)*.40;
    };
    const double front = damage(attacker.frontAttack*ammo[1])*(attacker.frontPiercing >= target.frontArmor ? 1. : .10);
    const double top = damage(attacker.topAttack*ammo[2])*(attacker.topPiercing >= target.topArmor ? 1. : .10);
    const double infantry = std::clamp(target.infantry,0.,1.);
    const double vehicles = std::clamp(target.vehicles,0.,1.);
    const double combined = (damage(attacker.softAttack*ammo[0])*infantry+(front+top)*vehicles)/std::max(.01,infantry+vehicles);
    const bool unpierced = target.frontPiercing < attacker.frontArmor &&
        target.topPiercing < attacker.topArmor && attacker.vehicles > .25;
    return combined * (unpierced ? 1.40 : 1.);
}

}
