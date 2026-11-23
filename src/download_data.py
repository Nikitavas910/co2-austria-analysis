"""Download the Our World in Data CO2 dataset (CC BY 4.0) into data/."""
import sys
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
OUT = Path(__file__).resolve().parents[1] / "data" / "owid-co2-data.csv"


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    print(f"Downloading {URL}")
    urllib.request.urlretrieve(URL, OUT)
    print(f"Saved {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
