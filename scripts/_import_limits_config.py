# SPDX-License-Identifier: MIT
"""
`import_limits:` config section: caps on gross imports per fuel for the whole
optimised region (self-sufficiency scenarios).

Standalone (no PatEx needed). Registered in
``scripts/lib/validation/config_updates.py`` like ``patex:``; with
``patex.import_limits`` the caps come from the PatEx bundle instead.
"""

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema

#: fuel → (component, carriers) whose supply counts as import of that fuel.
#: Links count their output (p × efficiency), generators their dispatch.
IMPORT_FUELS = {
    # fossil: LNG and pipeline entries (domestic production is split off as
    # `gas production` when the limits are enabled and the gas network is on)
    "gas": ("Generator", ["gas"]),
    "oil": ("Generator", ["oil primary", "oil"]),
    # PyPSA-Eur has no domestic hard coal; lignite is domestic
    "coal": ("Generator", ["coal"]),
    "H2": ("Generator", ["import H2"]),
    "NH3": ("Generator", ["import NH3"]),
    # carbon-neutral imports (`sector.imports`, `sector.solid_biomass_import`,
    # `import_limits.bio_imports`)
    "synthetic gas": ("Link", ["import gas"]),
    "synthetic oil": ("Link", ["import oil"]),
    "methanol": ("Link", ["import methanol"]),
    "solid biomass": ("Link", ["solid biomass import"]),
    "biogas": ("Link", ["import biogas"]),
    "bioliquids": ("Link", ["import bioliquids"]),
}

#: fuel → domestic supply components (``import_limits.domestic``). Generators
#: added by ``add_domestic_supply`` (gas: the split-off production generators);
#: lignite counts as domestic coal.
DOMESTIC_FUELS = {
    "gas": ("Generator", ["gas production"]),
    "oil": ("Generator", ["oil production"]),
    "coal": ("Generator", ["coal production", "lignite"]),
}


class ImportLimitsConfig(BaseModel):
    """Caps on gross imports per fuel, summed over all modelled countries."""

    enable: bool = Field(
        False,
        description="Add one global constraint per capped fuel (type `import_limit`).",
    )
    limits: dict[str, float | dict[int, float]] = Field(
        default_factory=dict,
        description="Fuel → cap [TWh/a] for the whole optimised region, a number or "
        "{planning horizon: number}. Fuels: " + ", ".join(IMPORT_FUELS) + ".",
    )
    domestic: dict[str, float | dict[int, float]] = Field(
        default_factory=dict,
        description="Fuel → cap on domestic production [TWh/a], whole region (fuels: "
        + ", ".join(DOMESTIC_FUELS)
        + "). Adds a domestic generator for oil and coal (PyPSA-Eur has none: "
        "without it all their supply counts as import); lignite counts as coal.",
    )
    bio_imports: list[str] = Field(
        default_factory=list,
        description="Add carbon-neutral imports of `biogas` (into the gas buses) and/or "
        "`bioliquids` (into the oil bus), priced like PyPSA-Eur's domestic biogas and "
        "bioliquids (technology-data `biogas` and `biodiesel crops` fuel costs).",
    )


class ImportLimitsConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            import_limits=(ImportLimitsConfig, Field(default_factory=ImportLimitsConfig)),
        )
