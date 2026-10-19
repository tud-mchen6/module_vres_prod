# Home

Welcome to the documentation of the `vres_prod` data module!
Please consult the [specification guidelines](./specification.md) and the [`clio` documentation](https://clio.readthedocs.io/) for more information.


### TODO
1. Downloading wind and solar atlas is still manual. The solar atlas gives hours of full load per day, while the wind atlas directly gives the yearly capacity factor. Need to double check the type of data downloaded and keep that updated in the code accordingly.
2. Regarding land use overlap of two technologies: it will result in situations where the land curve starts with a flat zero part in some countries (e.g. Albania), if the cheapest tech happens to occupy less land on the pixel it is in. If we cut the land curve somewhere before the other tech is deployed, this is an error. Can this be done in a smarter way? Maybe assign the land not in terms of area large/small, but in terms of lcoe?
3. Now that area_potential outputs are under specific geo_boundaries and area_potentials scenarios, I have to clip the solar atlas for a certain shape each time I introduce a new area_potentials scenario. But this is just the same shape. Ideally I only need to clip it once and this clipped version can be used for all scenarios of area_potential tifs. Snakemake rules make it a bit difficult though, given that input and output wildcards have to match.