"""Simulation-owned news feed. Headlines have no gameplay effects."""

from collections import Counter, deque
from dataclasses import dataclass, field
import random
from datetime import datetime, timedelta
from pathlib import Path
import warnings


PRIORITIES = {"flavor": 0, "regular": 1, "important": 2, "critical": 3}
BATCHED_NOTICES = {"construction_complete", "air_defense_completed", "aircraft_losses",
                   "division_destroyed", "territory_lost", "territory_gained"}


@dataclass(frozen=True)
class NewsTemplate:
    key: str
    title: str
    body: str
    priority: str
    daily_chance: float
    cooldown_days: int
    developer_note: str


WORLD_TEMPLATES = {
    template.key: template for template in (
        NewsTemplate("oil_crisis", "Мировой нефтяной кризис",
            "Участники рынка сообщают о перебоях поставок нефти. Правительства обсуждают доступ к топливу и альтернативные маршруты.",
            "critical", .0008, 365, "В будущем: рост цен на нефть, выгода экспортёрам и издержки импортёрам."),
        NewsTemplate("warming", "Ускорение глобального потепления",
            "Новые климатические наблюдения усилили международную дискуссию о долгосрочных рисках для экономики и населения.",
            "important", .0003, 730, "В будущем: урожайность, миграция, стихийные бедствия и энергетическая политика."),
        NewsTemplate("trade_routes", "Перебои на торговых маршрутах",
            "Торговые компании сообщают о задержках международных перевозок и пересматривают планы поставок.",
            "important", .0015, 240, "В будущем: логистика, внешние квоты и цены затронутых товаров."),
        NewsTemplate("harvest", "Сведения о неурожае",
            "В нескольких регионах обсуждают слабые прогнозы урожая. Импортёры продовольствия следят за рынком.",
            "important", .0015, 365, "В будущем: производство еды, цены, поддержка населения и торговля."),
        NewsTemplate("physicists", "Международный скандал вокруг физиков",
            "Сообщения о казни мирных учёных вызвали резкую реакцию научного сообщества и международную дискуссию.",
            "important", .0002, 1000, "В будущем: дипломатическая репутация, миграция специалистов и научное развитие."),
        NewsTemplate("science", "Прорыв в исследованиях",
            "Международная группа исследователей объявила о перспективном открытии. Практическое применение ещё предстоит проверить.",
            "regular", .004, 180, "В будущем: научные программы и технологические возможности."),
        NewsTemplate("energy", "Новые планы в энергетике",
            "Отраслевые эксперты обсуждают изменение структуры энергоснабжения и возможные инвестиции.",
            "regular", .003, 180, "В будущем: производство энергии, нефть и инвестиции."),
        NewsTemplate("climate_summit", "Международная климатическая встреча",
            "Представители стран собрались обсудить климатические прогнозы и совместные инициативы.",
            "regular", .003, 240, "В будущем: переговоры, соглашения и климатическая политика."),
        NewsTemplate("strange_signal", "Необычный радиосигнал",
            "Радиоастрономы проверяют сообщение о необычном сигнале. Пока наиболее вероятна техническая причина.",
            "flavor", .008, 150, "Атмосферное событие без обязательного игрового эффекта."),
        NewsTemplate("games", "Международные соревнования",
            "Спортсмены из разных стран готовятся к крупным соревнованиям. Газеты спорят о фаворитах.",
            "flavor", .006, 150, "Атмосферное событие без обязательного игрового эффекта."),
        NewsTemplate("ai_discovery", "Новый шаг в исследованиях ИИ",
            "Исследовательская группа представила систему, способную решать задачи, которые прежде требовали работы целой команды. Учёные призывают проверить результаты независимо, а общество уже спорит о будущем профессий.",
            "regular", .003, 240, "Позже: исследования, автоматизация и общественное мнение."),
        NewsTemplate("ai_debate", "Спор о правилах для ИИ",
            "На международной конференции разработчики и юристы не смогли договориться о границах применения новых моделей. Одни говорят об ускорении науки, другие — о цене ошибок.",
            "flavor", .003, 220, "Позже: регулирование технологий и научная кооперация."),
        NewsTemplate("evolution", "Неожиданная находка биологов",
            "Исследователи описали ранее неизвестную ветвь эволюционного дерева. Научные журналы обсуждают, насколько сильно открытие изменит привычную картину прошлого.",
            "regular", .002, 300, "Позже: научный прогресс и образование."),
        NewsTemplate("particle", "Новая частица в лабораторных данных",
            "Физики заметили необычный след в результатах эксперимента. До окончательных выводов ещё далеко, но имя будущего лауреата уже пытаются угадать в газетах.",
            "regular", .002, 300, "Позже: фундаментальная наука."),
        NewsTemplate("nobel_speculation", "Кому достанется Нобелевская премия?",
            "Научные обозреватели вновь составляют списки претендентов. Открытие, ещё недавно известное только специалистам, оказалось в центре общественного внимания.",
            "flavor", .002, 365, "Атмосферное событие; премия не присуждается игровой механикой."),
        NewsTemplate("exoplanet", "Открыта необычная экзопланета",
            "Астрономы сообщили о планете с неожиданными характеристиками атмосферы. Подтвердить наблюдения попробуют несколько независимых обсерваторий.",
            "flavor", .003, 250, "Позже: астрономические исследования."),
        NewsTemplate("fusion", "Обнадёживающий опыт с термоядерной энергией",
            "Инженеры сообщили о результатах нового эксперимента. От лабораторного успеха до электростанции ещё долгий путь, но энергетические ведомства уже запросили подробности.",
            "regular", .002, 360, "Позже: энергетика и научные программы."),
        NewsTemplate("battery", "Испытан новый накопитель энергии",
            "Разработчики обещают более долгую работу оборудования и меньшее потребление редких материалов. Конкуренты требуют показать результаты испытаний вне лаборатории.",
            "regular", .003, 220, "Позже: промышленность и энергетика."),
        NewsTemplate("medical_research", "Медики сообщили о перспективном лечении",
            "Первые результаты испытаний дают надежду пациентам. Врачи напоминают: пока рано говорить о массовом применении новой методики.",
            "regular", .003, 260, "Позже: здоровье населения и медицина."),
        NewsTemplate("vaccine_research", "Новая технология вакцин обсуждается врачами",
            "Исследователи предложили способ быстрее готовить защиту от новых заболеваний. Регуляторы обещают изучить данные, прежде чем делать выводы.",
            "regular", .002, 300, "Позже: здравоохранение и эпидемии."),
        NewsTemplate("deep_ocean", "Экспедиция вернулась из глубин океана",
            "Учёные подняли образцы с участков дна, куда раньше почти не добирались. В кадрах экспедиции уже ищут признаки неизвестных видов.",
            "flavor", .003, 220, "Позже: океанические исследования и ресурсы."),
        NewsTemplate("archaeology", "Археологи нашли забытый город",
            "Под слоем грунта обнаружены улицы и мастерские древнего поселения. Историки осторожны: громкие заявления придётся подтвердить раскопками.",
            "flavor", .003, 260, "Атмосферное событие без игрового эффекта."),
        NewsTemplate("biodiversity", "Учёные предупреждают об исчезновении видов",
            "Международная группа опубликовала новые наблюдения за природными экосистемами. Спор о мерах защиты уже вышел за пределы научных журналов.",
            "regular", .002, 320, "Позже: климат и природные ресурсы."),
        NewsTemplate("math_proof", "Долгая математическая задача решена?",
            "Молодой исследователь представил доказательство задачи, десятилетиями не поддававшейся коллегам. Теперь весь научный мир проверяет каждую строку.",
            "flavor", .002, 330, "Атмосферное событие; доказательство не даёт игровых бонусов."),
        NewsTemplate("telescope", "Новый телескоп начал наблюдения",
            "Первые снимки уже вызвали восторг у астрономов. Самые интересные кадры, по словам команды проекта, ещё только предстоит получить.",
            "flavor", .003, 240, "Позже: научные программы и космос."),
        NewsTemplate("comet", "Редкая комета приблизится к планете",
            "Небесное тело можно будет увидеть в ближайшие месяцы. Обсерватории готовят открытые наблюдения для всех желающих.",
            "flavor", .003, 260, "Атмосферное событие без игрового эффекта."),
        NewsTemplate("satellite", "Новый спутник вышел на орбиту",
            "Аппарат начал передавать первые данные. Разработчики надеются, что он поможет точнее наблюдать за погодой и поверхностью планеты.",
            "regular", .003, 230, "Позже: связь, разведка и метеорология."),
        NewsTemplate("robotics", "Роботы осваивают сложное производство",
            "На выставке показали машины, способные выполнять тонкую сборку без постоянного вмешательства оператора. Профсоюзы и промышленники увидели в новинке разные перспективы.",
            "regular", .003, 230, "Позже: производство и занятость."),
        NewsTemplate("agriculture_research", "Селекционеры представили новый сорт",
            "Авторы разработки обещают устойчивость к сложным погодным условиям. Аграрии ждут полевых испытаний, прежде чем менять планы посевов.",
            "regular", .003, 220, "Позже: урожайность и продовольствие."),
        NewsTemplate("art_festival", "Фестиваль объединил художников мира",
            "На улицах города спорят о самых неожиданных работах выставки. Организаторы надеются, что разговор о культуре переживёт сам фестиваль.",
            "flavor", .004, 170, "Атмосферное событие без игрового эффекта."),
        NewsTemplate("film_premiere", "Премьера фильма вызвала споры",
            "Зрители спорят о финале, критики — о смысле истории. Билеты на ближайшие показы раскуплены быстрее ожидаемого.",
            "flavor", .004, 160, "Атмосферное событие без игрового эффекта."),
        NewsTemplate("music_tour", "Музыканты объявили мировое турне",
            "Концертные площадки готовятся к наплыву зрителей. Поклонники уже обсуждают, какой город услышит новую программу первым.",
            "flavor", .004, 170, "Атмосферное событие без игрового эффекта."),
        NewsTemplate("polar_expedition", "Полярная экспедиция передала данные",
            "Учёные вернулись с измерениями, собранными в труднодоступных районах. Климатологи ждут полного анализа, прежде чем пересматривать прогнозы.",
            "regular", .002, 280, "Позже: климатические исследования."),
        NewsTemplate("meteor", "Яркий метеор привлёк внимание наблюдателей",
            "В разных городах обсуждают светящуюся полосу в ночном небе. Астрономы просят очевидцев прислать записи, чтобы восстановить траекторию.",
            "flavor", .004, 150, "Атмосферное событие без игрового эффекта."),
        NewsTemplate("manuscript", "Найден неизвестный научный рукописный труд",
            "Историки изучают страницы, десятилетиями лежавшие в архиве. Возможно, привычную историю одного открытия придётся написать заново.",
            "flavor", .003, 250, "Атмосферное событие без игрового эффекта."),
        NewsTemplate("education", "Международная олимпиада удивила результатами",
            "Школьники решили задачи, которые ещё недавно казались слишком сложными для соревнования. Университеты уже приглашают участников на исследовательские стажировки.",
            "flavor", .004, 170, "Позже: образование и кадровый резерв."),
        NewsTemplate("clean_water", "Инженеры показали новую систему очистки воды",
            "Установка обещает снизить стоимость очистки в удалённых районах. Эксперты напоминают, что масштабирование часто оказывается труднее первого испытания.",
            "regular", .003, 240, "Позже: инфраструктура и здоровье населения."),
    )
}

