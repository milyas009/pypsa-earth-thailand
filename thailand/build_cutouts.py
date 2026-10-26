"""
Download ERA5 weather cutouts for additional weather years (Thailand-focused extent).

Same resolution (0.3 deg) and features as the 2022 South-East Asia cutout, on a smaller box that
still covers Thailand, Lao PDR and the upstream river basins used for hydro inflow.
Requires a Copernicus CDS key in ~/.cdsapirc.

Each month is downloaded into its own small cutout (cutouts/monthly/) and retried on failure, so a
dropped connection only costs that month; finished months are skipped on restart. The months are
then merged into the yearly cutout.

Usage (from the repository root):
    python thailand/build_cutouts.py 2025 [2019 ...]
Creates cutouts/cutout-<year>-era5-TH.nc
"""

import logging
import sys
import time
from pathlib import Path

import atlite
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
X = slice(95.0, 110.0)
Y = slice(3.0, 24.0)
FEATURES = ["wind", "influx", "runoff", "temperature", "height"]
MAX_TRIES = 20

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def build_month(year, month):
    path = ROOT / f"cutouts/monthly/cutout-{year}-{month:02d}-era5-TH.nc"
    if path.exists():
        logging.info(f"skip {path.name} (exists)")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, MAX_TRIES + 1):
        try:
            cutout = atlite.Cutout(path, module="era5", x=X, y=Y, time=f"{year}-{month:02d}", dx=0.3, dy=0.3)
            cutout.prepare(features=FEATURES, monthly_requests=True, concurrent_requests=False)
            logging.info(f"done {path.name}: {path.stat().st_size / 1e6:.0f} MB")
            return path
        except Exception as e:  # dropped connections, SSL errors, server timeouts
            logging.warning(f"{path.name} attempt {attempt}/{MAX_TRIES} failed: {type(e).__name__}: {e}")
            path.unlink(missing_ok=True)
            time.sleep(min(60 * attempt, 600))
    raise RuntimeError(f"giving up on {path.name}")


def merge(year, paths):
    out = ROOT / f"cutouts/cutout-{year}-era5-TH.nc"
    parts = [xr.open_dataset(p) for p in paths]
    static = [v for v in parts[0].data_vars if "time" not in parts[0][v].dims]
    merged = xr.concat([p.drop_vars(static) for p in parts], dim="time")
    for v in static:
        merged[v] = parts[0][v]
    merged.attrs = parts[0].attrs
    merged.to_netcdf(out)
    for p in parts:
        p.close()
    logging.info(f"done {out.name}: {out.stat().st_size / 1e9:.2f} GB ({merged.sizes['time']} hours)")


if __name__ == "__main__":
    for year in sys.argv[1:]:
        logging.info(f"building cutout-{year}-era5-TH.nc month by month")
        merge(year, [build_month(int(year), m) for m in range(1, 13)])
