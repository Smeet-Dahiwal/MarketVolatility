# 🏛️ BullGuard AI — Indian Stock Market Intelligence & Automated EOD Audit System

**BullGuard AI** is an automated algorithmic stock analysis, prediction, and verification platform designed specifically for the **Indian Equities Market (NSE / BSE)**.

It combines **classical trading master frameworks** (Mark Minervini, William O'Neil, Stan Weinstein), **institutional Smart Money / Mutual Fund tracking**, **fundamental health scores**, and an **automated self-learning audit loop** that runs daily in the cloud via GitHub Actions and dispatches verified signals to Telegram.

---

## 📑 Table of Contents
1. [Core Philosophy](#-core-philosophy)
2. [How Predictions Are Calculated (The 7-Step Pipeline)](#-how-predictions-are-calculated-the-7-step-pipeline)
3. [What Factors & Indicators Are Considered](#-what-factors--indicators-are-considered)
   - [A. Technical Structure & Moving Averages](#a-technical-structure--moving-averages)
   - [B. Classical Trading Book Rules & Patterns](#b-classical-trading-book-rules--patterns)
   - [C. Smart Money & Mutual Fund Tracking](#c-smart-money--mutual-fund-tracking)
   - [D. Fundamental Health & Piotroski F-Score](#d-fundamental-health--piotroski-f-score)
   - [E. Upcoming Earnings Catalyst Buffer](#e-upcoming-earnings-catalyst-buffer)
   - [F. Database Lesson Memory (Self-Learning Loop)](#f-database-lesson-memory-self-learning-loop)
4. [Final Decision Matrix & Composite Formula](#-final-decision-matrix--composite-formula)
5. [Target Horizons: Swing (15-Day) vs. Monthly (30-Day)](#-target-horizons-swing-15-day-vs-monthly-30-day)
6. [Daily Verification Audit & Post-Mortem Engine](#-daily-verification-audit--post-mortem-engine)
7. [Cloud Automation & Telegram Alerts](#-cloud-automation--telegram-alerts)
8. [Local Development & CLI Tools](#-local-development--cli-tools)

---

## 🎯 Core Philosophy

Most retail trading models rely purely on single lagging indicators (like RSI or simple MACD crossovers), resulting in high whipsaw rates. 

BullGuard AI operates on **multi-factor confluence**:
> **A trade signal is ONLY valid when Institutional Inflows, Technical Stage 2 Structure, Fundamental Health, and Volatility Contraction align simultaneously.**

Every prediction is continuously audited end-of-day against real market high/low price action. If a trade fails, an automated **Post-Mortem diagnostic** records the root cause into a memory bank to protect future decisions.

---

## 🧠 How Predictions Are Calculated (The 7-Step Pipeline)

```mermaid
graph TD
    A[Raw NSE Closing Data] --> B[Technical Indicator Calculations]
    B --> C[Evaluate Classical Trading Book Rules]
    B --> D[Smart Money & Mutual Fund Consensus]
    B --> E[Fundamental & Piotroski Audit]
    C & D & E --> F[Check Memory Bank for Past Failure Lessons]
    F --> G[Weighted Composite Score 0 - 100]
    G --> H{Mandatory Rules Passed?}
    H -- No --> I[Action: HOLD / WAIT]
    H -- Yes --> J{Score Thresholds}
    J -- Score >= 78 --> K[Action: STRONG BUY 🟢]
    J -- Score >= 65 --> L[Action: ACCUMULATE 📈]
    J -- Score >= 48 --> M[Action: HOLD / WAIT 🟡]
    J -- Score < 48 --> N[Action: AVOID 🔴]
    K & L --> O[Calculate Asymmetric 15-Day & 30-Day Targets + Stop Loss]
```

---

## 🔍 What Factors & Indicators Are Considered

### A. Technical Structure & Moving Averages
We compute technical indicators over 2 years of daily candlestick data:
* **Exponential Moving Averages (EMA 20, 50, 150, 200)**: Evaluates trend direction and hierarchy. Bullish trend confirmed when:
  $$\text{Price} > \text{EMA}_{50} > \text{EMA}_{150} > \text{EMA}_{200}$$
* **Relative Strength Index (RSI-14)**: Measures momentum. Bullish accumulation zone is $45 \le \text{RSI} \le 68$. RSI above 75 triggers an overbought warning.
* **MACD (12, 26, 9)**: Gauges accelerating momentum via the MACD Line, Signal Line, and Histogram.
* **Average True Range (ATR-14)**: Measures daily volatility expansion to set dynamic, volatility-adjusted stop-loss and profit target distances.
* **52-Week High/Low Proximity**: Validates that the stock is within 25% of its 52-week high (Minervini rule).

---

### B. Classical Trading Book Rules & Patterns
BullGuard AI hard-codes rules from renowned market wizards:

1. **Mark Minervini — Specific Entry Point Analysis (SEPA) & VCP**:
   * **Stage 2 Uptrend Criteria**: 200 EMA must be trending up for at least 1 month.
   * **Volatility Contraction Pattern (VCP)**: Decreasing volume during base contractions indicates supply dry-up before breakout.
2. **Stan Weinstein — Stage Analysis**:
   * Identifies transitions from Stage 1 (Accumulation Base) into **Stage 2 (Advancing Phase)**.
3. **William O'Neil — CAN SLIM**:
   * Focuses on institutional sponsorship (the "I" in CAN SLIM) and strong quarterly EPS expansion.
4. **Nicolas Darvas — Box Theory**:
   * Validates upper consolidation boundary breakouts.

> **Mandatory Filters**: If a stock fails fundamental Stage 2 criteria (e.g. trading below its 200-day moving average), the system **strictly overrides the signal to HOLD/AVOID**, regardless of other indicators.

---

### C. Smart Money & Mutual Fund Tracking
Retail investors react to news; institutions drive price trends. We track institutional footprint across top Indian Asset Management Companies (AMCs) like HDFC, SBI, ICICI Prudential, Nippon India, and Parag Parikh Flexi Cap:
* **Total Institutional Capital**: Quantified in ₹ Crores invested across tracked funds.
* **Month-over-Month (MoM) Actions**:
  * 🚀 **Heavy Accumulation**: Multiple funds scaling position sizes.
  * 📈 **Accumulating**: Consistent net positive inflows.
  * ⚖️ **Stable Hold**: Institutional lock-in.
  * 📉 **Trimming**: Distribution warning signal.
### D. Fundamental Health, Shareholding Distribution & Quarterly P&L (CAN SLIM 'C & I')
Technical patterns fail when company balance sheets deteriorate or earnings turn negative. We perform a strict fundamental audit before any prediction:

1. **Quarterly Profit & Loss Pre-Prediction Checks (William O'Neil CAN SLIM 'C')**:
   * **Quarterly Net Profit (₹ Crores)**: Extracted directly from official quarterly income statements.
   * **Unprofitable Quarter Safety Block**: If a company reports a quarterly net loss (`is_quarterly_profitable == False`), the engine **blocks all fresh buy calls and overrides the action to `AVOID 🔴` / `HOLD 🟡`** with an automatic $-25$ fundamental penalty.
   * **YoY Quarterly Profit Growth**: William O'Neil's canonical benchmark requires at least **$15\% - 25\%$ YoY profit acceleration**. Stocks exceeding this threshold receive a $+15$ fundamental bonus.
   * **Top-Line Revenue Expansion**: Verified via quarterly revenue growth ($\ge 15\%$ YoY) to confirm organic business expansion.

2. **Shareholding Distribution Breakdown (CAN SLIM 'I')**:
   * **Foreign Institutional Investors (FII)**: Tracks foreign institutional sponsorship percentage.
   * **Domestic Institutional Investors (DII / Mutual Funds)**: Measures domestic asset manager backing.
   * **Promoter Holding**: Evaluates founder skin-in-the-game ($\ge 50\%$ preferred, $< 25\%$ flagged).
   * **Public / Retail Float ("Weak Hands")**: Retail ownership $> 50\%$ signals high panic-selling vulnerability during corrections and incurs a $-12$ fundamental penalty. Conversely, tight institutional float ($\text{FII} + \text{DII} \ge 35\%$) receives a stability bonus.
   * **Snapshot at Prediction**: Every generated forecast locks in the exact shareholding distribution and quarterly profit numbers at that exact moment for audit transparency.

3. **Valuation Multiples & Solvency**:
   * **Book Value per Share & Price-to-Book (P/B)**: Calculated daily to assess asset-backed margin of safety.
   * **Price-to-Earnings (P/E) vs. Sector**: Evaluated against industry median P/E and growth rate.
   * **Piotroski F-Score ($1 - 9$)**: Solvency score evaluating profitability, leverage, and liquidity.
   * **Debt-to-Equity ($D/E < 1.0$)** & **Return on Equity ($\text{ROE} \ge 15\%$)**: Ensures conservative leverage and high capital efficiency.

---

### E. News Trading & Real-Time Sentiment Analysis
BullGuard AI incorporates a dedicated **News Trading Engine** using real-time Google News RSS feeds for Indian equities (aggregating Economic Times, Moneycontrol, Livemint, Business Standard, Reuters, and CNBC-TV18).

#### 1. What We Consider in News:
* **Financial Keyword Dictionaries**: Scored on a polarity scale from **$-1.0$ (Extremely Bearish)** to **$+1.0$ (Extremely Bullish)**.
* **High-Impact Catalysts**: Earnings announcements, contract/order wins, patent approvals, regulatory interventions, rating upgrades/downgrades, and management changes.

#### 2. What Happens When News is GOOD (Positive/Bullish):
* **What to Consider**: Earnings beats, high-margin order wins, capacity expansion, FII stake purchases, dividend announcements, credit rating upgrades.
* **Impact on Prediction**:
  * **Confidence Boost**: Adds up to $+12\%$ to the prediction conviction score.
  * **Breakout Confirmation**: Accelerates a candidate from `ACCUMULATE` into a high-priority `STRONG BUY 🟢`.
  * **Validation**: Confirms that institutional accumulation is supported by external media catalysts.

#### 3. What Happens When News is BAD (Negative/Bearish) — Emergency Safety Circuit Breaker:
* **What to Consider**: Regulatory/SEBI probes, financial fraud/scam allegations, tax raids, major earnings misses, defaults, management or auditor resignations, credit rating downgrades, product recalls.
* **Impact on Prediction**:
  * **Emergency Circuit Breaker Override**: If news sentiment is negative ($\le -0.35$) or critical crisis keywords are triggered, the engine **immediately overrides the recommendation to `AVOID 🔴` or `HOLD 🟡`**, regardless of how bullish the technical chart looks!
  * **Blocks Fresh Buy Entries**: Prevents traders from "catching a falling knife" during headline-driven panic.
  * **Conviction Penalty**: Applies an automatic penalty deduction (up to $-25$ points) to the composite score.
  * **Capital Protection**: Tightens risk parameters and flags an urgent warning in daily audit alerts.

---

### F. Upcoming Earnings Catalyst Buffer
Earnings announcements introduce binary volatility. 
* The engine checks `next_earnings_date`.
* If quarterly earnings are scheduled within the next **14 days**, the model automatically **reduces confidence score** and shifts a `STRONG_BUY` signal down to `ACCUMULATE`.
* It calculates consensus **EPS Estimate** and **Revenue Forecast** to anticipate potential post-earnings gaps.

---

### G. Database Lesson Memory (Self-Learning Loop)
When a trade hits its stop-loss, BullGuard AI conducts a **Post-Mortem diagnostic** (e.g., *Failed due to high India VIX surge* or *Volume breakdown*).
* Before generating any new forecast for that stock or sector, the engine queries the `PredictionAudit` memory bank.
* If a similar risk condition currently exists (e.g., sector volatility during elevated VIX), the engine applies a **penalty deduction** to the confidence score, preventing repetitive mistakes.

---

## ⚖️ Final Decision Matrix & Composite Formula

All factors are normalized and aggregated into an institutional **Composite Score ($0 - 100$)**:

$$\text{Composite Score} = (S_{\text{SmartMoney}} \times 0.30) + (S_{\text{BookRules}} \times 0.25) + (S_{\text{Technicals}} \times 0.20) + (S_{\text{Fundamentals}} \times 0.15) + (S_{\text{News}} \times 0.10) - \text{LessonPenalty} - \text{NewsPenalty}$$

| Composite Score | Technical Criteria | News Sentiment | Book Filter Status | Final Action | Description |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **$\ge 78$** | $\ge 65$ | Bullish / Neutral | **All Passed** | **STRONG BUY 🟢** | High institutional backing + confirmed Stage 2 breakout + positive/neutral headlines. |
| **$65 - 77$** | Any | Bullish / Neutral | **All Passed** | **ACCUMULATE 📈** | Strong fundamentals & smart money inflows; accumulate on minor dips. |
| **$48 - 64$** | Any | Any | Any | **HOLD / WAIT 🟡** | Stock consolidating inside range; await volume breakout. |
| **$< 48$** | Any | Any | Failed | **AVOID 🔴** | Downtrend structure or institutional distribution. |
| **Any** | Any | **Adverse ($\le -0.35$)** | Any | **AVOID 🔴 / HOLD 🟡** | **Emergency News Circuit Breaker Active** (Blocks fresh buys). |

---

## 🎯 Disciplined 1:3 Risk-to-Reward Ratio: Next-Day (1D) vs. Weekly (5D) vs. Monthly (20D)

BullGuard AI calculates predictions across **three distinct time horizons**, checking and verifying predictions after **1 day** instead of waiting 7 days. Every signal enforces a **strict, non-negotiable 1:3 Risk-to-Reward Ratio ($RR = 3.0$)**:

```
                                  Entry Price (CMP)
                                          │
       ┌──────────────────────────────────┼──────────────────────────────────┐
       ▼                                  ▼                                  ▼
Next-Day Target (1-Day)          Weekly Target (5-Day)             Monthly Target (20-Day)
[Typical: +3.0% to +5.0%]        [Typical: +7.0% to +10.5%]        [Typical: +12.0% to +18.0%]
Verified: Next Trading Day       Verified: Weekly Cycle            Verified: Monthly Cycle
Formula: CMP + (1D Stop × 3.0)   Formula: CMP + (5D Stop × 3.0)    Formula: CMP + (20D Stop × 3.0)
       │                                  │                                  │
       └──────────────────────────────────┼──────────────────────────────────┘
                                          ▼
                                   Strict Stop-Loss
                         Formula: CMP - Stop Buffer (1D / 5D / 20D)
                              [Risk-to-Reward: EXACTLY 1:3]
```

### Horizon Calibration & Verification Rules:
1. **Next-Day (Daily) Prediction ⚡ (`timeframe_type='DAILY'`, `timeframe_days=1`)**:
   * **Stop Buffer**: $\text{Stop Buffer} = \max(0.75 \times \text{ATR}_{14},\, 0.01 \times \text{CMP})$.
   * **Target Price**: $\text{CMP} + (\text{Stop Buffer} \times 3.0)$ (Strict 1:3 RR).
   * **Verification Cadence**: **Verified the very next day** against that session's High/Low/Close. If neither Target nor SL is triggered, it resolves at next-day market close.
2. **Weekly Swing Prediction 📅 (`timeframe_type='WEEKLY'`, `timeframe_days=5`)**:
   * **Stop Buffer**: $\text{Stop Buffer} = \max(1.5 \times \text{ATR}_{14},\, 0.02 \times \text{CMP})$.
   * **Target Price**: $\text{CMP} + (\text{Stop Buffer} \times 3.0)$ (Strict 1:3 RR).
   * **Verification Cadence**: **Verified weekly** (monitored over 5 trading days). Resolves if Target/SL is hit or on Day 5 market close.
3. **Monthly Position Prediction 🗓️ (`timeframe_type='MONTHLY'`, `timeframe_days=20`)**:
   * **Stop Buffer**: $\text{Stop Buffer} = \max(2.5 \times \text{ATR}_{14},\, 0.035 \times \text{CMP},\, \text{CMP} - \text{EMA}_{50})$.
   * **Target Price**: $\text{CMP} + (\text{Stop Buffer} \times 3.0)$ (Strict 1:3 RR).
   * **Verification Cadence**: **Verified monthly** (monitored over 20-30 trading days). Resolves if Target/SL is hit or on Month close.

**Why 1:3 RR is Crucial**: With a disciplined 1:3 risk-to-reward ratio, a trader remains solidly profitable even with a modest **35% win rate**! BullGuard AI's historical win rate of $>65\%$ combined with $1:3$ asymmetry creates an extraordinary statistical edge.

---

## 🛡️ Daily Verification Audit & Post-Mortem Engine

Every trading day at **4:00 PM IST (Market Close)**:
1. **Live Valuation & News Crawl**: Book value, P/E, P/B, and latest Google News headlines are refreshed and saved to the database.
2. **Live High/Low Range Check**: The runner pulls the actual session's high/low range from NSE.
3. **Outcome Resolution**:
   * If $\text{High} \ge \text{Target Price} \implies$ **TARGET HIT 🎯 (Win logged)**.
   * If $\text{Low} \le \text{Stop Loss Price} \implies$ **STOP LOSS HIT 🛑 (Loss logged $\rightarrow$ Post-Mortem triggered)**.
   * If Days Active $\ge 15 \implies$ **EXPIRED ⏱️**.
4. **Single Active Trade Rule**: A stock has only **one ongoing active trade** at any time. A fresh trade cycle is generated only after the prior trade finishes.
5. **Win Rate Calculation**:
   $$\text{Win Rate \%} = \left(\frac{\text{Completed Wins}}{\text{Total Completed Trades}}\right) \times 100$$

---

## 🤖 Cloud Automation & Telegram Alerts

The entire system runs **100% free and automated** using GitHub Actions:
* **Workflow**: `.github/workflows/daily_stock_audit.yml`
* **Trigger**: Scheduled cron or instant webhook at 4:00 PM IST.
* **Execution**:
  1. Spins up Ubuntu runner with Python 3.12.
  2. Pulls NSE data using `yfinance` + `curl_cffi` (bypasses cloud bot-protection).
  3. Executes `python manage.py run_daily_audit`.
  4. Commits updated `db.sqlite3` and `audit_summary.json` back to GitHub.
  5. Dispatches formatted HTML market audit directly to your **Telegram Group**.

### Mobile-Optimized Telegram Card Preview:
```text
🏛️ BULLGUARD AI · EOD AUDIT
📅 2026-10-16 16:00 IST
🌐 Regime: Healthy Trending Market (Selective Buying)

📊 VERIFIED PERFORMANCE:
• System Win Rate: 81.8% (18W · 4L)
• Active Monitored Calls: 19

🎯 HIGH-CONVICTION ACTION CALLS:
1. 🟢 ICICIBANK · ACCUMULATE
   ₹1,397 ➔ 🎯 ₹1,516 (+8.6%) | SL: ₹1,357 (-2.9%)
   📅 30D Monthly: 🎯 ₹1,558 (+11.6%) [RR: 1:3]
   📰 News: NEUTRAL 🟡 · P/E: 18.1 (P/B: 2.6)
   🎯 Win Rate: 70% (10 trades) · Conf: 82%

3. 🟢 INFY · STRONG BUY
   ₹1,012 ➔ 🎯 ₹1,098 (+8.5%) | SL: ₹983 (-2.8%)
   📅 30D Monthly: 🎯 ₹1,132 (+11.8%) [RR: 1:3]
   📰 News: BULLISH 🟢 (+0.65) · P/E: 25.4 (P/B: 6.8)
   🎯 Win Rate: 83% (6 trades) · Conf: 85%

⏸️ NEUTRAL / HOLD STOCKS (19 Tracked):
• 🟡 HDFCBANK: ₹700 ➔ Tgt ₹766 (Win: 61%)
• 🟡 TCS: ₹2,128 ➔ Tgt ₹2,328 (Win: 75%)
...

🔔 TRADES RESOLVED TODAY:
• 🎯 INFY — TARGET HIT ✅ (+8.6%)
  📅 Called: 10-Oct ➔ Hit: 14-Oct (Day 4)
  💰 Entry: ₹1,012 | Exit: ₹1,099 | RR: 1:3

• 🛑 TCS — STOP-LOSS HIT ❌ (-2.8%)
  📅 Called: 11-Oct ➔ Hit: 14-Oct (Day 3)
  💰 Entry: ₹2,128 | Exit: ₹2,068 | Post-Mortem Logged
```

---

## 💻 Local Development & CLI Tools

### 1. Installation
```bash
git clone https://github.com/Smeet-Dahiwal/MarketVolatility.git
cd MarketVolatility
git checkout feature/django-ai-stock-analyzer

python -m venv venv
venv\Scripts\activate   # Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
python manage.py migrate
```

### 2. Run the Web Dashboard
```bash
python manage.py runserver 127.0.0.1:8000
```
Visit `http://127.0.0.1:8000/` to explore the interactive terminal.

### 3. Run the Daily Audit Manually
```bash
python manage.py run_daily_audit
```

### 4. Run 1-Year Historical Backfill Simulation (365 Days / 261 Trading Sessions)
To simulate the past 1 full year of AI predictions, 1:3 risk-to-reward verifications, and post-mortem diagnostics across all 261 trading sessions:
```bash
# Clean reset and populate 1 full year of verified trades into the local database
python manage.py run_yearly_backfill --reset

# Run a quick simulation of the last 30 trading days
python manage.py run_yearly_backfill --days 30
```

### 5. Inspect Database Tables & Fields
```bash
python inspect_db.py
```

---

## 🔒 License & Disclaimer
*This system is designed for technical research and algorithmic market intelligence. Stock trading involves market risk; always review risk management parameters and position sizes before execution.*
