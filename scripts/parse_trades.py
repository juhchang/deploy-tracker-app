import csv
import glob
import json
import re
import os
from datetime import datetime

IGNORED_CODES = {'ACH', 'INT', 'CDIV', 'GDBP', 'SLIP', 'MISC'}


def parse_amount(s):
    if not s or not s.strip():
        return None
    s = s.strip().replace(',', '')
    negative = s.startswith('(') and s.endswith(')')
    s = s.strip('()').replace('$', '')
    try:
        v = float(s)
        return -v if negative else v
    except ValueError:
        return None


def parse_price(s):
    if not s or not s.strip():
        return None
    s = s.strip().replace(',', '').replace('$', '')
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s):
    if not s or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), '%m/%d/%Y').date()
    except ValueError:
        return None


def parse_option_desc(desc):
    """Parse 'TICKER M/D/YYYY Put $STRIKE' -> (ticker, expiry_date, opt_type, strike)"""
    m = re.match(r'^(\w+)\s+(\d+/\d+/\d{4})\s+(Put|Call)\s+\$(\d+(?:\.\d+)?)$', desc.strip())
    if m:
        ticker, date_str, opt_type, strike = m.groups()
        try:
            expiry = datetime.strptime(date_str, '%m/%d/%Y').date()
            return ticker, expiry, opt_type, float(strike)
        except ValueError:
            pass
    return None, None, None, None


def parse_file(csv_path):
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            act_date_str = row.get('Activity Date', '').strip()
            if not act_date_str:
                continue
            code = row.get('Trans Code', '').strip()
            if not code or code in IGNORED_CODES:
                continue

            act_date = parse_date(act_date_str)
            if not act_date:
                continue

            desc = row.get('Description', '').replace('\n', ' ').replace('\r', ' ').strip()
            desc = re.sub(r'\s+', ' ', desc)

            instrument = row.get('Instrument', '').strip()
            qty = parse_price(row.get('Quantity', ''))
            price = parse_price(row.get('Price', ''))
            amount = parse_amount(row.get('Amount', ''))

            parsed = {
                'date': act_date.isoformat(),
                'instrument': instrument,
                'description': desc,
                'code': code,
                'quantity': qty,
                'price': price,
                'amount': amount,
                'opt_ticker': None,
                'opt_expiry': None,
                'opt_type': None,
                'opt_strike': None,
            }

            if code in ('STO', 'BTC', 'BTO', 'STC', 'OASGN'):
                ticker, expiry, opt_type, strike = parse_option_desc(desc)
                parsed['opt_ticker'] = ticker
                parsed['opt_expiry'] = expiry.isoformat() if expiry else None
                parsed['opt_type'] = opt_type
                parsed['opt_strike'] = strike

            rows.append(parsed)
    return rows


def main():
    # Read all CSVs directly in data/ (not subdirectories like archive/)
    csv_files = sorted(glob.glob('data/*.csv'))

    if not csv_files:
        print("No CSV files found in data/ — add a Robinhood export and try again")
        return

    all_rows = []
    for path in csv_files:
        file_rows = parse_file(path)
        print(f"  {os.path.basename(path)}: {len(file_rows)} rows")
        all_rows.extend(file_rows)

    # Deduplicate across overlapping exports.
    # Strategy: for each unique key, keep N copies where N = the most times
    # that key appeared in any single file. This handles the case where you
    # legitimately sold the same option twice on the same day.
    from collections import Counter
    key_max = Counter()
    for path in csv_files:
        file_counts = Counter()
        for r in parse_file(path):
            file_counts[(r['date'], r['code'], r['description'], r['amount'])] += 1
        for key, count in file_counts.items():
            key_max[key] = max(key_max[key], count)

    seen_counts = Counter()
    rows = []
    for r in all_rows:
        key = (r['date'], r['code'], r['description'], r['amount'])
        if seen_counts[key] < key_max[key]:
            seen_counts[key] += 1
            rows.append(r)

    # Sort chronologically
    rows.sort(key=lambda r: r['date'])

    os.makedirs('output', exist_ok=True)
    with open('output/parsed_trades.json', 'w') as f:
        json.dump(rows, f, indent=2)
    print(f"Total: {len(rows)} unique rows from {len(csv_files)} file(s) → output/parsed_trades.json")


if __name__ == '__main__':
    main()
