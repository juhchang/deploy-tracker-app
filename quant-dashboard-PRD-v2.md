# Quant Options Trading Dashboard — PRD v2

## Overview
An upgrade to an existing sophisticated options trading dashboard for an experienced premium seller. The goal is NOT to rebuild what exists — it is to add the missing quantitative guardrails, behavioral trading guards, and position recovery framework that removes emotional decision-making and replaces it with systematic rules.

**Primary problem to solve:** Emotional trading driven by income goal pressure — specifically end-of-month panic trading, greedy put timing, and false safety trades on underwater positions.

**Primary success metric:** Am I trading within my rules? (not: did I hit my dollar target)

---

## Existing Infrastructure — DO NOT REBUILD

The following is already built and working. Reference it, extend it, do not replace it.

### Existing Dashboards
- **dashboard.html** (746 lines) — original Robinhood trade history dashboard
  - VIX bar, Trade Opportunities (~0.25 delta scanner), Sell Put Scanner
  - Current Period Summary (weekly/monthly STO, BTC, Net)
  - YTD Premium by Month, YTD Net Premium by Ticker
  - Open Put Positions, Open Call Positions, Estimated Share Holdings
  - Capital Allocation Estimate, Assignment History

- **combined.html** (1,274 lines) — merged goal tracker + scanner
  - Monthly Progress, Market Sentiment & Deployment
  - YTD Goal Tracking, VIX Zone Reference
  - Capital Allocation, CSP Risk Guide
  - Trade Opportunities, Sell Put Scanner

### Existing Python Scripts
- **parse_trades.py** — reads Robinhood CSV, outputs parsed_trades.json and trade_data.js
- **calculate_premium.py** — computes weekly/monthly STO/BTC/Net rollups, share holdings, assignments → summary.json
- **collateral.py** — matches STO/BTC pairs, computes cash collateral for CSPs and share exposure for CCs
- **income_goal.py** — reads config.json + VIX + summary, computes gross target, required return %, VIX zone deployment rules → goal_metrics.js
- **scan_options.py** — calls Tradier API, finds ~0.25 delta contracts, computes Bollinger Band position and HV Rank → scanner_results.json, scanner_data.js
- **fetch_fear_greed.py** — fetches CNN Fear & Greed index → fear_greed.json
- **fetch_breadth.py** — fetches market breadth data

