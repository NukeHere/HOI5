#pragma once

#include "supply.hpp"

namespace hoi5 {

inline constexpr std::array<double,buildingCount> populationIncomeRates{
    700000, 300000, 240000, 210000, 390000, 230000, 480000, 420000, 460000, 220000, 360000, 0, 0, 0
};
inline constexpr std::array<double,buildingCount> populationIncomeWeights{
    5.0, 3.0, 1.2, 1.1, 1.9, 1.1, 2.2, 1.7, 2.3, 1.6, 1.8, 0, 0, 0
};
inline constexpr std::array<double,buildingCount> companyIncomeRates{
    0, 0, 45000, 52000, 160000, 65000, 220000, 165000, 240000, 90000, 135000, 0, 0, 0
};
inline constexpr std::array<double,buildingCount> infrastructureUpkeep{
    145000, 42000, 18000, 24000, 75000, 28000, 115000, 62000, 92000, 18000, 50000, 0, 0, 0
};
inline constexpr double ruralIncome = 150000;
inline constexpr double socialBase = 62000.0;
}
