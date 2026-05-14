# Options Income Dashboard — Claude Code Instructions

## PRD Reference
**Before starting any session, find and read the newest `quant-dashboard-PRD-v*.md` file in the project root** (highest version number). It defines all planned sessions, what to build, what not to rebuild, and the verification checklist for each session.

## Project Overview
This project tracks options premium income and collateral from a Robinhood account.
The goal is to produce a local dashboard (dashboard.html) from a CSV export, showing
weekly/monthly premium collected, collateral tied up in open positions, and assignment history.

## My Trading Style
- I primarily sell options for income: cash-secured puts (CSPs) and covered calls (CCs)
- I also hold some LEAPS (long-dated calls as bullish positions, not income)
- I roll positions frequently rather than take assignment — but assignments do happen
- I trade on a weekly or bi-weekly cycle
- Tickers I commonly trade: TQQQ, HOOD, SOFI, PLTR, BMNR, NVDA, GOOGL, AAPL, AMZN, BITX, ETHU, TNA, MSFT, IREN, TEM, COST, LMND

## Data Source
- CSV exported manually from robinhood.com → Profile icon → Account → Reports and Statements → Activity → Download CSV
- Note: export is only available on the web (robinhood.com), NOT the mobile app
- Robinhood only provides 1 year of history — download a fresh export monthly
- File lives at: data/robinhood_export.csv
- Past exports are archived in: data/archive/

## Actual CSV Column Format
My Robinhood export has these exact columns:
- Activity Date — date the trade occurred (format: M/D/YYYY)
- Process Date — date processed
- Settle Date — settlement date
- Instrument — ticker symbol (e.g. TQQQ, HOOD)
- Description — full description of the trade (e.g. "TQQQ 5/1/2026 Put $40.00")
- Trans Code — transaction type (see codes below)
- Quantity — number of contracts or shares
- Price — price per share/contract (formatted as $X.XX)
- Amount — total dollar amount (positive = credit, negative in parentheses = debit)

## Transaction Code Reference
| Code  | Meaning                                      | Income Trade? |
|-------|----------------------------------------------|---------------|
| STO   | Sell to Open — opening a short option        | YES           |
| BTC   | Buy to Close — closing a short option        | no (cost)     |
| BTO   | Buy to Open — buying a LEAP or long option   | no (cost)     |
| STC   | Sell to Close — selling a long option        | no (separate) |
| OASGN | Option Assignment notification               | no (flag)     |
| Buy   | Share purchase (often from assignment)       | no            |
| Sell  | Share sale (often from call assignment)      | no            |
| ACH   | Cash deposit or withdrawal                   | ignore        |
| INT   | Interest payment                             | ignore        |
| CDIV  | Cash dividend                                | ignore        |
| GDBP  | Gold Deposit Boost Payment                   | ignore        |
| SLIP  | Stock Lending Income Payment                 | ignore        |
| MISC  | Miscellaneous (cash rewards, etc.)           | ignore        |

## Key Metrics I Care About
1. Premium collected this week — sum of STO Amount values for current week (Mon-Sun)
2. Premium collected this month — sum of STO Amount for current calendar month
3. BTC costs this week/month — sum of BTC Amount values (always negative); show separately alongside STO
4. Net premium = STO credits + BTC costs (BTC is negative, so this is STO minus BTC spend)
5. Number of STO trades per month — count of STO rows, shown alongside premium totals
6. Open put positions — STOs with no matching BTC, expiry >= today, option type = Put
7. Open call positions (covered calls) — STOs with no matching BTC, expiry >= today, option type = Call
8. Cash collateral in open CSPs — strike × 100 × open contracts for each open put
9. Covered call share exposure — contracts × 100 shares per contract; show shares held vs shares in calls
10. Share holdings — net Buy minus Sell for each ticker across all history; use last recorded transaction price
11. Assignment history — all OASGN events, what was assigned, at what strike
12. P&L by ticker — how much net premium per underlying

## Premium Reporting Format
Always show three columns when breaking down premium by ticker or time period:
- STO (collected) — gross credits from selling options
- BTC (cost) — debits from buying to close (show as negative)
- Net — STO + BTC combined

When showing monthly breakdown, also include a # STOs column (count of STO trades that month).

## Full Dashboard Layout
When asked for the full dashboard, show all sections in this order:

1. **Current Period Summary** — this week and this month side by side: STO, BTC, Net
2. **YTD Premium by Month** — columns: Month, # STOs, STO, BTC, Net; total row at bottom
3. **YTD Net Premium by Ticker** — columns: Ticker, STO, BTC, Net; sorted by Net descending
4. **Open Put Positions (Cash Collateral)** — columns: Expiry, Ticker, Contracts, Strike, Collateral (strike×100×contracts); total collateral at bottom; only show expiry >= today
5. **Open Call Positions (Covered Calls)** — columns: Expiry, Ticker, Contracts, Strike, Shares Required; then a sub-table showing Ticker, CC Contracts, Shares in CC, Shares Held, Last Price, Position Value (shares in CC × last price); total at bottom
6. **Estimated Share Holdings** — columns: Ticker, Shares, Last Price, Est. Value; last price = most recent Buy or Sell transaction price for that ticker; total at bottom
7. **Capital Allocation Estimate** — cash in open CSPs + value of shares in covered calls = total options-related capital deployed; note that % of portfolio requires knowing account balance; note prices are last recorded, not real-time
8. **Assignment History** — chronological list of OASGN events with the corresponding Buy/Sell share transaction on the next line

## Open Position Detection
- Match STO and BTC rows by exact Description string
- Net open contracts = sum(STO qty) - sum(BTC qty) for that description
- Only show positions where net > 0 AND expiry date >= today
- Parse option type (Put/Call) and strike from the Description field: format is "TICKER M/D/YYYY Put $STRIKE" or "TICKER M/D/YYYY Call $STRIKE"
- Positions with expiry < today have expired or been assigned — exclude from open positions

## Share Holdings Tracking
- Track net shares per ticker by summing all Buy (+qty) and Sell (-qty) rows across full history
- Use the most recent Buy or Sell transaction price per ticker as "last known price"
- Negative share counts mean shares were sold/called away before the CSV history begins — show but note they are negative
- Covered calls require 100 shares per contract; flag if shares held < shares required for open calls

## Amount Field Parsing
- Positive amounts are plain: $423.90
- Negative amounts use parentheses: ($75.04) — these are debits/costs
- Strip $, comma and convert (X) to -X before any math

## LEAPS — Handle Separately
- BTO trades with expiry > 6 months out are LEAPS, not income trades
- Track LEAPS separately — they are capital invested, not premium collected
- Examples in my data: SOFI 1/15/2027 Call, AMZN 6/17/2027 Call, NFLX 1/15/2027 Call

## Assignment Logic
An assignment appears as TWO rows:
1. OASGN row — the assignment notification (no dollar amount)
2. Buy or Sell row — the actual share transaction at the strike price

Put assignment example (received shares):
  3/27/2026 | TQQQ | TQQQ 3/27/2026 Put $45.00 | OASGN | 1 contract
  3/27/2026 | TQQQ | ProShares UltraPro QQQ ... 1 TQQQ Option Assigned | Buy | 100 shares | $45.00 | ($4,500.00)

Call assignment example (shares sold away):
  1/16/2026 | AMZN | AMZN 1/16/2026 Call $230.00 | OASGN | 1 contract
  1/16/2026 | AMZN | Amazon ... 1 AMZN Option Assigned | Sell | 100 shares | $230.00 | $22,999.98

## File Structure
options-trading/
├── data/
│   ├── robinhood_export.csv      # latest export (replace monthly)
│   └── archive/                  # older exports for historical data
├── scripts/
│   ├── scan_options.py           # live options scanner — pulls ~0.25 delta contracts from Tradier
│   ├── parse_trades.py           # cleans and categorizes the CSV
│   ├── calculate_premium.py      # weekly/monthly premium rollups
│   └── collateral.py             # estimates collateral for open positions
├── dashboard.html                # visual output — open in any browser
├── output/
│   ├── scanner_results.json      # output from scan_options.py
│   └── summary.json              # intermediate data from Robinhood scripts
├── .env                          # Tradier API key (never commit)
├── requirements.txt              # pip dependencies
└── CLAUDE.md                     # this file

## How to Regenerate the Dashboard
When I drop a new CSV into data/, run:
  python3 scripts/parse_trades.py
  python3 scripts/calculate_premium.py
  python3 scripts/collateral.py
Then open dashboard.html in a browser. No server needed.

## Live Options Scanner
Run anytime to refresh trade opportunities:
  python3 scripts/scan_options.py

To add or remove tickers, edit tickers.json — the scanner reads it automatically on each run.

This pulls from the Tradier sandbox API and writes output/scanner_results.json,
which dashboard.html reads automatically on load.

