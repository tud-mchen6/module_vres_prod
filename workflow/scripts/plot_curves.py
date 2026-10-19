"""
This script takes the output vRES cost curve and land curve and plots
them with differentiated technology.
"""

import numpy as np
import matplotlib.pyplot as plt
import pyarrow.parquet as pq
import pycountry


def plot_curves(curve_data: str, cost_curve: str, land_curve: str):
    """

    Args:
        curve_data (str): path to the input curves data parquet file.
        cost_curve (str): path to the output cost curve plot file.
        land_curve (str): path to the output land curve plot file.
    """

    # Load the curves data
    curves = pq.ParquetFile(curve_data)
    dict_curves = {}
    for name in curves.schema_arrow.names:
        dict_curves[name] = curves.read(columns=[name])[name].to_numpy()

    # Get the country name
    shape = snakemake.wildcards.shape
    country_name = pycountry.countries.get(alpha_3=shape).name

    # Colors for each technology
    colors = {0: "yellow", 1: "lightblue", 2: "darkblue"}

    # Cumulative production on x-axis
    cum_prod = np.cumsum(dict_curves["prod"])

    # Plot the cost curve and the area below
    fig, ax = plt.subplots(figsize=(12, 6))
    # Plot the LCOE curve
    ax.plot(cum_prod, dict_curves["lcoe"], color="black", linewidth=0.8)
    # Fill the area below the curve, colored by technology
    for tech, color in colors.items():
        mask = dict_curves["tech_id"] == tech
        ax.fill_between(
            cum_prod,
            dict_curves["lcoe"],
            where=mask,
            color=color,
            alpha=0.3,
            interpolate=False,
            rasterized=True,
        )
    plt.xlabel("Cumulative Production (MWh)", fontsize=14)
    plt.ylabel("Levelised cost of electricity per MWh (EUR/MWh)", fontsize=14)
    plt.title(
        "Renewable electricity production cost curve of " + country_name, fontsize=16
    )
    plt.legend(
        handles=[
            plt.Line2D([0], [0], color="yellow", lw=4, label="Open field PV"),
            plt.Line2D([0], [0], color="lightblue", lw=4, label="Onshore Wind"),
            plt.Line2D([0], [0], color="darkblue", lw=4, label="Offshore Wind"),
        ],
        title="Technology",
    )
    plt.grid(alpha=0.3)
    plt.savefig(cost_curve)
    plt.close()

    # Plot the land curve
    land_cum = np.cumsum(dict_curves["area"])  # Unit: km2
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(
        np.cumsum(dict_curves["prod"]),  # Unit: MWh
        land_cum,  # Unit: km2
        color="green",
        linewidth=1,
    )
    ax.set_xlabel("Cumulative renewables production (MWh)", fontsize=14)
    ax.set_ylabel("Area (km²)", fontsize=14)
    ax.set_title("Land use curve in " + country_name, fontsize=16)
    ax.grid()
    plt.tight_layout()
    plt.savefig(land_curve, format="pdf")


if __name__ == "__main__":
    plot_curves(
        curve_data=snakemake.input.curve_data,
        cost_curve=snakemake.output.cost_curve,
        land_curve=snakemake.output.land_curve,
    )
