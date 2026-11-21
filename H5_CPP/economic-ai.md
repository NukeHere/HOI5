# Economic AI and starting economy

The national `ProductionPlan` is the only industrial allocation input. Tile sectors are legacy UI metadata and are not changed by economic planning or completion of bot construction.

## Planning

* First initialization uses the same demand-closure solver as subsequent bot planning. Existing plans survive `rebuildEconomy`.
* End uses include settlement/population upkeep, agriculture inputs, army stocks and combat use, concrete recruitment/defense orders, air replacement, and three near-term construction projects. Construction demand is amortized over three months; deferred work over twelve. A small continuing construction/repair flow is retained.
* Twelve deterministic closure passes expand end uses through exact recipes. Supported passive extraction/refining is subtracted (an unfed nominal refinery does not hide chemical demand). Industrial requirements are converted to production power. Under scarcity, the construction-material recovery chain is reserved first; remaining end uses are blended and re-closed with a bounded capacity search. There is no accumulating power assignment. This is a bounded forecast, not an optimal production/network-flow solver.
* Inventory can stop unnecessary reserve/equipment replenishment. Recurring civilian upkeep is accounted separately. Fertilizer demand is proportional to the food gap that its optional yield bonus can actually close; a country already covered by unfertilized output does not devote scarce industry/imports to that bonus.
* Weekly forecasts execute the same production model as simulation. Construction decisions use achievable output, rather than treating all nominal industrial outputs as available. A production shortage must persist for a week before ordinary expansion; emergency food can react immediately. If nominal construction-goods output cannot cover upkeep and the reserve is shrinking, industrial expansion takes priority. This does not override a food emergency. Mining regions and sites must contain the requested resource, and zero-yield farmland is rejected.

## Trade

All weekly import targets participate in one allocation, including resources outside the first six executable task slots. Volumes, costs and free storage are bounded. Recovery credit is available only to eligible resources. Food/fuel receive weight 2, inputs of active construction weight 3, other needs weight 1.

With competing requests, each resource first receives at most half of monthly import capacity. Completed shares recycle into other unmet requests. Once competing needs are covered, remaining capacity can be borrowed. Existing contracts are reduced before increases, eliminating order-dependent occupation of the entire limit by old food contracts. Desired targets remain separate from actual allocated contracts.

Contracts are monthly rates; an immediate construction stock requirement is divided by `Market::weeklyFraction` once. Import purchases do not grant resources: normal market execution, prices, access, budget and storage still apply.

## Supply infrastructure

Undersupplied physical troop presence is remembered daily. A concentration contributes after 48 hours (24 for severe wartime shortage). Weight reflects manpower, not merely the division count. Planned front assignments and border objectives remain additional demand signals. Adequately supplied locations contribute no infrastructure demand.

Site evaluation includes terrain, a costed depot stage of up to 0.30 area (the sum of successive legal 0.05 increments), current coverage and projected coverage from already ordered, unpaused depots. Sites without construction power, legal placement or financing are excluded. The existing construction queue remains responsible for paying for work and materials.

After 60 days without progress a project is deferred, preserving paid costs and consumed materials. Deferred projects release active execution slots; they are reconsidered weekly and resume when the next work portion and outstanding payment can be supplied. The bot does not create replacement copies on the same site. Impossible geography or a closed market can still leave explicit deferred work; there is no invented resource source.

## Starting food

After normal infrastructure placement, climate-ranked owned land receives additional fields up to 0.65 area per eligible tile. Water and agricultural suitability below 0.15 are excluded. The target includes population food and a conservative allowance for consumer-goods production, with 5% margin. Calculations use field health and **unfertilized** output. Fertilizer supplies and its production chain are simulated normally; their temporary bonus is never counted toward the guaranteed base target.

Where finite suitable land cannot meet this target, generation gives one finite transition reserve (at least one month of the uncovered gap plus a quarter-month of need). Normal warehouse limits still apply. The unresolved production gap remains visible in forecasts. No recurrent food grants or unlimited fields are introduced.

## Validation tools

`--check-bot-economy` checks exact recipe closure, capacity bounds, repeated planning, legacy-sector independence, competing imports, finite field geography, zero power, and defer/resume behavior.

