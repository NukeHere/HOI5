"""Finite market clearing. Planning does not mutate countries or orders."""


def clear_market(orders, *, allowed, priority, price, external_price,
                 external_supply, external_demand, stock, free_storage, bucket,
                 external_access, rotation=0):
    remaining = [max(0.0, float(order["amount"])) for order in orders]
    # Sale proceeds must cover an existing deficit before financing new purchases.
    wallets = {o["player"].id: float(o["player"].budget) for o in orders}
    stocks = {}
    storage = {}
    fills = []
    for order in orders:
        player, resource = order["player"], order["resource"]
        stocks.setdefault((player.id, resource), max(0.0, stock(player, resource)))
        storage.setdefault((player.id, bucket(resource)), max(0.0, free_storage(player, resource)))

    def transfer(buy_index, sell_index, available, unit_price):
        if unit_price <= 0:
            return 0.0
        buy = orders[buy_index] if buy_index is not None else None
        sell = orders[sell_index] if sell_index is not None else None
        resource = (buy or sell)["resource"]
        amount = available
        if buy:
            buyer = buy["player"].id
            amount = min(amount, remaining[buy_index], wallets[buyer] / unit_price,
                         storage[(buyer, bucket(resource))])
        if sell:
            seller = sell["player"].id
            amount = min(amount, remaining[sell_index], stocks[(seller, resource)])
        if amount <= 1e-9:
            return 0.0
        if buy:
            remaining[buy_index] -= amount
            wallets[buyer] -= amount * unit_price
            storage[(buyer, bucket(resource))] -= amount
            stocks[(buyer, resource)] += amount
        if sell:
            remaining[sell_index] -= amount
            wallets[seller] += amount * unit_price
            storage[(seller, bucket(resource))] += amount
            stocks[(seller, resource)] -= amount
        fills.append({"buyer": buy["player"] if buy else None,
                      "seller": sell["player"] if sell else None,
                      "resource": resource, "amount": amount, "price": unit_price})
        return amount

    by_resource = {}
    for index, order in enumerate(orders):
        by_resource.setdefault(order["resource"], {"buy": [], "sell": []})[order["mode"]].append(index)
    count = max(1, len(wallets))
    rank = {pid: (index - rotation) % count for index, pid in enumerate(sorted(wallets))}
    for resource, sides in sorted(by_resource.items()):
        pairs = [(b, s) for b in sides["buy"] for s in sides["sell"]
                 if allowed(orders[b]["player"].id, orders[s]["player"].id)]
        # Rotate equal-priority countries each execution to avoid permanent ID advantage.
        pairs.sort(key=lambda pair: (-priority(orders[pair[0]]["player"].id, orders[pair[1]]["player"].id),
                                     rank[orders[pair[0]]["player"].id], rank[orders[pair[1]]["player"].id]))
        for b, s in pairs:
            transfer(b, s, min(remaining[b], remaining[s]), price(resource))
        # External quotas are shared, not regenerated for every participant.
        supply = max(0, external_supply.get(resource, 0))
        demand = max(0, external_demand.get(resource, 0))
        for s in sorted(sides["sell"], key=lambda i: rank[orders[i]["player"].id]):
            if external_access(orders[s]["player"]):
                demand -= transfer(None, s, demand, external_price(resource, "sell"))
        for b in sorted(sides["buy"], key=lambda i: rank[orders[i]["player"].id]):
            if external_access(orders[b]["player"]):
                supply -= transfer(b, None, supply, external_price(resource, "buy"))
    return fills, remaining
