"""Run with RUN_ARCADE_TESTS=1 on a machine with an OpenGL display."""

import os
import random
import unittest


@unittest.skipUnless(os.environ.get("RUN_ARCADE_TESTS") == "1", "requires an Arcade/OpenGL window")
class CountryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import arcade
        from MainGame import Game
        cls.arcade = arcade
        cls.window = arcade.Window(1280, 800, visible=False)
        random.seed(1729)
        try:
            cls.game = Game(bot_count=1, map_size=32)
            cls.window.show_view(cls.game)
        except Exception:
            cls.window.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def setUp(self):
        from politics_system import PoliticalState
        self.a, self.b = self.game.players
        for player in (self.a, self.b):
            player.politics = PoliticalState()
            player.budget = 100_000_000
            player.trade_contracts.clear()
        self.game.initialize_politics()
        self.game.close_top_panel()
        self.game.update_side_panel_animation(1)
        self.game.close_hex_panel()
        self.game.set_selected_divisions([])
        self.game.trade_panel_cache = None
        self.game.recalculate_all_monthly_balances()

    def click(self, kind, value=None):
        self.game.update_side_panel_animation(1)
        self.game.on_draw()
        rect = next(rect for rect, k, v in self.game.country_card_hits if k == kind and (value is None or v == value))
        x, y, width, height = rect
        self.game.on_mouse_press(x + width / 2, y + height / 2, self.arcade.MOUSE_BUTTON_LEFT, 0)

    def test_card_open_edit_amount_confirm_and_escape(self):
        game = self.game
        game.on_draw()
        x, y, width, height = game.country_summary_rect
        game.on_mouse_press(x + width / 2, y + height / 2, self.arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertEqual(game.country_card_id, self.a.id)
        self.click("countries")
        self.click("country", self.b.id)
        self.click("tab", "actions")
        self.click("action", "aid")
        game.on_key_press(self.arcade.key.A, self.arcade.key.MOD_CTRL)
        game.on_text("123456")
        self.assertEqual(game.country_amount(), 123456)
        self.click("confirm", "aid")
        self.assertEqual(self.a.budget, 100_000_000 - 123456)
        self.assertEqual(self.b.budget, 100_000_000 + 123456)
        game.on_key_press(self.arcade.key.ESCAPE, 0)
        self.assertIsNone(game.country_card_id)

    def test_tax_and_program_affect_existing_budget(self):
        game = self.game
        previous = self.a.monthly_income_breakdown["companies"]
        game.submit_player_command("political_action", {"target": self.a.id, "action": "tax:smb:1"})
        self.assertAlmostEqual(self.a.monthly_income_breakdown["companies"], previous * 1.065)
        game.submit_player_command("political_action", {"target": self.a.id, "action": "support:large"})
        self.assertEqual(self.a.monthly_expenses_breakdown["political_programs"], 1_000_000)
        balance = self.a.budget
        from Constants import PRODUCTION_MONTH_HOURS
        self.game.advance_politics(PRODUCTION_MONTH_HOURS)
        game.run_economy_tick(self.a, PRODUCTION_MONTH_HOURS)
        self.assertAlmostEqual(self.a.budget - balance, self.a.monthly_balance, places=5)

    def test_program_duration_control_reaches_simulation(self):
        game = self.game
        game.open_country_card(self.a)
        game.open_country_dialog("action", "support:population")
        self.assertEqual(game.country_program_term, "ongoing")
        self.click("program_term", "week")
        self.click("confirm", "support:population")
        self.assertEqual(self.a.politics.programs["population"], game.politics.day + game.politics.hours / 24 + 7)
        game.advance_politics(72)
        self.assertIn("population", self.a.politics.programs)
        self.assertLess(self.a.politics.support["population"] - .61, .0015)

    def test_program_clock_matches_calendar_at_fast_speed(self):
        game = self.game
        server = game.simulation_server
        old_speed, old_paused = server.speed_level, server.paused
        start = server.current_time
        start_day, start_hours = game.politics.day, game.politics.hours
        game.submit_player_command("political_action", {"target": self.a.id, "action": "support:population", "program_term": "week"})
        try:
            server.accumulator = 0
            server.set_speed_level(5)
            server.set_paused(False)
            for _ in range(3):
                game.on_update(.25)
            hours = (server.current_time - start).total_seconds() / 3600
            self.assertEqual(hours, 72)
            self.assertEqual((game.politics.day - start_day) * 24 + game.politics.hours - start_hours, hours)
            self.assertIn("population", self.a.politics.programs)
        finally:
            server.set_speed_level(old_speed)
            server.set_paused(old_paused)

    def test_peace_war_gate_ground_and_air(self):
        game = self.game
        division = self.a.divisions[0]
        target = self.b.capital_tile
        self.assertFalse(game.division_can_capture_tile(division, target))
        self.assertFalse(game.air_mission_tile_is_hostile(self.a, target))
        game.submit_player_command("political_action", {"target": self.b.id, "action": "war"})
        self.assertTrue(game.division_can_capture_tile(division, target))
        self.assertTrue(game.air_mission_tile_is_hostile(self.a, target))
        game.submit_player_command("political_action", {"target": self.b.id, "action": "peace"})
        game.politics.resolve_offer(game.politics.pending[0], True)
        game.enforce_diplomatic_peace()
        self.assertFalse(game.division_can_capture_tile(division, target))
        self.assertFalse(game.air_mission_tile_is_hostile(self.a, target))

    def test_real_market_and_forecast_respect_embargo(self):
        game = self.game
        key = next(key for key in game.tradeable_resource_keys() if game.stockpile_amount(self.a, key) > 10)
        for player in (self.a, self.b):
            player.politics.external_access = False
        # Release enough real storage at the buyer for this transaction.
        for category in self.b.resource_stockpiles.values():
            for resource in category:
                category[resource] = 0
        game.mark_player_storage_dirty(self.b)
        self.a.trade_contracts = [{"resource": key, "mode": "sell", "amount": 10}]
        self.b.trade_contracts = [{"resource": key, "mode": "buy", "amount": 10}]
        self.assertGreater(game.estimate_monthly_trade_flows(self.b)["imports"].get(key, 0), 0)
        total_money = self.a.budget + self.b.budget
        total_stock = game.stockpile_amount(self.a, key) + game.stockpile_amount(self.b, key)
        game.run_weekly_market_tick()
        self.assertTrue(game.last_market_fills)
        self.assertAlmostEqual(self.a.budget + self.b.budget, total_money)
        self.assertAlmostEqual(game.stockpile_amount(self.a, key) + game.stockpile_amount(self.b, key), total_stock)
        game.submit_player_command("political_action", {"target": self.b.id, "action": "embargo"})
        self.assertFalse(game.estimate_monthly_trade_flows(self.b)["imports"])
        game.run_weekly_market_tick()
        self.assertFalse(game.last_market_fills)

    def test_country_details_and_context_actions(self):
        game = self.game
        game.open_country_card(self.a)
        self.click("tab", "summary")
        self.click("panel", "economy")
        self.assertEqual(game.active_top_panel_key, "economy")
        game.open_country_card(self.a)
        game.country_card_tab = "summary"
        self.click("tab", "population")
        self.assertEqual(game.country_card_tab, "summary")
        self.assertEqual(game.country_dialog, "population")
        self.assertIn("Военнообязанные", str(game.country_dialog_rows(self.a)))
        self.click("dialog_close")
        self.click("tab", "actions")
        self.assertEqual(len(game.country_rows(self.a)), 4)
        self.click("tab", "taxes")
        self.click("action", "tax:population:-1")
        self.click("confirm", "tax:population:-1")
        self.assertEqual(self.a.politics.taxes["population"], -1)
        self.assertEqual(game.country_dialog, "taxes")
        self.click("dialog_close")
        self.click("tab", "actions")
        self.click("tab", "programs")
        self.click("action", "support:population")
        self.click("confirm", "support:population")
        actions = [row.action for row in game.country_dialog_rows(self.a)]
        self.assertIn(("action", "stop:population"), actions)
        self.assertNotIn(("action", "support:population"), actions)
        self.click("action", "stop:population")
        self.click("confirm", "stop:population")
        self.assertNotIn("population", self.a.politics.programs)
        self.click("dialog_close")
        for key in ("exports", "external"):
            label = game.country_action_label(self.a, key)
            game.submit_player_command("political_action", {"target": self.a.id, "action": key})
            self.assertNotEqual(game.country_action_label(self.a, key), label)
        game.country_card_tab = "society"
        self.assertIn("Рабочие", str(game.country_rows(self.a)))
        self.assertIn("Националисты", str(game.country_rows(self.a)))
        game.on_draw()
        self.assertNotIn("Решение принято", [label.text for label in game.country_text_pool])
        game.country_card_tab = "budget"
        game.open_country_card(self.b)
        self.assertEqual(game.country_card_tab, "summary")
        self.assertIn("Военная угроза", str(game.country_rows(self.b)))

    def test_country_dialog_preserves_tab_scroll_and_map(self):
        game = self.game
        game.open_country_card(self.a)
        game.country_card_tab = "summary"
        game.country_card_scroll = 2
        game.open_country_dialog("population")
        zoom = game.world_camera.zoom
        game.on_mouse_scroll(self.window.width - 5, 200, 0, -2)
        self.assertEqual(game.world_camera.zoom, zoom)
        game.on_mouse_press(self.window.width - 5, 200, self.arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertEqual(game.country_dialog, "population")
        game.on_key_press(self.arcade.key.ESCAPE, 0)
        self.assertIsNone(game.country_dialog)
        self.assertEqual(game.country_card_tab, "summary")
        self.assertEqual(game.country_card_scroll, 2)
        self.assertEqual(game.country_card_id, self.a.id)

    def test_export_slider_is_applied_only_on_confirmation(self):
        game = self.game
        game.open_country_card(self.a)
        game.open_country_dialog("action", "exports")
        game.update_side_panel_animation(1)
        game.on_draw()
        rect = next(rect for rect, kind, _ in game.country_dialog_hits if kind == "export_slider")
        x, y, width, height = rect
        game.on_mouse_press(x + width * .25, y + height / 2, self.arcade.MOUSE_BUTTON_LEFT, 0)
        game.on_mouse_release(x + width * .25, y + height / 2, self.arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertEqual(game.country_export_percent, 25)
        self.assertEqual(self.a.politics.export_capacity_factor, 1)
        before = game.trade_capacity_per_month(self.a, "sell")
        self.click("confirm", "exports")
        self.assertEqual(self.a.politics.export_capacity_factor, .25)
        self.assertAlmostEqual(game.trade_capacity_per_month(self.a, "sell"), before * .25)
        self.assertIsNone(game.country_dialog)

    def test_country_idle_text_is_not_relaid_out_and_views_are_reused(self):
        from unittest.mock import patch
        from contextlib import ExitStack
        game = self.game
        game.open_country_card(self.a)
        game.country_card_tab = "society"
        game.update_side_panel_animation(1)
        game.on_draw()
        pool = game.country_text_pool
        with ExitStack() as stack:
            updates = [stack.enter_context(patch.object(label.label, "end_update", wraps=label.label.end_update)) for label in pool]
            game.on_draw()
            self.assertEqual(sum(mock.call_count for mock in updates), 0)
        game.country_card_tab = "summary"
        game.on_draw()
        game.country_card_tab = "society"
        game.on_draw()
        self.assertIs(game.country_text_pool, pool)
        game.open_country_dialog("power")
        game.on_draw()
        modal_pool = game.country_dialog_views[("power", None)][1]
        with ExitStack() as stack:
            updates = [stack.enter_context(patch.object(label.label, "end_update", wraps=label.label.end_update)) for label in modal_pool]
            game.on_draw()
            self.assertEqual(sum(mock.call_count for mock in updates), 0)

    def test_country_navigation_does_not_rebuild_inactive_resource_map(self):
        from unittest.mock import patch
        game = self.game
        game.open_top_panel("resources")
        game.selected_resource_key = "coal"
        with patch.object(game, "create_map_overview") as overview, patch.object(game, "refresh_visible_tiles"):
            game.open_top_panel("politics")
            self.assertEqual(overview.call_count, 1)
            game.open_top_panel("diplomacy")
            game.open_country_card(self.b)
            game.open_top_panel("economy")
            self.assertEqual(overview.call_count, 1)

    def test_population_forecast_matches_growth_without_mutating_tiles(self):
        from unittest.mock import patch
        game = self.game
        before = [tile.population for tile in self.a.tiles]
        with patch.object(game, "population_growth_multiplier", return_value=1):
            forecast = game.population_monthly_forecast(self.a)
        self.assertEqual(before, [tile.population for tile in self.a.tiles])
        try:
            actual = game.apply_positive_population_growth(self.a, 1, 1)
            self.assertAlmostEqual(forecast, actual)
        finally:
            for tile, population in zip(self.a.tiles, before):
                tile.population = population
            game.sync_player_population_from_tiles(self.a)

    def test_country_dialog_bounds_scrolling_and_bounded_text_cache(self):
        from politics_system import ACTIONS
        game = self.game
        game.open_country_card(self.a)
        try:
            for width, height in ((1280, 800), (800, 600)):
                self.window.set_size(width, height)
                game.update_side_panel_animation(1)
                for section in ("population", "power", "support", "taxes", "programs"):
                    game.open_country_dialog(section)
                    for scroll in (0, 88, 10000):
                        game.country_dialog_scroll = scroll
                        game.on_draw()
                        x, y, w, h = game.country_dialog_rect()
                        for rect, _, _ in game.country_dialog_hits:
                            self.assertGreaterEqual(rect[0], x)
                            self.assertGreaterEqual(rect[1], y)
                            self.assertLessEqual(rect[0] + rect[2], x + w)
                            self.assertLessEqual(rect[1] + rect[3], y + h)
                        for label in game.country_dialog_views[(section, None)][1]:
                            if label.text:
                                left = label.x - (label.content_width if label.anchor_x == "right" else label.content_width / 2 if label.anchor_x == "center" else 0)
                                self.assertGreaterEqual(left, x)
                                self.assertLessEqual(left + label.content_width, x + w)
                    game.close_country_dialog()
            for key, action in ACTIONS.items():
                if action.domestic:
                    game.open_country_dialog("action", key)
                    game.on_draw()
                    game.close_country_dialog()
            self.assertLessEqual(len(game.country_dialog_views), 16)
        finally:
            game.close_country_dialog()
            self.window.set_size(1280, 800)

    def test_trade_country_summary_and_all_detail_views_render(self):
        game = self.game
        self.a.trade_contracts = [{"resource": "coal", "mode": "buy", "amount": 100}]
        self.a.trade_contract_revision += 1
        game.submit_player_command("political_action", {"target": self.a.id, "action": "external"})
        game.open_country_card(self.a)
        game.country_card_tab = "trade"
        rows = game.country_rows(self.a)
        self.assertIn("Не исполняется", str(rows))
        self.assertIn(("panel", "trade"), [action for _, action in rows])
        for section in ("summary", "budget", "population", "society", "trade", "power", "taxes", "programs"):
            game.country_card_tab = section
            game.update_side_panel_animation(1)
            game.on_draw()
            self.assertGreater(game.country_text_cursor, 0)

    def test_hover_tooltips_draw_after_country_and_trade_panels(self):
        from unittest.mock import patch
        game = self.game
        for panel in ("politics", "diplomacy", "trade"):
            for hover in ("hovered_budget_summary", "hovered_population_summary"):
                game.open_top_panel(panel)
                game.update_side_panel_animation(1)
                game.on_draw()
                rect = game.budget_summary_rect if hover == "hovered_budget_summary" else game.population_summary_rect
                game.on_mouse_motion(rect[0] + 5, rect[1] + 5, 0, 0)
                self.assertTrue(getattr(game, hover))
                calls = []
                with patch.object(game, "draw_country_card", side_effect=lambda: calls.append("country")), \
                     patch.object(game, "draw_side_panel", side_effect=lambda: calls.append("side")), \
                     patch.object(game, "draw_top_hover_tooltips", side_effect=lambda: calls.append("tooltip")):
                    game.on_draw()
                self.assertGreater(calls.index("tooltip"), calls.index("country"))
                self.assertGreater(calls.index("tooltip"), calls.index("side"))
                setattr(game, hover, False)

    def test_resource_card_renders_production_and_consumption_after_click(self):
        from unittest.mock import patch

        game = self.game
        game.open_top_panel("resources")
        game.update_side_panel_animation(1)
        game.on_draw()
        rows = game.resource_rows()
        key = game.visible_resource_rows(rows)[0]["key"]
        x, y, width, height = game.resource_row_rects(rows)[0]
        game.on_mouse_press(x + width / 2, y + height / 2, self.arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertEqual(game.selected_resource_key, key)
        category = game.resource_category_for_key(key)
        entry = {
            "production": 100,
            "consumption": 50,
            "production_breakdown": [("Production source " * 6, 100, 100)],
            "consumption_breakdown": [("Consumption source " * 6, 50, 100)],
        }
        with patch.object(game, "cached_resource_balance_breakdown", return_value={category: {key: entry}}):
            game.on_draw()
        game.close_top_panel()

    def test_trade_buttons_leave_scrollbar_gutter(self):
        game = self.game
        try:
            for width, height in ((1280, 800), (800, 600)):
                self.window.set_size(width, height)
                game.open_top_panel("trade")
                game.update_side_panel_animation(1)
                game.on_draw()
                panel_x, _, panel_width, _ = game.side_panel_rect()
                thumb_left = panel_x + panel_width - 20
                self.assertTrue(game.trade_action_rects)
                for rect, _, _, _ in game.trade_action_rects:
                    self.assertLessEqual(rect[0] + rect[2], thumb_left - 10)
                cached_shapes = game.trade_table_shape_list
                game.on_draw()
                self.assertIs(game.trade_table_shape_list, cached_shapes)
        finally:
            self.window.set_size(1280, 800)

    def test_country_render_bounds_and_reuses_text_pool(self):
        game = self.game
        for width, height in ((1280, 800), (1024, 768), (800, 600)):
            self.window.set_size(width, height)
            game.open_country_card(self.b)
            game.country_card_action = "loan"
            game.country_amount_focus = True
            game.update_side_panel_animation(1)
            game.on_draw()
            self.assertGreater(game.country_text_cursor, 0)
            pool_size = len(game.country_text_pool)
            game.on_draw()
            self.assertEqual(len(game.country_text_pool), pool_size)
            x, y, panel_width, panel_height = game.country_panel_rect()
            for label in game.country_text_pool[:game.country_text_cursor]:
                self.assertGreaterEqual(label.x, x)
                self.assertLessEqual(label.y, y + panel_height)
                if label.anchor_x == "left":
                    self.assertLessEqual(label.x + label.content_width, x + panel_width)
        self.window.set_size(1280, 800)

    def test_politics_and_diplomacy_navigation_and_hex_owner(self):
        game = self.game
        for key in ("politics", "diplomacy"):
            button = next(b for b in game.top_nav_buttons if b["key"] == key)
            x, y, width, height = button["rect"]
            game.on_mouse_press(x + width / 2, y + height / 2, self.arcade.MOUSE_BUTTON_LEFT, 0)
            game.update_side_panel_animation(1)
            game.on_draw()
            self.assertEqual(game.active_top_panel_key, key)
            self.assertTrue(game.country_card_hits)
            if key == "diplomacy":
                self.assertTrue(game.country_list_open)
                self.assertEqual({v for _, k, v in game.country_card_hits if k == "country"}, {self.a.id, self.b.id})
        game.set_single_selected_tile(self.b.capital_tile)
        game.on_draw()
        self.assertIsNotNone(game.hex_country_rect)
        x, y, width, height = game.hex_country_rect
        game.on_mouse_press(x + width / 2, y + height / 2, self.arcade.MOUSE_BUTTON_LEFT, 0)
        self.assertEqual(game.country_card_id, self.b.id)
        self.assertFalse(game.country_list_open)

    def test_country_panel_does_not_capture_map_mouse(self):
        game = self.game
        game.open_country_card(self.a)
        game.update_side_panel_animation(1)
        game.on_draw()
        x, y = self.window.width - 40, self.window.height / 2
        game.world_camera.zoom = 1
        game.on_mouse_scroll(x, y, 0, 1)
        self.assertGreater(game.world_camera.zoom, 1)
        game.on_mouse_press(x, y, self.arcade.MOUSE_BUTTON_MIDDLE, 0)
        self.assertTrue(game.is_dragging)
        game.on_mouse_drag(x - 20, y, -20, 0, self.arcade.MOUSE_BUTTON_MIDDLE, 0)
        self.assertTrue(game.is_dragging)
        game.on_mouse_release(x - 20, y, self.arcade.MOUSE_BUTTON_MIDDLE, 0)
        self.assertFalse(game.is_dragging)
        zoom = game.world_camera.zoom
        game.on_mouse_scroll(40, 300, 0, -1)
        self.assertEqual(game.world_camera.zoom, zoom)
        self.assertGreater(game.country_card_scroll, 0)
        game.on_mouse_press(40, 300, self.arcade.MOUSE_BUTTON_MIDDLE, 0)
        self.assertFalse(game.is_dragging)

    def test_foreign_and_mixed_selection_cannot_change_specialization(self):
        from copy import deepcopy
        game = self.game
        own = next(t for t in self.a.tiles if t.building_coverage.get("industry", 0) > 0)
        foreign = next(t for t in self.b.tiles if t.building_coverage.get("industry", 0) > 0)
        before = deepcopy(foreign.industry_allocation)
        game.set_single_selected_tile(foreign)
        self.assertFalse(game.can_edit_selected_industry())
        game.toggle_hex_specialization_mode()
        self.assertFalse(game.hex_panel_specialization_mode)
        self.assertFalse(game.set_selected_tile_industry_sector("consumer_goods"))
        self.assertEqual(foreign.industry_allocation, before)
        game.selected_tiles = [own, foreign]
        self.assertFalse(game.set_selected_tile_industry_sector("machinery"))
        self.assertEqual(foreign.industry_allocation, before)
        game.set_single_selected_tile(own)
        self.assertTrue(game.can_edit_selected_industry())
        game.toggle_hex_specialization_mode()
        self.assertTrue(game.hex_panel_specialization_mode)

    def test_trade_status_updates_on_closure_and_direct_trade_remains_available(self):
        game = self.game
        key = next(k for k in game.tradeable_resource_keys() if game.stockpile_amount(self.a, k) > 100)
        self.a.trade_contracts = [{"resource": key, "mode": "sell", "amount": 10}]
        self.a.trade_contract_revision += 1
        game.trade_panel_category = game.resource_category_for_key(key)
        game.submit_player_command("political_action", {"target": self.a.id, "action": "external"})
        row = next(r for r in game.trade_panel_snapshot()["rows"] if r["key"] == key)
        self.assertEqual(row["contract_state"], "blocked")
        self.assertIn("Внешний рынок закрыт", row["contract_status"])
        for category in self.b.resource_stockpiles.values():
            for resource in category:
                category[resource] = 0
        game.mark_player_storage_dirty(self.b)
        self.b.trade_contracts = [{"resource": key, "mode": "buy", "amount": 10}]
        self.b.trade_contract_revision += 1
        row = next(r for r in game.trade_panel_snapshot()["rows"] if r["key"] == key)
        self.assertEqual(row["contract_state"], "ready")
        game.submit_player_command("political_action", {"target": self.b.id, "action": "embargo"})
        row = next(r for r in game.trade_panel_snapshot()["rows"] if r["key"] == key)
        self.assertEqual(row["contract_state"], "blocked")
        self.assertIn("эмбарго", row["contract_status"])

    def test_division_geometry_reused_and_invalidated_by_selection(self):
        game = self.game
        game.set_selected_divisions(self.a.divisions)
        game.on_draw()
        game.on_draw()  # Allow scroll clamping to settle.
        shapes = game.division_list_icon_shape_list
        game.on_draw()
        self.assertIs(game.division_list_icon_shape_list, shapes)
        game.set_selected_divisions(self.a.divisions[:2])
        game.on_draw()
        self.assertIsNot(game.division_list_icon_shape_list, shapes)
        self.assertEqual({d.id for _, d in game.division_list_row_rects}, {d.id for d in self.a.divisions[:2]})


if __name__ == "__main__":
    unittest.main()
