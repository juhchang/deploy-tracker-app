"""
Reads all 7 signal JSON files, scores each signal 0–100 (100 = extreme fear),
applies weighted composite, writes output/market_pulse.json, and optionally
pushes market-pulse.json to your GitHub Gist for phone access.

Weights (per agreed design):
  VIX      20%
  HY Spread 20%
  Put/Call  15%
  Breadth   15%
  Fear&Greed 15%
  AAII      10%
  2s10s      5%

Run after all fetch_* scripts have been run.
Requires GITHUB_TOKEN and GIST_ID in .env for Gist sync.
"""

import json, os, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_ID      = os.getenv("GIST_ID", "")

OUTPUT_DIR = "output"

WEIGHTS = {
    "vix":     0.20,
    "hy":      0.20,
    "pcr":     0.15,
    "breadth": 0.15,
    "fg":      0.15,
    "aaii":    0.10,
    "curve":   0.05,
}

VIX_ZONES = [
    {"max": 12,  "cls": "z-greed",        "name": "EXTREME GREED", "range": "< 12",  "cash_lo": 0.40, "cash_hi": 0.50},
    {"max": 15,  "cls": "z-slight-greed", "name": "GREED",         "range": "12–15", "cash_lo": 0.30, "cash_hi": 0.40},
    {"max": 20,  "cls": "z-slight-fear",  "name": "SLIGHT FEAR",   "range": "15–20", "cash_lo": 0.20, "cash_hi": 0.25},
    {"max": 25,  "cls": "z-fear",         "name": "FEAR",          "range": "20–25", "cash_lo": 0.10, "cash_hi": 0.15},
    {"max": 30,  "cls": "z-very-fearful", "name": "VERY FEARFUL",  "range": "25–30", "cash_lo": 0.05, "cash_hi": 0.10},
    {"max": 999, "cls": "z-extreme-fear", "name": "EXTREME FEAR",  "range": "≥ 30",  "cash_lo": 0.00, "cash_hi": 0.05},
]


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  WARNING: could not read {path}: {e}")
        return None


def status_from_score(score):
    if score >= 70:
        return "red"
    if score >= 40:
        return "yellow"
    return "green"


def composite_label(score):
    if score >= 85: return "Extreme Fear"
    if score >= 70: return "Fear"
    if score >= 55: return "Moderate Fear"
    if score >= 40: return "Neutral"
    if score >= 25: return "Greed"
    return "Extreme Greed"


def get_vix_zone(vix):
    for z in VIX_ZONES:
        if vix < z["max"]:
            return z
    return VIX_ZONES[-1]


