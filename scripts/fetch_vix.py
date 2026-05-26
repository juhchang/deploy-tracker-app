"""
Fetch current VIX and 30-day history from Yahoo Finance.
Writes: output/vix.json
"""

import json, os
import yfinance as yf
from datetime import datetime


def main():
    print("Fetching VIX (^VIX) ...", end=" ", flush=True)
    raw = yf.download("^VIX", period="3mo", progress=False, auto_adjust=True)
    closes = raw["Close"].squeeze()
    closes.index = closes.index.tz_localize(None)
    print(f"OK  ({len(closes)} trading days)")

    history = [
        {"date": dt.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
        for dt, v in closes.items()
    ]

    current       = round(float(closes.iloc[-1]), 2)
    previous_close = round(float(closes.iloc[-2]), 2) if len(closes) > 1 else None
    history_30d   = history[-30:]

    out = {
        "generated":      datetime.now().isoformat(),
        "vix":            current,
        "previous_close": previous_close,
        "history":        history_30d,
    }

    os.makedirs("output", exist_ok=True)
    with open("output/vix.json", "w") as f:
        json.dump(out, f, indent=2)

    chg = current - previous_close if previous_close else 0
    print(f"VIX: {current:.2f}  ({chg:+.2f} vs prev close)")
    print("Wrote output/vix.json")


if __name__ == "__main__":
    main()
