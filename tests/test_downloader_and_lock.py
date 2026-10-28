"""Tests for Stage 2 Historical Downloader, mutual exclusion lock, and post-market guardrails."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import pytest
import pytz

from data.historical_downloader import DownloaderLock, Stage2HistoricalDownloader


def test_downloader_lock_acquire_and_release(tmp_path: Path):
    """Verify DownloaderLock acquires and releases cleanly."""
    lock_file = tmp_path / "test_downloader.lock"
    pid_file = tmp_path / "test_recorder.pid"

    lock = DownloaderLock(lock_path=lock_file, pid_path=pid_file)
    assert not lock_file.exists()

    with lock:
        assert lock_file.exists()
        lock_data = json.loads(lock_file.read_text())
        assert lock_data["pid"] == os.getpid()
        assert lock.acquired

    assert not lock_file.exists()
    assert not lock.acquired


def test_downloader_lock_blocks_when_recorder_running(tmp_path: Path):
    """Verify DownloaderLock blocks execution if recorder process is active."""
    lock_file = tmp_path / "test_downloader.lock"
    pid_file = tmp_path / "test_recorder.pid"

    # Simulate active recorder with our own PID
    pid_file.write_text(str(os.getpid()))

    lock = DownloaderLock(lock_path=lock_file, pid_path=pid_file)
    with pytest.raises(RuntimeError) as exc_info:
        lock.acquire()

    assert "MUTUAL EXCLUSION VIOLATION" in str(exc_info.value)
    assert not lock_file.exists()


def test_downloader_post_market_timing_enforcement():
    """Verify Stage 2 restricts today's session to >= 15:45 IST while allowing past dates."""
    downloader = Stage2HistoricalDownloader()
    tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz)
    today = now_ist.date()

    # Past completed date must be eligible
    past_date = today - timedelta(days=2)
    is_elig_past, reason_past = downloader.is_post_market(past_date)
    assert is_elig_past
    assert "Past completed" in reason_past

    # Future date must be blocked
    future_date = today + timedelta(days=2)
    is_elig_fut, reason_fut = downloader.is_post_market(future_date)
    assert not is_elig_fut
    assert "Future date" in reason_fut

    # Today's date check: if running before 15:45 IST, must be blocked
    cutoff = now_ist.replace(hour=15, minute=45, second=0, microsecond=0)
    is_elig_today, reason_today = downloader.is_post_market(today)
    if now_ist < cutoff:
        assert not is_elig_today
        assert "< 15:45:00 IST" in reason_today
    else:
        assert is_elig_today


def test_downloader_session_filtering_skips_holidays():
    """Verify session filtering removes non-trading days and recognized holidays."""
    downloader = Stage2HistoricalDownloader()

    # October 2026 week containing Dussehra (2026-10-20)
    start = date(2026, 10, 19)  # Monday (Trading Day)
    end = date(2026, 10, 23)    # Friday (Trading Day)

    sessions = downloader.filter_sessions(start, end)
    # Expected: 19th (Mon), 21st (Wed), 22nd (Thu), 23rd (Fri)
    # 20th (Tue) is Dussehra holiday -> MUST be filtered out
    assert date(2026, 10, 19) in sessions
    assert date(2026, 10, 20) not in sessions, "Dussehra holiday must be skipped!"
    assert date(2026, 10, 21) in sessions
    assert date(2026, 10, 22) in sessions
    assert date(2026, 10, 23) in sessions
    assert len(sessions) == 4


def test_secrets_scanner_detects_credentials(tmp_path: Path):
    """Verify secrets scanner catches synthetic API keys or tokens and passes clean files."""
    downloader = Stage2HistoricalDownloader()

    # Clean file
    clean_file = tmp_path / "clean_report.md"
    clean_file.write_text("# Clean Report\nTracking error is 0.00 pts. Pass.")

    # Leak file
    leak_file = tmp_path / "leak_report.md"
    leak_file.write_text("api_key = 'abcdef1234567890abcdef'\nAuthorization: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0")

    # Clean scan
    rep_clean = downloader._run_secrets_scan([clean_file])
    assert "CLEAN (ZERO LEAKS)" in rep_clean.read_text()

    # Leak scan
    rep_leak = downloader._run_secrets_scan([leak_file])
    assert "CRITICAL: LEAKS DETECTED" in rep_leak.read_text()
