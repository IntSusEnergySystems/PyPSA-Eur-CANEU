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
| `number bev`, `number phev` (`patex_parameters`) | battery-electric / plug-in hybrid cars and vans |

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
- EV fleet (`add_EVs(number_evs=...)`): PatEx's BEVs + `patex.phev_fleet_factor` × PHEVs
  (factor 0: PHEVs count as combustion cars), split over nodes like PyPSA-Eur's cars. It
  sizes chargers and the EV battery; how much of it is flexible: next section;
- gas vehicles (`add_gas_vehicles`, new): load `land transport gas` per node with the
  ICE profile, supplied from the gas bus through a link with combustion CO2 (like
  `gas for industry`); PyPSA-Eur chooses fossil, bio or synthetic gas;
- diesel rail stays in the ICE load, as in PyPSA-Eur (`build_transport_demand`).

### EV charging flexibility (`ev_flexibility`, T16)

A standalone option of this fork (works without PatEx; default off, on in
`config/config.patex.yaml`), adapted from PyPSA-Wal (`TIMES2PYPSA/pypsa-wal`,
`docs/ev-charging-softlink.md`), which follows Elia's AdeqFlex 2025 study. Code:
`scripts/_ev_flexibility.py`, called in `add_EVs`.

PyPSA-Eur's defaults make half of the EV fleet a flexible battery (`bev_dsm_availability`
0.5) that is plugged in 80–95 % of the time (`bev_avail_mean` / `max`), with V2G: about
half of all EV charging can be shifted, and EVs can feed the grid. With the option:

1. **Flexible share = Elia's market share** (smart charging steered by the system, V1M +
   V2M) of the fleet, "Current commitments": 0.07 in 2030, 0.172 in 2035, 0.18 from
   2040 (Elia's last year, 2036, held). That share of the EV demand keeps PyPSA-Eur's
   driving profile on the `EV battery` bus behind the `BEV charger`; the charger
   (`bev_charge_rate` 11 kW) and the EV battery store are sized on that share of the
   fleet (`bev_energy` 60 kWh, Elia), with PyPSA-Eur's minimum state of charge in the
   morning.
2. **The rest is a fixed load**, `land transport EV inflexible`, on the electricity bus
   (low voltage with the distribution grid), shaped by Elia's daily charging curves:
   natural charging V0 (as soon as plugged in) and local smart charging V1H (home, by
   tariff and PV self-consumption, four sky × PV variants; work), weighted per horizon
   (`charging_weights`, natural 0.51 in 2030, 0.33 from 2040; home variants equal;
   work 0.13 / 0.12). Curves of the Elia vintage nearest to the horizon (2026, 2036),
   in each country's local time (standard time; summer time ignored, ≤ 1 h).
3. **Plugged-in availability** of the flexible fleet: PyPSA-Eur's traffic-based shape
   with Elia's max / mean (0.40 / 0.32 until 2030, 0.48 / 0.35 from 2035) and a floor
   (0.20 / 0.18).
4. **No V2G** (Elia's V2M share is small and not separated).
5. **Energy**: the two loads add up to the EV demand; the flexible one is set net of the
   charger loss (× `bev_charge_efficiency`), so the grid draws exactly the EV demand.

Data: `data/ev_charging/elia_charging_daily_profiles_local.csv` (Elia's curves in local
time) and `data/ev_charging/elia_adeqflex2025/` (Elia's tables: operation-mode shares,
availability, daily profiles, location shares), as compiled for PyPSA-Wal; the weights are
PyPSA-Wal's `build_ev_charging_weights.py` output for "Current commitments" (all three
modes from the same Elia scenario and year). Elia's "Current commitments – High Flex"
case (market 0.13 in 2030, 0.28 from 2036) is a sensitivity: set `market_share` and
`charging_weights` from it together, never one alone.

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
  fleet from PatEx's cars and vans. PHEVs are not counted (user, 2026-11-09, as PyPSA-Wal
  with TIMES): a ~15 kWh PHEV battery is no EV battery, and their electric km are already
  in the EV load. Elia counts a PHEV as half a BEV: `phev_fleet_factor` 0.5 if wanted.
- **EV flexibility (T16).** PyPSA-Eur's 50 % flexible fleet, 80–95 % plugged in, with V2G,
  overstates EV flexibility (supervisor's remark, 2026-11-09). Elia's AdeqFlex study is the
  reference PyPSA-Wal uses; it is Belgian, applied to every country for lack of a European
  equivalent with the same detail (a known limitation). Elia's market share is the share
  of EVs whose charging the system steers; the rest charges when plugged in or by local
  rules, which the model cannot move.
- **Belgian data for every country (checked 2026-11-09).** No harmonised per-country
  source of EV plug-in availability or smart-charging share was found: TSO figures
  (German NEP, NESO FES, RTE) are scenario assumptions, and the measured session datasets
  (emobpy DE, UK and NO home chargers, NL public charging) each cover one country with
  other metrics. The one harmonised driver, the share of people living in a house (a
  proxy for a private charger; Eurostat `ilc_lvho01`, 2023), varies widely: IE 90 %,
  NL 79 %, BE 77 %, FR 65 %, LU 59 %, EU 52 %, IT 41 %, DE 37 %, ES 34 %. Elia is kept
  for every country because (i) the availability only applies to the flexible share
  (7–18 %), cars steered by an aggregator that almost certainly have a private charger
  whatever the housing mix; (ii) a country correction (±0.1 on availability) is small
  next to the change from PyPSA-Eur's defaults; (iii) the flexible share is a market and
  policy assumption, not a mobility statistic; (iv) BE and NL are close in housing.
  Countries dominated by flats (ES, IT, DE, CH, Baltics) are likely somewhat too flexible;
  in a pan-European run, test with a lower `market_share` there rather than invent
  per-country values. For reference, 65 % of private EV users in France do no smart
  charging (AVERE-France, *Livre blanc pilotage de la recharge et V2X*, 2023).
- **Charger loss.** PatEx calibrates transport energy on the energy balances, i.e.
  electricity as metered; PyPSA-Eur put it behind the charger, adding its 10 % loss on top
  (the same double count PyPSA-Wal found with TIMES). With `ev_flexibility` the grid draws
  exactly PatEx's electricity road.
- **Time of day.** PyPSA-Wal's UTC file shifts Elia's curves the wrong way (local + 2 h
  instead of − 2 h: the 09:00 natural-charging peak lands at 11:00 UTC instead of 07:00);
  here the curves are kept in local time and shifted per country.
- **Shipping.** `shipping_demand.csv` is also built from today's totals; only its port
  split is kept.

## Checks and known gaps

- Ledger: land transport EV (grid draw: flexible / charger efficiency + inflexible),
  fuel cell / gas / oil, rail electricity and hydrogen, aviation kerosene and electricity,
  shipping oil / hydrogen / electricity per country = 1; EV fleet behind the chargers
  (BEV + factor × PHEV, × market share) = 1.
- Elia's charging behaviour is Belgian and applied everywhere; Elia's last year (2036) is
  held for 2040 and 2050.
- Domestic vs international aviation and navigation boundaries (Q5, T9) to confirm with
  Climact.
