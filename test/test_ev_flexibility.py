# SPDX-License-Identifier: MIT
"""EV flexibility after Elia AdeqFlex (scripts/_ev_flexibility.py, T16)."""

import numpy as np
import pandas as pd
import pytest

from scripts._ev_flexibility import (
    by_horizon,
    charging_shape,
    rescale_availability,
    split_demand,
)


def test_rescale_availability_keeps_shape_and_floor():
    base_max, base_mean = 0.95, 0.8
    x = np.array([0.0, 1.0, 3.0])  # traffic position: 0 = least traffic, 1 = mean
    avail = pd.DataFrame({"n": base_max - (base_max - base_mean) * x})
    out = rescale_availability(avail, base_max, base_mean, 0.4, 0.32, 0.2)["n"].values
    assert out == pytest.approx([0.4, 0.32, 0.2])  # 0.4 - 0.08 * 3 = 0.16 floored at 0.2


def test_charging_shape_follows_local_time(tmp_path):
    curve = np.zeros(24)
    curve[9] = 1.0  # all charging at 09:00 local
    fn = tmp_path / "profiles.csv"
    pd.DataFrame({"hour": range(24), "year": 2026, "natural": curve}).to_csv(fn, index=False)
    snapshots = pd.date_range("2013-01-01", periods=48, freq="h")
    shape = charging_shape(fn, snapshots, pd.Series({"BE0 0": "BE", "PT0 0": "PT"}), 2030, {"natural": 1.0})
    assert shape.sum().tolist() == pytest.approx([1.0, 1.0])
    assert set(shape.index[shape["BE0 0"] > 0].hour) == {8}  # 09:00 CET = 08:00 UTC
    assert set(shape.index[shape["PT0 0"] > 0].hour) == {9}
    with pytest.raises(ValueError, match="sum to 1"):
        charging_shape(fn, snapshots, pd.Series({"BE0 0": "BE"}), 2030, {"natural": 0.5})


def test_split_conserves_energy():
    snapshots = pd.date_range("2013-01-01", periods=24, freq="h")
    profile = pd.DataFrame({"a": np.linspace(1, 2, 24), "b": 3.0}, index=snapshots)
    shape = pd.DataFrame(1 / 24, index=snapshots, columns=["a", "b"])
    flexible, inflexible = split_demand(profile, shape, 0.18)
    assert (flexible + inflexible).sum().values == pytest.approx(profile.sum().values)
    assert flexible.sum().values == pytest.approx(0.18 * profile.sum().values)


def test_by_horizon_holds_earlier_value():
    assert by_horizon({2030: 0.07, 2040: 0.18}, 2045) == 0.18
    with pytest.raises(ValueError):
        by_horizon({2030: 0.07}, 2025)
