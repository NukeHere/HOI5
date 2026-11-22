#pragma once
#include <cmath>
#include <random>
namespace hoi5 {
// Negative trial counts can make the standard implementation loop forever.
// Preserve the established seeded distribution for valid combat packages.
template<class Generator> int sampleCombatHits(int trials,double probability,Generator& random) {
    if(trials<=0 || !std::isfinite(probability) || probability<=0.) return 0;
    if(probability>=1.) return trials;
    return std::binomial_distribution<int>(trials,probability)(random);
}
}
