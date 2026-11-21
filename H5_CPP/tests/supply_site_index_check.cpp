#include "../ai_supply.hpp"
#include <chrono>
#include <iostream>
#include <random>
#include <stdexcept>
int main() {
    using namespace hoi5;
    constexpr int width=150;
    std::mt19937 rng(146591);
    std::vector<BotSupplyPoint> points;std::vector<BotSupplyCandidate> candidates;
    for(int i=0;i<5000;++i) points.push_back({int(rng()%(width*width)),1.+rng()%20,(rng()%100)/100.,(rng()%40)/100.,.5+(rng()%40)/100.});
    for(int i=0;i<5000;++i) candidates.push_back({int(rng()%(width*width)),.5+(rng()%50)/100.,.8+(rng()%40)/100.});
    const auto begin=std::chrono::steady_clock::now();
    const auto fast=bestBotSupplySite(width,points,candidates);
    const double fastMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
    std::array<double,8> falloff{};for(int d=0;d<8;++d) falloff[d]=std::pow(.78,d);
    std::optional<BotSupplyChoice> reference;
    const auto slowBegin=std::chrono::steady_clock::now();
    for(auto candidate:candidates) {
        double gain=0.;
        for(auto p:points) {const int d=supplyHexDistance(candidate.tile,p.tile,width);if(d<=7) gain+=std::max(0.,std::min(p.target,candidate.strength*falloff[d]*(.42+.58*p.passability))-p.current)*p.weight;}
        gain*=candidate.multiplier;
        if(gain>.05 && (!reference || gain>reference->gain)) reference=BotSupplyChoice{gain,candidate.tile};
    }
    const double slowMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-slowBegin).count();
    if(!fast || !reference || fast->tile!=reference->tile || fast->gain!=reference->gain) throw std::runtime_error("Spatial supply index changed the exact result");
    std::cout<<"5000 points x 5000 sites: indexed="<<fastMs<<" ms reference="<<slowMs<<" ms; identical site and gain\n";
}
