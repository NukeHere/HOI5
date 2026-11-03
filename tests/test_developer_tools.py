import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from simulation_core import LocalSimulationServer


class FrameBudgetTests(unittest.TestCase):
    def test_slow_step_does_not_run_sixteen_catchup_steps(self):
        server = LocalSimulationServer()
        server.set_paused(False)
        server.set_speed_level(5)
        steps = []
        with patch("simulation_core.time.perf_counter", side_effect=[0, .2]):
            server.update(5, steps.append, max_wall_seconds=.008)
        self.assertEqual(steps, [6])
        self.assertGreater(server.accumulator, 0)
        self.assertLessEqual(server.accumulator, .5)
        server.set_paused(True)
        self.assertEqual(server.accumulator, 0)

    def test_unbudgeted_server_keeps_exact_game_time(self):
        server = LocalSimulationServer()
        server.set_paused(False)
        server.set_speed_level(5)
        steps = []
        server.update(.25, steps.append)
        self.assertEqual(sum(steps), 24)


class WorkerProcessTests(unittest.TestCase):
    def test_parallel_generation_equals_sequential_and_preserves_order(self):
        from map_generation_job import MapGenerationJob, generate_strip
        job = MapGenerationJob(8, 1729, workers=2)
        try:
            deadline = time.monotonic() + 20
            result = None
            while result is None and time.monotonic() < deadline:
                result = job.poll()
                time.sleep(.01)
            self.assertIsNotNone(result)
            self.assertEqual(result, generate_strip(8, 8, 1729, 0, 8))
        finally:
            job.close()

    def test_macro_worker_returns_same_result_without_live_game_objects(self):
        from ai_workers import AIPlanningWorkers, best_supply_site, regional_profiles
        workers = AIPlanningWorkers()
        try:
            supply = ([((0, 0), 3, .8, .1)], [((1, 0), .9, 1), ((7, 0), .9, 1)], 7, .78)
            regions = ([((0, 0), 1, 1000, .5, {"industry": .2}, {"food": 10}, True, ((1, 0),)),
                        ((1, 0), 1, 2000, .6, {}, {}, False, ((0, 0),))], 2, (0, 0))
            for key, function, data in (("supply", best_supply_site, supply), ("regions", regional_profiles, regions)):
                result = None
                deadline = time.monotonic() + 20
                while result is None and time.monotonic() < deadline:
                    result = workers.request(key, function, data, 0)
                    time.sleep(.01)
                self.assertEqual(result, function(data), workers.errors)
            self.assertNotEqual(next(iter(workers.executor._processes.values())).pid, os.getpid())
        finally:
            workers.close()


