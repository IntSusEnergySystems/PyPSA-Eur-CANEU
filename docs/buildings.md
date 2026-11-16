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
| `total {residential,services} {space,water} efficiency` (`patex_parameters_{h}.csv`) | PatEx useful heat / the final heat above (audit #4): fuels × PatEx boiler efficiency, heat pumps electricity + ambient heat, solar thermal, direct electric × efficiency, district heat at 1 (`patex_pypsa.heat`) |
| `district heat share` (`patex_parameters_{h}.csv`) | district heat / Σ (final heat × PatEx efficiency) = share of the useful building heat, the base PyPSA-Eur applies it to |
| `district heating loss` (`patex_parameters_{h}.csv`) | heat `distribution-losses` / heat delivered (`fec` + `consumption-energy-branch`): PatEx's `network-losses[%]`; 0 without heat networks |

PatEx efficiencies and technology mix come from the dataset (`bld energy-efficiency`,
`bld technology-mix`, OTS/FTS: the export needs the levers of the PatEx run), averaged
over the building uses of each building type; the export stops if its final heat differs
from the bundle columns.

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
| final → useful heat | `prepare_sector_network.main`, `build_heat_demand` | PatEx countries: PatEx's efficiencies of the horizon from the bundle replace `heating_efficiencies.csv` (`patex.heating_efficiencies`, `patex_heating_efficiencies`), so heat demand = PatEx's useful heat; fallback countries: PyPSA-Eur's (carrier mix of today) |
| hourly profile | `build_heat_demand` | PyPSA-Eur's degree-day profiles of the weather year; only the shape comes from the weather year |
| renovation | config | `sector.reduce_space_heat_exogenously: false`: PatEx demand already includes renovation |
| district heating | `build_district_heat_share.py` | country share of the horizon = PatEx's, spread over nodes like today's urban population; replaces today's share + `district_heating.progress` |
| electric heating in the load | `build_heat_demand` | PyPSA-Eur subtracts its own electric space/water heating (kept before the PatEx override: what the measured load holds) from the measured electricity load; the residual, the same in every horizon, is then rescaled (see [energy.md](energy.md), base load, audit #5) |
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
- **Useful heat and district heat share (audit #4, user, 2026-11-16).** PatEx computes
  useful heat per end use, splits off district heat (`district = useful ×
  district-heating-share`), converts the rest with `final = useful / energy-efficiency`
  per technology, then calibrates on statistics and switches fuels; it outputs final
  energy by carrier only, no useful heat. The bundle's heat columns are therefore final
  energy (decentralised) plus district heat (delivered heat). PyPSA-Eur converts them
  with today's carrier mix (`heating_efficiencies.csv`): (1) PatEx's mix and boiler
  efficiencies change over time, so the error grows with the horizon (heat demand too
  low in every PatEx country of the NW-Europe run, more in 2050 than in 2030); (2) heat-pump heat counted as electricity × today's efficiency
  instead of electricity + ambient heat; (3) the district heat share (district heat /
  final heat) applied to useful heat gave the urban central bus PatEx district heat ×
  efficiency (BE, IE, LU about 0.78). Now the link rebuilds PatEx's useful heat from the
  final energy by carrier and PatEx's efficiencies and technology mix (the alternative,
  an in-process PatEx run that keeps the final energy by technology, is exact but adds
  a PatEx run to the pipeline; user chose the carrier route) and passes
  `useful / final` per country as the heating efficiency, so the heat demand is PatEx's
  useful heat and the district heat share is a share of it.
  Carrier → technology: gaseous carriers and hydrogen at the gas boiler's efficiency,
  liquids at the oil boiler's (the fuel switch only renames the fuel), biomass and coal
  their own; ambient heat split between heat pumps and solar thermal by the technology
  mix (heat pumps only for space heating, solar thermal almost only for hot water);
  heat-pump electricity derived from its ambient heat (PatEx: 1/eff_el + 1/eff_amb = 1),
  the rest direct electric. Where PatEx's ambient heat implies more heat-pump
  electricity than it reports (its calibration treats the carriers separately; DE, DK,
  NL residential space heating), all the electricity is counted as heat pump and the
  heat-pump output is electricity + ambient heat: the energy PatEx reports is
  conserved. Efficiencies are averaged over the building uses of a type (they
  differ little within a type). Fallback countries keep PyPSA-Eur's efficiencies and the
  upstream convention for their district heat share (EU trend of PatEx's share on final
  energy). Heat-pump COP trajectory in PatEx: Q22.
- **Non-electric cooking.** PatEx's gas, oil, biomass, coal and hydrogen cooking had no
  load in PyPSA-Eur (upstream has none either: its `total ... cooking` columns are never
  used). Cooking is not heat (user): it gets its own loads per fuel, with combustion CO2
  like `gas for industry`, so the fuel burnt for cooking and its CO2 are in the model
  (T18, 2026-11-06). Flat profile: PyPSA-Eur has no hourly cooking profile, and the gas
  and oil buses have storage, so the shape barely matters.

## Checks and known gaps

- Ledger: `building heat (useful)` per country = 1 (bundle final heat × PatEx
  efficiency; losses in their own load), `district heat` [TWh] = 1 (urban central
  building load vs PatEx district heat), `district heat share` = 1, `district heating
  loss [-]` = PatEx's rate, `cooking <fuel>` = 1.
- Electric cooking is in the base load. Electric cooling is its own load (`patex.cooling`, see [energy.md](energy.md)).
- **District heating trends (T17)** checked with Climact.
- Useful heat is rebuilt from final energy by carrier (no technology dimension in the
  run pickle): approximations listed above; an in-process PatEx run would make it exact.
- Existing boilers (`add_existing_baseyear`) keep PyPSA-Eur's per-carrier efficiencies
  (`gas residential space efficiency`, ...); only the `total ... efficiency` columns
  (heat demand) are PatEx's.
