# Industry

## PatEx → bundle (`patex_industry_{h}.csv`)

Source variables: `ind_energy-demand-by-carrier-feedstock-material[TWh]` (by carrier,
feedstock / non-feedstock use and material), `ind_emissions-by-material-by-type[MtCO2e]`
and, for ammonia, `ind_material-production-by-material[kt]`. PatEx's materials are
**not** mapped to PyPSA-Eur's sectors: only carrier totals per country are passed,
**without ammonia**, whose route PyPSA-Eur optimises (below).

| Bundle column | PatEx rule |
|---|---|
| `electricity` | electricity |
| `methane` | fossil, bio and synthetic gas, non-feedstock (burnt) |
| `methane feedstock` (new) | same gases, feedstock use (olefins, other chemicals; not ammonia) |
| `hydrogen` | hydrogen, incl. feedstock (not ammonia) |
| `solid biomass`, `coal`, `low-temperature heat` | solid biomass, solid fossil (incl. coke), heat |
| `naphtha` | fossil, bio and synthetic liquids, feedstock use (olefins, other non-energy uses) |
| `oil for industry` (new) | same liquids, burnt (e.g. steam cracker fuel) |
| `process emission` | process emissions of every material except olefins and ammonia, **+ CO2 of solid waste fuel** |
| `process emission from feedstock` | olefin (steam cracker) process emissions |
| `ammonia` | PatEx ammonia production [kt] × 5.166 MWh/t (LHV, `industry.MWh_NH3_per_tNH3`): an **NH3 demand** |
| `coke`, `methanol` | 0 (see below) |

- Solid waste (kiln fuel in cement, ceramics, lime…) has no carrier in PyPSA-Eur: it is
  not supplied by the network, its CO2 (PatEx factor) is added to `process emission`.
- `coke` = 0: PatEx's solid fossil carrier already includes it.
- `methanol` = 0: PatEx has no methanol material (it is inside "chemical-other", without
  a production figure), so its energy stays in the carriers above and PyPSA-Eur is not
  asked for the product (no double count).
- **Ammonia route optimised by PyPSA-Eur (user, 2026-11-12).** PatEx fixes how ammonia
  is made (its green-ammonia lever); the soft-link splits demand (PatEx) from supply
  (PyPSA), and ammonia is a supply route (gas reforming, electrolytic hydrogen with a
  flexible Haber-Bosch, imports). So: the NH3 demand = PatEx's production; **every**
  PatEx energy carrier of material `chemical-ammonia` (feedstock gas, hydrogen, burnt
  gas, electricity, heat) and its process CO2 leave the industry columns (rules with
  `material!=chemical-ammonia`); they are kept as the `routes` target of
  `patex_demands_long.csv` (`ammonia|<column>`, `ammonia production`). PyPSA-Eur's NH3
  load (`sector.ammonia: regional`) is met by Haber-Bosch from any hydrogen (electrolysis,
  SMR with or without capture, imports) or NH3 imports (cap 0 for now: PatEx imports
  none). Reforming CO2 then comes from the gas PyPSA-Eur's SMR uses.
  **No double count:** at every export, `check_industry_balance` checks per country and
  year that industry columns + routes = PatEx's industry energy (all carriers) and
  process emissions; on levers2 the new bundle + routes equals the previous bundle to
  < 1e-5 TWh in every column. The ledger checks the NH3 load against the bundle.
  Fallback countries: the same split (their own ammonia production, PyPSA-Eur's USGS
  data, on PatEx's EU production trend; energy and CO2 per tonne of PatEx's EU route).
