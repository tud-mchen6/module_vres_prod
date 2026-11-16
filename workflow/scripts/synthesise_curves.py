"""
This script uses the synthesised data of the cost, quantity and area used by
all technologies and gives out a country-synthesised cost and land curve,
recording the cost ranking and land footprint of the vRES potential.

Performance notes (vs. the previous xarray/netCDF version):
- Inputs are uncompressed .npz files that load straight into numpy arrays.
  No lazy xarray datasets, no repeated netCDF fancy-indexed reads, no zlib.
- The LCOE threshold is applied per tech first, so every later step
  (land sharing, concatenation, sorting) works on fewer pixels.
- PV / onshore wind land sharing is resolved in place with np.searchsorted
  on the (already sorted) pixel ids. There is no split into "common" and "rest" pixels:
  the final sort by LCOE makes the concatenation order irrelevant.
- float32 for values, uint8 for tech_id, and one np.concatenate per column
  instead of repeated np.append and Python lists.
"""

import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# Integer code per technology, stored in the "tech_id" column of the output
TECH_NAME_DICT = {"pv_open_field": 0, "wind_onshore": 1, "wind_offshore": 2}
# Pixels with LCOE above this threshold (EUR/MWh) are left out of the curves
LCOE_THRESHOLD = 100
# Columns kept per pixel. Their order is the column order of the output parquet.
VALUE_KEYS = ("lcoe", "prod", "area")


def load_tech(path: str) -> dict:
    """Load one quantity_cost_{tech}.npz into a dict of numpy arrays."""
    with np.load(path) as npz:
        return {key: npz[key] for key in npz.files}


def filter_by_lcoe(data: dict, threshold: float) -> dict:
    """Keep only pixels with finite LCOE/production and LCOE <= threshold.

    Applied before the land-sharing logic, so that a pixel removed for being too
    expensive cannot "absorb" the land footprint of the other technology. This
    prevents land from being under-counted.
    """
    keep = (
        np.isfinite(data["lcoe"])
        & np.isfinite(data["prod"])
        & (data["lcoe"] <= threshold)
    )
    # Boolean indexing preserves order, so pixel_id stays sorted
    filtered = {key: data[key][keep] for key in ("pixel_id",) + VALUE_KEYS}
    # Grid metadata is not per-pixel, so pass it through unchanged
    filtered["grid_shape"] = data["grid_shape"]
    filtered["transform"] = data["transform"]
    return filtered


def share_land(pv: dict, wind: dict) -> None:
    """Resolve land sharing between open-field PV and onshore wind, in place.

    Logic: technologies can share land. If both are present in a pixel, only
    the larger land footprint is counted; the smaller one is set to zero.
    Ties go to PV, the same as the previous implementation.
    """
    # pixel_id = row * width + col on each tech's own raster (quantity_cost.py).
    # Equal ids mean the same location only if both rasters share the same grid
    # (shape + affine transform), so check that before matching ids.
    if not (
        np.array_equal(pv["grid_shape"], wind["grid_shape"])
        and np.allclose(pv["transform"], wind["transform"])
    ):
        raise ValueError("The pixels in wind_onshore and pv_open_field don't match!")

    pv_id, wind_id = pv["pixel_id"], wind["pixel_id"]
    if pv_id.size == 0 or wind_id.size == 0:
        return  # nothing to share

    # Both id arrays are sorted and unique (np.flatnonzero in quantity_cost.py,
    # and order-preserving filtering). For every PV pixel, binary-search its
    # position in the wind ids. This needs one int64 array of len(pv_id) and,
    # unlike np.intersect1d, does not concatenate and re-sort both arrays,
    # which matters for very large countries (~1e8 pixels).
    pos = np.searchsorted(wind_id, pv_id)
    # Positions equal to len(wind_id) mean "larger than every wind id";
    # clip them so the lookup below is valid (the comparison then fails).
    np.minimum(pos, wind_id.size - 1, out=pos)
    i_pv = np.flatnonzero(wind_id[pos] == pv_id)  # PV positions of shared pixels
    i_wind = pos[i_pv]  # matching wind positions
    del pos

    pv_larger = pv["area"][i_pv] >= wind["area"][i_wind]
    # Where PV uses more (or equal) land, wind's footprint is not counted, and vice versa
    wind["area"][i_wind[pv_larger]] = 0
    pv["area"][i_pv[~pv_larger]] = 0


