#pragma once

#include "market_data.hpp"
#include <deque>

namespace hoi5 {

struct Market {
    static constexpr double weeklyFraction = 7./30.;
    static constexpr double buyMarkup = 1.08, sellMarkdown = .92;
    static constexpr double sellCapacityMultiplier = 2.;
    Stockpile prices, previousPrices, shocks;
    std::vector<Stockpile> countryPrices, countryPreviousPrices, countryShocks, countryDemand, countrySupply;
    std::size_t revision = 0;
    Stockpile demand, supply, externalDemand, externalSupply;
    std::map<std::string_view,std::deque<double>> history;
    std::vector<MarketOrder> contracts;
    std::vector<MarketOrder> unfilled;
    MarketPlan last;

    double base(std::string_view key) const { return value(TRADE_BASE_PRICES,key,60); }
    double price(std::string_view key) const { return std::max(.01,value(prices,key,base(key))); }
    double previousPrice(std::string_view key) const { return std::max(.01,value(previousPrices,key,base(key))); }
    double priceChange(std::string_view key) const { return price(key)/previousPrice(key)-1; }

    double unitPrice(std::string_view key,bool buy) const { return price(key)*(buy ? buyMarkup : sellMarkdown); }
    double countryPrice(int country,std::string_view key) const {
        return country >= 0 && country < int(countryPrices.size())
            ? std::max(.01,value(countryPrices[country],key,price(key))) : price(key);
    }
    double unitPrice(int country,std::string_view key,bool buy) const {
        return countryPrice(country,key)*(buy ? buyMarkup : sellMarkdown);
    }

    double contractAmount(int country,std::string_view resource,bool buy) const {
        double amount = 0.;
        for (const auto& order : contracts)
            if (order.country == country && order.resource == resource && order.buy == buy &&
                std::isfinite(order.amount) && order.amount > 0) amount += order.amount;
        return amount;
    }

    bool changeContract(int country,std::string_view resource,bool buy,double delta,double monthlyLimit) {
        if (country < 0 || !TRADE_BASE_PRICES.contains(resource) || !std::isfinite(delta) || delta == 0) return false;
        contracts = normalizedContracts();
        bool changed = false;
        if (delta > 0) {
            const auto opposite = std::ranges::find_if(contracts,[&](const auto& order) {
                return order.country == country && order.resource == resource && order.buy != buy;
            });
            if (opposite != contracts.end()) {
                const double cancelled = std::min(delta,opposite->amount);
                opposite->amount -= cancelled;
                delta -= cancelled;
                if (opposite->amount <= 0) contracts.erase(opposite);
                changed = cancelled > 0;
            }
            double used = 0.;
            for (const auto& contract : contracts)
                if (contract.country == country && contract.buy == buy) used += contract.amount;
            delta = std::min(delta,std::max(0.,monthlyLimit-used));
        }
        if (delta == 0) return changed;
        auto existing = std::find_if(contracts.begin(),contracts.end(),[&](const MarketOrder& order) {
            return order.country == country && order.resource == resource && order.buy == buy;
        });
        if (existing == contracts.end()) {
            if (delta <= 0) return changed;
            contracts.push_back({country,resource,buy,delta});
        } else {
            existing->amount += delta;
            if (existing->amount <= 0) contracts.erase(existing);
        }
        return true;
    }

    std::vector<MarketOrder> normalizedContracts() const {
        std::vector<MarketOrder> normalized;
        std::map<std::tuple<int,std::string_view,bool>,std::size_t> indices;
        for (const auto& contract : contracts) {
            if (contract.country < 0 || !TRADE_BASE_PRICES.contains(contract.resource) ||
                !std::isfinite(contract.amount) || contract.amount <= 0) continue;
            const auto key = std::tuple{contract.country,contract.resource,contract.buy};
            const auto [entry,inserted] = indices.try_emplace(key,normalized.size());
            if (inserted) normalized.push_back(contract);
            else normalized[entry->second].amount += contract.amount;
        }
        return normalized;
    }

