# Agriculture

## PatEx → bundle

Source variable: `agr_energy-demand-by-vector[TWh]` (by carrier only; PatEx has no
end-use dimension in agriculture). PyPSA-Eur needs agriculture **by use**:

| PyPSA-Eur column | PyPSA-Eur load |
|---|---|
| `total agriculture electricity` | fixed electricity load |
| `total agriculture heat` | rural heat bus (any heat technology) |
| `total agriculture machinery` | oil load (part electrified by `agriculture_machinery_*_share`) |

Carrier groups extracted from PatEx: electricity; diesel (incl. liquid bio); fuel oil
(incl. gasoline); gas (fossil, LPG, bio); solids (coal); biomass.
`patex_pypsa/agriculture.py` splits each group into uses with the **JRC-IDEES 2021
shares of the country** (`data/agriculture_use_shares.csv` in PatEx-PyPSA, rebuilt with
`patex-pypsa build-agriculture-shares`; EU27 shares where a country has none). PatEx
gasoline goes with fuel oil, which JRC-IDEES uses for heat only. The shares are fixed over
the horizons.

Machinery: PatEx has no lever for machinery electrification. Electric machinery
(JRC-IDEES motor drives) is exported inside `total agriculture electricity`, and
`total agriculture machinery` holds liquid fuels only.

## Bundle → PyPSA-Eur

| Step | Where | What |
|---|---|---|
| annual totals | `prepare_sector_network.main` | the three columns replaced per country in `pop_weighted_energy_totals` (nodal split of PyPSA-Eur) |
| loads | `add_agriculture` | electricity load, rural heat load, machinery oil load (profiles of PyPSA-Eur) |
| no second electrification | `config.patex.yaml` | `agriculture_machinery_electric_share: 0`, `agriculture_machinery_oil_share: 1` |

## Why

- **Split by use, not by carrier.** PyPSA-Eur optimises how each use is supplied, and each
  carrier serves several uses (JRC-IDEES BE 2021: diesel is 1.12 TWh of heat and 2.49 of
  machinery; electricity is 0.28 heat, 0.26 motor drives and 1.19 other uses). A mapping
  carrier → use would misplace them.
- **Machinery shares 0 / 1.** PatEx's agriculture fuel mix is historical then held
  constant; only irrigation electricity and fossil → bio switches change. The electric
  machinery share PatEx implies is far below PyPSA-Eur's default (50 %), so PyPSA-Eur must
  not electrify it a second time.
- **Farm bioenergy.** PatEx agriculture is calibrated on six fossil and electric carriers;
  bio carriers only appear through the fuel switch. Hence the gap to JRC-IDEES (Q9).

## Checks and known gaps

- `scripts/check_agriculture_split.py` (PatEx-PyPSA): the split conserves PatEx's total;
  base year compared with JRC-IDEES by use.
- Ledger: agriculture electricity / heat / machinery per country = 1.
- **Farm bioenergy (Q9, T7)**: PatEx has no base-year solid biomass, biogas or biodiesel
  in agriculture (only through fuel switches), so agriculture heat is below JRC-IDEES.
  To confirm with Climact whether it is counted elsewhere.