def score_signal(key, data, spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data):
    """Return (score 0-100, display_dict) for the given signal key."""

    if key == "vix":
        v = data.get("vix")
        if v is None:
            return None, None
        score = clamp((v - 12) / (35 - 12) * 100)
        hist = [e["value"] for e in data.get("history", [])[-30:]] if "history" in data else []
        label = "Extreme Fear" if score >= 70 else ("Fear Zone" if score >= 40 else "Calm")
        prev = data.get("previous_close")
        delta_str = f"{v - prev:+.1f} vs prev" if prev else ""
        return score, {
            "value": v, "display": f"{v:.1f}", "unit": "",
            "score": round(score), "status": status_from_score(score), "label": label,
            "delta": delta_str, "delta_dir": "bad" if v > (prev or v) else "good",
            "history": hist,
        }

    if key == "hy":
        if not spread_data:
            return None, None
        v = spread_data["hy"]["value"]
        score = clamp((v - 250) / (1000 - 250) * 100)
        delta = spread_data["hy"].get("delta_30d", 0)
        label = "Crisis" if score >= 70 else ("Elevated" if score >= 40 else "Calm")
        return score, {
            "value": v, "display": f"{v:.0f}", "unit": "bps",
            "score": round(score), "status": status_from_score(score), "label": label,
            "delta": f"{delta:+.0f} bps vs 30d", "delta_dir": "bad" if delta > 0 else "good",
            "history": spread_data["hy"].get("history_30d", []),
        }

    if key == "pcr":
        if not pcr_data:
            return None, None
        v = pcr_data["value"]
        score = clamp((v - 0.70) / (1.30 - 0.70) * 100)
        avg = pcr_data.get("avg_20d", v)
        label = "Elevated" if score >= 70 else ("Elevated" if score >= 40 else "Normal")
        hist = [e["value"] for e in pcr_data.get("history_20d", [])]
        return score, {
            "value": v, "display": f"{v:.2f}", "unit": "",
            "score": round(score), "status": status_from_score(score), "label": label,
            "delta": f"{v - avg:+.2f} vs 20d avg", "delta_dir": "good" if v >= avg else "bad",
            "history": hist,
        }

    if key == "breadth":
        if not breadth_data:
            return None, None
        v = breadth_data.get("current")
        if v is None:
            return None, None
        score = clamp((80 - v) / (80 - 20) * 100)
        hist = [e["value"] for e in breadth_data.get("history", [])[-30:]] if "history" in breadth_data else []
        label = "Capitulation" if score >= 70 else ("Stressed" if score >= 40 else "Healthy")
        return score, {
            "value": v, "display": f"{v:.0f}", "unit": "%",
            "score": round(score), "status": status_from_score(score), "label": label,
            "delta": "", "delta_dir": "neutral",
            "history": hist,
        }

    if key == "fg":
        if not fg_data:
            return None, None
        v = fg_data.get("score")
        if v is None:
            return None, None
        score = clamp(100 - v)   # F&G: 0=fear, 100=greed → invert for fear score
        prev_mo = fg_data.get("previous_1_month")
        delta_str = f"{v - prev_mo:+.0f} vs 1mo" if prev_mo else ""
        label = "Extreme Fear" if score >= 70 else ("Fear" if score >= 40 else "Greed")
        return score, {
            "value": v, "display": f"{v:.0f}", "unit": "",
            "score": round(score), "status": status_from_score(score), "label": label,
            "delta": delta_str, "delta_dir": "bad" if (prev_mo and v < prev_mo) else "good",
            "history": [],
        }

    if key == "aaii":
        if not aaii_data:
            return None, None
        spread = aaii_data.get("spread")  # bulls - bears; negative = more bears
        if spread is None:
            return None, None
        # -40 spread → score 100 (extreme fear/contrarian buy); +40 spread → score 0
        score = clamp((-spread + 40) / 80 * 100)
        label = "Extreme Bearish" if score >= 70 else ("Bearish" if score >= 40 else "Bullish")
        bulls = aaii_data.get("bulls", 0)
        bears = aaii_data.get("bears", 0)
        return score, {
            "value": spread, "display": f"{spread:+.0f}", "unit": "",
            "score": round(score), "status": status_from_score(score), "label": label,
            "delta": f"Bulls {bulls:.0f}% · Bears {bears:.0f}%", "delta_dir": "neutral",
            "history": [],
        }

    if key == "curve":
        if not spread_data:
            return None, None
        v = spread_data["curve"]["value"]
        # Inverted (<0) → high fear. Steep (>1.5) → low fear.
        score = clamp((-v + 1.5) / (1.5 - (-0.5)) * 100)
        label = "Inverted" if score >= 70 else ("Flat" if score >= 40 else "Normal")
        return score, {
            "value": v, "display": f"{v:+.2f}", "unit": "%",
            "score": round(score), "status": status_from_score(score), "label": label,
            "delta": "", "delta_dir": "neutral",
            "history": spread_data["curve"].get("history_30d", []),
        }

    return None, None


