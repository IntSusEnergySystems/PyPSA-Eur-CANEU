# Energy system: electricity load, CO2, supply

## Residual electricity load (`patex.base_load`)

Bundle column `electricity base load` = building electricity − electric space and water
heating − electric space cooling: appliances, lighting, electric cooking. Electric
cooling is in the bundle columns `electricity {residential,services} space cooling`,
its own load (below). Rail, aviation
and shipping electricity have their own loads ([transport.md](transport.md)), added
after the rescaling below with the shape of this load.

PyPSA-Eur's electricity load is the measured load of the weather year, from which it
removes the electric heating and industry electricity that this load holds: PyPSA-Eur's
own electric space and water heating (`build_heat_demand`; space heating of the weather
year from the heating-degree-day regression of `build_heat_totals`, water heating of
`energy_totals_year`) and today's industry electricity (`current electricity`); with
`patex.cooling`, also today's electric cooling (below). The residual is therefore the
same in every horizon. Hours where it is negative are set to 0 (below). At the end of
`prepare_sector_network.main`, the remaining `electricity` loads of each PatEx country are
scaled (hourly shape kept) so that their annual sum equals `electricity base load`
(+ both cooling columns with `patex.cooling: false`). Heating, cooling, industry, EVs,
agriculture stay explicit components. The log gives per country the residual before
rescaling (TWh, Jan/Aug ratio, minimum) and the snapshots set to 0.

**Why upstream's electric heating, not PatEx's (audit #5, user, 2026-11-16).** Until then
the PatEx override of `pop_weighted_energy_totals` came before `add_heat`, so
`build_heat_demand` subtracted the horizon's PatEx electric heating from a load that
holds the weather year's. The residual then changed with the horizon: what PatEx's
electric heating does not cover stayed in it as a winter-heavy base load (counted twice
with PatEx's own heating), and where PatEx's exceeds today's it was taken out twice
(NO 2030/2040: negative residual in winter hours). Now `main()` keeps PyPSA-Eur's
`electricity {residential,services} {space,water}` before the override and passes them to
`build_heat_demand` for the subtraction only; the heat demand stays PatEx's. Same logic
as industry, which already subtracts today's `current electricity`. Residual before
rescaling now (PyPSA-Eur data only, hourly, 2013, before cooling): e.g. FR 255 TWh,
Jan/Aug 1.11; NO 53.7 TWh, Jan/Aug 1.06; the same in all horizons.

**Negative hours set to 0 (user, 2026-11-16).** IE: in 8 hours of the March 2013 cold
spell the electric heating PyPSA-Eur subtracts exceeds the measured load (minimum
−0.16 GW). No bug: JRC-IDEES gives IE a large electric heating (services conventional
electric space heating 4.0 TWh in 2013, 43 % of services space heat; all electric
heating 30 % of IE's measured load, FR 28 %, DE 6 %), and it is subtracted with the
generic heat-demand profile (daily heating degree days × a morning-peaking intraday
profile), while much of it is night storage heating that the measured load already puts
at night. A negative base load has no meaning, so these hours are set to 0 before the
rescaling (which restores the annual total); the log reports the snapshots and energy.

**Great Britain's measured load (`patex.gb_load_dukes`, user, 2026-11-16).** Upstream
takes GB's load from NESO's National Demand (`ND`, ENTSO-E has no GB data after 2021).
ND is transmission-level demand: it excludes embedded (distribution-connected) wind
and solar, whose growth makes it fall about twice as fast as UK demand (2013 → 2023:
305.6 → 228.2 TWh, −25 %; DUKES "Electricity available", UK consumption + losses: 350.9 →
304.1 TWh, −13 %). GB is a fallback country, so its base load is its measured residual ×
the EU trend: the bias went straight into GB's demand (2023 residual 105.5 TWh vs 180.5
with 2013 weather). With `gb_load_dukes`, `build_electricity_demand` scales GB's load of
each weather year to DUKES 5.1.2 "Electricity available" (`data/dukes_electricity_available.csv`,
DUKES 2026 edition, Accredited Official Statistics, DESNZ); PyPSA-Eur's GB includes
Northern Ireland, as DUKES' UK. The hourly shape stays NESO's, so summer middays keep
the embedded-solar dip (a limit; NESO's embedded wind and solar series would correct the
shape too).

### Electric cooling (`patex.cooling`, audit #5b, user, 2026-11-16)

PyPSA-Eur has no cooling demand: today's cooling is only inside the measured load.
PatEx's electric space cooling grows much faster than the rest of the base load (most
of its growth by 2050 in DE, FR, BE, NL), so spreading it with the base load's shape (one
factor) would put too little demand in summer. With `patex.cooling: true`, residential
and services cooling (bundle `electricity {residential,services} space cooling`) are
loads of their own:

- **Profiles: Hotmaps generic cooling profiles** (Fraunhofer ISI for the H2020 Hotmaps
  project, Pezzutto et al. 2019, *D2.3 WP2 Report – Open Data Set for the EU28*, section
  2.7.2–2.7.3; data `load_profile_{residential,tertiary}_cooling_generic`, CC BY 4.0).
  Hotmaps gives, per country, sector, day type and local hour, a load proportional to
  the daily mean outdoor temperature above 18 °C; residential shapes come from German
  data, tertiary shapes are weighted by each country's subsector cooling shares, both
  are shifted to national activity patterns (Eurostat time-use survey 2009). The slopes
  per K are in `data/hotmaps_cooling_profiles.csv` (one table per country: the tables
  are identical within a country and exactly linear in T − 18 °C; derived and checked
  by `PATEX_PyPSA/scripts/hotmaps_cooling_table.py`). `build_patex_cooling` applies them
  to the weather year: population-weighted daily cooling degree days (18 °C, daily mean
  per cutout cell, `atlite` `cooling_demand`, days at UTC+1) per clustered region ×
  slope of the local day type (weekday / Saturday / Sunday) and local hour.
- **Today's electric cooling** per PatEx country and sector: JRC-IDEES 2023, residential
  air conditioning and services electric space cooling (`...Thermal.SC.AC.Elec`), in
  the weather year (years outside 2000–2023 clamped). For 2013: e.g. DE 1.2 + 6.2, FR
  1.2 + 4.8, NL 0.1 + 1.2, BE 0.05 + 0.8 TWh (residential + services).
