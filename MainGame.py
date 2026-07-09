import arcade
import random
import json
import math
import struct
import time
import textwrap
import heapq
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from perlin_noise import PerlinNoise
from PIL import Image, ImageDraw
from pyglet.graphics import Batch
from arcade.gl import BufferDescription
from Constants import *
from HexTile import HexTile
from MapData import MapTileData
from Settings import apply_window_settings_safely, create_window_with_fallback, load_settings, save_settings

class PauseButton:
    def __init__(self, label, x, y, width, height, action):
        self.label = label
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.action = action
        self.text = arcade.Text(label, 0, 0, arcade.color.WHITE, 18, anchor_x="center", anchor_y="center")

    def contains(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def draw(self, hovered=False):
        fill = (63, 86, 116) if hovered else (42, 55, 72)
        border = (165, 195, 230) if hovered else (100, 126, 155)
        arcade.draw_lbwh_rectangle_filled(self.x, self.y, self.width, self.height, fill)
        arcade.draw_lbwh_rectangle_outline(self.x, self.y, self.width, self.height, border, 2)
        self.text.text = self.label
        self.text.x = self.x + self.width / 2
        self.text.y = self.y + self.height / 2
        self.text.draw()


class PauseSlider:
    def __init__(self, label, x, y, width, value, on_change):
        self.label = label
        self.x = x
        self.y = y
        self.width = width
        self.value = value
        self.on_change = on_change
        self.height = 28
        self.label_text = arcade.Text(label, 0, 0, (225, 232, 240), 16)
        self.value_text = arcade.Text("", 0, 0, (180, 192, 205), 16, anchor_x="right")

    def contains(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def set_from_mouse(self, x):
        self.value = max(0.0, min(1.0, (x - self.x) / self.width))
        self.on_change(self.value)

    def draw(self):
        self.label_text.text = self.label
        self.label_text.x = self.x
        self.label_text.y = self.y + 42
        self.label_text.draw()
        self.value_text.text = f"{int(self.value * 100)}%"
        self.value_text.x = self.x + self.width
        self.value_text.y = self.y + 42
        self.value_text.draw()
        arcade.draw_lbwh_rectangle_filled(self.x, self.y + 11, self.width, 6, (55, 66, 78))
        arcade.draw_lbwh_rectangle_filled(self.x, self.y + 11, self.width * self.value, 6, (109, 155, 210))
        arcade.draw_circle_filled(self.x + self.width * self.value, self.y + 14, 10, (230, 238, 248))


class PauseDropdown:
    def __init__(self, key, label, options, selected_index, x, y, width, height, on_select):
        self.key = key
        self.label = label
        self.options = options
        self.selected_index = selected_index
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.on_select = on_select
        self.hovered_index = None
        self.scroll_offset = 0
        self.max_visible_options = 5
        self.label_text = arcade.Text(label, 0, 0, (225, 232, 240), 16)
        self.selected_text = arcade.Text("", 0, 0, (225, 232, 240), 17, anchor_y="center")
        self.arrow_text = arcade.Text("v", 0, 0, (180, 192, 205), 16, anchor_x="center", anchor_y="center")
        self.option_texts = [
            arcade.Text("", 0, 0, (225, 232, 240), 16, anchor_y="center")
            for _index in range(self.max_visible_options)
        ]

    def contains_header(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def visible_count(self):
        return min(len(self.options), self.max_visible_options)

    def max_scroll_offset(self):
        return max(0, len(self.options) - self.visible_count())

    def clamp_scroll(self):
        self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll_offset()))

    def scroll(self, amount):
        self.scroll_offset += int(amount)
        self.clamp_scroll()

    def option_at(self, x, y):
        if not (self.x <= x <= self.x + self.width):
            return None

        self.clamp_scroll()
        list_height = self.height * self.visible_count()
        list_y = self.y - list_height
        if not (list_y <= y <= list_y + list_height):
            return None

        visible_index = int((list_y + list_height - y) // self.height)
        visible_index = max(0, min(self.visible_count() - 1, visible_index))
        return self.scroll_offset + visible_index

    def draw(self, is_open=False):
        self.label_text.text = self.label
        self.label_text.x = self.x
        self.label_text.y = self.y + self.height + 8
        self.label_text.draw()
        arcade.draw_lbwh_rectangle_filled(self.x, self.y, self.width, self.height, (42, 55, 72))
        arcade.draw_lbwh_rectangle_outline(self.x, self.y, self.width, self.height, (100, 126, 155), 2)
        self.selected_text.text = self.options[self.selected_index]
        self.selected_text.x = self.x + 14
        self.selected_text.y = self.y + self.height / 2
        self.selected_text.draw()
        self.arrow_text.x = self.x + self.width - 18
        self.arrow_text.y = self.y + self.height / 2
        self.arrow_text.draw()

        if not is_open:
            return

        self.clamp_scroll()
        list_height = self.height * self.visible_count()
        list_y = self.y - list_height
        arcade.draw_lbwh_rectangle_filled(self.x, list_y, self.width, list_height, (31, 41, 53))
        arcade.draw_lbwh_rectangle_outline(self.x, list_y, self.width, list_height, (80, 102, 128), 2)

        for visible_index in range(self.visible_count()):
            index = self.scroll_offset + visible_index
            option = self.options[index]
            option_y = self.y - self.height * (visible_index + 1)
            if index == self.hovered_index:
                fill = (54, 72, 94)
            elif index == self.selected_index:
                fill = (63, 86, 116)
            else:
                fill = (31, 41, 53)
            arcade.draw_lbwh_rectangle_filled(self.x + 1, option_y, self.width - 2, self.height, fill)
            if visible_index > 0:
                arcade.draw_line(self.x, option_y, self.x + self.width, option_y, (80, 102, 128), 1)
            option_text = self.option_texts[visible_index]
            option_text.text = option
            option_text.x = self.x + 14
            option_text.y = option_y + self.height / 2
            option_text.draw()

        if self.max_scroll_offset() > 0:
            track_x = self.x + self.width - 7
            thumb_height = max(18, list_height * self.visible_count() / len(self.options))
            scroll_range = max(1, self.max_scroll_offset())
            thumb_space = list_height - thumb_height
            thumb_y = list_y + thumb_space * (1 - self.scroll_offset / scroll_range)
            arcade.draw_lbwh_rectangle_filled(track_x, list_y + 4, 3, list_height - 8, (64, 77, 92))
            arcade.draw_lbwh_rectangle_filled(track_x - 2, thumb_y + 4, 7, thumb_height - 8, (150, 170, 194))


class HudButton:
    def __init__(self, label, x, y, width, height, action):
        self.label = label
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.action = action
        self.text = arcade.Text(label, 0, 0, arcade.color.WHITE, 14, anchor_x="center", anchor_y="center")

    def set_label(self, label):
        self.label = label
        self.text.text = label

    def contains(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def draw(self, hovered=False):
        fill = (64, 82, 105) if hovered else (38, 48, 61)
        border = (160, 186, 214) if hovered else (92, 112, 136)
        arcade.draw_lbwh_rectangle_filled(self.x, self.y, self.width, self.height, fill)
        arcade.draw_lbwh_rectangle_outline(self.x, self.y, self.width, self.height, border, 1)
        self.text.x = self.x + self.width / 2
        self.text.y = self.y + self.height / 2
        self.text.draw()


@dataclass
class GameTimeSnapshot:
    current_time: datetime
    paused: bool
    speed_level: int
    hours_per_tick: int
    tick_count: int
    market_tick_count: int


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
    trade_modifiers: dict = None
    construction_modifiers: dict = None
    construction_queue: list = None
    divisions: list = None
    armies: list = None
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

    def __post_init__(self):
        if self.tile is not None and self.x == 0.0 and self.y == 0.0:
            self.x = self.tile.center_x
            self.y = self.tile.center_y


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


class LocalSimulationServer:
    def __init__(self):
        self.current_time = SIMULATION_START_TIME
        self.paused = True
        self.speed_level = 1
        self.tick_count = 0
        self.market_tick_count = 0
        self.pending_market_ticks = 0
        self.accumulator = 0.0
        self.market_state = MarketState()
        self.next_market_execution_time = self.next_weekly_market_time(self.current_time)

    @property
    def hours_per_tick(self):
        return SIMULATION_HOURS_PER_TICK[self.speed_level - 1]

    @staticmethod
    def next_weekly_market_time(current_time):
        days_until_monday = (0 - current_time.weekday()) % 7
        execution_time = datetime(
            current_time.year,
            current_time.month,
            current_time.day,
        ) + timedelta(days=days_until_monday)
        if execution_time <= current_time:
            execution_time += timedelta(days=7)
        return execution_time

    def update(self, delta_time):
        if self.paused:
            return

        self.accumulator += delta_time
        ticks_to_process = min(16, int(self.accumulator / SIMULATION_REAL_SECONDS_PER_TICK))
        if ticks_to_process <= 0:
            return

        self.accumulator -= ticks_to_process * SIMULATION_REAL_SECONDS_PER_TICK
        previous_time = self.current_time
        self.current_time += timedelta(hours=self.hours_per_tick * ticks_to_process)
        self.tick_count += ticks_to_process
        self.update_market_schedule(previous_time, self.current_time)

    def update_market_schedule(self, previous_time, current_time):
        while previous_time < self.next_market_execution_time <= current_time:
            self.pending_market_ticks += 1
            self.market_tick_count += 1
            self.market_state.last_execution_time = self.next_market_execution_time
            self.next_market_execution_time += timedelta(days=7)

    def consume_market_ticks(self):
        count = self.pending_market_ticks
        self.pending_market_ticks = 0
        return count

    def set_paused(self, paused):
        self.paused = paused
        if paused:
            self.accumulator = 0.0

    def toggle_pause(self):
        self.set_paused(not self.paused)

    def set_speed_level(self, speed_level):
        self.speed_level = max(1, min(5, speed_level))

    def change_speed(self, delta):
        self.set_speed_level(self.speed_level + delta)

    def snapshot(self):
        return GameTimeSnapshot(
            current_time=self.current_time,
            paused=self.paused,
            speed_level=self.speed_level,
            hours_per_tick=self.hours_per_tick,
            tick_count=self.tick_count,
            market_tick_count=self.market_tick_count,
        )


class LocalSimulationClient:
    def __init__(self, server):
        self.server = server
        self.snapshot = server.snapshot()

    def sync_from_server(self):
        self.snapshot = self.server.snapshot()

    def request_toggle_pause(self):
        self.server.toggle_pause()
        self.sync_from_server()

    def request_speed_change(self, delta):
        self.server.change_speed(delta)
        self.sync_from_server()



def create_hex_texture():
    """Создает белую текстуру гексагона с помощью PIL"""
    image_width = HEX_WIDTH
    image_height = int(HEX_HEIGHT * 1.2)
    image = Image.new('RGBA', (image_width, image_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    center_x = image_width / 2
    center_y = image_height / 2
    points = []
    for i in range(6):
        angle_deg = 60 * i + 30
        angle_rad = math.pi / 180 * angle_deg
        x = center_x + HEX_SIZE * math.cos(angle_rad)
        y = center_y + HEX_SIZE * math.sin(angle_rad)
        points.append((x, y))
    # Рисуем белый залитый гексагон
    draw.polygon(points, fill=(255, 255, 255))
    # Рисуем черный контур
    draw.polygon(points, outline=(0, 0, 0), width=2)
    # Конвертируем в текстуру Arcade
    texture = arcade.Texture(
        name=f"hex_texture",
        image=image,
        hit_box_algorithm=arcade.hitbox.algo_detailed
    )
    return texture


def create_hex_border_texture(color=(255, 255, 0), width=4, name="hex_texture_border"):
    image_width = HEX_WIDTH
    image_height = int(HEX_HEIGHT * 1.2)
    image = Image.new('RGBA', (image_width, image_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    center_x = image_width / 2
    center_y = image_height / 2
    points = []
    for i in range(6):
        angle_deg = 60 * i + 30
        angle_rad = math.pi / 180 * angle_deg
        x = center_x + HEX_SIZE * math.cos(angle_rad)
        y = center_y + HEX_SIZE * math.sin(angle_rad)
        points.append((x, y))
    # Рисуем черный контур
    draw.polygon(points, outline=color, width=width)
    # Конвертируем в текстуру Arcade
    texture = arcade.Texture(
        name=name,
        image=image,
        hit_box_algorithm=arcade.hitbox.algo_detailed
    )
    return texture


class WorldGenerator:
    def __init__(self, width, height, seed=None):
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else random.randint(0, 999999)

        # Основные шумы для рельефа
        self.noise_elevation = PerlinNoise(octaves=1.5, seed=self.seed)
        self.noise_elevation_large = PerlinNoise(octaves=3, seed=self.seed + 50)
        self.noise_elevation_medium = PerlinNoise(octaves=4, seed=self.seed + 100)
        self.noise_elevation_small = PerlinNoise(octaves=6, seed=self.seed + 150)

        # Шумы для формы континентов
        self.noise_continent = PerlinNoise(octaves=2, seed=self.seed + 200)
        self.noise_continent_detail = PerlinNoise(octaves=3, seed=self.seed + 250)

        # Шумы для горных хребтов
        self.noise_mountains = PerlinNoise(octaves=2, seed=self.seed + 300)
        self.noise_mountains_detail = PerlinNoise(octaves=4, seed=self.seed + 350)
        self.noise_ridge_direction = PerlinNoise(octaves=1, seed=self.seed + 380)

        # Шумы для влажности
        self.noise_moisture_base = PerlinNoise(octaves=1, seed=self.seed + 400)
        self.noise_moisture_detail = PerlinNoise(octaves=1.5, seed=self.seed + 450)
        self.noise_rain_shadow = PerlinNoise(octaves=2, seed=self.seed + 480)

        # Шумы для температуры
        self.noise_temp_base = PerlinNoise(octaves=0.5, seed=self.seed + 500)
        self.noise_temp_variation = PerlinNoise(octaves=2, seed=self.seed + 550)

        # Шумы для озер и рек
        self.noise_water_features = PerlinNoise(octaves=3, seed=self.seed + 600)
        self.noise_lake_basins = PerlinNoise(octaves=2, seed=self.seed + 650)

        print(f"Генерация мира с сидом: {self.seed}")

    def generate_elevation(self, x, y):
        period = (self.width + self.height) / (25 * (1.1 - MOUNTAIN_FREQUENCY))
        large = self.noise_elevation_large([x * 0.8 / period, y * 0.8 / period])
        large = (large + 1) / 2
        medium = self.noise_elevation_medium([x / period, y / period])
        medium = (medium + 1) / 2
        small = self.noise_elevation_small([x * 1.5 / period, y * 1.5 / period])
        small = (small + 1) / 2
        elevation = (0.4 + 1.2 * 0.8 * self.noise_elevation([x / period, y / period])) / 1
        elevation = elevation  # + large * 0.2 + medium * 0.2 + small * 0.2

        return min(1.0, max(0.0, elevation))

    def generate_ridges(self, x, y):
        """Генерирует горные хребты"""
        nx = x / self.width * 1.5
        ny = y / self.height * 1.5
        # Основной шум для хребтов
        ridge_base = self.noise_mountains([nx, ny])
        ridge_detail = self.noise_mountains_detail([nx * 2, ny * 2])
        # Направление хребтов
        dir_x = self.noise_ridge_direction([nx + 10, ny])
        dir_y = self.noise_ridge_direction([nx, ny + 10])
        # Создаем линейные структуры
        ridge = (ridge_base + ridge_detail) / 2
        ridge = (ridge + 1) / 2
        # Усиливаем вдоль определенного направления
        direction_strength = abs(dir_x * dir_y) * 2
        ridge = ridge * (0.7 + direction_strength * 0.3)
        # Применяем частоту
        if ridge < RIDGE_FREQUENCY:
            ridge = 0
        else:
            ridge = (ridge - RIDGE_FREQUENCY) / (1 - RIDGE_FREQUENCY)
            ridge = math.pow(ridge, RIDGE_SHARPNESS)
        return ridge

    def generate_temperature(self, x, y, elevation):
        period = (self.width + self.height) / 15
        noise = self.noise_temp_variation([x * 3 / period, y * 3 / period])
        base_temp = 0.5 + self.noise_temp_base([x / period, y / period]) * 0.5
        elevation_factor = 1.0 - elevation * 0.4
        temp = (base_temp + noise * 0.6) * elevation_factor
        if temp > TROPICAL_TEMP:
            temp = TROPICAL_TEMP
        elif temp < POLAR_TEMP:
            temp = POLAR_TEMP
        return max(0.05, min(1.0, temp))

    def generate_moisture(self, x, y, elevation):
        """Генерирует влажность с учетом рельефа и proximity к воде"""
        period = (self.width + self.height) / 20
        moisture_base = self.noise_moisture_base([x / period, y / period])
        moisture_base = (moisture_base + 1) / 2
        moisture_detail = self.noise_moisture_detail([x * 2 / period, y * 2 / period])
        moisture_detail = (moisture_detail + 1) / 2
        rain_shadow = self.noise_rain_shadow([x / period, y / period])
        rain_shadow = (rain_shadow + 1) / 2
        if elevation > 0.6:
            shadow_effect = rain_shadow * 0.5
            moisture_base = moisture_base * (1 - shadow_effect)
        elevation_factor = 1.0 - elevation * 0.4
        lowland_bonus = 0
        if WATER_LEVEL < elevation < SWAMP_ELEVATION:
            lowland_bonus = 0.2 * (1 - (elevation - WATER_LEVEL) / (SWAMP_ELEVATION - WATER_LEVEL))
        moisture = (moisture_base * 0.6 + moisture_detail * 0.4) * GLOBAL_MOISTURE
        moisture = moisture * elevation_factor + lowland_bonus

        return max(0.1, min(1.0, moisture))

    def resource_seed_for_tile(self, q, r):
        return (self.seed * 1_000_003 + q * 9_176 + r * 131_071) & 0xFFFFFFFF

    def generate_tile_data(self, q, r, x, y):
        base_elevation = self.generate_elevation(q, r)
        ridge = self.generate_ridges(q, r)
        ridge_lift = ridge * MOUNTAIN_HEIGHT * 0.35
        if base_elevation < WATER_LEVEL:
            ridge_lift *= 0.35
        elevation = min(1.0, max(0.0, base_elevation + ridge_lift))

        moisture = self.generate_moisture(q, r, elevation)
        temperature = self.generate_temperature(q, r, elevation)
        terrain_type = None

        if elevation > WATER_LEVEL and self.is_lake(q, r, elevation, temperature):
            terrain_type = "lake"
            elevation = WATER_LEVEL - 0.02
            moisture = self.generate_moisture(q, r, elevation)
            temperature = self.generate_temperature(q, r, elevation)

        tile_data = MapTileData(
            q=q,
            r=r,
            x=x,
            y=y,
            elevation=elevation,
            moisture=moisture,
            temperature=temperature,
            ridge_value=ridge,
            terrain_type=terrain_type,
        )
        resource_rng = random.Random(self.resource_seed_for_tile(q, r))
        tile_data.finalize_generation(resource_rng)
        return tile_data

    def is_lake(self, x, y, elevation=None, temperature=None):
        """Определяет, является ли тайл озером"""
        if elevation is None:
            elevation = self.generate_elevation(x, y)
        # Озера только на суше
        if elevation < WATER_LEVEL:
            return False
        # Озера только в не-холодных зонах
        if temperature is None:
            temperature = self.generate_temperature(x, y, elevation)
        if temperature < 0.2:
            return False
        # Шум для определения озерных котловин
        nx = x / self.width * 3
        ny = y / self.height * 3
        lake_basin = self.noise_lake_basins([nx, ny])
        lake_basin = (lake_basin + 1) / 2
        # Дополнительный шум для формы озер
        water_feature = self.noise_water_features([nx * 2, ny * 2])
        water_feature = (water_feature + 1) / 2
        # Озера в низинах
        is_depression = WATER_LEVEL < elevation < WATER_LEVEL + LAKE_SIZE * 0.3
        # Комбинируем условия
        lake_chance = lake_basin * water_feature
        return lake_chance > (1 - LAKE_FREQUENCY * 0.7) and is_depression


class Game(arcade.View):
    def __init__(self, difficulty="Normal", bot_count=3, map_size=None):
        super().__init__()
        arcade.set_background_color(arcade.color.BLACK)
        self.paused = False
        self.game_over = False
        self.difficulty = difficulty
        self.bot_count = max(0, min(MAX_BOTS, bot_count))
        self.map_size = map_size or WORLD_SIZE
        self.players = []
        self.human_player = None
        self.start_territory_radius = 3
        self.keys_pressed = set()
        self.hex_grid = []
        self.hex_lookup = {}
        self.tile_spatial_hash = {}
        self.tile_spatial_cell_size = max(HEX_WID, HEX_HGT * 0.75)
        self.hex_draw_list = arcade.shape_list.ShapeElementList()
        self.state_border_list = arcade.shape_list.ShapeElementList()
        self.state_border_segments = {}
        self.state_border_chunk_segments = {}
        self.state_border_chunk_lists = {}
        self.selected_tile = None
        self.selected_tiles = []
        self.hovered_tile = None
        self.world_camera = arcade.camera.Camera2D()
        self.gui_camera = arcade.camera.Camera2D()
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_camera_x = 0
        self.drag_start_camera_y = 0
        self.target_camera_x = 0
        self.target_camera_y = 0
        self.visible_tiles = arcade.SpriteList()
        self.visible_tiles_revision = 0
        self.visible_tiles_signature = ()
        self.tile_visual_sprite_list = arcade.SpriteList()
        self.tile_visual_cache_key = None
        self.tile_visual_revision = 0
        self.last_visible_update = 0
        self.last_mouse_check = 0
        self.visible_update_interval = 0.1
        self.map_bounds = (0, 0, 0, 0)
        self.map_overview_sprite = None
        self.map_overview_sprite_list = arcade.SpriteList()
        self.map_overview_image = None
        self.map_overview_params = None
        self.map_overview_signature = None
        self.map_overview_revision = 0
        self.map_overview_dirty_tile_keys = set()
        self.map_overview_last_partial_update = 0.0
        self.ownership_dirty_tile_keys = set()
        self.map_overview_dirty = False
        self.fps = 0
        self.fps_frame_count = 0
        self.fps_timer = 0
        self.world_generator = None
        self.world_seed = random.randint(0, 999999)
        self.selection_border = None
        self.selection_border_sprite_list = arcade.SpriteList()
        self.divisions = []
        self.division_templates = self.load_division_templates()
        self.battles = {}
        self.next_division_id = 1
        self.next_army_id = 1
        self.next_battle_plan_id = 1
        self.selected_division_ids = set()
        self.division_shape_list = arcade.shape_list.ShapeElementList()
        self.division_route_shape_list = arcade.shape_list.ShapeElementList()
        self.division_route_cache_key = None
        self.division_group_shape_list = arcade.shape_list.ShapeElementList()
        self.division_list_icon_shape_list = arcade.shape_list.ShapeElementList()
        self.division_display_positions = {}
        self.division_group_texts = []
        self.division_tile_stack_texts = []
        self.division_render_cache_key = None
        self.division_groups_cache_key = None
        self.division_groups = []
        self.battle_indicator_rects = []
        self.selected_battle_id = None
        self.battle_panel_rect = None
        self.battle_panel_close_rect = None
        self.division_selection_drag_active = False
        self.division_selection_drag_started = False
        self.division_selection_start = (0, 0)
        self.division_selection_current = (0, 0)
        self.pending_map_click = None
        self.last_division_click_time = 0.0
        self.last_division_click_id = None
        self.division_list_scroll_index = 0
        self.division_list_scroll_indices = {}
        self.division_list_row_rects = []
        self.division_list_panel_rect = None
        self.division_list_panel_rects = []
        self.division_list_header_rects = []
        self.division_list_close_rects = []
        self.active_division_list_army_id = None
        self.division_detach_button_rect = None
        self.hovered_division_detach_button = False
        self.army_command_card_rects = []
        self.army_command_add_rect = None
        self.army_plan_button_rects = []
        self.hovered_army_plan_button = None
        self.army_plan_mode = None
        self.army_plan_army_id = None
        self.army_plan_drag_active = False
        self.army_plan_start_tile = None
        self.army_plan_preview_tiles = []
        self.army_plan_preview_target_owner = None
        self.batch = Batch()
        self.tooltip_batch = Batch()
        self.debug_text = arcade.Text(
            "",
            0,
            0,
            arcade.color.YELLOW,
            12,
            anchor_x="right",
            anchor_y="top",
        )
        self.simulation_server = LocalSimulationServer()
        self.simulation_client = LocalSimulationClient(self.simulation_server)
        self.last_production_tick_count = 0
        self.time_panel_rect = (0, 0, 0, 0)
        self.time_buttons = []
        self.hovered_time_button = None
        self.time_date_text = arcade.Text("", 0, 0, (225, 232, 240), 15, anchor_x="center", anchor_y="center")
        self.time_clock_text = arcade.Text("", 0, 0, (225, 232, 240), 13, anchor_x="center", anchor_y="center")
        self.ui_text_pool = []
        self.ui_text_pool_cursor = 0
        self.ui_text_pool_max_used = 0
        self.tooltip_text_pool = []
        self.tooltip_text_pool_cursor = 0
        self.tooltip_text_pool_max_used = 0
        self.map_layer = "terrain"
        self.map_layer_menu_open = False
        self.map_layer_menu_progress = 0.0
        self.hovered_map_layer_button = False
        self.hovered_map_layer_option = None
        self.resource_group_index = 0
        self.resource_group_menu_open = False
        self.resource_group_menu_progress = 0.0
        self.hovered_resource_group_button = False
        self.hovered_resource_group_option = None
        self.map_layer_message = ""
        self.map_layer_message_timer = 0.0
        self.top_nav_buttons = []
        self.top_nav_icon_textures = self.load_top_nav_icon_textures()
        self.hovered_top_nav_key = None
        self.warning_icon_rects = {}
        self.hovered_warning_key = None
        self.active_top_panel_key = None
        self.side_panel_progress = 0.0
        self.side_panel_target = 0.0
        self.hovered_side_panel_close = False
        self.resource_panel_category = "raw"
        self.selected_resource_key = None
        self.resource_scroll_index = 0
        self.resource_rows_cache = None
        self.budget_summary_rect = None
        self.hovered_budget_summary = False
        self.population_summary_rect = None
        self.hovered_population_summary = False
        self.resource_summary_rect = None
        self.hovered_resource_summary = False
        self.resource_warning_rects = []
        self.selected_resource_signal_cache_key = None
        self.selected_resource_signal_cache = {}
        self.trade_panel_category = "raw"
        self.trade_scroll_index = 0
        self.trade_action_rects = []
        self.trade_category_rects = []
        self.trade_panel_cache = None
        self.trade_text_pool = []
        self.trade_text_pool_cursor = 0
        self.construction_queue_expanded = False
        self.selected_construction_index = 0
        self.construction_placement_mode = False
        self.construction_placement_cache_key = None
        self.construction_placement_tile_cache = {}
        self.construction_placement_label_items = []
        self.construction_placement_label_texts = []
        self.construction_placement_text_cache = {}
        self.construction_placement_label_rects = []
        self.construction_placement_label_shapes = arcade.shape_list.ShapeElementList()
        self.construction_hover_tooltip_cache_key = None
        self.construction_hover_tooltip_cache_data = None
        self.construction_queue_toggle_rect = None
        self.construction_queue_priority_rects = []
        self.construction_building_rects = []
        self.construction_start_button_rect = None
        self.construction_pause_button_rect = None
        self.hovered_hex_panel_close = False
        self.hovered_hex_build_button = False
        self.hovered_hex_specialization_button = False
        self.hex_panel_scroll = 0.0
        self.hex_panel_content_height = 0.0
        self.hex_resources_expanded = False
        self.hex_resources_toggle_rect = None
        self.hex_panel_specialization_mode = False
        self.hex_specialization_row_rects = []
        self.hex_panel_message = ""
        self.hex_panel_message_timer = 0.0
        self.map_layer_icon_texture = arcade.load_texture(str(LAYER_ICON_PATH))
        self.tile_visual_textures = self.load_tile_visual_textures()
        self.premium_shader_program = None
        self.premium_shader_geometry = None
        self.premium_shader_enabled = False
        self.premium_shader_attempted = False
        self.shader_time = 0.0
        self.pause_buttons = []
        self.hovered_pause_button = None
        self.pause_message = ""
        self.pause_screen = "menu"
        self.pause_sliders = []
        self.pause_dropdowns = []
        self.active_pause_slider = None
        self.open_pause_dropdown = None
        settings = load_settings(RESOLUTIONS)
        self.sound_volume = settings["sound_volume"]
        self.music_volume = settings["music_volume"]
        self.fullscreen = settings["fullscreen"]
        self.resolution_index = settings["resolution_index"]
        self.pending_fullscreen = self.fullscreen
        self.pending_resolution_index = self.resolution_index

        self.setup()

    def load_division_templates(self):
        templates = {}
        try:
            data = json.loads(DIVISION_TEMPLATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Division template load failed: {error}")
            data = {}

        raw_templates = data.get("templates", data) if isinstance(data, dict) else {}
        if isinstance(raw_templates, dict):
            for key, template_data in raw_templates.items():
                if isinstance(template_data, dict):
                    templates[key] = self.normalize_division_template(key, template_data)

        if "basic_infantry" not in templates:
            templates["basic_infantry"] = self.normalize_division_template(
                "basic_infantry",
                {"name": "Пехотная дивизия"},
            )
        return templates

    def normalize_division_template(self, key, template_data):
        template = dict(DIVISION_TEMPLATE_DEFAULTS)
        template.update(template_data)
        template["key"] = str(key)
        template["name"] = str(template.get("name") or key)
        template["icon"] = str(template.get("icon") or "infantry")
        for field_name in DIVISION_TEMPLATE_NUMERIC_FIELDS:
            fallback = DIVISION_TEMPLATE_DEFAULTS[field_name]
            try:
                value = float(template.get(field_name, fallback))
            except (TypeError, ValueError):
                value = float(fallback)
            if field_name == "manpower":
                value = max(0, int(round(value)))
            else:
                value = max(0.0, value)
            template[field_name] = value
        total_share = template["infantry_share"] + template["vehicle_share"]
        if total_share > 0:
            template["infantry_share"] /= total_share
            template["vehicle_share"] /= total_share
        else:
            template["infantry_share"] = DIVISION_TEMPLATE_DEFAULTS["infantry_share"]
            template["vehicle_share"] = DIVISION_TEMPLATE_DEFAULTS["vehicle_share"]
        return template

    def register_division_template(self, key, template_data):
        template = self.normalize_division_template(key, template_data)
        self.division_templates[template["key"]] = template
        return template

    def division_template(self, template_key):
        return self.division_templates.get(template_key) or self.division_templates["basic_infantry"]

    def create_division_from_template(self, player, tile, template_key):
        template = self.division_template(template_key)
        division = Division(
            id=self.next_division_id,
            owner=player,
            template_key=template["key"],
            tile=tile,
            target_tile=None,
            path=[],
            manpower=template["manpower"],
            organization=template["organization"],
            max_organization=template["organization"],
            strength=template["strength"],
            max_strength=template["strength"],
            speed=template["speed"],
            organization_recovery=template["organization_recovery"],
            initiative=template["initiative"],
            front_width=template["front_width"],
            reliability=template["reliability"],
            recon=template["recon"],
            camouflage=template["camouflage"],
            soft_attack=template["soft_attack"],
            defense=template["defense"],
            breakthrough=template["breakthrough"],
            hard_front_attack=template["hard_front_attack"],
            hard_top_attack=template["hard_top_attack"],
            front_piercing=template["front_piercing"],
            top_piercing=template["top_piercing"],
            front_armor=template["front_armor"],
            top_armor=template["top_armor"],
            infantry_share=template["infantry_share"],
            vehicle_share=template["vehicle_share"],
        )
        self.next_division_id += 1
        return division

    def setup(self):
        self.grid_width = self.map_size
        self.grid_height = self.map_size
        self.world_generator = WorldGenerator(self.grid_width, self.grid_height, self.world_seed)
        self.create_hex_grid()
        self.build_tile_spatial_hash()
        self.setup_players_and_states()
        self.setup_premium_shader()
        self.update_map_bounds()
        self.create_map_overview()
        self.selection_border = arcade.Sprite(create_hex_border_texture())
        self.selection_border_sprite_list.append(self.selection_border)
        self.selection_border.visible = False
        min_x, min_y, max_x, max_y = self.map_bounds
        capital_tile = self.human_player.capital_tile if self.human_player else None
        if capital_tile:
            center_x = capital_tile.center_x
            center_y = capital_tile.center_y
        else:
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
        self.world_camera.position = self.clamp_camera_position(center_x, center_y)
        self.target_camera_x, self.target_camera_y = self.world_camera.position
        self.rebuild_pause_menu()
        self.rebuild_time_hud()
        self.rebuild_top_ui()

    def rebuild_time_hud(self):
        if not self.window:
            return

        panel_width = 300
        panel_height = 72
        panel_x = self.window.width - panel_width - 12
        panel_y = self.window.height - TOP_UI_HEIGHT - panel_height - 10
        self.time_panel_rect = (panel_x, panel_y, panel_width, panel_height)
        self.time_buttons = [
            HudButton("-", panel_x + 14, panel_y + 10, 28, 24, self.decrease_time_speed),
            HudButton(">", panel_x + 48, panel_y + 10, 38, 24, self.toggle_time_pause),
            HudButton("+", panel_x + 92, panel_y + 10, 28, 24, self.increase_time_speed),
        ]

    def rebuild_top_ui(self):
        if not self.window:
            return

        button_size = 38
        gap = 7
        x = 12
        y = self.window.height - TOP_UI_HEIGHT + 4
        self.top_nav_buttons = []
        for key, label, _icon_name in TOP_NAV_TABS:
            self.top_nav_buttons.append({
                "key": key,
                "label": label,
                "rect": (x, y, button_size, button_size),
            })
            x += button_size + gap

    def invalidate_tile_visual_cache(self):
        self.tile_visual_cache_key = None

    def invalidate_construction_placement_cache(self):
        self.construction_placement_cache_key = None
        self.construction_placement_tile_cache = {}
        self.construction_placement_label_items = []
        self.construction_placement_label_texts = []
        self.construction_placement_label_rects = []
        self.construction_placement_label_shapes = arcade.shape_list.ShapeElementList()

    def invalidate_selected_resource_signal_cache(self):
        self.selected_resource_signal_cache_key = None
        self.selected_resource_signal_cache = {}

    def refresh_visible_tiles_signature(self):
        signature = tuple((tile.q, tile.r) for tile in self.visible_tiles)
        if signature == self.visible_tiles_signature:
            return

        self.visible_tiles_signature = signature
        self.visible_tiles_revision += 1
        self.invalidate_tile_visual_cache()
        self.invalidate_construction_placement_cache()
        self.invalidate_selected_resource_signal_cache()

    @staticmethod
    def empty_resource_totals():
        return {"raw": {}}

    @staticmethod
    def empty_resource_stockpiles():
        return {
            "raw": {},
            "semi_finished": {},
            "finished": {},
        }

    @staticmethod
    def empty_production_cache():
        return {
            stage: {"inputs": {}, "outputs": {}}
            for stage in PRODUCTION_STAGES
        }

    @staticmethod
    def resource_names_for_category(category_key):
        if category_key == "raw":
            return RAW_RESOURCE_NAMES
        if category_key == "semi_finished":
            return SEMI_FINISHED_RESOURCE_NAMES
        if category_key == "finished":
            return FINISHED_RESOURCE_NAMES
        return []

    @staticmethod
    def resource_category_for_key(resource_key):
        if resource_key in FINISHED_RESOURCE_NAMES:
            return "finished"
        if resource_key in SEMI_FINISHED_RESOURCE_NAMES:
            return "semi_finished"
        return "raw"

    def player_starting_scale(self, player=None, land_tile_count=None):
        if land_tile_count is None and player is not None:
            land_tile_count = sum(1 for tile in player.tiles if not self.is_water_tile(tile))
        land_tile_count = land_tile_count or STARTING_REFERENCE_LAND_TILES
        territory_scale = land_tile_count / STARTING_REFERENCE_LAND_TILES
        map_scale = max(0.65, min(1.8, self.map_size / STARTING_REFERENCE_MAP_SIZE))
        scale = territory_scale * (map_scale ** 0.45)
        return max(STARTING_MIN_SCALE, min(STARTING_MAX_SCALE, scale))

    def apply_starting_profile(self, player):
        scale = self.player_starting_scale(player)
        player.starting_scale = scale
        player.population = round(STARTING_POPULATION * scale)
        player.budget = STARTING_BUDGET * (0.65 + scale * 0.35)
        self.create_starting_stockpiles(player, scale)

    @staticmethod
    def scaled_starting_infrastructure_budget(scale):
        budget_scale = max(0.45, min(2.6, scale ** 0.88))
        return {
            key: value * budget_scale
            for key, value in STARTING_INFRASTRUCTURE_BUDGET.items()
        }

    def create_starting_stockpiles(self, player, scale=1.0):
        rng = random.Random((self.world_seed + 1) * 1009)
        stockpiles = self.empty_resource_stockpiles()

        for category_key, (min_amount, max_amount) in STARTING_STOCK_RANGES.items():
            for resource_key in self.resource_names_for_category(category_key):
                multiplier = STARTING_STOCK_MULTIPLIERS.get(resource_key, 1.0)
                amount = rng.uniform(min_amount, max_amount) * multiplier * scale
                stockpiles[category_key][resource_key] = amount

        player.resource_stockpiles = stockpiles
        return stockpiles

    def ensure_player_stockpiles(self, player):
        stockpiles = player.resource_stockpiles or self.empty_resource_stockpiles()
        changed = False
        scale = getattr(player, "starting_scale", self.player_starting_scale(player))

        for category_key, (min_amount, max_amount) in STARTING_STOCK_RANGES.items():
            bucket = stockpiles.setdefault(category_key, {})
            for resource_key in self.resource_names_for_category(category_key):
                if resource_key in bucket:
                    continue
                resource_seed = sum((index + 1) * ord(char) for index, char in enumerate(resource_key))
                rng = random.Random((self.world_seed + 1) * 1009 + player.id * 7919 + resource_seed)
                multiplier = STARTING_STOCK_MULTIPLIERS.get(resource_key, 1.0)
                bucket[resource_key] = rng.uniform(min_amount, max_amount) * multiplier * scale
                changed = True

        if changed or player.resource_stockpiles is None:
            player.resource_stockpiles = stockpiles
            self.mark_player_stockpiles_changed(player)
        return stockpiles

    @staticmethod
    def mark_player_resource_balance_dirty(player):
        if player:
            player.resource_balance_dirty = True

    @staticmethod
    def mark_player_storage_dirty(player):
        if player:
            player.storage_dirty = True
            player.tile_stockpiles_dirty = True
            player.resource_balance_dirty = True

    def mark_player_stockpiles_changed(self, player):
        self.mark_player_resource_balance_dirty(player)
        if player:
            player.tile_stockpiles_dirty = True

    def cached_resource_balance_breakdown(self, player, max_age=0.35):
        if not player:
            return {}
        now = time.time()
        last_update = getattr(player, "resource_balance_last_update", 0.0)
        if (
            not player.resource_balance_breakdown
            or last_update <= 0
            or (player.resource_balance_dirty and now - last_update >= max_age)
        ):
            return self.recalculate_resource_balance_breakdown(player)
        return player.resource_balance_breakdown

    def ensure_player_storage(self, player):
        if not player:
            return self.empty_storage_summary(), self.empty_storage_summary(), self.empty_storage_summary()
        if (
            player.storage_dirty
            or not player.storage_capacity
            or not player.storage_used
            or not player.storage_overflow
        ):
            return self.recalculate_player_storage(player)
        return player.storage_capacity, player.storage_used, player.storage_overflow

    def ensure_player_tile_stockpiles(self, player):
        if player and getattr(player, "tile_stockpiles_dirty", True):
            self.distribute_player_stockpiles_to_tiles(player)

    @staticmethod
    def empty_tile_stockpiles():
        return {
            "raw": {},
            "semi_finished": {},
            "finished": {},
        }

    @staticmethod
    def storage_bucket_for_resource(resource_key):
        return "fuel" if resource_key in FUEL_STORAGE_RESOURCE_KEYS else Game.resource_category_for_key(resource_key)

    @staticmethod
    def empty_storage_summary():
        return {category: 0.0 for category in STORAGE_CATEGORIES}

    def tile_storage_capacity_by_category(self, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        capacities = self.empty_storage_summary()
        for category_key, building_values in STORAGE_CAPACITY_BY_COVERAGE.items():
            for building_key, capacity_per_coverage in building_values.items():
                capacities[category_key] += coverage.get(building_key, 0.0) * capacity_per_coverage
        for building_key, capacity_per_coverage in FUEL_STORAGE_CAPACITY_BY_COVERAGE.items():
            capacities["fuel"] += coverage.get(building_key, 0.0) * capacity_per_coverage
        return capacities

    def tile_storage_capacity(self, tile, category_key=None):
        capacities = self.tile_storage_capacity_by_category(tile)
        if category_key:
            return capacities.get(category_key, 0.0)
        return sum(capacities.get(key, 0.0) for key in ("raw", "semi_finished", "finished"))

    def tile_fuel_storage_capacity(self, tile):
        return self.tile_storage_capacity(tile, "fuel")

    def tile_storage_used_by_category(self, tile):
        used = self.empty_storage_summary()
        for category_bucket in (getattr(tile, "resource_stockpiles", {}) or {}).values():
            for resource_key, amount in category_bucket.items():
                storage_key = self.storage_bucket_for_resource(resource_key)
                used[storage_key] = used.get(storage_key, 0.0) + max(0.0, amount)
        return used

    def storage_summary_for_tiles(self, tiles):
        capacity = self.empty_storage_summary()
        used = self.empty_storage_summary()
        for tile in tiles:
            tile_capacity = self.tile_storage_capacity_by_category(tile)
            tile_used = self.tile_storage_used_by_category(tile)
            for category_key in STORAGE_CATEGORIES:
                capacity[category_key] += tile_capacity.get(category_key, 0.0)
                used[category_key] += tile_used.get(category_key, 0.0)
        return capacity, used

    def recalculate_player_storage(self, player):
        capacity = self.empty_storage_summary()
        used = self.empty_storage_summary()
        efficiency = (player.production_modifiers or {}).get("storage_efficiency", 1.0)

        for tile in player.tiles:
            tile_capacity = self.tile_storage_capacity_by_category(tile)
            for category_key, amount in tile_capacity.items():
                capacity[category_key] += amount * efficiency

        stockpiles = self.ensure_player_stockpiles(player)
        for category_key, bucket in stockpiles.items():
            for resource_key, amount in bucket.items():
                storage_key = self.storage_bucket_for_resource(resource_key)
                used[storage_key] = used.get(storage_key, 0.0) + max(0.0, amount)

        overflow = {
            category_key: max(0.0, used.get(category_key, 0.0) - capacity.get(category_key, 0.0))
            for category_key in STORAGE_CATEGORIES
        }
        player.storage_capacity = capacity
        player.storage_used = used
        player.storage_overflow = overflow
        player.storage_dirty = False
        return capacity, used, overflow

    def storage_free_capacity_for_resource(self, player, resource_key):
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_key = self.storage_bucket_for_resource(resource_key)
        return max(0.0, capacity.get(storage_key, 0.0) - used.get(storage_key, 0.0))

    def enforce_player_storage_capacity(self, player):
        capacity, used, overflow = self.recalculate_player_storage(player)
        if not any(amount > 0 for amount in overflow.values()):
            return overflow

        stockpiles = self.ensure_player_stockpiles(player)
        removed = self.empty_storage_summary()
        for storage_key, overflow_amount in overflow.items():
            if overflow_amount <= 0:
                continue
            resources = []
            for category_key, bucket in stockpiles.items():
                for resource_key, amount in bucket.items():
                    if amount > 0 and self.storage_bucket_for_resource(resource_key) == storage_key:
                        resources.append((category_key, resource_key, amount))
            total_amount = sum(amount for _category, _key, amount in resources)
            if total_amount <= 0:
                continue
            keep_ratio = max(0.0, min(1.0, capacity.get(storage_key, 0.0) / total_amount))
            for category_key, resource_key, amount in resources:
                new_amount = amount * keep_ratio
                stockpiles[category_key][resource_key] = new_amount
                removed[storage_key] += max(0.0, amount - new_amount)

        self.recalculate_player_storage(player)
        player.tile_stockpiles_dirty = False
        player.storage_overflow = removed
        return removed

    def distribute_player_stockpiles_to_tiles(self, player):
        for tile in player.tiles:
            tile.resource_stockpiles = self.empty_tile_stockpiles()

        capacity_tiles = {
            category_key: []
            for category_key in STORAGE_CATEGORIES
        }
        for tile in player.tiles:
            capacities = self.tile_storage_capacity_by_category(tile)
            for category_key, capacity in capacities.items():
                if capacity > 0:
                    capacity_tiles[category_key].append((tile, capacity))

        if not any(capacity_tiles[key] for key in ("raw", "semi_finished", "finished")):
            fallback_tile = player.capital_tile or next((tile for tile in player.tiles if not self.is_water_tile(tile)), None)
            if fallback_tile:
                self.set_tile_building_coverage(fallback_tile, "warehouse", 0.12, INFRASTRUCTURE_COVERAGE_LIMITS["warehouse"][1])
                capacities = self.tile_storage_capacity_by_category(fallback_tile)
                for category_key in ("raw", "semi_finished", "finished"):
                    capacity_tiles[category_key] = [(fallback_tile, capacities.get(category_key, 0.0))]
        if not capacity_tiles["fuel"]:
            fallback_tile = player.capital_tile or next((tile for tile in player.tiles if not self.is_water_tile(tile)), None)
            if fallback_tile:
                self.set_tile_building_coverage(fallback_tile, "fuel_storage", 0.14, INFRASTRUCTURE_COVERAGE_LIMITS["fuel_storage"][1])
                capacity_tiles["fuel"] = [(fallback_tile, self.tile_fuel_storage_capacity(fallback_tile))]

        total_capacity = {
            category_key: sum(capacity for _tile, capacity in tiles)
            for category_key, tiles in capacity_tiles.items()
        }

        self.enforce_player_storage_capacity(player)
        stockpiles = self.ensure_player_stockpiles(player)
        for category_key, bucket in stockpiles.items():
            for resource_key, amount in bucket.items():
                if amount <= 0:
                    continue
                storage_key = self.storage_bucket_for_resource(resource_key)
                target_tiles = capacity_tiles.get(storage_key, [])
                target_capacity = total_capacity.get(storage_key, 0.0)
                if target_capacity <= 0:
                    continue
                for tile, capacity in target_tiles:
                    share = capacity / target_capacity
                    tile_bucket = tile.resource_stockpiles.setdefault(category_key, {})
                    tile_bucket[resource_key] = tile_bucket.get(resource_key, 0.0) + amount * share

        self.recalculate_player_storage(player)

    @staticmethod
    def add_resource_amount(bucket, key, amount):
        bucket[key] = bucket.get(key, 0.0) + max(0.0, amount)

    @staticmethod
    def raw_amount(raw, key):
        return raw.get(key, 0.0)

    def recalculate_state_resources(self, player):
        totals = self.empty_resource_totals()
        raw = totals["raw"]
        sources = {}

        for tile in player.tiles:
            tile_resources = set()
            for resource in tile.resources:
                if len(resource) < 3:
                    continue
                name, _depth, mass = resource
                amount = float(mass)
                self.add_resource_amount(raw, name, amount)
                if amount > 0:
                    tile_resources.add(name)
            for name in tile_resources:
                sources[name] = sources.get(name, 0) + 1

        player.resource_totals = totals
        player.resource_sources = sources
        self.mark_player_resource_balance_dirty(player)
        return totals

    def recalculate_all_state_resources(self):
        for player in self.players:
            self.recalculate_state_resources(player)

    def tile_supply_source_strength(self, player, tile):
        if not tile or self.is_water_tile(tile):
            return 0.0
        coverage = getattr(tile, "building_coverage", {}) or {}
        strength = 0.0
        for building_key, weight in SUPPLY_SOURCE_WEIGHTS.items():
            strength += max(0.0, coverage.get(building_key, 0.0)) * weight
        if tile == player.capital_tile:
            strength += 0.85
        return self.clamp01(strength)

    def recalculate_player_supply(self, player):
        land_tiles = [tile for tile in player.tiles if not self.is_water_tile(tile)]
        if not land_tiles:
            player.supply_summary = {"average": 0.0, "low_tiles": 0, "critical_tiles": 0}
            return player.supply_summary

        sources = [
            (tile, strength)
            for tile in land_tiles
            for strength in [self.tile_supply_source_strength(player, tile)]
            if strength > 0
        ]
        if not sources and player.capital_tile:
            sources = [(player.capital_tile, 0.65)]

        total_supply = 0.0
        low_tiles = 0
        critical_tiles = 0
        for tile in land_tiles:
            passability = self.clamp01(getattr(tile, "passability", 0.0))
            best = 0.0
            for source_tile, strength in sources:
                distance = self.hex_distance(tile, source_tile)
                if distance > SUPPLY_SOURCE_RADIUS:
                    continue
                distance_factor = SUPPLY_DECAY_PER_HEX ** distance
                passability_factor = 0.42 + passability * 0.58
                best = max(best, strength * distance_factor * passability_factor)
            tile.supply_score = self.clamp01(best)
            total_supply += tile.supply_score
            if tile.supply_score < 0.25:
                critical_tiles += 1
            elif tile.supply_score < 0.50:
                low_tiles += 1

        for _pass_index in range(2):
            changed_tiles = []
            for tile in land_tiles:
                coverage = getattr(tile, "building_coverage", {}) or {}
                relay_strength = sum(
                    coverage.get(building_key, 0.0) * weight
                    for building_key, weight in SUPPLY_RELAY_BUILDING_WEIGHTS.items()
                )
                if relay_strength <= 0:
                    continue
                tile_passability = self.clamp01(getattr(tile, "passability", 0.0))
                for neighbor in self.neighbor_tiles(tile):
                    if neighbor.owner != player or self.is_water_tile(neighbor):
                        continue
                    inbound = getattr(neighbor, "supply_score", 0.0) * (0.46 + relay_strength * 0.38) * (
                        0.62 + tile_passability * 0.28
                    )
                    if inbound > getattr(tile, "supply_score", 0.0) + 0.001:
                        changed_tiles.append((tile, self.clamp01(inbound)))
                if getattr(tile, "supply_score", 0.0) <= 0.35:
                    continue
                relay_value = self.clamp01(tile.supply_score * (0.42 + relay_strength))
                for neighbor in self.neighbor_tiles(tile):
                    if neighbor.owner != player or self.is_water_tile(neighbor):
                        continue
                    passability = self.clamp01(getattr(neighbor, "passability", 0.0))
                    candidate = relay_value * (0.58 + passability * 0.30)
                    if candidate > getattr(neighbor, "supply_score", 0.0) + 0.001:
                        changed_tiles.append((neighbor, self.clamp01(candidate)))
            for tile, value in changed_tiles:
                tile.supply_score = max(getattr(tile, "supply_score", 0.0), value)

        total_supply = 0.0
        low_tiles = 0
        critical_tiles = 0
        for tile in land_tiles:
            total_supply += getattr(tile, "supply_score", 0.0)
            if tile.supply_score < 0.25:
                critical_tiles += 1
            elif tile.supply_score < 0.50:
                low_tiles += 1

        for tile in player.tiles:
            if self.is_water_tile(tile):
                tile.supply_score = 0.0

        average = total_supply / max(1, len(land_tiles))
        player.supply_summary = {
            "average": average,
            "low_tiles": low_tiles,
            "critical_tiles": critical_tiles,
        }
        return player.supply_summary

    def recalculate_all_supply_scores(self):
        for player in self.players:
            self.recalculate_player_supply(player)

    @staticmethod
    def add_production_amount(cache, stage, direction, key, amount):
        if amount <= 0:
            return
        bucket = cache[stage][direction]
        bucket[key] = bucket.get(key, 0.0) + amount

    def merge_production_cache(self, target, source, multiplier=1.0):
        for stage in PRODUCTION_STAGES:
            for direction in ["inputs", "outputs"]:
                for key, amount in source.get(stage, {}).get(direction, {}).items():
                    self.add_production_amount(target, stage, direction, key, amount * multiplier)

    @staticmethod
    def specialization_efficiency(allocation, penalty=0.9, free_specializations=1):
        sector_count = sum(1 for value in allocation.values() if value > 0)
        penalty_steps = max(0, sector_count - free_specializations)
        return penalty ** penalty_steps

    @staticmethod
    def normalize_industry_allocation(allocation):
        clean_sectors = [
            sector
            for sector, value in (allocation or {}).items()
            if sector in INDUSTRY_SECTOR_LABELS and value > 0
        ]
        if not clean_sectors:
            clean_sectors = ["consumer_goods"]
        clean_sectors = list(dict.fromkeys(clean_sectors))
        share = 1.0 / max(1, len(clean_sectors))
        return {
            sector: share
            for sector in clean_sectors
        }

    def resource_score_near_tile(self, player, tile, weights, radius=3):
        score = self.weighted_resource_score(tile, weights)
        return self.clamp01(score + self.nearby_resource_score(player, tile, weights, radius) * 0.75)

    def industry_sector_scores(self, player, tile):
        scores = {}
        for sector, weights in INDUSTRY_SECTOR_RESOURCE_WEIGHTS.items():
            scores[sector] = self.resource_score_near_tile(player, tile, weights, radius=3) if weights else 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_village = self.nearby_coverage_score(player, tile, ["village"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        nearby_mine = self.nearby_coverage_score(player, tile, ["mine"], 2)
        nearby_refinery = self.nearby_coverage_score(player, tile, ["refinery"], 2)
        passability = self.clamp01(getattr(tile, "passability", 0.0))

        scores["consumer_goods"] = self.clamp01(
            0.16
            + nearby_city * 0.82
            + nearby_village * 0.34
            + passability * 0.20
        )
        scores["machinery"] += nearby_city * 0.28 + nearby_mine * 0.24 + passability * 0.14
        scores["vehicles"] += nearby_city * 0.20 + nearby_port * 0.18 + nearby_refinery * 0.14 + passability * 0.12
        scores["metallurgy"] += nearby_mine * 0.18
        scores["construction_materials"] += nearby_city * 0.16 + nearby_mine * 0.10
        scores["chemicals"] += nearby_refinery * 0.24 + nearby_city * 0.10
        scores["electronics"] += nearby_city * 0.30 + passability * 0.08
        scores["shipbuilding"] += nearby_port * 0.65
        scores["weapons"] += nearby_city * 0.12 + scores["metallurgy"] * 0.14

        return {key: self.clamp01(value) for key, value in scores.items()}

    def assign_industry_allocation(self, player, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        if coverage.get("industry", 0.0) <= 0:
            tile.industry_allocation = {}
            return {}

        ranked = sorted(
            self.industry_sector_scores(player, tile).items(),
            key=lambda item: item[1],
            reverse=True,
        )
        ranked = [(sector, score) for sector, score in ranked if score > 0.05]
        if not ranked:
            ranked = [("consumer_goods", 0.5)]

        sectors = [ranked[0][0]]
        if len(ranked) > 1 and ranked[1][1] >= ranked[0][1] * 0.72:
            sectors.append(ranked[1][0])
        if len(ranked) > 2 and ranked[2][1] >= ranked[0][1] * 0.88:
            sectors.append(ranked[2][0])

        tile.industry_allocation = self.normalize_industry_allocation({
            sector: 1.0
            for sector in sectors
        })
        return tile.industry_allocation

    def add_consumer_goods_share_to_tile(self, tile, target_share):
        allocation = self.normalize_industry_allocation(getattr(tile, "industry_allocation", {}) or {})
        current_share = allocation.get("consumer_goods", 0.0)
        if current_share >= target_share:
            return False

        sectors = [key for key in allocation if key != "consumer_goods"]
        sectors.insert(0, "consumer_goods")
        while len(sectors) > 1 and 1.0 / len(sectors) < target_share:
            sectors.pop()
        tile.industry_allocation = self.normalize_industry_allocation({
            sector: 1.0
            for sector in sectors
        })
        return True

    def ensure_starting_consumer_goods_industry(self, player):
        industry_tiles = [
            tile
            for tile in player.tiles
            if (getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0) > 0
        ]
        if not industry_tiles:
            return

        total_coverage = sum((getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0) for tile in industry_tiles)
        if total_coverage <= 0:
            return

        def consumer_goods_coverage():
            return sum(
                (getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0)
                * (getattr(tile, "industry_allocation", {}) or {}).get("consumer_goods", 0.0)
                for tile in industry_tiles
            )

        target_coverage = total_coverage * STARTING_CONSUMER_GOODS_INDUSTRY_SHARE
        if consumer_goods_coverage() >= target_coverage:
            return

        ranked_tiles = sorted(
            industry_tiles,
            key=lambda tile: (
                -self.industry_sector_scores(player, tile).get("consumer_goods", 0.0),
                -((getattr(tile, "building_coverage", {}) or {}).get("industry", 0.0)),
                tile.q,
                tile.r,
            ),
        )
        for tile in ranked_tiles:
            if consumer_goods_coverage() >= target_coverage:
                break
            self.add_consumer_goods_share_to_tile(tile, STARTING_CONSUMER_GOODS_TILE_SHARE)

    def assign_starting_industry_allocations(self, player):
        for tile in player.tiles:
            self.assign_industry_allocation(player, tile)
        self.ensure_starting_consumer_goods_industry(player)

    def calculate_tile_production_cache(self, player, tile):
        cache = self.empty_production_cache()
        coverage = getattr(tile, "building_coverage", {}) or {}
        modifiers = player.production_modifiers

        mine_coverage = coverage.get("mine", 0.0)
        if mine_coverage > 0:
            mining_efficiency = modifiers.get("mining_efficiency", 1.0)
            for resource in getattr(tile, "resources", []):
                if len(resource) < 3:
                    continue
                key, _depth, mass = resource
                if key not in RAW_RESOURCE_NAMES:
                    continue
                if key in OIL_GAS_RESOURCE_KEYS:
                    continue
                abundance = min(1.0, math.log10(max(0.0, float(mass)) + 1) / math.log10(1_500_000 + 1))
                weight = STARTING_MINE_RESOURCE_WEIGHTS.get(key, 0.35)
                output = mine_coverage * abundance * (0.55 + weight) * mining_efficiency * 5200
                self.add_production_amount(cache, "raw", "outputs", key, output)

        rig_coverage = coverage.get("oil_gas_rig", 0.0)
        if rig_coverage > 0:
            mining_efficiency = modifiers.get("mining_efficiency", 1.0)
            for resource in getattr(tile, "resources", []):
                if len(resource) < 3:
                    continue
                key, _depth, mass = resource
                if key not in OIL_GAS_RESOURCE_KEYS:
                    continue
                abundance = min(1.0, math.log10(max(0.0, float(mass)) + 1) / math.log10(1_500_000 + 1))
                weight = STARTING_OIL_GAS_RIG_RESOURCE_WEIGHTS.get(key, 0.8)
                output = rig_coverage * abundance * (0.62 + weight) * mining_efficiency * 5600
                self.add_production_amount(cache, "raw", "outputs", key, output)

        farms_coverage = coverage.get("farms", 0.0)
        if farms_coverage > 0:
            agriculture_efficiency = modifiers.get("agriculture_efficiency", 1.0)
            base_output = (
                farms_coverage
                * self.agriculture_score(tile)
                * agriculture_efficiency
                * FARM_FOOD_BASE_RATE
            )
            self.add_production_amount(cache, "raw", "outputs", "food", base_output)
            self.add_production_amount(
                cache,
                "agriculture",
                "inputs",
                "fertilizer",
                farms_coverage * FERTILIZER_CONSUMPTION_PER_FARM_COVERAGE,
            )
            self.add_production_amount(cache, "agriculture", "outputs", "food", base_output * FERTILIZER_FOOD_BONUS)

        allocation = getattr(tile, "industry_allocation", None)
        if allocation is None or (coverage.get("industry", 0.0) > 0 and not allocation):
            allocation = self.assign_industry_allocation(player, tile)
        elif coverage.get("industry", 0.0) > 0:
            allocation = self.normalize_industry_allocation(allocation)
            tile.industry_allocation = allocation
        specialization_efficiency = self.specialization_efficiency(
            allocation,
            modifiers.get("industry_diversification_penalty", 0.9),
            modifiers.get("industry_free_specializations", 1),
        )

        for stage in ["semi_finished", "finished"]:
            for recipe in PRODUCTION_RECIPES[stage].values():
                required_tech = recipe.get("requires_tech")
                if required_tech and required_tech not in getattr(player, "technologies", set()):
                    continue
                building = recipe.get("building", "industry")
                building_coverage = coverage.get(building, 0.0)
                if building_coverage <= 0:
                    continue

                sector = recipe["sector"]
                if building == "industry":
                    sector_share = allocation.get(sector, 0.0)
                    if sector_share <= 0:
                        continue
                    efficiency = modifiers.get("industry_efficiency", 1.0) * specialization_efficiency
                elif building == "refinery":
                    sector_share = 1.0
                    efficiency = modifiers.get("refining_efficiency", 1.0)
                else:
                    sector_share = 1.0
                    efficiency = 1.0

                planned_units = recipe["base_rate"] * building_coverage * sector_share * efficiency
                if planned_units <= 0:
                    continue
                for key, amount in recipe.get("inputs", {}).items():
                    self.add_production_amount(cache, stage, "inputs", key, amount * planned_units)
                for key, amount in recipe.get("outputs", {}).items():
                    self.add_production_amount(cache, stage, "outputs", key, amount * planned_units)

        tile.production_cache = cache
        return cache

    def add_state_life_support_to_production_cache(self, player):
        population_millions = max(0.0, (player.population or 0.0) / 1_000_000)
        for key, amount in LIFE_SUPPORT_CONSUMPTION_PER_MILLION.items():
            self.add_production_amount(
                player.production_cache,
                "upkeep",
                "inputs",
                key,
                amount * population_millions,
            )

        for tile in player.tiles:
            coverage = getattr(tile, "building_coverage", {}) or {}
            for building, upkeep in SETTLEMENT_UPKEEP_PER_COVERAGE.items():
                building_coverage = coverage.get(building, 0.0)
                if building_coverage <= 0:
                    continue
                for key, amount in upkeep.items():
                    self.add_production_amount(
                        player.production_cache,
                        "upkeep",
                        "inputs",
                        key,
                        amount * building_coverage,
                    )

    def recalculate_state_production_cache(self, player):
        player.production_cache = self.empty_production_cache()
        for tile in player.tiles:
            cache = self.calculate_tile_production_cache(player, tile)
            self.merge_production_cache(player.production_cache, cache)
        self.add_state_life_support_to_production_cache(player)
        return player.production_cache

    def recalculate_all_state_production_caches(self):
        for player in self.players:
            self.recalculate_state_production_cache(player)

    def update_tile_production_cache(self, tile):
        player = getattr(tile, "owner", None)
        if not player:
            tile.production_cache = self.empty_production_cache()
            return tile.production_cache
        self.recalculate_state_production_cache(player)
        return getattr(tile, "production_cache", None) or self.empty_production_cache()

    def production_amount_for_key(self, player, key, direction):
        cache = player.production_cache or self.empty_production_cache()
        return sum(
            cache[stage][direction].get(key, 0.0)
            for stage in PRODUCTION_STAGES
        )

    def resource_output_source_tiles(self, player, resource_key):
        if not player:
            return []
        if not player.production_cache:
            self.recalculate_state_production_cache(player)

        source_tiles = []
        for tile in player.tiles:
            cache = getattr(tile, "production_cache", None)
            if not cache:
                cache = self.calculate_tile_production_cache(player, tile)
            output = sum(
                cache[stage]["outputs"].get(resource_key, 0.0)
                for stage in PRODUCTION_STAGES
            )
            if output > 0:
                source_tiles.append((tile, output))
        return source_tiles

    @staticmethod
    def breakdown_with_percent(items):
        total = sum(amount for _label, amount in items)
        if total <= 0:
            return [(label, amount, 0.0) for label, amount in items]
        return [(label, amount, amount / total * 100.0) for label, amount in items]

    def production_breakdown_from_flows(self, flows, resource_key):
        stage_outputs = flows["stage_outputs"]
        items = [
            ("Добыча/фермы", stage_outputs.get("raw", {}).get(resource_key, 0.0)),
            ("Удобрения", stage_outputs.get("agriculture", {}).get(resource_key, 0.0)),
            ("Промышленность", (
                stage_outputs.get("semi_finished", {}).get(resource_key, 0.0)
                + stage_outputs.get("finished", {}).get(resource_key, 0.0)
            )),
            ("Импорт", flows["trade_outputs"].get(resource_key, 0.0)),
        ]
        return self.breakdown_with_percent(items)

    def resource_production_breakdown(self, player, resource_key):
        if not player:
            return []
        return self.production_breakdown_from_flows(self.estimate_monthly_resource_flows(player), resource_key)

    def consumption_breakdown_from_flows(self, flows, resource_key):
        stage_inputs = flows["stage_inputs"]
        construction = flows["construction_inputs"].get(resource_key, 0.0)
        industry = sum(
            stage_inputs.get(stage, {}).get(resource_key, 0.0)
            for stage in ("semi_finished", "agriculture", "finished")
        )
        upkeep = stage_inputs.get("upkeep", {}).get(resource_key, 0.0)
        exports = flows["trade_inputs"].get(resource_key, 0.0)
        items = [
            ("Стройки", construction),
            ("Производство", industry),
            ("Поддержание", upkeep),
            ("Экспорт", exports),
        ]
        return self.breakdown_with_percent(items)

    def resource_consumption_breakdown(self, player, resource_key):
        if not player:
            return []
        return self.consumption_breakdown_from_flows(self.estimate_monthly_resource_flows(player), resource_key)

    def all_resource_keys_for_category(self, player, category_key, flows=None):
        keys = set(self.resource_names_for_category(category_key))
        stockpiles = self.ensure_player_stockpiles(player)
        keys.update(stockpiles.get(category_key, {}).keys())
        if category_key == "raw":
            keys.update((player.resource_totals or {}).get("raw", {}).keys())
        if flows:
            keys.update(
                key
                for key in set(flows["inputs"]) | set(flows["outputs"])
                if self.resource_category_for_key(key) == category_key
            )
        return sorted(keys, key=lambda key: self.resource_display_name(key))

    def recalculate_resource_balance_breakdown(self, player):
        if not player:
            return {}
        if not player.resource_totals:
            self.recalculate_state_resources(player)
        if not player.production_cache:
            self.recalculate_state_production_cache(player)

        stockpiles = self.ensure_player_stockpiles(player)
        flows = self.estimate_monthly_resource_flows(player)
        breakdown = {
            category_key: {}
            for category_key in ["raw", "semi_finished", "finished"]
        }
        for category_key in breakdown:
            ground = (player.resource_totals or {}).get("raw", {}) if category_key == "raw" else {}
            for resource_key in self.all_resource_keys_for_category(player, category_key, flows):
                stock = stockpiles.get(category_key, {}).get(resource_key, 0.0)
                production = flows["outputs"].get(resource_key, 0.0)
                consumption = flows["inputs"].get(resource_key, 0.0)
                breakdown[category_key][resource_key] = {
                    "key": resource_key,
                    "ground": ground.get(resource_key, None) if category_key == "raw" else None,
                    "stock": stock,
                    "production": production,
                    "consumption": consumption,
                    "balance": production - consumption,
                    "months": self.resource_duration_months(stock, production, consumption),
                    "production_breakdown": self.production_breakdown_from_flows(flows, resource_key),
                    "consumption_breakdown": self.consumption_breakdown_from_flows(flows, resource_key),
                }
        player.resource_balance_breakdown = breakdown
        player.resource_balance_dirty = False
        player.resource_balance_last_update = time.time()
        return breakdown

    def estimate_monthly_resource_flows(self, player):
        stockpiles = self.ensure_player_stockpiles(player)
        cache = player.production_cache or self.recalculate_state_production_cache(player)
        simulated_stockpiles = {
            category: dict(resources)
            for category, resources in stockpiles.items()
        }
        simulated_capacity, simulated_used, _overflow = self.ensure_player_storage(player)
        simulated_capacity = dict(simulated_capacity)
        simulated_used = dict(simulated_used)
        flows = {
            "inputs": {},
            "outputs": {},
            "stage_inputs": {stage: {} for stage in PRODUCTION_STAGES},
            "stage_outputs": {stage: {} for stage in PRODUCTION_STAGES},
            "construction_inputs": {},
            "trade_inputs": {},
            "trade_outputs": {},
            "trade_money": 0.0,
            "trade_capacity_used": 0.0,
            "trade_capacity_limit": self.trade_capacity_per_month(player),
        }

        def add_amount(bucket, key, amount):
            if amount <= 0:
                return
            bucket[key] = bucket.get(key, 0.0) + amount

        def stock_amount(key):
            category = self.resource_category_for_key(key)
            return simulated_stockpiles.setdefault(category, {}).get(key, 0.0)

        def add_stock(key, amount):
            if amount <= 0:
                return 0.0
            storage_key = self.storage_bucket_for_resource(key)
            free_capacity = max(
                0.0,
                simulated_capacity.get(storage_key, 0.0) - simulated_used.get(storage_key, 0.0),
            )
            accepted = min(amount, free_capacity)
            if accepted <= 0:
                return 0.0
            category = self.resource_category_for_key(key)
            bucket = simulated_stockpiles.setdefault(category, {})
            bucket[key] = bucket.get(key, 0.0) + accepted
            simulated_used[storage_key] = simulated_used.get(storage_key, 0.0) + accepted
            return accepted

        def consume_stock(key, amount):
            if amount <= 0:
                return 0.0
            category = self.resource_category_for_key(key)
            bucket = simulated_stockpiles.setdefault(category, {})
            available = bucket.get(key, 0.0)
            consumed = min(available, amount)
            bucket[key] = max(0.0, available - consumed)
            storage_key = self.storage_bucket_for_resource(key)
            simulated_used[storage_key] = max(0.0, simulated_used.get(storage_key, 0.0) - consumed)
            return consumed

        def record_input(stage, key, amount):
            add_amount(flows["inputs"], key, amount)
            add_amount(flows["stage_inputs"].setdefault(stage, {}), key, amount)

        def record_output(stage, key, amount):
            add_amount(flows["outputs"], key, amount)
            add_amount(flows["stage_outputs"].setdefault(stage, {}), key, amount)

        trade_flows = self.estimate_monthly_trade_flows(player)
        flows["trade_money"] = trade_flows["money_balance"]
        flows["trade_capacity_used"] = trade_flows["capacity_used"]
        flows["trade_capacity_limit"] = trade_flows["capacity_limit"]
        for key, amount in trade_flows["imports"].items():
            accepted = add_stock(key, amount)
            add_amount(flows["outputs"], key, accepted)
            add_amount(flows["trade_outputs"], key, accepted)
        for key, amount in trade_flows["exports"].items():
            exported = consume_stock(key, amount)
            add_amount(flows["inputs"], key, exported)
            add_amount(flows["trade_inputs"], key, exported)

        for stage in PRODUCTION_STAGES:
            if stage == "agriculture":
                planned_fertilizer = cache["agriculture"]["inputs"].get("fertilizer", 0.0)
                planned_bonus_food = cache["agriculture"]["outputs"].get("food", 0.0)
                if planned_fertilizer > 0 and planned_bonus_food > 0:
                    consumed = consume_stock("fertilizer", planned_fertilizer)
                    fertilizer_ratio = self.clamp01(consumed / planned_fertilizer)
                    bonus_food = planned_bonus_food * fertilizer_ratio
                    record_input(stage, "fertilizer", consumed)
                    if bonus_food > 0:
                        accepted = add_stock("food", bonus_food)
                        record_output(stage, "food", accepted)
                continue

            planned_inputs = {
                key: amount
                for key, amount in cache[stage]["inputs"].items()
                if amount > 0
            }
            planned_outputs = {
                key: amount
                for key, amount in cache[stage]["outputs"].items()
                if amount > 0
            }

            if stage == "upkeep":
                for key, required in planned_inputs.items():
                    consumed = consume_stock(key, required)
                    record_input(stage, key, consumed)
                continue

            actual_ratio = 1.0
            for key, required in planned_inputs.items():
                actual_ratio = min(actual_ratio, stock_amount(key) / required)
            actual_ratio = self.clamp01(actual_ratio)

            for key, required in planned_inputs.items():
                consumed = consume_stock(key, required * actual_ratio)
                record_input(stage, key, consumed)
            for key, output in planned_outputs.items():
                actual_output = output * actual_ratio
                accepted = add_stock(key, actual_output)
                record_output(stage, key, accepted)

        for key, amount in self.estimate_active_construction_consumption(player, stock_amount).items():
            consumed = consume_stock(key, amount)
            add_amount(flows["inputs"], key, consumed)
            add_amount(flows["construction_inputs"], key, consumed)

        return flows

    def estimate_active_construction_consumption(self, player, stock_amount_func):
        if not player.construction_queue:
            return {}
        project = player.construction_queue[0]
        status_info = self.evaluate_construction_project_status(
            player,
            project,
            month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
            stock_amount_func=stock_amount_func,
        )
        if status_info["status"] != "building":
            return {}
        monthly_delta = self.construction_project_progress_delta(player, project, month_fraction=1.0)
        return self.construction_project_resource_needs(project, monthly_delta)

    def stockpile_amount(self, player, key):
        category = self.resource_category_for_key(key)
        return self.ensure_player_stockpiles(player).get(category, {}).get(key, 0.0)

    def add_to_stockpile(self, player, key, amount):
        if amount <= 0:
            return 0.0
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_key = self.storage_bucket_for_resource(key)
        free_capacity = max(0.0, capacity.get(storage_key, 0.0) - used.get(storage_key, 0.0))
        accepted = min(amount, free_capacity)
        if accepted <= 0:
            return 0.0
        category = self.resource_category_for_key(key)
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(category, {})
        bucket[key] = bucket.get(key, 0.0) + accepted
        player.storage_used[storage_key] = player.storage_used.get(storage_key, 0.0) + accepted
        player.storage_overflow[storage_key] = max(
            0.0,
            player.storage_used.get(storage_key, 0.0) - player.storage_capacity.get(storage_key, 0.0),
        )
        self.mark_player_stockpiles_changed(player)
        return accepted

    def consume_from_stockpile(self, player, key, amount):
        if amount <= 0:
            return 0.0
        category = self.resource_category_for_key(key)
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(category, {})
        available = bucket.get(key, 0.0)
        consumed = min(available, amount)
        bucket[key] = max(0.0, available - consumed)
        self.ensure_player_storage(player)
        storage_key = self.storage_bucket_for_resource(key)
        player.storage_used[storage_key] = max(0.0, player.storage_used.get(storage_key, 0.0) - consumed)
        player.storage_overflow[storage_key] = max(
            0.0,
            player.storage_used.get(storage_key, 0.0) - player.storage_capacity.get(storage_key, 0.0),
        )
        if consumed > 0:
            self.mark_player_stockpiles_changed(player)
        return consumed

    def tradeable_resource_keys(self, category_key=None):
        categories = [category_key] if category_key else ["raw", "semi_finished", "finished"]
        keys = []
        for category in categories:
            for resource_key in self.resource_names_for_category(category):
                if resource_key not in keys:
                    keys.append(resource_key)
        return keys

    def normalize_trade_contracts(self, player):
        normalized = []
        seen = {}
        for contract in player.trade_contracts or []:
            resource_key = contract.get("resource")
            mode = contract.get("mode")
            amount = max(0.0, float(contract.get("amount", 0.0)))
            if resource_key not in self.tradeable_resource_keys() or mode not in ("buy", "sell") or amount <= 0:
                continue
            contract_key = (resource_key, mode)
            if contract_key in seen:
                normalized[seen[contract_key]]["amount"] += amount
            else:
                seen[contract_key] = len(normalized)
                normalized.append({"resource": resource_key, "mode": mode, "amount": amount})
        player.trade_contracts = normalized
        return normalized

    def trade_contract_amount(self, player, resource_key, mode):
        for contract in self.normalize_trade_contracts(player):
            if contract["resource"] == resource_key and contract["mode"] == mode:
                return contract["amount"]
        return 0.0

    def adjust_trade_contract(self, player, resource_key, mode, delta):
        if not player or resource_key not in self.tradeable_resource_keys() or mode not in ("buy", "sell"):
            return False
        contracts = self.normalize_trade_contracts(player)
        opposite = "sell" if mode == "buy" else "buy"
        remaining_delta = max(0.0, delta)
        changed = False
        if delta > 0:
            for contract in list(contracts):
                if contract["resource"] == resource_key and contract["mode"] == opposite:
                    removed = min(contract["amount"], remaining_delta)
                    contract["amount"] -= removed
                    remaining_delta -= removed
                    changed = changed or removed > 0
                    if remaining_delta <= 0:
                        break
            if remaining_delta <= 0:
                player.trade_contracts = [contract for contract in contracts if contract["amount"] > 0]
                if changed:
                    self.recalculate_monthly_balance(player)
                    self.mark_player_resource_balance_dirty(player)
                return True

        if delta > 0:
            used_capacity = sum(
                contract["amount"]
                for contract in contracts
                if contract["mode"] == mode
            )
            free_capacity = max(0.0, self.trade_capacity_per_month(player, mode) - used_capacity)
            applied_delta = min(remaining_delta, free_capacity)
            if applied_delta <= 0:
                player.trade_contracts = [contract for contract in contracts if contract["amount"] > 0]
                if changed:
                    self.recalculate_monthly_balance(player)
                    self.mark_player_resource_balance_dirty(player)
                return changed
        else:
            applied_delta = delta

        for contract in contracts:
            if contract["resource"] == resource_key and contract["mode"] == mode:
                old_amount = contract["amount"]
                contract["amount"] = max(0.0, contract["amount"] + applied_delta)
                changed = changed or contract["amount"] != old_amount
                break
        else:
            if applied_delta > 0:
                contracts.append({"resource": resource_key, "mode": mode, "amount": applied_delta})
                changed = True

        player.trade_contracts = [contract for contract in contracts if contract["amount"] > 0]
        if changed:
            self.recalculate_monthly_balance(player)
            self.mark_player_resource_balance_dirty(player)
        return changed

    def market_base_price(self, resource_key):
        market_state = getattr(self.simulation_server, "market_state", None)
        if market_state:
            return market_state.ensure_resource(resource_key)
        if resource_key in TRADE_BASE_PRICES:
            return float(TRADE_BASE_PRICES[resource_key])
        category = self.resource_category_for_key(resource_key)
        if category == "finished":
            return 420.0
        if category == "semi_finished":
            return 160.0
        return 60.0

    def market_current_price(self, resource_key):
        market_state = getattr(self.simulation_server, "market_state", None)
        if not market_state:
            return self.market_base_price(resource_key)
        market_state.ensure_resource(resource_key)
        return max(0.01, market_state.current_prices.get(resource_key, self.market_base_price(resource_key)))

    def market_previous_price(self, resource_key):
        market_state = getattr(self.simulation_server, "market_state", None)
        if not market_state:
            return self.market_base_price(resource_key)
        market_state.ensure_resource(resource_key)
        return max(0.01, market_state.previous_prices.get(resource_key, self.market_base_price(resource_key)))

    def market_price_change_fraction(self, resource_key):
        previous = self.market_previous_price(resource_key)
        current = self.market_current_price(resource_key)
        if previous <= 0:
            return 0.0
        return current / previous - 1.0

    def market_unit_price(self, resource_key, mode):
        price = self.market_current_price(resource_key)
        if mode == "buy":
            return price * TRADE_BUY_PRICE_MARKUP
        return price * TRADE_SELL_PRICE_MARKDOWN

    def trade_unit_price(self, player, resource_key, mode):
        return self.market_unit_price(resource_key, mode)

    @staticmethod
    def trade_mode_capacity_multiplier(mode):
        if mode == "sell":
            return TRADE_SELL_LIMIT_MULTIPLIER
        if mode == "buy":
            return 1.0
        return 1.0 + TRADE_SELL_LIMIT_MULTIPLIER

    def trade_logistics_capacity_per_month(self, player, mode=None):
        coverage_totals = {}
        for tile in player.tiles:
            for key, value in (getattr(tile, "building_coverage", {}) or {}).items():
                coverage_totals[key] = coverage_totals.get(key, 0.0) + max(0.0, value)
        supply = (player.supply_summary or {}).get("average", 1.0)
        logistics = (player.production_modifiers or {}).get("logistics_efficiency", 1.0)
        port_capacity = coverage_totals.get("port", 0.0) * TRADE_PORT_CAPACITY_PER_COVERAGE
        warehouse_capacity = coverage_totals.get("warehouse", 0.0) * TRADE_WAREHOUSE_CAPACITY_PER_COVERAGE
        supply_depot_capacity = coverage_totals.get("supply_depot", 0.0) * TRADE_SUPPLY_DEPOT_CAPACITY_PER_COVERAGE
        settlement_capacity = (
            coverage_totals.get("city", 0.0)
            + coverage_totals.get("village", 0.0) * 0.5
        ) * TRADE_SETTLEMENT_CAPACITY_PER_COVERAGE
        scale = getattr(player, "starting_scale", 1.0)
        base_capacity = TRADE_BASE_CAPACITY * max(0.5, scale)
        supply_factor = 0.35 + self.clamp01(supply) * 0.65
        capacity = max(
            0.0,
            (base_capacity + port_capacity + warehouse_capacity + supply_depot_capacity + settlement_capacity)
            * logistics
            * supply_factor,
        )
        return capacity * self.trade_mode_capacity_multiplier(mode)

    def trade_max_capacity_per_month(self, player, mode=None):
        scale = getattr(player, "starting_scale", 1.0)
        modifiers = player.trade_modifiers or {}
        external_limit = modifiers.get("external_market_limit", 1.0)
        diplomacy_bonus = modifiers.get("diplomacy_trade_bonus", 0.0)
        capacity = max(0.0, TRADE_BASE_MAX_CAPACITY * max(0.5, scale) * external_limit + diplomacy_bonus)
        return capacity * self.trade_mode_capacity_multiplier(mode)

    def trade_capacity_per_month(self, player, mode=None):
        return min(
            self.trade_logistics_capacity_per_month(player, mode),
            self.trade_max_capacity_per_month(player, mode),
        )

    def estimate_monthly_trade_flows(self, player):
        contracts = self.normalize_trade_contracts(player)
        capacity_limits = {
            "buy": self.trade_capacity_per_month(player, "buy"),
            "sell": self.trade_capacity_per_month(player, "sell"),
        }
        remaining_capacity = dict(capacity_limits)
        imports = {}
        exports = {}
        buy_cost = 0.0
        sell_income = 0.0
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_free = {
            category_key: max(0.0, capacity.get(category_key, 0.0) - used.get(category_key, 0.0))
            for category_key in STORAGE_CATEGORIES
        }

        for contract in contracts:
            resource_key = contract["resource"]
            mode = contract["mode"]
            if remaining_capacity.get(mode, 0.0) <= 0:
                continue
            amount = min(contract["amount"], remaining_capacity.get(mode, 0.0))
            if mode == "sell":
                amount = min(amount, self.stockpile_amount(player, resource_key))
                storage_key = self.storage_bucket_for_resource(resource_key)
                storage_free[storage_key] = storage_free.get(storage_key, 0.0) + amount
            else:
                storage_key = self.storage_bucket_for_resource(resource_key)
                amount = min(amount, storage_free.get(storage_key, 0.0))
            if amount <= 0:
                continue
            price = self.trade_unit_price(player, resource_key, mode)
            if mode == "buy":
                imports[resource_key] = imports.get(resource_key, 0.0) + amount
                buy_cost += amount * price
                storage_free[storage_key] = max(0.0, storage_free.get(storage_key, 0.0) - amount)
            else:
                exports[resource_key] = exports.get(resource_key, 0.0) + amount
                sell_income += amount * price
            remaining_capacity[mode] = max(0.0, remaining_capacity.get(mode, 0.0) - amount)

        capacity_used = {
            mode: max(0.0, capacity_limits[mode] - remaining_capacity.get(mode, 0.0))
            for mode in ("buy", "sell")
        }

        return {
            "imports": imports,
            "exports": exports,
            "buy_cost": buy_cost,
            "sell_income": sell_income,
            "money_balance": sell_income - buy_cost,
            "capacity_used": capacity_used["buy"] + capacity_used["sell"],
            "capacity_limit": capacity_limits["buy"] + capacity_limits["sell"],
            "buy_capacity_used": capacity_used["buy"],
            "sell_capacity_used": capacity_used["sell"],
            "buy_capacity_limit": capacity_limits["buy"],
            "sell_capacity_limit": capacity_limits["sell"],
            "logistics_capacity_limit": self.trade_logistics_capacity_per_month(player),
            "max_capacity_limit": self.trade_max_capacity_per_month(player),
            "buy_logistics_capacity_limit": self.trade_logistics_capacity_per_month(player, "buy"),
            "sell_logistics_capacity_limit": self.trade_logistics_capacity_per_month(player, "sell"),
            "buy_max_capacity_limit": self.trade_max_capacity_per_month(player, "buy"),
            "sell_max_capacity_limit": self.trade_max_capacity_per_month(player, "sell"),
        }

    def trade_weekly_capacity_limits(self, player):
        return {
            "buy": self.trade_capacity_per_month(player, "buy") * TRADE_WEEKLY_FRACTION,
            "sell": self.trade_capacity_per_month(player, "sell") * TRADE_WEEKLY_FRACTION,
        }

    def collect_player_market_orders(self, player, weekly_fraction=TRADE_WEEKLY_FRACTION, enforce_budget=True):
        contracts = self.normalize_trade_contracts(player)
        remaining_capacity = self.trade_weekly_capacity_limits(player)
        capacity, used, _overflow = self.ensure_player_storage(player)
        storage_free = {
            category_key: max(0.0, capacity.get(category_key, 0.0) - used.get(category_key, 0.0))
            for category_key in STORAGE_CATEGORIES
        }
        available_budget = max(0.0, player.budget)
        orders = []

        for contract in contracts:
            resource_key = contract["resource"]
            mode = contract["mode"]
            if remaining_capacity.get(mode, 0.0) <= 0:
                continue
            amount = min(contract["amount"] * weekly_fraction, remaining_capacity.get(mode, 0.0))
            if mode == "buy":
                storage_key = self.storage_bucket_for_resource(resource_key)
                amount = min(amount, storage_free.get(storage_key, 0.0))
                if enforce_budget:
                    unit_price = self.trade_unit_price(player, resource_key, "buy")
                    cost = amount * unit_price
                    if cost > available_budget and cost > 0:
                        amount *= max(0.0, available_budget / cost)
            else:
                amount = min(amount, self.stockpile_amount(player, resource_key))
            if amount <= 0:
                continue
            orders.append({
                "player": player,
                "resource": resource_key,
                "mode": mode,
                "amount": amount,
            })
            remaining_capacity[mode] = max(0.0, remaining_capacity.get(mode, 0.0) - amount)
            if mode == "buy":
                storage_key = self.storage_bucket_for_resource(resource_key)
                storage_free[storage_key] = max(0.0, storage_free.get(storage_key, 0.0) - amount)
                if enforce_budget:
                    available_budget = max(0.0, available_budget - amount * self.trade_unit_price(player, resource_key, "buy"))
            else:
                storage_key = self.storage_bucket_for_resource(resource_key)
                storage_free[storage_key] = storage_free.get(storage_key, 0.0) + amount
        return orders

    def external_market_volume_for_resource(self, resource_key, weekly_total_trade_capacity):
        rarity = MARKET_RESOURCE_RARITY.get(resource_key, 0.45)
        return max(750.0, weekly_total_trade_capacity * max(0.05, rarity) * 0.55)

    def update_market_prices_from_orders(self, orders):
        market_state = self.simulation_server.market_state
        keys = self.tradeable_resource_keys()
        weekly_total_trade_capacity = sum(
            self.trade_capacity_per_month(player) * TRADE_WEEKLY_FRACTION
            for player in self.players
        )
        demand = {key: 0.0 for key in keys}
        supply = {key: 0.0 for key in keys}
        for order in orders:
            bucket = demand if order["mode"] == "buy" else supply
            bucket[order["resource"]] = bucket.get(order["resource"], 0.0) + order["amount"]

        market_state.previous_prices = dict(market_state.current_prices or {})
        external_demand = {}
        external_supply = {}
        total_market_demand = {}
        total_market_supply = {}
        new_prices = {}
        for resource_key in keys:
            base_price = market_state.ensure_resource(resource_key)
            external_volume = self.external_market_volume_for_resource(resource_key, weekly_total_trade_capacity)
            external_demand[resource_key] = external_volume
            external_supply[resource_key] = external_volume
            total_demand = demand.get(resource_key, 0.0) + external_volume
            total_supply = supply.get(resource_key, 0.0) + external_volume
            total_market_demand[resource_key] = total_demand
            total_market_supply[resource_key] = total_supply
            denominator = max(1.0, min(total_demand, total_supply))
            imbalance = (total_demand - total_supply) / denominator
            volatility = MARKET_RESOURCE_VOLATILITY.get(resource_key, 1.0)
            base_change = max(
                -MARKET_MAX_WEEKLY_PRICE_MOVE,
                min(MARKET_MAX_WEEKLY_PRICE_MOVE, imbalance * 0.10 * volatility),
            )
            old_shock = market_state.price_shocks.get(resource_key, 0.0)
            shock = old_shock * MARKET_SHOCK_DECAY + base_change * max(0.0, MARKET_SHOCK_FACTOR - 1.0)
            shock = max(-MARKET_MAX_WEEKLY_PRICE_MOVE, min(MARKET_MAX_WEEKLY_PRICE_MOVE, shock))
            old_price = market_state.current_prices.get(resource_key, base_price)
            target_price = base_price * max(0.25, 1.0 + base_change + shock)
            new_price = old_price + (target_price - old_price) * MARKET_PRICE_SMOOTHING
            new_prices[resource_key] = max(base_price * 0.25, min(base_price * 4.0, new_price))
            market_state.price_shocks[resource_key] = shock

        linked_prices = dict(new_prices)
        for target_key, sources in MARKET_LINKED_PRICE_EFFECTS.items():
            if target_key not in linked_prices:
                continue
            source_pressure = 0.0
            weight_total = 0.0
            for source_key, weight in sources.items():
                base = market_state.base_prices.get(source_key, TRADE_BASE_PRICES.get(source_key, 60.0))
                source_price = new_prices.get(source_key, market_state.current_prices.get(source_key, base))
                if base <= 0:
                    continue
                source_pressure += (source_price / base - 1.0) * weight
                weight_total += weight
            if weight_total <= 0:
                continue
            base = market_state.base_prices.get(target_key, TRADE_BASE_PRICES.get(target_key, 60.0))
            linked_target = base * max(0.25, 1.0 + source_pressure)
            linked_prices[target_key] = linked_prices[target_key] + (linked_target - linked_prices[target_key]) * MARKET_LINKED_PRICE_SMOOTHING

        market_state.current_prices = {
            key: max(market_state.base_prices.get(key, 60.0) * 0.25, min(market_state.base_prices.get(key, 60.0) * 4.0, value))
            for key, value in linked_prices.items()
        }
        market_state.demand = total_market_demand
        market_state.supply = total_market_supply
        market_state.external_demand = external_demand
        market_state.external_supply = external_supply
        for key, price in market_state.current_prices.items():
            history = market_state.history.setdefault(key, [])
            history.append(price)
            if len(history) > MARKET_HISTORY_LIMIT:
                del history[:-MARKET_HISTORY_LIMIT]
        market_state.revision += 1

    def execute_market_orders(self, orders):
        money_by_player = {}
        for order in orders:
            player = order["player"]
            resource_key = order["resource"]
            mode = order["mode"]
            amount = order["amount"]
            price = self.trade_unit_price(player, resource_key, mode)
            if mode == "buy":
                amount = min(amount, self.storage_free_capacity_for_resource(player, resource_key))
                cost = amount * price
                if cost > player.budget and cost > 0:
                    amount *= max(0.0, player.budget / cost)
                    cost = amount * price
                accepted = self.add_to_stockpile(player, resource_key, amount)
                cost = accepted * price
                player.budget -= cost
                money_by_player[player.id] = money_by_player.get(player.id, 0.0) - cost
            else:
                amount = min(amount, self.stockpile_amount(player, resource_key))
                sold = self.consume_from_stockpile(player, resource_key, amount)
                income = sold * price
                player.budget += income
                money_by_player[player.id] = money_by_player.get(player.id, 0.0) + income
        for player in self.players:
            if money_by_player.get(player.id, 0.0) != 0.0:
                self.mark_player_resource_balance_dirty(player)
        return money_by_player

    def run_weekly_market_tick(self):
        orders = []
        for player in self.players:
            orders.extend(self.collect_player_market_orders(player, TRADE_WEEKLY_FRACTION, enforce_budget=True))
        self.update_market_prices_from_orders(orders)
        money_by_player = self.execute_market_orders(orders)
        for player in self.players:
            self.recalculate_monthly_balance(player)
            self.mark_player_resource_balance_dirty(player)
        self.trade_panel_cache = None
        return money_by_player

    @staticmethod
    def construction_level_for_coverage(coverage):
        return max(1, math.floor(max(0.0, coverage) / CONSTRUCTION_STEP) + 1)

    @staticmethod
    def next_construction_coverage(coverage):
        coverage = max(0.0, min(1.0, coverage))
        if coverage >= 1.0:
            return None
        next_step = math.floor(coverage / CONSTRUCTION_STEP + 1e-9) + 1
        return min(1.0, next_step * CONSTRUCTION_STEP)

    def build_power(self, player):
        coverage_totals = {}
        for tile in player.tiles:
            for key, value in (getattr(tile, "building_coverage", {}) or {}).items():
                coverage_totals[key] = coverage_totals.get(key, 0.0) + max(0.0, value)

        modifiers = player.construction_modifiers or {}
        industry_efficiency = (player.production_modifiers or {}).get("industry_efficiency", 1.0)
        city_multiplier = modifiers.get("city_build_multiplier", 1.0)
        tech_bonus = modifiers.get("tech_bonus", 0.0)
        industry_power = coverage_totals.get("industry", 0.0) * industry_efficiency
        settlement_power = (
            coverage_totals.get("city", 0.0)
            + coverage_totals.get("village", 0.0) * 0.5
        ) * city_multiplier
        return max(0.0, (industry_power + settlement_power) * BASE_BUILD_POWER_PER_MONTH + tech_bonus)

    def construction_cost(self, player, tile, building_key, current_coverage=None):
        base = BUILDING_CONSTRUCTION_BASE.get(building_key)
        if not base:
            return None

        if current_coverage is None:
            current_coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        current_coverage = max(0.0, min(1.0, current_coverage))
        target_coverage = self.next_construction_coverage(current_coverage)
        if target_coverage is None:
            return None

        step_size = target_coverage - current_coverage
        level = self.construction_level_for_coverage(current_coverage)
        level_multiplier = CONSTRUCTION_LEVEL_MULTIPLIER ** (level - 1)
        modifiers = player.construction_modifiers or {}
        build_efficiency = modifiers.get("build_efficiency", 1.0)
        cost_multiplier = level_multiplier * max(0.05, build_efficiency)
        resource_costs = {
            key: amount * step_size * cost_multiplier
            for key, amount in base.get("resources", {}).items()
        }
        work_required = base.get("work", 0.0) * step_size * level_multiplier
        return {
            "building": building_key,
            "from_coverage": current_coverage,
            "target_coverage": target_coverage,
            "level": level,
            "money_cost": base.get("money", 0.0) * step_size * cost_multiplier,
            "resource_costs": resource_costs,
            "work_required": work_required,
        }

    def queued_target_coverage(self, player, tile, building_key):
        coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        for project in player.construction_queue:
            cost = project.get("cost", {})
            if project.get("tile") == tile and cost.get("building") == building_key:
                coverage = max(coverage, cost.get("target_coverage", coverage))
        return min(1.0, coverage)

    def construction_queue_target_lookup(self, player, building_key):
        targets = {}
        if not player or not building_key:
            return targets
        for project in player.construction_queue:
            cost = project.get("cost", {})
            if cost.get("building") != building_key:
                continue
            tile = project.get("tile")
            if not tile:
                continue
            tile_key = (tile.q, tile.r)
            targets[tile_key] = max(targets.get(tile_key, 0.0), cost.get("target_coverage", 0.0))
        return targets

    def best_building_for_tile(self, player, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        upgradeable = [
            (key, value)
            for key, value in coverage.items()
            if key in BUILDING_CONSTRUCTION_BASE and value < 1.0
        ]
        if upgradeable:
            return max(upgradeable, key=lambda item: item[1])[0]

        if self.is_coastal_land_tile(tile):
            return "port"
        if self.oil_gas_rig_score(player, tile) > 0.12:
            return "oil_gas_rig"
        if self.mine_score(player, tile) > 0.12:
            return "mine"
        agriculture = self.agriculture_score(tile)
        if agriculture > 0.48:
            return "farms"
        if self.industry_score(player, tile) > 0.32:
            return "industry"
        if self.is_water_tile(tile):
            return None
        return "village"

    def selected_construction_building_key(self):
        if not BUILDING_TYPES:
            return None
        self.selected_construction_index = max(0, min(len(BUILDING_TYPES) - 1, self.selected_construction_index))
        return BUILDING_TYPES[self.selected_construction_index][0]

    def construction_queue_signature(self, player):
        if not player:
            return ()
        signature = []
        for project in player.construction_queue:
            cost = project.get("cost", {})
            tile = project.get("tile")
            signature.append((
                id(tile),
                cost.get("building") or project.get("building"),
                round(cost.get("target_coverage", 0.0), 4),
            ))
        return tuple(signature)

    def construction_placement_current_cache_key(self, building_key=None, player=None):
        return (
            tuple((tile.q, tile.r) for tile in self.visible_tiles),
            building_key or self.selected_construction_building_key(),
            self.construction_queue_signature(player or self.human_player),
            self.tile_visual_revision,
        )

    @staticmethod
    def construction_label_rect(tile, label):
        label_width = 104
        label_height = 22
        return (
            tile.center_x - label_width / 2,
            tile.center_y - label_height / 2 - 2,
            label_width,
            label_height,
        )

    def create_construction_label_text(self, tile, label):
        return arcade.Text(
            label,
            tile.center_x,
            tile.center_y - 1,
            (232, 252, 144),
            15,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )

    def get_construction_label_text(self, tile, label):
        tile_key = (tile.q, tile.r)
        text = self.construction_placement_text_cache.get(tile_key)
        if text is None:
            text = self.create_construction_label_text(tile, label)
            self.construction_placement_text_cache[tile_key] = text
        else:
            if text.text != label:
                text.text = label
            text.x = tile.center_x
            text.y = tile.center_y - 1
        return text

    @staticmethod
    def append_construction_label_shapes(shapes, rect):
        x, y, width, height = rect
        center_x = x + width / 2
        center_y = y + height / 2
        shapes.append(
            arcade.shape_list.create_rectangle_filled(
                center_x,
                center_y,
                width,
                height,
                (18, 27, 22, 210),
            )
        )
        shapes.append(
            arcade.shape_list.create_rectangle_outline(
                center_x,
                center_y,
                width,
                height,
                (206, 238, 140, 190),
                1,
            )
        )

    def create_construction_label_shapes(self, rects):
        shapes = arcade.shape_list.ShapeElementList()
        for rect in rects:
            self.append_construction_label_shapes(shapes, rect)
        return shapes

    def rebuild_construction_placement_cache(self):
        if not self.construction_placement_mode or self.active_top_panel_key != "construction":
            self.invalidate_construction_placement_cache()
            return

        building_key = self.selected_construction_building_key()
        player = self.human_player
        cache_key = self.construction_placement_current_cache_key(building_key, player)
        if cache_key == self.construction_placement_cache_key:
            return

        tile_cache = {}
        label_items = []
        label_texts = []
        label_rects = []
        if building_key and player:
            queued_targets = self.construction_queue_target_lookup(player, building_key)
            for tile in self.visible_tiles:
                if tile.owner != player:
                    continue
                coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
                queued_target = max(coverage, queued_targets.get((tile.q, tile.r), coverage))
                queued_delta = max(0.0, queued_target - coverage)
                reason = self.construction_tile_block_reason(
                    player,
                    tile,
                    building_key,
                    queued_coverage=queued_target,
                )
                can_place = reason is None
                label = f"{coverage:.0%}"
                if queued_delta > 0:
                    label += f"+{queued_delta:.0%}"
                tile_cache[(tile.q, tile.r)] = {
                    "can_place": can_place,
                    "coverage": coverage,
                    "queued_delta": queued_delta,
                    "label": label,
                }
                if can_place:
                    label_items.append((tile, label))
                    label_rects.append(self.construction_label_rect(tile, label))
                    label_texts.append(self.get_construction_label_text(tile, label))

        self.construction_placement_cache_key = cache_key
        self.construction_placement_tile_cache = tile_cache
        self.construction_placement_label_items = label_items
        self.construction_placement_label_texts = label_texts
        self.construction_placement_label_rects = label_rects
        self.construction_placement_label_shapes = self.create_construction_label_shapes(label_rects)

    def construction_label_index_for_tile(self, tile):
        tile_key = (tile.q, tile.r)
        for index, (label_tile, _label) in enumerate(self.construction_placement_label_items):
            if (label_tile.q, label_tile.r) == tile_key:
                return index
        return None

    def set_construction_label_for_tile(self, tile, label, visible):
        index = self.construction_label_index_for_tile(tile)
        if not visible:
            if index is not None:
                self.construction_placement_label_items.pop(index)
                self.construction_placement_label_rects.pop(index)
                self.construction_placement_label_texts.pop(index)
                self.construction_placement_label_shapes = self.create_construction_label_shapes(
                    self.construction_placement_label_rects
                )
            return

        rect = self.construction_label_rect(tile, label)
        if index is None:
            self.construction_placement_label_items.append((tile, label))
            self.construction_placement_label_rects.append(rect)
            self.construction_placement_label_texts.append(self.get_construction_label_text(tile, label))
            self.append_construction_label_shapes(self.construction_placement_label_shapes, rect)
        else:
            self.construction_placement_label_items[index] = (tile, label)
            old_rect = self.construction_placement_label_rects[index]
            self.construction_placement_label_rects[index] = rect
            text = self.construction_placement_label_texts[index]
            if text.text != label:
                text.text = label
            text.x = tile.center_x
            text.y = tile.center_y - 1
            if rect != old_rect:
                self.construction_placement_label_shapes = self.create_construction_label_shapes(
                    self.construction_placement_label_rects
                )

    def refresh_construction_placement_tile(self, tile, building_key=None):
        if not tile or not self.construction_placement_mode or self.active_top_panel_key != "construction":
            return
        building_key = building_key or self.selected_construction_building_key()
        player = self.human_player
        if not building_key or not player:
            return
        if self.construction_placement_cache_key is None:
            self.rebuild_construction_placement_cache()
            return
        if not any(visible_tile is tile for visible_tile in self.visible_tiles):
            self.construction_placement_cache_key = self.construction_placement_current_cache_key(building_key, player)
            return

        reason = self.construction_tile_block_reason(player, tile, building_key)
        can_place = reason is None
        coverage = (getattr(tile, "building_coverage", {}) or {}).get(building_key, 0.0)
        queued_target = self.queued_target_coverage(player, tile, building_key)
        queued_delta = max(0.0, queued_target - coverage)
        label = f"{coverage:.0%}"
        if queued_delta > 0:
            label += f"+{queued_delta:.0%}"

        self.construction_placement_tile_cache[(tile.q, tile.r)] = {
            "can_place": can_place,
            "coverage": coverage,
            "queued_delta": queued_delta,
            "label": label,
        }
        self.set_construction_label_for_tile(tile, label, can_place)
        self.construction_placement_cache_key = self.construction_placement_current_cache_key(building_key, player)
        self.apply_tile_draw_color(tile)

    def construction_tile_block_reason(self, player, tile, building_key, queued_coverage=None):
        if not player:
            return "Нет страны"
        if not tile or tile.owner != player:
            return "Чужая клетка"
        if building_key not in BUILDING_CONSTRUCTION_BASE:
            return "Неизвестное строение"
        coverage = (
            queued_coverage
            if queued_coverage is not None
            else self.queued_target_coverage(player, tile, building_key)
        )
        if coverage >= 1.0:
            return "Уже максимум"
        if building_key == "port":
            if not self.is_coastal_land_tile(tile):
                return "Порт только рядом с водой"
        elif self.is_water_tile(tile):
            return "Нужна суша"
        if building_key == "mine" and self.weighted_resource_score(tile, STARTING_SOLID_MINE_RESOURCE_WEIGHTS) <= 0:
            return "Нужны твердые залежи"
        if building_key == "oil_gas_rig" and self.weighted_resource_score(tile, STARTING_OIL_GAS_RIG_RESOURCE_WEIGHTS) <= 0:
            return "Нужна нефть или газ"
        if not self.construction_cost(player, tile, building_key, coverage):
            return "Нельзя улучшить"
        return None

    def can_place_construction(self, player, tile, building_key):
        return self.construction_tile_block_reason(player, tile, building_key) is None

    def set_construction_placement_mode(self, enabled):
        enabled = bool(enabled and self.active_top_panel_key == "construction" and self.human_player)
        if self.construction_placement_mode == enabled:
            return
        self.construction_placement_mode = enabled
        self.invalidate_construction_placement_cache()
        self.create_map_overview()
        self.refresh_visible_tiles()

    def enqueue_construction(self, player, tile, building_key=None, refresh=True):
        if not player or tile.owner != player:
            self.hex_panel_message = "Клетка не принадлежит стране"
            self.hex_panel_message_timer = 2.0
            return False

        building_key = building_key or self.best_building_for_tile(player, tile)
        if not building_key:
            self.hex_panel_message = "Здесь нельзя строить"
            self.hex_panel_message_timer = 2.0
            return False
        if building_key == "port" and not self.is_coastal_land_tile(tile):
            self.hex_panel_message = "Порт только у воды"
            self.hex_panel_message_timer = 2.0
            return False

        current_coverage = self.queued_target_coverage(player, tile, building_key)
        cost = self.construction_cost(player, tile, building_key, current_coverage)
        if not cost:
            self.hex_panel_message = "Уже максимум"
            self.hex_panel_message_timer = 2.0
            return False

        speed = self.build_power(player)
        cost = dict(cost)
        resources_spent = {}
        resource_costs = cost.get("resource_costs", {})
        cost["resources_spent"] = resources_spent
        player.construction_queue.append({
            "tile": tile,
            "building": building_key,
            "from_coverage": cost.get("from_coverage", current_coverage),
            "target_coverage": cost.get("target_coverage", current_coverage),
            "money_cost": cost.get("money_cost", 0.0),
            "resource_costs": resource_costs,
            "resources_spent": resources_spent,
            "cost": cost,
            "speed": speed,
            "progress": 0.0,
            "money_paid": False,
            "status": "queued",
            "status_reason": "Ждет очереди",
            "stall_reasons": [],
            "missing_money": 0.0,
            "missing_resources": {},
        })
        if refresh:
            self.refresh_construction_placement_tile(tile, building_key)
        return True

    def enqueue_construction_steps(self, player, tile, building_key=None, steps=1):
        added = 0
        for _index in range(max(1, steps)):
            if not self.enqueue_construction(player, tile, building_key, refresh=False):
                break
            added += 1

        if added:
            self.refresh_construction_placement_tile(tile, building_key)
        return added

    def cancel_queued_construction(self, player, tile, building_key=None):
        if not player or not tile:
            return False
        building_key = building_key or self.selected_construction_building_key()
        if not building_key:
            return False

        for index in range(len(player.construction_queue) - 1, -1, -1):
            project = player.construction_queue[index]
            cost = project.get("cost", {})
            if project.get("tile") != tile or cost.get("building") != building_key:
                continue
            if project.get("money_paid", False) or project.get("progress", 0.0) > 0:
                return False

            player.construction_queue.pop(index)
            self.refresh_construction_placement_tile(tile, building_key)
            return True

        return False

    def has_cancelable_construction(self, player, tile, building_key=None):
        if not player or not tile:
            return False
        building_key = building_key or self.selected_construction_building_key()
        if not building_key:
            return False
        return any(
            project.get("tile") == tile
            and (project.get("cost", {}) or {}).get("building") == building_key
            and not project.get("money_paid", False)
            and project.get("progress", 0.0) <= 0
            for project in player.construction_queue
        )

    @staticmethod
    def construction_project_is_locked(project):
        return project.get("money_paid", False) or project.get("progress", 0.0) > 0

    def can_move_construction_project(self, player, index, direction):
        if not player:
            return False
        queue = player.construction_queue
        target_index = index + direction
        if index < 0 or index >= len(queue) or target_index < 0 or target_index >= len(queue):
            return False
        return (
            not self.construction_project_is_locked(queue[index])
            and not self.construction_project_is_locked(queue[target_index])
        )

    def move_construction_project(self, player, index, direction):
        if not self.can_move_construction_project(player, index, direction):
            return False
        queue = player.construction_queue
        target_index = index + direction
        queue[index], queue[target_index] = queue[target_index], queue[index]
        self.invalidate_construction_placement_cache()
        self.recalculate_monthly_balance(player)
        return True

    def can_move_construction_group(self, player, group, direction):
        if not player or not group:
            return False
        queue = player.construction_queue
        groups = self.construction_queue_groups(queue)
        group_index = next(
            (
                index
                for index, candidate in enumerate(groups)
                if candidate["start_index"] == group["start_index"]
                and candidate["end_index"] == group["end_index"]
            ),
            None,
        )
        target_group_index = group_index + direction if group_index is not None else None
        if group_index is None or target_group_index < 0 or target_group_index >= len(groups):
            return False
        target_group = groups[target_group_index]
        return (
            not any(self.construction_project_is_locked(project) for project in group["projects"])
            and not any(self.construction_project_is_locked(project) for project in target_group["projects"])
        )

    def move_construction_group(self, player, group, direction):
        if not self.can_move_construction_group(player, group, direction):
            return False
        queue = player.construction_queue
        groups = self.construction_queue_groups(queue)
        group_index = next(
            (
                index
                for index, candidate in enumerate(groups)
                if candidate["start_index"] == group["start_index"]
                and candidate["end_index"] == group["end_index"]
            ),
            None,
        )
        target_group_index = group_index + direction
        current_group = groups[group_index]
        target_group = groups[target_group_index]
        current_projects = current_group["projects"]
        target_projects = target_group["projects"]
        if direction < 0:
            replacement = current_projects + target_projects
            start = target_group["start_index"]
            end = current_group["end_index"] + 1
        else:
            replacement = target_projects + current_projects
            start = current_group["start_index"]
            end = target_group["end_index"] + 1
        queue[start:end] = replacement
        self.invalidate_construction_placement_cache()
        self.recalculate_monthly_balance(player)
        return True

    def sync_construction_project_fields(self, project):
        cost = project.setdefault("cost", {})
        building_key = project.get("building") or cost.get("building")
        if building_key:
            project["building"] = building_key
            cost["building"] = building_key

        for key in ("from_coverage", "target_coverage", "money_cost", "work_required", "level"):
            if key not in project and key in cost:
                project[key] = cost[key]
            elif key in project:
                cost[key] = project[key]

        resource_costs = project.get("resource_costs")
        if resource_costs is None:
            resource_costs = cost.get("resource_costs", {})
        project["resource_costs"] = resource_costs
        cost["resource_costs"] = resource_costs

        resources_spent = project.get("resources_spent")
        if resources_spent is None:
            resources_spent = cost.get("resources_spent", {})
        project["resources_spent"] = resources_spent
        cost["resources_spent"] = resources_spent

        project.setdefault("status", "queued")
        project.setdefault("status_reason", "Ждет очереди")
        project.setdefault("stall_reasons", [])
        project.setdefault("missing_money", 0.0)
        project.setdefault("missing_resources", {})
        project.setdefault("progress", 0.0)
        project.setdefault("money_paid", False)
        project.setdefault("paused", False)
        return cost

    @staticmethod
    def construction_project_status_label(status):
        labels = {
            "queued": "Ждет очереди",
            "building": "Строится",
            "waiting_money": "Ждет деньги",
            "waiting_resources": "Ждет ресурсы",
            "waiting_power": "Нет строймощности",
            "paused": "Пауза",
            "complete": "Готово",
        }
        return labels.get(status, "Ждет")

    def set_construction_project_status(
        self,
        project,
        status,
        reasons=None,
        missing_money=0.0,
        missing_resources=None,
    ):
        reasons = reasons or []
        missing_resources = missing_resources or {}
        project["status"] = status
        project["stall_reasons"] = reasons
        project["status_reason"] = "; ".join(reasons) if reasons else self.construction_project_status_label(status)
        project["missing_money"] = max(0.0, missing_money)
        project["missing_resources"] = dict(missing_resources)

    def construction_project_progress_delta(self, player, project, month_fraction=1.0):
        cost = self.sync_construction_project_fields(project)
        speed = self.build_power(player)
        project["speed"] = speed
        if speed <= 0:
            return 0.0
        work_required = max(1.0, cost.get("work_required", project.get("work_required", 1.0)))
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        return min(1.0 - progress, speed * max(0.0, month_fraction) / work_required)

    def construction_project_resource_needs(self, project, progress_delta):
        self.sync_construction_project_fields(project)
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        target_progress = min(1.0, progress + max(0.0, progress_delta))
        resources_spent = project.get("resources_spent", {})
        needs = {}
        for key, total_amount in (project.get("resource_costs", {}) or {}).items():
            if total_amount <= 0:
                continue
            target_spent = total_amount * target_progress
            amount_needed = max(0.0, target_spent - resources_spent.get(key, 0.0))
            if amount_needed > 0:
                needs[key] = amount_needed
        return needs

    def construction_project_remaining_months(self, player, project):
        cost = self.sync_construction_project_fields(project)
        speed = self.build_power(player)
        if speed <= 0:
            return None
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        work_required = max(0.0, cost.get("work_required", project.get("work_required", 0.0)))
        return work_required * max(0.0, 1.0 - progress) / speed

    def evaluate_construction_project_status(
        self,
        player,
        project,
        month_fraction=1.0,
        stock_amount_func=None,
        update=True,
    ):
        cost = self.sync_construction_project_fields(project)
        stock_amount_func = stock_amount_func or (lambda key: self.stockpile_amount(player, key))
        speed = self.build_power(player) if player else 0.0
        project["speed"] = speed
        progress = max(0.0, min(1.0, project.get("progress", 0.0)))
        money_cost = max(0.0, cost.get("money_cost", project.get("money_cost", 0.0)))

        info = {
            "status": "queued",
            "reasons": [],
            "missing_money": 0.0,
            "missing_resources": {},
            "resource_needs": {},
            "progress_delta": 0.0,
            "remaining_months": self.construction_project_remaining_months(player, project),
        }

        if progress >= 0.999:
            info["status"] = "complete"
            if update:
                self.set_construction_project_status(project, "complete")
            return info

        if project.get("paused", False):
            info["status"] = "paused"
            info["reasons"] = ["остановлено игроком"]
            if update:
                self.set_construction_project_status(project, "paused", info["reasons"])
            return info

        if not project.get("money_paid", False) and player and player.budget < money_cost:
            missing_money = money_cost - player.budget
            info.update({
                "status": "waiting_money",
                "missing_money": missing_money,
                "reasons": [f"не хватает денег {self.format_money(missing_money)}"],
            })
            if update:
                self.set_construction_project_status(
                    project,
                    "waiting_money",
                    info["reasons"],
                    missing_money=missing_money,
                )
            return info

        if speed <= 0:
            info.update({
                "status": "waiting_power",
                "reasons": ["нет строительной мощности"],
            })
            if update:
                self.set_construction_project_status(project, "waiting_power", info["reasons"])
            return info

        progress_delta = self.construction_project_progress_delta(player, project, month_fraction)
        info["progress_delta"] = progress_delta
        if progress_delta <= 0:
            info["status"] = "complete"
            if update:
                self.set_construction_project_status(project, "complete")
            return info

        resource_needs = self.construction_project_resource_needs(project, progress_delta)
        missing_resources = {}
        for key, amount_needed in resource_needs.items():
            available = stock_amount_func(key)
            if available + 0.001 < amount_needed:
                missing_resources[key] = amount_needed - available

        info["resource_needs"] = resource_needs
        if missing_resources:
            reasons = [
                f"нет {self.resource_display_name(key)} {self.format_resource_amount(amount)}"
                for key, amount in sorted(missing_resources.items(), key=lambda item: item[1], reverse=True)
            ]
            info.update({
                "status": "waiting_resources",
                "missing_resources": missing_resources,
                "reasons": reasons,
            })
            if update:
                self.set_construction_project_status(
                    project,
                    "waiting_resources",
                    reasons,
                    missing_resources=missing_resources,
                )
            return info

        info["status"] = "building"
        if update:
            self.set_construction_project_status(project, "building")
        return info

    def complete_construction_project(self, player, project):
        tile = project.get("tile")
        cost = self.sync_construction_project_fields(project)
        building_key = project.get("building") or cost.get("building")
        if not tile or not building_key:
            return
        coverage = getattr(tile, "building_coverage", None)
        if coverage is None:
            coverage = {}
            tile.building_coverage = coverage
        coverage[building_key] = min(1.0, max(coverage.get(building_key, 0.0), cost.get("target_coverage", 0.0)))
        if not hasattr(tile, "buildings") or tile.buildings is None:
            tile.buildings = []
        if building_key not in tile.buildings:
            tile.buildings.append(building_key)
        self.recalculate_state_resources(player)
        self.update_tile_production_cache(tile)
        self.recalculate_player_supply(player)
        self.mark_player_storage_dirty(player)
        self.distribute_player_stockpiles_to_tiles(player)
        self.recalculate_resource_balance_breakdown(player)
        self.recalculate_monthly_balance(player)
        self.tile_visual_revision += 1
        self.invalidate_tile_visual_cache()
        self.invalidate_construction_placement_cache()

    def run_construction_tick(self, player, elapsed_hours=None):
        if not player.construction_queue:
            return
        project = player.construction_queue[0]
        if project.get("paused", False):
            self.evaluate_construction_project_status(player, project, update=True)
            return
        month_fraction = max(0.0, (elapsed_hours or 0.0) / PRODUCTION_MONTH_HOURS)
        if month_fraction <= 0:
            return

        cost = project.get("cost", {})
        money_cost = cost.get("money_cost", 0.0)
        if not project.get("money_paid", False):
            if player.budget < money_cost:
                self.evaluate_construction_project_status(player, project, month_fraction)
                return
            player.budget -= money_cost
            project["money_paid"] = True

        status_info = self.evaluate_construction_project_status(player, project, month_fraction)
        if status_info["status"] != "building":
            return

        resources_spent = project.get("resources_spent", cost.setdefault("resources_spent", {}))
        for key, amount_needed in status_info["resource_needs"].items():
            consumed = self.consume_from_stockpile(player, key, amount_needed)
            resources_spent[key] = resources_spent.get(key, 0.0) + consumed

        project["progress"] = min(1.0, project.get("progress", 0.0) + status_info["progress_delta"])
        self.set_construction_project_status(project, "building")
        self.mark_player_resource_balance_dirty(player)
        if project["progress"] >= 0.999:
            self.complete_construction_project(player, project)
            player.construction_queue.pop(0)
            self.invalidate_construction_placement_cache()

    def active_construction_consumption(self, player):
        if not player.construction_queue:
            return {}
        project = player.construction_queue[0]
        if project.get("paused", False):
            return {}
        status_info = self.evaluate_construction_project_status(
            player,
            project,
            month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
        )
        if status_info["status"] != "building":
            return {}
        monthly_delta = self.construction_project_progress_delta(player, project, month_fraction=1.0)
        return self.construction_project_resource_needs(project, monthly_delta)

    def construction_stall_reasons(self, player):
        if not player.construction_queue:
            return []
        project = player.construction_queue[0]
        if project.get("paused", False):
            return []
        status_info = self.evaluate_construction_project_status(
            player,
            project,
            month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
        )
        if status_info["status"] in ("waiting_money", "waiting_resources", "waiting_power"):
            return status_info["reasons"]
        return []

    def construction_warning_summary(self, player):
        reasons = self.construction_stall_reasons(player)
        if not reasons:
            return None
        project = player.construction_queue[0]
        status_label = self.construction_project_status_label(project.get("status", "queued"))
        return {
            "level": "red",
            "title": f"Стройка: {status_label}",
            "lines": [self.construction_project_label(project)] + reasons[:5],
        }

    def population_income_rate_for_tile(self, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        weighted_income = POPULATION_INCOME_PER_MILLION["rural"]
        total_weight = 1.0
        for building_key, weight_multiplier in POPULATION_INCOME_TYPE_WEIGHTS.items():
            weight = max(0.0, coverage.get(building_key, 0.0)) * weight_multiplier
            if weight <= 0:
                continue
            weighted_income += POPULATION_INCOME_PER_MILLION.get(building_key, 0.0) * weight
            total_weight += weight
        return weighted_income / max(1.0, total_weight)

    def monthly_population_income(self, player):
        income = 0.0
        for tile in player.tiles:
            population = self.estimated_tile_population(tile)
            if not population or population <= 0:
                continue
            income += (population / 1_000_000) * self.population_income_rate_for_tile(tile)
        return income

    @staticmethod
    def monthly_company_income(player):
        income = 0.0
        for tile in player.tiles:
            coverage = getattr(tile, "building_coverage", {}) or {}
            for building_key, amount_per_coverage in COMPANY_INCOME_PER_COVERAGE.items():
                income += max(0.0, coverage.get(building_key, 0.0)) * amount_per_coverage
        return income

    def monthly_tile_company_income(self, tile):
        income = 0.0
        coverage = getattr(tile, "building_coverage", {}) or {}
        for building_key, amount_per_coverage in COMPANY_INCOME_PER_COVERAGE.items():
            income += max(0.0, coverage.get(building_key, 0.0)) * amount_per_coverage
        return income

    def monthly_tile_population_income(self, tile):
        population = self.estimated_tile_population(tile)
        if not population or population <= 0:
            return 0.0
        return (population / 1_000_000) * self.population_income_rate_for_tile(tile)

    def monthly_tile_income(self, tile):
        return self.monthly_tile_population_income(tile) + self.monthly_tile_company_income(tile)

    def monthly_government_expenses(self, player):
        population_millions = max(0.0, (player.population or 0.0) / 1_000_000)
        land_tiles = sum(1 for tile in player.tiles if not self.is_water_tile(tile))
        return (
            MONEY_GOVERNMENT_BASE_EXPENSE
            + population_millions * MONEY_GOVERNMENT_PER_MILLION
            + land_tiles * MONEY_GOVERNMENT_PER_TILE
        )

    def monthly_social_expenses_breakdown(self, player):
        pensions = 0.0
        children = 0.0
        disability = 0.0
        local_services = 0.0
        for tile in player.tiles:
            population = self.estimated_tile_population(tile) or 0.0
            if population <= 0:
                continue
            coverage = getattr(tile, "building_coverage", {}) or {}
            city_share = self.clamp01(coverage.get("city", 0.0))
            village_share = self.clamp01(coverage.get("village", 0.0))
            population_millions = population / 1_000_000
            pensions += (
                population_millions
                * DEMOGRAPHIC_AGE_SHARES.get("elderly", 0.0)
                * MONEY_SOCIAL_PENSION_PER_ELDERLY_MILLION
            )
            children += (
                population_millions
                * DEMOGRAPHIC_AGE_SHARES.get("children", 0.0)
                * MONEY_SOCIAL_CHILD_SERVICES_PER_CHILD_MILLION
            )
            disability += population_millions * MONEY_SOCIAL_DISABILITY_PER_MILLION
            local_services += population_millions * (
                MONEY_SOCIAL_CITY_SERVICES_PER_MILLION * city_share
                + MONEY_SOCIAL_VILLAGE_SERVICES_PER_MILLION * village_share
            )
        return {
            "pensions": pensions,
            "children": children,
            "disability": disability,
            "local_services": local_services,
            "total": pensions + children + disability + local_services,
        }

    def monthly_social_expenses(self, player):
        return self.monthly_social_expenses_breakdown(player)["total"]

    @staticmethod
    def monthly_infrastructure_expenses(player):
        expenses = 0.0
        for tile in player.tiles:
            coverage = getattr(tile, "building_coverage", {}) or {}
            for building_key, amount_per_coverage in INFRASTRUCTURE_UPKEEP_PER_COVERAGE.items():
                expenses += max(0.0, coverage.get(building_key, 0.0)) * amount_per_coverage
        return expenses

    def monthly_army_expenses(self, player):
        return MONEY_ARMY_BASE_EXPENSE

    def monthly_expenses(self, player):
        army = self.monthly_army_expenses(player)
        government = self.monthly_government_expenses(player)
        social_breakdown = self.monthly_social_expenses_breakdown(player)
        social = social_breakdown["total"]
        infrastructure = self.monthly_infrastructure_expenses(player)
        return {
            "army": army,
            "government": government,
            "social": social,
            "social_breakdown": social_breakdown,
            "infrastructure": infrastructure,
            "total": army + government + social + infrastructure,
        }

    def recalculate_monthly_balance(self, player):
        population_income = self.monthly_population_income(player)
        company_income = self.monthly_company_income(player)
        trade_balance = self.estimate_monthly_trade_flows(player)["money_balance"]
        expenses = self.monthly_expenses(player)
        total_income = population_income + company_income + trade_balance
        total_balance = total_income - expenses["total"]
        player.monthly_trade_balance = trade_balance
        player.monthly_income_breakdown = {
            "population": population_income,
            "companies": company_income,
            "trade": trade_balance,
            "multiplier": 1.0,
            "total": total_income,
        }
        player.monthly_expenses_breakdown = expenses
        player.monthly_balance = total_balance
        return total_balance

    def recalculate_all_monthly_balances(self):
        for player in self.players:
            self.recalculate_monthly_balance(player)

    def economy_snapshot(self, player):
        income = player.monthly_income_breakdown or {}
        expenses = player.monthly_expenses_breakdown or self.monthly_expenses(player)
        return {
            "budget": player.budget,
            "population": player.population or 0.0,
            "balance": player.monthly_balance,
            "income": {
                "population": income.get("population", 0.0),
                "companies": income.get("companies", 0.0),
                "trade": income.get("trade", player.monthly_trade_balance),
                "total": income.get("total", 0.0),
            },
            "expenses": {
                "army": expenses.get("army", 0.0),
                "government": expenses.get("government", 0.0),
                "social": expenses.get("social", 0.0),
                "social_breakdown": dict(expenses.get("social_breakdown", {}) or {}),
                "infrastructure": expenses.get("infrastructure", 0.0),
                "total": expenses.get("total", 0.0),
            },
        }

    def update_economy_month_history(self, current_time):
        month_key = (current_time.year, current_time.month)
        for player in self.players:
            if player.economy_month_key is None:
                player.economy_month_key = month_key
                player.economy_current_snapshot = self.economy_snapshot(player)
                continue
            if player.economy_month_key != month_key:
                player.economy_previous_snapshot = player.economy_current_snapshot or self.economy_snapshot(player)
                player.economy_month_key = month_key
            player.economy_current_snapshot = self.economy_snapshot(player)

    def run_economy_tick(self, player, elapsed_hours=None):
        month_fraction = max(0.0, (elapsed_hours or 0.0) / PRODUCTION_MONTH_HOURS)
        if month_fraction <= 0:
            return
        income_breakdown = player.monthly_income_breakdown or {}
        if not income_breakdown:
            self.recalculate_monthly_balance(player)
            income_breakdown = player.monthly_income_breakdown or {}
        population_income = income_breakdown.get("population", 0.0)
        company_income = income_breakdown.get("companies", 0.0)
        expenses = player.monthly_expenses_breakdown or self.monthly_expenses(player)
        player.monthly_expenses_breakdown = expenses
        player.budget += (population_income + company_income - expenses.get("total", 0.0)) * month_fraction
        self.mark_player_resource_balance_dirty(player)

    def run_production_stage(self, player, stage, month_fraction):
        if stage == "agriculture":
            return self.run_agriculture_stage(player, month_fraction)
        if stage == "upkeep":
            return self.run_upkeep_stage(player, month_fraction)

        cache = player.production_cache or self.recalculate_state_production_cache(player)
        planned_inputs = {
            key: amount * month_fraction
            for key, amount in cache[stage]["inputs"].items()
            if amount > 0
        }
        planned_outputs = {
            key: amount * month_fraction
            for key, amount in cache[stage]["outputs"].items()
            if amount > 0
        }

        actual_ratio = 1.0
        for key, required in planned_inputs.items():
            if required <= 0:
                continue
            actual_ratio = min(actual_ratio, self.stockpile_amount(player, key) / required)
        actual_ratio = self.clamp01(actual_ratio)

        for key, required in planned_inputs.items():
            self.consume_from_stockpile(player, key, required * actual_ratio)
        for key, output in planned_outputs.items():
            self.add_to_stockpile(player, key, output * actual_ratio)
        return actual_ratio

    def run_upkeep_stage(self, player, month_fraction):
        cache = player.production_cache or self.recalculate_state_production_cache(player)
        planned_inputs = {
            key: amount * month_fraction
            for key, amount in cache["upkeep"]["inputs"].items()
            if amount > 0
        }
        ratios = []
        for key, required in planned_inputs.items():
            consumed = self.consume_from_stockpile(player, key, required)
            ratios.append(consumed / required if required > 0 else 1.0)
        if not ratios:
            return 1.0
        return min(ratios)

    def run_agriculture_stage(self, player, month_fraction):
        cache = player.production_cache or self.recalculate_state_production_cache(player)
        planned_fertilizer = cache["agriculture"]["inputs"].get("fertilizer", 0.0) * month_fraction
        planned_bonus_food = cache["agriculture"]["outputs"].get("food", 0.0) * month_fraction
        if planned_fertilizer <= 0 or planned_bonus_food <= 0:
            return 0.0

        consumed_fertilizer = self.consume_from_stockpile(player, "fertilizer", planned_fertilizer)
        fertilizer_ratio = self.clamp01(consumed_fertilizer / planned_fertilizer)
        if fertilizer_ratio > 0:
            self.add_to_stockpile(player, "food", planned_bonus_food * fertilizer_ratio)
        return fertilizer_ratio

    def run_production_tick(self, player, elapsed_hours=None):
        if player.production_cache is None:
            self.recalculate_state_production_cache(player)
        month_fraction = max(0.0, (elapsed_hours or 0.0) / PRODUCTION_MONTH_HOURS)
        if month_fraction <= 0:
            return
        for stage in PRODUCTION_STAGES:
            self.run_production_stage(player, stage, month_fraction)
        self.mark_player_resource_balance_dirty(player)

    @staticmethod
    def top_resource_items(resources, limit=3):
        return [
            (key, value)
            for key, value in sorted(resources.items(), key=lambda item: item[1], reverse=True)
            if value > 0
        ][:limit]

    @staticmethod
    def format_resource_amount(amount):
        sign = "-" if amount < 0 else ""
        value = abs(amount)
        if value >= 1_000_000:
            return f"{sign}{value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{sign}{value / 1_000:.1f}K"
        return f"{sign}{value:.0f}"

    @staticmethod
    def resource_duration_months(stock, production, consumption):
        net_consumption = max(0.0, (consumption or 0.0) - (production or 0.0))
        if stock is None or net_consumption <= 0:
            return None
        if stock <= 0:
            return 0.0
        return stock / net_consumption

    @staticmethod
    def format_resource_duration(months):
        if months is None:
            return "--"
        if months <= 0:
            return "0 дн."

        days = max(1, math.ceil(months * 30))
        if days < 7:
            return f"{days} дн."

        weeks = max(1, math.ceil(days / 7))
        if weeks < 5:
            return f"{weeks} нед."

        whole_months = max(1, math.ceil(months))
        if whole_months < 12:
            return f"{whole_months} мес."

        years = months / 12
        if years > 5:
            return "> 5 лет"
        if years < 2:
            return "1 год"
        return f"{math.ceil(years)} г."

    @staticmethod
    def format_build_duration(months):
        if months is None:
            return "нет скорости"
        if months <= 0:
            return "0 ч."

        hours = max(1, math.ceil(months * PRODUCTION_MONTH_HOURS))
        days = hours // 24
        remaining_hours = hours % 24
        if hours < 72:
            if days <= 0:
                return f"{hours} ч."
            if remaining_hours <= 0:
                return f"{days} дн."
            return f"{days} дн. {remaining_hours} ч."
        return Game.format_resource_duration(months)

    @staticmethod
    def resource_duration_color(months):
        if months is None:
            return (170, 184, 198)
        if months < 1:
            return (238, 104, 94)
        if months < 3:
            return (238, 198, 90)
        if months < 6:
            return (176, 214, 92)
        return (112, 214, 132)

    @staticmethod
    def resource_display_name(resource_key):
        return RESOURCE_DISPLAY_NAMES.get(resource_key, resource_key)

    @staticmethod
    def resource_usage_description(resource_key):
        return RESOURCE_USAGE_DESCRIPTIONS.get(
            resource_key,
            "Будет использоваться в будущих цепочках производства и потребления.",
        )

    @staticmethod
    def wrap_text_lines(text, width=29, max_lines=6):
        lines = textwrap.wrap(text, width=width)
        return lines[:max_lines]

    @staticmethod
    def format_money(amount):
        sign = "-" if amount < 0 else ""
        value = abs(amount)
        if value >= 1_000_000_000:
            return f"{sign}${value / 1_000_000_000:.1f}B"
        if value >= 1_000_000:
            return f"{sign}${value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"{sign}${value / 1_000:.1f}K"
        return f"{sign}${value:.0f}"

    @staticmethod
    def format_money_delta(amount):
        if amount > 0:
            return f"+{Game.format_money(amount)}"
        return Game.format_money(amount)

    @staticmethod
    def format_population_delta(amount):
        if amount is None:
            return "--"
        sign = "+" if amount > 0 else "-" if amount < 0 else ""
        return f"{sign}{Game.format_population(abs(amount))}"

    @staticmethod
    def format_population(population):
        if population is None:
            return "--"
        if population >= 1_000_000:
            return f"{population / 1_000_000:.1f}M"
        if population >= 1_000:
            return f"{population / 1_000:.1f}K"
        return f"{population:.0f}"

    @staticmethod
    def terrain_display_name(terrain_key):
        return TERRAIN_DISPLAY_NAMES.get(terrain_key, terrain_key or "--")

    @staticmethod
    def climate_display_name(tile):
        temperature = getattr(tile, "temperature", 0.5)
        moisture = getattr(tile, "moisture", 0.5)
        if temperature < 0.22:
            heat = "холодный"
        elif temperature > 0.68:
            heat = "жаркий"
        else:
            heat = "умеренный"

        if moisture < 0.28:
            humidity = "сухой"
        elif moisture > 0.62:
            humidity = "влажный"
        else:
            humidity = "нормальный"
        return f"{heat}, {humidity}"

    @staticmethod
    def format_percent(value):
        return f"{max(0.0, min(1.0, value)):.0%}"

    @staticmethod
    def format_temperature(value):
        celsius = round(-20 + max(0.0, min(1.0, value)) * 70)
        return f"{celsius}°C"

    @staticmethod
    def format_elevation(value):
        value = max(0.0, min(1.0, value))
        if value >= WATER_LEVEL:
            meters = round((value - WATER_LEVEL) / max(0.001, 1.0 - WATER_LEVEL) * 3000)
        else:
            meters = -round((WATER_LEVEL - value) / max(0.001, WATER_LEVEL) * 350)
        return f"{meters} м"

    @staticmethod
    def format_tile_coverage_total(value):
        if value >= 1.0:
            return f"{value:.1f} клет."
        return f"{value:.0%}"

    @staticmethod
    def average_tile_value(tiles, attr_name, default=0.0):
        if not tiles:
            return default
        return sum(getattr(tile, attr_name, default) for tile in tiles) / len(tiles)

    @staticmethod
    def mixed_or_single(values, mixed_label="Разные"):
        clean_values = [value for value in values if value]
        if not clean_values:
            return "--"
        first = clean_values[0]
        return first if all(value == first for value in clean_values) else mixed_label

    def estimated_tile_population(self, tile):
        if hasattr(tile, "population") and tile.population is not None:
            return tile.population
        owner = tile.owner
        if not owner or not owner.population or not owner.tiles:
            return None

        total_weight = 0.0
        tile_weight = 0.0
        for owned_tile in owner.tiles:
            weight = self.tile_population_weight(owned_tile)
            total_weight += weight
            if owned_tile == tile:
                tile_weight = weight
        if total_weight <= 0:
            return None
        return owner.population * tile_weight / total_weight

    @staticmethod
    def tile_population_weight(tile):
        if tile.terrain_type in ["deep_ocean", "ocean", "shallow_water", "lake"]:
            return 0.05
        weight = 1.0
        if tile.terrain_type in ["mountains", "snowy_mountains", "desert", "tundra"]:
            weight *= 0.45
        elif tile.terrain_type in ["hills", "swamp", "bog"]:
            weight *= 0.7
        weight *= 0.6 + getattr(tile, "grass_cover", 0.0) * 0.7 + getattr(tile, "tree_cover", 0.0) * 0.25
        coverage = getattr(tile, "building_coverage", {}) or {}
        weight += coverage.get("city", 0.0) * 8.0
        weight += coverage.get("village", 0.0) * 3.0
        weight += coverage.get("farms", 0.0) * 1.5
        return max(0.05, weight)

    def tile_population_capacity(self, tile):
        if self.is_water_tile(tile):
            capacity = POPULATION_CAPACITY_BASE_WATER
        else:
            capacity = POPULATION_CAPACITY_BASE_LAND
        coverage = getattr(tile, "building_coverage", {}) or {}
        for building_key, capacity_per_coverage in POPULATION_CAPACITY_PER_COVERAGE.items():
            capacity += max(0.0, coverage.get(building_key, 0.0)) * capacity_per_coverage
        return max(0.0, capacity)

    def tile_population_max_capacity(self, tile):
        return self.tile_population_capacity(tile) * POPULATION_MAX_OVERCAPACITY

    @staticmethod
    def tile_population(tile):
        return max(0.0, getattr(tile, "population", 0.0) or 0.0)

    def population_demographic_summary(self, player):
        population = max(0.0, player.population or self.sync_player_population_from_tiles(player))
        age = {
            key: population * share
            for key, share in DEMOGRAPHIC_AGE_SHARES.items()
        }
        gender = {
            key: population * share
            for key, share in DEMOGRAPHIC_GENDER_SHARES.items()
        }
        working_age = age.get("working_age", 0.0)
        obligated = working_age * MILITARY_OBLIGATION_WORKING_AGE_SHARE
        willingness = self.clamp01(
            MOBILIZATION_VOLUNTEER_BASE_SHARE
            + player.war_support * MOBILIZATION_WAR_SUPPORT_WEIGHT
            + player.stability * MOBILIZATION_STABILITY_WEIGHT
            + player.legitimacy * MOBILIZATION_LEGITIMACY_WEIGHT
        )
        willingness = min(MOBILIZATION_VOLUNTEER_MAX_SHARE, willingness)
        volunteers = obligated * willingness
        return {
            "population": population,
            "age": age,
            "gender": gender,
            "military_obligated": obligated,
            "volunteer_share": willingness,
            "mobilization_available": volunteers,
        }

    def sync_player_population_from_tiles(self, player):
        total = sum(self.tile_population(tile) for tile in player.tiles)
        if total > 0:
            player.population = total
        return player.population or 0.0

    def add_population_to_available_capacity(self, player, amount):
        remaining = max(0.0, amount)
        added = 0.0
        for _pass in range(3):
            if remaining <= 0:
                break
            candidates = []
            total_weight = 0.0
            for tile in player.tiles:
                free_capacity = max(0.0, self.tile_population_max_capacity(tile) - self.tile_population(tile))
                if free_capacity <= 1:
                    continue
                weight = free_capacity * (0.35 + self.tile_population_weight(tile))
                candidates.append((tile, free_capacity, weight))
                total_weight += weight
            if total_weight <= 0:
                break
            pass_added = 0.0
            for tile, free_capacity, weight in candidates:
                share = remaining * weight / total_weight
                delta = min(free_capacity, share)
                if delta <= 0:
                    continue
                tile.population = self.tile_population(tile) + delta
                pass_added += delta
            remaining -= pass_added
            added += pass_added
            if pass_added <= 0:
                break
        return added

    def enforce_population_capacity(self, player):
        excess = 0.0
        for tile in player.tiles:
            population = self.tile_population(tile)
            max_capacity = self.tile_population_max_capacity(tile)
            if population <= max_capacity:
                continue
            overflow = population - max_capacity
            tile.population = max_capacity
            excess += overflow
        if excess > 0:
            self.add_population_to_available_capacity(player, excess)
        self.sync_player_population_from_tiles(player)

    def population_resource_ratio(self, player, resource_key):
        monthly_need = self.production_amount_for_key(player, resource_key, "inputs")
        if monthly_need <= 0:
            return 1.25
        stock = self.stockpile_amount(player, resource_key)
        monthly_output = self.production_amount_for_key(player, resource_key, "outputs")
        return max(0.0, min(1.25, (stock + monthly_output) / monthly_need))

    def population_growth_multiplier(self, player):
        food_ratio = self.population_resource_ratio(player, "food")
        goods_ratio = self.population_resource_ratio(player, "consumer_goods")
        welfare = min(food_ratio, goods_ratio)
        if welfare >= 1.0:
            welfare_factor = min(1.15, 0.95 + (welfare - 1.0) * 0.2)
        elif welfare >= 0.70:
            welfare_factor = (welfare - 0.70) / 0.30
        else:
            welfare_factor = -min(2.0, (0.70 - welfare) / 0.70 * 1.8)

        supply = (player.supply_summary or {}).get("average", 1.0)
        supply_factor = 0.45 + self.clamp01(supply) * 0.55
        return welfare_factor * supply_factor

    def apply_positive_population_growth(self, player, month_fraction, growth_multiplier):
        monthly_rate = POPULATION_BASE_ANNUAL_GROWTH / 12
        if monthly_rate <= 0 or month_fraction <= 0 or growth_multiplier <= 0:
            return 0.0

        added = 0.0
        for tile in player.tiles:
            population = self.tile_population(tile)
            max_population = self.tile_population_capacity(tile)
            max_overcapacity = self.tile_population_max_capacity(tile)
            if population <= 0 or max_population <= 0:
                continue
            free_capacity = max(0.0, max_overcapacity - population)
            if free_capacity <= 0:
                continue
            capacity_pressure = 0.1 + 0.9 * ((POPULATION_MAX_OVERCAPACITY * max_population - population) / population)
            capacity_pressure = max(0.0, capacity_pressure)
            delta = population * monthly_rate * month_fraction * growth_multiplier * capacity_pressure
            delta = min(free_capacity, delta)
            if delta <= 0:
                continue
            tile.population = population + delta
            added += delta

        if added > 0:
            self.sync_player_population_from_tiles(player)
        return added

    def apply_population_delta(self, player, delta):
        if abs(delta) <= 0:
            return 0.0
        if delta > 0:
            added = self.add_population_to_available_capacity(player, delta)
            self.sync_player_population_from_tiles(player)
            return added

        total_population = self.sync_player_population_from_tiles(player)
        loss = min(total_population, abs(delta))
        if total_population <= 0 or loss <= 0:
            return 0.0
        for tile in player.tiles:
            population = self.tile_population(tile)
            if population <= 0:
                continue
            tile.population = max(0.0, population - loss * population / total_population)
        self.sync_player_population_from_tiles(player)
        return -loss

    def grow_settlements_from_overcrowding(self, player, month_fraction):
        changed = False
        for tile in player.tiles:
            coverage = getattr(tile, "building_coverage", {}) or {}
            population = self.tile_population(tile)
            capacity = self.tile_population_capacity(tile)
            if population <= 0 or capacity <= 0:
                continue
            overcrowding = self.clamp01((population / capacity - 1.0) / (POPULATION_MAX_OVERCAPACITY - 1.0))
            if overcrowding <= 0:
                continue
            for building_key, annual_growth in (
                ("city", CITY_NATURAL_ANNUAL_GROWTH),
                ("village", VILLAGE_NATURAL_ANNUAL_GROWTH),
            ):
                current = coverage.get(building_key, 0.0)
                if current <= 0:
                    continue
                max_coverage = INFRASTRUCTURE_COVERAGE_LIMITS[building_key][1]
                delta = current * annual_growth / 12 * month_fraction * overcrowding
                if delta <= 0:
                    continue
                new_value = min(max_coverage, current + delta)
                if new_value > current:
                    coverage[building_key] = new_value
                    changed = True
        if changed:
            self.recalculate_state_production_cache(player)
            self.recalculate_player_supply(player)
            self.mark_player_storage_dirty(player)
            self.tile_visual_revision += 1
            self.invalidate_tile_visual_cache()
            self.invalidate_construction_placement_cache()
        return changed

    def run_population_tick(self, player, elapsed_hours=None):
        month_fraction = max(0.0, (elapsed_hours or 0.0) / PRODUCTION_MONTH_HOURS)
        if month_fraction <= 0:
            return
        player.population_month_accumulator += month_fraction
        if player.population_month_accumulator < 1.0:
            return

        accumulated_months = player.population_month_accumulator
        player.population_month_accumulator = 0.0
        self.enforce_population_capacity(player)
        population = self.sync_player_population_from_tiles(player)
        if population <= 0:
            return

        growth_multiplier = self.population_growth_multiplier(player)
        if growth_multiplier > 0:
            self.apply_positive_population_growth(player, accumulated_months, growth_multiplier)
        else:
            monthly_rate = POPULATION_BASE_ANNUAL_GROWTH / 12
            growth = population * monthly_rate * accumulated_months * growth_multiplier
            self.apply_population_delta(player, growth)
        self.grow_settlements_from_overcrowding(player, accumulated_months)
        self.enforce_population_capacity(player)
        self.recalculate_monthly_balance(player)
        self.mark_player_resource_balance_dirty(player)

    def hex_resource_rows(self, tile):
        stockpiles = {}
        if tile.owner:
            for category_stockpiles in (getattr(tile, "resource_stockpiles", {}) or {}).values():
                for key, amount in category_stockpiles.items():
                    stockpiles[key] = stockpiles.get(key, 0.0) + amount

        rows = []
        seen = set()
        for resource in getattr(tile, "resources", []):
            if len(resource) < 3:
                continue
            key, depth, mass = resource
            ground_amount = max(0.0, float(mass))
            stock_amount = max(0.0, float(stockpiles.get(key, 0.0)))
            if ground_amount <= 0 and stock_amount <= 0:
                continue
            rows.append(
                {
                    "key": key,
                    "name": self.resource_display_name(key),
                    "ground": ground_amount,
                    "stock": stock_amount,
                    "depth": float(depth),
                }
            )
            seen.add(key)

        for key, stock_amount in stockpiles.items():
            if key in seen or stock_amount <= 0:
                continue
            rows.append(
                {
                    "key": key,
                    "name": self.resource_display_name(key),
                    "ground": 0.0,
                    "stock": stock_amount,
                    "depth": None,
                }
            )

        return rows

    def hex_resource_rows_for_tiles(self, tiles):
        tiles = [tile for tile in tiles if tile]
        owners = {}
        for tile in tiles:
            if tile.owner:
                owners[id(tile.owner)] = tile.owner
        for owner in owners.values():
            self.ensure_player_tile_stockpiles(owner)
        if len(tiles) == 1:
            return self.hex_resource_rows(tiles[0])

        totals = {}
        for tile in tiles:
            for row in self.hex_resource_rows(tile):
                key = row["key"]
                total = totals.setdefault(
                    key,
                    {
                        "key": key,
                        "name": self.resource_display_name(key),
                        "ground": 0.0,
                        "stock": 0.0,
                        "depth": row.get("depth"),
                    },
                )
                total["ground"] += row.get("ground", 0.0)
                total["stock"] += row.get("stock", 0.0)
                depth = row.get("depth")
                if depth is not None:
                    total["depth"] = depth if total["depth"] is None else min(total["depth"], depth)

        return sorted(
            totals.values(),
            key=lambda row: row["ground"] + row["stock"],
            reverse=True,
        )

    def building_coverage_rows_for_tiles(self, tiles):
        totals = {}
        listed_buildings = set()
        for tile in tiles:
            for key, value in (getattr(tile, "building_coverage", {}) or {}).items():
                if value > 0:
                    totals[key] = totals.get(key, 0.0) + value
            for key in getattr(tile, "buildings", []) or []:
                if key in BUILDING_DISPLAY_NAMES:
                    listed_buildings.add(key)
        return totals, listed_buildings

    def selected_industry_allocation_summary(self, industry_tiles):
        totals = {}
        if not industry_tiles:
            return {}
        for tile in industry_tiles:
            allocation = getattr(tile, "industry_allocation", {}) or {}
            if not allocation:
                allocation = self.assign_industry_allocation(tile.owner, tile) if tile.owner else {}
            else:
                allocation = self.normalize_industry_allocation(allocation)
                tile.industry_allocation = allocation
            for sector, share in allocation.items():
                totals[sector] = totals.get(sector, 0.0) + share
        return {
            sector: share / len(industry_tiles)
            for sector, share in totals.items()
            if share > 0
        }

    def selected_industry_efficiency(self, industry_tiles):
        if not industry_tiles:
            return 0.0
        total = 0.0
        for tile in industry_tiles:
            allocation = getattr(tile, "industry_allocation", {}) or {}
            if not allocation:
                allocation = self.assign_industry_allocation(tile.owner, tile) if tile.owner else {}
            else:
                allocation = self.normalize_industry_allocation(allocation)
                tile.industry_allocation = allocation
            modifiers = tile.owner.production_modifiers if tile.owner else {}
            total += self.specialization_efficiency(
                allocation,
                modifiers.get("industry_diversification_penalty", 0.9),
                modifiers.get("industry_free_specializations", 1),
            )
        return total / len(industry_tiles)

    def load_top_nav_icon_textures(self):
        textures = {}
        for key, _label, file_name in TOP_NAV_TABS:
            path = UI_ICON_DIR / file_name
            if path.exists():
                textures[key] = arcade.load_texture(str(path))
        return textures

    def player_resource_summary(self, player):
        stockpiles = self.ensure_player_stockpiles(player)
        raw = stockpiles.get("raw", {})
        finished = stockpiles.get("finished", {})
        metal_keys = [
            "iron_ore", "copper_ore", "bauxite", "lead", "zinc", "nickel",
            "gold", "silver", "rare_earth_metals", "alloying_additives",
        ]
        fuel_keys = ["coal", "oil", "natural_gas", "peat", "uranium"]
        metals = sum(raw.get(key, 0.0) for key in metal_keys)
        fuel = sum(raw.get(key, 0.0) for key in fuel_keys)
        consumer_goods = finished.get("consumer_goods", 0.0)
        return metals, fuel, consumer_goods

    def resource_problem_summary(self, player):
        breakdown = self.cached_resource_balance_breakdown(player)
        problems = {
            "raw": {"yellow": [], "red": []},
            "semi_finished": {"yellow": [], "red": []},
            "finished": {"yellow": [], "red": []},
        }
        for category, entries in breakdown.items():
            for key, entry in entries.items():
                if entry.get("consumption", 0.0) <= entry.get("production", 0.0):
                    continue
                months_left = entry.get("months")
                if months_left is not None and months_left < 1:
                    problems[category]["red"].append(key)
                elif months_left is not None and months_left < 3:
                    problems[category]["yellow"].append(key)

        return problems

    def resource_surplus_summary(self, player):
        breakdown = self.cached_resource_balance_breakdown(player)
        surplus = {
            "raw": [],
            "semi_finished": [],
            "finished": [],
        }
        for category, entries in breakdown.items():
            for key, entry in entries.items():
                consumption = entry.get("consumption", 0.0)
                if consumption > 0 and entry.get("stock", 0.0) / consumption >= 6.0:
                    surplus[category].append(key)

        return surplus

    def storage_problem_summary(self, player):
        self.ensure_player_storage(player)
        problems = {"yellow": [], "red": []}
        for category_key in STORAGE_CATEGORIES:
            capacity = player.storage_capacity.get(category_key, 0.0)
            used = player.storage_used.get(category_key, 0.0)
            if capacity <= 0:
                if used > 0:
                    problems["red"].append(category_key)
                continue
            fullness = used / capacity
            if fullness >= 1.0:
                problems["red"].append(category_key)
            elif fullness >= 0.88:
                problems["yellow"].append(category_key)
        return problems

    def resource_problem_level(self, player):
        problems = self.resource_problem_summary(player)
        storage = self.storage_problem_summary(player)
        if any(problems[key]["red"] for key in problems):
            return "red"
        if storage["red"]:
            return "red"
        if any(problems[key]["yellow"] for key in problems):
            return "yellow"
        if storage["yellow"]:
            return "yellow"
        return "green"

    @staticmethod
    def problem_color(level):
        if level == "red":
            return (112, 42, 42, 225)
        if level == "yellow":
            return (112, 92, 42, 225)
        return (38, 82, 54, 215)

    def load_tile_visual_textures(self):
        textures = {}
        for key, file_name in TILE_VISUAL_ASSETS.items():
            path = TILE_VISUAL_DIR / file_name
            if path.exists():
                textures[key] = arcade.load_texture(str(path))
        return textures

    @staticmethod
    def normalized_coverage_items(coverages):
        return [(key, value) for key, value in coverages.items() if value >= VISUAL_MIN_COVERAGE]

    def natural_coverages(self, tile):
        if self.is_water_tile(tile):
            water = max(0.35, tile.water_cover)
            return {"water": min(1.0, water)}

        return {
            "forest": tile.tree_cover,
            "grassland": tile.grass_cover,
            "desert": tile.sand_cover,
            "mountains": max(tile.rock_cover, tile.ridge_value),
            "snowfield": tile.snow_cover,
        }

    def human_coverages(self, tile):
        coverages = dict(getattr(tile, "building_coverage", {}) or {})
        if coverages.get("port", 0.0) > 0 and not self.is_coastal_land_tile(tile):
            coverages.pop("port", None)
        return coverages

    def ranked_visual_factors(self, tile, include_natural=True, include_human=True):
        factors = {}
        if include_natural:
            factors.update(self.natural_coverages(tile))
        if include_human:
            for key, value in self.human_coverages(tile).items():
                factors[key] = max(factors.get(key, 0.0), value)

        return sorted(
            self.normalized_coverage_items(factors),
            key=lambda item: item[1] * VISUAL_FACTOR_WEIGHTS.get(item[0], 1.0),
            reverse=True,
        )

    def visual_factor_size(self, coverage, minimum, scale, maximum):
        return min(maximum, minimum + math.sqrt(max(0.0, coverage)) * scale)

    def append_visual_factor_sprite(self, key, x, y, size, alpha=230):
        texture = self.tile_visual_textures.get(key)
        if not texture:
            return

        sprite = arcade.Sprite(texture)
        sprite.center_x = x
        sprite.center_y = y
        sprite.width = size
        sprite.height = size
        sprite.alpha = alpha
        self.tile_visual_sprite_list.append(sprite)

    def edge_anchor(self, tile, edge_index, edge_amount=0.72):
        x1, y1 = tile.corners[edge_index]
        x2, y2 = tile.corners[(edge_index + 1) % 6]
        edge_x = (x1 + x2) / 2
        edge_y = (y1 + y2) / 2
        return (
            tile.center_x * (1 - edge_amount) + edge_x * edge_amount,
            tile.center_y * (1 - edge_amount) + edge_y * edge_amount,
        )

    def best_neighbor_edge_for_factor(self, tile, factor_key):
        if factor_key == "port":
            return self.water_edge_for_port(tile)

        best_edge = None
        best_value = 0.0
        for edge_index in range(6):
            neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
            if not neighbor:
                continue

            value = self.human_coverages(neighbor).get(factor_key, 0.0)
            value = max(value, self.natural_coverages(neighbor).get(factor_key, 0.0))
            if value > best_value:
                best_edge = edge_index
                best_value = value
        return best_edge, best_value

    def water_edge_for_port(self, tile):
        for edge_index in range(6):
            neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
            if neighbor and self.is_water_tile(neighbor):
                return edge_index, 1.0
        return None, 0.0

    def fallback_edge_factor(self, tile, excluded_key=None):
        for key, coverage in self.ranked_visual_factors(tile, include_natural=True, include_human=False):
            if key != excluded_key and key != "water":
                return key, coverage
        return None, 0.0

    def edge_visual_factor(self, tile, edge_index, center_natural_key):
        neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
        if neighbor:
            ranked = self.ranked_visual_factors(neighbor, include_natural=True, include_human=True)
            for key, coverage in ranked:
                if key != "water":
                    return key, coverage

        return self.fallback_edge_factor(tile, excluded_key=center_natural_key)

    def reserve_human_edge_slots(self, tile, human_factors, max_slots=6):
        reserved_edges = {}
        used_edges = set()
        extras = human_factors[1:1 + max_slots]

        for key, _coverage in extras:
            edge_index, neighbor_value = self.best_neighbor_edge_for_factor(tile, key)
            if edge_index in used_edges or neighbor_value < VISUAL_MIN_COVERAGE:
                edge_index = None

            if edge_index is None:
                for candidate_edge in range(6):
                    if candidate_edge not in used_edges:
                        edge_index = candidate_edge
                        break

            if edge_index is None:
                break

            reserved_edges[edge_index] = key
            used_edges.add(edge_index)

        return reserved_edges

    def draw_tile_edge_visuals(self, tile, center_natural_key, reserved_edges=None):
        reserved_edges = reserved_edges or {}
        used_edges = set()
        for edge_index in range(6):
            if edge_index in reserved_edges:
                used_edges.add(edge_index)
                continue

            key, coverage = self.edge_visual_factor(tile, edge_index, center_natural_key)
            if not key:
                continue

            x, y = self.edge_anchor(tile, edge_index)
            size = self.visual_factor_size(coverage, HEX_SIZE * 0.16, HEX_SIZE * 0.18, HEX_SIZE * 0.36)
            self.append_visual_factor_sprite(key, x, y, size, alpha=145)
            used_edges.add(edge_index)
        return used_edges

    def draw_tile_center_visuals(
        self,
        tile,
        center_natural_key,
        center_natural_coverage,
        used_edges,
        draw_natural=True,
        human_factors=None,
        human_edge_slots=None,
    ):
        if draw_natural and center_natural_key:
            size = self.visual_factor_size(
                center_natural_coverage,
                HEX_SIZE * 0.28,
                HEX_SIZE * 0.38,
                HEX_SIZE * 0.86,
            )
            self.append_visual_factor_sprite(center_natural_key, tile.center_x, tile.center_y, size, alpha=175)

        if human_factors is None:
            human_factors = self.ranked_visual_factors(tile, include_natural=False, include_human=True)
        if not human_factors:
            return

        human_edge_slots = human_edge_slots or {}
        main_key, main_coverage = human_factors[0]
        main_size = self.visual_factor_size(main_coverage, HEX_SIZE * 0.25, HEX_SIZE * 0.42, HEX_SIZE * 0.74)
        self.append_visual_factor_sprite(main_key, tile.center_x, tile.center_y, main_size, alpha=255)

        slot_by_key = {key: edge_index for edge_index, key in human_edge_slots.items()}
        fallback_edges = [edge_index for edge_index in range(6) if edge_index not in used_edges]
        for key, coverage in human_factors[1:7]:
            edge_index = slot_by_key.get(key)
            if edge_index is None and fallback_edges:
                edge_index = fallback_edges.pop(0)
            if edge_index is None:
                continue

            x, y = self.edge_anchor(tile, edge_index, edge_amount=0.50)
            used_edges.add(edge_index)

            size = self.visual_factor_size(coverage, HEX_SIZE * 0.20, HEX_SIZE * 0.30, HEX_SIZE * 0.50)
            self.append_visual_factor_sprite(key, x, y, size, alpha=248)

    def tile_visual_zoom_mode(self):
        zoom = self.world_camera.zoom
        if self.map_layer != "terrain" or zoom < VISUAL_SYSTEM_MIN_ZOOM:
            return None

        visible_count = len(self.visible_tiles)
        if visible_count > VISUAL_DENSE_TILE_LIMIT:
            return "dense"
        if zoom >= VISUAL_EDGE_MIN_ZOOM and visible_count <= VISUAL_EDGE_TILE_LIMIT:
            return "edges"
        return "center"

    def rebuild_dense_tile_visual_sprites(self):
        candidates = []
        for tile in self.visible_tiles:
            if self.is_water_tile(tile):
                continue
            human_factors = self.ranked_visual_factors(tile, include_natural=False, include_human=True)
            if not human_factors:
                continue
            key, coverage = human_factors[0]
            score = coverage * VISUAL_FACTOR_WEIGHTS.get(key, 1.0)
            candidates.append((score, tile, key, coverage))

        candidates.sort(key=lambda item: item[0], reverse=True)
        for _score, tile, key, coverage in candidates[:VISUAL_DENSE_SPRITE_LIMIT]:
            size = self.visual_factor_size(coverage, HEX_SIZE * 0.22, HEX_SIZE * 0.32, HEX_SIZE * 0.58)
            self.append_visual_factor_sprite(key, tile.center_x, tile.center_y, size, alpha=225)

    def rebuild_tile_visual_sprites(self, mode):
        self.tile_visual_sprite_list.clear()
        if mode is None:
            return
        if mode == "dense":
            self.rebuild_dense_tile_visual_sprites()
            return

        draw_edges = mode == "edges"
        draw_natural = True
        for tile in self.visible_tiles:
            if self.is_water_tile(tile):
                continue

            human_factors = self.ranked_visual_factors(tile, include_natural=False, include_human=True)

            natural_factors = self.ranked_visual_factors(tile, include_natural=True, include_human=False)
            center_natural_key, center_natural_coverage = natural_factors[0] if natural_factors else (None, 0.0)
            human_edge_slots = self.reserve_human_edge_slots(tile, human_factors) if human_factors else {}
            used_edges = self.draw_tile_edge_visuals(tile, center_natural_key, human_edge_slots) if draw_edges else set()
            self.draw_tile_center_visuals(
                tile,
                center_natural_key,
                center_natural_coverage,
                used_edges,
                draw_natural=draw_natural,
                human_factors=human_factors,
                human_edge_slots=human_edge_slots,
            )

    def draw_tile_visual_system(self):
        mode = self.tile_visual_zoom_mode()
        cache_key = (self.visible_tiles_revision, self.tile_visual_revision, mode)
        if cache_key != self.tile_visual_cache_key:
            self.rebuild_tile_visual_sprites(mode)
            self.tile_visual_cache_key = cache_key

        self.tile_visual_sprite_list.draw()

    def get_current_resolution_index(self):
        if not self.window:
            return 1

        current_size = (self.window.width, self.window.height)
        if current_size in RESOLUTIONS:
            return RESOLUTIONS.index(current_size)

        return min(
            range(len(RESOLUTIONS)),
            key=lambda index: abs(RESOLUTIONS[index][0] - current_size[0]) + abs(RESOLUTIONS[index][1] - current_size[1]),
        )

    def rebuild_pause_menu(self):
        if not self.window:
            return

        self.pause_buttons = []
        self.pause_sliders = []
        self.pause_dropdowns = []
        if self.pause_screen == "settings":
            self.rebuild_pause_settings()
            return

        button_width = 320
        button_height = 44
        gap = 56
        x = self.window.width / 2 - button_width / 2
        y = self.window.height / 2 + 98
        self.pause_buttons = [
            PauseButton("Вернуться в игру", x, y, button_width, button_height, self.resume_game),
            PauseButton("Сохранить", x, y - gap, button_width, button_height, self.save_game),
            PauseButton("Загрузить", x, y - gap * 2, button_width, button_height, self.load_game),
            PauseButton("Выйти в главное меню", x, y - gap * 3, button_width, button_height, self.exit_to_main_menu),
            PauseButton("Выйти на рабочий стол", x, y - gap * 4, button_width, button_height, self.exit_to_desktop),
        ]
        self.pause_buttons.insert(
            3,
            PauseButton("Настройки", x, y - gap * 3, button_width, button_height, self.open_pause_settings),
        )
        self.pause_buttons[4].y = y - gap * 4
        self.pause_buttons[5].y = y - gap * 5

    def rebuild_pause_settings(self):
        panel_x = self.window.width / 2 - 230
        top = self.window.height / 2 + 135
        self.pause_sliders = [
            PauseSlider("Громкость звука", panel_x, top - 70, 460, self.sound_volume, self.set_sound_volume),
            PauseSlider("Громкость музыки", panel_x, top - 140, 460, self.music_volume, self.set_music_volume),
        ]
        self.pause_buttons = [
            PauseButton(
                f"Полный экран: {'Вкл' if self.pending_fullscreen else 'Выкл'}",
                panel_x,
                top - 210,
                220,
                42,
                self.toggle_pending_fullscreen,
            ),
            PauseButton("Применить", panel_x, top - 285, 220, 44, self.apply_pause_settings),
            PauseButton("Назад", panel_x + 240, top - 285, 220, 44, self.close_pause_settings),
        ]
        self.pause_dropdowns = [
            PauseDropdown(
                "resolution",
                "Разрешение",
                [f"{width}x{height}" for width, height in RESOLUTIONS],
                self.pending_resolution_index,
                panel_x + 240,
                top - 210,
                220,
                42,
                self.set_pending_resolution,
            )
        ]

    def create_hex_grid(self):
        self.x_offset = 100
        self.y_offset = 100
        hex_texture = create_hex_texture()
        # landscale = [[0 for i in range(self.grid_width)] for i in range(self.grid_height)]
        for q in range(self.grid_width):
            for r in range(self.grid_height):
                x = self.x_offset + q * HEX_WID + (r % 2) * HEX_WID / 2
                y = self.y_offset + r * HEX_HGT * 0.75
                tile_data = self.world_generator.generate_tile_data(q, r, x, y)
                hex_tile = HexTile(hex_texture=hex_texture, tile_data=tile_data)
                # landscale[q][r] = tile_data.moisture
                self.hex_grid.append(hex_tile)
                self.hex_lookup[(q, r)] = hex_tile
        # plt.imshow(landscale)
        # plt.show()
        print(f"Создано {len(self.hex_grid)} тайлов")

    def spatial_hash_coords(self, x, y):
        return (
            math.floor(x / self.tile_spatial_cell_size),
            math.floor(y / self.tile_spatial_cell_size),
        )

    def build_tile_spatial_hash(self):
        self.tile_spatial_hash.clear()
        for tile in self.hex_grid:
            min_x, min_y, max_x, max_y = tile.bounding_box
            min_cell_x, min_cell_y = self.spatial_hash_coords(min_x, min_y)
            max_cell_x, max_cell_y = self.spatial_hash_coords(max_x, max_y)

            for cell_x in range(min_cell_x, max_cell_x + 1):
                for cell_y in range(min_cell_y, max_cell_y + 1):
                    self.tile_spatial_hash.setdefault((cell_x, cell_y), []).append(tile)

    @staticmethod
    def clamp01(value):
        return max(0.0, min(1.0, value))

    def neighbor_tiles(self, tile):
        neighbors = []
        for edge_index in range(6):
            neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
            if neighbor:
                neighbors.append(neighbor)
        return neighbors

    def owned_neighbor_count(self, player, tile):
        return sum(1 for neighbor in self.neighbor_tiles(tile) if neighbor.owner == player)

    def owned_tiles_within_radius(self, player, tile, radius):
        tiles = []
        for dq in range(-radius, radius + 1):
            for dr in range(-radius, radius + 1):
                ds = -dq - dr
                if max(abs(dq), abs(dr), abs(ds)) > radius:
                    continue
                other = self.hex_lookup.get((tile.q + dq, tile.r + dr))
                if other and other.owner == player:
                    tiles.append(other)
        return tiles

    def division_can_enter_tile(self, division, tile):
        if not tile or self.is_water_tile(tile):
            return False
        return tile.owner == division.owner

    def division_can_capture_tile(self, division, tile):
        if not tile or self.is_water_tile(tile):
            return False
        if not division or tile.owner == division.owner:
            return False
        # Пока дипломатии нет, любая чужая сухопутная клетка считается захватываемой.
        return True

    def division_can_path_through_tile(self, division, tile, target_tile):
        if self.division_can_enter_tile(division, tile):
            return True
        if target_tile and target_tile.owner != division.owner:
            return self.division_can_capture_tile(division, tile)
        return False

    def division_path_expansion_limit(self, start_tile, target_tile):
        distance = self.hex_distance(start_tile, target_tile)
        distance_limit = int(distance * DIVISION_PATH_EXPANSIONS_PER_HEX)
        return min(
            len(self.hex_grid),
            max(DIVISION_PATH_MIN_EXPANSIONS, distance_limit),
        )

    def find_division_path(self, division, target_tile, max_expansions=None, start_tile=None):
        start_tile = start_tile or division.tile
        if not start_tile or not target_tile or start_tile == target_tile:
            return []
        if (
            not self.division_can_enter_tile(division, target_tile)
            and not self.division_can_capture_tile(division, target_tile)
        ):
            return []

        if max_expansions is None:
            max_expansions = self.division_path_expansion_limit(start_tile, target_tile)

        frontier = []
        counter = 0
        heapq.heappush(frontier, (0.0, counter, start_tile))
        start_key = self.tile_key(start_tile)
        target_key = self.tile_key(target_tile)
        came_from = {start_key: None}
        tile_lookup = {start_key: start_tile}
        cost_so_far = {start_key: 0.0}
        expansions = 0

        while frontier and expansions < max_expansions:
            _priority, _counter, current = heapq.heappop(frontier)
            expansions += 1
            if current == target_tile:
                break
            current_key = self.tile_key(current)
            for neighbor in self.neighbor_tiles(current):
                if not self.division_can_path_through_tile(division, neighbor, target_tile):
                    continue
                neighbor_key = self.tile_key(neighbor)
                movement_cost = max(1.0, float(getattr(neighbor, "movement_cost", 1.0) or 1.0))
                new_cost = cost_so_far[current_key] + movement_cost
                if neighbor_key not in cost_so_far or new_cost < cost_so_far[neighbor_key]:
                    cost_so_far[neighbor_key] = new_cost
                    tile_lookup[neighbor_key] = neighbor
                    heuristic = max(abs(neighbor.q - target_tile.q), abs(neighbor.r - target_tile.r))
                    counter += 1
                    heapq.heappush(frontier, (new_cost + heuristic, counter, neighbor))
                    came_from[neighbor_key] = current_key

        if target_key not in came_from:
            return []

        path = []
        current_key = target_key
        while current_key and current_key != start_key:
            path.append(tile_lookup[current_key])
            current_key = came_from.get(current_key)
        path.reverse()
        return path

    def order_selected_divisions_to_tile(self, target_tile, append=False):
        divisions = self.selected_divisions()
        if not divisions or not target_tile:
            return False
        ordered = False
        for division in divisions:
            if division.route_mode == "retreat":
                continue
            if target_tile == division.tile:
                if self.cancel_selected_division_orders_on_tile(target_tile):
                    ordered = True
                continue
            if division.organization < division.max_organization * DIVISION_MIN_ORDER_ORG_RATIO:
                continue
            if division.battle_id:
                self.detach_division_from_battle(division)
            start_tile = division.path[-1] if append and division.path else division.tile
            path = self.find_division_path(division, target_tile, start_tile=start_tile)
            if not path:
                continue
            division.target_tile = target_tile
            if append and division.path:
                division.path.extend(path)
            else:
                division.path = path
                division.movement_progress = 0.0
                division.visual_movement_progress = 0.0
            division.route_mode = "attack" if target_tile.owner and target_tile.owner != division.owner else "move"
            division.route_tiles = [division.tile] + list(division.path)
            ordered = True
        if ordered:
            self.invalidate_division_render_cache()
        return ordered

    def battle_key_for_tile(self, tile):
        return (tile.q, tile.r)

    def division_by_id(self, division_id):
        for division in self.divisions:
            if division.id == division_id:
                return division
        return None

    def enemy_divisions_on_tile(self, tile, owner):
        if not tile or owner is None:
            return []
        return [
            division for division in self.divisions
            if division.tile == tile and division.owner != owner and division.strength > 0
        ]

    def battle_divisions(self, battle, attr):
        return [
            division for division_id in getattr(battle, attr)
            for division in [self.division_by_id(division_id)]
            if division is not None
        ]

    def remove_division_from_battle_lists(self, battle, division):
        for attr in (
            "active_attackers", "reserve_attackers", "recovering_attackers",
            "active_defenders", "reserve_defenders", "recovering_defenders",
        ):
            values = getattr(battle, attr)
            if division.id in values:
                values[:] = [division_id for division_id in values if division_id != division.id]

    def detach_division_from_battle(self, division):
        if not division.battle_id:
            return False
        battle = self.battles.get(division.battle_id)
        if not battle:
            division.battle_id = None
            division.battle_side = None
            division.battle_status = None
            division.width_efficiency = 1.0
            division.post_battle_path = []
            return True

        old_side = division.battle_side
        self.remove_division_from_battle_lists(battle, division)
        division.battle_id = None
        division.battle_side = None
        division.battle_status = None
        division.width_efficiency = 1.0
        division.post_battle_path = []
        if old_side:
            self.rebalance_battle_side(battle, old_side)
            self.rebalance_battle_side(battle, "defender" if old_side == "attacker" else "attacker")
        if (
            not self.battle_divisions(battle, "active_attackers")
            and not self.battle_divisions(battle, "reserve_attackers")
            and not self.battle_divisions(battle, "recovering_attackers")
        ):
            self.end_battle(battle)
        return True

    def add_division_to_battle(self, battle, division, side, status="reserve"):
        self.remove_division_from_battle_lists(battle, division)
        origin_tile = division.tile
        if side == "attacker" and division.path:
            try:
                target_index = division.path.index(battle.tile)
            except ValueError:
                target_index = -1
            division.post_battle_path = list(division.path[target_index + 1:]) if target_index >= 0 else []
        else:
            division.post_battle_path = []
        division.battle_id = battle.id
        division.battle_side = side
        division.battle_status = status
        division.path = []
        division.route_tiles = ([origin_tile, battle.tile] if origin_tile else [battle.tile]) + list(division.post_battle_path)
        division.route_mode = "attack" if side == "attacker" else "move"
        division.target_tile = division.post_battle_path[-1] if division.post_battle_path else battle.tile
        division.movement_progress = 0.0
        division.visual_movement_progress = 0.0
        attr = f"{status}_{side}s"
        getattr(battle, attr).append(division.id)
        self.update_battle_combat_width(battle)

    def start_or_join_battle(self, division, target_tile):
        if not target_tile or self.is_water_tile(target_tile):
            return False
        battle_key = self.battle_key_for_tile(target_tile)
        battle = self.battles.get(battle_key)
        if not battle:
            battle = Battle(
                id=battle_key,
                tile=target_tile,
                attacker=division.owner,
                defender=target_tile.owner,
                attacker_from_tile=division.tile,
                started_at=self.simulation_client.snapshot.current_time,
                last_tick=self.simulation_client.snapshot.current_time,
            )
            self.battles[battle_key] = battle
            defenders = self.enemy_divisions_on_tile(target_tile, division.owner)
            for defender in defenders:
                self.add_division_to_battle(battle, defender, "defender", "reserve")

        side = "attacker" if division.owner == battle.attacker else "defender"
        self.add_division_to_battle(battle, division, side, "reserve")
        self.rebalance_battle_side(battle, side)
        self.rebalance_battle_side(battle, "defender" if side == "attacker" else "attacker")
        self.invalidate_division_render_cache()
        return True

    def battle_attack_direction_count(self, battle):
        origins = set()
        for division in (
            self.battle_divisions(battle, "active_attackers")
            + self.battle_divisions(battle, "reserve_attackers")
            + self.battle_divisions(battle, "recovering_attackers")
        ):
            origin_tile = None
            if division.route_tiles:
                origin_tile = division.route_tiles[0]
            if not origin_tile or origin_tile == battle.tile:
                origin_tile = division.tile
            if origin_tile and origin_tile != battle.tile and self.hex_distance(origin_tile, battle.tile) == 1:
                origins.add((origin_tile.q, origin_tile.r))
        if not origins and battle.attacker_from_tile and self.hex_distance(battle.attacker_from_tile, battle.tile) == 1:
            origins.add((battle.attacker_from_tile.q, battle.attacker_from_tile.r))
        return max(1, len(origins))

    def update_battle_combat_width(self, battle):
        direction_count = self.battle_attack_direction_count(battle)
        battle.combat_width = COMBAT_WIDTH_DEFAULT + COMBAT_WIDTH_EXTRA_DIRECTION * max(0, direction_count - 1)
        return battle.combat_width

    def rebalance_battle_side(self, battle, side):
        self.update_battle_combat_width(battle)
        active_attr = f"active_{side}s"
        reserve_attr = f"reserve_{side}s"
        recovering_attr = f"recovering_{side}s"
        active = self.battle_divisions(battle, active_attr)
        reserve = self.battle_divisions(battle, reserve_attr)
        recovering = self.battle_divisions(battle, recovering_attr)

        ready_recovering = [
            division for division in recovering
            if division.organization >= division.max_organization * COMBAT_REJOIN_ORG_RATIO
        ]
        for division in ready_recovering:
            self.remove_division_from_battle_lists(battle, division)
            getattr(battle, reserve_attr).append(division.id)
            division.battle_status = "reserve"

        candidates = [
            division for division in active + reserve + ready_recovering
            if division.strength > 0 and division.organization > 0
        ]
        candidates.sort(key=lambda division: (-division.initiative, division.id))
        getattr(battle, active_attr)[:] = []
        getattr(battle, reserve_attr)[:] = []
        used_width = 0.0
        for division in candidates:
            remaining = max(0.0, battle.combat_width - used_width)
            width = max(1.0, division.front_width)
            width_ratio = min(1.0, remaining / width)
            if width_ratio >= 0.6:
                getattr(battle, active_attr).append(division.id)
                division.battle_status = "active"
                division.width_efficiency = width_ratio
                used_width += width * width_ratio
            else:
                getattr(battle, reserve_attr).append(division.id)
                division.battle_status = "reserve"
                division.width_efficiency = 1.0

    @staticmethod
    def combat_damage_value(attack, active_defense):
        bonus_damage = max(0.0, attack - active_defense)
        return attack * COMBAT_ATTACK_PRESSURE_MULT + bonus_damage * COMBAT_ATTACK_OVERMATCH_MULT

    def apply_combat_attack(self, attacker, target, target_is_defending=True):
        attacker_eff = max(0.2, attacker.width_efficiency)
        target_eff = max(0.2, target.width_efficiency)
        active_defense = (target.defense if target_is_defending else target.breakthrough) * target_eff
        soft_raw = self.combat_damage_value(attacker.soft_attack * attacker_eff, active_defense)
        front_raw = self.combat_damage_value(attacker.hard_front_attack * attacker_eff, active_defense)
        top_raw = self.combat_damage_value(attacker.hard_top_attack * attacker_eff, active_defense)

        front_penetrated = attacker.front_piercing >= target.front_armor
        top_penetrated = attacker.top_piercing >= target.top_armor
        if not front_penetrated:
            front_raw *= COMBAT_ARMOR_BLOCKED_DAMAGE_MULT
        if not top_penetrated:
            top_raw *= COMBAT_ARMOR_BLOCKED_DAMAGE_MULT

        target_infantry = self.clamp01(target.infantry_share)
        target_vehicle = self.clamp01(target.vehicle_share)
        total_share = max(0.01, target_infantry + target_vehicle)
        target_infantry /= total_share
        target_vehicle /= total_share

        damage = soft_raw * target_infantry + (front_raw + top_raw) * target_vehicle
        attacker_unpierced = (
            target.front_piercing < attacker.front_armor
            and target.top_piercing < attacker.top_armor
            and attacker.vehicle_share > 0.25
        )
        if attacker_unpierced:
            damage *= COMBAT_UNPIERCED_DAMAGE_BONUS

        org_damage = damage * COMBAT_ORG_DAMAGE_MULT
        strength_damage = damage * COMBAT_STRENGTH_DAMAGE_MULT
        target.organization = max(0.0, target.organization - org_damage)
        target.strength = max(0.0, target.strength - strength_damage)
        return org_damage, strength_damage

    def destroy_division(self, division):
        if division.owner and division in division.owner.divisions:
            division.owner.divisions.remove(division)
        if division in self.divisions:
            self.divisions.remove(division)
        self.selected_division_ids.discard(division.id)
        for battle in self.battles.values():
            self.remove_division_from_battle_lists(battle, division)

    def battle_side_active(self, battle, side):
        return self.battle_divisions(battle, f"active_{side}s")

    def battle_side_present(self, battle, side):
        return (
            self.battle_divisions(battle, f"active_{side}s")
            + self.battle_divisions(battle, f"reserve_{side}s")
            + self.battle_divisions(battle, f"recovering_{side}s")
        )

    def recover_division_organization(self, division, elapsed_hours, multiplier=1.0):
        if elapsed_hours <= 0 or division.organization >= division.max_organization:
            return 0.0
        supply = self.clamp01(getattr(division.tile, "supply_score", 0.75) if division.tile else 0.75)
        recovery = (
            division.organization_recovery
            * self.organization_recovery_factor(division)
            * supply
            * multiplier
            * elapsed_hours
            / 24.0
        )
        old_value = division.organization
        division.organization = min(division.max_organization, division.organization + recovery)
        return division.organization - old_value

    def update_battle_recovery_and_reinforce(self, battle, elapsed_hours):
        for side in ("attacker", "defender"):
            recovering_attr = f"recovering_{side}s"
            reserve_attr = f"reserve_{side}s"
            for division in self.battle_divisions(battle, reserve_attr):
                self.recover_division_organization(division, elapsed_hours, multiplier=0.25)
            for division in self.battle_divisions(battle, recovering_attr):
                self.recover_division_organization(division, elapsed_hours, multiplier=0.25)
                if division.organization >= division.max_organization * COMBAT_REJOIN_ORG_RATIO:
                    self.remove_division_from_battle_lists(battle, division)
                    getattr(battle, reserve_attr).append(division.id)
                    division.battle_status = "reserve"
            self.rebalance_battle_side(battle, side)

    def tick_battle(self, battle, elapsed_hours):
        if battle.id not in self.battles:
            return
        battle.last_attacker_org_damage = 0.0
        battle.last_attacker_strength_damage = 0.0
        battle.last_defender_org_damage = 0.0
        battle.last_defender_strength_damage = 0.0
        self.update_battle_recovery_and_reinforce(battle, elapsed_hours)
        attackers = self.battle_side_active(battle, "attacker")
        defenders = self.battle_side_active(battle, "defender")

        for attacker in list(attackers):
            defenders = self.battle_side_active(battle, "defender")
            if not defenders:
                break
            target = random.choice(defenders)
            org_damage, strength_damage = self.apply_combat_attack(attacker, target, target_is_defending=True)
            battle.last_attacker_org_damage += org_damage
            battle.last_attacker_strength_damage += strength_damage
        for defender in list(defenders):
            attackers = self.battle_side_active(battle, "attacker")
            if not attackers:
                break
            target = random.choice(attackers)
            org_damage, strength_damage = self.apply_combat_attack(defender, target, target_is_defending=False)
            battle.last_defender_org_damage += org_damage
            battle.last_defender_strength_damage += strength_damage

        for division in list(self.divisions):
            if division.battle_id != battle.id:
                continue
            if division.strength <= 0:
                self.destroy_division(division)
                continue
            if division.organization <= 0 and division.battle_status == "active":
                side = division.battle_side
                self.remove_division_from_battle_lists(battle, division)
                getattr(battle, f"recovering_{side}s").append(division.id)
                division.battle_status = "recovering"
                division.width_efficiency = 1.0

        self.rebalance_battle_side(battle, "attacker")
        self.rebalance_battle_side(battle, "defender")
        attackers = self.battle_side_active(battle, "attacker")
        defenders = self.battle_side_active(battle, "defender")
        if attackers and not defenders:
            battle.advance_progress = min(1.25, battle.advance_progress + COMBAT_ADVANCE_PER_HOUR * elapsed_hours)
        elif attackers and defenders:
            battle.advance_progress = max(0.0, battle.advance_progress - COMBAT_ADVANCE_DECAY_PER_HOUR * elapsed_hours)

        if battle.advance_progress >= 1.0:
            self.capture_battle_tile(battle)
        elif (
            defenders
            and not attackers
            and not self.battle_divisions(battle, "reserve_attackers")
            and not self.battle_divisions(battle, "recovering_attackers")
        ):
            self.end_battle(battle)
        elif not attackers and not self.battle_divisions(battle, "reserve_attackers") and not self.battle_divisions(battle, "recovering_attackers"):
            self.end_battle(battle)

    def capture_battle_tile(self, battle):
        new_owner = battle.attacker
        battle_tile = battle.tile
        attackers = (
            self.battle_divisions(battle, "active_attackers")
            + self.battle_divisions(battle, "reserve_attackers")
            + self.battle_divisions(battle, "recovering_attackers")
        )
        defenders = (
            self.battle_divisions(battle, "active_defenders")
            + self.battle_divisions(battle, "reserve_defenders")
            + self.battle_divisions(battle, "recovering_defenders")
        )
        retreat_orders = []
        for division in defenders:
            retreat_tile = self.find_retreat_tile(division, battle_tile)
            if retreat_tile:
                retreat_orders.append((division, retreat_tile))
            else:
                self.destroy_division(division)

        attacker_remaining_paths = {
            division.id: [
                tile for tile in getattr(division, "post_battle_path", [])
                if tile is not None and tile != battle_tile
            ]
            for division in attackers
        }
        self.transfer_tile_owner(battle_tile, new_owner)
        for division in attackers:
            division.tile = battle.tile
            division.x = battle.tile.center_x
            division.y = battle.tile.center_y
        self.end_battle(battle)
        for division in attackers:
            remaining_path = attacker_remaining_paths.get(division.id, [])
            division.post_battle_path = []
            division.path = remaining_path
            division.target_tile = remaining_path[-1] if remaining_path else None
            division.route_tiles = [battle_tile] + list(remaining_path) if remaining_path else []
            division.route_mode = (
                "attack"
                if remaining_path and remaining_path[-1].owner and remaining_path[-1].owner != division.owner
                else "move"
            )
            division.movement_progress = 0.0
            division.visual_movement_progress = 0.0
        for division, retreat_tile in retreat_orders:
            division.tile = battle_tile
            division.x = battle_tile.center_x
            division.y = battle_tile.center_y
            division.path = [retreat_tile]
            division.target_tile = retreat_tile
            division.route_tiles = [battle_tile, retreat_tile]
            division.route_mode = "retreat"
            division.movement_progress = 0.0
            division.visual_movement_progress = 0.0
            division.organization = 0.0
        retreating_ids = {division.id for division, _retreat_tile in retreat_orders}
        for division in list(self.divisions):
            if (
                division.tile == battle_tile
                and division.owner != new_owner
                and (division.id not in retreating_ids or division.route_mode != "retreat" or not division.path)
            ):
                self.destroy_division(division)
        self.invalidate_division_render_cache()

    def valid_retreat_tile(self, division, tile):
        if not tile or self.is_water_tile(tile):
            return False
        if tile.owner != division.owner:
            return False
        if self.enemy_divisions_on_tile(tile, division.owner):
            return False
        return True

    def find_retreat_tile(self, division, from_tile):
        candidates = [
            tile for tile in self.neighbor_tiles(from_tile)
            if self.valid_retreat_tile(division, tile)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda tile: getattr(tile, "supply_score", 0.5))

    def end_battle(self, battle):
        for attr in (
            "active_attackers", "reserve_attackers", "recovering_attackers",
            "active_defenders", "reserve_defenders", "recovering_defenders",
        ):
            for division in self.battle_divisions(battle, attr):
                division.battle_id = None
                division.battle_side = None
                division.battle_status = None
                division.target_tile = None
                division.route_mode = "move"
                division.width_efficiency = 1.0
                division.post_battle_path = []
            getattr(battle, attr)[:] = []
        self.battles.pop(battle.id, None)

    def set_tile_owner_only(self, tile, new_owner):
        old_owner = tile.owner
        if old_owner is new_owner:
            return False
        if old_owner and tile in old_owner.tiles:
            old_owner.tiles.remove(tile)
        tile.owner = new_owner
        if new_owner and tile not in new_owner.tiles:
            new_owner.tiles.append(tile)
        tile.color = self.get_tile_map_color(tile)
        self.ownership_dirty_tile_keys.add((tile.q, tile.r))
        self.map_overview_dirty_tile_keys.add((tile.q, tile.r))
        self.map_overview_dirty = True
        return True

    def enclosed_water_owner(self, water_tile):
        land_neighbors = [
            neighbor for neighbor in self.neighbor_tiles(water_tile)
            if not self.is_water_tile(neighbor)
        ]
        if land_neighbors:
            first_owner = land_neighbors[0].owner
            if all(neighbor.owner is first_owner for neighbor in land_neighbors):
                return first_owner
            return None

        owner_counts = {}
        for neighbor in self.neighbor_tiles(water_tile):
            if not self.is_water_tile(neighbor) or not neighbor.owner:
                continue
            owner_key = neighbor.owner.id if hasattr(neighbor.owner, "id") else id(neighbor.owner)
            owner_counts[owner_key] = (neighbor.owner, owner_counts.get(owner_key, (neighbor.owner, 0))[1] + 1)
        if not owner_counts:
            return None
        ranked = sorted(owner_counts.values(), key=lambda item: item[1], reverse=True)
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            return None
        return ranked[0][0]

    def propagate_water_ownership_from_land(self, land_tile):
        if self.is_water_tile(land_tile):
            return False
        queue = deque(
            neighbor for neighbor in self.neighbor_tiles(land_tile)
            if self.is_water_tile(neighbor)
        )
        changed = False
        seen = set()
        while queue:
            water_tile = queue.popleft()
            tile_key = (water_tile.q, water_tile.r)
            if tile_key in seen:
                continue
            seen.add(tile_key)
            new_owner = self.enclosed_water_owner(water_tile)
            if not new_owner or water_tile.owner == new_owner:
                continue
            if self.set_tile_owner_only(water_tile, new_owner):
                changed = True
                for neighbor in self.neighbor_tiles(water_tile):
                    if self.is_water_tile(neighbor):
                        queue.append(neighbor)
        return changed

    def refresh_after_ownership_change(self):
        if not self.ownership_dirty_tile_keys:
            return
        dirty_tiles = [
            self.hex_lookup[tile_key]
            for tile_key in self.ownership_dirty_tile_keys
            if tile_key in self.hex_lookup
        ]
        self.refresh_state_borders_for_tiles(dirty_tiles)
        if self.refresh_army_front_plans_for_ownership_change(dirty_tiles):
            self.invalidate_division_render_cache()
        self.ownership_dirty_tile_keys.clear()

    def process_ownership_refresh(self):
        self.refresh_after_ownership_change()

    def transfer_tile_owner(self, tile, new_owner):
        changed = self.set_tile_owner_only(tile, new_owner)
        if not changed:
            return False
        self.propagate_water_ownership_from_land(tile)
        self.refresh_after_ownership_change()
        return True

    def cancel_selected_division_orders_on_tile(self, tile):
        if not tile:
            return False
        changed = False
        for division in self.selected_divisions():
            if division.tile != tile:
                continue
            if division.route_mode == "retreat":
                continue
            if division.battle_id and division.battle_side == "attacker":
                changed = self.detach_division_from_battle(division) or changed
            if division.path or division.target_tile or division.route_tiles:
                division.path = []
                division.target_tile = None
                division.route_tiles = []
                division.route_mode = "move"
                division.movement_progress = 0.0
                division.visual_movement_progress = 0.0
                changed = True
        if changed:
            self.invalidate_division_render_cache()
        return changed

    def update_battles(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        remaining = elapsed_hours
        while remaining > 0:
            step = min(1.0, remaining)
            for battle in list(self.battles.values()):
                self.tick_battle(battle, step)
            remaining -= step
        self.invalidate_division_render_cache()

    def organization_recovery_factor(self, division):
        missing_ratio = 1.0 - self.clamp01(division.organization / max(1.0, division.max_organization))
        return 1.0 + 0.5 * missing_ratio

    def destroy_stranded_enemy_division(self, division):
        if not division.tile or not division.owner:
            return False
        if division.tile.owner == division.owner:
            return False
        if division.battle_id or division.route_mode == "retreat":
            return False
        self.destroy_division(division)
        return True

    def destroy_invalid_retreating_division(self, division):
        if division.route_mode != "retreat":
            return False
        if not division.path:
            if division.tile and division.tile.owner == division.owner:
                division.route_mode = "move"
                division.target_tile = None
                division.route_tiles = []
                division.movement_progress = 0.0
                division.visual_movement_progress = 0.0
                return False
            self.destroy_division(division)
            return True
        next_tile = division.path[0]
        if self.is_water_tile(next_tile) or next_tile.owner != division.owner:
            self.destroy_division(division)
            return True
        return False

    def update_divisions(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        for division in list(self.divisions):
            if self.destroy_invalid_retreating_division(division):
                continue
            if self.destroy_stranded_enemy_division(division):
                continue
            if division.battle_id:
                if division.battle_id not in self.battles:
                    division.battle_id = None
                    division.battle_side = None
                    division.battle_status = None
                    division.width_efficiency = 1.0
                else:
                    continue
            if division.path:
                if (
                    division.route_mode != "retreat"
                    and division.organization < division.max_organization * DIVISION_MIN_ORDER_ORG_RATIO
                ):
                    self.recover_division_organization(division, elapsed_hours)
                    continue
                next_tile = division.path[0]
                if next_tile.owner and next_tile.owner != division.owner and self.enemy_divisions_on_tile(next_tile, division.owner):
                    self.start_or_join_battle(division, next_tile)
                    continue
                movement_cost = max(1.0, float(getattr(next_tile, "movement_cost", 1.0) or 1.0))
                org_ratio = self.clamp01(division.organization / max(1.0, division.max_organization))
                speed_factor = max(DIVISION_LOW_ORG_SPEED_FLOOR, 0.35 + org_ratio * 0.65)
                retreat_multiplier = 2.0 if division.route_mode == "retreat" else 1.0
                progress = division.speed * retreat_multiplier * speed_factor * elapsed_hours / 24.0 / movement_cost
                division.movement_progress += progress
                division.organization = max(
                    0.0,
                    division.organization - DIVISION_ORG_MOVE_COST_PER_TILE * progress,
                )
                while division.path and division.movement_progress >= 1.0:
                    division.movement_progress -= 1.0
                    division.visual_movement_progress = self.clamp01(division.movement_progress)
                    division.tile = division.path.pop(0)
                    division.x = division.tile.center_x
                    division.y = division.tile.center_y
                    if division.route_mode == "retreat" and division.tile.owner != division.owner:
                        self.destroy_division(division)
                        break
                    if division.route_mode != "retreat" and division.tile.owner != division.owner and division.owner:
                        self.transfer_tile_owner(division.tile, division.owner)
                    division.route_tiles = [division.tile] + list(division.path)
                if division not in self.divisions:
                    continue
                if not division.path:
                    division.target_tile = None
                    division.route_tiles = []
                    division.route_mode = "move"
                    division.movement_progress = 0.0
                    division.visual_movement_progress = 0.0
            else:
                self.recover_division_organization(division, elapsed_hours)
            if division.tile:
                division.x = division.tile.center_x
                division.y = division.tile.center_y
        self.invalidate_division_render_cache()

    def update_division_visual_motion(self, delta_time):
        if delta_time <= 0:
            return
        smoothing = min(1.0, delta_time * 12.0)
        changed = False
        for division in self.divisions:
            target_progress = self.clamp01(division.movement_progress) if division.path else 0.0
            old_progress = division.visual_movement_progress
            division.visual_movement_progress += (target_progress - division.visual_movement_progress) * smoothing
            if abs(division.visual_movement_progress - target_progress) < 0.002:
                division.visual_movement_progress = target_progress
            if abs(old_progress - division.visual_movement_progress) > 0.0005:
                changed = True
        if changed:
            self.invalidate_division_render_cache()

    def is_coastal_land_tile(self, tile):
        if self.is_water_tile(tile):
            return False
        return any(self.is_water_tile(neighbor) for neighbor in self.neighbor_tiles(tile))

    @staticmethod
    def infrastructure_candidate_limit(tile_count, ratio, min_limit, max_limit):
        if tile_count <= 0:
            return 0
        scaled = math.ceil(tile_count * ratio)
        return min(tile_count, max(1, min(max_limit, max(min_limit, scaled))))

    @staticmethod
    def sorted_scored_candidates(scores, limit, min_score=0.04):
        candidates = [
            (tile, score)
            for tile, score in scores.items()
            if score >= min_score
        ]
        candidates.sort(key=lambda item: (-item[1], item[0].q, item[0].r))
        return candidates[:limit]

    def set_tile_building_coverage(self, tile, building_key, amount, max_coverage):
        if amount <= 0:
            return 0.0
        if building_key == "port" and not self.is_coastal_land_tile(tile):
            return 0.0

        coverage = getattr(tile, "building_coverage", None)
        if coverage is None:
            coverage = {}
            tile.building_coverage = coverage

        current = coverage.get(building_key, 0.0)
        new_value = min(max_coverage, current + amount)
        actual = new_value - current
        if actual <= 0:
            return 0.0

        coverage[building_key] = new_value
        if not hasattr(tile, "buildings") or tile.buildings is None:
            tile.buildings = []
        if building_key not in tile.buildings:
            tile.buildings.append(building_key)
        return actual

    def allocate_building_coverage(self, building_key, candidates, coverage_budget, decay=0.82):
        min_coverage, max_coverage = INFRASTRUCTURE_COVERAGE_LIMITS[building_key]
        candidates = [(tile, score) for tile, score in candidates if score > 0]
        if coverage_budget <= 0 or not candidates:
            return max(0.0, coverage_budget)

        remaining = coverage_budget
        weights = [max(0.01, score) * (decay ** index) for index, (_tile, score) in enumerate(candidates)]
        total_weight = sum(weights)
        if total_weight <= 0:
            return remaining

        for (tile, _score), weight in zip(candidates, weights):
            if remaining <= 0.005:
                break
            desired = coverage_budget * weight / total_weight
            if desired < min_coverage and remaining >= min_coverage:
                desired = min_coverage
            desired = min(desired, remaining)
            remaining -= self.set_tile_building_coverage(tile, building_key, desired, max_coverage)

        while remaining > 0.005:
            progressed = False
            for tile, _score in candidates:
                if remaining <= 0.005:
                    break
                amount = min(remaining, max_coverage)
                actual = self.set_tile_building_coverage(tile, building_key, amount, max_coverage)
                if actual > 0:
                    remaining -= actual
                    progressed = True
            if not progressed:
                break

        return max(0.0, remaining)

    def state_raw_resource_amounts(self, player):
        amounts = {}
        for tile in player.tiles:
            for resource in getattr(tile, "resources", []):
                if len(resource) < 3:
                    continue
                key, _depth, mass = resource
                amounts[key] = amounts.get(key, 0.0) + max(0.0, float(mass))
        return amounts

    @staticmethod
    def resource_group_total(amounts, resource_names):
        return sum(amounts.get(resource_key, 0.0) for resource_key in resource_names)

    @staticmethod
    def weighted_resource_score(tile, weights):
        score = 0.0
        for resource in getattr(tile, "resources", []):
            if len(resource) < 3:
                continue
            key, _depth, mass = resource
            weight = weights.get(key, 0.0)
            if weight <= 0:
                continue
            amount_score = min(1.0, math.log10(max(0.0, float(mass)) + 1) / math.log10(1_500_000 + 1))
            score += weight * amount_score
        return max(0.0, min(1.0, score))

    def nearby_coverage_score(self, player, tile, building_keys, radius):
        total = 0.0
        for other in self.owned_tiles_within_radius(player, tile, radius):
            distance = max(1, self.hex_distance(tile, other))
            coverage = getattr(other, "building_coverage", {}) or {}
            for building_key in building_keys:
                total += coverage.get(building_key, 0.0) / distance
        return self.clamp01(total)

    def nearby_resource_score(self, player, tile, weights, radius):
        total = 0.0
        for other in self.owned_tiles_within_radius(player, tile, radius):
            distance = max(1, self.hex_distance(tile, other))
            total += self.weighted_resource_score(other, weights) / distance
        return self.clamp01(total)

    def agriculture_score(self, tile):
        if self.is_water_tile(tile):
            return 0.0

        temperature = self.clamp01(1.0 - abs(tile.temperature - 0.55) / 0.55)
        moisture = self.clamp01(1.0 - abs(tile.moisture - 0.52) / 0.52)
        flatness = self.clamp01(1.0 - tile.ridge_value * 1.15 - tile.rock_cover * 0.75 - tile.snow_cover * 0.55)
        base = (
            tile.grass_cover * 0.32
            + temperature * 0.22
            + moisture * 0.22
            + flatness * 0.18
            + tile.tree_cover * 0.06
        )
        if tile.terrain_type in ["grassland", "plains", "savanna"]:
            base += 0.12
        elif tile.terrain_type in ["temperate_forest", "taiga"]:
            base += 0.04
        elif tile.terrain_type in ["desert", "mountains", "snowy_mountains", "tundra"]:
            base -= 0.18
        elif tile.terrain_type in ["swamp", "bog", "mangrove"]:
            base -= 0.10

        return self.clamp01(base)

    def city_score(self, player, tile, agriculture_scores):
        if self.is_water_tile(tile):
            return 0.0

        passability = self.clamp01(getattr(tile, "passability", 0.0))
        climate = self.clamp01(
            1.0
            - abs(tile.temperature - 0.52) * 1.15
            - abs(tile.moisture - 0.50) * 0.55
            - tile.snow_cover * 0.45
        )
        centrality = self.owned_neighbor_count(player, tile) / 6
        agriculture_bonus = min(
            0.35,
            sum(
                agriculture_scores.get(other, 0.0) * 0.10
                for other in self.owned_tiles_within_radius(player, tile, 2)
                if other != tile
            ),
        )
        water_access = 0.06 if any(self.is_water_tile(neighbor) for neighbor in self.neighbor_tiles(tile)) else 0.0
        capital_bonus = 0.28 if tile == player.capital_tile else 0.0

        return self.clamp01(
            passability * 0.24
            + climate * 0.22
            + centrality * 0.18
            + agriculture_bonus
            + water_access
            + capital_bonus
        )

    def farm_score(self, player, tile, agriculture_scores):
        if self.is_water_tile(tile):
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 2)
        centrality = self.owned_neighbor_count(player, tile) / 6
        return self.clamp01(agriculture_scores.get(tile, 0.0) * 0.74 + nearby_city * 0.18 + centrality * 0.08)

    def village_score(self, player, tile, agriculture_scores):
        if self.is_water_tile(tile):
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        centrality = self.owned_neighbor_count(player, tile) / 6
        no_city_here = 1.0 - (getattr(tile, "building_coverage", {}) or {}).get("city", 0.0)
        return self.clamp01(
            agriculture_scores.get(tile, 0.0) * 0.54
            + nearby_city * 0.22
            + centrality * 0.14
            + no_city_here * 0.10
        )

    def mine_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        resource_score = self.weighted_resource_score(tile, STARTING_SOLID_MINE_RESOURCE_WEIGHTS)
        if resource_score <= 0:
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(resource_score * 0.74 + nearby_city * 0.12 + passability * 0.14)

    def oil_gas_rig_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        resource_score = self.weighted_resource_score(tile, STARTING_OIL_GAS_RIG_RESOURCE_WEIGHTS)
        if resource_score <= 0:
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_refinery = self.nearby_coverage_score(player, tile, ["refinery"], 3)
        nearby_storage = self.nearby_coverage_score(player, tile, ["fuel_storage"], 2)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            resource_score * 0.70
            + nearby_city * 0.08
            + nearby_refinery * 0.10
            + nearby_storage * 0.06
            + passability * 0.06
        )

    def industry_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_mine = self.nearby_coverage_score(player, tile, ["mine"], 2)
        nearby_rig = self.nearby_coverage_score(player, tile, ["oil_gas_rig"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        nearby_resources = self.nearby_resource_score(player, tile, STARTING_SOLID_MINE_RESOURCE_WEIGHTS, 2)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_city * 0.38
            + nearby_resources * 0.18
            + nearby_mine * 0.16
            + nearby_rig * 0.10
            + nearby_port * 0.10
            + passability * 0.18
        )

    def port_score(self, player, tile):
        if not self.is_coastal_land_tile(tile):
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_industry = self.nearby_coverage_score(player, tile, ["industry"], 3)
        nearby_resources = self.nearby_resource_score(player, tile, STARTING_MINE_RESOURCE_WEIGHTS, 3)
        water_edges = sum(1 for neighbor in self.neighbor_tiles(tile) if self.is_water_tile(neighbor)) / 6
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            0.22
            + nearby_city * 0.30
            + nearby_industry * 0.22
            + nearby_resources * 0.12
            + water_edges * 0.08
            + passability * 0.06
        )

    def warehouse_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        coverage = getattr(tile, "building_coverage", {}) or {}
        existing_storage = coverage.get("city", 0.0) + coverage.get("village", 0.0) + coverage.get("warehouse", 0.0)
        nearby_settlement = self.nearby_coverage_score(player, tile, ["city", "village"], 2)
        nearby_industry = self.nearby_coverage_score(player, tile, ["industry"], 2)
        nearby_mine = self.nearby_coverage_score(player, tile, ["mine"], 2)
        nearby_rig = self.nearby_coverage_score(player, tile, ["oil_gas_rig"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_settlement * 0.28
            + nearby_industry * 0.22
            + nearby_mine * 0.16
            + nearby_rig * 0.10
            + nearby_port * 0.14
            + passability * 0.16
            + (1.0 - min(1.0, existing_storage)) * 0.04
        )

    def fuel_storage_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        nearby_settlement = self.nearby_coverage_score(player, tile, ["city", "village"], 2)
        nearby_industry = self.nearby_coverage_score(player, tile, ["industry", "refinery"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        nearby_fuel = self.nearby_resource_score(player, tile, REFINERY_RESOURCE_WEIGHTS, 3)
        nearby_rig = self.nearby_coverage_score(player, tile, ["oil_gas_rig"], 3)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_settlement * 0.24
            + nearby_industry * 0.24
            + nearby_fuel * 0.20
            + nearby_rig * 0.12
            + nearby_port * 0.14
            + passability * 0.18
        )

    def refinery_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        nearby_fuel = self.nearby_resource_score(player, tile, REFINERY_RESOURCE_WEIGHTS, 3)
        nearby_rig = self.nearby_coverage_score(player, tile, ["oil_gas_rig"], 3)
        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_industry = self.nearby_coverage_score(player, tile, ["industry"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_fuel * 0.34
            + nearby_rig * 0.16
            + nearby_city * 0.22
            + nearby_industry * 0.18
            + nearby_port * 0.12
            + passability * 0.14
        )

    def clear_starting_infrastructure(self, player):
        for tile in player.tiles:
            tile.buildings = []
            tile.building_coverage = {}
            tile.population = 0.0
            tile.resource_stockpiles = self.empty_tile_stockpiles()
            tile.industry_allocation = {}
            tile.production_cache = self.empty_production_cache()

    def generate_starting_infrastructure_for_all_states(self):
        for player in self.players:
            self.clear_starting_infrastructure(player)

        for player in self.players:
            self.generate_starting_infrastructure(player)

        self.recalculate_all_state_production_caches()
        self.recalculate_all_supply_scores()
        for player in self.players:
            self.recalculate_player_storage(player)
        self.tile_visual_revision += 1
        self.invalidate_tile_visual_cache()

    def generate_starting_infrastructure(self, player):
        land_tiles = [tile for tile in player.tiles if not self.is_water_tile(tile)]
        if not land_tiles:
            self.apply_starting_compensation(player, sum(STARTING_INFRASTRUCTURE_BUDGET.values()), {})
            return

        infrastructure_budget = self.scaled_starting_infrastructure_budget(
            getattr(player, "starting_scale", self.player_starting_scale(player, len(land_tiles)))
        )
        agriculture_scores = {tile: self.agriculture_score(tile) for tile in land_tiles}
        city_scores = {
            tile: self.city_score(player, tile, agriculture_scores)
            for tile in land_tiles
        }
        self.place_starting_cities(player, land_tiles, city_scores)
        village_unspent = self.place_starting_villages(
            player,
            land_tiles,
            agriculture_scores,
            infrastructure_budget["village"],
        )

        farm_unspent = self.place_starting_farms(
            player,
            land_tiles,
            agriculture_scores,
            infrastructure_budget["farms"],
        )
        mine_unspent = self.place_starting_mines(player, land_tiles, infrastructure_budget["mine"])
        oil_gas_unspent = self.place_starting_oil_gas_rigs(
            player,
            land_tiles,
            infrastructure_budget["oil_gas_rig"],
        )

        port_budget = infrastructure_budget["port"]
        port_scores = {tile: self.port_score(player, tile) for tile in land_tiles}
        has_port_candidates = any(score >= 0.08 for score in port_scores.values())
        industry_budget = infrastructure_budget["industry"]
        port_unspent = 0.0

        if has_port_candidates:
            extra_farm_budget = 0.0
        else:
            industry_budget += port_budget * 0.65
            extra_farm_budget = port_budget * 0.35
            port_unspent = 0.0

        if extra_farm_budget > 0:
            farm_unspent += self.place_starting_farms(player, land_tiles, agriculture_scores, extra_farm_budget)

        industry_unspent = self.place_starting_industry(player, land_tiles, industry_budget)
        if has_port_candidates:
            port_scores = {tile: self.port_score(player, tile) for tile in land_tiles}
            port_unspent = self.place_starting_ports(player, land_tiles, port_scores, port_budget)

        warehouse_unspent = self.place_starting_warehouses(
            player,
            land_tiles,
            infrastructure_budget["warehouse"] + village_unspent * 0.35,
        )
        fuel_storage_unspent = self.place_starting_fuel_storage(
            player,
            land_tiles,
            infrastructure_budget["fuel_storage"],
        )
        refinery_unspent = self.place_starting_refineries(
            player,
            land_tiles,
            infrastructure_budget["refinery"],
        )
        self.assign_starting_industry_allocations(player)

        self.apply_starting_compensation(
            player,
            farm_unspent
            + mine_unspent
            + oil_gas_unspent
            + industry_unspent
            + port_unspent
            + warehouse_unspent
            + fuel_storage_unspent
            + refinery_unspent,
            agriculture_scores,
        )
        self.distribute_starting_population(player)
        self.distribute_player_stockpiles_to_tiles(player)

    def place_starting_cities(self, player, land_tiles, city_scores):
        coverage_budget = (player.population or STARTING_POPULATION) / CITY_POPULATION_PER_FULL_COVERAGE
        scale = getattr(player, "starting_scale", self.player_starting_scale(player, len(land_tiles)))
        min_limit = max(1, min(4, math.ceil(scale * 3)))
        max_limit = max(min_limit, min(10, math.ceil(scale * 7)))
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.10 + scale * 0.06, min_limit, max_limit)
        candidates = self.sorted_scored_candidates(city_scores, limit, min_score=0.05)

        if player.capital_tile and player.capital_tile in land_tiles and all(tile != player.capital_tile for tile, _score in candidates):
            capital_score = max(0.35, city_scores.get(player.capital_tile, 0.0))
            candidates.append((player.capital_tile, capital_score))
            candidates.sort(key=lambda item: (-item[1], item[0].q, item[0].r))
            candidates = candidates[:limit]

        if not candidates and player.capital_tile:
            candidates = [(player.capital_tile, 1.0)]

        self.allocate_building_coverage("city", candidates, coverage_budget, decay=0.78)

        city_tiles = [
            tile for tile in player.tiles
            if (getattr(tile, "building_coverage", {}) or {}).get("city", 0.0) > 0
        ]
        total_city_coverage = sum(tile.building_coverage.get("city", 0.0) for tile in city_tiles)
        if total_city_coverage <= 0:
            return

        urban_population = (player.population or STARTING_POPULATION) * STARTING_URBAN_POPULATION_SHARE
        for tile in city_tiles:
            share = tile.building_coverage.get("city", 0.0) / total_city_coverage
            tile.population = urban_population * share

    def distribute_starting_population(self, player):
        total_population = player.population or STARTING_POPULATION
        assigned_population = sum(max(0.0, getattr(tile, "population", 0.0) or 0.0) for tile in player.tiles)
        remaining_population = max(0.0, total_population - assigned_population)
        if remaining_population <= 0:
            return

        weighted_tiles = []
        for tile in player.tiles:
            coverage = getattr(tile, "building_coverage", {}) or {}
            if coverage.get("city", 0.0) > 0:
                continue
            weight = 0.0
            for building_key, multiplier in RURAL_POPULATION_WEIGHTS.items():
                weight += coverage.get(building_key, 0.0) * multiplier
            if weight > 0:
                weighted_tiles.append((tile, weight))

        total_weight = sum(weight for _tile, weight in weighted_tiles)
        if total_weight <= 0:
            city_tiles = [
                tile for tile in player.tiles
                if (getattr(tile, "building_coverage", {}) or {}).get("city", 0.0) > 0
            ]
            total_weight = sum(tile.building_coverage.get("city", 0.0) for tile in city_tiles)
            weighted_tiles = [(tile, tile.building_coverage.get("city", 0.0)) for tile in city_tiles]

        if total_weight <= 0:
            return

        for tile, weight in weighted_tiles:
            tile.population = (getattr(tile, "population", 0.0) or 0.0) + remaining_population * weight / total_weight

    def place_starting_farms(self, player, land_tiles, agriculture_scores, budget):
        scores = {
            tile: self.farm_score(player, tile, agriculture_scores)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.34, 5, 18)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.12)
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["farms"]
        return self.allocate_building_coverage("farms", candidates, coverage_budget, decay=0.88)

    def place_starting_villages(self, player, land_tiles, agriculture_scores, budget):
        scores = {
            tile: self.village_score(player, tile, agriculture_scores)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.22, 3, 10)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.12)
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["village"]
        return self.allocate_building_coverage("village", candidates, coverage_budget, decay=0.86)

    def place_starting_mines(self, player, land_tiles, budget):
        scores = {
            tile: self.mine_score(player, tile)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.30, 3, 12)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.10)
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["mine"]
        return self.allocate_building_coverage("mine", candidates, coverage_budget, decay=0.84)

    def place_starting_oil_gas_rigs(self, player, land_tiles, budget):
        scores = {
            tile: self.oil_gas_rig_score(player, tile)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.18, 1, 7)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.10)
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["oil_gas_rig"]
        return self.allocate_building_coverage("oil_gas_rig", candidates, coverage_budget, decay=0.84)

    def place_starting_industry(self, player, land_tiles, budget):
        scores = {
            tile: self.industry_score(player, tile)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.26, 3, 10)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.10)
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["industry"]
        return self.allocate_building_coverage("industry", candidates, coverage_budget, decay=0.84)

    def place_starting_ports(self, player, land_tiles, port_scores, budget):
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.18, 1, 5)
        candidates = self.sorted_scored_candidates(port_scores, limit, min_score=0.08)
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["port"]
        return self.allocate_building_coverage("port", candidates, coverage_budget, decay=0.82)

    def place_starting_warehouses(self, player, land_tiles, budget):
        scores = {
            tile: self.warehouse_score(player, tile)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.16, 2, 7)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.10)
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["warehouse"]
        return self.allocate_building_coverage("warehouse", candidates, coverage_budget, decay=0.82)

    def place_starting_fuel_storage(self, player, land_tiles, budget):
        scores = {
            tile: self.fuel_storage_score(player, tile)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.16, 2, 8)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.08)
        if not candidates and player.capital_tile in land_tiles:
            candidates = [(player.capital_tile, 0.5)]
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["fuel_storage"]
        return self.allocate_building_coverage("fuel_storage", candidates, coverage_budget, decay=0.84)

    def place_starting_refineries(self, player, land_tiles, budget):
        scores = {
            tile: self.refinery_score(player, tile)
            for tile in land_tiles
        }
        limit = self.infrastructure_candidate_limit(len(land_tiles), 0.10, 1, 4)
        candidates = self.sorted_scored_candidates(scores, limit, min_score=0.10)
        if not candidates:
            fallback = [
                (tile, self.industry_score(player, tile))
                for tile in land_tiles
                if self.industry_score(player, tile) > 0
            ]
            fallback.sort(key=lambda item: (-item[1], item[0].q, item[0].r))
            candidates = fallback[:max(1, min(3, len(fallback)))]
        coverage_budget = budget / INFRASTRUCTURE_COVERAGE_COSTS["refinery"]
        return self.allocate_building_coverage("refinery", candidates, coverage_budget, decay=0.82)

    def add_stockpile_compensation(self, player, bucket_key, resource_key, amount):
        if amount <= 0:
            return
        self.add_to_stockpile(player, resource_key, amount)

    def apply_starting_compensation(self, player, missing_infrastructure_budget, agriculture_scores):
        raw_amounts = self.state_raw_resource_amounts(player)
        budget_bonus = max(0.0, missing_infrastructure_budget) * INFRASTRUCTURE_MISSING_BUDGET_VALUE
        compensation_resources = {}

        for group in STARTING_RESOURCE_COMPENSATION_GROUPS:
            total = self.resource_group_total(raw_amounts, group["resources"])
            shortage = self.clamp01(1.0 - total / group["target"])
            if shortage <= 0:
                continue

            budget_bonus += group["budget"] * shortage
            for bucket_key, resource_key, amount, unit_value in group["stock"]:
                stock_amount = amount * shortage
                self.add_stockpile_compensation(player, bucket_key, resource_key, stock_amount)
                compensation_resources[resource_key] = compensation_resources.get(resource_key, 0.0) + stock_amount
                budget_bonus += stock_amount * unit_value

        farm_coverage = sum((getattr(tile, "building_coverage", {}) or {}).get("farms", 0.0) for tile in player.tiles)
        best_agriculture = sum(sorted(agriculture_scores.values(), reverse=True)[:6])
        agriculture_shortage = max(
            self.clamp01(1.0 - farm_coverage / 1.05),
            self.clamp01(1.0 - best_agriculture / 2.4),
        )
        if agriculture_shortage > 0.15:
            budget_bonus += STARTING_AGRICULTURE_COMPENSATION["budget"] * agriculture_shortage
            for bucket_key, resource_key, amount, unit_value in STARTING_AGRICULTURE_COMPENSATION["stock"]:
                stock_amount = amount * agriculture_shortage
                self.add_stockpile_compensation(player, bucket_key, resource_key, stock_amount)
                compensation_resources[resource_key] = compensation_resources.get(resource_key, 0.0) + stock_amount
                budget_bonus += stock_amount * unit_value

        budget_bonus = min(INFRASTRUCTURE_COMPENSATION_BUDGET_CAP, budget_bonus)
        if budget_bonus > 0:
            player.budget += budget_bonus
        player.starting_compensation = {
            "budget": budget_bonus,
            "resources": compensation_resources,
        }

    def setup_players_and_states(self):
        total_players = max(1, self.bot_count + 1)
        self.start_territory_radius = self.calculate_start_territory_radius(total_players)
        self.players = []

        for index in range(total_players):
            player = StatePlayer(
                id=index,
                name="Player" if index == 0 else f"Bot {index}",
                color=STATE_COLORS[index % len(STATE_COLORS)],
                border_color=STATE_BORDER_COLORS[index % len(STATE_BORDER_COLORS)],
                is_human=index == 0,
            )
            self.players.append(player)

        self.human_player = self.players[0]
        start_tiles = self.find_state_start_tiles(total_players)
        for player, start_tile in zip(self.players, start_tiles):
            player.capital_tile = start_tile
            self.claim_start_territory(player, start_tile, self.start_territory_radius)

        for player in self.players:
            self.apply_starting_profile(player)

        self.generate_starting_infrastructure_for_all_states()

        for tile in self.hex_grid:
            tile.color = self.get_tile_map_color(tile)
        self.recalculate_all_state_resources()
        self.recalculate_all_supply_scores()
        for player in self.players:
            self.recalculate_player_storage(player)
            self.recalculate_resource_balance_breakdown(player)
        self.rebuild_state_borders()
        self.recalculate_all_monthly_balances()
        self.update_economy_month_history(self.simulation_client.snapshot.current_time)
        self.generate_starting_divisions_for_all_states()

        print(
            f"Created {len(self.players)} states, "
            f"start territory radius: {self.start_territory_radius}"
        )

    def generate_starting_divisions_for_all_states(self):
        self.divisions = []
        self.battles = {}
        self.next_division_id = 1
        self.next_army_id = 1
        self.next_battle_plan_id = 1
        self.selected_division_ids.clear()
        for player in self.players:
            player.divisions = []
            player.armies = []
            self.generate_starting_divisions(player)
        self.invalidate_division_render_cache()

    def generate_starting_divisions(self, player):
        land_tiles = [tile for tile in player.tiles if not self.is_water_tile(tile)]
        if not land_tiles:
            return
        capital = player.capital_tile

        def tile_score(tile):
            coverage = getattr(tile, "building_coverage", {}) or {}
            city = coverage.get("city", 0.0)
            village = coverage.get("village", 0.0)
            supply = getattr(tile, "supply_score", 0.65)
            distance_penalty = 0.0
            if capital:
                distance_penalty = (abs(tile.q - capital.q) + abs(tile.r - capital.r)) * 0.015
            return city * 1.6 + village * 0.8 + supply * 0.5 + self.owned_neighbor_count(player, tile) * 0.08 - distance_penalty

        candidates = sorted(land_tiles, key=lambda tile: (-tile_score(tile), tile.q, tile.r))
        if not candidates:
            return

        for index in range(STARTING_DIVISIONS_PER_STATE):
            tile = candidates[index % len(candidates)]
            division = self.create_division_from_template(player, tile, "basic_infantry")
            player.divisions.append(division)
            self.divisions.append(division)

    def calculate_start_territory_radius(self, total_players):
        radius = round(self.map_size / max(8, total_players * 2))
        return max(3, min(12, radius))

    def find_state_start_tiles(self, total_players):
        min_x = min(tile.center_x for tile in self.hex_grid)
        max_x = max(tile.center_x for tile in self.hex_grid)
        min_y = min(tile.center_y for tile in self.hex_grid)
        max_y = max(tile.center_y for tile in self.hex_grid)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        radius_x = (max_x - min_x) * 0.31
        radius_y = (max_y - min_y) * 0.31
        start_tiles = []

        for index in range(total_players):
            angle = math.tau * index / total_players - math.pi / 2
            target_x = center_x + math.cos(angle) * radius_x
            target_y = center_y + math.sin(angle) * radius_y
            start_tiles.append(self.find_nearest_start_tile(target_x, target_y, start_tiles, total_players))

        return start_tiles

    def find_nearest_start_tile(self, target_x, target_y, existing_starts, total_players):
        valid_tiles = [
            tile for tile in self.hex_grid
            if self.is_valid_state_start(tile, existing_starts, total_players)
        ]
        if valid_tiles:
            return min(
                valid_tiles,
                key=lambda tile: (tile.center_x - target_x) ** 2 + (tile.center_y - target_y) ** 2,
            )

        return min(
            self.hex_grid,
            key=lambda tile: (tile.center_x - target_x) ** 2 + (tile.center_y - target_y) ** 2,
        )

    def is_valid_state_start(self, tile, existing_starts, total_players=None):
        if tile.terrain_type in ["deep_ocean", "ocean", "shallow_water", "lake"]:
            return False
        if tile.owner is not None:
            return False
        crowd_factor = 1.0 if not total_players else max(0.45, min(1.0, 8 / total_players))
        min_distance = max(2, round((self.start_territory_radius * 2 + 1) * crowd_factor))
        return all(self.hex_distance(tile, other) >= min_distance for other in existing_starts)

    def claim_start_territory(self, player, start_tile, radius):
        world_radius = self.start_territory_world_radius(radius)
        for tile in self.hex_grid:
            distance = math.hypot(tile.center_x - start_tile.center_x, tile.center_y - start_tile.center_y)
            if distance <= world_radius:
                if tile.owner and tile in tile.owner.tiles:
                    tile.owner.tiles.remove(tile)
                tile.owner = player
                if tile not in player.tiles:
                    player.tiles.append(tile)
        start_tile.is_capital = True

    @staticmethod
    def start_territory_world_radius(radius):
        center_spacing = (HEX_WID + HEX_HGT * 0.75) / 2
        return (radius + 0.5) * center_spacing

    @staticmethod
    def hex_distance(first, second):
        return max(abs(first.q - second.q), abs(first.r - second.r), abs(first.s - second.s))

    def get_neighbor_coords_for_edge(self, tile, edge_index):
        even_row_offsets = [(0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, 0)]
        odd_row_offsets = [(1, 1), (0, 1), (-1, 0), (0, -1), (1, -1), (1, 0)]
        offsets = odd_row_offsets if tile.r % 2 else even_row_offsets
        dq, dr = offsets[edge_index]
        return tile.q + dq, tile.r + dr

    def rebuild_state_borders(self):
        self.state_border_segments = {}
        self.state_border_chunk_segments = {}
        self.state_border_chunk_lists = {}
        for tile in self.hex_grid:
            self.add_state_border_segments_for_tile(tile)
        for chunk_key in list(self.state_border_chunk_segments):
            self.rebuild_state_border_chunk_shape_list(chunk_key)

    def state_border_edge_key(self, tile, edge_index):
        return tile.q, tile.r, edge_index

    def state_border_chunk_key_for_tile(self, tile):
        return tile.q // STATE_BORDER_CHUNK_SIZE, tile.r // STATE_BORDER_CHUNK_SIZE

    def state_border_chunk_key_for_edge_key(self, edge_key):
        q, r, _edge_index = edge_key
        return q // STATE_BORDER_CHUNK_SIZE, r // STATE_BORDER_CHUNK_SIZE

    def store_state_border_segment(self, edge_key, segment):
        self.state_border_segments[edge_key] = segment
        chunk_key = self.state_border_chunk_key_for_edge_key(edge_key)
        self.state_border_chunk_segments.setdefault(chunk_key, {})[edge_key] = segment

    def remove_state_border_segment(self, edge_key):
        self.state_border_segments.pop(edge_key, None)
        chunk_key = self.state_border_chunk_key_for_edge_key(edge_key)
        chunk_segments = self.state_border_chunk_segments.get(chunk_key)
        if chunk_segments is not None:
            chunk_segments.pop(edge_key, None)
            if not chunk_segments:
                self.state_border_chunk_segments.pop(chunk_key, None)

    def add_state_border_segments_for_tile(self, tile):
        if not tile.owner:
            return
        color = tile.owner.border_color
        for edge_index in range(6):
            neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
            if neighbor and neighbor.owner == tile.owner:
                continue

            x1, y1 = tile.corners[edge_index]
            x2, y2 = tile.corners[(edge_index + 1) % 6]
            edge_key = self.state_border_edge_key(tile, edge_index)
            self.store_state_border_segment(edge_key, (x1, y1, x2, y2, color))

    def state_border_shape_list_from_segments(self, segments):
        shape_list = arcade.shape_list.ShapeElementList()
        for _edge_key, (x1, y1, x2, y2, color) in sorted(segments.items()):
            shape_list.append(
                arcade.shape_list.create_line(x1, y1, x2, y2, (0, 0, 0), 11)
            )
            shape_list.append(
                arcade.shape_list.create_line(x1, y1, x2, y2, color, 7)
            )
        return shape_list

    def rebuild_state_border_shape_list(self):
        self.state_border_list = self.state_border_shape_list_from_segments(self.state_border_segments)

    def rebuild_state_border_chunk_shape_list(self, chunk_key):
        segments = self.state_border_chunk_segments.get(chunk_key)
        if not segments:
            self.state_border_chunk_lists.pop(chunk_key, None)
            return
        self.state_border_chunk_lists[chunk_key] = self.state_border_shape_list_from_segments(segments)

    def draw_state_borders(self):
        if self.state_border_chunk_lists:
            for chunk_key in sorted(self.state_border_chunk_lists):
                self.state_border_chunk_lists[chunk_key].draw()
        else:
            self.state_border_list.draw()

    def refresh_state_borders_for_tiles(self, dirty_tiles):
        affected = {}
        for tile in dirty_tiles:
            affected[(tile.q, tile.r)] = tile
            for neighbor in self.neighbor_tiles(tile):
                affected[(neighbor.q, neighbor.r)] = neighbor

        dirty_chunks = set()
        for tile in affected.values():
            dirty_chunks.add(self.state_border_chunk_key_for_tile(tile))
            for edge_index in range(6):
                edge_key = self.state_border_edge_key(tile, edge_index)
                dirty_chunks.add(self.state_border_chunk_key_for_edge_key(edge_key))
                self.remove_state_border_segment(edge_key)

        for tile in affected.values():
            self.add_state_border_segments_for_tile(tile)
            for edge_index in range(6):
                edge_key = self.state_border_edge_key(tile, edge_index)
                if edge_key in self.state_border_segments:
                    dirty_chunks.add(self.state_border_chunk_key_for_edge_key(edge_key))

        for chunk_key in dirty_chunks:
            self.rebuild_state_border_chunk_shape_list(chunk_key)

    def update_map_bounds(self):
        min_x = min(tile.bounding_box[0] for tile in self.hex_grid)
        min_y = min(tile.bounding_box[1] for tile in self.hex_grid)
        max_x = max(tile.bounding_box[2] for tile in self.hex_grid)
        max_y = max(tile.bounding_box[3] for tile in self.hex_grid)
        self.map_bounds = (min_x, min_y, max_x, max_y)

    @staticmethod
    def clamp_color_value(value):
        return max(0, min(255, int(value)))

    @classmethod
    def blend_colors(cls, first, second, amount):
        amount = max(0.0, min(1.0, amount))
        return tuple(
            cls.clamp_color_value(first[index] * (1 - amount) + second[index] * amount)
            for index in range(3)
        )

    @classmethod
    def shade_color(cls, color, amount):
        if amount >= 0:
            return cls.blend_colors(color, (255, 255, 255), amount)
        return cls.blend_colors(color, (0, 0, 0), -amount)

    @classmethod
    def terrain_color(cls, tile):
        color = tile.get_color(include_owner=False)
        if cls.is_water_tile(tile):
            if tile.terrain_type == "deep_ocean":
                water = (22, 55, 126)
            elif tile.terrain_type == "ocean":
                water = (36, 92, 168)
            elif tile.terrain_type == "shallow_water":
                water = (65, 151, 205)
            else:
                water = (76, 165, 214)
            highlight = max(0.0, min(1.0, tile.moisture * 0.18 + tile.temperature * 0.08))
            return cls.shade_color(water, highlight)

        height_shade = (tile.elevation - 0.48) * 0.28 + tile.ridge_value * 0.08
        if tile.snow_cover > 0.18:
            color = cls.blend_colors(color, (240, 248, 255), min(0.35, tile.snow_cover * 0.5))
        return cls.shade_color(color, height_shade)

    @staticmethod
    def is_water_tile(tile):
        return tile.terrain_type in ["ocean", "deep_ocean", "shallow_water", "lake", "river"] or tile.water_cover > 0.55

    @classmethod
    def political_color(cls, tile):
        base = cls.blend_colors(cls.terrain_color(tile), (158, 166, 150), 0.55)
        if not tile.owner:
            return cls.blend_colors(base, (92, 104, 96), 0.2)

        owner_amount = 0.62 if tile.is_capital else 0.48
        return cls.blend_colors(base, tile.owner.color, owner_amount)

    @classmethod
    def height_color(cls, tile):
        if tile.elevation < WATER_LEVEL:
            depth = max(0.0, min(1.0, tile.elevation / WATER_LEVEL))
            return cls.blend_colors((20, 55, 130), (68, 155, 220), depth)

        value = max(0.0, min(1.0, (tile.elevation - WATER_LEVEL) / (1.0 - WATER_LEVEL)))
        if value < 0.34:
            color = cls.blend_colors((72, 158, 72), (180, 204, 112), value / 0.34)
        elif value < 0.68:
            color = cls.blend_colors((180, 204, 112), (132, 118, 96), (value - 0.34) / 0.34)
        else:
            color = cls.blend_colors((132, 118, 96), (238, 242, 238), (value - 0.68) / 0.32)
        return cls.shade_color(color, tile.ridge_value * 0.18)

    @classmethod
    def climate_color(cls, tile):
        cold = (64, 130, 220)
        mild = (86, 196, 118)
        hot = (230, 174, 76)
        if tile.temperature < 0.5:
            color = cls.blend_colors(cold, mild, tile.temperature / 0.5)
        else:
            color = cls.blend_colors(mild, hot, (tile.temperature - 0.5) / 0.5)

        moisture_color = (45, 105, 215) if tile.moisture > 0.5 else (220, 200, 115)
        color = cls.blend_colors(color, moisture_color, abs(tile.moisture - 0.5) * 0.55)
        if tile.water_cover > 0.5:
            color = cls.blend_colors(color, (50, 135, 220), 0.55)
        return color

    @staticmethod
    def resource_amount_for_group(tile, resource_names):
        total = 0.0
        resource_set = set(resource_names)
        for resource in tile.resources:
            if len(resource) >= 3 and resource[0] in resource_set:
                total += float(resource[2])
        return total

    @staticmethod
    def resource_amount_for_key(tile, resource_key):
        total = 0.0
        for resource in tile.resources:
            if len(resource) >= 3 and resource[0] == resource_key:
                total += float(resource[2])
        return total

    @staticmethod
    def tile_output_amount_for_key(tile, resource_key):
        cache = getattr(tile, "production_cache", None)
        if not cache:
            return 0.0
        return sum(
            stage_cache["outputs"].get(resource_key, 0.0)
            for stage_cache in cache.values()
        )

    def rebuild_selected_resource_signal_cache(self):
        if (
            self.active_top_panel_key not in ("resources", "construction")
            or not self.selected_resource_key
        ):
            self.invalidate_selected_resource_signal_cache()
            return

        cache_key = (
            self.visible_tiles_signature,
            self.active_top_panel_key,
            self.resource_panel_category,
            self.selected_resource_key,
            self.last_production_tick_count,
            self.tile_visual_revision,
        )
        if cache_key == self.selected_resource_signal_cache_key:
            return

        signal_cache = {}
        if self.resource_panel_category == "raw":
            scale = 500_000
            low_color = (214, 176, 82)
            high_color = (255, 245, 140)
            for tile in self.visible_tiles:
                amount = self.resource_amount_for_key(tile, self.selected_resource_key)
                if amount <= 0:
                    continue
                intensity = min(1.0, math.log10(amount + 1) / math.log10(scale + 1))
                signal_cache[(tile.q, tile.r)] = (
                    intensity,
                    self.blend_colors(low_color, high_color, intensity),
                )
        elif self.human_player:
            scale = max(
                1.0,
                self.production_amount_for_key(self.human_player, self.selected_resource_key, "outputs") * 0.18,
            )
            low_color = (82, 172, 214)
            high_color = (154, 238, 255)
            for tile in self.visible_tiles:
                if tile.owner != self.human_player:
                    continue
                amount = self.tile_output_amount_for_key(tile, self.selected_resource_key)
                if amount <= 0:
                    continue
                intensity = min(1.0, math.log10(amount + 1) / math.log10(scale + 1))
                signal_cache[(tile.q, tile.r)] = (
                    intensity,
                    self.blend_colors(low_color, high_color, intensity),
                )

        self.selected_resource_signal_cache_key = cache_key
        self.selected_resource_signal_cache = signal_cache

    def selected_resource_signal(self, tile):
        cached = self.selected_resource_signal_cache.get((tile.q, tile.r))
        if cached:
            return cached
        if not self.selected_resource_key:
            return 0.0, None
        if self.resource_panel_category == "raw":
            amount = self.resource_amount_for_key(tile, self.selected_resource_key)
            scale = 500_000
            low_color = (214, 176, 82)
            high_color = (255, 245, 140)
        else:
            if tile.owner != self.human_player:
                return 0.0, None
            amount = self.tile_output_amount_for_key(tile, self.selected_resource_key)
            scale = max(1.0, self.production_amount_for_key(self.human_player, self.selected_resource_key, "outputs") * 0.18)
            low_color = (82, 172, 214)
            high_color = (154, 238, 255)
        if amount <= 0:
            return 0.0, None

        intensity = min(1.0, math.log10(amount + 1) / math.log10(scale + 1))
        return intensity, self.blend_colors(low_color, high_color, intensity)

    def selected_resource_overlay_color(self, tile, base_color):
        if (
            self.active_top_panel_key not in ("resources", "construction")
            or not self.selected_resource_key
        ):
            return base_color

        intensity, glow = self.selected_resource_signal(tile)
        if not glow:
            return base_color
        return self.blend_colors(base_color, glow, 0.42 + intensity * 0.36)

    def construction_overlay_color(self, tile, base_color):
        if not self.construction_placement_mode or self.active_top_panel_key != "construction":
            return base_color
        building_key = self.selected_construction_building_key()
        if not building_key or not self.human_player or tile.owner != self.human_player:
            return self.blend_colors(base_color, (18, 22, 26), 0.62)
        cached = self.construction_placement_tile_cache.get((tile.q, tile.r))
        can_place = cached["can_place"] if cached is not None else self.can_place_construction(
            self.human_player,
            tile,
            building_key,
        )
        if can_place:
            planned_coverage = 0.0
            if cached is not None:
                planned_coverage = max(0.0, min(1.0, cached["coverage"] + cached["queued_delta"]))
            overlay = self.blend_colors((36, 154, 72), (180, 235, 86), planned_coverage)
            amount = 0.60 + planned_coverage * 0.18
        else:
            overlay = (176, 58, 58)
            amount = 0.66
        if tile == self.hovered_tile:
            overlay = self.blend_colors(overlay, (245, 255, 150), 0.22 if can_place else 0.08)
            amount = min(0.86, amount + 0.10)
        result = self.blend_colors(base_color, overlay, amount)
        intensity, glow = self.selected_resource_signal(tile)
        if glow:
            result = self.blend_colors(result, glow, 0.18 + intensity * 0.22)
        return result

    def draw_construction_placement_labels(self):
        if not self.construction_placement_mode or self.use_overview_lod():
            return
        if self.construction_placement_cache_key is None:
            self.rebuild_construction_placement_cache()
        self.construction_placement_label_shapes.draw()
        for text in self.construction_placement_label_texts:
            text.draw()

    def division_base_world_position(self, division):
        tile = division.tile
        if not tile:
            return division.x, division.y
        if division.path:
            next_tile = division.path[0]
            progress = self.clamp01(division.visual_movement_progress)
            return (
                tile.center_x + (next_tile.center_x - tile.center_x) * progress,
                tile.center_y + (next_tile.center_y - tile.center_y) * progress,
            )
        return tile.center_x, tile.center_y

    def division_display_world_position(self, division):
        cached = self.division_display_positions.get(division.id)
        if cached and not self.use_division_lod():
            return cached
        base_x, base_y = self.division_base_world_position(division)
        return base_x + DIVISION_TILE_SIDE_OFFSET_X, base_y + DIVISION_TILE_SIDE_OFFSET_Y

    def division_screen_position(self, division):
        x, y = self.division_display_world_position(division)
        return self.world_to_screen(x, y)

    def visible_divisions(self):
        visible = []
        for division in self.divisions:
            screen_x, screen_y = self.division_screen_position(division)
            margin = DIVISION_ICON_SIZE * 1.6
            if -margin <= screen_x <= self.window.width + margin and -margin <= screen_y <= self.window.height + margin:
                visible.append(division)
        return visible

    def division_render_signature(self):
        return (
            round(self.world_camera.zoom, 3),
            round(self.world_camera.position[0], 1),
            round(self.world_camera.position[1], 1),
            tuple(
                (
                    division.id,
                    division.owner.id if division.owner else None,
                    division.template_key,
                    division.tile.q if division.tile else None,
                    division.tile.r if division.tile else None,
                    round(division.x, 1),
                    round(division.y, 1),
                    round(division.movement_progress, 2),
                    round(division.visual_movement_progress, 2),
                    round(division.organization, 1),
                    round(division.strength, 1),
                    division.selected,
                )
                for division in self.divisions
            ),
        )

    def use_division_lod(self):
        return self.world_camera.zoom < DIVISION_LOD_ZOOM

    def append_division_template_icon(self, shapes, template_key, x, y, size, color):
        icon_key = self.division_template(template_key).get("icon", "infantry")
        if icon_key == "infantry":
            head = max(3, size * 0.10)
            shapes.append(arcade.shape_list.create_ellipse_filled(x, y + size * 0.08, head * 2, head * 2, color))
            shapes.append(arcade.shape_list.create_line(x, y - size * 0.02, x, y - size * 0.19, color, 3))
            shapes.append(arcade.shape_list.create_line(x - size * 0.14, y - size * 0.07, x + size * 0.14, y - size * 0.07, color, 3))
            shapes.append(arcade.shape_list.create_line(x, y - size * 0.19, x - size * 0.12, y - size * 0.30, color, 3))
            shapes.append(arcade.shape_list.create_line(x, y - size * 0.19, x + size * 0.12, y - size * 0.30, color, 3))
        elif icon_key == "tank":
            shapes.append(arcade.shape_list.create_rectangle_filled(x, y - size * 0.05, size * 0.56, size * 0.20, color))
            shapes.append(arcade.shape_list.create_rectangle_filled(x - size * 0.04, y + size * 0.08, size * 0.27, size * 0.16, color))
            shapes.append(arcade.shape_list.create_line(x + size * 0.08, y + size * 0.09, x + size * 0.31, y + size * 0.13, color, 4))
            shapes.append(arcade.shape_list.create_line(x - size * 0.24, y - size * 0.18, x + size * 0.24, y - size * 0.18, color, 3))
        elif icon_key == "motorized":
            wheel = max(2, size * 0.055)
            shapes.append(arcade.shape_list.create_rectangle_filled(x, y - size * 0.03, size * 0.54, size * 0.20, color))
            shapes.append(arcade.shape_list.create_rectangle_filled(x - size * 0.08, y + size * 0.08, size * 0.26, size * 0.16, color))
            shapes.append(arcade.shape_list.create_ellipse_filled(x - size * 0.18, y - size * 0.19, wheel * 2, wheel * 2, color))
            shapes.append(arcade.shape_list.create_ellipse_filled(x + size * 0.18, y - size * 0.19, wheel * 2, wheel * 2, color))
        elif icon_key == "anti_tank":
            shapes.append(arcade.shape_list.create_line(x - size * 0.28, y + size * 0.10, x + size * 0.24, y + size * 0.19, color, 4))
            shapes.append(arcade.shape_list.create_line(x, y + size * 0.03, x, y - size * 0.26, color, 3))
            shapes.append(arcade.shape_list.create_line(x, y - size * 0.08, x - size * 0.20, y - size * 0.30, color, 3))
            shapes.append(arcade.shape_list.create_line(x, y - size * 0.08, x + size * 0.20, y - size * 0.30, color, 3))
            shapes.append(arcade.shape_list.create_line(x - size * 0.10, y - size * 0.10, x + size * 0.10, y - size * 0.10, color, 3))
        elif icon_key == "anti_air":
            shapes.append(arcade.shape_list.create_line(x, y - size * 0.25, x, y + size * 0.15, color, 3))
            shapes.append(arcade.shape_list.create_line(x - size * 0.22, y - size * 0.26, x, y - size * 0.05, color, 3))
            shapes.append(arcade.shape_list.create_line(x + size * 0.22, y - size * 0.26, x, y - size * 0.05, color, 3))
            shapes.append(arcade.shape_list.create_line(x - size * 0.22, y + size * 0.06, x + size * 0.22, y + size * 0.17, color, 4))
            shapes.append(arcade.shape_list.create_line(x + size * 0.22, y + size * 0.17, x + size * 0.12, y + size * 0.28, color, 3))
        else:
            shapes.append(arcade.shape_list.create_line(x - size * 0.18, y - size * 0.18, x + size * 0.18, y + size * 0.18, color, 3))
            shapes.append(arcade.shape_list.create_line(x - size * 0.18, y + size * 0.18, x + size * 0.18, y - size * 0.18, color, 3))

    def visible_division_tile_stacks(self):
        stacks = {}
        for division in self.visible_divisions():
            if not division.tile:
                continue
            key = (
                division.owner.id if division.owner else None,
                division.template_key,
                division.tile.q,
                division.tile.r,
            )
            stacks.setdefault(key, []).append(division)
        result = []
        for divisions in stacks.values():
            divisions.sort(key=lambda item: item.id)
            result.append(divisions)
        result.sort(key=lambda stack: (stack[0].tile.r, stack[0].tile.q, stack[0].template_key, stack[0].owner.id))
        return result

    def update_division_display_positions(self):
        self.division_display_positions = {}
        stacks_by_tile = {}
        for stack in self.visible_division_tile_stacks():
            if not stack or not stack[0].tile:
                continue
            tile = stack[0].tile
            stacks_by_tile.setdefault((tile.q, tile.r), []).append(stack)

        slot_offsets = [
            (DIVISION_TILE_SIDE_OFFSET_X, DIVISION_TILE_SIDE_OFFSET_Y),
            (DIVISION_TILE_SIDE_OFFSET_X, DIVISION_TILE_SIDE_OFFSET_Y + 38),
            (DIVISION_TILE_SIDE_OFFSET_X, DIVISION_TILE_SIDE_OFFSET_Y - 38),
            (DIVISION_TILE_SIDE_OFFSET_X - 58, DIVISION_TILE_SIDE_OFFSET_Y),
            (DIVISION_TILE_SIDE_OFFSET_X - 58, DIVISION_TILE_SIDE_OFFSET_Y + 38),
            (DIVISION_TILE_SIDE_OFFSET_X - 58, DIVISION_TILE_SIDE_OFFSET_Y - 38),
            (DIVISION_TILE_SIDE_OFFSET_X + 58, DIVISION_TILE_SIDE_OFFSET_Y),
            (DIVISION_TILE_SIDE_OFFSET_X + 58, DIVISION_TILE_SIDE_OFFSET_Y + 38),
            (DIVISION_TILE_SIDE_OFFSET_X + 58, DIVISION_TILE_SIDE_OFFSET_Y - 38),
        ]
        for stacks in stacks_by_tile.values():
            stacks.sort(key=lambda stack: (
                stack[0].owner.id if stack[0].owner else -1,
                stack[0].template_key,
                stack[0].id,
            ))
            for index, stack in enumerate(stacks):
                tile = stack[0].tile
                if index < len(slot_offsets):
                    offset_x, offset_y = slot_offsets[index]
                else:
                    extra = index - len(slot_offsets)
                    angle = extra * 0.95
                    offset_x = DIVISION_TILE_SIDE_OFFSET_X + math.cos(angle) * 74
                    offset_y = DIVISION_TILE_SIDE_OFFSET_Y + math.sin(angle) * 52
                base_x, base_y = self.division_base_world_position(stack[0])
                position = (base_x + offset_x, base_y + offset_y)
                for division in stack:
                    self.division_display_positions[division.id] = position

    def rebuild_division_shapes(self):
        cache_key = self.division_render_signature()
        if cache_key == self.division_render_cache_key:
            return
        self.division_render_cache_key = cache_key
        self.division_shape_list = arcade.shape_list.ShapeElementList()
        for text in self.division_tile_stack_texts:
            text.text = ""
        if self.use_division_lod():
            return

        self.update_division_display_positions()
        size = DIVISION_ICON_SIZE / max(0.35, min(1.0, self.world_camera.zoom ** 0.25))
        text_index = 0
        for stack in self.visible_division_tile_stacks():
            division = stack[0]
            x, y = self.division_display_world_position(division)
            counter_width = max(50, size * 1.62)
            counter_height = max(32, size * 1.02)
            self.append_division_counter_shapes(self.division_shape_list, stack, x, y, counter_width, counter_height)
            if len(stack) > 1:
                if text_index >= len(self.division_tile_stack_texts):
                    self.division_tile_stack_texts.append(
                        arcade.Text("", 0, 0, arcade.color.WHITE, 13, anchor_x="center", anchor_y="center")
                    )
                label = self.division_tile_stack_texts[text_index]
                label.text = str(len(stack))
                label.x = x + counter_width / 2 - 11
                label.y = y + 5
                label.color = arcade.color.WHITE
                label.font_size = 13
                text_index += 1
        for index in range(text_index, len(self.division_tile_stack_texts)):
            self.division_tile_stack_texts[index].text = ""

    def division_group_signature(self):
        return (
            round(self.world_camera.zoom, 3),
            round(self.world_camera.position[0], 1),
            round(self.world_camera.position[1], 1),
            tuple(
                (
                    division.id,
                    division.owner.id if division.owner else None,
                    division.template_key,
                    division.tile.q if division.tile else None,
                    division.tile.r if division.tile else None,
                    round(division.x, 1),
                    round(division.y, 1),
                    round(division.movement_progress, 2),
                    round(division.visual_movement_progress, 2),
                    round(division.organization, 1),
                    round(division.max_organization, 1),
                    round(division.strength, 1),
                    round(division.max_strength, 1),
                    division.selected,
                )
                for division in self.divisions
            ),
        )

    def division_counter_template_key(self, divisions):
        counts = {}
        for division in divisions:
            counts[division.template_key] = counts.get(division.template_key, 0) + 1
        if not counts:
            return "basic_infantry", False
        sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return sorted_counts[0][0], len(sorted_counts) > 1

    def append_division_counter_shapes(self, shapes, divisions, center_x, center_y, width=54, height=34):
        if not divisions:
            return (center_x - width / 2, center_y - height / 2, width, height)
        selected = any(division.selected for division in divisions)
        owner = divisions[0].owner
        owner_color = tuple((owner.color if owner else (148, 158, 168))[:3])
        fill = self.blend_colors(owner_color, (32, 38, 44), 0.44)
        border = (255, 246, 132) if selected else (186, 204, 220)
        shapes.append(
            arcade.shape_list.create_rectangle_filled(center_x, center_y, width, height, (*fill, 240))
        )
        shapes.append(
            arcade.shape_list.create_rectangle_outline(center_x, center_y, width, height, border, 2)
        )
        template_key, mixed = self.division_counter_template_key(divisions)
        icon_size = min(34, height * 0.98)
        self.append_division_template_icon(
            shapes,
            template_key,
            center_x - width * 0.17,
            center_y + 3,
            icon_size,
            (18, 24, 31),
        )
        if mixed:
            shapes.append(
                arcade.shape_list.create_line(
                    center_x - width * 0.38,
                    center_y + height * 0.33,
                    center_x - width * 0.02,
                    center_y - height * 0.28,
                    (236, 222, 150),
                    2,
                )
            )
        max_org = sum(max(1.0, division.max_organization) for division in divisions)
        org_ratio = 0.0
        if max_org > 0:
            org_ratio = self.clamp01(sum(division.organization for division in divisions) / max_org)
        max_strength = sum(max(1.0, division.max_strength) for division in divisions)
        strength_ratio = 0.0
        if max_strength > 0:
            strength_ratio = self.clamp01(sum(division.strength for division in divisions) / max_strength)
        hp_x = center_x - width / 2 + 4
        hp_height = height - 6
        shapes.append(
            arcade.shape_list.create_rectangle_filled(hp_x, center_y, 5, hp_height, (30, 34, 40))
        )
        if strength_ratio > 0:
            shapes.append(
                arcade.shape_list.create_rectangle_filled(
                    hp_x,
                    center_y - hp_height * (1 - strength_ratio) / 2,
                    5,
                    hp_height * strength_ratio,
                    (118, 204, 238) if strength_ratio >= 0.45 else (236, 112, 88),
                )
            )
        bar_width = width - 8
        bar_y = center_y - height / 2 + 4
        shapes.append(
            arcade.shape_list.create_rectangle_filled(center_x, bar_y, bar_width, 4, (28, 34, 42))
        )
        if org_ratio > 0:
            shapes.append(
                arcade.shape_list.create_rectangle_filled(
                    center_x - bar_width * (1 - org_ratio) / 2,
                    bar_y,
                    bar_width * org_ratio,
                    4,
                    (110, 214, 126) if org_ratio >= 0.45 else (234, 186, 72),
                )
            )
        return (center_x - width / 2, center_y - height / 2, width, height)

    def division_lod_group_entries(self):
        divisions = [
            division for division in self.visible_divisions()
            if division.tile is not None
        ]
        if not divisions:
            return []

        zoom = self.world_camera.zoom
        if zoom <= 0.10:
            neighbor_radius = 4
        elif zoom <= 0.25:
            neighbor_radius = 2
        elif zoom <= 0.40:
            neighbor_radius = 1
        else:
            neighbor_radius = 0

        if neighbor_radius <= 0:
            grouped = {}
            for division in divisions:
                key = (
                    division.owner.id if division.owner else None,
                    division.tile.q,
                    division.tile.r,
                )
                grouped.setdefault(key, []).append(division)
            return list(grouped.values())

        remaining = sorted(
            divisions,
            key=lambda division: (
                division.owner.id if division.owner else -1,
                division.tile.r,
                division.tile.q,
                division.id,
            ),
        )
        groups = []
        assigned = set()
        for seed in remaining:
            if seed.id in assigned:
                continue
            group = []
            for division in remaining:
                if division.id in assigned:
                    continue
                if division.owner != seed.owner:
                    continue
                if self.hex_distance(seed.tile, division.tile) <= neighbor_radius:
                    group.append(division)
                    assigned.add(division.id)
            groups.append(group)
        return groups

    def offset_division_counter_positions(self, entries):
        offsets = [
            (0, 0),
            (10, -7),
            (-10, -7),
            (10, 7),
            (-10, 7),
            (0, -12),
            (0, 12),
        ]
        placed = []
        for entry in entries:
            close_count = sum(
                1 for other_x, other_y in placed
                if math.hypot(entry["center_x"] - other_x, entry["center_y"] - other_y) < 42
            )
            dx, dy = offsets[min(close_count, len(offsets) - 1)]
            entry["center_x"] += dx
            entry["center_y"] += dy
            placed.append((entry["center_x"], entry["center_y"]))
        return entries

    def rebuild_division_groups(self):
        cache_key = self.division_group_signature()
        if cache_key == self.division_groups_cache_key:
            return
        self.division_groups_cache_key = cache_key
        self.division_groups = []
        self.division_group_shape_list = arcade.shape_list.ShapeElementList()
        for text in self.division_group_texts:
            text.text = ""

        if not self.use_division_lod():
            return

        entries = []
        for divisions in self.division_lod_group_entries():
            if not divisions:
                continue
            screen_positions = [self.division_screen_position(division) for division in divisions]
            center_x = sum(position[0] for position in screen_positions) / len(screen_positions)
            center_y = sum(position[1] for position in screen_positions) / len(screen_positions)
            entries.append({
                "center_x": center_x,
                "center_y": center_y,
                "divisions": divisions,
            })

        entries.sort(key=lambda entry: (entry["center_y"], entry["center_x"]))
        entries = self.offset_division_counter_positions(entries)

        text_index = 0
        for entry in entries:
            divisions = entry["divisions"]
            center_x = entry["center_x"]
            center_y = entry["center_y"]
            width = 54
            height = 34
            rect = self.append_division_counter_shapes(self.division_group_shape_list, divisions, center_x, center_y, width, height)
            if text_index >= len(self.division_group_texts):
                self.division_group_texts.append(
                    arcade.Text("", 0, 0, arcade.color.WHITE, 13, anchor_x="center", anchor_y="center")
                )
            label = self.division_group_texts[text_index]
            label.text = str(len(divisions))
            label.x = center_x + width / 2 - 11
            label.y = center_y + 5
            label.color = arcade.color.WHITE
            label.font_size = 13
            text_index += 1
            self.division_groups.append({
                "rect": rect,
                "divisions": divisions,
            })
        for index in range(text_index, len(self.division_group_texts)):
            self.division_group_texts[index].text = ""

    def draw_divisions(self):
        if not self.use_division_lod():
            self.update_division_display_positions()
        self.rebuild_division_route_shapes()
        self.division_route_shape_list.draw()
        self.rebuild_division_shapes()
        if not self.use_division_lod():
            self.division_shape_list.draw()
            for text in self.division_tile_stack_texts:
                if text.text:
                    text.draw()

    def battle_by_id(self, battle_id):
        return self.battles.get(battle_id)

    def battle_side_divisions(self, battle, side):
        return {
            "active": self.battle_divisions(battle, f"active_{side}s"),
            "reserve": self.battle_divisions(battle, f"reserve_{side}s"),
            "recovering": self.battle_divisions(battle, f"recovering_{side}s"),
        }

    def battle_power_score(self, divisions):
        score = 0.0
        for division in divisions:
            org_ratio = self.clamp01(division.organization / max(1.0, division.max_organization))
            hp_ratio = self.clamp01(division.strength / max(1.0, division.max_strength))
            score += (division.soft_attack + division.defense + division.breakthrough) * 0.25 * (0.35 + org_ratio * 0.45 + hp_ratio * 0.20)
        return score

    def battle_player_win_ratio(self, battle):
        attacker_groups = self.battle_side_divisions(battle, "attacker")
        defender_groups = self.battle_side_divisions(battle, "defender")
        attackers = attacker_groups["active"] + attacker_groups["reserve"] + attacker_groups["recovering"]
        defenders = defender_groups["active"] + defender_groups["reserve"] + defender_groups["recovering"]
        attacker_power = self.battle_power_score(attackers)
        defender_power = self.battle_power_score(defenders)
        power_ratio = attacker_power / max(1.0, attacker_power + defender_power)
        if self.human_player == battle.attacker:
            return self.clamp01(battle.advance_progress * 0.55 + power_ratio * 0.45)
        if self.human_player == battle.defender:
            return self.clamp01((1.0 - battle.advance_progress) * 0.55 + (1.0 - power_ratio) * 0.45)
        return power_ratio

    def battle_indicator_screen_position(self, battle):
        target = battle.tile
        source = battle.attacker_from_tile
        if not source:
            attackers = self.battle_side_divisions(battle, "attacker")
            source_divisions = attackers["active"] + attackers["reserve"] + attackers["recovering"]
            source = source_divisions[0].tile if source_divisions else None
        if source and source != target:
            world_x = (source.center_x + target.center_x) / 2
            world_y = (source.center_y + target.center_y) / 2
        else:
            world_x = target.center_x
            world_y = target.center_y + HEX_SIZE * 0.45
        return self.world_to_screen(world_x, world_y)

    def draw_battle_indicators(self):
        self.battle_indicator_rects = []
        for battle in self.battles.values():
            screen_x, screen_y = self.battle_indicator_screen_position(battle)
            radius = 22
            self.battle_indicator_rects.append(((screen_x - radius, screen_y - radius, radius * 2, radius * 2), battle.id))
            ratio = self.battle_player_win_ratio(battle)
            fill = (72, 44, 38, 235) if self.human_player == battle.attacker else (38, 55, 76, 235)
            arcade.draw_circle_filled(screen_x, screen_y, radius, fill)
            arcade.draw_circle_outline(screen_x, screen_y, radius, (235, 215, 150), 2)
            target_x, target_y = self.world_to_screen(battle.tile.center_x, battle.tile.center_y)
            angle = math.atan2(target_y - screen_y, target_x - screen_x)
            arrow_len = 16
            tip_x = screen_x + math.cos(angle) * arrow_len
            tip_y = screen_y + math.sin(angle) * arrow_len
            arcade.draw_line(screen_x, screen_y, tip_x, tip_y, (230, 92, 82), 3)
            for offset in (2.55, -2.55):
                wing_x = tip_x + math.cos(angle + offset) * 7
                wing_y = tip_y + math.sin(angle + offset) * 7
                arcade.draw_line(tip_x, tip_y, wing_x, wing_y, (230, 92, 82), 3)
            if not self.selected_battle_id:
                self.draw_ui_text(f"{int(ratio * 100)}%", screen_x, screen_y - 5, arcade.color.WHITE, 10, anchor_x="center", anchor_y="center")

    def draw_battle_division_rows(self, title, divisions, x, y, width):
        self.draw_ui_text(title, x, y, (220, 230, 240), 13)
        y -= 22
        if not divisions:
            self.draw_ui_text("-", x, y, (130, 145, 160), 12)
            return y - 20
        for division in divisions[:8]:
            org = self.clamp01(division.organization / max(1.0, division.max_organization))
            hp = self.clamp01(division.strength / max(1.0, division.max_strength))
            self.draw_ui_text(self.division_display_name(division), x, y, arcade.color.WHITE, 11)
            self.draw_ui_text(f"орг {org * 100:.0f}%  хп {hp * 100:.0f}%", x + width - 8, y, (168, 214, 166), 11, anchor_x="right")
            y -= 18
        if len(divisions) > 8:
            self.draw_ui_text(f"Еще {len(divisions) - 8}", x, y, (150, 166, 184), 11)
            y -= 18
        return y - 8

    def battle_remaining_time_text(self, battle, attacker_power, defender_power):
        if battle.advance_progress >= 1.0:
            return "сейчас"
        total_power = max(1.0, attacker_power + defender_power)
        pressure = max(0.08, abs(attacker_power - defender_power) / total_power)
        hours = (1.0 - self.clamp01(battle.advance_progress)) / max(0.001, COMBAT_ADVANCE_PER_HOUR)
        if defender_power > 0:
            hours += (1.0 - pressure) * 36.0
        return self.format_build_duration(hours / PRODUCTION_MONTH_HOURS)

    def draw_battle_panel(self):
        battle = self.battle_by_id(self.selected_battle_id)
        if not battle:
            self.selected_battle_id = None
            self.battle_panel_rect = None
            self.battle_panel_close_rect = None
            return
        width = min(760, self.window.width - 80)
        height = min(560, self.window.height - 110)
        x = (self.window.width - width) / 2
        y = (self.window.height - height) / 2
        self.battle_panel_rect = (x, y, width, height)
        self.battle_panel_close_rect = (x + width - 36, y + height - 36, 24, 24)
        arcade.draw_lbwh_rectangle_filled(x, y, width, height, (16, 24, 30, 238))
        arcade.draw_lbwh_rectangle_outline(x, y, width, height, (112, 142, 174), 2)
        arcade.draw_lbwh_rectangle_filled(*self.battle_panel_close_rect, (44, 54, 66, 240))
        arcade.draw_lbwh_rectangle_outline(*self.battle_panel_close_rect, (120, 142, 164), 1)
        self.draw_ui_text("X", self.battle_panel_close_rect[0] + 12, self.battle_panel_close_rect[1] + 12, arcade.color.WHITE, 11, anchor_x="center", anchor_y="center")
        self.draw_ui_text("Сражение", x + 20, y + height - 32, arcade.color.WHITE, 19)

        ratio = self.battle_player_win_ratio(battle)
        bar_x = x + 20
        bar_y = y + height - 70
        bar_w = width - 40
        arcade.draw_lbwh_rectangle_filled(bar_x, bar_y, bar_w, 16, (48, 42, 42, 230))
        arcade.draw_lbwh_rectangle_filled(bar_x, bar_y, bar_w * ratio, 16, (72, 126, 76, 235))
        arcade.draw_lbwh_rectangle_outline(bar_x, bar_y, bar_w, 16, (128, 148, 168), 1)
        self.draw_ui_text(f"Ход сражения: {ratio * 100:.0f}%", bar_x + bar_w / 2, bar_y + 8, arcade.color.WHITE, 11, anchor_x="center", anchor_y="center")

        attacker_groups = self.battle_side_divisions(battle, "attacker")
        defender_groups = self.battle_side_divisions(battle, "defender")
        attacker_all = attacker_groups["active"] + attacker_groups["reserve"] + attacker_groups["recovering"]
        defender_all = defender_groups["active"] + defender_groups["reserve"] + defender_groups["recovering"]
        attacker_power = self.battle_power_score(attacker_all)
        defender_power = self.battle_power_score(defender_all)
        player_is_attacker = self.human_player == battle.attacker
        player_is_defender = self.human_player == battle.defender
        remaining_text = self.battle_remaining_time_text(battle, attacker_power, defender_power)
        direction_count = self.battle_attack_direction_count(battle)
        self.draw_ui_text(
            f"Соотношение сил: {attacker_power:.0f} / {defender_power:.0f}   ШФ: {battle.combat_width:.0f} ({direction_count})",
            x + 20,
            bar_y - 24,
            (210, 222, 232),
            12,
        )
        self.draw_ui_text(f"Осталось: {remaining_text}", x + width - 20, bar_y - 24, (210, 222, 232), 12, anchor_x="right")

        if player_is_attacker:
            our_org_loss = battle.last_defender_org_damage
            our_hp_loss = battle.last_defender_strength_damage
            enemy_org_loss = battle.last_attacker_org_damage
            enemy_hp_loss = battle.last_attacker_strength_damage
        else:
            our_org_loss = battle.last_attacker_org_damage
            our_hp_loss = battle.last_attacker_strength_damage
            enemy_org_loss = battle.last_defender_org_damage
            enemy_hp_loss = battle.last_defender_strength_damage

        losses_y = bar_y - 58
        self.draw_ui_text("Потери", x + width / 2, losses_y, arcade.color.WHITE, 15, anchor_x="center")
        self.draw_ui_text(f"Наши: орг {our_org_loss:.1f}, хп {our_hp_loss:.1f}", x + 20, losses_y - 24, (224, 190, 150), 12)
        self.draw_ui_text(f"Враг: орг {enemy_org_loss:.1f}, хп {enemy_hp_loss:.1f}", x + width - 20, losses_y - 24, (224, 190, 150), 12, anchor_x="right")

        left_x = x + 20
        right_x = x + width / 2 + 18
        col_w = width / 2 - 38
        content_y = losses_y - 58
        left_is_player = player_is_attacker or player_is_defender
        self.draw_ui_text("Наши" if left_is_player else "Атакующие", left_x, content_y, arcade.color.WHITE, 16)
        self.draw_ui_text("Враг" if left_is_player else "Защитники", right_x, content_y, arcade.color.WHITE, 16)
        left_groups = attacker_groups if player_is_attacker or not player_is_defender else defender_groups
        right_groups = defender_groups if player_is_attacker or not player_is_defender else attacker_groups
        y_left = content_y - 28
        y_left = self.draw_battle_division_rows("В бою", left_groups["active"], left_x, y_left, col_w)
        y_left = self.draw_battle_division_rows("В резерве", left_groups["reserve"], left_x, y_left, col_w)
        self.draw_battle_division_rows("Восстановление", left_groups["recovering"], left_x, y_left, col_w)
        y_right = content_y - 28
        y_right = self.draw_battle_division_rows("В бою", right_groups["active"], right_x, y_right, col_w)
        y_right = self.draw_battle_division_rows("В резерве", right_groups["reserve"], right_x, y_right, col_w)
        self.draw_battle_division_rows("Восстановление", right_groups["recovering"], right_x, y_right, col_w)

    def route_point_for_tile(self, tile):
        return tile.center_x, tile.center_y

    def division_route_signature(self):
        return (
            self.use_overview_lod(),
            tuple(
                (
                    division.id,
                    division.tile.q if division.tile else None,
                    division.tile.r if division.tile else None,
                    round(division.x, 1),
                    round(division.y, 1),
                    division.route_mode,
                    round(division.movement_progress, 2),
                    round(division.visual_movement_progress, 2),
                    tuple((tile.q, tile.r) for tile in division.path),
                    tuple((tile.q, tile.r) for tile in division.route_tiles),
                    tuple((tile.q, tile.r) for tile in division.post_battle_path),
                )
                for division in self.selected_divisions()
                if division.path or division.route_tiles
            ),
        )

    def division_route_tiles_for_draw(self, division):
        if division.route_tiles:
            return [tile for tile in division.route_tiles if tile is not None]
        if division.path:
            return [division.tile] + list(division.path) if division.tile else list(division.path)
        return []

    def division_route_segment_mode(self, division, target_tile):
        if division.route_mode == "retreat":
            return "retreat"
        if target_tile and target_tile.owner and target_tile.owner != division.owner:
            return "attack"
        return "move"

    def rebuild_division_route_shapes(self):
        cache_key = self.division_route_signature()
        if cache_key == self.division_route_cache_key:
            return
        self.division_route_cache_key = cache_key
        self.division_route_shape_list = arcade.shape_list.ShapeElementList()
        if self.use_overview_lod():
            return
        for division in self.selected_divisions():
            route_tiles = self.division_route_tiles_for_draw(division)
            if len(route_tiles) < 2:
                continue
            points = [self.division_display_world_position(division)]
            points.extend(self.route_point_for_tile(tile) for tile in route_tiles[1:])
            if len(points) < 2:
                continue
            for index in range(len(points) - 1):
                x1, y1 = points[index]
                x2, y2 = points[index + 1]
                segment_mode = self.division_route_segment_mode(division, route_tiles[min(index + 1, len(route_tiles) - 1)])
                base_color, _progress_color = DIVISION_ROUTE_COLORS.get(segment_mode, DIVISION_ROUTE_COLORS["move"])
                self.division_route_shape_list.append(
                    arcade.shape_list.create_line(x1, y1, x2, y2, (*base_color, 210), 5)
                )
            x1, y1 = points[0]
            x2, y2 = points[1]
            progress = self.clamp01(division.movement_progress)
            first_segment_mode = self.division_route_segment_mode(division, route_tiles[min(1, len(route_tiles) - 1)])
            _base_color, progress_color = DIVISION_ROUTE_COLORS.get(first_segment_mode, DIVISION_ROUTE_COLORS["move"])
            self.division_route_shape_list.append(
                arcade.shape_list.create_line(
                    x1,
                    y1,
                    x1 + (x2 - x1) * progress,
                    y1 + (y2 - y1) * progress,
                    (*progress_color, 235),
                    6,
                )
            )
            arrow_x, arrow_y = points[-1]
            prev_x, prev_y = points[-2]
            last_segment_mode = self.division_route_segment_mode(division, route_tiles[-1])
            _base_color, arrow_color = DIVISION_ROUTE_COLORS.get(last_segment_mode, DIVISION_ROUTE_COLORS["move"])
            angle = math.atan2(arrow_y - prev_y, arrow_x - prev_x)
            wing = 16
            for offset in (2.55, -2.55):
                wx = arrow_x + math.cos(angle + offset) * wing
                wy = arrow_y + math.sin(angle + offset) * wing
                self.division_route_shape_list.append(
                    arcade.shape_list.create_line(arrow_x, arrow_y, wx, wy, (*arrow_color, 235), 5)
                )

    def draw_division_groups(self):
        if not self.use_division_lod():
            return
        self.rebuild_division_groups()
        self.division_group_shape_list.draw()
        for text in self.division_group_texts:
            if text.text:
                text.draw()

    def draw_division_selection_box(self):
        if not self.division_selection_drag_started:
            return
        x1, y1 = self.division_selection_start
        x2, y2 = self.division_selection_current
        left = min(x1, x2)
        bottom = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        arcade.draw_lbwh_rectangle_filled(left, bottom, width, height, (90, 130, 190, 42))
        arcade.draw_lbwh_rectangle_outline(left, bottom, width, height, (160, 205, 255, 210), 1)

    def construction_hover_tooltip_data(self):
        if (
            not self.construction_placement_mode
            or self.active_top_panel_key != "construction"
            or not self.hovered_tile
            or not self.human_player
        ):
            return None

        tile = self.hovered_tile
        building_key = self.selected_construction_building_key()
        if not building_key:
            return None
        cache_key = (
            tile.q,
            tile.r,
            building_key,
            self.construction_queue_signature(self.human_player),
            round(getattr(self.human_player, "budget", 0.0), -2),
        )
        if cache_key == self.construction_hover_tooltip_cache_key:
            return self.construction_hover_tooltip_cache_data

        building_name = BUILDING_DISPLAY_NAMES.get(building_key, building_key)
        reason = self.construction_tile_block_reason(self.human_player, tile, building_key)
        if reason:
            data = {
                "tile": tile,
                "title": f"{building_name} {tile.q}:{tile.r}",
                "lines": [reason],
                "level": "blocked",
            }
            self.construction_hover_tooltip_cache_key = cache_key
            self.construction_hover_tooltip_cache_data = data
            return data

        current_coverage = self.queued_target_coverage(self.human_player, tile, building_key)
        cost = self.construction_cost(self.human_player, tile, building_key, current_coverage)
        if not cost:
            data = {
                "tile": tile,
                "title": f"{building_name} {tile.q}:{tile.r}",
                "lines": ["Уже максимум"],
                "level": "blocked",
            }
            self.construction_hover_tooltip_cache_key = cache_key
            self.construction_hover_tooltip_cache_data = data
            return data

        speed = self.build_power(self.human_player)
        work_required = max(0.0, cost.get("work_required", 0.0))
        build_months = work_required / speed if speed > 0 else None
        resource_costs = {
            key: amount
            for key, amount in cost.get("resource_costs", {}).items()
            if amount > 0
        }
        monthly_costs = {}
        if build_months and build_months > 0:
            monthly_costs = {
                key: amount / build_months
                for key, amount in resource_costs.items()
                if amount > 0
            }

        lines = [
            f"{cost.get('from_coverage', 0.0):.0%} -> {cost.get('target_coverage', 0.0):.0%}",
            f"Время: {self.format_build_duration(build_months)}",
            f"Деньги: {self.format_money(cost.get('money_cost', 0.0))}",
        ]
        if building_key in ("mine", "oil_gas_rig"):
            allowed_resources = (
                STARTING_OIL_GAS_RIG_RESOURCE_WEIGHTS
                if building_key == "oil_gas_rig"
                else STARTING_SOLID_MINE_RESOURCE_WEIGHTS
            )
            ground_resources = [
                (key, max(0.0, float(mass)))
                for key, _depth, mass in getattr(tile, "resources", [])
                if key in allowed_resources and max(0.0, float(mass)) > 0
            ]
            ground_resources.sort(key=lambda item: item[1], reverse=True)
            if ground_resources:
                lines.append("В земле:")
                for key, amount in ground_resources[:5]:
                    lines.append(f"{self.resource_display_name(key)}: {self.format_resource_amount(amount)}")
                if len(ground_resources) > 5:
                    lines.append(f"Еще {len(ground_resources) - 5}")
            else:
                lines.append("В земле: нет сырья")
        if resource_costs:
            lines.append("Ресурсы: всего | /мес")
            for key, amount in resource_costs.items():
                monthly = monthly_costs.get(key)
                monthly_text = self.format_resource_amount(monthly) if monthly is not None else "--"
                lines.append(
                    f"{self.resource_display_name(key)}: {self.format_resource_amount(amount)} | {monthly_text}"
                )

        data = {
            "tile": tile,
            "title": f"{building_name} {tile.q}:{tile.r}",
            "lines": lines,
            "level": "ok",
        }
        self.construction_hover_tooltip_cache_key = cache_key
        self.construction_hover_tooltip_cache_data = data
        return data

    def world_to_screen(self, world_x, world_y):
        camera_x, camera_y = self.world_camera.position
        zoom = self.world_camera.zoom
        screen_x = (world_x - camera_x) * zoom + self.window.width / 2
        screen_y = (world_y - camera_y) * zoom + self.window.height / 2
        return screen_x, screen_y

    def draw_construction_hover_tooltip(self, data=None):
        if data is None:
            data = self.construction_hover_tooltip_data()
        if not data:
            return

        tile = data["tile"]
        lines = data["lines"]
        screen_x, screen_y = self.world_to_screen(tile.center_x, tile.center_y)
        tooltip_width = 292
        line_height = 16
        tooltip_height = 42 + min(len(lines), 16) * line_height
        max_x = max(12, self.window.width - tooltip_width - 12)
        max_y = max(12, self.window.height - tooltip_height - TOP_UI_HEIGHT - 8)
        tooltip_x = max(12, min(screen_x + 24, max_x))
        tooltip_y = max(12, min(screen_y + 22, max_y))
        fill = (18, 27, 22, 244) if data["level"] == "ok" else (36, 24, 24, 244)
        border = (184, 226, 126) if data["level"] == "ok" else (218, 118, 108)
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, fill)
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, border, 1)

        line_y = tooltip_y + tooltip_height - 20
        self.draw_tooltip_text(data["title"], tooltip_x + 12, line_y, arcade.color.WHITE, 12)
        line_y -= 18
        for line in lines[:16]:
            color = (232, 252, 144)
            if data["level"] == "blocked":
                color = (244, 176, 164)
            elif line.startswith("Ресурсы:") or line == "В земле:":
                color = (160, 190, 210)
            self.draw_tooltip_text(line, tooltip_x + 16, line_y, color, 11)
            line_y -= line_height

    def resource_color(self, tile):
        group_key, _label, resources, highlight_color, scale = RESOURCE_MAP_GROUPS[self.resource_group_index]
        amount = self.resource_amount_for_group(tile, resources)
        if amount <= 0:
            return self.blend_colors(self.terrain_color(tile), (20, 22, 26), 0.72)

        intensity = min(1.0, math.log10(amount + 1) / math.log10(scale + 1))
        base = self.blend_colors((38, 42, 48), highlight_color, 0.28 + intensity * 0.62)
        if tile == self.selected_tile or tile == self.hovered_tile:
            return self.blend_colors(base, (255, 255, 190), 0.18)
        return base

    def supply_color(self, tile):
        if not tile.owner or self.is_water_tile(tile):
            return self.blend_colors(self.terrain_color(tile), (12, 16, 22), 0.62)
        supply = getattr(tile, "supply_score", None)
        if supply is None:
            self.recalculate_player_supply(tile.owner)
            supply = getattr(tile, "supply_score", 0.0)
        supply = self.clamp01(supply)
        if supply < 0.25:
            target = (154, 48, 44)
        elif supply < 0.50:
            target = (190, 142, 54)
        elif supply < 0.75:
            target = (146, 174, 74)
        else:
            target = (62, 156, 88)
        base = self.blend_colors((28, 34, 42), target, 0.36 + supply * 0.45)
        if tile == self.selected_tile or tile == self.hovered_tile:
            return self.blend_colors(base, (255, 255, 190), 0.18)
        return base

    def get_tile_map_color(self, tile):
        if self.construction_placement_mode and self.active_top_panel_key == "construction":
            return self.construction_overlay_color(tile, self.terrain_color(tile))
        if self.map_layer == "political":
            return self.selected_resource_overlay_color(tile, self.political_color(tile))
        if self.map_layer == "height":
            return self.selected_resource_overlay_color(tile, self.height_color(tile))
        if self.map_layer == "climate":
            return self.selected_resource_overlay_color(tile, self.climate_color(tile))
        if self.map_layer == "resources":
            return self.selected_resource_overlay_color(tile, self.resource_color(tile))
        if self.map_layer == "supply":
            return self.selected_resource_overlay_color(tile, self.supply_color(tile))
        return self.selected_resource_overlay_color(tile, self.terrain_color(tile))

    def create_map_overview(self):
        min_x, min_y, max_x, max_y = self.map_bounds
        world_width = max_x - min_x
        world_height = max_y - min_y
        scale = min(
            OVERVIEW_TEXTURE_MAX_SIZE / world_width,
            OVERVIEW_TEXTURE_MAX_SIZE / world_height,
            1.0,
        )
        texture_width = max(1, int(world_width * scale))
        texture_height = max(1, int(world_height * scale))
        image = Image.new('RGBA', (texture_width, texture_height), (13, 18, 24, 255))
        draw = ImageDraw.Draw(image)

        for tile in self.hex_grid:
            self.draw_tile_on_map_overview(draw, tile, min_x, max_y, scale)

        self.map_overview_image = image
        self.map_overview_params = {
            "min_x": min_x,
            "max_y": max_y,
            "scale": scale,
            "world_width": world_width,
            "world_height": world_height,
            "center_x": min_x + world_width / 2,
            "center_y": min_y + world_height / 2,
        }
        self.map_overview_signature = self.current_map_overview_signature()
        self.update_map_overview_sprite_from_image()
        self.map_overview_dirty = False
        self.map_overview_dirty_tile_keys.clear()

    def current_map_overview_signature(self):
        return (
            self.world_seed,
            self.grid_width,
            self.grid_height,
            self.map_layer,
            self.resource_group_index,
            self.selected_resource_key or "none",
            self.construction_placement_mode,
            self.selected_construction_building_key() or "none",
        )

    def draw_tile_on_map_overview(self, draw, tile, min_x, max_y, scale):
        points = [
            (
                int((corner_x - min_x) * scale),
                int((max_y - corner_y) * scale),
            )
            for corner_x, corner_y in tile.corners
        ]
        draw.polygon(points, fill=(*self.get_tile_map_color(tile), 255))

    def update_map_overview_sprite_from_image(self):
        if self.map_overview_image is None or not self.map_overview_params:
            return
        self.map_overview_revision += 1
        texture = arcade.Texture(
            name=(
                f"map_overview_{self.world_seed}_{self.grid_width}x{self.grid_height}_"
                f"{self.map_layer}_{self.resource_group_index}_{self.selected_resource_key or 'none'}_"
                f"build_{self.construction_placement_mode}_{self.selected_construction_building_key() or 'none'}_"
                f"rev_{self.map_overview_revision}"
            ),
            image=self.map_overview_image,
        )
        self.map_overview_sprite = arcade.Sprite(texture)
        self.map_overview_sprite.center_x = self.map_overview_params["center_x"]
        self.map_overview_sprite.center_y = self.map_overview_params["center_y"]
        self.map_overview_sprite.width = self.map_overview_params["world_width"]
        self.map_overview_sprite.height = self.map_overview_params["world_height"]
        self.map_overview_sprite_list.clear()
        self.map_overview_sprite_list.append(self.map_overview_sprite)

    def refresh_dirty_map_overview_tiles(self):
        if not self.map_overview_dirty:
            return
        if (
            not self.map_overview_dirty_tile_keys
            or self.map_overview_image is None
            or not self.map_overview_params
            or self.map_overview_signature != self.current_map_overview_signature()
        ):
            self.create_map_overview()
            return

        current_time = time.time()
        if current_time - self.map_overview_last_partial_update < 0.08:
            return
        self.map_overview_last_partial_update = current_time

        draw = ImageDraw.Draw(self.map_overview_image)
        min_x = self.map_overview_params["min_x"]
        max_y = self.map_overview_params["max_y"]
        scale = self.map_overview_params["scale"]
        dirty_tiles = [
            self.hex_lookup[tile_key]
            for tile_key in self.map_overview_dirty_tile_keys
            if tile_key in self.hex_lookup
        ]
        for tile in dirty_tiles:
            self.draw_tile_on_map_overview(draw, tile, min_x, max_y, scale)
        self.update_map_overview_sprite_from_image()
        self.map_overview_dirty_tile_keys.clear()
        self.map_overview_dirty = False

    def clamp_camera_position(self, x, y):
        min_x, min_y, max_x, max_y = self.map_bounds
        clamped_x = max(min_x, min(max_x, x))
        clamped_y = max(min_y, min(max_y, y))
        return clamped_x, clamped_y

    def use_overview_lod(self):
        return self.map_overview_sprite is not None and self.world_camera.zoom <= OVERVIEW_LOD_ZOOM

    def draw_capital_markers(self):
        for player in self.players:
            tile = player.capital_tile
            if not tile:
                continue

            arcade.draw_circle_filled(tile.center_x, tile.center_y, 18, (10, 12, 16, 235))
            arcade.draw_circle_outline(tile.center_x, tile.center_y, 22, player.border_color, 4)
            arcade.draw_circle_filled(tile.center_x, tile.center_y, 8, player.border_color)

    def setup_premium_shader(self):
        if not self.window:
            return
        if self.premium_shader_attempted:
            return

        try:
            vertex_shader = """
            #version 330
            in vec2 in_pos;
            out vec2 uv;

            void main() {
                uv = in_pos * 0.5 + 0.5;
                gl_Position = vec4(in_pos, 0.0, 1.0);
            }
            """
            fragment_shader = """
            #version 330
            in vec2 uv;
            out vec4 fragColor;

            uniform float time;
            uniform vec2 resolution;

            float hash(vec2 p) {
                return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
            }

            void main() {
                vec2 aspect = resolution / max(resolution.x, resolution.y);
                vec2 centered = (uv - vec2(0.5)) * aspect;
                float vignette = smoothstep(0.82, 0.28, length(centered));
                float edge = 1.0 - vignette;
                float grain = hash(gl_FragCoord.xy + time * 23.0) - 0.5;
                vec3 color = mix(vec3(0.0, 0.015, 0.025), vec3(0.10, 0.095, 0.065), vignette);
                float alpha = edge * 0.13 + abs(grain) * 0.018;
                fragColor = vec4(color, alpha);
            }
            """
            self.premium_shader_program = self.window.ctx.program(
                vertex_shader=vertex_shader,
                fragment_shader=fragment_shader,
            )
            quad = struct.pack("8f", -1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0)
            buffer = self.window.ctx.buffer(data=quad)
            self.premium_shader_geometry = self.window.ctx.geometry(
                [BufferDescription(buffer, "2f", ["in_pos"])],
                mode=arcade.gl.TRIANGLE_STRIP,
            )
            self.premium_shader_enabled = True
            self.premium_shader_attempted = True
        except Exception as exc:
            self.premium_shader_enabled = False
            self.premium_shader_attempted = True
            print(f"Premium shader disabled: {exc}")

    def draw_premium_shader_overlay(self):
        if not self.premium_shader_enabled or not self.premium_shader_program or not self.premium_shader_geometry:
            return

        try:
            try:
                self.premium_shader_program["time"] = self.shader_time
                self.premium_shader_program["resolution"] = (float(self.window.width), float(self.window.height))
            except KeyError:
                pass
            self.window.ctx.enable(arcade.gl.BLEND)
            self.premium_shader_geometry.render(self.premium_shader_program)
        except Exception as exc:
            self.premium_shader_enabled = False
            print(f"Premium shader disabled: {exc}")

    def clamp_target_camera(self):
        self.target_camera_x, self.target_camera_y = self.clamp_camera_position(
            self.target_camera_x,
            self.target_camera_y,
        )

    def get_visible_tiles(self):
        camera_x, camera_y = self.world_camera.position
        zoom = self.world_camera.zoom
        view_width = self.window.width / zoom
        view_height = self.window.height / zoom
        left = camera_x - view_width / 2 - HEX_SIZE * 4
        right = camera_x + view_width / 2 + HEX_SIZE * 4
        bottom = camera_y - view_height / 2 - HEX_SIZE * 4
        top = camera_y + view_height / 2 + HEX_SIZE * 4
        self.visible_tiles.clear()
        min_cell_x, min_cell_y = self.spatial_hash_coords(left, bottom)
        max_cell_x, max_cell_y = self.spatial_hash_coords(right, top)
        candidates = []
        seen = set()
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                for tile in self.tile_spatial_hash.get((cell_x, cell_y), []):
                    tile_key = (tile.q, tile.r)
                    if tile_key in seen:
                        continue
                    seen.add(tile_key)
                    candidates.append(tile)

        for tile in sorted(candidates, key=lambda item: (item.r, item.q)):
            min_x, min_y, max_x, max_y = tile.bounding_box
            if (max_x >= left and min_x <= right and
                    max_y >= bottom and min_y <= top):
                self.visible_tiles.append(tile)

    def on_draw(self):
        self.sync_cameras_to_window()
        self.clear()
        self.begin_ui_text_frame()
        if not self.premium_shader_enabled and not self.premium_shader_attempted:
            self.setup_premium_shader()
        self.world_camera.use()
        if self.map_overview_dirty and self.use_overview_lod():
            self.refresh_dirty_map_overview_tiles()
        if self.use_overview_lod():
            self.map_overview_sprite_list.draw()
        else:
            self.visible_tiles.draw()
            if not self.construction_placement_mode:
                self.draw_tile_visual_system()
            self.draw_construction_placement_labels()
        self.draw_state_borders()
        if self.map_layer == "political":
            self.draw_capital_markers()
        if self.selection_border.visible:
            self.selection_border_sprite_list.draw()
        self.draw_army_plans()
        self.draw_divisions()
        self.draw_premium_shader_overlay()
        self.gui_camera.use()
        if not self.paused:
            self.draw_battle_indicators()
        self.draw_division_groups()
        self.draw_division_selection_box()
        self.draw_division_list_panel()
        self.draw_top_status_bar()
        self.draw_top_navigation_bar()
        self.draw_side_panel()
        self.draw_hex_info_panel()
        self.draw_gui()
        self.draw_army_command_bar()
        if not self.paused:
            self.draw_battle_panel()
        self.draw_time_hud()
        self.draw_map_layer_control()
        if self.paused:
            self.draw_pause_menu()
        construction_tooltip_data = self.construction_hover_tooltip_data()
        top_tooltip_active = (
            self.hovered_population_summary
            or self.hovered_budget_summary
            or self.hovered_resource_summary
            or self.hovered_warning_key
            or self.hovered_division_detach_button
            or self.hovered_army_plan_button
        )
        if construction_tooltip_data or top_tooltip_active:
            self.draw_ui_text_batch()
            self.begin_tooltip_text_frame()
            self.draw_construction_hover_tooltip(construction_tooltip_data)
            self.draw_top_hover_tooltips()
            self.draw_division_detach_tooltip()
            self.draw_army_plan_tooltip()
            self.draw_tooltip_text_batch()
        else:
            self.draw_ui_text_batch()
        self.debug_text.text = f"FPS: {self.fps:.0f} | Zoom: {self.world_camera.zoom:.2f}"
        self.debug_text.x = self.window.width - 12
        self.debug_text.y = self.window.height - 8
        self.debug_text.draw()

    def refresh_visible_tiles(self):
        if not self.window or not self.hex_grid:
            return

        if self.use_overview_lod():
            self.visible_tiles.clear()
            self.refresh_visible_tiles_signature()
        else:
            self.get_visible_tiles()
            self.refresh_visible_tiles_signature()
            self.update_draw_list()
        self.last_visible_update = time.time()

    def sync_cameras_to_window(self):
        if not self.window:
            return

        self.window.viewport = (0, 0, self.window.width, self.window.height)
        self.world_camera.match_window(viewport=True, projection=True, position=False)
        self.gui_camera.match_window(viewport=True, projection=True, position=True)

    def begin_ui_text_frame(self):
        self.ui_text_pool_cursor = 0

    def draw_ui_text_batch(self):
        for index in range(self.ui_text_pool_cursor, self.ui_text_pool_max_used):
            if index < len(self.ui_text_pool) and self.ui_text_pool[index].text:
                self.ui_text_pool[index].text = ""
        self.ui_text_pool_max_used = max(self.ui_text_pool_max_used, self.ui_text_pool_cursor)
        self.batch.draw()

    def draw_ui_text(
        self,
        text,
        x,
        y,
        color=arcade.color.WHITE,
        font_size=12,
        anchor_x="left",
        anchor_y="baseline",
        bold=False,
    ):
        index = self.ui_text_pool_cursor
        self.ui_text_pool_cursor += 1

        if index >= len(self.ui_text_pool):
            self.ui_text_pool.append(
                arcade.Text(
                    "",
                    0,
                    0,
                    color,
                    font_size,
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                    batch=self.batch,
                )
            )

        label = self.ui_text_pool[index]
        new_text = str(text)
        if label.text != new_text:
            label.text = new_text
        if label.font_size != font_size:
            label.font_size = font_size
        if label.anchor_x != anchor_x:
            label.anchor_x = anchor_x
        if label.anchor_y != anchor_y:
            label.anchor_y = anchor_y
        if label.color != color:
            label.color = color
        label.x = x
        label.y = y

    def begin_trade_text_frame(self):
        self.trade_text_pool_cursor = 0

    def draw_trade_text(
        self,
        text,
        x,
        y,
        color=arcade.color.WHITE,
        font_size=12,
        anchor_x="left",
        anchor_y="baseline",
    ):
        index = self.trade_text_pool_cursor
        self.trade_text_pool_cursor += 1
        if index >= len(self.trade_text_pool):
            self.trade_text_pool.append(
                arcade.Text(
                    "",
                    0,
                    0,
                    color,
                    font_size,
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                )
            )
        label = self.trade_text_pool[index]
        new_text = str(text)
        if label.text != new_text:
            label.text = new_text
        if label.font_size != font_size:
            label.font_size = font_size
        if label.anchor_x != anchor_x:
            label.anchor_x = anchor_x
        if label.anchor_y != anchor_y:
            label.anchor_y = anchor_y
        if label.color != color:
            label.color = color
        if label.x != x:
            label.x = x
        if label.y != y:
            label.y = y
        label.draw()

    def clear_unused_trade_text(self):
        for index in range(self.trade_text_pool_cursor, len(self.trade_text_pool)):
            if self.trade_text_pool[index].text:
                self.trade_text_pool[index].text = ""

    def begin_tooltip_text_frame(self):
        self.tooltip_text_pool_cursor = 0

    def draw_tooltip_text_batch(self):
        for index in range(self.tooltip_text_pool_cursor, self.tooltip_text_pool_max_used):
            if index < len(self.tooltip_text_pool) and self.tooltip_text_pool[index].text:
                self.tooltip_text_pool[index].text = ""
        self.tooltip_text_pool_max_used = max(self.tooltip_text_pool_max_used, self.tooltip_text_pool_cursor)
        self.tooltip_batch.draw()

    def draw_tooltip_text(
        self,
        text,
        x,
        y,
        color=arcade.color.WHITE,
        font_size=12,
        anchor_x="left",
        anchor_y="baseline",
    ):
        index = self.tooltip_text_pool_cursor
        self.tooltip_text_pool_cursor += 1

        if index >= len(self.tooltip_text_pool):
            self.tooltip_text_pool.append(
                arcade.Text(
                    "",
                    0,
                    0,
                    color,
                    font_size,
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                    batch=self.tooltip_batch,
                )
            )

        label = self.tooltip_text_pool[index]
        new_text = str(text)
        if label.text != new_text:
            label.text = new_text
        if label.font_size != font_size:
            label.font_size = font_size
        if label.anchor_x != anchor_x:
            label.anchor_x = anchor_x
        if label.anchor_y != anchor_y:
            label.anchor_y = anchor_y
        if label.color != color:
            label.color = color
        label.x = x
        label.y = y

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

        contracts = self.normalize_trade_contracts(player)
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
        previous_key = self.active_top_panel_key
        self.active_top_panel_key = key
        self.side_panel_target = 1.0
        if self.selected_resource_key and previous_key != key:
            self.create_map_overview()
            self.refresh_visible_tiles()
        if previous_key == "construction" and key != "construction":
            self.set_construction_placement_mode(False)

    def close_top_panel(self):
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

        self.recalculate_monthly_balance(player)
        current = self.economy_snapshot(player)
        player.economy_current_snapshot = current
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
        balance = self.cached_resource_balance_breakdown(player, max_age=1.0)
        contracts = self.normalize_trade_contracts(player)
        contract_signature = tuple(
            sorted((contract["resource"], contract["mode"], round(contract["amount"], 3)) for contract in contracts)
        )
        market_state = self.simulation_server.market_state
        cache_key = (
            self.trade_panel_category,
            contract_signature,
            round(getattr(player, "resource_balance_last_update", 0.0), 3),
            market_state.revision,
        )
        if self.trade_panel_cache and self.trade_panel_cache.get("key") == cache_key:
            return self.trade_panel_cache

        trade_flows = self.estimate_monthly_trade_flows(player)
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
            if row["buy"] > 0:
                contract_text = f"Покупка {self.format_resource_amount(row['buy'])}"
            elif row["sell"] > 0:
                contract_text = f"Продажа {self.format_resource_amount(row['sell'])}"
            price_text = f"{self.format_money(row['buy_price'])}/{self.format_money(row['sell_price'])}"
            change_text = f"{row['price_change']:+.0%}"
            change_color = (174, 224, 158) if row["price_change"] >= 0 else (236, 168, 154)
            market_text = f"{self.format_resource_amount(row['market_demand'])}/{self.format_resource_amount(row['market_supply'])}"
            balance_color = (170, 222, 154) if row["balance"] >= 0 else (238, 168, 154)
            row["display_values"] = [
                (self.resource_display_name(row["key"]), (220, 230, 240), 0),
                (self.format_resource_amount(row["stock"]), (220, 230, 240), 118),
                (self.format_resource_amount(row["balance"]), balance_color, 180),
                (price_text, (220, 230, 240), 244),
                (change_text, change_color, 332),
                (market_text, (190, 210, 224), 378),
                (contract_text, (220, 230, 240), 466),
            ]
        self.trade_panel_cache = {"key": cache_key, "rows": rows, "flows": trade_flows}
        return self.trade_panel_cache

    def trade_rows(self):
        return self.trade_panel_snapshot().get("rows", [])

    def scroll_trade_rows(self, amount):
        rows = self.trade_rows()
        panel_x, panel_y, _panel_width, panel_height = self.side_panel_rect()
        table_y = panel_y + panel_height - 254
        row_height = 28
        max_rows = max(6, int((table_y - 28 - (panel_y + 28)) / row_height))
        max_scroll = max(0, len(rows) - max_rows)
        old_index = self.trade_scroll_index
        self.trade_scroll_index = max(0, min(max_scroll, self.trade_scroll_index + int(amount)))
        return self.trade_scroll_index != old_index

    def draw_trade_panel_content(self, panel_x, panel_y, panel_width, panel_height):
        if not self.human_player:
            return
        self.begin_trade_text_frame()
        player = self.human_player
        self.trade_action_rects = []
        self.trade_category_rects = self.trade_category_rects_for_panel()
        snapshot = self.trade_panel_snapshot()
        trade_flows = snapshot["flows"]
        balance = trade_flows["money_balance"]
        buy_limit_text = (
            f"Покупка: {self.format_resource_amount(trade_flows['buy_capacity_used'])}/"
            f"{self.format_resource_amount(trade_flows['buy_capacity_limit'])} ед./мес"
        )
        sell_limit_text = (
            f"Продажа: {self.format_resource_amount(trade_flows['sell_capacity_used'])}/"
            f"{self.format_resource_amount(trade_flows['sell_capacity_limit'])} ед./мес"
        )
        money_color = (180, 226, 168) if balance >= 0 else (236, 168, 154)
        self.draw_trade_text("Внешний рынок", panel_x + 18, panel_y + panel_height - 70, arcade.color.WHITE, 15)
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
            f"{next_execution.day} {MONTH_NAMES[next_execution.month - 1]} "
            f"{next_execution.hour:02}:{next_execution.minute:02}"
        )
        self.draw_trade_text(
            f"Исполнение: понедельник 00:00, раз в неделю. След.: {next_execution_text}",
            panel_x + 18,
            panel_y + panel_height - 146,
            (156, 176, 194),
            10,
        )

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
        for text, offset in headers:
            self.draw_trade_text(text, table_x + offset, table_y, (150, 166, 184), 10)

        row_height = 28
        y = table_y - 28
        max_rows = max(6, int((y - (panel_y + 28)) / row_height))
        max_scroll = max(0, len(rows) - max_rows)
        self.trade_scroll_index = max(0, min(self.trade_scroll_index, max_scroll))
        visible_rows = rows[self.trade_scroll_index:self.trade_scroll_index + max_rows]
        for index, row in enumerate(visible_rows):
            row_y = y - index * row_height
            row_number = self.trade_scroll_index + index
            fill = (24, 32, 42, 118) if row_number % 2 == 0 else (30, 38, 48, 118)
            arcade.draw_lbwh_rectangle_filled(table_x, row_y - 4, panel_width - 36, row_height, fill)
            for value, color, offset in row["display_values"]:
                self.draw_trade_text(value, table_x + offset, row_y + 9, color, 10, anchor_y="center")

            button_specs = [
                ("-", "buy", -TRADE_CONTRACT_STEP, table_x + panel_width - 156),
                ("+", "buy", TRADE_CONTRACT_STEP, table_x + panel_width - 128),
                ("-", "sell", -TRADE_CONTRACT_STEP, table_x + panel_width - 82),
                ("+", "sell", TRADE_CONTRACT_STEP, table_x + panel_width - 54),
            ]
            for label, mode, delta, button_x in button_specs:
                rect = (button_x, row_y - 1, 24, 20)
                self.trade_action_rects.append((rect, row["key"], mode, delta))
                fill = (42, 62, 82, 210)
                if mode == "buy":
                    border = (124, 178, 232)
                else:
                    border = (180, 210, 128)
                arcade.draw_lbwh_rectangle_filled(*rect, fill)
                arcade.draw_lbwh_rectangle_outline(*rect, border, 1)
                self.draw_trade_text(label, rect[0] + rect[2] / 2, rect[1] + rect[3] / 2,
                                     arcade.color.WHITE, 12, anchor_x="center", anchor_y="center")

        if len(rows) > max_rows:
            track_x = panel_x + panel_width - 18
            track_y = panel_y + 46
            track_height = max(40, table_y - 48 - track_y)
            arcade.draw_lbwh_rectangle_filled(track_x, track_y, 4, track_height, (42, 52, 64, 180))
            thumb_height = max(24, track_height * max_rows / len(rows))
            thumb_y = track_y + (track_height - thumb_height) * (1 - self.trade_scroll_index / max(1, max_scroll))
            arcade.draw_lbwh_rectangle_filled(track_x - 2, thumb_y, 8, thumb_height, (130, 154, 184, 220))

        legend_y = panel_y + 20
        self.draw_trade_text("Цена: покупка/продажа. Лимит зависит от портов, складов, логистики и снабжения.",
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
        if tile:
            return f"{label} {tile.q}:{tile.r}"
        return label

    @staticmethod
    def construction_project_group_key(project):
        cost = project.get("cost", {})
        tile = project.get("tile")
        building_key = cost.get("building") or project.get("building")
        return id(tile), building_key

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
        from_coverage = first_cost.get("from_coverage", 0.0)
        if group["start_index"] == 0 and projects[0].get("progress", 0.0) > 0:
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
        project = player.construction_queue[0]
        status_info = self.evaluate_construction_project_status(
            player,
            project,
            month_fraction=CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION,
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
        elif status == "building":
            monthly_delta = self.construction_project_progress_delta(player, project, month_fraction=1.0)
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
        if groups:
            for index, group in enumerate(groups[:visible_count]):
                project = group["projects"][0]
                x, y, width, height = queue_rects[index]
                active = group["start_index"] == 0
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
                elif line.startswith("Статус: Строится"):
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
            "Чем больше промзон, городов и сел, тем быстрее идет первый проект в очереди.",
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

    def draw_side_panel(self):
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
            self.draw_resources_panel_content(panel_x, panel_y, panel_width, panel_height)
        elif self.active_top_panel_key == "economy":
            self.draw_economy_panel_content(panel_x, panel_y, panel_width, panel_height)
        elif self.active_top_panel_key == "trade":
            self.draw_trade_panel_content(panel_x, panel_y, panel_width, panel_height)
        elif self.active_top_panel_key == "construction":
            self.draw_construction_panel_content(panel_x, panel_y, panel_width, panel_height)
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
        self.hovered_hex_panel_close = False
        self.hovered_hex_build_button = False
        self.hovered_hex_specialization_button = False
        self.hex_panel_scroll = 0.0
        self.hex_panel_content_height = 0.0
        self.hex_resources_expanded = False
        self.hex_resources_toggle_rect = None
        self.hex_panel_specialization_mode = False
        self.hex_specialization_row_rects = []
        self.hex_panel_message = ""
        self.rebuild_selection_borders()

    def toggle_hex_specialization_mode(self):
        self.hex_panel_specialization_mode = not self.hex_panel_specialization_mode
        self.hex_panel_message = ""

    def set_selected_tile_industry_sector(self, sector):
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

    def draw_hex_info_panel(self):
        tiles = self.selected_hex_tiles()
        if not tiles:
            return
        tile = self.selected_tile if self.selected_tile in tiles else tiles[-1]
        multi_selected = len(tiles) > 1

        panel_x, panel_y, panel_width, panel_height = self.hex_panel_rect()
        content_bottom, content_top = self.hex_panel_content_bounds()
        content_width = panel_width - 32
        visible_content_height = max(1, content_top - content_bottom)
        self.hex_specialization_row_rects = []
        self.hex_resources_toggle_rect = None

        def visible_y(draw_y, top_margin=24):
            return content_bottom <= draw_y <= content_top + top_margin

        def panel_text(text, x, draw_y, color=arcade.color.WHITE, font_size=12, **kwargs):
            if visible_y(draw_y):
                self.draw_ui_text(text, x, draw_y, color, font_size, **kwargs)

        def panel_section(title, draw_y):
            panel_text(title, panel_x + 16, draw_y, arcade.color.WHITE, 14)
            return draw_y - 20

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

        owner_name = self.mixed_or_single(
            [selected.owner.name if selected.owner else "Нейтральная территория" for selected in tiles],
            mixed_label="Разные владельцы",
        )
        population = sum(self.estimated_tile_population(selected) or 0.0 for selected in tiles)
        terrain_name = self.mixed_or_single(
            [self.terrain_display_name(selected.terrain_type) for selected in tiles],
            mixed_label="Разная",
        )
        passability = self.average_tile_value(tiles, "passability", 0.0)
        supply_score = self.average_tile_value(tiles, "supply_score", 0.0)
        info_rows = [
            ("Владелец", owner_name),
            ("Население", self.format_population(population)),
            ("Местность", terrain_name),
            ("Проходимость", self.format_percent(passability)),
            ("Снабжение", self.format_percent(supply_score)),
        ]
        for label, value in info_rows:
            panel_text(label, panel_x + 16, y, (150, 166, 184), 11)
            panel_text(value, panel_x + 122, y, (224, 234, 244), 12)
            y -= 18

        y -= 8
        y = panel_section("Ресурсы", y)
        panel_text("Название", panel_x + 16, y, (150, 166, 184), 10)
        panel_text("В земле", panel_x + 174, y, (150, 166, 184), 10)
        panel_text("Склад", panel_x + 270, y, (150, 166, 184), 10)
        y -= 16

        resource_rows = self.hex_resource_rows_for_tiles(tiles)
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
        tile_capacity, tile_used = self.storage_summary_for_tiles(tiles)
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
        coverage, buildings = self.building_coverage_rows_for_tiles(tiles)
        if coverage:
            for key, value in sorted(coverage.items(), key=lambda item: item[0]):
                label = BUILDING_DISPLAY_NAMES.get(key, key)
                value_text = self.format_tile_coverage_total(value) if multi_selected else f"{value:.0%}"
                panel_text(f"{label}: {value_text}", panel_x + 16, y, (224, 234, 244), 11)
                y -= 16
        elif buildings:
            for key in sorted(buildings):
                panel_text(BUILDING_DISPLAY_NAMES.get(key, key), panel_x + 16, y, (224, 234, 244), 11)
                y -= 16
        else:
            panel_text("Пока нет", panel_x + 16, y, (180, 192, 205), 11)
            y -= 16

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

            if self.hex_panel_specialization_mode:
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

        if self.selected_tile_has_industry():
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

    def draw_time_hud(self):
        panel_x, panel_y, panel_width, panel_height = self.time_panel_rect
        snapshot = self.simulation_client.snapshot
        current_time = snapshot.current_time

        arcade.draw_lbwh_rectangle_filled(panel_x, panel_y, panel_width, panel_height, (20, 29, 38, 235))
        arcade.draw_lbwh_rectangle_outline(panel_x, panel_y, panel_width, panel_height, (100, 126, 155), 2)

        self.time_date_text.text = f"{current_time.day} {MONTH_NAMES[current_time.month - 1]} {current_time.year}  {current_time.hour:02}:00"
        self.time_date_text.x = panel_x + panel_width / 2
        self.time_date_text.y = panel_y + panel_height - 18
        self.time_date_text.draw()

        if snapshot.paused:
            self.time_clock_text.text = f"Пауза  |  Скорость {snapshot.speed_level}/5"
        else:
            self.time_clock_text.text = f"Скорость {snapshot.speed_level}/5"
        self.time_clock_text.x = panel_x + 210
        self.time_clock_text.y = panel_y + 22
        self.time_clock_text.draw()

        self.time_buttons[1].set_label(">" if snapshot.paused else "II")
        for button in self.time_buttons:
            button.draw(button == self.hovered_time_button)

    def map_layer_button_rect(self):
        return self.window.width - 62, 18, 44, 44

    def resource_group_button_rect(self):
        layer_x, layer_y, _layer_width, layer_height = self.map_layer_button_rect()
        width = 190
        return layer_x - width - 12, layer_y, width, layer_height

    def resource_group_option_rects(self):
        button_x, button_y, button_width, button_height = self.resource_group_button_rect()
        option_height = 34
        option_gap = 6
        base_y = button_y + button_height + 10 - (1 - self.resource_group_menu_progress) * 18
        return [
            (button_x, base_y + index * (option_height + option_gap), button_width, option_height)
            for index, _group in enumerate(RESOURCE_MAP_GROUPS)
        ]

    def map_layer_option_rects(self):
        button_x, button_y, button_width, button_height = self.map_layer_button_rect()
        option_width = 190
        option_height = 34
        option_gap = 6
        x = button_x + button_width - option_width
        base_y = button_y + button_height + 10 - (1 - self.map_layer_menu_progress) * 18
        return [
            (x, base_y + index * (option_height + option_gap), option_width, option_height)
            for index, _layer in enumerate(MAP_LAYERS)
        ]

    @staticmethod
    def point_in_rect(x, y, rect):
        rect_x, rect_y, rect_width, rect_height = rect
        return rect_x <= x <= rect_x + rect_width and rect_y <= y <= rect_y + rect_height

    def invalidate_division_render_cache(self):
        self.division_render_cache_key = None
        self.division_groups_cache_key = None

    def set_selected_divisions(self, divisions, additive=False, toggle=False):
        if not additive and not toggle:
            for division in self.divisions:
                division.selected = False
            self.selected_division_ids.clear()

        for division in divisions:
            if not division or division.owner != self.human_player:
                continue
            if toggle and division.id in self.selected_division_ids:
                division.selected = False
                self.selected_division_ids.discard(division.id)
            else:
                division.selected = True
                self.selected_division_ids.add(division.id)
        if not self.selected_division_ids:
            self.division_list_scroll_index = 0
            self.active_division_list_army_id = None
        self.invalidate_division_render_cache()

    def selected_divisions(self):
        return [
            division
            for division in self.divisions
            if division.id in self.selected_division_ids
        ]

    def division_display_name(self, division):
        template = self.division_template(division.template_key)
        base_name = template.get("name", "Дивизия")
        return f"{division.id}. {base_name}"

    def division_ui_left_edge(self, preferred_width=355):
        x = 10
        if self.side_panel_progress > 0.01:
            panel_x, _panel_y, panel_width, _panel_height = self.side_panel_rect()
            panel_right = panel_x + panel_width
            if panel_right > 0:
                x = panel_right + 10
        max_x = max(10, self.window.width - preferred_width - 10)
        return min(x, max_x)

    def army_command_bar_rect(self):
        if not self.human_player:
            return None
        if not self.selected_division_ids and not (getattr(self.human_player, "armies", []) or []):
            return None
        x = self.division_ui_left_edge(360)
        max_right = self.window.width - 78
        width = min(360, max(250, max_right - x))
        if x + width > max_right:
            x = max(10, max_right - width)
        return x, 14, width, 82

    def army_command_items(self):
        if not self.human_player:
            return []
        armies = list(getattr(self.human_player, "armies", []) or [])
        armies.sort(key=lambda army: army.id)
        return armies

    def divisions_for_army(self, army):
        ids = set(getattr(army, "division_ids", []) or [])
        return [
            division
            for division in getattr(army.owner, "divisions", []) or []
            if division.id in ids and division.army_id == army.id
        ]

    def selected_free_divisions(self):
        return [
            division
            for division in self.selected_divisions()
            if division.owner == self.human_player and division.army_id is None
        ]

    def division_list_rect(self):
        groups = self.division_list_groups()
        if not groups:
            return None
        preferred_width = 355
        x = self.division_ui_left_edge(preferred_width)
        width = min(preferred_width, max(280, self.window.width - x - 14))
        top = self.window.height - TOP_UI_HEIGHT - 10
        army_bar_rect = self.army_command_bar_rect()
        bottom = 88 if not army_bar_rect else army_bar_rect[1] + army_bar_rect[3] + 10
        height = self.division_list_total_height(groups, top, bottom)
        return x, top - height, width, height

    def division_list_rows(self):
        rows = self.selected_divisions()
        rows.sort(key=lambda division: (division.template_key, division.id))
        return rows

    def army_by_id(self, army_id):
        if not self.human_player:
            return None
        for army in getattr(self.human_player, "armies", []) or []:
            if army.id == army_id:
                return army
        return None

    @staticmethod
    def owner_id(owner):
        return owner.id if owner else None

    def battle_plan_tiles(self, plan):
        return [
            self.hex_lookup[tile_key]
            for tile_key in getattr(plan, "line_tile_keys", []) or []
            if tile_key in self.hex_lookup
        ]

    def army_plan_button_definitions(self):
        return [
            ("front_auto", "Ф", "создать линию фронта"),
            ("front_custom", "П", "создать линию фронта произвольной длинны"),
            ("defensive_line", "О", "создать линию обороны"),
            ("offensive_line", "Н", "создать линию наступления"),
            ("execute", "▶", "начать выполнение плана"),
            ("clear", "×", "очистить план"),
        ]

    def active_army_for_plan_controls(self):
        if not self.human_player:
            return None
        active_key = self.active_division_list_army_id
        if isinstance(active_key, int):
            army = self.army_by_id(active_key)
            if army:
                return army
        for army in self.army_command_items():
            if any(division.id in self.selected_division_ids for division in self.divisions_for_army(army)):
                return army
        return None

    def army_plan_button_at(self, x, y):
        for rect, army, action, _label, tooltip in self.army_plan_button_rects:
            if self.point_in_rect(x, y, rect):
                return {
                    "rect": rect,
                    "army": army,
                    "action": action,
                    "tooltip": tooltip,
                }
        return None

    def begin_army_plan_mode(self, army, mode):
        if not army:
            return False
        self.army_plan_mode = mode
        self.army_plan_army_id = army.id
        self.army_plan_drag_active = False
        self.army_plan_start_tile = None
        self.army_plan_preview_tiles = []
        self.army_plan_preview_target_owner = None
        return True

    def cancel_army_plan_mode(self):
        self.army_plan_mode = None
        self.army_plan_army_id = None
        self.army_plan_drag_active = False
        self.army_plan_start_tile = None
        self.army_plan_preview_tiles = []
        self.army_plan_preview_target_owner = None

    def border_target_owner_ids(self, tile, owner):
        if not tile or self.is_water_tile(tile) or tile.owner is not owner:
            return set()
        target_ids = set()
        for neighbor in self.neighbor_tiles(tile):
            if self.is_water_tile(neighbor) or neighbor.owner is owner:
                continue
            target_ids.add(self.owner_id(neighbor.owner))
        return target_ids

    def primary_border_target_owner_id(self, tile, owner):
        target_ids = self.border_target_owner_ids(tile, owner)
        if not target_ids:
            return None
        owned_targets = sorted(target_id for target_id in target_ids if target_id is not None)
        return owned_targets[0] if owned_targets else None

    def is_front_tile_for_target(self, tile, owner, target_owner_id):
        return target_owner_id in self.border_target_owner_ids(tile, owner)

    def collect_auto_front_line(self, army, clicked_tile):
        if not army or not clicked_tile or clicked_tile.owner is not army.owner:
            return [], None
        target_owner_id = self.primary_border_target_owner_id(clicked_tile, army.owner)
        if target_owner_id not in self.border_target_owner_ids(clicked_tile, army.owner):
            return [], None
        return self.collect_front_component_for_target(army, clicked_tile, target_owner_id), target_owner_id

    def collect_front_component_for_target(self, army, seed_tile, target_owner_id):
        if not army or not seed_tile or seed_tile.owner is not army.owner:
            return []
        if not self.is_front_tile_for_target(seed_tile, army.owner, target_owner_id):
            return []
        queue = deque([seed_tile])
        seen = set()
        tiles = []
        while queue:
            tile = queue.popleft()
            tile_key = self.tile_key(tile)
            if tile_key in seen:
                continue
            seen.add(tile_key)
            if not self.is_front_tile_for_target(tile, army.owner, target_owner_id):
                continue
            tiles.append(tile)
            for neighbor in self.neighbor_tiles(tile):
                if neighbor.owner is army.owner and self.tile_key(neighbor) not in seen:
                    queue.append(neighbor)
        return self.order_tile_line(tiles, seed_tile)

    def order_tile_line(self, tiles, preferred_start=None):
        if not tiles:
            return []
        tile_by_key = {self.tile_key(tile): tile for tile in tiles}
        tile_keys = set(tile_by_key)
        graph = {}
        for tile in tiles:
            key = self.tile_key(tile)
            graph[key] = [
                self.tile_key(neighbor)
                for neighbor in self.neighbor_tiles(tile)
                if self.tile_key(neighbor) in tile_keys
            ]
        endpoints = [key for key, neighbors in graph.items() if len(neighbors) <= 1]
        if endpoints:
            if preferred_start:
                start_key = min(endpoints, key=lambda key: self.hex_distance(tile_by_key[key], preferred_start))
            else:
                start_key = endpoints[0]
        elif preferred_start and self.tile_key(preferred_start) in tile_keys:
            start_key = self.tile_key(preferred_start)
        else:
            start_key = next(iter(tile_keys))

        ordered = []
        visited = set()
        current_key = start_key
        previous_key = None
        while current_key and current_key not in visited:
            ordered.append(tile_by_key[current_key])
            visited.add(current_key)
            candidates = [key for key in graph[current_key] if key != previous_key and key not in visited]
            if candidates:
                previous_key, current_key = current_key, candidates[0]
                continue
            remaining = [key for key in tile_keys if key not in visited]
            if not remaining:
                break
            previous_key = None
            current_key = min(remaining, key=lambda key: self.hex_distance(tile_by_key[key], tile_by_key[ordered and self.tile_key(ordered[-1]) or start_key]))
        return ordered

    def constrained_tile_path(self, start_tile, end_tile, valid_tile_fn):
        if not start_tile or not end_tile or not valid_tile_fn(start_tile) or not valid_tile_fn(end_tile):
            return []
        if start_tile == end_tile:
            return [start_tile]
        queue = deque([start_tile])
        start_key = self.tile_key(start_tile)
        end_key = self.tile_key(end_tile)
        came_from = {start_key: None}
        tile_lookup = {start_key: start_tile}
        max_expansions = min(len(self.hex_grid), max(2000, self.hex_distance(start_tile, end_tile) * 90))
        expansions = 0
        while queue and expansions < max_expansions:
            current = queue.popleft()
            expansions += 1
            if current == end_tile:
                break
            for neighbor in self.neighbor_tiles(current):
                if not valid_tile_fn(neighbor):
                    continue
                neighbor_key = self.tile_key(neighbor)
                if neighbor_key in came_from:
                    continue
                came_from[neighbor_key] = self.tile_key(current)
                tile_lookup[neighbor_key] = neighbor
                queue.append(neighbor)
        if end_key not in came_from:
            return []
        path = []
        current_key = end_key
        while current_key:
            path.append(tile_lookup[current_key])
            current_key = came_from[current_key]
        path.reverse()
        return path

    def create_army_battle_plan(self, army, plan_type, tiles, target_owner_id=None, source_plan_id=None):
        if not army or not tiles:
            return None
        ordered_tiles = self.order_tile_line(tiles, tiles[0])
        plan = BattlePlan(
            id=self.next_battle_plan_id,
            army_id=army.id,
            plan_type=plan_type,
            line_tile_keys=[self.tile_key(tile) for tile in ordered_tiles],
            target_owner_id=target_owner_id,
            source_plan_id=source_plan_id,
        )
        self.next_battle_plan_id += 1
        army.battle_plans.append(plan)
        if plan_type in ("front", "front_custom", "defense"):
            army.active_front_plan_id = plan.id
        return plan

    def latest_army_plan(self, army, plan_types):
        for plan in reversed(getattr(army, "battle_plans", []) or []):
            if plan.active and plan.plan_type in plan_types:
                return plan
        return None

    def active_front_plan_for_army(self, army):
        active_id = getattr(army, "active_front_plan_id", None)
        for plan in getattr(army, "battle_plans", []) or []:
            if plan.active and plan.id == active_id:
                return plan
        return self.latest_army_plan(army, ("front", "front_custom", "defense"))

    def plan_is_near_dirty_tiles(self, plan_tiles, dirty_tiles, radius=3):
        if not plan_tiles or not dirty_tiles:
            return False
        return any(
            self.hex_distance(plan_tile, dirty_tile) <= radius
            for plan_tile in plan_tiles
            for dirty_tile in dirty_tiles
        )

    def front_refresh_seed_tiles(self, army, plan, dirty_tiles, old_tiles):
        candidates = []
        for tile in dirty_tiles + old_tiles:
            if not tile:
                continue
            candidates.append(tile)
            candidates.extend(self.neighbor_tiles(tile))
        valid = [
            tile for tile in candidates
            if tile.owner is army.owner and self.is_front_tile_for_target(tile, army.owner, plan.target_owner_id)
        ]
        if not valid:
            return []
        old_reference = old_tiles[0] if old_tiles else valid[0]
        valid.sort(key=lambda tile: (
            min((self.hex_distance(tile, dirty_tile) for dirty_tile in dirty_tiles), default=999),
            self.hex_distance(tile, old_reference),
        ))
        return valid

    def refresh_front_custom_plan_tiles(self, army, plan, dirty_tiles, old_tiles):
        old_keys = {self.tile_key(tile) for tile in old_tiles}
        candidate_keys = set()
        for tile in old_tiles:
            if tile.owner is army.owner and self.is_front_tile_for_target(tile, army.owner, plan.target_owner_id):
                candidate_keys.add(self.tile_key(tile))
        for tile in dirty_tiles + old_tiles:
            for candidate in [tile] + self.neighbor_tiles(tile):
                if (
                    candidate.owner is army.owner
                    and self.is_front_tile_for_target(candidate, army.owner, plan.target_owner_id)
                    and (
                        not old_tiles
                        or self.tile_key(candidate) in old_keys
                        or min(self.hex_distance(candidate, old_tile) for old_tile in old_tiles) <= 2
                    )
                ):
                    candidate_keys.add(self.tile_key(candidate))
        if not candidate_keys:
            return []
        candidates = [
            self.hex_lookup[tile_key]
            for tile_key in candidate_keys
            if tile_key in self.hex_lookup
        ]
        reference = old_tiles[0] if old_tiles else candidates[0]
        return self.order_tile_line(candidates, reference)

    def refresh_army_front_plans_for_ownership_change(self, dirty_tiles):
        if not dirty_tiles:
            return False
        changed = False
        for player in self.players:
            for army in getattr(player, "armies", []) or []:
                for plan in getattr(army, "battle_plans", []) or []:
                    if not plan.active or plan.plan_type not in ("front", "front_custom"):
                        continue
                    old_tiles = self.battle_plan_tiles(plan)
                    if old_tiles and not self.plan_is_near_dirty_tiles(old_tiles, dirty_tiles):
                        continue
                    seed_tiles = self.front_refresh_seed_tiles(army, plan, dirty_tiles, old_tiles)
                    new_tiles = []
                    if plan.plan_type == "front" and seed_tiles:
                        new_tiles = self.collect_front_component_for_target(army, seed_tiles[0], plan.target_owner_id)
                    elif plan.plan_type == "front_custom":
                        new_tiles = self.refresh_front_custom_plan_tiles(army, plan, dirty_tiles, old_tiles)
                    old_keys = list(getattr(plan, "line_tile_keys", []) or [])
                    new_keys = [self.tile_key(tile) for tile in new_tiles]
                    if new_keys and new_keys != old_keys:
                        plan.line_tile_keys = new_keys
                        army.plan_update_accumulator = ARMY_PLAN_UPDATE_INTERVAL_HOURS
                        changed = True
        return changed

    def update_army_plan_preview(self, current_tile):
        army = self.army_by_id(self.army_plan_army_id)
        if not army or not self.army_plan_start_tile or not current_tile:
            self.army_plan_preview_tiles = []
            return
        mode = self.army_plan_mode
        start_tile = self.army_plan_start_tile
        if mode == "front_custom":
            target_owner_id = self.army_plan_preview_target_owner
            valid = lambda tile: tile.owner is army.owner and self.is_front_tile_for_target(tile, army.owner, target_owner_id)
        elif mode == "defensive_line":
            valid = lambda tile: tile.owner is army.owner and not self.is_water_tile(tile)
        elif mode == "offensive_line":
            valid = lambda tile: tile.owner is not army.owner and not self.is_water_tile(tile)
        else:
            self.army_plan_preview_tiles = []
            return
        self.army_plan_preview_tiles = self.constrained_tile_path(start_tile, current_tile, valid)

    def handle_army_plan_map_press(self, x, y):
        if not self.army_plan_mode:
            return False
        army = self.army_by_id(self.army_plan_army_id)
        if not army:
            self.cancel_army_plan_mode()
            return True
        world_x, world_y = self.screen_to_world(x, y)
        tile = self.get_tile_at(world_x, world_y)
        if not tile or self.is_water_tile(tile):
            return True

        mode = self.army_plan_mode
        if mode == "front_auto":
            tiles, target_owner_id = self.collect_auto_front_line(army, tile)
            if tiles:
                self.create_army_battle_plan(army, "front", tiles, target_owner_id=target_owner_id)
            self.cancel_army_plan_mode()
            return True

        if mode == "front_custom":
            target_owner_id = self.primary_border_target_owner_id(tile, army.owner)
            if target_owner_id not in self.border_target_owner_ids(tile, army.owner):
                return True
            self.army_plan_preview_target_owner = target_owner_id
        elif mode == "defensive_line":
            if tile.owner is not army.owner:
                return True
        elif mode == "offensive_line":
            if tile.owner is army.owner:
                return True
        else:
            return True

        self.army_plan_start_tile = tile
        self.army_plan_preview_tiles = [tile]
        self.army_plan_drag_active = True
        return True

    def handle_army_plan_map_drag(self, x, y):
        if not self.army_plan_drag_active:
            return False
        world_x, world_y = self.screen_to_world(x, y)
        self.update_army_plan_preview(self.get_tile_at(world_x, world_y))
        return True

    def handle_army_plan_map_release(self, x, y):
        if not self.army_plan_drag_active:
            return False
        army = self.army_by_id(self.army_plan_army_id)
        tiles = list(self.army_plan_preview_tiles)
        mode = self.army_plan_mode
        if army and len(tiles) >= 1:
            if mode == "front_custom":
                self.create_army_battle_plan(
                    army,
                    "front_custom",
                    tiles,
                    target_owner_id=self.army_plan_preview_target_owner,
                )
            elif mode == "defensive_line":
                self.create_army_battle_plan(army, "defense", tiles)
            elif mode == "offensive_line":
                source_plan = self.active_front_plan_for_army(army)
                self.create_army_battle_plan(
                    army,
                    "offensive",
                    tiles,
                    source_plan_id=source_plan.id if source_plan else None,
                )
        self.cancel_army_plan_mode()
        return True

    def army_plan_color(self, plan_type, preview=False):
        if preview:
            return (246, 238, 142, 230)
        if plan_type == "offensive":
            return (226, 72, 62, 230)
        if plan_type == "defense":
            return (86, 188, 232, 225)
        return (218, 184, 72, 230)

    def draw_tile_line_world(self, tiles, color, width=5, node_radius=8):
        if not tiles:
            return
        for index in range(len(tiles) - 1):
            first = tiles[index]
            second = tiles[index + 1]
            arcade.draw_line(first.center_x, first.center_y, second.center_x, second.center_y, color, width)
        for tile in tiles:
            arcade.draw_circle_filled(tile.center_x, tile.center_y, node_radius, color)
            arcade.draw_circle_outline(tile.center_x, tile.center_y, node_radius + 2, (18, 22, 26, 220), 2)

    def draw_army_plans(self):
        if not self.human_player:
            return
        active_army = self.active_army_for_plan_controls()
        for army in getattr(self.human_player, "armies", []) or []:
            active = active_army and active_army.id == army.id
            for plan in getattr(army, "battle_plans", []) or []:
                if not plan.active:
                    continue
                tiles = self.battle_plan_tiles(plan)
                if not tiles:
                    continue
                color = self.army_plan_color(plan.plan_type)
                width = 7 if active else 4
                self.draw_tile_line_world(tiles, color, width=width, node_radius=7 if active else 5)
        if self.army_plan_preview_tiles:
            self.draw_tile_line_world(
                self.army_plan_preview_tiles,
                self.army_plan_color(self.army_plan_mode or "front", preview=True),
                width=6,
                node_radius=7,
            )

    def draw_army_plan_tooltip(self):
        if not self.hovered_army_plan_button:
            return
        rect = self.hovered_army_plan_button["rect"]
        text = self.hovered_army_plan_button["tooltip"]
        tooltip_width = max(190, min(310, int(len(text) * 7.2 + 28)))
        tooltip_height = 34
        tooltip_x = max(12, min(rect[0] + rect[2] / 2 - tooltip_width / 2, self.window.width - tooltip_width - 12))
        tooltip_y = max(8, rect[1] + rect[3] + 8)
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 247))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (150, 170, 194), 1)
        self.draw_tooltip_text(
            text,
            tooltip_x + tooltip_width / 2,
            tooltip_y + tooltip_height / 2 + 1,
            arcade.color.WHITE,
            11,
            anchor_x="center",
            anchor_y="center",
        )

    def division_busy_for_army_plan(self, division):
        if division.route_mode == "retreat" or division.battle_id:
            return True
        if division.path or division.target_tile or division.route_tiles:
            return True
        if division.organization < division.max_organization * DIVISION_MIN_ORDER_ORG_RATIO:
            return True
        return False

    def enemy_pressure_near_tile(self, tile, owner):
        pressure = 0
        check_tiles = [tile] + self.neighbor_tiles(tile)
        for division in self.divisions:
            if division.owner is owner or not division.tile:
                continue
            if division.tile in check_tiles:
                pressure += 1
        return pressure

    def plan_target_slots(self, army, plan):
        return self.battle_plan_tiles(plan)

    def plan_target_weight(self, owner, tile):
        pressure = self.enemy_pressure_near_tile(tile, owner)
        return 1.0 + min(4, pressure) * 0.65

    def nearest_line_tile(self, tile, line_tiles):
        if not tile or not line_tiles:
            return None
        return min(line_tiles, key=lambda line_tile: self.hex_distance(tile, line_tile))

    def line_distance(self, tile, line_tiles):
        nearest = self.nearest_line_tile(tile, line_tiles)
        return self.hex_distance(tile, nearest) if nearest else 999

    def evenly_assigned_plan_targets(self, divisions, target_slots):
        if not divisions or not target_slots:
            return {}
        assignments = {}
        unique_targets = []
        seen_target_keys = set()
        for tile in target_slots:
            tile_key = self.tile_key(tile)
            if tile_key in seen_target_keys:
                continue
            seen_target_keys.add(tile_key)
            unique_targets.append(tile)
        if not unique_targets:
            return assignments
        target_indices = {self.tile_key(tile): index for index, tile in enumerate(unique_targets)}

        def division_line_position(division):
            nearest = self.nearest_line_tile(division.tile, unique_targets)
            if nearest is None:
                return 999
            return target_indices.get(self.tile_key(nearest), 999)

        sorted_divisions = sorted(divisions, key=lambda division: (division_line_position(division), division.id))
        owner = divisions[0].owner if divisions else None
        weights = [self.plan_target_weight(owner, tile) if owner else 1.0 for tile in unique_targets]
        total_weight = sum(weights)
        if total_weight <= 0:
            total_weight = float(len(unique_targets))
            weights = [1.0 for _tile in unique_targets]

        cumulative = []
        running = 0.0
        for weight in weights:
            running += weight
            cumulative.append(running)

        for index, division in enumerate(sorted_divisions):
            if len(sorted_divisions) == 1:
                desired = total_weight / 2
            else:
                desired = (index + 0.5) * total_weight / len(sorted_divisions)
            target_index = 0
            while target_index < len(cumulative) - 1 and cumulative[target_index] < desired:
                target_index += 1
            preferred = unique_targets[target_index]
            assignments[division.id] = preferred
        return assignments

    def issue_division_plan_order(self, division, target_tile, offensive=False):
        if not division or not target_tile or division.tile == target_tile:
            return False
        path = self.find_division_path(division, target_tile)
        if not path:
            return False
        if offensive:
            path = path[:1]
            target_tile = path[-1]
        division.path = path
        division.target_tile = target_tile
        division.route_mode = "attack" if target_tile.owner and target_tile.owner != division.owner else "move"
        division.route_tiles = [division.tile] + list(path)
        division.movement_progress = 0.0
        division.visual_movement_progress = 0.0
        return True

    def execute_army_plan_step(self, army):
        divisions = [
            division for division in self.divisions_for_army(army)
            if not self.division_busy_for_army_plan(division)
        ]
        if not divisions:
            return False

        offensive_plan = self.latest_army_plan(army, ("offensive",))
        front_plan = self.active_front_plan_for_army(army)
        changed = False

        if offensive_plan:
            offensive_slots = self.plan_target_slots(army, offensive_plan)
            front_tiles = self.battle_plan_tiles(front_plan) if front_plan else []
            staging = []
            attacking = []
            for division in divisions:
                if front_tiles and self.line_distance(division.tile, front_tiles) > ARMY_PLAN_OFFENSIVE_READY_DISTANCE:
                    staging.append(division)
                else:
                    attacking.append(division)
            if staging and front_tiles:
                assignments = self.evenly_assigned_plan_targets(staging, self.plan_target_slots(army, front_plan))
                for division in staging:
                    target = assignments.get(division.id)
                    if target and self.hex_distance(division.tile, target) > ARMY_PLAN_HOLD_DISTANCE:
                        changed = self.issue_division_plan_order(division, target) or changed
            if attacking and offensive_slots:
                assignments = self.evenly_assigned_plan_targets(attacking, offensive_slots)
                for division in attacking:
                    target = assignments.get(division.id)
                    if target:
                        changed = self.issue_division_plan_order(division, target, offensive=True) or changed
            return changed

        hold_plan = front_plan
        if not hold_plan:
            return False
        slots = self.plan_target_slots(army, hold_plan)
        assignments = self.evenly_assigned_plan_targets(divisions, slots)
        for division in divisions:
            target = assignments.get(division.id)
            if target and self.hex_distance(division.tile, target) > ARMY_PLAN_HOLD_DISTANCE:
                changed = self.issue_division_plan_order(division, target) or changed
        return changed

    def update_army_plans(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        changed = False
        for player in self.players:
            for army in getattr(player, "armies", []) or []:
                if not getattr(army, "executing_plan", False):
                    continue
                army.plan_update_accumulator += elapsed_hours
                if army.plan_update_accumulator < ARMY_PLAN_UPDATE_INTERVAL_HOURS:
                    continue
                army.plan_update_accumulator = 0.0
                changed = self.execute_army_plan_step(army) or changed
        if changed:
            self.invalidate_division_render_cache()

    def division_list_groups(self):
        selected = self.selected_divisions()
        if not selected or not self.human_player:
            return []

        selected_army_ids = []
        selected_free = []
        seen = set()
        for division in selected:
            if division.army_id is None:
                selected_free.append(division)
                continue
            if division.army_id not in seen:
                selected_army_ids.append(division.army_id)
                seen.add(division.army_id)

        groups = []
        for army_id in selected_army_ids:
            army = self.army_by_id(army_id)
            if not army:
                continue
            rows = self.divisions_for_army(army)
            rows.sort(key=lambda division: (division.template_key, division.id))
            groups.append({
                "key": army.id,
                "army": army,
                "title": army.name,
                "rows": rows,
                "selected_count": sum(1 for division in rows if division.id in self.selected_division_ids),
            })

        if selected_free:
            selected_free.sort(key=lambda division: (division.template_key, division.id))
            groups.append({
                "key": "free",
                "army": None,
                "title": "Без армии",
                "rows": selected_free,
                "selected_count": len(selected_free),
            })

        keys = {group["key"] for group in groups}
        if self.active_division_list_army_id not in keys:
            self.active_division_list_army_id = groups[0]["key"] if groups else None
        groups.sort(key=lambda group: (group["key"] != self.active_division_list_army_id, str(group["key"])))
        return groups

    def division_list_total_height(self, groups, top, bottom):
        max_height = min(520, max(120, top - bottom))
        collapsed_count = max(0, len(groups) - 1)
        collapsed_total = collapsed_count * 42
        active_group = next((group for group in groups if group["key"] == self.active_division_list_army_id), groups[0])
        row_h = 40
        header_h = 86
        footer_h = 10
        active_target = header_h + footer_h + len(active_group["rows"]) * row_h
        active_height = min(max_height - collapsed_total, active_target)
        active_height = max(78, active_height)
        return min(max_height, active_height + collapsed_total)

    def draw_division_list_panel(self):
        groups = self.division_list_groups()
        rect = self.division_list_rect()
        self.division_list_panel_rect = rect
        self.division_list_panel_rects = []
        self.division_list_header_rects = []
        self.division_list_close_rects = []
        self.division_list_row_rects = []
        self.division_detach_button_rect = None
        if not groups or not rect:
            return

        panel_x, panel_y, panel_width, panel_height = rect
        current_top = panel_y + panel_height
        self.division_list_icon_shape_list = arcade.shape_list.ShapeElementList()

        collapsed_h = 36
        gap = 6
        row_h = 40
        header_h = 86
        footer_h = 10
        for group in groups:
            active = group["key"] == self.active_division_list_army_id
            if active:
                remaining_collapsed = sum(1 for other in groups if other["key"] != group["key"]) * (collapsed_h + gap)
                group_height = current_top - panel_y - remaining_collapsed
                group_height = max(78, group_height)
            else:
                group_height = collapsed_h
            group_y = current_top - group_height
            group_rect = (panel_x, group_y, panel_width, group_height)
            self.division_list_panel_rects.append(group_rect)
            header_rect = (panel_x, group_y + group_height - min(group_height, header_h), panel_width, min(group_height, header_h))
            self.division_list_header_rects.append((header_rect, group["key"]))

            fill = (18, 24, 31, 238) if active else (26, 34, 43, 236)
            border = (116, 142, 170) if active else (78, 96, 116)
            arcade.draw_lbwh_rectangle_filled(*group_rect, fill)
            arcade.draw_lbwh_rectangle_outline(*group_rect, border, 2 if active else 1)

            close_rect = (panel_x + panel_width - 34, group_y + group_height - 30, 24, 22)
            self.division_list_close_rects.append((close_rect, group["key"]))
            close_fill = (70, 50, 54, 235)
            arcade.draw_lbwh_rectangle_filled(*close_rect, close_fill)
            arcade.draw_lbwh_rectangle_outline(*close_rect, (116, 136, 156), 1)
            self.draw_ui_text("X", close_rect[0] + close_rect[2] / 2, close_rect[1] + close_rect[3] / 2 + 1,
                              arcade.color.WHITE, 10, anchor_x="center", anchor_y="center")

            title_color = arcade.color.WHITE if active else (210, 222, 234)
            self.draw_ui_text(group["title"], panel_x + 14, group_y + group_height - 24, title_color, 15)
            count_text = f"{group['selected_count']}/{len(group['rows'])}"
            self.draw_ui_text(count_text, close_rect[0] - 10, group_y + group_height - 24,
                              (216, 228, 240), 12, anchor_x="right")

            if active:
                detach_size = 26
                detach_x = close_rect[0] + (close_rect[2] - detach_size) / 2
                detach_y = close_rect[1] - detach_size - 6
                self.division_detach_button_rect = (detach_x, detach_y, detach_size, detach_size)
                detach_fill = (70, 50, 54, 235) if self.hovered_division_detach_button else (38, 48, 58, 230)
                arcade.draw_lbwh_rectangle_filled(detach_x, detach_y, detach_size, detach_size, detach_fill)
                arcade.draw_lbwh_rectangle_outline(detach_x, detach_y, detach_size, detach_size, (110, 132, 154), 1)
                center_x = detach_x + detach_size / 2
                center_y = detach_y + detach_size / 2
                arcade.draw_circle_outline(center_x, center_y, 7, (220, 226, 232), 2)
                arcade.draw_line(center_x - 8, center_y + 8, center_x + 8, center_y - 8, (224, 70, 70), 3)

                rows = group["rows"]
                org_average = sum(division.organization for division in rows) / max(1, len(rows))
                manpower = sum(division.manpower for division in rows)
                self.draw_ui_text("Командир: нет", panel_x + 14, group_y + group_height - 48, (170, 184, 200), 11)
                self.draw_ui_text(
                    f"Люди {self.format_resource_amount(manpower)}  Орг. {org_average:.0f}%",
                    panel_x + 14,
                    group_y + group_height - 68,
                    (206, 218, 230),
                    11,
                )

                list_top = group_y + group_height - header_h
                list_bottom = group_y + footer_h
                visible_count = max(1, int((list_top - list_bottom) / row_h))
                max_scroll = max(0, len(rows) - visible_count)
                scroll_key = group["key"]
                scroll_index = self.division_list_scroll_indices.get(scroll_key, self.division_list_scroll_index)
                scroll_index = max(0, min(scroll_index, max_scroll))
                self.division_list_scroll_indices[scroll_key] = scroll_index
                self.division_list_scroll_index = scroll_index
                visible_rows = rows[scroll_index:scroll_index + visible_count]

                for index, division in enumerate(visible_rows):
                    row_y = list_top - (index + 1) * row_h
                    row_rect = (panel_x + 8, row_y + 3, panel_width - 16, row_h - 5)
                    self.division_list_row_rects.append((row_rect, division))
                    selected = division.id in self.selected_division_ids
                    fill = (54, 84, 58, 220) if selected else (35, 48, 60, 210)
                    arcade.draw_lbwh_rectangle_filled(*row_rect, fill)
                    arcade.draw_lbwh_rectangle_outline(*row_rect, (76, 98, 120), 1)
                    icon_x = row_rect[0] + 22
                    icon_y = row_rect[1] + row_rect[3] / 2
                    self.append_division_template_icon(
                        self.division_list_icon_shape_list,
                        division.template_key,
                        icon_x,
                        icon_y + 2,
                        27,
                        (210, 224, 232) if selected else (152, 168, 184),
                    )
                    text_color = arcade.color.WHITE if selected else (176, 190, 204)
                    self.draw_ui_text(self.division_display_name(division), row_rect[0] + 48, icon_y + 3, text_color, 13, anchor_y="center")
                    org_color = (154, 224, 142) if division.organization >= 45 else (236, 198, 90)
                    self.draw_ui_text(f"{division.organization:.0f}", row_rect[0] + row_rect[2] - 50, icon_y + 3, org_color, 12, anchor_x="right", anchor_y="center")
                    self.draw_ui_text("ORG", row_rect[0] + row_rect[2] - 12, icon_y + 3, (150, 166, 184), 9, anchor_x="right", anchor_y="center")

                if max_scroll > 0:
                    track_x = panel_x + panel_width - 8
                    track_y = list_bottom
                    track_h = list_top - list_bottom
                    thumb_h = max(22, track_h * visible_count / len(rows))
                    thumb_y = track_y + (track_h - thumb_h) * (1 - scroll_index / max(1, max_scroll))
                    arcade.draw_lbwh_rectangle_filled(track_x, track_y, 4, track_h, (48, 62, 78, 190))
                    arcade.draw_lbwh_rectangle_filled(track_x, thumb_y, 4, thumb_h, (142, 166, 194, 230))

            current_top = group_y - gap

        self.division_list_icon_shape_list.draw()

    def draw_commander_portrait(self, x, y, size, variant=0):
        palettes = [
            ((116, 91, 68), (214, 182, 145), (36, 42, 34)),
            ((64, 70, 74), (204, 166, 126), (82, 28, 28)),
            ((70, 62, 54), (190, 148, 112), (44, 34, 28)),
        ]
        bg_color, skin_color, uniform_color = palettes[variant % len(palettes)]
        arcade.draw_lbwh_rectangle_filled(x, y, size, size, bg_color)
        arcade.draw_lbwh_rectangle_outline(x, y, size, size, (34, 42, 44), 1)
        center_x = x + size * 0.5
        arcade.draw_circle_filled(center_x, y + size * 0.62, size * 0.20, skin_color)
        arcade.draw_lbwh_rectangle_filled(x + size * 0.28, y + size * 0.12, size * 0.44, size * 0.30, uniform_color)
        arcade.draw_lbwh_rectangle_filled(x + size * 0.30, y + size * 0.74, size * 0.40, size * 0.10, uniform_color)
        arcade.draw_line(center_x - size * 0.07, y + size * 0.64, center_x - size * 0.03, y + size * 0.64, (32, 30, 26), 1)
        arcade.draw_line(center_x + size * 0.03, y + size * 0.64, center_x + size * 0.07, y + size * 0.64, (32, 30, 26), 1)
        arcade.draw_line(center_x - size * 0.06, y + size * 0.54, center_x + size * 0.06, y + size * 0.54, (96, 54, 42), 1)

    def draw_army_command_card(self, x, y, width, height, count_text, variant=0, active=False, is_add=False):
        fill = (34, 45, 37, 238) if active else (24, 31, 38, 235)
        border = (148, 138, 82) if active else (70, 88, 104)
        arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
        arcade.draw_lbwh_rectangle_outline(x, y, width, height, border, 2 if active else 1)
        top_h = 13
        bottom_h = 15
        arcade.draw_lbwh_rectangle_filled(x + 3, y + height - top_h - 3, width - 6, top_h, (18, 24, 27, 235))
        status_colors = [(122, 54, 58), (56, 116, 68), (78, 110, 70)]
        for index, color in enumerate(status_colors):
            box_x = x + 7 + index * 16
            arcade.draw_lbwh_rectangle_filled(box_x, y + height - top_h - 1, 12, 8, color)
            arcade.draw_lbwh_rectangle_outline(box_x, y + height - top_h - 1, 12, 8, (24, 31, 34), 1)

        portrait_x = x + 6
        portrait_y = y + bottom_h + 5
        portrait_size = min(width - 12, height - top_h - bottom_h - 12)
        if is_add:
            arcade.draw_lbwh_rectangle_filled(portrait_x, portrait_y, portrait_size, portrait_size, (34, 42, 48, 230))
            arcade.draw_lbwh_rectangle_outline(portrait_x, portrait_y, portrait_size, portrait_size, (92, 108, 122), 1)
            self.draw_ui_text("+", portrait_x + portrait_size / 2, portrait_y + portrait_size / 2 + 1,
                              (210, 220, 226), 24, anchor_x="center", anchor_y="center")
        else:
            self.draw_commander_portrait(portrait_x, portrait_y, portrait_size, variant)

        arcade.draw_lbwh_rectangle_filled(x + 5, y + 3, width - 10, bottom_h, (12, 17, 19, 235))
        self.draw_ui_text(count_text, x + width / 2, y + bottom_h / 2 + 2,
                          arcade.color.WHITE, 10, anchor_x="center", anchor_y="center")

    def add_divisions_to_army(self, army, divisions):
        if not army or not divisions:
            return []
        current_ids = list(getattr(army, "division_ids", []) or [])
        current_ids = [division_id for division_id in current_ids if self.division_by_id(division_id)]
        existing = set(current_ids)
        added = []
        free_slots = max(0, ARMY_DIVISION_CAPACITY - len(current_ids))
        for division in divisions:
            if free_slots <= 0:
                break
            if division.owner is not army.owner or division.army_id is not None or division.id in existing:
                continue
            division.army_id = army.id
            current_ids.append(division.id)
            existing.add(division.id)
            added.append(division)
            free_slots -= 1
        army.division_ids = current_ids
        return added

    def create_army_from_selected_divisions(self):
        divisions = self.selected_free_divisions()
        if not divisions or not self.human_player:
            return None
        if self.human_player.armies is None:
            self.human_player.armies = []
        army = Army(
            id=self.next_army_id,
            owner=self.human_player,
            name=f"Армия {len(self.human_player.armies) + 1}",
        )
        self.next_army_id += 1
        self.human_player.armies.append(army)
        self.add_divisions_to_army(army, divisions)
        return army

    def toggle_army_plan_execution(self, army):
        if not army:
            return False
        army.executing_plan = not army.executing_plan
        army.plan_update_accumulator = ARMY_PLAN_UPDATE_INTERVAL_HOURS
        return True

    def clear_army_plan(self, army):
        if not army:
            return False
        changed = bool(getattr(army, "battle_plans", []) or army.executing_plan)
        army.battle_plans = []
        army.executing_plan = False
        army.plan_update_accumulator = 0.0
        army.active_front_plan_id = None
        if self.army_plan_army_id == army.id:
            self.cancel_army_plan_mode()
        for division in self.divisions_for_army(army):
            if division.route_mode == "retreat" or division.battle_id:
                continue
            if division.path or division.target_tile or division.route_tiles:
                division.path = []
                division.target_tile = None
                division.route_tiles = []
                division.route_mode = "move"
                division.movement_progress = 0.0
                division.visual_movement_progress = 0.0
                changed = True
        if changed:
            self.invalidate_division_render_cache()
        return changed

    def handle_army_plan_button_click(self, x, y):
        hit = self.army_plan_button_at(x, y)
        if not hit:
            return False
        army = hit["army"]
        action = hit["action"]
        if action == "execute":
            self.toggle_army_plan_execution(army)
        elif action == "clear":
            self.clear_army_plan(army)
        else:
            self.begin_army_plan_mode(army, action)
        return True

    def draw_army_plan_buttons(self, army, card_rect):
        if not army or not card_rect:
            return
        card_x, card_y, card_w, card_h = card_rect
        definitions = self.army_plan_button_definitions()
        button_size = 24
        gap = 4
        total_width = len(definitions) * button_size + (len(definitions) - 1) * gap
        x = card_x + card_w / 2 - total_width / 2
        x = max(8, min(x, self.window.width - total_width - 8))
        y = card_y + card_h + 7
        for action, label, tooltip in definitions:
            rect = (x, y, button_size, button_size)
            active = (
                self.army_plan_mode == action
                and self.army_plan_army_id == army.id
            ) or (action == "execute" and army.executing_plan)
            hovered_army = self.hovered_army_plan_button.get("army") if self.hovered_army_plan_button else None
            hovered = bool(
                self.hovered_army_plan_button
                and hovered_army is army
                and self.hovered_army_plan_button.get("action") == action
            )
            fill = (68, 90, 60, 238) if active else (28, 38, 45, 238)
            if hovered:
                fill = self.blend_colors(fill[:3], (120, 150, 178), 0.35)
            border = (194, 214, 126) if active else (94, 116, 136)
            arcade.draw_lbwh_rectangle_filled(*rect, fill)
            arcade.draw_lbwh_rectangle_outline(*rect, border, 1)
            self.draw_ui_text(label, x + button_size / 2, y + button_size / 2 + 1,
                              arcade.color.WHITE, 12, anchor_x="center", anchor_y="center")
            self.army_plan_button_rects.append((rect, army, action, label, tooltip))
            x += button_size + gap

    def draw_army_command_bar(self):
        rows = self.division_list_rows()
        rect = self.army_command_bar_rect()
        self.army_command_card_rects = []
        self.army_command_add_rect = None
        self.army_plan_button_rects = []
        if not rect:
            return
        armies = self.army_command_items()
        has_free_selection = bool(self.selected_free_divisions())
        if not rows and not armies:
            return
        bar_x, bar_y, bar_width, bar_height = rect
        arcade.draw_lbwh_rectangle_filled(bar_x, bar_y, bar_width, bar_height, (14, 19, 22, 232))
        arcade.draw_lbwh_rectangle_outline(bar_x, bar_y, bar_width, bar_height, (62, 80, 88), 2)

        label_w = 42
        arcade.draw_lbwh_rectangle_filled(bar_x + 5, bar_y + 6, label_w, bar_height - 12, (28, 38, 42, 238))
        arcade.draw_lbwh_rectangle_outline(bar_x + 5, bar_y + 6, label_w, bar_height - 12, (74, 92, 98), 1)
        self.draw_ui_text("ТВД", bar_x + 5 + label_w / 2, bar_y + bar_height - 22,
                          (214, 226, 232), 9, anchor_x="center")
        self.draw_ui_text("1", bar_x + 5 + label_w / 2, bar_y + 24,
                          arcade.color.WHITE, 16, anchor_x="center", anchor_y="center")

        card_x = bar_x + label_w + 11
        card_w = 56
        card_h = bar_height - 10
        gap = 7
        self.army_command_card_rects = []
        current_x = card_x
        active_army = self.active_army_for_plan_controls()
        active_card_rect = None
        for index, army in enumerate(armies):
            if current_x + card_w > bar_x + bar_width - 6:
                break
            army_divisions = self.divisions_for_army(army)
            active = any(division.id in self.selected_division_ids for division in army_divisions)
            self.draw_army_command_card(
                current_x,
                bar_y + 5,
                card_w,
                card_h,
                f"{len(army_divisions)}/{ARMY_DIVISION_CAPACITY}",
                variant=index,
                active=active,
            )
            card_rect = (current_x, bar_y + 5, card_w, card_h)
            self.army_command_card_rects.append((card_rect, army))
            if active_army and army.id == active_army.id:
                active_card_rect = card_rect
            current_x += card_w + gap

        add_x = current_x
        if add_x + card_w <= bar_x + bar_width - 6:
            self.draw_army_command_card(
                add_x,
                bar_y + 5,
                card_w,
                card_h,
                "",
                active=has_free_selection,
                is_add=True,
            )
            self.army_command_add_rect = (add_x, bar_y + 5, card_w, card_h)
        else:
            self.army_command_add_rect = None

        if active_army and active_card_rect:
            self.draw_army_plan_buttons(active_army, active_card_rect)

    def handle_division_list_click(self, x, y, modifiers):
        if not self.division_list_panel_rect or not self.point_in_rect(x, y, self.division_list_panel_rect):
            return False
        for close_rect, group_key in self.division_list_close_rects:
            if self.point_in_rect(x, y, close_rect):
                self.deselect_division_group(group_key)
                return True
        if self.division_detach_button_rect and self.point_in_rect(x, y, self.division_detach_button_rect):
            self.detach_selected_divisions_from_army()
            return True
        for header_rect, group_key in self.division_list_header_rects:
            if self.point_in_rect(x, y, header_rect):
                self.active_division_list_army_id = group_key
                return True
        for rect, division in self.division_list_row_rects:
            if self.point_in_rect(x, y, rect):
                self.set_selected_divisions([division], additive=True, toggle=True)
                return True
        return True

    def handle_division_list_right_click(self, x, y):
        if not self.division_list_panel_rect or not self.point_in_rect(x, y, self.division_list_panel_rect):
            return False
        for rect, division in self.division_list_row_rects:
            if self.point_in_rect(x, y, rect):
                division.selected = False
                self.selected_division_ids.discard(division.id)
                if not self.selected_division_ids:
                    self.division_list_scroll_index = 0
                    self.active_division_list_army_id = None
                self.invalidate_division_render_cache()
                return True
        return True

    def deselect_division_group(self, group_key):
        if group_key == "free":
            divisions = self.selected_free_divisions()
        else:
            army = self.army_by_id(group_key)
            divisions = self.divisions_for_army(army) if army else []
        changed = False
        for division in divisions:
            if division.id in self.selected_division_ids:
                self.selected_division_ids.discard(division.id)
                division.selected = False
                changed = True
        if changed:
            if self.active_division_list_army_id == group_key:
                self.active_division_list_army_id = None
            if not self.selected_division_ids:
                self.division_list_scroll_index = 0
            self.invalidate_division_render_cache()
        return changed

    def detach_selected_divisions_from_army(self):
        selected = self.selected_divisions()
        if not selected or not self.human_player:
            return False
        changed = False
        armies = getattr(self.human_player, "armies", []) or []
        for division in selected:
            if division.army_id is None:
                continue
            for army in armies:
                if army.id == division.army_id:
                    army.division_ids = [
                        division_id for division_id in (army.division_ids or [])
                        if division_id != division.id
                    ]
                    break
            division.army_id = None
            changed = True
        if changed:
            self.invalidate_division_render_cache()
        return changed

    def toggle_army_division_selection(self, army):
        divisions = self.divisions_for_army(army)
        if not divisions:
            return False
        all_selected = all(division.id in self.selected_division_ids for division in divisions)
        for division in divisions:
            if all_selected:
                division.selected = False
                self.selected_division_ids.discard(division.id)
            else:
                division.selected = True
                self.selected_division_ids.add(division.id)
        if not self.selected_division_ids:
            self.active_division_list_army_id = None
            self.division_list_scroll_index = 0
        else:
            self.active_division_list_army_id = army.id
        self.invalidate_division_render_cache()
        return True

    def handle_army_command_bar_click(self, x, y, activate=True, modifiers=0):
        rect = self.army_command_bar_rect()
        if not rect or not self.point_in_rect(x, y, rect):
            return False
        if not activate:
            return True

        if self.army_command_add_rect and self.point_in_rect(x, y, self.army_command_add_rect):
            army = self.create_army_from_selected_divisions()
            if army:
                self.set_selected_divisions(self.divisions_for_army(army))
            return True

        for card_rect, army in self.army_command_card_rects:
            if not self.point_in_rect(x, y, card_rect):
                continue
            if self.shift_modifier_active(modifiers):
                self.toggle_army_division_selection(army)
                return True
            free_divisions = self.selected_free_divisions()
            if free_divisions:
                self.add_divisions_to_army(army, free_divisions)
            self.set_selected_divisions(self.divisions_for_army(army))
            return True

        return True

    def scroll_division_list(self, amount):
        groups = self.division_list_groups()
        rect = self.division_list_rect()
        if not groups or not rect:
            return False
        active_group = next(
            (group for group in groups if group["key"] == self.active_division_list_army_id),
            groups[0],
        )
        rows = active_group["rows"]
        active_rect = next(
            (panel_rect for panel_rect, group_key in zip(self.division_list_panel_rects, [group["key"] for group in groups]) if group_key == active_group["key"]),
            None,
        )
        if not rows or not active_rect:
            return False
        _panel_x, panel_y, _panel_width, panel_height = active_rect
        visible_count = max(1, int((panel_y + panel_height - 86 - (panel_y + 10)) / 40))
        max_scroll = max(0, len(rows) - visible_count)
        key = active_group["key"]
        old_index = self.division_list_scroll_indices.get(key, self.division_list_scroll_index)
        new_index = max(0, min(max_scroll, old_index + int(amount)))
        self.division_list_scroll_indices[key] = new_index
        self.division_list_scroll_index = new_index
        return new_index != old_index

    def division_at_screen(self, x, y):
        if self.use_division_lod():
            self.rebuild_division_groups()
            for group in reversed(self.division_groups):
                if self.point_in_rect(x, y, group["rect"]):
                    return group
            return None

        best = None
        best_distance = float("inf")
        radius = DIVISION_ICON_SIZE * 1.05
        self.update_division_display_positions()
        for stack in self.visible_division_tile_stacks():
            division = stack[0]
            if division.owner != self.human_player:
                continue
            screen_x, screen_y = self.division_screen_position(division)
            distance = math.hypot(screen_x - x, screen_y - y)
            if distance <= radius and distance < best_distance:
                best = {"rect": (screen_x - radius, screen_y - radius, radius * 2, radius * 2), "divisions": stack} if len(stack) > 1 else division
                best_distance = distance
        return best

    def handle_division_click(self, x, y, modifiers):
        hit = self.division_at_screen(x, y)
        if not hit:
            return False

        shift = self.shift_modifier_active(modifiers)
        now = time.time()
        if isinstance(hit, dict):
            self.set_selected_divisions(hit["divisions"], additive=shift, toggle=shift)
            self.close_hex_panel()
            return True

        is_double = (
            self.last_division_click_id == hit.id
            and now - self.last_division_click_time <= DIVISION_DOUBLE_CLICK_SECONDS
        )
        self.last_division_click_time = now
        self.last_division_click_id = hit.id

        if is_double and not shift:
            template_key = hit.template_key
            divisions = [
                division
                for division in self.visible_divisions()
                if division.owner == self.human_player and division.template_key == template_key
            ]
            self.set_selected_divisions(divisions)
        else:
            self.set_selected_divisions([hit], additive=shift, toggle=shift)
        self.close_hex_panel()
        return True

    def handle_battle_ui_click(self, x, y):
        if self.selected_battle_id and self.battle_panel_rect and self.point_in_rect(x, y, self.battle_panel_rect):
            if self.battle_panel_close_rect and self.point_in_rect(x, y, self.battle_panel_close_rect):
                self.selected_battle_id = None
                self.battle_panel_rect = None
                self.battle_panel_close_rect = None
            return True
        for rect, battle_id in self.battle_indicator_rects:
            if self.point_in_rect(x, y, rect):
                self.selected_battle_id = battle_id
                return True
        return False

    def screen_rect_contains_point(self, rect, x, y):
        left, bottom, right, top = rect
        return left <= x <= right and bottom <= y <= top

    def select_divisions_in_screen_rect(self, start, end, modifiers):
        x1, y1 = start
        x2, y2 = end
        rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        shift = self.shift_modifier_active(modifiers)
        selected = []
        if self.use_division_lod():
            for group in self.division_groups:
                gx, gy, gw, gh = group["rect"]
                center_x = gx + gw / 2
                center_y = gy + gh / 2
                if self.screen_rect_contains_point(rect, center_x, center_y):
                    selected.extend(group["divisions"])
        else:
            self.update_division_display_positions()
            for division in self.visible_divisions():
                if division.owner != self.human_player:
                    continue
                screen_x, screen_y = self.division_screen_position(division)
                if self.screen_rect_contains_point(rect, screen_x, screen_y):
                    selected.append(division)
        self.set_selected_divisions(selected, additive=shift, toggle=shift)
        if selected:
            self.close_hex_panel()
        return bool(selected)

    def map_layer_option_at(self, x, y):
        if self.map_layer_menu_progress < 0.8:
            return None

        for index, rect in enumerate(self.map_layer_option_rects()):
            if self.point_in_rect(x, y, rect):
                return index
        return None

    def resource_group_option_at(self, x, y):
        if self.map_layer != "resources" or self.resource_group_menu_progress < 0.8:
            return None

        for index, rect in enumerate(self.resource_group_option_rects()):
            if self.point_in_rect(x, y, rect):
                return index
        return None

    def handle_map_layer_control_click(self, x, y):
        if self.map_layer == "resources":
            resource_option_index = self.resource_group_option_at(x, y)
            if resource_option_index is not None:
                self.set_resource_group(resource_option_index)
                return True

            if self.point_in_rect(x, y, self.resource_group_button_rect()):
                self.resource_group_menu_open = not self.resource_group_menu_open
                self.map_layer_menu_open = False
                return True

        option_index = self.map_layer_option_at(x, y)
        if option_index is not None:
            layer_key, _label, enabled = MAP_LAYERS[option_index]
            if enabled:
                self.set_map_layer(layer_key)
            else:
                self.set_map_layer("weather")
            return True

        if self.point_in_rect(x, y, self.map_layer_button_rect()):
            self.map_layer_menu_open = not self.map_layer_menu_open
            self.resource_group_menu_open = False
            return True

        if self.map_layer_menu_open or self.resource_group_menu_open:
            self.map_layer_menu_open = False
            self.resource_group_menu_open = False
            return True

        return False

    def set_resource_group(self, index):
        self.resource_group_index = max(0, min(len(RESOURCE_MAP_GROUPS) - 1, index))
        self.resource_group_menu_open = False
        self.hovered_resource_group_option = None
        self.create_map_overview()
        self.refresh_visible_tiles()

    def set_map_layer(self, layer_key):
        if layer_key == "weather":
            self.map_layer_message = "Погодный слой будет добавлен позже"
            self.map_layer_message_timer = 2.0
            return

        if self.map_layer == layer_key:
            self.map_layer_menu_open = False
            return

        self.map_layer = layer_key
        self.map_layer_menu_open = False
        self.hovered_map_layer_option = None
        if layer_key != "resources":
            self.resource_group_menu_open = False
            self.hovered_resource_group_button = False
            self.hovered_resource_group_option = None
        self.map_layer_message = ""
        self.map_layer_message_timer = 0.0
        self.create_map_overview()
        self.refresh_visible_tiles()

    def update_map_layer_menu_animation(self, delta_time):
        target = 1.0 if self.map_layer_menu_open else 0.0
        speed = min(1.0, delta_time * 10)
        self.map_layer_menu_progress += (target - self.map_layer_menu_progress) * speed
        if abs(self.map_layer_menu_progress - target) < 0.01:
            self.map_layer_menu_progress = target

        resource_target = 1.0 if self.resource_group_menu_open and self.map_layer == "resources" else 0.0
        self.resource_group_menu_progress += (resource_target - self.resource_group_menu_progress) * speed
        if abs(self.resource_group_menu_progress - resource_target) < 0.01:
            self.resource_group_menu_progress = resource_target

        if self.map_layer_message_timer > 0:
            self.map_layer_message_timer = max(0.0, self.map_layer_message_timer - delta_time)
            if self.map_layer_message_timer == 0:
                self.map_layer_message = ""

    def draw_map_layer_control(self):
        if self.map_layer_menu_progress > 0.01:
            alpha = int(235 * self.map_layer_menu_progress)
            for index, (layer_key, label, enabled) in enumerate(MAP_LAYERS):
                x, y, width, height = self.map_layer_option_rects()[index]
                active = layer_key == self.map_layer
                hovered = index == self.hovered_map_layer_option
                if not enabled:
                    fill = (38, 43, 49, alpha)
                    border = (88, 94, 102, alpha)
                    text_color = (128, 136, 145, alpha)
                elif active:
                    fill = (58, 92, 128, alpha)
                    border = (120, 210, 255, alpha)
                    text_color = (238, 248, 255, alpha)
                elif hovered:
                    fill = (50, 64, 82, alpha)
                    border = (150, 178, 210, alpha)
                    text_color = (232, 238, 245, alpha)
                else:
                    fill = (24, 32, 42, alpha)
                    border = (92, 112, 136, alpha)
                    text_color = (210, 220, 232, alpha)

                arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
                arcade.draw_lbwh_rectangle_outline(x, y, width, height, border, 1)
                self.draw_ui_text(label, x + 14, y + height / 2, text_color, 13, anchor_y="center")

        if self.map_layer == "resources":
            if self.resource_group_menu_progress > 0.01:
                alpha = int(235 * self.resource_group_menu_progress)
                for index, (_key, label, _resources, color, _scale) in enumerate(RESOURCE_MAP_GROUPS):
                    x, y, width, height = self.resource_group_option_rects()[index]
                    active = index == self.resource_group_index
                    hovered = index == self.hovered_resource_group_option
                    if active:
                        fill = (58, 92, 128, alpha)
                        border = (120, 210, 255, alpha)
                    elif hovered:
                        fill = (50, 64, 82, alpha)
                        border = (150, 178, 210, alpha)
                    else:
                        fill = (24, 32, 42, alpha)
                        border = (92, 112, 136, alpha)

                    arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
                    arcade.draw_lbwh_rectangle_outline(x, y, width, height, border, 1)
                    arcade.draw_lbwh_rectangle_filled(x + 10, y + 10, 14, 14, (*color, alpha))
                    self.draw_ui_text(label, x + 32, y + height / 2, (220, 230, 240, alpha), 11, anchor_y="center")

            group_key, group_label, _resources, group_color, _scale = RESOURCE_MAP_GROUPS[self.resource_group_index]
            group_x, group_y, group_width, group_height = self.resource_group_button_rect()
            group_fill = (
                (58, 82, 108)
                if self.hovered_resource_group_button or self.resource_group_menu_open
                else (30, 40, 52)
            )
            arcade.draw_lbwh_rectangle_filled(group_x, group_y, group_width, group_height, group_fill)
            arcade.draw_lbwh_rectangle_outline(group_x, group_y, group_width, group_height, (140, 170, 205), 2)
            arcade.draw_lbwh_rectangle_filled(group_x + 11, group_y + 15, 14, 14, group_color)
            self.draw_ui_text(group_label, group_x + 34, group_y + group_height / 2, arcade.color.WHITE, 11,
                              anchor_y="center")

        button_x, button_y, button_width, button_height = self.map_layer_button_rect()
        button_fill = (58, 82, 108) if self.hovered_map_layer_button or self.map_layer_menu_open else (30, 40, 52)
        arcade.draw_lbwh_rectangle_filled(button_x, button_y, button_width, button_height, button_fill)
        arcade.draw_lbwh_rectangle_outline(button_x, button_y, button_width, button_height, (140, 170, 205), 2)
        arcade.draw_texture_rect(
            self.map_layer_icon_texture,
            arcade.rect.XYWH(button_x + button_width / 2, button_y + button_height / 2, 30, 30),
        )

        if self.map_layer_message:
            self.draw_ui_text(
                self.map_layer_message,
                button_x - 246,
                button_y + button_height / 2,
                (240, 205, 110),
                13,
                anchor_y="center",
            )

    def draw_pause_menu(self):
        arcade.draw_lbwh_rectangle_filled(0, 0, self.window.width, self.window.height, (0, 0, 0, 185))
        panel_width = 420 if self.pause_screen == "menu" else 540
        panel_height = 440 if self.pause_screen == "menu" else 460
        panel_x = self.window.width / 2 - panel_width / 2
        panel_y = self.window.height / 2 - panel_height / 2
        arcade.draw_lbwh_rectangle_filled(panel_x, panel_y, panel_width, panel_height, (20, 29, 38))
        arcade.draw_lbwh_rectangle_outline(panel_x, panel_y, panel_width, panel_height, (100, 126, 155), 2)
        self.draw_ui_text(
            "Настройки" if self.pause_screen == "settings" else "Пауза",
            self.window.width / 2,
            panel_y + panel_height - 45,
            arcade.color.WHITE,
            32,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )

        if self.pause_screen == "settings":
            self.draw_pause_settings()
            return

        for button in self.pause_buttons:
            button.draw(button == self.hovered_pause_button)

        if self.pause_message:
            self.draw_ui_text(
                self.pause_message,
                self.window.width / 2,
                panel_y + 24,
                (220, 180, 90),
                15,
                anchor_x="center",
                anchor_y="center",
            )

    def draw_pause_settings(self):
        for slider in self.pause_sliders:
            slider.draw()

        for button in self.pause_buttons:
            button.draw(button == self.hovered_pause_button)

        for dropdown in self.pause_dropdowns:
            if dropdown.key != self.open_pause_dropdown:
                dropdown.draw(False)
        for dropdown in self.pause_dropdowns:
            if dropdown.key == self.open_pause_dropdown:
                dropdown.draw(True)

        if self.pause_message:
            self.draw_ui_text(
                self.pause_message,
                self.window.width / 2,
                self.window.height / 2 - 185,
                (220, 180, 90),
                15,
                anchor_x="center",
                anchor_y="center",
            )

    def draw_gui(self):
        pass

    def on_resize(self, width, height):
        super().on_resize(width, height)
        self.sync_cameras_to_window()
        self.world_camera.position = self.clamp_camera_position(*self.world_camera.position)
        self.target_camera_x, self.target_camera_y = self.world_camera.position
        self.rebuild_pause_menu()
        self.rebuild_time_hud()
        self.rebuild_top_ui()
        self.refresh_visible_tiles()

    def toggle_time_pause(self):
        self.simulation_client.request_toggle_pause()

    def increase_time_speed(self):
        self.simulation_client.request_speed_change(1)

    def decrease_time_speed(self):
        self.simulation_client.request_speed_change(-1)

    def open_pause_settings(self):
        self.pause_screen = "settings"
        if not self.fullscreen:
            self.resolution_index = self.get_current_resolution_index()
        self.pending_fullscreen = self.fullscreen
        self.pending_resolution_index = self.resolution_index
        self.pause_message = ""
        self.hovered_pause_button = None
        self.open_pause_dropdown = None
        self.rebuild_pause_menu()

    def close_pause_settings(self):
        self.pause_screen = "menu"
        self.pause_message = ""
        self.hovered_pause_button = None
        self.active_pause_slider = None
        self.open_pause_dropdown = None
        self.rebuild_pause_menu()

    def set_sound_volume(self, value):
        self.sound_volume = value

    def set_music_volume(self, value):
        self.music_volume = value

    def toggle_pending_fullscreen(self):
        self.pending_fullscreen = not self.pending_fullscreen
        self.rebuild_pause_menu()

    def set_pending_resolution(self, index):
        self.pending_resolution_index = index
        self.rebuild_pause_menu()

    def apply_pause_settings(self):
        self.fullscreen = self.pending_fullscreen
        self.resolution_index = self.pending_resolution_index
        width, height = RESOLUTIONS[self.resolution_index]
        self.fullscreen, error = apply_window_settings_safely(self.window, width, height, self.fullscreen)
        save_settings(self.sound_volume, self.music_volume, self.fullscreen, self.resolution_index, RESOLUTIONS)
        self.sync_cameras_to_window()
        self.pause_message = "Полный экран не применен, включен оконный режим." if error else "Настройки применены."
        self.rebuild_pause_menu()
        self.rebuild_time_hud()
        self.refresh_visible_tiles()

    def toggle_pause_menu(self):
        self.paused = not self.paused
        self.pause_message = ""
        self.hovered_pause_button = None
        self.active_pause_slider = None
        self.open_pause_dropdown = None
        self.hovered_tile = None
        if self.paused:
            self.pause_screen = "menu"
            self.rebuild_pause_menu()
        self.is_dragging = False
        self.keys_pressed.clear()

    def resume_game(self):
        self.paused = False
        self.pause_screen = "menu"
        self.pause_message = ""
        self.hovered_pause_button = None
        self.active_pause_slider = None
        self.open_pause_dropdown = None

    def save_game(self):
        self.pause_message = "Сохранение пока не реализовано."

    def load_game(self):
        self.pause_message = "Загрузка пока не реализована."

    def exit_to_main_menu(self):
        from MainMenu import MainMenuView

        self.window.show_view(MainMenuView())

    def exit_to_desktop(self):
        arcade.exit()

    def apply_tile_draw_color(self, tile):
        base_color = self.get_tile_map_color(tile)
        if tile == self.selected_tile:
            tile.color = self.blend_colors(base_color, (255, 255, 80), 0.22)
        elif tile == self.hovered_tile:
            tile.color = (
                min(255, base_color[0] + 50),
                min(255, base_color[1] + 50),
                min(255, base_color[2] + 50),
            )
        else:
            tile.color = base_color

    def update_draw_list(self):
        """Обновление списка отрисовки"""
        self.rebuild_selected_resource_signal_cache()
        self.rebuild_construction_placement_cache()
        for tile in self.visible_tiles:
            base_color = self.get_tile_map_color(tile)
            if tile == self.selected_tile:
                # Желтая подсветка
                tile.color = self.blend_colors(base_color, (255, 255, 80), 0.22)
            elif tile == self.hovered_tile:
                # Белая подсветка (чуть светлее)
                tile.color = (
                    min(255, base_color[0] + 50),
                    min(255, base_color[1] + 50),
                    min(255, base_color[2] + 50)
                )
            else:
                tile.color = base_color

    def on_update(self, delta_time):
        self.shader_time += delta_time
        self.update_map_layer_menu_animation(delta_time)
        self.update_side_panel_animation(delta_time)
        if self.hex_panel_message_timer > 0:
            self.hex_panel_message_timer = max(0.0, self.hex_panel_message_timer - delta_time)
            if self.hex_panel_message_timer == 0:
                self.hex_panel_message = ""

        if self.paused or self.game_over:
            return

        self.update_division_visual_motion(delta_time)
        self.fps_frame_count += 1
        self.fps_timer += delta_time
        if self.fps_timer >= 0.5:
            self.fps = self.fps_frame_count / self.fps_timer
            self.fps_frame_count = 0
            self.fps_timer = 0

        previous_tick_count = self.simulation_client.snapshot.tick_count
        self.simulation_server.update(delta_time)
        self.simulation_client.sync_from_server()
        snapshot = self.simulation_client.snapshot
        tick_delta = max(0, snapshot.tick_count - previous_tick_count)
        if tick_delta > 0:
            elapsed_hours = snapshot.hours_per_tick * tick_delta
            market_ticks = self.simulation_server.consume_market_ticks()
            for _market_index in range(market_ticks):
                self.run_weekly_market_tick()
            for player in self.players:
                self.run_economy_tick(player, elapsed_hours)
                self.run_production_tick(player, elapsed_hours)
                self.run_construction_tick(player, elapsed_hours)
                self.run_population_tick(player, elapsed_hours)
            self.update_divisions(elapsed_hours)
            self.update_battles(elapsed_hours)
            self.update_army_plans(elapsed_hours)
            self.update_economy_month_history(snapshot.current_time)
            self.last_production_tick_count = snapshot.tick_count

        self.process_ownership_refresh()
        self.handle_camera_keys(delta_time)
        self.clamp_target_camera()

        camera_x, camera_y = arcade.math.lerp_2d(
            self.world_camera.position,
            (self.target_camera_x, self.target_camera_y),
            CAMERA_LERP,
        )
        self.world_camera.position = self.clamp_camera_position(camera_x, camera_y)

        current_time = time.time()
        if current_time - self.last_visible_update > self.visible_update_interval:
            if self.use_overview_lod():
                self.visible_tiles.clear()
                self.refresh_visible_tiles_signature()
            else:
                self.get_visible_tiles()
                self.refresh_visible_tiles_signature()
                self.update_draw_list()
            self.last_visible_update = current_time

    def handle_camera_keys(self, delta_time):
        move_distance = MOVE_SPEED * 60 * delta_time
        if arcade.key.LEFT in self.keys_pressed:
            self.target_camera_x -= move_distance
        if arcade.key.RIGHT in self.keys_pressed:
            self.target_camera_x += move_distance
        if arcade.key.UP in self.keys_pressed:
            self.target_camera_y += move_distance
        if arcade.key.DOWN in self.keys_pressed:
            self.target_camera_y -= move_distance

    def on_mouse_press(self, x, y, button, modifiers):
        if self.paused:
            if button == arcade.MOUSE_BUTTON_LEFT:
                if self.pause_screen == "settings":
                    for dropdown in self.pause_dropdowns:
                        if dropdown.key == self.open_pause_dropdown:
                            option_index = dropdown.option_at(x, y)
                            if option_index is not None:
                                self.open_pause_dropdown = None
                                dropdown.hovered_index = None
                                dropdown.on_select(option_index)
                                return

                    for dropdown in self.pause_dropdowns:
                        if dropdown.contains_header(x, y):
                            self.open_pause_dropdown = None if self.open_pause_dropdown == dropdown.key else dropdown.key
                            dropdown.hovered_index = None
                            return

                    for slider in self.pause_sliders:
                        if slider.contains(x, y):
                            self.active_pause_slider = slider
                            slider.set_from_mouse(x)
                            return

                    self.open_pause_dropdown = None
                    for dropdown in self.pause_dropdowns:
                        dropdown.hovered_index = None

                for pause_button in self.pause_buttons:
                    if pause_button.contains(x, y):
                        pause_button.action()
                        return
            return

        world_x, world_y = self.screen_to_world(x, y)
        if button == arcade.MOUSE_BUTTON_LEFT:
            if self.side_panel_progress > 0:
                if self.point_in_rect(x, y, self.side_panel_close_rect()):
                    self.close_top_panel()
                    return
                if self.point_in_rect(x, y, self.side_panel_rect()):
                    if self.active_top_panel_key == "resources":
                        self.handle_resources_panel_click(x, y)
                    elif self.active_top_panel_key == "trade":
                        self.handle_trade_panel_click(x, y, modifiers)
                    elif self.active_top_panel_key == "construction":
                        self.handle_construction_panel_click(x, y)
                    return

            if self.handle_map_layer_control_click(x, y):
                return

            if self.handle_army_plan_button_click(x, y):
                return

            if self.handle_division_list_click(x, y, modifiers):
                return

            if self.handle_army_command_bar_click(x, y, modifiers=modifiers):
                return

            if self.handle_battle_ui_click(x, y):
                return

            if self.selected_tile and self.point_in_rect(x, y, self.hex_panel_rect()):
                if self.point_in_rect(x, y, self.hex_panel_close_rect()):
                    self.close_hex_panel()
                    return
                if self.hex_resources_toggle_rect and self.point_in_rect(x, y, self.hex_resources_toggle_rect):
                    self.toggle_hex_resources_expanded()
                    return
                if self.selected_tile_has_industry() and self.point_in_rect(x, y, self.hex_panel_specialization_button_rect()):
                    self.toggle_hex_specialization_mode()
                    return
                if self.hex_panel_specialization_mode:
                    for rect, sector in self.hex_specialization_row_rects:
                        if self.point_in_rect(x, y, rect):
                            self.set_selected_tile_industry_sector(sector)
                            return
                if self.point_in_rect(x, y, self.hex_panel_build_button_rect()):
                    self.open_top_panel("construction")
                    return
                return

            warning_key = self.warning_icon_at(x, y)
            if warning_key:
                if warning_key in ("resources", "storage"):
                    self.open_top_panel("resources")
                elif warning_key == "supply":
                    self.set_map_layer("supply")
                    self.open_top_panel("resources")
                elif warning_key == "trade":
                    self.open_top_panel("trade")
                elif warning_key == "construction":
                    self.open_top_panel("construction")
                return

            top_button = self.top_nav_button_at(x, y)
            if top_button:
                if self.active_top_panel_key == top_button["key"] and self.side_panel_target > 0:
                    self.close_top_panel()
                else:
                    self.open_top_panel(top_button["key"])
                return

            if y >= self.window.height - TOP_UI_HEIGHT:
                return

            for time_button in self.time_buttons:
                if time_button.contains(x, y):
                    time_button.action()
                    return

            if self.army_plan_mode and self.handle_army_plan_map_press(x, y):
                return

            if self.construction_placement_mode and self.active_top_panel_key == "construction":
                tile = self.get_tile_at(world_x, world_y)
                building_key = self.selected_construction_building_key()
                if tile and self.can_place_construction(self.human_player, tile, building_key):
                    steps = 1
                    if self.shift_modifier_active(modifiers):
                        steps = max(1, round(0.25 / CONSTRUCTION_STEP))
                    self.enqueue_construction_steps(self.human_player, tile, building_key, steps)
                    return
                return

            if self.handle_division_click(x, y, modifiers):
                return

            self.division_selection_drag_active = True
            self.division_selection_drag_started = False
            self.division_selection_start = (x, y)
            self.division_selection_current = (x, y)
            self.pending_map_click = (world_x, world_y, modifiers)
            return

        if button in (arcade.MOUSE_BUTTON_RIGHT, arcade.MOUSE_BUTTON_MIDDLE):
            if button == arcade.MOUSE_BUTTON_RIGHT:
                if self.selected_battle_id and self.battle_panel_rect and self.point_in_rect(x, y, self.battle_panel_rect):
                    return
                if self.handle_division_list_right_click(x, y):
                    return
                if self.handle_army_command_bar_click(x, y, activate=False, modifiers=modifiers):
                    return

            if (
                button == arcade.MOUSE_BUTTON_RIGHT
                and self.construction_placement_mode
                and self.active_top_panel_key == "construction"
            ):
                if y >= self.window.height - TOP_UI_HEIGHT:
                    return
                if self.side_panel_progress > 0 and self.point_in_rect(x, y, self.side_panel_rect()):
                    return
                if self.selected_tile and self.point_in_rect(x, y, self.hex_panel_rect()):
                    return
                tile = self.get_tile_at(world_x, world_y)
                building_key = self.selected_construction_building_key()
                if button == arcade.MOUSE_BUTTON_RIGHT and tile and self.has_cancelable_construction(
                    self.human_player,
                    tile,
                    building_key,
                ):
                    self.cancel_queued_construction(self.human_player, tile, building_key)
                    return

            if button == arcade.MOUSE_BUTTON_RIGHT and self.selected_divisions():
                if y >= self.window.height - TOP_UI_HEIGHT:
                    return
                if self.side_panel_progress > 0 and self.point_in_rect(x, y, self.side_panel_rect()):
                    return
                if self.selected_tile and self.point_in_rect(x, y, self.hex_panel_rect()):
                    return
                target_tile = self.get_tile_at(world_x, world_y)
                if target_tile and self.cancel_selected_division_orders_on_tile(target_tile):
                    return
                append_order = self.shift_modifier_active(modifiers)
                if target_tile and self.order_selected_divisions_to_tile(target_tile, append=append_order):
                    return

            self.is_dragging = True
            self.drag_start_x = x
            self.drag_start_y = y
            self.drag_start_camera_x, self.drag_start_camera_y = self.target_camera_x, self.target_camera_y
        elif button == arcade.MOUSE_BUTTON_LEFT:
            tile = self.get_tile_at(world_x, world_y)
            if self.shift_modifier_active(modifiers):
                self.toggle_tile_multi_selection(tile)
            elif tile:
                self.set_single_selected_tile(tile)
            else:
                self.close_hex_panel()

    def on_mouse_release(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.active_pause_slider = None
            if self.handle_army_plan_map_release(x, y):
                return
            if self.division_selection_drag_active:
                if self.division_selection_drag_started:
                    self.select_divisions_in_screen_rect(self.division_selection_start, (x, y), modifiers)
                elif self.pending_map_click:
                    world_x, world_y, click_modifiers = self.pending_map_click
                    tile = self.get_tile_at(world_x, world_y)
                    if self.shift_modifier_active(click_modifiers):
                        self.toggle_tile_multi_selection(tile)
                    elif tile:
                        self.set_single_selected_tile(tile)
                    else:
                        self.close_hex_panel()
                self.division_selection_drag_active = False
                self.division_selection_drag_started = False
                self.pending_map_click = None
        if button in (arcade.MOUSE_BUTTON_RIGHT, arcade.MOUSE_BUTTON_MIDDLE):
            self.is_dragging = False

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.paused:
            if self.active_pause_slider and buttons & arcade.MOUSE_BUTTON_LEFT:
                self.active_pause_slider.set_from_mouse(x)
            return

        if self.division_selection_drag_active and buttons & arcade.MOUSE_BUTTON_LEFT:
            self.division_selection_current = (x, y)
            start_x, start_y = self.division_selection_start
            if math.hypot(x - start_x, y - start_y) >= DIVISION_SELECTION_DRAG_THRESHOLD:
                self.division_selection_drag_started = True
            return

        if self.army_plan_drag_active and buttons & arcade.MOUSE_BUTTON_LEFT:
            self.handle_army_plan_map_drag(x, y)
            return

        if self.is_dragging and (
            arcade.MOUSE_BUTTON_RIGHT & buttons
            or arcade.MOUSE_BUTTON_MIDDLE & buttons
        ):
            self.target_camera_x = self.drag_start_camera_x - (x - self.drag_start_x) / self.world_camera.zoom
            self.target_camera_y = self.drag_start_camera_y - (y - self.drag_start_y) / self.world_camera.zoom
            self.clamp_target_camera()

    def on_mouse_motion(self, x, y, dx, dy):
        if self.paused:
            self.hovered_tile = None
            self.hovered_hex_panel_close = False
            self.hovered_hex_build_button = False
            self.hovered_hex_specialization_button = False
            self.hovered_population_summary = False
            self.hovered_budget_summary = False
            self.hovered_resource_summary = False
            self.hovered_division_detach_button = False
            self.hovered_army_plan_button = None
            if self.pause_screen == "settings" and self.open_pause_dropdown:
                for dropdown in self.pause_dropdowns:
                    if dropdown.key == self.open_pause_dropdown:
                        dropdown.hovered_index = dropdown.option_at(x, y)
                        break
                return

            self.hovered_pause_button = None
            for pause_button in self.pause_buttons:
                if pause_button.contains(x, y):
                    self.hovered_pause_button = pause_button
                    break
            return

        self.hovered_budget_summary = (
            self.budget_summary_rect is not None
            and self.point_in_rect(x, y, self.budget_summary_rect)
        )
        self.hovered_population_summary = (
            self.population_summary_rect is not None
            and self.point_in_rect(x, y, self.population_summary_rect)
        )
        self.hovered_resource_summary = (
            self.resource_summary_rect is not None
            and self.point_in_rect(x, y, self.resource_summary_rect)
        )
        self.hovered_division_detach_button = (
            self.division_detach_button_rect is not None
            and self.point_in_rect(x, y, self.division_detach_button_rect)
        )
        self.hovered_army_plan_button = self.army_plan_button_at(x, y)
        self.hovered_warning_key = self.warning_icon_at(x, y)
        top_button = self.top_nav_button_at(x, y)
        self.hovered_top_nav_key = top_button["key"] if top_button else None
        self.hovered_side_panel_close = (
            self.side_panel_progress > 0 and self.point_in_rect(x, y, self.side_panel_close_rect())
        )
        over_hex_panel = self.selected_tile and self.point_in_rect(x, y, self.hex_panel_rect())
        self.hovered_hex_panel_close = (
            bool(over_hex_panel) and self.point_in_rect(x, y, self.hex_panel_close_rect())
        )
        self.hovered_hex_build_button = (
            bool(over_hex_panel) and self.point_in_rect(x, y, self.hex_panel_build_button_rect())
        )
        self.hovered_hex_specialization_button = (
            bool(over_hex_panel)
            and self.selected_tile_has_industry()
            and self.point_in_rect(x, y, self.hex_panel_specialization_button_rect())
        )
        over_division_list = (
            self.division_list_panel_rect is not None
            and self.point_in_rect(x, y, self.division_list_panel_rect)
        )
        over_army_command_bar = (
            self.army_command_bar_rect() is not None
            and self.point_in_rect(x, y, self.army_command_bar_rect())
        )
        over_army_plan_button = self.hovered_army_plan_button is not None
        if (
            self.hovered_top_nav_key
            or self.hovered_warning_key
            or self.hovered_side_panel_close
            or over_division_list
            or over_army_command_bar
            or over_army_plan_button
            or over_hex_panel
            or y >= self.window.height - TOP_UI_HEIGHT
            or (self.side_panel_progress > 0 and self.point_in_rect(x, y, self.side_panel_rect()))
        ):
            self.hovered_map_layer_button = False
            self.hovered_map_layer_option = None
            self.hovered_resource_group_button = False
            self.hovered_resource_group_option = None
            self.hovered_time_button = None
            self.hovered_tile = None
            return

        self.hovered_resource_group_button = False
        self.hovered_resource_group_option = None
        if self.map_layer == "resources":
            self.hovered_resource_group_button = self.point_in_rect(x, y, self.resource_group_button_rect())
            self.hovered_resource_group_option = self.resource_group_option_at(x, y)
            if self.hovered_resource_group_button or self.hovered_resource_group_option is not None:
                self.hovered_map_layer_button = False
                self.hovered_map_layer_option = None
                self.hovered_time_button = None
                self.hovered_tile = None
                return

        self.hovered_map_layer_button = self.point_in_rect(x, y, self.map_layer_button_rect())
        self.hovered_map_layer_option = self.map_layer_option_at(x, y)
        if self.hovered_map_layer_button or self.hovered_map_layer_option is not None:
            self.hovered_time_button = None
            self.hovered_tile = None
            return

        self.hovered_time_button = None
        for time_button in self.time_buttons:
            if time_button.contains(x, y):
                self.hovered_time_button = time_button
                self.hovered_tile = None
                return

        if self.use_overview_lod():
            self.hovered_tile = None
            return

        current_time = time.time()
        if current_time - self.last_mouse_check > self.visible_update_interval * 0.25:
            world_x, world_y = self.screen_to_world(x, y)
            self.hovered_tile = self.get_tile_at(world_x, world_y)
            self.last_mouse_check = current_time

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if self.paused:
            if self.pause_screen == "settings" and self.open_pause_dropdown:
                for dropdown in self.pause_dropdowns:
                    if dropdown.key == self.open_pause_dropdown:
                        dropdown.scroll(-scroll_y)
                        dropdown.hovered_index = dropdown.option_at(x, y)
                        return
            return

        division_list_rect = self.division_list_rect()
        if division_list_rect and self.point_in_rect(x, y, division_list_rect):
            self.scroll_division_list(-scroll_y)
            return

        if self.selected_tile and self.point_in_rect(x, y, self.hex_panel_rect()):
            self.scroll_hex_panel(-scroll_y)
            return

        if self.active_top_panel_key == "resources" and self.side_panel_progress > 0:
            rows = self.resource_rows()
            over_resource_panel = self.point_in_rect(x, y, self.side_panel_rect())
            over_resource_table = self.point_in_rect(x, y, self.resource_table_rect(rows))
            if over_resource_table:
                self.scroll_resource_rows(-scroll_y)
                return
            if over_resource_panel:
                return

        if self.active_top_panel_key == "trade" and self.side_panel_progress > 0:
            if self.point_in_rect(x, y, self.side_panel_rect()):
                self.scroll_trade_rows(-scroll_y)
                return

        old_zoom = self.world_camera.zoom
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, old_zoom + scroll_y * ZOOM_SPEED))
        if new_zoom == old_zoom:
            return

        world_x, world_y = self.screen_to_world(x, y)
        self.world_camera.zoom = new_zoom

        camera_x = world_x - (x - self.window.width / 2) / new_zoom
        camera_y = world_y - (y - self.window.height / 2) / new_zoom
        camera_x, camera_y = self.clamp_camera_position(camera_x, camera_y)
        self.world_camera.position = (camera_x, camera_y)
        self.target_camera_x = camera_x
        self.target_camera_y = camera_y
        self.last_visible_update = 0

    def screen_to_world(self, screen_x, screen_y):
        camera_x, camera_y = self.world_camera.position
        zoom = self.world_camera.zoom
        world_x = camera_x + (screen_x - self.window.width / 2) / zoom
        world_y = camera_y + (screen_y - self.window.height / 2) / zoom
        return world_x, world_y

    def get_tile_at(self, x, y):
        return self.get_tile_at_world_position(x, y)

    def get_tile_at_world_position(self, x, y):
        cell = self.spatial_hash_coords(x, y)
        candidates = self.tile_spatial_hash.get(cell, [])
        for tile in candidates:
            if tile.contains_point(x, y):
                return tile
        return None

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE:
            if self.army_plan_mode:
                self.cancel_army_plan_mode()
                return

            if not self.paused and self.construction_placement_mode:
                self.set_construction_placement_mode(False)
                return

            if not self.paused and self.side_panel_target > 0:
                self.close_top_panel()
                return

            if self.paused and self.pause_screen == "settings":
                if self.open_pause_dropdown:
                    self.open_pause_dropdown = None
                    for dropdown in self.pause_dropdowns:
                        dropdown.hovered_index = None
                else:
                    self.close_pause_settings()
                return
            self.toggle_pause_menu()
            return

        if self.paused:
            return

        if key == arcade.key.SPACE:
            self.toggle_time_pause()
            return

        self.keys_pressed.add(key)

        if key == arcade.key.EQUAL or key == arcade.key.PLUS:
            self.world_camera.zoom = min(MAX_ZOOM, self.world_camera.zoom + ZOOM_SPEED)
        elif key == arcade.key.MINUS:
            self.world_camera.zoom = max(MIN_ZOOM, self.world_camera.zoom - ZOOM_SPEED)
        self.world_camera.position = self.clamp_camera_position(*self.world_camera.position)
        self.target_camera_x, self.target_camera_y = self.world_camera.position
        self.last_visible_update = 0

    def on_key_release(self, key, modifiers):
        if self.paused:
            return

        if key in self.keys_pressed:
            self.keys_pressed.remove(key)


def main():
    settings = load_settings(RESOLUTIONS)
    window = create_window_with_fallback(arcade, "HOI 5", settings, RESOLUTIONS)
    start_view = Game()
    window.show_view(start_view)
    arcade.run()


if __name__ == "__main__":
    main()
