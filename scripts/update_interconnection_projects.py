# SPDX-License-Identifier: MIT
"""
Refresh ``data/interconnection_projects_tyndp2024.csv`` (``interconnection_limits``,
T30) from the ENTSO-E TYNDP 2024 transmission projects.

    python scripts/update_interconnection_projects.py [--xlsx 20250312_export_transmission.xlsx]

Source: ENTSO-E TYNDP 2024 cost-benefit analysis export of the transmission projects
(``20250312_export_transmission.xlsx``, sheet ``Trans.Projects``: one row per project with
the promoter's commissioning year, status, borders and "Transfer capacity increase A-B /
B-A (MW)"), as distributed by Open-TYNDP (``CBA_projects.zip``; project sheets at
tyndp2024.entsoe.eu). TYNDP publishes no line ratings or coordinates per project: the
transfer-capacity increase is the only capacity given (for DC projects it is the
converter rating).

One output row per project and border between two countries (market zones mapped to
countries by their first two letters: UK → GB, PLI0 / PL00E / PL00I → PL; rows inside a
country or towards a non-European zone are kept with their country codes and filtered by
the model). Commissioning year: the last year written by the promoter ("2030/2032" →
2032, "12-2027" → 2027). ``in_pypsa_eur_tyndp2020``: the project ID is among the TYNDP
2020 new AC lines PyPSA-Eur already adds as existing (``data/transmission_projects/
tyndp2020/new_lines.csv`` with the default statuses), so its capacity is already in the
grid and must not be added a second time.
"""

import argparse
import datetime
import io
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://storage.googleapis.com/open-tyndp-data-store/2024/CBA_projects.zip"
MEMBER = "20250312_export_transmission.xlsx"
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "interconnection_projects_tyndp2024.csv"
TYNDP2020_LINES = ROOT / "data" / "transmission_projects" / "tyndp2020" / "new_lines.csv"
#: statuses PyPSA-Eur adds as existing by default (`transmission_projects.status`)
TYNDP2020_STATUS = {"under_construction", "in_permitting", "confirmed"}
#: column positions in sheet Trans.Projects (header on the second row)
COLS = {0: "project_id", 1: "project", 6: "commissioning", 7: "status_id",
        8: "cross_border", 22: "border", 23: "mw_a_to_b", 24: "mw_b_to_a"}


def country(zone: str) -> str:
    zone = zone.strip()
    return {"UK": "GB"}.get(zone[:2], zone[:2])


def last_year(text) -> float:
    years = re.findall(r"(20\d\d)", str(text))
    return float(years[-1]) if years else float("nan")


def tyndp2020_ids() -> set[str]:
    lines = pd.read_csv(TYNDP2020_LINES, index_col=0)
    lines = lines[lines["project_status"].isin(TYNDP2020_STATUS)]
    return set(lines["tags"].str.extract(r'tyndp2020_proj_id"=>"(\d+)')[0].dropna())


def build(sheet: pd.DataFrame, source: str) -> pd.DataFrame:
    body = sheet.iloc[2:, list(COLS)].set_axis(list(COLS.values()), axis=1)
    body = body[pd.to_numeric(body["project_id"], errors="coerce").notna()]
    rows = []
    for _, p in body.iterrows():
        borders = str(p["border"]).split("\n")
        ab = str(p["mw_a_to_b"]).split("\n")
        ba = str(p["mw_b_to_a"]).split("\n")
        for i, border in enumerate(borders):
            zones = [z for z in re.split(r"\s*-\s*", border.strip()) if z]
            if len(zones) != 2:
                continue
            rows.append({
                "project_id": int(p["project_id"]),
                "project": str(p["project"]).strip(),
                "zone0": zones[0], "zone1": zones[1],
                "country0": country(zones[0]), "country1": country(zones[1]),
                "mw_0to1": pd.to_numeric(ab[i] if i < len(ab) else None, errors="coerce"),
                "mw_1to0": pd.to_numeric(ba[i] if i < len(ba) else None, errors="coerce"),
                "commissioning_year": last_year(p["commissioning"]),
                "commissioning_text": str(p["commissioning"]).strip(),
                "status_id": pd.to_numeric(p["status_id"], errors="coerce"),
            })
    out = pd.DataFrame(rows)
    out["in_pypsa_eur_tyndp2020"] = out["project_id"].astype(str).isin(tyndp2020_ids())
    out["source"] = source
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--xlsx", help=f"{MEMBER} (default: download)")
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    if args.xlsx:
        source, origin = args.xlsx, Path(args.xlsx).name
    else:
        with urllib.request.urlopen(URL, timeout=300) as r:
            source = zipfile.ZipFile(io.BytesIO(r.read())).open(MEMBER)
        origin = f"{URL} ({MEMBER})"
    sheet = pd.read_excel(source, sheet_name="Trans.Projects", header=None)
    table = build(
        sheet,
        f"ENTSO-E TYNDP 2024 transmission projects (CBA export 2025-03-12), {origin}, "
        f"read {datetime.date.today().isoformat()}",
    )
    table.to_csv(args.output, index=False)
    cross = table[table.country0 != table.country1]
    print(f"{len(table)} rows, {len(cross)} cross-border, "
          f"{cross.in_pypsa_eur_tyndp2020.sum()} already in PyPSA-Eur (TYNDP 2020 AC lines)")
    print(cross.drop(columns=["source", "project"]).to_string(index=False))
