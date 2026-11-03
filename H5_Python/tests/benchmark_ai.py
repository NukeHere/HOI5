"""Reproducible runtime smoke and timings: python tests/benchmark_ai.py."""
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["PYGLET_AUDIO"] = "silent"
import arcade
from MainGame import Game


def run(bots, enabled, days):
    random.seed(314159)
    window = arcade.Window(1280, 800, visible=False)
    try:
        game = Game(bot_count=bots, map_size=50)
        window.show_view(game)
        game.ai_system.enabled = enabled
        game.profiler.set_visible(True)
        server = game.simulation_server
        server.set_speed_level(5)
        server.set_paused(False)
        samples, ai_samples, frames = [], [], []
        for day in range(days):
            day_time, ai_time = 0, 0
            for _ in range(15):
                started = time.perf_counter()
                game.on_update(1 / 60)
                duration = (time.perf_counter() - started) * 1000
                frames.append(duration)
                day_time += duration
                ai_time += game.profiler.latest_ms("update", "ai_total")
            samples.append(day_time)
            ai_samples.append(ai_time)
        game.on_draw()
        statuses = {}
        accepted = 0
        for bot in game.ai_system.bots.values():
            for task in bot.tasks:
                statuses[task.kind + ":" + task.status] = statuses.get(task.kind + ":" + task.status, 0) + 1
            accepted += sum(h["kind"] == "command" and h["accepted"] for h in bot.history)
        return dict(bots=bots, enabled=enabled, days=days, tiles=len(game.hex_lookup),
                    mean_day_ms=round(statistics.mean(samples), 3),
                    p95_day_ms=round(sorted(samples)[min(len(samples)-1, int(len(samples)*.95))], 3),
                    peak_day_ms=round(max(samples), 3), ai_mean_day_ms=round(statistics.mean(ai_samples), 3),
                    p95_update_ms=round(sorted(frames)[int(len(frames)*.95)], 3),
                    peak_update_ms=round(max(frames), 3),
                    ai_peak_day_ms=round(max(ai_samples), 3), accepted_commands_in_bounded_history=accepted,
                    tasks=statuses, news_log_error=game.politics.news.log_error,
                    courses={game.player_by_id(b.country_id).name: b.course for b in game.ai_system.bots.values()})
    finally:
        window.close()


results = []
for bot_count in (3, 11):
    for enabled in (False, True):
        result = run(bot_count, enabled, 35)
        results.append(result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
Path(".codex-work/ai-runtime-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
