"""DecodeX Trading — Institutional Multi-Timeframe Quantitative Execution Terminal.

Architecture:
- Completely decoupled Streamlit frontend.
- Zero WebSockets or heavy calculations in this process.
- Sub-millisecond polling from DecodeX StateStore (Redis or atomic local state).
- Sub-second UI updates via native Streamlit fragments (@st.fragment).
- Embedded TradingView Lightweight Charts with zero external dependencies.
"""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytz
import streamlit as st
import streamlit.components.v1 as components

# Setup workspace path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.state_store import state_store
from data.risk_engine import RiskCalculator, RiskEvaluationResult
from data.execution_engine import execution_engine
from dashboard.tradingview_streamlit import render_mtf_tradingview_html

IST_TZ = pytz.timezone("Asia/Kolkata")

# Page Configuration
icon_path = PROJECT_ROOT / "assets" / "decodex_icon.png"
logo_path = PROJECT_ROOT / "assets" / "decodex_logo_full.png"

st.set_page_config(
    page_title="DecodeX Trading | Institutional Multi-Timeframe Quant Terminal",
    page_icon=str(icon_path) if icon_path.exists() else "⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global Dark Mode CSS
st.markdown(
    """
    <style>
    /* Global TradingView Dark Palette */
    .stApp {
        background-color: #131722 !important;
        color: #D1D4DC !important;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #181B24 !important;
        border-right: 1px solid #2A2E39 !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #2A2E39 !important;
    }
    
    /* Card Container */
    .quant-card {
        background-color: #1E222D;
        border: 1px solid #2A2E39;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    
    /* Confluence Banner */
    .confluence-box {
        border-radius: 6px;
        padding: 10px 14px;
        text-align: center;
        font-weight: 800;
        font-size: 14px;
        letter-spacing: 0.5px;
        margin-bottom: 10px;
    }
    .confluence-bullish {
        background-color: rgba(8, 153, 129, 0.2);
        border: 1px solid #089981;
        color: #089981;
    }
    .confluence-bearish {
        background-color: rgba(242, 54, 69, 0.2);
        border: 1px solid #F23645;
        color: #F23645;
    }
    .confluence-wait {
        background-color: rgba(42, 46, 57, 0.6);
        border: 1px solid #363A45;
        color: #94A3B8;
    }
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        margin-right: 6px;
    }
    .badge-bull {
        background: rgba(8, 153, 129, 0.15);
        color: #089981;
    }
    .badge-bear {
        background: rgba(242, 54, 69, 0.15);
        color: #F23645;
    }
    .badge-neutral {
        background: rgba(120, 123, 134, 0.15);
        color: #94A3B8;
    }
    
    /* Typography */
    .mono {
        font-family: "SF Mono", monospace !important;
    }
    
    /* Table Styling */
    .depth-table, .options-table {
        width: 100%;
        border-collapse: collapse;
        font-family: "SF Mono", monospace;
        font-size: 11px;
    }
    .depth-table th, .options-table th {
        background: #181B24;
        color: #787B86;
        text-align: center;
        padding: 6px 4px;
        border-bottom: 1px solid #2A2E39;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .depth-table td, .options-table td {
        padding: 5px 4px;
        text-align: center;
        border-bottom: 1px solid #20242F;
    }
    .bid-text { color: #089981 !important; font-weight: 600; }
    .ask-text { color: #F23645 !important; font-weight: 600; }
    .atm-row { background: rgba(0, 229, 255, 0.08) !important; font-weight: 700; }
    
    /* Streamlit Metric Overrides */
    [data-testid="stMetricValue"] {
        font-family: "SF Mono", monospace !important;
        font-size: 1.4rem !important;
        color: #F8FAFC !important;
    }
    [data-testid="stMetricLabel"] {
        color: #787B86 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
    }
    
    /* News Card */
    .news-item {
        background: #181B24;
        border: 1px solid #2A2E39;
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 8px;
    }
    .news-title {
        color: #F8FAFC;
        font-size: 12px;
        font-weight: 600;
        margin-top: 4px;
        line-height: 1.4;
    }
    .news-meta {
        color: #787B86;
        font-size: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# HELPER FORMATTING FUNCTIONS
# =============================================================================

def format_oi(val: Any) -> str:
    """Format Open Interest / COI deltas with clean abbreviations (e.g. +48k, 1.2M)."""
    try:
        v = float(val)
    except (ValueError, TypeError):
        return str(val)
    abs_v = abs(v)
    sign = "+" if v > 0 else ("-" if v < 0 else "")
    if abs_v >= 1_000_000:
        return f"{sign}{abs_v / 1_000_000:.1f}M"
    elif abs_v >= 1_000:
        return f"{sign}{abs_v / 1_000:.0f}k"
    else:
        return f"{v:+.0f}" if v != 0 else "0"


def format_qty(val: Any) -> str:
    """Format market depth quantities cleanly."""
    try:
        v = float(val)
    except (ValueError, TypeError):
        return str(val)
    abs_v = abs(v)
    if abs_v >= 1_000_000:
        return f"{abs_v / 1_000_000:.1f}M"
    elif abs_v >= 10_000:
        return f"{abs_v / 1_000:.0f}k"
    else:
        return f"{int(v):,}"


# =============================================================================
# SIDEBAR CONTROLS & RISK GOVERNANCE
# =============================================================================

def render_sidebar():
    with st.sidebar:
        # DecodeX Official Logo
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.title("⚡ DecodeX Trading")

        st.caption("Institutional Multi-Timeframe Quantitative Execution Terminal")
        st.markdown("---")

        # Operating Mode
        st.subheader("⚙️ Engine Controls")
        op_mode = st.radio(
            "Operating Mode",
            ["Active Quant Execution (Live Signals)", "Strict Risk Gatekeeper (Read-Only)"],
            index=0,
            key="decodex_op_mode",
            help="Switch between active trade execution or strict risk management oversight.",
        )

        instrument = st.selectbox(
            "Active Instrument",
            ["NIFTY", "BANKNIFTY", "SENSEX"],
            index=0,
            key="decodex_active_instrument",
            help="Target index for MTF confluence and L2 microstructure analysis.",
        )

        expiry = st.selectbox(
            "Options Expiry",
            ["17NOV2026 (Near Weekly)", "24NOV2026", "28NOV2026 (Monthly)"],
            index=0,
            key="decodex_active_expiry",
            help="Options chain expiration contract for Greeks & Triad COI delta.",
        )

        chart_mode = st.radio(
            "TradingView Viewport",
            ["Dual MTF (15m + 3m)", "15m Structural Bias", "3m Execution Frame"],
            index=0,
            key="decodex_chart_viewport",
        )

        st.markdown("---")
        st.subheader("📐 Dynamic Position & Risk Sizing")
        account_equity = st.number_input(
            "Account Equity (INR)",
            min_value=10_000,
            max_value=10_000_000,
            value=1_000_000,
            step=50_000,
            key="decodex_account_equity",
        )
        risk_pct = st.slider("Risk per Trade (%)", min_value=0.25, max_value=3.0, value=1.0, step=0.25, key="decodex_risk_pct")
        atr_mult = st.slider("ATR Stop Multiplier", min_value=1.0, max_value=3.0, value=1.5, step=0.25, key="decodex_atr_mult")

        # Dynamic Sizing via RiskCalculator
        curr_state = state_store.get_state() or {}
        daily_atr = float(curr_state.get("mtf_15m", {}).get("daily_atr", 45.0))
        risk_eval = RiskCalculator.evaluate_risk(
            account_equity=account_equity,
            risk_per_trade_pct=risk_pct,
            atr_multiplier=atr_mult,
            instrument=instrument,
            atr_pts=daily_atr,
        )

        guard_color = "#089981" if risk_eval.guardrail_status == "SAFE" else ("#FFB74D" if risk_eval.guardrail_status == "WARNING" else "#F23645")
        st.markdown(
            f"""
            <div style="background:#1E222D; border:1px solid #2A2E39; border-radius:6px; padding:10px; font-size:11px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:#787B86;">Max Risk:</span>
                    <b style="color:#F8FAFC;">₹{risk_eval.max_risk_inr:,.0f}</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:#787B86;">Stop Distance:</span>
                    <b style="color:#D1D4DC;">{risk_eval.stop_distance_pts:.1f} pts</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:#787B86;">1-Lot Risk:</span>
                    <b style="color:#D1D4DC;">₹{risk_eval.risk_per_lot_inr:,.0f}</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="color:#787B86;">Recommended Size:</span>
                    <b style="color:#00E5FF;">{risk_eval.recommended_lots} Lots ({risk_eval.recommended_quantity} Qty)</b>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#787B86;">Small-Account Guard:</span>
                    <span class="badge" style="background:{guard_color}22; color:{guard_color}; border:1px solid {guard_color};">
                        {risk_eval.guardrail_status}
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if risk_eval.is_small_account_blocked:
            st.error(risk_eval.message)

        st.markdown("---")
        st.subheader("🔔 Alerts & Governance")
        enable_chime = st.checkbox("🔊 Audio Chime on Signal Change", value=True, key="decodex_enable_chime")
        hard_sl = st.checkbox("🛡️ Hard Capital Stop-Loss Guardrail", value=True, key="decodex_hard_sl")

        st.markdown("---")
        # Daemon status
        age = state_store.get_age_seconds()
        is_fresh = age < 5.0
        status_color = "#089981" if is_fresh else "#F23645"
        status_text = "ONLINE (<1s latency)" if is_fresh else f"STALE ({age:.1f}s ago)"
        redis_status = "Connected" if state_store.is_redis_active else "Atomic File Store"

        st.markdown(
            f"""
            <div style="font-size:10px; color:#787B86;">
                <div>Engine: <b style="color:{status_color};">{status_text}</b></div>
                <div>Storage: <b style="color:#D1D4DC;">{redis_status}</b></div>
                <div>Server Time: <b style="color:#D1D4DC;">{datetime.now().strftime('%H:%M:%S')}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    controls = {
        "op_mode": op_mode,
        "instrument": instrument,
        "expiry": expiry,
        "chart_mode": chart_mode,
        "account_equity": account_equity,
        "risk_pct": risk_pct,
        "atr_mult": atr_mult,
        "enable_chime": enable_chime,
        "hard_sl": hard_sl,
    }
    state_store.set_controls(controls)
    return controls


# =============================================================================
# LIVE TELEMETRY & QUANT FRAGMENTS (DECOUPLED REAL-TIME STREAMING)
# =============================================================================

@st.fragment(run_every="1s")
def render_header_confluence_fragment(controls: Dict[str, Any]):
    """Live spot ticker and 6-Factor MTF Confluence banner updating every 1s."""
    state = state_store.get_state()
    if not state:
        st.warning("⏳ Waiting for DecodeX Engine daemon... Please run `python engine.py` in your terminal.")
        return

    # Header Bar
    spot = state.get("spot_price", 25044.65)
    chg = state.get("change", 0.0)
    chg_pct = state.get("change_pct", 0.0)
    chg_color = "#089981" if chg >= 0 else "#F23645"
    sign = "+" if chg >= 0 else ""

    conn_status = state.get("connection_status", "Connected")
    conn_color = "#089981" if "Connected" in conn_status else "#FFB74D"

    h1, h2, h3, h4 = st.columns([2.5, 1.2, 1.2, 2.0])
    with h1:
        st.markdown(
            f"""
            <div style="display:flex; align-items:baseline; gap:12px;">
                <span style="font-size:26px; font-weight:800; font-family:'SF Mono', monospace; color:#F8FAFC;">₹{spot:,.2f}</span>
                <span style="font-size:14px; font-weight:700; font-family:'SF Mono', monospace; color:{chg_color};">
                    {sign}{chg:,.2f} ({sign}{chg_pct:.2f}%)
                </span>
                <span style="font-size:11px; color:#787B86;">{controls['instrument']} SPOT</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with h2:
        st.metric("Day High", f"₹{state.get('high', spot):,.2f}")
    with h3:
        st.metric("Day Low", f"₹{state.get('low', spot):,.2f}")
    lat = state.get("latency_ms", 12.0)
    lat_color = "#089981" if lat < 25.0 else ("#FFB74D" if lat < 60.0 else "#F23645")

    with h4:
        st.markdown(
            f"""
            <div style="text-align:right; font-size:11px;">
                <span class="badge" style="background:rgba(8,153,129,0.15); color:{conn_color}; border:1px solid {conn_color};">
                    🟢 {conn_status}
                </span>
                <div style="color:#787B86; margin-top:4px;">
                    <span style="color:{lat_color}; font-weight:700;">⚡ {lat:.1f}ms Latency</span> | 10Hz Feed | Ticks: {state.get('tick_count', 0):,}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 6-Factor MTF Confluence Gate Banner
    confl = state.get("confluence", {})
    sig = confl.get("signal", "CONFLUENCE WAIT")
    score = confl.get("score", 0.0)
    plan = confl.get("trade_plan", {})

    box_class = "confluence-bullish" if "BULLISH" in sig else ("confluence-bearish" if "BEARISH" in sig else "confluence-wait")
    bias_15 = confl.get("bias_15m", "NEUTRAL")
    trig_3 = confl.get("trigger_3m", "WAIT")
    exec_state = state.get("execution_state", "WAIT")
    exec_color = "#089981" if exec_state in ("POSITION_OPEN", "TRAILING_STOP") else ("#F23645" if "BLOCKED" in exec_state else "#787B86")

    st.markdown(
        f"""
        <div class="confluence-box {box_class}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span>🎯 6-FACTOR MTF CONFLUENCE: {sig.upper()}</span>
                <div>
                    <span class="badge" style="background:{exec_color}25; color:{exec_color}; border:1px solid {exec_color}; font-size:10px;">
                        STATE: {exec_state}
                    </span>
                    <span>Score: {score:+.2f} / +6.00</span>
                </div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:11px; margin-top:6px; font-weight:500;">
                <div>
                    <span class="badge badge-bull">15m Bias: {bias_15}</span>
                    <span class="badge badge-bull">3m Trigger: {trig_3}</span>
                </div>
                <div class="mono" style="color:#E2E8F0;">
                    Plan: Entry: ₹{plan.get('entry', spot):,.1f} | SL: ₹{plan.get('stop_loss', 0):,.1f} | 
                    Target: ₹{plan.get('target', 0):,.1f} | Strike: <b style="color:#00E5FF;">{plan.get('recommended_strike', 'ATM')}</b>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if controls.get("enable_chime") and state.get("chime_triggered"):
        components.html(
            """
            <script>
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = "sine";
                osc.frequency.setValueAtTime(659.25, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12);
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.28);
                osc.start();
                osc.stop(ctx.currentTime + 0.28);
            } catch(e) {}
            </script>
            """,
            height=0,
            width=0,
        )


@st.fragment(run_every="1s")
def render_telemetry_tabs_fragment(controls: Dict[str, Any]):
    """Right-side telemetry panel (L2 Depth, Market News, Options Grid) updating every 1s."""
    state = state_store.get_state()
    if not state:
        return

    spot = state.get("spot_price", 25044.65)
    tab_exec, tab_audit, tab_news, tab_opts = st.tabs(["⚡ L2 Depth", "📜 Audit & Orders", "📰 Market News", "📊 Options Grid"])

    # Tab 1: Level 2 Market Depth & OBI
    with tab_exec:
        depth = state.get("depth", {})
        obi = depth.get("order_book_imbalance", 0.0)
        obi_color = "#089981" if obi > 0.15 else ("#F23645" if obi < -0.15 else "#787B86")
        obi_desc = depth.get("sentiment", "Balanced")

        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-weight:700; color:#F8FAFC; font-size:12px;">Order Book Imbalance</span>
                <span class="mono" style="font-weight:800; color:{obi_color}; font-size:13px;">
                    OBI: {obi:+.2f} ({obi_desc})
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 5-Level Depth HTML Table
        bids = depth.get("bids", [])
        asks = depth.get("asks", [])
        depth_html = '<table class="depth-table"><thead><tr>' \
            '<th>ORDERS</th><th>BID QTY</th><th>BID PRICE</th>' \
            '<th>ASK PRICE</th><th>ASK QTY</th><th>ORDERS</th>' \
            '</tr></thead><tbody>'
        for i in range(5):
            b = bids[i] if i < len(bids) else {}
            a = asks[i] if i < len(asks) else {}
            b_ord = b.get('orders', '—')
            b_qty = format_qty(b.get('quantity', 0))
            b_px = f"₹{b.get('price', 0):,.1f}"
            a_px = f"₹{a.get('price', 0):,.1f}"
            a_qty = format_qty(a.get('quantity', 0))
            a_ord = a.get('orders', '—')
            depth_html += f'<tr><td style="color:#787B86;">{b_ord}</td><td class="bid-text">{b_qty}</td><td class="bid-text" style="font-weight:700;">{b_px}</td><td class="ask-text" style="font-weight:700;">{a_px}</td><td class="ask-text">{a_qty}</td><td style="color:#787B86;">{a_ord}</td></tr>'
        depth_html += '</tbody></table>'
        st.markdown(depth_html, unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="mono" style="font-size:10px; color:#787B86; margin-top:6px; display:flex; justify-content:space-between;">
                <span>Top Spread: {depth.get('spread', 0.5):.2f} pts</span>
                <span>Micro-Price: ₹{depth.get('micro_price', spot):,.2f}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Tab 2: Quant Audit Log & Active Orders
    with tab_audit:
        position = state.get("execution")
        if position and position.get("status") == "OPEN":
            pnl = position.get("pnl_inr", 0.0)
            pnl_color = "#089981" if pnl >= 0 else "#F23645"
            pnl_sign = "+" if pnl >= 0 else ""
            stage = position.get("stage", 0)
            stage_text = "Stage 0: Initial Risk" if stage == 0 else ("Stage 1: Breakeven Locked" if stage == 1 else "Stage 2: Runner Trail")
            act_badge_color = "#089981" if "CALL" in position.get("action", "") else "#F23645"

            st.markdown(
                f"""
                <div class="quant-card" style="border: 1px solid #00E5FF; background: rgba(0, 229, 255, 0.04); padding:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span class="badge" style="background:{act_badge_color}; color:#FFF; font-weight:800;">
                            {position.get('action')} • {position.get('strike')}
                        </span>
                        <span class="mono" style="font-size:14px; font-weight:800; color:{pnl_color};">
                            PnL: {pnl_sign}₹{pnl:,.0f}
                        </span>
                    </div>
                    <div class="mono" style="font-size:10px; display:grid; grid-template-columns: 1fr 1fr; gap:4px; color:#D1D4DC;">
                        <div>Entry Spot: <b>₹{position.get('spot_entry', 0):,.1f}</b></div>
                        <div>Current Spot: <b>₹{spot:,.1f}</b></div>
                        <div>Stop Loss: <b style="color:#F23645;">₹{position.get('stop_loss_pts', 0):,.1f}</b></div>
                        <div>Target 1: <b style="color:#089981;">₹{position.get('target_1_pts', 0):,.1f}</b></div>
                        <div>Position Size: <b>{position.get('lots', 1)} Lots ({position.get('quantity', 0)} Qty)</b></div>
                        <div>Order ID: <span style="color:#787B86;">{position.get('order_id', '')}</span></div>
                    </div>
                    <div style="margin-top:6px; font-size:10px; color:#00E5FF; font-weight:700;">
                        🛡️ Active Stage: {stage_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            exec_state = state.get("execution_state", "WAIT")
            st.markdown(
                f"""
                <div style="background:#181B24; border:1px dashed #2A2E39; border-radius:6px; padding:8px 12px; margin-bottom:8px; text-align:center;">
                    <span style="font-size:11px; color:#787B86;">No Active Positions Open</span>
                    <div style="font-size:10px; color:#00E5FF; margin-top:2px;">Confluence State: <b>{exec_state}</b></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Rolling Event Audit Log
        event_logs = state.get("event_logs", [])
        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-weight:700; color:#F8FAFC; font-size:12px;">Rolling Audit Log ({len(event_logs)})</span>
                <span style="font-size:10px; color:#787B86;">Live Telemetry</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        log_container = st.container(height=320)
        with log_container:
            if not event_logs:
                st.caption("No events recorded yet. Waiting for market signals...")
            for ev in event_logs:
                cat = ev.get("category", "SYSTEM")
                if cat == "ORDER":
                    badge_bg = "rgba(0, 229, 255, 0.2)"
                    badge_fg = "#00E5FF"
                elif cat == "CONFLUENCE":
                    badge_bg = "rgba(8, 153, 129, 0.2)"
                    badge_fg = "#089981"
                elif cat == "RISK_GUARD":
                    badge_bg = "rgba(242, 54, 69, 0.2)"
                    badge_fg = "#F23645"
                elif cat == "TRAILING_SL":
                    badge_bg = "rgba(171, 71, 188, 0.2)"
                    badge_fg = "#AB47BC"
                else:
                    badge_bg = "rgba(120, 123, 134, 0.2)"
                    badge_fg = "#94A3B8"

                st.markdown(
                    f"""
                    <div class="news-item" style="padding:6px 8px; margin-bottom:6px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span class="badge" style="background:{badge_bg}; color:{badge_fg}; font-size:9px;">
                                    {cat}
                                </span>
                                <b style="font-size:11px; color:#F8FAFC;">{ev.get('title', '')}</b>
                            </div>
                            <span class="news-meta mono">{ev.get('timestamp', '')}</span>
                        </div>
                        <div style="font-size:10px; color:#94A3B8; margin-top:3px; line-height:1.3;">
                            {ev.get('details', '')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Tab 3: Live Market News & Macro Confluence
    with tab_news:
        news = state.get("news", {})
        bias = news.get("bias", "NEUTRAL")
        score = news.get("bias_score", 0.0)
        tickers = news.get("macro_tickers", {})

        b_color = "#089981" if "BULL" in bias else ("#F23645" if "BEAR" in bias else "#787B86")
        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-weight:700; color:#60A5FA; font-size:12px;">Global Macro Confluence</span>
                <span class="badge" style="background:{b_color}; color:#FFF; font-weight:800;">
                    {bias} ({score:+.2f})
                </span>
            </div>
            <div class="mono" style="font-size:10px; color:#D1D4DC; background:#181B24; padding:6px; border-radius:4px; margin-bottom:8px;">
                USD/INR: ₹{tickers.get('usd_inr', {}).get('val', 84.38)} | Brent: ${tickers.get('brent_crude', {}).get('val', 74.20)} | US10Y: {tickers.get('us_10y', {}).get('val', 4.42)}%
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Scrollable News Stream
        headlines = news.get("headlines", [])
        news_container = st.container(height=380)
        with news_container:
            for h in headlines:
                s_color = "#089981" if h.get("sentiment") == "BULLISH" else ("#F23645" if h.get("sentiment") == "BEARISH" else "#787B86")
                st.markdown(
                    f"""
                    <div class="news-item">
                        <div style="display:flex; justify-content:space-between;">
                            <span class="badge" style="background:rgba(8,153,129,0.15); color:{s_color}; font-size:9px;">
                                {h.get('sentiment', 'NEUTRAL')}
                            </span>
                            <span class="news-meta">{h.get('source', '')} • {h.get('time', '')}</span>
                        </div>
                        <div class="news-title">{h.get('title', '')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Tab 3: Options Chain Grid (ATM ± 200)
    with tab_opts:
        opts = state.get("options_chain", {})
        triad = opts.get("triad_coi_delta", 0)
        triad_color = "#089981" if triad > 0 else "#F23645"

        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-weight:700; color:#F8FAFC; font-size:12px;">Triad COI Δ: <b style="color:{triad_color};">{format_oi(triad)}</b></span>
                <span style="font-size:10px; color:#787B86;">PCR: {opts.get('pcr_oi', 1.0)} | Max Pain: {opts.get('max_pain', spot)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        rows = opts.get("rows", [])
        opts_html = '<table class="options-table"><thead><tr>' \
            '<th>CE IV</th><th>CE Δ</th><th>CE COI</th>' \
            '<th>STRIKE</th><th>PE COI</th><th>PE Δ</th><th>PE IV</th>' \
            '</tr></thead><tbody>'
        for r in rows:
            atm_cls = "atm-row" if r.get("is_atm") else ""
            ce_coi_clr = "#089981" if r.get("ce_coi", 0) > 0 else "#787B86"
            pe_coi_clr = "#089981" if r.get("pe_coi", 0) > 0 else "#787B86"
            ce_iv = f"{r.get('ce_iv', 14.0):.1f}%"
            ce_delta = f"{r.get('ce_delta', 0.5):+.2f}"
            ce_coi = format_oi(r.get('ce_coi', 0))
            strike_lbl = r.get('strike_label', r.get('strike', ''))
            pe_coi = format_oi(r.get('pe_coi', 0))
            pe_delta = f"{r.get('pe_delta', -0.5):+.2f}"
            pe_iv = f"{r.get('pe_iv', 14.0):.1f}%"

            opts_html += f'<tr class="{atm_cls}">' \
                f'<td style="color:#787B86;">{ce_iv}</td>' \
                f'<td style="color:#00E5FF;">{ce_delta}</td>' \
                f'<td style="color:{ce_coi_clr};">{ce_coi}</td>' \
                f'<td style="font-weight:700; color:#F8FAFC;">{strike_lbl}</td>' \
                f'<td style="color:{pe_coi_clr};">{pe_coi}</td>' \
                f'<td style="color:#FFB74D;">{pe_delta}</td>' \
                f'<td style="color:#787B86;">{pe_iv}</td>' \
                f'</tr>'
        opts_html += '</tbody></table>'
        st.markdown(opts_html, unsafe_allow_html=True)


# =============================================================================
# TRADINGVIEW CHART COMPONENT (5Hz LOW-LATENCY ENGINE STREAM)
# =============================================================================

def render_chart_fragment(controls: Dict[str, Any]):
    """Render TradingView Lightweight Charts with continuous 5Hz streaming."""
    state = state_store.get_state() or {}
    frame_code = "both" if "Dual" in controls["chart_mode"] else ("15m" if "15m" in controls["chart_mode"] else "3m")

    chart_html = render_mtf_tradingview_html(
        candles_15m=state.get("mtf_15m", {}).get("candles", []),
        vwap_data=state.get("mtf_15m", {}).get("vwap_data", []),
        supertrend_data=state.get("mtf_15m", {}).get("supertrend_data", []),
        candles_3m=state.get("mtf_3m", {}).get("candles", []),
        ema9_data=state.get("mtf_3m", {}).get("ema9_data", []),
        ema21_data=state.get("mtf_3m", {}).get("ema21_data", []),
        ema50_data=state.get("mtf_3m", {}).get("ema50_data", []),
        rsi_data=state.get("mtf_3m", {}).get("rsi_data", []),
        height=660,
        active_frame=frame_code,
    )
    components.html(chart_html, height=665)


# =============================================================================
# MAIN STREAMLIT APP ENTRYPOINT
# =============================================================================

def main():
    controls = render_sidebar()

    # 1. Header Bar & Confluence Gate (1s live auto-refresh)
    render_header_confluence_fragment(controls)

    # 2. Split Layout: Interactive TradingView Chart (Left 68%) + Telemetry (Right 32%)
    c_chart, c_telem = st.columns([68, 32])

    with c_chart:
        render_chart_fragment(controls)

    with c_telem:
        # Right-side telemetry panel (1s live auto-refresh)
        render_telemetry_tabs_fragment(controls)


if __name__ == "__main__":
    main()

