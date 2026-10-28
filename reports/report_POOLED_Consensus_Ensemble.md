# Quantitative Walk-Forward Research Report: Consensus_Ensemble on POOLED

> [!IMPORTANT]
> **Proxy & Historical Continuity Disclaimer**:
> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.
> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.
> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.

## 1. Executive Summary & Decision Gate: **Class B (Marginal or Unstable Edge)**
- **Verdict Rationale**: Positive returns but unstable: does not beat Buy & Hold benchmark (3.62 vs 5.74). Edge does not conclusively clear the institutional threshold.
- **Model**: `Consensus_Ensemble` | **Instrument**: `POOLED`
- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)
- **Slippage Setting**: Base `base` (1.5 bps/side) vs Stress (5.0 bps/side)
- **Sample Size Qualification**: ✅ ADEQUATE SAMPLE (>= 100 trades)

---

## 2. Performance Metrics vs Benchmarks

| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Random Baseline (1,000 Seeds Mean) |
| :--- | :---: | :---: | :---: | :---: |
| **Sharpe Ratio** | **3.62** | 3.62 | 5.74 | 0.00 |
| **CAGR** | **1852783.91%** | 1837437.44% | 17.00% | N/A |
| **Sortino Ratio** | **302.77** | 299.91 | N/A | N/A |
| **Max Drawdown** | **4.93%** | 4.94% | 81.86% | N/A |
| **Calmar Ratio** | **375525.50** | 371817.03 | N/A | N/A |
| **Win Rate** | **57.53%** | 57.16% | N/A | ~50.0% |
| **Profit Factor** | **32.80** | 32.73 | N/A | ~1.00 |
| **Total Net P&L** | **Rs 911,740,107,823,876,850,258,615,501,704,360,714,060,588,646,400.00** | Rs 840,154,414,625,927,276,747,083,620,549,633,362,590,823,350,272.00 | N/A | N/A |
| **Total Trade Count** | **1858** | 1858 | 1 | 1858 |
| **Market Exposure** | **92.4%** | 92.4% | 100.0% | N/A |
| **Expectancy / Trade**| **Rs 490,710,499,366,995,106,191,007,810,535,351,873,741,783,040.00** | N/A | N/A | N/A |

### Multiple Testing & Statistical Significance
- **Random Baseline Percentile Rank**: **100.0%** (Higher than 100.0% of 1,000 random noise strategies)
- **Tested Hyperparameter Variants Count**: `48` combinations evaluated
- **Deflated Sharpe Ratio (DSR)**: **1.0000** (Statistically significant (DSR > 0.95))

---

## 3. Trade Gating Filter Removal Breakdown

| Gate / Filter | Trades Dropped | Description & Threshold |
| :--- | :---: | :--- |
| **Raw Signals Emitted** | **5376** | Total BUY (2767) and SELL (2609) raw signals |
| **Data Gap Gate** | **31** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |
| **Confidence Gate** | **2230** | Signals below calibrated probability threshold |
| **Regime Filter Gate** | **29** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |
| **VIX Percentile Gate** | **732** | Signals where VIX percentile > 85% or < 5% |
| **Expiry Proximity Gate**| **427** | Signals within 1 day of derivatives contract expiry |
| **Final Executed Signals** | **1927** | Final approved trades (932 BUY, 995 SELL) |
| **Total Filter Removal Rate** | **0.0%** | Overall fraction of raw signals filtered out |

---

## 4. Multi-Dimensional Performance Breakdowns

### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)
| Year | Trades | Win Rate | Net P&L (INR) |
| :---: | :---: | :---: | :---: |
| 2015 | 185 | 54.1% | Rs 254,673,582,255.39 |
| 2016 | 186 | 56.5% | Rs 18,255,336,722,529,632.00 |
| 2017 | 215 | 66.5% | Rs 6,426,389,105,102,679,034,560,512.00 |
| 2018 | 225 | 57.3% | Rs 495,202,246,621,327,400,243,323,469,824.00 |
| 2019 | 249 | 55.4% | Rs 139,692,202,041,822,820,211,459,666,011,488,256.00 |
| 2020 | 244 | 55.7% | Rs 2,353,482,810,506,183,471,157,006,777,881,855,000,576.00 |
| 2021 | 216 | 56.0% | Rs 438,258,561,959,335,021,850,272,465,058,643,969,048,576.00 |
| 2022 | 150 | 56.7% | Rs 11,495,764,209,124,046,646,004,041,076,431,089,450,352,640.00 |
| 2023 | 116 | 59.5% | Rs 15,958,629,412,791,559,877,824,372,182,099,851,679,224,561,664.00 |
| 2024 | 72 | 59.7% | Rs 895,769,542,034,691,984,491,328,599,333,462,034,062,250,082,304.00 |

