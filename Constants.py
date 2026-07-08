import math
from datetime import datetime
from pathlib import Path

# Константы для гексагональной сетки
HEX_SIZE = 90  # Радиус гексагона
HEX_WIDTH = HEX_SIZE * 2
HEX_HEIGHT = math.sqrt(3) * HEX_SIZE
HEX_WID = HEX_SIZE * math.sqrt(3)  # Ширина для вертикальной ориентации
HEX_HGT = HEX_SIZE * 2  # Высота для вертикальной ориентации
CAMERA_LERP = 0.3
MOVE_SPEED = 5
ZOOM_SPEED = 0.1
MIN_ZOOM = 0.05
MAX_ZOOM = 2.5

# Общие настройки окна, игроков и базовых слоев карты
RESOLUTIONS = [(1024, 768), (1200, 800), (1366, 768), (1600, 900), (1920, 1080)]
MAX_BOTS = 11
OVERVIEW_LOD_ZOOM = 0.2
OVERVIEW_TEXTURE_MAX_SIZE = 1024
STARTING_DIVISIONS_PER_STATE = 10
ARMY_DIVISION_CAPACITY = 20
DIVISION_TEMPLATE_BASE = {
    "basic_infantry": {
        "name": "Пехотная дивизия",
        "icon": "infantry",
        "manpower": 10_000,
        "organization": 100.0,
        "speed": 1.35,
    },
    "tank": {"name": "Танковая дивизия", "icon": "tank", "manpower": 8_000, "organization": 100.0, "speed": 1.7},
    "motorized": {"name": "Моторизованная дивизия", "icon": "motorized", "manpower": 9_000, "organization": 100.0, "speed": 1.9},
    "anti_tank": {"name": "ПТ/ПТУР дивизия", "icon": "anti_tank", "manpower": 7_000, "organization": 100.0, "speed": 1.25},
    "anti_air": {"name": "ПВО дивизия", "icon": "anti_air", "manpower": 7_000, "organization": 100.0, "speed": 1.25},
}
DIVISION_ICON_SIZE = 30
DIVISION_TILE_SIDE_OFFSET_X = 34
DIVISION_TILE_SIDE_OFFSET_Y = -22
DIVISION_LOD_ZOOM = 0.45
DIVISION_LOD_CELL_SIZE = 72
DIVISION_DOUBLE_CLICK_SECONDS = 0.35
DIVISION_SELECTION_DRAG_THRESHOLD = 6
DIVISION_ORG_MOVE_COST_PER_TILE = 1.4
DIVISION_ORG_RECOVERY_PER_DAY = 8.0
DIVISION_LOW_ORG_SPEED_FLOOR = 0.35
DIVISION_ROUTE_COLORS = {
    "move": ((120, 94, 28), (238, 196, 74)),
    "attack": ((132, 42, 42), (238, 92, 82)),
    "retreat": ((36, 76, 132), (92, 164, 244)),
}
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
    ("supply", "Снабжение", True),
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
        "chemistry",
        "Химсырье",
        ["sulfur", "potash", "phosphorite", "apatite", "rubber"],
        (112, 184, 132),
        250_000,
    ),
    (
        "gems",
        "Редкие минералы",
        ["gold", "silver", "rare_earth_metals", "uranium", "graphite", "mica", "quartz"],
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
    "oil": 1.7,
    "natural_gas": 1.7,
    "coal": 1.35,
    "food": 15.0,
    "fertilizer": 2.2,
    "consumer_goods": 12.0,
    "weapons": 0.55,
    "ships": 0.25,
    "electronics": 0.65,
    "construction_goods": 12.0,
    "refined_fuel": 6,
}
BUILDING_TYPES = [
    ("city", "Город"),
    ("village", "Село"),
    ("warehouse", "Склад"),
    ("supply_depot", "Пункт снабжения"),
    ("fuel_storage", "Топливохранилище"),
    ("refinery", "НПЗ"),
    ("oil_gas_rig", "Нефтегазовая вышка"),
    ("industry", "Промзона"),
    ("farms", "Поля/фермы"),
    ("mine", "Шахта"),
    ("port", "Порт"),
]
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
    "oil_gas_rig": 0.12,
    "warehouse": 0.12,
    "fuel_storage": 0.08,
    "refinery": 0.10,
    "industry": 0.10,
    "port": 0.08,
}
STARTING_INFRASTRUCTURE_BUDGET = {
    "village": 1.20,
    "farms": 5.20,
    "mine": 1.20,
    "oil_gas_rig": 0.85,
    "industry": 3.50,
    "port": 0.45,
    "warehouse": 0.35,
    "fuel_storage": 1.10,
    "refinery": 1.00,
}
INFRASTRUCTURE_COVERAGE_COSTS = {
    "village": 0.85,
    "farms": 1.00,
    "mine": 1.15,
    "oil_gas_rig": 1.25,
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
    "oil_gas_rig": (0.05, 0.28),
    "industry": (0.06, 0.32),
    "port": (0.08, 0.30),
    "warehouse": (0.05, 0.26),
    "supply_depot": (0.04, 0.24),
    "fuel_storage": (0.06, 0.34),
    "refinery": (0.05, 0.22),
}
CONSTRUCTION_LEVEL_MULTIPLIER = 1.10
CONSTRUCTION_STEP = 0.05
CONSTRUCTION_STATUS_CHECK_MONTH_FRACTION = 1 / 30
BASE_BUILD_POWER_PER_MONTH = 100.0
BUILDING_CONSTRUCTION_BASE = {
    "city": {
        "work": 520.0,
        "money": 17_500_000,
        "resources": {
            "construction_goods": 36_000,
            "steel": 9_000,
            "machinery": 1_200,
            "refined_fuel": 650,
        },
    },
    "village": {
        "work": 160.0,
        "money": 3_000_000,
        "resources": {
            "construction_goods": 7_000,
            "steel": 1_000,
            "machinery": 180,
            "refined_fuel": 120,
        },
    },
    "farms": {
        "work": 110.0,
        "money": 1_500_000,
        "resources": {
            "construction_goods": 4_500,
            "machinery": 160,
            "refined_fuel": 140,
        },
    },
    "mine": {
        "work": 240.0,
        "money": 5_000_000,
        "resources": {
            "construction_goods": 11_000,
            "steel": 3_500,
            "machinery": 750,
            "refined_fuel": 420,
        },
    },
    "oil_gas_rig": {
        "work": 260.0,
        "money": 6_500_000,
        "resources": {
            "construction_goods": 13_000,
            "steel": 4_600,
            "machinery": 900,
            "refined_fuel": 500,
        },
    },
    "industry": {
        "work": 340.0,
        "money": 8_000_000,
        "resources": {
            "construction_goods": 22_000,
            "steel": 8_000,
            "machinery": 1_800,
            "refined_fuel": 520,
        },
    },
    "port": {
        "work": 420.0,
        "money": 10_000_000,
        "resources": {
            "construction_goods": 20_000,
            "steel": 8_500,
            "machinery": 1_250,
            "refined_fuel": 850,
        },
    },
    "warehouse": {
        "work": 140.0,
        "money": 2_500_000,
        "resources": {
            "construction_goods": 8_000,
            "steel": 1_800,
            "machinery": 220,
            "refined_fuel": 120,
        },
    },
    "supply_depot": {
        "work": 120.0,
        "money": 2_200_000,
        "resources": {
            "construction_goods": 6_500,
            "steel": 1_200,
            "machinery": 240,
            "refined_fuel": 110,
        },
    },
    "fuel_storage": {
        "work": 190.0,
        "money": 4_000_000,
        "resources": {
            "construction_goods": 12_000,
            "steel": 4_800,
            "machinery": 650,
            "refined_fuel": 260,
        },
    },
    "refinery": {
        "work": 460.0,
        "money": 12_000_000,
        "resources": {
            "construction_goods": 28_000,
            "steel": 11_000,
            "machinery": 2_600,
            "refined_fuel": 900,
        },
    },
}
STORAGE_CATEGORIES = ["raw", "semi_finished", "finished", "fuel"]
STORAGE_CATEGORY_LABELS = {
    "raw": "Сырье",
    "semi_finished": "Полуфабрикаты",
    "finished": "Готовая продукция",
    "fuel": "Топливо",
}
STORAGE_CAPACITY_BY_COVERAGE = {
    "raw": {
        "city": 520_000,
        "village": 180_000,
        "warehouse": 1_050_000,
        "supply_depot": 240_000,
        "port": 280_000,
    },
    "semi_finished": {
        "city": 470_000,
        "village": 140_000,
        "warehouse": 820_000,
        "supply_depot": 210_000,
        "port": 240_000,
    },
    "finished": {
        "city": 560_000,
        "village": 200_000,
        "warehouse": 760_000,
        "supply_depot": 190_000,
        "port": 220_000,
    },
}
FUEL_STORAGE_CAPACITY_BY_COVERAGE = {
    "city": 180_000,
    "village": 35_000,
    "port": 220_000,
    "supply_depot": 120_000,
    "fuel_storage": 3_200_000,
    "refinery": 850_000,
    "oil_gas_rig": 420_000,
}
FUEL_STORAGE_RESOURCE_KEYS = {
    "coal",
    "oil",
    "natural_gas",
    "peat",
    "uranium",
    "refined_fuel",
}
SUPPLY_SOURCE_WEIGHTS = {
    "city": 1.00,
    "village": 0.48,
    "warehouse": 0.50,
    "supply_depot": 0.92,
    "port": 0.46,
    "fuel_storage": 0.22,
    "refinery": 0.30,
    "oil_gas_rig": 0.18,
    "industry": 0.18,
}
SUPPLY_RELAY_BUILDING_WEIGHTS = {
    "warehouse": 0.28,
    "supply_depot": 0.72,
    "port": 0.22,
}
SUPPLY_DECAY_PER_HEX = 0.78
SUPPLY_SOURCE_RADIUS = 7
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
    "sulfur": 0.42,
    "phosphorite": 0.40,
    "apatite": 0.36,
}
OIL_GAS_RESOURCE_KEYS = {"oil", "natural_gas"}
STARTING_OIL_GAS_RIG_RESOURCE_WEIGHTS = {
    "oil": 1.0,
    "natural_gas": 0.95,
}
STARTING_SOLID_MINE_RESOURCE_WEIGHTS = {
    key: value
    for key, value in STARTING_MINE_RESOURCE_WEIGHTS.items()
    if key not in OIL_GAS_RESOURCE_KEYS
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
    "refined_fuel",
    "chemicals",
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
PRODUCTION_STAGES = ["raw", "semi_finished", "agriculture", "finished", "upkeep"]
PRODUCTION_MONTH_HOURS = 24 * 30
FARM_FOOD_BASE_RATE = 30_000
FERTILIZER_FOOD_BONUS = 0.30
FERTILIZER_CONSUMPTION_PER_FARM_COVERAGE = 950
STARTING_CONSUMER_GOODS_INDUSTRY_SHARE = 0.30
STARTING_CONSUMER_GOODS_TILE_SHARE = 0.45
POPULATION_INCOME_PER_MILLION = {
    "rural": 150_000,
    "city": 700_000,
    "village": 300_000,
    "farms": 220_000,
    "mine": 360_000,
    "oil_gas_rig": 420_000,
    "industry": 460_000,
    "port": 390_000,
    "warehouse": 240_000,
    "supply_depot": 210_000,
    "fuel_storage": 230_000,
    "refinery": 480_000,
}
POPULATION_INCOME_TYPE_WEIGHTS = {
    "city": 5.0,
    "village": 3.0,
    "farms": 1.6,
    "mine": 1.8,
    "oil_gas_rig": 1.7,
    "industry": 2.3,
    "port": 1.9,
    "warehouse": 1.2,
    "supply_depot": 1.1,
    "fuel_storage": 1.1,
    "refinery": 2.2,
}
COMPANY_INCOME_PER_COVERAGE = {
    "farms": 90_000,
    "mine": 135_000,
    "oil_gas_rig": 165_000,
    "industry": 240_000,
    "port": 160_000,
    "warehouse": 45_000,
    "supply_depot": 52_000,
    "fuel_storage": 65_000,
    "refinery": 220_000,
}
POPULATION_CAPACITY_BASE_LAND = 55_000
POPULATION_CAPACITY_BASE_WATER = 0
POPULATION_CAPACITY_PER_COVERAGE = {
    "city": 10_000_000,
    "village": 2_200_000,
    "farms": 180_000,
    "mine": 130_000,
    "oil_gas_rig": 110_000,
    "industry": 520_000,
    "port": 320_000,
    "warehouse": 90_000,
    "supply_depot": 80_000,
    "fuel_storage": 70_000,
    "refinery": 180_000,
}
POPULATION_MAX_OVERCAPACITY = 1.20
POPULATION_BASE_ANNUAL_GROWTH = 0.012
DEMOGRAPHIC_AGE_SHARES = {
    "children": 0.23,
    "working_age": 0.61,
    "elderly": 0.16,
}
DEMOGRAPHIC_GENDER_SHARES = {
    "male": 0.52,
    "female": 0.48,
}
MILITARY_OBLIGATION_WORKING_AGE_SHARE = 0.54
MOBILIZATION_VOLUNTEER_BASE_SHARE = 0.04
MOBILIZATION_WAR_SUPPORT_WEIGHT = 0.62
MOBILIZATION_STABILITY_WEIGHT = 0.13
MOBILIZATION_LEGITIMACY_WEIGHT = 0.13
MOBILIZATION_VOLUNTEER_MAX_SHARE = 0.82
CITY_NATURAL_ANNUAL_GROWTH = 0.015
VILLAGE_NATURAL_ANNUAL_GROWTH = 0.025
MONEY_GOVERNMENT_BASE_EXPENSE = 450_000
MONEY_GOVERNMENT_PER_MILLION = 48_000
MONEY_GOVERNMENT_PER_TILE = 3_500
MONEY_SOCIAL_BASE_PER_MILLION = 62_000
MONEY_SOCIAL_CITY_BONUS = 70_000
MONEY_SOCIAL_VILLAGE_BONUS = 28_000
MONEY_SOCIAL_PENSION_PER_ELDERLY_MILLION = 230_000
MONEY_SOCIAL_CHILD_SERVICES_PER_CHILD_MILLION = 100_000
MONEY_SOCIAL_DISABILITY_PER_MILLION = 2_200
MONEY_SOCIAL_CITY_SERVICES_PER_MILLION = 70_000
MONEY_SOCIAL_VILLAGE_SERVICES_PER_MILLION = 28_000
MONEY_ARMY_BASE_EXPENSE = 0
INFRASTRUCTURE_UPKEEP_PER_COVERAGE = {
    "city": 145_000,
    "village": 42_000,
    "farms": 18_000,
    "mine": 50_000,
    "oil_gas_rig": 62_000,
    "industry": 92_000,
    "port": 75_000,
    "warehouse": 18_000,
    "supply_depot": 24_000,
    "fuel_storage": 28_000,
    "refinery": 115_000,
}
INDUSTRY_SECTOR_RESOURCE_WEIGHTS = {
    "metallurgy": {
        "iron_ore": 1.0,
        "coal": 0.8,
        "alloying_additives": 0.35,
    },
    "construction_materials": {},
    "chemicals": {
        "natural_gas": 0.9,
        "sulfur": 0.85,
        "phosphorite": 0.35,
        "apatite": 0.35,
        "potash": 0.35,
    },
    "machinery": {
        "iron_ore": 0.6,
        "copper_ore": 0.35,
        "coal": 0.25,
    },
    "vehicles": {
        "iron_ore": 0.45,
        "oil": 0.30,
        "rubber": 0.30,
        "bauxite": 0.20,
    },
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
    "machinery": "Машиностроение",
    "vehicles": "Транспорт",
    "consumer_goods": "Товары",
    "electronics": "Электроника",
    "shipbuilding": "Судостроение",
    "weapons": "Оружие",
}
LIFE_SUPPORT_CONSUMPTION_PER_MILLION = {
    "food": 8100,
    "consumer_goods": 150,
    "construction_goods": 100,
    "refined_fuel": 260,
    "chemicals": 95,
    "vehicles": 10,
    "electronics": 2,
}
SETTLEMENT_UPKEEP_PER_COVERAGE = {
    "city": {
        "construction_goods": 2370,
        "machinery": 120,
        "refined_fuel": 260,
    },
    "village": {
        "construction_goods": 700,
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
            "inputs": {"natural_gas": 0.7, "sulfur": 0.25},
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
            "sector": "vehicles",
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
            "base_rate": 4400,
            "inputs": {},
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
    "phosphorite": "Фосфориты",
    "apatite": "Апатиты",
    "sulfur": "Сера",
    "rubber": "Каучук",
    "graphite": "Графит",
    "mica": "Слюда",
    "quartz": "Кварц",
    "steel": "Сталь",
    "refined_fuel": "Топливо",
    "chemicals": "Химикаты",
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
    "phosphorite": "Сырье для удобрений и роста сельского хозяйства.",
    "apatite": "Источник фосфатов для удобрений и химической промышленности.",
    "sulfur": "Химикаты, удобрения, взрывчатка и переработка нефти.",
    "rubber": "Шины, техника, военное снабжение и потребительские товары.",
    "graphite": "Электроды, батареи, металлургия и высокотехнологичная промышленность.",
    "mica": "Изоляция, электроника, оптика и специальные материалы.",
    "quartz": "Стекло, электроника, оптика и точная промышленность.",
    "steel": "Главный материал для строительства, машин, транспорта и армии.",
    "refined_fuel": "Горючее для транспорта, армии, авиации и промышленности.",
    "chemicals": "Промежуточный ресурс для удобрений, пластмасс, медицины и боеприпасов.",
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
    "supply_depot": "warehouse.png",
    "fuel_storage": "fuel_storage.png",
    "refinery": "refinery.png",
    "oil_gas_rig": "refinery.png",
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
    "supply_depot": 1.18,
    "refinery": 1.15,
    "oil_gas_rig": 1.13,
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
VISUAL_EDGE_TILE_LIMIT = 90
VISUAL_DENSE_TILE_LIMIT = 180
VISUAL_DENSE_SPRITE_LIMIT = 260
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
    ("trade", "Торговля", "economy.png"),
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

# Торговля и общий рынок
TRADE_CONTRACT_STEP = 1_000.0
TRADE_CONTRACT_SHIFT_STEP = 10_000.0
TRADE_BASE_CAPACITY = 8_000.0
TRADE_BASE_MAX_CAPACITY = 160_000.0
TRADE_SELL_LIMIT_MULTIPLIER = 2.0
TRADE_PORT_CAPACITY_PER_COVERAGE = 90_000.0
TRADE_WAREHOUSE_CAPACITY_PER_COVERAGE = 22_000.0
TRADE_SUPPLY_DEPOT_CAPACITY_PER_COVERAGE = 12_000.0
TRADE_SETTLEMENT_CAPACITY_PER_COVERAGE = 8_000.0
TRADE_BUY_PRICE_MARKUP = 1.08
TRADE_SELL_PRICE_MARKDOWN = 0.92
TRADE_WEEKLY_FRACTION = 7 / 30
MARKET_SHOCK_FACTOR = 2.0
MARKET_SHOCK_DECAY = 0.55
MARKET_PRICE_SMOOTHING = 0.42
MARKET_LINKED_PRICE_SMOOTHING = 0.35
MARKET_MAX_WEEKLY_PRICE_MOVE = 0.35
MARKET_HISTORY_LIMIT = 16
TRADE_BASE_PRICES = {
    "coal": 34,
    "oil": 72,
    "natural_gas": 48,
    "peat": 16,
    "uranium": 420,
    "iron_ore": 38,
    "copper_ore": 96,
    "bauxite": 62,
    "lead": 58,
    "zinc": 54,
    "nickel": 118,
    "gold": 1_800,
    "silver": 620,
    "rare_earth_metals": 980,
    "alloying_additives": 180,
    "potash": 44,
    "phosphorite": 40,
    "apatite": 42,
    "sulfur": 58,
    "rubber": 120,
    "graphite": 160,
    "mica": 110,
    "quartz": 92,
    "steel": 135,
    "refined_fuel": 118,
    "chemicals": 145,
    "food": 22,
    "fertilizer": 105,
    "copper_wire": 210,
    "consumer_goods": 260,
    "machinery": 620,
    "vehicles": 850,
    "electronics": 1_250,
    "construction_goods": 170,
    "weapons": 1_100,
    "ships": 4_200,
}
MARKET_RESOURCE_RARITY = {
    "coal": 1.05,
    "oil": 0.85,
    "natural_gas": 0.80,
    "peat": 0.90,
    "uranium": 0.18,
    "iron_ore": 1.00,
    "copper_ore": 0.62,
    "bauxite": 0.55,
    "lead": 0.72,
    "zinc": 0.72,
    "nickel": 0.36,
    "gold": 0.50,
    "silver": 0.58,
    "rare_earth_metals": 0.10,
    "alloying_additives": 0.25,
    "potash": 0.42,
    "phosphorite": 0.50,
    "apatite": 0.46,
    "sulfur": 0.48,
    "rubber": 0.30,
    "graphite": 0.25,
    "mica": 0.28,
    "quartz": 0.42,
    "steel": 0.85,
    "refined_fuel": 0.78,
    "chemicals": 0.64,
    "food": 1.20,
    "fertilizer": 0.52,
    "copper_wire": 0.44,
    "consumer_goods": 0.78,
    "machinery": 0.46,
    "vehicles": 0.36,
    "electronics": 0.22,
    "construction_goods": 0.95,
    "weapons": 0.26,
    "ships": 0.14,
}
MARKET_RESOURCE_VOLATILITY = {
    "rare_earth_metals": 1.80,
    "uranium": 1.55,
    "gold": 1.20,
    "silver": 1.15,
    "electronics": 1.35,
    "ships": 1.45,
    "weapons": 1.30,
    "oil": 1.25,
    "natural_gas": 1.20,
    "rubber": 1.25,
    "food": 0.75,
    "construction_goods": 0.82,
    "iron_ore": 0.85,
    "coal": 0.80,
    "steel": 0.92,
}
MARKET_LINKED_PRICE_EFFECTS = {
    "oil": {"refined_fuel": 0.34, "chemicals": 0.10},
    "natural_gas": {"refined_fuel": 0.12, "fertilizer": 0.16, "chemicals": 0.12},
    "coal": {"refined_fuel": 0.06, "steel": 0.14},
    "peat": {"refined_fuel": 0.03},
    "iron_ore": {"steel": 0.22},
    "copper_ore": {"copper_wire": 0.28, "electronics": 0.08},
    "rare_earth_metals": {"electronics": 0.22},
    "rubber": {"vehicles": 0.12},
    "potash": {"fertilizer": 0.12},
    "phosphorite": {"fertilizer": 0.10},
    "apatite": {"fertilizer": 0.08},
    "sulfur": {"chemicals": 0.10},
    "refined_fuel": {"oil": 0.80, "natural_gas": 0.20, "coal": 0.12, "peat": 0.06},
    "fertilizer": {"natural_gas": 0.34, "potash": 0.24, "phosphorite": 0.18, "apatite": 0.16, "chemicals": 0.22},
    "chemicals": {"natural_gas": 0.22, "oil": 0.16, "sulfur": 0.18},
    "steel": {"iron_ore": 0.45, "coal": 0.26, "alloying_additives": 0.12, "machinery": 0.10, "vehicles": 0.10, "ships": 0.12},
    "copper_wire": {"copper_ore": 0.62, "refined_fuel": 0.08, "electronics": 0.10},
    "machinery": {"steel": 0.34, "copper_wire": 0.18, "chemicals": 0.08, "vehicles": 0.12, "ships": 0.10, "weapons": 0.10},
    "vehicles": {"steel": 0.28, "rubber": 0.20, "refined_fuel": 0.12, "machinery": 0.24},
    "electronics": {"rare_earth_metals": 0.34, "copper_wire": 0.22, "chemicals": 0.10},
    "consumer_goods": {"chemicals": 0.12, "food": 0.08, "refined_fuel": 0.06},
    "construction_goods": {"steel": 0.12, "refined_fuel": 0.06, "machinery": 0.05},
    "weapons": {"steel": 0.26, "machinery": 0.22, "electronics": 0.12},
    "ships": {"steel": 0.38, "machinery": 0.20, "electronics": 0.08, "refined_fuel": 0.08},
}

# Константы для генерации мира - ИЗМЕНЯЙ ИХ ДЛЯ РАЗНЫХ ВАРИАНТОВ
WORLD_SIZE = 100  # Размер мира (чем больше, тем дольше генерация)
# Параметры воды и суши
SEA_LEVEL = 0.28  # Уровень моря (0.2-0.4)
WATER_LEVEL = 0.25  # Уровень воды (0.2-0.3)
DEEP_OCEAN_LEVEL = 0.15  # Глубокий океан (< этого значения)
# Параметры рельефа
MOUNTAIN_FREQUENCY = 0.2  # Частота гор (0.1-0.8)
MOUNTAIN_HEIGHT = 0.6  # Высота гор (0.6-1.0)
HILL_FREQUENCY = 0.35  # Частота холмов (0.3-0.7)
CONTINENT_SIZE = 0.6  # Размер континентов (0.3-1.0)
ISLAND_MODE = False  # Режим островов (True/False)
# Параметры температуры
TROPICAL_WIDTH = 0.1  # Ширина тропической зоны (0.2-0.5)
TEMPERATE_WIDTH = 0.7  # Ширина умеренной зоны (0.3-0.6)
POLAR_TEMP = 0.15  # Температура на полюсах (0.0-0.3)
TROPICAL_TEMP = 0.85  # Температура на экваторе (0.7-1.0)
# Параметры влажности
GLOBAL_MOISTURE = 0.8  # Глобальная влажность (0.3-0.8)
DESERT_DRYNESS = 0.3  # Сухость пустынь (0.2-0.5)
JUNGLE_WETNESS = 0.7  # Влажность джунглей (0.6-0.9)
# Параметры озер
LAKE_FREQUENCY = 0.4  # Частота озер (0.1-0.5)
LAKE_SIZE = 0.4  # Размер озер (0.2-0.6)
# Параметры горных хребтов
RIDGE_FREQUENCY = 0.3  # Частота горных хребтов (0.2-0.6)
RIDGE_SHARPNESS = 0.7  # Резкость хребтов (0.3-1.0)
MOUNTAIN_CHAIN_LENGTH = 0.5  # Длина горных цепей (0.3-0.8)
# Параметры болот и топей
SWAMP_MOISTURE = 0.75  # Влажность для болот (0.7-0.9)
SWAMP_ELEVATION = 0.32  # Высота для болот (0.25-0.4)
MARSH_FREQUENCY = 0.4  # Частота появления болот (0.2-0.6)
BOG_TEMPERATURE = 0.4  # Температура для торфяников (0.3-0.6)
