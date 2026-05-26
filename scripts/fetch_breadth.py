"""
Fetch S&P 500 breadth: % of stocks above their 50-day moving average.
Primary:  ^SPXA50R via Yahoo Finance
Fallback: compute from a sample of SPX component ETFs using yfinance

Writes: output/breadth.json
"""

import json
import numpy as np
import yfinance as yf
from datetime import date, datetime


def fetch_spxa50r():
    """Try Yahoo Finance tickers for SPX % above 50MA."""
    for sym in ["^SPXA50R", "SPXA50R", "$SPXA50R"]:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="3mo", interval="1d", auto_adjust=True)
            if not hist.empty:
                return hist, sym
        except Exception:
            pass
    return None, None


def compute_breadth_from_etfs():
    """
    Proxy: check what % of a broad basket of large-cap stocks
    are above their 50-day MA. Uses ~30 representative SPX names.
    """
    basket = [
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","BRK-B","JPM","V",
        "JNJ","XOM","UNH","WMT","PG","MA","HD","CVX","ABBV","LLY",
        "AVGO","MRK","COST","PEP","KO","BAC","TMO","MCD","CRM","NFLX",
    ]
    data = yf.download(basket, period="4mo", progress=False, auto_adjust=True)["Close"]
    above = []
    for col in data.columns:
        series = data[col].dropna()
        if len(series) >= 50:
            ma50 = series.rolling(50).mean().iloc[-1]
            above.append(1 if series.iloc[-1] > ma50 else 0)
    return round(sum(above) / len(above) * 100, 1) if above else None


def main():
    print("Fetching SPX breadth (% above 50MA) ...", end=" ", flush=True)

    hist, sym = fetch_spxa50r()

    if hist is not None:
        hist.index = hist.index.tz_localize(None)
        history = [
            {"date": dt.strftime("%Y-%m-%d"), "value": round(float(row["Close"]), 2)}
            for dt, row in hist.iterrows()
        ]
        current = history[-1]["value"] if history else None
        source = sym
        print(f"OK via {sym}  ({current}%)")
    else:
        print("Yahoo symbol unavailable — computing from basket ...", end=" ", flush=True)
        current = compute_breadth_from_etfs()
        history = [{"date": date.today().isoformat(), "value": current}] if current else []
        source = "basket-proxy"
        print(f"OK  ({current}%)")

    if current is None:
        print("WARNING: Could not fetch breadth data.")
        return

    out = {
        "generated": datetime.now().isoformat(),
        "current":   current,
        "source":    source,
        "history":   history,
    }

    with open("output/breadth.json", "w") as f:
        json.dump(out, f, indent=2)

    label = "Capitulation" if current < 30 else ("Stressed" if current < 50 else "Healthy")
    print(f"Breadth: {current}%  ({label})")
    print("Wrote output/breadth.json")


if __name__ == "__main__":
    main()
