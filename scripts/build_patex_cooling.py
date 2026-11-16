# SPDX-License-Identifier: MIT
"""
Hourly electric space-cooling profiles per clustered region and sector, and today's
electric space cooling per country and sector (PatEx soft-link, ``patex.cooling``,
audit #5b).

PyPSA-Eur has no cooling demand: today's cooling is only inside the measured
electricity load. With ``patex.cooling``, ``prepare_sector_network`` takes it out of
that load and adds PatEx's electric cooling as its own load, with these profiles.

Method: the Hotmaps generic cooling profiles (Fraunhofer ISI for the H2020 Hotmaps
project; Pezzutto et al. 2019, D2.3 section 2.7.2-2.7.3; CC BY 4.0), applied to the
weather year of the snapshots. Hotmaps gives, per country, sector (residential,
tertiary), day type (weekday, Saturday, Sunday) and hour of the day (local time), a
load proportional to the daily mean outdoor temperature above 18 °C
(``data/hotmaps_cooling_profiles.csv``, slopes per K, derived by
``PATEX_PyPSA/scripts/hotmaps_cooling_table.py``):

    load(t) = slope[country, sector, day type(t), hour(t)] × max(T_day(t) − 18 °C, 0)

``T_day`` is the daily mean of the cutout temperature in each cell (day boundaries at
UTC+1, ``atlite`` ``cooling_demand``); cells are weighted by population and summed over
each region, so a region's total also sets its share of its country's cooling (more
people, warmer climate: more cooling). Hotmaps' holidays (day type 1 = day before a
holiday, 2 = holiday) are not modelled: weekdays, Saturdays and Sundays only.

Outputs

- ``cooling_profile``: variables ``residential`` and ``services``, dims (time, name),
  hourly over the snapshots (UTC, like the load) [person K, unitless scale].
- ``cooling_today``: columns ``residential`` and ``services``: electric space cooling of
  each PatEx country in the weather year(s) of the snapshots (JRC-IDEES 2023:
  residential air conditioning and services electric space cooling, rows
  ``...Thermal.SC.AC.Elec``; years outside its range, 2000-2023, clamped) [TWh/a].
  Countries without a JRC-IDEES file (GB, NO, CH...): NaN.
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from scripts._helpers import (
    configure_logging,
    get_snapshots,
    load_cutout,
    set_scenario_config,
    setup_dask,
)

logger = logging.getLogger(__name__)

KTOE_TO_TWH = 11.63 / 1e3
#: Hotmaps' temperature below which there is no cooling [°C]
BASE_TEMPERATURE = 18.0
#: PyPSA-Eur country code -> JRC-IDEES code
IDEES_CODES = {"GR": "EL", "GB": "UK"}
#: sector -> JRC-IDEES file, sheet and row code of electric space cooling
IDEES_COOLING = {
    "residential": ("Residential", "RES_hh_fec", ".Res.HH.Thermal.SC.AC.Elec"),
    "services": ("Tertiary", "SER_hh_fec", ".Ser.Bld.Thermal.SC.AC.Elec"),
}
SECTORS = list(IDEES_COOLING)
#: time zone of each country's clock (Hotmaps hours are local time)
TIME_ZONES = {
    "GB": "Europe/London",
    "IE": "Europe/Dublin",
    "PT": "Europe/Lisbon",
    "FI": "Europe/Helsinki",
    "EE": "Europe/Tallinn",
    "LV": "Europe/Riga",
    "LT": "Europe/Vilnius",
    "BG": "Europe/Sofia",
    "RO": "Europe/Bucharest",
    "GR": "Europe/Athens",
    "CY": "Asia/Nicosia",
}
DEFAULT_TIME_ZONE = "Europe/Brussels"  # central European time


def idees_electric_cooling(
    idees_dir: str, country: str, years: list[int], sector: str
) -> float:
    """Electric space cooling of ``sector`` [TWh/a], mean over ``years``."""
    code = IDEES_CODES.get(country, country)
    name, sheet, suffix = IDEES_COOLING[sector]
    path = Path(idees_dir) / code / f"JRC-IDEES-2023_{name}_{code}.xlsx"
    if not path.exists():
        return float("nan")
    df = pd.read_excel(path, sheet_name=sheet, index_col=0)
    rows = df[df["Code"].astype(str).str.endswith(suffix)]
    if len(rows) != 1:
        raise ValueError(f"{path}: {len(rows)} rows ending in {suffix}")
    available = [c for c in df.columns if isinstance(c, (int, np.integer))]
    used = sorted({min(max(y, min(available)), max(available)) for y in years})
    return float(rows[used].iloc[0].mean()) * KTOE_TO_TWH


def hourly_profiles(
    daily: pd.DataFrame, slopes: pd.DataFrame, time: pd.DatetimeIndex
) -> dict[str, pd.DataFrame]:
    """
    Hourly profile per sector: Hotmaps slope of the node's country at the local day
    type and hour × the node's cooling degree days of the local day.

    ``daily``: day × node population-weighted cooling degree days; ``slopes``: index
    (country, day_type, hour), columns = sectors; ``time``: hourly UTC snapshots.
    """
    out = {s: pd.DataFrame(0.0, index=time, columns=daily.columns) for s in SECTORS}
    days = pd.DatetimeIndex(daily.index).normalize()
    countries = slopes.index.get_level_values("country")
    for ct, nodes in daily.columns.groupby(daily.columns.str[:2]).items():
        nodes = list(nodes)
        if ct not in countries:
            logger.warning(f"No Hotmaps cooling profile for {ct}: no cooling profile")
            continue
        local = time.tz_localize("UTC").tz_convert(TIME_ZONES.get(ct, DEFAULT_TIME_ZONE))
        day_type = np.select([local.weekday < 5, local.weekday == 5], [0, 1], 2)
        keys = pd.MultiIndex.from_arrays(
            [[ct] * len(time), day_type, local.hour + 1], names=slopes.index.names
        )
        slope = slopes.reindex(keys)
        local_day = local.tz_localize(None).normalize()
        degrees = (
            daily.set_axis(days)[nodes].reindex(local_day, method="nearest").set_axis(time)
        )
        for sector in SECTORS:
            out[sector][nodes] = degrees.multiply(slope[sector].values, axis=0)
    return out


def full_load_hours(profile: pd.DataFrame) -> pd.Series:
    """Annual sum / peak of each country's profile [h]."""
    by_country = profile.T.groupby(profile.columns.str[:2]).sum().T
    return by_country.sum() / by_country.max()


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_patex_cooling")
    configure_logging(snakemake)
    set_scenario_config(snakemake)

    params = snakemake.params
    time = get_snapshots(params.snapshots, params.drop_leap_day)
    daily_index = get_snapshots(params.snapshots, params.drop_leap_day, freq="D")
    years = sorted(set(time.year))

    # today's electric cooling of the PatEx countries (rule build_patex_cooling only;
    # build_patex_cooling_horizon writes the shifted profile only)
    if "cooling_today" in snakemake.output.keys():
        countries = [c for c in params.countries if c not in params.fallback_countries]
        today = pd.DataFrame(
            {
                s: {
                    c: idees_electric_cooling(snakemake.input.idees, c, years, s)
                    for c in countries
                }
                for s in SECTORS
            }
        )
        today.index.name = "country"
        logger.info(
            f"Electric space cooling in the measured load (JRC-IDEES, years {years}) "
            f"[TWh/a]:\n{today.round(3)}"
        )
        today.to_csv(snakemake.output.cooling_today)

    # PatEx soft-link (patex.temperature_shift): outdoor temperature + shift, i.e.
    # threshold 18 °C - shift
    temperature_shift = float(getattr(params, "temperature_shift", 0.0))

    # population-weighted daily cooling degree days (18 °C) per region
    dask_kwargs = setup_dask(int(snakemake.threads))
    cutout = load_cutout(snakemake.input.cutout, time=time)
    regions = gpd.read_file(snakemake.input.onshore_regions).set_index("name").buffer(0)
    indicator = cutout.indicatormatrix(regions)
    pop = xr.open_dataarray(snakemake.input.pop_layout).stack(spatial=("y", "x"))
    matrix = indicator.multiply(pop.values[np.newaxis, :]).tocsr()
    daily = (
        cutout.cooling_demand(
            matrix=matrix,
            index=regions.index,
            threshold=BASE_TEMPERATURE - temperature_shift,
            hour_shift=1.0,
            dask_kwargs=dask_kwargs,
            show_progress=False,
        )
        .sel(time=daily_index)
        .to_pandas()
    )

    slopes = pd.read_csv(snakemake.input.hotmaps, index_col=["country", "day_type", "hour"])
    profiles = hourly_profiles(daily, slopes, time)
    for sector, p in profiles.items():
        per_node = p.sum()
        logger.info(
            f"{sector} cooling (temperature shift {temperature_shift:+.2f} °C): "
            f"equivalent full-load hours per country "
            f"{full_load_hours(p).round(0).to_dict()}; regions without cooling: "
            f"{sorted(per_node.index[per_node <= 0])}"
        )
    xr.Dataset(
        {s: (("time", "name"), p.values) for s, p in profiles.items()},
        coords={"time": time, "name": daily.columns.values},
    ).to_netcdf(snakemake.output.cooling_profile)
