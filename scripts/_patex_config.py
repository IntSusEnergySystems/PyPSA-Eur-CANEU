# SPDX-License-Identifier: MIT
"""
`patex:` config section for the PatEx soft-link.

Registered in ``scripts/lib/validation/config_updates.py`` (PyPSA-Eur's
soft-fork extension point, see doc/validation_dev.md). ``name`` is empty so that
``pixi run generate-config`` writes the section into ``config.default.yaml``,
which is where Snakemake reads the defaults from.
"""

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema


class PatexConfig(BaseModel):
    """PatEx → PyPSA-Eur demand soft-link."""

    enable: bool = Field(
        False, description="Use PatEx demands for the countries of the run."
    )
    coupling_dir: str | None = Field(
        None,
        description="Bundle written by `patex-pypsa export-coupling` (holds pypsa_inputs/).",
    )
    fallback_countries: list[str] = Field(
        default_factory=lambda: ["AL", "BA", "CH", "GB", "ME", "MK", "NO", "RS", "XK"],
        description="Countries without PatEx data: they keep the PyPSA-Eur preprocessed "
        "demands. Any other modelled country missing from the PatEx bundle is an error.",
    )
    energy_totals: bool = Field(
        True,
        description="Override buildings, transport and agriculture annual totals per country.",
    )
    industry: bool = Field(
        True,
        description="Override industrial final energy per carrier and process emissions.",
    )
    co2_intensity: bool = Field(
        True,
        description="CO2 intensity of gas, oil and coal from PatEx's emission factors.",
    )
    district_heating: bool = Field(
        True,
        description="District heating share of heat demand per country from PatEx.",
    )
    base_load: bool = Field(
        True,
        description="Rescale the residual electricity load per country to the PatEx value.",
    )


class PatexConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            patex=(PatexConfig, Field(default_factory=PatexConfig)),
        )
