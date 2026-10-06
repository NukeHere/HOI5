import math
import random

from Constants import *
from game_models import (
    AirAttackSalvo,
    AirCombatEstimate,
    AirDefenseUnit,
    AirSalvo,
    AirWing,
    Airbase,
    DivisionAirDefenseThreat,
)


class AirSystemMixin:
    def aircraft_type_data(self, aircraft_type):
        return AIRCRAFT_TYPES.get(aircraft_type, {})

    def munition_data(self, munition_id):
        return MUNITIONS.get(munition_id, {})

    def air_defense_class_data(self, unit_class):
        return AIR_DEFENSE_CLASSES.get(unit_class, {})

    def default_air_wing_loadout(self, aircraft_type):
        data = self.aircraft_type_data(aircraft_type)
        allowed = data.get("allowed_munitions", [])
        return allowed[0] if allowed else None

    def air_wing_mission_loadout(self, aircraft_type, mission_type, target_tile=None):
        data = self.aircraft_type_data(aircraft_type)
        allowed = list(data.get("allowed_munitions", []) or [])
        if not allowed:
            return None
        preferences = {
            "cas": [
                "light_guided_missile",
                "unguided_rockets",
                "guided_bomb",
                "glide_bomb",
            ],
            "strategic_strike": [
                "tactical_cruise_missile",
                "small_ballistic_missile",
                "heavy_strategic_missile",
                "glide_bomb",
                "guided_bomb",
                "bunker_buster",
                "light_guided_missile",
            ],
            "intercept": [
                AIR_WING_INTERCEPTOR_LOADOUTS.get(aircraft_type, {}).get("munition_id"),
            ],
            "air_superiority": [
                AIR_WING_INTERCEPTOR_LOADOUTS.get(aircraft_type, {}).get("munition_id"),
            ],
            "patrol": [
                AIR_WING_INTERCEPTOR_LOADOUTS.get(aircraft_type, {}).get("munition_id"),
            ],
        }
        for munition_id in preferences.get(mission_type, []):
            if munition_id and munition_id in allowed:
                return munition_id
            if munition_id and mission_type in {"intercept", "air_superiority", "patrol"}:
                return munition_id
        return self.default_air_wing_loadout(aircraft_type)

    def aircraft_type_is_helicopter(self, aircraft_type):
        return bool(self.aircraft_type_data(aircraft_type).get("is_helicopter", False))

    def aircraft_stockpile_count(self, player, aircraft_type):
        if not player:
            return 0
        return int((getattr(player, "aircraft_stockpile", {}) or {}).get(aircraft_type, 0))

    def add_aircraft_to_stockpile(self, player, aircraft_type, count):
        if not player or aircraft_type not in AIRCRAFT_TYPES or count <= 0:
            return 0
        if player.aircraft_stockpile is None:
            player.aircraft_stockpile = {}
        added = int(count)
        player.aircraft_stockpile[aircraft_type] = self.aircraft_stockpile_count(player, aircraft_type) + added
        return added

    def air_wing_composition(self, wing):
        if not wing:
            return {}
        composition = {
            aircraft_type: max(0, int(count))
            for aircraft_type, count in (getattr(wing, "aircraft_composition", {}) or {}).items()
            if aircraft_type in AIRCRAFT_TYPES and int(count) > 0
        }
        if not composition and getattr(wing, "aircraft_type", None) in AIRCRAFT_TYPES and getattr(wing, "aircraft_count", 0) > 0:
            composition = {wing.aircraft_type: int(wing.aircraft_count)}
        return composition

    def sync_air_wing_composition_fields(self, wing):
        if not wing:
            return
        composition = self.air_wing_composition(wing)
        wing.aircraft_composition = composition
        wing.aircraft_count = sum(composition.values())
        if composition:
            wing.aircraft_type = max(composition.items(), key=lambda item: item[1])[0]
        wing.ready_count = min(max(0, int(getattr(wing, "ready_count", 0))), wing.aircraft_count)
        wing.damaged_count = min(max(0, int(getattr(wing, "damaged_count", 0))), wing.aircraft_count)
        if wing.current_loadout not in self.aircraft_type_data(wing.aircraft_type).get("allowed_munitions", []):
            wing.current_loadout = self.default_air_wing_loadout(wing.aircraft_type)
        enabled = [
            mission for mission in (getattr(wing, "enabled_missions", []) or [])
            if mission in self.air_wing_allowed_missions(wing)
        ]
        wing.enabled_missions = enabled
        wing.mission = enabled[0] if enabled else "none"
        self.refresh_air_wing_interceptor_loadout(wing)

    def air_wing_type_count(self, wing, aircraft_type):
        return self.air_wing_composition(wing).get(aircraft_type, 0)

    def air_wing_extra_capacity_for_type(self, wing, aircraft_type):
        if not wing or not wing.base_tile or aircraft_type not in AIRCRAFT_TYPES:
            return 0
        composition = self.air_wing_composition(wing)
        current_same_role = sum(
            count for existing_type, count in composition.items()
            if self.aircraft_type_is_helicopter(existing_type) == self.aircraft_type_is_helicopter(aircraft_type)
        )
        return max(0, self.base_free_capacity_for_wing(wing.base_tile, wing, aircraft_type) - current_same_role)

    def air_wing_type_counts_by_role(self, wing):
        fixed = 0
        helicopters = 0
        for aircraft_type, count in self.air_wing_composition(wing).items():
            if self.aircraft_type_is_helicopter(aircraft_type):
                helicopters += count
            else:
                fixed += count
        return fixed, helicopters

    def air_wing_primary_type_for_mission(self, wing, mission=None):
        composition = self.air_wing_composition(wing)
        if not composition:
            return getattr(wing, "aircraft_type", None)
        if mission:
            role_priority = {
                "cas": {
                    "attack_helicopter": 5,
                    "cas_aircraft": 5,
                    "multirole_fighter": 3,
                    "fighter_bomber": 2,
                },
                "strategic_strike": {
                    "strategic_bomber": 6,
                    "fighter_bomber": 5,
                    "multirole_fighter": 4,
                    "cas_aircraft": 2,
                },
                "intercept": {
                    "light_fighter": 5,
                    "multirole_fighter": 4,
                    "fighter_bomber": 2,
                    "cas_aircraft": 1,
                },
                "air_superiority": {
                    "light_fighter": 5,
                    "multirole_fighter": 4,
                    "fighter_bomber": 2,
                },
                "patrol": {
                    "light_fighter": 5,
                    "multirole_fighter": 4,
                    "fighter_bomber": 2,
                },
            }.get(mission, {})
            candidates = []
            for aircraft_type, count in composition.items():
                if mission not in self.aircraft_type_data(aircraft_type).get("allowed_missions", []):
                    continue
                candidates.append((role_priority.get(aircraft_type, 1), count, aircraft_type))
            if candidates:
                return max(candidates)[2]
        return max((count, aircraft_type) for aircraft_type, count in composition.items())[1]

    def air_wing_ready_count_for_type(self, wing, aircraft_type):
        composition = self.air_wing_composition(wing)
        type_count = composition.get(aircraft_type, 0)
        if not wing or type_count <= 0 or wing.aircraft_count <= 0:
            return 0
        ready_ratio = self.clamp01(float(getattr(wing, "ready_count", 0)) / max(1, wing.aircraft_count))
        return max(0, min(type_count, int(round(type_count * ready_ratio))))

    def air_wing_interceptor_loadout_data(self, aircraft_type):
        return AIR_WING_INTERCEPTOR_LOADOUTS.get(aircraft_type, {})

    def air_wing_interceptor_capacity_for_type(self, aircraft_type, count):
        loadout = self.air_wing_interceptor_loadout_data(aircraft_type)
        if not loadout:
            return 0
        return max(0, int(count)) * max(0, int(loadout.get("ammo_per_aircraft", 0)))

    def air_wing_interceptor_capacity(self, wing):
        if not wing:
            return 0
        return sum(
            self.air_wing_interceptor_capacity_for_type(aircraft_type, count)
            for aircraft_type, count in self.air_wing_composition(wing).items()
        )

    def air_wing_default_interceptor_munition(self, wing):
        if not wing:
            return None
        candidates = []
        for aircraft_type, count in self.air_wing_composition(wing).items():
            loadout = self.air_wing_interceptor_loadout_data(aircraft_type)
            munition_id = loadout.get("munition_id")
            if munition_id in MUNITIONS:
                candidates.append((count, aircraft_type, munition_id))
        if not candidates:
            return None
        return max(candidates)[2]

    def refresh_air_wing_interceptor_loadout(self, wing, refill_new_capacity=False):
        if not wing:
            return
        old_capacity = max(0, int(getattr(wing, "interceptor_ammo_capacity", 0) or 0))
        capacity = self.air_wing_interceptor_capacity(wing)
        default_munition = self.air_wing_default_interceptor_munition(wing)
        if getattr(wing, "interceptor_munition", None) not in MUNITIONS:
            wing.interceptor_munition = default_munition
        if not default_munition:
            wing.interceptor_munition = None
            wing.interceptor_ammo_capacity = 0
            wing.interceptor_ammo = 0
            return
        wing.interceptor_ammo_capacity = capacity
        ammo = max(0, int(getattr(wing, "interceptor_ammo", 0) or 0))
        if refill_new_capacity:
            ammo += max(0, capacity - old_capacity)
        wing.interceptor_ammo = min(capacity, ammo)

    def air_wing_interceptor_fire_channels(self, aircraft_type, sorties):
        loadout = self.air_wing_interceptor_loadout_data(aircraft_type)
        channels_per_sortie = max(0, int(loadout.get("fire_channels_per_sortie", 0)))
        return max(0, int(sorties)) * channels_per_sortie

    def air_wing_interceptors_per_target(self, aircraft_type):
        loadout = self.air_wing_interceptor_loadout_data(aircraft_type)
        return max(1, int(loadout.get("interceptors_per_target", 1)))

    def air_wing_engaged_salvo_count(self, wing, aircraft_type, sorties, salvo):
        if not wing or not salvo or salvo.count <= 0:
            return 0
        self.refresh_air_wing_interceptor_loadout(wing)
        interceptors_per_target = self.air_wing_interceptors_per_target(aircraft_type)
        available_interceptors = max(0, int(getattr(wing, "interceptor_ammo", 0) or 0) // interceptors_per_target)
        return max(
            0,
            min(
                salvo.count,
                available_interceptors,
                self.air_wing_interceptor_fire_channels(aircraft_type, sorties),
            ),
        )

    def air_wing_engaged_aircraft_count(self, wing, aircraft_type, sorties, target_sorties):
        if not wing or target_sorties <= 0:
            return 0
        self.refresh_air_wing_interceptor_loadout(wing)
        interceptors_per_target = self.air_wing_interceptors_per_target(aircraft_type)
        available_interceptors = max(0, int(getattr(wing, "interceptor_ammo", 0) or 0) // interceptors_per_target)
        return max(
            0,
            min(
                int(target_sorties),
                available_interceptors,
                self.air_wing_interceptor_fire_channels(aircraft_type, sorties),
            ),
        )

    def remove_aircraft_from_wing(self, wing, aircraft_type, destroyed=0, damaged=0):
        if not wing or aircraft_type not in AIRCRAFT_TYPES:
            return
        destroyed = max(0, int(destroyed))
        damaged = max(0, int(damaged))
        composition = self.air_wing_composition(wing)
        current = composition.get(aircraft_type, 0)
        destroyed = min(destroyed, current)
        if destroyed > 0:
            remaining = current - destroyed
            if remaining > 0:
                composition[aircraft_type] = remaining
            else:
                composition.pop(aircraft_type, None)
            wing.aircraft_composition = composition
            wing.aircraft_count = max(0, wing.aircraft_count - destroyed)
            wing.ready_count = max(0, wing.ready_count - destroyed)
            wing.destroyed_count = max(0, int(getattr(wing, "destroyed_count", 0))) + destroyed
        if damaged > 0:
            damaged = min(damaged, max(0, wing.ready_count))
            wing.ready_count = max(0, wing.ready_count - damaged)
            wing.damaged_count = min(wing.aircraft_count, max(0, wing.damaged_count + damaged))
        self.sync_air_wing_composition_fields(wing)

    def airbase_capacity_for_wing(self, airbase, aircraft_type):
        if not airbase:
            return 0
        if self.aircraft_type_is_helicopter(aircraft_type):
            return max(0, int(airbase.helicopter_capacity))
        return max(0, int(airbase.aircraft_capacity))

    def field_helipad_capacity_for_wing(self, tile, aircraft_type):
        if not tile or not self.aircraft_type_is_helicopter(aircraft_type):
            return 0
        coverage = (getattr(tile, "building_coverage", {}) or {}).get("field_helipad", 0.0)
        if coverage <= 0 or self.building_health(tile, "field_helipad") <= 0.15:
            return 0
        return max(1, int(round(coverage * FIELD_HELIPAD_HELICOPTER_CAPACITY_PER_COVERAGE)))

    def base_capacity_for_wing(self, tile, aircraft_type):
        airbase = self.airbase_on_tile(tile)
        if airbase and airbase.owner is getattr(tile, "owner", None) and self.building_health(tile, "airbase") > 0.15:
            if not self.aircraft_type_is_helicopter(aircraft_type):
                runway_need = int(self.aircraft_type_data(aircraft_type).get("runway_need", 1))
                if airbase.runway_level < runway_need:
                    return 0
            return self.airbase_capacity_for_wing(airbase, aircraft_type)
        return self.field_helipad_capacity_for_wing(tile, aircraft_type)

    def based_aircraft_load(self, tile, helicopter=None, excluding_wing=None):
        if not tile:
            return 0
        total = 0
        for wing in self.air_wings_on_tile(tile):
            if excluding_wing and wing is excluding_wing:
                continue
            for aircraft_type, count in self.air_wing_composition(wing).items():
                is_helicopter = self.aircraft_type_is_helicopter(aircraft_type)
                if helicopter is None or is_helicopter == helicopter:
                    total += max(0, int(count))
        return total

    def base_free_capacity_for_wing(self, tile, wing, aircraft_type=None):
        if not tile or not wing:
            return 0
        aircraft_type = aircraft_type or wing.aircraft_type
        capacity = self.base_capacity_for_wing(tile, aircraft_type)
        load = self.based_aircraft_load(
            tile,
            helicopter=self.aircraft_type_is_helicopter(aircraft_type),
            excluding_wing=wing,
        )
        return max(0, capacity - load)

    def air_wing_fits_base(self, wing, target_tile):
        if not wing or not target_tile:
            return False, "Нет цели перебазирования"
        composition = self.air_wing_composition(wing)
        if not composition:
            return False, "Крыло пустое"
        fixed_count, helicopter_count = self.air_wing_type_counts_by_role(wing)
        if fixed_count > 0:
            for aircraft_type, _count in composition.items():
                if not self.aircraft_type_is_helicopter(aircraft_type) and self.base_capacity_for_wing(target_tile, aircraft_type) <= 0:
                    aircraft_name = AIRCRAFT_TYPES.get(aircraft_type, {}).get("name", aircraft_type)
                    return False, f"База не принимает {aircraft_name}"
            fixed_capacity = self.base_capacity_for_wing(target_tile, self.air_wing_primary_fixed_type(wing))
            fixed_load = self.based_aircraft_load(target_tile, helicopter=False, excluding_wing=wing)
            if fixed_capacity <= 0 or fixed_load + fixed_count > fixed_capacity:
                return False, f"Не хватает самолетных мест: {max(0, fixed_capacity - fixed_load)}/{fixed_count}"
        if helicopter_count > 0:
            heli_capacity = self.base_capacity_for_wing(target_tile, "attack_helicopter")
            heli_load = self.based_aircraft_load(target_tile, helicopter=True, excluding_wing=wing)
            if heli_capacity <= 0 or heli_load + helicopter_count > heli_capacity:
                return False, f"Не хватает вертолетных мест: {max(0, heli_capacity - heli_load)}/{helicopter_count}"
        return True, "OK"

    def air_wing_primary_fixed_type(self, wing):
        for aircraft_type, _count in sorted(self.air_wing_composition(wing).items(), key=lambda item: -item[1]):
            if not self.aircraft_type_is_helicopter(aircraft_type):
                return aircraft_type
        return getattr(wing, "aircraft_type", "light_fighter")

    @staticmethod
    def indexed_tile_key(tile):
        return (tile.q, tile.r) if tile else None

    @classmethod
    def add_to_tile_index(cls, index, tile, obj):
        key = cls.indexed_tile_key(tile)
        if key is None:
            return
        bucket = index.setdefault(key, [])
        if obj not in bucket:
            bucket.append(obj)

    @classmethod
    def remove_from_tile_index(cls, index, tile, obj):
        key = cls.indexed_tile_key(tile)
        if key is None:
            return
        bucket = index.get(key)
        if not bucket:
            return
        if obj in bucket:
            bucket.remove(obj)
        if not bucket:
            index.pop(key, None)

    def register_air_wing(self, wing):
        if not wing:
            return None
        if wing not in self.air_wings:
            self.air_wings.append(wing)
        if wing.owner and wing not in getattr(wing.owner, "air_wings", []):
            wing.owner.air_wings.append(wing)
        self.air_wing_lookup[wing.id] = wing
        self.add_to_tile_index(self.air_wings_by_tile, wing.base_tile, wing)
        self.air_asset_revision += 1
        return wing

    def unregister_air_wing(self, wing):
        if not wing:
            return
        if wing in self.air_wings:
            self.air_wings.remove(wing)
        if wing.owner and wing in getattr(wing.owner, "air_wings", []):
            wing.owner.air_wings.remove(wing)
        self.air_wing_lookup.pop(wing.id, None)
        self.remove_from_tile_index(self.air_wings_by_tile, wing.base_tile, wing)
        self.selected_air_wing_ids.discard(wing.id)
        if self.selected_air_wing_id == wing.id:
            self.selected_air_wing_id = None
        self.air_wing_target_mode_ids.discard(wing.id)
        self.air_wing_rebase_mode_ids.discard(wing.id)
        if self.air_wing_target_mode_id == wing.id:
            self.air_wing_target_mode_id = None
        if self.air_wing_rebase_mode_id == wing.id:
            self.air_wing_rebase_mode_id = None
        self.air_asset_revision += 1

    def register_air_defense_unit(self, unit):
        if not unit:
            return None
        if unit not in self.air_defense_units:
            self.air_defense_units.append(unit)
        if unit.owner and unit not in getattr(unit.owner, "air_defense_units", []):
            unit.owner.air_defense_units.append(unit)
        self.air_defense_unit_lookup[unit.id] = unit
        self.add_to_tile_index(self.air_defense_units_by_tile, unit.tile, unit)
        self.air_asset_revision += 1
        return unit

    def unregister_air_defense_unit(self, unit):
        if not unit:
            return
        if unit in self.air_defense_units:
            self.air_defense_units.remove(unit)
        if unit.owner and unit in getattr(unit.owner, "air_defense_units", []):
            unit.owner.air_defense_units.remove(unit)
        self.air_defense_unit_lookup.pop(unit.id, None)
        self.remove_from_tile_index(self.air_defense_units_by_tile, unit.tile, unit)
        if self.selected_air_defense_unit_id == unit.id:
            self.selected_air_defense_unit_id = None
        if self.air_defense_move_mode_id == unit.id:
            self.air_defense_move_mode_id = None
        self.air_asset_revision += 1

    def move_air_defense_unit_index(self, unit, old_tile, new_tile):
        if old_tile is new_tile:
            return
        self.remove_from_tile_index(self.air_defense_units_by_tile, old_tile, unit)
        self.add_to_tile_index(self.air_defense_units_by_tile, new_tile, unit)
        self.air_asset_revision += 1

    def register_air_salvo(self, salvo):
        if not salvo:
            return None
        if salvo not in self.air_salvos:
            self.air_salvos.append(salvo)
        self.air_salvo_lookup[salvo.id] = salvo
        self.invalidate_air_salvo_tile_cache()
        return salvo

    def unregister_air_salvo(self, salvo):
        if not salvo:
            return
        if salvo in self.air_salvos:
            self.air_salvos.remove(salvo)
        self.air_salvo_lookup.pop(salvo.id, None)
        self.invalidate_air_salvo_tile_cache()

    def register_air_attack_salvo(self, salvo):
        if not salvo:
            return None
        if salvo not in self.air_attack_salvos:
            self.air_attack_salvos.append(salvo)
        self.air_attack_salvo_lookup[salvo.id] = salvo
        return salvo

    def unregister_air_attack_salvo(self, salvo):
        if not salvo:
            return
        if salvo in self.air_attack_salvos:
            self.air_attack_salvos.remove(salvo)
        self.air_attack_salvo_lookup.pop(salvo.id, None)

    def invalidate_air_salvo_tile_cache(self):
        self.air_salvo_revision += 1
        self.air_salvo_tile_cache_revision = -1

    def rebuild_air_salvo_tile_cache(self):
        lookup = {}
        for salvo in getattr(self, "air_salvos", []) or []:
            seen_keys = set()
            for tile in (salvo.target_tile, salvo.current_tile, salvo.launch_tile):
                key = self.indexed_tile_key(tile)
                if key is None or key in seen_keys:
                    continue
                seen_keys.add(key)
                lookup.setdefault(key, []).append(salvo)
        self.air_salvo_tile_lookup = lookup
        self.air_salvo_tile_cache_revision = self.air_salvo_revision

    def air_wing_by_id(self, wing_id):
        return self.air_wing_lookup.get(wing_id)

    def air_defense_unit_by_id(self, unit_id):
        return self.air_defense_unit_lookup.get(unit_id)

    def rebase_air_wing(self, wing, target_tile):
        if not wing or not target_tile:
            return False, "Нет цели перебазирования"
        if target_tile.owner is not wing.owner:
            return False, "Нужна своя клетка"
        if self.is_water_tile(target_tile):
            return False, "Нельзя базироваться на воде"
        ok, message = self.air_wing_fits_base(wing, target_tile)
        if not ok:
            return False, message
        old_base_tile = wing.base_tile
        self.remove_from_tile_index(self.air_wings_by_tile, old_base_tile, wing)
        wing.base_tile = target_tile
        self.add_to_tile_index(self.air_wings_by_tile, wing.base_tile, wing)
        self.air_asset_revision += 1
        wing.target_tile = None
        wing.sortie_cooldown_hours = max(wing.sortie_cooldown_hours, 1.0)
        return True, f"Крыло перебазировано в {target_tile.q}:{target_tile.r}"

    def normalize_air_wing_operation_area_keys(self, wing):
        if not wing:
            return []
        raw_keys = getattr(wing, "operation_area_tile_keys", None)
        if raw_keys is None:
            raw_keys = [self.tile_key(wing.target_tile)] if getattr(wing, "target_tile", None) else []
        normalized = []
        seen = set()
        for raw_key in raw_keys or []:
            tile = self.tile_for_key(raw_key)
            if not tile:
                continue
            key = self.tile_key(tile)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(key)
        wing.operation_area_tile_keys = normalized
        return normalized

    def air_wing_operation_area_tiles(self, wing):
        keys = self.normalize_air_wing_operation_area_keys(wing)
        return [tile for tile in (self.tile_for_key(key) for key in keys) if tile]

    def air_wing_operation_area_summary(self, wing):
        tiles = self.air_wing_operation_area_tiles(wing)
        if not tiles:
            return "район нет"
        if len(tiles) == 1:
            tile = tiles[0]
            return f"район {tile.q}:{tile.r}"
        return f"район {len(tiles)} кл."

    def set_air_wing_operation_area_tile(self, wing, tile, mode="replace"):
        if not wing or not tile:
            return False, "Нет клетки района"
        key = self.tile_key(tile)
        keys = self.normalize_air_wing_operation_area_keys(wing)
        if mode == "add":
            if key not in keys:
                keys.append(key)
        elif mode == "remove":
            keys = [existing_key for existing_key in keys if existing_key != key]
        else:
            keys = [key]
        wing.operation_area_tile_keys = keys
        if keys:
            center_tile = self.tile_for_key(keys[-1])
            wing.target_tile = center_tile
            wing.target_area = center_tile
        else:
            wing.target_tile = None
            wing.target_area = None
        return True, self.air_wing_operation_area_summary(wing)

    def air_wing_can_reach_tile(self, wing, tile):
        return bool(
            wing
            and tile
            and wing.base_tile
            and self.tile_world_distance(wing.base_tile, tile) <= self.air_wing_display_range_world_radius(wing)
        )

    @staticmethod
    def tile_world_distance(first, second):
        if not first or not second:
            return float("inf")
        return math.hypot(first.center_x - second.center_x, first.center_y - second.center_y)

    def aircraft_type_range_world_radius(self, aircraft_type):
        return max(0.0, float(self.aircraft_type_data(aircraft_type).get("range", 0))) * HEX_WID

    def aircraft_type_can_reach_tile(self, origin_tile, aircraft_type, target_tile):
        return bool(
            origin_tile
            and target_tile
            and self.tile_world_distance(origin_tile, target_tile) <= self.aircraft_type_range_world_radius(aircraft_type)
        )

    def battle_has_enemy_for_owner(self, battle, owner):
        if not battle or not owner:
            return False
        for side in ("attacker", "defender"):
            for division in self.battle_side_present(battle, side):
                if self.countries_hostile(division.owner, owner) and division.strength > 0:
                    return True
        return False

    def air_wing_can_attack_tile(self, wing, tile, mission_type):
        if not wing or not tile or not wing.owner:
            return False
        if mission_type == "cas":
            battle = self.battles.get(self.battle_key_for_tile(tile))
            return self.battle_has_enemy_for_owner(battle, wing.owner)
        if mission_type == "strategic_strike":
            return self.air_mission_tile_is_hostile(wing.owner, tile)
        return self.air_mission_tile_is_hostile(wing.owner, tile) or bool(self.enemy_divisions_on_tile(tile, wing.owner))

    def tick_air_wing_mission_cooldowns(self, wing, elapsed_hours):
        if not wing or elapsed_hours <= 0:
            return
        cooldowns = getattr(wing, "mission_cooldowns", None)
        if cooldowns is None:
            wing.mission_cooldowns = {}
            cooldowns = wing.mission_cooldowns
        previous_mission_max = max((float(value or 0.0) for value in cooldowns.values()), default=0.0)
        previous_sortie_cooldown = max(0.0, float(getattr(wing, "sortie_cooldown_hours", 0.0) or 0.0))
        legacy_global_cooldown = max(0.0, previous_sortie_cooldown - elapsed_hours) if previous_sortie_cooldown > previous_mission_max + 0.01 else 0.0
        for mission_type in list(cooldowns.keys()):
            remaining = max(0.0, float(cooldowns.get(mission_type, 0.0) or 0.0) - elapsed_hours)
            if remaining > 0:
                cooldowns[mission_type] = remaining
            else:
                cooldowns.pop(mission_type, None)
        target_cooldowns = getattr(wing, "mission_target_cooldowns", None)
        if target_cooldowns is None:
            wing.mission_target_cooldowns = {}
            target_cooldowns = wing.mission_target_cooldowns
        for mission_type, by_key in list(target_cooldowns.items()):
            if not isinstance(by_key, dict):
                target_cooldowns.pop(mission_type, None)
                continue
            for key in list(by_key.keys()):
                remaining = max(0.0, float(by_key.get(key, 0.0) or 0.0) - elapsed_hours)
                if remaining > 0:
                    by_key[key] = remaining
                else:
                    by_key.pop(key, None)
            if not by_key:
                target_cooldowns.pop(mission_type, None)
        wing.sortie_cooldown_hours = max(legacy_global_cooldown, max(cooldowns.values(), default=0.0))

    def air_wing_has_global_sortie_cooldown(self, wing):
        if not wing:
            return False
        mission_max = max((float(value or 0.0) for value in (getattr(wing, "mission_cooldowns", None) or {}).values()), default=0.0)
        return float(getattr(wing, "sortie_cooldown_hours", 0.0) or 0.0) > mission_max + 0.01

    def air_wing_mission_cooldown(self, wing, mission_type):
        if not wing:
            return 0.0
        cooldowns = getattr(wing, "mission_cooldowns", None) or {}
        if mission_type in cooldowns:
            return max(0.0, float(cooldowns.get(mission_type, 0.0) or 0.0))
        return 0.0

    def set_air_wing_mission_cooldown(self, wing, mission_type, hours):
        if not wing or not mission_type:
            return
        if getattr(wing, "mission_cooldowns", None) is None:
            wing.mission_cooldowns = {}
        legacy_global_cooldown = (
            max(0.0, float(getattr(wing, "sortie_cooldown_hours", 0.0) or 0.0))
            if self.air_wing_has_global_sortie_cooldown(wing)
            else 0.0
        )
        hours = max(0.0, float(hours or 0.0))
        if hours > 0:
            wing.mission_cooldowns[mission_type] = max(
                hours,
                float(wing.mission_cooldowns.get(mission_type, 0.0) or 0.0),
            )
        else:
            wing.mission_cooldowns.pop(mission_type, None)
        wing.sortie_cooldown_hours = max(legacy_global_cooldown, max(wing.mission_cooldowns.values(), default=0.0))

    def air_wing_target_repeat_factor(self, wing, mission_type, tile):
        if not wing or not tile:
            return 1.0
        key = self.tile_key(tile)
        factor = 1.0
        if (getattr(wing, "last_mission_target_keys", {}) or {}).get(mission_type) == key:
            factor *= 0.50
        for other_mission, other_key in (getattr(wing, "last_mission_target_keys", {}) or {}).items():
            if other_mission != mission_type and other_key == key:
                factor *= 0.62
        recent = ((getattr(wing, "mission_target_cooldowns", {}) or {}).get(mission_type, {}) or {}).get(key, 0.0)
        if recent > 0:
            factor *= 0.38
        for other_mission, by_key in (getattr(wing, "mission_target_cooldowns", {}) or {}).items():
            if other_mission != mission_type and isinstance(by_key, dict) and by_key.get(key, 0.0) > 0:
                factor *= 0.62
        if mission_type == "strategic_strike":
            battle = self.battles.get(self.battle_key_for_tile(tile))
            if self.battle_has_enemy_for_owner(battle, getattr(wing, "owner", None)):
                factor *= 0.55
        for salvo in getattr(self, "air_salvos", []) or []:
            if (
                getattr(salvo, "owner", None) is wing.owner
                and getattr(salvo, "source_air_wing_id", None) == wing.id
                and getattr(salvo, "target_tile", None) is tile
                and getattr(salvo, "count", 0) > 0
            ):
                factor *= 0.28 if self.air_salvo_source_mission(salvo) == mission_type else 0.58
        return factor

    def mark_air_wing_mission_target(self, wing, mission_type, tile, hours=None):
        if not wing or not mission_type or not tile:
            return
        key = self.tile_key(tile)
        if getattr(wing, "last_mission_target_keys", None) is None:
            wing.last_mission_target_keys = {}
        if getattr(wing, "mission_target_cooldowns", None) is None:
            wing.mission_target_cooldowns = {}
        wing.last_mission_target_keys[mission_type] = key
        by_key = wing.mission_target_cooldowns.setdefault(mission_type, {})
        if hours is None:
            hours = 18.0 if mission_type == "strategic_strike" else 6.0
        by_key[key] = max(float(by_key.get(key, 0.0) or 0.0), max(0.0, float(hours)))

    def set_air_wing_operation_area_for_wings(self, wings, tile, mode="replace"):
        if mode in ("add", "replace"):
            reachable_wings = [wing for wing in wings if wing]
            if not tile or not reachable_wings or any(not self.air_wing_can_reach_tile(wing, tile) for wing in reachable_wings):
                return False
        changed = False
        for wing in wings:
            ok, _message = self.set_air_wing_operation_area_tile(wing, tile, mode)
            changed = changed or ok
        return changed

    def air_wing_reachable_operation_tiles(self, wing, mission_type=None):
        if not wing or not wing.base_tile:
            return []
        aircraft_type = self.air_wing_primary_type_for_mission(wing, mission_type) or wing.aircraft_type
        return [
            tile for tile in self.air_wing_operation_area_tiles(wing)
            if self.aircraft_type_can_reach_tile(wing.base_tile, aircraft_type, tile)
        ]

    def assign_air_wing_target(self, wing, target_tile):
        if not wing or not target_tile:
            return False, "Нет цели"
        if self.is_water_tile(target_tile):
            return False, "Цель на воде пока не поддержана"
        aircraft_type = self.air_wing_primary_type_for_mission(wing, "strategic_strike") or wing.aircraft_type
        if not self.aircraft_type_can_reach_tile(wing.base_tile, aircraft_type, target_tile):
            return False, "Цель вне радиуса"
        self.set_air_wing_operation_area_tile(wing, target_tile, mode="replace")
        if not self.air_wing_enabled_missions(wing):
            return True, "Цель назначена; выберите миссию"
        return True, f"Район назначен: {target_tile.q}:{target_tile.r}"

    def air_defense_unit_is_movable(self, unit):
        if not unit:
            return False
        return unit.unit_class not in AIR_DEFENSE_IMMOBILE_CLASSES

    def air_defense_can_enter_tile(self, unit, tile):
        return bool(
            unit
            and tile
            and tile.owner is unit.owner
            and not self.is_water_tile(tile)
        )

    def find_air_defense_path(self, unit, target_tile):
        if not unit or not target_tile or unit.tile is target_tile:
            return []
        if not self.air_defense_can_enter_tile(unit, target_tile):
            return []

        max_expansions = self.division_path_expansion_limit(unit.tile, target_tile)
        frontier = []
        counter = 0
        heapq.heappush(frontier, (0.0, counter, unit.tile))
        start_key = self.tile_key(unit.tile)
        target_key = self.tile_key(target_tile)
        came_from = {start_key: None}
        tile_lookup = {start_key: unit.tile}
        cost_so_far = {start_key: 0.0}
        expansions = 0

        while frontier and expansions < max_expansions:
            _priority, _counter, current = heapq.heappop(frontier)
            expansions += 1
            if current is target_tile:
                break
            current_key = self.tile_key(current)
            for neighbor in self.neighbor_tiles(current):
                if not self.air_defense_can_enter_tile(unit, neighbor):
                    continue
                neighbor_key = self.tile_key(neighbor)
                movement_cost = max(1.0, float(getattr(neighbor, "movement_cost", 1.0) or 1.0))
                new_cost = cost_so_far[current_key] + movement_cost
                if neighbor_key not in cost_so_far or new_cost < cost_so_far[neighbor_key]:
                    cost_so_far[neighbor_key] = new_cost
                    tile_lookup[neighbor_key] = neighbor
                    heuristic = self.hex_distance(neighbor, target_tile)
                    counter += 1
                    heapq.heappush(frontier, (new_cost + heuristic, counter, neighbor))
                    came_from[neighbor_key] = current_key

        if target_key not in came_from:
            return []

        path = []
        current_key = target_key
        while current_key and current_key != start_key:
            path.append(tile_lookup[current_key])
            current_key = came_from.get(current_key)
        path.reverse()
        return path

    def move_air_defense_unit(self, unit, target_tile):
        if not unit or not target_tile:
            return False, "Нет цели перемещения"
        if not self.air_defense_unit_is_movable(unit):
            return False, "Эта ПВО стационарная"
        if target_tile.owner is not unit.owner:
            return False, "ПВО можно двигать только по своей территории"
        if self.is_water_tile(target_tile):
            return False, "ПВО нельзя поставить на воду"
        if unit.tile is target_tile:
            unit.target_tile = None
            unit.path = []
            unit.route_tiles = []
            return True, "ПВО уже здесь"
        path = self.find_air_defense_path(unit, target_tile)
        if not path:
            return False, "Нет маршрута для ПВО"
        unit.target_tile = target_tile
        unit.path = path
        unit.route_tiles = [unit.tile] + list(path)
        unit.movement_progress = 0.0
        unit.visual_movement_progress = 0.0
        unit.readiness = min(unit.readiness, 0.55)
        return True, f"ПВО выдвигается в {target_tile.q}:{target_tile.r}"

    def create_airbase(self, player, tile, coverage=AIRBASE_STARTING_COVERAGE):
        if not player or not tile or self.is_water_tile(tile):
            return None
        self.set_tile_building_coverage(
            tile,
            "airbase",
            max(coverage, (getattr(tile, "building_coverage", {}) or {}).get("airbase", 0.0)),
            INFRASTRUCTURE_COVERAGE_LIMITS["airbase"][1],
        )
        effective_coverage = self.effective_building_coverage(tile, "airbase")
        airbase = Airbase(
            id=self.next_airbase_id,
            owner=player,
            tile=tile,
            runway_level=1 + int(effective_coverage >= 0.32),
            aircraft_capacity=max(18, int(28 + effective_coverage * 90)),
            helicopter_capacity=max(8, int(8 + effective_coverage * 38)),
            fuel_storage=8_000 + effective_coverage * 38_000,
            munition_storage=4_000 + effective_coverage * 18_000,
            hangar_level=1,
            hardened_shelter_level=1 if effective_coverage >= 0.30 else 0,
            repair_capacity=0.8 + effective_coverage * 1.4,
            radar_control_level=1,
        )
        self.next_airbase_id += 1
        self.airbases.append(airbase)
        player.airbases.append(airbase)
        tile.airbase = airbase
        self.tile_visual_revision += 1
        self.invalidate_tile_visual_cache()
        return airbase

    def create_air_wing(self, player, base_tile, aircraft_type, count):
        if not player or not base_tile or count <= 0 or aircraft_type not in AIRCRAFT_TYPES:
            return None
        if base_tile.owner is not player:
            return None
        capacity = self.base_capacity_for_wing(base_tile, aircraft_type)
        load = self.based_aircraft_load(base_tile, helicopter=self.aircraft_type_is_helicopter(aircraft_type))
        if capacity <= 0 or load + int(count) > capacity:
            return None
        wing = AirWing(
            id=self.next_air_wing_id,
            owner=player,
            base_tile=base_tile,
            aircraft_type=aircraft_type,
            aircraft_count=int(count),
            aircraft_composition={aircraft_type: int(count)},
            current_loadout=self.default_air_wing_loadout(aircraft_type),
        )
        self.refresh_air_wing_interceptor_loadout(wing, refill_new_capacity=True)
        self.next_air_wing_id += 1
        return self.register_air_wing(wing)

    def air_wing_creation_base_tile(self, player, aircraft_type):
        if not player or aircraft_type not in AIRCRAFT_TYPES:
            return None

        candidate_tiles = []
        for tile in self.selected_hex_tiles():
            if tile and tile.owner is player:
                candidate_tiles.append(tile)
        selected_wing = self.air_wing_by_id(self.selected_air_wing_id)
        if selected_wing and selected_wing.owner is player and selected_wing.base_tile:
            candidate_tiles.append(selected_wing.base_tile)
        for airbase in getattr(player, "airbases", []) or []:
            if airbase.tile:
                candidate_tiles.append(airbase.tile)

        seen = set()
        for tile in candidate_tiles:
            key = self.tile_key(tile)
            if key in seen:
                continue
            seen.add(key)
            capacity = self.base_capacity_for_wing(tile, aircraft_type)
            if capacity <= 0:
                continue
            load = self.based_aircraft_load(tile, helicopter=self.aircraft_type_is_helicopter(aircraft_type))
            if load < capacity:
                return tile
        return None

    def create_air_wing_from_stockpile(self, player, aircraft_type, requested_count):
        if not player or aircraft_type not in AIRCRAFT_TYPES:
            return None
        reserve = self.aircraft_stockpile_count(player, aircraft_type)
        if reserve <= 0:
            return None
        base_tile = self.air_wing_creation_base_tile(player, aircraft_type)
        if not base_tile:
            return None
        capacity = self.base_capacity_for_wing(base_tile, aircraft_type)
        load = self.based_aircraft_load(base_tile, helicopter=self.aircraft_type_is_helicopter(aircraft_type))
        count = min(max(1, int(requested_count)), reserve, max(0, capacity - load))
        if count <= 0:
            return None
        wing = self.create_air_wing(player, base_tile, aircraft_type, count)
        if not wing:
            return None
        if player.aircraft_stockpile is None:
            player.aircraft_stockpile = {}
        player.aircraft_stockpile[aircraft_type] = max(0, reserve - count)
        return wing

    def create_air_defense_unit(self, player, tile, unit_class):
        data = self.air_defense_class_data(unit_class)
        if not player or not tile or self.is_water_tile(tile) or not data:
            return None
        unit = AirDefenseUnit(
            id=self.next_air_defense_unit_id,
            owner=player,
            tile=tile,
            unit_class=unit_class,
            radar_range_cells=int(data.get("radar_range_cells", 0)),
            fire_range_cells=int(data.get("fire_range_cells", 0)),
            min_range_cells=int(data.get("min_range_cells", 0)),
            ammo=int(data.get("ammo", 0)),
            readiness=float(data.get("readiness", 1.0)),
            camouflage=float(data.get("camouflage", 0.0)),
            radar_active=bool(data.get("radar_active", False)),
            detection_power=float(data.get("detection_power", 0.0)),
            tracking_quality=float(data.get("tracking_quality", 0.0)),
            tracking_channels=int(data.get("tracking_channels", 0)),
            fire_channels=int(data.get("fire_channels", 0)),
            max_targets_per_tick=int(data.get("max_targets_per_tick", 0)),
            interceptors_per_target=max(1, int(data.get("interceptors_per_target", 1))),
            missile_profile=data.get("missile_profile"),
        )
        self.next_air_defense_unit_id += 1
        return self.register_air_defense_unit(unit)

    def munition_profile_factor(self, flight_profile, range_ratio):
        t = self.clamp01(range_ratio)
        if flight_profile == "sqrt":
            return math.sqrt(t)
        if flight_profile == "square":
            return t * t
        if flight_profile == "glide":
            return self.clamp01(0.18 + math.sqrt(t) * 0.92)
        if flight_profile == "rocket_boost_then_glide":
            return self.clamp01(0.12 + t * 0.55 + t * t * 0.35)
        if flight_profile == "sustained_motor":
            return self.clamp01(t * 0.72)
        if flight_profile == "two_stage":
            return self.clamp01(t * 0.58 + max(0.0, t - 0.70) * 0.35)
        if flight_profile == "ballistic":
            return self.clamp01(0.20 + t * 0.42)
        return t

    def munition_interceptability(self, munition_id, launch_distance):
        munition = self.munition_data(munition_id)
        if not munition:
            return 0.0
        max_range = max(0.001, float(munition.get("max_range", 1.0)))
        range_ratio = max(0.0, launch_distance) / max_range
        profile_factor = self.munition_profile_factor(munition.get("flight_profile", "linear"), range_ratio)
        low = float(munition.get("min_interceptability", 0.0))
        high = float(munition.get("max_interceptability", low))
        return self.clamp01(low + (high - low) * profile_factor)

    def choose_air_mission_launch_distance(
        self,
        target_distance,
        munition_id,
        known_or_suspected_air_defense_radius=0,
        risk_policy="normal",
        mission_type="strategic_strike",
    ):
        munition = self.munition_data(munition_id)
        if not munition:
            return None
        min_range = float(munition.get("min_range", 0.0))
        max_range = float(munition.get("max_range", 0.0))
        optimal = float(munition.get("optimal_range", max_range))
        target_distance = max(0.0, float(target_distance))
        if target_distance > max_range:
            return None

        safe_edge = max(0.0, float(known_or_suspected_air_defense_radius))
        if risk_policy == "cautious":
            desired = max(optimal, safe_edge, max_range * 0.82)
        elif risk_policy == "aggressive":
            desired = max(min_range, min(optimal * 0.65, max_range * 0.55))
        elif risk_policy == "all_out":
            desired = min_range
        else:
            desired = max(optimal, safe_edge if safe_edge > 0 else optimal * 0.75)
        if mission_type == "cas":
            desired = min(desired, max_range * 0.62)
        return max(min_range, min(max_range, target_distance, desired))

    def tiles_within_radius(self, center_tile, radius):
        if not center_tile or radius < 0:
            return []
        result = []
        for tile in self.hex_grid:
            if self.hex_distance(center_tile, tile) <= radius:
                result.append(tile)
        return result

    def hex_round_tile(self, q, r, s):
        rounded_q = round(q)
        rounded_r = round(r)
        rounded_s = round(s)
        q_diff = abs(rounded_q - q)
        r_diff = abs(rounded_r - r)
        s_diff = abs(rounded_s - s)

        if q_diff > r_diff and q_diff > s_diff:
            rounded_q = -rounded_r - rounded_s
        elif r_diff > s_diff:
            rounded_r = -rounded_q - rounded_s
        else:
            rounded_s = -rounded_q - rounded_r
        return self.hex_lookup.get((int(rounded_q), int(rounded_r)))

    def tile_between(self, start_tile, end_tile, fraction):
        if not start_tile or not end_tile:
            return None
        t = self.clamp01(fraction)
        start_s = getattr(start_tile, "s", -start_tile.q - start_tile.r)
        end_s = getattr(end_tile, "s", -end_tile.q - end_tile.r)
        return self.hex_round_tile(
            start_tile.q + (end_tile.q - start_tile.q) * t,
            start_tile.r + (end_tile.r - start_tile.r) * t,
            start_s + (end_s - start_s) * t,
        )

    def launch_tile_for_target_distance(self, origin_tile, target_tile, launch_distance):
        if not origin_tile or not target_tile:
            return None
        total_distance = max(0.001, self.hex_distance(origin_tile, target_tile))
        progress_from_origin = self.clamp01(1.0 - max(0.0, launch_distance) / total_distance)
        return self.tile_between(origin_tile, target_tile, progress_from_origin) or origin_tile

    def air_defense_fire_tiles(self, unit):
        if not unit or not unit.tile or unit.fire_range_cells <= 0:
            return []
        return [
            tile for tile in self.tiles_within_radius(unit.tile, unit.fire_range_cells)
            if self.hex_distance(unit.tile, tile) >= max(0, unit.min_range_cells)
        ]

    def air_defense_detection_tiles(self, unit):
        if not unit or not unit.tile:
            return []
        radius = max(unit.radar_range_cells, unit.fire_range_cells if not unit.radar_active else 0)
        return self.tiles_within_radius(unit.tile, radius)

    def air_defense_units_covering_tile(self, owner, tile):
        if not owner or not tile:
            return []
        return [
            unit for unit in getattr(owner, "air_defense_units", []) or []
            if unit.fire_range_cells > 0
            and unit.readiness > 0
            and unit.tile
            and self.hex_distance(unit.tile, tile) <= unit.fire_range_cells
            and self.hex_distance(unit.tile, tile) >= max(0, unit.min_range_cells)
        ]

    def air_defense_units_detecting_tile(self, owner, tile):
        if not owner or not tile:
            return []
        return [
            unit for unit in getattr(owner, "air_defense_units", []) or []
            if unit.tile
            and unit.radar_range_cells > 0
            and unit.radar_active
            and self.hex_distance(unit.tile, tile) <= unit.radar_range_cells
        ]

    def air_defense_range_factor(self, unit, target_tile):
        if not unit or not unit.tile or not target_tile:
            return 0.0
        distance = self.hex_distance(unit.tile, target_tile)
        if distance < max(0, unit.min_range_cells) or distance > unit.fire_range_cells:
            return 0.0
        profile = AIR_DEFENSE_INTERCEPTOR_PROFILES.get(unit.missile_profile or "", {})
        profile_max_range = max(0.001, float(profile.get("max_range", unit.fire_range_cells or 1)))
        no_escape_range = float(profile.get("no_escape_range", profile_max_range * 0.45))
        if distance <= no_escape_range:
            return 1.0
        range_ratio = (distance - no_escape_range) / max(0.001, profile_max_range - no_escape_range)
        return max(0.28, 1.0 - range_ratio * 0.55)

    def air_target_altitude_factor(self, unit, aircraft_type):
        altitude = self.aircraft_type_data(aircraft_type).get("altitude_class", "medium")
        unit_class = getattr(unit, "unit_class", "")
        if altitude in {"nap_of_earth", "low"}:
            if unit_class in {"manpads_team", "short_range_aa"}:
                return 1.14
            if unit_class == "long_range_sam":
                return 0.72
        if altitude == "high":
            if unit_class in {"medium_range_sam", "long_range_sam"}:
                return 1.10
            if unit_class == "manpads_team":
                return 0.45
        return 1.0

    def target_priority_value_for_salvo(self, salvo):
        if not salvo:
            return 1.0
        munition = self.munition_data(salvo.munition_type)
        munition_type = munition.get("type")
        priority = 1.0
        if munition_type in {"heavy_strategic_missile", "ballistic_missile"}:
            priority += 1.2
        elif munition_type in {"cruise_missile", "glide_bomb"}:
            priority += 0.55
        if salvo.target_object_type in {"airbase", "bunker", "sam", "radar", "factory", "depot", "city"}:
            priority += 1.05
        target_tile = salvo.target_tile
        if target_tile and target_tile.owner and getattr(target_tile.owner, "capital_tile", None) is target_tile:
            priority += 1.1
        return priority

    def target_priority_value_for_air_wing(self, wing, mission_type, aircraft_type, target_tile=None):
        data = self.aircraft_type_data(aircraft_type)
        priority = 0.85
        if mission_type == "cas":
            priority += 0.65
        if mission_type == "strategic_strike":
            priority += 0.85
        if self.aircraft_type_is_helicopter(aircraft_type):
            priority += 0.35
        if data.get("category") in {"cas_aircraft", "fighter_bomber", "strategic_bomber"}:
            priority += 0.45
        if target_tile and target_tile.owner and getattr(target_tile.owner, "capital_tile", None) is target_tile:
            priority += 0.45
        return priority

    def air_should_fire(self, chance, target_priority, ammo_cost=1, ammo_available=1):
        chance = self.clamp01(chance)
        priority = max(0.0, float(target_priority))
        scarcity = 1.0
        if ammo_available <= ammo_cost * 2:
            scarcity = 1.25
        if chance >= AIR_ESTIMATE_NORMAL_FIRE_THRESHOLD * scarcity:
            return True
        if priority >= 1.7 and chance >= AIR_ESTIMATE_DESPERATE_FIRE_THRESHOLD * scarcity:
            return True
        if priority >= 2.6 and chance >= AIR_ESTIMATE_MINIMAL_FIRE_THRESHOLD * scarcity:
            return True
        return False

    def estimate_intercept_or_hit_chance(self, attacker, weapon, target, launch_context=None):
        context = launch_context or {}
        if isinstance(target, AirSalvo):
            if isinstance(attacker, AirWing):
                wing = attacker
                salvo = target
                current_tile = context.get("target_tile") or salvo.current_tile or salvo.target_tile
                mission_type = context.get("mission_type", "intercept")
                aircraft_type = context.get("aircraft_type") or self.air_wing_primary_type_for_mission(wing, mission_type) or wing.aircraft_type
                ready_count = self.air_wing_ready_count_for_type(wing, aircraft_type)
                sorties = min(max(1, int(context.get("sorties", ready_count or 1))), max(0, ready_count))
                interceptor_munition = context.get("interceptor_munition") or getattr(wing, "interceptor_munition", None)
                if interceptor_munition not in MUNITIONS:
                    interceptor_munition = self.air_wing_default_interceptor_munition(wing)
                interceptor_data = self.munition_data(interceptor_munition)
                engaged_count = self.air_wing_engaged_salvo_count(wing, aircraft_type, sorties, salvo)
                interceptors_per_target = self.air_wing_interceptors_per_target(aircraft_type)
                ammo_cost = engaged_count * interceptors_per_target
                if (
                    not wing
                    or not current_tile
                    or sorties <= 0
                    or not interceptor_data
                    or engaged_count <= 0
                    or not self.aircraft_type_can_reach_tile(wing.base_tile, aircraft_type, current_tile)
                ):
                    return AirCombatEstimate(reason="no_interceptor_aircraft")
                aircraft_data = self.aircraft_type_data(aircraft_type)
                detection = self.clamp01(
                    0.16
                    + float(aircraft_data.get("radar", 0.0)) * 0.28
                    + float(aircraft_data.get("recon", 0.0)) * 0.22
                    + salvo.average_rcs * 0.42
                    + salvo.average_infrared_signature * 0.10
                )
                tracking = self.clamp01(
                    detection * 0.42
                    + float(aircraft_data.get("radar", 0.0)) * 0.32
                    + float(aircraft_data.get("speed", 1.0)) * 0.10
                    + float(aircraft_data.get("ew", 0.0)) * 0.08
                )
                speed_factor = max(0.28, 1.0 - max(0.0, salvo.terminal_speed - 1.0) * 0.18)
                maneuver_factor = max(0.45, 1.0 - salvo.average_maneuverability * 0.30)
                missile_quality = self.clamp01(
                    float(interceptor_data.get("accuracy", 0.55)) * 0.55
                    + float(interceptor_data.get("guidance_quality", 0.55)) * 0.35
                    + float(interceptor_data.get("maneuverability", 0.45)) * 0.10
                )
                missile_speed_factor = max(0.55, min(1.35, float(interceptor_data.get("terminal_speed", 1.5)) / max(0.35, salvo.terminal_speed)))
                hit_chance = self.clamp01(
                    (0.20 + tracking * 0.34)
                    * detection
                    * speed_factor
                    * maneuver_factor
                    * max(0.55, float(aircraft_data.get("survivability", 0.5)))
                    * (0.65 + missile_quality * 0.55)
                    * missile_speed_factor
                )
                priority = self.target_priority_value_for_salvo(salvo)
                should_fire = self.air_should_fire(hit_chance, priority, ammo_cost, getattr(wing, "interceptor_ammo", 0))
                if not should_fire and engaged_count > 0 and hit_chance > 0.03:
                    should_fire = True
                return AirCombatEstimate(
                    detection_chance=detection,
                    tracking_chance=tracking,
                    intercept_chance=hit_chance,
                    expected_hits=engaged_count * hit_chance,
                    expected_damage=engaged_count * hit_chance,
                    ammo_cost=ammo_cost,
                    target_priority=priority,
                    should_fire=should_fire,
                    reason="air_wing_salvo_intercept",
                )

            unit = attacker
            salvo = target
            chance = self.air_defense_salvo_intercept_chance(unit, salvo)
            engaged_count = self.air_defense_engaged_salvo_count(unit, salvo)
            ammo_cost = engaged_count * max(1, getattr(unit, "interceptors_per_target", 1))
            priority = self.target_priority_value_for_salvo(salvo)
            should_fire = engaged_count > 0 and self.air_should_fire(chance, priority, ammo_cost, getattr(unit, "ammo", 0))
            return AirCombatEstimate(
                detection_chance=self.clamp01(0.35 + getattr(unit, "detection_power", 0.0) * 0.65),
                tracking_chance=self.clamp01(getattr(unit, "tracking_quality", 0.0)),
                intercept_chance=chance,
                expected_hits=engaged_count * chance,
                expected_damage=engaged_count * chance,
                ammo_cost=ammo_cost,
                target_priority=priority,
                should_fire=should_fire or (isinstance(unit, DivisionAirDefenseThreat) and engaged_count > 0 and chance > 0.03),
                reason="salvo_intercept",
            )

        if isinstance(target, AirWing):
            if isinstance(attacker, AirWing):
                interceptor_wing = attacker
                target_wing = target
                target_tile = context.get("exposure_tile") or context.get("target_tile") or getattr(target_wing, "target_tile", None)
                mission_type = context.get("mission_type", "intercept")
                interceptor_aircraft_type = (
                    context.get("interceptor_aircraft_type")
                    or self.air_wing_primary_type_for_mission(interceptor_wing, mission_type)
                    or interceptor_wing.aircraft_type
                )
                target_aircraft_type = (
                    context.get("target_aircraft_type")
                    or context.get("aircraft_type")
                    or target_wing.aircraft_type
                )
                ready_count = self.air_wing_ready_count_for_type(interceptor_wing, interceptor_aircraft_type)
                sorties = min(max(1, int(context.get("sorties", ready_count or 1))), max(0, ready_count))
                target_sorties = max(1, int(context.get("target_sorties", 1)))
                interceptor_munition = context.get("interceptor_munition") or getattr(interceptor_wing, "interceptor_munition", None)
                if interceptor_munition not in MUNITIONS:
                    interceptor_munition = self.air_wing_default_interceptor_munition(interceptor_wing)
                interceptor_data = self.munition_data(interceptor_munition)
                engaged_count = self.air_wing_engaged_aircraft_count(
                    interceptor_wing,
                    interceptor_aircraft_type,
                    sorties,
                    target_sorties,
                )
                interceptors_per_target = self.air_wing_interceptors_per_target(interceptor_aircraft_type)
                ammo_cost = engaged_count * interceptors_per_target
                if (
                    not interceptor_wing
                    or not target_tile
                    or sorties <= 0
                    or engaged_count <= 0
                    or not interceptor_data
                    or not self.aircraft_type_can_reach_tile(interceptor_wing.base_tile, interceptor_aircraft_type, target_tile)
                ):
                    return AirCombatEstimate(reason="no_air_to_air_fire_solution")
                interceptor_data_aircraft = self.aircraft_type_data(interceptor_aircraft_type)
                target_data = self.aircraft_type_data(target_aircraft_type)
                target_rcs = float(target_data.get("rcs", 0.65))
                target_stealth = float(target_data.get("stealth", 0.0))
                detection = self.clamp01(
                    0.14
                    + float(interceptor_data_aircraft.get("radar", 0.0)) * 0.32
                    + float(interceptor_data_aircraft.get("recon", 0.0)) * 0.16
                    + target_rcs * 0.26
                    - target_stealth * 0.20
                )
                tracking = self.clamp01(
                    detection * 0.38
                    + float(interceptor_data_aircraft.get("radar", 0.0)) * 0.28
                    + float(interceptor_data_aircraft.get("speed", 1.0)) * 0.11
                    + float(interceptor_data_aircraft.get("ew", 0.0)) * 0.08
                )
                target_speed = float(target_data.get("speed", 1.0))
                target_survivability = float(target_data.get("survivability", 0.5))
                speed_factor = max(0.38, 1.0 - max(0.0, target_speed - 1.0) * 0.16)
                defensive = (
                    getattr(target_wing, "mission_state", "") == "defensive"
                    or getattr(target_wing, "defensive_hours", 0.0) > 0
                )
                defensive_factor = 0.52 if defensive else 1.0
                missile_quality = self.clamp01(
                    float(interceptor_data.get("accuracy", 0.55)) * 0.50
                    + float(interceptor_data.get("guidance_quality", 0.55)) * 0.36
                    + float(interceptor_data.get("maneuverability", 0.45)) * 0.14
                )
                missile_speed_factor = max(0.55, min(1.30, float(interceptor_data.get("terminal_speed", 1.5)) / max(0.45, target_speed)))
                hit_chance = self.clamp01(
                    (0.18 + tracking * 0.34)
                    * detection
                    * speed_factor
                    * max(0.42, 1.0 - target_survivability * 0.38)
                    * defensive_factor
                    * (0.62 + missile_quality * 0.58)
                    * missile_speed_factor
                )
                priority = self.target_priority_value_for_air_wing(
                    target_wing,
                    context.get("target_mission_type", getattr(target_wing, "mission", "none")),
                    target_aircraft_type,
                    target_tile,
                )
                should_fire = self.air_should_fire(
                    hit_chance,
                    priority,
                    ammo_cost,
                    getattr(interceptor_wing, "interceptor_ammo", 0),
                )
                return AirCombatEstimate(
                    detection_chance=detection,
                    tracking_chance=tracking,
                    hit_chance=hit_chance,
                    expected_hits=engaged_count * hit_chance,
                    expected_kills=engaged_count * hit_chance * AIR_CARRIER_DESTROY_FROM_HIT_CHANCE,
                    expected_damage=engaged_count * hit_chance,
                    ammo_cost=ammo_cost,
                    target_priority=priority,
                    should_fire=should_fire,
                    reason="air_to_air_carrier_attack",
                )

            unit = attacker
            wing = target
            aircraft_type = context.get("aircraft_type") or wing.aircraft_type
            target_tile = context.get("exposure_tile") or context.get("target_tile") or getattr(wing, "target_tile", None)
            sorties = max(1, int(context.get("sorties", 1)))
            if not unit or not target_tile or getattr(unit, "ammo", 0) <= 0 or getattr(unit, "fire_range_cells", 0) <= 0:
                return AirCombatEstimate(reason="no_fire_solution")
            range_factor = self.air_defense_range_factor(unit, target_tile)
            if range_factor <= 0:
                return AirCombatEstimate(reason="outside_range")
            profile = AIR_DEFENSE_INTERCEPTOR_PROFILES.get(unit.missile_profile or "", {})
            aircraft_data = self.aircraft_type_data(aircraft_type)
            rcs_sensitivity = float(profile.get("target_rcs_sensitivity", 0.45))
            stealth = float(aircraft_data.get("stealth", 0.0))
            rcs = float(aircraft_data.get("rcs", 0.65))
            detection = self.clamp01(
                0.18
                + getattr(unit, "detection_power", 0.0) * 0.52
                + rcs * rcs_sensitivity * 0.34
                + self.air_defense_radar_support_bonus(unit.owner, target_tile)
                - stealth * 0.22
            )
            tracking = self.clamp01(getattr(unit, "tracking_quality", 0.0) * 0.75 + detection * 0.25)
            speed = float(aircraft_data.get("speed", 1.0))
            survivability = float(aircraft_data.get("survivability", 0.5))
            speed_factor = max(0.42, 1.0 - max(0.0, speed - 1.0) * 0.17)
            altitude_factor = self.air_target_altitude_factor(unit, aircraft_type)
            defensive = getattr(wing, "mission_state", "") == "defensive" or getattr(wing, "defensive_hours", 0.0) > 0
            defensive_factor = 0.48 if defensive else 1.0
            if self.aircraft_type_is_helicopter(aircraft_type):
                defensive_factor = 0.68 if defensive else 1.12
            readiness_factor = self.clamp01(getattr(unit, "readiness", 1.0)) * self.clamp01(getattr(unit, "health", 1.0))
            risk_policy = context.get("risk_policy") or getattr(wing, "risk_policy", "normal")
            risk_factor = {"cautious": 0.82, "normal": 1.0, "aggressive": 1.18, "all_out": 1.32}.get(risk_policy, 1.0)
            unit_class = getattr(unit, "unit_class", "")
            category = aircraft_data.get("category", "")
            class_target_factor = 1.0
            if unit_class == "manpads_team" and self.aircraft_type_is_helicopter(aircraft_type):
                class_target_factor = 1.85
            elif unit_class == "short_range_aa" and (self.aircraft_type_is_helicopter(aircraft_type) or category == "cas_aircraft"):
                class_target_factor = 1.55
            elif unit_class == "long_range_sam" and self.aircraft_type_is_helicopter(aircraft_type):
                class_target_factor = 0.70
            base_hit = AIR_CARRIER_EXPOSURE_BASE_LOSS_CHANCE * 12.0
            hit_chance = self.clamp01(
                base_hit
                * detection
                * tracking
                * range_factor
                * speed_factor
                * altitude_factor
                * max(0.35, 1.0 - survivability * 0.42)
                * defensive_factor
                * readiness_factor
                * risk_factor
                * class_target_factor
            )
            interceptors_per_target = max(1, getattr(unit, "interceptors_per_target", 1))
            available_interceptors = max(0, unit.ammo // interceptors_per_target)
            engaged_count = max(
                0,
                min(
                    sorties,
                    available_interceptors,
                    max(0, getattr(unit, "tracking_channels", 0)),
                    max(0, getattr(unit, "fire_channels", 0)),
                    max(0, getattr(unit, "max_targets_per_tick", 0)),
                ),
            )
            ammo_cost = engaged_count * interceptors_per_target
            priority = self.target_priority_value_for_air_wing(
                wing,
                context.get("mission_type", getattr(wing, "mission", "none")),
                aircraft_type,
                target_tile,
            )
            should_fire = engaged_count > 0 and self.air_should_fire(hit_chance, priority, ammo_cost, getattr(unit, "ammo", 0))
            if (
                not should_fire
                and isinstance(unit, DivisionAirDefenseThreat)
                and engaged_count > 0
                and hit_chance > 0.03
                and context.get("mission_type") in {"cas", "strategic_strike", "intercept", "air_superiority", "patrol"}
            ):
                should_fire = True
            return AirCombatEstimate(
                detection_chance=detection,
                tracking_chance=tracking,
                hit_chance=hit_chance,
                expected_hits=engaged_count * hit_chance,
                expected_kills=engaged_count * hit_chance * AIR_CARRIER_DESTROY_FROM_HIT_CHANCE,
                expected_damage=engaged_count * hit_chance,
                ammo_cost=ammo_cost,
                target_priority=priority,
                should_fire=should_fire,
                reason="carrier_attack",
            )

        return AirCombatEstimate(reason="unsupported_target")

    def set_air_wing_mission_state(self, wing, state, target_tile=None, summary=None):
        if not wing:
            return
        valid_states = {"approach", "attack_run", "defensive", "egress", "returning", "aborted"}
        wing.mission_state = state if state in valid_states else "returning"
        wing.mission_state_hours = 0.0
        wing.mission_target_tile_key = self.tile_key(target_tile) if target_tile else None
        if summary is not None:
            wing.last_air_combat_summary = summary

    def tick_air_wing_mission_state(self, wing, elapsed_hours):
        if not wing or elapsed_hours <= 0:
            return
        wing.mission_state_hours = max(0.0, getattr(wing, "mission_state_hours", 0.0) + elapsed_hours)
        wing.defensive_hours = max(0.0, getattr(wing, "defensive_hours", 0.0) - elapsed_hours)
        wing.aborted_hours = max(0.0, getattr(wing, "aborted_hours", 0.0) - elapsed_hours)
        if wing.aborted_hours > 0:
            if wing.mission_state != "aborted":
                self.set_air_wing_mission_state(wing, "aborted", summary=wing.last_air_combat_summary)
            return
        if wing.defensive_hours > 0:
            if wing.mission_state != "defensive":
                self.set_air_wing_mission_state(wing, "defensive", summary=wing.last_air_combat_summary)
            return
        if self.air_wing_has_global_sortie_cooldown(wing):
            if wing.mission_state not in {"egress", "returning"}:
                self.set_air_wing_mission_state(wing, "returning", summary=wing.last_air_combat_summary)
            return
        if wing.mission_state == "egress":
            if wing.mission_state_hours >= AIR_VISUAL_EGRESS_HOURS:
                self.set_air_wing_mission_state(wing, "returning", summary=wing.last_air_combat_summary)
            return
        if wing.mission_state in {"aborted", "defensive"}:
            self.set_air_wing_mission_state(wing, "returning", summary=wing.last_air_combat_summary)

    def division_tactical_air_defense_covered_tiles(self, division):
        if not division or getattr(division, "strength", 0.0) <= 0:
            return []
        tiles = []
        if getattr(division, "tile", None):
            tiles.append(division.tile)
        if getattr(division, "battle_side", None) == "attacker" and getattr(division, "battle_id", None):
            battle = self.battles.get(division.battle_id)
            if battle and battle.tile:
                tiles.append(battle.tile)
        elif getattr(division, "route_mode", None) == "attack" and getattr(division, "target_tile", None):
            tiles.append(division.target_tile)
        unique = []
        seen = set()
        for tile in tiles:
            key = self.tile_key(tile)
            if key in seen:
                continue
            seen.add(key)
            unique.append(tile)
        return unique

    def division_tactical_air_defense_covers_tile(self, division, tile):
        if not division or not tile:
            return False
        tile_key = self.tile_key(tile)
        return any(self.tile_key(covered_tile) == tile_key for covered_tile in self.division_tactical_air_defense_covered_tiles(division))

    def division_tactical_air_defense_readiness(self, division):
        strength_ratio = self.clamp01(getattr(division, "strength", 0.0) / max(1.0, getattr(division, "max_strength", 100.0)))
        org_ratio = self.clamp01(getattr(division, "organization", 0.0) / max(1.0, getattr(division, "max_organization", 100.0)))
        supply_ratio = self.division_supply_ratio(division)
        return self.clamp01((0.25 + org_ratio * 0.55 + supply_ratio * 0.20) * strength_ratio)

    def make_division_air_defense_threat(self, division, tile, unit_class, ammo_key, ammo, channel_scale=1.0):
        data = self.air_defense_class_data(unit_class)
        if not data or ammo <= 0:
            return None
        readiness = self.division_tactical_air_defense_readiness(division)
        if readiness <= 0:
            return None
        fire_channels = max(1, min(int(data.get("fire_channels", 1)), int(round(data.get("fire_channels", 1) * channel_scale))))
        tracking_channels = max(1, min(int(data.get("tracking_channels", 1)), int(round(data.get("tracking_channels", 1) * channel_scale))))
        max_targets = max(1, min(int(data.get("max_targets_per_tick", 1)), int(round(data.get("max_targets_per_tick", 1) * channel_scale))))
        return DivisionAirDefenseThreat(
            id=("division_aa", division.id, unit_class, self.tile_key(tile)),
            owner=division.owner,
            tile=tile,
            unit_class=unit_class,
            division_id=division.id,
            ammo_key=ammo_key,
            radar_range_cells=0,
            fire_range_cells=1,
            min_range_cells=0,
            ammo=max(0, int(ammo)),
            readiness=readiness * float(data.get("readiness", 1.0)),
            camouflage=max(float(getattr(division, "camouflage", 0.0)), float(data.get("camouflage", 0.0))),
            radar_active=bool(data.get("radar_active", False)),
            detection_power=float(data.get("detection_power", 0.0)) * (0.75 + channel_scale * 0.25),
            tracking_quality=float(data.get("tracking_quality", 0.0)) * (0.75 + channel_scale * 0.25),
            tracking_channels=tracking_channels,
            fire_channels=fire_channels,
            max_targets_per_tick=max_targets,
            interceptors_per_target=max(1, int(data.get("interceptors_per_target", 1))),
            missile_profile=data.get("missile_profile"),
            health=self.clamp01(getattr(division, "strength", 0.0) / max(1.0, getattr(division, "max_strength", 100.0))),
        )

    def division_tactical_air_defense_threats_for_tile(self, owner, tile):
        if not owner or not tile:
            return []
        threats = []
        for division in getattr(self, "divisions", []) or []:
            if getattr(division, "owner", None) is owner:
                continue
            if getattr(division, "strength", 0.0) <= 0 or not self.division_tactical_air_defense_covers_tile(division, tile):
                continue
            anti_air_ammo = int((division.supply_stock or {}).get("anti_air_ammo", 0.0))
            if anti_air_ammo > 0:
                threats.append(
                    self.make_division_air_defense_threat(
                        division,
                        tile,
                        "manpads_team",
                        "anti_air_ammo",
                        anti_air_ammo,
                        channel_scale=min(1.0, max(0.45, anti_air_ammo / 8.0)),
                    )
                )
            aa_guns = max(0.0, (division.supply_stock or {}).get("old_light_aa_artillery", 0.0))
            light_aa_ammo = int((division.supply_stock or {}).get("light_aa_ammo", 0.0))
            if aa_guns > 0 and light_aa_ammo >= DIVISION_SHORT_AA_AMMO_PER_TARGET:
                channel_scale = min(1.0, max(0.25, aa_guns / max(1.0, AIR_DEFENSE_CLASSES["short_range_aa"]["fire_channels"] * DIVISION_SHORT_AA_GUNS_PER_CHANNEL)))
                threat = self.make_division_air_defense_threat(
                    division,
                    tile,
                    "short_range_aa",
                    "light_aa_ammo",
                    light_aa_ammo,
                    channel_scale=channel_scale,
                )
                if threat:
                    threat.interceptors_per_target = DIVISION_SHORT_AA_AMMO_PER_TARGET
                    threats.append(threat)
        return [threat for threat in threats if threat]

    def air_defense_units_threatening_aircraft(self, owner, tile):
        if not owner or not tile:
            return []
        fixed_units = [
            unit for unit in getattr(self, "air_defense_units", []) or []
            if self.countries_hostile(unit.owner, owner)
            and unit.tile
            and unit.fire_range_cells > 0
            and unit.readiness > 0
            and unit.health > 0
            and getattr(unit, "ammo", 0) > 0
            and self.hex_distance(unit.tile, tile) <= unit.fire_range_cells
            and self.hex_distance(unit.tile, tile) >= max(0, unit.min_range_cells)
        ]
        return fixed_units + self.division_tactical_air_defense_threats_for_tile(owner, tile)

    def spend_air_defense_unit_ammo(self, unit, ammo_cost):
        ammo_cost = max(0, int(ammo_cost))
        if not unit or ammo_cost <= 0:
            return 0
        division_id = getattr(unit, "division_id", None)
        ammo_key = getattr(unit, "ammo_key", None)
        if division_id is not None and ammo_key:
            division = self.division_by_id(division_id)
            if not division:
                unit.ammo = 0
                return 0
            consumed = int(self.consume_division_supply(division, ammo_key, ammo_cost))
            unit.ammo = max(0, int(getattr(unit, "ammo", 0)) - consumed)
            return consumed
        consumed = min(ammo_cost, max(0, int(getattr(unit, "ammo", 0))))
        unit.ammo = max(0, int(getattr(unit, "ammo", 0)) - consumed)
        return consumed

    def air_defense_engaged_aircraft_count(self, unit, sorties):
        if not unit or sorties <= 0:
            return 0
        interceptors_per_target = max(1, getattr(unit, "interceptors_per_target", 1))
        available_interceptors = max(0, getattr(unit, "ammo", 0) // interceptors_per_target)
        return max(
            0,
            min(
                int(sorties),
                available_interceptors,
                max(0, getattr(unit, "tracking_channels", 0)),
                max(0, getattr(unit, "fire_channels", 0)),
                max(0, getattr(unit, "max_targets_per_tick", 0)),
            ),
        )

    def apply_air_wing_air_defense_hits(self, wing, aircraft_type, hits):
        hits = max(0, int(hits))
        if not wing or hits <= 0:
            return 0, 0, 0
        aircraft_data = self.aircraft_type_data(aircraft_type)
        survivability = self.clamp01(float(aircraft_data.get("survivability", 0.5)))
        helicopter = self.aircraft_type_is_helicopter(aircraft_type)
        destroy_chance = AIR_CARRIER_DESTROY_FROM_HIT_CHANCE * (1.25 if helicopter else 1.0) * max(0.55, 1.15 - survivability * 0.55)
        damage_chance = AIR_CARRIER_DAMAGE_FROM_HIT_CHANCE * (1.12 if helicopter else 1.0) * max(0.65, 1.10 - survivability * 0.35)
        destroyed = 0
        damaged = 0
        aborted = 0
        for _hit_index in range(hits):
            roll = random.random()
            if roll < destroy_chance:
                destroyed += 1
            elif roll < destroy_chance + damage_chance:
                damaged += 1
            else:
                aborted += 1
        self.remove_aircraft_from_wing(wing, aircraft_type, destroyed=destroyed, damaged=damaged)
        return destroyed, damaged, aborted

    def air_wing_threat_decision(
        self,
        wing,
        sorties,
        engaged_total,
        hits_total,
        destroyed_total,
        damaged_total,
        aborted_from_hits,
        phase="approach",
        prelaunch_only=False,
    ):
        sorties = max(1, int(sorties or 1))
        risk_policy = getattr(wing, "risk_policy", "normal") if wing else "normal"
        hit_pressure = max(0.0, float(hits_total)) / sorties
        loss_pressure = (
            float(destroyed_total)
            + float(damaged_total) * 0.65
            + float(aborted_from_hits) * 0.25
        ) / sorties
        engaged_pressure = max(0.0, float(engaged_total)) / sorties
        if wing and getattr(wing, "ready_count", 0) <= 0:
            return {
                "aborted": True,
                "defensive": False,
                "decision": "abort",
                "reason": "no_ready_aircraft",
            }

        abort_thresholds = {
            "cautious": 0.01,
            "normal": 0.34,
            "aggressive": 0.56,
            "all_out": 0.78,
        }
        random_abort_chance = {
            "cautious": 0.24,
            "normal": 0.08,
            "aggressive": 0.02,
            "all_out": 0.0,
        }
        threshold = abort_thresholds.get(risk_policy, abort_thresholds["normal"])
        if hits_total > 0 and (risk_policy == "cautious" or loss_pressure >= threshold):
            return {
                "aborted": True,
                "defensive": False,
                "decision": "abort",
                "reason": f"{risk_policy}_loss_pressure",
            }
        if destroyed_total > 0 and risk_policy == "normal" and hit_pressure >= 0.25:
            return {
                "aborted": True,
                "defensive": False,
                "decision": "abort",
                "reason": "normal_destroyed_aircraft",
            }
        if hits_total > 0:
            return {
                "aborted": False,
                "defensive": True,
                "decision": "defensive_continue",
                "reason": f"{risk_policy}_absorbed_hits",
            }
        if engaged_total > 0 and risk_policy in {"cautious", "normal", "aggressive"}:
            chance = random_abort_chance.get(risk_policy, 0.08) * min(1.0, engaged_pressure)
            if not prelaunch_only and random.random() < chance:
                return {
                    "aborted": True,
                    "defensive": False,
                    "decision": "abort",
                    "reason": f"{risk_policy}_fire_pressure",
                }
            return {
                "aborted": False,
                "defensive": True,
                "decision": "defensive_continue",
                "reason": f"{risk_policy}_under_fire",
            }
        return {
            "aborted": False,
            "defensive": False,
            "decision": "continue",
            "reason": "no_threat_pressure",
        }

    def resolve_air_defense_against_air_wing(
        self,
        wing,
        exposure_tile,
        aircraft_type,
        sorties,
        mission_type,
        phase="approach",
        target_tile=None,
        prelaunch_only=False,
    ):
        if not wing or not exposure_tile or sorties <= 0:
            return {
                "engaged": 0,
                "hits": 0,
                "destroyed": 0,
                "damaged": 0,
                "aborted_aircraft": 0,
                "aborted": False,
                "defensive": False,
                "decision": "continue",
                "summary": "",
            }
        defenders = self.air_defense_units_threatening_aircraft(wing.owner, exposure_tile)
        if not defenders:
            return {
                "engaged": 0,
                "hits": 0,
                "destroyed": 0,
                "damaged": 0,
                "aborted_aircraft": 0,
                "aborted": False,
                "defensive": False,
                "decision": "continue",
                "summary": "",
            }
        context = {
            "aircraft_type": aircraft_type,
            "sorties": sorties,
            "mission_type": mission_type,
            "risk_policy": wing.risk_policy,
            "exposure_tile": exposure_tile,
            "target_tile": target_tile or exposure_tile,
            "phase": phase,
        }
        estimates = []
        for unit in defenders:
            estimate = self.estimate_intercept_or_hit_chance(unit, None, wing, context)
            if estimate.should_fire:
                estimates.append((unit, estimate))
        if not estimates:
            return {
                "engaged": 0,
                "hits": 0,
                "destroyed": 0,
                "damaged": 0,
                "aborted_aircraft": 0,
                "aborted": False,
                "defensive": False,
                "decision": "continue",
                "summary": "",
            }
        estimates.sort(key=lambda item: (-item[1].target_priority, -item[1].hit_chance, self.hex_distance(item[0].tile, exposure_tile)))

        engaged_total = 0
        hits_total = 0
        destroyed_total = 0
        damaged_total = 0
        aborted_from_hits = 0
        remaining_sorties = max(0, int(sorties))
        for unit, estimate in estimates:
            if remaining_sorties <= 0:
                break
            engaged_count = self.air_defense_engaged_aircraft_count(unit, remaining_sorties)
            if engaged_count <= 0:
                continue
            hit_chance = self.clamp01(estimate.hit_chance)
            if prelaunch_only:
                engaged_total += engaged_count
                hits_total += int(engaged_count * hit_chance + 0.5)
                continue
            ammo_cost = engaged_count * max(1, getattr(unit, "interceptors_per_target", 1))
            self.spend_air_defense_unit_ammo(unit, ammo_cost)
            hits = min(remaining_sorties, int(engaged_count * hit_chance + 0.5))
            destroyed, damaged, aborted = self.apply_air_wing_air_defense_hits(wing, aircraft_type, hits)
            engaged_total += engaged_count
            hits_total += hits
            destroyed_total += destroyed
            damaged_total += damaged
            aborted_from_hits += aborted
            remaining_sorties = max(0, remaining_sorties - destroyed - damaged - aborted)

        if prelaunch_only:
            decision = self.air_wing_threat_decision(
                wing,
                sorties,
                engaged_total,
                hits_total,
                0,
                hits_total,
                0,
                phase=phase,
                prelaunch_only=True,
            )
            return {
                "engaged": engaged_total,
                "hits": hits_total,
                "destroyed": 0,
                "damaged": 0,
                "aborted_aircraft": 0,
                "aborted": decision["aborted"],
                "defensive": decision["defensive"],
                "decision": decision["decision"],
                "summary": "",
            }

        decision = self.air_wing_threat_decision(
            wing,
            sorties,
            engaged_total,
            hits_total,
            destroyed_total,
            damaged_total,
            aborted_from_hits,
            phase=phase,
        )
        aborted = decision["aborted"]
        defensive = decision["defensive"]
        if hits_total > 0:
            if destroyed_total or damaged_total:
                summary = f"ПВО: {destroyed_total} сбито, {damaged_total} повреждено"
            else:
                summary = "ПВО вынудила уклонение"
        elif engaged_total:
            summary = "ПВО обстреляла крыло"
        else:
            summary = ""
        if defensive and summary:
            summary = f"{summary}, миссия продолжается"
        if aborted:
            wing.aborted_hours = max(getattr(wing, "aborted_hours", 0.0), AIR_CARRIER_ABORTED_COOLDOWN_HOURS)
            wing.sortie_cooldown_hours = max(getattr(wing, "sortie_cooldown_hours", 0.0), AIR_CARRIER_ABORTED_COOLDOWN_HOURS)
            self.set_air_wing_mission_state(wing, "aborted", target_tile, summary)
        elif defensive:
            wing.defensive_hours = max(getattr(wing, "defensive_hours", 0.0), AIR_CARRIER_DEFENSIVE_COOLDOWN_HOURS)
            self.set_air_wing_mission_state(wing, "defensive", target_tile, summary)
        elif phase == "egress":
            self.set_air_wing_mission_state(wing, "egress", target_tile, summary)
        return {
            "engaged": engaged_total,
            "hits": hits_total,
            "destroyed": destroyed_total,
            "damaged": damaged_total,
            "aborted_aircraft": aborted_from_hits,
            "aborted": aborted,
            "defensive": defensive,
            "decision": decision["decision"],
            "summary": summary,
        }

    def resolve_air_wing_interceptors_against_air_wing(
        self,
        target_wing,
        exposure_tile,
        target_aircraft_type,
        target_sorties,
        target_mission_type,
    ):
        if not target_wing or not exposure_tile or target_sorties <= 0:
            return {
                "engaged": 0,
                "hits": 0,
                "destroyed": 0,
                "damaged": 0,
                "aborted_aircraft": 0,
                "aborted": False,
                "summary": "",
            }
        candidates = []
        for interceptor_wing in getattr(self, "air_wings", []) or []:
            if interceptor_wing is target_wing or not self.countries_hostile(interceptor_wing.owner, target_wing.owner):
                continue
            mission = self.air_wing_salvo_intercept_mission_for_tile(interceptor_wing, exposure_tile)
            if not mission:
                continue
            mission_type, interceptor_aircraft_type = mission
            ready_count = self.air_wing_ready_count_for_type(interceptor_wing, interceptor_aircraft_type)
            sorties = max(1, int(math.ceil(ready_count * self.clamp01(interceptor_wing.sortie_intensity) * 0.18)))
            if self.air_wing_engaged_aircraft_count(interceptor_wing, interceptor_aircraft_type, sorties, target_sorties) <= 0:
                continue
            estimate = self.estimate_intercept_or_hit_chance(
                interceptor_wing,
                None,
                target_wing,
                {
                    "exposure_tile": exposure_tile,
                    "mission_type": mission_type,
                    "target_mission_type": target_mission_type,
                    "interceptor_aircraft_type": interceptor_aircraft_type,
                    "target_aircraft_type": target_aircraft_type,
                    "sorties": sorties,
                    "target_sorties": target_sorties,
                },
            )
            if estimate.should_fire:
                candidates.append((interceptor_wing, mission_type, interceptor_aircraft_type, sorties, estimate))
        candidates.sort(
            key=lambda item: (
                -item[4].target_priority,
                -item[4].hit_chance,
                self.hex_distance(item[0].base_tile, exposure_tile),
            )
        )

        engaged_total = 0
        launched_total = 0
        remaining_sorties = max(0, int(target_sorties))
        for interceptor_wing, mission_type, interceptor_aircraft_type, sorties, estimate in candidates:
            if remaining_sorties <= 0:
                break
            engaged_count = self.air_wing_engaged_aircraft_count(
                interceptor_wing,
                interceptor_aircraft_type,
                sorties,
                remaining_sorties,
            )
            if engaged_count <= 0:
                continue
            interceptors_per_target = self.air_wing_interceptors_per_target(interceptor_aircraft_type)
            ammo_spent = engaged_count * interceptors_per_target
            interceptor_wing.interceptor_ammo = max(0, getattr(interceptor_wing, "interceptor_ammo", 0) - ammo_spent)
            self.set_air_wing_mission_state(interceptor_wing, "attack_run", exposure_tile)
            attack_salvo = self.create_air_attack_salvo(
                interceptor_wing.owner,
                interceptor_wing,
                interceptor_aircraft_type,
                getattr(interceptor_wing, "interceptor_munition", None) or self.air_wing_default_interceptor_munition(interceptor_wing),
                engaged_count,
                exposure_tile,
                exposure_tile,
                estimate.hit_chance,
                target_air_wing=target_wing,
                target_aircraft_type=target_aircraft_type,
                target_sorties=remaining_sorties,
                launch_distance=1.0,
            )
            engaged_total += engaged_count
            if attack_salvo:
                launched_total += attack_salvo.count
                remaining_sorties = max(0, remaining_sorties - engaged_count)
            self.set_air_wing_mission_cooldown(interceptor_wing, mission_type, AIR_MISSION_MIN_COOLDOWN_HOURS)
            interceptor_summary = f"УРВВ {ammo_spent}, залп в пути"
            self.set_air_wing_mission_state(interceptor_wing, "egress", exposure_tile, interceptor_summary)

        if engaged_total:
            summary = "Истребители выпустили УРВВ"
            target_wing.defensive_hours = max(getattr(target_wing, "defensive_hours", 0.0), AIR_CARRIER_DEFENSIVE_COOLDOWN_HOURS)
            self.set_air_wing_mission_state(target_wing, "defensive", exposure_tile, summary)
        else:
            summary = ""
        return {
            "engaged": engaged_total,
            "launched": launched_total,
            "hits": 0,
            "destroyed": 0,
            "damaged": 0,
            "aborted_aircraft": 0,
            "aborted": False,
            "summary": summary,
        }

    def munition_uses_air_salvo(self, munition_id, launch_distance=None):
        munition = self.munition_data(munition_id)
        if not munition:
            return False
        munition_type = munition.get("type")
        if munition_type not in AIR_SALVO_INTERCEPTABLE_TYPES:
            return False
        if launch_distance is None:
            return True
        terminal_range = float(munition.get("terminal_range", 0.0))
        return launch_distance > max(0.15, terminal_range)

    def create_air_salvo(
        self,
        owner,
        munition_id,
        count,
        target_tile,
        launch_tile=None,
        source_air_wing=None,
        source_unit_id=None,
        mission_type=None,
        target_unit_id=None,
        target_object_type=None,
        launch_distance=None,
    ):
        munition = self.munition_data(munition_id)
        if not owner or not munition or not target_tile or count <= 0:
            return None
        launch_tile = launch_tile or target_tile
        if launch_distance is None:
            launch_distance = self.hex_distance(launch_tile, target_tile)
        launch_distance = max(0.0, float(launch_distance))
        salvo = AirSalvo(
            id=self.next_air_salvo_id,
            owner=owner,
            munition_type=munition_id,
            count=int(count),
            original_count=int(count),
            target_tile=target_tile,
            launch_tile=launch_tile,
            source_air_wing_id=getattr(source_air_wing, "id", None),
            source_unit_id=source_unit_id,
            mission_type=mission_type or getattr(source_air_wing, "mission", None),
            target_unit_id=target_unit_id,
            target_object_type=target_object_type,
            launch_distance=launch_distance,
            remaining_distance=launch_distance,
            current_tile=launch_tile,
            speed=max(0.05, float(munition.get("cruise_speed", 1.0))),
            terminal_speed=max(0.05, float(munition.get("terminal_speed", munition.get("cruise_speed", 1.0)))),
            altitude_profile=munition.get("altitude_class") or munition.get("flight_profile"),
            flight_profile=munition.get("flight_profile", "linear"),
            average_rcs=float(munition.get("rcs", 0.0)),
            average_infrared_signature=float(munition.get("infrared_signature", 0.0)),
            average_maneuverability=float(munition.get("maneuverability", 0.0)),
            average_interceptability=self.munition_interceptability(munition_id, launch_distance),
        )
        self.next_air_salvo_id += 1
        return self.register_air_salvo(salvo)

    def air_attack_salvo_by_id(self, salvo_id):
        return self.air_attack_salvo_lookup.get(salvo_id)

    def create_air_attack_salvo(
        self,
        owner,
        launcher_wing,
        interceptor_aircraft_type,
        munition_id,
        count,
        launch_tile,
        target_tile,
        hit_chance,
        target_air_wing=None,
        target_air_salvo=None,
        target_aircraft_type=None,
        target_sorties=0,
        launch_distance=None,
    ):
        munition = self.munition_data(munition_id)
        if not owner or not launcher_wing or not munition or not launch_tile or not target_tile or count <= 0:
            return None
        if not hasattr(self, "air_attack_salvos"):
            self.air_attack_salvos = []
        if not hasattr(self, "next_air_attack_salvo_id"):
            self.next_air_attack_salvo_id = 1
        if launch_distance is None:
            launch_distance = self.hex_distance(launch_tile, target_tile)
        launch_distance = max(0.5, float(launch_distance))
        salvo = AirAttackSalvo(
            id=self.next_air_attack_salvo_id,
            owner=owner,
            launcher_air_wing_id=launcher_wing.id,
            interceptor_aircraft_type=interceptor_aircraft_type,
            munition_type=munition_id,
            count=int(count),
            original_count=int(count),
            launch_tile=launch_tile,
            target_tile=target_tile,
            target_air_wing_id=getattr(target_air_wing, "id", None),
            target_air_salvo_id=getattr(target_air_salvo, "id", None),
            target_aircraft_type=target_aircraft_type,
            target_sorties=max(0, int(target_sorties)),
            launch_distance=launch_distance,
            remaining_distance=launch_distance,
            current_tile=launch_tile,
            speed=max(0.05, float(munition.get("cruise_speed", 1.0))),
            terminal_speed=max(0.05, float(munition.get("terminal_speed", munition.get("cruise_speed", 1.0)))),
            hit_chance=self.clamp01(hit_chance),
        )
        self.next_air_attack_salvo_id += 1
        return self.register_air_attack_salvo(salvo)

    def update_air_attack_salvo_target_tile(self, salvo):
        if not salvo:
            return None
        if salvo.target_air_salvo_id is not None:
            target_salvo = self.air_salvo_by_id(salvo.target_air_salvo_id)
            if target_salvo and target_salvo.count > 0:
                salvo.target_tile = target_salvo.current_tile or target_salvo.target_tile or salvo.target_tile
                return salvo.target_tile
            return None
        if salvo.target_air_wing_id is not None:
            target_wing = self.air_wing_by_id(salvo.target_air_wing_id)
            if target_wing and target_wing.ready_count > 0:
                mission_tile = self.tile_for_key(getattr(target_wing, "mission_target_tile_key", None))
                salvo.target_tile = mission_tile or salvo.target_tile or target_wing.base_tile
                return salvo.target_tile
            return None
        return salvo.target_tile

    def update_air_attack_salvo_position(self, salvo, elapsed_hours):
        if not salvo:
            return
        target_tile = self.update_air_attack_salvo_target_tile(salvo)
        if not target_tile:
            return
        if salvo.must_spend_reaction_tick:
            salvo.must_spend_reaction_tick = False
            salvo.current_tile = salvo.launch_tile
            return
        if salvo.launch_distance <= 0:
            salvo.remaining_distance = 0.0
            salvo.current_tile = target_tile
            return
        speed = salvo.terminal_speed if salvo.remaining_distance <= 1.0 else salvo.speed
        salvo.remaining_distance = max(0.0, salvo.remaining_distance - max(0.0, elapsed_hours) * speed)
        progress = 1.0 - salvo.remaining_distance / max(0.001, salvo.launch_distance)
        salvo.current_tile = self.tile_between(salvo.launch_tile, target_tile, progress) or target_tile

    def air_wing_outgoing_guided_salvos(self, wing):
        if not wing:
            return []
        result = []
        for salvo in getattr(self, "air_salvos", []) or []:
            if getattr(salvo, "source_air_wing_id", None) != wing.id or getattr(salvo, "count", 0) <= 0:
                continue
            munition_type = self.munition_data(salvo.munition_type).get("type")
            if AIR_EMERGENCY_DEFENSE_GUIDANCE_LOSS_BY_TYPE.get(munition_type, 0.0) > 0:
                result.append(salvo)
        return result

    def air_wing_emergency_defense_guidance_penalty(self, wing):
        disrupted = 0
        for outgoing in self.air_wing_outgoing_guided_salvos(wing):
            munition_type = self.munition_data(outgoing.munition_type).get("type")
            loss_ratio = self.clamp01(AIR_EMERGENCY_DEFENSE_GUIDANCE_LOSS_BY_TYPE.get(munition_type, 0.0))
            if loss_ratio <= 0:
                continue
            old_count = max(0, int(outgoing.count))
            new_count = max(0, int(old_count * (1.0 - loss_ratio) + 0.5))
            lost = max(0, old_count - new_count)
            if lost <= 0 and old_count > 0 and loss_ratio >= 0.45:
                lost = 1
                new_count = max(0, old_count - 1)
            outgoing.count = new_count
            disrupted += lost
        return disrupted

    def air_wing_should_emergency_defend(self, wing, salvo, target_type, engaged_count, hit_chance):
        if not wing or not salvo or engaged_count <= 0 or hit_chance <= 0:
            return False
        if getattr(wing, "aborted_hours", 0.0) > 0 or getattr(wing, "defensive_hours", 0.0) > 0:
            return False
        if getattr(wing, "mission_state", "") in {"defensive", "aborted", "returning"}:
            return False
        expected_hits = engaged_count * self.clamp01(hit_chance)
        risk_policy = getattr(wing, "risk_policy", "normal")
        threshold = AIR_EMERGENCY_DEFENSE_EXPECTED_HIT_THRESHOLD_BY_RISK.get(risk_policy, 0.34)
        outgoing_guided = self.air_wing_outgoing_guided_salvos(wing)
        if outgoing_guided and getattr(wing, "mission_state", "") == "attack_run":
            if risk_policy == "aggressive":
                threshold *= 1.35
            elif risk_policy == "all_out":
                threshold *= 1.75
            elif risk_policy == "normal":
                threshold *= 1.15
        if self.aircraft_type_is_helicopter(target_type):
            threshold *= 0.85
        return expected_hits >= threshold

    def apply_air_wing_emergency_defense_against_salvo(self, wing, salvo, target_type, engaged_count, hit_chance):
        if not self.air_wing_should_emergency_defend(wing, salvo, target_type, engaged_count, hit_chance):
            return hit_chance, False, 0
        defensive_mult = (
            AIR_EMERGENCY_DEFENSE_HELICOPTER_HIT_CHANCE_MULT
            if self.aircraft_type_is_helicopter(target_type)
            else AIR_EMERGENCY_DEFENSE_HIT_CHANCE_MULT
        )
        disrupted = self.air_wing_emergency_defense_guidance_penalty(wing)
        wing.defensive_hours = max(getattr(wing, "defensive_hours", 0.0), AIR_CARRIER_DEFENSIVE_COOLDOWN_HOURS)
        summary = "Экстренное уклонение"
        if disrupted:
            summary += f": сорвано наведение {disrupted}"
        self.set_air_wing_mission_state(wing, "defensive", salvo.current_tile or salvo.target_tile, summary)
        return self.clamp01(hit_chance * defensive_mult), True, disrupted

    def resolve_air_attack_salvo_impact(self, salvo):
        if not salvo or salvo.count <= 0:
            return False
        launcher = self.air_wing_by_id(salvo.launcher_air_wing_id)
        if salvo.target_air_salvo_id is not None:
            target_salvo = self.air_salvo_by_id(salvo.target_air_salvo_id)
            if not target_salvo or target_salvo.count <= 0 or not self.countries_hostile(salvo.owner, target_salvo.owner):
                return False
            engaged_count = min(salvo.count, target_salvo.count)
            hits = min(target_salvo.count, int(engaged_count * self.clamp01(salvo.hit_chance) + 0.5))
            target_salvo.count = max(0, target_salvo.count - hits)
            if launcher:
                if hits > 0:
                    launcher.last_air_combat_summary = f"УРВВ попали: {hits}/{salvo.original_count}"
                else:
                    launcher.last_air_combat_summary = f"УРВВ промах: 0/{salvo.original_count}"
                self.set_air_wing_mission_state(launcher, "egress", salvo.current_tile or salvo.target_tile, launcher.last_air_combat_summary)
            return hits > 0

        if salvo.target_air_wing_id is not None:
            target_wing = self.air_wing_by_id(salvo.target_air_wing_id)
            if not target_wing or target_wing.ready_count <= 0 or not self.countries_hostile(salvo.owner, target_wing.owner):
                return False
            target_type = salvo.target_aircraft_type or target_wing.aircraft_type
            target_sorties = salvo.target_sorties or self.air_wing_ready_count_for_type(target_wing, target_type)
            engaged_count = min(salvo.count, max(0, int(target_sorties)))
            terminal_hit_chance, emergency_defended, disrupted = self.apply_air_wing_emergency_defense_against_salvo(
                target_wing,
                salvo,
                target_type,
                engaged_count,
                salvo.hit_chance,
            )
            hits = min(engaged_count, int(engaged_count * self.clamp01(terminal_hit_chance) + 0.5))
            destroyed, damaged, aborted = self.apply_air_wing_air_defense_hits(target_wing, target_type, hits)
            if hits > 0:
                target_wing.aborted_hours = max(getattr(target_wing, "aborted_hours", 0.0), AIR_CARRIER_ABORTED_COOLDOWN_HOURS)
                target_wing.sortie_cooldown_hours = max(getattr(target_wing, "sortie_cooldown_hours", 0.0), AIR_CARRIER_ABORTED_COOLDOWN_HOURS)
                if destroyed or damaged:
                    summary = f"УРВВ: {destroyed} сбито, {damaged} повреждено"
                else:
                    summary = "УРВВ сорвали заход"
                self.set_air_wing_mission_state(target_wing, "aborted", salvo.current_tile or salvo.target_tile, summary)
            elif emergency_defended:
                summary = "Экстренное уклонение спасло крыло"
                if disrupted:
                    summary += f", сорвано наведение {disrupted}"
                self.set_air_wing_mission_state(target_wing, "defensive", salvo.current_tile or salvo.target_tile, summary)
            if launcher:
                if emergency_defended:
                    launcher.last_air_combat_summary = f"УРВВ: цель экстренно уклонилась, попаданий {hits}/{salvo.original_count}"
                else:
                    launcher.last_air_combat_summary = f"УРВВ попаданий {hits}/{salvo.original_count}"
                self.set_air_wing_mission_state(launcher, "egress", salvo.current_tile or salvo.target_tile, launcher.last_air_combat_summary)
            return hits > 0

        return False

    def update_air_attack_salvos(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        completed = []
        for salvo in list(getattr(self, "air_attack_salvos", []) or []):
            if salvo.count <= 0:
                completed.append(salvo)
                continue
            salvo.ticks_alive += 1
            target_tile = self.update_air_attack_salvo_target_tile(salvo)
            if not target_tile:
                completed.append(salvo)
                continue
            self.update_air_attack_salvo_position(salvo, elapsed_hours)
            if salvo.remaining_distance <= 0:
                self.resolve_air_attack_salvo_impact(salvo)
                completed.append(salvo)

        for salvo in completed:
            self.unregister_air_attack_salvo(salvo)

    def air_salvos_for_tile(self, tile, owner=None):
        if not tile:
            return []
        if self.air_salvo_tile_cache_revision != self.air_salvo_revision:
            self.rebuild_air_salvo_tile_cache()
        salvos = self.air_salvo_tile_lookup.get(self.indexed_tile_key(tile), [])
        if owner is None:
            return list(salvos)
        return [salvo for salvo in salvos if salvo.owner is owner]

    def air_salvo_by_id(self, salvo_id):
        return self.air_salvo_lookup.get(salvo_id)

    def air_salvo_source_wing(self, salvo):
        return self.air_wing_by_id(salvo.source_air_wing_id) if getattr(salvo, "source_air_wing_id", None) else None

    def air_salvo_source_mission(self, salvo):
        if getattr(salvo, "mission_type", None):
            return salvo.mission_type
        wing = self.air_salvo_source_wing(salvo)
        if wing and getattr(wing, "mission", None):
            return wing.mission
        if getattr(salvo, "target_object_type", None):
            return "strategic_strike"
        munition_type = self.munition_data(getattr(salvo, "munition_type", None)).get("type")
        if munition_type in {"cruise_missile", "ballistic_missile", "heavy_strategic_missile", "bunker_buster"}:
            return "strategic_strike"
        return "cas" if "divisions" in self.air_salvo_target_tags(salvo) else None

    def air_salvo_target_tags(self, salvo):
        munition = self.munition_data(salvo.munition_type)
        tags = set(munition.get("target_tags", []))
        if salvo.target_object_type:
            tags.add(salvo.target_object_type)
        return tags

    def air_mission_tile_is_hostile(self, owner, tile):
        return bool(tile and self.countries_hostile(owner, tile.owner))

    def air_salvo_has_hostile_division_target(self, salvo):
        if not salvo or not getattr(salvo, "owner", None):
            return False
        if getattr(salvo, "target_unit_id", None):
            target = self.division_by_id(salvo.target_unit_id)
            return bool(target and self.countries_hostile(target.owner, salvo.owner) and target.strength > 0)
        return bool(self.enemy_divisions_on_tile(getattr(salvo, "target_tile", None), salvo.owner))

    def air_salvo_target_is_still_valid(self, salvo):
        if not salvo or not getattr(salvo, "owner", None) or not getattr(salvo, "target_tile", None):
            return False
        mission_type = self.air_salvo_source_mission(salvo)
        target_tags = self.air_salvo_target_tags(salvo)
        if getattr(salvo, "target_unit_id", None) or mission_type == "cas":
            return self.air_salvo_has_hostile_division_target(salvo)
        if getattr(salvo, "target_object_type", None) or mission_type == "strategic_strike":
            return self.air_mission_tile_is_hostile(salvo.owner, salvo.target_tile)
        if target_tags.intersection({"buildings", "airbase", "bunker", "radar", "sam", "infrastructure", "factory", "depot", "city"}):
            return self.air_mission_tile_is_hostile(salvo.owner, salvo.target_tile)
        if "divisions" in target_tags or "armor" in target_tags:
            return self.air_salvo_has_hostile_division_target(salvo)
        return self.air_mission_tile_is_hostile(salvo.owner, salvo.target_tile)

    def building_keys_for_target_tag(self, tag):
        tag_map = {
            "airbase": ["airbase"],
            "field_helipad": ["field_helipad"],
            "hardened_shelter": ["airbase"],
            "bunker": ["airbase", "supply_depot", "warehouse"],
            "radar": ["airbase"],
            "sam": ["airbase", "supply_depot"],
            "infrastructure": ["supply_depot", "warehouse", "port", "fuel_storage", "city", "village"],
            "supply_infrastructure": ["supply_depot", "warehouse", "fuel_storage", "port"],
            "factory": ["industry", "refinery"],
            "industry": ["industry", "refinery", "mine", "oil_gas_rig"],
            "depot": ["supply_depot", "warehouse", "fuel_storage"],
            "bases": ["airbase", "supply_depot", "warehouse", "fuel_storage"],
            "airbases": ["airbase", "field_helipad"],
            "air_defense": ["airbase", "supply_depot"],
            "civilian_infrastructure": ["city", "village", "farms"],
            "city": ["city", "village"],
            "buildings": list(BUILDING_CONSTRUCTION_BASE.keys()),
        }
        return list(tag_map.get(tag, []))

    def air_wing_target_priority_building_keys(self, wing):
        if not wing:
            return []
        preferred = []
        for priority in getattr(wing, "target_priorities", []) or []:
            if priority == "enemy_units":
                continue
            if priority == "infrastructure":
                mapped = self.building_keys_for_target_tag("infrastructure")
            else:
                mapped = self.building_keys_for_target_tag(priority)
            for building_key in mapped:
                if building_key not in preferred:
                    preferred.append(building_key)
        return preferred

    def air_salvo_target_building_keys(self, salvo):
        preferred = []
        if salvo.target_object_type:
            for building_key in self.building_keys_for_target_tag(salvo.target_object_type):
                if building_key not in preferred:
                    preferred.append(building_key)
        wing = self.air_salvo_source_wing(salvo)
        if wing and self.air_salvo_source_mission(salvo) == "strategic_strike":
            for building_key in self.air_wing_target_priority_building_keys(wing):
                if building_key not in preferred:
                    preferred.append(building_key)
        for tag in self.air_salvo_target_tags(salvo):
            for building_key in self.building_keys_for_target_tag(tag):
                if building_key not in preferred:
                    preferred.append(building_key)
        return preferred

    def air_salvo_building_damage_amount(self, salvo, building_key, collateral_scale=1.0):
        munition = self.munition_data(salvo.munition_type)
        munition_type = munition.get("type", salvo.munition_type)
        accuracy = self.clamp01(float(munition.get("accuracy", 0.5)))
        warhead = max(0.05, float(munition.get("warhead", 1.0)))
        penetration = max(0.0, float(munition.get("penetration", 0.0)))
        count = max(1, int(getattr(salvo, "count", 1)))
        type_mult = AIR_SALVO_BUILDING_DAMAGE_MULT_BY_TYPE.get(munition_type, 0.65)
        hardness = max(0.25, AIR_SALVO_BUILDING_HARDNESS.get(building_key, 1.0))
        penetration_factor = 0.72 + min(1.5, penetration) * 0.34
        if munition_type == "bunker_buster" and building_key in {"airbase", "supply_depot", "warehouse"}:
            penetration_factor *= 1.35
        damage = (
            warhead
            * count
            * accuracy
            * AIR_SALVO_BUILDING_DAMAGE_PER_WARHEAD
            * type_mult
            * penetration_factor
            / hardness
            * max(0.0, float(collateral_scale))
        )
        type_cap = AIR_SALVO_BUILDING_DAMAGE_CAP_BY_TYPE.get(munition_type, AIR_SALVO_MAX_BUILDING_DAMAGE_PER_IMPACT)
        cap = min(AIR_SALVO_MAX_BUILDING_DAMAGE_PER_IMPACT, type_cap) * max(0.05, float(collateral_scale) ** 0.55)
        if munition_type == "heavy_strategic_missile":
            cap = type_cap * max(0.05, float(collateral_scale) ** 0.55)
        return max(0.0, min(cap, damage))

    def air_salvo_building_target_weight(self, salvo, building_key, coverage):
        health = self.building_health(salvo.target_tile, building_key)
        if health <= 0:
            return 0.0
        weight = max(0.02, coverage) * health
        weight *= AIR_SALVO_BUILDING_VALUE.get(building_key, 0.75)
        preferred = self.air_salvo_target_building_keys(salvo)
        if building_key in preferred:
            weight *= 2.4 / max(1, preferred.index(building_key) + 1) ** 0.35
        if salvo.target_object_type and building_key in self.building_keys_for_target_tag(salvo.target_object_type):
            weight *= 2.0
        return weight

    def resolve_air_salvo_building_impact(self, salvo, collateral_scale=1.0):
        tile = salvo.target_tile
        if not tile:
            return False
        coverage = getattr(tile, "building_coverage", {}) or {}
        candidate_keys = [
            key for key in self.air_salvo_target_building_keys(salvo)
            if coverage.get(key, 0.0) > 0 and self.building_health(tile, key) > 0
        ]
        if not candidate_keys:
            candidate_keys = [
                key for key, value in coverage.items()
                if value > 0 and key in BUILDING_CONSTRUCTION_BASE and self.building_health(tile, key) > 0
            ]
        if not candidate_keys:
            return False

        weights = [
            self.air_salvo_building_target_weight(salvo, key, coverage.get(key, 0.0))
            for key in candidate_keys
        ]
        if not any(weight > 0 for weight in weights):
            return False
        target_key = random.choices(candidate_keys, weights=weights, k=1)[0]
        primary_damage = self.air_salvo_building_damage_amount(salvo, target_key, collateral_scale=collateral_scale)
        changed = self.damage_building(tile, target_key, primary_damage, queue_repair=True)
        damage_summary = {target_key: primary_damage} if primary_damage > 0 else {}

        munition_type = self.munition_data(salvo.munition_type).get("type")
        spread_roll = 0.20 + min(0.45, max(0, salvo.count - 1) * 0.05)
        if munition_type in {"cruise_missile", "ballistic_missile", "heavy_strategic_missile", "bunker_buster"}:
            spread_roll += 0.20
        secondary_budget = 2 if munition_type in {"cruise_missile", "ballistic_missile", "heavy_strategic_missile"} else 1
        remaining_keys = [key for key in candidate_keys if key != target_key]
        for index in range(min(secondary_budget, len(remaining_keys))):
            if random.random() >= spread_roll:
                continue
            secondary_weights = [
                self.air_salvo_building_target_weight(salvo, key, coverage.get(key, 0.0))
                for key in remaining_keys
            ]
            if not any(weight > 0 for weight in secondary_weights):
                break
            secondary_key = random.choices(remaining_keys, weights=secondary_weights, k=1)[0]
            secondary_damage = self.air_salvo_building_damage_amount(
                salvo,
                secondary_key,
                collateral_scale=collateral_scale * (0.42 / (index + 1)),
            )
            changed = self.damage_building(tile, secondary_key, secondary_damage, queue_repair=True) or changed
            if secondary_damage > 0:
                damage_summary[secondary_key] = damage_summary.get(secondary_key, 0.0) + secondary_damage
            remaining_keys.remove(secondary_key)

        if damage_summary:
            salvo.last_building_damage_summary = {
                "target_tile": self.tile_key(tile),
                "munition_type": salvo.munition_type,
                "target_object_type": salvo.target_object_type,
                "collateral_scale": collateral_scale,
                "building_damage": damage_summary,
            }
        return changed

    def air_salvo_equipment_target_profile(self, munition_id):
        munition = self.munition_data(munition_id)
        munition_type = munition.get("type", munition_id)
        if munition_id == "unguided_rockets" or munition_type == "unguided_rocket":
            return {
                "vehicles": 2.40,
                "old_ifv": 2.05,
                "old_at_missiles": 1.80,
                "old_light_artillery": 0.80,
                "old_light_aa_artillery": 0.75,
                "spare_parts": 0.45,
            }
        if munition_type == "guided_missile":
            return {
                "vehicles": 2.40,
                "old_ifv": 2.15,
                "old_at_missiles": 1.95,
                "old_light_aa_artillery": 1.05,
                "old_light_artillery": 0.80,
                "spare_parts": 0.70,
            }
        if munition_type in {"guided_bomb", "glide_bomb"}:
            return {
                "field_supplies": 2.20,
                "spare_parts": 1.80,
                "old_light_artillery": 1.60,
                "old_light_aa_artillery": 1.25,
                "weapons": 0.75,
                "infantry_equipment": 0.65,
                "vehicles": 0.55,
                "old_ifv": 0.45,
            }
        if munition_type in {"cruise_missile", "ballistic_missile", "heavy_strategic_missile", "bunker_buster"}:
            return {
                "field_supplies": 1.75,
                "spare_parts": 1.55,
                "old_light_artillery": 1.25,
                "old_light_aa_artillery": 1.15,
                "vehicles": 0.85,
                "old_ifv": 0.70,
                "old_at_missiles": 0.65,
            }
        return {}

    def air_salvo_equipment_focus_factor(self, salvo, target, munition):
        accuracy = self.clamp01(float(munition.get("accuracy", 0.5)))
        guidance = self.clamp01(float(munition.get("guidance_quality", 0.0)))
        aircraft_recon = 0.0
        wing = self.air_wing_by_id(salvo.source_air_wing_id) if getattr(salvo, "source_air_wing_id", None) else None
        if wing:
            aircraft_type = (
                self.air_wing_primary_type_for_mission(wing, getattr(wing, "mission", "cas"))
                or getattr(wing, "aircraft_type", None)
            )
            aircraft_recon = float(self.aircraft_type_data(aircraft_type).get("recon", 0.0))
        friendly_recon = 0.0
        friendly_divisions = [
            division for division in getattr(self, "divisions", []) or []
            if getattr(division, "owner", None) is getattr(salvo, "owner", None)
            and getattr(division, "tile", None) is getattr(target, "tile", None)
        ]
        if friendly_divisions:
            friendly_recon = sum(float(getattr(division, "recon", 0.0)) for division in friendly_divisions) / len(friendly_divisions)
        defender_camouflage = float(getattr(target, "camouflage", 0.0))
        combat_intel_delta = aircraft_recon * 2.0 + friendly_recon * 0.25 - defender_camouflage
        focus = 0.62 + accuracy * 0.25 + guidance * 0.45 + combat_intel_delta * 0.18
        return max(AIR_SALVO_EQUIPMENT_FOCUS_MIN, min(AIR_SALVO_EQUIPMENT_FOCUS_MAX, focus))

    def apply_air_salvo_targeted_equipment_losses(self, division, base_loss_ratio, target_profile, focus_factor):
        if not division or base_loss_ratio <= 0 or not target_profile:
            return {}
        losses = {}
        for key, weight in target_profile.items():
            if key not in DIVISION_EQUIPMENT_LOSS_KEYS:
                continue
            capacity = (division.supply_capacity or {}).get(key, 0.0)
            current = (division.supply_stock or {}).get(key, 0.0)
            if capacity <= 0 or current <= 0:
                continue
            loss_ratio = base_loss_ratio * AIR_SALVO_TARGETED_EQUIPMENT_LOSS_MULT * focus_factor * max(0.0, float(weight))
            loss_ratio = min(AIR_SALVO_TARGETED_EQUIPMENT_MAX_LOSS_RATIO, loss_ratio)
            loss = min(current, capacity * loss_ratio)
            if loss <= 0:
                continue
            division.supply_stock[key] = max(0.0, current - loss)
            losses[key] = loss
        return losses

    def air_ground_suppression_owner_key(self, owner):
        if owner is None:
            return None
        return str(getattr(owner, "id", id(owner)))

    def mark_division_air_ground_suppressed(self, owner, division, hours=None):
        if not owner or not division:
            return False
        owner_key = self.air_ground_suppression_owner_key(owner)
        if owner_key is None:
            return False
        if getattr(division, "air_ground_suppression", None) is None:
            division.air_ground_suppression = {}
        hours = AIR_CAS_BREAKTHROUGH_BONUS_HOURS if hours is None else max(0.0, float(hours))
        division.air_ground_suppression[owner_key] = max(
            hours,
            float(division.air_ground_suppression.get(owner_key, 0.0) or 0.0),
        )
        return True

    def division_air_ground_suppressed_by(self, division, owner):
        owner_key = self.air_ground_suppression_owner_key(owner)
        if not division or owner_key is None:
            return False
        return float((getattr(division, "air_ground_suppression", {}) or {}).get(owner_key, 0.0) or 0.0) > 0

    def tick_division_air_ground_suppression(self, division, elapsed_hours):
        markers = getattr(division, "air_ground_suppression", None)
        if not markers or elapsed_hours <= 0:
            return
        for owner_key in list(markers.keys()):
            remaining = max(0.0, float(markers.get(owner_key, 0.0) or 0.0) - elapsed_hours)
            if remaining > 0:
                markers[owner_key] = remaining
            else:
                markers.pop(owner_key, None)

    def player_has_air_superiority_support(self, player, tile):
        if not player or not tile:
            return False
        tile_key = self.tile_key(tile)
        for wing in getattr(self, "air_wings", []) or []:
            if getattr(wing, "owner", None) is not player or getattr(wing, "ready_count", 0) <= 0:
                continue
            if "air_superiority" not in self.air_wing_enabled_missions(wing):
                continue
            aircraft_type = self.air_wing_primary_type_for_mission(wing, "air_superiority") or getattr(wing, "aircraft_type", None)
            if not self.aircraft_type_can_reach_tile(getattr(wing, "base_tile", None), aircraft_type, tile):
                continue
            area_keys = set(self.normalize_air_wing_operation_area_keys(wing))
            if not area_keys or tile_key in area_keys:
                return True
        return False

    def battle_enemy_air_suppressed_for_owner(self, battle, owner):
        if not battle or not owner:
            return False
        for defender in self.battle_side_present(battle, "defender"):
            if self.countries_hostile(defender.owner, owner) and self.division_air_ground_suppressed_by(defender, owner):
                return True
        return False

    def division_attack_breakthrough_air_bonus(self, division, battle):
        if not division or not battle or division.battle_side != "attacker":
            return 0.0
        bonus = 0.0
        if self.battle_enemy_air_suppressed_for_owner(battle, division.owner):
            bonus += AIR_CAS_BREAKTHROUGH_BONUS
        if self.player_has_air_superiority_support(division.owner, battle.tile):
            bonus += AIR_SUPERIORITY_BREAKTHROUGH_BONUS
        return bonus

    def resolve_air_salvo_division_impact(self, salvo):
        munition = self.munition_data(salvo.munition_type)
        target = self.division_by_id(salvo.target_unit_id) if salvo.target_unit_id else None
        if target and (not self.countries_hostile(target.owner, salvo.owner) or target.strength <= 0):
            return False
        if not target:
            candidates = self.enemy_divisions_on_tile(salvo.target_tile, salvo.owner)
            if not candidates:
                return False
            target = random.choice(candidates)
        accuracy = self.clamp01(float(munition.get("accuracy", 0.5)))
        warhead = max(0.05, float(munition.get("warhead", 1.0)))
        damage_scale = max(1, salvo.count) * warhead * accuracy
        org_damage = damage_scale * AIR_SALVO_DIVISION_ORG_DAMAGE_PER_WARHEAD
        strength_damage = damage_scale * AIR_SALVO_DIVISION_STRENGTH_DAMAGE_PER_WARHEAD
        target.organization = max(0.0, target.organization - org_damage)
        actual_strength_damage = self.apply_division_strength_losses(
            target,
            strength_damage,
            equipment_loss_multiplier=AIR_SALVO_GENERAL_EQUIPMENT_LOSS_MULT,
        )
        base_loss_ratio = actual_strength_damage / max(1.0, getattr(target, "max_strength", 1.0))
        target_profile = self.air_salvo_equipment_target_profile(salvo.munition_type)
        focus_factor = self.air_salvo_equipment_focus_factor(salvo, target, munition)
        targeted_losses = self.apply_air_salvo_targeted_equipment_losses(
            target,
            base_loss_ratio,
            target_profile,
            focus_factor,
        )
        salvo.last_division_damage_summary = {
            "target_division_id": getattr(target, "id", None),
            "munition_type": salvo.munition_type,
            "org_damage": org_damage,
            "strength_damage": actual_strength_damage,
            "equipment_focus_factor": focus_factor,
            "targeted_equipment_losses": targeted_losses,
        }
        if org_damage > 0 or actual_strength_damage > 0:
            self.mark_division_air_ground_suppressed(salvo.owner, target)
            if not salvo.target_object_type:
                self.resolve_air_salvo_building_impact(
                    salvo,
                    collateral_scale=AIR_SALVO_CAS_COLLATERAL_BUILDING_DAMAGE_MULT,
                )
        if target.strength <= 0:
            self.destroy_division(target)
        return True

    def resolve_air_salvo_impact(self, salvo):
        if not salvo or salvo.count <= 0:
            return False
        if not self.air_salvo_target_is_still_valid(salvo):
            return False
        target_tags = self.air_salvo_target_tags(salvo)
        mission_type = self.air_salvo_source_mission(salvo)
        changed = False
        if (
            not salvo.target_object_type
            and (salvo.target_unit_id or mission_type == "cas" or "divisions" in target_tags)
            and self.enemy_divisions_on_tile(salvo.target_tile, salvo.owner)
        ):
            changed = self.resolve_air_salvo_division_impact(salvo)
            if changed:
                self.add_air_impact_decal(salvo.target_tile, source_id=getattr(salvo, "source_air_wing_id", None) or salvo.id, strength=max(1.0, salvo.count * 0.35))
            return changed
        building_first = bool(
            salvo.target_object_type
            or target_tags.intersection({"buildings", "airbase", "bunker", "radar", "sam", "infrastructure", "factory", "depot", "city"})
            or mission_type == "strategic_strike"
        )
        if building_first:
            changed = self.resolve_air_salvo_building_impact(salvo)
        if not changed:
            changed = self.resolve_air_salvo_division_impact(salvo)
        if changed:
            self.add_air_impact_decal(salvo.target_tile, source_id=getattr(salvo, "source_air_wing_id", None) or salvo.id, strength=max(1.0, salvo.count * 0.35))
        return changed

    def air_defense_radar_support_bonus(self, owner, tile):
        if not owner or not tile:
            return 0.0
        supporting_radars = [
            unit for unit in getattr(owner, "air_defense_units", []) or []
            if unit.unit_class == "radar_unit"
            and unit.radar_active
            and unit.readiness > 0
            and unit.health > 0
            and unit.tile
            and self.hex_distance(unit.tile, tile) <= unit.radar_range_cells
        ]
        return min(0.18, 0.06 * len(supporting_radars))

    def air_defense_salvo_intercept_chance(self, unit, salvo):
        if not unit or not unit.tile or not salvo or unit.ammo <= 0 or unit.fire_range_cells <= 0:
            return 0.0
        current_tile = salvo.current_tile or salvo.target_tile
        if not current_tile:
            return 0.0
        range_factor = self.air_defense_range_factor(unit, current_tile)
        if range_factor <= 0:
            return 0.0

        profile = AIR_DEFENSE_INTERCEPTOR_PROFILES.get(unit.missile_profile or "", {})
        rcs_sensitivity = float(profile.get("target_rcs_sensitivity", 0.45))
        signature_factor = self.clamp01(
            0.42
            + salvo.average_rcs * rcs_sensitivity
            + salvo.average_infrared_signature * 0.20
            + self.air_defense_radar_support_bonus(unit.owner, current_tile)
        )
        munition = self.munition_data(salvo.munition_type)
        speed_factor = max(0.42, 1.0 - max(0.0, salvo.terminal_speed - 1.0) * 0.14)
        maneuver_factor = max(0.55, 1.0 - salvo.average_maneuverability * 0.28)
        difficulty_factor = max(0.35, 1.0 - float(munition.get("interception_difficulty", 0.5)) * 0.38)
        tracking_factor = self.clamp01(unit.tracking_quality * 0.58 + unit.detection_power * 0.42)
        readiness_factor = self.clamp01(unit.readiness) * self.clamp01(unit.health)
        chance = (
            salvo.average_interceptability
            * (0.32 + tracking_factor * 0.68)
            * range_factor
            * signature_factor
            * speed_factor
            * maneuver_factor
            * difficulty_factor
            * readiness_factor
        )
        return self.clamp01(chance)

    def air_defense_engaged_salvo_count(self, unit, salvo):
        interceptors_per_target = max(1, getattr(unit, "interceptors_per_target", 1))
        available_interceptors = max(0, unit.ammo // interceptors_per_target)
        return max(
            0,
            min(
                salvo.count,
                available_interceptors,
                max(0, getattr(unit, "tracking_channels", 0)),
                max(0, getattr(unit, "fire_channels", 0)),
                max(0, getattr(unit, "max_targets_per_tick", 0)),
            ),
        )

    def resolve_air_salvo_air_defense(self, salvo):
        if not salvo or salvo.count <= 0:
            return 0
        current_tile = salvo.current_tile or salvo.target_tile
        if not current_tile:
            return 0
        intercepted_total = 0
        defenders = [
            unit for unit in getattr(self, "air_defense_units", []) or []
            if self.countries_hostile(unit.owner, salvo.owner)
            and unit.tile
            and unit.fire_range_cells > 0
            and unit.readiness > 0
            and unit.health > 0
            and self.hex_distance(unit.tile, current_tile) <= unit.fire_range_cells
            and self.hex_distance(unit.tile, current_tile) >= max(0, unit.min_range_cells)
        ] + self.division_tactical_air_defense_threats_for_tile(salvo.owner, current_tile)
        defenders.sort(
            key=lambda unit: (
                -unit.fire_range_cells,
                -unit.tracking_quality,
                self.hex_distance(unit.tile, current_tile),
            )
        )
        for unit in defenders:
            if salvo.count <= 0:
                break
            engaged_count = self.air_defense_engaged_salvo_count(unit, salvo)
            if engaged_count <= 0:
                continue
            estimate = self.estimate_intercept_or_hit_chance(unit, None, salvo, {"target_tile": current_tile})
            if not estimate.should_fire:
                continue
            chance = self.clamp01(estimate.intercept_chance)
            intercepted = min(salvo.count, int(engaged_count * chance + 0.5))
            self.spend_air_defense_unit_ammo(unit, engaged_count * max(1, unit.interceptors_per_target))
            salvo.count = max(0, salvo.count - intercepted)
            intercepted_total += intercepted
            salvo.detected_by.add(unit.owner.id if unit.owner else unit.id)
        return intercepted_total

    def air_wing_salvo_intercept_mission_for_tile(self, wing, tile):
        if (
            not wing
            or not tile
            or getattr(wing, "aborted_hours", 0.0) > 0
            or self.air_wing_has_global_sortie_cooldown(wing)
        ):
            return None
        enabled = self.air_wing_enabled_missions(wing)
        for mission_type in ("intercept", "air_superiority", "patrol"):
            if mission_type not in enabled:
                continue
            aircraft_type = self.air_wing_primary_type_for_mission(wing, mission_type)
            if not aircraft_type or self.air_wing_ready_count_for_type(wing, aircraft_type) <= 0:
                continue
            if not self.aircraft_type_can_reach_tile(wing.base_tile, aircraft_type, tile):
                continue
            area_keys = set(self.normalize_air_wing_operation_area_keys(wing))
            if area_keys and self.tile_key(tile) not in area_keys:
                continue
            return mission_type, aircraft_type
        return None

    def resolve_air_salvo_air_wing_interception(self, salvo):
        if not salvo or salvo.count <= 0:
            return 0
        current_tile = salvo.current_tile or salvo.target_tile
        if not current_tile:
            return 0
        candidates = []
        for wing in getattr(self, "air_wings", []) or []:
            if not self.countries_hostile(wing.owner, salvo.owner) or not wing.base_tile or wing.ready_count <= 0:
                continue
            mission = self.air_wing_salvo_intercept_mission_for_tile(wing, current_tile)
            if not mission:
                continue
            mission_type, aircraft_type = mission
            ready_count = self.air_wing_ready_count_for_type(wing, aircraft_type)
            sorties = min(salvo.count, max(1, int(math.ceil(ready_count * self.clamp01(wing.sortie_intensity) * 0.18))))
            if self.air_wing_engaged_salvo_count(wing, aircraft_type, sorties, salvo) <= 0:
                continue
            estimate = self.estimate_intercept_or_hit_chance(
                wing,
                None,
                salvo,
                {
                    "target_tile": current_tile,
                    "mission_type": mission_type,
                    "aircraft_type": aircraft_type,
                    "sorties": sorties,
                },
            )
            if estimate.should_fire:
                candidates.append((wing, mission_type, aircraft_type, sorties, estimate))
        candidates.sort(
            key=lambda item: (
                -item[4].target_priority,
                -item[4].intercept_chance,
                self.hex_distance(item[0].base_tile, current_tile),
            )
        )

        launched_total = 0
        for wing, mission_type, aircraft_type, sorties, estimate in candidates:
            if salvo.count <= 0:
                break
            sorties = min(sorties, salvo.count, self.air_wing_ready_count_for_type(wing, aircraft_type))
            if sorties <= 0:
                continue
            engaged_count = self.air_wing_engaged_salvo_count(wing, aircraft_type, sorties, salvo)
            if engaged_count <= 0:
                continue
            interceptors_per_target = self.air_wing_interceptors_per_target(aircraft_type)
            ammo_spent = engaged_count * interceptors_per_target
            self.set_air_wing_mission_state(wing, "attack_run", current_tile)
            wing.interceptor_ammo = max(0, getattr(wing, "interceptor_ammo", 0) - ammo_spent)
            attack_salvo = self.create_air_attack_salvo(
                wing.owner,
                wing,
                aircraft_type,
                getattr(wing, "interceptor_munition", None) or self.air_wing_default_interceptor_munition(wing),
                engaged_count,
                current_tile,
                current_tile,
                estimate.intercept_chance,
                target_air_salvo=salvo,
                launch_distance=1.0,
            )
            if attack_salvo:
                launched_total += attack_salvo.count
            self.set_air_wing_mission_cooldown(wing, mission_type, AIR_MISSION_MIN_COOLDOWN_HOURS)
            wing.last_air_combat_summary = f"УРВВ {ammo_spent}, залп в пути"
            self.set_air_wing_mission_state(wing, "egress", current_tile, wing.last_air_combat_summary)
            salvo.detected_by.add(wing.owner.id if wing.owner else wing.id)
        return launched_total

    def update_air_salvo_position(self, salvo, elapsed_hours):
        if not salvo or not salvo.target_tile:
            return
        old_tile = salvo.current_tile
        if salvo.launch_distance <= 0:
            salvo.remaining_distance = 0.0
            salvo.current_tile = salvo.target_tile
            if old_tile is not salvo.current_tile:
                self.invalidate_air_salvo_tile_cache()
            return
        speed = salvo.terminal_speed if salvo.remaining_distance <= 1.0 else salvo.speed
        salvo.remaining_distance = max(0.0, salvo.remaining_distance - max(0.0, elapsed_hours) * speed)
        progress = 1.0 - salvo.remaining_distance / max(0.001, salvo.launch_distance)
        salvo.current_tile = self.tile_between(salvo.launch_tile, salvo.target_tile, progress) or salvo.target_tile
        if old_tile is not salvo.current_tile:
            self.invalidate_air_salvo_tile_cache()

    def air_salvo_has_inbound_air_attack(self, salvo):
        if not salvo:
            return False
        return any(
            attack_salvo.count > 0
            and attack_salvo.target_air_salvo_id == salvo.id
            for attack_salvo in getattr(self, "air_attack_salvos", []) or []
        )

    def air_salvo_in_defended_zone(self, salvo):
        current_tile = salvo.current_tile or salvo.target_tile
        if not current_tile:
            return False
        return any(
            self.countries_hostile(unit.owner, salvo.owner)
            and unit.tile
            and unit.fire_range_cells > 0
            and unit.readiness > 0
            and unit.health > 0
            and self.hex_distance(unit.tile, current_tile) <= unit.fire_range_cells
            and self.hex_distance(unit.tile, current_tile) >= max(0, unit.min_range_cells)
            for unit in getattr(self, "air_defense_units", []) or []
        )

    def update_air_salvos(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        completed = []
        for salvo in list(getattr(self, "air_salvos", []) or []):
            if salvo.count <= 0 or not salvo.target_tile:
                completed.append(salvo)
                continue
            if not self.air_salvo_target_is_still_valid(salvo):
                completed.append(salvo)
                continue
            salvo.ticks_alive += 1
            self.update_air_salvo_position(salvo, elapsed_hours)
            air_interceptors_launched = 0
            in_defended_zone = self.air_salvo_in_defended_zone(salvo)
            if (
                salvo.remaining_distance <= 0
                and getattr(salvo, "air_wing_terminal_reaction_spent", False)
                and not self.air_salvo_has_inbound_air_attack(salvo)
            ):
                self.resolve_air_salvo_impact(salvo)
                completed.append(salvo)
                continue
            if in_defended_zone and not salvo.entered_defended_zone:
                salvo.entered_defended_zone = True
                salvo.must_spend_intercept_tick = True
            if in_defended_zone or salvo.must_spend_intercept_tick:
                self.resolve_air_salvo_air_defense(salvo)
                if salvo.count > 0:
                    air_interceptors_launched = self.resolve_air_salvo_air_wing_interception(salvo)
                salvo.must_spend_intercept_tick = False
            elif salvo.count > 0:
                air_interceptors_launched = self.resolve_air_salvo_air_wing_interception(salvo)
            if air_interceptors_launched > 0 and salvo.remaining_distance <= 0:
                salvo.air_wing_terminal_reaction_spent = True
            if salvo.count <= 0:
                completed.append(salvo)
                continue
            if self.air_salvo_has_inbound_air_attack(salvo):
                continue
            if air_interceptors_launched > 0 and salvo.remaining_distance <= 0:
                continue
            if salvo.remaining_distance <= 0:
                self.resolve_air_salvo_impact(salvo)
                completed.append(salvo)

        for salvo in completed:
            self.unregister_air_salvo(salvo)

    def update_air_defense_units(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        changed = False
        for unit in getattr(self, "air_defense_units", []) or []:
            if not unit.tile:
                continue
            if not unit.path:
                unit.target_tile = None
                unit.route_tiles = []
                unit.movement_progress = 0.0
                unit.visual_movement_progress = 0.0
                unit.x = unit.tile.center_x
                unit.y = unit.tile.center_y
                continue
            next_tile = unit.path[0]
            if not self.air_defense_can_enter_tile(unit, next_tile):
                unit.path = []
                unit.route_tiles = []
                unit.target_tile = None
                unit.movement_progress = 0.0
                unit.visual_movement_progress = 0.0
                changed = True
                continue
            movement_cost = max(1.0, self.effective_tile_movement_cost(next_tile))
            speed = 0.55 * max(0.35, getattr(next_tile, "supply_score", 0.75))
            unit.movement_progress += elapsed_hours * speed / max(1.0, movement_cost * 18.0)
            while unit.path and unit.movement_progress >= 1.0:
                unit.movement_progress -= 1.0
                old_tile = unit.tile
                unit.tile = unit.path.pop(0)
                self.move_air_defense_unit_index(unit, old_tile, unit.tile)
                unit.x = unit.tile.center_x
                unit.y = unit.tile.center_y
                changed = True
                if unit.path:
                    next_tile = unit.path[0]
                    if not self.air_defense_can_enter_tile(unit, next_tile):
                        unit.path = []
                        unit.target_tile = None
                        break
            unit.visual_movement_progress += (self.clamp01(unit.movement_progress) - unit.visual_movement_progress) * 0.35
            if not unit.path:
                unit.target_tile = None
                unit.route_tiles = []
                unit.movement_progress = 0.0
                unit.visual_movement_progress = 0.0
                unit.x = unit.tile.center_x
                unit.y = unit.tile.center_y
        if changed:
            self.tile_visual_revision += 1

    def air_wing_munition_count_per_sortie(self, wing, munition_id):
        munition_type = self.munition_data(munition_id).get("type")
        if munition_type == "unguided_rocket":
            return 8
        if munition_type in {"guided_missile", "guided_bomb", "glide_bomb"}:
            return 2
        if munition_type in {"cruise_missile", "ballistic_missile", "bunker_buster"}:
            return 1
        if munition_type == "heavy_strategic_missile":
            return 1
        return 1

    def known_enemy_air_defense_radius_near(self, owner, target_tile):
        if not owner or not target_tile:
            return 0
        radius = 0
        for unit in getattr(self, "air_defense_units", []) or []:
            if not self.countries_hostile(unit.owner, owner) or not unit.tile or unit.fire_range_cells <= 0:
                continue
            if self.hex_distance(unit.tile, target_tile) <= unit.fire_range_cells + 1:
                radius = max(radius, unit.fire_range_cells)
        return radius

    def resolve_close_air_attack(self, wing, target_tile, munition_id, munition_count, aircraft_type=None, mission_type="cas"):
        if not wing or not target_tile or munition_count <= 0:
            return False
        if not self.air_wing_can_attack_tile(wing, target_tile, mission_type):
            return False
        aircraft_type = aircraft_type or self.air_wing_primary_type_for_mission(wing, mission_type) or wing.aircraft_type
        munitions_per_sortie = max(1, self.air_wing_munition_count_per_sortie(wing, munition_id))
        sorties = min(
            self.air_wing_ready_count_for_type(wing, aircraft_type),
            int(math.ceil(munition_count / munitions_per_sortie)),
        )
        if sorties <= 0:
            return False
        self.set_air_wing_mission_state(wing, "attack_run", target_tile)
        threat_result = self.resolve_air_defense_against_air_wing(
            wing,
            target_tile,
            aircraft_type,
            sorties,
            mission_type,
            phase="attack_run",
            target_tile=target_tile,
        )
        if threat_result.get("aborted"):
            return False
        suppressed_sorties = (
            threat_result.get("destroyed", 0)
            + threat_result.get("damaged", 0)
            + threat_result.get("aborted_aircraft", 0)
        )
        fighter_result = self.resolve_air_wing_interceptors_against_air_wing(
            wing,
            target_tile,
            aircraft_type,
            max(0, sorties - suppressed_sorties),
            mission_type,
        )
        if fighter_result.get("aborted"):
            return False
        suppressed_sorties += (
            fighter_result.get("destroyed", 0)
            + fighter_result.get("damaged", 0)
            + fighter_result.get("aborted_aircraft", 0)
        )
        delivered_sorties = max(0, sorties - suppressed_sorties)
        delivered_count = min(munition_count, delivered_sorties * munitions_per_sortie)
        if delivered_count <= 0:
            return False
        pseudo_salvo = self.create_air_salvo(
            wing.owner,
            munition_id,
            delivered_count,
            target_tile,
            launch_tile=target_tile,
            source_air_wing=wing,
            mission_type=mission_type,
            target_object_type=self.air_wing_strike_target_object_type(wing, target_tile) if mission_type == "strategic_strike" else None,
            launch_distance=0.0,
        )
        if not pseudo_salvo:
            return False
        changed = self.resolve_air_salvo_impact(pseudo_salvo)
        self.unregister_air_salvo(pseudo_salvo)
        self.set_air_wing_mission_state(wing, "egress", target_tile, wing.last_air_combat_summary)
        return changed

    def air_wing_strike_tile_score(self, wing, tile):
        if not wing or not tile:
            return 0.0, None
        coverage = getattr(tile, "building_coverage", {}) or {}
        if not coverage:
            return 0.0, None
        preferred = self.air_wing_target_priority_building_keys(wing)
        if not preferred:
            preferred = [
                "airbase",
                "supply_depot",
                "warehouse",
                "fuel_storage",
                "industry",
                "refinery",
                "port",
                "city",
                "village",
            ]
        best_score = 0.0
        best_key = None
        for building_key, built_coverage in coverage.items():
            if built_coverage <= 0 or building_key not in BUILDING_CONSTRUCTION_BASE:
                continue
            health = self.building_health(tile, building_key)
            if health <= 0:
                continue
            priority_factor = 1.0
            if building_key in preferred:
                priority_factor = 2.8 / max(1, preferred.index(building_key) + 1) ** 0.35
            elif getattr(wing, "target_priorities", None):
                continue
            score = (
                max(0.02, built_coverage)
                * health
                * AIR_SALVO_BUILDING_VALUE.get(building_key, 0.75)
                * priority_factor
            )
            if score > best_score:
                best_score = score
                best_key = building_key
        if best_score <= 0:
            return 0.0, None
        distance = self.hex_distance(wing.base_tile, tile)
        return best_score / (1.0 + distance * 0.12), best_key

    def air_wing_strike_target_object_type(self, wing, tile):
        _score, building_key = self.air_wing_strike_tile_score(wing, tile)
        object_map = {
            "industry": "factory",
            "refinery": "factory",
            "mine": "factory",
            "oil_gas_rig": "factory",
            "supply_depot": "depot",
            "warehouse": "depot",
            "fuel_storage": "depot",
            "port": "infrastructure",
            "city": "city",
            "village": "city",
            "farms": "civilian_infrastructure",
            "airbase": "airbase",
            "field_helipad": "airbase",
        }
        return object_map.get(building_key)

    def select_air_wing_strike_target(self, wing):
        if not wing:
            return None
        reachable_area = self.air_wing_reachable_operation_tiles(wing, "strategic_strike")
        reachable_area = [
            tile for tile in reachable_area
            if self.air_wing_can_attack_tile(wing, tile, "strategic_strike")
        ]
        if reachable_area:
            scored = [
                (
                    self.air_wing_strike_tile_score(wing, tile)[0] * self.air_wing_target_repeat_factor(wing, "strategic_strike", tile),
                    self.hex_distance(wing.base_tile, tile),
                    self.air_wing_strike_tile_score(wing, tile)[0],
                    tile,
                )
                for tile in reachable_area
            ]
            scored = [item for item in scored if item[0] > 0]
            if scored:
                scored.sort(key=lambda item: (-item[0], item[1], -item[2]))
                return scored[0][3]
        fallback = wing.target_tile or wing.target_area
        return fallback if self.air_wing_can_attack_tile(wing, fallback, "strategic_strike") else None

    def air_wing_cas_battle_score(self, wing, battle):
        if not wing or not battle or not battle.tile:
            return 0.0
        enemy_count = 0
        active_enemy_count = 0
        for side in ("attacker", "defender"):
            active_ids = set(getattr(battle, f"active_{side}s", []) or [])
            for division in self.battle_side_present(battle, side):
                if not self.countries_hostile(division.owner, wing.owner) or division.strength <= 0:
                    continue
                enemy_count += 1
                if division.id in active_ids:
                    active_enemy_count += 1
        if enemy_count <= 0:
            return 0.0
        distance = self.hex_distance(wing.base_tile, battle.tile)
        repeat_factor = self.air_wing_target_repeat_factor(wing, "cas", battle.tile)
        return (1.0 + enemy_count * 0.55 + active_enemy_count * 0.35) * repeat_factor / (1.0 + distance * 0.10)

    def select_air_wing_cas_target(self, wing):
        if not wing or not wing.base_tile:
            return None
        area_keys = set(self.normalize_air_wing_operation_area_keys(wing))
        owned_battles = [
            battle for battle in self.battles.values()
            if battle.attacker is wing.owner or battle.defender is wing.owner
        ]
        owned_battles = [
            battle for battle in owned_battles
            if self.battle_has_enemy_for_owner(battle, wing.owner)
        ]
        if area_keys:
            owned_battles = [
                battle for battle in owned_battles
                if battle.tile and self.tile_key(battle.tile) in area_keys
            ]
        if not owned_battles:
            return None
        scored = [
            (self.air_wing_cas_battle_score(wing, battle), self.hex_distance(wing.base_tile, battle.tile), battle)
            for battle in owned_battles
        ]
        scored = [item for item in scored if item[0] > 0]
        if not scored:
            return None
        scored.sort(key=lambda item: (-item[0], item[1]))
        return scored[0][2].tile

    def select_air_wing_active_mission(self, wing):
        enabled = self.air_wing_enabled_missions(wing)
        if "cas" in enabled:
            target_tile = self.select_air_wing_cas_target(wing)
            if target_tile:
                return "cas", target_tile
        if "strategic_strike" in enabled:
            target_tile = self.select_air_wing_strike_target(wing)
            if target_tile:
                return "strategic_strike", target_tile
        return None, None

    def execute_air_wing_active_mission(self, wing, mission_type, target_tile, used_aircraft_counts=None, apply_mission_cooldown=True):
        if not wing or not target_tile:
            return 0
        if not self.air_wing_can_attack_tile(wing, target_tile, mission_type):
            return 0
        mission_aircraft_type = self.air_wing_primary_type_for_mission(wing, mission_type)
        aircraft_data = self.aircraft_type_data(mission_aircraft_type)
        if not aircraft_data:
            return 0
        if not self.aircraft_type_can_reach_tile(wing.base_tile, mission_aircraft_type, target_tile):
            return 0
        ready_for_type = self.air_wing_ready_count_for_type(wing, mission_aircraft_type)
        reserved_for_type = max(0, int((used_aircraft_counts or {}).get(mission_aircraft_type, 0) or 0))
        available_for_type = max(0, ready_for_type - reserved_for_type)
        if available_for_type <= 0:
            return 0
        munition_id = self.air_wing_mission_loadout(mission_aircraft_type, mission_type, target_tile)
        if not munition_id or munition_id not in aircraft_data.get("allowed_munitions", []):
            munition_id = wing.current_loadout or self.default_air_wing_loadout(mission_aircraft_type)
        if not munition_id or munition_id not in aircraft_data.get("allowed_munitions", []):
            return 0
        target_distance = self.hex_distance(wing.base_tile, target_tile)
        air_defense_radius = self.known_enemy_air_defense_radius_near(wing.owner, target_tile)
        launch_distance = self.choose_air_mission_launch_distance(
            target_distance,
            munition_id,
            air_defense_radius,
            wing.risk_policy,
            mission_type,
        )
        if launch_distance is None:
            return 0
        package_size = max(1, int(math.ceil(ready_for_type * self.clamp01(wing.sortie_intensity) * 0.25)))
        sorties = min(available_for_type, package_size)
        if sorties <= 0:
            return 0
        munition_count = sorties * self.air_wing_munition_count_per_sortie(wing, munition_id)
        wing.mission = mission_type
        self.set_air_wing_mission_state(wing, "approach", target_tile)
        launched = False
        if self.munition_uses_air_salvo(munition_id, launch_distance):
            launch_tile = self.launch_tile_for_target_distance(wing.base_tile, target_tile, launch_distance)
            prelaunch_risk = self.resolve_air_defense_against_air_wing(
                wing,
                launch_tile,
                mission_aircraft_type,
                sorties,
                mission_type,
                phase="approach",
                target_tile=target_tile,
                prelaunch_only=True,
            )
            if wing.risk_policy == "cautious" and prelaunch_risk.get("hits", 0) > 0:
                wing.aborted_hours = max(getattr(wing, "aborted_hours", 0.0), AIR_CARRIER_DEFENSIVE_COOLDOWN_HOURS)
                if apply_mission_cooldown:
                    self.set_air_wing_mission_cooldown(wing, mission_type, AIR_CARRIER_DEFENSIVE_COOLDOWN_HOURS)
                self.set_air_wing_mission_state(wing, "aborted", target_tile, "Пуск отменен: риск ПВО")
                return 0
            self.set_air_wing_mission_state(wing, "attack_run", target_tile)
            threat_result = self.resolve_air_defense_against_air_wing(
                wing,
                launch_tile,
                mission_aircraft_type,
                sorties,
                mission_type,
                phase="attack_run",
                target_tile=target_tile,
            )
            if threat_result.get("aborted"):
                return 0
            fighter_result = self.resolve_air_wing_interceptors_against_air_wing(
                wing,
                launch_tile,
                mission_aircraft_type,
                sorties,
                mission_type,
            )
            if fighter_result.get("aborted"):
                return 0
            launched = bool(self.create_air_salvo(
                wing.owner,
                munition_id,
                munition_count,
                target_tile,
                launch_tile=launch_tile,
                source_air_wing=wing,
                mission_type=mission_type,
                target_object_type=self.air_wing_strike_target_object_type(wing, target_tile) if mission_type == "strategic_strike" else None,
                launch_distance=launch_distance,
            ))
            if launched:
                self.set_air_wing_mission_state(wing, "egress", target_tile, wing.last_air_combat_summary)
        else:
            launched = self.resolve_close_air_attack(
                wing,
                target_tile,
                munition_id,
                munition_count,
                aircraft_type=mission_aircraft_type,
                mission_type=mission_type,
            )
        if not launched:
            return 0
        if apply_mission_cooldown:
            intensity = max(0.1, self.clamp01(wing.sortie_intensity))
            cooldown = max(
                AIR_MISSION_MIN_COOLDOWN_HOURS,
                AIR_MISSION_BASE_COOLDOWN_HOURS / intensity,
            )
            self.set_air_wing_mission_cooldown(wing, mission_type, cooldown)
        self.mark_air_wing_mission_target(wing, mission_type, target_tile)
        if used_aircraft_counts is not None:
            used_aircraft_counts[mission_aircraft_type] = used_aircraft_counts.get(mission_aircraft_type, 0) + sorties
        return sorties

    def launch_air_wing_mission_packages(self, wing, mission_type, used_aircraft_counts=None):
        if not wing or mission_type not in self.air_wing_enabled_missions(wing):
            return 0
        if self.air_wing_mission_cooldown(wing, mission_type) > 0:
            return 0
        launched_packages = 0
        launched_sorties = 0
        max_packages = 4
        if mission_type == "cas":
            max_packages = max(1, min(5, len([
                battle for battle in self.battles.values()
                if battle.tile
                and self.battle_has_enemy_for_owner(battle, wing.owner)
                and self.tile_key(battle.tile) in set(self.normalize_air_wing_operation_area_keys(wing))
            ]) or 1))
        elif mission_type == "strategic_strike":
            max_packages = max(1, min(5, len([
                tile for tile in self.air_wing_reachable_operation_tiles(wing, "strategic_strike")
                if self.air_wing_can_attack_tile(wing, tile, "strategic_strike")
                and self.air_wing_strike_tile_score(wing, tile)[0] > 0
            ]) or 1))
        for _package_index in range(max_packages):
            target_tile = (
                self.select_air_wing_cas_target(wing)
                if mission_type == "cas"
                else self.select_air_wing_strike_target(wing)
            )
            if not target_tile:
                break
            sorties = self.execute_air_wing_active_mission(
                wing,
                mission_type,
                target_tile,
                used_aircraft_counts=used_aircraft_counts,
                apply_mission_cooldown=False,
            )
            if sorties <= 0:
                break
            launched_packages += 1
            launched_sorties += sorties
        if launched_packages > 0:
            intensity = max(0.1, self.clamp01(wing.sortie_intensity))
            cooldown = max(
                AIR_MISSION_MIN_COOLDOWN_HOURS,
                AIR_MISSION_BASE_COOLDOWN_HOURS / intensity,
            )
            self.set_air_wing_mission_cooldown(wing, mission_type, cooldown)
        return launched_sorties

    def update_air_missions(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        for wing in list(getattr(self, "air_wings", []) or []):
            self.tick_air_wing_mission_state(wing, elapsed_hours)
            self.sync_air_wing_primary_mission(wing)
            if not self.air_wing_enabled_missions(wing) or wing.ready_count <= 0 or not wing.base_tile:
                if getattr(wing, "mission_state", "returning") not in {"returning", "aborted", "defensive"}:
                    self.set_air_wing_mission_state(wing, "returning", summary=wing.last_air_combat_summary)
                continue
            self.tick_air_wing_mission_cooldowns(wing, elapsed_hours)
            if getattr(wing, "aborted_hours", 0.0) > 0 or self.air_wing_has_global_sortie_cooldown(wing):
                continue
            launched_any = False
            used_aircraft_counts = {}
            if "cas" in self.air_wing_enabled_missions(wing):
                launched_any = self.launch_air_wing_mission_packages(
                    wing,
                    "cas",
                    used_aircraft_counts=used_aircraft_counts,
                ) > 0 or launched_any
            if "strategic_strike" in self.air_wing_enabled_missions(wing):
                launched_any = self.launch_air_wing_mission_packages(
                    wing,
                    "strategic_strike",
                    used_aircraft_counts=used_aircraft_counts,
                ) > 0 or launched_any
            if not launched_any:
                if getattr(wing, "mission_state", "returning") not in {"returning", "aborted", "defensive"}:
                    self.set_air_wing_mission_state(wing, "returning", summary=wing.last_air_combat_summary)

    def update_air_assets_after_tile_owner_change(self, tile, old_owner, new_owner):
        if not tile or old_owner is new_owner:
            return
        airbase = self.airbase_on_tile(tile)
        if airbase:
            if old_owner and airbase in getattr(old_owner, "airbases", []):
                old_owner.airbases.remove(airbase)
            airbase.owner = new_owner
            if new_owner and airbase not in getattr(new_owner, "airbases", []):
                new_owner.airbases.append(airbase)
            for wing in list(self.air_wings_on_tile(tile, owner=old_owner)):
                self.unregister_air_wing(wing)
        for unit in list(self.air_defense_units_on_tile(tile)):
            if unit.owner is new_owner:
                continue
            self.unregister_air_defense_unit(unit)
        for project in list(self.field_helipad_projects_on_tile(tile)):
            if project.owner is not new_owner and project in self.field_helipad_projects:
                self.field_helipad_projects.remove(project)

