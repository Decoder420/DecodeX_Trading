"""Unit tests for Intraday Data and Interactive 15m Candlestick Charting."""

import pandas as pd
import pytest
from dashboard.charting import build_15m_candlestick_figure
from dashboard.intraday_data import get_live_15m_candles, load_base_15m_candles
from signals.engine import IntradaySignalEngine, SignalState, TradeAction


def test_base_15m_candles_generation():
    candles = load_base_15m_candles("NIFTY", "2026-10-26")
    assert not candles.empty
    assert len(candles) == 25
    assert "open" in candles.columns
    assert "high" in candles.columns
    assert "low" in candles.columns
    assert "close" in candles.columns
    assert "ema_21" in candles.columns
    assert "ema_50" in candles.columns


def test_live_15m_candles_in_memory_update():
    candles = get_live_15m_candles("NIFTY", "2026-10-26", live_ltp=22780.0)
    assert not candles.empty
    last_row = candles.iloc[-1]
    assert float(last_row["close"]) == 22780.0
    assert float(last_row["high"]) >= 22780.0


def test_build_15m_candlestick_figure_bullish_rr():
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(
        spot_price=22750.0,
        ema_21=22710.0,
        ema_50=22670.0,
        adx_14=29.0,
        atr_14=125.0,
        pcr_oi=1.22,
        max_pain=22750.0,
        futures_basis=54.0,
        account_equity=1000000.0,
        risk_pct=1.0,
        atr_multiplier=1.5,
    )
    candles = get_live_15m_candles("NIFTY", "2026-10-26", live_ltp=22750.0)
    sig_df = engine.generate_intraday_log(plan, "2026-10-26")
    
    fig = build_15m_candlestick_figure(
        df_candles=candles,
        trade_plan=plan,
        signal_log_df=sig_df,
        max_pain_strike=22750.0,
        atr_val=125.0,
        ltp_change=45.0,
    )

    # Check figure composition
    assert fig is not None
    assert len(fig.data) >= 3  # Candlestick, EMA21, EMA50, markers
    assert len(fig.layout.shapes) >= 4  # Entry box, SL box, T1 box, T2 box
    assert len(fig.layout.annotations) >= 4  # LTP, Max Pain, SL, T1, T2


def test_option_premium_guardrail_fields():
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(
        spot_price=22750.0,
        ema_21=22710.0,
        ema_50=22670.0,
        adx_14=29.0,
        atr_14=125.0,
        pcr_oi=1.22,
        account_equity=1000000.0,
        risk_pct=1.0,
    )
    assert plan.option_delta == 0.50
    assert plan.option_entry_ltp > 0.0
    assert plan.option_stop_loss < plan.option_entry_ltp
    assert plan.option_target_1 > plan.option_entry_ltp
    assert plan.option_target_2 > plan.option_target_1
    assert plan.option_risk_pts > 0.0