- `prepare_sector_network` (base-load block): each country's cooling of a sector is
  spread over its nodes and hours in proportion to that sector's profile
  (`patex_cooling_shape`). Today's cooling is subtracted from the measured load, then
  negative hours are set to 0 and the residual is rescaled to `electricity base load`;
  PatEx's cooling of the horizon (both sectors) is added as load `<node> electricity
  cooling` (carrier `electricity cooling`) on the bus of the node's electricity load.
- Fallback countries (GB, NO…): no JRC-IDEES data on today's cooling; cooling stays in
  their measured residual, whose EU-trend factor is that of base load + cooling
  (`patex_pypsa.fallback.base_load_factor`).

**Why Hotmaps.** It is the EU-wide, documented, openly licensed source of hourly cooling
profiles by country and sector, and the same 18 °C cooling-degree-day reference and
Hotmaps weighting are used in the Horizon Europe CoolLife assessment of space cooling
demand (D2.2, 2024). A first version (hourly cooling degree hours above 21 °C, no
sector or time-of-day structure) put a year's cooling into a few hundred hours (DE
today's cooling 40 GW in one hour), far from the published equivalent full-load hours.
Same logic as heating: what the measured load holds today is taken out with the profile
it has, the horizon's PatEx demand is put back with the same profile (or the horizon's
climate, below).

### Climate of the horizon (`patex.temperature_shift`, user, 2026-11-16)

With one weather year for every horizon, a growing cooling volume only raised the same
peaks. PatEx's cooling growth has two parts (levers 2, 2023 → 2050; figures in the
private notes): the cooled share of floor area, growing most in residential buildings,
which should raise the peak (more units on the same hot afternoon), and the cooling need
per cooled m², growing steadily in every country, the climate and comfort part, which
should also spread cooling over more days. `patex.temperature_shift` adds, per horizon, a uniform shift to
the weather year's outdoor temperature in: the heat demand profile (rules
`build_{daily,hourly}_heat_demand_horizon`: atlite heat-demand threshold 15 °C − shift),
the cooling profiles (`build_patex_cooling_horizon`: 18 °C − shift), heat-pump COPs
(air and ground sources, `build_cop_profiles`) and district heating forward temperatures
(`build_central_heating_temperature_profiles`). Annual totals stay PatEx's; only the
shapes change. What today's measured load holds (PyPSA-Eur's electric heating, today's
cooling) keeps the weather year's unshifted profiles. Wind, solar and hydro keep the
weather year as it is (the correlation between temperature and renewables is kept).

**Values (run `24h-2023-shift`, weather year 2023):** +0.3 °C in 2030, +0.7 °C in 2040
(+1.1 °C in 2050): the climate trend from 2023 to the horizon, 0.4 °C per decade for
north-western Europe (ERA5 land trends: Europe 0.53–0.56 °C per decade, western Europe
0.2–0.5 °C per decade; Copernicus ESOTC 2025 and C3S climate indicators). 2023 itself
(warm, record in parts of western and central Europe) is kept as one realisation of its
climate, not brought to the average. Not calibrated on PatEx's cooling need per m²:
PatEx's base year reflects an average climate while 2023 is already warm (double count).
To check: IPCC AR6 Atlas, Western & Central Europe, SSP2-4.5, 2021–2040 and 2041–2060 vs
1995–2014 (possibly seasonal shifts). Summer extremes warm faster than the mean: a
uniform shift slightly understates the growth of cooling peaks. With the 2013 weather
year the shift would be much larger (about +1 to +1.4 °C in 2030).

**Known limits.** (1) The rest of the base load is still rescaled by one factor per
country. (2) The subtracted electric heating follows the heat-demand profile, not a
measured electric-heating profile (upstream approximation). (3) Hotmaps' holidays are
not modelled (weekday / Saturday / Sunday only); its shapes date from 2009–2010 data
and German measurements. (4) No cooling flexibility (building inertia, cold storage).
(5) The weather year 2013 has few hot days in north-western Europe; the 2023 cutout run
will give another spread.

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
without CO2, naphtha carbon kept in products except PatEx's non-renewable
waste-to-energy, burned in waste CHPs as a must-burn (`patex.waste_to_energy`, audit #2).

Scope against the 1990 baseline (UNFCCC CO2, sectors of `determine_emission_sectors`):
waste burned for energy is in both (baseline: CRF 1.A.1.a and 1.A.2; model: waste CHPs
and industry process emissions); waste incineration without energy recovery (CRF 5.C)
and carbon stored in products are in neither.

## CO2 budget (open, T11)

**No direct air capture** (`sector.dac: false` in `config.patex.yaml`, user 2026-11-16):
the scenario's removals come only from capturing biogenic CO2 (BECCS). Scenario choice;
PatEx levers2 does build some DAC by 2050 (amount in the private notes).

Not set by the link yet. PyPSA-Eur's default `co2_budget` is relative to the 1990
emissions of the modelled countries (UNFCCC: electricity, transport, buildings, industry
energy and processes, agriculture, domestic and international aviation and navigation)
— not a PAC 2.0 target. Its scope differs from PatEx's (e.g. refineries; plastics end of
life aligned since audit #2, see above). A run limited to a few countries has no trade with the others and few CO2 storage
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

**Countries without PatEx data in the run** (e.g. GB, NO, CH). General rule (user,
2026-11-09): exchanges between a modelled non-EU country and the EU are imports / exports
from outside the system in the import and export constraints; imports of a non-EU country
from abroad do not count in the EU caps; a non-EU country's own import cap is the EU's
import cap per person times its population (user, 2026-11-10; before: its current
Eurostat imports). Imports are therefore counted per region: the PatEx countries together
(the "EU" region) and each other modelled country on its own.

- EU region: imports entering at its nodes plus the **gross inflow from GB, NO or any
  other non-PatEx modelled country into a PatEx country** (gas and H2 pipelines, one-way
  link pairs in PyPSA-Eur) ≤ PatEx imports summed over the PatEx countries. Gas from
  Norway or through the GB interconnectors is an import of the EU, as in PatEx.
- GB, NO, CH: imports entering at their nodes plus gross pipeline inflow from any other
  modelled country ≤ the **EU import cap per person × the country's population**, per
  fuel (`patex.fallback_import_caps: eu_per_capita`, user 2026-11-10). EU figure = PatEx
  import caps (imports + the production gap above) of **every country of the PatEx
  bundle**, not only the modelled ones, divided by their population; population of both
  sides from JRC ARDECO (`SNPTD`, country level, year `energy_totals_year`; the source
  PyPSA-Eur already uses for NUTS3 population, with UK, NO and CH). Domestic gas / oil /
  coal ≤ their Eurostat production (without a cap Norway could produce gas without
  limit). Eurostat year: `energy_totals_year`, or the latest earlier year where the
  country's balance has data (GB: 2019, Eurostat reports zeros after Brexit; logged).
  SIEC: gas G3000, oil O4000XBIO, coal C0000X0350-0370.
  Why: with their own Eurostat imports the caps of H2, methanol, NH3 and synthetic fuels
  were 0 (no such imports today) and bound, which also stopped GB and NO from drawing
  them from the EU (2026-11-09 NWE run); the PatEx scenario's import intensity applied to
  their population treats them like an average PatEx country. A fuel PatEx imports
  nowhere (methanol, NH3 in levers2) stays at 0 for them too.
  `patex.fallback_import_caps: eurostat` keeps the earlier rule (Eurostat imports;
  SIEC as above plus solid biomass R5110-5150_W6000RI, biogas R5300, bioliquids
  R5210P+R5220P+R5230P+R5290; H2, NH3, methanol, synthetic fuels: cap 0).
- Fuels on an EU-wide bus, the "pools" (oil incl. bioliquids and synthetic oil, coal incl.
  lignite, methanol, NH3; user, 2026-11-09): split per region. Each country outside the
  PatEx region gets its own copy of every import and domestic-production component of
  the pool, located in the country ("GB EU oil primary", same cost); the originals are
  the EU's (`location: EU`). Demand drawing from a pool is located per node (oil by
  default; `regional_coal_demand`, `methanol.regional_methanol_demand`,
  `ammonia: regional` set in `config.patex.yaml`; the workflow stops if EU-wide demand
  remains). Net annual flow of a country c into the pool = its located supply (own
  imports, production, conversion links such as Fischer-Tropsch) − its located draws
  (boilers, transport, industry...). EU cap: EU imports + Σ_c max(0, net_c) ≤ PatEx EU
  imports; c's cap: c's imports + max(0, −net_c) ≤ c's Eurostat imports (max(0, ·)
  through two non-negative variables per country and pool). Liquid flows count in the
  oil cap whatever their origin (bioliquids, synthetic oil have their own regional caps
  for what each region imports from abroad). Annual net flows: the pools are copper
  plates with storage, there is no hourly route.
- Trade between the EU and a modelled non-EU country costs the same as importing from
  abroad (user, 2026-11-09): their import copies have the world price, pools and existing
  pipelines are free. Equal costs leave the solver indifferent (it may feed GB through
  the EU's imports, ~416 TWh of oil in 2030), so a tie-break of
  `import_limits.transit_penalty` (0.01 EUR/MWh, not a cost) applies to the pool flows
  (x, y) and to gas / H2 pipelines crossing the EU / non-EU boundary: each side imports
  for itself unless a cap or a real price difference makes trade worthwhile.
- Electricity has no import cap (user, 2026-11-09): flows between GB / NO and the EU are
  free in the model and are reported in the self-sufficiency indicators (pypsa2html page
  "Imports and self-sufficiency", branch `can-climact`: per supply region and vector the
  imports from outside the model, flows with the other modelled regions, cap, cap use
  and dual, electricity imports / exports as parts of the hourly net exchange, and
  self-sufficiency = domestic primary production / (production + imports − exports)).

Implementation: `patex_supply_limits` returns `{fuel: {region: TWh}}` (the PatEx region
keyed "EU:c1,c2,..."); `split_pooled_supply` copies the pools' supply per outside
country;
`add_supply_limits` writes one constraint per region where the fuel's components are
located per node (`carrier_attribute` "fuel|countries"), else one summed cap;
`solve_network.add_supply_limits_per_fuel` sums the components in the region and the
gross pipeline inflow (`PIPELINES`). Without non-PatEx countries nothing changes (one
region).

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
  (4) after `h`; reactors under construction from their expected grid connection;
- in its extension, the model decides whether to keep it (extendable up to its capacity,
  at the cost-data fixed O&M; no specific long-term-operation investment in the data),
  never more than it kept at the previous horizon;
- must-run (`must_run_margin`): `p_min_pu = p_max_pu − margin`, `p_max_pu` = the country
  availability of `conventional.nuclear.p_max_pu` (weather year), as PyPSA-Wal.

No new build (nuclear is not extendable in this configuration; PAC 2.0: to confirm with
CAN, Q16).

Why: user's rules (2026-11-07): every country can use its installed nuclear, one 10-year
extension, not used within 4 years of its end (5 until 2026-11-07); default lifetime 50 years where no official
end date or lifetime exists (France's regulator allows operation 10 years after each 4th
periodic review, i.e. to about 50 years for the 900 MW fleet; no country sets a legal
lifetime); dates that are already an extension get no second one.

Data (`data/nuclear_fleet.csv`, `scripts/update_nuclear_fleet_from_pris.py`): units in
operation, suspended or under construction, with status, net MW and grid connection year
from IAEA PRIS (JSON interface of the PRIS Analytics app, `pris-stats.iaea.org`, accessed
2026-11-07; raw snapshot `data/nuclear_pris.csv`, all units and statuses); official end
dates with their basis and source per row from national decisions, regulators and
operators (PRIS has none); site coordinates from powerplantmatching 0.8.1. Units under
construction keep an expected grid connection year from the operator or government
(Hinkley Point C 1 2030 per EDF, unit 2 2031 assumed; Paks 5 2032; Mochovce 4 2026, grid
connection reported in October 2026 while PRIS still lists it under construction).
Sizewell C is not under construction in PRIS. Uncertain end dates: Spain's Ascó II and
Vandellòs II (no official date, default lifetime used), Belgium (2003 law repealed in May
2025; legal end date 2035, 2037 or 2045 in a draft, 2035 kept), Romania's licences.

## Wind and solar capacity limits (`renewable_limits`, T31)

A standalone option of this fork (default off; on in `config.patex.yaml`). Three rules,
each cap counting existing and new capacity of the group in the country:

| Horizon | Offshore wind | Onshore wind | Solar (utility, tracking, rooftop together) |
|---|---|---|---|
| ≤ `planned_until` (2030) | planned 2030 capacity | planned 2030 capacity | planned 2030 capacity |
| later | country goal for 2050, at every horizon | PyPSA-Eur potential | PyPSA-Eur potential |

No build-rate limit: after 2030 the model invests up to the potentials if it pays.

**Offshore goals** (`data/offshore_wind_goals.csv`): the Member States' non-binding
offshore renewable generation goals for 2030, 2040 and 2050 under the TEN-E Regulation
(EU) 2022/869 Art. 14, as delivered on 20 January 2023 per sea basin, read in Table 1
(upper end of each range) of ENTSO-E's five TYNDP 2024 Offshore Network Development Plans
(Northern Seas, Atlantic, Baltic, South and East, South and West; values summed per
country over its basins). 2050: DE 70.1, NL 72, FR 47.5, DK 42.9, IE 35, GR 17.3, FI 12,
PL 10.9, PT 10, IT 8.5, BE 8 GW…; EU sum about 352 GW (Commission: 281–354). Sweden gave
only a 2030 goal, and GB is not a Member State: ENTSO-E's data are used for them (SE
25.2, GB 97.9 incl. Northern Ireland). Norway: the government's goal, areas for 30 GW by
2040 in all Norwegian waters (May 2022, reaffirmed 2025), used for 2040 and 2050;
ENTSO-E's figure (15 GW) covers the North Sea only, while the model can build in every
Norwegian zone, Norwegian and Barents Seas included (decision 2026-11-16, audit #3).

**Offshore class potentials** (`scale_offshore_potentials`): PyPSA-Eur's potential per
node and resource class (`p_nom_max`, 2 MW/km² of eligible sea) is kept. Where a
country's cap at the horizon is above the sum of its potentials (BE, DE, NL at the 2050
goal; in 2030 only BE, whose existing capacity is already above its cap), every class potential of the country (ac, dc, float) is
multiplied by cap / sum, before existing capacity is subtracted per class. A country
without a goal keeps PyPSA-Eur's potential and no cap (logged).

**Planned 2030 capacity** (`data/renewables_planned_2030.csv`,
`scripts/update_renewables_planned.py`): ENTSO-E / ENTSOG TYNDP 2026 scenarios, National
Trends+ (central scenario, built on the final updated NECPs 2024–2025 and the TSOs'
data), installed capacity per country used as model input in 2030 (KPI dashboard, one
sheet per country; offshore = radial + hub; GB = UK + Northern Ireland). EU27 sums equal
the scenario report: onshore 331.0, offshore 65.3, solar 647 GW (report: 652). Solar is
left uncapped where the dashboard leaves out behind-the-meter PV (AT, CH, HU) or has no
value (EE). Where existing capacity is already above the planned value (e.g. BE offshore:
2.75 GW existing in PyPSA-Eur against 2.26 GW planned) no new capacity is built, with a
warning.

Implementation: `compose_network` writes one `GlobalConstraint` per country and group
(type `renewable_limit`, `carrier_attribute` = "<country> <group>", `constant` in MW);
`solve_network` holds new capacity ≤ cap − existing capacity; the dual is in `mu`. Groups:
`onwind`; `offwind-ac`, `offwind-dc`, `offwind-float`; `solar`, `solar-hsat`,
`solar rooftop`. Myopic and overnight only.

Why (user's decisions, 2026-11-09):

- offshore: PyPSA-Eur's potential (2 MW/km² of eligible sea, upstream PR #280) is below
  the capacity already installed in Belgium (3.1 GW in the BE-LU-NL run, 2.26 GW
  installed), and well below national plans in the Netherlands (56.6 vs 72 GW) and
  Germany (5.2 GW at PyPSA-Wal's clustering, vs 70 GW). JRC ENSPRESO's reference scenario
  is no better (BE 2, DE 28, FR 16 GW). The goals are the one consistent, official,
  per-country source for every EU coastal state, set by the Member States from their
  maritime spatial plans and NECPs. As in PyPSA-Wal, the national plan replaces the
  geographic potential offshore;
- offshore classes (decision 2026-11-16, audit #3): until then the per-node potential was
  lifted (`p_nom_max = inf`) in every country with a goal. With 4 resource classes the
  solver then put the whole goal in one class, near-shore AC with the best capacity
  factor: 2050, DE 69 GW in a 0.94 GW class, BE 8 in 0.41, NL 63 in 2.2, DK west 35 in
  2.1, GB 86 in 34. Fleet capital cost was that of a near-shore AC site (about 255–264
  €/kW/a against 290–314 with the capacity spread over the potential) and the capacity
  factor too high where far sites are poorer (FR 0.52 vs 0.44, IE 0.60 vs 0.53). Only
  BE, DE and NL need more room than PyPSA-Eur's potential; scaling all their classes by
  one factor is a higher build density on the same sea area (Belgian zones are built
  denser than 2 MW/km²) and keeps the class shares. Wake losses at higher density are
  not modelled (fixed `correction_factor`);
- onshore wind and solar: PyPSA-Eur's potentials are technical potentials of the right
  order (BE 15.3, NL 46.9, LU 2.3 GW onshore against ENSPRESO's reference 18, 49, 2 GW),
  far above any plan; rooftop PV to be reviewed later;
- 2030: five years ahead most of what will stand is already decided; capping at the
  planned fleet keeps the optimiser from building a counterfactual 2030;
- no build rate: to see first where the model invests when only the potentials bind
  (PyPSA-Wal's `2 × IRENA record` rate not ported, T33 open).

Limits: the goals date from January 2023; the Member States updated them on 18 December
2024 (EU about 88 GW in 2030, about 360 GW in 2050), per-country tables not yet obtained.
The French Mediterranean and Italian/Maltese South-and-West values are read from a figure.
PyPSA-Eur's own potentials were compared only for BE, NL, LU (Germany: ENSPRESO's
reference, 144 GW onshore, is below the national 160 GW target for 2040; to check in a
full-Europe run).

## Cross-border transmission (`interconnection_limits`, T30)

A standalone option of this fork (default off; on in `config.patex.yaml`). Everything is
stated in **usable physical capacity**: AC lines × `s_max_pu` (0.7, PyPSA-Eur's N-1 proxy)
+ DC links, existing and new together:

    cap(border, h) = factor[h] × ( base(border) + Σ ΔTYNDP(border, projects up to h) )

| Term | Source | Content |
|---|---|---|
| `base` | PyPSA-Eur's grid | lines and DC links crossing the border: OSM grid (v0.7, Feb 2026) plus the TYNDP 2020 / NEP projects PyPSA-Eur adds as existing (`transmission_projects`); their original `s_nom` / `p_nom`, the same at every horizon |
| ΔTYNDP | TYNDP 2024 transmission projects (`data/interconnection_projects_tyndp2024.csv`, `scripts/update_interconnection_projects.py`) | transfer-capacity increase per border of each cross-border project, larger of its two directions (`direction`), counted from its commissioning year |
| `factor` | config, per horizon | 1.0 in 2030, 1.5 from 2035 (user's choice) |

Projects counted: status in planning, in permitting or under construction
(`project_statuses: [2, 3, 4]`; "under consideration" left out); commissioned after
`in_grid_until` (2025: earlier ones are taken as already in the OSM grid) and up to the
horizon; not already among PyPSA-Eur's TYNDP 2020 AC lines (same project ID, 16 project
rows). Commissioning year: the last year written by the promoter ("2030/2032" → 2032).
Market zones → countries by their first two letters (UK → GB, Polish import / export
zones → PL); a project booked by TYNDP on several borders counts on each (e.g. the
Luxembourg line Bofferdange–Bertrange raises DE–LU and BE–LU, as LU's German-connected
zone). Example, BE–NL (MW usable): base 4 755 (two clustered AC lines, 6 792 MW rating);
+1 000 in 2030 (ZuidWest380, 2030, in permitting; BRABO III, 2026, already in PyPSA-Eur);
cap 5 755 in 2030, 1.5 × 5 755 = 8 632 in 2040 and 2050. BE–LU: 688 in 2030, 1 482 from
2040 (+300 Bofferdange–Bertrange, 2035).

The cap is a ceiling: projects are allowed, not imposed, and the model builds up to the
cap only if it pays (TYNDP 2020 DC projects are in the grid as zero-capacity candidates,
`new_link_capacity: zero`; AC lines expand along existing corridors). A border with a
TYNDP project but no line or link in the model (e.g. a new country pair) cannot be
expanded (warning). `compose_network` writes one `GlobalConstraint` per border (type
`interconnection_limit`, `carrier_attribute` "c0-c1", MW) and logs base, ΔTYNDP, cap and
the TYNDP 2026 NTC 2030 (`data/interconnection_ntc_2030.csv`,
`scripts/update_interconnection_ntc.py`) side by side; `solve_network` holds new usable
capacity ≤ cap − existing (dual in `mu`). Myopic and overnight only.

Why (user, 2026-11-09):

- reason in physical line ratings, transparently: every MW of a cap is a line or link of
  the model or a TYNDP project ID;
- NTCs are not used as caps: they are market exchange capacities, after the TSOs have
  deducted loop flows, internal bottlenecks and outage margins. PyPSA-Eur computes
  those effects itself with its power flow and the 70 % margin, so an NTC cap would count
  them twice (BE–NL: NTC 2 400 / 3 400 MW against 4 755 MW usable in PyPSA-Eur's existing
  lines). For DC links NTC ≈ rating, so both conventions agree there. NTCs stay as a
  comparison in the log;
- cross-border capacity is cheap flexibility; nearly free expansion (`vopt`, up to
  20 GW per line) understates storage, demand response and backup needs, the flexibility
  CAN asks about. 2030 follows the planned grid, later horizons may go to 1.5 × the
  grid planned for that horizon;
- PyPSA-Wal lessons (`set_NTCs.py`): compare transfer values with usable capacity, cap
  rather than pin (pinned borders: 96–99 % loading, 12.3 bn EUR/a congestion rent in
  2050), count every element of a border.

Limits: TYNDP publishes no line ratings or coordinates per project, only the transfer-
capacity increase: exact for DC projects (converter rating), below the physical rating
for AC projects, so AC caps are somewhat tight. Projects are not placed as lines: an
AC project raises the border's cap and the model expands its existing corridor. Lines
inside countries are not capped (`transmission_limit`). The TYNDP 2024 list is the
cost-benefit export of 12 March 2025, distributed by Open-TYNDP (`CBA_projects.zip`);
the TYNDP 2026 portfolio has no capacities.

## Geological CO2 storage (`co2_storage`, `patex.co2_sequestration`, T32)

Upstream limits the CO2 sequestered (`co2 sequestered` stores, one per node with
`co2_spatial`) in two layers:

1. per node, the CO2StoP storage potential (EU database; offshore regions, `conservative
   estimate` of gas, oil and aquifer units above 3 Mt, clipped at 25 Gt) divided by
   `years_of_storage` (25), as `e_nom_max` of the store
   (`sector.regional_co2_sequestration_potential`);
2. a total over all countries, `sector.co2_sequestration_potential`: 0 / 0 / 40 / 100 /
   180 / 250 Mt/a for 2020–2045, no source in upstream's history.

Three problems: CO2StoP has gaps (with upstream's attributes Norway, France, Spain and
Austria get about 0, while Denmark has 15.7 Gt and Great Britain 7.2 Gt), and a stock in
Gt says nothing about how fast CO2 can be injected; under myopic foresight the per-node
ceiling is set on the store built at each horizon, while `add_brownfield` carries the
earlier stores (50-year lifetime) onto the same bus, so the fleet exceeds the ceiling
(measured in PyPSA-Wal: German storage at 2.6 times its ceiling in 2050); the total is
not sourced.

**`co2_storage`** (standalone option of this fork, default off): the CO2 sequestered in a
country per year is capped at the injection capacity of its storage projects, from the
IEA CCUS Projects Database (`data/co2_storage_projects.csv`, built by
`scripts/update_co2_storage_projects.py`). Rule per country and horizon `h`
(`scripts/_co2_storage.py`):

- storage sites only: project types Storage and T&S, and Full chain projects that are not
  part of a CCUS hub (a hub member injects into the hub's site, counted once); dedicated
  storage only (no enhanced oil recovery); cancelled, suspended, decommissioned out;
- in operation or under construction (FID taken): from their operation year;
- planned: only after `built_only_until` (2030), from their operation year; planned
  without an operation year from `undated_from` (2040);
- capacity = the IEA's estimated capacity, else the announced one; a project without
  either counts as 0 (logged); a country without a counted project gets 0.

Resulting caps [Mt CO2/a] (database accessed 2026-11-09; only modelled countries are
used, Iceland is not one):

| | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|
| NO | 6.9 | 58.9 | 88.7 | 88.7 | 88.7 |
| GB | 4.0 | 126.8 | 182.8 | 182.8 | 182.8 |
| NL | 2.5 | 27.0 | 30.0 | 30.0 | 35.0 |
| DK | 0.4 | 31.7 | 38.2 | 38.2 | 38.2 |
| FR | 0 | 5.1 | 5.1 | 5.1 | 5.1 |
| IT | 0 | 4.0 | 4.0 | 4.0 | 4.0 |
| GR | 0 | 3.5 | 3.5 | 3.5 | 3.5 |
| ES, BG, HR, HU | 0 | 3.0 | 3.0 | 3.0 | 3.0 |
| total (with IS) | 13.8 | 263.2 | 358.5 | 358.5 | 363.5 |

Every other country gets 0 (no storage project, e.g. Belgium, Germany, Poland, Austria,
Ireland): its captured CO2 must go through the CO2 network (`co2_network`) to a country
with a site. Implementation: one `GlobalConstraint` per country (type
`co2_storage_limit`, `carrier_attribute` = country, `constant` in t over the modelled
period) in the composed network; `solve_network` holds the CO2 in **all** the country's
`co2 sequestered` stores at the last snapshot, whatever their build year, below it (the
stores start empty and only fill). The CO2StoP `e_nom_max` is removed (`inf`): the country
cap replaces it. Without `co2_spatial` (one EU store) the cap is the sum over the modelled
countries. Myopic and overnight only.

**`patex.co2_sequestration`** (default true with `patex.enable`): the total cap of each
horizon is PatEx's CO2 stored, summed over the modelled countries (bundle
`patex_parameters_{h}.csv`, column `co2 stored`, from `clm_total-emissions-CCS`: captured
− (CO2 use − direct air capture)), instead of `sector.co2_sequestration_potential`. It is
written as the same `co2_sequestration_limit` constraint as upstream's (PyPSA
`operational_limit` on the `co2 sequestered` carrier, which counts every store, so the
build-year problem does not arise there). PatEx books a CO2 deficit (use above capture
and DAC) as negative storage; the export sets such a country to 0 (a country cannot take
CO2 back out of the ground), with a warning. Fallback countries have no PatEx figure:
their sequestration counts in the total of the PatEx countries (logged).

Why: user's decision (2026-11-09) between three per-country options (CO2StoP clipped as in
PyPSA-Wal, CO2StoP neutral estimate, injection ramp from projects) and three totals (PatEx,
EU policy ramp, the lower of the two):

- the injection rate binds before 2050, not the geological stock: Europe's cumulative
  storage to 2050 is a few Gt against hundreds of Gt in CO2StoP; and CO2StoP's gaps would
  rule out Norway, which hosts Northern Lights;
- the IEA database is the one public source with type, status, FID and operation year for
  every European project (CC BY 4.0); a rule on it, refreshed by a script, instead of
  numbers by hand per country (as `nuclear_fleet` with PRIS);
- up to 2030 only sites with FID: a site without FID now is unlikely to inject by 2030
  (Porthos: FID 2023, operation 2026 in the database). For comparison, the EU Net-Zero
  Industry Act sets an objective of 50 Mt/a of injection capacity in the EU by 2030
  (an obligation on oil and gas producers, not capacity in place); the database's EU
  sites under construction reach 2.9 Mt/a;
- the total from PatEx: CCS is a lever of the PAC 2.0 scenario ("CCS, maximum level" in
  CAN's scenario note), so the amount follows PatEx while PyPSA-Eur decides where CO2 is
  captured, transported and stored.

Limits: the open copy of the database (KAPSARC data portal) has the IEA's 2025 statuses
(e.g. Northern Lights phase 1 still under construction); the IEA's 2026 file needs a free
IEA account and can be read with `--xlsx`. After 2030 the caps are announcements: the
British pipeline (183 Mt/a from 2040) is well above the UK government's ambition. Inside a
country, every node can store (no transport to the coast is costed within a country).
Legal bans are not modelled as such: the database has no site where storage is banned.

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

## Network costs (2026-11-10)

PyPSA-Eur prices one distribution link per node (high to low voltage, sized at the
node's coincident LV peak) at technology-data's `electricity distribution grid`
(668 €/kW in 2025 €, i.e. the old undocumented 500 €/kW of PyPSA-Eur-Sec, source field
"TODO"), and transmission as inter-node lines and DC links (Danish Energy Agency unit
costs), all at the 7 % default discount rate. Method after the pypsa-wal network-cost
review (`TIMES2PYPSA/pypsa-wal/docs/network-costs-review-20260928.md`, calibrated on the
Walloon regulator's DSO accounts); changes in `config/config.patex.yaml`:

- **Regulated discount rate, 4 % real** (one central parameter,
  `network_costs.discount_rate` in `config.patex.yaml`; option of this fork, default
  off), applied before the annuity to every asset in `network_costs.technologies`:
  distribution grid, HVAC / HVDC lines, cables and converters (all inter-node branches,
  cross-border interconnectors included), offshore wind grid connections (export
  cables and substations, built by the TSOs in DE, NL, DK, BE and by regulated OFTOs in
  GB) and CH4 / H2 / CO2 pipelines. Why: networks are regulated monopolies financed at
  the regulated cost of capital, not at a merchant hurdle rate (generation keeps 7 %).
  Evidence (real, 2025–2031 decisions): Ofgem RIIO-3 Final Determinations (Dec 2025),
  Finance Annex Table 16, electricity transmission real WACC **4.46–4.67 %** (CPIH-real,
  vanilla: cost of equity 5.70 % after tax, gearing 55 %; nominal 6.65–6.86 %), read in
  the primary source; CWaPE 2025–29: 4.03 % after tax nominal on the asset base,
  ≈ 3.3 % real before tax (pypsa-wal review, primary source); CRU PR6 draft 3.85 % real,
  Ofgem RIIO-ED2 ≈ 3.9 % real, BNetzA 4th period 5.07 % nominal before corporate tax on
  new equity (search results only, to re-check). The model has no tax: the vanilla /
  after-tax rate is the resource cost (corporate tax is a transfer), the pre-tax rate
  what tariffs recover; recent decisions give 3.3–4.7 % real, older ones (before the
  2022 rate rise) lower. 4 % is the middle; range 3–5 %, `null` restores the 7 %
  default for a sensitivity. Annuity + 2 % FOM over 40 y: 9.5 % of the investment at
  7 %, 7.1 % at 4 % (−25 %).
  Note: `costs.overwrites: discount rate` is **not** applied by `process_cost_data`
  (it overwrites investment, lifetime, FOM, VOM, efficiency, fuel, standing losses
  only); the first attempt of 2026-11-10 used it and had no effect, hence the option.
- **Distribution unit cost 620 €/kW** of LV peak (range 410–960): pypsa-wal's
  calibration on the DSOs' transition-driven capex 2026–30 over the modelled LV peak
  increase, with a quarter of that capex attributed to PV (next item). Close to the
  default; the literature brackets 190 €/kW (DEA, local reinforcement per new
  connection) to ≈ 1 000 €/kW (US full-electrification studies).
- **Rooftop PV hosting 120 €/kWp** (range 0–250), added to the rooftop PV capital cost
  at the distribution grid's annuity (`distribution_grid.pv_hosting_cost`): at one LV
  bus per node rooftop PV never congests the modelled grid, while DSOs reinforce LV
  feeders for it (voltage, reverse flow).
- **Industry at transmission level off the LV bus** (`distribution_grid.
  industry_hv_share`): PyPSA-Eur puts all `industry electricity` behind the
  distribution link, so it sizes (and pays for) a grid it does not use. Share per
  country = Eurostat `nrg_pc_205_v` 2023, non-household consumers ≥ 70 GWh/a (bands
  IF + IG, about ≥ 10 MW average load, the size usually connected at ≥ 36–70 kV) ×
  non-household electricity ÷ industry electricity (Eurostat balances 2023): BE 0.64,
  DE 0.47, DK 0.62, FR 0.53, NL 0.55, NO 0.89. IE is not usable (its large consumers are
  data centres, booked as services: ratio > 1), LU is confidential, GB has no 2023 data:
  median of the others, 0.58. Cross-check: TIMES-WAL draws 70 % of Walloon industrial
  electricity at HV. With bands ≥ 20 GWh/a the shares would be 0.73–0.98 (upper case).
- **Bug fixed (with `patex.enable`)**: the zero-length `-reversed` twin of each lossy
  bidirectional DC link was priced a converter pair by `set_transmission_costs` in every
  myopic horizon after the first (24 links, 1.67 bn€/a in NW Europe 2040), and counted
  in the transmission-volume reference. The twins stay extendable (the bidirectional
  sync constraint needs them).

Not in the optimisation (reporting layers, to add in pypsa2html): the existing grid's
capital charges and the DSOs' non-capacity OPEX (calibrate per country on regulated
revenues or Eurelectric *Grids for Speed*), the intra-country transmission grid and
system services (TSO revenues). Side effect to know: the gas-boiler grid charge
(`sector.gas_distribution_grid_cost_factor: 1.0`) is the electricity distribution
capital cost, so it falls by about 30 % with the lower rate and unit cost.

## Ground-mounted PV potential (2026-11-10, rules 2026-11-12)

PyPSA-Eur's utility PV potential: CORINE 2018 classes 1–20, 26, 31, 32 eligible (all
farmland, built-up land, natural grassland, bare rock), Natura 2000 excluded, 5.1 MW/km²
of eligible land (upstream since January 2024, 1.7 before; no source). In the NW Europe
run this makes 60–79 % of each country eligible and allows fenced plants on about 7–9 %
of the land: not binding (except LU), and not what national rules allow on farmland.

`renewable_limits.ground_pv_file` (`data/ground_pv_potential.csv`, written by
`scripts/update_ground_pv_potential.py`) caps utility + single-axis tracking PV
(existing and new) per country at every horizon. Cap = eligible farmland × national
share at 1 ha/MW + 10 % of brownfield and corridor land at 80 MW/km²; no natural land,
no protected areas, no High Nature Value farmland (user, 2026-11-12):

| country | farmland, all (km²) | farmland, eligible (km²) | farmland GW | brownfield & corridors GW | cap GW | PyPSA-Eur rule, land outside farmland GW |
|---|---|---|---|---|---|---|
| BE | 17,643 | 11,577 | 5.8 | 5.5 | 11.2 | 31.1 |
| DE | 212,931 | 138,234 | 115.2 | 33.7 | 148.9 | 152.4 |
| DK | 32,533 | 26,854 | 53.7 | 2.9 | 56.6 | 16.9 |
| FR | 327,573 | 229,461 | 114.7 | 35.5 | 150.2 | 203.1 |
| GB | 137,402 | 109,690 | 109.7 | 21.7 | 131.4 | 167.7 |
| IE | 47,561 | 41,191 | 41.2 | 2.3 | 43.4 | 10.2 |
| LU | 1,402 | 767 | 0.8 | 0.3 | 1.0 | 1.2 |
| NL | 24,316 | 18,797 | 9.4 | 8.0 | 17.4 | 25.8 |
| NO | 15,574 | 5,639 | 2.8 | 1.9 | 4.7 | 514.7 |

### Farmland

Eligible farmland: CORINE 12–20 (arable land, permanent crops, pastures, annual crops
with permanent crops, complex cultivation patterns) outside Natura 2000, outside WDPA
protected areas and outside High Nature Value farmland (EEA 2012). CORINE 21 (land
principally occupied by agriculture with significant areas of natural vegetation) and
22 (agro-forestry, e.g. dehesa) are out: semi-natural mosaics of high biodiversity.
On it, a share from the national rules at 1 ha/MW (100 MW/km² of fenced site). DE: the
EEG ceiling (177.5 GW) expressed as a share of all its farmland (0.83 %), applied to the
eligible farmland like the other shares. Rules read in the official texts on
2026-11-12, except where marked:

| country | farmland rule | share |
|---|---|---|
| DE | EEG §37(4): no tenders for ground PV on agricultural land above 80 GW, 177.5 GW after 2030; farmland only in less-favoured areas or as Agri-PV (§37(1)) | 177.5 GW (0.83 %) |
| FR | Code de l'urbanisme L.111-29 (loi APER art. 54), décret 2024-318: non-agrivoltaic solar on agricultural, natural or forest land only on the departmental document-cadre: land not farmable (R.111-56) **or** not farmed for ≥ 10 years before March 2023 (R.111-57), plus listed categories (R.111-58: brownfields, quarries, landfills, …). Agrivoltaics: yield > 90 % of a control plot (code de l'énergie R.314-114), coverage ≤ 40 % above 10 MWc for non-proven technologies (R.314-118). No area or capacity limit | 0.5 % |
| GB | Solar Roadmap 2025: 45–47 GW by 2030 on ≤ 0.4 % of UK land; best and most versatile land must be justified | 1 % |
| NL | Aangescherpte voorkeursvolgorde zon (Kamerstuk 32813 nr. 1310, Oct 2023): solar on farmland "in principe ongewenst"; exceptions: agri-PV with a substantial farming function, land in transition under binding agreements, grid-congestion relief. Binding through the provincial omgevingsverordeningen since early 2025 (nr. 1464) | 0.5 % |
| BE | Wallonia: circulaire photovoltaïque of 14 Mar 2024: farmland keeps its food function, ground PV on farmed parcels only as research pilots. Flanders: policy note "Zonneparken en agrivoltaïcs in agrarisch gebied", farming stays primary (6 projects advised negatively in 2025; minister's answers, secondary) | 0.5 % |
| IE | No limit on farmland; no national solar planning guidelines (2025); solar farms need full planning permission (S.I. 493/2022). 8 GW solar by 2030 (CAP25, secondary: gov.ie unreachable) | 1 % |
| DK | No national limit; municipal planning plus state-designated energy parks (lov 614/2024); ambition of a market-driven quadrupling of land-based solar and wind by 2030 (agreement of Oct 2025) | 2 % |
| LU | Agrivoltaic tenders on grassland and arable land (2022 pilot 50 MW; 2025 75 MWc, an active farmer in each project) | 1 % |
| NO | Jordlova §9: cultivated land kept for farming, dispensation only; not applicable to plants with a concession (energiloven §3-1) or zoned in a reguleringsplan (§2). National goal ≤ 2,000 daa (200 ha) of cultivated land converted per year, all uses (≈ 0.5 % of farmland to 2050) | 0.5 % |

**Why these shares:** apart from the EEG ceiling, no text sets an area or a capacity:
the rules are "no, unless" with exceptions (NL, BE, FR, NO), or leave siting to planning
(GB, IE, DK, LU). The shares are therefore a modelling choice: stricter rules get 0.5 %,
planning-led countries 1 %, DK (no limit, energy parks) 2 %. NO's 0.5 % matches its
farmland-conversion goal over 25 years. The share applies to the eligible farmland: the
protected and HNV parts are not counted, also in DE (115 GW instead of the legal 177.5).

**Why 1 ha/MW:** density of new German ground plants (UBA), what the 2040–2050 fleet will
look like. The median of existing UK sites, 2.25 ha/MW (older modules, wider rows),
halves the farmland GW: a sensitivity, not the base case. It does not change DE (legal
ceiling in GW).

### Other land: brownfield and corridors only

10 % at 80 MW/km² (share and density of Tröndle et al. 2019's technical-social
potential) of CORINE 3, 4, 7–9 (industrial or commercial units, road and rail networks
with their associated land, mineral extraction, dump sites, construction sites),
outside Natura 2000 and WDPA, slope ≤ 10°.

**Why no natural land** (user, 2026-11-12): natural grassland, moors and heathland,
sclerophyllous vegetation (garrigue, maquis), transitional woodland-shrub, bare rock and
sparse vegetation (CORINE 26–29, 31, 32) are habitats of high biodiversity or natural
interest; no national rule sends ground PV there (they send it to brownfield and
degraded land: FR R.111-58, NL zonneladder, Walloon circular, NO "grey areas" target),
and the Nature Restoration Regulation (EU 2024/1991) covers habitats outside Natura
2000 too. Tröndle's rule kept 10 % of them: FR 41, GB 101, NO 619 GW (mountain plateaus).
Settlements (CORINE 1, 2, 5, 6, 10, 11) are rooftop or urban land, not ground PV.

**Why protected areas and HNV farmland are out, also on farmland:** WDPA holds every
designated site (national parks and reserves, Natura 2000, Ramsar, Emerald, DK §3
habitats, Flemish ecological network, and landscape designations: DE
Landschaftsschutzgebiete, FR parcs naturels régionaux, UK national parks and AONBs,
biosphere reserves). HNV farmland (EEA, 100 m, 2012 accounting version: extensive
grassland, mosaics) is the farmland that carries a special biodiversity value. Variant:
`--keep-landscape` keeps IUCN V landscape designations and biosphere-reserve transition
areas eligible (lived-in farmland protected for scenery): DE 179, FR 165, GB 150 GW
(other countries unchanged within 0.2 GW).

**Grid rule:** a 250 m CORINE cell is excluded when its centre lies in a WDPA polygon or
most of it is Natura 2000 / HNV (100 m rasters, mode). "Any touching cell" would also
remove the farmland around small sites: DK's §3 habitats (ponds, meadows, streams) then
removed 43 % of Danish farmland.

### Data and how to rebuild

```
pixi run python scripts/update_ground_pv_potential.py \
    resources/<run>/country_shapes.geojson \
    --wdpa <wdpa.gpkg> --hnv <hnv-farmland-2012.tif> \
    --gebco <GEBCO_2014_2D.nc of rule retrieve_gebco>
