import random
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from ai_models import BotState, FlowLedger, Intelligence, choose_close
from ai_regions import RegionMap
from ai_system import CountryAI
from country_names import country_identities
from news_system import NewsSystem
from simulation_core import LocalSimulationServer, SimulationCommand
from Constants import SIMULATION_START_TIME


class AIModelTests(unittest.TestCase):
    def bot(self, seed=7):
        return BotState(1, random.Random(seed), 0, 0, 0, 0)

    def test_repeated_intelligence_and_refresh_keep_correlated_error(self):
        bot, intel = self.bot(), Intelligence()
        a = intel.estimate(bot, 2, "economy", "oil", 100, 0)
        for i in range(100):
            b = intel.estimate(bot, 2, "economy", "oil", 100, i)
            self.assertEqual(a.value, b.value)
            self.assertLessEqual(b.lower, 100)
            self.assertGreaterEqual(b.upper, 100)
        bot.intelligence = .8
        better = intel.estimate(bot, 2, "economy", "oil", 100, 101)
        self.assertLess(abs(better.value - 100), abs(a.value - 100))
        own = intel.estimate(bot, 1, "economy", "oil", 123, 101)
        self.assertEqual((own.value, own.lower, own.upper), (123, 123, 123))
        self.assertEqual(intel.estimate(bot, 1, "finance", "budget", -50, 101).value, -50)

    def test_obvious_choice_stays_obvious_but_close_choices_vary(self):
        rng = random.Random(3)
        self.assertEqual({choose_close(rng, [(100, "best"), (20, "bad")]) for _ in range(50)}, {"best"})
        self.assertEqual({choose_close(rng, [(100, "a"), (98, "b")]) for _ in range(100)}, {"a", "b"})

    def test_flow_ledger_records_actual_transfers_and_bounds_history(self):
        ledger = FlowLedger()
        ledger.sample(1, 0)
        for day in range(1, 40):
            ledger.advance(1, 24)
            ledger.record(1, "output", "oil", 10)
            ledger.record(1, "import", "food", 3, 2)
            ledger.sample(1, day * 24)
        rates, hours = ledger.rates(1, 39 * 24)
        self.assertEqual(rates["output", "oil", None], 300)
        self.assertEqual(rates["import", "food", 2], 90)
        self.assertLessEqual(len(ledger.samples[1]), 10)
        self.assertEqual(hours, 168)

    def test_names_unique_and_do_not_touch_global_random(self):
        before = random.getstate()
        pairs = country_identities(42, 12)
        self.assertEqual(before, random.getstate())
        self.assertEqual(pairs, country_identities(42, 12))
        self.assertEqual(len({name for name, ruler in pairs}), 12)
        self.assertEqual(len({ruler for name, ruler in pairs}), 12)

    def test_clock_calls_world_in_six_hour_steps_at_max_speed(self):
        server = LocalSimulationServer()
        server.set_paused(False)
        server.set_speed_level(5)
        dates = []
        server.update(.25, lambda hours: dates.append((hours, server.current_time)))
        self.assertEqual([hours for hours, date in dates], [6, 6, 6, 6])
        self.assertEqual(dates[-1][1], SIMULATION_START_TIME + timedelta(days=1))
        server.set_paused(True)
        server.update(1, lambda hours: self.fail("AI/world advanced during pause"))

    def test_fast_speed_spreads_work_across_render_updates(self):
        server = LocalSimulationServer()
        server.set_speed_level(5)
        server.set_paused(False)
        counts = []
        for _ in range(15):
            steps = []
            server.update(1 / 60, steps.append)
            counts.append(len(steps))
        self.assertEqual(sum(counts), 4)
        self.assertEqual(max(counts), 1)
        self.assertEqual(server.current_time, SIMULATION_START_TIME + timedelta(days=1))

    def test_weekly_review_runs_on_different_days(self):
        bot = self.bot()
        bot.reviews["weekly"] = review = __import__("ai_models").Review("weekly", 0, 0)
        server = SimpleNamespace(current_time=SIMULATION_START_TIME)
        game = SimpleNamespace(simulation_server=server, players=[SimpleNamespace(id=i) for i in range(12)])
        ai = CountryAI.__new__(CountryAI)
        ai.game = game
        calls = []
        ai.economy_report = lambda *args: calls.append("economy")
        ai.military_report = lambda *args: calls.append("military")
        ai.profiles = lambda *args: {}
        ai.assess_dependencies = lambda *args: calls.append("dependencies")
        ai.economic_tasks = lambda *args: calls.append("tasks")
        ai.diplomatic_tasks = lambda *args: calls.append("diplomacy")
        ai.air_tasks = lambda *args: calls.append("air")
        player = SimpleNamespace(id=1)
        stages = []
        for _ in range(20):
            if "weekly" not in bot.reviews:
                break
            server.current_time = SIMULATION_START_TIME + timedelta(hours=review.next_hour)
            before, count = review.stage, len(calls)
            ai.review_stage(bot, player, review)
            self.assertLessEqual(len(calls) - count, 3)
            if review.stage != before:
                stages.append(before)
        self.assertEqual(stages, list(range(7)))
        self.assertNotIn("weekly", bot.reviews)
        self.assertGreater((server.current_time - SIMULATION_START_TIME).total_seconds() / 3600, 120)

    def test_untrusted_ai_command_cannot_mutate_world(self):
        ai = CountryAI.__new__(CountryAI)
        ai.pending = {}
        ai.bots = {1: self.bot()}
        self.assertFalse(ai.handle_command(SimulationCommand("ai_action", 1, {"operation": "intelligence"})))


class RegionTests(unittest.TestCase):
    def test_connected_cover_and_owner_fragments(self):
        owner = SimpleNamespace(id=1, tiles=[])
        tiles = {(q, 0): SimpleNamespace(q=q, r=0, owner=owner) for q in range(12)}
        owner.tiles = list(tiles.values())
        game = SimpleNamespace(hex_lookup=tiles, tile_key=lambda t: (t.q, t.r),
            tile_for_key=lambda key: tiles.get(tuple(key)), is_water_tile=lambda t: False,
            neighbor_tiles=lambda t: [tiles[k] for k in ((t.q - 1, 0), (t.q + 1, 0)) if k in tiles])
        regions = RegionMap(game, max_tiles=4)
        self.assertEqual(len(regions.tile_region), 12)
        before = dict(regions.tile_region)
        tiles[1, 0].owner = None
        owner.tiles.remove(tiles[1, 0])
        parts = regions.controlled(owner)
        self.assertEqual(sum(len(part) for part in parts.values()), 11)
        self.assertEqual(regions.tile_region, before)
        self.assertTrue(all(max(k[0] for k in part) - min(k[0] for k in part) + 1 == len(part) for part in parts.values()))


class NewsLogTests(unittest.TestCase):
    def test_persistent_complete_history_reset_only_for_new_game(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "news.txt"
            news = NewsSystem()
            news.start_log(path, SIMULATION_START_TIME, 123)
            for i in range(305):
                news.publish(i, "test", f"Заголовок {i}", f"Описание {i}", scope="local", country_ids=(2,))
            text = path.read_text(encoding="utf-8")
            self.assertIn("Заголовок 0\nОписание 0", text)
            self.assertIn("Заголовок 304\nОписание 304", text)
            self.assertIn((SIMULATION_START_TIME + timedelta(days=304)).strftime("%Y-%m-%d"), text)
            self.assertEqual(len(news.items), 300)
            NewsSystem().start_log(path, SIMULATION_START_TIME, 456)
            self.assertNotIn("Заголовок", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
