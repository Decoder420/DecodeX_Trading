"""DecodeX Trading — TradingView Lightweight Charts Generator for Streamlit.

Renders high-performance TradingView Lightweight Charts embedding the local production
bundle with zero external network dependencies, explicit container layout, and real-time
5Hz live streaming from the DecodeX Engine daemon.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_PATH = PROJECT_ROOT / "dashboard" / "static" / "lightweight-charts.standalone.production.js"

_INLINED_BUNDLE: Optional[str] = None


def get_bundle() -> str:
    """Read and cache local TradingView Lightweight Charts bundle."""
    global _INLINED_BUNDLE
    if _INLINED_BUNDLE is None:
        if BUNDLE_PATH.exists():
            _INLINED_BUNDLE = BUNDLE_PATH.read_text(encoding="utf-8")
        else:
            _INLINED_BUNDLE = ""
    return _INLINED_BUNDLE


def render_mtf_tradingview_html(
    candles_15m: List[Dict[str, Any]],
    vwap_data: List[Dict[str, Any]],
    supertrend_data: List[Dict[str, Any]],
    candles_3m: List[Dict[str, Any]],
    ema9_data: List[Dict[str, Any]],
    ema21_data: List[Dict[str, Any]],
    ema50_data: List[Dict[str, Any]],
    rsi_data: List[Dict[str, Any]],
    height: int = 680,
    active_frame: str = "both",  # 'both', '15m', '3m'
) -> str:
    """Generate self-contained HTML for Streamlit components.html with live 5Hz polling."""
    bundle = get_bundle()
    candles_15m_json = json.dumps(candles_15m)
    vwap_json = json.dumps(vwap_data)
    st_json = json.dumps(supertrend_data)

    candles_3m_json = json.dumps(candles_3m)
    ema9_json = json.dumps(ema9_data)
    ema21_json = json.dumps(ema21_data)
    ema50_json = json.dumps(ema50_data)
    rsi_json = json.dumps(rsi_data)

    # Dynamic sizing based on viewport
    if active_frame == "15m":
        h_box15 = f"{height - 10}px"
        h_canv15 = f"{height - 64}px"
        h_box3 = "0px"
        h_canv3 = "0px"
        h_canv_rsi = "0px"
    elif active_frame == "3m":
        h_box15 = "0px"
        h_canv15 = "0px"
        h_box3 = f"{height - 10}px"
        h_canv3 = f"{int((height - 70) * 0.72)}px"
        h_canv_rsi = f"{int((height - 70) * 0.28)}px"
    else:  # both
        h_box15 = "320px"
        h_canv15 = "266px"
        h_box3 = "330px"
        h_canv3 = "191px"
        h_canv_rsi = "85px"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DecodeX TradingView Charts</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-user-select: none;
        }}
        body, html {{
            width: 100%;\
            height: 100%;
            overflow: hidden;
            background-color: #131722;
            color: #D1D4DC;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
            font-size: 11px;
        }}
        #main-container {{
            display: flex;
            flex-direction: column;
            width: 100%;
            height: {height}px;
            gap: 8px;
            background-color: #131722;
        }}
        .chart-box {{
            width: 100%;
            background: #1E222D;
            border: 1px solid #2A2E39;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
        }}
        .chart-header {{
            height: 30px;
            background: #181B24;
            border-bottom: 1px solid #2A2E39;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 10px;
            font-size: 11px;
            font-weight: 700;
        }}
        .header-title {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .dot-green {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #089981;
            box-shadow: 0 0 6px #089981;
        }}
        .dot-cyan {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #00E5FF;
            box-shadow: 0 0 6px #00E5FF;
        }}
        .chart-canvas {{
            width: 100%;
            position: relative;
        }}
        .legend-hud {{
            height: 22px;
            background: #181B24;
            border-bottom: 1px solid #20242F;
            font-family: "SF Mono", monospace;
            font-size: 10px;
            padding: 0 10px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: #787B86;
        }}
        .legend-hud b {{
            color: #D1D4DC;
        }}
        /* Hide TradingView watermark logo */
        a[href*="tradingview"], .tv-lightweight-charts-logo {{
            display: none !important;
        }}
        .btn-fit {{
            background: #2A2E39;
            border: 1px solid #363A45;
            color: #D1D4DC;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 3px;
            cursor: pointer;
        }}
        .btn-fit:hover {{
            background: #363A45;
            color: #FFF;
        }}
        .live-tag {{
            font-size: 9px;
            font-weight: 700;
            background: rgba(8, 153, 129, 0.18);
            color: #089981;
            padding: 2px 6px;
            border-radius: 4px;
            margin-right: 6px;
        }}
    </style>
    <script>{bundle}</script>
</head>
<body>
    <div id="main-container">
        <!-- 15m Structural Frame -->
        <div class="chart-box" id="box-15m" style="height: {h_box15}; display: {'block' if active_frame in ('both', '15m') else 'none'};">
            <div class="chart-header">
                <div class="header-title" style="color: #00E5FF;">
                    <span class="dot-cyan"></span>
                    <span>15M STRUCTURAL FRAME (ANCHORED VWAP & SUPERTREND 10, 2.5)</span>
                </div>
                <div style="display:flex; align-items:center;">
                    <span class="live-tag" id="tag-15m">● REAL-TIME 5Hz</span>
                    <button class="btn-fit" onclick="fit15m()">⚡ Auto-Fit</button>
                </div>
            </div>
            <div class="legend-hud" id="hud-15m">
                <span>O: <b id="l15-o">—</b></span>
                <span>H: <b id="l15-h">—</b></span>
                <span>L: <b id="l15-l">—</b></span>
                <span>C: <b id="l15-c">—</b></span>
                <span style="color:#00E5FF;">VWAP: <b id="l15-vwap">—</b></span>
                <span style="color:#089981;">ST: <b id="l15-st">—</b></span>
            </div>
            <div class="chart-canvas" id="canvas-15m" style="height: {h_canv15};"></div>
        </div>

        <!-- 3m Execution Frame + RSI Sub-pane -->
        <div class="chart-box" id="box-3m" style="height: {h_box3}; display: {'block' if active_frame in ('both', '3m') else 'none'};">
            <div class="chart-header">
                <div class="header-title" style="color: #FFB74D;">
                    <span class="dot-green"></span>
                    <span>3M EXECUTION FRAME (EMA RIBBON 9/21/50 & RSI 14 MOMENTUM)</span>
                </div>
                <div style="display:flex; align-items:center;">
                    <span class="live-tag" id="tag-3m">● REAL-TIME 5Hz</span>
                    <button class="btn-fit" onclick="fit3m()">⚡ Auto-Fit</button>
                </div>
            </div>
            <div class="legend-hud" id="hud-3m">
                <span>O: <b id="l3-o">—</b></span>
                <span>H: <b id="l3-h">—</b></span>
                <span>L: <b id="l3-l">—</b></span>
                <span>C: <b id="l3-c">—</b></span>
                <span style="color:#F59E0B;">EMA9: <b id="l3-e9">—</b></span>
                <span style="color:#FF6D00;">EMA21: <b id="l3-e21">—</b></span>
                <span style="color:#AB47BC;">EMA50: <b id="l3-e50">—</b></span>
                <span style="color:#00E5FF;">RSI: <b id="l3-rsi">—</b></span>
            </div>
            <div class="chart-canvas" id="canvas-3m" style="height: {h_canv3};"></div>
            <div id="canvas-3m-rsi" style="height: {h_canv_rsi}; width: 100%; border-top: 1px solid #2A2E39;"></div>
        </div>
    </div>

    <script>
        const c15_data = {candles_15m_json};
        const vwap_data = {vwap_json};
        const st_data = {st_json};

        const c3_data = {candles_3m_json};
        const e9_data = {ema9_json};
        const e21_data = {ema21_json};
        const e50_data = {ema50_json};
        const rsi_data = {rsi_json};

        let chart15 = null;
        let sCandle15 = null;
        let sVwap15 = null;
        let sSt15 = null;
        let lastBarTime15 = c15_data.length > 0 ? c15_data[c15_data.length - 1].time : 0;

        let chart3 = null;
        let sCandle3 = null;
        let sE9 = null;
        let sE21 = null;
        let sE50 = null;
        let lastBarTime3 = c3_data.length > 0 ? c3_data[c3_data.length - 1].time : 0;

        let chartRsi = null;
        let sRsi = null;

        function initCharts() {{
            // 1. Initialize 15m Chart
            const el15 = document.getElementById('canvas-15m');
            if (el15 && document.getElementById('box-15m').style.display !== 'none') {{
                const w15 = el15.clientWidth || window.innerWidth || 800;
                const h15 = el15.clientHeight || parseInt('{h_canv15}') || 288;

                chart15 = LightweightCharts.createChart(el15, {{
                    width: w15,
                    height: h15,
                    layout: {{
                        background: {{ type: 'solid', color: '#1E222D' }},
                        textColor: '#787B86',
                        fontSize: 11,
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
                    }},
                    grid: {{
                        vertLines: {{ color: 'rgba(42, 46, 57, 0.45)', style: 2 }},
                        horzLines: {{ color: 'rgba(42, 46, 57, 0.45)', style: 2 }},
                    }},
                    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                    rightPriceScale: {{ borderColor: '#2A2E39', autoScale: true }},
                    timeScale: {{ borderColor: '#2A2E39', timeVisible: true, secondsVisible: false }},
                }});

                sCandle15 = chart15.addCandlestickSeries({{
                    upColor: '#089981', downColor: '#F23645',
                    borderUpColor: '#089981', borderDownColor: '#F23645',
                    wickUpColor: '#089981', wickDownColor: '#F23645',
                }});
                if (c15_data.length > 0) sCandle15.setData(c15_data);

                sVwap15 = chart15.addLineSeries({{ color: '#00E5FF', lineWidth: 2, title: 'VWAP' }});
                if (vwap_data.length > 0) sVwap15.setData(vwap_data);

                sSt15 = chart15.addLineSeries({{ color: '#089981', lineWidth: 1.6, title: 'Supertrend' }});
                if (st_data.length > 0) sSt15.setData(st_data);

                if (c15_data.length > 0) {{
                    const last15 = c15_data[c15_data.length - 1];
                    document.getElementById('l15-o').innerText = last15.open.toFixed(1);
                    document.getElementById('l15-h').innerText = last15.high.toFixed(1);
                    document.getElementById('l15-l').innerText = last15.low.toFixed(1);
                    document.getElementById('l15-c').innerText = last15.close.toFixed(1);
                    document.getElementById('l15-c').style.color = last15.close >= last15.open ? '#089981' : '#F23645';
                    if (vwap_data.length > 0) document.getElementById('l15-vwap').innerText = vwap_data[vwap_data.length - 1].value.toFixed(1);
                    if (st_data.length > 0) document.getElementById('l15-st').innerText = st_data[st_data.length - 1].value.toFixed(1);
                    chart15.timeScale().fitContent();
                }}
            }}

            // 2. Initialize 3m Chart + RSI Sub-pane
            const el3 = document.getElementById('canvas-3m');
            const elRsi = document.getElementById('canvas-3m-rsi');
            if (el3 && document.getElementById('box-3m').style.display !== 'none') {{
                const w3 = el3.clientWidth || window.innerWidth || 800;
                const h3 = el3.clientHeight || parseInt('{h_canv3}') || 215;

                chart3 = LightweightCharts.createChart(el3, {{
                    width: w3,
                    height: h3,
                    layout: {{
                        background: {{ type: 'solid', color: '#1E222D' }},
                        textColor: '#787B86',
                        fontSize: 11,
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
                    }},
                    grid: {{
                        vertLines: {{ color: 'rgba(42, 46, 57, 0.45)', style: 2 }},
                        horzLines: {{ color: 'rgba(42, 46, 57, 0.45)', style: 2 }},
                    }},
                    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                    rightPriceScale: {{ borderColor: '#2A2E39', autoScale: true }},
                    timeScale: {{ borderColor: '#2A2E39', timeVisible: true, secondsVisible: false }},
                }});

                sCandle3 = chart3.addCandlestickSeries({{
                    upColor: '#089981', downColor: '#F23645',
                    borderUpColor: '#089981', borderDownColor: '#F23645',
                    wickUpColor: '#089981', wickDownColor: '#F23645',
                }});
                if (c3_data.length > 0) sCandle3.setData(c3_data);

                sE9 = chart3.addLineSeries({{ color: '#F59E0B', lineWidth: 1.5, title: 'EMA9' }});
                if (e9_data.length > 0) sE9.setData(e9_data);

                sE21 = chart3.addLineSeries({{ color: '#FF6D00', lineWidth: 1.5, title: 'EMA21' }});
                if (e21_data.length > 0) sE21.setData(e21_data);

                sE50 = chart3.addLineSeries({{ color: '#AB47BC', lineWidth: 1.5, title: 'EMA50' }});
                if (e50_data.length > 0) sE50.setData(e50_data);

                // RSI Pane
                if (elRsi) {{
                    const hRsi = elRsi.clientHeight || parseInt('{h_canv_rsi}') || 85;
                    chartRsi = LightweightCharts.createChart(elRsi, {{
                        width: w3,
                        height: hRsi,
                        layout: {{
                            background: {{ type: 'solid', color: '#181B24' }},
                            textColor: '#787B86',
                            fontSize: 10,
                        }},
                        grid: {{
                            vertLines: {{ color: 'rgba(42, 46, 57, 0.35)', style: 2 }},
                            horzLines: {{ color: 'rgba(42, 46, 57, 0.35)', style: 2 }},
                        }},
                        crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                        rightPriceScale: {{ borderColor: '#2A2E39', scaleMargins: {{ top: 0.1, bottom: 0.1 }} }},
                        timeScale: {{ borderColor: '#2A2E39', timeVisible: true, visible: false }},
                    }});

                    sRsi = chartRsi.addLineSeries({{ color: '#00E5FF', lineWidth: 1.5, title: 'RSI(14)' }});
                    if (rsi_data.length > 0) sRsi.setData(rsi_data);

                    // Synchronize time scales between 3m price and RSI momentum
                    chart3.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                        if (range && chartRsi) chartRsi.timeScale().setVisibleLogicalRange(range);
                    }});
                    chartRsi.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                        if (range && chart3) chart3.timeScale().setVisibleLogicalRange(range);
                    }});
                }}

                if (c3_data.length > 0) {{
                    const last3 = c3_data[c3_data.length - 1];
                    document.getElementById('l3-o').innerText = last3.open.toFixed(1);
                    document.getElementById('l3-h').innerText = last3.high.toFixed(1);
                    document.getElementById('l3-l').innerText = last3.low.toFixed(1);
                    document.getElementById('l3-c').innerText = last3.close.toFixed(1);
                    document.getElementById('l3-c').style.color = last3.close >= last3.open ? '#089981' : '#F23645';
                    if (e9_data.length > 0) document.getElementById('l3-e9').innerText = e9_data[e9_data.length - 1].value.toFixed(1);
                    if (e21_data.length > 0) document.getElementById('l3-e21').innerText = e21_data[e21_data.length - 1].value.toFixed(1);
                    if (e50_data.length > 0) document.getElementById('l3-e50').innerText = e50_data[e50_data.length - 1].value.toFixed(1);
                    if (rsi_data.length > 0) document.getElementById('l3-rsi').innerText = rsi_data[rsi_data.length - 1].value.toFixed(1);
                    chart3.timeScale().fitContent();
                    if (chartRsi) chartRsi.timeScale().fitContent();
                }}
            }}
        }}

        function fit15m() {{ if (chart15) chart15.timeScale().fitContent(); }}
        function fit3m() {{
            if (chart3) chart3.timeScale().fitContent();
            if (chartRsi) chartRsi.timeScale().fitContent();
        }}

        // =====================================================================
        // ULTRA-FAST 5Hz REAL-TIME DATA STREAM FROM DECODEX ENGINE DAEMON
        // =====================================================================
        function updateLiveTag(isLive) {{
            const tag15 = document.getElementById('tag-15m');
            const tag3 = document.getElementById('tag-3m');
            const color = isLive ? '#089981' : '#F23645';
            const text = isLive ? '● REAL-TIME 5Hz' : '○ OFFLINE';
            if (tag15) {{ tag15.style.color = color; tag15.innerText = text; }}
            if (tag3) {{ tag3.style.color = color; tag3.innerText = text; }}
        }}

        async function streamLiveTicks() {{
            try {{
                const res = await fetch("http://127.0.0.1:8765/state", {{ cache: "no-store" }});
                if (!res.ok) {{
                    updateLiveTag(false);
                    return;
                }}
                const state = await res.json();
                if (!state) return;
                updateLiveTag(true);

                // Update 15m Real-time Bar
                const m15 = state.mtf_15m;
                if (m15 && sCandle15) {{
                    const candles15 = m15.candles;
                    if (candles15 && candles15.length > 0) {{
                        const cur = candles15[candles15.length - 1];
                        if (cur.time > lastBarTime15) {{
                            sCandle15.setData(candles15);
                            if (sVwap15 && m15.vwap_data) sVwap15.setData(m15.vwap_data);
                            if (sSt15 && m15.supertrend_data) sSt15.setData(m15.supertrend_data);
                            lastBarTime15 = cur.time;
                        }} else {{
                            sCandle15.update(cur);
                            if (sVwap15 && m15.anchored_vwap != null) sVwap15.update({{ time: cur.time, value: m15.anchored_vwap }});
                            if (sSt15 && m15.supertrend != null) sSt15.update({{ time: cur.time, value: m15.supertrend }});
                        }}

                        document.getElementById('l15-o').innerText = cur.open.toFixed(1);
                        document.getElementById('l15-h').innerText = cur.high.toFixed(1);
                        document.getElementById('l15-l').innerText = cur.low.toFixed(1);
                        document.getElementById('l15-c').innerText = cur.close.toFixed(1);
                        document.getElementById('l15-c').style.color = cur.close >= cur.open ? '#089981' : '#F23645';
                        if (m15.anchored_vwap != null) document.getElementById('l15-vwap').innerText = m15.anchored_vwap.toFixed(1);
                        if (m15.supertrend != null) document.getElementById('l15-st').innerText = m15.supertrend.toFixed(1);
                    }}
                }}

                // Update 3m Real-time Bar
                const m3 = state.mtf_3m;
                if (m3 && sCandle3) {{
                    const candles3 = m3.candles;
                    if (candles3 && candles3.length > 0) {{
                        const cur = candles3[candles3.length - 1];
                        if (cur.time > lastBarTime3) {{
                            sCandle3.setData(candles3);
                            if (sE9 && m3.ema9_data) sE9.setData(m3.ema9_data);
                            if (sE21 && m3.ema21_data) sE21.setData(m3.ema21_data);
                            if (sE50 && m3.ema50_data) sE50.setData(m3.ema50_data);
                            if (sRsi && m3.rsi_data) sRsi.setData(m3.rsi_data);
                            lastBarTime3 = cur.time;
                        }} else {{
                            sCandle3.update(cur);
                            if (sE9 && m3.ema_9 != null) sE9.update({{ time: cur.time, value: m3.ema_9 }});
                            if (sE21 && m3.ema_21 != null) sE21.update({{ time: cur.time, value: m3.ema_21 }});
                            if (sE50 && m3.ema_50 != null) sE50.update({{ time: cur.time, value: m3.ema_50 }});
                            if (sRsi && m3.rsi_14 != null) sRsi.update({{ time: cur.time, value: m3.rsi_14 }});
                        }}

                        document.getElementById('l3-o').innerText = cur.open.toFixed(1);
                        document.getElementById('l3-h').innerText = cur.high.toFixed(1);
                        document.getElementById('l3-l').innerText = cur.low.toFixed(1);
                        document.getElementById('l3-c').innerText = cur.close.toFixed(1);
                        document.getElementById('l3-c').style.color = cur.close >= cur.open ? '#089981' : '#F23645';
                        if (m3.ema_9 != null) document.getElementById('l3-e9').innerText = m3.ema_9.toFixed(1);
                        if (m3.ema_21 != null) document.getElementById('l3-e21').innerText = m3.ema_21.toFixed(1);
                        if (m3.ema_50 != null) document.getElementById('l3-e50').innerText = m3.ema_50.toFixed(1);
                        if (m3.rsi_14 != null) document.getElementById('l3-rsi').innerText = m3.rsi_14.toFixed(1);
                    }}
                }}
            }} catch (e) {{
                updateLiveTag(false);
            }}
        }}

        // Run on load and poll every 200ms for authentic real-time ticks
        window.addEventListener('DOMContentLoaded', () => {{
            initCharts();
            setInterval(streamLiveTicks, 200);
        }});

        // Responsive resize observer
        window.addEventListener('resize', () => {{
            const el15 = document.getElementById('canvas-15m');
            if (chart15 && el15) chart15.applyOptions({{ width: el15.clientWidth }});
            const el3 = document.getElementById('canvas-3m');
            if (chart3 && el3) chart3.applyOptions({{ width: el3.clientWidth }});
            const elRsi = document.getElementById('canvas-3m-rsi');
            if (chartRsi && elRsi) chartRsi.applyOptions({{ width: elRsi.clientWidth }});
        }});
    </script>
</body>
</html>"""