```

- CORINE 2018 v18_5 (250 m), Natura 2000 (2025-08-15), GEBCO 2014 30″: PyPSA-Eur's
  retrieve rules. The slope (degrees) is computed by the script from GEBCO land
  elevation (sea at 0 m; x spacing scaled by cos(latitude)).
- WDPA (UNEP-WCMC / IUCN, Protected Planet), downloaded by hand:
  `WDPA_Nov2026_Public.zip` (2 GB, file geodatabase) from
  `https://d1gam3xoknrgr2.cloudfront.net/current/` (Protected Planet download page,
  free for non-commercial use). The script keeps polygons with status Designated,
  Inscribed or Established, non-marine realm. A country extract (`ogr2ogr -spat` on
  the region's bounding box, polygon layer) keeps the read fast.
- High Nature Value farmland 2012 (100 m) accounting version, Nov 2017 (EEA, GeoTIFF,
  1 = HNV), downloaded by hand from the EEA datastore share
  `eea_r_3035_100_m_hnv-farm-2012-acc_p_2012_v01_r00` (catalogue record
  82feb669-ebb9-4601-8a84-9e1fe0ae2e2c). The 2018 version (1 km, likelihood 0–100)
  needs a threshold; not used.
- Not used: Key Biodiversity Areas (BirdLife; data on request, restrictive terms).
- Rules and sources per country: `FARMLAND_RULES` in the script and the `rule`,
  `source` columns of the CSV.

Why not Tröndle et al. (2019, Zenodo 3533038) directly: its technical-social potential
bans farmland entirely (DE 90 GW, below the 177.5 GW the EEG allows), uses GlobCover 2009
at 300 m (IE 193 GW, NO 644 GW of "other land"), and gives totals per administrative
unit without resource quality. Its share and density are reused here; its numbers serve as a
cross-check. The cap is per country: within a country the model still places PV on
PyPSA-Eur's per-node potentials (per-node split: later).

## Rooftop PV potential (2026-11-12)

PyPSA-Eur caps the extendable `solar rooftop` generators of each region at 2 kW per
inhabitant (20 m² of usable roof per person × 0.1 kW/m², no source;
`build_solar_rooftop_potentials.py`). In the NW Europe runs this cap binds in 2050 in
BE, DE, DK, IE, LU and NL, and is already almost reached today in NL (about 23 GW on
roofs against a 31 GW cap).

`renewable_limits.rooftop_pv_file` (`data/rooftop_pv_potential.csv`, written by
`scripts/update_rooftop_pv_potential.py`) replaces it with a technical potential per
country, spread over the country's regions by population (as PyPSA-Eur does), times
`renewable_limits.rooftop_pv_share`: **50 % of the technical potential** in
`config.patex.yaml` (user, 2026-11-12; 100 % first the same day). Countries missing from
the file keep 2 kW per inhabitant.

| GW | 2 kW/inhabitant | ENSPRESO 2019 | **technical potential** (cap = 50 %) | national cross-check |
|---|---|---|---|---|
| BE | 23 | 15 | **72** (JRC 2026) | ~100 additional to 2018 (EnergyVille/VITO 2021) |
| DE | 163 | 107 | **429** (JRC 2026) | 409 (Agora Energiewende 2023), 504 (Fraunhofer ISE / IÖR 2020) |
| DK | 8 | 8 | **48** (JRC 2026) | ≤ 47 on roofs > 100 m², upper bound (Energistyrelsen) |
| FR | 125 | 86 | **386** (JRC 2026) | ~350–364 (ADEME 2018–2019) |
| GB | 124 | 82 | **369** (ENSPRESO × 4.51) | no national study |
| IE | 9 | 6 | **30** (JRC 2026) | 13 on homes + > 3 farm and business roofs |
| LU | 1.0 | 0.8 | **3.4** (JRC 2026) | no official study |
| NL | 31 | 21 | **92** (JRC 2026) | 66 (PBL 2014) – 145 roofs + facades (government, 2023) |
| NO | 10 | – | **77** (Multiconsult 2023) | NVE 2024: uncertain (roof load) |

Sources:

- **JRC 2026**: Kakoulaki et al., "Mapping Europe's rooftop photovoltaic potential with
  a building-level database", Nature Energy 11:324–333,
  doi:10.1038/s41560-025-01947-x (CC BY 4.0). Digital Building Stock Model R2025
  (EUBUCCO, OpenStreetMap, Microsoft footprints, cadastres; 271 million EU buildings);
  usable roof 25 % of the footprint on residential buildings, 40 % on others; modules
  facing south at 20°, 22 % efficiency; EU27 2,340 GWp. Used: the Wp per inhabitant of
  the paper's Fig. 7 source data (`Wp_per_capita_dbsm`) × ARDECO population 2024. The
  per-building GeoPackages (JRC data catalogue) would place the potential within a
  country more precisely than population: later.
- **GB** (not in JRC 2026): ENSPRESO 2019 rooftop (JRC, building areas of Bódis et al.
  2019, which covered the UK; residential + industrial roofs, all orientations,
  170 W/m²) × 4.51, the median ratio JRC 2026 / ENSPRESO of the seven EU countries
  modelled (4.0–4.7). Same order as the JRC per-inhabitant values of the neighbours
  (5.1–5.6 kW × 69 million).
- **NO** (not in JRC): Multiconsult (2023) for the Norwegian solar cluster and NHO
  Elektro, technical potential on roofs 76.8 GWp (facades 10.6 GWp not counted), as
  reported by NVE (2024).

**Why JRC 2026:** the newest and only pan-European building-level estimate, open data
and code, and within about ±30 % of the national building-level studies (DE, FR, BE,
NL, DK). ENSPRESO / Bódis 2019 are about 4× lower (older footprints, 18 % modules);
PyPSA-Eur's 2 kW per inhabitant sits between. **Why 50 %:** the technical potential
counts every roof (sheds, listed buildings, weak roofs, shaded or small parts), while the
deployable potential is lower (in NL, 8 % of the suitable roof area has no barrier such
as grid congestion or roof strength, 44 % has one; RVO 2023). Half of it: BE 36, DE
215, DK 24, FR 193, GB 185, IE 15, LU 1.7, NL 46, NO 38 GW (749 GW in total), still
above the national rooftop scenarios (e.g. RTE M1: 35 GW on houses in 2050). The cost
(and the hosting cost of `network_costs`) decides how much is built below the cap. The
JRC yields assume south-facing modules; only the GW cap is used, the profiles stay
PyPSA-Eur's. Facades are not counted.

## Countries outside PatEx (2026-11-12)

Modelled countries without PatEx data (`patex.fallback_countries`: GB, NO, CH…) used to
keep PyPSA-Eur's own pathways: 2023 demand with PyPSA-Eur's fixed EU-wide shares per
horizon (EVs 20/70/100 %, methanol ships, steel and plastics routes) and, with
`reduce_space_heat_exogenously: false`, heat frozen at 2023. That is not PAC 2.0.

With `patex.fallback_demand: eu_trend` (user, 2026-11-12) they start from **their own
data** and follow **PatEx's EU trend in relative terms** ("EU" = the sum over the 25
countries of the PatEx bundle). `build_patex_demands` adds their rows to the PatEx
tables (`patex_pypsa.fallback`), so every soft-link hook treats them like PatEx
countries; import caps and the CO2-storage total still treat them as fallback.

