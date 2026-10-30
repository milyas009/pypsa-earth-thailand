"""
Key indicators for the Thailand scenarios solved by solve_thailand.py.

Usage (from the repository root):
    python thailand/analyze_thailand.py PDP LC ...            # scenarios of TH2037_base
    python thailand/analyze_thailand.py --weather PDP LC_CAP LC  # same scenarios across weather years
Writes results/<run>/scenarios/summary.csv (or weather_years_summary.csv).
"""

import sys
from pathlib import Path

import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/TH2037_base/scenarios"

VRE = ["solar", "onwind", "offwind-ac", "offwind-dc"]
RE = VRE + ["ror", "biomass", "geothermal", "imports"]  # + reservoir hydro (storage unit)


def metrics(n):
    w = n.snapshot_weightings.generators
    g, su, lk = n.generators, n.storage_units, n.links
    gen = n.generators_t.p.mul(w, axis=0).sum().groupby(g.carrier).sum()
    cap = g.p_nom_opt.groupby(g.carrier).sum()
    hydro = n.storage_units_t.p_dispatch[su.index[su.carrier == "hydro"]].mul(w, axis=0).sum().sum()
    demand = n.loads_t.p_set.mul(w, axis=0).sum().sum()

    re = gen.reindex(RE).fillna(0).sum() + hydro
    vre_i = g.index[g.carrier.isin(VRE)]
    avail = (n.get_switchable_as_dense("Generator", "p_max_pu")[vre_i] * g.p_nom_opt[vre_i]).mul(w, axis=0).sum().sum()
    co2 = (n.generators_t.p.mul(w, axis=0).sum() / g.efficiency * g.carrier.map(n.carriers.co2_emissions).fillna(0)).sum()
    gas = g.index[g.carrier.isin(["CCGT", "OCGT"])]
    capex, opex = n.statistics.capex().sum(), n.statistics.opex().sum()

    dis = lk.index[lk.carrier == "battery discharger"]
    bat_store = n.stores.index[n.stores.carrier == "battery"]
    lines = n.lines

    return {
        "demand_TWh": demand / 1e6,
        "peak_GW": n.loads_t.p_set.sum(axis=1).max() / 1e3,
        "RE_share_pct": 100 * re / demand,
        "RE_share_excl_imports_pct": 100 * (re - gen.get("imports", 0)) / demand,
        "VRE_share_pct": 100 * gen.reindex(VRE).fillna(0).sum() / demand,
        "VRE_curtailment_pct": 100 * (1 - gen.reindex(VRE).fillna(0).sum() / avail),
        "total_cost_bnEUR": (capex + opex) / 1e9,
        "capex_bnEUR": capex / 1e9,
        "opex_bnEUR": opex / 1e9,
        "avg_cost_EURperMWh": (capex + opex) / demand,
        "CO2_Mt": co2 / 1e6,
        "gas_share_pct": 100 * gen.reindex(["CCGT", "OCGT"]).fillna(0).sum() / demand,
        "gas_fuel_TWhth": (n.generators_t.p[gas].mul(w, axis=0).sum() / g.efficiency[gas]).sum() / 1e6,
        "solar_GW": cap.get("solar", 0) / 1e3,
        "wind_GW": cap.reindex(VRE[1:]).fillna(0).sum() / 1e3,
        "CCGT_GW": cap.get("CCGT", 0) / 1e3,
        "OCGT_GW": cap.get("OCGT", 0) / 1e3,
        "biomass_GW": cap.get("biomass", 0) / 1e3,
        "lignite_TWh": gen.get("lignite", 0) / 1e6,
        "coal_TWh": gen.get("coal", 0) / 1e6,
        "imports_TWh": gen.get("imports", 0) / 1e6,
        "domestic_hydro_TWh": (hydro + gen.get("ror", 0)) / 1e6,
        "battery_GW": lk.p_nom_opt[dis].sum() / 1e3,
        "battery_GWh": n.stores.e_nom_opt[bat_store].sum() / 1e3,
        "H2_store_GWh": n.stores.e_nom_opt[n.stores.carrier == "H2"].sum() / 1e3,
        "line_expansion_TWkm": ((lines.s_nom_opt - lines.s_nom) * lines.length).sum() / 1e6,
    }


