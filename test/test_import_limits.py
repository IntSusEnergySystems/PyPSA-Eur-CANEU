# SPDX-License-Identifier: MIT
"""Import and domestic supply caps per fuel and region (import_limits, T29 / T30 run)."""

import pandas as pd
import pypsa
import pytest

from scripts.prepare_sector_network import (
    add_supply_limits,
    eurostat_latest,
    patex_supply_limits,
    split_pooled_supply,
)
from scripts.solve_network import add_supply_limits_per_fuel


def balances():
    rows = []
    for year in (2019, 2023):
        # GB: data until 2019, zeros afterwards (Eurostat after Brexit)
        gb = 500.0 if year == 2019 else 0.0
        rows += [("IMP", "G3000", "GB", year, gb), ("PPRD", "G3000", "GB", year, gb / 2)]
        rows += [("IMP", "G3000", "NO", year, 1.0), ("PPRD", "G3000", "NO", year, 1200.0)]
        # GB: another series still filled after 2019 must not select 2023 for imports
        rows += [("FC_E", "G3000", "GB", year, 300.0)]
        # BE: real zero coal production, data in 2023
        rows += [("PPRD", "C0000X0350-0370", "BE", year, 5.0 if year == 2019 else 0.0),
                 ("PPRD", "G3000", "BE", year, 0.1), ("IMP", "G3000", "BE", year, 220.0)]
    return pd.DataFrame(rows, columns=["nrg_bal", "siec", "country", "year", "value"])


def test_eurostat_year_per_country():
    codes = {"gas": ["G3000"], "coal": ["C0000X0350-0370"]}
    out = eurostat_latest(balances(), "PPRD", ["BE", "GB"], codes, 2023)
    assert out.at["BE", "coal"] == 0.0  # zero in a year with data stays zero
    assert out.at["GB", "gas"] == 250.0  # GB: latest year with data, 2019


def test_patex_limits_with_fallback_countries(tmp_path):
    supply = pd.DataFrame(
        {"gas": [100.0, 50.0], "gas production": [0.5, 0.0], "oil": [300.0, 10.0]},
        index=["BE", "NL"],
    )
    supply.to_csv(tmp_path / "supply.csv")
    balances().to_csv(tmp_path / "eurostat.csv", index=False)
    out = patex_supply_limits(tmp_path / "supply.csv", ["BE", "NL", "GB"],
                              tmp_path / "eurostat.csv", 2023, ["GB", "NO", "CH"])
    gas = out["import"]["gas"]
    # PatEx countries together; BE production above today's 0.1 -> 0.4 to imports
    assert gas["EU:BE,NL"] == pytest.approx(150.4)
    assert gas["GB"] == pytest.approx(500.0)  # Eurostat 2019
    assert out["domestic"]["gas"]["GB"] == pytest.approx(250.0)
    with pytest.raises(ValueError, match="no PatEx supply"):
        patex_supply_limits(tmp_path / "supply.csv", ["BE", "FR"],
                            tmp_path / "eurostat.csv", 2023, ["GB"])


def test_fallback_import_caps_eu_per_capita(tmp_path):
    supply = pd.DataFrame(
        {"gas": [100.0, 50.0, 30.0], "gas production": [0.5, 0.0, 0.0],
         "H2": [10.0, 0.0, 2.0]},
        index=["BE", "NL", "FR"],
    )
    supply.to_csv(tmp_path / "supply.csv")
    balances().to_csv(tmp_path / "eurostat.csv", index=False)
    pop = pd.DataFrame(
        {"TERRITORY_ID": ["BE", "NL", "FR", "UK", "NO"], "LEVEL_ID": 0,
         "2022": [10e6, 20e6, 30e6, 40e6, 5e6], "2023": [10e6, 20e6, 30e6, 60e6, None]}
    )
    pop.to_csv(tmp_path / "pop.csv", index=False)
    out = patex_supply_limits(tmp_path / "supply.csv", ["BE", "NL", "GB", "NO"],
                              tmp_path / "eurostat.csv", 2023, ["GB", "NO", "CH"],
                              tmp_path / "pop.csv")
    # EU indicator over every bundle country (FR too), gap included: 180.4 TWh / 60 M
    gas, h2 = out["import"]["gas"], out["import"]["H2"]
    assert gas["EU:BE,NL"] == pytest.approx(150.4)  # region = modelled PatEx countries
    assert gas["GB"] == pytest.approx(180.4 / 60e6 * 60e6)
    assert gas["NO"] == pytest.approx(180.4 / 60e6 * 5e6)  # NO: latest year with data
    assert h2["GB"] == pytest.approx(12.0)
    assert out["domestic"]["gas"]["NO"] == pytest.approx(1200.0)  # Eurostat, unchanged


