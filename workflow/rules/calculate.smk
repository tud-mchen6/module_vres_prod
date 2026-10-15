"""This script uses the input of the atlases and area selection, cost parameters, 
to produce renewable yearly production potential of a given shape."""


TECH_TO_SOURCE = {
    "pv_open_field": "PV",
    "pv_rooftop": "PV",
    "wind_onshore": "WIND",
    "wind_offshore": "WIND",
}


rule prod_quantity_cost:
    message:
        """
        Calculate the yearly production potential of each pixel and document the area used for such production.
        Also store the average LCOE of potential production in each pixel for each tech.
        Applicable: all types of PV and wind.
        """
    params:
        density=lambda wildcards: config["techs"][f"{wildcards.tech}"]["density"],
        lifetime=lambda wildcards: config["techs"][f"{wildcards.tech}"]["lifetime"],
        costs=lambda wildcards: config["techs"][f"{wildcards.tech}"]["costs"],
    input:
        area_potentials_path="<potentials>/{shape}/area_potential_{tech}.tif",
        resampled_path=lambda wc:
            f"<resources_scenarios>/automatic/resampled/{wc.shape}/"
            f"resampled_{TECH_TO_SOURCE[wc.tech]}OUT.tif",
    output:
        production_tech="<resources_scenarios>/automatic/resampled/{shape}/quantity_cost_{tech}.nc",
    log:
        "<logs>/{shape}/quantity_cost_{tech}.log",
    script:
        "../scripts/quantity_cost.py"



rule synthesise_cost_land:
    message:
        """
        Get the synthesized cost curve and land curve for a given shape, combining several
        technologies.
        """
    input:
        quantity_cost_techs=lambda wildcards: expand(
            "<resources_scenarios>/automatic/resampled/{shape}/quantity_cost_{tech}.nc",
            shape=wildcards.shape,
            tech=config["techs"].keys(),
        ),
    output:
        curve_data="<results>/{shape}/curves_data_prep.parquet",
    log:
        "<logs>/{shape}/synthesise_curves.log",
    script:
        "../scripts/synthesise_curves.py"


rule plot_curves:
    message:
        """
        Plot the cost curve and land curve for a given shape, combining several
        technologies.
        """
    input:
        curve_data="<results>/{shape}/curves_data_prep.parquet",
    output:
        cost_curve="<results>/{shape}/cost_curve.pdf",
        land_curve="<results>/{shape}/land_curve.pdf",
    log:
        "<logs>/{shape}/plot_curves.log",
    script:
        "../scripts/plot_curves.py"