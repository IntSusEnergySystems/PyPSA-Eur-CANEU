# SPDX-License-Identifier: MIT
"""
Geological CO2 storage limits (T32).

``co2_storage``: the CO2 sequestered in a country per year is capped at the injection
capacity of its storage projects (IEA CCUS Projects Database,
``data/co2_storage_projects.csv``). ``patex.co2_sequestration``: the total over all
countries is PatEx's CO2 stored, summed over the modelled countries.

Both caps count every ``co2 sequestered`` store, whatever its build year: under myopic
foresight ``add_brownfield`` carries the stores of the earlier horizons onto the same
bus, so a cap on the new store's ``e_nom_max`` alone lets the fleet exceed it.
Config: ``scripts/_co2_storage_config.py``; reasons: ``docs/co2_storage.md``.
"""

import logging

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

CARRIER = "co2 sequestered"
#: GlobalConstraint type of the per-country caps (solved in ``solve_network``)
LIMIT_TYPE = "co2_storage_limit"
BUILT = {"Operational", "Under construction"}
EXCLUDED = {"Cancelled", "Decommissioned", "Suspended"}


def counted_projects(projects: pd.DataFrame, horizon: int, cfg: dict) -> pd.DataFrame:
    """
    Projects whose injection capacity counts at ``horizon``.

    - storage sites only: types Storage and T&S, and Full chain projects that are not
      part of a CCUS hub (a hub member injects into the hub's storage, counted once);
      dedicated storage only (no EOR); cancelled, suspended or decommissioned out;
    - in operation or under construction: from their operation year (no year: now);
    - planned: only after ``built_only_until``, from their operation year; without an
      operation year from ``undated_from``.
    """
    p = projects
    kind = p["project_type"].str.lower()
    site = kind.isin(["storage", "t&s"]) | (
        (kind == "full chain") & p["part_of_ccus_hub"].isna()
    )
    keep = (
        site
        & (p["fate_of_carbon"] == "Dedicated storage")
        & ~p["project_status"].isin(EXCLUDED)
    )
    built = p["project_status"].isin(BUILT)
    start = pd.to_numeric(p["operation"], errors="coerce")
    on = built & (start.isna() | (start <= horizon))
    if horizon > cfg["built_only_until"]:
        on |= ~built & (start <= horizon)
        undated = cfg.get("undated_from")
        if undated is not None and horizon >= undated:
            on |= ~built & start.isna()
    return p[keep & on]


def country_storage_limits(
    projects: pd.DataFrame, horizon: int, cfg: dict, countries: list[str]
) -> pd.Series:
    """Injection capacity per modelled country [Mt CO2/a]; 0 without a counted project."""
    counted = counted_projects(projects, horizon, cfg)
    unknown = counted[counted["capacity_mt"].isna()]
    if not unknown.empty:
        logger.info(
            "CO2 storage projects without capacity (count as 0): "
            + ", ".join(f"{r.country} {r.project}" for r in unknown.itertuples())
        )
    limits = (
        counted.groupby("country")["capacity_mt"].sum().reindex(countries).fillna(0.0)
    )
    positive = ", ".join(f"{c} {v:.2f}" for c, v in limits[limits > 0].items())
    logger.info(
        f"CO2 storage limits {horizon} [Mt/a]: {positive or 'none'}; "
        f"0 in {(limits == 0).sum()} countries"
    )
    return limits


def sequestration_stores(n: pypsa.Network) -> pd.Series:
    """``co2 sequestered`` stores → country of their bus location (``EU`` without
    ``co2_spatial``: one store for the whole network)."""
    stores = n.stores.index[n.stores.carrier == CARRIER]
    location = n.stores.loc[stores, "bus"].map(n.buses.location)
    country = n.buses.get("country", pd.Series(dtype=object))
    return location.map(country).replace("", np.nan).fillna(location)


