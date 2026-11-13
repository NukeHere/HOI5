#pragma once

#include "production.hpp"

namespace hoi5 {

inline constexpr std::array<std::string_view,4> storageBuckets{"raw","semi_finished","finished","fuel"};

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
Stockpile tileStorageCapacity(const Tile& tile) {
    constexpr int rates[][buildingCount] = {
        {520000,180000,1050000,240000,280000},
        {470000,140000,820000,210000,240000},
        {560000,200000,760000,190000,220000},
        {180000,35000,0,120000,220000,3200000,850000,420000}
    };
    Stockpile result;
    for (std::size_t bucket = 0; bucket < storageBuckets.size(); ++bucket) {
        double capacity = 0;
        for (int b = 0; b < buildingCount; ++b)
            capacity += tile.buildings[b].area * tile.buildings[b].health * rates[bucket][b];
        result[storageBuckets[bucket]] = capacity;
    }
    return result;
}

inline Stockpile enforceStorageCapacity(Stockpile& stocks,const Stockpile& capacity) {
    Stockpile used;
    for (const auto& [resource,amount] : stocks) used[storageBucket(resource)] += std::max(0.,amount);
    Stockpile retention;
    for (auto bucket : storageBuckets) {
        const double total = value(used,bucket);
        retention[bucket] = total > 0. ? std::clamp(value(capacity,bucket)/total,0.,1.) : 1.;
    }
    Stockpile discarded;
    for (auto& [resource,amount] : stocks) {
        const auto bucket = storageBucket(resource);
        if (amount <= 0. || retention.at(bucket) == 1.) continue;
        const double retained = amount * retention.at(bucket);
        discarded[bucket] += amount-retained;
        amount = retained;
    }
    return discarded;
}

inline Stockpile distributeTileStockpile(const Stockpile& stocks,const Stockpile& nationalCapacity,
                                         const Stockpile& tileCapacity) {
    Stockpile result;
    for (const auto& [resource,amount] : stocks) {
        if (amount <= 0.) continue;
        const auto bucket = storageBucket(resource);
        const double total = value(nationalCapacity,bucket), local = value(tileCapacity,bucket);
        if (total > 0. && local > 0.) result[resource] = amount*(local/total);
    }
    return result;
}

template<class Tile>
Stockpile storageCapacity(const std::vector<Tile>& tiles,int country) {
    Stockpile result{{"raw",0},{"semi_finished",0},{"finished",0},{"fuel",0}};
    for (const auto& tile : tiles) {
        if (tile.owner != country) continue;
        for (const auto& [bucket,capacity] : tileStorageCapacity(tile)) result[bucket] += capacity;
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
