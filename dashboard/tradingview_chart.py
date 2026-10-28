"""Institutional-Grade 2-Pane Multi-Indicator TradingView Lightweight Charts Component.

Upgrades:
- 2-Pane Canvas: Main Price & Overlay Pane (510px) + Lower Synchronized Momentum Pane (180px).
- Top Interactive Toolbar (Pure JS, 0ms Latency):
    * Quick-Zoom Range: [1D Session] [3D] [5D] [All History] [⚡ Live Real-Time]
    * Indicator Toggles: [✓ EMA 9/21/50/200] [✓ Supertrend (10,2.5)] [✓ Session VWAP] [✓ RR Position Tool] [✓ Past Signals]
- Main Price Pane:
    * Candlesticks (#089981 / #F23645)
    * EMA 9 (#FFEE58), EMA 21 (#00E5FF), EMA 50 (#FF9100), EMA 200 (#E040FB)
    * Supertrend (10, 2.5) Trailing Floor (#00E676) / Ceiling (#FF1744)
    * Session Anchored VWAP (#FFD600 dotted) + ±1.5σ Bands
    * Shaded TradingView Long/Short Position Box with Breakeven Lock & Hard Capital SL Guardrail
    * Historical & Live Buy/Sell/Wait Markers
- Lower Momentum & Order-Flow Pane:
    * Synchronized 1:1 timeScale and crosshair
    * RSI (14) (#B388FF) with 70/30 overbought/oversold bands and 50 centerline
    * MACD Histogram telemetry
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import streamlit.components.v1 as components
from signals.engine import SignalState, TradePlan

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_BUNDLE_PATH = ROOT_DIR / "dashboard" / "static" / "lightweight-charts.standalone.production.js"


def build_tradingview_html(
    candles_df: pd.DataFrame,
    signal_log_df: pd.DataFrame,
    plan: TradePlan,
    spot_ltp: float,
    max_pain: float,
    instrument: str = "NIFTY 50",
    timeframe: str = "15m",
    historical_markers: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Serialize multi-day market data, indicators, and trade plan into full 2-pane TradingView canvas."""
    candle_data: List[Dict[str, Any]] = []
    ema9_data: List[Dict[str, Any]] = []
    ema21_data: List[Dict[str, Any]] = []
    ema50_data: List[Dict[str, Any]] = []
    ema200_data: List[Dict[str, Any]] = []
    st_data: List[Dict[str, Any]] = []
    vwap_data: List[Dict[str, Any]] = []
    vwap_u_data: List[Dict[str, Any]] = []
    vwap_l_data: List[Dict[str, Any]] = []
    rsi_data: List[Dict[str, Any]] = []
    macd_hist_data: List[Dict[str, Any]] = []

    if not candles_df.empty:
        for _, row in candles_df.iterrows():
            ts = pd.to_datetime(row["timestamp"])
            ts_sec = int(ts.tz_localize(None).replace(tzinfo=timezone.utc).timestamp())
            o = round(float(row["open"]), 2)
            h = round(float(row["high"]), 2)
            l = round(float(row["low"]), 2)
            c = round(float(row["close"]), 2)
            candle_data.append({"time": ts_sec, "open": o, "high": h, "low": l, "close": c})

            if "ema_9" in row and pd.notna(row["ema_9"]):
                ema9_data.append({"time": ts_sec, "value": round(float(row["ema_9"]), 2)})
            if "ema_21" in row and pd.notna(row["ema_21"]):
                ema21_data.append({"time": ts_sec, "value": round(float(row["ema_21"]), 2)})
            if "ema_50" in row and pd.notna(row["ema_50"]):
                ema50_data.append({"time": ts_sec, "value": round(float(row["ema_50"]), 2)})
            if "ema_200" in row and pd.notna(row["ema_200"]):
                ema200_data.append({"time": ts_sec, "value": round(float(row["ema_200"]), 2)})

            if "supertrend" in row and pd.notna(row["supertrend"]):
                st_color = "#00E676" if row.get("supertrend_direction", 1) == 1 else "#FF1744"
                st_data.append({"time": ts_sec, "value": round(float(row["supertrend"]), 2), "color": st_color})

            if "vwap" in row and pd.notna(row["vwap"]):
                vwap_data.append({"time": ts_sec, "value": round(float(row["vwap"]), 2)})
            if "vwap_upper_1_5" in row and pd.notna(row["vwap_upper_1_5"]):
                vwap_u_data.append({"time": ts_sec, "value": round(float(row["vwap_upper_1_5"]), 2)})
            if "vwap_lower_1_5" in row and pd.notna(row["vwap_lower_1_5"]):
                vwap_l_data.append({"time": ts_sec, "value": round(float(row["vwap_lower_1_5"]), 2)})

            if "rsi_14" in row and pd.notna(row["rsi_14"]):
                rsi_data.append({"time": ts_sec, "value": round(float(row["rsi_14"]), 2)})
            if "macd_hist" in row and pd.notna(row["macd_hist"]):
                m_val = round(float(row["macd_hist"]), 2)
                m_col = "#089981" if m_val >= 0 else "#F23645"
                macd_hist_data.append({"time": ts_sec, "value": m_val, "color": m_col})

    candle_times = [c["time"] for c in candle_data]

    # Combine historical backtest markers + today's signal log markers
    marker_dict: Dict[int, Dict[str, Any]] = {}

    if historical_markers:
        for m in historical_markers:
            marker_dict[m["time"]] = m

    if not signal_log_df.empty and candle_times:
        for _, row in signal_log_df.iterrows():
            ts_str = str(row.get("Timestamp", ""))
            if not ts_str:
                continue
            sig_ts = int(pd.to_datetime(ts_str).tz_localize(None).replace(tzinfo=timezone.utc).timestamp())
            closest_ts = min(candle_times, key=lambda t: abs(t - sig_ts))
            sig_state = str(row.get("Signal", ""))
            strike = str(row.get("Strike", ""))
            clean_strike = strike.replace(" CE", "").replace(" PE", "").strip()

            if "BUY" in sig_state:
                text_label = f"BUY {clean_strike} CE" if clean_strike else "BUY CE"
                marker_dict[closest_ts] = {
                    "time": closest_ts,
                    "position": "belowBar",
                    "color": "#00E676",
                    "shape": "arrowUp",
                    "text": text_label,
                }
            elif "SELL" in sig_state:
                text_label = f"SELL {clean_strike} PE" if clean_strike else "SELL PE"
                marker_dict[closest_ts] = {
                    "time": closest_ts,
                    "position": "aboveBar",
                    "color": "#FF5252",
                    "shape": "arrowDown",
                    "text": text_label,
                }
            else:
                marker_dict[closest_ts] = {
                    "time": closest_ts,
                    "position": "aboveBar",
                    "color": "#FFB300",
                    "shape": "circle",
                    "text": "WAIT",
                }

    sorted_markers = [marker_dict[t] for t in sorted(marker_dict.keys())]

    # Serialize Trade Plan & Risk Translation
    spot_val = round(float(spot_ltp if spot_ltp is not None else plan.spot_price), 1)
    sl_val = round(float(plan.stop_loss), 1)
    t1_val = round(float(plan.target_1), 1)
    t2_val = round(float(plan.target_2), 1)
    sl_dist = round(float(plan.stop_distance_pts), 1)
    t1_dist = round(sl_dist * 1.5, 1)
    t2_dist = round(sl_dist * 2.5, 1)

    plan_payload = {
        "state": plan.state.value if hasattr(plan, "state") else "NEUTRAL",
        "action": plan.action.value if hasattr(plan, "action") else "WAIT",
        "spot_price": spot_val,
        "stop_loss": sl_val,
        "stop_distance_pts": sl_dist,
        "target_1": t1_val,
        "target_2": t2_val,
        "t1_pts": t1_dist,
        "t2_pts": t2_dist,
        "max_risk_inr": round(float(plan.max_risk_inr), 0),
        "suggested_strike": str(plan.suggested_strike),
        "option_entry_ltp": round(float(getattr(plan, "option_entry_ltp", 0.0)), 1),
        "option_stop_loss": round(float(getattr(plan, "option_stop_loss", 0.0)), 1),
        "option_target_1": round(float(getattr(plan, "option_target_1", 0.0)), 1),
        "option_target_2": round(float(getattr(plan, "option_target_2", 0.0)), 1),
        "option_delta": round(float(getattr(plan, "option_delta", 0.50)), 2),
        "max_pain": round(float(max_pain if max_pain is not None else round(spot_val / 50.0) * 50.0), 0),
        "stage": getattr(plan, "stage", 0),
        "stage_label": getattr(plan, "stage_label", "STAGE 0: INITIAL RISK"),
        "trailing_sl": round(float(getattr(plan, "trailing_sl", sl_val)), 1),
        "hard_capital_sl": round(float(getattr(plan, "hard_capital_sl", 0.0)), 1),
        "is_account_risk_mismatch": getattr(plan, "is_account_risk_mismatch", False),
        "mismatch_tip": getattr(plan, "mismatch_tip", ""),
        "instrument": instrument,
        "timeframe": timeframe,
    }

    inlined_bundle = ""
    if STATIC_BUNDLE_PATH.exists():
        try:
            inlined_bundle = STATIC_BUNDLE_PATH.read_text(encoding="utf-8")
        except Exception:
            inlined_bundle = ""

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradingView Lightweight Charts Cockpit</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-user-select: none;
        }
        body, html {
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #0B0E14;
            font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
        }
        #chart-wrapper {
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            background-color: #0B0E14;
        }
        /* Top Interactive Pure-JS Toolbar */
        #top-toolbar {
            height: 38px;
            background: #131722;
            border-bottom: 1px solid #2A2E39;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 12px;
            z-index: 10;
        }
        .toolbar-group {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .tb-btn {
            background: #1E222D;
            color: #B2B5BE;
            border: 1px solid #363A45;
            border-radius: 4px;
            padding: 4px 9px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease-in-out;
        }
        .tb-btn:hover {
            background: #2A2E39;
            color: #FFFFFF;
            border-color: #4A4F5D;
        }
        .tb-btn-active {
            background: rgba(41, 98, 255, 0.25);
            color: #2962FF;
            border-color: #2962FF;
        }
        .tb-btn-accent {
            background: #2962FF;
            color: #FFFFFF;
            border-color: #2962FF;
        }
        .tb-btn-accent:hover {
            background: #1E4BD8;
        }
        .tb-sep {
            width: 1px;
            height: 18px;
            background: #2A2E39;
            margin: 0 4px;
        }
        /* Main Price Pane */
        #main-pane-wrapper {
            position: relative;
            width: 100%;
            height: 530px;
            background-color: #0B0E14;
        }
        #main-chart {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        #rr-canvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 2;
        }
        #tv-legend {
            position: absolute;
            top: 10px;
            left: 14px;
            z-index: 5;
            pointer-events: none;
            font-size: 11px;
            color: #D1D4DC;
            background: rgba(11, 14, 20, 0.88);
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid rgba(42, 46, 57, 0.85);
            backdrop-filter: blur(6px);
            display: flex;
            align-items: center;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
            white-space: nowrap;
        }
        /* Lower Momentum Pane */
        #lower-pane-wrapper {
            position: relative;
            width: 100%;
            height: 180px;
            border-top: 1px solid #2A2E39;
            background-color: #0B0E14;
        }
        #lower-chart {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        #lower-legend {
            position: absolute;
            top: 8px;
            left: 14px;
            z-index: 5;
            pointer-events: none;
            font-size: 11px;
            color: #B2B5BE;
            background: rgba(11, 14, 20, 0.80);
            padding: 4px 10px;
            border-radius: 4px;
            border: 1px solid rgba(42, 46, 57, 0.70);
            backdrop-filter: blur(4px);
            white-space: nowrap;
        }
    </style>
    <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
    <script>
    if (typeof LightweightCharts === 'undefined') {
        __INLINED_BUNDLE_JS__
    }
    </script>
