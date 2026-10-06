"""Centered country detail windows with independent navigation and text caches."""

from collections import OrderedDict
from dataclasses import dataclass
import textwrap
import time

import arcade
from pyglet.graphics import Batch

from country_power import power_ranking, relative_power
from politics_system import ACTIONS, GROUPS, SOCIAL_GROUPS, FACTIONS, SUPPORT_GROUPS

INK = (224, 234, 244)
MUTED = (163, 184, 202)
GREEN = (133, 213, 169)
GOLD = (238, 199, 111)
BLUE = (126, 186, 235)
RED = (234, 146, 136)


@dataclass
class DetailRow:
    kind: str
    label: str
    value: str = ""
    ratio: float = 0
    color: tuple = INK
    action: tuple | None = None


class CountryDialogMixin:
    def initialize_country_dialog(self):
        self.country_dialog = None
        self.country_dialog_scroll = 0
        self.country_dialog_stack = []
        self.country_dialog_hits = []
        self.country_dialog_cache = None
        self.country_dialog_views = OrderedDict()
        self.country_slider_drag = False
        self.country_export_percent = 100
        self.country_dialog_error = ""

    def country_dialog_rect(self):
        width = min(720, self.window.width - 40)
        height = min(660, self.window.height - 108)
        return ((self.window.width - width) / 2,
                (self.window.height - height) / 2, width, height)

    def open_country_dialog(self, section, action=None):
        if self.country_dialog and action:
            self.country_dialog_stack.append((self.country_dialog, self.country_dialog_scroll))
        else:
            self.country_dialog_stack = []
        self.country_dialog = section
        self.country_dialog_scroll = 0
        self.country_card_action = action
        self.country_amount_focus = action in ("aid", "loan")
        self.country_dialog_cache = None
        self.country_dialog_error = ""
        self.country_dialog_hits = []
        self.country_slider_drag = False
        player = self.player_by_id(self.country_card_id)
        if action == "exports":
            self.country_export_percent = round(player.politics.export_capacity_factor * 100)
        self.is_dragging = False
        self.division_selection_drag_active = False
        self.pending_map_click = None
        self.hovered_budget_summary = False
        self.hovered_population_summary = False
        self.hovered_resource_summary = False
        self.hovered_warning_key = None

    def close_country_dialog(self):
        if self.country_dialog_stack:
            self.country_dialog, self.country_dialog_scroll = self.country_dialog_stack.pop()
        else:
            self.country_dialog = None
            self.country_dialog_scroll = 0
        self.country_card_action = None
        self.country_amount_focus = False
        self.country_slider_drag = False
        self.country_dialog_hits = []
        self.country_dialog_cache = None
        self.country_dialog_error = ""

    def country_export_slider_rect(self):
        x, y, width, height = self.country_dialog_rect()
        return (x + 28, y + height - 210 - self.country_dialog_scroll, width - 56, 24)

    def set_country_export_slider(self, x):
        left, _, width, _ = self.country_export_slider_rect()
        self.country_export_percent = int(round(max(0, min(1, (x - left) / width)) * 20)) * 5

    def handle_country_dialog_click(self, x, y, button):
        if not self.country_dialog:
            return False
        if button != arcade.MOUSE_BUTTON_LEFT:
            return True
        for rect, kind, value in self.country_dialog_hits:
            if not self.point_in_rect(x, y, rect):
                continue
            if kind == "dialog_close":
                self.close_country_dialog()
            elif kind == "action":
                self.open_country_dialog("action", value)
            elif kind == "amount":
                self.country_amount_focus = True
            elif kind == "amount_step":
                self.country_amount_text = str(max(1000, min(10**12, (self.country_amount() or 0) + value)))
            elif kind == "export_slider":
                self.country_slider_drag = True
                self.set_country_export_slider(x)
            elif kind == "export_step":
                self.country_export_percent = max(0, min(100, self.country_export_percent + value))
            elif kind == "confirm":
                amount = self.country_export_percent if value == "exports" else self.country_amount() if value in ("aid", "loan") else None
                reason = self.politics.reason(self.human_player.id, self.country_card_id, value, amount)
                if reason:
                    self.country_dialog_error = reason
                else:
                    self.submit_player_command("political_action", {"target": self.country_card_id, "action": value, "amount": amount})
                    self.close_country_dialog()
            self.country_dialog_hits = []
            return True
        return True

    def country_dialog_rows(self, player):
        kind = self.country_dialog
        rows = []
        if kind == "population":
            data = self.population_demographic_summary(player)
            total = data["population"]
            change = self.population_monthly_forecast(player)
            rows.extend([DetailRow("hero", "Население", self.format_population(total), color=BLUE),
                         DetailRow("metric", "Ожидаемое изменение за месяц", f"{change:+,.0f}", color=GREEN if change >= 0 else RED),
                         DetailRow("text", "Прогноз при текущем снабжении и вместимости поселений. Без боевых потерь и изменения границ.", color=MUTED),
                         DetailRow("section", "Возрастной состав")])
            for key, label, color in (("children", "Дети", BLUE), ("working_age", "Рабочий возраст", GREEN), ("elderly", "Пожилые", GOLD)):
                count = data["age"].get(key, 0)
                share = count / total if total else 0
                rows.append(DetailRow("bar", label, f"{self.format_population(count)}  /  {share:.1%}", share, color))
            rows.append(DetailRow("section", "Пол и военный ресурс"))
            for key, label in (("male", "Мужчины"), ("female", "Женщины")):
                rows.append(DetailRow("metric", label, self.format_population(data["gender"].get(key, 0)), color=BLUE))
            for key, label in (("military_obligated", "Военнообязанные"), ("mobilization_available", "Доступно добровольцев")):
                rows.append(DetailRow("metric", label, self.format_population(data[key]), color=GOLD))
            rows.append(DetailRow("section", "Условия жизни"))
            for resource, name in (("food", "Обеспеченность продовольствием"), ("consumer_goods", "Обеспеченность потребительскими товарами")):
                ratio = self.population_resource_ratio(player, resource)
                rows.append(DetailRow("bar", name, f"{ratio:.0%}", min(1, ratio), GREEN if ratio >= 1 else RED))
            capacity = sum(self.tile_population_max_capacity(tile) for tile in player.tiles)
            rows.append(DetailRow("metric", "Предельная вместимость поселений", self.format_population(capacity)))
        elif kind == "power":
            ratings = power_ranking(self.players)
            rating = ratings[player.id]
            rows.append(DetailRow("hero", "Место в мире", f"{rating['rank']} / {len(ratings)}", color=GOLD))
            if player is not self.human_player:
                rows.append(DetailRow("text", relative_power(rating["total"], ratings[self.human_player.id]["total"]), color=GREEN))
                rows.append(DetailRow("text", self.country_threat(player), color=GOLD))
            rows.append(DetailRow("section", "Сравнение с лидерами"))
            for key, label, weight, detail in (
                ("economy", "Экономика", 40, "Налоговая база населения и предприятий"),
                ("military", "Сухопутные силы", 40, "Личный состав, вооружение, состояние, организация и снабжение"),
                ("society", "Общество", 20, "Население, устойчивость, легитимность и поддержка правительства")):
                rows.append(DetailRow("bar", label, f"{rating[key]:.0f}% от лидера", rating[key] / 100, BLUE))
                rows.append(DetailRow("text", f"Вес в общем рейтинге: {weight}%. {detail}.", color=MUTED))
            rows.append(DetailRow("section", "Итоговая оценка"))
            rows.append(DetailRow("bar", "Сводный индекс", f"{rating['total']:.1f} из 100", rating["total"] / 100, GOLD))
            rows.append(DetailRow("text", "100% в категории означает уровень сильнейшей страны именно в этой категории. Лидеры категорий могут различаться.", color=MUTED))
            rows.append(DetailRow("text", "Авиация и география пока не учтены. Рейтинг не предсказывает исход войны.", color=MUTED))
        elif kind == "support":
            state = player.politics
            rows.extend([DetailRow("hero", "Поддержка правительства", f"{state.government_support:.0%}", color=GREEN),
                         DetailRow("bar", "Устойчивость", f"{player.stability:.0%}", player.stability, BLUE),
                         DetailRow("bar", "Легитимность", f"{player.legitimacy:.0%}", player.legitimacy, GOLD)])
            for title, groups in (("Экономические группы", GROUPS), ("Социальные группы", SOCIAL_GROUPS), ("Политические фракции", FACTIONS)):
                rows.append(DetailRow("section", title))
                for key, label in groups.items():
                    support = state.support[key]
                    target = self.politics.rules.support_target(self.politics, player, key)
                    rows.append(DetailRow("bar", label, f"{support:.0%}  /  ожидаемо {target:.0%}", support, GREEN if target >= support else GOLD))
        elif kind == "taxes":
            rows.append(DetailRow("text", "Изменение относительно базовых налоговых поступлений. Это не процентная ставка налога.", color=MUTED))
            for group, label in GROUPS.items():
                rows.append(DetailRow("section", label))
                rows.append(DetailRow("tax", group, f"{player.politics.tax_multiplier(group):.0%} базового уровня", color=GOLD))
                rows.append(DetailRow("text", f"Поддержка группы: {player.politics.support[group]:.0%}", color=MUTED))
        elif kind == "programs":
            for title, groups in (("Общие и деловые программы", GROUPS), ("Социальные группы", SOCIAL_GROUPS), ("Политическое представительство", FACTIONS)):
                rows.append(DetailRow("section", title))
                for group, name in groups.items():
                    active = group in player.politics.programs
                    key = f"{'stop' if active else 'support'}:{group}"
                    quote = self.politics.quote(self.human_player.id, player.id, key)
                    value = (f"До {self.politics.date_text(player.politics.programs[group])}" if active else f"{self.format_money(quote.program_monthly_cost)}/мес.")
                    rows.append(DetailRow("program", name, value, color=GREEN if active else MUTED, action=("action", key)))
        elif kind == "action":
            key = self.country_card_action
            if key == "exports":
                current = round(player.politics.export_capacity_factor * 100)
                rows.extend([DetailRow("metric", "Текущий лимит", f"{current}% базовой мощности", color=MUTED),
                             DetailRow("metric", "Новый лимит", f"{self.country_export_percent}%", color=GOLD),
                             DetailRow("slider", "Лимит экспорта"),
                             DetailRow("text", "0%: экспорт остановлен. 100%: полная торговая мощность. Лимит не гарантирует наличие покупателей.", color=MUTED),
                             DetailRow("section", "Последствия"),
                             DetailRow("text", "Меняется пропускная способность экспортных контрактов. Снижение лимита может уменьшить продажи и поддержку бизнеса."),
                             DetailRow("text", "Импорт не ограничивается этим решением.", color=MUTED)])
                reason = self.politics.reason(self.human_player.id, player.id, key, self.country_export_percent)
                rows.append(DetailRow("text" if reason else "button", reason or "Применить лимит", color=GOLD, action=None if reason else ("confirm", key)))
            else:
                for label, action in self.country_rows(player, action_preview=True):
                    if action and action[0] == "cancel":
                        continue
                    rows.append(DetailRow("button" if action else "text", label, action=action))
        return rows

    def draw_country_dialog(self):
        if not self.country_dialog:
            return
        player = self.player_by_id(self.country_card_id)
        x, y, width, height = self.country_dialog_rect()
        top = y + height
        view_key = (self.country_dialog, self.country_card_action)
        if view_key not in self.country_dialog_views:
            self.country_dialog_views[view_key] = (Batch(), [])
        self.country_dialog_views.move_to_end(view_key)
        while len(self.country_dialog_views) > 16:
            _, (_, labels) = self.country_dialog_views.popitem(last=False)
            for label in labels:
                label.delete()
        batch, pool = self.country_dialog_views[view_key]
        cursor = 0

        def text(value, tx, ty, color=INK, size=12, anchor="left"):
            nonlocal cursor
            if cursor == len(pool):
                pool.append(arcade.Text("", 0, 0, batch=batch))
            label = pool[cursor]
            cursor += 1
            with label:
                for attr, val in (("text", str(value)), ("x", tx), ("y", ty), ("font_size", size), ("color", color), ("anchor_x", anchor), ("anchor_y", "center")):
                    if getattr(label, attr) != val:
                        setattr(label, attr, val)

        self.country_dialog_hits = []
        def button(label, rect, action, color=BLUE):
            bx, by, bw, bh = rect
            arcade.draw_lbwh_rectangle_filled(*rect, (36, 52, 64))
            arcade.draw_lbwh_rectangle_outline(*rect, color, 1)
            text(label, bx + bw / 2, by + bh / 2, color, 11, "center")
            self.country_dialog_hits.append((rect, *action))

        arcade.draw_lbwh_rectangle_filled(0, 0, self.window.width, self.window.height, (0, 0, 0, 95))
        arcade.draw_lbwh_rectangle_filled(x, y, width, height, (20, 28, 36, 255))
        arcade.draw_lbwh_rectangle_outline(x, y, width, height, (116, 144, 163), 2)
        titles = {"population": "Население", "power": "Мощь государства", "support": "Общественная поддержка", "taxes": "Налоги", "programs": "Программы поддержки"}
        title = titles.get(self.country_dialog, self.country_action_label(player, self.country_card_action) if self.country_card_action else "")
        # Long action names occupy two lines inside a fixed-height header.
        for index, line in enumerate(textwrap.wrap(title, max(20, int((width - 105) / 9)))[:2]):
            text(line, x + 24, top - 28 - index * 23, INK, 16)
        button("X", (x + width - 50, top - 48, 30, 30), ("dialog_close", None), MUTED)
        arcade.draw_line(x + 20, top - 78, x + width - 20, top - 78, (70, 91, 108), 1)
        cache_key = (view_key, self.country_card_id, width, self.politics.revision,
                     int(time.monotonic() * 2), self.country_export_percent, self.country_amount_text,
                     self.country_amount_focus, tuple(p.trade_contract_revision for p in self.players))
        if self.country_dialog_cache is None or self.country_dialog_cache[0] != cache_key:
            layout = []
            for row in self.country_dialog_rows(player):
                lines = textwrap.wrap(row.label, max(20, int((width - 56) / 7))) or [""]
                row_height = {"hero": 66, "section": 44, "metric": 32, "bar": 53, "slider": 56,
                              "tax": 40, "program": 66}.get(row.kind, max(36, len(lines) * 19 + 12))
                layout.append((row, lines, row_height))
            self.country_dialog_cache = (cache_key, layout)
        layout = self.country_dialog_cache[1]
        available = height - 116
        total = sum(item[2] for item in layout)
        self.country_dialog_scroll = min(self.country_dialog_scroll, max(0, total - available))
        row_top = top - 90 + self.country_dialog_scroll
        for row, lines, row_height in layout:
            bottom = row_top - row_height
            if bottom >= y + 26 and row_top <= top - 85:
                left, right = x + 28, x + width - 28
                if row.kind == "section":
                    arcade.draw_line(left, row_top - 12, right, row_top - 12, (56, 76, 91), 1)
                    text(row.label, left, row_top - 31, GOLD, 12)
                elif row.kind == "hero":
                    text(row.label, left, row_top - 15, MUTED)
                    text(row.value, left, row_top - 44, row.color, 24)
                elif row.kind in ("metric", "bar"):
                    text(row.label, left, row_top - 15, INK, 11)
                    text(row.value, right, row_top - 15, row.color, 11, "right")
                    if row.kind == "bar":
                        arcade.draw_lbwh_rectangle_filled(left, row_top - 38, width - 56, 7, (43, 60, 71))
                        arcade.draw_lbwh_rectangle_filled(left, row_top - 38, (width - 56) * max(0, min(1, row.ratio)), 7, row.color)
                elif row.kind == "tax":
                    text(row.value, left, row_top - 18, row.color)
                    for label, delta, offset in (("-", -1, 94), ("+", 1, 42)):
                        button(label, (right - offset, bottom + 5, 38, 28), ("action", f"tax:{row.label}:{delta}"))
                elif row.kind == "program":
                    text(row.label, left, row_top - 15, INK, 11)
                    text(row.value, left, row_top - 39, row.color, 10)
                    active = row.action[1].startswith("stop:")
                    button("Завершить" if active else "Начать", (right - 96, bottom + 15, 96, 28), row.action, GOLD if active else GREEN)
                elif row.kind == "slider":
                    rect = (left, row_top - 40, width - 56, 24)
                    # Geometry is shared with pointer handling, including scrolling.
                    self.country_slider_rect = rect
                    arcade.draw_lbwh_rectangle_filled(left, rect[1] + 9, rect[2], 6, (61, 78, 92))
                    arcade.draw_lbwh_rectangle_filled(left, rect[1] + 9, rect[2] * self.country_export_percent / 100, 6, GOLD)
                    arcade.draw_circle_filled(left + rect[2] * self.country_export_percent / 100, rect[1] + 12, 8, GOLD)
                    self.country_dialog_hits.append((rect, "export_slider", None))
                elif row.kind == "button":
                    rect = (left, bottom + 4, width - 56, row_height - 8)
                    if row.action[0] == "amount":
                        rect = (left, bottom + 4, width - 152, row_height - 8)
                        button("-", (right - 88, bottom + 4, 38, 28), ("amount_step", -1000000))
                        button("+", (right - 40, bottom + 4, 38, 28), ("amount_step", 1000000))
                    arcade.draw_lbwh_rectangle_filled(*rect, (35, 55, 63))
                    for index, line in enumerate(lines):
                        text(line, left + 10, row_top - 18 - index * 19, GREEN, 11)
                    self.country_dialog_hits.append((rect, *row.action))
                else:
                    for index, line in enumerate(lines):
                        text(line, left, row_top - 14 - index * 19, row.color, 11)
            row_top = bottom
        if total > available:
            track = height - 120
            thumb = max(24, track * available / total)
            offset = (track - thumb) * self.country_dialog_scroll / max(1, total - available)
            arcade.draw_lbwh_rectangle_filled(x + width - 12, y + 28, 4, track, (47, 64, 79))
            arcade.draw_lbwh_rectangle_filled(x + width - 12, top - 92 - offset - thumb, 4, thumb, MUTED)
        if self.country_dialog_error:
            text(self.country_dialog_error, x + 28, y + 13, RED, 10)
        for label in pool[cursor:]:
            if label.text:
                label.text = ""
        batch.draw()
        # Existing click helpers see only controls on the foremost window.
        self.country_card_hits = list(self.country_dialog_hits)

