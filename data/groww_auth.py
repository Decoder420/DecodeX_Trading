"""Groww authentication and session management module.

Handles automated daily token generation at 6:00 AM IST using TOTP or approval flows.
Enforces strict secret isolation (secrets live only in .env, never logged or printed).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Optional, Tuple
import pytz
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


class GrowwAuthError(Exception):
    """Base exception for Groww authentication issues."""
    pass


class GrowwApprovalKeyOnlyError(GrowwAuthError):
    """Raised when unattended morning login is attempted with only an approval-based key."""
    pass


class GrowwAuthManager:
    """Manages Groww Trade API access tokens and morning session resets.
    
    Keys reset daily at 6:00 AM IST.
    Credentials:
      - GROWW_API_KEY
      - GROWW_API_SECRET (for approval-based API keys)
      - GROWW_TOTP_SECRET (for TOTP-based automated API keys)
    """

    def __init__(
        self,
        env_file: Optional[str] = None,
        token_cache_path: str = "data/cache/groww_token.json",
    ) -> None:
        if env_file:
            env_path = Path(env_file)
            if env_path.exists():
                load_dotenv(dotenv_path=env_path, override=True)
        else:
            workspace_env = Path.cwd() / ".env"
            if workspace_env.exists():
                load_dotenv(dotenv_path=workspace_env, override=False)

        self.token_cache_path = Path(token_cache_path)
        self.api_key: Optional[str] = os.getenv("GROWW_API_KEY")
        self.api_secret: Optional[str] = os.getenv("GROWW_API_SECRET")
        self.totp_secret: Optional[str] = os.getenv("GROWW_TOTP_SECRET")

    @property
    def has_credentials(self) -> bool:
        """Check if minimum required credentials exist in environment."""
        return bool(self.api_key and (self.totp_secret or self.api_secret))

    @staticmethod
    def get_session_window(now_dt: Optional[datetime] = None) -> Tuple[datetime, datetime]:
        """Compute the current 6:00 AM IST daily session boundary.
        
        Session runs from today's 06:00 IST to tomorrow's 06:00 IST (if now >= 06:00),
        or yesterday's 06:00 IST to today's 06:00 IST (if now < 06:00).
        """
        now = now_dt or datetime.now(IST)
        if now.tzinfo is None:
            now = IST.localize(now)
        else:
            now = now.astimezone(IST)

        today_6am = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if now >= today_6am:
            start = today_6am
            end = today_6am + timedelta(days=1)
        else:
            start = today_6am - timedelta(days=1)
            end = today_6am

        return start, end

    def is_cached_token_valid(self) -> Tuple[bool, Optional[str]]:
        """Check if cached token exists and was created during the current 6 AM session."""
        if not self.token_cache_path.exists():
            return False, None

        try:
            data = json.loads(self.token_cache_path.read_text(encoding="utf-8"))
            token = data.get("token")
            created_str = data.get("created_at")
            if not token or not created_str:
                return False, None

            created_at = datetime.fromisoformat(created_str)
            if created_at.tzinfo is None:
                created_at = IST.localize(created_at)
            else:
                created_at = created_at.astimezone(IST)

            start, end = self.get_session_window()
            if start <= created_at < end:
                return True, token
        except Exception as e:
            logger.debug("Failed to validate cached token: %s", type(e).__name__)

        return False, None

    def cache_token(self, token: str) -> None:
        """Persist token to disk with session metadata (strictly gitignored)."""
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(IST)
        payload = {
            "token": token,
            "created_at": now.isoformat(),
            "resets_at": (self.get_session_window(now)[1]).isoformat(),
        }
        self.token_cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Cached Groww session token (valid until 6:00 AM IST tomorrow).")

    def get_access_token(
        self,
        force_refresh: bool = False,
        allow_approval_fallback: bool = False,
    ) -> str:
        """Retrieve valid session token, refreshing via TOTP if needed.
        
        Args:
            force_refresh: Force a fresh API request even if cached token is within session.
            allow_approval_fallback: If True and only GROWW_API_SECRET is configured,
                                     allows generation via approval checksum instead of raising.

        Returns:
            Bearer access token string.

        Raises:
            GrowwApprovalKeyOnlyError: If only approval key is present and fallback not allowed.
            GrowwAuthError: If authentication fails.
        """
        if not force_refresh:
            valid, cached_token = self.is_cached_token_valid()
            if valid and cached_token:
                logger.info("Using valid cached Groww session token for current trading day.")
                return cached_token

        if not self.api_key:
            raise GrowwAuthError(
                "GROWW_API_KEY is missing from environment. Please populate .env file."
            )

        from growwapi import GrowwAPI
        import pyotp

        if self.totp_secret and self.totp_secret.strip():
            logger.info("Generating fresh Groww access token using automated TOTP flow...")
            try:
                totp_code = pyotp.TOTP(self.totp_secret.strip()).now()
                token = GrowwAPI.get_access_token(
                    api_key=self.api_key.strip(),
                    totp=totp_code,
                )
                self.cache_token(token)
                return token
            except Exception as e:
                logger.error("Groww TOTP authentication failed: %s", type(e).__name__)
                raise GrowwAuthError(f"Groww TOTP authentication failed: {e}") from e

        if self.api_secret and self.api_secret.strip():
            msg = (
                "Groww credentials contain only an approval-based key (GROWW_API_SECRET). "
                "Keys reset daily at 6:00 AM IST. Automated unattended morning login requires "
                "a TOTP-based key. Please click 'Generate API key' in Groww dashboard "
                "(groww.in/trade-api/api-keys), select 'TOTP based', and add GROWW_TOTP_SECRET to .env."
            )
            if not allow_approval_fallback:
                logger.error(msg)
                raise GrowwApprovalKeyOnlyError(msg)

            logger.warning(
                "Using approval-based key fallback for one-off execution: %s",
                msg,
            )
            try:
                token = GrowwAPI.get_access_token(
                    api_key=self.api_key.strip(),
                    secret=self.api_secret.strip(),
                )
                self.cache_token(token)
                return token
            except Exception as e:
                logger.error("Groww approval-key authentication failed: %s", type(e).__name__)
                raise GrowwAuthError(f"Groww approval-key authentication failed: {e}") from e

        raise GrowwAuthError(
            "Neither GROWW_TOTP_SECRET nor GROWW_API_SECRET is present in .env. "
            "Cannot authenticate with Groww Trade API."
        )
