# Quantitative Walk-Forward Research Report: Baseline_Breakout_Donchian on BANKNIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Baseline_Breakout_Donchian` | **Instrument**: `BANKNIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **5.56%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.04** | -0.11 | 0.59 | 0.59 | -0.00 |
| **CAGR** | **-0.15%** | -0.35% | 11.21% | **2.65%** | N/A |
| **Excess Return vs Exposure B&H** | **-2.81%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.02** | -0.04 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **5.56%** | 5.94% | 47.86% | N/A | N/A |
| **Calmar Ratio** | **-0.03** | -0.06 | N/A | N/A | N/A |
| **Win Rate** | **48.78%** | 45.12% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.96** | 0.90 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -15,094.57** | Rs -34,212.15 | N/A | N/A | N/A |
| **Total Trade Count** | **82** | 82 | 1 | N/A | 82 |
| **Market Exposure** | **23.7%** | 23.7% | 100.0% | 23.7% | N/A |
| **Expectancy / Trade**| **Rs -184.08** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **48.0%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9973** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.66, 0.20]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **4/10 (40.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **344** | Total BUY (242) and SELL (102) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **0** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **10** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **91** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **96** | Signals on contract expiry days |
| **Final Executed Signals** | **147** | Final approved trades (114 BUY, 33 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 9 | 22.2% | Rs -36,575.99 | -3.66% | -1.86 |
| 2016 | 7 | 57.1% | Rs 11,381.13 | 1.18% | 0.55 |
| 2017 | 7 | 42.9% | Rs -9,733.14 | -1.00% | -0.22 |
| 2018 | 7 | 57.1% | Rs 5,419.37 | 0.56% | 0.22 |
| 2019 | 10 | 70.0% | Rs 49,369.27 | 5.09% | 1.66 |
| 2020 | 11 | 54.5% | Rs -6,388.35 | -0.63% | -0.34 |
| 2021 | 11 | 27.3% | Rs -34,733.84 | -3.43% | -1.27 |
| 2022 | 7 | 71.4% | Rs 23,961.60 | 2.45% | 0.94 |
| 2023 | 10 | 50.0% | Rs -2,226.35 | -0.22% | -0.06 |
| 2024 | 3 | 33.3% | Rs -15,568.28 | -1.56% | -0.67 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 51 | 51.0% | Rs 13,035.14 | 0.20 |
| RANGING | 30 | 43.3% | Rs -28,332.39 | -0.49 |
| HIGH_VOL | 1 | 100.0% | Rs 202.68 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 58 | 56.9% | Rs 62,721.39 | 0.86 |
| **SELL (Short)** | 24 | 29.2% | Rs -77,815.96 | -1.78 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 9 | 22.2% | Rs -36,575.99 | Rs 963,424.01 | -1.86 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 7 | 57.1% | Rs 11,381.13 | Rs 974,805.14 | 0.55 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 7 | 42.9% | Rs -9,733.14 | Rs 965,072.00 | -0.22 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 7 | 57.1% | Rs 5,419.37 | Rs 970,491.37 | 0.22 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 10 | 70.0% | Rs 49,369.27 | Rs 1,019,860.64 | 1.66 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 11 | 54.5% | Rs -6,388.35 | Rs 1,013,472.30 | -0.34 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 11 | 27.3% | Rs -34,733.84 | Rs 978,738.46 | -1.27 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 7 | 71.4% | Rs 23,961.60 | Rs 1,002,700.06 | 0.94 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 10 | 50.0% | Rs -2,226.35 | Rs 1,000,473.71 | -0.06 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 3 | 33.3% | Rs -15,568.28 | Rs 984,905.43 | -0.67 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*