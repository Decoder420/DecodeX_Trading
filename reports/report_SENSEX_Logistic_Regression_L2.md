# Quantitative Walk-Forward Research Report: Logistic_Regression_L2 on SENSEX

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Logistic_Regression_L2` | **Instrument**: `SENSEX`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **23.92%**
- **Kill Switch Triggers**: **3** times | **Total Days Paused**: **60** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.14** | -0.26 | 0.61 | 0.61 | -0.01 |
| **CAGR** | **-1.89%** | -3.10% | 8.86% | **5.46%** | N/A |
| **Excess Return vs Exposure B&H** | **-7.36%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.13** | -0.23 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **23.92%** | 28.73% | 38.07% | N/A | N/A |
| **Calmar Ratio** | **-0.08** | -0.11 | N/A | N/A | N/A |
| **Win Rate** | **49.54%** | 49.08% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.92** | 0.87 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -171,376.49** | Rs -265,920.25 | N/A | N/A | N/A |
| **Total Trade Count** | **327** | 326 | 1 | N/A | 327 |
| **Market Exposure** | **61.6%** | 61.6% | 100.0% | 61.6% | N/A |
| **Expectancy / Trade**| **Rs -524.09** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **37.8%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9990** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.76, 0.12]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **4/10 (40.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2419** | Total BUY (2288) and SELL (131) raw signals |
| **Data Gap Gate** | **24** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **541** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **17** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **466** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **209** | Signals on contract expiry days |
| **Final Executed Signals** | **1162** | Final approved trades (1144 BUY, 18 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 46 | 41.3% | Rs -186,330.51 | -18.63% | -1.96 |
| 2016 | 13 | 46.2% | Rs 6,417.83 | 0.79% | 0.21 |
| 2017 | 24 | 66.7% | Rs 99,127.86 | 12.09% | 1.63 |
| 2018 | 37 | 54.1% | Rs -1,601.76 | -0.17% | 0.02 |
| 2019 | 35 | 42.9% | Rs -64,624.48 | -7.04% | -0.99 |
| 2020 | 42 | 64.3% | Rs 179,365.68 | 21.03% | 1.14 |
| 2021 | 38 | 47.4% | Rs -70,900.61 | -6.87% | -0.97 |
| 2022 | 30 | 36.7% | Rs -73,118.57 | -7.60% | -0.67 |
| 2023 | 38 | 50.0% | Rs 63,878.71 | 7.19% | 0.68 |
| 2024 | 24 | 45.8% | Rs -123,590.64 | -12.98% | -1.75 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 137 | 53.3% | Rs -15,389.12 | -0.10 |
| RANGING | 190 | 46.8% | Rs -155,987.37 | -0.65 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 317 | 49.5% | Rs -177,427.34 | -0.56 |
| **SELL (Short)** | 10 | 50.0% | Rs 6,050.86 | 0.20 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 46 | 41.3% | Rs -186,330.51 | Rs 813,669.49 | -1.96 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 13 | 46.2% | Rs 6,417.83 | Rs 820,087.32 | 0.21 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 24 | 66.7% | Rs 99,127.86 | Rs 919,215.19 | 1.63 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 37 | 54.1% | Rs -1,601.76 | Rs 917,613.43 | 0.02 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 35 | 42.9% | Rs -64,624.48 | Rs 852,988.95 | -0.99 |
| 6 | 2020 | 2020-01-02 to 2020-12-31 | 42 | 64.3% | Rs 179,365.68 | Rs 1,032,354.63 | 1.14 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 38 | 47.4% | Rs -70,900.61 | Rs 961,454.02 | -0.97 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 30 | 36.7% | Rs -73,118.57 | Rs 888,335.45 | -0.67 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 38 | 50.0% | Rs 63,878.71 | Rs 952,214.16 | 0.68 |
| 10 | 2024 | 2024-01-02 to 2024-10-31 | 24 | 45.8% | Rs -123,590.64 | Rs 828,623.51 | -1.75 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*