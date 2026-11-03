"""Fortification math and paid replacement of separate air-defense batteries."""


def fortification_bonus(coverage, health, supply, vehicle_share):
    level = max(0, min(1, coverage)) * max(0, min(1, health))
    logistics = .3 + .7 * max(0, min(1, supply))
    armor = max(0, min(1, vehicle_share))
    return level * logistics * (.60 * (1 - armor) + .25 * armor)


def air_defense_quote(game, unit_class):
    data = game.air_defense_class_data(unit_class)
    if not data:
        return None
    ammunition = int(data.get("ammo", 0))
    resource = "light_aa_ammo" if unit_class == "short_range_aa" else "anti_air_ammo"
    prices = {"manpads_team": 500_000, "short_range_aa": 1_200_000,
              "medium_range_sam": 2_500_000, "long_range_sam": 5_000_000, "radar_unit": 1_000_000}
    materials = dict(steel=80, construction_goods=200, electronics=40, machinery=15, vehicles=2)
    if ammunition:
        materials[resource] = ammunition
    if unit_class == "short_range_aa":
        materials["old_light_aa_artillery"] = 2
    return dict(money=prices.get(unit_class, 2_500_000), resources=materials, hours=48)


def enqueue_air_defense(game, player, unit_class):
    queues = getattr(game, "air_defense_replacements", None)
    if queues is None:
        game.air_defense_replacements = queues = {}
    if player.id in queues:
        return False, "ПВО уже производится"
    quote = air_defense_quote(game, unit_class)
    if quote is None or player.budget < quote["money"]:
        return False, "Недостаточно средств или неизвестный тип ПВО"
    if any(game.stockpile_amount(player, key) < amount for key, amount in quote["resources"].items()):
        return False, "Не хватает материалов и оснащения для ПВО"
    player.budget -= quote["money"]
    for key, amount in quote["resources"].items():
        game.consume_from_stockpile(player, key, amount)
        game.record_ai_flow(player, "consumption", key, amount)
    queues[player.id] = dict(unit_class=unit_class, remaining=quote["hours"])
    return True, "Оплачено производство ПВО: 48 часов"


def update_air_defense_replacements(game, elapsed_hours):
    queues = getattr(game, "air_defense_replacements", {})
    for country_id, project in list(queues.items()):
        project["remaining"] -= elapsed_hours
        if project["remaining"] > 0:
            continue
        player = game.player_by_id(country_id)
        sites = [t for t in player.tiles if not game.is_water_tile(t) and not game.tile_has_active_battle(t)
                 and getattr(t, "supply_score", 0) >= .25]
        if not sites:
            continue  # Paid equipment waits for a safe, supplied deployment site.
        site = max(sites, key=lambda t: getattr(t, "supply_score", 0) + (t is player.capital_tile))
        ai = getattr(game, "ai_system", None)
        bot = ai.bots.get(player.id) if ai else None
        target = ai.preparation_target(bot, player) if bot else None
        front = ai.preparation_front(player, target) if target else []
        if front:
            front_keys = {game.tile_key(t) for t in front}
            rear = {game.tile_key(n) for t in front for n in game.neighbor_tiles(t)} - front_keys
            forward_sites = [t for t in sites if game.tile_key(t) in rear]
            if forward_sites:
                site = max(forward_sites, key=lambda t: (t.supply_score,
                           -game.hex_distance(t, target.capital_tile) if target.capital_tile else 0))
        unit = game.create_air_defense_unit(player, site, project["unit_class"])
        if unit:
            queues.pop(country_id)
            game.politics.news.notice(game.politics.day, player, "air_defense_completed", "ПВО восстановлено",
                f"Новая установка {project['unit_class']} развёрнута на ({site.q}, {site.r}).")
