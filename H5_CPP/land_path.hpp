#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <limits>
#include <vector>

namespace hoi5 {
struct LandPathMetrics { std::size_t expanded{}, pushed{}; };

// Odd-row offset coordinates, as used by World::forFrontNeighbor.
inline int landHexDistance(int a,int b,int size) {
    const int ar = a/size, br = b/size;
    const int dq = a%size-ar/2-(b%size-br/2), dr = ar-br;
    return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
}

// Scratch storage, not a route cache: every call rechecks current permissions and
// terrain. Generation stamps avoid clearing the entire map for every AI order.
struct LandPathScratch {
    struct Node { double f, g; std::size_t sequence; int tile; };
    std::vector<double> cost;
    std::vector<int> parent;
    std::vector<std::uint64_t> stamp;
    std::vector<Node> heap;
    std::uint64_t generation{};
};

inline LandPathScratch& landPathScratch() {
    static thread_local LandPathScratch scratch;
    return scratch;
}

template<class CanEnter,class MovementCost>
std::deque<int> findLandPath(int size,int count,int origin,int destination,
                            CanEnter canEnter,MovementCost movementCost,LandPathMetrics* metrics = nullptr) {
    if (metrics) *metrics = {};
    if (size <= 0 || origin < 0 || destination < 0 || origin >= count || destination >= count ||
        origin == destination || !canEnter(destination)) return {};
    auto& s = landPathScratch();
    s.cost.resize(count);
    s.parent.resize(count);
    s.stamp.resize(count);
    if (++s.generation == 0) { std::fill(s.stamp.begin(),s.stamp.end(),0); ++s.generation; }
    s.heap.clear();
    // Prefer progress toward the goal on equal f, then preserve neighbor order.
    const auto later = [](const auto& a,const auto& b) {
        if (a.f != b.f) return a.f > b.f;
        if (a.g != b.g) return a.g < b.g;
        return a.sequence > b.sequence;
    };
    std::size_t sequence = 0;
    const auto push = [&](int tile,double g) {
        s.heap.push_back({g+landHexDistance(tile,destination,size),g,sequence++,tile});
        std::push_heap(s.heap.begin(),s.heap.end(),later);
        if (metrics) ++metrics->pushed;
    };
    s.stamp[origin] = s.generation;
    s.cost[origin] = 0.;
    push(origin,0.);
    while (!s.heap.empty()) {
        std::pop_heap(s.heap.begin(),s.heap.end(),later);
        const auto node = s.heap.back();
        s.heap.pop_back();
        if (node.g != s.cost[node.tile]) continue; // stale improved queue entry
        if (metrics) ++metrics->expanded;
        if (node.tile == destination) {
            std::deque<int> result;
            for (int step = destination; step != origin; step = s.parent[step]) result.push_front(step);
            return result;
        }
        const int q = node.tile%size, r = node.tile/size, shift = r%2;
        const int offsets[6][2] = {{shift,1},{shift-1,1},{-1,0},{shift-1,-1},{shift,-1},{1,0}};
        for (const auto& offset : offsets) {
            const int nq = q+offset[0], nr = r+offset[1];
            if (nq < 0 || nq >= size || nr < 0 || nr >= size) continue;
            const int next = nr*size+nq;
            if (next >= count || !canEnter(next)) continue;
            const double g = node.g+std::max(1.,movementCost(next));
            if (s.stamp[next] == s.generation && g >= s.cost[next]) continue;
            s.stamp[next] = s.generation;
            s.cost[next] = g;
            s.parent[next] = node.tile;
            push(next,g);
        }
    }
    // Exhausted the reachable component, not an arbitrary search budget.
    return {};
}
}
