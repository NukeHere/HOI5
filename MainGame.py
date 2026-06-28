import arcade
import random
import math
import struct
import time
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from perlin_noise import PerlinNoise
from PIL import Image, ImageDraw
from pyglet.graphics import Batch
from arcade.gl import BufferDescription
from Constants import *
from HexTile import HexTile
from MapData import MapTileData
from Settings import create_window_with_fallback, load_settings, save_settings

OVERVIEW_LOD_ZOOM = 0.2
OVERVIEW_TEXTURE_MAX_SIZE = 1024
RESOLUTIONS = [(1024, 768), (1200, 800), (1366, 768), (1600, 900), (1920, 1080)]
MAX_BOTS = 11
STATE_COLORS = [
    (235, 65, 56),
    (255, 184, 0),
    (0, 183, 255),
    (255, 72, 191),
    (118, 235, 74),
    (255, 126, 0),
    (170, 98, 255),
    (0, 220, 190),
    (255, 238, 72),
    (52, 112, 255),
    (255, 112, 145),
    (215, 255, 112),
]
STATE_BORDER_COLORS = [
    (255, 30, 20),
    (255, 230, 0),
    (0, 220, 255),
    (255, 0, 210),
    (80, 255, 40),
    (255, 135, 0),
    (190, 65, 255),
    (0, 255, 215),
    (255, 255, 80),
    (40, 105, 255),
    (255, 75, 135),
    (215, 255, 55),
]
MAP_LAYERS = [
    ("terrain", "Местность", True),
    ("political", "Политическая", True),
    ("height", "Высотная", True),
    ("climate", "Климат", True),
    ("resources", "Ресурсы", True),
    ("weather", "Погодная", False),
]
RESOURCE_MAP_GROUPS = [
    (
        "fuel",
        "Топливо",
        ["coal", "oil", "natural_gas", "peat", "uranium"],
        (222, 92, 54),
        1_200_000,
    ),
    (
        "metals",
        "Сырьевые металлы",
        [
            "iron_ore", "copper_ore", "bauxite", "lead", "zinc", "nickel",
            "gold", "silver", "rare_earth_metals", "alloying_additives",
        ],
        (214, 176, 82),
        350_000,
    ),
    (
        "construction",
        "Стройсырье",
        ["limestone", "sand", "gravel", "crushed_stone", "clay", "quartz"],
        (174, 156, 124),
        450_000,
    ),
    (
        "chemistry",
        "Химсырье",
        ["sulfur", "potash", "phosphorite", "apatite", "salt", "rubber"],
        (112, 184, 132),
        250_000,
    ),
    (
        "gems",
        "Редкие минералы",
        ["gold", "silver", "rare_earth_metals", "uranium", "graphite", "mica"],
        (156, 124, 218),
        80_000,
    ),
]
RAW_RESOURCE_NAMES = list(
    dict.fromkeys(
        resource
        for _key, _label, resources, _color, _scale in RESOURCE_MAP_GROUPS
        for resource in resources
    )
)
STARTING_STOCK_RANGES = {
    "raw": (20_000, 70_000),
    "semi_finished": (5_000, 18_000),
    "finished": (1_500, 8_000),
}
STARTING_STOCK_MULTIPLIERS = {
    "gold": 0.08,
    "silver": 0.18,
    "rare_earth_metals": 0.12,
    "uranium": 0.16,
    "oil": 1.35,
    "natural_gas": 1.35,
    "coal": 1.35,
    "salt": 1.5,
    "sand": 1.45,
    "gravel": 1.35,
    "crushed_stone": 1.35,
    "food": 1.6,
    "consumer_goods": 1.35,
    "weapons": 0.55,
    "ships": 0.25,
    "electronics": 0.65,
}
BUILDING_TYPES = [
    ("city", "Город"),
    ("village", "Село"),
    ("industry", "Промзона"),
    ("farms", "Поля/фермы"),
    ("mine", "Шахта"),
    ("port", "Порт"),
]
BUILDING_STEP = 0.05
RESOURCE_PANEL_CATEGORIES = [
    ("raw", "Сырье"),
    ("semi_finished", "Полуфабрикаты"),
    ("finished", "Готовая продукция"),
]
SEMI_FINISHED_RESOURCE_NAMES = [
    "steel",
    "cement",
    "refined_fuel",
    "chemicals",
    "lumber",
    "food",
    "fertilizer",
    "copper_wire",
]
FINISHED_RESOURCE_NAMES = [
    "consumer_goods",
    "machinery",
    "vehicles",
    "electronics",
    "construction_goods",
    "weapons",
    "ships",
]
RESOURCE_DISPLAY_NAMES = {
    "coal": "Уголь",
    "peat": "Торф",
    "oil": "Нефть",
    "natural_gas": "Газ",
    "uranium": "Уран",
    "iron_ore": "Железная руда",
    "alloying_additives": "Легир. добавки",
    "bauxite": "Бокситы",
    "copper_ore": "Медная руда",
    "lead": "Свинец",
    "nickel": "Никель",
    "zinc": "Цинк",
    "gold": "Золото",
    "silver": "Серебро",
    "rare_earth_metals": "Редкоземы",
    "potash": "Калийные соли",
    "salt": "Соль",
    "phosphorite": "Фосфориты",
    "apatite": "Апатиты",
    "sulfur": "Сера",
    "rubber": "Каучук",
    "sand": "Песок",
    "gravel": "Гравий",
    "crushed_stone": "Щебень",
    "limestone": "Известняк",
    "clay": "Глина",
    "graphite": "Графит",
    "mica": "Слюда",
    "quartz": "Кварц",
    "steel": "Сталь",
    "cement": "Цемент",
    "refined_fuel": "Топливо",
    "chemicals": "Химикаты",
    "lumber": "Пиломатериалы",
    "food": "Еда",
    "fertilizer": "Удобрения",
    "copper_wire": "Медная проволока",
    "consumer_goods": "Потреб. товары",
    "machinery": "Оборудование",
    "vehicles": "Транспорт",
    "electronics": "Электроника",
    "construction_goods": "Стройтовары",
    "weapons": "Оружие",
    "ships": "Корабли",
}
RESOURCE_USAGE_DESCRIPTIONS = {
    "coal": "Топливо для электростанций, металлургии и тяжелой промышленности.",
    "peat": "Местное топливо и сырье для химии, удобрений и сельского хозяйства.",
    "oil": "Основа топлива, пластмасс, химикатов и военного снабжения.",
    "natural_gas": "Топливо для энергетики, отопления и химической промышленности.",
    "uranium": "Сырье для атомной энергетики, исследований и стратегических программ.",
    "iron_ore": "База для стали, строительства, машин, транспорта и вооружений.",
    "alloying_additives": "Добавки для прочных сплавов, станков, двигателей и оружия.",
    "bauxite": "Сырье для алюминия, авиации, транспорта и электрооборудования.",
    "copper_ore": "Нужна для проводов, электроники, энергетики и промышленного оборудования.",
    "lead": "Используется в аккумуляторах, боеприпасах, защите и химической промышленности.",
    "nickel": "Нужен для нержавеющей стали, сплавов, батарей и военной техники.",
    "zinc": "Защита стали от коррозии, сплавы, химия и строительные материалы.",
    "gold": "Драгоценный металл для бюджета, электроники, резервов и торговли.",
    "silver": "Используется в электронике, химии, медицине и торговых товарах.",
    "rare_earth_metals": "Критичны для электроники, датчиков, батарей и высоких технологий.",
    "potash": "Основа удобрений и аграрного производства.",
    "salt": "Пищевое сырье, химическая промышленность и базовые товары населения.",
    "phosphorite": "Сырье для удобрений и роста сельского хозяйства.",
    "apatite": "Источник фосфатов для удобрений и химической промышленности.",
    "sulfur": "Химикаты, удобрения, взрывчатка и переработка нефти.",
    "rubber": "Шины, техника, военное снабжение и потребительские товары.",
    "sand": "Стекло, бетон, строительство и базовая промышленность.",
    "gravel": "Дороги, бетон, инфраструктура и строительство.",
    "crushed_stone": "Фундамент для дорог, бетона, зданий и укреплений.",
    "limestone": "Цемент, сталь, строительство и химическая промышленность.",
    "clay": "Кирпич, керамика, цемент и строительные материалы.",
    "graphite": "Электроды, батареи, металлургия и высокотехнологичная промышленность.",
    "mica": "Изоляция, электроника, оптика и специальные материалы.",
    "quartz": "Стекло, электроника, оптика и точная промышленность.",
    "steel": "Главный материал для строительства, машин, транспорта и армии.",
    "cement": "Базовый материал для зданий, дорог, портов и укреплений.",
    "refined_fuel": "Горючее для транспорта, армии, авиации и промышленности.",
    "chemicals": "Промежуточный ресурс для удобрений, пластмасс, медицины и боеприпасов.",
    "lumber": "Строительство, мебель, упаковка и простая промышленность.",
    "food": "Снабжение населения и армии, основа стабильности страны.",
    "fertilizer": "Повышает выпуск сельского хозяйства и продовольствия.",
    "copper_wire": "Электросети, техника, электроника и промышленное оборудование.",
    "consumer_goods": "Товары для населения, влияющие на довольство и экономику.",
    "machinery": "Станки и оборудование для фабрик, шахт и строительства.",
    "vehicles": "Гражданский и военный транспорт, логистика и торговля.",
    "electronics": "Исследования, связь, автоматизация, армия и высокие технологии.",
    "construction_goods": "Готовые материалы для ускоренного строительства.",
    "weapons": "Оснащение армии, мобилизация и военное производство.",
    "ships": "Флот, морская торговля, перевозки и контроль побережья.",
}
TILE_VISUAL_ASSETS = {
    "forest": "forest.png",
    "grassland": "grassland.png",
    "desert": "desert.png",
    "mountains": "mountains.png",
    "snowfield": "snowfield.png",
    "water": "water.png",
    "city": "city.png",
    "village": "village.png",
    "industry": "industry.png",
    "farms": "farms.png",
    "mine": "mine.png",
    "port": "port.png",
}
VISUAL_FACTOR_WEIGHTS = {
    "city": 1.45,
    "port": 1.4,
    "industry": 1.3,
    "farms": 1.22,
    "mine": 1.2,
    "village": 1.08,
    "water": 1.18,
    "mountains": 1.12,
    "forest": 1.05,
    "desert": 1.02,
    "snowfield": 1.02,
    "grassland": 0.92,
}
VISUAL_MIN_COVERAGE = 0.03
VISUAL_SYSTEM_MIN_ZOOM = 0.38
VISUAL_EDGE_MIN_ZOOM = 0.62
VISUAL_DENSE_TILE_LIMIT = 650
ASSET_DIR = Path(__file__).resolve().parent / "assets"
LAYER_ICON_PATH = ASSET_DIR / "layers_icon.png"
TILE_VISUAL_DIR = ASSET_DIR / "tile_visuals"
UI_ICON_DIR = ASSET_DIR / "ui_icons"
TOP_STATUS_BAR_HEIGHT = 36
TOP_NAV_BAR_HEIGHT = 46
TOP_UI_HEIGHT = TOP_STATUS_BAR_HEIGHT + TOP_NAV_BAR_HEIGHT
SIDE_PANEL_WIDTH = 420
SIDE_PANEL_MARGIN = 12
TOP_NAV_TABS = [
    ("politics", "Внутренняя политика", "politics.png"),
    ("economy", "Экономика", "economy.png"),
    ("resources", "Ресурсы", "resources.png"),
    ("construction", "Строительство", "construction.png"),
    ("research", "Исследования", "research.png"),
    ("diplomacy", "Дипломатия", "diplomacy.png"),
    ("military", "Армия", "military.png"),
]
SIMULATION_START_TIME = datetime(2000, 1, 1, 0)
SIMULATION_REAL_SECONDS_PER_TICK = 0.25
SIMULATION_HOURS_PER_TICK = [1, 2, 4, 8, 24]
MONTH_NAMES = [
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]


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
    population: float | None = None
    budget: float = 250_000_000.0
    monthly_balance: float = 0.0
    stability: float = 0.72
    legitimacy: float = 0.61

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


