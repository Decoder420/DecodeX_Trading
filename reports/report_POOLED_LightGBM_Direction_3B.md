# Quantitative Walk-Forward Research Report: LightGBM_Direction_3B on POOLED

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.

## 1. Executive Summary & Decision Gate: **Class B (Marginal or Unstable Edge)**
- **Verdict Rationale**: Positive returns but unstable: does not beat Buy & Hold benchmark (2.60 vs 5.74). Edge does not conclusively clear the institutional threshold.
- **Model**: `LightGBM_Direction_3B` | **Instrument**: `POOLED`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Random Baseline (1,000 Seeds Mean) |
| :--- | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **2.60** | 2.60 | 5.74 | 0.00 |
| **CAGR** | **9447.69%** | 9401.57% | 17.00% | N/A |
| **Sortino Ratio** | **12.10** | 12.14 | N/A | N/A |
| **Max Drawdown** | **71.66%** | 71.70% | 81.86% | N/A |
| **Calmar Ratio** | **131.84** | 131.12 | N/A | N/A |
| **Win Rate** | **54.51%** | 54.08% | N/A | ~50.0% |
| **Profit Factor** | **31.84** | 31.77 | N/A | ~1.00 |
| **Total Net P&L** | **Rs 29,215,404,407,925,950,543,560,704.00** | Rs 27,857,295,072,171,246,844,116,992.00 | N/A | N/A |
| **Total Trade Count** | **1163** | 1163 | 1 | 1163 |
| **Market Exposure** | **57.6%** | 57.6% | 100.0% | N/A |
| **Expectancy / Trade**| **Rs 25,120,726,060,125,495,754,752.00** | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **100.0%** (Higher than 100.0% of 1,000 random noise strategies)
- **Tested Hyperparameter Variants Count**: `48` combinations evaluated
- **Deflated Sharpe Ratio (DSR)**: **1.0000** (Statistically significant (DSR > 0.95))

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **5171** | Total BUY (2088) and SELL (3083) raw signals |
| **Data Gap Gate** | **35** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **3165** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **2** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **457** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **214** | Signals within 1 day of derivatives contract expiry |
| **Final Executed Signals** | **1298** | Final approved trades (331 BUY, 967 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) |
| :---: | :---: | :---: | :---: |
| 2015 | 421 | 53.7% | Rs 5,710,912,199,951.50 |
| 2016 | 59 | 52.5% | Rs 1,265,507,923,243,967.00 |
| 2017 | 24 | 54.2% | Rs 96,195,187,520,510,208.00 |
| 2018 | 86 | 54.7% | Rs 782,948,142,378,002,048.00 |
| 2019 | 81 | 51.9% | Rs -215,311,035,860,744,192.00 |
| 2020 | 56 | 51.8% | Rs 4,552,792,752,057,557,504.00 |
| 2021 | 141 | 53.9% | Rs 103,845,073,276,200,779,776.00 |
| 2022 | 132 | 53.8% | Rs 925,484,097,439,819,890,688.00 |
| 2023 | 96 | 61.5% | Rs 661,164,171,991,178,866,065,408.00 |
| 2024 | 67 | 59.7% | Rs 28,553,205,688,867,787,871,617,024.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| TRENDING | 574 | 55.1% | Rs 15,747,374,520,969,325,612,892,160.00 |
| RANGING | 586 | 54.3% | Rs 13,468,029,894,918,678,253,666,304.00 |
| HIGH_VOL | 3 | 0.0% | Rs -7,962,056,590,061,484.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| **BUY (Long)** | 275 | 51.6% | Rs -1,461,299,039,232,454,912.00 |
| **SELL (Short)** | 888 | 55.4% | Rs 29,215,405,869,224,986,016,743,424.00 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 421 | 53.7% | Rs 5,710,912,199,951.50 | Rs 5,710,913,199,951.50 | 4.89 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 59 | 52.5% | Rs 1,265,507,923,243,966.75 | Rs 1,258,703,388,195,634.25 | 2.45 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 24 | 54.2% | Rs 96,195,187,520,510,208.00 | Rs 97,453,890,908,705,824.00 | 2.18 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 86 | 54.7% | Rs 782,948,142,378,001,920.00 | Rs 880,402,033,286,707,712.00 | 2.16 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 81 | 51.9% | Rs -215,311,035,860,743,488.00 | Rs 665,090,997,425,964,160.00 | 0.02 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 56 | 51.8% | Rs 4,552,792,752,057,557,504.00 | Rs 5,217,883,749,483,522,048.00 | 2.31 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 141 | 53.9% | Rs 103,845,073,276,200,697,856.00 | Rs 109,062,957,025,684,226,048.00 | 2.76 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 132 | 53.8% | Rs 925,484,097,439,819,890,688.00 | Rs 1,042,459,820,284,352,135,168.00 | 2.61 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 96 | 61.5% | Rs 661,164,171,991,178,866,065,408.00 | Rs 662,206,631,811,463,178,616,832.00 | 3.77 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 67 | 59.7% | Rs 28,553,205,688,867,792,166,584,320.00 | Rs 29,215,412,320,679,255,210,983,424.00 | 3.34 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*