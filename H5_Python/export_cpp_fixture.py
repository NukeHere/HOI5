"""Export a reference scenario without running any AI ticks."""
from pathlib import Path
import argparse

from headless_simulation import HeadlessGame, SimulationTile
from HexTile import HexTile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=823558)
    parser.add_argument("--size", type=int, default=50)
    parser.add_argument("--countries", type=int, default=2)
    parser.add_argument("--difficulty", type=int, choices=range(3), default=1)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "H5_CPP" / "reference-map.txt")
    args = parser.parse_args()
    game = HeadlessGame(args.seed, countries=args.countries, map_size=args.size,
                        difficulty=("Легкая", "Обычная", "Сложная")[args.difficulty])
    SimulationTile.get_color = HexTile.get_color
    target = args.output
    player = game.players[0]
    with target.open("w", encoding="utf-8") as output:
        print(game.map_size, len(game.divisions), file=output)
        print(player.capital_tile.q, player.capital_tile.r, file=output)
        metals, fuel, goods = game.player_resource_summary(player)
        print("|".join(("Player", f"Нас: {game.format_population(player.population)}",
            f"{game.format_money(player.budget)}  {game.format_money_delta(player.monthly_balance)}/мес",
            f"Металлы {game.format_resource_amount(metals)}  Топливо {game.format_resource_amount(fuel)}  "
            f"Товары {game.format_resource_amount(goods)}",
            f"Стаб: {player.stability:.0%}", f"Легит: {player.legitimacy:.0%}",
            f"Подд. войны: {player.war_support:.0%}")), file=output)
        for r in range(game.map_size):
            for q in range(game.map_size):
                tile = game.hex_lookup[q, r]
                water = game.is_water_tile(tile)
                print(tile.owner.id if tile.owner else -1, int(water), round(tile.supply_score * 100),
                      1 if water else game.effective_tile_movement_cost(tile),
                      *game.terrain_color(tile), *(tile.owner.border_color[:3] if tile.owner else (0, 0, 0)),
                      file=output)
        for division in game.divisions:
            print(division.owner.id, division.tile.q, division.tile.r, division.speed,
                  division.organization, division.max_organization,
                  game.division_template(division.template_key).get("icon", "infantry"), file=output)


if __name__ == "__main__":
    main()
