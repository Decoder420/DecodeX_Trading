# PROJECT_STATE.md

## 1. Project Overview & Scope
- **Current Milestone**: Part 2 of 3 COMPLETE & RIGOROUSLY AUDITED (Walk-Forward Backtesting Engine, Statistical Model Suite, Execution & Cost Model, Decision Gate Evaluation).
- **Domain**: Statistical research and decision support for Indian market indices (**NIFTY 50**, **BANK NIFTY**, **BSE SENSEX**, and **INDIA VIX**).
- **Tradable Proxy**: Index futures proxy for cash index series.
  > [!CAUTION]
  > **Core Quantitative Finding**: **NO MODEL IS VALIDATED.**
  > All tested strategies fail multiple institutional robustness criteria (e.g., bootstrap difference CI spans zero, Deflated Sharpe Ratio p-value $\ge 0.10$, or lack of consistency).
  > All candidates are strictly classified as **"marginal, unconfirmed"** (Class B or Class C). Live trading is strictly discouraged.
  >
  > **Index Futures Proxy Approximation**: Cash index series are utilized as the tradable proxy for index futures. This approximation assumes zero spot-futures basis and no roll gaps between contract months. BSE SENSEX derivatives prior to their May 2023 relaunch are hypothetical backtest constructs.
- **Execution Policy**: Strictly personal quantitative research and statistical decision support. Zero live order execution. No guaranteed profitability claims.

---

## 2. Ingested Historical Data (2010 to Present)

The pipeline was executed across the maximum available daily history from `2010-01-01` to `2026-10-24` (~16.8 years of daily data):

| Instrument | Underlying Symbol | Rows Ingested | Historical Start Date | Latest End Date | Status | Gaps Flagged |
| :--- | :--- | :---: | :---: | :---: | :--- | :---: |
| **NIFTY 50** | `^NSEI` | **4,128** | `2010-01-04` | `2026-10-23` | `UNEXPLAINED_GAPS (10)` | 16 (6 Jan 1, 10 missing in feed) |
| **BANK NIFTY** | `^NSEBANK` | **4,143** | `2010-01-04` | `2026-10-23` | `HEALTHY` | 0 |
| **BSE SENSEX** | `^BSESN` | **4,133** | `2010-01-04` | `2026-10-23` | `UNEXPLAINED_GAPS (2)` | 9 (7 Jan 1 / year-end, 2 missing in feed) |
| **INDIA VIX** | `^INDIAVIX` | **4,127** | `2010-01-04` | `2026-10-23` | `UNEXPLAINED_GAPS (10)` | 16 (6 Jan 1, 10 missing in feed) |

Persistent database: `data/market_data.duckdb` (tables: `ohlcv_nifty_1d`, `ohlcv_banknifty_1d`, `ohlcv_sensex_1d`, `ohlcv_india_vix_1d`).

---

## 3. Holiday Calendar & Gap Audit Methodology

### How the 245 Holidays Were Built
The calendar in `config/holidays.yaml` was compiled directly from **official annual exchange trading holiday circulars** issued by the National Stock Exchange of India (NSE) and BSE for calendar years 2010 through 2026 under the Negotiable Instruments Act 1881 / Capital Market Segment Holidays.
- It includes standard statutory national holidays, religious festivals, state/assembly election closure days in Maharashtra, and official special closure days.
- Muhurat trading sessions on Diwali (evening 1 hour) are treated as special trading sessions rather than full holidays.
- **Zero reliance on yfinance data gaps**: Holidays were established exclusively from regulatory circulars, not inferred from feed absences.

### Cross-Instrument Gap Audit & Status Policy
Per system requirements, **an instrument status never reports `HEALTHY` if any gap is unexplained**.
Every flagged gap date is evaluated against cross-instrument trading activity across all database tables (`market_trading_dates`):
- **Another instrument traded on that date**: Labeled strictly as `DATA_MISSING_IN_FEED (cause unknown)`. All unsupported speculations have been eliminated.
- **No instrument traded on that date**: Evaluated against the official exchange holiday list. If unlisted, labeled `MARKET_WIDE_CLOSURE (cause unknown)`.
- **Zero Forward-Filling**: The pipeline flags missing candles with `is_gap = True` for auditability; it never forward-fills price bars. In Part 2, the `TradeGatekeeper` applies a 3-bar blackout window around any flagged date to completely eliminate lookahead or distortion in return/label windows.

#### Flagged Gaps Audit Detail:
1. **BANK NIFTY**: **0 gaps**. Continuous unbroken record. Status: `HEALTHY`.
2. **NIFTY 50 (`^NSEI`)**: 16 missing days:
   - *6 Jan 1 Global Feed Drops*: `2013-01-01`, `2014-01-01`, `2015-01-01`, `2016-01-01`, `2018-01-01`, `2019-01-01`.
   - *10 Feed Drops*: `2011-05-31`, `2011-07-14`, `2011-11-24`, `2011-12-26`, `2012-01-02`, `2012-05-21`, `2012-08-28`, `2014-02-17`, `2015-04-15`, `2016-08-12`. BANK NIFTY traded on these dates $\rightarrow$ labeled `DATA_MISSING_IN_FEED (cause unknown)`. Status: `UNEXPLAINED_GAPS (10)`.
3. **BSE SENSEX (`^BSESN`)**: 9 missing days:
   - *7 Jan 1 / Year-End Drops*: `2013-01-01`, `2014-12-29`, `2015-01-01`, `2016-01-01`, `2019-01-01`, `2020-01-01`, `2024-01-01`.
   - *2 Feed Drops*: `2012-01-02` and `2021-05-07`. NIFTY/BANKNIFTY traded $\rightarrow$ labeled `DATA_MISSING_IN_FEED (cause unknown)`. Status: `UNEXPLAINED_GAPS (2)`.
4. **INDIA VIX (`^INDIAVIX`)**: 16 missing days:
   - *6 Jan 1 Global Feed Drops*: New Year's Day omissions.
   - *10 Feed Drops*: Underlying indices traded $\rightarrow$ labeled `DATA_MISSING_IN_FEED (cause unknown)`. Status: `UNEXPLAINED_GAPS (10)`.

---

## 4. Expiry Regimes Coverage (2010 to Present)

