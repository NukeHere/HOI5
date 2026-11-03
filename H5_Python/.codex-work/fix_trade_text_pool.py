from pathlib import Path
path = Path('MainGame.py')
text = path.read_text(encoding='utf-8')
text = text.replace('''        self.trade_panel_cache = None
        self.trade_text_pool = []
        self.trade_text_pool_cursor = 0
''', '''        self.trade_panel_cache = None
        self.trade_batch = Batch()
        self.trade_text_pool = []
        self.trade_text_pool_cursor = 0
        self.trade_text_pool_max_used = 0
''')
old = '''    def begin_trade_text_frame(self):
        # Trade text is routed through the shared UI batch. Keeping this
        # wrapper preserves the trade panel call sites without per-label draws.
        pass

    def draw_trade_text(
        self,
        text,
        x,
        y,
        color=arcade.color.WHITE,
        font_size=12,
        anchor_x="left",
        anchor_y="baseline",
    ):
        self.draw_ui_text(
            text,
            x,
            y,
            color,
            font_size,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
        )

    def clear_unused_trade_text(self):
        pass
'''
new = '''    def begin_trade_text_frame(self):
        self.trade_text_pool_cursor = 0

    def draw_trade_text(
        self,
        text,
        x,
        y,
        color=arcade.color.WHITE,
        font_size=12,
        anchor_x="left",
        anchor_y="baseline",
    ):
        index = self.trade_text_pool_cursor
        self.trade_text_pool_cursor += 1

        if index >= len(self.trade_text_pool):
            self.trade_text_pool.append(
                arcade.Text(
                    "",
                    0,
                    0,
                    color,
                    font_size,
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                    batch=self.trade_batch,
                )
            )

        label = self.trade_text_pool[index]
        new_text = str(text)
        if label.text != new_text:
            label.text = new_text
        if label.font_size != font_size:
            label.font_size = font_size
        if label.anchor_x != anchor_x:
            label.anchor_x = anchor_x
        if label.anchor_y != anchor_y:
            label.anchor_y = anchor_y
        if label.color != color:
            label.color = color
        label.x = x
        label.y = y

    def clear_unused_trade_text(self):
        for index in range(self.trade_text_pool_cursor, self.trade_text_pool_max_used):
            if index < len(self.trade_text_pool) and self.trade_text_pool[index].text:
                self.trade_text_pool[index].text = ""
        self.trade_text_pool_max_used = max(self.trade_text_pool_max_used, self.trade_text_pool_cursor)
        self.trade_batch.draw()
'''
if old not in text:
    raise SystemExit('trade text block not found')
text = text.replace(old, new)
path.write_text(text, encoding='utf-8', newline='\n')
