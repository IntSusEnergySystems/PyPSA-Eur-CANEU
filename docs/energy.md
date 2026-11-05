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
