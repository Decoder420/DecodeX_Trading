"""Institutional-Grade Interactive 15-Minute Candlestick Charting Module.

Features:
- Plotly 15-minute Candlestick chart with EMA 21, EMA 50, and True Max Pain overlays.
- Live Buy/Sell signal markers mapped from Intraday Signal Log with rich hover tooltips.
- TradingView-style visual Risk-to-Reward (RR) shaded projection zones.
- Dual Spot + Option Premium risk translation labels.
- Gapless NSE market hours (rangebreaks) and dynamic right-axis Y auto-scaling.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from signals.engine import SignalState, TradePlan
from dashboard.tradingview_chart import build_tradingview_html, render_tradingview_chart


def generate_chart_uirevision(instrument: str, timeframe: str, expiry: Optional[str] = None) -> str:
    """Generate deterministic Plotly uirevision key incorporating instrument, timeframe, and expiry."""
    clean_inst = str(instrument).upper().strip()
    clean_tf = str(timeframe).lower().strip()
    clean_exp = str(expiry).upper().strip() if expiry else "CURRENT"
    return f"{clean_inst}_{clean_tf}_{clean_exp}_chart_state"


def calculate_tight_y_axis_bounds(
    df_candles: pd.DataFrame,
    trade_plan: Optional[TradePlan] = None,
    show_rr: bool = True,
    padding_pts: Optional[float] = None,
    active_session_only: bool = True,
    buffer_pct: float = 0.065,  # 6.5% buffer on top and bottom (5-8% requirement)
) -> tuple[float, float]:
    """Calculate tight Y-axis viewport bounds based on active session price action and risk/reward levels.
    
    Applies a dynamic 5-8% (default 6.5%) vertical buffer to highest high and lowest low to eliminate
    excessive headroom while ensuring candlestick wicks and reference levels are cleanly visible.
    """
    if df_candles is None or df_candles.empty:
        base = getattr(trade_plan, "spot_price", 22500.0) if trade_plan else 22500.0
        return (base - 100.0, base + 100.0)

    # Isolate active session candles if multi-day dataset is supplied
    df_target = df_candles
    if active_session_only and "timestamp" in df_candles.columns and not df_candles.empty:
        ts_s = pd.to_datetime(df_candles["timestamp"])
        latest_date = ts_s.dt.date.iloc[-1]
        session_mask = (ts_s.dt.date == latest_date)
        if session_mask.any():
            df_target = df_candles[session_mask]

    c_low = float(df_target["low"].min())
    c_high = float(df_target["high"].max())
    y_pts = [c_low, c_high]

    if show_rr and trade_plan and trade_plan.state != SignalState.NEUTRAL:
        y_pts.extend([trade_plan.stop_loss, trade_plan.target_1, trade_plan.target_2])

    span = max(y_pts) - min(y_pts)
    if padding_pts is not None:
        pad = float(padding_pts)
    else:
        # Dynamic 5-8% buffer on top and bottom
        pad = max(round(span * buffer_pct, 1), 18.0)

    y_min = min(y_pts) - pad
    y_max = max(y_pts) + pad
    return (round(y_min, 1), round(y_max, 1))


def build_15m_candlestick_figure(
    df_candles: pd.DataFrame,
    trade_plan: TradePlan,
    signal_log_df: pd.DataFrame,
    max_pain_strike: Optional[float] = None,
    atr_val: float = 120.0,
    ltp_change: float = 0.0,
    indicators_config: Optional[Dict[str, Any]] = None,
    instrument: str = "NIFTY",
    timeframe: str = "15m",
    expiry: Optional[str] = None,
    is_refresh: bool = False,
    **kwargs: Any,
) -> go.Figure:
    """Construct an institutional-grade dark-themed candlestick chart with full persistent overlays."""
    fig = go.Figure()

    if df_candles.empty:
        return fig

    cfg = indicators_config or {}
    instrument = cfg.get("instrument", instrument)
    timeframe = cfg.get("timeframe", timeframe)
    expiry = cfg.get("expiry", expiry)
    is_refresh = cfg.get("is_refresh", is_refresh)

    show_ema21 = cfg.get("show_ema21", True)
    show_ema50 = cfg.get("show_ema50", True)
    show_pain = cfg.get("show_pain", True)
    show_signals = cfg.get("show_signals", True)
    show_rr = cfg.get("show_rr", True)
    tick_time = cfg.get("tick_time", "Live")
    latency_ms = cfg.get("latency_ms", 12.0)
    source = cfg.get("source", "Angel One Live Feed")

    # Header Telemetry Annotation (optional in-canvas overlay; primary display in Streamlit caption)
    if cfg.get("show_canvas_telemetry", False):
        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.01, y=1.12,
            text=f"⏱️ <b>Last Tick:</b> {tick_time} | <b>Latency:</b> {latency_ms:.0f} ms | <b>Feed:</b> {source}",
            showarrow=False,
            font=dict(color="#00E5FF", size=11, family="monospace"),
            align="left",
        )

    # 1. Base Candlestick Trace
    fig.add_trace(
        go.Candlestick(
            x=df_candles["timestamp"],
            open=df_candles["open"],
            high=df_candles["high"],
            low=df_candles["low"],
            close=df_candles["close"],
            name="NIFTY",
            increasing_line_color="#00E676",
            increasing_fillcolor="rgba(0, 230, 118, 0.75)",
            decreasing_line_color="#FF5252",
            decreasing_fillcolor="rgba(255, 82, 82, 0.75)",
            whiskerwidth=0.7,
            showlegend=False,
        )
    )

    # 2. EMA 21 Overlay (High-Contrast Solid Cyan #00E5FF, width 2.5)
    if show_ema21 and "ema_21" in df_candles.columns:
        fig.add_trace(
            go.Scatter(
                x=df_candles["timestamp"],
                y=df_candles["ema_21"],
                mode="lines",
                name="EMA 21",
                line=dict(color="#00E5FF", width=2.5),
                hoverinfo="skip",
            )
        )

    # 3. EMA 50 Overlay (High-Contrast Solid Amber Orange #FF9100, width 2.2)
    if show_ema50 and "ema_50" in df_candles.columns:
        fig.add_trace(
            go.Scatter(
                x=df_candles["timestamp"],
                y=df_candles["ema_50"],
                mode="lines",
                name="EMA 50",
                line=dict(color="#FF9100", width=2.2),
                hoverinfo="skip",
            )
        )

    # 4. True Max Pain Strike Reference Line (Vivid Magenta Dotted with Top-Left Badge, yshift=10)
    if show_pain:
        pain_val = max_pain_strike or round(trade_plan.spot_price / 50.0) * 50.0
        fig.add_hline(
            y=pain_val,
            line=dict(color="#D500F9", width=2.0, dash="dot"),
            annotation_text=f"📌 True Max Pain: ₹{pain_val:,.0f}",
            annotation_position="top left",
            annotation_font=dict(color="#F3E5F5", size=10, family="monospace", weight="bold"),
            annotation_bgcolor="rgba(74, 20, 140, 0.85)",
            annotation_bordercolor="#D500F9",
            annotation_borderwidth=1,
            annotation_yshift=10,
            annotation_xshift=10,
        )

    # 5. Live Spot LTP Line (Dashed Green/Red with Bottom-Right Price Badge, yshift=-8)
    # Pinned to bottom-right opposite from Max Pain (top-left) to strictly prevent annotation collision
    ltp_color = "#00E676" if ltp_change >= 0 else "#FF5252"
    fig.add_hline(
        y=trade_plan.spot_price,
        line=dict(color=ltp_color, width=1.8, dash="dash"),
        annotation_text=f"⚡ LTP: ₹{trade_plan.spot_price:,.2f}",
        annotation_position="bottom right",
        annotation_font=dict(color="#FFFFFF", size=11, family="monospace", weight="bold"),
        annotation_bgcolor="rgba(0, 200, 83, 0.90)" if ltp_change >= 0 else "rgba(213, 0, 0, 0.90)",
        annotation_bordercolor=ltp_color,
        annotation_borderwidth=1,
        annotation_yshift=-8,
        annotation_xshift=-10,
    )

    # 6. Intraday Buy/Sell Signal Markers from Signal Log
    if show_signals and not signal_log_df.empty:
        buy_x, buy_y, buy_text, buy_hover = [], [], [], []
        sell_x, sell_y, sell_text, sell_hover = [], [], [], []
        neutral_x, neutral_y, neutral_hover = [], [], []

        candle_times = [
            t.tz_localize(None) if hasattr(t, "tz_localize") and t.tzinfo else t
            for t in pd.to_datetime(df_candles["timestamp"]).tolist()
        ]

        for _, row in signal_log_df.iterrows():
            ts_str = str(row.get("Timestamp", ""))
            if not ts_str:
                continue
            sig_ts = pd.to_datetime(ts_str)
            if hasattr(sig_ts, "tz_localize") and sig_ts.tzinfo:
                sig_ts = sig_ts.tz_localize(None)

            # Match to closest candle
            closest_idx = min(range(len(candle_times)), key=lambda i: abs(candle_times[i] - sig_ts))
            matched_candle = df_candles.iloc[closest_idx]
            c_ts = matched_candle["timestamp"]
            c_high = float(matched_candle["high"])
            c_low = float(matched_candle["low"])
            c_close = float(matched_candle["close"])

            sig_state = str(row.get("Signal", ""))
            strike = str(row.get("Strike", ""))
            trigger = str(row.get("Trigger", ""))
            conf = float(row.get("Confidence", 0.70)) * 100
            score = float(row.get("Score", 1.5))
            confluence = str(row.get("Confluence Drivers", trigger))

            hover_html = (
                f"<b>{sig_state}</b> ({strike})<br>"
                f"Time: {c_ts.strftime('%H:%M') if hasattr(c_ts, 'strftime') else c_ts}<br>"
                f"Spot: ₹{matched_candle['close']:,.1f}<br>"
                f"Confidence: {conf:.0f}% (Score: {score:+.2f})<br>"
                f"<i>Trigger:</i> {trigger}<br>"
                f"<i>Confluence:</i> {confluence}"
            )

            if "BUY" in sig_state or "CE" in sig_state:
                buy_x.append(c_ts)
                buy_y.append(c_low - (0.15 * atr_val))
                clean_strike = strike.replace(" CE", "").replace(" PE", "").strip()
                buy_text.append(f"BUY {clean_strike} CE" if clean_strike else "BUY CE")
                buy_hover.append(hover_html)
            elif "SELL" in sig_state or "PE" in sig_state:
                sell_x.append(c_ts)
                sell_y.append(c_high + (0.15 * atr_val))
                clean_strike = strike.replace(" CE", "").replace(" PE", "").strip()
                sell_text.append(f"BUY {clean_strike} PE" if clean_strike else "BUY PE")
                sell_hover.append(hover_html)
            else:
                neutral_x.append(c_ts)
                neutral_y.append(c_close)
                neutral_hover.append(hover_html)

        if buy_x:
            fig.add_trace(
                go.Scatter(
                    x=buy_x,
                    y=buy_y,
                    mode="markers",
                    name="BUY Signals",
                    marker=dict(symbol="triangle-up", size=13, color="#00E676", line=dict(width=1, color="#FFFFFF")),
                    hovertext=buy_hover,
                    hoverinfo="text",
                )
            )

        if sell_x:
            fig.add_trace(
                go.Scatter(
                    x=sell_x,
                    y=sell_y,
                    mode="markers",
                    name="SELL Signals",
                    marker=dict(symbol="triangle-down", size=13, color="#FF1744", line=dict(width=1, color="#FFFFFF")),
                    hovertext=sell_hover,
                    hoverinfo="text",
                )
            )

        if neutral_x:
            fig.add_trace(
                go.Scatter(
                    x=neutral_x,
                    y=neutral_y,
                    mode="markers",
                    name="Consolidation / Wait",
                    marker=dict(symbol="diamond", size=9, color="#FFD600"),
                    hovertext=neutral_hover,
                    hoverinfo="text",
                )
            )

    # 7. TradingView-Style Visual Risk-to-Reward (RR) Projection Zones
    # Extended forward by 12 bars (3 hours) from last active candle
    if show_rr and trade_plan.state != SignalState.NEUTRAL and not df_candles.empty:
        last_ts = pd.to_datetime(df_candles["timestamp"].iloc[-1])
        proj_start = pd.to_datetime(df_candles["timestamp"].iloc[max(0, len(df_candles) - 6)])
        proj_end = last_ts + timedelta(minutes=180)

        is_bullish = "BUY" in trade_plan.state.value

        # A. Entry Range Band (Gold/Blue semi-transparent band)
        fig.add_shape(
            type="rect",
            x0=proj_start,
            x1=proj_end,
            y0=trade_plan.entry_min,
            y1=trade_plan.entry_max,
            fillcolor="rgba(66, 165, 245, 0.16)",
            line=dict(color="#42A5F5", width=1, dash="dot"),
        )
        fig.add_annotation(
            x=proj_end,
            y=(trade_plan.entry_min + trade_plan.entry_max) / 2.0,
            text=f"ENTRY: ₹{trade_plan.entry_min:,.1f} – ₹{trade_plan.entry_max:,.1f}",
            showarrow=False,
            xanchor="left",
            font=dict(color="#90CAF9", size=10),
            bgcolor="rgba(13, 71, 161, 0.6)",
            bordercolor="#42A5F5",
            borderwidth=1,
        )

        if is_bullish:
            # Stop Loss Box (Red shaded, below entry)
            fig.add_shape(
                type="rect",
                x0=proj_start,
                x1=proj_end,
                y0=trade_plan.stop_loss,
                y1=trade_plan.entry_min,
                fillcolor="rgba(255, 75, 75, 0.16)",
                line=dict(color="#FF4B4B", width=1.5),
            )
            fig.add_annotation(
                x=proj_end,
                y=trade_plan.stop_loss,
                text=(
                    f"SL: ₹{trade_plan.stop_loss:,.1f} (-{trade_plan.stop_distance_pts:.1f} pts) | "
                    f"Risk: -₹{trade_plan.max_risk_inr:,.0f} | Opt SL: ₹{trade_plan.option_stop_loss:.1f}"
                ),
                showarrow=False,
                xanchor="left",
                font=dict(color="#FF8A80", size=10),
                bgcolor="rgba(183, 28, 28, 0.6)",
                bordercolor="#FF4B4B",
                borderwidth=1,
            )

            # Target 1 Box (Emerald green shaded, 1:1.5 RR)
            fig.add_shape(
                type="rect",
                x0=proj_start,
                x1=proj_end,
                y0=trade_plan.entry_max,
                y1=trade_plan.target_1,
                fillcolor="rgba(0, 200, 105, 0.14)",
                line=dict(color="#00C869", width=1, dash="dash"),
            )
            fig.add_annotation(
                x=proj_end,
                y=trade_plan.target_1,
                text=(
                    f"T1 (1:1.5 RR): ₹{trade_plan.target_1:,.1f} (+{trade_plan.target_1 - trade_plan.spot_price:,.1f} pts) | "
                    f"Opt T1: ₹{trade_plan.option_target_1:.1f}"
                ),
                showarrow=False,
                xanchor="left",
                font=dict(color="#B9F6CA", size=10),
                bgcolor="rgba(27, 94, 32, 0.6)",
                bordercolor="#00C869",
                borderwidth=1,
            )

            # Target 2 Box (Deeper green shaded, 1:2.5 RR)
            fig.add_shape(
                type="rect",
                x0=proj_start,
                x1=proj_end,
                y0=trade_plan.target_1,
                y1=trade_plan.target_2,
                fillcolor="rgba(0, 230, 118, 0.22)",
                line=dict(color="#00E676", width=1.5),
            )
            fig.add_annotation(
                x=proj_end,
                y=trade_plan.target_2,
                text=(
                    f"T2 (1:2.5 RR): ₹{trade_plan.target_2:,.1f} (+{trade_plan.target_2 - trade_plan.spot_price:,.1f} pts) | "
                    f"Opt T2: ₹{trade_plan.option_target_2:.1f}"
                ),
                showarrow=False,
                xanchor="left",
                font=dict(color="#69F0AE", size=10),
                bgcolor="rgba(0, 200, 83, 0.6)",
                bordercolor="#00E676",
                borderwidth=1,
            )

        else:
            # Bearish (Short / Put) setup: Stop Loss is above entry, Targets below entry
            fig.add_shape(
                type="rect",
                x0=proj_start,
                x1=proj_end,
                y0=trade_plan.entry_max,
                y1=trade_plan.stop_loss,
                fillcolor="rgba(255, 75, 75, 0.16)",
                line=dict(color="#FF4B4B", width=1.5),
            )
            fig.add_annotation(
                x=proj_end,
                y=trade_plan.stop_loss,
                text=(
                    f"SL: ₹{trade_plan.stop_loss:,.1f} (+{trade_plan.stop_distance_pts:.1f} pts) | "
                    f"Risk: -₹{trade_plan.max_risk_inr:,.0f} | Opt SL: ₹{trade_plan.option_stop_loss:.1f}"
                ),
                showarrow=False,
                xanchor="left",
                font=dict(color="#FF8A80", size=10),
                bgcolor="rgba(183, 28, 28, 0.6)",
                bordercolor="#FF4B4B",
                borderwidth=1,
            )

            # Target 1 Box (below entry)
            fig.add_shape(
                type="rect",
                x0=proj_start,
                x1=proj_end,
                y0=trade_plan.target_1,
                y1=trade_plan.entry_min,
                fillcolor="rgba(0, 200, 105, 0.14)",
                line=dict(color="#00C869", width=1, dash="dash"),
            )
            fig.add_annotation(
                x=proj_end,
                y=trade_plan.target_1,
                text=(
                    f"T1 (1:1.5 RR): ₹{trade_plan.target_1:,.1f} (-{trade_plan.spot_price - trade_plan.target_1:,.1f} pts) | "
                    f"Opt T1: ₹{trade_plan.option_target_1:.1f}"
                ),
                showarrow=False,
                xanchor="left",
                font=dict(color="#B9F6CA", size=10),
                bgcolor="rgba(27, 94, 32, 0.6)",
                bordercolor="#00C869",
                borderwidth=1,
            )

            # Target 2 Box (further below)
            fig.add_shape(
                type="rect",
                x0=proj_start,
                x1=proj_end,
                y0=trade_plan.target_2,
                y1=trade_plan.target_1,
                fillcolor="rgba(0, 230, 118, 0.22)",
                line=dict(color="#00E676", width=1.5),
            )
            fig.add_annotation(
                x=proj_end,
                y=trade_plan.target_2,
                text=(
                    f"T2 (1:2.5 RR): ₹{trade_plan.target_2:,.1f} (-{trade_plan.spot_price - trade_plan.target_2:,.1f} pts) | "
                    f"Opt T2: ₹{trade_plan.option_target_2:.1f}"
                ),
                showarrow=False,
                xanchor="left",
                font=dict(color="#69F0AE", size=10),
                bgcolor="rgba(0, 200, 83, 0.6)",
                bordercolor="#00E676",
                borderwidth=1,
            )

    # 8. Dynamic Range Bounds & Y-axis Auto-Scaling (1D, 3D, 5D, and ALL)
    # Ensure y-axis auto-scales dynamically to the highest high and lowest low of the currently selected
    # visible window (with a fixed 5–8% buffer on top and bottom).
    has_ts = not df_candles.empty and "timestamp" in df_candles.columns
    if has_ts:
        ts_s = pd.to_datetime(df_candles["timestamp"])
        unique_dates = sorted(ts_s.dt.date.unique())
        latest_date = unique_dates[-1]
        today_str = latest_date.strftime("%Y-%m-%d")

        # 1D Bounds (Active Session with 5-8% dynamic buffer)
        df_1d = df_candles[ts_s.dt.date == latest_date]
        y_min_1d, y_max_1d = calculate_tight_y_axis_bounds(
            df_1d, trade_plan, show_rr=show_rr, buffer_pct=0.065
        )
        x_1d_range = [f"{today_str} 09:15:00", f"{today_str} 15:30:00"]

        # 3D Bounds
        d3_dates = unique_dates[-3:] if len(unique_dates) >= 3 else unique_dates
        df_3d = df_candles[ts_s.dt.date.isin(d3_dates)]
        y_min_3d, y_max_3d = calculate_tight_y_axis_bounds(
            df_3d, trade_plan, show_rr=False, buffer_pct=0.065, active_session_only=False
        )
        x_3d_start = d3_dates[0].strftime("%Y-%m-%d")
        x_3d_range = [f"{x_3d_start} 09:15:00", f"{today_str} 15:30:00"]

        # 5D Bounds
        d5_dates = unique_dates[-5:] if len(unique_dates) >= 5 else unique_dates
        df_5d = df_candles[ts_s.dt.date.isin(d5_dates)]
        y_min_5d, y_max_5d = calculate_tight_y_axis_bounds(
            df_5d, trade_plan, show_rr=False, buffer_pct=0.065, active_session_only=False
        )
        x_5d_start = d5_dates[0].strftime("%Y-%m-%d")
        x_5d_range = [f"{x_5d_start} 09:15:00", f"{today_str} 15:30:00"]
    else:
        y_min_1d, y_max_1d = calculate_tight_y_axis_bounds(
            df_candles, trade_plan, show_rr=show_rr, buffer_pct=0.065
        )
        x_1d_range = None
        y_min_3d, y_max_3d = y_min_1d, y_max_1d
        x_3d_range = None
        y_min_5d, y_max_5d = y_min_1d, y_max_1d
        x_5d_range = None

    ui_key = generate_chart_uirevision(instrument, timeframe, expiry)

    # 9. Y-Axis Configuration (Dynamic 5-8% padding tightly framed to active session; user zoom preserved via uirevision)
    yaxis_config = dict(
        showgrid=True,
        gridcolor="#1F2430",
        side="right",
        fixedrange=False,
        color="#E0E0E0",
        tickformat=",.1f",
        range=[y_min_1d, y_max_1d],
        autorange=False,
    )

    # 10. X-Axis Configuration with Default 1D Viewport
    xaxis_config = dict(
        showgrid=True,
        gridcolor="#1F2430",
        rangeslider=dict(visible=False),
        rangebreaks=[
            dict(bounds=["sat", "mon"]),  # Hide weekends
            dict(bounds=[15.5, 9.25], pattern="hour"),  # Hide 15:30 to 09:15 IST
        ],
        tickformat="%H:%M",
        color="#9E9E9E",
    )
    if x_1d_range:
        xaxis_config["range"] = x_1d_range

    # 11. Interactive Dual-Axis Range Selector Buttons (1D, 3D, 5D, ALL)
    # Dynamically recalculates both X and Y axis bounds on click without page reload
    updatemenus = [
        dict(
            type="buttons",
            direction="right",
            active=0,
            x=1.0,
            xanchor="right",
            y=1.04,
            yanchor="bottom",
            bgcolor="#1E222D",
            bordercolor="#2A2E39",
            borderwidth=1,
            font=dict(color="#D1D4DC", size=11, family="monospace"),
            pad=dict(r=2, t=2, b=2, l=2),
            buttons=[
                dict(
                    label="1D",
                    method="relayout",
                    args=[{
                        "xaxis.range": x_1d_range,
                        "yaxis.range": [y_min_1d, y_max_1d],
                        "xaxis.autorange": False,
                        "yaxis.autorange": False,
                    }],
                ),
                dict(
                    label="3D",
                    method="relayout",
                    args=[{
                        "xaxis.range": x_3d_range,
                        "yaxis.range": [y_min_3d, y_max_3d],
                        "xaxis.autorange": False,
                        "yaxis.autorange": False,
                    }],
                ),
                dict(
                    label="5D",
                    method="relayout",
                    args=[{
                        "xaxis.range": x_5d_range,
                        "yaxis.range": [y_min_5d, y_max_5d],
                        "xaxis.autorange": False,
                        "yaxis.autorange": False,
                    }],
                ),
                dict(
                    label="ALL",
                    method="relayout",
                    args=[{
                        "xaxis.autorange": True,
                        "yaxis.autorange": True,
                    }],
                ),
            ],
        )
    ]

    # 12. Dark-Mode Layout & Persistent Viewport
    fig.update_layout(
        uirevision=ui_key,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        height=650,
        margin=dict(t=50, b=20, l=30, r=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="left",
            x=0.0,
            bgcolor="rgba(14, 17, 23, 0.8)",
            font=dict(size=11, color="#E0E0E0"),
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1A1F2C",
            font_size=12,
            font_family="monospace",
        ),
        xaxis=xaxis_config,
        yaxis=yaxis_config,
        updatemenus=updatemenus,
    )

    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[15.5, 9.25], pattern="hour"),
        ],
        rangeslider_visible=False,
    )

    return fig
