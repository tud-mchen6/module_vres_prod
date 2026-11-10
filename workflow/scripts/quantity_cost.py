"""
This script uses assumed technology cost data, renewables density and discount rate
to calculate the cost of each pixel, then put the area, cost and production quantity
together in a netCDF file for the given technology.
"""

import xarray as xr
import rioxarray as rxr
import numpy as np
import glom


def flatten_with_pixel_id(input_raster):
    data = input_raster.values  # (y, x)
    valid_mask = ~np.isnan(data)

    pixel_ids = np.arange(data.size, dtype=np.int64).reshape(data.shape)

    return xr.DataArray(
        data[valid_mask], coords={"pixel_id": pixel_ids[valid_mask]}, dims=["pixel_id"]
    )


def quantity_cost_tech(
    config: dict,
    area_potentials_path: str,
    resampled_path: str,
    output_path: str,
    overrides: dict = None,
):
    """_summary_

    Args:
        density (float): MW/km2
        lifetime (int): year
        costs (dict): EUR/MW
        area_potentials_path (str): path to the input selected area raster file.
        resampled_path (str): path to the resampled capacity factor raster file.
        output_path (str): path to the output netCDF file.
    """

    # Get the tech name
    tech = snakemake.wildcards.tech
    # Get the area potentials
    area_potentials = rxr.open_rasterio(area_potentials_path)  # m2
    area_potentials = area_potentials.where(area_potentials > 0, np.nan)
    # If there is no area potential, directly return without any output
    shape = snakemake.wildcards.shape
    if area_potentials.notnull().sum().values == 0:
        print(
            f"No area potential for tech={tech}, country={shape}, output empty dataset."
        )
        quantity_cost = xr.Dataset({"area": [], "prod": [], "lcoe": []})
        quantity_cost.to_netcdf(output_path)
    # Load the capacity factor within the resampled input
    resampled = rxr.open_rasterio(resampled_path)
    # To slim down the calculation, mask out the pixels where area_potentials is nan
    # The atlas also has nan values from the original dataset
    mask = np.isfinite(area_potentials) & np.isfinite(resampled)
    resampled_masked = resampled.where(mask)
    area_potentials_masked = area_potentials.where(mask)
    # Flatten the raster to decrease the size
    area_potentials_flattened = flatten_with_pixel_id(area_potentials_masked)
    cf = flatten_with_pixel_id(resampled_masked)
    # For PV, cf is hour of full load per day, divide by 24 to get the capacity factor
    if "pv" in tech:
        cf = cf / 24

    # Get overrides if exist
    if overrides:
        config = glom.merge([config, overrides])
    capex = config["CAPEX"]
    opex = config["OPEX"]
    wacc = config["WACC"]
    density = config["density"]
    lifetime = config["lifetime"]

    # Calculate the yearly aggregated production
    # Assuming same production level for each year
    # area convert to km2; production unit is MWh
    yearly_prod = area_potentials_flattened * cf * density * 8760 * 1e-6

    # Calculate the rastered LCOE. Cost unit: EUR/MWh
    lcoe = (capex / (1 - (1 + wacc) ** (-lifetime)) * wacc + opex) / (cf * 8760)

    # Save to .nc
    # If the tech is offshore wind, it does not occupy land area, then make the
    # area variable values zero
    if tech == "wind_offshore":
        area_potentials_flattened.values[:] = 0
    # Downgrade the precision to float32 to save space
    area_potentials_flattened = area_potentials_flattened.astype("float32")
    area_potentials_flattened.attrs.pop("scale_factor", None)
    area_potentials_flattened.attrs.pop("add_offset", None)
    yearly_prod = yearly_prod.astype("float32")
    # TODO: clean the Attributes of yearly_prod and lcoe
    quantity_cost = xr.Dataset(
        {"area": area_potentials_flattened, "prod": yearly_prod, "lcoe": lcoe}
    )
    # add tech as a dimension, prepare for the synthesis
    quantity_cost = quantity_cost.assign_coords(tech=[tech])
    quantity_cost.to_netcdf(output_path)


if __name__ == "__main__":
    quantity_cost_tech(
        config=snakemake.params.config,
        area_potentials_path=snakemake.input.area_potentials_path,
        resampled_path=snakemake.input.resampled_path,
        output_path=snakemake.output.production_tech,
        overrides=snakemake.params.overrides,
    )
