# Quantitative Walk-Forward Research Report: Baseline_Trend_EMA_ADX on NIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class B (Marginal or Unstable Edge)**
- **Verdict Rationale**: Marginal or unconfirmed candidate; fails Class A criteria: Sharpe 0.36 <= B&H 0.63; Bootstrap difference 95% CI [-1.22, 0.37] does not exclude zero; Random noise rank 50.5% < 95.0%; DSR p-value 0.94 >= 0.10; Positive years 20.0% < 70.0%; Weak sample (3 < 100 trades).
- **Model**: `Baseline_Trend_EMA_ADX` | **Instrument**: `NIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **0.69%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **0.36** | 0.35 | 0.63 | 0.63 | -0.19 |
| **CAGR** | **0.32%** | 0.31% | 9.10% | **0.03%** | N/A |
| **Excess Return vs Exposure B&H** | **+0.29%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **0.00** | 0.00 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **0.69%** | 0.71% | 38.44% | N/A | N/A |
| **Calmar Ratio** | **0.46** | 0.43 | N/A | N/A | N/A |
| **Win Rate** | **66.67%** | 66.67% | N/A | N/A | ~50.0% |
| **Profit Factor** | **5.44** | 5.11 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs 31,825.71** | Rs 30,425.92 | N/A | N/A | N/A |
| **Total Trade Count** | **3** | 3 | 1 | N/A | 3 |
| **Market Exposure** | **0.4%** | 0.4% | 100.0% | 0.4% | N/A |
| **Expectancy / Trade**| **Rs 10,608.57** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **50.5%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9358** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.22, 0.37]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **2/10 (20.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **7** | Total BUY (1) and SELL (6) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **0** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **1** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **3** | Signals on contract expiry days |
| **Final Executed Signals** | **3** | Final approved trades (1 BUY, 2 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2016 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2017 | 1 | 100.0% | Rs 22,817.66 | 2.28% | 1.01 |
| 2018 | 1 | 100.0% | Rs 16,172.91 | 1.58% | 1.02 |
| 2019 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2020 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2021 | 1 | 0.0% | Rs -7,164.86 | -0.69% | -1.01 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 0 | 0.0% | Rs 0.00 | 0.00 |
| RANGING | 3 | 66.7% | Rs 31,825.71 | 1.43 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 1 | 100.0% | Rs 22,817.66 | 0.00 |
| **SELL (Short)** | 2 | 50.0% | Rs 9,008.05 | 0.55 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,000,000.00 | 0.00 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 0 | 0.0% | Rs 0.00 | Rs 1,000,000.00 | 0.00 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 1 | 100.0% | Rs 22,817.66 | Rs 1,022,817.66 | 1.01 |
| 4 | 2018 | 2018-01-02 to 2018-12-31 | 1 | 100.0% | Rs 16,172.91 | Rs 1,038,990.57 | 1.02 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,038,990.57 | 0.00 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,038,990.57 | 0.00 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 1 | 0.0% | Rs -7,164.86 | Rs 1,031,825.71 | -1.01 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 1,031,825.71 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 0 | 0.0% | Rs 0.00 | Rs 1,031,825.71 | 0.00 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 0 | 0.0% | Rs 0.00 | Rs 1,031,825.71 | 0.00 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*