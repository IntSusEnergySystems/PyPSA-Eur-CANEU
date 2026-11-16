# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Build solar rooftop capacity potentials per clustered region and resource class.

The gridded total population layout is summed over each solar resource class
region using the cutout indicator matrix. The potential assumes 20 m2 of
usable roof area per person and 0.1 kW per m2, i.e. 2 kW per person. The
result in MW caps the solar rooftop capacity expansion in the network.

With ``renewable_limits.rooftop_pv_file`` (country totals [GW], JRC 2026 building-level
technical potential) × ``renewable_limits.rooftop_pv_share``, each listed country's
total is spread over its regions in proportion to population instead; other countries
keep 2 kW per person.
"""

import geopandas as gpd
import pandas as pd
import xarray as xr

from scripts._helpers import load_cutout, set_scenario_config


def scale_to_country_totals(potentials: pd.Series, totals_gw: pd.Series) -> pd.Series:
    """Potentials [MW] indexed (bus, bin): for each country of ``totals_gw`` (bus names
    start with the country code), the country total spread by the existing (population)
    shares; other countries unchanged."""
    country = potentials.index.get_level_values("bus").str[:2]
    out = potentials.copy()
    for ct, gw in totals_gw.items():
        mask = country == ct
        if mask.any() and potentials[mask].sum() > 0:
            out[mask] = potentials[mask] / potentials[mask].sum() * gw * 1e3
    return out

if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "build_solar_rooftop_potentials",
            configfiles="config/test/config.myopic.yaml",
        )

    set_scenario_config(snakemake)

    cutout = load_cutout(snakemake.input.cutout)

    class_regions = gpd.read_file(snakemake.input.class_regions).set_index(
        ["bus", "bin"]
    )

    I = cutout.indicatormatrix(class_regions)  # noqa: E741

    with xr.open_dataarray(snakemake.input.pop_layout) as pop_layout:
        pop = I.dot(pop_layout.stack(spatial=("y", "x")))

    # add max solar rooftop potential assuming 0.1 kW/m2 and 20 m2/person,
    # i.e. 2 kW/person (population data is in thousands of people) so we get MW
    potentials = 0.1 * 20 * pd.Series(pop, index=class_regions.index)

    if snakemake.input.get("rooftop_totals"):
        totals = pd.read_csv(snakemake.input.rooftop_totals, index_col="country")["gw"]
        share = snakemake.params.get("rooftop_share", 1.0)
        potentials = scale_to_country_totals(potentials, totals * share)

    potentials.to_csv(snakemake.output.potentials)
