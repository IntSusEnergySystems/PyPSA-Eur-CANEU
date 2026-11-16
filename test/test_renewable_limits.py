# SPDX-License-Identifier: MIT
"""Wind and solar caps per country (scripts/_renewable_limits.py, T31)."""

from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts._renewable_limits import (
    add_renewable_limit_constraints,
    apply_renewable_limits,
    country_caps,
    scale_offshore_potentials,
)

CFG = {"offshore_goal_year": 2050, "planned_until": 2030}
ROOT = Path(__file__).resolve().parents[1]


def goals():
    return pd.DataFrame(
        {"country": ["BE", "NL"], "gw_2030": [6.0, 16.0], "gw_2040": [8.0, 50.0],
         "gw_2050": [8.0, 72.0]}
    )


def planned():
    return pd.DataFrame(
        {"country": ["BE", "NL"], "onwind": [8.0, 9.0], "offwind": [5.0, None],
         "solar": [20.0, None]}
    )


def test_caps_by_horizon():
    early = country_caps(2030, CFG, goals(), planned())
    # 2030: planned capacity; NL has no planned offshore value -> its 2030 goal
    assert early["offwind"].to_dict() == {"BE": 5000, "NL": 16000}
    assert early["onwind"]["BE"] == 8000 and "NL" not in early["solar"]
    late = country_caps(2040, CFG, goals(), planned())
    # after 2030: offshore at the 2050 goal, no cap on onshore wind and solar
    assert late["offwind"].to_dict() == {"BE": 8000, "NL": 72000}
    assert set(late) == {"offwind"}


