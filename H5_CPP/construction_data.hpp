#pragma once

#include "market.hpp"

namespace hoi5 {
struct ConstructionSpec { Building building; std::string_view label; double work, money; Stockpile resources; };
inline const ConstructionSpec constructionSpecs[] = {
    {city, "\u0413\u043e\u0440\u043e\u0434", 520.0, 17500000, {{"construction_goods",36000}, {"steel",9000}, {"machinery",1200}, {"refined_fuel",650}}},
    {village, "\u0421\u0435\u043b\u043e", 160.0, 3000000, {{"construction_goods",7000}, {"steel",1000}, {"machinery",180}, {"refined_fuel",120}}},
    {farms, "\u041f\u043e\u043b\u044f/\u0444\u0435\u0440\u043c\u044b", 110.0, 1500000, {{"construction_goods",4500}, {"machinery",160}, {"refined_fuel",140}}},
    {mine, "\u0428\u0430\u0445\u0442\u0430", 240.0, 5000000, {{"construction_goods",11000}, {"steel",3500}, {"machinery",750}, {"refined_fuel",420}}},
    {oilGasRig, "\u041d\u0435\u0444\u0442\u0435\u0433\u0430\u0437\u043e\u0432\u0430\u044f \u0432\u044b\u0448\u043a\u0430", 260.0, 6500000, {{"construction_goods",13000}, {"steel",4600}, {"machinery",900}, {"refined_fuel",500}}},
    {industry, "\u041f\u0440\u043e\u043c\u0437\u043e\u043d\u0430", 340.0, 8000000, {{"construction_goods",22000}, {"steel",8000}, {"machinery",1800}, {"refined_fuel",520}}},
    {port, "\u041f\u043e\u0440\u0442", 420.0, 10000000, {{"construction_goods",20000}, {"steel",8500}, {"machinery",1250}, {"refined_fuel",850}}},
    {warehouse, "\u0421\u043a\u043b\u0430\u0434", 140.0, 2500000, {{"construction_goods",8000}, {"steel",1800}, {"machinery",220}, {"refined_fuel",120}}},
    {supplyDepot, "\u041f\u0443\u043d\u043a\u0442 \u0441\u043d\u0430\u0431\u0436\u0435\u043d\u0438\u044f", 120.0, 2200000, {{"construction_goods",6500}, {"steel",1200}, {"machinery",240}, {"refined_fuel",110}}},
    {fortification, "\u0423\u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0438\u044f / \u0431\u0443\u043d\u043a\u0435\u0440\u044b", 180.0, 4000000, {{"construction_goods",9000}, {"steel",2000}, {"machinery",180}, {"refined_fuel",80}}},
    {fuelStorage, "\u0422\u043e\u043f\u043b\u0438\u0432\u043e\u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0435", 190.0, 4000000, {{"construction_goods",12000}, {"steel",4800}, {"machinery",650}, {"refined_fuel",260}}},
    {refinery, "\u041d\u041f\u0417", 460.0, 12000000, {{"construction_goods",28000}, {"steel",11000}, {"machinery",2600}, {"refined_fuel",900}}},
    {airbase, "\u0410\u044d\u0440\u043e\u0434\u0440\u043e\u043c", 360.0, 9500000, {{"construction_goods",18000}, {"steel",7500}, {"machinery",1100}, {"electronics",240}, {"refined_fuel",420}}},
    {fieldHelipad, "\u041f\u043e\u043b\u0435\u0432\u0430\u044f \u0432\u0435\u0440\u0442\u043e\u043b\u0435\u0442\u043d\u0430\u044f \u043f\u043b\u043e\u0449\u0430\u0434\u043a\u0430", 42.0, 450000, {{"construction_goods",1300}, {"steel",260}, {"field_supplies",140}, {"refined_fuel",40}}},
};
}
