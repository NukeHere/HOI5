#pragma once

#include "air_layer.hpp"

namespace hoi5 {
struct Munition { std::string_view key, type, profile; double minRange,maxRange,optimal,terminalRange,cruise,terminal,accuracy,warhead,penetration,rcs,infrared,maneuver,difficulty,low,high,damageMult,damageCap; bool interceptable; double guidance; };
inline constexpr Munition munitions[] = {
    {"unguided_rockets", "unguided_rocket", "sqrt", 0.0, 1.0, 0.35, 0.15, 0.8, 0.9, 0.32, 0.45, 0.12, 0.1, 0.42, 0.08, 0.18, 0.18, 0.55, 0.18, 0.035, false, .05},
    {"light_guided_missile", "guided_missile", "linear", 0.3, 3.0, 1.4, 0.4, 1.1, 0.9, 0.72, 0.85, 0.76, 0.18, 0.38, 0.32, 0.42, 0.2, 0.9, 0.42, 0.08, true, .70},
    {"guided_bomb", "guided_bomb", "square", 0.2, 2.2, 1.0, 0.25, 0.75, 1.15, 0.64, 1.35, 0.38, 0.22, 0.12, 0.1, 0.3, 0.22, 0.66, 0.95, 0.17, true, .62},
    {"glide_bomb", "glide_bomb", "glide", 0.7, 5.0, 3.0, 0.5, 0.65, 0.85, 0.62, 1.55, 0.42, 0.34, 0.1, 0.12, 0.34, 0.28, 0.86, 1.05, 0.2, true, .64},
    {"tactical_cruise_missile", "cruise_missile", "sustained_motor", 2.0, 10.0, 7.0, 1.0, 0.95, 1.05, 0.78, 2.2, 0.55, 0.24, 0.32, 0.26, 0.58, 0.34, 0.78, 1.35, 0.29, true, .76},
    {"small_ballistic_missile", "ballistic_missile", "ballistic", 2.0, 8.0, 5.0, 0.8, 1.8, 2.6, 0.7, 2.5, 0.8, 0.42, 0.64, 0.18, 0.74, 0.22, 0.58, 1.65, 0.34, true, .70},
    {"heavy_strategic_missile", "heavy_strategic_missile", "two_stage", 4.0, 18.0, 12.0, 1.5, 2.4, 3.2, 0.74, 4.8, 1.15, 0.55, 0.82, 0.3, 0.88, 0.18, 0.48, 2.25, 0.46, true, .76},
    {"bunker_buster", "bunker_buster", "square", 0.2, 1.8, 0.8, 0.2, 0.72, 1.45, 0.68, 2.8, 1.35, 0.28, 0.1, 0.04, 0.44, 0.26, 0.72, 1.85, 0.39, true, .66},
    {"short_air_to_air_missile", "air_to_air_missile", "sustained_motor", 0.1, 2.5, 1.0, 0.4, 1.9, 2.2, 0.62, 0.32, 0.08, 0.08, 0.58, 0.74, 0.52, 0.1, 0.44, 0.65, 0.32, false, .66},
    {"medium_air_to_air_missile", "air_to_air_missile", "sustained_motor", 0.4, 5.5, 2.8, 0.7, 2.2, 2.5, 0.66, 0.38, 0.1, 0.1, 0.44, 0.68, 0.58, 0.12, 0.5, 0.65, 0.32, false, .72},
};
inline const std::vector<std::string_view> aircraftMunitions[] = {
    {"unguided_rockets", "light_guided_missile"},
    {"light_guided_missile", "guided_bomb", "glide_bomb"},
    {"guided_bomb", "glide_bomb", "tactical_cruise_missile", "small_ballistic_missile"},
    {"unguided_rockets", "light_guided_missile", "guided_bomb"},
    {"unguided_rockets", "light_guided_missile"},
    {"tactical_cruise_missile", "small_ballistic_missile", "heavy_strategic_missile", "bunker_buster"},
};
inline constexpr std::array<double,buildingCount> buildingHardness{
    1.35, 0.85, 0.85, 0.8, 1.25, 0.72, 1.05, 1.1, 1.15, 0.65, 1.25, 1.15, 1, 0.42
};
inline constexpr std::array<double,buildingCount> buildingValue{
    1.15, 0.55, 0.9, 1.25, 1.1, 1.15, 1.25, 1.0, 1.35, 0.42, 0.8, 1.45, 0.75, 0.7
};
struct InterceptorProfile { double maximum, escape, rcsSensitivity; };
inline constexpr std::array<InterceptorProfile, std::size(defenseClasses)> interceptorProfiles{{
    {1, 0.45, .20},
    {1, 0.65, .38},
    {3, 1.7, .62},
    {5, 2.4, .78},
    {1, 0.45, .45},
}};
}
