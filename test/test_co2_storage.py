# SPDX-License-Identifier: MIT
"""Geological CO2 storage limits (scripts/_co2_storage.py, T32)."""

from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts._co2_storage import (
    add_co2_storage_constraints,
    add_co2_storage_limits,
    add_patex_sequestration_limit,
    counted_projects,
    country_storage_limits,
    patex_sequestration_limit,
)

CFG = {"built_only_until": 2030, "undated_from": 2040}
ROOT = Path(__file__).resolve().parents[1]


def projects():
    rows = [
        # country, project, type, status, operation, capacity, fate, hub
        ("NO", "running", "Full chain", "Operational", 1996, 1.0, "Dedicated storage", None),
        ("NO", "building", "T&S", "Under construction", 2028, 1.5, "Dedicated storage", "H"),
        ("NL", "planned 2029", "Storage", "Planned", 2029, 5.0, "Dedicated storage", "A"),
        ("NL", "planned 2035", "T&S", "Planned", 2035, 3.0, "Dedicated storage", "A"),
        ("GB", "undated", "Storage", "Planned", None, 10.0, "Dedicated storage", None),
        ("GB", "no capacity", "Storage", "Planned", 2030, None, "Dedicated storage", None),
        ("NL", "hub member", "Full chain", "Under construction", 2026, 0.8, "Dedicated storage", "A"),
        ("HU", "eor", "Full chain", "Operational", 1992, 0.2, "EOR", None),
        ("NL", "cancelled", "Storage", "Cancelled", 2030, 3.0, "Dedicated storage", "A"),
    ]
    return pd.DataFrame(
        rows,
        columns=["country", "project", "project_type", "project_status", "operation",
                 "capacity_mt", "fate_of_carbon", "part_of_ccus_hub"],
    )


@pytest.mark.parametrize(
    "horizon, expected",
    [
        # up to 2030: built projects only (the planned 2029 site waits)
        (2030, {"running", "building"}),
        (2035, {"running", "building", "planned 2029", "planned 2035", "no capacity"}),
        (2040, {"running", "building", "planned 2029", "planned 2035", "no capacity",
                "undated"}),
    ],
)
def test_counted_projects(horizon, expected):
    # never: a hub member (its CO2 goes to the hub's site), EOR, cancelled
    assert set(counted_projects(projects(), horizon, CFG)["project"]) == expected


def test_country_limits_cover_every_modelled_country():
    limits = country_storage_limits(projects(), 2040, CFG, ["NL", "NO", "DE", "GB"])
    assert limits.to_dict() == {"NL": 8.0, "NO": 2.5, "DE": 0.0, "GB": 10.0}


def network(inherited_nl: float = 0.0) -> pypsa.Network:
    """Two countries; CO2 that pays to be stored at each node (as under a CO2 cap);
    sequestered stores as PyPSA-Eur names them."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2040-01-01", periods=3, freq="h"))
    n.add("Carrier", ["AC", "co2 sequestered"])
    for node, ct in (("NL0 0", "NL"), ("DE0 0", "DE")):
        n.add("Bus", node, country=ct, location=node, carrier="AC")
        bus = f"{node} co2 sequestered"
        n.add("Bus", bus, location=node, carrier="co2 sequestered")
        n.add("Generator", f"{node} co2 source", bus=bus, p_nom=10.0, marginal_cost=-1.0)
        n.add(
            "Store",
            bus,
            bus=bus,
            carrier="co2 sequestered",
            e_nom_extendable=True,
            e_nom_max=1.0,  # a CO2StoP ceiling, replaced by the country cap
        )
    if inherited_nl:
        n.add(
            "Store",
            "NL0 0 co2 sequestered-2030",
            bus="NL0 0 co2 sequestered",
            carrier="co2 sequestered",
            e_nom=inherited_nl,
        )
    return n


def test_country_cap_binds_all_build_years():
    n = network(inherited_nl=6.0)
    add_co2_storage_limits(n, pd.Series({"NL": 4e-6, "DE": 0.0}), nyears=1.0)  # 4 t
    assert (n.stores.loc[n.stores.e_nom_extendable, "e_nom_max"] == float("inf")).all()
    n.optimize(
        solver_name="highs",
        include_objective_constant=False,
        extra_functionality=lambda n, sns: add_co2_storage_constraints(n, sns),
    )
    e = n.stores_t.e.iloc[-1]
    # the 2030 store alone could take 6 t: the fleet is still held at 4 t
    assert e.filter(like="NL0").sum() == pytest.approx(4.0)
    assert e.filter(like="DE0").sum() == pytest.approx(0.0)
    assert n.global_constraints.loc["co2 storage limit NL", "type"] == "co2_storage_limit"


def test_patex_limit_sums_patex_countries_and_needs_the_column(tmp_path):
    fn = tmp_path / "patex_parameters_2040.csv"
    pd.DataFrame({"co2 stored": [1.5, 0.0, 2.0]}, index=["NL", "BE", "DE"]).to_csv(fn)
    total = patex_sequestration_limit(fn, ["NL", "BE", "NO"], fallback=["NO"])
    assert total == pytest.approx(1.5)  # DE not modelled, NO a fallback country
    with pytest.raises(ValueError, match="no PatEx data"):
        patex_sequestration_limit(fn, ["NL", "FR"], fallback=["NO"])
    pd.DataFrame({"other": [1.0]}, index=["NL"]).to_csv(fn)
    with pytest.raises(ValueError, match="re-export"):
        patex_sequestration_limit(fn, ["NL"], fallback=[])


def test_patex_total_cap_counts_inherited_stores():
    n = network(inherited_nl=6.0)
    add_patex_sequestration_limit(n, 5e-6, nyears=1.0)  # 5 t
    n.stores["e_nom_max"] = float("inf")
    n.optimize(solver_name="highs", include_objective_constant=False)
    assert n.stores_t.e.iloc[-1].sum() == pytest.approx(5.0)


def test_project_table_in_the_repository():
    table = pd.read_csv(ROOT / "data" / "co2_storage_projects.csv")
    assert table["source"].notna().all() and table["country"].str.len().eq(2).all()
    totals = [
        country_storage_limits(table, h, CFG, sorted(table["country"].unique())).sum()
        for h in (2030, 2040, 2050)
    ]
    assert 0 < totals[0] <= totals[1] <= totals[2]


def test_one_eu_store_gets_the_sum_of_the_country_caps():
    n = pypsa.Network()
    n.add("Bus", "co2 sequestered", location="EU", carrier="co2 sequestered")
    n.add("Store", "co2 sequestered", bus="co2 sequestered", carrier="co2 sequestered",
          e_nom_extendable=True)
    add_co2_storage_limits(n, pd.Series({"NL": 2.0, "BE": 0.0, "NO": 1.0}), nyears=1.0)
    assert n.global_constraints.loc["co2 storage limit EU", "constant"] == pytest.approx(3e6)
