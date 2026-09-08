"""
This script uses assumed technology cost data, renewables density and discount rate
to calculate the cost of each pixel, then put the area, cost and production quantity
together in a netCDF file for the given technology.
"""

import xarray as xr
import rioxarray as rxr
import numpy as np


def flatten_with_pixel_id(input_raster):
    pixel = input_raster.stack(pixel=("y", "x"))

    # Pixel IDs correspond directly to the flattened pixel position.
    pixel = pixel.assign_coords(
        pixel_id=("pixel", np.arange(pixel.sizes["pixel"], dtype=np.int64))
    )

    # Remove nodata pixels.
    pixel = pixel.where(pixel.notnull(), drop=True)

    return pixel.swap_dims({"pixel": "pixel_id"}).drop_vars(["pixel", "x", "y"])


def quantity_cost_tech(
    density: float,
    lifetime: int,
    costs: dict,
    area_potentials_path: str,
    resampled_path: str,
    output_path: str,
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

    # Calculate the yearly aggregated production
    # Assuming same production level for each year
    # area convert to km2; production unit is MWh
    yearly_prod = area_potentials_flattened * cf * density * 8760 * 1e-6

    # Calculate the rastered LCOE. Cost unit: EUR/MW
    lcoe = (
        costs["CAPEX"] / (1 - (1 + costs["WACC"]) ** (-lifetime)) * costs["WACC"]
        + costs["OPEX"]
    ) / (cf * 8760)

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
    quantity_cost = quantity_cost.rename_dims({"band": "tech"})
    quantity_cost = quantity_cost.assign_coords(tech=[tech])
    quantity_cost = quantity_cost.drop_vars("band")
    quantity_cost.to_netcdf(output_path)


if __name__ == "__main__":
    quantity_cost_tech(
        density=snakemake.params.density,
        lifetime=snakemake.params.lifetime,
        costs=snakemake.params.costs,
        area_potentials_path=snakemake.input.area_potentials_path,
        resampled_path=snakemake.input.resampled_path,
        output_path=snakemake.output.production_tech,
    )