### Existing Config & Data
- **config.json** — account balance ($448,128), monthly net goal ($8,000), tax rate (30.3%), state (MA)
- **tickers.json** — 15 tickers on watchlist/scanner
- **data/robinhood_export.csv** — Robinhood export (Jan–Apr 2026)
- **data/starting_positions.json** — manually entered pre-CSV share positions
- **output/** — all generated JSON/JS files consumed by HTML dashboards

### Already Connected Data Sources
- Tradier API — options chains, Greeks, IV Rank, real-time quotes, 0.25 delta scanner
- VIX feed
- CNN Fear & Greed Index
- Market breadth data

---

## Trader Profile & Context

- 3 years options trading, 12 years investing
- Strategy: premium collection via short puts and covered calls
- Monthly net income target: $8,000 (mortgage + daycare), pre-tax ~$11,500
- Account balance: ~$448k collateral
- Watchlist: HOOD, PALANTIR, SOFI, TQQQ, AMAZON, NVIDIA, GOOGLE, BMNR, ETHU + other AI names
- Stock conviction: fundamentally bullish on most holdings — comfortable with assignment on puts, protective of shares on calls
- Key behavioral problem: income goal pressure causes emotional trading — greedy put timing, false safety trades on underwater positions, end-of-month panic

### Existing Trading Rules (already codified in scanner)
| Rule | Value |
|------|-------|
| Target delta | ~0.25 (puts and calls) |
| DTE range | 7–28 days |
| Target weekly return | ~1% |
| IV Rank threshold | >50 preferred |
| Early close signal | % gain > % time remaining |
| Cash reserve | VIX-dependent (already in income_goal.py) |
| Bollinger Band | Used for short-term directional read |
| Assignment comfort | Yes on puts — fundamentally bullish on holdings |

---

## What Is Net New — Build This

### 1. Position Status Framework (Most Important)

For every open stock position, calculate and display a color-coded status that drives all call-selling decisions:

| Status | Condition | Recommended Action |
|--------|-----------|-------------------|
| 🟢 Green | Stock at or above cost basis | Sell call normally at or above cost basis |
| 🟡 Yellow | Stock 5–15% below cost basis | Partial coverage (50–75%), sell at best available strike |
| 🔴 Red | Stock 15–30% below cost basis | Light coverage (25–50%), roll existing if needed |
| ⚫ Black | Stock 30%+ below cost basis OR no viable strike | Hold, do not sell calls, protect recovery upside |

**Partial Coverage Ratio Table** (shown per position):
| Distance from Cost Basis | Suggested Call Coverage |
|--------------------------|------------------------|
| At or above cost basis | 100% |
| Within 5% below | 100% |
| 5–15% below | 50–75% |
| 15–30% below | 25–50% |
| 30%+ below | 0–25% |

Display per position:
- Total shares held
- Shares currently covered by calls
- Current coverage ratio vs suggested coverage ratio
- Cost basis, current price, gap to cost basis
- Estimated weeks to recovery at current premium pace

### 2. False Safety Trade Detector

When a trader attempts to sell a call at 0.07 delta or lower on a ⚫ or 🔴 position, surface a pre-trade interrupt:

> "⚠️ Low delta trade on an underwater position detected.
> Strike: $X | Delta: 0.07 | Premium: $Y | Caps recovery at: $Z
> At current pace this position needs to reach $W to break even.
> Selling this call delays recovery by approximately N weeks.
>
> Is this trade based on:
> [Technical Analysis] or [Income Pressure]"

Do not block the trade — create a conscious pause. Log the reason selected for later performance review.

### 3. Put Entry Timing Framework

Extend the existing put scanner to score each opportunity on three factors simultaneously:

| Factor | Signal | Weight |
|--------|--------|--------|
| Premium quality | IV Rank > 50 | 35% |
| Price positioning | At or below middle Bollinger Band | 35% |
| Income urgency | Days remaining vs premium gap to goal | 30% |

**Income urgency score logic** (pull from existing income_goal.py):
- On track or ahead: urgency = Low → tighten entry criteria
- Slightly behind: urgency = Medium → standard criteria
- Significantly behind with few days left: urgency = High → flag as pressure trade, show warning

When urgency = High, show warning before trade:
> "⚠️ You are behind your monthly goal with X days remaining. This trade may be driven by income pressure rather than optimal entry timing. IV Rank is Y, Bollinger position is Z. Proceed?"

### 4. Total Position P&L View

Current dashboard tracks options premium only. Add a combined view per position:

- Options premium collected (from existing summary.json)
- Unrealized stock gain/loss (current price vs cost basis × shares held)
- **Total position P&L = premium collected + unrealized stock gain/loss**
- Display whether options income is offsetting stock loss or compounding stock gain

This gives the trader a complete picture of whether a position is actually working.

### 5. Effective Deployable Capital & Adjusted Goal

Current dashboard shows fixed $8,000 monthly goal against full $448k balance. Add:

- **Viable positions this month** — positions in 🟢 or 🟡 status only
- **Effective deployable capital** — capital in viable positions
- **Realistic premium target** — what $8k goal looks like against only deployable capital
- **Adjusted monthly goal** — if several positions are ⚫ or 🔴, surface a realistic target for this month
- **Gap to fixed goal** — how much requires new positions or accepting a lower month

This reframes the income goal so the trader isn't measuring themselves against a target that's unachievable with good trades in a given month.

### 6. Deployment Rate Tracker

Trader identified they don't deploy enough capital consistently. Add:

- % of available capital actively working (premium at risk / total deployable capital)
- Historical deployment rate by month — am I improving over time?
- Comparison: months with higher deployment vs lower — does income track deployment rate?
- VIX-adjusted deployment target — what deployment % is appropriate given current VIX zone

### 7. Roll Management Framework

For existing positions approaching expiry or in loss:

Per position, show:
- Current % gain
- % time remaining to expiry
- **Early close signal:** highlight when % gain > % time remaining (already a trader rule)
- Roll suggestion: if underwater near expiry — show best available roll strike, net debit/credit, weeks gained
- Delta drift alert: has delta moved significantly from entry delta?

Roll decision helper:
> "Position is X% loss with Y days remaining.
> Best roll: [Strike] [Expiry] | Net credit/debit: $Z | Buys N additional weeks"

### 8. Behavioral Trading Guards

**End-of-month risk creep detector:**
- Track buying power usage in final 7 days of month
- Alert if new positions opened in final week exceed average weekly deployment by >20%
- Flag: "You have opened more positions in the last 7 days than your monthly average. Review before continuing."

**Rules compliance score:**
- Daily score 0–100 based on: did trades taken today follow all defined rules?
- Show rolling 30-day compliance score
- Monthly compliance history — correlate with premium performance

**Trade score gate (extend existing scanner):**
Current scanner finds 0.25 delta opportunities. Extend scoring to 0–100:

| Criteria | Weight |
|----------|--------|
| Delta within 0.20–0.30 | 25pts |
| DTE within 7–28 days | 20pts |
| IV Rank > 50 | 25pts |
| Premium meets 1% weekly target | 20pts |
| Bollinger Band confirms direction | 10pts |

Score < 60 shows confirmation warning before trade entry.

### 9. Stress Test View (New Section)

Show estimated portfolio impact if market drops:
- 5% drop scenario
- 10% drop scenario  
- 15% drop scenario

Per scenario show:
- Estimated loss on open put positions (delta × price move × contracts)
- Estimated loss on stock holdings
- Buying power impact
- Which positions breach key support levels

> ⚠️ Flag TQQQ, BMNR, ETHU as leveraged/high-volatility — premium looks attractive but stress test impact is amplified.

### 10. Performance Analytics (New Section)

Calculate from existing Robinhood CSV history:

**Strategy performance:**
- Win rate by strategy type (puts vs calls)
- Win rate by underlying
- Average P&L per trade, per underlying

**Rules optimization:**
- DTE analysis: do 7-day or 28-day trades perform better?
- Delta analysis: does 0.20 or 0.30 delta perform better historically?
- IV Rank analysis: do trades entered at IV Rank > 50 outperform? (builds conviction in the rule)
- Fear & Greed analysis: do trades entered at sentiment extremes outperform?
- Deployment rate vs income: do higher deployment months produce proportionally more income?

**Behavioral performance:**
- False safety trade log: review trades flagged as potential pressure trades — how did they perform?
- End-of-month trades vs mid-month trades: do they underperform? (validates the behavioral guard)
- Trade rationale review: trades where journal entry noted income pressure — how did they perform vs conviction trades?

---

### 11. Trade Rationale Capture System

**Problem it solves:** Trader makes trades on Robinhood mobile, then loses the rationale by the time the CSV is uploaded. Emotion fills the gap where clear thinking used to be. Seeing your own words from when you entered a trade with a clear head is the most powerful emotional anchor when a position moves against you.

**Architecture — no paid APIs required, uses existing Google account:**

```
Google Form (mobile capture)
    ↓ auto-saves responses
Google Sheet (private storage)
    ↓ fetch_journal.py reads on CSV upload
output/journal_data.json
    ↓ matched to positions by ticker + date
dashboard.html / combined.html (notes field per position)
```

#### Google Form Setup (trader sets this up manually — 5 minutes)
Create a private Google Form with these fields:
- **Ticker** (short answer)
- **Put or Call** (dropdown: Put / Call)
- **Strike Price** (short answer)
- **Expiry Date** (short answer)
- **Why am I making this trade?** (paragraph)
- **Short term thesis on the stock** (paragraph)
- **What would make me wrong?** (paragraph)
- **Emotional check** (multiple choice: Full conviction / Mostly conviction, some pressure / Mostly pressure, some conviction / Pure income pressure)

Save Google Form URL as home screen shortcut on iPhone/iPad for one-tap access after every Robinhood trade.

Link form responses to a Google Sheet (automatic in Google Forms settings).

#### New Script: fetch_journal.py
- Reads from Google Sheet via Google Sheets API (free, uses existing Google account)
- Requires one-time OAuth setup — Claude Code will walk through this
- Outputs output/journal_data.json with all captured rationale entries
- Runs automatically as part of existing CSV upload pipeline alongside other fetch scripts

#### Dashboard Integration
In open positions tables (both dashboard.html and combined.html), add per position:
- **Rationale field** — shows matched journal entry if exists, blank if not
- **Emotional check indicator** — color coded dot showing conviction level at entry:
  - 🔵 Full conviction
  - 🟡 Mixed
  - 🔴 Pressure trade
- **Manual notes field** — always editable, for trades with no capture or additional context added later
- After position closes — rationale and emotional check move to performance history for review

#### Emotional Pattern Tracking
In Performance Analytics section, add:
- Win rate by emotional check category — do conviction trades outperform pressure trades?
- Average P&L: full conviction vs pressure trade entries
- This is the data that will build lasting behavioral change over time

---

## Session Guide for Claude Code

Work through these sessions in order. Start each session by reading this PRD and the existing codebase summary before writing any code. At the end of every session, run the Claude verification steps first, then hand off to the trader for human verification before starting the next session.

---

### Session 1 — Position Status Framework + Cost Basis Integration
**Goal:** Get cost basis data into the dashboard and show position status colors

**Build:**
- Read collateral.py and starting_positions.json to understand current position tracking
- Add cost basis per position (may need manual input for positions predating CSV)
- Calculate distance from cost basis for each holding
- Render position status (🟢🟡🔴⚫) in existing open positions tables in dashboard.html and combined.html
- Add partial coverage ratio suggestion per position
- **Do not touch scanner or goal tracker yet**

**Claude verifies:**
- [ ] collateral.py runs without errors after changes
- [ ] Every open position has a cost basis value — no nulls or blanks
- [ ] Position status displays for all positions — no missing or undefined statuses
- [ ] Partial coverage ratio calculates correctly for a sample position at each status level (🟢🟡🔴⚫)
- [ ] Existing dashboard sections (VIX bar, scanner, summary) still render correctly — nothing broken

**You verify:**
- [ ] Open dashboard.html and combined.html in browser — do positions show correct status colors?
- [ ] Pick 2-3 positions you know well — does the cost basis match what you paid?
- [ ] Does the partial coverage ratio suggestion make intuitive sense for each position?
- [ ] Does anything look visually broken or out of place?

---

### Session 2 — Total P&L View + Effective Deployable Capital
**Goal:** Show complete picture of what each position is actually doing

**Build:**
- Add unrealized stock gain/loss per position using current price vs cost basis
- Calculate total position P&L (premium collected + unrealized stock gain/loss)
- Add effective deployable capital calculation (viable positions only)
- Add adjusted monthly goal view to existing goal tracker section in combined.html
- Add deployment rate tracker

**Claude verifies:**
- [ ] Total P&L calculation is correct: premium + unrealized stock gain/loss = total
- [ ] Effective deployable capital only includes 🟢 and 🟡 positions
- [ ] Adjusted monthly goal is lower than fixed $8k goal when ⚫/🔴 positions exist
- [ ] Deployment rate % calculates correctly against total available capital
- [ ] All existing Session 1 features still work — run full pipeline end to end

**You verify:**
- [ ] Pick one position you're up on and one you're down on — does total P&L look right?
- [ ] Does effective deployable capital feel like an accurate picture of what you can actually trade this month?
- [ ] Does the adjusted monthly goal feel more realistic than the fixed $8k when positions are underwater?
- [ ] Does deployment rate % match your gut feel of how much capital you have working?

---

### Session 3 — Behavioral Trading Guards + False Safety Detector
**Goal:** Add the pre-trade interrupts and compliance scoring

**Build:**
- Add false safety trade detector to scanner output — flag any 0.07 delta or lower on ⚫/🔴 positions
- Add put entry timing framework scoring (IV Rank + Bollinger + income urgency) to scan_options.py output
- Add income urgency warning to goal tracker when significantly behind with few days left
- Add end-of-month risk creep detector — alert when final week deployment exceeds monthly average by >20%
- Add rules compliance score (0–100) to dashboard

**Claude verifies:**
- [ ] False safety detector fires correctly on a simulated 0.07 delta trade against a ⚫ position
- [ ] False safety detector does NOT fire on a 0.25 delta trade against a 🟢 position
- [ ] Put entry timing score produces a value between 0–100 for every scanner result
- [ ] Income urgency warning triggers when goal gap is large and days remaining are few
- [ ] Income urgency warning does NOT trigger when on track or ahead of goal
- [ ] End-of-month detector logic is correct — test against last month's trade history
- [ ] Rules compliance score calculates without errors
- [ ] All previous session features still intact — run full pipeline

**You verify:**
- [ ] Look at current scanner results — does the put entry timing score feel right for each opportunity?
- [ ] Find a position in ⚫ or 🔴 status in scanner — does the false safety warning appear as expected?
- [ ] Does the income urgency warning reflect where you actually are vs your goal right now?
- [ ] Does the rules compliance score feel like an honest reflection of your recent trading?

---

### Session 4 — Trade Rationale Capture System
**Goal:** Connect Google Sheets journal to dashboard

**Pre-session requirement:** Trader must have Google Form and linked Google Sheet set up before this session starts. Share the Google Sheet ID with Claude Code.

**Build:**
- Set up fetch_journal.py to read from Google Sheet via Google Sheets API
- Walk trader through one-time OAuth setup for Google Sheets access
- Output output/journal_data.json
- Integrate fetch_journal.py into existing pipeline — runs automatically on CSV upload
- Add rationale field to open positions tables in dashboard.html and combined.html
- Add emotional check color indicator (🔵🟡🔴) per position
- Add always-editable manual notes field per position
- Ensure rationale and emotional check move to performance history when position closes

**Claude verifies:**
- [ ] fetch_journal.py connects to Google Sheet and pulls data without errors
- [ ] journal_data.json is correctly formatted and contains all form submissions
- [ ] Trade matching works — entries match to positions by ticker + approximate date
- [ ] Rationale field displays correctly for a matched position
- [ ] Emotional check indicator renders the correct color for each category
- [ ] Manual notes field is editable and saves correctly
- [ ] Pipeline runs end to end including journal fetch without errors
- [ ] All previous session features still intact

**You verify:**
- [ ] Submit a test entry in your Google Form — does it appear on the dashboard after running the pipeline?
- [ ] Does the emotional check color look right for your test entry?
- [ ] Edit the manual notes field on a position — does it save?
- [ ] Does the rationale field display cleanly next to the position without breaking the table layout?

---

### Session 5 — Roll Management + Stress Test
**Goal:** Add roll decision helper and downside scenario modeling

**Build:**
- Add early close signal highlighting — flag when % gain > % time remaining
- Add roll suggestion logic to open positions tables — show best available roll strike, net debit/credit, weeks gained
- Add delta drift alert — flag positions where delta has moved significantly from entry
- Build stress test view as new section — 5%, 10%, 15% market drop scenarios
- Flag TQQQ, BMNR, ETHU as leveraged/high-volatility in scanner and stress test

**Claude verifies:**
- [ ] Early close signal fires correctly — test with a position at 60% gain and 40% time remaining
- [ ] Early close signal does NOT fire on a position at 30% gain and 60% time remaining
- [ ] Roll suggestion pulls a real available strike from Tradier API for a sample position
- [ ] Stress test calculates estimated P&L impact for all three scenarios (5/10/15%)
- [ ] Leveraged tickers (TQQQ, BMNR, ETHU) show amplified stress test impact and warning flag
- [ ] Delta drift alert fires on a position that has moved significantly
- [ ] All previous session features still intact — run full pipeline

**You verify:**
- [ ] Look at your current open positions — does the early close signal appear on any that are past the threshold?
- [ ] Pick one underwater position — does the roll suggestion show a realistic strike and credit/debit?
- [ ] Look at the stress test — does a 10% market drop scenario feel like a realistic estimate of your risk?
- [ ] Do the leveraged ticker warnings stand out visually enough to catch your attention?

---

### Session 6 — Performance Analytics
**Goal:** Surface historical patterns from existing trade data

**Build:**
- Build performance analytics section using existing parsed_trades.json and summary.json
- Win rate by strategy type (puts vs calls) and by underlying
- DTE analysis — 7-day vs 28-day trade performance
- Delta analysis — 0.20 vs 0.30 delta performance
- IV Rank entry analysis — do >50 IV Rank trades outperform?
- Fear & Greed entry analysis — do extreme sentiment entries outperform?
- Deployment rate vs income correlation by month
- Behavioral performance — end-of-month trades vs mid-month trades
- Emotional pattern analysis — conviction trades vs pressure trades (from journal data)

**Claude verifies:**
- [ ] Win rate calculations are correct — verify manually against a known subset of trades
- [ ] DTE and delta analysis buckets trades correctly — no trades in wrong categories
- [ ] IV Rank analysis only includes trades where IV Rank was captured at entry
- [ ] Emotional pattern analysis only runs if journal data exists — graceful fallback if not
- [ ] All charts and tables render without errors
- [ ] All previous session features still intact — run full pipeline end to end

**You verify:**
- [ ] Does your overall win rate look right based on your experience?
- [ ] Does the DTE or delta analysis surface anything surprising about your own performance?
- [ ] Does the end-of-month vs mid-month comparison confirm or challenge your intuition about emotional trading?
- [ ] After a few months of journal data — does the conviction vs pressure trade comparison show a clear pattern?
- [ ] Is there anything in the analytics that changes how you want to trade going forward?

---

## Out of Scope (V1)
- Direct Robinhood API connection (CSV upload only)
- Automated trade execution
- Tax optimization engine
- Multi-account support
- Anthropic API integration (no additional cost tools only)

---

## Success Criteria
1. Trader can see position status (🟢🟡🔴⚫) at a glance for every holding
2. False safety trade detector fires before a low-delta trade on an underwater position
3. Put entry timing score surfaces when all three factors align — not just delta
4. Total P&L view shows whether positions are actually working including stock movement
5. Adjusted monthly goal reflects realistic deployable capital not just fixed $8k
6. Stress test shows estimated loss on 10% market drop within 30 seconds of opening dashboard
7. Trade rationale captured on phone within 60 seconds of Robinhood trade and visible on dashboard at next CSV upload
8. Emotional pattern data shows measurable performance difference between conviction trades and pressure trades after 3 months of use
9. End-of-month compliance score is measurably tracked over time
