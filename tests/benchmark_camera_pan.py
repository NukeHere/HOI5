"""Paused scene: same visible divisions while the camera moves a fraction of a pixel."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("PYGLET_AUDIO", "silent")
import arcade
from MainGame import Game


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--unit-motion", action="store_true")
    parser.add_argument("--live", action="store_true", help="Compare paused drawing with real speed-5 updates")
    args = parser.parse_args()
    window = arcade.Window(1920, 1080, visible=False)
    game = None
    try:
        game = Game(bot_count=11, map_size=100 if args.unit_motion or args.live else 150, world_seed=146591)
        window.show_view(game)
        game.stop_background_services()
        game.simulation_server.set_paused(True)
        game.world_camera.zoom = .05
        x1, y1, x2, y2 = game.map_bounds
        game.world_camera.position = ((x1 + x2) / 2, (y1 + y2) / 2)
        game.visible_tiles.clear()
        game.profiler.set_visible(True)
        results = []
        first_ids = {d.id for d in game.visible_divisions()}
        for moving in (False, True):
            if args.live:
                game.simulation_server.set_speed_level(5)
                game.simulation_server.set_paused(not moving)
            samples = []
            for index in range(40):
                if args.live:
                    game.on_update(.0625)
                elif moving:
                    if args.unit_motion:
                        for division in game.divisions:
                            division.x += 3
                            division.organization = max(0, division.organization - .2)
                    else:
                        x, y = game.world_camera.position
                        game.world_camera.position = (x + 4, y)
                if not args.live:
                    assert first_ids == {d.id for d in game.visible_divisions()}
                start = time.perf_counter()
                game.on_draw()
                assert all(len({game.division_icon_key(d) for d in group["divisions"]}) == 1
                           for group in game.division_groups)
                window.flip()
                if index >= 10:
                    samples.append(dict(total=(time.perf_counter() - start) * 1000,
                        divisions=game.profiler.latest_ms("draw", "world_divisions"),
                        groups=game.profiler.latest_ms("draw", "ui_division_groups"),
                        air=game.profiler.latest_ms("draw", "world_air_assets")))
            results.append(dict(moving=moving, visible_divisions=len(first_ids),
                mean_ms={k: statistics.mean(row[k] for row in samples) for k in samples[0]}))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2))
        print(json.dumps(results), flush=True)
    finally:
        if game:
            game.stop_background_services()
        window.close()


if __name__ == "__main__":
    main()
