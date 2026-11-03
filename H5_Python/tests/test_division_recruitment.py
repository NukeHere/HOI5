import contextlib
import io
import unittest

from headless_simulation import HeadlessGame
from simulate_ai import audit_world
from simulation_core import SimulationCommand


class RecruitmentTests(unittest.TestCase):
    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.game = HeadlessGame(1, countries=2, map_size=16)
        self.service = self.game.recruitment
        self.player = self.game.players[0]
        self.tile = self.service.site(self.player)

    def fund(self, key="basic_infantry"):
        cost = self.service.quote(self.game.division_template(key))
        self.player.budget = 10 * cost["money"]
        self.player.manpower_reserve = 10 * cost["manpower"]
        for k, n in cost["equipment"].items():
            self.game.add_to_stockpile_unsafe(self.player, k, n)
        return cost

    def test_composition_matches_presets_and_mixes_stats(self):
        for key, original in self.service.archetypes.items():
            result = self.service.compose({key: 10})
            for field in ("manpower", "soft_attack", "defense", "front_width", "speed", "front_armor"):
                self.assertAlmostEqual(result[field], original[field])
            self.assertEqual(set(result["supply_capacity"]), set(original["supply_capacity"]))
            for resource, amount in original["supply_capacity"].items():
                self.assertAlmostEqual(result["supply_capacity"][resource], amount)
        mixed = self.service.compose({"basic_infantry": 6, "tank": 4})
        self.assertEqual(mixed["manpower"], 9200)
        self.assertAlmostEqual(mixed["soft_attack"], 18 * .6 + 16 * .4)
        self.assertEqual(mixed["speed"], 1.35)

    def test_invalid_compositions_are_rejected(self):
        for parts in ({}, {"tank": 21}, {"tank": -1}, {"tank": 1.5}, {"tank": True},
                      {"tank": float("nan")}, {"missing": 1}, {"tank": 15, "basic_infantry": 15}):
            with self.assertRaises(ValueError):
                self.service.compose(parts)

    def test_designs_are_private_and_queued_design_is_frozen(self):
        ok, key = self.service.save_design(self.player, {"basic_infantry": 10}, "Своя дивизия")
        self.assertTrue(ok)
        self.assertFalse(self.service.allowed(self.game.players[1], key))
        self.fund(key)
        self.assertTrue(self.service.enqueue(self.player, key, self.tile)[0])
        project = self.service.queues[self.player.id][0]
        self.game.division_templates[key]["soft_attack"] = 999
        self.assertEqual(project["template"]["soft_attack"], 18)

    def test_missing_equipment_does_not_charge_anything(self):
        self.fund()
        self.player.resource_stockpiles[self.game.resource_category_for_key("old_assault_rifles")]["old_assault_rifles"] = 0
        money, people = self.player.budget, self.player.manpower_reserve
        self.assertFalse(self.service.enqueue(self.player, "basic_infantry", self.tile)[0])
        self.assertEqual((self.player.budget, self.player.manpower_reserve), (money, people))
        self.assertFalse(self.service.queues[self.player.id])

    def test_paid_training_deploys_once_after_duration(self):
        cost = self.fund()
        money, people = self.player.budget, self.player.manpower_reserve
        stock = self.game.stockpile_amount(self.player, "old_assault_rifles")
        count = len(self.player.divisions)
        self.assertTrue(self.service.enqueue(self.player, "basic_infantry", self.tile)[0])
        self.assertEqual(self.player.budget, money - cost["money"])
        self.assertEqual(self.player.manpower_reserve, people - cost["manpower"])
        self.assertEqual(self.game.stockpile_amount(self.player, "old_assault_rifles"), stock - cost["equipment"]["old_assault_rifles"])
        self.service.update(cost["days"] * 24 - 1)
        self.assertEqual(len(self.player.divisions), count)
        self.service.update(1)
        self.service.update(1)
        self.assertEqual(len(self.player.divisions), count + 1)
        unit = self.player.divisions[-1]
        self.assertEqual(unit.organization, unit.max_organization * .5)
        self.assertEqual(unit.supply_stock, cost["equipment"])
        audit_world(self.game)

    def test_cancellation_refunds_once_and_spent_training_is_not_free(self):
        cost = self.fund()
        money, people = self.player.budget, self.player.manpower_reserve
        stock = self.game.stockpile_amount(self.player, "old_assault_rifles")
        self.service.enqueue(self.player, "basic_infantry", self.tile)
        project = self.service.queues[self.player.id][0]
        self.service.update(cost["days"] * 12)
        self.assertTrue(self.service.cancel(self.player, project["id"])[0])
        self.assertFalse(self.service.cancel(self.player, project["id"])[0])
        self.assertEqual(self.player.budget, money - cost["money"] * .5)
        self.assertEqual(self.player.manpower_reserve, people)
        self.assertEqual(self.game.stockpile_amount(self.player, "old_assault_rifles"), stock)

    def test_no_safe_site_delays_deployment(self):
        cost = self.fund()
        self.service.enqueue(self.player, "basic_infantry", self.tile)
        for tile in self.player.tiles:
            tile.supply_score = 0
        count = len(self.player.divisions)
        self.service.update(cost["days"] * 24)
        self.assertEqual(len(self.player.divisions), count)
        self.assertEqual(self.service.queues[self.player.id][0]["status"], "waiting_site")
        self.tile.supply_score = 1
        self.service.update(6)
        self.assertEqual(len(self.player.divisions), count + 1)

    def test_human_adapter_rejects_foreign_controller(self):
        self.game.human_player = self.player
        other = self.game.players[1]
        command = SimulationCommand("division_recruitment", other.id,
                                    dict(operation="save", composition={"tank": 10}))
        self.assertFalse(self.service.handle_command(command))
        self.assertFalse(self.service.designs[other.id])

    def test_human_deployment_waits_for_selected_hex_and_can_be_relocated(self):
        self.game.human_player = self.player
        cost = self.fund()
        self.assertTrue(self.service.enqueue(self.player, "basic_infantry", self.tile)[0])
        project = self.service.queues[self.player.id][0]
        self.tile.supply_score = 0
        alternate = self.service.site(self.player)
        self.assertIsNotNone(alternate)
        count = len(self.player.divisions)
        self.service.update(cost["days"] * 24)
        self.assertEqual(len(self.player.divisions), count)
        self.assertEqual(project["status"], "waiting_site")
        other_project_key = self.game.tile_key(self.game.players[1].capital_tile)
        rejected = SimulationCommand("division_recruitment", self.player.id,
            dict(operation="relocate", id=project["id"], tile_key=other_project_key), client_id="local")
        self.assertFalse(self.service.handle_command(rejected))
        command = SimulationCommand("division_recruitment", self.player.id,
            dict(operation="relocate", id=project["id"], tile_key=self.game.tile_key(alternate)), client_id="local")
        self.assertTrue(self.service.handle_command(command))
        self.service.update(6)
        self.assertEqual(len(self.player.divisions), count + 1)
        self.assertIs(self.player.divisions[-1].tile, alternate)

    def test_bot_orders_replacements_through_paid_rules(self):
        cost = self.fund()
        self.game.destroy_division(self.player.divisions[-1])
        bot = self.game.ai_system.bots[self.player.id]
        self.game.ai_system.recruitment_tasks(bot, self.player, *self.game.ai_system.available(self.player))
        self.game.ai_system.execute_tasks(bot, self.player)
        self.game.simulation_server.process_pending_commands()
        self.assertTrue(self.service.queues[self.player.id])
        self.assertLess(self.player.budget, cost["money"] * 10)
