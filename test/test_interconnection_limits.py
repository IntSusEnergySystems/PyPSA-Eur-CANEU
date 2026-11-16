# SPDX-License-Identifier: MIT
"""Cross-border capacity per border (scripts/_interconnection_limits.py, T30)."""

from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts._interconnection_limits import (
    add_interconnection_constraints,
    apply_interconnection_limits,
    factor_at,
    project_increase,
)

ROOT = Path(__file__).resolve().parents[1]
CFG = {"direction": "max", "factor": {2030: 1.0, 2040: 1.5}, "project_statuses": [2, 3, 4],
       "in_grid_until": 2025}


def projects():
    rows = [
        # id, c0, c1, 0to1, 1to0, year, status, already in PyPSA-Eur
        (1, "BE", "NL", 1000, 600, 2028, 4, False),   # counted from 2030
        (2, "BE", "NL", 500, 500, 2036, 2, False),    # counted from 2040
        (3, "NL", "BE", 700, 700, 2029, 3, True),     # already a PyPSA-Eur line
        (4, "BE", "NL", 900, 900, 2024, 4, False),    # already in the OSM grid
        (5, "BE", "NL", 2000, 2000, 2035, 1, False),  # under consideration
        (6, "BE", "BE", 800, 800, 2028, 4, False),    # internal
    ]
    return pd.DataFrame(rows, columns=["project_id", "country0", "country1", "mw_0to1",
                                       "mw_1to0", "commissioning_year", "status_id",
                                       "in_pypsa_eur_tyndp2020"])


def test_project_increase_by_horizon():
    assert project_increase(projects(), 2030, CFG).to_dict() == {"BE-NL": 1000}
    assert project_increase(projects(), 2040, CFG).to_dict() == {"BE-NL": 1500}
    assert factor_at(CFG["factor"], 2050) == 1.5
    with pytest.raises(ValueError):
        factor_at(CFG["factor"], 2025)


def network(existing_ac=1000.0):
    """BE exports cheap power to NL over an AC line (s_max_pu 0.7) and a DC candidate."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2030-01-01", periods=2, freq="h"))
    for b, ct in (("BE0 0", "BE"), ("NL0 0", "NL")):
        n.add("Bus", b, country=ct, carrier="AC")
    n.add("Generator", "cheap", bus="BE0 0", p_nom=1e5, marginal_cost=1.0)
    n.add("Generator", "dear", bus="NL0 0", p_nom=1e5, marginal_cost=1e3)
    n.add("Load", "load", bus="NL0 0", p_set=2e4)
    n.add("Line", "ac", bus0="BE0 0", bus1="NL0 0", x=0.1, r=0.01, s_nom=existing_ac,
          s_nom_min=existing_ac, s_nom_extendable=True, s_nom_max=1e5, s_max_pu=0.7,
          capital_cost=1.0)
    n.add("Link", "dc", bus0="BE0 0", bus1="NL0 0", carrier="DC", p_nom=0,
          p_nom_extendable=True, p_nom_max=1e5, p_min_pu=-1, capital_cost=1.0)
    return n


def test_reversed_dc_copy_counted_once():
    """transmission_efficiency splits a DC link into a forward and a "-reversed" link
    of the same capacity: the border's capacity is the forward one."""
    from scripts._interconnection_limits import base_capacity

    n = network(existing_ac=0.0)
    n.links["reversed"] = False
    n.add("Link", "nemo", bus0="BE0 0", bus1="NL0 0", carrier="DC", p_nom=1000.0)
    n.add("Link", "nemo-reversed", bus0="NL0 0", bus1="BE0 0", carrier="DC",
          p_nom=1000.0)
    n.links.loc["nemo-reversed", "reversed"] = True  # other links: NaN, read as False
    assert base_capacity(n)["BE-NL"] == pytest.approx(1000.0)


def solve(n):
    n.optimize(solver_name="highs", include_objective_constant=False,
               extra_functionality=lambda n, sns: add_interconnection_constraints(n))
    return n.lines.s_nom_opt["ac"] * 0.7 + n.links.p_nom_opt["dc"]


@pytest.mark.parametrize(
    "horizon, usable",
    [
        (2030, 700 + 1000),            # grid (1000 MW x 0.7) + project 1
        (2040, 1.5 * (700 + 1500)),    # 1.5 x (grid + projects 1 and 2)
    ],
)
def test_usable_capacity_capped(horizon, usable):
    n = network()
    table = apply_interconnection_limits(n, horizon, CFG, projects())
    assert table.loc["BE-NL", "base"] == pytest.approx(700)
    assert solve(n) == pytest.approx(usable)


def test_project_files_in_the_repository():
    p = pd.read_csv(ROOT / "data" / "interconnection_projects_tyndp2024.csv")
    assert p["source"].notna().all() and p["in_pypsa_eur_tyndp2020"].any()
    t = pd.read_csv(ROOT / "data" / "interconnection_ntc_2030.csv")
    assert (t["country0"] < t["country1"]).all()