def push_to_gist(data: dict):
    """Push market_pulse.json to GitHub Gist as 'market-pulse.json'."""
    token = GITHUB_TOKEN.strip()
    gist  = GIST_ID.strip()
    if not token or token == "your_github_token_here":
        print("Gist sync skipped — add GITHUB_TOKEN and GIST_ID to .env to enable.")
        return
    if not gist or gist == "your_gist_id_here":
        print("Gist sync skipped — GIST_ID not set in .env.")
        return

    print("Pushing to GitHub Gist ...", end=" ", flush=True)
    try:
        res = requests.patch(
            f"https://api.github.com/gists/{gist}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
                "Accept":        "application/vnd.github+json",
            },
            json={"files": {"market-pulse.json": {"content": json.dumps(data, indent=2)}}},
            timeout=15,
        )
        res.raise_for_status()
        print("OK")
    except Exception as e:
        print(f"FAILED ({e})")


def main():
    print("Loading signal data ...")

    vix_data     = load_json(f"{OUTPUT_DIR}/vix.json")
    spread_data  = load_json(f"{OUTPUT_DIR}/spread_data.json")
    pcr_data     = load_json(f"{OUTPUT_DIR}/pcr.json")
    hvrank_data  = load_json(f"{OUTPUT_DIR}/hvrank_spx.json")
    breadth_data = load_json(f"{OUTPUT_DIR}/breadth.json")
    fg_data      = load_json(f"{OUTPUT_DIR}/fear_greed.json")
    aaii_data    = load_json(f"{OUTPUT_DIR}/aaii.json")

    signal_sources = {
        "vix":     (vix_data,     spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data),
        "hy":      (vix_data,     spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data),
        "pcr":     (vix_data,     spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data),
        "breadth": (vix_data,     spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data),
        "fg":      (vix_data,     spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data),
        "aaii":    (vix_data,     spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data),
        "curve":   (vix_data,     spread_data, pcr_data, hvrank_data, breadth_data, fg_data, aaii_data),
    }

    signals = {}
    weighted_sum = 0.0
    weight_used  = 0.0
    fear_count   = 0

    for key, sources in signal_sources.items():
        sc, display = score_signal(key, *sources)
        if sc is None:
            print(f"  {key:10s}: MISSING — skipping")
            continue
        signals[key] = display
        weighted_sum += sc * WEIGHTS[key]
        weight_used  += WEIGHTS[key]
        if sc >= 40:
            fear_count += 1
        print(f"  {key:10s}: score={sc:5.1f}  status={display['status']:6s}  ({display['label']})")

    # Re-normalize in case some signals were missing
    composite = round(weighted_sum / weight_used * 100) / 100 if weight_used > 0 else 0
    composite = round(composite)

    # VIX zone for deploy guidance
    vix_val  = vix_data.get("vix") if vix_data else 20
    vix_zone = get_vix_zone(vix_val or 20)

    # HV rank (standalone signal, not in composite weights)
    hv_display = None
    if hvrank_data:
        rank = hvrank_data["rank"]
        hv_score = rank  # rank IS the score (higher = richer premium = green for sellers)
        hv_display = {
            "rank":        rank,
            "current_hv20": hvrank_data["current_hv20"],
            "score":       rank,
            "status":      "green" if rank >= 60 else ("yellow" if rank >= 30 else "red"),
            "label":       "Rich Premium" if rank >= 60 else ("Normal" if rank >= 30 else "Thin Premium"),
            "history":     hvrank_data.get("history_30d", []),
        }

    out = {
        "generated": datetime.now().isoformat(),
        "composite": {
            "score":       composite,
            "label":       composite_label(composite),
            "fear_count":  fear_count,
            "total":       len(signals),
        },
        "signals":   signals,
        "hv_rank":   hv_display,
        "vix_zone":  vix_zone,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(f"{OUTPUT_DIR}/market_pulse.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"\nComposite: {composite}  —  {composite_label(composite)}")
    print(f"{fear_count} of {len(signals)} signals in fear territory")
    print(f"Written output/market_pulse.json")

    push_to_gist(out)


if __name__ == "__main__":
    main()
