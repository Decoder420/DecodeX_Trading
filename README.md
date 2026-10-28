# Quantitative Research Platform (Parts 1 & 2 of 3)

A statistical research and decision-support platform designed for generating `BUY` / `SELL` / `NO-TRADE` signals on benchmark Indian market indices: **NIFTY 50**, **BANK NIFTY**, and **BSE SENSEX** (with index futures as the tradable proxy).

> [!CAUTION]
> **Regulatory & Risk Disclaimer**: This platform is strictly for personal quantitative research and statistical decision support. It contains **no live order execution** and does **never claim or imply guaranteed profitability**. Market participation involves substantial financial risk.
>
> **Index Futures Proxy Approximation**: Cash index series are utilized as the tradable proxy for index futures. This approximation assumes zero spot-futures basis and no roll gaps between contract months. BSE SENSEX derivatives prior to their May 2023 relaunch are hypothetical backtest constructs.

---

## Architecture Overview

### Part 1: Data & Feature Engineering
- **Market Session**: NSE & BSE, 09:15 to 15:30 IST (`Asia/Kolkata` timezone normalized throughout).
- **Timeframes**: Configurable (`1d` primary, `15m` secondary).
- **Zero Hardcoding**: All lot sizes, expiry regimes, session hours, holiday lists, provider tokens, and transaction costs are isolated in `config/config.yaml`.
- **Dynamic Scrip Master**: Angel One tokens are resolved dynamically at runtime from the official scrip master JSON and cached locally (`data/cache/`).
- **Resilient Fallback**: If Angel One credentials are missing or unauthenticated, the system logs a descriptive message and falls back to Yahoo Finance daily data.
- **Incremental Storage**: DuckDB storage (`data/market_data.duckdb`) storing one table per instrument with deduplicated incremental upserts.
- **Lookahead Bias Prevention**: Mathematically verified via pytest. GARCH(1,1) is fitted on rolling windows only; HMM regime labels are computed using filtered forward probabilities and mapped to regimes by fitted variance/return (never by arbitrary state index).
- **Volume Awareness**: Spot index series do not carry traded volume; intraday VWAP is automatically skipped for index series with explicit logging and only computed when valid volume is present.

### Part 2: Statistical Models, Walk-Forward Backtesting & Execution Engine
- **Standardized Output Interface**: Every model emits a `SignalPacket` with direction (`BUY` / `SELL` / `NO_TRADE`), confidence, suggested entry ($Open_{t+1}$), ATR-based stop-loss, ATR-based profit target, and time horizon.
- **Model Suite**:
  1. *Rule-Based Baselines*: Trend Following (EMA/ADX), Mean Reversion (Bollinger %B & Z-Score), Breakout (Donchian Channel), and Regime Switching (adaptive rule selection by market state).
  2. *Regularized Linear Models*: Logistic Regression L1 (Lasso) and L2 (Ridge) with chronological calibration and bounded scaling.
  3. *Gradient Boosted Decision Trees*: LightGBM Direction (Model 3A) and LightGBM Triple Barrier (Model 3B with exact 2.0 ATR target, 1.5 ATR stop, 10 bar limit) with native Tree SHAP explainability.
  4. *Consensus Voting Ensemble*: Fires only when $\ge 2$ independent models agree on direction with zero opposing dissent.
- **Walk-Forward Validation**: 10 expanding chronological folds (2015–2024), 10-bar purging, 5-bar embargoing.
- **Sealed Out-Of-Sample Holdout**: Last 2 years (`2024-11-01` to `2026-10-23`) locked by `HoldoutManager` with cryptographic tampering checks.
- **Realistic Execution**:
  - Next-open fills (no same-bar execution).
  - Open gaps beyond stop or target filled at actual Open price.
  - Conservative stop-loss priority on dual barrier breaches.
  - Effective-dated statutory transaction costs: STT (0.02% sell side), GST (18%), stamp duty (0.002% buy side), exchange turnover charges, SEBI fee, and Rs 20 brokerage.
  - Base slippage (1.5 bps) vs stress slippage (5.0 bps).
- **Risk Management & Gating**:
  - Volatility-targeted position sizing (15% portfolio vol), fixed fractional risk (1.0% per trade), max daily loss limit (2.5%).
  - Portfolio Drawdown Kill Switch (15%) with a **20-day pause & restart rule**.
  - Multi-gate filter: Data Gap blackout, Confidence gate, Regime gate, VIX percentile gate, and Expiry Day A/B filter.

---

## Directory Layout

