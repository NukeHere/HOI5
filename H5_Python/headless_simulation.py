"""The real game simulation with plain map cells and no window, textures or draw calls.

Game rules are inherited from Game. Only initialization and rendering/cache adapters
are replaced; combat/economy/politics/AI are the same code as the interactive game.
"""

import random
from collections import deque
from pathlib import Path

import pyglet
pyglet.options["shadow_window"] = False

from MainGame import Game, WorldGenerator
from Constants import HEX_WID, HEX_HGT, MAX_BOTS
from simulation_core import LocalSimulationServer, LocalSimulationClient
from performance import PerformanceProfiler
from politics_system import PoliticsSystem
from ai_system import CountryAI
from country_names import country_identities


class SimulationTile:
    def __init__(self, data):
        self.__dict__.update(vars(data))
        self.map_data = data
        self.s = -self.q - self.r
        self.center_x, self.center_y = self.x, self.y
        self.owner = None
        self.supply_score = 0.0
        self.is_capital = False
        self.buildings = []
        self.building_coverage = {}
        self.building_health = {}
        self.color = (0, 0, 0)


class HeadlessGame(Game):
    def __init__(self, seed=1, countries=4, map_size=32, news_path=None, ai_seed=None, difficulty="Normal"):
        if not 1 <= countries <= MAX_BOTS + 1:
            raise ValueError(f"countries must be between 1 and {MAX_BOTS + 1}")
        if not 16 <= map_size <= 150:
            raise ValueError("map_size must be between 16 and 150")
        # Do NOT call arcade.View/Game.__init__: neither a real nor hidden GL window.
        random.seed(seed)
        self.world_seed = seed
        self.bot_count = countries - 1
        self.map_size = self.grid_width = self.grid_height = map_size
        self.difficulty = difficulty
        self.paused = self.game_over = False
        self.human_player = None
        self._window = None
        self.battles_started = 0
        self.divisions_destroyed = {}
        self.event_sink = None
        for key in ("players", "hex_grid", "divisions", "airbases", "air_wings", "air_defense_units",
                    "air_salvos", "air_attack_salvos", "air_impact_decals", "field_helipad_projects",
                    "last_market_fills", "last_market_unfilled"):
            setattr(self, key, [])
        for key in ("hex_lookup", "division_lookup", "battles", "air_wing_lookup", "air_wings_by_tile",
                    "air_defense_unit_lookup", "air_defense_units_by_tile", "air_salvo_lookup",
                    "air_salvo_tile_lookup", "air_attack_salvo_lookup", "selected_resource_signal_cache"):
            setattr(self, key, {})
        for key in ("selected_division_ids", "selected_air_wing_ids", "air_wing_target_mode_ids",
                    "air_wing_rebase_mode_ids", "ownership_dirty_tile_keys", "map_overview_dirty_tile_keys"):
            setattr(self, key, set())
        for key in ("next_division_id", "next_army_id", "next_battle_plan_id", "next_airbase_id",
                    "next_air_wing_id", "next_air_defense_unit_id", "next_air_salvo_id",
                    "next_air_attack_salvo_id", "next_field_helipad_project_id"):
            setattr(self, key, 1)
        for key in ("tile_visual_revision", "air_asset_revision", "air_salvo_revision", "last_production_tick_count"):
            setattr(self, key, 0)
        for key in ("selected_air_wing_id", "selected_air_defense_unit_id", "air_wing_target_mode_id",
                    "air_wing_rebase_mode_id", "air_defense_move_mode_id", "trade_panel_cache", "economy_panel_cache"):
            setattr(self, key, None)
        self.air_salvo_tile_cache_revision = -1
        self.map_overview_dirty = False
        self.hex_panel_message = ""
        self.hex_panel_message_timer = 0
        self.profiler = PerformanceProfiler()
        self.simulation_server = LocalSimulationServer()
        self.simulation_client = LocalSimulationClient(self.simulation_server)
        self.division_templates = self.load_division_templates()
        self.world_generator = WorldGenerator(map_size, map_size, seed)
        for q in range(map_size):
            for r in range(map_size):
                x = 100 + q * HEX_WID + (r % 2) * HEX_WID / 2
                y = 100 + r * HEX_HGT * .75
                tile = SimulationTile(self.world_generator.generate_tile_data(q, r, x, y))
                self.hex_grid.append(tile)
                self.hex_lookup[q, r] = tile
        self.setup_players_and_states()
        identities = country_identities(seed, countries)
        for player, (name, ruler) in zip(self.players, identities):
            player.is_human = False
            player.name, player.ruler_name = name, ruler
        self.human_player = None
        self.register_simulation_command_handlers()
        self.ai_system = CountryAI(self, random_seed=ai_seed)
        if news_path:
            self.politics.news.start_log(Path(news_path), self.simulation_server.current_time, seed, self.players)
        self.simulation_server.set_speed_level(5)
        self.simulation_server.set_paused(False)

    def initialize_politics(self):
        self.politics = PoliticsSystem(self.players, start_time=self.simulation_server.current_time,
                                      news_seed=self.world_seed)
        self.last_market_fills, self.last_market_unfilled = [], []
        self.country_card_message = ""

    def selected_hex_tiles(self):
        return []

    def get_tile_map_color(self, tile):
        return tile.owner.color if tile.owner else (0, 0, 0)

    def rebuild_state_borders(self):
        pass

    def refresh_state_borders_for_tiles(self, dirty_tiles):
        pass

    def invalidate_construction_placement_cache(self):
        self.construction_placement_cache_key = None

    def refresh_construction_placement_tile(self, tile, building_key=None):
        pass

    def advance_day(self):
        self.simulation_server.update(.25, self.advance_simulation)
        self.simulation_client.sync_from_server()
        self.process_ownership_refresh()

    def start_or_join_battle(self, division, target_tile):
        before = set(self.battles)
        result = super().start_or_join_battle(division, target_tile)
        for key in self.battles.keys() - before:
            self.battles_started += 1
            if self.event_sink:
                self.event_sink(dict(type="battle_started", hour=self.ai_system.hour,
                                     tile=self.tile_key(target_tile), attacker=division.owner.id))
        return result

    def destroy_division(self, division):
        if division in self.divisions:
            owner = division.owner.id
            self.divisions_destroyed[owner] = self.divisions_destroyed.get(owner, 0) + 1
            if self.event_sink:
                self.event_sink(dict(type="division_destroyed", hour=self.ai_system.hour,
                                     country_id=owner, division_id=division.id,
                                     tile=self.tile_key(division.tile) if division.tile else None))
        return super().destroy_division(division)

    def setup_border_war(self, forward_counts=(5, 3)):
        """Explicit test fixture, never silently applied to a natural game."""
        for index, a in enumerate(self.players):
            for b in self.players[index + 1:]:
                start, end = self.tile_key(a.capital_tile), self.tile_key(b.capital_tile)
                previous = {start: None}
                queue = deque([start])
                while queue and end not in previous:
                    key = queue.popleft()
                    for tile in self.neighbor_tiles(self.tile_for_key(key)):
                        other = self.tile_key(tile)
                        if other not in previous and not self.is_water_tile(tile) and tile.owner in (None, a, b):
                            previous[other] = key
                            queue.append(other)
                if end not in previous:
                    continue
                path, key = [], end
                while key is not None:
                    path.append(key)
                    key = previous[key]
                path.reverse()
                if len(path) < 4:
                    continue
                middle = len(path) // 2
                for i, key in enumerate(path):
                    self.set_tile_owner_only(self.tile_for_key(key), a if i < middle else b)
                for player, key, count in ((a, path[middle - 1], forward_counts[0]),
                                           (b, path[middle], forward_counts[1])):
                    tile = self.tile_for_key(key)
                    tile.building_coverage.update(supply_depot=1, warehouse=.6)
                    for division in player.divisions[:count]:
                        division.tile = tile
                        division.x, division.y = tile.center_x, tile.center_y
                    player.legitimacy = player.war_support = .7
                    player.politics.political_capital = 100
                    self.recalculate_state_resources(player)
                    self.recalculate_state_production_cache(player)
                    self.recalculate_player_supply(player)
                    self.recalculate_player_storage(player)
                self.politics.war_goals[a.id, b.id] = self.politics.day
                ok, reason = self.politics.execute(a.id, b.id, "war")
                if not ok:
                    raise RuntimeError(f"Scenario war rejected: {reason}")
                self.politics.news.publish(self.politics.day, "test_scenario", "Тестовый пограничный конфликт",
                    f"Сценарий: {a.name} и {b.name} получили сухопутный коридор, передовые группы "
                    f"{forward_counts[0]} против {forward_counts[1]} и пункты снабжения. "
                    "Война начата настройкой теста, а не самостоятельным решением ИИ.")
                return a.id, b.id
        raise ValueError("No pair of countries shares a reachable land component; try another seed")
