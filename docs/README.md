# PatEx → PyPSA-Eur soft-link: data flow

How the outputs of PatEx (Climact's Pathways Explorer) enter this fork, sector by sector.
The link code outside this repository is the package `patex_pypsa`
([IntSusEnergySystems/PatEx-PyPSA](https://github.com/IntSusEnergySystems/PatEx-PyPSA));
the reasons behind each choice are in the "Why" section of each sector file and in its
`MODEL_CHANGES.md`, open questions in its `OPEN_QUESTIONS.md` (`Qn`), work items in its
`TODO.md` (`Tn`).

| Sector | File |
|---|---|
| Buildings (heat, electricity, cooking, district heating) | [buildings.md](buildings.md) |
| Transport (road, rail, aviation, navigation, EV fleet) | [transport.md](transport.md) |
| Industry (carriers, feedstock, process emissions, plastics) | [industry.md](industry.md) |
| Agriculture | [agriculture.md](agriculture.md) |
| Energy system (base load, CO2 intensities, CO2 budget, power, imports, nuclear, waste) | [energy.md](energy.md) |

## Rule of the link

PatEx sets **what has to be served**: annual demand per country, carrier and horizon,
plus a few parameters (district heating share, EV fleet, process emissions, CO2 factors).
PyPSA-Eur decides **how**: capacities, dispatch, fuel origin (fossil / bio / synthetic),
CCS, trade, costs. Each country keeps PyPSA-Eur's split over its nodes and its hourly
profiles; only the annual total is PatEx's. No annual demand comes from PyPSA-Eur,
except for the countries without PatEx data (`patex.fallback_countries`).

CO2: process emissions come from PatEx; all other emissions are computed by PyPSA-Eur from
the fuels it supplies, with PatEx's CO2 factors ([energy.md](energy.md)).

## Pipeline

```
patex run ... -o run.pkl                       PatEx (uv env, pandas 2.2)
  └─ patex-pypsa export-coupling               rules data/extraction_rules.csv (+ checks)
       └─ <coupling_dir>/pypsa_inputs/         the "bundle", CSV only
            patex_energy_totals_{h}.csv        country × energy_totals columns [TWh]
            patex_industry_{h}.csv             country × industrial demand columns [TWh, MtCO2]
            patex_parameters_{h}.csv           district heat share, number evs
            patex_co2_intensity_{h}.csv        gas / oil / coal, oil refining [tCO2/MWh]
            manifest.json                      checksums, horizons, countries
rule build_patex_demands (rules/patex.smk)     copies one horizon into resources/, fails if
                                               a modelled country is neither in the bundle
                                               nor in patex.fallback_countries
hooks (behind patex.enable, see sector files)  build_industrial_energy_demand_per_node,
                                               build_district_heat_share, compose_network,
                                               prepare_sector_network
```

Extraction rules: one signed term per row, rows with the same `category` are summed;
`target = ignore` declares a slice left out on purpose. The export fails if a PatEx demand
row is neither exported nor ignored (`coverage.csv`), if a demand is negative, or if a
horizon is missing (no interpolation).

## Common mechanism: country totals onto nodes

`patex_pypsa.override_country_totals(nodal, country_totals, node_country, fallback)`:
for each country in the bundle and each column, node value = PyPSA-Eur node value /
PyPSA-Eur country sum × PatEx country total. Where PyPSA-Eur has zero for the whole
country, the population fraction of the node is used. Countries absent from the bundle
keep PyPSA-Eur's values.

## Configuration (`patex:` section, `scripts/_patex_config.py`)

| Key | Default | Effect |
|---|---|---|
| `enable` | false | every hook below; without it the fork behaves as upstream |
| `coupling_dir` | — | bundle directory (`.../runs/<scenario>`) |
| `fallback_countries` | AL BA CH GB ME MK NO RS XK | keep PyPSA-Eur demands |
| `energy_totals` | true | buildings, transport, agriculture totals |
| `industry` | true | industry carriers, feedstock gas, process emissions |
| `co2_intensity` | true | CO2 intensity of gas / oil / coal, refinery CO2 |
| `district_heating` | true | district heating share |
| `base_load` | true | residual electricity load (required by `energy_totals`) |
| `plastics_eol_co2` | false | CO2 of plastics not burned for energy (false = PatEx convention) |

Run configs: `config/config.patex.yaml` (settings common to every PatEx run) plus a run
overlay in `config/patex/` (countries, bundle, resolution), e.g.
`pixi run snakemake --configfile config/config.patex.yaml config/patex/levers2-be-lu-nl.yaml`.

## Checks

- `scripts/co2_by_sector.py` (PatEx-PyPSA): CO2 to the atmosphere per country and sector
  of a solved network, bio credits on their consumers ([energy.md](energy.md)).
- `scripts/check_network_ledger.py` (PatEx-PyPSA): loads of a composed or solved network
  per carrier and country against the bundle (ratio 1 expected, known exceptions listed
  in the sector files).
- Rule `build_patex_report`: Sankey of every PatEx demand row from fuel to PyPSA-Eur input,
  with a reconciliation table (`results/<run>/patex_report/`).
