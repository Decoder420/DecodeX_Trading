# Quantitative Walk-Forward Research Report: Baseline_Breakout_Donchian on NIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `Baseline_Breakout_Donchian` | **Instrument**: `NIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ⚠️ STATISTICALLY WEAK (< 100 trades)
- **True Max Drawdown from All-Time Peak**: **8.65%**
- **Kill Switch Triggers**: **0** times | **Total Days Paused**: **0** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.09** | -0.19 | 0.63 | 0.63 | 0.02 |
| **CAGR** | **-0.45%** | -0.85% | 9.10% | **2.61%** | N/A |
| **Excess Return vs Exposure B&H** | **-3.06%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.04** | -0.09 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **8.65%** | 9.78% | 38.44% | N/A | N/A |
| **Calmar Ratio** | **-0.05** | -0.09 | N/A | N/A | N/A |
| **Win Rate** | **45.83%** | 45.83% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.92** | 0.85 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -43,111.58** | Rs -80,705.83 | N/A | N/A | N/A |
| **Total Trade Count** | **96** | 96 | 1 | N/A | 96 |
| **Market Exposure** | **28.7%** | 28.7% | 100.0% | 28.7% | N/A |
| **Expectancy / Trade**| **Rs -449.08** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **43.1%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **0.9983** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-1.64, 0.19]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **6/10 (60.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **368** | Total BUY (268) and SELL (100) raw signals |
| **Data Gap Gate** | **0** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **0** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **5** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **95** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **80** | Signals on contract expiry days |
| **Final Executed Signals** | **188** | Final approved trades (146 BUY, 42 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 11 | 36.4% | Rs -43,177.65 | -4.32% | -1.50 |
| 2016 | 9 | 44.4% | Rs 945.41 | 0.10% | 0.04 |
| 2017 | 10 | 30.0% | Rs -44,255.68 | -4.62% | -1.09 |
| 2018 | 10 | 60.0% | Rs 43,472.42 | 4.76% | 0.90 |
| 2019 | 9 | 44.4% | Rs 14,616.24 | 1.53% | 0.43 |
| 2020 | 10 | 60.0% | Rs 14,011.42 | 1.44% | 0.54 |
| 2021 | 11 | 54.5% | Rs 18,441.84 | 1.87% | 0.42 |
| 2022 | 9 | 44.4% | Rs -2,997.06 | -0.30% | -0.06 |
| 2023 | 11 | 54.5% | Rs 9,341.40 | 0.93% | 0.24 |
| 2024 | 6 | 16.7% | Rs -53,509.92 | -5.30% | -2.08 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 46 | 47.8% | Rs 6,609.03 | 0.07 |
| RANGING | 50 | 44.0% | Rs -49,720.60 | -0.61 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 69 | 50.7% | Rs 44,430.86 | 0.44 |
| **SELL (Short)** | 27 | 33.3% | Rs -87,542.44 | -1.24 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 11 | 36.4% | Rs -43,177.65 | Rs 956,822.35 | -1.50 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 9 | 44.4% | Rs 945.41 | Rs 957,767.76 | 0.04 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 10 | 30.0% | Rs -44,255.68 | Rs 913,512.08 | -1.09 |
| 4 | 2018 | 2018-01-02 to 2018-12-31 | 10 | 60.0% | Rs 43,472.42 | Rs 956,984.50 | 0.90 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 9 | 44.4% | Rs 14,616.24 | Rs 971,600.74 | 0.43 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 10 | 60.0% | Rs 14,011.42 | Rs 985,612.16 | 0.54 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 11 | 54.5% | Rs 18,441.84 | Rs 1,004,054.01 | 0.42 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 9 | 44.4% | Rs -2,997.06 | Rs 1,001,056.95 | -0.06 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 11 | 54.5% | Rs 9,341.40 | Rs 1,010,398.34 | 0.24 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 6 | 16.7% | Rs -53,509.92 | Rs 956,888.42 | -2.08 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*