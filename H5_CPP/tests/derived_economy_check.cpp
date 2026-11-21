#include "../derived_economy.hpp"
#include "../storage.hpp"
#include "../treasury.hpp"
#include "supply_reference.hpp"
#include <random>
#include <stdexcept>
struct Tile {
    int owner{};bool water{};hoi5::Terrain natural{};
    double movementCost=1.,population=10000.,supply{};
    std::array<hoi5::BuildingCoverage,hoi5::buildingCount> buildings{};
    std::vector<hoi5::Deposit> deposits;
    std::vector<std::string_view> industries;
};
struct Profile {double population=1000000.,industryEfficiency=1.,scale=1.;};
void check(bool ok){if(!ok) throw std::runtime_error("derived economy parity");}
int main() {
    using namespace hoi5;
    std::mt19937 rng(146591);std::vector<Tile> tiles(900);
    std::vector<Profile> countries(6);std::vector<ProductionPlan> plans(6,{{"steel",20}});
    std::vector<int> capitals;
    for(int c=0;c<6;++c) capitals.push_back(c*150);
    for(int i=0;i<900;++i) {
        auto& t=tiles[i];t.owner=i/150;t.water=rng()%13==0;t.movementCost=1.+rng()%5;
        t.buildings[rng()%buildingCount].area=(rng()%100)/100.;
        t.buildings[industry].area=.2;
    }
    tiles[10].water=true;tiles[10].natural.water=1.;tiles[10].deposits.push_back({"phosphorite",10.,100000.});
    tiles[11].water=false;tiles[11].natural.water=0.;tiles[11].buildings[port].area=.8;
    DerivedEconomyIndex<Tile> index;SimulationWorkers workers(3);
    for(int iteration=0;iteration<30;++iteration) {
        index.scan(tiles,countries,plans);
        if(iteration==1) check(std::ranges::none_of(index.dirty,[](auto x){return x;}));
        for(int c=0;c<6;++c) {
            check(storageCapacity(tiles,c)==storageCapacity(tiles,c,&index.territory[c]));
            check(monthlyTreasury(tiles,c,1e6).balance()==monthlyTreasury(tiles,c,1e6,&index.territory[c]).balance());
            const auto a=buildProduction(tiles,30,c,1e6,{},&plans[c]);
            const auto b=buildProduction(tiles,30,c,1e6,{},&plans[c],1.,&index.territory[c],&index.offshore);
            check(a.totalPower==b.totalPower);
            for(int s=0;s<productionStages;++s) check(a[s].inputs==b[s].inputs && a[s].outputs==b[s].outputs);
        }
        auto reference=tiles,parallel=tiles;
        reference::originalSupply(std::span(reference),30,capitals);
        recalculateSupply(std::span(parallel),30,capitals,&workers,&index.territory);
        recalculateSupply(std::span(tiles),30,capitals,&workers,&index.territory,&index.supplyDirty);
        for(int i=0;i<900;++i) check(reference[i].supply==parallel[i].supply && reference[i].supply==tiles[i].supply);
        index.commit(countries,plans);
        if(iteration>0) {
            auto& t=tiles[rng()%900];t.owner=rng()%6;t.buildings[warehouse].area+=.1;t.movementCost+=.1;
            tiles[rng()%900].buildings[industry].health*=.9;
            tiles[rng()%900].population+=10;
            plans[rng()%6][0].power+=1;
        }
    }
}
