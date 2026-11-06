# SPDX-License-Identifier: MIT
"""
Snakemake wrapper: bring the PatEx demands of one planning horizon into resources/.

The extraction lives in the sibling ``PATEX_PyPSA`` repository (run
``patex-pypsa export-coupling`` in the PatEx environment first). This script
only checks the bundle and copies it, so that every PyPSA-Eur run records the
exact PatEx inputs it used.
"""

import json
import logging
import shutil
from pathlib import Path

from scripts._helpers import configure_logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_patex_demands", horizon="2030")
    configure_logging(snakemake)

    horizon = int(snakemake.wildcards.horizon)
    manifest = json.loads(Path(snakemake.input.manifest).read_text())

    if horizon not in manifest["horizons"]:
        raise ValueError(
            f"PatEx bundle exported for {manifest['horizons']}, not {horizon}: "
            "re-run `patex-pypsa export-coupling --horizons ...`"
        )
    modelled = set(snakemake.params.countries)
    fallback = set(snakemake.params.fallback_countries)
    missing = sorted(modelled - set(manifest["countries"]) - fallback)
    if missing:
        raise ValueError(
            f"no PatEx data for {missing}: add them to the PatEx run, or to "
            "patex.fallback_countries to keep the PyPSA-Eur demands"
        )
    kept = sorted(modelled & fallback)
    if kept:
        logger.info(
            "PyPSA-Eur preprocessed demands kept for %s (patex.fallback_countries)",
            kept,
        )
    if manifest.get("uncovered_slices"):
        logger.warning(
            "%d PatEx slices are mapped by no rule (see coverage.csv)",
            manifest["uncovered_slices"],
        )

    for name in (
        "energy_totals",
        "industry",
        "parameters",
        "co2_intensity",
        "supply",
        "manifest",
    ):
        shutil.copy2(snakemake.input[name], snakemake.output[name])
