# Energy system: electricity load, CO2, supply

## Residual electricity load (`patex.base_load`)

Bundle column `electricity base load` = building electricity − electric space and water
heating: appliances, lighting, cooling, electric cooking. Rail, aviation and shipping
electricity have their own loads ([transport.md](transport.md)), added after the
rescaling below with the shape of this load.

PyPSA-Eur's electricity load is today's measured load, from which it removes electric
heating (`build_heat_demand`) and today's industry electricity. At the end of
`prepare_sector_network.main`, the remaining `electricity` loads of each PatEx country are
scaled (hourly shape kept) so that their annual sum equals `electricity base load`.
Heating, industry, EVs, agriculture stay explicit components.

## CO2 accounting rule

**Process emissions come from PatEx; every other emission is computed by PyPSA-Eur from
the fuels it supplies, with PatEx's CO2 content of each fuel** (user's rule, 2026-11-05).

- PatEx → PyPSA-Eur: process emissions (before capture) on the `process emissions` buses
  ([industry.md](industry.md)); CO2 factors of gas, oil, coal and refinery CO2 per MWh
  of oil (below), computed from PatEx at export, never written in the config.
- PyPSA-Eur: combustion CO2 of every link burning a fossil fuel, capture, fuel origin
  (fossil / bio / synthetic), DAC, sequestration. PatEx's combustion emissions are not
  passed.
- Where PyPSA-Eur cannot burn the fuel (no carrier), its CO2 is computed at export with
  PatEx's factor and added to process emissions: industry solid waste.
- PatEx feedstock (gas for ammonia and olefins) is not burnt: no combustion CO2; the CO2 it
  releases is in PatEx's process emissions.

## CO2 intensity of fuels (`patex.co2_intensity`)

PyPSA-Eur uses one CO2 intensity per carrier; PatEx has one factor per sector and fuel
(diesel, gasoline, kerosene, marine fuel oil, natural gas, coal…). `patex-pypsa
export-coupling --dataset ...` reads PatEx's factors from the dataset and weights them by
PatEx's fossil final energy over the bundle countries, per horizon
(`patex_co2_intensity_{h}.csv`: `gas`, `oil`, `coal`). `compose_network.py` writes them
into the cost table, so every PyPSA-Eur link burning these carriers uses them. Bio and
synthetic fuels are carbon-neutral in both models. Lignite (power only) keeps PyPSA-Eur's
value: PatEx has no lignite carrier.