### B. Regime Breakdown
| Market Regime | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| TRENDING | 913 | 55.5% | Rs 469,191,749,270,567,789,652,885,300,057,129,663,229,289,562,112.00 |
| RANGING | 935 | 59.9% | Rs 442,548,358,531,121,564,832,826,737,123,703,282,126,490,173,440.00 |
| HIGH_VOL | 10 | 20.0% | Rs 22,187,742,660,833,056,731,368,761,725,135,355,904.00 |

### C. Direction Breakdown (Long vs Short)
| Direction | Trades | Win Rate | Net P&L (INR) |
| :--- | :---: | :---: | :---: |
| **BUY (Long)** | 900 | 60.0% | Rs 12,045,519,286,789,057,957,524,200,460,944,599,416,832.00 |
| **SELL (Short)** | 958 | 55.2% | Rs 911,740,095,778,357,746,560,862,758,119,871,388,854,618,423,296.00 |

---

## 5. Walk-Forward Fold Progression
| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 2015 | 2015-01-01 to 2015-12-31 | 185 | 54.1% | Rs 254,673,582,255.39 | Rs 254,674,582,255.39 | 4.17 |
| 2 | 2016 | 2016-01-01 to 2016-12-30 | 186 | 56.5% | Rs 18,255,336,722,529,628.00 | Rs 18,075,860,808,779,604.00 | 3.90 |
| 3 | 2017 | 2017-01-02 to 2017-12-29 | 215 | 66.5% | Rs 6,426,389,105,102,680,108,302,336.00 | Rs 6,373,254,846,024,204,249,202,688.00 | 4.73 |
| 4 | 2018 | 2018-01-01 to 2018-12-31 | 225 | 57.3% | Rs 495,202,246,621,327,329,874,579,292,160.00 | Rs 495,208,619,876,173,367,654,146,375,680.00 | 3.58 |
| 5 | 2019 | 2019-01-01 to 2019-12-31 | 249 | 55.4% | Rs 139,692,202,041,822,838,658,203,739,721,039,872.00 | Rs 139,692,697,250,442,711,791,993,489,113,219,072.00 | 4.25 |
| 6 | 2020 | 2020-01-01 to 2020-12-31 | 244 | 55.7% | Rs 2,353,482,810,506,183,471,157,006,777,881,855,000,576.00 | Rs 2,353,622,503,203,433,846,353,715,461,594,009,305,088.00 | 3.99 |
| 7 | 2021 | 2021-01-01 to 2021-12-31 | 216 | 56.0% | Rs 438,258,561,959,335,099,221,524,920,394,911,150,243,840.00 | Rs 440,612,184,462,538,447,536,376,898,121,491,049,086,976.00 | 3.57 |
| 8 | 2022 | 2022-01-03 to 2022-12-30 | 150 | 56.7% | Rs 11,495,764,209,124,046,646,004,041,076,431,089,450,352,640.00 | Rs 12,027,672,145,404,154,331,547,041,490,878,846,445,027,328.00 | 3.39 |
| 9 | 2023 | 2023-01-02 to 2023-12-29 | 116 | 59.5% | Rs 15,958,629,412,791,559,877,824,372,182,099,851,679,224,561,664.00 | Rs 15,970,657,084,936,965,210,674,836,623,272,752,229,635,850,240.00 | 3.93 |
| 10 | 2024 | 2024-01-01 to 2024-10-31 | 72 | 59.7% | Rs 895,769,542,034,691,822,232,051,770,120,098,642,484,239,794,176.00 | Rs 911,740,199,119,628,812,795,738,611,307,959,424,647,939,751,936.00 | 3.48 |

---
*(Report generated by Antigravity Quantitative Research Platform - Part 2)*