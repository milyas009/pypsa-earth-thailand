# PyPSA-Earth model of Thailand: draft Power Development Plan 2024–2037

Model setup, input data, scripts and result summaries for the paper

> Ilyas, M., Suyaroj, N., Kuensaen, C. *Can national power plans meet their own renewable targets? A calibrated multi-weather-year test of Thailand's draft Power Development Plan 2024–2037* (manuscript in preparation for *Energy Policy*).

The model is an hourly, six-node representation of the Thai power system in 2037, built with
[PyPSA-Earth](https://github.com/pypsa-meets-earth/pypsa-earth) v0.10.0 and calibrated to observed
generation by fuel in 2022 (Ember). It compares the capacities of the draft PDP2024 with a realistic
least-cost expansion (LC-CAP) and an unconstrained least-cost bound (LC), under cost, demand, import and
weather-year (2020, 2022, 2025) sensitivities.

## Contents

| Path | Content |
|---|---|
| `config.yaml` | Thailand settings on top of PyPSA-Earth's `config.default.yaml` (base year 2037, weather 2022) |
| `config_TH2022_calib.yaml` | overlay for the 2022 calibration run |
| `config_TH2037_w2020.yaml`, `config_TH2037_w2025.yaml` | overlays for the 2020 and 2025 weather years |
| `data/thailand/custom_powerplants_TH.csv` | plant-level list of the Thai fleet with retirement dates (incl. Hongsa as lignite) |
| `data/thailand/agg_p_nom_minmax_*.csv` | capacity limits per technology: `PDP2024_2037` (plan), `LC_CAP_2037` (realistic), `LC_2037` (unconstrained), `2022_existing` (calibration) |
| `data/ssp2-2.6/2037/era5_YYYY/Asia.csv` | hourly demand for 2037 (2022 profile; re-dated for 2020 and 2025) |
| `thailand/solve_thailand.py` | scenario definitions and solving (adds Lao hydropower imports, new OCGT, sensitivities) |
| `thailand/analyze_thailand.py` | indicators, capacity ceiling and weather-year comparison |
| `thailand/calibrate_2022.py` | comparison of the 2022 run with Ember data |
| `thailand/build_cutouts.py` | download of ERA5 weather cutouts month by month |
| `thailand/make_tables.py`, `thailand/make_figures.py` | tables and figures of the paper |
| `results/` | result summaries (CSV) for all scenarios |

The solved networks (about 17 MB each) and the ERA5 cutouts (about 1 GB per year) are not included;
they can be regenerated with the steps below.

## How the model is run

The workflow has two stages.

1. **Network building with PyPSA-Earth's Snakemake workflow.** The standard rules (OpenStreetMap network,
   clustering to six nodes, renewable profiles, demand, existing plants, costs) produce the prepared network
   `networks/<run>/elec_s_6_ec_lcopt_CCL.nc`. No PyPSA-Earth source file is modified.
2. **Scenario solving with `thailand/solve_thailand.py`.** The script loads the prepared network, applies the
   scenario settings that PyPSA-Earth's configuration cannot express (Lao hydropower imports, new OCGT at every
   node, capacity limits per case, sensitivities, weather-year scaling of hydropower and imports) and then calls
   PyPSA-Earth's own `prepare_network` and `solve_network` functions from `scripts/solve_network.py`, i.e. the
   same optimisation as the `solve_network` rule.

## Reproducing the results

