from dataclasses import dataclass, field
from datetime import datetime

from Constants import *


@dataclass
class MarketState:
    base_prices: dict = field(default_factory=lambda: dict(TRADE_BASE_PRICES))
    current_prices: dict = field(default_factory=dict)
    previous_prices: dict = field(default_factory=dict)
    price_shocks: dict = field(default_factory=dict)
    demand: dict = field(default_factory=dict)
    supply: dict = field(default_factory=dict)
    external_demand: dict = field(default_factory=dict)
    external_supply: dict = field(default_factory=dict)
    history: dict = field(default_factory=dict)
    revision: int = 0
    last_execution_time: datetime | None = None

    def ensure_resource(self, resource_key):
        base_price = float(self.base_prices.get(resource_key, TRADE_BASE_PRICES.get(resource_key, 60.0)))
        self.base_prices.setdefault(resource_key, base_price)
        self.current_prices.setdefault(resource_key, base_price)
        self.previous_prices.setdefault(resource_key, base_price)
        self.price_shocks.setdefault(resource_key, 0.0)
        self.demand.setdefault(resource_key, 0.0)
        self.supply.setdefault(resource_key, 0.0)
        self.external_demand.setdefault(resource_key, 0.0)
        self.external_supply.setdefault(resource_key, 0.0)
        self.history.setdefault(resource_key, [base_price])
        return base_price


@dataclass
class StatePlayer:
    id: int
    name: str
    color: tuple[int, int, int]
    border_color: tuple[int, int, int]
    is_human: bool = False
    capital_tile: object | None = None
    tiles: list = None
    resource_totals: dict = None
    resource_sources: dict = None
    resource_stockpiles: dict = None
    production_modifiers: dict = None
    production_cache: dict = None
    resource_balance_breakdown: dict = None
    resource_balance_dirty: bool = True
    resource_balance_last_update: float = 0.0
    storage_capacity: dict = None
    storage_used: dict = None
    storage_overflow: dict = None
    storage_dirty: bool = True
    tile_stockpiles_dirty: bool = True
    supply_summary: dict = None
    trade_contracts: list = None
    trade_contract_revision: int = 0
    trade_modifiers: dict = None
    construction_modifiers: dict = None
    construction_queue: list = None
    divisions: list = None
    armies: list = None
    air_wings: list = None
    air_defense_units: list = None
    airbases: list = None
    aircraft_stockpile: dict = None
    monthly_income_breakdown: dict = None
    monthly_expenses_breakdown: dict = None
    economy_month_key: tuple | None = None
    economy_current_snapshot: dict = None
    economy_previous_snapshot: dict = None
    population: float | None = None
    budget: float = 250_000_000.0
    monthly_balance: float = 0.0
    monthly_trade_balance: float = 0.0
    population_month_accumulator: float = 0.0
    manpower_reserve: float = 0.0
    stability: float = 0.72
    legitimacy: float = 0.61
    war_support: float = 0.50

    def __post_init__(self):
        if self.tiles is None:
            self.tiles = []
        if self.resource_totals is None:
            self.resource_totals = {"raw": {}}
        if self.resource_sources is None:
            self.resource_sources = {}
        if self.resource_stockpiles is None:
            self.resource_stockpiles = {
                "raw": {},
                "semi_finished": {},
                "finished": {},
            }
        if self.production_modifiers is None:
            self.production_modifiers = {
                "industry_efficiency": 1.0,
                "mining_efficiency": 1.0,
                "agriculture_efficiency": 1.0,
                "refining_efficiency": 1.0,
                "logistics_efficiency": 1.0,
                "storage_efficiency": 1.0,
                "industry_diversification_penalty": 0.9,
                "industry_free_specializations": 1,
            }
        if self.production_cache is None:
            self.production_cache = {
                stage: {"inputs": {}, "outputs": {}}
                for stage in PRODUCTION_STAGES
            }
        if self.resource_balance_breakdown is None:
            self.resource_balance_breakdown = {
                category: {}
                for category in ["raw", "semi_finished", "finished"]
            }
        if self.storage_capacity is None:
            self.storage_capacity = {category: 0.0 for category in STORAGE_CATEGORIES}
        if self.storage_used is None:
            self.storage_used = {category: 0.0 for category in STORAGE_CATEGORIES}
        if self.storage_overflow is None:
            self.storage_overflow = {category: 0.0 for category in STORAGE_CATEGORIES}
        if self.supply_summary is None:
            self.supply_summary = {
                "average": 1.0,
                "low_tiles": 0,
                "critical_tiles": 0,
            }
        if self.trade_contracts is None:
            self.trade_contracts = []
        if self.trade_modifiers is None:
            self.trade_modifiers = {
                "external_market_limit": 1.0,
                "diplomacy_trade_bonus": 0.0,
            }
        if self.construction_modifiers is None:
            self.construction_modifiers = {
                "build_efficiency": 1.0,
                "city_build_multiplier": 1.0,
                "tech_bonus": 0.0,
            }
        if self.construction_queue is None:
            self.construction_queue = []
        if not hasattr(self, "divisions") or self.divisions is None:
            self.divisions = []
        if not hasattr(self, "armies") or self.armies is None:
            self.armies = []
        if not hasattr(self, "air_wings") or self.air_wings is None:
            self.air_wings = []
        if not hasattr(self, "air_defense_units") or self.air_defense_units is None:
            self.air_defense_units = []
        if not hasattr(self, "airbases") or self.airbases is None:
            self.airbases = []
        if not hasattr(self, "aircraft_stockpile") or self.aircraft_stockpile is None:
            self.aircraft_stockpile = {}
        if self.monthly_income_breakdown is None:
            self.monthly_income_breakdown = {
                "population": 0.0,
                "companies": 0.0,
                "trade": 0.0,
                "multiplier": 1.0,
                "total": 0.0,
            }
        if self.monthly_expenses_breakdown is None:
            self.monthly_expenses_breakdown = {
                "army": 0.0,
                "government": 0.0,
                "social": 0.0,
                "social_breakdown": {
                    "pensions": 0.0,
                    "children": 0.0,
                    "disability": 0.0,
                    "local_services": 0.0,
                    "total": 0.0,
                },
                "infrastructure": 0.0,
                "total": 0.0,
            }
        if self.economy_current_snapshot is None:
            self.economy_current_snapshot = {}


