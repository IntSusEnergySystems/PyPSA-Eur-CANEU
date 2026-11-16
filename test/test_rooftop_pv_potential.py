# SPDX-License-Identifier: MIT
"""Rooftop PV potential per country (``renewable_limits.rooftop_pv_file``, 2026-11-12)."""

import pandas as pd

from scripts.build_solar_rooftop_potentials import scale_to_country_totals


def test_country_total_spread_by_population_others_unchanged():
    idx = pd.MultiIndex.from_tuples(
        [("BE0 0", 0), ("BE0 0", 1), ("BE1 0", 0), ("NL0 0", 0)], names=["bus", "bin"]
    )
    pot = pd.Series([10.0, 30.0, 60.0, 50.0], index=idx)  # MW at 2 kW/person
    out = scale_to_country_totals(pot, pd.Series({"BE": 1.0, "FR": 5.0}))  # GW
    assert out[out.index.get_level_values("bus").str.startswith("BE")].sum() == 1000.0
    assert out[("BE0 0", 1)] == 300.0  # 30 % of BE's population
    assert out[("NL0 0", 0)] == 50.0  # not in the file
