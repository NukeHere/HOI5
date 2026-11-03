"""Small per-wing air plans using existing range, stock and combat rules."""


def reposition_air_defense(game, bot, player, center, hour):
    movable = [u for u in player.air_defense_units if game.air_defense_unit_is_movable(u) and u.health > 0]
    moving = sum(bool(u.path) for u in movable)
    limit = max(1, len(movable) // 3)
    if moving >= limit:
        return "ПВО удерживает позиции; лимит передислокации"
    for unit in movable:
        if unit.path or unit.fire_range_cells <= 0 or unit.ammo > 0 or getattr(unit.tile, "supply_score", 0) >= .35:
            continue
        sites = [tile for tile in player.tiles if not game.is_water_tile(tile)
                 and getattr(tile, "supply_score", 0) >= .35 and not game.tile_has_active_battle(tile)
                 and not any(n.owner and game.countries_hostile(player, n.owner) for n in game.neighbor_tiles(tile))]
        for site in sorted(sites, key=lambda tile: game.hex_distance(unit.tile, tile) - getattr(tile, "supply_score", 0)):
            ok, message = game.move_air_defense_unit(unit, site)
            if ok:
                bot.next_air_defense_move = hour + 24
                bot.note(hour, "air_defense_move", unit=unit.id, target=game.tile_key(site),
                         reason="Пустой БК и плохое снабжение: отвод на перезарядку")
                return message
    if hour < bot.next_air_defense_move:
        return "ПВО удерживает позиции; пауза между передислокациями"
    for unit in sorted(movable, key=lambda u: -game.hex_distance(u.tile, center)):
        coverage = max(unit.fire_range_cells, unit.radar_range_cells if unit.radar_active else 0)
        if unit.path or (unit.fire_range_cells > 0 and unit.ammo <= 0) or game.hex_distance(unit.tile, center) <= max(2, coverage - 1):
            continue
        if any((battle.attacker is player or battle.defender is player)
               and game.hex_distance(unit.tile, battle.tile) <= unit.fire_range_cells
               for battle in game.battles.values()):
            continue
        ok, message = game.move_air_defense_unit(unit, center)
        if ok:
            bot.next_air_defense_move = hour + 48
            bot.note(hour, "air_defense_move", unit=unit.id, target=game.tile_key(center),
                     reason="Переброска к району прикрытия; остальные батареи остаются на позиции", moving_limit=limit)
            return message
    return "ПВО уже прикрывает район либо занята боем/пополнением"


def configure_air_operations(game, bot, player, wing, front_members, combat):
    allowed = set()
    for kind in (wing.aircraft_composition or {wing.aircraft_type: 1}):
        allowed.update(game.aircraft_type_data(kind).get("allowed_missions", []))
    missions = [m for m in ("air_superiority", "intercept", "patrol", "cas", "strategic_strike")
                if m in allowed and (combat or m not in ("cas", "strategic_strike"))]
    if not missions:
        return
    area = set(front_members)
    for key in front_members:
        for tile in game.neighbor_tiles(game.tile_for_key(key)):
            if tile.owner and game.countries_hostile(player, tile.owner):
                area.add(game.tile_key(tile))
    support = {game.tile_key(b.tile) for b in game.battles.values()
               if b.tile and (b.attacker is player or b.defender is player)}
    support.update(game.tile_key(d.target_tile) for d in player.divisions
                   if d.target_tile and d.route_mode == "attack" and (d.path or d.battle_id))
    weights = dict(supply_depot=9, warehouse=7, fuel_storage=7, refinery=7,
                   industry=6, airbase=6, port=5, oil_gas_rig=4, mine=3)
    strategic = []
    concentrations = []
    for enemy in game.players:
        if not game.countries_hostile(player, enemy):
            continue
        for tile in enemy.tiles:
            key = game.tile_key(tile)
            units = game.enemy_divisions_on_tile(tile, player)
            if units:
                concentrations.append((len(units) * 2 + (10 if key in support else 0), key))
            value = sum(game.effective_building_coverage(tile, k, tile.building_coverage.get(k, 0)) * w
                        for k, w in weights.items())
            if value > 0:
                strategic.append((value, key))
    cas_type = game.air_wing_primary_type_for_mission(wing, "cas")
    strike_type = game.air_wing_primary_type_for_mission(wing, "strategic_strike")
    cas_keys = [key for value, key in sorted(concentrations, reverse=True)
                if cas_type and game.aircraft_type_can_reach_tile(wing.base_tile, cas_type, game.tile_for_key(key))][:12]
    strike_keys = [key for value, key in sorted(strategic, reverse=True)
                   if strike_type and game.aircraft_type_can_reach_tile(wing.base_tile, strike_type, game.tile_for_key(key))][:8]
    area.update(cas_keys)
    area.update(strike_keys)
    area.update(support)
    wing.enabled_missions = missions
    wing.mission = missions[0]
    wing.operation_area_tile_keys = sorted(area)
    wing.target_priorities = ["depot", "factory", "airbase", "infrastructure"]
    wing.risk_policy = "normal"
    wing.sortie_intensity = .65 + bot.aggression * .25
    bot.note(game.ai_system.hour, "air_plan", wing_id=wing.id, missions=missions,
             cas_targets=cas_keys, strike_targets=strike_keys, support_targets=sorted(support), risk="normal")
