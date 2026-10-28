"""Stage 1 Live Market Recorder Test Run.

Executes a live test (~60-75 seconds) during active market hours:
- Captures live ticks and depth for Spot & Futures via WebSocket
- Validates watchdog & REST fallback mechanism
- Flushes 1-minute futures bars with volume differencing and VWAP
- Captures 1-minute options chain snapshot with Black-76 SENSEX greeks
- Records health heartbeats
- Inspects storage size in data/live/live_YYYY_MM_DD.duckdb
- Runs automated secret scan on the test log
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import duckdb
from dotenv import load_dotenv

# Set up dedicated sanitized test log
log_dir = Path("logs") / datetime.now().strftime("%Y-%m-%d")
log_dir.mkdir(parents=True, exist_ok=True)
test_log_file = log_dir / "recorder_test.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(test_log_file, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Stage1Test")

from recorder.engine import LiveRecorderEngine
from recorder.storage import LiveStorageManager

# Sensitive keywords pattern for secrets scan
SENSITIVE_PATTERNS = [
    r"Bearer\s+[A-Za-z0-9_\-\.]+",
    r"\"jwtToken\"\s*:\s*\"[^\"]+\"",
    r"\"refreshToken\"\s*:\s*\"[^\"]+\"",
    r"\"feedToken\"\s*:\s*\"[^\"]+\"",
    r"X-PrivateKey:\s*[A-Za-z0-9]+",
]


def run_secrets_scan(log_path: Path) -> Dict[str, Any]:
    """Scan log file for any potential credentials, tokens, or private keys."""
    load_dotenv()
    api_key = os.getenv("ANGEL_API_KEY", "")
    client_id = os.getenv("ANGEL_CLIENT_ID", "")
    mpin = os.getenv("ANGEL_MPIN", "")
    totp = os.getenv("ANGEL_TOTP_SECRET", "")

    raw_secrets = [s for s in [api_key, client_id, mpin, totp] if s and len(s) >= 4]

    findings = []
    if not log_path.exists():
        return {"status": "SKIPPED", "findings_count": 0, "findings": []}

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for idx, line in enumerate(lines, 1):
        for sec in raw_secrets:
            if sec in line:
                findings.append(f"Line {idx}: Exact secret value matched (redacted)")
        for pat in SENSITIVE_PATTERNS:
            if re.search(pat, line, re.IGNORECASE):
                findings.append(f"Line {idx}: Pattern '{pat}' matched")

    return {
        "status": "PASSED" if len(findings) == 0 else "FAILED",
        "findings_count": len(findings),
        "findings": findings,
        "scanned_lines": len(lines),
    }


def main():
    print("=" * 80)
    print("STAGE 1 LIVE RECORDER INTEGRATION TEST (Active Market Hours)")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 80)

    storage = LiveStorageManager()
    engine = LiveRecorderEngine(storage_mgr=storage)

    # Run for 65 seconds
    test_duration = 65
    print(f"\n1. Starting recorder for {test_duration} seconds...")
    summary = engine.run(duration_seconds=test_duration)

    print("\n2. Recorder Execution Summary:")
    print(f"   Uptime: {summary['uptime_seconds']}s")
    print(f"   Total Ticks Received: {summary['ticks_received']}")
    print(f"   Tick Rate: {summary['tick_rate_per_sec']} ticks/sec")
    print(f"   Active Source: {summary['active_source']}")
    print(f"   Disconnect Count: {summary['disconnect_count']}")

    # 3. Database Table Row Counts
    db_path = storage.get_db_path()
    print(f"\n3. Database Verification ({db_path}):")
    if db_path.exists():
        file_size_kb = round(db_path.stat().st_size / 1024, 2)
        print(f"   Database File Size: {file_size_kb} KB")
        conn = duckdb.connect(str(db_path))
        tables = [
            "live_ticks",
            "live_depth",
            "futures_bars",
            "options_snapshots",
            "live_derived_metrics",
            "recorder_health",
        ]
        for t in tables:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"   - {t:<22}: {cnt} rows")

        # Show samples
        print("\n   Sample Futures Bar:")
        fb_sample = conn.execute("SELECT * FROM futures_bars LIMIT 2").fetchdf()
        print(fb_sample.to_string())

        print("\n   Sample Options Snapshot (NIFTY & SENSEX):")
        opt_sample = conn.execute(
            "SELECT underlying, contract_expiry, strike, option_type, ltp, iv, delta, greeks_source, source "
            "FROM options_snapshots LIMIT 4"
        ).fetchdf()
        print(opt_sample.to_string())

        print("\n   Sample Derived Metrics:")
        dm_sample = conn.execute("SELECT * FROM live_derived_metrics LIMIT 3").fetchdf()
        print(dm_sample.to_string())

        print("\n   Sample Recorder Health:")
        h_sample = conn.execute("SELECT * FROM recorder_health ORDER BY timestamp DESC LIMIT 2").fetchdf()
        print(h_sample.to_string())
        conn.close()
    else:
        print("   Database file not found!")

    # 4. Secrets Scan
    print("\n4. Running Automated Secrets Scan on Recorder Test Log...")
    scan_res = run_secrets_scan(test_log_file)
    print(f"   Log File Scanned: {test_log_file}")
    print(f"   Scanned Lines: {scan_res['scanned_lines']}")
    print(f"   Secrets Scan Status: {scan_res['status']}")
    print(f"   Findings Count: {scan_res['findings_count']}")
    if scan_res["findings"]:
        for f in scan_res["findings"]:
            print(f"   - {f}")

    print("\n" + "=" * 80)
    print("STAGE 1 TEST RUN COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
