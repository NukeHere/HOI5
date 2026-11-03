from pathlib import Path
main = Path('MainGame.py')
text = main.read_text(encoding='utf-8')
text = text.replace('''        self.trade_batch = Batch()
        self.trade_text_pool = []
        self.trade_text_pool_cursor = 0
        self.trade_text_pool_max_used = 0
''', '''        self.trade_batch = Batch()
        self.trade_text_pool = []
        self.trade_text_pool_cursor = 0
        self.trade_text_pool_max_used = 0
        self.trade_table_shape_list = arcade.shape_list.ShapeElementList()
        self.trade_table_shape_cache_key = None
        self.trade_table_shape_actions = []
''')
main.write_text(text, encoding='utf-8', newline='\n')

path = Path('ui_panels.py')
text = path.read_text(encoding='utf-8')
marker = '''    def scroll_trade_rows(self, amount):
        rows = self.trade_rows()
        panel_x, panel_y, _panel_width, panel_height = self.side_panel_rect()
        table_y = panel_y + panel_height - 254
        row_height = 28
        max_rows = max(6, int((table_y - 28 - (panel_y + 28)) / row_height))
        max_scroll = max(0, len(rows) - max_rows)
        old_index = self.trade_scroll_index
        self.trade_scroll_index = max(0, min(max_scroll, self.trade_scroll_index + int(amount)))
        return self.trade_scroll_index != old_index

'''
insert = marker + '''    @staticmethod
    def append_trade_rect_shapes(shapes, rect, fill, border=None, border_width=1):
        x, y, width, height = rect
        center_x = x + width / 2
        center_y = y + height / 2
        shapes.append(arcade.shape_list.create_rectangle_filled(center_x, center_y, width, height, fill))
        if border is not None:
            shapes.append(arcade.shape_list.create_rectangle_outline(center_x, center_y, width, height, border, border_width))

    def rebuild_trade_table_shapes(self, table_x, panel_y, panel_width, table_y, rows, visible_rows, start_y, row_height, max_rows, max_scroll):
        shapes = arcade.shape_list.ShapeElementList()
        actions = []
        for index, row in enumerate(visible_rows):
            row_y = start_y - index * row_height
            row_number = self.trade_scroll_index + index
            fill = (24, 32, 42, 118) if row_number % 2 == 0 else (30, 38, 48, 118)
            self.append_trade_rect_shapes(shapes, (table_x, row_y - 4, panel_width - 36, row_height), fill)
            button_specs = [
                ("-", "buy", -TRADE_CONTRACT_STEP, table_x + panel_width - 156),
                ("+", "buy", TRADE_CONTRACT_STEP, table_x + panel_width - 128),
                ("-", "sell", -TRADE_CONTRACT_STEP, table_x + panel_width - 82),
                ("+", "sell", TRADE_CONTRACT_STEP, table_x + panel_width - 54),
            ]
            for label, mode, delta, button_x in button_specs:
                rect = (button_x, row_y - 1, 24, 20)
                actions.append((rect, row["key"], mode, delta))
                border = (124, 178, 232) if mode == "buy" else (180, 210, 128)
                self.append_trade_rect_shapes(shapes, rect, (42, 62, 82, 210), border)
                center_x = rect[0] + rect[2] / 2
                center_y = rect[1] + rect[3] / 2
                shapes.append(arcade.shape_list.create_line(center_x - 5, center_y, center_x + 5, center_y, arcade.color.WHITE, 2))
                if label == "+":
                    shapes.append(arcade.shape_list.create_line(center_x, center_y - 5, center_x, center_y + 5, arcade.color.WHITE, 2))
        if len(rows) > max_rows:
            track_x = self.side_panel_rect()[0] + self.side_panel_rect()[2] - 18
            track_y = panel_y + 46
            track_height = max(40, table_y - 48 - track_y)
            self.append_trade_rect_shapes(shapes, (track_x, track_y, 4, track_height), (42, 52, 64, 180))
            thumb_height = max(24, track_height * max_rows / len(rows))
            thumb_y = track_y + (track_height - thumb_height) * (1 - self.trade_scroll_index / max(1, max_scroll))
            self.append_trade_rect_shapes(shapes, (track_x - 2, thumb_y, 8, thumb_height), (130, 154, 184, 220))
        self.trade_table_shape_list = shapes
        self.trade_table_shape_actions = actions

    def draw_trade_table_shapes(self, table_x, panel_y, panel_width, table_y, rows, visible_rows, start_y, row_height, max_rows, max_scroll):
        shape_key = (
            round(table_x, 2),
            round(panel_y, 2),
            round(panel_width, 2),
            round(table_y, 2),
            self.trade_panel_category,
            self.trade_scroll_index,
            max_rows,
            len(rows),
            tuple(row["key"] for row in visible_rows),
        )
        if self.trade_table_shape_cache_key != shape_key:
            self.rebuild_trade_table_shapes(table_x, panel_y, panel_width, table_y, rows, visible_rows, start_y, row_height, max_rows, max_scroll)
            self.trade_table_shape_cache_key = shape_key
        self.trade_action_rects = list(self.trade_table_shape_actions)
        self.trade_table_shape_list.draw()

'''
if marker not in text:
    raise SystemExit('scroll_trade_rows marker not found')
