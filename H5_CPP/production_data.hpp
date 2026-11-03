#pragma once

#include "market_clearing.hpp"

namespace hoi5 {

enum ProductionStage { raw, semiFinished, agriculture, finished, upkeep, productionStages };
struct ProductionFlows { Stockpile inputs, outputs; };
using Production = std::array<ProductionFlows, productionStages>;
struct Recipe {
    ProductionStage stage;
    Building building;
    std::string_view sector, technology;
    double rate;
    Stockpile inputs, outputs;
};

inline const Recipe recipes[] = {
    {semiFinished, industry, "metallurgy", "", 5200, {{"iron_ore",2.0}, {"coal",0.8}}, {{"steel",1.0}}},
    {semiFinished, refinery, "refining", "", 6200, {{"oil",1.0}}, {{"refined_fuel",0.72}, {"chemicals",0.22}}},
    {semiFinished, industry, "chemicals", "", 3600, {{"natural_gas",0.7}, {"sulfur",0.25}}, {{"chemicals",1.0}}},
    {semiFinished, industry, "chemicals", "", 2600, {{"chemicals",0.5}, {"phosphorite",0.4}, {"potash",0.3}}, {{"fertilizer",1.0}}},
    {semiFinished, industry, "electronics", "", 2600, {{"copper_ore",1.2}}, {{"copper_wire",1.0}}},
    {finished, industry, "consumer_goods", "", 3400, {{"food",0.4}, {"chemicals",0.25}, {"steel",0.15}}, {{"consumer_goods",1.0}}},
    {finished, industry, "machinery", "", 2800, {{"steel",0.9}, {"copper_wire",0.25}, {"chemicals",0.2}}, {{"machinery",1.0}}},
    {finished, industry, "vehicles", "", 1700, {{"steel",0.8}, {"machinery",0.45}, {"refined_fuel",0.2}}, {{"vehicles",1.0}}},
    {finished, industry, "electronics", "", 1600, {{"copper_wire",0.65}, {"rare_earth_metals",0.12}, {"chemicals",0.25}}, {{"electronics",1.0}}},
    {finished, industry, "construction_materials", "", 4400, {}, {{"construction_goods",1.0}}},
    {finished, industry, "weapons", "", 1200, {{"steel",0.8}, {"machinery",0.35}, {"chemicals",0.25}}, {{"weapons",1.0}}},
    {finished, industry, "shipbuilding", "", 800, {{"steel",1.4}, {"machinery",0.65}, {"refined_fuel",0.25}}, {{"ships",1.0}}},
};
inline const Stockpile lifeSupport = {{"food",8100}, {"consumer_goods",150}, {"construction_goods",100}, {"refined_fuel",260}, {"chemicals",95}, {"vehicles",10}, {"electronics",2}};
inline const Stockpile cityUpkeep = {{"construction_goods",2370}, {"machinery",120}, {"refined_fuel",260}};
inline const Stockpile villageUpkeep = {{"construction_goods",700}, {"machinery",45}, {"refined_fuel",80}};
struct Sector { std::string_view name; std::vector<ResourceWeight> weights; };
inline const Sector sectors[] = {
    {"metallurgy", {{"iron_ore",1.0}, {"coal",0.8}, {"alloying_additives",0.35}}},
    {"construction_materials", {}},
    {"chemicals", {{"natural_gas",0.9}, {"sulfur",0.85}, {"phosphorite",0.35}, {"apatite",0.35}, {"potash",0.35}}},
    {"machinery", {{"iron_ore",0.6}, {"copper_ore",0.35}, {"coal",0.25}}},
    {"vehicles", {{"iron_ore",0.45}, {"oil",0.3}, {"rubber",0.3}, {"bauxite",0.2}}},
    {"electronics", {{"copper_ore",0.85}, {"rare_earth_metals",0.75}, {"quartz",0.35}}},
    {"shipbuilding", {{"iron_ore",0.45}, {"oil",0.25}}},
    {"weapons", {{"iron_ore",0.55}, {"copper_ore",0.25}, {"sulfur",0.25}}},
};
inline const Stockpile mineWeights = {{"coal",1.0}, {"oil",1.0}, {"natural_gas",0.95}, {"peat",0.55}, {"iron_ore",1.0}, {"copper_ore",0.82}, {"bauxite",0.64}, {"sulfur",0.42}, {"phosphorite",0.4}, {"apatite",0.36}};
}
