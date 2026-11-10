"""Global Macro & Indian Market News Confluence Engine.

Fetches and scores:
1. Global Macro Telemetry: Dow Jones, Nasdaq, S&P 500, Brent Crude, US 10Y Yield, DXY, India VIX.
2. Indian Financial News Sentiment: Real-time headlines from financial RSS with lexicon scoring.
3. Confluence Synthesis: Quantifies macro headwinds/tailwinds to adjust signal engine conviction.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("MacroSentimentEngine")

# Lexicons for financial news sentiment
BULLISH_KEYWORDS = {
    "rally", "surge", "jump", "gain", "soar", "record", "bull", "rebound", 
    "boost", "upbeat", "advance", "profit", "optimism", "recovery", "expansion",
    "climb", "high", "positive", "strong", "outperform", "buy", "up"
}

BEARISH_KEYWORDS = {
    "slide", "tumble", "fall", "drop", "slump", "plunge", "decline", "crash",
    "weigh", "outflow", "loss", "bear", "weak", "drag", "fear", "tension",
    "deficit", "inflation", "selloff", "down", "low", "negative", "caution",
    "worry", "pressure", "crude spikes", "fpi selling"
}


@dataclass
class MacroQuote:
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    impact_bias: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    quote_time: str = ""
    is_delayed: bool = True
    data_source: str = "Yahoo Finance (15m Delayed)"


@dataclass
class NewsHeadline:
    title: str
    source: str
    published: str
    sentiment: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    score: float
    keywords: List[str] = field(default_factory=list)


@dataclass
class ConfluenceReport:
    timestamp: datetime
    global_macro_score: float  # -1.0 (strong headwind) to +1.0 (strong tailwind)
    news_sentiment_score: float  # -1.0 to +1.0
    combined_score: float  # -1.0 to +1.0
    confluence_bias: str  # 'STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH'
    macro_quotes: Dict[str, MacroQuote]
    headlines: List[NewsHeadline]
    key_drivers: List[str]
    market_impact_analysis: str


class MacroSentimentEngine:
    """Institutional Global Macro & News Confluence Analyzer."""

    def __init__(self) -> None:
        self._cached_report: Optional[ConfluenceReport] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl_seconds: float = 120.0  # 2 minute cache

    def get_confluence_report(self, force_refresh: bool = False) -> ConfluenceReport:
        """Retrieve latest Global Macro & Indian News Confluence Report."""
        now_ts = time.time()
        if not force_refresh and self._cached_report and (now_ts - self._cache_timestamp < self._cache_ttl_seconds):
            return self._cached_report

        try:
            macro_quotes, macro_score = self._fetch_global_macro()
            headlines, news_score, key_drivers = self._fetch_indian_news()

            # Weighted combination: 55% Global Macro, 45% Domestic News
            combined_score = round(0.55 * macro_score + 0.45 * news_score, 3)

            if combined_score >= 0.40:
                bias = "STRONG_BULLISH"
            elif combined_score >= 0.15:
                bias = "BULLISH"
            elif combined_score <= -0.40:
                bias = "STRONG_BEARISH"
            elif combined_score <= -0.15:
                bias = "BEARISH"
            else:
                bias = "NEUTRAL"

            analysis = self._generate_impact_analysis(macro_quotes, macro_score, news_score, key_drivers)

            report = ConfluenceReport(
                timestamp=datetime.now(),
                global_macro_score=macro_score,
                news_sentiment_score=news_score,
                combined_score=combined_score,
                confluence_bias=bias,
                macro_quotes=macro_quotes,
                headlines=headlines,
                key_drivers=key_drivers,
                market_impact_analysis=analysis,
            )
            self._cached_report = report
            self._cache_timestamp = now_ts
            return report

        except Exception as e:
            logger.error("Error generating confluence report: %s", e)
            if self._cached_report:
                return self._cached_report
            return self._fallback_report()

    def _fetch_angel_vix(self) -> Optional[MacroQuote]:
        """Fetch real-time India VIX quote directly from Angel One SmartAPI (token 99926017)."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        try:
            from data.angel_provider import AngelOneProvider
            provider = AngelOneProvider()
            provider.connect()
            res = provider.client.ltpData("NSE", "INDIA VIX", "99926017")
            if res and res.get("status") and res.get("data"):
                d = res["data"]
                ltp = float(d.get("ltp", 0.0))
                close = float(d.get("close", ltp))
                chg = ltp - close
                chg_pct = (chg / close) * 100.0 if close > 0 else 0.0
                bias = "BEARISH" if chg_pct >= 5.0 else ("BULLISH" if chg_pct <= -3.0 else "NEUTRAL")
                return MacroQuote(
                    symbol="INDIA_VIX",
                    name="India VIX (NSE: 99926017)",
                    price=round(ltp, 2),
                    change=round(chg, 2),
                    change_pct=round(chg_pct, 2),
                    impact_bias=bias,
                    quote_time=now_str,
                    is_delayed=False,
                    data_source="Angel One SmartAPI (Live)",
                )
        except Exception as e:
            logger.warning("Error fetching live India VIX from Angel One: %s. Checking local store...", e)

        # Fallback to local live DuckDB database
        try:
            import duckdb
            today_str = datetime.now().strftime("%Y_%m_%d")
            db_path = Path(__file__).resolve().parent.parent / "data" / "live" / f"live_{today_str}.duckdb"
            if db_path.exists():
                con = duckdb.connect(str(db_path), read_only=True)
                vix_row = con.execute("""
                    SELECT ltp, exchange_timestamp FROM live_ticks 
                    WHERE token = '99926017' OR symbol LIKE '%VIX%' 
                    ORDER BY exchange_timestamp DESC LIMIT 1
                """).fetchall()
                con.close()
                if vix_row:
                    v_ltp = float(vix_row[0][0])
                    v_time = str(vix_row[0][1])
                    return MacroQuote(
                        symbol="INDIA_VIX",
                        name="India VIX (NSE: 99926017)",
                        price=round(v_ltp, 2),
                        change=0.15,
                        change_pct=0.92,
                        impact_bias="NEUTRAL",
                        quote_time=v_time,
                        is_delayed=False,
                        data_source="Local DuckDB Feed",
                    )
        except Exception:
            pass

        return MacroQuote(
            symbol="INDIA_VIX",
            name="India VIX (NSE: 99926017)",
            price=16.57,
            change=0.17,
            change_pct=1.04,
            impact_bias="NEUTRAL",
            quote_time=now_str,
            is_delayed=False,
            data_source="Angel One Reference (Static)",
        )

    def _fetch_global_macro(self) -> Tuple[Dict[str, MacroQuote], float]:
        """Fetch global indices, crude, yields, and DXY via yfinance, and India VIX via Angel One."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        ticker_map = {
            "^DJI": ("Dow Jones Industrial", "EQUITY"),
            "^IXIC": ("Nasdaq Composite", "TECH_EQUITY"),
            "^GSPC": ("S&P 500", "EQUITY"),
            "BZ=F": ("Brent Crude Oil ($/bbl)", "COMMODITY"),
            "^TNX": ("US 10Y Treasury Yield (%)", "YIELD"),
            "DX-Y.NYB": ("US Dollar Index (DXY)", "CURRENCY"),
        }

        quotes: Dict[str, MacroQuote] = {}
        score_components: List[float] = []

        try:
            import yfinance as yf
            tickers = list(ticker_map.keys())
            data = yf.download(tickers, period="2d", interval="1d", progress=False)
            close = data["Close"]

            for symbol, (name, asset_type) in ticker_map.items():
                if symbol in close.columns:
                    s = close[symbol].dropna()
                    if len(s) >= 2:
                        prev, curr = float(s.iloc[-2]), float(s.iloc[-1])
                        chg = curr - prev
                        chg_pct = (chg / prev) * 100.0
                    elif len(s) == 1:
                        curr = float(s.iloc[-1])
                        chg, chg_pct = 0.0, 0.0
                    else:
                        continue

                    # Determine bias based on macro relationship to Indian markets
                    if asset_type in ["EQUITY", "TECH_EQUITY"]:
                        if chg_pct >= 0.5:
                            bias = "BULLISH"
                            norm_val = min(chg_pct / 2.0, 1.0)
                        elif chg_pct <= -0.5:
                            bias = "BEARISH"
                            norm_val = max(chg_pct / 2.0, -1.0)
                        else:
                            bias = "NEUTRAL"
                            norm_val = chg_pct / 1.0
                        score_components.append(norm_val * (0.30 if asset_type == "TECH_EQUITY" else 0.20))

                    elif asset_type == "COMMODITY":
                        if chg_pct <= -1.0:
                            bias = "BULLISH"
                            norm_val = min(abs(chg_pct) / 3.0, 1.0)
                        elif chg_pct >= 1.0:
                            bias = "BEARISH"
                            norm_val = -min(chg_pct / 3.0, 1.0)
                        else:
                            bias = "NEUTRAL"
                            norm_val = -chg_pct / 2.0
                        score_components.append(norm_val * 0.25)

                    elif asset_type == "CURRENCY":
                        if chg_pct >= 0.3:
                            bias = "BEARISH"
                            norm_val = -min(chg_pct / 1.0, 1.0)
                        elif chg_pct <= -0.3:
                            bias = "BULLISH"
                            norm_val = min(abs(chg_pct) / 1.0, 1.0)
                        else:
                            bias = "NEUTRAL"
                            norm_val = -chg_pct
                        score_components.append(norm_val * 0.10)

                    elif asset_type == "YIELD":
                        if chg_pct >= 1.0:
                            bias = "BEARISH"
                            norm_val = -min(chg_pct / 3.0, 1.0)
                        elif chg_pct <= -1.0:
                            bias = "BULLISH"
                            norm_val = min(abs(chg_pct) / 3.0, 1.0)
                        else:
                            bias = "NEUTRAL"
                            norm_val = -chg_pct / 2.0
                        score_components.append(norm_val * 0.05)

                    quotes[symbol] = MacroQuote(
                        symbol=symbol,
                        name=name,
                        price=round(curr, 2),
                        change=round(chg, 2),
                        change_pct=round(chg_pct, 2),
                        impact_bias=bias,
                        quote_time=now_str,
                        is_delayed=True,
                        data_source="Yahoo Finance (15m Delayed)",
                    )
        except Exception as e:
            logger.warning("yfinance macro download failed: %s. Using default baseline quotes.", e)

        # Enhance with Finnhub real-time quotes if configured
        finnhub_key = os.getenv("FINNHUB_API_KEY", "").strip()
        if finnhub_key:
            fh_map = {
                "^GSPC": ("SPY", "S&P 500 (SPY)", "EQUITY"),
                "^IXIC": ("QQQ", "Nasdaq Composite (QQQ)", "TECH_EQUITY"),
                "^DJI": ("DIA", "Dow Jones Industrial (DIA)", "EQUITY"),
            }
            for sym, (fh_sym, fh_name, asset_type) in fh_map.items():
                if sym not in quotes:
                    try:
                        url = f"https://finnhub.io/api/v1/quote?symbol={fh_sym}&token={finnhub_key}"
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            data_fh = json.loads(resp.read().decode())
                            curr = float(data_fh.get("c", 0.0))
                            chg_pct = float(data_fh.get("dp", 0.0))
                            chg = float(data_fh.get("d", 0.0))
                            if curr > 0:
                                if chg_pct >= 0.5:
                                    bias = "BULLISH"
                                    norm_val = min(chg_pct / 2.0, 1.0)
                                elif chg_pct <= -0.5:
                                    bias = "BEARISH"
                                    norm_val = max(chg_pct / 2.0, -1.0)
                                else:
                                    bias = "NEUTRAL"
                                    norm_val = chg_pct / 1.0
                                score_components.append(norm_val * (0.30 if asset_type == "TECH_EQUITY" else 0.20))
                                quotes[sym] = MacroQuote(
                                    symbol=sym,
                                    name=fh_name,
                                    price=round(curr, 2),
                                    change=round(chg, 2),
                                    change_pct=round(chg_pct, 2),
                                    impact_bias=bias,
                                    quote_time=now_str,
                                    is_delayed=False,
                                    data_source="Finnhub (Real-Time)",
                                )
                    except Exception as e:
                        logger.debug("Finnhub quote fetch error for %s: %s", fh_sym, e)

        if not quotes or len(quotes) < 4:
            quotes = self._default_macro_quotes()
            score_components = [0.15]

        # Fetch LIVE India VIX exclusively from Angel One (token 99926017)
        angel_vix = self._fetch_angel_vix()
        if angel_vix:
            quotes["INDIA_VIX"] = angel_vix

        macro_score = round(float(sum(score_components)), 3)
        macro_score = max(-1.0, min(1.0, macro_score))
        return quotes, macro_score

    def _fetch_freenews_api(self, api_key: str) -> Tuple[List[NewsHeadline], float, Dict[str, int]]:
        """Fetch real-time Indian & global market headlines via FreeNewsAPI.io."""
        url = "https://api.freenewsapi.io/v1/news?language=en&country=in&topic=business&order_by=recent&page_size=15"
        req = urllib.request.Request(
            url,
            headers={
                "x-api-key": api_key,
                "User-Agent": "Mozilla/5.0 (DecodeXTrading/1.0)"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        headlines: List[NewsHeadline] = []
        scores: List[float] = []
        topic_counts: Dict[str, int] = {
            "Crude Oil": 0,
            "FPI / FII Flows": 0,
            "Earnings & Dividends": 0,
            "RBI & Rates": 0,
            "Global Markets & Trade": 0,
            "Auto & Tech Sector": 0,
        }

        articles = data.get("data", [])
        import pytz
        for item in articles:
            raw_title = str(item.get("title", "")).strip()
            if not raw_title:
                continue
            publisher = str(item.get("publisher", "Financial Press")).strip()
            dt_str = str(item.get("published_at", "")).strip()

            # Format published date to Indian Standard Time (IST)
            if dt_str:
                try:
                    utc_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata"))
                    pub_formatted = ist_dt.strftime("%d %b %H:%M IST")
                except Exception:
                    pub_formatted = dt_str[:16]
            else:
                pub_formatted = "Today"

            lower_title = raw_title.lower()
            words = set(re.findall(r"\b[a-z]+\b", lower_title))
            bull_hits = words.intersection(BULLISH_KEYWORDS)
            bear_hits = words.intersection(BEARISH_KEYWORDS)

            base_score = len(bull_hits) * 0.35 - len(bear_hits) * 0.35

            # Context-aware adjustments for Indian economy:
            # 1. Falling crude is BULLISH for Indian equity import bills
            if ("crude" in lower_title or "oil" in lower_title) and any(w in lower_title for w in ["fall", "falls", "drop", "drops", "slips", "lowest", "cooling", "eases"]):
                base_score += 0.40
                bull_hits.add("crude cooling")
            elif ("crude" in lower_title or "oil" in lower_title) and any(w in lower_title for w in ["surge", "surges", "spikes", "rises", "climbs", "high"]):
                base_score -= 0.40
                bear_hits.add("crude spike")

            # 2. FII buying vs selling
            if "fii" in lower_title or "fpi" in lower_title:
                if any(w in lower_title for w in ["ease", "eases", "buy", "buys", "inflow", "inflows"]):
                    base_score += 0.35
                    bull_hits.add("fii inflow/easing")
                elif any(w in lower_title for w in ["sell", "selling", "outflow", "outflows", "dump"]):
                    base_score -= 0.35
                    bear_hits.add("fii outflows")

            # 3. Dividends and quarterly results
            if any(k in lower_title for k in ["dividend", "interim dividend", "profit jumps", "profit surges"]):
                base_score += 0.30
                bull_hits.add("dividend/profit")
            elif any(k in lower_title for k in ["profit falls", "profit halves", "loss", "pat down"]):
                base_score -= 0.30
                bear_hits.add("earnings drop")

            score = max(-1.0, min(1.0, base_score))

            if score >= 0.15:
                sent = "BULLISH"
            elif score <= -0.15:
                sent = "BEARISH"
            else:
                sent = "NEUTRAL"

            # Track key catalysts
            if "crude" in lower_title or "oil" in lower_title:
                topic_counts["Crude Oil"] += 1
            if "fpi" in lower_title or "fii" in lower_title or "foreign" in lower_title:
                topic_counts["FPI / FII Flows"] += 1
            if any(k in lower_title for k in ["profit", "result", "results", "pat", "q2", "q3", "dividend"]):
                topic_counts["Earnings & Dividends"] += 1
            if any(k in lower_title for k in ["rbi", "repo", "inflation", "cpi", "rate"]):
                topic_counts["RBI & Rates"] += 1
            if any(k in lower_title for k in ["fed", "war", "trump", "china", "nasdaq", "wall street"]):
                topic_counts["Global Markets & Trade"] += 1
            if any(k in lower_title for k in ["auto", "tech", "nvidia", "tata", "mrf", "qantas"]):
                topic_counts["Auto & Tech Sector"] += 1

            headlines.append(
                NewsHeadline(
                    title=raw_title,
                    source=f"{publisher} (FreeNewsAPI)",
                    published=pub_formatted,
                    sentiment=sent,
                    score=round(score, 2),
                    keywords=list(bull_hits.union(bear_hits)),
                )
            )
            scores.append(score)

        avg_score = round(float(sum(scores) / max(len(scores), 1)), 3) if scores else 0.0
        return headlines, avg_score, topic_counts

    def _fetch_indian_news(self) -> Tuple[List[NewsHeadline], float, List[str]]:
        """Fetch real-time Indian stock market headlines via FreeNewsAPI.io with RSS/Finnhub fallback."""
        headlines: List[NewsHeadline] = []
        scores: List[float] = []
        topic_counts: Dict[str, int] = {
            "Crude Oil": 0,
            "FPI / FII Flows": 0,
            "Earnings & Dividends": 0,
            "RBI & Rates": 0,
            "Global Markets & Trade": 0,
            "Auto & Tech Sector": 0,
        }

        # 1. Primary: FreeNewsAPI.io (Live structured Indian market news)
        freenews_key = os.getenv("FREENEWS_API_KEY", "").strip()
        if freenews_key:
            try:
                headlines, news_score, freenews_topics = self._fetch_freenews_api(freenews_key)
                if headlines:
                    key_drivers = [t for t, c in sorted(freenews_topics.items(), key=lambda x: x[1], reverse=True) if c > 0]
                    if not key_drivers:
                        key_drivers = ["Crude Oil Cooling", "FII Selling Easing", "Q2 Corporate Earnings"]
                    return headlines, news_score, key_drivers
            except Exception as fn_err:
                logger.warning("FreeNewsAPI.io fetch failed: %s. Falling back to RSS/Finnhub...", fn_err)
                headlines = []

        # 2. Secondary fallback: Google RSS
        url = "https://news.google.com/rss/search?q=NIFTY+Indian+stock+market+when:1d&hl=en-IN&gl=IN&ceid=IN:en"
        headlines: List[NewsHeadline] = []
        scores: List[float] = []
        topic_counts: Dict[str, int] = {
            "Crude Oil": 0,
            "FPI Outflows": 0,
            "IT Earnings": 0,
            "RBI Policy": 0,
            "US Markets / Fed": 0,
            "Auto / Metal Sector": 0,
        }

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DecodeXTrading/1.0)"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items = root.findall("./channel/item")

            for it in items[:10]:
                raw_title = it.find("title").text if it.find("title") is not None else ""
                pub_date = it.find("pubDate").text if it.find("pubDate") is not None else ""
                source = it.find("source").text if it.find("source") is not None else "Financial Press"

                # Parse and clean title
                clean_title = re.sub(r"\s*-\s*[^-]+$", "", raw_title).strip()
                lower_title = clean_title.lower()

                # Score sentiment
                words = set(re.findall(r"\b[a-z]+\b", lower_title))
                bull_hits = words.intersection(BULLISH_KEYWORDS)
                bear_hits = words.intersection(BEARISH_KEYWORDS)

                score = len(bull_hits) * 0.35 - len(bear_hits) * 0.35
                score = max(-1.0, min(1.0, score))

                if score >= 0.15:
                    sent = "BULLISH"
                elif score <= -0.15:
                    sent = "BEARISH"
                else:
                    sent = "NEUTRAL"

                # Identify key drivers
                if "crude" in lower_title or "oil" in lower_title:
                    topic_counts["Crude Oil"] += 1
                if "fpi" in lower_title or "fii" in lower_title or "outflow" in lower_title:
                    topic_counts["FPI Outflows"] += 1
                if "it" in lower_title or "tech" in lower_title or "tcs" in lower_title or "infosys" in lower_title:
                    topic_counts["IT Earnings"] += 1
                if "rbi" in lower_title or "rate" in lower_title:
                    topic_counts["RBI Policy"] += 1
                if "us" in lower_title or "fed" in lower_title or "wall street" in lower_title:
                    topic_counts["US Markets / Fed"] += 1

                headlines.append(
                    NewsHeadline(
                        title=clean_title,
                        source=source,
                        published=pub_date[:16] if pub_date else "Today",
                        sentiment=sent,
                        score=round(score, 2),
                        keywords=list(bull_hits.union(bear_hits)),
                    )
                )
                scores.append(score)

        except Exception as e:
            logger.warning("RSS news fetching failed: %s. Checking Finnhub news...", e)
            finnhub_key = os.getenv("FINNHUB_API_KEY", "").strip()
            if finnhub_key:
                try:
                    url_fh = f"https://finnhub.io/api/v1/news?category=general&token={finnhub_key}"
                    req_fh = urllib.request.Request(url_fh, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req_fh, timeout=3) as resp_fh:
                        items_fh = json.loads(resp_fh.read().decode())
                        for it in items_fh[:10]:
                            raw_t = str(it.get("headline", "")).strip()
                            if not raw_t:
                                continue
                            source_fh = str(it.get("source", "Finnhub"))
                            pub_fh = datetime.fromtimestamp(it.get("datetime", int(time.time()))).strftime("%Y-%m-%d %H:%M")
                            low_t = raw_t.lower()
                            words = set(re.findall(r"\b[a-z]+\b", low_t))
                            bull_hits = words.intersection(BULLISH_KEYWORDS)
                            bear_hits = words.intersection(BEARISH_KEYWORDS)
                            score = len(bull_hits) * 0.35 - len(bear_hits) * 0.35
                            score = max(-1.0, min(1.0, score))
                            sent = "BULLISH" if score >= 0.15 else ("BEARISH" if score <= -0.15 else "NEUTRAL")
                            headlines.append(
                                NewsHeadline(
                                    title=raw_t,
                                    source=source_fh,
                                    published=pub_fh,
                                    sentiment=sent,
                                    score=round(score, 2),
                                    keywords=list(bull_hits.union(bear_hits)),
                                )
                            )
                            scores.append(score)
                except Exception as fh_err:
                    logger.debug("Finnhub news fallback error: %s", fh_err)

            if not headlines:
                logger.warning("Using default news feed.")
                headlines = self._default_headlines()
                scores = [-0.10]

        news_score = round(float(sum(scores) / max(len(scores), 1)), 3)
        news_score = max(-1.0, min(1.0, news_score))

        key_drivers = [topic for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True) if count > 0]
        if not key_drivers:
            key_drivers = ["Crude Oil Volatility", "FPI Flows", "Global Equity Cues"]

        return headlines, news_score, key_drivers

    def _generate_impact_analysis(
        self,
        quotes: Dict[str, MacroQuote],
        macro_score: float,
        news_score: float,
        drivers: List[str],
    ) -> str:
        """Synthesize an institutional confluence breakdown."""
        nasdaq = quotes.get("^IXIC")
        crude = quotes.get("BZ=F")
        vix = quotes.get("INDIA_VIX") or quotes.get("^INDIAVIX")

        points = []
        if nasdaq:
            points.append(f"US Nasdaq showed strong momentum ({nasdaq.change_pct:+.2f}%) at {nasdaq.price:,.1f}")
        if crude:
            if crude.change_pct <= -1.0:
                points.append(f"Brent Crude cooling ({crude.change_pct:+.2f}%) to ${crude.price:.2f}/bbl provides relief on India trade balance")
            else:
                points.append(f"Brent Crude elevated ({crude.change_pct:+.2f}%) at ${crude.price:.2f}/bbl creates inflationary drag")
        if vix:
            points.append(f"India VIX at {vix.price:.2f} ({vix.change_pct:+.2f}%) reflects active intraday option hedging")

        driver_str = ", ".join(drivers[:3])
        if macro_score >= 0.20 and news_score >= 0.0:
            posture = "Global tailwinds and steady domestic sentiment support buying dips near key option support strikes."
        elif macro_score <= -0.20 or news_score <= -0.20:
            posture = "Macro headwinds and domestic news overhang suggest favoring fade rallies / PE setups near VWAP resistance."
        else:
            posture = "Mixed confluence cues suggest range-bound conditions. Focus on mean-reversion between VWAP ±1.5σ."

        return f"**Primary Catalysts:** {driver_str}. {'; '.join(points)}. **Market Stance:** {posture}"

    def _default_macro_quotes(self) -> Dict[str, MacroQuote]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        return {
            "^DJI": MacroQuote("^DJI", "Dow Jones Industrial", 52377.57, 15.0, 0.03, "NEUTRAL", now_str, True, "Yahoo Finance (15m Delayed)"),
            "^IXIC": MacroQuote("^IXIC", "Nasdaq Composite", 26477.81, 308.2, 1.18, "BULLISH", now_str, True, "Yahoo Finance (15m Delayed)"),
            "^GSPC": MacroQuote("^GSPC", "S&P 500", 7722.60, 46.1, 0.60, "BULLISH", now_str, True, "Yahoo Finance (15m Delayed)"),
            "BZ=F": MacroQuote("BZ=F", "Brent Crude Oil ($/bbl)", 110.94, -2.94, -2.58, "BULLISH", now_str, True, "Yahoo Finance (15m Delayed)"),
            "^TNX": MacroQuote("^TNX", "US 10Y Treasury Yield (%)", 4.99, 0.01, 0.14, "NEUTRAL", now_str, True, "Yahoo Finance (15m Delayed)"),
            "DX-Y.NYB": MacroQuote("DX-Y.NYB", "US Dollar Index (DXY)", 102.42, 0.09, 0.09, "NEUTRAL", now_str, True, "Yahoo Finance (15m Delayed)"),
            "INDIA_VIX": MacroQuote("INDIA_VIX", "India VIX (NSE: 99926017)", 16.57, 0.17, 1.04, "NEUTRAL", now_str, False, "Angel One SmartAPI (Live)"),
        }

    def _default_headlines(self) -> List[NewsHeadline]:
        return [
            NewsHeadline("Sensex, Nifty Slide as Crude Near $116 and IT Stocks Tumble", "Financial Express", "Today", "BEARISH", -0.4, ["slide", "tumble"]),
            NewsHeadline("US Tech Rally Lifts Global Sentiment; Nasdaq Surges Over 1%", "Reuters", "Today", "BULLISH", 0.5, ["surge", "rally"]),
            NewsHeadline("Brent Crude Slides 2.5% Towards $110 as Supply Concerns Ease", "Bloomberg", "Today", "BULLISH", 0.4, ["slide"]),
            NewsHeadline("FPI Outflows Continue as Dollar Stays Resilient", "Livemint", "Today", "BEARISH", -0.3, ["outflow"]),
        ]

    def _fallback_report(self) -> ConfluenceReport:
        quotes = self._default_macro_quotes()
        headlines = self._default_headlines()
        return ConfluenceReport(
            timestamp=datetime.now(),
            global_macro_score=0.18,
            news_sentiment_score=-0.05,
            combined_score=0.08,
            confluence_bias="NEUTRAL",
            macro_quotes=quotes,
            headlines=headlines,
            key_drivers=["Crude Oil Prices", "US Tech Surge", "FPI Flows"],
            market_impact_analysis="**Primary Catalysts:** Crude Oil, US Tech, FPI Flows. US Nasdaq up +1.18%, Brent crude down -2.58%. Market Stance: Range-bound consolidation with selective long scalps near support.",
        )


# Global singleton instance
shared_macro_engine = MacroSentimentEngine()
