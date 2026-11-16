# SPDX-License-Identifier: MIT
"""build_heat_demand subtracts the electric heating that is in the measured load
(audit #5): PyPSA-Eur's values when given, while the heat demand stays PatEx's."""

from itertools import product

import numpy as np
import pandas as pd
import pypsa
import xarray as xr

from scripts.prepare_sector_network import build_heat_demand

USES = [f"{s} {u}" for s, u in product(["residential", "services"], ["water", "space"])]


def setup(tmp_path):
    snapshots = pd.date_range("2013-01-01", periods=4, freq="h")
    n = pypsa.Network()
    n.set_snapshots(snapshots)
    n.add("Bus", "BE0")
    n.add("Load", "BE0", bus="BE0", carrier="electricity", p_set=pd.Series(100.0, snapshots))
    shape = np.array([4.0, 3.0, 2.0, 1.0])
    ds = xr.Dataset(
        {u: (("snapshots", "node"), shape[:, None]) for u in USES},
        coords={"snapshots": snapshots, "node": ["BE0"]},
    )
    path = tmp_path / "hourly_heat_demand.nc"
    ds.to_netcdf(path)

    def totals(elec):  # TWh, each use
        return pd.DataFrame(
            {**{f"total {u}": [1e-4] for u in USES}, **{f"electricity {u}": [elec] for u in USES}},
            index=["BE0"],
        )

    eff = {f"total {u} efficiency": {"BE": 0.9} for u in USES}
    return n, path, totals, eff


def test_default_subtracts_totals(tmp_path):
    n, path, totals, eff = setup(tmp_path)
    build_heat_demand(n, path, totals(1e-5), eff)
    # 4 uses × 10 MWh spread over shape 0.4, 0.3, 0.2, 0.1
    np.testing.assert_allclose(n.loads_t.p_set["BE0"], [84.0, 88.0, 92.0, 96.0])


def test_electric_heat_in_load_used_for_subtraction_only(tmp_path):
    n, path, totals, eff = setup(tmp_path)
    patex, today = totals(5e-5), totals(1e-5)
    heat = build_heat_demand(
        n, path, patex, eff, electric_heat_in_load=today[[f"electricity {u}" for u in USES]]
    )
    # load: today's electric heating removed, not PatEx's
    np.testing.assert_allclose(n.loads_t.p_set["BE0"], [84.0, 88.0, 92.0, 96.0])
    # heat demand: PatEx totals × efficiency
    assert np.isclose(heat.sum().sum(), 4 * 100.0 * 0.9)


def test_horizon_heat_shape_for_demand_weather_year_shape_for_load(tmp_path):
    n, path, totals, eff = setup(tmp_path)
    snapshots = n.snapshots
    shifted = tmp_path / "hourly_heat_demand_horizon.nc"
    xr.Dataset(
        {u: (("snapshots", "node"), np.array([[1.0], [1.0], [1.0], [1.0]])) for u in USES},
        coords={"snapshots": snapshots, "node": ["BE0"]},
    ).to_netcdf(shifted)
    heat = build_heat_demand(
        n, path, totals(1e-5), eff, heat_demand_horizon_file=shifted
    )
    # electric heating in the measured load: weather year's shape (0.4 ... 0.1)
    np.testing.assert_allclose(n.loads_t.p_set["BE0"], [84.0, 88.0, 92.0, 96.0])
    # heat demand: the horizon's (flat) shape, same annual total
    values = heat.to_numpy().ravel()
    np.testing.assert_allclose(values, values[0])  # flat
    assert np.isclose(values.sum(), 4 * 100.0 * 0.9)
