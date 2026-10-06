# Country politics foundation

## Entry points

Click the country name in the top status bar to open your country. Select a hex
and click its owner to open another country. The Diplomacy navigation button
opens a country list; the Domestic Politics button opens your decisions. The
card's Countries button returns to the list. Tabs retain their selection across
countries. Cards use the existing animated side panel. Escape closes the card;
Space controls simulation time. Mouse wheel scrolls only when over the panel;
camera zoom, dragging and unit orders remain available on the rest of the map.
Cooldowns, offer dates, program expirations, loan payments and history use the
simulation calendar (YYYY-MM-DD), including leap years.

Aid and loan previews have an editable amount and +/- one-million steppers.
Ctrl+A or Delete clears the amount; Backspace removes a digit. Aid transfers
immediately; a loan requires acceptance. Decisions go through the existing
simulation command queue and are validated again at execution.

## State and extensible rules

`politics_system.py` contains the renderer-independent model. `PoliticalState`
belongs to `StatePlayer`. `PoliticsSystem` owns bilateral relations, offers,
active loans, and the daily political clock. History is capped at 40 events.

`PoliticalRules.quote(system, actor, target, action, amount)` is the extension
point for dynamic action costs, relationship/trust changes, cooldowns, response
times, program costs/durations, truce durations and loan terms. Its inputs
include current countries and the whole political context. Current values are
balancing placeholders, not calibrated simulation coefficients.

The UI reads `ActionQuote`; execution uses the same rules boundary. Pending
offers retain their quote, so changing rules never silently rewrites an offered
loan. Funding and diplomatic eligibility are checked again at acceptance.
`PoliticalRules.accepts` owns bot decisions, and `support_target` owns social
response. Tests replace the rules to verify this boundary.

## Implemented decisions

- Separate population, small/medium business, and large business support/taxes.
- Tax changes and temporary support programs affect the existing budget.
- Diplomatic missions, selectable aid, selectable loan offers, embargoes.
- Trade treaties, alliances, declarations of war, peace offers and termination.
- Export-volume restrictions and access to the external market.
- Daily social response, delayed bot answers, incoming human accept/reject.
- Loans with interest on remaining principal, monthly installments, partial
  payments and arrears. No automatic debt forgiveness or negative-budget payment.

Loan cash movements settle on due dates. Monthly budget forecasts include debt
service and expected receipts without settling them a second time in economy
ticks. Fixed financial months are 30 days; the initial loan terms are 12 months
at 5% annual interest. Expected receipts are not guaranteed when a debtor lacks cash.

## Market settlement

`market_clearing.py` plans transactions without mutating countries. Direct deals
require an eligible buyer AND seller; money and goods are conserved between them.
War or either country's embargo blocks direct trading in both directions.
Alliance and trade treaties establish matching priority; equal-priority country
order rotates between market executions. This is deterministic priority matching,
not an optimizer that guarantees maximal total trade across every restricted graph.

Remaining orders can use shared, finite external quotas if external access is
open. The external price uses the existing base-price spread; direct deals use
the changing market price. Bilateral embargoes do not ban trading with unrelated
external suppliers. Export restrictions reduce sell capacity and hence market
orders. Forecasts use the same clearing routine and current budgets/stocks.
The card lists actual counterparties, quantities and settlement prices.
The trade panel marks blocked contracts in red with a strike-through and a
reason; partial forecasts are yellow. Closed external access does not mark
available direct trades as blocked. Before the first market execution, demand
and supply are displayed as unknown instead of misleading zeroes. Those columns
represent the latest executed market snapshot, not a live supply guarantee.

Foreign and mixed-ownership hex selections cannot edit industrial specialization;
the mutation handler rechecks ownership independently of button visibility.

## Current abstraction boundaries

- Existing company tax income is split 65% small/medium and 35% large as an
  explicit temporary proxy. There are no individual firms yet.
- Public support uses temporary weights (85/12/3), not a demographic census.
  The public component blends general support (50%), social-group support (30%)
  and faction support (20%). Social and ideological shares are separate views of
  the same population, not additive headcounts. Initial social shares are
  workers/farmers/middle class/aristocracy 45/25/28/2%; four factions start at 25%
  each. These are tunable placeholders, not inferred census data.
  Targeted programs affect support gradually and use the existing expense,
  cooldown, cancellation and expiry rules. Taxes remain three economic categories.
- Country details expose demographic and budget data, contract forecasts and
  context-sensitive actions. Tooltips render after country and trade panels.
  Successful decisions are recorded in Events without a debug footer.
- Power indices in `country_power.py` normalize each component to the current
  world leader and combine economy/ground forces/society with weights 40/40/20.
  Tax revenue is the economic proxy; ground forces include manpower, equipment,
  strength, organization and supply. Social potential combines population with
  stability, legitimacy and government support. Ties share rank. Aircraft,
  geography and operational matchups are not included; this is not a win forecast.
  Threat combines current diplomatic hostility and relative ground capability.
- Countries start at peace. Ground capture and air targeting/interception check
  hostility. Neutral unowned land remains capturable.
- Alliance means mutual non-aggression and trade priority. Automatic defense,
  transit rights, occupation settlements and coalition wars are not implemented.
- Foreign budgets/support are hidden; no intelligence collection system exists yet.
- Bot diplomacy currently responds to offers; it does not initiate a foreign policy.
- Existing save/load menu entries are stubs; this change does not add persistence.

## Verification

Run `.venv\Scripts\python.exe -m unittest discover -s tests -v` for model tests.
Set `RUN_ARCADE_TESTS=1` to include actual hidden-window Arcade integration tests:
card input/rendering, budget effects, market settlement and ground/air war gates.
The tests exercise 1280x800, 1024x768 and 800x600 card layouts.
