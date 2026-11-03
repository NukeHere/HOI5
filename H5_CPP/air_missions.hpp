#pragma once

#include "munition_data.hpp"

namespace hoi5 {

struct AirSalvo {
    int owner, origin, target, current, count;
    const Munition* weapon;
    double distance, remaining, interceptability;
    bool strategic;
};

inline int airHexDistance(int a,int b,int size) {
    const int dq = a%size-b%size, dr = a/size-b/size;
    return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
}

inline int airTileBetween(int a,int b,int size,double progress) {
    const double q = std::lerp(double(a%size),double(b%size),progress);
    const double r = std::lerp(double(a/size),double(b/size),progress);
    const double s = -q-r;
    int rq = int(std::nearbyint(q)), rr = int(std::nearbyint(r)), rs = int(std::nearbyint(s));
    const double dq = std::abs(rq-q), dr = std::abs(rr-r), ds = std::abs(rs-s);
    if (dq > dr && dq > ds) rq = -rr-rs;
    else if (dr > ds) rr = -rq-rs;
    if (rq < 0 || rq >= size || rr < 0 || rr >= size) return b;
    return rr*size+rq;
}

inline const Munition* missionWeapon(int type,bool strategic) {
    const auto& allowed = aircraftMunitions[type];
    if (allowed.empty()) return nullptr;
    const auto preferences = strategic
        ? std::vector<std::string_view>{"tactical_cruise_missile","small_ballistic_missile","heavy_strategic_missile",
            "glide_bomb","guided_bomb","bunker_buster","light_guided_missile"}
        : std::vector<std::string_view>{"light_guided_missile","unguided_rockets","guided_bomb","glide_bomb"};
    auto key = allowed.front();
    for (auto candidate : preferences)
        if (std::find(allowed.begin(),allowed.end(),candidate) != allowed.end()) {
            key = candidate;
            break;
        }
    const auto found = std::find_if(std::begin(munitions),std::end(munitions),[&](const auto& m) { return m.key == key; });
    return found == std::end(munitions) ? nullptr : found;
}

inline double weaponInterceptability(const Munition& weapon,double distance) {
    const double t = std::clamp(distance/std::max(.001,weapon.maxRange),0.,1.);
    const auto profile = weapon.profile;
    const double factor = profile == "sqrt" ? std::sqrt(t) : profile == "square" ? t*t :
        profile == "glide" ? .18+std::sqrt(t)*.92 : profile == "rocket_boost_then_glide" ? .12+t*.55+t*t*.35 :
        profile == "sustained_motor" ? t*.72 : profile == "two_stage" ? t*.58+std::max(0.,t-.70)*.35 :
        profile == "ballistic" ? .20+t*.42 : t;
    return std::clamp(std::lerp(weapon.low,weapon.high,std::clamp(factor,0.,1.)),0.,1.);
}

inline int munitionsPerSortie(const Munition& weapon) {
    if (weapon.type == "unguided_rocket") return 8;
    if (weapon.type == "guided_missile" || weapon.type == "guided_bomb" || weapon.type == "glide_bomb") return 2;
    return 1;
}

inline double buildingDamage(const AirSalvo& salvo,Building building,double collateral) {
    const auto& weapon = *salvo.weapon;
    double penetration = .72+std::min(1.5,weapon.penetration)*.34;
    if (weapon.type == "bunker_buster" && (building == airbase || building == supplyDepot || building == warehouse))
        penetration *= 1.35;
    const double damage = weapon.warhead*salvo.count*weapon.accuracy*.012*weapon.damageMult*penetration
        /std::max(.25,buildingHardness[building])*collateral;
    const double limit = (weapon.type == "heavy_strategic_missile" ? weapon.damageCap : std::min(.32,weapon.damageCap))
        * std::max(.05,std::pow(collateral,.55));
    return std::clamp(damage,0.,limit);
}

}
