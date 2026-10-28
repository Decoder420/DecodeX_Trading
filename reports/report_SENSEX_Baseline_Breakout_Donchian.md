# Quantitative Walk-Forward Research Report: Baseline_Breakout_Donchian on SENSEX

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Baseline_Breakout_Donchian` | **Instrument**: `SENSEX`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **8.12%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.01** | -0.11 | 0.61 | 0.61 | -0.01 |
| **CAGR** | **-0.12%** | -0.50% | 8.86% | **2.74%** | N/A |
| **Excess Return vs Exposure B&H** | **-2.85%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.00** | -0.05 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **8.12%** | 9.30% | 38.07% | N/A | N/A |
| **Calmar Ratio** | **-0.01** | -0.05 | N/A | N/A | N/A |
| **Win Rate** | **48.45%** | 48.45% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.98** | 0.91 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -11,534.00** | Rs -48,210.25 | N/A | N/A | N/A |
| **Total Trade Count** | **97** | 97 | 1 | N/A | 97 |
| **Market Exposure** | **30.9%** | 30.9% | 100.0% | 30.9% | N/A |
| **Expectancy / Trade**| **Rs -118.91** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **49.4%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9964** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.46, 0.25]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **2/10 (20.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **358** | Total BUY (250) and SELL (108) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **0** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **4** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **92** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **48** | Signals on contract expiry days |
| **Final Executed Signals** | **214** | Final approved trades (162 BUY, 52 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 12 | 33.3% | Rs -50,712.72 | -5.07% | -1.63 |
| 2016 | 8 | 37.5% | Rs -383.90 | -0.04% | 0.01 |
| 2017 | 9 | 44.4% | Rs -5,418.28 | -0.57% | -0.16 |
| 2018 | 10 | 70.0% | Rs 84,222.94 | 8.93% | 1.58 |
| 2019 | 11 | 45.5% | Rs -17,506.31 | -1.70% | -0.36 |
| 2020 | 12 | 50.0% | Rs -5,538.56 | -0.55% | -0.17 |
| 2021 | 11 | 63.6% | Rs 40,886.73 | 4.07% | 1.05 |
| 2022 | 9 | 44.4% | Rs -8,682.11 | -0.83% | -0.29 |
| 2023 | 10 | 50.0% | Rs -1,150.29 | -0.11% | -0.01 |
| 2024 | 5 | 40.0% | Rs -47,251.49 | -4.56% | -1.65 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 44 | 59.1% | Rs 121,354.34 | 1.43 |
| RANGING | 53 | 39.6% | Rs -132,888.33 | -1.60 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 67 | 55.2% | Rs 41,775.89 | 0.45 |
| **SELL (Short)** | 30 | 33.3% | Rs -53,309.89 | -0.70 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 12 | 33.3% | Rs -50,712.72 | Rs 949,287.28 | -1.63 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 8 | 37.5% | Rs -383.90 | Rs 948,903.38 | 0.01 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 9 | 44.4% | Rs -5,418.28 | Rs 943,485.11 | -0.16 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 10 | 70.0% | Rs 84,222.94 | Rs 1,027,708.05 | 1.58 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 11 | 45.5% | Rs -17,506.31 | Rs 1,010,201.73 | -0.36 |
| 6 | 2020 | 2020-01-02 to 2020-12-31 | 12 | 50.0% | Rs -5,538.56 | Rs 1,004,663.17 | -0.17 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 11 | 63.6% | Rs 40,886.73 | Rs 1,045,549.90 | 1.05 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 9 | 44.4% | Rs -8,682.11 | Rs 1,036,867.79 | -0.29 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 10 | 50.0% | Rs -1,150.29 | Rs 1,035,717.50 | -0.01 |
| 10 | 2024 | 2024-01-02 to 2024-10-31 | 5 | 40.0% | Rs -47,251.49 | Rs 988,466.00 | -1.65 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*