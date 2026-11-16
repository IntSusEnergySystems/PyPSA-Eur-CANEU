# SPDX-License-Identifier: MIT
"""
Refresh ``data/interconnection_ntc_2030.csv`` (``interconnection_limits`` option, T30)
from the ENTSO-E / ENTSOG TYNDP 2026 scenarios reference grid.

    python scripts/update_interconnection_ntc.py [--xlsx ReferenceGrid_Electricity.xlsx] [--year 2030]

``ReferenceGrid_Electricity.xlsx`` (in ``Line-data.zip``, National Trends+ model input,
2026-data.entsos-tyndp-scenarios.eu) gives per border between market zones the NTC of
the reference grid of each year (today's grid plus the TYNDP projects of that year),
"Summary Direction 1" (first zone → second) and "Summary Direction 2", in MW.

Zones are mapped to countries by their first two letters (UK → GB; Poland's PL00E / PL00I
import and export zones → PL; offshore hubs ``*_OFF`` → their country, so a hybrid
interconnector counts on its cross-border leg, e.g. BEO1_OFF–UK00 for BE–GB). Rows
inside one country are dropped; rows of the same border are summed per direction.
"""

import argparse
import datetime
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = (
    "https://2026-data.entsos-tyndp-scenarios.eu/input/model-input/national-trends/"
    "Line-data.zip"
)
MEMBER = "Line-data/ReferenceGrid_Electricity.xlsx"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "interconnection_ntc_2030.csv"


def borders(sheet: pd.DataFrame) -> pd.DataFrame:
    df = sheet[sheet["Border"].notna()]
    zones = df["Border"].astype(str).str.split("-", expand=True)
    country = [z.str[:2].replace({"UK": "GB"}) for z in (zones[0], zones[1])]
    cross = country[0] != country[1]
    directed = pd.concat(
        [
            pd.DataFrame({"a": country[0], "b": country[1],
                          "mw": df["Summary Direction 1"]})[cross],
            pd.DataFrame({"a": country[1], "b": country[0],
                          "mw": df["Summary Direction 2"]})[cross],
        ]
    )
    mw = directed.groupby(["a", "b"])["mw"].sum()
    rows = [
        (a, b, v, mw.get((b, a), 0.0)) for (a, b), v in mw.items() if a < b
    ] + [(b, a, 0.0, v) for (a, b), v in mw.items() if a > b and (b, a) not in mw]
    return pd.DataFrame(rows, columns=["country0", "country1", "mw_0to1", "mw_1to0"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--xlsx", help="ReferenceGrid_Electricity.xlsx (default: download)")
    parser.add_argument("--year", type=int, default=2030)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    if args.xlsx:
        source, origin = args.xlsx, Path(args.xlsx).name
    else:
        with urllib.request.urlopen(URL, timeout=300) as r:
            source = zipfile.ZipFile(io.BytesIO(r.read())).open(MEMBER)
        origin = f"{URL} ({MEMBER})"
    sheet = pd.read_excel(source, sheet_name=f"Year_{args.year}")
    table = borders(sheet).sort_values(["country0", "country1"])
    table["source"] = (
        f"ENTSO-E/ENTSOG TYNDP 2026 scenarios, reference grid {args.year}, NTC "
        f"(Summary Direction 1/2), {origin}, read {datetime.date.today().isoformat()}"
    )
    table.to_csv(args.output, index=False)
    print(table.drop(columns="source").to_string(index=False))
