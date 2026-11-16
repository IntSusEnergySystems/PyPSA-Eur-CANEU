# SPDX-License-Identifier: MIT
"""PatEx electric cooling as its own load (patex.cooling, audit #5b)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import pytest

from scripts.build_patex_cooling import (
    full_load_hours,
    hourly_profiles,
    idees_electric_cooling,
)
from scripts.prepare_sector_network import add_patex_cooling_load, patex_cooling_shape

SNAPSHOTS = pd.date_range("2013-07-01", periods=4, freq="h")
WEIGHTS = pd.Series(1.0, index=SNAPSHOTS)


def hotmaps_slopes():
    """Slope per K: residential = local hour, services = 10 × day type + 1."""
    idx = pd.MultiIndex.from_product(
        [["BE", "GB"], [0, 1, 2], range(1, 25)], names=["country", "day_type", "hour"]
    )
    return pd.DataFrame(
        {
            "residential": idx.get_level_values("hour").astype(float),
            "services": 10.0 * idx.get_level_values("day_type") + 1.0,
        },
        index=idx,
    )


def test_hourly_profiles_local_hour_day_type_and_day():
    # Fri 2013-07-05 and Sat 2013-07-06 (UTC hours 21-23 and 22-23 of Saturday)
    time = pd.DatetimeIndex(
        ["2013-07-05 21:00", "2013-07-05 22:00", "2013-07-06 21:00"]
    )
    daily = pd.DataFrame(
        {"BE0": [2.0, 3.0], "GB0": [1.0, 0.0], "NO0": [5.0, 5.0]},
        index=pd.DatetimeIndex(["2013-07-05", "2013-07-06"]),
    )
    out = hourly_profiles(daily, hotmaps_slopes(), time)
    # BE (CEST, UTC+2): 23:00 Fri, 00:00 Sat, 23:00 Sat -> hours 24, 1, 24
    np.testing.assert_allclose(out["residential"]["BE0"], [24 * 2, 1 * 3, 24 * 3])
    np.testing.assert_allclose(out["services"]["BE0"], [1 * 2, 11 * 3, 11 * 3])
    # GB (BST, UTC+1): 22:00 Fri, 23:00 Fri, 22:00 Sat -> hours 23, 24, 23
    np.testing.assert_allclose(out["residential"]["GB0"], [23, 24, 0])
    # no Hotmaps table (NO): no profile
    assert out["services"]["NO0"].eq(0).all()


def test_full_load_hours():
    p = pd.DataFrame({"BE0": [1.0, 3.0], "BE1": [1.0, 1.0]})
    assert full_load_hours(p)["BE"] == pytest.approx(6 / 4)


def test_shape_splits_country_cooling_over_nodes_and_hours():
    profile = pd.DataFrame(
        {"BE0": [0.0, 1.0, 2.0, 1.0], "BE1": [0.0, 0.0, 4.0, 0.0], "NL0": 0.0},
        index=SNAPSHOTS,
    )
    location = pd.Series({"BE0": "BE0", "BE1": "BE1", "NL0": "NL0"})
    fraction = pd.Series({"BE0": 0.5, "BE1": 0.5, "NL0": 1.0})
    shape = patex_cooling_shape(profile, location, fraction, WEIGHTS)
    # BE: 8 person-K over nodes and hours; BE1 holds 4 of them, in one hour
    assert shape[["BE0", "BE1"]].sum().sum() == pytest.approx(1.0)
    assert shape.at[SNAPSHOTS[2], "BE1"] == pytest.approx(0.5)
    # NL has no cooling degree hour: profile of all nodes, its population share
    assert shape["NL0"].sum() == pytest.approx(1.0)
    np.testing.assert_allclose(shape["NL0"], [0.0, 0.125, 0.75, 0.125])


def test_cooling_load_on_the_bus_of_the_electricity_load():
    n = pypsa.Network()
    n.set_snapshots(SNAPSHOTS)
    n.add("Bus", ["BE0", "BE0 low voltage"])
    n.add("Load", "BE0", bus="BE0 low voltage", carrier="electricity", p_set=1.0)
    p = pd.DataFrame({"BE0": [0.0, 1.0, 2.0, 3.0]}, index=SNAPSHOTS)
    add_patex_cooling_load(n, pd.Index(["BE0"]), p)
    assert n.loads.at["BE0 electricity cooling", "bus"] == "BE0 low voltage"
    assert n.loads.at["BE0 electricity cooling", "carrier"] == "electricity cooling"
    np.testing.assert_allclose(n.loads_t.p_set["BE0 electricity cooling"], [0, 1, 2, 3])


IDEES = Path("data/jrc_idees/archive/2023-v1")


@pytest.mark.skipif(not (IDEES / "DE").exists(), reason="JRC-IDEES not retrieved")
def test_idees_electric_cooling_by_sector_years_clamped():
    res = idees_electric_cooling(str(IDEES), "DE", [2013], "residential")
    ser = idees_electric_cooling(str(IDEES), "DE", [2013], "services")
    assert 0.5 < res < ser < 20.0  # TWh: services cool most
    assert idees_electric_cooling(str(IDEES), "DE", [2030], "services") == pytest.approx(
        idees_electric_cooling(str(IDEES), "DE", [2023], "services")
    )
    assert np.isnan(idees_electric_cooling(str(IDEES), "NO", [2013], "services"))


def test_shape_warns_only_for_listed_countries(caplog):
    profile = pd.DataFrame({"BE0": [0.0, 1.0, 1.0, 0.0], "NO0": 0.0}, index=SNAPSHOTS)
    location = pd.Series({"BE0": "BE0", "NO0": "NO0"})
    fraction = pd.Series({"BE0": 1.0, "NO0": 1.0})
    with caplog.at_level("WARNING"):
        patex_cooling_shape(profile, location, fraction, WEIGHTS, countries=["BE"])
    assert "NO" not in caplog.text
    with caplog.at_level("WARNING"):
        patex_cooling_shape(profile, location, fraction, WEIGHTS)
    assert "PatEx cooling NO" in caplog.text
