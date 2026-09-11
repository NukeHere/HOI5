import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import arcade
from MainGame import Game

window = arcade.Window(800, 600, "HOI5 trade profile", visible=False)
try:
    game = Game(difficulty="Normal", bot_count=3, map_size=50)
    game.active_top_panel_key = "trade"
    samples = []
    for i in range(30):
        start = time.perf_counter()
        snap = game.trade_panel_snapshot()
        samples.append((time.perf_counter() - start) * 1000)
    print("rows", len(snap.get("rows", [])))
    print("first_ms", round(samples[0], 3))
    print("second_ms", round(samples[1], 3))
    print("avg_after_first_ms", round(sum(samples[1:]) / max(1, len(samples)-1), 3))
    print("max_after_first_ms", round(max(samples[1:]), 3))
finally:
    window.close()
