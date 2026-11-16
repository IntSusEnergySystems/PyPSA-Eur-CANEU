# SPDX-License-Identifier: MIT
"""
`ev_flexibility:` config section (T16); the rules are in ``scripts/_ev_flexibility.py``.

Registered in ``scripts/lib/validation/config_updates.py`` like ``patex:``. The
defaults are Elia's AdeqFlex 2025 "Current commitments" case, as derived for
PyPSA-Wal (``TIMES2PYPSA/pypsa-wal``, ``build_ev_charging_weights.py``); horizons
past Elia's last year (2036) hold it.
"""

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema

_HOME = ("sunny_PV", "sunny_noPV", "cloudy_PV", "cloudy_noPV")


def _weights(natural: float, home: float, work: float) -> dict[str, float]:
    return {"natural": natural, **{k: home for k in _HOME}, "work": work}


class EVFlexibilityConfig(BaseModel):
    """Electric-car flexibility after Elia AdeqFlex 2025 (T16)."""

    enable: bool = Field(
        False,
        description="Only the market share of the EV fleet is flexible; the rest of the "
        "EV load follows Elia's charging curves on the electricity bus.",
    )
    market_share: dict[int, float] = Field(
        default_factory=lambda: {
            2020: 0.005, 2025: 0.01, 2030: 0.07, 2035: 0.172,
            2040: 0.18, 2045: 0.18, 2050: 0.18,
        },
        description="Share of the EV fleet and EV demand steered by the system "
        "(Elia V1M + V2M); replaces `sector.bev_dsm_availability`.",
    )
    avail_max: dict[int, float] = Field(
        default_factory=lambda: {
            2020: 0.4, 2025: 0.4, 2030: 0.4, 2035: 0.48, 2040: 0.48, 2045: 0.48, 2050: 0.48,
        },
        description="Maximum plugged-in share of EVs (Elia); replaces `sector.bev_avail_max`.",
    )
    avail_mean: dict[int, float] = Field(
        default_factory=lambda: {
            2020: 0.32, 2025: 0.32, 2030: 0.32, 2035: 0.35, 2040: 0.35, 2045: 0.35, 2050: 0.35,
        },
        description="Mean plugged-in share (Elia); replaces `sector.bev_avail_mean`.",
    )
    avail_min: dict[int, float] = Field(
        default_factory=lambda: {
            2020: 0.2, 2025: 0.2, 2030: 0.2, 2035: 0.18, 2040: 0.18, 2045: 0.18, 2050: 0.18,
        },
        description="Floor of the plugged-in share (Elia).",
    )
    charging_weights: dict[int, dict[str, float]] = Field(
        default_factory=lambda: {
            2020: _weights(0.7388, 0.0429, 0.0896),
            2025: _weights(0.6969, 0.0498, 0.1039),
            2030: _weights(0.5054, 0.0909, 0.131),
            2035: _weights(0.3416, 0.1331, 0.126),
            2040: _weights(0.3292, 0.1381, 0.1184),
            2045: _weights(0.3292, 0.1381, 0.1184),
            2050: _weights(0.3292, 0.1381, 0.1184),
        },
        description="Weights of Elia's daily charging curves for the inflexible EV load "
        "(natural V0 vs local V1H/V2H home and work), renormalised over the non-market "
        "share; must sum to 1 per horizon.",
    )
    charging_profile_file: str = Field(
        "data/ev_charging/elia_charging_daily_profiles_local.csv",
        description="Elia's daily charging curves in local time (2026 and 2036 vintages).",
    )
    bev_energy: float = Field(
        0.06, description="Battery per EV [MWh] (Elia: 60 kWh); replaces `sector.bev_energy`."
    )
    v2g: bool = Field(False, description="Vehicle-to-grid (Elia's V2M is not modelled).")


class EVFlexibilityConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            ev_flexibility=(EVFlexibilityConfig, Field(default_factory=EVFlexibilityConfig)),
        )
