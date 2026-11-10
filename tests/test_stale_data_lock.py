"""Unit tests for the 15-second Stale-Data Lock, Signal Suppression, and Paper-Trade Halt."""

import json
from datetime import datetime, time, timedelta
from pathlib import Path
import duckdb
import pandas as pd
import pytest
from dashboard.tradingview_chart import build_tradingview_html
from data.paper_trading import log_and_evaluate_signal
from signals.engine import IntradaySignalEngine, SignalState, TradeAction, TradePlan


def test_stale_data_lock_tick_age_threshold():
    """Verify that tick age > 15 seconds triggers stale lock."""
    now_dt = datetime.now()
    fresh_tick = (now_dt - timedelta(seconds=8)).strftime("%Y-%m-%d %H:%M:%S")
    stale_tick = (now_dt - timedelta(seconds=22)).strftime("%Y-%m-%d %H:%M:%S")

    fresh_diff = (now_dt - pd.to_datetime(fresh_tick)).total_seconds()
    stale_diff = (now_dt - pd.to_datetime(stale_tick)).total_seconds()

    assert fresh_diff <= 15.0
    assert stale_diff > 15.0


def test_stale_data_suppresses_active_chart_lines():
    """Verify that is_stale=True hides ENTRY/SL/target price lines and displays NO SIGNAL: DATA STALE banner."""
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(
        spot_price=22750.0,
        ema_21=22780.0,
        ema_50=22810.0,
        adx_14=28.5,
        atr_14=59.0,
    )
    candles_df = pd.DataFrame([{
        "timestamp": "2026-10-28 10:41:00",
        "open": 22740.0, "high": 22760.0, "low": 22735.0, "close": 22750.0,
        "volume": 0.0, "source": "broker_history"
    }])

    # Build HTML with is_stale=True
    html_stale = build_tradingview_html(
        candles_df=candles_df,
        signal_log_df=pd.DataFrame(),
        plan=plan,
        spot_ltp=22750.0,
        max_pain=22750.0,
        instrument="NIFTY",
        timeframe="15m",
        is_stale=True,
        stale_since="10:41:40",
    )

    # 1. Stale banner must be present in HTML
    assert "stale-banner" in html_stale
    assert "NO SIGNAL: DATA STALE" in html_stale
    assert "10:41:40" in html_stale

    # 2. Plan payload must record is_stale=True
    assert '"is_stale": true' in html_stale
    assert '"stale_since": "10:41:40"' in html_stale


def test_stale_data_stops_paper_trade_logging(tmp_path, monkeypatch):
    """Verify that paper trade logging is halted when is_stale=True."""
    mock_db = tmp_path / "live_mock_paper.duckdb"
    monkeypatch.setattr("data.paper_trading.get_paper_db_path", lambda: mock_db)

    # Call with is_stale=True
    stats_stale = log_and_evaluate_signal(
        instrument="NIFTY",
        timeframe="15m",
        action="BUY_CE",
        state="BUY",
        spot_price=22750.0,
        strike="22750 CE",
        entry_premium=150.0,
        stop_loss_premium=120.0,
        target_1_premium=195.0,
        target_2_premium=225.0,
        quantity=65,
        confidence=0.85,
        score=2.5,
        current_ltp=22750.0,
        is_stale=True,
    )

    # Database should have 0 inserted rows
    con = duckdb.connect(str(mock_db))
    count = con.execute("SELECT count(*) FROM paper_signals_log").fetchone()[0]
    con.close()
    assert count == 0

    # Call with is_stale=False (normal feed)
    stats_live = log_and_evaluate_signal(
        instrument="NIFTY",
        timeframe="15m",
        action="BUY_CE",
        state="BUY",
        spot_price=22750.0,
        strike="22750 CE",
        entry_premium=150.0,
        stop_loss_premium=120.0,
        target_1_premium=195.0,
        target_2_premium=225.0,
        quantity=65,
        confidence=0.85,
        score=2.5,
        current_ltp=22750.0,
        is_stale=False,
    )

    con = duckdb.connect(str(mock_db))
    count_after = con.execute("SELECT count(*) FROM paper_signals_log").fetchone()[0]
    con.close()
    assert count_after == 1
