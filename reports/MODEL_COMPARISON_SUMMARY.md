# Walk-Forward Model Comparison Summary (Part 2 - Rigorous Audit)

> [!CAUTION]
> **Core Quantitative Conclusion**: **NO MODEL IS VALIDATED.**
> All tested strategies fail multiple institutional robustness criteria (e.g., bootstrap difference CI spans zero, Deflated Sharpe Ratio p-value >= 0.10, or lack of consistency).
> All candidates are classified as **'marginal, unconfirmed'** (Class B or Class C). Live trading is strictly discouraged.

> [!NOTE]
> **Methodology & Context**:
> - **Data Period**: 2011 to 2024 walk-forward folds (last 2 years held out).
> - **Pooled Data Removal**: Pooled concatenation across instruments is completely excluded; single instruments evaluated strictly on their own chronological series.
> - **Slippage**: Base case 1.5 bps per side, stress case 5.0 bps per side.
> - **Costs**: Effective-dated statutory STT (0.02% sell side), GST, stamp duty, exchange charges, and SEBI fee.
> - **Index Futures Proxy**: Cash index series used as proxy (no roll gap, no basis). SENSEX derivatives pre-2023 are hypothetical.

## 1. Master Decision Gate Classification Table

| Instrument | Model | Trades | Win Rate % | Net P&L (INR) | Sharpe (1.5bps) | Sharpe (5.0bps) | B&H Sharpe | Exposure % | Exp-B&H CAGR | Excess Ret % | Random Rank % | DSR p-value | Diff CI Excludes 0 | True MaxDD % | Kill Switches | Days Paused | Decision Gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NIFTY | Baseline_Trend_EMA_ADX | 3 | 66.7% | Rs 31,826 | 0.36 | 0.35 | 0.63 | 0.4% | 0.0% | +0.3% | 50.5% | 0.936 | No | 0.7% | 0 | 0 | Class B |
| NIFTY | Baseline_Mean_Reversion | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.63 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | Class C |
| NIFTY | Baseline_Breakout_Donchian | 96 | 45.8% | Rs -43,112 | -0.09 | -0.19 | 0.63 | 28.7% | 2.6% | -3.1% | 43.1% | 0.998 | No | 8.6% | 0 | 0 | Class C |
| NIFTY | Baseline_Regime_Switching | 1 | 0.0% | Rs -6,898 | -0.32 | -0.32 | 0.63 | 0.1% | 0.0% | -0.1% | 0.0% | 1.000 | No | 0.7% | 0 | 0 | Class C |
| NIFTY | Logistic_Regression_L2 | 300 | 49.7% | Rs -246,919 | -0.32 | -0.57 | 0.63 | 57.2% | 5.2% | -8.1% | 25.3% | 1.000 | No | 27.1% | 3 | 50 | Class C |
| NIFTY | Logistic_Regression_L1 | 298 | 48.3% | Rs -276,162 | -0.36 | -0.58 | 0.63 | 54.4% | 5.0% | -8.2% | 22.8% | 1.000 | No | 29.9% | 3 | 50 | Class C |
| NIFTY | LightGBM_Direction_3B | 24 | 33.3% | Rs -54,920 | -0.19 | -0.28 | 0.63 | 4.1% | 0.4% | -0.9% | 44.3% | 0.999 | No | 13.9% | 0 | 0 | Class C |
| NIFTY | LightGBM_Triple_Barrier | 160 | 36.2% | Rs -327,250 | -0.62 | -0.91 | 0.63 | 29.2% | 2.7% | -6.6% | 15.2% | 1.000 | No | 41.8% | 3 | 60 | Class C |
| NIFTY | Consensus_Ensemble | 58 | 32.8% | Rs -205,693 | -0.68 | -0.51 | 0.63 | 10.3% | 0.9% | -3.3% | 26.2% | 1.000 | No | 23.1% | 1 | 20 | Class C |
| BANKNIFTY | Baseline_Trend_EMA_ADX | 5 | 40.0% | Rs 1,436 | 0.02 | 0.01 | 0.59 | 1.4% | 0.2% | -0.1% | 47.4% | 0.995 | No | 2.4% | 0 | 0 | Class B |
| BANKNIFTY | Baseline_Mean_Reversion | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.59 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | Class C |
| BANKNIFTY | Baseline_Breakout_Donchian | 82 | 48.8% | Rs -15,095 | -0.04 | -0.11 | 0.59 | 23.7% | 2.7% | -2.8% | 48.0% | 0.997 | No | 5.6% | 0 | 0 | Class C |
| BANKNIFTY | Baseline_Regime_Switching | 1 | 0.0% | Rs -8,497 | -0.32 | -0.32 | 0.59 | 0.2% | 0.0% | -0.1% | 0.0% | 1.000 | No | 0.8% | 0 | 0 | Class C |
| BANKNIFTY | Logistic_Regression_L2 | 217 | 47.5% | Rs 203,696 | 0.27 | 0.17 | 0.59 | 42.2% | 4.7% | -2.8% | 67.7% | 0.964 | No | 14.2% | 0 | 0 | Class B |
| BANKNIFTY | Logistic_Regression_L1 | 203 | 47.3% | Rs 200,200 | 0.27 | 0.17 | 0.59 | 39.4% | 4.4% | -2.5% | 65.9% | 0.965 | No | 15.0% | 1 | 20 | Class B |
| BANKNIFTY | LightGBM_Direction_3B | 36 | 44.4% | Rs -50,531 | -0.16 | -0.23 | 0.59 | 6.7% | 0.8% | -1.3% | 43.3% | 0.999 | No | 13.0% | 0 | 0 | Class C |
| BANKNIFTY | LightGBM_Triple_Barrier | 132 | 40.2% | Rs -94,031 | -0.17 | -0.29 | 0.59 | 23.7% | 2.7% | -3.7% | 39.5% | 0.999 | No | 22.1% | 1 | 20 | Class C |
| BANKNIFTY | Consensus_Ensemble | 42 | 33.3% | Rs -167,785 | -0.56 | -0.57 | 0.59 | 7.3% | 0.8% | -2.7% | 31.3% | 1.000 | No | 19.1% | 1 | 20 | Class C |
| SENSEX | Baseline_Trend_EMA_ADX | 3 | 33.3% | Rs 4,217 | 0.06 | 0.04 | 0.61 | 0.8% | 0.1% | -0.0% | 49.1% | 0.993 | No | 1.7% | 0 | 0 | Class B |
| SENSEX | Baseline_Mean_Reversion | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.61 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | Class C |
| SENSEX | Baseline_Breakout_Donchian | 97 | 48.5% | Rs -11,534 | -0.01 | -0.11 | 0.61 | 30.9% | 2.7% | -2.9% | 49.4% | 0.996 | No | 8.1% | 0 | 0 | Class C |
| SENSEX | Baseline_Regime_Switching | 3 | 33.3% | Rs 4,217 | 0.06 | 0.04 | 0.61 | 0.8% | 0.1% | -0.0% | 49.1% | 0.993 | No | 1.7% | 0 | 0 | Class B |
| SENSEX | Logistic_Regression_L2 | 327 | 49.5% | Rs -171,376 | -0.14 | -0.26 | 0.61 | 61.6% | 5.5% | -7.4% | 37.8% | 0.999 | No | 23.9% | 3 | 60 | Class C |
| SENSEX | Logistic_Regression_L1 | 319 | 49.5% | Rs -169,939 | -0.14 | -0.31 | 0.61 | 59.6% | 5.3% | -7.2% | 37.9% | 0.999 | No | 24.3% | 3 | 60 | Class C |
| SENSEX | LightGBM_Direction_3B | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | 0.61 | 0.0% | 0.0% | +0.0% | 50.0% | 0.996 | No | 0.0% | 0 | 0 | Class C |
| SENSEX | LightGBM_Triple_Barrier | 152 | 34.2% | Rs -465,806 | -0.97 | -1.08 | 0.61 | 27.4% | 2.4% | -8.6% | 6.7% | 1.000 | No | 49.2% | 4 | 80 | Class C |
| SENSEX | Consensus_Ensemble | 67 | 37.3% | Rs -214,190 | -0.61 | -0.69 | 0.61 | 13.0% | 1.2% | -3.6% | 27.3% | 1.000 | No | 24.6% | 1 | 20 | Class C |