def weather_comparison(bases):
    runs = {"2022": ("TH2037_base", ""), "2020": ("TH2037_w2020", "_w2020"), "2025": ("TH2037_w2025", "_w2025")}
    cols = {}
    for year, (run, suffix) in runs.items():
        for b in bases:
            f = ROOT / f"results/{run}/scenarios/{b}{suffix}.nc"
            if f.exists():
                cols[f"{b} {year}"] = metrics(pypsa.Network(f))
    df = pd.DataFrame(cols)
    df.round(3).to_csv(RES / "weather_years_summary.csv")
    pd.set_option("display.width", 250)
    print(df.round(2).to_string())


if __name__ == "__main__":
    if sys.argv[1:2] == ["--weather"]:
        weather_comparison(sys.argv[2:] or ["PDP", "LC_CAP", "LC"])
        sys.exit()
    names = sys.argv[1:] or sorted(p.stem for p in RES.glob("*.nc"))
    df = pd.DataFrame({s: metrics(pypsa.Network(RES / f"{s}.nc")) for s in names})
    out = "sweep_summary.csv" if all(x.startswith("PDP_solar") for x in names) else "summary.csv"
    df.round(3).to_csv(RES / out)
    pd.set_option("display.width", 200)
    print(df.round(2).to_string())


def capacity_ceiling(run="TH2037_base", lao_mw=3565.0 + 3500.0, lao_cf=0.60):
    """RQ1: renewable output if every renewable technology sits at its PDP capacity limit, at the best-resource
    node, never curtailed (imports at their contracted capacity and availability, reservoir hydro = annual inflow)."""
    n = pypsa.Network(ROOT / f"networks/{run}/elec_s_6_ec_lcopt_CCL.nc")
    w = n.snapshot_weightings.generators
    lim = pd.read_csv(ROOT / "data/thailand/agg_p_nom_minmax_PDP2024_2037.csv", index_col=[0, 1], header=[0, 1])["2037"]["max"].droplevel(0)
    pmax = n.get_switchable_as_dense("Generator", "p_max_pu").clip(upper=1.0)  # as in the solve (cap_availability)
    g = n.generators
    rows = {}
    for c in ["solar", "onwind", "offwind-ac", "offwind-dc", "biomass", "ror", "geothermal"]:
        idx = g.index[g.carrier == c]
        if idx.empty:
            continue
        cap = lim.get(c, g.loc[idx, "p_nom"].sum())
        best_cf = (pmax[idx].mul(w, axis=0).sum() / w.sum()).max()
        rows[c] = {"cap_GW": cap / 1e3, "best_CF": best_cf, "TWh": cap * best_cf * w.sum() / 1e6}
    rows["imports"] = {"cap_GW": lao_mw / 1e3, "best_CF": lao_cf, "TWh": lao_mw * lao_cf * w.sum() / 1e6}
    hydro = n.storage_units.index[n.storage_units.carrier == "hydro"]
    rows["hydro (inflow)"] = {"cap_GW": n.storage_units.p_nom[hydro].sum() / 1e3, "best_CF": float("nan"),
                              "TWh": n.storage_units_t.inflow[hydro].mul(w, axis=0).sum().sum() / 1e6}
    df = pd.DataFrame(rows).T
    demand = n.loads_t.p_set.mul(w, axis=0).sum().sum() / 1e6
    df.loc["TOTAL", "TWh"] = df.TWh.sum()
    df.loc["TOTAL", "share_pct"] = 100 * df.loc["TOTAL", "TWh"] / demand
    df.loc["TOTAL excl. imports", "TWh"] = df.loc["TOTAL", "TWh"] - df.loc["imports", "TWh"]
    df.loc["TOTAL excl. imports", "share_pct"] = 100 * df.loc["TOTAL excl. imports", "TWh"] / demand
    df.round(3).to_csv(RES / "pdp_ceiling.csv")
    return df
