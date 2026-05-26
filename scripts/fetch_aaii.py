"""
Fetch AAII weekly investor sentiment survey.
Source: aaii.com/sentimentsurvey — the national figure is computed as a
population-weighted average of the state-level data embedded in the page JS.
Published every Thursday.

Writes: output/aaii.json
"""

import re, json, os, requests
from datetime import datetime

URL = "https://www.aaii.com/sentimentsurvey"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Approximate retail investor populations by state (proportional weights)
STATE_WEIGHTS = {
    "CA": 40, "TX": 30, "FL": 22, "NY": 20, "PA": 13, "IL": 13, "OH": 12,
    "GA": 11, "NC": 11, "MI": 10, "WA": 8,  "NJ": 9,  "VA": 9,  "AZ": 7,
    "MA": 7,  "TN": 7,  "IN": 7,  "MO": 6,  "MD": 6,  "WI": 6,  "CO": 6,
    "MN": 6,  "SC": 5,  "AL": 5,  "LA": 5,  "KY": 5,  "OR": 4,  "OK": 4,
    "CT": 4,  "UT": 3,  "IA": 3,  "NV": 3,  "AR": 3,  "MS": 3,  "KS": 3,
    "NM": 2,  "NE": 2,  "ID": 2,  "WV": 2,  "HI": 1,  "NH": 1,  "ME": 1,
    "MT": 1,  "RI": 1,  "DE": 1,  "SD": 1,  "WY": 1,  "DC": 1,  "AK": 1,
    "VT": 1,  "ND": 1,
}


def parse_state_data(html: str):
    """
    Parse the JS variable block: var CA = "bullish: 21.9%<br> neutral: 25.0%<br> bearish: 53.1%";
    Returns dict of {state: (bulls, neutral, bears)}.
    """
    pattern = r'var ([A-Z]{2}) = "bullish: ([\d.]+)%<br> neutral: ([\d.]+)%<br> bearish: ([\d.]+)%"'
    matches = re.findall(pattern, html)
    result = {}
    for state, b, n, br in matches:
        result[state] = (float(b), float(n), float(br))
    return result


def weighted_national(state_data: dict):
    """Compute population-weighted national bulls / neutral / bears."""
    total_w = sum_b = sum_n = sum_br = 0.0
    for state, (b, n, br) in state_data.items():
        w = STATE_WEIGHTS.get(state, 1)
        total_w  += w
        sum_b    += b  * w
        sum_n    += n  * w
        sum_br   += br * w
    if total_w == 0:
        raise ValueError("No state data found")
    return round(sum_b / total_w, 1), round(sum_n / total_w, 1), round(sum_br / total_w, 1)


def main():
    print("Fetching AAII sentiment ...", end=" ", flush=True)
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    print(f"OK  (HTTP {resp.status_code})")

    state_data = parse_state_data(resp.text)
    if not state_data:
        raise ValueError("No state sentiment data found in AAII page")

    bulls, neutral, bears = weighted_national(state_data)
    spread = round(bulls - bears, 1)

    out = {
        "generated":   datetime.now().isoformat(),
        "bulls":       bulls,
        "neutral":     neutral,
        "bears":       bears,
        "spread":      spread,
        "states_used": len(state_data),
        "note":        "Weighted avg of state-level data from aaii.com/sentimentsurvey",
    }

    os.makedirs("output", exist_ok=True)
    with open("output/aaii.json", "w") as f:
        json.dump(out, f, indent=2)

    direction = "Contrarian Buy" if spread <= -10 else ("Neutral" if abs(spread) < 10 else "Bullish")
    print(f"Bulls {bulls}%  Neutral {neutral}%  Bears {bears}%  |  Spread {spread:+.1f}  ({direction})  [{len(state_data)} states]")
    print("Wrote output/aaii.json")


if __name__ == "__main__":
    main()
