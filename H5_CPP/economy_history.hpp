#pragma once
#include <algorithm>
#include <deque>
#include <vector>
namespace hoi5 {
class EconomyTradeHistory {
    struct Sample {int hour;std::vector<double> cash;};
    std::deque<Sample> samples;
    std::vector<int> firstSeen;
    std::vector<double> openingCash;
public:
    template<class Archive> void saveFields(Archive& archive) { archive(samples,firstSeen,openingCash); }
    std::vector<double> update(int hour,const std::vector<double>& cash) {
        if(!samples.empty() && hour<samples.back().hour) {samples.clear();firstSeen.clear();openingCash.clear();}
        const auto previous=firstSeen.size();firstSeen.resize(cash.size(),hour);openingCash.resize(cash.size());
        for(std::size_t i=previous;i<cash.size();++i) openingCash[i]=cash[i];
        if(samples.empty() || hour/24>samples.back().hour/24) samples.push_back({hour,cash});
        while(samples.size()>1 && samples[1].hour<=hour-720) samples.pop_front();
        std::vector<double> result(cash.size());const auto& baseline=samples.front();
        for(std::size_t i=0;i<cash.size();++i) {
            const int from=std::max(baseline.hour,firstSeen[i]);
            const double opening=i<baseline.cash.size()?baseline.cash[i]:openingCash[i];
            if(hour>from) result[i]=(cash[i]-opening)*720./(hour-from);
        }
        return result;
    }
};
}
