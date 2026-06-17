import arcade
import random
import math
import time
from perlin_noise import PerlinNoise
from PIL import Image, ImageDraw
from pyglet.graphics import Batch
import matplotlib.pyplot as plt
from Constants import *
from HexTile import HexTile

arcade.enable_timings()



def create_hex_texture():
    """Создает белую текстуру гексагона с помощью PIL"""
    image = Image.new('RGBA', (HEX_WIDTH, int(HEX_HEIGHT * 1.2)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    center_x = HEX_HEIGHT // 2
    center_y = HEX_WIDTH // 2
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


def create_hex_border_texture():
    image = Image.new('RGBA', (HEX_WIDTH, int(HEX_HEIGHT * 1.2)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    center_x = HEX_HEIGHT // 2
    center_y = HEX_WIDTH // 2
    points = []
    for i in range(6):
        angle_deg = 60 * i + 30
        angle_rad = math.pi / 180 * angle_deg
        x = center_x + HEX_SIZE * math.cos(angle_rad)
        y = center_y + HEX_SIZE * math.sin(angle_rad)
        points.append((x, y))
    # Рисуем черный контур
    draw.polygon(points, outline=(255, 255, 0), width=4)
    # Конвертируем в текстуру Arcade
    texture = arcade.Texture(
        name=f"hex_texture_border",
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

    def is_lake(self, x, y):
        """Определяет, является ли тайл озером"""
        elevation = self.generate_elevation(x, y)
        # Озера только на суше
        if elevation < WATER_LEVEL:
            return False
        # Озера только в не-холодных зонах
        temp = self.generate_temperature(x, y, elevation)
        if temp < 0.2:
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
    def __init__(self):
        super().__init__()
        arcade.set_background_color(arcade.color.BLACK)
        self.paused = False
        self.game_over = False
        self.keys_pressed = set()
        self.hex_grid = []
        self.hex_draw_list = arcade.shape_list.ShapeElementList()
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
        self.last_visible_update = 0
        self.last_mouse_check = 0
        self.visible_update_interval = 0.1
        self.world_generator = None
        self.world_seed = random.randint(0, 999999)
        self.selection_border = None
        self.selection_border_sprite_list = arcade.SpriteList()
        self.batch = Batch()

        self.setup()

    def setup(self):
        self.grid_width = WORLD_SIZE
        self.grid_height = WORLD_SIZE
        self.world_generator = WorldGenerator(self.grid_width, self.grid_height, self.world_seed)
        self.create_hex_grid()
        self.selection_border = arcade.Sprite(create_hex_border_texture())
        self.selection_border_sprite_list.append(self.selection_border)
        self.selection_border.visible = False
        center_x = (self.grid_width * HEX_WID) / 2
        center_y = (self.grid_height * HEX_HGT * 0.75) / 2
        self.world_camera.position = (center_x, center_y)
        self.target_camera_x, self.target_camera_y = self.world_camera.position

    def create_hex_grid(self):
        x_offset = 100
        y_offset = 100
        hex_texture = create_hex_texture()
        # landscale = [[0 for i in range(self.grid_width)] for i in range(self.grid_height)]
        for q in range(self.grid_width):
            for r in range(self.grid_height):
                x = x_offset + q * HEX_WID + (r % 2) * HEX_WID / 2
                y = y_offset + r * HEX_HGT * 0.75
                elevation = self.world_generator.generate_elevation(q, r)
                ridge = self.world_generator.generate_ridges(q, r)
                moisture = self.world_generator.generate_moisture(q, r, elevation)
                temperature = self.world_generator.generate_temperature(q, r, elevation)
                hex_tile = HexTile(q, r, x, y, elevation, moisture, temperature, ridge, hex_texture)
                # landscale[q][r] = moisture
                if hex_tile.elevation > WATER_LEVEL:
                    is_lake = self.world_generator.is_lake(q, r)
                    if is_lake:
                        hex_tile.terrain_type = 'lake'
                        hex_tile.elevation = WATER_LEVEL - 0.02
                self.hex_grid.append(hex_tile)
        # plt.imshow(landscale)
        # plt.show()
        print(f"Создано {len(self.hex_grid)} тайлов")

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
        self.clear()
        start_time = time.time()
        self.world_camera.use()
        self.visible_tiles.draw()
        if self.selection_border.visible:
            self.selection_border_sprite_list.draw()
        self.gui_camera.use()
        self.draw_gui()
        draw_time = (time.time() - start_time) * 1000
        fps = arcade.get_fps(frame_count=60)
        debug_text = f"FPS: {fps:.0f} | Draw: {draw_time:.1f}ms | Tiles: {len(self.visible_tiles)} | Seed: {self.world_seed}"
        arcade.draw_text(debug_text, 10, 30, arcade.color.YELLOW, 12)

    def draw_gui(self):
        if self.selected_tile:
            y_pos = self.window.height - 30
            arcade.draw_text(f"Тип: {self.selected_tile.terrain_type}", 10, y_pos, arcade.color.WHITE, 14)
            arcade.draw_text(f"Высота: {self.selected_tile.elevation:.2f}", 10, y_pos - 20, arcade.color.WHITE, 14)
            arcade.draw_text(f"Температура: {self.selected_tile.temperature:.2f}", 10, y_pos - 40, arcade.color.WHITE,
                             14)
            arcade.draw_text(f"Влажность: {self.selected_tile.moisture:.2f}", 10, y_pos - 60, arcade.color.WHITE,
                             14)
            # Показываем компоненты
            arcade.draw_text(f"Вода: {self.selected_tile.water_cover:.0%}", 10, y_pos - 80, arcade.color.BLUE, 12)
            arcade.draw_text(f"Деревья: {self.selected_tile.tree_cover:.0%}", 10, y_pos - 95, arcade.color.GREEN, 12)
            arcade.draw_text(f"Трава: {self.selected_tile.grass_cover:.0%}", 10, y_pos - 110, arcade.color.LIGHT_GREEN,
                             12)
            arcade.draw_text(f"Камни: {self.selected_tile.rock_cover:.0%}", 10, y_pos - 125, arcade.color.DARK_GRAY, 12)
            arcade.draw_text(f"Песок: {self.selected_tile.sand_cover:.0%}", 10, y_pos - 140, arcade.color.YELLOW, 12)
            arcade.draw_text(f"Снег: {self.selected_tile.snow_cover:.0%}", 10, y_pos - 155, arcade.color.WHITE, 12)
            if self.selected_tile.resources:
                res_text = f"Ресурсы: {', '.join([f"{i[0]}, глубина: {i[1]}, масса {i[2]}" for i in self.selected_tile.resources])}"
                arcade.draw_text(res_text, 10, y_pos - 175, arcade.color.YELLOW, 14)

    def update_draw_list(self):
        """Обновление списка отрисовки"""
        for tile in self.visible_tiles:
            if tile == self.selected_tile:
                # Желтая подсветка
                tile.color = tile.get_color()
            elif tile == self.hovered_tile:
                # Белая подсветка (чуть светлее)
                base_color = tile.get_color()
                tile.color = (
                    min(255, base_color[0] + 50),
                    min(255, base_color[1] + 50),
                    min(255, base_color[2] + 50)
                )
            else:
                tile.color = tile.get_color()

    def on_update(self, delta_time):
        if self.paused or self.game_over:
            return

        self.world_camera.position = arcade.math.lerp_2d(
            self.world_camera.position,
            (self.target_camera_x, self.target_camera_y),
            CAMERA_LERP,
        )

        self.handle_camera_keys(delta_time)

        current_time = time.time()
        if current_time - self.last_visible_update > self.visible_update_interval:
            self.get_visible_tiles()
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
        if button == arcade.MOUSE_BUTTON_RIGHT:
            self.is_dragging = False

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if arcade.MOUSE_BUTTON_RIGHT & buttons and self.is_dragging:
            self.target_camera_x = self.drag_start_camera_x - (x - self.drag_start_x) / self.world_camera.zoom
            self.target_camera_y = self.drag_start_camera_y - (y - self.drag_start_y) / self.world_camera.zoom

    def on_mouse_motion(self, x, y, dx, dy):
        current_time = time.time()
        if current_time - self.last_mouse_check > self.visible_update_interval * 0.25:
            world_x, world_y = self.screen_to_world(x, y)
            self.hovered_tile = self.get_tile_at(world_x, world_y)
            self.last_mouse_check = current_time

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        new_zoom = self.world_camera.zoom + scroll_y * ZOOM_SPEED
        self.world_camera.zoom = max(MIN_ZOOM, min(MAX_ZOOM, new_zoom))

    def screen_to_world(self, screen_x, screen_y):
        camera_x, camera_y = self.world_camera.position
        zoom = self.world_camera.zoom
        world_x = camera_x + (screen_x - self.window.width / 2) / zoom
        world_y = camera_y + (screen_y - self.window.height / 2) / zoom
        return world_x, world_y

    def get_tile_at(self, x, y):
        sprites = arcade.get_sprites_at_point((x, y), self.visible_tiles)
        for sprite in sprites:
            if isinstance(sprite, HexTile):
                return sprite
        return None

    def on_key_press(self, key, modifiers):
        self.keys_pressed.add(key)

        if key == arcade.key.EQUAL or key == arcade.key.PLUS:
            self.world_camera.zoom = min(MAX_ZOOM, self.world_camera.zoom + ZOOM_SPEED)
        elif key == arcade.key.MINUS:
            self.world_camera.zoom = max(MIN_ZOOM, self.world_camera.zoom - ZOOM_SPEED)

    def on_key_release(self, key, modifiers):
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)


def main():
    window = arcade.Window(1400, 900, "HOI 5")
    start_view = Game()
    window.show_view(start_view)
    arcade.run()


if __name__ == "__main__":
    main()
