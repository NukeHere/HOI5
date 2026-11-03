import unittest
from types import SimpleNamespace

from news_system import NewsSystem, WORLD_TEMPLATES, FUTURE_EVENT_TEMPLATES
from politics_system import PoliticalState, PoliticsSystem


def player(pid):
    return SimpleNamespace(id=pid, name=f"Страна {pid}", budget=100_000_000,
                           population=1_000_000, monthly_balance=1_000_000,
                           tiles=[object()], is_human=pid == 0, politics=PoliticalState(),
                           legitimacy=.61, stability=.72, war_support=.5)


class NewsTests(unittest.TestCase):
    def test_batch_groups_losses_by_owner_and_preserves_total(self):
        news, a, b = NewsSystem(1), player(0), player(1)
        news.begin_notice_batch()
        news.notice(1, a, "aircraft_losses", "Потери авиации", "Потеряно 2", important=True, quantity=2)
        news.notice(1, a, "aircraft_losses", "Потери авиации", "Потеряно 3", important=True, quantity=3)
        news.notice(1, b, "aircraft_losses", "Потери авиации", "Потеряно 1")
        news.end_notice_batch()
        self.assertEqual(len(news.visible(a.id)), 1)
        self.assertEqual(news.visible(a.id)[0].title, "Потери авиации (5)")
        self.assertEqual(news.visible(a.id)[0].priority, "important")
        self.assertEqual(news.visible(b.id)[0].body, "Потеряно 1")

    def test_alert_reports_problem_once_and_reports_recovery(self):
        news, owner = NewsSystem(1), player(0)
        for day in range(10):
            news.alert(day, owner, "shortage", True, "Нехватка", "Проверьте запасы", "Запасы восстановлены")
        self.assertEqual(len(news.items), 1)
        self.assertEqual(news.items[0].priority, "important")
        news.alert(10, owner, "shortage", False, "Нехватка", "Проверьте запасы", "Запасы восстановлены")
        self.assertEqual(len(news.items), 2)
        self.assertEqual(news.items[0].priority, "regular")
        self.assertEqual(news.visible(1), [])

    def test_offer_receipt_and_rejection_are_visible_to_affected_country(self):
        a, b = player(0), player(1)
        system = PoliticsSystem([a, b])
        self.assertTrue(system.execute(0, 1, "trade")[0])
        self.assertIn("offer_received", [item.key for item in system.news.visible(1)])
        system.resolve_offer(system.pending[0], False)
        self.assertIn("offer_rejected", [item.key for item in system.news.visible(0)])

    def test_active_catalog_has_variety_without_future_crises(self):
        self.assertGreaterEqual(len(WORLD_TEMPLATES), 30)
        self.assertEqual(len(WORLD_TEMPLATES), len(set(WORLD_TEMPLATES)))
        self.assertTrue(all(template.cooldown_days >= 150 for template in WORLD_TEMPLATES.values()))
        self.assertFalse(set(WORLD_TEMPLATES) & set(FUTURE_EVENT_TEMPLATES))

    def test_battle_loss_news_uses_actual_strength_loss_and_is_local(self):
        news = NewsSystem(1)
        a, b = player(0), player(1)
        battle = SimpleNamespace(id=(1, 2), attacker=a, defender=b)
        news.record_battle_losses(10, battle, 6, 4)
        self.assertFalse(news.items)
        news.record_battle_losses(11, battle, 7, 9)
        self.assertEqual(len(news.items), 2)
        self.assertTrue(all(item.key == "battle_losses" for item in news.items))
        self.assertEqual(len(news.visible(2)), 0)
        self.assertIn("боеспособности", news.items[0].body)
        news.record_battle_losses(12, battle, 20, 20)
        self.assertEqual(len(news.items), 2)

    def test_logistics_damage_news_needs_real_threshold_crossing(self):
        news = NewsSystem(1)
        owner = player(0)
        tile = SimpleNamespace(q=3, r=7)
        self.assertIsNone(news.record_logistics_damage(10, owner, tile, "port", .9, .7))
        item = news.record_logistics_damage(10, owner, tile, "port", .7, .4)
        self.assertEqual(item.key, "logistics_damage")
        self.assertEqual(item.priority, "important")
        self.assertIsNone(news.record_logistics_damage(11, owner, tile, "port", .8, .3))
        self.assertEqual(len(news.visible(1)), 0)

    def test_visibility_priority_and_bounded_archive(self):
        news = NewsSystem(17)
        news.publish(1, "local", "Наше решение", "Описание", scope="local", country_ids=(0,))
        news.publish(1, "world", "Мировая новость", "Описание", "critical")
        self.assertEqual(len(news.visible(0)), 2)
        self.assertEqual(len(news.visible(1)), 1)
        for day in range(400):
            news.publish(day, "note", f"Сообщение {day}", "Описание")
        self.assertEqual(len(news.items), 300)
        self.assertEqual(news.items[0].title, "Сообщение 399")

    def test_oil_context_changes_chance_but_not_game_state(self):
        news = NewsSystem(17)
        baseline = news.template_chance("oil_crisis", {"oil_pressure": 1})
        stressed = news.template_chance("oil_crisis", {
            "oil_pressure": 2, "major_oil_exporter_restricted": True})
        self.assertGreater(stressed, baseline)
        self.assertIn("В будущем", WORLD_TEMPLATES["oil_crisis"].developer_note)
        item = news.trigger_template("oil_crisis", 42, {
            "oil_pressure": 2, "major_oil_exporter_restricted": True})
        self.assertIn("экспортёром", item.body)
        self.assertEqual(item.priority, "critical")

    def test_deterministic_random_news_and_cooldown(self):
        first, second = NewsSystem(921), NewsSystem(921)
        for news in (first, second):
            news.advance(1000)
        self.assertEqual([(item.day, item.key) for item in first.items],
                         [(item.day, item.key) for item in second.items])
        for key, template in WORLD_TEMPLATES.items():
            days = sorted(item.day for item in first.items if item.key == key)
            self.assertTrue(all(b - a >= template.cooldown_days for a, b in zip(days, days[1:])))
        self.assertFalse(any(item.key in FUTURE_EVENT_TEMPLATES for item in first.items))

    def test_political_news_and_no_protest_event(self):
        a, b = player(0), player(1)
        system = PoliticsSystem([a, b], news_seed=15)
        self.assertTrue(system.execute(0, 0, "support:workers", program_term="week")[0])
        self.assertEqual(system.news.visible(0)[0].key, "program_start")
        system.advance(8 * 24)
        self.assertIn("program_expired", [item.key for item in system.news.visible(0)])
        a.politics.faction_radicalization["liberals"] = .9
        a.stability = .2
        system.advance(24)
        self.assertFalse(a.politics.unrest_active)
        self.assertFalse(a.politics.crisis_flags)
        self.assertFalse(any(item.key in ("protests", "uprising") for item in system.news.items))
        self.assertTrue(system.execute(0, 1, "justify")[0])
        self.assertEqual(system.news.visible(1)[0].key, "war_justification")
        system.advance(30 * 24)
        self.assertIn("war_goal_ready", [item.key for item in system.news.visible(0)])
        self.assertNotIn("war_goal_ready", [item.key for item in system.news.visible(1)])

    def test_large_trade_headline_only_for_real_record(self):
        news = NewsSystem(3)
        a, b = player(0), player(1)
        fill = {"buyer": a, "seller": b, "resource": "oil", "amount": 100_000, "price": 60}
        self.assertIsNotNone(news.record_trade_fill(10, fill, "Нефть"))
        self.assertIsNone(news.record_trade_fill(11, fill, "Нефть"))
        self.assertEqual(news.items[0].key, "large_trade")

    def test_large_support_change_is_a_local_ticker_item(self):
        news = NewsSystem(3)
        owner = player(0)
        self.assertIsNone(news.report_support(1, owner, "liberals", "Либералы", .59))
        item = news.report_support(2, owner, "liberals", "Либералы", .49)
        self.assertEqual(item.priority, "regular")
        self.assertIn("снизилась", item.title)
        self.assertEqual(len(news.visible(1)), 0)

    def test_war_headline_reflects_alliance_without_creating_relations(self):
        a, b, c = player(0), player(1), player(2)
        system = PoliticsSystem([a, b, c])
        item = system.news.publish(0, "war", "Страна 1 объявила войну стране 2", "Описание",
                                   "critical", context={"actor": 1, "target": 2})
        self.assertEqual(len(system.relations), 0)
        self.assertEqual(system.news.headline_for(item, 0, system), item.title)
        self.assertEqual(len(system.relations), 0)
        system.relation(0, 2).treaties.add("alliance")
        self.assertIn("нашего союзника", system.news.headline_for(item, 0, system))
        warning = system.news.publish(1, "war_justification", "Подготовка войны", "Описание",
                                      "important", context={"actor": 1, "target": 2})
        self.assertIn("нашего союзника", system.news.headline_for(warning, 0, system))
        self.assertIn("дипломаты", system.news.body_for(warning, 0, system).lower())
        system.relation(0, 2).treaties.clear()
        system.relation(0, 1).treaties.add("alliance")
        self.assertIn("решение о подготовке принято", system.news.body_for(warning, 0, system))
        self.assertNotIn("демократ", system.news.body_for(item, 0, system).lower())
