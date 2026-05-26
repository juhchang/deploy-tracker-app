"""
Fetch CBOE total put/call ratio.
Primary:  CBOE market statistics page (HTML parse)
Fallback: Compute from SPY + QQQ options chains via yfinance

Maintains a rolling 20-day history in output/pcr.json.
Writes: output/pcr.json
"""

import re, json, os, requests
import yfinance as yf
import numpy as np
from datetime import datetime, date

CBOE_URL = "https://www.cboe.com/us/options/market_statistics/daily/"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
OUT_FILE = "output/pcr.json"


def fetch_cboe_pcr():
    """Parse total put/call ratio from CBOE daily statistics page."""
    r = requests.get(CBOE_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    html = r.text

    # CBOE page shows P/C ratios in a table; look for "Total" row
    # Pattern: number like 1.21 or 0.89 near the word "Total"
    total_m = re.search(
        r'[Tt]otal[^<]{0,200}?(\d\.\d{2})',
        html, re.DOTALL
    )
    if total_m:
        val = float(total_m.group(1))
        if 0.4 <= val <= 3.0:
            return val, "cboe"

    # Broader search: find all decimal values in plausible P/C range
    candidates = [float(v) for v in re.findall(r'\b([01]\.\d{2})\b', html)
                  if 0.5 <= float(v) <= 2.5]
    if candidates:
        # Use the median of candidates to avoid outliers
        import statistics
        return round(statistics.median(candidates), 2), "cboe-estimated"

    raise ValueError("Could not parse CBOE P/C ratio from page")


def compute_yf_pcr():
    """
    Compute put/call ratio from SPY + QQQ options (first 3 expiries each).
    Returns a proxy P/C ratio — directionally accurate for index sentiment.
    """
    total_puts = total_calls = 0
    for ticker in ["SPY", "QQQ"]:
        t = yf.Ticker(ticker)
        expiries = t.options[:3] if len(t.options) >= 3 else t.options
        for exp in expiries:
            try:
                chain = t.option_chain(exp)
                total_puts  += chain.puts["volume"].fillna(0).sum()
                total_calls += chain.calls["volume"].fillna(0).sum()
            except Exception:
                pass

    if total_calls == 0:
        raise ValueError("No options volume data returned from yfinance")

    return round(total_puts / total_calls, 2), "yfinance-proxy"


def main():
    # --- Fetch current P/C ---
    pcr_value = None
    source = None
    print("Fetching P/C ratio from CBOE ...", end=" ", flush=True)
    try:
        pcr_value, source = fetch_cboe_pcr()
        print(f"OK  ({pcr_value})")
    except Exception as e:
        print(f"failed ({e})")
        print("Falling back to yfinance SPY+QQQ options ...", end=" ", flush=True)
        try:
            pcr_value, source = compute_yf_pcr()
            print(f"OK  ({pcr_value})")
        except Exception as e2:
            print(f"failed ({e2})")

    if pcr_value is None:
        print("WARNING: Could not fetch P/C ratio. Skipping update.")
        return

    # --- Load existing history and append today ---
    os.makedirs("output", exist_ok=True)
    existing = {}
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE) as f:
                existing = json.load(f)
        except Exception:
            pass

    history = existing.get("history_20d", [])
    today_str = date.today().isoformat()

    # Replace today's entry if already present, otherwise append
    history = [e for e in history if e.get("date") != today_str]
    history.append({"date": today_str, "value": pcr_value})
    history = sorted(history, key=lambda x: x["date"])[-20:]  # keep last 20 days

    avg_20d = round(float(np.mean([e["value"] for e in history])), 2)

    out = {
        "generated":   datetime.now().isoformat(),
        "value":       pcr_value,
        "source":      source,
        "avg_20d":     avg_20d,
        "history_20d": history,
    }

    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2)

    direction = "Elevated (fear)" if pcr_value >= 1.1 else ("Normal" if pcr_value >= 0.8 else "Low (greed)")
    print(f"P/C Ratio: {pcr_value}  |  20d avg: {avg_20d}  |  {direction}  |  source: {source}")
    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
