import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime_diagnostics import RuntimeDiagnostics, diagnose_frame


class RuntimeDiagnosticsTests(unittest.TestCase):
    def monitor(self, root):
        return RuntimeDiagnostics(dict(seed=123, map_size=100, bots=3), Path(root) / "runtime")

    def records(self, monitor):
        return [json.loads(line) for line in monitor.path.read_text(encoding="utf-8").splitlines()]

    def test_stalled_frame_persists_stack_and_does_not_spam(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = self.monitor(root)
            monitor.active = (time.perf_counter() - 10, dict(phase="update", game_time="2000-01-30 00:00:00"))
            monitor.stage("ai_total", "2000-01-30 00:00:00")
            monitor.poll()
            monitor.poll()
            rows = [r for r in self.records(monitor) if r["kind"] == "stalled_frame"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["subsystem"], "ai_total")
            self.assertIn("test_stalled_frame", rows[0]["stack"])
            text = monitor.text_path.read_text(encoding="utf-8")
            self.assertIn("2000-01-30", text)
            self.assertIn("stalled_frame", text)
            self.assertEqual(json.loads((Path(root) / "runtime/latest.json").read_text())["seed"], 123)

    def test_exception_is_logged_and_propagates(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = self.monitor(root)
            game = SimpleNamespace(runtime_diagnostics=monitor,
                simulation_server=SimpleNamespace(current_time="2000-01-30"),
                active_top_panel_key="military", world_camera=SimpleNamespace(zoom=.45))
            @diagnose_frame("update")
            def broken(game):
                raise ValueError("diagnostic test failure")
            with self.assertRaisesRegex(ValueError, "diagnostic test failure"):
                broken(game)
            self.assertIsNone(monitor.active)
            row = next(r for r in self.records(monitor) if r["kind"] == "exception")
            self.assertIn("ValueError", row["traceback"])
            self.assertEqual(row["context"]["panel"], "military")

    def test_event_loop_stall_between_callbacks_is_recorded(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = self.monitor(root)
            monitor.heartbeat = time.perf_counter() - 10
            monitor.last_context = dict(phase="mouse_drag", game_time="2000-05-07")
            monitor.poll()
            monitor.poll()
            rows = [r for r in self.records(monitor) if r["kind"] == "stalled_frame"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["phase"], "event_loop")
            self.assertEqual(rows[0]["game_time"], "2000-05-07")
            monitor.heartbeat = None  # hidden views must not trigger alarms
            monitor.last_reported = None
            monitor.poll()
            self.assertEqual(len([r for r in self.records(monitor) if r["kind"] == "stalled_frame"]), 1)

    def test_release_logs_selection_and_pause_after_input(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = self.monitor(root)
            game = SimpleNamespace(runtime_diagnostics=monitor,
                simulation_server=SimpleNamespace(current_time="2000-05-07", paused=True),
                active_top_panel_key=None, world_camera=SimpleNamespace(zoom=.55),
                selected_division_ids=set(), division_selection_drag_active=True)
            @diagnose_frame("input_mouse_release")
            def release(game):
                game.selected_division_ids = {3, 1}
                game.division_selection_drag_active = False
            release(game)
            row = next(r for r in self.records(monitor) if r["kind"] == "input_result")
            self.assertTrue(row["paused"])
            self.assertEqual(row["selected_divisions"], [1, 3])
            self.assertFalse(row["selection_drag"])

    def test_disk_failure_does_not_break_simulation(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = self.monitor(root)
            with patch.object(Path, "open", side_effect=OSError("disk unavailable")):
                monitor.write("test")
            self.assertIn("disk unavailable", monitor.error)

    def test_no_monitor_keeps_original_call(self):
        @diagnose_frame("update")
        def operation(game, value):
            return value + 1
        self.assertEqual(operation(object(), 5), 6)

    def test_subsystem_is_tracked_even_with_f3_disabled(self):
        from performance import PerformanceProfiler
        with tempfile.TemporaryDirectory() as root:
            monitor = self.monitor(root)
            monitor.active = (time.perf_counter(), dict(phase="draw", game_time="2000-01-30"))
            profiler = PerformanceProfiler()
            profiler.diagnostic_stage = monitor.stage
            with profiler.measure("world_air_assets"):
                self.assertEqual(monitor.active[1]["subsystem"], "world_air_assets")
                self.assertEqual(monitor.active[1]["game_time"], "2000-01-30")
            self.assertFalse(profiler.enabled)

    def test_input_exception_records_click_and_news_state(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = self.monitor(root)
            game = SimpleNamespace(runtime_diagnostics=monitor,
                simulation_server=SimpleNamespace(current_time="2000-07-12"),
                active_top_panel_key=None, world_camera=SimpleNamespace(zoom=.4),
                map_layer="supply", news_archive_open=True, news_popup_id=None)
            @diagnose_frame("input_mouse_press")
            def click(game, x, y):
                raise ValueError("input test")
            with self.assertRaises(ValueError):
                click(game, 100, 200)
            event = next(r for r in self.records(monitor) if r["kind"] == "input")
            self.assertEqual(event["arguments"], [100, 200])
            self.assertTrue(event["news_archive"])
            self.assertTrue(any(r["kind"] == "exception" for r in self.records(monitor)))
