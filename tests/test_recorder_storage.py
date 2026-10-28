"""Unit tests for isolated daily DuckDB storage layer and Parquet consolidation."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
import duckdb
import pytest

from recorder.storage import LiveStorageManager


@pytest.fixture
def temp_live_storage():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_live_storage_"))
    mgr = LiveStorageManager(base_dir=temp_dir)
    yield mgr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_isolated_db_creation_and_insertion(temp_live_storage: LiveStorageManager) -> None:
    test_date = date(2026, 10, 26)
    db_path = temp_live_storage.get_db_path(test_date)
    assert not db_path.exists()

    # 1. Insert ticks
    tick_rows = [
        {
            "exchange_timestamp": datetime.now(),
            "received_at": datetime.now(),
            "token": "99926000",
            "symbol": "NIFTY",
            "instrument_type": "AMXIDX",
            "ltp": 24000.50,
            "ltq": 50,
            "volume": 1250000,
            "source": "websocket",
        }
    ]
    count = temp_live_storage.insert_ticks(tick_rows, test_date)
    assert count == 1
    assert db_path.exists()

    # 2. Insert depth
    depth_rows = [
        {
            "timestamp": datetime.now(),
            "token": "99926000",
            "symbol": "NIFTY",
            "best_bid": 24000.40,
            "best_ask": 24000.60,
            "depth_imbalance": 0.15,
            "spread": 0.20,
            "source": "websocket",
        }
    ]
    d_count = temp_live_storage.insert_depth(depth_rows, test_date)
    assert d_count == 1

    # 3. Insert futures bars
    fbar_rows = [
        {
            "timestamp": datetime.now(),
            "symbol": "NIFTY_FUT",
            "token": "48704",
            "contract_expiry": test_date,
            "open": 24050.0,
            "high": 24060.0,
            "low": 24040.0,
            "close": 24055.0,
            "volume": 5000,
            "oi": 12000000,
            "vwap": 24052.5,
            "source": "websocket",
        }
    ]
    fb_count = temp_live_storage.insert_futures_bars(fbar_rows, test_date)
    assert fb_count == 1

    # 4. Insert health
    health_row = {
        "timestamp": datetime.now(),
        "status": "RUNNING",
        "uptime_seconds": 60.0,
        "ticks_received": 150,
        "tick_rate_per_sec": 2.5,
        "active_source": "websocket",
        "disconnect_count": 0,
        "last_tick_age_seconds": 0.2,
        "memory_mb": 45.0,
    }
    temp_live_storage.insert_health(health_row, test_date)

    # Verify tables via direct DuckDB connection
    conn = duckdb.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM live_ticks").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM live_depth").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM futures_bars").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM recorder_health").fetchone()[0] == 1
    conn.close()


def test_parquet_consolidation_and_retention(temp_live_storage: LiveStorageManager) -> None:
    test_date = date(2026, 10, 26)
    tick_rows = [
        {
            "exchange_timestamp": datetime.now(),
            "received_at": datetime.now(),
            "token": "99926000",
            "symbol": "NIFTY",
            "instrument_type": "AMXIDX",
            "ltp": 24000.0,
            "ltq": 25,
            "volume": 1000,
            "source": "websocket",
        }
    ]
    temp_live_storage.insert_ticks(tick_rows, test_date)

    # Run consolidation
    res = temp_live_storage.consolidate_day_to_parquet(test_date)
    assert res.get("live_ticks") == 1

    pq_path = temp_live_storage.consolidated_dir / "date=2026-10-26" / "live_ticks.parquet"
    assert pq_path.exists()

    # Verify disk usage report
    usage = temp_live_storage.get_disk_usage()
    assert usage["daily_duckdb_files_count"] == 1
    assert usage["consolidated_parquet_files_count"] >= 1
    assert usage["raw_duckdb_retention_days"] == 14
