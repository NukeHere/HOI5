"""Small non-modal news ticker, archive and important-news card."""

import math
import textwrap

import arcade

from news_system import PRIORITIES


NEWS_COLORS = {
    "critical": (242, 112, 104),
    "important": (242, 190, 105),
    "regular": (170, 210, 235),
    "flavor": (170, 188, 202),
}
NEWS_LABELS = {"critical": "Срочно", "important": "Важно", "regular": "Новости", "flavor": "В мире"}


class NewsPanelMixin:
    def initialize_news_ui(self):
        self.news_archive_open = False
        self.news_archive_scroll = 0
        self.news_archive_hits = []
        self.news_popup_id = None
        self.news_popup_scroll = 0
        self.news_popup_queue = []
        self.news_seen_id = 0
        self.news_ticker_index = 0
        self.news_ticker_position = 0.0
        self.news_text_pool = []
        self.news_text_cursor = 0

    def news_visible_items(self):
        if not self.human_player or not hasattr(self, "politics"):
            return []
        return self.politics.news.visible(self.human_player.id)

    def update_news_ui(self, delta_time):
        if not self.human_player or not hasattr(self, "politics"):
            return
        items = self.news_visible_items()
        recent = [item for item in reversed(items) if item.id > self.news_seen_id]
        if recent:
            self.news_seen_id = max(item.id for item in recent)
            self.news_popup_queue.extend(item.id for item in recent if PRIORITIES[item.priority] >= 2)
            self.news_ticker_index = 0
            self.news_ticker_position = 0.0
        if self.news_popup_id is None and not self.news_archive_open and self.news_popup_queue:
            self.news_popup_id = self.news_popup_queue.pop(0)
            self.news_popup_scroll = 0
        if items:
            self.news_ticker_index %= len(items)
            title = self.politics.news.headline_for(items[self.news_ticker_index], self.human_player.id, self.politics)
            length = len(title) + 8
            self.news_ticker_position += max(0, delta_time) * 9
            if self.news_ticker_position >= length:
                self.news_ticker_position = 0.0
                self.news_ticker_index = (self.news_ticker_index + 1) % len(items)

    def news_ticker_rect(self):
        left = 16
        if self.side_panel_progress > .8:
            left = max(left, self.side_panel_rect()[2] + 16)
        for panel in (self.air_wing_list_panel_rect, self.division_list_panel_rect):
            if panel and panel[1] < 54 and panel[1] + panel[3] > 16:
                left = max(left, panel[0] + panel[2] + 10)
        right_margin = 310 if self.window.width >= 1100 else 74
        width = min(560, self.window.width - left - right_margin)
        y = 16
        if width < 200:
            y = 70
            width = min(360, self.window.width - left - 16)
        return left, y, max(120, width), 38

    def news_popup_rect(self):
        width = min(350, self.window.width - 24)
        height = min(220, max(155, self.window.height - 260))
        return self.window.width - width - 14, 104, width, height

    def news_archive_rect(self):
        width = min(400, self.window.width - 24)
        height = min(440, max(260, self.window.height - 215))
        return self.window.width - width - 14, 125, width, height

    def news_item_by_id(self, item_id):
        return next((item for item in self.news_visible_items() if item.id == item_id), None)

    def draw_news_text(self, value, x, y, color=(222, 233, 242), size=12):
        index = self.news_text_cursor
        self.news_text_cursor += 1
        if index == len(self.news_text_pool):
            self.news_text_pool.append(arcade.Text("", x, y, font_size=size, anchor_y="center"))
        label = self.news_text_pool[index]
        rgba = (*color, 255) if len(color) == 3 else color
        changes = [(key, wanted) for key, wanted in (("text", str(value)), ("x", x), ("y", y),
                   ("color", rgba), ("font_size", size)) if getattr(label, key) != wanted]
        if changes:
            with label:
                for key, wanted in changes:
                    setattr(label, key, wanted)
        label.draw()

    def draw_news_overlay(self):
        if self.paused or not self.window:
            return
        self.news_text_cursor = 0
        items = self.news_visible_items()
        x, y, width, height = self.news_ticker_rect()
        arcade.draw_lbwh_rectangle_filled(x, y, width, height, (20, 29, 39, 240))
        arcade.draw_lbwh_rectangle_outline(x, y, width, height, (96, 122, 148), 1)
        compact = width < 360
        content_left = 96 if compact else 155
        self.draw_news_text("Новости" if compact else "Мировые новости", x + 10, y + height / 2,
                            (235, 239, 244), 12)
        if items:
            item = items[self.news_ticker_index % len(items)]
            headline = self.politics.news.headline_for(item, self.human_player.id, self.politics)
            message = f"  •  {headline}  •  "
            offset = int(self.news_ticker_position) % len(message)
            max_chars = max(8, int((width - content_left - 5) / 7))
            stream = message * (2 + math.ceil(max_chars / len(message)))
            self.draw_news_text(stream[offset:offset + max_chars], x + content_left, y + height / 2,
                                NEWS_COLORS[item.priority], 11)
        else:
            self.draw_news_text("Пока нет сообщений", x + content_left, y + height / 2)
        if self.news_archive_open:
            self.draw_news_archive()
        elif self.news_popup_id is not None:
            self.draw_news_popup()

    def draw_news_archive(self):
        x, y, width, height = self.news_archive_rect()
        arcade.draw_lbwh_rectangle_filled(x, y, width, height, (21, 29, 39, 248))
        arcade.draw_lbwh_rectangle_outline(x, y, width, height, (110, 137, 165), 2)
        self.draw_news_text("Мировые новости и события", x + 14, y + height - 25, size=15)
        self.draw_news_text("X", x + width - 26, y + height - 25, size=15)
        items = self.news_visible_items()
        visible = max(1, int((height - 65) // 48))
        self.news_archive_scroll = min(self.news_archive_scroll, max(0, len(items) - visible))
        self.news_archive_hits = []
        for index, item in enumerate(items[self.news_archive_scroll:self.news_archive_scroll + visible]):
            row_y = y + height - 72 - index * 48
            arcade.draw_lbwh_rectangle_filled(x + 10, row_y - 14, width - 20, 42, (35, 46, 59, 235))
            self.draw_news_text(f"{self.politics.date_text(item.day)} · {NEWS_LABELS[item.priority]}",
                                x + 18, row_y + 15, NEWS_COLORS[item.priority], 10)
            title = self.politics.news.headline_for(item, self.human_player.id, self.politics)
            self.draw_news_text(title[:max(20, int((width - 40) / 7))], x + 18, row_y - 3, size=11)
            self.news_archive_hits.append(((x + 10, row_y - 14, width - 20, 42), item.id))
        if len(items) > visible:
            self.draw_news_text(f"{self.news_archive_scroll + 1}–{min(len(items), self.news_archive_scroll + visible)} из {len(items)} · колесо мыши",
                                x + 14, y + 18, (170, 188, 202), 10)

    def draw_news_popup(self):
        item = self.news_item_by_id(self.news_popup_id)
        if item is None:
            return
        x, y, width, height = self.news_popup_rect()
        arcade.draw_lbwh_rectangle_filled(x, y, width, height, (24, 32, 43, 248))
        arcade.draw_lbwh_rectangle_outline(x, y, width, height, NEWS_COLORS[item.priority], 2)
        self.draw_news_text(f"{NEWS_LABELS[item.priority]} · {self.politics.date_text(item.day)}",
                            x + 14, y + height - 24, NEWS_COLORS[item.priority], 11)
        self.draw_news_text("X", x + width - 25, y + height - 24, size=15)
        title = self.politics.news.headline_for(item, self.human_player.id, self.politics)
        for index, line in enumerate(textwrap.wrap(title, max(25, int((width - 30) / 7.5)))[:2]):
            self.draw_news_text(line, x + 14, y + height - 52 - index * 19, size=13)
        body = self.politics.news.body_for(item, self.human_player.id, self.politics)
        lines = textwrap.wrap(body, max(25, int((width - 30) / 7.5))) or [""]
        visible = max(1, int((height - 118) / 18))
        self.news_popup_scroll = min(self.news_popup_scroll, max(0, len(lines) - visible))
        for index, line in enumerate(lines[self.news_popup_scroll:self.news_popup_scroll + visible]):
            self.draw_news_text(line, x + 14, y + height - 100 - index * 18, (205, 219, 232), 11)
        self.draw_news_text("Все новости", x + 14, y + 19, (150, 204, 241), 11)
        if len(lines) > visible:
            self.draw_news_text(f"{self.news_popup_scroll + 1}/{len(lines) - visible + 1} ↓",
                                x + width - 76, y + 19, (170, 188, 202), 10)

    def handle_news_click(self, x, y, button):
        if self.paused or button != arcade.MOUSE_BUTTON_LEFT:
            return False
        if self.news_archive_open:
            rect = self.news_archive_rect()
            if self.point_in_rect(x, y, rect):
                ax, ay, aw, ah = rect
                if x > ax + aw - 46 and y > ay + ah - 48:
                    self.news_archive_open = False
                else:
                    for hit_rect, item_id in self.news_archive_hits:
                        if self.point_in_rect(x, y, hit_rect):
                            self.news_popup_id = item_id
                            self.news_popup_scroll = 0
                            self.news_archive_open = False
                            break
                return True
        elif self.news_popup_id is not None and self.point_in_rect(x, y, self.news_popup_rect()):
            px, py, pw, ph = self.news_popup_rect()
            if x > px + pw - 46 and y > py + ph - 48:
                self.news_popup_id = None
            elif y < py + 42 and x < px + 115:
                self.news_popup_id = None
                self.news_archive_open = True
            return True
        if self.point_in_rect(x, y, self.news_ticker_rect()):
            self.news_archive_open = not self.news_archive_open
            if self.news_archive_open:
                self.news_popup_id = None
            return True
        return False

    def handle_news_scroll(self, x, y, scroll_y):
        if self.paused:
            return False
        if self.news_archive_open and self.point_in_rect(x, y, self.news_archive_rect()):
            self.news_archive_scroll = max(0, self.news_archive_scroll - int(scroll_y * 2))
            return True
        if self.news_popup_id is not None and self.point_in_rect(x, y, self.news_popup_rect()):
            self.news_popup_scroll = max(0, self.news_popup_scroll - int(scroll_y * 2))
            return True
        return False
