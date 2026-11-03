"""Actual empty-camera render loop on the requested 150x150 / 11-bot world."""
import json
from collections import Counter
import os
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("PYGLET_AUDIO", "silent")
import arcade
from MainGame import Game
from map_generation_job import MapGenerationJob


def main():
    root = Path(os.environ.get("HOI_BENCH_OUTPUT", "logs/diagnostics/performance-2026-11-03"))
    root.mkdir(parents=True, exist_ok=True)
    window = arcade.Window(1920, 1080, visible=False)
    game = None
    job = None
    try:
        random.seed(146591)
        generation_started = time.perf_counter()
        job = MapGenerationJob(150, 146591)
        data = None
        generation_pids = []
        while data is None:
            if job.executor._processes:
                generation_pids = [p.pid for p in job.executor._processes.values()]
            data = job.poll()
            window.dispatch_events()
            time.sleep(.01)
        generation_seconds = time.perf_counter() - generation_started
        game = Game(bot_count=11, map_size=150, world_seed=146591, map_data=data)
        window.show_view(game)
        game.profiler.set_visible(os.environ.get("HOI_BENCH_HIDE_F3") != "1")
        game.profiler.enabled = True
        game.world_camera.zoom = 1.5
        # Empty distant corner, without armies or aerial icons in the viewport.
        game.target_camera_x, game.target_camera_y = game.hex_grid[-1].position
        game.world_camera.position = (game.target_camera_x, game.target_camera_y)
        result = []
        delta = 1 / 60
        for speed in (1, 3, 5):
            game.simulation_server.set_speed_level(speed)
            game.simulation_server.set_paused(False)
            frames, updates, draws = [], [], []
            phases = Counter()
            for frame in range(150):
                started = time.perf_counter()
                window.dispatch_events()
                stamp = time.perf_counter()
                game.on_update(delta)
                updates.append(time.perf_counter() - stamp)
                stamp = time.perf_counter()
                game.on_draw()
                draws.append(time.perf_counter() - stamp)
                window.flip()
                delta = max(1 / 60, time.perf_counter() - started)
                if frame >= 20:
                    frames.append(time.perf_counter() - started)
                    for phase, samples in game.profiler.latest.items():
                        for label, seconds in samples.items():
                            phases[f"{phase}.{label}"] += seconds * 1000
            result.append(dict(speed=speed, game_time=str(game.simulation_server.current_time),
                mean_frame_ms=statistics.mean(frames) * 1000, p95_frame_ms=sorted(frames)[int(len(frames) * .95)] * 1000,
                update_max_ms=max(updates) * 1000, draw_mean_ms=statistics.mean(draws) * 1000,
                mean_stage_ms={label: round(ms / len(frames), 3) for label, ms in phases.most_common(20)},
                worker_results=len(game.ai_system.workers.results), worker_errors=game.ai_system.workers.errors))
            print(json.dumps(result[-1]), flush=True)
        workers = game.ai_system.workers
        result.append(dict(worker_pids=[p.pid for p in workers.executor._processes.values()], main_pid=os.getpid(),
                           generation_seconds=generation_seconds, generation_pids=generation_pids))
        assert workers.results and not workers.errors, workers.errors
        game.simulation_server.set_paused(True)
        game.on_key_press(arcade.key.F4, 0)
        game.on_draw()
        arcade.get_image().save(root / "large-f4.png")
        (root / "large-gui.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        if game:
            game.stop_background_services()
        if job:
            job.close()
        window.close()


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    main()
