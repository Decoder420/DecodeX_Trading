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
    padding_pts: float = 30.0,
) -> tuple[float, float]:
    """Calculate tight Y-axis viewport bounds based on active price action and risk/reward levels."""
    if df_candles is None or df_candles.empty:
        base = getattr(trade_plan, "spot_price", 22500.0) if trade_plan else 22500.0
        return (base - 100.0, base + 100.0)
    
    c_low = float(df_candles["low"].min())
    c_high = float(df_candles["high"].max())
    y_pts = [c_low, c_high]
    if show_rr and trade_plan and trade_plan.state != SignalState.NEUTRAL:
        y_pts.extend([trade_plan.stop_loss, trade_plan.target_1, trade_plan.target_2])
    y_min = min(y_pts) - padding_pts
    y_max = max(y_pts) + padding_pts
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

    # Header Telemetry Annotation (Tick Time & Latency)
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.01, y=1.06,
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

    # 2. EMA 21 Overlay (Cyan dashed)
    if show_ema21 and "ema_21" in df_candles.columns:
        fig.add_trace(
            go.Scatter(
                x=df_candles["timestamp"],
                y=df_candles["ema_21"],
                mode="lines",
                name="EMA 21",
                line=dict(color="#00E5FF", width=1.5, dash="dash"),
                hoverinfo="skip",
            )
        )

    # 3. EMA 50 Overlay (Orange solid)
    if show_ema50 and "ema_50" in df_candles.columns:
        fig.add_trace(
            go.Scatter(
                x=df_candles["timestamp"],
                y=df_candles["ema_50"],
                mode="lines",
                name="EMA 50",
                line=dict(color="#FF9100", width=2.0),
                hoverinfo="skip",
            )
        )

    # 4. True Max Pain Strike Reference Line (Purple dotted)
    if show_pain:
        pain_val = max_pain_strike or round(trade_plan.spot_price / 50.0) * 50.0
        fig.add_hline(
            y=pain_val,
            line=dict(color="#B388FF", width=1.5, dash="dot"),
            annotation_text=f"True Max Pain: ₹{pain_val:,.0f}",
            annotation_position="top left",
            annotation_font=dict(color="#B388FF", size=11),
        )

    # 5. Live Spot LTP Line (Pulsing Green/Red)
    ltp_color = "#00E676" if ltp_change >= 0 else "#FF5252"
    fig.add_hline(
        y=trade_plan.spot_price,
        line=dict(color=ltp_color, width=1.2, dash="dash"),
        annotation_text=f"LTP: ₹{trade_plan.spot_price:,.2f}",
        annotation_position="bottom right",
        annotation_font=dict(color=ltp_color, size=12),
    )

    # 6. Intraday Buy/Sell Signal Markers from Signal Log
    if show_signals and not signal_log_df.empty:
        buy_x, buy_y, buy_text, buy_hover = [], [], [], []
        sell_x, sell_y, sell_text, sell_hover = [], [], [], []
        neutral_x, neutral_y, neutral_hover = [], [], []

        candle_times = pd.to_datetime(df_candles["timestamp"]).tolist()

        for _, row in signal_log_df.iterrows():
            ts_str = str(row.get("Timestamp", ""))
            if not ts_str:
                continue
            sig_ts = pd.to_datetime(ts_str)

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

            if "BUY" in sig_state:
                buy_x.append(c_ts)
                buy_y.append(c_low - (0.15 * atr_val))
                buy_text.append(f"BUY | {strike}")
                buy_hover.append(hover_html)
            elif "SELL" in sig_state:
                sell_x.append(c_ts)
                sell_y.append(c_high + (0.15 * atr_val))
                sell_text.append(f"SELL | {strike}")
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
                    mode="markers+text",
                    name="BUY Signals",
                    marker=dict(symbol="triangle-up", size=14, color="#00E676", line=dict(width=1, color="#FFFFFF")),
                    text=buy_text,
                    textposition="bottom center",
                    textfont=dict(color="#00E676", size=10, family="monospace"),
                    hovertext=buy_hover,
                    hoverinfo="text",
                )
            )

        if sell_x:
            fig.add_trace(
                go.Scatter(
                    x=sell_x,
                    y=sell_y,
                    mode="markers+text",
                    name="SELL Signals",
                    marker=dict(symbol="triangle-down", size=14, color="#FF1744", line=dict(width=1, color="#FFFFFF")),
                    text=sell_text,
                    textposition="top center",
                    textfont=dict(color="#FF1744", size=10, family="monospace"),
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

    # 8. Y-axis Framing (Tight framing around active price action & SL/TP bounds)
    y_min, y_max = calculate_tight_y_axis_bounds(df_candles, trade_plan, show_rr=show_rr)
    ui_key = generate_chart_uirevision(instrument, timeframe, expiry)

    yaxis_config = dict(
        showgrid=True,
        gridcolor="#1F2430",
        side="right",
        fixedrange=False,
        color="#E0E0E0",
        tickformat=",.1f",
    )
    if is_refresh:
        # On background fragment refresh, do NOT reapply tight bounds so user pan/zoom persists
        yaxis_config["autorange"] = True
    else:
        # On initial render or instrument/timeframe/expiry change, apply tight bounds
        yaxis_config["range"] = [y_min, y_max]

    # 9. Dark-Mode Layout & NSE Gapless Rangebreaks
    fig.update_layout(
        uirevision=ui_key,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        height=650,
        margin=dict(l=15, r=160, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(14, 17, 23, 0.8)",
            font=dict(size=11, color="#E0E0E0"),
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1A1F2C",
            font_size=12,
            font_family="monospace",
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="#1F2430",
            rangeslider=dict(visible=False),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=3, label="3D", step="day", stepmode="backward"),
                    dict(count=5, label="5D", step="day", stepmode="backward"),
                    dict(step="all", label="ALL"),
                ]),
                bgcolor="#1E222D",
                activecolor="#2962FF",
                font=dict(color="#D1D4DC", size=11),
                x=0.01,
                y=0.98,
            ),
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # Hide weekends
                dict(bounds=[15.5, 9.25], pattern="hour"),  # Hide non-trading hours: 15:30 to 09:15
            ],
            tickformat="%H:%M",
            color="#9E9E9E",
        ),
        yaxis=yaxis_config,
    )

    return fig
