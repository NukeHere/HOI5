#include "../combat_sampling.hpp"
#include <limits>
#include <stdexcept>
int main() {
    using namespace hoi5;std::mt19937 a(146591),b(146591);
    auto check=[](bool ok){if(!ok) throw std::runtime_error("bounded combat sampling");};
    check(sampleCombatHits(8,0.,a)==0 && sampleCombatHits(8,1.,a)==8);
    check(sampleCombatHits(-4,.5,a)==0 && sampleCombatHits(0,.5,a)==0 && sampleCombatHits(8,std::numeric_limits<double>::quiet_NaN(),a)==0);
    long sum=0;constexpr int samples=100000;
    for(int i=0;i<samples;++i) {
        const int x=sampleCombatHits(8,.3,a);check(x>=0 && x<=8 && x==sampleCombatHits(8,.3,b));sum+=x;
    }
    check(std::abs(double(sum)/samples-2.4)<.025);
    struct Zero {using result_type=unsigned;static constexpr unsigned min(){return 0;}static constexpr unsigned max(){return 0xffffffffu;}unsigned operator()(){return 0;}} zero;
    check(sampleCombatHits(8,.3,zero)==8);
}