@dataclass
class Division:
    id: int
    owner: StatePlayer
    template_key: str
    tile: object
    target_tile: object | None = None
    path: list = field(default_factory=list)
    route_mode: str = "move"
    route_tiles: list = field(default_factory=list)
    post_battle_path: list = field(default_factory=list)
    manpower: int = 10_000
    organization: float = 100.0
    max_organization: float = 100.0
    strength: float = 100.0
    max_strength: float = 100.0
    speed: float = 1.35
    organization_recovery: float = 8.0
    initiative: float = 0.03
    front_width: float = 20.0
    reliability: float = 1.0
    recon: float = 0.0
    camouflage: float = 0.0
    soft_attack: float = 18.0
    defense: float = 26.0
    breakthrough: float = 8.0
    hard_front_attack: float = 3.0
    hard_top_attack: float = 1.0
    front_piercing: float = 4.0
    top_piercing: float = 1.0
    front_armor: float = 2.0
    top_armor: float = 1.0
    infantry_share: float = 0.92
    vehicle_share: float = 0.08
    max_manpower: int = 10_000
    supply_capacity: dict = field(default_factory=dict)
    supply_stock: dict = field(default_factory=dict)
    combat_supply_use: dict = field(default_factory=dict)
    last_supply_ratio: float = 1.0
    last_reinforcement_ratio: float = 0.0
    selected: bool = False
    x: float = 0.0
    y: float = 0.0
    movement_progress: float = 0.0
    visual_movement_progress: float = 0.0
    army_id: int | None = None
    battle_id: tuple | None = None
    battle_side: str | None = None
    battle_status: str | None = None
    width_efficiency: float = 1.0
    air_ground_suppression: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.tile is not None and self.x == 0.0 and self.y == 0.0:
            self.x = self.tile.center_x
            self.y = self.tile.center_y
        if self.max_manpower <= 0:
            self.max_manpower = max(1, int(self.manpower))
        if not self.supply_capacity:
            self.supply_capacity = {}
        if not self.supply_stock:
            self.supply_stock = dict(self.supply_capacity)
        if not self.combat_supply_use:
            self.combat_supply_use = {}
        if self.air_ground_suppression is None:
            self.air_ground_suppression = {}


@dataclass
class Army:
    id: int
    owner: StatePlayer
    name: str
    division_ids: list = field(default_factory=list)
    battle_plans: list = field(default_factory=list)
    executing_plan: bool = False
    plan_update_accumulator: float = 0.0
    active_front_plan_id: int | None = None
    selected: bool = False


@dataclass
class BattlePlan:
    id: int
    army_id: int
    plan_type: str
    line_tile_keys: list = field(default_factory=list)
    target_owner_id: int | None = None
    source_plan_id: int | None = None
    active: bool = True


