#pragma once

#include "production.hpp"

namespace hoi5 {

inline std::string_view storageBucket(std::string_view resource) {
    constexpr std::array fuel{"coal","oil","natural_gas","peat","uranium","refined_fuel"};
    constexpr std::array semi{"steel","chemicals","food","fertilizer","copper_wire"};
    constexpr std::array manufactured{"consumer_goods","machinery","vehicles","electronics","construction_goods",
        "weapons","infantry_equipment","old_assault_rifles","small_arms_ammo","old_light_artillery",
        "light_artillery_ammo","old_light_aa_artillery","light_aa_ammo","old_ifv","old_at_missiles",
        "autocannon_ammo","artillery_ammo","tank_ammo","anti_air_ammo","spare_parts","field_supplies","ships"};
    if (std::find(fuel.begin(),fuel.end(),resource) != fuel.end()) return "fuel";
    if (std::find(semi.begin(),semi.end(),resource) != semi.end()) return "semi_finished";
    if (std::find(manufactured.begin(),manufactured.end(),resource) != manufactured.end()) return "finished";
    return "raw";
}

template<class Tile>
Stockpile storageCapacity(const std::vector<Tile>& tiles, int country) {
    constexpr std::array<std::string_view,4> buckets{"raw","semi_finished","finished","fuel"};
    constexpr int rates[][buildingCount] = {
        {520000,180000,1050000,240000,280000},
        {470000,140000,820000,210000,240000},
        {560000,200000,760000,190000,220000},
        {180000,35000,0,120000,220000,3200000,850000,420000}
    };
    Stockpile result;
    for (auto bucket : buckets) result[bucket] = 0;
    for (const auto& tile : tiles) {
        if (tile.owner != country) continue;
        for (std::size_t bucket = 0; bucket < buckets.size(); ++bucket)
            for (int b = 0; b < buildingCount; ++b)
                result[buckets[bucket]] += tile.buildings[b].area * tile.buildings[b].health * rates[bucket][b];
    }
    return result;
}

inline double freeStorage(const Stockpile& capacity, const Stockpile& stocks, std::string_view resource) {
    const auto bucket = storageBucket(resource);
    double free = capacity.at(bucket);
    for (const auto& [key,amount] : stocks)
        if (storageBucket(key) == bucket) free -= amount;
    return std::max(0.,free);
}

}
