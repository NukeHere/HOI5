"""Political state and deterministic actions, independent of rendering."""

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import math
from news_system import NewsSystem


GROUPS = {"population": "Население", "smb": "Малый и средний бизнес", "large": "Крупный бизнес"}
GROUP_WEIGHTS = {"population": 0.85, "smb": 0.12, "large": 0.03}
SOCIAL_GROUPS = {"workers": "Рабочие (пролетариат)", "farmers": "Сельские жители", "middle": "Средний класс", "aristocracy": "Аристократия"}
SOCIAL_WEIGHTS = {"workers": 0.45, "farmers": 0.25, "middle": 0.28, "aristocracy": 0.02}
FACTIONS = {"nationalists": "Националисты", "socialists": "Социалисты", "liberals": "Либералы", "conservatives": "Консерваторы"}
SUPPORT_GROUPS = {**GROUPS, **SOCIAL_GROUPS, **FACTIONS}
TREATIES = {"trade": "Торговый договор", "peace": "Мирный договор", "alliance": "Союз",
            "nonaggression": "Пакт о ненападении", "transit": "Разрешение на проход войск"}
OFFERS = {**TREATIES, "loan": "Кредит"}
PROGRAM_TERMS = {"week": ("Неделя", 7), "month": ("Месяц: 30 дней", 30),
                 "year": ("Год: 365 дней", 365), "ongoing": ("До отмены", None)}


@dataclass
class PoliticalState:
    support: dict = field(default_factory=lambda: dict.fromkeys(SUPPORT_GROUPS, 0.61))
    social_shares: dict = field(default_factory=lambda: dict(SOCIAL_WEIGHTS))
    faction_shares: dict = field(default_factory=lambda: dict.fromkeys(FACTIONS, 0.25))
    taxes: dict = field(default_factory=lambda: dict.fromkeys(GROUPS, 0))
    programs: dict = field(default_factory=dict)
    program_costs: dict = field(default_factory=dict)
    program_funding: dict = field(default_factory=dict)
    program_funded_hours: dict = field(default_factory=dict)
    living_conditions: dict = field(default_factory=lambda: {
        "food": 1.0, "goods": 1.0, "food_price": 1.0, "goods_price": 1.0})
    unrest_active: bool = False
    political_capital: float = 50.0
    reputation: float = 0.5
    reliability: float = 0.5
    faction_patience: dict = field(default_factory=lambda: dict.fromkeys(FACTIONS, 0.7))
    faction_radicalization: dict = field(default_factory=lambda: dict.fromkeys(FACTIONS, 0.0))
    crisis_flags: set = field(default_factory=set)
    cooldowns: dict = field(default_factory=dict)
    export_restricted: bool = False
    export_limit: float = 1.0
    external_access: bool = True
    history: deque = field(default_factory=lambda: deque(maxlen=40))

    @property
    def government_support(self):
        social = sum(self.support[key] * share for key, share in self.social_shares.items())
        factions = sum(self.support[key] * share for key, share in self.faction_shares.items())
        population = 0.5 * self.support["population"] + 0.3 * social + 0.2 * factions
        return population * GROUP_WEIGHTS["population"] + sum(self.support[key] * GROUP_WEIGHTS[key] for key in ("smb", "large"))

    def tax_multiplier(self, group):
        return 1.0 + self.taxes[group] * 0.1

    @property
    def export_capacity_factor(self):
        return self.export_limit if self.export_limit != 1.0 else (0.5 if self.export_restricted else 1.0)


@dataclass
class BilateralRelation:
    opinions: dict = field(default_factory=dict)
    trust: float = 0.5
    at_war: bool = False
    treaties: set = field(default_factory=set)
    embargoes: set = field(default_factory=set)
    truce_until: int = 0
    transit_grants: set = field(default_factory=set)
    grievances: dict = field(default_factory=dict)
    fear: dict = field(default_factory=dict)
    respect: dict = field(default_factory=dict)
    crisis_level: float = 0.0
    war_started_day: int = 0


@dataclass(frozen=True)
class PoliticalAction:
    key: str
    label: str
    domestic: bool
    description: str
    cost: float = 0
    cooldown: int = 7