    void updatePriceBook(Stockpile& current,Stockpile& previous,Stockpile& shockBook,
                         const Stockpile& bookDemand,const Stockpile& bookSupply) {
        previous = current;
        Stockpile next;
        for (const auto& [key, baseline] : TRADE_BASE_PRICES) {
            const double totalDemand = value(bookDemand,key), totalSupply = value(bookSupply,key);
            const double imbalance = (totalDemand-totalSupply)/std::max(1.,std::min(totalDemand,totalSupply));
            const double cap = MARKET_MAX_WEEKLY_PRICE_MOVE;
            const double move = std::clamp(imbalance*MARKET_PRICE_ELASTICITY*
                value(MARKET_RESOURCE_VOLATILITY,key,1),-cap,cap);
            double& shock = shockBook[key];
            shock = std::clamp(shock*MARKET_SHOCK_DECAY + move*std::max(0.,MARKET_SHOCK_FACTOR-1),-cap,cap);
            const double target = baseline*std::max(.25,1+move+shock);
            const double old = std::max(.01,value(current,key,baseline));
            next[key] = std::clamp(old+(target-old)*MARKET_PRICE_SMOOTHING,baseline*.25,baseline*4);
        }
        current = next;
        auto linked = current;
        for (const auto& [key, sources] : linkedPrices) {
            if (!current.contains(key)) continue;
            double pressure = 0;
            for (const auto& [source, weight] : sources)
                pressure += (value(current,source,value(previous,source,base(source)))/base(source)-1)*weight;
            const double baseline = base(key);
            linked[key] = std::clamp(current[key]+baseline*pressure*MARKET_LINKED_PRICE_SMOOTHING,
                baseline*.25,baseline*4);
        }
        current = std::move(linked);
    }

    void updatePrices(const std::vector<MarketOrder>& orders, const Stockpile& quotas) {
        demand = supply = externalDemand = externalSupply = quotas;
        for (const auto& order : orders)
            (order.buy ? demand : supply)[order.resource] += order.amount;
        updatePriceBook(prices,previousPrices,shocks,demand,supply);
        for (const auto& [key,current] : prices) {
            auto& series = history[key];
            series.push_back(current);
            if (series.size() > 16) series.pop_front();
        }
        ++revision;
    }

    template<class TradeAllowed,class ExternalAccess>
    void updateCountryPrices(const std::vector<MarketOrder>& orders,const Stockpile& quotas,int countries,
                             TradeAllowed allowed,ExternalAccess externalAccess) {
        countryPrices.resize(countries);
        countryPreviousPrices.resize(countries);
        countryShocks.resize(countries);
        countryDemand.resize(countries);
        countrySupply.resize(countries);
        for (int country = 0; country < countries; ++country) {
            auto& localDemand = countryDemand[country];
            auto& localSupply = countrySupply[country];
            localDemand.clear();
            localSupply.clear();
            if (externalAccess(country)) localDemand = localSupply = quotas;
            for (const auto& order : orders) {
                if (order.country != country && !allowed(country,order.country)) continue;
                (order.buy ? localDemand : localSupply)[order.resource] += order.amount;
            }
            updatePriceBook(countryPrices[country],countryPreviousPrices[country],countryShocks[country],
                localDemand,localSupply);
        }
    }

    template<class Tile>
    static std::vector<double> monthlyCapacity(const std::vector<Tile>& tiles,
                                               const std::vector<StartingProfile>& countries) {
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
        std::vector<double> result(countries.size());
        for (std::size_t i = 0; i < countries.size(); ++i) {
            const auto& t = totals[i];
            const double scale = std::max(.5,countries[i].scale);
            const double logistics = (8000*scale+t.logistics)*(.35+.65*std::clamp(t.supply/std::max(1,t.land),0.,1.));
            result[i] = std::min(logistics,160000*scale);
        }
        return result;
    }