def network():
    """BE (EU) and GB gas nodes, an LNG entry in each, a pipeline GB -> BE, an oil
    import on an EU-wide bus; expensive domestic gas in BE."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2030-01-01", periods=2, freq="h"))
    for ct in ("BE", "GB"):
        n.add("Bus", f"{ct}0 0", country=ct, carrier="AC")
        n.add("Bus", f"{ct}0 0 gas", location=f"{ct}0 0", carrier="gas")
        n.add("Generator", f"{ct}0 0 gas", bus=f"{ct}0 0 gas", carrier="gas",
              p_nom=1e3, marginal_cost=1.0)
    n.add("Generator", "BE0 0 gas production", bus="BE0 0 gas", carrier="gas production",
          p_nom=1e3, marginal_cost=100.0)
    n.add("Link", "pipe GB-BE", bus0="GB0 0 gas", bus1="BE0 0 gas", carrier="gas pipeline",
          p_nom=1e3, efficiency=1.0)
    n.add("Load", "BE gas demand", bus="BE0 0 gas", p_set=100.0)
    n.add("Bus", "EU oil primary", location="EU", carrier="oil primary")
    n.add("Generator", "EU oil primary", bus="EU oil primary", carrier="oil primary",
          p_nom=1e3, marginal_cost=1.0)
    n.add("Load", "oil demand", bus="EU oil primary", p_set=10.0)
    return n


def test_regional_caps_count_pipeline_inflow_as_eu_import():
    n = network()
    nyears = 2 / 8760
    # caps in TWh/a: EU (BE) gas 30 MW x 8760 h, GB 1000 MW; oil: EU + GB summed
    limits = {"import": {"gas": {"EU:BE": 30 * 8760 / 1e6, "GB": 1e3 * 8760 / 1e6},
                         "oil": {"EU:BE": 0.05, "GB": 0.05}}}
    add_supply_limits(n, limits, nyears)
    glc = n.global_constraints
    # oil on one EU bus, not split: one summed cap
    assert set(glc.carrier_attribute) == {"gas|EU:BE", "gas|GB", "oil"}
    n.optimize(solver_name="highs", include_objective_constant=False,
               extra_functionality=lambda n, sns: add_supply_limits_per_fuel(n, sns))
    p = n.generators_t.p.sum()  # MWh over the two hours (caps are annual)
    flow = n.links_t.p0["pipe GB-BE"].sum()
    # BE's LNG + GB pipeline gas into BE <= 60 MWh; the rest (140) is domestic
    assert p["BE0 0 gas"] + flow == pytest.approx(60.0)
    assert p["BE0 0 gas production"] == pytest.approx(140.0)


def pool_network():
    """Oil pool ("EU oil", no location) with the EU's import generator and an expensive
    domestic production; BE and GB draw from it through located demand links."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2030-01-01", periods=2, freq="h"))
    n.add("Bus", "EU oil", location="EU", carrier="oil")
    n.add("Generator", "EU oil", bus="EU oil", carrier="oil", p_nom=1e3, marginal_cost=10.0)
    n.add("Generator", "EU oil production", bus="EU oil", carrier="oil production",
          p_nom=1e3, marginal_cost=100.0)
    for ct, mw in (("BE", 50.0), ("GB", 25.0)):
        n.add("Bus", f"{ct}0 0", country=ct, carrier="AC")
        bus = f"{ct}0 0 land transport oil"
        n.add("Bus", bus, location=f"{ct}0 0", carrier="land transport oil")
        n.add("Link", bus, bus0="EU oil", bus1=bus, carrier="land transport oil",
              p_nom=1e3)
        n.add("Load", bus, bus=bus, p_set=mw)
    return n