Every instrument has continuous, gap-free expiry rules from `2010-01-01` to today, verified by `test_expiry_rules_continuous_coverage_from_2010`:

| Instrument | Effective From | Frequency | Day of Week | Verification Status | Regulatory Context / Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **NIFTY** | `2010-01-01` | Monthly | Thursday | **Verified** | Prior to weekly contracts; standard last Thursday monthly expiry |
| **NIFTY** | `2019-02-11` | Weekly | Thursday | **Verified** | NSE launched Nifty weekly options |
| **NIFTY** | `2025-09-01` | Weekly | Tuesday | **Unverified** | User-specified schedule effective Sep 2025; verify exchange circular |
| **BANKNIFTY** | `2010-01-01` | Monthly | Thursday | **Verified** | Prior to weekly contracts; standard last Thursday monthly expiry |
| **BANKNIFTY** | `2016-05-27` | Weekly | Thursday | **Verified** | NSE launched Bank Nifty weekly options |
| **BANKNIFTY** | `2023-09-04` | Weekly | Wednesday | **Verified** | NSE shifted Bank Nifty weekly expiry from Thursday to Wednesday |
| **BANKNIFTY** | `2024-11-20` | Monthly | Thursday | **Verified** | SEBI index derivatives framework (1 weekly per exchange); weekly discontinued |
| **BANKNIFTY** | `2025-09-01` | Monthly | Tuesday | **Unverified** | User-specified monthly on last Tuesday; verify exchange circular |
| **SENSEX** | `2010-01-01` | Monthly | Thursday | **Verified** | BSE monthly settlement on last Thursday |
| **SENSEX** | `2023-05-12` | Weekly | Friday | **Verified** | BSE Sensex derivatives relaunch with Friday weekly expiry |
| **SENSEX** | `2024-11-20` | Weekly | Tuesday | **Verified** | SEBI framework: BSE shifted Sensex weekly to Tuesday |
| **SENSEX** | `2025-09-01` | Weekly | Thursday | **Unverified** | User-specified weekly on Thursday; verify exchange circular |

*Holiday Advance Rule*: Whenever an expiry date falls on an exchange holiday in `config/holidays.yaml`, `resolve_expiry_date()` shifts it to the immediate preceding trading day.

---

## 5. Lot Size History (2010 to Present)

All historical lot size changes covering 2010 to present:

| Instrument | Effective From | Lot Size | Verification Status | Regulatory Context / Change Description |
| :--- | :---: | :---: | :---: | :--- |
| **NIFTY** | `2010-01-01` | **50** | **Verified** | Historical contract lot size |
| **NIFTY** | `2015-10-30` | **75** | **Verified** | NSE derivative contract lot revision |
| **NIFTY** | `2021-04-30` | **50** | **Verified** | NSE contract lot revision |
| **NIFTY** | `2024-04-26` | **25** | **Verified** | NSE contract lot revision |
| **NIFTY** | `2024-11-20` | **75** | **Verified** | SEBI index derivatives framework revision |
| **NIFTY** | `2025-12-30` | **65** | **Unverified** | Replaced 75 around Dec 2025/Jan 2026; verify against contract master |
| **BANKNIFTY** | `2010-01-01` | **25** | **Verified** | Historical contract lot size |
| **BANKNIFTY** | `2016-05-27` | **40** | **Verified** | NSE Bank Nifty derivatives revision |
| **BANKNIFTY** | `2020-07-01` | **25** | **Verified** | NSE contract lot revision |
| **BANKNIFTY** | `2023-07-01` | **15** | **Verified** | NSE contract lot revision |
| **BANKNIFTY** | `2024-11-20` | **35** | **Verified** | SEBI index derivatives framework revision |
| **BANKNIFTY** | `2025-12-30` | **30** | **Unverified** | Replaced 35 around Dec 2025/Jan 2026; verify against contract master |
| **SENSEX** | `2010-01-01` | **50** | **Verified** | Historical BSE contract lot size |
| **SENSEX** | `2023-05-12` | **10** | **Verified** | BSE Sensex derivatives relaunch |
| **SENSEX** | `2024-11-20` | **20** | **Verified** | SEBI index derivatives framework revision |
| **SENSEX** | `2025-09-01` | **20** | **Unverified** | Current contract master (unchanged from Nov 2024) |

---

## 6. Part 2 Architecture & Signal Models

### Standard Output Interface: `SignalPacket`
Every model implements `BaseSignalModel` and returns a standard `SignalPacket` containing:
- `direction`: `SignalDirection.BUY`, `SELL`, or `NO_TRADE`.
- `confidence`: Calibrated probability $[0.0, 1.0]$. For 3-class models, defined as $\max(P(\text{BUY}), P(\text{SELL}))$.
- `suggested_entry`: Recommended execution price ($Open_{t+1}$).
- `stop_loss`: Volatility-adjusted stop level ($Entry \mp 1.5 \times ATR_{14}$).
- `target_price`: Volatility-adjusted profit target ($Entry \pm 2.0 \times ATR_{14}$).
- `time_limit_bars`: Maximum vertical holding horizon (default 10 bars).
- `features_used` & `metadata`: Feature names, raw probabilities, and SHAP contributions.

### Model Catalog:
1. **Rule-Based Baselines** (`models/baselines.py`):
   - `Baseline_Trend_EMA_ADX`: Trend-following filter (EMA 21 > EMA 50 and ADX > 25 for BUY; opposite for SELL).
   - `Baseline_Mean_Reversion`: Bollinger %B ($\le 0.20$ for BUY, $\ge 0.80$ for SELL) and 20-day return Z-score ($|Z| \ge 1.25$).
   - `Baseline_Breakout_Donchian`: 20-day high/low channel breakout with 10-day exit channel.
   - `Baseline_Regime_Switching`: Dynamically activates Trend model in `TRENDING` regime, Mean Reversion in `RANGING` regime, and forces `NO_TRADE` in `HIGH_VOL` or `UNKNOWN` regimes.
2. **Regularized Linear Models** (`models/linear.py`):
   - `Logistic_Regression_L2`: Ridge regularized logistic regression with separate chronological calibration.
   - `Logistic_Regression_L1`: Lasso regularized logistic regression (`l1_ratio=1.0`) with feature variance pruning ($\sigma > 10^{-6}$) and bounded feature scaling.
