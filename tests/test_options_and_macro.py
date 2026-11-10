"""Tests for Options Chain, Full Greeks, Dynamic Expiries, and Macro News Confluence."""

from datetime import date, datetime
import pytest
import pandas as pd

from dashboard.options_chain import get_available_expiries, load_options_chain_data
from recorder.engine import LiveRecorderEngine
from recorder.storage import LiveStorageManager
from signals.macro_sentiment import shared_macro_engine, ConfluenceReport
from signals.engine import IntradaySignalEngine, SignalState, TradeAction, TradePlan



def test_dynamic_expiries_nifty_future_only():
    """Verify expiries returned are future dates (no stale expired contracts)."""
    today = date(2026, 10, 28)
    expiries = get_available_expiries("NIFTY")
    assert len(expiries) > 0
    # First expiry should be >= today
    first_exp_str = expiries[0][0]
    first_dt = datetime.strptime(first_exp_str, "%d%b%Y").date()
    assert first_dt >= today
    # Expiry 27OCT2026 should not be present as near weekly
    assert first_exp_str != "27OCT2026"


def test_options_chain_data_loader_structure():
    """Verify options chain produces matrix with full Call/Put Greeks, PCR, and Max Pain."""
    spot_price = 22550.0
    chain = load_options_chain_data("NIFTY", "03NOV2026", spot_price=spot_price, window_strikes=5)

    assert "matrix_df" in chain
    assert isinstance(chain["matrix_df"], pd.DataFrame)
    assert not chain["matrix_df"].empty

    # Columns check
    cols = chain["matrix_df"].columns
    assert "Call Delta (Δ)" in cols
    assert "Call Gamma (Γ)" in cols
    assert "Call Theta (Θ/d)" in cols
    assert "Call IV%" in cols
    assert "STRIKE" in cols
    assert "Put Delta (Δ)" in cols
    assert "Put Gamma (Γ)" in cols
    assert "Put Theta (Θ/d)" in cols
    assert "Put IV%" in cols

    # Metrics check
    assert chain["pcr_oi"] is not None and chain["pcr_oi"] > 0
    assert chain["max_pain"] is not None and 20000 <= chain["max_pain"] <= 25000
    assert 0.40 <= abs(chain["atm_call_delta"]) <= 0.65
    assert -0.65 <= chain["atm_put_delta"] <= -0.40
    assert chain["daily_theta_cost_inr"] > 0

    # Live exchange telemetry metadata check
    assert "feed_type" in chain
    assert "feed_badge_color" in chain
    assert "last_option_tick_time" in chain
    assert "is_synthetic" in chain
    assert chain["is_synthetic"] is False
    assert "Live NFO" in chain["feed_type"]
    assert chain["real_strikes_count"] > 0


def test_recorder_option_tokens_subscription(tmp_path):
    """Verify LiveRecorderEngine resolves 30 active NFO option tokens (ATM ± 7) and maps symbols."""
    storage = LiveStorageManager(base_dir=str(tmp_path / "live"))
    recorder = LiveRecorderEngine(storage_mgr=storage)
    
    tokens = recorder._resolve_active_option_tokens("NIFTY", window_strikes=7)
    assert len(tokens) == 30  # 15 CE + 15 PE
    
    assert len(recorder.option_tokens_meta) == 30
    for tok, meta in recorder.option_tokens_meta.items():
        assert meta["symbol"].startswith("NIFTY")
        assert meta["instrument_type"] == "OPTIDX"
        assert meta["option_type"] in ["CE", "PE"]
        assert meta["strike"] > 0
        
        # Verify symbol and instrument mapping
        sym, itype = recorder._token_to_symbol(tok)
        assert sym == meta["symbol"]
        assert itype == "OPTIDX"


