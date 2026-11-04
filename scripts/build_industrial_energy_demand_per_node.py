# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Build the industrial energy demand per model region for a planning horizon in TWh/a.

The specific energy consumption per subsector and country for the horizon from [build_industry_sector_ratios_intermediate][] (MWh/t) is multiplied by the regional production from [build_industrial_production_per_node][] and summed over subsectors. This gives, per region, the demand for electricity, coal, coke, solid biomass, methane, hydrogen, low-temperature heat, naphtha, methanol and ammonia (non-zero only if `industry: ammonia` is enabled), as well as process emissions and process emissions from feedstock in MtCO2/a. Today's regional electricity demand from [build_industrial_energy_demand_per_node_today][] is appended as `current electricity` so that [prepare_sector_network][] can separate the new industrial electricity load from the existing one.
"""

import logging

import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "build_industrial_energy_demand_per_node",
            horizon=2030,
        )
    configure_logging(snakemake)
    set_scenario_config(snakemake)

    # import ratios
    fn = snakemake.input.industry_sector_ratios
    sector_ratios = pd.read_csv(fn, header=[0, 1], index_col=0)

    # material demand per node and industry (Mton/a)
    fn = snakemake.input.industrial_production_per_node
    nodal_production = pd.read_csv(fn, index_col=0) / 1e3

    # energy demand today to get current electricity
    fn = snakemake.input.industrial_energy_demand_per_node_today
    nodal_today = pd.read_csv(fn, index_col=0)

    nodal_sector_ratios = pd.concat(
        {node: sector_ratios[node[:2]] for node in nodal_production.index}, axis=1
    )

    nodal_production_stacked = nodal_production.stack()
    nodal_production_stacked.index.names = [None, None]

    # final energy consumption per node and industry (TWh/a)
    nodal_df = (
        (nodal_sector_ratios.multiply(nodal_production_stacked))
        .T.groupby(level=0)
        .sum()
    )

    rename_sectors = {
        "elec": "electricity",
        "biomass": "solid biomass",
        "heat": "low-temperature heat",
    }
    nodal_df.rename(columns=rename_sectors, inplace=True)

    nodal_df["current electricity"] = nodal_today["electricity"]

    # PatEx soft-link: country totals per carrier and process emissions from
    # PatEx, nodal split from PyPSA-Eur. `current electricity` (today's load) is
    # left untouched; ammonia, methanol and coke are 0 (in PatEx's carriers).
    if snakemake.input.get("patex_industry"):
        from patex_pypsa import override_country_totals

        pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)
        patex_industry = pd.read_csv(snakemake.input.patex_industry, index_col=0)
        # feedstock gas (PatEx only) is spread over the nodes like the gas use
        nodal_df["methane feedstock"] = nodal_df["methane"]
        # hydrogen is spread like its gross uses: PatEx has no chlor-alkali
        # by-product, and the net value (uses - by-product) can be negative at a
        # node or for a whole country, which would flip the signs of the split
        h2_ratios = nodal_sector_ratios.loc["hydrogen"].clip(lower=0)
        gross_h2 = (h2_ratios * nodal_production_stacked).groupby(level=0).sum()
        patex_nodes = pop_layout.index[pop_layout.ct.isin(patex_industry.index)]
        patex_nodes = patex_nodes.intersection(nodal_df.index)
        nodal_df.loc[patex_nodes, "hydrogen"] = gross_h2.reindex(patex_nodes).fillna(0.0)
        nodal_df = override_country_totals(
            nodal_df,
            patex_industry,
            pop_layout.ct,
            pop_layout.fraction,
        )

    nodal_df.index.name = "TWh/a (MtCO2/a)"

    fn = snakemake.output.industrial_energy_demand_per_node
    nodal_df.to_csv(fn, float_format="%.6f")
