#pragma once

#include <string_view>

namespace hoi5 {
struct AircraftType { std::string_view key; double range; int runway, starting; bool helicopter; };
inline constexpr AircraftType aircraftTypes[] = {
    {"light_fighter", 7, 1, 12, false},
    {"multirole_fighter", 8, 1, 8, false},
    {"fighter_bomber", 9, 1, 0, false},
    {"cas_aircraft", 5, 1, 8, false},
    {"attack_helicopter", 4, 0, 6, true},
    {"strategic_bomber", 18, 2, 0, false},
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
