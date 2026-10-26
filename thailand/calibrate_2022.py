"""
Compare the 2022 calibration run (scenario CALIB2022) with Ember's 2022 data for Thailand.

Ember counts the Hongsa lignite plant (Lao PDR) as net imports, whereas the model includes it in the
lignite generator at the northern node together with Mae Moh; its output is split off by capacity share.

Usage (from the repository root):
    python thailand/calibrate_2022.py
Writes results/TH2022_calib/scenarios/calibration_vs_ember2022.csv.
"""

from pathlib import Path

import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/TH2022_calib/scenarios"

# Ember yearly electricity data, Thailand 2022 (TWh)
EMBER_2022 = {
    "Gas": 114.64,
    "Coal + lignite (excl. Hongsa)": 35.52,
    "Bioenergy": 13.86,
    "Hydro (domestic)": 6.60,
    "Solar": 5.03,
    "Wind": 2.99,
    "Oil / other fossil": 1.73,
    "Net imports (Lao hydro + Hongsa)": 33.41,
}
HONGSA_SHARE = 1470 / (1470 + 2220)  # Hongsa / (Hongsa + Mae Moh in 2022), MW


def main():
    n = pypsa.Network(RES / "CALIB2022.nc")
    w = n.snapshot_weightings.generators
    g, su = n.generators, n.storage_units
    gen = n.generators_t.p.mul(w, axis=0).sum().groupby(g.carrier).sum() / 1e6
    hydro = n.storage_units_t.p_dispatch[su.index[su.carrier == "hydro"]].mul(w, axis=0).sum().sum() / 1e6
    hongsa = gen.get("lignite", 0) * HONGSA_SHARE

    model = {
        "Gas": gen.reindex(["CCGT", "OCGT"]).fillna(0).sum(),
        "Coal + lignite (excl. Hongsa)": gen.get("coal", 0) + gen.get("lignite", 0) - hongsa,
        "Bioenergy": gen.get("biomass", 0),
        "Hydro (domestic)": hydro + gen.get("ror", 0),
        "Solar": gen.get("solar", 0),
        "Wind": gen.reindex(["onwind", "offwind-ac", "offwind-dc"]).fillna(0).sum(),
        "Oil / other fossil": gen.get("oil", 0),
        "Net imports (Lao hydro + Hongsa)": gen.get("imports", 0) + hongsa,
    }
    df = pd.DataFrame({"Model 2022 (TWh)": model, "Ember 2022 (TWh)": EMBER_2022})
    df["Difference (TWh)"] = df.iloc[:, 0] - df.iloc[:, 1]
    df["Difference (%)"] = 100 * df["Difference (TWh)"] / df.iloc[:, 1]
    tot = df.iloc[:, :2].sum()
    df.loc["Total supply"] = [tot.iloc[0], tot.iloc[1], tot.iloc[0] - tot.iloc[1], 100 * (tot.iloc[0] / tot.iloc[1] - 1)]
    df.round(2).to_csv(RES / "calibration_vs_ember2022.csv")
    print(df.round(1).to_string())


if __name__ == "__main__":
    main()
