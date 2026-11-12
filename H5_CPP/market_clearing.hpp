#pragma once

#include "starting_economy.hpp"
#include <functional>
#include <optional>

namespace hoi5 {

struct MarketOrder {
    int country;
    std::string_view resource;
    bool buy;
    double amount;
};

struct MarketFill {
    std::optional<int> buyer, seller;
    std::string_view resource;
    double amount, price;
};

struct MarketPlan {
    std::vector<MarketFill> fills;
    std::vector<double> remaining;
};

struct MarketRules {
    std::function<bool(int,int)> allowed;
    std::function<int(int,int)> priority;
    std::function<double(std::string_view,int,int)> price;
    std::function<double(std::string_view,bool,int)> externalPrice;
    std::function<double(int)> budget;
    std::function<double(int,std::string_view)> stock, freeStorage;
    std::function<std::string_view(std::string_view)> bucket;
    std::function<bool(int)> externalAccess;
    Stockpile externalSupply, externalDemand;
};

inline MarketPlan clearMarket(std::span<const MarketOrder> orders, const MarketRules& rules, int rotation) {
    MarketPlan plan;
    std::map<int,double> wallets;
    std::map<std::pair<int,std::string_view>,double> stocks, storage;
    struct Sides { std::vector<std::size_t> buys, sells; };
    std::map<std::string_view,Sides> resources;
    for (std::size_t index = 0; index < orders.size(); ++index) {
        const auto& order = orders[index];
        plan.remaining.push_back(std::max(0.,order.amount));
        wallets.try_emplace(order.country,rules.budget(order.country));
        stocks.try_emplace({order.country,order.resource},std::max(0.,rules.stock(order.country,order.resource)));
        storage.try_emplace({order.country,rules.bucket(order.resource)},
                            std::max(0.,rules.freeStorage(order.country,order.resource)));
        auto& sides = resources[order.resource];
        (order.buy ? sides.buys : sides.sells).push_back(index);
    }
    if (wallets.empty()) return plan;
    const int count = static_cast<int>(wallets.size());
    std::map<int,int> rank;
    int index = 0;
    for (const auto& [country, money] : wallets) rank[country] = (index++ - rotation % count + count) % count;

    using OrderIndex = std::optional<std::size_t>;
    const auto transfer = [&](OrderIndex buy, OrderIndex sell, double amount, double price) {
        if (price <= 0 || !std::isfinite(price)) return 0.;
        const auto resource = orders[buy ? *buy : *sell].resource;
        const auto bucket = rules.bucket(resource);
        std::optional<int> buyer, seller;
        if (buy) {
            buyer = orders[*buy].country;
            amount = std::min({amount, plan.remaining[*buy], wallets[*buyer] / price, storage[{*buyer,bucket}]});
        }
        if (sell) {
            seller = orders[*sell].country;
            amount = std::min({amount, plan.remaining[*sell], stocks[{*seller,resource}]});
        }
        if (amount <= 1e-9) return 0.;
        if (buy) {
            plan.remaining[*buy] -= amount;
            wallets[*buyer] -= amount * price;
            storage[{*buyer,bucket}] -= amount;
            stocks[{*buyer,resource}] += amount;
        }
        if (sell) {
            plan.remaining[*sell] -= amount;
            wallets[*seller] += amount * price;
            storage[{*seller,bucket}] += amount;
            stocks[{*seller,resource}] -= amount;
        }
        plan.fills.push_back({buyer,seller,resource,amount,price});
        return amount;
    };
    const auto quota = [](const Stockpile& values, std::string_view resource) {
        const auto found = values.find(resource);
        return found == values.end() ? 0. : std::max(0.,found->second);
    };
    for (auto& [resource,sides] : resources) {
        std::vector<std::pair<std::size_t,std::size_t>> pairs;
        for (auto buy : sides.buys) for (auto sell : sides.sells)
            if (rules.allowed(orders[buy].country,orders[sell].country)) pairs.emplace_back(buy,sell);
        const auto pairRank = [&](const auto& pair) {
            const int buyer = orders[pair.first].country, seller = orders[pair.second].country;
            return std::tuple{-rules.priority(buyer,seller),rank[buyer],rank[seller]};
        };
        std::stable_sort(pairs.begin(),pairs.end(),[&](const auto& a,const auto& b) { return pairRank(a) < pairRank(b); });
        for (auto [buy,sell] : pairs)
            transfer(buy,sell,std::min(plan.remaining[buy],plan.remaining[sell]),
                rules.price(resource,orders[buy].country,orders[sell].country));
        const auto compare = [&](auto a, auto b) { return rank[orders[a].country] < rank[orders[b].country]; };
        std::stable_sort(sides.sells.begin(),sides.sells.end(),compare);
        std::stable_sort(sides.buys.begin(),sides.buys.end(),compare);
        double demand = quota(rules.externalDemand,resource), supply = quota(rules.externalSupply,resource);
        for (auto sell : sides.sells)
            if (rules.externalAccess(orders[sell].country))
                demand -= transfer({},sell,demand,rules.externalPrice(resource,false,orders[sell].country));
        for (auto buy : sides.buys)
            if (rules.externalAccess(orders[buy].country))
                supply -= transfer(buy,{},supply,rules.externalPrice(resource,true,orders[buy].country));
    }
    return plan;
}

}
