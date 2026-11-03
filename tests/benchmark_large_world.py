"""Fixed large-world CPU workload, independent of camera and graphics."""
import argparse
import ast
import cProfile
import io
import json
from pathlib import Path
import pstats
import sys
import time
import inspect
import textwrap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headless_simulation import HeadlessGame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="logs/diagnostics/performance-2026-11-03/before")
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--size", type=int, default=150)
    parser.add_argument("--legacy-expansion", action="store_true", help="Keep pre-fix neutral expansion for CPU comparisons")
    args = parser.parse_args()
    if args.legacy_expansion:
        import ai_system
        source = textwrap.dedent(inspect.getsource(ai_system.CountryAI.economic_tasks))
        tree = ast.parse(source)
        replacement = ast.parse('''
if bot.course == "development":
    expansion = []
    focus = game.player_by_id(bot.expansion_target) if bot.expansion_target is not None else None
    for tile in player.tiles:
        for neighbor in self.geography.neighbors.get(game.tile_key(tile), ()):
            if neighbor.owner is None and not game.is_water_tile(neighbor):
                key = game.tile_key(neighbor)
                score = .5 + getattr(neighbor, "passability", 0)
                score += game.agriculture_score(neighbor) * .3
                if focus and focus.tiles:
                    score += 8 / (1 + game.hex_distance(neighbor, focus.capital_tile))
                expansion.append((score, key))
    key = choose_close(bot.rng, expansion)
    if key is not None and not any(t.kind == "claim" and t.status in ("planned", "blocked", "executing") for t in bot.tasks):
        self.task(bot, "claim", tile_key=key)
''').body[0]
        method = tree.body[0]
        index = next(i for i, node in enumerate(method.body) if isinstance(node, ast.If)
                     and ast.unparse(node.test) == "bot.course == 'development'")
        method.body[index] = replacement
        namespace = dict(vars(ai_system))
        exec(compile(ast.fix_missing_locations(tree), "legacy-expansion-benchmark", "exec"), namespace)
        ai_system.CountryAI.economic_tasks = namespace["economic_tasks"]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    game = HeadlessGame(seed=146591, countries=12, map_size=args.size)
    initialization = time.perf_counter() - started
    timings = []
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.days):
        started = time.perf_counter()
        game.advance_day()
        timings.append(time.perf_counter() - started)
    profiler.disable()
    profiler.dump_stats(str(path.with_suffix(".prof")))
    report = io.StringIO()
    pstats.Stats(profiler, stream=report).strip_dirs().sort_stats("cumtime").print_stats(45)
    path.with_suffix(".txt").write_text(report.getvalue(), encoding="utf-8")
    result = dict(days=game.politics.day, size=args.size, countries=12, legacy_expansion=args.legacy_expansion,
                  initialization_seconds=initialization, mean_day_seconds=sum(timings)/len(timings),
                  max_day_seconds=max(timings), divisions=len(game.divisions),
                  territory=sum(len(p.tiles) for p in game.players))
    path.with_suffix(".json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
