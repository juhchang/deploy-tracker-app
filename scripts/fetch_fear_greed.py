import requests
import json
import os
from datetime import datetime

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def main():
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    fg = data["fear_and_greed"]
    out = {
        "score": round(float(fg["score"]), 1),
        "rating": fg["rating"],
        "timestamp": fg.get("timestamp", ""),
        "previous_close": fg.get("previous_close"),
        "previous_1_week": fg.get("previous_1_week"),
        "previous_1_month": fg.get("previous_1_month"),
        "previous_1_year": fg.get("previous_1_year"),
        "generated": datetime.now().isoformat(),
    }

    os.makedirs("output", exist_ok=True)
    with open("output/fear_greed.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"Fear & Greed: {out['score']:.0f} — {out['rating']}")
    print("Wrote output/fear_greed.json")


if __name__ == "__main__":
    main()
