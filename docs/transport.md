# Transport

## PatEx → bundle

Source variables: `tra_energy-demand-domestic-by-carrier-user-vehicule[TWh]`,
`tra_energy-demand-bunkers-by-type-carrier[TWh]`, `tra_total-veh-fleet[number]`.

| Bundle column | PatEx rule |
|---|---|
| `total road`, `electricity road`, `hydrogen road` (new), `gas road` (new) | 2W, LDV, HDV, bus; all / electricity / hydrogen / gas (fossil, bio, syn) |
| `total/electricity passenger cars`, `two-wheel`, `other road passenger`, `light/heavy duty road freight` | by user and vehicle type (kept for comparison) |
| `total rail`, `electricity rail`, `hydrogen rail` (new) | rail; all / electricity / hydrogen |
| `total domestic aviation`, `total domestic navigation` | aviation, inland waterways, **without electricity** |
| `total international aviation`, `total international navigation` | bunkers, without electricity |
| `electricity aviation`, `electricity navigation` (new) | domestic + bunkers, electricity |
| `hydrogen navigation` (new) | inland waterways + bunkers-marine, hydrogen |
| `number evs` (`patex_parameters`) | cars and vans BEV + PHEV |

Every PatEx transport fuel has its own load in PyPSA-Eur (below); none is hidden in the
base load or served as another fuel. PatEx ships have no methanol or ammonia (Q14).

## Bundle → PyPSA-Eur

### Land transport (`prepare_sector_network.add_land_transport`)

PyPSA-Eur builds road demand once, from today's energy, as a driven distance served by
EV / fuel-cell / ICE shares that are the same everywhere. For PatEx countries it is
replaced:

- energy per fuel per node: `electric` = electricity road, `fuel_cell` = hydrogen road,
  `gas` = gas road, `ice` = total road + total rail − electricity rail − hydrogen rail −
  electricity road − hydrogen road − gas road, i.e. liquid road fuels and diesel rail
  (country totals from PatEx, split over nodes like PyPSA-Eur's energy totals; the new
  columns like `total road` / `total rail`);
- each load keeps PyPSA-Eur's hourly profile (traffic × temperature dependence; EV
  profile smoothed as in `add_EVs`) and is scaled so that its annual energy equals PatEx's
  (`patex_pypsa.land_transport_scale`). No distance or drivetrain efficiency enters the
  totals;
- EV fleet (`add_EVs(number_evs=...)`): PatEx's fleet, split over nodes like PyPSA-Eur's
  cars. It sizes chargers (`bev_charge_rate`), smart-charging storage (`bev_energy` ×
  `bev_dsm_availability`) and V2G;
- gas vehicles (`add_gas_vehicles`, new): load `land transport gas` per node with the
  ICE profile, supplied from the gas bus through a link with combustion CO2 (like
  `gas for industry`); PyPSA-Eur chooses fossil, bio or synthetic gas;
- diesel rail stays in the ICE load, as in PyPSA-Eur (`build_transport_demand`).

### Rail, aviation and shipping electricity, hydrogen rail (`add_patex_transport_loads`)

New loads per node, added at the end of `prepare_sector_network.main`, after the base-load
rescaling: `rail electricity`, `aviation electricity`, `shipping electricity` on the
transmission bus (not low voltage) with the hourly shape of the node's residual
electricity load; `H2 for rail` on the H2 bus, flat. Nodal split like `total rail`,
aviation and navigation totals. PyPSA-Eur's measured load holds today's rail electricity:
the base-load rescaling replaces it with PatEx's building electricity only.

Countries in `fallback_countries` keep `sector.land_transport_*_share`.

### Aviation (`add_aviation`)

Domestic + international aviation (PatEx, per country, nodal split of PyPSA-Eur) →
`kerosene for aviation` loads, supplied by the oil bus (fossil, bio or synthetic,
optimised).

### Navigation (`add_shipping`)

- international: PyPSA-Eur's port-based split (`shipping_demand.csv`, built from today's
  totals) rescaled per country to PatEx;
- domestic: PatEx totals in the energy totals;
- fuel split per country **from PatEx**: hydrogen share = `hydrogen navigation` / total
  navigation, methanol share = `methanol navigation` / total if the bundle has it (PatEx
  has no methanol ships yet, Q14), oil = the rest (marine fuel oil, fossil / bio /
  synthetic chosen by PyPSA-Eur). PatEx's energy per fuel is used as is: no conversion with
  `shipping_*_efficiency`. Fallback countries keep `shipping_*_share` with the conversion.
  Ammonia ships do not exist in PyPSA-Eur; they would need a new load on the NH3 bus.

## Why

- **Loads per fuel, not distance.** PyPSA-Eur builds `transport_demand.csv` once, without
  horizon, from today's energy totals, as a driven distance (final energy / ICE-based fleet
  efficiency); overriding the energy totals alone would leave road at today's level.
  Feeding PatEx's electrified energy through that efficiency counts the EV gain twice (less
  distance, then less EV electricity), and an energy ratio `electricity road / total road`
  as EV share has the same bias (an EV needs ~3.3× less energy per km: 53.2 vs 16.1
  (100 km)/MWh). So each load is set to PatEx's energy per fuel; PatEx's vehicle-km are
  not needed.
- **EV fleet from PatEx.** PyPSA-Eur's EV share × today's cars gives a quite different
  fleet from PatEx's BEV + PHEV cars and vans.
- **Shipping.** `shipping_demand.csv` is also built from today's totals; only its port
  split is kept.

## Checks and known gaps

- Ledger: land transport EV / fuel cell / gas / oil, rail electricity and hydrogen,
  aviation kerosene and electricity, shipping oil / hydrogen / electricity per country
  = 1; EV fleet = 1.
- **PHEV battery (T16)**: PHEVs use the car battery size of BEVs (50 kWh): smart charging
  and V2G may be overestimated where PHEVs dominate.
- Domestic vs international aviation and navigation boundaries (Q5, T9) to confirm with
  Climact.
