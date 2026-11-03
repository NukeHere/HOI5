"""Real decoder, EOS and game lifecycle checks; RUN_ARCADE_TESTS=1 PYGLET_AUDIO=silent."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import wave


@unittest.skipUnless(os.environ.get("RUN_ARCADE_TESTS") == "1", "requires Arcade/audio drivers")
class MusicStreamingTests(unittest.TestCase):
    def test_real_library_decodes_as_streams(self):
        from concurrent.futures import ThreadPoolExecutor
        from pyglet import media
        from dynamic_music import release_source
        root = Path(__file__).resolve().parents[1]
        results = []
        with ThreadPoolExecutor(max_workers=1) as worker:
            for path in sorted((root / "music").rglob("*.ogg")):
                source = worker.submit(media.load, str(path), streaming=True).result(timeout=10)
                try:
                    self.assertIsNotNone(source.audio_format, path)
                    self.assertGreater(source.duration, 0, path)
                    results.append(dict(path=str(path.relative_to(root)), seconds=source.duration))
                finally:
                    release_source(source)
        self.assertGreater(len(results), 0)
        output = root / "logs/diagnostics/music-library.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_real_ogg_playback_reaches_natural_eos(self):
        import pyglet
        from dynamic_music import StreamingMusic
        backend = StreamingMusic()
        self.addCleanup(backend.close)
        root = Path(__file__).resolve().parents[1]
        path = next((root / "music/economy").glob("*.ogg"))
        backend.prepare(path)
        deadline = time.monotonic() + 6
        while not backend.start(path, 0) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertIsNotNone(backend.player)
        backend.player.seek(max(0, backend.player.source.duration - .1))
        deadline = time.monotonic() + 6
        while not backend.finished() and time.monotonic() < deadline:
            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()
            time.sleep(.01)
        self.assertTrue(backend.finished())

    def test_menu_theme_stops_on_view_change_and_restarts_on_return(self):
        import arcade
        from MainMenu import MainMenuView
        window = arcade.Window(1280, 800, visible=False)
        menu = None
        try:
            menu = MainMenuView()
            window.show_view(menu)
            deadline = time.monotonic() + 6
            while menu.music.current_path is None and time.monotonic() < deadline:
                menu.on_update(1 / 60)
                window.dispatch_events()
                time.sleep(.01)
            self.assertEqual(menu.music.current_path.name, "hoi3maintheme.ogg")
            old = menu.music
            menu.set_music_volume(.12)
            deadline = time.monotonic() + 3
            while old.status.get("music_volume") != .12 and time.monotonic() < deadline:
                menu.on_update(1 / 60)
                time.sleep(.02)
            self.assertAlmostEqual(old.status["music_volume"], .12, places=2)
            window.show_view(arcade.View())
            self.assertTrue(old.closed)
            self.assertIsNone(menu.music)
            window.show_view(menu)
            self.assertIsNotNone(menu.music)
            self.assertIsNot(old, menu.music)
        finally:
            if menu:
                menu.stop_music()
            window.close()

    def test_real_game_natural_eos_pause_volume_and_cleanup(self):
        import arcade
        import pyglet
        from dynamic_music import DynamicMusic
        from MainGame import Game
        window = arcade.Window(1280, 800, visible=False)
        game = None
        try:
            game = Game(bot_count=1, map_size=32, world_seed=555016)
            window.show_view(game)
            game.stop_music()
            with tempfile.TemporaryDirectory() as root:
                for category in ("economy", "start_war", "war", "bad_times"):
                    folder = Path(root) / category
                    folder.mkdir()
                    with wave.open(str(folder / "test.wav"), "wb") as audio:
                        audio.setnchannels(1)
                        audio.setsampwidth(2)
                        audio.setframerate(22050)
                        audio.writeframes(b"\0\0" * 11025)  # actual half-second EOS
                events = []
                game.music = DynamicMusic(root, report=lambda kind, **data: events.append((kind, data)))
                game.human_player.stability = .72
                for division in game.human_player.divisions:
                    division.last_supply_ratio = 1
                game.simulation_server.set_paused(True)
                game.paused = True  # music also continues in the Escape menu

                def pump_until(predicate):
                    deadline = time.monotonic() + 6
                    while not predicate() and time.monotonic() < deadline:
                        pyglet.clock.tick()
                        pyglet.app.platform_event_loop.dispatch_posted_events()
                        window.dispatch_events()
                        game.on_update(1 / 60)
                        game.on_draw()
                        window.flip()
                        time.sleep(.01)
                    self.assertTrue(predicate(), events)

                pump_until(lambda: game.music.current_category == "economy")
                original_player = game.music.backend.player
                game.politics.war_goals[1, 0] = 30
                game.music.next_review = 0
                game.on_update(1 / 60)
                self.assertIs(game.music.backend.player, original_player)
                game.set_music_volume(.23)
                self.assertAlmostEqual(game.music.backend.player.volume, .23, places=2)
                pump_until(lambda: game.music.current_category == "start_war")
                self.assertFalse(any(kind == "music_error" for kind, _ in events), events)
                self.assertEqual(game.politics.day, 0)
                director = game.music
                window.show_view(arcade.View())
                self.assertTrue(director.closed)
                self.assertTrue(director.backend.closed)
                self.assertIsNone(director.backend.player)
                self.assertIsNone(game.music)
        finally:
            if game is not None:
                game.stop_music()
            window.close()


if __name__ == "__main__":
    unittest.main()
