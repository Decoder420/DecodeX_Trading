# Quantitative Walk-Forward Research Report: Logistic_Regression_L1 on NIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Logistic_Regression_L1` | **Instrument**: `NIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **29.91%**
- **Kill Switch Triggers**: **3** times | **Total Days Paused**: **50** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.36** | -0.58 | 0.63 | 0.63 | 0.00 |
| **CAGR** | **-3.23%** | -4.99% | 9.10% | **4.95%** | N/A |
| **Excess Return vs Exposure B&H** | **-8.19%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.37** | -0.55 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **29.91%** | 41.38% | 38.44% | N/A | N/A |
| **Calmar Ratio** | **-0.11** | -0.12 | N/A | N/A | N/A |
| **Win Rate** | **48.32%** | 47.30% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.84** | 0.76 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -276,161.63** | Rs -395,648.28 | N/A | N/A | N/A |
| **Total Trade Count** | **298** | 296 | 1 | N/A | 298 |
| **Market Exposure** | **54.4%** | 54.4% | 100.0% | 54.4% | N/A |
| **Expectancy / Trade**| **Rs -926.72** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **22.8%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9999** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.88, -0.12]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **6/10 (60.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2419** | Total BUY (2282) and SELL (137) raw signals |
| **Data Gap Gate** | **24** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **671** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **445** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **376** | Signals on contract expiry days |
| **Final Executed Signals** | **903** | Final approved trades (894 BUY, 9 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 51 | 37.3% | Rs -168,526.85 | -16.85% | -1.94 |
| 2016 | 7 | 57.1% | Rs 4,380.90 | 0.53% | 0.23 |
| 2017 | 16 | 62.5% | Rs 28,834.55 | 3.45% | 0.53 |
| 2018 | 33 | 54.5% | Rs 2,501.27 | 0.29% | 0.08 |
| 2019 | 32 | 46.9% | Rs -52,876.41 | -6.10% | -0.91 |
| 2020 | 31 | 54.8% | Rs -38,136.84 | -4.68% | -0.78 |
| 2021 | 35 | 51.4% | Rs 3,177.38 | 0.41% | 0.09 |
| 2022 | 30 | 46.7% | Rs 57,150.43 | 7.33% | 0.60 |
| 2023 | 35 | 51.4% | Rs 145.18 | 0.02% | 0.05 |
| 2024 | 28 | 39.3% | Rs -112,811.26 | -13.48% | -1.79 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 139 | 48.9% | Rs -79,051.34 | -0.50 |
| RANGING | 159 | 47.8% | Rs -197,110.29 | -1.37 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 290 | 48.6% | Rs -248,381.16 | -1.11 |
| **SELL (Short)** | 8 | 37.5% | Rs -27,780.47 | -0.58 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 51 | 37.3% | Rs -168,526.85 | Rs 831,473.15 | -1.94 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 7 | 57.1% | Rs 4,380.90 | Rs 835,854.05 | 0.23 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 16 | 62.5% | Rs 28,834.55 | Rs 864,688.61 | 0.53 |
| 4 | 2018 | 2018-01-02 to 2018-12-31 | 33 | 54.5% | Rs 2,501.27 | Rs 867,189.88 | 0.08 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 32 | 46.9% | Rs -52,876.41 | Rs 814,313.47 | -0.91 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 31 | 54.8% | Rs -38,136.84 | Rs 776,176.64 | -0.78 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 35 | 51.4% | Rs 3,177.38 | Rs 779,354.02 | 0.09 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 30 | 46.7% | Rs 57,150.43 | Rs 836,504.44 | 0.60 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 35 | 51.4% | Rs 145.18 | Rs 836,649.62 | 0.05 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 28 | 39.3% | Rs -112,811.26 | Rs 723,838.37 | -1.79 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*