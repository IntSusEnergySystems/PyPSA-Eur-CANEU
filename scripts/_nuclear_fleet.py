# SPDX-License-Identifier: MIT
"""
`nuclear_fleet:` the existing and under-construction nuclear reactors from an
official per-reactor table (``data/nuclear_fleet.csv``), with lifetime extension
and must-run (T34).

Standalone (no PatEx needed), default off; config section in
``scripts/_nuclear_fleet_config.py``. Applied by ``compose_network`` at every
planning horizon, after the brownfield step.

Rules, per reactor and planning horizon ``h``:

* retirement year = the official one (law, decision, licence) or else the
  commissioning year + the official lifetime (``lifetime`` column, else
  ``default_lifetime``, else the cost data's nuclear lifetime);
* one extension of ``extension_years`` after it, unless the official end date
  is itself an extension (``end_date_includes_extension``);
* usable at ``h`` if commissioned by ``h`` and the retirement year after the
  extension is more than ``min_remaining_years`` after ``h``;
* in its extension at ``h`` if the retirement year itself is not more than
  ``min_remaining_years`` after ``h``: then the model chooses whether to keep it
  (extendable up to its capacity, at the fixed O&M cost, never above what it kept
  at the previous horizon), else it is a fixed existing capacity.

Nuclear is modelled as Links from the uranium bus only (PyPSA-Eur's duplicate
electricity Generators are removed), one per reactor.
"""

import logging

import numpy as np
import pandas as pd
import pypsa
logger = logging.getLogger(__name__)


def fleet_at_horizon(
    fleet: pd.DataFrame,
    horizon: int,
    default_lifetime: float,
    extension_years: int,
    min_remaining_years: int,
) -> pd.DataFrame:
    """Reactors usable at ``horizon``, with ``retirement``, ``retirement_extended``
    and ``extension`` (True: in its extension at ``horizon``)."""
    fleet = fleet.copy()
    lifetime = fleet["lifetime"].fillna(default_lifetime)
    fleet["retirement"] = fleet["retirement_year"].fillna(
        fleet["commissioning_year"] + lifetime
    )
    # an official end date that is itself an extension gets no other one
    already = fleet.get("end_date_includes_extension", False)
    already = pd.Series(already, index=fleet.index).fillna(False).astype(bool)
    fleet["retirement_extended"] = fleet["retirement"] + extension_years * (~already)
    usable = (fleet["commissioning_year"] <= horizon) & (
        fleet["retirement_extended"] > horizon + min_remaining_years
    )
    fleet = fleet[usable]
    fleet["extension"] = fleet["retirement"] <= horizon + min_remaining_years
    return fleet


def nearest_bus(fleet: pd.DataFrame, buses: pd.DataFrame) -> pd.Series:
    """Nearest AC bus of the same country to each reactor (lat / lon)."""
    out = {}
    for name, row in fleet.iterrows():
        candidates = buses[buses.country == row["country"]]
        if candidates.empty:
            continue
        coslat = np.cos(np.radians(row["lat"]))
        d2 = ((candidates.x - row["lon"]) * coslat) ** 2 + (candidates.y - row["lat"]) ** 2
        out[name] = d2.idxmin()
    return pd.Series(out, dtype=object)


