#pragma once

#include "treasury_data.hpp"

namespace hoi5 {

struct TreasuryFlows {
    double population{}, companies{}, government = 450000, social{}, infrastructure{};
    double pensions{}, children{}, disability{}, localServices{};
    double expenses() const { return government+social+infrastructure; }
    double balance() const { return population+companies-government-social-infrastructure; }
};

template<class Tile>
TreasuryFlows monthlyTreasury(const std::vector<Tile>& tiles,int owner,double population) {
    TreasuryFlows flows;
    flows.government += population/1e6*48000;
    for (const auto& tile : tiles) {
        if (tile.owner != owner) continue;
        if (!tile.water) flows.government += 3500;
        double weightedIncome = ruralIncome, totalWeight = 1;
        for (int building = 0; building < buildingCount; ++building) {
            const auto& b = tile.buildings[building];
            const double weight = b.area*populationIncomeWeights[building];
            weightedIncome += populationIncomeRates[building]*weight;
            totalWeight += weight;
            flows.companies += b.area*b.health*companyIncomeRates[building];
            flows.infrastructure += b.area*infrastructureUpkeep[building];
        }
        flows.population += tile.population/1e6 * weightedIncome/totalWeight;
        const double millions = tile.population/1e6;
        flows.pensions += millions*.16*230000;
        flows.children += millions*.23*100000;
        flows.disability += millions*2200;
        flows.localServices += millions*(std::clamp(tile.buildings[city].area,0.,1.)*70000
            + std::clamp(tile.buildings[village].area,0.,1.)*28000);
    }
    flows.social = flows.pensions+flows.children+flows.disability+flows.localServices;
    return flows;
}

}
