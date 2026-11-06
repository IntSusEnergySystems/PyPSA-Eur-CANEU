# SPDX-License-Identifier: MIT
"""
Refresh ``data/nuclear_fleet.csv`` (``nuclear_fleet`` option, T34) from IAEA PRIS.

    python scripts/update_nuclear_fleet_from_pris.py [--countries BE FR ...] [--offline]

PRIS (pris.iaea.org, now the "PRIS Analytics" app at pris-stats.iaea.org) serves its data
from a JSON interface: ``country/countries/`` and ``reactor/reactors-by-code/<ISO2>``
(undocumented, used by the app; one request per country). This script:

1. fetches every PyPSA-Eur country listed in PRIS and writes the raw snapshot
   ``data/nuclear_pris.csv`` (all units, every status, access date);
2. rebuilds ``data/nuclear_fleet.csv`` with the units in operation, suspended or under
   construction: reactor, status, net MW and grid connection year from PRIS; official end
   dates (``retirement_year``, ``end_date_includes_extension``, basis, source) and site
   coordinates kept from the current table (national decisions and powerplantmatching;
   PRIS has neither), matched by unit name. Units under construction keep the expected
   grid connection year of the current table (PRIS gives none).

A PRIS unit without a row in the current table, or a row without a PRIS unit, stops the
script: add it to ``ALIASES`` or to the table by hand.
"""

import argparse
import datetime
import json
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

API = "https://pris-stats.iaea.org"
COUNTRIES = (
    "AL AT BA BE BG CH CZ DE DK EE ES FI FR GB GR HR HU IE IT LT LU LV ME MK NL NO PL "
    "PT RO RS SE SI SK XK"
).split()
KEEP = ["Operational", "Suspended Operation", "Under Construction"]
#: PRIS unit → row of the current table where names differ (AGR station rows)
ALIASES = {
    "hartlepool a 1": "hartlepool",
    "hartlepool a 2": "hartlepool",
    "heysham a 1": "heysham 1",
    "heysham a 2": "heysham 1",
    "heysham b 1": "heysham 2",
    "heysham b 2": "heysham 2",
    "torness 1": "torness",
    "torness 2": "torness",
    "paks 5": "paks ii 5",
}
PRIS_COLUMNS = [
    "id", "countryCode", "unitName", "siteName", "statusName", "typeCode",
    "netElectricalCapacity", "designNetElectricalCapacity", "grossElectricalCapacity",
    "constructionDate", "gridDate", "commercialDate", "shutdownDate",
    "latestOperatingLicenseDate", "operatorName",
]


def get(path: str) -> dict:
    request = urllib.request.Request(
        f"{API}/{path}", headers={"Accept": "application/json", "User-Agent": "pypsa-eur"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def key(name: str) -> str:
    name = name.lower().replace("-", " ").replace(".", "")
    return re.sub(r"\s+", " ", name).strip()


def fetch(countries: list[str]) -> pd.DataFrame:
    listed = {c["countryCode"] for c in get("country/countries/")["items"]}
    rows = []
    for code in [c for c in countries if c in listed]:
        rows += get(f"reactor/reactors-by-code/{code}")["items"]
        time.sleep(1)  # one request per country, gently
    pris = pd.DataFrame(rows)[PRIS_COLUMNS]
    pris["accessed"] = datetime.date.today().isoformat()
    return pris


def rebuild(pris: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    units = pris[pris.statusName.isin(KEEP)].copy()
    current = current.assign(key=current.reactor.map(key))
    # exact name first; aliases only for units without a row of their own
    known = set(zip(current.country, current.key))
    units["key"] = [
        k if (c, k) in known else ALIASES.get(k, k)
        for c, k in zip(units.countryCode, units.unitName.map(key))
    ]

    merged = units.merge(
        current.drop(columns=["reactor", "net_mw", "status", "source_capacity"]),
        left_on=["countryCode", "key"],
        right_on=["country", "key"],
        how="left",
        indicator=True,
    )
    missing = merged[merged._merge == "left_only"]
    if len(missing):
        raise ValueError(f"PRIS units without a row in the table:\n{missing[['countryCode', 'unitName']]}")
    gone = set(zip(current.country, current.key)) - set(zip(units.countryCode, units.key))
    if gone:
        raise ValueError(f"table rows not operating / under construction in PRIS: {sorted(gone)}")

    grid = pd.to_datetime(merged.gridDate).dt.year
    under_construction = merged.statusName.eq("Under Construction") & grid.isna()
    merged["commissioning_year"] = grid.where(~under_construction, merged.commissioning_year)
    merged["net_mw"] = merged.netElectricalCapacity.fillna(merged.designNetElectricalCapacity)
    merged["source_capacity"] = (
        "IAEA PRIS unit " + merged["id"].astype(str) + " (" + API + "/reactor/reactor-by-id/"
        + merged["id"].astype(str) + "), accessed " + merged["accessed"]
    )
    out = merged.rename(columns={"unitName": "reactor", "statusName": "status"})
    columns = [
        "country", "reactor", "lat", "lon", "net_mw", "commissioning_year", "retirement_year",
        "end_date_includes_extension", "lifetime", "status", "retirement_basis",
        "source_capacity", "source_retirement",
    ]
    out = out[columns].sort_values(["country", "reactor"])
    out["commissioning_year"] = out.commissioning_year.astype(int)
    out["retirement_year"] = out.retirement_year.astype("Int64")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--countries", nargs="*", default=COUNTRIES)
    p.add_argument("--offline", action="store_true", help="reuse data/nuclear_pris.csv")
    p.add_argument("--data", type=Path, default=Path("data"))
    a = p.parse_args()

    raw = a.data / "nuclear_pris.csv"
    if a.offline:
        pris = pd.read_csv(raw)
    else:
        pris = fetch(a.countries)
        pris.to_csv(raw, index=False)
    fleet_file = a.data / "nuclear_fleet.csv"
    fleet = rebuild(pris, pd.read_csv(fleet_file))
    fleet.to_csv(fleet_file, index=False)
    print(fleet.groupby(["country", "status"]).net_mw.agg(["size", "sum"]).to_string())


if __name__ == "__main__":
    main()
