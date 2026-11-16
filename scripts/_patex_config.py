# SPDX-License-Identifier: MIT
"""
`patex:` config section for the PatEx soft-link.

Registered in ``scripts/lib/validation/config_updates.py`` (PyPSA-Eur's
soft-fork extension point, see doc/validation_dev.md). ``name`` is empty so that
``pixi run generate-config`` writes the section into ``config.default.yaml``,
which is where Snakemake reads the defaults from.
"""

from typing import Literal

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
    fallback_demand: Literal["pypsa", "eu_trend"] = Field(
        "pypsa",
        description="Demand of the modelled `fallback_countries`: `pypsa` = PyPSA-Eur's "
        "own pathways; `eu_trend` = the country's own base-year data (PyPSA-Eur energy "
        "totals; Eurostat and UNFCCC relative to the PatEx countries for industry) on "
        "the relative trend of the sum over the PatEx countries, fuel shares following "
        "the EU's relative change (patex_pypsa.fallback; user, 2026-11-12). Their rows "
        "are added to the PatEx tables, so every soft-link hook applies to them; import "
        "caps and CO2 storage still treat them as fallback countries.",
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
    heating_efficiencies: bool = Field(
        True,
        description="Final-to-useful building heat conversion of the PatEx countries with "
        "PatEx's own efficiencies (bundle `total {sector} {use} efficiency` = PatEx "
        "useful heat / final heat, technology mix of the horizon; audit #4) instead of "
        "`heating_efficiencies.csv` (today's mix): heat demand = PatEx's useful heat. The "
        "bundle's district heat share is on this useful heat. Fallback countries keep "
        "PyPSA-Eur's efficiencies.",
    )
    base_load: bool = Field(
        True,
        description="Rescale the residual electricity load per country to the PatEx value.",
    )
    cooling: bool = Field(
        False,
        description="PatEx's electric space cooling (bundle `electricity {residential,"
        "services} space cooling`) as its own load per node, with the Hotmaps "
        "residential and tertiary cooling profiles applied to the weather year, instead "
        "of inside the rescaled base load; today's electric cooling (JRC-IDEES, weather "
        "year) is taken out of the measured load with the same profiles (audit #5b). "
        "Fallback countries keep cooling in their base load. Needs `base_load`.",
    )
    gb_load_dukes: bool = Field(
        False,
        description="Scale Great Britain's measured load of the weather year to DUKES "
        "'Electricity available' (UK consumption + losses, DUKES 5.1.2, "
        "`data/dukes_electricity_available.csv`): upstream's NESO National Demand "
        "excludes embedded wind and solar (2013: -13 %, 2023: -25 %). Hourly shape kept.",
    )
    temperature_shift: dict[int, float] = Field(
        default_factory=dict,
        description="Uniform shift [°C] added, per planning horizon, to the weather year's "
        "outdoor temperature for the heat demand profile, the cooling profiles "
        "(`patex.cooling`), heat-pump COPs (air and ground sources) and district heating "
        "forward temperatures: the climate trend between the weather year and the "
        "horizon (audit #5b; user, 2026-11-16: weather year 2023, +0.3 °C in 2030, "
        "+0.7 °C in 2040, 0.4 °C per decade). Annual totals are unchanged (PatEx's); "
        "what today's measured load holds (electric heating, today's cooling) keeps "
        "the unshifted profiles. Horizons not listed: no shift.",
    )
    phev_fleet_factor: float = Field(
        0.0,
        description="Weight of a plug-in hybrid in the EV fleet that sizes chargers and EV "
        "batteries (PatEx `number bev` + factor × `number phev`; T16: 0, PHEVs count as "
        "combustion cars, their electric km stay in the load).",
    )
    import_limits: bool = Field(
        True,
        description="With `import_limits.enable`: caps on gross imports per fuel = PatEx "
        "imports summed over the modelled countries (replace `import_limits.limits`).",
    )
    fallback_import_caps: Literal["eu_per_capita", "eurostat"] = Field(
        "eu_per_capita",
        description="Import caps of the modelled countries without PatEx data (GB, NO, "
        "CH...), per fuel: `eu_per_capita` = EU import cap per person (PatEx caps of "
        "every country of the bundle / their population, JRC ARDECO) x the country's "
        "population (user, 2026-11-10); `eurostat` = its own Eurostat imports today.",
    )
    co2_sequestration: bool = Field(
        True,
        description="Total CO2 sequestration cap of each horizon = PatEx's CO2 stored "
        "summed over the modelled countries (replaces `sector.co2_sequestration_"
        "potential`; T32). Fallback countries have no PatEx figure and share it.",
    )
    plastics_eol_co2: bool = Field(
        False,
        description="CO2 of plastics (HVC) that are not burned for energy. False = PatEx / "
        "inventory convention: only waste-to-energy plants emit (`industry: "
        "waste_to_energy`); True = PyPSA-Eur default, all of it goes to the air.",
    )
    waste_to_energy: bool = Field(
        False,
        description="Plastics end of life as in PatEx and the 1990 inventory (audit #2): "
        "the non-renewable waste PatEx burns in power and heat plants (bundle "
        "`waste to energy fuel` / `co2`) must be burned in waste CHPs within the year, at "
        "PatEx's CO2 factor; the rest of the naphtha carbon stays in products (no "
        "`HVC to air`). Needs `industry: waste_to_energy` and `plastics_eol_co2: false`.",
    )


class PatexConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            patex=(PatexConfig, Field(default_factory=PatexConfig)),
        )