@dataclass
class Battle:
    id: tuple
    tile: object
    attacker: StatePlayer
    defender: StatePlayer | None
    attacker_from_tile: object | None = None
    active_attackers: list = field(default_factory=list)
    reserve_attackers: list = field(default_factory=list)
    recovering_attackers: list = field(default_factory=list)
    active_defenders: list = field(default_factory=list)
    reserve_defenders: list = field(default_factory=list)
    recovering_defenders: list = field(default_factory=list)
    combat_width: float = COMBAT_WIDTH_DEFAULT
    advance_progress: float = 0.0
    last_attacker_org_damage: float = 0.0
    last_attacker_strength_damage: float = 0.0
    last_defender_org_damage: float = 0.0
    last_defender_strength_damage: float = 0.0
    started_at: object | None = None
    last_tick: object | None = None


@dataclass
class Airbase:
    id: int
    owner: StatePlayer
    tile: object
    runway_level: int = 1
    aircraft_capacity: int = 36
    helicopter_capacity: int = 12
    fuel_storage: float = 12_000.0
    munition_storage: float = 6_000.0
    hangar_level: int = 1
    hardened_shelter_level: int = 0
    repair_capacity: float = 1.0
    radar_control_level: int = 1


@dataclass
class AirWing:
    id: int
    owner: StatePlayer
    base_tile: object
    aircraft_type: str
    aircraft_count: int
    aircraft_composition: dict = field(default_factory=dict)
    ready_count: int = 0
    damaged_count: int = 0
    reserve_count: int = 0
    fuel: float = 1.0
    current_loadout: str | None = None
    mission: str = "none"
    enabled_missions: list = field(default_factory=list)
    target_priorities: list = field(default_factory=list)
    auto_execute_orders: bool = True
    operation_area_tile_keys: list = field(default_factory=list)
    target_area: object | None = None
    target_tile: object | None = None
    risk_policy: str = "normal"
    sortie_intensity: float = 0.5
    sortie_cooldown_hours: float = 0.0
    mission_cooldowns: dict = field(default_factory=dict)
    mission_target_cooldowns: dict = field(default_factory=dict)
    last_mission_target_keys: dict = field(default_factory=dict)
    mission_state: str = "returning"
    mission_state_hours: float = 0.0
    mission_target_tile_key: object | None = None
    defensive_hours: float = 0.0
    aborted_hours: float = 0.0
    last_air_combat_summary: str = ""
    destroyed_count: int = 0
    interceptor_munition: str | None = None
    interceptor_ammo: int = 0
    interceptor_ammo_capacity: int = 0

    def __post_init__(self):
        if self.aircraft_composition is None:
            self.aircraft_composition = {}
        self.aircraft_composition = {
            aircraft_type: max(0, int(count))
            for aircraft_type, count in (self.aircraft_composition or {}).items()
            if aircraft_type in AIRCRAFT_TYPES and int(count) > 0
        }
        if not self.aircraft_composition and self.aircraft_type in AIRCRAFT_TYPES and self.aircraft_count > 0:
            self.aircraft_composition = {self.aircraft_type: int(self.aircraft_count)}
        if self.aircraft_composition:
            self.aircraft_type = max(self.aircraft_composition.items(), key=lambda item: item[1])[0]
            self.aircraft_count = sum(self.aircraft_composition.values())
        if self.ready_count <= 0:
            self.ready_count = max(0, self.aircraft_count - self.damaged_count - self.reserve_count)
        self.ready_count = min(self.aircraft_count, max(0, self.ready_count))
        if self.enabled_missions is None:
            self.enabled_missions = []
        if not self.enabled_missions and self.mission not in (None, "none"):
            self.enabled_missions = [self.mission]
        if self.target_priorities is None:
            self.target_priorities = []
        if self.operation_area_tile_keys is None:
            self.operation_area_tile_keys = []
        if self.mission_state not in {"approach", "attack_run", "defensive", "egress", "returning", "aborted"}:
            self.mission_state = "returning"
        if self.mission_cooldowns is None:
            self.mission_cooldowns = {}
        if self.mission_target_cooldowns is None:
            self.mission_target_cooldowns = {}
        if self.last_mission_target_keys is None:
            self.last_mission_target_keys = {}
        self.mission_state_hours = max(0.0, float(self.mission_state_hours or 0.0))
        self.defensive_hours = max(0.0, float(self.defensive_hours or 0.0))
        self.aborted_hours = max(0.0, float(self.aborted_hours or 0.0))
        self.destroyed_count = max(0, int(self.destroyed_count or 0))
        self.interceptor_ammo = max(0, int(getattr(self, "interceptor_ammo", 0) or 0))
        self.interceptor_ammo_capacity = max(0, int(getattr(self, "interceptor_ammo_capacity", 0) or 0))


