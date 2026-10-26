"""
Solve Thailand scenarios on a network prepared by the PyPSA-Earth v0.10 workflow.

The prepared network (`networks/<run>/elec_s_6_ec_lcopt_CCL.nc`) lacks the contracted
hydropower imports from Lao PDR: v0.10 has no import carrier, and tagging Lao dams as Thai
hydro would rescale them to Thailand's national hydro statistics. This script adds them as
a generator and then calls PyPSA-Earth's own `prepare_network` / `solve_network`, so every
constraint (capacity limits, battery coupling) is the same as in the standard workflow.

Usage (from the repository root):
    python thailand/solve_thailand.py PDP LC CALIB2022 ...
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pypsa
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import solve_network as pe  # noqa: E402

# Lao hydropower available to Thailand. Contracts from data/thailand/custom_powerplants_TH_original.csv:
# 3,985 MW operating in 2022; 3,565 MW still contracted in 2037 (Nam Theun 2 ends 2035), plus 3,500 MW
# of additional imports planned in the draft PDP2024 (BNEF 2025). Availability 60%: Ember 2022 net imports
# of 33.4 TWh minus ~10.5 TWh from Hongsa imply ~23 TWh from ~4 GW of Lao hydro. Price ~2.1 THB/kWh
# (between ~35 USD/MWh and the 2.32 THB/kWh Nam Ngiep 1 PPA).
LAO_HYDRO_CF = 0.60

# Weather years (Ember): domestic hydro 2020 4.54 / 2022 6.60 / 2025 7.62 TWh; net imports 26.9 / 33.4 / 36.9 TWh,
# i.e. Lao hydro ~16.4 / 22.9 / 26.4 TWh after ~10.5 TWh from Hongsa. Hydro inflow keeps each year's seasonal shape
# but is scaled relative to the 2022-calibrated base; Lao import availability is scaled by the same logic.
WEATHER = {
    2020: dict(hydro_ratio=4.54 / 6.60, lao_cf=0.60 * 16.4 / 22.9),
    2025: dict(hydro_ratio=7.62 / 6.60, lao_cf=0.60 * 26.4 / 22.9),
}
LAO_HYDRO_PRICE = 55.0  # EUR/MWh
LAO_HYDRO_XY = (104.0, 17.0)  # connect at the Thai bus nearest to the north-eastern border

BASE_2037 = dict(run="TH2037_base", horizon="2037", cost_year="2035", lao_mw=3565.0 + 3500.0, ocgt=True)
SCENARIOS = {
    "PDP": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_PDP2024_2037.csv"),
    "LC": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_2037.csv"),
    # realistic expansion: solar <= plan + 32 GW (Ember, Sep 2025 cost-optimal pathway), onshore wind <= 13 GW
    # (national technical potential); all other limits as in the plan
    "LC_CAP": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_CAP_2037.csv"),
    # sensitivities: gas price +50% (LNG exposure), solar capital cost +50%, demand at the draft-PDP peak
    "PDP_HG": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_PDP2024_2037.csv", gas_factor=1.5),
    "LC_HG": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_2037.csv", gas_factor=1.5),
    "LC_HSC": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_2037.csv", solar_cost_factor=1.5),
    "PDP_HSC": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_PDP2024_2037.csv", solar_cost_factor=1.5),
    "LC_CAP_HG": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_CAP_2037.csv", gas_factor=1.5),
    # must-take Lao imports (take-or-pay contracts): flat output at the contracted availability
    "PDP_MT": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_PDP2024_2037.csv", lao_must_take=True),
    "LC_CAP_MT": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_CAP_2037.csv", lao_must_take=True),
    "LC_MT": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_2037.csv", lao_must_take=True),
    "LC_CAP_HSC": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_CAP_2037.csv", solar_cost_factor=1.5),
    "LC_CAP_HD": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_CAP_2037.csv", load_factor=56133 / 49120),
    "PDP_HD": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_PDP2024_2037.csv", load_factor=56133 / 49120),
    "LC_HD": dict(BASE_2037, limits="data/thailand/agg_p_nom_minmax_LC_2037.csv", load_factor=56133 / 49120),
    # 2022 calibration: existing fleet only, compared with Ember 2022 (overlay config_TH2022_calib.yaml)
    "CALIB2022": dict(run="TH2022_calib", horizon="2022", cost_year="2025", lao_mw=3985.0, ocgt=False, fix_vre=True,
                      limits="data/thailand/agg_p_nom_minmax_2022_existing.csv", overlay="config_TH2022_calib.yaml"),
}


def load_config(overlay=None):
    cfg = {}
    for f in ["config.default.yaml", "configs/solving.default.yaml", "config.yaml", overlay]:
        if f:
            _merge(cfg, yaml.safe_load(open(ROOT / f)))
    return cfg


def _merge(base, new):
    for k, v in (new or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v


def add_lao_hydro_imports(n, mw, cf=LAO_HYDRO_CF, must_take=False):
    ac = n.buses.query("carrier == 'AC'")
    bus = ((ac.x - LAO_HYDRO_XY[0]) ** 2 + (ac.y - LAO_HYDRO_XY[1]) ** 2).idxmin()
    if "imports" not in n.carriers.index:
        n.add("Carrier", "imports", co2_emissions=0.0)
    n.add(
        "Generator",
        f"{bus} Lao hydro imports",
        bus=bus,
        carrier="imports",
        p_nom=mw,
        p_max_pu=cf,
        p_min_pu=cf if must_take else 0.0,  # must-take: contracted energy taken every hour
        marginal_cost=LAO_HYDRO_PRICE,
    )
    return bus


def add_ocgt(n, run, cost_year):
    """The prepared network has no new-build peaking option; allow OCGT at every AC bus,
    with costs from the same processed technology-data file the workflow used."""
    c = pd.read_csv(ROOT / f"resources/{run}/costs_{cost_year}_elec.csv", index_col=0).loc["OCGT"]
    buses = n.buses.index[n.buses.carrier == "AC"]
    n.madd(
        "Generator",
        buses + " OCGT new",
        bus=buses,
        carrier="OCGT",
        p_nom_extendable=True,
        capital_cost=c.capital_cost,
        marginal_cost=c.marginal_cost,
        efficiency=c.efficiency,
    )
    if "OCGT" not in n.carriers.index:
        n.add("Carrier", "OCGT", co2_emissions=0.198)


def weather_year_scenarios():
    out = {}
    for y, w in WEATHER.items():
        for base in ["PDP", "LC_CAP", "LC"]:
            out[f"{base}_w{y}"] = dict(SCENARIOS[base], run=f"TH2037_w{y}", overlay=f"config_TH2037_w{y}.yaml",
                                       lao_cf=w["lao_cf"], hydro_ratio=w["hydro_ratio"])
    return out


def scale_hydro_inflow(n, ratio):
    """Scale reservoir inflow to ratio x the annual inflow of the 2022-calibrated base network."""
    ref = pypsa.Network(ROOT / "networks/TH2037_base/elec_s_6_ec_lcopt_CCL.nc")
    target = ref.storage_units_t.inflow.mul(ref.snapshot_weightings.generators, axis=0).sum().sum() * ratio
    inflow = n.storage_units_t.inflow
    n.storage_units_t.inflow = inflow * target / inflow.mul(n.snapshot_weightings.generators, axis=0).sum().sum()


def solar_limits_file(gw, run):
    """PDP limits with the solar maximum replaced (solar sweep)."""
    src = ROOT / SCENARIOS["PDP"]["limits"]
    lines = [
        f"TH,solar,{l.split(',')[2]},{gw * 1e3:.1f}" if l.startswith("TH,solar,") else l
        for l in open(src).read().splitlines()
    ]
    out = ROOT / f"results/{run}/limits/agg_p_nom_minmax_PDP_solar{gw:g}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return str(out.relative_to(ROOT))


def apply_sensitivities(n, run, cost_year, gas_factor, solar_cost_factor, load_factor):
    if gas_factor != 1.0:  # scale the fuel part of gas plants' marginal cost
        fuel = pd.read_csv(ROOT / f"resources/{run}/costs_{cost_year}_elec.csv", index_col=0).loc["gas", "fuel"]
        gas = n.generators.index[n.generators.carrier.isin(["CCGT", "OCGT"])]
        n.generators.loc[gas, "marginal_cost"] += (gas_factor - 1) * fuel / n.generators.loc[gas, "efficiency"]
    if solar_cost_factor != 1.0:
        n.generators.loc[n.generators.carrier == "solar", "capital_cost"] *= solar_cost_factor
    if load_factor != 1.0:
        n.loads_t.p_set *= load_factor


def solve(name, limits, run, horizon, cost_year, lao_mw, ocgt, overlay=None, fix_vre=False,
          gas_factor=1.0, solar_cost_factor=1.0, load_factor=1.0, lao_cf=LAO_HYDRO_CF, hydro_ratio=None, lao_must_take=False):
    config = load_config(overlay)
    config["electricity"]["agg_p_nom_limits"]["file"] = limits
    opts = ["CCL"]

    # PyPSA-Earth's solve functions read these module-level globals set by Snakemake
    pe.snakemake = SimpleNamespace(
        config=config,
        params=SimpleNamespace(policy_config=config["policy_config"]),
        input=SimpleNamespace(agg_p_nom_minmax=str(ROOT / limits)),
        wildcards=SimpleNamespace(planning_horizons=horizon, opts="-".join(opts)),
    )
    pe.opts = opts
    pe.n_ref = None

    n = pypsa.Network(ROOT / f"networks/{run}/elec_s_6_ec_lcopt_CCL.nc")

    # as in solve_network.py __main__: lines added by augmented_line_connection get a minimum size
    aug = config["augmented_line_connection"]
    if aug.get("add_to_snakefile") and not n.lines.empty:
        n.lines.loc[n.lines.index.str.contains("new"), "s_nom_min"] = aug.get("min_expansion")

    if fix_vre:  # calibration: existing solar/wind at their network locations, no re-optimised siting
        vre = n.generators.index[n.generators.carrier.isin(["solar", "onwind", "offwind-ac", "offwind-dc"])]
        n.generators.loc[vre, "p_nom_extendable"] = False
    bus = add_lao_hydro_imports(n, lao_mw, lao_cf, lao_must_take)
    if hydro_ratio is not None:
        scale_hydro_inflow(n, hydro_ratio)
    if ocgt:
        add_ocgt(n, run, cost_year)  # before scaling, so new OCGT also gets the gas sensitivity
    apply_sensitivities(n, run, cost_year, gas_factor, solar_cost_factor, load_factor)
    print(f"{name}: Lao hydro imports ({lao_mw:.0f} MW) at bus {bus}; new OCGT allowed: {ocgt}")

    n = pe.prepare_network(n, config["solving"]["options"], config=config["solving"]["options"])
    n = pe.solve_network(n, config=config, solving=config["solving"])
    out = ROOT / f"results/{run}/scenarios"
    out.mkdir(parents=True, exist_ok=True)
    n.export_to_netcdf(out / f"{name}.nc")
    print(f"{name}: objective {n.objective / 1e9:.3f} bn EUR")


SWEEP_SOLAR_GW = [30.3, 45, 60, 75, 90, 105, 120]

if __name__ == "__main__":
    for name in sys.argv[1:] or ["PDP", "LC"]:
        if name == "sweep":  # PDP with the solar maximum raised step by step (wind stays at the plan level)
            for gw in SWEEP_SOLAR_GW:
                solve(f"PDP_solar{gw:g}", **dict(SCENARIOS["PDP"], limits=solar_limits_file(gw, "TH2037_base")))
        else:
            solve(name, **{**SCENARIOS, **weather_year_scenarios()}[name])
