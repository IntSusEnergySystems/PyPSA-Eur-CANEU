# SPDX-License-Identifier: MIT
"""
`nuclear_fleet:` config section (T34); the rules are in ``scripts/_nuclear_fleet.py``.

Registered in ``scripts/lib/validation/config_updates.py`` like ``patex:``.
"""

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema


class NuclearFleetConfig(BaseModel):
    """Nuclear fleet from an official per-reactor table (T34)."""

    enable: bool = Field(
        False,
        description="Replace PyPSA-Eur's nuclear (powerplantmatching generators and "
        "links) by one link per reactor of `fleet_file`, at every planning horizon.",
    )
    fleet_file: str = Field(
        "data/nuclear_fleet.csv",
        description="Per-reactor table: country, reactor, lat, lon, net_mw, "
        "commissioning_year, retirement_year (official, may be empty), "
        "end_date_includes_extension, lifetime (official, may be empty), status, "
        "sources.",
    )
    default_lifetime: float | None = Field(
        None,
        description="Lifetime [a] of reactors with neither an official retirement year "
        "nor an official lifetime; empty = the cost data's nuclear lifetime.",
    )
    extension_years: int = Field(
        10, description="One lifetime extension [a] after the retirement year."
    )
    min_remaining_years: int = Field(
        4,
        description="A reactor is not used at a horizon if its retirement year (after "
        "extension) is within this many years after the horizon.",
    )
    optional_extension: bool = Field(
        True,
        description="True: the model decides whether to keep a reactor in its "
        "extension (at the fixed O&M cost); false: it is kept.",
    )
    must_run_margin: float | None = Field(
        None,
        description="Must-run: p_min_pu = p_max_pu − margin (per unit of capacity; "
        "p_max_pu = `conventional.nuclear.p_max_pu`). Empty = fully flexible.",
    )


class NuclearFleetConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            nuclear_fleet=(NuclearFleetConfig, Field(default_factory=NuclearFleetConfig)),
        )
