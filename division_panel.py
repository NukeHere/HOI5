"""Army overview, composition editor and paid recruitment UI."""

import arcade


class DivisionPanelMixin:
    def initialize_division_panel(self):
        if hasattr(self, "division_panel_tab"):
            return
        self.division_panel_tab = "overview"
        self.division_draft = {"basic_infantry": 10}
        self.division_design_name = "Новая дивизия"
        self.division_name_focused = False
        self.division_panel_key = "basic_infantry"
        self.division_panel_hits = []
        self.division_equipment_scroll = 0
        self.division_deployment_key = None
        self.division_site_pick_mode = False
        self.division_site_project_id = None

    def draw_army_panel_content(self, x, y, width, height):
        self.initialize_division_panel()
        self.division_panel_hits = []
        top = y + height - 62
        def button(label, bx, by, bw, action, value=None):
            rect = (bx, by - 22, bw, 22)
            arcade.draw_lbwh_rectangle_filled(*rect, (42, 57, 72))
            self.draw_ui_text(label, bx + 6, by - 11, (225, 234, 244), 10, anchor_y="center")
            self.division_panel_hits.append((rect, action, value))
        for i, (tab, label) in enumerate((("overview", "Сводка"), ("designer", "Конструктор"), ("recruit", "Набор"))):
            button(label, x + 18 + i * (width - 36) / 3, top, (width - 42) / 3, "tab", tab)
        if self.division_panel_tab == "overview":
            self.draw_army_overview_content(x, y, width, height - 32)
            return
        player = self.human_player
        if player is None:
            return
        service = self.recruitment
        left, right = x + 18, x + width - 18
        cursor = top - 46
        def line(text, color=(210, 224, 236), size=10):
            nonlocal cursor
            self.draw_ui_text(text, left, cursor, color, size)
            cursor -= 20
        if self.division_panel_tab == "designer":
            button(self.division_design_name + (" |" if self.division_name_focused else " (изменить)"),
                   left, cursor + 10, width - 36, "name")
            cursor -= 28
            line("Батальоны: от 1 до 20; 10 одного типа = готовый тип")
            for key, template in service.archetypes.items():
                self.draw_ui_text(template["name"].replace(" дивизия", "")[:25], left, cursor, (225, 233, 242), 10)
                button("−", right - 100, cursor + 13, 26, "count", (key, -1))
                self.draw_ui_text(str(self.division_draft.get(key, 0)), right - 62, cursor, (255, 225, 140), 11)
                button("+", right - 28, cursor + 13, 26, "count", (key, 1))
                cursor -= 28
            try:
                template = service.compose(self.division_draft, self.division_design_name)
            except ValueError as error:
                line(str(error), (245, 155, 130))
                return
            line(f"Люди: {template['manpower']}  Ширина: {template['front_width']:.1f}  Скорость: {template['speed']:.2f}")
            line(f"Пехотная атака: {template['soft_attack']:.1f}  Защита: {template['defense']:.1f}")
            line(f"Прорыв: {template['breakthrough']:.1f}  Броня: {template['front_armor']:.1f}")
            line(f"Атака брони: {template['hard_front_attack']:.1f}  Пробитие: {template['front_piercing']:.1f}")
            line(f"Организация: {template['organization']:.0f}  Восстановление: {template['organization_recovery']:.1f}")
            cost = service.quote(template)
            line(f"Подготовка: {cost['days']} суток; {self.format_money(cost['money'])}")
            button("Сохранить шаблон и перейти к набору", left, cursor + 10, width - 36, "save")
            cursor -= 42
            line(service.message[:65], (240, 203, 130))
            return
        keys = list(service.archetypes) + service.designs[player.id]
        if self.division_panel_key not in keys:
            self.division_panel_key = keys[0]
        template = self.division_template(self.division_panel_key)
        line(template["name"][:44], size=13)
        button("< Шаблон", left, cursor + 10, 110, "cycle", -1)
        button("Шаблон >", left + 120, cursor + 10, 110, "cycle", 1)
        button("Изменить", right - 94, cursor + 10, 94, "edit")
        cursor -= 34
        cost = service.quote(template)
        line(f"{cost['manpower']} человек; резерв {player.manpower_reserve:,.0f}".replace(",", " "))
        line(f"Цена: {self.format_money(cost['money'])}; срок: {cost['days']} суток")
        tile = self.tile_for_key(self.division_deployment_key)
        line(f"Развёртывание: ({tile.q}, {tile.r})" if tile else "Гекс развёртывания не выбран")
        button("ЛКМ по гексу; ESC / ПКМ — отмена" if self.division_site_pick_mode else "Выбрать гекс на карте (ЛКМ)",
               left, cursor + 10, width - 36, "site")
        cursor -= 30
        button("Начать подготовку", left, cursor + 10, width - 36, "recruit")
        cursor -= 32
        line(service.message[:65], (240, 203, 130))
        line("Очередь (последовательно, максимум 4):")
        for project in service.queues[player.id]:
            progress = project["hours"] / (project["cost"]["days"] * 24)
            label = f"{project['template']['name'][:22]}: {progress:.0%}"
            if project["status"] == "waiting_site":
                label += " — нет места"
            self.draw_ui_text(label, left, cursor, (218, 228, 240), 10)
            button("Гекс", right - 120, cursor + 13, 48, "project_site", project["id"])
            button("Отмена", right - 66, cursor + 13, 66, "cancel", project["id"])
            cursor -= 18
            self.draw_ui_text(f"Место: {tuple(project['tile_key'])}", left, cursor, (170, 190, 210), 9)
            cursor -= 24
        line("Оснащение: нужно / склад (прокрутка колесом)")
        equipment = list(cost["equipment"].items())
        visible = max(1, int((cursor - y - 18) // 20) + 1)
        self.division_equipment_scroll = min(self.division_equipment_scroll, max(0, len(equipment) - visible))
        for key, amount in equipment[self.division_equipment_scroll:]:
            if cursor < y + 18:
                break
            stock = self.stockpile_amount(player, key)
            line(f"{self.resource_display_name(key)[:25]}: {amount:.0f} / {stock:.0f}",
                 (160, 223, 170) if stock + 1e-6 >= amount else (241, 151, 125))

    def handle_division_panel_click(self, x, y):
        self.initialize_division_panel()
        for rect, action, value in self.division_panel_hits:
            if not self.point_in_rect(x, y, rect):
                continue
            self.division_name_focused = action == "name"
            if action == "tab":
                self.division_panel_tab = value
                self.division_site_pick_mode = False
            elif action == "count":
                key, delta = value
                count = self.division_draft.get(key, 0)
                if delta < 0 or sum(self.division_draft.values()) < 20:
                    self.division_draft[key] = max(0, count + delta)
            elif action == "cycle":
                keys = list(self.recruitment.archetypes) + self.recruitment.designs[self.human_player.id]
                self.division_panel_key = keys[(keys.index(self.division_panel_key) + value) % len(keys)]
                self.division_equipment_scroll = 0
            elif action == "edit":
                template = self.division_template(self.division_panel_key)
                self.division_draft = dict(template.get("composition", {self.division_panel_key: 10}))
                self.division_design_name = template["name"]
                self.division_panel_tab = "designer"
            elif action == "save":
                self.submit_player_command("division_recruitment", dict(operation="save",
                    name=self.division_design_name, composition=dict(self.division_draft)))
                if self.recruitment.message.startswith("design-"):
                    self.division_panel_key = self.recruitment.message
                    self.division_panel_tab = "recruit"
                    self.recruitment.message = "Шаблон сохранён"
            elif action == "recruit":
                tile = self.tile_for_key(self.division_deployment_key)
                if tile is None:
                    self.recruitment.message = "Сначала выберите гекс развёртывания на карте"
                    return True
                self.submit_player_command("division_recruitment", dict(operation="recruit",
                    key=self.division_panel_key, tile_key=self.tile_key(tile) if tile else None))
            elif action in ("site", "project_site"):
                self.division_site_pick_mode = True
                self.division_site_project_id = value if action == "project_site" else None
                self.cancel_army_plan_mode()
                self.clear_air_wing_map_modes()
                self.division_selection_drag_active = False
                self.pending_map_click = None
                self.is_dragging = False
                self.close_hex_panel()
                self.recruitment.message = "Укажите свою снабжаемую клетку: ЛКМ; отмена — ESC / ПКМ"
            elif action == "cancel":
                self.submit_player_command("division_recruitment", dict(operation="cancel", id=value))
            return True
        self.division_name_focused = False
        return False

    def select_division_deployment_tile(self, tile):
        """Consume a map click without selecting units or issuing movement."""
        if not getattr(self, "division_site_pick_mode", False):
            return False
        if not self.recruitment.safe_site(self.human_player, tile):
            self.recruitment.message = "Нужен свой сухопутный гекс со снабжением от 25%, вне боя"
            return True
        if self.division_site_project_id is not None:
            self.submit_player_command("division_recruitment", dict(operation="relocate",
                id=self.division_site_project_id, tile_key=self.tile_key(tile)))
        else:
            self.division_deployment_key = self.tile_key(tile)
            self.recruitment.message = f"Место развёртывания: ({tile.q}, {tile.r})"
        self.division_site_pick_mode = False
        self.division_site_project_id = None
        self.set_single_selected_tile(tile)
        return True

    def on_text(self, text):
        if (getattr(self, "division_name_focused", False) and self.active_top_panel_key == "military"
                and self.division_panel_tab == "designer" and not self.paused):
            self.division_design_name = (self.division_design_name + "".join(c for c in text if c.isprintable()))[:48]
            return
        super().on_text(text)

    def handle_division_name_key(self, key, modifiers):
        if not (getattr(self, "division_name_focused", False) and self.active_top_panel_key == "military"
                and self.division_panel_tab == "designer" and not self.paused):
            return False
        if key in (arcade.key.ESCAPE, arcade.key.ENTER):
            self.division_name_focused = False
        elif key == arcade.key.BACKSPACE:
            self.division_design_name = self.division_design_name[:-1]
        elif key == arcade.key.DELETE or (key == arcade.key.A and modifiers & arcade.key.MOD_CTRL):
            self.division_design_name = ""
        return key != arcade.key.F3
