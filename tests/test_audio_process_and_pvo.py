import os
from pathlib import Path
import tempfile
import time
import unittest
import wave
import random
from unittest.mock import patch


class AudioProcessTests(unittest.TestCase):
    def test_music_eos_and_effect_continue_while_parent_does_no_audio_updates(self):
        from audio_process import ProcessAudio
        with tempfile.TemporaryDirectory() as root:
            paths = []
            for name in ("one.wav", "two.wav"):
                path = Path(root) / name
                with wave.open(str(path), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(22050)
                    output.writeframes(b"\0\0" * 11025)
                paths.append(path)
            audio = ProcessAudio(playlists={"economy": paths}, volume=0, sound_volume=0)
            try:
                deadline = time.monotonic() + 10
                while not audio.status.get("sequence") and time.monotonic() < deadline:
                    audio.update()
                    time.sleep(.02)
                self.assertTrue(audio.status.get("sequence"), audio.status)
                self.assertNotEqual(audio.status["pid"], os.getpid())
                before = audio.status["sequence"]
                self.assertTrue(audio.play_effect(paths[0]))
                # Main thread is CPU-bound and pumps neither pyglet nor the IPC.
                deadline = time.monotonic() + 2.5
                while time.monotonic() < deadline:
                    sum(i * i for i in range(1000))
                audio.poll()
                self.assertGreater(audio.status["sequence"], before + 1, audio.status)
                self.assertEqual(audio.status["effect_sequence"], 1)
                self.assertLess(time.monotonic() - audio.status["heartbeat"], .4)
            finally:
                audio.close()
            self.assertFalse(audio.process.is_alive())


class AirDefenseSupplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from headless_simulation import HeadlessGame
        cls.game = HeadlessGame(146591, countries=2, map_size=16)

    def setUp(self):
        self.player = self.game.players[0]
        self.tile = self.player.capital_tile
        self.unit = self.game.create_air_defense_unit(self.player, self.tile, "medium_range_sam")
        self.unit.ammo = 0
        self.unit.reload_credit = 0
        self.tile.supply_score = 1
        self.game.add_to_stockpile_unsafe(self.player, "anti_air_ammo", 100)

    def tearDown(self):
        self.game.unregister_air_defense_unit(self.unit)

    def test_reload_transfers_real_stock_and_accumulates_fractional_hours(self):
        before = self.game.stockpile_amount(self.player, "anti_air_ammo")
        for _ in range(24):
            self.game.replenish_air_defense_ammo(self.unit, 1)
        self.assertEqual(self.unit.ammo, self.unit.ammo_capacity)
        self.assertAlmostEqual(self.game.stockpile_amount(self.player, "anti_air_ammo"), before - self.unit.ammo)

    def test_no_reload_without_supply_or_stock(self):
        self.tile.supply_score = .05
        self.game.replenish_air_defense_ammo(self.unit, 24)
        self.assertEqual(self.unit.ammo, 0)
        self.tile.supply_score = 1
        self.game.consume_from_stockpile(self.player, "anti_air_ammo", 1e12)
        self.game.replenish_air_defense_ammo(self.unit, 24)
        self.assertEqual(self.unit.ammo, 0)
        self.assertIn("Нет", self.unit.resupply_status)

    def test_moving_unit_cannot_reload_detect_or_engage(self):
        neighbor = next(t for t in self.game.neighbor_tiles(self.tile) if t.owner is self.player)
        self.unit.path = [neighbor]
        self.game.replenish_air_defense_ammo(self.unit, 24)
        self.assertEqual(self.unit.ammo, 0)
        self.assertEqual(self.game.air_defense_fire_tiles(self.unit), [])
        self.assertEqual(self.game.air_defense_detection_tiles(self.unit), [])
        self.assertNotIn(self.unit, self.game.air_defense_units_covering_tile(self.player, self.tile))
        self.assertEqual(self.game.air_defense_range_factor(self.unit, self.tile), 0)

    def test_single_low_probability_shot_can_hit_and_is_not_rounded_to_zero(self):
        with patch("air_system.random.random", return_value=.1):
            self.assertEqual(self.game.sample_air_hits(1, .2), 1)
        with patch("air_system.random.random", return_value=.9):
            self.assertEqual(self.game.sample_air_hits(1, .2), 0)
        rng = random.Random(42)
        with patch("air_system.random.random", side_effect=rng.random):
            hits = sum(self.game.sample_air_hits(1, .2) for _ in range(1000))
        self.assertGreater(hits, 150)
        self.assertLess(hits, 250)

    def test_moving_radar_does_not_support_interception(self):
        old = self.player.air_defense_units
        self.player.air_defense_units = [self.unit]
        try:
            self.unit.unit_class = "radar_unit"
            self.unit.radar_active = True
            self.unit.radar_range_cells = 8
            self.assertGreater(self.game.air_defense_radar_support_bonus(self.player, self.tile), 0)
            self.unit.path = [self.tile]
            self.assertEqual(self.game.air_defense_radar_support_bonus(self.player, self.tile), 0)
        finally:
            self.player.air_defense_units = old

    def test_ai_moves_one_battery_and_keeps_the_rest_on_station(self):
        from ai_air_operations import reposition_air_defense
        game = self.game
        bot = game.ai_system.bots[self.player.id]
        bot.next_air_defense_move = 0
        added = [game.create_air_defense_unit(self.player, self.tile, "short_range_aa") for _ in range(4)]
        center = max((tile for tile in self.player.tiles if not game.is_water_tile(tile)),
                     key=lambda tile: game.hex_distance(self.tile, tile))
        def move(unit, target):
            unit.path = [target]
            return True, "test move"
        try:
            with patch.object(game, "move_air_defense_unit", side_effect=move) as orders:
                for _ in range(5):
                    reposition_air_defense(game, bot, self.player, center, 0)
                self.assertLessEqual(orders.call_count, 1)
                self.assertGreater(sum(not unit.path for unit in added), 0)
        finally:
            for unit in added:
                game.unregister_air_defense_unit(unit)
