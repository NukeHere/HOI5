#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <random>
#include <unordered_map>

namespace hoi5 {

struct Terrain {
    double elevation, ridge, moisture, temperature;
    bool lake;
    double water{}, trees{}, grass{}, rock{}, sand{}, snow{};

    void initializeCovers() {
        if (elevation < .25) {
            water = 1;
            return;
        }
        const double rockBonus = ridge * .45;
        const double treePenalty = ridge * .35;
        if (elevation > .7 || ridge > .65) {
            rock = std::min(.95, .4 + std::max(0., elevation - .7) * 2 + rockBonus);
            trees = std::clamp(.1 + (moisture - .3) * 2 - treePenalty, 0., .35);
            if (temperature < .3) snow = std::min(.85, .3 + (.3 - temperature) * 2 + ridge * .15);
            grass = std::max(0., 1 - rock - snow - trees);
        } else if (elevation > .5 || ridge > .35) {
            rock = std::min(.75, .2 + std::max(0., elevation - .5) + rockBonus);
            trees = std::clamp(.35 + (moisture - .35) * 2 - treePenalty, 0., .65);
            grass = std::max(0., 1 - rock - trees);
        } else if (moisture > .5) {
            grass = .8;
            trees = .2;
        } else if (moisture > .2) {
            trees = std::min(.8, .5 + (moisture - .4) * 2);
            grass = std::max(0., 1 - trees);
        } else if (temperature > .6) {
            sand = .6;
            grass = .4;
        } else {
            grass = .5;
            sand = .3;
            trees = .2;
        }
        if (temperature < .2 && elevation < .5) {
            snow = std::min(.7, snow + .3);
            grass *= 1 - snow;
            trees *= 1 - snow;
            sand *= 1 - snow;
        }
        const double total = trees + grass + rock + sand + snow;
        trees /= total;
        grass /= total;
        rock /= total;
        sand /= total;
        snow /= total;
    }

    double movementCost() const {
        const double cost = 1 + ridge * 1.5 + rock * 1.2 + snow * .5;
        if (ridge > .75 && temperature < .35) return cost + 2;
        if (ridge > .7 || rock > .7) return cost + 1.5;
        if (ridge > .4 || rock > .45) return cost + .75;
        return cost;
    }
};

// Python random.seed(int) initializes MT19937 with init_by_array.
struct PythonSeed {
    using result_type = std::uint32_t;
    std::uint64_t value;

    template<class Iterator>
    void generate(Iterator first, Iterator last) {
        std::array<std::uint32_t, 624> state;
        state[0] = 19650218;
        for (std::uint32_t i = 1; i < state.size(); ++i)
            state[i] = 1812433253u * (state[i-1] ^ (state[i-1] >> 30)) + i;
        const std::array key{std::uint32_t(value), std::uint32_t(value >> 32)};
        const unsigned length = key[1] ? 2 : 1;
        unsigned i = 1, j = 0;
        const auto next = [&] {
            if (++i == state.size()) {
                state[0] = state.back();
                i = 1;
            }
        };
        for (unsigned k = 0; k < state.size(); ++k) {
            state[i] = (state[i] ^ ((state[i-1] ^ (state[i-1] >> 30)) * 1664525u)) + key[j] + j;
            next();
            j = (j + 1) % length;
        }
        for (unsigned k = 1; k < state.size(); ++k) {
            state[i] = (state[i] ^ ((state[i-1] ^ (state[i-1] >> 30)) * 1566083941u)) - i;
            next();
        }
        state[0] = 0x80000000u;
        std::copy(state.begin(), state.end(), first);
        (void)last;
    }
};

class WorldGenerator {
    int size;
    std::uint32_t seed;
    std::unordered_map<std::uint64_t, std::array<double, 2>> gradients;

    static double fade(double value) {
        return 6 * std::pow(value, 5) - 15 * std::pow(value, 4) + 10 * std::pow(value, 3);
    }

    double noise(double x, double y, double octaves, unsigned offset) {
        x *= octaves;
        y *= octaves;
        const int q = static_cast<int>(std::floor(x)), r = static_cast<int>(std::floor(y));
        double sum = 0;
        for (int i = q; i <= q + 1; ++i) for (int j = r; j <= r + 1; ++j) {
            const auto key = std::uint64_t(seed + offset) * std::max(1, std::abs(i + 10 * j + 1));
            auto [entry, inserted] = gradients.try_emplace(key);
            if (inserted) {
                PythonSeed input{key};
                std::mt19937 rng(input);
                for (double& axis : entry->second) {
                    const auto high = rng() >> 5;
                    const auto low = rng() >> 6;
                    axis = -1 + 2 * ((high * 67108864. + low) / 9007199254740992.);
                }
            }
            const double dx = x - i, dy = y - j;
            sum += fade(1 - std::abs(dx)) * fade(1 - std::abs(dy))
                * (entry->second[0] * dx + entry->second[1] * dy);
        }
        return sum;
    }

    double temperature(int q, int r, double elevation) {
        const double period = 2. * size / 15;
        const double variation = noise(q * 3 / period, r * 3 / period, 2, 550);
        const double base = .5 + noise(q / period, r / period, .5, 500) * .5;
        return std::clamp((base + variation * .6) * (1 - elevation * .4), .15, .85);
    }

    double moisture(int q, int r, double elevation) {
        const double period = 2. * size / 20;
        double base = (noise(q / period, r / period, 1, 400) + 1) / 2;
        const double detail = (noise(q * 2 / period, r * 2 / period, 1.5, 450) + 1) / 2;
        const double shadow = (noise(q / period, r / period, 2, 480) + 1) / 2;
        if (elevation > .6) base *= 1 - shadow * .5;
        const double bonus = elevation > .25 && elevation < .32
            ? .2 * (1 - (elevation - .25) / (.32 - .25)) : 0;
        return std::clamp((base * .6 + detail * .4) * .8 * (1 - elevation * .4) + bonus, .1, 1.);
    }

public:
    WorldGenerator(int size, std::uint32_t seed) : size(size), seed(seed) {}

    Terrain generate(int q, int r) {
        const double period = 2. * size / (25 * (1.1 - .2));
        double elevation = std::clamp(.4 + 1.2 * .8 * noise(q / period, r / period, 1.5, 0), 0., 1.);
        const double x = 1.5 * q / size, y = 1.5 * r / size;
        double ridge = ((noise(x, y, 2, 300) + noise(x * 2, y * 2, 4, 350)) / 2 + 1) / 2;
        const double direction = std::abs(noise(x + 10, y, 1, 380) * noise(x, y + 10, 1, 380)) * 2;
        ridge *= .7 + direction * .3;
        ridge = ridge < .3 ? 0 : std::pow((ridge - .3) / (1 - .3), .7);
        elevation = std::clamp(elevation + ridge * .6 * .35 * (elevation < .25 ? .35 : 1), 0., 1.);

        const double basin = (noise(x * 2, y * 2, 2, 650) + 1) / 2;
        const double feature = (noise(x * 4, y * 4, 3, 600) + 1) / 2;
        const bool lake = elevation > .25 && elevation < .25 + .4 * .3
            && temperature(q, r, elevation) >= .2 && basin * feature > 1 - .4 * .7;
        if (lake) elevation = .25 - .02;
        Terrain tile{elevation, ridge, moisture(q, r, elevation), temperature(q, r, elevation), lake};
        tile.initializeCovers();
        return tile;
    }
};

}
