# SPDX-License-Identifier: MIT
"""
Refresh ``data/renewables_planned_2030.csv`` (``renewable_limits`` option, T31) from the
ENTSO-E / ENTSOG TYNDP 2026 scenarios, National Trends+ (NT+).

    python scripts/update_renewables_planned.py [--xlsx NT+_KPI_Dashboard.xlsx] [--year 2030]

NT+ is the central TYNDP 2026 scenario, built on the Member States' final updated
NECPs (2024-2025) and the TSOs' national data. Its KPI dashboard
(2026-data.entsos-tyndp-scenarios.eu, "NT+_KPI_Dashboard.xlsx", one sheet per country)
gives the installed capacity per technology as a model *input* ("I"). The script reads
Wind Onshore, Wind Offshore Radial + Hub and Solar PV for ``--year`` (column "Weighted
WS"), in GW. UK and NI (Northern Ireland) are summed into GB. Solar is left empty
(no cap) where the dashboard leaves out behind-the-meter PV (AT, CH, HU) or has none.
"""

import argparse
import datetime
import io
import urllib.request
from pathlib import Path

import pandas as pd

URL = (
    "https://2026-data.entsos-tyndp-scenarios.eu/output/model-results/kpi-dashboards/"
    "NT+_KPI_Dashboard.xlsx"
)
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "renewables_planned_2030.csv"
ROWS = {
    "Wind Onshore": "onwind",
    "Wind Offshore Radial": "offwind",
    "Wind Offshore Hub": "offwind",
    "Solar PV": "solar",
}
#: dashboard sheet → PyPSA-Eur country
SHEETS = {"UK": "GB", "NI": "GB"}
SKIP = {"Info", "EU27"}
#: Solar PV in the dashboard leaves out behind-the-meter PV for AT, CH, HU (dashboard
#: "Info" sheet); no solar value at all for EE: no solar cap there (empty cell)
NO_SOLAR = {"AT", "CH", "HU"}


def read(source, year: int) -> pd.DataFrame:
    sheets = pd.read_excel(source, sheet_name=None, header=None)
    rows = []
    for name, df in sheets.items():
        if name in SKIP:
            continue
        header = df.iloc[2].ffill()  # horizon of each column
        cols = df.columns[(header == year) & (df.iloc[3] == "Weighted WS")]
        if len(cols) != 1:
            raise ValueError(f"{name}: no single 'Weighted WS' column for {year}")
        # only the "Installed Capacity [GW]" block, up to the next block title
        # ("Generation [TWh]", ...): the same labels come back in every block
        blocks = df[0].where(df[0].astype(str).str.contains(r"\[", regex=True)).ffill()
        tech = df[1].astype(str).str.strip().where(blocks == "Installed Capacity [GW]")
        values = pd.to_numeric(df[cols[0]], errors="coerce").fillna(0.0)
        for label, group in ROWS.items():
            rows.append((SHEETS.get(name, name), group, values[tech == label].sum()))
    out = pd.DataFrame(rows, columns=["country", "group", "gw"])
    return out.pivot_table(index="country", columns="group", values="gw", aggfunc="sum")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--xlsx", help="NT+_KPI_Dashboard.xlsx (default: download)")
    parser.add_argument("--year", type=int, default=2030)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    if args.xlsx:
        source, origin = args.xlsx, Path(args.xlsx).name
    else:
        with urllib.request.urlopen(URL, timeout=300) as r:
            source = io.BytesIO(r.read())
        origin = URL
    table = read(source, args.year).round(3)
    table.loc[table.index.isin(NO_SOLAR) | (table["solar"] == 0), "solar"] = None
    table["source"] = (
        f"ENTSO-E/ENTSOG TYNDP 2026 scenarios, National Trends+ {args.year} installed "
        f"capacity (input), {origin}, read {datetime.date.today().isoformat()}"
    )
    table.reset_index()[["country", "onwind", "offwind", "solar", "source"]].to_csv(
        args.output, index=False
    )
    print(table.drop(columns="source").to_string())
