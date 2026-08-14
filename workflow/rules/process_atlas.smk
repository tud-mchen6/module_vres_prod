"""Rules to clip and resample the downloaded atlases."""


rule clip_solar_atlas:
    message:
        "Clip the downloaded atlas to given shapes."
    input:
        raster="resources/automatic/global/PVOUT.tif",
        like_raster="resources/user/shapes/{shape}/area_potential_pv_open_field.tif",
    output:
        path="resources/automatic/cutout/{shape}/sub_PVOUT.tif",
    log:
        "logs/{shape}/clip_solar_atlas.log",
    wrapper:
        "v9.0.0/geo/rasterio/clip"


rule resample_solar_atlas:
    message:
        "Resample the clipped atlas to the given resolution."
    input:
        raster="resources/automatic/cutout/{shape}/sub_PVOUT.tif",
        like_raster="resources/user/shapes/{shape}/area_potential_pv_open_field.tif",
        script=workflow.source_path("../scripts/resample_atlas.py"),
    output:
        path="resources/automatic/resampled/{shape}/resampled_PVOUT.tif",
    log:
        "logs/{shape}/resample_solar_atlas.log",
    shell:
        """
        python {input.script:q} {input.raster} {input.like_raster} {output.path} 2> {log:q}
        """