def network():
    """BE: 2 GW existing offshore, two extendable offshore sites (PyPSA-Eur potential
    1 GW each), onshore wind; all free and worth building."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2030-01-01", periods=2, freq="h"))
    n.add("Carrier", ["AC", "offwind-ac", "offwind-dc", "onwind"])
    n.add("Bus", "BE0 0", country="BE", carrier="AC")
    n.add("Load", "load", bus="BE0 0", p_set=1e5)
    n.add("Generator", "backup", bus="BE0 0", p_nom=1e5, marginal_cost=1e3)
    n.add("Generator", "BE0 0 offwind-ac-2020", bus="BE0 0", carrier="offwind-ac",
          p_nom=2000)
    for c in ("offwind-ac", "offwind-dc"):
        n.add("Generator", f"BE0 0 {c}", bus="BE0 0", carrier=c, p_nom_extendable=True,
              p_nom_max=1000, capital_cost=1.0)
    n.add("Generator", "BE0 0 onwind", bus="BE0 0", carrier="onwind",
          p_nom_extendable=True, p_nom_max=50000, capital_cost=1.0)
    return n


@pytest.mark.parametrize("horizon, offwind, onwind", [(2030, 5000, 8000), (2040, 8000, 50000)])
def test_caps_bind_on_existing_plus_new(horizon, offwind, onwind):
    n = network()
    factors = scale_offshore_potentials(n, horizon, CFG, goals(), planned())
    # BE cap (5 GW in 2030, 8 GW after) above its potential (2 x 1 GW): each class
    # scaled by cap / potential, shares kept
    assert factors.to_dict() == {"BE": pytest.approx(offwind / 2000)}
    ext = n.generators.filter(like="offwind", axis=0).query("p_nom_extendable")
    assert ext.p_nom_max.tolist() == pytest.approx([offwind / 2] * 2)
    apply_renewable_limits(n, horizon, CFG, goals(), planned())
    n.optimize(solver_name="highs", include_objective_constant=False,
               extra_functionality=lambda n, sns: add_renewable_limit_constraints(n))
    off = n.generators.carrier.str.startswith("offwind")
    assert n.generators.p_nom_opt[off].sum() == pytest.approx(offwind)
    assert n.generators.p_nom_opt["BE0 0 onwind"] == pytest.approx(onwind)


def test_class_limits_kept_where_cap_below_potential():
    """Audit #3: a country whose goal fits in its potential keeps PyPSA-Eur's class
    limits; the best class cannot take the whole goal."""
    n = network()
    n.generators.loc["BE0 0 offwind-ac", "p_nom_max"] = 3000  # best class, cheaper
    n.generators.loc["BE0 0 offwind-ac", "capital_cost"] = 0.5
    n.generators.loc["BE0 0 offwind-dc", "p_nom_max"] = 20000
    factors = scale_offshore_potentials(n, 2040, CFG, goals(), planned())
    assert factors.empty
    assert n.generators.at["BE0 0 offwind-ac", "p_nom_max"] == 3000
    apply_renewable_limits(n, 2040, CFG, goals(), planned())
    n.optimize(solver_name="highs", include_objective_constant=False,
               extra_functionality=lambda n, sns: add_renewable_limit_constraints(n))
    assert n.generators.p_nom_opt["BE0 0 offwind-ac"] == pytest.approx(3000)
    assert n.generators.p_nom_opt["BE0 0 offwind-dc"] == pytest.approx(3000)  # 8-2-3


def test_scaled_room_covers_cap_after_brownfield():
    """Scaling comes before existing capacity is subtracted per class: even when the
    existing capacity sits above its scaled class, the room left covers cap - existing."""
    from scripts.add_brownfield import adjust_renewable_capacity_limits

    n = pypsa.Network()
    n.add("Bus", "BE0 0", country="BE", carrier="AC")
    for k, pot in (("0", 600.0), ("1", 400.0)):
        n.add("Generator", f"BE0 0 {k} offwind-ac-2040", bus="BE0 0",
              carrier="offwind-ac", p_nom_extendable=True, p_nom_max=pot)
    scale_offshore_potentials(n, 2040, CFG, goals(), planned())  # x8: 4.8 + 3.2 GW
    n.add("Generator", "BE0 0 1 offwind-ac-2030", bus="BE0 0", carrier="offwind-ac",
          p_nom=4000)  # existing, above its scaled class (3.2 GW)
    adjust_renewable_capacity_limits(n, "2040", ["offwind-ac"])
    room = n.generators.query("p_nom_extendable").p_nom_max
    assert room.to_dict() == {"BE0 0 0 offwind-ac-2040": pytest.approx(4800),
                              "BE0 0 1 offwind-ac-2040": 0.0}
    assert room.sum() >= 8000 - 4000


def test_existing_above_cap_allows_no_new_build():
    n = network()
    small = goals().assign(gw_2030=[1.0, 16.0])
    apply_renewable_limits(n, 2030, CFG, small, None)
    n.optimize(solver_name="highs", include_objective_constant=False,
               extra_functionality=lambda n, sns: add_renewable_limit_constraints(n))
    assert n.generators.p_nom_opt.filter(like="offwind").sum() == pytest.approx(2000)


def test_goals_file_in_the_repository():
    g = pd.read_csv(ROOT / "data" / "offshore_wind_goals.csv")
    assert g["country"].is_unique and g["country"].str.len().eq(2).all()
    years = g[["gw_2030", "gw_2040", "gw_2050"]]
    assert (years.diff(axis=1).iloc[:, 1:] >= 0).all().all()  # goals never decrease
    goals_ms = g[g["basis"] == "Member State goal"]  # not SE, GB, NO (ENTSO-E data)
    assert 330 < goals_ms["gw_2050"].sum() < 360  # Commission: 281-354 GW (January 2023)


def test_planned_file_in_the_repository():
    t = pd.read_csv(ROOT / "data" / "renewables_planned_2030.csv").set_index("country")
    eu = ("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI "
          "ES SE").split()
    # TYNDP 2026 NT+ 2030, EU27 (report data figure 57): onshore 331.01, offshore 65.27
    assert t.loc[eu, "onwind"].sum() == pytest.approx(331.01, abs=0.05)
    assert t.loc[eu, "offwind"].sum() == pytest.approx(65.27, abs=0.05)
    assert t.loc[["AT", "CH", "HU", "EE"], "solar"].isna().all()  # no solar cap there


def test_ground_pv_cap_on_utility_and_tracking_pv():
    """Ground-mounted PV (utility + single-axis tracking) capped per country at every
    horizon from ``ground_pv_file``; rooftop PV is not in the group (2026-11-10)."""
    import pandas as pd

    from scripts._renewable_limits import GROUPS, country_caps

    assert GROUPS["solar ground"] == ["solar", "solar-hsat"]
    goals = pd.DataFrame({"country": ["BE"], "gw_2030": [5.8], "gw_2050": [8.0]})
    ground = pd.DataFrame({"country": ["BE", "NL"], "cap_gw": [38.55, 37.39]})
    cfg = {"planned_until": 2030, "offshore_goal_year": 2050}
    for horizon in (2030, 2050):
        caps = country_caps(horizon, cfg, goals, None, ground)
        assert caps["solar ground"]["BE"] == pytest.approx(38550.0)
        assert caps["solar ground"]["NL"] == pytest.approx(37390.0)
    assert "solar ground" not in country_caps(2050, cfg, goals, None)
