# SPDX-License-Identifier: MIT
"""
Snakemake wrapper: bring the PatEx demands of one planning horizon into resources/.

The extraction lives in the sibling ``PATEX_PyPSA`` repository (run
``patex-pypsa export-coupling`` in the PatEx environment first). This script
only checks the bundle and copies it, so that every PyPSA-Eur run records the
exact PatEx inputs it used.

With ``patex.fallback_demand: eu_trend``, the modelled fallback countries (GB, NO,
CH…) get rows in the energy-totals, industry and parameters tables: their own
base-year data on the relative trend of the PatEx countries (``patex_pypsa.fallback``;
reasons in docs/energy.md, "Countries outside PatEx").
"""

import json
import logging
import shutil
from pathlib import Path

import pandas as pd

from scripts._helpers import configure_logging

logger = logging.getLogger(__name__)

#: PatEx industry carrier → Eurostat (nrg_bal, siec list). Coal adds the blast-furnace
#: input (PatEx coal includes coke); feedstock = final non-energy use.
INDUSTRY_SOURCE = {
    "coal": [("FC_IND_E", "C0000X0350-0370"), ("TI_BF_E", "C0000X0350-0370")],
    "electricity": [("FC_IND_E", "E7000")],
    "low-temperature heat": [("FC_IND_E", "H8000")],
    "methane": [("FC_IND_E", "G3000")],
    "oil for industry": [("FC_IND_E", "O4000XBIO")],
    "solid biomass": [("FC_IND_E", "BIOE")],
    "methane feedstock": [("FC_NE", "G3000")],
    "naphtha": [("FC_NE", "O4000XBIO")],
}
#: UNFCCC country codes that differ from PyPSA-Eur's
UNFCCC_CODES = {"GB": "UK", "GR": "GR"}


def base_energy_totals(fn: str, countries: list[str], year: int) -> pd.DataFrame:
    """PyPSA-Eur energy totals of ``year`` [TWh] (PatEx column names)."""
    e = pd.read_csv(fn, index_col=[0, 1])
    have = [c for c in countries if (c, year) in e.index]
    return e.xs(year, level=1).loc[have]


def eurostat_industry(e: pd.DataFrame, countries: list[str], year: int) -> pd.DataFrame:
    """Eurostat industry energy per PatEx carrier [TWh], one row per country (latest
    year with data <= ``year``, in column ``year``)."""
    from scripts.build_industrial_production_per_country import eurostat_industry_year

    flows = e[e.country.isin(countries)
              & e.nrg_bal.isin({b for v in INDUSTRY_SOURCE.values() for b, _ in v})]
    rows = {}
    for c in countries:
        y = eurostat_industry_year(e, c, year)
        sel = flows[(flows.country == c) & (flows.year == y)]
        rows[c] = {
            k: sum(
                sel[(sel.nrg_bal == b) & (sel.siec == s)]["value"].sum() for b, s in pairs
            )
            for k, pairs in INDUSTRY_SOURCE.items()
        } | {"year": y}
    return pd.DataFrame(rows).T


def eurostat_waste_to_energy(e: pd.DataFrame, countries: list[str], year: int) -> pd.Series:
    """Non-renewable waste (industrial + non-renewable municipal) input to electricity
    and heat generation [TWh] per country in ``year`` (Eurostat TI_EHG_E, W6100_6220)."""
    sel = e[(e.nrg_bal == "TI_EHG_E") & (e.siec == "W6100_6220") & (e.year == year)
            & e.country.isin(countries)]
    return sel.groupby("country")["value"].sum().reindex(countries).fillna(0.0)


def unfccc_ippu(fn: str, countries: list[str], year: int) -> pd.Series:
    """CO2 of industrial processes (CRF 2) per country, latest year <= ``year``."""
    u = pd.read_csv(
        fn,
        usecols=["Country_code", "Pollutant_name", "Sector_code", "Year", "emissions"],
        encoding="latin-1",
        low_memory=False,
    )
    u = u[(u.Pollutant_name == "CO2") & (u.Sector_code == "2")]
    u["Year"] = pd.to_numeric(u["Year"], errors="coerce")
    y = int(u.loc[u.Year <= year, "Year"].max())
    u = u[u.Year == y].set_index("Country_code")["emissions"]
    u = pd.to_numeric(u, errors="coerce")
    return pd.Series({c: u.get(UNFCCC_CODES.get(c, c), float("nan")) for c in countries})


