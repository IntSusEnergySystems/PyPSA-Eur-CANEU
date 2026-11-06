# SPDX-License-Identifier: MIT
"""Nuclear fleet rules (scripts/_nuclear_fleet.py, T34)."""

import pandas as pd
import pypsa
import pytest

from scripts._nuclear_fleet import apply_nuclear_fleet, fleet_at_horizon


def fleet():
    return pd.DataFrame(
        {
            "country": ["BE", "BE", "BE", "BE", "BE"],
            "reactor": ["old", "official", "extended", "new", "late"],
            "lat": 50.8,
            "lon": 4.4,
            "net_mw": [1000.0, 1000.0, 1000.0, 1000.0, 1000.0],
            "commissioning_year": [1985, 1980, 1980, 2000, 2032],
            "retirement_year": [None, 2040, 2035, None, None],
            "end_date_includes_extension": [False, False, True, False, False],
            "lifetime": [None, None, None, None, None],
        }
    ).set_index("reactor")


@pytest.mark.parametrize(
    "horizon, usable, extension",
    [
        # old: 1985 + 50 = 2035, extended 2045; official 2040 → 2050;
        # extended: 2035 final; new: 2050 → 2060; late: from 2032.
        # Used if the end after extension is more than 4 years after the horizon.
        (2030, ["old", "official", "extended", "new"], []),
        (2040, ["old", "official", "new", "late"], ["old", "official"]),
        (2050, ["new", "late"], ["new"]),
    ],
)
def test_fleet_at_horizon(horizon, usable, extension):
    out = fleet_at_horizon(fleet(), horizon, 50, 10, 4)
    assert sorted(out.index) == sorted(usable)
    assert sorted(out.index[out.extension]) == sorted(extension)


def network():
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2013-01-01", periods=2, freq="h"))
    n.add("Bus", "BE0 0", carrier="AC", country="BE", x=4.4, y=50.8)
    n.add("Bus", "co2 atmosphere", carrier="co2")
    n.add("Generator", "BE0 0 nuclear", bus="BE0 0", carrier="nuclear", p_nom=5000)
    return n


def costs():
    return pd.DataFrame(
        {
            "efficiency": [0.33, None],
            "VOM": [4.0, None],
            "FOM": [1.0, None],
            "investment": [1e7, None],
            "lifetime": [40.0, None],
            "fuel": [None, 7.5],
            "CO2 intensity": [None, 0.0],
        },
        index=["nuclear", "uranium"],
    )


def test_apply_replaces_generators_and_drops_declined_extension(tmp_path):
    fn = tmp_path / "fleet.csv"
    fleet().reset_index().assign(country="BE").to_csv(fn, index=False)
    options = dict(
        fleet_file=fn,
        default_lifetime=50,
        extension_years=10,
        min_remaining_years=4,
        optional_extension=True,
        must_run_margin=0.1,
    )
    n = network()
    apply_nuclear_fleet(n, None, costs(), 2030, options, None)
    assert not (n.generators.carrier == "nuclear").any()
    links = n.links[n.links.carrier == "nuclear"]
    assert sorted(links.index) == [
        "BE0 0 nuclear extended", "BE0 0 nuclear new", "BE0 0 nuclear official", "BE0 0 nuclear old"
    ]
    assert not links.p_nom_extendable.any()  # nobody in its extension in 2030
    assert links.at["BE0 0 nuclear new", "p_nom"] == pytest.approx(1000 / 0.33)
    assert links.p_min_pu.eq(0.9).all()

    # 2040: "official" is in its extension; if it was declined before (as an
    # extendable link kept at 0), it cannot come back
    n.links.loc["BE0 0 nuclear official", ["p_nom_extendable", "p_nom_opt"]] = [True, 0.0]
    n_next = network()
    apply_nuclear_fleet(n_next, n, costs(), 2040, options, None)
    assert n_next.links.at["BE0 0 nuclear official", "p_nom_max"] == 0.0
    assert n_next.links.at["BE0 0 nuclear late", "p_nom"] > 0