| Item | Base year | Horizon |
|---|---|---|
| sector totals (heat, cooking, road, rail, aviation, navigation, agriculture) | PyPSA-Eur energy totals 2023 (Eurostat, JRC-IDEES) | × EU(h) / EU(2023) |
| fuel shares in a sector (electric / hydrogen / gas road, electric heat, cooking fuels…) | the country's 2023 share; PatEx-only fuels (hydrogen road, cooking per fuel…): none | EU share falling: × its relative change; rising: the country keeps its relative position in what is left to switch, 1 − s = (1 − s₂₀₂₃) × (1 − s_EU(h)) / (1 − s_EU(2023)); no base value: the EU share. Shares of one total ≤ 1 together |
| industry energy per carrier, feedstock (gas, naphtha) | Eurostat final energy (+ blast-furnace input for coal) and non-energy use, latest year with data (GB 2019), **relative to the EU sum in the same year**, × PatEx's EU values | total × EU(h)/EU(2023); carrier shares as above, renormalised to 100 %; hydrogen: EU share |
| process emissions | UNFCCC CRF 2 CO2 relative to the EU (2018, latest in the v23 file) × PatEx EU | × EU trend |
| ammonia (NH3 demand) and its route | own ammonia production (PyPSA-Eur's USGS data, latest year) | × EU ammonia production trend; the route's energy and process CO2 per tonne (PatEx EU) are taken out of the industry rows, as for PatEx countries (industry trend computed on PatEx's industry with the route added back, the scope of Eurostat) |
| electricity base load | the measured residual load in the network (the same in every horizon, audit #5; electric cooling stays in it, audit #5b) | × EU(h)/EU(2023) (`electricity base load factor`): PyPSA-Eur's electric heating exceeds NO's building electricity, so no absolute value |
| district heat share | PyPSA-Eur's 2023 share | × EU relative change (proportional, ≤ 1: full district heating is no end state) |
| district heating loss rate | — | EU rate |
| EV fleet | — | EU EVs per TWh of electric passenger-car energy × the country's |
| waste-to-energy (non-renewable waste in power and heat plants, audit #2) | Eurostat input of non-renewable waste to electricity and heat generation (TI_EHG_E, W6100_6220), same year as the industry balance (GB 2019), **relative to the EU sum in that year** | × PatEx's EU fuel; CO2 at PatEx's EU factor |

**Why relative:** the country keeps its own starting point (GB's gas heating, NO's
electric heating and aluminium) and decarbonises at PatEx's European pace. **Why the
catch-up rule for rising shares:** multiplying a tiny base share (GB electric road
0.1 % in the 2023 data) by the EU's growth would leave it near zero in 2050; on what is
left to switch, a late starter converges as the EU approaches full adoption. **Why
industry relative to the EU in one source:** Eurostat's and PatEx's carrier
definitions differ (PatEx coal includes coke, process CO2 includes waste); the
country's position against the EU in the same source and year carries over to PatEx's
definitions. Countries without Eurostat industry data (CH) keep PyPSA-Eur's industry;
without 2023 energy totals, all of PyPSA-Eur's demand.
