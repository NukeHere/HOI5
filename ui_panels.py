import arcade
import textwrap
import time

from Constants import *


class UIPanelsMixin:
    def draw_top_status_bar(self):
        if not self.human_player:
            return

        player = self.human_player
        if not player.resource_totals:
            self.recalculate_state_resources(player)
        metals, fuel, consumer_goods = self.player_resource_summary(player)

        y = self.window.height - TOP_STATUS_BAR_HEIGHT
        arcade.draw_lbwh_rectangle_filled(0, y, self.window.width, TOP_STATUS_BAR_HEIGHT, (18, 24, 31, 245))
        arcade.draw_line(0, y, self.window.width, y, (88, 106, 128), 2)

        self.budget_summary_rect = None
        self.population_summary_rect = None
        budget_text = f"{self.format_money(player.budget)}  {self.format_money_delta(player.monthly_balance)}/мес"
        resource_text = (
            f"Металлы {self.format_resource_amount(metals)}  "
            f"Топливо {self.format_resource_amount(fuel)}  "
            f"Товары {self.format_resource_amount(consumer_goods)}"
        )
        items = [
            player.name,
            f"Нас: {self.format_population(player.population)}",
            budget_text,
            f"Стаб: {player.stability:.0%}",
            f"Легит: {player.legitimacy:.0%}",
            f"Подд. войны: {player.war_support:.0%}",
        ]

        x = 10
        for index, text in enumerate(items[:3]):
            item_width = max(88, len(text) * 7 + 22)
            if index == 0:
                self.country_summary_rect = (x - 6, y + 5, item_width - 8, TOP_STATUS_BAR_HEIGHT - 10)
                arcade.draw_lbwh_rectangle_outline(*self.country_summary_rect, (118, 146, 176), 1)
            if index == 1:
                self.population_summary_rect = (x - 6, y + 5, item_width - 8, TOP_STATUS_BAR_HEIGHT - 10)
                if self.hovered_population_summary:
                    arcade.draw_lbwh_rectangle_filled(*self.population_summary_rect, (36, 48, 62, 210))
                    arcade.draw_lbwh_rectangle_outline(*self.population_summary_rect, (118, 146, 176, 180), 1)
            if index == 2:
                self.budget_summary_rect = (x - 6, y + 5, item_width - 8, TOP_STATUS_BAR_HEIGHT - 10)
                if self.hovered_budget_summary:
                    arcade.draw_lbwh_rectangle_filled(*self.budget_summary_rect, (36, 48, 62, 210))
                    arcade.draw_lbwh_rectangle_outline(*self.budget_summary_rect, (118, 146, 176, 180), 1)
            color = (238, 244, 250) if index == 0 else (210, 220, 232)
            self.draw_ui_text(text, x, y + TOP_STATUS_BAR_HEIGHT / 2, color, 12, anchor_y="center")
            x += item_width

        status_reserved_width = 300
        available_resource_width = max(280, self.window.width - x - status_reserved_width)
        resource_width = min(available_resource_width, max(360, len(resource_text) * 7 + 38))
        self.resource_summary_rect = (x, y + 5, resource_width, TOP_STATUS_BAR_HEIGHT - 10)
        resource_fill = self.problem_color(self.resource_problem_level(player))
        if self.hovered_resource_summary:
            resource_fill = self.blend_colors(resource_fill[:3], (255, 255, 255), 0.12) + (resource_fill[3],)
        arcade.draw_lbwh_rectangle_filled(*self.resource_summary_rect, resource_fill)
        arcade.draw_lbwh_rectangle_outline(*self.resource_summary_rect, (116, 140, 162, 180), 1)
        self.draw_ui_text(resource_text, x + 10, y + TOP_STATUS_BAR_HEIGHT / 2, (238, 244, 250), 12, anchor_y="center")
        x += resource_width + 14

        for text in items[3:]:
            if x > self.window.width - 330:
                break
            self.draw_ui_text(text, x, y + TOP_STATUS_BAR_HEIGHT / 2, (210, 220, 232), 12, anchor_y="center")
            x += max(88, len(text) * 7 + 22)

    def draw_resource_summary_tooltip(self, player):
        if not self.hovered_resource_summary or not self.resource_summary_rect:
            return

        problems = self.resource_problem_summary(player)
        red_items = []
        yellow_items = []
        for _bucket, bucket_problems in problems.items():
            red_items.extend(bucket_problems["red"])
            yellow_items.extend(bucket_problems["yellow"])
        if not red_items and not yellow_items:
            return

        x, y, _width, _height = self.resource_summary_rect
        tooltip_width = 320
        tooltip_height = 76 + (len(red_items) + len(yellow_items)) * 16
        tooltip_x = min(x, self.window.width - tooltip_width - 12)
        tooltip_y = max(8, y - tooltip_height - 8)
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 245))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (140, 160, 184), 1)
        line_y = tooltip_y + tooltip_height - 20
        self.draw_tooltip_text("Проблемы ресурсов", tooltip_x + 12, line_y, arcade.color.WHITE, 12)
        line_y -= 18
        for label, items, color in [("Красные", red_items, (240, 108, 98)), ("Желтые", yellow_items, (238, 198, 90))]:
            if not items:
                continue
            self.draw_tooltip_text(f"{label}:", tooltip_x + 12, line_y, color, 11)
            line_y -= 16
            for item in items[:5]:
                self.draw_tooltip_text(f"- {self.resource_display_name(item)}", tooltip_x + 22, line_y, (220, 230, 240), 11)
                line_y -= 15

    def draw_budget_summary_tooltip(self, player):
        if not self.hovered_budget_summary or not self.budget_summary_rect:
            return

        income = player.monthly_income_breakdown or {}
        expenses = player.monthly_expenses_breakdown or self.monthly_expenses(player)
        social_parts = expenses.get("social_breakdown", {}) or {}
        trade_value = income.get("trade", player.monthly_trade_balance)
        rows = [
            ("Бюджет", self.format_money(player.budget), arcade.color.WHITE, 12),
            (
                "Месячный баланс",
                f"{self.format_money_delta(player.monthly_balance)}/мес",
                (174, 224, 158) if player.monthly_balance >= 0 else (236, 148, 132),
                12,
            ),
            None,
            ("Доходы:", None, arcade.color.WHITE, 12),
            ("Налоги населения", self.format_money_delta(income.get("population", 0.0)), (190, 226, 174), 11),
            ("Компании", self.format_money_delta(income.get("companies", 0.0)), (190, 226, 174), 11),
            ("Возврат кредитов (прогноз)", self.format_money_delta(income.get("loan_repayments", 0.0)), (190, 226, 174), 11),
            (
                "Торговля",
                self.format_money_delta(trade_value),
                (190, 226, 174) if trade_value >= 0 else (236, 168, 154),
                11,
            ),
            None,
            ("Расходы:", None, arcade.color.WHITE, 12),
            ("Армия", f"-{self.format_money(expenses.get('army', 0.0))}", (236, 168, 154), 11),
            ("Правительство", f"-{self.format_money(expenses.get('government', 0.0))}", (236, 168, 154), 11),
            ("Соц. обеспечение", f"-{self.format_money(expenses.get('social', 0.0))}", (236, 168, 154), 11),
            ("  Пенсии", f"-{self.format_money(social_parts.get('pensions', 0.0))}", (206, 178, 168), 10),
            ("  Дети/школы", f"-{self.format_money(social_parts.get('children', 0.0))}", (206, 178, 168), 10),
            ("  Инвалиды", f"-{self.format_money(social_parts.get('disability', 0.0))}", (206, 178, 168), 10),
            ("  Соцслужбы", f"-{self.format_money(social_parts.get('local_services', 0.0))}", (206, 178, 168), 10),
            ("Инфраструктура", f"-{self.format_money(expenses.get('infrastructure', 0.0))}", (236, 168, 154), 11),
            ("Программы поддержки", f"-{self.format_money(expenses.get('political_programs', 0.0))}", (236, 168, 154), 11),
            ("Платежи по кредитам", f"-{self.format_money(expenses.get('debt_service', 0.0))}", (236, 168, 154), 11),
        ]
        text_width = 0
        for row in rows:
            if row is None:
                continue
            label, value, _color, size = row
            text_width = max(text_width, len(label) * size * 0.58)
            if value is not None:
                text_width = max(text_width, len(label) * size * 0.52 + len(value) * size * 0.58 + 46)
        tooltip_width = int(max(300, min(430, text_width + 34)))
        tooltip_height = 28 + sum(7 if row is None else 17 for row in rows)
        x, y, _width, _height = self.budget_summary_rect
        tooltip_x = max(12, min(x, self.window.width - tooltip_width - 12))
        tooltip_y = max(8, y - tooltip_height - 8)
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 247))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (140, 160, 184), 1)

        line_y = tooltip_y + tooltip_height - 20

        def line(label, value=None, color=(220, 230, 240), size=11):
            nonlocal line_y
            if value is None:
                self.draw_tooltip_text(label, tooltip_x + 14, line_y, color, size)
            else:
                self.draw_tooltip_text(label, tooltip_x + 14, line_y, color, size)
                self.draw_tooltip_text(value, tooltip_x + tooltip_width - 14, line_y, color, size, anchor_x="right")
            line_y -= 17

        for row in rows:
            if row is None:
                line_y -= 7
                continue
            line(*row)

    def draw_population_summary_tooltip(self, player):
        if not self.hovered_population_summary or not self.population_summary_rect:
            return

        summary = self.population_demographic_summary(player)
        age = summary["age"]
        gender = summary["gender"]
        rows = [
            ("Население", self.format_population(summary["population"]), arcade.color.WHITE, 12),
            None,
            ("Возраст:", None, arcade.color.WHITE, 12),
            ("Дети", self.format_population(age.get("children", 0.0)), (220, 230, 240), 11),
            ("Рабочий возраст", self.format_population(age.get("working_age", 0.0)), (220, 230, 240), 11),
            ("Старики", self.format_population(age.get("elderly", 0.0)), (220, 230, 240), 11),
            None,
            ("Пол:", None, arcade.color.WHITE, 12),
            ("Мужчины", self.format_population(gender.get("male", 0.0)), (220, 230, 240), 11),
            ("Женщины", self.format_population(gender.get("female", 0.0)), (220, 230, 240), 11),
            None,
            ("Военный ресурс:", None, arcade.color.WHITE, 12),
            ("Военнообязанные", self.format_population(summary["military_obligated"]), (220, 230, 240), 11),
            (
                "Добровольцы",
                self.format_population(summary["mobilization_available"]),
                (190, 226, 174),
                11,
            ),
            (
                "Готовность",
                f"{summary['volunteer_share']:.0%}",
                (190, 226, 174),
                11,
            ),
            None,
            ("Стабильность", f"{player.stability:.0%}", (210, 222, 234), 11),
            ("Легитимность", f"{player.legitimacy:.0%}", (210, 222, 234), 11),
            ("Поддержка войны", f"{player.war_support:.0%}", (210, 222, 234), 11),
        ]

        tooltip_width = 330
        tooltip_height = 28 + sum(7 if row is None else 17 for row in rows)
        x, y, _width, _height = self.population_summary_rect
        tooltip_x = max(12, min(x, self.window.width - tooltip_width - 12))
        tooltip_y = max(8, y - tooltip_height - 8)
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 247))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (140, 160, 184), 1)

        line_y = tooltip_y + tooltip_height - 20
        for row in rows:
            if row is None:
                line_y -= 7
                continue
            label, value, color, size = row
            if value is None:
                self.draw_tooltip_text(label, tooltip_x + 14, line_y, color, size)
            else:
                self.draw_tooltip_text(label, tooltip_x + 14, line_y, color, size)
                self.draw_tooltip_text(value, tooltip_x + tooltip_width - 14, line_y, color, size, anchor_x="right")
            line_y -= 17

    def top_warning_items(self, player):
        items = []
        problems = self.resource_problem_summary(player)
        resource_red = sum(len(bucket["red"]) for bucket in problems.values())
        resource_yellow = sum(len(bucket["yellow"]) for bucket in problems.values())
        if resource_red or resource_yellow:
            level = "red" if resource_red else "yellow"
            lines = []
            for bucket in problems.values():
                lines.extend([f"Критично: {self.resource_display_name(key)}" for key in bucket["red"][:3]])
                lines.extend([f"Мало: {self.resource_display_name(key)}" for key in bucket["yellow"][:3]])
            items.append({
                "key": "resources",
                "label": "!",
                "title": "Проблемы ресурсов",
                "level": level,
                "lines": lines[:6],
                "panel": "resources",
            })

        storage = self.storage_problem_summary(player)
        if storage["red"] or storage["yellow"]:
            level = "red" if storage["red"] else "yellow"
            storage_items = storage["red"] + storage["yellow"]
            items.append({
                "key": "storage",
                "label": "S",
                "title": "Склады заполнены" if storage["red"] else "Склады почти заполнены",
                "level": level,
                "lines": [
                    (
                        f"{STORAGE_CATEGORY_LABELS.get(category, category)}: "
                        f"{self.format_resource_amount(player.storage_used.get(category, 0.0))}/"
                        f"{self.format_resource_amount(player.storage_capacity.get(category, 0.0))}"
                    )
                    for category in storage_items[:6]
                ],
                "panel": "resources",
            })

        supply = player.supply_summary or self.recalculate_player_supply(player)
        if supply.get("critical_tiles", 0) > 0 or supply.get("low_tiles", 0) > 0:
            level = "red" if supply.get("critical_tiles", 0) > 0 else "yellow"
            items.append({
                "key": "supply",
                "label": "L",
                "title": "Проблемы снабжения",
                "level": level,
                "lines": [
                    f"Среднее снабжение: {supply.get('average', 0.0):.0%}",
                    f"Критичных клеток: {supply.get('critical_tiles', 0)}",
                    f"Слабых клеток: {supply.get('low_tiles', 0)}",
                ],
                "panel": "resources",
            })

        contracts = self.normalized_trade_contracts(getattr(player, "trade_contracts", []))
        if contracts:
            planned_buy = sum(contract["amount"] for contract in contracts if contract["mode"] == "buy")
            planned_sell = sum(contract["amount"] for contract in contracts if contract["mode"] == "sell")
            buy_capacity = self.trade_capacity_per_month(player, "buy")
            sell_capacity = self.trade_capacity_per_month(player, "sell")
            if planned_buy > buy_capacity + 0.001 or planned_sell > sell_capacity + 0.001:
                items.append({
                    "key": "trade",
                    "label": "T",
                    "title": "Торговля уперлась в лимит",
                    "level": "yellow",
                    "lines": [
                        f"Покупка: {self.format_resource_amount(planned_buy)}/{self.format_resource_amount(buy_capacity)}/мес",
                        f"Продажа: {self.format_resource_amount(planned_sell)}/{self.format_resource_amount(sell_capacity)}/мес",
                        "Нужны порты, склады, логистика или снабжение.",
                    ],
                    "panel": "trade",
                })

        construction_warning = self.construction_warning_summary(player)
        if construction_warning:
            items.append({
                "key": "construction",
                "label": "C",
                "title": construction_warning["title"],
                "level": construction_warning["level"],
                "lines": construction_warning["lines"],
                "panel": "construction",
            })
        return items

    def draw_top_warning_icons(self):
        self.warning_icon_rects = {}
        if not self.human_player:
            return
        items = self.top_warning_items(self.human_player)
        if not items:
            return

        nav_right = max((button["rect"][0] + button["rect"][2] for button in self.top_nav_buttons), default=12)
        x = nav_right + 16
        y = self.window.height - TOP_UI_HEIGHT + 9
        size = 28
        gap = 8
        for item in items:
            rect = (x, y, size, size)
            self.warning_icon_rects[item["key"]] = rect
            fill = (128, 48, 42, 235) if item["level"] == "red" else (138, 104, 38, 235)
            if self.hovered_warning_key == item["key"]:
                fill = self.blend_colors(fill[:3], (255, 255, 255), 0.14) + (fill[3],)
            arcade.draw_lbwh_rectangle_filled(*rect, fill)
            arcade.draw_lbwh_rectangle_outline(*rect, (214, 222, 232), 1)
            self.draw_ui_text(item["label"], x + size / 2, y + size / 2, arcade.color.WHITE, 13,
                              anchor_x="center", anchor_y="center")
            x += size + gap

    def draw_top_warning_tooltip(self, items):
        if not self.hovered_warning_key:
            return
        item = next((entry for entry in items if entry["key"] == self.hovered_warning_key), None)
        rect = self.warning_icon_rects.get(self.hovered_warning_key)
        if not item or not rect:
            return

        lines = item.get("lines") or []
        tooltip_width = 300
        tooltip_height = 48 + min(6, len(lines)) * 16
        tooltip_x = min(rect[0], self.window.width - tooltip_width - 12)
        tooltip_y = rect[1] - tooltip_height - 8
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 246))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (150, 170, 194), 1)
        line_y = tooltip_y + tooltip_height - 20
        self.draw_tooltip_text(item["title"], tooltip_x + 12, line_y, arcade.color.WHITE, 12)
        line_y -= 18
        for line in lines[:6]:
            self.draw_tooltip_text(line, tooltip_x + 18, line_y, (220, 230, 240), 11)
            line_y -= 16

    def draw_top_hover_tooltips(self):
        if self.human_player:
            self.draw_population_summary_tooltip(self.human_player)
            self.draw_budget_summary_tooltip(self.human_player)
            self.draw_resource_summary_tooltip(self.human_player)
            self.draw_top_warning_tooltip(self.top_warning_items(self.human_player))

    def draw_division_detach_tooltip(self):
        if not self.hovered_division_detach_button or not self.division_detach_button_rect:
            return
        rect_x, rect_y, _rect_width, _rect_height = self.division_detach_button_rect
        tooltip_width = 214
        tooltip_height = 34
        tooltip_x = max(12, min(rect_x, self.window.width - tooltip_width - 12))
        tooltip_y = max(8, rect_y - tooltip_height - 8)
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 247))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (150, 170, 194), 1)
        self.draw_tooltip_text(
            "открепить выбранные дивизии",
            tooltip_x + tooltip_width / 2,
            tooltip_y + tooltip_height / 2 + 1,
            arcade.color.WHITE,
            11,
            anchor_x="center",
            anchor_y="center",
        )

    def draw_top_navigation_bar(self):
        y = self.window.height - TOP_UI_HEIGHT
        arcade.draw_lbwh_rectangle_filled(0, y, self.window.width, TOP_NAV_BAR_HEIGHT, (24, 31, 40, 238))
        arcade.draw_line(0, y, self.window.width, y, (70, 88, 108), 2)

        for button in self.top_nav_buttons:
            key = button["key"]
            x, y, width, height = button["rect"]
            active = key == self.active_top_panel_key
            hovered = key == self.hovered_top_nav_key
            fill = (60, 78, 98) if active else ((48, 62, 78) if hovered else (30, 39, 50))
            border = (190, 206, 224) if active or hovered else (92, 112, 136)
            arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
            arcade.draw_lbwh_rectangle_outline(x, y, width, height, border, 2)
            texture = self.top_nav_icon_textures.get(key)
            if texture:
                arcade.draw_texture_rect(
                    texture,
                    arcade.rect.XYWH(x + width / 2, y + height / 2, 30, 30),
                    alpha=245,
                )
        self.draw_top_warning_icons()

    def top_nav_button_at(self, x, y):
        for button in self.top_nav_buttons:
            if self.point_in_rect(x, y, button["rect"]):
                return button
        return None

    def warning_icon_at(self, x, y):
        for key, rect in self.warning_icon_rects.items():
            if self.point_in_rect(x, y, rect):
                return key
        return None

    def open_top_panel(self, key):
        self.country_dialog = None
        self.country_dialog_stack = []
        self.country_slider_drag = False
        previous_key = self.active_top_panel_key
        self.country_card_action = None
        self.country_card_scroll = 0
        self.country_amount_focus = False
        self.country_card_hits = []
        self.country_list_open = key == "diplomacy"
        self.country_card_id = self.human_player.id if key == "politics" and self.human_player else None
        if key == "politics":
            self.country_card_tab = "actions"
        self.active_top_panel_key = key
        self.side_panel_target = 1.0
        if (self.selected_resource_key and previous_key != key
                and (previous_key in ("resources", "construction") or key in ("resources", "construction"))):
            self.create_map_overview()
            self.refresh_visible_tiles()
        if previous_key == "construction" and key != "construction":
            self.set_construction_placement_mode(False)

    def close_top_panel(self):
        self.country_dialog = None
        self.country_dialog_stack = []
        self.country_slider_drag = False
        self.country_card_id = None
        self.country_list_open = False
        self.country_amount_focus = False
        self.side_panel_target = 0.0
        self.hovered_side_panel_close = False
        if self.active_top_panel_key == "construction":
            self.set_construction_placement_mode(False)
        if self.selected_resource_key:
            self.selected_resource_key = None
            self.create_map_overview()
            self.refresh_visible_tiles()

    def update_side_panel_animation(self, delta_time):
        speed = min(1.0, delta_time * 12)
        self.side_panel_progress += (self.side_panel_target - self.side_panel_progress) * speed
        if abs(self.side_panel_progress - self.side_panel_target) < 0.01:
            self.side_panel_progress = self.side_panel_target
            if self.side_panel_progress == 0:
                self.active_top_panel_key = None

    def side_panel_rect(self):
        top = self.window.height - TOP_UI_HEIGHT - SIDE_PANEL_MARGIN
        height = top - SIDE_PANEL_MARGIN
        if self.active_top_panel_key == "resources":
            width = 760
        elif self.active_top_panel_key == "economy":
            width = 620
        elif self.active_top_panel_key == "trade":
            width = 760
        elif self.active_top_panel_key == "construction":
            width = 500
        elif self.active_top_panel_key in ("politics", "diplomacy"):
            width = min(560, self.window.width - 24)
        else:
            width = SIDE_PANEL_WIDTH
        x = -width + width * self.side_panel_progress
        return x, SIDE_PANEL_MARGIN, width, height

    def side_panel_close_rect(self):
        panel_x, panel_y, panel_width, panel_height = self.side_panel_rect()
        return panel_x + panel_width - 38, panel_y + panel_height - 38, 28, 28

    def resource_category_rects(self):
        panel_x, panel_y, _panel_width, panel_height = self.side_panel_rect()
        block_width = 160
        block_height = 76
        gap = 10
        y = panel_y + panel_height - 128
        return [
            (panel_x + 18 + index * (block_width + gap), y, block_width, block_height)
            for index, _category in enumerate(RESOURCE_PANEL_CATEGORIES)
        ]

    def resource_rows(self):
        if not self.human_player:
            return []

        if not self.human_player.resource_totals:
            self.recalculate_state_resources(self.human_player)
        if not self.human_player.production_cache:
            self.recalculate_state_production_cache(self.human_player)
        breakdown = self.cached_resource_balance_breakdown(self.human_player)
        cache_key = (
            self.resource_panel_category,
            round(getattr(self.human_player, "resource_balance_last_update", 0.0), 3),
        )
        if self.resource_rows_cache and self.resource_rows_cache.get("key") == cache_key:
            return self.resource_rows_cache["rows"]

        if self.resource_panel_category == "raw":
            keys = list(RAW_RESOURCE_NAMES)
            for key in sorted(breakdown["raw"].keys()):
                if key not in keys:
                    keys.append(key)
            rows = []
            for key in keys:
                entry = breakdown["raw"].get(key, {})
                production = entry.get("production", 0.0)
                consumption = entry.get("consumption", 0.0)
                stock = entry.get("stock", 0.0)
                rows.append({
                    "key": key,
                    "ground": entry.get("ground", 0.0),
                    "stock": stock,
                    "production": production,
                    "consumption": consumption,
                    "months": entry.get("months", self.resource_duration_months(stock, production, consumption)),
                })
        else:
            names = SEMI_FINISHED_RESOURCE_NAMES if self.resource_panel_category == "semi_finished" else FINISHED_RESOURCE_NAMES
            rows = []
            for key in names:
                entry = breakdown[self.resource_panel_category].get(key, {})
                production = entry.get("production", 0.0)
                consumption = entry.get("consumption", 0.0)
                stock_amount = entry.get("stock", 0.0)
                rows.append({
                    "key": key,
                    "ground": None,
                    "stock": stock_amount,
                    "production": production,
                    "consumption": consumption,
                    "months": entry.get("months", self.resource_duration_months(stock_amount, production, consumption)),
                })
        for row in rows:
            row["display_values"] = [
                (self.resource_display_name(row["key"]), (220, 230, 240)),
                (self.format_resource_amount(row["ground"]) if row["ground"] is not None else "--", (220, 230, 240)),
                ("--" if row["stock"] is None else self.format_resource_amount(row["stock"]), (220, 230, 240)),
                ("--" if row["production"] is None else self.format_resource_amount(row["production"]), (220, 230, 240)),
                ("--" if row["consumption"] is None else self.format_resource_amount(row["consumption"]), (220, 230, 240)),
                (self.format_resource_duration(row["months"]), self.resource_duration_color(row["months"])),
            ]
        self.resource_rows_cache = {"key": cache_key, "rows": rows}
        return rows

    def draw_economy_panel_content(self, panel_x, panel_y, panel_width, panel_height):
        player = self.human_player
        if not player:
            return

        current = self.cached_economy_snapshot(player)
        previous = player.economy_previous_snapshot or {}
        has_previous = bool(previous)

        content_x = panel_x + 18
        content_width = panel_width - 36
        top_y = panel_y + panel_height - 68
        forecast_1m = current["budget"] + current["balance"]
        forecast_3m = current["budget"] + current["balance"] * 3
        balance_color = (178, 226, 158) if current["balance"] >= 0 else (238, 150, 132)

        card_gap = 10
        card_width = (content_width - card_gap) / 2
        card_height = 82
        cards = [
            ("Бюджет", self.format_money(current["budget"]), f"{self.format_money_delta(current['balance'])}/мес", balance_color),
            ("Прогноз", f"1 мес: {self.format_money(forecast_1m)}", f"3 мес: {self.format_money(forecast_3m)}", (210, 222, 236)),
        ]
        for index, (title, value, subvalue, subcolor) in enumerate(cards):
            x = content_x + index * (card_width + card_gap)
            y = top_y - card_height
            arcade.draw_lbwh_rectangle_filled(x, y, card_width, card_height, (28, 40, 52, 220))
            arcade.draw_lbwh_rectangle_outline(x, y, card_width, card_height, (86, 112, 138), 1)
            self.draw_ui_text(title, x + 12, y + card_height - 22, (164, 180, 198), 10)
            self.draw_ui_text(value, x + 12, y + card_height - 46, arcade.color.WHITE, 15)
            self.draw_ui_text(subvalue, x + 12, y + 16, subcolor, 11)

        y = top_y - card_height - 28
        value_x = panel_x + panel_width - 178
        delta_x = panel_x + panel_width - 18

        def previous_value(section, key, default=0.0):
            if not has_previous:
                return None
            if section is None:
                return previous.get(key, default)
            return (previous.get(section, {}) or {}).get(key, default)

        def delta_text(current_value, previous_value_):
            if previous_value_ is None:
                return "--"
            return self.format_money_delta(current_value - previous_value_)

        def delta_color(current_value, previous_value_, positive_good=True):
            if previous_value_ is None:
                return (150, 164, 180)
            delta = current_value - previous_value_
            if abs(delta) < 1:
                return (170, 184, 198)
            good = delta >= 0 if positive_good else delta <= 0
            return (178, 226, 158) if good else (238, 150, 132)

        def section_title(title, y_pos):
            self.draw_ui_text(title, content_x, y_pos, arcade.color.WHITE, 14)
            arcade.draw_line(content_x, y_pos - 7, panel_x + panel_width - 18, y_pos - 7, (72, 92, 112, 180), 1)
            self.draw_ui_text("Сейчас", value_x, y_pos, (150, 166, 184), 10, anchor_x="right")
            self.draw_ui_text("К прошл. мес.", delta_x, y_pos, (150, 166, 184), 10, anchor_x="right")
            return y_pos - 24

        def money_row(label, value, prev_value, y_pos, positive_good=True, force_minus=False):
            value_color = (210, 222, 234)
            if value > 0 and not force_minus:
                value_color = (190, 226, 174)
            elif value < 0 or force_minus:
                value_color = (236, 168, 154)
            shown_value = f"-{self.format_money(value)}" if force_minus else self.format_money_delta(value)
            self.draw_ui_text(label, content_x + 8, y_pos, (214, 224, 234), 11)
            self.draw_ui_text(shown_value, value_x, y_pos, value_color, 11, anchor_x="right")
            self.draw_ui_text(
                delta_text(value, prev_value),
                delta_x,
                y_pos,
                delta_color(value, prev_value, positive_good=positive_good),
                11,
                anchor_x="right",
            )
            return y_pos - 18

        y = section_title("Доходы", y)
        income = current["income"]
        y = money_row("Налоги населения", income["population"], previous_value("income", "population"), y)
        y = money_row("Компании", income["companies"], previous_value("income", "companies"), y)
        y = money_row("Торговля", income["trade"], previous_value("income", "trade"), y)
        y = money_row("Всего доходов", income["total"], previous_value("income", "total"), y)

        y -= 8
        y = section_title("Расходы", y)
        expenses = current["expenses"]
        social_parts = expenses.get("social_breakdown", {}) or {}
        previous_social_parts = (previous.get("expenses", {}) or {}).get("social_breakdown", {}) if has_previous else {}
        y = money_row("Армия", expenses["army"], previous_value("expenses", "army"), y, positive_good=False, force_minus=True)
        y = money_row("Правительство", expenses["government"], previous_value("expenses", "government"), y, positive_good=False, force_minus=True)
        y = money_row("Соц. обеспечение", expenses["social"], previous_value("expenses", "social"), y, positive_good=False, force_minus=True)
        y = money_row("  Пенсии", social_parts.get("pensions", 0.0), previous_social_parts.get("pensions") if has_previous else None, y, positive_good=False, force_minus=True)
        y = money_row("  Дети/школы", social_parts.get("children", 0.0), previous_social_parts.get("children") if has_previous else None, y, positive_good=False, force_minus=True)
        y = money_row("  Инвалиды", social_parts.get("disability", 0.0), previous_social_parts.get("disability") if has_previous else None, y, positive_good=False, force_minus=True)
        y = money_row("  Соцслужбы", social_parts.get("local_services", 0.0), previous_social_parts.get("local_services") if has_previous else None, y, positive_good=False, force_minus=True)
        y = money_row("Инфраструктура", expenses["infrastructure"], previous_value("expenses", "infrastructure"), y, positive_good=False, force_minus=True)
        y = money_row("Всего расходов", expenses["total"], previous_value("expenses", "total"), y, positive_good=False, force_minus=True)

        y -= 8
        y = section_title("Итог и показатели", y)
        y = money_row("Месячный баланс", current["balance"], previous_value(None, "balance"), y)

        population_previous = previous_value(None, "population")
        population_delta = None if population_previous is None else current["population"] - population_previous
        self.draw_ui_text("Население", content_x + 8, y, (214, 224, 234), 11)
        self.draw_ui_text(self.format_population(current["population"]), value_x, y, (210, 222, 234), 11, anchor_x="right")
        self.draw_ui_text(
            self.format_population_delta(population_delta),
            delta_x,
            y,
            (178, 226, 158) if (population_delta or 0) >= 0 else (238, 150, 132),
            11,
            anchor_x="right",
        )
        y -= 18

        land_tiles = sum(1 for tile in player.tiles if not self.is_water_tile(tile))
        population_millions = max(0.001, current["population"] / 1_000_000)
        net_company_after_upkeep = income["companies"] - expenses["infrastructure"]
        indicators = [
            ("Территория", f"{land_tiles} клеток"),
            ("Налогов на 1M жителей", self.format_money(income["population"] / population_millions)),
            ("Компании - инфраструктура", self.format_money_delta(net_company_after_upkeep)),
        ]
        for label, value in indicators:
            self.draw_ui_text(label, content_x + 8, y, (214, 224, 234), 11)
            self.draw_ui_text(value, value_x, y, (210, 222, 234), 11, anchor_x="right")
            y -= 18

        if not has_previous:
            self.draw_ui_text(
                "Сравнение появится после перехода на следующий календарный месяц.",
                content_x + 8,
                panel_y + 18,
                (160, 174, 190),
                10,
            )

    def resource_row_rects(self, rows):
        panel_x, panel_y, _panel_width, panel_height = self.side_panel_rect()
        start_y = panel_y + panel_height - 336
        row_height = 22
        bottom_y = panel_y + 26
        max_visible_count = max(8, int((start_y - bottom_y) / row_height) + 1)
        visible_count = min(len(rows), max_visible_count)
        return [
            (panel_x + 18, start_y - index * row_height, 500, row_height)
            for index in range(visible_count)
        ]

    def visible_resource_rows(self, rows):
        visible_count = len(self.resource_row_rects(rows))
        max_scroll = max(0, len(rows) - visible_count)
        self.resource_scroll_index = max(0, min(self.resource_scroll_index, max_scroll))
        end_index = self.resource_scroll_index + visible_count
        return rows[self.resource_scroll_index:end_index]

    def resource_table_rect(self, rows=None):
        rows = rows if rows is not None else self.resource_rows()
        row_rects = self.resource_row_rects(rows)
        if not row_rects:
            panel_x, panel_y, _panel_width, panel_height = self.side_panel_rect()
            return panel_x + 18, panel_y + 26, 500, 0

        x, _y, width, height = row_rects[0]
        bottom_y = row_rects[-1][1]
        top_y = row_rects[0][1] + height
        return x, bottom_y, width, top_y - bottom_y

    def scroll_resource_rows(self, amount):
        rows = self.resource_rows()
        visible_count = len(self.resource_row_rects(rows))
        max_scroll = max(0, len(rows) - visible_count)
        old_index = self.resource_scroll_index
        self.resource_scroll_index = max(0, min(max_scroll, self.resource_scroll_index + int(amount)))
        return self.resource_scroll_index != old_index

    def resource_sources_count(self, resource_key):
        if not self.human_player:
            return 0

        if not self.human_player.resource_sources:
            self.recalculate_state_resources(self.human_player)
        return self.human_player.resource_sources.get(resource_key, 0)

    def selected_resource_card_rect(self):
        panel_x, panel_y, panel_width, panel_height = self.side_panel_rect()
        card_x = panel_x + 528
        card_y = panel_y + 58
        card_width = panel_width - 546
        card_height = panel_height - 112
        return card_x, card_y, card_width, card_height

    def selected_resource_close_rect(self):
        card_x, card_y, card_width, card_height = self.selected_resource_card_rect()
        return card_x + card_width - 32, card_y + card_height - 34, 24, 24

    def draw_resources_panel_content(self, panel_x, panel_y, panel_width, panel_height):
        if not self.human_player:
            return

        self.resource_warning_rects = []
        problems = self.resource_problem_summary(self.human_player)
        surplus = self.resource_surplus_summary(self.human_player)
        for index, (category_key, label) in enumerate(RESOURCE_PANEL_CATEGORIES):
            x, y, width, height = self.resource_category_rects()[index]
            active = category_key == self.resource_panel_category
            yellow_count = len(problems[category_key]["yellow"])
            red_count = len(problems[category_key]["red"])
            surplus_count = len(surplus[category_key])
            level = "red" if red_count else ("yellow" if yellow_count else "green")
            fill = self.problem_color(level)
            if active:
                fill = self.blend_colors(fill[:3], (255, 255, 255), 0.12) + (fill[3],)
            arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
            arcade.draw_lbwh_rectangle_outline(x, y, width, height, (120, 142, 166), 1)
            self.draw_ui_text(label, x + 10, y + height - 20, arcade.color.WHITE, 13)
            self.draw_ui_text(f"Недостаток: {red_count + yellow_count}", x + 10, y + 32, (226, 234, 242), 11)
            self.draw_ui_text(f"Избыток: {surplus_count}", x + 10, y + 14, (180, 222, 166), 11)

        warning_y = panel_y + panel_height - 166
        self.draw_ui_text("Склады и снабжение", panel_x + 18, warning_y, arcade.color.WHITE, 14)
        warning_y -= 18
        self.ensure_player_storage(self.human_player)
        storage_parts = []
        for category_key in STORAGE_CATEGORIES:
            capacity = self.human_player.storage_capacity.get(category_key, 0.0)
            used = self.human_player.storage_used.get(category_key, 0.0)
            fullness = used / capacity if capacity > 0 else (1.0 if used > 0 else 0.0)
            storage_parts.append(
                f"{STORAGE_CATEGORY_LABELS[category_key]} "
                f"{self.format_resource_amount(used)}/{self.format_resource_amount(capacity)} ({fullness:.0%})"
            )
        self.draw_ui_text(" | ".join(storage_parts[:2]), panel_x + 24, warning_y, (190, 210, 224), 9)
        warning_y -= 14
        self.draw_ui_text(" | ".join(storage_parts[2:]), panel_x + 24, warning_y, (190, 210, 224), 9)
        warning_y -= 14
        supply = self.human_player.supply_summary or self.recalculate_player_supply(self.human_player)
        self.draw_ui_text(
            f"Снабжение: {supply.get('average', 0.0):.0%} | слабых: {supply.get('low_tiles', 0)} | крит.: {supply.get('critical_tiles', 0)}",
            panel_x + 24,
            warning_y,
            (190, 210, 224),
            10,
        )
        warning_y -= 18
        red_items = []
        yellow_items = []
        for _category, category_problems in problems.items():
            red_items.extend(category_problems["red"])
            yellow_items.extend(category_problems["yellow"])
        warnings = (
            [("red", item, f"Критично: {self.resource_display_name(item)}") for item in red_items]
            + [("yellow", item, f"Внимание: {self.resource_display_name(item)}") for item in yellow_items]
        )
        if warnings:
            for level, resource_key, warning in warnings[:3]:
                row_rect = (panel_x + 22, warning_y - 3, 360, 16)
                self.resource_warning_rects.append((row_rect, resource_key))
                fill = (92, 42, 42, 145) if level == "red" else (92, 76, 34, 135)
                arcade.draw_lbwh_rectangle_filled(*row_rect, fill)
                self.draw_ui_text(warning, panel_x + 28, warning_y, (238, 198, 90), 11)
                warning_y -= 16
        else:
            self.draw_ui_text("Все спокойно", panel_x + 28, warning_y, (180, 192, 205), 11)

        rows = self.resource_rows()
        table_y = panel_y + panel_height - 286
        title = next(label for key, label in RESOURCE_PANEL_CATEGORIES if key == self.resource_panel_category)
        self.draw_ui_text(title, panel_x + 18, table_y, arcade.color.WHITE, 15)
        header_y = table_y - 24
        headers = [
            ("Ресурс", 18),
            ("В земле", 184),
            ("Склад", 266),
            ("+/мес", 326),
            ("-/мес", 384),
            ("Хватит", 446),
        ]
        for text, offset in headers:
            self.draw_ui_text(text, panel_x + offset, header_y, (150, 166, 184), 10)

        row_rects = self.resource_row_rects(rows)
        visible_rows = self.visible_resource_rows(rows)
        for index, row in enumerate(visible_rows):
            x, y, width, height = row_rects[index]
            selected = row["key"] == self.selected_resource_key
            row_number = self.resource_scroll_index + index
            fill = (44, 58, 74, 180) if selected else ((24, 32, 42, 120) if row_number % 2 == 0 else (30, 38, 48, 120))
            arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
            for (value, color), (_header, offset) in zip(row["display_values"], headers):
                self.draw_ui_text(
                    value,
                    panel_x + offset,
                    y + height / 2,
                    color,
                    10,
                    anchor_y="center",
                )

        self.draw_resource_scrollbar(rows, row_rects)

        self.draw_selected_resource_card(panel_x, panel_y, panel_width, panel_height)

    def draw_resource_scrollbar(self, rows, row_rects):
        if not row_rects or len(rows) <= len(row_rects):
            return

        table_x, table_y, table_width, table_height = self.resource_table_rect(rows)
        track_x = table_x + table_width + 8
        arcade.draw_lbwh_rectangle_filled(track_x, table_y, 4, table_height, (42, 52, 64, 180))

        visible_count = len(row_rects)
        thumb_height = max(24, table_height * visible_count / len(rows))
        max_scroll = max(1, len(rows) - visible_count)
        thumb_y = table_y + (table_height - thumb_height) * (1 - self.resource_scroll_index / max_scroll)
        arcade.draw_lbwh_rectangle_filled(track_x - 2, thumb_y, 8, thumb_height, (130, 154, 184, 220))

    def draw_selected_resource_card(self, panel_x, panel_y, panel_width, panel_height):
        if not self.selected_resource_key:
            return

        card_x, card_y, card_width, card_height = self.selected_resource_card_rect()
        arcade.draw_lbwh_rectangle_filled(card_x, card_y, card_width, card_height, (22, 29, 38, 230))
        arcade.draw_lbwh_rectangle_outline(card_x, card_y, card_width, card_height, (100, 126, 155), 1)

        close_x, close_y, close_width, close_height = self.selected_resource_close_rect()
        arcade.draw_lbwh_rectangle_filled(close_x, close_y, close_width, close_height, (50, 58, 68))
        arcade.draw_lbwh_rectangle_outline(close_x, close_y, close_width, close_height, (150, 166, 184), 1)
        self.draw_ui_text(
            "X",
            close_x + close_width / 2,
            close_y + close_height / 2,
            arcade.color.WHITE,
            12,
            anchor_x="center",
            anchor_y="center",
        )
        self.draw_ui_text(
            self.resource_display_name(self.selected_resource_key),
            card_x + 14,
            card_y + card_height - 26,
            arcade.color.WHITE,
            15,
        )
        y = card_y + card_height - 62
        source_tiles = self.resource_output_source_tiles(self.human_player, self.selected_resource_key)
        if source_tiles:
            sources_count = len(source_tiles)
        elif self.resource_panel_category == "raw":
            sources_count = self.resource_sources_count(self.selected_resource_key)
        else:
            sources_count = 0
        self.draw_ui_text(f"Источники: {sources_count} клетки", card_x + 14, y, (220, 230, 240), 12)
        y -= 30

        balance = self.cached_resource_balance_breakdown(self.human_player)
        category = self.resource_category_for_key(self.selected_resource_key)
        entry = balance.get(category, {}).get(self.selected_resource_key, {})
        production = entry.get("production", 0.0)
        consumption = entry.get("consumption", 0.0)
        max_line_chars = max(20, int((card_width - 48) / 7))

        self.draw_ui_text("Производство", card_x + 14, y, arcade.color.WHITE, 12)
        y -= 20
        if production > 0:
            for label, amount, percent in entry.get("production_breakdown", []):
                if amount <= 0:
                    continue
                text = f"{label}: {percent:.0f}% ({self.format_resource_amount(amount)}/мес)"
                for line in textwrap.wrap(text, width=max_line_chars) or [text]:
                    self.draw_ui_text(line, card_x + 20, y, (206, 218, 230), 11)
                    y -= 16
        else:
            self.draw_ui_text("Текущего прихода нет", card_x + 20, y, (180, 192, 205), 11)
            y -= 16
        y -= 6

        self.draw_ui_text("Потребление", card_x + 14, y, arcade.color.WHITE, 12)
        y -= 20
        breakdown = entry.get("consumption_breakdown", [])
        if consumption > 0:
            for label, amount, percent in breakdown:
                if amount <= 0 and label != "Стройки":
                    continue
                text = f"{label}: {percent:.0f}% ({self.format_resource_amount(amount)}/мес)"
                for line in textwrap.wrap(text, width=max_line_chars) or [text]:
                    self.draw_ui_text(
                        line,
                        card_x + 20,
                        y,
                        (206, 218, 230),
                        11,
                    )
                    y -= 16
        else:
            self.draw_ui_text("Текущего расхода нет", card_x + 20, y, (180, 192, 205), 11)
            y -= 16

        self.draw_ui_text("Описание", card_x + 14, y, arcade.color.WHITE, 12)
        y -= 20
        description = self.resource_usage_description(self.selected_resource_key)
        for line in self.wrap_text_lines(description):
            self.draw_ui_text(line, card_x + 14, y, (196, 208, 220), 11)
            y -= 16

    def handle_resources_panel_click(self, x, y):
        if self.active_top_panel_key != "resources":
            return False

        if self.selected_resource_key and self.point_in_rect(x, y, self.selected_resource_close_rect()):
            self.selected_resource_key = None
            self.create_map_overview()
            self.refresh_visible_tiles()
            return True

        for rect, resource_key in self.resource_warning_rects:
            if self.point_in_rect(x, y, rect):
                self.resource_panel_category = self.resource_category_for_key(resource_key)
                self.selected_resource_key = resource_key
                self.resource_scroll_index = 0
                self.create_map_overview()
                self.refresh_visible_tiles()
                return True

        for index, (category_key, _label) in enumerate(RESOURCE_PANEL_CATEGORIES):
            if self.point_in_rect(x, y, self.resource_category_rects()[index]):
                self.resource_panel_category = category_key
                self.selected_resource_key = None
                self.resource_scroll_index = 0
                self.create_map_overview()
                self.refresh_visible_tiles()
                return True

        rows = self.resource_rows()
        visible_rows = self.visible_resource_rows(rows)
        for index, rect in enumerate(self.resource_row_rects(rows)):
            if self.point_in_rect(x, y, rect):
                self.selected_resource_key = visible_rows[index]["key"]
                self.create_map_overview()
                self.refresh_visible_tiles()
                return True

        return False

    def trade_category_rects_for_panel(self):
        panel_x, panel_y, panel_width, panel_height = self.side_panel_rect()
        block_width = 190
        block_height = 40
        gap = 10
        y = panel_y + panel_height - 198
        return [
            (panel_x + 18 + index * (block_width + gap), y, block_width, block_height)
            for index, _category in enumerate(RESOURCE_PANEL_CATEGORIES)
        ]

    def trade_panel_snapshot(self):
        if not self.human_player:
            return {"rows": [], "flows": {}}
        player = self.human_player
        market_state = self.simulation_server.market_state
        balance_last_update = getattr(player, "resource_balance_last_update", 0.0)
        balance_is_stale = (
            getattr(player, "resource_balance_dirty", False)
            and (time.time() - balance_last_update >= 1.0)
        )
        cache_key = (
            self.trade_panel_category,
            getattr(player, "trade_contract_revision", 0),
            round(balance_last_update, 3),
            market_state.revision,
            self.politics.revision,
            tuple(p.trade_contract_revision for p in self.players),
        )
        if (
            self.trade_panel_cache
            and self.trade_panel_cache.get("key") == cache_key
            and not balance_is_stale
        ):
            return self.trade_panel_cache

        balance = self.cached_resource_balance_breakdown(player, max_age=1.0)
        contracts = self.normalized_trade_contracts(getattr(player, "trade_contracts", []))
        cache_key = (
            self.trade_panel_category,
            getattr(player, "trade_contract_revision", 0),
            round(getattr(player, "resource_balance_last_update", 0.0), 3),
            market_state.revision,
            self.politics.revision,
            tuple(p.trade_contract_revision for p in self.players),
        )
        trade_flows = self.estimate_monthly_trade_flows(player, contracts=contracts)
        diagnostics = self.trade_contract_diagnostics(player, contracts, trade_flows)
        contract_amounts = {
            (contract["resource"], contract["mode"]): contract["amount"]
            for contract in contracts
        }
        rows = []
        for resource_key in self.tradeable_resource_keys(self.trade_panel_category):
            entry = balance.get(self.trade_panel_category, {}).get(resource_key, {})
            stock = entry.get("stock", self.stockpile_amount(player, resource_key))
            market_state.ensure_resource(resource_key)
            price_change = self.market_price_change_fraction(resource_key)
            rows.append({
                "key": resource_key,
                "stock": stock,
                "balance": entry.get("balance", 0.0),
                "buy_price": self.trade_unit_price(player, resource_key, "buy"),
                "sell_price": self.trade_unit_price(player, resource_key, "sell"),
                "market_price": self.market_current_price(resource_key),
                "price_change": price_change,
                "market_demand": market_state.demand.get(resource_key, 0.0),
                "market_supply": market_state.supply.get(resource_key, 0.0),
                "buy": contract_amounts.get((resource_key, "buy"), 0.0),
                "sell": contract_amounts.get((resource_key, "sell"), 0.0),
            })
        for row in rows:
            contract_text = "--"
            mode = "buy" if row["buy"] > 0 else "sell"
            row["contract_state"], row["contract_status"] = diagnostics.get((row["key"], mode), ("none", ""))
            contract_color = (236, 148, 132) if row["contract_state"] == "blocked" else (238, 198, 90) if row["contract_state"] == "partial" else (220, 230, 240)
            if row["buy"] > 0:
                contract_text = f"Покупка {self.format_resource_amount(row['buy'])}"
            elif row["sell"] > 0:
                contract_text = f"Продажа {self.format_resource_amount(row['sell'])}"
            price_text = f"{self.format_money(row['buy_price'])}/{self.format_money(row['sell_price'])}"
            change_text = f"{row['price_change']:+.0%}"
            change_color = (174, 224, 158) if row["price_change"] >= 0 else (236, 168, 154)
            market_text = f"{self.format_resource_amount(row['market_demand'])}/{self.format_resource_amount(row['market_supply'])}"
            if market_state.revision == 0:
                market_text = "--"
            balance_color = (170, 222, 154) if row["balance"] >= 0 else (238, 168, 154)
            row["display_values"] = [
                (self.resource_display_name(row["key"]), (220, 230, 240), 0),
                (self.format_resource_amount(row["stock"]), (220, 230, 240), 118),
                (self.format_resource_amount(row["balance"]), balance_color, 180),
                (price_text, (220, 230, 240), 244),
                (change_text, change_color, 332),
                (market_text, (190, 210, 224), 378),
                (contract_text, contract_color, 466),
            ]
        self.trade_panel_cache = {"key": cache_key, "rows": rows, "flows": trade_flows}
        return self.trade_panel_cache

    def trade_rows(self):
        return self.trade_panel_snapshot().get("rows", [])

    def scroll_trade_rows(self, amount):
        rows = self.trade_rows()
        panel_x, panel_y, _panel_width, panel_height = self.side_panel_rect()
        table_y = panel_y + panel_height - 254
        row_height = 44
        max_rows = max(1, int((table_y - 28 - (panel_y + 28)) / row_height))
        max_scroll = max(0, len(rows) - max_rows)
        old_index = self.trade_scroll_index
        self.trade_scroll_index = max(0, min(max_scroll, self.trade_scroll_index + int(amount)))
        return self.trade_scroll_index != old_index

    @staticmethod
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
        track_x = table_x + panel_width - 36
        buttons_right = track_x - 12
        for index, row in enumerate(visible_rows):
            row_y = start_y - index * row_height
            row_number = self.trade_scroll_index + index
            fill = (24, 32, 42, 118) if row_number % 2 == 0 else (30, 38, 48, 118)
            self.append_trade_rect_shapes(shapes, (table_x, row_y - 16, panel_width - 36, row_height), fill)
            if row["contract_state"] == "blocked":
                shapes.append(arcade.shape_list.create_line(table_x + 466, row_y + 9, table_x + 574, row_y + 9, (236, 148, 132), 1))
            button_specs = [
                ("-", "buy", -TRADE_CONTRACT_STEP, buttons_right - 126),
                ("+", "buy", TRADE_CONTRACT_STEP, buttons_right - 98),
                ("-", "sell", -TRADE_CONTRACT_STEP, buttons_right - 52),
                ("+", "sell", TRADE_CONTRACT_STEP, buttons_right - 24),
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
            tuple((row["key"], row["contract_state"]) for row in visible_rows),
        )
        if self.trade_table_shape_cache_key != shape_key:
            self.rebuild_trade_table_shapes(table_x, panel_y, panel_width, table_y, rows, visible_rows, start_y, row_height, max_rows, max_scroll)
            self.trade_table_shape_cache_key = shape_key
        self.trade_action_rects = list(self.trade_table_shape_actions)
        self.trade_table_shape_list.draw()

    def draw_trade_panel_content(self, panel_x, panel_y, panel_width, panel_height):
        if not self.human_player:
            return
        self.begin_trade_text_frame()
        player = self.human_player
        self.trade_action_rects = []
        with self.profiler.measure("trade_layout"):
            self.trade_category_rects = self.trade_category_rects_for_panel()
        with self.profiler.measure("trade_snapshot"):
            snapshot = self.trade_panel_snapshot()
        trade_flows = snapshot["flows"]
        balance = trade_flows["money_balance"]
        with self.profiler.measure("trade_header"):
            buy_limit_text = (
                f"Покупка: {self.format_resource_amount(trade_flows['buy_capacity_used'])}/"
                f"{self.format_resource_amount(trade_flows['buy_capacity_limit'])} ед./мес"
            )
            sell_limit_text = (
                f"Продажа: {self.format_resource_amount(trade_flows['sell_capacity_used'])}/"
                f"{self.format_resource_amount(trade_flows['sell_capacity_limit'])} ед./мес"
            )
            money_color = (180, 226, 168) if balance >= 0 else (236, 168, 154)
            market_label = "Торговля: внешний рынок открыт" if player.politics.external_access else "Внешний рынок закрыт. Доступны только сделки со странами"
            self.draw_trade_text(market_label, panel_x + 18, panel_y + panel_height - 70,
                                 arcade.color.WHITE if player.politics.external_access else (238, 198, 90), 13)
            self.draw_trade_text(buy_limit_text, panel_x + 18, panel_y + panel_height - 94, (205, 216, 228), 11)
            self.draw_trade_text(sell_limit_text, panel_x + 18, panel_y + panel_height - 112, (205, 216, 228), 11)
            self.draw_trade_text(
                f"Деньги от торговли: {self.format_money(balance)}/мес",
                panel_x + 330,
                panel_y + panel_height - 94,
                money_color,
                11,
            )
            self.draw_trade_text(
                "Лимиты: "
                f"покупка {self.format_resource_amount(trade_flows['buy_logistics_capacity_limit'])} лог. / "
                f"{self.format_resource_amount(trade_flows['buy_max_capacity_limit'])} рынок; "
                f"продажа {self.format_resource_amount(trade_flows['sell_logistics_capacity_limit'])} лог. / "
                f"{self.format_resource_amount(trade_flows['sell_max_capacity_limit'])} рынок",
                panel_x + 18,
                panel_y + panel_height - 130,
                (170, 188, 204),
                10,
            )
            market_limit_total = trade_flows["buy_max_capacity_limit"] + trade_flows["sell_max_capacity_limit"]
            actual_limit_total = trade_flows["buy_capacity_limit"] + trade_flows["sell_capacity_limit"]
            trade_efficiency = actual_limit_total / market_limit_total if market_limit_total > 0 else 1.0
            self.draw_trade_text(
                f"Эфф. торговли: {trade_efficiency:.0%}",
                panel_x + panel_width - 18,
                panel_y + panel_height - 130,
                (190, 214, 232),
                10,
                anchor_x="right",
            )
            next_execution = self.simulation_server.next_market_execution_time
            next_execution_text = (
                f"{next_execution.year}-{next_execution.month:02}-{next_execution.day:02} "
                f"{next_execution.hour:02}:{next_execution.minute:02}"
            )
            self.draw_trade_text(
                f"Исполнение: понедельник 00:00, раз в неделю. След.: {next_execution_text}",
                panel_x + 18,
                panel_y + panel_height - 146,
                (156, 176, 194),
                10,
            )

        with self.profiler.measure("trade_categories"):
            for index, (category_key, label) in enumerate(RESOURCE_PANEL_CATEGORIES):
                x, y, width, height = self.trade_category_rects[index]
                active = category_key == self.trade_panel_category
                fill = (58, 88, 112, 220) if active else (30, 40, 52, 175)
                border = (170, 202, 232) if active else (86, 108, 132)
                arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
                arcade.draw_lbwh_rectangle_outline(x, y, width, height, border, 1)
                self.draw_trade_text(label, x + 10, y + height / 2, (230, 238, 246), 12, anchor_y="center")

        rows = snapshot["rows"]
        table_x = panel_x + 18
        table_y = panel_y + panel_height - 254
        headers = [
            ("Ресурс", 0),
            ("Склад", 118),
            ("Баланс", 180),
            ("Цена", 244),
            ("Изм.", 332),
            ("Спрос/пр.", 378),
            ("Контракт", 466),
        ]
        with self.profiler.measure("trade_table_header"):
            for text, offset in headers:
                self.draw_trade_text(text, table_x + offset, table_y, (150, 166, 184), 10)

        row_height = 44
        y = table_y - 28
        max_rows = max(1, int((y - (panel_y + 28)) / row_height))
        max_scroll = max(0, len(rows) - max_rows)
        self.trade_scroll_index = max(0, min(self.trade_scroll_index, max_scroll))
        visible_rows = rows[self.trade_scroll_index:self.trade_scroll_index + max_rows]
        with self.profiler.measure("trade_table_shapes"):
            self.draw_trade_table_shapes(table_x, panel_y, panel_width, table_y, rows, visible_rows, y, row_height, max_rows, max_scroll)
        with self.profiler.measure("trade_rows"):
            for index, row in enumerate(visible_rows):
                row_y = y - index * row_height
                row_number = self.trade_scroll_index + index
                for value, color, offset in row["display_values"]:
                    self.draw_trade_text(value, table_x + offset, row_y + 9, color, 10, anchor_y="center")
                if row["contract_status"]:
                    color = (236, 148, 132) if row["contract_state"] == "blocked" else (238, 198, 90) if row["contract_state"] == "partial" else (170, 210, 180)
                    self.draw_trade_text(row["contract_status"], table_x + 4, row_y - 9, color, 9, anchor_y="center")

        with self.profiler.measure("trade_buttons"):
            pass

        with self.profiler.measure("trade_footer"):
            legend_y = panel_y + 20
            footer = "Спрос/предложение: итоги последних торгов. Объём контракта не гарантирован."
            if self.simulation_server.market_state.revision == 0:
                footer = "Спрос/предложение появятся после первых торгов. Контракты ожидают исполнения."
            self.draw_trade_text(footer,
                                 panel_x + 18, legend_y, (160, 176, 192), 10)
            self.clear_unused_trade_text()

    def handle_trade_panel_click(self, x, y, modifiers=0):
        if self.active_top_panel_key != "trade":
            return False
        for index, (category_key, _label) in enumerate(RESOURCE_PANEL_CATEGORIES):
            if index < len(self.trade_category_rects) and self.point_in_rect(x, y, self.trade_category_rects[index]):
                self.trade_panel_category = category_key
                self.trade_scroll_index = 0
                self.trade_panel_cache = None
                return True
        for rect, resource_key, mode, delta in self.trade_action_rects:
            if self.point_in_rect(x, y, rect):
                step = TRADE_CONTRACT_SHIFT_STEP if self.shift_modifier_active(modifiers) else TRADE_CONTRACT_STEP
                adjusted_delta = step if delta > 0 else -step
                self.adjust_trade_contract(self.human_player, resource_key, mode, adjusted_delta)
                self.trade_panel_cache = None
                self.recalculate_resource_balance_breakdown(self.human_player)
                return True
        return True

    def construction_queue_rows(self):
        if not self.human_player:
            return []
        return list(self.human_player.construction_queue)

    def construction_project_label(self, project):
        cost = project.get("cost", {})
        building_key = cost.get("building") or project.get("building")
        tile = project.get("tile")
        label = BUILDING_DISPLAY_NAMES.get(building_key, building_key or "--")
        if project.get("project_type") == "repair":
            label = f"Ремонт: {label}"
        if tile:
            return f"{label} {tile.q}:{tile.r}"
        return label

    @staticmethod
    def construction_project_group_key(project):
        cost = project.get("cost", {})
        tile = project.get("tile")
        building_key = cost.get("building") or project.get("building")
        return project.get("project_type", "build"), id(tile), building_key

    def construction_queue_groups(self, rows=None):
        rows = self.construction_queue_rows() if rows is None else rows
        groups = []
        for index, project in enumerate(rows):
            group_key = self.construction_project_group_key(project)
            if groups and groups[-1]["key"] == group_key:
                groups[-1]["projects"].append(project)
                groups[-1]["end_index"] = index
                continue
            groups.append({
                "key": group_key,
                "projects": [project],
                "start_index": index,
                "end_index": index,
            })
        return groups

    def construction_group_label(self, group):
        label = self.construction_project_label(group["projects"][0])
        count = len(group["projects"])
        return f"{label} x{count}" if count > 1 else label

    @staticmethod
    def construction_group_coverage_label(group):
        projects = group["projects"]
        first_cost = projects[0].get("cost", {})
        last_cost = projects[-1].get("cost", {})
        if projects[0].get("project_type") == "repair":
            from_health = first_cost.get("from_health", projects[0].get("from_health", 1.0))
            if projects[0].get("progress", 0.0) > 0:
                target = first_cost.get("target_health", 1.0)
                from_health += (target - from_health) * max(0.0, min(1.0, projects[0].get("progress", 0.0)))
            return f"{from_health:.0%}->100%"
        from_coverage = first_cost.get("from_coverage", 0.0)
        if projects[0].get("progress", 0.0) > 0:
            target = first_cost.get("target_coverage", from_coverage)
            from_coverage += (target - from_coverage) * max(0.0, min(1.0, projects[0].get("progress", 0.0)))
        target_coverage = last_cost.get("target_coverage", from_coverage)
        return f"{from_coverage:.0%}->{target_coverage:.0%}"

    def format_resource_amount_pairs(self, amounts, limit=3):
        items = [
            (key, amount)
            for key, amount in sorted((amounts or {}).items(), key=lambda item: item[1], reverse=True)
            if amount > 0
        ]
        if not items:
            return "--"
        parts = [
            f"{self.resource_display_name(key)} {self.format_resource_amount(amount)}"
            for key, amount in items[:limit]
        ]
        if len(items) > limit:
            parts.append(f"еще {len(items) - limit}")
        return ", ".join(parts)

    def active_construction_detail_lines(self, player):
        if not player or not player.construction_queue:
            return []
        active_projects = self.active_construction_projects(player)
        project = active_projects[0] if active_projects else player.construction_queue[0]
        build_power = self.build_power(player) / max(1, len(active_projects)) if active_projects else None
        if build_power is not None:
            build_power *= self.construction_project_speed_multiplier(project)
        status_info = self.evaluate_construction_project_status(
            player,
            project,
            month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
            build_power=build_power,
        )
        status = status_info["status"]
        lines = [
            f"Статус: {self.construction_project_status_label(status)}",
            f"Осталось: {self.format_build_duration(status_info['remaining_months'])}",
        ]
        if status == "waiting_money":
            lines.append(f"Не хватает: {self.format_money(status_info['missing_money'])}")
        elif status == "waiting_resources":
            lines.append(f"Не хватает: {self.format_resource_amount_pairs(status_info['missing_resources'])}")
        elif status == "waiting_power":
            lines.append("Нет строительной мощности")
        elif status == "paused":
            lines.append("Стройка остановлена вручную")
        elif self.construction_project_is_active_status(status):
            speed_note = self.construction_project_speed_note(project)
            if speed_note:
                lines.append(speed_note)
            monthly_delta = self.construction_project_progress_delta(
                player,
                project,
                month_fraction=1.0,
                build_power=build_power,
            )
            monthly_needs = self.construction_project_resource_needs(project, monthly_delta)
            consumption = self.format_resource_amount_pairs(monthly_needs, limit=2)
            if consumption != "--":
                lines.append(f"Расход/мес: {consumption}")
        return lines

    def toggle_active_construction_pause(self, player):
        if not player or not player.construction_queue:
            return False
        project = player.construction_queue[0]
        project["paused"] = not project.get("paused", False)
        status = "paused" if project["paused"] else "queued"
        self.set_construction_project_status(
            project,
            status,
            ["остановлено игроком"] if project["paused"] else None,
        )
        self.mark_player_resource_balance_dirty(player)
        return True

    def construction_queue_item_rects(self, rows):
        groups = self.construction_queue_groups(rows)
        panel_x, panel_y, panel_width, panel_height = self.side_panel_rect()
        start_y = panel_y + panel_height - 112
        row_height = 26
        reserved_bottom = panel_y + 310
        max_expanded_count = max(4, int((start_y - reserved_bottom) / row_height) + 1)
        visible_count = min(len(groups), max_expanded_count) if self.construction_queue_expanded else min(4, len(groups))
        return [
            (panel_x + 18, start_y - index * row_height, panel_width - 36, row_height - 3)
            for index in range(visible_count)
        ]

    def construction_content_layout(self, rows=None):
        rows = self.construction_queue_rows() if rows is None else rows
        groups = self.construction_queue_groups(rows)
        panel_x, panel_y, panel_width, panel_height = self.side_panel_rect()
        queue_rects = self.construction_queue_item_rects(rows)
        if queue_rects:
            queue_bottom = queue_rects[-1][1]
            if len(groups) > 4:
                queue_bottom -= 24
        else:
            queue_bottom = panel_y + panel_height - 112
        detail_y = queue_bottom - 20 if rows else None
        detail_height = 58 if rows else 0
        speed_y = queue_bottom - 42 - detail_height
        options_top = min(speed_y - 78, panel_y + panel_height - 310)
        options_bottom_limit = panel_y + 76
        return {
            "queue_rects": queue_rects,
            "detail_y": detail_y,
            "speed_y": speed_y,
            "options_top": max(options_bottom_limit + 30, options_top),
        }

    def construction_building_option_rects(self):
        panel_x, panel_y, panel_width, _panel_height = self.side_panel_rect()
        start_y = self.construction_content_layout()["options_top"]
        row_height = 30
        left_width = (panel_width - 46) / 2
        rects = []
        for index, _item in enumerate(BUILDING_TYPES):
            col = index % 2
            row = index // 2
            x = panel_x + 18 + col * (left_width + 10)
            y = start_y - row * (row_height + 7)
            rects.append((x, y, left_width, row_height))
        return rects

    def construction_start_rect(self):
        panel_x, panel_y, panel_width, _panel_height = self.side_panel_rect()
        return panel_x + 18, panel_y + 24, panel_width - 36, 36

    def construction_pause_rect(self):
        panel_x, panel_y, panel_width, panel_height = self.side_panel_rect()
        return panel_x + panel_width - 150, panel_y + panel_height - 80, 132, 26

    def draw_construction_panel_content(self, panel_x, panel_y, panel_width, panel_height):
        if not self.human_player:
            return

        self.construction_queue_toggle_rect = None
        self.construction_queue_priority_rects = []
        self.construction_building_rects = self.construction_building_option_rects()
        self.construction_start_button_rect = self.construction_start_rect()
        self.construction_pause_button_rect = None
        rows = self.construction_queue_rows()
        if rows:
            self.evaluate_construction_project_status(
                self.human_player,
                rows[0],
                month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
            )
        groups = self.construction_queue_groups(rows)
        queue_y = panel_y + panel_height - 70
        self.draw_ui_text("Очередь строительства", panel_x + 18, queue_y, arcade.color.WHITE, 14)
        if rows:
            self.construction_pause_button_rect = self.construction_pause_rect()
            pause_x, pause_y, pause_width, pause_height = self.construction_pause_button_rect
            paused = rows[0].get("paused", False)
            pause_fill = (80, 98, 56, 220) if paused else (52, 62, 78, 220)
            pause_border = (190, 216, 132, 230) if paused else (120, 146, 174, 220)
            pause_label = "Продолжить" if paused else "Пауза стройки"
            arcade.draw_lbwh_rectangle_filled(pause_x, pause_y, pause_width, pause_height, pause_fill)
            arcade.draw_lbwh_rectangle_outline(pause_x, pause_y, pause_width, pause_height, pause_border, 1)
            self.draw_ui_text(
                pause_label,
                pause_x + pause_width / 2,
                pause_y + pause_height / 2,
                arcade.color.WHITE,
                10,
                anchor_x="center",
                anchor_y="center",
            )
        layout = self.construction_content_layout(rows)
        queue_rects = layout["queue_rects"]
        visible_count = len(queue_rects)
        active_project_ids = {id(project) for project in self.active_construction_projects(self.human_player)}
        if groups:
            for index, group in enumerate(groups[:visible_count]):
                project = group["projects"][0]
                x, y, width, height = queue_rects[index]
                active = any(id(group_project) in active_project_ids for group_project in group["projects"])
                fill = (46, 70, 58, 190) if active else (30, 40, 52, 160)
                arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
                arcade.draw_lbwh_rectangle_outline(x, y, width, height, (82, 108, 132), 1)
                prefix = self.construction_project_status_label(project.get("status", "queued")) if active else "Ждет"
                self.draw_ui_text(
                    f"{prefix}: {self.construction_group_label(group)}",
                    x + 8,
                    y + height / 2,
                    (226, 236, 244),
                    10,
                    anchor_y="center",
                )
                up_rect = (x + width - 58, y + 3, 20, height - 6)
                down_rect = (x + width - 34, y + 3, 20, height - 6)
                for rect, direction, label in ((up_rect, -1, "^"), (down_rect, 1, "v")):
                    enabled = self.can_move_construction_group(self.human_player, group, direction)
                    button_fill = (52, 70, 88, 210) if enabled else (34, 40, 48, 150)
                    button_border = (128, 156, 184, 220) if enabled else (70, 82, 96, 150)
                    text_color = (232, 240, 248) if enabled else (128, 138, 148)
                    arcade.draw_lbwh_rectangle_filled(*rect, button_fill)
                    arcade.draw_lbwh_rectangle_outline(*rect, button_border, 1)
                    self.draw_ui_text(
                        label,
                        rect[0] + rect[2] / 2,
                        rect[1] + rect[3] / 2,
                        text_color,
                        10,
                        anchor_x="center",
                        anchor_y="center",
                    )
                    self.construction_queue_priority_rects.append((rect, group["start_index"], group["end_index"], direction))
                self.draw_ui_text(
                    self.construction_group_coverage_label(group),
                    x + width - 66,
                    y + height / 2,
                    (226, 236, 244),
                    10,
                    anchor_x="right",
                    anchor_y="center",
                )
            if len(groups) > 4:
                toggle_y = queue_rects[-1][1] - 24
                hidden_count = max(0, len(groups) - visible_count)
                toggle_text = "Свернуть очередь" if self.construction_queue_expanded else f"Показать еще {hidden_count}"
                self.construction_queue_toggle_rect = (panel_x + 18, toggle_y, panel_width - 36, 20)
                self.draw_ui_text(toggle_text, panel_x + 24, toggle_y + 10, (180, 194, 210), 10, anchor_y="center")
        else:
            self.draw_ui_text("Пока пусто", panel_x + 28, queue_y - 28, (180, 192, 205), 11)

        if rows and layout["detail_y"] is not None:
            detail_y = layout["detail_y"]
            detail_lines = self.active_construction_detail_lines(self.human_player)
            for line_index, line in enumerate(detail_lines[:4]):
                color = (210, 222, 234)
                if line.startswith("Не хватает") or line.startswith("Нет "):
                    color = (236, 178, 154)
                elif line.startswith("Статус: Строится") or line.startswith("Статус: Ремонт"):
                    color = (190, 230, 174)
                self.draw_ui_text(
                    line,
                    panel_x + 28,
                    detail_y - line_index * 15,
                    color,
                    10,
                )

        speed_y = layout["speed_y"]
        speed = self.build_power(self.human_player)
        self.draw_ui_text("Скорость строительства", panel_x + 18, speed_y, arcade.color.WHITE, 14)
        self.draw_ui_text(
            f"{speed:.0f} строй-очков в месяц",
            panel_x + 28,
            speed_y - 24,
            (220, 230, 240),
            12,
        )
        self.draw_ui_text(
            f"До {CONSTRUCTION_PARALLEL_PROJECTS} проектов делят строймощность между собой.",
            panel_x + 28,
            speed_y - 44,
            (160, 174, 190),
            10,
        )

        for index, (building_key, label) in enumerate(BUILDING_TYPES):
            x, y, width, height = self.construction_building_rects[index]
            active = index == self.selected_construction_index
            fill = (58, 88, 112, 220) if active else (30, 40, 52, 175)
            border = (170, 202, 232) if active else (86, 108, 132)
            arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
            arcade.draw_lbwh_rectangle_outline(x, y, width, height, border, 1)
            self.draw_ui_text(label, x + 8, y + height / 2, (230, 238, 246), 10, anchor_y="center")

        button_x, button_y, button_width, button_height = self.construction_start_button_rect
        button_active = self.construction_placement_mode
        fill = (72, 112, 82, 230) if button_active else (42, 62, 82, 220)
        border = (170, 220, 180) if button_active else (110, 138, 166)
        arcade.draw_lbwh_rectangle_filled(button_x, button_y, button_width, button_height, fill)
        arcade.draw_lbwh_rectangle_outline(button_x, button_y, button_width, button_height, border, 2)
        label = "Отменить размещение" if button_active else "Построить"
        self.draw_ui_text(label, button_x + button_width / 2, button_y + button_height / 2,
                          arcade.color.WHITE, 13, anchor_x="center", anchor_y="center")

    def handle_construction_panel_click(self, x, y):
        if self.active_top_panel_key != "construction":
            return False

        if self.construction_pause_button_rect and self.point_in_rect(x, y, self.construction_pause_button_rect):
            self.toggle_active_construction_pause(self.human_player)
            return True

        for rect, start_index, end_index, direction in self.construction_queue_priority_rects:
            if self.point_in_rect(x, y, rect):
                group = next(
                    (
                        candidate
                        for candidate in self.construction_queue_groups()
                        if candidate["start_index"] == start_index
                        and candidate["end_index"] == end_index
                    ),
                    None,
                )
                self.move_construction_group(self.human_player, group, direction)
                return True

        if self.construction_queue_toggle_rect and self.point_in_rect(x, y, self.construction_queue_toggle_rect):
            self.construction_queue_expanded = not self.construction_queue_expanded
            return True

        for index, rect in enumerate(self.construction_building_option_rects()):
            if self.point_in_rect(x, y, rect):
                self.selected_construction_index = index
                self.invalidate_construction_placement_cache()
                if self.construction_placement_mode:
                    self.create_map_overview()
                    self.refresh_visible_tiles()
                return True

        if self.point_in_rect(x, y, self.construction_start_rect()):
            self.set_construction_placement_mode(not self.construction_placement_mode)
            return True

        return True

    def draw_army_panel_content(self, panel_x, panel_y, panel_width, panel_height):
        player = self.human_player
        if not player:
            return

        content_x = panel_x + 18
        content_right = panel_x + panel_width - 18
        y = panel_y + panel_height - 72
        divisions = list(getattr(player, "divisions", []) or [])
        armies = list(getattr(player, "armies", []) or [])
        selected_count = len(self.selected_division_ids)
        avg_org = sum(division.organization for division in divisions) / max(1, len(divisions))
        avg_strength = sum(division.strength for division in divisions) / max(1, len(divisions))

        self.draw_ui_text("Сводка армии", content_x, y, arcade.color.WHITE, 15)
        y -= 24
        summary_lines = [
            ("Дивизии", f"{len(divisions)}"),
            ("Армии", f"{len(armies)}"),
            ("Выбрано", f"{selected_count}"),
            ("Резерв людей", self.format_resource_amount(getattr(player, "manpower_reserve", 0.0))),
            ("Средняя орг.", f"{avg_org:.0f}%"),
            ("Средняя прочн.", f"{avg_strength:.0f}%"),
        ]
        column_width = max(170, (panel_width - 42) / 2)
        for index, (label, value) in enumerate(summary_lines):
            row_x = content_x + (index % 2) * column_width
            row_y = y - (index // 2) * 19
            self.draw_ui_text(label, row_x, row_y, (150, 166, 184), 10)
            self.draw_ui_text(value, row_x + min(118, column_width - 16), row_y, (220, 230, 240), 10, anchor_x="right")
        y -= 72

        arcade.draw_line(content_x, y + 8, content_right, y + 8, (72, 92, 112, 180), 1)
        self.draw_ui_text("Армейские ресурсы", content_x, y - 8, arcade.color.WHITE, 15)
        y -= 34
        self.draw_ui_text("Ресурс", content_x, y, (150, 166, 184), 10)
        self.draw_ui_text("Склад", content_x + 190, y, (150, 166, 184), 10, anchor_x="right")
        self.draw_ui_text("В дивизиях", content_right, y, (150, 166, 184), 10, anchor_x="right")
        y -= 18

        division_stock = {}
        division_capacity = {}
        for division in divisions:
            for key, amount in (division.supply_stock or {}).items():
                division_stock[key] = division_stock.get(key, 0.0) + max(0.0, amount)
            for key, amount in (division.supply_capacity or {}).items():
                division_capacity[key] = division_capacity.get(key, 0.0) + max(0.0, amount)

        always_show_army_resources = {
            "small_arms_ammo",
            "light_artillery_ammo",
            "light_aa_ammo",
            "autocannon_ammo",
            "artillery_ammo",
            "tank_ammo",
            "anti_air_ammo",
            "refined_fuel",
            "field_supplies",
        }
        for resource_key in DIVISION_ARMY_RESOURCE_KEYS:
            stock = self.stockpile_amount(player, resource_key)
            in_divisions = division_stock.get(resource_key, 0.0)
            capacity = division_capacity.get(resource_key, 0.0)
            if stock <= 0 and in_divisions <= 0 and capacity <= 0 and resource_key not in always_show_army_resources:
                continue
            self.draw_ui_text(self.resource_display_name(resource_key), content_x, y, (210, 222, 234), 10)
            self.draw_ui_text(self.format_resource_amount(stock), content_x + 190, y, (220, 230, 240), 10, anchor_x="right")
            div_text = f"{self.format_resource_amount(in_divisions)}/{self.format_resource_amount(capacity)}"
            ratio = self.clamp01(in_divisions / capacity) if capacity > 0 else 1.0
            color = (154, 224, 142) if ratio >= 0.65 else (236, 198, 90) if ratio >= 0.30 else (238, 128, 110)
            self.draw_ui_text(div_text, content_right, y, color, 10, anchor_x="right")
            y -= 17

        aircraft_inventory = self.player_aircraft_inventory_by_type(player)
        if aircraft_inventory:
            y -= 8
            arcade.draw_line(content_x, y + 8, content_right, y + 8, (72, 92, 112, 180), 1)
            self.draw_ui_text("Авиационный парк", content_x, y - 8, arcade.color.WHITE, 15)
            y -= 34
            self.draw_ui_text("Тип", content_x, y, (150, 166, 184), 10)
            self.draw_ui_text("На базах", content_x + 190, y, (150, 166, 184), 10, anchor_x="right")
            self.draw_ui_text("Резерв", content_right, y, (150, 166, 184), 10, anchor_x="right")
            y -= 18
            for aircraft_type, counts in sorted(aircraft_inventory.items()):
                aircraft_name = AIRCRAFT_TYPES.get(aircraft_type, {}).get("name", aircraft_type)
                if len(aircraft_name) > 25:
                    aircraft_name = aircraft_name[:24] + "..."
                self.draw_ui_text(aircraft_name, content_x, y, (210, 222, 234), 10)
                self.draw_ui_text(str(counts.get("based", 0)), content_x + 190, y, (220, 230, 240), 10, anchor_x="right")
                self.draw_ui_text(str(counts.get("reserve", 0)), content_right, y, (220, 230, 240), 10, anchor_x="right")
                y -= 17

        y -= 12
        arcade.draw_line(content_x, y + 8, content_right, y + 8, (72, 92, 112, 180), 1)
        button_h = 34
        for label in ("Конструктор дивизий", "Развертывание войск"):
            arcade.draw_lbwh_rectangle_filled(content_x, y - button_h, panel_width - 36, button_h, (32, 42, 54, 220))
            arcade.draw_lbwh_rectangle_outline(content_x, y - button_h, panel_width - 36, button_h, (84, 106, 130), 1)
            self.draw_ui_text(f"{label}: позже", content_x + 12, y - button_h / 2, (180, 192, 205), 12, anchor_y="center")
            y -= button_h + 8

    def draw_side_panel(self):
        if self.active_top_panel_key in ("politics", "diplomacy"):
            return
        if not self.active_top_panel_key and self.side_panel_progress <= 0:
            return

        panel_x, panel_y, panel_width, panel_height = self.side_panel_rect()
        arcade.draw_lbwh_rectangle_filled(panel_x, panel_y, panel_width, panel_height, (18, 24, 31, 244))
        arcade.draw_lbwh_rectangle_outline(panel_x, panel_y, panel_width, panel_height, (110, 130, 154), 2)

        title = next((label for key, label, _icon_name in TOP_NAV_TABS if key == self.active_top_panel_key), "")
        self.draw_ui_text(title, panel_x + 18, panel_y + panel_height - 28, arcade.color.WHITE, 18, anchor_y="center")

        close_x, close_y, close_width, close_height = self.side_panel_close_rect()
        close_fill = (96, 56, 58) if self.hovered_side_panel_close else (50, 58, 68)
        arcade.draw_lbwh_rectangle_filled(close_x, close_y, close_width, close_height, close_fill)
        arcade.draw_lbwh_rectangle_outline(close_x, close_y, close_width, close_height, (150, 166, 184), 1)
        self.draw_ui_text(
            "X",
            close_x + close_width / 2,
            close_y + close_height / 2,
            arcade.color.WHITE,
            14,
            anchor_x="center",
            anchor_y="center",
        )

        if self.active_top_panel_key == "resources":
            with self.profiler.measure("panel_resources"):
                self.draw_resources_panel_content(panel_x, panel_y, panel_width, panel_height)
        elif self.active_top_panel_key == "economy":
            with self.profiler.measure("panel_economy"):
                self.draw_economy_panel_content(panel_x, panel_y, panel_width, panel_height)
        elif self.active_top_panel_key == "trade":
            with self.profiler.measure("panel_trade"):
                self.draw_trade_panel_content(panel_x, panel_y, panel_width, panel_height)
        elif self.active_top_panel_key == "construction":
            with self.profiler.measure("panel_construction"):
                self.draw_construction_panel_content(panel_x, panel_y, panel_width, panel_height)
        elif self.active_top_panel_key == "military":
            with self.profiler.measure("panel_military"):
                self.draw_army_panel_content(panel_x, panel_y, panel_width, panel_height)
        else:
            self.draw_ui_text(
                "Раздел пока пуст",
                panel_x + 18,
                panel_y + panel_height - 72,
                (180, 192, 205),
                14,
            )

    def hex_panel_rect(self):
        width = min(380, max(320, self.window.width - 32))
        top = self.window.height - TOP_UI_HEIGHT - 12
        time_x, time_y, time_width, _time_height = self.time_panel_rect
        overlaps_time_panel = time_width > 0 and (self.window.width - width - 16) < time_x + time_width
        if overlaps_time_panel:
            top = min(top, time_y - 10)
        bottom = 78
        available_height = max(240, top - bottom)
        height = min(560, available_height)
        if height < 300:
            bottom = max(12, top - height)
        x = self.window.width - width - 16
        y = bottom
        return x, y, width, height

    def hex_panel_close_rect(self):
        panel_x, panel_y, panel_width, panel_height = self.hex_panel_rect()
        return panel_x + panel_width - 36, panel_y + panel_height - 36, 24, 24

    def hex_panel_build_button_rect(self):
        panel_x, panel_y, panel_width, _panel_height = self.hex_panel_rect()
        return panel_x + 16, panel_y + 14, panel_width - 32, 34

    def hex_panel_specialization_button_rect(self):
        panel_x, panel_y, panel_width, _panel_height = self.hex_panel_rect()
        return panel_x + 16, panel_y + 54, panel_width - 32, 32

    def hex_panel_content_bounds(self):
        panel_x, panel_y, panel_width, panel_height = self.hex_panel_rect()
        bottom_padding = 96 if self.selected_tile_has_industry() else 58
        return panel_y + bottom_padding, panel_y + panel_height - 52

    def clamp_hex_panel_scroll(self):
        content_bottom, content_top = self.hex_panel_content_bounds()
        visible_height = max(1, content_top - content_bottom)
        max_scroll = max(0.0, self.hex_panel_content_height - visible_height)
        self.hex_panel_scroll = max(0.0, min(max_scroll, self.hex_panel_scroll))

    def scroll_hex_panel(self, amount):
        old_scroll = self.hex_panel_scroll
        self.hex_panel_scroll += amount * 30
        self.clamp_hex_panel_scroll()
        return self.hex_panel_scroll != old_scroll

    def selected_tile_has_industry(self):
        return bool(self.selected_industry_tiles())

    @staticmethod
    def shift_modifier_active(modifiers):
        return bool(modifiers & arcade.key.MOD_SHIFT)

    @staticmethod
    def tile_key(tile):
        return tile.q, tile.r

    def tile_for_key(self, key):
        if key is None:
            return None
        if isinstance(key, str):
            parts = key.replace(":", ",").split(",")
            if len(parts) != 2:
                return None
            try:
                return self.hex_lookup.get((int(parts[0]), int(parts[1])))
            except ValueError:
                return None
        if isinstance(key, (tuple, list)) and len(key) >= 2:
            try:
                return self.hex_lookup.get((int(key[0]), int(key[1])))
            except (TypeError, ValueError):
                return None
        return None

    def selected_hex_tiles(self):
        if self.selected_tiles:
            return [tile for tile in self.selected_tiles if tile]
        return [self.selected_tile] if self.selected_tile else []

    def selected_industry_tiles(self):
        return [
            tile
            for tile in self.selected_hex_tiles()
            if (getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0) > 0
        ]

    def reset_hex_panel_view_state(self):
        self.hex_panel_scroll = 0.0
        self.hex_panel_content_height = 0.0
        self.hex_resources_expanded = False
        self.hex_resources_toggle_rect = None
        self.hex_panel_specialization_mode = False
        self.hex_air_wing_row_rects = []
        self.hex_air_wing_button_rects = []
        self.hex_air_defense_row_rects = []
        self.hex_air_defense_button_rects = []
        self.hex_airbase_upgrade_button_rect = None

    def set_hex_panel_message(self, message, timer=2.0):
        self.hex_panel_message = message or ""
        self.hex_panel_message_timer = max(0.0, float(timer))

    def selected_air_wings(self):
        selected_ids = set(getattr(self, "selected_air_wing_ids", set()) or set())
        if self.selected_air_wing_id:
            selected_ids.add(self.selected_air_wing_id)
        return [
            wing for wing in getattr(self, "air_wings", []) or []
            if wing.id in selected_ids and wing.owner is self.human_player
        ]

    def command_air_wings_for(self, wing):
        selected = self.selected_air_wings()
        if wing and any(selected_wing.id == wing.id for selected_wing in selected):
            return selected
        return [wing] if wing else []

    def clear_air_wing_map_modes(self):
        self.air_wing_target_mode_id = None
        self.air_wing_rebase_mode_id = None
        self.air_wing_target_mode_ids = set()
        self.air_wing_rebase_mode_ids = set()

    def clear_air_wing_selection(self):
        self.selected_air_wing_id = None
        self.selected_air_wing_ids.clear()
        self.clear_air_wing_map_modes()
        self.air_wing_mission_menu_wing_id = None
        self.air_wing_target_menu_wing_id = None
        self.air_wing_edit_menu_wing_id = None
        self.air_wing_risk_menu_wing_id = None
        self.air_wing_creation_open = False
        return True

    def select_air_wing(self, wing, additive=False, toggle=False):
        if not wing:
            return False
        if not additive and not toggle:
            self.selected_air_wing_ids = {wing.id}
            self.selected_air_wing_id = wing.id
        elif toggle and wing.id in self.selected_air_wing_ids:
            self.selected_air_wing_ids.discard(wing.id)
            if self.selected_air_wing_id == wing.id:
                self.selected_air_wing_id = next(iter(self.selected_air_wing_ids), None)
            if not self.selected_air_wing_ids:
                self.clear_air_wing_selection()
                return True
        else:
            self.selected_air_wing_ids.add(wing.id)
            self.selected_air_wing_id = wing.id
        self.selected_air_defense_unit_id = None
        self.clear_air_wing_map_modes()
        self.air_defense_move_mode_id = None
        if self.air_wing_mission_menu_wing_id not in (None, self.selected_air_wing_id):
            self.air_wing_mission_menu_wing_id = None
        if self.air_wing_target_menu_wing_id not in (None, self.selected_air_wing_id):
            self.air_wing_target_menu_wing_id = None
        if self.air_wing_edit_menu_wing_id not in (None, self.selected_air_wing_id):
            self.air_wing_edit_menu_wing_id = None
        if self.air_wing_risk_menu_wing_id not in (None, self.selected_air_wing_id):
            self.air_wing_risk_menu_wing_id = None
        return True

    def select_air_defense_unit(self, unit):
        if not unit:
            return False
        self.selected_air_defense_unit_id = unit.id
        self.selected_air_wing_id = None
        self.selected_air_wing_ids.clear()
        self.clear_air_wing_map_modes()
        return True

    def air_wing_available_auto_missions(self):
        return [
            ("cas", "CAS", "Непосредственная поддержка своих дивизий в бою в радиусе крыла."),
            ("intercept", "Перехват", "Перехватывать вражеские самолеты и перехватываемые боеприпасы, когда этот слой будет активен."),
            ("patrol", "Патруль", "Патрулировать район, повышая обнаружение авиации, ракет и других воздушных целей."),
            ("air_superiority", "Превосходство", "Бороться за контроль воздуха и повышать риск для вражеской авиации."),
            ("strategic_strike", "Удар", "Автоматически атаковать выбранные категории наземных целей, когда появится полный слой ударов."),
        ]

    def air_wing_target_priority_items(self):
        return [
            ("enemy_units", "Войска", "Дивизии, техника, артиллерия и войсковые средства поддержки."),
            ("supply_infrastructure", "Снабжение", "Склады, дороги, мосты, железная дорога и узлы снабжения."),
            ("infrastructure", "Инфраструктура", "Дороги, рельсы, мосты и прочие объекты темпа перемещения."),
            ("civilian_infrastructure", "Гражданская", "Городская и гражданская инфраструктура, если игрок сознательно выбирает такую цель."),
            ("industry", "Заводы", "Промышленность, энергетика и ресурсные объекты."),
            ("bases", "Базы", "Склады, узлы, укрепленные позиции и крупные военные объекты."),
            ("airbases", "Аэродромы", "Аэродромы, ангары, укрытия и авиация на земле при достаточной разведке."),
            ("air_defense", "ПВО/РЛС", "Позиции ПВО, радары и связанные с ними объекты."),
        ]

    def air_wing_risk_items(self):
        return [
            ("cautious", "Осторожно", "Крыло старается не входить в предполагаемую зону ПВО, чаще запускает оружие с дальней дистанции. Меньше риск носителю, но боеприпасы проще перехватывать."),
            ("normal", "Нормально", "Баланс риска и эффективности: без явной ПВО работает со средней дистанции, при угрозе старается держаться у границы опасной зоны."),
            ("aggressive", "Агрессивно", "Крыло подходит ближе ради точности и меньшего окна перехвата боеприпасов. Потери от ПВО и авиации противника вероятнее."),
        ]

    def air_wing_enabled_missions(self, wing):
        if not wing:
            return []
        raw_missions = getattr(wing, "enabled_missions", None)
        missions = list(raw_missions or [])
        if raw_missions is None and not missions and getattr(wing, "mission", "none") not in (None, "none"):
            missions = [wing.mission]
        allowed = self.air_wing_allowed_missions(wing)
        return [mission for mission in missions if mission in allowed]

    def air_wing_allowed_missions(self, wing):
        allowed = set()
        for aircraft_type in self.air_wing_composition(wing):
            allowed.update(self.aircraft_type_data(aircraft_type).get("allowed_missions", []))
        if not allowed and getattr(wing, "aircraft_type", None):
            allowed.update(self.aircraft_type_data(wing.aircraft_type).get("allowed_missions", []))
        return allowed

    def sync_air_wing_primary_mission(self, wing):
        if not wing:
            return
        enabled = self.air_wing_enabled_missions(wing)
        wing.enabled_missions = enabled
        wing.mission = enabled[0] if enabled else "none"

    def toggle_air_wing_enabled_mission(self, wing, mission):
        if not wing or mission not in self.air_wing_allowed_missions(wing):
            return False
        missions = list(getattr(wing, "enabled_missions", []) or [])
        if mission in missions:
            missions.remove(mission)
        else:
            missions.append(mission)
        wing.enabled_missions = missions
        self.sync_air_wing_primary_mission(wing)
        return True

    def set_air_wing_enabled_mission(self, wing, mission, enabled):
        if not wing or mission not in self.air_wing_allowed_missions(wing):
            return False
        missions = list(getattr(wing, "enabled_missions", []) or [])
        if enabled and mission not in missions:
            missions.append(mission)
        elif not enabled and mission in missions:
            missions.remove(mission)
        wing.enabled_missions = missions
        self.sync_air_wing_primary_mission(wing)
        return True

    def toggle_air_wing_target_priority(self, wing, target_key):
        if not wing:
            return False
        priorities = list(getattr(wing, "target_priorities", []) or [])
        if target_key in priorities:
            priorities.remove(target_key)
        else:
            priorities.append(target_key)
        wing.target_priorities = priorities
        return True

    def set_air_wing_target_priority(self, wing, target_key, enabled):
        if not wing:
            return False
        priorities = list(getattr(wing, "target_priorities", []) or [])
        if enabled and target_key not in priorities:
            priorities.append(target_key)
        elif not enabled and target_key in priorities:
            priorities.remove(target_key)
        wing.target_priorities = priorities
        return True

    def transfer_aircraft_to_wing(self, wing, aircraft_type, delta):
        if not wing or not wing.owner or aircraft_type not in AIRCRAFT_TYPES or delta == 0:
            return False
        composition = self.air_wing_composition(wing)
        if delta > 0:
            reserve = self.aircraft_stockpile_count(wing.owner, aircraft_type)
            free_capacity = self.air_wing_extra_capacity_for_type(wing, aircraft_type)
            added = min(int(delta), reserve, free_capacity)
            if added <= 0:
                return False
            if wing.owner.aircraft_stockpile is None:
                wing.owner.aircraft_stockpile = {}
            wing.owner.aircraft_stockpile[aircraft_type] = max(0, reserve - added)
            composition[aircraft_type] = composition.get(aircraft_type, 0) + added
            wing.aircraft_composition = composition
            self.sync_air_wing_composition_fields(wing)
            self.refresh_air_wing_interceptor_loadout(wing, refill_new_capacity=True)
            wing.ready_count += added
            return True
        current_count = composition.get(aircraft_type, 0)
        removed = min(abs(int(delta)), current_count, max(0, wing.aircraft_count - 1))
        if removed <= 0:
            return False
        remaining = current_count - removed
        if remaining > 0:
            composition[aircraft_type] = remaining
        else:
            composition.pop(aircraft_type, None)
        wing.aircraft_composition = composition
        wing.ready_count = max(0, wing.ready_count - min(wing.ready_count, removed))
        self.sync_air_wing_composition_fields(wing)
        self.add_aircraft_to_stockpile(wing.owner, aircraft_type, removed)
        return True

    def cycle_air_wing_mission(self, wing):
        if not wing:
            return False
        allowed = ["none"] + sorted(self.air_wing_allowed_missions(wing))
        if not allowed:
            return False
        try:
            current_index = allowed.index(wing.mission)
        except ValueError:
            current_index = 0
        wing.mission = allowed[(current_index + 1) % len(allowed)]
        wing.enabled_missions = [] if wing.mission == "none" else [wing.mission]
        self.sync_air_wing_primary_mission(wing)
        return True

    def cycle_air_wing_risk_policy(self, wing):
        if not wing:
            return False
        policies = ["cautious", "normal", "aggressive"]
        try:
            current_index = policies.index(wing.risk_policy)
        except ValueError:
            current_index = 1
        wing.risk_policy = policies[(current_index + 1) % len(policies)]
        return True

    def set_air_wing_target_mode_for(self, wings):
        wing_ids = {wing.id for wing in wings if wing}
        if not wing_ids:
            return False
        if set(self.air_wing_target_mode_ids or set()) == wing_ids:
            self.clear_air_wing_map_modes()
            return True
        self.air_wing_target_mode_ids = wing_ids
        self.air_wing_target_mode_id = next(iter(wing_ids), None)
        self.air_wing_rebase_mode_ids = set()
        self.air_wing_rebase_mode_id = None
        self.air_defense_move_mode_id = None
        return True

    def set_air_wing_rebase_mode_for(self, wings):
        wing_ids = {wing.id for wing in wings if wing}
        if not wing_ids:
            return False
        if set(self.air_wing_rebase_mode_ids or set()) == wing_ids:
            self.clear_air_wing_map_modes()
            return True
        self.air_wing_rebase_mode_ids = wing_ids
        self.air_wing_rebase_mode_id = next(iter(wing_ids), None)
        self.air_wing_target_mode_ids = set()
        self.air_wing_target_mode_id = None
        self.air_defense_move_mode_id = None
        return True

    def handle_hex_air_controls_click(self, x, y):
        for rect, action, obj_id in self.hex_air_wing_button_rects:
            if not self.point_in_rect(x, y, rect):
                continue
            wing = self.air_wing_by_id(obj_id)
            if not wing:
                return True
            self.select_air_wing(wing)
            if action == "mission":
                self.air_wing_mission_menu_wing_id = None if self.air_wing_mission_menu_wing_id == wing.id else wing.id
                self.air_wing_target_menu_wing_id = None
                self.air_wing_edit_menu_wing_id = None
                self.air_wing_risk_menu_wing_id = None
            elif action == "risk":
                self.air_wing_risk_menu_wing_id = None if self.air_wing_risk_menu_wing_id == wing.id else wing.id
                self.air_wing_mission_menu_wing_id = None
                self.air_wing_target_menu_wing_id = None
                self.air_wing_edit_menu_wing_id = None
            elif action == "target":
                self.set_air_wing_target_mode_for(self.command_air_wings_for(wing))
            elif action == "rebase":
                self.set_air_wing_rebase_mode_for(self.command_air_wings_for(wing))
            return True

        for rect, action, obj_id in self.hex_air_defense_button_rects:
            if not self.point_in_rect(x, y, rect):
                continue
            unit = self.air_defense_unit_by_id(obj_id)
            if not unit:
                return True
            self.select_air_defense_unit(unit)
            if action == "radar":
                unit.radar_active = not unit.radar_active
            return True

        for rect, wing_id in self.hex_air_wing_row_rects:
            if self.point_in_rect(x, y, rect):
                wing = self.air_wing_by_id(wing_id)
                if wing:
                    self.select_air_wing(wing)
                return True

        for rect, unit_id in self.hex_air_defense_row_rects:
            if self.point_in_rect(x, y, rect):
                unit = self.air_defense_unit_by_id(unit_id)
                if unit:
                    self.select_air_defense_unit(unit)
                return True

        if self.hex_airbase_upgrade_button_rect and self.point_in_rect(x, y, self.hex_airbase_upgrade_button_rect):
            self.set_hex_panel_message("Развитие аэродрома: заглушка")
            return True
        return False

    def handle_air_map_command_click(self, target_tile, modifiers=0, force_mode=None):
        target_mode_ids = set(self.air_wing_target_mode_ids or set())
        if self.air_wing_target_mode_id:
            target_mode_ids.add(self.air_wing_target_mode_id)
        if target_mode_ids:
            wings = [self.air_wing_by_id(wing_id) for wing_id in list(target_mode_ids)]
            wings = [wing for wing in wings if wing]
            mode = force_mode or ("add" if self.shift_modifier_active(modifiers) else "replace")
            changed = self.set_air_wing_operation_area_for_wings(wings, target_tile, mode=mode)
            if changed:
                if mode == "replace":
                    self.clear_air_wing_map_modes()
                if target_tile:
                    self.set_single_selected_tile(target_tile)
            return True

        rebase_mode_ids = set(self.air_wing_rebase_mode_ids or set())
        if self.air_wing_rebase_mode_id:
            rebase_mode_ids.add(self.air_wing_rebase_mode_id)
        if rebase_mode_ids:
            changed = False
            for wing_id in list(rebase_mode_ids):
                wing = self.air_wing_by_id(wing_id)
                ok, _message = self.rebase_air_wing(wing, target_tile)
                changed = changed or ok
            if changed:
                self.clear_air_wing_map_modes()
                if target_tile:
                    self.set_single_selected_tile(target_tile)
            return True
        if self.air_defense_move_mode_id:
            unit = self.air_defense_unit_by_id(self.air_defense_move_mode_id)
            ok, message = self.move_air_defense_unit(unit, target_tile)
            if ok:
                self.air_defense_move_mode_id = None
                if target_tile:
                    self.set_single_selected_tile(target_tile)
            return True
        return False

    def rebuild_selection_borders(self):
        self.selection_border_sprite_list.clear()
        if not self.selection_border:
            return

        tiles = self.selected_hex_tiles()
        if not tiles:
            self.selection_border.visible = False
            return

        border_texture = self.selection_border.texture
        for index, tile in enumerate(tiles):
            sprite = self.selection_border if index == 0 else arcade.Sprite(border_texture)
            sprite.position = (tile.center_x, tile.center_y)
            sprite.visible = True
            self.selection_border_sprite_list.append(sprite)

    def set_single_selected_tile(self, tile):
        previous_tile = self.selected_tile
        self.selected_tiles = []
        self.selected_tile = tile
        if tile:
            if self.selected_air_defense_unit_id:
                selected_unit = self.air_defense_unit_by_id(self.selected_air_defense_unit_id)
                if not selected_unit or selected_unit.tile is not tile:
                    self.selected_air_defense_unit_id = None
            if tile != previous_tile:
                self.reset_hex_panel_view_state()
            self.rebuild_selection_borders()
            self.last_visible_update = 0
        else:
            self.close_hex_panel()

    def toggle_tile_multi_selection(self, tile):
        if not tile:
            return

        if not self.selected_tiles:
            self.selected_tiles = [self.selected_tile] if self.selected_tile else []

        key = self.tile_key(tile)
        for index, selected in enumerate(self.selected_tiles):
            if self.tile_key(selected) == key:
                self.selected_tiles.pop(index)
                break
        else:
            self.selected_tiles.append(tile)

        if self.selected_tiles:
            previous_tile = self.selected_tile
            self.selected_tile = self.selected_tiles[-1]
            if self.selected_tile != previous_tile:
                self.reset_hex_panel_view_state()
            self.rebuild_selection_borders()
            self.last_visible_update = 0
        else:
            self.close_hex_panel()

    def close_hex_panel(self):
        self.selected_tile = None
        self.selected_tiles = []
        self.selected_air_defense_unit_id = None
        self.air_defense_move_mode_id = None
        self.hovered_hex_panel_close = False
        self.hovered_hex_build_button = False
        self.hovered_hex_specialization_button = False
        self.hex_panel_scroll = 0.0
        self.hex_panel_content_height = 0.0
        self.hex_resources_expanded = False
        self.hex_resources_toggle_rect = None
        self.hex_panel_specialization_mode = False
        self.hex_specialization_row_rects = []
        self.hex_air_wing_row_rects = []
        self.hex_air_wing_button_rects = []
        self.hex_air_defense_row_rects = []
        self.hex_air_defense_button_rects = []
        self.hex_airbase_upgrade_button_rect = None
        self.hex_panel_message = ""
        self.rebuild_selection_borders()

    def toggle_hex_specialization_mode(self):
        if not self.can_edit_selected_industry():
            self.hex_panel_specialization_mode = False
            return
        self.hex_panel_specialization_mode = not self.hex_panel_specialization_mode
        self.hex_panel_message = ""

    def can_edit_selected_industry(self):
        tiles = self.selected_hex_tiles()
        return bool(self.human_player and tiles and self.selected_industry_tiles()
                    and all(tile.owner is self.human_player for tile in tiles))

    def set_selected_tile_industry_sector(self, sector):
        if sector not in INDUSTRY_SECTOR_LABELS or not self.can_edit_selected_industry():
            self.hex_panel_specialization_mode = False
            return False
        industry_tiles = self.selected_industry_tiles()
        if not industry_tiles:
            return

        allocations = []
        fallback_counts = {}
        for tile in industry_tiles:
            allocation = {
                key: value
                for key, value in self.normalize_industry_allocation(
                    getattr(tile, "industry_allocation", {}) or {}
                ).items()
                if value > 0
            }
            if not allocation:
                allocation = {sector: 1.0}
            for key in allocation:
                if key != sector:
                    fallback_counts[key] = fallback_counts.get(key, 0) + 1
            allocations.append(allocation)

        remove_sector = any(sector in allocation for allocation in allocations)
        fallback_sector = next(
            (
                key
                for key, _count in sorted(fallback_counts.items(), key=lambda item: item[1], reverse=True)
                if key != sector
            ),
            None,
        )
        if fallback_sector is None:
            fallback_sector = "consumer_goods" if sector != "consumer_goods" else "machinery"

        affected_players = {}
        for tile, allocation in zip(industry_tiles, allocations):
            if remove_sector:
                allocation.pop(sector, None)
                if not allocation:
                    allocation[fallback_sector] = 1.0
            else:
                allocation[sector] = allocation.get(sector, 0.0) or 1.0

            tile.industry_allocation = self.normalize_industry_allocation({
                key: 1.0
                for key in allocation
            })
            self.update_tile_production_cache(tile)
            if tile.owner:
                affected_players[id(tile.owner)] = tile.owner

        for player in affected_players.values():
            self.recalculate_monthly_balance(player)

        self.hex_panel_message = ""
        self.hex_panel_message_timer = 0.0

    def toggle_hex_resources_expanded(self):
        self.hex_resources_expanded = not self.hex_resources_expanded
        self.clamp_hex_panel_scroll()

    def hex_panel_snapshot_key(self, tiles, tile):
        tile_keys = tuple((selected.q, selected.r) for selected in tiles if selected)
        owners = {}
        for selected in tiles:
            owner = getattr(selected, "owner", None)
            if owner:
                owners[id(owner)] = owner
        owner_markers = tuple(
            sorted(
                (
                    id(owner),
                    len(getattr(owner, "tiles", []) or []),
                    bool(getattr(owner, "storage_dirty", False)),
                    bool(getattr(owner, "tile_stockpiles_dirty", False)),
                    round(getattr(owner, "resource_balance_last_update", 0.0), 3),
                    getattr(owner, "trade_contract_revision", 0),
                )
                for owner in owners.values()
            )
        )
        return (
            tile_keys,
            (tile.q, tile.r) if tile else None,
            self.tile_visual_revision,
            self.air_asset_revision,
            self.air_salvo_revision,
            len(self.field_helipad_projects),
            owner_markers,
        )

    def hex_panel_snapshot(self, tiles, tile):
        tiles = [selected for selected in tiles if selected]
        cache_key = self.hex_panel_snapshot_key(tiles, tile)
        if self.hex_panel_snapshot_cache and self.hex_panel_snapshot_cache.get("key") == cache_key:
            return self.hex_panel_snapshot_cache["snapshot"]

        multi_selected = len(tiles) > 1
        owner_name = self.mixed_or_single(
            [selected.owner.name if selected.owner else "Нейтральная территория" for selected in tiles],
            mixed_label="Разные владельцы",
        )
        terrain_name = self.mixed_or_single(
            [self.terrain_display_name(selected.terrain_type) for selected in tiles],
            mixed_label="Разная",
        )
        airbases = []
        for selected in tiles:
            airbase = self.airbase_on_tile(selected)
            if airbase:
                airbases.append(airbase)

        snapshot = {
            "multi_selected": multi_selected,
            "owner_name": owner_name,
            "population": sum(self.estimated_tile_population(selected) or 0.0 for selected in tiles),
            "terrain_name": terrain_name,
            "passability": self.average_tile_value(tiles, "passability", 0.0),
            "supply_score": self.average_tile_value(tiles, "supply_score", 0.0),
            "resource_rows": self.hex_resource_rows_for_tiles(tiles),
            "storage": self.storage_summary_for_tiles(tiles),
            "coverage_buildings": self.building_coverage_rows_for_tiles(tiles),
            "damage_by_building": self.building_damage_rows_for_tiles(tiles),
            "airbases": airbases,
            "tile_air_defense_units": self.air_defense_units_for_tiles(tiles),
            "wing_counts": self.air_wing_counts_by_type_for_tiles(tiles),
            "air_defense_counts": self.air_defense_counts_by_class_for_tiles(tiles),
            "air_salvo_counts": self.air_salvo_counts_for_tiles(tiles),
            "helipad_projects": [
                project for selected in tiles
                for project in self.field_helipad_projects_on_tile(selected)
            ],
            "helipad_coverage": sum(
                (getattr(selected, "building_coverage", {}) or {}).get("field_helipad", 0.0)
                for selected in tiles
            ),
        }
        self.hex_panel_snapshot_cache = {"key": cache_key, "snapshot": snapshot}
        return snapshot

    def draw_hex_info_panel(self):
        self.hex_country_rect = None
        tiles = self.selected_hex_tiles()
        if not tiles:
            return
        tile = self.selected_tile if self.selected_tile in tiles else tiles[-1]
        multi_selected = len(tiles) > 1

        with self.profiler.measure("hex_panel_snapshot"):
            hex_snapshot = self.hex_panel_snapshot(tiles, tile)

        panel_x, panel_y, panel_width, panel_height = self.hex_panel_rect()
        content_bottom, content_top = self.hex_panel_content_bounds()
        content_width = panel_width - 32
        visible_content_height = max(1, content_top - content_bottom)
        self.hex_specialization_row_rects = []
        self.hex_resources_toggle_rect = None
        self.hex_air_wing_row_rects = []
        self.hex_air_wing_button_rects = []
        self.hex_air_defense_row_rects = []
        self.hex_air_defense_button_rects = []
        self.hex_airbase_upgrade_button_rect = None

        def visible_y(draw_y, top_margin=24):
            return content_bottom <= draw_y <= content_top + top_margin

        def panel_text(text, x, draw_y, color=arcade.color.WHITE, font_size=12, **kwargs):
            if visible_y(draw_y):
                self.draw_ui_text(text, x, draw_y, color, font_size, **kwargs)

        def panel_section(title, draw_y):
            panel_text(title, panel_x + 16, draw_y, arcade.color.WHITE, 14)
            return draw_y - 20

        def panel_button(rect, label, fill=(44, 58, 74), border=(92, 118, 148), color=(226, 236, 246)):
            rect_x, rect_y, rect_width, rect_height = rect
            if rect_y + rect_height < content_bottom or rect_y > content_top:
                return False
            arcade.draw_lbwh_rectangle_filled(rect_x, rect_y, rect_width, rect_height, fill)
            arcade.draw_lbwh_rectangle_outline(rect_x, rect_y, rect_width, rect_height, border, 1)
            self.draw_ui_text(
                label,
                rect_x + rect_width / 2,
                rect_y + rect_height / 2,
                color,
                10,
                anchor_x="center",
                anchor_y="center",
            )
            return True

        arcade.draw_lbwh_rectangle_filled(panel_x, panel_y, panel_width, panel_height, (18, 24, 31, 244))
        arcade.draw_lbwh_rectangle_outline(panel_x, panel_y, panel_width, panel_height, (110, 130, 154), 2)

        close_x, close_y, close_width, close_height = self.hex_panel_close_rect()
        close_fill = (96, 56, 58) if self.hovered_hex_panel_close else (50, 58, 68)
        arcade.draw_lbwh_rectangle_filled(close_x, close_y, close_width, close_height, close_fill)
        arcade.draw_lbwh_rectangle_outline(close_x, close_y, close_width, close_height, (150, 166, 184), 1)
        self.draw_ui_text("X", close_x + close_width / 2, close_y + close_height / 2, arcade.color.WHITE, 13,
                          anchor_x="center", anchor_y="center")

        y = panel_y + panel_height - 28 + self.hex_panel_scroll
        title = f"Гексов {len(tiles)}" if multi_selected else f"Гекс {tile.q}:{tile.r}"
        panel_text(title, panel_x + 16, y, arcade.color.WHITE, 18, anchor_y="center")
        y -= 34

        owner_name = hex_snapshot["owner_name"]
        population = hex_snapshot["population"]
        terrain_name = hex_snapshot["terrain_name"]
        passability = hex_snapshot["passability"]
        supply_score = hex_snapshot["supply_score"]
        info_rows = [
            ("Владелец", owner_name),
            ("Население", self.format_population(population)),
            ("Местность", terrain_name),
            ("Проходимость", self.format_percent(passability)),
            ("Снабжение", self.format_percent(supply_score)),
        ]
        for label, value in info_rows:
            if label == "Владелец" and tile.owner and not multi_selected and visible_y(y, top_margin=0):
                self.hex_country_rect = (panel_x + 12, y - 5, panel_width - 24, 18)
                arcade.draw_lbwh_rectangle_outline(*self.hex_country_rect, (118, 146, 176), 1)
            panel_text(label, panel_x + 16, y, (150, 166, 184), 11)
            panel_text(value, panel_x + 122, y, (224, 234, 244), 12)
            y -= 18

        y -= 8
        y = panel_section("Ресурсы", y)
        panel_text("Название", panel_x + 16, y, (150, 166, 184), 10)
        panel_text("В земле", panel_x + 174, y, (150, 166, 184), 10)
        panel_text("Склад", panel_x + 270, y, (150, 166, 184), 10)
        y -= 16

        resource_rows = hex_snapshot["resource_rows"]
        if resource_rows:
            max_collapsed_resources = 5
            displayed_resource_rows = resource_rows if self.hex_resources_expanded else resource_rows[:max_collapsed_resources]
            list_top_y = y + 12
            for row in displayed_resource_rows:
                row_name = row["name"]
                if len(row_name) > 21:
                    row_name = row_name[:20] + "..."
                panel_text(row_name, panel_x + 16, y, (224, 234, 244), 11)
                ground = self.format_resource_amount(row["ground"]) if row["ground"] > 0 else "-"
                stock = self.format_resource_amount(row["stock"]) if row["stock"] > 0 else "-"
                panel_text(ground, panel_x + 174, y, (206, 218, 230), 11)
                panel_text(stock, panel_x + 270, y, (206, 218, 230), 11)
                y -= 16
            if len(resource_rows) > max_collapsed_resources:
                toggle_text = "Скрыть" if self.hex_resources_expanded else f"Еще {len(resource_rows) - max_collapsed_resources}"
                panel_text(toggle_text, panel_x + 16, y, (180, 192, 205), 10)
                y -= 16
                rect_top = min(content_top, list_top_y + 8)
                rect_bottom = max(content_bottom, y + 4)
                if rect_top > rect_bottom:
                    self.hex_resources_toggle_rect = (panel_x + 12, rect_bottom, panel_width - 24, rect_top - rect_bottom)
        else:
            panel_text("Нет доступных залежей и запасов", panel_x + 16, y, (180, 192, 205), 11)
            y -= 18

        y -= 8
        y = panel_section("Емкость", y)
        tile_capacity, tile_used = hex_snapshot["storage"]
        for category_key in STORAGE_CATEGORIES:
            capacity = tile_capacity.get(category_key, 0.0)
            used = tile_used.get(category_key, 0.0)
            if capacity <= 0 and used <= 0:
                continue
            panel_text(
                f"{STORAGE_CATEGORY_LABELS[category_key]}: "
                f"{self.format_resource_amount(used)}/{self.format_resource_amount(capacity)}",
                panel_x + 16,
                y,
                (206, 218, 230),
                11,
            )
            y -= 16

        y -= 8
        y = panel_section("Строения", y)
        coverage, buildings = hex_snapshot["coverage_buildings"]
        damage_by_building = hex_snapshot["damage_by_building"]
        if coverage:
            for key, value in sorted(coverage.items(), key=lambda item: item[0]):
                label = BUILDING_DISPLAY_NAMES.get(key, key)
                value_text = self.format_tile_coverage_total(value) if multi_selected else f"{value:.0%}"
                damage = damage_by_building.get(key, 0.0)
                if damage > 0.001:
                    value_text += f" | повр. {damage:.0%}"
                panel_text(f"{label}: {value_text}", panel_x + 16, y, (224, 234, 244), 11)
                y -= 16
        elif buildings:
            for key in sorted(buildings):
                panel_text(BUILDING_DISPLAY_NAMES.get(key, key), panel_x + 16, y, (224, 234, 244), 11)
                y -= 16
        else:
            panel_text("Пока нет", panel_x + 16, y, (180, 192, 205), 11)
            y -= 16

        airbases = hex_snapshot["airbases"]
        tile_air_defense_units = hex_snapshot["tile_air_defense_units"]
        wing_counts = hex_snapshot["wing_counts"]
        air_defense_counts = hex_snapshot["air_defense_counts"]
        air_salvo_counts = hex_snapshot["air_salvo_counts"]
        helipad_projects = hex_snapshot["helipad_projects"]
        has_aviation_info = bool(
            airbases
            or wing_counts
            or air_defense_counts
            or air_salvo_counts
            or helipad_projects
        )
        if has_aviation_info:
            y -= 8
            y = panel_section("Авиация/ПВО", y)
            if airbases:
                if multi_selected:
                    panel_text(f"Аэродромы: {len(airbases)}", panel_x + 16, y, (224, 234, 244), 11)
                else:
                    airbase = airbases[0]
                    health = self.building_health(airbase.tile, "airbase")
                    load = self.airbase_load_summary(airbase.tile)
                    panel_text(
                        f"Аэродром: ВПП {airbase.runway_level}, сост. {health:.0%}",
                        panel_x + 16,
                        y,
                        (224, 234, 244),
                        11,
                    )
                    y -= 16
                    if load:
                        panel_text(
                            f"Места: сам. {load['fixed_load']}/{load['fixed_capacity']} | верт. {load['helicopter_load']}/{load['helicopter_capacity']}",
                            panel_x + 16,
                            y,
                            (206, 218, 230),
                            11,
                        )
                        y -= 16
                    if airbase.owner is self.human_player:
                        upgrade_rect = (panel_x + 16, y - 5, min(180, content_width), 20)
                        if panel_button(upgrade_rect, "Развитие аэродрома", fill=(52, 62, 78), border=(112, 134, 160)):
                            self.hex_airbase_upgrade_button_rect = upgrade_rect
                        y -= 16
            helipad_coverage = hex_snapshot["helipad_coverage"]
            if helipad_coverage > 0:
                helipad_load = self.airbase_load_summary(tile) if not multi_selected else None
                label = f"Полевые площадки: {helipad_coverage:.0%}"
                if helipad_load and helipad_load["helicopter_capacity"] > 0 and not airbases:
                    label += f" | верт. {helipad_load['helicopter_load']}/{helipad_load['helicopter_capacity']}"
                panel_text(label, panel_x + 16, y, (206, 224, 210), 11)
                y -= 16
            for project in helipad_projects:
                progress = project.progress_hours / max(1.0, project.work_required_hours)
                panel_text(f"Площадка строится: {progress:.0%}", panel_x + 16, y, (190, 230, 174), 11)
                y -= 16
            for aircraft_type, count in sorted(wing_counts.items()):
                aircraft_name = AIRCRAFT_TYPES.get(aircraft_type, {}).get("name", aircraft_type)
                panel_text(f"{aircraft_name}: {count} на базе", panel_x + 16, y, (206, 218, 230), 11)
                y -= 16
            for munition_type, count in sorted(air_salvo_counts.items()):
                munition_name = MUNITIONS.get(munition_type, {}).get("name", munition_type)
                panel_text(f"Залп: {munition_name} x{count}", panel_x + 16, y, (238, 218, 176), 11)
                y -= 16
            if tile_air_defense_units:
                panel_text("ПВО", panel_x + 16, y, (150, 166, 184), 10)
                y -= 22
            for unit in tile_air_defense_units:
                unit_name = AIR_DEFENSE_CLASSES.get(unit.unit_class, {}).get("name", unit.unit_class)
                selected = unit.id == self.selected_air_defense_unit_id
                row_y = y - 6
                row_height = 22
                if content_bottom <= row_y + row_height and row_y <= content_top:
                    fill = (70, 66, 48, 178) if selected else (36, 38, 34, 120)
                    arcade.draw_lbwh_rectangle_filled(panel_x + 12, row_y, content_width + 8, row_height, fill)
                    arcade.draw_lbwh_rectangle_outline(panel_x + 12, row_y, content_width + 8, row_height, (118, 104, 72), 1)
                    self.hex_air_defense_row_rects.append(((panel_x + 12, row_y, content_width + 8, row_height), unit.id))
                radar_state = "РЛС+" if unit.radar_active else "РЛС-"
                panel_text(
                    f"{unit_name}: огонь {unit.fire_range_cells}, {radar_state}, БК {unit.ammo}",
                    panel_x + 18,
                    y,
                    (238, 228, 198) if selected else (224, 214, 184),
                    11,
                )
                y -= 25
                if selected and unit.owner is self.human_player:
                    buttons = []
                    if unit.radar_range_cells > 0:
                        buttons.append(("radar", "Радар", 58))
                    button_x = panel_x + 18
                    for action, label, width in buttons:
                        rect = (button_x, y - 4, width, 20)
                        if panel_button(rect, label):
                            self.hex_air_defense_button_rects.append((rect, action, unit.id))
                        button_x += width + 6
                    if buttons:
                        y -= 24

        if self.selected_tile_has_industry():
            y -= 8
            y = panel_section("Производство", y)
            industry_tiles = self.selected_industry_tiles()
            allocation = self.selected_industry_allocation_summary(industry_tiles)
            efficiency = self.selected_industry_efficiency(industry_tiles)
            panel_text(f"Эффективность: {efficiency:.0%}", panel_x + 16, y, (224, 234, 244), 11)
            y -= 18
            for sector, share in sorted(allocation.items(), key=lambda item: item[1], reverse=True):
                label = INDUSTRY_SECTOR_LABELS.get(sector, sector)
                panel_text(f"{label}: {share:.0%}", panel_x + 16, y, (206, 218, 230), 11)
                y -= 16

            if self.hex_panel_specialization_mode and self.can_edit_selected_industry():
                y -= 6
                panel_text("Выбор категории", panel_x + 16, y, (150, 166, 184), 10)
                y -= 18
                for sector, label in INDUSTRY_SECTOR_LABELS.items():
                    row_x = panel_x + 16
                    row_y = y - 6
                    row_height = 24
                    active = allocation.get(sector, 0.0) > 0
                    if content_bottom <= row_y + row_height and row_y <= content_top:
                        fill = (54, 76, 96, 190) if active else (32, 42, 54, 160)
                        arcade.draw_lbwh_rectangle_filled(row_x, row_y, content_width, row_height, fill)
                        arcade.draw_lbwh_rectangle_outline(row_x, row_y, content_width, row_height, (84, 108, 132), 1)
                        panel_text(label, row_x + 8, y + 6, (226, 234, 242), 11, anchor_y="center")
                        self.hex_specialization_row_rects.append(((row_x, row_y, content_width, row_height), sector))
                    y -= row_height + 5

        y -= 8
        y = panel_section("Климат", y)
        climate_rows = [
            ("Тип", self.climate_display_name(tile) if not multi_selected else "Среднее по выбору"),
            ("Температура", self.format_temperature(self.average_tile_value(tiles, "temperature", 0.0))),
            ("Влажность", self.format_percent(self.average_tile_value(tiles, "moisture", 0.0))),
            ("Высота", self.format_elevation(self.average_tile_value(tiles, "elevation", 0.0))),
        ]
        for label, value in climate_rows:
            panel_text(label, panel_x + 16, y, (150, 166, 184), 11)
            panel_text(value, panel_x + 122, y, (224, 234, 244), 11)
            y -= 16

        self.hex_panel_content_height = max(0.0, content_top + self.hex_panel_scroll - y + 12)
        self.clamp_hex_panel_scroll()

        if self.hex_panel_content_height > visible_content_height + 2:
            track_x = panel_x + panel_width - 10
            track_y = content_bottom
            track_height = visible_content_height
            max_scroll = max(1.0, self.hex_panel_content_height - visible_content_height)
            thumb_height = max(28, track_height * visible_content_height / self.hex_panel_content_height)
            thumb_y = track_y + (track_height - thumb_height) * (1 - self.hex_panel_scroll / max_scroll)
            arcade.draw_lbwh_rectangle_filled(track_x, track_y, 4, track_height, (48, 62, 78, 180))
            arcade.draw_lbwh_rectangle_filled(track_x, thumb_y, 4, thumb_height, (132, 156, 184, 220))

        if self.can_edit_selected_industry():
            spec_x, spec_y, spec_width, spec_height = self.hex_panel_specialization_button_rect()
            spec_fill = (64, 92, 118) if self.hovered_hex_specialization_button else (38, 50, 66)
            spec_border = (165, 195, 230) if self.hovered_hex_specialization_button else (95, 118, 145)
            arcade.draw_lbwh_rectangle_filled(spec_x, spec_y, spec_width, spec_height, spec_fill)
            arcade.draw_lbwh_rectangle_outline(spec_x, spec_y, spec_width, spec_height, spec_border, 2)
            spec_label = "Закрыть специализацию" if self.hex_panel_specialization_mode else "Изменить специализацию"
            self.draw_ui_text(spec_label, spec_x + spec_width / 2, spec_y + spec_height / 2,
                              arcade.color.WHITE, 12, anchor_x="center", anchor_y="center")

        button_x, button_y, button_width, button_height = self.hex_panel_build_button_rect()
        button_fill = (64, 92, 118) if self.hovered_hex_build_button else (42, 55, 72)
        button_border = (165, 195, 230) if self.hovered_hex_build_button else (100, 126, 155)
        arcade.draw_lbwh_rectangle_filled(button_x, button_y, button_width, button_height, button_fill)
        arcade.draw_lbwh_rectangle_outline(button_x, button_y, button_width, button_height, button_border, 2)
        self.draw_ui_text("Постройка", button_x + button_width / 2, button_y + button_height / 2,
                          arcade.color.WHITE, 14, anchor_x="center", anchor_y="center")

        if self.hex_panel_message:
            message_y = button_y + button_height + 12
            if self.selected_tile_has_industry():
                _spec_x, spec_y, _spec_width, spec_height = self.hex_panel_specialization_button_rect()
                message_y = spec_y + spec_height + 10
            self.draw_ui_text(self.hex_panel_message, panel_x + 16, message_y, (235, 205, 120), 11)

