# SPDX-License-Identifier: MIT
"""PyPSA-Eur-CANEU network-cost changes (2026-11-10): reversed DC twins unpriced,
industry at transmission level, rooftop PV hosting cost."""

import pandas as pd
import pypsa
import pytest

from scripts.add_electricity import set_transmission_costs
from scripts.prepare_network import set_transmission_limit
from scripts.prepare_sector_network import refine_distribution_grid


def _costs():
    return pd.DataFrame(
        {"capital_cost": [70.0, 50.0, 300.0, 52_000.0, 63_000.0],
         "investment": [680.0, 550.0, 2950.0, 580_000.0, 620_000.0]},
        index=["HVAC overhead", "HVDC overhead", "HVDC submarine", "HVDC inverter pair",
               "electricity distribution grid"],
    )


def _dc_network():
    n = pypsa.Network()
    n.add("Bus", ["A", "B"], carrier="AC")
    n.add("Link", "AB", bus0="A", bus1="B", carrier="DC", length=100.0, p_nom=1000.0,
          underwater_fraction=0.0)
    n.add("Link", "AB-reversed", bus0="B", bus1="A", carrier="DC", length=0.0, p_nom=1000.0,
          underwater_fraction=0.0, capital_cost=0.0)
    n.links["reversed"] = [False, True]
    return n


def test_reversed_dc_twin_gets_no_converter_cost():
    n = _dc_network()
    set_transmission_costs(n, _costs(), skip_reversed=True)
    assert n.links.at["AB", "capital_cost"] == pytest.approx(100 * 50 + 52_000)
    assert n.links.at["AB-reversed", "capital_cost"] == 0.0
    # upstream behaviour unchanged without the flag (the twin pays a converter pair)
    n = _dc_network()
    set_transmission_costs(n, _costs())
    assert n.links.at["AB-reversed", "capital_cost"] == pytest.approx(52_000)


def test_reversed_twin_stays_extendable_and_out_of_the_reference():
    n = _dc_network()
    set_transmission_limit(n, "v", "1.5", _costs(), skip_reversed=True)
    assert n.links.p_nom_extendable.all()  # the sync constraint needs both legs
    glc = n.global_constraints.iloc[0]
    assert glc.constant == pytest.approx(1.5 * 1000 * 100)  # forward leg only


def _lv_network():
    n = pypsa.Network()
    n.set_snapshots(range(2))
    for node, ct in (("BE0", "BE"), ("IE0", "IE")):
        n.add("Bus", node, carrier="AC", country=ct)
        n.add("Bus", f"{node} low voltage", carrier="low voltage", location=node)
        n.add("Load", f"{node} industry electricity", bus=f"{node} low voltage",
              carrier="industry electricity", p_set=100.0)
        n.add("Generator", f"{node} solar rooftop", bus=f"{node} low voltage",
              carrier="solar rooftop", p_nom_extendable=True, capital_cost=48_000.0)
    return n


def test_industry_share_moves_to_transmission_bus():
    n = _lv_network()
    refine_distribution_grid(n, _costs(), {"industry_hv_share": {"BE": 0.64, "default": 0.58}})
    assert n.loads.at["BE0 industry electricity", "p_set"] == pytest.approx(36.0)
    assert n.loads.at["BE0 industry electricity HV", "p_set"] == pytest.approx(64.0)
    assert n.loads.at["BE0 industry electricity HV", "bus"] == "BE0"
    assert n.loads.at["IE0 industry electricity HV", "p_set"] == pytest.approx(58.0)
    # energy is conserved
    assert n.loads.p_set.sum() == pytest.approx(200.0)


def test_pv_hosting_cost_at_the_distribution_grid_annuity():
    n = _lv_network()
    refine_distribution_grid(n, _costs(), {"pv_hosting_cost": 120.0})
    factor = 63_000.0 / 620_000.0
    assert n.generators.at["BE0 solar rooftop", "capital_cost"] == pytest.approx(
        48_000.0 + 120_000.0 * factor)


COSTS_2030 = "data/costs/archive/v0.15.0/costs_2030.csv"


@pytest.mark.skipif(not __import__("os").path.exists(COSTS_2030),
                    reason="technology-data cost file not downloaded")
def test_network_discount_rate_reaches_the_capital_cost():
    """One central rate for the network assets (``network_costs.discount_rate``); the
    capital cost, not just the column, must change (2026-11-10: a ``costs.overwrites:
    discount rate`` entry was silently ignored)."""
    from scripts._distribution_grid_config import NETWORK_TECHNOLOGIES
    from scripts.process_cost_data import prepare_costs

    import yaml

    config = yaml.safe_load(open("config/config.default.yaml"))["costs"]
    raw = pd.read_csv(COSTS_2030, index_col=["technology", "parameter"])
    custom = config["custom_cost_fn"]
    base = prepare_costs(raw.copy(), config, "2030", {"battery": 6, "H2": 168}, 1.0, custom)
    out = prepare_costs(raw.copy(), config, "2030", {"battery": 6, "H2": 168}, 1.0, custom,
                        network_costs={"discount_rate": 0.04,
                                       "technologies": NETWORK_TECHNOLOGIES})

    def annuity(r, n):
        return r / (1 - (1 + r) ** -n)

    for tech in ("HVDC inverter pair", "offwind-dc-station", "electricity distribution grid"):
        row = out.loc[tech]
        assert row["discount rate"] == pytest.approx(0.04)
        expected = (annuity(0.04, row["lifetime"]) + row["FOM"] / 100) * row["investment"]
        assert row["capital_cost"] == pytest.approx(expected)
        assert row["capital_cost"] < base.at[tech, "capital_cost"]
    # generation keeps its own rate
    assert out.at["onwind", "capital_cost"] == pytest.approx(base.at["onwind", "capital_cost"])