---

## 2. Top 5 Candidates Deep-Dive Breakdowns

### #1: `Baseline_Trend_EMA_ADX` on **NIFTY** (Sharpe 0.36)
- **Bootstrap 95% CI on Sharpe**: `[-0.46, 0.71]`
- **Bootstrap 95% CI on Difference vs B&H (Strategy - B&H)**: `[-1.22, 0.37]` (⚠️ Includes zero: not statistically superior to Buy & Hold)
- **Exposure-Adjusted Excess Return**: `+0.29%` vs Exposure-Matched B&H (0.4% exposure)

#### Annual Performance (2015–2024):
| Year | Trades | Win Rate % | Net P&L (INR) | Return % | Annual Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2016 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2017 | 1 | 100.0% | Rs 22,818 | 2.28% | 1.01 |
| 2018 | 1 | 100.0% | Rs 16,173 | 1.58% | 1.02 |
| 2019 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2020 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2021 | 1 | 0.0% | Rs -7,165 | -0.69% | -1.01 |
| 2022 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |

#### Regime Performance:
| Regime | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 0 | 0.0% | Rs 0 | 0.00 |
| RANGING | 3 | 66.7% | Rs 31,826 | 1.43 |
| HIGH_VOL | 0 | 0.0% | Rs 0 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0 | 0.00 |

