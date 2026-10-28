"""Tests for credentials isolation, order endpoint restrictions, and daily session reset safety."""

from __future__ import annotations

import io
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import pytz

from data.groww_auth import (
    GrowwAuthError,
    GrowwApprovalKeyOnlyError,
    GrowwAuthManager,
    IST,
)


def test_no_secrets_in_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify that credentials and secrets NEVER appear in log outputs."""
    dummy_key = "SECRET_GROWW_API_KEY_XY123456"
    dummy_secret = "SECRET_GROWW_APPROVAL_VAL_789"
    dummy_totp = "JBSWY3DPEHPK3PXP"
    dummy_token = "SECRET_BEARER_TOKEN_999999"

    monkeypatch.setenv("GROWW_API_KEY", dummy_key)
    monkeypatch.setenv("GROWW_API_SECRET", dummy_secret)
    monkeypatch.setenv("GROWW_TOTP_SECRET", dummy_totp)

    # Capture logs in memory
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    cache_file = tmp_path / "test_token.json"
    manager = GrowwAuthManager(token_cache_path=str(cache_file))

    # Mock GrowwAPI to return dummy token
    with patch("growwapi.GrowwAPI.get_access_token", return_value=dummy_token):
        token = manager.get_access_token()
        assert token == dummy_token

    # Flush handler
    handler.flush()
    log_content = log_stream.getvalue()
    logger.removeHandler(handler)

    # Assert none of the secret strings leaked into logs
    for secret in [dummy_key, dummy_secret, dummy_totp, dummy_token]:
        assert secret not in log_content, f"Security violation: Secret '{secret}' leaked into log output!"


def test_no_order_endpoints_referenced_in_code() -> None:
    """Verify that NO order placement, modification, or cancellation endpoints are referenced."""
    workspace = Path(__file__).resolve().parent.parent
    
    # Subdirectories to check
    check_dirs = ["data", "features", "models", "backtest", "signals", "dashboard", "scripts", "config"]
    
    forbidden_tokens = [
        "place_order",
        "modify_order",
        "cancel_order",
        "create_smart_order",
        "modify_smart_order",
        "cancel_smart_order",
        "/order/place",
        "/order/modify",
        "/order/cancel",
        "/smart-order",
        "place_gtt",
        "cancel_gtt",
    ]

    violations: list[str] = []

    for d in check_dirs:
        dir_path = workspace / d
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                # Search for whole identifier or explicit endpoint string
                if token in text:
                    violations.append(f"{py_file.relative_to(workspace)} contains forbidden order token '{token}'")

    assert not violations, f"Safety violation: Order execution code detected in read-only platform:\n" + "\n".join(violations)


def test_approval_only_raises_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensure automated token generation fails with clear error if only approval key exists."""
    monkeypatch.setenv("GROWW_API_KEY", "dummy_key")
    monkeypatch.setenv("GROWW_API_SECRET", "dummy_approval_secret")
    monkeypatch.delenv("GROWW_TOTP_SECRET", raising=False)

    dummy_env = tmp_path / "approval_only.env"
    dummy_env.write_text("GROWW_API_KEY=dummy_key\n%s\n" % "GROWW_API_SECRET=dummy_approval_secret")
    manager = GrowwAuthManager(env_file=str(dummy_env), token_cache_path=str(tmp_path / "cache.json"))
    
    with pytest.raises(GrowwApprovalKeyOnlyError) as exc_info:
        manager.get_access_token(allow_approval_fallback=False)

    msg = str(exc_info.value)
    assert "approval-based key" in msg.lower()
    assert "totp" in msg.lower()
    assert "6:00 am" in msg.lower()


def test_session_window_calculation() -> None:
    """Verify session window accurately bounds 6:00 AM IST resets."""
    # Case A: 05:30 IST on 2026-10-25 -> belongs to session starting 2026-10-24 06:00
    early_morning = datetime(2026, 10, 25, 5, 30, tzinfo=IST)
    start_a, end_a = GrowwAuthManager.get_session_window(early_morning)
    assert start_a == datetime(2026, 10, 24, 6, 0, tzinfo=IST)
    assert end_a == datetime(2026, 10, 25, 6, 0, tzinfo=IST)

    # Case B: 09:15 IST on 2026-10-25 -> belongs to session starting 2026-10-25 06:00
    trading_hours = datetime(2026, 10, 25, 9, 15, tzinfo=IST)
    start_b, end_b = GrowwAuthManager.get_session_window(trading_hours)
    assert start_b == datetime(2026, 10, 25, 6, 0, tzinfo=IST)
    assert end_b == datetime(2026, 10, 26, 6, 0, tzinfo=IST)


def test_cached_token_validity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify valid cached token is reused within the same 6 AM session."""
    monkeypatch.setenv("GROWW_API_KEY", "dummy_key")
    monkeypatch.setenv("GROWW_TOTP_SECRET", "JBSWY3DPEHPK3PXP")

    cache_file = tmp_path / "token.json"
    manager = GrowwAuthManager(token_cache_path=str(cache_file))

    # Pre-populate valid cache
    manager.cache_token("valid_session_token_123")

    with patch("growwapi.GrowwAPI.get_access_token") as mock_api:
        token = manager.get_access_token(force_refresh=False)
        assert token == "valid_session_token_123"
        mock_api.assert_not_called()


def test_groww_provider_interface_and_resolution() -> None:
    """Verify GrowwProvider implements BaseDataProvider and resolves indices without order methods."""
    from data.groww_provider import GrowwProvider
    from data.base_provider import BaseDataProvider

    provider = GrowwProvider()
    assert isinstance(provider, BaseDataProvider)
    assert hasattr(provider, "fetch_ohlcv")
    assert hasattr(provider, "fetch_vix")
    
    # Assert no order methods exist on provider
    assert not hasattr(provider, "place_order")
    assert not hasattr(provider, "modify_order")
    assert not hasattr(provider, "cancel_order")
    
    # Check symbol mapping
    nifty = provider.resolve_instrument("NIFTY")
    assert nifty["groww_symbol"] == "NSE-NIFTY"
    assert nifty["segment"] == "CASH"

    sensex = provider.resolve_instrument("SENSEX")
    assert sensex["groww_symbol"] == "BSE-SENSEX"
    assert sensex["exchange"] == "BSE"

