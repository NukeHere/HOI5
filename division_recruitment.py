"""Server-owned division designs, paid training and deployment."""

from copy import deepcopy
import math

from Constants import TRADE_BASE_PRICES


class DivisionRecruitment:
    def __init__(self, game):
        self.game = game
        self.archetypes = {k: deepcopy(game.division_template(k)) for k in
                           ("basic_infantry", "tank", "motorized", "anti_tank", "anti_air")}
        self.designs = {p.id: [] for p in game.players}
        self.queues = {p.id: [] for p in game.players}
        self.next_id = 1
        self.completed = {p.id: 0 for p in game.players}
        self.message = ""

    def compose(self, composition, name="Смешанная дивизия"):
        if not isinstance(composition, dict) or any(k not in self.archetypes for k in composition):
            raise ValueError("Неизвестный тип батальона")
        if any(type(v) is not int or not 0 <= v <= 20 for v in composition.values()):
            raise ValueError("Количество батальонов должно быть целым от 0 до 20")
        parts = {k: n for k, n in composition.items() if n}
        total = sum(parts.values())
        if not 1 <= total <= 20:
            raise ValueError("В дивизии должно быть от 1 до 20 батальонов")
        result = dict(name=str(name).strip()[:48] or "Смешанная дивизия", composition=parts,
                      strength=100, speed=min(self.archetypes[k]["speed"] for k in parts),
                      icon=self.archetypes[max(parts, key=parts.get)]["icon"])
        for field in ("manpower", "front_width", "soft_attack", "defense", "breakthrough",
                      "hard_front_attack", "hard_top_attack"):
            result[field] = sum(self.archetypes[k][field] * n / 10 for k, n in parts.items())
        for field in ("organization", "organization_recovery", "initiative", "reliability", "recon",
                      "camouflage", "front_piercing", "top_piercing", "front_armor", "top_armor",
                      "infantry_share", "vehicle_share"):
            result[field] = sum(self.archetypes[k][field] * n / total for k, n in parts.items())
        for field in ("supply_capacity", "combat_supply_use"):
            result[field] = {}
            for k, n in parts.items():
                for resource, amount in self.archetypes[k][field].items():
                    result[field][resource] = result[field].get(resource, 0) + amount * n / 10
        return self.game.normalize_division_template("preview", result)

    def save_design(self, player, composition, name):
        if len(self.designs[player.id]) >= 64:
            return False, "Достигнут предел 64 шаблона"
        try:
            template = self.compose(composition, name)
        except (ValueError, TypeError) as error:
            return False, str(error)
        key = f"design-{player.id}-{len(self.designs[player.id]) + 1}"
        self.game.register_division_template(key, template)
        self.designs[player.id].append(key)
        return True, key

    def allowed(self, player, key):
        return isinstance(key, str) and (key in self.archetypes or key in self.designs[player.id])

    def quote(self, template):
        equipment = dict(template["supply_capacity"])
        money = round(template["manpower"] * 80 + sum(
            amount * TRADE_BASE_PRICES.get(k, 100) * .05 for k, amount in equipment.items()))
        days = 30 + math.ceil(template["front_width"] * .5 + template["vehicle_share"] * 20)
        return dict(money=money, manpower=template["manpower"], equipment=equipment, days=days)

    def safe_site(self, player, tile):
        return bool(tile and tile.owner is player and not self.game.is_water_tile(tile)
                    and getattr(tile, "supply_score", 0) >= .25
                    and not self.game.enemy_divisions_on_tile(tile, player)
                    and not any(self.game.enemy_divisions_on_tile(n, player) for n in self.game.neighbor_tiles(tile)))

    def site(self, player):
        candidates = [t for t in player.tiles if self.safe_site(player, t)]
        return max(candidates, key=lambda t: getattr(t, "supply_score", 0), default=None)

    def enqueue(self, player, key, tile):
        game = self.game
        if not self.allowed(player, key):
            return False, "Чужой или неизвестный шаблон"
        if not self.safe_site(player, tile):
            return False, "Нужна своя снабжаемая клетка вне боя"
        template = deepcopy(game.division_template(key))
        cost = self.quote(template)
        if player.budget < cost["money"] or player.manpower_reserve < cost["manpower"]:
            return False, "Недостаточно денег или резерва людей"
        missing = [k for k, n in cost["equipment"].items() if game.stockpile_amount(player, k) + 1e-6 < n]
        if missing:
            return False, "Не хватает: " + ", ".join(game.resource_display_name(k) for k in missing[:3])
        player.budget -= cost["money"]
        player.manpower_reserve -= cost["manpower"]
        for k, n in cost["equipment"].items():
            game.consume_from_stockpile(player, k, n)
        project = dict(id=self.next_id, key=key, template=template, cost=cost,
                       tile_key=game.tile_key(tile), manual_site=player is game.human_player,
                       hours=0., status="training")
        self.next_id += 1
        self.queues[player.id].append(project)
        game.politics.news.publish(game.politics.day, "division_training", "Начата подготовка дивизии",
            f"{player.name}: {template['name']}, {cost['manpower']} человек, срок {cost['days']} суток.",
            country_ids=(player.id,))
        return True, "Подготовка начата; люди, деньги и оснащение зарезервированы"

    def cancel(self, player, project_id):
        queue = self.queues[player.id]
        project = next((p for p in queue if p["id"] == project_id), None)
        if project is None:
            return False, "Проект не найден"
        queue.remove(project)
        cost = project["cost"]
        fraction = max(0, 1 - project["hours"] / (cost["days"] * 24))
        player.budget += cost["money"] * fraction
        player.manpower_reserve += cost["manpower"]
        for k, amount in cost["equipment"].items():
            self.game.add_to_stockpile_unsafe(player, k, amount)
        self.game.politics.news.publish(self.game.politics.day, "division_training_cancelled", "Подготовка дивизии отменена",
            f"{player.name}: {project['template']['name']}. Люди и оснащение возвращены; возврат денег {cost['money'] * fraction:.0f}.",
            country_ids=(player.id,))
        return True, "Набор отменён; люди, оснащение и неистраченные деньги возвращены"

    def update(self, hours):
        game = self.game
        for player in game.players:
            queue = self.queues[player.id]
            if not queue:
                continue
            if not player.tiles:
                for project in list(queue):
                    self.cancel(player, project["id"])
                continue
            remaining = []
            for project in queue:
                duration = project["cost"]["days"] * 24
                project["hours"] = min(duration, project["hours"] + max(0, hours))
                if project["hours"] < duration:
                    remaining.append(project)
                    continue
                tile = game.tile_for_key(project["tile_key"])
                if not self.safe_site(player, tile):
                    tile = None if project.get("manual_site") else self.site(player)
                if tile is None:
                    project["status"] = "waiting_site"
                    remaining.append(project)
                    continue
                key = f"trained-{player.id}-{project['id']}"
                game.register_division_template(key, project["template"])
                division = game.create_division_from_template(player, tile, key)
                division.organization = division.max_organization * .5
                game.register_division(division)
                self.completed[player.id] += 1
                game.politics.news.publish(game.politics.day, "division_deployed", "Дивизия завершила подготовку",
                    f"{player.name}: {project['template']['name']} развёрнута в ({tile.q}, {tile.r}).",
                    country_ids=(player.id,))
            if len(remaining) != len(queue):
                queue[:] = remaining
                game.invalidate_division_render_cache()
                game.mark_player_resource_balance_dirty(player)
                game.recalculate_monthly_balance(player, include_trade=False)

    def handle_command(self, command):
        game = self.game
        player = game.human_player
        if not player or command.player_id != player.id or command.client_id != "local":
            return False
        payload = command.payload
        if not isinstance(payload, dict):
            return False
        operation = payload.get("operation")
        if operation == "save":
            ok, message = self.save_design(player, payload.get("composition"), payload.get("name", "Дивизия"))
        elif operation in ("recruit", "relocate"):
            position = payload.get("tile_key")
            valid = (isinstance(position, (tuple, list)) and len(position) == 2
                     and all(type(v) is int for v in position))
            tile = game.tile_for_key(position) if valid else None
            if operation == "recruit":
                ok, message = self.enqueue(player, payload.get("key"), tile)
            else:
                project = next((p for p in self.queues[player.id] if p["id"] == payload.get("id")), None)
                ok = project is not None and self.safe_site(player, tile)
                if ok:
                    project["tile_key"] = game.tile_key(tile)
                    project["status"] = "training"
                message = "Гекс развёртывания изменён" if ok else "Проект или место развёртывания недоступны"
        elif operation == "cancel":
            ok, message = self.cancel(player, payload.get("id"))
        else:
            ok, message = False, "Неизвестная команда набора"
        self.message = message
        return ok
