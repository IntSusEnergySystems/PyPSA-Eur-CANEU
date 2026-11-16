# SPDX-License-Identifier: MIT
"""
Electric-car flexibility after Elia AdeqFlex 2025 (``ev_flexibility``, T16).

Adapted from PyPSA-Wal (``TIMES2PYPSA/pypsa-wal``, ``docs/ev-charging-softlink.md``)
for every country. PyPSA-Eur makes half of the EV fleet a flexible battery that is
plugged in 80-95 % of the time, with V2G. Here:

* only the market share of the fleet (Elia V1M + V2M) is flexible: that share of the
  EV demand stays on the EV battery bus behind the BEV charger, and the charger and
  EV battery are sized on that share of the fleet;
* the rest of the EV demand is a fixed load on the electricity bus, shaped by
  Elia's daily charging curves (natural V0 and local V1H home / work), in each
  country's local time;
* the plugged-in availability follows Elia (max, mean, floor), on PyPSA-Eur's
  traffic shape; no V2G.

The EV demand is final electricity as metered (PatEx calibrates it on the energy
balances), so the flexible part is put on the battery bus net of the charger loss:
the grid draws exactly the EV demand.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

#: hours ahead of UTC, standard time (summer time ignored: at most 1 h)
UTC_OFFSET = {
    **{c: 0 for c in ("GB", "IE", "PT", "IS")},
    **{c: 2 for c in ("BG", "EE", "FI", "GR", "LT", "LV", "RO", "UA", "MD")},
}
DEFAULT_UTC_OFFSET = 1


def by_horizon(values: dict, horizon: int):
    """The horizon's entry, else the nearest earlier one (held, not interpolated)."""
    if horizon in values:
        return values[horizon]
    earlier = [y for y in sorted(values) if y < horizon]
    if not earlier:
        raise ValueError(f"ev_flexibility: no entry at or before {horizon} ({sorted(values)})")
    logger.warning(f"ev_flexibility: no entry for {horizon}, holding {earlier[-1]}")
    return values[earlier[-1]]


def rescale_availability(
    avail: pd.DataFrame,
    base_max: float,
    base_mean: float,
    new_max: float,
    new_mean: float,
    new_min: float,
) -> pd.DataFrame:
    """PyPSA-Eur's plugged-in profile (``max − (max − mean) × x``, x from traffic)
    re-expressed with other max / mean, floored at ``new_min``."""
    x = (base_max - avail) / (base_max - base_mean)
    return (new_max - (new_max - new_mean) * x).clip(lower=new_min)


def charging_shape(
    profile_file: str,
    snapshots: pd.DatetimeIndex,
    node_country: pd.Series,
    horizon: int,
    weights: dict[str, float],
) -> pd.DataFrame:
    """Snapshot × node shape of the inflexible EV load, each column summing to 1:
    Elia's daily curves (vintage nearest to ``horizon``), weighted, in the node's
    local time."""
    daily = pd.read_csv(profile_file)
    vintages = sorted(daily["year"].unique())
    vintage = min(vintages, key=lambda y: (abs(y - horizon), y))
    daily = daily[daily["year"] == vintage].set_index("hour").sort_index()
    missing = sorted(set(weights) - set(daily.columns))
    if missing:
        raise ValueError(f"ev_flexibility.charging_weights: no curve {missing} in {profile_file}")
    if not np.isclose(sum(weights.values()), 1.0):
        raise ValueError(f"ev_flexibility.charging_weights[{horizon}] must sum to 1")
    curve = sum(w * daily[k] for k, w in weights.items()).values

    hours = np.asarray(snapshots.hour)
    shape = pd.DataFrame(
        {
            node: curve[(hours + UTC_OFFSET.get(ct, DEFAULT_UTC_OFFSET)) % 24]
            for node, ct in node_country.items()
        },
        index=snapshots,
    )
    return shape / shape.sum()


def split_demand(
    profile: pd.DataFrame, shape: pd.DataFrame, market_share: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(flexible, inflexible): the market share keeps the driving profile, the rest
    of each node's energy takes ``shape``; the two add up to ``profile``'s energy."""
    flexible = profile * market_share
    inflexible = shape[profile.columns] * profile.sum() * (1 - market_share)
    return flexible, inflexible
