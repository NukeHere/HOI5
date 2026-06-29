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
    "food": 5.0,
    "fertilizer": 2.2,
    "consumer_goods": 1.35,
    "weapons": 0.55,
    "ships": 0.25,
    "electronics": 0.65,
}
BUILDING_TYPES = [
    ("city", "Город"),
    ("village", "Село"),
    ("warehouse", "Склад"),
    ("fuel_storage", "Топливохранилище"),
    ("refinery", "НПЗ"),
    ("industry", "Промзона"),
    ("farms", "Поля/фермы"),
    ("mine", "Шахта"),
    ("port", "Порт"),
]
BUILDING_STEP = 0.05
TERRAIN_DISPLAY_NAMES = {
    "deep_ocean": "Глубокий океан",
    "ocean": "Океан",
    "shallow_water": "Мелководье",
    "lake": "Озеро",
    "river": "Река",
    "swamp": "Болото",
    "bog": "Торфяник",
    "mangrove": "Мангры",
    "mountains": "Горы",
    "snowy_mountains": "Снежные горы",
    "hills": "Холмы",
    "desert": "Пустыня",
    "plains": "Равнины",
    "tundra": "Тундра",
    "taiga": "Тайга",
    "temperate_forest": "Умеренный лес",
    "jungle": "Джунгли",
    "tropical_rainforest": "Тропический лес",
    "savanna": "Саванна",
    "forest": "Лес",
    "grassland": "Степь",
}
BUILDING_DISPLAY_NAMES = dict(BUILDING_TYPES)
STARTING_POPULATION = 21_000_000
STARTING_BUDGET = 250_000_000.0
CITY_POPULATION_PER_FULL_COVERAGE = 10_000_000
STARTING_REFERENCE_LAND_TILES = 90
STARTING_REFERENCE_MAP_SIZE = 40
STARTING_MIN_SCALE = 0.45
STARTING_MAX_SCALE = 2.40
STARTING_URBAN_POPULATION_SHARE = 0.72
RURAL_POPULATION_WEIGHTS = {
    "village": 3.8,
    "farms": 0.30,
    "mine": 0.16,
    "warehouse": 0.12,
    "fuel_storage": 0.08,
    "refinery": 0.10,
    "industry": 0.10,
    "port": 0.08,
}
STARTING_INFRASTRUCTURE_BUDGET = {
    "village": 0.80,
    "farms": 1.45,
    "mine": 1.05,
    "industry": 1.10,
    "port": 0.45,
    "warehouse": 0.35,
    "fuel_storage": 0.55,
    "refinery": 0.35,
}
INFRASTRUCTURE_COVERAGE_COSTS = {
    "village": 0.85,
    "farms": 1.00,
    "mine": 1.15,
    "industry": 1.35,
    "port": 1.20,
    "warehouse": 0.90,
    "fuel_storage": 0.95,
    "refinery": 1.45,
}
INFRASTRUCTURE_COVERAGE_LIMITS = {
    "city": (0.08, 0.72),
    "village": (0.06, 0.30),
    "farms": (0.08, 0.42),
    "mine": (0.06, 0.34),
    "industry": (0.06, 0.32),
    "port": (0.08, 0.30),
    "warehouse": (0.05, 0.26),
    "fuel_storage": (0.06, 0.34),
    "refinery": (0.05, 0.22),
}
STORAGE_CAPACITY_BY_COVERAGE = {
    "city": 1_800_000,
    "village": 520_000,
    "warehouse": 2_400_000,
}
FUEL_STORAGE_CAPACITY_BY_COVERAGE = {
    "city": 180_000,
    "village": 35_000,
    "port": 220_000,
    "fuel_storage": 3_200_000,
    "refinery": 850_000,
}
FUEL_STORAGE_RESOURCE_KEYS = {
    "coal",
    "oil",
    "natural_gas",
    "peat",
    "uranium",
    "refined_fuel",
}
REFINERY_RESOURCE_WEIGHTS = {
    "oil": 1.0,
    "natural_gas": 0.75,
    "coal": 0.20,
}
STARTING_MINE_RESOURCE_WEIGHTS = {
    "coal": 1.00,
    "oil": 1.00,
    "natural_gas": 0.95,
    "peat": 0.55,
    "iron_ore": 1.00,
    "copper_ore": 0.82,
    "bauxite": 0.64,
    "limestone": 0.72,
    "sand": 0.60,
    "gravel": 0.58,
    "crushed_stone": 0.58,
    "clay": 0.52,
    "salt": 0.38,
    "sulfur": 0.42,
    "phosphorite": 0.40,
    "apatite": 0.36,
}
STARTING_RESOURCE_COMPENSATION_GROUPS = [
    {
        "resources": ["coal", "oil", "natural_gas", "peat"],
        "target": 650_000,
        "stock": [("raw", "coal", 55_000, 180)],
        "budget": 14_000_000,
    },
    {
        "resources": ["iron_ore", "copper_ore", "bauxite"],
        "target": 450_000,
        "stock": [("raw", "iron_ore", 45_000, 280), ("raw", "copper_ore", 20_000, 420)],
        "budget": 18_000_000,
    },
    {
        "resources": ["limestone", "sand", "gravel", "crushed_stone", "clay"],
        "target": 500_000,
        "stock": [("raw", "limestone", 40_000, 90), ("raw", "sand", 40_000, 45), ("raw", "gravel", 30_000, 60)],
        "budget": 12_000_000,
    },
]
STARTING_AGRICULTURE_COMPENSATION = {
    "stock": [("semi_finished", "food", 90_000, 260), ("semi_finished", "fertilizer", 22_000, 320)],
    "budget": 10_000_000,
}
INFRASTRUCTURE_MISSING_BUDGET_VALUE = 30_000_000
INFRASTRUCTURE_COMPENSATION_BUDGET_CAP = 120_000_000
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
PRODUCTION_STAGES = ["raw", "semi_finished", "finished", "upkeep"]
PRODUCTION_MONTH_HOURS = 24 * 30
FARM_FOOD_BASE_RATE = 30_000
FERTILIZER_FOOD_BONUS = 0.30
FERTILIZER_CONSUMPTION_PER_FARM_COVERAGE = 950
INDUSTRY_SECTOR_RESOURCE_WEIGHTS = {
    "metallurgy": {
        "iron_ore": 1.0,
        "coal": 0.8,
        "alloying_additives": 0.35,
    },
    "construction_materials": {
        "limestone": 1.0,
        "sand": 0.75,
        "gravel": 0.65,
        "crushed_stone": 0.55,
        "clay": 0.35,
    },
    "chemicals": {
        "natural_gas": 0.9,
        "sulfur": 0.85,
        "salt": 0.45,
        "phosphorite": 0.35,
        "apatite": 0.35,
        "potash": 0.35,
    },
    "refining": {
        "oil": 1.0,
        "natural_gas": 0.65,
        "coal": 0.25,
    },
    "machinery": {
        "iron_ore": 0.6,
        "copper_ore": 0.35,
        "coal": 0.25,
    },
    "consumer_goods": {},
    "electronics": {
        "copper_ore": 0.85,
        "rare_earth_metals": 0.75,
        "quartz": 0.35,
    },
    "shipbuilding": {
        "iron_ore": 0.45,
        "oil": 0.25,
    },
    "weapons": {
        "iron_ore": 0.55,
        "copper_ore": 0.25,
        "sulfur": 0.25,
    },
}
INDUSTRY_SECTOR_LABELS = {
    "metallurgy": "Металлургия",
    "construction_materials": "Стройматериалы",
    "chemicals": "Химия",
    "refining": "Переработка топлива",
    "machinery": "Машиностроение",
    "consumer_goods": "Товары",
    "electronics": "Электроника",
    "shipbuilding": "Судостроение",
    "weapons": "Оружие",
}
LIFE_SUPPORT_CONSUMPTION_PER_MILLION = {
    "food": 8200,
    "consumer_goods": 1850,
    "construction_goods": 420,
    "refined_fuel": 260,
    "chemicals": 95,
}
SETTLEMENT_UPKEEP_PER_COVERAGE = {
    "city": {
        "construction_goods": 1750,
        "cement": 620,
        "machinery": 120,
        "refined_fuel": 260,
    },
    "village": {
        "construction_goods": 520,
        "cement": 180,
        "machinery": 45,
        "refined_fuel": 80,
    },
}
PRODUCTION_RECIPES = {
    "semi_finished": {
        "steel": {
            "building": "industry",
            "sector": "metallurgy",
            "base_rate": 5200,
            "inputs": {"iron_ore": 2.0, "coal": 0.8},
            "outputs": {"steel": 1.0},
        },
        "cement": {
            "building": "industry",
            "sector": "construction_materials",
            "base_rate": 4200,
            "inputs": {"limestone": 1.2, "sand": 0.7, "gravel": 0.5},
            "outputs": {"cement": 1.0},
        },
        "oil_refining": {
            "building": "refinery",
            "sector": "refining",
            "base_rate": 6200,
            "inputs": {"oil": 1.0},
            "outputs": {"refined_fuel": 0.72, "chemicals": 0.22},
        },
        "chemicals": {
            "building": "industry",
            "sector": "chemicals",
            "base_rate": 3600,
            "inputs": {"natural_gas": 0.7, "sulfur": 0.25, "salt": 0.15},
            "outputs": {"chemicals": 1.0},
        },
        "fertilizer": {
            "building": "industry",
            "sector": "chemicals",
            "base_rate": 2600,
            "inputs": {"chemicals": 0.5, "phosphorite": 0.4, "potash": 0.3},
            "outputs": {"fertilizer": 1.0},
        },
        "copper_wire": {
            "building": "industry",
            "sector": "electronics",
            "base_rate": 2600,
            "inputs": {"copper_ore": 1.2},
            "outputs": {"copper_wire": 1.0},
        },
    },
    "finished": {
        "consumer_goods": {
            "building": "industry",
            "sector": "consumer_goods",
            "base_rate": 3400,
            "inputs": {"food": 0.4, "chemicals": 0.25, "steel": 0.15},
            "outputs": {"consumer_goods": 1.0},
        },
        "machinery": {
            "building": "industry",
            "sector": "machinery",
            "base_rate": 2800,
            "inputs": {"steel": 0.9, "copper_wire": 0.25, "chemicals": 0.2},
            "outputs": {"machinery": 1.0},
        },
        "vehicles": {
            "building": "industry",
            "sector": "machinery",
            "base_rate": 1700,
            "inputs": {"steel": 0.8, "machinery": 0.45, "refined_fuel": 0.2},
            "outputs": {"vehicles": 1.0},
        },
        "electronics": {
            "building": "industry",
            "sector": "electronics",
            "base_rate": 1600,
            "inputs": {"copper_wire": 0.65, "rare_earth_metals": 0.12, "chemicals": 0.25},
            "outputs": {"electronics": 1.0},
        },
        "construction_goods": {
            "building": "industry",
            "sector": "construction_materials",
            "base_rate": 3600,
            "inputs": {"cement": 0.9, "steel": 0.25},
            "outputs": {"construction_goods": 1.0},
        },
        "weapons": {
            "building": "industry",
            "sector": "weapons",
            "base_rate": 1200,
            "inputs": {"steel": 0.8, "machinery": 0.35, "chemicals": 0.25},
            "outputs": {"weapons": 1.0},
        },
        "ships": {
            "building": "industry",
            "sector": "shipbuilding",
            "base_rate": 800,
            "inputs": {"steel": 1.4, "machinery": 0.65, "refined_fuel": 0.25},
            "outputs": {"ships": 1.0},
        },
    },
}
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
    "warehouse": "warehouse.png",
    "fuel_storage": "fuel_storage.png",
    "refinery": "refinery.png",
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
    "warehouse": 1.16,
    "refinery": 1.15,
    "fuel_storage": 1.14,
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
    production_modifiers: dict = None
    production_cache: dict = None
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
        self.last_production_tick_count = 0
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
            self.update_tile_production_cache(self.selected_tile)
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
        return stockpiles

    @staticmethod
    def empty_tile_stockpiles():
        return {
            "raw": {},
            "semi_finished": {},
            "finished": {},
        }

    def tile_storage_capacity(self, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        capacity = 0.0
        for building_key, capacity_per_coverage in STORAGE_CAPACITY_BY_COVERAGE.items():
            capacity += coverage.get(building_key, 0.0) * capacity_per_coverage
        return capacity

    def tile_fuel_storage_capacity(self, tile):
        coverage = getattr(tile, "building_coverage", {}) or {}
        capacity = 0.0
        for building_key, capacity_per_coverage in FUEL_STORAGE_CAPACITY_BY_COVERAGE.items():
            capacity += coverage.get(building_key, 0.0) * capacity_per_coverage
        return capacity

    def distribute_player_stockpiles_to_tiles(self, player):
        for tile in player.tiles:
            tile.resource_stockpiles = self.empty_tile_stockpiles()

        storage_tiles = [
            (tile, self.tile_storage_capacity(tile))
            for tile in player.tiles
            if self.tile_storage_capacity(tile) > 0
        ]
        total_capacity = sum(capacity for _tile, capacity in storage_tiles)
        fuel_storage_tiles = [
            (tile, self.tile_fuel_storage_capacity(tile))
            for tile in player.tiles
            if self.tile_fuel_storage_capacity(tile) > 0
        ]
        total_fuel_capacity = sum(capacity for _tile, capacity in fuel_storage_tiles)
        if total_capacity <= 0:
            fallback_tile = player.capital_tile or next((tile for tile in player.tiles if not self.is_water_tile(tile)), None)
            if fallback_tile:
                self.set_tile_building_coverage(fallback_tile, "warehouse", 0.12, INFRASTRUCTURE_COVERAGE_LIMITS["warehouse"][1])
                storage_tiles = [(fallback_tile, self.tile_storage_capacity(fallback_tile))]
                total_capacity = storage_tiles[0][1]
        if total_fuel_capacity <= 0:
            fallback_tile = player.capital_tile or next((tile for tile in player.tiles if not self.is_water_tile(tile)), None)
            if fallback_tile:
                self.set_tile_building_coverage(fallback_tile, "fuel_storage", 0.14, INFRASTRUCTURE_COVERAGE_LIMITS["fuel_storage"][1])
                fuel_storage_tiles = [(fallback_tile, self.tile_fuel_storage_capacity(fallback_tile))]
                total_fuel_capacity = fuel_storage_tiles[0][1]
        if total_capacity <= 0:
            return

        stockpiles = self.ensure_player_stockpiles(player)
        for category_key, bucket in stockpiles.items():
            for resource_key, amount in bucket.items():
                if amount <= 0:
                    continue
                target_tiles = fuel_storage_tiles if resource_key in FUEL_STORAGE_RESOURCE_KEYS else storage_tiles
                target_capacity = total_fuel_capacity if resource_key in FUEL_STORAGE_RESOURCE_KEYS else total_capacity
                if target_capacity <= 0:
                    continue
                for tile, capacity in target_tiles:
                    share = capacity / target_capacity
                    tile_bucket = tile.resource_stockpiles.setdefault(category_key, {})
                    tile_bucket[resource_key] = tile_bucket.get(resource_key, 0.0) + amount * share

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

        scores["consumer_goods"] += nearby_city * 0.55 + nearby_village * 0.18 + passability * 0.12
        scores["machinery"] += nearby_city * 0.28 + nearby_mine * 0.24 + passability * 0.14
        scores["metallurgy"] += nearby_mine * 0.18
        scores["construction_materials"] += nearby_city * 0.16 + nearby_mine * 0.10
        scores["chemicals"] += nearby_refinery * 0.24 + nearby_city * 0.10
        scores["refining"] += nearby_refinery * 0.25 + nearby_port * 0.16
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

        allocation = {ranked[0][0]: 1.0}
        if len(ranked) > 1 and ranked[1][1] >= ranked[0][1] * 0.72:
            allocation[ranked[0][0]] = 0.78
            allocation[ranked[1][0]] = 0.22
        if len(ranked) > 2 and ranked[2][1] >= ranked[0][1] * 0.88:
            first, second = list(allocation.keys())[:2]
            allocation[first] = 0.70
            allocation[second] = 0.20
            allocation[ranked[2][0]] = 0.10

        total = sum(allocation.values()) or 1.0
        tile.industry_allocation = {
            sector: value / total
            for sector, value in allocation.items()
        }
        return tile.industry_allocation

    def assign_starting_industry_allocations(self, player):
        for tile in player.tiles:
            self.assign_industry_allocation(player, tile)

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
                abundance = min(1.0, math.log10(max(0.0, float(mass)) + 1) / math.log10(1_500_000 + 1))
                weight = STARTING_MINE_RESOURCE_WEIGHTS.get(key, 0.35)
                output = mine_coverage * abundance * (0.55 + weight) * mining_efficiency * 5200
                self.add_production_amount(cache, "raw", "outputs", key, output)

        farms_coverage = coverage.get("farms", 0.0)
        if farms_coverage > 0:
            agriculture_efficiency = modifiers.get("agriculture_efficiency", 1.0)
            output = (
                farms_coverage
                * self.agriculture_score(tile)
                * agriculture_efficiency
                * FARM_FOOD_BASE_RATE
                * (1.0 + FERTILIZER_FOOD_BONUS)
            )
            self.add_production_amount(cache, "raw", "outputs", "food", output)
            self.add_production_amount(
                cache,
                "upkeep",
                "inputs",
                "fertilizer",
                farms_coverage * FERTILIZER_CONSUMPTION_PER_FARM_COVERAGE,
            )

        allocation = getattr(tile, "industry_allocation", None)
        if allocation is None or (coverage.get("industry", 0.0) > 0 and not allocation):
            allocation = self.assign_industry_allocation(player, tile)
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

    def stockpile_amount(self, player, key):
        category = self.resource_category_for_key(key)
        return self.ensure_player_stockpiles(player).get(category, {}).get(key, 0.0)

    def add_to_stockpile(self, player, key, amount):
        if amount <= 0:
            return
        category = self.resource_category_for_key(key)
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(category, {})
        bucket[key] = bucket.get(key, 0.0) + amount

    def consume_from_stockpile(self, player, key, amount):
        if amount <= 0:
            return 0.0
        category = self.resource_category_for_key(key)
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(category, {})
        available = bucket.get(key, 0.0)
        consumed = min(available, amount)
        bucket[key] = max(0.0, available - consumed)
        return consumed

    def run_production_stage(self, player, stage, month_fraction):
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

    def run_production_tick(self, player, elapsed_hours=None):
        if player.production_cache is None:
            self.recalculate_state_production_cache(player)
        month_fraction = max(0.0, (elapsed_hours or 0.0) / PRODUCTION_MONTH_HOURS)
        if month_fraction <= 0:
            return
        for stage in PRODUCTION_STAGES:
            self.run_production_stage(player, stage, month_fraction)
        self.distribute_player_stockpiles_to_tiles(player)

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

        resource_score = self.weighted_resource_score(tile, STARTING_MINE_RESOURCE_WEIGHTS)
        if resource_score <= 0:
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(resource_score * 0.74 + nearby_city * 0.12 + passability * 0.14)

    def industry_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_mine = self.nearby_coverage_score(player, tile, ["mine"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        nearby_resources = self.nearby_resource_score(player, tile, STARTING_MINE_RESOURCE_WEIGHTS, 2)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_city * 0.38
            + nearby_resources * 0.18
            + nearby_mine * 0.16
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
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_settlement * 0.28
            + nearby_industry * 0.22
            + nearby_mine * 0.16
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
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_settlement * 0.24
            + nearby_industry * 0.24
            + nearby_fuel * 0.20
            + nearby_port * 0.14
            + passability * 0.18
        )

    def refinery_score(self, player, tile):
        if self.is_water_tile(tile):
            return 0.0

        nearby_fuel = self.nearby_resource_score(player, tile, REFINERY_RESOURCE_WEIGHTS, 3)
        nearby_city = self.nearby_coverage_score(player, tile, ["city"], 3)
        nearby_industry = self.nearby_coverage_score(player, tile, ["industry"], 2)
        nearby_port = self.nearby_coverage_score(player, tile, ["port"], 3)
        passability = self.clamp01(getattr(tile, "passability", 0.0))
        return self.clamp01(
            nearby_fuel * 0.34
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
        stockpiles = self.ensure_player_stockpiles(player)
        bucket = stockpiles.setdefault(bucket_key, {})
        bucket[resource_key] = bucket.get(resource_key, 0.0) + amount

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
        self.rebuild_state_borders()

        print(
            f"Created {len(self.players)} states, "
            f"start territory radius: {self.start_territory_radius}"
        )

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
        self.draw_hex_info_panel()
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
        if not self.human_player.production_cache:
            self.recalculate_state_production_cache(self.human_player)
        stockpiles = self.ensure_player_stockpiles(self.human_player)
        if self.resource_panel_category == "raw":
            raw = self.human_player.resource_totals.get("raw", {})
            raw_stock = stockpiles.get("raw", {})
            keys = list(RAW_RESOURCE_NAMES)
            for key in sorted(raw.keys()):
                if key not in keys:
                    keys.append(key)
            rows = []
            for key in keys:
                production = self.production_amount_for_key(self.human_player, key, "outputs")
                consumption = self.production_amount_for_key(self.human_player, key, "inputs")
                stock = raw_stock.get(key, 0.0)
                rows.append({
                    "key": key,
                    "ground": raw.get(key, 0.0),
                    "stock": stock,
                    "production": production,
                    "consumption": consumption,
                    "months": self.resource_duration_months(stock, production, consumption),
                })
            return rows

        names = SEMI_FINISHED_RESOURCE_NAMES if self.resource_panel_category == "semi_finished" else FINISHED_RESOURCE_NAMES
        stock = stockpiles.get(self.resource_panel_category, {})
        rows = []
        for key in names:
            production = self.production_amount_for_key(self.human_player, key, "outputs")
            consumption = self.production_amount_for_key(self.human_player, key, "inputs")
            stock_amount = stock.get(key, 0.0)
            rows.append({
                "key": key,
                "ground": None,
                "stock": stock_amount,
                "production": production,
                "consumption": consumption,
                "months": self.resource_duration_months(stock_amount, production, consumption),
            })
        return rows

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
                self.format_resource_duration(row["months"]),
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
        bottom_padding = 96 if self.selected_tile and (getattr(self.selected_tile, "building_coverage", {}) or {}).get("industry", 0.0) > 0 else 58
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
        if not self.selected_tile:
            return False
        coverage = getattr(self.selected_tile, "building_coverage", {}) or {}
        return coverage.get("industry", 0.0) > 0

    def close_hex_panel(self):
        self.selected_tile = None
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
        if self.selection_border:
            self.selection_border.visible = False

    def trigger_hex_build_placeholder(self):
        self.hex_panel_message = "Строительство будет добавлено позже"
        self.hex_panel_message_timer = 2.0

    def toggle_hex_specialization_mode(self):
        self.hex_panel_specialization_mode = not self.hex_panel_specialization_mode
        self.hex_panel_scroll = 0.0
        self.hex_panel_message = ""

    def set_selected_tile_industry_sector(self, sector):
        tile = self.selected_tile
        if not tile or not self.selected_tile_has_industry():
            return
        tile.industry_allocation = {sector: 1.0}
        self.update_tile_production_cache(tile)
        self.hex_panel_message = f"Специализация: {INDUSTRY_SECTOR_LABELS.get(sector, sector)}"
        self.hex_panel_message_timer = 2.0
        self.hex_panel_scroll = 0.0

    def toggle_hex_resources_expanded(self):
        self.hex_resources_expanded = not self.hex_resources_expanded
        self.clamp_hex_panel_scroll()

    def draw_hex_info_panel(self):
        tile = self.selected_tile
        if not tile:
            return

        panel_x, panel_y, panel_width, panel_height = self.hex_panel_rect()
        content_bottom, content_top = self.hex_panel_content_bounds()
        content_width = panel_width - 32
        visible_content_height = max(1, content_top - content_bottom)
        self.hex_specialization_row_rects = []
        self.hex_resources_toggle_rect = None

        def visible_y(draw_y, margin=24):
            return content_bottom - margin <= draw_y <= content_top + margin

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

        title_y = panel_y + panel_height - 28
        self.draw_ui_text(f"Гекс {tile.q}:{tile.r}", panel_x + 16, title_y, arcade.color.WHITE, 18, anchor_y="center")
        y = content_top + self.hex_panel_scroll

        owner_name = tile.owner.name if tile.owner else "Нейтральная территория"
        info_rows = [
            ("Владелец", owner_name),
            ("Население", self.format_population(self.estimated_tile_population(tile))),
            ("Местность", self.terrain_display_name(tile.terrain_type)),
            ("Проходимость", self.format_percent(getattr(tile, "passability", 0.0))),
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

        resource_rows = self.hex_resource_rows(tile)
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
        y = panel_section("Строения", y)
        coverage = getattr(tile, "building_coverage", {}) or {}
        buildings = [key for key in getattr(tile, "buildings", []) if key in BUILDING_DISPLAY_NAMES]
        if coverage:
            for key, value in sorted(coverage.items(), key=lambda item: item[0]):
                label = BUILDING_DISPLAY_NAMES.get(key, key)
                panel_text(f"{label}: {value:.0%}", panel_x + 16, y, (224, 234, 244), 11)
                y -= 16
        elif buildings:
            for key in buildings:
                panel_text(BUILDING_DISPLAY_NAMES.get(key, key), panel_x + 16, y, (224, 234, 244), 11)
                y -= 16
        else:
            panel_text("Пока нет", panel_x + 16, y, (180, 192, 205), 11)
            y -= 16

        if self.selected_tile_has_industry():
            y -= 8
            y = panel_section("Производство", y)
            allocation = getattr(tile, "industry_allocation", {}) or {}
            if not allocation:
                allocation = self.assign_industry_allocation(tile.owner, tile) if tile.owner else {}
            modifiers = tile.owner.production_modifiers if tile.owner else {}
            efficiency = self.specialization_efficiency(
                allocation,
                modifiers.get("industry_diversification_penalty", 0.9),
                modifiers.get("industry_free_specializations", 1),
            )
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
            ("Тип", self.climate_display_name(tile)),
            ("Температура", self.format_percent(getattr(tile, "temperature", 0.0))),
            ("Влажность", self.format_percent(getattr(tile, "moisture", 0.0))),
            ("Высота", self.format_percent(getattr(tile, "elevation", 0.0))),
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
        if self.hex_panel_message_timer > 0:
            self.hex_panel_message_timer = max(0.0, self.hex_panel_message_timer - delta_time)
            if self.hex_panel_message_timer == 0:
                self.hex_panel_message = ""

        if self.paused or self.game_over:
            return

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
            for player in self.players:
                self.run_production_tick(player, elapsed_hours)
            self.last_production_tick_count = snapshot.tick_count

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
                    self.trigger_hex_build_placeholder()
                    return
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
            previous_tile = self.selected_tile
            self.selected_tile = self.get_tile_at(world_x, world_y)
            if self.selected_tile:
                if self.selected_tile != previous_tile:
                    self.hex_panel_scroll = 0.0
                    self.hex_panel_content_height = 0.0
                    self.hex_resources_expanded = False
                    self.hex_resources_toggle_rect = None
                    self.hex_panel_specialization_mode = False
                self.selection_border.position = (self.selected_tile.center_x, self.selected_tile.center_y)
                self.selection_border.visible = True
                self.last_visible_update = 0
            else:
                self.close_hex_panel()

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
            self.hovered_hex_panel_close = False
            self.hovered_hex_build_button = False
            self.hovered_hex_specialization_button = False
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
        if (
            self.hovered_top_nav_key
            or self.hovered_side_panel_close
            or over_hex_panel
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