```text
├── config/
│   ├── config.yaml               # Master YAML configuration & effective-dated cost schedules
│   ├── holidays.yaml             # NSE/BSE official trading holidays calendar (2010–2026)
│   └── loader.py                 # Configuration manager & time-varying calendar logic
├── data/
│   ├── base_provider.py          # Abstract BaseDataProvider interface
│   ├── yfinance_provider.py      # Yahoo Finance provider (daily + 15m fallback)
│   ├── angel_provider.py         # Angel One SmartAPI provider (rate limits, TOTP, chunking)
│   ├── upstox_provider.py        # Upstox V2 provider adapter stub
│   ├── cleaner.py                # Data validation, outlier flagging, gap auditing
│   ├── storage.py                # DuckDB persistence with incremental upserts
│   ├── quality_report.py         # Tabular data quality report generator
│   ├── provider_factory.py       # Orchestrator with fallback & date range expansion
│   ├── market_data.duckdb        # Ingested daily data (~4,130 bars per instrument)
│   └── experiments/              # JSONL experiment run tracker
├── features/
│   ├── trend.py                  # EMA 9/21/50/200, ADX, Supertrend, VWAP, HH/HL structure
│   ├── momentum.py               # RSI, MACD, ROC, Stochastic %K/%D, Return Z-score
│   ├── volatility.py             # ATR, Bollinger width, Realized Vol, GARCH(1,1), India VIX rank
│   ├── mean_reversion.py         # Distance from MA in ATR units, rolling Hurst exponent, ADF p-value
│   ├── calendar.py               # Day of week, time-varying expiry flags, gap %, month-end
│   ├── regime.py                 # HMM (filtered forward probs) & rolling stats regime classification
│   └── pipeline.py               # Orchestrator computing all feature sets
├── models/
│   ├── base.py                   # BaseSignalModel abstract class & SignalPacket dataclass
│   ├── calibration.py            # Chronological calibration slice, Platt & Isotonic calibrators, ECE
│   ├── baselines.py              # Trend, Mean Reversion, Breakout, Regime Switching models
│   ├── linear.py                 # Regularized Logistic Regression (L1/L2)
│   ├── tree_models.py            # LightGBM Direction & Triple Barrier models with SHAP
│   ├── ensemble.py               # Consensus Voting Ensemble
│   ├── labels.py                 # Forward returns & Triple Barrier labeling
│   └── artifacts/                # Versioned model artifacts & audit manifests
├── backtest/
│   ├── engine.py                 # Event-driven execution engine (next-open fills, gap fills)
│   ├── costs.py                  # Effective-dated statutory cost calculator & slippage
│   ├── holdout.py                # 2-year out-of-sample holdout guard & access audit
│   ├── position_sizing.py        # Volatility targeting, fractional risk, drawdown kill switch
│   ├── walk_forward.py           # Expanding walk-forward backtest runner with purging & embargoing
│   ├── metrics.py                # CAGR, Sharpe, Sortino, MaxDD, Win Rate, Expectancy, Weak sample flag
│   ├── robustness.py             # Deflated Sharpe Ratio, Bootstrap CI, Monte Carlo noise benchmark
│   ├── tracker.py                # Experiment logger and versioned artifact repository
│   └── reporter.py               # Markdown report generator with proxy disclaimers
├── signals/
│   ├── gates.py                  # TradeGatekeeper & multi-gate filtering
│   └── ...                       # Reserved for Part 3 (Service & Endpoints)
├── dashboard/                    # Reserved for Part 3 (Streamlit App)
├── tests/
│   ├── test_backtest_engine.py   # No same-bar fills, open gap fills, dual breach priority, holdout
│   ├── test_calendar_rules.py    # Time-varying lot sizes & expiry holiday shifts
│   ├── test_costs.py             # Hand-verified statutory cost math for 2012, 2018, 2025
│   ├── test_data_cleaning.py     # Duplicates, invalid prices, outlier flags, gaps
│   ├── test_lookahead.py         # Anti-leakage tests: full vs truncated dataset equivalence
│   ├── test_providers.py         # Fallback, rate limits, storage upsert
│   ├── test_signal_models.py     # Calibration slice separation, Model 3B exact exits, ensemble
│   └── test_walk_forward.py      # Expanding folds, 10-bar purging, gap date trading exclusion
├── scripts/
│   ├── run_pipeline.py           # Data ingestion & feature matrix generator
│   └── run_model_comparison.py   # Master walk-forward model evaluation & Decision Gate runner
├── reports/                      # Detailed model evaluation markdown reports
├── .env.example                  # Template for credentials
├── requirements.txt              # Pinned Python dependencies
└── PROJECT_STATE.md              # Living architecture state, Decision Gate results, and handoffs
```

