import contextlib
from collections import defaultdict
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from headless_simulation import HeadlessGame
from simulate_ai import run, audit_world


class HeadlessTests(unittest.TestCase):
    def game(self, seed=1):
        with contextlib.redirect_stdout(io.StringIO()):
            return HeadlessGame(seed, countries=4, map_size=32)

    def test_production_cache_reuses_tiles_and_refreshes_after_damage(self):
        game = self.game()
        player = game.players[0]
        tile = player.capital_tile
        tile.building_coverage["farms"] = 1.0
        game.recalculate_state_production_cache(player)
        game.recalculate_state_production_cache(player)
        with patch.object(game, "calculate_tile_production_cache", wraps=game.calculate_tile_production_cache) as calculate:
            original = game.production_amount_for_key(player, "food", "outputs")
            game.recalculate_state_production_cache(player)
            calculate.assert_not_called()
            game.set_building_health(tile, "farms", .5)
            game.recalculate_state_production_cache(player)
            calculate.assert_called_once_with(player, tile)
            self.assertLess(game.production_amount_for_key(player, "food", "outputs"), original)

    def test_fort_repair_does_not_recalculate_unrelated_country_caches(self):
        game = self.game()
        player = game.players[0]
        tile = player.capital_tile
        tile.building_coverage["fortification"] = 1.0
        game._defer_building_refresh = True
        game._building_refresh_pending = {}
        with patch.object(game, "recalculate_state_production_cache") as production, \
             patch.object(game, "recalculate_player_supply") as supply, \
             patch.object(game, "distribute_player_stockpiles_to_tiles") as storage:
            game.damage_building(tile, "fortification", .2, queue_repair=False)
            game.flush_building_refreshes()
            for refresh in (production, supply, storage):
                refresh.assert_not_called()
        self.assertAlmostEqual(game.building_health(tile, "fortification"), .8)

    def test_no_window_texture_sprite_or_text_and_all_countries_are_bots(self):
        with patch("arcade.Window", side_effect=AssertionError("window created")), \
             patch("arcade.load_texture", side_effect=AssertionError("texture loaded")), \
             patch("arcade.Sprite", side_effect=AssertionError("sprite created")), \
             patch("arcade.Text", side_effect=AssertionError("text created")), \
             patch("arcade.shape_list.ShapeElementList", side_effect=AssertionError("GL shapes created")):
            game = self.game()
            for _ in range(8):
                game.advance_day()
        self.assertEqual(len(game.ai_system.bots), 4)
        self.assertTrue(all(not p.is_human for p in game.players))
        self.assertEqual(game.politics.day, 8)

    def test_reproducible_reports_and_decisions(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            a = Path(directory) / "a"
            b = Path(directory) / "b"
            run(5, 8, 2, 16, a)
            run(5, 8, 2, 16, b)
            for name in ("news.txt", "decisions.jsonl", "daily.jsonl", "combat.jsonl"):
                self.assertEqual((a / "seed-5" / name).read_bytes(), (b / "seed-5" / name).read_bytes(), name)

    def test_ai_seed_changes_personality_without_changing_initial_world(self):
        with contextlib.redirect_stdout(io.StringIO()):
            a = HeadlessGame(1, countries=2, map_size=16, ai_seed=41)
            b = HeadlessGame(1, countries=2, map_size=16, ai_seed=42)
        self.assertEqual([(t.q, t.r, t.owner.id if t.owner else None, t.terrain_type) for t in a.hex_grid],
                         [(t.q, t.r, t.owner.id if t.owner else None, t.terrain_type) for t in b.hex_grid])
        self.assertNotEqual(a.ai_system.bots[0].aggression, b.ai_system.bots[0].aggression)

    def test_border_fixture_produces_actual_battles(self):
        game = self.game()
        game.setup_border_war()
        for _ in range(12):
            game.advance_day()
        self.assertGreater(game.battles_started, 0)
        self.assertTrue(any(r.get("operation") == "attack" and r.get("accepted")
                            for bot in game.ai_system.bots.values() for r in bot.history))
        rejected = [r for bot in game.ai_system.bots.values() for r in bot.history
                    if r.get("operation") == "withdraw" and not r.get("accepted")]
        self.assertFalse(rejected)

    def test_own_preparation_does_not_frighten_bot_into_abandoning_it(self):
        game = self.game()
        player, target = game.players[:2]
        bot = game.ai_system.bots[player.id]
        border = next(n for tile in player.tiles for n in game.neighbor_tiles(tile)
                      if n.owner is None and not game.is_water_tile(n))
        game.set_tile_owner_only(border, target)
        bot.course, bot.target_id = "war_preparation", target.id
        game.politics.war_goals[player.id, target.id] = 30
        game.politics.relation(player.id, target.id).crisis_level = 40
        game.ai_system.military_report(bot, player)
        game.ai_system.military_report(bot, target)
        options = game.ai_system.course_candidates(bot, player)
        self.assertIn("war_preparation", options)
        game.ai_system.select_course(bot, player, options)
        self.assertEqual(bot.course, "war_preparation")

    def test_actual_neighbor_with_legacy_distance_two_is_valid_retreat(self):
        game = self.game()
        player = game.players[0]
        pair = next((tile, n) for tile in player.tiles for n in game.neighbor_tiles(tile)
                    if n.owner is player and not game.is_water_tile(n) and game.hex_distance(tile, n) != 1)
        division = player.divisions[0]
        division.tile, division.path, division.battle_id = pair[0], [], None
        game.ai_system.send(game.ai_system.bots[player.id], "withdraw", division_id=division.id,
                            tile_key=game.tile_key(pair[1]))
        game.simulation_server.process_pending_commands()
        self.assertEqual(division.route_mode, "retreat")
        self.assertIs(division.target_tile, pair[1])

    def test_repeated_move_preserves_progress(self):
        game = self.game()
        player = game.players[0]
        division = player.divisions[0]
        target = next(t for t in game.neighbor_tiles(division.tile)
                      if t.owner is player and not game.is_water_tile(t))
        bot = game.ai_system.bots[player.id]
        game.ai_system.send(bot, "move", division_id=division.id, tile_key=game.tile_key(target))
        game.simulation_server.process_pending_commands()
        division.movement_progress = .37
        game.ai_system.send(bot, "move", division_id=division.id, tile_key=game.tile_key(target))
        game.simulation_server.process_pending_commands()
        self.assertEqual(division.movement_progress, .37)
        self.assertTrue(division.path)

    def test_world_audit_detects_corrupt_state(self):
        game = self.game()
        audit_world(game)
        game.players[0].budget = float("nan")
        with self.assertRaisesRegex(RuntimeError, "non-finite budget"):
            audit_world(game)
        game.players[0].budget = 100
        division = game.divisions[0]
        division.battle_id = -100
        with self.assertRaisesRegex(RuntimeError, "dangling battle"):
            audit_world(game)

    def test_capturing_air_defense_position_removes_enemy_asset(self):
        game = self.game()
        defender = next(p for p in game.players if p.air_defense_units)
        attacker = next(p for p in game.players if p is not defender)
        unit = defender.air_defense_units[0]
        tile = unit.tile
        self.assertTrue(game.transfer_tile_owner(tile, attacker))
        self.assertNotIn(unit, game.air_defense_units)
        self.assertNotIn(unit, defender.air_defense_units)
        self.assertNotIn(unit.id, game.air_defense_unit_lookup)
        self.assertIs(tile.owner, attacker)
        audit_world(game)

    def test_tactical_deployment_preserves_in_progress_route(self):
        game = self.game()
        game.setup_border_war()
        player = game.players[0]
        bot = game.ai_system.bots[player.id]
        division = player.divisions[-1]
        target = next(t for t in player.tiles if t is not division.tile
                      and any(n.owner and game.countries_hostile(player, n.owner) for n in game.neighbor_tiles(t))
                      and game.find_division_path(division, t))
        self.assertTrue(game.issue_division_plan_order(division, target))
        division.movement_progress = .37
        division.organization = division.max_organization
        division.last_supply_ratio = 1
        with patch.object(game.ai_system, "nearby_enemies", return_value=[]):
            game.ai_system.tactical(bot, player)
            game.simulation_server.process_pending_commands()
        self.assertIs(division.target_tile, target)
        self.assertEqual(division.movement_progress, .37)

    def test_attack_cancellation_evaluates_whole_committed_group(self):
        game = self.game()
        game.setup_border_war()
        player, opponent = game.players[:2]
        bot = game.ai_system.bots[player.id]
        target = opponent.capital_tile
        group = player.divisions[:2]
        for division in group:
            division.path = [target]
            division.target_tile = target
            division.route_mode = "attack"
            division.organization = division.max_organization
            division.last_supply_ratio = 1
        game.ai_system.units_by_tile = defaultdict(list, {
            game.tile_key(target): [SimpleNamespace(owner=opponent)]})
        with patch("ai_system.division_vector", return_value={"attack": 10, "defense": 15}), \
             patch.object(game.ai_system, "nearby_enemies", return_value=[]), \
             patch.object(game.ai_system, "send") as send:
            game.ai_system.tactical(bot, player)
        cancelled = [c for c in send.call_args_list if c.args[1] == "move"
                     and c.kwargs.get("division_id") in {d.id for d in group}]
        self.assertFalse(cancelled)
