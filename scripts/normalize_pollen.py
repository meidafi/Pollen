#!/usr/bin/env python3
"""Normalize reviewed NOAA pollen tables into a common wetland-evidence table.

This script intentionally does not assign a final wetland classification. It
keeps only older NOAA pollen tables with likely wetland indicators, preserves
source IDs and taxon names, and writes a single long-format evidence table.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

PROCESSED = Path("data/processed_reviewed")
OUTPUT = Path("data/wetland_candidates.csv")

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

ALIASES = {
    "cyperaceae": {"cyperaceae", "cypera", "cyperacae", "cyperac", "cyp"},
    "sphagnum": {"sphagnum", "sphagn"},
    "isoetes": {"isoetes"},
    "myriophyllum": {"myriophyllum", "myrioph"},
    "potamogeton": {"potamogeton"},
    "nymphaea": {"nymphaea", "nymph"},
    "nuphar": {"nuphar"},
    "sparganium": {"sparganium", "spargan", "sparg"},
    "utricularia": {"utricularia", "utric"},
    "pediastrum": {"pediastrum", "pediast"},
    "botryococcus": {"botryococcus", "botryoco", "botyrococus"},
    "typha": {"typha"},
}

EXCLUDE_PATTERNS = [
    "odp",
    "ew9504",
    "franklin",
    "kotzebue",
    "paleosol",
    "marine",
]


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def infer_taxon(column_name: str):
    name = normalize(column_name)
    for taxon, aliases in ALIASES.items():
        if name in aliases:
            return taxon
    return None


def main() -> None:
    records = []

    for path in sorted(PROCESSED.glob("*.csv")):
        name = path.name.lower()
        if any(pattern in name for pattern in EXCLUDE_PATTERNS):
            continue

        try:
            df = pd.read_csv(path)
        except Exception:
            continue

        if df.empty:
            continue

        age_cols = [
            c for c in df.columns if re.search(r"age|year|yrbp|calbp", str(c), flags=re.I)
        ]
        if not age_cols:
            continue

        for column in df.columns:
            taxon = infer_taxon(column)
            if taxon is None:
                continue

            sub = df[[age_cols[0], column]].copy()
            sub.columns = ["age_calBP", "value"]
            sub["taxon"] = taxon
            sub["source_file"] = str(path)
            sub["study_id"] = path.name.split("_", 1)[0]
            records.append(sub)

    if not records:
        print("No wetland candidates found.")
        return

    out = pd.concat(records, ignore_index=True)
    out = out.dropna(subset=["value"]).copy()
    out["wetland_indicator_strength"] = out["taxon"].map(
        lambda t: "strong" if t in STRONG else "supporting"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)

    print(out.head().to_string(index=False))
    print(f"\nRows: {len(out)}")
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
