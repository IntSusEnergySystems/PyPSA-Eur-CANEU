# Buildings (residential and services)

## PatEx → bundle

Source variables: `bld_energy-demand[TWh]` (by building type, end use, carrier, incl.
ambient heat) and `bld_energy-demand-incl-district-heating[TWh]`, `bld_district-energy-demand[TWh]`.

| Bundle column (`patex_energy_totals_{h}.csv`) | PatEx rule |
|---|---|
| `total {residential,services} {space,water}` | incl-district-heating − ambient heat, end use heating / hotwater |
| `electricity {residential,services} {space,water}` | electricity of that end use |
| `electricity {residential,services}` | all building electricity |
| `total / electricity {residential,services} cooking` | cooking, all carriers / electricity |
| `district heat share` (`patex_parameters_{h}.csv`) | district heat / (residential + services space + water), same final-energy base |

Ignored on purpose: non-electric space/water heating in `bld_energy-demand` (taken from
the incl-district-heating variable instead), non-electric appliances / cooling / others
(none in PatEx).

Boundary: **final energy incl. district heat, without ambient heat** — the Eurostat /
JRC-IDEES boundary of PyPSA-Eur's `energy_totals`. Heat pumps' ambient heat is not passed:
PyPSA-Eur models it through the COP.

## Bundle → PyPSA-Eur

| Step | Where | What |
|---|---|---|
| annual totals | `prepare_sector_network.main` | `pop_weighted_energy_totals` columns replaced per country (`override_country_totals`), nodal split of PyPSA-Eur kept |
| final → useful heat | `build_heat_demand` | PyPSA-Eur's `heating_efficiencies.csv` (per country, carrier mix of today) converts the final-energy totals to heat demand |
| hourly profile | `build_heat_demand` | PyPSA-Eur's degree-day profiles of the weather year; only the shape comes from the weather year |
| renovation | config | `sector.reduce_space_heat_exogenously: false`: PatEx demand already includes renovation |
| district heating | `build_district_heat_share.py` | country share of the horizon = PatEx's, spread over nodes like today's urban population; replaces today's share + `district_heating.progress` |
| electric heating in the load | `build_heat_demand` | PyPSA-Eur subtracts the (PatEx) electric space/water heating from the historical electricity load; the residual is then rescaled (see [energy.md](energy.md), base load) |

Heat buses: residential and services heat goes to PyPSA-Eur's `rural heat`,
`urban decentral heat` and `urban central heat` buses; the network chooses the heating
technologies (heat pumps, boilers, district heating supply).

## Checks and known gaps

- Ledger: `building heat (useful)` per country ≈ 1; above 1 by the district heating losses.
- **District heating losses (T19)**: PyPSA-Eur adds `sector.district_heating_loss` (15 %,
  EU-wide) to the building part of the urban central heat demand; PatEx reports
  delivered heat and its own network losses per country (buildings and industry).
  Proposal: losses from PatEx, PyPSA-Eur loss set to 0 for PatEx countries.
- **Non-electric cooking (T18)**: exported (`total ... cooking` − `electricity ... cooking`)
  but PyPSA-Eur has no load for it. Proposal: cooking loads per carrier (gas, oil,
  biomass, hydrogen) with their CO2. Electric cooking is in the base load.
- **District heating trends (T17)** checked with Climact.
- Heating efficiencies are PyPSA-Eur's (today's mix) while PatEx's carrier mix changes
  over time: open question Q1 (final vs useful boundary).
