#!/usr/bin/env python3
"""Build a reviewable site inventory from NOAA Paleo Search JSON metadata.

Usage: python3 scripts/build_inventory.py [--data-dir data] [--output data/study_inventory.csv]

The first-pass filter uses only the 0-120 ka age window and keeps broad wetland-
related metadata in review. It intentionally does not exclude studies solely
because NOAA labels them as reconstructions.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterator

FIELDS = [
    "study_id",
    "site_name",
    "latitude",
    "longitude",
    "archive_type",
    "oldest_age_bp",
    "youngest_age_bp",
    "age_overlap_0_120ka",
    "reconstruction",
    "wetland_proxy_signal",
    "selection_status",
    "pollen_file_url",
]
ALIASES = {
    "study_id": {"studyid", "noaastudyid", "studyidentifier", "xmlid"},
    "site_name": {"sitename", "site"},
    "latitude": {"latitude", "lat"},
    "longitude": {"longitude", "lon", "long"},
    "archive_type": {"archivetype", "archive", "archiveclass"},
    "oldest_age_bp": {"oldestagebp", "ageold", "oldestage", "maximumage", "maxage"},
    "youngest_age_bp": {"youngestagebp", "ageyoung", "youngestage", "minimumage", "minage"},
    "reconstruction": {"reconstruction", "isreconstruction", "climatereconstruction"},
}
WETLAND_KEYWORDS = {
    "wetland",
    "peat",
    "peatland",
    "bog",
    "fen",
    "marsh",
    "swamp",
    "mire",
    "palud",
    "aquatic",
    "cyperaceae",
    "sphagnum",
    "alnus",
    "salix",
    "isoetes",
    "myriophyllum",
    "potamogeton",
    "nymphaea",
    "nuphar",
    "sparganium",
    "utricularia",
    "pediastrum",
    "botryococcus",
}


def key_norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def walk(obj: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key_norm(key), value
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def first_value(obj: Any, aliases: set[str]) -> Any:
    for key, value in walk(obj):
        if key in aliases and value not in (None, "", [], {}):
            if isinstance(value, (str, int, float, bool)):
                return value
            if isinstance(value, dict):
                for nested_key in ("name", "value", "label", "text"):
                    if nested_key in value and isinstance(value[nested_key], (str, int, float, bool)):
                        return value[nested_key]
    return ""


def study_records(payload: Any) -> Iterator[dict[str, Any]]:
    """Find study objects in both NOAA's `study` and `studies` response shapes."""
    if isinstance(payload, list):
        for item in payload:
            yield from study_records(item)
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in {"study", "studies", "results", "records"} and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(value, (dict, list)):
                yield from study_records(value)


def text(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(text(item) for item in value if text(item))
    if isinstance(value, dict):
        for key in ("name", "value", "label", "text"):
            if key in value:
                return text(value[key])
        return ""
    return str(value).strip() if value is not None else ""


def number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value.replace(",", ""))
        return match.group(0) if match else ""
    return ""


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def age_overlap_0_120ka(oldest_bp: Any, youngest_bp: Any) -> str:
    oldest = as_float(oldest_bp)
    youngest = as_float(youngest_bp)

    if oldest is None and youngest is None:
        return "UNKNOWN"

    # NOAA study metadata may use `oldest_age_bp`/`youngest_age_bp` as values in years BP.
    # A record overlaps the window if its age range intersects [0, 120000].
    if oldest is not None and youngest is not None:
        if oldest >= 0 and youngest <= 120000:
            return "YES"
        if oldest <= 120000 and youngest >= 0:
            return "YES"
        return "NO"

    if youngest is not None:
        if 0 <= youngest <= 120000:
            return "YES"
        return "NO"

    if oldest is not None:
        if 0 <= oldest <= 120000:
            return "YES"
        return "NO"

    return "UNKNOWN"