### What the scanner does
- Fetches options chains for all tickers with greeks=true
- Finds the contract closest to 0.25 delta for each expiry in the 7–45 DTE window
- Calculates 20-day Bollinger Band position to suggest Put or Call side
- Calculates 52-week HV Rank (realized volatility rank) as an IV rank proxy
- Suggests Put if price is near lower BB (<35%), Call if near upper BB (>65%), Both if middle
- Sorts output by HV Rank descending (highest = most expensive options = best premium to sell)

### Scanner columns
- BB Position: where price sits in the 20-day BB (0% = lower band, 100% = upper band)
- Suggested: which side to sell based on BB position
- Delta: absolute value; puts are negative in the raw data but shown as positive
- IV%: implied volatility from Tradier greeks (mid_iv × 100)
- HV Rank: 52-week historical volatility rank (0–100); proxy for IV rank since Tradier sandbox
  does not provide historical IV; 100 = historically high volatility = richer premium

### API key
- Stored in .env as TRADIER_API_KEY
- Sandbox key gives real market data for free (paper trading tier at tradier.com)
- Sandbox base URL: https://sandbox.tradier.com/v1

## Dashboard Display Preferences
- Show dollar amounts with 2 decimal places and $ sign
- Use green for premium income / net credits, red for costs and assignments
- Week starts on Monday
- Sort open positions tables by expiry date ascending (soonest first)
- Summary bar: show current week AND current month premium side by side
- Flag assignments in a separate section — they affect collateral significantly
- In covered call sub-table, flag tickers where shares held < shares required for open calls

## Income Goal Framework

The primary goal of this project is to generate **$10,000/month after taxes** from selling options.

### Monthly Target Math
- Household income (excl. options): ~$250,000/year (wife's salary + RSUs)
- State: Massachusetts — 5% flat income tax
- Filing: Married Filing Jointly
- Options income is short-term, taxed as ordinary income
- Federal marginal rate on options income: 24% (up to ~$394k combined) then 32%
- Blended effective rate on options income: **~30%**
- **Gross monthly target: ~$14,343** (must collect this much before taxes to net $10,000)

### VIX-Based Cash Allocation Rules
Keep a cash reserve that scales inversely with fear — more fear = less cash needed (deploy more):

| VIX Range | Zone Label     | Cash to Hold | Deployable Capital |
|-----------|----------------|--------------|--------------------|
| < 12      | Extreme Greed  | 40 – 50%     | 50 – 60%           |
| 12 – 15   | Greed          | 30 – 40%     | 60 – 70%           |
| 15 – 20   | Slight Fear    | 20 – 25%     | 75 – 80%           |
| 20 – 25   | Fear           | 10 – 15%     | 85 – 90%           |
| 25 – 30   | Very Fearful   | 5 – 10%      | 90 – 95%           |
| ≥ 30      | Extreme Fear   | 0 – 5%       | 95 – 100%          |

Required monthly return % = gross monthly target / deployable capital. Show as a range matching the cash % band.

### Capital Allocation — CSP vs CC Split
Of the deployable capital:
- **Covered calls** use shares already held — no new cash required, just need 100 shares per contract
- **Cash-secured puts** consume cash: strike × 100 × contracts
- Available for new CSPs = deployable capital − share holdings value − existing open CSP collateral

### Goal Tracker Tool
A separate dashboard (`goal_tracker.html`) tracks the income goal. It reads:
- `config.json` — account balance, monthly net goal, household income, state tax rate
- `output/vix.json` — current VIX (from `scripts/fetch_vix.py`)
- `output/summary.json` — current month premium progress
- `output/goal_metrics.js` — computed by `scripts/income_goal.py`

To regenerate:
  python3 scripts/fetch_vix.py
  python3 scripts/parse_trades.py
  python3 scripts/calculate_premium.py
  python3 scripts/income_goal.py
Then open goal_tracker.html in a browser.

## Workflow Preferences
- **Always present a written plan first** before building anything non-trivial
- **Always build a static HTML mockup with fake/illustrative data** before wiring up real scripts or data — let the user approve the design first
- Break large builds into discrete pieces and confirm before executing each

## Notes for Claude
- The CSV may have a blank last row — skip it
- Some Description fields contain newlines for multi-line assignment descriptions — parse carefully
- When I say "how much premium did I collect", count only STO amounts
- When I say "net" premium, subtract BTC costs from STO credits
- If I mention a ticker, assume it is options unless I say "shares" or "stock"
- Assignments mean I now own (or sold) shares — factor that into collateral tracking
- I have been assigned on: SOFI, HOOD, PLTR, BMNR, ETHU, TQQQ, TNA — I may hold shares from those