# Trigger-only concepts. Their political/economic sources do not exist yet;
# they must not be selected by the daily random-news scheduler.
FUTURE_EVENT_TEMPLATES = {
    template.key: template for template in (
        NewsTemplate("faction_protests", "Протесты политической фракции",
            "Сторонники политического движения требуют перемен.", "important", 0, 90,
            "Позже: источник — реальные протесты, требования группы, ответ правительства."),
        NewsTemplate("national_strike", "Общенациональная забастовка",
            "Работники нескольких отраслей прекратили работу.", "critical", 0, 180,
            "Позже: выпуск предприятий, переговоры, бюджет и поддержка рабочих."),
        NewsTemplate("coup_attempt", "Попытка государственного переворота",
            "Часть элит выступила против действующей власти.", "critical", 0, 365,
            "Позже: элиты, армия, легитимность и смена власти."),
        NewsTemplate("separatism", "Региональный сепаратистский кризис",
            "В одном из регионов усилились требования автономии.", "critical", 0, 365,
            "Позже: региональные группы, автономия и контроль территории."),
        NewsTemplate("refugees", "Волна беженцев",
            "Соседние страны обсуждают приём людей, покинувших зону конфликта.", "important", 0, 180,
            "Позже: население, логистика, границы и бюджет."),
        NewsTemplate("border_incident", "Инцидент на границе",
            "Стороны сообщают о столкновении у спорной границы.", "important", 0, 90,
            "Позже: пограничные силы, претензии и дипломатическая эскалация."),
        NewsTemplate("naval_blockade", "Морская блокада",
            "Торговые маршруты в районе конфликта оказались под угрозой.", "critical", 0, 180,
            "Позже: транспортные пути, доступ к рынку и снабжение."),
        NewsTemplate("debt_default", "Дефолт по государственному долгу",
            "Правительство объявило о невозможности выполнить долговые обязательства.", "critical", 0, 365,
            "Позже: кредиты, рейтинг надёжности и цены заимствования."),
        NewsTemplate("bank_panic", "Банковская паника",
            "Вкладчики массово выводят средства из банков.", "important", 0, 240,
            "Позже: банковская система, кредитование и доверие к валюте."),
        NewsTemplate("inflation", "Инфляционный скачок",
            "Население и предприятия сообщают о резком росте цен.", "important", 0, 180,
            "Позже: товары, доходы, налоги и поддержка правительства."),
        NewsTemplate("epidemic", "Распространение заболевания",
            "Медицинские службы обсуждают меры против новой вспышки болезни.", "important", 0, 365,
            "Позже: здоровье населения, производство и здравоохранение."),
        NewsTemplate("energy_shortage", "Недостаток топлива и энергии",
            "Власти предупреждают о перебоях энергоснабжения.", "important", 0, 180,
            "Позже: выпуск заводов, нефтяной рынок и бытовое потребление."),
        NewsTemplate("arms_race", "Новая гонка вооружений",
            "Соседние страны объявили о расширении военных программ.", "important", 0, 240,
            "Позже: военные расходы, угрозы, дипломатия и производство оружия."),
        NewsTemplate("diplomatic_scandal", "Дипломатический скандал",
            "Переговоры между странами осложнились после публичного заявления.", "regular", 0, 90,
            "Позже: репутация, доверие и общественное мнение."),
    )
}


