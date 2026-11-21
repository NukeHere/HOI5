#pragma once

#include "production_data.hpp"
#include <set>
#include <functional>

namespace hoi5 {

template<class Tile>
std::vector<std::string_view> industryAllocation(const std::vector<Tile>& tiles, int size, int index,
                                                 double& consumerScore) {
    const auto& tile = tiles[index];
    const int q = index % size, r = index / size;
    const auto nearby = [&](int radius, auto value) {
        double total = 0;
        for (int dq = -radius; dq <= radius; ++dq) for (int dr = -radius; dr <= radius; ++dr) {
            const int distance = std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
            if (distance > radius || q+dq < 0 || q+dq >= size || r+dr < 0 || r+dr >= size) continue;
            const auto& other = tiles[(r+dr)*size+q+dq];
            if (other.owner == tile.owner) total += value(other) / std::max(1,distance);
        }
        return std::clamp(total,0.,1.);
    };
    const auto coverage = [&](int radius, Building building) {
        return nearby(radius,[&](const Tile& other) { return other.buildings[building].area; });
    };
    std::vector<ResourceWeight> scores;
    for (const auto& sector : sectors) {
        const auto score = [&](const Tile& other) { return resourceScore(other.deposits, sector.weights); };
        scores.emplace_back(sector.name, std::clamp(score(tile)+nearby(3,score)*.75,0.,1.));
    }
    scores.emplace_back("consumer_goods",0.);
    const auto score = [&](std::string_view key) -> double& {
        return std::find_if(scores.begin(),scores.end(),[&](const auto& item) { return item.first == key; })->second;
    };
    const double cityScore = coverage(3,city), villageScore = coverage(2,village);
    const double portScore = coverage(3,port), mineScore = coverage(2,mine), refineryScore = coverage(2,refinery);
    const double pass = 1 / tile.movementCost;
    score("consumer_goods") = consumerScore = std::clamp(.16+cityScore*.82+villageScore*.34+pass*.20,0.,1.);
    score("machinery") += cityScore*.28+mineScore*.24+pass*.14;
    score("vehicles") += cityScore*.20+portScore*.18+refineryScore*.14+pass*.12;
    score("metallurgy") += mineScore*.18;
    score("construction_materials") += cityScore*.16+mineScore*.10;
    score("chemicals") += refineryScore*.24+cityScore*.10;
    score("electronics") += cityScore*.30+pass*.08;
    score("shipbuilding") += portScore*.65;
    score("military") += cityScore*.12+score("metallurgy")*.14;
    for (auto& [key,value] : scores) value = std::clamp(value,0.,1.);
    std::stable_sort(scores.begin(),scores.end(),[](const auto& a,const auto& b) { return a.second > b.second; });
    std::vector allocation{scores.front().first};
    if (scores[1].second >= scores[0].second*.72) allocation.push_back(scores[1].first);
    if (scores[2].second >= scores[0].second*.88) allocation.push_back(scores[2].first);
    return allocation;
}

template<class Tile>
void assignStartingIndustry(std::vector<Tile>& tiles, int size, const std::vector<int>& land) {
    std::vector<std::pair<int,double>> industrial;
    double total = 0, consumer = 0;
    const auto consumerCoverage = [](const Tile& tile) {
        const auto& sectors = tile.industries;
        return std::find(sectors.begin(),sectors.end(),"consumer_goods") == sectors.end()
            ? 0. : tile.buildings[industry].area / sectors.size();
    };
    for (int index : land) {
        auto& tile = tiles[index];
        if (tile.buildings[industry].area <= 0) continue;
        double score = 0;
        tile.industries = industryAllocation(tiles,size,index,score);
        industrial.emplace_back(index,score);
        total += tile.buildings[industry].area;
        consumer += consumerCoverage(tile);
    }
    std::sort(industrial.begin(),industrial.end(),[&](const auto& a,const auto& b) {
        return std::tuple{-a.second,-tiles[a.first].buildings[industry].area,a.first%size,a.first/size}
             < std::tuple{-b.second,-tiles[b.first].buildings[industry].area,b.first%size,b.first/size};
    });
    for (const auto& [index,score] : industrial) {
        if (consumer >= total*.30) break;
        auto& tile = tiles[index];
        const double previous = consumerCoverage(tile);
        if (previous >= tile.buildings[industry].area*.45) continue;
        auto& allocation = tile.industries;
        std::erase(allocation,std::string_view("consumer_goods"));
        allocation.insert(allocation.begin(),"consumer_goods");
        if (allocation.size() > 2) allocation.resize(2);
        consumer += consumerCoverage(tile)-previous;
    }
}

template<class Tile>
void accumulateTileProduction(Production& result,const Tile& tile,
                              const std::set<std::string_view>& technologies) {
    const auto effective = [&](Building building) {
        const auto& b = tile.buildings[building];
        return b.area * b.health;
    };
    for (const auto& deposit : tile.deposits) {
        const bool liquid = deposit.resource == "oil" || deposit.resource == "natural_gas";
        const double area = effective(liquid ? oilGasRig : mine);
        if (area <= 0) continue;
        const double abundance = std::min(1.,std::log10(deposit.mass+1)/std::log10(1500001.));
        const auto found = mineWeights.find(deposit.resource);
        const double weight = found == mineWeights.end() ? .35 : found->second;
        result[raw].outputs[deposit.resource] += area * abundance *
            (liquid ? (.62+weight)*5600 : (.55+weight)*5200);
    }
    const double farmCoverage = effective(farms);
    if (farmCoverage > 0) {
        const double food = farmCoverage * agricultureScore(tile.natural) * 30000;
        result[raw].outputs["food"] += food;
        result[agriculture].inputs["fertilizer"] += farmCoverage*950;
        result[agriculture].outputs["food"] += food*.30;
    }
    for (const auto& recipe : recipes) {
        if (!recipe.technology.empty() && !technologies.contains(recipe.technology)) continue;
        double units = recipe.rate * effective(recipe.building);
        if (units <= 0) continue;
        if (recipe.building == industry) continue;
        for (const auto& [name,amount] : recipe.inputs) result[recipe.stage].inputs[name] += amount*units;
        for (const auto& [name,amount] : recipe.outputs) result[recipe.stage].outputs[name] += amount*units;
    }
    for (const auto& [name,amount] : cityUpkeep) result[upkeep].inputs[name] += effective(city)*amount;
    for (const auto& [name,amount] : villageUpkeep) result[upkeep].inputs[name] += effective(village)*amount;
}

inline const Recipe* productionRecipe(std::string_view id) {
    for (const auto& recipe : recipes) if (recipe.id == id) return &recipe;
    return nullptr;
}
template<class Tile>
double productionPower(const std::vector<Tile>& tiles,int country,double efficiency = 1.) {
    double power = 0;
    for (const auto& tile : tiles) if (tile.owner == country)
        power += std::max(0.,tile.buildings[industry].area)*std::clamp(tile.buildings[industry].health,0.,1.)*100.;
    return power*(std::isfinite(efficiency) ? std::max(0.,efficiency) : 0.);
}
inline ProductionPlan startingProductionPlan(double power) {
    const std::pair<std::string_view,double> shares[]{
        {"consumer_goods",.18},{"construction_goods",.17},{"steel",.16},
        {"chemicals",.09},{"copper_wire",.06},{"fertilizer",.05},
        {"machinery",.07},{"vehicles",.035},{"electronics",.025},
        {"infantry_equipment",.025},{"old_assault_rifles",.025},{"small_arms_ammo",.025},
        {"old_light_artillery",.01},{"old_light_aa_artillery",.01},{"old_ifv",.01},{"tank",.01},
        {"old_at_missiles",.01},{"field_supplies",.015},{"spare_parts",.015},
        {"light_artillery_ammo",.005},{"light_aa_ammo",.005},{"autocannon_ammo",.005},
        {"artillery_ammo",.003},{"tank_ammo",.003},{"anti_air_ammo",.004}};
    ProductionPlan result;
    double total = 0.;
    for (auto [key,share] : shares) total += share;
    for (auto [key,share] : shares) result.push_back({key,power*share/total});
    return result;
}
// National demand closure: quantities are monthly; transient orders are amortized by caller.
// Rebuild from end uses, rather than growing assignments or reading legacy tile sectors.
inline ProductionPlan demandProductionPlan(double power,const Production& passive,
                                           Stockpile endUse,const Stockpile& stocks,const Stockpile& recurrentSales = {}) {
    // Reserves and one-off orders may be postponed while stocks cover them; recurring
    // civilian upkeep below is never mistaken for another stock-replenishment order.
    for(auto& [key,amount]:endUse) amount=std::max(0.,amount+(amount*.5-value(stocks,key))/3.);
    for(auto [key,amount]:recurrentSales) endUse[key]+=std::max(0.,amount);
    Stockpile baseOutput;
    const double baseFood=value(passive[raw].outputs,"food");
    const double foodNeed=value(passive[upkeep].inputs,"food")+value(passive[upkeep].inputs,"consumer_goods")*.4;
    const double bonusFood=value(passive[agriculture].outputs,"food");
    const double fertilizerShare=bonusFood>0?std::clamp((foodNeed*1.02-baseFood)/bonusFood,0.,1.):0.;
    for (int index=0;index<productionStages;++index) {
        const auto& stage=passive[index];double supported=1.;
        for(auto [key,amount]:stage.inputs) {
            const double wanted=index==agriculture?amount*fertilizerShare:amount;
            endUse[key]+=wanted;
            if(amount>0) supported=std::min(supported,(value(baseOutput,key)+value(stocks,key)/3.)/amount);
        }
        // A nominal refinery without oil must not suppress a feasible chemical recipe.
        for(auto [key,amount]:stage.outputs) baseOutput[key]+=amount*std::clamp(supported,0.,1.);
    }
    const auto close=[&](const Stockpile& use) {
        Stockpile demand=use,units;
        for(int pass=0;pass<12;++pass) {
            Stockpile next=use;units.clear();
            for(const auto& recipe:recipes) {
                if(recipe.building!=industry || !recipe.technology.empty() || recipe.outputs.empty()) continue;
                double count=0.;
                for(auto [key,yield]:recipe.outputs) if(yield>0)
                    count=std::max(count,std::max(0.,value(demand,key)-value(baseOutput,key))/yield);
                units[recipe.id]=count;
                for(auto [key,amount]:recipe.inputs) next[key]+=amount*count;
            }
            demand=std::move(next);
        }
        Stockpile powers;
        for(const auto& recipe:recipes) if(recipe.building==industry && recipe.rate>0 && recipe.powerCost>0)
            powers[recipe.id]=value(units,recipe.id)*recipe.powerCost/recipe.rate;
        return powers;
    };
    const auto sum=[](const Stockpile& powers){double total=0.;for(auto [key,amount]:powers) total+=amount;return total;};
    const auto wanted=close(endUse);Stockpile assigned=wanted;
    if(sum(wanted)>power) {
        // Protect a positive construction-material flow and its entire input chain before
        // optional reserves/luxuries. Otherwise upkeep can consume every unit forever.
        Stockpile bootstrap;
        const double upkeepGoods=value(passive[upkeep].inputs,"construction_goods");
        bootstrap["construction_goods"]=std::max(upkeepGoods*1.25,
            std::min(value(endUse,"construction_goods"),upkeepGoods*1.6));
        const double machines=upkeepGoods>0?150.*std::clamp(upkeepGoods/1000.,.5,2.4):0.;
        bootstrap["machinery"]=std::max(0.,machines-value(stocks,"machinery")/3.);
        assigned=close(bootstrap);
        const double reserved=sum(assigned);
        if(reserved>power) for(auto& [key,amount]:assigned) amount*=std::max(0.,power)/reserved;
        else {
            // Civilian recurring consumption must not compete with arbitrary equipment
            // reserve orders: losing household goods also destroys political/tax stability.
            Stockpile civilian=bootstrap;
            for(auto [key,amount]:passive[upkeep].inputs)
                civilian[key]=std::max(value(civilian,key),amount);
            const auto fit=[&](const Stockpile& floor,const Stockpile& target) {
                double low=0.,high=1.;
                for(int pass=0;pass<12;++pass) {
                    const double fraction=(low+high)*.5;Stockpile blended=floor;
                    for(auto [key,amount]:target) blended[key]+=std::max(0.,amount-value(floor,key))*fraction;
                    auto candidate=close(blended);
                    if(sum(candidate)<=power) {low=fraction;assigned=std::move(candidate);} else high=fraction;
                }
            };
            auto basic=close(civilian);
            if(sum(basic)>power) fit(bootstrap,civilian);
            else {assigned=std::move(basic);fit(civilian,endUse);}
        }
    }
    ProductionPlan result;
    for(const auto& recipe:recipes) if(recipe.building==industry && value(assigned,recipe.id)>1e-8)
        result.push_back({recipe.id,value(assigned,recipe.id)});
    return result;
}

inline bool setProductionPower(ProductionPlan& plan,std::string_view id,double power) {
    const auto* recipe = productionRecipe(id);
    if (!recipe || recipe->building != industry || !std::isfinite(power) || power < 0) return false;
    for (auto& line : plan) if (line.recipe == id) { line.power = power; return true; }
    plan.push_back({recipe->id,power}); return true;
}
inline bool moveProductionLine(ProductionPlan& plan,std::size_t from,std::size_t to) {
    if (from >= plan.size() || to >= plan.size()) return false;
    auto line = plan[from]; plan.erase(plan.begin()+from); plan.insert(plan.begin()+to,line); return true;
}

template<class Tile>
Production buildProduction(const std::vector<Tile>& tiles, int size, int country, double population,
                           const std::set<std::string_view>& technologies,
                           const ProductionPlan* plan = nullptr,double efficiency = 1.) {
    Production result;
    for (const auto& tile : tiles)
        if (tile.owner == country) accumulateTileProduction(result,tile,technologies);
    for (int index = 0; index < int(tiles.size()); ++index) {
        const auto& sea = tiles[index];
        if (!sea.water && sea.natural.water <= .55) continue;
        if (sea.owner >= 0 && sea.owner != country) continue;
        const int q = index%size, r = index/size, shift = r%2;
        double coverage = 0.;
        int beneficiary = -1;
        for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
            {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
        }}) {
            if (q+dq < 0 || q+dq >= size || r+dr < 0 || r+dr >= size) continue;
            const auto& coast = tiles[(r+dr)*size+q+dq];
            if (coast.water || coast.natural.water > .55 || coast.owner < 0 ||
                (sea.owner >= 0 && coast.owner != sea.owner)) continue;
            const auto& dock = coast.buildings[port];
            if (dock.area*dock.health > coverage) {
                coverage = dock.area*dock.health;
                beneficiary = coast.owner;
            }
        }
        if (beneficiary != country) continue;
        for (const auto& deposit : sea.deposits)
            if (deposit.resource == "phosphorite")
                result[raw].outputs[deposit.resource] += coverage*.95*5200*
                    std::min(1.,std::log10(deposit.mass+1)/std::log10(1500001.));
    }
    for (const auto& [name,amount] : lifeSupport) result[upkeep].inputs[name] += population/1e6*amount;
    result.passive = static_cast<const std::array<ProductionFlows,productionStages>&>(result);
    result.nationalPlan = true;
    result.totalPower = result.unusedPower = productionPower(tiles,country,efficiency);
    const auto defaults = plan ? ProductionPlan{} : startingProductionPlan(result.totalPower);
    for (const auto& assignment : plan ? *plan : defaults) {
        ProductionLine line; line.recipe = assignment.recipe;
        line.assignedPower = std::isfinite(assignment.power) ? std::max(0.,assignment.power) : 0.;
        const auto* recipe = productionRecipe(line.recipe);
        if (!recipe || recipe->building != industry) {
            line.limits.push_back("invalid_recipe"); result.lines.push_back(line); continue;
        }
        if (!recipe->technology.empty() && !technologies.contains(recipe->technology)) {
            line.limits.push_back("technology"); result.lines.push_back(line); continue;
        }
        line.availablePower = std::min(line.assignedPower,result.unusedPower);
        result.unusedPower -= line.availablePower;
        if (line.availablePower < line.assignedPower) line.limits.push_back("capacity");
        line.plannedUnits = recipe->rate*line.availablePower/recipe->powerCost;
        for (auto [key,amount] : recipe->inputs) {
            line.inputs[key] = amount*line.plannedUnits;
            result[recipe->stage].inputs[key] += amount*line.plannedUnits;
        }
        for (auto [key,amount] : recipe->outputs) {
            line.outputs[key] = amount*line.plannedUnits;
            result[recipe->stage].outputs[key] += amount*line.plannedUnits;
        }
        result.lines.push_back(std::move(line));
    }
    return result;
}

