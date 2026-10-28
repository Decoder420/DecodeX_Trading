# Quantitative Walk-Forward Research Report: LightGBM_Direction_3B on NIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `LightGBM_Direction_3B` | **Instrument**: `NIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **13.91%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.19** | -0.28 | 0.63 | 0.63 | 0.03 |
| **CAGR** | **-0.57%** | -0.81% | 9.10% | **0.37%** | N/A |
| **Excess Return vs Exposure B&H** | **-0.94%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.07** | -0.10 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **13.91%** | 14.97% | 38.44% | N/A | N/A |
| **Calmar Ratio** | **-0.04** | -0.05 | N/A | N/A | N/A |
| **Win Rate** | **33.33%** | 33.33% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.74** | 0.66 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -54,919.61** | Rs -77,237.28 | N/A | N/A | N/A |
| **Total Trade Count** | **24** | 24 | 1 | N/A | 24 |
| **Market Exposure** | **4.1%** | 4.1% | 100.0% | 4.1% | N/A |
| **Expectancy / Trade**| **Rs -2,288.32** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **44.3%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9994** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.75, -0.06]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **1/10 (10.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **1488** | Total BUY (1088) and SELL (400) raw signals |
| **Data Gap Gate** | **13** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1396** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **30** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **8** | Signals on contract expiry days |
| **Final Executed Signals** | **41** | Final approved trades (0 BUY, 41 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2016 | 6 | 16.7% | Rs -46,419.73 | -4.64% | -1.59 |
| 2017 | 11 | 36.4% | Rs -24,841.18 | -2.61% | -0.40 |
| 2018 | 6 | 33.3% | Rs -16,976.62 | -1.83% | -0.42 |
| 2019 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2020 | 1 | 100.0% | Rs 33,317.93 | 3.65% | 1.01 |
| 2021 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 5 | 60.0% | Rs 20,926.83 | 0.61 |
| RANGING | 19 | 26.3% | Rs -75,846.43 | -1.07 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 0 | 0.0% | Rs 0.00 | 0.00 |
| **SELL (Short)** | 24 | 33.3% | Rs -54,919.61 | -0.68 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,000,000.00 | 0.00 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 6 | 16.7% | Rs -46,419.73 | Rs 953,580.27 | -1.59 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 11 | 36.4% | Rs -24,841.18 | Rs 928,739.09 | -0.40 |
| 4 | 2018 | 2018-01-02 to 2018-12-31 | 6 | 33.3% | Rs -16,976.62 | Rs 911,762.47 | -0.42 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 0 | 0.0% | Rs 0.00 | Rs 911,762.47 | 0.00 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 1 | 100.0% | Rs 33,317.93 | Rs 945,080.39 | 1.01 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 0 | 0.0% | Rs 0.00 | Rs 945,080.39 | 0.00 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 945,080.39 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 0 | 0.0% | Rs 0.00 | Rs 945,080.39 | 0.00 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 0 | 0.0% | Rs 0.00 | Rs 945,080.39 | 0.00 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*