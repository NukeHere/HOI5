#pragma once

#include "munition_data.hpp"
#include "air_data.hpp"
#include <optional>

namespace hoi5 {

struct InboundInterceptor {
    int owner,count;
    double chance,remaining;
};

struct AircraftInterceptorSalvo {
    int targetWing,sorties;
    InboundInterceptor attack;
    int targetAircraft = -1;
    int exposure = -1;
};

struct AirSalvo {
    int owner, origin, target, current, count;
    const Munition* weapon;
    double distance, remaining, interceptability;
    bool strategic;
    int sourceWing = -1;
    std::string_view targetObject;
    std::vector<InboundInterceptor> inbound;
    bool terminalReactionSpent = false;
    int sourceAircraft = -1;
};

inline double emergencyGuidanceLoss(std::string_view type) {
    if (type == "guided_missile") return .25;
    if (type == "guided_bomb") return .55;
    if (type == "glide_bomb") return .45;
    if (type == "cruise_missile") return .12;
    if (type == "bunker_buster") return .35;
    return 0.;
}

inline double fighterSalvoInterceptChance(const FighterInterceptor& fighter,double recon,
                                           const Munition& interceptor,const Munition& target) {
    const double detection = std::clamp(.16+fighter.radar*.28+recon*.22+target.rcs*.42+target.infrared*.10,0.,1.);
    const double tracking = std::clamp(detection*.42+fighter.radar*.32+fighter.speed*.10+fighter.ew*.08,0.,1.);
    const double speed = std::max(.28,1-std::max(0.,target.terminal-1)*.18);
    const double maneuver = std::max(.45,1-target.maneuver*.30);
    const double quality = std::clamp(interceptor.accuracy*.55+interceptor.guidance*.35+interceptor.maneuver*.10,0.,1.);
    const double missileSpeed = std::clamp(interceptor.terminal/std::max(.35,target.terminal),.55,1.35);
    return std::clamp((.20+tracking*.34)*detection*speed*maneuver*std::max(.55,fighter.survivability)*
        (.65+quality*.55)*missileSpeed,0.,1.);
}

inline double fighterAircraftHitChance(int fighterType,int targetType,const Munition& missile,bool defensive) {
    const auto& fighter = fighterInterceptors[fighterType];
    const auto& target = aircraftSignatures[targetType];
    const double detection = std::clamp(.14+fighter.radar*.32+aircraftTypes[fighterType].recon*.16+
        target.rcs*.26-target.stealth*.20,0.,1.);
    const double tracking = std::clamp(detection*.38+fighter.radar*.28+fighter.speed*.11+fighter.ew*.08,0.,1.);
    const double speed = std::max(.38,1-std::max(0.,target.speed-1)*.16);
    const double quality = std::clamp(missile.accuracy*.50+missile.guidance*.36+missile.maneuver*.14,0.,1.);
    const double missileSpeed = std::clamp(missile.terminal/std::max(.45,target.speed),.55,1.30);
    return std::clamp((.18+tracking*.34)*detection*speed*std::max(.42,1-target.survivability*.38)*
        (defensive ? .52 : 1.)*(.62+quality*.58)*missileSpeed,0.,1.);
}

inline std::span<const std::pair<std::string_view,double>> airEquipmentTargetProfile(std::string_view type) {
    using Target = std::pair<std::string_view,double>;
    static constexpr Target rockets[]{{"vehicles",2.40},{"old_ifv",2.05},{"old_at_missiles",1.80},
        {"old_light_artillery",.80},{"old_light_aa_artillery",.75},{"spare_parts",.45}};
    static constexpr Target guided[]{{"vehicles",2.40},{"old_ifv",2.15},{"old_at_missiles",1.95},
        {"old_light_aa_artillery",1.05},{"old_light_artillery",.80},{"spare_parts",.70}};
    static constexpr Target bombs[]{{"field_supplies",2.20},{"spare_parts",1.80},{"old_light_artillery",1.60},
        {"old_light_aa_artillery",1.25},{"weapons",.75},{"infantry_equipment",.65},{"vehicles",.55},{"old_ifv",.45}};
    static constexpr Target heavy[]{{"field_supplies",1.75},{"spare_parts",1.55},{"old_light_artillery",1.25},
        {"old_light_aa_artillery",1.15},{"vehicles",.85},{"old_ifv",.70},{"old_at_missiles",.65}};
    if (type == "unguided_rocket") return rockets;
    if (type == "guided_missile") return guided;
    if (type == "guided_bomb" || type == "glide_bomb") return bombs;
    if (type == "cruise_missile" || type == "ballistic_missile" ||
        type == "heavy_strategic_missile" || type == "bunker_buster") return heavy;
    return {};
}

inline std::span<const Building> buildingsForAirTarget(std::string_view tag) {
    static constexpr Building airfields[]{airbase}, bunker[]{airbase,supplyDepot,warehouse};
    static constexpr Building sam[]{airbase,supplyDepot}, factories[]{industry,refinery};
    static constexpr Building depot[]{supplyDepot,warehouse,fuelStorage}, cities[]{city,village};
    static constexpr Building infrastructure[]{supplyDepot,warehouse,port,fuelStorage,city,village};
    static constexpr Building civilian[]{city,village,farms};
    static constexpr Building supply[]{supplyDepot,warehouse,fuelStorage,port};
    static constexpr Building industrial[]{industry,refinery,mine,oilGasRig};
    static constexpr Building bases[]{airbase,supplyDepot,warehouse,fuelStorage};
    static constexpr Building aviation[]{airbase,fieldHelipad};
    static constexpr Building helipads[]{fieldHelipad};
    static constexpr Building all[]{city,village,farms,mine,oilGasRig,industry,port,
        warehouse,supplyDepot,fortification,fuelStorage,refinery,airbase,fieldHelipad};
    if (tag == "airbase" || tag == "radar" || tag == "hardened_shelter") return airfields;
    if (tag == "field_helipad") return helipads;
    if (tag == "bunker") return bunker;
    if (tag == "sam") return sam;
    if (tag == "factory") return factories;
    if (tag == "depot") return depot;
    if (tag == "city") return cities;
    if (tag == "infrastructure") return infrastructure;
    if (tag == "civilian_infrastructure") return civilian;
    if (tag == "supply_infrastructure") return supply;
    if (tag == "industry") return industrial;
    if (tag == "bases") return bases;
    if (tag == "airbases") return aviation;
    if (tag == "air_defense") return sam;
    if (tag == "buildings") return all;
    return {};
}

inline std::string_view airTargetObject(int building) {
    switch (building) {
        case industry: case refinery: case mine: case oilGasRig: return "factory";
        case supplyDepot: case warehouse: case fuelStorage: return "depot";
        case port: return "infrastructure";
        case city: case village: return "city";
        case farms: return "civilian_infrastructure";
        case airbase: case fieldHelipad: return "airbase";
        default: return {};
    }
}

inline std::vector<Building> airImpactPreferences(const AirSalvo& salvo,
                                                  std::span<const std::string_view> priorities = {}) {
    std::vector<Building> preferred;
    const auto append = [&](std::string_view tag) {
        for (auto building : buildingsForAirTarget(tag))
            if (std::ranges::find(preferred,building) == preferred.end()) preferred.push_back(building);
    };
    append(salvo.targetObject);
    for (auto tag : priorities) append(tag);
    const auto type = salvo.weapon->type;
    if (type == "guided_missile") {
        append("buildings"); append("sam");
    } else if (type == "guided_bomb" || type == "glide_bomb") {
        append("buildings"); append("infrastructure"); append("factory"); append("depot");
        if (type == "glide_bomb") append("bunker");
    } else if (type == "cruise_missile") {
        append("airbase"); append("radar"); append("sam"); append("infrastructure"); append("factory"); append("depot");
    } else if (type == "ballistic_missile" || type == "heavy_strategic_missile") {
        append("airbase"); append("bunker"); append("depot"); append("infrastructure");
        if (type == "ballistic_missile") append("sam");
        else { append("city"); append("factory"); }
    } else if (type == "bunker_buster") {
        append("bunker"); append("airbase"); append("hardened_shelter");
    }
    return preferred;
}

inline int airHexDistance(int a,int b,int size) {
    const int dq = a%size-b%size, dr = a/size-b/size;
    return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
}

inline std::optional<double> airMissionLaunchDistance(double targetDistance,const Munition& weapon,
                                                      int defenseRadius,AirRisk risk,bool strategic) {
    if (weapon.maxRange < weapon.minRange || weapon.maxRange <= 0) return std::nullopt;
    const double safeEdge = std::max(0,defenseRadius);
    double desired = std::max(weapon.optimal,safeEdge > 0 ? safeEdge : weapon.optimal*.75);
    switch (risk) {
        case AirRisk::cautious:
            desired = std::max({weapon.optimal,safeEdge,weapon.maxRange*.82});
            break;
        case AirRisk::aggressive:
            desired = std::max(weapon.minRange,std::min(weapon.optimal*.65,weapon.maxRange*.55));
            break;
        case AirRisk::allOut:
            desired = weapon.minRange;
            break;
        case AirRisk::normal:
            break;
    }
    if (!strategic) desired = std::min(desired,weapon.maxRange*.62);
    return std::max(weapon.minRange,std::min({weapon.maxRange,std::max(0.,targetDistance),desired}));
}

inline int airTileBetween(int a,int b,int size,double progress,int fallback = -1) {
    const double q = std::lerp(double(a%size),double(b%size),progress);
    const double r = std::lerp(double(a/size),double(b/size),progress);
    const double s = -q-r;
    int rq = int(std::nearbyint(q)), rr = int(std::nearbyint(r)), rs = int(std::nearbyint(s));
    const double dq = std::abs(rq-q), dr = std::abs(rr-r), ds = std::abs(rs-s);
    if (dq > dr && dq > ds) rq = -rr-rs;
    else if (dr > ds) rr = -rq-rs;
    if (rq < 0 || rq >= size || rr < 0 || rr >= size) return fallback < 0 ? b : fallback;
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
