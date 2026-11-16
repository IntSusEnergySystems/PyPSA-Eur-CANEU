# SPDX-License-Identifier: MIT
"""
`interconnection_limits:` config section (T30); the rules are in
``scripts/_interconnection_limits.py``.

Registered in ``scripts/lib/validation/config_updates.py`` like ``patex:``.
"""

from typing import Literal

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema


class InterconnectionLimitsConfig(BaseModel):
    """Cross-border transmission capacity per border (T30)."""

    enable: bool = Field(
        False,
        description="Cap the usable capacity of each border (AC lines × s_max_pu + DC "
        "links, existing and new) at factor[horizon] × (usable capacity of PyPSA-Eur's "
        "grid + transfer-capacity increase of the TYNDP projects commissioned up to "
        "the horizon).",
    )
    projects_file: str = Field(
        "data/interconnection_projects_tyndp2024.csv",
        description="TYNDP 2024 transmission projects per border "
        "(`scripts/update_interconnection_projects.py`).",
    )
    project_statuses: list[int] = Field(
        default_factory=lambda: [2, 3, 4],
        description="TYNDP status IDs counted: 1 under consideration, 2 in planning, "
        "3 in permitting, 4 under construction.",
    )
    in_grid_until: int = Field(
        2025,
        description="Projects commissioned up to this year are taken as already in "
        "PyPSA-Eur's grid (OSM data) and not added.",
    )
    direction: Literal["max", "min", "mean"] = Field(
        "max",
        description="How the two directions of a project's transfer-capacity increase "
        "become one value (PyPSA lines and links are symmetric).",
    )
    factor: dict[int, float] = Field(
        default_factory=lambda: {2030: 1.0, 2035: 1.5, 2040: 1.5, 2045: 1.5, 2050: 1.5},
        description="Cap multiplier per planning horizon (a horizon without an entry "
        "takes the latest earlier one).",
    )
    ntc_file: str | None = Field(
        "data/interconnection_ntc_2030.csv",
        description="TYNDP 2026 reference-grid NTC 2030, logged next to each cap for "
        "comparison only (empty: no comparison).",
    )


class InterconnectionLimitsConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            interconnection_limits=(
                InterconnectionLimitsConfig,
                Field(default_factory=InterconnectionLimitsConfig),
            ),
        )
