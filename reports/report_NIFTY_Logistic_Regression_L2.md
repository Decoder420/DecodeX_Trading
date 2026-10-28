# Quantitative Walk-Forward Research Report: Logistic_Regression_L2 on NIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Logistic_Regression_L2` | **Instrument**: `NIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **27.07%**
- **Kill Switch Triggers**: **3** times | **Total Days Paused**: **50** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.32** | -0.57 | 0.63 | 0.63 | 0.01 |
| **CAGR** | **-2.84%** | -4.80% | 9.10% | **5.21%** | N/A |
| **Excess Return vs Exposure B&H** | **-8.05%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.32** | -0.52 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **27.07%** | 40.20% | 38.44% | N/A | N/A |
| **Calmar Ratio** | **-0.11** | -0.12 | N/A | N/A | N/A |
| **Win Rate** | **49.67%** | 48.33% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.85** | 0.77 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -246,918.99** | Rs -383,525.73 | N/A | N/A | N/A |
| **Total Trade Count** | **300** | 300 | 1 | N/A | 300 |
| **Market Exposure** | **57.2%** | 57.2% | 100.0% | 57.2% | N/A |
| **Expectancy / Trade**| **Rs -823.06** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **25.3%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9999** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.85, -0.07]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **5/10 (50.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2419** | Total BUY (2303) and SELL (116) raw signals |
| **Data Gap Gate** | **24** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **522** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **25** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **468** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **429** | Signals on contract expiry days |
| **Final Executed Signals** | **951** | Final approved trades (933 BUY, 18 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 51 | 37.3% | Rs -168,526.85 | -16.85% | -1.94 |
| 2016 | 5 | 60.0% | Rs 476.62 | 0.06% | 0.04 |
| 2017 | 14 | 64.3% | Rs 41,490.14 | 4.99% | 0.84 |
| 2018 | 33 | 54.5% | Rs 2,542.04 | 0.29% | 0.08 |
| 2019 | 32 | 46.9% | Rs -53,397.35 | -6.10% | -0.91 |
| 2020 | 37 | 62.2% | Rs -892.86 | -0.11% | 0.01 |
| 2021 | 36 | 55.6% | Rs 31,884.42 | 3.88% | 0.59 |
| 2022 | 29 | 44.8% | Rs 23,686.84 | 2.78% | 0.28 |
| 2023 | 35 | 51.4% | Rs -6,871.51 | -0.78% | -0.04 |
| 2024 | 28 | 39.3% | Rs -117,310.50 | -13.48% | -1.79 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 137 | 48.9% | Rs -101,155.94 | -0.64 |
| RANGING | 163 | 50.3% | Rs -145,763.06 | -1.00 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 291 | 49.5% | Rs -264,829.99 | -1.17 |
| **SELL (Short)** | 9 | 55.6% | Rs 17,910.99 | 0.40 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 51 | 37.3% | Rs -168,526.85 | Rs 831,473.15 | -1.94 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 5 | 60.0% | Rs 476.62 | Rs 831,949.77 | 0.04 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 14 | 64.3% | Rs 41,490.14 | Rs 873,439.91 | 0.84 |
| 4 | 2018 | 2018-01-02 to 2018-12-31 | 33 | 54.5% | Rs 2,542.04 | Rs 875,981.95 | 0.08 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 32 | 46.9% | Rs -53,397.35 | Rs 822,584.60 | -0.91 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 37 | 62.2% | Rs -892.86 | Rs 821,691.74 | 0.01 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 36 | 55.6% | Rs 31,884.42 | Rs 853,576.17 | 0.59 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 29 | 44.8% | Rs 23,686.84 | Rs 877,263.01 | 0.28 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 35 | 51.4% | Rs -6,871.51 | Rs 870,391.51 | -0.04 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 28 | 39.3% | Rs -117,310.50 | Rs 753,081.01 | -1.79 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*