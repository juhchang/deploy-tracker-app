#!/usr/bin/env python3
"""
Options scanner — finds ~0.25 delta contracts for selling puts/calls.
Data source: Tradier API (sandbox tier)
"""

import os
import json
import math
import requests
import numpy as np
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

API_KEY = os.getenv('TRADIER_API_KEY')
BASE_URL = os.getenv('TRADIER_BASE_URL', 'https://sandbox.tradier.com/v1')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Accept': 'application/json'}

def load_tickers():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'tickers.json')
    try:
        with open(config_path) as f:
            data = json.load(f)
        return [entry['ticker'] for entry in data.get('watchlist', []) if entry.get('ticker')]
    except FileNotFoundError:
        # fallback if tickers.json is missing
        return ['TQQQ', 'HOOD', 'SOFI', 'PLTR', 'BMNR', 'NVDA', 'GOOGL', 'AAPL', 'AMZN', 'BITX', 'ETHU', 'TNA']

TICKERS = load_tickers()

TARGET_DELTA = 0.25
MIN_DTE = 7
MAX_DTE = 30
BB_PERIOD = 20
BB_STD = 2
HV_PERIOD = 30


# ---------------------------------------------------------------------------
# Tradier API helpers
# ---------------------------------------------------------------------------

def get_quotes(symbols):
    r = requests.get(
        f'{BASE_URL}/markets/quotes',
        headers=HEADERS,
        params={'symbols': ','.join(symbols), 'greeks': 'false'},
        timeout=15,
    )
    r.raise_for_status()
    quotes = r.json().get('quotes', {}).get('quote', [])
    if isinstance(quotes, dict):
        quotes = [quotes]
    return {q['symbol']: float(q['last']) for q in quotes if q.get('last')}


def get_expirations(symbol):
    r = requests.get(
        f'{BASE_URL}/markets/options/expirations',
        headers=HEADERS,
        params={'symbol': symbol, 'includeAllRoots': 'false', 'strikes': 'false'},
        timeout=15,
    )
    r.raise_for_status()
    dates = r.json().get('expirations', {}).get('date', [])
    if isinstance(dates, str):
        dates = [dates]
    return dates or []


def get_options_chain(symbol, expiration):
    r = requests.get(
        f'{BASE_URL}/markets/options/chains',
        headers=HEADERS,
        params={'symbol': symbol, 'expiration': expiration, 'greeks': 'true'},
        timeout=15,
    )
    r.raise_for_status()
    options = r.json().get('options') or {}
    chain = options.get('option', [])
    if isinstance(chain, dict):
        chain = [chain]
    return chain or []


def get_historical_prices(symbol, days=260):
    end = date.today()
    start = end - timedelta(days=days)
    r = requests.get(
        f'{BASE_URL}/markets/history',
        headers=HEADERS,
        params={
            'symbol': symbol,
            'interval': 'daily',
            'start': start.strftime('%Y-%m-%d'),
            'end': end.strftime('%Y-%m-%d'),
        },
        timeout=15,
    )
    r.raise_for_status()
    history = r.json().get('history') or {}
    days_data = history.get('day', [])
    if isinstance(days_data, dict):
        days_data = [days_data]
    return [float(d['close']) for d in days_data if d.get('close')]


# ---------------------------------------------------------------------------
# Technical calculations
# ---------------------------------------------------------------------------

def calculate_bollinger_bands(prices):
    """
    Returns (position_pct, upper, lower, mid).
    position_pct: 0 = at lower band, 100 = at upper band.
    """
    if len(prices) < BB_PERIOD:
        return None, None, None, None
    recent = prices[-BB_PERIOD:]
    mid = float(np.mean(recent))
    std = float(np.std(recent, ddof=1))
    upper = mid + BB_STD * std
    lower = mid - BB_STD * std
    current = prices[-1]
    if upper == lower:
        return 50.0, upper, lower, mid
    pos = (current - lower) / (upper - lower) * 100
    return round(pos, 1), round(upper, 2), round(lower, 2), round(mid, 2)


def calculate_hv_rank(prices):
    """
    52-week historical volatility rank as an IV rank proxy.
    Returns 0-100 where 100 = highest HV of the past year.
    """
    if len(prices) < HV_PERIOD + 2:
        return None
    log_returns = np.diff(np.log(prices))
    hvs = []
    for i in range(HV_PERIOD, len(log_returns) + 1):
        window = log_returns[i - HV_PERIOD:i]
        hv = float(np.std(window, ddof=1)) * math.sqrt(252) * 100
        hvs.append(hv)
    if not hvs:
        return None
    current_hv = hvs[-1]
    min_hv = min(hvs)
    max_hv = max(hvs)
    if max_hv == min_hv:
        return 50.0
    return round((current_hv - min_hv) / (max_hv - min_hv) * 100, 1)


