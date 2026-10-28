"""Tests for recorder resilience, REST fallback watchdog, and strike re-centering."""

import time
from datetime import datetime
from unittest.mock import MagicMock
import pytest

from recorder.engine import LiveRecorderEngine
from recorder.options_monitor import OptionsMonitor
from recorder.storage import LiveStorageManager


def test_rest_fallback_on_websocket_stall(tmp_path):
    """Demonstrate REST fallback triggers and inserts ticks when WS stalls for >10s."""
    storage = LiveStorageManager(base_dir=str(tmp_path / "live"))
    engine = LiveRecorderEngine(storage_mgr=storage)
    engine.client = MagicMock()

    # Mock REST getMarketData responses
    engine.client.getMarketData.side_effect = [
        # Spot LTP
        {
            "status": True,
            "data": {
                "fetched": [
                    {"symbolToken": "99926000", "ltp": 22680.50},
                    {"symbolToken": "99926009", "ltp": 54200.10},
                    {"symbolToken": "99919000", "ltp": 73400.00},
                ]
            },
        },
        # Futures Quote
        {
            "status": True,
            "data": {
                "fetched": [
                    {
                        "symbolToken": "48704",
                        "ltp": 22730.00,
                        "tradeVolume": 5000000,
                        "opnInterest": 11000000,
                    },
                    {
                        "symbolToken": "61471",
                        "ltp": 22840.00,
                        "tradeVolume": 4500000,
                        "opnInterest": 11200000,
                    },
                ]
            },
        },
    ]

    # Initially WS is active
    engine.active_source = "websocket"
    engine.last_tick_time = time.time() - 15.0  # Stall for 15 seconds

    # Trigger REST fallback poll
    engine._poll_rest_fallback()

    assert engine.active_source == "rest"
    assert engine.latest_prices["NIFTY"] == 22680.50
    assert engine.latest_prices["NIFTY_FUT_NEAR"] == 22730.00

    # Verify DuckDB recorded ticks with source='rest'
    conn = storage.get_connection()
    try:
        ticks_df = conn.execute("SELECT * FROM live_ticks").fetchdf()
        assert not ticks_df.empty
        assert (ticks_df["source"] == "rest").all()
        assert set(ticks_df["symbol"]).issuperset({"NIFTY", "BANKNIFTY", "SENSEX", "NIFTY_FUT_NEAR"})
    finally:
        conn.close()


def test_strike_recentering_on_spot_movement():
    """Test ATM strike detection and window recentering when spot moves across strikes."""
    monitor = OptionsMonitor(client=MagicMock())

    # Initial spot 22,610 -> ATM strike center is 22,600
    strikes_1 = monitor.get_atm_strikes("NIFTY", 22610.0)
    assert len(strikes_1) == 21
    assert monitor.center_strikes["NIFTY"] == 22600.0
    assert strikes_1[0] == 22100.0
    assert strikes_1[10] == 22600.0
    assert strikes_1[-1] == 23100.0
    assert not monitor.should_recenter("NIFTY", 22625.0)  # within 50 pts

    # Spot rallies by 160 points to 22,770 -> recenter triggered (>= 50 pt threshold)
    assert monitor.should_recenter("NIFTY", 22770.0)
    strikes_2 = monitor.get_atm_strikes("NIFTY", 22770.0)
    assert len(strikes_2) == 21
    assert monitor.center_strikes["NIFTY"] == 22750.0 or monitor.center_strikes["NIFTY"] == 22800.0

    # Verify window recentered
    dropped_strikes = set(strikes_1) - set(strikes_2)
    new_strikes = set(strikes_2) - set(strikes_1)
    assert len(dropped_strikes) > 0
    assert len(new_strikes) > 0
    assert min(strikes_2) > min(strikes_1)


def test_banknifty_and_sensex_strike_steps():
    """Verify strike rounding steps: 100 for BANKNIFTY, 100 for SENSEX."""
    monitor = OptionsMonitor(client=MagicMock())

    # BANKNIFTY (step=100)
    bn_strikes = monitor.get_atm_strikes("BANKNIFTY", 54148.0)
    assert monitor.center_strikes["BANKNIFTY"] == 54100.0
    assert bn_strikes[10] == 54100.0
    assert bn_strikes[11] - bn_strikes[10] == 100.0

    # SENSEX (step=100)
    sensex_strikes = monitor.get_atm_strikes("SENSEX", 73380.0)
    assert monitor.center_strikes["SENSEX"] == 73400.0
    assert sensex_strikes[10] == 73400.0
    assert sensex_strikes[11] - sensex_strikes[10] == 100.0
