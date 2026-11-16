# SPDX-License-Identifier: MIT
"""GB load scaled to DUKES 'electricity available' (patex.gb_load_dukes)."""

import numpy as np
import pandas as pd
import pytest

from scripts.build_electricity_demand import scale_gb_to_dukes


def test_gb_scaled_to_dukes_shape_kept_others_untouched():
    idx = pd.date_range("2023-01-01", "2024-01-01", freq="h", inclusive="left")
    gb = pd.Series(np.linspace(20_000.0, 40_000.0, len(idx)), index=idx)
    load = pd.DataFrame({"GB": gb, "FR": 50_000.0})
    out = scale_gb_to_dukes(load, pd.Series({2023: 304.08}))
    assert out["GB"].sum() / 1e6 == pytest.approx(304.08)
    np.testing.assert_allclose(out["GB"] / out["GB"].sum(), gb / gb.sum())
    assert out["FR"].equals(load["FR"])


def test_partial_year_pro_rata_and_missing_year_fails():
    idx = pd.date_range("2023-07-01", periods=24, freq="h")
    load = pd.DataFrame({"GB": 1000.0}, index=idx)
    out = scale_gb_to_dukes(load, pd.Series({2023: 8760.0}))  # 1 TWh per hour
    assert out["GB"].sum() == pytest.approx(24e6)
    with pytest.raises(ValueError):
        scale_gb_to_dukes(load, pd.Series({2019: 1.0}))
