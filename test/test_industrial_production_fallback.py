# SPDX-License-Identifier: MIT
"""Countries missing from Eurostat in the reference year must not lose their industry
(GB after Brexit, found 2026-11-12)."""

import pandas as pd
import pytest

from scripts.build_industrial_production_per_country import (
    check_industry_present,
    eb_sectors,
    eurostat_industry_year,
)


def balances(values: dict[int, float], country="GB") -> pd.DataFrame:
    """Eurostat-like long table: one sector, ``values`` per year (zeros = no data)."""
    sector = next(iter(eb_sectors))
    return pd.DataFrame(
        [
            {"nrg_bal": sector, "siec": "TOTAL", "country": country, "year": y, "value": v}
            for y, v in values.items()
        ]
    )


def test_year_with_data_is_kept():
    assert eurostat_industry_year(balances({2019: 5.0, 2023: 4.0}), "GB", 2023) == 2023


def test_zero_rows_fall_back_to_latest_earlier_year():
    eurostat = balances({2018: 6.0, 2019: 5.0, 2020: 0.0, 2023: 0.0})
    assert eurostat_industry_year(eurostat, "GB", 2023) == 2019


def test_only_later_data_uses_earliest_later_year():
    assert eurostat_industry_year(balances({2025: 3.0, 2026: 2.0}), "GB", 2023) == 2025


def test_country_without_any_data_raises():
    with pytest.raises(ValueError, match="no industry data for XX"):
        eurostat_industry_year(balances({2019: 5.0}), "XX", 2023)


def test_country_without_industry_raises():
    demand = pd.DataFrame(
        {"Cement": [10.0, 0.0], "Ammonia": [1.0, 364.0]}, index=["NO", "GB"]
    )
    with pytest.raises(ValueError, match=r"\['GB'\]"):
        check_industry_present(demand)
    check_industry_present(demand.loc[["NO"]])


def test_jrc_labels_matched_to_eurostat_names():
    from scripts.build_industrial_production_per_country import align_sector_labels

    jrc = pd.Series(1.0, index=[n.replace("Non Ferrous Metals", "Non-ferrous metals")
                                for n in eb_sectors.values()])
    out = align_sector_labels(jrc)
    assert "Non Ferrous Metals" in out.index
    with pytest.raises(ValueError, match="Iron and steel"):
        align_sector_labels(jrc.drop("Iron and steel"))
