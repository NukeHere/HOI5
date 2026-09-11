import math
import random
import time

from Constants import *


class EconomySystemMixin:
    @staticmethod
    def empty_resource_totals():
        return {"raw": {}}

    @staticmethod
    def empty_resource_stockpiles():
        return {
            "raw": {},
            "semi_finished": {},
            "finished": {},
        }

    @staticmethod
    def empty_production_cache():
        return {
            stage: {"inputs": {}, "outputs": {}}
            for stage in PRODUCTION_STAGES
        }

    @staticmethod
    def resource_names_for_category(category_key):
        if category_key == "raw":
            return RAW_RESOURCE_NAMES
        if category_key == "semi_finished":
            return SEMI_FINISHED_RESOURCE_NAMES
        if category_key == "finished":
            return FINISHED_RESOURCE_NAMES
        return []

    @staticmethod
    def resource_category_for_key(resource_key):
        if resource_key in FINISHED_RESOURCE_NAMES:
            return "finished"
        if resource_key in SEMI_FINISHED_RESOURCE_NAMES:
            return "semi_finished"
        return "raw"

    def player_starting_scale(self, player=None, land_tile_count=None):
        if land_tile_count is None and player is not None:
            land_tile_count = sum(1 for tile in player.tiles if not self.is_water_tile(tile))
        land_tile_count = land_tile_count or STARTING_REFERENCE_LAND_TILES
        territory_scale = land_tile_count / STARTING_REFERENCE_LAND_TILES
        map_scale = max(0.65, min(1.8, self.map_size / STARTING_REFERENCE_MAP_SIZE))
        scale = territory_scale * (map_scale ** 0.45)
        return max(STARTING_MIN_SCALE, min(STARTING_MAX_SCALE, scale))

    def apply_starting_profile(self, player):
        scale = self.player_starting_scale(player)
        player.starting_scale = scale
        player.population = round(STARTING_POPULATION * scale)
        player.budget = STARTING_BUDGET * (0.65 + scale * 0.35)
        self.create_starting_stockpiles(player, scale)

    @staticmethod
    def scaled_starting_infrastructure_budget(scale):
        budget_scale = max(0.45, min(2.6, scale ** 0.88))
        return {
            key: value * budget_scale
            for key, value in STARTING_INFRASTRUCTURE_BUDGET.items()
        }

    def create_starting_stockpiles(self, player, scale=1.0):
        rng = random.Random((self.world_seed + 1) * 1009)
        stockpiles = self.empty_resource_stockpiles()

        for category_key, (min_amount, max_amount) in STARTING_STOCK_RANGES.items():
            for resource_key in self.resource_names_for_category(category_key):
                multiplier = STARTING_STOCK_MULTIPLIERS.get(resource_key, 1.0)
                amount = rng.uniform(min_amount, max_amount) * multiplier * scale
                stockpiles[category_key][resource_key] = amount

        player.resource_stockpiles = stockpiles
        return stockpiles

    def ensure_player_stockpiles(self, player):
        stockpiles = player.resource_stockpiles or self.empty_resource_stockpiles()
        changed = False
        scale = getattr(player, "starting_scale", self.player_starting_scale(player))

        for category_key, (min_amount, max_amount) in STARTING_STOCK_RANGES.items():
            bucket = stockpiles.setdefault(category_key, {})
            for resource_key in self.resource_names_for_category(category_key):
                if resource_key in bucket:
                    continue
                resource_seed = sum((index + 1) * ord(char) for index, char in enumerate(resource_key))
                rng = random.Random((self.world_seed + 1) * 1009 + player.id * 7919 + resource_seed)
                multiplier = STARTING_STOCK_MULTIPLIERS.get(resource_key, 1.0)
                bucket[resource_key] = rng.uniform(min_amount, max_amount) * multiplier * scale
                changed = True

        if changed or player.resource_stockpiles is None:
            player.resource_stockpiles = stockpiles
            self.mark_player_stockpiles_changed(player)
        return stockpiles

    @staticmethod
    def mark_player_resource_balance_dirty(player):
        if player:
            player.resource_balance_dirty = True

    @staticmethod
    def mark_player_storage_dirty(player):
        if player:
            player.storage_dirty = True
            player.tile_stockpiles_dirty = True
            player.resource_balance_dirty = True

    def mark_player_stockpiles_changed(self, player):
        self.mark_player_resource_balance_dirty(player)
        if player:
            player.tile_stockpiles_dirty = True

    def cached_resource_balance_breakdown(self, player, max_age=0.35):
        if not player:
            return {}
        now = time.time()
        last_update = getattr(player, "resource_balance_last_update", 0.0)
        if (
            not player.resource_balance_breakdown
            or last_update <= 0
            or (player.resource_balance_dirty and now - last_update >= max_age)
        ):
            return self.recalculate_resource_balance_breakdown(player)
        return player.resource_balance_breakdown

    def ensure_player_storage(self, player):
        if not player:
            return self.empty_storage_summary(), self.empty_storage_summary(), self.empty_storage_summary()
        if (
            player.storage_dirty
            or not player.storage_capacity
            or not player.storage_used
            or not player.storage_overflow
        ):
            return self.recalculate_player_storage(player)
        return player.storage_capacity, player.storage_used, player.storage_overflow

    def ensure_player_tile_stockpiles(self, player):
        if player and getattr(player, "tile_stockpiles_dirty", True):
            self.distribute_player_stockpiles_to_tiles(player)

    @staticmethod
    def empty_tile_stockpiles():
        return {
            "raw": {},
            "semi_finished": {},
            "finished": {},
        }

    @staticmethod
    def storage_bucket_for_resource(resource_key):
        return "fuel" if resource_key in FUEL_STORAGE_RESOURCE_KEYS else EconomySystemMixin.resource_category_for_key(resource_key)

    @staticmethod
    def empty_storage_summary():
        return {category: 0.0 for category in STORAGE_CATEGORIES}

    def tile_storage_capacity_by_category(self, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        capacities = self.empty_storage_summary()
        for category_key, building_values in STORAGE_CAPACITY_BY_COVERAGE.items():
            for building_key, capacity_per_coverage in building_values.items():
                capacities[category_key] += (
                    self.effective_building_coverage(tile, building_key, coverage.get(building_key, 0.0))
                    * capacity_per_coverage
                )
        for building_key, capacity_per_coverage in FUEL_STORAGE_CAPACITY_BY_COVERAGE.items():
            capacities["fuel"] += (
                self.effective_building_coverage(tile, building_key, coverage.get(building_key, 0.0))
                * capacity_per_coverage
            )
        return capacities

    def tile_storage_capacity(self, tile, category_key=None):
        capacities = self.tile_storage_capacity_by_category(tile)
        if category_key:
            return capacities.get(category_key, 0.0)
        return sum(capacities.get(key, 0.0) for key in ("raw", "semi_finished", "finished"))

    def tile_fuel_storage_capacity(self, tile):
        return self.tile_storage_capacity(tile, "fuel")

    def tile_storage_used_by_category(self, tile):
        used = self.empty_storage_summary()
        for category_bucket in (getattr(tile, "resource_stockpiles", {}) or {}).values():
            for resource_key, amount in category_bucket.items():
                storage_key = self.storage_bucket_for_resource(resource_key)
                used[storage_key] = used.get(storage_key, 0.0) + max(0.0, amount)
        return used

    def storage_summary_for_tiles(self, tiles):
        capacity = self.empty_storage_summary()
        used = self.empty_storage_summary()
        for tile in tiles:
            tile_capacity = self.tile_storage_capacity_by_category(tile)
            tile_used = self.tile_storage_used_by_category(tile)
            for category_key in STORAGE_CATEGORIES:
                capacity[category_key] += tile_capacity.get(category_key, 0.0)
                used[category_key] += tile_used.get(category_key, 0.0)
        return capacity, used

    def recalculate_player_storage(self, player):
        capacity = self.empty_storage_summary()
        used = self.empty_storage_summary()
        efficiency = (player.production_modifiers or {}).get("storage_efficiency", 1.0)

        for tile in player.tiles:
            tile_capacity = self.tile_storage_capacity_by_category(tile)
            for category_key, amount in tile_capacity.items():
                capacity[category_key] += amount * efficiency

        stockpiles = self.ensure_player_stockpiles(player)
        for category_key, bucket in stockpiles.items():
            for resource_key, amount in bucket.items():
                storage_key = self.storage_bucket_for_resource(resource_key)
                used[storage_key] = used.get(storage_key, 0.0) + max(0.0, amount)

        overflow = {
            category_key: max(0.0, used.get(category_key, 0.0) - capacity.get(category_key, 0.0))
            for category_key in STORAGE_CATEGORIES
        }
        player.storage_capacity = capacity
        player.storage_used = used
        player.storage_overflow = overflow
        player.storage_dirty = False
        return capacity, used, overflow

    def storage_free_capacity_for_resource(self, player, resource_key):
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_key = self.storage_bucket_for_resource(resource_key)
        return max(0.0, capacity.get(storage_key, 0.0) - used.get(storage_key, 0.0))

    def enforce_player_storage_capacity(self, player):
        capacity, used, overflow = self.recalculate_player_storage(player)
        if not any(amount > 0 for amount in overflow.values()):
            return overflow

        stockpiles = self.ensure_player_stockpiles(player)
        removed = self.empty_storage_summary()
        for storage_key, overflow_amount in overflow.items():
            if overflow_amount <= 0:
                continue
            resources = []
            for category_key, bucket in stockpiles.items():
                for resource_key, amount in bucket.items():
                    if amount > 0 and self.storage_bucket_for_resource(resource_key) == storage_key:
                        resources.append((category_key, resource_key, amount))
            total_amount = sum(amount for _category, _key, amount in resources)
            if total_amount <= 0:
                continue
            keep_ratio = max(0.0, min(1.0, capacity.get(storage_key, 0.0) / total_amount))
            for category_key, resource_key, amount in resources:
                new_amount = amount * keep_ratio
                stockpiles[category_key][resource_key] = new_amount
                removed[storage_key] += max(0.0, amount - new_amount)

        self.recalculate_player_storage(player)
        player.tile_stockpiles_dirty = False
        player.storage_overflow = removed
        return removed

    def distribute_player_stockpiles_to_tiles(self, player):
        for tile in player.tiles:
            tile.resource_stockpiles = self.empty_tile_stockpiles()

        capacity_tiles = {
            category_key: []
            for category_key in STORAGE_CATEGORIES
        }
        for tile in player.tiles:
            capacities = self.tile_storage_capacity_by_category(tile)
            for category_key, capacity in capacities.items():
                if capacity > 0:
                    capacity_tiles[category_key].append((tile, capacity))

        if not any(capacity_tiles[key] for key in ("raw", "semi_finished", "finished")):
            fallback_tile = player.capital_tile or next((tile for tile in player.tiles if not self.is_water_tile(tile)), None)
            if fallback_tile:
                self.set_tile_building_coverage(fallback_tile, "warehouse", 0.12, INFRASTRUCTURE_COVERAGE_LIMITS["warehouse"][1])
                capacities = self.tile_storage_capacity_by_category(fallback_tile)
                for category_key in ("raw", "semi_finished", "finished"):
                    capacity_tiles[category_key] = [(fallback_tile, capacities.get(category_key, 0.0))]
        if not capacity_tiles["fuel"]:
            fallback_tile = player.capital_tile or next((tile for tile in player.tiles if not self.is_water_tile(tile)), None)
            if fallback_tile:
                self.set_tile_building_coverage(fallback_tile, "fuel_storage", 0.14, INFRASTRUCTURE_COVERAGE_LIMITS["fuel_storage"][1])
                capacity_tiles["fuel"] = [(fallback_tile, self.tile_fuel_storage_capacity(fallback_tile))]

        total_capacity = {
            category_key: sum(capacity for _tile, capacity in tiles)
            for category_key, tiles in capacity_tiles.items()
        }

        self.enforce_player_storage_capacity(player)
        stockpiles = self.ensure_player_stockpiles(player)
        for category_key, bucket in stockpiles.items():
            for resource_key, amount in bucket.items():
                if amount <= 0:
                    continue
                storage_key = self.storage_bucket_for_resource(resource_key)
                target_tiles = capacity_tiles.get(storage_key, [])
                target_capacity = total_capacity.get(storage_key, 0.0)
                if target_capacity <= 0:
                    continue
                for tile, capacity in target_tiles:
                    share = capacity / target_capacity
                    tile_bucket = tile.resource_stockpiles.setdefault(category_key, {})
                    tile_bucket[resource_key] = tile_bucket.get(resource_key, 0.0) + amount * share

        self.recalculate_player_storage(player)

    @staticmethod
    def add_resource_amount(bucket, key, amount):
        bucket[key] = bucket.get(key, 0.0) + max(0.0, amount)

    @staticmethod
    def raw_amount(raw, key):
        return raw.get(key, 0.0)

    def recalculate_state_resources(self, player):
        totals = self.empty_resource_totals()
        raw = totals["raw"]
        sources = {}

        for tile in player.tiles:
            tile_resources = set()
            for resource in tile.resources:
                if len(resource) < 3:
                    continue
                name, _depth, mass = resource
                amount = float(mass)
                self.add_resource_amount(raw, name, amount)
                if amount > 0:
                    tile_resources.add(name)
            for name in tile_resources:
                sources[name] = sources.get(name, 0) + 1

        player.resource_totals = totals
        player.resource_sources = sources
        self.mark_player_resource_balance_dirty(player)
        return totals

    def recalculate_all_state_resources(self):
        for player in self.players:
            self.recalculate_state_resources(player)

    def tile_supply_source_strength(self, player, tile):
        if not tile or self.is_water_tile(tile):
            return 0.0
        coverage = getattr(tile, "building_coverage", {}) or {}
        strength = 0.0
        for building_key, weight in SUPPLY_SOURCE_WEIGHTS.items():
            strength += self.effective_building_coverage(tile, building_key, coverage.get(building_key, 0.0)) * weight
        if tile == player.capital_tile:
            strength += 0.85
        return self.clamp01(strength)

    def recalculate_player_supply(self, player):
        land_tiles = [tile for tile in player.tiles if not self.is_water_tile(tile)]
        if not land_tiles:
            player.supply_summary = {"average": 0.0, "low_tiles": 0, "critical_tiles": 0}
            return player.supply_summary

        sources = [
            (tile, strength)
            for tile in land_tiles
            for strength in [self.tile_supply_source_strength(player, tile)]
            if strength > 0
        ]
        if not sources and player.capital_tile:
            sources = [(player.capital_tile, 0.65)]

        total_supply = 0.0
        low_tiles = 0
        critical_tiles = 0
        for tile in land_tiles:
            passability = self.clamp01(getattr(tile, "passability", 0.0))
            best = 0.0
            for source_tile, strength in sources:
                distance = self.hex_distance(tile, source_tile)
                if distance > SUPPLY_SOURCE_RADIUS:
                    continue
                distance_factor = SUPPLY_DECAY_PER_HEX ** distance
                passability_factor = 0.42 + passability * 0.58
                best = max(best, strength * distance_factor * passability_factor)
            tile.supply_score = self.clamp01(best)
            total_supply += tile.supply_score
            if tile.supply_score < 0.25:
                critical_tiles += 1
            elif tile.supply_score < 0.50:
                low_tiles += 1

        for _pass_index in range(2):
            changed_tiles = []
            for tile in land_tiles:
                coverage = getattr(tile, "building_coverage", {}) or {}
                relay_strength = sum(
                    self.effective_building_coverage(tile, building_key, coverage.get(building_key, 0.0)) * weight
                    for building_key, weight in SUPPLY_RELAY_BUILDING_WEIGHTS.items()
                )
                if relay_strength <= 0:
                    continue
                tile_passability = self.clamp01(getattr(tile, "passability", 0.0))
                for neighbor in self.neighbor_tiles(tile):
                    if neighbor.owner != player or self.is_water_tile(neighbor):
                        continue
                    inbound = getattr(neighbor, "supply_score", 0.0) * (0.46 + relay_strength * 0.38) * (
                        0.62 + tile_passability * 0.28
                    )
                    if inbound > getattr(tile, "supply_score", 0.0) + 0.001:
                        changed_tiles.append((tile, self.clamp01(inbound)))
                if getattr(tile, "supply_score", 0.0) <= 0.35:
                    continue
                relay_value = self.clamp01(tile.supply_score * (0.42 + relay_strength))
                for neighbor in self.neighbor_tiles(tile):
                    if neighbor.owner != player or self.is_water_tile(neighbor):
                        continue
                    passability = self.clamp01(getattr(neighbor, "passability", 0.0))
                    candidate = relay_value * (0.58 + passability * 0.30)
                    if candidate > getattr(neighbor, "supply_score", 0.0) + 0.001:
                        changed_tiles.append((neighbor, self.clamp01(candidate)))
            for tile, value in changed_tiles:
                tile.supply_score = max(getattr(tile, "supply_score", 0.0), value)

        total_supply = 0.0
        low_tiles = 0
        critical_tiles = 0
        for tile in land_tiles:
            total_supply += getattr(tile, "supply_score", 0.0)
            if tile.supply_score < 0.25:
                critical_tiles += 1
            elif tile.supply_score < 0.50:
                low_tiles += 1

        for tile in player.tiles:
            if self.is_water_tile(tile):
                tile.supply_score = 0.0

        average = total_supply / max(1, len(land_tiles))
        player.supply_summary = {
            "average": average,
            "low_tiles": low_tiles,
            "critical_tiles": critical_tiles,
        }
        return player.supply_summary

    def recalculate_all_supply_scores(self):
        for player in self.players:
            self.recalculate_player_supply(player)

    @staticmethod
    def add_production_amount(cache, stage, direction, key, amount):
        if amount <= 0:
            return
        bucket = cache[stage][direction]
        bucket[key] = bucket.get(key, 0.0) + amount

    def merge_production_cache(self, target, source, multiplier=1.0):
        for stage in PRODUCTION_STAGES:
            for direction in ["inputs", "outputs"]:
                for key, amount in source.get(stage, {}).get(direction, {}).items():
                    self.add_production_amount(target, stage, direction, key, amount * multiplier)

    @staticmethod
    def specialization_efficiency(allocation, penalty=0.9, free_specializations=1):
        sector_count = sum(1 for value in allocation.values() if value > 0)
        penalty_steps = max(0, sector_count - free_specializations)
        return penalty ** penalty_steps

    @staticmethod
    def normalize_industry_allocation(allocation):
        clean_sectors = [
            sector
            for sector, value in (allocation or {}).items()
            if sector in INDUSTRY_SECTOR_LABELS and value > 0
        ]
        if not clean_sectors:
            clean_sectors = ["consumer_goods"]
        clean_sectors = list(dict.fromkeys(clean_sectors))
        share = 1.0 / max(1, len(clean_sectors))
        return {
            sector: share
            for sector in clean_sectors
        }

    def resource_score_near_tile(self, player, tile, weights, radius=3):
        score = self.weighted_resource_score(tile, weights)
        return self.clamp01(score + self.nearby_resource_score(player, tile, weights, radius) * 0.75)

    def industry_sector_scores(self, player, tile):
        scores = {}
        for sector, weights in INDUSTRY_SECTOR_RESOURCE_WEIGHTS.items():
            scores[sector] = self.resource_score_near_tile(player, tile, weights, radius=3) if weights else 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_village = self.nearby_coverage_score(player, tile, ["village"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        nearby_mine = self.nearby_coverage_score(player, tile, ["mine"], 2)
        nearby_refinery = self.nearby_coverage_score(player, tile, ["refinery"], 2)
        passability = self.clamp01(getattr(tile, "passability", 0.0))

        scores["consumer_goods"] = self.clamp01(
            0.16
            + nearby_city * 0.82
            + nearby_village * 0.34
            + passability * 0.20
        )
        scores["machinery"] += nearby_city * 0.28 + nearby_mine * 0.24 + passability * 0.14
        scores["vehicles"] += nearby_city * 0.20 + nearby_port * 0.18 + nearby_refinery * 0.14 + passability * 0.12
        scores["metallurgy"] += nearby_mine * 0.18
        scores["construction_materials"] += nearby_city * 0.16 + nearby_mine * 0.10
        scores["chemicals"] += nearby_refinery * 0.24 + nearby_city * 0.10
        scores["electronics"] += nearby_city * 0.30 + passability * 0.08
        scores["shipbuilding"] += nearby_port * 0.65
        scores["weapons"] += nearby_city * 0.12 + scores["metallurgy"] * 0.14

        return {key: self.clamp01(value) for key, value in scores.items()}

    def assign_industry_allocation(self, player, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        if coverage.get("industry", 0.0) <= 0:
            tile.industry_allocation = {}
            return {}

        ranked = sorted(
            self.industry_sector_scores(player, tile).items(),
            key=lambda item: item[1],
            reverse=True,
        )
        ranked = [(sector, score) for sector, score in ranked if score > 0.05]
        if not ranked:
            ranked = [("consumer_goods", 0.5)]

        sectors = [ranked[0][0]]
        if len(ranked) > 1 and ranked[1][1] >= ranked[0][1] * 0.72:
            sectors.append(ranked[1][0])
        if len(ranked) > 2 and ranked[2][1] >= ranked[0][1] * 0.88:
            sectors.append(ranked[2][0])

        tile.industry_allocation = self.normalize_industry_allocation({
            sector: 1.0
            for sector in sectors
        })
        return tile.industry_allocation

    def add_consumer_goods_share_to_tile(self, tile, target_share):
        allocation = self.normalize_industry_allocation(getattr(tile, "industry_allocation", {}) or {})
        current_share = allocation.get("consumer_goods", 0.0)
        if current_share >= target_share:
            return False

        sectors = [key for key in allocation if key != "consumer_goods"]
        sectors.insert(0, "consumer_goods")
        while len(sectors) > 1 and 1.0 / len(sectors) < target_share:
            sectors.pop()
        tile.industry_allocation = self.normalize_industry_allocation({
            sector: 1.0
            for sector in sectors
        })
        return True

    def ensure_starting_consumer_goods_industry(self, player):
        industry_tiles = [
            tile
            for tile in player.tiles
            if (getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0) > 0
        ]
        if not industry_tiles:
            return

        total_coverage = sum((getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0) for tile in industry_tiles)
        if total_coverage <= 0:
            return

        def consumer_goods_coverage():
            return sum(
                (getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0)
                * (getattr(tile, "industry_allocation", {}) or {}).get("consumer_goods", 0.0)
                for tile in industry_tiles
            )

        target_coverage = total_coverage * STARTING_CONSUMER_GOODS_INDUSTRY_SHARE
        if consumer_goods_coverage() >= target_coverage:
            return

        ranked_tiles = sorted(
            industry_tiles,
            key=lambda tile: (
                -self.industry_sector_scores(player, tile).get("consumer_goods", 0.0),
                -((getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0)),
                tile.q,
                tile.r,
            ),
        )
        for tile in ranked_tiles:
            if consumer_goods_coverage() >= target_coverage:
                break
            self.add_consumer_goods_share_to_tile(tile, STARTING_CONSUMER_GOODS_TILE_SHARE)

    def assign_starting_industry_allocations(self, player):
        for tile in player.tiles:
            self.assign_industry_allocation(player, tile)
        self.ensure_starting_consumer_goods_industry(player)

    def calculate_tile_production_cache(self, player, tile):
        cache = self.empty_production_cache()
        raw_coverage = getattr(tile, "building_coverage", {}) or {}
        coverage = self.effective_building_coverage_map(tile)
        modifiers = player.production_modifiers

        mine_coverage = coverage.get("mine", 0.0)
        if mine_coverage > 0:
            mining_efficiency = modifiers.get("mining_efficiency", 1.0)
            for resource in getattr(tile, "resources", []):
                if len(resource) < 3:
                    continue
                key, _depth, mass = resource
                if key not in RAW_RESOURCE_NAMES:
                    continue
                if key in OIL_GAS_RESOURCE_KEYS:
                    continue
                abundance = min(1.0, math.log10(max(0.0, float(mass)) + 1) / math.log10(1_500_000 + 1))
                weight = STARTING_MINE_RESOURCE_WEIGHTS.get(key, 0.35)
                output = mine_coverage * abundance * (0.55 + weight) * mining_efficiency * 5200
                self.add_production_amount(cache, "raw", "outputs", key, output)

        rig_coverage = coverage.get("oil_gas_rig", 0.0)
        if rig_coverage > 0:
            mining_efficiency = modifiers.get("mining_efficiency", 1.0)
            for resource in getattr(tile, "resources", []):
                if len(resource) < 3:
                    continue
                key, _depth, mass = resource
                if key not in OIL_GAS_RESOURCE_KEYS:
                    continue
                abundance = min(1.0, math.log10(max(0.0, float(mass)) + 1) / math.log10(1_500_000 + 1))
                weight = STARTING_OIL_GAS_RIG_RESOURCE_WEIGHTS.get(key, 0.8)
                output = rig_coverage * abundance * (0.62 + weight) * mining_efficiency * 5600
                self.add_production_amount(cache, "raw", "outputs", key, output)

        farms_coverage = coverage.get("farms", 0.0)
        if farms_coverage > 0:
            agriculture_efficiency = modifiers.get("agriculture_efficiency", 1.0)
            base_output = (
                farms_coverage
                * self.agriculture_score(tile)
                * agriculture_efficiency
                * FARM_FOOD_BASE_RATE
            )
            self.add_production_amount(cache, "raw", "outputs", "food", base_output)
            self.add_production_amount(
                cache,
                "agriculture",
                "inputs",
                "fertilizer",
                farms_coverage * FERTILIZER_CONSUMPTION_PER_FARM_COVERAGE,
            )
            self.add_production_amount(cache, "agriculture", "outputs", "food", base_output * FERTILIZER_FOOD_BONUS)

        allocation = getattr(tile, "industry_allocation", None)
        if allocation is None or (raw_coverage.get("industry", 0.0) > 0 and not allocation):
            allocation = self.assign_industry_allocation(player, tile)
        elif raw_coverage.get("industry", 0.0) > 0:
            allocation = self.normalize_industry_allocation(allocation)
            tile.industry_allocation = allocation
        specialization_efficiency = self.specialization_efficiency(
            allocation,
            modifiers.get("industry_diversification_penalty", 0.9),
            modifiers.get("industry_free_specializations", 1),
        )

        for stage in ["semi_finished", "finished"]:
            for recipe in PRODUCTION_RECIPES[stage].values():
                required_tech = recipe.get("requires_tech")
                if required_tech and required_tech not in getattr(player, "technologies", set()):
                    continue
                building = recipe.get("building", "industry")
                building_coverage = coverage.get(building, 0.0)
                if building_coverage <= 0:
                    continue

                sector = recipe["sector"]
                if building == "industry":
                    sector_share = allocation.get(sector, 0.0)
                    if sector_share <= 0:
                        continue
                    efficiency = modifiers.get("industry_efficiency", 1.0) * specialization_efficiency
                elif building == "refinery":
                    sector_share = 1.0
                    efficiency = modifiers.get("refining_efficiency", 1.0)
                else:
                    sector_share = 1.0
                    efficiency = 1.0

                planned_units = recipe["base_rate"] * building_coverage * sector_share * efficiency
                if planned_units <= 0:
                    continue
                for key, amount in recipe.get("inputs", {}).items():
                    self.add_production_amount(cache, stage, "inputs", key, amount * planned_units)
                for key, amount in recipe.get("outputs", {}).items():
                    self.add_production_amount(cache, stage, "outputs", key, amount * planned_units)

        tile.production_cache = cache
        return cache

    def add_state_life_support_to_production_cache(self, player):
        population_millions = max(0.0, (player.population or 0.0) / 1_000_000)
        for key, amount in LIFE_SUPPORT_CONSUMPTION_PER_MILLION.items():
            self.add_production_amount(
                player.production_cache,
                "upkeep",
                "inputs",
                key,
                amount * population_millions,
            )

        for tile in player.tiles:
            coverage = self.effective_building_coverage_map(tile)
            for building, upkeep in SETTLEMENT_UPKEEP_PER_COVERAGE.items():
                building_coverage = coverage.get(building, 0.0)
                if building_coverage <= 0:
                    continue
                for key, amount in upkeep.items():
                    self.add_production_amount(
                        player.production_cache,
                        "upkeep",
                        "inputs",
                        key,
                        amount * building_coverage,
                    )

    def recalculate_state_production_cache(self, player):
        player.production_cache = self.empty_production_cache()
        for tile in player.tiles:
            cache = self.calculate_tile_production_cache(player, tile)
            self.merge_production_cache(player.production_cache, cache)
        self.add_state_life_support_to_production_cache(player)
        return player.production_cache

    def recalculate_all_state_production_caches(self):
        for player in self.players:
            self.recalculate_state_production_cache(player)

    def update_tile_production_cache(self, tile):
        player = getattr(tile, "owner", None)
        if not player:
            tile.production_cache = self.empty_production_cache()
            return tile.production_cache
        self.recalculate_state_production_cache(player)
        return getattr(tile, "production_cache", None) or self.empty_production_cache()

    def production_amount_for_key(self, player, key, direction):
        cache = player.production_cache or self.empty_production_cache()
        return sum(
            cache[stage][direction].get(key, 0.0)
            for stage in PRODUCTION_STAGES
        )

    def resource_output_source_tiles(self, player, resource_key):
        if not player:
            return []
        if not player.production_cache:
            self.recalculate_state_production_cache(player)

        source_tiles = []
        for tile in player.tiles:
            cache = getattr(tile, "production_cache", None)
            if not cache:
                cache = self.calculate_tile_production_cache(player, tile)
            output = sum(
                cache[stage]["outputs"].get(resource_key, 0.0)
                for stage in PRODUCTION_STAGES
            )
            if output > 0:
                source_tiles.append((tile, output))
        return source_tiles

    @staticmethod
    def breakdown_with_percent(items):
        total = sum(amount for _label, amount in items)
        if total <= 0:
            return [(label, amount, 0.0) for label, amount in items]
        return [(label, amount, amount / total * 100.0) for label, amount in items]

    def production_breakdown_from_flows(self, flows, resource_key):
        stage_outputs = flows["stage_outputs"]
        items = [
            ("Добыча/фермы", stage_outputs.get("raw", {}).get(resource_key, 0.0)),
            ("Удобрения", stage_outputs.get("agriculture", {}).get(resource_key, 0.0)),
            ("Промышленность", (
                stage_outputs.get("semi_finished", {}).get(resource_key, 0.0)
                + stage_outputs.get("finished", {}).get(resource_key, 0.0)
            )),
            ("Импорт", flows["trade_outputs"].get(resource_key, 0.0)),
        ]
        return self.breakdown_with_percent(items)

    def resource_production_breakdown(self, player, resource_key):
        if not player:
            return []
        return self.production_breakdown_from_flows(self.estimate_monthly_resource_flows(player), resource_key)

    def consumption_breakdown_from_flows(self, flows, resource_key):
        stage_inputs = flows["stage_inputs"]
        construction = flows["construction_inputs"].get(resource_key, 0.0)
        industry = sum(
            stage_inputs.get(stage, {}).get(resource_key, 0.0)
            for stage in ("semi_finished", "agriculture", "finished")
        )
        upkeep = stage_inputs.get("upkeep", {}).get(resource_key, 0.0)
        army = flows.get("army_inputs", {}).get(resource_key, 0.0)
        exports = flows["trade_inputs"].get(resource_key, 0.0)
        items = [
            ("Армия", army),
            ("Стройки", construction),
            ("Производство", industry),
            ("Поддержание", upkeep),
            ("Экспорт", exports),
        ]
        return self.breakdown_with_percent(items)

    def resource_consumption_breakdown(self, player, resource_key):
        if not player:
            return []
        return self.consumption_breakdown_from_flows(self.estimate_monthly_resource_flows(player), resource_key)

    def all_resource_keys_for_category(self, player, category_key, flows=None):
        keys = set(self.resource_names_for_category(category_key))
        stockpiles = self.ensure_player_stockpiles(player)
        keys.update(stockpiles.get(category_key, {}).keys())
        if category_key == "raw":
            keys.update((player.resource_totals or {}).get("raw", {}).keys())
        if flows:
            keys.update(
                key
                for key in set(flows["inputs"]) | set(flows["outputs"])
                if self.resource_category_for_key(key) == category_key
            )
        return sorted(keys, key=lambda key: self.resource_display_name(key))

    def recalculate_resource_balance_breakdown(self, player):
        if not player:
            return {}
        if not player.resource_totals:
            self.recalculate_state_resources(player)
        if not player.production_cache:
            self.recalculate_state_production_cache(player)

        stockpiles = self.ensure_player_stockpiles(player)
        flows = self.estimate_monthly_resource_flows(player)
        breakdown = {
            category_key: {}
            for category_key in ["raw", "semi_finished", "finished"]
        }
        for category_key in breakdown:
            ground = (player.resource_totals or {}).get("raw", {}) if category_key == "raw" else {}
            for resource_key in self.all_resource_keys_for_category(player, category_key, flows):
                stock = stockpiles.get(category_key, {}).get(resource_key, 0.0)
                production = flows["outputs"].get(resource_key, 0.0)
                consumption = flows["inputs"].get(resource_key, 0.0)
                breakdown[category_key][resource_key] = {
                    "key": resource_key,
                    "ground": ground.get(resource_key, None) if category_key == "raw" else None,
                    "stock": stock,
                    "production": production,
                    "consumption": consumption,
                    "balance": production - consumption,
                    "months": self.resource_duration_months(stock, production, consumption),
                    "production_breakdown": self.production_breakdown_from_flows(flows, resource_key),
                    "consumption_breakdown": self.consumption_breakdown_from_flows(flows, resource_key),
                }
        player.resource_balance_breakdown = breakdown
        player.resource_balance_dirty = False
        player.resource_balance_last_update = time.time()
        return breakdown

    def estimate_monthly_resource_flows(self, player):
        stockpiles = self.ensure_player_stockpiles(player)
        cache = player.production_cache or self.recalculate_state_production_cache(player)
        simulated_stockpiles = {
            category: dict(resources)
            for category, resources in stockpiles.items()
        }
        simulated_capacity, simulated_used, _overflow = self.ensure_player_storage(player)
        simulated_capacity = dict(simulated_capacity)
        simulated_used = dict(simulated_used)
        flows = {
            "inputs": {},
            "outputs": {},
            "stage_inputs": {stage: {} for stage in PRODUCTION_STAGES},
            "stage_outputs": {stage: {} for stage in PRODUCTION_STAGES},
            "construction_inputs": {},
            "army_inputs": {},
            "trade_inputs": {},
            "trade_outputs": {},
            "trade_money": 0.0,
            "trade_capacity_used": 0.0,
            "trade_capacity_limit": self.trade_capacity_per_month(player),
        }

        def add_amount(bucket, key, amount):
            if amount <= 0:
                return
            bucket[key] = bucket.get(key, 0.0) + amount

        def stock_amount(key):
            category = self.resource_category_for_key(key)
            return simulated_stockpiles.setdefault(category, {}).get(key, 0.0)

        def add_stock(key, amount):
            if amount <= 0:
                return 0.0
            storage_key = self.storage_bucket_for_resource(key)
            free_capacity = max(
                0.0,
                simulated_capacity.get(storage_key, 0.0) - simulated_used.get(storage_key, 0.0),
            )
            accepted = min(amount, free_capacity)
            if accepted <= 0:
                return 0.0
            category = self.resource_category_for_key(key)
            bucket = simulated_stockpiles.setdefault(category, {})
            bucket[key] = bucket.get(key, 0.0) + accepted
            simulated_used[storage_key] = simulated_used.get(storage_key, 0.0) + accepted
            return accepted

        def consume_stock(key, amount):
            if amount <= 0:
                return 0.0
            category = self.resource_category_for_key(key)
            bucket = simulated_stockpiles.setdefault(category, {})
            available = bucket.get(key, 0.0)
            consumed = min(available, amount)
            bucket[key] = max(0.0, available - consumed)
            storage_key = self.storage_bucket_for_resource(key)
            simulated_used[storage_key] = max(0.0, simulated_used.get(storage_key, 0.0) - consumed)
            return consumed

        def record_input(stage, key, amount):
            add_amount(flows["inputs"], key, amount)
            add_amount(flows["stage_inputs"].setdefault(stage, {}), key, amount)

        def record_output(stage, key, amount):
            add_amount(flows["outputs"], key, amount)
            add_amount(flows["stage_outputs"].setdefault(stage, {}), key, amount)

        trade_flows = self.estimate_monthly_trade_flows(player)
        flows["trade_money"] = trade_flows["money_balance"]
        flows["trade_capacity_used"] = trade_flows["capacity_used"]
        flows["trade_capacity_limit"] = trade_flows["capacity_limit"]
        for key, amount in trade_flows["imports"].items():
            accepted = add_stock(key, amount)
            add_amount(flows["outputs"], key, accepted)
            add_amount(flows["trade_outputs"], key, accepted)
        for key, amount in trade_flows["exports"].items():
            exported = consume_stock(key, amount)
            add_amount(flows["inputs"], key, exported)
            add_amount(flows["trade_inputs"], key, exported)

        for stage in PRODUCTION_STAGES:
            if stage == "agriculture":
                planned_fertilizer = cache["agriculture"]["inputs"].get("fertilizer", 0.0)
                planned_bonus_food = cache["agriculture"]["outputs"].get("food", 0.0)
                if planned_fertilizer > 0 and planned_bonus_food > 0:
                    consumed = consume_stock("fertilizer", planned_fertilizer)
                    fertilizer_ratio = self.clamp01(consumed / planned_fertilizer)
                    bonus_food = planned_bonus_food * fertilizer_ratio
                    record_input(stage, "fertilizer", consumed)
                    if bonus_food > 0:
                        accepted = add_stock("food", bonus_food)
                        record_output(stage, "food", accepted)
                continue

            planned_inputs = {
                key: amount
                for key, amount in cache[stage]["inputs"].items()
                if amount > 0
            }
            planned_outputs = {
                key: amount
                for key, amount in cache[stage]["outputs"].items()
                if amount > 0
            }

            if stage == "upkeep":
                for key, required in planned_inputs.items():
                    consumed = consume_stock(key, required)
                    record_input(stage, key, consumed)
                continue

            actual_ratio = 1.0
            for key, required in planned_inputs.items():
                actual_ratio = min(actual_ratio, stock_amount(key) / required)
            actual_ratio = self.clamp01(actual_ratio)

            for key, required in planned_inputs.items():
                consumed = consume_stock(key, required * actual_ratio)
                record_input(stage, key, consumed)
            for key, output in planned_outputs.items():
                actual_output = output * actual_ratio
                accepted = add_stock(key, actual_output)
                record_output(stage, key, accepted)

        for key, amount in self.estimate_active_construction_consumption(player, stock_amount).items():
            consumed = consume_stock(key, amount)
            add_amount(flows["inputs"], key, consumed)
            add_amount(flows["construction_inputs"], key, consumed)

        for key, amount in self.estimate_monthly_army_consumption(player, stock_amount).items():
            consumed = consume_stock(key, amount)
            add_amount(flows["inputs"], key, consumed)
            add_amount(flows["army_inputs"], key, consumed)

        return flows

    def estimate_active_construction_consumption(self, player, stock_amount_func):
        if not player.construction_queue:
            return {}
        projects = self.active_construction_projects(player)
        if not projects:
            return {}
        build_power = self.build_power(player) / max(1, len(projects))
        totals = {}
        for project in projects:
            project_build_power = build_power * self.construction_project_speed_multiplier(project)
            status_info = self.evaluate_construction_project_status(
                player,
                project,
                month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
                stock_amount_func=stock_amount_func,
                build_power=project_build_power,
            )
            if not self.construction_project_is_active_status(status_info["status"]):
                continue
            monthly_delta = self.construction_project_progress_delta(
                player,
                project,
                month_fraction=1.0,
                build_power=project_build_power,
            )
            for key, amount in self.construction_project_resource_needs(project, monthly_delta).items():
                totals[key] = totals.get(key, 0.0) + amount
        return totals

    def stockpile_amount(self, player, key):
        category = self.resource_category_for_key(key)
        return self.ensure_player_stockpiles(player).get(category, {}).get(key, 0.0)

    def add_to_stockpile(self, player, key, amount):
        if amount <= 0:
            return 0.0
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_key = self.storage_bucket_for_resource(key)
        free_capacity = max(0.0, capacity.get(storage_key, 0.0) - used.get(storage_key, 0.0))
        accepted = min(amount, free_capacity)
        if accepted <= 0:
            return 0.0
        category = self.resource_category_for_key(key)
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(category, {})
        bucket[key] = bucket.get(key, 0.0) + accepted
        player.storage_used[storage_key] = player.storage_used.get(storage_key, 0.0) + accepted
        player.storage_overflow[storage_key] = max(
            0.0,
            player.storage_used.get(storage_key, 0.0) - player.storage_capacity.get(storage_key, 0.0),
        )
        self.mark_player_stockpiles_changed(player)
        return accepted

    def consume_from_stockpile(self, player, key, amount):
        if amount <= 0:
            return 0.0
        category = self.resource_category_for_key(key)
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(category, {})
        available = bucket.get(key, 0.0)
        consumed = min(available, amount)
        bucket[key] = max(0.0, available - consumed)
        self.ensure_player_storage(player)
        storage_key = self.storage_bucket_for_resource(key)
        player.storage_used[storage_key] = max(0.0, player.storage_used.get(storage_key, 0.0) - consumed)
        player.storage_overflow[storage_key] = max(
            0.0,
            player.storage_used.get(storage_key, 0.0) - player.storage_capacity.get(storage_key, 0.0),
        )
        if consumed > 0:
            self.mark_player_stockpiles_changed(player)
        return consumed

    def add_to_stockpile_unsafe(self, player, key, amount):
        if not player or amount <= 0:
            return 0.0
        category = self.resource_category_for_key(key)
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(category, {})
        bucket[key] = bucket.get(key, 0.0) + amount
        self.mark_player_storage_dirty(player)
        return amount

    def initialize_player_manpower_reserve(self, player):
        summary = self.population_demographic_summary(player)
        fielded = sum(max(0, getattr(division, "max_manpower", division.manpower)) for division in player.divisions)
        player.manpower_reserve = max(0.0, summary.get("mobilization_available", 0.0) - fielded)
        return player.manpower_reserve

    def seed_starting_military_stockpiles(self, player):
        if not player or not getattr(player, "divisions", None):
            return {}
        reserve = {}
        for division in player.divisions:
            for key, capacity in (division.supply_capacity or {}).items():
                reserve[key] = reserve.get(key, 0.0) + max(0.0, capacity) * DIVISION_STARTING_ARMY_STOCK_MULT
        for key, amount in reserve.items():
            self.add_to_stockpile_unsafe(player, key, amount)
        return reserve

    def division_supply_ratio(self, division):
        if not division or not division.tile:
            return 0.0
        supply = self.clamp01(getattr(division.tile, "supply_score", 0.0))
        if division.tile.owner is not division.owner:
            supply *= DIVISION_FOREIGN_TILE_SUPPLY_MULT
        return self.clamp01(supply)

    def consume_division_supply(self, division, key, amount):
        if amount <= 0:
            return 0.0
        stock = division.supply_stock.setdefault(key, 0.0)
        consumed = min(stock, amount)
        division.supply_stock[key] = max(0.0, stock - consumed)
        return consumed

    def division_strength_reinforcement_requirements(self, division, strength_delta):
        if strength_delta <= 0:
            return 0.0, {}
        strength_ratio = strength_delta / max(1.0, division.max_strength)
        manpower_needed = max(0.0, division.max_manpower - division.manpower) * strength_ratio
        if manpower_needed <= 0:
            manpower_needed = division.max_manpower * strength_ratio * 0.85
        resources = {}
        for key in DIVISION_EQUIPMENT_LOSS_KEYS:
            capacity = (division.supply_capacity or {}).get(key, 0.0)
            if capacity <= 0:
                continue
            resources[key] = capacity * strength_ratio * 0.42
        return manpower_needed, resources

    def replenish_division(self, division, elapsed_hours):
        if elapsed_hours <= 0 or not division.owner:
            return 0.0
        supply = self.division_supply_ratio(division)
        division.last_supply_ratio = supply
        if supply <= 0:
            division.last_reinforcement_ratio = 0.0
            return 0.0

        in_battle_mult = DIVISION_COMBAT_REINFORCEMENT_MULT if division.battle_id else 1.0
        fill_fraction = DIVISION_REINFORCEMENT_SUPPLY_FILL_PER_DAY * elapsed_hours / 24.0 * supply * in_battle_mult
        for key, capacity in (division.supply_capacity or {}).items():
            capacity = max(0.0, capacity)
            if capacity <= 0:
                continue
            current = min(capacity, division.supply_stock.get(key, 0.0))
            missing = capacity - current
            if missing <= 0:
                continue
            requested = min(missing, capacity * fill_fraction)
            consumed = self.consume_from_stockpile(division.owner, key, requested)
            if consumed > 0:
                division.supply_stock[key] = current + consumed

        if division.strength >= division.max_strength or division.manpower >= division.max_manpower:
            division.last_reinforcement_ratio = 1.0
            return 0.0

        max_strength_delta = (
            DIVISION_REINFORCEMENT_STRENGTH_PER_DAY
            * elapsed_hours
            / 24.0
            * supply
            * in_battle_mult
        )
        strength_delta = min(max_strength_delta, division.max_strength - division.strength)
        manpower_needed, resource_needs = self.division_strength_reinforcement_requirements(division, strength_delta)
        ratios = []
        if manpower_needed > 0:
            ratios.append(max(0.0, division.owner.manpower_reserve) / manpower_needed)
        for key, required in resource_needs.items():
            if required > 0:
                ratios.append(self.stockpile_amount(division.owner, key) / required)
        actual_ratio = self.clamp01(min(ratios) if ratios else 1.0)
        actual_strength = strength_delta * actual_ratio
        if actual_strength <= 0:
            division.last_reinforcement_ratio = 0.0
            return 0.0

        if manpower_needed > 0:
            manpower_used = min(division.owner.manpower_reserve, manpower_needed * actual_ratio)
            division.owner.manpower_reserve = max(0.0, division.owner.manpower_reserve - manpower_used)
            division.manpower = min(division.max_manpower, division.manpower + int(round(manpower_used)))
        for key, required in resource_needs.items():
            self.consume_from_stockpile(division.owner, key, required * actual_ratio)
        division.strength = min(division.max_strength, division.strength + actual_strength)
        division.last_reinforcement_ratio = actual_ratio
        return actual_strength

    def consume_division_combat_supplies(self, division, elapsed_hours):
        if elapsed_hours <= 0:
            return 1.0
        ratios = []
        for key, amount_per_hour in (division.combat_supply_use or {}).items():
            required = max(0.0, amount_per_hour) * elapsed_hours
            if required <= 0:
                continue
            consumed = self.consume_division_supply(division, key, required)
            ratios.append(consumed / required)
        return self.clamp01(min(ratios) if ratios else 1.0)

    def division_can_use_supply_key(self, division, key):
        return bool(
            (division.supply_capacity or {}).get(key, 0.0) > 0
            or (division.supply_stock or {}).get(key, 0.0) > 0
            or (division.combat_supply_use or {}).get(key, 0.0) > 0
        )

    def add_attack_supply_requirement(self, requirements, channel, key, amount):
        if amount <= 0:
            return
        bucket = requirements.setdefault(channel, {})
        bucket[key] = max(bucket.get(key, 0.0), amount)

    def division_attack_supply_requirements(self, division, target=None, elapsed_hours=1.0):
        requirements = {"soft": {}, "front": {}, "top": {}, "support": {}}
        elapsed_hours = max(0.0, float(elapsed_hours))
        if not division or elapsed_hours <= 0:
            return requirements

        soft_attack = max(0.0, float(getattr(division, "soft_attack", 0.0)))
        front_attack = max(0.0, float(getattr(division, "hard_front_attack", 0.0)))
        top_attack = max(0.0, float(getattr(division, "hard_top_attack", 0.0)))
        for key, factor in DIVISION_ATTACK_AMMO_SOFT_FACTORS.items():
            if self.division_can_use_supply_key(division, key):
                self.add_attack_supply_requirement(requirements, "soft", key, soft_attack * factor * elapsed_hours)
        for key, factor in DIVISION_ATTACK_AMMO_FRONT_FACTORS.items():
            if self.division_can_use_supply_key(division, key):
                self.add_attack_supply_requirement(requirements, "front", key, front_attack * factor * elapsed_hours)
        for key, factor in DIVISION_ATTACK_AMMO_TOP_FACTORS.items():
            if self.division_can_use_supply_key(division, key):
                self.add_attack_supply_requirement(requirements, "top", key, top_attack * factor * elapsed_hours)

        legacy_channels = {
            "small_arms_ammo": "soft",
            "light_artillery_ammo": "top",
            "old_at_missiles": "front",
            "autocannon_ammo": "front",
            "tank_ammo": "front",
            "artillery_ammo": "top",
            "refined_fuel": "support",
            "field_supplies": "support",
        }
        for key, amount_per_hour in (division.combat_supply_use or {}).items():
            if key in {"light_aa_ammo", "anti_air_ammo"}:
                continue
            channel = legacy_channels.get(key, "support")
            self.add_attack_supply_requirement(
                requirements,
                channel,
                key,
                max(0.0, amount_per_hour) * elapsed_hours,
            )

        field_supply_need = (
            DIVISION_ATTACK_FIELD_SUPPLY_BASE
            + max(1.0, float(getattr(division, "front_width", 20.0))) / 20.0 * DIVISION_ATTACK_FIELD_SUPPLY_PER_WIDTH
            + (soft_attack + front_attack + top_attack) * DIVISION_ATTACK_FIELD_SUPPLY_PER_ATTACK
        ) * elapsed_hours
        self.add_attack_supply_requirement(requirements, "support", "field_supplies", field_supply_need)
        fuel_need = (
            self.clamp01(float(getattr(division, "vehicle_share", 0.0)))
            * max(0.1, float(getattr(division, "speed", 1.0)))
            * DIVISION_ATTACK_FUEL_USE_PER_VEHICLE_SHARE
            * elapsed_hours
        )
        if self.division_can_use_supply_key(division, "refined_fuel"):
            self.add_attack_supply_requirement(requirements, "support", "refined_fuel", fuel_need)
        return requirements

    def consume_attack_supply_bucket(self, division, bucket):
        ratios = []
        consumed = {}
        for key, required in (bucket or {}).items():
            required = max(0.0, required)
            if required <= 0:
                continue
            amount = self.consume_division_supply(division, key, required)
            ratios.append(amount / required)
            consumed[key] = consumed.get(key, 0.0) + amount
        return self.clamp01(min(ratios) if ratios else 1.0), consumed

    def consume_division_attack_supplies(self, division, target=None, elapsed_hours=1.0):
        requirements = self.division_attack_supply_requirements(division, target, elapsed_hours)
        ratios = {}
        consumed = {}
        for channel in ("soft", "front", "top", "support"):
            ratio, channel_consumed = self.consume_attack_supply_bucket(division, requirements.get(channel, {}))
            ratios[channel] = ratio
            for key, amount in channel_consumed.items():
                consumed[key] = consumed.get(key, 0.0) + amount
        support_ratio = ratios.get("support", 1.0)
        for channel in ("soft", "front", "top"):
            ratios[channel] = self.clamp01(min(ratios.get(channel, 1.0), support_ratio))
        ratios["overall"] = self.clamp01(min(ratios.values()) if ratios else 1.0)
        division.last_attack_supply_requirements = requirements
        division.last_attack_supply_consumed = consumed
        division.last_attack_supply_ratios = ratios
        return ratios

    def combat_ammo_factor(self, ratio):
        return DIVISION_AMMO_ATTACK_FLOOR + (1.0 - DIVISION_AMMO_ATTACK_FLOOR) * self.clamp01(ratio)

    def consume_division_movement_supplies(self, division, elapsed_hours):
        if elapsed_hours <= 0:
            return 1.0
        needs = {
            "refined_fuel": max(0.0, division.vehicle_share * division.speed * 1.8 * elapsed_hours),
            "field_supplies": max(0.0, 0.12 * elapsed_hours),
        }
        ratios = []
        for key, required in needs.items():
            if required <= 0:
                continue
            consumed = self.consume_division_supply(division, key, required)
            ratios.append(consumed / required)
        if not ratios:
            return 1.0
        return 0.55 + self.clamp01(min(ratios)) * 0.45

    def apply_division_strength_losses(self, division, strength_damage, equipment_loss_multiplier=1.0):
        actual_damage = min(max(0.0, strength_damage), max(0.0, division.strength))
        if actual_damage <= 0:
            return 0.0
        loss_ratio = actual_damage / max(1.0, division.max_strength)
        manpower_loss = division.max_manpower * loss_ratio * DIVISION_MANPOWER_STRENGTH_LOSS_MULT
        division.manpower = max(0, int(round(division.manpower - manpower_loss)))
        for key in DIVISION_EQUIPMENT_LOSS_KEYS:
            capacity = (division.supply_capacity or {}).get(key, 0.0)
            if capacity <= 0:
                continue
            current = division.supply_stock.get(key, 0.0)
            loss = min(
                current,
                capacity * loss_ratio * DIVISION_EQUIPMENT_STRENGTH_LOSS_MULT * max(0.0, equipment_loss_multiplier),
            )
            division.supply_stock[key] = max(0.0, current - loss)
        for key in DIVISION_COMBAT_STOCK_LOSS_KEYS:
            capacity = (division.supply_capacity or {}).get(key, 0.0)
            current = division.supply_stock.get(key, 0.0)
            if capacity <= 0 or current <= 0:
                continue
            loss = min(
                current,
                capacity * loss_ratio * DIVISION_COMBAT_STOCK_STRENGTH_LOSS_MULT * max(0.0, equipment_loss_multiplier),
            )
            division.supply_stock[key] = max(0.0, current - loss)
        division.strength = max(0.0, division.strength - actual_damage)
        return actual_damage

    def estimate_monthly_army_consumption(self, player, stock_amount_func=None):
        if not player:
            return {}
        stock_amount_func = stock_amount_func or (lambda key: self.stockpile_amount(player, key))
        planned = {}

        def add_need(key, amount):
            if amount > 0:
                planned[key] = planned.get(key, 0.0) + amount

        for division in getattr(player, "divisions", []) or []:
            supply = self.division_supply_ratio(division)
            if supply <= 0:
                continue
            battle_mult = DIVISION_COMBAT_REINFORCEMENT_MULT if division.battle_id else 1.0
            fill_fraction = DIVISION_REINFORCEMENT_SUPPLY_FILL_PER_DAY * 30.0 * supply * battle_mult
            for key, capacity in (division.supply_capacity or {}).items():
                missing = max(0.0, capacity - division.supply_stock.get(key, 0.0))
                add_need(key, min(missing, capacity * fill_fraction))
            if division.battle_id:
                for key, per_hour in (division.combat_supply_use or {}).items():
                    add_need(key, per_hour * 24.0 * 30.0)
            strength_delta = min(
                division.max_strength - division.strength,
                DIVISION_REINFORCEMENT_STRENGTH_PER_DAY * 30.0 * supply * battle_mult,
            )
            _manpower_needed, resource_needs = self.division_strength_reinforcement_requirements(division, strength_delta)
            for key, amount in resource_needs.items():
                add_need(key, amount)

        capped = {}
        for key, amount in planned.items():
            available = stock_amount_func(key)
            capped[key] = min(amount, available)
        return capped

    def tradeable_resource_keys(self, category_key=None):
        categories = [category_key] if category_key else ["raw", "semi_finished", "finished"]
        keys = []
        for category in categories:
            for resource_key in self.resource_names_for_category(category):
                if resource_key not in keys:
                    keys.append(resource_key)
        return keys

    def normalized_trade_contracts(self, contracts):
        normalized = []
        seen = {}
        tradeable_keys = set(self.tradeable_resource_keys())
        for contract in contracts or []:
            resource_key = contract.get("resource")
            mode = contract.get("mode")
            amount = max(0.0, float(contract.get("amount", 0.0)))
            if resource_key not in tradeable_keys or mode not in ("buy", "sell") or amount <= 0:
                continue
            contract_key = (resource_key, mode)
            if contract_key in seen:
                normalized[seen[contract_key]]["amount"] += amount
            else:
                seen[contract_key] = len(normalized)
                normalized.append({"resource": resource_key, "mode": mode, "amount": amount})
        return normalized

    def normalize_trade_contracts(self, player):
        current_contracts = player.trade_contracts or []
        normalized = self.normalized_trade_contracts(current_contracts)
        if current_contracts != normalized:
            player.trade_contracts = normalized
            player.trade_contract_revision = getattr(player, "trade_contract_revision", 0) + 1
        return normalized

    def trade_contract_amount(self, player, resource_key, mode):
        for contract in self.normalized_trade_contracts(getattr(player, "trade_contracts", [])):
            if contract["resource"] == resource_key and contract["mode"] == mode:
                return contract["amount"]
        return 0.0

    def adjust_trade_contract(self, player, resource_key, mode, delta):
        if not player or resource_key not in self.tradeable_resource_keys() or mode not in ("buy", "sell"):
            return False
        contracts = self.normalize_trade_contracts(player)
        opposite = "sell" if mode == "buy" else "buy"
        remaining_delta = max(0.0, delta)
        changed = False
        if delta > 0:
            for contract in list(contracts):
                if contract["resource"] == resource_key and contract["mode"] == opposite:
                    removed = min(contract["amount"], remaining_delta)
                    contract["amount"] -= removed
                    remaining_delta -= removed
                    changed = changed or removed > 0
                    if remaining_delta <= 0:
                        break
            if remaining_delta <= 0:
                player.trade_contracts = [contract for contract in contracts if contract["amount"] > 0]
                if changed:
                    player.trade_contract_revision = getattr(player, "trade_contract_revision", 0) + 1
                    self.recalculate_monthly_balance(player)
                    self.mark_player_resource_balance_dirty(player)
                return True

        if delta > 0:
            used_capacity = sum(
                contract["amount"]
                for contract in contracts
                if contract["mode"] == mode
            )
            free_capacity = max(0.0, self.trade_capacity_per_month(player, mode) - used_capacity)
            applied_delta = min(remaining_delta, free_capacity)
            if applied_delta <= 0:
                player.trade_contracts = [contract for contract in contracts if contract["amount"] > 0]
                if changed:
                    player.trade_contract_revision = getattr(player, "trade_contract_revision", 0) + 1
                    self.recalculate_monthly_balance(player)
                    self.mark_player_resource_balance_dirty(player)
                return changed
        else:
            applied_delta = delta

        for contract in contracts:
            if contract["resource"] == resource_key and contract["mode"] == mode:
                old_amount = contract["amount"]
                contract["amount"] = max(0.0, contract["amount"] + applied_delta)
                changed = changed or contract["amount"] != old_amount
                break
        else:
            if applied_delta > 0:
                contracts.append({"resource": resource_key, "mode": mode, "amount": applied_delta})
                changed = True

        player.trade_contracts = [contract for contract in contracts if contract["amount"] > 0]
        if changed:
            player.trade_contract_revision = getattr(player, "trade_contract_revision", 0) + 1
            self.recalculate_monthly_balance(player)
            self.mark_player_resource_balance_dirty(player)
        return changed

    def market_base_price(self, resource_key):
        market_state = getattr(self.simulation_server, "market_state", None)
        if market_state:
            return market_state.ensure_resource(resource_key)
        if resource_key in TRADE_BASE_PRICES:
            return float(TRADE_BASE_PRICES[resource_key])
        category = self.resource_category_for_key(resource_key)
        if category == "finished":
            return 420.0
        if category == "semi_finished":
            return 160.0
        return 60.0

    def market_current_price(self, resource_key):
        market_state = getattr(self.simulation_server, "market_state", None)
        if not market_state:
            return self.market_base_price(resource_key)
        market_state.ensure_resource(resource_key)
        return max(0.01, market_state.current_prices.get(resource_key, self.market_base_price(resource_key)))

    def market_previous_price(self, resource_key):
        market_state = getattr(self.simulation_server, "market_state", None)
        if not market_state:
            return self.market_base_price(resource_key)
        market_state.ensure_resource(resource_key)
        return max(0.01, market_state.previous_prices.get(resource_key, self.market_base_price(resource_key)))

    def market_price_change_fraction(self, resource_key):
        previous = self.market_previous_price(resource_key)
        current = self.market_current_price(resource_key)
        if previous <= 0:
            return 0.0
        return current / previous - 1.0

    def market_unit_price(self, resource_key, mode):
        price = self.market_current_price(resource_key)
        if mode == "buy":
            return price * TRADE_BUY_PRICE_MARKUP
        return price * TRADE_SELL_PRICE_MARKDOWN

    def trade_unit_price(self, player, resource_key, mode):
        return self.market_unit_price(resource_key, mode)

    @staticmethod
    def trade_mode_capacity_multiplier(mode):
        if mode == "sell":
            return TRADE_SELL_LIMIT_MULTIPLIER
        if mode == "buy":
            return 1.0
        return 1.0 + TRADE_SELL_LIMIT_MULTIPLIER

    def trade_logistics_capacity_per_month(self, player, mode=None):
        coverage_totals = {}
        for tile in player.tiles:
            for key, value in (getattr(tile, "building_coverage", {}) or {}).items():
                coverage_totals[key] = coverage_totals.get(key, 0.0) + self.effective_building_coverage(tile, key, value)
        supply = (player.supply_summary or {}).get("average", 1.0)
        logistics = (player.production_modifiers or {}).get("logistics_efficiency", 1.0)
        port_capacity = coverage_totals.get("port", 0.0) * TRADE_PORT_CAPACITY_PER_COVERAGE
        warehouse_capacity = coverage_totals.get("warehouse", 0.0) * TRADE_WAREHOUSE_CAPACITY_PER_COVERAGE
        supply_depot_capacity = coverage_totals.get("supply_depot", 0.0) * TRADE_SUPPLY_DEPOT_CAPACITY_PER_COVERAGE
        settlement_capacity = (
            coverage_totals.get("city", 0.0)
            + coverage_totals.get("village", 0.0) * 0.5
        ) * TRADE_SETTLEMENT_CAPACITY_PER_COVERAGE
        scale = getattr(player, "starting_scale", 1.0)
        base_capacity = TRADE_BASE_CAPACITY * max(0.5, scale)
        supply_factor = 0.35 + self.clamp01(supply) * 0.65
        capacity = max(
            0.0,
            (base_capacity + port_capacity + warehouse_capacity + supply_depot_capacity + settlement_capacity)
            * logistics
            * supply_factor,
        )
        return capacity * self.trade_mode_capacity_multiplier(mode)

    def trade_max_capacity_per_month(self, player, mode=None):
        scale = getattr(player, "starting_scale", 1.0)
        modifiers = player.trade_modifiers or {}
        external_limit = modifiers.get("external_market_limit", 1.0)
        diplomacy_bonus = modifiers.get("diplomacy_trade_bonus", 0.0)
        capacity = max(0.0, TRADE_BASE_MAX_CAPACITY * max(0.5, scale) * external_limit + diplomacy_bonus)
        return capacity * self.trade_mode_capacity_multiplier(mode)

    def trade_capacity_per_month(self, player, mode=None):
        return min(
            self.trade_logistics_capacity_per_month(player, mode),
            self.trade_max_capacity_per_month(player, mode),
        )

    def estimate_monthly_trade_flows(self, player, contracts=None):
        contracts = self.normalized_trade_contracts(getattr(player, "trade_contracts", [])) if contracts is None else contracts
        capacity_limits = {
            "buy": self.trade_capacity_per_month(player, "buy"),
            "sell": self.trade_capacity_per_month(player, "sell"),
        }
        remaining_capacity = dict(capacity_limits)
        imports = {}
        exports = {}
        buy_cost = 0.0
        sell_income = 0.0
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_free = {
            category_key: max(0.0, capacity.get(category_key, 0.0) - used.get(category_key, 0.0))
            for category_key in STORAGE_CATEGORIES
        }

        for contract in contracts:
            resource_key = contract["resource"]
            mode = contract["mode"]
            if remaining_capacity.get(mode, 0.0) <= 0:
                continue
            amount = min(contract["amount"], remaining_capacity.get(mode, 0.0))
            if mode == "sell":
                amount = min(amount, self.stockpile_amount(player, resource_key))
                storage_key = self.storage_bucket_for_resource(resource_key)
                storage_free[storage_key] = storage_free.get(storage_key, 0.0) + amount
            else:
                storage_key = self.storage_bucket_for_resource(resource_key)
                amount = min(amount, storage_free.get(storage_key, 0.0))
            if amount <= 0:
                continue
            price = self.trade_unit_price(player, resource_key, mode)
            if mode == "buy":
                imports[resource_key] = imports.get(resource_key, 0.0) + amount
                buy_cost += amount * price
                storage_free[storage_key] = max(0.0, storage_free.get(storage_key, 0.0) - amount)
            else:
                exports[resource_key] = exports.get(resource_key, 0.0) + amount
                sell_income += amount * price
            remaining_capacity[mode] = max(0.0, remaining_capacity.get(mode, 0.0) - amount)

        capacity_used = {
            mode: max(0.0, capacity_limits[mode] - remaining_capacity.get(mode, 0.0))
            for mode in ("buy", "sell")
        }

        return {
            "imports": imports,
            "exports": exports,
            "buy_cost": buy_cost,
            "sell_income": sell_income,
            "money_balance": sell_income - buy_cost,
            "capacity_used": capacity_used["buy"] + capacity_used["sell"],
            "capacity_limit": capacity_limits["buy"] + capacity_limits["sell"],
            "buy_capacity_used": capacity_used["buy"],
            "sell_capacity_used": capacity_used["sell"],
            "buy_capacity_limit": capacity_limits["buy"],
            "sell_capacity_limit": capacity_limits["sell"],
            "logistics_capacity_limit": self.trade_logistics_capacity_per_month(player),
            "max_capacity_limit": self.trade_max_capacity_per_month(player),
            "buy_logistics_capacity_limit": self.trade_logistics_capacity_per_month(player, "buy"),
            "sell_logistics_capacity_limit": self.trade_logistics_capacity_per_month(player, "sell"),
            "buy_max_capacity_limit": self.trade_max_capacity_per_month(player, "buy"),
            "sell_max_capacity_limit": self.trade_max_capacity_per_month(player, "sell"),
        }

    def trade_weekly_capacity_limits(self, player):
        return {
            "buy": self.trade_capacity_per_month(player, "buy") * TRADE_WEEKLY_FRACTION,
            "sell": self.trade_capacity_per_month(player, "sell") * TRADE_WEEKLY_FRACTION,
        }

    def collect_player_market_orders(self, player, weekly_fraction=TRADE_WEEKLY_FRACTION, enforce_budget=True):
        contracts = self.normalize_trade_contracts(player)
        remaining_capacity = self.trade_weekly_capacity_limits(player)
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_free = {
            category_key: max(0.0, capacity.get(category_key, 0.0) - used.get(category_key, 0.0))
            for category_key in STORAGE_CATEGORIES
        }
        available_budget = max(0.0, player.budget)
        orders = []

        for contract in contracts:
            resource_key = contract["resource"]
            mode = contract["mode"]
            if remaining_capacity.get(mode, 0.0) <= 0:
                continue
            amount = min(contract["amount"] * weekly_fraction, remaining_capacity.get(mode, 0.0))
            if mode == "buy":
                storage_key = self.storage_bucket_for_resource(resource_key)
                amount = min(amount, storage_free.get(storage_key, 0.0))
                if enforce_budget:
                    unit_price = self.trade_unit_price(player, resource_key, "buy")
                    cost = amount * unit_price
                    if cost > available_budget and cost > 0:
                        amount *= max(0.0, available_budget / cost)
            else:
                amount = min(amount, self.stockpile_amount(player, resource_key))
            if amount <= 0:
                continue
            orders.append({
                "player": player,
                "resource": resource_key,
                "mode": mode,
                "amount": amount,
            })
            remaining_capacity[mode] = max(0.0, remaining_capacity.get(mode, 0.0) - amount)
            if mode == "buy":
                storage_key = self.storage_bucket_for_resource(resource_key)
                storage_free[storage_key] = max(0.0, storage_free.get(storage_key, 0.0) - amount)
                if enforce_budget:
                    available_budget = max(0.0, available_budget - amount * self.trade_unit_price(player, resource_key, "buy"))
            else:
                storage_key = self.storage_bucket_for_resource(resource_key)
                storage_free[storage_key] = storage_free.get(storage_key, 0.0) + amount
        return orders

    def external_market_volume_for_resource(self, resource_key, weekly_total_trade_capacity):
        rarity = MARKET_RESOURCE_RARITY.get(resource_key, 0.45)
        return max(750.0, weekly_total_trade_capacity * max(0.05, rarity) * 0.55)

    def update_market_prices_from_orders(self, orders):
        market_state = self.simulation_server.market_state
        keys = self.tradeable_resource_keys()
        weekly_total_trade_capacity = sum(
            self.trade_capacity_per_month(player) * TRADE_WEEKLY_FRACTION
            for player in self.players
        )
        demand = {key: 0.0 for key in keys}
        supply = {key: 0.0 for key in keys}
        for order in orders:
            bucket = demand if order["mode"] == "buy" else supply
            bucket[order["resource"]] = bucket.get(order["resource"], 0.0) + order["amount"]

        market_state.previous_prices = dict(market_state.current_prices or {})
        external_demand = {}
        external_supply = {}
        total_market_demand = {}
        total_market_supply = {}
        new_prices = {}
        for resource_key in keys:
            base_price = market_state.ensure_resource(resource_key)
            external_volume = self.external_market_volume_for_resource(resource_key, weekly_total_trade_capacity)
            external_demand[resource_key] = external_volume
            external_supply[resource_key] = external_volume
            total_demand = demand.get(resource_key, 0.0) + external_volume
            total_supply = supply.get(resource_key, 0.0) + external_volume
            total_market_demand[resource_key] = total_demand
            total_market_supply[resource_key] = total_supply
            denominator = max(1.0, min(total_demand, total_supply))
            imbalance = (total_demand - total_supply) / denominator
            volatility = MARKET_RESOURCE_VOLATILITY.get(resource_key, 1.0)
            base_change = max(
                -MARKET_MAX_WEEKLY_PRICE_MOVE,
                min(MARKET_MAX_WEEKLY_PRICE_MOVE, imbalance * 0.10 * volatility),
            )
            old_shock = market_state.price_shocks.get(resource_key, 0.0)
            shock = old_shock * MARKET_SHOCK_DECAY + base_change * max(0.0, MARKET_SHOCK_FACTOR - 1.0)
            shock = max(-MARKET_MAX_WEEKLY_PRICE_MOVE, min(MARKET_MAX_WEEKLY_PRICE_MOVE, shock))
            old_price = market_state.current_prices.get(resource_key, base_price)
            target_price = base_price * max(0.25, 1.0 + base_change + shock)
            new_price = old_price + (target_price - old_price) * MARKET_PRICE_SMOOTHING
            new_prices[resource_key] = max(base_price * 0.25, min(base_price * 4.0, new_price))
            market_state.price_shocks[resource_key] = shock

        linked_prices = dict(new_prices)
        for target_key, sources in MARKET_LINKED_PRICE_EFFECTS.items():
            if target_key not in linked_prices:
                continue
            source_pressure = 0.0
            weight_total = 0.0
            for source_key, weight in sources.items():
                base = market_state.base_prices.get(source_key, TRADE_BASE_PRICES.get(source_key, 60.0))
                source_price = new_prices.get(source_key, market_state.current_prices.get(source_key, base))
                if base <= 0:
                    continue
                source_pressure += (source_price / base - 1.0) * weight
                weight_total += weight
            if weight_total <= 0:
                continue
            base = market_state.base_prices.get(target_key, TRADE_BASE_PRICES.get(target_key, 60.0))
            linked_target = base * max(0.25, 1.0 + source_pressure)
            linked_prices[target_key] = linked_prices[target_key] + (linked_target - linked_prices[target_key]) * MARKET_LINKED_PRICE_SMOOTHING

        market_state.current_prices = {
            key: max(market_state.base_prices.get(key, 60.0) * 0.25, min(market_state.base_prices.get(key, 60.0) * 4.0, value))
            for key, value in linked_prices.items()
        }
        market_state.demand = total_market_demand
        market_state.supply = total_market_supply
        market_state.external_demand = external_demand
        market_state.external_supply = external_supply
        for key, price in market_state.current_prices.items():
            history = market_state.history.setdefault(key, [])
            history.append(price)
            if len(history) > MARKET_HISTORY_LIMIT:
                del history[:-MARKET_HISTORY_LIMIT]
        market_state.revision += 1

    def execute_market_orders(self, orders):
        money_by_player = {}
        for order in orders:
            player = order["player"]
            resource_key = order["resource"]
            mode = order["mode"]
            amount = order["amount"]
            price = self.trade_unit_price(player, resource_key, mode)
            if mode == "buy":
                amount = min(amount, self.storage_free_capacity_for_resource(player, resource_key))
                cost = amount * price
                if cost > player.budget and cost > 0:
                    amount *= max(0.0, player.budget / cost)
                    cost = amount * price
                accepted = self.add_to_stockpile(player, resource_key, amount)
                cost = accepted * price
                player.budget -= cost
                money_by_player[player.id] = money_by_player.get(player.id, 0.0) - cost
            else:
                amount = min(amount, self.stockpile_amount(player, resource_key))
                sold = self.consume_from_stockpile(player, resource_key, amount)
                income = sold * price
                player.budget += income
                money_by_player[player.id] = money_by_player.get(player.id, 0.0) + income
        for player in self.players:
            if money_by_player.get(player.id, 0.0) != 0.0:
                self.mark_player_resource_balance_dirty(player)
        return money_by_player

    def run_weekly_market_tick(self):
        orders = []
        for player in self.players:
            orders.extend(self.collect_player_market_orders(player, TRADE_WEEKLY_FRACTION, enforce_budget=True))
        self.update_market_prices_from_orders(orders)
        money_by_player = self.execute_market_orders(orders)
        for player in self.players:
            self.recalculate_monthly_balance(player)
            self.mark_player_resource_balance_dirty(player)
        self.trade_panel_cache = None
        return money_by_player