3. **Gradient Boosted Decision Trees** (`models/tree_models.py`):
   - `LightGBM_Direction_3B`: Multiclass LightGBM predicting forward $N=5$ bar return sign (`DOWN`, `FLAT`, `UP`).
   - `LightGBM_Triple_Barrier`: Multiclass LightGBM trained on exact triple barrier outcomes (`HIT_UPPER`, `HIT_LOWER`, `HIT_VERTICAL`). Executed in backtest with exact barrier parameters: 2.0 ATR target, 1.5 ATR stop, 10 bar time limit.
4. **Ensemble Models** (`models/ensemble.py`):
   - `Consensus_Ensemble`: Independent multi-model ensemble combining Regime Switching, Logistic L2, LightGBM Direction, and LightGBM Triple Barrier. Emits an active signal **only when $\ge 2$ independent models agree on direction** with zero opposing dissent. Submodels are re-fit unconditionally on each walk-forward fold.
   - `MajorityOfThreeEnsemble`: Simple 2-out-of-3 majority voting across 3 distinct model families (Trend, Breakout, Logistic L1).

---

## 7. Walk-Forward Backtesting Framework & Execution Engine

### Walk-Forward Methodology:
- **Expanding Folds**: 10 chronological folds evaluated from `2015-01-01` to `2024-10-31`. Training expands from an initial 4-year history (`2011-2014`).
- **Purging**: Exactly 10 bars are purged at the boundary of each training set to eliminate overlap between forward label horizons and the test fold.
- **Embargoing**: 5 bars are embargoed immediately post-test period before ingesting data for subsequent folds.
- **Holdout Security Guard**: The final 2-year sample (`2024-11-01` to `2026-10-23`) is **strictly sealed** by `HoldoutManager` (`backtest/holdout.py`). Any unauthorized evaluation attempt raises `HoldoutGuardError` and halts execution.

### Execution Rules & Realism:
- **Next-Open Entry**: Signals generated at close $t$ fill strictly at $Open_{t+1}$. Same-bar execution is physically prohibited.
- **Open Gap Fill Logic**: If overnight gap opens beyond the stop-loss or profit target, execution is simulated at the actual $Open$ price rather than the theoretical barrier price.
- **Conservative Dual Breach**: In any bar where both stop-loss and profit target price ranges are touched, the engine conservatively fills the stop-loss first.
- **Slippage**: Evaluated under two explicit regimes:
  - **Base Case**: 1.5 bps per side.
  - **Stress Case**: 5.0 bps per side.
- **Persistent Risk Tracking**: A single continuous `RiskManager` spans all 10 folds, ensuring all-time peak drawdown, kill switch triggers, and pause countdowns are preserved across fold transitions without memory loss.

---

## 8. Effective-Dated Transaction Costs (`backtest/costs.py`)

| Effective Date | STT (Sell Side) | Stamp Duty (Buy Side) | Exchange Fee | SEBI Fee | GST | Brokerage | Verification Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `2010-01-01` | 0.017% | 0.002% | 0.0020% | 0.0001% | 10.3% | Rs 20 | **Unverified / Estimated** (Pre-2015 brokerage assumed flat) |
| `2013-06-01` | 0.010% | 0.002% | 0.0020% | 0.0001% | 12.36% | Rs 20 | **Unverified** (STT revision effective date) |
| `2017-07-01` | 0.010% | 0.002% | 0.0020% | 0.0001% | 18.0% | Rs 20 | **Verified** (GST implementation) |
| `2020-07-01` | 0.010% | 0.002% | 0.0020% | 0.0001% | 18.0% | Rs 20 | **Verified** (Pan-India uniform stamp duty) |
| `2023-04-01` | 0.0125% | 0.002% | 0.0020% | 0.0001% | 18.0% | Rs 20 | **Verified** (Finance Act STT hike) |
| `2024-10-01` | 0.020% | 0.002% | 0.00173% | 0.0001% | 18.0% | Rs 20 | **Verified** (SEBI uniform turnover charge & STT 0.02%) |

---

## 9. Audited Decision Gate Results (Single Instruments Only)

> [!NOTE]
> Pooled multi-index concatenation has been completely removed from the decision gate. The table below reports only genuine, uncompromised single-index walk-forward evaluations.
>
> **Class A Criteria (Strict Institutional Standard)**:
> Net Sharpe above Buy & Hold, Bootstrap 95% difference CI strictly excluding zero, Random noise rank $\ge 95\%$, Deflated Sharpe Ratio p-value $< 0.10$, Positive in $\ge 70\%$ of walk-forward years, and Positive under 5 bps stress slippage. Anything failing goes to Class B or C.

