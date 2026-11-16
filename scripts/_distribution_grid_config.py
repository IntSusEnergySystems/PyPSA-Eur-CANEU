# SPDX-License-Identifier: MIT
"""
`distribution_grid:` config section: refinements of the electricity distribution grid
(PyPSA-Eur-CANEU, 2026-11-10; method after the pypsa-wal network-cost review).

Standalone (no PatEx needed), default off. Registered in
``scripts/lib/validation/config_updates.py``. The unit cost and discount rate of the
distribution grid itself are set through ``costs.overwrites``.
"""

from pydantic import BaseModel, Field

from scripts.lib.validation.config._base import ConfigUpdater
from scripts.lib.validation.config._schema import ConfigSchema


class DistributionGridConfig(BaseModel):
    """Which loads use the distribution grid, and the cost of hosting rooftop PV."""

    enable: bool = Field(
        False,
        description="Apply `industry_hv_share` and `pv_hosting_cost` (needs "
        "`sector.electricity_distribution_grid`).",
    )
    industry_hv_share: float | dict[str, float] = Field(
        0.0,
        description="Share of `industry electricity` connected at transmission level, "
        "left on the transmission bus instead of the low-voltage bus; one number or "
        "{country: share} (missing countries: key `default`, else 0).",
    )
    pv_hosting_cost: float = Field(
        0.0,
        description="Distribution reinforcement caused by rooftop PV [EUR/kWp], added "
        "to the rooftop PV capital cost at the annuity (discount rate, lifetime, FOM) "
        "of the `electricity distribution grid`.",
    )


#: Network assets financed at the regulated cost of capital: electricity distribution,
#: transmission lines / cables / converters, offshore wind grid connections, pipelines
NETWORK_TECHNOLOGIES = [
    "electricity distribution grid",
    "distribution grid reinforcement",
    "HVAC overhead",
    "HVAC underground",
    "HVAC submarine",
    "HVDC overhead",
    "HVDC underground",
    "HVDC submarine",
    "HVDC inverter pair",
    "offwind-ac-connection-submarine",
    "offwind-ac-connection-underground",
    "offwind-ac-station",
    "offwind-dc-connection-submarine",
    "offwind-dc-connection-underground",
    "offwind-dc-station",
    "offwind-float-connection-submarine",
    "offwind-float-connection-underground",
    "offwind-float-station",
    "CH4 (g) pipeline",
    "CH4 (g) submarine pipeline",
    "H2 (g) pipeline",
    "H2 (g) pipeline repurposed",
    "H2 (g) submarine pipeline",
    "H2 (g) submarine pipeline repurposed",
    "H2 pipeline",
    "CO2 pipeline",
    "CO2 submarine pipeline",
]


class NetworkCostsConfig(BaseModel):
    """One discount rate for all regulated network assets (central parameter)."""

    discount_rate: float | None = Field(
        None,
        description="Real discount rate of the network assets in `technologies` "
        "(regulated cost of capital), replacing their `discount rate` before the "
        "annuity is computed. None: technology-data / `costs.fill_values`.",
    )
    technologies: list[str] = Field(
        default_factory=lambda: list(NETWORK_TECHNOLOGIES),
        description="Cost-table technologies financed as regulated networks.",
    )


class NetworkCostsConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            network_costs=(NetworkCostsConfig, Field(default_factory=NetworkCostsConfig)),
        )


class DistributionGridConfigUpdater(ConfigUpdater):
    name: str = ""
    docs_url: str | None = None

    def update(self) -> type[ConfigSchema]:
        return self._apply_updates(
            distribution_grid=(DistributionGridConfig, Field(default_factory=DistributionGridConfig)),
        )
