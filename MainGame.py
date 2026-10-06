import arcade
import random
import json
import math
import struct
import time
import textwrap
import heapq
from collections import deque
from perlin_noise import PerlinNoise
from PIL import Image, ImageDraw
from pyglet.graphics import Batch
from arcade.gl import BufferDescription
from Constants import *
from HexTile import HexTile
from MapData import MapTileData
from Settings import apply_window_settings_safely, create_window_with_fallback, load_settings, save_settings

from air_system import AirSystemMixin
from economy_system import EconomySystemMixin
from construction_system import ConstructionSystemMixin
from game_models import (
    AirImpactDecal,
    Army,
    Battle,
    BattlePlan,
    Division,
    FieldHelipadProject,
    StatePlayer,
)
from performance import PerformanceProfiler
from simulation_core import LocalSimulationClient, LocalSimulationServer
from ui_controls import HudButton, PauseButton, PauseDropdown, PauseSlider
from ui_panels import UIPanelsMixin
from country_panel import CountryPanelMixin


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


class Game(CountryPanelMixin, AirSystemMixin, EconomySystemMixin, ConstructionSystemMixin, UIPanelsMixin, arcade.View):
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
        self.division_lookup = {}
        self.division_templates = self.load_division_templates()
        self.battles = {}
        self.airbases = []
        self.air_wings = []
        self.air_wing_lookup = {}
        self.air_wings_by_tile = {}
        self.air_defense_units = []
        self.air_defense_unit_lookup = {}
        self.air_defense_units_by_tile = {}
        self.air_salvos = []
        self.air_salvo_lookup = {}
        self.air_salvo_tile_lookup = {}
        self.air_salvo_tile_cache_revision = -1
        self.air_salvo_revision = 0
        self.air_attack_salvos = []
        self.air_attack_salvo_lookup = {}
        self.air_asset_revision = 0
        self.air_impact_decals = []
        self.field_helipad_projects = []
        self.next_division_id = 1
        self.next_army_id = 1
        self.next_battle_plan_id = 1
        self.next_airbase_id = 1
        self.next_air_wing_id = 1
        self.next_air_defense_unit_id = 1
        self.next_air_salvo_id = 1
        self.next_air_attack_salvo_id = 1
        self.next_field_helipad_project_id = 1
        self.selected_division_ids = set()
        self.selected_air_wing_id = None
        self.selected_air_wing_ids = set()
        self.selected_air_defense_unit_id = None
        self.air_wing_target_mode_id = None
        self.air_wing_rebase_mode_id = None
        self.air_wing_target_mode_ids = set()
        self.air_wing_rebase_mode_ids = set()
        self.air_defense_move_mode_id = None
        self.hex_air_wing_row_rects = []
        self.hex_air_wing_button_rects = []
        self.hex_air_defense_row_rects = []
        self.hex_air_defense_button_rects = []
        self.hex_airbase_upgrade_button_rect = None
        self.division_shape_list = arcade.shape_list.ShapeElementList()
        self.air_asset_shape_list = arcade.shape_list.ShapeElementList()
        self.air_wing_overlay_cache_key = None
        self.air_wing_overlay_range_shapes = arcade.shape_list.ShapeElementList()
        self.air_wing_overlay_unavailable_shapes = arcade.shape_list.ShapeElementList()
        self.air_wing_overlay_area_shapes = arcade.shape_list.ShapeElementList()
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
        self.air_wing_list_row_rects = []
        self.air_wing_list_panel_rect = None
        self.air_wing_command_add_rect = None
        self.air_wing_command_button_rects = []
        self.air_wing_mission_menu_wing_id = None
        self.air_wing_mission_option_rects = []
        self.air_wing_target_menu_wing_id = None
        self.air_wing_target_option_rects = []
        self.air_wing_edit_menu_wing_id = None
        self.air_wing_edit_button_rects = []
        self.air_wing_risk_menu_wing_id = None
        self.air_wing_risk_option_rects = []
        self.air_wing_dropdown_panel_rects = []
        self.hovered_air_wing_control = None
        self.air_wing_creation_open = False
        self.air_wing_creation_panel_rect = None
        self.air_wing_creation_row_rects = []
        self.air_wing_creation_minus_rect = None
        self.air_wing_creation_plus_rect = None
        self.air_wing_creation_slider_rect = None
        self.air_wing_creation_create_rect = None
        self.air_wing_creation_type = None
        self.air_wing_creation_count = 1
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
        self.army_plan_preview_target_locked = False
        self.army_plan_preview_last_tile = None
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
        self.profiler = PerformanceProfiler()
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
        self.performance_overlay_batch = Batch()
        self.performance_overlay_texts = []
        self.performance_overlay_rows = []
        self.performance_overlay_last_update = 0.0
        self.performance_overlay_update_interval = 0.25
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
        self.air_defense_overlay_enabled = False
        self.hovered_map_layer_filter_option = None
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
        self.economy_panel_cache = None
        self.hex_panel_snapshot_cache = None
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
        self.trade_batch = Batch()
        self.trade_text_pool = []
        self.trade_text_pool_cursor = 0
        self.trade_text_pool_max_used = 0
        self.trade_table_shape_list = arcade.shape_list.ShapeElementList()
        self.trade_table_shape_cache_key = None
        self.trade_table_shape_actions = []
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

    @staticmethod
    def clean_positive_amounts(values):
        cleaned = {}
        if not isinstance(values, dict):
            return cleaned
        for key, amount in values.items():
            try:
                value = float(amount)
            except (TypeError, ValueError):
                continue
            if value > 0:
                cleaned[str(key)] = value
        return cleaned

    def default_division_supply_capacity(self, template):
        manpower_ratio = max(0.25, float(template.get("manpower", 10_000)) / 10_000)
        infantry_share = self.clamp01(float(template.get("infantry_share", 0.92)))
        vehicle_share = self.clamp01(float(template.get("vehicle_share", 0.08)))
        combat_weight = max(0.5, float(template.get("front_width", 20.0)) / 20.0)
        capacity = {}
        for key, base_amount in DIVISION_DEFAULT_SUPPLY_CAPACITY.items():
            if key in ("vehicles", "tank_ammo", "refined_fuel", "spare_parts"):
                scale = manpower_ratio * (0.25 + vehicle_share * 1.35)
            elif key in ("artillery_ammo", "anti_air_ammo"):
                scale = manpower_ratio * (0.55 + combat_weight * 0.35 + vehicle_share * 0.20)
            else:
                scale = manpower_ratio * (0.35 + infantry_share * 0.85 + vehicle_share * 0.20)
            capacity[key] = max(0.0, base_amount * scale)
        return capacity

    def default_division_combat_supply_use(self, template):
        manpower_ratio = max(0.25, float(template.get("manpower", 10_000)) / 10_000)
        infantry_share = self.clamp01(float(template.get("infantry_share", 0.92)))
        vehicle_share = self.clamp01(float(template.get("vehicle_share", 0.08)))
        soft_attack = max(0.0, float(template.get("soft_attack", 18.0)))
        hard_front = max(0.0, float(template.get("hard_front_attack", 3.0)))
        hard_top = max(0.0, float(template.get("hard_top_attack", 1.0)))
        speed = max(0.1, float(template.get("speed", 1.35)))
        base_use = DIVISION_DEFAULT_COMBAT_SUPPLY_USE_PER_HOUR
        return {
            "small_arms_ammo": max(base_use["small_arms_ammo"] * 0.25, (6.0 + soft_attack * 0.55) * infantry_share * manpower_ratio),
            "artillery_ammo": max(base_use["artillery_ammo"] * 0.15, (soft_attack - 10.0) * 0.16 * manpower_ratio),
            "tank_ammo": max(base_use["tank_ammo"] * vehicle_share * 0.25, hard_front * vehicle_share * 0.18 * manpower_ratio),
            "anti_air_ammo": max(base_use["anti_air_ammo"] * 0.15, hard_top * 0.10 * manpower_ratio),
            "refined_fuel": max(base_use["refined_fuel"] * vehicle_share * 0.25, vehicle_share * speed * 4.2 * manpower_ratio),
            "field_supplies": max(base_use["field_supplies"] * 0.25, 0.85 * manpower_ratio),
        }

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
        explicit_supply_capacity = self.clean_positive_amounts(template.get("supply_capacity", {}))
        explicit_combat_supply_use = self.clean_positive_amounts(template.get("combat_supply_use", {}))
        supply_capacity = explicit_supply_capacity or self.default_division_supply_capacity(template)
        combat_supply_use = explicit_combat_supply_use or self.default_division_combat_supply_use(template)
        template["supply_capacity"] = supply_capacity
        template["combat_supply_use"] = combat_supply_use
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
            max_manpower=template["manpower"],
            supply_capacity=dict(template["supply_capacity"]),
            supply_stock=dict(template["supply_capacity"]),
            combat_supply_use=dict(template["combat_supply_use"]),
        )
        self.next_division_id += 1
        return division

    def register_division(self, division):
        if not division:
            return None
        if division.owner and division not in division.owner.divisions:
            division.owner.divisions.append(division)
        if division not in self.divisions:
            self.divisions.append(division)
        self.division_lookup[division.id] = division
        return division



    def setup(self):
        self.grid_width = self.map_size
        self.grid_height = self.map_size
        self.world_generator = WorldGenerator(self.grid_width, self.grid_height, self.world_seed)
        self.create_hex_grid()
        self.build_tile_spatial_hash()
        self.setup_players_and_states()
        self.register_simulation_command_handlers()
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

    def register_simulation_command_handlers(self):
        self.simulation_server.register_command_handler("political_action", self.handle_political_command)
        self.simulation_server.register_command_handler("enqueue_construction", self.handle_enqueue_construction_command)
        self.simulation_server.register_command_handler("cancel_construction", self.handle_cancel_construction_command)

    def submit_player_command(self, command_type, payload=None, player=None):
        player = player or self.human_player
        player_id = player.id if player else None
        self.simulation_client.request_command(command_type, player_id=player_id, payload=payload or {})

    def player_by_id(self, player_id):
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def handle_enqueue_construction_command(self, command):
        player = self.player_by_id(command.player_id)
        tile = self.tile_for_key(command.payload.get("tile_key"))
        building_key = command.payload.get("building_key")
        steps = max(1, int(command.payload.get("steps", 1) or 1))
        if not player or not tile:
            return False
        return self.enqueue_construction_steps(player, tile, building_key, steps) > 0

    def handle_cancel_construction_command(self, command):
        player = self.player_by_id(command.player_id)
        tile = self.tile_for_key(command.payload.get("tile_key"))
        building_key = command.payload.get("building_key")
        if not player or not tile:
            return False
        return self.cancel_queued_construction(player, tile, building_key)

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

    def monthly_company_income(self, player):
        income = 0.0
        for tile in player.tiles:
            coverage = getattr(tile, "building_coverage", {}) or {}
            for building_key, amount_per_coverage in COMPANY_INCOME_PER_COVERAGE.items():
                income += self.effective_building_coverage(tile, building_key, coverage.get(building_key, 0.0)) * amount_per_coverage
        return income

    def monthly_tile_company_income(self, tile):
        income = 0.0
        coverage = getattr(tile, "building_coverage", {}) or {}
        for building_key, amount_per_coverage in COMPANY_INCOME_PER_COVERAGE.items():
            income += self.effective_building_coverage(tile, building_key, coverage.get(building_key, 0.0)) * amount_per_coverage
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
        political_programs = self.politics.program_expenses(player)
        _, debt_service = self.politics.monthly_debt_flows(player.id)
        return {
            "army": army,
            "government": government,
            "social": social,
            "social_breakdown": social_breakdown,
            "infrastructure": infrastructure,
            "political_programs": political_programs,
            "debt_service": debt_service,
            "total": army + government + social + infrastructure + political_programs + debt_service,
        }

    def recalculate_monthly_balance(self, player):
        population_income = self.monthly_population_income(player) * player.politics.tax_multiplier("population")
        base_company_income = self.monthly_company_income(player)
        # The economy has no individual firms yet; keep this proxy explicit.
        smb_income = base_company_income * 0.65 * player.politics.tax_multiplier("smb")
        large_income = base_company_income * 0.35 * player.politics.tax_multiplier("large")
        company_income = smb_income + large_income
        trade_balance = self.estimate_monthly_trade_flows(player)["money_balance"]
        expenses = self.monthly_expenses(player)
        loan_repayments, _ = self.politics.monthly_debt_flows(player.id)
        total_income = population_income + company_income + trade_balance + loan_repayments
        total_balance = total_income - expenses["total"]
        player.monthly_trade_balance = trade_balance
        player.monthly_income_breakdown = {
            "population": population_income,
            "companies": company_income,
            "smb": smb_income,
            "large": large_income,
            "loan_repayments": loan_repayments,
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

    def cached_economy_snapshot(self, player):
        if not player:
            return {}
        cache_key = (
            id(player),
            player.budget,
            player.population or 0.0,
            player.monthly_balance,
            player.monthly_trade_balance,
            id(player.monthly_income_breakdown),
            id(player.monthly_expenses_breakdown),
        )
        if self.economy_panel_cache and self.economy_panel_cache.get("key") == cache_key:
            return self.economy_panel_cache["snapshot"]
        snapshot = self.economy_snapshot(player)
        player.economy_current_snapshot = snapshot
        self.economy_panel_cache = {"key": cache_key, "snapshot": snapshot}
        return snapshot

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
        # Political simulation settles loans and actual funded program-hours.
        operating_expenses = (expenses.get("total", 0.0) - expenses.get("debt_service", 0.0)
                              - expenses.get("political_programs", 0.0))
        player.budget += (population_income + company_income - operating_expenses) * month_fraction
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
            delta = self.tile_population_growth_delta(tile, month_fraction, growth_multiplier)
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

    def tile_population_growth_delta(self, tile, month_fraction, growth_multiplier):
        population = self.tile_population(tile)
        capacity = self.tile_population_capacity(tile)
        free = max(0.0, self.tile_population_max_capacity(tile) - population)
        if population <= 0 or capacity <= 0 or growth_multiplier <= 0:
            return 0.0
        pressure = max(0.0, 0.1 + 0.9 * ((POPULATION_MAX_OVERCAPACITY * capacity - population) / population))
        return min(free, population * POPULATION_BASE_ANNUAL_GROWTH / 12 * month_fraction * growth_multiplier * pressure)

    def population_monthly_forecast(self, player):
        multiplier = self.population_growth_multiplier(player)
        if multiplier > 0:
            return sum(self.tile_population_growth_delta(tile, 1, multiplier) for tile in player.tiles)
        population = sum(self.tile_population(tile) for tile in player.tiles)
        return max(-population, population * POPULATION_BASE_ANNUAL_GROWTH / 12 * multiplier)

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

    def building_damage_rows_for_tiles(self, tiles):
        damage_totals = {}
        coverage_totals = {}
        for tile in tiles:
            for key, coverage in (getattr(tile, "building_coverage", {}) or {}).items():
                if coverage <= 0:
                    continue
                damage = self.building_damage_fraction(tile, key)
                coverage_totals[key] = coverage_totals.get(key, 0.0) + coverage
                damage_totals[key] = damage_totals.get(key, 0.0) + coverage * damage
        return {
            key: damage_totals.get(key, 0.0) / max(0.001, coverage_totals.get(key, 0.0))
            for key in coverage_totals
            if damage_totals.get(key, 0.0) > 0.001
        }

    def airbase_on_tile(self, tile):
        return getattr(tile, "airbase", None) if tile else None

    def air_wings_on_tile(self, tile, owner=None):
        if not tile:
            return []
        wings = self.air_wings_by_tile.get(self.indexed_tile_key(tile), [])
        if owner is None:
            return list(wings)
        return [wing for wing in wings if wing.owner is owner]

    def air_defense_units_on_tile(self, tile, owner=None):
        if not tile:
            return []
        units = self.air_defense_units_by_tile.get(self.indexed_tile_key(tile), [])
        if owner is None:
            return list(units)
        return [unit for unit in units if unit.owner is owner]

    def field_helipad_projects_on_tile(self, tile, owner=None):
        if not tile:
            return []
        return [
            project for project in self.field_helipad_projects
            if project.tile is tile and (owner is None or project.owner is owner)
        ]

    def air_wing_counts_by_type_for_tiles(self, tiles):
        counts = {}
        for tile in tiles:
            for wing in self.air_wings_on_tile(tile):
                for aircraft_type, count in self.air_wing_composition(wing).items():
                    counts[aircraft_type] = counts.get(aircraft_type, 0) + count
        return counts

    def air_wings_for_tiles(self, tiles):
        wings = []
        seen = set()
        for tile in tiles:
            for wing in self.air_wings_on_tile(tile):
                if wing.id in seen:
                    continue
                seen.add(wing.id)
                wings.append(wing)
        return sorted(wings, key=lambda wing: (wing.owner.id if wing.owner else 0, wing.aircraft_type, wing.id))

    def air_defense_units_for_tiles(self, tiles):
        units = []
        seen = set()
        for tile in tiles:
            for unit in self.air_defense_units_on_tile(tile):
                if unit.id in seen:
                    continue
                seen.add(unit.id)
                units.append(unit)
        return sorted(units, key=lambda unit: (unit.owner.id if unit.owner else 0, unit.unit_class, unit.id))

    def player_aircraft_inventory_by_type(self, player):
        totals = {}
        if not player:
            return totals
        for aircraft_type, count in (getattr(player, "aircraft_stockpile", {}) or {}).items():
            totals.setdefault(aircraft_type, {"based": 0, "reserve": 0})
            totals[aircraft_type]["reserve"] += int(count)
        for wing in getattr(player, "air_wings", []) or []:
            for aircraft_type, count in self.air_wing_composition(wing).items():
                totals.setdefault(aircraft_type, {"based": 0, "reserve": 0})
                totals[aircraft_type]["based"] += max(0, int(count))
        return totals

    def airbase_load_summary(self, tile):
        if not tile:
            return None
        airbase = self.airbase_on_tile(tile)
        fixed_load = self.based_aircraft_load(tile, helicopter=False)
        helicopter_load = self.based_aircraft_load(tile, helicopter=True)
        if airbase:
            return {
                "fixed_load": fixed_load,
                "fixed_capacity": max(0, int(airbase.aircraft_capacity)),
                "helicopter_load": helicopter_load,
                "helicopter_capacity": max(0, int(airbase.helicopter_capacity)),
            }
        helipad_capacity = self.field_helipad_capacity_for_wing(tile, "attack_helicopter")
        if helipad_capacity > 0:
            return {
                "fixed_load": 0,
                "fixed_capacity": 0,
                "helicopter_load": helicopter_load,
                "helicopter_capacity": helipad_capacity,
            }
        return None

    def air_defense_counts_by_class_for_tiles(self, tiles):
        counts = {}
        for tile in tiles:
            for unit in self.air_defense_units_on_tile(tile):
                counts[unit.unit_class] = counts.get(unit.unit_class, 0) + 1
        return counts

    def air_salvo_counts_for_tiles(self, tiles):
        counts = {}
        seen = set()
        for tile in tiles:
            for salvo in self.air_salvos_for_tile(tile):
                if salvo.id in seen:
                    continue
                seen.add(salvo.id)
                counts[salvo.munition_type] = counts.get(salvo.munition_type, 0) + salvo.count
        return counts

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
        return tile.owner is None or self.countries_hostile(division.owner, tile.owner)

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
        return self.division_lookup.get(division_id)

    def enemy_divisions_on_tile(self, tile, owner):
        if not tile or owner is None:
            return []
        return [
            division for division in self.divisions
            if division.tile == tile and self.countries_hostile(division.owner, owner) and division.strength > 0
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
        if not self.countries_hostile(division.owner, target_tile.owner):
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

    def apply_combat_attack(self, attacker, target, target_is_defending=True, elapsed_hours=1.0, battle=None):
        attacker_eff = max(0.2, attacker.width_efficiency)
        ammo_ratios = self.consume_division_attack_supplies(attacker, target, elapsed_hours)
        soft_ammo_factor = self.combat_ammo_factor(ammo_ratios.get("soft", 1.0))
        front_ammo_factor = self.combat_ammo_factor(ammo_ratios.get("front", 1.0))
        top_ammo_factor = self.combat_ammo_factor(ammo_ratios.get("top", 1.0))
        supply_ratio = self.division_supply_ratio(attacker)
        supply_factor = DIVISION_LOW_SUPPLY_ATTACK_FLOOR + (1.0 - DIVISION_LOW_SUPPLY_ATTACK_FLOOR) * supply_ratio
        attacker_eff *= supply_factor
        target_eff = max(0.2, target.width_efficiency)
        active_defense_value = target.defense if target_is_defending else target.breakthrough
        breakthrough_bonus = 0.0
        if not target_is_defending:
            breakthrough_bonus = self.division_attack_breakthrough_air_bonus(target, battle)
            active_defense_value *= 1.0 + breakthrough_bonus
        active_defense = active_defense_value * target_eff
        soft_raw = self.combat_damage_value(attacker.soft_attack * attacker_eff * soft_ammo_factor, active_defense)
        front_raw = self.combat_damage_value(attacker.hard_front_attack * attacker_eff * front_ammo_factor, active_defense)
        top_raw = self.combat_damage_value(attacker.hard_top_attack * attacker_eff * top_ammo_factor, active_defense)
        attacker.last_combat_attack_debug = {
            "soft_ammo_factor": soft_ammo_factor,
            "front_ammo_factor": front_ammo_factor,
            "top_ammo_factor": top_ammo_factor,
            "supply_ratio": supply_ratio,
            "supply_factor": supply_factor,
            "attacker_eff": attacker_eff,
            "breakthrough_bonus": breakthrough_bonus,
            "active_defense": active_defense,
        }

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
        strength_damage = self.apply_division_strength_losses(target, strength_damage)
        return org_damage, strength_damage

    def destroy_division(self, division):
        if division.owner and division in division.owner.divisions:
            division.owner.divisions.remove(division)
        if division in self.divisions:
            self.divisions.remove(division)
        self.division_lookup.pop(division.id, None)
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

    def apply_battle_collateral_damage(self, battle, elapsed_hours, active_attackers, active_defenders):
        tile = battle.tile
        if not tile or elapsed_hours <= 0:
            return False
        coverage = {
            key: value
            for key, value in (getattr(tile, "building_coverage", {}) or {}).items()
            if value > 0 and key in BUILDING_CONSTRUCTION_BASE
        }
        if not coverage:
            return False

        active_count = len(active_attackers) + len(active_defenders)
        if active_count <= 0:
            return False
        total_org_damage = battle.last_attacker_org_damage + battle.last_defender_org_damage
        total_strength_damage = battle.last_attacker_strength_damage + battle.last_defender_strength_damage
        intensity = self.clamp01((total_org_damage / 18.0) + (total_strength_damage / 7.0))
        active_factor = self.clamp01(active_count / 6.0)
        per_hour_damage = COMBAT_COLLATERAL_BASE_DAMAGE_PER_HOUR * (0.45 + intensity * 0.85) * (0.65 + active_factor)
        per_hour_damage = min(COMBAT_COLLATERAL_MAX_DAMAGE_PER_HOUR, per_hour_damage)
        damage = per_hour_damage * elapsed_hours
        if damage <= 0:
            return False

        keys = list(coverage.keys())
        weights = [max(0.02, coverage[key]) for key in keys]
        primary_key = random.choices(keys, weights=weights, k=1)[0]
        changed = self.damage_building(tile, primary_key, damage, queue_repair=True)
        if len(keys) > 1 and random.random() < 0.25 + intensity * 0.25:
            secondary_keys = [key for key in keys if key != primary_key]
            secondary_weights = [max(0.02, coverage[key]) for key in secondary_keys]
            secondary_key = random.choices(secondary_keys, weights=secondary_weights, k=1)[0]
            changed = self.damage_building(tile, secondary_key, damage * 0.45, queue_repair=True) or changed
        return changed

    def player_has_attack_helicopters(self, player):
        return any(
            self.air_wing_type_count(wing, "attack_helicopter") > 0
            for wing in getattr(player, "air_wings", []) or []
        )

    def air_support_base_tiles(self, player):
        tiles = []
        for airbase in getattr(player, "airbases", []) or []:
            if airbase.tile and airbase.tile.owner is player and self.building_health(airbase.tile, "airbase") > 0.15:
                tiles.append(airbase.tile)
        for tile in player.tiles:
            if (getattr(tile, "building_coverage", {}) or {}).get("field_helipad", 0.0) > 0:
                if self.building_health(tile, "field_helipad") > 0.15:
                    tiles.append(tile)
        return tiles

    def has_air_support_base_near(self, player, tile, radius=FIELD_HELIPAD_OPERATIONAL_RADIUS):
        if not player or not tile:
            return False
        return any(self.hex_distance(tile, base_tile) <= radius for base_tile in self.air_support_base_tiles(player))

    def has_field_helipad_or_project_near(self, player, tile, radius=FIELD_HELIPAD_AUTO_SEARCH_RADIUS):
        if not player or not tile:
            return False
        for owned_tile in player.tiles:
            if (getattr(owned_tile, "building_coverage", {}) or {}).get("field_helipad", 0.0) <= 0:
                continue
            if self.hex_distance(tile, owned_tile) <= radius:
                return True
        return any(
            project.owner is player
            and project.tile
            and self.hex_distance(tile, project.tile) <= radius
            for project in self.field_helipad_projects
        )

    def battle_side_all_divisions(self, battle, side):
        return (
            self.battle_divisions(battle, f"active_{side}s")
            + self.battle_divisions(battle, f"reserve_{side}s")
            + self.battle_divisions(battle, f"recovering_{side}s")
        )

    def division_can_prepare_field_helipad(self, division, tile):
        if not division or not tile or tile.owner is not division.owner or self.is_water_tile(tile):
            return False
        if self.hex_distance(division.tile, tile) > 1:
            return False
        supply = getattr(tile, "supply_score", 0.0)
        return supply >= 0.30 and division.strength > 0 and division.organization > 0

    def field_helipad_candidate_tiles(self, player, battle, divisions):
        candidates = []
        search_tiles = [battle.tile] + self.neighbor_tiles(battle.tile)
        for tile in search_tiles:
            if tile.owner is not player or self.is_water_tile(tile):
                continue
            if (getattr(tile, "building_coverage", {}) or {}).get("field_helipad", 0.0) > 0:
                continue
            if any(project.tile is tile for project in self.field_helipad_projects):
                continue
            if not any(self.division_can_prepare_field_helipad(division, tile) for division in divisions):
                continue
            candidates.append(tile)
        return sorted(
            candidates,
            key=lambda tile: (
                -getattr(tile, "supply_score", 0.0),
                self.hex_distance(tile, battle.tile),
                tile.r,
                tile.q,
            ),
        )

    def create_field_helipad_project(self, player, tile, battle_id=None):
        if not player or not tile or tile.owner is not player:
            return None
        project = FieldHelipadProject(
            id=self.next_field_helipad_project_id,
            owner=player,
            tile=tile,
            source_battle_id=battle_id,
        )
        self.next_field_helipad_project_id += 1
        self.field_helipad_projects.append(project)
        return project

    def maybe_start_field_helipad_for_battle_side(self, battle, player, divisions):
        if not player or not divisions or not self.player_has_attack_helicopters(player):
            return False
        if self.has_air_support_base_near(player, battle.tile):
            return False
        if self.has_field_helipad_or_project_near(player, battle.tile):
            return False
        candidates = self.field_helipad_candidate_tiles(player, battle, divisions)
        if not candidates:
            return False
        return self.create_field_helipad_project(player, candidates[0], battle.id) is not None

    def maybe_start_field_helipads_for_battle(self, battle):
        attackers = self.battle_side_all_divisions(battle, "attacker")
        defenders = self.battle_side_all_divisions(battle, "defender")
        changed = False
        if battle.attacker:
            changed = self.maybe_start_field_helipad_for_battle_side(battle, battle.attacker, attackers) or changed
        if battle.defender:
            changed = self.maybe_start_field_helipad_for_battle_side(battle, battle.defender, defenders) or changed
        return changed

    def update_field_helipad_projects(self, elapsed_hours):
        if elapsed_hours <= 0:
            return
        for battle in list(self.battles.values()):
            self.maybe_start_field_helipads_for_battle(battle)
        completed = []
        for project in list(self.field_helipad_projects):
            if not project.tile or project.tile.owner is not project.owner:
                completed.append(project)
                continue
            supply = self.clamp01(getattr(project.tile, "supply_score", 0.0))
            if supply < 0.25:
                continue
            nearby_divisions = [
                division for division in getattr(project.owner, "divisions", []) or []
                if division.tile and self.hex_distance(division.tile, project.tile) <= 1
            ]
            if not nearby_divisions:
                continue
            project.progress_hours += elapsed_hours * (0.45 + supply * 0.55)
            if project.progress_hours >= project.work_required_hours:
                self.set_tile_building_coverage(
                    project.tile,
                    "field_helipad",
                    max(
                        FIELD_HELIPAD_AUTO_COVERAGE,
                        (getattr(project.tile, "building_coverage", {}) or {}).get("field_helipad", 0.0),
                    ),
                    INFRASTRUCTURE_COVERAGE_LIMITS["field_helipad"][1],
                )
                self.refresh_tile_after_building_health_change(project.tile, project.owner)
                completed.append(project)
        for project in completed:
            if project in self.field_helipad_projects:
                self.field_helipad_projects.remove(project)

    def tick_battle(self, battle, elapsed_hours):
        if battle.id not in self.battles:
            return
        with self.profiler.measure("battle_air_suppression"):
            for division in self.battle_side_present(battle, "attacker") + self.battle_side_present(battle, "defender"):
                self.tick_division_air_ground_suppression(division, elapsed_hours)
        battle.last_attacker_org_damage = 0.0
        battle.last_attacker_strength_damage = 0.0
        battle.last_defender_org_damage = 0.0
        battle.last_defender_strength_damage = 0.0
        with self.profiler.measure("battle_recover_reinforce"):
            self.update_battle_recovery_and_reinforce(battle, elapsed_hours)
            attackers = self.battle_side_active(battle, "attacker")
            defenders = self.battle_side_active(battle, "defender")

        with self.profiler.measure("battle_attack_phase"):
            for attacker in list(attackers):
                defenders = self.battle_side_active(battle, "defender")
                if not defenders:
                    break
                target = random.choice(defenders)
                org_damage, strength_damage = self.apply_combat_attack(
                    attacker,
                    target,
                    target_is_defending=True,
                    elapsed_hours=elapsed_hours,
                    battle=battle,
                )
                battle.last_attacker_org_damage += org_damage
                battle.last_attacker_strength_damage += strength_damage
            for defender in list(defenders):
                attackers = self.battle_side_active(battle, "attacker")
                if not attackers:
                    break
                target = random.choice(attackers)
                org_damage, strength_damage = self.apply_combat_attack(
                    defender,
                    target,
                    target_is_defending=False,
                    elapsed_hours=elapsed_hours,
                    battle=battle,
                )
                battle.last_defender_org_damage += org_damage
                battle.last_defender_strength_damage += strength_damage

        with self.profiler.measure("battle_collateral"):
            self.apply_battle_collateral_damage(battle, elapsed_hours, attackers, defenders)

        with self.profiler.measure("battle_cleanup"):
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

        with self.profiler.measure("battle_rebalance"):
            self.rebalance_battle_side(battle, "attacker")
            self.rebalance_battle_side(battle, "defender")
            attackers = self.battle_side_active(battle, "attacker")
            defenders = self.battle_side_active(battle, "defender")
        with self.profiler.measure("battle_resolution"):
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
        old_owner = tile.owner if tile else None
        changed = self.set_tile_owner_only(tile, new_owner)
        if not changed:
            return False
        self.propagate_water_ownership_from_land(tile)
        self.refresh_after_ownership_change()
        self.update_air_assets_after_tile_owner_change(tile, old_owner, new_owner)
        if new_owner:
            self.enqueue_tile_repairs(new_owner, tile)
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
        with self.profiler.measure("battles_tick_loop"):
            remaining = elapsed_hours
            while remaining > 0:
                step = min(1.0, remaining)
                for battle in list(self.battles.values()):
                    self.tick_battle(battle, step)
                remaining -= step
        with self.profiler.measure("battles_invalidate_render"):
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
            self.replenish_division(division, elapsed_hours)
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
                if next_tile.owner is not None and next_tile.owner is not division.owner and not self.countries_hostile(division.owner, next_tile.owner):
                    division.path.clear()
                    division.route_tiles.clear()
                    division.target_tile = None
                    continue
                if next_tile.owner and next_tile.owner != division.owner and self.enemy_divisions_on_tile(next_tile, division.owner):
                    self.start_or_join_battle(division, next_tile)
                    continue
                movement_cost = self.effective_tile_movement_cost(next_tile)
                org_ratio = self.clamp01(division.organization / max(1.0, division.max_organization))
                speed_factor = max(DIVISION_LOW_ORG_SPEED_FLOOR, 0.35 + org_ratio * 0.65)
                speed_factor *= self.consume_division_movement_supplies(division, elapsed_hours)
                retreat_multiplier = 2.0 if division.route_mode == "retreat" else 1.0
                progress = division.speed * retreat_multiplier * speed_factor * elapsed_hours / 24.0 / movement_cost
                division.movement_progress += progress
                division.organization = max(
                    0.0,
                    division.organization - DIVISION_ORG_MOVE_COST_PER_TILE * progress,
                )
                while division.path and division.movement_progress >= 1.0:
                    step_owner = division.path[0].owner
                    if step_owner is not None and step_owner is not division.owner and not self.countries_hostile(division.owner, step_owner):
                        division.path.clear()
                        break
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
            tile.building_health = {}
            tile.airbase = None
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

    def reset_air_layer(self):
        self.airbases = []
        self.air_wings = []
        self.air_wing_lookup = {}
        self.air_wings_by_tile = {}
        self.air_defense_units = []
        self.air_defense_unit_lookup = {}
        self.air_defense_units_by_tile = {}
        self.air_salvos = []
        self.air_salvo_lookup = {}
        self.air_salvo_tile_lookup = {}
        self.air_salvo_tile_cache_revision = -1
        self.air_salvo_revision = 0
        self.air_attack_salvos = []
        self.air_attack_salvo_lookup = {}
        self.air_asset_revision = 0
        self.air_impact_decals = []
        self.field_helipad_projects = []
        self.next_airbase_id = 1
        self.next_air_wing_id = 1
        self.next_air_defense_unit_id = 1
        self.next_air_salvo_id = 1
        self.next_air_attack_salvo_id = 1
        self.next_field_helipad_project_id = 1
        for player in self.players:
            player.airbases = []
            player.air_wings = []
            player.air_defense_units = []
            player.aircraft_stockpile = {}
        for tile in self.hex_grid:
            tile.airbase = None

    def airbase_site_score(self, player, tile):
        if not tile or tile.owner is not player or self.is_water_tile(tile):
            return -1.0
        coverage = getattr(tile, "building_coverage", {}) or {}
        distance = self.hex_distance(tile, player.capital_tile) if player.capital_tile else 0
        return (
            self.clamp01(getattr(tile, "passability", 0.0)) * 0.30
            + coverage.get("city", 0.0) * 0.34
            + coverage.get("industry", 0.0) * 0.22
            + coverage.get("fuel_storage", 0.0) * 0.12
            + coverage.get("warehouse", 0.0) * 0.08
            - distance * 0.025
        )

    def starting_airbase_tile(self, player):
        land_tiles = [tile for tile in player.tiles if not self.is_water_tile(tile)]
        if not land_tiles:
            return None
        candidates = self.owned_tiles_within_radius(player, player.capital_tile, 4) if player.capital_tile else land_tiles
        candidates = [tile for tile in candidates if not self.is_water_tile(tile)]
        if not candidates:
            candidates = land_tiles
        return max(candidates, key=lambda tile: (self.airbase_site_score(player, tile), -tile.r, -tile.q))

    def generate_starting_air_wings(self, player, airbase):
        scale = max(0.55, min(1.20, getattr(player, "starting_scale", 1.0)))
        for aircraft_type, base_count in STARTING_AIR_WINGS.items():
            count = max(1, int(round(base_count * scale)))
            reserve_count = max(1, int(round(count * STARTING_AIRCRAFT_STOCKPILE_RATIO)))
            self.add_aircraft_to_stockpile(player, aircraft_type, count + reserve_count)

    def important_air_defense_tiles(self, player, airbase_tile, limit=3):
        candidates = []
        for tile in player.tiles:
            if self.is_water_tile(tile):
                continue
            coverage = getattr(tile, "building_coverage", {}) or {}
            border_pressure = sum(
                1 for neighbor in self.neighbor_tiles(tile)
                if neighbor.owner is not None and neighbor.owner is not player and not self.is_water_tile(neighbor)
            )
            score = (
                coverage.get("city", 0.0) * 0.50
                + coverage.get("industry", 0.0) * 0.28
                + coverage.get("supply_depot", 0.0) * 0.22
                + coverage.get("airbase", 0.0) * 0.30
                + border_pressure * 0.18
            )
            if tile is player.capital_tile:
                score += 0.45
            if tile is airbase_tile:
                score += 0.25
            if score > 0:
                candidates.append((score, tile))
        candidates.sort(key=lambda item: (-item[0], item[1].r, item[1].q))
        result = []
        seen = set()
        for _score, tile in candidates:
            key = self.tile_key(tile)
            if key in seen:
                continue
            result.append(tile)
            seen.add(key)
            if len(result) >= limit:
                break
        return result

    def generate_starting_air_defense(self, player, airbase):
        if player.capital_tile and not self.is_water_tile(player.capital_tile):
            self.create_air_defense_unit(player, player.capital_tile, "medium_range_sam")
            self.create_air_defense_unit(player, player.capital_tile, "radar_unit")
        if airbase and airbase.tile:
            self.create_air_defense_unit(player, airbase.tile, "short_range_aa")
        important_tiles = self.important_air_defense_tiles(player, airbase.tile if airbase else None, limit=3)
        for index, tile in enumerate(important_tiles):
            if tile is player.capital_tile or (airbase and tile is airbase.tile):
                continue
            self.create_air_defense_unit(player, tile, "short_range_aa" if index == 0 else "manpads_team")
        if getattr(player, "starting_scale", 1.0) >= 1.85 and player.capital_tile:
            self.create_air_defense_unit(player, player.capital_tile, "long_range_sam")

    def generate_starting_air_layer_for_all_states(self):
        self.reset_air_layer()
        for player in self.players:
            airbase_tile = self.starting_airbase_tile(player)
            airbase = self.create_airbase(player, airbase_tile) if airbase_tile else None
            if airbase:
                self.generate_starting_air_wings(player, airbase)
            self.generate_starting_air_defense(player, airbase)
        self.recalculate_all_supply_scores()
        for player in self.players:
            self.recalculate_player_storage(player)
            self.recalculate_monthly_balance(player)
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
        self.initialize_politics()
        start_tiles = self.find_state_start_tiles(total_players)
        for player, start_tile in zip(self.players, start_tiles):
            player.capital_tile = start_tile
            self.claim_start_territory(player, start_tile, self.start_territory_radius)

        for player in self.players:
            self.apply_starting_profile(player)

        self.generate_starting_infrastructure_for_all_states()
        self.generate_starting_air_layer_for_all_states()

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
            self.initialize_player_manpower_reserve(player)
            self.seed_starting_military_stockpiles(player)
            self.recalculate_player_storage(player)
            self.distribute_player_stockpiles_to_tiles(player)
            self.recalculate_resource_balance_breakdown(player)
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
            self.register_division(division)

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

    def visible_tile_key_set(self):
        return {self.tile_key(tile) for tile in self.visible_tiles}

    def draw_airbase_icon(self, tile, owner_color):
        x, y = tile.center_x, tile.center_y + 12
        arcade.draw_lbwh_rectangle_filled(x - 18, y - 4, 36, 8, (18, 24, 31, 225))
        arcade.draw_lbwh_rectangle_outline(x - 18, y - 4, 36, 8, owner_color, 2)
        arcade.draw_line(x - 12, y, x + 12, y, (228, 238, 248), 1)

    def draw_field_helipad_icon(self, tile, owner_color, progress=None):
        x, y = tile.center_x + 16, tile.center_y - 12
        arcade.draw_circle_filled(x, y, 9, (18, 24, 31, 220))
        arcade.draw_circle_outline(x, y, 10, owner_color, 2)
        arcade.draw_line(x - 4, y - 5, x - 4, y + 5, (230, 238, 246), 1)
        arcade.draw_line(x + 4, y - 5, x + 4, y + 5, (230, 238, 246), 1)
        arcade.draw_line(x - 4, y, x + 4, y, (230, 238, 246), 1)
        if progress is not None:
            progress = self.clamp01(progress)
            arcade.draw_line(x - 9, y - 13, x - 9 + 18 * progress, y - 13, (170, 224, 144), 2)

    def draw_air_defense_icon(self, unit):
        if not unit or not unit.tile:
            return
        color_by_class = {
            "manpads_team": (180, 224, 128),
            "short_range_aa": (124, 200, 220),
            "medium_range_sam": (236, 204, 112),
            "long_range_sam": (238, 150, 112),
            "radar_unit": (178, 164, 238),
        }
        color = color_by_class.get(unit.unit_class, (210, 220, 230))
        x = getattr(unit, "x", unit.tile.center_x) - 17
        y = getattr(unit, "y", unit.tile.center_y) - 12
        if unit.path:
            next_tile = unit.path[0]
            progress = self.clamp01(getattr(unit, "visual_movement_progress", 0.0))
            x = unit.tile.center_x + (next_tile.center_x - unit.tile.center_x) * progress - 17
            y = unit.tile.center_y + (next_tile.center_y - unit.tile.center_y) * progress - 12
        arcade.draw_circle_filled(x, y, 8, (18, 24, 31, 225))
        arcade.draw_circle_outline(x, y, 9, color, 2)
        if unit.unit_class == "radar_unit":
            arcade.draw_line(x, y, x + 7, y + 4, color, 2)
            arcade.draw_circle_outline(x, y, 13, (*color, 130), 1)
        else:
            arcade.draw_line(x, y + 6, x - 6, y - 5, color, 2)
            arcade.draw_line(x - 6, y - 5, x + 6, y - 5, color, 2)
            arcade.draw_line(x + 6, y - 5, x, y + 6, color, 2)

    def air_wing_visual_area_tiles(self, wing):
        if not wing:
            return []
        tiles = self.air_wing_operation_area_tiles(wing)
        return tiles or ([getattr(wing, "target_tile", None)] if getattr(wing, "target_tile", None) else [])

    def air_wing_visual_target_tile(self, wing, slot_index=0, now=None):
        if not wing:
            return None
        mission_tile = self.tile_for_key(getattr(wing, "mission_target_tile_key", None))
        if mission_tile:
            return mission_tile
        area_tiles = self.air_wing_visual_area_tiles(wing)
        if area_tiles and self.air_wing_is_standing_air_mission(wing):
            if now is None:
                now = time.perf_counter()
            offset = int(now / 5.5)
            return area_tiles[(slot_index + offset) % len(area_tiles)]
        if getattr(wing, "target_tile", None):
            return wing.target_tile
        if getattr(wing, "target_area", None):
            return wing.target_area
        if area_tiles:
            if now is None:
                now = time.perf_counter()
            offset = int(now / 5.5) if self.air_wing_is_standing_air_mission(wing) else 0
            return area_tiles[(slot_index + offset) % len(area_tiles)]
        return getattr(wing, "base_tile", None)

    def air_wing_is_standing_air_mission(self, wing):
        enabled = set(self.air_wing_enabled_missions(wing))
        return bool(enabled.intersection({"patrol", "intercept", "air_superiority", "cas", "strategic_strike"}))

    def air_wing_visual_mission_for_slot(self, wing, slot_index=0):
        enabled = self.air_wing_enabled_missions(wing)
        if not enabled:
            return getattr(wing, "mission", "none")
        ordered = [
            mission for mission in ("cas", "strategic_strike", "intercept", "air_superiority", "patrol")
            if mission in enabled
        ]
        if not ordered:
            ordered = enabled
        return ordered[slot_index % len(ordered)]

    def air_wing_visual_package_count(self, wing):
        if not wing:
            return 0
        area_count = max(1, len(self.air_wing_visual_area_tiles(wing)))
        ready_count = max(0, int(getattr(wing, "ready_count", 0) or 0))
        if ready_count <= 0:
            return 0
        return max(1, min(4, area_count, int(math.ceil(ready_count / 6.0))))

    def air_wing_visual_aircraft_type(self, wing, slot_index=0):
        composition = self.air_wing_composition(wing)
        if not composition:
            return getattr(wing, "aircraft_type", None)
        state = getattr(wing, "mission_state", "returning")
        if state in {"approach", "attack_run", "egress", "defensive"}:
            mission_type = getattr(wing, "mission", None)
            return self.air_wing_primary_type_for_mission(wing, mission_type) or getattr(wing, "aircraft_type", None)
        visual_mission = self.air_wing_visual_mission_for_slot(wing, slot_index)
        preferred_type = self.air_wing_primary_type_for_mission(wing, visual_mission)
        if preferred_type:
            return preferred_type
        standing_missions = set(self.air_wing_enabled_missions(wing)).intersection({"patrol", "intercept", "air_superiority", "cas", "strategic_strike"})
        candidates = [
            aircraft_type for aircraft_type, count in composition.items()
            if count > 0 and (
                not standing_missions
                or standing_missions.intersection(set(self.aircraft_type_data(aircraft_type).get("allowed_missions", [])))
            )
        ]
        if not candidates:
            candidates = list(composition.keys())
        candidates.sort(key=lambda aircraft_type: (-composition.get(aircraft_type, 0), aircraft_type))
        return candidates[slot_index % len(candidates)]

    @staticmethod
    def stable_visual_seed(*values):
        seed = 2166136261
        for value in values:
            if value is None:
                item = 0
            elif isinstance(value, (int, float)):
                item = int(value)
            else:
                item = sum(ord(char) for char in str(value))
            seed ^= item & 0xFFFFFFFF
            seed = (seed * 16777619) & 0xFFFFFFFF
        return seed

    def air_visual_tile_point(self, tile, wing=None, slot_index=0, phase=0, scale=1.0):
        if not tile:
            return 0.0, 0.0
        seed = self.stable_visual_seed(
            getattr(wing, "id", 0),
            getattr(tile, "q", 0),
            getattr(tile, "r", 0),
            slot_index,
            phase,
        )
        angle = ((seed % 6283) / 1000.0) % math.tau
        radius_noise = (((seed >> 10) & 1023) / 1023.0)
        radius = AIR_VISUAL_TILE_OFFSET_RADIUS * max(0.0, float(scale)) * (0.35 + radius_noise * 0.65)
        return tile.center_x + math.cos(angle) * radius, tile.center_y + math.sin(angle) * radius * 0.72

    def air_wing_visual_position(self, wing, now=None, slot_index=0, slot_count=1):
        if not wing or not wing.base_tile:
            return None
        now = time.perf_counter() if now is None else now
        state = getattr(wing, "mission_state", "returning")
        target_tile = self.air_wing_visual_target_tile(wing, slot_index=slot_index, now=now)
        if not target_tile:
            return None
        slot_angle = (math.tau * slot_index / max(1, slot_count)) + wing.id * 0.19
        base_x, base_y = self.air_visual_tile_point(wing.base_tile, wing, slot_index, phase=11, scale=0.38)
        target_x, target_y = self.air_visual_tile_point(target_tile, wing, slot_index, phase=23, scale=0.92)

        if state == "approach":
            progress = self.clamp01(getattr(wing, "mission_state_hours", 0.0) / AIR_VISUAL_APPROACH_HOURS)
            x = base_x + (target_x - base_x) * progress
            y = base_y + (target_y - base_y) * progress
            heading = math.atan2(target_y - base_y, target_x - base_x)
            return x, y, heading, True

        if state in {"egress", "aborted"}:
            progress = self.clamp01(getattr(wing, "mission_state_hours", 0.0) / AIR_VISUAL_EGRESS_HOURS)
            if progress >= 1.0:
                return None
            x = target_x + (base_x - target_x) * progress
            y = target_y + (base_y - target_y) * progress
            heading = math.atan2(base_y - target_y, base_x - target_x)
            return x, y, heading, True

        if state == "attack_run":
            angle = now * AIR_VISUAL_ATTACK_ORBIT_SPEED + wing.id * 0.73 + slot_angle
            radius = 14.0
            x = target_x + math.cos(angle) * radius
            y = target_y + math.sin(angle) * radius * 0.55
            heading = angle + math.pi * 0.5
            return x, y, heading, True

        if state == "defensive":
            angle = now * (AIR_VISUAL_ATTACK_ORBIT_SPEED * 0.68) + wing.id * 1.11 + slot_angle
            radius = 18.0
            x = target_x + math.cos(angle) * radius
            y = target_y + math.sin(angle) * radius
            heading = angle + math.pi * 0.5
            return x, y, heading, True

        if self.air_wing_is_standing_air_mission(wing) and target_tile is not wing.base_tile:
            angle = now * (AIR_VISUAL_STANDING_ORBIT_SPEED + (wing.id % 3) * 0.12) + wing.id * 0.91 + slot_angle
            radius = 12.0 + (slot_index % 3) * 5.0
            x = target_x + math.cos(angle) * radius
            y = target_y + math.sin(angle) * radius * 0.75
            heading = angle + math.pi * 0.5
            return x, y, heading, False

        return None

    def add_air_impact_decal(self, tile, source_id=0, strength=1.0, color=None):
        if not tile:
            return False
        if not hasattr(self, "air_impact_decals"):
            self.air_impact_decals = []
        phase = 41 + len(self.air_impact_decals) + int(getattr(self, "next_air_salvo_id", 1) or 1)
        marker = type("AirImpactMarker", (), {"id": int(source_id or 0)})()
        x, y = self.air_visual_tile_point(tile, marker, slot_index=phase, phase=67, scale=0.82)
        size = max(0.75, min(2.4, float(strength) ** 0.35))
        self.air_impact_decals.append(
            AirImpactDecal(
                tile=tile,
                x=x,
                y=y,
                size=size,
                color=color or (255, 184, 86),
            )
        )
        overflow = len(self.air_impact_decals) - AIR_IMPACT_DECAL_MAX_COUNT
        if overflow > 0:
            del self.air_impact_decals[:overflow]
        return True

    def update_air_impact_decals(self, delta_time):
        decals = getattr(self, "air_impact_decals", None)
        if not decals or delta_time <= 0:
            return
        for decal in decals:
            decal.age = max(0.0, float(getattr(decal, "age", 0.0)) + delta_time)
        self.air_impact_decals = [
            decal for decal in decals
            if decal.age < max(0.05, float(getattr(decal, "duration", AIR_IMPACT_DECAL_DURATION)))
        ]

    def draw_air_impact_decals(self, visible_keys):
        for decal in getattr(self, "air_impact_decals", []) or []:
            tile = getattr(decal, "tile", None)
            if not tile or self.tile_key(tile) not in visible_keys:
                continue
            duration = max(0.05, float(getattr(decal, "duration", AIR_IMPACT_DECAL_DURATION)))
            t = self.clamp01(float(getattr(decal, "age", 0.0)) / duration)
            alpha = int(210 * (1.0 - t))
            if alpha <= 0:
                continue
            x = float(getattr(decal, "x", tile.center_x))
            y = float(getattr(decal, "y", tile.center_y))
            size = max(0.5, float(getattr(decal, "size", 1.0)))
            color = tuple((getattr(decal, "color", (255, 184, 86)) or (255, 184, 86))[:3])
            inner_radius = (4.0 + 8.0 * t) * size
            outer_radius = (10.0 + 18.0 * t) * size
            arcade.draw_circle_filled(x, y, outer_radius, (*color, max(18, alpha // 4)))
            arcade.draw_circle_outline(x, y, outer_radius, (*color, max(32, alpha // 2)), max(1, int(2 * size)))
            arcade.draw_circle_filled(x, y, inner_radius, (255, 235, 164, max(28, alpha // 2)))
            for index in range(4):
                angle = index * math.pi * 0.5 + t * 0.9
                start = inner_radius * 0.55
                end = outer_radius * 0.92
                arcade.draw_line(
                    x + math.cos(angle) * start,
                    y + math.sin(angle) * start,
                    x + math.cos(angle) * end,
                    y + math.sin(angle) * end,
                    (*color, max(26, alpha // 2)),
                    max(1, int(2 * size)),
                )

    def draw_air_wing_flight_icon(self, wing, x, y, heading, active=False, aircraft_type=None):
        owner_color = tuple((wing.owner.border_color if wing.owner else (190, 205, 220))[:3])
        fill = (*owner_color, 225 if active else 190)
        outline = (245, 250, 255, 230) if wing.id in getattr(self, "selected_air_wing_ids", set()) else (20, 26, 34, 220)
        size = 12 if active else 10
        cos_a = math.cos(heading)
        sin_a = math.sin(heading)
        aircraft_type = aircraft_type or self.air_wing_visual_aircraft_type(wing)

        def rotate(dx, dy):
            return x + dx * cos_a - dy * sin_a, y + dx * sin_a + dy * cos_a

        if self.aircraft_type_is_helicopter(aircraft_type):
            body = [rotate(size * 0.55, 0), rotate(0, size * 0.34), rotate(-size * 0.62, size * 0.24), rotate(-size * 0.74, -size * 0.24), rotate(0, -size * 0.34)]
            tail_start = rotate(-size * 0.56, 0)
            tail_end = rotate(-size * 1.28, 0)
            rotor_a = rotate(-size * 0.05, -size * 0.95)
            rotor_b = rotate(-size * 0.05, size * 0.95)
            tail_rotor_a = rotate(-size * 1.35, -size * 0.28)
            tail_rotor_b = rotate(-size * 1.35, size * 0.28)
            arcade.draw_polygon_filled(body, fill)
            arcade.draw_line_strip(body + [body[0]], outline, 1)
            arcade.draw_line(*tail_start, *tail_end, outline, 2)
            arcade.draw_line(*rotor_a, *rotor_b, (230, 240, 248, 210), 2)
            arcade.draw_line(*tail_rotor_a, *tail_rotor_b, (230, 240, 248, 190), 1)
        else:
            fuselage = [
                rotate(size * 0.95, 0),
                rotate(size * 0.12, size * 0.18),
                rotate(-size * 0.86, size * 0.13),
                rotate(-size * 0.98, 0),
                rotate(-size * 0.86, -size * 0.13),
                rotate(size * 0.12, -size * 0.18),
            ]
            left_wing = [rotate(size * 0.14, size * 0.10), rotate(-size * 0.30, size * 0.88), rotate(-size * 0.12, size * 0.10)]
            right_wing = [rotate(size * 0.14, -size * 0.10), rotate(-size * 0.30, -size * 0.88), rotate(-size * 0.12, -size * 0.10)]
            left_tail = [rotate(-size * 0.68, size * 0.08), rotate(-size * 1.02, size * 0.48), rotate(-size * 0.86, size * 0.06)]
            right_tail = [rotate(-size * 0.68, -size * 0.08), rotate(-size * 1.02, -size * 0.48), rotate(-size * 0.86, -size * 0.06)]
            for part in (left_wing, right_wing, left_tail, right_tail, fuselage):
                arcade.draw_polygon_filled(part, fill)
                arcade.draw_line_strip(part + [part[0]], outline, 1)
        if active and getattr(wing, "mission_state", "") == "attack_run":
            pulse = (time.perf_counter() * 4.0 + wing.id) % 1.0
            if pulse < 0.34:
                nose_x, nose_y = rotate(size + 3, 0)
                end_x, end_y = rotate(size + 18, 0)
                arcade.draw_line(nose_x, nose_y, end_x, end_y, (255, 206, 94, 190), 2)

    def draw_air_wings_in_flight(self, visible_keys):
        now = time.perf_counter()
        for wing in getattr(self, "air_wings", []) or []:
            if not wing or wing.ready_count <= 0 or not wing.base_tile:
                continue
            state = getattr(wing, "mission_state", "returning")
            package_count = 1 if state in {"approach", "attack_run", "egress", "defensive", "aborted"} else self.air_wing_visual_package_count(wing)
            for slot_index in range(max(1, package_count)):
                visual = self.air_wing_visual_position(wing, now=now, slot_index=slot_index, slot_count=package_count)
                if not visual:
                    continue
                target_tile = self.air_wing_visual_target_tile(wing, slot_index=slot_index, now=now)
                if (
                    self.tile_key(wing.base_tile) not in visible_keys
                    and (not target_tile or self.tile_key(target_tile) not in visible_keys)
                ):
                    continue
                x, y, heading, active = visual
                aircraft_type = self.air_wing_visual_aircraft_type(wing, slot_index=slot_index)
                self.draw_air_wing_flight_icon(wing, x, y, heading, active=active, aircraft_type=aircraft_type)

    def draw_selected_air_defense_ranges(self):
        tile = self.selected_tile
        units = []
        show_for_air_wing = bool(self.selected_air_wings() or self.air_wing_target_mode_ids or self.air_wing_target_mode_id)
        if self.air_defense_overlay_enabled or show_for_air_wing:
            units = [
                unit for unit in self.air_defense_units
                if unit.tile and unit.readiness > 0 and unit.health > 0
            ]
        elif tile:
            selected_unit = self.air_defense_unit_by_id(self.selected_air_defense_unit_id)
            if selected_unit and selected_unit.tile is tile:
                units.append(selected_unit)
            for unit in self.air_defense_units_on_tile(tile):
                if unit not in units:
                    units.append(unit)
        for unit in units:
            friendly = unit.owner is self.human_player
            fire_color = (120, 230, 150, 150) if friendly else (248, 132, 96, 150)
            fire_glow = (120, 230, 150, 85) if friendly else (248, 132, 96, 85)
            radar_color = (122, 196, 248, 112) if friendly else (238, 150, 238, 112)
            if unit.fire_range_cells > 0:
                radius = unit.fire_range_cells * HEX_WID
                arcade.draw_circle_outline(unit.tile.center_x, unit.tile.center_y, radius, fire_color, 4)
                arcade.draw_circle_outline(unit.tile.center_x, unit.tile.center_y, radius + 3, fire_glow, 2)
            if unit.radar_active and unit.radar_range_cells > 0:
                radius = unit.radar_range_cells * HEX_WID
                arcade.draw_circle_outline(unit.tile.center_x, unit.tile.center_y, radius, radar_color, 3)

    def air_wing_display_range_cells(self, wing):
        composition = self.air_wing_composition(wing)
        if not composition and getattr(wing, "aircraft_type", None):
            composition = {wing.aircraft_type: 1}
        ranges = [
            float(self.aircraft_type_data(aircraft_type).get("range", 0))
            for aircraft_type in composition
        ]
        return max(ranges) if ranges else 0.0

    def air_wing_display_range_world_radius(self, wing):
        return max(0.0, self.air_wing_display_range_cells(wing)) * HEX_WID

    def air_wing_overlay_signature(self, wings):
        wing_data = []
        for wing in wings:
            if not wing:
                continue
            base_key = self.tile_key(wing.base_tile) if wing.base_tile else None
            wing_data.append((
                wing.id,
                base_key,
                round(self.air_wing_display_range_world_radius(wing), 2),
                tuple(self.normalize_air_wing_operation_area_keys(wing)),
            ))
        target_ids = tuple(sorted(set(self.air_wing_target_mode_ids or set()) | ({self.air_wing_target_mode_id} if self.air_wing_target_mode_id else set())))
        return (
            tuple(wing_data),
            target_ids,
            self.visible_tiles_signature,
        )

    def air_wing_area_target_mode_active(self):
        return bool(self.air_wing_target_mode_id or self.air_wing_target_mode_ids)

    @staticmethod
    def append_air_tile_shapes(shapes, tile, fill, outline=None, outline_width=1):
        if not tile or not getattr(tile, "corners", None):
            return
        points = list(tile.corners)
        shapes.append(arcade.shape_list.create_polygon(points, fill))
        if outline:
            shapes.append(arcade.shape_list.create_line_loop(points, outline, outline_width))

    def rebuild_air_wing_overlay_cache(self, wings):
        cache_key = self.air_wing_overlay_signature(wings)
        if cache_key == self.air_wing_overlay_cache_key:
            return

        range_shapes = arcade.shape_list.ShapeElementList()
        unavailable_shapes = arcade.shape_list.ShapeElementList()
        area_shapes = arcade.shape_list.ShapeElementList()
        selectable_wings = [wing for wing in wings if wing and wing.base_tile]
        for index, wing in enumerate(selectable_wings[:6]):
            radius = self.air_wing_display_range_world_radius(wing)
            if radius <= 0:
                continue
            alpha = max(44, 92 - index * 10)
            range_shapes.append(
                arcade.shape_list.create_ellipse_outline(
                    wing.base_tile.center_x,
                    wing.base_tile.center_y,
                    radius * 2,
                    radius * 2,
                    (255, 44, 42, alpha),
                    6,
                )
            )
            range_shapes.append(
                arcade.shape_list.create_ellipse_outline(
                    wing.base_tile.center_x,
                    wing.base_tile.center_y,
                    radius * 2 + 10,
                    radius * 2 + 10,
                    (255, 122, 118, max(40, alpha // 2)),
                    2,
                )
            )

        seen_area = set()
        for wing in wings:
            for key in self.normalize_air_wing_operation_area_keys(wing):
                if key in seen_area:
                    continue
                tile = self.tile_for_key(key)
                if not tile:
                    continue
                seen_area.add(key)
                self.append_air_tile_shapes(
                    area_shapes,
                    tile,
                    (70, 168, 230, 62),
                    (126, 218, 255, 178),
                    2,
                )

        if self.air_wing_area_target_mode_active() and selectable_wings:
            for tile in self.visible_tiles:
                if not all(self.air_wing_can_reach_tile(wing, tile) for wing in selectable_wings):
                    self.append_air_tile_shapes(
                        unavailable_shapes,
                        tile,
                        (210, 48, 52, 72),
                    )

        self.air_wing_overlay_cache_key = cache_key
        self.air_wing_overlay_range_shapes = range_shapes
        self.air_wing_overlay_unavailable_shapes = unavailable_shapes
        self.air_wing_overlay_area_shapes = area_shapes

    def draw_air_wing_operation_overlays(self):
        wings = self.selected_air_wings()
        if not wings:
            self.air_wing_overlay_cache_key = None
            return

        self.rebuild_air_wing_overlay_cache(wings)
        self.air_wing_overlay_range_shapes.draw()
        if self.air_wing_area_target_mode_active():
            self.air_wing_overlay_unavailable_shapes.draw()
        self.air_wing_overlay_area_shapes.draw()

    def draw_air_assets(self):
        visible_keys = self.visible_tile_key_set()
        self.draw_air_wing_operation_overlays()
        self.draw_selected_air_defense_ranges()
        for airbase in self.airbases:
            tile = airbase.tile
            if not tile or self.tile_key(tile) not in visible_keys:
                continue
            owner_color = tuple((airbase.owner.border_color if airbase.owner else (190, 200, 210))[:3])
            self.draw_airbase_icon(tile, owner_color)
        for tile in self.visible_tiles:
            coverage = (getattr(tile, "building_coverage", {}) or {}).get("field_helipad", 0.0)
            if coverage <= 0:
                continue
            owner_color = tuple((tile.owner.border_color if tile.owner else (180, 190, 200))[:3])
            self.draw_field_helipad_icon(tile, owner_color)
        for project in self.field_helipad_projects:
            tile = project.tile
            if not tile or self.tile_key(tile) not in visible_keys:
                continue
            owner_color = tuple((project.owner.border_color if project.owner else (180, 190, 200))[:3])
            progress = project.progress_hours / max(1.0, project.work_required_hours)
            self.draw_field_helipad_icon(tile, owner_color, progress=progress)
        for unit in self.air_defense_units:
            if unit.tile and self.tile_key(unit.tile) in visible_keys:
                self.draw_air_defense_icon(unit)
        self.draw_air_impact_decals(visible_keys)
        self.draw_air_wings_in_flight(visible_keys)

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
        profiler = self.profiler
        profiler.begin_phase("draw")
        with profiler.measure("total"):
            with profiler.measure("setup"):
                self.sync_cameras_to_window()
                self.clear()
                self.begin_ui_text_frame()
                if not self.premium_shader_enabled and not self.premium_shader_attempted:
                    self.setup_premium_shader()
            with profiler.measure("world_camera"):
                self.world_camera.use()
            if self.map_overview_dirty and self.use_overview_lod():
                with profiler.measure("world_overview_refresh"):
                    self.refresh_dirty_map_overview_tiles()
            if self.use_overview_lod():
                with profiler.measure("world_overview_draw"):
                    self.map_overview_sprite_list.draw()
            else:
                with profiler.measure("world_tiles"):
                    self.visible_tiles.draw()
                if not self.construction_placement_mode:
                    with profiler.measure("world_tile_visuals"):
                        self.draw_tile_visual_system()
                with profiler.measure("world_construction_labels"):
                    self.draw_construction_placement_labels()
            with profiler.measure("world_state_borders"):
                self.draw_state_borders()
            if self.map_layer == "political":
                with profiler.measure("world_capitals"):
                    self.draw_capital_markers()
            with profiler.measure("world_air_assets"):
                self.draw_air_assets()
            if self.selection_border.visible:
                with profiler.measure("world_selection"):
                    self.selection_border_sprite_list.draw()
            with profiler.measure("world_army_plans"):
                self.draw_army_plans()
            with profiler.measure("world_divisions"):
                self.draw_divisions()
            with profiler.measure("world_shader_overlay"):
                self.draw_premium_shader_overlay()
            with profiler.measure("gui_camera"):
                self.gui_camera.use()
            if not self.paused:
                with profiler.measure("ui_battle_indicators"):
                    self.draw_battle_indicators()
            with profiler.measure("ui_division_groups"):
                self.draw_division_groups()
            with profiler.measure("ui_selection_box"):
                self.draw_division_selection_box()
            with profiler.measure("ui_air_wing_list"):
                self.draw_air_wing_list_panel()
            with profiler.measure("ui_division_list"):
                self.draw_division_list_panel()
            with profiler.measure("ui_top_status"):
                self.draw_top_status_bar()
            with profiler.measure("ui_top_navigation"):
                self.draw_top_navigation_bar()
            with profiler.measure("ui_side_panel"):
                self.draw_side_panel()
            with profiler.measure("ui_hex_panel"):
                self.draw_hex_info_panel()
            with profiler.measure("ui_gui_stub"):
                self.draw_gui()
            with profiler.measure("ui_army_command"):
                self.draw_army_command_bar()
            if not self.paused:
                with profiler.measure("ui_battle_panel"):
                    self.draw_battle_panel()
            with profiler.measure("ui_time_hud"):
                self.draw_time_hud()
            with profiler.measure("ui_map_layer"):
                self.draw_map_layer_control()
            if self.paused:
                with profiler.measure("ui_pause_menu"):
                    self.draw_pause_menu()
            with profiler.measure("ui_tooltip_prepare"):
                construction_tooltip_data = self.construction_hover_tooltip_data()
                top_tooltip_active = (
                    self.hovered_population_summary
                    or self.hovered_budget_summary
                    or self.hovered_resource_summary
                    or self.hovered_warning_key
                    or self.hovered_division_detach_button
                    or self.hovered_army_plan_button
                    or self.hovered_air_wing_control
                )
            with profiler.measure("ui_text_batch"):
                self.draw_ui_text_batch()
            if not self.paused:
                with profiler.measure("ui_country_card"):
                    self.draw_country_card()
            if construction_tooltip_data or top_tooltip_active:
                with profiler.measure("ui_tooltips"):
                    self.begin_tooltip_text_frame()
                    self.draw_construction_hover_tooltip(construction_tooltip_data)
                    self.draw_top_hover_tooltips()
                    self.draw_division_detach_tooltip()
                    self.draw_army_plan_tooltip()
                    self.draw_air_wing_ui_tooltip()
                    self.draw_tooltip_text_batch()
        with profiler.measure("debug_text"):
            self.debug_text.text = f"FPS: {self.fps:.0f} | Zoom: {self.world_camera.zoom:.2f}"
            self.debug_text.x = self.window.width - 12
            self.debug_text.y = self.window.height - 8
            self.debug_text.draw()
        if self.profiler.visible:
            with profiler.measure("profiler_overlay"):
                self.draw_performance_overlay()
        profiler.end_phase("draw")

    def draw_performance_overlay(self):
        profiler = self.profiler
        if not self.window:
            return

        rows = [
            ("Профайлер F3", None, None),
            ("DRAW total", "draw", "total"),
            ("  карта/тайлы", "draw", "world_tiles"),
            ("  тайловый визуал", "draw", "world_tile_visuals"),
            ("  границы", "draw", "world_state_borders"),
            ("  авиация визуал", "draw", "world_air_assets"),
            ("  планы армий", "draw", "world_army_plans"),
            ("  дивизии", "draw", "world_divisions"),
            ("  списки авиации/дивизий", "draw", ("ui_air_wing_list", "ui_division_list")),
            ("  верхний UI", "draw", ("ui_top_status", "ui_top_navigation", "ui_time_hud")),
            ("  боковая/гекс панель", "draw", ("ui_side_panel", "ui_hex_panel")),
            ("    hex resources", "draw", "hex_resources_lookup"),
            ("    hex storage", "draw", "hex_storage_lookup"),
            ("    hex buildings", "draw", "hex_buildings_lookup"),
            ("    hex aviation", "draw", "hex_aviation_lookup"),
            ("    панель ресурсов", "draw", "panel_resources"),
            ("    панель торговли", "draw", "panel_trade"),
            ("      trade snapshot", "draw", "trade_snapshot"),
            ("      trade header", "draw", "trade_header"),
            ("      trade rows", "draw", "trade_rows"),
            ("      trade buttons", "draw", "trade_buttons"),
            ("    панель стройки", "draw", "panel_construction"),
            ("  текст UI", "draw", "ui_text_batch"),
            ("  сам профайлер", "draw", "profiler_overlay"),
            ("UPDATE total", "update", "total"),
            ("  сервер время/команды", "update", "server_clock"),
            ("  рынок", "update", "server_market"),
            ("  экономика", "update", "server_economy"),
            ("  производство", "update", "server_production"),
            ("  строительство", "update", "server_construction"),
            ("    стройка: auto repair", "update", "construction_auto_repairs"),
            ("    стройка: проекты", "update", "construction_projects"),
            ("    стройка: статус", "update", "construction_status_eval"),
            ("    стройка: ресурсы", "update", "construction_consume_resources"),
            ("  население", "update", "server_population"),
            ("  дивизии логика", "update", "server_divisions"),
            ("  наземные бои", "update", "server_ground_battles"),
            ("    бой: атаки", "update", "battle_attack_phase"),
            ("    бой: подкрепл./орг", "update", "battle_recover_reinforce"),
            ("    бой: урон зданиям", "update", "battle_collateral"),
            ("    бой: cleanup", "update", "battle_cleanup"),
            ("    бой: rebalance", "update", "battle_rebalance"),
            ("  ПВО/воздушные атаки", "update", ("server_air_defense", "server_air_attack_salvos")),
            ("  авиация логика", "update", ("server_air_missions", "server_air_salvos")),
            ("  планы армий логика", "update", "server_army_plans"),
            ("  владение/камера/видимость", "update", ("ownership_refresh", "camera", "visible_tiles_refresh")),
            ("    владение", "update", "ownership_refresh"),
            ("    камера", "update", "camera"),
            ("    видимые тайлы", "update", "visible_tiles_refresh"),
        ]

        line_height = 14
        panel_width = 360
        panel_height = 12 + line_height * len(rows)
        x = 12
        y = self.window.height - panel_height - 12
        arcade.draw_lbwh_rectangle_filled(x, y, panel_width, panel_height, (12, 18, 24, 222))
        arcade.draw_lbwh_rectangle_outline(x, y, panel_width, panel_height, (100, 126, 155, 210), 1)

        now = time.perf_counter()
        if (
            not self.performance_overlay_rows
            or now - self.performance_overlay_last_update >= self.performance_overlay_update_interval
        ):
            self.performance_overlay_rows = []
            for label, phase, names in rows:
                if phase is None:
                    text = label
                    color = (235, 242, 250)
                else:
                    if isinstance(names, tuple):
                        avg_ms = sum(profiler.average_ms(phase, name) for name in names)
                        last_ms = sum(profiler.latest_ms(phase, name) for name in names)
                    else:
                        avg_ms = profiler.average_ms(phase, names)
                        last_ms = profiler.latest_ms(phase, names)
                    text = f"{label}: {avg_ms:5.2f} ms  last {last_ms:5.2f}"
                    color = (206, 218, 230) if avg_ms < 2.0 else (238, 205, 120)
                    if avg_ms >= 6.0:
                        color = (242, 142, 118)
                self.performance_overlay_rows.append((text, color))
            self.performance_overlay_last_update = now

        text_y = y + panel_height - 18
        for index, (text, color) in enumerate(self.performance_overlay_rows):
            if index >= len(self.performance_overlay_texts):
                self.performance_overlay_texts.append(
                    arcade.Text("", 0, 0, color, 10, batch=self.performance_overlay_batch)
                )
            overlay_text = self.performance_overlay_texts[index]
            if overlay_text.text != text:
                overlay_text.text = text
            overlay_text.x = x + 10
            overlay_text.y = text_y
            if overlay_text.color != color:
                overlay_text.color = color
            if overlay_text.font_size != 10:
                overlay_text.font_size = 10
            text_y -= line_height
        for overlay_text in self.performance_overlay_texts[len(self.performance_overlay_rows):]:
            if overlay_text.text:
                overlay_text.text = ""
        self.performance_overlay_batch.draw()

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
                    batch=self.trade_batch,
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
        label.x = x
        label.y = y

    def clear_unused_trade_text(self):
        for index in range(self.trade_text_pool_cursor, self.trade_text_pool_max_used):
            if index < len(self.trade_text_pool) and self.trade_text_pool[index].text:
                self.trade_text_pool[index].text = ""
        self.trade_text_pool_max_used = max(self.trade_text_pool_max_used, self.trade_text_pool_cursor)
        self.trade_batch.draw()

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

    def map_layer_filter_items(self):
        return [("air_defense", "ПВО", self.air_defense_overlay_enabled)]

    def map_layer_filter_option_rects(self):
        button_x, button_y, button_width, button_height = self.map_layer_button_rect()
        option_width = 190
        option_height = 34
        option_gap = 6
        x = button_x + button_width - option_width
        base_y = button_y + button_height + 10 - (1 - self.map_layer_menu_progress) * 18
        filters_base_y = base_y + len(MAP_LAYERS) * (option_height + option_gap) + 10
        return [
            (x, filters_base_y + index * (option_height + option_gap), option_width, option_height)
            for index, _item in enumerate(self.map_layer_filter_items())
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

    def army_command_layout(self, width, army_count, include_add):
        label_w = 42
        card_w = 56
        card_h = 72
        gap = 7
        usable_width = max(card_w, width - label_w - 17)
        columns = max(1, int((usable_width + gap) // (card_w + gap)))
        total_cards = max(1, army_count + (1 if include_add else 0))
        rows = max(1, math.ceil(total_cards / columns))
        return {
            "label_w": label_w,
            "card_w": card_w,
            "card_h": card_h,
            "gap": gap,
            "columns": columns,
            "rows": rows,
            "height": 10 + rows * card_h + max(0, rows - 1) * gap,
        }

    def army_command_bar_rect(self):
        if not self.human_player:
            return None
        armies = getattr(self.human_player, "armies", []) or []
        if not self.selected_division_ids and not armies:
            return None
        x = self.division_ui_left_edge(360)
        max_right = self.window.width - 78
        width = min(360, max(250, max_right - x))
        if x + width > max_right:
            x = max(10, max_right - width)
        layout = self.army_command_layout(width, len(armies), bool(self.selected_free_divisions()))
        height = min(max(82, layout["height"]), max(82, self.window.height - TOP_UI_HEIGHT - 46))
        return x, 14, width, height

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
        if army_bar_rect and self.active_army_for_plan_controls():
            bottom += 28
        air_rect = self.air_wing_list_rect()
        if air_rect:
            bottom = max(bottom, air_rect[1] + air_rect[3] + 8)
        height = self.division_list_total_height(groups, top, bottom)
        return x, top - height, width, height

    def air_wing_list_rows(self):
        if not self.human_player:
            return []
        rows = list(getattr(self.human_player, "air_wings", []) or [])
        rows.sort(key=lambda wing: (wing.base_tile.r if wing.base_tile else 999, wing.base_tile.q if wing.base_tile else 999, wing.aircraft_type, wing.id))
        return rows

    def air_wing_creation_stock_rows(self):
        if not self.human_player:
            return []
        rows = [
            (aircraft_type, int(count))
            for aircraft_type, count in (getattr(self.human_player, "aircraft_stockpile", {}) or {}).items()
            if int(count) > 0 and aircraft_type in AIRCRAFT_TYPES
        ]
        rows.sort(key=lambda item: AIRCRAFT_TYPES.get(item[0], {}).get("name", item[0]))
        return rows

    def air_wing_mission_label(self, mission):
        return {
            "none": "нет",
            "cas": "CAS",
            "patrol": "патруль",
            "strategic_strike": "удар",
            "intercept": "перехват",
            "air_superiority": "превосх.",
        }.get(mission, mission or "нет")

    def air_wing_missions_summary(self, wing):
        enabled = self.air_wing_enabled_missions(wing)
        if not enabled:
            return "миссий нет"
        labels = [self.air_wing_mission_label(mission) for mission in enabled]
        return ", ".join(labels[:3]) + (f" +{len(labels) - 3}" if len(labels) > 3 else "")

    def air_wing_auto_loadout_summary(self, wing):
        if not wing:
            return "авто БК: нет"
        parts = []
        for mission in self.air_wing_enabled_missions(wing):
            if mission in {"intercept", "air_superiority", "patrol"}:
                aircraft_type = self.air_wing_primary_type_for_mission(wing, mission)
                munition_id = AIR_WING_INTERCEPTOR_LOADOUTS.get(aircraft_type, {}).get("munition_id")
            else:
                aircraft_type = self.air_wing_primary_type_for_mission(wing, mission)
                munition_id = self.air_wing_mission_loadout(aircraft_type, mission)
            if not aircraft_type or not munition_id:
                continue
            mission_label = self.air_wing_mission_label(mission)
            munition_name = MUNITIONS.get(munition_id, {}).get("name", munition_id)
            parts.append(f"{mission_label}: {munition_name}")
        if not parts:
            return "авто БК: нет"
        return "авто БК " + "; ".join(parts[:3]) + (f"; +{len(parts) - 3}" if len(parts) > 3 else "")

    def air_wing_targets_summary(self, wing):
        priorities = list(getattr(wing, "target_priorities", []) or [])
        if not priorities:
            return "целей нет"
        label_by_key = {key: label for key, label, _description in self.air_wing_target_priority_items()}
        labels = [label_by_key.get(key, key) for key in priorities]
        return ", ".join(labels[:2]) + (f" +{len(labels) - 2}" if len(labels) > 2 else "")

    def air_wing_composition_label(self, wing):
        composition = self.air_wing_composition(wing)
        if not composition:
            return "-"
        sorted_types = sorted(composition.items(), key=lambda item: (-item[1], AIRCRAFT_TYPES.get(item[0], {}).get("name", item[0])))
        primary_type, _count = sorted_types[0]
        primary_name = AIRCRAFT_TYPES.get(primary_type, {}).get("name", primary_type)
        if len(sorted_types) > 1:
            return f"{primary_name}+{len(sorted_types) - 1}"
        return primary_name

    def air_wing_risk_label(self, risk_policy):
        return {
            "cautious": "остор.",
            "normal": "норм.",
            "aggressive": "агр.",
            "all_out": "любой",
        }.get(risk_policy, risk_policy or "норм.")

    def air_wing_state_label(self, wing):
        state = getattr(wing, "mission_state", "returning") if wing else "returning"
        return {
            "approach": "заход",
            "attack_run": "атака",
            "defensive": "уклон.",
            "egress": "выход",
            "returning": "база",
            "aborted": "сорвано",
        }.get(state, state or "база")

    def air_wing_panel_layout(self, width, wing_count):
        card_w = 74
        card_h = 48
        gap = 7
        usable_width = max(card_w, width - 20)
        columns = max(1, int((usable_width + gap) // (card_w + gap)))
        total_cards = max(1, wing_count + 1)
        rows = max(1, math.ceil(total_cards / columns))
        selected_controls_h = 74 if self.selected_air_wing_id else 0
        return {
            "card_w": card_w,
            "card_h": card_h,
            "gap": gap,
            "columns": columns,
            "rows": rows,
            "controls_h": selected_controls_h,
            "height": 36 + rows * card_h + max(0, rows - 1) * gap + selected_controls_h + 18,
        }

    def air_wing_list_rect(self):
        rows = self.air_wing_list_rows()
        stock_rows = self.air_wing_creation_stock_rows()
        if not rows and not stock_rows:
            return None
        army_bar_rect = self.army_command_bar_rect()
        y = 14
        height = 82
        preferred_width = 420
        max_right = self.window.width - 78
        if army_bar_rect:
            x = army_bar_rect[0] + army_bar_rect[2] + 10
            width = min(preferred_width, max(270, max_right - x))
            if width < 270:
                x = max(10, max_right - preferred_width)
                width = min(preferred_width, max_right - x)
        else:
            x = self.division_ui_left_edge(preferred_width)
            width = min(preferred_width, max(270, max_right - x))
        layout = self.air_wing_panel_layout(width, len(rows))
        height = min(max(82, layout["height"]), max(82, self.window.height - TOP_UI_HEIGHT - 46))
        return x, y, width, height

    def air_wing_creation_count_limit(self, aircraft_type):
        if not self.human_player or aircraft_type not in AIRCRAFT_TYPES:
            return 0
        reserve = self.aircraft_stockpile_count(self.human_player, aircraft_type)
        base_tile = self.air_wing_creation_base_tile(self.human_player, aircraft_type)
        if not base_tile:
            return 0
        capacity = self.base_capacity_for_wing(base_tile, aircraft_type)
        load = self.based_aircraft_load(base_tile, helicopter=self.aircraft_type_is_helicopter(aircraft_type))
        return max(0, min(reserve, capacity - load))

    def division_list_rows(self):
        rows = self.selected_divisions()
        rows.sort(key=lambda division: (division.template_key, division.id))
        return rows

    def army_resource_summary_rows(self, player):
        if not player:
            return []
        stock = self.ensure_player_stockpiles(player)
        finished = stock.get("finished", {})
        semi_finished = stock.get("semi_finished", {})
        return [
            ("Резерв людей", self.format_resource_amount(getattr(player, "manpower_reserve", 0.0))),
            (
                "Оснащение",
                f"{self.format_resource_amount(finished.get('weapons', 0.0))} / "
                f"{self.format_resource_amount(finished.get('infantry_equipment', 0.0))}",
            ),
            (
                "БК",
                f"{self.format_resource_amount(finished.get('small_arms_ammo', 0.0))} / "
                f"{self.format_resource_amount(finished.get('artillery_ammo', 0.0))}",
            ),
            (
                "Техника",
                f"{self.format_resource_amount(finished.get('vehicles', 0.0))} / "
                f"{self.format_resource_amount(semi_finished.get('refined_fuel', 0.0))}",
            ),
        ]

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
        self.army_plan_preview_target_locked = False
        self.army_plan_preview_last_tile = None
        return True

    def cancel_army_plan_mode(self):
        self.army_plan_mode = None
        self.army_plan_army_id = None
        self.army_plan_drag_active = False
        self.army_plan_start_tile = None
        self.army_plan_preview_tiles = []
        self.army_plan_preview_target_owner = None
        self.army_plan_preview_target_locked = False
        self.army_plan_preview_last_tile = None

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

        ordered_keys = []
        visited = set()

        def walk_line(current_key, previous_key=None):
            visited.add(current_key)
            ordered_keys.append(current_key)
            candidates = [
                key for key in graph[current_key]
                if key != previous_key and key not in visited
            ]
            candidates.sort(key=lambda key: (
                len(graph[key]) > 2,
                len(graph[key]),
                tile_by_key[key].r,
                tile_by_key[key].q,
            ))
            for next_key in candidates:
                if next_key in visited:
                    continue
                walk_line(next_key, current_key)
                remaining_neighbors = [
                    key for key in graph[current_key]
                    if key != previous_key and key not in visited
                ]
                if remaining_neighbors:
                    ordered_keys.append(current_key)

        walk_line(start_key)
        return [tile_by_key[key] for key in ordered_keys]

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

    def army_plan_tile_valid_for_mode(self, army, mode, tile):
        if not army or not tile or self.is_water_tile(tile):
            return False
        if mode == "front_custom":
            target_ids = self.border_target_owner_ids(tile, army.owner)
            if tile.owner is not army.owner or not target_ids:
                return False
            if not self.army_plan_preview_target_locked:
                return True
            return self.army_plan_preview_target_owner in target_ids
        if mode == "defensive_line":
            return tile.owner is army.owner
        if mode == "offensive_line":
            return tile.owner is not army.owner
        return False

    def append_army_plan_preview_tile(self, tile):
        army = self.army_by_id(self.army_plan_army_id)
        mode = self.army_plan_mode
        if not self.army_plan_tile_valid_for_mode(army, mode, tile):
            return False
        if mode == "front_custom" and not self.army_plan_preview_target_locked:
            self.army_plan_preview_target_owner = self.primary_border_target_owner_id(tile, army.owner)
            self.army_plan_preview_target_locked = True
        if not self.army_plan_preview_tiles:
            self.army_plan_preview_tiles = [tile]
            self.army_plan_preview_last_tile = tile
            return True

        last_tile = self.army_plan_preview_last_tile or self.army_plan_preview_tiles[-1]
        if tile == last_tile:
            return False

        valid = lambda candidate: self.army_plan_tile_valid_for_mode(army, mode, candidate)
        distance = self.hex_distance(last_tile, tile)
        if distance <= 1:
            bridge_tiles = [tile]
        elif mode == "front_custom" and distance <= 2:
            bridge_tiles = self.constrained_tile_path(last_tile, tile, valid)
            if not (1 < len(bridge_tiles) <= 3):
                return False
            bridge_tiles = bridge_tiles[1:]
        elif mode == "front_custom":
            return False
        else:
            bridge_tiles = self.constrained_tile_path(last_tile, tile, valid)
            if len(bridge_tiles) <= 1:
                return False
            bridge_tiles = bridge_tiles[1:]

        for bridge_tile in bridge_tiles:
            if self.army_plan_preview_tiles and bridge_tile == self.army_plan_preview_tiles[-1]:
                continue
            self.army_plan_preview_tiles.append(bridge_tile)
            self.army_plan_preview_last_tile = bridge_tile
        return True

    def clear_conflicting_army_plans(self, army, new_plan_type):
        if not army:
            return
        if new_plan_type in ("front", "front_custom"):
            conflicting_types = {"front", "front_custom", "defense"}
        elif new_plan_type == "defense":
            conflicting_types = {"front", "front_custom", "defense", "offensive"}
        elif new_plan_type == "offensive":
            conflicting_types = {"offensive", "defense"}
        else:
            conflicting_types = set()
        if not conflicting_types:
            return

        old_active_front_id = getattr(army, "active_front_plan_id", None)
        army.battle_plans = [
            plan for plan in (getattr(army, "battle_plans", []) or [])
            if plan.plan_type not in conflicting_types
        ]
        if old_active_front_id and not any(plan.id == old_active_front_id for plan in army.battle_plans):
            army.active_front_plan_id = None

    def create_army_battle_plan(self, army, plan_type, tiles, target_owner_id=None, source_plan_id=None, preserve_order=False):
        if not army or not tiles:
            return None
        self.clear_conflicting_army_plans(army, plan_type)
        if preserve_order:
            ordered_tiles = []
            previous_key = None
            for tile in tiles:
                tile_key = self.tile_key(tile)
                if tile_key == previous_key:
                    continue
                ordered_tiles.append(tile)
                previous_key = tile_key
        else:
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
        if not old_tiles:
            return []

        valid = lambda tile: (
            tile.owner is army.owner
            and self.is_front_tile_for_target(tile, army.owner, plan.target_owner_id)
        )
        dirty_tiles = dirty_tiles or []
        dirty_keys = {self.tile_key(tile) for tile in dirty_tiles}
        impacted_keys = set(dirty_keys)
        for dirty_tile in dirty_tiles:
            impacted_keys.update(self.tile_key(neighbor) for neighbor in self.neighbor_tiles(dirty_tile))

        old_unique_tiles = []
        old_seen = set()
        for old_tile in old_tiles:
            old_key = self.tile_key(old_tile)
            if old_key in old_seen:
                continue
            old_seen.add(old_key)
            old_unique_tiles.append(old_tile)

        result_keys = []
        added_dirty_keys = set()
        for old_tile in old_unique_tiles:
            old_key = self.tile_key(old_tile)
            old_removed_by_capture = old_key in impacted_keys and not valid(old_tile)
            if not old_removed_by_capture and old_tile.owner is army.owner:
                result_keys.append(old_key)

            for dirty_tile in dirty_tiles:
                dirty_key = self.tile_key(dirty_tile)
                if dirty_key in added_dirty_keys or dirty_key in old_seen:
                    continue
                if (
                    dirty_tile.owner is army.owner
                    and valid(dirty_tile)
                    and self.hex_distance(dirty_tile, old_tile) == 1
                ):
                    result_keys.append(dirty_key)
                    added_dirty_keys.add(dirty_key)

        refreshed = []
        refreshed_keys = set()
        for tile_key in result_keys:
            if tile_key in refreshed_keys:
                continue
            tile = self.hex_lookup.get(tile_key)
            if not tile or tile.owner is not army.owner:
                continue
            if tile_key in impacted_keys and not valid(tile):
                continue
            refreshed.append(tile)
            refreshed_keys.add(tile_key)
        return refreshed

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
                    can_apply_empty_line = plan.plan_type == "front_custom"
                    if (new_keys or can_apply_empty_line) and new_keys != old_keys:
                        plan.line_tile_keys = new_keys
                        army.plan_update_accumulator = ARMY_PLAN_UPDATE_INTERVAL_HOURS
                        changed = True
                    elif getattr(army, "executing_plan", False):
                        army.plan_update_accumulator = ARMY_PLAN_UPDATE_INTERVAL_HOURS
        return changed

    def update_army_plan_preview(self, current_tile):
        army = self.army_by_id(self.army_plan_army_id)
        if not army or not self.army_plan_start_tile or not current_tile:
            return
        self.append_army_plan_preview_tile(current_tile)

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
            if tile.owner is not army.owner:
                return True
        elif mode == "defensive_line":
            if tile.owner is not army.owner:
                return True
        elif mode == "offensive_line":
            if tile.owner is army.owner:
                return True
        else:
            return True

        self.army_plan_start_tile = tile
        self.army_plan_preview_tiles = []
        self.army_plan_preview_last_tile = None
        self.army_plan_drag_active = True
        self.append_army_plan_preview_tile(tile)
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
                    preserve_order=True,
                )
            elif mode == "defensive_line":
                self.create_army_battle_plan(army, "defense", tiles, preserve_order=True)
            elif mode == "offensive_line":
                source_plan = self.active_front_plan_for_army(army)
                if source_plan and source_plan.plan_type == "defense":
                    source_plan = None
                self.create_army_battle_plan(
                    army,
                    "offensive",
                    tiles,
                    source_plan_id=source_plan.id if source_plan else None,
                    preserve_order=True,
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

    def front_plan_edge_indices(self, tile, target_owner_id=None):
        if not tile:
            return []
        matching_edges = []
        fallback_edges = []
        for edge_index in range(6):
            neighbor = self.hex_lookup.get(self.get_neighbor_coords_for_edge(tile, edge_index))
            if not neighbor or self.is_water_tile(neighbor) or neighbor.owner is tile.owner:
                continue
            fallback_edges.append(edge_index)
            if self.owner_id(neighbor.owner) == target_owner_id:
                matching_edges.append(edge_index)
        return matching_edges or fallback_edges

    def plan_tile_line_points(self, tile, plan_type, target_owner_id=None, previous_point=None):
        return [(tile.center_x, tile.center_y)]

    def draw_tile_line_points_world(self, points, color, width=5, node_radius=8, max_link_distance=None):
        if not points:
            return
        previous_point = None
        if max_link_distance is None:
            max_link_distance = HEX_SIZE * 2.4
        for point in points:
            if point is None:
                previous_point = None
                continue
            if previous_point is not None:
                distance = math.hypot(point[0] - previous_point[0], point[1] - previous_point[1])
                if distance <= max_link_distance:
                    arcade.draw_line(previous_point[0], previous_point[1], point[0], point[1], color, width)
            previous_point = point
        for point in points:
            if point is None:
                continue
            point_x, point_y = point
            arcade.draw_circle_filled(point_x, point_y, node_radius, color)
            arcade.draw_circle_outline(point_x, point_y, node_radius + 2, (18, 22, 26, 220), 2)

    def front_edge_segment_points(self, tile, edge_index, inset=0.82):
        x1, y1 = tile.corners[edge_index]
        x2, y2 = tile.corners[(edge_index + 1) % 6]
        return (
            (
                tile.center_x * (1 - inset) + x1 * inset,
                tile.center_y * (1 - inset) + y1 * inset,
            ),
            (
                tile.center_x * (1 - inset) + x2 * inset,
                tile.center_y * (1 - inset) + y2 * inset,
            ),
        )

    def draw_front_plan_world(self, tiles, target_owner_id, color, width=5, node_radius=8):
        drawn_segments = set()
        node_points = []
        for tile in tiles:
            for edge_index in self.front_plan_edge_indices(tile, target_owner_id):
                segment_key = (self.tile_key(tile), edge_index)
                if segment_key in drawn_segments:
                    continue
                drawn_segments.add(segment_key)
                first, second = self.front_edge_segment_points(tile, edge_index)
                arcade.draw_line(first[0], first[1], second[0], second[1], color, width)
                node_points.append(self.edge_anchor(tile, edge_index))
        for point_x, point_y in node_points:
            arcade.draw_circle_filled(point_x, point_y, node_radius, color)
            arcade.draw_circle_outline(point_x, point_y, node_radius + 2, (18, 22, 26, 220), 2)

    def draw_plan_line_world(self, tiles, plan_type, target_owner_id, color, width=5, node_radius=8):
        if plan_type in ("front", "front_custom"):
            self.draw_front_plan_world(tiles, target_owner_id, color, width=width, node_radius=node_radius)
            return

        points = []
        previous_point = None
        for tile in tiles:
            tile_points = self.plan_tile_line_points(tile, plan_type, target_owner_id, previous_point)
            if (
                previous_point is not None
                and tile_points
                and math.hypot(tile_points[0][0] - previous_point[0], tile_points[0][1] - previous_point[1]) > HEX_SIZE * 2.4
            ):
                points.append(None)
            points.extend(tile_points)
            if tile_points:
                previous_point = tile_points[-1]
        self.draw_tile_line_points_world(points, color, width=width, node_radius=node_radius)

    def preview_plan_type(self):
        if self.army_plan_mode == "front_custom":
            return "front_custom"
        if self.army_plan_mode == "defensive_line":
            return "defense"
        if self.army_plan_mode == "offensive_line":
            return "offensive"
        return self.army_plan_mode or "front"

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
                self.draw_plan_line_world(
                    tiles,
                    plan.plan_type,
                    plan.target_owner_id,
                    color,
                    width=width,
                    node_radius=7 if active else 5,
                )
        if self.army_plan_preview_tiles:
            preview_type = self.preview_plan_type()
            self.draw_plan_line_world(
                self.army_plan_preview_tiles,
                preview_type,
                self.army_plan_preview_target_owner,
                self.army_plan_color(preview_type, preview=True),
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

    def draw_air_wing_ui_tooltip(self):
        if not self.hovered_air_wing_control:
            return
        rect = self.hovered_air_wing_control["rect"]
        title = self.hovered_air_wing_control.get("title", "")
        body = self.hovered_air_wing_control.get("body", "")
        lines = textwrap.wrap(body, width=42)[:5] if body else []
        tooltip_width = 330
        tooltip_height = 32 + len(lines) * 15
        tooltip_x = max(12, min(rect[0], self.window.width - tooltip_width - 12))
        tooltip_y = max(8, min(rect[1] + rect[3] + 8, self.window.height - tooltip_height - TOP_UI_HEIGHT - 8))
        arcade.draw_lbwh_rectangle_filled(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (18, 24, 31, 247))
        arcade.draw_lbwh_rectangle_outline(tooltip_x, tooltip_y, tooltip_width, tooltip_height, (150, 170, 194), 1)
        line_y = tooltip_y + tooltip_height - 18
        self.draw_tooltip_text(title, tooltip_x + 12, line_y, arcade.color.WHITE, 12)
        line_y -= 17
        for line in lines:
            self.draw_tooltip_text(line, tooltip_x + 12, line_y, (220, 230, 240), 10)
            line_y -= 15

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

    def unique_plan_tiles(self, tiles):
        result = []
        seen = set()
        for tile in tiles:
            tile_key = self.tile_key(tile)
            if tile_key in seen:
                continue
            seen.add(tile_key)
            result.append(tile)
        return result

    def weighted_line_targets_for_count(self, tiles, count, owner):
        unique_tiles = self.unique_plan_tiles(tiles)
        if count <= 0 or not unique_tiles:
            return []
        if count >= len(unique_tiles):
            return unique_tiles

        weights = [self.plan_target_weight(owner, tile) for tile in unique_tiles]
        total_weight = sum(weights) or float(len(unique_tiles))
        if total_weight <= 0:
            weights = [1.0 for _tile in unique_tiles]
            total_weight = float(len(unique_tiles))

        cumulative = []
        running = 0.0
        for weight in weights:
            running += weight
            cumulative.append(running)

        selected = []
        selected_keys = set()
        for index in range(count):
            desired = (index + 0.5) * total_weight / count
            target_index = 0
            while target_index < len(cumulative) - 1 and cumulative[target_index] < desired:
                target_index += 1
            tile = unique_tiles[target_index]
            tile_key = self.tile_key(tile)
            if tile_key not in selected_keys:
                selected.append(tile)
                selected_keys.add(tile_key)

        if len(selected) < count:
            for tile in unique_tiles:
                if self.tile_key(tile) in selected_keys:
                    continue
                selected.append(tile)
                selected_keys.add(self.tile_key(tile))
                if len(selected) >= count:
                    break
        return self.order_tile_line(selected, selected[0] if selected else None)

    def assign_nearest_divisions_to_targets(self, divisions, targets):
        assignments = {}
        if not divisions or not targets:
            return assignments, [], list(divisions)

        target_list = self.unique_plan_tiles(targets)
        pairs = []
        for division in divisions:
            if not division.tile:
                continue
            for target_index, target in enumerate(target_list):
                pairs.append((
                    self.hex_distance(division.tile, target),
                    division.id,
                    target_index,
                    division,
                    target,
                ))
        pairs.sort(key=lambda item: (item[0], item[1], item[2]))

        assigned_division_ids = set()
        assigned_target_indices = set()
        for _distance, division_id, target_index, division, target in pairs:
            if division_id in assigned_division_ids or target_index in assigned_target_indices:
                continue
            assignments[division.id] = target
            assigned_division_ids.add(division_id)
            assigned_target_indices.add(target_index)
            if len(assigned_target_indices) >= len(target_list):
                break

        holders = [division for division in divisions if division.id in assigned_division_ids]
        surplus = [division for division in divisions if division.id not in assigned_division_ids]
        return assignments, holders, surplus

    def nearest_line_tile(self, tile, line_tiles):
        if not tile or not line_tiles:
            return None
        return min(line_tiles, key=lambda line_tile: self.hex_distance(tile, line_tile))

    def line_distance(self, tile, line_tiles):
        nearest = self.nearest_line_tile(tile, line_tiles)
        return self.hex_distance(tile, nearest) if nearest else 999

    def covered_plan_target_keys(self, targets, divisions, owner, distance=0):
        covered = set()
        pairs = []
        for target_index, target in enumerate(self.unique_plan_tiles(targets)):
            for division in divisions:
                if division.owner is not owner or division.tile is None or division.route_mode == "retreat":
                    continue
                tile_distance = self.hex_distance(division.tile, target)
                if tile_distance <= distance:
                    pairs.append((tile_distance, target_index, division.id, target, division))
        pairs.sort(key=lambda item: (item[0], item[1], item[2]))

        used_division_ids = set()
        used_target_keys = set()
        for _distance, _target_index, _division_id, target, division in pairs:
            target_key = self.tile_key(target)
            if target_key in used_target_keys or division.id in used_division_ids:
                continue
            covered.add(target_key)
            used_target_keys.add(target_key)
            used_division_ids.add(division.id)
        return covered

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

    def next_offensive_step_target(self, division, offensive_tiles):
        if not division or not division.tile or not offensive_tiles:
            return None
        current_distance = self.line_distance(division.tile, offensive_tiles)
        candidates = [
            neighbor for neighbor in self.neighbor_tiles(division.tile)
            if (
                not self.is_water_tile(neighbor)
                and neighbor.owner is not division.owner
                and self.division_can_capture_tile(division, neighbor)
            )
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda tile: (
                self.line_distance(tile, offensive_tiles) >= current_distance,
                self.line_distance(tile, offensive_tiles),
                self.enemy_pressure_near_tile(tile, division.owner),
                tile.r,
                tile.q,
            ),
        )

    def army_division_counts_by_tile_key(self, divisions):
        counts = {}
        for division in divisions:
            if not division.tile or division.route_mode == "retreat":
                continue
            tile_key = self.tile_key(division.tile)
            counts[tile_key] = counts.get(tile_key, 0) + 1
        return counts

    def allied_division_count_on_tile(self, owner, tile):
        return sum(
            1 for division in self.divisions
            if division.owner is owner and division.tile is tile and division.route_mode != "retreat"
        )

    def cohesive_offensive_orders(self, army, attacking, attack_assignments, offensive_tiles, front_tiles, all_army_divisions):
        raw_orders = []
        source_counts = self.army_division_counts_by_tile_key(all_army_divisions)
        planned_target_counts = {}
        unique_front_tiles = self.unique_plan_tiles(front_tiles)
        endpoint_keys = set()
        if len(unique_front_tiles) >= 2:
            endpoint_keys.add(self.tile_key(unique_front_tiles[0]))
            endpoint_keys.add(self.tile_key(unique_front_tiles[-1]))

        for division in attacking:
            assigned_line_target = attack_assignments.get(division.id)
            target_options = [assigned_line_target] if assigned_line_target else offensive_tiles
            step_target = self.next_offensive_step_target(division, target_options)
            if not step_target:
                continue
            source_front_tile = self.nearest_line_tile(division.tile, front_tiles)
            if not source_front_tile:
                continue
            source_key = self.tile_key(division.tile)
            front_key = self.tile_key(source_front_tile)
            raw_orders.append({
                "division": division,
                "target": step_target,
                "source_key": source_key,
                "front_key": front_key,
                "target_key": self.tile_key(step_target),
                "target_has_enemy": bool(self.enemy_divisions_on_tile(step_target, army.owner)),
                "enemy_count": len(self.enemy_divisions_on_tile(step_target, army.owner)),
            })

        if not raw_orders:
            return []

        for order in raw_orders:
            target = order["target"]
            order["has_neighbor_attack"] = any(
                other is not order
                and self.hex_distance(target, other["target"]) <= 1
                for other in raw_orders
            )

        selected = []
        sent_from_source = {}
        raw_orders.sort(key=lambda order: (
            not order["target_has_enemy"],
            not order["has_neighbor_attack"],
            order["division"].id,
        ))
        for order in raw_orders:
            source_count = source_counts.get(order["source_key"], 0)
            is_endpoint = order["front_key"] in endpoint_keys
            is_empty_push = not order["target_has_enemy"]
            current_target_count = self.allied_division_count_on_tile(army.owner, order["target"])
            target_limit = 1 if is_empty_push else min(3, max(1, order["enemy_count"] + 1))
            planned_to_target = planned_target_counts.get(order["target_key"], 0)
            if current_target_count + planned_to_target >= target_limit:
                continue

            if is_empty_push and source_count <= 1:
                if not order["has_neighbor_attack"] or is_endpoint:
                    continue

            if is_empty_push and source_count > 1:
                max_from_source = max(1, source_count - 1)
            else:
                max_from_source = max(1, source_count)
            already_sent = sent_from_source.get(order["source_key"], 0)
            if already_sent >= max_from_source:
                continue

            selected.append((order["division"], order["target"]))
            sent_from_source[order["source_key"]] = already_sent + 1
            planned_target_counts[order["target_key"]] = planned_to_target + 1
        return selected

    def attack_support_divisions(self, army, lead_division, target_tile):
        # Future aggressive tactics can use this for local breakthroughs; regular offensive plans stay conservative.
        return [
            division for division in self.divisions_for_army(army)
            if (
                division.id != lead_division.id
                and division.tile is not None
                and division.tile.owner is division.owner
                and self.hex_distance(division.tile, target_tile) == 1
                and not self.division_busy_for_army_plan(division)
                and division.organization >= division.max_organization * DIVISION_MIN_ORDER_ORG_RATIO
                and self.division_can_capture_tile(division, target_tile)
            )
        ]

    def issue_group_offensive_order(self, army, lead_division, target_tile, used_division_ids):
        if not target_tile or lead_division.id in used_division_ids:
            return False
        attackers = [lead_division] + [
            division for division in self.attack_support_divisions(army, lead_division, target_tile)
            if division.id not in used_division_ids
        ]
        changed = False
        for division in attackers:
            if self.issue_division_plan_order(division, target_tile, offensive=True):
                used_division_ids.add(division.id)
                changed = True
        return changed

    def execute_army_plan_step(self, army):
        all_army_divisions = self.divisions_for_army(army)
        divisions = [
            division for division in all_army_divisions
            if not self.division_busy_for_army_plan(division)
        ]
        if not divisions:
            return False

        offensive_plan = self.latest_army_plan(army, ("offensive",))
        front_plan = self.active_front_plan_for_army(army)
        changed = False

        if offensive_plan:
            front_tiles = self.battle_plan_tiles(front_plan) if front_plan else []
            offensive_tiles = self.plan_target_slots(army, offensive_plan)
            if front_tiles:
                holder_count = min(
                    len(divisions),
                    max(ARMY_PLAN_FRONT_HOLDER_MIN, min(len(front_tiles), len(divisions))),
                )
                holder_targets = self.weighted_line_targets_for_count(front_tiles, holder_count, army.owner)
                assignments, _holders, surplus = self.assign_nearest_divisions_to_targets(divisions, holder_targets)
                covered_target_keys = self.covered_plan_target_keys(holder_targets, all_army_divisions, army.owner)
                front_ready = True
                for division in divisions:
                    target = assignments.get(division.id)
                    target_needs_holder = target and self.tile_key(target) not in covered_target_keys
                    if (
                        target
                        and (
                            target_needs_holder
                            or self.line_distance(division.tile, front_tiles) > ARMY_PLAN_HOLD_DISTANCE
                        )
                        and self.hex_distance(division.tile, target) > ARMY_PLAN_HOLD_DISTANCE
                    ):
                        if self.issue_division_plan_order(division, target):
                            changed = True
                            front_ready = False
                assigned_holder_ids = set(assignments)
                if not front_ready or len(assigned_holder_ids) < holder_count:
                    return changed
                attacking = []
                attacking_ids = set()
                for division in divisions:
                    target = assignments.get(division.id)
                    if not target:
                        continue
                    if self.line_distance(division.tile, front_tiles) <= ARMY_PLAN_HOLD_DISTANCE:
                        attacking.append(division)
                        attacking_ids.add(division.id)
                for division in surplus:
                    if division.id in attacking_ids:
                        continue
                    if self.line_distance(division.tile, front_tiles) <= ARMY_PLAN_HOLD_DISTANCE:
                        attacking.append(division)
                        attacking_ids.add(division.id)
                if not attacking:
                    return changed
                staging = [
                    division for division in surplus
                    if division not in attacking and self.line_distance(division.tile, front_tiles) > ARMY_PLAN_HOLD_DISTANCE
                ]
                if staging:
                    staging_assignments, _staging_holders, _extra = self.assign_nearest_divisions_to_targets(
                        staging,
                        holder_targets,
                    )
                    for division in staging:
                        target = staging_assignments.get(division.id)
                        if target and self.hex_distance(division.tile, target) > ARMY_PLAN_HOLD_DISTANCE:
                            if self.issue_division_plan_order(division, target):
                                changed = True
            else:
                return changed
            if attacking and offensive_tiles:
                attack_targets = self.weighted_line_targets_for_count(offensive_tiles, len(attacking), army.owner)
                attack_assignments, _attackers, _surplus_attackers = self.assign_nearest_divisions_to_targets(
                    attacking,
                    attack_targets,
                )
                orders = self.cohesive_offensive_orders(
                    army,
                    attacking,
                    attack_assignments,
                    offensive_tiles,
                    front_tiles,
                    all_army_divisions,
                )
                for division, step_target in orders:
                    if self.issue_division_plan_order(division, step_target, offensive=True):
                        changed = True
            return changed

        hold_plan = front_plan
        if not hold_plan:
            return False
        slots = self.plan_target_slots(army, hold_plan)
        target_count = min(len(divisions), len(self.unique_plan_tiles(slots)))
        holder_targets = self.weighted_line_targets_for_count(slots, target_count, army.owner)
        assignments, _holders, surplus = self.assign_nearest_divisions_to_targets(divisions, holder_targets)
        covered_target_keys = self.covered_plan_target_keys(holder_targets, all_army_divisions, army.owner)
        for division, target in assignments.items():
            division = self.division_by_id(division)
            target_needs_holder = target and self.tile_key(target) not in covered_target_keys
            if (
                division
                and target
                and (
                    target_needs_holder
                    or self.line_distance(division.tile, slots) > ARMY_PLAN_HOLD_DISTANCE
                )
                and self.hex_distance(division.tile, target) > ARMY_PLAN_HOLD_DISTANCE
            ):
                if self.issue_division_plan_order(division, target):
                    changed = True
        for division in surplus:
            if self.line_distance(division.tile, slots) <= ARMY_PLAN_HOLD_DISTANCE:
                continue
            target = self.nearest_line_tile(division.tile, slots)
            if target:
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
        geometry_key = (
            rect, self.active_division_list_army_id, self.hovered_division_detach_button,
            tuple(sorted(self.selected_division_ids)), self.division_list_scroll_index,
            tuple(sorted(self.division_list_scroll_indices.items(), key=lambda item: str(item[0]))),
            tuple((group["key"], tuple((d.id, d.template_key) for d in group["rows"])) for group in groups),
        )
        rebuild_geometry = geometry_key != getattr(self, "division_list_geometry_key", None)
        if rebuild_geometry:
            self.division_list_icon_shape_list = arcade.shape_list.ShapeElementList()
        shapes = self.division_list_icon_shape_list

        def rectangle(rectangle_rect, fill, border=None, border_width=1):
            if rebuild_geometry:
                self.append_trade_rect_shapes(shapes, rectangle_rect, fill, border, border_width)

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
            rectangle(group_rect, fill, border, 2 if active else 1)

            close_rect = (panel_x + panel_width - 34, group_y + group_height - 30, 24, 22)
            self.division_list_close_rects.append((close_rect, group["key"]))
            close_fill = (70, 50, 54, 235)
            rectangle(close_rect, close_fill, (116, 136, 156))
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
                rectangle((detach_x, detach_y, detach_size, detach_size), detach_fill, (110, 132, 154))
                center_x = detach_x + detach_size / 2
                center_y = detach_y + detach_size / 2
                if rebuild_geometry:
                    shapes.append(arcade.shape_list.create_ellipse_outline(center_x, center_y, 14, 14, (220, 226, 232), 2))
                    shapes.append(arcade.shape_list.create_line(center_x - 8, center_y + 8, center_x + 8, center_y - 8, (224, 70, 70), 3))

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
                    rectangle(row_rect, fill, (76, 98, 120))
                    icon_x = row_rect[0] + 22
                    icon_y = row_rect[1] + row_rect[3] / 2
                    if rebuild_geometry:
                        self.append_division_template_icon(
                            shapes, division.template_key, icon_x, icon_y + 2, 27,
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
                    rectangle((track_x, track_y, 4, track_h), (48, 62, 78, 190))
                    rectangle((track_x, thumb_y, 4, thumb_h), (142, 166, 194, 230))

            current_top = group_y - gap

        self.division_list_geometry_key = geometry_key
        shapes.draw()

    def draw_air_wing_list_panel(self):
        rows = self.air_wing_list_rows()
        rect = self.air_wing_list_rect()
        self.air_wing_list_panel_rect = rect
        self.air_wing_list_row_rects = []
        self.air_wing_command_add_rect = None
        self.air_wing_command_button_rects = []
        self.air_wing_creation_panel_rect = None
        self.air_wing_creation_row_rects = []
        self.air_wing_creation_minus_rect = None
        self.air_wing_creation_plus_rect = None
        self.air_wing_creation_slider_rect = None
        self.air_wing_creation_create_rect = None
        self.air_wing_mission_option_rects = []
        self.air_wing_target_option_rects = []
        self.air_wing_edit_button_rects = []
        self.air_wing_risk_option_rects = []
        self.air_wing_dropdown_panel_rects = []
        if not rect:
            return

        panel_x, panel_y, panel_width, panel_height = rect
        arcade.draw_lbwh_rectangle_filled(panel_x, panel_y, panel_width, panel_height, (17, 24, 34, 238))
        arcade.draw_lbwh_rectangle_outline(panel_x, panel_y, panel_width, panel_height, (86, 116, 150), 2)
        self.draw_ui_text("Авиакрылья", panel_x + 12, panel_y + panel_height - 18, arcade.color.WHITE, 13)
        selected_count = len(self.selected_air_wings())
        header_hint = f"выбрано {selected_count}" if selected_count > 1 else "Shift: несколько"
        self.draw_ui_text(header_hint, panel_x + panel_width - 12, panel_y + panel_height - 18,
                          (150, 166, 184), 9, anchor_x="right")

        selected_wing = self.air_wing_by_id(self.selected_air_wing_id)
        layout = self.air_wing_panel_layout(panel_width, len(rows))
        card_gap = layout["gap"]
        card_w = layout["card_w"]
        card_h = layout["card_h"]
        columns = layout["columns"]
        grid_top = panel_y + panel_height - 34
        for index, wing in enumerate(rows):
            row_index = index // columns
            column_index = index % columns
            card_x = panel_x + 10 + column_index * (card_w + card_gap)
            card_y = grid_top - (row_index + 1) * card_h - row_index * card_gap
            selected = wing.id in (getattr(self, "selected_air_wing_ids", set()) or set())
            card_rect = (card_x, card_y, card_w, card_h)
            fill = (48, 76, 104, 230) if selected else (28, 39, 52, 224)
            border = (128, 180, 220) if selected else (74, 96, 122)
            arcade.draw_lbwh_rectangle_filled(*card_rect, fill)
            arcade.draw_lbwh_rectangle_outline(*card_rect, border, 2 if selected else 1)
            self.air_wing_list_row_rects.append((card_rect, wing.id))
            self.hex_air_wing_row_rects.append((card_rect, wing.id))
            aircraft_name = self.air_wing_composition_label(wing)
            short_name = aircraft_name
            if len(short_name) > 11:
                short_name = short_name[:10] + "."
            base_label = f"{wing.base_tile.q}:{wing.base_tile.r}" if wing.base_tile else "-"
            mission_label = self.air_wing_missions_summary(wing)
            self.draw_ui_text(short_name, card_x + 6, card_y + 34, arcade.color.WHITE, 8)
            self.draw_ui_text(f"x{wing.aircraft_count}", card_x + card_w - 6, card_y + 24,
                              (220, 232, 242), 11, anchor_x="right")
            self.draw_ui_text(mission_label[:8], card_x + 6, card_y + 8, (166, 184, 202), 8)
            state_label = self.air_wing_state_label(wing)
            self.draw_ui_text(f"{state_label} {base_label}", card_x + card_w - 6, card_y + 8, (166, 184, 202), 8, anchor_x="right")

        add_index = len(rows)
        add_row = add_index // columns
        add_column = add_index % columns
        add_rect = (
            panel_x + 10 + add_column * (card_w + card_gap),
            grid_top - (add_row + 1) * card_h - add_row * card_gap,
            card_w,
            card_h,
        )
        self.air_wing_command_add_rect = add_rect
        add_active = self.air_wing_creation_open
        arcade.draw_lbwh_rectangle_filled(*add_rect, (42, 58, 74, 235) if add_active else (28, 39, 48, 225))
        arcade.draw_lbwh_rectangle_outline(*add_rect, (150, 190, 224) if add_active else (86, 108, 128), 2)
        self.draw_ui_text("+", add_rect[0] + add_rect[2] / 2, add_rect[1] + add_rect[3] / 2 + 2,
                          arcade.color.WHITE, 24, anchor_x="center", anchor_y="center")

        if selected_wing:
            controls_y = panel_y + 9
            base_label = f"{selected_wing.base_tile.q}:{selected_wing.base_tile.r}" if selected_wing.base_tile else "-"
            target_label = self.air_wing_operation_area_summary(selected_wing)
            status_label = self.air_wing_state_label(selected_wing)
            if selected_wing.last_air_combat_summary:
                status_label = f"{status_label}, {selected_wing.last_air_combat_summary}"
            interceptor_label = ""
            if getattr(selected_wing, "interceptor_ammo_capacity", 0) > 0:
                munition_name = MUNITIONS.get(getattr(selected_wing, "interceptor_munition", ""), {}).get("name", "УРВВ")
                interceptor_label = (
                    f" | {munition_name}: "
                    f"{getattr(selected_wing, 'interceptor_ammo', 0)}/"
                    f"{getattr(selected_wing, 'interceptor_ammo_capacity', 0)}"
                )
            self.draw_ui_text(
                f"{self.air_wing_missions_summary(selected_wing)} | {status_label} | риск {self.air_wing_risk_label(selected_wing.risk_policy)} | база {base_label} | {target_label}{interceptor_label} | цели: {self.air_wing_targets_summary(selected_wing)}",
                panel_x + 12,
                controls_y + 47,
                (184, 202, 218),
                9,
            )
            self.draw_ui_text(
                self.air_wing_auto_loadout_summary(selected_wing),
                panel_x + 12,
                controls_y + 33,
                (154, 176, 196),
                8,
            )
            button_defs = [
                ("mission", "Миссии", 58, "Выбрать автоматические миссии крыла: CAS, перехват, патруль, превосходство или удар."),
                ("targets", "Цели", 48, "Выбрать категории наземных целей для автоматической миссии Удар."),
                ("target", "Район", 48, "Редактировать район ответственности: ЛКМ заменить, Shift+ЛКМ добавить, Shift+ПКМ убрать."),
                ("rebase", "База", 44, "Перебазировать крыло на другой аэродром или вертолетную площадку."),
                ("risk", "Риск", 42, "Сменить профиль риска: осторожно, нормально или агрессивно."),
                ("edit", "Ред.", 42, "Изменить численность крыла, добавляя самолеты из резерва или возвращая их в резерв."),
                ("strike_manual", "Удар+", 54, "Создать отдельную ударную миссию. Заглушка для следующего слоя."),
            ]
            button_x = panel_x + panel_width - 12
            for action, label, width, tooltip in reversed(button_defs):
                button_x -= width
                rect = (button_x, controls_y - 2, width, 22)
                active = (
                    action == "mission" and self.air_wing_mission_menu_wing_id == selected_wing.id
                ) or (
                    action == "targets" and self.air_wing_target_menu_wing_id == selected_wing.id
                ) or (
                    action == "edit" and self.air_wing_edit_menu_wing_id == selected_wing.id
                ) or (
                    action == "risk" and self.air_wing_risk_menu_wing_id == selected_wing.id
                ) or (
                    action == "target" and selected_wing.id in (self.air_wing_target_mode_ids or set())
                ) or (
                    action == "rebase" and selected_wing.id in (self.air_wing_rebase_mode_ids or set())
                )
                arcade.draw_lbwh_rectangle_filled(*rect, (58, 82, 108, 235) if active else (32, 42, 54, 230))
                arcade.draw_lbwh_rectangle_outline(*rect, (150, 185, 218) if active else (90, 110, 132), 1)
                self.draw_ui_text(label, rect[0] + rect[2] / 2, rect[1] + rect[3] / 2 + 1,
                                  arcade.color.WHITE, 10, anchor_x="center", anchor_y="center")
                self.air_wing_command_button_rects.append((rect, action, selected_wing.id, tooltip))
                button_x -= 6

            dropdown_y = panel_y + panel_height + 8
            if self.air_wing_mission_menu_wing_id == selected_wing.id:
                dropdown_y = self.draw_air_wing_mission_dropdown(selected_wing, panel_x, dropdown_y, panel_width)
            if self.air_wing_target_menu_wing_id == selected_wing.id:
                dropdown_y = self.draw_air_wing_target_dropdown(selected_wing, panel_x, dropdown_y, panel_width)
            if self.air_wing_risk_menu_wing_id == selected_wing.id:
                dropdown_y = self.draw_air_wing_risk_dropdown(selected_wing, panel_x, dropdown_y, panel_width)
            if self.air_wing_edit_menu_wing_id == selected_wing.id:
                dropdown_y = self.draw_air_wing_edit_dropdown(selected_wing, panel_x, dropdown_y, panel_width)

        if self.air_wing_creation_open:
            self.draw_air_wing_creation_panel(panel_x, panel_y + panel_height + 8, panel_width)

    def draw_air_wing_dropdown_panel(self, x, y, width, title, rows):
        row_h = 27
        panel_height = 38 + len(rows) * row_h
        self.air_wing_dropdown_panel_rects.append((x, y, width, panel_height))
        arcade.draw_lbwh_rectangle_filled(x, y, width, panel_height, (18, 24, 32, 244))
        arcade.draw_lbwh_rectangle_outline(x, y, width, panel_height, (96, 122, 150), 2)
        self.draw_ui_text(title, x + 12, y + panel_height - 20, arcade.color.WHITE, 13)
        return y + panel_height, y + panel_height - 48, row_h

    def draw_air_wing_mission_dropdown(self, wing, x, y, width):
        rows = self.air_wing_available_auto_missions()
        panel_top, row_y, row_h = self.draw_air_wing_dropdown_panel(x, y, width, "Автоматические миссии", rows)
        allowed = set(self.air_wing_allowed_missions(wing))
        enabled = set(self.air_wing_enabled_missions(wing))
        for mission_key, label, description in rows:
            available = mission_key in allowed
            checked = mission_key in enabled
            row_rect = (x + 10, row_y - 5, width - 20, row_h - 3)
            fill = (42, 62, 78, 220) if available else (34, 36, 40, 180)
            if checked:
                fill = (48, 82, 60, 230)
            arcade.draw_lbwh_rectangle_filled(*row_rect, fill)
            arcade.draw_lbwh_rectangle_outline(*row_rect, (78, 102, 128), 1)
            box_x = row_rect[0] + 8
            box_y = row_rect[1] + 5
            arcade.draw_lbwh_rectangle_outline(box_x, box_y, 14, 14, (190, 206, 220) if available else (104, 112, 122), 1)
            if checked:
                self.draw_ui_text("✓", box_x + 7, box_y + 8, (180, 238, 166), 11, anchor_x="center", anchor_y="center")
            text_color = arcade.color.WHITE if available else (128, 136, 145)
            self.draw_ui_text(label, row_rect[0] + 30, row_rect[1] + row_rect[3] / 2 + 1, text_color, 10, anchor_y="center")
            status = "" if available else "недоступно"
            if status:
                self.draw_ui_text(status, row_rect[0] + row_rect[2] - 8, row_rect[1] + row_rect[3] / 2 + 1,
                                  (150, 158, 168), 9, anchor_x="right", anchor_y="center")
            self.air_wing_mission_option_rects.append((row_rect, wing.id, mission_key, description, available))
            row_y -= row_h
        return panel_top + 8

    def draw_air_wing_target_dropdown(self, wing, x, y, width):
        rows = self.air_wing_target_priority_items()
        panel_top, row_y, row_h = self.draw_air_wing_dropdown_panel(
            x,
            y,
            width,
            "Список целей для миссии Удар",
            [("__all__", "Выбрать все", "Включить все категории целей для выбранных авиакрыльев.")] + rows,
        )
        selected = set(getattr(wing, "target_priorities", []) or [])
        all_selected = all(target_key in selected for target_key, _label, _description in rows)
        all_rect = (x + 10, row_y - 5, width - 20, row_h - 3)
        arcade.draw_lbwh_rectangle_filled(*all_rect, (50, 70, 92, 230) if all_selected else (36, 50, 66, 225))
        arcade.draw_lbwh_rectangle_outline(*all_rect, (102, 136, 170), 1)
        self.draw_ui_text("Выбрать все", all_rect[0] + 12, all_rect[1] + all_rect[3] / 2 + 1,
                          arcade.color.WHITE, 10, anchor_y="center")
        self.draw_ui_text("все категории", all_rect[0] + all_rect[2] - 8, all_rect[1] + all_rect[3] / 2 + 1,
                          (174, 194, 212), 9, anchor_x="right", anchor_y="center")
        self.air_wing_target_option_rects.append((
            all_rect,
            wing.id,
            "__all__",
            "Включить все категории целей для выбранных авиакрыльев.",
        ))
        row_y -= row_h
        for target_key, label, description in rows:
            checked = target_key in selected
            row_rect = (x + 10, row_y - 5, width - 20, row_h - 3)
            fill = (48, 72, 58, 230) if checked else (30, 42, 54, 220)
            arcade.draw_lbwh_rectangle_filled(*row_rect, fill)
            arcade.draw_lbwh_rectangle_outline(*row_rect, (78, 102, 128), 1)
            box_x = row_rect[0] + 8
            box_y = row_rect[1] + 5
            arcade.draw_lbwh_rectangle_outline(box_x, box_y, 14, 14, (190, 206, 220), 1)
            if checked:
                self.draw_ui_text("✓", box_x + 7, box_y + 8, (180, 238, 166), 11, anchor_x="center", anchor_y="center")
            self.draw_ui_text(label, row_rect[0] + 30, row_rect[1] + row_rect[3] / 2 + 1,
                              arcade.color.WHITE, 10, anchor_y="center")
            self.air_wing_target_option_rects.append((row_rect, wing.id, target_key, description))
            row_y -= row_h
        return panel_top + 8

    def draw_air_wing_risk_dropdown(self, wing, x, y, width):
        rows = self.air_wing_risk_items()
        panel_top, row_y, row_h = self.draw_air_wing_dropdown_panel(x, y, width, "Режим риска", rows)
        for risk_key, label, description in rows:
            selected = wing.risk_policy == risk_key
            row_rect = (x + 10, row_y - 5, width - 20, row_h - 3)
            fill = (48, 72, 58, 230) if selected else (30, 42, 54, 220)
            arcade.draw_lbwh_rectangle_filled(*row_rect, fill)
            arcade.draw_lbwh_rectangle_outline(*row_rect, (78, 102, 128), 1)
            marker = "✓" if selected else ""
            self.draw_ui_text(marker, row_rect[0] + 15, row_rect[1] + row_rect[3] / 2 + 1,
                              (180, 238, 166), 11, anchor_x="center", anchor_y="center")
            self.draw_ui_text(label, row_rect[0] + 32, row_rect[1] + row_rect[3] / 2 + 1,
                              arcade.color.WHITE, 10, anchor_y="center")
            self.air_wing_risk_option_rects.append((row_rect, wing.id, risk_key, description))
            row_y -= row_h
        return panel_top + 8

    def draw_air_wing_edit_dropdown(self, wing, x, y, width):
        composition = self.air_wing_composition(wing)
        candidate_types = set(composition.keys())
        for aircraft_type, reserve in self.air_wing_creation_stock_rows():
            if reserve > 0:
                candidate_types.add(aircraft_type)
        rows = sorted(candidate_types, key=lambda aircraft_type: AIRCRAFT_TYPES.get(aircraft_type, {}).get("name", aircraft_type))
        if not rows:
            rows = [wing.aircraft_type]

        row_h = 34
        panel_height = 44 + len(rows) * row_h + 8
        self.air_wing_dropdown_panel_rects.append((x, y, width, panel_height))
        arcade.draw_lbwh_rectangle_filled(x, y, width, panel_height, (18, 24, 32, 244))
        arcade.draw_lbwh_rectangle_outline(x, y, width, panel_height, (96, 122, 150), 2)
        self.draw_ui_text("Редактирование состава крыла", x + 12, y + panel_height - 20, arcade.color.WHITE, 13)
        self.draw_ui_text(
            f"Всего в крыле: {wing.aircraft_count}",
            x + width - 12,
            y + panel_height - 20,
            (184, 202, 218),
            10,
            anchor_x="right",
        )
        row_y = y + panel_height - 70
        button_defs = [
            (-10, "-10", "Вернуть десять самолетов этого типа в резерв."),
            (-1, "-1", "Вернуть один самолет этого типа в резерв."),
            (1, "+1", "Добавить один самолет этого типа из резерва в крыло."),
            (10, "+10", "Добавить десять самолетов этого типа из резерва в крыло."),
        ]
        for aircraft_type in rows:
            count_in_wing = composition.get(aircraft_type, 0)
            reserve = self.aircraft_stockpile_count(wing.owner, aircraft_type)
            extra_capacity = self.air_wing_extra_capacity_for_type(wing, aircraft_type)
            row_rect = (x + 10, row_y - 6, width - 20, row_h - 4)
            arcade.draw_lbwh_rectangle_filled(*row_rect, (28, 38, 50, 220))
            arcade.draw_lbwh_rectangle_outline(*row_rect, (78, 102, 128), 1)
            name = AIRCRAFT_TYPES.get(aircraft_type, {}).get("name", aircraft_type)
            if len(name) > 22:
                name = name[:21] + "."
            self.draw_ui_text(name, row_rect[0] + 8, row_rect[1] + row_rect[3] - 9,
                              arcade.color.WHITE, 9, anchor_y="center")
            self.draw_ui_text(
                f"в крыле {count_in_wing} | рез. {reserve} | мест {extra_capacity}",
                row_rect[0] + 8,
                row_rect[1] + 8,
                (168, 186, 202),
                8,
                anchor_y="center",
            )
            button_x = row_rect[0] + row_rect[2] - 166
            for delta, label, description in button_defs:
                rect = (button_x, row_rect[1] + 5, 36, 20)
                enabled = (
                    (delta < 0 and count_in_wing > 0 and wing.aircraft_count > 1)
                    or (delta > 0 and reserve > 0 and extra_capacity > 0)
                )
                fill = (34, 46, 58, 230) if enabled else (38, 40, 44, 190)
                text_color = arcade.color.WHITE if enabled else (132, 138, 146)
                arcade.draw_lbwh_rectangle_filled(*rect, fill)
                arcade.draw_lbwh_rectangle_outline(*rect, (92, 112, 136) if enabled else (72, 78, 86), 1)
                self.draw_ui_text(label, rect[0] + rect[2] / 2, rect[1] + rect[3] / 2 + 1,
                                  text_color, 9, anchor_x="center", anchor_y="center")
                self.air_wing_edit_button_rects.append((rect, wing.id, aircraft_type, delta, description))
                button_x += 42
            row_y -= row_h
        return y + panel_height + 8

    def draw_air_wing_creation_panel(self, x, y, width):
        stock_rows = self.air_wing_creation_stock_rows()
        visible_rows = stock_rows[:8]
        panel_height = min(320, 54 + max(1, len(visible_rows)) * 30 + 42)
        self.air_wing_creation_panel_rect = (x, y, width, panel_height)
        arcade.draw_lbwh_rectangle_filled(x, y, width, panel_height, (18, 24, 32, 242))
        arcade.draw_lbwh_rectangle_outline(x, y, width, panel_height, (96, 122, 150), 2)
        self.draw_ui_text("Создать авиакрыло", x + 12, y + panel_height - 20, arcade.color.WHITE, 13)

        row_y = y + panel_height - 52
        if not stock_rows:
            self.draw_ui_text("Нет самолетов в резерве", x + 12, row_y + 8, (174, 188, 202), 10)
            return

        for aircraft_type, reserve in visible_rows:
            row_rect = (x + 10, row_y - 5, width - 20, 25)
            selected = aircraft_type == self.air_wing_creation_type
            fill = (50, 72, 94, 225) if selected else (28, 38, 50, 210)
            arcade.draw_lbwh_rectangle_filled(*row_rect, fill)
            arcade.draw_lbwh_rectangle_outline(*row_rect, (78, 102, 128), 1)
            self.air_wing_creation_row_rects.append((row_rect, aircraft_type))
            name = AIRCRAFT_TYPES.get(aircraft_type, {}).get("name", aircraft_type)
            if len(name) > 28:
                name = name[:27] + "."
            limit = self.air_wing_creation_count_limit(aircraft_type)
            self.draw_ui_text(name, row_rect[0] + 8, row_rect[1] + row_rect[3] / 2 + 1,
                              arcade.color.WHITE, 10, anchor_y="center")
            self.draw_ui_text(f"рез. {reserve} | мест {limit}", row_rect[0] + row_rect[2] - 8,
                              row_rect[1] + row_rect[3] / 2 + 1, (170, 188, 204), 9,
                              anchor_x="right", anchor_y="center")
            row_y -= 30

        if not self.air_wing_creation_type and stock_rows:
            self.air_wing_creation_type = stock_rows[0][0]
        selected_type = self.air_wing_creation_type
        limit = self.air_wing_creation_count_limit(selected_type)
        self.air_wing_creation_count = max(1, min(max(1, limit), int(self.air_wing_creation_count)))

        controls_y = y + 12
        minus_rect = (x + 12, controls_y, 28, 24)
        plus_rect = (x + 98, controls_y, 28, 24)
        slider_rect = (x + 140, controls_y, max(60, width - 286), 24)
        create_rect = (x + width - 122, controls_y, 110, 24)
        self.air_wing_creation_minus_rect = minus_rect
        self.air_wing_creation_plus_rect = plus_rect
        self.air_wing_creation_slider_rect = slider_rect
        self.air_wing_creation_create_rect = create_rect
        for rect, label in ((minus_rect, "-"), (plus_rect, "+")):
            arcade.draw_lbwh_rectangle_filled(*rect, (34, 46, 58, 230))
            arcade.draw_lbwh_rectangle_outline(*rect, (92, 112, 136), 1)
            self.draw_ui_text(label, rect[0] + rect[2] / 2, rect[1] + rect[3] / 2 + 1,
                              arcade.color.WHITE, 14, anchor_x="center", anchor_y="center")
        self.draw_ui_text(str(self.air_wing_creation_count), x + 70, controls_y + 13,
                          arcade.color.WHITE, 12, anchor_x="center", anchor_y="center")
        slider_x, slider_hit_y, slider_w, _slider_hit_h = slider_rect
        slider_y = slider_hit_y + 9
        slider_h = 6
        ratio = 0.0 if limit <= 1 else (self.air_wing_creation_count - 1) / max(1, limit - 1)
        knob_x = slider_x + slider_w * max(0.0, min(1.0, ratio))
        arcade.draw_lbwh_rectangle_filled(slider_x, slider_y, slider_w, slider_h, (46, 58, 70, 230))
        arcade.draw_lbwh_rectangle_filled(slider_x, slider_y, slider_w * max(0.0, min(1.0, ratio)), slider_h, (98, 146, 190, 235))
        arcade.draw_circle_filled(knob_x, slider_y + slider_h / 2, 6, (218, 232, 242))
        arcade.draw_circle_outline(knob_x, slider_y + slider_h / 2, 6, (86, 112, 140), 1)
        range_label = f"1-{limit}" if limit > 0 else "нет мест"
        self.draw_ui_text(range_label, slider_x + slider_w / 2, slider_y + 17,
                          (150, 166, 184), 8, anchor_x="center")
        can_create = bool(selected_type and limit > 0)
        fill = (52, 78, 60, 235) if can_create else (54, 55, 58, 210)
        arcade.draw_lbwh_rectangle_filled(*create_rect, fill)
        arcade.draw_lbwh_rectangle_outline(*create_rect, (116, 152, 120) if can_create else (90, 94, 98), 1)
        self.draw_ui_text("Создать", create_rect[0] + create_rect[2] / 2, create_rect[1] + create_rect[3] / 2 + 1,
                          arcade.color.WHITE if can_create else (158, 164, 170), 11,
                          anchor_x="center", anchor_y="center")

    def handle_air_wing_list_click(self, x, y, modifiers=0):
        for rect, wing_id, mission_key, _description, available in self.air_wing_mission_option_rects:
            if self.point_in_rect(x, y, rect):
                if available:
                    wing = self.air_wing_by_id(wing_id)
                    enable = mission_key not in self.air_wing_enabled_missions(wing)
                    for command_wing in self.command_air_wings_for(wing):
                        self.set_air_wing_enabled_mission(command_wing, mission_key, enable)
                return True

        for rect, wing_id, target_key, _description in self.air_wing_target_option_rects:
            if self.point_in_rect(x, y, rect):
                wing = self.air_wing_by_id(wing_id)
                if target_key == "__all__":
                    all_targets = [key for key, _label, _description in self.air_wing_target_priority_items()]
                    for command_wing in self.command_air_wings_for(wing):
                        command_wing.target_priorities = list(all_targets)
                    return True
                enable = target_key not in (getattr(wing, "target_priorities", []) or [])
                for command_wing in self.command_air_wings_for(wing):
                    self.set_air_wing_target_priority(command_wing, target_key, enable)
                return True

        for rect, wing_id, risk_key, _description in self.air_wing_risk_option_rects:
            if self.point_in_rect(x, y, rect):
                wing = self.air_wing_by_id(wing_id)
                for command_wing in self.command_air_wings_for(wing):
                    command_wing.risk_policy = risk_key
                self.air_wing_risk_menu_wing_id = None
                return True

        for rect, wing_id, aircraft_type, delta, _description in self.air_wing_edit_button_rects:
            if self.point_in_rect(x, y, rect):
                wing = self.air_wing_by_id(wing_id)
                self.transfer_aircraft_to_wing(wing, aircraft_type, delta)
                return True

        if self.air_wing_creation_open and self.air_wing_creation_panel_rect and self.point_in_rect(x, y, self.air_wing_creation_panel_rect):
            for rect, aircraft_type in self.air_wing_creation_row_rects:
                if self.point_in_rect(x, y, rect):
                    self.air_wing_creation_type = aircraft_type
                    limit = self.air_wing_creation_count_limit(aircraft_type)
                    self.air_wing_creation_count = max(1, min(max(1, limit), self.air_wing_creation_count))
                    return True
            selected_type = self.air_wing_creation_type
            limit = self.air_wing_creation_count_limit(selected_type)
            step = 10 if self.shift_modifier_active(modifiers) else 1
            if self.air_wing_creation_minus_rect and self.point_in_rect(x, y, self.air_wing_creation_minus_rect):
                self.air_wing_creation_count = max(1, self.air_wing_creation_count - step)
                return True
            if self.air_wing_creation_plus_rect and self.point_in_rect(x, y, self.air_wing_creation_plus_rect):
                self.air_wing_creation_count = min(max(1, limit), self.air_wing_creation_count + step)
                return True
            if self.air_wing_creation_slider_rect and self.point_in_rect(x, y, self.air_wing_creation_slider_rect):
                slider_x, _slider_y, slider_w, _slider_h = self.air_wing_creation_slider_rect
                if limit > 1 and slider_w > 0:
                    ratio = max(0.0, min(1.0, (x - slider_x) / slider_w))
                    self.air_wing_creation_count = max(1, min(limit, int(round(1 + ratio * (limit - 1)))))
                return True
            if self.air_wing_creation_create_rect and self.point_in_rect(x, y, self.air_wing_creation_create_rect):
                if selected_type and limit > 0:
                    wing = self.create_air_wing_from_stockpile(self.human_player, selected_type, self.air_wing_creation_count)
                    if wing:
                        self.select_air_wing(wing)
                        if wing.base_tile:
                            self.set_single_selected_tile(wing.base_tile)
                        self.air_wing_creation_open = False
                return True
            return True

        if not self.air_wing_list_panel_rect or not self.point_in_rect(x, y, self.air_wing_list_panel_rect):
            if any(self.point_in_rect(x, y, rect) for rect in self.air_wing_dropdown_panel_rects):
                return True
            if self.air_wing_creation_open:
                self.air_wing_creation_open = False
            self.air_wing_mission_menu_wing_id = None
            self.air_wing_target_menu_wing_id = None
            self.air_wing_edit_menu_wing_id = None
            self.air_wing_risk_menu_wing_id = None
            return False
        for rect, action, wing_id, _tooltip in self.air_wing_command_button_rects:
            if not self.point_in_rect(x, y, rect):
                continue
            wing = self.air_wing_by_id(wing_id)
            if not wing:
                return True
            if wing.id in (self.selected_air_wing_ids or set()):
                self.selected_air_wing_id = wing.id
            else:
                self.select_air_wing(wing)
            if action == "mission":
                self.air_wing_mission_menu_wing_id = None if self.air_wing_mission_menu_wing_id == wing.id else wing.id
                self.air_wing_target_menu_wing_id = None
                self.air_wing_edit_menu_wing_id = None
                self.air_wing_risk_menu_wing_id = None
                self.air_wing_creation_open = False
            elif action == "targets":
                self.air_wing_target_menu_wing_id = None if self.air_wing_target_menu_wing_id == wing.id else wing.id
                self.air_wing_mission_menu_wing_id = None
                self.air_wing_edit_menu_wing_id = None
                self.air_wing_risk_menu_wing_id = None
                self.air_wing_creation_open = False
            elif action == "risk":
                self.air_wing_risk_menu_wing_id = None if self.air_wing_risk_menu_wing_id == wing.id else wing.id
                self.air_wing_mission_menu_wing_id = None
                self.air_wing_target_menu_wing_id = None
                self.air_wing_edit_menu_wing_id = None
                self.air_wing_creation_open = False
            elif action == "target":
                self.set_air_wing_target_mode_for(self.command_air_wings_for(wing))
            elif action == "rebase":
                self.set_air_wing_rebase_mode_for(self.command_air_wings_for(wing))
            elif action == "edit":
                self.air_wing_edit_menu_wing_id = None if self.air_wing_edit_menu_wing_id == wing.id else wing.id
                self.air_wing_mission_menu_wing_id = None
                self.air_wing_target_menu_wing_id = None
                self.air_wing_risk_menu_wing_id = None
                self.air_wing_creation_open = False
            elif action == "strike_manual":
                self.air_wing_target_menu_wing_id = None if self.air_wing_target_menu_wing_id == wing.id else wing.id
                self.air_wing_mission_menu_wing_id = None
                self.air_wing_edit_menu_wing_id = None
                self.air_wing_risk_menu_wing_id = None
                self.air_wing_creation_open = False
            return True
        if self.air_wing_command_add_rect and self.point_in_rect(x, y, self.air_wing_command_add_rect):
            self.air_wing_creation_open = not self.air_wing_creation_open
            self.air_wing_mission_menu_wing_id = None
            self.air_wing_target_menu_wing_id = None
            self.air_wing_edit_menu_wing_id = None
            self.air_wing_risk_menu_wing_id = None
            stock_rows = self.air_wing_creation_stock_rows()
            if stock_rows and self.air_wing_creation_type not in {aircraft_type for aircraft_type, _reserve in stock_rows}:
                self.air_wing_creation_type = stock_rows[0][0]
            return True
        for rect, wing_id in self.air_wing_list_row_rects:
            if self.point_in_rect(x, y, rect):
                wing = self.air_wing_by_id(wing_id)
                if wing:
                    shift = self.shift_modifier_active(modifiers)
                    selected_ids = set(getattr(self, "selected_air_wing_ids", set()) or set())
                    if not selected_ids and self.selected_air_wing_id:
                        selected_ids.add(self.selected_air_wing_id)
                    if not shift and selected_ids == {wing.id}:
                        self.clear_air_wing_selection()
                        return True
                    self.select_air_wing(wing, additive=shift, toggle=shift)
                    if wing.base_tile and not shift:
                        self.set_single_selected_tile(wing.base_tile)
                return True
        return True

    def handle_air_wing_list_right_click(self, x, y):
        if not self.air_wing_list_panel_rect or not self.point_in_rect(x, y, self.air_wing_list_panel_rect):
            return False
        for rect, wing_id in self.air_wing_list_row_rects:
            if self.point_in_rect(x, y, rect):
                selected_ids = set(getattr(self, "selected_air_wing_ids", set()) or set())
                if not selected_ids and self.selected_air_wing_id:
                    selected_ids.add(self.selected_air_wing_id)
                if selected_ids == {wing_id}:
                    self.clear_air_wing_selection()
                return True
        return False

    def air_wing_hover_control_at(self, x, y):
        for rect, action, _wing_id, tooltip in self.air_wing_command_button_rects:
            if self.point_in_rect(x, y, rect):
                title = {
                    "mission": "Миссии",
                    "targets": "Список целей",
                    "target": "Район работы",
                    "rebase": "Базирование",
                    "risk": "Режим риска",
                    "edit": "Редактирование",
                    "strike_manual": "Создать миссию Удар",
                }.get(action, "Авиакрыло")
                return {"rect": rect, "title": title, "body": tooltip}
        mission_labels = {key: label for key, label, _description in self.air_wing_available_auto_missions()}
        for rect, _wing_id, mission_key, description, available in self.air_wing_mission_option_rects:
            if self.point_in_rect(x, y, rect):
                suffix = "" if available else " Эта миссия недоступна для выбранного типа самолетов."
                return {
                    "rect": rect,
                    "title": mission_labels.get(mission_key, mission_key),
                    "body": description + suffix,
                }
        target_labels = {key: label for key, label, _description in self.air_wing_target_priority_items()}
        target_labels["__all__"] = "Выбрать все"
        for rect, _wing_id, target_key, description in self.air_wing_target_option_rects:
            if self.point_in_rect(x, y, rect):
                return {"rect": rect, "title": target_labels.get(target_key, target_key), "body": description}
        risk_labels = {key: label for key, label, _description in self.air_wing_risk_items()}
        for rect, _wing_id, risk_key, description in self.air_wing_risk_option_rects:
            if self.point_in_rect(x, y, rect):
                return {"rect": rect, "title": risk_labels.get(risk_key, risk_key), "body": description}
        for rect, _wing_id, aircraft_type, _delta, description in self.air_wing_edit_button_rects:
            if self.point_in_rect(x, y, rect):
                aircraft_name = AIRCRAFT_TYPES.get(aircraft_type, {}).get("name", aircraft_type)
                return {"rect": rect, "title": aircraft_name, "body": description}
        if self.air_wing_command_add_rect and self.point_in_rect(x, y, self.air_wing_command_add_rect):
            return {
                "rect": self.air_wing_command_add_rect,
                "title": "Создать авиакрыло",
                "body": "Открывает список самолетов в резерве, выбор типа и количества для нового крыла.",
            }
        return None

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

    def draw_army_plan_buttons(self, army, card_rect, y_override=None):
        if not army or not card_rect:
            return
        card_x, card_y, card_w, card_h = card_rect
        definitions = self.army_plan_button_definitions()
        button_size = 24
        gap = 4
        total_width = len(definitions) * button_size + (len(definitions) - 1) * gap
        x = card_x + card_w / 2 - total_width / 2
        x = max(8, min(x, self.window.width - total_width - 8))
        y = y_override if y_override is not None else card_y + card_h + 7
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

        layout = self.army_command_layout(bar_width, len(armies), has_free_selection)
        label_w = layout["label_w"]
        card_w = layout["card_w"]
        card_h = layout["card_h"]
        gap = layout["gap"]
        columns = layout["columns"]
        label_rect = (bar_x + 5, bar_y + 5, label_w, bar_height - 10)
        arcade.draw_lbwh_rectangle_filled(*label_rect, (28, 38, 42, 238))
        arcade.draw_lbwh_rectangle_outline(*label_rect, (74, 92, 98), 1)
        self.draw_ui_text("ТВД", bar_x + 5 + label_w / 2, bar_y + bar_height - 22,
                          (214, 226, 232), 9, anchor_x="center")
        self.draw_ui_text("1", bar_x + 5 + label_w / 2, bar_y + bar_height / 2 - 8,
                          arcade.color.WHITE, 16, anchor_x="center", anchor_y="center")

        self.army_command_card_rects = []
        card_start_x = bar_x + label_w + 11
        grid_top = bar_y + bar_height - 5
        active_army = self.active_army_for_plan_controls()
        active_card_rect = None
        for index, army in enumerate(armies):
            row_index = index // columns
            column_index = index % columns
            card_x = card_start_x + column_index * (card_w + gap)
            card_y = grid_top - (row_index + 1) * card_h - row_index * gap
            army_divisions = self.divisions_for_army(army)
            active = any(division.id in self.selected_division_ids for division in army_divisions)
            self.draw_army_command_card(
                card_x,
                card_y,
                card_w,
                card_h,
                f"{len(army_divisions)}/{ARMY_DIVISION_CAPACITY}",
                variant=index,
                active=active,
            )
            card_rect = (card_x, card_y, card_w, card_h)
            self.army_command_card_rects.append((card_rect, army))
            if active_army and army.id == active_army.id:
                active_card_rect = card_rect

        if has_free_selection:
            add_index = len(armies)
            add_row = add_index // columns
            add_column = add_index % columns
            add_x = card_start_x + add_column * (card_w + gap)
            add_y = grid_top - (add_row + 1) * card_h - add_row * gap
            self.draw_army_command_card(
                add_x,
                add_y,
                card_w,
                card_h,
                "",
                active=has_free_selection,
                is_add=True,
            )
            self.army_command_add_rect = (add_x, add_y, card_w, card_h)
        else:
            self.army_command_add_rect = None

        if active_army and active_card_rect:
            self.draw_army_plan_buttons(active_army, active_card_rect, y_override=bar_y + bar_height + 7)

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

    def map_layer_filter_option_at(self, x, y):
        if self.map_layer_menu_progress < 0.8:
            return None

        for index, rect in enumerate(self.map_layer_filter_option_rects()):
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

        filter_index = self.map_layer_filter_option_at(x, y)
        if filter_index is not None:
            filter_key, _label, _active = self.map_layer_filter_items()[filter_index]
            if filter_key == "air_defense":
                self.air_defense_overlay_enabled = not self.air_defense_overlay_enabled
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

            for index, (_filter_key, label, active) in enumerate(self.map_layer_filter_items()):
                x, y, width, height = self.map_layer_filter_option_rects()[index]
                hovered = index == self.hovered_map_layer_filter_option
                if active:
                    fill = (48, 86, 58, alpha)
                    border = (150, 218, 132, alpha)
                    text_color = (238, 248, 238, alpha)
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
                self.draw_ui_text("Фильтр", x + 12, y + height / 2, (150, 166, 184, alpha), 9, anchor_y="center")
                self.draw_ui_text(label, x + 72, y + height / 2, text_color, 13, anchor_y="center")
                self.draw_ui_text("вкл" if active else "выкл", x + width - 12, y + height / 2,
                                  text_color, 10, anchor_x="right", anchor_y="center")

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
        profiler = self.profiler
        profiler.begin_phase("update")
        try:
            with profiler.measure("total"):
                with profiler.measure("ui_animation"):
                    self.shader_time += delta_time
                    self.update_map_layer_menu_animation(delta_time)
                    self.update_side_panel_animation(delta_time)
                    if self.hex_panel_message_timer > 0:
                        self.hex_panel_message_timer = max(0.0, self.hex_panel_message_timer - delta_time)
                        if self.hex_panel_message_timer == 0:
                            self.hex_panel_message = ""

                if self.paused or self.game_over:
                    return

                with profiler.measure("visual_motion"):
                    self.update_division_visual_motion(delta_time)
                    self.update_air_impact_decals(delta_time)
                with profiler.measure("fps_counter"):
                    self.fps_frame_count += 1
                    self.fps_timer += delta_time
                    if self.fps_timer >= 0.5:
                        self.fps = self.fps_frame_count / self.fps_timer
                        self.fps_frame_count = 0
                        self.fps_timer = 0

                previous_tick_count = self.simulation_client.snapshot.tick_count
                previous_time = self.simulation_server.current_time
                with profiler.measure("server_clock"):
                    self.simulation_server.update(delta_time)
                    self.simulation_client.sync_from_server()
                snapshot = self.simulation_client.snapshot
                tick_delta = max(0, snapshot.tick_count - previous_tick_count)
                if tick_delta > 0:
                    elapsed_hours = (snapshot.current_time - previous_time).total_seconds() / 3600
                    with profiler.measure("server_politics"):
                        self.advance_politics(elapsed_hours)
                    with profiler.measure("server_market"):
                        market_ticks = self.simulation_server.consume_market_ticks()
                        for _market_index in range(market_ticks):
                            self.run_weekly_market_tick()
                    with profiler.measure("server_economy"):
                        for player in self.players:
                            self.run_economy_tick(player, elapsed_hours)
                    with profiler.measure("server_production"):
                        for player in self.players:
                            self.run_production_tick(player, elapsed_hours)
                    with profiler.measure("server_construction"):
                        for player in self.players:
                            self.run_construction_tick(player, elapsed_hours)
                    with profiler.measure("server_population"):
                        for player in self.players:
                            self.run_population_tick(player, elapsed_hours)
                    with profiler.measure("server_divisions"):
                        self.update_divisions(elapsed_hours)
                    with profiler.measure("server_ground_battles"):
                        self.update_battles(elapsed_hours)
                    with profiler.measure("server_field_helipads"):
                        self.update_field_helipad_projects(elapsed_hours)
                    with profiler.measure("server_air_defense"):
                        self.update_air_defense_units(elapsed_hours)
                    with profiler.measure("server_air_attack_salvos"):
                        self.update_air_attack_salvos(elapsed_hours)
                    with profiler.measure("server_air_missions"):
                        self.update_air_missions(elapsed_hours)
                    with profiler.measure("server_air_salvos"):
                        self.update_air_salvos(elapsed_hours)
                    with profiler.measure("server_army_plans"):
                        self.update_army_plans(elapsed_hours)
                    with profiler.measure("server_economy_history"):
                        self.update_economy_month_history(snapshot.current_time)
                        self.last_production_tick_count = snapshot.tick_count

                with profiler.measure("ownership_refresh"):
                    self.process_ownership_refresh()
                with profiler.measure("camera"):
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
                    with profiler.measure("visible_tiles_refresh"):
                        if self.use_overview_lod():
                            self.visible_tiles.clear()
                            self.refresh_visible_tiles_signature()
                        else:
                            self.get_visible_tiles()
                            self.refresh_visible_tiles_signature()
                            self.update_draw_list()
                        self.last_visible_update = current_time
        finally:
            profiler.end_phase("update")

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

        if self.handle_country_click(x, y, button):
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

            if self.handle_air_wing_list_click(x, y, modifiers):
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
                if self.can_edit_selected_industry() and self.point_in_rect(x, y, self.hex_panel_specialization_button_rect()):
                    self.toggle_hex_specialization_mode()
                    return
                if self.hex_panel_specialization_mode:
                    for rect, sector in self.hex_specialization_row_rects:
                        if self.point_in_rect(x, y, rect):
                            self.set_selected_tile_industry_sector(sector)
                            return
                if self.handle_hex_air_controls_click(x, y):
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

            target_tile = self.get_tile_at(world_x, world_y)
            if self.handle_air_map_command_click(target_tile, modifiers):
                return

            if self.construction_placement_mode and self.active_top_panel_key == "construction":
                tile = target_tile
                building_key = self.selected_construction_building_key()
                if tile and self.can_place_construction(self.human_player, tile, building_key):
                    steps = 1
                    if self.shift_modifier_active(modifiers):
                        steps = max(1, round(0.25 / CONSTRUCTION_STEP))
                    self.submit_player_command("enqueue_construction", {
                        "tile_key": self.tile_key(tile),
                        "building_key": building_key,
                        "steps": steps,
                    })
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
                if self.handle_air_wing_list_right_click(x, y):
                    return
                if (
                    (self.air_wing_list_panel_rect and self.point_in_rect(x, y, self.air_wing_list_panel_rect))
                    or (self.air_wing_creation_panel_rect and self.point_in_rect(x, y, self.air_wing_creation_panel_rect))
                    or any(self.point_in_rect(x, y, rect) for rect in self.air_wing_dropdown_panel_rects)
                    or any(self.point_in_rect(x, y, rect) for rect, *_rest in self.air_wing_mission_option_rects)
                    or any(self.point_in_rect(x, y, rect) for rect, *_rest in self.air_wing_target_option_rects)
                    or any(self.point_in_rect(x, y, rect) for rect, *_rest in self.air_wing_edit_button_rects)
                ):
                    return
                if self.shift_modifier_active(modifiers) and (
                    self.air_wing_target_mode_id
                    or self.air_wing_target_mode_ids
                ):
                    target_tile = self.get_tile_at(world_x, world_y)
                    if self.handle_air_map_command_click(target_tile, modifiers, force_mode="remove"):
                        return
                if (
                    self.air_wing_target_mode_id
                    or self.air_wing_rebase_mode_id
                    or self.air_wing_target_mode_ids
                    or self.air_wing_rebase_mode_ids
                    or self.air_defense_move_mode_id
                ):
                    self.clear_air_wing_map_modes()
                    self.air_defense_move_mode_id = None
                    return

                selected_air_defense = self.air_defense_unit_by_id(self.selected_air_defense_unit_id)
                if selected_air_defense and selected_air_defense.owner is self.human_player:
                    if y >= self.window.height - TOP_UI_HEIGHT:
                        return
                    if self.side_panel_progress > 0 and self.point_in_rect(x, y, self.side_panel_rect()):
                        return
                    if self.selected_tile and self.point_in_rect(x, y, self.hex_panel_rect()):
                        return
                    target_tile = self.get_tile_at(world_x, world_y)
                    if target_tile:
                        self.move_air_defense_unit(selected_air_defense, target_tile)
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
                    self.submit_player_command("cancel_construction", {
                        "tile_key": self.tile_key(tile),
                        "building_key": building_key,
                    })
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
        if self.country_dialog and not self.paused:
            self.country_slider_drag = False
            return
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
        if self.country_dialog and not self.paused:
            if self.country_slider_drag:
                self.set_country_export_slider(x)
            return
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
        if self.country_dialog and not self.paused:
            self.hovered_tile = None
            return
        if self.country_panel_contains(x, y) and not self.paused:
            self.hovered_tile = None
            return
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
            self.hovered_air_wing_control = None
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
        self.hovered_air_wing_control = self.air_wing_hover_control_at(x, y)
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
            and self.can_edit_selected_industry()
            and self.point_in_rect(x, y, self.hex_panel_specialization_button_rect())
        )
        over_division_list = (
            self.division_list_panel_rect is not None
            and self.point_in_rect(x, y, self.division_list_panel_rect)
        )
        over_air_wing_list = (
            self.air_wing_list_panel_rect is not None
            and self.point_in_rect(x, y, self.air_wing_list_panel_rect)
        )
        over_air_wing_creation = (
            self.air_wing_creation_panel_rect is not None
            and self.point_in_rect(x, y, self.air_wing_creation_panel_rect)
        )
        over_air_wing_dropdown = any(self.point_in_rect(x, y, rect) for rect in self.air_wing_dropdown_panel_rects)
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
            or over_air_wing_list
            or over_air_wing_creation
            or over_air_wing_dropdown
            or self.hovered_air_wing_control
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
            self.hovered_map_layer_filter_option = None
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
                self.hovered_map_layer_filter_option = None
                self.hovered_time_button = None
                self.hovered_tile = None
                return

        self.hovered_map_layer_button = self.point_in_rect(x, y, self.map_layer_button_rect())
        self.hovered_map_layer_option = self.map_layer_option_at(x, y)
        self.hovered_map_layer_filter_option = self.map_layer_filter_option_at(x, y)
        if (
            self.hovered_map_layer_button
            or self.hovered_map_layer_option is not None
            or self.hovered_map_layer_filter_option is not None
        ):
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
        if self.country_dialog and not self.paused:
            self.country_dialog_scroll = max(0, self.country_dialog_scroll - int(scroll_y * 44))
            return
        if self.country_panel_contains(x, y) and not self.paused:
            self.country_card_scroll = max(0, self.country_card_scroll - int(scroll_y * 3))
            self.country_card_hits = []
            return
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
        if self.country_dialog and not self.paused:
            if key == arcade.key.ESCAPE:
                self.close_country_dialog()
                return
            if self.country_card_action in ("aid", "loan"):
                self.country_amount_key(key, modifiers)
            if key not in (arcade.key.F3, arcade.key.SPACE):
                return
        if self.active_top_panel_key in ("politics", "diplomacy") and not self.paused:
            if key == arcade.key.ESCAPE:
                self.close_country_card()
                return
            if self.country_amount_focus and key not in (arcade.key.SPACE, arcade.key.F3):
                self.country_amount_key(key, modifiers)
                return
        if key == arcade.key.F3:
            self.profiler.set_visible(not self.profiler.visible)
            self.performance_overlay_last_update = 0.0
            return

        if key == arcade.key.ESCAPE:
            if self.army_plan_mode:
                self.cancel_army_plan_mode()
                return

            if (
                self.air_wing_target_mode_id
                or self.air_wing_target_mode_ids
                or self.air_wing_rebase_mode_id
                or self.air_wing_rebase_mode_ids
            ):
                self.clear_air_wing_map_modes()
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
