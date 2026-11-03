"""Headless bot laboratory; defaults to an explicitly initialized border war.

Use --scenario natural to observe autonomous declarations in an untouched world.
"""

import argparse
from collections import Counter
import json
import math
import os
import sys
from pathlib import Path
import time
import traceback

os.environ.setdefault("PYGLET_AUDIO", "silent")
from headless_simulation import HeadlessGame


def run_directory(output, seed, ai_seed):
    return Path(output) / (f"seed-{seed}" if ai_seed is None else f"seed-{seed}-ai-{ai_seed}")


def front_metrics(game, player):
    front = {game.tile_key(t) for t in player.tiles if not game.is_water_tile(t)
             and any(n.owner and game.countries_hostile(player, n.owner) for n in game.neighbor_tiles(t))}
    occupied = {game.tile_key(d.tile) for d in player.divisions if d.tile and d.route_mode != "retreat"}
    inbound = {game.tile_key(d.target_tile) for d in player.divisions if d.path and d.target_tile
               and d.target_tile.owner is player and d.route_mode != "retreat"}
    stacks = Counter(game.tile_key(d.tile) for d in player.divisions if d.tile)
    return dict(hexes=len(front), occupied=len(front & occupied), assigned=len(front & (occupied | inbound)),
                largest_stack=max(stacks.values(), default=0),
                organization=round(sum(d.organization / max(1, d.max_organization) for d in player.divisions)
                                   / max(1, len(player.divisions)), 3))


def audit_world(game):
    """Fail at the first corrupt state, before a long run conceals its origin."""
    def require(condition, message):
        if not condition:
            raise RuntimeError("World audit: " + message)
    ids = [d.id for d in game.divisions]
    require(len(ids) == len(set(ids)), "duplicate division IDs")
    world_units = {d.id: d for d in game.divisions}
    listed = []
    for player in game.players:
        require(math.isfinite(player.budget), f"country {player.id}: non-finite budget")
        require(len(player.tiles) == len(set(player.tiles)), f"country {player.id}: duplicate tiles")
        require(all(t.owner is player for t in player.tiles), f"country {player.id}: stale owned tiles")
        for bucket in player.resource_stockpiles.values():
            require(all(math.isfinite(v) and v >= -1e-6 for v in bucket.values()),
                    f"country {player.id}: invalid stockpile")
        for division in player.divisions:
            listed.append(division.id)
            require(world_units.get(division.id) is division and division.owner is player,
                    f"division {division.id}: inconsistent owner/world registry")
    require(sorted(listed) == sorted(ids), "country/world army registries differ")
    for tile in game.hex_grid:
        require(tile.owner is None or tile in tile.owner.tiles, "tile missing from owner registry")
    for division in game.divisions:
        require(division.tile is not None, f"division {division.id}: no position")
        for name, maximum in (("strength", division.max_strength), ("organization", division.max_organization)):
            value = getattr(division, name)
            require(math.isfinite(value) and -1e-6 <= value <= maximum + 1e-6,
                    f"division {division.id}: invalid {name}")
        require(division.battle_id is None or division.battle_id in game.battles,
                f"division {division.id}: dangling battle")


