"""
Compute 52-week Historical Volatility Rank for SPX.
HV Rank = percentile of current 20-day HV vs all 20-day HV readings in the past 52 weeks.
A rank of 71 means current vol is higher than 71% of readings in the past year.

Writes: output/hvrank_spx.json
"""

import json, os
import numpy as np
import yfinance as yf
from datetime import datetime


def compute_hv(closes, window=20):
    """Annualized historical volatility using log returns, in percent."""
    log_ret = np.log(closes / closes.shift(1))
    return (log_ret.rolling(window).std() * np.sqrt(252) * 100).round(2)


def main():
    print("Fetching SPX prices (^GSPC, 1 year) ...", end=" ", flush=True)
    raw = yf.download("^GSPC", period="1y", progress=False, auto_adjust=True)
    closes = raw["Close"].squeeze()
    closes.index = closes.index.tz_localize(None)
    print(f"OK  ({len(closes)} trading days)")

    hv = compute_hv(closes).dropna()

    current_hv  = float(hv.iloc[-1])
    hv_values   = hv.values

    # Rank: fraction of past readings below today's HV
    rank = round(float(np.sum(hv_values < current_hv) / len(hv_values) * 100))

    history_30d = [v for v in hv.tail(30).tolist() if not np.isnan(v)]

    out = {
        "generated":   datetime.now().isoformat(),
        "rank":        rank,
        "current_hv20": round(current_hv, 1),
        "history_30d":  [round(v, 1) for v in history_30d],
    }

    os.makedirs("output", exist_ok=True)
    with open("output/hvrank_spx.json", "w") as f:
        json.dump(out, f, indent=2)

    label = "Rich" if rank >= 60 else ("Normal" if rank >= 30 else "Thin")
    print(f"SPX HV20: {current_hv:.1f}%  |  52wk rank: {rank}  ({label} premium environment)")
    print("Wrote output/hvrank_spx.json")


if __name__ == "__main__":
    main()
