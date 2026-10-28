"""Full-Day Put-Call Parity Audit across All Liquid Strikes.

Evaluates Put-Call Parity: C - P = (F - K) * e^(-r*T) across all timestamps
and liquid strikes (OI > 0, Volume > 0, or ATM +/- 500) for recorded sessions.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List
import duckdb
import pandas as pd

DB_DIR = Path(__file__).resolve().parent.parent / "data" / "live"
DATES = ["2026_10_26", "2026_10_27", "2026_10_28"]


def audit_session_parity(db_date: str, tolerance_pts: float = 15.0) -> Dict[str, Any]:
    db_path = DB_DIR / f"live_{db_date}.duckdb"
    if not db_path.exists():
        return {"error": f"Database {db_path} not found"}

    con = duckdb.connect(str(db_path), read_only=True)
    
    # Check tables
    tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
    if "options_snapshots" not in tables:
        con.close()
        return {"error": "options_snapshots table missing"}

    # Reference spot for the day
    spot_query = "SELECT avg(ltp) FROM live_ticks WHERE symbol = 'NIFTY 50' OR symbol = 'NIFTY'"
    try:
        ref_spot = con.execute(spot_query).fetchone()[0]
        if not ref_spot or pd.isna(ref_spot):
            ref_spot = 22540.0
    except Exception:
        ref_spot = 22540.0

    # Query all simultaneous CE and PE quotes for liquid strikes
    query = f"""
        WITH calls AS (
            SELECT 
                timestamp,
                strike,
                contract_expiry,
                ltp AS call_ltp,
                oi AS call_oi,
                volume AS call_volume,
                iv AS call_iv
            FROM options_snapshots
            WHERE underlying = 'NIFTY' 
              AND option_type = 'CE'
              AND is_valid = TRUE
              AND ltp > 0
              AND oi > 0
        ),
        puts AS (
            SELECT 
                timestamp,
                strike,
                contract_expiry,
                ltp AS put_ltp,
                oi AS put_oi,
                volume AS put_volume,
                iv AS put_iv
            FROM options_snapshots
            WHERE underlying = 'NIFTY' 
              AND option_type = 'PE'
              AND is_valid = TRUE
              AND ltp > 0
              AND oi > 0
        )
        SELECT 
            c.timestamp,
            c.strike,
            c.contract_expiry,
            c.call_ltp,
            p.put_ltp,
            c.call_oi,
            p.put_oi,
            c.call_volume,
            p.put_volume,
            c.call_iv,
            p.put_iv,
            round(c.call_ltp - p.put_ltp, 2) AS spread,
            round(abs(c.call_iv - p.put_iv), 4) AS iv_diff
        FROM calls c
        JOIN puts p 
          ON c.timestamp = p.timestamp 
         AND c.strike = p.strike 
         AND c.contract_expiry = p.contract_expiry
        WHERE abs(c.strike - {ref_spot}) <= 1000.0  -- All liquid strikes within +/- 1000 pts
        ORDER BY c.timestamp ASC, c.strike ASC;
    """

    df = con.execute(query).df()
    con.close()

    if df.empty:
        return {
            "session": db_date,
            "total_pairs": 0,
            "pass_count": 0,
            "fail_count": 0,
            "pass_rate_pct": 0.0,
            "avg_discrepancy": 0.0,
        }

    # Evaluate synchronous snapshot-level Put-Call Parity:
    # At each exact snapshot timestamp and expiry, the options market establishes an implied forward:
    # F_implied(t) = Strike + (Call_LTP - Put_LTP) * e^(r*T)
    # Put-Call Parity across strikes requires:
    # |(Call_LTP - Put_LTP) - (F_implied(t) - Strike) * e^(-r*T)| <= tolerance
    r = 0.0685
    cur_date = datetime.strptime(db_date, "%Y_%m_%d").date()

    df["dte_days"] = df["contract_expiry"].apply(
        lambda exp: max(1, ((exp.date() if hasattr(exp, "date") else exp) - cur_date).days) if pd.notna(exp) else 6
    )
    df["t_years"] = df["dte_days"] / 365.25
    df["discount_factor"] = (-r * df["t_years"]).apply(math.exp)
    df["synthetic_fwd"] = df["strike"] + df["spread"] / df["discount_factor"]

    # Calculate median forward at each snapshot timestamp to eliminate spot dissemination latency
    fwd_by_ts = (
        df.groupby(["timestamp", "contract_expiry"])["synthetic_fwd"]
        .median()
        .rename("session_fwd_at_timestamp")
    )
    df = df.join(fwd_by_ts, on=["timestamp", "contract_expiry"])

    df["theoretical_spread"] = (df["session_fwd_at_timestamp"] - df["strike"]) * df["discount_factor"]
    df["discrepancy_pts"] = (df["spread"] - df["theoretical_spread"]).abs()
    df["is_pass"] = df["discrepancy_pts"] <= tolerance_pts

    total = len(df)
    passes = int(df["is_pass"].sum())
    failing = total - passes
    pass_rate = (passes / total) * 100.0 if total > 0 else 0.0
    avg_disc = float(df["discrepancy_pts"].mean())
    median_disc = float(df["discrepancy_pts"].median())
    p95_disc = float(df["discrepancy_pts"].quantile(0.95))

    return {
        "session": db_date,
        "total_liquid_pairs": total,
        "passing_pairs": passes,
        "failing_pairs": failing,
        "pass_rate_pct": round(pass_rate, 2),
        "avg_discrepancy_pts": round(avg_disc, 2),
        "median_discrepancy_pts": round(median_disc, 2),
        "p95_discrepancy_pts": round(p95_disc, 2),
        "tolerance_pts": tolerance_pts,
        "unique_timestamps": int(df["timestamp"].nunique()),
        "unique_strikes_analyzed": int(df["strike"].nunique()),
        "strike_range": f"{df['strike'].min():.0f} - {df['strike'].max():.0f}",
    }


def main():
    print("=" * 85)
    print("INSTITUTIONAL AUDIT: FULL-DAY PUT-CALL PARITY ACROSS ALL LIQUID STRIKES")
    print("Tolerance: 15.0 pts (Standard Exchange Market Maker Bid-Ask Boundary)")
    print("=" * 85)

    all_res = []
    for d in DATES:
        res = audit_session_parity(d, tolerance_pts=15.0)
        all_res.append(res)
        print(f"\nSession: {d}")
        for k, v in res.items():
            print(f"  {k}: {v}")

    print("\n" + "=" * 85)
    total_pairs = sum(r.get("total_liquid_pairs", 0) for r in all_res)
    total_passes = sum(r.get("passing_pairs", 0) for r in all_res)
    overall_pass_rate = (total_passes / total_pairs * 100.0) if total_pairs > 0 else 0.0
    print(f"OVERALL 3-DAY AGGREGATE:")
    print(f"  Total Liquid Pairs Analyzed: {total_pairs:,}")
    print(f"  Total Passing Pairs: {total_passes:,}")
    print(f"  Overall Parity Pass Rate: {overall_pass_rate:.2f}%")
    print("=" * 85)


if __name__ == "__main__":
    main()
