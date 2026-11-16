# SPDX-License-Identifier: MIT
"""
Refresh ``data/co2_storage_projects.csv`` (``co2_storage`` option, T32) from the IEA
CCUS Projects Database.

    python scripts/update_co2_storage_projects.py [--xlsx "IEA CCUS Projects Database 2026.xlsx"]

The IEA database (CC BY 4.0) lists every large-scale CO2 capture, transport and storage
project with its type, status, FID and operation years and capacity [Mt CO2/a]. The
IEA's own download (iea.org, data product "CCUS Projects Database") needs a free IEA
account: give that file with ``--xlsx``. Without it, the script reads the open mirror
of the same database on KAPSARC's data portal (no login, CSV export).

The table keeps the European projects that can store CO2 (types Storage, T&S and Full
chain), all statuses, with the IEA's columns; which of them count at a planning horizon
is decided by the model (``scripts/_co2_storage.py``), not here.
"""

import argparse
import datetime
import io
import re
import urllib.request
from pathlib import Path

import pandas as pd
import pycountry

KAPSARC_URL = (
    "https://data.kapsarc.org/api/explore/v2.1/catalog/datasets/"
    "iea-ccus-projects-database/exports/csv?delimiter=%2C"
)
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "co2_storage_projects.csv"

#: IEA country labels pycountry does not resolve. Cross-border entries take the first
#: country, where the IEA puts the storage site (PYCASSO: Aquitaine basin, France;
#: Carbon Connect Delta: Dutch North Sea).
ALIASES = {"Island": "IS", "France-Spain": "FR", "Netherlands-Belgium": "NL"}

STORAGE_TYPES = {"storage", "t&s", "full chain"}

COLUMNS = [
    "country",
    "project",
    "project_type",
    "project_status",
    "fid",
    "operation",
    "capacity_mt",
    "fate_of_carbon",
    "part_of_ccus_hub",
    "iea_country",
    "reference",
    "source",
]


def snake(name: str) -> str:
    """IEA xlsx header → KAPSARC field name (``Project Status`` → ``project_status``)."""
    name = re.sub(r"[^0-9a-z]+", "_", name.strip().lower())
    return name.strip("_")


def iso2(label: str) -> str:
    if label in ALIASES:
        return ALIASES[label]
    return pycountry.countries.lookup(label).alpha_2


def load(xlsx: str | None) -> tuple[pd.DataFrame, str]:
    today = datetime.date.today().isoformat()
    if xlsx:
        sheets = pd.read_excel(xlsx, sheet_name=None)
        # the project list is the sheet with a "Project name" column
        raw = next(
            df for df in sheets.values() if "project_name" in map(snake, df.columns)
        )
        raw.columns = [snake(c) for c in raw.columns]
        source = f"IEA CCUS Projects Database ({Path(xlsx).name}), CC BY 4.0, read {today}"
    else:
        with urllib.request.urlopen(KAPSARC_URL, timeout=120) as r:
            raw = pd.read_csv(io.BytesIO(r.read()))
        source = (
            "IEA CCUS Projects Database, CC BY 4.0, KAPSARC mirror "
            f"(data.kapsarc.org, iea-ccus-projects-database), accessed {today}"
        )
    return raw, source


def build(raw: pd.DataFrame, source: str) -> pd.DataFrame:
    df = raw[
        (raw["region"] == "Europe")
        & raw["project_type"].str.lower().isin(STORAGE_TYPES)
    ].copy()
    capacity = df["estimated_capacity_by_iea_mt_co2_yr"].fillna(
        df["announced_capacity_mt_co2_yr"]
    )
    refs = [c for c in df.columns if c.startswith("ref_")]
    out = pd.DataFrame(
        {
            "country": df["country_or_economy"].map(iso2),
            "project": df["project_name"].str.strip(),
            "project_type": df["project_type"].str.strip(),
            "project_status": df["project_status"].str.strip(),
            "fid": pd.to_numeric(df["fid"], errors="coerce").astype("Int64"),
            "operation": pd.to_numeric(df["operation"], errors="coerce").astype("Int64"),
            "capacity_mt": capacity,
            "fate_of_carbon": df["fate_of_carbon"],
            "part_of_ccus_hub": df["part_of_ccus_hub"],
            "iea_country": df["country_or_economy"],
            "reference": df[refs].bfill(axis=1).iloc[:, 0] if refs else "",
            "source": source,
        }
    )
    return out[COLUMNS].sort_values(["country", "project"]).reset_index(drop=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--xlsx", help="IEA CCUS Projects Database file (iea.org)")
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    raw, source = load(args.xlsx)
    table = build(raw, source)
    table.to_csv(args.output, index=False)
    print(
        f"{len(table)} European storage projects written to {args.output}\n"
        + table.groupby("project_status").size().to_string()
    )
