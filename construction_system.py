import math

import arcade

from Constants import *


class ConstructionSystemMixin:
    @staticmethod
    def construction_level_for_coverage(coverage):
        return max(1, math.floor(max(0.0, coverage) / CONSTRUCTION_STEP) + 1)

    @staticmethod
    def next_construction_coverage(coverage):
        coverage = max(0.0, min(1.0, coverage))
        if coverage >= 1.0:
            return None
        next_step = math.floor(coverage / CONSTRUCTION_STEP + 1e-9) + 1
        return min(1.0, next_step * CONSTRUCTION_STEP)

    def building_health_map(self, tile):
        health = getattr(tile, "building_health", None)
        if health is None:
            health = {}
            tile.building_health = health
        return health

    def building_health(self, tile, building_key):
        if not tile or not building_key:
            return 1.0
        coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        if coverage <= 0:
            return 1.0
        health = self.building_health_map(tile).get(building_key, 1.0)
        return max(0.0, min(1.0, health))

    def set_building_health(self, tile, building_key, health):
        if not tile or not building_key:
            return False
        coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        if coverage <= 0:
            return False
        health = max(0.0, min(1.0, health))
        health_map = self.building_health_map(tile)
        old_health = self.building_health(tile, building_key)
        if abs(old_health - health) < 0.0005:
            return False
        if health >= 0.999:
            health_map.pop(building_key, None)
        else:
            health_map[building_key] = health
        return True

    def effective_building_coverage(self, tile, building_key, coverage=None):
        if coverage is None:
            coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        return max(0.0, coverage) * self.building_health(tile, building_key)

    def effective_building_coverage_map(self, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        return {
            key: self.effective_building_coverage(tile, key, value)
            for key, value in coverage.items()
            if value > 0
        }

    def building_damage_fraction(self, tile, building_key):
        return 1.0 - self.building_health(tile, building_key)

    def damaged_building_keys(self, tile, threshold=0.001):
        coverage = getattr(tile, "building_coverage", {}) or {}
        return [
            key for key, value in coverage.items()
            if value > 0 and self.building_damage_fraction(tile, key) > threshold
        ]

    def refresh_tile_after_building_health_change(self, tile, owner=None):
        owner = owner or getattr(tile, "owner", None)
        if owner:
            self.update_tile_production_cache(tile)
            self.recalculate_player_supply(owner)
            self.mark_player_storage_dirty(owner)
            self.distribute_player_stockpiles_to_tiles(owner)
            self.recalculate_resource_balance_breakdown(owner)
            self.recalculate_monthly_balance(owner)
        self.tile_visual_revision += 1
        self.invalidate_tile_visual_cache()
        self.invalidate_construction_placement_cache()

    def damage_building(self, tile, building_key, damage_fraction, queue_repair=True):
        if damage_fraction <= 0:
            return False
        old_health = self.building_health(tile, building_key)
        if old_health <= 0:
            return False
        new_health = max(0.0, old_health - damage_fraction)
        changed = self.set_building_health(tile, building_key, new_health)
        if changed:
            owner = getattr(tile, "owner", None)
            self.refresh_tile_after_building_health_change(tile, owner)
            if queue_repair and owner:
                self.enqueue_auto_repair(owner, tile, building_key)
        return changed

    def effective_tile_movement_cost(self, tile):
        # Roads are not modeled yet; damaged infrastructure affects movement indirectly through supply.
        return max(1.0, float(getattr(tile, "movement_cost", 1.0) or 1.0))

    def build_power(self, player):
        coverage_totals = {}
        for tile in player.tiles:
            for key, value in (getattr(tile, "building_coverage", {}) or {}).items():
                coverage_totals[key] = coverage_totals.get(key, 0.0) + self.effective_building_coverage(tile, key, value)

        modifiers = player.construction_modifiers or {}
        industry_efficiency = (player.production_modifiers or {}).get("industry_efficiency", 1.0)
        city_multiplier = modifiers.get("city_build_multiplier", 1.0)
        tech_bonus = modifiers.get("tech_bonus", 0.0)
        industry_power = coverage_totals.get("industry", 0.0) * industry_efficiency
        settlement_power = (
            coverage_totals.get("city", 0.0)
            + coverage_totals.get("village", 0.0) * 0.5
        ) * city_multiplier
        return max(0.0, (industry_power + settlement_power) * BASE_BUILD_POWER_PER_MONTH + tech_bonus)

    def construction_cost(self, player, tile, building_key, current_coverage=None):
        base = BUILDING_CONSTRUCTION_BASE.get(building_key)
        if not base:
            return None

        if current_coverage is None:
            current_coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        current_coverage = max(0.0, min(1.0, current_coverage))
        target_coverage = self.next_construction_coverage(current_coverage)
        if target_coverage is None:
            return None

        step_size = target_coverage - current_coverage
        level = self.construction_level_for_coverage(current_coverage)
        level_multiplier = CONSTRUCTION_LEVEL_MULTIPLIER ** (level - 1)
        modifiers = player.construction_modifiers or {}
        build_efficiency = modifiers.get("build_efficiency", 1.0)
        cost_multiplier = level_multiplier * max(0.05, build_efficiency)
        resource_costs = {
            key: amount * step_size * cost_multiplier
            for key, amount in base.get("resources", {}).items()
        }
        work_required = base.get("work", 0.0) * step_size * level_multiplier
        return {
            "building": building_key,
            "from_coverage": current_coverage,
            "target_coverage": target_coverage,
            "level": level,
            "money_cost": base.get("money", 0.0) * step_size * cost_multiplier,
            "resource_costs": resource_costs,
            "work_required": work_required,
        }

    def repair_cost(self, player, tile, building_key):
        base = BUILDING_CONSTRUCTION_BASE.get(building_key)
        if not base or not tile:
            return None
        coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        if coverage <= 0:
            return None
        health = self.building_health(tile, building_key)
        damage = 1.0 - health
        if damage <= 0.001:
            return None

        level = self.construction_level_for_coverage(coverage)
        level_multiplier = CONSTRUCTION_LEVEL_MULTIPLIER ** (level - 1)
        repair_scale = coverage * damage * level_multiplier
        resource_costs = {
            key: amount * repair_scale * BUILDING_REPAIR_RESOURCE_MULTIPLIER
            for key, amount in base.get("resources", {}).items()
        }
        return {
            "project_type": "repair",
            "building": building_key,
            "from_health": health,
            "target_health": 1.0,
            "damaged_coverage": coverage,
            "level": level,
            "money_cost": base.get("money", 0.0) * repair_scale * BUILDING_REPAIR_MONEY_MULTIPLIER,
            "resource_costs": resource_costs,
            "work_required": max(1.0, base.get("work", 0.0) * repair_scale * BUILDING_REPAIR_WORK_MULTIPLIER),
        }

    def queued_repair_project(self, player, tile, building_key):
        if not player or not tile or not building_key:
            return None
        for project in player.construction_queue:
            cost = project.get("cost", {}) or {}
            if (
                project.get("project_type") == "repair"
                and project.get("tile") is tile
                and (project.get("building") or cost.get("building")) == building_key
            ):
                return project
        return None

    def enqueue_auto_repair(self, player, tile, building_key):
        if not player or not tile or tile.owner is not player:
            return False
        if self.queued_repair_project(player, tile, building_key):
            return False
        cost = self.repair_cost(player, tile, building_key)
        if not cost:
            return False
        resources_spent = {}
        cost["resources_spent"] = resources_spent
        player.construction_queue.append({
            "project_type": "repair",
            "auto_repair": True,
            "tile": tile,
            "building": building_key,
            "from_health": cost.get("from_health", 1.0),
            "target_health": cost.get("target_health", 1.0),
            "money_cost": cost.get("money_cost", 0.0),
            "resource_costs": cost.get("resource_costs", {}),
            "resources_spent": resources_spent,
            "cost": cost,
            "speed": self.build_power(player),
            "progress": 0.0,
            "money_paid": False,
            "status": "queued",
            "status_reason": "Ждет очереди",
            "stall_reasons": [],
            "missing_money": 0.0,
            "missing_resources": {},
        })
        self.invalidate_construction_placement_cache()
        self.mark_player_resource_balance_dirty(player)
        return True

    def enqueue_tile_repairs(self, player, tile):
        if not player or not tile or tile.owner is not player:
            return 0
        added = 0
        for building_key in self.damaged_building_keys(tile):
            if self.enqueue_auto_repair(player, tile, building_key):
                added += 1
        return added

    def prune_invalid_repair_projects(self, player):
        if not player or not player.construction_queue:
            return False
        kept_projects = []
        changed = False
        for project in player.construction_queue:
            if project.get("project_type") != "repair":
                kept_projects.append(project)
                continue
            cost = project.get("cost", {}) or {}
            tile = project.get("tile")
            building_key = project.get("building") or cost.get("building")
            if (
                not tile
                or tile.owner is not player
                or not building_key
                or self.building_damage_fraction(tile, building_key) <= 0.001
            ):
                changed = True
                continue
            kept_projects.append(project)
        if changed:
            player.construction_queue[:] = kept_projects
            self.invalidate_construction_placement_cache()
        return changed

    def enqueue_auto_repairs_for_player(self, player):
        if not player:
            return 0
        self.prune_invalid_repair_projects(player)
        added = 0
        for tile in player.tiles:
            added += self.enqueue_tile_repairs(player, tile)
        return added

    def queued_target_coverage(self, player, tile, building_key):
        coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        for project in player.construction_queue:
            if project.get("project_type") == "repair":
                continue
            cost = project.get("cost", {})
            if project.get("tile") == tile and cost.get("building") == building_key:
                coverage = max(coverage, cost.get("target_coverage", coverage))
        return min(1.0, coverage)

    def construction_queue_target_lookup(self, player, building_key):
        targets = {}
        if not player or not building_key:
            return targets
        for project in player.construction_queue:
            if project.get("project_type") == "repair":
                continue
            cost = project.get("cost", {})
            if cost.get("building") != building_key:
                continue
            tile = project.get("tile")
            if not tile:
                continue
            tile_key = (tile.q, tile.r)
            targets[tile_key] = max(targets.get(tile_key, 0.0), cost.get("target_coverage", 0.0))
        return targets

    def best_building_for_tile(self, player, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        upgradeable = [
            (key, value)
            for key, value in coverage.items()
            if key in BUILDING_CONSTRUCTION_BASE and value < 1.0
        ]
        if upgradeable:
            return max(upgradeable, key=lambda item: item[1])[0]

        if self.is_coastal_land_tile(tile):
            return "port"
        if self.oil_gas_rig_score(player, tile) > 0.12:
            return "oil_gas_rig"
        if self.mine_score(player, tile) > 0.12:
            return "mine"
        agriculture = self.agriculture_score(tile)
        if agriculture > 0.48:
            return "farms"
        if self.industry_score(player, tile) > 0.32:
            return "industry"
        if self.is_water_tile(tile):
            return None
        return "village"

    def selected_construction_building_key(self):
        if not BUILDING_TYPES:
            return None
        self.selected_construction_index = max(0, min(len(BUILDING_TYPES) - 1, self.selected_construction_index))
        return BUILDING_TYPES[self.selected_construction_index][0]

    def construction_queue_signature(self, player):
        if not player:
            return ()
        signature = []
        for project in player.construction_queue:
            cost = project.get("cost", {})
            tile = project.get("tile")
            signature.append((
                id(tile),
                cost.get("building") or project.get("building"),
                round(cost.get("target_coverage", 0.0), 4),
            ))
        return tuple(signature)

    def construction_placement_current_cache_key(self, building_key=None, player=None):
        return (
            tuple((tile.q, tile.r) for tile in self.visible_tiles),
            building_key or self.selected_construction_building_key(),
            self.construction_queue_signature(player or self.human_player),
            self.tile_visual_revision,
        )

    @staticmethod
    def construction_label_rect(tile, label):
        label_width = 104
        label_height = 22
        return (
            tile.center_x - label_width / 2,
            tile.center_y - label_height / 2 - 2,
            label_width,
            label_height,
        )

    def create_construction_label_text(self, tile, label):
        return arcade.Text(
            label,
            tile.center_x,
            tile.center_y - 1,
            (232, 252, 144),
            15,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )

    def get_construction_label_text(self, tile, label):
        tile_key = (tile.q, tile.r)
        text = self.construction_placement_text_cache.get(tile_key)
        if text is None:
            text = self.create_construction_label_text(tile, label)
            self.construction_placement_text_cache[tile_key] = text
        else:
            if text.text != label:
                text.text = label
            text.x = tile.center_x
            text.y = tile.center_y - 1
        return text

    @staticmethod
    def append_construction_label_shapes(shapes, rect):
        x, y, width, height = rect
        center_x = x + width / 2
        center_y = y + height / 2
        shapes.append(
            arcade.shape_list.create_rectangle_filled(
                center_x,
                center_y,
                width,
                height,
                (18, 27, 22, 210),
            )
        )
        shapes.append(
            arcade.shape_list.create_rectangle_outline(
                center_x,
                center_y,
                width,
                height,
                (206, 238, 140, 190),
                1,
            )
        )

    def create_construction_label_shapes(self, rects):
        shapes = arcade.shape_list.ShapeElementList()
        for rect in rects:
            self.append_construction_label_shapes(shapes, rect)
        return shapes

    def rebuild_construction_placement_cache(self):
        if not self.construction_placement_mode or self.active_top_panel_key != "construction":
            self.invalidate_construction_placement_cache()
            return

        building_key = self.selected_construction_building_key()
        player = self.human_player
        cache_key = self.construction_placement_current_cache_key(building_key, player)
        if cache_key == self.construction_placement_cache_key:
            return

        tile_cache = {}
        label_items = []
        label_texts = []
        label_rects = []
        if building_key and player:
            queued_targets = self.construction_queue_target_lookup(player, building_key)
            for tile in self.visible_tiles:
                if tile.owner != player:
                    continue
                coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
                queued_target = max(coverage, queued_targets.get((tile.q, tile.r), coverage))
                queued_delta = max(0.0, queued_target - coverage)
                reason = self.construction_tile_block_reason(
                    player,
                    tile,
                    building_key,
                    queued_coverage=queued_target,
                )
                can_place = reason is None
                label = f"{coverage:.0%}"
                if queued_delta > 0:
                    label += f"+{queued_delta:.0%}"
                tile_cache[(tile.q, tile.r)] = {
                    "can_place": can_place,
                    "coverage": coverage,
                    "queued_delta": queued_delta,
                    "label": label,
                }
                if can_place:
                    label_items.append((tile, label))
                    label_rects.append(self.construction_label_rect(tile, label))
                    label_texts.append(self.get_construction_label_text(tile, label))

        self.construction_placement_cache_key = cache_key
        self.construction_placement_tile_cache = tile_cache
        self.construction_placement_label_items = label_items
        self.construction_placement_label_texts = label_texts
        self.construction_placement_label_rects = label_rects
        self.construction_placement_label_shapes = self.create_construction_label_shapes(label_rects)

    def construction_label_index_for_tile(self, tile):
        tile_key = (tile.q, tile.r)
        for index, (label_tile, _label) in enumerate(self.construction_placement_label_items):
            if (label_tile.q, label_tile.r) == tile_key:
                return index
        return None

    def set_construction_label_for_tile(self, tile, label, visible):
        index = self.construction_label_index_for_tile(tile)
        if not visible:
            if index is not None:
                self.construction_placement_label_items.pop(index)
                self.construction_placement_label_rects.pop(index)
                self.construction_placement_label_texts.pop(index)
                self.construction_placement_label_shapes = self.create_construction_label_shapes(
                    self.construction_placement_label_rects
                )
            return

        rect = self.construction_label_rect(tile, label)
        if index is None:
            self.construction_placement_label_items.append((tile, label))
            self.construction_placement_label_rects.append(rect)
            self.construction_placement_label_texts.append(self.get_construction_label_text(tile, label))
            self.append_construction_label_shapes(self.construction_placement_label_shapes, rect)
        else:
            self.construction_placement_label_items[index] = (tile, label)
            old_rect = self.construction_placement_label_rects[index]
            self.construction_placement_label_rects[index] = rect
            text = self.construction_placement_label_texts[index]
            if text.text != label:
                text.text = label
            text.x = tile.center_x
            text.y = tile.center_y - 1
            if rect != old_rect:
                self.construction_placement_label_shapes = self.create_construction_label_shapes(
                    self.construction_placement_label_rects
                )

    def refresh_construction_placement_tile(self, tile, building_key=None):
        if not tile or not self.construction_placement_mode or self.active_top_panel_key != "construction":
            return
        building_key = building_key or self.selected_construction_building_key()
        player = self.human_player
        if not building_key or not player:
            return
        if self.construction_placement_cache_key is None:
            self.rebuild_construction_placement_cache()
            return
        if not any(visible_tile is tile for visible_tile in self.visible_tiles):
            self.construction_placement_cache_key = self.construction_placement_current_cache_key(building_key, player)
            return

        reason = self.construction_tile_block_reason(player, tile, building_key)
        can_place = reason is None
        coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        queued_target = self.queued_target_coverage(player, tile, building_key)
        queued_delta = max(0.0, queued_target - coverage)
        label = f"{coverage:.0%}"
        if queued_delta > 0:
            label += f"+{queued_delta:.0%}"

        self.construction_placement_tile_cache[(tile.q, tile.r)] = {
            "can_place": can_place,
            "coverage": coverage,
            "queued_delta": queued_delta,
            "label": label,
        }
        self.set_construction_label_for_tile(tile, label, can_place)
        self.construction_placement_cache_key = self.construction_placement_current_cache_key(building_key, player)
        self.apply_tile_draw_color(tile)

    def construction_tile_block_reason(self, player, tile, building_key, queued_coverage=None):
        if not player:
            return "Нет страны"
        if not tile or tile.owner != player:
            return "Чужая клетка"
        if building_key not in BUILDING_CONSTRUCTION_BASE:
            return "Неизвестное строение"
        coverage = (
            queued_coverage
            if queued_coverage is not None
            else self.queued_target_coverage(player, tile, building_key)
        )
        if coverage >= 1.0:
            return "Уже максимум"
        if building_key == "port":
            if not self.is_coastal_land_tile(tile):
                return "Порт только рядом с водой"
        elif self.is_water_tile(tile):
            return "Нужна суша"
        if building_key == "mine" and self.weighted_resource_score(tile, STARTING_SOLID_MINE_RESOURCE_WEIGHTS) <= 0:
            return "Нужны твердые залежи"
        if building_key == "oil_gas_rig" and self.weighted_resource_score(tile, STARTING_OIL_GAS_RIG_RESOURCE_WEIGHTS) <= 0:
            return "Нужна нефть или газ"
        if not self.construction_cost(player, tile, building_key, coverage):
            return "Нельзя улучшить"
        return None

    def can_place_construction(self, player, tile, building_key):
        return self.construction_tile_block_reason(player, tile, building_key) is None

    def set_construction_placement_mode(self, enabled):
        enabled = bool(enabled and self.active_top_panel_key == "construction" and self.human_player)
        if self.construction_placement_mode == enabled:
            return
        self.construction_placement_mode = enabled
        self.invalidate_construction_placement_cache()
        self.create_map_overview()
        self.refresh_visible_tiles()

    def enqueue_construction(self, player, tile, building_key=None, refresh=True):
        if not player or tile.owner != player:
            self.hex_panel_message = "Клетка не принадлежит стране"
            self.hex_panel_message_timer = 2.0
            return False

        building_key = building_key or self.best_building_for_tile(player, tile)
        if not building_key:
            self.hex_panel_message = "Здесь нельзя строить"
            self.hex_panel_message_timer = 2.0
            return False
        if building_key == "port" and not self.is_coastal_land_tile(tile):
            self.hex_panel_message = "Порт только у воды"
            self.hex_panel_message_timer = 2.0
            return False

        current_coverage = self.queued_target_coverage(player, tile, building_key)
        cost = self.construction_cost(player, tile, building_key, current_coverage)
        if not cost:
            self.hex_panel_message = "Уже максимум"
            self.hex_panel_message_timer = 2.0
            return False

        speed = self.build_power(player)
        cost = dict(cost)
        resources_spent = {}
        resource_costs = cost.get("resource_costs", {})
        cost["resources_spent"] = resources_spent
        player.construction_queue.append({
            "project_type": "build",
            "tile": tile,
            "building": building_key,
            "from_coverage": cost.get("from_coverage", current_coverage),
            "target_coverage": cost.get("target_coverage", current_coverage),
            "money_cost": cost.get("money_cost", 0.0),
            "resource_costs": resource_costs,
            "resources_spent": resources_spent,
            "cost": cost,
            "speed": speed,
            "progress": 0.0,
            "money_paid": False,
            "status": "queued",
            "status_reason": "Ждет очереди",
            "stall_reasons": [],
            "missing_money": 0.0,
            "missing_resources": {},
        })
        if refresh:
            self.refresh_construction_placement_tile(tile, building_key)
        return True

    def enqueue_construction_steps(self, player, tile, building_key=None, steps=1):
        added = 0
        for _index in range(max(1, steps)):
            if not self.enqueue_construction(player, tile, building_key, refresh=False):
                break
            added += 1

        if added:
            self.refresh_construction_placement_tile(tile, building_key)
        return added

    def cancel_queued_construction(self, player, tile, building_key=None):
        if not player or not tile:
            return False
        building_key = building_key or self.selected_construction_building_key()
        if not building_key:
            return False

        for index in range(len(player.construction_queue) - 1, -1, -1):
            project = player.construction_queue[index]
            cost = project.get("cost", {})
            if project.get("tile") != tile or cost.get("building") != building_key:
                continue
            if project.get("money_paid", False) or project.get("progress", 0.0) > 0:
                return False

            player.construction_queue.pop(index)
            self.refresh_construction_placement_tile(tile, building_key)
            return True

        return False

    def has_cancelable_construction(self, player, tile, building_key=None):
        if not player or not tile:
            return False
        building_key = building_key or self.selected_construction_building_key()
        if not building_key:
            return False
        return any(
            project.get("tile") == tile
            and (project.get("cost", {}) or {}).get("building") == building_key
            and not project.get("money_paid", False)
            and project.get("progress", 0.0) <= 0
            for project in player.construction_queue
        )

    @staticmethod
    def construction_project_is_locked(project):
        return project.get("money_paid", False) or project.get("progress", 0.0) > 0

    def can_move_construction_project(self, player, index, direction):
        if not player:
            return False
        queue = player.construction_queue
        target_index = index + direction
        if index < 0 or index >= len(queue) or target_index < 0 or target_index >= len(queue):
            return False
        return (
            not self.construction_project_is_locked(queue[index])
            and not self.construction_project_is_locked(queue[target_index])
        )

    def move_construction_project(self, player, index, direction):
        if not self.can_move_construction_project(player, index, direction):
            return False
        queue = player.construction_queue
        target_index = index + direction
        queue[index], queue[target_index] = queue[target_index], queue[index]
        self.invalidate_construction_placement_cache()
        self.recalculate_monthly_balance(player)
        return True

    def can_move_construction_group(self, player, group, direction):
        if not player or not group:
            return False
        queue = player.construction_queue
        groups = self.construction_queue_groups(queue)
        group_index = next(
            (
                index
                for index, candidate in enumerate(groups)
                if candidate["start_index"] == group["start_index"]
                and candidate["end_index"] == group["end_index"]
            ),
            None,
        )
        target_group_index = group_index + direction if group_index is not None else None
        if group_index is None or target_group_index < 0 or target_group_index >= len(groups):
            return False
        target_group = groups[target_group_index]
        return (
            not any(self.construction_project_is_locked(project) for project in group["projects"])
            and not any(self.construction_project_is_locked(project) for project in target_group["projects"])
        )

    def move_construction_group(self, player, group, direction):
        if not self.can_move_construction_group(player, group, direction):
            return False
        queue = player.construction_queue
        groups = self.construction_queue_groups(queue)
        group_index = next(
            (
                index
                for index, candidate in enumerate(groups)
                if candidate["start_index"] == group["start_index"]
                and candidate["end_index"] == group["end_index"]
            ),
            None,
        )
        target_group_index = group_index + direction
        current_group = groups[group_index]
        target_group = groups[target_group_index]
        current_projects = current_group["projects"]
        target_projects = target_group["projects"]
        if direction < 0:
            replacement = current_projects + target_projects
            start = target_group["start_index"]
            end = current_group["end_index"] + 1
        else:
            replacement = target_projects + current_projects
            start = current_group["start_index"]
            end = target_group["end_index"] + 1
        queue[start:end] = replacement
        self.invalidate_construction_placement_cache()
        self.recalculate_monthly_balance(player)
        return True

    def sync_construction_project_fields(self, project):
        cost = project.setdefault("cost", {})
        project_type = project.get("project_type") or cost.get("project_type") or "build"
        project["project_type"] = project_type
        cost["project_type"] = project_type
        building_key = project.get("building") or cost.get("building")
        if building_key:
            project["building"] = building_key
            cost["building"] = building_key

        for key in (
            "from_coverage", "target_coverage",
            "from_health", "target_health", "damaged_coverage",
            "money_cost", "work_required", "level",
        ):
            if key not in project and key in cost:
                project[key] = cost[key]
            elif key in project:
                cost[key] = project[key]

        resource_costs = project.get("resource_costs")
        if resource_costs is None:
            resource_costs = cost.get("resource_costs", {})
        project["resource_costs"] = resource_costs
        cost["resource_costs"] = resource_costs

        resources_spent = project.get("resources_spent")
        if resources_spent is None:
            resources_spent = cost.get("resources_spent", {})
        project["resources_spent"] = resources_spent
        cost["resources_spent"] = resources_spent

        project.setdefault("status", "queued")
        project.setdefault("status_reason", "Ждет очереди")
        project.setdefault("stall_reasons", [])
        project.setdefault("missing_money", 0.0)
        project.setdefault("missing_resources", {})
        project.setdefault("progress", 0.0)
        project.setdefault("money_paid", False)
        project.setdefault("paused", False)
        return cost

    @staticmethod
    def construction_project_status_label(status):
        labels = {
            "queued": "Ждет очереди",
            "building": "Строится",
            "repairing": "Ремонт",
            "waiting_money": "Ждет деньги",
            "waiting_resources": "Ждет ресурсы",
            "waiting_power": "Нет строймощности",
            "paused": "Пауза",
            "complete": "Готово",
        }
        return labels.get(status, "Ждет")

    def set_construction_project_status(
        self,
        project,
        status,
        reasons=None,
        missing_money=0.0,
        missing_resources=None,
    ):
        reasons = reasons or []
        missing_resources = missing_resources or {}
        project["status"] = status
        project["stall_reasons"] = reasons
        project["status_reason"] = "; ".join(reasons) if reasons else self.construction_project_status_label(status)
        project["missing_money"] = max(0.0, missing_money)
        project["missing_resources"] = dict(missing_resources)

    def construction_project_progress_delta(self, player, project, month_fraction=1.0, build_power=None):
        cost = self.sync_construction_project_fields(project)
        speed = self.build_power(player) if build_power is None else build_power
        project["speed"] = speed
        if speed <= 0:
            return 0.0
        work_required = max(1.0, cost.get("work_required", project.get("work_required", 1.0)))
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        return min(1.0 - progress, speed * max(0.0, month_fraction) / work_required)

    def construction_project_resource_needs(self, project, progress_delta):
        self.sync_construction_project_fields(project)
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        target_progress = min(1.0, progress + max(0.0, progress_delta))
        resources_spent = project.get("resources_spent", {})
        needs = {}
        for key, total_amount in (project.get("resource_costs", {}) or {}).items():
            if total_amount <= 0:
                continue
            target_spent = total_amount * target_progress
            amount_needed = max(0.0, target_spent - resources_spent.get(key, 0.0))
            if amount_needed > 0:
                needs[key] = amount_needed
        return needs

    @staticmethod
    def construction_project_is_active_status(status):
        return status in ("building", "repairing")

    def tile_has_active_battle(self, tile):
        if not tile or not getattr(self, "battles", None):
            return False
        return (tile.q, tile.r) in self.battles

    def construction_project_speed_multiplier(self, project):
        tile = project.get("tile") if project else None
        if self.tile_has_active_battle(tile):
            return CONSTRUCTION_BATTLE_TILE_SPEED_MULTIPLIER
        return 1.0

    def construction_project_speed_note(self, project):
        if self.construction_project_speed_multiplier(project) < 0.999:
            return "Работы замедлены: бой на клетке"
        return None

    def active_construction_projects(self, player, limit=None):
        if not player:
            return []
        limit = CONSTRUCTION_PARALLEL_PROJECTS if limit is None else max(1, limit)
        projects = []
        for project in player.construction_queue:
            if project.get("paused", False):
                continue
            projects.append(project)
            if len(projects) >= limit:
                break
        return projects

    def construction_project_remaining_months(self, player, project, build_power=None):
        cost = self.sync_construction_project_fields(project)
        speed = self.build_power(player) if build_power is None else build_power
        if speed <= 0:
            return None
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        work_required = max(0.0, cost.get("work_required", project.get("work_required", 0.0)))
        return work_required * max(0.0, 1.0 - progress) / speed

    def evaluate_construction_project_status(
        self,
        player,
        project,
        month_fraction=1.0,
        stock_amount_func=None,
        build_power=None,
        update=True,
    ):
        cost = self.sync_construction_project_fields(project)
        stock_amount_func = stock_amount_func or (lambda key: self.stockpile_amount(player, key))
        speed = (self.build_power(player) if player else 0.0) if build_power is None else build_power
        project["speed"] = speed
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        money_cost = max(0.0, cost.get("money_cost", project.get("money_cost", 0.0)))

        info = {
            "status": "queued",
            "reasons": [],
            "missing_money": 0.0,
            "missing_resources": {},
            "resource_needs": {},
            "progress_delta": 0.0,
            "remaining_months": self.construction_project_remaining_months(player, project, build_power=speed),
        }

        if progress >= 0.999:
            info["status"] = "complete"
            if update:
                self.set_construction_project_status(project, "complete")
            return info

        if project.get("paused", False):
            info["status"] = "paused"
            info["reasons"] = ["остановлено игроком"]
            if update:
                self.set_construction_project_status(project, "paused", info["reasons"])
            return info

        if not project.get("money_paid", False) and player and player.budget < money_cost:
            missing_money = money_cost - player.budget
            info.update({
                "status": "waiting_money",
                "missing_money": missing_money,
                "reasons": [f"не хватает денег {self.format_money(missing_money)}"],
            })
            if update:
                self.set_construction_project_status(
                    project,
                    "waiting_money",
                    info["reasons"],
                    missing_money=missing_money,
                )
            return info

        if speed <= 0:
            info.update({
                "status": "waiting_power",
                "reasons": ["нет строительной мощности"],
            })
            if update:
                self.set_construction_project_status(project, "waiting_power", info["reasons"])
            return info

        progress_delta = self.construction_project_progress_delta(player, project, month_fraction, build_power=speed)
        info["progress_delta"] = progress_delta
        if progress_delta <= 0:
            info["status"] = "complete"
            if update:
                self.set_construction_project_status(project, "complete")
            return info

        resource_needs = self.construction_project_resource_needs(project, progress_delta)
        missing_resources = {}
        for key, amount_needed in resource_needs.items():
            available = stock_amount_func(key)
            if available + 0.001 < amount_needed:
                missing_resources[key] = amount_needed - available

        info["resource_needs"] = resource_needs
        if missing_resources:
            reasons = [
                f"нет {self.resource_display_name(key)} {self.format_resource_amount(amount)}"
                for key, amount in sorted(missing_resources.items(), key=lambda item: item[1], reverse=True)
            ]
            info.update({
                "status": "waiting_resources",
                "missing_resources": missing_resources,
                "reasons": reasons,
            })
            if update:
                self.set_construction_project_status(
                    project,
                    "waiting_resources",
                    reasons,
                    missing_resources=missing_resources,
                )
            return info

        info["status"] = "repairing" if project.get("project_type") == "repair" else "building"
        if update:
            self.set_construction_project_status(project, info["status"])
        return info

    def apply_repair_project_progress(self, player, project, old_progress, new_progress):
        if project.get("project_type") != "repair":
            return
        tile = project.get("tile")
        cost = self.sync_construction_project_fields(project)
        building_key = project.get("building") or cost.get("building")
        if not tile or not building_key:
            return
        from_health = max(0.0, min(1.0, cost.get("from_health", project.get("from_health", 1.0))))
        target_health = max(from_health, min(1.0, cost.get("target_health", project.get("target_health", 1.0))))
        health_gain = max(0.0, new_progress - old_progress) * max(0.0, target_health - from_health)
        if health_gain <= 0:
            return
        if self.set_building_health(tile, building_key, self.building_health(tile, building_key) + health_gain):
            self.refresh_tile_after_building_health_change(tile, player)

    def complete_construction_project(self, player, project):
        tile = project.get("tile")
        cost = self.sync_construction_project_fields(project)
        building_key = project.get("building") or cost.get("building")
        if not tile or not building_key:
            return
        if project.get("project_type") == "repair":
            self.set_building_health(tile, building_key, cost.get("target_health", 1.0))
            self.refresh_tile_after_building_health_change(tile, player)
            return
        coverage = getattr(tile, "building_coverage", None)
        if coverage is None:
            coverage = {}
            tile.building_coverage = coverage
        coverage[building_key] = min(1.0, max(coverage.get(building_key, 0.0), cost.get("target_coverage", 0.0)))
        if not hasattr(tile, "buildings") or tile.buildings is None:
            tile.buildings = []
        if building_key not in tile.buildings:
            tile.buildings.append(building_key)
        if building_key == "airbase" and not self.airbase_on_tile(tile):
            self.create_airbase(player, tile, coverage.get("airbase", 0.0))
        self.recalculate_state_resources(player)
        self.update_tile_production_cache(tile)
        self.recalculate_player_supply(player)
        self.mark_player_storage_dirty(player)
        self.distribute_player_stockpiles_to_tiles(player)
        self.recalculate_resource_balance_breakdown(player)
        self.recalculate_monthly_balance(player)
        self.tile_visual_revision += 1
        self.invalidate_tile_visual_cache()
        self.invalidate_construction_placement_cache()

    def run_construction_tick(self, player, elapsed_hours=None):
        with self.profiler.measure("construction_auto_repairs"):
            self.enqueue_auto_repairs_for_player(player)
        if not player.construction_queue:
            return
        month_fraction = max(0.0, (elapsed_hours or 0.0) / PRODUCTION_MONTH_HOURS)
        if month_fraction <= 0:
            return

        with self.profiler.measure("construction_active_lookup"):
            active_projects = self.active_construction_projects(player)
        if not active_projects:
            with self.profiler.measure("construction_paused_status"):
                for project in player.construction_queue:
                    if project.get("paused", False):
                        self.evaluate_construction_project_status(player, project, update=True)
            return

        with self.profiler.measure("construction_build_power"):
            build_power = self.build_power(player) / max(1, len(active_projects))
        completed_projects = []
        with self.profiler.measure("construction_projects"):
            for project in list(active_projects):
                project_build_power = build_power * self.construction_project_speed_multiplier(project)
                cost = self.sync_construction_project_fields(project)
                money_cost = cost.get("money_cost", 0.0)
                if not project.get("money_paid", False):
                    if player.budget < money_cost:
                        with self.profiler.measure("construction_status_eval"):
                            self.evaluate_construction_project_status(
                                player,
                                project,
                                month_fraction,
                                build_power=project_build_power,
                            )
                        continue
                    player.budget -= money_cost
                    project["money_paid"] = True

                with self.profiler.measure("construction_status_eval"):
                    status_info = self.evaluate_construction_project_status(
                        player,
                        project,
                        month_fraction,
                        build_power=project_build_power,
                    )
                if not self.construction_project_is_active_status(status_info["status"]):
                    continue

                with self.profiler.measure("construction_consume_resources"):
                    resources_spent = project.get("resources_spent", cost.setdefault("resources_spent", {}))
                    for key, amount_needed in status_info["resource_needs"].items():
                        consumed = self.consume_from_stockpile(player, key, amount_needed)
                        resources_spent[key] = resources_spent.get(key, 0.0) + consumed

                old_progress = max(0.0, min(1.0, project.get("progress", 0.0)))
                new_progress = min(1.0, old_progress + status_info["progress_delta"])
                project["progress"] = new_progress
                if project.get("project_type") == "repair":
                    self.apply_repair_project_progress(player, project, old_progress, new_progress)
                self.set_construction_project_status(project, status_info["status"])
                self.mark_player_resource_balance_dirty(player)
                if project["progress"] >= 0.999:
                    self.complete_construction_project(player, project)
                    completed_projects.append(project)

        with self.profiler.measure("construction_complete_cleanup"):
            for project in completed_projects:
                if project in player.construction_queue:
                    player.construction_queue.remove(project)
            if completed_projects:
                self.invalidate_construction_placement_cache()

    def active_construction_consumption(self, player):
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

    def construction_stall_reasons(self, player):
        if not player.construction_queue:
            return []
        projects = self.active_construction_projects(player)
        if not projects:
            return []
        project = projects[0]
        status_info = self.evaluate_construction_project_status(
            player,
            project,
            month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
        )
        if status_info["status"] in ("waiting_money", "waiting_resources", "waiting_power"):
            return status_info["reasons"]
        return []

    def construction_warning_summary(self, player):
        reasons = self.construction_stall_reasons(player)
        if not reasons:
            return None
        active_projects = self.active_construction_projects(player)
        project = active_projects[0] if active_projects else player.construction_queue[0]
        status_label = self.construction_project_status_label(project.get("status", "queued"))
        return {
            "level": "red",
            "title": f"Стройка: {status_label}",
            "lines": [self.construction_project_label(project)] + reasons[:5],
        }

