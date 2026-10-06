import unittest
from dataclasses import replace
from types import SimpleNamespace

from politics_system import PoliticalState, PoliticalRules, PoliticsSystem
from market_clearing import clear_market


def player(pid, budget=100_000_000):
    return SimpleNamespace(id=pid, name=f"P{pid}", budget=budget, tiles=[object()],
                           monthly_balance=10_000_000, population=1_000_000,
                           is_human=True, politics=PoliticalState())


class PoliticsTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = player(0), player(1)
        self.system = PoliticsSystem([self.a, self.b])

    def test_aid_amount_is_conserved_and_cannot_repeat(self):
        self.assertTrue(self.system.execute(0, 1, "aid", 123_456)[0])
        self.assertEqual(self.a.budget, 100_000_000 - 123_456)
        self.assertEqual(self.a.budget + self.b.budget, 200_000_000)
        self.assertFalse(self.system.execute(0, 1, "aid", 123_456)[0])

    def test_invalid_amounts_have_no_effect(self):
        for amount in (-1, 0, 999, float("nan"), float("inf"), True, "1000", None, 10**15):
            with self.subTest(amount=amount):
                self.assertFalse(self.system.execute(0, 1, "aid", amount)[0])
                self.assertFalse(self.system.execute(0, 1, "loan", amount)[0])
        self.assertEqual(self.a.budget, 100_000_000)
        self.assertFalse(self.system.pending)

    def test_export_limits_validate_and_preserve_legacy_toggle(self):
        for invalid in (-1, 101, True, float("nan"), "50"):
            self.assertFalse(self.system.execute(0, 0, "exports", invalid)[0])
        self.assertFalse(self.system.execute(0, 0, "exports", 100)[0])
        self.assertFalse(self.a.politics.cooldowns)
        self.assertTrue(self.system.execute(0, 0, "exports", 0)[0])
        self.assertEqual(self.a.politics.export_capacity_factor, 0)
        self.system.advance(7 * 24)
        self.assertTrue(self.system.execute(0, 0, "exports")[0])
        self.assertEqual(self.a.politics.export_capacity_factor, 1)

    def test_tax_direction_shares_cooldown_and_support_is_delayed(self):
        self.assertTrue(self.system.execute(0, 0, "tax:smb:1")[0])
        self.assertFalse(self.system.execute(0, 0, "tax:smb:-1")[0])
        self.assertEqual(self.a.politics.support["smb"], .61)
        self.system.advance(24)
        self.assertLess(self.a.politics.support["smb"], .61)
        self.assertEqual(self.a.politics.support["large"], .61)

    def test_dates_follow_the_simulation_calendar(self):
        from datetime import datetime
        self.system = PoliticsSystem([self.a, self.b], start_time=datetime(2000, 2, 28))
        self.assertEqual(self.system.date_text(2), "2000-03-01")
        self.system.execute(0, 1, "mission")
        self.assertIn("2000-03-29", self.system.reason(0, 1, "mission"))
        self.assertNotIn("дня", self.system.reason(0, 1, "mission"))

    def test_social_and_faction_programs_affect_support_and_expire(self):
        from politics_system import SOCIAL_GROUPS, FACTIONS
        self.assertAlmostEqual(sum(self.a.politics.social_shares.values()), 1)
        self.assertAlmostEqual(sum(self.a.politics.faction_shares.values()), 1)
        before = self.a.politics.government_support
        for key in (*SOCIAL_GROUPS, *FACTIONS):
            self.assertTrue(self.system.execute(0, 0, f"support:{key}", program_term="month")[0])
        self.system.advance(24)
        self.assertGreater(self.a.politics.government_support, before)
        self.assertGreater(self.a.politics.support["workers"], .61)
        self.assertGreater(self.a.politics.support["nationalists"], .61)
        self.system.advance(90 * 24)
        self.assertFalse(self.a.politics.programs)
        self.assertEqual(self.system.program_expenses(self.a), 0)

    def test_program_expires_and_stops_cost(self):
        self.assertTrue(self.system.execute(0, 0, "support:smb", program_term="month")[0])
        self.assertEqual(self.system.program_expenses(self.a), 1_000_000)
        self.system.advance(90 * 24)
        self.assertEqual(self.system.program_expenses(self.a), 0)

    def test_program_duration_costs_and_partial_hour_start(self):
        from politics_system import PROGRAM_TERMS
        for term, (_, days) in PROGRAM_TERMS.items():
            with self.subTest(term=term):
                a = player(0)
                system = PoliticsSystem([a])
                system.advance(6)
                self.assertTrue(system.execute(0, 0, "support:population", program_term=term)[0])
                duration = days or 400
                system.advance(duration * 24 - 1)
                self.assertIn("population", a.politics.programs)
                system.advance(1)
                self.assertAlmostEqual(a.budget, 100_000_000 - duration / 30 * 1_000_000, places=4)
                self.assertEqual("population" in a.politics.programs, days is None)
                if days is None:
                    system.execute(0, 0, "stop:population")
                budget = a.budget
                system.advance(48)
                self.assertEqual(a.budget, budget)

    def test_support_changes_slowly_and_scales_with_conditions(self):
        self.system.execute(0, 0, "support:population")
        self.system.advance(72)
        self.assertLess(self.a.politics.support["population"] - .61, .0015)
        self.assertAlmostEqual(self.a.budget, 99_900_000, places=5)
        small_effect = self.system.rules.program_support_effect(self.a, "population")
        self.a.population = 100_000_000
        self.assertLess(self.system.rules.program_support_effect(self.a, "population"), small_effect)
        self.a.supply_summary = {"average": 0}
        self.assertEqual(self.system.rules.program_support_effect(self.a, "population"), 0)

    def test_program_not_deleted_when_funds_run_out(self):
        self.system.execute(0, 0, "support:population")
        self.a.budget = 100
        self.system.advance(72)
        self.assertIn("population", self.a.politics.programs)
        self.assertEqual(self.a.budget, 0)
        self.assertEqual(self.a.politics.program_funding["population"], 0)
        self.a.budget = 1_000_000
        self.system.advance(24)
        self.assertEqual(self.a.politics.program_funding["population"], 1)

    def test_program_term_validation_and_weekly_renewal(self):
        for term in ("bad", None, [], True):
            self.assertFalse(self.system.execute(0, 0, "support:population", program_term=term)[0])
        self.assertEqual(self.a.budget, 100_000_000)
        self.assertFalse(self.a.politics.programs)
        self.system.execute(0, 0, "support:population", program_term="week")
        self.system.advance(7 * 24)
        self.assertTrue(self.system.execute(0, 0, "support:population", program_term="week")[0])

    def test_program_batch_and_hourly_advance_match(self):
        a, b = player(0), player(0)
        one, many = PoliticsSystem([a]), PoliticsSystem([b])
        for system in (one, many):
            system.execute(0, 0, "support:workers", program_term="week")
        one.advance(9 * 24)
        for _ in range(9 * 24):
            many.advance(1)
        self.assertAlmostEqual(a.budget, b.budget, places=4)
        self.assertAlmostEqual(a.politics.support["workers"], b.politics.support["workers"])
        self.assertEqual(a.politics.programs, b.politics.programs)

    def test_diplomatic_access_and_truce(self):
        self.assertTrue(self.system.trade_allowed(0, 1))
        self.system.execute(0, 1, "embargo")
        self.assertFalse(self.system.trade_allowed(1, 0))
        self.system.advance(7 * 24)
        self.system.execute(0, 1, "embargo")
        self.system.execute(0, 1, "war")
        self.assertTrue(self.system.hostile(0, 1))
        self.assertFalse(self.system.trade_allowed(0, 1))
        self.system.execute(0, 1, "peace")
        self.system.resolve_offer(self.system.pending[0], True)
        self.assertFalse(self.system.hostile(0, 1))
        self.assertTrue(self.system.trade_allowed(0, 1))
        self.assertFalse(self.system.execute(1, 0, "war")[0])

    def test_bankrupt_country_can_propose_peace_and_cancel_program(self):
        self.system.execute(0, 0, "support:smb")
        self.system.execute(0, 1, "war")
        self.a.budget = -100
        self.assertTrue(self.system.execute(0, 1, "peace")[0])
        self.assertTrue(self.system.execute(0, 0, "stop:smb")[0])
        self.assertEqual(self.system.program_expenses(self.a), 0)

    def test_loan_requires_acceptance_and_repayment_preserves_money(self):
        self.system.execute(0, 1, "loan", 1_200_000)
        self.assertEqual(self.a.budget, 100_000_000)
        offer = self.system.pending[0]
        self.assertTrue(self.system.resolve_offer(offer, True))
        self.assertFalse(self.system.resolve_offer(offer, True))
        self.assertEqual(self.b.budget, 101_200_000)
        self.system.advance(30 * 24)
        self.assertAlmostEqual(self.system.loans[0].principal, 1_100_000)
        self.assertAlmostEqual(self.a.budget, 98_905_000)
        self.system.advance(330 * 24)
        self.assertFalse(self.system.loans)
        self.assertAlmostEqual(self.a.budget + self.b.budget, 200_000_000)
        self.assertGreater(self.a.budget, 100_000_000)

    def test_loan_revalidates_funds_and_keeps_arrears(self):
        self.system.execute(0, 1, "loan", 1_200_000)
        self.a.budget = 0
        self.assertFalse(self.system.resolve_offer(self.system.pending[0], True))
        self.assertFalse(self.system.loans)
        self.a.budget = 100_000_000
        self.system.advance(30 * 24)
        self.system.execute(0, 1, "loan", 1_200_000)
        self.system.resolve_offer(self.system.pending[0], True)
        self.b.budget = 10
        self.system.advance(30 * 24)
        self.assertEqual(self.b.budget, 0)
        self.assertEqual(self.system.loans[0].principal, 1_200_000)
        self.assertAlmostEqual(self.system.loans[0].interest_due, 4990)

    def test_rules_drive_preview_execution_and_frozen_loan_terms(self):
        class Rules(PoliticalRules):
            def quote(self, system, actor, target, action, amount):
                result = super().quote(system, actor, target, action, amount)
                return replace(result, cost=actor.population * 2, opinion_delta=17,
                               trust_delta=.12, loan_annual_rate=.09, loan_term_months=6)

        self.system.rules = Rules()
        quote = self.system.quote(0, 1, "mission")
        self.system.execute(0, 1, "mission")
        self.assertEqual(self.a.budget, 100_000_000 - quote.cost)
        relation = self.system.relation(0, 1)
        self.assertEqual(relation.opinions[1], quote.opinion_delta)
        self.assertAlmostEqual(relation.trust, .5 + quote.trust_delta)
        self.system.execute(0, 1, "loan", 1_000_000)
        self.system.rules = PoliticalRules()
        self.system.resolve_offer(self.system.pending[0], True)
        self.assertEqual(self.system.loans[0].annual_rate, .09)
        self.assertEqual(self.system.loans[0].term_months, 6)


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.players = [player(i, 1000) for i in range(3)]
        self.system = PoliticsSystem(self.players)
        self.stocks = {(0, "food"): 100, (1, "food"): 0, (2, "food"): 0}
        self.free = {0: 100, 1: 100, 2: 100}

    def order(self, pid, mode, amount):
        return dict(player=self.players[pid], resource="food", mode=mode, amount=amount)

    def clear(self, orders, external=0):
        return clear_market(orders, allowed=self.system.trade_allowed, priority=self.system.trade_priority,
                            price=lambda key: 10, external_price=lambda key, mode: 12,
                            external_supply={"food": external}, external_demand={"food": external},
                            stock=lambda p, k: self.stocks[p.id, k],
                            free_storage=lambda p, k: self.free[p.id], bucket=lambda k: "food",
                            external_access=lambda p: p.politics.external_access)

    def test_finite_supply_and_conservation(self):
        fills, remaining = self.clear([self.order(0, "sell", 50), self.order(1, "buy", 100)])
        self.assertEqual(sum(f["amount"] for f in fills), 50)
        self.assertEqual(remaining, [0, 50])
        self.assertEqual(self.players[0].budget, 1000)  # Planning is read-only.

    def test_embargo_cannot_be_bypassed_by_other_orders(self):
        self.system.relation(0, 1).embargoes.add(0)
        fills, remaining = self.clear([self.order(0, "sell", 100), self.order(1, "buy", 100)])
        self.assertFalse(fills)
        self.assertEqual(remaining, [100, 100])

    def test_allied_buyer_has_priority(self):
        self.system.relation(0, 2).treaties.add("alliance")
        fills, _ = self.clear([self.order(0, "sell", 50), self.order(1, "buy", 50), self.order(2, "buy", 50)])
        self.assertEqual(fills[0]["buyer"].id, 2)
        self.assertEqual(len(fills), 1)

    def test_external_quota_is_shared_and_access_is_checked(self):
        orders = [self.order(1, "buy", 100), self.order(2, "buy", 100)]
        fills, _ = self.clear(orders, external=50)
        self.assertEqual(sum(f["amount"] for f in fills), 50)
        self.players[1].politics.external_access = False
        fills, _ = self.clear(orders, external=50)
        self.assertEqual(fills[0]["buyer"].id, 2)

    def test_storage_and_budget_limit_transfers(self):
        self.free[1] = 3
        self.players[2].budget = 15
        fills, _ = self.clear([self.order(0, "sell", 100), self.order(1, "buy", 100), self.order(2, "buy", 100)])
        self.assertEqual([f["amount"] for f in fills], [3, 1.5])

    def test_sales_cover_existing_deficit_before_financing_purchases(self):
        self.players[0].budget = -600
        self.stocks[(0, "wood")] = 0
        self.stocks[(2, "wood")] = 10
        orders = [self.order(0, "sell", 50), self.order(1, "buy", 50),
                  dict(player=self.players[0], resource="wood", mode="buy", amount=10),
                  dict(player=self.players[2], resource="wood", mode="sell", amount=10)]
        fills, remaining = self.clear(orders)
        self.assertEqual(len(fills), 1)
        self.assertEqual(remaining[2], 10)
        self.assertEqual(self.players[0].budget, -600)
        # A smaller deficit leaves precisely enough proceeds for five units.
        self.players[0].budget = -450
        fills, remaining = self.clear(orders)
        self.assertEqual(fills[-1]["resource"], "wood")
        self.assertEqual(fills[-1]["amount"], 5)
        self.assertEqual(remaining[2], 5)


if __name__ == "__main__":
    unittest.main()
