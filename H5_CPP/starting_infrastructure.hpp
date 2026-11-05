#pragma once

#include "map_data.hpp"
#include "supply.hpp"
#include <tuple>

namespace hoi5 {

struct StartingProfile {
    double scale;
    double population;
    double budget;
    double industryEfficiency = 1., cityBuildMultiplier = 1., buildTechBonus = 0.;
    double buildEfficiency = 1.;
};

inline StartingProfile startingProfile(int size, int land) {
    const double mapScale = std::clamp(size / 40., .65, 1.8);
    const double scale = std::clamp((land ? land : 90) / 90. * std::pow(mapScale, .45), .45, 2.4);
    return {scale, std::nearbyint(21000000 * scale), 250000000 * (.65 + scale * .35)};
}

inline double agricultureScore(const Terrain& t) {
    if (t.water > .5) return 0;
    const auto clamp = [](double x) { return std::clamp(x, 0., 1.); };
    double base = t.grass * .32 + clamp(1 - std::abs(t.temperature - .55) / .55) * .22
        + clamp(1 - std::abs(t.moisture - .52) / .52) * .22
        + clamp(1 - t.ridge * 1.15 - t.rock * .75 - t.snow * .55) * .18 + t.trees * .06;
    const auto type = biome(t);
    if (type == "grassland" || type == "plains" || type == "savanna") base += .12;
    else if (type == "temperate_forest" || type == "taiga") base += .04;
    else if (type == "desert" || type == "mountains" || type == "snowy_mountains" || type == "tundra") base -= .18;
    return clamp(base);
}

template<class Tile>
int ownedNeighbors(const std::vector<Tile>& tiles, int size, int index, bool* coastal = nullptr) {
    const int q = index % size, r = index / size, shift = r % 2;
    const std::array<std::pair<int, int>, 6> offsets{{
        {shift, 1}, {shift - 1, 1}, {-1, 0}, {shift - 1, -1}, {shift, -1}, {1, 0}
    }};
    int count = 0;
    for (const auto [dq, dr] : offsets) {
        if (q+dq < 0 || q+dq >= size || r+dr < 0 || r+dr >= size) continue;
        const auto& neighbor = tiles[(r+dr)*size + q+dq];
        if (coastal && (neighbor.water || neighbor.natural.water > .55)) *coastal = true;
        count += neighbor.owner == tiles[index].owner;
    }
    return count;
}

template<class Tile>
void placeStartingCities(std::vector<Tile>& tiles, int size, int capital,
                         const std::vector<int>& land, const StartingProfile& profile) {
    std::vector<std::pair<int, double>> candidates;
    for (int index : land) {
        const auto& tile = tiles[index];
        const auto& t = tile.natural;
        const int q = index % size, r = index / size;
        double agriculture = 0;
        for (int dq = -2; dq <= 2; ++dq) for (int dr = -2; dr <= 2; ++dr) {
            if ((!dq && !dr) || std::abs(dq + dr) > 2 ||
                q+dq < 0 || q+dq >= size || r+dr < 0 || r+dr >= size) continue;
            const auto& other = tiles[(r+dr)*size + q+dq];
            if (other.owner == tile.owner) agriculture += agricultureScore(other.natural) * .10;
        }
        bool coastal = false;
        const int neighbors = ownedNeighbors(tiles, size, index, &coastal);
        const double climate = std::clamp(1 - std::abs(t.temperature-.52)*1.15
            - std::abs(t.moisture-.50)*.55 - t.snow*.45, 0., 1.);
        const double score = std::clamp(.24 / tile.movementCost + climate*.22 + neighbors*.03
            + std::min(.35, agriculture) + (coastal ? .06 : 0) + (index == capital ? .28 : 0), 0., 1.);
        if (score >= .05 || index == capital) candidates.emplace_back(index, score >= .05 ? score : .35);
    }
    const auto order = [size](const auto& a, const auto& b) {
        return std::tuple{-a.second, a.first % size, a.first / size}
             < std::tuple{-b.second, b.first % size, b.first / size};
    };
    std::sort(candidates.begin(), candidates.end(), order);
    const int minimum = std::clamp(int(std::ceil(profile.scale*3)), 1, 4);
    const int maximum = std::clamp(int(std::ceil(profile.scale*7)), minimum, 10);
    const int limit = std::clamp(int(std::ceil(land.size()*(.10 + profile.scale*.06))), minimum, maximum);
    if (candidates.size() > std::size_t(limit)) candidates.resize(limit);
    if (candidates.empty()) return;
    const double budget = profile.population / 10000000;
    std::vector<double> weights;
    double total = 0;
    for (const auto& [index, score] : candidates) {
        weights.push_back(std::max(.01, score) * std::pow(.78, weights.size()));
        total += weights.back();
    }
    double remaining = budget;
    for (std::size_t i = 0; i < candidates.size() && remaining > .005; ++i) {
        double desired = budget * weights[i] / total;
        if (remaining >= .08) desired = std::max(.08, desired);
        auto& coverage = tiles[candidates[i].first].buildings[city].area;
        coverage = std::min({desired, remaining, .72});
        remaining -= coverage;
    }
    for (const auto& [index, score] : candidates) {
        if (remaining <= .005) break;
        auto& coverage = tiles[index].buildings[city].area;
        const double added = std::min(remaining, .72 - coverage);
        coverage += added;
        remaining -= added;
    }
}

using ResourceWeight = std::pair<std::string_view, double>;

inline double resourceScore(const std::vector<Deposit>& deposits, std::span<const ResourceWeight> weights) {
    double result = 0;
    for (const auto& deposit : deposits)
        for (const auto& [name, weight] : weights)
            if (deposit.resource == name)
                result += weight * std::min(1., std::log10(deposit.mass + 1) / std::log10(1500001.));
    return std::clamp(result, 0., 1.);
}

template<class Tile>
double placeStartingBuildings(std::vector<Tile>& tiles, int size, int capital,
                              const std::vector<int>& land, double scale) {
    constexpr ResourceWeight solid[] = {{"coal",1}, {"peat",.55}, {"iron_ore",1},
        {"copper_ore",.82}, {"bauxite",.64}, {"sulfur",.42}, {"phosphorite",.40}, {"apatite",.36}};
    constexpr ResourceWeight all[] = {{"coal",1}, {"oil",1}, {"natural_gas",.95}, {"peat",.55},
        {"iron_ore",1}, {"copper_ore",.82}, {"bauxite",.64}, {"sulfur",.42}, {"phosphorite",.40}, {"apatite",.36}};
    constexpr ResourceWeight oilGas[] = {{"oil",1}, {"natural_gas",.95}};
    constexpr ResourceWeight fuel[] = {{"oil",1}, {"natural_gas",.75}, {"coal",.20}};
    const double budgetScale = std::clamp(std::pow(scale,.88), .45, 2.6);

    const auto nearby = [&](int index, int radius, auto value) {
        const int q = index % size, r = index / size;
        double sum = 0;
        for (int dq = -radius; dq <= radius; ++dq) for (int dr = -radius; dr <= radius; ++dr) {
            if (std::abs(dq+dr) > radius || q+dq < 0 || q+dq >= size || r+dr < 0 || r+dr >= size) continue;
            const auto& tile = tiles[(r+dr)*size + q+dq];
            if (tile.owner == tiles[index].owner)
                sum += value(tile) / std::max({1, std::abs(dq), std::abs(dr), std::abs(dq+dr)});
        }
        return std::clamp(sum, 0., 1.);
    };
    const auto coverage = [&](int index, int radius, std::initializer_list<Building> buildings) {
        return nearby(index, radius, [&](const Tile& tile) {
            double sum = 0;
            for (auto building : buildings) sum += tile.buildings[building].area;
            return sum;
        });
    };
    const auto resources = [&](int index, int radius, std::span<const ResourceWeight> weights) {
        return nearby(index, radius, [&](const Tile& tile) { return resourceScore(tile.deposits, weights); });
    };
    using Candidate = std::pair<int,double>;
    const auto candidates = [&](auto score, double ratio, int low, int high, double threshold) {
        std::vector<Candidate> result;
        for (int index : land) {
            const auto value = std::clamp(score(index), 0., 1.);
            if (value >= threshold && value > 0) result.emplace_back(index, value);
        }
        std::sort(result.begin(), result.end(), [size](const auto& a, const auto& b) {
            return std::tuple{-a.second,a.first%size,a.first/size} < std::tuple{-b.second,b.first%size,b.first/size};
        });
        const auto limit = std::size_t(std::clamp(int(std::ceil(land.size()*ratio)), low, high));
        if (result.size() > limit) result.resize(limit);
        return result;
    };
    const auto allocate = [&](Building building, const std::vector<Candidate>& choices, double amount,
                              double minimum, double maximum, double decay) {
        double remaining = amount, total = 0;
        std::vector<double> weights;
        for (const auto& [index, score] : choices) {
            weights.push_back(std::max(.01,score) * std::pow(decay, weights.size()));
            total += weights.back();
        }
        const auto add = [&](int index, double wanted) {
            auto& area = tiles[index].buildings[building].area;
            const double added = std::min({wanted, remaining, maximum - area});
            area += added;
            remaining -= added;
        };
        for (std::size_t i = 0; i < choices.size() && remaining > .005; ++i) {
            double wanted = amount * weights[i] / total;
            if (remaining >= minimum) wanted = std::max(wanted, minimum);
            add(choices[i].first, wanted);
        }
        for (const auto& [index, score] : choices) {
            if (remaining <= .005) break;
            add(index, remaining);
        }
        return remaining;
    };
    const auto pass = [&](int i) { return 1 / tiles[i].movementCost; };
    const auto centrality = [&](int i) { return ownedNeighbors(tiles,size,i) / 6.; };
    const auto villageScore = [&](int i) {
        return agricultureScore(tiles[i].natural)*.54 + coverage(i,3,{city})*.22
            + centrality(i)*.14 + (1-tiles[i].buildings[city].area)*.10;
    };
    const auto farmScore = [&](int i) {
        return agricultureScore(tiles[i].natural)*.74 + coverage(i,2,{city})*.18 + centrality(i)*.08;
    };
    const auto industryScore = [&](int i) {
        return coverage(i,3,{city})*.38 + resources(i,2,solid)*.18 + coverage(i,2,{mine})*.16
            + coverage(i,2,{oilGasRig})*.10 + coverage(i,3,{port})*.10 + pass(i)*.18;
    };
    const auto portScore = [&](int i) {
        int waterEdges = 0;
        const int q = i % size, r = i / size, shift = r % 2;
        for (const auto [dq,dr] : std::array<std::pair<int,int>,6>{{
            {shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}
        }})
            if (q+dq >= 0 && q+dq < size && r+dr >= 0 && r+dr < size)
                waterEdges += tiles[(r+dr)*size+q+dq].water;
        if (!waterEdges) return 0.;
        return .22 + coverage(i,3,{city})*.30 + coverage(i,3,{industry})*.22
            + resources(i,3,all)*.12 + waterEdges/6.*.08 + pass(i)*.06;
    };
    const double villageLeft = allocate(village,candidates(villageScore,.22,3,10,.12),
        1.20*budgetScale/.85,.06,.30,.86);
    const auto farmCandidates = candidates(farmScore,.34,5,18,.12);
    double remaining = allocate(farms,farmCandidates,5.20*budgetScale,.08,.42,.88);
    remaining += allocate(mine,candidates([&](int i) {
        const double raw = resourceScore(tiles[i].deposits,solid);
        return raw > 0 ? raw*.74 + coverage(i,3,{city})*.12 + pass(i)*.14 : 0;
    },.30,3,12,.10),1.20*budgetScale/1.15,.06,.34,.84);
    remaining += allocate(oilGasRig,candidates([&](int i) {
        const double raw = resourceScore(tiles[i].deposits,oilGas);
        return raw > 0 ? raw*.70 + coverage(i,3,{city})*.08 + coverage(i,3,{refinery})*.10
            + coverage(i,2,{fuelStorage})*.06 + pass(i)*.06 : 0;
    },.18,1,7,.10),.85*budgetScale/1.25,.05,.28,.84);

    const bool hasPort = !candidates(portScore,.18,1,5,.08).empty();
    if (!hasPort) remaining += allocate(farms,farmCandidates,.45*budgetScale*.35,.08,.42,.88);
    const double industryBudget = (3.50 + (hasPort ? 0. : .45*.65))*budgetScale;
    remaining += allocate(industry,candidates(industryScore,.26,3,10,.10),industryBudget/1.35,.06,.32,.84);
    if (hasPort) remaining += allocate(port,candidates(portScore,.18,1,5,.08),.45*budgetScale/1.20,.08,.30,.82);
    remaining += allocate(warehouse,candidates([&](int i) {
        const auto& b = tiles[i].buildings;
        const double storage = b[city].area + b[village].area + b[warehouse].area;
        return coverage(i,2,{city,village})*.28 + coverage(i,2,{industry})*.22 + coverage(i,2,{mine})*.16
            + coverage(i,2,{oilGasRig})*.10 + coverage(i,3,{port})*.14 + pass(i)*.16 + (1-std::min(1.,storage))*.04;
    },.16,2,7,.10),(.35*budgetScale+villageLeft*.35)/.90,.05,.26,.82);
    auto fuelCandidates = candidates([&](int i) {
        return coverage(i,2,{city,village})*.24 + coverage(i,2,{industry,refinery})*.24 + resources(i,3,fuel)*.20
            + coverage(i,3,{oilGasRig})*.12 + coverage(i,3,{port})*.14 + pass(i)*.18;
    },.16,2,8,.08);
    if (fuelCandidates.empty() && std::find(land.begin(),land.end(),capital) != land.end())
        fuelCandidates.emplace_back(capital,.5);
    remaining += allocate(fuelStorage,fuelCandidates,1.10*budgetScale/.95,.06,.34,.84);
    auto refineryCandidates = candidates([&](int i) {
        return resources(i,3,fuel)*.34 + coverage(i,3,{oilGasRig})*.16 + coverage(i,3,{city})*.22
            + coverage(i,2,{industry})*.18 + coverage(i,3,{port})*.12 + pass(i)*.14;
    },.10,1,4,.10);
    if (refineryCandidates.empty()) refineryCandidates = candidates(industryScore,0,3,3,0);
    remaining += allocate(refinery,refineryCandidates,1.00*budgetScale/1.45,.05,.22,.82);
    return remaining;
}

template<class Tile>
void distributeStartingPopulation(std::vector<Tile>& tiles, const std::vector<int>& land, double population) {
    constexpr std::array<std::pair<Building,double>, 9> ruralWeights{{
        {village,3.8},{farms,.30},{mine,.16},{oilGasRig,.12},{warehouse,.12},
        {fuelStorage,.08},{refinery,.10},{industry,.10},{port,.08}
    }};
    double cityTotal = 0, ruralTotal = 0;
    std::vector<double> rural(land.size());
    for (std::size_t i = 0; i < land.size(); ++i) {
        const auto& buildings = tiles[land[i]].buildings;
        cityTotal += buildings[city].area;
        if (buildings[city].area > 0) continue;
        for (const auto& [building, weight] : ruralWeights) rural[i] += buildings[building].area * weight;
        ruralTotal += rural[i];
    }
    const double urbanShare = cityTotal <= 0 ? 0 : ruralTotal > 0 ? .72 : 1.;
    for (std::size_t i = 0; i < land.size(); ++i) {
        auto& tile = tiles[land[i]];
        const double cityShare = cityTotal > 0 ? tile.buildings[city].area / cityTotal : 0;
        const double ruralShare = ruralTotal > 0 ? rural[i] / ruralTotal : 0;
        tile.population = population * (urbanShare * cityShare + (1-urbanShare) * ruralShare);
    }
}
}