Why: PyPSA-Eur keeps its CO2 accounting and decides CCS, but with PatEx's numbers wherever
they exist (user's decision, 2026-11-03). PyPSA-Eur's own values (gas 0.198, oil 0.2571,
coal 0.3361 tCO2/MWh) are a few % below PatEx's. The factors are computed from PatEx at
export, never written in the config. Lignite: PatEx has one `elec-plant-with-solid-coal`;
PyPSA-Eur's 0.407 tCO2/MWh is kept, PatEx has no lignite value to align with.

## Inventory (CRF) calibration: not transferred (T27, decided 2026-11-05)

PatEx scales the combustion CO2 of every sector (industry per material, buildings per
building type, transport per domestic / bunkers, agriculture on 1A4c) to the national
inventories (CRF), keeping the last inventory rate for the future. PyPSA-Eur keeps the
**physical** factors (fuel × PatEx's factor) in every sector.

Why: the 1990 baseline of the relative cap is the inventory itself (EEA / UNFCCC data,
`build_co2_totals.py`), so the model's total must be counted like the inventory. But many
of PatEx's rates move an emission between sectors (inventory booking vs energy-statistics
transformation, e.g. autoproducer and greenhouse CHPs); they cancel in PatEx's total
because PatEx calibrates every sector, power included. PyPSA-Eur counts the carbon where it
burns it, and its other sectors are not calibrated: transferring one sector's rate would
remove real CO2 (rate < 1) or count it twice (rate > 1). Calibrated factors also break
capture (90 % of a non-physical amount) and the biogenic balance (credit at one factor,
burnt at another), and were applied to the bio / synthetic share PatEx already has in
industry (BE-LU-NL test 2030: industry combustion above PatEx). Consistency with the
baseline is handled as a total instead (T11): carbon truly missing from the model's
physical count (coke ovens and blast-furnace gases of steel, fugitive emissions,
refining of exported products) to be added as fixed amounts or removed from the baseline,
each with its source.

## CO2 per sector: bio credits on their consumers (T35, reporting)

Gas, oil and methanol are pooled in PyPSA-Eur: every consumer is charged the fossil CO2 of
all it burns, and the carbon of the bio fuels entering the pool is credited on the entry
link (`biogas to gas`, `unsustainable bioliquids`, `biomass to liquid`, `electrobiofuels`,
`biomass-to-methanol`). The total is exact, but the sector lines are gross.
`scripts/co2_by_sector.py` (PatEx-PyPSA) reports CO2 per country and sector with the bio
credit (pool input × pool CO2 intensity) moved to the pool's consumers in proportion to
their annual use (mass balance), like the inventory, which counts no CO2 for burnt
biomass; the rest of an entry link's flow (capture) stays on it. Synthetic fuels are not
moved (their carbon is captured CO2, credited where captured). The net total equals the
CO2 to the atmosphere (checked). The optimisation is unchanged. For national caps (T28),
where to book the credit (production or consumption) is a separate decision.

## Refineries (T26)

`oil refining` (PyPSA-Eur: fossil oil passes through a refining link that emits a fixed
CO2 per MWh, `industry.oil_refining_emissions`) uses PatEx's refinery CO2 per MWh of oil
products: refinery emissions before capture / refinery output, summed over every country
of the PatEx run, per horizon (row `oil refining` of `patex_co2_intensity_{h}.csv`; one EU
refining link). Applied to the fossil oil PyPSA-Eur uses, it counts the refining of what
the modelled countries consume, not of exported products (PatEx counts territorial
refinery emissions): a scope difference to remember for the CO2 target (T11).

Why: an emissions-per-unit parameter like the fuel CO2 contents (user's decision,
2026-11-05, option A of three: PatEx intensity on consumed oil; PatEx refinery emissions
as a fixed amount; PyPSA-Eur's 0.013 tCO2/MWh).

## Process emissions and plastics

See [industry.md](industry.md): PatEx process emissions (before capture), feedstock gas
without CO2, plastics end of life only where burned (`patex.plastics_eol_co2: false`,
waste CHPs on).

## CO2 budget (open, T11)

Not set by the link yet. PyPSA-Eur's default `co2_budget` is relative to the 1990
emissions of the modelled countries (UNFCCC: electricity, transport, buildings, industry
energy and processes, agriculture, domestic and international aviation and navigation)
— not a PAC 2.0 target. Its scope differs from PatEx's (e.g. refineries, plastics end of
life). A run limited to a few countries has no trade with the others and few CO2 storage
and biomass options, so a strict cap can be infeasible. Options: EU or national target
from CAN, or PatEx's own emission trajectory per country.

## Power and supply side: not passed

PatEx's power-sector outputs (`elc_*`: capacities, production, power emissions) are not
imposed: PyPSA-Eur optimises the supply and its CO2. They are kept to compare afterwards
(T13). Fuel origin (fossil / bio / synthetic), refineries, heating technologies, CCS and
storage are PyPSA-Eur's decisions, within the import and domestic supply caps below.

## Imports and domestic supply (`import_limits`, T29)

A standalone option of this fork (works without PatEx; default off, so upstream runs are
unchanged): caps on the **gross imports of each fuel, summed over all modelled
countries** (a self-sufficiency constraint on the whole region, not per country), and
optionally on domestic fossil production.

| Fuel | Components counted as import | Domestic components |
|---|---|---|
| gas | `gas` generators (LNG and pipeline entries) | `gas production` (gas fields, split off from the entries when the option is on) |
| oil | `oil primary` | `oil production` (added when domestic oil is capped) |
| coal | `coal` | `coal production` (added when capped) + `lignite` |
| H2, NH3 | `import H2`, `import NH3` | |
| synthetic gas / oil, methanol | `import gas`, `import oil`, `import methanol` | |
| solid biomass | `solid biomass import` | |
| biogas, bioliquids | `import biogas`, `import bioliquids` (new, carbon-neutral like `import gas`; priced at technology-data `biogas` / `biodiesel crops` fuel costs, as PyPSA-Eur's domestic ones) | |

Config: `import_limits.limits` / `import_limits.domestic` (TWh/a, a number or per horizon),
`import_limits.bio_imports`. Each cap is a `GlobalConstraint` of type `import_limit` /
`domestic_limit` in the composed network (`constant` in MWh over the modelled period);
`solve_network` sums generator dispatch and link output of the listed carriers, and the
dual (EUR/MWh) is written to `mu`. Without a gas network, gas production is not separable
(one EU generator); oil and coal have no domestic generator unless capped, so without a
domestic cap all their supply counts as import.

With `patex.import_limits` (PatEx bundle `patex_supply_{h}.csv`): import caps = PatEx gross
imports per fuel (supply Sankey `source = import`; bioenergy `origin = import`), summed
over the modelled countries; a fuel PatEx does not import (methanol, NH3) gets cap 0. All
modelled countries must be PatEx countries. `config/config.patex.yaml` switches on
PyPSA-Eur's import options (`sector.imports`, `sector.solid_biomass_import`) and the bio
imports, so that every fuel PatEx imports can be imported, up to PatEx's amount.

Why the domestic caps and the gap: PatEx does not model fossil resources. For gas and
coal it imports `demand × energy-net-import-refineries[%]` (a lever) and books the rest as
"primary production", whether or not the country has mines or fields (e.g. coal in
Belgium, which has none since 1992). Imports alone at PatEx's level cannot then serve
PatEx's own demand. Domestic supply is capped per country at min(PatEx production,
today's production from the Eurostat balances, `PPRD` of `energy_totals_year`); the part of
PatEx's production above that (the gap) is added to the import cap and logged by
`compose_network` (user's decision, 2026-11-07, as long as the PatEx scenarios are not
checked; stricter later). Lignite counts in the domestic coal cap (PatEx has one solid
fossil carrier).

District heating: the share of heat demand and the network loss rate come from PatEx
([buildings.md](buildings.md)).

## Nuclear fleet (`nuclear_fleet`, T34)

A standalone option of this fork (works without PatEx; default off). Upstream PyPSA-Eur
has three problems with nuclear in sector runs: every country's nuclear is both an
electricity `Generator` (no build year, infinite lifetime: never retired, e.g. Belgium's
4.1 GW kept to 2050) and a sector `Link` from `EU uranium` (the same plants twice); the
uranium bus has no supply, so the links cannot run; and powerplantmatching (0.8.1) is out
of date (closed Belgian units without end date, missing British units, gross capacities).

With the option, at every planning horizon (after the brownfield step) the nuclear
generators and links are replaced by one Link per reactor of `data/nuclear_fleet.csv`
(uranium → nearest AC bus of the country, cost-data efficiency, VOM and fuel), with a
uranium supply at the cost-data fuel price. Rules per reactor and horizon `h`:

- retirement year = official end date (law, government or regulator decision, licence,
  operator's announced closure), else commissioning year + `default_lifetime`;
- one extension of `extension_years` (10) after it, unless the official end date is
  already an extension (`end_date_includes_extension`, e.g. Doel 4 / Tihange 3 2035,
  Borssele 2033, Krško 2043, Paks 50 years, the British AGRs, Almaraz 2030);
- not used at `h` if its retirement year after extension is within `min_remaining_years`
  (5) after `h`; reactors under construction from their expected grid connection;
- in its extension, the model decides whether to keep it (extendable up to its capacity,
  at the cost-data fixed O&M; no specific long-term-operation investment in the data),
  never more than it kept at the previous horizon;
- must-run (`must_run_margin`): `p_min_pu = p_max_pu − margin`, `p_max_pu` = the country
  availability of `conventional.nuclear.p_max_pu` (weather year), as PyPSA-Wal.

No new build (nuclear is not extendable in this configuration; PAC 2.0: to confirm with
CAN, Q16).

Why: user's rules (2026-11-07): every country can use its installed nuclear, one 10-year
extension, not used within 5 years of its end; default lifetime 50 years where no official
end date or lifetime exists (France's regulator allows operation 10 years after each 4th
periodic review, i.e. to about 50 years for the 900 MW fleet; no country sets a legal
lifetime); dates that are already an extension get no second one.

Data (`data/nuclear_fleet.csv`, built 2026-11-07): reactors in operation and under
construction in the PyPSA-Eur countries, net MW, grid connection, official end dates with
their basis and source URLs per row; coordinates from powerplantmatching 0.8.1. Sources:
World Nuclear Association country profiles and reactor database, national decisions and
regulators, operators; IAEA PRIS could not be read (JavaScript-only), so capacities and
dates should be checked against it. Uncertain: British AGR station capacities, Spain's
Ascó II and Vandellòs II (no official date, default lifetime used), Belgium (2003 law
repealed in May 2025; legal end date 2035, 2037 or 2045 in a draft, 2035 kept), Romania's
licences, Hinkley Point C (unit 1 2030 per EDF, unit 2 2031 assumed, 1630 MW net each),
Paks II unit 5 (2032, 1200 MW rating). Sizewell C (investment decision July 2025) is not
included: first nuclear concrete not confirmed.

## Gas storage (data fix)

Existing gas storage comes from SciGRID_gas (`IGGIELGN_Storages`). Upstream sizes it with
`max_cushionGas_M_m3`, the gas that stays in the reservoir, and clips the nodes at the
98 % quantile. With `patex.enable` it uses `max_workingGas_M_m3` (usable volume) without
clipping: BE 720 instead of 48 Mm³ (Loenhout, ~8 TWh), NL 9 121 instead of 40 227 Mm³.
Why: a data bug, found in PyPSA-Wal (`TIMES2PYPSA/pypsa-wal`, commit `46c2f485`).

## Countries without PatEx data

`patex.fallback_countries` (AL, BA, CH, GB, ME, MK, NO, RS, XK on dataset 47.x.4) keep
PyPSA-Eur's own demands and shares for the `energy_totals_year`, the same for every
horizon; with `reduce_space_heat_exogenously: false` their heat stays at today's level
(Q8, T12). Any other modelled country missing from the bundle stops the workflow
(`build_patex_demands`).
