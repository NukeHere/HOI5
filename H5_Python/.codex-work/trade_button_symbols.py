from pathlib import Path
path = Path('ui_panels.py')
text = path.read_text(encoding='utf-8')
old = '''                    arcade.draw_lbwh_rectangle_filled(*rect, fill)
                    arcade.draw_lbwh_rectangle_outline(*rect, border, 1)
                    self.draw_trade_text(label, rect[0] + rect[2] / 2, rect[1] + rect[3] / 2,
                                         arcade.color.WHITE, 12, anchor_x="center", anchor_y="center")
'''
new = '''                    arcade.draw_lbwh_rectangle_filled(*rect, fill)
                    arcade.draw_lbwh_rectangle_outline(*rect, border, 1)
                    center_x = rect[0] + rect[2] / 2
                    center_y = rect[1] + rect[3] / 2
                    arcade.draw_line(center_x - 5, center_y, center_x + 5, center_y, arcade.color.WHITE, 2)
                    if label == "+":
                        arcade.draw_line(center_x, center_y - 5, center_x, center_y + 5, arcade.color.WHITE, 2)
'''
if old not in text:
    raise SystemExit('trade button text block not found')
path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')