def test_pool_flow_from_gb_counts_as_eu_import():
    n = pool_network()
    split_pooled_supply(n, ["GB", "NO"])  # NO not modelled: ignored
    assert "GB EU oil" in n.generators.index  # GB's own import, located in GB
    assert n.generators.at["GB EU oil", "location"] == "GB0 0"
    n.generators.loc["GB EU oil", "marginal_cost"] = 1.0  # GB imports are cheaper
    nyears = 2 / 8760
    twh = lambda mwh: mwh / 1e6 / nyears  # noqa: E731
    add_supply_limits(n, {"import": {"oil": {"EU:BE": twh(60), "GB": twh(1000)}}}, nyears)
    assert set(n.global_constraints.carrier_attribute) == {"oil|EU:BE", "oil|GB"}
    n.optimize(solver_name="highs", include_objective_constant=False,
               extra_functionality=lambda n, sns: add_supply_limits_per_fuel(n, sns))
    p = n.generators_t.p.sum()  # MWh over two hours; demand BE 100, GB 50
    # GB's oil reaching BE (net flow GB -> pool) + EU's own imports <= 60
    assert p["GB EU oil"] - 50 + p["EU oil"] == pytest.approx(60.0)
    assert p["EU oil production"] == pytest.approx(40.0)  # the rest, domestic


def test_split_stops_on_eu_wide_demand_only():
    n = pool_network()
    # regional industry demand (located through its node bus): accepted
    n.add("Bus", "BE0 0 coal for industry", location="BE0 0", carrier="coal for industry")
    n.add("Link", "BE0 0 coal for industry", bus0="EU oil", bus1="BE0 0 coal for industry",
          carrier="coal for industry", p_nom=1.0)
    split_pooled_supply(n, ["GB"])
    # EU-wide industry demand: cannot be attributed, stop
    m = pool_network()
    m.add("Bus", "EU coal for industry", location="EU", carrier="coal for industry")
    m.add("Link", "EU coal for industry", bus0="EU oil", bus1="EU coal for industry",
          carrier="coal for industry", p_nom=1.0)
    with pytest.raises(ValueError, match="cannot be attributed"):
        split_pooled_supply(m, ["GB"])


def test_tie_break_each_side_imports_for_itself():
    """Equal prices: without the tie-break the solver may feed GB through the EU's
    imports; with it, GB imports its own oil and the EU its own (no cap binding)."""
    n = pool_network()
    split_pooled_supply(n, ["GB"])
    n.config = {"import_limits": {"transit_penalty": 0.01}}
    nyears = 2 / 8760
    twh = lambda mwh: mwh / 1e6 / nyears  # noqa: E731
    add_supply_limits(n, {"import": {"oil": {"EU:BE": twh(1000), "GB": twh(1000)}}}, nyears)
    n.optimize(solver_name="highs", include_objective_constant=False,
               extra_functionality=lambda n, sns: add_supply_limits_per_fuel(n, sns))
    p = n.generators_t.p.sum()
    assert p["GB EU oil"] == pytest.approx(50.0)  # GB's demand, its own import
    assert p["EU oil"] == pytest.approx(100.0)  # BE's demand, the EU's import


def test_tie_break_on_boundary_pipelines_only():
    from scripts.prepare_sector_network import add_boundary_tie_break

    n = network()  # BE (EU) and GB gas nodes, pipeline GB -> BE
    n.add("Bus", "NL0 0", country="NL", carrier="AC")
    n.add("Bus", "NL0 0 gas", location="NL0 0", carrier="gas")
    n.add("Link", "pipe NL-BE", bus0="NL0 0 gas", bus1="BE0 0 gas", carrier="gas pipeline")
    add_boundary_tie_break(n, ["GB", "NO"], 0.01)
    assert n.links.at["pipe GB-BE", "marginal_cost"] == pytest.approx(0.01)
    assert n.links.at["pipe NL-BE", "marginal_cost"] == 0.0  # inside the EU
