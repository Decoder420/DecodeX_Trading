# Quantitative Walk-Forward Research Report: Consensus_Ensemble on BANKNIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Consensus_Ensemble` | **Instrument**: `BANKNIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **19.13%**
- **Kill Switch Triggers**: **1** times | **Total Days Paused**: **20** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.56** | -0.57 | 0.59 | 0.59 | 0.07 |
| **CAGR** | **-1.85%** | -1.84% | 11.21% | **0.81%** | N/A |
| **Excess Return vs Exposure B&H** | **-2.66%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.24** | -0.20 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **19.13%** | 18.22% | 47.86% | N/A | N/A |
| **Calmar Ratio** | **-0.10** | -0.10 | N/A | N/A | N/A |
| **Win Rate** | **33.33%** | 26.83% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.51** | 0.50 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -167,785.02** | Rs -167,110.91 | N/A | N/A | N/A |
| **Total Trade Count** | **42** | 41 | 1 | N/A | 42 |
| **Market Exposure** | **7.3%** | 7.3% | 100.0% | 7.3% | N/A |
| **Expectancy / Trade**| **Rs -3,994.88** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **31.3%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **1.0000** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-2.17, -0.31]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **1/10 (10.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **1311** | Total BUY (789) and SELL (522) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1071** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **10** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **71** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **68** | Signals on contract expiry days |
| **Final Executed Signals** | **91** | Final approved trades (12 BUY, 79 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 3 | 33.3% | Rs -7,899.39 | -0.79% | -0.58 |
| 2016 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2017 | 32 | 31.2% | Rs -139,036.11 | -14.01% | -1.51 |
| 2018 | 1 | 100.0% | Rs 8,776.85 | 1.03% | 1.02 |
| 2019 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2020 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2021 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2024 | 6 | 33.3% | Rs -29,626.38 | -3.44% | -1.49 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 8 | 50.0% | Rs -42,053.58 | -1.56 |
| RANGING | 34 | 29.4% | Rs -125,731.44 | -1.52 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 10 | 40.0% | Rs -28,748.92 | -1.11 |
| **SELL (Short)** | 32 | 31.2% | Rs -139,036.11 | -1.68 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 3 | 33.3% | Rs -7,899.39 | Rs 992,100.61 | -0.58 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 0 | 0.0% | Rs 0.00 | Rs 992,100.61 | 0.00 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 32 | 31.2% | Rs -139,036.11 | Rs 853,064.50 | -1.51 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 1 | 100.0% | Rs 8,776.85 | Rs 861,841.35 | 1.02 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 0 | 0.0% | Rs 0.00 | Rs 861,841.35 | 0.00 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 0 | 0.0% | Rs 0.00 | Rs 861,841.35 | 0.00 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 0 | 0.0% | Rs 0.00 | Rs 861,841.35 | 0.00 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 861,841.35 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 0 | 0.0% | Rs 0.00 | Rs 861,841.35 | 0.00 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 6 | 33.3% | Rs -29,626.38 | Rs 832,214.98 | -1.49 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*