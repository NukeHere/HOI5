import arcade
import random
from Constants import *


class HexTile(arcade.Sprite):
    def __init__(
        self,
        q=None,
        r=None,
        x=None,
        y=None,
        elevation=None,
        moisture=None,
        temperature=None,
        ridge_value=0,
        hex_texture=None,
        tile_data=None,
        resource_rng=None,
    ):
        super().__init__(path_or_texture=hex_texture)
        self.map_data = tile_data
        if tile_data is not None:
            q = tile_data.q
            r = tile_data.r
            x = tile_data.x
            y = tile_data.y
            elevation = tile_data.elevation
            moisture = tile_data.moisture
            temperature = tile_data.temperature
            ridge_value = tile_data.ridge_value
        self.q = q
        self.r = r
        self.s = -q - r
        self.center_x = x
        self.center_y = y
        self.elevation = elevation
        self.moisture = moisture
        self.temperature = temperature
        self.ridge_value = ridge_value
        # Компоненты тайла (в процентах 0-1)
        self.water_cover = 0.0  # % покрытия водой
        self.tree_cover = 0.0  # % покрытия деревьями
        self.grass_cover = 0.0  # % покрытия травой
        self.rock_cover = 0.0  # % покрытия камнями/горами
        self.sand_cover = 0.0  # % покрытия песком
        self.snow_cover = 0.0  # % покрытия снегом
        # Инициализируем компоненты на основе параметров
        if tile_data is None:
            self._init_components()
        # Определяем текущий биом на основе компонентов
        if tile_data is None:
            self.terrain_type = self.determine_biome()
        if tile_data is not None:
            self.water_cover = tile_data.water_cover
            self.tree_cover = tile_data.tree_cover
            self.grass_cover = tile_data.grass_cover
            self.rock_cover = tile_data.rock_cover
            self.sand_cover = tile_data.sand_cover
            self.snow_cover = tile_data.snow_cover
            self.terrain_type = tile_data.terrain_type
            self.resources = [list(resource) for resource in tile_data.resources]
        else:
            self.resources = self.generate_resources(resource_rng)
        if tile_data is not None:
            self.movement_cost = tile_data.movement_cost
            self.passability = tile_data.passability
        else:
            self.movement_cost = self.calculate_movement_cost()
            self.passability = 0.0 if self.movement_cost == float("inf") else 1.0 / self.movement_cost
        self.owner = None
        self.buildings = []  # Список построек
        # Предрассчитанные углы для отрисовки
        self.corners = self._calculate_corners()
        self.bounding_box = self._calculate_bounding_box()
        self.color = arcade.color.WHITE
        self.hex_texture = hex_texture

    def calculate_movement_cost(self):
        if self.terrain_type in ['deep_ocean', 'ocean']:
            return float("inf")
        if self.terrain_type in ['shallow_water', 'lake', 'river', 'swamp', 'bog', 'mangrove']:
            return 3.0

        cost = 1.0
        cost += self.ridge_value * 1.5
        cost += self.rock_cover * 1.2
        cost += self.snow_cover * 0.5
        if self.terrain_type == 'mountains':
            cost += 1.5
        elif self.terrain_type == 'snowy_mountains':
            cost += 2.0
        elif self.terrain_type == 'hills':
            cost += 0.75
        return max(1.0, cost)

    def _init_components(self):
        """Инициализирует компоненты на основе природных параметров"""
        # Сбрасываем все в 0
        self.water_cover = 0.0
        self.tree_cover = 0.0
        self.grass_cover = 0.0
        self.rock_cover = 0.0
        self.sand_cover = 0.0
        self.snow_cover = 0.0

        # Вода
        if self.elevation < WATER_LEVEL:
            self.water_cover = 0.8 * (WATER_LEVEL - self.elevation) / WATER_LEVEL + 0.2
            return

        # Базовое распределение для суши
        if self.elevation > 0.7:  # Горы
            self.rock_cover = 0.4 + (self.elevation - 0.7) * 2
            self.rock_cover = min(0.9, self.rock_cover)
            self.tree_cover = 0.1 + max(0.0, (self.moisture - 0.3)) * 2
            self.tree_cover = min(0.4, self.tree_cover)

            if self.temperature < 0.3:
                self.snow_cover = 0.3 + (0.3 - self.temperature) * 2
                self.snow_cover = min(0.8, self.snow_cover)

            self.grass_cover = max(0.0, 1.0 - self.rock_cover - self.snow_cover)

        elif self.elevation > 0.5:  # Холмы
            self.rock_cover = 0.2 + (self.elevation - 0.5) * 1
            self.rock_cover = min(0.6, self.rock_cover)

            if self.moisture > 0.15:
                self.tree_cover = 0.4 + (self.moisture - 0.35) * 2
                self.tree_cover = min(0.7, self.tree_cover)

            remaining = 1.0 - self.rock_cover - self.tree_cover
            self.grass_cover = max(0.0, remaining)

        else:  # Равнины
            if self.moisture > 0.5:  # Умеренно - луг
                self.grass_cover = 0.8
                self.tree_cover = 0.2
            elif self.moisture > 0.2:  # Влажно - лес
                self.tree_cover = 0.5 + (self.moisture - 0.4) * 2
                self.tree_cover = min(0.8, self.tree_cover)
                self.grass_cover = max(0.0, 1.0 - self.tree_cover)


            else:  # Сухо - пустыня/саванна
                if self.temperature > 0.6:
                    self.sand_cover = 0.6
                    self.grass_cover = 0.4
                else:
                    self.grass_cover = 0.5
                    self.sand_cover = 0.3
                    self.tree_cover = 0.2

        # Корректируем по температуре
        if self.temperature < 0.2 and self.elevation < 0.5:
            self.snow_cover = min(0.7, self.snow_cover + 0.3)
            # Уменьшаем другие компоненты пропорционально
            factor = 1.0 - self.snow_cover
            self.grass_cover *= factor
            self.tree_cover *= factor
            self.sand_cover *= factor

        # Финальная нормализация
        self._normalize_covers()

    def determine_biome(self):
        """Определяет биом на основе компонентов"""
        # Проверяем воду
        if self.water_cover > 0.5:
            if self.water_cover > 0.9:
                if self.elevation < DEEP_OCEAN_LEVEL:
                    return 'deep_ocean'
                return 'ocean'
            elif self.water_cover > 0.5:
                return 'shallow_water'
            else:
                return 'lake'

        # Проверяем болота (вода + растительность)
        if self.water_cover > 0.2 and self.tree_cover > 0.3:
            if self.temperature > 0.6:
                return 'mangrove'
            elif self.temperature > 0.3:
                return 'swamp'
            else:
                return 'bog'

        # Преобладающий компонент определяет биом
        if self.ridge_value > 0.75 and self.temperature < 0.35:
            return 'snowy_mountains'
        if self.ridge_value > 0.7:
            return 'mountains'
        if self.ridge_value > 0.4:
            return 'hills'

        components = [
            (self.rock_cover, 'rocky'),
            (self.sand_cover, 'sandy'),
            (self.snow_cover, 'snowy'),
            (self.tree_cover, 'forested'),
            (self.grass_cover, 'grassy')
        ]

        primary = max(components, key=lambda x: x[0])
        primary_type = primary[1]
        primary_value = primary[0]

        # Определяем биом по преобладающему компоненту
        if primary_type == 'rocky':
            if self.temperature < 0.3:
                return 'snowy_mountains'
            elif primary_value > 0.7:
                return 'mountains'
            else:
                return 'hills'

        elif primary_type == 'sandy':
            if self.temperature > 0.6:
                return 'desert'
            else:
                return 'plains'

        elif primary_type == 'snowy':
            return 'tundra'

        elif primary_type == 'forested':
            if self.temperature > 0.7:
                return 'tropical_rainforest'
            elif self.temperature > 0.5:
                return 'jungle'
            elif self.temperature > 0.3:
                return 'temperate_forest'
            else:
                return 'taiga'

        else:  # grassy
            if self.temperature > 0.7:
                return 'savanna'
            elif self.temperature > 0.4:
                return 'grassland'
            else:
                return 'tundra'

    def modify_terrain(self, changes):
        for key, value in changes.items():
            if hasattr(self, key):
                current = getattr(self, key)
                new_value = current + value
                # Жестко ограничиваем от 0 до 1
                setattr(self, key, max(0, min(1, new_value)))
        total = self.water_cover + self.tree_cover + self.grass_cover + self.rock_cover + self.sand_cover + self.snow_cover
        if total > 1.0:
            factor = 1.0 / total
            self.water_cover *= factor
            self.tree_cover *= factor
            self.grass_cover *= factor
            self.rock_cover *= factor
            self.sand_cover *= factor
            self.snow_cover *= factor
        self.terrain_type = self.determine_biome()
        self.movement_cost = self.calculate_movement_cost()
        self.passability = 0.0 if self.movement_cost == float("inf") else 1.0 / self.movement_cost

    def _normalize_covers(self):
        """Нормализует сумму компонентов до 1 с защитой от отрицательных"""
        # Сначала убираем отрицательные значения
        self.water_cover = max(0.0, self.water_cover)
        self.tree_cover = max(0.0, self.tree_cover)
        self.grass_cover = max(0.0, self.grass_cover)
        self.rock_cover = max(0.0, self.rock_cover)
        self.sand_cover = max(0.0, self.sand_cover)
        self.snow_cover = max(0.0, self.snow_cover)
        # Считаем сумму
        total = self.water_cover + self.tree_cover + self.grass_cover + self.rock_cover + self.sand_cover + self.snow_cover
        # Если сумма слишком мала или велика, нормализуем
        if total > 0.001:  # Защита от деления на ноль
            # Ограничиваем каждый компонент
            self.water_cover = min(1.0, self.water_cover / total)
            self.tree_cover = min(1.0, self.tree_cover / total)
            self.grass_cover = min(1.0, self.grass_cover / total)
            self.rock_cover = min(1.0, self.rock_cover / total)
            self.sand_cover = min(1.0, self.sand_cover / total)
            self.snow_cover = min(1.0, self.snow_cover / total)
        else:
            # Если все нули, ставим траву по умолчанию
            self.grass_cover = 1.0

    def get_color(self):
        """Возвращает цвет на основе компонентов - старые цвета"""
        if self.terrain_type in ['deep_ocean', 'ocean', 'shallow_water', 'lake', 'river']:
            # Вода - градиент по глубине
            base_color = {
                'deep_ocean': (30, 70, 150),
                'ocean': (80, 140, 200),
                'shallow_water': (64, 164, 223),
                'lake': (100, 180, 230),
                'river': (100, 180, 230)
            }.get(self.terrain_type, (64, 164, 223))
            return base_color
        # Старые цвета из оригинального кода
        colors = {
            # Вода
            'deep_ocean': (20, 40, 100),
            'ocean': (30, 70, 150),
            'shallow_water': (64, 164, 223),
            'lake': (80, 140, 200),

            # Побережья
            'beach': (238, 214, 175),
            'marsh': (120, 140, 120),

            # Равнины
            'grassland': (100, 180, 100),
            'plains': (150, 200, 100),
            'savanna': (210, 180, 140),
            'tundra': (200, 220, 200),
            'desert': (238, 203, 173),

            # Леса
            'temperate_forest': (34, 139, 34),
            'boreal_forest': (50, 100, 50),
            'tropical_rainforest': (20, 150, 20),
            'jungle': (30, 120, 30),
            'swamp': (80, 110, 80),
            'taiga': (60, 90, 60),

            # Холмы
            'hills': (139, 119, 101),
            'wooded_hills': (100, 130, 70),
            'arid_hills': (180, 150, 120),

            # Горы
            'mountains': (120, 120, 120),
            'snowy_mountains': (220, 240, 255),
            'wooded_mountains': (90, 110, 90),
            'high_peak': (240, 248, 255),
            'glacier': (250, 250, 250),

            # Болота
            'mangrove': (60, 100, 70),
            'bog': (80, 90, 70),
            'tundra_swamp': (150, 160, 140),
            'taiga_swamp': (70, 100, 70),
            'tropical_swamp': (50, 120, 60),
        }
        # if self.terrain_type in colors:
        #     return colors[self.terrain_type]
        color = list(colors[self.terrain_type])
        for i in range(3):
            color[i] = color[i] * 0.5
        # Цвета компонентов (базовые)
        comp_colors = {
            'rock': (120, 120, 120),
            'sand': (238, 203, 173),
            'snow': (240, 248, 255),
            'tree': (34, 139, 34),
            'grass': (100, 180, 100)
        }
        total_weight = 0
        for comp, weight in [
            ('rock', self.rock_cover),
            ('sand', self.sand_cover),
            ('snow', self.snow_cover),
            ('tree', self.tree_cover),
            ('grass', self.grass_cover)
        ]:
            if weight > 0:
                for i in range(3):
                    color[i] += comp_colors[comp][i] * weight
                total_weight += weight
        if total_weight > 0:
            for i in range(3):
                color[i] = int(color[i] / (total_weight + 0.5))
        else:
            for i in range(3):
                color[i] = int(color[i])
        return tuple(color)

    def generate_resources(self, rng=None):
        rng = rng or globals()["random"]
        # Keep legacy random.* calls deterministic when an RNG is passed in.
        random = rng
        resources = []  # [ресурс, глубина, масса] пример ['coal', '0.2', '10000'] уголь, 200м под землей, 10000 тонн
        elevation_above_sea = self.elevation - WATER_LEVEL
        biome = self.terrain_type
        # СЕКТОР 1: ТОПЛИВНО-ЭНЕРГЕТИЧЕСКОЕ СЫРЬЕ
        # Уголь (Coal)
        if biome in ['hills', 'wooded_hills', 'mountains', 'wooded_mountains',
                     'temperate_forest', 'taiga', 'boreal_forest'] or (
                self.rock_cover > 0.3 and elevation_above_sea > 0.2):
            if random.random() < 0.3:  # 30% шанс в подходящих биомах
                depth = 1 / 1000 * random.uniform(100, 800)  # метры
                mass = random.uniform(5000, 50000)  # тонны
                resources.append(['coal', depth, mass])
        # Торф (Peat)
        if biome in ['swamp', 'bog', 'tundra_swamp', 'taiga_swamp', 'tropical_swamp', 'tundra'] or (
                0.3 < self.water_cover < 0.8 and self.moisture > 0.7):
            if random.random() < 0.4:
                depth = 1 / 1000 * random.uniform(0, 10)
                mass = random.uniform(1000, 20000)
                resources.append(['peat', depth, mass])
        # Нефть (Oil)
        if biome in ['desert', 'plains'] or self.sand_cover > 0.3:
            if random.random() < 0.2:
                depth = 1 / 1000 * random.uniform(500, 3000)
                mass = random.uniform(100000, 1000000)  # нефти много
                resources.append(['oil', depth, mass])
        elif self.water_cover > 0.8 and elevation_above_sea < 0:  # под водой
            if random.random() < 0.15:  # шельф
                depth = 1 / 1000 * random.uniform(500, 3000)
                mass = random.uniform(200000, 2000000)
                resources.append(['oil', depth, mass])
        # Природный газ (Natural gas) - часто рядом с нефтью
        if 'oil' in [r[0] for r in resources]:
            if random.random() < 0.6:  # 60% шанс газа там же где нефть
                depth = 1 / 1000 * random.uniform(500, 4000)
                mass = random.uniform(50000, 500000)
                resources.append(['natural_gas', depth, mass])
        # Уран (Uranium)
        if biome in ['mountains', 'snowy_mountains', 'high_peak', 'desert', 'arid_hills'] or (
                self.rock_cover > 0.4 and elevation_above_sea > 0.5):
            if random.random() < 0.1:  # редкий ресурс
                depth = 1 / 1000 * random.uniform(50, 500)
                mass = random.uniform(1000, 10000)
                resources.append(['uranium', depth, mass])

        # СЕКТОР 2: ЧЕРНЫЕ МЕТАЛЛЫ
        # Железная руда (Iron ore)
        if biome in ['mountains', 'wooded_mountains', 'hills', 'arid_hills', 'desert'] or (
                self.rock_cover > 0.4 and elevation_above_sea > 0.3):
            if random.random() < 0.35:
                depth = 1 / 1000 * random.uniform(0, 1000)
                mass = random.uniform(10000, 200000)
                resources.append(['iron_ore', depth, mass])
        # Легирующие добавки (Alloying additives)
        if biome in ['mountains', 'high_peak', 'desert'] or self.rock_cover > 0.5:
            if random.random() < 0.15:
                depth = 1 / 1000 * random.uniform(100, 800)
                mass = random.uniform(1000, 20000)
                resources.append(['alloying_additives', depth, mass])

        # СЕКТОР 3: ЦВЕТНЫЕ МЕТАЛЛЫ
        # Бокситы (Bauxite)
        if biome in ['tropical_rainforest', 'jungle', 'savanna', 'hills'] or (
                self.moisture > 0.6 and self.temperature > 0.4):  # 0.7 = ~24°C
            if random.random() < 0.25:
                depth = 1 / 1000 * random.uniform(0, 50)
                mass = random.uniform(5000, 100000)
                resources.append(['bauxite', depth, mass])
        # Медная руда (Copper ore)
        if biome in ['mountains', 'desert', 'hills', 'wooded_mountains'] or self.rock_cover > 0.4:
            if random.random() < 0.2:
                depth = 1 / 1000 * random.uniform(50, 1500)
                mass = random.uniform(5000, 100000)
                resources.append(['copper_ore', depth, mass])
        # Свинец (Lead)
        if biome in ['mountains', 'desert', 'hills'] or self.rock_cover > 0.3:
            if random.random() < 0.15:
                depth = 1 / 1000 * random.uniform(100, 600)
                mass = random.uniform(3000, 50000)
                resources.append(['lead', depth, mass])
        # Никель (Nickel)
        if biome in ['taiga', 'boreal_forest', 'mountains', 'snowy_mountains'] or self.rock_cover > 0.4:
            if random.random() < 0.15:
                depth = 1 / 1000 * random.uniform(200, 1000)
                mass = random.uniform(2000, 40000)
                resources.append(['nickel', depth, mass])
        # Цинк (Zinc)
        if biome in ['mountains', 'desert', 'hills'] or self.rock_cover > 0.3:
            if random.random() < 0.15:
                depth = 1 / 1000 * random.uniform(100, 600)
                mass = random.uniform(2000, 30000)
                resources.append(['zinc', depth, mass])

        # СЕКТОР 4: РЕДКИЕ И БЛАГОРОДНЫЕ МЕТАЛЛЫ
        # Золото (Gold)
        gold_chance = 0
        if biome in ['mountains', 'desert', 'taiga', 'boreal_forest'] or self.rock_cover > 0.3:
            gold_chance = 0.05  # жильное
        elif 'river' in biome or self.water_cover > 0.1:  # россыпи в реках
            gold_chance = 0.03

        if random.random() < gold_chance:
            if self.water_cover > 0.1:  # россыпь
                depth = 1 / 1000 * random.uniform(0, 100)
            else:  # жила
                depth = 1 / 1000 * random.uniform(100, 1000)
            mass = random.uniform(10, 1000)  # золота мало
            resources.append(['gold', depth, mass])

        # Серебро (Silver)
        if biome in ['mountains', 'desert', 'hills'] or self.rock_cover > 0.3:
            if random.random() < 0.06:
                depth = 1 / 1000 * random.uniform(100, 800)
                mass = random.uniform(50, 5000)
                resources.append(['silver', depth, mass])

        # Редкоземельные металлы (Rare earth metals)
        if biome in ['mountains', 'high_peak', 'desert', 'tundra'] or self.rock_cover > 0.5:
            if random.random() < 0.03:  # очень редкие
                depth = 1 / 1000 * random.uniform(50, 500)
                mass = random.uniform(100, 5000)
                resources.append(['rare_earth_metals', depth, mass])

        # СЕКТОР 5: ГОРНО-ХИМИЧЕСКОЕ СЫРЬЕ
        # Калийные соли (Potash)
        if biome in ['desert', 'plains'] or self.moisture < 0.3:
            if random.random() < 0.15:
                depth = 1 / 1000 * random.uniform(100, 1000)
                mass = random.uniform(10000, 200000)
                resources.append(['potash', depth, mass])

        # Поваренная соль (Salt)
        if biome in ['ocean', 'shallow_water']:
            # морская соль (испарение)
            if random.random() < 0.3:
                resources.append(['salt', 0, 1000000])  # бесконечно много в море
        elif biome in ['desert'] or self.moisture < 0.2:
            if random.random() < 0.2:  # солончаки
                depth = 1 / 1000 * random.uniform(0, 50)
                mass = random.uniform(50000, 500000)
                resources.append(['salt', depth, mass])

        # Фосфориты (Phosphorite)
        if biome in ['ocean', 'shallow_water'] or self.water_cover > 0.5:
            if random.random() < 0.1:
                depth = 1 / 1000 * random.uniform(0, 100)  # на дне
                mass = random.uniform(10000, 100000)
                resources.append(['phosphorite', depth, mass])

        # Апатиты (Apatite)
        if biome in ['mountains', 'high_peak'] or self.rock_cover > 0.4:
            if random.random() < 0.1:
                depth = 1 / 1000 * random.uniform(50, 300)
                mass = random.uniform(5000, 50000)
                resources.append(['apatite', depth, mass])

        # Сера (Sulfur)
        if biome in ['mountains', 'desert'] or self.temperature > 0.7:  # вулканические зоны
            if random.random() < 0.1:
                depth = 1 / 1000 * random.uniform(0, 1500)
                mass = random.uniform(1000, 50000)
                resources.append(['sulfur', depth, mass])

        # СЕКТОР 6: ИНДУСТРИАЛЬНО-СТРОИТЕЛЬНОЕ СЫРЬЕ
        # Песок (Sand)
        if biome in ['desert', 'beach'] or self.sand_cover > 0.5:
            depth = 1 / 1000 * random.uniform(0, 20)
            mass = random.uniform(10000, 100000)
            resources.append(['sand', depth, mass])
        elif biome in ['river', 'shallow_water', 'ocean'] or self.sand_cover > 0.3:
            if random.random() < 0.3:
                depth = 1 / 1000 * random.uniform(0, 20)
                mass = random.uniform(5000, 50000)
                resources.append(['sand', depth, mass])

        # Гравий (Gravel)
        if biome in ['river', 'hills', 'mountains'] or self.rock_cover > 0.2:
            if random.random() < 0.3:
                depth = 1 / 1000 * random.uniform(0, 10)
                mass = random.uniform(5000, 50000)
                resources.append(['gravel', depth, mass])

        # Щебень (Crushed stone)
        if biome in ['mountains', 'hills'] or self.rock_cover > 0.5:
            if random.random() < 0.4:
                depth = 1 / 1000 * random.uniform(0, 50)
                mass = random.uniform(10000, 100000)
                resources.append(['crushed_stone', depth, mass])

        # Известняк (Limestone)
        if biome in ['hills', 'mountains', 'shallow_water'] or self.rock_cover > 0.3:
            if random.random() < 0.25:
                depth = 1 / 1000 * random.uniform(0, 200)
                mass = random.uniform(10000, 200000)
                resources.append(['limestone', depth, mass])

        # Глина (Clay)
        if biome in ['river', 'lake', 'swamp', 'bog'] or self.moisture > 0.6:
            if random.random() < 0.3:
                depth = 1 / 1000 * random.uniform(0, 20)
                mass = random.uniform(5000, 50000)
                resources.append(['clay', depth, mass])

        # Графит (Graphite)
        if biome in ['mountains', 'high_peak'] or self.rock_cover > 0.4:
            if random.random() < 0.1:
                depth = 1 / 1000 * random.uniform(50, 500)
                mass = random.uniform(1000, 20000)
                resources.append(['graphite', depth, mass])

        # Слюда (Mica)
        if biome in ['mountains', 'high_peak'] or self.rock_cover > 0.5:
            if random.random() < 0.1:
                depth = 1 / 1000 * random.uniform(50, 300)
                mass = random.uniform(500, 10000)
                resources.append(['mica', depth, mass])

        # Кварц (Quartz)
        if biome in ['mountains', 'desert', 'hills'] or self.rock_cover > 0.3:
            if random.random() < 0.15:
                depth = 1 / 1000 * random.uniform(10, 200)
                mass = random.uniform(1000, 30000)
                resources.append(['quartz', depth, mass])

        # СЕКТОР 7: РАСТИТЕЛЬНОЕ СЫРЬЕ (на поверхности, не в недрах)
        # Древесина (Wood)
        if self.tree_cover > 0.4:
            # это возобновляемый ресурс на поверхности
            pass  # будет обрабатываться отдельно в системе растений

        # СЕКТОР 8: ЖИВОТНОЕ СЫРЬЕ (на поверхности)
        if self.grass_cover > 0.3:
            # будет в системе животных
            pass
        return resources

    def _calculate_corners(self):
        """Возвращает список угловых точек гексагона"""
        corners = []
        for i in range(6):
            angle_deg = 60 * i + 30
            angle_rad = math.pi / 180 * angle_deg
            corner_x = self.center_x + HEX_SIZE * math.cos(angle_rad)
            corner_y = self.center_y + HEX_SIZE * math.sin(angle_rad)
            corners.append((corner_x, corner_y))
        return corners

    def _calculate_bounding_box(self):
        """Вычисляет ограничивающий прямоугольник"""
        min_x = min(x for x, _ in self.corners)
        max_x = max(x for x, _ in self.corners)
        min_y = min(y for _, y in self.corners)
        max_y = max(y for _, y in self.corners)
        return (min_x, min_y, max_x, max_y)

    def contains_point(self, x, y):
        """Проверяет, находится ли точка внутри гексагона"""
        min_x, min_y, max_x, max_y = self.bounding_box
        if x < min_x or x > max_x or y < min_y or y > max_y:
            return False
        return self.point_in_polygon(x, y, self.corners)

    def irrigate(self):
        """Орошение - увеличивает влажность"""
        if self.water_cover < 0.3:
            self.modify_terrain({'water_cover': 0.1, 'grass_cover': 0.1, 'sand_cover': -0.2})
            return True
        return False

    @staticmethod
    def point_in_polygon(x, y, poly):
        """Алгоритм проверки точки в полигоне"""
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(1, n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside
