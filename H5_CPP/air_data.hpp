#pragma once

#include <string_view>

namespace hoi5 {
enum class AirRisk { cautious, normal, aggressive, allOut };
struct AircraftType { std::string_view key; double range; int runway, starting; bool helicopter, cas, strike; double recon; bool airSuperiority = false; };
struct FighterInterceptor { double radar,speed,ew,survivability; int ammoPerAircraft; };
inline constexpr FighterInterceptor fighterInterceptors[]{
    {.72,2.2,.18,.72,4}, {.68,2.,.24,.66,3}
};
struct AircraftSignature { double speed,stealth,rcs,survivability; };
inline constexpr AircraftSignature aircraftSignatures[]{
    {2.2,.12,.55,.72},{2.,.16,.62,.66},{1.65,.10,.82,.54},
    {1.1,.04,.95,.48},{.65,.08,.42,.36},{1.35,.06,1.35,.60}
};
inline constexpr AircraftType aircraftTypes[] = {
    {"light_fighter", 7, 1, 12, false, false, false, .22, true},
    {"multirole_fighter", 8, 1, 8, false, true, true, .25, true},
    {"fighter_bomber", 9, 1, 0, false, true, true, .18},
    {"cas_aircraft", 5, 1, 8, false, true, true, .30},
    {"attack_helicopter", 4, 0, 6, true, true, false, .36},
    {"strategic_bomber", 18, 2, 0, false, false, true, .16},
};
inline constexpr std::string_view aircraftNames[]{
    "Легкий истребитель","Многоцелевой истребитель","Истребитель-бомбардировщик",
    "Штурмовик","Ударный вертолет","Стратегический бомбардировщик"
};
struct DefenseClass {
    std::string_view key;
    int radarRange, fireRange, minimumRange, ammo;
    double readiness, camouflage, detectionPower, trackingQuality;
    int trackingChannels, fireChannels, maxTargets, interceptors;
    bool radarActive;
};
inline constexpr DefenseClass defenseClasses[] = {
    {"manpads_team", 0, 1, 0, 10, 0.82, 0.82, 0.28, 0.3, 2, 2, 2, 1, false},
    {"short_range_aa", 2, 1, 0, 24, 0.78, 0.55, 0.52, 0.48, 5, 4, 5, 1, true},
    {"medium_range_sam", 5, 3, 1, 18, 0.72, 0.38, 0.76, 0.68, 6, 4, 6, 1, true},
    {"long_range_sam", 8, 5, 1, 12, 0.66, 0.25, 0.88, 0.76, 5, 3, 5, 1, true},
    {"radar_unit", 7, 0, 0, 0, 0.86, 0.3, 0.95, 0.82, 0, 0, 0, 1, true},
};
}
