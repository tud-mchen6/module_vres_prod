"""Rules to clip and resample the downloaded atlases."""

# The wind rules are not tested yet.
# Ideally one rule for clip, and one rule for resample would be less verbose, but requires some complex wildcards, thus discarded.


rule clip_solar_atlas:
    message:
        "Clip the downloaded solar atlas to given shapes."
    input:
        raster="<resources>/automatic/global/PVOUT.tif",
        like_raster="<potentials>/shapes/{shape}/area_potential_pv_open_field.tif",
    output:
        path=temp("<resources>/automatic/cutout/{shape}/clipped_PVOUT.tif"),
    log:
        "<logs>/{shape}/clip_solar_atlas.log",
    wrapper:
        "v9.0.0/geo/rasterio/clip"


rule clip_wind_atlas:
    message:
        "Clip the downloaded wind atlas to given shapes."
    input:
        raster="<resources>/automatic/global/WINDOUT.tif",
        like_raster="<potentials>/shapes/{shape}/area_potential_wind_onshore.tif",
    output:
        path="<resources>/automatic/cutout/{shape}/clipped_WINDOUT.tif",
    log:
        "<logs>/{shape}/clip_wind_atlas.log",
    wrapper:
        "v9.0.0/geo/rasterio/clip"


rule resample_solar_atlas:
    message:
        "Resample the clipped atlas to the given resolution."
    input:
        raster="<resources>/automatic/cutout/{shape}/clipped_PVOUT.tif",
        like_raster="<potentials>/shapes/{shape}/area_potential_pv_open_field.tif",
        script=workflow.source_path("../scripts/resample_atlas.py"),
    output:
        path="<resources>/automatic/resampled/{shape}/resampled_PVOUT.tif",
    log:
        "<logs>/{shape}/resample_solar_atlas.log",
    shell:
        """
        python {input.script:q} {input.raster} {input.like_raster} {output.path} 2> {log:q}
        """


rule resample_wind_atlas:
    message:
        "Resample the clipped atlas to the given resolution."
    input:
        raster="<resources>/automatic/cutout/{shape}/clipped_WINDOUT.tif",
        like_raster="<potentials>/shapes/{shape}/area_potential_wind_onshore.tif",
        script=workflow.source_path("../scripts/resample_atlas.py"),
    output:
        path="<resources>/automatic/resampled/{shape}/resampled_WINDOUT.tif",
    log:
        "<logs>/{shape}/resample_wind_atlas.log",
    shell:
        """
        python {input.script:q} {input.raster} {input.like_raster} {output.path} 2> {log:q}
        """