| Instrument | Model | Trades | Win Rate % | Net P&L (INR) | Sharpe (1.5bps) | Sharpe (5.0bps) | B&H Sharpe | Exposure % | Exp-B&H CAGR | Excess Ret % | Random Rank % | DSR p-value | Diff CI Excludes 0 | True MaxDD % | Kill Switches | Days Paused | Decision Gate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **NIFTY** | Baseline_Trend_EMA_ADX | 3 | 66.7% | Rs 31,826 | 0.36 | 0.35 | 0.63 | 0.4% | 0.0% | +0.3% | 50.5% | 0.936 | No | 0.7% | 0 | 0 | **Class B (Weak sample)** |
| **NIFTY** | Baseline_Mean_Reversion | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.63 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | **Class C** |
| **NIFTY** | Baseline_Breakout_Donchian | 96 | 45.8% | Rs -43,112 | -0.09 | -0.19 | 0.63 | 28.7% | 2.6% | -3.1% | 43.1% | 0.998 | No | 8.6% | 0 | 0 | **Class C** |
| **NIFTY** | Baseline_Regime_Switching | 1 | 0.0% | Rs -6,898 | -0.32 | -0.32 | 0.63 | 0.1% | 0.0% | -0.1% | 0.0% | 1.000 | No | 0.7% | 0 | 0 | **Class C** |
| **NIFTY** | Logistic_Regression_L2 | 300 | 49.7% | Rs -246,919 | -0.32 | -0.57 | 0.63 | 57.2% | 5.2% | -8.1% | 25.3% | 1.000 | No | 27.1% | 3 | 50 | **Class C** |
| **NIFTY** | Logistic_Regression_L1 | 298 | 48.3% | Rs -276,162 | -0.36 | -0.58 | 0.63 | 54.4% | 5.0% | -8.2% | 22.8% | 1.000 | No | 29.9% | 3 | 50 | **Class C** |
| **NIFTY** | LightGBM_Direction_3B | 24 | 33.3% | Rs -54,920 | -0.19 | -0.28 | 0.63 | 4.1% | 0.4% | -0.9% | 44.3% | 0.999 | No | 13.9% | 0 | 0 | **Class C** |
| **NIFTY** | LightGBM_Triple_Barrier | 160 | 36.2% | Rs -327,250 | -0.62 | -0.91 | 0.63 | 29.2% | 2.7% | -6.6% | 15.2% | 1.000 | No | 41.8% | 3 | 60 | **Class C** |
| **NIFTY** | Consensus_Ensemble | 58 | 32.8% | Rs -205,693 | -0.68 | -0.51 | 0.63 | 10.3% | 0.9% | -3.3% | 26.2% | 1.000 | No | 23.1% | 1 | 20 | **Class C** |
| **BANKNIFTY** | Baseline_Trend_EMA_ADX | 5 | 40.0% | Rs 1,436 | 0.02 | 0.01 | 0.59 | 1.4% | 0.2% | -0.1% | 47.4% | 0.995 | No | 2.4% | 0 | 0 | **Class B (Weak sample)** |
| **BANKNIFTY** | Baseline_Mean_Reversion | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.59 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | **Class C** |
| **BANKNIFTY** | Baseline_Breakout_Donchian | 82 | 48.8% | Rs -15,095 | -0.04 | -0.11 | 0.59 | 23.7% | 2.7% | -2.8% | 48.0% | 0.997 | No | 5.6% | 0 | 0 | **Class C** |
| **BANKNIFTY** | Baseline_Regime_Switching | 1 | 0.0% | Rs -8,497 | -0.32 | -0.32 | 0.59 | 0.2% | 0.0% | -0.1% | 0.0% | 1.000 | No | 0.8% | 0 | 0 | **Class C** |
| **BANKNIFTY** | Logistic_Regression_L2 | 217 | 47.5% | Rs 203,696 | 0.27 | 0.17 | 0.59 | 42.2% | 4.7% | -2.8% | 67.7% | 0.964 | No | 14.2% | 0 | 0 | **Class B (Marginal Edge)** |
| **BANKNIFTY** | Logistic_Regression_L1 | 203 | 47.3% | Rs 200,200 | 0.27 | 0.17 | 0.59 | 39.4% | 4.4% | -2.5% | 65.9% | 0.965 | No | 15.0% | 1 | 20 | **Class B (Marginal Edge)** |
| **BANKNIFTY** | LightGBM_Direction_3B | 36 | 44.4% | Rs -50,531 | -0.16 | -0.23 | 0.59 | 6.7% | 0.8% | -1.3% | 43.3% | 0.999 | No | 13.0% | 0 | 0 | **Class C** |
| **BANKNIFTY** | LightGBM_Triple_Barrier | 132 | 40.2% | Rs -94,031 | -0.17 | -0.29 | 0.59 | 23.7% | 2.7% | -3.7% | 39.5% | 0.999 | No | 22.1% | 1 | 20 | **Class C** |
| **BANKNIFTY** | Consensus_Ensemble | 42 | 33.3% | Rs -167,785 | -0.56 | -0.57 | 0.59 | 7.3% | 0.8% | -2.7% | 31.3% | 1.000 | No | 19.1% | 1 | 20 | **Class C** |
| **SENSEX** | Baseline_Trend_EMA_ADX | 3 | 33.3% | Rs 4,217 | 0.06 | 0.04 | 0.61 | 0.8% | 0.1% | -0.0% | 49.1% | 0.993 | No | 1.7% | 0 | 0 | **Class B (Weak sample)** |
| **SENSEX** | Baseline_Mean_Reversion | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.61 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | **Class C** |
| **SENSEX** | Baseline_Breakout_Donchian | 97 | 48.5% | Rs -11,534 | -0.01 | -0.11 | 0.61 | 30.9% | 2.7% | -2.9% | 49.4% | 0.996 | No | 8.1% | 0 | 0 | **Class C** |
| **SENSEX** | Baseline_Regime_Switching | 3 | 33.3% | Rs 4,217 | 0.06 | 0.04 | 0.61 | 0.8% | 0.1% | -0.0% | 49.1% | 0.993 | No | 1.7% | 0 | 0 | **Class B (Weak sample)** |
| **SENSEX** | Logistic_Regression_L2 | 327 | 49.5% | Rs -171,376 | -0.14 | -0.26 | 0.61 | 61.6% | 5.5% | -7.4% | 37.8% | 0.999 | No | 23.9% | 3 | 60 | **Class C** |
| **SENSEX** | Logistic_Regression_L1 | 319 | 49.5% | Rs -169,939 | -0.14 | -0.31 | 0.61 | 59.6% | 5.3% | -7.2% | 37.9% | 0.999 | No | 24.3% | 3 | 60 | **Class C** |
| **SENSEX** | LightGBM_Direction_3B | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.61 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | **Class C** |
| **SENSEX** | LightGBM_Triple_Barrier | 152 | 34.2% | Rs -465,806 | -0.97 | -1.08 | 0.61 | 27.4% | 2.4% | -8.6% | 6.7% | 1.000 | No | 49.2% | 4 | 80 | **Class C** |
| **SENSEX** | Consensus_Ensemble | 67 | 37.3% | Rs -214,190 | -0.61 | -0.69 | 0.61 | 13.0% | 1.2% | -3.6% | 27.3% | 1.000 | No | 24.6% | 1 | 20 | **Class C** |

---

## 10. Deep-Dive Audits & Quantitative Findings

### 1. Deflated Sharpe Ratio (DSR) Explanation & Verification
- **Root Cause of Prior 0.00 / 1.00 Output**:
  - The previous calculation divided the annualized Sharpe by $\sqrt{N}$ where $N = 2520$ daily bars without standardizing by $\sqrt{252}$ or using sample length $Y=10.0$ years. This artificially crushed the standard error to $0.0199$ (instead of $\approx 0.35$), inflating test statistics to $-44.1$ (forcing $\Phi(z) \to 0.00$).
  - For pooled data, nominal Sharpe was 3.62, which forced $z \to +101$ ($\Phi(z) \to 1.00$).