def apply_nuclear_fleet(
    n: pypsa.Network,
    n_previous: pypsa.Network | None,
    costs: pd.DataFrame,
    horizon: int,
    options: dict,
    availability_file: str | None,
) -> None:
    """Replace the network's nuclear by the reactors of ``options["fleet_file"]``
    usable at ``horizon`` (see the module docstring)."""
    fleet = pd.read_csv(options["fleet_file"])
    fleet["name"] = fleet["country"] + " " + fleet["reactor"]
    fleet = fleet.set_index("name")
    if fleet.index.duplicated().any():
        raise ValueError(f"duplicate reactors in {options['fleet_file']}")

    default_lifetime = options["default_lifetime"] or costs.at["nuclear", "lifetime"]
    usable = fleet_at_horizon(
        fleet,
        horizon,
        default_lifetime,
        options["extension_years"],
        options["min_remaining_years"],
    )
    buses = n.buses[n.buses.carrier == "AC"]
    bus = nearest_bus(usable, buses)
    usable = usable.loc[bus.index].assign(bus=bus)

    # remove PyPSA-Eur's nuclear: duplicate Generators and powerplantmatching links
    n.remove("Generator", n.generators.index[n.generators.carrier == "nuclear"])
    n.remove("Link", n.links.index[n.links.carrier == "nuclear"])

    # uranium supply (PyPSA-Eur's uranium bus has only a cyclic store)
    uranium = "EU uranium"
    if uranium not in n.buses.index:
        n.add("Bus", uranium, location="EU", carrier="uranium", unit="MWh_th")
    if "uranium" not in n.carriers.index:
        n.add("Carrier", "uranium")
    supply = n.generators.index[(n.generators.bus == uranium)]
    if supply.empty:
        n.add(
            "Generator",
            uranium,
            bus=uranium,
            carrier="uranium",
            p_nom_extendable=True,
            marginal_cost=costs.at["uranium", "fuel"],
        )

    if usable.empty:
        logger.info(f"Nuclear fleet {horizon}: no usable reactor in the network")
        return

    efficiency = costs.at["nuclear", "efficiency"]
    names = pd.Index(usable["bus"].astype(str) + " nuclear " + usable["reactor"].astype(str))
    p_nom = (usable["net_mw"] / efficiency).set_axis(names)
    extension = usable["extension"].set_axis(names)
    optional = extension & options["optional_extension"]

    p_nom_max = p_nom.where(optional, np.inf)
    if n_previous is not None:
        # a reactor not kept (fully) in its extension cannot come back
        previous = n_previous.links.reindex(names)
        was_optional = previous.p_nom_extendable.fillna(False).astype(bool)
        p_nom_max = p_nom_max.where(
            ~(optional & was_optional),
            np.minimum(p_nom_max, previous.p_nom_opt.fillna(0.0)),
        )

    availability = pd.Series(1.0, index=names)
    if availability_file:
        # as PyPSA-Eur's add_electricity: the weather year's column, else the last
        df = pd.read_csv(availability_file, index_col=0)
        df.columns = df.columns.astype(int)
        year = n.snapshots[0].year
        table = df[year] if year in df.columns else df.iloc[:, -1]
        availability = (
            usable["country"].set_axis(names).map(table).fillna(1.0).astype(float)
        )
    margin = options["must_run_margin"]
    p_min_pu = (
        (availability - margin).clip(lower=0.0) if margin is not None else 0.0 * availability
    )

    if "nuclear" not in n.carriers.index:
        n.add("Carrier", "nuclear")
    n.add(
        "Link",
        names,
        bus0=uranium,
        bus1=usable.bus.values,
        bus2="co2 atmosphere",
        carrier="nuclear",
        p_nom=p_nom.where(~optional, 0.0),
        p_nom_min=0.0,
        p_nom_max=p_nom_max,
        p_nom_extendable=optional,
        efficiency=efficiency,
        efficiency2=costs.at["uranium", "CO2 intensity"],
        marginal_cost=efficiency * costs.at["nuclear", "VOM"],
        # kept in extension: fixed O&M only (per MW_el, as PyPSA-Eur's links)
        capital_cost=(
            efficiency
            * costs.at["nuclear", "FOM"]
            / 100
            * costs.at["nuclear", "investment"]
        ),
        p_max_pu=availability,
        p_min_pu=p_min_pu,
        build_year=usable["commissioning_year"].astype(int).values,
        lifetime=(usable["retirement_extended"] - usable["commissioning_year"]).values,
    )
    summary = usable.assign(extension=usable["extension"]).groupby(
        ["country", "extension"]
    )["net_mw"].sum()
    logger.info(f"Nuclear fleet {horizon} [MW net] (country, in extension):\n{summary}")
