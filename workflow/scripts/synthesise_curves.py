# Remember: delete the fat .nc file. Also think about whether there's a better way to do all these.

"""
This script uses the synthesised data of the cost, quantity and area used by
all technologies and gives out a country-synthesised cost and land curve,
recording the cost ranking and land footprint of the vRES potential.
"""

import xarray as xr
import numpy as np
import time
import pyarrow as pa
import pyarrow.parquet as pq


def flatten_da_to_np_with_tech(da):
    dims = list(da.dims)
    transpose_order = [d for d in dims if d != "tech"] + ["tech"]
    arr = da.transpose(*transpose_order).values
    return arr.reshape(-1)


def cutout_da_pixels(da, arr):
    mask = da.pixel_id.isin(arr)
    return da.sel(pixel_id=mask), da.sel(pixel_id=~mask)


def synthesise_cost_land(quantity_cost_techs, curve_data):

    # Initialise the output
    area_all_tech = np.array([])
    prod_all_tech = np.array([])
    lcoe_all_tech = np.array([])
    id_all_tech = np.array([])
    tech_name_dict = {"pv_open_field": 0, "wind_onshore": 1, "wind_offshore": 2}

    t1 = time.perf_counter()
    # Read the data files for all techs except rooftop PV (not used for utility)
    tech_files = [p for p in quantity_cost_techs if "rooftop" not in p]
    ds_dict = {}
    for file in tech_files:
        ds_dict[file.split("/")[-1].split(".")[0].replace("quantity_cost_", "")] = (
            xr.open_dataset(file)
        )
    t2 = time.perf_counter()
    print(f"[TIMING] Reading NetCDF files took {t2 - t1:.4f} seconds")
    # The techs that will 'occupy land' are pv_open_field and wind_onshore
    # Find the pixels where both tech exist to calculate the land footprint
    breakpoint()
    if ("pv_open_field" in ds_dict.keys()) & ("wind_onshore" in ds_dict.keys()):
        t3 = time.perf_counter()
        pv_area_pixels = ds_dict["pv_open_field"]["pixel_id"].values
        wind_area_pixels = ds_dict["wind_onshore"]["pixel_id"].values
        common = np.intersect1d(pv_area_pixels, wind_area_pixels)
        pv_common, pv_rest = cutout_da_pixels(ds_dict["pv_open_field"], common)
        wind_common, wind_rest = cutout_da_pixels(ds_dict["wind_onshore"], common)
        t4 = time.perf_counter()
        print(
            f"[TIMING] Disseminating wind and solar overlaps took {t4 - t3:.4f} seconds"
        )
        # Check if the shapes fit
        if np.array_equal(pv_common["pixel_id"].values, wind_common["pixel_id"].values):
            t5 = time.perf_counter()
            pv_area_common = pv_common.area.data[0]
            wind_area_common = wind_common.area.data[0]
            # Logic: technologies can share land. So if one technology occupies
            # more land in a specific pixel, there's no need to count the land
            # footprint of another technology
            mask_pv = pv_area_common >= wind_area_common
            wind_area_common[mask_pv] = 0
            pv_area_common[~mask_pv] = 0
            t6 = time.perf_counter()
            print(
                f"[TIMING] Recalculating wind and solar areas took {t6 - t5:.4f} seconds"
            )
        else:
            ValueError("The pixels in wind_onshore and pv_open_field don't match!")
            # TODO: think what's appropriate here
        # Flatten the dataarrays into numpy arrays
        t7 = time.perf_counter()
        tech_name_dict = {"pv_open_field": 0, "wind_onshore": 1, "wind_offshore": 2}
        for key in ds_dict.keys():
            if (key != "pv_open_field") & (key != "wind_onshore"):
                area_all_tech = np.append(
                    area_all_tech, np.zeros(ds_dict[key].area.sel(tech=key).size)
                )
                prod_all_tech = np.append(
                    prod_all_tech, ds_dict[key]["prod"].sel(tech=key).values
                )
                lcoe_all_tech = np.append(
                    lcoe_all_tech, ds_dict[key]["lcoe"].sel(tech=key).values
                )
                id_all_tech = np.append(
                    id_all_tech,
                    [tech_name_dict[key]] * ds_dict[key].area.sel(tech=key).size,
                )
        area_all_tech = np.concatenate(
            (
                area_all_tech,
                pv_area_common,
                pv_rest.area.values.reshape(-1),  # TODO: think about wiser ways
                wind_area_common,
                wind_rest.area.values.reshape(-1),
            )
        )
        prod_all_tech = np.concatenate(
            (
                prod_all_tech,
                pv_common["prod"].values.reshape(-1),
                pv_rest["prod"].values.reshape(-1),
                wind_common["prod"].values.reshape(-1),
                wind_rest["prod"].values.reshape(-1),
            )
        )
        lcoe_all_tech = np.concatenate(
            (
                lcoe_all_tech,
                pv_common["lcoe"].values.reshape(-1),
                pv_rest["lcoe"].values.reshape(-1),
                wind_common["lcoe"].values.reshape(-1),
                wind_rest["lcoe"].values.reshape(-1),
            )
        )
        id_all_tech = np.concatenate(
            (
                id_all_tech,
                [tech_name_dict["pv_open_field"]] * pv_common["area"][0].size,
                [tech_name_dict["pv_open_field"]] * pv_rest["area"][0].size,
                [tech_name_dict["wind_onshore"]] * wind_common["area"][0].size,
                [tech_name_dict["wind_onshore"]] * wind_rest["area"][0].size,
            )
        )
        t8 = time.perf_counter()
        print(f"[TIMING] Constructing all three full arrays took {t8 - t7:.4f} seconds")
    else:
        for key in ds_dict.keys():
            area_all_tech = np.append(
                area_all_tech, ds_dict[key]["area"].sel(tech=key).values
            )
            prod_all_tech = np.append(
                prod_all_tech, ds_dict[key]["prod"].sel(tech=key).values
            )
            lcoe_all_tech = np.append(
                lcoe_all_tech, ds_dict[key]["lcoe"].sel(tech=key).values
            )
            id_all_tech = np.append(
                id_all_tech, [tech_name_dict[key]] * ds_dict[key]["lcoe"][0].size
            )
    # Sort all arrays with lcoe
    t9 = time.perf_counter()
    order = np.argsort(lcoe_all_tech, kind="mergesort")
    lcoe_all_tech = lcoe_all_tech[order]
    prod_all_tech = prod_all_tech[order]
    area_all_tech = area_all_tech[order]
    id_all_tech = id_all_tech[order]
    # Need to return: lcoe, prod, area, tech_id, left_positions
    left_positions = np.cumsum(np.concatenate(([0.0], prod_all_tech[:-1]))).astype(
        np.float32
    )
    result_dict = {
        "lcoe": lcoe_all_tech,
        "prod": prod_all_tech,
        "area": area_all_tech,
        "tech_id": id_all_tech,
        "left_positions": left_positions,
    }
    table = pa.table(result_dict)
    pq.write_table(table, curve_data)
    t10 = time.perf_counter()
    print(
        f"[TIMING] Sorting the arrays and save to parquet took {t10 - t9:.4f} seconds"
    )

    # Read the data files for all techs except rooftop as it does not
    # "occupy extra land"
    # tech_files = [p for p in quantity_cost_techs if "rooftop" not in p]
    # combined = xr.open_mfdataset(
    #     tech_files,
    #     chunks={"pixel_id": 262144},  # heuristic chunk size, 512 * 512
    #     join="outer",
    #     combine="nested",
    #     concat_dim="tech",
    #     parallel=True,
    # )
    # area_pv = combined.area.sel(tech="pv_open_field")
    # area_onshore = combined.area.sel(tech="wind_onshore")
    # # First find pixels where both techs are present, assume they
    # # share land totally (conservative land use estimation)
    # both_valid = (area_onshore.notnull() & area_pv.notnull()).compute()
    # combined_both = combined.where(both_valid, drop=True)
    # del area_pv, area_onshore
    # # Update the 'area' value: if one is larger than the other, the
    # # other is set to zero
    # area_pv_both = combined_both.area.sel(tech="pv_open_field")
    # area_wind_both = combined_both.area.sel(tech="wind_onshore")
    # area_pv_new = xr.where(area_pv_both >= area_wind_both, area_pv_both, 0)
    # area_onshore_new = xr.where(area_wind_both > area_pv_both, area_wind_both, 0)
    # combined_both["area"] = xr.concat(
    #     [
    #         area_pv_new.expand_dims(tech=["pv_open_field"]),
    #         area_onshore_new.expand_dims(tech=["wind_onshore"]),
    #         combined_both["area"].sel(tech="wind_offshore"),
    #     ],
    #     dim="tech",
    #     join="outer",
    # ).assign_coords(tech=combined_both.tech)
    # # combined_both is then ready for flattening
    # combined_both_dict = {}
    # for var in list(combined_both.data_vars):
    #     combined_both_dict[var] = flatten_da_to_np_with_tech(combined_both[var])
    # # Also correspond each data point to a tech
    # tech_names = [str(v) for v in combined_both.coords["tech"].values]
    # non_tech_size = combined_both_dict["area"].size // len(tech_names)
    # tech_id = np.tile(np.arange(len(tech_names), dtype=np.uint16), non_tech_size)
    # # Filter out nan values
    # mask = np.isfinite(combined_both_dict["lcoe"]) & np.isfinite(
    #     combined_both_dict["prod"]
    # )
    # for key in combined_both_dict.keys():
    #     combined_both_dict[key] = combined_both_dict[key][mask]
    # combined_both_dict["tech"] = tech_id[mask]
    # # Same procedure for other pixels where only one tech exist
    # single_valid = ~both_valid.compute()
    # combined_single = combined.where(single_valid, drop=True)
    # breakpoint()
    # # Sort everything according to lcoe
    # order = np.argsort(combined_both_dict["lcoe"], kind="mergesort")
    # for key in combined_both_dict.keys():
    #     combined_both_dict[key] = combined_both_dict[key][order]
    # combined_both_dict["left_positions"] = np.cumsum(
    #     np.concatenate(([0.0], combined_both_dict["prod"][:-1]))
    # ).astype(np.float64)


if __name__ == "__main__":
    synthesise_cost_land(
        quantity_cost_techs=snakemake.input.quantity_cost_techs,
        curve_data=snakemake.output.curve_data,
    )
