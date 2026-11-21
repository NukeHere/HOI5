#pragma once
#include "production.hpp"
#include <utility>

namespace hoi5 {
template<class Tile> class DerivedEconomyIndex {
    struct Snapshot {
        int owner=-2;bool water{},sea{};
        double population{},movement{},agriculture{};
        decltype(std::declval<Tile>().buildings) buildings{};
        decltype(std::declval<Tile>().deposits) deposits;
    };
    std::vector<Snapshot> snapshots;
    std::vector<double> populations,efficiencies,scales;
    std::vector<ProductionPlan> plans;
    static bool sameBuildings(const auto& a,const auto& b) {
        return std::ranges::equal(a,b,[](const auto& x,const auto& y){return x.area==y.area && x.health==y.health;});
    }
    static bool sameDeposits(const auto& a,const auto& b) {
        return std::ranges::equal(a,b,[](const auto& x,const auto& y){return x.resource==y.resource && x.depth==y.depth && x.mass==y.mass;});
    }
    static bool samePlan(const ProductionPlan& a,const ProductionPlan& b) {
        return std::ranges::equal(a,b,[](auto x,auto y){return x.recipe==y.recipe && x.power==y.power;});
    }
public:
    std::vector<std::vector<int>> territory;
    std::vector<int> offshore;
    std::vector<unsigned char> dirty;
    std::vector<unsigned char> supplyDirty;
    bool supplyChanged{};
    void remember(int index,const Tile& tile) {
        auto& s=snapshots[index];s.owner=tile.owner;s.water=tile.water;s.sea=tile.natural.water>.55;
        s.population=tile.population;s.movement=tile.movementCost;s.agriculture=agricultureScore(tile.natural);
        s.buildings=tile.buildings;s.deposits=tile.deposits;
    }
    template<class Profile> void scan(const std::vector<Tile>& tiles,const std::vector<Profile>& countries,const std::vector<ProductionPlan>& currentPlans) {
        const auto count=countries.size();const bool fresh=snapshots.size()!=tiles.size();
        if(fresh) snapshots.assign(tiles.size(),{});
        territory.assign(count,{});offshore.clear();dirty.assign(count,fresh);supplyDirty.assign(count,fresh);supplyChanged=fresh;
        bool sharedSeaChanged=false;
        const auto mark=[&](int owner){if(owner>=0 && owner<int(count)) dirty[owner]=true;};
        for(int i=0;i<int(tiles.size());++i) {
            const auto& tile=tiles[i];auto& old=snapshots[i];
            if(tile.owner>=0 && tile.owner<int(count)) territory[tile.owner].push_back(i);
            if((tile.water || tile.natural.water>.55) && std::ranges::any_of(tile.deposits,[](const auto& d){return d.resource=="phosphorite";})) offshore.push_back(i);
            const bool ownership=old.owner!=tile.owner || old.water!=tile.water || old.sea!=(tile.natural.water>.55);
            const bool buildings=!sameBuildings(old.buildings,tile.buildings),deposits=!sameDeposits(old.deposits,tile.deposits);
            if(ownership || buildings || deposits || old.population!=tile.population || old.agriculture!=agricultureScore(tile.natural)) {
                mark(old.owner);mark(tile.owner);
                const double before=old.buildings[port].area*old.buildings[port].health,after=tile.buildings[port].area*tile.buildings[port].health;
                sharedSeaChanged|=before!=after || (ownership && (before>0 || after>0 || old.sea || tile.natural.water>.55 || old.water || tile.water)) || (deposits && (old.sea || old.water || tile.natural.water>.55 || tile.water));
            }
            bool supplyTileChanged=ownership || old.movement!=tile.movementCost;
            if(buildings) for(int b=0;b<buildingCount;++b) if(supplySourceWeights[b]!=0 &&
                (old.buildings[b].area!=tile.buildings[b].area || old.buildings[b].health!=tile.buildings[b].health)) supplyTileChanged=true;
            if(supplyTileChanged) {
                supplyChanged=true;
                for(int owner:{old.owner,tile.owner}) if(owner>=0 && owner<int(count)) supplyDirty[owner]=true;
            }
            if(ownership || buildings || deposits || old.population!=tile.population || old.agriculture!=agricultureScore(tile.natural) || old.movement!=tile.movementCost) remember(i,tile);
        }
        if(sharedSeaChanged) std::fill(dirty.begin(),dirty.end(),true);
        for(std::size_t i=0;i<count;++i) if(i>=populations.size() || populations[i]!=countries[i].population ||
            efficiencies[i]!=countries[i].industryEfficiency || scales[i]!=countries[i].scale ||
            i>=plans.size() || i>=currentPlans.size() || !samePlan(plans[i],currentPlans[i])) dirty[i]=true;
    }
    template<class Profile> void commit(const std::vector<Profile>& countries,const std::vector<ProductionPlan>& currentPlans) {
        populations.resize(countries.size());efficiencies.resize(countries.size());scales.resize(countries.size());
        for(std::size_t i=0;i<countries.size();++i) {populations[i]=countries[i].population;efficiencies[i]=countries[i].industryEfficiency;scales[i]=countries[i].scale;}
        plans=currentPlans;
    }
};
}
