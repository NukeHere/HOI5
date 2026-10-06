"""Relative strategic indicators, not a prediction of battle outcomes."""

POWER_WEIGHTS = {"economy": 0.4, "military": 0.4, "society": 0.2}


def power_components(player):
    income = player.monthly_income_breakdown or {}
    economy = max(0, income.get("population", 0)) + max(0, income.get("companies", 0))
    military = 0.0
    for division in player.divisions:
        readiness = max(0, min(1, division.organization / max(1, division.max_organization)))
        strength = max(0, min(1, division.strength / max(1, division.max_strength)))
        supply = max(0, min(1, division.last_supply_ratio))
        equipment = division.soft_attack + division.hard_front_attack + division.hard_top_attack + division.defense
        military += max(0, division.manpower) * max(0, equipment) * strength * (0.25 + 0.75 * readiness) * supply
    cohesion = (player.stability + player.legitimacy + player.politics.government_support) / 3
    society = max(0, player.population or 0) * max(0, min(1, cohesion))
    return {"economy": economy, "military": military, "society": society}


def power_ranking(players):
    components = {player.id: power_components(player) for player in players}
    maxima = {key: max((values[key] for values in components.values()), default=0) for key in POWER_WEIGHTS}
    result = {}
    for country_id, values in components.items():
        indices = {key: 100 * value / maxima[key] if maxima[key] else 0 for key, value in values.items()}
        result[country_id] = {**indices, "total": sum(indices[key] * weight for key, weight in POWER_WEIGHTS.items())}
    for values in result.values():
        values["rank"] = 1 + sum(other["total"] > values["total"] for other in result.values())
    return result


def relative_power(target, own):
    if target == own == 0:
        return "Сопоставимая мощь"
    ratio = target / own if own > 0 else float("inf")
    if ratio >= 1.5:
        return "Значительно сильнее нас"
    if ratio >= 1.15:
        return "Сильнее нас"
    if ratio <= 0.67:
        return "Значительно слабее нас"
    if ratio <= 0.87:
        return "Слабее нас"
    return "Сопоставимая мощь"