    template<class Tile, class TradeAllowed, class TradePriority, class ExternalAccess, class ExportLimit>
    void execute(const std::vector<Tile>& tiles,std::vector<StartingProfile>& countries,
                 std::vector<Stockpile>& stocks,const std::vector<Stockpile>& capacities,
                 int rotation,TradeAllowed allowed,TradePriority priority,ExternalAccess externalAccess,ExportLimit exportLimit,
                 double fraction = weeklyFraction,bool reprice = true) {
        const auto monthly = monthlyCapacity(tiles,countries);
        double externalCapacity = 0;
        std::vector<std::array<double,2>> limits(countries.size());
        std::vector<double> budgets;
        std::vector<Stockpile> availableStorage(countries.size());
        for (std::size_t i = 0; i < countries.size(); ++i) {
            const double limit = monthly[i]*fraction;
            limits[i] = {sellCapacityMultiplier*limit*exportLimit(int(i)),limit};
            if (externalAccess(int(i)))
                externalCapacity += (1+sellCapacityMultiplier*std::clamp(exportLimit(int(i)),0.,1.))*
                    monthly[i]*weeklyFraction;
            budgets.push_back(std::max(0.,countries[i].budget));
            for (const auto& [bucket,amount] : capacities[i]) availableStorage[i][bucket] = amount;
            for (const auto& [key,amount] : stocks[i]) availableStorage[i][storageBucket(key)] -= amount;
            for (auto& [bucket,amount] : availableStorage[i]) amount = std::max(0.,amount);
        }
        std::vector<MarketOrder> orders;
        for (const auto& contract : normalizedContracts()) {
            const int i = contract.country;
            if (i >= int(countries.size())) continue;
            const auto key = contract.resource;
            auto& capacity = limits[i][contract.buy];
            auto& space = availableStorage[i][storageBucket(key)];
            const double purchasePrice = unitPrice(i,key,true);
            double amount = std::min(contract.amount*fraction,capacity);
            amount = contract.buy ? std::min({amount,space,budgets[i]/purchasePrice})
                                  : std::min(amount,value(stocks[i],key));
            if (amount <= 0) continue;
            orders.push_back({i,key,contract.buy,amount});
            capacity -= amount;
            space += contract.buy ? -amount : amount;
            if (contract.buy) budgets[i] -= amount*purchasePrice;
        }
        Stockpile weeklyQuota, quota;
        for (const auto& [key, basePrice] : TRADE_BASE_PRICES) {
            weeklyQuota[key] = std::max(750.,externalCapacity*std::max(.05,value(MARKET_RESOURCE_RARITY,key,.45))*.55);
            quota[key] = weeklyQuota[key]*fraction/weeklyFraction;
        }
        if (reprice) {
            updatePrices(orders,weeklyQuota);
            updateCountryPrices(orders,weeklyQuota,int(countries.size()),allowed,externalAccess);
        }
        MarketRules rules;
        rules.allowed = allowed;
        rules.priority = priority;
        rules.externalAccess = externalAccess;
        rules.price = [&](auto key,int buyer,int seller) {
            return (countryPrice(buyer,key)+countryPrice(seller,key))*.5;
        };
        rules.externalPrice = [&](auto key,bool buy,int country) { return unitPrice(country,key,buy); };
        rules.budget = [&](int i) { return countries[i].budget; };
        rules.stock = [&](int i,auto key) { return value(stocks[i],key); };
        rules.freeStorage = [&](int i,auto key) { return freeStorage(capacities[i],stocks[i],key); };
        rules.bucket = storageBucket;
        rules.externalSupply = rules.externalDemand = quota;
        last = clearMarket(orders,rules,rotation);
        unfilled.clear();
        for (std::size_t i = 0; i < orders.size(); ++i)
            if (last.remaining[i] > 1e-6) {
                auto order = orders[i];
                order.amount = last.remaining[i];
                unfilled.push_back(order);
            }
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