def test_intraday_atr_and_tight_chart_viewport():
    """Verify Intraday ATR scaling to 15m bar (~59.2 pts), realistic Trade Plan and Option SL/Targets, and tight Y-axis."""
    engine = IntradaySignalEngine("NIFTY")
    daily_atr = 295.8
    # 15m candle ATR = daily_atr * 0.20 = 59.16 (~59.2 pts)
    intraday_atr = round(daily_atr * 0.20, 2)
    assert abs(intraday_atr - 59.16) < 0.01

    plan = engine.compute_signal(
        spot_price=22753.2,
        ema_21=22780.0,
        ema_50=22810.0,
        adx_14=28.5,
        atr_14=intraday_atr,
        pcr_oi=1.127,
        max_pain=22750.0,
        futures_basis=17.7,
        account_equity=1000000.0,
        risk_pct=1.0,
        atr_multiplier=1.5,
    )

    # 1. Verify Stop Loss and Targets
    assert plan.state in (SignalState.SELL, SignalState.STRONG_SELL)
    assert abs(plan.stop_distance_pts - 88.7) < 0.1
    assert abs(plan.stop_loss - 22841.9) < 0.2
    assert abs(plan.target_1 - 22620.1) < 0.2
    assert abs(plan.target_2 - 22531.4) < 0.2

    # 2. Verify Dual Option Premium Bar translation
    assert abs(plan.option_entry_ltp - 266.2) < 0.1
    assert abs(plan.option_stop_loss - 221.8) < 0.2
    assert abs(plan.option_target_1 - 332.8) < 0.2
    assert abs(plan.option_target_2 - 377.1) < 0.2

    # 3. Verify Plotly Y-axis tight framing
    candles = get_live_15m_candles("NIFTY", "2026-10-26", live_ltp=22753.2)
    sig_df = engine.generate_intraday_log(plan, "2026-10-26")
    fig = build_15m_candlestick_figure(
        df_candles=candles,
        trade_plan=plan,
        signal_log_df=sig_df,
        max_pain_strike=22750.0,
        atr_val=intraday_atr,
        ltp_change=53.2,
    )
    y_min, y_max = fig.layout.yaxis.range
    candle_low_min = float(candles["low"].min())
    candle_high_max = float(candles["high"].max())

    # Dynamic 6.5% buffer on top and bottom (5-8% requirement)
    expected_pad = round((max(candle_high_max, plan.stop_loss) - min(candle_low_min, plan.target_2)) * 0.065, 1)
    expected_min = min(candle_low_min, plan.target_2) - expected_pad
    expected_max = max(candle_high_max, plan.stop_loss) + expected_pad
    assert abs(y_min - expected_min) < 0.5
    assert abs(y_max - expected_max) < 0.5
    # Ensure total Y-span is tightly framed (~513 pts around authentic session), NOT the bloated 1600 pts
    assert (y_max - y_min) < 550.0


def test_tradingview_html_serialization():
    """Verify TradingView Lightweight Charts HTML5 Canvas component structure and serialization."""
    from dashboard.tradingview_chart import build_tradingview_html

    engine = IntradaySignalEngine("NIFTY")
    daily_atr = 295.8
    intraday_atr = round(daily_atr * 0.20, 2)
    plan = engine.compute_signal(
        spot_price=22753.2,
        ema_21=22780.0,
        ema_50=22810.0,
        adx_14=28.5,
        atr_14=intraday_atr,
        pcr_oi=1.127,
        max_pain=22750.0,
        futures_basis=17.7,
        account_equity=1000000.0,
        risk_pct=1.0,
        atr_multiplier=1.5,
    )
    candles = get_live_15m_candles("NIFTY", "2026-10-26", live_ltp=22753.2)
    sig_df = engine.generate_intraday_log(plan, "2026-10-26")

    html = build_tradingview_html(
        candles_df=candles,
        signal_log_df=sig_df,
        plan=plan,
        spot_ltp=22753.2,
        max_pain=22750.0,
        instrument="NIFTY",
    )

    # 1. Verification of Library and Theme
    assert "lightweight-charts@4.2.0" in html
    assert "LightweightCharts.createChart" in html
    assert "CrosshairMode.Normal" in html
    assert "rightOffset: 14" in html
    assert "#0B0E14" in html

    # 2. Verification of Colors and Palette
    assert "#089981" in html  # Emerald
    assert "#F23645" in html  # Crimson
    assert "#00E5FF" in html  # EMA 21 Cyan
    assert "#FF9100" in html  # EMA 50 Orange

    # 3. Verification of Native Price Lines (Price Pills)
    assert "createPriceLine" in html
    assert "Max Pain" in html
    assert "ENTRY (Spot)" in html
    assert "'SL | Opt ₹' + planData.option_stop_loss" in html
    assert '"option_stop_loss": 221.8' in html
    assert '"option_target_1": 332.8' in html
    assert '"option_target_2": 377.1' in html

    # 4. Verification of Native Markers
    assert "setMarkers" in html
    assert "BUY" in html or "SELL" in html

    # 5. Verification of RR Shaded Overlay and Controls
    assert "rr-canvas" in html
    assert "tv-legend" in html
    assert "btn-fit" in html
    assert "btn-realtime" in html
    assert "rgba(242, 54, 69, 0.22)" in html  # Risk zone fill
    assert "rgba(8, 153, 129, 0.20)" in html   # T1 zone fill
    assert "rgba(0, 230, 118, 0.28)" in html  # T2 zone fill