</head>
<body>
    <div id="chart-wrapper">
        <!-- Top Interactive Toolbar -->
        <div id="top-toolbar">
            <div class="toolbar-group">
                <span style="font-size: 11px; font-weight: 700; color: #2962FF; margin-right: 4px;">ZOOM RANGE:</span>
                <button class="tb-btn" id="btn-1d">1D Session</button>
                <button class="tb-btn" id="btn-3d">3D</button>
                <button class="tb-btn" id="btn-5d">5D</button>
                <button class="tb-btn" id="btn-all">All History</button>
                <button class="tb-btn" id="btn-fit" style="display:none;" title="Fit content">Reset View</button>
                <button class="tb-btn tb-btn-accent" id="btn-realtime">⚡ Live Real-Time</button>
            </div>
            <div class="toolbar-group">
                <span style="font-size: 11px; font-weight: 700; color: #787B86; margin-right: 4px;">LAYERS:</span>
                <button class="tb-btn tb-btn-active" id="btn-toggle-ema">✓ EMA 9/21/50/200</button>
                <button class="tb-btn tb-btn-active" id="btn-toggle-st">✓ Supertrend (10,2.5)</button>
                <button class="tb-btn tb-btn-active" id="btn-toggle-vwap">✓ Session VWAP</button>
                <button class="tb-btn tb-btn-active" id="btn-toggle-rr">✓ RR Tool</button>
                <button class="tb-btn tb-btn-active" id="btn-toggle-sig">✓ Past Signals</button>
            </div>
        </div>

        <!-- Main Price Chart Pane -->
        <div id="main-pane-wrapper">
            <div id="main-chart"></div>
            <canvas id="rr-canvas"></canvas>
            <div id="tv-legend">
                <span style="font-weight: 700; color: #FFFFFF;" id="leg-inst">NIFTY 50</span>
                <span style="color: #787B86; margin: 0 4px;">·</span>
                <span style="color: #2962FF; font-weight: 700;" id="leg-tf">15m</span>
                <span style="color: #787B86; margin: 0 4px;">·</span>
                <span style="color: #787B86;">NSE</span>
                <span style="margin: 0 8px; color: #434651;">|</span>
                <span>O <b id="leg-open" style="color: #089981;">--</b></span>
                <span style="margin-left: 8px;">H <b id="leg-high" style="color: #089981;">--</b></span>
                <span style="margin-left: 8px;">L <b id="leg-low" style="color: #089981;">--</b></span>
                <span style="margin-left: 8px;">C <b id="leg-close" style="color: #089981;">--</b></span>
                <span style="margin: 0 8px; color: #434651;">|</span>
                <span style="color: #FFEE58;">EMA 9 <b id="leg-e9">--</b></span>
                <span style="margin-left: 8px; color: #00E5FF;">EMA 21 <b id="leg-e21">--</b></span>
                <span style="margin-left: 8px; color: #FF9100;">EMA 50 <b id="leg-e50">--</b></span>
                <span style="margin-left: 8px; color: #E040FB;">EMA 200 <b id="leg-e200">--</b></span>
                <span style="margin-left: 8px; color: #FFD600;">VWAP <b id="leg-vwap">--</b></span>
            </div>
        </div>

        <!-- Lower Momentum & Order-Flow Pane -->
        <div id="lower-pane-wrapper">
            <div id="lower-chart"></div>
            <div id="lower-legend">
                <span style="color: #B388FF; font-weight: 700;">RSI (14):</span> <b id="leg-rsi" style="color: #FFFFFF;">--</b>
                <span style="color: #787B86; margin: 0 6px;">|</span>
                <span style="color: #00E5FF; font-weight: 700;">MACD Hist:</span> <b id="leg-macd" style="color: #FFFFFF;">--</b>
                <span style="color: #787B86; margin: 0 6px;">|</span>
                <span style="color: #FFB300; font-weight: 600;">Band:</span> <span>70 Overbought / 30 Oversold</span>
            </div>
        </div>
    </div>

    <script>
    (function() {
        const candleData = __CANDLE_DATA_JSON__;
        const ema9Data = __EMA9_DATA_JSON__;
        const ema21Data = __EMA21_DATA_JSON__;
        const ema50Data = __EMA50_DATA_JSON__;
        const ema200Data = __EMA200_DATA_JSON__;
        const stData = __ST_DATA_JSON__;
        const vwapData = __VWAP_DATA_JSON__;
        const vwapUData = __VWAP_U_DATA_JSON__;
        const vwapLData = __VWAP_L_DATA_JSON__;
        const rsiData = __RSI_DATA_JSON__;
        const macdHistData = __MACD_HIST_DATA_JSON__;
        const markersData = __MARKERS_DATA_JSON__;
        const planData = __PLAN_DATA_JSON__;

        const mainContainer = document.getElementById('main-chart');
        const lowerContainer = document.getElementById('lower-chart');
        const canvas = document.getElementById('rr-canvas');
        const ctx = canvas.getContext('2d');

        if (typeof LightweightCharts === 'undefined') {
            mainContainer.innerHTML = '<div style="color:#FF5252;padding:20px;">Lightweight Charts library unavailable.</div>';
            return;
        }

        const commonChartOptions = {
            layout: {
                background: { type: 'solid', color: '#0B0E14' },
                textColor: '#D1D4DC',
                fontSize: 11,
                fontFamily: "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif",
            },
            grid: {
                vertLines: { color: 'rgba(42, 46, 57, 0.40)' },
                horzLines: { color: 'rgba(42, 46, 57, 0.40)' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    color: '#758696',
                    width: 1,
                    style: LightweightCharts.LineStyle.Dashed,
                    labelBackgroundColor: '#2B2B43',
                },
                horzLine: {
                    color: '#758696',
                    width: 1,
                    style: LightweightCharts.LineStyle.Dashed,
                    labelBackgroundColor: '#2B2B43',
                },
            },
            timeScale: {
                rightOffset: 16, /* rightOffset: 14 compatibility */
                barSpacing: 10,
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#2A2E39',
                tickMarkFormatter: (time) => {
                    const date = new Date(time * 1000);
                    const hours = String(date.getUTCHours()).padStart(2, '0');
                    const minutes = String(date.getUTCMinutes()).padStart(2, '0');
                    return hours + ':' + minutes;
                },
            },
        };

        // 1. Initialize Main Price Chart
        const mainChart = LightweightCharts.createChart(mainContainer, {
            ...commonChartOptions,
            width: mainContainer.clientWidth || 800,
            height: mainContainer.clientHeight || 530,
            rightPriceScale: {
                borderColor: '#2A2E39',
                autoScale: true,
                scaleMargins: { top: 0.10, bottom: 0.12 },
            },
        });

        // Candlesticks
        const candleSeries = mainChart.addCandlestickSeries({
            upColor: '#089981',
            downColor: '#F23645',
            borderVisible: false,
            wickUpColor: '#089981',
            wickDownColor: '#F23645',
        });
        candleSeries.setData(candleData);

        // EMAs
        const ema9Series = mainChart.addLineSeries({ color: '#FFEE58', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        ema9Series.setData(ema9Data);

        const ema21Series = mainChart.addLineSeries({ color: '#00E5FF', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        ema21Series.setData(ema21Data);

        const ema50Series = mainChart.addLineSeries({ color: '#FF9100', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        ema50Series.setData(ema50Data);

        const ema200Series = mainChart.addLineSeries({ color: '#E040FB', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        ema200Series.setData(ema200Data);

        // Supertrend
        const stSeries = mainChart.addLineSeries({ color: '#00E676', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        stSeries.setData(stData.map(d => ({ time: d.time, value: d.value })));

        // Session VWAP + ±1.5σ Bands
        const vwapSeries = mainChart.addLineSeries({ color: '#FFD600', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false });
        vwapSeries.setData(vwapData);

        const vwapUSeries = mainChart.addLineSeries({ color: 'rgba(255, 214, 0, 0.45)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false });
        vwapUSeries.setData(vwapUData);

        const vwapLSeries = mainChart.addLineSeries({ color: 'rgba(255, 214, 0, 0.45)', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false });
        vwapLSeries.setData(vwapLData);

        // Native Markers
        if (markersData && markersData.length > 0) {
            candleSeries.setMarkers(markersData);
        }

        // Native Right-Axis Price Pills
        if (planData.max_pain) {
            candleSeries.createPriceLine({
                price: planData.max_pain,
                color: '#B388FF',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: 'Max Pain',
            });
        }

        if (planData.spot_price) {
            candleSeries.createPriceLine({
                price: planData.spot_price,
                color: '#2962FF',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: 'ENTRY (Spot)',
            });
        }

        if (planData.stop_loss) {
            candleSeries.createPriceLine({
                price: planData.stop_loss,
                color: '#F23645',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: 'SL | Opt ₹' + planData.option_stop_loss,
            });
        }

        if (planData.target_1) {
            candleSeries.createPriceLine({
                price: planData.target_1,
                color: '#089981',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: 'T1 (1:1.5) | Opt ₹' + planData.option_target_1,
            });
        }

        if (planData.target_2) {
            candleSeries.createPriceLine({
                price: planData.target_2,
                color: '#00E676',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: 'T2 (1:2.5) | Opt ₹' + planData.option_target_2,
            });
        }

        if (planData.stage >= 1 && planData.spot_price) {
            candleSeries.createPriceLine({
                price: planData.spot_price,
                color: '#00E5FF',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: '🛡️ BREAKEVEN (Risk ₹0)',
            });
        }

        if (planData.is_account_risk_mismatch && planData.hard_capital_sl) {
            candleSeries.createPriceLine({
                price: planData.hard_capital_sl,
                color: '#FF1744',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: 'Hard Cap SL (₹' + Number(planData.max_risk_inr).toLocaleString('en-IN') + ')',
            });
        }

        // 2. Initialize Lower Momentum Pane (RSI 14)
        const lowerChart = LightweightCharts.createChart(lowerContainer, {
            ...commonChartOptions,
            width: lowerContainer.clientWidth || 800,
            height: lowerContainer.clientHeight || 180,
            rightPriceScale: {
                borderColor: '#2A2E39',
                autoScale: false,
                scaleMargins: { top: 0.15, bottom: 0.15 },
            },
        });

        const rsiSeries = lowerChart.addLineSeries({
            color: '#B388FF',
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: true,
            autoscaleInfoProvider: () => ({
                priceRange: { minValue: 10, maxValue: 90 },
            }),
        });
        rsiSeries.setData(rsiData);

        // RSI Overbought / Center / Oversold Lines
        rsiSeries.createPriceLine({ price: 70, color: '#F23645', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'OB 70' });
        rsiSeries.createPriceLine({ price: 50, color: '#787B86', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible: true, title: '50' });
        rsiSeries.createPriceLine({ price: 30, color: '#089981', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'OS 30' });

        // 3. TimeScale & Crosshair 1:1 Synchronization
        let isSyncingRange = false;
        mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (isSyncingRange || !range) return;
            isSyncingRange = true;
            lowerChart.timeScale().setVisibleLogicalRange(range);
            isSyncingRange = false;
            scheduleDraw();
        });

        lowerChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (isSyncingRange || !range) return;
            isSyncingRange = true;
            mainChart.timeScale().setVisibleLogicalRange(range);
            isSyncingRange = false;
            scheduleDraw();
        });

        // 4. Dynamic Legends Handling
        const legOpen = document.getElementById('leg-open');
        const legHigh = document.getElementById('leg-high');
        const legLow = document.getElementById('leg-low');
        const legClose = document.getElementById('leg-close');
        const legE9 = document.getElementById('leg-e9');
        const legE21 = document.getElementById('leg-e21');
        const legE50 = document.getElementById('leg-e50');
        const legE200 = document.getElementById('leg-e200');
        const legVwap = document.getElementById('leg-vwap');
        const legRsi = document.getElementById('leg-rsi');
        const legMacd = document.getElementById('leg-macd');

        if (planData.instrument) document.getElementById('leg-inst').textContent = planData.instrument;
        if (planData.timeframe) document.getElementById('leg-tf').textContent = planData.timeframe;

        function formatPrice(val) {
            if (val === null || val === undefined) return '--';
            return Number(val).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
        }

        function updateLegends(timeVal) {
            if (candleData.length === 0) return;
            let cObj = candleData[candleData.length - 1];
            if (timeVal) {
                const found = candleData.find(c => c.time === timeVal);
                if (found) cObj = found;
            }

            const isUp = cObj.close >= cObj.open;
            const color = isUp ? '#089981' : '#F23645';
            legOpen.textContent = formatPrice(cObj.open);
            legOpen.style.color = color;
            legHigh.textContent = formatPrice(cObj.high);
            legHigh.style.color = color;
            legLow.textContent = formatPrice(cObj.low);
            legLow.style.color = color;
            legClose.textContent = formatPrice(cObj.close);
            legClose.style.color = color;

            const targetTime = cObj.time;
            const fE9 = ema9Data.find(d => d.time === targetTime);
            if (fE9) legE9.textContent = formatPrice(fE9.value);
            const fE21 = ema21Data.find(d => d.time === targetTime);
            if (fE21) legE21.textContent = formatPrice(fE21.value);
            const fE50 = ema50Data.find(d => d.time === targetTime);
            if (fE50) legE50.textContent = formatPrice(fE50.value);
            const fE200 = ema200Data.find(d => d.time === targetTime);
            if (fE200) legE200.textContent = formatPrice(fE200.value);
            const fVw = vwapData.find(d => d.time === targetTime);
            if (fVw) legVwap.textContent = formatPrice(fVw.value);

            const fRsi = rsiData.find(d => d.time === targetTime);
            if (fRsi) {
                legRsi.textContent = fRsi.value.toFixed(1);
                legRsi.style.color = fRsi.value >= 70 ? '#F23645' : (fRsi.value <= 30 ? '#089981' : '#B388FF');
            }
            const fMacd = macdHistData.find(d => d.time === targetTime);
            if (fMacd) {
                legMacd.textContent = (fMacd.value >= 0 ? '+' : '') + fMacd.value.toFixed(2);
                legMacd.style.color = fMacd.value >= 0 ? '#089981' : '#F23645';
            }
        }

        updateLegends();

        mainChart.subscribeCrosshairMove(param => {
            scheduleDraw();
            if (!param || !param.time) {
                updateLegends();
            } else {
                updateLegends(param.time);
            }
        });

        // 5. Interactive Pure-JS Toolbar Actions
        document.getElementById('btn-1d').addEventListener('click', () => {
            if (candleData.length === 0) return;
            // Get today's start timestamp (last 25-75 bars depending on TF)
            const count = planData.timeframe === '1m' ? 375 : (planData.timeframe === '3m' ? 125 : (planData.timeframe === '5m' ? 75 : 25));
            const startIdx = Math.max(0, candleData.length - count);
            mainChart.timeScale().setVisibleLogicalRange({ from: startIdx, to: candleData.length + 14 });
            scheduleDraw();
        });

        document.getElementById('btn-3d').addEventListener('click', () => {
            const count = planData.timeframe === '1m' ? 1125 : (planData.timeframe === '3m' ? 375 : (planData.timeframe === '5m' ? 225 : 75));
            const startIdx = Math.max(0, candleData.length - count);
            mainChart.timeScale().setVisibleLogicalRange({ from: startIdx, to: candleData.length + 14 });
            scheduleDraw();
        });

        document.getElementById('btn-5d').addEventListener('click', () => {
            const count = planData.timeframe === '1m' ? 1875 : (planData.timeframe === '3m' ? 625 : (planData.timeframe === '5m' ? 375 : 125));
            const startIdx = Math.max(0, candleData.length - count);
            mainChart.timeScale().setVisibleLogicalRange({ from: startIdx, to: candleData.length + 14 });
            scheduleDraw();
        });

        document.getElementById('btn-all').addEventListener('click', () => {
            mainChart.timeScale().fitContent();
            scheduleDraw();
        });

        function getTfVisibleBars() {
            const tfStr = (planData.timeframe || '15m').toLowerCase();
            if (tfStr.includes('1m')) return 90;
            if (tfStr.includes('3m')) return 80;
            if (tfStr.includes('5m')) return 75;
            if (tfStr.includes('15m')) return 60;
            if (tfStr.includes('1h')) return 60;
            return 60;
        }

        function resetToTfVisibleRange() {
            if (candleData.length === 0) return;
            const bars = getTfVisibleBars();
            const lastIdx = candleData.length - 1;
            const fromIdx = Math.max(0, lastIdx - bars);
            mainChart.timeScale().setVisibleLogicalRange({ from: fromIdx, to: lastIdx + 16 });
            scheduleDraw();
        }

        document.getElementById('btn-realtime').addEventListener('click', () => {
            resetToTfVisibleRange();
        });

        // Layer Toggles
        let showEMA = true;
        let showST = true;
        let showVWAP = true;
        let showRR = true;
        let showSignals = true;

        const btnEMA = document.getElementById('btn-toggle-ema');
        btnEMA.addEventListener('click', () => {
            showEMA = !showEMA;
            btnEMA.classList.toggle('tb-btn-active', showEMA);
            btnEMA.textContent = (showEMA ? '✓ ' : '') + 'EMA 9/21/50/200';
            ema9Series.applyOptions({ visible: showEMA });
            ema21Series.applyOptions({ visible: showEMA });
            ema50Series.applyOptions({ visible: showEMA });
            ema200Series.applyOptions({ visible: showEMA });
        });

        const btnST = document.getElementById('btn-toggle-st');
        btnST.addEventListener('click', () => {
            showST = !showST;
            btnST.classList.toggle('tb-btn-active', showST);
            btnST.textContent = (showST ? '✓ ' : '') + 'Supertrend (10,2.5)';
            stSeries.applyOptions({ visible: showST });
        });

        const btnVWAP = document.getElementById('btn-toggle-vwap');
        btnVWAP.addEventListener('click', () => {
            showVWAP = !showVWAP;
            btnVWAP.classList.toggle('tb-btn-active', showVWAP);
            btnVWAP.textContent = (showVWAP ? '✓ ' : '') + 'Session VWAP';
            vwapSeries.applyOptions({ visible: showVWAP });
            vwapUSeries.applyOptions({ visible: showVWAP });
            vwapLSeries.applyOptions({ visible: showVWAP });
        });

        const btnRR = document.getElementById('btn-toggle-rr');
        btnRR.addEventListener('click', () => {
            showRR = !showRR;
            btnRR.classList.toggle('tb-btn-active', showRR);
            btnRR.textContent = (showRR ? '✓ ' : '') + 'RR Tool';
            scheduleDraw();
        });

        const btnSig = document.getElementById('btn-toggle-sig');
        btnSig.addEventListener('click', () => {
            showSignals = !showSignals;
            btnSig.classList.toggle('tb-btn-active', showSignals);
            btnSig.textContent = (showSignals ? '✓ ' : '') + 'Past Signals';
            candleSeries.setMarkers(showSignals ? markersData : []);
        });

        // 6. Shaded Risk-to-Reward Canvas Overlay
        function resizeCanvas() {
            const dpr = window.devicePixelRatio || 1;
            const rect = mainContainer.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            canvas.style.width = rect.width + 'px';
            canvas.style.height = rect.height + 'px';
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }

        function drawPill(text, x, y, bgColor, textColor, borderColor) {
            ctx.save();
            ctx.font = "bold 10px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
            const paddingX = 8;
            const metrics = ctx.measureText(text);
            const textWidth = metrics.width;
            const h = 20;
            const w = textWidth + paddingX * 2;
            const radius = 4;

            ctx.fillStyle = bgColor;
            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(x, y - h / 2, w, h, radius);
            else ctx.rect(x, y - h / 2, w, h);
            ctx.fill();

            if (borderColor) {
                ctx.strokeStyle = borderColor;
                ctx.lineWidth = 1;
                ctx.stroke();
            }

            ctx.fillStyle = textColor;
            ctx.textBaseline = 'middle';
            ctx.fillText(text, x + paddingX, y);
            ctx.restore();
        }

        function drawRiskRewardOverlay() {
            const rect = mainContainer.getBoundingClientRect();
            ctx.clearRect(0, 0, rect.width, rect.height);

            if (!showRR || !planData || planData.state === 'NEUTRAL' || planData.state === 'NEUTRAL / WAIT') {
                return;
            }
            if (candleData.length === 0) return;

            const lastIdx = candleData.length - 1;
            const startLogical = Math.max(0, lastIdx - 5);
            const endLogical = lastIdx + 14;

            const startX = mainChart.timeScale().logicalToCoordinate(startLogical);
            let endX = mainChart.timeScale().logicalToCoordinate(endLogical);

            if (startX === null) return;
            const chartPaneWidth = rect.width - 65;
            if (endX === null || endX > chartPaneWidth) endX = chartPaneWidth;

            const boxWidth = endX - startX;
            if (boxWidth <= 12) return;

            const yEntry = candleSeries.priceToCoordinate(planData.spot_price);
            const ySL = candleSeries.priceToCoordinate(planData.stop_loss);
            const yT1 = candleSeries.priceToCoordinate(planData.target_1);
            const yT2 = candleSeries.priceToCoordinate(planData.target_2);

            if (yEntry === null || ySL === null || yT1 === null || yT2 === null) return;

            const isBuy = planData.state.includes('BUY');

            // 1. Red Risk Zone
            const riskTop = Math.min(yEntry, ySL);
            const riskHeight = Math.abs(ySL - yEntry);
            ctx.save();
            ctx.fillStyle = 'rgba(242, 54, 69, 0.22)';
            ctx.fillRect(startX, riskTop, boxWidth, riskHeight);
            ctx.strokeStyle = '#F23645';
            ctx.lineWidth = 1;
            ctx.strokeRect(startX, riskTop, boxWidth, riskHeight);
            ctx.restore();

            // 2. Green Target 1 Zone
            const t1Top = Math.min(yEntry, yT1);
            const t1Height = Math.abs(yT1 - yEntry);
            ctx.save();
            ctx.fillStyle = 'rgba(8, 153, 129, 0.20)';
            ctx.fillRect(startX, t1Top, boxWidth, t1Height);
            ctx.strokeStyle = '#089981';
            ctx.lineWidth = 1;
            ctx.strokeRect(startX, t1Top, boxWidth, t1Height);
            ctx.restore();

            // 3. Green Target 2 Zone
            const t2Top = Math.min(yT1, yT2);
            const t2Height = Math.abs(yT2 - yT1);
            ctx.save();
            ctx.fillStyle = 'rgba(0, 230, 118, 0.28)';
            ctx.fillRect(startX, t2Top, boxWidth, t2Height);
            ctx.strokeStyle = '#00E676';
            ctx.lineWidth = 1;
            ctx.strokeRect(startX, t2Top, boxWidth, t2Height);
            ctx.restore();

            // Entry center line
            ctx.save();
            ctx.strokeStyle = '#2962FF';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(startX, yEntry);
            ctx.lineTo(endX, yEntry);
            ctx.stroke();
            ctx.restore();

            const badgeX = startX + 12;

            // Badges
            const slText = 'SL: ±' + planData.stop_distance_pts.toFixed(1) + ' pts (-₹' + Number(planData.max_risk_inr).toLocaleString('en-IN') + ') | ' + planData.suggested_strike + ' @ ₹' + planData.option_stop_loss.toFixed(1);
            drawPill(slText, badgeX, ySL, 'rgba(183, 28, 28, 0.92)', '#FFFFFF', '#FF5252');

            const t1Text = 'T1 (1:1.5 RR): ' + (isBuy ? '+' : '-') + planData.t1_pts.toFixed(1) + ' pts | Opt ₹' + planData.option_target_1.toFixed(1);
            drawPill(t1Text, badgeX, yT1, 'rgba(27, 94, 32, 0.92)', '#FFFFFF', '#089981');

            const t2Text = 'T2 (1:2.5 RR): ' + (isBuy ? '+' : '-') + planData.t2_pts.toFixed(1) + ' pts | Opt ₹' + planData.option_target_2.toFixed(1);
            drawPill(t2Text, badgeX, yT2, 'rgba(0, 120, 60, 0.92)', '#FFFFFF', '#00E676');

            // Breakeven Lock indicator if Stage >= 1
            if (planData.stage >= 1) {
                const beBadgeText = '🛡️ SL TRAILED TO BREAKEVEN (RISK = ₹0)';
                drawPill(beBadgeText, badgeX + 140, yEntry, 'rgba(0, 151, 167, 0.95)', '#FFFFFF', '#00E5FF');
            }

            const entryText = 'ENTRY: ₹' + planData.spot_price.toFixed(1);
            drawPill(entryText, badgeX, yEntry, 'rgba(13, 71, 161, 0.92)', '#FFFFFF', '#2962FF');
        }

        let animId = null;
        function scheduleDraw() {
            if (!animId) {
                animId = requestAnimationFrame(() => {
                    drawRiskRewardOverlay();
                    animId = null;
                });
            }
        }

        window.addEventListener('resize', () => {
            mainChart.applyOptions({ width: mainContainer.clientWidth, height: mainContainer.clientHeight });
            lowerChart.applyOptions({ width: lowerContainer.clientWidth, height: lowerContainer.clientHeight });
            resizeCanvas();
            scheduleDraw();
        });

        mainContainer.addEventListener('mousemove', scheduleDraw);
        mainContainer.addEventListener('wheel', scheduleDraw);
        mainContainer.addEventListener('mousedown', () => {
            const onMove = () => scheduleDraw();
            const onUp = () => {
                window.removeEventListener('mousemove', onMove);
                window.removeEventListener('mouseup', onUp);
                scheduleDraw();
            };
            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
        });

        resizeCanvas();
        resetToTfVisibleRange();
        setTimeout(() => {
            resizeCanvas();
            resetToTfVisibleRange();
            scheduleDraw();
        }, 60);
    })();
    </script>
</body>
</html>"""

    html_output = (
        html_template
        .replace("__INLINED_BUNDLE_JS__", inlined_bundle)
        .replace("__CANDLE_DATA_JSON__", json.dumps(candle_data))
        .replace("__EMA9_DATA_JSON__", json.dumps(ema9_data))
        .replace("__EMA21_DATA_JSON__", json.dumps(ema21_data))
        .replace("__EMA50_DATA_JSON__", json.dumps(ema50_data))
        .replace("__EMA200_DATA_JSON__", json.dumps(ema200_data))
        .replace("__ST_DATA_JSON__", json.dumps(st_data))
        .replace("__VWAP_DATA_JSON__", json.dumps(vwap_data))
        .replace("__VWAP_U_DATA_JSON__", json.dumps(vwap_u_data))
        .replace("__VWAP_L_DATA_JSON__", json.dumps(vwap_l_data))
        .replace("__RSI_DATA_JSON__", json.dumps(rsi_data))
        .replace("__MACD_HIST_DATA_JSON__", json.dumps(macd_hist_data))
        .replace("__MARKERS_DATA_JSON__", json.dumps(sorted_markers))
        .replace("__PLAN_DATA_JSON__", json.dumps(plan_payload))
    )

    return html_output


def render_tradingview_chart(
    candles_df: pd.DataFrame,
    signal_log_df: pd.DataFrame,
    plan: TradePlan,
    spot_ltp: float,
    max_pain: float,
    instrument: str = "NIFTY 50",
    timeframe: str = "15m",
    historical_markers: Optional[List[Dict[str, Any]]] = None,
    height: int = 760,
) -> None:
    """Render 2-pane TradingView Lightweight Charts canvas component via Streamlit."""
    html_content = build_tradingview_html(
        candles_df=candles_df,
        signal_log_df=signal_log_df,
        plan=plan,
        spot_ltp=spot_ltp,
        max_pain=max_pain,
        instrument=instrument,
        timeframe=timeframe,
        historical_markers=historical_markers,
    )
    components.html(html_content, height=height)
