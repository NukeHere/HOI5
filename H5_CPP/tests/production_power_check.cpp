#include "../production.hpp"
#include "../division_data.hpp"
#include "../munition_data.hpp"
#include <iostream>
#include <stdexcept>

struct Tile {
    int owner = 0;
    bool water = false;
    hoi5::Terrain natural{};
    double movementCost = 1.;
    std::array<hoi5::BuildingCoverage,hoi5::buildingCount> buildings{};
    std::vector<hoi5::Deposit> deposits;
    std::vector<std::string_view> industries;
};
void check(bool ok,const char* message) { if (!ok) throw std::runtime_error(message); }
bool close(double a,double b) { return std::abs(a-b) < 1e-7; }
int main() {
    using namespace hoi5;
    std::vector<Tile> tiles(1);
    tiles[0].buildings[industry].area = 1.;
    ProductionPlan plan{{"steel",60},{"construction_goods",50}};
    const auto build = [&] { return buildProduction(tiles,1,0,0,{},&plan); };
    auto model = build();
    check(close(model.totalPower,100) && close(model.lines[1].availablePower,40),"100/110 power");
    check(moveProductionLine(plan,1,0),"move API");
    check(close(build().lines[1].availablePower,50),"priority");
    tiles[0].buildings[industry].health = .4;
    check(close(build().lines[0].availablePower,40) && close(build().lines[1].availablePower,0),"damage");
    tiles[0].owner = 1;
    check(close(build().totalPower,0),"ownership loss");
    check(close(buildProduction(tiles,1,1,0,{},&plan).totalPower,40),"ownership gain");
    tiles[0].owner = 0; tiles[0].buildings[industry].health = 1;
    check(close(buildProduction(tiles,1,0,0,{},&plan,1.2).totalPower,120),"modifier");
    check(!setProductionPower(plan,"steel",-1) && !setProductionPower(plan,"steel",NAN),"invalid power");
    check(!setProductionPower(plan,"oil_refining",10),"refinery cannot duplicate");
    check(!setProductionPower(plan,"unknown",10),"unknown recipe");

    plan = {{"steel",50},{"copper_wire",50}};
    Stockpile stock{{"copper_ore",1000}};
    model = build();
    std::vector<ProductionLine> report;
    runProduction(model,stock,6,[&](auto key,double amount) { stock[key] += amount; },{},&report);
    check(close(value(stock,"steel"),0) && value(stock,"copper_wire") > 0,"unrelated shortage");
    check(report[0].actualUnits == 0 && !report[0].limits.empty(),"shortage report");

    plan = {{"machinery",40},{"old_assault_rifles",40}};
    stock = {{"steel",1},{"copper_wire",100},{"chemicals",100}};
    model = build();
    auto reversedStock = stock;
    runProduction(model,stock,6,[&](auto key,double amount) { stock[key] += amount; });
    moveProductionLine(plan,1,0); model = build();
    runProduction(model,reversedStock,6,[&](auto key,double amount) { reversedStock[key] += amount; });
    for (auto [key,amount] : stock) check(close(amount,value(reversedStock,key)),"row order dependence");
    for (auto [key,amount] : stock) check(amount >= 0,"negative stock");

    plan = {{"steel",50},{"machinery",50}};
    stock = {{"iron_ore",1000},{"coal",1000},{"copper_wire",1000},{"chemicals",1000}};
    model = build();
    runProduction(model,stock,6,[&](auto key,double amount) { stock[key] += amount; });
    check(value(stock,"steel") > 0 && value(stock,"machinery") == 0,"same tick chain");
    runProduction(model,stock,6,[&](auto key,double amount) { stock[key] += amount; });
    check(value(stock,"machinery") > 0,"next tick chain");
    // Filling a warehouse must not hide the distinction between production and storage.
    plan = {{"construction_goods",100}}; model = build(); stock={{"steel",1000},{"chemicals",1000},{"quartz",1000}};
    runProduction(model,stock,6,[](auto,double) { return 0.; },{},&report);
    check(report[0].actualUnits > 0 && value(report[0].storedOutputs,"construction_goods") == 0,
          "storage acceptance report");
    check(std::ranges::find(report[0].limits,"storage") != report[0].limits.end(),"storage reason");
    plan.clear(); check(build().lines.empty() && close(build().unusedPower,100),"empty plan retained");
    tiles[0].buildings[oilGasRig].area = 1.;
    tiles[0].buildings[refinery].area = 1.;
    tiles[0].deposits = {{"oil",.1,1500000}};
    model = build(); stock.clear();
    runProduction(model,stock,6,[&](auto key,double amount) { stock[key] += amount; });
    check(value(stock,"oil") > 0 && value(stock,"refined_fuel") == 0,"empty plan snapshot");
    runProduction(model,stock,6,[&](auto key,double amount) { stock[key] += amount; });
    check(value(stock,"refined_fuel") > 0,"profile refinery next tick");
    plan = {{"unknown",100},{"steel",50},{"steel",50}};
    model = build(); check(close(model.unusedPower,0) && model.lines[2].availablePower == 50,"independent duplicate rows");
    stock={{"iron_ore",1000},{"coal",1000}};
    runProduction(model,stock,6,[&](auto key,double amount) { stock[key] += amount; },{},&report);
    check(report[1].actualUnits > 0 && close(report[1].actualUnits,report[2].actualUnits),"duplicate recipe produces independently");
    check(close(productionPower(tiles,0),100),"specializations ignored");
    for (const auto& recipe : recipes) {
        check(!recipe.id.empty(),"stable recipe id");
        check(!recipe.inputs.contains("weapons") && !recipe.outputs.contains("weapons"),"removed weapons");
    }
    for (const auto& type : divisionTemplates) {
        check(!type.capacity.contains("weapons"),"division weapons removed");
        for (auto [key,amount] : type.capacity) {
            check(TRADE_BASE_PRICES.contains(key),"equipment price");
            check(storageBucket(key) != "raw","equipment storage bucket");
            if (key != "refined_fuel") check(productionRecipe(key),"equipment recipe");
        }
    }
    for (const auto& type : aircraftTypes) check(productionRecipe(type.key),"aircraft recipe");
    for (const auto& item : munitions) check(productionRecipe(item.key),"munition recipe");
    for (const auto& type : defenseClasses) check(productionRecipe(type.key),"defense recipe");
    AirLayer air;
    double money = 1e8;
    Stockpile materials{{"medium_range_sam",1},{"construction_goods",40},{"anti_air_ammo",18}};
    check(air.enqueueDefense(0,2,money,materials) == "Оплачено производство ПВО: 48 часов","finished SAM deployment");
    check(materials["medium_range_sam"] == 0 && materials["anti_air_ammo"] == 0,"SAM charged once");
    check(!TRADE_BASE_PRICES.contains("weapons"),"market weapons removed");
    for(auto key : {"tank","old_ifv","light_fighter","medium_range_sam","heavy_strategic_missile"})
        check(Market::orderStep(key,false,true)==1 && Market::orderStep(key)==10 && Market::orderStep(key,true)==100,"individual trade steps");
    for(auto key : {"gold","silver","uranium","anti_air_ammo","medium_air_to_air_missile"})
        check(Market::orderStep(key,false,true)==10 && Market::orderStep(key)==100 && Market::orderStep(key,true)==1000,"medium trade steps");
    for(auto key : {"food","steel","chemicals","construction_goods","small_arms_ammo"})
        check(Market::orderStep(key,false,true)==100 && Market::orderStep(key)==1000 && Market::orderStep(key,true)==10000,"bulk trade steps");
    Production oilStarved;
    oilStarved[semiFinished].inputs["oil"]=100.;
    oilStarved[semiFinished].outputs["chemicals"]=1000.;
    const auto chemicalFallback=demandProductionPlan(1000.,oilStarved,{{"chemicals",500.}},{});
    check(std::ranges::any_of(chemicalFallback,[](const auto& line){return line.recipe=="chemicals" && line.power>0;}),
          "unfed passive refinery cannot hide chemical demand");
    Production maintenance;
    maintenance[upkeep].inputs={{"construction_goods",1000.},{"chemicals",1000.},{"consumer_goods",1000.}};
    const auto recovery=demandProductionPlan(60.,maintenance,{},{});
    double recoveryPower=0.,constructionFlow=0.;
    for(auto line:recovery) {recoveryPower+=line.power;if(line.recipe=="construction_goods") constructionFlow+=line.power*44.;}
    check(recoveryPower<=60.+1e-7 && constructionFlow>1000.,"scarce power preserves material surplus for rebuilding");
    Production civilians;
    civilians[upkeep].inputs["consumer_goods"]=1000.;
    const auto competingArmy=demandProductionPlan(60.,civilians,{{"tank",1e9}},{});
    double householdFlow=0.,competingPower=0.;
    for(auto line:competingArmy) {competingPower+=line.power;if(line.recipe=="consumer_goods") householdFlow+=line.power*34.;}
    check(competingPower<=60.+1e-7 && householdFlow>=1000.-1e-6,
          "civilian recurring goods precede an oversized military reserve order");
    Production fed;
    fed[raw].outputs["food"]=1100.;fed[upkeep].inputs["food"]=1000.;
    fed[agriculture].inputs["fertilizer"]=100.;fed[agriculture].outputs["food"]=330.;
    const auto foodPlan=demandProductionPlan(100.,fed,{},{});
    check(std::ranges::none_of(foodPlan,[](const auto& line){return line.recipe=="fertilizer" && line.power>0;}),
          "optional fertilizer cannot crowd out recovery when base food is covered");
    const auto exportPlan=demandProductionPlan(1000.,{}, {},{{"steel",1e9}},{{"steel",1000.}});
    check(std::ranges::any_of(exportPlan,[](const auto& line){return line.recipe=="steel" && line.power>0;}),
        "recurring commercial orders survive a large inventory");
    std::cout << "Production capacity, priority, inputs, chains and ownership passed\n";
}
