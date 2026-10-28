# Quantitative Walk-Forward Research Report: LightGBM_Triple_Barrier on BANKNIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `LightGBM_Triple_Barrier` | **Instrument**: `BANKNIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **22.06%**
- **Kill Switch Triggers**: **1** times | **Total Days Paused**: **20** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.17** | -0.29 | 0.59 | 0.59 | 0.02 |
| **CAGR** | **-1.00%** | -1.61% | 11.21% | **2.65%** | N/A |
| **Excess Return vs Exposure B&H** | **-3.65%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.11** | -0.18 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **22.06%** | 24.96% | 47.86% | N/A | N/A |
| **Calmar Ratio** | **-0.05** | -0.06 | N/A | N/A | N/A |
| **Win Rate** | **40.15%** | 38.64% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.87** | 0.80 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -94,030.56** | Rs -147,327.98 | N/A | N/A | N/A |
| **Total Trade Count** | **132** | 132 | 1 | N/A | 132 |
| **Market Exposure** | **23.7%** | 23.7% | 100.0% | 23.7% | N/A |
| **Expectancy / Trade**| **Rs -712.35** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **39.5%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9993** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.75, 0.02]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **5/10 (50.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2421** | Total BUY (809) and SELL (1612) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1705** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **17** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **180** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **154** | Signals on contract expiry days |
| **Final Executed Signals** | **365** | Final approved trades (126 BUY, 239 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 38 | 31.6% | Rs -95,028.99 | -9.50% | -1.25 |
| 2016 | 25 | 44.0% | Rs 29,532.03 | 3.26% | 0.56 |
| 2017 | 33 | 33.3% | Rs -89,360.97 | -9.56% | -0.94 |
| 2018 | 4 | 50.0% | Rs -5,582.72 | -0.66% | -0.22 |
| 2019 | 1 | 0.0% | Rs -319.02 | -0.04% | -1.02 |
| 2020 | 1 | 100.0% | Rs 7,403.62 | 0.88% | 1.01 |
| 2021 | 17 | 52.9% | Rs 26,798.79 | 3.17% | 0.79 |
| 2022 | 2 | 50.0% | Rs 14,853.92 | 1.70% | 0.59 |
| 2023 | 4 | 75.0% | Rs 45,215.81 | 5.09% | 1.27 |
| 2024 | 7 | 42.9% | Rs -27,543.05 | -2.95% | -1.25 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 59 | 40.7% | Rs -29,321.07 | -0.33 |
| RANGING | 72 | 38.9% | Rs -72,113.11 | -0.64 |
| HIGH_VOL | 1 | 100.0% | Rs 7,403.62 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 47 | 36.2% | Rs -98,384.70 | -1.29 |
| **SELL (Short)** | 85 | 42.4% | Rs 4,354.14 | 0.04 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 38 | 31.6% | Rs -95,028.99 | Rs 904,971.01 | -1.25 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 25 | 44.0% | Rs 29,532.03 | Rs 934,503.05 | 0.56 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 33 | 33.3% | Rs -89,360.97 | Rs 845,142.08 | -0.94 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 4 | 50.0% | Rs -5,582.72 | Rs 839,559.36 | -0.22 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 1 | 0.0% | Rs -319.02 | Rs 839,240.34 | -1.02 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 1 | 100.0% | Rs 7,403.62 | Rs 846,643.97 | 1.01 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 17 | 52.9% | Rs 26,798.79 | Rs 873,442.76 | 0.79 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 2 | 50.0% | Rs 14,853.92 | Rs 888,296.68 | 0.59 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 4 | 75.0% | Rs 45,215.81 | Rs 933,512.49 | 1.27 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 7 | 42.9% | Rs -27,543.05 | Rs 905,969.44 | -1.25 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*