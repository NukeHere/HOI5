#pragma once

#include "combat.hpp"
#include "market.hpp"
#include <limits>
#include <numeric>

namespace hoi5 {
struct DivisionTemplate {
    std::string_view key, name, icon;
    int manpower;
    double organization, recovery, speed;
    CombatStats combat;
    Stockpile capacity, use;
    double recon, camouflage;
    double reliability = 1.;
};
inline const DivisionTemplate divisionTemplates[] = {
    {"basic_infantry", "\u041f\u0435\u0445\u043e\u0442\u043d\u0430\u044f \u0434\u0438\u0432\u0438\u0437\u0438\u044f", "infantry", 10000, 100.0, 8.0, 1.35, {100.0,20.0,0.03,18.0,3.0,1.0,26.0,8.0,4.0,1.0,2.0,1.0,0.92,0.08}, {{"infantry_equipment",950}, {"old_assault_rifles",900}, {"small_arms_ammo",5600}, {"old_light_artillery",24}, {"light_artillery_ammo",420}, {"old_light_aa_artillery",18}, {"light_aa_ammo",340}, {"old_ifv",48}, {"old_at_missiles",160}, {"autocannon_ammo",520}, {"vehicles",260}, {"field_supplies",1050}, {"spare_parts",130}, {"refined_fuel",360}}, {{"small_arms_ammo",15.0}, {"light_artillery_ammo",1.4}, {"light_aa_ammo",0.35}, {"old_at_missiles",0.05}, {"autocannon_ammo",0.65}, {"field_supplies",0.9}, {"refined_fuel",0.45}}, 0., 0.},
    {"tank", "\u0422\u0430\u043d\u043a\u043e\u0432\u0430\u044f \u0434\u0438\u0432\u0438\u0437\u0438\u044f", "tank", 8000, 100.0, 6.0, 1.7, {100.0,28.0,0.06,16.0,22.0,4.0,16.0,34.0,26.0,5.0,30.0,8.0,0.25,0.75}, {{"weapons",541.5}, {"infantry_equipment",484.5}, {"small_arms_ammo",2736.0}, {"artillery_ammo",495.03999999999996}, {"tank_ammo",181.8}, {"anti_air_ammo",133.28}, {"vehicles",222.20000000000005}, {"refined_fuel",1111.0000000000002}, {"spare_parts",363.6}, {"field_supplies",513.0}}, {{"small_arms_ammo",4.0}, {"artillery_ammo",0.768}, {"tank_ammo",2.376}, {"anti_air_ammo",0.32000000000000006}, {"refined_fuel",4.284}, {"field_supplies",0.68}}, .04, 0.},
    {"motorized", "\u041c\u043e\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d\u043d\u0430\u044f \u0434\u0438\u0432\u0438\u0437\u0438\u044f", "motorized", 9000, 100.0, 7.0, 1.9, {100.0,22.0,0.05,20.0,7.0,2.0,20.0,18.0,8.0,2.0,7.0,3.0,0.65,0.35}, {{"weapons",831.4875}, {"infantry_equipment",743.9625}, {"small_arms_ammo",4201.2}, {"artillery_ammo",470.34000000000003}, {"tank_ammo",117.04499999999999}, {"anti_air_ammo",126.63000000000001}, {"vehicles",143.05499999999998}, {"refined_fuel",715.275}, {"spare_parts",234.08999999999997}, {"field_supplies",787.7249999999999}}, {{"small_arms_ammo",9.945}, {"artillery_ammo",1.4400000000000002}, {"tank_ammo",0.3969}, {"anti_air_ammo",0.18000000000000002}, {"refined_fuel",2.5136999999999996}, {"field_supplies",0.765}}, .03, 0.},
    {"anti_tank", "\u041f\u0422/\u041f\u0422\u0423\u0420 \u0434\u0438\u0432\u0438\u0437\u0438\u044f", "anti_tank", 7000, 100.0, 7.0, 1.25, {100.0,18.0,0.04,10.0,20.0,5.0,22.0,7.0,28.0,8.0,3.0,1.0,0.85,0.15}, {{"weapons",733.1624999999999}, {"infantry_equipment",655.9874999999998}, {"small_arms_ammo",3704.399999999999}, {"artillery_ammo",325.78000000000003}, {"tank_ammo",57.01499999999999}, {"anti_air_ammo",87.71000000000001}, {"vehicles",69.685}, {"refined_fuel",348.425}, {"spare_parts",114.02999999999999}, {"field_supplies",694.5749999999999}}, {{"small_arms_ammo",6.8425}, {"artillery_ammo",0.33}, {"tank_ammo",0.378}, {"anti_air_ammo",0.35}, {"refined_fuel",0.55125}, {"field_supplies",0.595}}, .02, 0.},
    {"anti_air", "\u041f\u0412\u041e \u0434\u0438\u0432\u0438\u0437\u0438\u044f", "anti_air", 7000, 100.0, 7.0, 1.25, {100.0,18.0,0.03,9.0,8.0,12.0,20.0,6.0,10.0,14.0,3.0,1.0,0.82,0.18}, {{"weapons",720.1949999999999}, {"infantry_equipment",644.385}, {"small_arms_ammo",3638.8799999999997}, {"artillery_ammo",327.964}, {"tank_ammo",62.117999999999995}, {"anti_air_ammo",88.298}, {"vehicles",75.922}, {"refined_fuel",379.61}, {"spare_parts",124.23599999999999}, {"field_supplies",682.29}}, {{"small_arms_ammo",6.285299999999999}, {"artillery_ammo",0.33}, {"tank_ammo",0.18144}, {"anti_air_ammo",0.8400000000000001}, {"refined_fuel",0.6615}, {"field_supplies",0.595}}, .02, 0.},
};
using DivisionComposition = std::array<int,std::size(divisionTemplates)>;

inline std::vector<std::string_view> divisionEquipmentOrder(const DivisionComposition& parts) {
    constexpr std::string_view infantry[]{"infantry_equipment","old_assault_rifles","small_arms_ammo",
        "old_light_artillery","light_artillery_ammo","old_light_aa_artillery","light_aa_ammo","old_ifv",
        "old_at_missiles","autocannon_ammo","vehicles","field_supplies","spare_parts","refined_fuel"};
    constexpr std::string_view standard[]{"weapons","infantry_equipment","small_arms_ammo","artillery_ammo",
        "tank_ammo","anti_air_ammo","vehicles","refined_fuel","spare_parts","field_supplies"};
    std::vector<std::string_view> result;
    if (parts[0] > 0) result.assign(std::begin(infantry),std::end(infantry));
    if (std::ranges::any_of(parts.begin()+1,parts.end(),[](int count) { return count > 0; }))
        for (const auto key : standard)
            if (std::ranges::find(result,key) == result.end()) result.push_back(key);
    return result;
}

inline DivisionTemplate composeDivision(const DivisionComposition& parts,std::string_view name) {
    const int total = std::accumulate(parts.begin(),parts.end(),0);
    DivisionTemplate result{};
    if (total < 1 || total > 20 ||
        std::ranges::any_of(parts,[](int count) { return count < 0 || count > 20; })) return result;
    result.name = name;
    result.icon = divisionTemplates[std::ranges::max_element(parts)-parts.begin()].icon;
    result.speed = std::numeric_limits<double>::infinity();
    result.reliability = 0.;
    auto& combat = result.combat;
    combat = {100,0,0,0,0,0,0,0,0,0,0,0,0,0};
    double manpower = 0.;
    for (std::size_t i = 0; i < parts.size(); ++i) {
        if (parts[i] <= 0) continue;
        const auto& type = divisionTemplates[i];
        const double scale = parts[i]/10., share = double(parts[i])/total;
        manpower += type.manpower*scale;
        result.speed = std::min(result.speed,type.speed);
        result.organization += type.organization*share;
        result.recovery += type.recovery*share;
        result.recon += type.recon*share;
        result.camouflage += type.camouflage*share;
        result.reliability += type.reliability*share;
        for (auto field : {&CombatStats::width,&CombatStats::softAttack,&CombatStats::defense,
             &CombatStats::breakthrough,&CombatStats::frontAttack,&CombatStats::topAttack})
            combat.*field += type.combat.*field*scale;
        for (auto field : {&CombatStats::initiative,&CombatStats::frontPiercing,&CombatStats::topPiercing,
             &CombatStats::frontArmor,&CombatStats::topArmor,&CombatStats::infantry,&CombatStats::vehicles})
            combat.*field += type.combat.*field*share;
        for (const auto& [key,amount] : type.capacity) result.capacity[key] += amount*scale;
        for (const auto& [key,amount] : type.use) result.use[key] += amount*scale;
    }
    result.manpower = int(std::nearbyint(manpower));
    const double share = combat.infantry+combat.vehicles;
    combat.infantry /= share;
    combat.vehicles /= share;
    return result;
}

struct SavedDivisionDesign {
    std::string name;
    DivisionComposition composition;
    DivisionTemplate design;