template<class AddStock>
std::array<double,productionStages> runPassiveProduction(const Production& production, Stockpile& stock,
                                                  int hours, AddStock addStock,
    const std::function<void(std::string_view,double,double)>& consume = {}) {
    std::array<double,productionStages> ratios{};
    const double fraction = hours / 720.;
    for (int stage = 0; stage < productionStages; ++stage) {
        const auto& [inputs,outputs] = production[stage];
        double ratio = 1;
        for (const auto& [name,amount] : inputs)
            if (amount > 0) ratio = std::min(ratio,stock[name]/(amount*fraction));
        ratio = std::clamp(ratio,0.,1.);
        ratios[stage] = ratio;
        for (const auto& [name,amount] : inputs) {
            auto& stored = stock[name];
            if (stage == upkeep && consume) consume(name,std::min(stored,amount*fraction),amount*fraction);
            stored = std::max(0.,stored-amount*fraction*(stage == upkeep ? 1. : ratio));
        }
        for (const auto& [name,amount] : outputs) addStock(name,amount*fraction*ratio);
    }
    return ratios;
}

template<class AddStock>
std::array<double,productionStages> runProduction(const Production& production,Stockpile& stock,
    int hours,AddStock addStock,
    const std::function<void(std::string_view,double,double)>& consume = {},
    std::vector<ProductionLine>* report = nullptr) {
    if (report) report->clear();
    if (hours <= 0) return {};
    if (!production.nationalPlan) return runPassiveProduction(production,stock,hours,addStock,consume);
    const double fraction = hours/720.;
    Stockpile demand, pending;
    auto lines = production.lines;
    for (const auto& line : lines) for (auto [key,amount] : line.inputs) demand[key] += amount*fraction;
    Stockpile ratios;
    for (auto [key,amount] : demand) ratios[key] = amount > 0 ? std::clamp(value(stock,key)/amount,0.,1.) : 1.;
    for (auto& line : lines) {
        double ratio = 1;
        for (auto [key,amount] : line.inputs) if (amount > 0 && ratios[key] < 1.) {
            ratio = std::min(ratio,ratios[key]); line.limits.push_back(key);
        }
        line.actualUnits = line.plannedUnits*fraction*ratio;
        for (auto [key,amount] : line.inputs) {
            line.actualInputs[key] = amount*fraction*ratio;
            stock[key] = std::max(0.,stock[key]-line.actualInputs[key]);
        }
        for (auto [key,amount] : line.outputs) {
            line.actualOutputs[key] = amount*fraction*ratio;
            pending[key] += line.actualOutputs[key];
        }
    }
    Production passive;
    static_cast<std::array<ProductionFlows,productionStages>&>(passive) = production.passive;
    auto stageRatios = runPassiveProduction(passive,stock,hours,[&](auto key,double amount) { pending[key] += amount; },consume);
    Stockpile acceptedRatio;
    for (auto [key,amount] : pending) {
        if constexpr (std::is_void_v<decltype(addStock(key,amount))>) {
            addStock(key,amount); acceptedRatio[key] = 1.;
        } else {
            const double accepted = std::clamp(double(addStock(key,amount)),0.,amount);
            acceptedRatio[key] = amount > 0 ? accepted/amount : 1.;
        }
    }
    for (auto& line : lines) for (auto [key,amount] : line.actualOutputs) {
        line.storedOutputs[key] = amount*acceptedRatio[key];
        if (acceptedRatio[key] < 1. && amount > 0) line.limits.push_back("storage");
    }
    if (report) *report = std::move(lines);
    return stageRatios;
}

}
