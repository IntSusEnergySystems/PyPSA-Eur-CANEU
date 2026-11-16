# SPDX-License-Identifier: MIT
"""
Capacity limits per country for wind and solar (``renewable_limits``, T31).

- Offshore wind: each country's goal is its ceiling at every horizon (the goal of
  ``offshore_goal_year``; up to ``planned_until`` the planned capacity of that year).
  PyPSA-Eur's per-class potentials (2 MW/km² of eligible sea) are kept. Where the
  country's cap is above its total potential (BE, DE, NL: upstream's potential is
  below national plans), every class potential of the country is multiplied by
  cap / total potential, i.e. a higher build density on the same sea area: the classes
  keep their shares and the solver cannot put the whole goal in the best class
  (``scale_offshore_potentials``, before brownfield subtracts existing capacity per
  class).
- Up to ``planned_until`` (2030): onshore wind, offshore wind and solar capped at the
  capacity planned for that year (``planned_file``: TYNDP 2026 National Trends+); a
  country without a planned value keeps no cap (offshore: its goal of that year).
- Ground-mounted PV (utility + single-axis tracking), every horizon: the country
  potential of ``ground_pv_file`` (farmland share from national rules + other eligible
  land; ``scripts/update_ground_pv_potential.py``), on top of PyPSA-Eur's per-node
  potentials.
- Other horizons and other resources: PyPSA-Eur's potentials, no build rate.

Each cap counts existing and new capacity of the group in the country. Written as
``GlobalConstraint`` rows (type ``renewable_limit``, ``carrier_attribute`` =
"<country> <group>", ``constant`` in MW) by ``compose_network``, solved by
``add_renewable_limit_constraints``. Config: ``scripts/_renewable_limits_config.py``;
reasons: ``docs/energy.md``.
"""

import logging

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

LIMIT_TYPE = "renewable_limit"
GROUPS = {
    "onwind": ["onwind"],
    "offwind": ["offwind-ac", "offwind-dc", "offwind-float"],
    "solar": ["solar", "solar-hsat", "solar rooftop"],
    # ground-mounted PV (utility and single-axis tracking), ``ground_pv_file``
    "solar ground": ["solar", "solar-hsat"],
}


def country_caps(
    horizon: int, cfg: dict, goals: pd.DataFrame, planned: pd.DataFrame | None,
    ground_pv: pd.DataFrame | None = None,
) -> dict[str, pd.Series]:
    """Group → cap per country [MW] at ``horizon``."""
    until = cfg.get("planned_until")
    early = until is not None and horizon <= until
    year = until if early else cfg["offshore_goal_year"]
    column = f"gw_{year}"
    if column not in goals:
        raise ValueError(f"renewable_limits: no column {column} in the offshore goals")
    caps = {"offwind": goals.set_index("country")[column].astype(float) * 1e3}
    if early and planned is not None:
        # planned capacity of that year, offshore included (overrides the goal)
        planned = planned.set_index("country")
        for group in ("onwind", "offwind", "solar"):
            if group in planned:
                values = planned[group].dropna().astype(float) * 1e3
                caps[group] = (
                    values.combine_first(caps[group]) if group == "offwind" else values
                )
    if ground_pv is not None:
        caps["solar ground"] = ground_pv.set_index("country")["cap_gw"].astype(float) * 1e3
    return caps