def fallback_trend_rows(inputs, countries, horizon, base_year, tables):
    """Rows of the fallback ``countries`` for the energy-totals, industry and
    parameters tables (``tables``: the PatEx tables of the horizon)."""
    from patex_pypsa import default_mappings_dir
    from patex_pypsa.emissions import industry_factor
    from patex_pypsa.export import load_country_map
    from patex_pypsa.fallback import (
        base_load_factor,
        eu_tables,
        split_routes,
        trend_energy_totals,
        trend_industry,
        trend_parameters,
        trend_waste_to_energy,
        with_routes,
    )

    long = pd.read_csv(inputs.trend_long)
    factors = pd.read_csv(inputs.trend_co2_factors)
    waste = industry_factor(factors, "solid-waste").rename(
        load_country_map(default_mappings_dir())
    )
    eu_b = eu_tables(long, base_year, waste)
    eu_h = eu_tables(long, horizon, waste)
    eu_countries = sorted(long["country"].unique())

    base = base_energy_totals(inputs.trend_energy_totals, countries, base_year)
    missing = sorted(set(countries) - set(base.index))
    if missing:
        logger.warning(
            "patex.fallback_demand: no %d energy totals for %s: PyPSA-Eur demands kept",
            base_year, missing,
        )
    countries = list(base.index)
    if not countries:
        return {}
    et = trend_energy_totals(
        base, eu_b["energy_totals"], eu_h["energy_totals"],
        list(tables["energy_totals"].columns),
    )

    eurostat = pd.read_csv(inputs.trend_eurostat)
    ind_countries = []
    for c in countries:
        try:
            eurostat_industry(eurostat, [c], base_year)
            ind_countries.append(c)
        except ValueError:
            logger.warning(
                "patex.fallback_demand: no Eurostat industry balance for %s: "
                "PyPSA-Eur industry kept", c,
            )
    src_c = eurostat_industry(eurostat, ind_countries, base_year)
    years = src_c.pop("year").astype(int)
    src_eu = pd.DataFrame(
        {
            c: eurostat_industry(eurostat, eu_countries, years[c])
            .drop(columns="year")
            .sum()
            for c in ind_countries
        }
    ).T
    ippu_c = unfccc_ippu(inputs.trend_ghg, ind_countries, base_year)
    ippu_eu = unfccc_ippu(inputs.trend_ghg, eu_countries, base_year).sum()
    src_c["process emission"] = ippu_c
    src_eu["process emission"] = ippu_eu
    # Eurostat's industry includes ammonia: trend on PatEx's industry with the
    # routes added back, then the routes taken out as for the PatEx countries
    ind = trend_industry(
        src_c.astype(float), src_eu.astype(float),
        with_routes(eu_b["industry"], eu_b["routes"]),
        with_routes(eu_h["industry"], eu_h["routes"]),
        list(tables["industry"].columns),
    )
    nh3 = pd.read_csv(inputs.trend_ammonia, index_col=0)
    nh3.columns = nh3.columns.astype(int)
    nh3_year = min(base_year, max(nh3.columns))
    ind = split_routes(
        ind, pd.DataFrame({"ammonia": nh3[nh3_year]}), eu_b["routes"], eu_h["routes"]
    )

    dh = pd.read_csv(inputs.trend_district_heat_share, index_col=0)
    dh_base = dh[str(base_year)].reindex(countries)
    par = trend_parameters(
        dh_base, eu_b["parameters"], eu_h["parameters"],
        ev_energy_c=et["electricity passenger cars"],
        ev_energy_eu=eu_h["energy_totals"].get("electricity passenger cars", 0.0),
        columns=list(tables["parameters"].columns),
        # residual load of a fallback country: base load + electric cooling
        base_load_factor=base_load_factor(eu_b["energy_totals"], eu_h["energy_totals"]),
    )
    wte_cols = ["waste to energy fuel", "waste to energy co2"]
    if set(wte_cols) <= set(tables["parameters"].columns):
        # non-renewable waste in power and heat plants (audit #2): the country's share
        # of Eurostat's input to electricity and heat generation, same year as its
        # industry balance (GB 2019), on PatEx's EU fuel and factor
        wte_years = pd.Series({c: years.get(c, base_year) for c in countries})
        src_c = pd.Series({c: eurostat_waste_to_energy(eurostat, [c], wte_years[c]).sum()
                           for c in countries})
        src_eu = pd.Series({c: eurostat_waste_to_energy(eurostat, eu_countries, wte_years[c]).sum()
                            for c in countries})
        eu_par = tables["parameters"].reindex(eu_countries)
        wte = trend_waste_to_energy(
            src_c, src_eu, eu_par[wte_cols[0]].sum(), eu_par[wte_cols[1]].sum()
        )
        par[wte_cols[0]], par[wte_cols[1]] = wte["fuel"], wte["co2"]
    logger.info(
        "patex.fallback_demand: %s on the EU trend (Eurostat industry years %s)",
        countries, years.to_dict(),
    )
    return {"energy_totals": et, "industry": ind.loc[ind_countries], "parameters": par}

if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_patex_demands", horizon="2030")
    configure_logging(snakemake)

    horizon = int(snakemake.wildcards.horizon)
    manifest = json.loads(Path(snakemake.input.manifest).read_text())

    if horizon not in manifest["horizons"]:
        raise ValueError(
            f"PatEx bundle exported for {manifest['horizons']}, not {horizon}: "
            "re-run `patex-pypsa export-coupling --horizons ...`"
        )
    modelled = set(snakemake.params.countries)
    fallback = set(snakemake.params.fallback_countries)
    missing = sorted(modelled - set(manifest["countries"]) - fallback)
    if missing:
        raise ValueError(
            f"no PatEx data for {missing}: add them to the PatEx run, or to "
            "patex.fallback_countries to keep the PyPSA-Eur demands"
        )
    kept = sorted(modelled & fallback)
    if kept:
        logger.info(
            "PyPSA-Eur preprocessed demands kept for %s (patex.fallback_countries)",
            kept,
        )
    if manifest.get("uncovered_slices"):
        logger.warning(
            "%d PatEx slices are mapped by no rule (see coverage.csv)",
            manifest["uncovered_slices"],
        )

    trend = {}
    if snakemake.params.fallback_demand == "eu_trend" and kept:
        tables = {
            name: pd.read_csv(snakemake.input[name], index_col=0)
            for name in ("energy_totals", "industry", "parameters")
        }
        trend = fallback_trend_rows(
            snakemake.input, kept, horizon, int(snakemake.params.base_year), tables
        )
        for name, rows in trend.items():
            out = pd.concat([tables[name], rows.reindex(columns=tables[name].columns.union(rows.columns, sort=False))])
            out.index.name = tables[name].index.name
            out.to_csv(snakemake.output[name], float_format="%.6f")

    for name in (
        "energy_totals",
        "industry",
        "parameters",
        "co2_intensity",
        "supply",
        "manifest",
    ):
        if name not in trend:
            shutil.copy2(snakemake.input[name], snakemake.output[name])
