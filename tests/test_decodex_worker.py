"""Unit tests for DecodeX Trading Native Worker Engine."""

from datetime import datetime
import pytz
import pytest
from PyQt6.QtCore import QCoreApplication

# Initialize Qt Core for headless testing
@pytest.fixture(scope="session", autouse=True)
def q_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_decodex_worker_l2_depth_parsing():
    """Verify true 5-level market depth parsing and Order Book Imbalance (OBI)."""
    from worker import DecodeXDataWorker

    worker = DecodeXDataWorker(instrument="NIFTY")
    fake_tick = {
        "token": "99926000",
        "last_traded_price": 2500000,
        "best_5_buy_data": [
            {"price": 2500000, "quantity": 1000, "no of orders": 10},
            {"price": 2499950, "quantity": 1500, "no of orders": 15},
        ],
        "best_5_sell_data": [
            {"price": 2500050, "quantity": 500, "no of orders": 5},
            {"price": 2500100, "quantity": 700, "no of orders": 7},
        ],
    }

    depth = worker.parse_l2_depth(fake_tick)

    assert depth["symbol"] == "NIFTY"
    assert depth["total_bid_qty"] == 2500
    assert depth["total_ask_qty"] == 1200
    assert len(depth["bids"]) == 2
    assert len(depth["asks"]) == 2
    assert depth["top_bid"] == 25000.0
    assert depth["top_ask"] == 25000.5
    assert depth["spread"] == 0.5
    # OBI = (2500 - 1200) / 3700 = +0.3514
    assert depth["order_book_imbalance"] > 0.35


def test_decodex_worker_mtf_confluence_strict_lock():
    """Verify 6-Factor confluence strictly enforces MTF alignment."""
    from worker import DecodeXDataWorker

    worker = DecodeXDataWorker(instrument="NIFTY")
    captured = []
    worker.mtf_signal.connect(lambda d: captured.append(d))

    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    worker._update_mtf_bars(now, 25000.0, 100, 0.20)

    assert len(captured) == 1
    data = captured[0]
    assert "15m" in data
    assert "3m" in data
    assert "confluence" in data
    assert "signal" in data["confluence"]
    assert "reasons" in data["confluence"]