ACTIONS = {
    a.key: a for a in (
        PoliticalAction("mission", "Дипломатическая миссия", False, "Переговоры об улучшении отношений.", 1_000_000, 30),
        PoliticalAction("aid", "Безвозмездная помощь", False, "Выбранная сумма перечисляется сразу, без возврата.", cooldown=30),
        PoliticalAction("loan", "Предложить кредит", False, "Деньги перечисляются после согласия; условия фиксируются при отправке предложения.", cooldown=30),
        PoliticalAction("embargo", "Ввести / снять эмбарго", False, "Блокирует прямые сделки в обоих направлениях; внешние рынки сохраняются."),
        PoliticalAction("trade", "Предложить торговый договор", False, "Договор даёт приоритет сопоставления заявок."),
        PoliticalAction("alliance", "Предложить союз", False, "Запрет взаимных атак и приоритет торговли; без автоматического вступления в войны."),
        PoliticalAction("nonaggression", "Предложить пакт о ненападении", False, "Обе стороны обязуются не объявлять войну, пока пакт действует."),
        PoliticalAction("transit", "Запросить проход войск", False, "Разрешает проход через территорию другой страны без смены владельца."),
        PoliticalAction("revoke_transit", "Отозвать проход войск", False, "Отзывает выданное другой стране разрешение на проход."),
        PoliticalAction("justify", "Подготовить цель войны", False, "Начинает 30-дневное обоснование войны; требует политической поддержки.", 2_000_000, 30),
        PoliticalAction("cancel_justify", "Отменить подготовку войны", False, "Снижает дипломатическую напряжённость; потраченные ресурсы не возвращаются."),
        PoliticalAction("peace", "Предложить мир", False, "Прекращение войны по текущим границам с временным запретом новой войны."),
        PoliticalAction("war", "Объявить войну", False, "Требует подготовленной цели войны, поддержки общества и политического капитала.", cooldown=30),
        PoliticalAction("break", "Расторгнуть договоры", False, "Прекращает союз и торговый договор; срок перемирия сохраняется."),
        PoliticalAction("exports", "Ограничить / открыть экспорт", True, "Лимит экспорта уменьшается вдвое. Цены реагируют на изменение рыночных заявок."),
        PoliticalAction("external", "Закрыть / открыть внешний рынок", True, "Меняет доступ к внешнему рынку. Прямые сделки со странами сохраняются."),
    )
}
for _group, _label in GROUPS.items():
    for _delta, _verb in ((-1, "Снизить"), (1, "Повысить")):
        _key = f"tax:{_group}:{_delta}"
        ACTIONS[_key] = PoliticalAction(_key, f"{_verb} налог: {_label.lower()}", True,
            "Изменение налоговых поступлений группы на 10% базового уровня. Отношение меняется постепенно.", cooldown=30)
for _group, _label in SUPPORT_GROUPS.items():
    _key = f"support:{_group}"
    _description = ("Финансирование политического представительства интересов фракции. Повышает её поддержку правительства постепенно."
                    if _group in FACTIONS else "Бюджетная программа в интересах выбранной социальной или деловой группы. Повышает её поддержку правительства постепенно.")
    ACTIONS[_key] = PoliticalAction(_key, f"Поддержка: {_label.lower()}", True,
        _description, cooldown=0)
    _key = f"stop:{_group}"
    ACTIONS[_key] = PoliticalAction(_key, f"Завершить поддержку: {_label.lower()}", True,
        "Прекращает регулярные расходы; поддержка группы постепенно меняется.", cooldown=0)


@dataclass
class GovernmentLoan:
    lender: int
    borrower: int
    original: float
    principal: float
    next_due: int
    annual_rate: float = 0.05
    term_months: int = 12
    interest_due: float = 0.0
    principal_due: float = 0.0
    payments_due: int = 0


@dataclass(frozen=True)
class ActionQuote:
    cost: float
    opinion_delta: float
    trust_delta: float
    cooldown_days: int
    program_days: int | None = None
    program_monthly_cost: float = 1_000_000
    loan_annual_rate: float = 0.05
    loan_term_months: int = 12
    response_days: int = 3
    truce_days: int = 30
    political_cost: float = 0.0


