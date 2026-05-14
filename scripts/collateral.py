import json
from datetime import date
from collections import defaultdict


def calc_position_status(gap_pct):
    """gap_pct = (current_price - cost_basis) / cost_basis * 100"""
    if gap_pct is None:
        return 'unknown'
    if gap_pct >= -5:
        return 'green'
    elif gap_pct >= -15:
        return 'yellow'
    elif gap_pct >= -30:
        return 'red'
    else:
        return 'black'


def suggested_coverage(status):
    return {
        'green':   '100%',
        'yellow':  '50–75%',
        'red':     '25–50%',
        'black':   '0–25%',
        'unknown': 'N/A',
    }.get(status, 'N/A')


def calc_put_status(buffer_pct):
    """buffer_pct = (current_price - strike) / current_price * 100; negative = ITM"""
    if buffer_pct is None:
        return 'unknown'
    if buffer_pct >= 15:
        return 'green'
    elif buffer_pct >= 5:
        return 'yellow'
    elif buffer_pct >= 0:
        return 'red'
    else:
        return 'black'


def main():
    with open('output/parsed_trades.json') as f:
        rows = json.load(f)
    with open('output/summary.json') as f:
        summary = json.load(f)

    # Pre-CSV starting share positions
    starting = defaultdict(float)
    try:
        with open('data/starting_positions.json') as f:
            sp = json.load(f)
        for entry in sp.get('positions', []):
            starting[entry['ticker']] += entry['shares']
    except FileNotFoundError:
        pass

    # Manual cost basis from Robinhood app (authoritative)
    manual_basis = {}
    try:
        with open('data/cost_basis.json') as f:
            cb = json.load(f)
        for entry in cb.get('positions', []):
            manual_basis[entry['ticker']] = entry['cost_basis']
    except FileNotFoundError:
        pass

    # CSV-derived weighted average cost basis (fallback for tickers not in cost_basis.json)
    csv_cost_total  = defaultdict(float)
    csv_share_total = defaultdict(float)
    for r in rows:
        if r['code'] != 'Buy':
            continue
        t = (r.get('instrument') or '').strip()
        if not t:
            continue
        csv_cost_total[t]  += r['quantity'] * r['price']
        csv_share_total[t] += r['quantity']
    csv_avg_basis = {
        t: csv_cost_total[t] / csv_share_total[t]
        for t in csv_share_total if csv_share_total[t] > 0
    }

    # Current prices from scanner (live Tradier quotes)
    scanner_prices = {}
    scanner_data = {}
    try:
        with open('output/scanner_results.json') as f:
            scanner_data = json.load(f)
        for r in scanner_data.get('results', []) + scanner_data.get('put_results', []):
            t = r.get('ticker')
            p = r.get('price')
            if t and p and t not in scanner_prices:
                scanner_prices[t] = p
    except (FileNotFoundError, KeyError):
        pass

    vix = scanner_data.get('vix', 20.0)

    today = date.today().isoformat()

    # --- Open positions ---
    pos_qty  = defaultdict(float)
    pos_meta = {}

    for row in rows:
        code = row['code']
        if code not in ('STO', 'BTC'):
            continue
        desc = row['description']
        qty  = row.get('quantity') or 0
        pos_qty[desc] += qty if code == 'STO' else -qty
        if desc not in pos_meta and row.get('opt_expiry'):
            pos_meta[desc] = {
                'ticker': row.get('opt_ticker'),
                'expiry': row.get('opt_expiry'),
                'type':   row.get('opt_type'),
                'strike': row.get('opt_strike'),
            }

    open_puts  = []
    open_calls = []

    for desc, qty in pos_qty.items():
        if qty <= 0:
            continue
        meta = pos_meta.get(desc)
        if not meta or not meta.get('expiry'):
            continue
        if meta['expiry'] < today:
            continue

        ticker = meta['ticker']
        strike = meta['strike']

        entry = {
            'ticker':    ticker,
            'expiry':    meta['expiry'],
            'type':      meta['type'],
            'strike':    strike,
            'contracts': int(round(qty)),
            'collateral': round(strike * 100 * qty, 2) if strike else None,
        }

        if meta['type'] == 'Put':
            cur_price = scanner_prices.get(ticker)
            if cur_price and strike:
                buf_amt = round(cur_price - strike, 2)
                buf_pct = round((cur_price - strike) / cur_price * 100, 1)
            else:
                buf_amt = buf_pct = None
            entry['current_price'] = cur_price
            entry['buffer_amt']    = buf_amt
            entry['buffer_pct']    = buf_pct
            entry['put_status']    = calc_put_status(buf_pct)
            open_puts.append(entry)
        elif meta['type'] == 'Call':
            open_calls.append(entry)

    open_puts.sort(key=lambda x:  (x['expiry'], x['ticker']))
    open_calls.sort(key=lambda x: (x['expiry'], x['ticker']))

    # --- Share holdings ---
    share_qty        = defaultdict(float)
    last_price       = {}
    last_price_date  = {}

    for row in rows:
        code = row['code']
        if code not in ('Buy', 'Sell'):
            continue
        ticker = row.get('instrument', '').strip()
        if not ticker:
            continue
        qty   = row.get('quantity') or 0
        price = row.get('price')
        share_qty[ticker] += qty if code == 'Buy' else -qty
        if price and row['date'] >= last_price_date.get(ticker, ''):
            last_price[ticker]      = price
            last_price_date[ticker] = row['date']

    all_tickers = set(share_qty.keys()) | set(starting.keys())
    holdings = []
    for ticker in sorted(all_tickers):
        qty   = share_qty.get(ticker, 0) + starting.get(ticker, 0)
        price = scanner_prices.get(ticker) or last_price.get(ticker)
        basis = manual_basis.get(ticker) or csv_avg_basis.get(ticker)
        gap_pct = round((price - basis) / basis * 100, 1) if price and basis else None
        status  = calc_position_status(gap_pct)
        holdings.append({
            'ticker':          ticker,
            'shares':          int(round(qty)),
            'last_price':      price,
            'est_value':       round(qty * price, 2) if price else None,
            'cost_basis':      round(basis, 2) if basis else None,
            'gap_pct':         gap_pct,
            'position_status': status,
        })

    # --- Covered call exposure sub-table ---
    cc_contracts = defaultdict(int)
    for c in open_calls:
        cc_contracts[c['ticker']] += c['contracts']

    call_exposure = []
    for ticker, contracts in cc_contracts.items():
        shares_in_cc = contracts * 100
        # Include pre-CSV starting positions in shares_held
        held  = int(round(share_qty.get(ticker, 0) + starting.get(ticker, 0)))
        price = scanner_prices.get(ticker) or last_price.get(ticker)
        basis = manual_basis.get(ticker) or csv_avg_basis.get(ticker)
        gap_pct      = round((price - basis) / basis * 100, 1) if price and basis else None
        status       = calc_position_status(gap_pct)
        actual_cov   = round(shares_in_cc / held * 100, 1) if held > 0 else None
        call_exposure.append({
            'ticker':             ticker,
            'cc_contracts':       contracts,
            'shares_in_cc':       shares_in_cc,
            'shares_held':        held,
            'last_price':         price,
            'position_value':     round(shares_in_cc * price, 2) if price else None,
            'short_shares':       held < shares_in_cc,
            'cost_basis':         round(basis, 2) if basis else None,
            'gap_pct':            gap_pct,
            'position_status':    status,
            'suggested_coverage': suggested_coverage(status),
            'actual_coverage':    actual_cov,
        })

    # --- Assignment history ---
    assignments = []
    for row in rows:
        if row['code'] != 'OASGN':
            continue
        assignments.append({
            'date':        row['date'],
            'ticker':      row.get('opt_ticker') or row.get('instrument'),
            'description': row['description'],
            'contracts':   int(row.get('quantity') or 0),
            'opt_type':    row.get('opt_type'),
            'strike':      row.get('opt_strike'),
        })
    assignments.sort(key=lambda x: x['date'])

    # --- Capital allocation ---
    total_put_collateral = sum(p['collateral'] or 0 for p in open_puts)
    total_call_value     = sum(e['position_value'] or 0 for e in call_exposure)

    # ─── Session 2: Deployment ceiling, VIX cash check, Position P&L ─────────

    config = {}
    try:
        with open('config.json') as f:
            config = json.load(f)
    except FileNotFoundError:
        pass

    account_balance  = float(config.get('account_balance', 0))
    monthly_net_goal = float(config.get('monthly_net_goal', 0))
    tax_rate         = float(config.get('blended_tax_rate', 0.30))
    gross_target     = monthly_net_goal / (1 - tax_rate) if (1 - tax_rate) > 0 else 0

    _VIX_ZONES = [
        {"name": "Extreme Greed", "vix_min": 0,  "vix_max": 12,  "cash_min": 0.40, "cash_max": 0.50},
        {"name": "Greed",         "vix_min": 12, "vix_max": 15,  "cash_min": 0.30, "cash_max": 0.40},
        {"name": "Slight Fear",   "vix_min": 15, "vix_max": 20,  "cash_min": 0.20, "cash_max": 0.25},
        {"name": "Fear",          "vix_min": 20, "vix_max": 25,  "cash_min": 0.10, "cash_max": 0.15},
        {"name": "Very Fearful",  "vix_min": 25, "vix_max": 30,  "cash_min": 0.05, "cash_max": 0.10},
        {"name": "Extreme Fear",  "vix_min": 30, "vix_max": 999, "cash_min": 0.00, "cash_max": 0.05},
    ]
    zone = next((z for z in _VIX_ZONES if z["vix_min"] <= vix < z["vix_max"]), _VIX_ZONES[-1])

    cash_reserve_min = zone['cash_min'] * account_balance
    cash_reserve_max = zone['cash_max'] * account_balance
    cash_reserve_mid = (cash_reserve_min + cash_reserve_max) / 2
    deploy_mid       = account_balance - cash_reserve_mid
    req_return_rate  = gross_target / deploy_mid if deploy_mid > 0 else 0

    positive_holdings_value = sum((h.get('est_value') or 0) for h in holdings if (h.get('est_value') or 0) > 0)
    cash_on_hand = max(0.0, account_balance - positive_holdings_value - total_put_collateral)
    vix_passes   = cash_on_hand >= cash_reserve_min
    excess_min   = max(0.0, cash_on_hand - cash_reserve_max)
    excess_max   = max(0.0, cash_on_hand - cash_reserve_min)

    # Deployment ceiling per holding (position-status limits)
    _DEPLOY_PCT = {
        'green':   (1.00, 1.00),
        'yellow':  (0.50, 0.75),
        'red':     (0.25, 0.50),
        'black':   (0.00, 0.00),
        'unknown': (1.00, 1.00),
    }
    _STATUS_NOTE = {
        'green':   'At/above basis — full deployment',
        'yellow':  '5–15% below basis — partial coverage',
        'red':     '15–30% below basis — light coverage',
        'black':   '30%+ below basis — hold, protect recovery',
        'unknown': '—',
    }

    ceiling_min = 0.0
    ceiling_max = 0.0
    green_total = yellow_min = yellow_max = red_min = red_max = black_total = 0.0
    per_position = []

    for h in holdings:
        val = h.get('est_value') or 0
        if val <= 0:
            continue
        status = h.get('position_status', 'unknown')
        pct_min, pct_max = _DEPLOY_PCT.get(status, (1.0, 1.0))
        d_min = val * pct_min
        d_max = val * pct_max
        ceiling_min += d_min
        ceiling_max += d_max
        if status == 'green':
            green_total += val
        elif status == 'yellow':
            yellow_min += d_min
            yellow_max += d_max
        elif status == 'red':
            red_min += d_min
            red_max += d_max
        elif status == 'black':
            black_total += val
        per_position.append({
            'ticker':     h['ticker'],
            'shares':     h['shares'],
            'value':      round(val, 2),
            'status':     status,
            'deploy_min': round(d_min, 2),
            'deploy_max': round(d_max, 2),
            'note':       _STATUS_NOTE.get(status, '—'),
        })

    deployable_cash = max(0.0, cash_on_hand - cash_reserve_mid)
    ceiling_min += deployable_cash
    ceiling_max += deployable_cash
    ceiling_mid  = (ceiling_min + ceiling_max) / 2

    total_cc_open_value = sum((e.get('position_value') or 0) for e in call_exposure)
    total_deployed  = total_put_collateral + total_cc_open_value
    deployed_pct    = total_deployed / account_balance * 100 if account_balance > 0 else 0
    ceiling_pct_min = ceiling_min / account_balance * 100 if account_balance > 0 else 0
    ceiling_pct_max = ceiling_max / account_balance * 100 if account_balance > 0 else 0
    gap_min = max(0.0, ceiling_min - total_deployed)
    gap_max = max(0.0, ceiling_max - total_deployed)
    missed_income_min = gap_min * 0.01  # 1% weekly estimate
    missed_income_max = gap_max * 0.01

    # CC capacity — uncovered shares by status
    cc_cap_min = 0.0
    cc_cap_max = 0.0
    cc_cap_by_ticker = []
    for h in holdings:
        ticker     = h['ticker']
        shares_held = h['shares']
        if shares_held <= 0:
            continue
        open_cc_shares = cc_contracts.get(ticker, 0) * 100
        uncov = max(0, shares_held - open_cc_shares)
        if uncov == 0:
            continue
        price = h.get('last_price')
        if not price:
            continue
        uncov_val  = uncov * price
        status     = h.get('position_status', 'unknown')
        pct_min, pct_max = _DEPLOY_PCT.get(status, (1.0, 1.0))
        cap_min = uncov_val * pct_min
        cap_max = uncov_val * pct_max
        cc_cap_min += cap_min
        cc_cap_max += cap_max
        cc_cap_by_ticker.append({
            'ticker':          ticker,
            'uncovered_shares': int(uncov),
            'uncov_value':     round(uncov_val, 2),
            'cap_min':         round(cap_min, 2),
            'cap_max':         round(cap_max, 2),
            'position_status': status,
        })

    # Adjusted monthly goal (ceiling_mid at same required return rate)
    adjusted_gross    = ceiling_mid * req_return_rate
    adjusted_net_goal = adjusted_gross * (1 - tax_rate)
    goal_reduction    = monthly_net_goal - adjusted_net_goal

    deployment = {
        'account_balance':   round(account_balance, 2),
        'total_deployed':    round(total_deployed, 2),
        'deployed_pct':      round(deployed_pct, 1),
        'ceiling_min':       round(ceiling_min, 2),
        'ceiling_max':       round(ceiling_max, 2),
        'ceiling_mid':       round(ceiling_mid, 2),
        'ceiling_pct_min':   round(ceiling_pct_min, 1),
        'ceiling_pct_max':   round(ceiling_pct_max, 1),
        'gap_min':           round(gap_min, 2),
        'gap_max':           round(gap_max, 2),
        'missed_income_min': round(missed_income_min, 0),
        'missed_income_max': round(missed_income_max, 0),
        'green_total':       round(green_total, 2),
        'yellow_min':        round(yellow_min, 2),
        'yellow_max':        round(yellow_max, 2),
        'red_min':           round(red_min, 2),
        'red_max':           round(red_max, 2),
        'black_total':       round(black_total, 2),
        'deployable_cash':   round(deployable_cash, 2),
        'per_position':      per_position,
        'vix_cash_check': {
            'vix':              vix,
            'zone_name':        zone['name'],
            'cash_reserve_min': round(cash_reserve_min, 2),
            'cash_reserve_max': round(cash_reserve_max, 2),
            'cash_on_hand':     round(cash_on_hand, 2),
            'passes':           vix_passes,
            'excess_min':       round(excess_min, 2),
            'excess_max':       round(excess_max, 2),
            'cash_pct_min':     zone['cash_min'],
            'cash_pct_max':     zone['cash_max'],
        },
        'cc_capacity': {
            'total_min':  round(cc_cap_min, 2),
            'total_max':  round(cc_cap_max, 2),
            'by_ticker':  cc_cap_by_ticker,
        },
        'adjusted_net_goal':  round(adjusted_net_goal, 2),
        'adjusted_gross':     round(adjusted_gross, 2),
        'gross_target':       round(gross_target, 2),
        'monthly_net_goal':   monthly_net_goal,
        'goal_reduction':     round(goal_reduction, 2),
        'req_return_rate_pct': round(req_return_rate * 100, 2),
    }

    # Position P&L — unrealized stock + YTD options + this-month options
    ytd_by_ticker   = {t['ticker']: t for t in summary.get('by_ticker', [])}
    month_by_ticker = {t['ticker']: t for t in summary.get('current_month_by_ticker', [])}

    position_pnl = []
    for h in holdings:
        if (h.get('shares') or 0) <= 0:
            continue
        ticker    = h['ticker']
        price     = h.get('last_price')
        basis     = h.get('cost_basis')
        shares    = h.get('shares', 0)
        unrealized = round((price - basis) * shares, 2) if price and basis else None
        ytd_net    = round(ytd_by_ticker.get(ticker, {}).get('net', 0), 2)
        month_net  = round(month_by_ticker.get(ticker, {}).get('net', 0), 2)
        total_pnl  = round(unrealized + ytd_net, 2) if unrealized is not None else None

        if total_pnl is None:
            verdict = 'unknown'
        elif total_pnl > 0:
            if unrealized is not None and unrealized < 0:
                verdict = 'Premium covering loss'
            else:
                verdict = 'Working'
        elif ytd_net > 0 and unrealized is not None and unrealized < 0:
            verdict = 'Premium offsetting loss'
        else:
            verdict = 'Options not covering loss'

        position_pnl.append({
            'ticker':          ticker,
            'shares':          shares,
            'position_status': h.get('position_status', 'unknown'),
            'unrealized_pnl':  unrealized,
            'month_net':       month_net,
            'ytd_net':         ytd_net,
            'total_pnl':       total_pnl,
            'verdict':         verdict,
        })
    position_pnl.sort(key=lambda x: (x.get('total_pnl') or 0), reverse=True)

    trade_data = {
        **summary,
        'open_puts':    open_puts,
        'open_calls':   open_calls,
        'call_exposure': call_exposure,
        'holdings':     holdings,
        'assignments':  assignments,
        'capital': {
            'put_collateral': round(total_put_collateral, 2),
            'call_value':     round(total_call_value, 2),
            'total':          round(total_put_collateral + total_call_value, 2),
        },
        'deployment':    deployment,
        'position_pnl':  position_pnl,
        'generated': date.today().isoformat(),
    }

    with open('output/trade_data.js', 'w') as f:
        f.write('window.TRADE_DATA = ')
        json.dump(trade_data, f, indent=2)
        f.write(';\n')

    with open('output/trade_data.json', 'w') as f:
        json.dump(trade_data, f, indent=2)

    print(f"Open puts:  {len(open_puts)}  (collateral: ${total_put_collateral:,.2f})")
    print(f"Open calls: {len(open_calls)}")
    print(f"Holdings:   {len(holdings)} tickers")
    print(f"Assignments:{len(assignments)}")
    print("Wrote output/trade_data.js + trade_data.json")


if __name__ == '__main__':
    main()
