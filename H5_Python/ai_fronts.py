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
    incoming = {actor for actor, target in game.politics.war_goals if target == player.id}
    for key, tile in own.items():
        adjacent = [t for t in neighbors[key] if not game.is_water_tile(t) and t.owner is not player]
        warning = any(t.owner and t.owner.id in incoming for t in adjacent)
        active = any(t.owner and game.countries_hostile(player, t.owner) for t in adjacent)
        if wars and not (active or warning):
            continue
        if not adjacent:
            continue
        threats = Counter()
        for division in ai.nearby_enemies(player, tile) if wars else ():
            threats[division.owner.id] += division_vector(division)["attack"]
        for nearby in (tile, *neighbors[key]):
            for division in ai.units_by_tile.get(game.tile_key(nearby), ()):
                owner = division.owner
                if owner and owner is not player and owner.id in incoming and not game.countries_hostile(player, owner):
                    threats[owner.id] += division_vector(division)["attack"]
        threat = sum(threats.values())
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
        front[key] = dict(priority=priority, threat=threat, warning=warning, active=active,
                          opponents={t.owner.id for t in adjacent if t.owner and
                                     (t.owner.id in incoming or game.countries_hostile(player, t.owner))},
                          mobilization=bool(preparation and any(t.owner is preparation for t in adjacent)))
    units = [d for d in player.divisions if d.id not in excluded and d.tile
             and not d.battle_id and d.route_mode != "retreat"
             and game.tile_key(d.tile) in component]
    if not front:
        bot.front_quotas = {}
        return {}, set()
    if wars and (bot.offensive_focus not in front):
        bot.offensive_focus = max((k for k in front if front[k]["active"]),
                                  key=lambda k: (getattr(own[k], "supply_score", 0), front[k]["priority"]), default=None)
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
        rank = lambda k: (-front[k]["priority"], k)
        ranked = sorted(local_front, key=rank)
        selected = []
        covered = set()
        # Give each opponent a watch post before distributing the remaining strength.
        for key in sorted(ranked, key=lambda k: (not front[k]["active"], *rank(k))):
            opponents = front[key]["opponents"]
            if opponents - covered:
                selected.append(key)
                covered.update(opponents)
            if len(selected) >= len(local_units):
                break
        pressured = [k for k in ranked if front[k]["threat"] > 0]
        # Under pressure, quiet stretches keep their opponent's watch post.
        # Empty forest hexes must not absorb every spare division as a quota of one.
        candidates = pressured or ranked
        selected += [k for k in candidates if k not in selected][:len(local_units) - len(selected)]
        quota = {k: 1 for k in selected}
        concentrating = sum(front[k]["threat"] > 0 for k in selected) if pressured else len(selected)
        cap = len(local_units) if concentrating <= 1 else max(2, math.ceil(len(local_units) * .5))
        for _ in range(len(local_units) - len(selected)):
            options = [k for k in selected if quota[k] < cap and
                       (not pressured or front[k]["threat"] > 0)]
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
            if d.path and d.target_tile and (d.route_mode == "attack" or key in local_front):
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
            candidates = []
            for d in remaining:
                source = game.tile_key(d.tile)
                if source not in local_front or counts[key] == 0:
                    candidates.append(d)
                elif (counts[source] > 0 and source != key
                      and front[key]["threat"] > 1.5 * front[source]["threat"] + 10):
                    candidates.append(d)
            if not candidates:
                continue
            d = min(candidates, key=lambda d: game.hex_distance(d.tile, own[key])
                    - (2 if bot.hex_assignments.get(d.id) == key else 0))
            posts[d.id] = key
            counts[key] += 1
            remaining.remove(d)
    bot.front_quotas = quotas
    return posts, pinned
