# Transport

## PatEx → bundle

Source variables: `tra_energy-demand-domestic-by-carrier-user-vehicule[TWh]`,
`tra_energy-demand-bunkers-by-type-carrier[TWh]`, `tra_total-veh-fleet[number]`.

| Bundle column | PatEx rule |
|---|---|
| `total road`, `electricity road`, `hydrogen road` (new) | 2W, LDV, HDV, bus; all / electricity / hydrogen |
| `total/electricity passenger cars`, `two-wheel`, `other road passenger`, `light/heavy duty road freight` | by user and vehicle type (kept for comparison) |
| `total rail`, `electricity rail` | rail |
| `total domestic aviation`, `total domestic navigation` | aviation, inland waterways, **without electricity** |
| `total international aviation`, `total international navigation` | bunkers, without electricity |
| `number evs` (`patex_parameters`) | cars and vans BEV + PHEV |

Electric rail, aviation and shipping go to `electricity base load` (PyPSA-Eur has no such
loads, see [energy.md](energy.md)).

## Bundle → PyPSA-Eur

### Land transport (`prepare_sector_network.add_land_transport`)

PyPSA-Eur builds road demand once, from today's energy, as a driven distance served by
EV / fuel-cell / ICE shares that are the same everywhere. For PatEx countries it is
replaced:

- energy per fuel per node: `electric` = electricity road, `fuel_cell` = hydrogen road,
  `ice` = total road + non-electric rail − electric road − hydrogen road (country totals
  from PatEx, split over nodes like PyPSA-Eur's energy totals);
- each load keeps PyPSA-Eur's hourly profile (traffic × temperature dependence; EV
  profile smoothed as in `add_EVs`) and is scaled so that its annual energy equals PatEx's
  (`patex_pypsa.land_transport_scale`). No distance or drivetrain efficiency enters the
  totals;
- EV fleet (`add_EVs(number_evs=...)`): PatEx's fleet, split over nodes like PyPSA-Eur's
  cars. It sizes chargers (`bev_charge_rate`), smart-charging storage (`bev_energy` ×
  `bev_dsm_availability`) and V2G;
- gas road vehicles (fossil, bio, syn) and hydrogen rail stay in the ICE part, served as
  oil: PyPSA-Eur has no gas vehicles.

Countries in `fallback_countries` keep `sector.land_transport_*_share`.

### Aviation (`add_aviation`)

Domestic + international aviation (PatEx, per country, nodal split of PyPSA-Eur) →
`kerosene for aviation` loads, supplied by the oil bus (fossil, bio or synthetic,
optimised).

### Navigation (`add_shipping`)

- international: PyPSA-Eur's port-based split (`shipping_demand.csv`, built from today's
  totals) rescaled per country to PatEx;
- domestic: PatEx totals in the energy totals;
- the sum is served by PyPSA-Eur's `shipping_{oil,methanol,hydrogen}_share`, each
  converted with its efficiency.

## Checks and known gaps

- Ledger: land transport EV / fuel cell / oil and aviation per country = 1; EV fleet = 1.
- **Shipping (T15)**: the energy delivered differs from PatEx by the efficiency of the
  PyPSA-Eur fuel shares (gap grows as methanol and hydrogen replace oil). Option: set the
  shipping loads per fuel from PatEx (bunkers-marine and IWW by carrier), as for road.
- **PHEV battery (T16)**: PHEVs use the car battery size of BEVs (50 kWh): smart charging
  and V2G may be overestimated where PHEVs dominate.
- Domestic vs international aviation and navigation boundaries (Q5, T9) to confirm with
  Climact.
