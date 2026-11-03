"""Instrument actual ammo deliveries, aircraft losses and rebuilding in a combat fixture."""
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headless_simulation import HeadlessGame
from simulate_ai import audit_world


def main():
    game = HeadlessGame(146591, countries=6, map_size=50)
    game.setup_border_war()
    for player in game.players:
        if not any(game.countries_hostile(player, other) for other in game.players):
            continue
        unit = next((u for u in player.air_defense_units if u.fire_range_cells > 0), None)
        if unit:
            old = unit.tile
            unit.tile = player.divisions[0].tile
            unit.x, unit.y = unit.tile.center_x, unit.tile.center_y
            game.move_air_defense_unit_index(unit, old, unit.tile)
    counts = Counter()
    original_replenish = game.replenish_air_defense_ammo
    original_spend = game.spend_air_defense_unit_ammo
    original_hits = game.apply_air_wing_air_defense_hits
    original_create = game.create_air_defense_unit
    original_complete = game.complete_construction_project
    def replenish(unit, hours):
        original_replenish(unit, hours)
        counts["aa_ammo_received"] += unit.last_ammo_received
    def spend(unit, amount):
        result = original_spend(unit, amount)
        key = "standalone_aa_ammo_fired" if getattr(unit, "division_id", None) is None else "division_aa_ammo_fired"
        counts[key] += result
        return result
    def hits(wing, aircraft_type, amount):
        result = original_hits(wing, aircraft_type, amount)
        for key, value in zip(("aircraft_destroyed_from_hits", "aircraft_damaged_from_hits", "sorties_aborted_from_hits"), result):
            counts[key] += value
        return result
    def create(*args, **kwargs):
        result = original_create(*args, **kwargs)
        counts["aa_replacements"] += bool(result)
        return result
    def complete(player, project):
        original_complete(player, project)
        counts[f"{project['building']}_{project.get('project_type')}_steps"] += 1
    game.replenish_air_defense_ammo = replenish
    game.spend_air_defense_unit_ammo = spend
    game.apply_air_wing_air_defense_hits = hits
    game.create_air_defense_unit = create
    game.complete_construction_project = complete
    for day in range(120):
        game.advance_day()
        if (day + 1) % 30 == 0:
            audit_world(game)
            counts["audits_passed"] += 1
        for unit in game.air_defense_units:
            assert 0 <= unit.ammo <= unit.ammo_capacity
    result = dict(days=120, scenario="prepared border war; one armed battery per belligerent deployed at frontline", counts=dict(counts),
                  battles_started=game.battles_started,
                  survivors=[dict(country=p.id, units=len(p.air_defense_units),
                                  empty=sum(u.ammo == 0 and u.fire_range_cells > 0 for u in p.air_defense_units)) for p in game.players])
    output = Path("logs/diagnostics/audio-pvo-camera/defense-balance.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
