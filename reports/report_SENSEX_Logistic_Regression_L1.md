# Quantitative Walk-Forward Research Report: Logistic_Regression_L1 on SENSEX

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Logistic_Regression_L1` | **Instrument**: `SENSEX`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **24.26%**
- **Kill Switch Triggers**: **3** times | **Total Days Paused**: **60** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.14** | -0.31 | 0.61 | 0.61 | -0.01 |
| **CAGR** | **-1.88%** | -3.50% | 8.86% | **5.28%** | N/A |
| **Excess Return vs Exposure B&H** | **-7.16%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.13** | -0.27 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **24.26%** | 31.60% | 38.07% | N/A | N/A |
| **Calmar Ratio** | **-0.08** | -0.11 | N/A | N/A | N/A |
| **Win Rate** | **49.53%** | 48.75% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.91** | 0.85 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -169,939.29** | Rs -295,432.10 | N/A | N/A | N/A |
| **Total Trade Count** | **319** | 320 | 1 | N/A | 319 |
| **Market Exposure** | **59.6%** | 59.6% | 100.0% | 59.6% | N/A |
| **Expectancy / Trade**| **Rs -532.73** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **37.9%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9990** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.77, 0.16]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **3/10 (30.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2419** | Total BUY (2243) and SELL (176) raw signals |
| **Data Gap Gate** | **24** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **597** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **17** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **455** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **206** | Signals on contract expiry days |
| **Final Executed Signals** | **1120** | Final approved trades (1108 BUY, 12 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 46 | 41.3% | Rs -186,330.51 | -18.63% | -1.96 |
| 2016 | 8 | 37.5% | Rs -4,475.50 | -0.55% | -0.15 |
| 2017 | 22 | 68.2% | Rs 100,025.31 | 12.36% | 1.74 |
| 2018 | 37 | 54.1% | Rs -1,602.49 | -0.18% | 0.02 |
| 2019 | 35 | 42.9% | Rs -63,938.79 | -7.04% | -1.00 |
| 2020 | 42 | 64.3% | Rs 177,385.03 | 21.03% | 1.14 |
| 2021 | 36 | 44.4% | Rs -81,645.59 | -8.00% | -1.14 |
| 2022 | 31 | 41.9% | Rs -49,546.36 | -5.27% | -0.44 |
| 2023 | 38 | 50.0% | Rs 63,992.47 | 7.19% | 0.68 |
| 2024 | 24 | 45.8% | Rs -123,802.87 | -12.98% | -1.75 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 133 | 54.1% | Rs 24,228.65 | 0.16 |
| RANGING | 186 | 46.2% | Rs -194,167.94 | -0.81 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 312 | 49.7% | Rs -173,755.75 | -0.56 |
| **SELL (Short)** | 7 | 42.9% | Rs 3,816.47 | 0.14 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 46 | 41.3% | Rs -186,330.51 | Rs 813,669.49 | -1.96 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 8 | 37.5% | Rs -4,475.50 | Rs 809,193.99 | -0.15 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 22 | 68.2% | Rs 100,025.31 | Rs 909,219.30 | 1.74 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 37 | 54.1% | Rs -1,602.49 | Rs 907,616.82 | 0.02 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 35 | 42.9% | Rs -63,938.79 | Rs 843,678.03 | -1.00 |
| 6 | 2020 | 2020-01-02 to 2020-12-31 | 42 | 64.3% | Rs 177,385.03 | Rs 1,021,063.06 | 1.14 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 36 | 44.4% | Rs -81,645.59 | Rs 939,417.47 | -1.14 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 31 | 41.9% | Rs -49,546.36 | Rs 889,871.11 | -0.44 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 38 | 50.0% | Rs 63,992.47 | Rs 953,863.58 | 0.68 |
| 10 | 2024 | 2024-01-02 to 2024-10-31 | 24 | 45.8% | Rs -123,802.87 | Rs 830,060.71 | -1.75 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*