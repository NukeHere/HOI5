"""Long real-rule war fixture with a streaming loss/recovery ledger, no graphics."""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("PYGLET_AUDIO", "silent")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headless_simulation import HeadlessGame
from simulate_ai import audit_world, front_metrics


def run(days, size, seed, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    game = HeadlessGame(seed, countries=2, map_size=size, news_path=output / "news.txt")
    a, b = game.setup_border_war(forward_counts=(7, 3))
    front = [p.divisions[0].tile for p in game.players]
    neighbors = {neighbor for center in front for neighbor in game.neighbor_tiles(center)}
    for tile in sorted(neighbors, key=game.tile_key):
        if tile.owner is None and not game.is_water_tile(tile):
            side = min(range(2), key=lambda i: (game.hex_distance(front[i], tile), tile.q % 2 != i))
            game.set_tile_owner_only(tile, game.players[side])
    # Give the attacker a local advantage. Subsequent orders come from AI.
    for player in game.players:
        tile = player.divisions[0].tile
        unit = next((u for u in player.air_defense_units if u.fire_range_cells > 0), None)
        if unit:
            old = unit.tile
            unit.tile = tile
            unit.x, unit.y = tile.center_x, tile.center_y
            game.move_air_defense_unit_index(unit, old, tile)
        rear = next((t for t in game.neighbor_tiles(tile) if t.owner is player and not game.is_water_tile(t)
                     and not any(n.owner and n.owner is not player for n in game.neighbor_tiles(t))), tile)
        game.create_airbase(player, rear, coverage=1)
        for wing in player.air_wings:
            game.remove_from_tile_index(game.air_wings_by_tile, wing.base_tile, wing)
            wing.base_tile = rear
            game.add_to_tile_index(game.air_wings_by_tile, rear, wing)
        game.recalculate_player_supply(player)
        game.recalculate_player_storage(player)
    totals = defaultdict(Counter)
    context = {}
    ownership = Counter()
    recovery = {}
    completed_recoveries = []
    started = time.perf_counter()

    def snapshot():
        return dict(day=game.politics.day, date=str(game.simulation_server.current_time),
            battles=len(game.battles), battles_started=game.battles_started,
            wars=sum(r.at_war for r in game.politics.relations.values()),
            countries=[dict(id=p.id, name=p.name, tiles=len(p.tiles), budget=p.budget,
                manpower_reserve=p.manpower_reserve, front=front_metrics(game, p),
                recruited=game.recruitment.completed[p.id],
                units=[dict(id=d.id, tile=game.tile_key(d.tile), strength=d.strength,
                    max_strength=d.max_strength, manpower=d.manpower, max_manpower=d.max_manpower,
                    organization=d.organization, supply=game.division_supply_ratio(d),
                    stock=dict(d.supply_stock), battle=d.battle_id, route=d.route_mode,
                    target=game.tile_key(d.target_tile) if d.target_tile else None) for d in p.divisions],
                wings=[dict(id=w.id, tile=game.tile_key(w.base_tile), aircraft=w.aircraft_count,
                    damaged=w.damaged_count, ready=w.ready_count) for w in p.air_wings if w.base_tile],
                aa=[dict(id=u.id, unit_class=u.unit_class, ammo=u.ammo, capacity=u.ammo_capacity,
                    health=u.health, tile=game.tile_key(u.tile)) for u in p.air_defense_units],
                construction=[dict(building=q.get("building"), kind=q.get("project_type"),
                    status=q.get("status")) for q in p.construction_queue]) for p in game.players])

    config = dict(seed=seed, days=days, map_size=size, countries=2,
        scenario="Explicit widened border-war fixture, seven vs three forward divisions, forward airbases and one armed AA battery per side; autonomous AI thereafter",
        belligerents=[a, b])
    (output / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    initial = snapshot()
    (output / "initial.json").write_text(json.dumps(initial, ensure_ascii=False, indent=2), encoding="utf-8")

    with (output / "battle.jsonl").open("w", encoding="utf-8") as log, \
         (output / "daily.jsonl").open("w", encoding="utf-8") as daily, \
         (output / "decisions.jsonl").open("w", encoding="utf-8") as decisions:
        def emit(kind, **data):
            log.write(json.dumps(dict(hour=game.ai_system.hour, date=str(game.simulation_server.current_time),
                kind=kind, **data), ensure_ascii=False) + "\n")
        game.event_sink = lambda record: emit("world_event", event=record)
        for bot in game.ai_system.bots.values():
            def note(hour, kind, _bot=bot, _note=bot.note, **data):
                _note(hour, kind, **data)
                decisions.write(json.dumps(dict(country=_bot.country_id, **_bot.history[-1]), ensure_ascii=False) + "\n")
            bot.note = note

        def contextual(name, make_context):
            original = getattr(game, name)
            def call(*args, **kwargs):
                old = dict(context)
                context.update(make_context(*args, **kwargs))
                try:
                    return original(*args, **kwargs)
                finally:
                    context.clear()
                    context.update(old)
            setattr(game, name, call)

        contextual("apply_combat_attack", lambda attacker, target, *args, **kw:
            dict(cause="ground", attacker=attacker.id, attacker_country=attacker.owner.id))
        contextual("resolve_air_salvo_impact", lambda salvo:
            dict(cause="air", munition=salvo.munition_type, attacker_country=salvo.owner.id,
                 wing=getattr(salvo, "source_air_wing_id", None)))
        contextual("apply_battle_collateral_damage", lambda *args, **kw: dict(cause="ground_collateral"))
        contextual("capture_battle_tile", lambda battle: dict(cause="overrun_on_capture", attacker_country=battle.attacker.id))
        contextual("destroy_invalid_retreating_division", lambda division: dict(cause="retreat_cut_off"))
        contextual("destroy_stranded_enemy_division", lambda division: dict(cause="stranded_on_enemy_tile"))
        contextual("resolve_air_attack_salvo_impact", lambda salvo: dict(cause="air_to_air",
                   attacker_country=salvo.owner.id, wing=salvo.launcher_air_wing_id))

        destroy_original = game.destroy_division
        def destroy(division):
            if division in game.divisions:
                cause = context.get("cause", "depleted_strength" if division.strength <= 0 else "other")
                totals[division.owner.id]["manpower_in_destroyed_units"] += division.manpower
                totals[division.owner.id]["strength_in_destroyed_units"] += division.strength
                emit("division_removed", country=division.owner.id, division=division.id,
                     tile=game.tile_key(division.tile), strength_remaining=division.strength,
                     manpower_remaining=division.manpower, equipment_remaining=division.supply_stock,
                     cause=cause, interrupted_recovery=recovery.pop(division.id, None))
            return destroy_original(division)
        game.destroy_division = destroy

        end_original = game.end_battle
        def end(battle):
            if battle.id in game.battles:
                emit("battle_ended", battle=battle.id, tile=game.tile_key(battle.tile), attacker=battle.attacker.id,
                     owner=battle.tile.owner.id if battle.tile.owner else None,
                     captured=battle.tile.owner is battle.attacker)
            return end_original(battle)
        game.end_battle = end

        loss_original = game.apply_division_strength_losses
        def loss(division, *args, **kwargs):
            before = (division.strength, division.manpower, dict(division.supply_stock))
            result = loss_original(division, *args, **kwargs)
            if result:
                equipment = {k: v - division.supply_stock.get(k, 0) for k, v in before[2].items()
                             if v - division.supply_stock.get(k, 0) > 1e-8}
                cause = context.get("cause", "other")
                c = totals[division.owner.id]
                c[cause + "_strength_lost"] += result
                c[cause + "_manpower_lost"] += before[1] - division.manpower
                if division.id not in recovery and (division.strength < division.max_strength * .95
                                                     or division.manpower < division.max_manpower * .95):
                    recovery[division.id] = dict(first_damaged_hour=game.ai_system.hour, country=division.owner.id)
                emit("division_loss", division=division.id, country=division.owner.id, tile=game.tile_key(division.tile),
                     strength=result, manpower=before[1] - division.manpower, equipment=equipment,
                     strength_after=division.strength, manpower_after=division.manpower, **context)
            return result
        game.apply_division_strength_losses = loss

        targeted_original = game.apply_air_salvo_targeted_equipment_losses
        def targeted(division, *args, **kwargs):
            result = targeted_original(division, *args, **kwargs)
            if result:
                emit("targeted_equipment_loss", division=division.id, country=division.owner.id, losses=result, **context)
            return result
        game.apply_air_salvo_targeted_equipment_losses = targeted

        replenish_original = game.replenish_division
        def replenish(division, hours):
            before = (division.strength, division.manpower, dict(division.supply_stock))
            result = replenish_original(division, hours)
            strength, manpower = division.strength - before[0], division.manpower - before[1]
            stock = {k: v - before[2].get(k, 0) for k, v in division.supply_stock.items()
                     if v - before[2].get(k, 0) > 1e-8}
            if strength or manpower or stock:
                totals[division.owner.id]["strength_restored"] += strength
                totals[division.owner.id]["manpower_reinforced"] += manpower
                emit("reinforcement", division=division.id, country=division.owner.id, hours=hours,
                    strength=strength, manpower=manpower, supplies=stock, supply=division.last_supply_ratio,
                    in_battle=bool(division.battle_id), strength_after=division.strength, manpower_after=division.manpower)
            if division.id in recovery and division.strength >= division.max_strength * .95 and division.manpower >= division.max_manpower * .95:
                episode = recovery.pop(division.id)
                episode.update(division=division.id, hours=game.ai_system.hour - episode["first_damaged_hour"])
                completed_recoveries.append(episode)
                emit("recovered_to_95_percent", **episode)
            return result
        game.replenish_division = replenish

        recover_original = game.recover_division_organization
        def recover(division, *args, **kwargs):
            result = recover_original(division, *args, **kwargs)
            if result:
                totals[division.owner.id]["organization_recovered"] += result
                emit("organization_recovery", country=division.owner.id, division=division.id,
                    amount=result, after=division.organization, supply=game.division_supply_ratio(division))
            return result
        game.recover_division_organization = recover

        damage_original = game.damage_building
        def damage(tile, key, *args, **kwargs):
            before = game.building_health(tile, key)
            result = damage_original(tile, key, *args, **kwargs)
            if result:
                emit("building_damage", country=tile.owner.id if tile.owner else None,
                    tile=game.tile_key(tile), building=key, before=before, after=game.building_health(tile, key), **context)
            return result
        game.damage_building = damage

        transfer_original = game.transfer_tile_owner
        def transfer(tile, owner):
            old = tile.owner.id if tile.owner else None
            result = transfer_original(tile, owner)
            new = tile.owner.id if tile.owner else None
            if old != new:
                ownership[game.tile_key(tile)] += 1
                emit("territory_transfer", tile=game.tile_key(tile), previous=old, owner=new, supply=tile.supply_score)
            return result
        game.transfer_tile_owner = transfer

        aa_original = game.replenish_air_defense_ammo
        def aa(unit, hours):
            aa_original(unit, hours)
            if unit.last_ammo_received:
                totals[unit.owner.id]["aa_ammo_received"] += unit.last_ammo_received
                emit("aa_reloaded", country=unit.owner.id, unit=unit.id, amount=unit.last_ammo_received, ammo=unit.ammo)
        game.replenish_air_defense_ammo = aa
        spend_original = game.spend_air_defense_unit_ammo
        def spend(unit, amount):
            spent = spend_original(unit, amount)
            if spent:
                tactical = getattr(unit, "division_id", None)
                totals[unit.owner.id]["division_aa_ammo_fired" if tactical else "standalone_aa_ammo_fired"] += spent
                emit("aa_fired", country=unit.owner.id, unit=unit.id, division=tactical,
                     amount=spent, ammo=unit.ammo)
            return spent
        game.spend_air_defense_unit_ammo = spend
        hits_original = game.apply_air_wing_air_defense_hits
        def hits(wing, aircraft_type, amount):
            result = hits_original(wing, aircraft_type, amount)
            if any(result):
                for key, value in zip(("aircraft_destroyed_by_hits", "aircraft_damaged_by_hits", "sorties_aborted_by_hits"), result):
                    totals[wing.owner.id][key] += value
                emit("aircraft_hit", country=wing.owner.id, wing=wing.id, aircraft=aircraft_type,
                     destroyed=result[0], damaged=result[1], aborted=result[2],
                     cause=context.get("cause", "ground_aa"))
            return result
        game.apply_air_wing_air_defense_hits = hits
        complete_original = game.complete_construction_project
        def complete(player, project):
            result = complete_original(player, project)
            totals[player.id][project.get("project_type", "build") + "_" + project["building"]] += 1
            emit("construction_completed", country=player.id, building=project["building"], project_type=project.get("project_type"))
            return result
        game.complete_construction_project = complete

        audit_world(game)
        audits = 1
        for day in range(1, days + 1):
            game.advance_day()
            state = snapshot()
            daily.write(json.dumps(state, ensure_ascii=False) + "\n")
            if day % 30 == 0 or day == days:
                audit_world(game)
                audits += 1
                log.flush()
                daily.flush()
                decisions.flush()
                print(json.dumps(dict(day=day, battles=state["battles"], total_battles=game.battles_started,
                    elapsed=round(time.perf_counter() - started, 1),
                    countries=[dict(id=p.id, tiles=len(p.tiles), divisions=len(p.divisions)) for p in game.players])), flush=True)
        final = snapshot()
    result = dict(config=config, elapsed_seconds=time.perf_counter() - started, audits=audits,
        initial=initial, final=final, totals={k: dict(v) for k, v in totals.items()},
        destroyed_divisions=game.divisions_destroyed, completed_recoveries=completed_recoveries,
        unrecovered_episodes=recovery, territory_transfers=sum(ownership.values()),
        repeatedly_contested_hexes=[dict(tile=k, transfers=v) for k, v in ownership.most_common(20)])
    (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--map-size", type=int, default=150)
    parser.add_argument("--seed", type=int, default=146591)
    parser.add_argument("--output", default="logs/diagnostics/long-war-730")
    args = parser.parse_args()
    run(args.days, args.map_size, args.seed, args.output)
