# Quantitative Walk-Forward Research Report: Logistic_Regression_L2 on BANKNIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class B (Marginal or Unstable Edge)**
- **Verdict Rationale**: Marginal or unconfirmed candidate; fails Class A criteria: Sharpe 0.27 <= B&H 0.59; Bootstrap difference 95% CI [-1.37, 0.42] does not exclude zero; Random noise rank 67.7% < 95.0%; DSR p-value 0.96 >= 0.10; Positive years 40.0% < 70.0%.
- **Model**: `Logistic_Regression_L2` | **Instrument**: `BANKNIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **14.17%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **0.27** | 0.17 | 0.59 | 0.59 | 0.03 |
| **CAGR** | **1.90%** | 1.10% | 11.21% | **4.73%** | N/A |
| **Excess Return vs Exposure B&H** | **-2.83%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **0.29** | 0.17 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **14.17%** | 15.76% | 47.86% | N/A | N/A |
| **Calmar Ratio** | **0.13** | 0.07 | N/A | N/A | N/A |
| **Win Rate** | **47.47%** | 46.08% | N/A | N/A | ~50.0% |
| **Profit Factor** | **1.16** | 1.09 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs 203,696.46** | Rs 113,786.16 | N/A | N/A | N/A |
| **Total Trade Count** | **217** | 217 | 1 | N/A | 217 |
| **Market Exposure** | **42.2%** | 42.2% | 100.0% | 42.2% | N/A |
| **Expectancy / Trade**| **Rs 938.69** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **67.7%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9643** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.37, 0.42]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **4/10 (40.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2425** | Total BUY (1829) and SELL (596) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1046** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **11** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **361** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **348** | Signals on contract expiry days |
| **Final Executed Signals** | **659** | Final approved trades (658 BUY, 1 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 46 | 34.8% | Rs 46,132.35 | 4.61% | 0.36 |
| 2016 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2017 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2018 | 28 | 53.6% | Rs 71,253.06 | 6.81% | 0.93 |
| 2019 | 32 | 46.9% | Rs -34,399.46 | -3.08% | -0.50 |
| 2020 | 12 | 50.0% | Rs -11,702.57 | -1.08% | -0.61 |
| 2021 | 9 | 44.4% | Rs -7,403.42 | -0.69% | -0.38 |
| 2022 | 24 | 50.0% | Rs 162,428.81 | 15.27% | 1.08 |
| 2023 | 34 | 58.8% | Rs 50,030.76 | 4.08% | 0.60 |
| 2024 | 32 | 46.9% | Rs -72,643.06 | -5.69% | -0.74 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 152 | 48.0% | Rs 315,832.44 | 1.19 |
| RANGING | 65 | 46.2% | Rs -112,135.98 | -1.18 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 216 | 47.7% | Rs 209,702.16 | 0.74 |
| **SELL (Short)** | 1 | 0.0% | Rs -6,005.69 | 0.00 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 46 | 34.8% | Rs 46,132.35 | Rs 1,046,132.35 | 0.36 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 0 | 0.0% | Rs 0.00 | Rs 1,046,132.35 | 0.00 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 0 | 0.0% | Rs 0.00 | Rs 1,046,132.35 | 0.00 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 28 | 53.6% | Rs 71,253.06 | Rs 1,117,385.41 | 0.93 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 32 | 46.9% | Rs -34,399.46 | Rs 1,082,985.95 | -0.50 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 12 | 50.0% | Rs -11,702.57 | Rs 1,071,283.38 | -0.61 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 9 | 44.4% | Rs -7,403.42 | Rs 1,063,879.96 | -0.38 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 24 | 50.0% | Rs 162,428.81 | Rs 1,226,308.76 | 1.08 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 34 | 58.8% | Rs 50,030.76 | Rs 1,276,339.52 | 0.60 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 32 | 46.9% | Rs -72,643.06 | Rs 1,203,696.46 | -0.74 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*