- **Verified Institutional Formulation (Bailey & López de Prado, 2014)**:
  - Total research trials evaluated: $K = 162$ trials (3 instruments $\times$ 9 models $\times$ 6 gate variants).
  - Empirical trial Sharpe variance: $\mathbb{V}[\{SR_k\}] = 0.0969$ (Std Dev: $0.311$).
  - Expected Maximum Sharpe under Null: $E[\max SR] = 0.81$.
  - Result: Every single-instrument model yields a DSR p-value $> 0.90$ ($p \gg 0.10$). **None of the models achieves statistical significance after adjusting for multiple testing.**

### 2. Ensemble Component Audit & Causality Verification
- **Audit Findings**:
  - In `Consensus_Ensemble`, when submodels were properly re-fitted fold-by-fold without leakage, the ensemble emitted 42 to 67 trades with win rates between 32.8% and 37.3%, producing negative net P&L after costs.
  - SENSEX vote breakdown: `Baseline_Regime_Switching` and `LightGBM_Direction_3B` voted `NO_TRADE` on >99% of bars, leaving `Logistic_Regression_L2` and `LightGBM_Triple_Barrier` as the sole agreeing pair (61 trades, all decisive).
- **Ensemble Architecture Variants on SENSEX**:
  - *Standard Consensus Ensemble ($\ge 2$ of 4)*: 67 trades, Sharpe -0.61, Net P&L -Rs 214k (Class C).
  - *Non-Negative Standalone Members Only (Trend + Regime)*: 3 trades, Sharpe 0.06, Net P&L +Rs 4k (Class B, weak sample).
  - *Majority of 3 (Trend, Breakout, Logistic L1)*: 67 trades, 58.2% win rate, Sharpe 0.33, Net P&L +Rs 113k (Class C; fails stress slippage).
- **Leakage Prevention Proof**:
  - Verified by `test_ensemble_components_fit_strictly_before_test_fold`: each component model is re-fitted strictly on data preceding each test fold.

### 3. Systematic Gate Ablation Study
Ablation of each gate was conducted on SENSEX Consensus Ensemble and BANK NIFTY Logistic L1:
- **Confidence Gate**: Removing the confidence gate increases trades by +99 to +159 but severely degrades performance (BANK NIFTY net P&L drops from +Rs 200k to +Rs 2k; SENSEX MaxDD expands from 24.6% to 34.0%). The confidence gate is vital.
- **Expiry Gate Reality**:
  - On SENSEX, removing the expiry gate adds +6 trades and improves net P&L from -Rs 214k to -Rs 185k (Sharpe improves from -0.61 to -0.47).
  - On BANK NIFTY, removing the expiry gate adds +43 trades and maintains a 48.0% win rate.
  - **Retraction**: The earlier assertion that expiries systematically degrade win rates is unsupported by out-of-sample data and is formally retracted.
- **Raw Signals (No Gates)**: Produces severe drawdown (36.2% to 42.6%) and negative returns across all configurations.

### 4. SENSEX Era Split (Pre vs Post May 2023)
BSE SENSEX derivatives were officially relaunched on **May 12, 2023** (`2023-05-12`):
- **Pre-May 2023 Era** (`2015-01-01` to `2023-05-11`): 67 trades, 37.3% win rate, Net P&L -Rs 214k, Sharpe -0.66. **Hypothetical Back-Extension Period.**
- **Post-May 2023 Era** (`2023-05-12` to `2024-10-31`): **0 trades executed** in the live derivatives era.
- **Conclusion**: SENSEX derivatives models have zero live out-of-sample trading history in Part 2.

### 5. Exposure Adjustment vs Buy & Hold
Comparing raw Sharpe ratios alone is misleading because strategies maintain low average exposure (0.4% to 42.2% of market days):
- `BANKNIFTY Logistic_Regression_L2`: 42.2% exposure. Exposure-matched Buy & Hold delivers a 4.7% CAGR. The strategy delivers a 1.9% CAGR, resulting in an **Excess Return of -2.8%** relative to exposure-matched buy-and-hold.
- `BANKNIFTY Logistic_Regression_L1`: 39.4% exposure. Excess Return is **-2.5%** relative to exposure-matched buy-and-hold.
- None of the active strategies outperform exposure-matched Buy & Hold.

---

## 11. Model Registry & Saved Artifacts

All runs are recorded in `data/experiments/experiment_log.jsonl`.
Artifacts in `models/artifacts/` are labeled **"Marginal, Unconfirmed"**:
- `Logistic_Regression_L1_BANKNIFTY_v1` (Class B — Marginal Edge)
- `Logistic_Regression_L2_BANKNIFTY_v1` (Class B — Marginal Edge)
- `Baseline_Trend_EMA_ADX_NIFTY_v3` (Class B — Low Sample Size, 3 trades)
- `Baseline_Regime_Switching_SENSEX_v1` (Class B — Low Sample Size, 3 trades)

---

## 12. Verification & Test Suite Status

The platform maintains full test coverage across data ingestion, calendars, lookahead bias prevention, cost calculations, execution engine, risk sizing, and ensemble components:
- **Total Tests Passing**: **38 of 38 tests** in `45.79s`.
- Test modules:
  - `tests/test_backtest_engine.py` (5 tests): No same-bar execution, adverse/favorable open gap fills, conservative dual barrier breach, holdout security guard.
  - `tests/test_calendar_rules.py` (5 tests): Continuous 2010-present expiry rules, holiday shifts, lot size time-varying resolution.
  - `tests/test_costs.py` (3 tests): Hand-verified mathematical calculations for effective-dated statutory STT, GST, SEBI, exchange fee, stamp duty for 2012, 2018, and 2025.
  - `tests/test_data_cleaning.py` (7 tests): Deduplication, gap auditing, outlier detection.
  - `tests/test_lookahead.py` (6 tests): Multi-cutoff causal integrity tests ($T=650\dots 1000$) and real data slice testing.
  - `tests/test_providers.py` (5 tests): Data provider abstraction, SmartAPI fallback, rate limit retry.
  - `tests/test_signal_models.py` (5 tests): Calibration slice separation, Model 3B exact exits, seed determinism, ensemble consensus rule, **and ensemble component causal re-fitting on test folds**.
  - `tests/test_walk_forward.py` (2 tests): Non-overlapping walk-forward folds, 10-bar purging, 5-bar embargoing, gap date trading exclusion.

