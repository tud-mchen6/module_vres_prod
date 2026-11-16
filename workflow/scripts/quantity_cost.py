"""
This script uses assumed technology cost data, renewables density and discount rate
to calculate the cost of each pixel, then stores the area, production quantity and
cost of every valid pixel of the given technology in an uncompressed .npz file.

Performance notes (vs. the previous xarray/netCDF version):
- Rasters are read with rasterio directly into float32 numpy arrays. No xarray
  objects, so no coordinate alignment and no full-raster float64 copies.
- One boolean validity mask is built once and turned into a flat index array.
  Everything after that only touches the (much smaller) set of valid pixels.
- The output is a plain uncompressed .npz (temp file, written once and read once).
  This avoids zlib compression and decompression and netCDF fancy-indexing costs.
"""

import glom
import numpy as np
import rasterio

# Hours per year, used for production and LCOE
HOURS_PER_YEAR = 8760


def read_band_as_float32(path: str):
    """Read band 1 of a raster as float32, with the nodata value replaced by NaN.

    Returns the 2D array plus the grid information (shape and affine transform).
    Shape and transform only describe the rectangular pixel grid (size, corner
    position, pixel size), not the country border. The border is encoded in
    the pixel values (nodata/NaN/0 outside), which the validity mask handles.
    The grid info is used to check that the area and atlas rasters line up
    pixel by pixel.
    """
    with rasterio.open(path) as src:
        data = src.read(1, out_dtype="float32")
        nodata = src.nodata
        grid_shape = (src.height, src.width)
        transform = src.transform
    # rasterio does not mask nodata by itself. Convert it to NaN so that one
    # isfinite() check covers both "real" NaNs and nodata values.
    if nodata is not None and not np.isnan(nodata):
        data[data == np.float32(nodata)] = np.nan
    return data, grid_shape, transform


def quantity_cost_tech(
    config: dict,
    area_potentials_path: str,
    resampled_path: str,
    output_path: str,
    overrides: dict = None,
):
    """Calculate yearly production, LCOE and land area of every valid pixel.

    Args:
        config (dict): tech parameters (density [MW/km2], lifetime [year],
            CAPEX [EUR/MW], OPEX [EUR/MW/year], WACC [-]).
        area_potentials_path (str): path to the input selected area raster file (m2).
        resampled_path (str): path to the resampled capacity factor raster file.
        output_path (str): path to the output .npz file.
        overrides (dict): shape-specific overrides of config.
    """

    # Get the tech and shape name
    tech = snakemake.wildcards.tech
    shape = snakemake.wildcards.shape

    # ------------------------------------------------------------------
    # 1. Read both rasters as plain float32 numpy arrays
    # ------------------------------------------------------------------
    area_raw, area_shape, area_transform = read_band_as_float32(area_potentials_path)
    cf_raw, cf_shape, cf_transform = read_band_as_float32(resampled_path)

    # The previous version relied on xarray aligning the x/y coordinates
    # (an inner join on float coordinates). Here we work on raw arrays, so
    # the two rasters must be on exactly the same grid: pixel (row, col) must
    # be the same location in both. resample_atlas.py uses reproject_match
    # against the area raster, so this should always hold. Fail loudly if not.
    if area_shape != cf_shape or not area_transform.almost_equals(cf_transform):
        raise ValueError(
            f"Grid mismatch for tech={tech}, shape={shape}: "
            f"area raster {area_shape} {area_transform} vs "
            f"atlas raster {cf_shape} {cf_transform}"
        )

    # ------------------------------------------------------------------
    # 2. One validity mask, one flat index array
    # ------------------------------------------------------------------
    # Valid pixel = positive available area AND a finite capacity factor.
    # NaN comparisons are False, so (area_raw > 0) also excludes NaN/nodata area.
    valid = (area_raw > 0) & np.isfinite(cf_raw)
    # Flat (row-major) pixel index, which is the same pixel_id definition as before.
    # flatnonzero returns sorted unique ids, which synthesise_curves.py relies on.
    pixel_id = np.flatnonzero(valid)
    # uint32 halves the id column; fall back to int64 for huge rasters.
    if area_raw.size < np.iinfo(np.uint32).max:
        pixel_id = pixel_id.astype(np.uint32)

    if pixel_id.size == 0:
        # Intentionally no early return: the code below then naturally writes
        # empty arrays, which synthesise_curves.py skips.
        print(
            f"No area potential for tech={tech}, country={shape}, output empty dataset."
        )

    # Pull out only the valid pixels, then drop the full rasters to free memory
    area = area_raw.ravel()[pixel_id]  # m2
    cf = cf_raw.ravel()[pixel_id]
    del area_raw, cf_raw, valid

    # For PV, the atlas value is hours of full load per day; divide by 24 to get
    # the capacity factor
    if "pv" in tech:
        cf = cf / np.float32(24)

    # ------------------------------------------------------------------
    # 3. Production and LCOE on the compact arrays
    # ------------------------------------------------------------------
    # Get overrides if exist
    if overrides:
        config = glom.merge([config, overrides])
    capex = config["CAPEX"]
    opex = config["OPEX"]
    wacc = config["WACC"]
    density = config["density"]
    lifetime = config["lifetime"]

    # Yearly production (MWh), assuming the same production level every year.
    # Area is converted from m2 to km2 (1e-6). The scalar factor is computed
    # in Python float first so that the array stays float32.
    prod = area * cf * np.float32(density * HOURS_PER_YEAR * 1e-6)

    # LCOE (EUR/MWh): annualised CAPEX (capital recovery factor) plus OPEX,
    # divided by yearly full-load hours. Pixels with cf == 0 get inf; they are
    # filtered out in synthesise_curves.py.
    annual_cost = capex / (1 - (1 + wacc) ** (-lifetime)) * wacc + opex
    with np.errstate(divide="ignore"):
        lcoe = np.float32(annual_cost) / (cf * np.float32(HOURS_PER_YEAR))

    # Offshore wind does not occupy land, so its land area is zero
    if tech == "wind_offshore":
        area[:] = 0

    # ------------------------------------------------------------------
    # 4. Save as uncompressed .npz (temp file, read once by synthesise_curves.py)
    # ------------------------------------------------------------------
    # grid_shape and transform are stored so that synthesise_curves.py can check
    # that pixel_ids of different techs refer to the same grid before matching them.
    np.savez(
        output_path,
        pixel_id=pixel_id,
        area=area.astype(np.float32, copy=False),
        prod=prod.astype(np.float32, copy=False),
        lcoe=lcoe.astype(np.float32, copy=False),
        grid_shape=np.asarray(area_shape, dtype=np.int64),
        transform=np.asarray(tuple(area_transform)[:6], dtype=np.float64),
    )


if __name__ == "__main__":
    quantity_cost_tech(
        config=snakemake.params.config,
        area_potentials_path=snakemake.input.area_potentials_path,
        resampled_path=snakemake.input.resampled_path,
        output_path=snakemake.output.production_tech,
        overrides=snakemake.params.overrides,
    )
