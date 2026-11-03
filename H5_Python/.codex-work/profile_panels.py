import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import arcade
from MainGame import Game

window = arcade.Window(1280, 720, "HOI5 panel profile", visible=False)
try:
    game = Game(difficulty="Normal", bot_count=3, map_size=50)
    window.show_view(game)
    game.side_panel_progress = 1.0
    panel = game.side_panel_rect()
    def measure_panel(name, func, repeats=30):
        samples = []
        for _ in range(repeats):
            game.begin_ui_text_frame()
            start = time.perf_counter()
            func(*panel)
            game.draw_ui_text_batch()
            samples.append((time.perf_counter() - start) * 1000)
        after_first = samples[1:]
        print(name, "first", round(samples[0], 3), "avg_after_first", round(sum(after_first)/len(after_first), 3), "max_after_first", round(max(after_first), 3))
    game.trade_panel_snapshot()
    game.resource_rows()
    measure_panel("trade", game.draw_trade_panel_content)
    measure_panel("resources", game.draw_resources_panel_content)
finally:
    window.close()
