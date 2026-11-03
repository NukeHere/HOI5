from dataclasses import dataclass, field

from Constants import DEEP_OCEAN_LEVEL, WATER_LEVEL


@dataclass
class MapTileData:
    q: int
    r: int
    x: float
    y: float
    elevation: float
    moisture: float
    temperature: float
    ridge_value: float = 0.0
    terrain_type: str | None = None
    resources: list = field(default_factory=list)
    water_cover: float | None = None
    tree_cover: float | None = None
    grass_cover: float | None = None
    rock_cover: float | None = None
    sand_cover: float | None = None
    snow_cover: float | None = None
    movement_cost: float = 1.0
    passability: float = 1.0

    def initialize_natural_components(self):
        self.water_cover = 0.0
        self.tree_cover = 0.0
        self.grass_cover = 0.0
        self.rock_cover = 0.0
        self.sand_cover = 0.0
        self.snow_cover = 0.0

        if self.elevation < WATER_LEVEL:
            self.water_cover = 0.8 * (WATER_LEVEL - self.elevation) / WATER_LEVEL + 0.2
            self.normalize_covers()
            return

        ridge_rock_bonus = self.ridge_value * 0.45
        ridge_tree_penalty = self.ridge_value * 0.35

        if self.elevation > 0.7 or self.ridge_value > 0.65:
            self.rock_cover = min(0.95, 0.4 + max(0.0, self.elevation - 0.7) * 2 + ridge_rock_bonus)
            self.tree_cover = min(0.35, max(0.0, 0.1 + (self.moisture - 0.3) * 2 - ridge_tree_penalty))
            if self.temperature < 0.3:
                self.snow_cover = min(0.85, 0.3 + (0.3 - self.temperature) * 2 + self.ridge_value * 0.15)
            self.grass_cover = max(0.0, 1.0 - self.rock_cover - self.snow_cover - self.tree_cover)

        elif self.elevation > 0.5 or self.ridge_value > 0.35:
            self.rock_cover = min(0.75, 0.2 + max(0.0, self.elevation - 0.5) + ridge_rock_bonus)
            self.tree_cover = min(0.65, max(0.0, 0.35 + (self.moisture - 0.35) * 2 - ridge_tree_penalty))
            self.grass_cover = max(0.0, 1.0 - self.rock_cover - self.tree_cover)

        else:
            if self.moisture > 0.5:
                self.grass_cover = 0.8
                self.tree_cover = 0.2
            elif self.moisture > 0.2:
                self.tree_cover = min(0.8, 0.5 + (self.moisture - 0.4) * 2)
                self.grass_cover = max(0.0, 1.0 - self.tree_cover)
            elif self.temperature > 0.6:
                self.sand_cover = 0.6
                self.grass_cover = 0.4
            else:
                self.grass_cover = 0.5
                self.sand_cover = 0.3
                self.tree_cover = 0.2

        if self.temperature < 0.2 and self.elevation < 0.5:
            self.snow_cover = min(0.7, self.snow_cover + 0.3)
            factor = 1.0 - self.snow_cover
            self.grass_cover *= factor
            self.tree_cover *= factor
            self.sand_cover *= factor

        self.normalize_covers()

    def normalize_covers(self):
        self.water_cover = max(0.0, self.water_cover or 0.0)
        self.tree_cover = max(0.0, self.tree_cover or 0.0)
        self.grass_cover = max(0.0, self.grass_cover or 0.0)
        self.rock_cover = max(0.0, self.rock_cover or 0.0)
        self.sand_cover = max(0.0, self.sand_cover or 0.0)
        self.snow_cover = max(0.0, self.snow_cover or 0.0)
        total = (
            self.water_cover + self.tree_cover + self.grass_cover
            + self.rock_cover + self.sand_cover + self.snow_cover
        )
        if total > 0.001:
            self.water_cover /= total
            self.tree_cover /= total
            self.grass_cover /= total
            self.rock_cover /= total
            self.sand_cover /= total
            self.snow_cover /= total
        else:
            self.grass_cover = 1.0

    def determine_biome(self):
        if self.water_cover > 0.5:
            if self.terrain_type == "lake":
                return "lake"
            if self.water_cover > 0.9:
                if self.elevation < DEEP_OCEAN_LEVEL:
                    return "deep_ocean"
                return "ocean"
            return "shallow_water"

        if self.water_cover > 0.2 and self.tree_cover > 0.3:
            if self.temperature > 0.6:
                return "mangrove"
            if self.temperature > 0.3:
                return "swamp"
            return "bog"

        if self.ridge_value > 0.75 and self.temperature < 0.35:
            return "snowy_mountains"
        if self.ridge_value > 0.7 or self.rock_cover > 0.7:
            return "mountains"
        if self.ridge_value > 0.4 or self.rock_cover > 0.45:
            return "hills"

        components = [
            (self.sand_cover, "sandy"),
            (self.snow_cover, "snowy"),
            (self.tree_cover, "forested"),
            (self.grass_cover, "grassy"),
        ]
        primary_type = max(components, key=lambda item: item[0])[1]

        if primary_type == "sandy":
            return "desert" if self.temperature > 0.6 else "plains"
        if primary_type == "snowy":
            return "tundra"
        if primary_type == "forested":
            if self.temperature > 0.7:
                return "tropical_rainforest"
            if self.temperature > 0.5:
                return "jungle"
            if self.temperature > 0.3:
                return "temperate_forest"
            return "taiga"
        if self.temperature > 0.7:
            return "savanna"
        if self.temperature > 0.4:
            return "grassland"
        return "tundra"

    def generate_resources(self, rng):
        resources = []

        def add(name, chance, depth_range, mass_range):
            if rng.random() < chance:
                depth = rng.uniform(*depth_range) / 1000
                mass = rng.uniform(*mass_range)
                resources.append([name, depth, mass])

        rocky = self.terrain_type in ["hills", "mountains", "snowy_mountains"] or self.rock_cover > 0.35
        dry = self.terrain_type in ["desert", "plains"] or self.sand_cover > 0.3 or self.moisture < 0.3
        wet = self.terrain_type in ["lake", "swamp", "bog"] or self.moisture > 0.6
        water = self.water_cover > 0.5

        rare_geology = rocky and (
            self.terrain_type in ["hills", "mountains", "snowy_mountains"]
            or self.ridge_value > 0.25
            or self.rock_cover > 0.55
        )
        peatland = (
            self.terrain_type in ["swamp", "bog", "tundra", "taiga", "lake"]
            or (self.moisture > 0.55 and self.temperature < 0.55 and self.elevation < 0.55)
        )
        tropical_latex = (
            self.temperature > 0.55
            and self.moisture > 0.35
            and (
                self.tree_cover > 0.05
                or self.terrain_type in ["jungle", "tropical_rainforest", "mangrove", "savanna"]
            )
        )

        if rocky:
            add("coal", 0.22, (100, 800), (5000, 50000))
            add("iron_ore", 0.32, (0, 1000), (10000, 200000))
            add("alloying_additives", 0.15, (100, 800), (1000, 20000))
            add("copper_ore", 0.18, (50, 1500), (5000, 100000))
            add("lead", 0.12, (100, 600), (3000, 50000))
            add("zinc", 0.12, (100, 600), (2000, 30000))
            add("nickel", 0.12, (200, 1000), (2000, 40000))
            add("silver", 0.04, (100, 800), (50, 5000))
            add("apatite", 0.09, (50, 300), (5000, 50000))
            add("graphite", 0.08, (50, 500), (1000, 20000))
            add("mica", 0.08, (50, 300), (500, 10000))
            if rare_geology:
                add("gold", 0.035, (100, 1000), (10, 1000))
                add("silver", 0.07, (100, 800), (50, 5000))
                add("rare_earth_metals", 0.045, (50, 500), (100, 5000))
                add("uranium", 0.05, (50, 500), (1000, 10000))
                add("quartz", 0.16, (10, 200), (1000, 30000))

        if self.temperature > 0.42 and self.moisture > 0.45:
            add("bauxite", 0.34, (0, 50), (5000, 100000))

        if tropical_latex:
            add("rubber", 0.18, (0, 0), (1000, 30000))

        if dry:
            add("oil", 0.18, (500, 3000), (100000, 1000000))
            add("potash", 0.15, (100, 1000), (10000, 200000))

        if self.terrain_type in ["mountains", "hills", "desert"] or self.temperature > 0.7:
            add("sulfur", 0.1, (0, 1500), (1000, 50000))

        if any(resource[0] == "oil" for resource in resources):
            add("natural_gas", 0.6, (500, 4000), (50000, 500000))

        if peatland:
            add("peat", 0.22, (0, 10), (1000, 20000))

        if water:
            add("phosphorite", 0.1, (0, 100), (10000, 100000))

        self.resources = resources

    def calculate_movement_cost(self):
        if self.terrain_type in ["deep_ocean", "ocean"]:
            return float("inf")
        if self.terrain_type in ["shallow_water", "lake", "river", "swamp", "bog", "mangrove"]:
            return 3.0

        cost = 1.0
        cost += self.ridge_value * 1.5
        cost += self.rock_cover * 1.2
        cost += self.snow_cover * 0.5
        if self.terrain_type == "mountains":
            cost += 1.5
        elif self.terrain_type == "snowy_mountains":
            cost += 2.0
        elif self.terrain_type == "hills":
            cost += 0.75
        return max(1.0, cost)

    def finalize_generation(self, rng):
        self.initialize_natural_components()
        self.terrain_type = self.determine_biome()
        self.generate_resources(rng)
        self.movement_cost = self.calculate_movement_cost()
        self.passability = 0.0 if self.movement_cost == float("inf") else 1.0 / self.movement_cost
