"""Batched small aviation markers for distant camera scales."""
import math
import time
import arcade
from Constants import HEX_WID


class AirRenderLODMixin:
    def draw_cached_air_defense_ranges(self, units):
        key = tuple((u.id, u.tile.center_x, u.tile.center_y, u.fire_range_cells,
                     u.radar_active, u.radar_range_cells, u.owner is self.human_player) for u in units)
        if key != getattr(self, "_air_defense_ranges_key", None):
            shapes = arcade.shape_list.ShapeElementList()
            for unit in units:
                friendly = unit.owner is self.human_player
                fire = (120, 230, 150) if friendly else (248, 132, 96)
                radar = (122, 196, 248, 112) if friendly else (238, 150, 238, 112)
                for radius, color, width in (
                    (unit.fire_range_cells * HEX_WID, (*fire, 150), 4),
                    (unit.fire_range_cells * HEX_WID + 3 if unit.fire_range_cells > 0 else 0, (*fire, 85), 2),
                    (unit.radar_range_cells * HEX_WID if unit.radar_active else 0, radar, 3)):
                    if radius > 0:
                        shapes.append(arcade.shape_list.create_ellipse_outline(unit.tile.center_x,
                            unit.tile.center_y, radius * 2, radius * 2, color, width))
            self._air_defense_ranges_shapes, self._air_defense_ranges_key = shapes, key
        self._air_defense_ranges_shapes.draw()

    def draw_static_air_assets(self, visible_keys):
        bases = [base for base in self.airbases if base.tile and self.tile_key(base.tile) in visible_keys]
        helipads = [tile for tile in self.visible_tiles if tile.building_coverage.get("field_helipad", 0) > 0]
        units = [unit for unit in self.air_defense_units if unit.tile and not unit.path
                 and self.tile_key(unit.tile) in visible_keys]
        key = (tuple((base.id, self.tile_key(base.tile), tuple(base.owner.border_color) if base.owner else None) for base in bases),
               tuple((self.tile_key(t), tuple(t.owner.border_color) if t.owner else None) for t in helipads),
               tuple((u.id, self.tile_key(u.tile), u.unit_class, getattr(u, "x", 0), getattr(u, "y", 0)) for u in units))
        if key != getattr(self, "_air_static_detail_key", None):
            shapes = arcade.shape_list.ShapeElementList()
            def line(x1, y1, x2, y2, color, width=1):
                shapes.append(arcade.shape_list.create_line(x1, y1, x2, y2, color, width))
            for base in bases:
                x, y = base.tile.center_x, base.tile.center_y + 12
                color = base.owner.border_color if base.owner else (190, 200, 210)
                shapes.append(arcade.shape_list.create_rectangle_filled(x, y, 36, 8, (18, 24, 31, 225)))
                shapes.append(arcade.shape_list.create_rectangle_outline(x, y, 36, 8, color, 2))
                line(x - 12, y, x + 12, y, (228, 238, 248))
            for tile in helipads:
                x, y = tile.center_x + 16, tile.center_y - 12
                color = tile.owner.border_color if tile.owner else (180, 190, 200)
                shapes.append(arcade.shape_list.create_ellipse_filled(x, y, 18, 18, (18, 24, 31, 220)))
                shapes.append(arcade.shape_list.create_ellipse_outline(x, y, 20, 20, color, 2))
                for x1, y1, x2, y2 in ((x - 4, y - 5, x - 4, y + 5), (x + 4, y - 5, x + 4, y + 5), (x - 4, y, x + 4, y)):
                    line(x1, y1, x2, y2, (230, 238, 246))
            colors = {"manpads_team": (180, 224, 128), "short_range_aa": (124, 200, 220),
                      "medium_range_sam": (236, 204, 112), "long_range_sam": (238, 150, 112), "radar_unit": (178, 164, 238)}
            for unit in units:
                x, y = getattr(unit, "x", unit.tile.center_x) - 17, getattr(unit, "y", unit.tile.center_y) - 12
                color = colors.get(unit.unit_class, (210, 220, 230))
                shapes.append(arcade.shape_list.create_ellipse_filled(x, y, 16, 16, (18, 24, 31, 225)))
                shapes.append(arcade.shape_list.create_ellipse_outline(x, y, 18, 18, color, 2))
                if unit.unit_class == "radar_unit":
                    line(x, y, x + 7, y + 4, color, 2)
                    shapes.append(arcade.shape_list.create_ellipse_outline(x, y, 26, 26, (*color, 130), 1))
                else:
                    for x1, y1, x2, y2 in ((x, y + 6, x - 6, y - 5), (x - 6, y - 5, x + 6, y - 5), (x + 6, y - 5, x, y + 6)):
                        line(x1, y1, x2, y2, color, 2)
            self._air_static_detail_shapes, self._air_static_detail_key = shapes, key
        self._air_static_detail_shapes.draw()

    def draw_air_assets_lod(self):
        zoom = self.world_camera.zoom
        cx, cy = self.world_camera.position
        half_w = self.window.width / zoom / 2 + HEX_WID
        half_h = self.window.height / zoom / 2 + HEX_WID
        def visible(tile):
            return tile and abs(tile.center_x - cx) <= half_w and abs(tile.center_y - cy) <= half_h
        key = (round(zoom, 5), self.window.width, self.window.height,
               self.air_defense_overlay_enabled, self.selected_air_defense_unit_id,
               tuple((b.id, b.tile.center_x, b.tile.center_y, tuple(b.owner.border_color) if b.owner else None)
                     for b in self.airbases if visible(b.tile)),
               tuple((u.id, u.tile.center_x, u.tile.center_y, u.fire_range_cells, u.radar_range_cells, u.radar_active,
                      tuple(u.owner.border_color) if u.owner else None) for u in self.air_defense_units if visible(u.tile)))
        if key != getattr(self, "_air_lod_static_key", None):
            shapes = arcade.shape_list.ShapeElementList()
            for base in self.airbases:
                if visible(base.tile):
                    color = base.owner.border_color if base.owner else (190, 200, 210)
                    shapes.append(arcade.shape_list.create_rectangle_filled(
                        base.tile.center_x, base.tile.center_y, 5 / zoom, 3 / zoom, (*color[:3], 210)))
            for unit in self.air_defense_units:
                if not visible(unit.tile):
                    continue
                color = unit.owner.border_color if unit.owner else (190, 200, 210)
                shapes.append(arcade.shape_list.create_rectangle_filled(
                    unit.tile.center_x, unit.tile.center_y, 3 / zoom, 3 / zoom, (*color[:3], 200)))
                if self.air_defense_overlay_enabled or self.selected_air_defense_unit_id == unit.id:
                    for radius, rgba in ((unit.fire_range_cells, (*color[:3], 100)),
                                         (unit.radar_range_cells, (120, 180, 240, 70))):
                        if radius > 0:
                            shapes.append(arcade.shape_list.create_ellipse_outline(unit.tile.center_x,
                                unit.tile.center_y, radius * HEX_WID * 2, radius * HEX_WID * 2, rgba, 1))
            self._air_lod_static_shapes, self._air_lod_static_key = shapes, key
        self._air_lod_static_shapes.draw()
        now = time.perf_counter()
        flight_key = (key, tuple(sorted(self.selected_air_wing_ids)))
        if now >= getattr(self, "_air_lod_next_flight", 0) or flight_key != getattr(self, "_air_lod_flight_key", None):
            shapes = arcade.shape_list.ShapeElementList()
            for wing in self.air_wings:
                if not wing.base_tile or wing.ready_count <= 0:
                    continue
                position = self.air_wing_visual_position(wing, now=now)
                if not position:
                    continue
                x, y, heading, active = position
                if abs(x - cx) > half_w or abs(y - cy) > half_h:
                    continue
                size = (5 if active else 4) / zoom
                points = [(x + math.cos(heading + angle) * size, y + math.sin(heading + angle) * size)
                          for angle in (0, 2.5, -2.5)]
                color = wing.owner.border_color if wing.owner else (190, 200, 210)
                shapes.append(arcade.shape_list.create_polygon(points, (*color[:3], 240)))
            for decal in self.air_impact_decals:
                if not visible(decal.tile):
                    continue
                fraction = min(1, decal.age / max(.05, decal.duration))
                diameter = (5 + fraction * 7) / zoom
                shapes.append(arcade.shape_list.create_ellipse_outline(decal.tile.center_x,
                    decal.tile.center_y, diameter, diameter, (*decal.color[:3], max(20, int(160 * (1 - fraction)))), 1))
            self._air_lod_flight_shapes = shapes
            self._air_lod_flight_key = flight_key
            self._air_lod_next_flight = now + .1
        self._air_lod_flight_shapes.draw()
        for wing, x, y, heading in self.sampled_air_flight_positions():
            if abs(x - cx) <= half_w and abs(y - cy) <= half_h:
                size = 5 / zoom
                points = [(x + math.cos(heading + angle) * size, y + math.sin(heading + angle) * size)
                          for angle in (0, 2.5, -2.5)]
                color = wing.owner.border_color if wing.owner else (190, 200, 210)
                arcade.draw_polygon_filled(points, (*color[:3], 240))
        self.draw_air_wing_operation_overlays()