class LocalSimulationServer:
    def __init__(self):
        self.current_time = SIMULATION_START_TIME
        self.paused = True
        self.speed_level = 1
        self.tick_count = 0
        self.accumulator = 0.0

    @property
    def hours_per_tick(self):
        return SIMULATION_HOURS_PER_TICK[self.speed_level - 1]

    def update(self, delta_time):
        if self.paused:
            return

        self.accumulator += delta_time
        ticks_to_process = min(16, int(self.accumulator / SIMULATION_REAL_SECONDS_PER_TICK))
        if ticks_to_process <= 0:
            return

        self.accumulator -= ticks_to_process * SIMULATION_REAL_SECONDS_PER_TICK
        self.current_time += timedelta(hours=self.hours_per_tick * ticks_to_process)
        self.tick_count += ticks_to_process

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
        self.selected_tile = None
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
        self.fps = 0
        self.fps_frame_count = 0
        self.fps_timer = 0
        self.world_generator = None
        self.world_seed = random.randint(0, 999999)
        self.selection_border = None
        self.selection_border_sprite_list = arcade.SpriteList()
        self.batch = Batch()
        self.debug_text = arcade.Text("", 10, 30, arcade.color.YELLOW, 12)
        self.simulation_server = LocalSimulationServer()
        self.simulation_client = LocalSimulationClient(self.simulation_server)
        self.time_panel_rect = (0, 0, 0, 0)
        self.time_buttons = []
        self.hovered_time_button = None
        self.time_date_text = arcade.Text("", 0, 0, (225, 232, 240), 15, anchor_x="center", anchor_y="center")
        self.time_clock_text = arcade.Text("", 0, 0, (225, 232, 240), 13, anchor_x="center", anchor_y="center")
        self.ui_text_pool = []
        self.ui_text_pool_cursor = 0
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
        self.building_dropdown = None
        self.selected_building_index = 0
        self.open_building_dropdown = False
        self.hovered_build_button = False
        self.building_message = ""
        self.building_message_timer = 0.0
        self.show_build_controls = False
        self.top_nav_buttons = []
        self.top_nav_icon_textures = self.load_top_nav_icon_textures()
        self.hovered_top_nav_key = None
        self.active_top_panel_key = None
        self.side_panel_progress = 0.0
        self.side_panel_target = 0.0
        self.hovered_side_panel_close = False
        self.resource_panel_category = "raw"
        self.selected_resource_key = None
        self.resource_scroll_index = 0
        self.resource_summary_rect = None
        self.hovered_resource_summary = False
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
        self.rebuild_build_controls()
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

    def rebuild_build_controls(self):
        if not self.window:
            return

        panel_x, panel_y, panel_width, panel_height = self.build_panel_rect()
        control_y = panel_y + panel_height - 62
        self.building_dropdown = PauseDropdown(
            "building",
            "Строение",
            [label for _key, label in BUILDING_TYPES],
            self.selected_building_index,
            panel_x + 222,
            control_y,
            190,
            34,
            self.set_selected_building,
        )

    def build_panel_rect(self):
        return 12, 74, 430, 250

    def build_button_rect(self):
        panel_x, panel_y, panel_width, panel_height = self.build_panel_rect()
        return panel_x + 14, panel_y + panel_height - 62, 150, 34

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

    def set_selected_building(self, index):
        self.selected_building_index = max(0, min(len(BUILDING_TYPES) - 1, index))
        if self.building_dropdown:
            self.building_dropdown.selected_index = self.selected_building_index

    def selected_building_type(self):
        return BUILDING_TYPES[self.selected_building_index]

    def build_selected_structure(self):
        if not self.selected_tile:
            self.building_message = "Выберите клетку"
            self.building_message_timer = 2.0
            return

        key, label = self.selected_building_type()
        coverage = getattr(self.selected_tile, "building_coverage", None)
        if coverage is None:
            coverage = {}
            self.selected_tile.building_coverage = coverage

        coverage[key] = min(1.0, coverage.get(key, 0.0) + BUILDING_STEP)
        if key not in self.selected_tile.buildings:
            self.selected_tile.buildings.append(key)

        self.building_message = f"{label}: {coverage[key]:.0%}"
        self.building_message_timer = 2.0
        if self.selected_tile.owner:
            self.recalculate_state_resources(self.selected_tile.owner)
        self.tile_visual_revision += 1
        self.invalidate_tile_visual_cache()

    def invalidate_tile_visual_cache(self):
        self.tile_visual_cache_key = None

    def refresh_visible_tiles_signature(self):
        signature = tuple((tile.q, tile.r) for tile in self.visible_tiles)
        if signature == self.visible_tiles_signature:
            return

        self.visible_tiles_signature = signature
        self.visible_tiles_revision += 1
        self.invalidate_tile_visual_cache()

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
    def resource_names_for_category(category_key):
        if category_key == "raw":
            return RAW_RESOURCE_NAMES
        if category_key == "semi_finished":
            return SEMI_FINISHED_RESOURCE_NAMES
        if category_key == "finished":
            return FINISHED_RESOURCE_NAMES
        return []

    def create_starting_stockpiles(self, player):
        rng = random.Random((self.world_seed + 1) * 1009 + player.id * 7919)
        stockpiles = self.empty_resource_stockpiles()

        for category_key, (min_amount, max_amount) in STARTING_STOCK_RANGES.items():
            for resource_key in self.resource_names_for_category(category_key):
                multiplier = STARTING_STOCK_MULTIPLIERS.get(resource_key, 1.0)
                amount = rng.uniform(min_amount, max_amount) * multiplier
                stockpiles[category_key][resource_key] = amount

        player.resource_stockpiles = stockpiles
        return stockpiles

    def ensure_player_stockpiles(self, player):
        stockpiles = player.resource_stockpiles or self.empty_resource_stockpiles()
        changed = False

        for category_key, (min_amount, max_amount) in STARTING_STOCK_RANGES.items():
            bucket = stockpiles.setdefault(category_key, {})
            for resource_key in self.resource_names_for_category(category_key):
                if resource_key in bucket:
                    continue
                resource_seed = sum((index + 1) * ord(char) for index, char in enumerate(resource_key))
                rng = random.Random((self.world_seed + 1) * 1009 + player.id * 7919 + resource_seed)
                multiplier = STARTING_STOCK_MULTIPLIERS.get(resource_key, 1.0)
                bucket[resource_key] = rng.uniform(min_amount, max_amount) * multiplier
                changed = True

        if changed or player.resource_stockpiles is None:
            player.resource_stockpiles = stockpiles
        return stockpiles

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
        return totals

    def recalculate_all_state_resources(self):
        for player in self.players:
            self.recalculate_state_resources(player)

    @staticmethod
    def top_resource_items(resources, limit=3):
        return [
            (key, value)
            for key, value in sorted(resources.items(), key=lambda item: item[1], reverse=True)
            if value > 0
        ][:limit]

    @staticmethod
    def format_resource_amount(amount):
        if amount >= 1_000_000:
            return f"{amount / 1_000_000:.1f}M"
        if amount >= 1_000:
            return f"{amount / 1_000:.1f}K"
        return f"{amount:.0f}"

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
    def format_population(population):
        if population is None:
            return "--"
        if population >= 1_000_000:
            return f"{population / 1_000_000:.1f}M"
        if population >= 1_000:
            return f"{population / 1_000:.1f}K"
        return f"{population:.0f}"

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
        return {
            "raw": {"yellow": [], "red": []},
            "semi_finished": {"yellow": [], "red": []},
            "finished": {"yellow": [], "red": []},
        }

    def resource_problem_level(self, player):
        problems = self.resource_problem_summary(player)
        if any(problems[key]["red"] for key in problems):
            return "red"
        if any(problems[key]["yellow"] for key in problems):
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

    @staticmethod
    def human_coverages(tile):
        return dict(getattr(tile, "building_coverage", {}) or {})

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

    def fallback_edge_factor(self, tile, excluded_key=None):
        for key, coverage in self.ranked_visual_factors(tile, include_natural=True, include_human=False):
            if key != excluded_key:
                return key, coverage
        return None, 0.0

    def edge_visual_factor(self, tile, edge_index, center_natural_key):
        neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
        if neighbor:
            ranked = self.ranked_visual_factors(neighbor, include_natural=True, include_human=True)
            if ranked:
                return ranked[0]

        return self.fallback_edge_factor(tile, excluded_key=center_natural_key)

    def draw_tile_edge_visuals(self, tile, center_natural_key):
        used_edges = set()
        for edge_index in range(6):
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

        main_key, main_coverage = human_factors[0]
        main_size = self.visual_factor_size(main_coverage, HEX_SIZE * 0.2, HEX_SIZE * 0.34, HEX_SIZE * 0.62)
        self.append_visual_factor_sprite(main_key, tile.center_x, tile.center_y, main_size, alpha=245)

        fallback_angles = [-math.pi / 2, math.pi / 6, 5 * math.pi / 6, math.pi / 2]
        fallback_index = 0
        for key, coverage in human_factors[1:5]:
            edge_index, neighbor_value = self.best_neighbor_edge_for_factor(tile, key)
            if edge_index is not None and neighbor_value >= VISUAL_MIN_COVERAGE:
                x, y = self.edge_anchor(tile, edge_index, edge_amount=0.48)
                used_edges.add(edge_index)
            else:
                angle = fallback_angles[fallback_index % len(fallback_angles)]
                fallback_index += 1
                x = tile.center_x + math.cos(angle) * HEX_SIZE * 0.33
                y = tile.center_y + math.sin(angle) * HEX_SIZE * 0.33

            size = self.visual_factor_size(coverage, HEX_SIZE * 0.16, HEX_SIZE * 0.24, HEX_SIZE * 0.42)
            self.append_visual_factor_sprite(key, x, y, size, alpha=230)

    def tile_visual_zoom_mode(self):
        zoom = self.world_camera.zoom
        if self.map_layer != "terrain" or zoom < VISUAL_SYSTEM_MIN_ZOOM:
            return None

        dense_view = len(self.visible_tiles) > VISUAL_DENSE_TILE_LIMIT
        if dense_view:
            return "dense"
        if zoom >= VISUAL_EDGE_MIN_ZOOM:
            return "edges"
        return "center"

    def rebuild_tile_visual_sprites(self, mode):
        self.tile_visual_sprite_list.clear()
        if mode is None:
            return

        draw_edges = mode == "edges"
        draw_natural = mode != "dense"
        for tile in self.visible_tiles:
            if self.is_water_tile(tile):
                continue

            human_factors = self.ranked_visual_factors(tile, include_natural=False, include_human=True)
            if mode == "dense" and not human_factors:
                continue

            natural_factors = self.ranked_visual_factors(tile, include_natural=True, include_human=False)
            center_natural_key, center_natural_coverage = natural_factors[0] if natural_factors else (None, 0.0)
            used_edges = self.draw_tile_edge_visuals(tile, center_natural_key) if draw_edges else set()
            self.draw_tile_center_visuals(
                tile,
                center_natural_key,
                center_natural_coverage,
                used_edges,
                draw_natural=draw_natural,
                human_factors=human_factors,
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
            self.create_starting_stockpiles(player)
            self.players.append(player)

        self.human_player = self.players[0]
        start_tiles = self.find_state_start_tiles(total_players)
        for player, start_tile in zip(self.players, start_tiles):
            player.capital_tile = start_tile
            self.claim_start_territory(player, start_tile, self.start_territory_radius)

        for tile in self.hex_grid:
            tile.color = self.get_tile_map_color(tile)
        self.recalculate_all_state_resources()
        self.rebuild_state_borders()

        print(
            f"Created {len(self.players)} states, "
            f"start territory radius: {self.start_territory_radius}"
        )

    def calculate_start_territory_radius(self, total_players):
        radius = round(self.map_size / max(8, total_players * 2))
        return max(3, min(12, radius))

    def find_state_start_tiles(self, total_players):
        center_q = (self.grid_width - 1) / 2
        center_r = (self.grid_height - 1) / 2
        placement_radius = max(
            self.start_territory_radius * 2 + 3,
            min(self.grid_width, self.grid_height) * 0.28,
        )
        start_tiles = []

        for index in range(total_players):
            angle = math.tau * index / total_players - math.pi / 2
            target_q = round(center_q + math.cos(angle) * placement_radius)
            target_r = round(center_r + math.sin(angle) * placement_radius)
            start_tiles.append(self.find_nearest_start_tile(target_q, target_r, start_tiles))

        return start_tiles

    def find_nearest_start_tile(self, target_q, target_r, existing_starts):
        max_search_radius = max(self.grid_width, self.grid_height)
        for radius in range(max_search_radius):
            candidates = []
            for dq in range(-radius, radius + 1):
                for dr in range(-radius, radius + 1):
                    q = target_q + dq
                    r = target_r + dr
                    tile = self.hex_lookup.get((q, r))
                    if tile and self.is_valid_state_start(tile, existing_starts):
                        candidates.append(tile)
            if candidates:
                return min(candidates, key=lambda tile: (tile.q - target_q) ** 2 + (tile.r - target_r) ** 2)

        return min(
            self.hex_grid,
            key=lambda tile: (tile.q - target_q) ** 2 + (tile.r - target_r) ** 2,
        )

    def is_valid_state_start(self, tile, existing_starts):
        if tile.terrain_type in ["deep_ocean", "ocean", "shallow_water", "lake"]:
            return False
        if tile.owner is not None:
            return False
        min_distance = self.start_territory_radius * 2 + 2
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
        self.state_border_list = arcade.shape_list.ShapeElementList()
        for tile in self.hex_grid:
            if not tile.owner:
                continue

            color = tile.owner.border_color
            for edge_index in range(6):
                neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
                if neighbor and neighbor.owner == tile.owner:
                    continue

                x1, y1 = tile.corners[edge_index]
                x2, y2 = tile.corners[(edge_index + 1) % 6]
                self.state_border_list.append(
                    arcade.shape_list.create_line(x1, y1, x2, y2, (0, 0, 0), 11)
                )
                self.state_border_list.append(
                    arcade.shape_list.create_line(x1, y1, x2, y2, color, 7)
                )

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

    def selected_resource_overlay_color(self, tile, base_color):
        if (
            self.active_top_panel_key != "resources"
            or self.resource_panel_category != "raw"
            or not self.selected_resource_key
        ):
            return base_color

        amount = self.resource_amount_for_key(tile, self.selected_resource_key)
        if amount <= 0:
            return base_color

        intensity = min(1.0, math.log10(amount + 1) / math.log10(500_000 + 1))
        glow = self.blend_colors((214, 176, 82), (255, 245, 140), intensity)
        return self.blend_colors(base_color, glow, 0.42 + intensity * 0.36)

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

    def get_tile_map_color(self, tile):
        if self.map_layer == "political":
            return self.selected_resource_overlay_color(tile, self.political_color(tile))
        if self.map_layer == "height":
            return self.selected_resource_overlay_color(tile, self.height_color(tile))
        if self.map_layer == "climate":
            return self.selected_resource_overlay_color(tile, self.climate_color(tile))
        if self.map_layer == "resources":
            return self.selected_resource_overlay_color(tile, self.resource_color(tile))
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
            points = [
                (
                    int((corner_x - min_x) * scale),
                    int((max_y - corner_y) * scale),
                )
                for corner_x, corner_y in tile.corners
            ]
            draw.polygon(points, fill=(*self.get_tile_map_color(tile), 255))

        texture = arcade.Texture(
            name=(
                f"map_overview_{self.world_seed}_{self.grid_width}x{self.grid_height}_"
                f"{self.map_layer}_{self.resource_group_index}_{self.selected_resource_key or 'none'}"
            ),
            image=image,
        )
        self.map_overview_sprite = arcade.Sprite(texture)
        self.map_overview_sprite.center_x = min_x + world_width / 2
        self.map_overview_sprite.center_y = min_y + world_height / 2
        self.map_overview_sprite.width = world_width
        self.map_overview_sprite.height = world_height
        self.map_overview_sprite_list.clear()
        self.map_overview_sprite_list.append(self.map_overview_sprite)

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
        for tile in self.hex_grid:
            min_x, min_y, max_x, max_y = tile.bounding_box
            if (max_x >= left and min_x <= right and
                    max_y >= bottom and min_y <= top):
                self.visible_tiles.append(tile)

    def on_draw(self):
        self.sync_cameras_to_window()
        self.clear()
        if not self.premium_shader_enabled and not self.premium_shader_attempted:
            self.setup_premium_shader()
        start_time = time.time()
        self.world_camera.use()
        if self.use_overview_lod():
            self.map_overview_sprite_list.draw()
        else:
            self.visible_tiles.draw()
            self.draw_tile_visual_system()
        self.state_border_list.draw()
        if self.map_layer == "political":
            self.draw_capital_markers()
        if self.selection_border.visible:
            self.selection_border_sprite_list.draw()
        self.draw_premium_shader_overlay()
        self.gui_camera.use()
        self.begin_ui_text_frame()
        self.draw_top_status_bar()
        self.draw_top_navigation_bar()
        self.draw_side_panel()
        self.draw_gui()
        if self.show_build_controls:
            self.draw_build_controls()
        self.draw_time_hud()
        self.draw_map_layer_control()
        if self.paused:
            self.draw_pause_menu()
        draw_time = (time.time() - start_time) * 1000
        draw_mode = "Overview" if self.use_overview_lod() else "Tiles"
        layer_label = next(label for key, label, _enabled in MAP_LAYERS if key == self.map_layer)
        self.debug_text.text = f"FPS: {self.fps:.0f} | Draw: {draw_time:.1f}ms | Mode: {draw_mode} | Layer: {layer_label} | Tiles: {len(self.visible_tiles)} | Seed: {self.world_seed}"
        self.debug_text.draw()

    def refresh_visible_tiles(self):
        if not self.window or not self.hex_grid:
            return

        if self.use_overview_lod():
            self.visible_tiles.clear()
            self.refresh_visible_tiles_signature()
        else:
            self.get_visible_tiles()
            self.update_draw_list()
            self.refresh_visible_tiles_signature()
        self.last_visible_update = time.time()

    def sync_cameras_to_window(self):
        if not self.window:
            return

        self.window.viewport = (0, 0, self.window.width, self.window.height)
        self.world_camera.match_window(viewport=True, projection=True, position=False)
        self.gui_camera.match_window(viewport=True, projection=True, position=True)

    def begin_ui_text_frame(self):
        self.ui_text_pool_cursor = 0

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
        label.draw()

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

        budget_text = f"{self.format_money(player.budget)}  {self.format_money(player.monthly_balance)}/мес"
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
            "Наука: --",
        ]

        x = 10
        for index, text in enumerate(items[:3]):
            color = (238, 244, 250) if index == 0 else (210, 220, 232)
            self.draw_ui_text(text, x, y + TOP_STATUS_BAR_HEIGHT / 2, color, 12, anchor_y="center")
            x += max(88, len(text) * 7 + 22)

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

        self.draw_resource_summary_tooltip(player)

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
        tooltip_y = y - tooltip_height - 8
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 245))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (140, 160, 184), 1)
        line_y = tooltip_y + tooltip_height - 20
        self.draw_ui_text("Проблемы ресурсов", tooltip_x + 12, line_y, arcade.color.WHITE, 12)
        line_y -= 18
        for label, items, color in [("Красные", red_items, (240, 108, 98)), ("Желтые", yellow_items, (238, 198, 90))]:
            if not items:
                continue
            self.draw_ui_text(f"{label}:", tooltip_x + 12, line_y, color, 11)
            line_y -= 16
            for item in items[:5]:
                self.draw_ui_text(f"- {self.resource_display_name(item)}", tooltip_x + 22, line_y, (220, 230, 240), 11)
                line_y -= 15

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

    def top_nav_button_at(self, x, y):
        for button in self.top_nav_buttons:
            if self.point_in_rect(x, y, button["rect"]):
                return button
        return None

    def open_top_panel(self, key):
        previous_key = self.active_top_panel_key
        self.active_top_panel_key = key
        self.side_panel_target = 1.0
        if self.selected_resource_key and previous_key != key:
            self.create_map_overview()
            self.refresh_visible_tiles()

    def close_top_panel(self):
        self.side_panel_target = 0.0
        self.hovered_side_panel_close = False
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
        width = 760 if self.active_top_panel_key == "resources" else SIDE_PANEL_WIDTH
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
        stockpiles = self.ensure_player_stockpiles(self.human_player)
        if self.resource_panel_category == "raw":
            raw = self.human_player.resource_totals.get("raw", {})
            raw_stock = stockpiles.get("raw", {})
            keys = list(RAW_RESOURCE_NAMES)
            for key in sorted(raw.keys()):
                if key not in keys:
                    keys.append(key)
            return [
                {
                    "key": key,
                    "ground": raw.get(key, 0.0),
                    "stock": raw_stock.get(key, 0.0),
                    "production": None,
                    "consumption": None,
                    "months": None,
                }
                for key in keys
            ]

        names = SEMI_FINISHED_RESOURCE_NAMES if self.resource_panel_category == "semi_finished" else FINISHED_RESOURCE_NAMES
        stock = stockpiles.get(self.resource_panel_category, {})
        return [
            {
                "key": key,
                "ground": None,
                "stock": stock.get(key, 0.0),
                "production": None,
                "consumption": None,
                "months": None,
            }
            for key in names
        ]

    def resource_row_rects(self, rows):
        panel_x, panel_y, _panel_width, panel_height = self.side_panel_rect()
        start_y = panel_y + panel_height - 300
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

        problems = self.resource_problem_summary(self.human_player)
        for index, (category_key, label) in enumerate(RESOURCE_PANEL_CATEGORIES):
            x, y, width, height = self.resource_category_rects()[index]
            active = category_key == self.resource_panel_category
            yellow_count = len(problems[category_key]["yellow"])
            red_count = len(problems[category_key]["red"])
            level = "red" if red_count else ("yellow" if yellow_count else "green")
            fill = self.problem_color(level)
            if active:
                fill = self.blend_colors(fill[:3], (255, 255, 255), 0.12) + (fill[3],)
            arcade.draw_lbwh_rectangle_filled(x, y, width, height, fill)
            arcade.draw_lbwh_rectangle_outline(x, y, width, height, (120, 142, 166), 1)
            self.draw_ui_text(label, x + 10, y + height - 20, arcade.color.WHITE, 13)
            self.draw_ui_text(f"Недостаток: {red_count + yellow_count}", x + 10, y + 32, (226, 234, 242), 11)
            self.draw_ui_text("Избыток: 0", x + 10, y + 14, (226, 234, 242), 11)

        warning_y = panel_y + panel_height - 166
        self.draw_ui_text("Состояние снабжения", panel_x + 18, warning_y, arcade.color.WHITE, 14)
        warning_y -= 20
        red_items = []
        yellow_items = []
        for _category, category_problems in problems.items():
            red_items.extend(category_problems["red"])
            yellow_items.extend(category_problems["yellow"])
        warnings = (
            [f"Критично: {self.resource_display_name(item)}" for item in red_items]
            + [f"Внимание: {self.resource_display_name(item)}" for item in yellow_items]
        )
        if warnings:
            for warning in warnings[:4]:
                self.draw_ui_text(warning, panel_x + 28, warning_y, (238, 198, 90), 11)
                warning_y -= 16
        else:
            self.draw_ui_text("Все спокойно", panel_x + 28, warning_y, (180, 192, 205), 11)

        rows = self.resource_rows()
        table_y = panel_y + panel_height - 250
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
            values = [
                self.resource_display_name(row["key"]),
                self.format_resource_amount(row["ground"]) if row["ground"] is not None else "--",
                "--" if row["stock"] is None else self.format_resource_amount(row["stock"]),
                "--" if row["production"] is None else self.format_resource_amount(row["production"]),
                "--" if row["consumption"] is None else self.format_resource_amount(row["consumption"]),
                "--" if row["months"] is None else f"{row['months']:.0f} мес.",
            ]
            for value, (_header, offset) in zip(values, headers):
                self.draw_ui_text(
                    value,
                    panel_x + offset,
                    y + height / 2,
                    (220, 230, 240),
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
        sources = self.resource_sources_count(self.selected_resource_key) if self.resource_panel_category == "raw" else 0
        self.draw_ui_text(f"Источники: {sources} клетки", card_x + 14, y, (220, 230, 240), 12)
        y -= 34
        self.draw_ui_text("Ресурс пока не используется.", card_x + 14, y, (180, 192, 205), 12)
        y -= 34
        self.draw_ui_text("Использование", card_x + 14, y, arcade.color.WHITE, 12)
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
        else:
            self.draw_ui_text(
                "Раздел пока пуст",
                panel_x + 18,
                panel_y + panel_height - 72,
                (180, 192, 205),
                14,
            )

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

    def draw_build_controls(self):
        if not self.show_build_controls or not self.selected_tile or not self.building_dropdown:
            return

        panel_x, panel_y, panel_width, panel_height = self.build_panel_rect()
        arcade.draw_lbwh_rectangle_filled(panel_x, panel_y, panel_width, panel_height, (18, 25, 33, 230))
        arcade.draw_lbwh_rectangle_outline(panel_x, panel_y, panel_width, panel_height, (100, 126, 155), 2)

        self.building_dropdown.selected_index = self.selected_building_index
        self.building_dropdown.draw(self.open_building_dropdown)

        button_x, button_y, button_width, button_height = self.build_button_rect()
        fill = (64, 92, 118) if self.hovered_build_button else (42, 55, 72)
        border = (165, 195, 230) if self.hovered_build_button else (100, 126, 155)
        arcade.draw_lbwh_rectangle_filled(button_x, button_y, button_width, button_height, fill)
        arcade.draw_lbwh_rectangle_outline(button_x, button_y, button_width, button_height, border, 2)
        self.draw_ui_text(
            "+5% построить",
            button_x + button_width / 2,
            button_y + button_height / 2,
            arcade.color.WHITE,
            14,
            anchor_x="center",
            anchor_y="center",
        )

        coverage = getattr(self.selected_tile, "building_coverage", {})
        y = panel_y + 94
        if coverage:
            self.draw_ui_text("На клетке:", panel_x + 14, y, (220, 230, 240), 13)
            y -= 20
            labels = dict(BUILDING_TYPES)
            for key, value in sorted(coverage.items(), key=lambda item: item[1], reverse=True):
                self.draw_ui_text(f"{labels.get(key, key)}: {value:.0%}", panel_x + 24, y, (220, 230, 240), 13)
                y -= 18
        else:
            self.draw_ui_text("На клетке пока нет строений", panel_x + 14, y, (180, 192, 205), 13)

        owner = self.selected_tile.owner
        if owner:
            totals = owner.resource_totals or self.recalculate_state_resources(owner)
            resource_x = panel_x + 222
            resource_y = panel_y + 130
            self.draw_ui_text(f"Страна: {owner.name}", resource_x, resource_y, (220, 230, 240), 12)
            resource_y -= 18
            self.draw_ui_text("Сырье:", resource_x, resource_y, (180, 192, 205), 11)
            resource_y -= 16
            items = self.top_resource_items(totals["raw"], limit=5)
            if items:
                for key, value in items:
                    line = f"{self.resource_display_name(key)}: {self.format_resource_amount(value)}"
                    self.draw_ui_text(line, resource_x + 8, resource_y, (220, 230, 240), 11)
                    resource_y -= 15
            else:
                self.draw_ui_text("нет", resource_x + 8, resource_y, (220, 230, 240), 11)

        if self.building_message:
            self.draw_ui_text(self.building_message, panel_x + 14, panel_y + 16, (235, 205, 120), 13)

    def on_resize(self, width, height):
        super().on_resize(width, height)
        self.sync_cameras_to_window()
        self.world_camera.position = self.clamp_camera_position(*self.world_camera.position)
        self.target_camera_x, self.target_camera_y = self.world_camera.position
        self.rebuild_pause_menu()
        self.rebuild_time_hud()
        self.rebuild_build_controls()
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
        self.window.set_fullscreen(self.fullscreen)
        if not self.fullscreen:
            self.window.set_size(width, height)
        save_settings(self.sound_volume, self.music_volume, self.fullscreen, self.resolution_index, RESOLUTIONS)
        self.sync_cameras_to_window()
        self.pause_message = "Настройки применены."
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

    def update_draw_list(self):
        """Обновление списка отрисовки"""
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
        if self.building_message_timer > 0:
            self.building_message_timer = max(0.0, self.building_message_timer - delta_time)
            if self.building_message_timer == 0:
                self.building_message = ""

        if self.paused or self.game_over:
            return

        self.fps_frame_count += 1
        self.fps_timer += delta_time
        if self.fps_timer >= 0.5:
            self.fps = self.fps_frame_count / self.fps_timer
            self.fps_frame_count = 0
            self.fps_timer = 0

        self.simulation_server.update(delta_time)
        self.simulation_client.sync_from_server()

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
                self.update_draw_list()
                self.refresh_visible_tiles_signature()
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

        if button == arcade.MOUSE_BUTTON_LEFT:
            if self.side_panel_progress > 0:
                if self.point_in_rect(x, y, self.side_panel_close_rect()):
                    self.close_top_panel()
                    return
                if self.point_in_rect(x, y, self.side_panel_rect()):
                    self.handle_resources_panel_click(x, y)
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

            if self.show_build_controls and self.selected_tile and self.building_dropdown:
                if self.open_building_dropdown:
                    option_index = self.building_dropdown.option_at(x, y)
                    if option_index is not None:
                        self.open_building_dropdown = False
                        self.building_dropdown.hovered_index = None
                        self.set_selected_building(option_index)
                        return

                if self.building_dropdown.contains_header(x, y):
                    self.open_building_dropdown = not self.open_building_dropdown
                    self.building_dropdown.hovered_index = None
                    return

                if self.point_in_rect(x, y, self.build_button_rect()):
                    self.open_building_dropdown = False
                    self.build_selected_structure()
                    return

                if self.point_in_rect(x, y, self.build_panel_rect()):
                    self.open_building_dropdown = False
                    return

            if self.map_layer == "resources":
                resource_option_index = self.resource_group_option_at(x, y)
                if resource_option_index is not None:
                    self.set_resource_group(resource_option_index)
                    return

                if self.point_in_rect(x, y, self.resource_group_button_rect()):
                    self.resource_group_menu_open = not self.resource_group_menu_open
                    self.map_layer_menu_open = False
                    return

                if self.resource_group_menu_open:
                    self.resource_group_menu_open = False

            option_index = self.map_layer_option_at(x, y)
            if option_index is not None:
                layer_key, _label, enabled = MAP_LAYERS[option_index]
                if enabled:
                    self.set_map_layer(layer_key)
                else:
                    self.set_map_layer("weather")
                return

            if self.point_in_rect(x, y, self.map_layer_button_rect()):
                self.map_layer_menu_open = not self.map_layer_menu_open
                self.resource_group_menu_open = False
                return

            if self.map_layer_menu_open:
                self.map_layer_menu_open = False

            for time_button in self.time_buttons:
                if time_button.contains(x, y):
                    time_button.action()
                    return

        world_x, world_y = self.screen_to_world(x, y)
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self.is_dragging = True
            self.drag_start_x = x
            self.drag_start_y = y
            self.drag_start_camera_x, self.drag_start_camera_y = self.target_camera_x, self.target_camera_y
        elif button == arcade.MOUSE_BUTTON_LEFT:
            self.selected_tile = self.get_tile_at(world_x, world_y)
            if self.selected_tile:
                self.selection_border.position = (self.selected_tile.center_x, self.selected_tile.center_y)
                self.selection_border.visible = True
                self.last_visible_update = 0

    def on_mouse_release(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.active_pause_slider = None
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self.is_dragging = False

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.paused:
            if self.active_pause_slider and buttons & arcade.MOUSE_BUTTON_LEFT:
                self.active_pause_slider.set_from_mouse(x)
            return

        if arcade.MOUSE_BUTTON_RIGHT & buttons and self.is_dragging:
            self.target_camera_x = self.drag_start_camera_x - (x - self.drag_start_x) / self.world_camera.zoom
            self.target_camera_y = self.drag_start_camera_y - (y - self.drag_start_y) / self.world_camera.zoom
            self.clamp_target_camera()

    def on_mouse_motion(self, x, y, dx, dy):
        if self.paused:
            self.hovered_tile = None
            self.hovered_build_button = False
            self.hovered_resource_summary = False
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

        self.hovered_resource_summary = (
            self.resource_summary_rect is not None
            and self.point_in_rect(x, y, self.resource_summary_rect)
        )
        top_button = self.top_nav_button_at(x, y)
        self.hovered_top_nav_key = top_button["key"] if top_button else None
        self.hovered_side_panel_close = (
            self.side_panel_progress > 0 and self.point_in_rect(x, y, self.side_panel_close_rect())
        )
        if (
            self.hovered_top_nav_key
            or self.hovered_side_panel_close
            or y >= self.window.height - TOP_UI_HEIGHT
            or (self.side_panel_progress > 0 and self.point_in_rect(x, y, self.side_panel_rect()))
        ):
            self.hovered_build_button = False
            self.hovered_map_layer_button = False
            self.hovered_map_layer_option = None
            self.hovered_resource_group_button = False
            self.hovered_resource_group_option = None
            self.hovered_time_button = None
            self.hovered_tile = None
            return

        self.hovered_build_button = False
        if self.show_build_controls and self.selected_tile and self.building_dropdown:
            if self.open_building_dropdown:
                self.building_dropdown.hovered_index = self.building_dropdown.option_at(x, y)
            else:
                self.building_dropdown.hovered_index = None

            self.hovered_build_button = self.point_in_rect(x, y, self.build_button_rect())
            if (
                self.hovered_build_button
                or self.building_dropdown.contains_header(x, y)
                or self.point_in_rect(x, y, self.build_panel_rect())
                or self.building_dropdown.hovered_index is not None
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

        if self.active_top_panel_key == "resources" and self.side_panel_progress > 0:
            rows = self.resource_rows()
            over_resource_panel = self.point_in_rect(x, y, self.side_panel_rect())
            over_resource_table = self.point_in_rect(x, y, self.resource_table_rect(rows))
            if over_resource_table:
                self.scroll_resource_rows(-scroll_y)
                return
            if over_resource_panel:
                return

        if self.show_build_controls and self.selected_tile and self.open_building_dropdown and self.building_dropdown:
            self.building_dropdown.scroll(-scroll_y)
            self.building_dropdown.hovered_index = self.building_dropdown.option_at(x, y)
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
            if not self.paused and self.side_panel_target > 0:
                self.close_top_panel()
                return

            if not self.paused and self.show_build_controls and self.open_building_dropdown:
                self.open_building_dropdown = False
                if self.building_dropdown:
                    self.building_dropdown.hovered_index = None
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
