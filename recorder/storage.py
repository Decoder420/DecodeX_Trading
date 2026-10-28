"""Isolated daily DuckDB persistence layer for live market recorder."""

from __future__ import annotations

from datetime import date, datetime
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import duckdb
import pandas as pd

logger = logging.getLogger("LiveStorage")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIVE_DIR = PROJECT_ROOT / "data" / "live"


class LiveStorageManager:
    """Manages isolated per-day DuckDB files under data/live/ to prevent table locking."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir or DEFAULT_LIVE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.consolidated_dir = self.base_dir / "consolidated"
        self.consolidated_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def get_db_path(self, target_date: Optional[Union[date, str]] = None) -> Path:
        if isinstance(target_date, str):
            try:
                clean_str = target_date.replace("-", "").replace("_", "")
                d = datetime.strptime(clean_str, "%Y%m%d").date()
            except Exception:
                d = datetime.now().date()
        else:
            d = target_date or datetime.now().date()
        date_str = d.strftime("%Y_%m_%d")
        return self.base_dir / f"live_{date_str}.duckdb"

    def get_connection(self, target_date: Optional[date] = None) -> duckdb.DuckDBPyConnection:
        db_path = self.get_db_path(target_date)
        conn = duckdb.connect(str(db_path))
        self._init_tables(conn)
        return conn

    def _init_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create isolated per-day tables if not existing."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS live_ticks (
                exchange_timestamp TIMESTAMPTZ,
                received_at TIMESTAMPTZ,
                token VARCHAR,
                symbol VARCHAR,
                instrument_type VARCHAR,
                ltp DOUBLE,
                ltq BIGINT,
                volume BIGINT,
                source VARCHAR
            );

            CREATE TABLE IF NOT EXISTS live_depth (
                timestamp TIMESTAMPTZ,
                token VARCHAR,
                symbol VARCHAR,
                best_bid DOUBLE,
                best_ask DOUBLE,
                depth_imbalance DOUBLE,
                spread DOUBLE,
                source VARCHAR
            );

            CREATE TABLE IF NOT EXISTS futures_bars (
                timestamp TIMESTAMPTZ,
                symbol VARCHAR,
                token VARCHAR,
                contract_expiry DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                oi BIGINT,
                vwap DOUBLE,
                source VARCHAR
            );

            CREATE TABLE IF NOT EXISTS options_snapshots (
                timestamp TIMESTAMPTZ,
                underlying VARCHAR,
                contract_expiry DATE,
                strike DOUBLE,
                option_type VARCHAR,
                token VARCHAR,
                ltp DOUBLE,
                volume BIGINT,
                oi BIGINT,
                iv DOUBLE,
                delta DOUBLE,
                gamma DOUBLE,
                theta DOUBLE,
                vega DOUBLE,
                greeks_source VARCHAR, -- 'broker_optionGreek' OR 'computed_black76'
                source VARCHAR
            );

            CREATE TABLE IF NOT EXISTS live_derived_metrics (
                timestamp TIMESTAMPTZ,
                underlying VARCHAR,
                pcr_oi DOUBLE,
                pcr_volume DOUBLE,
                max_pain DOUBLE,
                atm_iv DOUBLE,
                iv_skew DOUBLE,
                futures_basis DOUBLE,
                recording_since TIMESTAMPTZ,
                history_days_count INTEGER,
                roll_active_contract VARCHAR,
                roll_spread DOUBLE
            );
            ALTER TABLE live_derived_metrics ADD COLUMN IF NOT EXISTS roll_active_contract VARCHAR;
            ALTER TABLE live_derived_metrics ADD COLUMN IF NOT EXISTS roll_spread DOUBLE;


            CREATE TABLE IF NOT EXISTS recorder_health (
                timestamp TIMESTAMPTZ,
                status VARCHAR,
                uptime_seconds DOUBLE,
                ticks_received BIGINT,
                tick_rate_per_sec DOUBLE,
                active_source VARCHAR,
                disconnect_count INTEGER,
                last_tick_age_seconds DOUBLE,
                memory_mb DOUBLE
            );
        """)

    def insert_ticks(self, rows: List[Dict[str, Any]], target_date: Optional[date] = None) -> int:
        if not rows:
            return 0
        df = pd.DataFrame(rows)
        with self._lock:
            conn = self.get_connection(target_date)
            try:
                conn.register("df_ticks", df)
                conn.execute("INSERT INTO live_ticks SELECT * FROM df_ticks")
                return len(rows)
            finally:
                conn.close()

    def insert_depth(self, rows: List[Dict[str, Any]], target_date: Optional[date] = None) -> int:
        if not rows:
            return 0
        df = pd.DataFrame(rows)
        with self._lock:
            conn = self.get_connection(target_date)
            try:
                conn.register("df_depth", df)
                conn.execute("INSERT INTO live_depth SELECT * FROM df_depth")
                return len(rows)
            finally:
                conn.close()

    def insert_futures_bars(self, rows: List[Dict[str, Any]], target_date: Optional[date] = None) -> int:
        if not rows:
            return 0
        df = pd.DataFrame(rows)
        with self._lock:
            conn = self.get_connection(target_date)
            try:
                conn.register("df_fbars", df)
                conn.execute("INSERT INTO futures_bars SELECT * FROM df_fbars")
                return len(rows)
            finally:
                conn.close()

    def insert_options_snapshots(self, rows: List[Dict[str, Any]], target_date: Optional[date] = None) -> int:
        if not rows:
            return 0
        df = pd.DataFrame(rows)
        with self._lock:
            conn = self.get_connection(target_date)
            try:
                conn.register("df_opts", df)
                conn.execute("INSERT INTO options_snapshots SELECT * FROM df_opts")
                return len(rows)
            finally:
                conn.close()

    def insert_derived_metrics(self, rows: List[Dict[str, Any]], target_date: Optional[date] = None) -> int:
        if not rows:
            return 0
        df = pd.DataFrame(rows)
        with self._lock:
            conn = self.get_connection(target_date)
            try:
                conn.register("df_metrics", df)
                conn.execute("INSERT INTO live_derived_metrics BY NAME SELECT * FROM df_metrics")
                return len(rows)
            finally:
                conn.close()

    def insert_health(self, health_row: Dict[str, Any], target_date: Optional[date] = None) -> None:
        df = pd.DataFrame([health_row])
        with self._lock:
            conn = self.get_connection(target_date)
            try:
                conn.register("df_h", df)
                conn.execute("INSERT INTO recorder_health SELECT * FROM df_h")
            finally:
                conn.close()

    def get_disk_usage(self) -> Dict[str, Any]:
        """Estimate disk usage of active daily databases and consolidated archives."""
        daily_files = list(self.base_dir.glob("live_*.duckdb"))
        daily_bytes = sum(f.stat().st_size for f in daily_files)
        consolidated_files = list(self.consolidated_dir.rglob("*.parquet"))
        cons_bytes = sum(f.stat().st_size for f in consolidated_files)

        return {
            "daily_duckdb_files_count": len(daily_files),
            "daily_duckdb_total_mb": round(daily_bytes / (1024 * 1024), 2),
            "consolidated_parquet_files_count": len(consolidated_files),
            "consolidated_parquet_total_mb": round(cons_bytes / (1024 * 1024), 2),
            "estimated_daily_duckdb_mb": 20.0,
            "estimated_daily_parquet_mb": 6.5,
            "estimated_monthly_raw_mb": 420.0,
            "estimated_monthly_consolidated_mb": 136.5,
            "raw_duckdb_retention_days": 14,
            "consolidated_parquet_retention_days": 365,
        }

    def consolidate_day_to_parquet(self, target_date: Union[date, str]) -> Dict[str, int]:
        """Nightly consolidation job (runs >= 15:45 IST) exporting daily tables to compressed parquet."""
        db_path = self.get_db_path(target_date)
        if not db_path.exists():
            return {}

        if isinstance(target_date, str):
            clean_str = target_date.replace("-", "").replace("_", "")
            try:
                d = datetime.strptime(clean_str, "%Y%m%d").date()
            except Exception:
                d = datetime.now().date()
        else:
            d = target_date

        date_str = d.strftime("%Y-%m-%d")
        dest_dir = self.consolidated_dir / f"date={date_str}"
        dest_dir.mkdir(parents=True, exist_ok=True)

        counts = {}
        with self._lock:
            conn = duckdb.connect(str(db_path))
            try:
                tables = ["live_ticks", "live_depth", "futures_bars", "options_snapshots", "live_derived_metrics", "recorder_health"]
                for t in tables:
                    cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    counts[t] = cnt
                    if cnt > 0:
                        pq_path = dest_dir / f"{t}.parquet"
                        conn.execute(f"COPY {t} TO '{pq_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            finally:
                conn.close()

        logger.info("Consolidated %s into %s: %s", date_str, dest_dir, counts)
        return counts

    def cleanup_old_raw_dbs(self, retention_days: int = 14) -> List[Path]:
        """Purge raw DuckDB daily files older than retention_days if consolidated parquet exists."""
        purged = []
        today = datetime.now().date()
        daily_files = list(self.base_dir.glob("live_*.duckdb"))

        with self._lock:
            for f in daily_files:
                try:
                    # File name format: live_YYYY_MM_DD.duckdb
                    parts = f.stem.replace("live_", "").split("_")
                    if len(parts) == 3:
                        f_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                        age_days = (today - f_date).days
                        if age_days > retention_days:
                            # Verify consolidated parquet exists before purging raw db
                            date_str = f_date.strftime("%Y-%m-%d")
                            pq_dir = self.consolidated_dir / f"date={date_str}"
                            if pq_dir.exists() and any(pq_dir.glob("*.parquet")):
                                f.unlink()
                                purged.append(f)
                                logger.info("Purged raw duckdb %s (age %d days, consolidated copy preserved)", f.name, age_days)
                except Exception as e:
                    logger.warning("Error inspecting file %s for cleanup: %s", f.name, e)

        return purged
