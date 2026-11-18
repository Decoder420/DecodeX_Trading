"""Tests for DecodeX Trading Decoupled Architecture (engine.py, app.py, and StateStore)."""

import pytest
import time
from pathlib import Path
from data.state_store import StateStore
from engine import DecodeXEngine
from dashboard.tradingview_streamlit import render_mtf_tradingview_html


def test_state_store_atomic_write_and_read(tmp_path):
    """Verify that StateStore writes and reads state payload without data loss."""
    test_file = tmp_path / "test_decodex_state.json"
    store = StateStore(file_path=test_file)

    payload = {
        "spot_price": 25044.65,
        "instrument": "NIFTY",
        "confluence": {"signal": "BULLISH ENTRY", "score": 4.8},
    }
    success = store.set_state(payload)
    assert success is True

    loaded = store.get_state()
    assert loaded is not None
    assert loaded["spot_price"] == 25044.65
    assert loaded["instrument"] == "NIFTY"
    assert loaded["confluence"]["signal"] == "BULLISH ENTRY"
    assert "updated_at" in loaded
    assert store.get_age_seconds() < 2.0


def test_engine_initialization_and_confluence():
    """Verify DecodeXEngine computes MTF indicators, L2 depth, and writes state."""
    engine = DecodeXEngine(instrument="NIFTY", active_expiry="17NOV2026")
    engine._compute_initial_indicators()

    # Verify MTF bars
    assert len(engine.bars_15m) > 0
    assert len(engine.bars_3m) > 0

    # Verify latest indicators
    assert engine.last_vwap > 0
    assert engine.last_supertrend > 0
    assert engine.last_ema9 > 0
    assert engine.last_ema21 > 0
    assert engine.last_ema50 > 0
    assert 0 <= engine.last_rsi <= 100

    # Verify 5-level depth & OBI
    depth = engine.latest_depth_payload
    assert len(depth["bids"]) == 5
    assert len(depth["asks"]) == 5
    assert -1.0 <= depth["order_book_imbalance"] <= 1.0
    assert depth["micro_price"] > 0
    assert depth["spread"] >= 0

    # Verify Options Chain Grid
    opts = engine.latest_options_payload
    assert len(opts["rows"]) == 5
    assert "triad_coi_delta" in opts
    assert opts["pcr_oi"] > 0

    # Verify Consolidated State
    from data.state_store import state_store
    state = state_store.get_state()
    assert state is not None
    assert state["instrument"] == "NIFTY"
    assert "mtf_15m" in state
    assert "mtf_3m" in state
    assert "confluence" in state
    assert "depth" in state
    assert "options_chain" in state
    assert "news" in state


def test_tradingview_html_generator():
    """Verify that TradingView HTML renders inlined bundle with candles and indicators."""
    candles = [
        {"time": 1700000000 + i * 900, "open": 25000 + i, "high": 25010 + i, "low": 24990 + i, "close": 25005 + i}
        for i in range(10)
    ]
    vwap = [{"time": c["time"], "value": c["close"] - 2} for c in candles]
    st = [{"time": c["time"], "value": c["close"] - 10} for c in candles]

    html = render_mtf_tradingview_html(
        candles_15m=candles,
        vwap_data=vwap,
        supertrend_data=st,
        candles_3m=candles,
        ema9_data=vwap,
        ema21_data=vwap,
        ema50_data=vwap,
        rsi_data=[{"time": c["time"], "value": 55.0} for c in candles],
        height=500,
        active_frame="both",
    )
    assert "LightweightCharts" in html
    assert "15M STRUCTURAL FRAME" in html
    assert "3M EXECUTION FRAME" in html
    assert len(html) > 50_000

