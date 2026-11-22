#pragma once
#include <string_view>
#include <vector>
namespace hoi5 {
inline std::vector<std::string_view> botAirTargetPriorities(bool groundSupport,bool enemyAir,bool enemyDefense,bool strategic) {
    std::vector<std::string_view> result;
    if(groundSupport) result.push_back("enemy_units");
    if(enemyDefense) result.push_back("air_defense");
    if(enemyAir) result.push_back("airbases");
    result.push_back("supply_infrastructure");
    if(strategic) {
        if(!enemyAir) result.push_back("airbases");
        result.push_back("industry");
    }
    return result;
}
inline double fighterSortieFuel(int distance) {return 2.*(1.+distance);}
}