def test_multi_timeframe_pipeline_and_atr_scaling():
    """Verify multi-timeframe candle synthesis, technical indicators, and ATR scaling across 1m, 3m, 5m, 15m, 1H."""
    from dashboard.intraday_data import get_live_multi_day_candles, TIMEFRAME_CONFIG

    timeframes = ["1m", "3m", "5m", "15m", "1H"]
    prev_atr = 0.0

    for tf in timeframes:
        cfg = TIMEFRAME_CONFIG[tf]
        candles = get_live_multi_day_candles(instrument="NIFTY", timeframe=tf, date_str="2026-10-26", live_ltp=22753.2)
        assert not candles.empty
        # Verify bar count is at least 80% of expected bars across lookback days
        assert len(candles) >= int(cfg["approx_bars"] * 0.8)

        # Verify indicators computed
        for col in ["open", "high", "low", "close", "ema_9", "ema_21", "ema_50", "ema_200", "supertrend", "rsi_14", "macd_hist", "adx_14", "atr_14"]:
            assert col in candles.columns
            assert not candles[col].dropna().empty

        # Rule 7: Index volume is 0.0 and index Session VWAP is NaN (hidden)
        assert (candles["volume"] == 0.0).all()
        assert candles["vwap"].isna().all()

        current_atr = float(candles["atr_14"].dropna().iloc[-1])
        assert current_atr > 0.0
        # Verify ATR increases monotonically with higher timeframes (1m < 3m < 5m < 15m < 1H)
        assert current_atr > prev_atr
        prev_atr = current_atr


def test_tradingview_2pane_and_toolbar_toggles():
    """Verify 2-pane structure (530px + 180px), interactive toolbar buttons, and breakeven/hard SL lines."""
    from dashboard.tradingview_chart import build_tradingview_html
    from dashboard.intraday_data import get_live_multi_day_candles

    engine = IntradaySignalEngine("NIFTY")
    candles_1m = get_live_multi_day_candles(instrument="NIFTY", timeframe="1m", date_str="2026-10-26", live_ltp=22753.2)
    plan = engine.compute_6factor_signal(candles_df=candles_1m, timeframe="1m", account_equity=50000.0, risk_pct=1.0)

    # Set plan to Stage 1 to test Breakeven badge
    plan.stage = 1
    plan.stage_label = "STAGE 1: BREAKEVEN LOCK"
    plan.is_account_risk_mismatch = True
    plan.hard_capital_sl = 22737.8

    html = build_tradingview_html(
        candles_df=candles_1m,
        signal_log_df=pd.DataFrame(),
        plan=plan,
        spot_ltp=22753.2,
        max_pain=22750.0,
        instrument="NIFTY",
        timeframe="1m",
    )

    # Toolbar buttons
    assert "btn-1d" in html
    assert "btn-3d" in html
    assert "btn-5d" in html
    assert "btn-all" in html
    assert "btn-realtime" in html
    assert "btn-toggle-vol" in html
    assert "btn-toggle-ema" in html
    assert "btn-toggle-st" in html
    assert "btn-toggle-vwap" in html
    assert "btn-toggle-rr" in html
    assert "btn-toggle-sig" in html
    assert "volumeSeries" in html
    assert "watermark" in html

    # 2-pane layout
    assert "main-pane-wrapper" in html
    assert "530px" in html
    assert "lower-pane-wrapper" in html
    assert "180px" in html
    assert "lower-chart" in html
    assert "RSI (14)" in html
    assert "MACD Hist" in html

    # Breakeven lock pill and Hard Capital SL
    assert "BREAKEVEN" in html
    assert "Hard Cap SL" in html


