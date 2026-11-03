"""Render a real Arcade game through day 30; retain slow frames and hang stacks."""
import argparse
import faulthandler
import json
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("PYGLET_AUDIO", "silent")
import arcade
from MainGame import Game
from Constants import MAP_LAYERS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=601451)
    parser.add_argument("--bots", type=int, default=5)
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--panel", default="")
    parser.add_argument("--news-layers", action="store_true")
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    directory = Path("logs/diagnostics") / f"gui-{args.seed}-{args.size}-{args.bots}-{args.panel or 'map'}"
    if args.label:
        directory = directory.with_name(directory.name + "-" + args.label)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "stacks.txt").open("w") as stacks, (directory / "frames.jsonl").open("w", encoding="utf-8") as frames:
        faulthandler.enable(stacks)
        faulthandler.dump_traceback_later(30, file=stacks, repeat=True)
        random.seed(args.seed)
        window = arcade.Window(1920, 1080, visible=False)
        try:
            game = Game(bot_count=args.bots, map_size=args.size, world_seed=args.seed)
            window.show_view(game)
            game.politics.news.start_log(directory / "news.txt", game.simulation_server.current_time, args.seed, game.players)
            game.world_camera.zoom = .45
            game.last_visible_update = 0
            game.profiler.set_visible(True)
            game.simulation_server.set_paused(False)
            game.simulation_server.set_speed_level(5)
            if args.panel:
                game.open_top_panel(args.panel)
                game.side_panel_progress = 1
            peak = {"update": 0., "draw": 0.}
            samples = []
            previous_day = -1
            frame_number = 0
            def draw():
                window.dispatch_events()
                game.on_draw()
                window.flip()
            while game.politics.day < args.days:
                if args.news_layers:
                    if frame_number % 15 == 0:
                        rect = game.map_layer_button_rect()
                        game.on_mouse_press(rect[0] + 8, rect[1] + 8, arcade.MOUSE_BUTTON_LEFT, 0)
                        game.map_layer_menu_progress = 1
                        choices = [i for i, (key, title, enabled) in enumerate(MAP_LAYERS) if enabled and key != "weather"]
                        index = choices[(frame_number // 15) % len(choices)]
                        rect = game.map_layer_option_rects()[index]
                        game.on_mouse_press(rect[0] + 8, rect[1] + 8, arcade.MOUSE_BUTTON_LEFT, 0)
                        if not game.news_archive_open:
                            rect = game.news_ticker_rect()
                            game.on_mouse_press(rect[0] + 8, rect[1] + 8, arcade.MOUSE_BUTTON_LEFT, 0)
                    elif frame_number % 15 == 1 and game.news_archive_open:
                        x, y, w, h = game.news_archive_rect()
                        game.on_mouse_press(x + w - 25, y + h - 25, arcade.MOUSE_BUTTON_LEFT, 0)
                for name, operation in (("update", lambda: game.on_update(1 / 30)), ("draw", draw)):
                    faulthandler.cancel_dump_traceback_later()
                    faulthandler.dump_traceback_later(8, file=stacks, repeat=True)
                    started = time.perf_counter()
                    operation()
                    elapsed = time.perf_counter() - started
                    peak[name] = max(peak[name], elapsed)
                    if elapsed > .1:
                        row = dict(time=str(game.simulation_server.current_time), phase=name, seconds=elapsed,
                                   timings=game.profiler.latest.get(name, {}))
                        frames.write(json.dumps(row) + "\n")
                        frames.flush()
                    samples.append(elapsed)
                if game.politics.day != previous_day:
                    previous_day = game.politics.day
                    print(str(game.simulation_server.current_time), "peaks", peak, flush=True)
                frame_number += 1
            (directory / "summary.json").write_text(json.dumps(dict(status="completed", days=game.politics.day,
                seed=args.seed, size=args.size, bots=args.bots, panel=args.panel, peak_seconds=peak), indent=2), encoding="utf-8")
        finally:
            faulthandler.cancel_dump_traceback_later()
            window.close()


if __name__ == "__main__":
    main()
