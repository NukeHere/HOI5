"""Political state and deterministic actions, independent of rendering."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math


GROUPS = {"population": "Население", "smb": "Малый и средний бизнес", "large": "Крупный бизнес"}
GROUP_WEIGHTS = {"population": 0.85, "smb": 0.12, "large": 0.03}
SOCIAL_GROUPS = {"workers": "Рабочие (пролетариат)", "farmers": "Сельские жители", "middle": "Средний класс", "aristocracy": "Аристократия"}
SOCIAL_WEIGHTS = {"workers": 0.45, "farmers": 0.25, "middle": 0.28, "aristocracy": 0.02}
FACTIONS = {"nationalists": "Националисты", "socialists": "Социалисты", "liberals": "Либералы", "conservatives": "Консерваторы"}
SUPPORT_GROUPS = {**GROUPS, **SOCIAL_GROUPS, **FACTIONS}
TREATIES = {"trade": "Торговый договор", "peace": "Мирный договор", "alliance": "Союз"}
OFFERS = {**TREATIES, "loan": "Кредит"}


@dataclass
class PoliticalState:
    support: dict = field(default_factory=lambda: dict.fromkeys(SUPPORT_GROUPS, 0.61))
    social_shares: dict = field(default_factory=lambda: dict(SOCIAL_WEIGHTS))
    faction_shares: dict = field(default_factory=lambda: dict.fromkeys(FACTIONS, 0.25))
    taxes: dict = field(default_factory=lambda: dict.fromkeys(GROUPS, 0))
    programs: dict = field(default_factory=dict)
    program_costs: dict = field(default_factory=dict)
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
        PoliticalAction("peace", "Предложить мир", False, "Прекращение войны по текущим границам с временным запретом новой войны."),
        PoliticalAction("war", "Объявить войну", False, "Прекращает прямую торговлю и договоры.", cooldown=30),
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
        _description, cooldown=90)
    _key = f"stop:{_group}"
    ACTIONS[_key] = PoliticalAction(_key, f"Завершить поддержку: {_label.lower()}", True,
        "Прекращает регулярные расходы; поддержка группы постепенно меняется.")


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
    program_days: int = 90
    program_monthly_cost: float = 1_000_000
    loan_annual_rate: float = 0.05
    loan_term_months: int = 12
    response_days: int = 3
    truce_days: int = 30


class PoliticalRules:
    """Replaceable rule boundary; current tuning is intentionally fixed."""

    def quote(self, system, actor, target, action, amount):
        opinion = {"mission": 8, "aid": 5, "embargo": -10, "war": -60, "break": -20}.get(action.key, 0)
        trust = {"mission": 0.04, "break": -0.2}.get(action.key, 0)
        if action.key == "war":
            trust = -system.relation(actor.id, target.id).trust
        if action.key == "embargo" and actor.id in system.relation(actor.id, target.id).embargoes:
            opinion = 0
        cost = amount if action.key == "aid" and amount is not None else action.cost
        return ActionQuote(cost, opinion, trust, action.cooldown)

    def accepts(self, system, offer):
        a, b, key, _ = offer
        relation = system.relation(a, b)
        target = system.players[b]
        if key == "peace":
            return target.budget < 0 or relation.opinions[b] >= -20
        threshold = 30 if key == "alliance" else -10
        if relation.opinions[b] < threshold or relation.trust < 0.35:
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
        target += 0.08 if group in politics.programs else 0
        if group not in GROUPS and "population" in politics.programs:
            target += 0.04
        target -= 0.12 if player.budget < 0 else 0
        target -= 0.03 if group in ("smb", "large") and politics.export_restricted else 0
        return max(0, min(1, target))


class PoliticsSystem:
    def __init__(self, players, rules=None, start_time=None):
        self.rules = rules or PoliticalRules()
        self.start_time = start_time or datetime(2000, 1, 1)
        self.players = {player.id: player for player in players}
        self.relations = {}
        self.pending = []
        self.offer_amounts = {}
        self.offer_quotes = {}
        self.loans = []
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
            self.relations[key] = BilateralRelation(opinions={a: 0.0, b: 0.0})
        return self.relations[key]

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

    def quote(self, actor_id, target_id, key, amount=None):
        return self.rules.quote(self, self.players[actor_id], self.players[target_id], ACTIONS[key], amount)

    def reason(self, actor_id, target_id, key, amount=None):
        action = ACTIONS.get(key)
        if not action or actor_id not in self.players or target_id not in self.players:
            return "Неизвестное действие или государство"
        if action.domestic != (actor_id == target_id):
            return "Действие недоступно для этой страны"
        actor = self.players[actor_id]
        if key == "exports" and amount is not None:
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or not 0 <= amount <= 100:
                return "Выберите лимит экспорта от 0 до 100%"
        if key in ("aid", "loan"):
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or not 1_000 <= amount <= 1_000_000_000_000:
                return "Введите сумму от 1 тыс. до 1 трлн"
            if actor.budget < amount:
                return "Недостаточно средств для выбранной суммы"
        quote = self.quote(actor_id, target_id, key, amount)
        if not actor.tiles or not self.players[target_id].tiles:
            return "Государство не контролирует территорию"
        cooldown_key = (key if not key.startswith("tax:") else key.rsplit(":", 1)[0], target_id)
        if actor.politics.cooldowns.get(cooldown_key, 0) > self.day:
            return f"Доступно с {self.date_text(actor.politics.cooldowns[cooldown_key])}"
        if (quote.cost > 0 and actor.budget < quote.cost) or (key.startswith("support:") and actor.budget < quote.cost + quote.program_monthly_cost):
            return "Недостаточно средств"
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
            if key in ("mission", "aid", "loan", "trade", "alliance") and relation.at_war:
                return "Сначала заключите мир"
            if key in OFFERS:
                if key in relation.treaties:
                    return "Договор уже действует"
                if any({p[0], p[1]} == {actor_id, target_id} and p[2] == key for p in self.pending):
                    return "Предложение ожидает ответа"
                if key == "peace" and not relation.at_war:
                    return "Войны нет"
                if key in ("trade", "alliance") and relation.embargoes:
                    return "Сначала снимите эмбарго"
            if key == "war" and (relation.at_war or "alliance" in relation.treaties or self.day < relation.truce_until):
                return "Война уже идёт, действует союз или перемирие"
            if key == "break" and not relation.treaties:
                return "Нет действующих договоров"
        return ""

    def record(self, player, message):
        player.politics.history.appendleft((self.day, message))

    def execute(self, actor_id, target_id, key, amount=None):
        reason = self.reason(actor_id, target_id, key, amount)
        if reason:
            return False, reason
        actor = self.players[actor_id]
        action = ACTIONS[key]
        quote = self.quote(actor_id, target_id, key, amount)
        actor.budget -= quote.cost
        cooldown_key = (key if not key.startswith("tax:") else key.rsplit(":", 1)[0], target_id)
        actor.politics.cooldowns[cooldown_key] = self.day + quote.cooldown_days
        if key.startswith("tax:"):
            _, group, delta = key.split(":")
            actor.politics.taxes[group] += int(delta)
        elif key.startswith("support:"):
            group = key.split(":")[1]
            actor.politics.programs[group] = self.day + quote.program_days
            actor.politics.program_costs[group] = quote.program_monthly_cost
        elif key.startswith("stop:"):
            group = key.split(":")[1]
            del actor.politics.programs[group]
            actor.politics.program_costs.pop(group, None)
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
                if key == "loan":
                    self.offer_amounts[offer] = float(amount)
            elif key == "aid":
                target.budget += amount
            elif key == "embargo":
                if actor_id in relation.embargoes:
                    relation.embargoes.remove(actor_id)
                else:
                    relation.embargoes.add(actor_id)
            elif key == "war":
                relation.at_war = True
                relation.treaties.clear()
            elif key == "break":
                relation.treaties.clear()
            if key not in OFFERS:
                relation.trust = max(0, min(1, relation.trust + quote.trust_delta))
                relation.opinions[target_id] = max(-100, min(100, relation.opinions[target_id] + quote.opinion_delta))
            self.record(target, f"{actor.name}: {action.label}" + (f" ({amount:,.0f})" if key in ("aid", "loan") else ""))
        self.record(actor, action.label + (f" ({amount:,.0f})" if key in ("aid", "loan") else ""))
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
            else:
                relation.treaties.add(key)
            if key == "peace":
                relation.at_war = False
                relation.truce_until = self.day + quote.truce_days
        self.pending.remove(offer)
        self.offer_amounts.pop(offer, None)
        self.offer_quotes.pop(offer, None)
        for player_id in (a, b):
            self.record(self.players[player_id], f"{OFFERS[key]}: {'принят' if accept else 'отклонён'}")
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
            if loan.principal <= 1e-6 and loan.interest_due <= 1e-6:
                self.loans.remove(loan)
                for player in (lender, borrower):
                    self.record(player, "Кредит полностью погашен")

    def advance(self, hours):
        self.hours += max(0, hours)
        days = int(self.hours // 24)
        self.hours -= days * 24
        for _ in range(days):
            self.day += 1
            self.service_loans()
            for player in self.players.values():
                politics = player.politics
                for group, end in list(politics.programs.items()):
                    if end <= self.day or player.budget < 0:
                        del politics.programs[group]
                        politics.program_costs.pop(group, None)
                        self.record(player, f"Программа завершена: {SUPPORT_GROUPS[group]}")
                for group in SUPPORT_GROUPS:
                    target = self.rules.support_target(self, player, group)
                    politics.support[group] += (max(0, min(1, target)) - politics.support[group]) * 0.04
            for offer in list(self.pending):
                a, b, key, due = offer
                if due > self.day or self.players[b].is_human:
                    continue
                accept = self.rules.accepts(self, offer)
                self.resolve_offer(offer, accept)
            self.revision += 1