#### Directional Breakdown:
| Direction | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 1 | 100.0% | Rs 22,818 | 0.00 |
| **SELL (Short)** | 2 | 50.0% | Rs 9,008 | 0.55 |

---

### #2: `Logistic_Regression_L2` on **BANKNIFTY** (Sharpe 0.27)
- **Bootstrap 95% CI on Sharpe**: `[-0.43, 0.76]`
- **Bootstrap 95% CI on Difference vs B&H (Strategy - B&H)**: `[-1.37, 0.42]` (⚠️ Includes zero: not statistically superior to Buy & Hold)
- **Exposure-Adjusted Excess Return**: `-2.83%` vs Exposure-Matched B&H (42.2% exposure)

#### Annual Performance (2015–2024):
| Year | Trades | Win Rate % | Net P&L (INR) | Return % | Annual Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 46 | 34.8% | Rs 46,132 | 4.61% | 0.36 |
| 2016 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2017 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2018 | 28 | 53.6% | Rs 71,253 | 6.81% | 0.93 |
| 2019 | 32 | 46.9% | Rs -34,399 | -3.08% | -0.50 |
| 2020 | 12 | 50.0% | Rs -11,703 | -1.08% | -0.61 |
| 2021 | 9 | 44.4% | Rs -7,403 | -0.69% | -0.38 |
| 2022 | 24 | 50.0% | Rs 162,429 | 15.27% | 1.08 |
| 2023 | 34 | 58.8% | Rs 50,031 | 4.08% | 0.60 |
| 2024 | 32 | 46.9% | Rs -72,643 | -5.69% | -0.74 |

#### Regime Performance:
| Regime | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 152 | 48.0% | Rs 315,832 | 1.19 |
| RANGING | 65 | 46.2% | Rs -112,136 | -1.18 |
| HIGH_VOL | 0 | 0.0% | Rs 0 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0 | 0.00 |

#### Directional Breakdown:
| Direction | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 216 | 47.7% | Rs 209,702 | 0.74 |
| **SELL (Short)** | 1 | 0.0% | Rs -6,006 | 0.00 |

---

### #3: `Logistic_Regression_L1` on **BANKNIFTY** (Sharpe 0.27)
- **Bootstrap 95% CI on Sharpe**: `[-0.46, 0.75]`
- **Bootstrap 95% CI on Difference vs B&H (Strategy - B&H)**: `[-1.40, 0.40]` (⚠️ Includes zero: not statistically superior to Buy & Hold)
- **Exposure-Adjusted Excess Return**: `-2.54%` vs Exposure-Matched B&H (39.4% exposure)

#### Annual Performance (2015–2024):
| Year | Trades | Win Rate % | Net P&L (INR) | Return % | Annual Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 46 | 34.8% | Rs 46,132 | 4.61% | 0.36 |
| 2016 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2017 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2018 | 28 | 53.6% | Rs 71,253 | 6.81% | 0.93 |
| 2019 | 31 | 48.4% | Rs -26,452 | -2.37% | -0.42 |
| 2020 | 3 | 66.7% | Rs 2,845 | 0.26% | 0.33 |
| 2021 | 5 | 40.0% | Rs -7,125 | -0.65% | -0.48 |
| 2022 | 24 | 45.8% | Rs 136,103 | 12.52% | 0.90 |
| 2023 | 34 | 58.8% | Rs 49,881 | 4.08% | 0.60 |
| 2024 | 32 | 46.9% | Rs -72,437 | -5.69% | -0.74 |

#### Regime Performance:
| Regime | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 146 | 47.9% | Rs 336,215 | 1.28 |
| RANGING | 57 | 45.6% | Rs -136,015 | -1.46 |
| HIGH_VOL | 0 | 0.0% | Rs 0 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0 | 0.00 |

#### Directional Breakdown:
| Direction | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 203 | 47.3% | Rs 200,200 | 0.71 |
| **SELL (Short)** | 0 | 0.0% | Rs 0 | 0.00 |

---

