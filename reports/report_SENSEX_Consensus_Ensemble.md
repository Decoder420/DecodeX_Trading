# Quantitative Walk-Forward Research Report: Consensus_Ensemble on SENSEX

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Consensus_Ensemble` | **Instrument**: `SENSEX`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **24.58%**
- **Kill Switch Triggers**: **1** times | **Total Days Paused**: **20** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.61** | -0.69 | 0.61 | 0.61 | -0.01 |
| **CAGR** | **-2.42%** | -2.75% | 8.86% | **1.15%** | N/A |
| **Excess Return vs Exposure B&H** | **-3.57%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.15** | -0.17 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **24.58%** | 26.70% | 38.07% | N/A | N/A |
| **Calmar Ratio** | **-0.10** | -0.10 | N/A | N/A | N/A |
| **Win Rate** | **37.31%** | 35.82% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.54** | 0.50 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -214,189.84** | Rs -239,447.85 | N/A | N/A | N/A |
| **Total Trade Count** | **67** | 67 | 1 | N/A | 67 |
| **Market Exposure** | **13.0%** | 13.0% | 100.0% | 13.0% | N/A |
| **Expectancy / Trade**| **Rs -3,196.86** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **27.3%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **1.0000** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-2.11, -0.42]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **1/10 (10.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **911** | Total BUY (809) and SELL (102) raw signals |
| **Data Gap Gate** | **16** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **646** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **4** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **64** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **21** | Signals on contract expiry days |
| **Final Executed Signals** | **160** | Final approved trades (130 BUY, 30 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 28 | 39.3% | Rs -137,919.52 | -13.79% | -1.56 |
| 2016 | 20 | 35.0% | Rs -58,482.64 | -6.78% | -1.28 |
| 2017 | 1 | 100.0% | Rs 19,192.09 | 2.39% | 1.01 |
| 2018 | 2 | 0.0% | Rs -17,849.44 | -2.17% | -1.44 |
| 2019 | 15 | 40.0% | Rs -11,562.16 | -1.44% | -0.28 |
| 2020 | 1 | 0.0% | Rs -7,568.17 | -0.95% | -1.01 |
| 2021 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2022 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0.00 | 0.00% | 0.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 26 | 46.2% | Rs 9,184.12 | 0.17 |
| RANGING | 41 | 31.7% | Rs -223,373.96 | -2.56 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 54 | 35.2% | Rs -199,472.37 | -2.04 |
| **SELL (Short)** | 13 | 46.2% | Rs -14,717.47 | -0.37 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 28 | 39.3% | Rs -137,919.52 | Rs 862,080.48 | -1.56 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 20 | 35.0% | Rs -58,482.64 | Rs 803,597.84 | -1.28 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 1 | 100.0% | Rs 19,192.09 | Rs 822,789.93 | 1.01 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 2 | 0.0% | Rs -17,849.44 | Rs 804,940.49 | -1.44 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 15 | 40.0% | Rs -11,562.16 | Rs 793,378.33 | -0.28 |
| 6 | 2020 | 2020-01-02 to 2020-12-31 | 1 | 0.0% | Rs -7,568.17 | Rs 785,810.16 | -1.01 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 0 | 0.0% | Rs 0.00 | Rs 785,810.16 | 0.00 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 0 | 0.0% | Rs 0.00 | Rs 785,810.16 | 0.00 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 0 | 0.0% | Rs 0.00 | Rs 785,810.16 | 0.00 |
| 10 | 2024 | 2024-01-02 to 2024-10-31 | 0 | 0.0% | Rs 0.00 | Rs 785,810.16 | 0.00 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*