    SavedDivisionDesign(std::string name,DivisionComposition composition)
        : name(std::move(name)), composition(composition), design(composeDivision(composition,this->name)) {}
};
inline constexpr double DIVISION_COMBAT_REINFORCEMENT_MULT = 0.22;
inline constexpr double DIVISION_REINFORCEMENT_STRENGTH_PER_DAY = 1.6;
inline constexpr double DIVISION_MANPOWER_STRENGTH_LOSS_MULT = 1.0;
inline constexpr double DIVISION_EQUIPMENT_STRENGTH_LOSS_MULT = 0.75;
inline constexpr double DIVISION_COMBAT_STOCK_STRENGTH_LOSS_MULT = 0.55;
inline constexpr double DIVISION_AMMO_ATTACK_FLOOR = 0.35;
inline constexpr std::string_view DIVISION_EQUIPMENT_LOSS_KEYS[] = {"field_supplies", "infantry_equipment", "old_assault_rifles", "old_at_missiles", "old_ifv", "old_light_aa_artillery", "old_light_artillery", "spare_parts", "vehicles", "weapons"};
inline constexpr std::string_view DIVISION_COMBAT_STOCK_LOSS_KEYS[] = {"anti_air_ammo", "artillery_ammo", "autocannon_ammo", "light_aa_ammo", "light_artillery_ammo", "refined_fuel", "small_arms_ammo", "tank_ammo"};
}