def run(seed, days, countries, size, output, scenario="natural", ai_seed=None):
    directory = run_directory(output, seed, ai_seed)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(dict(seed=seed, days=days, countries=countries,
        map_size=size, scenario=scenario, headless=True, ai_seed=seed if ai_seed is None else ai_seed), indent=2), encoding="utf-8")
    (directory / "summary.json").write_text(json.dumps(dict(status="running", seed=seed, scenario=scenario)), encoding="utf-8")
    (directory / "error.json").write_text("null\n", encoding="utf-8")
    game = HeadlessGame(seed, countries, size, directory / "news.txt", ai_seed=ai_seed)
    events = Counter()
    news = Counter()
    original_publish = game.politics.news.publish
    def publish(*args, **kwargs):
        item = original_publish(*args, **kwargs)
        news[item.key] += 1
        return item
    game.politics.news.publish = publish
    if scenario == "border-war":
        game.setup_border_war()
    initial = {p.id: len(p.tiles) for p in game.players}
    audit_world(game)
    audits = 1
    started = time.perf_counter()
    with (directory / "decisions.jsonl").open("w", encoding="utf-8") as decisions, \
         (directory / "combat.jsonl").open("w", encoding="utf-8") as combat, \
         (directory / "daily.jsonl").open("w", encoding="utf-8") as daily:
        def record_combat(record):
            combat.write(json.dumps(record, ensure_ascii=False) + "\n")
            combat.flush()
        game.event_sink = record_combat
        def install_trace(bot):
            original_note = bot.note
            def note(hour, kind, **data):
                original_note(hour, kind, **data)
                record = bot.history[-1]
                decisions.write(json.dumps(dict(country_id=bot.country_id, **record), ensure_ascii=False) + "\n")
                events[record["kind"]] += 1
                if record["kind"] == "command":
                    events[record["operation"] + (":accepted" if record["accepted"] else ":rejected")] += 1
            bot.note = note
        for bot in game.ai_system.bots.values():
            install_trace(bot)
        for day in range(days):
            game.advance_day()
            if (day + 1) % 30 == 0 or day + 1 == days:
                audit_world(game)
                audits += 1
            snapshot = dict(day=day + 1, battles=len(game.battles), battles_started=game.battles_started,
                wars=sum(r.at_war for r in game.politics.relations.values()),
                countries=[dict(id=p.id, tiles=len(p.tiles), divisions=len(p.divisions), budget=round(p.budget),
                                training=len(game.recruitment.queues[p.id]),
                                recruited=game.recruitment.completed[p.id],
                                front=front_metrics(game, p),
                                course=game.ai_system.bots[p.id].course,
                                offensive_focus=game.ai_system.bots[p.id].offensive_focus,
                                units=[dict(id=d.id, tile=game.tile_key(d.tile), organization=round(d.organization, 2),
                                            supply=round(d.last_supply_ratio, 3), strength=round(d.strength, 2),
                                            target=game.tile_key(d.target_tile) if d.target_tile else None,
                                            movement_progress=round(d.movement_progress, 4),
                                            route=d.route_mode, moving=bool(d.path))
                                       for d in p.divisions]) for p in game.players])
            daily.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
            decisions.flush()
            daily.flush()
            if (day + 1) % 30 == 0:
                print(f"seed={seed} day={day+1}/{days} wars={snapshot['wars']} battles={snapshot['battles']}", flush=True)
    summary = dict(status="completed", seed=seed, ai_seed=seed if ai_seed is None else ai_seed,
        scenario=scenario, requested_days=days, days=game.politics.day,
        elapsed_seconds=round(time.perf_counter() - started, 3), events=dict(events), news=dict(news),
        battles_started=game.battles_started, divisions_destroyed=game.divisions_destroyed, audits_passed=audits,
        divisions_recruited=dict(game.recruitment.completed),
        countries=[dict(id=p.id, name=p.name, ruler=p.ruler_name, initial_tiles=initial[p.id], tiles=len(p.tiles),
                        divisions=len(p.divisions), budget=round(p.budget), course=game.ai_system.bots[p.id].course,
                        training=len(game.recruitment.queues[p.id]), manpower_reserve=round(p.manpower_reserve),
                        aggression=game.ai_system.bots[p.id].aggression,
                        course_candidates=game.ai_system.course_candidates(game.ai_system.bots[p.id], p) if p.tiles else {},
                        neighbors=sorted({t.owner.id for own in p.tiles for t in game.neighbor_tiles(own)
                                          if t.owner and t.owner is not p and not game.is_water_tile(t)}),
                        tasks=dict(Counter(t.status for t in game.ai_system.bots[p.id].tasks))) for p in game.players])
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--ai-seed", type=int, default=None, help="Change AI randomness without changing the world")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--countries", type=int, default=4)
    parser.add_argument("--map-size", type=int, default=32)
    parser.add_argument("--output", default="logs/simulations")
    parser.add_argument("--scenario", choices=("natural", "border-war"), default="border-war")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")
    status = 0
    for seed in args.seeds:
        print(f"scenario={args.scenario} seed={seed} (border-war is an explicit test fixture)", flush=True)
        try:
            result = run(seed, args.days, args.countries, args.map_size, args.output, args.scenario, args.ai_seed)
        except KeyboardInterrupt:
            print(f"Interrupted. Partial news, decisions and daily records: {run_directory(args.output, seed, args.ai_seed)}")
            return 130
        except Exception as error:
            path = run_directory(args.output, seed, args.ai_seed) / "error.json"
            path.write_text(json.dumps(dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()),
                                       ensure_ascii=False, indent=2), encoding="utf-8")
            path.with_name("summary.json").write_text(json.dumps(dict(status="failed", seed=seed,
                scenario=args.scenario, error=str(error)), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"seed={seed} failed: {type(error).__name__}: {error}; details: {path}", file=sys.stderr, flush=True)
            status = 1
            continue
        print(json.dumps(dict(seed=seed, days=result["days"], seconds=result["elapsed_seconds"],
                              events=result["events"]), ensure_ascii=True), flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main() or 0)
