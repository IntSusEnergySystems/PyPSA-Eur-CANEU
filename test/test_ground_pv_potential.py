# SPDX-License-Identifier: MIT
"""Slope from GEBCO in ``scripts/update_ground_pv_potential.py`` (2026-11-12)."""

import sys
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from update_ground_pv_potential import slope_from_gebco  # noqa: E402


def test_slope_from_gebco_plane_and_sea(tmp_path):
    """A north-south ramp of 1 m per 100 m gives atan(0.01); the sea counts as 0 m."""
    res = 1 / 120
    rows, cols = 40, 30
    dy = 111320.0 * res
    z = np.tile((np.arange(rows)[::-1] * dy * 0.01)[:, None], (1, cols))
    z[:, :5] = -50.0  # sea on the west edge
    path = tmp_path / "dem.tif"
    transform = rasterio.transform.from_origin(4.0, 50.0, res, res)
    with rasterio.open(path, "w", driver="GTiff", height=rows, width=cols, count=1,
                       dtype="float64", crs="EPSG:4326", transform=transform) as out:
        out.write(z, 1)
    with slope_from_gebco(path) as slope:
        s = slope.read(1)
    assert np.allclose(s[5:-5, 10:-5], np.degrees(np.arctan(0.01)), rtol=1e-3)
    assert np.allclose(s[:, :4], 0.0)  # flat sea, not the bathymetry
