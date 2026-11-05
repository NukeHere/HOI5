#pragma once

#include "world_generation.hpp"

#include <limits>
#include <string_view>
#include <vector>

namespace hoi5 {

inline std::string_view biome(const Terrain& tile) {
    if (tile.water > .5) {
        if (tile.lake) return "lake";
        if (tile.water > .9) return tile.elevation < .15 ? "deep_ocean" : "ocean";
        return "shallow_water";
    }
    if (tile.water > .2 && tile.trees > .3) {
        if (tile.temperature > .6) return "mangrove";
        if (tile.temperature > .3) return "swamp";
        return "bog";
    }
    if (tile.temperature < .35 && (tile.ridge > .75 || (tile.elevation > .7 && tile.snow >= .25)))
        return "snowy_mountains";
    if (tile.ridge > .7 || tile.rock > .7) return "mountains";
    if (tile.ridge > .4 || tile.rock > .45) return "hills";

    const std::array covers{tile.sand, tile.snow, tile.trees, tile.grass};
    switch (std::max_element(covers.begin(), covers.end()) - covers.begin()) {
    case 0: return tile.temperature > .6 ? "desert" : "plains";
    case 1: return "tundra";
    case 2:
        if (tile.temperature > .7) return "tropical_rainforest";
        if (tile.temperature > .5) return "jungle";
        if (tile.temperature > .3) return "temperate_forest";
        return "taiga";
    default:
        if (tile.temperature > .7) return "savanna";
        return tile.temperature > .4 ? "grassland" : "tundra";
    }
}

struct Deposit {
    std::string_view resource;
    double depth;
    double mass;
};

inline double terrainMovementCost(const Terrain& tile) {
    const auto type = biome(tile);
    if (type == "deep_ocean" || type == "ocean") return std::numeric_limits<double>::infinity();
    if (type == "shallow_water" || type == "lake" || type == "swamp" || type == "bog" || type == "mangrove")
        return 3.;
    double cost = 1 + tile.ridge * 1.5 + tile.rock * 1.2 + tile.snow * .5;
    if (type == "mountains") cost += 1.5;
    else if (type == "snowy_mountains") cost += 2.;
    else if (type == "hills") cost += .75;
    return std::max(1.,cost);
}

struct GroundTerrainEffects { double attack, defense, speed; };

inline GroundTerrainEffects groundTerrainEffects(const Terrain& tile,double vehicleShare) {
    const auto clamp = [](double value) { return std::clamp(value,0.,1.); };
    const double vehicles = clamp(vehicleShare);
    const double highland = std::max(clamp(tile.ridge),clamp((tile.elevation-.45)/.55));
    const double wetland = clamp(tile.water*2.)*clamp((tile.moisture-.35)/.65);
    const double forest = clamp(tile.trees), rock = clamp(tile.rock), snow = clamp(tile.snow);
    const double openGround = clamp(tile.grass)*(1.-highland)*(1.-wetland);
    const double attackPenalty = highland*.16+forest*.13+rock*.06+snow*.08+wetland*.11;
    const double vehiclePenalty = highland*.09+forest*.10+wetland*.10+snow*.04;
    return {std::clamp(1.-attackPenalty-vehicles*vehiclePenalty+vehicles*openGround*.04,.55,1.04),
        1.+std::min(.15,highland*.07+forest*.08+rock*.04+snow*.03+wetland*.04),
        std::clamp(1.-forest*.09-snow*.12-wetland*.18-vehicles*(highland*.10+forest*.08+wetland*.09)
            +vehicles*openGround*.04,.60,1.04)};
}

inline std::vector<Deposit> generateDeposits(const Terrain& tile, std::uint32_t seed, int q, int r) {
    PythonSeed input{std::uint32_t(seed * 1000003u + q * 9176u + r * 131071u)};
    std::mt19937 rng(input);
    const auto random = [&] {
        const auto high = rng() >> 5;
        const auto low = rng() >> 6;
        return (high * 67108864. + low) / 9007199254740992.;
    };
    std::vector<Deposit> deposits;
    const auto add = [&](std::string_view name, double chance, int minDepth, int maxDepth, int minMass, int maxMass) {
        if (random() < chance) {
            const double depth = (minDepth + (maxDepth - minDepth) * random()) / 1000;
            const double mass = minMass + (maxMass - minMass) * random();
            deposits.push_back({name, depth, mass});
        }
    };

    const auto type = biome(tile);
    const bool mountains = type == "mountains" || type == "hills" || type == "snowy_mountains";
    const bool rocky = mountains || tile.rock > .35;
    const bool dry = type == "desert" || type == "plains" || tile.sand > .3 || tile.moisture < .3;
    const bool rareGeology = mountains || tile.ridge > .25 || tile.rock > .55;
    const bool peatland = type == "swamp" || type == "bog" || type == "tundra" || type == "taiga" || type == "lake"
        || (tile.moisture > .55 && tile.temperature < .55 && tile.elevation < .55);
    const bool tropicalLatex = tile.temperature > .55 && tile.moisture > .35
        && (tile.trees > .05 || type == "jungle" || type == "tropical_rainforest" ||
            type == "mangrove" || type == "savanna");

    if (rocky) {
        add("coal", .22, 100, 800, 5000, 50000);
        add("iron_ore", .32, 0, 1000, 10000, 200000);
        add("alloying_additives", .15, 100, 800, 1000, 20000);
        add("copper_ore", .18, 50, 1500, 5000, 100000);
        add("lead", .12, 100, 600, 3000, 50000);
        add("zinc", .12, 100, 600, 2000, 30000);
        add("nickel", .12, 200, 1000, 2000, 40000);
        add("silver", .04, 100, 800, 50, 5000);
        add("apatite", .09, 50, 300, 5000, 50000);
        add("graphite", .08, 50, 500, 1000, 20000);
        add("mica", .08, 50, 300, 500, 10000);
        if (rareGeology) {
            add("gold", .035, 100, 1000, 10, 1000);
            add("silver", .07, 100, 800, 50, 5000);
            add("rare_earth_metals", .045, 50, 500, 100, 5000);
            add("uranium", .05, 50, 500, 1000, 10000);
            add("quartz", .16, 10, 200, 1000, 30000);
        }
    }
    if (tile.temperature > .42 && tile.moisture > .45) add("bauxite", .34, 0, 50, 5000, 100000);
    if (tropicalLatex) add("rubber", .18, 0, 0, 1000, 30000);
    if (dry) {
        add("oil", .18, 500, 3000, 100000, 1000000);
        add("potash", .15, 100, 1000, 10000, 200000);
    }
    if (type == "mountains" || type == "hills" || type == "desert" || tile.temperature > .7)
        add("sulfur", .1, 0, 1500, 1000, 50000);
    if (std::any_of(deposits.begin(), deposits.end(), [](const auto& deposit) { return deposit.resource == "oil"; }))
        add("natural_gas", .6, 500, 4000, 50000, 500000);
    if (peatland) add("peat", .22, 0, 10, 1000, 20000);
    if (tile.water > .5) add("phosphorite", .1, 0, 100, 10000, 100000);
    return deposits;
}

}
