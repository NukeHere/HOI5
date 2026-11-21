#include "../production.hpp"
#include "../diplomacy.hpp"
#include "../simulation_clock.hpp"
#include <cmath>
#include <iostream>

int main() {
    hoi5::Production production{};
    production[hoi5::raw].outputs["food"] = 150;
    production[hoi5::upkeep].inputs = {{"food",300},{"consumer_goods",300},{"coal",900}};
    hoi5::Stockpile stocks{{"consumer_goods",2.5}};
    double food = 0, goods = 0;
    const auto ratios = hoi5::runProduction(production,stocks,6,
        [&](auto key,double amount) { stocks[key] += amount; },
        [&](auto key,double used,double needed) {
            if (key == "food") food = used/needed;
            if (key == "consumer_goods") goods = used/needed;
        });
    // An unrelated missing upkeep input must not invent 50% food or erase delivered goods.
    if (ratios[hoi5::upkeep] != 0 || std::abs(food-.5) > 1e-12 || goods != 1 ||
        hoi5::value(stocks,"food") != 0 || hoi5::value(stocks,"consumer_goods") != 0) return 1;
    hoi5::CountryPolitics relief;
    relief.crisisDays = 720; relief.unrest = 1;
    relief.factionPatience.fill(0); relief.factionRadicalization.fill(1);
    for (int day = 0; day < 6; ++day) relief.advanceCrisis(false);
    if (!relief.civilWarRisk(1)) return 1;
    relief.advanceCrisis(false);
    if (relief.civilWarRisk(1)) return 1;
    relief.food = relief.goods = 0;
    relief.advanceCrisis(false);
    if (relief.reliefDays != 0 || !relief.civilWarRisk(1)) return 1;
    hoi5::SimulationClock clock;
    clock.setSpeed(5); clock.setPaused(false);
    int steps = 0;
    clock.update(.5,[&](int) { ++steps; clock.setPaused(true); });
    if (steps != 1 || !clock.paused || clock.elapsedHours != 6) return 1;
    std::cout << "Actual per-resource consumption and immediate modal pause passed\n";
}
