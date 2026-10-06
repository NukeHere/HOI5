"""Country card and simulation-command adapter."""

import textwrap
import time
from collections import OrderedDict
import arcade
from pyglet.graphics import Batch

from politics_system import ACTIONS, GROUPS, SOCIAL_GROUPS, FACTIONS, SUPPORT_GROUPS, TREATIES, OFFERS, PoliticsSystem
from country_power import power_ranking, relative_power
from country_dialog import CountryDialogMixin


class CountryPanelMixin(CountryDialogMixin):
    def initialize_politics(self):
        self.politics = PoliticsSystem(self.players, start_time=self.simulation_server.current_time)
        self.country_card_id = None
        self.country_list_open = False
        self.country_card_tab = "summary"
        self.country_card_scroll = 0
        self.country_card_action = None
        self.country_card_message = ""
        self.country_amount_text = "5000000"
        self.country_amount_focus = False
        self.country_card_hits = []
        self.country_summary_rect = None
        self.hex_country_rect = None
        self.last_market_fills = []
        self.last_market_unfilled = []
        self.country_text_batch = Batch()
        self.country_text_pool = []
        self.country_text_cursor = 0
        self.country_lines_cache = None
        self.country_text_views = OrderedDict()
        self.initialize_country_dialog()

    def countries_hostile(self, a, b):
        return bool(a is not None and b is not None and self.politics.hostile(a.id, b.id))

    def open_country_card(self, player):
        if player is None:
            return
        previous_tab = self.country_card_tab
        self.open_top_panel("politics" if player is self.human_player else "diplomacy")
        self.country_card_id = player.id
        self.country_list_open = False
        self.country_card_tab = previous_tab if previous_tab in ("summary", "society", "trade", "actions", "history") else "summary"
        self.country_card_scroll = 0
        self.country_card_action = None
        self.country_card_message = ""
        self.country_amount_focus = False
        self.country_card_hits = []
        self.is_dragging = False
        self.division_selection_drag_active = False

    def close_country_card(self):
        self.country_card_id = None
        self.country_list_open = False
        self.country_card_hits = []
        self.country_card_action = None
        self.close_top_panel()

    def handle_political_command(self, command):
        if not self.human_player or command.player_id != self.human_player.id:
            return False
        payload = command.payload
        if "offer" in payload:
            offer = tuple(payload["offer"])
            if offer not in self.politics.pending or offer[1] != command.player_id:
                return False
            self.politics.resolve_offer(offer, payload.get("accept") is True)
            self.country_card_message = "Ответ отправлен"
            success = True
        else:
            success, self.country_card_message = self.politics.execute(
                command.player_id, payload.get("target"), payload.get("action"), payload.get("amount"),
                payload.get("program_term", "ongoing"))
        if success:
            self.enforce_diplomatic_peace()
            self.recalculate_all_monthly_balances()
            self.trade_panel_cache = None
        return success

    def enforce_diplomatic_peace(self):
        for key, battle in list(self.battles.items()):
            if battle.defender and not self.countries_hostile(battle.attacker, battle.defender):
                for division in self.divisions:
                    if division.battle_id == key:
                        division.battle_id = None
                        division.battle_side = None
                        division.battle_status = None
                        division.path.clear()
                        division.post_battle_path.clear()
                        division.route_tiles.clear()
                        division.target_tile = None
                del self.battles[key]
                self.invalidate_division_render_cache()

    def advance_politics(self, hours):
        previous = self.politics.revision
        self.politics.advance(hours)
        if self.politics.revision != previous:
            self.enforce_diplomatic_peace()
            self.recalculate_all_monthly_balances()
            self.trade_panel_cache = None

    def country_panel_rect(self):
        return self.side_panel_rect()

    def country_panel_contains(self, x, y):
        return (self.active_top_panel_key in ("politics", "diplomacy")
                and self.side_panel_progress > 0
                and self.point_in_rect(x, y, self.country_panel_rect()))

    def handle_country_click(self, x, y, button):
        if self.handle_country_dialog_click(x, y, button):
            return True
        if self.country_panel_contains(x, y):
            if button == arcade.MOUSE_BUTTON_LEFT:
                for rect, kind, value in self.country_card_hits:
                    if not self.point_in_rect(x, y, rect):
                        continue
                    if kind == "close":
                        self.close_country_card()
                    elif kind == "country":
                        self.open_country_card(self.player_by_id(value))
                    elif kind == "countries":
                        self.open_top_panel("diplomacy")
                    elif kind == "tab":
                        if value in ("population", "power", "taxes", "programs"):
                            self.open_country_dialog(value)
                        elif value == "budget":
                            self.open_top_panel("economy")
                        else:
                            self.country_card_tab = value
                            self.country_card_scroll = 0
                            self.country_card_action = None
                    elif kind == "dialog":
                        self.open_country_dialog(value)
                    elif kind == "panel":
                        self.open_top_panel(value)
                    elif kind == "action":
                        self.open_country_dialog("action", value)
                    elif kind == "amount":
                        self.country_amount_focus = True
                    elif kind == "amount_step":
                        self.country_amount_text = str(max(1000, min(10**12, (self.country_amount() or 0) + value)))
                    elif kind == "cancel":
                        self.country_card_action = None
                    elif kind == "confirm":
                        self.submit_player_command("political_action", {"target": self.country_card_id, "action": value,
                                                                       "amount": self.country_amount()})
                        self.country_card_action = None
                        self.country_amount_focus = False
                    elif kind == "offer":
                        self.submit_player_command("political_action", {"offer": value[0], "accept": value[1]})
                    self.country_card_hits = []
                    return True
            return True
        self.country_amount_focus = False
        if button == arcade.MOUSE_BUTTON_LEFT:
            if self.country_summary_rect and self.point_in_rect(x, y, self.country_summary_rect):
                self.open_country_card(self.human_player)
                return True
            if self.selected_tile and self.hex_country_rect and self.point_in_rect(x, y, self.hex_country_rect):
                self.open_country_card(self.selected_tile.owner)
                return True
        return False

    def country_amount(self):
        return int(self.country_amount_text) if self.country_amount_text else None

    def on_text(self, text):
        if self.country_card_id is not None and self.country_card_action in ("aid", "loan") and self.country_amount_focus:
            digits = "".join(char for char in text if char in "0123456789")
            self.country_amount_text = (self.country_amount_text + digits).lstrip("0")[:13]
            self.country_card_hits = []

    def country_amount_key(self, key, modifiers):
        if self.country_card_action not in ("aid", "loan") or not self.country_amount_focus:
            return
        if key == arcade.key.BACKSPACE:
            self.country_amount_text = self.country_amount_text[:-1]
        elif key == arcade.key.DELETE or (key == arcade.key.A and modifiers & arcade.key.MOD_CTRL):
            self.country_amount_text = ""
        self.country_card_hits = []

    def country_action_label(self, player, key):
        if key == "exports":
            return "Открыть экспорт" if player.politics.export_restricted else "Ограничить экспорт"
        if key == "external":
            return "Закрыть внешний рынок" if player.politics.external_access else "Открыть внешний рынок"
        if key == "embargo":
            relation = self.politics.relation(self.human_player.id, player.id)
            return "Снять эмбарго" if self.human_player.id in relation.embargoes else "Ввести эмбарго"
        if key.startswith(("support:", "stop:")):
            verb = "Завершить программу" if key.startswith("stop:") else "Начать программу"
            return f"{verb}: {SUPPORT_GROUPS[key.split(':')[1]]}"
        return ACTIONS[key].label

    def country_society_rows(self, player):
        state = player.politics
        rows = [(f"Поддержка правительства: {state.government_support:.0%}", None),
                (f"Устойчивость: {player.stability:.0%}; легитимность: {player.legitimacy:.0%}", None),
                (f"Поддержка войны: {player.war_support:.0%}", None),
                ("Демография", ("tab", "population")), ("Программы поддержки", ("tab", "programs"))]
        for title, groups, shares in (("Экономические группы", GROUPS, {}),
                                      ("Социальные группы населения", SOCIAL_GROUPS, state.social_shares),
                                      ("Политические фракции", FACTIONS, state.faction_shares)):
            rows.append((title, None))
            for key, name in groups.items():
                share = f"; оценочная доля {shares[key]:.0%}" if key in shares else ""
                rows.append((f"{name}: поддержка {state.support[key]:.0%}{share}", None))
        return rows

    def country_detail_rows(self, player, section):
        rows = [("Назад к сводке", ("tab", "summary"))]
        if section == "population":
            data = self.population_demographic_summary(player)
            rows.append((f"Население: {self.format_population(data['population'])}", None))
            for key, name in (("children", "Дети"), ("working_age", "Трудоспособный возраст"), ("elderly", "Пожилые")):
                rows.append((f"{name}: {self.format_population(data['age'].get(key, 0))}", None))
            for key, name in (("male", "Мужчины"), ("female", "Женщины")):
                rows.append((f"{name}: {self.format_population(data['gender'].get(key, 0))}", None))
            for key, name in (("military_obligated", "Военнообязанные"), ("mobilization_available", "Доступно добровольцев")):
                rows.append((f"{name}: {self.format_population(data[key])}", None))
            rows.append((f"Готовность добровольцев: {data['volunteer_share']:.0%}", None))
            rows.append(("Общественные настроения", ("tab", "society")))
        elif section == "budget":
            income, expenses = player.monthly_income_breakdown or {}, player.monthly_expenses_breakdown or {}
            rows.extend([(f"Казна: {self.format_money(player.budget)}", None),
                         (f"Баланс: {self.format_money_delta(player.monthly_balance)}/мес.", None),
                         ("Доходы и торговый баланс за месяц", None)])
            for key, name in (("population", "Налоги населения"), ("companies", "Налоги компаний"), ("trade", "Торговля (прогноз)"), ("loan_repayments", "Возврат кредитов (прогноз)")):
                rows.append((f"{name}: {self.format_money_delta(income.get(key, 0))}", None))
            rows.append(("Расходы за месяц", None))
            for key, name in (("army", "Армия"), ("government", "Правительство"), ("social", "Социальное обеспечение"), ("infrastructure", "Инфраструктура"), ("political_programs", "Программы поддержки"), ("debt_service", "Платежи по кредитам")):
                rows.append((f"{name}: {self.format_money(expenses.get(key, 0))}", None))
            rows.append(("Подробная экономика", ("panel", "economy")))
        elif section == "taxes":
            rows = [("Налоги", None), ("Назад к решениям", ("tab", "actions"))]
            for key, name in GROUPS.items():
                rows.append((f"{name}: {player.politics.tax_multiplier(key):.0%} базовых поступлений", None))
                for delta in (-1, 1):
                    action = f"tax:{key}:{delta}"
                    rows.append((ACTIONS[action].label, ("action", action)))
        elif section == "programs":
            rows = [("Программы поддержки групп", None), ("Назад к решениям", ("tab", "actions"))]
            for heading, groups in (("Социальные и деловые программы", GROUPS), ("Социальные группы", SOCIAL_GROUPS), ("Политическое представительство", FACTIONS)):
                rows.append((heading, None))
                for key in groups:
                    active = key in player.politics.programs
                    action = f"{'stop' if active else 'support'}:{key}"
                    rows.append((self.country_action_label(player, action), ("action", action)))
                    if active:
                        end = player.politics.programs[key]
                        term = "До отмены" if end is None else f"До {self.politics.date_text(end)}"
                        rows.append((f"{term}; {self.format_money(player.politics.program_costs.get(key, 0))}/мес.", None))
        elif section == "power":
            return self.country_power_rows(player)
        return rows

    def country_threat(self, player):
        relation = self.politics.relation(self.human_player.id, player.id)
        ratings = power_ranking(self.players)
        military = ratings[player.id]['military']
        own = ratings[self.human_player.id]['military']
        if relation.at_war:
            level = "высокая" if military >= own else "средняя"
            return f"Военная угроза: {level}; идёт война"
        if "alliance" in relation.treaties:
            return "Военная угроза: низкая; действует союз"
        hostile = relation.opinions[player.id] < -20
        level = "высокая" if hostile and military > own * 1.15 else "средняя" if hostile else "низкая"
        return f"Военная угроза: {level}; отношение {relation.opinions[player.id]:+.0f}"

    def country_power_rows(self, player):
        ratings = power_ranking(self.players)
        rating = ratings[player.id]
        rows = [("Назад к сводке", ("tab", "summary")),
                (f"Мощь: {rating['total']:.1f}/100; место {rating['rank']} из {len(ratings)}", None)]
        for key, name in (("economy", "Экономический потенциал"), ("military", "Боеготовность сухопутных сил"), ("society", "Социальный потенциал")):
            rows.append((f"{name}: {rating[key]:.1f}/100", None))
        rows.extend([("Экономика 40%: налоговая база; армия 40%: люди, вооружение, состояние и снабжение; общество 20%: население и внутренняя устойчивость.", None),
                     ("100 по отдельному показателю: лидер текущего мира. Авиация и география пока не входят в оценку; это не прогноз победы.", None)])
        if player is not self.human_player:
            rows.extend([(relative_power(rating['total'], ratings[self.human_player.id]['total']), None),
                         (self.country_threat(player), None)])
        return rows

    def country_rows(self, player, action_preview=False):
        own = player.id == self.human_player.id
        rows = []
        if self.country_card_action and (not self.country_dialog or action_preview):
            action = ACTIONS[self.country_card_action]
            description = action.description
            if action.key == "exports":
                description = "Восстановить полный лимит экспорта." if player.politics.export_restricted else "Сократить лимит экспорта на 50%."
            elif action.key == "external":
                description = "Прямые сделки со странами сохраняются. " + ("Заявки внешнему рынку перестанут исполняться." if player.politics.external_access else "Заявки внешнему рынку снова смогут исполняться.")
            rows.extend([(self.country_action_label(player, action.key), None), (description, None)])
            amount = self.country_amount()
            if action.key in ("aid", "loan"):
                rows.append((f"Сумма: {self.country_amount_text or '0'}" + (" |" if self.country_amount_focus else ""), ("amount", None)))
            quote = self.politics.quote(self.human_player.id, player.id, action.key, amount)
            rows.append((f"Расход сейчас: {self.format_money(quote.cost)}; повтор с {self.politics.date_text(self.politics.day + quote.cooldown_days)}", None))
            if quote.opinion_delta or quote.trust_delta:
                rows.append((f"Отношение: {quote.opinion_delta:+g}; доверие: {quote.trust_delta:+.0%}", None))
            if action.key == "loan":
                rows.append((f"Срок: {quote.loan_term_months} мес.; ставка: {quote.loan_annual_rate:.1%} годовых", None))
            if action.key in OFFERS:
                rows.append((f"Ожидаемый ответ: {self.politics.date_text(self.politics.day + quote.response_days)}", None))
            if action.key == "peace":
                rows.append((f"Перемирие: {quote.truce_days} дн.", None))
            if action.key.startswith("support:"):
                term = "до отмены" if quote.program_days is None else f"на {quote.program_days} дней"
                rows.append((f"{self.format_money(quote.program_monthly_cost)}/мес., {term}", None))
                group = action.key.split(":")[1]
                rows.append((f"Поддержка правительства группой: {player.politics.support[group]:.0%}. Программа постепенно повышает её лояльность; это регулярные расходы бюджета.", None))
            if action.key.startswith("stop:"):
                rows.append(("Регулярные расходы прекратятся. Эффект программы на лояльность постепенно исчезнет.", None))
            reason = self.politics.reason(self.human_player.id, player.id, action.key, amount)
            rows.append((reason or "Подтвердить решение", None if reason else ("confirm", action.key)))
            rows.append(("Отмена", ("cancel", None)))
            return rows
        if own and self.country_card_tab in ("budget", "population", "taxes", "programs", "power"):
            return self.country_detail_rows(player, self.country_card_tab)
        if self.country_card_tab == "power":
            return self.country_power_rows(player)
        if self.country_card_tab == "summary":
            rows.append((f"Население: {self.format_population(player.population or 0)}", ("tab", "population") if own else None))
            if own:
                rows.extend([
                    ("Бюджет", ("panel", "economy")),
                    (f"Баланс: {self.format_money_delta(player.monthly_balance)}/мес", None),
                    (f"Поддержка правительства: {player.politics.government_support:.0%}", ("dialog", "support")),
                    (f"Устойчивость: {player.stability:.0%}; легитимность: {player.legitimacy:.0%}", None),
                ])
                if player.monthly_balance < 0:
                    rows.append(("Дефицит бюджета", ("tab", "actions")))
                if self.last_market_unfilled:
                    amount = sum(o["amount"] for o in self.last_market_unfilled if o["player"].id == player.id and o["mode"] == "buy")
                    if amount:
                        rows.append((f"Не исполнено закупок: {self.format_resource_amount(amount)}", ("tab", "trade")))
            else:
                relation = self.politics.relation(self.human_player.id, player.id)
                status = "Война" if relation.at_war else "Союз" if "alliance" in relation.treaties else "Мир"
                rows.extend([(f"Статус: {status}", None),
                             (f"Отношение к нам: {relation.opinions[player.id]:+.0f}; доверие: {relation.trust:.0%}", None),
                             ("Договоры: " + (", ".join(TREATIES[k] for k in sorted(relation.treaties)) or "нет"), None),
                             ("Внутренняя поддержка и бюджет: нет достоверных сведений", None)])
            rating = power_ranking(self.players)[player.id]
            rows.append((f"Мощь государства: место {rating['rank']} из {len(self.players)}", ("tab", "power")))
            if not own:
                rows.append((self.country_threat(player), None))
        elif self.country_card_tab == "society":
            if own:
                rows.extend(self.country_society_rows(player))
            else:
                rows.append(("Нет достоверных сведений о настроениях групп", None))
        elif self.country_card_tab == "trade":
            rows.append(("Внешний рынок: " + ("открыт" if player.politics.external_access else "закрыт"), None))
            rows.append((f"Экспорт: {player.politics.export_capacity_factor:.0%} базовой мощности", None))
            if not own:
                allowed = self.politics.trade_allowed(self.human_player.id, player.id)
                rows.append(("Прямая торговля: " + ("разрешена" if allowed else "заблокирована"), None))
            else:
                flows = self.estimate_monthly_trade_flows(player)
                rows.extend([(f"Прогноз импорта: {self.format_resource_amount(sum(flows['imports'].values()))}/мес.; экспорта: {self.format_resource_amount(sum(flows['exports'].values()))}/мес.", None),
                             (f"Торговый баланс (прогноз): {self.format_money_delta(flows['money_balance'])}/мес.", None),
                             ("Управление контрактами", ("panel", "trade"))])
                contracts = self.normalized_trade_contracts(player.trade_contracts)
                diagnostics = self.trade_contract_diagnostics(player, contracts, flows)
                rows.append((f"Контракты: {len(contracts)}", None))
                for contract in contracts:
                    key, mode = contract['resource'], contract['mode']
                    label = "Закупка" if mode == "buy" else "Продажа"
                    rows.append((f"{label}: {self.resource_display_name(key)}, {self.format_resource_amount(contract['amount'])}/мес.", None))
                    rows.append((diagnostics[(key, mode)][1], None))
            rows.append(("Последние исполненные сделки:", None))
            for fill in self.last_market_fills:
                buyer, seller = fill["buyer"], fill["seller"]
                ids = {p.id for p in (buyer, seller) if p is not None}
                if self.human_player.id not in ids or (not own and player.id not in ids):
                    continue
                rows.append((f"{seller.name if seller else 'Внешний рынок'} > {buyer.name if buyer else 'Внешний рынок'}: "
                             f"{self.resource_display_name(fill['resource'])}, {self.format_resource_amount(fill['amount'])}, "
                             f"{self.format_money(fill['price'])}/ед.", None))
        elif self.country_card_tab == "actions":
            if own:
                rows.extend([(self.country_action_label(player, key), ("action", key)) for key in ("exports", "external")])
                rows.extend([("Налоги", ("tab", "taxes")), ("Программы поддержки групп", ("tab", "programs"))])
            else:
                for key, action in ACTIONS.items():
                    if action.domestic:
                        continue
                    reason = self.politics.reason(self.human_player.id, player.id, key, self.country_amount())
                    rows.append((self.country_action_label(player, key) + (f" ({reason})" if reason else ""), ("action", key)))
        elif self.country_card_tab == "history":
            for offer in self.politics.pending:
                a, b, key, due = offer
                if self.human_player.id not in (a, b) or (not own and player.id not in (a, b)):
                    continue
                rows.append((f"{OFFERS[key]}: {self.player_by_id(a).name} > {self.player_by_id(b).name}; ожидаемый ответ: {self.politics.date_text(due)}", None))
                if key == "loan":
                    quote = self.politics.offer_quotes[offer]
                    rows.append((f"{self.format_money(self.politics.offer_amounts[offer])}; {quote.loan_term_months} мес.; {quote.loan_annual_rate:.1%}", None))
                if b == self.human_player.id:
                    rows.extend([("Принять", ("offer", (offer, True))), ("Отклонить", ("offer", (offer, False)))])
            for loan in self.politics.loans:
                if self.human_player.id not in (loan.lender, loan.borrower) or (not own and player.id not in (loan.lender, loan.borrower)):
                    continue
                rows.append((f"Кредит: {self.player_by_id(loan.lender).name} > {self.player_by_id(loan.borrower).name}; "
                             f"долг {self.format_money(loan.principal)}; ставка {loan.annual_rate:.1%}; следующий платёж: {self.politics.date_text(loan.next_due)}", None))
                if loan.principal_due + loan.interest_due > 0:
                    rows.append((f"К оплате / просрочка: {self.format_money(loan.principal_due + loan.interest_due)}", None))
            rows.extend((f"{self.politics.date_text(day)}: {message}", None) for day, message in player.politics.history
                        if own or message.startswith(self.human_player.name + ":"))
        return rows or [("Нет событий", None)]

    def draw_country_text(self, text, x, y, color=(224, 234, 244), font_size=12, anchor_x="left", anchor_y="baseline"):
        color = (*color, 255) if len(color) == 3 else color
        index = self.country_text_cursor
        self.country_text_cursor += 1
        if index == len(self.country_text_pool):
            self.country_text_pool.append(arcade.Text("", 0, 0, batch=self.country_text_batch))
        label = self.country_text_pool[index]
        changes = [(name, value) for name, value in
                   (("text", str(text)), ("x", x), ("y", y), ("color", color),
                    ("font_size", font_size), ("anchor_x", anchor_x), ("anchor_y", anchor_y))
                   if getattr(label, name) != value]
        if changes:
            with label:
                for name, value in changes:
                    setattr(label, name, value)

    def draw_country_card(self):
        if self.active_top_panel_key not in ("politics", "diplomacy") or self.side_panel_progress <= 0:
            return
        view_key = (self.country_list_open, self.country_card_tab)
        if view_key not in self.country_text_views:
            self.country_text_views[view_key] = (Batch(), [])
        self.country_text_views.move_to_end(view_key)
        while len(self.country_text_views) > 12:
            _, (_, labels) = self.country_text_views.popitem(last=False)
            for label in labels:
                label.label.delete()
        self.country_text_batch, self.country_text_pool = self.country_text_views[view_key]
        self.country_text_cursor = 0
        player = self.player_by_id(self.country_card_id)
        x, y, width, height = self.country_panel_rect()
        arcade.draw_lbwh_rectangle_filled(x, y, width, height, (18, 24, 31, 244))
        arcade.draw_lbwh_rectangle_outline(x, y, width, height, (110, 130, 154), 2)
        self.country_card_hits = []

        def button(label, rect, kind, value=None):
            bx, by, bw, bh = rect
            arcade.draw_lbwh_rectangle_filled(bx, by, bw, bh, (38, 50, 66))
            arcade.draw_lbwh_rectangle_outline(bx, by, bw, bh, (95, 118, 145), 1)
            self.draw_country_text(label, bx + bw / 2, by + bh / 2, font_size=11, anchor_x="center", anchor_y="center")
            self.country_card_hits.append((rect, kind, value))

        top = y + height
        title = "Дипломатия" if self.country_list_open else (player.name if player else "Государство")
        self.draw_country_text(title[:30], x + 18, top - 28, (238, 244, 250), 18, anchor_y="center")
        button("X", self.side_panel_close_rect(), "close")
        if not self.country_list_open:
            button("Страны", (x + width - 130, top - 38, 82, 28), "countries")
        tabs = (("summary", "Сводка"), ("society", "Общество"), ("trade", "Торговля"), ("actions", "Решения"), ("history", "События"))
        tab_width = (width - 24) / len(tabs)
        for index, (key, label) in enumerate(() if self.country_list_open else tabs):
            rect = (x + 12 + index * tab_width, top - 78, tab_width - 3, 28)
            button(label, rect, "tab", key)
            active_tab = {"budget": "summary", "population": "summary", "power": "summary", "taxes": "actions", "programs": "actions"}.get(self.country_card_tab, self.country_card_tab)
            if key == active_tab:
                arcade.draw_line(rect[0], rect[1], rect[0] + rect[2], rect[1], (110, 210, 155), 2)
        cache_key = (self.country_card_id, self.country_list_open, self.country_card_tab, self.country_card_action, self.country_amount_text,
                     self.country_amount_focus, width, self.politics.revision,
                     int(time.monotonic() * 2), self.simulation_server.market_state.revision,
                     tuple(p.trade_contract_revision for p in self.players))
        if self.country_lines_cache is None or self.country_lines_cache[0] != cache_key:
            lines = []
            rows = []
            if self.country_list_open:
                ratings = power_ranking(self.players)
                wars = sum(self.politics.hostile(self.human_player.id, p.id) for p in self.players if p is not self.human_player)
                rows.append((f"Государств: {len(self.players)}; войн: {wars}; наше место по мощи: {ratings[self.human_player.id]['rank']}", None))
                relations = [self.politics.relation(self.human_player.id, p.id) for p in self.players if p is not self.human_player]
                rows.append((f"Союзов: {sum('alliance' in r.treaties for r in relations)}; торговых договоров: {sum('trade' in r.treaties for r in relations)}", None))
                for country in self.players:
                    if country is self.human_player:
                        status = "Ваше государство"
                    else:
                        relation = self.politics.relation(self.human_player.id, country.id)
                        status = "Война" if relation.at_war else "Союз" if "alliance" in relation.treaties else "Мир"
                    rows.append((f"{country.name}   |   {status}", ("country", country.id)))
                    if country is not self.human_player:
                        rows.append((f"Отношение {relation.opinions[country.id]:+.0f}; доверие {relation.trust:.0%}. "
                                     + relative_power(ratings[country.id]['total'], ratings[self.human_player.id]['total']), ("country", country.id)))
            elif player:
                rows = self.country_rows(player)
            for text, action in rows:
                if not action and text in ("Экономические группы", "Социальные группы населения", "Политические фракции", "Последние исполненные сделки:"):
                    if lines and lines[-1][0]:
                        lines.append(("", None))
                wrapped = textwrap.wrap(text, max(20, int((width - 40) / 7.5))) or [""]
                lines.extend((line, action) for line in wrapped)
            self.country_lines_cache = (cache_key, lines)
        lines = self.country_lines_cache[1]
        visible = max(1, int((height - 132) // 23))
        self.country_card_scroll = min(max(0, self.country_card_scroll), max(0, len(lines) - visible))
        for index, (line, action) in enumerate(lines[self.country_card_scroll:self.country_card_scroll + visible]):
            line_y = top - 104 - index * 23
            action_width = width - 24
            if action:
                if action[0] == "amount":
                    action_width -= 76
                    button("-", (x + width - 80, line_y - 5, 30, 23), "amount_step", -1_000_000)
                    button("+", (x + width - 46, line_y - 5, 30, 23), "amount_step", 1_000_000)
                arcade.draw_lbwh_rectangle_filled(x + 12, line_y - 5, action_width, 23, (35, 48, 57))
            self.draw_country_text(line, x + 16, line_y, (170, 220, 195) if action else (224, 234, 244), 11)
            if action:
                self.country_card_hits.append(((x + 12, line_y - 5, action_width, 23), action[0], action[1]))
        if len(lines) > visible:
            track_height = max(23, visible * 23)
            thumb_height = max(24, track_height * visible / len(lines))
            track_y = top - 104 - (visible - 1) * 23 - 5
            thumb_y = track_y + (track_height - thumb_height) * (1 - self.country_card_scroll / max(1, len(lines) - visible))
            arcade.draw_lbwh_rectangle_filled(x + width - 8, track_y, 4, track_height, (48, 62, 78, 180))
            arcade.draw_lbwh_rectangle_filled(x + width - 8, thumb_y, 4, thumb_height, (132, 156, 184, 220))
            self.draw_country_text(f"{self.country_card_scroll + 1}-{min(len(lines), self.country_card_scroll + visible)} / {len(lines)}", x + width - 16, y + 12, font_size=10, anchor_x="right")
        for label in self.country_text_pool[self.country_text_cursor:]:
            if label.text:
                label.text = ""
        self.country_text_batch.draw()
        self.draw_country_dialog()
