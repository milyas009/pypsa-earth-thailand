"""
Journal paper figures, generated from the solved scenarios (no hand-edited numbers).

Usage (from the repository root):
    python thailand/make_figures.py
Writes PDFs into $PAPER_DIR/figures/ (default: paper_outputs/).
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/TH2037_base/scenarios"
PAPER = Path(os.environ.get("PAPER_DIR", ROOT / "paper_outputs"))  # folder of the LaTeX manuscript
FIG = PAPER / "figures"

CORE = {"PDP": "PDP", "LC_CAP": "LC-CAP", "LC": "LC"}
# technology groups in stacking order; colours = validated categorical palette in its fixed slot order
GROUPS = {
    "Hydro (domestic)": ["hydro", "ror"],
    "Gas (CCGT + OCGT)": ["CCGT", "OCGT"],
    "Wind": ["onwind", "offwind-ac", "offwind-dc"],
    "Solar PV": ["solar"],
    "Hydro imports": ["imports"],
    "Biomass": ["biomass"],
    "Other": ["nuclear", "oil", "geothermal"],
    "Coal and lignite": ["coal", "lignite"],
}
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42, "mathtext.fontset": "stix",
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral"], "font.size": 8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True, "legend.frameon": False,
})


def by_group(series):
    return pd.Series({k: series.reindex(v).fillna(0).sum() for k, v in GROUPS.items()})


def capacity_and_generation(n):
    w = n.snapshot_weightings.generators
    g, su = n.generators, n.storage_units
    cap = g.p_nom_opt.groupby(g.carrier).sum()
    cap = cap.add(su.p_nom_opt.groupby(su.carrier).sum().reindex(["hydro"]).fillna(0), fill_value=0)
    gen = n.generators_t.p.mul(w, axis=0).sum().groupby(g.carrier).sum()
    hyd = n.storage_units_t.p_dispatch[su.index[su.carrier == "hydro"]].mul(w, axis=0).sum().sum()
    gen = gen.add(pd.Series({"hydro": hyd}), fill_value=0)
    return by_group(cap) / 1e3, by_group(gen) / 1e6


def fig_mix():
    caps, gens = {}, {}
    for key, label in CORE.items():
        caps[label], gens[label] = capacity_and_generation(pypsa.Network(RES / f"{key}.nc"))
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 2.6))
    for ax, df, ylabel, title in [(axes[0], pd.DataFrame(caps).T, "Capacity (GW)", "(a) Installed capacity"),
                                  (axes[1], pd.DataFrame(gens).T, "Generation (TWh)", "(b) Annual generation")]:
        bottom = pd.Series(0.0, index=df.index)
        for col, color in zip(df.columns, COLORS):
            ax.bar(df.index, df[col], bottom=bottom, color=color, width=0.6, label=col, edgecolor="white", linewidth=1.0)
            bottom += df[col]
        for x, v in bottom.items():
            ax.text(x, v + bottom.max() * 0.015, f"{v:.0f}", ha="center", va="bottom", fontsize=7, color=INK)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=8, loc="left")
        ax.set_ylim(0, bottom.max() * 1.12)
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="upper center", bbox_to_anchor=(0.5, 0.0), fontsize=6.5, ncol=4)
    fig.tight_layout()
    fig.savefig(FIG / "fig_mix.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_sweep():
    s = pd.read_csv(RES / "sweep_summary.csv", index_col=0).T
    s.index = [float(i.replace("PDP_solar", "")) for i in s.index]
    panels = [("RE_share_pct", "Renewable share (%)", "(a) Renewable share"),
              ("total_cost_bnEUR", "System cost (billion EUR/yr)", "(b) Total system cost"),
              ("gas_fuel_TWhth", "Gas use (TWh$_{th}$)", "(c) Gas fuel use"),
              ("battery_GWh", "Battery energy (GWh)", "(d) Battery storage")]
    fig, axes = plt.subplots(2, 2, figsize=(5.4, 3.8))
    for ax, (col, ylabel, title) in zip(axes.flat, panels):
        ax.plot(s.index, s[col], color=COLORS[0], linewidth=2, marker="o", markersize=4)
        ax.axvline(62.3, color=MUTED, linestyle=":", linewidth=1)
        ax.set_title(title, fontsize=8, loc="left")
        ax.set_ylabel(ylabel, fontsize=7)
        ax.set_xlabel("Solar PV limit (GW)", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.set_xticks([30, 60, 90, 120])
        if col == "RE_share_pct":
            ax.axhline(51, color=MUTED, linestyle="--", linewidth=1)
            ax.text(s.index.min(), 51.6, "51% target", fontsize=6.5, color=MUTED, va="bottom")
    fig.tight_layout()
    fig.savefig(FIG / "fig_solar_sweep.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_dispatch(scenario="LC_CAP"):
    """Hourly balance in the week with the highest VRE output (Thai local time, UTC+7)."""
    n = pypsa.Network(RES / f"{scenario}.nc")
    g, su, lk = n.generators, n.storage_units, n.links
    p = n.generators_t.p.T.groupby(g.carrier).sum().T
    vre = p.reindex(columns=["solar", "onwind", "offwind-ac", "offwind-dc"]).fillna(0).sum(axis=1)
    end = vre.rolling(168).sum().idxmax()
    sl = slice(end - pd.Timedelta(hours=167), end)
    gen = pd.DataFrame({k: p.reindex(columns=v).fillna(0).sum(axis=1) for k, v in GROUPS.items()})
    gen["Hydro (domestic)"] += n.storage_units_t.p_dispatch[su.index[su.carrier == "hydro"]].sum(axis=1)
    sto = n.storage_units_t.p[su.index[su.carrier == "PHS"]].sum(axis=1)
    dis, cha = lk.index[lk.carrier == "battery discharger"], lk.index[lk.carrier == "battery charger"]
    sto += -n.links_t.p1[dis].sum(axis=1) - n.links_t.p0[cha].sum(axis=1)
    load = n.loads_t.p_set.sum(axis=1)
    gen, sto, load = (x.loc[sl] / 1e3 for x in (gen, sto, load))
    gen, sto, load = (x.set_axis(x.index + pd.Timedelta(hours=7)) for x in (gen, sto, load))
    fig, ax = plt.subplots(figsize=(5.4, 2.8))
    ax.stackplot(gen.index, gen.T.values, colors=COLORS, labels=gen.columns, linewidth=0)
    top = gen.sum(axis=1)
    ax.fill_between(gen.index, top, top + sto.clip(lower=0), color=MUTED, linewidth=0, label="Storage discharge")
    ax.plot(load.index, load - sto.clip(upper=0), color=INK, linewidth=1.0, linestyle="--", label="Demand + storage charging")
    ax.plot(load.index, load, color=INK, linewidth=1.5, label="Demand")
    ax.set_ylabel("Power (GW)")
    ax.margins(x=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=6.5, ncol=4, reverse=True)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d %b"))
    fig.tight_layout()
    fig.savefig(FIG / f"fig_dispatch_{scenario}.pdf", bbox_inches="tight")
    plt.close(fig)
    return sl


def fig_robustness():
    import sys
    sys.path.insert(0, str(ROOT / "thailand"))
    from make_tables import robustness_conditions

    cond = robustness_conditions()
    labels = [k.replace(" (2022)", "") for k in cond]
    x = range(len(cond))
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 2.9))
    for i, (case, color) in enumerate(zip(["LC-CAP", "LC"], [COLORS[0], COLORS[1]])):
        diff = [100 * (d.loc["total_cost_bnEUR", case] / d.loc["total_cost_bnEUR", "PDP"] - 1) for d in cond.values()]
        axes[0].bar([j + (i - 0.5) * 0.36 for j in x], diff, width=0.34, color=color, label=case)
    axes[0].axhline(0, color=MUTED, linewidth=0.8)
    axes[0].set_ylabel("Cost difference to PDP (%)")
    axes[0].set_title("(a) System cost relative to PDP", fontsize=8, loc="left")
    for i, (case, color) in enumerate(zip(["PDP", "LC-CAP", "LC"], [COLORS[7], COLORS[0], COLORS[1]])):
        re = [d.loc["RE_share_pct", case] for d in cond.values()]
        axes[1].bar([j + (i - 1) * 0.26 for j in x], re, width=0.25, color=color, label=case)
    axes[1].axhline(51, color=MUTED, linestyle="--", linewidth=1, label="51% target")
    axes[1].set_ylim(0, 90)
    axes[1].set_ylabel("Renewable share (%)")
    axes[1].set_title("(b) Renewable share incl. imports", fontsize=8, loc="left")
    for ax in axes:
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
        ax.legend(fontsize=6.5, loc="lower right" if ax is axes[0] else "upper left", ncol=1 if ax is axes[0] else 2)
    fig.tight_layout()
    fig.savefig(FIG / "fig_robustness.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_network(scenario="LC_CAP"):
    """Six-node network: regions, lines and demand (a); solar and battery capacity of a case by node (b)."""
    import geopandas as gpd
    from matplotlib.lines import Line2D

    regions = gpd.read_file(ROOT / "resources/TH2037_base/bus_regions/regions_onshore_elec_s_6.geojson").set_index("name")
    n = pypsa.Network(RES / f"{scenario}.nc")
    w = n.snapshot_weightings.generators
    buses = n.buses.loc[regions.index]
    names = {"TH0 0": "Bangkok and east", "TH0 1": "North", "TH0 2": "South", "TH0 3": "Northeast",
             "TH0 4": "Lower central", "TH1 0": "Upper central"}
    # label offsets (degrees) chosen so that labels do not overlap; upper central sits next to lower central
    off_a = {"TH0 0": (0.7, -0.5), "TH0 1": (-0.6, 0.5), "TH0 2": (0.6, 0.0), "TH0 3": (0.6, 0.3),
             "TH0 4": (-0.7, -0.2), "TH1 0": (1.2, -0.3)}
    demand = n.loads_t.p_set.mul(w, axis=0).sum().groupby(n.loads.bus).sum() / 1e6
    g, st = n.generators, n.stores
    solar = g[g.carrier == "solar"].groupby("bus").p_nom_opt.sum().reindex(buses.index, fill_value=0) / 1e3
    batt = st[st.carrier == "battery"].groupby(st.bus.str.replace(" battery", "")).e_nom_opt.sum().reindex(buses.index, fill_value=0) / 1e3
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 4.4))
    for ax in axes:
        regions.dissolve(level=0).plot(ax=ax, color="#f2f1ec", edgecolor=MUTED, linewidth=0.5)
        for _, l in n.lines.iterrows():
            new = l.s_nom == 0
            ax.plot([buses.x[l.bus0], buses.x[l.bus1]], [buses.y[l.bus0], buses.y[l.bus1]],
                    color=COLORS[1] if new else INK, linewidth=0.5 + l.s_nom_opt / 12000,
                    linestyle="--" if new else "-", zorder=2)
        ax.set_axis_off()
        ax.set_xlim(96.5, 107.5)
    ax = axes[0]
    ax.scatter(buses.x, buses.y, s=demand.reindex(buses.index) * 1.5, color=COLORS[0], zorder=3, edgecolor="white")
    for b, r in buses.iterrows():
        dx, dy = off_a[b]
        ax.text(r.x + dx, r.y + dy, f"{names[b]}\n{demand[b]:.0f} TWh", fontsize=6.5, ha="left" if dx > 0 else "right",
                va="center", color=INK, zorder=4, bbox=dict(fc="white", ec="none", alpha=0.75, pad=0.6))
    lao = n.generators[n.generators.carrier == "imports"].bus.iloc[0]
    ax.annotate("Lao hydropower\nimports, 7.1 GW", (buses.x[lao], buses.y[lao]), xytext=(104.3, 19.6), fontsize=6.5,
                color=COLORS[4], arrowprops=dict(arrowstyle="->", color=COLORS[4], lw=0.8))
    ax.legend(handles=[Line2D([], [], color=INK, lw=1.8, label="line (width: capacity)"),
                       Line2D([], [], color=COLORS[1], lw=1, ls="--", label="new connection"),
                       Line2D([], [], marker="o", ls="", color=COLORS[0], ms=6, label="node (area: demand)")],
              loc="lower left", fontsize=6.5)
    ax.set_title("(a) Network and demand in 2037", fontsize=8, loc="left")
    ax = axes[1]
    ax.scatter(buses.x - 0.2, buses.y, s=solar * 5, color=COLORS[3], zorder=3, edgecolor="white")
    ax.scatter(buses.x + 0.2, buses.y, s=batt * 5, color=COLORS[6], zorder=3, edgecolor="white")
    for b, r in buses.iterrows():
        if b == "TH1 0" or solar[b] + batt[b] < 1:
            continue
        ax.text(r.x - 0.75, r.y, f"{solar[b]:.1f}", fontsize=6.5, ha="right", va="center", color="#9a6a00", zorder=4,
                bbox=dict(fc="white", ec="none", alpha=0.75, pad=0.5))
        ax.text(r.x + 0.75, r.y, f"{batt[b]:.1f}", fontsize=6.5, ha="left", va="center", color=COLORS[6], zorder=4,
                bbox=dict(fc="white", ec="none", alpha=0.75, pad=0.5))
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=COLORS[3], ms=6, label="solar PV (GW)"),
                       Line2D([], [], marker="o", ls="", color=COLORS[6], ms=6, label="batteries (GWh)")],
              loc="lower left", fontsize=6.5)
    ax.set_title(f"(b) Solar and batteries, {CORE[scenario]}", fontsize=8, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "fig_network.pdf", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    fig_network()
    fig_mix()
    fig_sweep()
    fig_robustness()
    print("dispatch week (UTC):", fig_dispatch())
    print("figures written to", FIG)
