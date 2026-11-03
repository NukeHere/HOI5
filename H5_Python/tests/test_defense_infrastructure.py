import unittest
from unittest.mock import patch

from defense_infrastructure import fortification_bonus, air_defense_quote, enqueue_air_defense, update_air_defense_replacements
from headless_simulation import HeadlessGame


class DefenseInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = HeadlessGame(1729, countries=2, map_size=16)

    def test_fortification_has_thirty_percent_base_and_seventy_percent_supply_part(self):
        self.assertAlmostEqual(fortification_bonus(1, 1, 0, 0), .18)
        self.assertAlmostEqual(fortification_bonus(1, 1, 1, 0), .60)
        self.assertAlmostEqual(fortification_bonus(1, 1, 1, 1), .25)
        self.assertAlmostEqual(fortification_bonus(.5, .5, 1, 0), .15)
        self.assertEqual(fortification_bonus(1, 0, 1, 0), 0)

    def test_real_battle_defense_bonus_depends_on_attacker_and_damage(self):
        game = self.game
        attacker, target = game.players[0].divisions[0], game.players[1].divisions[0]
        target.tile = game.players[1].capital_tile
        tile = target.tile
        tile.building_coverage["fortification"] = 1
        tile.building_health["fortification"] = 0
        tile.supply_score = 1
        def hit(health, armor, defending=True):
            tile.building_health["fortification"] = health
            attacker.vehicle_share = armor
            target.organization = target.max_organization
            target.strength = target.max_strength
            game.apply_combat_attack(attacker, target, target_is_defending=defending, elapsed_hours=.01)
            return attacker.last_combat_attack_debug
        with patch.object(game, "consume_division_attack_supplies", return_value=dict(soft=1, front=1, top=1)):
            self.assertAlmostEqual(hit(1, 0)["fortification_bonus"], .6)
            self.assertAlmostEqual(hit(1, 1)["fortification_bonus"], .25)
            self.assertEqual(hit(0, 0)["fortification_bonus"], 0)
            self.assertEqual(hit(1, 0, defending=False)["fortification_bonus"], 0)

    def test_bunker_is_normal_paid_construction_and_can_be_destroyed(self):
        game = self.game
        player = game.players[1]
        tile = next(t for t in player.tiles if not game.is_water_tile(t) and t is not player.capital_tile)
        tile.building_coverage.pop("fortification", None)
        quote = game.construction_cost(player, tile, "fortification")
        self.assertGreater(quote["money_cost"], 0)
        self.assertGreater(quote["resource_costs"]["steel"], 0)
        self.assertTrue(game.enqueue_construction(player, tile, "fortification", refresh=False))
        tile.building_coverage["fortification"] = .3
        tile.building_health.pop("fortification", None)
        self.assertTrue(game.damage_building(tile, "fortification", 1, queue_repair=False))
        self.assertEqual(game.building_health(tile, "fortification"), 0)

    def test_replacement_costs_equipment_and_completes_after_training(self):
        game = self.game
        player = game.players[0]
        game.air_defense_replacements = {}
        quote = air_defense_quote(game, "medium_range_sam")
        for key, amount in quote["resources"].items():
            game.add_to_stockpile_unsafe(player, key, amount * 10)
        player.budget = 100_000_000
        before = player.budget
        units = len(player.air_defense_units)
        self.assertTrue(enqueue_air_defense(game, player, "medium_range_sam")[0])
        self.assertEqual(player.budget, before - quote["money"])
        self.assertFalse(enqueue_air_defense(game, player, "medium_range_sam")[0])
        player.capital_tile.supply_score = 1
        update_air_defense_replacements(game, 47)
        self.assertEqual(len(player.air_defense_units), units)
        update_air_defense_replacements(game, 1)
        self.assertEqual(len(player.air_defense_units), units + 1)

    def test_bot_replacement_task_reaches_paid_server_command(self):
        game = self.game
        player = game.players[0]
        bot = game.ai_system.bots[player.id]
        kind = "medium_range_sam"
        bot.air_defense_targets = {kind: sum(u.unit_class == kind for u in player.air_defense_units) + 1}
        bot.tasks.clear()
        game.air_defense_replacements = {}
        player.budget = 100_000_000
        for key, amount in air_defense_quote(game, kind)["resources"].items():
            game.add_to_stockpile_unsafe(player, key, amount * 100)
        game.ai_system.defense_infrastructure_tasks(bot, player)
        game.ai_system.execute_tasks(bot, player)
        game.simulation_server.process_pending_commands()
        self.assertIn(player.id, game.air_defense_replacements)
        self.assertEqual(game.air_defense_replacements[player.id]["unit_class"], kind)
        game.air_defense_replacements.clear()