---

## Setup & Quickstart

### 1. Environment Preparation
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Data Pipeline (Part 1)
```bash
# Ingest historical data, engineer features, and display Data Quality Report
python scripts/run_pipeline.py --symbols NIFTY BANKNIFTY SENSEX --days 365
```

### 3. Run Walk-Forward Model Comparison (Part 2)
```bash
# Evaluates all 9 models across NIFTY, BANKNIFTY, SENSEX, and POOLED with 10 expanding folds
python scripts/run_model_comparison.py
```

Reports and summary tables are automatically generated in `reports/MODEL_COMPARISON_SUMMARY.md` and `reports/report_<INSTRUMENT>_<MODEL>.md`.

### 4. Run Test Suite
```bash
# Run all 38 tests (anti-leakage proofs, cost math, execution logic, model gates, ensemble re-fitting)
.venv/bin/pytest -v
```

---

## Decision Gate Summary (Part 2 - Audited)

> [!CAUTION]
> **Core Quantitative Finding**: **NO MODEL IS VALIDATED.**
> All tested strategies fail multiple institutional robustness criteria (e.g., bootstrap difference CI spans zero, Deflated Sharpe Ratio p-value >= 0.10, or lack of consistency).
> All candidates are strictly classified as **"marginal, unconfirmed"** (Class B or Class C). Live trading is strictly discouraged.

| Instrument | Model | Out-of-Sample Trades | Win Rate % | Net P&L (INR) | Sharpe (1.5 bps) | Sharpe (5.0 bps) | B&H Sharpe | Exposure % | Excess vs Exp-B&H | DSR p-value | Diff CI Excludes 0 | Decision Gate Classification |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **NIFTY** | Baseline_Trend_EMA_ADX | 3 | 66.7% | Rs 31,826 | 0.36 | 0.35 | 0.63 | 0.4% | +0.3% | 0.936 | No | **Class B (Weak sample)** |
| **BANKNIFTY** | Logistic_Regression_L2 | 217 | 47.5% | Rs 203,696 | 0.27 | 0.17 | 0.59 | 42.2% | -2.8% | 0.964 | No | **Class B (Marginal Edge)** |
| **BANKNIFTY** | Logistic_Regression_L1 | 203 | 47.3% | Rs 200,200 | 0.27 | 0.17 | 0.59 | 39.4% | -2.5% | 0.965 | No | **Class B (Marginal Edge)** |
| **SENSEX** | Baseline_Trend_EMA_ADX | 3 | 33.3% | Rs 4,217 | 0.06 | 0.04 | 0.61 | 0.8% | -0.0% | 0.993 | No | **Class B (Weak sample)** |
| **SENSEX** | Baseline_Regime_Switching | 3 | 33.3% | Rs 4,217 | 0.06 | 0.04 | 0.61 | 0.8% | -0.0% | 0.993 | No | **Class B (Weak sample)** |
| **BANKNIFTY** | Baseline_Trend_EMA_ADX | 5 | 40.0% | Rs 1,436 | 0.02 | 0.01 | 0.59 | 1.4% | -0.1% | 0.995 | No | **Class B (Weak sample)** |
| *All Instruments* | LightGBM Triple Barrier | 132–160 | 34–40% | Negative | < -0.17 | < -0.29 | ~0.60 | 23–29% | Negative | 1.000 | No | **Class C (No Edge After Costs)** |
| *All Instruments* | Consensus Ensemble | 42–67 | 32–37% | Negative | < -0.56 | < -0.51 | ~0.60 | 7–13% | Negative | 1.000 | No | **Class C (No Edge After Costs)** |
| *All Instruments* | Breakout (Donchian) | 82–97 | 45–48% | Negative | < -0.01 | < -0.11 | ~0.60 | 23–31% | Negative | ~0.997 | No | **Class C (No Edge After Costs)** |
| *All Instruments* | Mean Reversion | 0 | 0.0% | Rs 0 | 0.00 | 0.00 | ~0.60 | 0.0% | 0.0% | 0.996 | No | **Class C (Untested / 0 Trades)** |

---

## Next Steps (Part 3)
- Build real-time daily signal generation service in `signals/` for decision support and risk monitoring.
- Deploy FastAPI endpoints for signal queries and risk diagnostics.
- Build interactive Streamlit decision-support dashboard in `dashboard/`.
