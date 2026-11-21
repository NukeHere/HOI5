#include "../production.hpp"
#include "../market_data.hpp"
#include "../storage.hpp"
#include <iostream>
#include <random>
#include <stdexcept>
using namespace hoi5;
static void equal(const Stockpile& a,const Stockpile& b) {
    for(auto [key,n]:a) if(n!=value(b,key)) throw std::runtime_error("Forecast value differs");
    for(auto [key,n]:b) if(n!=value(a,key)) throw std::runtime_error("Forecast value differs");
}
int main() {
    std::mt19937 rng(918273);
    for(int fixture=0;fixture<12;++fixture) {
        Production model;model.nationalPlan=fixture!=0;
        model.passive[raw].outputs={{"oil",450.},{"food",1500.},{"iron_ore",1100.},{"coal",800.},{"quartz",350.},{"natural_gas",700.},{"sulfur",400.}};
        model.passive[semiFinished].inputs={{"oil",500.}};
        model.passive[semiFinished].outputs={{"refined_fuel",360.},{"chemicals",110.}};
        model.passive[upkeep].inputs={{"food",1400.},{"consumer_goods",400.},{"construction_goods",500.}};
        if(model.nationalPlan) for(const auto& recipe:recipes) if(recipe.building==industry) {
            ProductionLine line;line.recipe=recipe.id;line.plannedUnits=recipe.rate*.04;
            for(auto [key,a]:recipe.inputs) line.inputs[key]=a*line.plannedUnits;
            for(auto [key,a]:recipe.outputs) line.outputs[key]=a*line.plannedUnits;
            model.lines.push_back(line);
        }
        else static_cast<std::array<ProductionFlows,productionStages>&>(model)=model.passive;
        Stockpile reference,fast;
        for(auto [key,p]:TRADE_BASE_PRICES) reference[key]=fixture%3==0?0.:double(rng()%100);
        fast=reference;ForecastProductionStepper stepper(model,fast);
        for(int tick=0;tick<120;++tick) {
            Stockpile referenceUsed,fastUsed,referenceOutput,fastOutput;
            std::vector<ProductionLine> report;
            const auto add=[&](Stockpile& stock,Stockpile& outputs,auto key,double amount) {
                double occupied=0.;for(auto [k,n]:stock) if(storageBucket(k)==storageBucket(key)) occupied+=n;
                const double accepted=std::min(amount,std::max(0.,1000.-occupied));stock[key]+=accepted;outputs[key]+=accepted;return accepted;
            };
            const auto a=runProduction(model,reference,6,[&](auto key,double n){return add(reference,referenceOutput,key,n);},[&](auto key,double n,double){referenceUsed[key]+=n;},&report);
            const auto b=stepper.run(fast,[&](auto key,double n){return add(fast,fastOutput,key,n);},[&](auto key,double n,double){fastUsed[key]+=n;});
            if(a!=b) throw std::runtime_error("Forecast passive ratios differ");
            equal(reference,fast);equal(referenceUsed,fastUsed);equal(referenceOutput,fastOutput);
            if(report.size()!=stepper.actualUnits.size()) throw std::runtime_error("Forecast line count differs");
            for(std::size_t i=0;i<report.size();++i) if(report[i].actualUnits!=stepper.actualUnits[i]) throw std::runtime_error("Forecast output differs");
        }
    }
    std::cout<<"Exact 120-step forecast parity: shortages, empty stocks, chains, storage, civilian upkeep, legacy mode and all recipes passed\n";
}
