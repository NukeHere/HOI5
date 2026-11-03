from collections import Counter, defaultdict
import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_fronts import deployment_posts
from ai_regions import RegionMap
from headless_simulation import HeadlessGame


class FrontTests(unittest.TestCase):
    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.game = HeadlessGame(1, countries=2, map_size=16)
        game = self.game
        self.a, self.b = game.players
        for tile in game.hex_grid:
            tile.terrain_type = "plains"
            tile.water_cover = 0
            tile.passability = .8
            tile.movement_cost = 1
            tile.supply_score = 1
            owner = self.a if 2 <= tile.q <= 6 and 4 <= tile.r <= 6 else (
                    self.b if 7 <= tile.q <= 11 and 4 <= tile.r <= 6 else None)
            game.set_tile_owner_only(tile, owner)
        self.a.capital_tile = game.hex_lookup[3, 5]
        self.b.capital_tile = game.hex_lookup[10, 5]
        for player in (self.a, self.b):
            for d in player.divisions:
                d.tile, d.target_tile, d.path = player.capital_tile, None, []
                d.organization = d.max_organization
                d.last_supply_ratio = 1
        game.ai_system.geography = RegionMap(game)
        game.politics.relation(self.a.id, self.b.id).at_war = True
        self.ai = game.ai_system
        self.bot = self.ai.bots[self.a.id]
        self.refresh()

    def refresh(self):
        self.ai.units_by_tile = defaultdict(list)
        for d in self.game.divisions:
            self.ai.units_by_tile[self.game.tile_key(d.tile)].append(d)
        self.bot.regions = self.ai.profiles(self.a)

    def fronts(self):
        return {self.game.tile_key(t) for t in self.a.tiles
                if any(n.owner is self.b for n in self.game.neighbor_tiles(t))}

    def test_rear_army_covers_all_three_front_hexes(self):
        front = self.fronts()
        self.assertEqual(len(front), 3)
        self.ai.assign_forces(self.bot, self.a)
        self.ai.tactical(self.bot, self.a)
        self.game.simulation_server.process_pending_commands()
        destinations = Counter(self.game.tile_key(d.target_tile or d.tile) for d in self.a.divisions)
        self.assertTrue(all(destinations[k] >= 1 for k in front))
        self.assertLessEqual(max(destinations.values()), 5)
        for _ in range(14):
            self.game.update_divisions(24)
        positions = Counter(self.game.tile_key(d.tile) for d in self.a.divisions)
        self.assertTrue(all(positions[k] >= 1 for k in front))

    def test_surplus_guards_leave_stack_to_cover_gaps(self):
        for d in self.a.divisions:
            d.tile = self.game.hex_lookup[6, 5]
        self.refresh()
        posts, pinned = deployment_posts(self.ai, self.bot, self.a, [self.b])
        counts = Counter(posts.values())
        self.assertTrue(all(counts[key] >= 1 for key in self.fronts()))
        self.assertLessEqual(max(counts.values()), 5)

    def test_capture_is_held_in_peace_instead_of_return_to_capital(self):
        self.game.politics.relation(self.a.id, self.b.id).at_war = False
        d = self.a.divisions[-1]
        d.tile = self.game.hex_lookup[6, 5]
        self.bot.hex_assignments[d.id] = self.game.tile_key(d.tile)
        self.refresh()
        self.ai.tactical(self.bot, self.a)
        self.game.simulation_server.process_pending_commands()
        self.assertIsNone(d.target_tile)
        self.assertFalse(d.path)
        self.assertEqual(self.bot.hex_assignments[d.id], self.game.tile_key(d.tile))

    def test_reserve_identity_does_not_rotate_each_replan(self):
        for d in self.a.divisions:
            d.tile = self.game.hex_lookup[6, 5]
        self.refresh()
        posts, pinned = deployment_posts(self.ai, self.bot, self.a, [self.b])
        reserve = self.game.division_by_id(self.bot.reserve_id)
        capital = self.game.tile_key(self.a.capital_tile)
        self.assertEqual(posts[reserve.id], capital)
        self.game.issue_division_plan_order(reserve, self.a.capital_tile)
        reserve.movement_progress = .3
        again, pinned = deployment_posts(self.ai, self.bot, self.a, [self.b])
        self.assertEqual(again[reserve.id], capital)
        self.assertIn(reserve.id, pinned)
        self.assertEqual(reserve.movement_progress, .3)

    def test_units_on_isolated_component_get_reachable_posts(self):
        island = self.game.hex_lookup[14, 14]
        self.game.set_tile_owner_only(island, self.a)
        self.game.set_tile_owner_only(self.game.hex_lookup[14, 15], self.b)
        d = self.a.divisions[-1]
        d.tile = island
        self.refresh()
        posts, pinned = deployment_posts(self.ai, self.bot, self.a, [self.b])
        self.assertEqual(posts[d.id], self.game.tile_key(island))
        self.assertTrue(all(target != self.game.tile_key(island) for identifier, target in posts.items() if identifier != d.id))

    def test_group_already_in_battle_counts_when_continuing_attack(self):
        target = self.game.hex_lookup[7, 5]
        joined, approaching = self.a.divisions[:2]
        joined.battle_id, joined.battle_side = 123, "attacker"
        self.game.battles[123] = SimpleNamespace(tile=target)
        approaching.path, approaching.target_tile, approaching.route_mode = [target], target, "attack"
        self.ai.units_by_tile[self.game.tile_key(target)] = [SimpleNamespace(owner=self.b)]
        with patch("ai_system.division_vector", return_value={"attack": 10, "defense": 15}), \
             patch.object(self.ai, "nearby_enemies", return_value=[]), patch.object(self.ai, "send") as send:
            self.ai.tactical(self.bot, self.a)
        self.assertFalse(any(c.args[1] == "move" and c.kwargs.get("division_id") == approaching.id
                             for c in send.call_args_list))

    def test_air_operation_area_includes_hostile_side_of_front(self):
        self.a.capital_tile.building_coverage["airbase"] = 1
        self.game.create_airbase(self.a, self.a.capital_tile, coverage=1)
        region = next(r for r, p in self.bot.regions.items() if any(k in self.fronts() for k in p["tiles"]))
        ok, reason = self.ai.apply_action(self.bot, self.a, dict(operation="air", region_id=region))
        self.assertTrue(ok, reason)
        self.assertTrue(self.a.air_wings)
        self.assertTrue(any("patrol" in wing.enabled_missions for wing in self.a.air_wings))
        self.assertTrue(any("cas" in wing.enabled_missions for wing in self.a.air_wings))
        self.assertTrue(any(self.game.tile_for_key(key).owner is self.b for wing in self.a.air_wings
                            for key in wing.operation_area_tile_keys))

    def test_exhausted_unit_is_not_redeployed_before_rest_threshold(self):
        d = self.a.divisions[-1]
        d.tile = self.game.hex_lookup[6, 5]
        d.organization = d.max_organization * .35
        self.b.divisions[0].tile = self.game.hex_lookup[7, 5]
        self.refresh()
        self.ai.tactical(self.bot, self.a)
        self.game.simulation_server.process_pending_commands()
        self.assertIn(d.id, self.bot.resting_ids)
        self.assertIsNotNone(d.target_tile)
        self.assertFalse(self.ai.nearby_enemies(self.a, d.target_tile))
        d.tile, d.path, d.target_tile = d.target_tile, [], None
        d.organization = d.max_organization * .7
        self.refresh()
        self.ai.tactical(self.bot, self.a)
        self.game.simulation_server.process_pending_commands()
        self.assertIn(d.id, self.bot.resting_ids)
        self.assertFalse(d.path)
        d.organization = d.max_organization * .81
        self.ai.tactical(self.bot, self.a)
        self.game.simulation_server.process_pending_commands()
        self.assertNotIn(d.id, self.bot.resting_ids)

    def test_moderate_supply_alone_does_not_trigger_retreat_loop(self):
        d = self.a.divisions[-1]
        d.tile = self.game.hex_lookup[6, 5]
        d.last_supply_ratio = .2
        self.b.divisions[0].tile = self.game.hex_lookup[7, 5]
        self.refresh()
        with patch("ai_system.division_vector", return_value={"attack": 10, "defense": 20}), \
             patch.object(self.ai, "send") as send:
            self.ai.tactical(self.bot, self.a)
        self.assertFalse(any(c.args[1] == "withdraw" and c.kwargs.get("division_id") == d.id for c in send.call_args_list))

    def test_supplied_inventory_can_capture_empty_hex_with_limited_resupply(self):
        for d in self.a.divisions:
            d.tile = self.game.hex_lookup[6, 5]
            d.last_supply_ratio = .18
        self.refresh()
        self.ai.tactical(self.bot, self.a)
        self.game.simulation_server.process_pending_commands()
        self.assertTrue(any(r.get("operation") == "attack" and r.get("accepted") for r in self.bot.history))

    def test_front_snapshot_remains_json_serializable(self):
        self.ai.tactical(self.bot, self.a)
        self.game.simulation_server.process_pending_commands()
        self.assertTrue(self.bot.front_quotas)
        json.dumps(self.ai.snapshot())

    def test_defended_hex_can_be_attacked_by_more_than_four_from_two_sides(self):
        game = self.game
        target = game.hex_lookup[7, 5]
        approaches = game.neighbor_tiles(target)[:2]
        for tile in approaches:
            game.set_tile_owner_only(tile, self.a)
        for tile in list(self.b.tiles):
            if tile is not target:
                game.set_tile_owner_only(tile, None)
        for index, division in enumerate(self.a.divisions):
            division.tile = approaches[index % 2]
            division.front_width = 20
        for division in self.b.divisions[:4]:
            division.tile = target
        self.refresh()
        def power(division):
            return {"attack": 12 if division.owner is self.a else 1,
                    "defense": 16 if division.owner is self.b else 30}
        with patch("ai_system.division_vector", side_effect=power), \
             patch("ai_system.deployment_posts", return_value=({}, set())), \
             patch.object(self.ai, "send") as send:
            self.ai.tactical(self.bot, self.a)
        attacks = [c.kwargs for c in send.call_args_list if c.args[1] == "attack"]
        self.assertGreater(len(attacks), 4)
        self.assertEqual({c["tile_key"] for c in attacks}, {game.tile_key(target)})
        sources = {game.division_by_id(c["division_id"]).tile for c in attacks}
        self.assertEqual(len(sources), 2)

    def test_attack_avoids_empty_salient_with_only_one_friendly_neighbor(self):
        game = self.game
        target = game.hex_lookup[7, 5]
        neighbors = game.neighbor_tiles(target)
        approaches = [t for t in neighbors if t.owner is self.a]
        self.assertEqual(len(approaches), 1)
        self.assertGreaterEqual(sum(t.owner is self.b for t in neighbors), 2)
        for division in self.a.divisions:
            division.tile = approaches[0]
        self.refresh()
        with patch("ai_system.deployment_posts", return_value=({}, set())), patch.object(self.ai, "send") as send:
            self.ai.tactical(self.bot, self.a)
        self.assertFalse(any(c.args[1] == "attack" and c.kwargs["tile_key"] == game.tile_key(target)
                             for c in send.call_args_list))

    def test_mobilization_can_train_past_starting_army_and_respects_reserve(self):
        game = self.game
        game.politics.relation(self.a.id, self.b.id).at_war = False
        game.politics.war_goals[self.a.id, self.b.id] = 30
        service = game.recruitment
        key = "basic_infantry"
        template = service.archetypes[key]
        original = len(self.a.divisions)
        self.a.budget = 500_000_000
        self.a.manpower_reserve = 200_000
        resources = self.ai.military_reserve(self.a, extra=template).keys() | template["supply_capacity"].keys()
        for resource in resources:
            game.add_to_stockpile_unsafe(self.a, resource, 100_000)
        ammo = "small_arms_ammo"
        existing = self.ai.military_reserve(self.a)[ammo]
        per_unit = (self.ai.military_reserve(self.a, extra=template)[ammo] - existing
                    + service.quote(template)["equipment"][ammo])
        stock = game.stockpile_amount(self.a, ammo)
        game.consume_from_stockpile(self.a, ammo, stock - existing - 10.5 * per_unit)
        operation = dict(operation="recruit", key=key, batch=True)
        self.assertTrue(self.ai.apply_action(self.bot, self.a, operation)[0])
        self.assertEqual(len(service.queues[self.a.id]), 10)
        self.assertFalse(self.ai.apply_action(self.bot, self.a, operation)[0])
        game.recruitment.update(24)
        self.assertEqual([p["hours"] for p in service.queues[self.a.id]], [24] * 10)
        game.recruitment.update(service.quote(template)["days"] * 24)
        self.assertEqual(len(self.a.divisions), original + 10)
        news = game.politics.news
        deployed = [item for item in news.visible(self.a.id) if item.key == "division_deployed"]
        self.assertEqual(len(deployed), 1)
        self.assertIn("10", deployed[0].title)
        self.assertIn("×10", deployed[0].body)
        self.assertFalse(any(item.key in {"division_training", "division_deployed"}
                             for item in news.visible(self.b.id)))

    def test_justification_targets_deployment_and_blocks_unprepared_declaration(self):
        game = self.game
        game.politics.relation(self.a.id, self.b.id).at_war = False
        self.a.legitimacy = self.a.war_support = .8
        self.a.politics.political_capital = 100
        game.politics.war_goals[self.a.id, self.b.id] = 0
        self.ai.tactical(self.bot, self.a)
        self.assertTrue(self.bot.hex_assignments)
        self.assertTrue(set(self.bot.hex_assignments.values()) & self.fronts())
        ok, reason = self.ai.apply_action(self.bot, self.a, dict(operation="politics", target=self.b.id, action="war"))
        self.assertFalse(ok)
        self.assertIn("Дивизии", reason)
        front = game.hex_lookup[6, 5]
        for d in self.a.divisions:
            d.tile, d.path = front, []
        game.create_air_defense_unit(self.a, front, "manpads_team")
        for resource, amount in self.ai.military_reserve(self.a).items():
            game.add_to_stockpile_unsafe(self.a, resource, amount)
        ok, reason = self.ai.apply_action(self.bot, self.a, dict(operation="politics", target=self.b.id, action="war"))
        self.assertTrue(ok, reason)
