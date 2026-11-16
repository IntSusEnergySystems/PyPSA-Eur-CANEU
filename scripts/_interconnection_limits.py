# SPDX-License-Identifier: MIT
"""
Cross-border transmission capacity per border (``interconnection_limits``, T30).

Everything in usable physical capacity: AC lines × ``s_max_pu`` (0.7) + DC links.

    cap(border, h) = factor[h] × ( base(border) + Σ ΔTYNDP(border, projects up to h) )

- ``base``: usable capacity of the lines and DC links crossing the border in PyPSA-Eur's
  grid (OSM grid + the TYNDP 2020 / NEP projects PyPSA-Eur adds as existing); their
  ``s_nom`` / ``p_nom`` is the original grid at every horizon.
- ``ΔTYNDP``: TYNDP 2024 transfer-capacity increase of each cross-border project with a
  counted status, commissioned after ``in_grid_until`` (already in the OSM grid before)
  and up to ``h``, not already in PyPSA-Eur's TYNDP 2020 AC lines (same project ID).
  TYNDP publishes no line ratings per project: for DC projects the increase is the
  converter rating; for AC projects it is a transfer value (below the physical rating).
- ``factor``: per horizon (1.0 in 2030, 1.5 after, user's choice).

The cap is a ceiling the model may build up to (projects are allowed, not imposed), and
every line and link crossing the border counts. A border with a TYNDP project but no
line or link in the model cannot be expanded (logged). TYNDP 2026 NTCs are logged next to
the caps for comparison only (market values: in a power-flow model they would count the
network's limits twice).

Written as ``GlobalConstraint`` rows (type ``interconnection_limit``,
``carrier_attribute`` = "<c0>-<c1>", ``constant`` in MW) by ``compose_network``,
solved by ``add_interconnection_constraints``. Config:
``scripts/_interconnection_limits_config.py``; reasons: ``docs/energy.md``.
"""

import logging

import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

LIMIT_TYPE = "interconnection_limit"


def factor_at(factors: dict, horizon: int) -> float:
    keys = sorted(int(k) for k in factors if int(k) <= horizon)
    if not keys:
        raise ValueError(f"interconnection_limits.factor: no entry at or before {horizon}")
    if keys[-1] != horizon:
        logger.warning(f"interconnection_limits.factor: no {horizon}, using {keys[-1]}")
    return float({int(k): v for k, v in factors.items()}[keys[-1]])


def one_value(df: pd.DataFrame, direction: str) -> pd.Series:
    both = df[["mw_0to1", "mw_1to0"]].fillna(0.0)
    return {"max": both.max(axis=1), "min": both.min(axis=1),
            "mean": both.mean(axis=1)}[direction]


def border_key(df: pd.DataFrame) -> pd.Series:
    return df[["country0", "country1"]].apply(lambda r: "-".join(sorted(r)), axis=1)


def project_increase(projects: pd.DataFrame, horizon: int, cfg: dict) -> pd.Series:
    """Σ TYNDP transfer-capacity increase per border [MW] of the projects counted at
    ``horizon``."""
    p = projects[
        (projects["country0"] != projects["country1"])
        & projects["status_id"].isin(cfg["project_statuses"])
        & ~projects["in_pypsa_eur_tyndp2020"].astype(bool)
        & (projects["commissioning_year"] > cfg["in_grid_until"])
        & (projects["commissioning_year"] <= horizon)
    ]
    if p.empty:
        return pd.Series(dtype=float)
    return one_value(p, cfg["direction"]).groupby(border_key(p).values).sum()


def crossing(n: pypsa.Network) -> dict[str, pd.Series]:
    """Lines and DC links between two countries → border "c0-c1". A DC link is counted
    once: its "-reversed" copy (``transmission_efficiency``) has the same capacity,
    tied by ``add_lossy_bidirectional_link_constraints``."""
    country = n.buses.country
    reversed_ = n.links.get("reversed", pd.Series(False, n.links.index)).fillna(False)
    dc = n.links[(n.links.carrier == "DC") & ~reversed_.astype(bool)]
    out = {}
    for c, static in (("Line", n.lines), ("Link", dc)):
        a, b = static.bus0.map(country), static.bus1.map(country)
        cross = a.notna() & b.notna() & (a != b)
        out[c] = pd.Series(
            ["-".join(sorted(p)) for p in zip(a[cross], b[cross])],
            index=static.index[cross],
            dtype=object,
        )
    return out


