# Quantitative Walk-Forward Research Report: LightGBM_Triple_Barrier on NIFTY

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.
> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**

## 1. Executive Summary & Decision Gate: **Class C (No Edge After Costs)**
- **Verdict Rationale**: Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected.
- **Model**: `LightGBM_Triple_Barrier` | **Instrument**: `NIFTY`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)
- **True Max Drawdown from All-Time Peak**: **41.76%**
- **Kill Switch Triggers**: **3** times | **Total Days Paused**: **60** trading days

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **-0.62** | -0.91 | 0.63 | 0.63 | 0.02 |
| **CAGR** | **-3.95%** | -5.67% | 9.10% | **2.66%** | N/A |
| **Excess Return vs Exposure B&H** | **-6.61%** | N/A | N/A | 0.00% | N/A |
| **Sortino Ratio** | **-0.46** | -0.64 | N/A | N/A | N/A |
| **Max Drawdown (True Peak)** | **41.76%** | 50.26% | 38.44% | N/A | N/A |
| **Calmar Ratio** | **-0.09** | -0.11 | N/A | N/A | N/A |
| **Win Rate** | **36.25%** | 34.78% | N/A | N/A | ~50.0% |
| **Profit Factor** | **0.67** | 0.57 | N/A | N/A | ~1.00 |
| **Total Net P&L** | **Rs -327,250.30** | Rs -436,645.61 | N/A | N/A | N/A |
| **Total Trade Count** | **160** | 161 | 1 | N/A | 160 |
| **Market Exposure** | **29.2%** | 29.2% | 100.0% | 29.2% | N/A |
| **Expectancy / Trade**| **Rs -2,045.31** | N/A | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **15.2%** (Must be >= 95.0% for Class A)
- **Total Research Trials Evaluated ($K$)**: `162` (All models x instruments x gate variants)
- **Expected Maximum Sharpe under Null ($E[\max SR]$)**: **0.84**
- **Deflated Sharpe Ratio (DSR) p-value**: **1.0000** (p >= 0.10: Inconclusive under multiple testing)
- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[-2.26, -0.32]** (Includes zero - cannot reject B&H equivalence)
- **Walk-Forward Positive Years**: **2/10 (20.0%)**

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **2354** | Total BUY (822) and SELL (1532) raw signals |
| **Data Gap Gate** | **24** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1553** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **0** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **196** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **96** | Signals on contract expiry days |
| **Final Executed Signals** | **485** | Final approved trades (158 BUY, 327 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 41 | 39.0% | Rs -115,703.61 | -11.57% | -1.42 |
| 2016 | 29 | 37.9% | Rs -19,479.21 | -2.20% | -0.28 |
| 2017 | 45 | 24.4% | Rs -191,257.04 | -22.12% | -2.07 |
| 2018 | 2 | 0.0% | Rs -18,386.65 | -2.73% | -1.42 |
| 2019 | 3 | 33.3% | Rs -11,969.78 | -1.83% | -0.61 |
| 2020 | 7 | 42.9% | Rs -669.01 | -0.10% | -0.02 |
| 2021 | 13 | 38.5% | Rs -35,754.75 | -5.56% | -1.23 |
| 2022 | 1 | 0.0% | Rs -6,290.84 | -1.04% | -1.01 |
| 2023 | 7 | 57.1% | Rs 18,178.14 | 3.03% | 0.75 |
| 2024 | 12 | 58.3% | Rs 54,082.44 | 8.74% | 1.30 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 45 | 44.4% | Rs -16,010.87 | -0.20 |
| RANGING | 115 | 33.0% | Rs -311,239.43 | -2.53 |
| HIGH_VOL | 0 | 0.0% | Rs 0.00 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0.00 | 0.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 46 | 37.0% | Rs -142,179.05 | -1.79 |
| **SELL (Short)** | 114 | 36.0% | Rs -185,071.25 | -1.50 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-02 to 2015-12-31 | 41 | 39.0% | Rs -115,703.61 | Rs 884,296.39 | -1.42 |
| 2 | 2016 | 2016-01-04 to 2016-12-30 | 29 | 37.9% | Rs -19,479.21 | Rs 864,817.17 | -0.28 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 45 | 24.4% | Rs -191,257.04 | Rs 673,560.14 | -2.07 |
| 4 | 2018 | 2018-01-02 to 2018-12-31 | 2 | 0.0% | Rs -18,386.65 | Rs 655,173.49 | -1.42 |
| 5 | 2019 | 2019-01-02 to 2019-12-31 | 3 | 33.3% | Rs -11,969.78 | Rs 643,203.71 | -0.61 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 7 | 42.9% | Rs -669.01 | Rs 642,534.70 | -0.02 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 13 | 38.5% | Rs -35,754.75 | Rs 606,779.95 | -1.23 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 1 | 0.0% | Rs -6,290.84 | Rs 600,489.12 | -1.01 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 7 | 57.1% | Rs 18,178.14 | Rs 618,667.26 | 0.75 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 12 | 58.3% | Rs 54,082.44 | Rs 672,749.70 | 1.30 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*