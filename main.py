"""DecodeX Trading — Native Desktop Quantitative Execution Terminal.

Role:
- Main PyQt6 Desktop Application Window powered by embedded TradingView Lightweight Charts (QWebEngineView).
- Built natively for macOS (Apple Silicon / M-Series) with High-DPI Retina scaling.
- Connects to DecodeXDataWorker (QThread) to receive real-time ticks, 5-level depth, MTF signals, and live news.
- Ultra-low latency split-pane layout:
    * Top View: 15-Minute Structural Frame (TradingView Candlesticks, Anchored VWAP, Supertrend 10, 2.5).
    * Bottom View: 3-Minute Execution Frame (TradingView Candlesticks, EMA Ribbon 9/21/50, Squeeze Metrics, RSI 14).
    * Right Panel: Tabbed Institutional Telemetry:
        - Tab 1: Execution Telemetry (6-Factor MTF Confluence Gate, L2 Depth & OBI Matrix, Real-Time Options Chain Grid).
        - Tab 2: Live Market News & Macro Confluence (Real-Time Indian News Feed, Global Macro Tickers, Sentiment Breakdown).
        - Tab 3: Risk Management & Quant Governance (Dynamic Position Sizing, 3-Stage Breakeven Lock, Risk Guards, Toggles).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("DecodeXTerminal")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure Qt plugin path and remove macOS hidden file flags
qt_plugins = PROJECT_ROOT / ".venv" / "lib" / "python3.12" / "site-packages" / "PyQt6" / "Qt6" / "plugins"
if qt_plugins.exists():
    if sys.platform == "darwin":
        try:
            subprocess.run(["chflags", "-R", "0", str(qt_plugins)], capture_output=True)
            subprocess.run(["xattr", "-rc", str(qt_plugins)], capture_output=True)
        except Exception:
            pass
    os.environ["QT_PLUGIN_PATH"] = str(qt_plugins)
    if "QT_QPA_PLATFORM_PLUGIN_PATH" in os.environ:
        del os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"]

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QUrl, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPixmap
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from dashboard.tradingview_bridge import get_tradingview_15m_html, get_tradingview_3m_html
from worker import DecodeXDataWorker


# =============================================================================
# FORMATTING UTILITIES FOR INSTITUTIONAL TELEMETRY
# =============================================================================

def format_oi(val: Any) -> str:
    """Format Open Interest / COI deltas with clean institutional abbreviations (e.g. +48k, -120k)."""
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
    """Format quantities cleanly without overflowing table cells."""
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
# MAIN DECODEX TRADING APPLICATION WINDOW
# =============================================================================

class DecodeXMainWindow(QMainWindow):
    """DecodeX Trading Institutional Multi-Timeframe Quant Terminal."""

    def __init__(self):
        super().__init__()

        # Critical Naming Directive & Window Icon
        self.setWindowTitle("DecodeX Trading — Institutional Multi-Timeframe Quant Terminal")
        icon_path = str(PROJECT_ROOT / "assets" / "decodex_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.resize(1740, 1040)
        self.setMinimumSize(1280, 800)

        # State Variables
        self.current_instrument = "NIFTY"
        self.current_expiry = "17NOV2026"
        self.spot_price = 25044.65
        self.current_obi = 0.0
        self.last_signal = "CONFLUENCE WAIT"

        # Risk Management State
        self.account_equity = 1_000_000.0
        self.risk_pct = 1.0
        self.atr_mult = 1.5
        self.enable_sound_chime = True
        self.enable_hard_sl = True

        # WebEngine chart readiness and cached data
        self._chart_15m_ready = False
        self._chart_3m_ready = False
        self._last_p15 = None
        self._last_p3 = None

        # Indicator values cache for live tick updates
        self.last_vwap = self.spot_price
        self.last_st = self.spot_price
        self.last_ema9 = self.spot_price
        self.last_ema21 = self.spot_price
        self.last_ema50 = self.spot_price
        self.last_rsi = 50.0

        # Build UI Architecture
        self._setup_institutional_theme()
        self._build_ui_layout()

        # Launch Isolated Background Worker Thread
        self.worker = DecodeXDataWorker(
            instrument=self.current_instrument,
            active_expiry=self.current_expiry,
        )
        self._wire_worker_signals()
        self.worker.start()

    # =========================================================================
    # INSTITUTIONAL TRADINGVIEW DARK THEME (macOS / Retina Optimized)
    # =========================================================================

    def _setup_institutional_theme(self) -> None:
        """Apply modern TradingView Dark Mode institutional QSS styling."""
        qss = """
        QMainWindow {
            background-color: #131722;
        }
        QWidget {
            color: #D1D4DC;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
        }
        QFrame#card {
            background-color: #1E222D;
            border: 1px solid #2A2E39;
            border-radius: 8px;
            padding: 6px;
        }
        QFrame#highlight_card {
            background-color: #1E222D;
            border: 1px solid #363A45;
            border-radius: 8px;
            padding: 8px;
        }
        QLabel#title {
            font-size: 18px;
            font-weight: 700;
            color: #F8FAFC;
            letter-spacing: 0.5px;
        }
        QLabel#subtitle {
            font-size: 11px;
            color: #787B86;
            font-weight: 500;
        }
        QLabel#metric_val {
            font-family: "SF Mono", "Menlo", "Consolas", monospace;
            font-size: 22px;
            font-weight: 800;
            color: #F8FAFC;
            letter-spacing: -0.5px;
        }
        QLabel#status_badge {
            background-color: rgba(8, 153, 129, 0.15);
            border: 1px solid #089981;
            color: #089981;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 11px;
            font-weight: 700;
        }
        QComboBox {
            background-color: #2A2E39;
            border: 1px solid #363A45;
            border-radius: 6px;
            padding: 4px 10px;
            color: #F8FAFC;
            font-weight: 600;
            font-size: 12px;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 6px;
        }
        QComboBox QAbstractItemView {
            background-color: #1E222D;
            border: 1px solid #363A45;
            selection-background-color: #2A2E39;
            selection-color: #00E5FF;
            color: #D1D4DC;
            padding: 4px;
        }
        QTabWidget::pane {
            border: 1px solid #2A2E39;
            border-radius: 8px;
            background-color: #1E222D;
            padding: 6px;
        }
        QTabBar::tab {
            background: #181B24;
            color: #787B86;
            font-weight: 700;
            font-size: 11px;
            padding: 7px 14px;
            margin-right: 4px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border: 1px solid #2A2E39;
            border-bottom: none;
        }
        QTabBar::tab:selected {
            background: #1E222D;
            color: #00E5FF;
            border-bottom: 2px solid #00E5FF;
        }
        QTabBar::tab:hover:!selected {
            background: #222632;
            color: #D1D4DC;
        }
        QTableWidget {
            background-color: #1E222D;
            border: none;
            border-radius: 6px;
            gridline-color: transparent;
            font-family: "SF Mono", "Menlo", "Consolas", monospace;
            font-size: 11px;
            color: #D1D4DC;
        }
        QTableWidget::item {
            border-bottom: 1px solid #2A2E39;
            border-top: none;
            border-left: none;
            border-right: none;
            padding: 2px 4px;
        }
        QTableWidget::item:selected {
            background-color: #2A2E39;
        }
        QHeaderView::section {
            background-color: #2A2E39;
            color: #787B86;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
            font-weight: 700;
            font-size: 10px;
            border: none;
            border-bottom: 1px solid #363A45;
            padding: 4px 4px;
            text-transform: uppercase;
        }
        QScrollBar:vertical {
            background-color: #1E222D;
            width: 6px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background-color: #2A2E39;
            border-radius: 3px;
            min-height: 20px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QSplitter::handle {
            background-color: #131722;
        }
        QSlider::groove:horizontal {
            height: 4px;
            background: #2A2E39;
            border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: #2962FF;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #00E5FF;
            border: 1px solid #2962FF;
            width: 14px;
            margin-top: -5px;
            margin-bottom: -5px;
            border-radius: 7px;
        }
        QProgressBar {
            background-color: #2A2E39;
            border: 1px solid #363A45;
            border-radius: 4px;
            text-align: center;
            font-size: 10px;
            font-weight: 700;
            color: #F8FAFC;
            height: 14px;
        }
        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #089981, stop:1 #00E5FF);
            border-radius: 3px;
        }
        QCheckBox {
            spacing: 8px;
            font-size: 12px;
            font-weight: 600;
            color: #D1D4DC;
        }
        QCheckBox::indicator {
            width: 15px;
            height: 15px;
            border-radius: 3px;
            border: 1px solid #363A45;
            background: #2A2E39;
        }
        QCheckBox::indicator:checked {
            background: #2962FF;
            border-color: #00E5FF;
        }
        """
        self.setStyleSheet(qss)

    # =========================================================================
    # UI COMPOSITION (SPLIT-PANE + CHARTS + TELEMETRY + OPTIONS CHAIN + NEWS)
    # =========================================================================

    def _build_ui_layout(self) -> None:
        """Compose split-pane layout with TradingView WebEngine charts (70%) and telemetry tabs (30%)."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # 1. Top Header Bar
        main_layout.addWidget(self._build_header_bar())

        # 2. Main Work Area (Splitter: Charts on Left 70%, Telemetry on Right 30%)
        work_splitter = QSplitter(Qt.Orientation.Horizontal)
        work_splitter.setHandleWidth(5)

        # Left: Vertical Chart Splitter (15m Top Chart + 3m Bottom Chart)
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(6)

        self.chart_splitter = QSplitter(Qt.Orientation.Vertical)
        self.chart_splitter.setHandleWidth(5)

        # Setup Top 15m Structural Chart (TradingView QWebEngineView)
        self.chart_15m_view = QWebEngineView()
        self.chart_15m_view.setStyleSheet("background-color: #1E222D; border-radius: 8px;")
        self.chart_15m_view.loadFinished.connect(self._on_15m_chart_loaded)
        self.chart_15m_view.setHtml(get_tradingview_15m_html(), QUrl("http://localhost"))
        self.chart_splitter.addWidget(self.chart_15m_view)

        # Setup Bottom 3m Execution Chart with Integrated RSI (TradingView QWebEngineView)
        self.chart_3m_view = QWebEngineView()
        self.chart_3m_view.setStyleSheet("background-color: #1E222D; border-radius: 8px;")
        self.chart_3m_view.loadFinished.connect(self._on_3m_chart_loaded)
        self.chart_3m_view.setHtml(get_tradingview_3m_html(), QUrl("http://localhost"))
        self.chart_splitter.addWidget(self.chart_3m_view)

        chart_layout.addWidget(self.chart_splitter)
        work_splitter.addWidget(chart_container)

        # Right: Institutional Telemetry & Control Tabs
        work_splitter.addWidget(self._build_right_tabs_panel())

        # Set splitter proportions: 70% Charts, 30% Right Panel
        work_splitter.setStretchFactor(0, 70)
        work_splitter.setStretchFactor(1, 30)

        # Vertical chart proportions: 48% 15m, 52% 3m
        self.chart_splitter.setStretchFactor(0, 48)
        self.chart_splitter.setStretchFactor(1, 52)

        main_layout.addWidget(work_splitter)

    # =========================================================================
    # HEADER BAR & BRANDING
    # =========================================================================

    def _build_header_bar(self) -> QWidget:
        header = QFrame()
        header.setObjectName("card")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(14)

        # DecodeX Official Logo
        logo_path = str(PROJECT_ROOT / "assets" / "decodex_logo_full.png")
        if os.path.exists(logo_path):
            logo_pix = QPixmap(logo_path)
            if not logo_pix.isNull():
                scaled_logo = logo_pix.scaledToHeight(36, Qt.TransformationMode.SmoothTransformation)
                logo_lbl = QLabel()
                logo_lbl.setPixmap(scaled_logo)
                logo_lbl.setFixedHeight(36)
                layout.addWidget(logo_lbl)
            else:
                self._add_fallback_brand(layout)
        else:
            self._add_fallback_brand(layout)

        layout.addSpacing(10)

        # Instrument Selector
        inst_box = QHBoxLayout()
        inst_lbl = QLabel("Instrument:")
        inst_lbl.setStyleSheet("color: #787B86; font-size: 11px; font-weight: 600;")
        self.inst_combo = QComboBox()
        self.inst_combo.addItems(["NIFTY", "BANKNIFTY", "SENSEX"])
        self.inst_combo.setCurrentText(self.current_instrument)
        self.inst_combo.currentTextChanged.connect(self._on_instrument_changed)
        inst_box.addWidget(inst_lbl)
        inst_box.addWidget(self.inst_combo)
        layout.addLayout(inst_box)

        # Expiry Selector
        exp_box = QHBoxLayout()
        exp_lbl = QLabel("Expiry:")
        exp_lbl.setStyleSheet("color: #787B86; font-size: 11px; font-weight: 600;")
        self.expiry_combo = QComboBox()
        self.expiry_combo.addItems(["17NOV2026 (Near Weekly)", "24NOV2026 (Next Weekly)", "26NOV2026 (Monthly)"])
        exp_box.addWidget(exp_lbl)
        exp_box.addWidget(self.expiry_combo)
        layout.addLayout(exp_box)

        layout.addSpacing(16)

        # Live Spot Price Widget
        spot_box = QVBoxLayout()
        spot_box.setSpacing(1)
        self.spot_title_lbl = QLabel(f"{self.current_instrument} SPOT LTP")
        self.spot_title_lbl.setStyleSheet("font-size: 10px; color: #787B86; font-weight: 700; letter-spacing: 0.5px;")
        self.spot_price_lbl = QLabel(f"₹{self.spot_price:,.2f}")
        self.spot_price_lbl.setObjectName("metric_val")
        spot_box.addWidget(self.spot_title_lbl)
        spot_box.addWidget(self.spot_price_lbl)
        layout.addLayout(spot_box)

        layout.addStretch()

        # Macro Sentiment Pill
        self.macro_header_badge = QLabel("🌐 Macro: Neutral (+0.00)")
        self.macro_header_badge.setStyleSheet(
            "background-color: rgba(42, 46, 57, 0.6); border: 1px solid #363A45; color: #CBD5E1; "
            "border-radius: 12px; padding: 4px 10px; font-weight: 700; font-size: 11px;"
        )
        layout.addWidget(self.macro_header_badge)

        # Connection Status Badge
        self.conn_badge = QLabel("🟢 Connected (Mode 3 FULL_SNAP Active | Tokens: 23)")
        self.conn_badge.setObjectName("status_badge")
        layout.addWidget(self.conn_badge)

        return header

    def _add_fallback_brand(self, layout: QHBoxLayout) -> None:
        brand_lbl = QLabel("⚡ DecodeX Trading")
        brand_lbl.setObjectName("title")
        sub_lbl = QLabel("Institutional Quant Terminal")
        sub_lbl.setObjectName("subtitle")
        brand_box = QVBoxLayout()
        brand_box.addWidget(brand_lbl)
        brand_box.addWidget(sub_lbl)
        layout.addLayout(brand_box)

    # =========================================================================
    # RIGHT TABBED PANEL (EXECUTION + LIVE NEWS + RISK CONTROLS)
    # =========================================================================

    def _build_right_tabs_panel(self) -> QWidget:
        """Create tabbed right-side panel with Execution, Live News, and Risk Controls."""
        self.tabs = QTabWidget()
        self.tab_widget = self.tabs

        # Tab 1: Execution Telemetry (Confluence + Depth + Options Grid)
        self.tabs.addTab(self._build_execution_tab(), "🎯 Execution")

        # Tab 2: Live Market News & Macro Confluence
        self.tabs.addTab(self._build_news_tab(), "📰 Market News")

        # Tab 3: Risk Management & Quant Governance
        self.tabs.addTab(self._build_risk_tab(), "🛡️ Risk & Controls")

        return self.tabs

    # -------------------------------------------------------------------------
    # TAB 1: EXECUTION TELEMETRY
    # -------------------------------------------------------------------------

    def _build_execution_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(8)

        # 1. 6-Factor MTF Confluence Card
        layout.addWidget(self._build_confluence_card())

        # 2. Level 2 Market Depth & Imbalance Card
        layout.addWidget(self._build_l2_depth_card())

        # 3. Real-Time Options Chain Grid Card
        layout.addWidget(self._build_options_chain_card())

        return panel

    def _build_confluence_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("highlight_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header
        h_layout = QHBoxLayout()
        title = QLabel("🎯 6-Factor MTF Confluence Gate")
        title.setStyleSheet("font-weight: 700; color: #F8FAFC; font-size: 12px; letter-spacing: 0.3px;")
        self.score_badge = QLabel("Score: +4.80")
        self.score_badge.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 700; color: #089981; font-size: 12px;')
        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(self.score_badge)
        layout.addLayout(h_layout)

        # Status Banner
        self.confluence_banner = QLabel("⚪ CONFLUENCE WAIT (CHOP / SQUEEZE FILTER)")
        self.confluence_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.confluence_banner.setStyleSheet(
            "background-color: rgba(42, 46, 57, 0.6); border: 1px solid #363A45; "
            "color: #D1D4DC; font-weight: 800; font-size: 13px; border-radius: 6px; padding: 7px;"
        )
        layout.addWidget(self.confluence_banner)

        # MTF Badges Grid
        badges_layout = QHBoxLayout()
        self.badge_15m = QLabel("15m Bias: BULLISH")
        self.badge_15m.setStyleSheet("background: rgba(8, 153, 129, 0.15); color: #089981; font-weight: 700; padding: 3px 8px; border-radius: 4px; font-size: 11px;")
        self.badge_3m = QLabel("3m Trigger: LONG")
        self.badge_3m.setStyleSheet("background: rgba(8, 153, 129, 0.15); color: #089981; font-weight: 700; padding: 3px 8px; border-radius: 4px; font-size: 11px;")
        badges_layout.addWidget(self.badge_15m)
        badges_layout.addWidget(self.badge_3m)
        layout.addLayout(badges_layout)

        # Suggested Trade Plan
        self.trade_plan_lbl = QLabel("Plan: Entry: ₹25,044.7 | SL: ₹24,978.0 | Target: ₹25,133.5 | R:R: 1:2.3")
        self.trade_plan_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-size: 11px; color: #94A3B8; font-weight: 500;')
        layout.addWidget(self.trade_plan_lbl)

        return card

    def _build_l2_depth_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header with OBI Readout
        h_layout = QHBoxLayout()
        title = QLabel("⚡ True L2 Depth & Microstructure")
        title.setStyleSheet("font-weight: 700; color: #F8FAFC; font-size: 12px; letter-spacing: 0.3px;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self.obi_lbl = QLabel("OBI: +0.28 (Heavy Buying)")
        self.obi_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 800; color: #089981; font-size: 12px;')
        h_layout.addWidget(self.obi_lbl)
        layout.addLayout(h_layout)

        # 5-Level Depth Table
        self.depth_table = QTableWidget(5, 6)
        self.depth_table.setHorizontalHeaderLabels(["BID ORDERS", "BID QTY", "BID PRICE", "ASK PRICE", "ASK QTY", "ASK ORDERS"])
        self.depth_table.setShowGrid(False)
        self.depth_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.depth_table.verticalHeader().setVisible(False)
        self.depth_table.verticalHeader().setDefaultSectionSize(22)
        self.depth_table.horizontalHeader().setFixedHeight(24)
        self.depth_table.setFixedHeight(138)
        layout.addWidget(self.depth_table)

        # Micro-price & Spread Footer
        self.spread_lbl = QLabel("Top Spread: 0.50 pts | Micro-Price: ₹25,044.80")
        self.spread_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-size: 11px; color: #787B86;')
        layout.addWidget(self.spread_lbl)

        return card

    def _build_options_chain_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header
        h_layout = QHBoxLayout()
        title = QLabel("📊 Options Chain Grid (ATM ± 200)")
        title.setStyleSheet("font-weight: 700; color: #F8FAFC; font-size: 12px; letter-spacing: 0.3px;")
        self.coi_delta_lbl = QLabel("Triad COI Δ: +48k (Bullish)")
        self.coi_delta_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 700; color: #089981; font-size: 12px;')
        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(self.coi_delta_lbl)
        layout.addLayout(h_layout)

        # Options Table
        self.options_table = QTableWidget(5, 9)
        self.options_table.setHorizontalHeaderLabels([
            "CE IV", "CE Δ", "CE COI", "CE OI", "STRIKE", "PE OI", "PE COI", "PE Δ", "PE IV"
        ])
        self.options_table.setShowGrid(False)
        self.options_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.options_table.verticalHeader().setVisible(False)
        self.options_table.verticalHeader().setDefaultSectionSize(22)
        self.options_table.horizontalHeader().setFixedHeight(24)
        self.options_table.setFixedHeight(138)
        layout.addWidget(self.options_table)

        return card

    # -------------------------------------------------------------------------
    # TAB 2: LIVE MARKET NEWS & MACRO CONFLUENCE
    # -------------------------------------------------------------------------

    def _build_news_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(8)

        # 1. Macro Impact Synthesis Card
        macro_card = QFrame()
        macro_card.setObjectName("highlight_card")
        m_layout = QVBoxLayout(macro_card)
        m_layout.setContentsMargins(10, 8, 10, 8)
        m_layout.setSpacing(6)

        h_box = QHBoxLayout()
        m_title = QLabel("🌐 Global Macro & Sentiment Confluence")
        m_title.setStyleSheet("font-weight: 700; color: #60A5FA; font-size: 12px;")
        self.news_bias_badge = QLabel("BIAS: BULLISH (+0.42)")
        self.news_bias_badge.setStyleSheet(
            "background: #00C853; color: white; font-weight: 800; font-size: 11px; padding: 3px 8px; border-radius: 10px;"
        )
        h_box.addWidget(m_title)
        h_box.addStretch()
        h_box.addWidget(self.news_bias_badge)
        m_layout.addLayout(h_box)

        self.macro_breakdown_lbl = QLabel("Global Macro: +0.35 | Domestic Sentiment: +0.50")
        self.macro_breakdown_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 500;")
        m_layout.addWidget(self.macro_breakdown_lbl)

        # Global Macro Tickers Grid (USD/INR, Brent Crude, US 10Y, GIFT NIFTY)
        self.macro_tickers_lbl = QLabel(
            "USD/INR: ₹84.38 (–0.12%) | Brent: $74.20 (+0.45%) | US 10Y: 4.42% (–0.03%)"
        )
        self.macro_tickers_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-size: 11px; color: #E2E8F0; font-weight: 600;')
        m_layout.addWidget(self.macro_tickers_lbl)

        self.catalysts_lbl = QLabel("Key Catalysts: FPI Inflows, Rate Pause, Strong Bank Earnings")
        self.catalysts_lbl.setStyleSheet("font-size: 11px; color: #38BDF8; font-weight: 600;")
        m_layout.addWidget(self.catalysts_lbl)

        layout.addWidget(macro_card)

        # 2. Scrollable Live Financial News Feed
        feed_card = QFrame()
        feed_card.setObjectName("card")
        f_layout = QVBoxLayout(feed_card)
        f_layout.setContentsMargins(10, 8, 10, 8)
        f_layout.setSpacing(6)

        feed_header = QHBoxLayout()
        feed_title = QLabel("📰 Live Indian Financial News Stream")
        feed_title.setStyleSheet("font-weight: 700; color: #F8FAFC; font-size: 12px;")
        feed_badge = QLabel("🟢 FreeNewsAPI.io / RSS")
        feed_badge.setStyleSheet("font-size: 10px; color: #00E676; font-weight: 600;")
        feed_header.addWidget(feed_title)
        feed_header.addStretch()
        feed_header.addWidget(feed_badge)
        f_layout.addLayout(feed_header)

        self.news_browser = QTextBrowser()
        self.news_browser.setOpenExternalLinks(True)
        self.news_browser.setStyleSheet(
            "background-color: #181B24; border: 1px solid #2A2E39; border-radius: 6px; "
            "color: #D1D4DC; font-size: 12px; padding: 6px;"
        )
        self._populate_default_news_view()
        f_layout.addWidget(self.news_browser)

        layout.addWidget(feed_card)
        return panel

    def _populate_default_news_view(self) -> None:
        """Render initial formatted HTML news headlines."""
        html = """
        <div style="font-family: -apple-system, sans-serif; line-height: 1.5;">
            <div style="background: #1E222D; border: 1px solid #2A2E39; border-radius: 6px; padding: 8px; margin-bottom: 8px;">
                <span style="background: rgba(8, 153, 129, 0.2); color: #089981; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px;">🟢 BULLISH</span>
                <span style="color: #787B86; font-size: 10px; margin-left: 6px;">Moneycontrol • Today</span>
                <div style="color: #F8FAFC; font-weight: 600; font-size: 12px; margin-top: 4px;">
                    Nifty breaches fresh resistance as institutional buying accelerates across banking and tech heavyweights.
                </div>
            </div>
            <div style="background: #1E222D; border: 1px solid #2A2E39; border-radius: 6px; padding: 8px; margin-bottom: 8px;">
                <span style="background: rgba(8, 153, 129, 0.2); color: #089981; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px;">🟢 BULLISH</span>
                <span style="color: #787B86; font-size: 10px; margin-left: 6px;">Economic Times • Today</span>
                <div style="color: #F8FAFC; font-weight: 600; font-size: 12px; margin-top: 4px;">
                    Crude prices cool toward $74/bbl easing domestic inflation worries; FPI flows turn net positive in cash market.
                </div>
            </div>
            <div style="background: #1E222D; border: 1px solid #2A2E39; border-radius: 6px; padding: 8px;">
                <span style="background: rgba(120, 123, 134, 0.2); color: #94A3B8; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px;">⚪ NEUTRAL</span>
                <span style="color: #787B86; font-size: 10px; margin-left: 6px;">LiveMint • Today</span>
                <div style="color: #F8FAFC; font-weight: 600; font-size: 12px; margin-top: 4px;">
                    RBI commentary highlights robust GDP growth trajectory while monitoring global central bank rate cues.
                </div>
            </div>
        </div>
        """
        self.news_browser.setHtml(html)

    # -------------------------------------------------------------------------
    # TAB 3: RISK MANAGEMENT & QUANT GOVERNANCE
    # -------------------------------------------------------------------------

    def _build_risk_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(8)

        # 1. Position Sizing & Capital Allocation Card
        sizing_card = QFrame()
        sizing_card.setObjectName("card")
        s_layout = QVBoxLayout(sizing_card)
        s_layout.setContentsMargins(12, 10, 12, 10)
        s_layout.setSpacing(8)

        s_title = QLabel("📐 Dynamic Position & Risk Sizing")
        s_title.setStyleSheet("font-weight: 700; color: #F8FAFC; font-size: 12px;")
        s_layout.addWidget(s_title)

        # Portfolio Capital
        cap_box = QHBoxLayout()
        cap_box.addWidget(QLabel("Account Equity (INR):"))
        self.equity_spin = QSpinBox()
        self.equity_spin.setRange(10_000, 10_000_000)
        self.equity_spin.setSingleStep(50_000)
        self.equity_spin.setValue(int(self.account_equity))
        self.equity_spin.valueChanged.connect(self._on_risk_params_changed)
        cap_box.addWidget(self.equity_spin)
        s_layout.addLayout(cap_box)

        # Risk per Trade Slider
        risk_box = QVBoxLayout()
        self.risk_pct_lbl = QLabel(f"Risk per Trade: {self.risk_pct:.2f}% (Max Risk: ₹{self.account_equity * self.risk_pct / 100:,.0f})")
        self.risk_pct_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #D1D4DC;")
        self.risk_slider = QSlider(Qt.Orientation.Horizontal)
        self.risk_slider.setRange(25, 300)  # 0.25% to 3.00%
        self.risk_slider.setValue(int(self.risk_pct * 100))
        self.risk_slider.valueChanged.connect(self._on_risk_params_changed)
        risk_box.addWidget(self.risk_pct_lbl)
        risk_box.addWidget(self.risk_slider)
        s_layout.addLayout(risk_box)

        # ATR Stop Multiplier Slider
        atr_box = QVBoxLayout()
        self.atr_mult_lbl = QLabel(f"ATR Stop Multiplier: {self.atr_mult:.2f}x")
        self.atr_mult_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #D1D4DC;")
        self.atr_slider = QSlider(Qt.Orientation.Horizontal)
        self.atr_slider.setRange(10, 30)  # 1.0x to 3.0x
        self.atr_slider.setValue(int(self.atr_mult * 10))
        self.atr_slider.valueChanged.connect(self._on_risk_params_changed)
        atr_box.addWidget(self.atr_mult_lbl)
        atr_box.addWidget(self.atr_slider)
        s_layout.addLayout(atr_box)

        # Dynamic Sizing Metrics Grid
        grid_metrics = QGridLayout()
        grid_metrics.addWidget(QLabel("Recommended Sizing:"), 0, 0)
        self.recommended_size_lbl = QLabel("65 Qty (1 Lot)")
        self.recommended_size_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 700; color: #00E5FF;')
        grid_metrics.addWidget(self.recommended_size_lbl, 0, 1)

        grid_metrics.addWidget(QLabel("Small-Account Guardrail:"), 1, 0)
        self.guardrail_lbl = QLabel("✅ SAFE (Within Risk Limit)")
        self.guardrail_lbl.setStyleSheet("font-weight: 700; color: #089981;")
        grid_metrics.addWidget(self.guardrail_lbl, 1, 1)

        s_layout.addLayout(grid_metrics)

        # Risk Allocation Progress Bar
        self.risk_pbar = QProgressBar()
        self.risk_pbar.setValue(int(self.risk_pct / 3.0 * 100))
        s_layout.addWidget(self.risk_pbar)

        layout.addWidget(sizing_card)

        # 2. Capital Protection & 3-Stage Breakeven Lock Card
        prot_card = QFrame()
        prot_card.setObjectName("highlight_card")
        p_layout = QVBoxLayout(prot_card)
        p_layout.setContentsMargins(12, 10, 12, 10)
        p_layout.setSpacing(8)

        p_title = QLabel("🛡️ Profit-Locking & Runner Trail")
        p_title.setStyleSheet("font-weight: 700; color: #F8FAFC; font-size: 12px;")
        p_layout.addWidget(p_title)

        self.stage_lbl = QLabel("Stage 0: Initial Risk (1.5x Structural ATR Stop)")
        self.stage_lbl.setStyleSheet(
            "background: rgba(41, 98, 255, 0.15); border: 1px solid #2962FF; color: #00E5FF; "
            "padding: 6px; border-radius: 4px; font-weight: 700; font-size: 11px;"
        )
        p_layout.addWidget(self.stage_lbl)

        # Safety & Strategy Toggles
        self.chk_hard_sl = QCheckBox("🛡️ Hard Capital Stop Loss Guardrail")
        self.chk_hard_sl.setChecked(True)
        p_layout.addWidget(self.chk_hard_sl)

        self.chk_class_b = QCheckBox("🧪 Show Experimental (Class B) Models")
        self.chk_class_b.setChecked(True)
        p_layout.addWidget(self.chk_class_b)

        self.chk_chime = QCheckBox("🔊 Play Sound Chime on Signal Change")
        self.chk_chime.setChecked(True)
        self.chk_chime.stateChanged.connect(lambda s: setattr(self, "enable_sound_chime", s == 2))
        p_layout.addWidget(self.chk_chime)

        test_chime_btn = QPushButton("🔔 Test Signal Chime")
        test_chime_btn.setStyleSheet(
            "background: #2A2E39; border: 1px solid #363A45; border-radius: 4px; padding: 4px; color: #F8FAFC; font-weight: 600;"
        )
        test_chime_btn.clicked.connect(self._play_chime)
        p_layout.addWidget(test_chime_btn)

        layout.addWidget(prot_card)
        layout.addStretch()

        return panel

    # =========================================================================
    # QT SIGNALS & REAL-TIME EVENT HANDLERS
    # =========================================================================

    def _wire_worker_signals(self) -> None:
        """Connect DecodeXDataWorker Qt signals to GUI update slots."""
        self.worker.tick_signal.connect(self.on_tick_received)
        self.worker.l2_depth_signal.connect(self.on_l2_depth_received)
        self.worker.mtf_signal.connect(self.on_mtf_updated)
        self.worker.options_chain_signal.connect(self.on_options_chain_updated)
        self.worker.news_sentiment_signal.connect(self.on_news_received)
        self.worker.connection_status_signal.connect(self.on_connection_status)

    @pyqtSlot(dict)
    def on_tick_received(self, tick: Dict[str, Any]) -> None:
        """Update live spot price and header metrics."""
        self.spot_price = tick["ltp"]
        self.spot_price_lbl.setText(f"₹{self.spot_price:,.2f}")

        # Bridge live tick candle update to TradingView charts via runJavaScript
        b15 = tick.get("bar_15m")
        if b15:
            js_15 = f"if (window.updateLiveBar) window.updateLiveBar({json.dumps(b15)}, {self.last_vwap}, {self.last_st});"
            self.chart_15m_view.page().runJavaScript(js_15)

        b3 = tick.get("bar_3m")
        if b3:
            js_3 = f"if (window.updateLiveBar) window.updateLiveBar({json.dumps(b3)}, {self.last_ema9}, {self.last_ema21}, {self.last_ema50}, {self.last_rsi});"
            self.chart_3m_view.page().runJavaScript(js_3)

    @pyqtSlot(dict)
    def on_l2_depth_received(self, depth: Dict[str, Any]) -> None:
        """Render 5-level market depth matrix and Order Book Imbalance (OBI)."""
        obi = depth.get("order_book_imbalance", 0.0)
        self.current_obi = obi

        if obi > 0.15:
            self.obi_lbl.setText(f"OBI: {obi:+.2f} (Heavy Buying)")
            self.obi_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 800; color: #089981; font-size: 12px;')
        elif obi < -0.15:
            self.obi_lbl.setText(f"OBI: {obi:+.2f} (Heavy Selling)")
            self.obi_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 800; color: #F23645; font-size: 12px;')
        else:
            self.obi_lbl.setText(f"OBI: {obi:+.2f} (Balanced)")
            self.obi_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 800; color: #787B86; font-size: 12px;')

        self.spread_lbl.setText(
            f"Top Spread: {depth.get('spread', 0):.2f} pts | Micro-Price: ₹{depth.get('micro_price', 0):,.2f}"
        )

        bids = depth.get("bids", [])
        asks = depth.get("asks", [])
        for i in range(5):
            b = bids[i] if i < len(bids) else {}
            a = asks[i] if i < len(asks) else {}

            self._set_table_item(self.depth_table, i, 0, str(b.get("orders", "—")), color="#787B86", align=Qt.AlignmentFlag.AlignCenter)
            self._set_table_item(self.depth_table, i, 1, format_qty(b.get('quantity', 0)), color="#089981")
            self._set_table_item(self.depth_table, i, 2, f"₹{b.get('price', 0):,.1f}", color="#089981", bold=True)

            self._set_table_item(self.depth_table, i, 3, f"₹{a.get('price', 0):,.1f}", color="#F23645", bold=True)
            self._set_table_item(self.depth_table, i, 4, format_qty(a.get('quantity', 0)), color="#F23645")
            self._set_table_item(self.depth_table, i, 5, str(a.get("orders", "—")), color="#787B86", align=Qt.AlignmentFlag.AlignCenter)

    def _on_15m_chart_loaded(self, ok: bool) -> None:
        """Handle 15m QWebEngineView loadFinished signal."""
        self._chart_15m_ready = ok
        if ok and self._last_p15:
            js_cmd_15 = f"if (window.setChartData) window.setChartData({json.dumps(self._last_p15)});"
            self.chart_15m_view.page().runJavaScript(js_cmd_15)

    def _on_3m_chart_loaded(self, ok: bool) -> None:
        """Handle 3m QWebEngineView loadFinished signal."""
        self._chart_3m_ready = ok
        if ok and self._last_p3:
            js_cmd_3 = f"if (window.setChartData) window.setChartData({json.dumps(self._last_p3)});"
            self.chart_3m_view.page().runJavaScript(js_cmd_3)

    @pyqtSlot(dict)
    def on_mtf_updated(self, mtf_data: Dict[str, Any]) -> None:
        """Update TradingView Lightweight Charts, Confluence Gate, and Risk telemetry."""
        # 1. Update 15m Structural Frame TradingView Chart via JS Bridge
        d15 = mtf_data.get("15m", {})
        candles_15m = d15.get("candles", [])
        vwap_data = d15.get("vwap_data", [])
        st_data = d15.get("supertrend_data", [])

        self.last_vwap = d15.get("anchored_vwap", self.spot_price)
        self.last_st = d15.get("supertrend", self.spot_price)

        if candles_15m:
            p15 = {"candles": candles_15m, "vwap": vwap_data, "supertrend": st_data}
            self._last_p15 = p15
            if self._chart_15m_ready:
                js_cmd_15 = f"if (window.setChartData) window.setChartData({json.dumps(p15)});"
                self.chart_15m_view.page().runJavaScript(js_cmd_15)

        # 2. Update 3m Execution Frame TradingView Chart via JS Bridge
        d3 = mtf_data.get("3m", {})
        candles_3m = d3.get("candles", [])
        e9_data = d3.get("ema9_data", [])
        e21_data = d3.get("ema21_data", [])
        e50_data = d3.get("ema50_data", [])
        rsi_data = d3.get("rsi_data", [])

        self.last_ema9 = d3.get("ema_9", self.spot_price)
        self.last_ema21 = d3.get("ema_21", self.spot_price)
        self.last_ema50 = d3.get("ema_50", self.spot_price)
        self.last_rsi = d3.get("rsi_14", 50.0)

        if candles_3m:
            p3 = {
                "candles": candles_3m,
                "ema9": e9_data,
                "ema21": e21_data,
                "ema50": e50_data,
                "rsi": rsi_data,
            }
            self._last_p3 = p3
            if self._chart_3m_ready:
                js_cmd_3 = f"if (window.setChartData) window.setChartData({json.dumps(p3)});"
                self.chart_3m_view.page().runJavaScript(js_cmd_3)

        # 3. Update Confluence Banner & Badges
        confl = mtf_data.get("confluence", {})
        sig = confl.get("signal", "CONFLUENCE WAIT")
        score = confl.get("score", 0.0)
        self.score_badge.setText(f"Score: {score:+.2f}")

        # Check for signal change chime
        if sig != self.last_signal:
            if "ENTRY" in sig and self.enable_sound_chime:
                self._play_chime()
            self.last_signal = sig

        if "BULLISH" in sig:
            self.confluence_banner.setText("🟢 BULLISH ENTRY (15m + 3m Converged)")
            self.confluence_banner.setStyleSheet(
                "background-color: rgba(8, 153, 129, 0.2); border: 1px solid #089981; "
                "color: #089981; font-weight: 800; font-size: 13px; border-radius: 6px; padding: 7px;"
            )
        elif "BEARISH" in sig:
            self.confluence_banner.setText("🔴 BEARISH ENTRY (15m + 3m Converged)")
            self.confluence_banner.setStyleSheet(
                "background-color: rgba(242, 54, 69, 0.2); border: 1px solid #F23645; "
                "color: #F23645; font-weight: 800; font-size: 13px; border-radius: 6px; padding: 7px;"
            )
        else:
            self.confluence_banner.setText("⚪ CONFLUENCE WAIT (CHOP / SQUEEZE FILTER)")
            self.confluence_banner.setStyleSheet(
                "background-color: rgba(42, 46, 57, 0.6); border: 1px solid #363A45; "
                "color: #D1D4DC; font-weight: 800; font-size: 13px; border-radius: 6px; padding: 7px;"
            )

        # Update Timeframe Badges
        bias_15 = d15.get("bias", "NEUTRAL")
        trig_3 = d3.get("trigger", "WAIT")
        self.badge_15m.setText(f"15m Bias: {bias_15}")
        self.badge_3m.setText(f"3m Trigger: {trig_3}")

        # Update Trade Plan & Position Sizing
        entry = confl.get("entry_price", self.spot_price)
        sl = confl.get("stop_loss", self.spot_price - 50)
        t1 = confl.get("target_1", self.spot_price + 80)
        self.trade_plan_lbl.setText(
            f"Plan: Entry: ₹{entry:,.1f} | SL: ₹{sl:,.1f} | Target: ₹{t1:,.1f} | R:R: {confl.get('risk_reward', '1:2.3')}"
        )

        # Dynamic Position Sizing Calculation
        sl_dist = abs(entry - sl)
        lot_size = 25 if self.current_instrument == "NIFTY" else 15
        max_risk_inr = self.account_equity * (self.risk_pct / 100.0)
        risk_per_lot = sl_dist * lot_size
        rec_lots = max(1, int(max_risk_inr / max(risk_per_lot, 1.0)))

        self.recommended_size_lbl.setText(f"{rec_lots * lot_size} Qty ({rec_lots} Lots)")
        if risk_per_lot > max_risk_inr * 1.2:
            self.guardrail_lbl.setText("⚠️ RISK OVERHANG (Reduce Lots)")
            self.guardrail_lbl.setStyleSheet("font-weight: 700; color: #F59E0B;")
        else:
            self.guardrail_lbl.setText("✅ SAFE (Within Risk Limit)")
            self.guardrail_lbl.setStyleSheet("font-weight: 700; color: #089981;")

    @pyqtSlot(dict)
    def on_options_chain_updated(self, opt_data: Dict[str, Any]) -> None:
        """Render Options Chain grid and highlight institutional writing walls."""
        strikes = opt_data.get("strikes", [])
        net_triad = opt_data.get("net_coi_delta_triad", 0.0)

        if net_triad > 0:
            self.coi_delta_lbl.setText(f"Triad COI Δ: {format_oi(net_triad)} (PE Writing / Support Floor)")
            self.coi_delta_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 700; color: #089981; font-size: 11px;')
        else:
            self.coi_delta_lbl.setText(f"Triad COI Δ: {format_oi(net_triad)} (CE Writing / Resistance Wall)")
            self.coi_delta_lbl.setStyleSheet('font-family: "SF Mono", monospace; font-weight: 700; color: #F23645; font-size: 11px;')

        for i, s in enumerate(strikes[:5]):
            self._set_table_item(self.options_table, i, 0, f"{s['ce_iv']:.1f}%", color="#94A3B8", align=Qt.AlignmentFlag.AlignCenter)
            self._set_table_item(self.options_table, i, 1, f"{s['ce_delta']:+.2f}", color="#089981" if s["ce_delta"] >= 0 else "#F23645", align=Qt.AlignmentFlag.AlignCenter)
            self._set_table_item(
                self.options_table, i, 2, format_oi(s["ce_coi"]),
                bg_color="#3B1214" if s["heavy_ce_writing"] else None,
                color="#F23645" if s["heavy_ce_writing"] else "#CBD5E1",
                bold=s["heavy_ce_writing"],
                align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._set_table_item(
                self.options_table, i, 3, format_qty(s["ce_oi"]),
                color="#D1D4DC",
                align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )

            is_atm = s.get("is_atm", False)
            self._set_table_item(
                self.options_table, i, 4, f"{s['strike']:,.0f}",
                bold=True,
                bg_color="#2A2E39" if is_atm else None,
                color="#F59E0B" if is_atm else "#F8FAFC",
                align=Qt.AlignmentFlag.AlignCenter,
            )

            self._set_table_item(
                self.options_table, i, 5, format_qty(s["pe_oi"]),
                color="#D1D4DC",
                align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self._set_table_item(
                self.options_table, i, 6, format_oi(s["pe_coi"]),
                bg_color="#0F2D1E" if s["heavy_pe_writing"] else None,
                color="#089981" if s["heavy_pe_writing"] else "#CBD5E1",
                bold=s["heavy_pe_writing"],
                align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self._set_table_item(self.options_table, i, 7, f"{s['pe_delta']:+.2f}", color="#089981" if s["pe_delta"] >= 0 else "#F23645", align=Qt.AlignmentFlag.AlignCenter)
            self._set_table_item(self.options_table, i, 8, f"{s['pe_iv']:.1f}%", color="#94A3B8", align=Qt.AlignmentFlag.AlignCenter)

    @pyqtSlot(dict)
    def on_news_received(self, news_data: Dict[str, Any]) -> None:
        """Render live Indian financial news headlines and global macro quotes."""
        score = news_data.get("combined_score", 0.0)
        bias = news_data.get("confluence_bias", "NEUTRAL")
        g_score = news_data.get("global_macro_score", 0.0)
        d_score = news_data.get("news_sentiment_score", 0.0)

        # Update Header Sentiment Badge
        badge_col = "#089981" if score >= 0.15 else ("#F23645" if score <= -0.15 else "#787B86")
        self.macro_header_badge.setText(f"🌐 Macro: {bias} ({score:+.2f})")
        self.macro_header_badge.setStyleSheet(
            f"background-color: rgba(42, 46, 57, 0.7); border: 1px solid {badge_col}; color: {badge_col}; "
            "border-radius: 12px; padding: 4px 10px; font-weight: 700; font-size: 11px;"
        )

        # Update News Tab Badges & Metrics
        self.news_bias_badge.setText(f"BIAS: {bias} ({score:+.2f})")
        self.news_bias_badge.setStyleSheet(
            f"background: {badge_col}; color: white; font-weight: 800; font-size: 11px; padding: 3px 8px; border-radius: 10px;"
        )
        self.macro_breakdown_lbl.setText(f"Global Macro: {g_score:+.2f} | Domestic Sentiment: {d_score:+.2f}")

        # Format Macro Tickers
        quotes = news_data.get("macro_quotes", [])
        if quotes:
            q_strs = []
            for q in quotes[:4]:
                color = "green" if q.get("change_pct", 0) >= 0 else "red"
                q_strs.append(f"{q.get('name', q.get('symbol'))}: {q.get('price', 0):,.2f} ({q.get('change_pct', 0):+.2f}%)")
            self.macro_tickers_lbl.setText(" | ".join(q_strs))

        # Format Catalysts
        drivers = news_data.get("key_drivers", [])
        if drivers:
            self.catalysts_lbl.setText(f"Key Catalysts: {', '.join(drivers[:5])}")

        # Format News Articles HTML
        headlines = news_data.get("headlines", [])
        if headlines:
            cards_html = ['<div style="font-family: -apple-system, sans-serif; line-height: 1.4;">']
            for h in headlines[:20]:
                sentiment = h.get("sentiment", "NEUTRAL")
                if sentiment == "BULLISH":
                    sent_pill = '<span style="background: rgba(8, 153, 129, 0.2); color: #089981; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px;">🟢 BULLISH</span>'
                elif sentiment == "BEARISH":
                    sent_pill = '<span style="background: rgba(242, 54, 69, 0.2); color: #F23645; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px;">🔴 BEARISH</span>'
                else:
                    sent_pill = '<span style="background: rgba(120, 123, 134, 0.2); color: #94A3B8; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 4px;">⚪ NEUTRAL</span>'

                source_time = f"<span style='color: #787B86; font-size: 10px; margin-left: 6px;'>{h.get('source', 'News')} • {h.get('published', '')}</span>"
                title_html = f"<div style='color: #F8FAFC; font-weight: 600; font-size: 12px; margin-top: 4px;'>{h.get('title', '')}</div>"

                kw = h.get("keywords", [])
                kw_html = ""
                if kw:
                    kw_tags = [f"<span style='background: #2A2E39; color: #38BDF8; font-size: 9px; padding: 1px 5px; border-radius: 3px;'>{k}</span>" for k in kw[:3]]
                    kw_html = f"<div style='margin-top: 4px; display: flex; gap: 4px;'>{' '.join(kw_tags)}</div>"

                card = f"""
                <div style="background: #1E222D; border: 1px solid #2A2E39; border-radius: 6px; padding: 8px; margin-bottom: 8px;">
                    <div>{sent_pill}{source_time}</div>
                    {title_html}
                    {kw_html}
                </div>
                """
                cards_html.append(card)
            cards_html.append("</div>")
            self.news_browser.setHtml("\n".join(cards_html))

    @pyqtSlot(str, str)
    def on_connection_status(self, status: str, message: str) -> None:
        """Update top status LED badge with connection state."""
        if status == "CONNECTED":
            self.conn_badge.setText(f"🟢 Connected ({message})")
            self.conn_badge.setStyleSheet(
                "background-color: rgba(8, 153, 129, 0.15); border: 1px solid #089981; "
                "color: #089981; border-radius: 12px; padding: 4px 12px; font-weight: 700;"
            )
        elif status == "RECONNECTING":
            self.conn_badge.setText(f"🟠 {message}")
            self.conn_badge.setStyleSheet(
                "background-color: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; "
                "color: #F59E0B; border-radius: 12px; padding: 4px 12px; font-weight: 700;"
            )
        else:
            self.conn_badge.setText(f"🔴 {status}: {message}")
            self.conn_badge.setStyleSheet(
                "background-color: rgba(242, 54, 69, 0.15); border: 1px solid #F23645; "
                "color: #F23645; border-radius: 12px; padding: 4px 12px; font-weight: 700;"
            )

    def _set_table_item(
        self,
        table: QTableWidget,
        row: int,
        col: int,
        text: str,
        color: Optional[str] = None,
        bg_color: Optional[str] = None,
        bold: bool = False,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    ) -> None:
        """Helper to set table cell values with custom formatting."""
        item = table.item(row, col)
        if item is None:
            item = QTableWidgetItem(text)
            table.setItem(row, col, item)
        else:
            item.setText(text)

        item.setTextAlignment(align)
        if color:
            item.setForeground(QColor(color))
        if bg_color:
            item.setBackground(QColor(bg_color))
        else:
            item.setBackground(QBrush())

        if bold:
            f = item.font()
            f.setBold(True)
            item.setFont(f)

    def _on_instrument_changed(self, inst: str) -> None:
        """Handle active instrument switching."""
        self.current_instrument = inst
        self.spot_title_lbl.setText(f"{inst} SPOT LTP")
        self.worker.instrument = inst
        self.worker._warmup_historical_bars()
        logger.info("Switched active instrument to %s.", inst)

    def _on_risk_params_changed(self) -> None:
        """Handle changes to risk controls."""
        self.account_equity = float(self.equity_spin.value())
        self.risk_pct = self.risk_slider.value() / 100.0
        self.atr_mult = self.atr_slider.value() / 10.0

        max_risk = self.account_equity * (self.risk_pct / 100.0)
        self.risk_pct_lbl.setText(f"Risk per Trade: {self.risk_pct:.2f}% (Max Risk: ₹{max_risk:,.0f})")
        self.atr_mult_lbl.setText(f"ATR Stop Multiplier: {self.atr_mult:.2f}x")
        self.risk_pbar.setValue(int(self.risk_pct / 3.0 * 100))

    def _play_chime(self) -> None:
        """Play terminal audio chime on signal transition or button press."""
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["afplay", "/System/Library/Sounds/Ping.aiff"], stderr=subprocess.DEVNULL)
            else:
                print("\a")
        except Exception:
            pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Clean shutdown of background QThread worker upon window close."""
        logger.info("Shutting down DecodeX Trading Terminal...")
        self.worker.stop()
        event.accept()


# =============================================================================
# APPLICATION ENTRYPOINT (macOS / Apple Silicon Optimized)
# =============================================================================

def main() -> None:
    """Launch native DecodeX Trading application."""
    if hasattr(QtCore.Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    if qt_plugins.exists():
        QtCore.QCoreApplication.addLibraryPath(str(qt_plugins))
        QtCore.QCoreApplication.addLibraryPath(str(qt_plugins / "platforms"))

    app = QApplication(sys.argv)
    app.setApplicationName("DecodeX Trading")
    app.setOrganizationName("DecodeX")

    icon_path = str(PROJECT_ROOT / "assets" / "decodex_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = DecodeXMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