# ---------------------------------------------------------------------------
# Contract selection
# ---------------------------------------------------------------------------

def find_target_contract(chain, option_type):
    candidates = []
    for opt in chain:
        if opt.get('option_type') != option_type:
            continue
        greeks = opt.get('greeks') or {}
        delta = greeks.get('delta')
        if delta is None:
            continue
        abs_delta = abs(float(delta))
        if 0.10 <= abs_delta <= 0.50:
            candidates.append((abs(abs_delta - TARGET_DELTA), opt))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Per-ticker scan
# ---------------------------------------------------------------------------

def scan_ticker(ticker, current_price, force_type=None):
    prices = get_historical_prices(ticker)
    bb_pos, bb_upper, bb_lower, bb_mid = calculate_bollinger_bands(prices)
    hv_rank = calculate_hv_rank(prices)

    if bb_pos is not None:
        if bb_pos <= 35:
            suggested = 'Put'
            bb_label = f'{bb_pos:.0f}% — near lower'
        elif bb_pos >= 65:
            suggested = 'Call'
            bb_label = f'{bb_pos:.0f}% — near upper'
        else:
            suggested = 'Both'
            bb_label = f'{bb_pos:.0f}% — middle'
    else:
        suggested = 'Both'
        bb_label = 'N/A'

    all_expirations = get_expirations(ticker)
    today = date.today()
    valid_expirations = []
    for exp_str in all_expirations:
        exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
        dte = (exp_date - today).days
        if MIN_DTE <= dte <= MAX_DTE:
            valid_expirations.append((dte, exp_str))

    if not valid_expirations:
        return []

    if force_type:
        types_to_scan = [force_type]
    else:
        types_to_scan = ['put'] if suggested == 'Put' else ['call'] if suggested == 'Call' else ['put', 'call']

    # Scan every valid expiry, collect all candidates, then pick best ann_return per type
    candidates = {t: [] for t in types_to_scan}
    for dte, expiration in valid_expirations:
        chain = get_options_chain(ticker, expiration)
        if not chain:
            continue
        for opt_type in types_to_scan:
            contract = find_target_contract(chain, opt_type)
            if not contract:
                continue
            greeks = contract.get('greeks') or {}
            delta = greeks.get('delta')
            iv = greeks.get('mid_iv')
            bid = float(contract.get('bid') or 0)
            ask = float(contract.get('ask') or 0)
            mid = round((bid + ask) / 2, 2)
            strike = contract.get('strike')
            collateral_per_share = float(strike) if opt_type == 'put' else current_price
            pct_return = round(mid / collateral_per_share * 100, 3) if collateral_per_share else None
            ann_return = round(pct_return / dte * 365, 2) if (pct_return and dte) else None

            # BB buffer: distance between strike and the relevant band edge
            # Put: bb_lower - strike (positive = strike is safely below lower band)
            # Call: strike - bb_upper (positive = strike is safely above upper band)
            if strike is not None and bb_lower is not None and bb_upper is not None:
                s = float(strike)
                if opt_type == 'put':
                    bb_buffer = round(bb_lower - s, 2)
                else:
                    bb_buffer = round(s - bb_upper, 2)
                bb_buffer_pct = round(bb_buffer / current_price * 100, 2) if current_price else None
            else:
                bb_buffer = None
                bb_buffer_pct = None

            candidates[opt_type].append({
                'ticker': ticker,
                'price': current_price,
                'bb_position': bb_label,
                'bb_pos_pct': bb_pos,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'suggested': suggested,
                'expiry': expiration,
                'dte': dte,
                'type': opt_type.capitalize(),
                'strike': strike,
                'delta': round(float(delta), 3) if delta is not None else None,
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'iv_pct': round(float(iv) * 100, 1) if iv else None,
                'hv_rank': hv_rank,
                'pct_return': pct_return,
                'ann_return': ann_return,
                'bb_buffer': bb_buffer,
                'bb_buffer_pct': bb_buffer_pct,
                'open_interest': contract.get('open_interest', 0),
                'volume': contract.get('volume', 0),
            })

    # Return only the best annualized return per option type
    results = []
    for opt_type in types_to_scan:
        if not candidates[opt_type]:
            continue
        best = max(candidates[opt_type], key=lambda x: x['ann_return'] or 0)
        results.append(best)
    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_table(results):
    if not results:
        print('No results found.')
        return

    headers = [
        'Ticker', 'Price', 'BB Position', 'Suggested', 'Expiry', 'DTE',
        'Type', 'Strike', 'Delta', 'Bid', 'Ask', 'Mid', 'Ret%', 'Ann%', 'BB Buffer', 'IV%', 'HV Rank',
    ]

    rows = []
    for r in results:
        buf = r.get('bb_buffer')
        buf_pct = r.get('bb_buffer_pct')
        if buf is not None:
            band_price = r.get('bb_lower') if r['type'] == 'Put' else r.get('bb_upper')
            sign = '+' if buf >= 0 else ''
            buf_str = f"{sign}${band_price:.2f} ({sign}{buf_pct:.1f}%)" if band_price else 'N/A'
        else:
            buf_str = 'N/A'
        rows.append([
            r['ticker'],
            f"${r['price']:.2f}",
            r['bb_position'],
            r['suggested'],
            r['expiry'],
            str(r['dte']),
            r['type'],
            f"${r['strike']:.2f}" if r['strike'] else 'N/A',
            f"{r['delta']:.3f}" if r['delta'] is not None else 'N/A',
            f"${r['bid']:.2f}",
            f"${r['ask']:.2f}",
            f"${r['mid']:.2f}",
            f"{r['pct_return']:.2f}%" if r['pct_return'] is not None else 'N/A',
            f"{r['ann_return']:.1f}%" if r['ann_return'] is not None else 'N/A',
            buf_str,
            f"{r['iv_pct']:.1f}%" if r['iv_pct'] else 'N/A',
            f"{r['hv_rank']:.0f}" if r['hv_rank'] is not None else 'N/A',
        ])

    col_widths = [
        max(len(headers[i]), max(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    sep = '+-' + '-+-'.join('-' * w for w in col_widths) + '-+'
    fmt_row = lambda cells: '| ' + ' | '.join(c.ljust(col_widths[i]) for i, c in enumerate(cells)) + ' |'

    print(sep)
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def get_vix():
    """Fetch current VIX level."""
    try:
        r = requests.get(
            f'{BASE_URL}/markets/quotes',
            headers=HEADERS,
            params={'symbols': 'VIX', 'greeks': 'false'},
            timeout=15,
        )
        r.raise_for_status()
        quotes = r.json().get('quotes', {}).get('quote', {})
        if isinstance(quotes, list):
            quotes = quotes[0] if quotes else {}
        last = quotes.get('last') or quotes.get('close') or quotes.get('prevclose')
        return float(last) if last else None
    except Exception:
        return None


def main():
    print(f'\nOptions Scanner — {date.today()}')
    print(f'Target delta: {TARGET_DELTA} | DTE range: {MIN_DTE}-{MAX_DTE} days\n')

    print('Fetching VIX...')
    vix = get_vix()
    if vix:
        vix_label = 'LOW' if vix < 15 else 'NORMAL' if vix < 20 else 'ELEVATED' if vix < 30 else 'HIGH'
        print(f'  VIX: {vix:.2f} ({vix_label})\n')
    else:
        print('  VIX: unavailable\n')

    print('Fetching quotes...')
    try:
        prices = get_quotes(TICKERS)
    except Exception as e:
        print(f'Error fetching quotes: {e}')
        prices = {}

    all_results = []
    put_results = []
    for ticker in TICKERS:
        current_price = prices.get(ticker)
        if not current_price:
            print(f'  {ticker}: no quote, skipping')
            continue
        print(f'  Scanning {ticker} @ ${current_price:.2f}...')
        try:
            results = scan_ticker(ticker, current_price)
            all_results.extend(results)
            for r in results:
                print(f'    -> {r["type"]} {r["expiry"]} ${r["strike"]} delta={r["delta"]}')
        except Exception as e:
            print(f'  {ticker}: error — {e}')

        try:
            puts = scan_ticker(ticker, current_price, force_type='put')
            put_results.extend(puts)
        except Exception as e:
            print(f'  {ticker}: put scan error — {e}')

    print()
    # Sort by HV rank descending (best selling opportunities first)
    all_results.sort(key=lambda x: x.get('hv_rank') or 0, reverse=True)
    format_table(all_results)

    # Sort put scanner by ann_return descending
    put_results.sort(key=lambda x: x.get('ann_return') or 0, reverse=True)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    os.makedirs(out_dir, exist_ok=True)

    payload = {'generated': datetime.now().isoformat(), 'vix': vix, 'results': all_results, 'put_results': put_results}

    # JSON for external tooling
    with open(os.path.join(out_dir, 'scanner_results.json'), 'w') as f:
        json.dump(payload, f, indent=2)

    # JS file for dashboard.html (works from file:// without CORS issues)
    with open(os.path.join(out_dir, 'scanner_data.js'), 'w') as f:
        f.write('const SCANNER_DATA = ')
        json.dump(payload, f)
        f.write(';\n')

    print(f'\nSaved to output/scanner_results.json + output/scanner_data.js')
    print('\nNotes:')
    print('  HV Rank: 52-week realized volatility rank (proxy for IV rank). 100 = historically expensive.')
    print('  BB Position: where price sits in the 20-day Bollinger Band. 0% = lower band, 100% = upper band.')
    print('  Suggested side: Put if near lower band (<35%), Call if near upper band (>65%), Both if middle.')


if __name__ == '__main__':
    main()
