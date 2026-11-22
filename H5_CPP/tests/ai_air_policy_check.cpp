#include "../ai_air_policy.hpp"
#include <algorithm>
#include <stdexcept>
int main() {
    using namespace hoi5;
    auto check=[](bool ok){if(!ok) throw std::runtime_error("situational air targets");};
    const auto support=botAirTargetPriorities(true,false,false,false);
    check(support.front()=="enemy_units");
    const auto suppression=botAirTargetPriorities(false,true,true,true);
    check(suppression.front()=="air_defense" && suppression[1]=="airbases");
    const auto rear=botAirTargetPriorities(false,false,false,true);
    check(rear.front()=="supply_infrastructure" && std::find(rear.begin(),rear.end(),"enemy_units")==rear.end());
    check(support!=suppression && rear!=support && fighterSortieFuel(5)>fighterSortieFuel(1));
}
