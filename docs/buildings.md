# Buildings (residential and services)

## PatEx → bundle

Source variables: `bld_energy-demand[TWh]` (by building type, end use, carrier, incl.
ambient heat) and `bld_energy-demand-incl-district-heating[TWh]`, `bld_district-energy-demand[TWh]`;
heat network losses from `elc_energy-sankey-detailed[TWh]` (label `heat`).

| Bundle column (`patex_energy_totals_{h}.csv`) | PatEx rule |
|---|---|
| `total {residential,services} {space,water}` | incl-district-heating − ambient heat, end use heating / hotwater |
| `electricity {residential,services} {space,water}` | electricity of that end use |
| `electricity {residential,services}` | all building electricity |
| `total / electricity {residential,services} cooking` | cooking, all carriers / electricity |
| `{gas,oil,solid biomass,coal,hydrogen} cooking` | non-electric cooking per fuel, residential + services (fossil + bio + synthetic per fuel) |
| `district heat share` (`patex_parameters_{h}.csv`) | district heat / (residential + services space + water), same final-energy base |
| `district heating loss` (`patex_parameters_{h}.csv`) | heat `distribution-losses` / heat delivered (`fec` + `consumption-energy-branch`): PatEx's `network-losses[%]`; 0 without heat networks |

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
| district heating losses | `add_heat`, `add_patex_district_heating_losses` | `district_heating_loss` = 0 for the PatEx countries (`patex.district_heating`); load `urban central heat losses` on each `urban central heat` bus = PatEx rate × (building + low-temperature industry heat loads on the bus), hour by hour |
| non-electric cooking | `add_patex_cooking_loads` | per node and fuel a flat load (`gas / oil / coal / solid biomass for cooking` bus) fed from the fuel bus by a link with the fuel's CO2 (PatEx intensity; none for solid biomass), `H2 for cooking` on the H2 bus; split over nodes like PyPSA-Eur's cooking totals. Fallback countries: none (as upstream) |

Heat buses: residential and services heat goes to PyPSA-Eur's `rural heat`,
`urban decentral heat` and `urban central heat` buses; the network chooses the heating
technologies (heat pumps, boilers, district heating supply).

## Why

- **Space vs water heating.** The totals agree, the split does not: PatEx space + water
  matches JRC-IDEES (its calibration source); PyPSA-Eur is 2 % higher because it
  overwrites JRC-IDEES with Eurostat `nrg_d_hhq` (`update_residential_from_eurostat`), which
  puts 11.7 TWh in BE water heating against 8.9 in JRC-IDEES. Little impact: both go to
  the same heat buses, only the profile differs (flat for water, weather-dependent for
  space). Source of PatEx's split: open question Q10.
- **District heating losses.** PatEx `bld_district-energy-demand` is delivered heat
  (`dh = E × district-heating-share`); PatEx adds network losses in its supply module
  (`heat_demand = heat + heat × network-losses[%]`, per country, reported in
  `elc_energy-sankey-detailed`, heat → distribution-losses, buildings and industry
  together). PyPSA-Eur multiplies the building urban central heat demand by
  `1 + district_heating_loss` (15 %, EU-wide) and puts industry low-temperature heat on
  the same bus without loss. So the PatEx countries get PatEx's rate per country on all
  the heat the network delivers, industry included, as their own load (user's proposal,
  T19, 2026-11-06). The rate is applied to PyPSA-Eur's heat on the bus (useful heat for
  buildings), not PatEx's absolute losses, which sit on PatEx's final-energy base and
  include energy-branch heat PyPSA-Eur does not put on these buses. Fallback countries
  keep 15 %.
- **Non-electric cooking.** PatEx's gas, oil, biomass, coal and hydrogen cooking had no
  load in PyPSA-Eur (upstream has none either: its `total ... cooking` columns are never
  used). Cooking is not heat (user): it gets its own loads per fuel, with combustion CO2
  like `gas for industry`, so the fuel burnt for cooking and its CO2 are in the model
  (T18, 2026-11-06). Flat profile: PyPSA-Eur has no hourly cooking profile, and the gas
  and oil buses have storage, so the shape barely matters.

## Checks and known gaps

- Ledger: `building heat (useful)` per country = 1 (losses in their own load),
  `district heating loss [-]` = PatEx's rate, `cooking <fuel>` = 1.
- Electric cooking is in the base load.
- **District heating trends (T17)** checked with Climact.
- Heating efficiencies are PyPSA-Eur's (today's mix) while PatEx's carrier mix changes
  over time: open question Q1 (final vs useful boundary).
