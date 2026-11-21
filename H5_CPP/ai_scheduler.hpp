#pragma once
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

namespace hoi5 {
// Deterministic simulation-time budget. Urgency may change eligibility, never
// multiply the expensive-work allowance. Fast tactical reactions run separately.
template<class Eligible>
std::vector<bool> selectBotDailyWork(std::size_t count,int active,double hours,
                                    std::size_t& cursor,Eligible eligible) {
    std::vector<bool> selected(count);
    if(!count || active<=0 || hours<=0) return selected;
    int remaining=std::max(1,int(std::ceil(active*std::min(24.,hours)/24.)));
    const auto start=cursor%count;
    for(std::size_t offset=0;offset<count && remaining; ++offset) {
        const auto index=(start+offset)%count;
        if(!eligible(index)) continue;
        selected[index]=true;--remaining;cursor=(index+1)%count;
    }
    return selected;
}
}
