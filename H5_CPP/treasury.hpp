#pragma once

#include "treasury_data.hpp"

namespace hoi5 {

inline constexpr double monthlyArmyExpenses() { return 0.; }

template<class Tile>
double populationIncomeRateForTile(const Tile& tile) {
    double income = ruralIncome, totalWeight = 1.;
    for (int building = 0; building < buildingCount; ++building) {
        const double weight = std::max(0.,tile.buildings[building].area)*populationIncomeWeights[building];
        income += populationIncomeRates[building]*weight;
        totalWeight += weight;
    }
    return income/totalWeight;
}

template<class Tile>
double monthlyTilePopulationIncome(const Tile& tile) {
    return std::max(0.,tile.population)/1e6*populationIncomeRateForTile(tile);
}

template<class Tile>
double monthlyTileCompanyIncome(const Tile& tile) {
    double income = 0.;
    for (int building = 0; building < buildingCount; ++building) {
        const auto& b = tile.buildings[building];
        income += std::max(0.,b.area)*std::clamp(b.health,0.,1.)*companyIncomeRates[building];
    }
    return income;
}

struct TreasuryFlows {
    double population{}, companies{}, government = 450000, social{}, infrastructure{};
    double pensions{}, children{}, disability{}, localServices{};
    double loanRepayments{}, debtService{}, politicalPrograms{};
    double operatingBalance() const { return population+companies-government-social-infrastructure-monthlyArmyExpenses(); }
    double expenses() const { return government+social+infrastructure+debtService+politicalPrograms+monthlyArmyExpenses(); }
    double balance() const { return operatingBalance()+loanRepayments-debtService-politicalPrograms; }
};

template<class Tile>
TreasuryFlows monthlyTreasury(const std::vector<Tile>& tiles,int owner,double population) {
    TreasuryFlows flows;
    flows.government += std::max(0.,population)/1e6*48000;
    for (const auto& tile : tiles) {
        if (tile.owner != owner) continue;
        if (!tile.water) flows.government += 3500;
        flows.population += monthlyTilePopulationIncome(tile);
        flows.companies += monthlyTileCompanyIncome(tile);
        for (int building = 0; building < buildingCount; ++building) {
            const auto& b = tile.buildings[building];
            flows.infrastructure += std::max(0.,b.area)*infrastructureUpkeep[building];
        }
        const double millions = std::max(0.,tile.population)/1e6;
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
