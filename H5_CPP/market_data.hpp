#pragma once

#include "storage.hpp"

namespace hoi5 {

inline const Stockpile TRADE_BASE_PRICES = {{"coal",34}, {"oil",72}, {"natural_gas",48}, {"peat",16}, {"uranium",420}, {"iron_ore",38}, {"copper_ore",96}, {"bauxite",62}, {"lead",58}, {"zinc",54}, {"nickel",118}, {"gold",1800}, {"silver",620}, {"rare_earth_metals",980}, {"alloying_additives",180}, {"potash",44}, {"phosphorite",40}, {"apatite",42}, {"sulfur",58}, {"rubber",120}, {"graphite",160}, {"mica",110}, {"quartz",92}, {"steel",135}, {"refined_fuel",118}, {"chemicals",145}, {"food",22}, {"fertilizer",105}, {"copper_wire",210}, {"consumer_goods",260}, {"machinery",620}, {"vehicles",850}, {"electronics",1250}, {"construction_goods",170}, {"weapons",1100}, {"infantry_equipment",520}, {"old_assault_rifles",380}, {"small_arms_ammo",42}, {"old_light_artillery",1450}, {"light_artillery_ammo",190}, {"old_light_aa_artillery",1650}, {"light_aa_ammo",230}, {"old_ifv",2200}, {"old_at_missiles",620}, {"autocannon_ammo",160}, {"artillery_ammo",280}, {"tank_ammo",460}, {"anti_air_ammo",540}, {"spare_parts",240}, {"field_supplies",95}, {"ships",4200}};
inline const Stockpile MARKET_RESOURCE_RARITY = {{"coal",1.05}, {"oil",0.85}, {"natural_gas",0.8}, {"peat",0.9}, {"uranium",0.18}, {"iron_ore",1.0}, {"copper_ore",0.62}, {"bauxite",0.55}, {"lead",0.72}, {"zinc",0.72}, {"nickel",0.36}, {"gold",0.5}, {"silver",0.58}, {"rare_earth_metals",0.1}, {"alloying_additives",0.25}, {"potash",0.42}, {"phosphorite",0.5}, {"apatite",0.46}, {"sulfur",0.48}, {"rubber",0.3}, {"graphite",0.25}, {"mica",0.28}, {"quartz",0.42}, {"steel",0.85}, {"refined_fuel",0.78}, {"chemicals",0.64}, {"food",1.2}, {"fertilizer",0.52}, {"copper_wire",0.44}, {"consumer_goods",0.78}, {"machinery",0.46}, {"vehicles",0.36}, {"electronics",0.22}, {"construction_goods",0.95}, {"weapons",0.26}, {"infantry_equipment",0.36}, {"old_assault_rifles",0.34}, {"small_arms_ammo",0.42}, {"old_light_artillery",0.22}, {"light_artillery_ammo",0.32}, {"old_light_aa_artillery",0.2}, {"light_aa_ammo",0.3}, {"old_ifv",0.16}, {"old_at_missiles",0.18}, {"autocannon_ammo",0.3}, {"artillery_ammo",0.3}, {"tank_ammo",0.22}, {"anti_air_ammo",0.2}, {"spare_parts",0.45}, {"field_supplies",0.7}, {"ships",0.14}};
inline const Stockpile MARKET_RESOURCE_VOLATILITY = {{"rare_earth_metals",1.8}, {"uranium",1.55}, {"gold",1.2}, {"silver",1.15}, {"electronics",1.35}, {"ships",1.45}, {"weapons",1.3}, {"old_ifv",1.25}, {"old_at_missiles",1.2}, {"tank_ammo",1.28}, {"anti_air_ammo",1.35}, {"artillery_ammo",1.18}, {"small_arms_ammo",1.05}, {"oil",1.25}, {"natural_gas",1.2}, {"rubber",1.25}, {"food",0.75}, {"construction_goods",0.82}, {"iron_ore",0.85}, {"coal",0.8}, {"steel",0.92}};
inline const std::map<std::string_view, Stockpile> linkedPrices = {
    {"oil",{{"refined_fuel",0.34}, {"chemicals",0.1}}},
    {"natural_gas",{{"refined_fuel",0.12}, {"fertilizer",0.16}, {"chemicals",0.12}}},
    {"coal",{{"refined_fuel",0.06}, {"steel",0.14}}},
    {"peat",{{"refined_fuel",0.03}}},
    {"iron_ore",{{"steel",0.22}}},
    {"copper_ore",{{"copper_wire",0.28}, {"electronics",0.08}}},
    {"rare_earth_metals",{{"electronics",0.22}}},
    {"rubber",{{"vehicles",0.12}}},
    {"potash",{{"fertilizer",0.12}}},
    {"phosphorite",{{"fertilizer",0.1}}},
    {"apatite",{{"fertilizer",0.08}}},
    {"sulfur",{{"chemicals",0.1}}},
    {"refined_fuel",{{"oil",0.8}, {"natural_gas",0.2}, {"coal",0.12}, {"peat",0.06}}},
    {"fertilizer",{{"natural_gas",0.34}, {"potash",0.24}, {"phosphorite",0.18}, {"apatite",0.16}, {"chemicals",0.22}}},
    {"chemicals",{{"natural_gas",0.22}, {"oil",0.16}, {"sulfur",0.18}}},
    {"steel",{{"iron_ore",0.45}, {"coal",0.26}, {"alloying_additives",0.12}, {"machinery",0.1}, {"vehicles",0.1}, {"ships",0.12}}},
    {"copper_wire",{{"copper_ore",0.62}, {"refined_fuel",0.08}, {"electronics",0.1}}},
    {"machinery",{{"steel",0.34}, {"copper_wire",0.18}, {"chemicals",0.08}, {"vehicles",0.12}, {"ships",0.1}, {"weapons",0.1}}},
    {"vehicles",{{"steel",0.28}, {"rubber",0.2}, {"refined_fuel",0.12}, {"machinery",0.24}}},
    {"electronics",{{"rare_earth_metals",0.34}, {"copper_wire",0.22}, {"chemicals",0.1}}},
    {"consumer_goods",{{"chemicals",0.12}, {"food",0.08}, {"refined_fuel",0.06}}},
    {"construction_goods",{{"steel",0.12}, {"refined_fuel",0.06}, {"machinery",0.05}}},
    {"weapons",{{"steel",0.26}, {"machinery",0.22}, {"electronics",0.12}}},
    {"ships",{{"steel",0.38}, {"machinery",0.2}, {"electronics",0.08}, {"refined_fuel",0.08}}},
};
inline constexpr double MARKET_MAX_WEEKLY_PRICE_MOVE = 0.35;
inline constexpr double MARKET_SHOCK_DECAY = 0.55;
inline constexpr double MARKET_SHOCK_FACTOR = 2.0;
inline constexpr double MARKET_PRICE_SMOOTHING = 0.42;
inline constexpr double MARKET_LINKED_PRICE_SMOOTHING = 0.35;
}