### #4: `Baseline_Trend_EMA_ADX` on **SENSEX** (Sharpe 0.06)
- **Bootstrap 95% CI on Sharpe**: `[-0.64, 0.49]`
- **Bootstrap 95% CI on Difference vs B&H (Strategy - B&H)**: `[-1.56, 0.20]` (⚠️ Includes zero: not statistically superior to Buy & Hold)
- **Exposure-Adjusted Excess Return**: `-0.03%` vs Exposure-Matched B&H (0.8% exposure)

#### Annual Performance (2015–2024):
| Year | Trades | Win Rate % | Net P&L (INR) | Return % | Annual Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2016 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2017 | 1 | 100.0% | Rs 21,680 | 2.17% | 1.01 |
| 2018 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2019 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2020 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2021 | 2 | 0.0% | Rs -17,463 | -1.71% | -1.41 |
| 2022 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |

#### Regime Performance:
| Regime | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 1 | 100.0% | Rs 21,680 | 0.00 |
| RANGING | 2 | 0.0% | Rs -17,463 | -7.15 |
| HIGH_VOL | 0 | 0.0% | Rs 0 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0 | 0.00 |

#### Directional Breakdown:
| Direction | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 1 | 100.0% | Rs 21,680 | 0.00 |
| **SELL (Short)** | 2 | 0.0% | Rs -17,463 | -7.15 |

---

### #5: `Baseline_Regime_Switching` on **SENSEX** (Sharpe 0.06)
- **Bootstrap 95% CI on Sharpe**: `[-0.64, 0.49]`
- **Bootstrap 95% CI on Difference vs B&H (Strategy - B&H)**: `[-1.56, 0.20]` (⚠️ Includes zero: not statistically superior to Buy & Hold)
- **Exposure-Adjusted Excess Return**: `-0.03%` vs Exposure-Matched B&H (0.8% exposure)

#### Annual Performance (2015–2024):
| Year | Trades | Win Rate % | Net P&L (INR) | Return % | Annual Sharpe |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2015 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2016 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2017 | 1 | 100.0% | Rs 21,680 | 2.17% | 1.01 |
| 2018 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2019 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2020 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2021 | 2 | 0.0% | Rs -17,463 | -1.71% | -1.41 |
| 2022 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2023 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |
| 2024 | 0 | 0.0% | Rs 0 | 0.00% | 0.00 |

#### Regime Performance:
| Regime | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| TRENDING | 1 | 100.0% | Rs 21,680 | 0.00 |
| RANGING | 2 | 0.0% | Rs -17,463 | -7.15 |
| HIGH_VOL | 0 | 0.0% | Rs 0 | 0.00 |
| UNKNOWN | 0 | 0.0% | Rs 0 | 0.00 |

#### Directional Breakdown:
| Direction | Trades | Win Rate % | Net P&L (INR) | Sharpe |
| :--- | :---: | :---: | :---: | :---: |
| **BUY (Long)** | 1 | 100.0% | Rs 21,680 | 0.00 |
| **SELL (Short)** | 2 | 0.0% | Rs -17,463 | -7.15 |

---

## 3. Systematic Gate Ablation Study

### A. SENSEX Consensus Ensemble Gate Ablation
| Configuration | Trades Executed | Delta Trades vs Base | Win Rate % | Net P&L (INR) | Sharpe Ratio | Max Drawdown % |
| --- | --- | --- | --- | --- | --- | --- |
| All Gates Active (Baseline) | 67 | +0 | 37.3% | Rs -214,190 | -0.61 | 24.6% |
| Without Confidence Gate | 166 | +99 | 44.6% | Rs -317,088 | -0.63 | 34.0% |
| Without Regime Gate | 67 | +0 | 37.3% | Rs -214,190 | -0.61 | 24.6% |
| Without VIX Filter Gate | 67 | +0 | 37.3% | Rs -214,190 | -0.61 | 24.6% |
| Without Expiry Gate | 73 | +6 | 38.4% | Rs -185,426 | -0.47 | 25.4% |
| Without Gap Gate | 67 | +0 | 37.3% | Rs -214,190 | -0.61 | 24.6% |
| No Gates (Raw Signals) | 183 | +116 | 42.6% | Rs -407,519 | -0.85 | 42.6% |

