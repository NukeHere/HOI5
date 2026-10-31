"""Server-owned baseline country AI. Expensive reviews intentionally span game days."""

from collections import defaultdict
import math
import random

from Constants import PRODUCTION_RECIPES, SIMULATION_START_TIME, TRADE_BASE_PRICES
from simulation_core import SimulationCommand
from ai_models import BotState, CountryReport, FlowLedger, Intelligence, AITask, Review, choose_close, division_vector
from ai_regions import RegionMap


class CountryAI:
    def __init__(self, game, random_seed=None):
        self.game = game
        self.enabled = True
        self.ledger = FlowLedger()
        self.intelligence = Intelligence()
        self.geography = RegionMap(game)
        self.bots = {}
        self.pending = {}
        self.next_task_id = 1
        self.units_by_tile = {}
        self.market_revision = 0
        self.balance_refresh = set()
        for player in game.players:
            self.ledger.sample(player.id, 0)
            if player.is_human:
                continue
            rng = random.Random((game.world_seed if random_seed is None else random_seed) ^ (player.id * 1_000_003))
            self.bots[player.id] = BotState(player.id, rng, rng.uniform(0, 6),
                rng.uniform(6, 24), rng.uniform(12, 72), rng.uniform(24, 168))
            self.bots[player.id].aggression = rng.random()
            targets = [other for other in game.players if other.id != player.id and other.capital_tile]
            if targets:
                self.bots[player.id].expansion_target = choose_close(rng, [
                    (1 / (1 + game.hex_distance(player.capital_tile, other.capital_tile)), other.id)
                    for other in targets], margin=.35)
        game.simulation_server.register_command_handler("ai_action", self.handle_command)
        game.politics.offer_evaluator = self.offer_response

    @property
    def hour(self):
        return (self.game.simulation_server.current_time - SIMULATION_START_TIME).total_seconds() / 3600

    def controlled(self, player):
        return self.geography.controlled(player)

    def profiles(self, player):
        profiles = {key: self.geography.profile(player, tiles) for key, tiles in self.controlled(player).items()}
        lookup = {tile: key for key, profile in profiles.items() for tile in profile["tiles"]}
        for profile in profiles.values():
            profile["military"] = defaultdict(float)
        for division in player.divisions:
            region = lookup.get(self.game.tile_key(division.tile)) if division.tile else None
            if region is not None:
                for key, value in division_vector(division).items():
                    profiles[region]["military"][key] += value
        return profiles

    def economy_report(self, bot, target):
        game = self.game
        now = self.hour
        report = bot.reports.get(target.id)
        if report is None:
            report = CountryReport(target.id, now)
            bot.reports[target.id] = report
        report.observed_hour = now
        rates, hours = self.ledger.rates(target.id, now)
        flows = defaultdict(float)
        for (kind, resource, partner), amount in rates.items():
            flows[kind, resource] += amount
        keys = set(TRADE_BASE_PRICES)
        capacity = defaultdict(float)
        demand = defaultdict(float)
        for stage in (target.production_cache or {}).values():
            for key, amount in stage.get("outputs", {}).items():
                capacity[key] += amount
            for key, amount in stage.get("inputs", {}).items():
                demand[key] += amount
        army = game.estimate_monthly_army_consumption(target)
        for key, amount in army.items():
            demand[key] += amount
        economy = {}
        for key in sorted(keys | set(capacity) | set(demand)):
            values = dict(capacity=capacity[key], required=demand[key],
                          stock=target.resource_stockpiles.get(game.resource_category_for_key(key), {}).get(key, 0))
            for kind in ("output", "consumption", "import", "export"):
                values[kind] = flows[kind, key]
            economy[key] = {name: self.intelligence.estimate(bot, target.id, "economy", key, value, now)
                            for name, value in values.items()}
        report.economy = economy
        report.finance = {key: self.intelligence.estimate(bot, target.id, "finance", key, value, now)
                          for key, value in dict(budget=target.budget,
                              income=max(0, target.monthly_income_breakdown.get("total", 0)),
                              expenses=max(0, target.monthly_expenses_breakdown.get("total", 0))).items()}
        report.finance["observed_hours"] = hours
        return report

    def military_report(self, bot, target):
        values = defaultdict(float)
        for division in target.divisions:
            for key, value in division_vector(division).items():
                values[key] += value
        values["divisions"] = len(target.divisions)
        values["aircraft"] = sum(w.ready_count for w in target.air_wings)
        values["air_defense"] = sum(u.readiness * u.health * (1 + u.fire_range_cells)
                                    for u in target.air_defense_units)
        report = bot.reports.setdefault(target.id, CountryReport(target.id, self.hour))
        report.military = {key: self.intelligence.estimate(bot, target.id, "military", key, value, self.hour)
                           for key, value in values.items()}
        return report

    def update(self, elapsed_hours):
        if not self.enabled:
            return
        game = self.game
        now = self.hour
        self.units_by_tile = defaultdict(list)
        for division in game.divisions:
            if division.tile and division.strength > 0:
                self.units_by_tile[game.tile_key(division.tile)].append(division)
        for player in game.players:
            self.ledger.sample(player.id, now)
        for bot in self.bots.values():
            player = game.player_by_id(bot.country_id)
            if not player.tiles:
                continue
            with game.profiler.measure("ai_reviews"):
                if now >= bot.next_weekly and "weekly" not in bot.reviews:
                    bot.reviews["weekly"] = Review("weekly", now, now)
                    bot.next_weekly = now + 168 + bot.rng.uniform(-12, 12)
                if now >= bot.next_monthly and "monthly" not in bot.reviews:
                    bot.reviews["monthly"] = Review("monthly", now, now)
                    bot.next_monthly = now + 720 + bot.rng.uniform(-48, 48)
                for review in list(bot.reviews.values()):
                    if now >= review.next_hour:
                        self.review_stage(bot, player, review)
            if now >= bot.next_daily or bot.urgent:
                with game.profiler.measure("ai_daily"):
                    bot.regions = self.profiles(player)
                    self.military_report(bot, player)
                    self.assign_forces(bot, player)
                    bot.next_daily = now + 24
            if now >= bot.next_micro or bot.urgent:
                with game.profiler.measure("ai_micro"):
                    self.tactical(bot, player)
                    bot.next_micro = now + 6
                    bot.urgent = False
            with game.profiler.measure("ai_tasks"):
                self.execute_tasks(bot, player)
        # All controllers evaluate first; apply their orders only after this phase.
        game.simulation_server.process_pending_commands()
        # One exact market forecast at a time, rather than one world clearing for every changed order.
        if self.balance_refresh:
            country_id = min(self.balance_refresh)
            self.balance_refresh.remove(country_id)
            game.recalculate_monthly_balance(game.player_by_id(country_id))

    def review_stage(self, bot, player, review):
        game = self.game
        now = self.hour
        batched = (review.kind == "weekly" and review.stage in (1, 2)) or (review.kind == "monthly" and review.stage == 1)
        if batched:
            cursor = review.data.get("country_cursor", 0)
            count = max(1, math.ceil(len(game.players) / 4))
            for other in game.players[cursor:cursor + count]:
                if review.kind == "weekly" and review.stage == 1:
                    self.economy_report(bot, other)
                else:
                    self.military_report(bot, other)
            cursor += count
            if cursor < len(game.players):
                review.data["country_cursor"] = cursor
                review.next_hour = now + 6
                return
            review.data.pop("country_cursor", None)
        # Each stage intentionally reads its own current date. Plans can age while being prepared.
        if review.kind == "weekly":
            if review.stage == 0:
                self.economy_report(bot, player)
                bot.regions = self.profiles(player)
            elif review.stage == 1:
                pass  # Foreign countries were sampled in small batches above.
            elif review.stage == 2:
                pass
            elif review.stage == 3:
                self.assess_dependencies(bot, player)
            elif review.stage == 4:
                self.economic_tasks(bot, player)
            elif review.stage == 5:
                self.diplomatic_tasks(bot, player)
            else:
                self.air_tasks(bot, player)
        else:
            if review.stage == 0:
                self.economy_report(bot, player)
            elif review.stage == 1:
                pass
            elif review.stage == 2:
                self.assess_dependencies(bot, player)
            elif review.stage == 3:
                bot.regions = self.profiles(player)
            elif review.stage == 4:
                bot.course_bias = {key: bot.rng.uniform(-3, 3) for key in
                                   ("development", "deterrence", "war_preparation")}
                review.data = self.course_candidates(bot, player)
            elif review.stage == 5:
                self.select_course(bot, player, review.data)
            else:
                self.diplomatic_tasks(bot, player)
        bot.note(now, "review_stage", review=review.kind, stage=review.stage)
        review.stage += 1
        review.next_hour = now + (6 if batched else 24 + bot.rng.uniform(-3, 3))
        if review.stage >= 7:
            del bot.reviews[review.kind]

    def assess_dependencies(self, bot, player):
        report = bot.reports.get(player.id)
        if not report:
            return
        rates, hours = self.ledger.rates(player.id, self.hour)
        dependencies = {}
        for (kind, resource, partner), amount in rates.items():
            if kind != "import" or partner is None or amount <= 0:
                continue
            info = report.economy.get(resource, {})
            required = info.get("required")
            stock = info.get("stock")
            dependence = amount / max(1, required.value if required else amount)
            dependencies[(partner, resource)] = dict(share=dependence,
                stock_days=30 * (stock.value if stock else 0) / max(1, amount), observed_hour=self.hour)
        bot.dependencies = dependencies
        influence = {}
        for other in self.game.players:
            if other.id == player.id:
                continue
            report = bot.reports.get(other.id)
            if not report:
                continue
            economic = 0
            for (kind, resource, partner), amount in rates.items():
                if kind == "export" and partner == other.id and resource in report.economy:
                    economic = max(economic, amount / max(1, report.economy[resource]["required"].value))
            own = bot.reports.get(player.id)
            own_attack = own.military.get("attack") if own else None
            defense = report.military.get("defense")
            relation = self.game.politics.relation(player.id, other.id)
            influence[other.id] = dict(economic=min(1, economic),
                military_ratio=(own_attack.value if own_attack else 0) / max(1, defense.value if defense else 1),
                trust=relation.trust, cultural=None, observed_hour=self.hour)
        bot.influence = influence

    def course_candidates(self, bot, player):
        game = self.game
        wars = [p.id for p in game.players if game.countries_hostile(player, p)]
        if wars:
            return {"defense": (100, wars[0])}
        if player.budget < 0 or player.politics.government_support < .4:
            return {"recovery": (100, None)}
        own = bot.reports.get(player.id)
        own_power = own.military.get("attack").value if own and own.military.get("attack") else 0
        options = {"development": (50, None)}
        neighbors = {tile.owner.id for own_tile in player.tiles for tile in game.neighbor_tiles(own_tile)
                     if tile.owner is not None and tile.owner is not player and not game.is_water_tile(tile)}
        for target in sorted(neighbors):
            other = game.player_by_id(target)
            relation = game.politics.relation(player.id, target)
            report = bot.reports.get(target)
            power = report.military.get("attack").value if report and report.military.get("attack") else own_power
            own_preparation = (player.id, target) in game.politics.war_goals
            if own_preparation and bot.course == "war_preparation" and bot.target_id == target and own_power >= power * .75:
                options["war_preparation"] = (75, target)
                continue  # Our own justification raises crisis; it isn't evidence of enemy preparation.
            if power > own_power * 1.1 or relation.crisis_level >= 25:
                options["deterrence"] = (60 + relation.crisis_level * .2, target)
            elif own_power > power * (1.15 - .25 * bot.aggression) and not relation.treaties.intersection({"alliance", "nonaggression"}):
                score = 48 + bot.aggression * 16 + min(10, (own_power / max(1, power) - 1.15) * 8)
                candidate = options.get("war_preparation", (float("-inf"), None))
                if score > candidate[0]:
                    options["war_preparation"] = (score, target)
        return options

    def select_course(self, bot, player, options):
        # Revalidate emergencies now rather than blindly publish a several-days-old proposal.
        fresh = self.course_candidates(bot, player)
        if "defense" in fresh or "recovery" in fresh:
            options = fresh
        candidates = []
        for course, (score, target) in options.items():
            score += bot.course_bias.get(course, 0)
            if course == bot.course:
                score += 10
            if self.hour - bot.course_since < 1440 and course != bot.course and course not in ("defense", "recovery"):
                score -= 20
            candidates.append((score, (course, target)))
        selection = choose_close(bot.rng, candidates)
        if selection and selection != (bot.course, bot.target_id):
            bot.course, bot.target_id = selection
            bot.course_since = self.hour
            bot.note(self.hour, "course", course=bot.course, target=bot.target_id)

    def task(self, bot, kind, region_id=None, **payload):
        active = [t for t in bot.tasks if t.status in ("planned", "blocked", "executing", "waiting_market", "waiting_offer")]
        if len(active) >= 12 or any(t.kind == kind and t.region_id == region_id and
                                  all(t.payload.get(k) == v for k, v in payload.items()) for t in active):
            return
        bot.tasks.append(AITask(self.next_task_id, kind, region_id, payload, self.hour))
        self.next_task_id += 1
        finished = [t for t in bot.tasks if t not in active and t is not bot.tasks[-1]]
        for old in finished[:max(0, len(bot.tasks) - 60)]:
            bot.tasks.remove(old)

    def available(self, player):
        money = max(0, player.budget - max(5_000_000, abs(player.monthly_balance)))
        resources = {key: amount for bucket in player.resource_stockpiles.values() for key, amount in bucket.items()}
        for project in player.construction_queue:
            if not project.get("money_paid"):
                money -= project.get("money_cost", 0)
            for key, amount in project.get("resource_costs", {}).items():
                resources[key] = resources.get(key, 0) - max(0, amount - project.get("resources_spent", {}).get(key, 0))
        return max(0, money), resources

    def economic_tasks(self, bot, player):
        game = self.game
        report = bot.reports.get(player.id)
        if not report:
            return
        money, free = self.available(player)
        shortages = []
        trade_candidates = []
        for key, data in report.economy.items():
            required = data["required"].value
            capacity = data["capacity"].value
            stock = data["stock"].value
            deficit = max(0, required - capacity)
            if required > 0 and stock < required * .5:
                score = (required * .5 - stock) / max(1, required)
                if key in ("food", "refined_fuel", "consumer_goods"):
                    score *= 2
                shortages.append((score, key))
                desired = max(deficit, required * .5 - stock)
                trade_candidates.append((score, key, "buy", desired))
            elif stock > max(1000, required * 3) and capacity > required and bot.course != "war_preparation":
                amount = min((stock - required * 3) * .15, capacity - required)
                trade_candidates.append((.1, key, "sell", amount))
        for score, key, mode, amount in sorted(trade_candidates, reverse=True)[:6]:
            self.task(bot, "trade", resource=key, mode=mode, amount=amount)
        self.recruitment_tasks(bot, player, money, free)
        if bot.course == "development":
            # Neutral land uses the same capture rules as player orders; this also allows
            # initially separated countries to reach one another instead of waiting forever.
            expansion = []
            focus = game.player_by_id(bot.expansion_target) if bot.expansion_target is not None else None
            for tile in player.tiles:
                for neighbor in self.geography.neighbors.get(game.tile_key(tile), ()):
                    if neighbor.owner is None and not game.is_water_tile(neighbor):
                        key = game.tile_key(neighbor)
                        score = .5 + getattr(neighbor, "passability", 0)
                        score += game.agriculture_score(neighbor) * .3
                        if focus and focus.tiles:
                            score += 8 / (1 + game.hex_distance(neighbor, focus.capital_tile))
                        expansion.append((score, key))
            key = choose_close(bot.rng, expansion)
            if key is not None and not any(t.kind == "claim" and t.status in ("planned", "blocked", "executing") for t in bot.tasks):
                self.task(bot, "claim", tile_key=key)
        if len(player.construction_queue) >= 4 or money <= 0:
            return
        resource = choose_close(bot.rng, shortages)
        building = "industry"
        sector = None
        if resource == "food":
            building = "farms"
        elif resource in ("oil", "natural_gas"):
            building = "oil_gas_rig"
        elif resource == "refined_fuel":
            building = "refinery"
        elif resource:
            for recipes in PRODUCTION_RECIPES.values():
                for recipe in recipes.values():
                    if resource in recipe.get("outputs", {}):
                        building = recipe.get("building", "industry")
                        sector = recipe.get("sector")
        candidates = [(p["importance"] + (10 if p["supply"] < .4 else 0), region)
                      for region, p in bot.regions.items()]
        region = choose_close(bot.rng, candidates)
        if any(game.countries_hostile(player, other) for other in game.players):
            front_regions = [(p["importance"] + 20, r) for r, p in bot.regions.items()
                             if any(n.owner and game.countries_hostile(player, n.owner)
                                    for key in p["borders"] for n in self.geography.neighbors[key])]
            if front_regions:
                region = choose_close(bot.rng, front_regions)
        if region:
            profile = bot.regions[region]
            if profile["supply"] < .55:
                building, sector = "supply_depot", None
            self.task(bot, "build", region, building=building, sector=sector)
            if sector:
                self.task(bot, "specialize", region, sector=sector)

    def recruitment_tasks(self, bot, player, money, free):
        service = self.game.recruitment
        if service.queues[player.id] or len(player.divisions) >= service.target_armies[player.id]:
            return
        if service.site(player) is None:
            return
        options = []
        for key, template in service.archetypes.items():
            cost = service.quote(template)
            if cost["money"] > money or cost["manpower"] > player.manpower_reserve:
                continue
            coverage = min((free.get(k, 0) / max(1, n) for k, n in cost["equipment"].items()), default=0)
            options.append((coverage, key))
        key = choose_close(bot.rng, options)
        if key is None:
            return
        cost = service.quote(service.archetypes[key])
        shortages = [(n - free.get(k, 0), k) for k, n in cost["equipment"].items() if free.get(k, 0) < n]
        if shortages:
            for missing, resource in sorted(shortages, reverse=True)[:4]:
                self.task(bot, "trade", resource=resource, mode="buy", amount=missing)
        else:
            self.task(bot, "recruit", key=key)

    def diplomatic_tasks(self, bot, player):
        game = self.game
        wars = [p for p in game.players if game.countries_hostile(player, p)]
        if wars:
            bot.course = "defense"
            if player.budget < 0 or player.war_support < .4:
                self.task(bot, "politics", target=wars[0].id, action="peace")
        elif bot.course == "war_preparation" and bot.target_id is not None:
            action = "war" if (player.id, bot.target_id) in game.politics.war_goals else "justify"
            if not game.politics.reason(player.id, bot.target_id, action):
                self.task(bot, "politics", target=bot.target_id, action=action)
        else:
            candidates = []
            for other in game.players:
                if other is player or not other.tiles:
                    continue
                relation = game.politics.relation(player.id, other.id)
                candidates.append((relation.opinions.get(player.id, 0) + 50, other.id))
            target = choose_close(bot.rng, candidates)
            if target is not None:
                action = "trade" if bot.dependencies else "mission"
                if not game.politics.reason(player.id, target, action):
                    self.task(bot, "politics", target=target, action=action)
        if player.budget > 10_000_000 and player.politics.government_support < .55:
            if not game.politics.reason(player.id, player.id, "support:population"):
                self.task(bot, "politics", target=player.id, action="support:population", program_term="month")
        if player.monthly_balance < 0:
            action = "tax:large:1"
            if not game.politics.reason(player.id, player.id, action):
                self.task(bot, "politics", target=player.id, action=action)
        if player.budget > 30_000_000 and bot.intelligence < .8:
            self.task(bot, "intelligence")

    def offer_response(self, system, offer):
        a, b, key, due = offer
        bot = self.bots.get(b)
        if not bot or not self.enabled:
            return system.rules.accepts(system, offer)
        if key == "peace":
            target = system.players[b]
            return target.budget < 0 or target.war_support < .45 or system.rules.accepts(system, offer)
        if bot.course == "war_preparation" and bot.target_id == a and key in ("alliance", "nonaggression", "transit"):
            return False
        return system.rules.accepts(system, offer)

    def air_tasks(self, bot, player):
        if not bot.regions:
            return
        region = max(bot.regions, key=lambda r: bot.regions[r]["importance"])
        self.task(bot, "air", region)

    def send(self, bot, operation, task=None, **payload):
        command = SimulationCommand("ai_action", bot.country_id,
                                    dict(operation=operation, **payload), client_id="server_ai")
        sequence = self.game.simulation_server.submit_command(command)
        self.pending[sequence] = (command, task)
        if task:
            task.command_id = sequence
        return sequence

    def execute_tasks(self, bot, player):
        game = self.game
        for task in list(bot.tasks):
            if task.status == "executing" and task.kind == "claim":
                tile = game.tile_for_key(task.payload["tile_key"])
                if tile and tile.owner is player:
                    task.status = "succeeded"
                elif not tile or tile.owner is not None or self.hour - task.created_hour > 168:
                    task.status, task.reason = "failed", "Цель занята или срок развёртывания истёк"
                continue
            if task.status == "waiting_offer":
                if not any(o[0] == player.id and o[1] == task.payload["target"] and o[2] == task.payload["action"]
                           for o in game.politics.pending):
                    relation = game.politics.relation(player.id, task.payload["target"])
                    action = task.payload["action"]
                    accepted = (not relation.at_war if action == "peace" else
                                game.politics.can_transit(player.id, task.payload["target"]) if action == "transit" else
                                action in relation.treaties)
                    task.status = "succeeded" if accepted else "failed"
                    task.reason = "Получен ответ на дипломатическое предложение"
                continue
            if task.status == "waiting_market":
                if self.game.simulation_server.market_tick_count > task.payload.get("market_tick", 0):
                    side = "buyer" if task.payload["mode"] == "buy" else "seller"
                    filled = sum(f["amount"] for f in game.last_market_fills
                                 if f.get(side) is player and f["resource"] == task.payload["resource"])
                    task.status = "succeeded" if filled > 0 else "failed"
                    task.reason = f"Фактически исполнено {filled:.1f}; заявка может исполняться частично"
                continue
            if task.status == "executing" and task.kind == "build":
                tile = game.tile_for_key(task.payload.get("tile_key"))
                building = task.payload["building"]
                if not tile or tile.owner is not player:
                    task.status, task.reason = "cancelled", "Район потерян"
                elif game.building_health(tile, building) > .9 and tile.building_coverage.get(building, 0) >= task.payload.get("target_coverage", 1):
                    task.status = "succeeded"
                elif not any(p["tile"] is tile and p["building"] == building for p in player.construction_queue):
                    task.status, task.reason = "failed", "Проект исчез из очереди"
                continue
            if task.status not in ("planned", "blocked") or task.command_id in self.pending or self.hour < task.retry_hour:
                continue
            if self.hour - task.created_hour > 336:
                task.status, task.reason = "cancelled", "Задача устарела"
                continue
            payload = dict(task.payload)
            if task.kind == "claim":
                tile = game.tile_for_key(payload["tile_key"])
                units = [d for d in player.divisions if not d.path and not d.battle_id and d.route_mode != "retreat"
                         and d.organization >= d.max_organization * .5]
                if not tile or tile.owner is not None or not units:
                    task.status, task.reason, task.retry_hour = "blocked", "Нет свободного исполнителя или нейтральной цели", self.hour + 24
                    continue
                payload["division_id"] = min(units, key=lambda d: game.hex_distance(d.tile, tile)).id
            if task.kind == "build":
                choices = []
                current = self.controlled(player)
                for key in current.get(task.region_id, ()):
                    tile = game.tile_for_key(key)
                    building = payload["building"]
                    if game.construction_tile_block_reason(player, tile, building):
                        continue
                    if any(p["tile"] is tile and p["building"] == building for p in player.construction_queue):
                        continue
                    cost = game.construction_cost(player, tile, building)
                    money, resources = self.available(player)
                    if cost["money_cost"] > money or any(resources.get(k, 0) < v for k, v in cost["resource_costs"].items()):
                        continue
                    score = getattr(tile, "supply_score", 0) + .3 * getattr(tile, "passability", 0)
                    if building == "supply_depot":
                        score = 2 * (1 - getattr(tile, "supply_score", 0)) + .3 * getattr(tile, "passability", 0)
                        if self.nearby_enemies(player, tile):
                            score -= 3
                    if building == "farms":
                        score += game.agriculture_score(tile)
                    choices.append((score, key))
                key = choose_close(bot.rng, choices)
                if key is None:
                    task.status, task.reason, task.retry_hour = "blocked", "Нет доступной площадки или ресурсов", self.hour + 48
                    continue
                payload["tile_key"] = key
            elif task.kind in ("specialize", "air"):
                payload["region_id"] = task.region_id
            self.send(bot, task.kind, task, **payload)
            task.retry_hour = self.hour + 24

    def handle_command(self, command):
        pending = self.pending.pop(command.sequence, None)
        if not pending or pending[0] is not command or command.player_id not in self.bots:
            return False
        task = pending[1]
        bot = self.bots[command.player_id]
        player = self.game.player_by_id(command.player_id)
        ok, reason = self.apply_action(bot, player, command.payload)
        if task:
            task.reason = reason
            task.status = ("executing" if task.kind in ("build", "claim") else
                           "waiting_market" if task.kind == "trade" else "succeeded") if ok else "blocked"
            if ok and task.kind == "trade":
                task.payload["market_tick"] = self.game.simulation_server.market_tick_count
            if ok and task.kind == "politics" and any(o[0] == player.id and o[1] == task.payload["target"]
                                                      and o[2] == task.payload["action"] for o in self.game.politics.pending):
                task.status = "waiting_offer"
            if ok and task.kind == "build":
                task.payload["tile_key"] = tuple(command.payload["tile_key"])
                tile = self.game.tile_for_key(task.payload["tile_key"])
                task.payload["target_coverage"] = self.game.queued_target_coverage(player, tile, task.payload["building"])
        bot.note(self.hour, "command", operation=command.payload["operation"], accepted=ok, reason=reason,
                 task_id=task.id if task else None, payload=dict(command.payload))
        return ok

    def apply_action(self, bot, player, payload):
        game = self.game
        operation = payload["operation"]
        if operation == "recruit":
            service = game.recruitment
            key = payload.get("key")
            if key not in service.archetypes or service.queues[player.id]:
                return False, "Подготовка уже идёт или шаблон недоступен"
            if len(player.divisions) >= service.target_armies[player.id]:
                return False, "Численность армии восстановлена"
            cost = service.quote(service.archetypes[key])
            money, resources = self.available(player)
            if money < cost["money"] or any(resources.get(k, 0) < n for k, n in cost["equipment"].items()):
                return False, "Средства или оснащение зарезервированы"
            return service.enqueue(player, key, service.site(player))
        if operation == "politics":
            reason = game.politics.reason(player.id, payload["target"], payload["action"],
                                         payload.get("amount"), payload.get("program_term", "ongoing"))
            if reason:
                return False, reason
            quote = game.politics.quote(player.id, payload["target"], payload["action"],
                                       payload.get("amount"), payload.get("program_term", "ongoing"))
            money, resources = self.available(player)
            if quote.cost > money:
                return False, "Средства зарезервированы"
            result = game.apply_country_political_action(player.id, payload, refresh=False)
            if result[0] and payload["action"] in ("trade", "alliance", "embargo", "war", "peace", "break", "external", "exports"):
                self.balance_refresh.update({player.id, payload["target"]})
            return result
        if operation == "intelligence":
            cost = 2_000_000 * (1 + bot.intelligence * 4)
            money, resources = self.available(player)
            if cost > money or bot.intelligence >= .8:
                return False, "Недостаточно средств на разведку"
            player.budget -= cost
            bot.intelligence = min(.8, bot.intelligence + .1)
            return True, "Разведка улучшена"
        if operation == "trade":
            key, mode = payload["resource"], payload["mode"]
            amount = max(0, payload["amount"])
            money, resources = self.available(player)
            if mode == "buy":
                committed = sum(c["amount"] * game.trade_unit_price(player, c["resource"], "buy")
                                for c in player.trade_contracts if c["mode"] == "buy" and c["resource"] != key)
                amount = min(amount, max(0, money * .15 - committed) / max(1, game.trade_unit_price(player, key, mode)),
                             game.storage_free_capacity_for_resource(player, key))
            else:
                report = bot.reports.get(player.id)
                data = report.economy.get(key, {}) if report else {}
                reserve = data["required"].value if "required" in data else 0
                amount = min(amount, max(0, resources.get(key, 0) - reserve) * .15)
            old = game.trade_contract_amount(player, key, mode)
            if abs(amount - old) < max(1, amount * .1):
                return True, "Заявка уже соответствует потребности"
            ok = bool(game.adjust_trade_contract(player, key, mode, amount - old, refresh=False))
            if ok:
                self.balance_refresh.add(player.id)
                game.recalculate_monthly_balance(player, include_trade=False)
            return ok, "Торговая заявка проверена"
        if operation == "build":
            tile = game.tile_for_key(payload["tile_key"])
            building = payload["building"]
            reason = game.construction_tile_block_reason(player, tile, building)
            if reason:
                return False, reason
            if any(p["tile"] is tile and p["building"] == building for p in player.construction_queue):
                return False, "Такой проект уже есть в очереди"
            cost = game.construction_cost(player, tile, building)
            money, resources = self.available(player)
            if cost["money_cost"] > money or any(resources.get(k, 0) < v for k, v in cost["resource_costs"].items()):
                return False, "Ресурсы уже заняты"
            ok = game.enqueue_construction(player, tile, building, refresh=False)
            return bool(ok), "Проект поставлен в очередь" if ok else "Строительство отклонено"
        if operation == "specialize":
            for key in self.controlled(player).get(payload["region_id"], ()):
                tile = game.tile_for_key(key)
                if tile.building_coverage.get("industry", 0) > 0:
                    tile.industry_allocation = ({"consumer_goods": 1} if payload["sector"] == "consumer_goods" else
                                                {payload["sector"]: .7, "consumer_goods": .3})
                    game.update_tile_production_cache(tile)
                    game.mark_player_resource_balance_dirty(player)
                    return True, "Специализация изменена"
            return False, "Нет промышленной площадки"
        if operation == "air":
            members = self.controlled(player).get(payload["region_id"], ())
            if not members:
                return False, "Район недоступен"
            center = game.tile_for_key(members[len(members) // 2])
            # Starting aircraft are in the national stockpile, not already in wings.
            # Deploy existing equipment through the normal capacity/stock checks.
            for aircraft_type, count in sorted(player.aircraft_stockpile.items()):
                if len(player.air_wings) >= 2:
                    break
                if count > 0 and not any(aircraft_type in w.aircraft_composition for w in player.air_wings):
                    game.create_air_wing_from_stockpile(player, aircraft_type, min(8, count))
            for wing in player.air_wings:
                allowed = set()
                for kind in (wing.aircraft_composition or {wing.aircraft_type: 1}):
                    allowed.update(game.aircraft_type_data(kind).get("allowed_missions", []))
                missions = [m for m in ("air_superiority", "intercept", "cas") if m in allowed]
                if missions:
                    wing.enabled_missions = missions
                    wing.mission = missions[0]
                    wing.operation_area_tile_keys = list(members)
            game.air_asset_revision += 1
            for unit in player.air_defense_units:
                if not unit.path and game.air_defense_unit_is_movable(unit) and game.hex_distance(unit.tile, center) > 2:
                    ok, message = game.move_air_defense_unit(unit, center)
                    if ok:
                        return True, "Миссии назначены; " + message
            return True, "Район прикрытия назначен"
        if operation in ("move", "attack", "withdraw", "claim"):
            division = game.division_by_id(payload["division_id"])
            tile = game.tile_for_key(payload["tile_key"])
            if not division or division.owner is not player or not tile or division.route_mode == "retreat":
                return False, "Исполнитель недоступен"
            if operation == "attack" and tile.owner and not game.countries_hostile(player, tile.owner):
                return False, "Цель не враждебна"
            if operation == "claim" and (tile.owner is not None or not game.division_can_capture_tile(division, tile)):
                return False, "Цель больше не нейтральна"
            if operation in ("move", "withdraw") and tile.owner is not player:
                return False, "Нужна своя позиция"
            if operation == "withdraw" and (tile not in game.neighbor_tiles(division.tile) or
                                             game.enemy_divisions_on_tile(tile, player)):
                return False, "Нет безопасной соседней позиции"
            if division.battle_id and operation != "withdraw":
                return False, "Дивизия занята боем"
            if division.path and division.target_tile is tile and operation != "withdraw":
                return True, "Приказ уже исполняется"
            if operation == "withdraw" and division.battle_id:
                game.detach_division_from_battle(division)
            if tile is division.tile:
                division.path = []
                division.target_tile = None
                return True, "Позиция удерживается"
            ok = game.issue_division_plan_order(division, tile, offensive=operation == "attack")
            if ok:
                if operation == "withdraw":
                    division.route_mode = "retreat"
                    division.organization *= .8
                game.invalidate_division_render_cache()
            return bool(ok), "Приказ выдан" if ok else "Маршрут недоступен"
        return False, "Неизвестное действие"

    def nearby_enemies(self, player, tile):
        game = self.game
        keys = [game.tile_key(tile)] + [game.tile_key(n) for n in self.geography.neighbors[game.tile_key(tile)]]
        return [d for key in keys for d in self.units_by_tile.get(key, ()) if game.countries_hostile(player, d.owner)]

    def assign_forces(self, bot, player):
        """Macro chooses districts and force quotas; tactical chooses actual hexes."""
        game = self.game
        if not bot.regions:
            bot.assignments = {}
            return
        candidates = list(player.divisions)
        assignments = {}
        requests = []
        focus_candidates = []
        for region, profile in bot.regions.items():
            enemies = {}
            hostile_border = False
            for key in profile["borders"]:
                tile = game.tile_for_key(key)
                for enemy in self.nearby_enemies(player, tile):
                    enemies[enemy.id] = enemy
                hostile_border |= any(n.owner and game.countries_hostile(player, n.owner)
                                      for n in self.geography.neighbors[key])
                if any(n.owner and game.countries_hostile(player, n.owner) for n in self.geography.neighbors[key]):
                    focus_candidates.append((max(.01, getattr(tile, "supply_score", 0)) ** 2, (region, key)))
            threat = sum(division_vector(d)["attack"] for d in enemies.values())
            profile["threat"] = threat
            profile["desired_defense"] = max(12, threat * 1.15) if hostile_border or enemies else 0
            if profile["desired_defense"]:
                requests.append((profile["importance"] + threat * 2, region))
        focus_region = None
        if bot.aggression >= .3 and len(player.divisions) >= 5 and focus_candidates:
            current = next((item for score, item in focus_candidates if item[1] == bot.offensive_focus), None)
            focus_region, bot.offensive_focus = current or choose_close(bot.rng, focus_candidates)
            average_defense = sum(division_vector(d)["defense"] for d in player.divisions) / len(player.divisions)
            bot.regions[focus_region]["desired_defense"] = max(bot.regions[focus_region]["desired_defense"], average_defense * 4)
        else:
            bot.offensive_focus = None
        reserve = max(1, len(candidates) // 5)
        for score, region in sorted(requests, reverse=True):
            profile = bot.regions[region]
            center = game.tile_for_key(profile["tiles"][0])
            total = 0
            while total < profile["desired_defense"] and len(candidates) > reserve:
                division = min(candidates, key=lambda d: game.hex_distance(d.tile, center) / max(.1, d.speed)
                               - division_vector(d)["defense"] * .1
                               - (3 if bot.assignments.get(d.id) == region else 0))
                candidates.remove(division)
                assignments[division.id] = region
                total += division_vector(division)["defense"]
        counts = defaultdict(int)
        for region in assignments.values():
            counts[region] += 1
        for index, division in enumerate(candidates):
            choices = [(profile["importance"] / (1 + counts[region]) +
                        (2 if bot.assignments.get(division.id) == region else 0), region)
                       for region, profile in bot.regions.items()]
            region = focus_region if focus_region is not None and index >= reserve else choose_close(bot.rng, choices)
            assignments[division.id] = region
            counts[region] += 1
        bot.assignments = assignments

    def tactical(self, bot, player):
        game = self.game
        wars = [p for p in game.players if game.countries_hostile(player, p)]
        if not wars and self.hour < bot.next_peace_deployment:
            return
        if not wars:
            bot.next_peace_deployment = self.hour + 48
        if wars and bot.course not in ("defense", "war_preparation"):
            bot.course, bot.target_id, bot.course_since = "defense", wars[0].id, self.hour
            bot.note(self.hour, "emergency_course", target=wars[0].id)
        borders = []
        border_regions = {}
        positions = self.controlled(player)
        for region, members in (positions.items() if wars else ()):
            profile = bot.regions.get(region, {})
            for key in profile.get("borders", members):
                tile = game.tile_for_key(key)
                enemies = self.nearby_enemies(player, tile)
                adjacent_hostile = any(n.owner and game.countries_hostile(player, n.owner) for n in self.geography.neighbors[key])
                if enemies or adjacent_hostile:
                    threat = sum(division_vector(d)["attack"] for d in enemies)
                    borders.append((threat + 2 + profile.get("importance", 0) * .15 +
                                    (100 if key == bot.offensive_focus else 0), key, threat))
                    border_regions[key] = region
        used = set()
        # First prevent immediate local traps; this path is never deferred by the weekly review.
        for division in (player.divisions if wars else ()):
            if division.route_mode == "retreat" or not division.tile:
                continue
            enemies = self.nearby_enemies(player, division.tile)
            own_exits = [n for n in game.neighbor_tiles(division.tile)
                         if n.owner is player and not game.is_water_tile(n) and not game.enemy_divisions_on_tile(n, player)]
            threat = sum(division_vector(d)["attack"] for d in enemies)
            local_defense = sum(division_vector(d)["defense"] for d in
                                self.units_by_tile.get(game.tile_key(division.tile), ()) if d.owner is player)
            hostile_sides = sum(bool(n.owner and game.countries_hostile(player, n.owner))
                                for n in game.neighbor_tiles(division.tile))
            weak = division.organization < division.max_organization * .25 or division.last_supply_ratio < .25
            trapped = len(own_exits) <= 1 and hostile_sides >= 3
            pressure_limit = (division_vector(division)["defense"] if weak else local_defense) * .8
            if enemies and (weak or trapped or threat > local_defense * 1.8) and own_exits and threat > pressure_limit:
                target = min(own_exits, key=lambda t: (len(self.nearby_enemies(player, t)), -getattr(t, "supply_score", 0)))
                self.send(bot, "withdraw", division_id=division.id, tile_key=game.tile_key(target))
                used.add(division.id)
            elif division.path and division.route_mode == "attack" and not division.battle_id:
                defense = sum(division_vector(d)["defense"] for d in
                              self.units_by_tile.get(game.tile_key(division.target_tile), ())
                              if game.countries_hostile(player, d.owner)) if division.target_tile else 0
                committed_attack = sum(division_vector(d)["attack"] for d in player.divisions
                                       if d.target_tile is division.target_tile and d.route_mode == "attack"
                                       and d.path and not d.battle_id)
                if weak or defense > committed_attack * 1.2:
                    self.send(bot, "move", division_id=division.id, tile_key=game.tile_key(division.tile))
                    used.add(division.id)
        available = [d for d in player.divisions if d.id not in used and not d.battle_id and not d.path and d.route_mode != "retreat"
                     and d.organization >= d.max_organization * .65]
        front_keys = {key for score, key, threat in borders}
        # Don't count a unit as present on two fronts, or steal the only existing guard.
        guards = {d.id for d in available if game.tile_key(d.tile) in front_keys}
        available = [d for d in available if d.id not in guards]
        # Each front position requests useful defense, not one evenly spaced division.
        assigned = defaultdict(float)
        for score, key, threat in sorted(borders, reverse=True):
            tile = game.tile_for_key(key)
            assigned[key] = sum(division_vector(d)["defense"] for d in player.divisions
                                if d.id not in used and ((d.tile is tile and d.target_tile is None) or d.target_tile is tile))
            desired = max(12, threat * 1.15)
            if key == bot.offensive_focus:
                desired = max(desired, sum(division_vector(d)["defense"] for d in player.divisions) * .4)
            while assigned[key] < desired and available:
                eligible = [d for d in available if bot.assignments.get(d.id) == border_regions[key]
                            or game.hex_distance(d.tile, tile) <= 2]
                if not eligible:
                    break
                division = min(eligible, key=lambda d: game.hex_distance(d.tile, tile) * 4
                               - division_vector(d)["defense"] * .15
                               + (10 if d.target_tile and d.target_tile is not tile else 0))
                available.remove(division)
                if division.tile is tile:
                    continue
                if self.hour - bot.last_orders.get(division.id, -1000) < 12 and division.target_tile is not None:
                    continue
                self.send(bot, "move", division_id=division.id, tile_key=key)
                bot.last_orders[division.id] = self.hour
                assigned[key] += division_vector(division)["defense"]
                used.add(division.id)
        # Use surplus guards or a lone guard covered by stationary neighbors;
        # keep the capital guarded and retain a national reserve.
        if wars:
            choices = []
            ready = [d for d in player.divisions if d.id not in used and not d.battle_id and not d.path
                     and d.route_mode != "retreat" and d.organization >= d.max_organization * .65
                     # Supply already scales attack in division_vector. Do not
                     # require near-rear-area logistics on every front hex.
                     and d.last_supply_ratio >= .25]
            targets = {game.tile_key(n) for d in ready for n in game.neighbor_tiles(d.tile)
                       if n.owner and game.countries_hostile(player, n.owner) and not game.is_water_tile(n)}
            for key in sorted(targets):
                tile = game.tile_for_key(key)
                pool = [d for d in ready if tile in game.neighbor_tiles(d.tile)]
                defense = sum(division_vector(d)["defense"] for d in self.units_by_tile.get(key, ())
                              if game.countries_hostile(player, d.owner))
                source_counts = defaultdict(int)
                for d in player.divisions:
                    if d.tile and not d.battle_id and not d.path and d.route_mode != "retreat":
                        source_counts[game.tile_key(d.tile)] += 1
                package = []
                protected = set()
                limit = min(4, max(0, len(player.divisions) - 2))
                if not limit:
                    continue
                for d in sorted(pool, key=lambda d: -division_vector(d)["attack"]):
                    source = game.tile_key(d.tile)
                    if d.id in protected:
                        continue
                    if source_counts[source] <= 1:
                        support = [other for n in game.neighbor_tiles(d.tile)
                                   for other in self.units_by_tile.get(game.tile_key(n), ())
                                   if other.owner is player and other.id not in used
                                   and all(other.id != selected.id for selected in package)
                                   and not other.path and not other.battle_id and other.route_mode != "retreat"]
                        if d.tile is player.capital_tile or len(support) < (1 if defense == 0 else 2):
                            continue
                        protected.add(support[0].id)
                    package.append(d)
                    source_counts[source] -= 1
                    if len(package) >= limit:
                        break
                attack = sum(division_vector(d)["attack"] for d in package)
                threshold = 1.05 - .15 * bot.aggression
                if package and attack > max(8, defense * threshold):
                    value = attack / max(8, defense) + .1 * (game.tile_for_key(key).building_coverage.get("industry", 0))
                    choices.append((value, (key, package)))
            selection = choose_close(bot.rng, choices)
            if selection:
                key, package = selection
                for d in package:
                    self.send(bot, "attack", division_id=d.id, tile_key=key)
        if not wars and not borders:
            # During peace hold important own districts; don't run old evenly distributed army plans.
            for division in available:
                if division.path or self.hour - bot.last_orders.get(division.id, -1000) < 48:
                    continue
                if bot.regions:
                    region = bot.assignments.get(division.id)
                    members = positions.get(region, ())
                    if members:
                        key = max(members, key=lambda k: getattr(game.tile_for_key(k), "supply_score", 0))
                        if game.tile_for_key(key) is not division.tile:
                            self.send(bot, "move", division_id=division.id, tile_key=key)
                            bot.last_orders[division.id] = self.hour

    def ownership_changed(self, old_owner, new_owner):
        for owner in (old_owner, new_owner):
            if owner and owner.id in self.bots:
                self.bots[owner.id].urgent = True

    def snapshot(self):
        return {bot.country_id: dict(course=bot.course, target=bot.target_id, intelligence=bot.intelligence,
                    offensive_focus=bot.offensive_focus,
                    reviews={k: dict(stage=v.stage, started=v.started_hour, next=v.next_hour) for k, v in bot.reviews.items()},
                    regions=len(bot.regions), assignments=dict(bot.assignments),
                    tasks=[dict(id=t.id, kind=t.kind, status=t.status, reason=t.reason) for t in bot.tasks],
                    history=list(bot.history)) for bot in self.bots.values()}
