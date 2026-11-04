#pragma once

#include "market_data.hpp"

namespace hoi5 {

inline double value(const Stockpile& values, std::string_view name, double fallback = 0) {
    const auto it = values.find(name);
    return it == values.end() ? fallback : it->second;
}

struct Market {
    Stockpile prices, previousPrices, shocks;
    std::vector<MarketOrder> contracts;
    MarketPlan last;

    double base(std::string_view key) const { return value(TRADE_BASE_PRICES,key,60); }
    double price(std::string_view key) const { return value(prices,key,base(key)); }

    void changeContract(int country, std::string_view resource, bool buy, double delta) {
        auto existing = std::find_if(contracts.begin(),contracts.end(),[&](const MarketOrder& order) {
            return order.country == country && order.resource == resource && order.buy == buy;
        });
        if (existing == contracts.end()) {
            if (delta > 0) contracts.push_back({country,resource,buy,delta});
        } else {
            existing->amount += delta;
            if (existing->amount <= 0) contracts.erase(existing);
        }
    }

    void updatePrices(const std::vector<MarketOrder>& orders, const Stockpile& quotas) {
        previousPrices = prices;
        Stockpile demand, supply, next;
        for (const auto& order : orders)
            (order.buy ? demand : supply)[order.resource] += order.amount;
        for (const auto& [key, quota] : quotas) {
            const double baseline = base(key);
            const double totalDemand = demand[key]+quota, totalSupply = supply[key]+quota;
            const double imbalance = (totalDemand-totalSupply)/std::max(1.,std::min(totalDemand,totalSupply));
            const double cap = MARKET_MAX_WEEKLY_PRICE_MOVE;
            const double move = std::clamp(imbalance*.10*value(MARKET_RESOURCE_VOLATILITY,key,1),-cap,cap);
            double& shock = shocks[key];
            shock = std::clamp(shock*MARKET_SHOCK_DECAY + move*std::max(0.,MARKET_SHOCK_FACTOR-1),-cap,cap);
            const double target = baseline*std::max(.25,1+move+shock);
            next[key] = std::clamp(price(key)+(target-price(key))*MARKET_PRICE_SMOOTHING,baseline*.25,baseline*4);
        }
        prices = next;
        for (const auto& [key, sources] : linkedPrices) {
            if (!next.contains(key)) continue;
            double pressure = 0;
            for (const auto& [source, weight] : sources)
                pressure += (value(next,source,base(source))/base(source)-1)*weight;
            const double baseline = base(key);
            const double target = baseline*std::max(.25,1+pressure);
            prices[key] = std::clamp(next[key]+(target-next[key])*MARKET_LINKED_PRICE_SMOOTHING,baseline*.25,baseline*4);
        }
    }

    template<class Tile, class TradeAllowed, class TradePriority, class ExternalAccess, class ExportLimit>
    void execute(const std::vector<Tile>& tiles, std::vector<StartingProfile>& countries,
                 std::vector<Stockpile>& stocks, const std::vector<Stockpile>& capacities,
                 int rotation, TradeAllowed allowed, TradePriority priority, ExternalAccess externalAccess, ExportLimit exportLimit, double fraction = 7./30., bool reprice = true) {
        struct Capacity {
            double supply{}, logistics{};
            int land{};
        };
        std::vector<Capacity> totals(countries.size());
        for (const auto& tile : tiles) {
            if (tile.owner < 0 || tile.water) continue;
            auto& total = totals[tile.owner];
            ++total.land;
            total.supply += tile.supply;
            const auto area = [&](Building building) {
                return tile.buildings[building].area*tile.buildings[building].health;
            };
            total.logistics += area(port)*90000 + area(warehouse)*22000 + area(supplyDepot)*12000
                + (area(city)+area(village)*.5)*8000;
        }
        constexpr double week = 7./30.;
        double externalCapacity = 0;
        std::vector<std::array<double,2>> limits(countries.size());
        std::vector<double> budgets;
        std::vector<Stockpile> availableStorage(countries.size());
        for (std::size_t i = 0; i < countries.size(); ++i) {
            const auto& t = totals[i];
            const double scale = std::max(.5,countries[i].scale);
            const double logistics = (8000*scale+t.logistics)*(.35 + .65*t.supply/std::max(1,t.land));
            const double limit = std::min(logistics,160000*scale)*fraction;
            limits[i] = {2*limit*exportLimit(int(i)),limit};
            externalCapacity += 3*limit;
            budgets.push_back(std::max(0.,countries[i].budget));
            for (const auto& [bucket,amount] : capacities[i]) availableStorage[i][bucket] = amount;
            for (const auto& [key,amount] : stocks[i]) availableStorage[i][storageBucket(key)] -= amount;
            for (auto& [bucket,amount] : availableStorage[i]) amount = std::max(0.,amount);
        }
        std::vector<MarketOrder> orders;
        for (const auto& contract : contracts) {
            const int i = contract.country;
            const auto key = contract.resource;
            auto& capacity = limits[i][contract.buy];
            auto& space = availableStorage[i][storageBucket(key)];
            const double unitPrice = base(key)*1.08;
            double amount = std::min(contract.amount*fraction,capacity);
            amount = contract.buy ? std::min({amount,space,budgets[i]/unitPrice})
                                  : std::min(amount,value(stocks[i],key));
            if (amount <= 0) continue;
            orders.push_back({i,key,contract.buy,amount});
            capacity -= amount;
            space += contract.buy ? -amount : amount;
            if (contract.buy) budgets[i] -= amount*unitPrice;
        }
        Stockpile quota;
        for (const auto& [key, amount] : stocks.front())
            quota[key] = std::max(750.,externalCapacity*week/fraction*std::max(.05,value(MARKET_RESOURCE_RARITY,key,.45))*.55)*fraction/week;
        if (reprice) updatePrices(orders,quota);
        MarketRules rules;
        rules.allowed = allowed;
        rules.priority = priority;
        rules.externalAccess = externalAccess;
        rules.price = [&](auto key) { return price(key); };
        rules.externalPrice = [&](auto key,bool buy) { return base(key)*(buy ? 1.08 : .92); };
        rules.budget = [&](int i) { return countries[i].budget; };
        rules.stock = [&](int i,auto key) { return value(stocks[i],key); };
        rules.freeStorage = [&](int i,auto key) { return freeStorage(capacities[i],stocks[i],key); };
        rules.bucket = storageBucket;
        rules.externalSupply = rules.externalDemand = quota;
        last = clearMarket(orders,rules,rotation);
        for (const auto& fill : last.fills) {
            if (fill.seller) {
                stocks[*fill.seller][fill.resource] -= fill.amount;
                countries[*fill.seller].budget += fill.amount*fill.price;
            }
            if (fill.buyer) {
                stocks[*fill.buyer][fill.resource] += fill.amount;
                countries[*fill.buyer].budget -= fill.amount*fill.price;
            }
        }
    }
};

}