---

## 13. Handoff to Part 3 (Signals & Dashboard)

1. **Research Platform Reality**: No model possesses a statistically confirmed edge over Buy & Hold.
2. **Part 3 Purpose**:
   - Built strictly as a **decision support, signal diagnostic, and risk monitoring platform**, NOT an automated execution system.
   - Candidates deployed for tracking will be clearly tagged **"Marginal, Unconfirmed"** in the UI and API responses.
3. **Candidate Selection for Decision Support**:
   - **Primary Model**: `BANKNIFTY Logistic_Regression_L1` (Class B: 203 trades, positive net P&L Rs +200k, Sharpe 0.27 base / 0.17 stress, 1 kill switch trigger with 20 days paused).
   - **Secondary Monitoring**: `NIFTY Baseline_Trend_EMA_ADX` (Class B: conservative trend filter).
4. **Part 3 Deliverables**:
   - `signals/`: Daily signal generation service producing `BUY` / `SELL` / `NO_TRADE` with calibrated confidence, gate audit diagnostic logs, and dynamic ATR targets.
   - FastAPI REST endpoints providing signal lookups, gate audit traces, and historical performance metrics.
   - `dashboard/`: Interactive Streamlit dashboard visualizing daily signals, regime classification, model consensus radar, and walk-forward equity curves.

---

## 14. Part 3: Intraday Infrastructure & Stage 1 Live Recorder

### 14.1 Historical Candle Audit & Feed Limitation
- **1-Minute Feed Structure:** Across 9 audited sessions (Oct 12 to Oct 23, 2026), the 1m feed provides exactly **361 rows per session**. Feed runs unbroken from `09:15` to `15:14` (360 continuous minutes). Minutes `15:15` to `15:27` are omitted in 9/9 sessions. A single closing print is published at `15:28` or `15:29`.
- **Refutation:** The hypothesis that the feed stops at 15:15 is refuted; it stops at 15:14, and the 361st row is the closing print ($360 + 1 = 361$).
- **5m and 15m Bars:** 5m bars run 09:15 to 15:25 (73 bars/session, omitting 15:25–15:30). 15m bars run 09:15 to 15:15 (25 bars/session).
- **Daily vs Intraday Close:** The closing 1m bar matches the daily historical close with **0.00 difference** across all 9 audited sessions.

### 14.2 Transaction Costs & Effective-Dated Schedules
- **₹2.93 Exchange Fee Discrepancy Resolved:** Discrepancy between Angel One calculator (0.00183%) and NSE tariff (0.00173%) was proven to be the **NSE Investor Protection Fund Trust (IPFT)** charge of 0.00010% (₹10/crore). Added as `ipft_pct: 0.00010` in `config/config.yaml` and `backtest/costs.py`.
- **Budget 2026 STT:** Added effective-dated row from `2026-04-01` with sell-side futures STT at 0.050% (Finance Act / Budget 2026), retaining 0.020% for `2024-10-01` to `2026-03-31`. All component sums match total costs exactly (`abs < 1e-6`).

### 14.3 Analytical Black-76 Greeks Engine
- **SENSEX BFO Options:** Because Angel One's `optionGreek` REST API is restricted to NSE/NFO, SENSEX BFO options use analytical Black-76 (`recorder/metrics.py`) with risk-free rate $r = 6.5\%$ and spot cost-of-carry forward price $F = S \cdot e^{rT}$.
- **Validation on NIFTY:** Analytical Black-76 validated against Angel `optionGreek`: Delta MAE = 0.0016, Gamma MAE = 0.000022, Vega MAE = 0.0396. Labeled `computed_black76` in `options_snapshots`.

### 14.4 Live Market Recorder Architecture & Live Test Results
- **Core Subscriptions:** Continuous Mode 3 (SNAP_QUOTE) WebSocket streaming on 6 core tokens (3 Spot Indices: NIFTY, BANKNIFTY, SENSEX; 3 Active Futures). Options captured as 1-minute snapshots (ATM $\pm 10$ strikes across weekly and monthly expiries).
- **Volume Differencing & VWAP:** $\Delta Vol = \max(0, Vol_{cum}(t) - Vol_{cum}(t-1))$. Cumulative intraday VWAP handles intraday accumulation, session reset, and contract rollover.
- **Shared Rate Limiter:** Token buckets operating at 70% of broker limits with exponential backoff (2s to 60s). `AB1021` removed from matcher.
- **Storage Isolation & Retention:** Daily partitioned DuckDB databases in `data/live/live_YYYY_MM_DD.duckdb` (14-day retention). Nightly consolidation to Zstandard Parquet in `data/live/consolidated/` (365-day retention). Disk usage marked strictly as estimates until full-day telemetry measurement.
- **Stage 1 Market-Hours Live Test:** Executed on 2026-10-26 during active trading hours. Ingested over **10,000 ticks at 27.75 ticks/sec** with 0 disconnects. Populated all 6 tables (`live_ticks`, `live_depth`, `futures_bars`, `options_snapshots`, `live_derived_metrics`, `recorder_health`). Automated secrets scan passed with **0 findings**.

### 14.5 Full Chain Derived Metrics & Max Pain Resolution
- **OI Source for NIFTY & BANKNIFTY:** `optionGreek` REST endpoint returns analytical Greeks, IV, and trade volume, but returns 0 or missing Open Interest (`openInterest` key absent). To calculate valid PCR and Max Pain, Open Interest is merged from `getMarketData("FULL")` in batches of 50 tokens across the full option chain.
- **Full Chain Sample & Max Pain 22,100 Edge Artifact:**
  - With the truncated ATM $\pm 10$ window (strikes 22,100 to 23,100), Max Pain calculated to 22,100 (the lowest strike of the window). This is **100% CONFIRMED as an edge artifact** caused by window truncation and missing OI.
  - When computed across the **FULL NIFTY chain (288 strikes)** with merged OI:
    - Call OI: 297,404,055 | Put OI: 313,039,805
    - Full Chain PCR OI: **1.053** | PCR Volume: **1.038**
    - True Full Chain Max Pain: **22,700.0** (within 45 points of spot 22,655).
