# Quantitative Walk-Forward Research Report: Baseline_Trend_EMA_ADX on SENSEX

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class B (Marginal or Unstable Edge)**
- **Verdict Rationale**: Marginal or unconfirmed candidate; fails Class A criteria: Sharpe 0.06 <= B&H 0.61; Bootstrap difference 95% CI [-1.56, 0.20] does not exclude zero; Random noise rank 49.1% < 95.0%; DSR p-value 0.99 >= 0.10; Positive years 10.0% < 70.0%; Weak sample (3 < 100 trades).
- **Model**: `Baseline_Trend_EMA_ADX` | **Instrument**: `SENSEX`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **1.71%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **0.06** | 0.04 | 0.61 | 0.61 | -0.37 |
| **CAGR** | **0.04%** | 0.03% | 8.86% | **0.07%** | N/A |
| **Excess Return vs Exposure B&H** | **-0.03%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **0.02** | 0.01 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **1.71%** | 1.75% | 38.07% | N/A | N/A |
| **Calmar Ratio** | **0.03** | 0.02 | N/A | N/A | N/A |
| **Win Rate** | **33.33%** | 33.33% | N/A | N/A | ~50.0% |
| **Profit Factor** | **1.24** | 1.17 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs 4,216.52** | Rs 3,077.19 | N/A | N/A | N/A |
| **Total Trade Count** | **3** | 3 | 1 | N/A | 3 |
| **Market Exposure** | **0.8%** | 0.8% | 100.0% | 0.8% | N/A |
| **Expectancy / Trade**| **Rs 1,405.51** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **49.1%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9932** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.56, 0.20]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **1/10 (10.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **6** | Total BUY (1) and SELL (5) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **0** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **2** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **1** | Signals on contract expiry days |
| **Final Executed Signals** | **3** | Final approved trades (1 BUY, 2 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2016 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2017 | 1 | 100.0% | Rs 21,679.81 | 2.17% | 1.01 |
| 2018 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2019 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2020 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2021 | 2 | 0.0% | Rs -17,463.29 | -1.71% | -1.41 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 1 | 100.0% | Rs 21,679.81 | 0.00 |
| RANGING | 2 | 0.0% | Rs -17,463.29 | -7.15 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 1 | 100.0% | Rs 21,679.81 | 0.00 |
| **SELL (Short)** | 2 | 0.0% | Rs -17,463.29 | -7.15 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,000,000.00 | 0.00 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 0 | 0.0% | Rs 0.00 | Rs 1,000,000.00 | 0.00 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 1 | 100.0% | Rs 21,679.81 | Rs 1,021,679.81 | 1.01 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,021,679.81 | 0.00 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,021,679.81 | 0.00 |
| 6 | 2020 | 2020-01-02 to 2020-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,021,679.81 | 0.00 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 2 | 0.0% | Rs -17,463.29 | Rs 1,004,216.52 | -1.41 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 1,004,216.52 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 0 | 0.0% | Rs 0.00 | Rs 1,004,216.52 | 0.00 |
| 10 | 2024 | 2024-01-02 to 2024-10-31 | 0 | 0.0% | Rs 0.00 | Rs 1,004,216.52 | 0.00 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*