"""This script resamples the atlases to a common shape and resolution."""

import click
import rioxarray as rxr
from rasterio.enums import Resampling


@click.command()
@click.argument("raster_path", type=str)
@click.argument("like_raster_path", type=str)
@click.argument("output_path", type=str)
def resample_atlas(
    raster_path: str,
    like_raster_path: str,
    output_path: str,  # , plot_path: str
):
    """Resample the atlas to a common shape and resolution.

    Args:
        raster_path (str): Path to the input raster file.
        like_raster_path (str): Path to the raster file to match the shape and resolution.
        output_path (str): Path to save the resampled raster file.
    """

    ds_atlas = rxr.open_rasterio(raster_path)
    like_raster = rxr.open_rasterio(like_raster_path)
    print("Atlas original resolution: " + str(ds_atlas.rio.resolution()))
    print("Target resolution: " + str(like_raster.rio.resolution()))
    resampled_atlas = ds_atlas.rio.reproject_match(
        like_raster, resampling=Resampling.average
    )

    print("Saving result to output path:", output_path)
    resampled_atlas.rio.to_raster(output_path)


if __name__ == "__main__":
    resample_atlas()