def synthesise_cost_land(quantity_cost_techs, curve_data):
    # ------------------------------------------------------------------
    # 1. Read the data files for all techs except rooftop PV (not used for utility)
    # ------------------------------------------------------------------
    t1 = time.perf_counter()
    tech_files = [p for p in quantity_cost_techs if "rooftop" not in p]
    data_dict = {}
    for file in tech_files:
        # "<...>/quantity_cost_wind_onshore.npz" -> "wind_onshore"
        # (pathlib also handles Windows path separators)
        tech = Path(file).stem.removeprefix("quantity_cost_")
        data = load_tech(file)
        # Techs without any area potential produce empty files; skip them
        if data["area"].size > 0:
            data_dict[tech] = data
    t2 = time.perf_counter()
    print(f"[TIMING] Reading npz files took {t2 - t1:.4f} seconds")

    # ------------------------------------------------------------------
    # 2. Remove too-expensive / invalid pixels per tech (before land sharing)
    # ------------------------------------------------------------------
    for tech in data_dict:
        data_dict[tech] = filter_by_lcoe(data_dict[tech], LCOE_THRESHOLD)
    t3 = time.perf_counter()
    print(f"[TIMING] Filtering by LCOE threshold took {t3 - t2:.4f} seconds")

    # ------------------------------------------------------------------
    # 3. Land sharing between the techs that 'occupy land':
    #    pv_open_field and wind_onshore
    # ------------------------------------------------------------------
    if "pv_open_field" in data_dict and "wind_onshore" in data_dict:
        share_land(data_dict["pv_open_field"], data_dict["wind_onshore"])
    t4 = time.perf_counter()
    print(f"[TIMING] Recalculating wind and solar areas took {t4 - t3:.4f} seconds")

    # ------------------------------------------------------------------
    # 4. Build the full arrays: one concatenate per column
    # ------------------------------------------------------------------
    result_dict = {
        key: np.concatenate(
            [data[key] for data in data_dict.values()]
            or [np.empty(0, dtype=np.float32)]
        ).astype(np.float32, copy=False)
        for key in VALUE_KEYS
    }
    # np.full creates the tech id column directly as uint8, with no Python lists
    result_dict["tech_id"] = np.concatenate(
        [
            np.full(data["lcoe"].size, TECH_NAME_DICT[tech], dtype=np.uint8)
            for tech, data in data_dict.items()
        ]
        or [np.empty(0, dtype=np.uint8)]
    )
    del data_dict  # free the per-tech copies before sorting
    t5 = time.perf_counter()
    print(f"[TIMING] Constructing all full arrays took {t5 - t4:.4f} seconds")

    # ------------------------------------------------------------------
    # 5. Sort all arrays by LCOE and save to parquet
    # ------------------------------------------------------------------
    # Stable sort keeps the result deterministic for equal LCOE values
    order = np.argsort(result_dict["lcoe"], kind="stable")
    for key in result_dict:
        result_dict[key] = np.take(result_dict[key], order)
    del order

    # prod and area are written as float64: plot_curves.py takes cumulative
    # sums over millions of rows, and a float32 running sum would accumulate
    # rounding error. lcoe stays float32 and tech_id stays uint8.
    result_dict["prod"] = result_dict["prod"].astype(np.float64)
    result_dict["area"] = result_dict["area"].astype(np.float64)

    # Output columns: lcoe, prod, area, tech_id (same as before)
    table = pa.table(result_dict)
    pq.write_table(table, curve_data)
    t6 = time.perf_counter()
    print(f"[TIMING] Sorting the arrays and save to parquet took {t6 - t5:.4f} seconds")


if __name__ == "__main__":
    synthesise_cost_land(
        quantity_cost_techs=snakemake.input.quantity_cost_techs,
        curve_data=snakemake.output.curve_data,
    )