`--check-economic-development SEED DAYS SCENARIO SIZE COUNTRIES` runs real six-hour production/consumption/construction and weekly trading. Scenarios: `peace` suppresses wars in this diagnostic only; `war` starts a war on day 31; `scarcity` keeps external market access closed (domestic trading remains possible).

CSV reports generation time and field-balancing time, geography/climate, food stock, unfertilized output, monthly requirements, executable food/fertilizer forecast, actual cumulative civilian food delivery, completed construction projects, steel/construction recipe power, army supply, waiting days/streak and active task count. An initial or postwar food gap is reported explicitly. Counters also include actual cumulative steel/construction-goods output, effective depot area and deferred projects. Waiting streaks are not by themselves proof of deadlock: distinguish progress/completions, changed requirements and deferred projects.

## Front endurance and difficulty

Daily local observations track normalized organization changes of own units and enemies within two hexes of own troops. Enemy rear units are not sampled. Observations expire after a gap or discontinuous movement; losses and the last observed enemy recovery are smoothed/decayed.

Supply targets combine own observed organization loss, enemy observed recovery, and own known recovery at full supply. Impossible uses a 15% recovery margin and a maximum target of 0.90 (other levels cap at 0.75). Terrain places a further physical bound. Higher-pressure fronts receive more infrastructure weight even above the ordinary 0.50 supply threshold; there is still no demand when expected existing/ordered supply covers the target.

At levels 2/3, exhausted fronts also use more conservative rest thresholds (55% organization to rest, 90% organization and 40% supply to return). This uses the existing movement/retreat system and does not increase unit recovery or alter combat rules. Active battle participants do not normally regenerate organization; battle reserves recover at one quarter rate, so building infrastructure alone cannot guarantee positive net organization or victory. Composition changes, rotation and limited observation make the opponent estimate approximate.

The diagnostic accepts an optional final difficulty argument: `--check-economic-development SEED DAYS SCENARIO SIZE COUNTRIES DIFFICULTY`. It reports the maximum current front supply target alongside actual army supply.

## Strategic fortifications

Fortification planning uses hostile borders, hostile war goals, crisis/fear and own war preparations. Quiet, unthreatened peace does not trigger a country-wide fortification program.

The planner follows threatened borders into connected owned land, identifies capital approaches and a radius-one/two defensive ring when the capital is close to danger, and scores airfields, field pads, supply hubs, industry, troops, observed nearby enemy concentrations, recent breakthroughs and persistent front positions. Natural ground-defense effects and narrow land approaches affect placement. Construction on water or in active battles is excluded.

Prewar coverage targets are modest (0.15). Wartime targets rise to 0.25, or 0.35 on persistent/exhausted/breakthrough-threatened fronts. Parallel fortification projects are bounded to one before war and two during war. Successive normal 0.05 increments are bundled into a stage of at most 0.15, with exactly their accumulated normal work, resource and money costs. Existing tasks/projects prevent duplicate orders. New forts reserve a near-term execution slot behind the first two recovery projects.

The planner checks real money and construction power. Missing materials create ordinary construction-purchase requests and remain visible in the queue; the economic plan supports their manufacturing chain. The same stalled-project deferral/reconsideration applies. `--check-bot-fortifications` covers calm peace, prewar threat, airfields, capital ring, persistent front, water, duplicates and financing.

Under a severe capacity shortage, preserving upkeep alone can still leave no construction surplus. The recovery tier therefore requests 125–160% of recurring construction-goods upkeep plus a modest machinery buffer, closes its steel/chemical/raw chain, then fits the remaining end uses into the remaining power by a bounded search. This reallocates real power and can temporarily leave other civilian or military demands uncovered; it never raises physical capacity or grants products. Ordinary industry expansion is driven by those remaining shortages.

Structural input deficits are considered for construction while stocks still cover roughly three months of the gap. The import trigger remains the near-term reserve threshold. This separates anticipatory capacity work from emergency purchasing. Geography without a feasible domestic chain, military losses or a closed external market can still require expansion, domestic trade, deferral or a smaller plan; universal self-sufficiency is not asserted.

## Export income and long-term finances

Sales are planned jointly outside the purchase-task shortlist. Offers retain civilian/production reserves, military equipment, pending recruitment and active construction materials; contracts are capped again against actual stocks immediately before weekly clearing. Resources being purchased are not offered for sale. Export capacity, export restrictions, accessible buyers and current market prices remain real constraints. Surplus raw materials and finished products use the same market and credit the seller's actual treasury; no additional revenue grant is introduced.