- **Urea and PatEx's ammonia CO2 (talking point for Climact, Q21).** PatEx's ammonia
  process CO2 per MWh of feedstock gas is above the carbon natural gas contains
  (0.20 tCO2/MWh), and PatEx also books urea application CO2 in agriculture (3H), as the
  inventory does with a 2.B.1 figure *net* of the CO2 bound in urea. PatEx's plant-side
  figure looks gross, so the urea carbon would be counted twice within PatEx. With the optimised route this no longer
  enters the model: PyPSA-Eur's reforming emits the carbon of the gas it burns, and
  agriculture CO2 is not in the network (audit #10).
- Combustion emissions are not passed: PyPSA-Eur computes them from the fuels it supplies
  (with PatEx's CO2 intensities, see [energy.md](energy.md)).

## Bundle → PyPSA-Eur

| Step | Where | What |
|---|---|---|
| nodal demand per carrier | `build_industrial_energy_demand_per_node.py` | PyPSA-Eur's own nodal demand of the horizon (industrial sites × production × energy per tonne) gives each node's **share of its country, per carrier**; × PatEx country total (`override_country_totals`). `current electricity` (today's load, used to clean the historical load) is not touched |
| hydrogen split | same | key = **gross hydrogen uses** per node (sectors with a positive hydrogen demand only). PyPSA-Eur's chlorine sector has a negative hydrogen entry (chlor-alkali by-product); PatEx has no by-product, and the net value can be negative at a node or for a whole country, which flipped the signs of the split. The by-product is not added as a supply. Fallback countries keep PyPSA-Eur's net values |
| feedstock gas | `add_industry` | load `gas feedstock for industry` on the gas bus, **no CO2** (its CO2 is in PatEx process emissions); spread over nodes like the burnt gas. `methane feedstock` and `oil for industry` are 0 for fallback countries (their PyPSA-Eur gas and naphtha hold these uses) |
| burnt fuels | `add_industry` | PyPSA-Eur's industry buses / loads (`gas for industry`, `H2 for industry`, `solid biomass for industry`, `coal for industry`, `low-temperature heat for industry`, …) with combustion CO2 and optional capture |
| process emissions | `add_industry` | PatEx values on the `process emissions` bus; capture decided by PyPSA |
| burnt oil | `add_industry` | load `oil for industry` per node, supplied from the oil bus through a link with oil combustion CO2 (like `agriculture machinery oil`); spread over nodes like the naphtha |
| naphtha | `add_industry` | `naphtha for industry` load (feedstock only); the olefin process emissions fix the share of its carbon released at the steam cracker (factor = olefin process CO2 / naphtha) |
| plastics end of life, waste-to-energy | `add_industry` | see below |

Hourly profile: flat (PyPSA-Eur default for industry).

### Plastics end of life and waste-to-energy (`patex.waste_to_energy`, audit #2, 2026-11-16)

Convention: **the inventory's, as in PatEx and in the 1990 baseline of the CO2 cap.**
Naphtha carbon emits CO2 only at the steam cracker (PatEx olefin process emissions) and
where waste is burned for energy. The rest stays in products (exported, in use,
recycled, landfilled) and emits nothing.

| Flow | Where | Value |
|---|---|---|
| steam cracker CO2 | `naphtha for industry` link, port 2 | PatEx olefin process emissions (unchanged) |
| waste burned for power and heat | store `non-sequestered HVC` per node, emptied within the year by the **waste CHPs** only (no `HVC to air`): a **must-burn** of a fixed annual amount, timing and plant capacity optimised | bundle `waste to energy fuel` [TWh] per country (PatEx non-renewable waste input to power and heat plants), spread over the nodes by population; CO2 per MWh = `waste to energy co2 / fuel` (PatEx's power-sector factor of non-renewable waste) on the waste CHP's CO2 port |
| rest of the naphtha carbon | — | kept in products, no CO2 (logged by `add_industry`) |
| industry waste fuel (cement kilns…) | `process emissions` | PatEx factor × PatEx solid waste (unchanged, see above) |
| waste incineration without energy recovery (CRF 5.C) | — | **left out on both sides**: not in the model, not in the baseline (user, 2026-11-16) |

Settings: `patex.waste_to_energy: true` with `patex.plastics_eol_co2: false` and
`industry.waste_to_energy: true` (checked, error otherwise); not compatible with
`sector.municipal_solid_waste` (error). Fallback countries: see
[energy.md](energy.md), "Countries outside PatEx".

**Why.** PyPSA-Eur's default emits *all* naphtha carbon at end of life (all plastics
non-sequestered, `HVC_environment_sequestration_fraction: 0`), in the region that made
the naphtha. The NW Europe chemical clusters make several times the plastics their own
waste holds: most of the carbon leaves as exported products or long-lived stock. The
inventory, and so the 1990 baseline of the relative cap, counts none of it (carbon
stored in products is excluded), but counts the fossil part of waste burned for energy
(CRF 1.A.1.a, in the baseline) and in industry (1.A.2). The earlier setting
(`plastics_eol_co2: false` alone, 2026-11-05) dropped the waste-to-energy CO2 too: the
waste CHPs had a free CO2-free alternative (`HVC to air`) and never ran. A share of the
naphtha (PatEx's waste treatment shares) was rejected: it would charge the export
industry's carbon to the region's waste.

**Accepted simplifications.** The waste bus holds PatEx's waste fuel, not the naphtha
carbon: the carbon balance of the oil pool is not closed by it (the waste carbon is
older products and imports). Bio or synthetic carbon in the oil pool that ends up in
products counts as removed, whereas PatEx gives olefin feedstock no credit (open, Q13).
The waste CHP is PyPSA-Eur's (efficiencies, costs); PatEx's own waste plants and
heat-only boilers are not reproduced, only their fuel and CO2.

## Why

- **Process emissions from PatEx.** PyPSA-Eur derives them from its own industrial
  production (today's volumes), so PatEx's activity changes per material would not reach
  it. They are CO2e with a small non-CO2 share (CH4 of olefins mostly), kept as is.
- **Burnt oil apart from naphtha (T24).** PyPSA-Eur's `naphtha` is chemical feedstock only:
  all its carbon goes to the steam cracker CO2 and to plastics, whose end of life emits
  nothing except PatEx's waste-to-energy (audit #2). PatEx's liquids also include oil burnt in industry (mostly
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

- Ledger: every carrier, feedstock gas, process emissions per country = 1; waste-to-energy
  per country: store = bundle fuel, burned = store, CO2 = bundle CO2; no `HVC to air`.
- Chlor-alkali by-product hydrogen: left out (PatEx convention); whether PatEx should
  represent it is a question for Climact.
- `naphtha` = all industry liquids incl. feedstock: reading to confirm with Climact (Q3, T8).

## Fallback countries (outside PatEx): industrial production (2026-11-12)

GB, NO, CH… keep PyPSA-Eur's industry: today's production (kt) per subsector, then
the horizon's process switches (`industry.St_primary_fraction`, `DRI_fraction`,
`HVC_*`, `Al_primary_fraction`, `sector_ratios_fraction_future`). Outside the EU27,
`build_industrial_production_per_country` scales EU27 production by the ratio of the
country's sectoral final energy (Eurostat) to the EU27's (JRC-IDEES). Two upstream
bugs zeroed part of it, fixed in the fork (no option: they only act where data was
silently lost):

- **Missing Eurostat year.** Eurostat keeps GB rows after Brexit, filled with zeros:
  with `industry.reference_year: 2023` all GB production was 0 except ammonia (USGS),
  so GB had no industrial fuel, feedstock or process CO2 while the 1990 CO2 baseline
  counts GB industry. Now the ratio uses the latest earlier year with data (GB: 2019,
  country and EU27 energy of that year), applied to EU27 production of the reference
  year; a warning names the year.
- **Sector label mismatch.** Eurostat's "Non Ferrous Metals" never matched JRC-IDEES
  2023's "Non-ferrous metals": alumina, aluminium and other non-ferrous production was
  0 for every non-EU country (NO: about 22 TWh of industry energy). Labels are now
  matched ignoring case, hyphens and spaces.

The build stops if a modelled country ends with no industrial production (other than
ammonia) or a Eurostat sector has no JRC-IDEES total (`test/test_industrial_production_fallback.py`).

Known limit: the scaling assumes the EU27 mix within each sector. NO gets 247 kt of
primary aluminium (real output well above 1 Mt) and 1,030 kt of alumina (none produced
in Norway); GB's "not elsewhere specified" industry energy lands in "Other industrial
sectors". National production data for fallback countries would refine this.
