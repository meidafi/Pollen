#!/usr/bin/env python3
"""Build a reviewable site inventory from NOAA Paleo Search JSON metadata.

Usage: python3 scripts/build_inventory.py [--data-dir data] [--output data/study_inventory.csv]

The script intentionally marks reconstruction status as UNKNOWN when the source
metadata does not explicitly identify it. It does not infer observational status
from a study title or assume that a missing flag means "N".
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
    "reconstruction",
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
                    if nested_key in value and isinstance(value[nested_key], (str, int, float)):
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


def reconstruction_flag(study: dict[str, Any]) -> str:
    value = first_value(study, ALIASES["reconstruction"])
    normalized = key_norm(value)
    if normalized in {"n", "no", "false", "0", "notreconstruction", "observational"}:
        return "N"
    if normalized in {"y", "yes", "true", "1", "reconstruction", "climatereconstruction"}:
        return "Y"
    # NOAA's data type can identify climate reconstructions, but not other types
    # as observations; keep all other cases for explicit review.
    data_type = key_norm(first_value(study, {"datatype", "datatypename"}))
    if "recon" in data_type:
        return "Y"
    return "UNKNOWN"


def selection_status(flag: str) -> str:
    """Apply study-selection rules without excluding any age range."""
    if flag == "Y":
        return "EXCLUDE_RECONSTRUCTION"
    if flag == "N":
        return "INCLUDE"
    return "REVIEW_UNKNOWN"


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
    flag = reconstruction_flag(study)
    return {
        "study_id": text(first_value(study, ALIASES["study_id"])),
        "site_name": text(first_value(study, ALIASES["site_name"])),
        "latitude": number(first_value(study, ALIASES["latitude"])),
        "longitude": number(first_value(study, ALIASES["longitude"])),
        "archive_type": text(first_value(study, ALIASES["archive_type"])),
        "oldest_age_bp": number(first_value(study, ALIASES["oldest_age_bp"])),
        "youngest_age_bp": number(first_value(study, ALIASES["youngest_age_bp"])),
        "reconstruction": flag,
        "selection_status": selection_status(flag),
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
            # NOAAStudyId is preferred; path and index keep unidentified records distinct.
            key = row["study_id"] or f"{path.as_posix()}#{index}"
            rows[key] = row

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows.values())
    print(f"Wrote {len(rows)} studies to {args.output}")
    print("Selection status: INCLUDE for reconstruction=N, EXCLUDE_RECONSTRUCTION for Y, and REVIEW_UNKNOWN otherwise.")
    print("Age bounds are retained as metadata; no temporal cutoff is applied.")


if __name__ == "__main__":
    main()
