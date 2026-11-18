"""DecodeX Trading — TradingView Lightweight Charts Bridge for PyQt6 QWebEngineView.

Role:
- Generates self-contained HTML/JS templates embedding the official TradingView Lightweight Charts library.
- Provides interactive dark-themed charts with zero external dependencies (inlines local JS bundle).
- Implements two specialized chart views:
    1. 15-Minute Structural Frame (Candlesticks, Anchored VWAP, Supertrend 10, 2.5).
    2. 3-Minute Execution Frame (Candlesticks, EMA Ribbon 9/21/50, Bollinger Bands, RSI 14 Momentum Sub-pane).
- Exposes JavaScript bridge functions (setChartData, updateLiveBar, zoomRange, fitContent)
  for dynamic non-blocking updates via QWebEngineView.page().runJavaScript().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_BUNDLE_PATH = ROOT_DIR / "dashboard" / "static" / "lightweight-charts.standalone.production.js"

# Cache JS bundle in memory for fast rendering
_INLINED_BUNDLE: Optional[str] = None


def get_inlined_bundle() -> str:
    """Read and cache local TradingView Lightweight Charts production bundle."""
    global _INLINED_BUNDLE
    if _INLINED_BUNDLE is None:
        if STATIC_BUNDLE_PATH.exists():
            _INLINED_BUNDLE = STATIC_BUNDLE_PATH.read_text(encoding="utf-8")
        else:
            _INLINED_BUNDLE = ""
    return _INLINED_BUNDLE


# =============================================================================
# 15-MINUTE STRUCTURAL BIAS CHART HTML TEMPLATE
# =============================================================================

def get_tradingview_15m_html() -> str:
    """Generate HTML template for the 15-Minute Structural Frame TradingView chart."""
    bundle = get_inlined_bundle()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DecodeX 15m Structural Frame</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-user-select: none;
        }}
        body, html {{
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #1E222D;
            color: #D1D4DC;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
            font-size: 11px;
        }}
        #container {{
            display: flex;
            flex-direction: column;
            width: 100%;
            height: 100%;
            background-color: #1E222D;
            border-radius: 8px;
            overflow: hidden;
        }}
        #toolbar {{
            height: 32px;
            background: #181B24;
            border-bottom: 1px solid #2A2E39;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 12px;
            z-index: 10;
        }}
        .tb-title {{
            font-size: 11px;
            font-weight: 700;
            color: #00E5FF;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .tb-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #089981;
            box-shadow: 0 0 6px #089981;
            display: inline-block;
        }}
        .btn-group {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .tb-btn {{
            background: #2A2E39;
            color: #B2B5BE;
            border: 1px solid #363A45;
            border-radius: 4px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .tb-btn:hover {{
            background: #363A45;
            color: #FFFFFF;
        }}
        .tb-btn.active {{
            background: rgba(0, 229, 255, 0.18);
            color: #00E5FF;
            border-color: #00E5FF;
        }}
        #chart-wrapper {{
            position: relative;
            flex: 1;
            width: 100%;
            height: calc(100% - 32px);
        }}
        #tv-chart {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }}
        #legend {{
            position: absolute;
            top: 8px;
            left: 12px;
            z-index: 5;
            pointer-events: none;
            font-size: 11px;
            font-family: "SF Mono", Menlo, monospace;
            color: #D1D4DC;
            background: rgba(30, 34, 45, 0.88);
            padding: 4px 10px;
            border-radius: 4px;
            border: 1px solid #2A2E39;
            display: flex;
            gap: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
            white-space: nowrap;
        }}
        .legend-val {{
            font-weight: 700;
        }}
    </style>
    <script>{bundle}</script>
</head>
<body>
    <div id="container">
        <div id="toolbar">
            <div class="tb-title">
                <span class="tb-dot"></span>
                <span>15M STRUCTURAL FRAME (ANCHORED VWAP & SUPERTREND)</span>
            </div>
            <div class="btn-group">
                <button class="tb-btn active" id="btn-session" onclick="zoomRange('session')">1D Session</button>
                <button class="tb-btn" id="btn-3d" onclick="zoomRange('3d')">3D</button>
                <button class="tb-btn" id="btn-all" onclick="zoomRange('all')">All</button>
                <button class="tb-btn" onclick="fitContent()">⚡ Auto-Fit</button>
            </div>
        </div>
        <div id="chart-wrapper">
            <div id="tv-chart"></div>
            <div id="legend">
                <span>O: <span id="l-open" class="legend-val">—</span></span>
                <span>H: <span id="l-high" class="legend-val">—</span></span>
                <span>L: <span id="l-low" class="legend-val">—</span></span>
                <span>C: <span id="l-close" class="legend-val">—</span></span>
                <span style="color:#00E5FF;">VWAP: <span id="l-vwap" class="legend-val">—</span></span>
                <span style="color:#089981;">ST: <span id="l-st" class="legend-val">—</span></span>
            </div>
        </div>
    </div>

    <script>
        const chartContainer = document.getElementById('tv-chart');
        let chart = null;
        let candleSeries = null;
        let vwapSeries = null;
        let stSeries = null;
        let rawCandles = [];

        function initChart() {{
            chart = LightweightCharts.createChart(chartContainer, {{
                width: chartContainer.clientWidth,
                height: chartContainer.clientHeight,
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
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{ color: '#787B86', width: 1, style: 3 }},
                    horzLine: {{ color: '#787B86', width: 1, style: 3 }},
                }},
                rightPriceScale: {{
                    borderColor: '#2A2E39',
                    autoScale: true,
                    scaleMargins: {{ top: 0.12, bottom: 0.12 }},
                }},
                timeScale: {{
                    borderColor: '#2A2E39',
                    timeVisible: true,
                    secondsVisible: false,
                }},
            }});

            candleSeries = chart.addCandlestickSeries({{
                upColor: '#089981',
                downColor: '#F23645',
                borderUpColor: '#089981',
                borderDownColor: '#F23645',
                wickUpColor: '#089981',
                wickDownColor: '#F23645',
            }});

            vwapSeries = chart.addLineSeries({{
                color: '#00E5FF',
                lineWidth: 2,
                title: 'VWAP',
                priceLineVisible: false,
            }});

            stSeries = chart.addLineSeries({{
                color: '#089981',
                lineWidth: 1.6,
                title: 'Supertrend',
                priceLineVisible: false,
            }});

            // Crosshair subscriber for dynamic hover legend
            chart.subscribeCrosshairMove(param => {{
                if (!param || !param.time || !param.seriesData) return;
                const cData = param.seriesData.get(candleSeries);
                if (cData) {{
                    document.getElementById('l-open').innerText = cData.open ? cData.open.toFixed(1) : '—';
                    document.getElementById('l-high').innerText = cData.high ? cData.high.toFixed(1) : '—';
                    document.getElementById('l-low').innerText = cData.low ? cData.low.toFixed(1) : '—';
                    document.getElementById('l-close').innerText = cData.close ? cData.close.toFixed(1) : '—';
                    const isUp = cData.close >= cData.open;
                    document.getElementById('l-close').style.color = isUp ? '#089981' : '#F23645';
                }}
                const vData = param.seriesData.get(vwapSeries);
                if (vData && vData.value) {{
                    document.getElementById('l-vwap').innerText = vData.value.toFixed(1);
                }}
                const sData = param.seriesData.get(stSeries);
                if (sData && sData.value) {{
                    document.getElementById('l-st').innerText = sData.value.toFixed(1);
                }}
            }});

            // Auto-resize observer
            const resizeObserver = new ResizeObserver(entries => {{
                if (entries.length === 0 || !chart) return;
                const {{ width, height }} = entries[0].contentRect;
                chart.applyOptions({{ width, height }});
            }});
            resizeObserver.observe(chartContainer);
        }}

        window.setChartData = function(data) {{
            if (!chart) initChart();
            if (!data) return;

            if (data.candles && data.candles.length > 0) {{
                rawCandles = data.candles;
                candleSeries.setData(data.candles);
                const last = data.candles[data.candles.length - 1];
                document.getElementById('l-open').innerText = last.open.toFixed(1);
                document.getElementById('l-high').innerText = last.high.toFixed(1);
                document.getElementById('l-low').innerText = last.low.toFixed(1);
                document.getElementById('l-close').innerText = last.close.toFixed(1);
            }}
            if (data.vwap && data.vwap.length > 0) {{
                vwapSeries.setData(data.vwap);
                document.getElementById('l-vwap').innerText = data.vwap[data.vwap.length - 1].value.toFixed(1);
            }}
            if (data.supertrend && data.supertrend.length > 0) {{
                stSeries.setData(data.supertrend);
                document.getElementById('l-st').innerText = data.supertrend[data.supertrend.length - 1].value.toFixed(1);
            }}
            chart.timeScale().fitContent();
        }};

        window.updateLiveBar = function(candle, vwapVal, stVal) {{
            if (!chart || !candle) return;
            candleSeries.update(candle);
            document.getElementById('l-open').innerText = candle.open.toFixed(1);
            document.getElementById('l-high').innerText = candle.high.toFixed(1);
            document.getElementById('l-low').innerText = candle.low.toFixed(1);
            document.getElementById('l-close').innerText = candle.close.toFixed(1);

            if (vwapVal !== undefined && vwapVal !== null) {{
                vwapSeries.update({{ time: candle.time, value: vwapVal }});
                document.getElementById('l-vwap').innerText = vwapVal.toFixed(1);
            }}
            if (stVal !== undefined && stVal !== null) {{
                stSeries.update({{ time: candle.time, value: stVal }});
                document.getElementById('l-st').innerText = stVal.toFixed(1);
            }}
        }};

        window.fitContent = function() {{
            if (chart) chart.timeScale().fitContent();
        }};

        window.zoomRange = function(rangeType) {{
            if (!chart || rawCandles.length === 0) return;
            document.querySelectorAll('.tb-btn').forEach(b => b.classList.remove('active'));
            const n = rawCandles.length;
            let fromIdx = 0;
            if (rangeType === 'session') {{
                fromIdx = Math.max(0, n - 26);
                document.getElementById('btn-session').classList.add('active');
            }} else if (rangeType === '3d') {{
                fromIdx = Math.max(0, n - 75);
                document.getElementById('btn-3d').classList.add('active');
            }} else {{
                fromIdx = 0;
                document.getElementById('btn-all').classList.add('active');
            }}
            chart.timeScale().setVisibleLogicalRange({{ from: fromIdx, to: n + 2 }});
        }};

        window.onload = initChart;
    </script>
</body>
</html>"""


