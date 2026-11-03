"""Server-owned baseline country AI. Expensive reviews intentionally span game days."""

from collections import defaultdict, Counter
import math
import random

from Constants import PRODUCTION_RECIPES, SIMULATION_START_TIME, TRADE_BASE_PRICES
from simulation_core import SimulationCommand
from ai_models import BotState, CountryReport, FlowLedger, Intelligence, AITask, Review, choose_close, division_vector
from ai_regions import RegionMap
from ai_fronts import deployment_posts
from ai_supply import supply_site
from ai_air_operations import configure_air_operations, reposition_air_defense
from ai_workers import AIPlanningWorkers, regional_profiles
from defense_infrastructure import air_defense_quote, enqueue_air_defense


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
        self.workers = None
        for player in game.players:
            self.ledger.sample(player.id, 0)
            if player.is_human:
                continue
            rng = random.Random((game.world_seed if random_seed is None else random_seed) ^ (player.id * 1_000_003))
            self.bots[player.id] = BotState(player.id, rng, rng.uniform(0, 6),
                rng.uniform(6, 24), rng.uniform(12, 72), rng.uniform(24, 168))
            self.bots[player.id].aggression = rng.random()
            self.bots[player.id].air_defense_targets = dict(Counter(u.unit_class for u in player.air_defense_units))
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
        if self.workers and not self.workers.closed:
            rows = []
            for tile in player.tiles:
                key = self.game.tile_key(tile)
                if key not in self.geography.tile_region:
                    continue
                flows = defaultdict(float)
                for stage in (getattr(tile, "production_cache", {}) or {}).values():
                    for resource, amount in stage.get("outputs", {}).items():
                        flows[resource] += amount
                neighbors = self.geography.neighbors[key]
                rows.append((key, self.geography.tile_region[key], self.game.estimated_tile_population(tile) or 0,
                    getattr(tile, "supply_score", 0), self.game.effective_building_coverage_map(tile), dict(flows),
                    any(n.owner is not player and not self.game.is_water_tile(n) for n in neighbors),
                    tuple(self.game.tile_key(n) for n in neighbors if n.owner is player and not self.game.is_water_tile(n))))
            capital = self.game.tile_key(player.capital_tile) if player.capital_tile else None
            result = self.workers.request(("regions", player.id), regional_profiles, (rows, player.id, capital), self.hour)
            owned = {row[0] for row in rows}
            if result is not None and {key for profile in result.values() for key in profile["tiles"]} == owned:
                return self.profile_military(player, result)
            bot = self.bots.get(player.id)
            if bot and bot.regions and {key for profile in bot.regions.values() for key in profile["tiles"]} == owned:
                return self.profile_military(player, bot.regions)
        profiles = {key: self.geography.profile(player, tiles) for key, tiles in self.controlled(player).items()}
        return self.profile_military(player, profiles)

    def profile_military(self, player, profiles):
        lookup = {tile: key for key, profile in profiles.items() for tile in profile["tiles"]}
        for profile in profiles.values():
            profile["military"] = defaultdict(float)
        for division in player.divisions:
            region = lookup.get(self.game.tile_key(division.tile)) if division.tile else None
            if region is not None:
                for key, value in division_vector(division).items():
                    profiles[region]["military"][key] += value
        return profiles

    def close_workers(self):
        if self.workers:
            self.workers.close()
            self.workers = None

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
        for unit in target.air_defense_units:
            ammo_capacity = max(unit.ammo_capacity, int(game.air_defense_class_data(unit.unit_class).get("ammo", 0)))
            key = "light_aa_ammo" if unit.unit_class == "short_range_aa" else "anti_air_ammo"
            demand[key] += max(0, ammo_capacity - unit.ammo) + ammo_capacity
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
                    self.supply_tasks(bot, player)
                    self.defense_infrastructure_tasks(bot, player)
                    if self.preparation_target(bot, player):
                        self.prepare_for_war(bot, player)
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
        bot.course_evidence = {}
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
            bot.course_evidence[target] = dict(own_attack=own_power, enemy_attack=power,
                ratio=own_power / max(1, power), crisis=relation.crisis_level,
                treaties=sorted(relation.treaties), aggression=bot.aggression,
                war_ratio_threshold=1.15 - .25 * bot.aggression,
                observed_hour=report.military["attack"].observed_hour if report and report.military.get("attack") else None)
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
        proposal_evidence = bot.course_evidence
        fresh = self.course_candidates(bot, player)
        if "defense" in fresh or "recovery" in fresh:
            options = fresh
        else:
            bot.course_evidence = proposal_evidence
        candidates = []
        for course, (score, target) in options.items():
            score += bot.course_bias.get(course, 0)
            if course == bot.course:
                score += 10
            if self.hour - bot.course_since < 1440 and course != bot.course and course not in ("defense", "recovery"):
                score -= 20
            candidates.append((score, (course, target)))
        selection = choose_close(bot.rng, candidates)
        bot.course_decision = dict(hour=self.hour, selected=selection,
            candidates=[dict(score=score, course=value[0], target=value[1]) for score, value in candidates],
            continuity_bonus=10, early_change_penalty=20, commitment_hours=1440)
        if selection and selection != (bot.course, bot.target_id):
            bot.course, bot.target_id = selection
            bot.course_since = self.hour
            bot.note(self.hour, "course", course=bot.course, target=bot.target_id)

    def task(self, bot, kind, region_id=None, motivation="", **payload):
        active = [t for t in bot.tasks if t.status in ("planned", "blocked", "executing", "waiting_market", "waiting_offer")]
        if len(active) >= 12 or any(t.kind == kind and t.region_id == region_id and
                                  all(t.payload.get(k) == v for k, v in payload.items()) for t in active):
            return
        bot.tasks.append(AITask(self.next_task_id, kind, region_id, payload, self.hour))
        bot.tasks[-1].motivation = motivation
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
        preparing = bool(self.preparation_target(bot, player))
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
            elif stock > max(1000, required * 3) and capacity > required and not preparing:
                amount = min((stock - required * 3) * .15, capacity - required)
                trade_candidates.append((.1, key, "sell", amount))
        for score, key, mode, amount in sorted(trade_candidates, reverse=True)[:6]:
            self.task(bot, "trade", resource=key, mode=mode, amount=amount,
                motivation=f"{'Дефицит' if mode == 'buy' else 'Избыток'} {key}; полезность {score:.3f}; "
                f"нужно {report.economy[key]['required'].value:.1f}/мес, "
                f"мощность {report.economy[key]['capacity'].value:.1f}/мес, запас {report.economy[key]['stock'].value:.1f}")
        self.recruitment_tasks(bot, player, money, free)
        if bot.course == "development":
            # Neutral land uses the same capture rules as player orders; this also allows
            # initially separated countries to reach one another instead of waiting forever.
            expansion = {}
            needs = {key: max(0, values["required"].value * .5 - values["stock"].value)
                     / max(1, values["required"].value * .5)
                     for key, values in report.economy.items() if values["required"].value > 0}
            focus = game.player_by_id(bot.expansion_target) if bot.expansion_target is not None else None
            for tile in player.tiles:
                for neighbor in self.geography.neighbors.get(game.tile_key(tile), ()):
                    if neighbor.owner is None and not game.is_water_tile(neighbor):
                        key = game.tile_key(neighbor)
                        terrain = .5 + getattr(neighbor, "passability", 0)
                        agriculture = game.agriculture_score(neighbor) * .3
                        resources = {name: min(1, math.log1p(max(0, mass)) / math.log(1_000_001)) * needs.get(name, 0) * 4
                                     for name, _, mass in neighbor.resources}
                        direction = 0
                        if focus and focus.tiles:
                            direction = 8 / (1 + game.hex_distance(neighbor, focus.capital_tile))
                        score = terrain + agriculture + direction + sum(resources.values())
                        expansion[key] = dict(score=score, tile=key, terrain=terrain, agriculture=agriculture,
                            direction=direction, resources={k: v for k, v in resources.items() if v > 0})
            bot.expansion_candidates = sorted(expansion.values(), key=lambda row: -row["score"])[:12]
            bot.expansion_observed_hour = self.hour
            key = choose_close(bot.rng, [(row["score"], key) for key, row in expansion.items()])
            if key is not None and not any(t.kind == "claim" and t.status in ("planned", "blocked", "executing") for t in bot.tasks):
                row = expansion[key]
                self.task(bot, "claim", tile_key=key,
                    motivation=f"Нейтральная клетка {key}: оценка {row['score']:.2f}; "
                    f"местность {row['terrain']:.2f}, сельхоз. {row['agriculture']:.2f}, "
                    f"направление к соседу {row['direction']:.2f}, ресурсы {row['resources']}")
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
            self.task(bot, "build", region, building=building, sector=sector,
                motivation=f"Выбран дефицит {resource or 'нет, общее развитие'}; здание {building}; район {region}")
            if sector:
                self.task(bot, "specialize", region, sector=sector)

    def preparation_target(self, bot, player):
        game = self.game
        if any(game.countries_hostile(player, other) for other in game.players):
            return None
        goals = [target for actor, target in game.politics.war_goals if actor == player.id]
        target = bot.target_id if bot.target_id in goals else (min(goals) if goals else
                 bot.target_id if bot.course == "war_preparation" else None)
        other = game.player_by_id(target) if target is not None else None
        return other if other and other.tiles else None

    def military_reserve(self, player, preparing=False, extra=None):
        """Projected stock after training, including divisions already in the queue."""
        needs = defaultdict(float)
        templates = [(d.supply_capacity, d.combat_supply_use) for d in player.divisions]
        templates += [(p["template"]["supply_capacity"], p["template"]["combat_supply_use"])
                      for p in self.game.recruitment.queues[player.id]]
        if extra:
            templates.append((extra["supply_capacity"], extra["combat_supply_use"]))
        for capacity, combat_use in templates:
            for key, amount in capacity.items():
                needs[key] += amount * (.5 if preparing else .15)
            for key, amount in combat_use.items():
                needs[key] += amount * (48 if preparing else 12)
        if preparing:
            for unit in player.air_defense_units:
                key = "light_aa_ammo" if unit.unit_class == "short_range_aa" else "anti_air_ammo"
                needs[key] += max(0, unit.ammo_capacity * 2 - unit.ammo)
        return needs

    def prepare_for_war(self, bot, player):
        game = self.game
        target = self.preparation_target(bot, player)
        if target is None:
            return
        reserve = self.military_reserve(player, preparing=True)
        for contract in list(player.trade_contracts):
            key = contract["resource"]
            if contract["mode"] == "sell" and reserve.get(key, 0) > 0:
                if game.adjust_trade_contract(player, key, "sell", -contract["amount"], refresh=False):
                    self.balance_refresh.add(player.id)
        money, free = self.available(player)
        shortages = sorted(((amount - free.get(key, 0)) / amount, key, amount - free.get(key, 0))
                           for key, amount in reserve.items() if amount > max(0, free.get(key, 0)))
        for _, key, missing in reversed(shortages[-4:]):
            if not any(t.kind == "trade" and t.payload.get("resource") == key
                       and t.payload.get("mode") == "buy" and t.status in
                       ("planned", "blocked", "executing", "waiting_market") for t in bot.tasks):
                self.task(bot, "trade", resource=key, mode="buy", amount=missing,
                          motivation="Мобилизационный запас перед войной")
        self.recruitment_tasks(bot, player, money, free)
        front = self.preparation_front(player, target)
        if front:
            center = max(front, key=lambda t: (t.supply_score, -game.hex_distance(t, target.capital_tile)))
            sites = [t for t in (center, *game.neighbor_tiles(center)) if t.owner is player
                     and not game.is_water_tile(t) and t.supply_score >= .25]
            if sites:
                reposition_air_defense(game, bot, player, max(sites, key=lambda t: t.supply_score), self.hour)
        self.diplomatic_tasks(bot, player)

    def preparation_front(self, player, target):
        game = self.game
        return [tile for tile in player.tiles if not game.is_water_tile(tile)
                and any(n.owner is target and not game.is_water_tile(n) for n in game.neighbor_tiles(tile))]

    def war_preparation_blocker(self, player, target):
        game = self.game
        front = self.preparation_front(player, target)
        if not front:
            return "Нет сухопутного фронта"
        goal_day = game.politics.war_goals.get((player.id, target.id))
        if goal_day is not None and game.politics.day < goal_day + 14:
            if any(0 < project["cost"]["days"] * 24 - project["hours"] <= 14 * 24
                   for project in game.recruitment.queues[player.id]):
                return "Завершается подготовка мобилизованных дивизий"
        near = {game.tile_key(t) for tile in front for t in (tile, *game.neighbor_tiles(tile))}
        ready = [d for d in player.divisions if d.tile and game.tile_key(d.tile) in near and not d.path
                 and d.organization >= d.max_organization * .65 and game.division_supply_ratio(d) >= .25]
        if len(ready) < max(1, (len(player.divisions) + 2) // 3):
            return "Дивизии ещё не готовы на снабжаемых позициях"
        if not any(u.ammo > 0 and u.fire_range_cells > 0 and game.air_defense_unit_operational(u)
                   and any(game.hex_distance(u.tile, d.tile) <= u.fire_range_cells for d in ready)
                   for u in player.air_defense_units):
            return "Передовая ещё без действующего ПВО"
        stocks = self.military_reserve(player)
        if any(game.stockpile_amount(player, key) < amount for key, amount in stocks.items()):
            return "Недостаточно минимального запаса снабжения и боеприпасов"
        return None

    def recruitment_tasks(self, bot, player, money, free):
        service = self.game.recruitment
        if service.site(player) is None:
            return
        options = []
        for key, template in service.archetypes.items():
            cost = service.quote(template)
            if cost["money"] > money or cost["manpower"] > player.manpower_reserve:
                continue
            reserve = self.military_reserve(player, extra=template)
            coverage = min((free.get(k, 0) / max(1, reserve.get(k, 0) + cost["equipment"].get(k, 0))
                            for k in reserve.keys() | cost["equipment"].keys()), default=0)
            options.append((coverage, key))
        key = choose_close(bot.rng, [option for option in options if option[0] >= 1] or options)
        if key is None:
            return
        cost = service.quote(service.archetypes[key])
        reserve = self.military_reserve(player, extra=service.archetypes[key])
        shortages = [(n + cost["equipment"].get(k, 0) - free.get(k, 0), k)
                     for k, n in reserve.items() if free.get(k, 0) < n + cost["equipment"].get(k, 0)]
        if shortages:
            for missing, resource in sorted(shortages, reverse=True)[:4]:
                self.task(bot, "trade", resource=resource, mode="buy", amount=missing)
        else:
            self.task(bot, "recruit", key=key, batch=True, motivation="Оснащение и запас снабжения для всей армии")

    def supply_tasks(self, bot, player):
        projects = [p for p in player.construction_queue if p["building"] == "supply_depot"]
        for project in projects:
            for resource, amount in project.get("resource_costs", {}).items():
                missing = amount - project.get("resources_spent", {}).get(resource, 0) - self.game.stockpile_amount(player, resource)
                if missing > 0 and not any(t.kind == "trade" and t.payload.get("mode") == "buy"
                        and t.payload.get("resource") == resource and t.status in ("planned", "blocked", "waiting_market") for t in bot.tasks):
                    self.task(bot, "trade", resource=resource, mode="buy", amount=missing,
                              motivation="Материалы для приоритетного фронтового снабжения")
        sites = {self.game.tile_key(p["tile"]) for p in projects if p.get("project_type") != "repair"}
        critical = [d.tile for d in player.divisions if d.tile and d.tile.owner is player
                    and getattr(d.tile, "supply_score", 0) < .3]
        protected = any(not p.get("paused") and p.get("project_type") != "repair"
                        and any(self.game.hex_distance(p["tile"], tile) <= 3 for tile in critical) for p in projects)
        if len(sites) >= 2 or protected or (sites and not critical):
            return
        selected = supply_site(self, bot, player)
        if selected is None:
            bot.supply_target = None
            return
        gain, key = selected
        bot.supply_target = key
        active = [t for t in bot.tasks if t.status in ("planned", "blocked") and t.kind == "supply"]
        if active:
            return
        if len([t for t in bot.tasks if t.status in ("planned", "blocked", "executing", "waiting_market", "waiting_offer")]) >= 12:
            replace = next((t for t in bot.tasks if t.status in ("planned", "blocked") and t.kind != "supply"), None)
            if replace:
                replace.status, replace.reason = "cancelled", "Приоритет фронтового снабжения"
        before = self.next_task_id
        self.task(bot, "supply", tile_key=key,
            motivation=f"Недостаток снабжения занятых/планируемых позиций; ожидаемый взвешенный прирост {gain:.3f}")
        if self.next_task_id > before:
            task = bot.tasks.pop()
            bot.tasks.insert(0, task)
            bot.note(self.hour, "supply_plan", tile=key, expected_weighted_gain=round(gain, 3))

    def defense_infrastructure_tasks(self, bot, player):
        game = self.game
        counts = Counter(u.unit_class for u in player.air_defense_units if u.health > 0)
        queues = getattr(game, "air_defense_replacements", {})
        if player.id not in queues:
            targets = dict(bot.air_defense_targets)
            if self.preparation_target(bot, player) or any(game.countries_hostile(player, p) for p in game.players):
                targets["manpads_team"] = targets.get("manpads_team", 0) + max(1, len(player.divisions) // 6)
            choices = []
            for kind, count in targets.items():
                if counts[kind] >= count:
                    continue
                quote = air_defense_quote(game, kind)
                lacks = {key: amount - game.stockpile_amount(player, key)
                         for key, amount in quote["resources"].items() if game.stockpile_amount(player, key) < amount}
                choices.append((kind, quote, lacks))
            missing, quote, shortages = min(choices, key=lambda row: len(row[2]), default=(None, None, {}))
            if missing:
                for key, amount in shortages.items():
                    self.task(bot, "trade", resource=key, mode="buy", amount=amount, motivation="Восстановление уничтоженной ПВО")
                if not shortages and player.budget >= quote["money"] + 5_000_000:
                    active = [t for t in bot.tasks if t.status in ("planned", "blocked", "executing", "waiting_market", "waiting_offer")]
                    if len(active) >= 12:
                        expendable = next((t for t in active if t.status in ("planned", "blocked")
                                           and t.kind in ("intelligence", "specialize", "build")), None)
                        if expendable:
                            expendable.status, expendable.reason = "cancelled", "Приоритет восстановления ПВО"
                    self.task(bot, "rebuild_air_defense", unit_class=missing, motivation="Восполнение потери ПВО до исходного состава")
        if not any(game.countries_hostile(player, p) for p in game.players):
            return
        if any(p["building"] == "fortification" for p in player.construction_queue):
            return
        if any(t.kind == "build" and t.payload.get("building") == "fortification"
               and t.status in ("planned", "blocked", "executing") for t in bot.tasks):
            return
        positions = Counter(game.tile_key(d.tile) for d in player.divisions if d.tile and d.tile.owner is player)
        candidates = [t for t in player.tiles if positions[game.tile_key(t)]
            and getattr(t, "supply_score", 0) >= .25 and t.building_coverage.get("fortification", 0) < .25
            and not game.is_water_tile(t) and any(n.owner and game.countries_hostile(player, n.owner) for n in game.neighbor_tiles(t))]
        if candidates:
            tile = max(candidates, key=lambda t: positions[game.tile_key(t)] + getattr(t, "supply_score", 0))
            self.task(bot, "build", building="fortification", tile_key=game.tile_key(tile),
                      motivation="Закрепление занятой снабжаемой позиции на фронте; снабжение имеет приоритет")

    def diplomatic_tasks(self, bot, player):
        game = self.game
        wars = [p for p in game.players if game.countries_hostile(player, p)]
        if wars:
            bot.course = "defense"
            if player.budget < 0 or player.war_support < .4:
                self.task(bot, "politics", target=wars[0].id, action="peace")
        elif target := self.preparation_target(bot, player):
            action = "war" if (player.id, target.id) in game.politics.war_goals else "justify"
            if not game.politics.reason(player.id, target.id, action):
                blocker = self.war_preparation_blocker(player, target) if action == "war" else None
                if blocker:
                    bot.note(self.hour, "war_preparation", target=target.id, reason=blocker)
                    return
                self.task(bot, "politics", target=target.id, action=action,
                    motivation=f"Курс war_preparation, цель {bot.target_id}; "
                    f"оценки при выборе курса: {bot.course_evidence.get(bot.target_id, {})}; "
                    + ("цель войны подготовлена, юридические условия выполнены" if action == "war"
                       else "начинаем 30-дневное оправдание цели войны"))
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
        frontline = [r for r, p in bot.regions.items()
                     if any(n.owner and self.game.countries_hostile(player, n.owner)
                            for key in p["borders"] for n in self.geography.neighbors[key])]
        region = max(frontline or list(bot.regions), key=lambda r: bot.regions[r]["importance"])
        self.task(bot, "air", region, motivation=f"Прикрытие района {region}; приоритет боёв и вражеских целей при войне")

    def send(self, bot, operation, task=None, rationale="", **payload):
        command = SimulationCommand("ai_action", bot.country_id,
                                    dict(operation=operation, _rationale=rationale or (task.motivation if task else ""), **payload), client_id="server_ai")
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
            if task.status == "executing" and task.kind in ("build", "supply"):
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
                units = [d for d in player.divisions if d.id not in bot.resting_ids and not d.path and not d.battle_id and d.route_mode != "retreat"
                         and d.organization >= d.max_organization * .5]
                if not tile or tile.owner is not None or not units:
                    task.status, task.reason, task.retry_hour = "blocked", "Нет свободного исполнителя или нейтральной цели", self.hour + 24
                    continue
                payload["division_id"] = min(units, key=lambda d: game.hex_distance(d.tile, tile)).id
            if task.kind == "build" and "tile_key" not in payload:
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
        if ok and command.payload.get("division_id") is not None and command.payload.get("_rationale"):
            bot.last_order_reasons[command.payload["division_id"]] = command.payload["_rationale"]
        if task:
            task.reason = reason
            task.status = ("executing" if task.kind in ("build", "supply", "claim") else
                           "waiting_market" if task.kind == "trade" else "succeeded") if ok else "blocked"
            if ok and task.kind == "trade":
                task.payload["market_tick"] = self.game.simulation_server.market_tick_count
            if ok and task.kind == "politics" and any(o[0] == player.id and o[1] == task.payload["target"]
                                                      and o[2] == task.payload["action"] for o in self.game.politics.pending):
                task.status = "waiting_offer"
            if ok and task.kind in ("build", "supply"):
                task.payload["tile_key"] = tuple(command.payload["tile_key"])
                if task.kind == "supply":
                    task.payload["building"] = "supply_depot"
                tile = self.game.tile_for_key(task.payload["tile_key"])
                task.payload["target_coverage"] = self.game.queued_target_coverage(player, tile, task.payload["building"])
        bot.note(self.hour, "command", operation=command.payload["operation"], accepted=ok, reason=reason,
                 task_id=task.id if task else None, payload=dict(command.payload))
        return ok

    def apply_action(self, bot, player, payload):
        game = self.game
        operation = payload["operation"]
        if operation == "rebuild_air_defense":
            return enqueue_air_defense(game, player, payload["unit_class"])
        if operation == "supply":
            tile = game.tile_for_key(payload.get("tile_key"))
            if not tile or tile.owner is not player:
                return False, "Позиция снабжения потеряна"
            if any(p["tile"] is tile and p["building"] == "supply_depot" for p in player.construction_queue):
                return False, "На позиции уже есть проект снабжения"
            reason = game.construction_tile_block_reason(player, tile, "supply_depot")
            if reason:
                return False, reason
            cost = game.construction_cost(player, tile, "supply_depot")
            if not cost or cost["money_cost"] > max(0, player.budget - 5_000_000):
                return False, "Недостаточно денег на фронтовой склад"
            resources = {key: amount for bucket in player.resource_stockpiles.values() for key, amount in bucket.items()}
            if cost:
                for key, required in cost["resource_costs"].items():
                    if resources.get(key, 0) < required:
                        self.task(bot, "trade", resource=key, mode="buy", amount=required - resources.get(key, 0))
            ok = game.enqueue_construction(player, tile, "supply_depot", refresh=False)
            reason = "Фронтовой склад поставлен первым; деньги и материалы списываются правилами строительства" if ok else "Строительство отклонено"
            if ok:
                project = player.construction_queue.pop()
                player.construction_queue.insert(0, project)
            return ok, reason
        if operation == "recruit":
            service = game.recruitment
            key = payload.get("key")
            if key not in service.archetypes:
                return False, "Шаблон недоступен"
            cost = service.quote(service.archetypes[key])
            money, resources = self.available(player)
            existing = self.military_reserve(player)
            reserve = self.military_reserve(player, extra=service.archetypes[key])
            count = min(int(money // max(1, cost["money"])),
                        int(player.manpower_reserve // max(1, cost["manpower"])))
            for k in reserve.keys() | cost["equipment"].keys():
                current = existing.get(k, 0)
                per_division = reserve.get(k, 0) - current + cost["equipment"].get(k, 0)
                free = resources.get(k, 0) - current
                if free < 0:
                    count = 0
                elif per_division > 0:
                    count = min(count, int((free + 1e-8) / per_division))
            if count <= 0:
                return False, "Средства или оснащение зарезервированы"
            tile = service.site(player)
            started = 0
            for _ in range(count if payload.get("batch") else 1):
                ok, reason = service.enqueue(player, key, tile)
                if not ok:
                    return (True, f"Начата подготовка дивизий: {started}") if started else (False, reason)
                started += 1
            return True, f"Начата подготовка дивизий: {started}"
        if operation == "politics":
            reason = game.politics.reason(player.id, payload["target"], payload["action"],
                                         payload.get("amount"), payload.get("program_term", "ongoing"))
            if reason:
                return False, reason
            if payload["action"] == "war":
                blocker = self.war_preparation_blocker(player, game.player_by_id(payload["target"]))
                if blocker:
                    return False, blocker
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
            if mode == "sell" and self.preparation_target(bot, player):
                return False, "Экспорт приостановлен на время мобилизации"
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
            combat = any(game.countries_hostile(player, p) for p in game.players)
            # Starting aircraft are in the national stockpile, not already in wings.
            # Deploy existing equipment through the normal capacity/stock checks.
            aircraft = sorted(player.aircraft_stockpile.items(), key=lambda item: (
                -int("air_superiority" in game.aircraft_type_data(item[0]).get("allowed_missions", [])),
                -int("cas" in game.aircraft_type_data(item[0]).get("allowed_missions", [])), item[0]))
            for aircraft_type, count in aircraft:
                if len(player.air_wings) >= 2:
                    break
                allowed = game.aircraft_type_data(aircraft_type).get("allowed_missions", [])
                if not set(allowed).intersection({"air_superiority", "intercept", "patrol", "cas", "strategic_strike"}):
                    continue
                if count > 0 and not any(aircraft_type in w.aircraft_composition for w in player.air_wings):
                    game.create_air_wing_from_stockpile(player, aircraft_type, min(8, count))
            for wing in player.air_wings:
                allowed = set()
                for kind in (wing.aircraft_composition or {wing.aircraft_type: 1}):
                    allowed.update(game.aircraft_type_data(kind).get("allowed_missions", []))
                missions = [m for m in ("air_superiority", "intercept", "patrol", "cas", "strategic_strike") if m in allowed]
                if missions:
                    configure_air_operations(game, bot, player, wing, members, combat)
                    bases = [b.tile for b in player.airbases if b.owner is player
                             and game.air_wing_fits_base(wing, b.tile)[0]]
                    if bases and wing.base_tile:
                        base = min(bases, key=lambda t: game.hex_distance(t, center))
                        if game.hex_distance(base, center) + 2 < game.hex_distance(wing.base_tile, center):
                            game.rebase_air_wing(wing, base)
            game.air_asset_revision += 1
            return True, "Миссии назначены; " + reposition_air_defense(game, bot, player, center, self.hour)
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
        """Macro records regional demand; actual reachable hex posts are tactical."""
        game = self.game
        region_for = {key: region for region, profile in bot.regions.items() for key in profile["tiles"]}
        bot.assignments = {d.id: region_for.get(bot.hex_assignments.get(d.id, game.tile_key(d.tile)))
                           for d in player.divisions if d.tile}
        at_war = any(game.countries_hostile(player, other) for other in game.players)
        for profile in bot.regions.values():
            enemies = ({d.id: d for key in profile["borders"]
                        for d in self.nearby_enemies(player, game.tile_for_key(key))} if at_war else {})
            threat = sum(division_vector(d)["attack"] for d in enemies.values())
            profile["threat"] = threat
            profile["desired_defense"] = max(12, threat * 1.15) if enemies else 0

    def tactical(self, bot, player):
        game = self.game
        wars = [p for p in game.players if game.countries_hostile(player, p)]
        if not wars and self.hour < bot.next_peace_deployment:
            return
        if not wars:
            bot.next_peace_deployment = self.hour + 48
        if wars and bot.course != "defense":
            bot.course, bot.target_id, bot.course_since = "defense", wars[0].id, self.hour
            bot.note(self.hour, "emergency_course", target=wars[0].id)
        positions = self.controlled(player)
        if wars and self.hour >= bot.next_air_refresh:
            self.air_tasks(bot, player)
            bot.next_air_refresh = self.hour + 24
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
            weak = division.organization < division.max_organization * .25 or division.last_supply_ratio < .12
            trapped = len(own_exits) <= 1 and hostile_sides >= 3
            pressure_limit = (division_vector(division)["defense"] if weak else local_defense) * .8
            if enemies and (weak or trapped or threat > local_defense * 1.8) and own_exits and threat > pressure_limit:
                target = min(own_exits, key=lambda t: (len(self.nearby_enemies(player, t)), -getattr(t, "supply_score", 0)))
                self.send(bot, "withdraw", division_id=division.id, tile_key=game.tile_key(target),
                    rationale=f"Угроза обхода/истощения: атака врага {threat:.1f}, местная оборона {local_defense:.1f}; "
                    f"безопасных выходов {len(own_exits)}, слабая дивизия {weak}, окружение {trapped}")
                used.add(division.id)
            elif division.path and division.route_mode == "attack" and not division.battle_id:
                defense = sum(division_vector(d)["defense"] for d in
                              self.units_by_tile.get(game.tile_key(division.target_tile), ())
                              if game.countries_hostile(player, d.owner)) if division.target_tile else 0
                committed_attack = sum(division_vector(d)["attack"] for d in player.divisions
                                       if ((d.target_tile is division.target_tile and d.route_mode == "attack" and d.path)
                                           or (d.battle_id in game.battles and d.battle_side == "attacker"
                                               and game.battles[d.battle_id].tile is division.target_tile)))
                if weak or defense > committed_attack * 1.2:
                    self.send(bot, "move", division_id=division.id, tile_key=game.tile_key(division.tile),
                        rationale=f"Отмена атаки: слабая дивизия {weak}; оборона цели {defense:.1f}, наша атака {committed_attack:.1f}")
                    used.add(division.id)
        bot.resting_ids.intersection_update(d.id for d in player.divisions)
        for division in player.divisions:
            organization = division.organization / max(1, division.max_organization)
            if organization < .4 or division.last_supply_ratio < .12:
                bot.resting_ids.add(division.id)
            elif organization >= .8 and division.last_supply_ratio >= .25:
                bot.resting_ids.discard(division.id)
            if division.id not in bot.resting_ids or division.id in used:
                continue
            used.add(division.id)
            if division.battle_id or division.route_mode == "retreat":
                continue
            target = division.target_tile
            if (division.path and target and target.owner is player
                    and getattr(target, "supply_score", 0) >= .35 and not self.nearby_enemies(player, target)):
                continue
            sites = [t for t in player.tiles if not game.is_water_tile(t)
                     and getattr(t, "supply_score", 0) >= .35 and not self.nearby_enemies(player, t)]
            sites.sort(key=lambda t: game.hex_distance(division.tile, t) - getattr(t, "supply_score", 0))
            for tile in sites[:5]:
                if tile is division.tile:
                    if division.path:
                        self.send(bot, "move", division_id=division.id, tile_key=game.tile_key(tile), rationale="Отдых: переход на безопасную снабжаемую позицию")
                    break
                if game.find_division_path(division, tile):
                    self.send(bot, "move", division_id=division.id, tile_key=game.tile_key(tile), rationale="Отдых: восстановление организации и снабжения")
                    break
        posts, pinned = deployment_posts(self, bot, player, wars, used)
        bot.hex_assignments = posts
        region_for = {key: region for region, members in positions.items() for key in members}
        bot.assignments = {identifier: region_for.get(key) for identifier, key in posts.items()}
        # Cover every reachable front hex before adding a second or third unit
        # to a concentration. Already travelling reinforcements keep their route.
        for division in player.divisions:
            key = posts.get(division.id)
            if key is None or division.id in used or division.id in pinned:
                continue
            if division.battle_id or division.route_mode == "retreat":
                continue
            target = game.tile_for_key(key)
            if target is division.tile or division.organization < division.max_organization * .65:
                continue
            if self.send(bot, "move", division_id=division.id, tile_key=key, rationale="Назначение пограничного поста: сначала закрываем свободные участки фронта"):
                bot.last_orders[division.id] = self.hour
                used.add(division.id)
        # Use surplus guards or a lone guard covered by stationary neighbors;
        # keep the capital guarded and retain a national reserve.
        if wars:
            choices = []
            ready = [d for d in player.divisions if d.id not in used and not d.battle_id and not d.path
                     and d.route_mode != "retreat" and d.organization >= d.max_organization * .65
                     # Supply already scales attack in division_vector. Do not
                     # require near-rear-area logistics on every front hex.
                     and d.last_supply_ratio >= .12]
            targets = {game.tile_key(n) for d in ready for n in game.neighbor_tiles(d.tile)
                       if n.owner and game.countries_hostile(player, n.owner) and not game.is_water_tile(n)}
            for key in sorted(targets):
                tile = game.tile_for_key(key)
                pool = [d for d in ready if tile in game.neighbor_tiles(d.tile)]
                defense = sum(division_vector(d)["defense"] for d in self.units_by_tile.get(key, ())
                              if game.countries_hostile(player, d.owner))
                if defense > 0:
                    pool = [d for d in pool if d.last_supply_ratio >= .25]
                source_counts = defaultdict(int)
                for d in player.divisions:
                    if d.id not in used and d.tile and not d.battle_id and not d.path and d.route_mode != "retreat":
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
                        exposed = any(n is not tile and self.game.enemy_divisions_on_tile(n, player)
                                      for n in game.neighbor_tiles(d.tile))
                        if d.tile is player.capital_tile or (defense == 0 and exposed) or (defense > 0 and len(support) < 2):
                            continue
                        if support:
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
                    self.send(bot, "attack", division_id=d.id, tile_key=key, rationale="Локальная атака: допустимое соотношение сил, тыл и соседние посты прикрыты")

    def ownership_changed(self, old_owner, new_owner):
        for owner in (old_owner, new_owner):
            if owner and owner.id in self.bots:
                self.bots[owner.id].urgent = True

    def snapshot(self):
        return {bot.country_id: dict(course=bot.course, target=bot.target_id, intelligence=bot.intelligence,
                    offensive_focus=bot.offensive_focus,
                    hex_assignments=dict(bot.hex_assignments),
                    front_quotas=[dict(tile=key, count=value) for key, value in bot.front_quotas.items()],
                    resting_ids=sorted(bot.resting_ids),
                    supply_target=bot.supply_target,
                    reviews={k: dict(stage=v.stage, started=v.started_hour, next=v.next_hour) for k, v in bot.reviews.items()},
                    regions=len(bot.regions), assignments=dict(bot.assignments),
                    tasks=[dict(id=t.id, kind=t.kind, status=t.status, reason=t.reason) for t in bot.tasks],
                    history=list(bot.history)) for bot in self.bots.values()}
