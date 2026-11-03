import contextlib
import io
import unittest
from unittest.mock import patch

from Constants import TRADE_BASE_PRICES
from ai_air_operations import configure_air_operations
from headless_simulation import HeadlessGame


class AirSupportTests(unittest.TestCase):
    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.game = HeadlessGame(1, countries=2, map_size=16)
        game = self.game
        self.a, self.b = game.players
        for tile in game.hex_grid:
            tile.terrain_type, tile.water_cover, tile.passability = "plains", 0, 1
        self.base = game.hex_lookup[5, 5]
        self.target = game.hex_lookup[8, 5]
        self.depot = game.hex_lookup[9, 5]
        for tile, owner in ((self.base, self.a), (self.target, self.b), (self.depot, self.b)):
            game.set_tile_owner_only(tile, owner)
        self.base.building_coverage["airbase"] = 1
        game.create_airbase(self.a, self.base, coverage=1)
        game.politics.relation(self.a.id, self.b.id).at_war = True
        for unit in list(game.air_defense_units):
            game.unregister_air_defense_unit(unit)
        for d in self.b.divisions:
            d.tile = self.target
        self.depot.building_coverage.update(supply_depot=.8, industry=.8)
        for key in TRADE_BASE_PRICES:
            game.add_to_stockpile_unsafe(self.a, key, 100000)
        self.bot = game.ai_system.bots[self.a.id]
        self.wing = game.create_air_wing(self.a, self.base, "multirole_fighter", 10)
        self.wing.enabled_missions = ["cas", "strategic_strike"]
        self.wing.operation_area_tile_keys = [game.tile_key(self.target), game.tile_key(self.depot)]

    def test_cas_can_target_concentration_without_ground_battle(self):
        self.assertFalse(self.game.battles)
        self.assertTrue(self.game.air_wing_can_attack_tile(self.wing, self.target, "cas"))
        self.assertIs(self.game.select_air_wing_cas_target(self.wing), self.target)

    def test_sampled_flight_leaves_base_and_advances_faster_at_speed_five(self):
        game = self.game
        game.simulation_server.set_paused(False)
        game.simulation_server.set_speed_level(1)
        game.update_sampled_air_flights(.1)
        _, x, y, _ = next(game.sampled_air_flight_positions())
        self.assertEqual((x, y), (self.base.center_x, self.base.center_y))
        game.update_sampled_air_flights(.1)
        self.assertAlmostEqual(game._sampled_air_flights[0][3], .1)
        game.simulation_server.set_speed_level(5)
        game.update_sampled_air_flights(.1)
        self.assertAlmostEqual(game._sampled_air_flights[0][3], .35)
        game.simulation_server.set_paused(True)
        game.update_sampled_air_flights(1)
        self.assertAlmostEqual(game._sampled_air_flights[0][3], .35)

    def test_stationary_battery_spends_ammo_against_cas_with_low_hit_chance(self):
        game = self.game
        unit = game.create_air_defense_unit(self.b, self.depot, "medium_range_sam")
        before = unit.ammo
        with patch.object(game, "air_defense_range_factor", return_value=.65), \
             patch.object(game, "sample_air_hits", return_value=0):
            estimate = game.estimate_intercept_or_hit_chance(unit, None, self.wing,
                {"exposure_tile": self.target, "aircraft_type": "multirole_fighter", "mission_type": "cas"})
            self.assertLess(estimate.hit_chance, .15)
            game.resolve_air_defense_against_air_wing(
                self.wing, self.target, "multirole_fighter", 1, "cas", phase="attack_run")
        self.assertLess(unit.ammo, before)

    def test_own_ground_battle_has_priority_over_small_remote_group(self):
        game = self.game
        for d in self.b.divisions[3:]:
            d.tile = self.depot
        battle_tile = game.hex_lookup[7, 5]
        game.set_tile_owner_only(battle_tile, self.b)
        self.b.divisions[0].tile = battle_tile
        attacker = self.a.divisions[0]
        attacker.tile = game.hex_lookup[6, 5]
        game.start_or_join_battle(attacker, battle_tile)
        self.wing.operation_area_tile_keys.append(game.tile_key(battle_tile))
        self.assertIs(game.select_air_wing_cas_target(self.wing), battle_tile)

    def test_aircraft_can_approach_when_base_is_outside_weapon_range(self):
        weapon = self.game.munition_data("unguided_rockets")
        distance = weapon["max_range"] + 3
        launch = self.game.choose_air_mission_launch_distance(distance, "unguided_rockets", mission_type="cas")
        self.assertIsNotNone(launch)
        self.assertLessEqual(launch, weapon["max_range"])

    def test_out_of_aircraft_range_is_not_selected(self):
        far = self.game.hex_lookup[15, 15]
        self.b.divisions[0].tile = far
        self.wing.operation_area_tile_keys = [self.game.tile_key(far)]
        self.assertIsNone(self.game.select_air_wing_cas_target(self.wing))

    def test_bot_plan_enables_strikes_and_includes_economic_targets(self):
        configure_air_operations(self.game, self.bot, self.a, self.wing, [self.game.tile_key(self.base)], True)
        self.assertIn("strategic_strike", self.wing.enabled_missions)
        self.assertIn("cas", self.wing.enabled_missions)
        self.assertIn(self.game.tile_key(self.depot), self.wing.operation_area_tile_keys)
        self.assertEqual(self.wing.risk_policy, "normal")

    def test_hostile_aa_does_not_remove_target_from_plan(self):
        self.game.create_air_defense_unit(self.b, self.target, "medium_range_sam")
        configure_air_operations(self.game, self.bot, self.a, self.wing, [self.game.tile_key(self.base)], True)
        self.assertIn(self.game.tile_key(self.target), self.wing.operation_area_tile_keys)
        with patch.object(self.game, "resolve_air_defense_against_air_wing", return_value={"aborted": True}) as defense:
            self.game.execute_air_wing_active_mission(self.wing, "cas", self.target)
        self.assertTrue(defense.called)

    def test_real_cas_and_strike_both_launch_from_same_wing(self):
        self.wing.sortie_intensity = 1
        self.game.update_air_missions(1)
        events = [r for r in self.bot.history if r["kind"] == "air_sortie"]
        missions = {r["mission"] for r in events}
        self.assertIn("cas", missions)
        self.assertIn("strategic_strike", missions)
        self.assertLessEqual(sum(r["sorties"] for r in events), 10)

    def test_strategic_hit_reduces_real_building_health(self):
        game = self.game
        before = sum(game.building_health(self.depot, k) for k in ("supply_depot", "industry"))
        sorties = game.execute_air_wing_active_mission(self.wing, "strategic_strike", self.depot)
        self.assertGreater(sorties, 0)
        for _ in range(30):
            game.update_air_salvos(1)
        after = sum(game.building_health(self.depot, k) for k in ("supply_depot", "industry"))
        self.assertLess(after, before)

    def test_cas_hit_causes_real_organization_or_strength_loss(self):
        game = self.game
        before = sum(d.organization + d.strength for d in self.b.divisions)
        self.assertGreater(game.execute_air_wing_active_mission(self.wing, "cas", self.target), 0)
        for _ in range(30):
            game.update_air_salvos(1)
        self.assertLess(sum(d.organization + d.strength for d in self.b.divisions), before)

    def test_defensive_support_hits_attackers_source_not_friendly_battle_tile(self):
        game = self.game
        source, defended = game.hex_lookup[6, 5], game.hex_lookup[7, 5]
        game.set_tile_owner_only(source, self.b)
        game.set_tile_owner_only(defended, self.a)
        attacker, defender = self.b.divisions[0], self.a.divisions[0]
        attacker.tile, defender.tile = source, defended
        game.start_or_join_battle(attacker, defended)
        self.wing.operation_area_tile_keys = [game.tile_key(defended)]
        self.assertIs(game.select_air_wing_cas_target(self.wing), source)
        before = attacker.organization + attacker.strength
        self.assertGreater(game.launch_air_wing_mission_packages(self.wing, "cas", {}), 0)
        for _ in range(30):
            game.update_air_salvos(1)
        self.assertLess(attacker.organization + attacker.strength, before)