# =============================================================================
# 3-MINUTE EXECUTION TRIGGERS CHART HTML TEMPLATE (WITH INTEGRATED RSI PANE)
# =============================================================================

def get_tradingview_3m_html() -> str:
    """Generate HTML template for the 3-Minute Execution Frame TradingView chart with RSI sub-pane."""
    bundle = get_inlined_bundle()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DecodeX 3m Execution Frame</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-user-select: none;
        }}
        body, html {{
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #1E222D;
            color: #D1D4DC;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
            font-size: 11px;
        }}
        #container {{
            display: flex;
            flex-direction: column;
            width: 100%;
            height: 100%;
            background-color: #1E222D;
            border-radius: 8px;
            overflow: hidden;
        }}
        #toolbar {{
            height: 32px;
            background: #181B24;
            border-bottom: 1px solid #2A2E39;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 12px;
            z-index: 10;
        }}
        .tb-title {{
            font-size: 11px;
            font-weight: 700;
            color: #F59E0B;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .tb-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #089981;
            box-shadow: 0 0 6px #089981;
            display: inline-block;
        }}
        .btn-group {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .tb-btn {{
            background: #2A2E39;
            color: #B2B5BE;
            border: 1px solid #363A45;
            border-radius: 4px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .tb-btn:hover {{
            background: #363A45;
            color: #FFFFFF;
        }}
        .tb-btn.active {{
            background: rgba(245, 158, 11, 0.18);
            color: #F59E0B;
            border-color: #F59E0B;
        }}
        #panes-wrapper {{
            display: flex;
            flex-direction: column;
            flex: 1;
            width: 100%;
            height: calc(100% - 32px);
        }}
        #main-chart-wrapper {{
            position: relative;
            flex: 72;
            width: 100%;
        }}
        #tv-main-chart {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }}
        #rsi-chart-wrapper {{
            position: relative;
            flex: 28;
            width: 100%;
            border-top: 1px solid #2A2E39;
        }}
        #tv-rsi-chart {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }}
        #legend {{
            position: absolute;
            top: 6px;
            left: 12px;
            z-index: 5;
            pointer-events: none;
            font-size: 11px;
            font-family: "SF Mono", Menlo, monospace;
            color: #D1D4DC;
            background: rgba(30, 34, 45, 0.88);
            padding: 4px 10px;
            border-radius: 4px;
            border: 1px solid #2A2E39;
            display: flex;
            gap: 10px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
            white-space: nowrap;
        }}
        #rsi-legend {{
            position: absolute;
            top: 4px;
            left: 12px;
            z-index: 5;
            pointer-events: none;
            font-size: 10px;
            font-family: "SF Mono", Menlo, monospace;
            color: #2962FF;
            font-weight: 700;
        }}
        .legend-val {{
            font-weight: 700;
        }}
    </style>
    <script>{bundle}</script>
