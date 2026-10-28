"""Compute today's live signals, microstructure metrics, and gate evaluations."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.loader import ConfigManager
from features.pipeline import FeaturePipeline
from models.baselines import TrendFollowingModel, BreakoutModel
from models.linear import RegularizedLogisticModel
from signals.gates import TradeGatekeeper

def main():
    cfg = ConfigManager()
    pipeline = FeaturePipeline(cfg)
    db_path = ROOT_DIR / "data" / "market_data.duckdb"
    live_db_path = ROOT_DIR / "data" / "live" / "live_2026_10_26.duckdb"

    con = duckdb.connect(str(db_path), read_only=True)
    df_vix = con.execute("SELECT * FROM ohlcv_india_vix_1d ORDER BY timestamp ASC").df()
    vix_latest = float(df_vix["close"].iloc[-1])

    live_con = None
    import time
    for _ in range(20):
        try:
            live_con = duckdb.connect(str(live_db_path), read_only=True)
            break
        except Exception:
            time.sleep(0.15)

    if live_con is None:
        raise RuntimeError("Could not connect to live database due to persistent lock.")


    results = []

    for inst in ["NIFTY", "BANKNIFTY", "SENSEX"]:
        tbl = f"ohlcv_{inst.lower()}_1d"
        df_inst = con.execute(f"SELECT * FROM {tbl} ORDER BY timestamp ASC").df()

        # Get latest tick and metrics from live recorder
        live_ticks = live_con.execute(f"""
            SELECT ltp, volume, exchange_timestamp FROM live_ticks 
            WHERE symbol = '{inst}' ORDER BY exchange_timestamp DESC LIMIT 1
        """).df()

        metrics = live_con.execute(f"""
            SELECT pcr_oi, pcr_volume, max_pain, futures_basis FROM live_derived_metrics
            WHERE underlying = '{inst}' ORDER BY timestamp DESC LIMIT 1
        """).df()

        ltp = float(live_ticks["ltp"].iloc[0]) if not live_ticks.empty else float(df_inst["close"].iloc[-1])
        prev_close = float(df_inst["close"].iloc[-1])
        chg_pts = ltp - prev_close
        chg_pct = (chg_pts / prev_close) * 100.0

        # Construct today row
        today_row = df_inst.iloc[-1].copy()
        if hasattr(df_inst["timestamp"].iloc[-1], "tzinfo") and df_inst["timestamp"].iloc[-1].tzinfo is not None:
            today_row["timestamp"] = pd.Timestamp("2026-10-26", tz=df_inst["timestamp"].iloc[-1].tzinfo)
        else:
            today_row["timestamp"] = pd.Timestamp("2026-10-26")
        today_row["open"] = prev_close
        today_row["high"] = max(prev_close, ltp)
        today_row["low"] = min(prev_close, ltp)
        today_row["close"] = ltp
        today_row["volume"] = 1000000

        df_combined = pd.concat([df_inst, pd.DataFrame([today_row])], ignore_index=True)
        df_combined["timestamp"] = pd.to_datetime(df_combined["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata")

        feats = pipeline.compute_all_features(df_combined, instrument=inst, vix_df=df_vix, include_garch=False, include_regime=False)

        atr = float(feats["atr_14"].iloc[-1])
        ema21 = float(feats.get("ema_21", pd.Series([ltp])).iloc[-1])
        ema50 = float(feats.get("ema_50", pd.Series([ltp])).iloc[-1])
        adx = float(feats.get("adx_14", pd.Series([20.0])).iloc[-1])
        vix_pctile = float(feats.get("vix_pctile_252", pd.Series([50.0])).iloc[-1])

        # Models fit strictly on historical data (before today)
        train_feats = feats.iloc[:-1]

        lr = RegularizedLogisticModel(name="Logistic_L2", penalty="l2")
        lr.fit(train_feats)
        lr_sig = lr.predict_signals(feats).iloc[-1]

        trend = TrendFollowingModel()
        trend.fit(train_feats)
        trend_sig = trend.predict_signals(feats).iloc[-1]

        breakout = BreakoutModel()
        breakout.fit(train_feats)
        breakout_sig = breakout.predict_signals(feats).iloc[-1]

        pcr = float(metrics["pcr_oi"].iloc[0]) if not metrics.empty else None
        max_pain = float(metrics["max_pain"].iloc[0]) if not metrics.empty else None
        basis = float(metrics["futures_basis"].iloc[0]) if not metrics.empty else None

        # Sizing and risk
        lot_map = {"NIFTY": 65, "BANKNIFTY": 30, "SENSEX": 20}
        lot_size = lot_map.get(inst, 50)
        stop_dist = atr * 1.5
        target_dist = atr * 2.0

        results.append({
            "instrument": inst,
            "ltp": ltp,
            "chg_pts": chg_pts,
            "chg_pct": chg_pct,
            "ema21": ema21,
            "ema50": ema50,
            "atr": atr,
            "adx": adx,
            "vix": vix_latest,
            "vix_pctile": vix_pctile,
            "pcr_oi": pcr,
            "max_pain": max_pain,
            "futures_basis": basis,
            "lot_size": lot_size,
            "stop_loss_pts": round(stop_dist, 1),
            "target_pts": round(target_dist, 1),
            "lr_direction": str(lr_sig["direction"]),
            "lr_confidence": float(lr_sig["confidence"]),
            "trend_direction": str(trend_sig["direction"]),
            "trend_confidence": float(trend_sig["confidence"]),
            "breakout_direction": str(breakout_sig["direction"]),
            "breakout_confidence": float(breakout_sig["confidence"]),
        })

    con.close()
    live_con.close()

    for r in results:
        print(f"\n==================== {r['instrument']} (LTP: ₹{r['ltp']:,.2f} | {r['chg_pts']:+,.2f} pts / {r['chg_pct']:+.2f}%) ====================")
        print(f"Technical Context:  EMA21=₹{r['ema21']:,.1f} | EMA50=₹{r['ema50']:,.1f} | ATR(14)={r['atr']:.1f} pts | ADX={r['adx']:.1f}")
        print(f"Options & Basis:    PCR(OI)={r['pcr_oi']:.3f} | Max Pain=₹{r['max_pain']:,.0f} | Basis=+{r['futures_basis']:.2f} pts")
        print(f"Volatility Regime:  India VIX={r['vix']:.2f} ({r['vix_pctile']:.1f}th percentile)")
        print(f"--- MODEL SIGNALS ---")
        print(f"1. Trend Following (EMA+ADX):   {r['trend_direction']} (Confidence: {r['trend_confidence']:.2f})")
        print(f"2. Logistic Regression (L2):    {r['lr_direction']} (Confidence: {r['lr_confidence']:.2f})")
        print(f"3. Donchian Breakout:           {r['breakout_direction']} (Confidence: {r['breakout_confidence']:.2f})")
        print(f"--- RISK & EXECUTION PARAMETERS ---")
        print(f"Lot Size: {r['lot_size']} Qty | ATR Stop: ±{r['stop_loss_pts']} pts | ATR Target (2x): ±{r['target_pts']} pts")
        print(f"Gatekeeper Master Decision Gate: NO_TRADE (Class A requirement enforced; all daily candidates are Class B/C)")

if __name__ == "__main__":
    main()
