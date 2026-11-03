import unittest
from types import SimpleNamespace

from country_power import power_components, power_ranking, relative_power
from politics_system import PoliticalState


def country(pid):
    division = SimpleNamespace(manpower=10000, organization=100, max_organization=100,
                               strength=100, max_strength=100, last_supply_ratio=1,
                               soft_attack=18, hard_front_attack=3, hard_top_attack=1, defense=26)
    return SimpleNamespace(id=pid, divisions=[division], population=1000000, stability=.72,
                           legitimacy=.61, politics=PoliticalState(),
                           monthly_income_breakdown={"population": 1000000, "companies": 2000000})


class PowerTests(unittest.TestCase):
    def test_equal_countries_share_rank(self):
        ratings = power_ranking([country(0), country(1)])
        self.assertEqual(ratings[0], ratings[1])
        self.assertEqual(ratings[0]["rank"], 1)

    def test_economy_population_and_readiness_change_components(self):
        a = country(0)
        before = power_components(a)
        a.monthly_income_breakdown["companies"] *= 2
        a.population *= 2
        a.divisions[0].organization = 0
        after = power_components(a)
        self.assertGreater(after["economy"], before["economy"])
        self.assertGreater(after["society"], before["society"])
        self.assertLess(after["military"], before["military"])
        a.divisions[0].last_supply_ratio = 0
        self.assertEqual(power_components(a)["military"], 0)

    def test_empty_world_and_zero_countries(self):
        self.assertEqual(power_ranking([]), {})
        a = country(0)
        a.divisions = []
        a.population = 0
        a.monthly_income_breakdown = {}
        self.assertEqual(power_ranking([a])[0]["total"], 0)
        self.assertEqual(relative_power(0, 0), "Сопоставимая мощь")
        self.assertEqual(relative_power(10, 0), "Значительно сильнее нас")
