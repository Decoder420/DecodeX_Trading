# Quantitative Walk-Forward Research Report: LightGBM_Triple_Barrier on SENSEX

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `LightGBM_Triple_Barrier` | **Instrument**: `SENSEX`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **49.23%**
- **Kill Switch Triggers**: **4** times | **Total Days Paused**: **80** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.97** | -1.08 | 0.61 | 0.61 | -0.03 |
| **CAGR** | **-6.18%** | -6.99% | 8.86% | **2.43%** | N/A |
| **Excess Return vs Exposure B&H** | **-8.61%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.51** | -0.56 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **49.23%** | 53.19% | 38.07% | N/A | N/A |
| **Calmar Ratio** | **-0.13** | -0.13 | N/A | N/A | N/A |
| **Win Rate** | **34.21%** | 33.77% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.52** | 0.48 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -465,806.48** | Rs -509,606.03 | N/A | N/A | N/A |
| **Total Trade Count** | **152** | 154 | 1 | N/A | 152 |
| **Market Exposure** | **27.4%** | 27.4% | 100.0% | 27.4% | N/A |
| **Expectancy / Trade**| **Rs -3,064.52** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **6.7%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **1.0000** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-2.48, -0.70]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **1/10 (10.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2401** | Total BUY (912) and SELL (1489) raw signals |
| **Data Gap Gate** | **24** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1549** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **8** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **230** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **90** | Signals on contract expiry days |
| **Final Executed Signals** | **500** | Final approved trades (156 BUY, 344 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 34 | 41.2% | Rs -165,324.60 | -16.53% | -1.93 |
| 2016 | 38 | 31.6% | Rs -109,954.74 | -13.17% | -1.31 |
| 2017 | 39 | 30.8% | Rs -103,382.73 | -14.27% | -1.29 |
| 2018 | 3 | 0.0% | Rs -23,089.84 | -3.72% | -1.74 |
| 2019 | 8 | 25.0% | Rs -23,193.59 | -3.88% | -1.38 |
| 2020 | 1 | 0.0% | Rs -5,498.53 | -0.96% | -1.01 |
| 2021 | 9 | 66.7% | Rs 18,455.61 | 3.24% | 0.99 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 20 | 30.0% | Rs -53,818.06 | -9.15% | -1.31 |
| 2024 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 50 | 30.0% | Rs -161,848.89 | -1.96 |
| RANGING | 102 | 36.3% | Rs -303,957.58 | -2.66 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 53 | 34.0% | Rs -275,332.16 | -3.06 |
| **SELL (Short)** | 99 | 34.3% | Rs -190,474.31 | -1.78 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 34 | 41.2% | Rs -165,324.60 | Rs 834,675.40 | -1.93 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 38 | 31.6% | Rs -109,954.74 | Rs 724,720.66 | -1.31 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 39 | 30.8% | Rs -103,382.73 | Rs 621,337.93 | -1.29 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 3 | 0.0% | Rs -23,089.84 | Rs 598,248.09 | -1.74 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 8 | 25.0% | Rs -23,193.59 | Rs 575,054.50 | -1.38 |
| 6 | 2020 | 2020-01-02 to 2020-12-31 | 1 | 0.0% | Rs -5,498.53 | Rs 569,555.97 | -1.01 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 9 | 66.7% | Rs 18,455.61 | Rs 588,011.59 | 0.99 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 588,011.59 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 20 | 30.0% | Rs -53,818.06 | Rs 534,193.52 | -1.31 |
| 10 | 2024 | 2024-01-02 to 2024-10-31 | 0 | 0.0% | Rs 0.00 | Rs 534,193.52 | 0.00 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*