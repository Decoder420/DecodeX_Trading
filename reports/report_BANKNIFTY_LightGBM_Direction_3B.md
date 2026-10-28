# Quantitative Walk-Forward Research Report: LightGBM_Direction_3B on BANKNIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `LightGBM_Direction_3B` | **Instrument**: `BANKNIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **13.04%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.16** | -0.23 | 0.59 | 0.59 | 0.09 |
| **CAGR** | **-0.53%** | -0.75% | 11.21% | **0.75%** | N/A |
| **Excess Return vs Exposure B&H** | **-1.28%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.06** | -0.07 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **13.04%** | 14.04% | 47.86% | N/A | N/A |
| **Calmar Ratio** | **-0.04** | -0.05 | N/A | N/A | N/A |
| **Win Rate** | **44.44%** | 36.11% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.81** | 0.74 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -50,530.71** | Rs -70,949.00 | N/A | N/A | N/A |
| **Total Trade Count** | **36** | 36 | 1 | N/A | 36 |
| **Market Exposure** | **6.7%** | 6.7% | 100.0% | 6.7% | N/A |
| **Expectancy / Trade**| **Rs -1,403.63** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **43.3%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9992** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.70, 0.08]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **2/10 (20.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **1573** | Total BUY (877) and SELL (696) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1402** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **32** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **59** | Signals on contract expiry days |
| **Final Executed Signals** | **80** | Final approved trades (0 BUY, 80 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 1 | 100.0% | Rs 7,517.99 | 0.75% | 1.02 |
| 2016 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2017 | 25 | 36.0% | Rs -82,250.26 | -8.16% | -0.90 |
| 2018 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2019 | 10 | 60.0% | Rs 24,201.56 | 2.62% | 0.82 |
| 2020 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2021 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 9 | 66.7% | Rs 170.95 | 0.01 |
| RANGING | 27 | 37.0% | Rs -50,701.65 | -0.59 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 0 | 0.0% | Rs 0.00 | 0.00 |
| **SELL (Short)** | 36 | 44.4% | Rs -50,530.71 | -0.56 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 1 | 100.0% | Rs 7,517.99 | Rs 1,007,517.99 | 1.02 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 0 | 0.0% | Rs 0.00 | Rs 1,007,517.99 | 0.00 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 25 | 36.0% | Rs -82,250.26 | Rs 925,267.73 | -0.90 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 0 | 0.0% | Rs 0.00 | Rs 925,267.73 | 0.00 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 10 | 60.0% | Rs 24,201.56 | Rs 949,469.29 | 0.82 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 0 | 0.0% | Rs 0.00 | Rs 949,469.29 | 0.00 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 0 | 0.0% | Rs 0.00 | Rs 949,469.29 | 0.00 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 949,469.29 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 0 | 0.0% | Rs 0.00 | Rs 949,469.29 | 0.00 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 0 | 0.0% | Rs 0.00 | Rs 949,469.29 | 0.00 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*