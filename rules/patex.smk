# SPDX-License-Identifier: MIT
#
# PatEx soft-link rules (included from the Snakefile after rules/build_sector.smk).


def patex_input(name):
    def f(w):
        coupling_dir = get_config(w)["patex"]["coupling_dir"]
        if not coupling_dir:
            raise ValueError("patex.enable is true but patex.coupling_dir is not set")
        return f"{coupling_dir}/pypsa_inputs/{name.format(horizon=getattr(w, 'horizon', ''))}"

    return f


def patex_trend_inputs(w):
    """Inputs of the fallback countries' EU trend (patex.fallback_demand: eu_trend)."""
    if get_config(w)["patex"]["fallback_demand"] != "eu_trend":
        return {}
    return {
        "trend_long": patex_input("patex_demands_long.csv")(w),
        "trend_co2_factors": patex_input("patex_co2_factors.csv")(w),
        "trend_energy_totals": resources("energy_totals.csv"),
        "trend_district_heat_share": resources("district_heat_share.csv"),
        "trend_eurostat": resources("eurostat_energy_balances.csv"),
        "trend_ghg": rules.retrieve_ghg_emissions.output["csv"],
        "trend_ammonia": resources("ammonia_production.csv"),
    }


rule build_patex_demands:
    """Copies one horizon's PatEx inputs into resources/, adding fallback countries on the EU trend."""
    input:
        unpack(patex_trend_inputs),
        energy_totals=patex_input("patex_energy_totals_{horizon}.csv"),
        industry=patex_input("patex_industry_{horizon}.csv"),
        parameters=patex_input("patex_parameters_{horizon}.csv"),
        co2_intensity=patex_input("patex_co2_intensity_{horizon}.csv"),
        supply=patex_input("patex_supply_{horizon}.csv"),
        manifest=patex_input("manifest.json"),
    output:
        energy_totals=resources("patex_energy_totals_{horizon}.csv"),
        industry=resources("patex_industry_{horizon}.csv"),
        parameters=resources("patex_parameters_{horizon}.csv"),
        co2_intensity=resources("patex_co2_intensity_{horizon}.csv"),
        supply=resources("patex_supply_{horizon}.csv"),
        manifest=resources("patex_manifest_{horizon}.json"),
    params:
        countries=config_provider("countries"),
        fallback_countries=config_provider("patex", "fallback_countries"),
        fallback_demand=config_provider("patex", "fallback_demand"),
        base_year=config_provider("energy", "energy_totals_year"),
    log:
        logs("build_patex_demands_{horizon}.log"),
    threads: 1
    resources:
        mem_mb=500,
    script:
        scripts("build_patex_demands.py")


def patex_temperature_shift(w):
    """Temperature shift [°C] of horizon ``w.horizon`` (``patex.temperature_shift``)."""
    patex = get_config(w)["patex"]
    if not patex["enable"]:
        return 0.0
    return float(patex["temperature_shift"].get(int(w.horizon), 0.0))


rule build_daily_heat_demand_horizon:
    """Builds daily heat demand per region with the horizon's temperature shift."""
    input:
        pop_layout=resources("pop_layout_total.nc"),
        onshore_regions=resources("onshore_regions.geojson"),
        cutout=lambda w: input_cutout(
            w, config_provider("sector", "heat_demand_cutout")(w)
        ),
    output:
        heat_demand=resources("daily_heat_demand_total_{horizon}.nc"),
    log:
        logs("build_daily_heat_demand_total_{horizon}.log"),
    benchmark:
        benchmarks("build_daily_heat_demand_total_{horizon}")
    threads: 8
    resources:
        mem_mb=20000,
    params:
        snapshots=config_provider("snapshots"),
        drop_leap_day=config_provider("enable", "drop_leap_day"),
        temperature_shift=patex_temperature_shift,
    script:
        scripts("build_daily_heat_demand.py")


rule build_hourly_heat_demand_horizon:
    """Builds hourly heat demand profiles with the horizon's temperature shift."""
    input:
        heat_profile="data/heat_load_profile_BDEW.csv",
        heat_demand=resources("daily_heat_demand_total_{horizon}.nc"),
    output:
        heat_demand=resources("hourly_heat_demand_total_{horizon}.nc"),
        heat_dsm_profile=resources("residential_heat_dsm_profile_{horizon}.csv"),
    log:
        logs("build_hourly_heat_demand_total_{horizon}.log"),
    benchmark:
        benchmarks("build_hourly_heat_demand_total_{horizon}")
    threads: 8
    resources:
        mem_mb=2000,
    params:
        snapshots=config_provider("snapshots"),
        drop_leap_day=config_provider("enable", "drop_leap_day"),
        sector=config_provider("sector"),
    script:
        scripts("build_hourly_heat_demand.py")


rule build_patex_cooling_horizon:
    """Builds hourly cooling profiles (Hotmaps) with the horizon's temperature shift."""
    input:
        pop_layout=resources("pop_layout_total.nc"),
        onshore_regions=resources("onshore_regions.geojson"),
        cutout=lambda w: input_cutout(
            w, config_provider("sector", "heat_demand_cutout")(w)
        ),
        hotmaps="data/hotmaps_cooling_profiles.csv",
    output:
        cooling_profile=resources("patex_cooling_profile_{horizon}.nc"),
    params:
        snapshots=config_provider("snapshots"),
        drop_leap_day=config_provider("enable", "drop_leap_day"),
        temperature_shift=patex_temperature_shift,
    log:
        logs("build_patex_cooling_{horizon}.log"),
    benchmark:
        benchmarks("build_patex_cooling_{horizon}")
    threads: 8
    resources:
        mem_mb=20000,
    script:
        scripts("build_patex_cooling.py")


rule build_patex_cooling:
    """Builds hourly cooling profiles (Hotmaps) per region and today's electric cooling."""
    input:
        pop_layout=resources("pop_layout_total.nc"),
        onshore_regions=resources("onshore_regions.geojson"),
        cutout=lambda w: input_cutout(
            w, config_provider("sector", "heat_demand_cutout")(w)
        ),
        idees=rules.retrieve_jrc_idees.output["directory"],
        hotmaps="data/hotmaps_cooling_profiles.csv",
    output:
        cooling_profile=resources("patex_cooling_profile.nc"),
        cooling_today=resources("patex_cooling_today.csv"),
    params:
        snapshots=config_provider("snapshots"),
        drop_leap_day=config_provider("enable", "drop_leap_day"),
        countries=config_provider("countries"),
        fallback_countries=config_provider("patex", "fallback_countries"),
    log:
        logs("build_patex_cooling.log"),
    benchmark:
        benchmarks("build_patex_cooling")
    threads: 8
    resources:
        mem_mb=20000,
    script:
        scripts("build_patex_cooling.py")


rule build_patex_report:
    """HTML Sankey (PatEx -> PyPSA-Eur inputs) and PatEx indicator pages of the bundle.

    Needs no solved network: it describes the PatEx side of the soft-link. Not part
    of `all`; request it explicitly:
    snakemake ... results/<run>/patex_report/index.html
    """
    input:
        flows=patex_input("sankey_flows.csv"),
        indicators=patex_input("patex_indicators.csv"),
        manifest=patex_input("manifest.json"),
    output:
        index=RESULTS + "patex_report/index.html",
    log:
        RESULTS + "logs/build_patex_report.log",
    threads: 1
    resources:
        mem_mb=2000,
    run:
        from pathlib import Path

        from patex_pypsa.pages import write_report

        coupling_dir = Path(input.manifest).parent.parent
        write_report(coupling_dir, Path(output.index).parent)
