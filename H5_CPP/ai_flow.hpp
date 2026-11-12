#pragma once

#include <algorithm>
#include <deque>
#include <map>
#include <string_view>
#include <tuple>

namespace hoi5 {

enum class FlowKind { output, consumption, import, export_ };
using FlowKey = std::tuple<FlowKind,std::string_view,int>;

struct FlowSample {
    double observedHour, elapsedHours;
    std::map<FlowKey,double> totals;
};

struct FlowLedger {
    std::map<int,std::map<FlowKey,double>> totals;
    std::map<int,double> hours;
    std::map<int,std::deque<FlowSample>> samples;

    void record(int country,FlowKind kind,std::string_view resource,double amount,int partner = -1) {
        totals[country][{kind,resource,partner}] += amount;
    }

    void advance(int country,double amount) { hours[country] += amount; }

    void sample(int country,double now) {
        auto& history = samples[country];
        if (history.empty() || now-history.back().observedHour >= 24.) {
            history.push_back({now,hours[country],totals[country]});
            if (history.size() > 10) history.pop_front();
        }
    }

    std::pair<std::map<FlowKey,double>,double> rates(int country,double now) {
        sample(country,now);
        const auto& history = samples[country];
        const auto baseline = std::ranges::find_if(history,[&](const auto& entry) {
            return entry.observedHour >= now-168.;
        });
        const auto& first = baseline == history.end() ? history.front() : *baseline;
        const double elapsed = hours[country]-first.elapsedHours;
        if (elapsed <= 0) return {{},0.};
        std::map<FlowKey,double> result;
        for (const auto& [key,amount] : totals[country]) {
            const auto old = first.totals.find(key);
            result[key] = (amount-(old == first.totals.end() ? 0. : old->second))*720./elapsed;
        }
        return {std::move(result),elapsed};
    }
};

struct BotDependency { double share, stockDays; int observedHour; };

}
