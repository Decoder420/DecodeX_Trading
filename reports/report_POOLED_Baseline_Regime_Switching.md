# Quantitative Walk-Forward Research Report: Baseline_Regime_Switching on POOLED

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Baseline_Regime_Switching` | **Instrument**: `POOLED`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Random Baseline (1,000 Seeds Mean) |
| :--- | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.19** | -0.19 | 5.74 | -0.05 |
| **CAGR** | **-0.70%** | -0.70% | 17.00% | N/A |
| **Sortino Ratio** | **-0.02** | -0.02 | N/A | N/A |
| **Max Drawdown** | **11.22%** | 11.24% | 81.86% | N/A |
| **Calmar Ratio** | **-0.06** | -0.06 | N/A | N/A |
| **Win Rate** | **41.18%** | 41.18% | N/A | ~50.0% |
| **Profit Factor** | **0.60** | 0.60 | N/A | ~1.00 |
| **Total Net P&L** | **Rs -66,602.26** | Rs -66,955.09 | N/A | N/A |
| **Total Trade Count** | **17** | 17 | 1 | 17 |
| **Market Exposure** | **0.8%** | 0.8% | 100.0% | N/A |
| **Expectancy / Trade**| **Rs -3,917.78** | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **48.9%** (Higher than 48.9% of 1,000 random noise strategies)
- **Tested Hyperparameter Variants Count**: `48` combinations evaluated
- **Deflated Sharpe Ratio (DSR)**: **0.0000** (Not statistically significant after accounting for multiple trials)

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **44** | Total BUY (11) and SELL (33) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **0** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **16** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **11** | Signals within 1 day of derivatives contract expiry |
| **Final Executed Signals** | **17** | Final approved trades (3 BUY, 14 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) |
| :---: | :---: | :---: | :---: |
| 2016 | 5 | 40.0% | Rs 1,813.81 |
| 2017 | 2 | 50.0% | Rs -12,384.73 |
| 2020 | 1 | 0.0% | Rs -8,940.83 |
| 2021 | 6 | 33.3% | Rs -60,366.50 |
| 2023 | 3 | 66.7% | Rs 13,276.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| TRENDING | 8 | 37.5% | Rs -18,028.12 |
| RANGING | 9 | 44.4% | Rs -48,574.14 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| **BUY (Long)** | 3 | 33.3% | Rs -94,928.21 |
| **SELL (Short)** | 14 | 42.9% | Rs 28,325.95 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 0 | 0.0% | Rs 0.00 | Rs 1,000,000.00 | 0.00 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 5 | 40.0% | Rs 1,813.81 | Rs 1,001,813.81 | 0.09 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 2 | 50.0% | Rs -12,384.73 | Rs 989,429.08 | -0.55 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 0 | 0.0% | Rs 0.00 | Rs 989,429.08 | 0.00 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 0 | 0.0% | Rs 0.00 | Rs 989,429.08 | 0.00 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 1 | 0.0% | Rs -8,940.83 | Rs 980,488.25 | -1.01 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 6 | 33.3% | Rs -60,366.50 | Rs 920,121.75 | -0.59 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 920,121.75 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 3 | 66.7% | Rs 13,276.00 | Rs 933,397.74 | 0.82 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 0 | 0.0% | Rs 0.00 | Rs 933,397.74 | 0.00 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*