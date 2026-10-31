"""Run with RUN_ARCADE_TESTS=1; these exercise the real game and command adapters."""

import os
import random
import unittest


@unittest.skipUnless(os.environ.get("RUN_ARCADE_TESTS") == "1", "requires an Arcade/OpenGL window")
class AIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import arcade
        cls.window = arcade.Window(1280, 800, visible=False)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def setUp(self):
        from MainGame import Game
        random.seed(103)
        self.game = Game(bot_count=3, map_size=32)
        self.window.show_view(self.game)

    def test_staged_reviews_execute_real_actions_and_keep_human_state_unassigned(self):
        game = self.game
        game.simulation_server.set_paused(False)
        game.simulation_server.set_speed_level(5)
        for _ in range(18):
            game.on_update(.25)
        self.assertEqual(game.politics.day, 18)
        self.assertEqual(len(game.ai_system.bots), 3)
        for bot in game.ai_system.bots.values():
            self.assertEqual(len(bot.reports), 4)
            self.assertTrue(bot.regions)
            self.assertTrue(any(h["kind"] == "command" and h["accepted"] for h in bot.history))
            stage_times = [h["hour"] for h in bot.history if h["kind"] == "review_stage"]
            self.assertGreater(len(set(stage_times)), 5)
        self.assertNotIn(game.human_player.id, game.ai_system.bots)

    def test_division_designer_and_recruitment_panel_commands(self):
        import arcade
        from pathlib import Path
        game = self.game
        game.open_top_panel("military")
        game.side_panel_progress = game.side_panel_target = 1
        game.initialize_division_panel()
        game.division_panel_tab = "designer"
        game.division_draft = {"basic_infantry": 6, "tank": 4}
        game.division_name_focused = True
        game.on_key_press(arcade.key.A, arcade.key.MOD_CTRL)
        game.on_text("Смешанная тестовая")
        self.assertEqual(game.division_design_name, "Смешанная тестовая")
        game.division_name_focused = False
        game.on_draw()
        Path("logs").mkdir(exist_ok=True)
        arcade.get_image().save("logs/recruitment-designer.png")
        rect = next(rect for rect, action, value in game.division_panel_hits if action == "save")
        self.assertTrue(game.handle_division_panel_click(rect[0] + 5, rect[1] + 5))
        self.assertEqual(game.division_panel_tab, "recruit")
        self.assertTrue(game.division_panel_key.startswith("design-"))
        template = game.division_template(game.division_panel_key)
        cost = game.recruitment.quote(template)
        player = game.human_player
        player.manpower_reserve = cost["manpower"] * 2
        for key, amount in cost["equipment"].items():
            game.add_to_stockpile_unsafe(player, key, amount)
        game.selected_tile = None
        game.on_draw()
        from unittest.mock import patch
        site = game.recruitment.site(player)
        rect = next(rect for rect, action, value in game.division_panel_hits if action == "site")
        game.on_mouse_press(rect[0] + 5, rect[1] + 5, arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertTrue(game.division_site_pick_mode)
        with patch.object(game, "get_tile_at", return_value=site):
            game.on_mouse_press(700, 450, arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertFalse(game.division_site_pick_mode)
        self.assertEqual(game.division_deployment_key, game.tile_key(site))
        self.assertFalse(game.division_selection_drag_active)
        game.on_draw()
        rect = next(rect for rect, action, value in game.division_panel_hits if action == "recruit")
        game.handle_division_panel_click(rect[0] + 5, rect[1] + 5)
        self.assertEqual(len(game.recruitment.queues[player.id]), 1)
        self.assertEqual(game.recruitment.queues[player.id][0]["tile_key"], game.tile_key(site))
        game.on_draw()
        arcade.get_image().save("logs/recruitment-queue.png")

    def test_deployment_picker_rejects_enemy_hex_and_escape_cancels(self):
        import arcade
        from unittest.mock import patch
        game = self.game
        game.open_top_panel("military")
        game.side_panel_progress = game.side_panel_target = 1
        game.initialize_division_panel()
        game.division_panel_tab = "recruit"
        game.on_draw()
        rect = next(rect for rect, action, value in game.division_panel_hits if action == "site")
        game.on_mouse_press(rect[0] + 5, rect[1] + 5, arcade.MOUSE_BUTTON_LEFT, 0)
        enemy = game.players[1].capital_tile
        with patch.object(game, "get_tile_at", return_value=enemy):
            game.on_mouse_press(700, 450, arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertTrue(game.division_site_pick_mode)
        self.assertIsNone(game.division_deployment_key)
        game.on_key_press(arcade.key.ESCAPE, 0)
        self.assertFalse(game.division_site_pick_mode)
        self.assertEqual(game.side_panel_target, 1)
        self.assertIsNone(game.division_deployment_key)

    def test_build_duplicate_and_untrusted_command_are_rejected(self):
        from simulation_core import SimulationCommand
        game = self.game
        player = game.players[1]
        bot = game.ai_system.bots[player.id]
        tile = next(t for t in player.tiles if game.construction_tile_block_reason(player, t, "warehouse") is None)
        player.budget = 1_000_000_000
        cost = game.construction_cost(player, tile, "warehouse")
        for key, amount in cost["resource_costs"].items():
            game.add_to_stockpile(player, key, amount * 4)
        before = len(player.construction_queue)
        payload = dict(building="warehouse", tile_key=game.tile_key(tile))
        game.ai_system.send(bot, "build", **payload)
        game.ai_system.send(bot, "build", **payload)
        game.simulation_server.process_pending_commands()
        self.assertEqual(len(player.construction_queue), before + 1)
        self.assertFalse(game.simulation_server.apply_command(SimulationCommand("ai_action", player.id,
            dict(operation="build", **payload))))

    def test_tactical_escape_does_not_wait_for_weekly_review(self):
        from ai_models import division_vector
        from collections import defaultdict
        game = self.game
        player, enemy = game.players[1:3]
        bot = game.ai_system.bots[player.id]
        division = player.divisions[0]
        tile = next(t for t in player.tiles if sum(n.owner is player and not game.is_water_tile(n) for n in game.neighbor_tiles(t)) >= 3)
        division.tile = tile
        division.organization = 10
        division.path = []
        division.battle_id = None
        division.route_mode = "move"
        neighbors = [n for n in game.neighbor_tiles(tile) if n.owner is player and not game.is_water_tile(n)]
        hostile_tile = neighbors[0]
        game.set_tile_owner_only(hostile_tile, enemy)
        hostile = enemy.divisions[0]
        hostile.tile = hostile_tile
        game.politics.relation(player.id, enemy.id).at_war = True
        ai = game.ai_system
        ai.units_by_tile = defaultdict(list)
        for unit in game.divisions:
            ai.units_by_tile[game.tile_key(unit.tile)].append(unit)
        ai.tactical(bot, player)
        game.simulation_server.process_pending_commands()
        self.assertEqual(division.route_mode, "retreat")
        self.assertIs(division.target_tile.owner, player)
        self.assertTrue(any(h["kind"] == "command" and h.get("operation") == "withdraw" and h["accepted"] for h in bot.history))

    def test_human_country_can_be_target_zero(self):
        game = self.game
        player = game.players[1]
        bot = game.ai_system.bots[player.id]
        bot.course, bot.target_id = "war_preparation", 0
        game.politics.reason = lambda *args: None
        game.ai_system.diplomatic_tasks(bot, player)
        self.assertTrue(any(t.kind == "politics" and t.payload["target"] == 0 and t.payload["action"] == "justify" for t in bot.tasks))

    def test_real_war_preparation_and_combat_runtime(self):
        game = self.game
        player, enemy = game.players[1], game.players[0]
        bot = game.ai_system.bots[player.id]
        bot.course, bot.target_id, bot.next_monthly = "war_preparation", enemy.id, 10000
        success, reason = game.politics.execute(player.id, enemy.id, "justify")
        self.assertTrue(success, reason)
        tile = next(t for t in player.tiles if sum(n.owner is player and not game.is_water_tile(n) for n in game.neighbor_tiles(t)) >= 3)
        target = next(n for n in game.neighbor_tiles(tile) if n.owner is player and not game.is_water_tile(n))
        game.set_tile_owner_only(target, enemy)
        enemy.divisions[0].tile = target
        player.divisions[0].tile = tile
        server = game.simulation_server
        server.set_paused(False)
        server.set_speed_level(5)
        for _ in range(48):
            game.on_update(.25)
        self.assertTrue(game.countries_hostile(player, enemy))
        self.assertTrue(any(h["kind"] == "command" and h.get("operation") in ("move", "attack", "withdraw") for h in bot.history))

    def test_batched_budget_forecast_matches_individual_forecasts(self):
        game = self.game
        for player in game.players:
            game.adjust_trade_contract(player, "food", "buy", 500)
        expected = [game.estimate_monthly_trade_flows(p)["money_balance"] for p in game.players]
        game.recalculate_all_monthly_balances()
        self.assertEqual(expected, [p.monthly_trade_balance for p in game.players])
        self.assertIsNone(game._trade_forecast_batch)

    def test_air_task_configures_wings_even_when_sam_needs_moving(self):
        game = self.game
        player = game.players[1]
        ai = game.ai_system
        region = next(iter(ai.controlled(player)))
        for wing in player.air_wings:
            wing.enabled_missions = []
        ai.send(ai.bots[player.id], "air", region_id=region)
        game.simulation_server.process_pending_commands()
        self.assertTrue(any(w.enabled_missions and w.operation_area_tile_keys for w in player.air_wings))