class PoliticalRules:
    """Replaceable rule boundary; current tuning is intentionally fixed."""

    def political_cost(self, system, actor, action):
        if action.key.startswith(("tax:", "support:")):
            return 2.0
        return {"justify": 15.0, "war": 20.0, "break": 8.0, "embargo": 3.0,
                "external": 2.0, "exports": 2.0, "alliance": 3.0,
                "nonaggression": 2.0, "transit": 1.0, "mission": 1.0}.get(action.key, 0.0)

    def quote(self, system, actor, target, action, amount):
        opinion = {"mission": 8, "aid": 5, "embargo": -10, "justify": -10, "war": -60, "break": -20}.get(action.key, 0)
        trust = {"mission": 0.04, "justify": -0.02, "break": -0.2}.get(action.key, 0)
        if action.key == "war":
            trust = -system.relation(actor.id, target.id).trust
        if action.key == "embargo" and actor.id in system.relation(actor.id, target.id).embargoes:
            opinion = 0
        cost = amount if action.key == "aid" and amount is not None else action.cost
        return ActionQuote(cost, opinion, trust, action.cooldown,
                           political_cost=self.political_cost(system, actor, action))

    def accepts(self, system, offer):
        a, b, key, _ = offer
        relation = system.relation(a, b)
        target = system.players[b]
        if key == "peace":
            return (target.budget < 0 or relation.opinions[b] >= -20
                    or system.day - relation.war_started_day >= 90 and getattr(target, "war_support", .5) < .5)
        threshold = 30 if key == "alliance" else 0 if key == "transit" else -10
        threshold += relation.grievances[b] * .3 - relation.respect[b] * .2
        threshold += 15 * self.ideology_distance(system.players[a], target)
        threshold += relation.crisis_level * .2
        if relation.opinions[b] < threshold or relation.trust < 0.35:
            return False
        proposer = system.players[a]
        if key in ("alliance", "nonaggression", "transit") and (proposer.politics.reliability < .25
                                                                     or proposer.politics.reputation < .2
                                                                     or relation.grievances[b] > 40):
            return False
        if key == "loan":
            amount = system.offer_amounts[offer]
            quote = system.offer_quotes[offer]
            payment = amount / quote.loan_term_months + amount * quote.loan_annual_rate / 12
            return target.budget < amount * 4 and target.monthly_balance >= payment
        return True

    def support_target(self, system, player, group):
        politics = player.politics
        tax_group = group if group in GROUPS else "population"
        target = 0.61 - politics.taxes[tax_group] * 0.04
        target += self.program_support_effect(player, group)
        if group not in GROUPS and "population" in politics.programs:
            target += self.program_support_effect(player, "population") * 0.5
        target -= 0.12 if player.budget < 0 else 0
        target -= 0.03 if group in ("smb", "large") and politics.export_restricted else 0
        living = politics.living_conditions
        shortage = max(0.0, 1.0 - min(living["food"], living["goods"]))
        price_pressure = (max(0.0, living["food_price"] - 1) * 0.6
                          + max(0.0, living["goods_price"] - 1) * 0.4)
        exposure = 1.0 if group in ("population", "workers", "farmers", "socialists") else 0.5
        target -= exposure * (0.18 * shortage + 0.025 * min(2.0, price_pressure))
        wars = sum(relation.at_war for pair, relation in system.relations.items() if player.id in pair)
        if wars:
            if group == "nationalists":
                target += 0.025 * min(2, wars)
            elif group in ("population", "workers", "socialists", "liberals"):
                target -= 0.02 * min(2, wars) * (1 - max(0, min(1, getattr(player, "war_support", .5))))
        return max(0, min(1, target))

    def war_readiness(self, player):
        state = player.politics
        return (state.government_support >= 0.45 and getattr(player, "legitimacy", .61) >= .45
                and getattr(player, "war_support", .5) >= .35 and state.political_capital >= 20
                and max(state.faction_radicalization[k] for k in ("liberals", "socialists")) < .7)

    def faction_demand(self, player, faction, at_war=False):
        state = player.politics
        if faction == "nationalists":
            return "Поддержка обороны не ниже 50%", at_war or getattr(player, "war_support", .5) >= .5
        if faction == "socialists":
            return "Социальная программа или сниженный налог населения", (any(group in state.programs for group in
                ("population", "workers", "socialists")) or state.taxes["population"] < 0)
        if faction == "liberals":
            return "Открытый внешний рынок и отсутствие войны", state.external_access and not at_war
        return "Положительный бюджет и легитимность не ниже 50%", (player.budget >= 0
            and getattr(player, "legitimacy", .61) >= .5)

    def ideology_distance(self, first, second):
        def profile(player):
            weights = {key: player.politics.faction_shares[key] * player.politics.support[key] for key in FACTIONS}
            total = sum(weights.values()) or 1
            return {key: value / total for key, value in weights.items()}
        a, b = profile(first), profile(second)
        return sum(abs(a[key] - b[key]) for key in FACTIONS) / 2

    def institutional_targets(self, player):
        politics = player.politics
        living = politics.living_conditions
        shortage = max(0, 1 - min(living["food"], living["goods"]))
        support_gap = politics.government_support - 0.61
        stability = max(0, min(1, 0.72 + 0.7 * support_gap - 0.25 * shortage))
        legitimacy = max(0, min(1, 0.61 + 0.4 * support_gap - 0.1 * shortage))
        return stability, legitimacy

    def company_tax_yield_factor(self, player):
        # Instability disrupts taxable activity; unrest adds a separate shock.
        stability = max(0, min(1, getattr(player, "stability", 0.72)))
        return max(0.65, min(1.05, 1 + 0.5 * (stability - 0.72)))

    def program_support_effect(self, player, group, monthly_cost=None):
        politics = player.politics
        if group not in politics.programs and monthly_cost is None:
            return 0.0
        relative_size = 1.0
        if group in SOCIAL_WEIGHTS:
            relative_size = politics.social_shares[group] / SOCIAL_WEIGHTS[group]
        elif group in FACTIONS:
            relative_size = politics.faction_shares[group] / 0.25
        need = max(1_000_000, (player.population or 0) * 0.1 * relative_size)
        intensity = min(1.0, (politics.program_costs.get(group, 0) if monthly_cost is None else monthly_cost) / need)
        funding = politics.program_funding.get(group, 1.0) if monthly_cost is None else 1.0
        legitimacy = max(0, min(1, getattr(player, "legitimacy", 0.61)))
        supply = max(0, min(1, (getattr(player, "supply_summary", None) or {}).get("average", 1)))
        return 0.04 * intensity * funding * (0.5 + legitimacy * 0.5) * supply

    def daily_support_change(self, current, target):
        # A six-month response time prevents short, cheap opinion spikes.
        return max(-0.0005, min(0.0005, (target - current) * -math.expm1(-1 / 180)))


