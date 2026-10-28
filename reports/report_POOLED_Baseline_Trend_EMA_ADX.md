# Quantitative Walk-Forward Research Report: Baseline_Trend_EMA_ADX on POOLED

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Baseline_Trend_EMA_ADX` | **Instrument**: `POOLED`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Random Baseline (1,000 Seeds Mean) |
| :--- | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.30** | -0.30 | 5.74 | 0.03 |
| **CAGR** | **nan%** | nan% | 17.00% | N/A |
| **Sortino Ratio** | **-0.03** | -0.03 | N/A | N/A |
| **Max Drawdown** | **200.31%** | 200.39% | 81.86% | N/A |
| **Calmar Ratio** | **nan** | nan | N/A | N/A |
| **Win Rate** | **41.67%** | 41.67% | N/A | ~50.0% |
| **Profit Factor** | **0.20** | 0.20 | N/A | ~1.00 |
| **Total Net P&L** | **Rs -2,278,359.45** | Rs -2,278,276.48 | N/A | N/A |
| **Total Trade Count** | **48** | 48 | 1 | 48 |
| **Market Exposure** | **2.4%** | 2.4% | 100.0% | N/A |
| **Expectancy / Trade**| **Rs -47,465.82** | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **41.5%** (Higher than 41.5% of 1,000 random noise strategies)
- **Tested Hyperparameter Variants Count**: `48` combinations evaluated
- **Deflated Sharpe Ratio (DSR)**: **0.0000** (Not statistically significant after accounting for multiple trials)

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **95** | Total BUY (26) and SELL (69) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **0** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **25** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **20** | Signals within 1 day of derivatives contract expiry |
| **Final Executed Signals** | **50** | Final approved trades (12 BUY, 38 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) |
| :---: | :---: | :---: | :---: |
| 2016 | 7 | 28.6% | Rs -4,517.74 |
| 2017 | 4 | 25.0% | Rs -18,472.70 |
| 2018 | 10 | 60.0% | Rs 35,268.04 |
| 2019 | 2 | 50.0% | Rs -35,327.75 |
| 2020 | 3 | 0.0% | Rs -21,953.88 |
| 2021 | 15 | 46.7% | Rs 300,925.95 |
| 2022 | 1 | 0.0% | Rs -215,526.08 |
| 2023 | 5 | 60.0% | Rs 5,835.04 |
| 2024 | 1 | 0.0% | Rs -2,324,590.34 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| TRENDING | 22 | 36.4% | Rs -2,221,309.95 |
| RANGING | 26 | 46.2% | Rs -57,049.50 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| **BUY (Long)** | 11 | 36.4% | Rs 225,259.81 |
| **SELL (Short)** | 37 | 43.2% | Rs -2,503,619.27 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,000,000.00 | 0.00 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 7 | 28.6% | Rs -4,517.74 | Rs 995,482.26 | -0.17 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 4 | 25.0% | Rs -18,472.70 | Rs 977,009.56 | -0.80 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 10 | 60.0% | Rs 35,268.04 | Rs 1,012,277.61 | 0.92 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 2 | 50.0% | Rs -35,327.75 | Rs 976,949.86 | -1.02 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 3 | 0.0% | Rs -21,953.88 | Rs 954,995.98 | -1.42 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 15 | 46.7% | Rs 300,925.95 | Rs 1,255,921.93 | 0.86 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 1 | 0.0% | Rs -215,526.08 | Rs 1,040,395.85 | -1.01 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 5 | 60.0% | Rs 5,835.04 | Rs 1,046,230.89 | 0.29 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 1 | 0.0% | Rs -2,324,590.34 | Rs -1,278,359.45 | -1.11 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*