def reconstruction_flag(study: dict[str, Any]) -> str:
    value = first_value(study, ALIASES["reconstruction"])
    normalized = key_norm(value)
    if normalized in {"n", "no", "false", "0", "notreconstruction", "observational"}:
        return "N"
    if normalized in {"y", "yes", "true", "1", "reconstruction", "climatereconstruction"}:
        return "Y"
    data_type = key_norm(first_value(study, {"datatype", "datatypename"}))
    if "recon" in data_type:
        return "Y"
    return "UNKNOWN"


def wetland_proxy_signal(study: dict[str, Any]) -> str:
    # Keep broad and inclusive: this is an initial, metadata-level clue rather than a final
    # wetland-extent determination. Positive signals are retained for review.
    texts: list[str] = []
    for key, value in walk(study):
        if isinstance(value, (str, int, float, bool)):
            texts.append(str(value))
    haystack = " ".join(texts).lower()

    if any(keyword in haystack for keyword in WETLAND_KEYWORDS):
        return "YES"
    return "UNKNOWN"


def selection_status(age_flag: str, wetland_flag: str) -> str:
    """First-pass screening: only the 0-120 ka window is hard-filtered."""
    if age_flag == "NO":
        return "EXCLUDE_NO_AGE_OVERLAP"
    if age_flag == "UNKNOWN":
        return "REVIEW_AGE_BOUNDARY"
    if wetland_flag == "UNKNOWN":
        return "REVIEW_NO_WETLAND_PROXY"
    return "INCLUDE_0_120KA"


def pollen_urls(study: dict[str, Any]) -> str:
    found: list[str] = []
    for _, value in walk(study):
        if not isinstance(value, str) or not value.lower().startswith(("http://", "https://")):
            continue
        candidate = value.strip()
        lower = candidate.lower()
        if ("pollen" in lower or "paleo" in lower) and re.search(r"\.(txt|tsv|csv)(?:[?#].*)?$", lower):
            if candidate not in found:
                found.append(candidate)
    return ";".join(found)


def row_for(study: dict[str, Any]) -> dict[str, str]:
    oldest = first_value(study, ALIASES["oldest_age_bp"])
    youngest = first_value(study, ALIASES["youngest_age_bp"])
    age_flag = age_overlap_0_120ka(oldest, youngest)
    wetland_flag = wetland_proxy_signal(study)
    flag = reconstruction_flag(study)
    return {
        "study_id": text(first_value(study, ALIASES["study_id"])),
        "site_name": text(first_value(study, ALIASES["site_name"])),
        "latitude": number(first_value(study, ALIASES["latitude"])),
        "longitude": number(first_value(study, ALIASES["longitude"])),
        "archive_type": text(first_value(study, ALIASES["archive_type"])),
        "oldest_age_bp": number(oldest),
        "youngest_age_bp": number(youngest),
        "age_overlap_0_120ka": age_flag,
        "reconstruction": flag,
        "wetland_proxy_signal": wetland_flag,
        "selection_status": selection_status(age_flag, wetland_flag),
        "pollen_file_url": pollen_urls(study),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Directory containing NOAA metadata JSON files")
    parser.add_argument("--output", type=Path, default=Path("data/study_inventory.csv"), help="Output CSV path")
    args = parser.parse_args()

    rows: dict[str, dict[str, str]] = {}
    for path in sorted(args.data_dir.rglob("*.json")):
        if path.resolve() == args.output.resolve():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Skipping {path}: {error}")
            continue
        for index, study in enumerate(study_records(payload)):
            row = row_for(study)
            key = row["study_id"] or f"{path.as_posix()}#{index}"
            rows[key] = row

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows.values())
    print(f"Wrote {len(rows)} studies to {args.output}")
    print("Selection statuses: INCLUDE_0_120KA, EXCLUDE_NO_AGE_OVERLAP, REVIEW_AGE_BOUNDARY, REVIEW_NO_WETLAND_PROXY.")


if __name__ == "__main__":
    main()