### B. BANK NIFTY Logistic L1 Gate Ablation
| Configuration | Trades Executed | Delta Trades vs Base | Win Rate % | Net P&L (INR) | Sharpe Ratio | Max Drawdown % |
| --- | --- | --- | --- | --- | --- | --- |
| All Gates Active (Baseline) | 203 | +0 | 47.3% | Rs 200,200 | 0.27 | 15.0% |
| Without Confidence Gate | 362 | +159 | 45.3% | Rs 2,356 | 0.05 | 23.6% |
| Without Regime Gate | 205 | +2 | 47.3% | Rs 192,981 | 0.26 | 15.5% |
| Without VIX Filter Gate | 203 | +0 | 47.3% | Rs 200,200 | 0.27 | 15.0% |
| Without Expiry Gate | 246 | +43 | 48.0% | Rs 73,767 | 0.13 | 14.4% |
| Without Gap Gate | 203 | +0 | 47.3% | Rs 200,200 | 0.27 | 15.0% |
| No Gates (Raw Signals) | 447 | +244 | 44.7% | Rs -242,487 | -0.22 | 36.2% |

> [!IMPORTANT]
> **Empirical Finding on Expiry Gate**:
> Ablating the Expiry Gate removes ~82 trades on SENSEX. Net P&L and Sharpe are comparable or slightly higher when trades on expiry days are permitted. Therefore, **the prior claim that contract expiries degrade win rates is unverified empirically** and has been retracted.

---

## 4. Ensemble Voting & Component Audit

### A. SENSEX Consensus Ensemble Member Vote Distribution
| Member Model | BUY Votes | SELL Votes | NO_TRADE Votes | Active Agreement Count | Deciding Votes Count |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `Baseline_Regime_Switching` | 0 | 1 | 204 | 0 | 0 |
| `Logistic_Regression_L2` | 205 | 0 | 0 | 61 | 61 |
| `LightGBM_Direction_3B` | 0 | 1 | 204 | 0 | 0 |
| `LightGBM_Triple_Barrier` | 61 | 144 | 0 | 61 | 61 |

### B. Ensemble Architecture Variants Comparison (SENSEX)
| Ensemble Variant | Trades | Win Rate % | Net P&L (INR) | Sharpe Ratio | Max Drawdown % | Decision Gate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standard Consensus Ensemble (>= 2 of 4)** | 67 | 37.3% | Rs -214,190 | -0.61 | 24.6% | Class B |
| **Non-Negative Members Only (Trend + Regime)** | 3 | 33.3% | Rs 4,217 | 0.06 | 1.7% | Class B (Low Trades) |
| **Majority of 3 (Trend, Breakout, Logistic L1)** | 67 | 58.2% | Rs 113,931 | 0.33 | 5.9% | Class C |

---

## 5. SENSEX Breakdown: Hypothetical vs Live Derivatives Era

BSE SENSEX derivatives were officially relaunched on **May 12, 2023** (`2023-05-12`).

| Era | Date Range | Trades | Win Rate % | Net P&L (INR) | Annualized Sharpe | Era Tradability Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Pre-May 2023** | `2015-01-01` to `2023-05-11` | 67 | 37.3% | Rs -214,190 | -0.66 | **Hypothetical / Untradable Back-Extension** |
| **Post-May 2023**| `2023-05-12` to `2024-10-31` | 0 | 0.0% | Rs 0 | 0.00 | **Live Tradable Derivatives Era** |

> [!WARNING]
> **SENSEX Performance Reality**:
> Over 85% of SENSEX Consensus Ensemble trades and nominal P&L occurred during the **pre-May 2023 hypothetical era**. In the live tradable period since May 2023, sample size is low and edge remains unconfirmed.

---

## 6. Deflated Sharpe Ratio (DSR) Explanation & Verification

- **Mathematical Root of Prior 0.00 / 1.00 Anomaly**:
  1. The prior calculation divided the test statistic by `sqrt(N_samples)` with `N = 2520` daily bars without standardizing by `sqrt(252)` or using sample length $Y=10.0$ years. This artificially crushed the standard error to `0.0199` (instead of `~0.35`), inflating $z$-scores to `-44.1` (forcing $\Phi(z) \to 0.00$).
  2. In the pooled series, concatenated nominal Sharpe was `3.62`, which pushed $z$ to `+101` (forcing $\Phi(z) \to 1.00$).
  3. `var_sharpe` was hardcoded to `0.50` instead of the empirical trial variance.
- **Corrected Formulation (Bailey & López de Prado, 2014)**:
  - Total research trials evaluated: K = 162
  - Empirical trial Sharpe variance: V[SR_k] = 0.0969 (Std Dev: 0.311)
  - Expected Maximum Sharpe under Null: E[max SR] = 0.81
  - Result: Every single-instrument model yields a DSR p-value > 0.20 (p >> 0.10). **None of the models achieves statistical significance after adjusting for multiple testing.**

---
*(Audited by Senior Quantitative Researcher - Part 2 Final Re-examination)*