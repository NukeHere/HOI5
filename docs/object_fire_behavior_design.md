# Division Object Fire Behavior

This note preserves the planned future layer for deliberate division fire against infrastructure and other damageable objects. It is intentionally separate from passive combat collateral damage and from aviation/munition salvos.

## Separate Settings

Do not merge these two concepts into one flag:

- `target_priority_policy` answers what the division prefers to target.
- `object_fire_behavior` answers when and how willingly the division spends combat resources on those targets.

Passive combat collateral damage still applies even when deliberate object fire is forbidden.

## object_fire_behavior

### forbidden / Запрещено

The division does not deliberately fire at infrastructure or objects.

- Attacks enemy divisions only.
- Passive collateral damage may still happen.
- Minimal extra ammunition/resource spend against objects.
- Useful when the player wants to preserve captured territory.

### conserve / Экономить

The division fires at objects only when supply conditions are good.

Conditions:

- field supplies/ammunition above roughly 50%;
- no serious supply penalty;
- organization above the accepted threshold;
- at least one target matching `target_priority_policy`.

Behavior:

- moderate object damage;
- limited supply/ammunition spend;
- stops deliberate object fire when supply/ammo drops below threshold.

### opportunistic / По возможности

The division fires at objects when a valid target exists and resources are available.

Conditions:

- at least one target matching `target_priority_policy`;
- ammunition/supplies are not empty;
- organization is not critical;
- preferably no severe supply shortage.

Behavior:

- likely default for offensive operations;
- can damage logistics, depots, defenses, air assets, industry, and city infrastructure according to priorities;
- noticeable but not maximum resource spend.

### destructive / Максимальное разрушение

The division deliberately damages objects whenever it can.

Conditions:

- usable weapons/supplies remain;
- target from priority list or any valuable target exists;
- can continue under imperfect supply unless completely impossible.

Behavior:

- increased object damage;
- increased ammunition, fuel, and/or organization spend;
- may reduce damage dealt to enemy divisions because part of combat power is diverted;
- should be an explicit player order, not the default.

## target_priority_policy Categories

This should be a list of enabled categories, not a single exclusive switch.

1. `logistics` / Снабжение
   - depots, warehouses;
   - roads, rail, bridges;
   - supply hubs later.

2. `defenses` / Оборона
   - forts, field fortifications;
   - air defense, radar;
   - hardened positions.

3. `industry` / Промышленность
   - factories;
   - power;
   - resource buildings;
   - city industry.

4. `air_and_strike_assets` / Авиация и ударные средства
   - airbase;
   - field helipad;
   - hangars;
   - aircraft on ground if spotted;
   - missile/artillery positions later.

5. `enemy_units` / Войска
   - divisions;
   - armor;
   - artillery;
   - organic division AA;
   - rear/support elements.

6. `urban_infrastructure` / Городская инфраструктура
   - city structures;
   - local infrastructure;
   - may have political/economic consequences later.

7. `command_support` / Командование и поддержка later
   - HQs;
   - communications;
   - logistics/support companies;
   - command posts.

## Future Target Selection Helper

Suggested flow:

```text
available_targets = find_damageable_targets_near_battle(division, battle_or_tile)
filtered_targets = targets matching target_priority_policy
scored_targets = score by priority, intel, value, hardness, current health, mission context
selected_target = best scored target
```

Scoring should consider:

- category order and enabled categories in `target_priority_policy`;
- visibility/global intel;
- value for current battle or logistics;
- weapon suitability against target type and hardness;
- current health, to avoid wasting fire on nearly destroyed targets;
- `object_fire_behavior`, which limits willingness and spend.

## Costs And Tradeoffs

Deliberate object fire must not be free.

Possible costs/effects:

- field supplies and ammunition spend;
- fuel spend for vehicles/artillery;
- small organization cost or slower recovery;
- part of combat power diverted from enemy divisions;
- `destructive` mode amplifies both damage and tradeoff.

## Recon And Camouflage

Global intel determines whether small/hidden objects are known at all.

Division `recon` and enemy `camouflage` affect only tactical combat targeting:

- high `recon - camouflage`: better chance to find and damage rear assets such as artillery, AA, support, and logistics;
- low/negative value: long-range fire and precise target selection become less effective, with slightly lower damage and slightly higher losses.

Do not turn division recon/camouflage into global fog of war.

## UI Plan

When UI work reaches this layer, expose two separate controls:

- `target_priority_policy`: Logistics, Defenses, Industry, Air/Strike Assets, Enemy Units, Urban Infrastructure, Command/Support later.
- `object_fire_behavior`: Forbidden, Conserve, Opportunistic, Destructive.

Storage can start on division and/or army defaults. Battle plans can inherit or override later.

Safer defaults:

- `forbidden` or `conserve` for preservation-focused behavior;
- `opportunistic` for normal offensive behavior if balance supports it;
- never `destructive` by default.