def add_co2_storage_limits(n: pypsa.Network, limits: pd.Series, nyears: float) -> None:
    """
    One ``GlobalConstraint`` per country (type ``co2_storage_limit``,
    ``carrier_attribute`` = country, ``constant`` in t over the modelled period), and
    no CO2StoP ceiling on the stores: the country cap replaces it. Without
    ``co2_spatial`` (one ``EU`` store) a single cap, the sum over the countries.
    """
    country = sequestration_stores(n)
    if country.empty:
        raise ValueError("co2_storage: no 'co2 sequestered' store in the network")
    unknown = set(country) - set(limits.index)
    if unknown == {"EU"} and set(country) == {"EU"}:
        # sector.co2_spatial: false, one store for all: the sum of the country caps
        logger.info("co2_storage: one CO2 store (no co2_spatial), capped at the sum")
        limits = pd.Series({"EU": limits.sum()})
    elif unknown:
        raise ValueError(f"co2_storage: 'co2 sequestered' stores in {sorted(unknown)}")
    n.stores.loc[country.index, "e_nom_max"] = np.inf
    for ct, limit in limits.items():
        n.add(
            "GlobalConstraint",
            f"co2 storage limit {ct}",
            type=LIMIT_TYPE,
            carrier_attribute=ct,
            sense="<=",
            constant=limit * 1e6 * nyears,
        )


def patex_sequestration_limit(
    parameters_fn: str, countries: list[str], fallback: list[str]
) -> float:
    """
    PatEx's CO2 stored [Mt/a], summed over the modelled countries in the bundle
    (already ≥ 0 per country, see the export). Fallback countries have no PatEx
    figure: their own capture shares this total.
    """
    stored = pd.read_csv(parameters_fn, index_col=0)
    if "co2 stored" not in stored:
        raise ValueError(
            f"{parameters_fn}: no 'co2 stored' (bundle older than T32): re-export it"
        )
    patex = [c for c in countries if c not in fallback]
    missing = sorted(set(patex) - set(stored.index))
    if missing:
        raise ValueError(f"patex.co2_sequestration: no PatEx data for {missing}")
    outside = sorted(set(countries) & set(fallback))
    if outside:
        logger.warning(
            f"patex.co2_sequestration: no PatEx CO2 stored for {outside}; their "
            "sequestration counts in the PatEx total of the other countries"
        )
    return float(stored.loc[patex, "co2 stored"].clip(lower=0).sum())


def add_patex_sequestration_limit(n: pypsa.Network, limit: float, nyears: float) -> None:
    """
    The total cap of ``solve_network.add_co2_sequestration_limit`` with PatEx's value;
    ``solve_network`` keeps it instead of ``sector.co2_sequestration_potential``.
    """
    logger.info(f"PatEx CO2 sequestration limit: {limit:.2f} Mt/a")
    n.add(
        "GlobalConstraint",
        "co2_sequestration_limit",
        sense=">=",
        constant=-limit * 1e6 * nyears,
        type="operational_limit",
        carrier_attribute=CARRIER,
    )


def add_co2_storage_constraints(n: pypsa.Network, sns: pd.DatetimeIndex) -> None:
    """
    Per-country caps (``co2_storage_limit`` rows): CO2 in all the country's
    ``co2 sequestered`` stores at the last snapshot (they start empty and only fill)
    ≤ constant. Named ``GlobalConstraint-<name>`` so that its dual is written to ``mu``.
    """
    glcs = n.global_constraints[n.global_constraints.type == LIMIT_TYPE]
    if glcs.empty:
        return
    country = sequestration_stores(n)
    e = n.model["Store-e"].loc[sns[-1]]
    for name, glc in glcs.iterrows():
        stores = country.index[country == glc.carrier_attribute]
        if stores.empty:
            # no store in that country: nothing can be sequestered there anyway
            continue
        lhs = e.loc[stores].sum()
        n.model.add_constraints(
            lhs, glc.sense, glc.constant, name=f"GlobalConstraint-{name}"
        )