def test_generate_chart_uirevision_key():
    """Verify that uirevision key includes instrument, timeframe, and expiry."""
    from dashboard.charting import generate_chart_uirevision

    key1 = generate_chart_uirevision("NIFTY", "15m", "03NOV2026")
    assert key1 == "NIFTY_15m_03NOV2026_chart_state"

    key2 = generate_chart_uirevision("banknifty", "1d", "23nov2026")
    assert key2 == "BANKNIFTY_1d_23NOV2026_chart_state"

    key3 = generate_chart_uirevision("SENSEX", "5m", None)
    assert key3 == "SENSEX_5m_CURRENT_chart_state"


def test_chart_refresh_does_not_reapply_tight_y_bounds():
    """Verify that initial render applies tight Y-axis bounds, but refresh leaves bounds open for zoom/pan."""
    from dashboard.charting import build_15m_candlestick_figure
    from dashboard.intraday_data import get_live_15m_candles

    engine = IntradaySignalEngine("NIFTY")
    intraday_atr = 59.16
    plan = engine.compute_signal(
        spot_price=22753.2,
        ema_21=22780.0,
        ema_50=22810.0,
        adx_14=28.5,
        atr_14=intraday_atr,
        account_equity=1000000.0,
    )
    candles = get_live_15m_candles("NIFTY", "2026-10-26", live_ltp=22753.2)
    sig_df = engine.generate_intraday_log(plan, "2026-10-26")

    # Initial Render: is_refresh = False -> Tight bounds must be applied
    fig_initial = build_15m_candlestick_figure(
        df_candles=candles,
        trade_plan=plan,
        signal_log_df=sig_df,
        instrument="NIFTY",
        timeframe="15m",
        expiry="03NOV2026",
        is_refresh=False,
    )
    assert fig_initial.layout.uirevision == "NIFTY_15m_03NOV2026_chart_state"
    assert fig_initial.layout.yaxis.range is not None
    assert len(fig_initial.layout.yaxis.range) == 2
    assert fig_initial.layout.xaxis.range is not None
    assert len(fig_initial.layout.xaxis.range) == 2
    assert "09:15:00" in fig_initial.layout.xaxis.range[0]
    assert "15:30:00" in fig_initial.layout.xaxis.range[1]
    assert fig_initial.layout.legend.orientation == "h"
    assert fig_initial.layout.legend.y == 1.04
    assert fig_initial.layout.margin.t == 50

    # Fragment Refresh: is_refresh = True -> Preserves uirevision and maintains tight 1D viewport without 23,200 blowup
    fig_refresh = build_15m_candlestick_figure(
        df_candles=candles,
        trade_plan=plan,
        signal_log_df=sig_df,
        instrument="NIFTY",
        timeframe="15m",
        expiry="03NOV2026",
        is_refresh=True,
    )
    assert fig_refresh.layout.uirevision == "NIFTY_15m_03NOV2026_chart_state"
    assert fig_refresh.layout.yaxis.range is not None
    assert fig_refresh.layout.yaxis.autorange is False
    assert len(fig_refresh.layout.yaxis.range) == 2
    assert fig_refresh.layout.updatemenus is not None
    assert len(fig_refresh.layout.updatemenus[0].buttons) == 4
    button_labels = [b.label for b in fig_refresh.layout.updatemenus[0].buttons]
    assert button_labels == ["1D", "3D", "5D", "ALL"]


def test_calculate_tight_y_axis_bounds_helper():
    """Verify standalone tight Y-axis bounding calculation helper."""
    from dashboard.charting import calculate_tight_y_axis_bounds
    from dashboard.intraday_data import get_live_15m_candles

    candles = get_live_15m_candles("NIFTY", "2026-10-26", live_ltp=22753.2)
    c_low = float(candles["low"].min())
    c_high = float(candles["high"].max())

    y_min, y_max = calculate_tight_y_axis_bounds(candles, trade_plan=None, padding_pts=30.0)
    assert abs(y_min - (c_low - 30.0)) < 0.1
    assert abs(y_max - (c_high + 30.0)) < 0.1




