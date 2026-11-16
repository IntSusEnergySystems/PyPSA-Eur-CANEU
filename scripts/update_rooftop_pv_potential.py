# SPDX-License-Identifier: MIT
"""
Rooftop PV potential per country (``renewable_limits.rooftop_pv_file``).

    python scripts/update_rooftop_pv_potential.py [--out data/rooftop_pv_potential.csv]

Technical potential of building roofs (no facades) [GW]:

- EU countries: JRC, Kakoulaki et al. (2026), "Mapping Europe's rooftop photovoltaic
  potential with a building-level database", Nature Energy 11:324-333,
  doi:10.1038/s41560-025-01947-x (CC BY 4.0). Digital Building Stock Model R2025
  (EUBUCCO, OSM, Microsoft footprints, cadastres; 271 million buildings); usable roof
  25 % of the footprint (residential) / 40 % (non-residential); south 20°, 22 %
  modules. Per-capita values from the paper's Fig. 7 source data
  (``Wp_per_capita_dbsm``, file MOESM4) × ARDECO population 2024.
- GB (not in JRC 2026): ENSPRESO 2019 rooftop (JRC, same building approach as Bódis et
  al. 2019, which covered the UK; residential + industrial roofs, all orientations,
  170 W/m²) × the median ratio JRC 2026 / ENSPRESO of the EU countries modelled.
- NO (not in JRC): Multiconsult (2023), "Teknoøkonomisk potensial for solkraft på
  bygg" (for the Norwegian solar cluster and NHO Elektro), technical potential of
  roofs 76.8 GWp, as reported by NVE (2024).

Reasons in ``docs/energy.md`` ("Rooftop PV potential").
"""

import argparse
from pathlib import Path

import pandas as pd

ARDECO = "data/jrc_ardeco/archive/2021/ARDECO-SNPTD.2021.table.csv"
POP_YEAR = 2024

#: JRC 2026, Fig. 7 source data (MOESM4), Wp per inhabitant (EU27)
JRC_WP_PER_CAPITA = {
    "AT": 6307, "BE": 6051, "BG": 5156, "CY": 8728, "CZ": 5159, "DE": 5136, "DK": 8093,
    "ES": 4446, "EE": 6722, "FI": 8256, "FR": 5633, "GR": 5290, "HR": 5744, "HU": 5384,
    "IE": 5490, "IT": 5292, "LT": 6814, "LU": 4939, "LV": 5808, "MT": 3149, "NL": 5087,
    "PL": 4572, "PT": 6166, "RO": 4653, "SK": 5341, "SI": 5841, "SE": 5725,
}
#: ENSPRESO_SOLAR_PV_CSP.XLSX, sheet "MS 170 W per m2 and 100%", sum of the residential
#: and industrial roof-top rows (4 orientations each) [GW]
ENSPRESO_ROOF_GW = {
    "BE": 15.3, "DE": 106.8, "DK": 7.8, "FR": 85.6, "GB": 81.8, "IE": 6.4, "LU": 0.8,
    "NL": 21.3,
}
#: national studies where JRC 2026 has no data [GW]
NATIONAL_GW = {
    "NO": (76.8, "Multiconsult 2023 for Solklyngen / NHO Elektro, technical potential "
           "on roofs (facades 10.6 GW not counted), reported in NVE 2024"),
}


def main():
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.prepare_sector_network import ardeco_population

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    p.add_argument("--out", type=Path, default=Path("data/rooftop_pv_potential.csv"))
    a = p.parse_args()

    jrc_ct = sorted(JRC_WP_PER_CAPITA)
    pop = ardeco_population(ARDECO, jrc_ct, POP_YEAR)
    rows = {
        ct: (JRC_WP_PER_CAPITA[ct] * pop[ct] / 1e9, "JRC 2026 (Kakoulaki et al., "
             f"Nature Energy): {JRC_WP_PER_CAPITA[ct]} Wp/inhabitant x ARDECO "
             f"population {POP_YEAR}")
        for ct in jrc_ct
    }
    ratio = pd.Series({ct: rows[ct][0] / gw for ct, gw in ENSPRESO_ROOF_GW.items()
                       if ct in rows}).median()
    rows["GB"] = (ENSPRESO_ROOF_GW["GB"] * ratio, f"ENSPRESO 2019 roofs "
                  f"{ENSPRESO_ROOF_GW['GB']} GW x {ratio:.2f} (median JRC 2026 / "
                  "ENSPRESO of BE, DE, DK, FR, IE, LU, NL)")
    for ct, (gw, src) in NATIONAL_GW.items():
        rows[ct] = (gw, src)
    out = pd.DataFrame(
        [(ct, round(gw, 2), src) for ct, (gw, src) in sorted(rows.items())],
        columns=["country", "gw", "source"],
    )
    out.to_csv(a.out, index=False)
    print(out[["country", "gw"]].to_string(index=False))


if __name__ == "__main__":
    main()
