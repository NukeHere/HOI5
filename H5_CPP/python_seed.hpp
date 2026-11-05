#pragma once

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <random>

namespace hoi5 {

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

class PythonRandom {
    std::mt19937 engine;

public:
    explicit PythonRandom(std::uint64_t value = 0) { seed(value); }

    void seed(std::uint64_t value) {
        PythonSeed sequence{value};
        engine.seed(sequence);
    }

    // Python choice uses getrandbits with rejection, including for a singleton.
    std::uint32_t below(std::uint32_t stop) {
        const int bits = std::bit_width(stop);
        std::uint32_t value;
        do {
            value = engine() >> (32-bits);
        } while (value >= stop);
        return value;
    }

    double uniform() {
        const auto high = engine() >> 5;
        const auto low = engine() >> 6;
        return (high*67108864.+low)/9007199254740992.;
    }
};

}
