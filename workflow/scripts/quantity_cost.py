"""
This script uses assumed technology cost data, renewables density and discount rate
to calculate the cost of each pixel, then put the area, cost and production quantity
together in a netCDF file for the given technology.
"""

import xarray as xr
import rioxarray as rxr
import numpy as np


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
        density (float): MW/m2
        lifetime (int): year
        costs (dict): EUR/MW
        area_potentials_path (str): path to the input selected area raster file.
        resampled_path (str): path to the resampled capacity factor raster file.
        output_path (str): path to the output netCDF file.
    """

    # Get the tech name
    tech = snakemake.wildcards.tech
    # Get the area potentials
    area_potentials = rxr.open_rasterio(area_potentials_path)
    # Load the capacity factor within the resampled input
    resampled = rxr.open_rasterio(resampled_path)

    # Calculate the yearly aggregated production
    # Assuming same production level for each year

    # Reindex to keep the original coordinates, otherwise there will be
    # missing pixels in the result
    cf = resampled.reindex(
        y=area_potentials.y, x=area_potentials.x, method="nearest", tolerance=1e-6
    )
    # area convert to km2; production unit is MWh
    yearly_prod = area_potentials * cf * density * 8760 * 1e-6
    # Since area_potentials have -1 values, get rid of them
    yearly_prod = yearly_prod.where(yearly_prod > 0, np.nan)

    # Calculate the rastered LCOE
    lcoe = (
        costs["CAPEX"] / (1 - (1 + costs["WACC"]) ** (-lifetime)) * costs["WACC"]
        + costs["OPEX"]
    ) / (cf * 8760)
    # Make the not-eligible areas also without lcoe data
    lcoe = lcoe.where(yearly_prod > 0, np.nan)

    # Save to .nc
    quantity_cost = xr.Dataset(
        {"area": area_potentials, "prod": yearly_prod, "lcoe": lcoe}
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
