"""Read-only developer inspector. Reasons are recorded by the decision code."""
import textwrap
import time


COURSES = {"development": "Развитие", "war_preparation": "Подготовка войны",
           "defense": "Оборона", "deterrence": "Сдерживание", "recovery": "Восстановление"}


def inspection_rows(game, country_id, foreign_id):
    ai = game.ai_system
    bot = ai.bots[country_id]
    player = game.player_by_id(country_id)
    other = game.player_by_id(foreign_id)
    relation = game.politics.relations.get(tuple(sorted((country_id, foreign_id))))
    target = game.player_by_id(bot.target_id) if bot.target_id is not None else None
    rows = [f"Курс: {COURSES.get(bot.course, bot.course)}; цель: {target.name if target else 'нет'}",
            f"Агрессивность {bot.aggression:.0%}; разведка {bot.intelligence:.0%}; "
            f"курс выбран {max(0, ai.hour - bot.course_since) / 24:.1f} дн. назад",
            f"Казна {player.budget:,.0f}; баланс/мес {player.monthly_balance:,.0f}; "
            f"дивизий {len(player.divisions)}; территорий {len(player.tiles)}",
            f"Снабжение страны {player.supply_summary.get('average', 0):.0%}; "
            f"резерв {bot.reserve_id}; отдыхает {len(bot.resting_ids)}",
            f"ОТНОШЕНИЕ К: {other.name} (ID {foreign_id})"]
    if relation:
        rows += [f"Мнение бота {relation.opinions.get(country_id, 0):+.1f}; "
                 f"ответное {relation.opinions.get(foreign_id, 0):+.1f}; доверие {relation.trust:.0%}",
                 f"Война: {relation.at_war}; кризис {relation.crisis_level:.1f}; "
                 f"договоры: {', '.join(sorted(relation.treaties)) or 'нет'}"]
    else:
        rows.append("Дипломатические отношения ещё не сформированы")
    rows.append("ЭКОНОМИЧЕСКАЯ ЗАВИСИМОСТЬ: последняя оценка поставок")
    dependencies = [(resource, data) for (partner, resource), data in bot.dependencies.items() if partner == foreign_id]
    for resource, data in dependencies:
        rows.append(f"{resource}: импорт покрывает {data['share']:.0%} потребности, запас на {data['stock_days']:.1f} дн.; "
                    f"оценка {max(0, ai.hour - data['observed_hour']) / 24:.1f} дн. назад")
    if not dependencies:
        rows.append("В последней оценке зависимость от поставок этой страны не зафиксирована")
    influence = bot.influence.get(foreign_id)
    if influence:
        rows.append(f"Наше экономическое влияние на неё: {influence['economic']:.0%}; военное соотношение атака/оборона {influence['military_ratio']:.2f}")
    if player.divisions:
        rows.append(f"Готовность армии: организация {sum(d.organization / max(1, d.max_organization) for d in player.divisions) / len(player.divisions):.0%}; "
                    f"фактическое снабжение дивизий {sum(d.last_supply_ratio for d in player.divisions) / len(player.divisions):.0%}")
    own = bot.reports.get(country_id)
    report = bot.reports.get(foreign_id)
    if report:
        rows.append("ВОЕННАЯ/ЭКОНОМИЧЕСКАЯ ОЦЕНКА (разведданные бота)")
        for label, estimates, key in (("Атака", report.military, "attack"),
                                      ("Оборона", report.military, "defense"),
                                      ("Казна", report.finance, "budget")):
            estimate = estimates.get(key)
            if estimate:
                rows.append(f"{label}: {estimate.value:,.1f} [{estimate.lower:,.1f}..{estimate.upper:,.1f}], "
                            f"возраст {max(0, ai.hour - estimate.observed_hour) / 24:.1f} дн.")
        attack = report.military.get("attack")
        own_attack = own.military.get("attack") if own else None
        if attack and own_attack:
            rows.append(f"Их атака / наша: {attack.value / max(1, own_attack.value):.2f}; "
                        f"порог угрозы алгоритма: >1.10 либо кризис >=25")
        deficits = [(v["required"].value - v["capacity"].value, key) for key, v in report.economy.items()]
        rows.append("Их дефициты мощности: " + ", ".join(f"{key} {value:,.0f}/мес" for value, key in sorted(deficits, reverse=True)[:5] if value > 0))
    else:
        rows.append("Разведывательного отчёта об этой стране пока нет")
    rows += [f"Оценка при выборе курса: {bot.course_evidence.get(foreign_id, 'нет в последнем наборе сравнения')}",
             "Прогноз будущего усиления противника и отдельная превентивная война пока не рассчитываются.",
             (f"ПОСЛЕДНИЙ ВЫБОР КУРСА: {max(0, ai.hour - bot.course_decision['hour']) / 24:.1f} дн. назад"
              if bot.course_decision else "ВЫБОР КУРСА ещё не проводился; действует начальная установка")]
    for candidate in bot.course_decision.get("candidates", []):
        rows.append(f"{COURSES.get(candidate['course'], candidate['course'])}: {candidate['score']:.2f}; цель ID {candidate['target']}")
    rows.append("Оценки включают случайный уклон, +10 за текущий курс и -20 за раннюю смену; выбор среди близких оценок.")
    ready = game.politics.war_goals.get((country_id, foreign_id))
    if ready is not None:
        rows.append(f"Оправдание войны: готово через {max(0, ready - game.politics.day)} дн.")
    rows.append("ПЛАНЫ / СТАТУС / ПРИЧИНЫ")
    for task in sorted(bot.tasks, key=lambda t: (t.status in {"succeeded", "failed", "cancelled"}, -t.id))[:18]:
        rows.append(f"#{task.id} {task.kind}: {task.status}; создана {max(0, ai.hour - task.created_hour) / 24:.1f} дн. назад; {task.payload}")
        if task.motivation:
            rows.append("Зачем: " + task.motivation)
        if task.reason:
            rows.append("Результат/помеха: " + task.reason)
    rows.append(f"НЕЙТРАЛЬНАЯ ЭКСПАНСИЯ: снимок {max(0, ai.hour - bot.expansion_observed_hour) / 24:.1f} дн. назад")
    for row in bot.expansion_candidates[:8]:
        rows.append(f"{row['tile']}: {row['score']:.2f} = местность {row['terrain']:.2f} + "
                    f"сельхоз {row['agriculture']:.2f} + направление {row['direction']:.2f} + ресурсы {row['resources']}")
    rows.append("АРМИЯ: реальные приказы / назначенные посты")
    for division in player.divisions:
        tile = game.tile_key(division.tile) if division.tile else None
        destination = game.tile_key(division.target_tile) if division.target_tile else None
        rows.append(f"#{division.id}: {tile} -> {destination}; {division.route_mode}; "
                    f"пост {bot.hex_assignments.get(division.id)}; путь {len(division.path)}; "
                    f"орг. {division.organization:.0f}; снабж. {division.last_supply_ratio:.0%}; бой {division.battle_id}")
        if division.id in bot.last_order_reasons:
            rows.append("Мотив последнего приказа: " + bot.last_order_reasons[division.id])
    rows.append("ФАКТИЧЕСКИЕ РЕШЕНИЯ И ОТВЕТЫ СЕРВЕРА")
    rows.append("ПВО: боекомплект / пополнение / движение")
    for unit in player.air_defense_units:
        rows.append(f"#{unit.id} {unit.unit_class}: БК {unit.ammo}/{unit.ammo_capacity}; "
                    f"в пути {bool(unit.path)}, работает {game.air_defense_unit_operational(unit)}; {unit.resupply_status}")
    for event in list(reversed(bot.history))[:18]:
        rows.append(str(event))
    workers = getattr(ai, "workers", None)
    if workers:
        rows.append(f"МАКРОПРОЦЕСС: задач {len(workers.pending)}, результатов {len(workers.results)}, ошибки {workers.errors}")
        for key, (hour, _) in workers.results.items():
            if key[1] == country_id:
                rows.append(f"{key[0]}: снимок {max(0, ai.hour - hour) / 24:.1f} дн. назад")
    if report:
        rows.append("ПОЛНЫЙ ЭКОНОМИЧЕСКИЙ ВЕКТОР ЦЕЛЕВОЙ СТРАНЫ (оценки/мес)")
        for key, values in sorted(report.economy.items()):
            rows.append(f"{key}: мощность {values['capacity'].value:.1f}; нужно {values['required'].value:.1f}; "
                        f"запас {values['stock'].value:.1f}; импорт {values['import'].value:.1f}; экспорт {values['export'].value:.1f}")
    return rows


