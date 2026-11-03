"""Fixed aviation fixture; real GUI render/update timings at distant zoom."""
import argparse
import ast
import json
import os
from pathlib import Path
import statistics
import random
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("PYGLET_AUDIO", "silent")
import arcade
from MainGame import Game

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="logs/diagnostics/zoom-benchmark.json")
parser.add_argument("--compare", action="store_true", help="Compare HEAD's four render methods on this same game fixture")
args = parser.parse_args()
window = arcade.Window(1920, 1080, visible=False)
try:
    random.seed(424099)
    game = Game(bot_count=5, map_size=50, world_seed=424099)
    window.show_view(game)
    game.simulation_server.set_paused(True)
    for player in game.players:
        for kind in ("multirole_fighter", "attack_helicopter"):
            wing = game.create_air_wing_from_stockpile(player, kind, 8)
            if wing:
                wing.enabled_missions = ["cas"] if kind == "attack_helicopter" else ["patrol", "intercept", "cas"]
                wing.mission = wing.enabled_missions[0]
                wing.operation_area_tile_keys = [game.tile_key(t) for t in player.tiles]
    game.profiler.set_visible(True)
    current = {name: getattr(game, name) for name in ("draw_air_assets", "get_visible_tiles", "update_draw_list", "use_overview_lod")}
    policies = [("after", current)]
    if args.compare:
        import MainGame
        source = subprocess.check_output(["git", "show", "HEAD:MainGame.py"]).decode("utf-8-sig")
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Game")
        methods = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in current]
        namespace = dict(vars(MainGame))
        exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])), "HEAD:MainGame.py", "exec"), namespace)
        policies.insert(0, ("before", {name: namespace[name].__get__(game, type(game)) for name in current}))
    results = []
    for policy, methods in policies:
      for name, method in methods.items():
        setattr(game, name, method)
      for zoom in (.45, .25, .20000000000000036, .15):
        game.world_camera.zoom = zoom
        game.target_camera_x = (game.map_bounds[0] + game.map_bounds[2]) / 2
        game.target_camera_y = (game.map_bounds[1] + game.map_bounds[3]) / 2
        game.world_camera.position = (game.target_camera_x, game.target_camera_y)
        timings = []
        for frame in range(40):
            game.last_visible_update = 0
            game.on_update(1/60)
            game.on_draw()
            window.flip()
            if frame >= 8:
                timings.append(dict(air=game.profiler.latest_ms("draw", "world_air_assets"),
                    visible=game.profiler.latest_ms("update", "visible_tiles_refresh"),
                    draw=game.profiler.latest_ms("draw", "total")))
        results.append(dict(policy=policy, zoom=zoom, overview=game.use_overview_lod(), wings=len(game.air_wings),
            visible_tiles=len(game.visible_tiles),
            mean_ms={k: round(statistics.mean(t[k] for t in timings), 3) for k in timings[0]},
            p95_ms={k: round(sorted(t[k] for t in timings)[int(len(timings)*.95)], 3) for k in timings[0]}))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results), flush=True)
finally:
    window.close()