@dataclass(frozen=True)
class NewsItem:
    id: int
    day: int
    key: str
    title: str
    body: str
    priority: str
    scope: str = "world"
    country_ids: tuple = ()
    context: dict = field(default_factory=dict)


class NewsSystem:
    def __init__(self, seed=0):
        self.items = deque(maxlen=300)
        self.next_id = 1
        self.rng = random.Random(seed)
        self.last_daily_day = 0
        self.last_template_day = {}
        self.trade_records = {}
        self.last_trade_news_day = {}
        self.reported_support = {}
        self.world_context = {}
        self.battle_losses = {}
        self.last_battle_loss_news_day = {}
        self.last_logistics_news_day = {}
        self.alert_states = {}
        self.notice_days = {}
        self.pending_notices = None
        self.log_path = None
        self.log_error = None
        self.log_start_time = datetime(2000, 1, 1)

    def start_log(self, path, start_time, seed=0, countries=()):
        """Reset once per new game. Each event is closed/flushed immediately."""
        self.log_path = Path(path)
        self.log_start_time = start_time
        self.log_error = None
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("w", encoding="utf-8") as stream:
                stream.write(f"HOI5 — история новостей новой партии\nСид: {seed}\nНачало: {start_time:%Y-%m-%d}\n")
                for country in countries:
                    stream.write(f"Страна {country.id}: {country.name}; правитель: {country.ruler_name or 'не указан'}\n")
                stream.write("\n")
        except OSError as error:
            self.log_error = str(error)
            warnings.warn(f"Не удалось создать журнал новостей: {error}", RuntimeWarning)

    def log_item(self, item):
        if self.log_path is None or self.log_error:
            return
        date = self.log_start_time + timedelta(days=item.day)
        try:
            with self.log_path.open("a", encoding="utf-8") as stream:
                audience = "мир" if item.scope == "world" else "страны " + ", ".join(map(str, item.country_ids))
                stream.write(f"[{date:%Y-%m-%d}] #{item.id} [{item.priority}] [{audience}] {item.key}\n")
                stream.write(f"{item.title}\n{item.body}\n\n")
        except OSError as error:
            self.log_error = str(error)
            warnings.warn(f"Не удалось записать новость: {error}", RuntimeWarning)

    def begin_notice_batch(self):
        self.pending_notices = {}

    def end_notice_batch(self):
        pending, self.pending_notices = self.pending_notices, None
        for (day, owner_id, key), entries in (pending or {}).items():
            title, body, _, _ = entries[0]
            if len(entries) > 1:
                total = sum(quantity for _, _, _, quantity in entries)
                if key == "construction_complete":
                    title = "Завершены строительные и ремонтные работы"
                title = f"{title} ({total})"
                body = "\n".join(f"{detail} ×{count}" if count > 1 else detail
                                 for detail, count in Counter(detail for _, detail, _, _ in entries).items())
            self.notice_days[owner_id, key] = day
            self.publish(day, key, title, body,
                         "important" if any(item[2] for item in entries) else "regular",
                         scope="local", country_ids=(owner_id,))

    def notice(self, day, owner, key, title, body, important=False, cooldown=0, quantity=1):
        if self.pending_notices is not None and key in BATCHED_NOTICES:
            self.pending_notices.setdefault((day, owner.id, key), []).append((title, body, important, quantity))
            return None
        token = owner.id, key
        if day - self.notice_days.get(token, -10000) < cooldown:
            return None
        self.notice_days[token] = day
        return self.publish(day, key, title, body, "important" if important else "regular",
                            scope="local", country_ids=(owner.id,))

    def alert(self, day, owner, key, active, title, body, recovery):
        token = owner.id, key
        previous = self.alert_states.get(token, False)
        self.alert_states[token] = bool(active)
        if bool(active) == previous:
            return None
        return self.notice(day, owner, key, title if active else recovery,
                           body if active else f"{owner.name}: {recovery}.", important=bool(active))

    def publish(self, day, key, title, body, priority="regular", scope="world", country_ids=(), context=None):
        if priority not in PRIORITIES or scope not in ("world", "local"):
            raise ValueError("Invalid news priority or scope")
        item = NewsItem(self.next_id, day, key, title, body, priority, scope,
                        tuple(country_ids), dict(context or {}))
        self.next_id += 1
        self.items.appendleft(item)
        self.log_item(item)
        return item

    def visible(self, viewer_id):
        return [item for item in self.items if item.scope == "world" or viewer_id in item.country_ids]

    def template_chance(self, key, context=None):
        chance = WORLD_TEMPLATES[key].daily_chance
        if key == "oil_crisis":
            context = context or self.world_context
            pressure = max(0.0, float(context.get("oil_pressure", 1.0)) - 1.0)
            chance += min(.015, pressure * .015)
            if context.get("major_oil_exporter_restricted"):
                chance += .025
        return min(1.0, chance)

    def trigger_template(self, key, day, context=None):
        template = WORLD_TEMPLATES[key]
        context = context or {}
        body = template.body
        if key == "oil_crisis" and context.get("major_oil_exporter_restricted"):
            body += " Дополнительную тревогу вызвали ограничения поставок крупным экспортёром."
        elif key == "oil_crisis" and context.get("oil_pressure", 1) > 1.25:
            body += " Последний обзор рынка показал заметный перевес спроса над предложением."
        self.last_template_day[key] = day
        return self.publish(day, key, template.title, body, template.priority)

    def advance(self, day, context=None):
        self.world_context = dict(context or self.world_context)
        for current_day in range(self.last_daily_day + 1, day + 1):
            for key, template in WORLD_TEMPLATES.items():
                if current_day - self.last_template_day.get(key, -10_000) < template.cooldown_days:
                    continue
                if self.rng.random() < self.template_chance(key, self.world_context):
                    self.trigger_template(key, current_day, self.world_context)
        self.last_daily_day = max(self.last_daily_day, day)

    def record_trade_fill(self, day, fill, resource_name):
        buyer, seller = fill.get("buyer"), fill.get("seller")
        if not buyer or not seller or buyer is seller:
            return None
        value = max(0.0, fill["amount"] * fill["price"])
        key = fill["resource"]
        previous = self.trade_records.get(key, 0.0)
        self.trade_records[key] = max(previous, value)
        if value < 5_000_000 or (previous and value < previous * 1.25):
            return None
        if day - self.last_trade_news_day.get(key, -1000) < 180:
            return None
        self.last_trade_news_day[key] = day
        return self.publish(day, "large_trade", f"Крупная сделка: {resource_name}",
            f"{seller.name} поставляет {buyer.name} {fill['amount']:,.0f} ед. товара. Стоимость сделки — ${value:,.0f}.",
            "important", country_ids=(seller.id, buyer.id))

    def report_support(self, day, player, group, label, value):
        key = player.id, group
        reference = self.reported_support.setdefault(key, .61)
        if abs(value - reference) < .10:
            return None
        direction = "выросла" if value > reference else "снизилась"
        self.reported_support[key] = value
        return self.publish(day, "support_shift",
            f"Поддержка группы «{label}» {direction} до {value:.0%}",
            f"В стране {player.name} заметно изменилось отношение группы «{label}» к правительству.",
            scope="local", country_ids=(player.id,))

    def record_battle_losses(self, day, battle, attacker_loss, defender_loss):
        """Report sustained strength losses, not an invented head count."""
        if not battle.defender:
            return
        for side, player, loss, opponent in (
            ("attacker", battle.attacker, attacker_loss, battle.defender),
            ("defender", battle.defender, defender_loss, battle.attacker),
        ):
            if not player or loss <= 0:
                continue
            key = battle.id, side
            self.battle_losses[key] = self.battle_losses.get(key, 0.0) + loss
            if self.battle_losses[key] < 12 or day - self.last_battle_loss_news_day.get(key, -1000) < 30:
                continue
            self.battle_losses[key] = 0.0
            self.last_battle_loss_news_day[key] = day
            self.publish(day, "battle_losses", f"Тяжёлые потери на фронте с {opponent.name}",
                f"Военное командование {player.name} сообщает о серьёзных потерях боеспособности соединений "
                f"в боях против {opponent.name}. Оценка положения на фронте продолжается; "
                "точные людские потери пока не установлены.",
                "important", scope="local", country_ids=(player.id,),
                context={"battle": str(battle.id), "opponent": opponent.id})

    def record_logistics_damage(self, day, owner, tile, building_key, old_health, new_health):
        names = {"supply_depot": "пункт снабжения", "fuel_storage": "топливохранилище", "port": "порт"}
        if not owner or building_key not in names or not (old_health > .5 >= new_health):
            return None
        key = owner.id, getattr(tile, "q", None), getattr(tile, "r", None), building_key
        if day - self.last_logistics_news_day.get(key, -1000) < 45:
            return None
        self.last_logistics_news_day[key] = day
        return self.publish(day, "logistics_damage", f"Повреждён {names[building_key]}",
            f"В стране {owner.name} серьёзно повреждён {names[building_key]} на участке "
            f"({getattr(tile, 'q', '?')}, {getattr(tile, 'r', '?')}). "
            "Объект работает с ограничениями; службы оценивают ущерб и готовят ремонт.",
            "important", scope="local", country_ids=(owner.id,))

    def headline_for(self, item, viewer_id, politics=None):
        if item.key not in ("war", "war_justification") or politics is None:
            return item.title
        actor_id, target_id = item.context.get("actor"), item.context.get("target")
        if actor_id is None or target_id is None or viewer_id in (actor_id, target_id):
            return item.title
        actor, target = politics.players[actor_id], politics.players[target_id]
        actor_relation = politics.relations.get(tuple(sorted((viewer_id, actor_id))))
        target_relation = politics.relations.get(tuple(sorted((viewer_id, target_id))))
        if item.key == "war_justification":
            if actor_relation and "alliance" in actor_relation.treaties:
                return f"Наш союзник {actor.name} готовит цель войны против {target.name}"
            if target_relation and "alliance" in target_relation.treaties:
                return f"Страна {actor.name} готовит цель войны против нашего союзника {target.name}"
            return item.title
        if actor_relation and "alliance" in actor_relation.treaties:
            return f"Наш союзник {actor.name} объявил войну стране {target.name}"
        if target_relation and "alliance" in target_relation.treaties:
            return f"На нашего союзника {target.name} напала страна {actor.name}"
        actor_distance = politics.rules.ideology_distance(politics.players[viewer_id], actor)
        target_distance = politics.rules.ideology_distance(politics.players[viewer_id], target)
        if target_distance + .12 < actor_distance:
            return f"Близкая нам по взглядам страна {target.name} оказалась в войне"
        return item.title

    def body_for(self, item, viewer_id, politics=None):
        if item.key not in ("war", "war_justification") or politics is None:
            return item.body
        actor_id, target_id = item.context.get("actor"), item.context.get("target")
        if actor_id not in politics.players or target_id not in politics.players:
            return item.body
        actor, target = politics.players[actor_id], politics.players[target_id]
        if viewer_id not in politics.players:
            return item.body
        if viewer_id == actor_id:
            return item.body + (" Наша страна готовит цель войны; объявление войны потребует отдельного решения."
                if item.key == "war_justification" else " Наша страна официально находится в состоянии войны.")
        if viewer_id == target_id:
            return item.body + (" Заявление направлено против нашей страны. Война ещё не объявлена."
                if item.key == "war_justification" else " Нашей стране объявлена война.")
        actor_relation = politics.relations.get(tuple(sorted((viewer_id, actor_id))))
        target_relation = politics.relations.get(tuple(sorted((viewer_id, target_id))))
        if actor_relation and "alliance" in actor_relation.treaties:
            if item.key == "war_justification":
                return (item.body + f" Для нашего союзника {actor.name} это уже не просто обмен дипломатическими заявлениями: "
                    f"решение о подготовке принято. Наш союзник готовит цель войны против {target.name}.")
            return (item.body + f" Наш союзник {actor.name} теперь участвует в открытом конфликте. "
                "Наше правительство следит за развитием обстановки; союз сам по себе не означает автоматического вступления в войну.")
        if target_relation and "alliance" in target_relation.treaties:
            if item.key == "war_justification":
                return (item.body + f" Заявления прозвучали в адрес нашего союзника {target.name}. "
                    "Дипломаты внимательно следят за обстановкой: угроза войны стала заметно серьёзнее.")
            return (item.body + f" Военные действия направлены против нашего союзника {target.name}. "
                "В союзных столицах обсуждают дальнейшие шаги, но автоматического вступления в войну договор не предусматривает.")
        actor_distance = politics.rules.ideology_distance(politics.players[viewer_id], actor)
        target_distance = politics.rules.ideology_distance(politics.players[viewer_id], target)
        if item.key == "war" and target_distance + .12 < actor_distance:
            return (item.body + f" Общественные настроения в {target.name} ближе к нашим, чем настроения в стране {actor.name}. "
                f"Близкая нам по взглядам страна {target.name} оказалась в войне.")
        return item.body