def test_macro_sentiment_engine_report():
    """Verify macro sentiment engine produces institutional report with quotes & headlines."""
    report = shared_macro_engine.get_confluence_report()
    assert isinstance(report, ConfluenceReport)
    assert -1.0 <= report.global_macro_score <= 1.0
    assert -1.0 <= report.news_sentiment_score <= 1.0
    assert -1.0 <= report.combined_score <= 1.0
    assert report.confluence_bias in ["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]
    assert len(report.macro_quotes) >= 4
    assert len(report.key_drivers) > 0
    assert len(report.market_impact_analysis) > 20


def test_signal_engine_factor_7_macro_confluence():
    """Verify Factor 7 adjusts score and reasons when macro news score is supplied."""
    engine = IntradaySignalEngine("NIFTY")
    
    # Base neutral calculation
    base_plan = engine.compute_signal(
        spot_price=22550.0,
        ema_9=22550.0,
        ema_21=22550.0,
        ema_50=22550.0,
        ema_200=22550.0,
        supertrend=22550.0,
        supertrend_direction=1,
        vwap=22550.0,
        vwap_upper_1_5=22580.0,
        vwap_lower_1_5=22520.0,
        rsi_14=50.0,
        macd_hist=0.0,
        adx_14=25.0,
        squeeze_on=False,
        atr_14=30.0,
        macro_news_score=0.0,
    )

    # Bullish macro tailwind calculation
    bull_plan = engine.compute_signal(
        spot_price=22550.0,
        ema_9=22550.0,
        ema_21=22550.0,
        ema_50=22550.0,
        ema_200=22550.0,
        supertrend=22550.0,
        supertrend_direction=1,
        vwap=22550.0,
        vwap_upper_1_5=22580.0,
        vwap_lower_1_5=22520.0,
        rsi_14=50.0,
        macd_hist=0.0,
        adx_14=25.0,
        squeeze_on=False,
        atr_14=30.0,
        macro_news_score=0.35,
        macro_confluence_bias="BULLISH",
    )

    # Per 2010-2024 walk-forward econometric validation, macro is unweighted in score (0.00 weight)
    assert bull_plan.score == base_plan.score
    assert any("Global Macro & News Context (Unweighted)" in r for r in bull_plan.reasons)
    assert bull_plan.macro_news_score == 0.35
    assert bull_plan.macro_confluence_bias == "BULLISH"


def test_signal_engine_real_greeks_option_pricing():
    """Verify TradePlan translates spot risk to option risk using real live Greeks."""
    engine = IntradaySignalEngine("NIFTY")
    
    plan = engine.compute_signal(
        spot_price=22550.0,
        ema_9=22570.0,
        ema_21=22550.0,
        ema_50=22530.0,
        ema_200=22480.0,
        supertrend=22520.0,
        supertrend_direction=1,
        vwap=22545.0,
        vwap_upper_1_5=22585.0,
        vwap_lower_1_5=22505.0,
        rsi_14=62.0,
        macd_hist=2.5,
        macd_hist_rising=True,
        adx_14=28.0,
        squeeze_on=False,
        atr_14=35.0,
        live_atm_delta=0.525,
        live_atm_ltp=185.0,
        live_atm_theta=-16.8,
        live_atm_gamma=0.00085,
        live_atm_iv=16.2,
        active_expiry="03NOV2026",
    )

    assert plan.option_delta == 0.525
    assert plan.option_entry_ltp == 185.0
    assert plan.option_theta_decay == -16.8
    assert plan.contract_expiry == "03NOV2026"
    assert plan.option_stop_loss < 185.0
    assert plan.option_target_1 > 185.0


def test_freenews_api_parsing_and_fallback(monkeypatch):
    """Verify FreeNewsAPI.io parses real-time headlines with Indian market context and falls back gracefully."""
    import json
    from signals.macro_sentiment import MacroSentimentEngine

    engine = MacroSentimentEngine()
    fake_json = {
        "data": [
            {
                "uuid": "fake-1",
                "title": "Brent Crude Falls Below $90 Providing Major Relief to Indian Markets",
                "published_at": "2026-11-10T10:00:00.000Z",
                "publisher": "The Economic Times"
            },
            {
                "uuid": "fake-2",
                "title": "FII Selling Eases as IT Stocks Jump on Strong Earnings",
                "published_at": "2026-11-10T10:15:00.000Z",
                "publisher": "BusinessLine"
            }
        ]
    }

    class MockResp:
        def read(self):
            return json.dumps(fake_json).encode()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=5: MockResp())
    headlines, score, topics = engine._fetch_freenews_api("mock_key")

    assert len(headlines) == 2
    assert headlines[0].source == "The Economic Times (FreeNewsAPI)"
    assert headlines[0].sentiment == "BULLISH"
    assert "IST" in headlines[0].published
    assert score > 0.0
    assert topics["Crude Oil"] == 1
    assert topics["FPI / FII Flows"] == 1
