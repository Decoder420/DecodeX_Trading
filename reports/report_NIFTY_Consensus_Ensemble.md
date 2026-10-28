# Quantitative Walk-Forward Research Report: Consensus_Ensemble on NIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Consensus_Ensemble` | **Instrument**: `NIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **23.08%**
- **Kill Switch Triggers**: **1** times | **Total Days Paused**: **20** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.68** | -0.51 | 0.63 | 0.63 | 0.04 |
| **CAGR** | **-2.32%** | -2.00% | 9.10% | **0.94%** | N/A |
| **Excess Return vs Exposure B&H** | **-3.26%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.31** | -0.26 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **23.08%** | 20.43% | 38.44% | N/A | N/A |
| **Calmar Ratio** | **-0.10** | -0.10 | N/A | N/A | N/A |
| **Win Rate** | **32.76%** | 35.48% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.53** | 0.62 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -205,692.77** | Rs -180,249.61 | N/A | N/A | N/A |
| **Total Trade Count** | **58** | 62 | 1 | N/A | 58 |
| **Market Exposure** | **10.3%** | 10.3% | 100.0% | 10.3% | N/A |
| **Expectancy / Trade**| **Rs -3,546.43** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **26.2%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **1.0000** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-2.27, -0.39]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **0/10 (0.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **959** | Total BUY (843) and SELL (116) raw signals |
| **Data Gap Gate** | **17** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **705** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **57** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **26** | Signals on contract expiry days |
| **Final Executed Signals** | **154** | Final approved trades (117 BUY, 37 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 34 | 38.2% | Rs -74,544.25 | -7.45% | -0.97 |
| 2016 | 6 | 16.7% | Rs -34,987.33 | -3.78% | -1.16 |
| 2017 | 10 | 20.0% | Rs -75,867.34 | -8.52% | -1.67 |
| 2018 | 1 | 0.0% | Rs -9,195.08 | -1.13% | -1.02 |
| 2019 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2020 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2021 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2024 | 7 | 42.9% | Rs -11,098.77 | -1.38% | -0.42 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 20 | 40.0% | Rs -34,459.27 | -0.74 |
| RANGING | 38 | 28.9% | Rs -171,233.50 | -2.13 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 42 | 38.1% | Rs -94,838.09 | -1.21 |
| **SELL (Short)** | 16 | 18.8% | Rs -110,854.67 | -2.32 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 34 | 38.2% | Rs -74,544.25 | Rs 925,455.75 | -0.97 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 6 | 16.7% | Rs -34,987.33 | Rs 890,468.42 | -1.16 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 10 | 20.0% | Rs -75,867.34 | Rs 814,601.08 | -1.67 |
| 4 | 2018 | 2018-01-02 to 2018-12-31 | 1 | 0.0% | Rs -9,195.08 | Rs 805,406.00 | -1.02 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 0 | 0.0% | Rs 0.00 | Rs 805,406.00 | 0.00 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 0 | 0.0% | Rs 0.00 | Rs 805,406.00 | 0.00 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 0 | 0.0% | Rs 0.00 | Rs 805,406.00 | 0.00 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 805,406.00 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 0 | 0.0% | Rs 0.00 | Rs 805,406.00 | 0.00 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 7 | 42.9% | Rs -11,098.77 | Rs 794,307.23 | -0.42 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*