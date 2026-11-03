import contextlib
import io
import unittest
from Constants import TRADE_BASE_PRICES
from ai_supply import supply_site
from headless_simulation import HeadlessGame


class SupplyPlanningTests(unittest.TestCase):
    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.game = HeadlessGame(1, countries=2, map_size=32)
        self.player = self.game.players[0]
        self.ai = self.game.ai_system
        self.bot = self.ai.bots[self.player.id]
        self.post = min((t for t in self.player.tiles if not self.game.is_water_tile(t)),
                        key=lambda t: getattr(t, "supply_score", 0))
        for d in self.player.divisions:
            d.tile = self.post
        for t in self.player.tiles:
            t.supply_score = .95
        self.post.supply_score = .05
        self.bot.hex_assignments = {d.id: self.game.tile_key(self.post) for d in self.player.divisions}
        for key in TRADE_BASE_PRICES:
            self.game.add_to_stockpile_unsafe(self.player, key, 100000)

    def test_poor_occupied_hex_is_not_hidden_by_high_country_average(self):
        self.assertGreater(sum(t.supply_score for t in self.player.tiles) / len(self.player.tiles), .8)
        selection = supply_site(self.ai, self.bot, self.player)
        self.assertIsNotNone(selection)
        self.assertGreater(selection[0], 0)
        self.assertLessEqual(self.game.hex_distance(self.game.tile_for_key(selection[1]), self.post), 2)

    def test_prewar_depot_uses_normal_queue_and_is_not_duplicated(self):
        self.assertFalse(self.game.countries_hostile(self.player, self.game.players[1]))
        self.ai.supply_tasks(self.bot, self.player)
        self.ai.execute_tasks(self.bot, self.player)
        self.game.simulation_server.process_pending_commands()
        projects = [p for p in self.player.construction_queue if p["building"] == "supply_depot"]
        self.assertEqual(len(projects), 1)
        self.ai.supply_tasks(self.bot, self.player)
        self.ai.execute_tasks(self.bot, self.player)
        self.game.simulation_server.process_pending_commands()
        self.assertEqual(len(self.player.construction_queue), 1)
        self.assertGreater(projects[0]["money_cost"], 0)

    def test_unfunded_depot_does_not_bypass_costs(self):
        self.player.budget = 0
        self.ai.supply_tasks(self.bot, self.player)
        self.ai.execute_tasks(self.bot, self.player)
        self.game.simulation_server.process_pending_commands()
        self.assertFalse(self.player.construction_queue)
        self.assertEqual(self.player.budget, 0)

    def test_frontline_depot_has_priority_over_full_paused_build_queue(self):
        game = self.game
        game.enqueue_construction_steps(self.player, self.player.capital_tile, "warehouse", 4)
        self.assertEqual(len(self.player.construction_queue), 4)
        for project in self.player.construction_queue:
            project["paused"] = True
        self.ai.supply_tasks(self.bot, self.player)
        self.ai.execute_tasks(self.bot, self.player)
        game.simulation_server.process_pending_commands()
        self.assertEqual(self.player.construction_queue[0]["building"], "supply_depot")
        self.assertFalse(self.player.construction_queue[0].get("paused"))

    def test_repair_queue_does_not_block_new_depot_at_weak_position(self):
        game = self.game
        tile = self.player.capital_tile
        tile.building_coverage["supply_depot"] = .3
        game.set_building_health(tile, "supply_depot", .5)
        game.enqueue_auto_repair(self.player, tile, "supply_depot")
        self.assertTrue(any(p.get("project_type") == "repair" for p in self.player.construction_queue))
        self.ai.supply_tasks(self.bot, self.player)
        self.ai.execute_tasks(self.bot, self.player)
        game.simulation_server.process_pending_commands()
        self.assertTrue(any(p["building"] == "supply_depot" and p.get("project_type") == "build"
                            for p in self.player.construction_queue))

    def test_newly_owned_hex_without_supply_field_is_supported(self):
        del self.post.supply_score
        self.assertIsNotNone(supply_site(self.ai, self.bot, self.player))

    def test_constructed_depot_improves_real_supply_at_held_position(self):
        game = self.game
        for tile in self.player.tiles:
            tile.building_coverage.clear()
        self.player.capital_tile.building_coverage.update(city=1, industry=1)
        game.recalculate_player_supply(self.player)
        before = self.post.supply_score
        selection = supply_site(self.ai, self.bot, self.player)
        self.assertIsNotNone(selection)
        tile = game.tile_for_key(selection[1])
        self.assertGreater(game.enqueue_construction_steps(self.player, tile, "supply_depot", 14), 0)
        for _ in range(180):
            game.run_construction_tick(self.player, 24)
            if not self.player.construction_queue:
                break
        self.assertFalse(self.player.construction_queue)
        self.assertGreater(tile.building_coverage.get("supply_depot", 0), .65)
        self.assertGreater(self.post.supply_score, before)