def scale_offshore_potentials(
    n: pypsa.Network, horizon: int, cfg: dict, goals: pd.DataFrame,
    planned: pd.DataFrame | None,
) -> pd.Series:
    """
    Where a country's offshore cap at ``horizon`` is above the sum of its per-class
    potentials (``p_nom_max`` of the extendable offwind generators of the horizon),
    multiply each of those potentials by cap / sum. Call before existing capacity is
    subtracted per class (``adjust_renewable_capacity_limits``, brownfield): the room
    left, sum of max(scaled potential - existing, 0), is then at least cap - existing,
    so the national cap binds and the class shares stay those of PyPSA-Eur. Returns
    the factor per scaled country.
    """
    caps = country_caps(horizon, cfg, goals, planned)["offwind"]
    country = n.generators.bus.map(n.buses.country)
    offwind = n.generators.carrier.isin(GROUPS["offwind"])
    ext = offwind & n.generators.p_nom_extendable
    missing = sorted(set(country[offwind]) - set(caps.index))
    if missing:
        logger.warning(
            f"renewable_limits: no offshore goal for {missing}, PyPSA-Eur's potential "
            "kept, no cap"
        )
    potential = n.generators.loc[ext, "p_nom_max"].groupby(country[ext]).sum()
    if not np.isfinite(potential).all():
        raise ValueError(f"renewable_limits: infinite offshore potential in {potential}")
    factors = (caps.reindex(potential.index) / potential).where(lambda f: f > 1).dropna()
    for ct, f in factors.items():
        n.generators.loc[ext & (country == ct), "p_nom_max"] *= f
    logger.info(
        f"renewable_limits {horizon} offwind: potential [GW] "
        + ", ".join(f"{c} {v / 1e3:.1f}" for c, v in potential.items())
        + "; scaled to the cap: "
        + (", ".join(f"{c} x{f:.2f}" for c, f in factors.items()) or "none")
    )
    return factors


def apply_renewable_limits(
    n: pypsa.Network, horizon: int, cfg: dict, goals: pd.DataFrame,
    planned: pd.DataFrame | None, ground_pv: pd.DataFrame | None = None,
) -> None:
    """Write the caps per country and group (offshore potentials: see
    ``scale_offshore_potentials``, called earlier)."""
    modelled = set(n.buses.country.dropna()) - {""}
    for group, caps in country_caps(horizon, cfg, goals, planned, ground_pv).items():
        if group != "offwind":
            missing = sorted(modelled - set(caps.index))
            if missing:
                logger.warning(f"renewable_limits: no planned {group} for {missing}")
        for ct, cap in caps.items():
            if ct not in modelled:
                continue
            n.add(
                "GlobalConstraint",
                f"renewable limit {ct} {group}",
                type=LIMIT_TYPE,
                carrier_attribute=f"{ct} {group}",
                sense="<=",
                constant=cap,
            )
        logger.info(
            f"renewable_limits {horizon} {group} [GW]: "
            + ", ".join(f"{c} {v / 1e3:.1f}" for c, v in caps.items() if c in modelled)
        )


def add_renewable_limit_constraints(n: pypsa.Network) -> None:
    """
    Per country and group: new capacity (extendable generators) ≤ cap − existing
    capacity (non-extendable generators still in the network). Existing above the cap
    is logged and allows no new build. Named ``GlobalConstraint-<name>`` (dual in ``mu``).
    """
    glcs = n.global_constraints[n.global_constraints.type == LIMIT_TYPE]
    if glcs.empty:
        return
    country = n.generators.bus.map(n.buses.country)
    p_nom = n.model["Generator-p_nom"]
    for name, glc in glcs.iterrows():
        ct, group = glc.carrier_attribute.split(" ", 1)
        gens = n.generators.index[
            n.generators.carrier.isin(GROUPS[group]) & (country == ct)
        ]
        ext = gens[n.generators.loc[gens, "p_nom_extendable"]]
        existing = n.generators.loc[gens.difference(ext), "p_nom"].sum()
        rhs = glc.constant - existing
        if rhs < 0:
            logger.warning(
                f"{name}: existing {existing / 1e3:.2f} GW above the cap "
                f"{glc.constant / 1e3:.2f} GW, no new build"
            )
            rhs = 0.0
        if ext.empty:
            continue
        dim = p_nom.dims[0]
        lhs = p_nom.sel({dim: ext}).sum()
        n.model.add_constraints(lhs, "<=", rhs, name=f"GlobalConstraint-{name}")
