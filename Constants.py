import math

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
