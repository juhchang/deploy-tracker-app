import json
import calendar
from datetime import date

VIX_ZONES = [
    {"name": "Extreme Greed", "vix_min": 0,  "vix_max": 12,  "cash_min": 0.40, "cash_max": 0.50, "color": "#ef4444"},
    {"name": "Greed",         "vix_min": 12, "vix_max": 15,  "cash_min": 0.30, "cash_max": 0.40, "color": "#f97316"},
    {"name": "Slight Fear",   "vix_min": 15, "vix_max": 20,  "cash_min": 0.20, "cash_max": 0.25, "color": "#eab308"},
    {"name": "Fear",          "vix_min": 20, "vix_max": 25,  "cash_min": 0.10, "cash_max": 0.15, "color": "#84cc16"},
    {"name": "Very Fearful",  "vix_min": 25, "vix_max": 30,  "cash_min": 0.05, "cash_max": 0.10, "color": "#22c55e"},
    {"name": "Extreme Fear",  "vix_min": 30, "vix_max": 999, "cash_min": 0.00, "cash_max": 0.05, "color": "#10b981"},
]


def get_zone(vix):
    for z in VIX_ZONES:
        if z["vix_min"] <= vix < z["vix_max"]:
            return z
    return VIX_ZONES[-1]


def compute_metrics(config, summary, scanner, trade_data):
    account = float(config["account_balance"])
    net_goal = float(config["monthly_net_goal"])
    tax_rate = float(config["blended_tax_rate"])

    gross_target = net_goal / (1 - tax_rate)

    vix = scanner.get("vix") or 20.0
    zone = get_zone(vix)

    cash_min = zone["cash_min"] * account
    cash_max = zone["cash_max"] * account
    cash_mid = (cash_min + cash_max) / 2
    deploy_min = account - cash_max
    deploy_max = account - cash_min
    deploy_mid = (deploy_min + deploy_max) / 2

    req_return_min = gross_target / deploy_max if deploy_max > 0 else 0
    req_return_max = gross_target / deploy_min if deploy_min > 0 else None

    # Current month progress
    cm = summary.get("current_month", {})
    gross_net = cm.get("net", 0)
    after_tax = gross_net * (1 - tax_rate)
    still_needed = gross_target - gross_net
    pct_of_target = (gross_net / gross_target * 100) if gross_target > 0 else 0

    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    days_remaining = days_in_month - days_elapsed
    daily_run_rate = gross_net / days_elapsed if days_elapsed > 0 else 0
    projected_total = daily_run_rate * days_in_month


    # Capital allocation
    holdings = trade_data.get("holdings", [])
    positive_holdings_value = sum(
        h.get("est_value") or 0
        for h in holdings
        if (h.get("est_value") or 0) > 0
    )

    capital_raw = trade_data.get("capital", {})
    open_csp_collateral = capital_raw.get("put_collateral", 0)
    available_for_csps = max(0, deploy_mid - positive_holdings_value - open_csp_collateral)

    # All zones with computed dollar values
    all_zones = []
    for z in VIX_ZONES:
        z_cash_min = z["cash_min"] * account
        z_cash_max = z["cash_max"] * account
        z_deploy_min = account - z_cash_max
        z_deploy_max = account - z_cash_min
        z_req_min = gross_target / z_deploy_max if z_deploy_max > 0 else None
        z_req_max = gross_target / z_deploy_min if z_deploy_min > 0 else None
        all_zones.append({
            **z,
            "cash_min_dollar": round(z_cash_min),
            "cash_max_dollar": round(z_cash_max),
            "deploy_min_dollar": round(z_deploy_min),
            "deploy_max_dollar": round(z_deploy_max),
            "req_return_min": z_req_min,
            "req_return_max": z_req_max,
            "is_current": z["name"] == zone["name"],
        })

    return {
        "gross_target": round(gross_target, 2),
        "blended_tax_rate": tax_rate,
        "vix": vix,
        "vix_zone": {
            **zone,
            "cash_min_dollar": round(cash_min),
            "cash_max_dollar": round(cash_max),
            "deploy_min_dollar": round(deploy_min),
            "deploy_max_dollar": round(deploy_max),
            "req_return_min": req_return_min,
            "req_return_max": req_return_max,
        },
        "all_zones": all_zones,
        "current_month": {
            "label": cm.get("label", ""),
            "sto": cm.get("sto", 0),
            "btc": cm.get("btc", 0),
            "gross_net": round(gross_net, 2),
            "after_tax": round(after_tax, 2),
            "still_needed": round(still_needed, 2),
            "pct_of_target": round(pct_of_target, 1),
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "days_in_month": days_in_month,
            "daily_run_rate": round(daily_run_rate, 2),
            "projected_total": round(projected_total, 2),
        },
        "capital": {
            "account_balance": account,
            "cash_buffer_min": round(cash_min),
            "cash_buffer_max": round(cash_max),
            "cash_buffer_mid": round(cash_mid),
            "deploy_min": round(deploy_min),
            "deploy_max": round(deploy_max),
            "deploy_mid": round(deploy_mid),
            "positive_holdings_value": round(positive_holdings_value),
            "open_csp_collateral": round(open_csp_collateral),
            "available_for_csps": round(available_for_csps),
        },
    }


if __name__ == "__main__":
    with open("config.json") as f:
        config = json.load(f)
    with open("output/summary.json") as f:
        summary = json.load(f)
    with open("output/scanner_results.json") as f:
        scanner = json.load(f)
    trade_data = {}
    try:
        with open("output/trade_data.json") as f:
            trade_data = json.load(f)
    except FileNotFoundError:
        pass

    m = compute_metrics(config, summary, scanner, trade_data)
    print(f"Gross target:     ${m['gross_target']:,.2f}/month")
    print(f"VIX:              {m['vix']} — {m['vix_zone']['name']}")
    rr = m['vix_zone']
    print(f"Required return:  {rr['req_return_min']:.2%} – {rr['req_return_max']:.2%}" if rr['req_return_max'] else f"  {rr['req_return_min']:.2%}")
    cap = m['capital']
    print(f"Deployable:       ${cap['deploy_min']:,.0f} – ${cap['deploy_max']:,.0f}")
    print(f"Available CSPs:   ${cap['available_for_csps']:,.0f}")
