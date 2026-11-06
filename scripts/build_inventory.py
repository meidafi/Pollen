# Pollen

A workflow for building a global, pollen-observation-derived wetland database with no preset time-period limit.

The broad first-pass screen is intentionally inclusive:
- Keep studies whose age range overlaps 0-120 ka BP.
- Keep reconstruction-labeled studies in review rather than excluding them automatically.
- Record a wetland-proxy signal from study metadata, but do not treat metadata alone as final evidence of wetland extent.

## Data currently in the repository

- `data/noaa_paleo_study_search.json` is the NOAA Paleo Search study metadata response fetched by `scripts/fetch_noaa_paleo_search.py`.
- Metadata are useful for locating studies and associated files, but taxon observations are generally in the study's pollen data files.

## Build the site inventory

With Python 3, from the repository root run:

```bash
python3 scripts/build_inventory.py
```

This reads JSON files under `data/` and writes `data/study_inventory.csv`.

The inventory includes study ID, site, coordinates, archive type, age bounds, age-window overlap, reconstruction status, a broad wetland-proxy signal, a selection status, and discovered pollen-data URLs.

## First-pass selection rules

The generated `selection_status` column applies these rules:
- `EXCLUDE_NO_AGE_OVERLAP` when age range does not intersect 0-120 ka BP.
- `REVIEW_AGE_BOUNDARY` when age metadata is missing or ambiguous.
- `REVIEW_NO_WETLAND_PROXY` when age is valid but wetland-affiliated metadata is not obvious.
- `INCLUDE_0_120KA` when age overlaps and wetland metadata is present.

This is intentionally broad; later passes can remove records without wetland-specific indicators.

## Wetland indicator list

The initial wetland-indicator list is Cyperaceae, Sphagnum, Alnus, Salix, Isoetes, Myriophyllum, Potamogeton, Nymphaea, Nuphar, Sparganium, Utricularia, Pediastrum, and Botryococcus.

## Current limitations

The inventory builder is a first-pass metadata extractor; it does not yet download pollen files, harmonize taxonomic synonyms, normalize pollen counts, or calculate the wetland index.

