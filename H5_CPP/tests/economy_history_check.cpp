#include "../economy_history.hpp"
#include <stdexcept>
#include <cmath>
int main() {
    hoi5::EconomyTradeHistory history;
    auto check=[](bool ok){if(!ok) throw std::runtime_error("actual trade history");};
    check(history.update(0,{100})[0]==0);
    check(history.update(24,{100})[0]==0);
    auto rate=[&](double x){check(std::abs(x-720.)<1e-8);};
    rate(history.update(168,{268})[0]);
    rate(history.update(169,{269})[0]);
    check(history.update(192,{292,500})[1]==0);
    rate(history.update(216,{316,524})[1]);
    history={};history.update(0,{100});
    for(int day=1;day<=80;++day) rate(history.update(day*24,{100.+day*24})[0]);
    check(history.update(0,{100})[0]==0);
}