def base_capacity(n: pypsa.Network) -> pd.Series:
    """Usable capacity per border of the grid as built: Σ s_nom × s_max_pu + Σ p_nom."""
    borders = crossing(n)
    lines = n.lines.loc[borders["Line"].index]
    links = n.links.loc[borders["Link"].index]
    return pd.concat(
        [
            (lines.s_nom * lines.s_max_pu).groupby(borders["Line"].values).sum(),
            links.p_nom.groupby(borders["Link"].values).sum(),
        ]
    ).groupby(level=0).sum()


def apply_interconnection_limits(
    n: pypsa.Network, horizon: int, cfg: dict, projects: pd.DataFrame,
    ntc: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Write one cap per border with a line or link; return the table logged."""
    factor = factor_at(cfg["factor"], horizon)
    base = base_capacity(n)
    increase = project_increase(projects, horizon, cfg)
    modelled = set(n.buses.country.dropna()) - {""}
    unreachable = [
        b for b in increase.index
        if b not in base.index and set(b.split("-")) <= modelled and increase[b] > 0
    ]
    if unreachable:
        logger.warning(
            "interconnection_limits: TYNDP projects on borders without line or link in "
            f"the model, not representable: {unreachable}"
        )
    table = pd.DataFrame({"base": base, "tyndp_increase": increase}).fillna(0.0)
    table = table.loc[base.index]
    table["cap"] = factor * (table["base"] + table["tyndp_increase"])
    if ntc is not None:
        table["ntc_2030"] = one_value(ntc, cfg["direction"]).groupby(
            border_key(ntc).values).sum().reindex(table.index)
    for border, row in table.iterrows():
        n.add(
            "GlobalConstraint",
            f"interconnection limit {border}",
            type=LIMIT_TYPE,
            carrier_attribute=border,
            sense="<=",
            constant=row["cap"],
        )
    logger.info(
        f"interconnection_limits {horizon} (factor {factor}) [MW usable]:\n"
        + table.round(0).to_string()
    )
    return table


def add_interconnection_constraints(n: pypsa.Network) -> None:
    """New usable capacity ≤ cap − existing usable capacity, per border."""
    glcs = n.global_constraints[n.global_constraints.type == LIMIT_TYPE]
    if glcs.empty:
        return
    borders = crossing(n)
    lines, links = n.lines, n.links
    for name, glc in glcs.iterrows():
        line = borders["Line"].index[borders["Line"] == glc.carrier_attribute]
        link = borders["Link"].index[borders["Link"] == glc.carrier_attribute]
        ext_line = line[lines.loc[line, "s_nom_extendable"]]
        ext_link = link[links.loc[link, "p_nom_extendable"]]
        # extendable components' variable covers their floor; fixed ones are constants
        fixed = (
            (lines.loc[line.difference(ext_line), "s_nom"]
             * lines.loc[line.difference(ext_line), "s_max_pu"]).sum()
            + links.loc[link.difference(ext_link), "p_nom"].sum()
        )
        existing = fixed + (
            (lines.loc[ext_line, ["s_nom", "s_nom_min"]].max(axis=1)
             * lines.loc[ext_line, "s_max_pu"]).sum()
            + links.loc[ext_link, ["p_nom", "p_nom_min"]].max(axis=1).sum()
        )
        if existing > glc.constant + 1e-6:
            logger.warning(
                f"{name}: existing {existing:.0f} MW usable above the cap "
                f"{glc.constant:.0f} MW: kept, no new capacity"
            )
        terms = []
        if len(ext_line):
            s_nom = n.model["Line-s_nom"]
            terms.append(
                (s_nom.sel({s_nom.dims[0]: ext_line})
                 * lines.loc[ext_line, "s_max_pu"].values).sum()
            )
        if len(ext_link):
            p_nom = n.model["Link-p_nom"]
            terms.append(p_nom.sel({p_nom.dims[0]: ext_link}).sum())
        if not terms:
            continue
        lhs = terms[0] if len(terms) == 1 else terms[0] + terms[1]
        rhs = max(glc.constant, existing) - fixed
        n.model.add_constraints(lhs, "<=", rhs, name=f"GlobalConstraint-{name}")
