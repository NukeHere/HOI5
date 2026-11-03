"""Persistent hex posts: cover a reachable front before concentrating reserves."""
from collections import Counter, deque
import math
from ai_models import division_vector


def deployment_posts(ai, bot, player, wars, excluded=()):
    game = ai.game
    own = {game.tile_key(t): t for t in player.tiles if not game.is_water_tile(t)}
    neighbors = ai.geography.neighbors
    # Components prevent a district assignment from sending units across water
    # or an enemy-held corridor to an unreachable part of the country.
    component = {}
    for seed in sorted(own):
        if seed in component:
            continue
        component[seed] = seed
        queue = deque([seed])
        while queue:
            key = queue.popleft()
            for tile in neighbors[key]:
                other = game.tile_key(tile)
                if other in own and other not in component:
                    component[other] = seed
                    queue.append(other)
    front = {}
    focus = game.player_by_id(bot.expansion_target) if bot.expansion_target is not None else None
    preparation = ai.preparation_target(bot, player) if not wars else None
    occupied = Counter(game.tile_key(d.tile) for d in player.divisions if d.tile)
    previous_posts = set(bot.hex_assignments.values())
    for key, tile in own.items():
        adjacent = [t for t in neighbors[key] if not game.is_water_tile(t) and t.owner is not player]
        if wars:
            adjacent = [t for t in adjacent if t.owner and game.countries_hostile(player, t.owner)]
        if not adjacent:
            continue
        enemies = {d.id: d for d in ai.nearby_enemies(player, tile)} if wars else {}
        threat = sum(division_vector(d)["attack"] for d in enemies.values())
        priority = 2 + getattr(tile, "supply_score", 0) + (2 if occupied[key] else 0)
        priority += int(key in previous_posts)
        if wars:
            priority += threat / 20
        else:
            priority += 2 * any(t.owner is not None for t in adjacent)
            if preparation:
                priority += 20 * any(t.owner is preparation for t in adjacent)
                priority += 4 * getattr(tile, "supply_score", 0)
            if focus and focus.tiles:
                priority += 3 / (1 + game.hex_distance(tile, focus.capital_tile))
        front[key] = dict(priority=priority, threat=threat,
                          mobilization=bool(preparation and any(t.owner is preparation for t in adjacent)))
    units = [d for d in player.divisions if d.id not in excluded and d.tile
             and not d.battle_id and d.route_mode != "retreat"
             and game.tile_key(d.tile) in component]
    if not front:
        bot.front_quotas = {}
        return {}, set()
    if wars and (bot.offensive_focus not in front):
        bot.offensive_focus = max(front, key=lambda k: (getattr(own[k], "supply_score", 0), front[k]["priority"]))
    if not wars:
        bot.offensive_focus = None
    posts, pinned = {}, set()
    quotas = {}
    for group in sorted(set(component.values())):
        local_units = [d for d in units if component[game.tile_key(d.tile)] == group]
        local_front = [k for k in front if component[k] == group]
        mobilization_front = [k for k in local_front if front[k]["mobilization"]]
        if mobilization_front:
            local_front = mobilization_front
        if not local_front or not local_units:
            continue
        # Never reserve the whole army in the rear. At most one is held back.
        reserve = None
        capital = game.tile_key(player.capital_tile) if player.capital_tile else None
        if capital in own and component[capital] == group and capital not in front and len(local_units) >= len(local_front) + 3:
            candidates = [d for d in local_units if d.route_mode != "attack"
                          and (not d.path or d.target_tile is own[capital])]
            reserve = next((d for d in candidates if d.id == bot.reserve_id), None)
            if reserve is None and candidates:
                reserve = min(candidates, key=lambda d: game.hex_distance(d.tile, own[capital]))
            if reserve:
                bot.reserve_id = reserve.id
                posts[reserve.id] = capital
                if reserve.path:
                    pinned.add(reserve.id)
                local_units = [d for d in local_units if d is not reserve]
        selected = sorted(local_front, key=lambda k: (-front[k]["priority"], k))[:len(local_units)]
        quota = {k: 1 for k in selected}
        cap = len(local_units) if len(selected) == 1 else max(2, math.ceil(len(local_units) * .5))
        for _ in range(len(local_units) - len(selected)):
            options = [k for k in selected if quota[k] < cap]
            if not options:
                break
            key = max(options, key=lambda k: (front[k]["priority"] +
                (4 if wars and k == bot.offensive_focus else 0)) / (1 + quota[k]))
            quota[key] += 1
        quotas.update(quota)
        counts = Counter()
        remaining = list(local_units)
        # Finish valid journeys and attacks. A new war may supersede a trip to
        # the old peacetime rear, but it does not interrupt a front reinforcement.
        for d in list(remaining):
            key = game.tile_key(d.target_tile) if d.target_tile else None
            if d.path and d.target_tile and (d.route_mode == "attack" or (key in quota and counts[key] < quota[key])):
                key = game.tile_key(d.target_tile)
                posts[d.id] = key
                if key in quota:
                    counts[key] += 1
                pinned.add(d.id)
                remaining.remove(d)
        # Incumbents keep their hex while its quota allows: no routine return
        # to the district center after capturing neutral territory.
        for d in list(remaining):
            key = game.tile_key(d.tile)
            if key in quota and counts[key] < quota[key]:
                posts[d.id] = key
                counts[key] += 1
                remaining.remove(d)
        slots = [k for k in selected if counts[k] == 0]
        slots += [k for k in selected for _ in range(max(0, quota[k] - counts[k] - (counts[k] == 0)))]
        for key in slots:
            if not remaining:
                break
            d = min(remaining, key=lambda d: game.hex_distance(d.tile, own[key])
                    - (2 if bot.hex_assignments.get(d.id) == key else 0))
            posts[d.id] = key
            counts[key] += 1
            remaining.remove(d)
    bot.front_quotas = quotas
    return posts, pinned
