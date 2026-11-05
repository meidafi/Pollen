#!/usr/bin/env python3
"""Filter wetland evidence to lake/peatland contexts and write a final analysis table.

This script:
1. Reads the normalized wetland evidence CSV.
2. Keeps only strong wetland indicator taxa and records with likely lake/peatland context.
3. Normalizes age columns to a single `age_calBP` field when possible.
4. Writes a final summary table for site-level wetland review and analysis.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

INPUT = Path("data/wetland_candidates.csv")
OUTPUT = Path("data/wetland_site_summary.csv")

STRONG = {
    "cyperaceae",
    "sphagnum",
    "isoetes",
    "myriophyllum",
    "potamogeton",
    "nymphaea",
    "nuphar",
    "sparganium",
    "utricularia",
    "pediastrum",
    "botryococcus",
    "typha",
}

# Site names and file names that indicate non-wetland or marine records to remove.
EXCLUDE_CONTEXT = [
    "odp",
    "ocean",
    "marine",
    "paleosol",
    "franklin",
    "kotzebue",
    "deep sea",
]

# Common lake or peatland context labels. This is intentionally conservative.
KEEP_CONTEXT = [
    "lake",
    "pond",
    "peatland",
    "basin",
    "wetland",
    "bog",
    "fen",
    "marsh",
]


def normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def age_to_cal_bp(value: object) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_site_type(source_file: str, study_id: str, site_name: str | None = None) -> str:
    text = " ".join(
        [
            str(source_file or "").lower(),
            str(study_id or "").lower(),
            str(site_name or "").lower(),
        ]
    )

    if any(token in text for token in EXCLUDE_CONTEXT):
        return "exclude"

    if any(token in text for token in KEEP_CONTEXT):
        return "lake_or_peatland"

    return "review"


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT}")

    df = pd.read_csv(INPUT)
    if df.empty:
        print("No normalized evidence rows found.")
        return

    # Preserve only the strong wetland indicators for the summary table.
    df = df[df["taxon"].map(lambda x: str(x).lower() in STRONG)].copy()

    # Add a site-context label using study/site/file names.
    if "source_file" not in df.columns:
        raise KeyError("Input file does not contain 'source_file'.")
    if "study_id" not in df.columns:
        raise KeyError("Input file does not contain 'study_id'.")

    df["site_context"] = df.apply(
        lambda r: infer_site_type(
            str(r.get("source_file", "")),
            str(r.get("study_id", "")),
            r.get("site_name"),
        ),
        axis=1,
    )

    # Filter out known non-wetland or marine contexts.
    df = df[df["site_context"] != "exclude"].copy()

    # Age normalization: keep original numeric age if already cal BP-like.
    # If the source already uses a cal BP column, keep it. Otherwise leave as-is.
    age_values = []
    for value in df.get("age_calBP", pd.Series(dtype="float64")):
        age_values.append(age_to_cal_bp(value))
    df["age_calBP_clean"] = age_values

    # Final formatting for analysis.
    columns = [
        "study_id",
        "taxon",
        "age_calBP_clean",
        "value",
        "wetland_indicator_strength",
        "source_file",
        "site_context",
    ]
    final = df[columns].copy()
    final = final.rename(columns={"age_calBP_clean": "age_calBP"})

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT, index=False)

    print(final.head().to_string(index=False))
    print(f"\nRows: {len(final)}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
