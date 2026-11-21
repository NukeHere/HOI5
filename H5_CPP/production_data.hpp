#pragma once

#include "market_clearing.hpp"

namespace hoi5 {
inline constexpr unsigned productionContractVersion = 1;

enum ProductionStage { raw, semiFinished, agriculture, finished, upkeep, productionStages };
struct ProductionFlows { Stockpile inputs, outputs; };
struct ProductionAssignment { std::string_view recipe; double power{}; };
using ProductionPlan = std::vector<ProductionAssignment>;
struct ProductionLine {
    std::string_view recipe;
    double assignedPower{}, availablePower{}, plannedUnits{}, actualUnits{};
    Stockpile inputs, outputs;
    Stockpile actualInputs, actualOutputs, storedOutputs;
    std::vector<std::string_view> limits;
};
struct Production : std::array<ProductionFlows, productionStages> {
    bool nationalPlan = false;
    double totalPower{}, unusedPower{};
    std::vector<ProductionLine> lines;
    std::array<ProductionFlows, productionStages> passive;
};
struct Recipe {
    ProductionStage stage;
    Building building;
    std::string_view sector, technology;
    double rate;
    Stockpile inputs, outputs;
    std::string_view id;
    double powerCost = 100.;
};

inline const Recipe recipes[] = {
    {semiFinished, industry, "metallurgy", "", 5200, {{"iron_ore",2.0}, {"coal",0.8}}, {{"steel",1.0}}, "steel"},
    {semiFinished, refinery, "refining", "", 6200, {{"oil",1.0}}, {{"refined_fuel",0.72}, {"chemicals",0.22}}, "oil_refining"},
    {semiFinished, industry, "chemicals", "", 3600, {{"natural_gas",0.7}, {"sulfur",0.25}}, {{"chemicals",1.0}}, "chemicals"},
    {semiFinished, industry, "chemicals", "", 2600, {{"chemicals",0.5}, {"phosphorite",0.4}, {"potash",0.3}}, {{"fertilizer",1.0}}, "fertilizer"},
    {semiFinished, industry, "electronics", "", 2600, {{"copper_ore",1.2}}, {{"copper_wire",1.0}}, "copper_wire"},
    {finished, industry, "consumer_goods", "", 3400, {{"food",0.4}, {"chemicals",0.25}, {"steel",0.15}}, {{"consumer_goods",1.0}}, "consumer_goods"},
    {finished, industry, "machinery", "", 2800, {{"steel",0.9}, {"copper_wire",0.25}, {"chemicals",0.2}}, {{"machinery",1.0}}, "machinery"},
    {finished, industry, "vehicles", "", 1700, {{"steel",0.8}, {"machinery",0.45}, {"refined_fuel",0.2}}, {{"vehicles",1.0}}, "vehicles"},
    {finished, industry, "electronics", "", 1600, {{"copper_wire",0.65}, {"rare_earth_metals",0.12}, {"chemicals",0.25}}, {{"electronics",1.0}}, "electronics"},
    {finished, industry, "construction_materials", "", 4400, {{"steel",0.12}, {"chemicals",0.06}, {"quartz",0.18}}, {{"construction_goods",1.0}}, "construction_goods"},
    {finished, industry, "shipbuilding", "", 800, {{"steel",1.4}, {"machinery",0.65}, {"refined_fuel",0.25}}, {{"ships",1.0}}, "ships"},
    {finished, industry, "military", "", 1600, {{"steel",0.25}, {"machinery",0.08}, {"chemicals",0.12}}, {{"infantry_equipment",1}}, "infantry_equipment"},
    {finished, industry, "military", "", 1200, {{"steel",0.5}, {"machinery",0.08}, {"chemicals",0.1}}, {{"old_assault_rifles",1}}, "old_assault_rifles"},
    {finished, industry, "military", "", 12000, {{"steel",0.04}, {"machinery",0}, {"chemicals",0.08}}, {{"small_arms_ammo",1}}, "small_arms_ammo"},
    {finished, industry, "military", "", 80, {{"steel",8}, {"machinery",2}, {"chemicals",0.5}}, {{"old_light_artillery",1}}, "old_light_artillery"},
    {finished, industry, "military", "", 1800, {{"steel",0.3}, {"machinery",0}, {"chemicals",0.4}}, {{"light_artillery_ammo",1}}, "light_artillery_ammo"},
    {finished, industry, "military", "", 65, {{"steel",8}, {"machinery",2}, {"chemicals",0.8}}, {{"old_light_aa_artillery",1}}, "old_light_aa_artillery"},
    {finished, industry, "military", "", 2400, {{"steel",0.2}, {"machinery",0}, {"chemicals",0.3}}, {{"light_aa_ammo",1}}, "light_aa_ammo"},
    {finished, industry, "military", "", 20, {{"steel",30}, {"machinery",12}, {"electronics",4}}, {{"tank",1}}, "tank"},
    {finished, industry, "military", "", 45, {{"steel",16}, {"machinery",8}, {"chemicals",2}}, {{"old_ifv",1}}, "old_ifv"},
    {finished, industry, "military", "", 260, {{"steel",0.6}, {"machinery",0.15}, {"chemicals",1}}, {{"old_at_missiles",1}}, "old_at_missiles"},
    {finished, industry, "military", "", 3000, {{"steel",0.15}, {"machinery",0}, {"chemicals",0.22}}, {{"autocannon_ammo",1}}, "autocannon_ammo"},
    {finished, industry, "military", "", 1400, {{"steel",0.4}, {"machinery",0}, {"chemicals",0.5}}, {{"artillery_ammo",1}}, "artillery_ammo"},
    {finished, industry, "military", "", 900, {{"steel",0.5}, {"machinery",0}, {"chemicals",0.6}}, {{"tank_ammo",1}}, "tank_ammo"},
    {finished, industry, "military", "", 650, {{"steel",0.3}, {"machinery",0.1}, {"chemicals",0.8}}, {{"anti_air_ammo",1}}, "anti_air_ammo"},
    {finished, industry, "military", "", 2000, {{"steel",0.4}, {"machinery",0.15}, {"chemicals",0.05}}, {{"spare_parts",1}}, "spare_parts"},
    {finished, industry, "military", "", 3200, {{"steel",0.05}, {"machinery",0.02}, {"chemicals",0.2}}, {{"field_supplies",1}}, "field_supplies"},
    {finished, industry, "military", "", 12, {{"steel",40}, {"machinery",20}, {"electronics",12}, {"chemicals",8}}, {{"light_fighter",1}}, "light_fighter"},
    {finished, industry, "military", "", 8, {{"steel",50}, {"machinery",25}, {"electronics",18}, {"chemicals",10}}, {{"multirole_fighter",1}}, "multirole_fighter"},
    {finished, industry, "military", "", 8, {{"steel",60}, {"machinery",30}, {"electronics",16}, {"chemicals",12}}, {{"fighter_bomber",1}}, "fighter_bomber"},
    {finished, industry, "military", "", 12, {{"steel",40}, {"machinery",20}, {"electronics",8}, {"chemicals",8}}, {{"cas_aircraft",1}}, "cas_aircraft"},
    {finished, industry, "military", "", 14, {{"steel",25}, {"machinery",15}, {"electronics",10}, {"chemicals",5}}, {{"attack_helicopter",1}}, "attack_helicopter"},
    {finished, industry, "military", "", 3, {{"steel",180}, {"machinery",70}, {"electronics",30}, {"chemicals",36}}, {{"strategic_bomber",1}}, "strategic_bomber"},
    {finished, industry, "military", "", 1800, {{"steel",0.3}, {"machinery",0.05}, {"electronics",0.02}, {"chemicals",0.06}}, {{"unguided_rockets",1}}, "unguided_rockets"},
    {finished, industry, "military", "", 450, {{"steel",0.7}, {"machinery",0.2}, {"electronics",0.5}, {"chemicals",0.14}}, {{"light_guided_missile",1}}, "light_guided_missile"},
    {finished, industry, "military", "", 650, {{"steel",1}, {"machinery",0.1}, {"electronics",0.2}, {"chemicals",0.2}}, {{"guided_bomb",1}}, "guided_bomb"},
    {finished, industry, "military", "", 450, {{"steel",1.3}, {"machinery",0.15}, {"electronics",0.3}, {"chemicals",0.26}}, {{"glide_bomb",1}}, "glide_bomb"},
    {finished, industry, "military", "", 80, {{"steel",4}, {"machinery",1}, {"electronics",2}, {"chemicals",0.8}}, {{"tactical_cruise_missile",1}}, "tactical_cruise_missile"},
    {finished, industry, "military", "", 60, {{"steel",6}, {"machinery",1.5}, {"electronics",1.5}, {"chemicals",1.2}}, {{"small_ballistic_missile",1}}, "small_ballistic_missile"},
    {finished, industry, "military", "", 12, {{"steel",20}, {"machinery",5}, {"electronics",5}, {"chemicals",4}}, {{"heavy_strategic_missile",1}}, "heavy_strategic_missile"},
    {finished, industry, "military", "", 100, {{"steel",5}, {"machinery",0.5}, {"electronics",0.3}, {"chemicals",1}}, {{"bunker_buster",1}}, "bunker_buster"},
    {finished, industry, "military", "", 240, {{"steel",0.5}, {"machinery",0.1}, {"electronics",0.4}, {"chemicals",0.1}}, {{"short_air_to_air_missile",1}}, "short_air_to_air_missile"},
    {finished, industry, "military", "", 160, {{"steel",0.7}, {"machinery",0.2}, {"electronics",0.6}, {"chemicals",0.14}}, {{"medium_air_to_air_missile",1}}, "medium_air_to_air_missile"},
    {finished, industry, "military", "", 100, {{"steel",1}, {"machinery",0.2}, {"electronics",0.6}, {"chemicals",0.2}}, {{"manpads_team",1}}, "manpads_team"},
    {finished, industry, "military", "", 25, {{"steel",10}, {"machinery",4}, {"electronics",5}, {"chemicals",2}}, {{"short_range_aa",1}}, "short_range_aa"},
    {finished, industry, "military", "", 12, {{"steel",20}, {"machinery",8}, {"electronics",12}, {"chemicals",4}}, {{"medium_range_sam",1}}, "medium_range_sam"},
    {finished, industry, "military", "", 6, {{"steel",40}, {"machinery",16}, {"electronics",24}, {"chemicals",8}}, {{"long_range_sam",1}}, "long_range_sam"},
    {finished, industry, "military", "", 15, {{"steel",12}, {"machinery",6}, {"electronics",20}, {"chemicals",2.4}}, {{"radar_unit",1}}, "radar_unit"},
};
inline const Stockpile lifeSupport = {{"food",8100}, {"consumer_goods",150}, {"construction_goods",100}, {"refined_fuel",260}, {"chemicals",95}, {"vehicles",10}, {"electronics",2}};
inline const Stockpile cityUpkeep = {{"construction_goods",1185}, {"machinery",120}, {"refined_fuel",260}};
inline const Stockpile villageUpkeep = {{"construction_goods",350}, {"machinery",45}, {"refined_fuel",80}};
struct Sector { std::string_view name; std::vector<ResourceWeight> weights; };
inline const Sector sectors[] = {
    {"metallurgy", {{"iron_ore",1.0}, {"coal",0.8}, {"alloying_additives",0.35}}},
    {"construction_materials", {}},
    {"chemicals", {{"natural_gas",0.9}, {"sulfur",0.85}, {"phosphorite",0.35}, {"apatite",0.35}, {"potash",0.35}}},
    {"machinery", {{"iron_ore",0.6}, {"copper_ore",0.35}, {"coal",0.25}}},
    {"vehicles", {{"iron_ore",0.45}, {"oil",0.3}, {"rubber",0.3}, {"bauxite",0.2}}},
    {"electronics", {{"copper_ore",0.85}, {"rare_earth_metals",0.75}, {"quartz",0.35}}},
    {"shipbuilding", {{"iron_ore",0.45}, {"oil",0.25}}},
    {"military", {{"iron_ore",0.55}, {"copper_ore",0.25}, {"sulfur",0.25}}},
};
inline const Stockpile mineWeights = {{"coal",1.0}, {"oil",1.0}, {"natural_gas",0.95}, {"peat",0.55}, {"iron_ore",1.0}, {"copper_ore",0.82}, {"bauxite",0.64}, {"sulfur",0.42}, {"phosphorite",0.4}, {"apatite",0.36},
    {"quartz",.35},{"potash",.35},{"rare_earth_metals",.35},{"uranium",.35},{"lead",.35},{"zinc",.35},
    {"nickel",.35},{"gold",.35},{"silver",.35},{"alloying_additives",.35},{"graphite",.35},{"mica",.35}};
}
