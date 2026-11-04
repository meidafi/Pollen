import json
from pathlib import Path
from urllib.request import urlopen

URL = "https://www.ncei.noaa.gov/access/paleo-search/study/search.json?dataPublisher=NOAA&dataTypeId=16&headersOnly=true"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "noaa_paleo_study_search.json"


def main() -> None:
    with urlopen(URL) as response:
        payload = response.read().decode("utf-8")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(payload, encoding="utf-8")
    print(f"Wrote NOAA study metadata to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
