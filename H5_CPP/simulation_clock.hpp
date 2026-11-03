#pragma once

#include <algorithm>
#include <array>
#include <chrono>

namespace hoi5 {

class SimulationClock {
    using Clock = std::chrono::steady_clock;
    static constexpr std::array hoursPerTick{1, 2, 4, 8, 24};
    double accumulator{};
    // 1 January 2000 was a Saturday. The first market opens Monday.
    int nextMarketHour = 48;

public:
    int elapsedHours{};
    int tickCount{};
    int marketTickCount{};
    int pendingMarketTicks{};
    int speed = 1;
    bool paused = true;

    template<class Step>
    void update(double deltaTime, Step step) {
        if (paused) return;
        accumulator = std::min(accumulator + deltaTime, .5);
        const int hours = hoursPerTick[speed - 1];
        const int hoursPerStep = hours / ((hours + 5) / 6);
        const double secondsPerStep = .25 * hoursPerStep / hours;
        const int ticks = std::min(16, int((accumulator + 1e-10) / secondsPerStep));
        const auto started = Clock::now();
        for (int i = 0; i < ticks; ++i) {
            if (i && Clock::now() - started >= std::chrono::milliseconds(8)) break;
            accumulator = std::max(0., accumulator - secondsPerStep);
            ++tickCount;
            int remaining = hoursPerStep;
            while (remaining > 0) {
                const int duration = std::min({6, remaining, 24 - elapsedHours % 24});
                elapsedHours += duration;
                if (elapsedHours == nextMarketHour) {
                    ++pendingMarketTicks;
                    ++marketTickCount;
                    nextMarketHour += 7 * 24;
                }
                step(duration);
                remaining -= duration;
            }
        }
    }
};

}
