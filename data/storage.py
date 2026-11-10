"""Data persistence layer supporting DuckDB and SQLite with incremental upserts."""

from __future__ import annotations

import inspect
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
import duckdb
import pandas as pd
import pytz

from config.loader import ConfigManager, config_manager

logger = logging.getLogger(__name__)

_DOWNLOADER_WRITE_AUTHORIZED = threading.local()


@contextmanager
def DownloaderWriteGuard():
    """Context manager authorizing writes to market_data.duckdb strictly from downloader workflows."""
    _DOWNLOADER_WRITE_AUTHORIZED.active = True
    try:
        yield
    finally:
        _DOWNLOADER_WRITE_AUTHORIZED.active = False


def is_downloader_authorized() -> bool:
    """Check whether current thread or call stack is authorized to write to market_data.duckdb."""
    if getattr(_DOWNLOADER_WRITE_AUTHORIZED, "active", False):
        return True
    for frame_info in inspect.stack():
        filename = frame_info.filename.lower()
        if "historical_downloader" in filename:
            return True
    return False


class StorageManager:
    """Manages persistent time-series storage in DuckDB or SQLite."""

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        self.backend = self.cfg.get("data.storage.backend", "duckdb").lower()
        self.tz = pytz.timezone(self.cfg.get("market.timezone", "Asia/Kolkata"))

        if self.backend == "duckdb":
            db_path_str = self.cfg.get("data.storage.duckdb_path", "data/market_data.duckdb")
        else:
            db_path_str = self.cfg.get("data.storage.sqlite_path", "data/market_data.db")

        self.db_path = Path(db_path_str)
        if not self.db_path.is_absolute():
            self.db_path = Path(__file__).resolve().parent.parent / self.db_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("StorageManager initialized using %s at %s", self.backend, self.db_path)

    @staticmethod
    def _format_table_name(symbol: str, timeframe: str) -> str:
        clean_symbol = symbol.replace("^", "").replace(" ", "_").replace(":", "_").lower()
        clean_tf = timeframe.lower()
        return f"ohlcv_{clean_symbol}_{clean_tf}"

    def get_latest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Retrieve the most recent timestamp stored for an instrument and timeframe."""
        table_name = self._format_table_name(symbol, timeframe)

        if self.backend == "duckdb":
            con = duckdb.connect(str(self.db_path))
            try:
                tables = con.execute("SHOW TABLES").fetchall()
                table_names = [t[0] for t in tables]
                if table_name not in table_names:
                    return None
                res = con.execute(f"SELECT MAX(timestamp) FROM {table_name}").fetchone()
                if res and res[0] is not None:
                    ts = pd.to_datetime(res[0])
                    if ts.tz is None:
                        ts = ts.tz_localize(self.tz)
                    else:
                        ts = ts.tz_convert(self.tz)
                    return ts.to_pydatetime()
                return None
            finally:
                con.close()
        else:
            con = sqlite3.connect(str(self.db_path))
            try:
                cur = con.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                )
                if not cur.fetchone():
                    return None
                cur.execute(f"SELECT MAX(timestamp) FROM {table_name}")
                row = cur.fetchone()
                if row and row[0] is not None:
                    ts = pd.to_datetime(row[0])
                    if ts.tz is None:
                        ts = ts.tz_localize(self.tz)
                    else:
                        ts = ts.tz_convert(self.tz)
                    return ts.to_pydatetime()
                return None
            finally:
                con.close()

    def get_earliest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Retrieve the earliest timestamp stored for an instrument and timeframe."""
        table_name = self._format_table_name(symbol, timeframe)

        if self.backend == "duckdb":
            con = duckdb.connect(str(self.db_path))
            try:
                tables = con.execute("SHOW TABLES").fetchall()
                table_names = [t[0] for t in tables]
                if table_name not in table_names:
                    return None
                res = con.execute(f"SELECT MIN(timestamp) FROM {table_name}").fetchone()
                if res and res[0] is not None:
                    ts = pd.to_datetime(res[0])
                    if ts.tz is None:
                        ts = ts.tz_localize(self.tz)
                    else:
                        ts = ts.tz_convert(self.tz)
                    return ts.to_pydatetime()
                return None
            finally:
                con.close()
        else:
            con = sqlite3.connect(str(self.db_path))
            try:
                cur = con.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                )
                if not cur.fetchone():
                    return None
                cur.execute(f"SELECT MIN(timestamp) FROM {table_name}")
                row = cur.fetchone()
                if row and row[0] is not None:
                    ts = pd.to_datetime(row[0])
                    if ts.tz is None:
                        ts = ts.tz_localize(self.tz)
                    else:
                        ts = ts.tz_convert(self.tz)
                    return ts.to_pydatetime()
                return None
            finally:
                con.close()

    def get_all_market_trading_dates(self) -> set[date]:
        """Collect the union of all trading dates observed across all stored instruments."""
        all_dates: set[date] = set()
        if self.backend == "duckdb":
            con = duckdb.connect(str(self.db_path))
            try:
                tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
                for t in tables:
                    if t.startswith("ohlcv_"):
                        rows = con.execute(f"SELECT DISTINCT SUBSTRING(timestamp, 1, 10) FROM {t}").fetchall()
                        for r in rows:
                            if r[0]:
                                try:
                                    all_dates.add(datetime.strptime(r[0], "%Y-%m-%d").date())
                                except Exception:
                                    pass
            finally:
                con.close()
        return all_dates

    def save_ohlcv(self, df: pd.DataFrame, symbol: str, timeframe: str) -> int:
        """Upsert candles into the instrument-timeframe table.

        Returns:
            Number of candles upserted.
        """
        if df.empty:
            return 0

        # Guard: Only the historical downloader may write to market_data.duckdb
        if self.db_path.name == "market_data.duckdb" and not is_downloader_authorized():
            raise PermissionError(
                f"UNAUTHORIZED WRITER GUARD: Only data.historical_downloader is permitted to write to {self.db_path.name}. "
                "All other components, tests, and real-time feeds are forbidden from writing to the persistent historical archive."
            )

        table_name = self._format_table_name(symbol, timeframe)
        clean_df = df.copy()

        # Enforce Index volume is 0. Spot indices and VIX do not trade volume.
        clean_symbol = symbol.replace("^", "").replace(" ", "_").replace(":", "_").lower()
        index_names = {"nifty", "banknifty", "sensex", "india_vix", "vix"}
        if clean_symbol in index_names or any(idx in clean_symbol for idx in index_names):
            clean_df["volume"] = 0.0

        # Ensure timestamp is string in ISO format for stable database storage
        if "timestamp" not in clean_df.columns:
            raise ValueError("DataFrame must contain 'timestamp' column.")

        clean_df["timestamp"] = pd.to_datetime(clean_df["timestamp"])
        if clean_df["timestamp"].dt.tz is None:
            clean_df["timestamp"] = clean_df["timestamp"].dt.tz_localize(self.tz)
        else:
            clean_df["timestamp"] = clean_df["timestamp"].dt.tz_convert(self.tz)

        clean_df["ts_str"] = clean_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S%z")

        if "is_outlier" not in clean_df.columns:
            clean_df["is_outlier"] = False
        if "is_gap" not in clean_df.columns:
            clean_df["is_gap"] = False

        now_str = datetime.now(self.tz).strftime("%Y-%m-%d %H:%M:%S%z")
        clean_df["updated_at"] = now_str

        # Remove duplicate timestamps within the batch
        clean_df = clean_df.drop_duplicates(subset=["ts_str"]).sort_values("ts_str")

        if self.backend == "duckdb":
            con = duckdb.connect(str(self.db_path))
            try:
                con.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        timestamp VARCHAR PRIMARY KEY,
                        open DOUBLE,
                        high DOUBLE,
                        low DOUBLE,
                        close DOUBLE,
                        volume DOUBLE,
                        is_outlier BOOLEAN,
                        is_gap BOOLEAN,
                        updated_at VARCHAR
                    )
                    """
                )
                # Temp table for upsert
                con.register("incoming_batch", clean_df)
                con.execute(
                    f"""
                    INSERT OR REPLACE INTO {table_name}
                    SELECT ts_str AS timestamp, open, high, low, close, volume,
                           is_outlier, is_gap, updated_at
                    FROM incoming_batch
                    """
                )
                count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                logger.info(
                    "Upserted %d candles into DuckDB table %s (total rows: %d)",
                    len(clean_df),
                    table_name,
                    count,
                )
                return len(clean_df)
            finally:
                con.close()
        else:
            con = sqlite3.connect(str(self.db_path))
            try:
                cur = con.cursor()
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        timestamp TEXT PRIMARY KEY,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume REAL,
                        is_outlier INTEGER,
                        is_gap INTEGER,
                        updated_at TEXT
                    )
                    """
                )
                records = [
                    (
                        row["ts_str"],
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        float(row["volume"]),
                        1 if row["is_outlier"] else 0,
                        1 if row["is_gap"] else 0,
                        row["updated_at"],
                    )
                    for _, row in clean_df.iterrows()
                ]
                cur.executemany(
                    f"""
                    INSERT OR REPLACE INTO {table_name}
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    records,
                )
                con.commit()
                return len(clean_df)
            finally:
                con.close()

    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Load stored candles for an instrument as a sorted DataFrame."""
        table_name = self._format_table_name(symbol, timeframe)

        if self.backend == "duckdb":
            con = duckdb.connect(str(self.db_path))
            try:
                tables = con.execute("SHOW TABLES").fetchall()
                if table_name not in [t[0] for t in tables]:
                    return pd.DataFrame(
                        columns=["timestamp", "open", "high", "low", "close", "volume", "is_outlier", "is_gap"]
                    )
                query = f"SELECT * FROM {table_name}"
                df = con.execute(query).df()
            finally:
                con.close()
        else:
            con = sqlite3.connect(str(self.db_path))
            try:
                cur = con.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                )
                if not cur.fetchone():
                    return pd.DataFrame(
                        columns=["timestamp", "open", "high", "low", "close", "volume", "is_outlier", "is_gap"]
                    )
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", con)
            finally:
                con.close()

        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(self.tz)
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert(self.tz)

        df = df.sort_values("timestamp").reset_index(drop=True)

        if start is not None:
            start_tz = start if start.tzinfo else self.tz.localize(start)
            df = df[df["timestamp"] >= start_tz]
        if end is not None:
            end_tz = end if end.tzinfo else self.tz.localize(end)
            df = df[df["timestamp"] <= end_tz]

        return df.reset_index(drop=True)
