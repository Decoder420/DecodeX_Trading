# Quantitative Walk-Forward Research Report: LightGBM_Triple_Barrier on POOLED

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.

## 1. Executive Summary & Decision Gate: **Class B (Marginal or Unstable Edge)**
- **Verdict Rationale**: Positive returns but unstable: does not beat Buy & Hold benchmark (3.34 vs 5.74). Edge does not conclusively clear the institutional threshold.
- **Model**: `LightGBM_Triple_Barrier` | **Instrument**: `POOLED`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Random Baseline (1,000 Seeds Mean) |
| :--- | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **3.34** | 3.34 | 5.74 | 0.00 |
| **CAGR** | **17277.88%** | 17170.27% | 17.00% | N/A |
| **Sortino Ratio** | **20.46** | 20.47 | N/A | N/A |
| **Max Drawdown** | **34.52%** | 34.57% | 81.86% | N/A |
| **Calmar Ratio** | **500.58** | 496.69 | N/A | N/A |
| **Win Rate** | **51.45%** | 50.83% | N/A | ~50.0% |
| **Profit Factor** | **32.35** | 32.27 | N/A | ~1.00 |
| **Total Net P&L** | **Rs 10,539,079,464,592,504,404,471,447,552.00** | Rs 9,914,675,919,176,645,111,967,645,696.00 | N/A | N/A |
| **Total Trade Count** | **1625** | 1625 | 1 | 1625 |
| **Market Exposure** | **81.4%** | 81.4% | 100.0% | N/A |
| **Expectancy / Trade**| **Rs 6,485,587,362,826,156,855,263,232.00** | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **100.0%** (Higher than 100.0% of 1,000 random noise strategies)
- **Tested Hyperparameter Variants Count**: `48` combinations evaluated
- **Deflated Sharpe Ratio (DSR)**: **1.0000** (Statistically significant (DSR > 0.95))

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **4173** | Total BUY (7) and SELL (4166) raw signals |
| **Data Gap Gate** | **22** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **1484** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **26** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **648** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **317** | Signals within 1 day of derivatives contract expiry |
| **Final Executed Signals** | **1676** | Final approved trades (0 BUY, 1676 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) |
| :---: | :---: | :---: | :---: |
| 2015 | 250 | 52.0% | Rs 28,643,805.44 |
| 2016 | 170 | 50.6% | Rs 15,632,813,505.63 |
| 2017 | 162 | 42.6% | Rs 25,062,786,416,384.36 |
| 2018 | 129 | 47.3% | Rs 1,093,568,703,591,997.75 |
| 2019 | 187 | 51.3% | Rs 660,058,196,696,463,744.00 |
| 2020 | 184 | 51.1% | Rs 93,037,208,002,997,993,472.00 |
| 2021 | 186 | 52.7% | Rs 3,523,416,244,323,302,244,352.00 |
| 2022 | 153 | 56.9% | Rs 98,856,873,602,744,192,073,728.00 |
| 2023 | 132 | 54.5% | Rs 184,506,389,589,550,424,890,802,176.00 |
| 2024 | 72 | 59.7% | Rs 10,354,470,601,014,720,242,789,646,336.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| TRENDING | 746 | 53.8% | Rs 5,393,028,676,933,199,468,649,512,960.00 |
| RANGING | 870 | 49.9% | Rs 5,146,050,787,323,287,585,303,822,336.00 |
| HIGH_VOL | 9 | 11.1% | Rs 336,015,293,616,641,152.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| **BUY (Long)** | 0 | 0.0% | Rs 0.00 |
| **SELL (Short)** | 1625 | 51.4% | Rs 10,539,079,464,592,504,404,471,447,552.00 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 250 | 52.0% | Rs 28,643,805.44 | Rs 29,643,805.44 | 3.28 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 170 | 50.6% | Rs 15,632,813,505.63 | Rs 15,662,457,311.06 | 3.41 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 162 | 42.6% | Rs 25,062,786,416,384.36 | Rs 25,078,448,873,695.43 | 3.47 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 129 | 47.3% | Rs 1,093,568,703,591,997.50 | Rs 1,118,647,152,465,693.00 | 2.72 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 187 | 51.3% | Rs 660,058,196,696,463,872.00 | Rs 661,176,843,848,929,536.00 | 4.23 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 184 | 51.1% | Rs 93,037,208,002,997,960,704.00 | Rs 93,698,384,846,846,902,272.00 | 3.79 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 186 | 52.7% | Rs 3,523,416,244,323,302,244,352.00 | Rs 3,617,114,629,170,149,720,064.00 | 2.84 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 153 | 56.9% | Rs 98,856,873,602,744,225,628,160.00 | Rs 103,257,763,767,210,320,330,752.00 | 3.42 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 132 | 54.5% | Rs 184,506,389,589,550,459,250,540,544.00 | Rs 184,609,647,353,317,657,558,384,640.00 | 4.01 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 72 | 59.7% | Rs 10,354,470,601,014,722,441,812,901,888.00 | Rs 10,539,080,248,368,038,896,780,443,648.00 | 3.48 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*