@unittest.skipUnless(os.environ.get("RUN_ARCADE_TESTS") == "1", "requires Arcade/OpenGL")
class DeveloperGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import arcade
        cls.window = arcade.Window(1920, 1080, visible=False)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def setUp(self):
        from MainGame import Game
        self.game = Game(bot_count=3, map_size=32, world_seed=146591)
        self.window.show_view(self.game)
        self.game.simulation_server.set_paused(True)

    def tearDown(self):
        self.game.stop_background_services()

    def test_f4_shows_recorded_reasons_and_does_not_mutate_politics(self):
        import arcade
        from ai_debug_panel import inspection_rows
        game = self.game
        bot = game.ai_system.bots[1]
        player = game.players[1]
        for other in game.players:
            game.ai_system.military_report(bot, other)
            game.ai_system.economy_report(bot, other)
        options = game.ai_system.course_candidates(bot, player)
        game.ai_system.select_course(bot, player, options)
        game.ai_system.economic_tasks(bot, player)
        before = len(game.politics.relations), game.politics.revision
        rows = inspection_rows(game, 1, 0)
        self.assertTrue(any("разведданные" in row for row in rows))
        self.assertTrue(any("реальные приказы" in row for row in rows))
        self.assertEqual(before, (len(game.politics.relations), game.politics.revision))
        game.on_key_press(arcade.key.F4, 0)
        self.assertTrue(game.ai_debug_panel.open)
        game.on_draw()
        count = len(game.ai_debug_panel.labels)
        for _ in range(5):
            game.ai_debug_panel.select(game, 1)
            game.on_draw()
        self.assertEqual(len(game.ai_debug_panel.labels), count)
        Path("logs/diagnostics/performance-2026-11-03").mkdir(parents=True, exist_ok=True)
        arcade.get_image().save("logs/diagnostics/performance-2026-11-03/f4-panel.png")

    def test_expanded_layers_receive_clicks_over_news_popup(self):
        import arcade
        from Constants import MAP_LAYERS
        game = self.game
        game.politics.news.notice(0, game.human_player, "test_popup", "Проверка новости", "Тест слоя", important=True)
        news = game.news_visible_items()[-1]
        for layer in ("supply", "resources", "terrain"):
            game.news_popup_id = news.id
            game.map_layer_menu_open = True
            game.map_layer_menu_progress = 1
            game.on_draw()
            index = next(i for i, row in enumerate(MAP_LAYERS) if row[0] == layer)
            x, y, w, h = game.map_layer_option_rects()[index]
            game.on_mouse_press(x + w / 2, y + h / 2, arcade.MOUSE_BUTTON_LEFT, 0)
            self.assertEqual(game.map_layer, layer)

    def test_destroyed_depot_reduces_actual_supply_on_tile_and_neighbors(self):
        game = self.game
        player = game.players[1]
        for tile in player.tiles:
            tile.building_coverage = {}
            tile.building_health = {}
        target = max((t for t in player.tiles if not game.is_water_tile(t)),
                     key=lambda t: game.hex_distance(t, player.capital_tile))
        target.building_coverage["supply_depot"] = 1
        game.recalculate_player_supply(player)
        old = target.supply_score
        neighbors = [(tile, tile.supply_score) for tile in game.neighbor_tiles(target) if tile.owner is player]
        game.damage_building(target, "supply_depot", 1, queue_repair=False)
        self.assertEqual(game.building_health(target, "supply_depot"), 0)
        self.assertLess(target.supply_score, old)
        self.assertTrue(any(tile.supply_score < score for tile, score in neighbors))

    def test_step_coverage_cache_invalidates_when_health_changes(self):
        game = self.game
        player = game.players[1]
        target = player.capital_tile
        target.building_coverage["warehouse"] = 1
        game._coverage_step_cache = {}
        old = game.effective_coverage_totals(player)["warehouse"]
        game.set_building_health(target, "warehouse", 0)
        self.assertLess(game.effective_coverage_totals(player)["warehouse"], old)
        expected = sum(game.tile_storage_capacity_by_category(tile)["raw"] for tile in player.tiles)
        capacity, _, _ = game.recalculate_player_storage(player)
        self.assertAlmostEqual(capacity["raw"], expected * player.production_modifiers.get("storage_efficiency", 1))

    def test_menu_generates_in_processes_and_stops_music_before_start(self):
        import arcade
        from MainMenu import MainMenuView
        menu = MainMenuView()
        self.window.show_view(menu)
        menu.map_size_index = 0
        menu.bot_count_index = 0
        try:
            menu.start_new_game()
            self.assertIsNone(menu.music)
            self.assertIsNotNone(menu.generation_job)
            job = menu.generation_job
            menu.on_key_press(arcade.key.ESCAPE, 0)
            self.assertIs(menu.generation_job, job)
            menu.on_draw()
            deadline = time.monotonic() + 30
            while self.window.current_view is menu and time.monotonic() < deadline:
                menu.on_update(1 / 60)
                self.window.dispatch_events()
                time.sleep(.01)
            self.assertIsNot(self.window.current_view, menu, menu.message)
            self.assertEqual(self.window.current_view.map_size, 50)
            self.assertEqual(len(self.window.current_view.hex_grid), 2500)
        finally:
            menu.stop_menu()
            current = self.window.current_view
            if current is not menu:
                current.stop_background_services()

    def test_neutral_resource_need_is_scored_and_recorded_on_task(self):
        from ai_models import Estimate
        game = self.game
        ai = game.ai_system
        player = game.players[1]
        bot = ai.bots[1]
        report = ai.economy_report(bot, player)
        report.economy["test_ore"] = {key: Estimate(value, value, value, ai.hour)
            for key, value in {"required": 100, "capacity": 0, "stock": 0}.items()}
        target = next(n for tile in player.tiles for n in game.neighbor_tiles(tile)
                      if n.owner is None and not game.is_water_tile(n))
        target.resources = [("test_ore", 1, 1_000_000)]
        ai.economic_tasks(bot, player)
        candidate = next(row for row in bot.expansion_candidates if row["tile"] == game.tile_key(target))
        self.assertGreater(candidate["resources"]["test_ore"], 0)
        claim = next(task for task in bot.tasks if task.kind == "claim")
        self.assertIn("Нейтральная клетка", claim.motivation)

    def test_multiple_repairs_flush_country_only_once(self):
        game = self.game
        player = game.players[1]
        tile = player.capital_tile
        tile.building_coverage["supply_depot"] = 1
        game._defer_building_refresh = True
        game._building_refresh_pending = {}
        try:
            with patch.object(game, "recalculate_player_supply", wraps=game.recalculate_player_supply) as supply:
                game.damage_building(tile, "supply_depot", .1, queue_repair=False)
                game.damage_building(tile, "supply_depot", .1, queue_repair=False)
                self.assertEqual(supply.call_count, 0)
                game.flush_building_refreshes()
                self.assertEqual(supply.call_count, 1)
        finally:
            game._defer_building_refresh = False

    def test_camera_pan_reuses_counter_mesh_and_keeps_click_targets_aligned(self):
        game = self.game
        game.world_camera.zoom = .1
        game.rebuild_division_groups()
        group = next(group for group in game.division_groups if group["divisions"][0].owner is game.human_player)
        shapes = group["mesh"]
        original = group["rect"]
        x, y = game.world_camera.position
        game.world_camera.position = (x + 4, y)
        game.rebuild_division_groups()
        self.assertIn(group, game.division_groups)
        self.assertIs(shapes, group["mesh"])
        self.assertAlmostEqual(group["rect"][0], original[0] - .4)
        self.assertAlmostEqual(group["rect"][1], original[1])
        gx, gy, width, height = group["rect"]
        self.assertTrue(game.handle_division_click(gx + width / 2, gy + height / 2, 0))
        self.assertEqual(game.selected_division_ids, {d.id for d in group["divisions"]})

    def test_news_hover_space_middle_drag_and_escape_keep_responding(self):
        import arcade
        game = self.game
        game.politics.news.notice(0, game.human_player, "input_stress", "Проверка ввода", "Описание новости. " * 80, important=True)
        news = game.news_visible_items()[-1]
        for _ in range(20):
            game.news_archive_open = False
            game.news_popup_id = news.id
            x, y, width, height = game.news_popup_rect()
            x, y = x + width / 2, y + height / 2
            game.on_mouse_motion(x, y, 0, 0)
            self.assertIsNone(game.hovered_tile)
            game.on_mouse_press(x, y, arcade.MOUSE_BUTTON_MIDDLE, 0)
            self.assertFalse(game.is_dragging)
            game.on_mouse_drag(x + 20, y, 20, 0, arcade.MOUSE_BUTTON_MIDDLE, 0)
            game.on_mouse_release(x + 20, y, arcade.MOUSE_BUTTON_MIDDLE, 0)
            game.on_key_press(arcade.key.SPACE, 0)
            game.on_update(1 / 60)
            game.on_draw()
            game.on_key_press(arcade.key.ESCAPE, 0)
            self.assertTrue(game.paused)
            game.on_draw()
            game.on_key_press(arcade.key.ESCAPE, 0)
            self.assertFalse(game.paused)
            game.is_dragging = True
            game.on_input_deactivate()
            self.assertFalse(game.is_dragging)
