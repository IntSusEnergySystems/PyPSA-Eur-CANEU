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


rule build_patex_demands:
    """Copies the PatEx inputs of one horizon (demands, parameters, CO2 intensity) into resources/."""
    input:
        energy_totals=patex_input("patex_energy_totals_{horizon}.csv"),
        industry=patex_input("patex_industry_{horizon}.csv"),
        parameters=patex_input("patex_parameters_{horizon}.csv"),
        co2_intensity=patex_input("patex_co2_intensity_{horizon}.csv"),
        industry_co2_intensity=patex_input("patex_industry_co2_intensity_{horizon}.csv"),
        manifest=patex_input("manifest.json"),
    output:
        energy_totals=resources("patex_energy_totals_{horizon}.csv"),
        industry=resources("patex_industry_{horizon}.csv"),
        parameters=resources("patex_parameters_{horizon}.csv"),
        co2_intensity=resources("patex_co2_intensity_{horizon}.csv"),
        industry_co2_intensity=resources("patex_industry_co2_intensity_{horizon}.csv"),
        manifest=resources("patex_manifest_{horizon}.json"),
    params:
        countries=config_provider("countries"),
        fallback_countries=config_provider("patex", "fallback_countries"),
    log:
        logs("build_patex_demands_{horizon}.log"),
    threads: 1
    resources:
        mem_mb=500,
    script:
        scripts("build_patex_demands.py")


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