The bot distinguishes observed sales supported by recurring native surplus from liquidation of finite opening stocks. Only sustainable receipts can support permanent payroll. Import budgets also reserve room for domestic operating costs and development. Recruitment accounts for queued personnel and reinforcement costs, destroyed units no longer incur payroll, and a peacetime structural deficit can cancel training, park aircraft or gradually demobilize safe idle divisions while returning remaining personnel/equipment. Wartime forces are not cut by this fiscal review.

Profitable extraction/refining/industrial expansion checks accessible unmet demand and spare export capacity. Optional commercial industrial recipes use at most 10% of real power after basic needs and input feasibility checks. Their recurring sales demand remains present even with large output inventories; intermediate input chains still consume ordinary power and materials. A closed market or an unprofitable chain does not justify export investment.

`--check-bot-exports` exercises protected reserves, actual budget receipts and sustainable-versus-finite income. `--check-bot-finances` covers payroll, recruitment commitments, import allocation and conserved peacetime force reduction. The development diagnostic supports up to 3650 days and reports true completed building types, new sites separately from extensions, effective production power, fiscal balances and cumulative real export/import money. Country 0 is the passive player slot; later civil-war factions are identified by origin and birth day.

A bot also protects a physical stock portion for the next execution step of one affordable project among the three active queue slots. It prefers manufacturing/refining and food recovery, then logistics. Existing goods are temporarily withheld from ordinary recipe/upkeep consumption and restored before construction; fresh production is still created only by the normal executor. The reserved goods continue to occupy warehouse capacity and ledger consumption excludes the temporary hold. This lets sub-step production accumulate instead of being consumed by upkeep every tick. The regression reproduces that batch-size deadlock and verifies progress plus material conservation over a month.

Under competing demand, the planner closes three successive tiers: the minimal construction recovery flow, recurring civilian upkeep, then additional reserves/orders/commercial sales. Each tier includes its full recipe input chain and uses only remaining real power. If even civilian upkeep cannot fit, it receives the largest feasible share above the recovery floor. A huge equipment reserve order therefore cannot dilute affordable household-goods production. This controls power assignments; unavailable physical raw materials can still reduce actual execution.

## Economic sovereignty and defense under isolation

When external access is closed, a separate weekly plan closes full civilian/standing-army/development requirements before rationing them to existing power. Finite opening stocks do not erase those structural requirements. It targets domestic extraction and refining with a 15% margin, unfertilized food with a 5% margin, and industrial power with a 15% margin. Unpaused projects contribute only their ordered additional capacity; sites already ordered are not duplicated. One active industrial expansion can accompany extraction, with at most two outstanding industrial projects including deferred work. Other optional development waits while essential self-reliance work is infeasible.

Missing minerals with legal domestic sites create exact-site extraction tasks. The classifier and mine-placement rule now include quartz, potash and rare earths (and other generated solid minerals), which legacy mine rules omitted. If usable domestic sites are absent, a land BFS finds a neutral corridor to a deposit, and expansion takes its next border cell. Deposits inside bordering non-allied countries can become resource war objectives when no neutral resource route is selected. Existing diplomatic legality, war preparation, readiness and coalition checks still apply; hostile resource approaches receive additional front priority. No territory or resource is granted by the planner.

A closed market also permits a modest precautionary screen against non-allied neighbors. While power/raw chains are incomplete, ordinary fortification stages are limited to 0.05 and the total non-emergency screen to 0.05 per strategic region. Executing a non-emergency fort retains cash/materials for one ordinary 0.05 industry stage and one 0.05 mine stage, in addition to existing queue reservations. Optional air-defense replacement also waits during recovery. A threatened capital, a recent local breakthrough or locally superior hostile presence restores normal emergency fortification rules. Thus isolation does not disable defense, but routine fortification cannot consume the last industrial recovery batch.

`--check-bot-sovereignty` checks structural dependence despite a large opening stock, a two-step neutral deposit route, exact-site extraction, duplicate prevention, industrial expansion, pure quartz mine placement, foreign deposit targeting, protected economic materials and emergency defense override, plus clearing the isolation plan on market reopening.