class PoliticsSystem:
    def __init__(self, players, rules=None, start_time=None, news_seed=0):
        self.rules = rules or PoliticalRules()
        self.start_time = start_time or datetime(2000, 1, 1)
        self.players = {player.id: player for player in players}
        self.relations = {}
        self.pending = []
        self.offer_amounts = {}
        self.offer_quotes = {}
        self.loans = []
        self.war_goals = {}
        self.news = NewsSystem(news_seed)
        self.offer_evaluator = None
        for player in players:
            self.news.reported_support.update({(player.id, group): value
                for group, value in player.politics.support.items()})
        self.day = 0
        self.hours = 0.0
        self.revision = 0

    def date_text(self, day):
        return (self.start_time + timedelta(days=day)).strftime("%Y-%m-%d")

    def relation(self, a, b):
        key = tuple(sorted((a, b)))
        if a == b or a not in self.players or b not in self.players:
            raise ValueError("Invalid country pair")
        if key not in self.relations:
            self.relations[key] = BilateralRelation(opinions={a: 0.0, b: 0.0},
                grievances={a: 0.0, b: 0.0}, fear={a: 0.0, b: 0.0}, respect={a: 0.0, b: 0.0})
        return self.relations[key]

    def can_transit(self, guest_id, owner_id):
        if guest_id == owner_id:
            return True
        relation = self.relation(guest_id, owner_id)
        return (not relation.at_war and ("alliance" in relation.treaties
                or (owner_id, guest_id) in relation.transit_grants))

    def hostile(self, a, b):
        return a != b and self.relation(a, b).at_war

    def trade_allowed(self, a, b):
        if a == b:
            return False
        relation = self.relation(a, b)
        return not relation.at_war and not relation.embargoes

    def trade_priority(self, a, b):
        relation = self.relation(a, b)
        return 2 * ("alliance" in relation.treaties) + ("trade" in relation.treaties)

    @staticmethod
    def program_expenses(player):
        return sum(player.politics.program_costs.get(group, 0) for group in player.politics.programs)

    def monthly_debt_flows(self, player_id):
        incoming = outgoing = 0.0
        for loan in self.loans:
            payment = min(loan.principal, loan.original / loan.term_months) + loan.principal * loan.annual_rate / 12
            if loan.borrower == player_id:
                outgoing += payment
            if loan.lender == player_id:
                incoming += payment
        return incoming, outgoing

    def quote(self, actor_id, target_id, key, amount=None, program_term="ongoing"):
        quote = self.rules.quote(self, self.players[actor_id], self.players[target_id], ACTIONS[key], amount)
        if key.startswith("support:"):
            quote = replace(quote, program_days=PROGRAM_TERMS[program_term][1])
        return quote

    def reason(self, actor_id, target_id, key, amount=None, program_term="ongoing"):
        action = ACTIONS.get(key)
        if not action or actor_id not in self.players or target_id not in self.players:
            return "Неизвестное действие или государство"
        if action.domestic != (actor_id == target_id):
            return "Действие недоступно для этой страны"
        actor = self.players[actor_id]
        if key.startswith("support:") and (not isinstance(program_term, str) or program_term not in PROGRAM_TERMS):
            return "Выберите срок программы"
        if key == "exports" and amount is not None:
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or not 0 <= amount <= 100:
                return "Выберите лимит экспорта от 0 до 100%"
            if abs(actor.politics.export_capacity_factor * 100 - amount) < 1e-6:
                return "Лимит не изменён"
        if key in ("aid", "loan"):
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or not 1_000 <= amount <= 1_000_000_000_000:
                return "Введите сумму от 1 тыс. до 1 трлн"
            if actor.budget < amount:
                return "Недостаточно средств для выбранной суммы"
        quote = self.quote(actor_id, target_id, key, amount, program_term)
        if not actor.tiles or not self.players[target_id].tiles:
            return "Государство не контролирует территорию"
        cooldown_key = (key if not key.startswith("tax:") else key.rsplit(":", 1)[0], target_id)
        if actor.politics.cooldowns.get(cooldown_key, 0) > self.day:
            return f"Доступно с {self.date_text(actor.politics.cooldowns[cooldown_key])}"
        if (quote.cost > 0 and actor.budget < quote.cost) or (key.startswith("support:") and actor.budget < quote.cost + quote.program_monthly_cost):
            return "Недостаточно средств"
        if actor.politics.political_capital < quote.political_cost:
            return f"Недостаточно политического капитала (нужно {quote.political_cost:g})"
        if key.startswith("tax:"):
            _, group, delta = key.split(":")
            if not -2 <= actor.politics.taxes[group] + int(delta) <= 2:
                return "Достигнут предел ставки"
        if key.startswith("support:") and key.split(":")[1] in actor.politics.programs:
            return "Программа уже действует"
        if key.startswith("stop:") and key.split(":")[1] not in actor.politics.programs:
            return "Программа не действует"
        if not action.domestic:
            relation = self.relation(actor_id, target_id)
            if key in ("mission", "aid", "loan", "trade", "alliance", "nonaggression", "transit", "justify") and relation.at_war:
                return "Сначала заключите мир"
            if key in OFFERS:
                if key in relation.treaties:
                    return "Договор уже действует"
                if key == "transit" and self.can_transit(actor_id, target_id):
                    return "Проход уже разрешён"
                if any({p[0], p[1]} == {actor_id, target_id} and p[2] == key for p in self.pending):
                    return "Предложение ожидает ответа"
                if key == "peace" and not relation.at_war:
                    return "Войны нет"
                if key in ("trade", "alliance", "transit") and relation.embargoes:
                    return "Сначала снимите эмбарго"
            if key in ("war", "justify") and (relation.at_war or "alliance" in relation.treaties
                                                  or "nonaggression" in relation.treaties or self.day < relation.truce_until):
                return "Война уже идёт, действует пакт, союз или перемирие"
            if key == "justify":
                if (actor_id, target_id) in self.war_goals:
                    return "Цель войны уже готовится или подготовлена"
                if actor.politics.government_support < .45 or getattr(actor, "legitimacy", .61) < .45:
                    return "Недостаточно поддержки власти или легитимности"
            if key == "cancel_justify" and (actor_id, target_id) not in self.war_goals:
                return "Нет подготовки войны против этой страны"
            if key == "war":
                goal = self.war_goals.get((actor_id, target_id))
                if goal is None:
                    return "Сначала подготовьте цель войны"
                if self.day < goal:
                    return f"Цель войны будет готова {self.date_text(goal)}"
                if self.day > goal + 180:
                    return "Срок подготовленной цели войны истёк"
                if not self.rules.war_readiness(actor):
                    return "Нужно 45% поддержки, 45% легитимности, 35% поддержки войны, 20 политического капитала и отсутствие сильного сопротивления фракций"
            if key == "revoke_transit" and (actor_id, target_id) not in relation.transit_grants:
                return "Вы не выдавали этой стране разрешение на проход"
            if key == "break" and not relation.treaties:
                return "Нет действующих договоров"
        return ""

    def record(self, player, message):
        player.politics.history.appendleft((self.day, message))

    def publish_action_news(self, actor, target, key):
        leader = getattr(actor, "leader_name", None)
        speaker = f"глава государства {leader}" if leader else f"правительство страны {actor.name}"
        declared = "объявил" if leader else "объявило"
        spoke = "выступил" if leader else "выступило"
        if key.startswith("support:"):
            group = key.split(":")[1]
            self.news.publish(self.day, "program_start", f"Начата программа: {SUPPORT_GROUPS[group]}",
                f"Правительство страны {actor.name} начало поддержку группы «{SUPPORT_GROUPS[group]}».",
                scope="local", country_ids=(actor.id,))
        elif key.startswith("stop:"):
            group = key.split(":")[1]
            self.news.publish(self.day, "program_stop", f"Поддержка прекращена: {SUPPORT_GROUPS[group]}",
                f"Программа поддержки группы «{SUPPORT_GROUPS[group]}» в стране {actor.name} завершена.",
                scope="local", country_ids=(actor.id,))
        elif key.startswith("tax:") or key in ("exports", "external"):
            decision = (f"Лимит экспорта: {actor.politics.export_capacity_factor:.0%}" if key == "exports" else
                        "Внешний рынок открыт" if key == "external" and actor.politics.external_access else
                        "Внешний рынок закрыт" if key == "external" else ACTIONS[key].label)
            self.news.publish(self.day, "domestic_decision", f"{actor.name}: {decision}",
                f"Правительство страны {actor.name} изменило экономическую политику.",
                scope="local", country_ids=(actor.id,))
        elif key == "war":
            self.news.publish(self.day, "war", f"{actor.name} объявила войну стране {target.name}",
                f"После недель напряжённых заявлений {speaker} {declared} о начале войны против {target.name}. "
                "Дипломатические каналы ещё работают, однако отношения сторон перешли в состояние войны. На что пойдут правительства дальше, пока неизвестно.",
                "critical", context={"actor": actor.id, "target": target.id})
        elif key == "justify":
            self.news.publish(self.day, "war_justification", f"{actor.name} готовится к войне с {target.name}",
                f"{speaker[:1].upper() + speaker[1:]} {spoke} с резким заявлением в адрес {target.name}. "
                "Действия другой стороны в заявлении названы провокационными; власти предупреждают, что могут принять решительные меры. "
                "Это позиция одной из сторон конфликта: боевые действия пока не начались.",
                "important", context={"actor": actor.id, "target": target.id})
        elif key == "cancel_justify":
            self.news.publish(self.day, "war_deescalation", f"{actor.name} прекращает подготовку войны",
                f"Подготовка войны против страны {target.name} отменена. Напряжённость снизилась.", "important")
        elif key in ("embargo", "break"):
            action = "ввела эмбарго против" if key == "embargo" and actor.id in self.relation(actor.id, target.id).embargoes else (
                "сняла эмбарго со" if key == "embargo" else "разорвала договоры со")
            self.news.publish(self.day, key, f"{actor.name} {action} страны {target.name}",
                "Дипломатические и торговые отношения сторон изменились.", "important")
        elif key in ("revoke_transit", "mission", "aid"):
            self.news.publish(self.day, key, f"{actor.name}: {ACTIONS[key].label}",
                f"Решение касается отношений со страной {target.name}.", scope="local",
                country_ids=(actor.id, target.id))

    def execute(self, actor_id, target_id, key, amount=None, program_term="ongoing"):
        reason = self.reason(actor_id, target_id, key, amount, program_term)
        if reason:
            return False, reason
        actor = self.players[actor_id]
        action = ACTIONS[key]
        quote = self.quote(actor_id, target_id, key, amount, program_term)
        actor.budget -= quote.cost
        actor.politics.political_capital -= quote.political_cost
        cooldown_key = (key if not key.startswith("tax:") else key.rsplit(":", 1)[0], target_id)
        actor.politics.cooldowns[cooldown_key] = self.day + quote.cooldown_days
        if key.startswith("tax:"):
            _, group, delta = key.split(":")
            actor.politics.taxes[group] += int(delta)
        elif key.startswith("support:"):
            group = key.split(":")[1]
            actor.politics.programs[group] = None if quote.program_days is None else self.day + self.hours / 24 + quote.program_days
            actor.politics.program_costs[group] = quote.program_monthly_cost
            actor.politics.program_funding[group] = 1.0
            actor.politics.program_funded_hours[group] = 0.0
        elif key.startswith("stop:"):
            group = key.split(":")[1]
            del actor.politics.programs[group]
            actor.politics.program_costs.pop(group, None)
            actor.politics.program_funding.pop(group, None)
            actor.politics.program_funded_hours.pop(group, None)
        elif key == "exports":
            limit = amount / 100 if amount is not None else (1.0 if actor.politics.export_restricted else 0.5)
            actor.politics.export_limit = limit
            actor.politics.export_restricted = limit < 1.0
        elif key == "external":
            actor.politics.external_access = not actor.politics.external_access
        else:
            target = self.players[target_id]
            relation = self.relation(actor_id, target_id)
            if key in OFFERS:
                offer = (actor_id, target_id, key, self.day + quote.response_days)
                self.pending.append(offer)
                self.offer_quotes[offer] = quote
                self.news.notice(self.day, target, "offer_received", f"Предложение от {actor.name}",
                    f"{actor.name} предлагает: {OFFERS[key]}. Ответ доступен в дипломатии.", important=True)
                if key == "loan":
                    self.offer_amounts[offer] = float(amount)
            elif key == "aid":
                target.budget += amount
            elif key == "embargo":
                if actor_id in relation.embargoes:
                    relation.embargoes.remove(actor_id)
                else:
                    relation.embargoes.add(actor_id)
            elif key == "justify":
                self.war_goals[(actor_id, target_id)] = self.day + 30
                relation.crisis_level = max(relation.crisis_level, 25)
                relation.grievances[target_id] = min(100, relation.grievances[target_id] + 10)
            elif key == "cancel_justify":
                del self.war_goals[(actor_id, target_id)]
                relation.crisis_level = 0 if (target_id, actor_id) not in self.war_goals else 25
            elif key == "revoke_transit":
                relation.transit_grants.remove((actor_id, target_id))
            elif key == "war":
                actor.politics.reputation = max(0, actor.politics.reputation - .05)
                actor.politics.reliability = max(0, actor.politics.reliability - .02)
                self.war_goals.pop((actor_id, target_id), None)
                self.war_goals.pop((target_id, actor_id), None)
                relation.at_war = True
                relation.war_started_day = self.day
                relation.crisis_level = 100
                relation.treaties.clear()
                relation.transit_grants.clear()
                relation.grievances[target_id] = min(100, relation.grievances[target_id] + 50)
                relation.fear[target_id] = min(100, relation.fear[target_id] + 20)
                actor.politics.faction_patience["nationalists"] = min(1, actor.politics.faction_patience["nationalists"] + .04)
                for faction in ("liberals", "socialists"):
                    actor.politics.faction_patience[faction] = max(0, actor.politics.faction_patience[faction] - .06)
            elif key == "break":
                relation.treaties.clear()
                relation.transit_grants.clear()
                actor.politics.reliability = max(0, actor.politics.reliability - .04)
            if key not in OFFERS:
                relation.trust = max(0, min(1, relation.trust + quote.trust_delta))
                relation.opinions[target_id] = max(-100, min(100, relation.opinions[target_id] + quote.opinion_delta))
                if key == "embargo" and actor_id in relation.embargoes:
                    relation.grievances[target_id] = min(100, relation.grievances[target_id] + 10)
                if key in ("mission", "aid"):
                    relation.respect[target_id] = min(100, relation.respect[target_id] + (2 if key == "mission" else 4))
                    relation.grievances[target_id] = max(0, relation.grievances[target_id] - 2)
            self.record(target, f"{actor.name}: {action.label}" + (f" ({amount:,.0f})" if key in ("aid", "loan") else ""))
        event_label = f"Лимит экспорта: {actor.politics.export_capacity_factor:.0%}" if key == "exports" else action.label
        self.record(actor, event_label + (f" ({amount:,.0f})" if key in ("aid", "loan") else ""))
        self.publish_action_news(actor, self.players[target_id], key)
        self.revision += 1
        return True, "Решение принято"

    def resolve_offer(self, offer, accept):
        if offer not in self.pending:
            return False
        a, b, key, _ = offer
        relation = self.relation(a, b)
        valid = (key == "peace" and relation.at_war) or (key != "peace" and not relation.at_war and (key == "loan" or not relation.embargoes))
        accept = accept and valid and bool(self.players[a].tiles and self.players[b].tiles)
        amount = self.offer_amounts.get(offer, 0)
        if key == "loan":
            accept = accept and amount > 0 and self.players[a].budget >= amount
        if accept:
            quote = self.offer_quotes[offer]
            relation.trust = max(0, min(1, relation.trust + quote.trust_delta))
            relation.opinions[b] = max(-100, min(100, relation.opinions[b] + quote.opinion_delta))
            if key == "loan":
                self.players[a].budget -= amount
                self.players[b].budget += amount
                self.loans.append(GovernmentLoan(a, b, amount, amount, self.day + 30,
                                                quote.loan_annual_rate, quote.loan_term_months))
            elif key == "transit":
                relation.transit_grants.add((b, a))
            else:
                relation.treaties.add(key)
                if key in ("alliance", "nonaggression"):
                    self.war_goals.pop((a, b), None)
                    self.war_goals.pop((b, a), None)
                    relation.crisis_level = 0
            if key in ("trade", "alliance", "nonaggression", "transit"):
                for player_id in (a, b):
                    state = self.players[player_id].politics
                    state.reliability = min(1, state.reliability + .01)
            if key == "peace":
                relation.at_war = False
                relation.crisis_level = 0
                self.war_goals.pop((a, b), None)
                self.war_goals.pop((b, a), None)
                relation.truce_until = self.day + quote.truce_days
        self.pending.remove(offer)
        self.offer_amounts.pop(offer, None)
        self.offer_quotes.pop(offer, None)
        for player_id in (a, b):
            self.record(self.players[player_id], f"{OFFERS[key]}: {'принят' if accept else 'отклонён'}")
        if accept:
            actor, target = self.players[a], self.players[b]
            if key in ("peace", "alliance", "nonaggression", "trade"):
                self.news.publish(self.day, key, f"{actor.name} и {target.name}: {OFFERS[key].lower()}",
                    f"Государства {actor.name} и {target.name} достигли соглашения.",
                    "critical" if key == "peace" else "important", context={"actor": a, "target": b})
            else:
                self.news.publish(self.day, key, f"Соглашение: {OFFERS[key].lower()}",
                    f"Страны {actor.name} и {target.name} согласовали условия.",
                    scope="local", country_ids=(a, b))
        else:
            self.news.notice(self.day, self.players[a], "offer_rejected", "Дипломатическое предложение отклонено",
                f"{self.players[b].name}: предложение «{OFFERS[key]}» не принято либо утратило силу.")
        self.revision += 1
        return accept

    def service_loans(self):
        for loan in list(self.loans):
            lender, borrower = self.players[loan.lender], self.players[loan.borrower]
            if self.day >= loan.next_due:
                loan.interest_due += loan.principal * loan.annual_rate / 12
                loan.payments_due += 1
                loan.principal_due = min(loan.principal, loan.principal_due + loan.original / loan.term_months)
                loan.next_due += 30
                self.record(borrower, f"Платёж по кредиту: {loan.principal_due + loan.interest_due:,.0f}")
            due = loan.principal_due + loan.interest_due
            payment = min(max(0, borrower.budget), due)
            borrower.budget -= payment
            lender.budget += payment
            interest_paid = min(payment, loan.interest_due)
            loan.interest_due -= interest_paid
            principal_paid = payment - interest_paid
            loan.principal -= principal_paid
            loan.principal_due = max(0, loan.principal_due - principal_paid)
            self.news.alert(self.day, borrower, f"loan_arrears:{loan.lender}",
                any(item.principal_due + item.interest_due > 1e-6 for item in self.loans
                    if item.borrower == loan.borrower and item.lender == loan.lender),
                "Не хватает средств на платёж по кредиту",
                f"Обязательства перед {lender.name} оплачены не полностью. Проверьте бюджет и график выплат.",
                "Просроченные платежи по кредиту погашены")
            if loan.principal <= 1e-6 and loan.interest_due <= 1e-6:
                self.loans.remove(loan)
                for player in (lender, borrower):
                    self.news.notice(self.day, player, "loan_repaid", "Кредит полностью погашен",
                        f"Расчёты между {lender.name} и {borrower.name} по кредиту завершены.")
                for player in (lender, borrower):
                    self.record(player, "Кредит полностью погашен")

    def advance(self, hours):
        remaining = max(0.0, hours)
        while remaining > 1e-9:
            step = min(24 - self.hours, remaining)
            now = self.day + self.hours / 24
            for player in self.players.values():
                state = player.politics
                active_hours = {group: step if end is None else min(step, max(0, (end - now) * 24))
                                for group, end in state.programs.items()}
                required = sum(state.program_costs.get(group, 0) * span / 720 for group, span in active_hours.items())
                funded = min(required, max(0, player.budget))
                ratio = funded / required if required > 0 else 0
                player.budget -= funded
                for group, span in active_hours.items():
                    state.program_funding[group] = ratio
                    state.program_funded_hours[group] = state.program_funded_hours.get(group, 0) + span * ratio
            self.hours += step
            remaining -= step
            if self.hours < 24 - 1e-9:
                self.expire_programs()
                continue
            self.day += 1
            self.hours = 0.0
            self.service_loans()
            for player in self.players.values():
                politics = player.politics
                for group in politics.programs:
                    politics.program_funding[group] = min(1, politics.program_funded_hours.get(group, 0) / 24)
                    politics.program_funded_hours[group] = 0.0
                for group in SUPPORT_GROUPS:
                    target = self.rules.support_target(self, player, group)
                    politics.support[group] += self.rules.daily_support_change(politics.support[group], max(0, min(1, target)))
                    self.news.report_support(self.day, player, group, SUPPORT_GROUPS[group], politics.support[group])
                at_war = any(relation.at_war for pair, relation in self.relations.items() if player.id in pair)
                if hasattr(player, "war_support"):
                    recovery = max(-.0002, min(.0002, (.5 - player.war_support) / 180))
                    player.war_support = max(0, min(1, player.war_support + (-.0002 if at_war else recovery)))
                if not at_war and politics.reputation < .5:
                    politics.reputation = min(.5, politics.reputation + .00005)
                politics.political_capital = max(0, min(100, politics.political_capital
                    + .05 * (politics.government_support + getattr(player, "legitimacy", .61)) / 1.22
                    - (.04 if at_war else 0)))
                for faction in FACTIONS:
                    wartime = (.05 if faction == "nationalists" else -.08 if faction in ("liberals", "socialists") else 0) if at_war else 0
                    _, demand_met = self.rules.faction_demand(player, faction, at_war)
                    demand_effect = .08 if demand_met else -.35
                    patience_target = max(0, min(1, .7 + 1.5 * (politics.support[faction] - .61) + wartime + demand_effect))
                    patience = politics.faction_patience[faction]
                    patience = max(0, min(1, patience + (patience_target - patience) / 90))
                    politics.faction_patience[faction] = patience
                    radical = politics.faction_radicalization[faction]
                    politics.faction_radicalization[faction] = max(0, min(1, radical
                        + max(0, .4 - patience) * .005 - max(0, patience - .55) * .001))
                stability_target, legitimacy_target = self.rules.institutional_targets(player)
                for attribute, target, days in (("stability", stability_target, 90), ("legitimacy", legitimacy_target, 180)):
                    if hasattr(player, attribute):
                        current = getattr(player, attribute)
                        setattr(player, attribute, max(0, min(1, current + max(-0.0015, min(0.0015, (target - current) / days)))))
            for country_ids, relation in self.relations.items():
                if relation.truce_until == self.day:
                    for country_id in country_ids:
                        self.news.notice(self.day, self.players[country_id], "truce_expired", "Срок перемирия истёк",
                            f"Перемирие между {self.players[country_ids[0]].name} и {self.players[country_ids[1]].name} "
                            "больше не ограничивает объявление войны. Остальные требования сохраняются.")
                for country_id in relation.grievances:
                    relation.grievances[country_id] = max(0, relation.grievances[country_id] - .02)
                    relation.fear[country_id] = max(0, relation.fear[country_id] - .01)
                if not relation.at_war and relation.crisis_level > 0:
                    relation.crisis_level = min(60, relation.crisis_level + .5)
            self.expire_programs()
            for (actor_id, target_id), ready_day in list(self.war_goals.items()):
                if self.day == ready_day:
                    self.record(self.players[actor_id], f"Цель войны против {self.players[target_id].name} подготовлена")
                    self.news.publish(self.day, "war_goal_ready", "Цель войны подготовлена",
                        f"Цель войны против страны {self.players[target_id].name} готова. Решение об объявлении войны остаётся за вами.",
                        scope="local", country_ids=(actor_id,))
                elif self.day > ready_day + 180:
                    del self.war_goals[(actor_id, target_id)]
                    if (target_id, actor_id) not in self.war_goals:
                        self.relation(actor_id, target_id).crisis_level = 0
                    self.record(self.players[actor_id], f"Срок цели войны против {self.players[target_id].name} истёк")
                    self.news.publish(self.day, "war_goal_expired", "Цель войны утратила силу",
                        f"Подготовленная цель войны против страны {self.players[target_id].name} больше не действует.",
                        scope="local", country_ids=(actor_id,))
            for offer in list(self.pending):
                a, b, key, due = offer
                if due > self.day or self.players[b].is_human:
                    continue
                accept = self.offer_evaluator(self, offer) if self.offer_evaluator else self.rules.accepts(self, offer)
                self.resolve_offer(offer, accept)
            self.news.advance(self.day)
            self.revision += 1

    def expire_programs(self):
        now = self.day + self.hours / 24
        for player in self.players.values():
            state = player.politics
            for group, end in list(state.programs.items()):
                if end is not None and end <= now + 1e-9:
                    del state.programs[group]
                    state.program_costs.pop(group, None)
                    state.program_funding.pop(group, None)
                    state.program_funded_hours.pop(group, None)
                    self.record(player, f"Программа завершена по сроку: {SUPPORT_GROUPS[group]}")
                    self.news.publish(self.day, "program_expired", f"Срок поддержки истёк: {SUPPORT_GROUPS[group]}",
                        f"Программа поддержки группы «{SUPPORT_GROUPS[group]}» в стране {player.name} завершилась по сроку.",
                        scope="local", country_ids=(player.id,))
                    self.revision += 1