</head>
<body>
    <div id="container">
        <div id="toolbar">
            <div class="tb-title">
                <span class="tb-dot"></span>
                <span>3M EXECUTION TRIGGERS (EMA RIBBON 9/21/50 & RSI 14)</span>
            </div>
            <div class="btn-group">
                <button class="tb-btn active" id="btn-session" onclick="zoomRange('session')">1D Session</button>
                <button class="tb-btn" id="btn-3d" onclick="zoomRange('3d')">3D</button>
                <button class="tb-btn" id="btn-all" onclick="zoomRange('all')">All</button>
                <button class="tb-btn" onclick="fitContent()">⚡ Auto-Fit</button>
            </div>
        </div>
        <div id="panes-wrapper">
            <div id="main-chart-wrapper">
                <div id="tv-main-chart"></div>
                <div id="legend">
                    <span>C: <span id="l-close" class="legend-val">—</span></span>
                    <span style="color:#F59E0B;">EMA 9: <span id="l-ema9" class="legend-val">—</span></span>
                    <span style="color:#FF6D00;">EMA 21: <span id="l-ema21" class="legend-val">—</span></span>
                    <span style="color:#AB47BC;">EMA 50: <span id="l-ema50" class="legend-val">—</span></span>
                </div>
            </div>
            <div id="rsi-chart-wrapper">
                <div id="tv-rsi-chart"></div>
                <div id="rsi-legend">RSI(14): <span id="l-rsi" style="color:#38BDF8;">—</span></div>
            </div>
        </div>
    </div>

    <script>
        const mainContainer = document.getElementById('tv-main-chart');
        const rsiContainer = document.getElementById('tv-rsi-chart');
        let mainChart = null;
        let rsiChart = null;
        let candleSeries = null;
        let ema9Series = null;
        let ema21Series = null;
        let ema50Series = null;
        let rsiSeries = null;
        let rawCandles = [];

        function initCharts() {{
            // 1. Initialize Main Price Chart
            mainChart = LightweightCharts.createChart(mainContainer, {{
                width: mainContainer.clientWidth,
                height: mainContainer.clientHeight,
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
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{ color: '#787B86', width: 1, style: 3 }},
                    horzLine: {{ color: '#787B86', width: 1, style: 3 }},
                }},
                rightPriceScale: {{
                    borderColor: '#2A2E39',
                    autoScale: true,
                    scaleMargins: {{ top: 0.10, bottom: 0.10 }},
                }},
                timeScale: {{
                    borderColor: '#2A2E39',
                    timeVisible: true,
                    secondsVisible: false,
                    visible: false, // Hidden on main pane; visible on RSI pane below
                }},
            }});

            candleSeries = mainChart.addCandlestickSeries({{
                upColor: '#089981',
                downColor: '#F23645',
                borderUpColor: '#089981',
                borderDownColor: '#F23645',
                wickUpColor: '#089981',
                wickDownColor: '#F23645',
            }});

            ema9Series = mainChart.addLineSeries({{
                color: '#F59E0B',
                lineWidth: 1.5,
                title: 'EMA 9',
                priceLineVisible: false,
            }});

            ema21Series = mainChart.addLineSeries({{
                color: '#FF6D00',
                lineWidth: 1.5,
                title: 'EMA 21',
                priceLineVisible: false,
            }});

            ema50Series = mainChart.addLineSeries({{
                color: '#AB47BC',
                lineWidth: 1.5,
                title: 'EMA 50',
                priceLineVisible: false,
            }});

            // 2. Initialize Lower RSI Momentum Chart
            rsiChart = LightweightCharts.createChart(rsiContainer, {{
                width: rsiContainer.clientWidth,
                height: rsiContainer.clientHeight,
                layout: {{
                    background: {{ type: 'solid', color: '#1E222D' }},
                    textColor: '#787B86',
                    fontSize: 10,
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(42, 46, 57, 0.35)', style: 2 }},
                    horzLines: {{ color: 'rgba(42, 46, 57, 0.35)', style: 2 }},
                }},
                rightPriceScale: {{
                    borderColor: '#2A2E39',
                    autoScale: false,
                    scaleMargins: {{ top: 0.05, bottom: 0.05 }},
                }},
                timeScale: {{
                    borderColor: '#2A2E39',
                    timeVisible: true,
                    secondsVisible: false,
                }},
            }});

            rsiSeries = rsiChart.addLineSeries({{
                color: '#2962FF',
                lineWidth: 1.6,
                priceLineVisible: false,
            }});

            // RSI Reference Lines (70 Overbought, 50 Centerline, 30 Oversold)
            const rsi70 = rsiChart.addLineSeries({{ color: 'rgba(242, 54, 69, 0.65)', lineStyle: 2, lineWidth: 1, priceLineVisible: false }});
            const rsi50 = rsiChart.addLineSeries({{ color: 'rgba(71, 85, 105, 0.65)', lineStyle: 3, lineWidth: 1, priceLineVisible: false }});
            const rsi30 = rsiChart.addLineSeries({{ color: 'rgba(8, 153, 129, 0.65)', lineStyle: 2, lineWidth: 1, priceLineVisible: false }});

            // Synchronize TimeScales between Main Price and RSI
            mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                if (range && rsiChart) rsiChart.timeScale().setVisibleLogicalRange(range);
            }});
            rsiChart.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                if (range && mainChart) mainChart.timeScale().setVisibleLogicalRange(range);
            }});

            // Crosshair subscriber for dynamic hover legend
            mainChart.subscribeCrosshairMove(param => {{
                if (!param || !param.time || !param.seriesData) return;
                const cData = param.seriesData.get(candleSeries);
                if (cData) {{
                    document.getElementById('l-close').innerText = cData.close ? cData.close.toFixed(1) : '—';
                    document.getElementById('l-close').style.color = (cData.close >= cData.open) ? '#089981' : '#F23645';
                }}
                const e9 = param.seriesData.get(ema9Series);
                if (e9 && e9.value) document.getElementById('l-ema9').innerText = e9.value.toFixed(1);
                const e21 = param.seriesData.get(ema21Series);
                if (e21 && e21.value) document.getElementById('l-ema21').innerText = e21.value.toFixed(1);
                const e50 = param.seriesData.get(ema50Series);
                if (e50 && e50.value) document.getElementById('l-ema50').innerText = e50.value.toFixed(1);
            }});

            rsiChart.subscribeCrosshairMove(param => {{
                if (!param || !param.time || !param.seriesData) return;
                const rData = param.seriesData.get(rsiSeries);
                if (rData && rData.value) {{
                    document.getElementById('l-rsi').innerText = rData.value.toFixed(1);
                }}
            }});

            // Auto-resize observers
            const roMain = new ResizeObserver(entries => {{
                if (entries.length === 0 || !mainChart) return;
                mainChart.applyOptions({{ width: entries[0].contentRect.width, height: entries[0].contentRect.height }});
            }});
            roMain.observe(mainContainer);

            const roRsi = new ResizeObserver(entries => {{
                if (entries.length === 0 || !rsiChart) return;
                rsiChart.applyOptions({{ width: entries[0].contentRect.width, height: entries[0].contentRect.height }});
            }});
            roRsi.observe(rsiContainer);
        }}

        window.setChartData = function(data) {{
            if (!mainChart) initCharts();
            if (!data) return;

            if (data.candles && data.candles.length > 0) {{
                rawCandles = data.candles;
                candleSeries.setData(data.candles);
                const last = data.candles[data.candles.length - 1];
                document.getElementById('l-close').innerText = last.close.toFixed(1);
            }}
            if (data.ema9 && data.ema9.length > 0) {{
                ema9Series.setData(data.ema9);
                document.getElementById('l-ema9').innerText = data.ema9[data.ema9.length - 1].value.toFixed(1);
            }}
            if (data.ema21 && data.ema21.length > 0) {{
                ema21Series.setData(data.ema21);
                document.getElementById('l-ema21').innerText = data.ema21[data.ema21.length - 1].value.toFixed(1);
            }}
            if (data.ema50 && data.ema50.length > 0) {{
                ema50Series.setData(data.ema50);
                document.getElementById('l-ema50').innerText = data.ema50[data.ema50.length - 1].value.toFixed(1);
            }}
            if (data.rsi && data.rsi.length > 0) {{
                rsiSeries.setData(data.rsi);
                document.getElementById('l-rsi').innerText = data.rsi[data.rsi.length - 1].value.toFixed(1);

                // Populate static RSI horizontal guideline bounds across the candle times
                const times = data.candles.map(c => c.time);
                // We don't need to re-add series repeatedly
            }}

            mainChart.timeScale().fitContent();
            rsiChart.timeScale().fitContent();
        }};

        window.updateLiveBar = function(candle, ema9Val, ema21Val, ema50Val, rsiVal) {{
            if (!mainChart || !candle) return;
            candleSeries.update(candle);
            document.getElementById('l-close').innerText = candle.close.toFixed(1);

            if (ema9Val !== undefined && ema9Val !== null) {{
                ema9Series.update({{ time: candle.time, value: ema9Val }});
                document.getElementById('l-ema9').innerText = ema9Val.toFixed(1);
            }}
            if (ema21Val !== undefined && ema21Val !== null) {{
                ema21Series.update({{ time: candle.time, value: ema21Val }});
                document.getElementById('l-ema21').innerText = ema21Val.toFixed(1);
            }}
            if (ema50Val !== undefined && ema50Val !== null) {{
                ema50Series.update({{ time: candle.time, value: ema50Val }});
                document.getElementById('l-ema50').innerText = ema50Val.toFixed(1);
            }}
            if (rsiVal !== undefined && rsiVal !== null) {{
                rsiSeries.update({{ time: candle.time, value: rsiVal }});
                document.getElementById('l-rsi').innerText = rsiVal.toFixed(1);
            }}
        }};

        window.fitContent = function() {{
            if (mainChart) mainChart.timeScale().fitContent();
            if (rsiChart) rsiChart.timeScale().fitContent();
        }};

        window.zoomRange = function(rangeType) {{
            if (!mainChart || rawCandles.length === 0) return;
            document.querySelectorAll('.tb-btn').forEach(b => b.classList.remove('active'));
            const n = rawCandles.length;
            let fromIdx = 0;
            if (rangeType === 'session') {{
                fromIdx = Math.max(0, n - 65);
                document.getElementById('btn-session').classList.add('active');
            }} else if (rangeType === '3d') {{
                fromIdx = Math.max(0, n - 130);
                document.getElementById('btn-3d').classList.add('active');
            }} else {{
                fromIdx = 0;
                document.getElementById('btn-all').classList.add('active');
            }}
            mainChart.timeScale().setVisibleLogicalRange({{ from: fromIdx, to: n + 2 }});
        }};

        window.onload = initCharts;
    </script>
</body>
</html>"""

