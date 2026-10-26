"""
Write the journal paper's LaTeX tables directly from result files (no hand-typed numbers).

Usage (from the repository root):
    python thailand/make_tables.py
Writes into $PAPER_DIR/tables/ (default: paper_outputs/).
"""

import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAPER = Path(os.environ.get("PAPER_DIR", ROOT / "paper_outputs"))  # folder of the LaTeX manuscript


def calibration_table():
    df = pd.read_csv(ROOT / "results/TH2022_calib/scenarios/calibration_vs_ember2022.csv", index_col=0)
    lines = [
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"Fuel & Model & Observed & \multicolumn{2}{c}{Difference} \\",
        r" & (TWh) & (TWh) & (TWh) & (\%) \\",
        r"\midrule",
    ]
    for name, r in df.iterrows():
        if name == "Total supply":
            lines.append(r"\midrule")
        lines.append(f"{name} & {r.iloc[0]:.1f} & {r.iloc[1]:.1f} & {r.iloc[2]:+.1f} & {r.iloc[3]:+.1f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "tables/tab_calibration.tex").write_text("\n".join(lines) + "\n")


def assumptions_table():
    import pypsa

    n = pypsa.Network(ROOT / "networks/TH2037_base/elec_s_6_ec_lcopt_CCL.nc")
    g = n.generators
    costs = pd.read_csv(ROOT / "resources/TH2037_base/costs_2035_elec.csv", index_col=0)
    lim = pd.read_csv(ROOT / "data/thailand/agg_p_nom_minmax_PDP2024_2037.csv", index_col=[0, 1], header=[0, 1])["2037"].droplevel(0)
    ex = g.groupby("carrier").p_nom.sum() / 1e3
    hydro_gw = n.storage_units[n.storage_units.carrier == "hydro"].p_nom.sum() / 1e3
    rows = [
        ("CCGT", costs.loc["CCGT", "investment"] / 1e3, g[g.carrier == "CCGT"].marginal_cost.mean(), f"{ex['CCGT']:.1f}--{lim.loc['CCGT', 'max'] / 1e3:.1f}"),
        ("OCGT (new)", costs.loc["OCGT", "investment"] / 1e3, costs.loc["OCGT", "marginal_cost"], "unlimited"),
        ("Coal (existing)", None, g[g.carrier == "coal"].marginal_cost.mean(), f"{ex['coal']:.1f} (fixed, 70\\% available)"),
        ("Lignite incl. Hongsa", None, g[g.carrier == "lignite"].marginal_cost.mean(), f"{ex['lignite']:.1f} (fixed, 70\\% available)"),
        ("Biomass", costs.loc["biomass", "investment"] / 1e3, g[g.carrier == "biomass"].marginal_cost.mean(), f"{ex['biomass']:.1f}--{lim.loc['biomass', 'max'] / 1e3:.1f} (85\\% available)"),
        ("Nuclear (SMR)", costs.loc["nuclear", "investment"] / 1e3, g[g.carrier == "nuclear"].marginal_cost.mean(), f"{lim.loc['nuclear', 'max'] / 1e3:.1f} (fixed)"),
        ("Solar PV", costs.loc["solar", "investment"] / 1e3, 0.0, "by case (Table 3)"),
        ("Onshore wind", costs.loc["onwind", "investment"] / 1e3, 0.0, "by case (Table 3)"),
        ("Battery storage", None, None, f"optimised; energy {costs.loc['battery storage', 'investment'] / 1e3:.0f} EUR/kWh, power {costs.loc['battery inverter', 'investment'] / 1e3:.0f} EUR/kW"),
        ("Reservoir hydro", None, 0.0, f"{hydro_gw:.1f} (fixed, 2,500 h storage)"),
        ("Lao hydropower imports", None, 55.0, "7.1 (fixed, 60\\% available)"),
    ]
    lines = [r"\begin{tabular}{@{}lrr>{\raggedright\arraybackslash}p{4.3cm}@{}}", r"\toprule",
             r"Technology & Investment & Marginal cost & Capacity (GW) \\",
             r" & (EUR/kW) & (EUR/MWh) & \\", r"\midrule"]
    for name, inv, mc, cap in rows:
        lines.append(f"{name} & {'--' if inv is None else f'{inv:,.0f}'} & {'--' if mc is None else f'{mc:.1f}'} & {cap} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "tables/tab_assumptions.tex").write_text("\n".join(lines) + "\n")


def results_table():
    s = pd.read_csv(ROOT / "results/TH2037_base/scenarios/summary.csv", index_col=0)
    cols = {"PDP": "PDP", "LC_CAP": "LC-CAP", "LC": "LC"}
    rows = [
        ("Total system cost (billion EUR/yr)", "total_cost_bnEUR", "{:.2f}"),
        ("Average system cost (EUR/MWh)", "avg_cost_EURperMWh", "{:.1f}"),
        ("Renewable share, incl.\\ imports (\\%)", "RE_share_pct", "{:.1f}"),
        ("Renewable share, excl.\\ imports (\\%)", "RE_share_excl_imports_pct", "{:.1f}"),
        ("CO$_2$ emissions (Mt)", "CO2_Mt", "{:.1f}"),
        ("Gas fuel use (TWh$_\\mathrm{th}$)", "gas_fuel_TWhth", "{:.1f}"),
        ("Gas share of generation (\\%)", "gas_share_pct", "{:.1f}"),
        ("Solar PV (GW)", "solar_GW", "{:.1f}"),
        ("Wind (GW)", "wind_GW", "{:.1f}"),
        ("New OCGT (GW)", "OCGT_GW", "{:.1f}"),
        ("Battery energy (GWh)", "battery_GWh", "{:.1f}"),
        ("VRE curtailment (\\%)", "VRE_curtailment_pct", "{:.1f}"),
    ]
    lines = [r"\begin{tabular}{@{}lrrr@{}}", r"\toprule", "Indicator & " + " & ".join(cols.values()) + r" \\", r"\midrule"]
    for name, key, fmt in rows:
        lines.append(name + " & " + " & ".join(fmt.format(s.loc[key, c]) for c in cols) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "tables/tab_results.tex").write_text("\n".join(lines) + "\n")


def robustness_conditions():
    """Cost and RE share of the core cases under each sensitivity and weather year (2025 added once solved)."""
    res = ROOT / "results/TH2037_base/scenarios"
    s = pd.read_csv(res / "summary.csv", index_col=0)
    w = pd.read_csv(res / "weather_years_summary.csv", index_col=0)
    cond = {"Base (2022)": "", "High gas price": "_HG", "High solar cost": "_HSC", "Plan demand": "_HD", "Must-take imports": "_MT"}
    out = {label: s[[c + suf for c in ("PDP", "LC_CAP", "LC")]].set_axis(["PDP", "LC-CAP", "LC"], axis=1) for label, suf in cond.items()}
    for year, label in (("2020", "Dry year 2020"), ("2025", "Wet year 2025")):
        cols = [f"{c} {year}" for c in ("PDP", "LC_CAP", "LC")]
        if set(cols) <= set(w.columns):
            out[label] = w[cols].set_axis(["PDP", "LC-CAP", "LC"], axis=1)
    return out


def robustness_table():
    lines = [r"\begin{tabular}{@{}lrrrrrrr@{}}", r"\toprule",
             r" & \multicolumn{3}{c}{System cost} & LC-CAP & \multicolumn{3}{c}{Renewable share} \\",
             r" & \multicolumn{3}{c}{(billion EUR/yr)} & vs PDP & \multicolumn{3}{c}{incl. imports (\%)} \\",
             r"\cmidrule(lr){2-4}\cmidrule(lr){6-8}",
             r"Condition & PDP & LC-CAP & LC & (\%) & PDP & LC-CAP & LC \\", r"\midrule"]
    for label, d in robustness_conditions().items():
        c, re = d.loc["total_cost_bnEUR"], d.loc["RE_share_pct"]
        diff = 100 * (c["LC-CAP"] / c["PDP"] - 1)
        lines.append(f"{label} & {c['PDP']:.2f} & {c['LC-CAP']:.2f} & {c['LC']:.2f} & {diff:+.1f} & "
                     f"{re['PDP']:.1f} & {re['LC-CAP']:.1f} & {re['LC']:.1f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "tables/tab_robustness.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    (PAPER / "tables").mkdir(parents=True, exist_ok=True)
    calibration_table()
    assumptions_table()
    results_table()
    robustness_table()
    print("tables written to", PAPER / "tables")
