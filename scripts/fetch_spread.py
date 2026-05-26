"""
Fetch HY OAS spread and 2s10s yield curve from FRED API.
Requires FRED_API_KEY in .env — free at fred.stlouisfed.org/docs/api/api_key.html

Writes: output/spread_data.json
"""

import os, json, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FRED_KEY = os.getenv("FRED_API_KEY", "")
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred(series_id, limit=60):
    if not FRED_KEY or FRED_KEY == "your_key_here":
        raise RuntimeError("FRED_API_KEY not set in .env")
    params = {
        "series_id":  series_id,
        "api_key":    FRED_KEY,
        "file_type":  "json",
        "sort_order": "desc",
        "limit":      limit,
    }
    r = requests.get(FRED_URL, params=params, timeout=15)
    r.raise_for_status()
    return [
        {"date": o["date"], "value": float(o["value"])}
        for o in r.json()["observations"]
        if o["value"] != "."
    ]


def main():
    print("Fetching HY OAS (BAMLH0A0HYM2) ...", end=" ", flush=True)
    hy_raw = fetch_fred("BAMLH0A0HYM2", limit=60)
    print(f"OK  ({hy_raw[0]['date']})")

    print("Fetching 2s10s curve (T10Y2Y)    ...", end=" ", flush=True)
    curve_raw = fetch_fred("T10Y2Y", limit=60)
    print(f"OK  ({curve_raw[0]['date']})")

    # FRED stores HY OAS as percent (4.87 = 487 bps) — convert to bps
    hy_current  = hy_raw[0]["value"] * 100
    hy_month_ago = hy_raw[min(21, len(hy_raw) - 1)]["value"] * 100
    hy_history  = [round(d["value"] * 100, 1) for d in reversed(hy_raw[:30])]

    # 2s10s already in percent (0.18 = 0.18%)
    curve_current = curve_raw[0]["value"]
    curve_history = [round(d["value"], 3) for d in reversed(curve_raw[:30])]

    out = {
        "generated": datetime.now().isoformat(),
        "hy": {
            "value":      round(hy_current, 1),
            "delta_30d":  round(hy_current - hy_month_ago, 1),
            "history_30d": hy_history,
        },
        "curve": {
            "value":      round(curve_current, 3),
            "history_30d": curve_history,
        },
    }

    os.makedirs("output", exist_ok=True)
    with open("output/spread_data.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"HY OAS : {out['hy']['value']:.1f} bps  (30d delta: {out['hy']['delta_30d']:+.1f} bps)")
    print(f"2s10s  : {out['curve']['value']:+.3f}%")
    print("Wrote output/spread_data.json")


if __name__ == "__main__":
    main()