class AIDebugPanel:
    def __init__(self):
        self.open = False
        self.country_id = None
        self.foreign_id = None
        self.scroll = 0
        self.next_refresh = 0
        self.rows = []
        self.labels = []
        self.header = None

    def rect(self, game):
        return max(8, game.window.width - 700), 90, min(684, game.window.width - 16), game.window.height - 180

    def select(self, game, step=0, foreign=False):
        ids = sorted(p.id for p in game.players if p.id != self.country_id) if foreign else sorted(game.ai_system.bots)
        if not ids:
            return
        current = self.foreign_id if foreign else self.country_id
        value = ids[(ids.index(current) + step) % len(ids)] if current in ids else ids[0]
        if foreign:
            self.foreign_id = value
        else:
            self.country_id = value
            if self.foreign_id == value or self.foreign_id is None:
                self.foreign_id = next((p.id for p in game.players if p.id != value), value)
        self.scroll = 0
        self.next_refresh = 0

    def click(self, game, x, y):
        if not self.open or not game.point_in_rect(x, y, self.rect(game)):
            return False
        left, bottom, width, height = self.rect(game)
        if y > bottom + height - 50:
            self.select(game, -1 if x < left + width / 2 else 1, foreign=y < bottom + height - 27)
        return True

    def wheel(self, game, x, y, amount):
        if not self.open or not game.point_in_rect(x, y, self.rect(game)):
            return False
        self.scroll = max(0, min(max(0, len(self.rows) - 5), self.scroll - int(amount * 3)))
        return True

    def draw(self, game):
        if not self.open:
            return
        import arcade
        if not game.ai_system.bots:
            if self.header is None:
                self.header = arcade.Text("F4: в этой партии нет ботов", 20, game.window.height - 115,
                                          (245, 211, 132), 14)
            self.header.draw()
            return
        if self.country_id not in game.ai_system.bots:
            self.select(game)
        left, bottom, width, height = self.rect(game)
        if time.monotonic() >= self.next_refresh:
            self.rows = [part for row in inspection_rows(game, self.country_id, self.foreign_id)
                         for part in textwrap.wrap(row, width=max(32, int((width - 24) / 7))) or [""]]
            self.next_refresh = time.monotonic() + .5
        count = max(1, int((height - 84) / 17))
        if self.header is None:
            self.header = arcade.Text("", 0, 0, (245, 211, 132), 12, width=width - 20, multiline=True)
        while len(self.labels) < count:
            self.labels.append(arcade.Text("", 0, 0, (218, 231, 241), 11))
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, (12, 19, 28, 248))
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, (180, 155, 90), 2)
        actor = game.player_by_id(self.country_id)
        other = game.player_by_id(self.foreign_id)
        self.header.text = f"< БОТ: {actor.name} >    F4: закрыть\n< К ДРУГОЙ СТРАНЕ: {other.name} >\nКолесо: прокрутка | строки {self.scroll + 1}/{len(self.rows)}"
        self.header.x, self.header.y = left + 10, bottom + height - 20
        self.header.draw()
        for index, label in enumerate(self.labels[:count]):
            label.text = self.rows[self.scroll + index] if self.scroll + index < len(self.rows) else ""
            label.x, label.y = left + 10, bottom + height - 91 - index * 17
            label.draw()
