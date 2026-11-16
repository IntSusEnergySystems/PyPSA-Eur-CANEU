# SPDX-License-Identifier: MIT
"""
`renewable_limits:` config section (T31); the rules are in ``scripts/_renewable_limits.py``.

Registered in ``scripts/lib/validation/config_updates.py`` like ``patex:``.
"""

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema


class RenewableLimitsConfig(BaseModel):
    """Capacity limits per country for wind and solar (T31)."""

    enable: bool = Field(
        False,
        description="Offshore wind per country capped at its goal (`offshore_goals_file`) "
        "at every horizon, instead of PyPSA-Eur's per-node potential; up to "
        "`planned_until`, onshore wind, offshore wind and solar capped at the capacity "
        "planned for that year. Caps count existing and new capacity.",
    )
    offshore_goals_file: str = Field(
        "data/offshore_wind_goals.csv",
        description="Offshore wind goals per country [GW] for 2030, 2040, 2050 (columns "
        "`gw_<year>`): Member States' non-binding TEN-E goals of January 2023, read in "
        "ENTSO-E's ONDP 2024 sea-basin reports.",
    )
    offshore_goal_year: int = Field(
        2050,
        description="Goal used as the offshore ceiling at every horizon after "
        "`planned_until`.",
    )
    planned_file: str | None = Field(
        None,
        description="Planned capacity per country [GW] at `planned_until`: columns "
        "`country`, `onwind`, `offwind`, `solar` (TYNDP 2026 National Trends+, "
        "`scripts/update_renewables_planned.py`); an empty cell: no cap (offshore: "
        "the `gw_<planned_until>` goal). Empty: offshore goal only.",
    )
    ground_pv_file: str | None = Field(
        None,
        description="Ground-mounted PV potential per country [GW] (columns `country`, "
        "`cap_gw`; `scripts/update_ground_pv_potential.py`): utility and tracking PV "
        "(existing and new) capped at `cap_gw` at every horizon. Empty: PyPSA-Eur's "
        "per-node potential only.",
    )
    rooftop_pv_file: str | None = Field(
        None,
        description="Rooftop PV technical potential per country [GW] (columns `country`, "
        "`gw`; JRC 2026 building-level data, `scripts/update_rooftop_pv_potential.py`): "
        "replaces PyPSA-Eur's 2 kW per inhabitant; each country's total is spread over "
        "its regions by population. Applies even when `enable` is false. Countries "
        "missing from the file keep 2 kW per inhabitant. Empty: PyPSA-Eur's rule.",
    )
    rooftop_pv_share: float = Field(
        1.0,
        description="Share of the technical potential of `rooftop_pv_file` used as the "
        "cap (1: all roofs; lower: deployable share, e.g. weak roofs, heritage, grid).",
    )
    planned_until: int | None = Field(
        2030,
        description="Horizons up to this year are capped at the planned capacity "
        "(empty: never).",
    )


class RenewableLimitsConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            renewable_limits=(
                RenewableLimitsConfig,
                Field(default_factory=RenewableLimitsConfig),
            ),
        )