text = text.replace(marker, insert)
# Draw cached shapes after visible rows are known.
old = '''        visible_rows = rows[self.trade_scroll_index:self.trade_scroll_index + max_rows]
        with self.profiler.measure("trade_rows"):
'''
new = '''        visible_rows = rows[self.trade_scroll_index:self.trade_scroll_index + max_rows]
        with self.profiler.measure("trade_table_shapes"):
            self.draw_trade_table_shapes(table_x, panel_y, panel_width, table_y, rows, visible_rows, y, row_height, max_rows, max_scroll)
        with self.profiler.measure("trade_rows"):
'''
if old not in text:
    raise SystemExit('visible_rows marker not found')
text = text.replace(old, new, 1)
# Remove immediate row background.
text = text.replace('''                fill = (24, 32, 42, 118) if row_number % 2 == 0 else (30, 38, 48, 118)
                arcade.draw_lbwh_rectangle_filled(table_x, row_y - 4, panel_width - 36, row_height, fill)
                for value, color, offset in row["display_values"]:
''', '''                for value, color, offset in row["display_values"]:
''', 1)
# Remove immediate button drawing; actions are produced by cached shapes.
old = '''        with self.profiler.measure("trade_buttons"):
            for index, row in enumerate(visible_rows):
                row_y = y - index * row_height
                button_specs = [
                    ("-", "buy", -TRADE_CONTRACT_STEP, table_x + panel_width - 156),
                    ("+", "buy", TRADE_CONTRACT_STEP, table_x + panel_width - 128),
                    ("-", "sell", -TRADE_CONTRACT_STEP, table_x + panel_width - 82),
                    ("+", "sell", TRADE_CONTRACT_STEP, table_x + panel_width - 54),
                ]
                for label, mode, delta, button_x in button_specs:
                    rect = (button_x, row_y - 1, 24, 20)
                    self.trade_action_rects.append((rect, row["key"], mode, delta))
                    fill = (42, 62, 82, 210)
                    if mode == "buy":
                        border = (124, 178, 232)
                    else:
                        border = (180, 210, 128)
                    arcade.draw_lbwh_rectangle_filled(*rect, fill)
                    arcade.draw_lbwh_rectangle_outline(*rect, border, 1)
                    center_x = rect[0] + rect[2] / 2
                    center_y = rect[1] + rect[3] / 2
                    arcade.draw_line(center_x - 5, center_y, center_x + 5, center_y, arcade.color.WHITE, 2)
                    if label == "+":
                        arcade.draw_line(center_x, center_y - 5, center_x, center_y + 5, arcade.color.WHITE, 2)

'''
new = '''        with self.profiler.measure("trade_buttons"):
            pass

'''
if old not in text:
    raise SystemExit('trade buttons block not found')
text = text.replace(old, new, 1)
# Remove immediate scrollbar drawing from footer; it is in cached shapes now.
old = '''            if len(rows) > max_rows:
                track_x = panel_x + panel_width - 18
                track_y = panel_y + 46
                track_height = max(40, table_y - 48 - track_y)
                arcade.draw_lbwh_rectangle_filled(track_x, track_y, 4, track_height, (42, 52, 64, 180))
                thumb_height = max(24, track_height * max_rows / len(rows))
                thumb_y = track_y + (track_height - thumb_height) * (1 - self.trade_scroll_index / max(1, max_scroll))
                arcade.draw_lbwh_rectangle_filled(track_x - 2, thumb_y, 8, thumb_height, (130, 154, 184, 220))

            legend_y = panel_y + 20
'''
new = '''            legend_y = panel_y + 20
'''
if old not in text:
    raise SystemExit('trade footer scrollbar block not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8', newline='\n')
