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


#: fuel → links carrying it between countries: their gross inflow into a region counts
#: as an import of that region (pipelines are one-way link pairs in PyPSA-Eur)
PIPELINES = {
    "gas": ["gas pipeline", "gas pipeline new"],
    "H2": ["H2 pipeline", "H2 pipeline retrofitted"],
}

#: fuels supplied on an EU-wide bus ("pool"): bus carriers of the pool. Countries outside
#: the PatEx region get their own copy of the pool's import / production components;
#: their net annual flow into the pool counts as an import of the EU (and their net draw
#: from it as their own import), in the cap of ``POOL_FLOW_FUEL``
POOLS = {
    "oil": ["oil primary", "oil"],
    "coal": ["coal", "lignite"],
    "methanol": ["methanol"],
    "NH3": ["NH3"],
}
#: fuel → pool it is supplied into
POOL_OF = {"oil": "oil", "synthetic oil": "oil", "bioliquids": "oil", "coal": "coal",
           "methanol": "methanol", "NH3": "NH3"}
#: pool → fuel whose cap counts the net flows (liquids of any origin count as oil)
POOL_FLOW_FUEL = {"oil": "oil", "coal": "coal", "methanol": "methanol", "NH3": "NH3"}

#: Eurostat SIEC of the imports and domestic production of countries without PatEx data
#: (`patex.fallback_countries`, e.g. GB, NO); a fuel without code: no import today, cap 0
EUROSTAT_IMPORTS = {
    "gas": ["G3000"],
    "oil": ["O4000XBIO"],
    "coal": ["C0000X0350-0370"],
    "solid biomass": ["R5110-5150_W6000RI"],
    "biogas": ["R5300"],
    "bioliquids": ["R5210P", "R5220P", "R5230P", "R5290"],
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
    transit_penalty: float = Field(
        0.01,
        description="Tie-break [EUR/MWh] on fuel flows between the PatEx region and a "
        "modelled non-PatEx country (net flows into or out of the EU-wide pools; gas and "
        "H2 pipelines crossing that boundary). Trade costs the same as importing from "
        "abroad; without it the solver is indifferent and may route one side's imports "
        "through the other. Not a cost estimate.",
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
