#include "../air_missions.hpp"
#include <stdexcept>
int main() {
    using namespace hoi5;
    auto check=[](bool ok){if(!ok) throw std::runtime_error("available air payload");};
    auto choose=[](int type,bool strategic,bool hard,std::string_view only) {
        return availableMissionWeapon(type,strategic,hard,[&](const auto& weapon){return weapon.key==only;});
    };
    for(auto key:{"tactical_cruise_missile","small_ballistic_missile","heavy_strategic_missile","bunker_buster"}) {
        auto weapon=choose(5,true,true,key);check(weapon && weapon->key==key);
    }
    auto fallback=choose(3,false,false,"unguided_rockets");check(fallback && fallback->key=="unguided_rockets");
    check(!choose(4,true,true,"heavy_strategic_missile"));
    auto bunker=availableMissionWeapon(5,true,true,[](const auto&){return true;});
    check(bunker && bunker->key=="bunker_buster");
    check(!availableMissionWeapon(5,true,true,[](const auto&){return false;}));
    AirLayer layer;BuildingCoverage runway{.1,1.};
    layer.registerConstructedBase(0,0,runway);check(layer.bases[0].runway==1);
    runway.area=.35;layer.registerConstructedBase(0,0,runway);
    check(layer.bases.size()==1 && layer.bases[0].runway==2 && runway.area==.35);
    // A close target cannot use a missile with a minimum standoff distance.
    auto close=availableMissionWeapon(5,true,true,[](const auto& weapon){
        return airMissionLaunchDistance(1,weapon,0,AirRisk::normal,true).has_value();
    });
    check(close && close->key=="bunker_buster");
}
