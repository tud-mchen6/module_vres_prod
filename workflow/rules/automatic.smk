"""Rules to used to download, unzip and get the TIFF wind and solar atlases files."""


rule dummy_download:
    message:
        "Download the Modelblocks README file."
    params:
        url=internal["resources"]["automatic"]["dummy_readme"],
    output:
        readme="<resources>/automatic/dummy_readme.md",
    log:
        "<logs>/dummy_download.log",
    conda:
        "../envs/module.yaml"
    shell:
        'curl -sSLo {output.readme} "{params.url}"'
