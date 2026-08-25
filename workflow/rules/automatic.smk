"""Rules to used to download, unzip and get the TIFF wind and solar atlases files."""


# rule download_wind_atlas:
#     message:
#         "Download the Wind Atlas data."
#     params:
#         url=internal["resources"]["automatic"]["wind_atlas"],
#     output:
#         path="resources/automatic/global/WINDOUT.tif",
#     log:
#         "logs/download_wind_atlas.log",
#     shell:
#         """
#         wget --user-agent="Mozilla/5.0" \
#             --tries=inf \
#             --continue \
#             {params.url:q} \
#             -O {output:q}
#         """


