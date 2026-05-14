import json
from datetime import date, datetime, timedelta
from collections import defaultdict


def week_start(d):
    return d - timedelta(days=d.weekday())


def month_label(year, month):
    return datetime(year, month, 1).strftime('%b %Y')


def main():
    with open('output/parsed_trades.json') as f:
        rows = json.load(f)

    today = date.today()
    cur_week_start = week_start(today)
    cur_month_key = (today.year, today.month)

    # {(year,month): {sto, btc, count}}
    monthly = defaultdict(lambda: {'sto': 0.0, 'btc': 0.0, 'count': 0})
    # {ticker: {sto, btc}}
    by_ticker = defaultdict(lambda: {'sto': 0.0, 'btc': 0.0})
    # {ticker: {sto, btc}} — current month only
    cur_month_ticker = defaultdict(lambda: {'sto': 0.0, 'btc': 0.0})
    week = {'sto': 0.0, 'btc': 0.0}
    month = {'sto': 0.0, 'btc': 0.0}

    for row in rows:
        code = row['code']
        if code not in ('STO', 'BTC'):
            continue
        amount = row.get('amount') or 0.0
        d = date.fromisoformat(row['date']) if row.get('date') else None
        if not d:
            continue
        ticker = row.get('opt_ticker') or row.get('instrument') or 'UNKNOWN'
        mk = (d.year, d.month)

        if code == 'STO':
            monthly[mk]['sto'] += amount
            monthly[mk]['count'] += 1
            by_ticker[ticker]['sto'] += amount
            if d >= cur_week_start:
                week['sto'] += amount
            if mk == cur_month_key:
                month['sto'] += amount
                cur_month_ticker[ticker]['sto'] += amount
        else:  # BTC
            monthly[mk]['btc'] += amount
            by_ticker[ticker]['btc'] += amount
            if d >= cur_week_start:
                week['btc'] += amount
            if mk == cur_month_key:
                month['btc'] += amount
                cur_month_ticker[ticker]['btc'] += amount

    sorted_months = sorted(monthly.keys())
    monthly_list = []
    for mk in sorted_months:
        m = monthly[mk]
        monthly_list.append({
            'month': month_label(*mk),
            'sto': round(m['sto'], 2),
            'btc': round(m['btc'], 2),
            'net': round(m['sto'] + m['btc'], 2),
            'count': m['count'],
        })

    ticker_list = []
    for ticker, v in by_ticker.items():
        ticker_list.append({
            'ticker': ticker,
            'sto': round(v['sto'], 2),
            'btc': round(v['btc'], 2),
            'net': round(v['sto'] + v['btc'], 2),
        })
    ticker_list.sort(key=lambda x: x['net'], reverse=True)

    cur_month_ticker_list = []
    for ticker, v in cur_month_ticker.items():
        cur_month_ticker_list.append({
            'ticker': ticker,
            'sto': round(v['sto'], 2),
            'btc': round(v['btc'], 2),
            'net': round(v['sto'] + v['btc'], 2),
        })
    cur_month_ticker_list.sort(key=lambda x: x['net'], reverse=True)

    summary = {
        'current_week': {
            'label': f"Week of {cur_week_start.strftime('%b %d')}",
            'sto': round(week['sto'], 2),
            'btc': round(week['btc'], 2),
            'net': round(week['sto'] + week['btc'], 2),
        },
        'current_month': {
            'label': today.strftime('%B %Y'),
            'sto': round(month['sto'], 2),
            'btc': round(month['btc'], 2),
            'net': round(month['sto'] + month['btc'], 2),
        },
        'monthly': monthly_list,
        'by_ticker': ticker_list,
        'current_month_by_ticker': cur_month_ticker_list,
    }

    with open('output/summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    w = summary['current_week']
    m = summary['current_month']
    print(f"This week  — STO: ${w['sto']:,.2f}  BTC: ${w['btc']:,.2f}  Net: ${w['net']:,.2f}")
    print(f"This month — STO: ${m['sto']:,.2f}  BTC: ${m['btc']:,.2f}  Net: ${m['net']:,.2f}")
    print("Wrote output/summary.json")


if __name__ == '__main__':
    main()
