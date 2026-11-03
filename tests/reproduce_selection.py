"""Real OpenGL selection smoke test; writes timings without replacing user evidence."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="logs/diagnostics/selection-after.json")
    parser.add_argument("--cycles", type=int, default=60)
    parser.add_argument("--days", type=int, default=0)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".stacks.txt").open("w") as stacks:
        faulthandler.dump_traceback_later(15, file=stacks, repeat=True)
        random.seed(555016)
        window = arcade.Window(1920, 1080, visible=False)
        try:
            game = Game(bot_count=5, map_size=50, world_seed=555016)
            window.show_view(game)
            game.simulation_server.set_paused(True)
            game.world_camera.zoom = .55
            tile = game.human_player.divisions[0].tile
            game.target_camera_x, game.target_camera_y = tile.center_x, tile.center_y
            game.world_camera.position = (tile.center_x, tile.center_y)
            game.set_map_layer("supply")
            game.air_defense_overlay_enabled = True
            game.on_update(1 / 60)
            if args.days:
                game.simulation_server.set_paused(False)
                game.simulation_server.set_speed_level(5)
                while game.politics.day < args.days:
                    faulthandler.cancel_dump_traceback_later()
                    faulthandler.dump_traceback_later(15, file=stacks, repeat=True)
                    game.on_update(.25)
                    game.on_draw()
                    window.flip()
                    window.dispatch_events()
                game.simulation_server.set_paused(True)
            timings = []
            font_changes = []
            selected = []
            for cycle in range(args.cycles):
                faulthandler.cancel_dump_traceback_later()
                faulthandler.dump_traceback_later(15, file=stacks, repeat=True)
                game.news_popup_id = None
                game.news_popup_queue.clear()
                game.set_selected_divisions([])
                for mode in ("click", "box"):
                    game.on_update(1 / 60)
                    game.on_draw()
                    window.flip()
                    started = time.perf_counter()
                    if mode == "click":
                        game.update_division_display_positions()
                        x, y = game.division_screen_position(game.human_player.divisions[0])
                        game.on_mouse_press(x, y, arcade.MOUSE_BUTTON_LEFT, 0)
                        game.on_mouse_release(x, y, arcade.MOUSE_BUTTON_LEFT, 0)
                    else:
                        # Start outside the division list and command bar.
                        game.on_mouse_press(500, 200, arcade.MOUSE_BUTTON_LEFT, 0)
                        assert game.division_selection_drag_active, "box start intercepted"
                        game.on_mouse_drag(1600, 900, 1100, 700, arcade.MOUSE_BUTTON_LEFT, 0)
                        game.on_mouse_release(1600, 900, arcade.MOUSE_BUTTON_LEFT, 0)
                        assert not game.division_selection_drag_active
                    selected.append(len(game.selected_division_ids))
                    assert selected[-1] > 0, (mode, cycle)
                    old_fonts = [label.font_size for label in game.ui_text_pool]
                    game.on_draw()
                    window.flip()
                    font_changes.append(sum(label.font_size != size for label, size in zip(game.ui_text_pool, old_fonts)))
                    timings.append(time.perf_counter() - started)
                    window.dispatch_events()
            arcade.get_image().save(output.with_suffix(".png"))
            assert sum(font_changes) == 0, "selection rebuilt existing label fonts"
            result = dict(cycles=args.cycles, days=game.politics.day, selections=len(selected), min_selected=min(selected),
                          peak_seconds=max(timings), mean_seconds=sum(timings)/len(timings),
                          font_size_changes=sum(font_changes), labels=len(game.ui_text_pool))
            output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result), flush=True)
        finally:
            faulthandler.cancel_dump_traceback_later()
            window.close()


if __name__ == "__main__":
    main()
