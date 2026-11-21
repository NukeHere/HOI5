#include "../production.hpp"
#include <iostream>
#include <random>
#include <stdexcept>
using namespace hoi5;
static void require(bool ok) {if(!ok) throw std::runtime_error("Compiled production graph/balance regression");}
static Stockpile referenceClose(const Stockpile& use,const Stockpile& base) {
    Stockpile demand=use,units;
    for(int pass=0;pass<12;++pass) {
        Stockpile next=use;units.clear();
        for(const auto& recipe:recipes) if(recipe.building==industry && recipe.technology.empty() && !recipe.outputs.empty()) {
            double n=0.;for(auto [key,yield]:recipe.outputs) if(yield>0) n=std::max(n,std::max(0.,value(demand,key)-value(base,key))/yield);
            units[recipe.id]=n;for(auto [key,a]:recipe.inputs) next[key]+=a*n;
        }
        demand=std::move(next);
    }
    Stockpile powers;for(const auto& r:recipes) if(r.building==industry && r.rate>0 && r.powerCost>0) powers[r.id]=value(units,r.id)*r.powerCost/r.rate;
    return powers;
}
int main() {
    const auto& graph=productionGraph();require(graph.acyclic);
    std::mt19937 rng(146591);
    for(int fixture=0;fixture<64;++fixture) {
        Stockpile use,base;
        for(auto key:graph.keys) {use[key]=double(rng()%10000);base[key]=double(rng()%4000);}
        auto expected=referenceClose(use,base),actual=graph.close(use,base);
        for(auto [key,a]:expected) require(std::abs(a-value(actual,key))<=1e-9*std::max(1.,a));
    }
    Production model;model.nationalPlan=true;
    model.passive[raw].outputs={{"iron_ore",10400.},{"coal",4160.},{"natural_gas",1000.},{"sulfur",1000.},{"quartz",1000.}};
    const auto add=[&](std::string_view id,double count) {
        const auto& r=*productionRecipe(id);ProductionLine line;line.recipe=id;line.plannedUnits=count;
        for(auto [key,a]:r.inputs) line.inputs[key]=a*count;
        for(auto [key,a]:r.outputs) line.outputs[key]=a*count;
        model.lines.push_back(line);
    };
    add("steel",5200.);add("chemicals",1000.);add("construction_goods",1000.);
    CompiledProductionBalance balance;balance.update(model);require(balance.rebuilds==1);
    Stockpile stock;auto output=balance.estimate(stock);
    require(value(output,"steel")==5200. && value(output,"construction_goods")==1000. && stock.empty());
    balance.update(model);require(balance.rebuilds==1);
    model.passive[raw].outputs["iron_ore"]=0.;balance.update(model);require(balance.rebuilds==2);
    output=balance.estimate(stock);require(value(output,"steel")==0. && value(output,"construction_goods")==0. && value(output,"chemicals")==1000.);
    stock["iron_ore"]=31200.;const auto before=stock;output=balance.estimate(stock);
    require(value(output,"steel")==5200. && value(output,"construction_goods")==1000. && before==stock && balance.rebuilds==2);
    stock.clear();model.passive[raw].outputs["iron_ore"]=10400.;balance.update(model);
    for(auto& [key,a]:model.lines.front().inputs) a*=.5;
    for(auto& [key,a]:model.lines.front().outputs) a*=.5;
    balance.update(model);output=balance.estimate(stock);require(value(output,"steel")==2600. && balance.rebuilds==4);
    std::cout<<"Cached DAG vs reference closure, full/blocked chains, stocks without recompilation, input/power invalidation and no stock mutation passed\n";
}
