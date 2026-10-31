"""Stable connected geographic districts and their currently controlled fragments."""

from collections import deque


class RegionMap:
    def __init__(self, game, max_tiles=48):
        self.game = game
        self.tile_region = {}
        self.regions = {}
        self.max_tiles = max_tiles
        self.neighbors = {key: tuple(game.neighbor_tiles(tile)) for key, tile in game.hex_lookup.items()}
        self.revision = 0
        self.build()

    def build(self):
        game = self.game
        remaining = {game.tile_key(tile) for tile in game.hex_lookup.values() if not game.is_water_tile(tile)}
        index = 0
        while remaining:
            seed = min(remaining)
            queue = deque([seed])
            queued = {seed}
            members = []
            while queue and len(members) < self.max_tiles:
                key = queue.popleft()
                if key not in remaining:
                    continue
                remaining.remove(key)
                members.append(key)
                self.tile_region[key] = index
                tile = game.tile_for_key(key)
                for neighbor in self.neighbors[key]:
                    neighbor_key = game.tile_key(neighbor)
                    if neighbor_key in remaining and neighbor_key not in queued:
                        queued.add(neighbor_key)
                        queue.append(neighbor_key)
            self.regions[index] = tuple(members)
            index += 1

    def controlled(self, player):
        game = self.game
        remaining = {game.tile_key(tile) for tile in player.tiles if game.tile_key(tile) in self.tile_region}
        result = {}
        while remaining:
            seed = min(remaining)
            base = self.tile_region[seed]
            queue = deque([seed])
            remaining.remove(seed)
            members = []
            while queue:
                key = queue.popleft()
                members.append(key)
                for tile in self.neighbors[key]:
                    other = game.tile_key(tile)
                    if other in remaining and self.tile_region[other] == base:
                        remaining.remove(other)
                        queue.append(other)
            # Base ID is stable; fragment anchor can change after a capture.
            result[(base, player.id, min(members))] = tuple(members)
        return result

    def profile(self, player, members):
        game = self.game
        population = 0
        supply = 0
        buildings = {}
        output = {}
        borders = []
        for key in members:
            tile = game.tile_for_key(key)
            population += game.estimated_tile_population(tile) or 0
            supply += getattr(tile, "supply_score", 0)
            for building, coverage in game.effective_building_coverage_map(tile).items():
                buildings[building] = buildings.get(building, 0) + coverage
            for flows in (getattr(tile, "production_cache", {}) or {}).values():
                for resource, amount in flows.get("outputs", {}).items():
                    output[resource] = output.get(resource, 0) + amount
            if any(n.owner is not player and not game.is_water_tile(n) for n in self.neighbors[key]):
                borders.append(key)
        value = population / 100_000 + sum(buildings.get(k, 0) * w for k, w in
            (("industry", 5), ("refinery", 6), ("oil_gas_rig", 4), ("supply_depot", 3)))
        if player.capital_tile and game.tile_key(player.capital_tile) in members:
            value += 30
        return dict(tiles=members, population=population, supply=supply / max(1, len(members)),
                    buildings=buildings, output=output, borders=borders, importance=value)