```bash
# 1. PyPSA-Earth v0.10.0 and its environment
git clone https://github.com/pypsa-meets-earth/pypsa-earth.git
cd pypsa-earth && git checkout v0.10.0
conda env create -f envs/environment.yaml && conda activate pypsa-earth

# 2. copy this repository into the PyPSA-Earth folder (same relative paths)
cp -r /path/to/pypsa-earth-thailand/{config*.yaml,data,thailand} .

# 3. weather data: ERA5 cutouts (requires a Copernicus CDS account, ~/.cdsapirc)
python thailand/build_cutouts.py 2020      # -> cutouts/cutout-2020-era5-TH.nc
python thailand/build_cutouts.py 2025      # -> cutouts/cutout-2025-era5-TH.nc
python thailand/build_cutouts.py 2022      # base year; save or link it as cutouts/cutout-2022-era5-SEA.nc

# 4. build the prepared networks (first run also downloads the PyPSA-Earth data bundles;
#    set enable: retrieve_databundle: true in config.yaml for that run)
snakemake networks/TH2037_base/elec_s_6_ec_lcopt_CCL.nc --cores 4
snakemake networks/TH2037_w2020/elec_s_6_ec_lcopt_CCL.nc --configfile config_TH2037_w2020.yaml --cores 4
snakemake networks/TH2037_w2025/elec_s_6_ec_lcopt_CCL.nc --configfile config_TH2037_w2025.yaml --cores 4
snakemake networks/TH2022_calib/elec_s_6_ec_lcopt_CCL.nc --configfile config_TH2022_calib.yaml --cores 4

# 5. solve the scenarios (Gurobi was used; other LP solvers supported by linopy work as well)
python thailand/solve_thailand.py CALIB2022
python thailand/solve_thailand.py PDP LC_CAP LC PDP_HG LC_CAP_HG LC_HG PDP_HSC LC_CAP_HSC LC_HSC \
       PDP_HD LC_CAP_HD LC_HD PDP_MT LC_CAP_MT LC_MT
python thailand/solve_thailand.py sweep
python thailand/solve_thailand.py PDP_w2020 LC_CAP_w2020 LC_w2020 PDP_w2025 LC_CAP_w2025 LC_w2025

# 6. indicators, tables and figures
python thailand/calibrate_2022.py
python thailand/analyze_thailand.py PDP LC_CAP LC PDP_HG LC_CAP_HG LC_HG PDP_HSC LC_CAP_HSC LC_HSC \
       PDP_HD LC_CAP_HD LC_HD PDP_MT LC_CAP_MT LC_MT
python thailand/analyze_thailand.py PDP_solar30.3 PDP_solar45 PDP_solar60 PDP_solar75 PDP_solar90 PDP_solar105 PDP_solar120
python thailand/analyze_thailand.py --weather
PAPER_DIR=paper_outputs python thailand/make_tables.py
PAPER_DIR=paper_outputs python thailand/make_figures.py
```

## Scenario names

| Name | Meaning |
|---|---|
| `PDP` | solar and wind limited to the draft PDP2024 (30.3 GW solar, 6.9 GW onshore wind) |
| `LC_CAP` | realistic least cost: solar ≤ 62.3 GW, onshore wind ≤ 13 GW (central case) |
| `LC` | unconstrained least cost (technical potential only) |
| `_HG`, `_HSC`, `_HD`, `_MT` | gas price +50 %, solar capital cost +50 %, demand at the plan's peak, must-take Lao imports |
| `_w2020`, `_w2025` | weather year 2020 (dry) or 2025 (wet) |
| `PDP_solarX` | PDP with the solar limit raised to X GW (solar sweep) |
| `CALIB2022` | 2022 calibration run (existing fleet) |

## Data sources

Power plants: compiled from EGAT, Global Energy Monitor and powerplantmatching data, with Mae Moh retirement
dates from the National Energy Policy Committee decision of August 2025. Plan capacities: draft PDP2024
(public hearing, June 2024). Calibration: Ember yearly electricity data. Costs: PyPSA technology-data v0.15.0
(2035). Weather: ERA5 (Copernicus Climate Change Service). Full references are given in the paper.

## Licence

Code (`thailand/`): AGPL-3.0-or-later, as PyPSA-Earth. Data, configuration and results: CC BY 4.0.
See `LICENSES/`.

## Citation

Please cite the paper (see `CITATION.cff`) and PyPSA-Earth (Parzen et al., 2023, *Applied Energy* 341, 121096).
