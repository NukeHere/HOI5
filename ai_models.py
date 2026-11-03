"""Small, serializable state for the server's country controllers."""

from collections import deque
from dataclasses import dataclass, field
import math
import random


@dataclass
class Estimate:
    value: float
    lower: float
    upper: float
    observed_hour: float


@dataclass
class CountryReport:
    country_id: int
    observed_hour: float
    economy: dict = field(default_factory=dict)
    military: dict = field(default_factory=dict)
    finance: dict = field(default_factory=dict)


@dataclass
class AITask:
    id: int
    kind: str
    region_id: tuple | None
    payload: dict
    created_hour: float
    status: str = "planned"
    reason: str = ""
    retry_hour: float = 0
    command_id: int | None = None
    motivation: str = ""


@dataclass
class Review:
    kind: str
    started_hour: float
    next_hour: float
    stage: int = 0
    data: dict = field(default_factory=dict)


@dataclass
class BotState:
    country_id: int
    rng: random.Random
    next_micro: float
    next_daily: float
    next_weekly: float
    next_monthly: float
    course: str = "development"
    target_id: int | None = None
    course_since: float = 0
    intelligence: float = .25
    aggression: float = .5
    expansion_target: int | None = None
    course_bias: dict = field(default_factory=dict)
    offensive_focus: tuple | None = None
    next_peace_deployment: float = 0
    next_air_refresh: float = 0
    next_air_defense_move: float = 0
    air_defense_targets: dict = field(default_factory=dict)
    biases: dict = field(default_factory=dict)
    reports: dict = field(default_factory=dict)
    reviews: dict = field(default_factory=dict)
    tasks: list = field(default_factory=list)
    assignments: dict = field(default_factory=dict)
    hex_assignments: dict = field(default_factory=dict)
    front_quotas: dict = field(default_factory=dict)
    reserve_id: int | None = None
    resting_ids: set = field(default_factory=set)
    supply_target: tuple | None = None
    dependencies: dict = field(default_factory=dict)
    influence: dict = field(default_factory=dict)
    regions: dict = field(default_factory=dict)
    history: deque = field(default_factory=lambda: deque(maxlen=100))
    last_orders: dict = field(default_factory=dict)
    last_order_reasons: dict = field(default_factory=dict)
    urgent: bool = False
    decision_sequence: int = 0
    course_evidence: dict = field(default_factory=dict)
    course_decision: dict = field(default_factory=dict)
    expansion_candidates: list = field(default_factory=list)
    expansion_observed_hour: float = 0

    def note(self, hour, kind, **data):
        self.decision_sequence += 1
        self.history.append(dict(sequence=self.decision_sequence, hour=hour, kind=kind, **data))


def choose_close(rng, candidates, margin=.12):
    """Randomness only among near-best positive utilities, never among illegal actions."""
    if not candidates:
        return None
    best = max(score for score, item in candidates)
    pool = [(score, item) for score, item in candidates
            if score >= best - max(1e-9, abs(best) * margin)]
    if len(pool) == 1:
        return pool[0][1]
    weights = [math.exp((score - best) / max(1e-9, abs(best) * margin)) for score, item in pool]
    return rng.choices([item for score, item in pool], weights=weights, k=1)[0]


def division_vector(division):
    strength = max(0, min(1, division.strength / max(1, division.max_strength)))
    organization = max(0, min(1, division.organization / max(1, division.max_organization)))
    supply = max(0, min(1, division.last_supply_ratio))
    factor = strength * (.25 + .75 * organization) * (.35 + .65 * supply)
    return {
        "personnel": max(0, division.manpower),
        "attack": (division.soft_attack + division.hard_front_attack + division.hard_top_attack) * factor,
        "defense": division.defense * factor,
        "breakthrough": division.breakthrough * factor,
        "armor": max(division.front_armor, division.top_armor) * strength,
        "piercing": max(division.front_piercing, division.top_piercing) * factor,
        "mobility": division.speed * organization,
        "ready": factor,
    }


class Intelligence:
    """Persistent correlated errors: requests or refreshes cannot average them away."""

    def estimate(self, bot, target, group, key, value, hour):
        value = float(value)
        if target == bot.country_id:
            return Estimate(value, value, value, hour)
        bias_key = (target, group)
        if bias_key not in bot.biases:
            bot.biases[bias_key] = bot.rng.uniform(-1, 1)
        amplitude = .45 * (1 - max(0, min(.95, bot.intelligence)))
        factor = 1 + bot.biases[bias_key] * amplitude
        observed = value * factor
        limits = sorted((observed / (1 + amplitude), observed / (1 - amplitude)))
        return Estimate(observed, limits[0], limits[1], hour)


class FlowLedger:
    """Cumulative exact production/trade operations, sampled into a bounded history."""

    def __init__(self):
        self.totals = {}
        self.hours = {}
        self.samples = {}

    def record(self, country_id, kind, resource, amount, partner=None):
        totals = self.totals.setdefault(country_id, {})
        key = (kind, resource, partner)
        totals[key] = totals.get(key, 0) + amount

    def advance(self, country_id, hours):
        self.hours[country_id] = self.hours.get(country_id, 0) + hours

    def sample(self, country_id, now):
        samples = self.samples.setdefault(country_id, deque(maxlen=10))
        if not samples or now - samples[-1][0] >= 24:
            samples.append((now, self.hours.get(country_id, 0), dict(self.totals.get(country_id, {}))))

    def rates(self, country_id, now):
        self.sample(country_id, now)
        samples = self.samples[country_id]
        baseline = next((s for s in samples if s[0] >= now - 168), samples[0])
        hours = self.hours.get(country_id, 0) - baseline[1]
        if hours <= 0:
            return {}, 0
        return {key: (amount - baseline[2].get(key, 0)) * 720 / hours
                for key, amount in self.totals.get(country_id, {}).items()}, hours
