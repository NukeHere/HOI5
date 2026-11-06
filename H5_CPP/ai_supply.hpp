#pragma once

#include <algorithm>
#include <cmath>
#include <optional>
#include <span>

namespace hoi5 {

struct BotSupplyPoint { int tile; double weight, passability, current; };
struct BotSupplyCandidate { int tile; double strength, multiplier; };
struct BotSupplyChoice { double gain; int tile; };

inline int supplyHexDistance(int first,int second,int width) {
    const int dq = first%width-second%width, dr = first/width-second/width;
    return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
}

inline std::optional<BotSupplyChoice> bestBotSupplySite(int width,std::span<const BotSupplyPoint> points,
                                                     std::span<const BotSupplyCandidate> candidates) {
    std::optional<BotSupplyChoice> best;
    for (const auto& candidate : candidates) {
        double gain = 0.;
        for (const auto& point : points) {
            const int distance = supplyHexDistance(candidate.tile,point.tile,width);
            if (distance > 7) continue;
            const double expected = candidate.strength*std::pow(.78,distance)*(.42+.58*point.passability);
            gain += std::max(0.,std::min(.6,expected)-point.current)*point.weight;
        }
        gain *= candidate.multiplier;
        if (gain > .05 && (!best || gain > best->gain)) best = BotSupplyChoice{gain,candidate.tile};
    }
    return best;
}

}
