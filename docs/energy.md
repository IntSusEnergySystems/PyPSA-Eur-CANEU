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
  ([industry.md](industry.md)); CO2 factors of gas, oil, coal; industry factors with
  PatEx's inventory calibration; refinery CO2 per MWh of oil (below). All are emissions
  per unit, computed from PatEx at export, never written in the config.
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

## Industry: PatEx's inventory (CRF) calibration (T27)

PatEx computes industry combustion CO2 as fuel × factor, then scales it per country and
material to the national inventories (CRF tables reported to the UNFCCC): rate = official
/ computed in the inventory years, the last rate kept for the future
(`patex.core.calibration`). PyPSA-Eur keeps computing the CO2 from the fuels it supplies,
with factors that carry this calibration:

- export (`patex_pypsa.emissions.industry_co2_intensity`): per country, horizon and
  material `rate = PatEx combustion CO2 / Σ fuel × factor` (fossil fuels and solid waste;
  bio and synthetic fuels have no factor in PatEx); per fuel `factor × Σ_m E_m rate_m /
  Σ_m E_m` → `patex_industry_co2_intensity_{h}.csv` (country × `gas`, `oil`, `coal`).
  Burning PatEx's fossil industry fuels with them gives PatEx's industry combustion CO2
  exactly. Solid waste CO2 (added to process emissions) uses the calibrated waste factor;
- `prepare_sector_network.scale_patex_industry_co2`: the CO2 ports (atmosphere and
  captured) of `gas for industry`, `gas for industry CC`, `coal for industry`,
  `oil for industry` are scaled from the cost-table intensity to the country's value;
  links on an EU bus get the demand-weighted mean over the modelled countries;
  countries without PatEx data keep the cost-table intensity.

Why: coherence with PatEx's industry emissions (user's decision, 2026-11-05). The rates
differ a lot between countries and materials (inventory boundaries, e.g. blast furnace
and coke-oven gases booked under steel combustion), so the calibrated factors can be far
from the physical ones (below or above). Known side effect: biogas and bio-oil get their
credit at the cost-table intensity when they enter the gas / oil bus, but industry burns
them at the calibrated one, so a bio MWh burnt in industry nets slightly positive or
negative. PatEx's combustion figures are CO2e: the calibrated factors carry their small
non-CO2 share, like the process emissions.

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

PatEx's power-sector outputs (`elc_*`: capacities, production, imports, power emissions)
are not imposed: PyPSA-Eur optimises the supply and its CO2. They are kept to compare
afterwards (T13). Fuel origin (fossil / bio / synthetic), refineries, heating
technologies, CCS and storage are PyPSA-Eur's decisions.

District heating: the share of heat demand comes from PatEx ([buildings.md](buildings.md));
network losses are PyPSA-Eur's (`district_heating_loss`, T19).

## Countries without PatEx data

`patex.fallback_countries` (AL, BA, CH, GB, ME, MK, NO, RS, XK on dataset 47.x.4) keep
PyPSA-Eur's own demands and shares for the `energy_totals_year`, the same for every
horizon; with `reduce_space_heat_exogenously: false` their heat stays at today's level
(Q8, T12). Any other modelled country missing from the bundle stops the workflow
(`build_patex_demands`).
