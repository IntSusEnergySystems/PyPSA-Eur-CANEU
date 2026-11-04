# Industry

## PatEx → bundle (`patex_industry_{h}.csv`)

Source variables: `ind_energy-demand-by-carrier-feedstock[TWh]` (by carrier and
feedstock / non-feedstock use) and `ind_emissions-by-material-by-type[MtCO2e]`.
PatEx's materials are **not** mapped to PyPSA-Eur's sectors: only carrier totals per
country are passed.

| Bundle column | PatEx rule |
|---|---|
| `electricity` | electricity |
| `methane` | fossil, bio and synthetic gas, non-feedstock (burnt) |
| `methane feedstock` (new) | same gases, feedstock use (ammonia, olefins) |
| `hydrogen` | hydrogen, incl. feedstock |
| `solid biomass`, `coal`, `low-temperature heat` | solid biomass, solid fossil (incl. coke), heat |
| `naphtha` | fossil, bio and synthetic liquids, incl. feedstock |
| `process emission` | process emissions of every material except olefins, **+ CO2 of solid waste fuel** |
| `process emission from feedstock` | olefin (steam cracker) process emissions |
| `coke`, `ammonia`, `methanol` | 0 (see below) |

- Solid waste (kiln fuel in cement, ceramics, lime…) has no carrier in PyPSA-Eur: it is
  not supplied by the network, its CO2 (PatEx factor) is added to `process emission`.
- `coke` = 0: PatEx's solid fossil carrier already includes it.
- `ammonia`, `methanol` = 0: PatEx makes them from the carriers above (hydrogen, gas);
  PyPSA-Eur would make them a second time (with `industry.ammonia: true` it removes their
  energy from hydrogen / methane and asks for the product).
- Combustion emissions are not passed: PyPSA-Eur computes them from the fuels it supplies
  (with PatEx's CO2 intensities, see [energy.md](energy.md)).

## Bundle → PyPSA-Eur

| Step | Where | What |
|---|---|---|
| nodal demand per carrier | `build_industrial_energy_demand_per_node.py` | PyPSA-Eur's own nodal demand of the horizon (industrial sites × production × energy per tonne) gives each node's **share of its country, per carrier**; × PatEx country total (`override_country_totals`). `current electricity` (today's load, used to clean the historical load) is not touched |
| feedstock gas | `add_industry` | load `gas feedstock for industry` on the gas bus, **no CO2** (its CO2 is in PatEx process emissions); spread over nodes like the burnt gas |
| burnt fuels | `add_industry` | PyPSA-Eur's industry buses / loads (`gas for industry`, `H2 for industry`, `solid biomass for industry`, `coal for industry`, `low-temperature heat for industry`, …) with combustion CO2 and optional capture |
| process emissions | `add_industry` | PatEx values on the `process emissions` bus; capture decided by PyPSA |
| naphtha | `add_industry` | `naphtha for industry` load; the olefin process emissions fix the share of its carbon released at the steam cracker |
| plastics end of life | `add_industry` | see below |

Hourly profile: flat (PyPSA-Eur default for industry).

### Plastics end of life (`patex.plastics_eol_co2`, default false)

PyPSA-Eur turns the non-recycled, non-landfilled plastics (`non-sequestered HVC`) into
CO2, either through `HVC to air` or in waste CHPs. PatEx follows the inventory
convention: feedstock carbon is emitted only where waste is burned (waste-to-energy in
its power sector). With `plastics_eol_co2: false` the `HVC to air` link emits nothing,
and `config.patex.yaml` sets `industry.waste_to_energy: true` so that waste CHPs can burn
plastics for electricity and heat, **with** their CO2. Not compatible with
`sector.municipal_solid_waste` (the biogenic credit of waste would become a net removal:
error). Talking point with Climact / CAN (T23).

## Checks and known gaps

- Ledger: every carrier, feedstock gas, process emissions per country = 1.
- **Hydrogen split over nodes (T22)**: PyPSA-Eur's energy per tonne of chlorine has a
  negative hydrogen entry (chlor-alkali by-product), so a node can receive a negative
  hydrogen load although the country total (PatEx, ≥ 0, no by-product) is positive.
  Option: nodal key from the positive part only.
- `naphtha` = all industry liquids incl. feedstock: reading to confirm with Climact (Q3, T8).
