"""
Fetch current VIX and 30-day history from Yahoo Finance.
Writes: output/vix.json
"""

import json, os, sys
import yfinance as yf
from datetime import datetime


def fetch_closes():
    # Try yf.download first, fall back to Ticker.history if empty
    raw = yf.download("^VIX", period="3mo", progress=False, auto_adjust=True)
    closes = raw["Close"].squeeze() if not raw.empty else None

    if closes is None or closes.empty:
        print("yf.download returned empty — trying Ticker.history ...", end=" ", flush=True)
        closes = yf.Ticker("^VIX").history(period="3mo")["Close"]

    if closes is None or closes.empty:
        return None

    closes.index = closes.index.tz_localize(None) if closes.index.tzinfo else closes.index
    return closes


def main():
    print("Fetching VIX (^VIX) ...", end=" ", flush=True)
    closes = fetch_closes()

    if closes is None or closes.empty:
        print("FAILED — no data returned; keeping existing output/vix.json")
        sys.exit(1)

    print(f"OK  ({len(closes)} trading days)")

    history = [
        {"date": dt.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
        for dt, v in closes.items()
    ]

    current        = round(float(closes.iloc[-1]), 2)
    previous_close = round(float(closes.iloc[-2]), 2) if len(closes) > 1 else None
    history_30d    = history[-30:]

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
