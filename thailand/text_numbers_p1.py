"""
Numbers cited in the text of P1 (and Chapter 4 of the thesis) that are not in a table, from the solved networks and
the summaries of analyze_thailand.py. Prints them grouped by manuscript section, so that the text can be checked.

Usage (from the model root, pypsa-earth environment):
    python thailand/text_numbers_p1.py
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/TH2037_base/scenarios"
logging.disable(logging.WARNING)
LOCAL = pd.Timedelta(hours=7)
S = pd.read_csv(RES / "summary.csv", index_col=0)
SW = pd.read_csv(RES / "sweep_summary.csv", index_col=0)
W = pd.read_csv(RES / "weather_years_summary.csv", index_col=0)
C = pd.read_csv(RES / "pdp_ceiling.csv", index_col=0)


def net(name, run="TH2037_base"):
    return pypsa.Network(ROOT / f"results/{run}/scenarios/{name}.nc")


def gen_by(n, carrier):
    g = n.generators.index[n.generators.carrier == carrier]
    return n.generators_t.p[g].mul(n.snapshot_weightings.generators, axis=0).sum(axis=1)


def p(label, value, fmt=".1f"):
    print(f"  {label}: {value:{fmt}}")


def adv(a, b):
    return 100 * (1 - S.at["total_cost_bnEUR", b] / S.at["total_cost_bnEUR", a])


if __name__ == "__main__":
    nets = {c: net(c) for c in ["PDP", "LC_CAP", "LC"]}
    demand = S.at["demand_TWh", "PDP"]

    print("RQ1 ceiling and dispatch")
    p("ceiling TWh", C.at["TOTAL", "TWh"]), p("ceiling %", C.at["TOTAL", "share_pct"]), p("ceiling excl imports %", C.at["TOTAL excl. imports", "share_pct"])
    p("PDP RE %", S.at["RE_share_pct", "PDP"]), p("PDP RE excl %", S.at["RE_share_excl_imports_pct", "PDP"])
    for gw in [45, 60, 75]:
        p(f"sweep RE at {gw} GW", SW.at["RE_share_pct", f"PDP_solar{gw}"])
    s = SW.loc["RE_share_pct"].values
    gws = [30.3, 45, 60, 75, 90, 105, 120]
    p("solar for 51% (interpolated, GW)", float(np.interp(51, s[: np.argmax(s) + 1], gws[: np.argmax(s) + 1])))
    p("sweep solar built at 120 limit", SW.at["solar_GW", "PDP_solar120"])
    p("sweep RE excl at 120", SW.at["RE_share_excl_imports_pct", "PDP_solar120"])
    p("sweep cost 30.3 -> 120", SW.at["total_cost_bnEUR", "PDP_solar30.3"], ".2f"), p("  to", SW.at["total_cost_bnEUR", "PDP_solar120"], ".2f")
    re_pdp = S.at["RE_share_pct", "PDP"] * demand / 100
    gap = C.at["TOTAL", "TWh"] - re_pdp
    p("gap ceiling - PDP RE (TWh)", gap)
    p("  imports gap", C.at["imports", "TWh"] - S.at["imports_TWh", "PDP"])
    p("  import CF %", 100 * S.at["imports_TWh", "PDP"] / C.at["imports", "TWh"] * 60)
    bio_pdp = gen_by(nets["PDP"], "biomass").sum() / 1e6
    p("  biomass gap", C.at["biomass", "TWh"] - bio_pdp)
    p("  remainder", gap - (C.at["imports", "TWh"] - S.at["imports_TWh", "PDP"]) - (C.at["biomass", "TWh"] - bio_pdp))
    p("PDP_MT RE %", S.at["RE_share_pct", "PDP_MT"])

    print("RQ2 cases")
    for c in ["LC_CAP", "LC"]:
        p(f"{c} solar GW", S.at["solar_GW", c]), p(f"{c} wind GW", S.at["wind_GW", c]), p(f"{c} battery GW", S.at["battery_GW", c])
        p(f"{c} battery GWh", S.at["battery_GWh", c]), p(f"{c} RE %", S.at["RE_share_pct", c])
        p(f"{c} cost saving bn", S.at["total_cost_bnEUR", "PDP"] - S.at["total_cost_bnEUR", c], ".2f"), p(f"{c} cost saving %", adv("PDP", c))
        p(f"{c} CO2 cut Mt", S.at["CO2_Mt", "PDP"] - S.at["CO2_Mt", c]), p(f"{c} CO2 cut %", 100 * (1 - S.at["CO2_Mt", c] / S.at["CO2_Mt", "PDP"]))
        p(f"{c} gas fuel cut %", 100 * (1 - S.at["gas_fuel_TWhth", c] / S.at["gas_fuel_TWhth", "PDP"]))
        p(f"{c} capex", S.at["capex_bnEUR", c]), p(f"{c} opex", S.at["opex_bnEUR", c])
    p("PDP capex", S.at["capex_bnEUR", "PDP"]), p("PDP opex", S.at["opex_bnEUR", "PDP"])
    p("capture of cost saving %", 100 * (S.at["total_cost_bnEUR", "PDP"] - S.at["total_cost_bnEUR", "LC_CAP"]) / (S.at["total_cost_bnEUR", "PDP"] - S.at["total_cost_bnEUR", "LC"]))
    p("capture of CO2 cut %", 100 * (S.at["CO2_Mt", "PDP"] - S.at["CO2_Mt", "LC_CAP"]) / (S.at["CO2_Mt", "PDP"] - S.at["CO2_Mt", "LC"]))
    for c in ["PDP", "LC_CAP"]:
        p(f"{c} gas share %", S.at["gas_share_pct", c]), p(f"{c} OCGT GW", S.at["OCGT_GW", c]), p(f"{c} imports TWh", S.at["imports_TWh", c])
    cl = lambda c: S.at["coal_TWh", c] + S.at["lignite_TWh", c]
    p("coal+lignite decline %", 100 * (1 - cl("LC_CAP") / cl("PDP")))
    p("LC_CAP curtailment %", S.at["VRE_curtailment_pct", "LC_CAP"], ".2f")

    print("Spatial and operation")
    for c, n in nets.items():
        g = n.generators
        lines = n.lines
        p(f"{c} line reinforcement GW", (lines.s_nom_opt - lines.s_nom).clip(lower=0).sum() / 1e3, ".2f")
    n = nets["LC_CAP"]
    w = n.snapshot_weightings.generators
    vre = n.generators.index[n.generators.carrier.isin(["solar", "onwind"])]
    avail = n.get_switchable_as_dense("Generator", "p_max_pu")[vre] * n.generators.p_nom_opt[vre]
    curt = (avail - n.generators_t.p[vre]).clip(lower=0).sum(axis=1).mul(w)
    loc = curt.set_axis(curt.index + LOCAL)
    p("LC_CAP curtailment TWh", curt.sum() / 1e6, ".2f")
    p("  share Oct-Feb %", 100 * loc[loc.index.month.isin([10, 11, 12, 1, 2])].sum() / loc.sum())
    p("  December TWh", loc[loc.index.month == 12].sum() / 1e6, ".2f")
    for c, n in nets.items():
        w = n.snapshot_weightings.generators
        dis = n.links.index[n.links.carrier == "battery discharger"]
        out = n.links_t.p1[dis].mul(-1).mul(w, axis=0).sum(axis=1)
        e = n.stores.e_nom_opt[n.stores.carrier == "battery"].sum()
        p(f"{c} battery output TWh", out.sum() / 1e6), p(f"{c} battery cycles", out.sum() / e, ".0f")
        lo = out.set_axis(out.index + LOCAL)
        p(f"{c} battery share 17-23h %", 100 * lo[(lo.index.hour >= 17) & (lo.index.hour < 23)].sum() / lo.sum(), ".0f")
        g = n.generators
        ex = g.index[(g.carrier == "CCGT") & ~g.index.str.contains("new")]
        p(f"{c} existing CCGT CF %", 100 * n.generators_t.p[ex].mul(w, axis=0).sum().sum() / (g.p_nom_opt[ex].sum() * w.sum()), ".0f")
        oc = g.index[g.index.str.endswith("OCGT new")]
        p(f"{c} new OCGT hours", (n.generators_t.p[oc].sum(axis=1) > 1).mul(w).sum(), ".0f")
        p(f"{c} new OCGT CF %", 100 * n.generators_t.p[oc].mul(w, axis=0).sum().sum() / max(g.p_nom_opt[oc].sum() * w.sum(), 1), ".1f")
        load = n.loads_t.p_set.sum(axis=1)
        price = n.buses_t.marginal_price[n.buses.index[n.buses.carrier == "AC"]]
        dem = n.loads_t.p_set.T.groupby(n.loads.bus).sum().T.reindex(columns=price.columns).fillna(0)
        p(f"{c} demand-weighted price", (price * dem).sum().sum() / dem.sum().sum())
        zero = (price.max(axis=1) < 0.5)
        zl = zero.set_axis(zero.index + LOCAL)
        p(f"{c} zero-price hours", int(zero.sum()), "d")
        if zero.sum():
            print("    hours of day:", sorted(set(zl[zl].index.hour)), "months:", zl[zl].groupby(zl[zl].index.month).size().to_dict())
    nh = net("LC_CAP_HD")
    g = nh.generators
    newccgt = g.index[(g.carrier == "CCGT") & g.p_nom_extendable]
    p("LC_CAP_HD CCGT above existing (GW)", (g.p_nom_opt[newccgt] - g.p_nom_min[newccgt]).sum() / 1e3, ".2f")
    p("LC_CAP CCGT above existing (GW)", (nets["LC_CAP"].generators.p_nom_opt[newccgt] - nets["LC_CAP"].generators.p_nom_min[newccgt]).sum() / 1e3, ".2f")

    print("Robustness")
    for sens in ["HG", "HSC", "HD", "MT"]:
        p(f"{sens} adv LC_CAP vs PDP %", adv(f"PDP_{sens}", f"LC_CAP_{sens}"))
        for c in ["PDP", "LC_CAP", "LC"]:
            print(f"    {c}_{sens}: RE {S.at['RE_share_pct', f'{c}_{sens}']:.1f}, solar {S.at['solar_GW', f'{c}_{sens}']:.1f}, wind {S.at['wind_GW', f'{c}_{sens}']:.1f},"
                  f" bat {S.at['battery_GWh', f'{c}_{sens}']:.1f} GWh, biomass {S.at['biomass_GW', f'{c}_{sens}']:.2f}, imports {S.at['imports_TWh', f'{c}_{sens}']:.1f},"
                  f" CO2 {S.at['CO2_Mt', f'{c}_{sens}']:.1f}, OCGT {S.at['OCGT_GW', f'{c}_{sens}']:.1f}, cost {S.at['total_cost_bnEUR', f'{c}_{sens}']:.2f}")
    p("HSC CO2 lower % (LC_CAP vs PDP)", 100 * (1 - S.at["CO2_Mt", "LC_CAP_HSC"] / S.at["CO2_Mt", "PDP_HSC"]))
    p("MT capture %", 100 * (S.at["total_cost_bnEUR", "PDP_MT"] - S.at["total_cost_bnEUR", "LC_CAP_MT"]) / (S.at["total_cost_bnEUR", "PDP_MT"] - S.at["total_cost_bnEUR", "LC_MT"]))
    p("HG cost increase LC_CAP bn", S.at["total_cost_bnEUR", "LC_CAP_HG"] - S.at["total_cost_bnEUR", "LC_CAP"], ".2f")
    p("HG cost increase PDP bn", S.at["total_cost_bnEUR", "PDP_HG"] - S.at["total_cost_bnEUR", "PDP"], ".2f")
    p("capex increase LC_CAP vs PDP bn", S.at["capex_bnEUR", "LC_CAP"] - S.at["capex_bnEUR", "PDP"], ".2f")
    p("battery GW above PDP (LC_CAP)", S.at["battery_GW", "LC_CAP"] - S.at["battery_GW", "PDP"], ".2f")
    p("PDP battery GW", S.at["battery_GW", "PDP"], ".2f")

    print("Weather years")
    for y in ["2022", "2020", "2025"]:
        for c in ["PDP", "LC_CAP", "LC"]:
            k = f"{c} {y}"
            print(f"    {k}: RE {W.at['RE_share_pct', k]:.1f}, hydro {W.at['domestic_hydro_TWh', k]:.1f}, imports {W.at['imports_TWh', k]:.1f}, bat {W.at['battery_GWh', k]:.1f}, cost {W.at['total_cost_bnEUR', k]:.3f}")
        a = 100 * (1 - W.at["total_cost_bnEUR", f"LC_CAP {y}"] / W.at["total_cost_bnEUR", f"PDP {y}"])
        cap = 100 * (W.at["total_cost_bnEUR", f"PDP {y}"] - W.at["total_cost_bnEUR", f"LC_CAP {y}"]) / (W.at["total_cost_bnEUR", f"PDP {y}"] - W.at["total_cost_bnEUR", f"LC {y}"])
        print(f"    {y}: LC_CAP advantage {a:.1f}%, capture {cap:.0f}%")
