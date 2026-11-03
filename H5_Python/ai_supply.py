"""Choose depots by the supply gain at held/planned military positions."""
from collections import Counter
from Constants import SUPPLY_DECAY_PER_HEX, SUPPLY_SOURCE_RADIUS, SUPPLY_SOURCE_WEIGHTS
from ai_workers import best_supply_site


def supply_site(ai, bot, player):
    game = ai.game
    counts = Counter(game.tile_key(d.tile) for d in player.divisions if d.tile and d.tile.owner is player)
    for key in bot.hex_assignments.values():
        counts[key] += 1
    points = []
    target = ai.preparation_target(bot, player)
    for tile in player.tiles:
        if game.is_water_tile(tile):
            continue
        key = game.tile_key(tile)
        neighbors = game.neighbor_tiles(tile)
        border = any(n.owner and n.owner is not player for n in neighbors)
        mobilization_front = target is not None and any(n.owner is target for n in neighbors)
        weight = counts[key] + (3 if border else 0) + (6 if mobilization_front else 0)
        if weight and getattr(tile, "supply_score", 0) < .55:
            points.append((tile, weight))
    if not points:
        return None
    candidates = []
    queued = {p["tile"] for p in player.construction_queue if p["building"] == "supply_depot"}
    at_war = any(game.countries_hostile(player, other) for other in game.players)
    for tile in player.tiles:
        if game.is_water_tile(tile) or tile in queued:
            continue
        coverage = tile.building_coverage.get("supply_depot", 0)
        if coverage >= .7:
            continue
        strength = min(1, game.tile_supply_source_strength(player, tile)
                       + SUPPLY_SOURCE_WEIGHTS["supply_depot"] * (.7 - coverage))
        multiplier = 1
        if at_war and any(n.owner and game.countries_hostile(player, n.owner)
                          and not game.is_water_tile(n) for n in game.neighbor_tiles(tile)):
            multiplier = .85
        if game.tile_has_active_battle(tile):
            multiplier *= .8
        if game.tile_key(tile) == bot.supply_target:
            multiplier *= 1.2
        candidates.append((game.tile_key(tile), strength, multiplier))
    snapshot = ([(game.tile_key(position), weight, position.passability, getattr(position, "supply_score", 0))
                 for position, weight in points], candidates, SUPPLY_SOURCE_RADIUS, SUPPLY_DECAY_PER_HEX)
    workers = getattr(ai, "workers", None)
    result = (workers.request(("supply", player.id), best_supply_site, snapshot, ai.hour)
              if workers and not workers.closed else best_supply_site(snapshot))
    if result:
        tile = game.tile_for_key(result[1])
        if not tile or tile.owner is not player or tile.building_coverage.get("supply_depot", 0) >= .7:
            return None
    return result
