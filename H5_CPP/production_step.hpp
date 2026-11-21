#pragma once
#include "storage.hpp"
namespace hoi5 {
struct ProductionStepResult {
    Stockpile stocks,before,produced,output;
    std::array<double,productionStages> ratios{};
    std::array<double,2> delivered{},needed{};
    std::vector<ProductionLine> report;
};
inline ProductionStepResult calculateProductionStep(const Production& model,const Stockpile& capacity,
    const Stockpile& opening,const Stockpile& reserve,int hours) {
    ProductionStepResult result;result.stocks=opening;result.before=opening;
    auto& stocks=result.stocks;Stockpile held,heldBuckets;
    for(auto [key,amount]:reserve) {
        const double reserved=std::min(amount,value(stocks,key));stocks[key]-=reserved;
        held[key]=reserved;heldBuckets[storageBucket(key)]+=reserved;
    }
    result.ratios=runProduction(model,stocks,hours,[&](auto key,double amount) {
        result.output[key]+=amount;
        const double accepted=std::min(amount,std::max(0.,freeStorage(capacity,stocks,key)-value(heldBuckets,storageBucket(key))));
        stocks[key]+=accepted;result.produced[key]+=accepted;return accepted;
    },[&](auto key,double used,double need) {
        const int index=key=="food"?0:key=="consumer_goods"?1:-1;
        if(index>=0) {result.delivered[index]+=used;result.needed[index]+=need;}
    },&result.report);
    for(auto [key,amount]:held) stocks[key]+=amount;
    return result;
}
}
