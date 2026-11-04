# Pollen

A workflow for building a global, pollen-observation-derived wetland database with no preset time-period limit. Wetland indicators must be calculated from observed pollen and aquatic/wetland-affiliated taxa, not from climate variables, methane inversions, OH assumptions, climate models, or pollen-based climate reconstructions.

## Data currently in the repository

- `data/noaa_paleo_study_search.json` is the NOAA Paleo Search study metadata response fetched by `scripts/fetch_noaa_paleo_search.py`.
- Metadata are useful for locating studies and associated files, but taxon observations are generally in the study's pollen data files.

## Build the site inventory

With Python 3, from the repository root run:

```bash
python3 scripts/build_inventory.py
```

This reads JSON files under `data/` and writes `data/study_inventory.csv`. You can specify other paths:

```bash
python3 scripts/build_inventory.py --data-dir data --output data/study_inventory.csv
```

The inventory includes study ID, site, coordinates, archive type, age bounds, reconstruction status, and discovered pollen-data URLs. The extractor tolerates common NOAA key-name variations. Verify the generated CSV against the source metadata before analysis: values that cannot be identified confidently are left blank, and reconstruction status is `UNKNOWN` unless the metadata explicitly says otherwise (or the data type clearly says reconstruction). Do not treat unknown status as observational.

## Selection rules

Exclude studies explicitly marked `reconstruction = Y`, including pollen-based climate reconstructions such as temperature reconstructions. Keep studies marked `reconstruction = N`, regardless of their age range; there is no preset temporal cutoff. Manually review `UNKNOWN` statuses and resolve them against NOAA study records before including a study. Retain age information as metadata and document the source age scale and any conversions, but do not use age to exclude studies.

## Taxon processing and wetland metric

NOAA pollen files can differ in delimiter, layout, counting units, age conventions, and taxonomic naming. Preserve each original downloaded file and document any transformations. Convert only identified observations into the agreed long-form structure:

```text
study_id,age_bp,taxon,value,latitude,longitude,archive_type
```

The initial wetland-indicator list is Cyperaceae, Sphagnum, Alnus, Salix, Isoetes, Myriophyllum, Potamogeton, Nymphaea, Nuphar, Sparganium, Utricularia, Pediastrum, and Botryococcus. Define and document how values from different source units are made comparable before aggregating them into a wetland-affinity index. Do not silently treat counts, percentages, and concentrations as equivalent, and do not infer missing taxa as zero.

## Current limitations

The inventory builder is a first-pass metadata extractor; it does not yet download pollen files, harmonize taxonomic synonyms, normalize pollen counts, or calculate the wetland index. Those steps require file-format inspection and explicit normalization decisions so that heterogeneous records are not misrepresented.
