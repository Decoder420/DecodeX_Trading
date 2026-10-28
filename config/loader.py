"""Configuration loader and market calendar helper.

Provides strongly typed access to config parameters, holiday calendars,
and time-varying lot size and expiry schedules for Indian indices.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


class ConfigManager:
    """Manages application configuration, calendar rules, and instrument metadata."""

    def __init__(self, config_path: Path | str = DEFAULT_CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = self._load_yaml(self.config_path)
        self.holiday_path = Path(
            self.config.get("market", {}).get("holiday_calendar_path", "config/holidays.yaml")
        )
        if not self.holiday_path.is_absolute():
            self.holiday_path = self.config_path.parent.parent / self.holiday_path

        self.holidays: Dict[str, str] = self._load_holidays(self.holiday_path)

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _load_holidays(path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data.get("holidays", {})

    def get(self, key: str, default: Any = None) -> Any:
        """Fetch nested dictionary values using dot notation (e.g. 'data.storage.backend')."""
        keys = key.split(".")
        val = self.config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def is_holiday(self, check_date: date | datetime | str) -> bool:
        """Check if a date is a recognized exchange trading holiday."""
        d_str = check_date.strftime("%Y-%m-%d") if isinstance(check_date, (date, datetime)) else str(check_date)
        return d_str in self.holidays

    def is_trading_day(self, check_date: date | datetime) -> bool:
        """Check if date is a weekday (Mon-Fri) and not an exchange holiday."""
        d = check_date.date() if isinstance(check_date, datetime) else check_date
        if d.weekday() >= 5:  # Saturday or Sunday
            return False
        return not self.is_holiday(d)

    def get_previous_trading_day(self, ref_date: date | datetime) -> date:
        """Return the nearest preceding trading day."""
        d = ref_date.date() if isinstance(ref_date, datetime) else ref_date
        candidate = d - timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate -= timedelta(days=1)
        return candidate

    def get_next_trading_day(self, ref_date: date | datetime) -> date:
        """Return the nearest following trading day."""
        d = ref_date.date() if isinstance(ref_date, datetime) else ref_date
        candidate = d + timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate += timedelta(days=1)
        return candidate

    def get_lot_size(self, instrument: str, ref_date: date | datetime) -> int:
        """Retrieve the effective lot size for an instrument on a given date."""
        inst = self.config.get("instruments", {}).get(instrument)
        if not inst:
            if instrument == "POOLED":
                return 50
            raise KeyError(f"Unknown instrument: {instrument}")

        history: List[Dict[str, Any]] = inst.get("lot_size_history", [])
        if not history:
            return int(inst.get("lot_size", 1))

        d = ref_date.date() if isinstance(ref_date, datetime) else ref_date
        d_str = d.strftime("%Y-%m-%d")

        # Sort history ascending by effective_from
        sorted_history = sorted(history, key=lambda x: str(x["effective_from"]))
        effective_lot = sorted_history[0]["lot_size"]
        for entry in sorted_history:
            if str(entry["effective_from"]) <= d_str:
                effective_lot = entry["lot_size"]
            else:
                break
        return int(effective_lot)

    def get_expiry_rule(self, instrument: str, ref_date: date | datetime) -> Dict[str, Any]:
        """Retrieve active expiry rule for an instrument on a given date."""
        inst = self.config.get("instruments", {}).get(instrument)
        if not inst:
            if instrument == "POOLED":
                return {"frequency": "weekly", "day_of_week": "Thursday"}
            raise KeyError(f"Unknown instrument: {instrument}")

        history: List[Dict[str, Any]] = inst.get("expiry_rules_history", [])
        if not history:
            return {"frequency": "weekly", "day_of_week": "Thursday"}

        d = ref_date.date() if isinstance(ref_date, datetime) else ref_date
        d_str = d.strftime("%Y-%m-%d")

        sorted_history = sorted(history, key=lambda x: str(x["effective_from"]))
        active_rule = sorted_history[0]
        for entry in sorted_history:
            if str(entry["effective_from"]) <= d_str:
                active_rule = entry
            else:
                break
        return active_rule

    def _day_name_to_weekday(self, day_name: str) -> int:
        days = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        return days.get(day_name.lower().strip(), 3)

    def _get_candidate_expiry_dates_in_month(
        self, year: int, month: int, weekday: int, frequency: str
    ) -> List[date]:
        """Get all nominal scheduled expiry dates in a given month."""
        from calendar import monthrange

        _, num_days = monthrange(year, month)
        all_dates = [date(year, month, d) for d in range(1, num_days + 1)]
        matching = [d for d in all_dates if d.weekday() == weekday]

        if frequency == "monthly":
            return [matching[-1]] if matching else []
        return matching

    def resolve_expiry_date(self, nominal_expiry: date) -> date:
        """If nominal expiry lands on a holiday or weekend, advance to previous trading day."""
        candidate = nominal_expiry
        while not self.is_trading_day(candidate):
            candidate -= timedelta(days=1)
        return candidate

    def is_expiry_day(self, instrument: str, check_date: date | datetime) -> bool:
        """Check whether check_date is the actual resolved expiry day for instrument."""
        d = check_date.date() if isinstance(check_date, datetime) else check_date
        rule = self.get_expiry_rule(instrument, d)
        target_weekday = self._day_name_to_weekday(rule.get("day_of_week", "Thursday"))
        frequency = rule.get("frequency", "weekly")

        # Check candidate expiries in the current month
        candidates = self._get_candidate_expiry_dates_in_month(
            d.year, d.month, target_weekday, frequency
        )
        resolved_expiries = [self.resolve_expiry_date(cand) for cand in candidates]
        return d in resolved_expiries

    def days_to_expiry(self, instrument: str, check_date: date | datetime) -> int:
        """Calculate calendar days to the next resolved expiry day for instrument."""
        d = check_date.date() if isinstance(check_date, datetime) else check_date
        rule = self.get_expiry_rule(instrument, d)
        target_weekday = self._day_name_to_weekday(rule.get("day_of_week", "Thursday"))
        frequency = rule.get("frequency", "weekly")

        # Search candidates in this month and next month
        next_month_year = d.year + (1 if d.month == 12 else 0)
        next_month = 1 if d.month == 12 else d.month + 1

        cand_curr = self._get_candidate_expiry_dates_in_month(
            d.year, d.month, target_weekday, frequency
        )
        cand_next = self._get_candidate_expiry_dates_in_month(
            next_month_year, next_month, target_weekday, frequency
        )

        resolved = sorted(
            [self.resolve_expiry_date(c) for c in cand_curr + cand_next if self.resolve_expiry_date(c) >= d]
        )
        if resolved:
            return (resolved[0] - d).days
        return 0


# Singleton default loader
config_manager = ConfigManager()
