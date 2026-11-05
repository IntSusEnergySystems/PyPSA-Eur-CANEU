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
| `naphtha` | fossil, bio and synthetic liquids, feedstock use (olefins, other non-energy uses) |
| `oil for industry` (new) | same liquids, burnt (e.g. steam cracker fuel) |
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
| hydrogen split | same | key = **gross hydrogen uses** per node (sectors with a positive hydrogen demand only). PyPSA-Eur's chlorine sector has a negative hydrogen entry (chlor-alkali by-product); PatEx has no by-product, and the net value can be negative at a node or for a whole country, which flipped the signs of the split. The by-product is not added as a supply. Fallback countries keep PyPSA-Eur's net values |
| feedstock gas | `add_industry` | load `gas feedstock for industry` on the gas bus, **no CO2** (its CO2 is in PatEx process emissions); spread over nodes like the burnt gas. `methane feedstock` and `oil for industry` are 0 for fallback countries (their PyPSA-Eur gas and naphtha hold these uses) |
| burnt fuels | `add_industry` | PyPSA-Eur's industry buses / loads (`gas for industry`, `H2 for industry`, `solid biomass for industry`, `coal for industry`, `low-temperature heat for industry`, …) with combustion CO2 and optional capture; CO2 factors per country with PatEx's inventory calibration ([energy.md](energy.md)) |
| process emissions | `add_industry` | PatEx values on the `process emissions` bus; capture decided by PyPSA |
| burnt oil | `add_industry` | load `oil for industry` per node, supplied from the oil bus through a link with oil combustion CO2 (like `agriculture machinery oil`); spread over nodes like the naphtha |
| naphtha | `add_industry` | `naphtha for industry` load (feedstock only); the olefin process emissions fix the share of its carbon released at the steam cracker (factor = olefin process CO2 / naphtha) |
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

Consequence (user's decision, 2026-11-05: kept as is): burning plastics is the model's
choice. `HVC to air` is free and emits nothing, so waste CHPs run only where their power
and heat pay for their cost and CO2; under a cap they may stay unused (BE-LU-NL test
without cap: unused). PatEx's waste-incineration emissions are then not reproduced.

## Why

- **Process emissions from PatEx.** PyPSA-Eur derives them from its own industrial
  production (today's volumes), so PatEx's activity changes per material would not reach
  it. They are CO2e with a small non-CO2 share (CH4 of olefins mostly), kept as is.
- **Burnt oil apart from naphtha (T24).** PyPSA-Eur's `naphtha` is chemical feedstock only:
  all its carbon goes to the steam cracker CO2 and to plastics, whose end of life emits
  nothing unless burnt (T23). PatEx's liquids also include oil burnt in industry (mostly
  steam cracker fuel); in `naphtha` its combustion CO2 was lost (BE-LU-NL test 2030: all
  plastics to `HVC to air`). Burnt oil now gets combustion CO2 like burnt gas (CO2 rule,
  [energy.md](energy.md)).
- **Feedstock gas apart.** PatEx counts the CO2 of ammonia and olefin feedstock gas in its
  *process* emissions; PyPSA-Eur burns all industry `methane` with combustion CO2. In one
  column the CO2 would be counted twice.
- **Solid waste.** PyPSA-Eur's own data book JRC-IDEES "biomass and waste" as biomass. Not
  done here: it would make the waste carbon-neutral.
- **Chlor-alkali hydrogen** (T22, Q12). PyPSA-Eur's industry ratios give chlorine
  −0.937 MWh H2/t (by-product; stoichiometry 28.4 kg H2/t Cl2 = 0.947 MWh/t LHV), ~1.0
  TWh/a in NL and ~0.5 TWh/a in BE with its site data, constant over horizons. PatEx has
  no chlorine material and no by-product route. Order of magnitude (desk research, to
  confirm): EU chlorine output ~8 Mt/a → ~7.6 TWh H2/a, about 3 % of EU hydrogen demand
  (~264 TWh/a in 2023); NL capacity ~0.85 Mt Cl2 → ≤ 0.8 TWh/a, BE ~1.07 Mt → ≤ 1.0 TWh/a
  (site table, not verified). About 85–90 % is used today (burned for heat or used by
  neighbours), 10–15 % vented. Marginal at country scale, locally relevant; energy
  statistics do not show it as a carrier (CBS). Sources: eurochlor.org/production,
  Euro Chlor FOCS-13 Hydrogen (2024), Clean Hydrogen Observatory market landscape
  (Nov 2024), CBS hydrogen balance note (2020).

## Checks and known gaps

- Ledger: every carrier, feedstock gas, process emissions per country = 1.
- Chlor-alkali by-product hydrogen: left out (PatEx convention); whether PatEx should
  represent it is a question for Climact.
- `naphtha` = all industry liquids incl. feedstock: reading to confirm with Climact (Q3, T8).