@dataclass
class AirDefenseUnit:
    id: int
    owner: StatePlayer
    tile: object
    unit_class: str
    radar_range_cells: int = 0
    fire_range_cells: int = 0
    min_range_cells: int = 0
    ammo: int = 0
    readiness: float = 1.0
    camouflage: float = 0.0
    radar_active: bool = False
    detection_power: float = 0.0
    tracking_quality: float = 0.0
    tracking_channels: int = 0
    fire_channels: int = 0
    max_targets_per_tick: int = 0
    interceptors_per_target: int = 1
    missile_profile: str | None = None
    health: float = 1.0
    target_tile: object | None = None
    path: list = field(default_factory=list)
    route_tiles: list = field(default_factory=list)
    movement_progress: float = 0.0
    visual_movement_progress: float = 0.0
    x: float = 0.0
    y: float = 0.0

    def __post_init__(self):
        if self.tile is not None and self.x == 0.0 and self.y == 0.0:
            self.x = self.tile.center_x
            self.y = self.tile.center_y


@dataclass
class DivisionAirDefenseThreat:
    id: tuple
    owner: StatePlayer
    tile: object
    unit_class: str
    division_id: int
    ammo_key: str
    radar_range_cells: int = 0
    fire_range_cells: int = 1
    min_range_cells: int = 0
    ammo: int = 0
    readiness: float = 1.0
    camouflage: float = 0.0
    radar_active: bool = False
    detection_power: float = 0.0
    tracking_quality: float = 0.0
    tracking_channels: int = 0
    fire_channels: int = 0
    max_targets_per_tick: int = 0
    interceptors_per_target: int = 1
    missile_profile: str | None = None
    health: float = 1.0


@dataclass
class AirSalvo:
    id: int
    owner: StatePlayer
    munition_type: str
    count: int
    original_count: int
    target_tile: object
    launch_tile: object
    source_air_wing_id: int | None = None
    source_unit_id: int | None = None
    mission_type: str | None = None
    target_unit_id: int | None = None
    target_object_type: str | None = None
    launch_distance: float = 0.0
    remaining_distance: float = 0.0
    current_tile: object | None = None
    speed: float = 1.0
    terminal_speed: float = 1.0
    altitude_profile: str | None = None
    flight_profile: str = "linear"
    average_rcs: float = 0.0
    average_infrared_signature: float = 0.0
    average_maneuverability: float = 0.0
    average_interceptability: float = 0.0
    detected_by: set = field(default_factory=set)
    ticks_alive: int = 0
    must_spend_intercept_tick: bool = False
    entered_defended_zone: bool = False


@dataclass
class AirAttackSalvo:
    id: int
    owner: StatePlayer
    launcher_air_wing_id: int
    interceptor_aircraft_type: str
    munition_type: str
    count: int
    original_count: int
    launch_tile: object
    target_tile: object
    target_air_wing_id: int | None = None
    target_air_salvo_id: int | None = None
    target_aircraft_type: str | None = None
    target_sorties: int = 0
    launch_distance: float = 0.0
    remaining_distance: float = 0.0
    current_tile: object | None = None
    speed: float = 1.0
    terminal_speed: float = 1.0
    hit_chance: float = 0.0
    ticks_alive: int = 0
    must_spend_reaction_tick: bool = True


@dataclass
class AirImpactDecal:
    tile: object
    x: float
    y: float
    age: float = 0.0
    duration: float = AIR_IMPACT_DECAL_DURATION
    size: float = 1.0
    color: tuple = (255, 184, 86)


@dataclass
class AirCombatEstimate:
    detection_chance: float = 0.0
    tracking_chance: float = 0.0
    hit_chance: float = 0.0
    intercept_chance: float = 0.0
    expected_kills: float = 0.0
    expected_hits: float = 0.0
    expected_damage: float = 0.0
    ammo_cost: int = 0
    target_priority: float = 1.0
    should_fire: bool = False
    reason: str = ""


@dataclass
class FieldHelipadProject:
    id: int
    owner: StatePlayer
    tile: object
    progress_hours: float = 0.0
    work_required_hours: float = FIELD_HELIPAD_AUTO_WORK_HOURS
    source_battle_id: tuple | None = None
