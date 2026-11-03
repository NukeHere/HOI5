import unittest

from headless_simulation import HeadlessGame


class DivisionReinforcementTests(unittest.TestCase):
    def setUp(self):
        self.game = HeadlessGame(1729, countries=2, map_size=16)
        self.division = self.game.players[0].divisions[0]
        self.player = self.division.owner
        self.division.tile = self.player.capital_tile
        self.division.tile.supply_score = 1
        self.division.battle_id = None
        self.division.supply_stock = dict(self.division.supply_capacity)
        self.player.manpower_reserve = 100_000
        for key in self.division.supply_capacity:
            self.game.add_to_stockpile_unsafe(self.player, key, 1_000_000)

    def test_full_manpower_does_not_block_strength_repairs(self):
        d = self.division
        d.manpower = d.max_manpower
        d.strength = d.max_strength * .5
        before = self.player.manpower_reserve
        self.assertGreater(self.game.replenish_division(d, 24), 0)
        self.assertEqual(self.player.manpower_reserve, before)
        self.assertEqual(d.manpower, d.max_manpower)

    def test_full_strength_does_not_block_manpower_reinforcement(self):
        d = self.division
        d.strength = d.max_strength
        d.manpower = int(d.max_manpower * .5)
        before = self.player.manpower_reserve
        stock = {key: self.game.stockpile_amount(self.player, key) for key in d.supply_capacity}
        self.game.replenish_division(d, 24)
        self.assertGreater(d.manpower, d.max_manpower * .5)
        self.assertEqual(before - self.player.manpower_reserve, d.manpower - int(d.max_manpower * .5))
        self.assertEqual(stock, {key: self.game.stockpile_amount(self.player, key) for key in d.supply_capacity})

    def test_combined_losses_can_recover_completely(self):
        d = self.division
        d.strength = d.max_strength * .5
        d.manpower = int(d.max_manpower * .7)
        for _ in range(100):
            self.game.replenish_division(d, 24)
        self.assertAlmostEqual(d.strength, d.max_strength)
        self.assertEqual(d.manpower, d.max_manpower)


if __name__ == "__main__":
    unittest.main()
