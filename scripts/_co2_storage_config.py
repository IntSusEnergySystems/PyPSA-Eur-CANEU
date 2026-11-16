# SPDX-License-Identifier: MIT
"""
`co2_storage:` config section (T32); the rules are in ``scripts/_co2_storage.py``.

Registered in ``scripts/lib/validation/config_updates.py`` like ``patex:``.
"""

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema


class CO2StorageConfig(BaseModel):
    """Geological CO2 storage per country from injection projects (T32)."""

    enable: bool = Field(
        False,
        description="Cap the CO2 sequestered per country and year at the injection "
        "capacity of its storage projects (`projects_file`), all build years of the "
        "`co2 sequestered` stores together. Replaces the CO2StoP limits per node "
        "(`sector.regional_co2_sequestration_potential`); the total over all countries "
        "(`sector.co2_sequestration_potential`) still applies. Needs `co2_spatial`.",
    )
    projects_file: str = Field(
        "data/co2_storage_projects.csv",
        description="European storage projects from the IEA CCUS Projects Database "
        "(`scripts/update_co2_storage_projects.py`).",
    )
    built_only_until: int = Field(
        2030,
        description="Up to this horizon only projects in operation or under "
        "construction count (FID taken); after it, planned projects count from their "
        "operation year.",
    )
    undated_from: int | None = Field(
        2040,
        description="Planned projects without an operation year count from this "
        "horizon (empty: never).",
    )


class CO2StorageConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            co2_storage=(CO2StorageConfig, Field(default_factory=CO2StorageConfig)),
        )
