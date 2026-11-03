#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <span>
#include <vector>

namespace hoi5 {

enum Building { city, village, warehouse, supplyDepot, port, fuelStorage, refinery, oilGasRig, industry, farms, mine, airbase, fortification, fieldHelipad, buildingCount };

struct BuildingCoverage {
    double area{};
    double health = 1;
};

template<class Tile>
void recalculateSupply(std::span<Tile> tiles, int size, const std::vector<int>& capitals) {
    constexpr std::array<double,buildingCount> sourceWeights{1., .48, .50, .92, .46, .22, .30, .18, .18, 0., 0., 0.};
    constexpr std::array<double,buildingCount> relayWeights{0., 0., .28, .72, .22, 0., 0., 0., 0., 0., 0., 0.};
    std::array<double, 8> decay{};
    for (int d = 0; d <= 7; ++d) decay[d] = std::pow(.78, d);
    for (auto& tile : tiles) tile.supply = 0;
    const auto effective = [](const BuildingCoverage& building) {
        return building.area * building.health;
    };
    for (int index = 0; index < static_cast<int>(tiles.size()); ++index) {
        const auto& source = tiles[index];
        if (source.water || source.owner < 0) continue;
        double strength = index == capitals[source.owner] ? .85 : 0.;
        for (int b = 0; b < buildingCount; ++b) strength += effective(source.buildings[b]) * sourceWeights[b];
        strength = std::clamp(strength, 0., 1.);
        if (strength <= 0) continue;
        const int q = index % size, r = index / size;
        for (int dr = -7; dr <= 7; ++dr) for (int dq = -7; dq <= 7; ++dq) {
            const int distance = std::max({std::abs(dq), std::abs(dr), std::abs(dq + dr)});
            if (distance > 7 || q + dq < 0 || q + dq >= size || r + dr < 0 || r + dr >= size) continue;
            auto& tile = tiles[(r + dr) * size + q + dq];
            if (tile.owner == source.owner && !tile.water)
                tile.supply = std::max(tile.supply, strength * decay[distance]);
        }
    }
    const auto passability = [](const Tile& tile) { return std::clamp(1. / tile.movementCost, 0., 1.); };
    for (auto& tile : tiles) tile.supply *= .42 + passability(tile) * .58;

    std::vector<double> updates(tiles.size());
    for (int pass = 0; pass < 2; ++pass) {
        std::fill(updates.begin(), updates.end(), 0.);
        for (int index = 0; index < static_cast<int>(tiles.size()); ++index) {
            const auto& tile = tiles[index];
            if (tile.owner < 0 || tile.water) continue;
            double relay = 0;
            for (int b = 0; b < buildingCount; ++b) relay += effective(tile.buildings[b]) * relayWeights[b];
            if (relay <= 0) continue;
            const int q = index % size, r = index / size, shift = r % 2;
            const std::array<std::pair<int, int>, 6> offsets{{
                {shift, 1}, {shift - 1, 1}, {-1, 0}, {shift - 1, -1}, {shift, -1}, {1, 0}
            }};
            for (const auto [dq, dr] : offsets) {
                if (q + dq < 0 || q + dq >= size || r + dr < 0 || r + dr >= size) continue;
                const int next = (r + dr) * size + q + dq;
                const auto& neighbor = tiles[next];
                if (neighbor.owner != tile.owner || neighbor.water) continue;
                const double inbound = neighbor.supply * (.46 + relay * .38) * (.62 + passability(tile) * .28);
                if (inbound > tile.supply + .001) updates[index] = std::max(updates[index], std::min(1., inbound));
                if (tile.supply <= .35) continue;
                const double candidate = std::min(1., tile.supply * (.42 + relay)) * (.58 + passability(neighbor) * .30);
                if (candidate > neighbor.supply + .001) updates[next] = std::max(updates[next], std::min(1., candidate));
            }
        }
        for (std::size_t i = 0; i < tiles.size(); ++i)
            tiles[i].supply = std::max(tiles[i].supply, updates[i]);
    }
}

}