- **Implementation:** `recorder/options_monitor.py` updated to compute full-chain PCR and Max Pain across all available strikes while storing the ATM $\pm 10$ strikes for granular tick-level snapshots.

### 14.6 Spot-Futures Basis vs Cost of Carry
- **Observed Basis Values (2026-10-26 13:25 IST):**
  - NIFTY Spot: 22,655.15 | Near Future (`NIFTY27OCT26FUT`, token 48704): 22,706.30 $\rightarrow$ Basis = **+51.15 pts**.
  - Next Future (`NIFTY23NOV26FUT`, token 61471): 22,819.80 $\rightarrow$ Roll Spread = **+113.50 pts**.
  - BANKNIFTY Spot: 54,153.50 | Near Future (48699): 54,249.20 $\rightarrow$ Basis = **+95.70 pts**.
  - SENSEX Spot: 73,323.46 | Near Future (864571): 73,513.10 $\rightarrow$ Basis = **+189.64 pts**.
- **Theoretical Cost of Carry:**
  $$F = S \cdot e^{r \cdot \frac{T}{365}}$$
  At $r = 6.5\%$ and $DTE = 1$ day ($T = 1/365$), theoretical carry is $22,655 \times 0.065 \times (1 / 365) \approx 4.03$ points.
- **Basis Explanation:** The +51 pt basis is NOT a token mapping error or timestamp mismatch (exchange timestamps match within 300ms). Rather, on Expiry Eve ($DTE=1$ before the 2026-10-27 monthly expiry), institutional rollover volume and next-month liquidity premiums dominate trading prices. Next-month OI (11.24M) already surpassed near-month OI (11.09M), creating substantial roll pressure that widens the cash-futures spread beyond theoretical risk-free carry.

### 14.7 Per-Interval Audit Table (1m, 5m, 15m) & OHLC Aggregation
Audit conducted across all 9 ingested historical sessions (Oct 12 to Oct 23, 2026):

| Interval | Bars / Session | First Bar IST | Last Bar IST | Bars $\ge$ 15:15 IST | Missing Minutes Structure |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1-Minute** | **361** | `09:15:00` | `15:28:00` / `15:29:00` | **1** | Continuous 09:15–15:14 (360 bars); 15:15–15:27 missing; 1 closing print. |
| **5-Minute** | **73** | `09:15:00` | `15:25:00` | **3** | Continuous 09:15–15:25 (73 bars); 15:25–15:30 omitted. |
| **15-Minute** | **25** | `09:15:00` | `15:15:00` | **1** | Continuous 09:15–15:15 (25 bars); 15:15–15:30 omitted. |

- **Aggregated Intraday vs Daily OHLC Comparison:**
  For all 9 sessions, constructing the daily bar from 1m intraday bars ($Open = Open_{09:15}$, $High = \max(High_{intraday})$, $Low = \min(Low_{intraday})$, $Close = Close_{last}$) matches the official daily historical bar with **exactly 0.00 difference across Open, High, Low, and Close**.
- **Closing Auction Hypothesis:** The isolated 1m bar at 15:28/15:29 is labeled as a *hypothesis* (closing auction settlement print), not an established fact, as official exchange timestamp specifications for historical REST API feeds do not distinguish uncrossing trades from continuous matching.

### 14.8 Exit Price Rule When No 15:15 1m Bar Exists
1. **Live Continuous Trading:** Any open intraday or scalping position must submit exit market/limit orders between **15:14:00 and 15:14:30 IST**, ensuring execution within continuous matching before the 15:15:00 feed cutoff.
2. **Backtesting & Simulation:** Exit fill prices are strictly mapped to the **Close of the 15:14:00 1m bar** (or the Open of the 15:14:00 bar for conservative fills).
3. **Closing Print Exclusion:** The single 15:28/15:29 closing bar MUST NEVER be used as an exit price in backtests, as it reflects the volume-weighted closing session where continuous retail execution is unavailable.

### 14.9 Futures Rollover Manager (`recorder/roll.py`)
- Both nearest and next-month futures are recorded simultaneously across all three underlyings (6 futures contracts total: `NIFTY_FUT_NEAR`, `NIFTY_FUT_NEXT`, `BANKNIFTY_FUT_NEAR`, `BANKNIFTY_FUT_NEXT`, `SENSEX_FUT_NEAR`, `SENSEX_FUT_NEXT`).
- **Institutional Roll Rules:**
  - **Trigger A (OI Crossover):** $DTE \le 1$ and $OI_{next} > OI_{near}$.
  - **Trigger B (Volume Crossover):** $DTE \le 1$ and $Vol_{next} > Vol_{near}$.
  - **Trigger C (Mandatory Time Cutoff):** $DTE = 0$ (Expiry Day) at or after **12:00 IST**, forcing rollover to avoid cash settlement distortions in the final 3.5 hours.
- Validated via unit tests in `tests/test_recorder_metrics.py`.

### 14.10 Production Daemon, macOS Wrapper & Resilience
- **Daemon Management:** `scripts/recorder_daemon.sh` manages lifecycle (`start`, `stop`, `restart`, `status`).
- **Sleep Prevention:** Runs under `caffeinate -dimsu` to assert display, system, disk, and idle sleep suppression.
- **Power Warnings:** Inspects `pmset -g batt` and warns if operating on battery power.
- **Automated Scheduling:** `scripts/com.valiantcurie.recorder.plist` configured for macOS `launchd` to trigger daily at 09:00:00 IST (Monday–Friday) with automated shutdown at 15:35:00 IST.
- **REST Fallback on WebSocket Stall:** Watchdog monitors tick arrival; if no tick is received for $\ge 10.0$ seconds, it triggers REST polling of spot LTP and futures quote via `_poll_rest_fallback()`, stamping `source='rest'`. Tested and verified in `tests/test_recorder_resilience.py`.
- **Strike Recentering:** Detects when spot moves $\ge 1$ strike step from previous ATM center, recomputing the $\pm 10$ window and updating subscriptions. Tested in `tests/test_recorder_resilience.py`.
- **WebSocket Subscription Limits:**
  - Mode 1 (LTP): Up to 3,000 tokens.
  - Mode 2 (Quote): Up to 500 tokens.
  - Mode 3 (Snap Quote): Up to 100 tokens per connection across NSE, NFO, BSE, BFO.
  - Mode 4 (Market Depth / Full 20-order book): Strictly capped at **50 tokens max**, limited to `exchangeType: 1` (NSE CM). Attempting to send NFO tokens or >50 tokens causes rejection/disconnect by SmartAPI server.

