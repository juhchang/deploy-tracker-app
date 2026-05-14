import json
from datetime import date

import yfinance as yf


def main():
    ticker = yf.Ticker("^SPXA50R")
    hist = ticker.history(period="6mo", interval="1d", auto_adjust=True)

    if hist.empty:
        print("No data returned for ^SPXA50R")
        return

    history = []
    for dt, row in hist.iterrows():
        history.append({
            "date": dt.strftime("%Y-%m-%d"),
            "value": round(float(row["Close"]), 2),
        })

    current = history[-1]["value"] if history else None

    out = {
        "current": current,
        "history": history,
        "generated": date.today().isoformat(),
    }

    with open("output/breadth.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"S&P 500 Breadth (^SPXA50R): {current}% · {len(history)} trading days")
    print("Wrote output/breadth.json")


if __name__ == "__main__":
    main()
