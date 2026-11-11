"""This script uses the input of the atlases and area selection, cost parameters, 
to produce renewable yearly production potential of a given shape."""


TECH_TO_SOURCE = {
    "pv_open_field": "PV",
    "pv_rooftop": "PV",
    "wind_onshore": "WIND",
    "wind_offshore": "WIND",
}

wildcard_constraints:
    tech="pv_open_field|pv_rooftop|wind_onshore|wind_offshore",
    scenario="[^_]+",   # or list your scenario names explicitly

rule prod_quantity_cost:
    message:
        """
        Calculate the yearly production potential of each pixel and document the area used for such production.
        Also store the average LCOE of potential production in each pixel for each tech.
        Applicable: all types of PV and wind.
        """
    params:
        config=lambda wildcards: config["scenarios"][wildcards.scenario]["techs"].get(wildcards.tech, {}),
        overrides=lambda wildcards: config["scenarios"][wildcards.scenario].get("overrides", {}).get(wildcards.shape, {}).get(wildcards.tech, {}),
    input:
        area_potentials_path="<potentials>/{shape}/area_potential_{tech}.tif",
        resampled_path=lambda wc:
            f"<resources_scenarios>/resampled/{wc.shape}/"
            f"resampled_{TECH_TO_SOURCE[wc.tech]}OUT.tif",
    output:
        production_tech=temp("<resources_scenarios>/{shape}/{scenario}/quantity_cost_{tech}.nc"),
    conda:
        "../envs/module.yaml",
    log:
        "<logs>/{shape}/{scenario}/quantity_cost_{tech}.log",
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
            "<resources_scenarios>/{shape}/{scenario}/quantity_cost_{tech}.nc",
            shape=wildcards.shape,
            scenario=wildcards.scenario,
            tech=config["scenarios"][wildcards.scenario]["techs"].keys(),
        ),
    output:
        curve_data="<results>/{shape}/curves_data_prep_{scenario}.parquet",
    conda:
        "../envs/module.yaml",
    log:
        "<logs>/{shape}/synthesise_curves_{scenario}.log",
    script:
        "../scripts/synthesise_curves.py"


rule plot_curves:
    message:
        """
        Plot the cost curve and land curve for a given shape, combining several
        technologies.
        """
    input:
        curve_data="<results>/{shape}/curves_data_prep_{scenario}.parquet",
    output:
        cost_curve="<results>/{shape}/cost_curve_{scenario}.pdf",
        land_curve="<results>/{shape}/land_curve_{scenario}.pdf",
    log:
        "<logs>/{shape}/plot_curves_{scenario}.log",
    script:
        "../scripts/plot_curves.py"