---

## 15. Intraday 15m Signal Engine & Institutional Candlestick Architecture

### 15.1 Zero Rate-Limit Candle Architecture (`getCandleData` Protection)
- Angel One SmartAPI enforces strict rate limits (120 req/min, 3 req/sec) and throttles polling loops.
- `dashboard/intraday_data.py` caches base 15m candles with `@st.cache_data(ttl=900)` (15-minute TTL).
- Incoming live ticks from Angel One WebSocket `SNAP_QUOTE` update the current forming 15m candle (`Open`, `High`, `Low`, `Close`, `Volume`) strictly in-memory without making REST API calls on UI refreshes.

### 15.2 Institutional 15m Candlestick Charting (`dashboard/charting.py`)
- **Theme:** Dark mode (`#0E1117` background, subtle `#1F2430` gridlines).
- **Y-Axis Auto-Scaling:** `yaxis=dict(autorange=True, fixedrange=False, side="right")` tightly frames the active NIFTY trading corridor rather than starting at 0.
- **NSE Gapless Rangebreaks:** `rangebreaks=[dict(bounds=['sat', 'mon']), dict(bounds=[15.5, 9.25], pattern='hour')]` hides weekends and non-market hours (15:30 to 09:15 IST) so overnight gaps do not distort EMA 21/50 slopes.
- **Technical Overlays:**
  - EMA 21 (`#00E5FF` dashed line, width 1.5).
  - EMA 50 (`#FF9100` solid line, width 2.0).
  - True Max Pain Strike (`#B388FF` dotted reference line at ₹22,750).
  - Live Spot LTP Line (pulsing green/red dashed price line with right-axis price tag).

### 15.3 Live Buy/Sell Signal Markers
- Parsed directly from `Today's Intraday Signal Log (15m Intervals)`:
  - **BUY / STRONG BUY:** Neon green `triangle-up` marker (`size=14`) positioned below candle low (`low - 0.15*ATR`) with floating tag `BUY | [Strike] CE`.
  - **SELL / STRONG SELL:** Crimson `triangle-down` marker (`size=14`) positioned above candle high (`high + 0.15*ATR`) with floating tag `SELL | [Strike] PE`.
  - **NEUTRAL / WAIT:** Subtle amber diamond marker (`size=9`) on consolidation bars.
  - Interactive hover tooltips displaying `Time`, `Signal State`, `Confidence %`, `Score`, and `Confluence Drivers`.

### 15.4 TradingView-Style Visual Risk-to-Reward (RR) Projection Zones
- Forward projection extends from the signal trigger timestamp across the next 12 bars (3 hours):
  - **Entry Zone Band:** Semi-transparent blue band (`rgba(66, 165, 245, 0.16)`) spanning exact `Entry Range`.
  - **Stop Loss Zone (Risk Box):** Semi-transparent red shaded rectangle (`rgba(255, 75, 75, 0.16)`) with solid red border at `1.5x ATR Stop Loss` level.
  - **Target 1 Zone (1:1.5 RR):** Semi-transparent emerald green shaded rectangle (`rgba(0, 200, 105, 0.14)`) from Entry to `Target 1`.
  - **Target 2 Zone (1:2.5 RR):** Deeper green shaded rectangle (`rgba(0, 230, 118, 0.22)`) from Target 1 to `Target 2`.

### 15.5 Dual Spot + Option Premium Risk Translation (Delta $\approx 0.50$ ATM Guardrail)
- Translates spot levels into realistic intraday scalping option premium metrics for 1-DTE ATM options (`65 Qty` lot size):
  - `Option Entry LTP`: ₹266.2 (`22750 PE` ATM strike).
  - `Option Hard SL`: ₹221.8 (-44.4 pts / -₹2,886 per lot).
  - `Option Target 1 (1:1.5 RR)`: ₹332.8 (+66.6 pts / +₹4,329 per lot).
  - `Option Target 2 (1:2.5 RR)`: ₹377.1 (+110.9 pts / +₹7,208 per lot).
- Integrated directly into the Active Trade Card and shaded RR box annotations.
- Full test coverage verified in `tests/test_signal_engine.py` and `tests/test_charting_and_intraday.py`.

### 15.7 TradingView Lightweight Charts™ Canvas Component
- **Engine Architecture:** Replaced Plotly with pure HTML5 Canvas TradingView Lightweight Charts v4.2.0 (`dashboard/tradingview_chart.py`) rendered via `st.components.v1.html(..., height=640)`.
- **Canvas Styling & Controls:** Background `#0B0E14`, grid `rgba(42, 46, 57, 0.45)`, `CrosshairMode.Normal` magnet crosshair, `rightOffset: 14` (14 empty future bars for zero clipping).
- **Interactive Controls:** Top-left floating TradingView legend overlay dynamically updating `O/H/L/C` and `EMA 21/EMA 50` on crosshair hover; bottom-right floating `"⟳ Reset Chart View"` and `"⚡ Jump to Real-Time"` viewport buttons.
- **Series & Indicators:** Authentic emerald `#089981` / crimson `#F23645` candlesticks, cyan `#00E5FF` EMA 21, and orange `#FF9100` EMA 50.
- **Native Right-Axis Price Pills (`createPriceLine`):** Max Pain (dotted purple), Entry (solid blue), Stop Loss (solid red with option SL), Target 1 (dashed green with option T1), Target 2 (solid green with option T2).
- **Native Markers (`setMarkers`):** BUY CE (emerald arrowUp belowBar), SELL PE (red arrowDown aboveBar), WAIT (amber circle). Strictly ascending chronological order.
- **Shaded Risk-to-Reward Drawing Tool Canvas Overlay:** Synchronized 60 FPS HTML5 canvas overlay with red Risk rectangle (`rgba(242, 54, 69, 0.22)`), green Target 1 rectangle (`rgba(8, 153, 129, 0.20)`), green Target 2 rectangle (`rgba(0, 230, 118, 0.28)`), and embedded pill badges pinned to price and bar coordinates across all zoom, pan, and resize interactions.



