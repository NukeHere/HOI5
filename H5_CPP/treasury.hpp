#pragma once

#include "treasury_data.hpp"

namespace hoi5 {

struct TreasuryFlows {
    double population{}, companies{}, government = 450000, social{}, infrastructure{};
    double balance() const { return population+companies-government-social-infrastructure; }
};

template<class Tile>
TreasuryFlows monthlyTreasury(const std::vector<Tile>& tiles,int owner,double population,double stability) {
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
        flows.social += tile.population/1e6 * (socialBase + tile.buildings[city].area*70000 + tile.buildings[village].area*28000);
    }
    flows.companies *= std::clamp(1+.5*(std::clamp(stability,0.,1.)-.72),.65,1.05);
    return flows;
}

}
