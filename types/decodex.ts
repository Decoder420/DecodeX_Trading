/**
 * DecodeX Trading — Institutional Multi-Timeframe Quant Execution Terminal
 * TypeScript Core Interfaces and Data Contracts
 */

// ============================================================================
// 1. REAL-TIME MARKET TICK & MICROSTRUCTURE DATA
// ============================================================================

export interface TickData {
  symbol: string;              // e.g. "NIFTY", "BANKNIFTY", "SENSEX"
  ltp: number;                 // Last Traded Price (₹)
  change: number;              // Net change from open/prev close (₹)
  changePct: number;           // Percentage change (%)
  open: number;                // Session Open (₹)
  high: number;                // Session High (₹)
  low: number;                 // Session Low (₹)
  volume: number;              // Cumulative volume
  timestamp: string;           // ISO 8601 or IST string
  epochMs: number;             // UNIX timestamp in milliseconds
  tickCount: number;           // Total ticks processed in session
}

export interface MarketDepthLevel {
  orders: number;              // Number of pending limit orders
  quantity: number;            // Total depth quantity at level
  price: number;               // Limit price (₹)
}

export interface L2Depth {
  symbol: string;
  orderBookImbalance: number;  // OBI: -1.0 (Heavy Selling) to +1.0 (Heavy Buying)
  sentiment: 'Heavy Buying' | 'Moderate Buying' | 'Balanced' | 'Moderate Selling' | 'Heavy Selling';
  spread: number;              // Top Bid/Ask spread (pts)
  microPrice: number;          // Volume-weighted top-of-book price (₹)
  totalBidQty: number;
  totalAskQty: number;
  bids: [MarketDepthLevel, MarketDepthLevel, MarketDepthLevel, MarketDepthLevel, MarketDepthLevel];
  asks: [MarketDepthLevel, MarketDepthLevel, MarketDepthLevel, MarketDepthLevel, MarketDepthLevel];
  latencyMs: number;           // Pipeline processing latency in ms
}

// ============================================================================
// 2. REAL-TIME OPTIONS CHAIN & GREEKS (ATM ± 200)
// ============================================================================

export interface OptionsChainRow {
  strike: number;              // Strike price (e.g. 25050)
  strikeLabel: string;         // Formatted label (e.g. "₹25,050")
  isAtm: boolean;              // True if strike is At-The-Money

  // Call Side (CE)
  ceLtp: number;               // Call Premium LTP (₹)
  ceIv: number;                // Call Implied Volatility (%)
  ceDelta: number;             // Call Delta (0.0 to 1.0)
  ceCoi: number;               // Call Change in Open Interest (contracts)
  ceOi: number;                // Call Total Open Interest

  // Put Side (PE)
  peLtp: number;               // Put Premium LTP (₹)
  peIv: number;                // Put Implied Volatility (%)
  peDelta: number;             // Put Delta (-1.0 to 0.0)
  peCoi: number;               // Put Change in Open Interest (contracts)
  peOi: number;                // Put Total Open Interest

  // Institutional Microstructure Flags
  coiDelta: number;            // Put COI - Call COI (positive = Bullish support building)
  heavyWriting: 'PE_SUPPORT' | 'CE_RESISTANCE' | 'NEUTRAL';
}

export interface OptionsChainState {
  expiry: string;              // e.g. "17NOV2026"
  triadCoiDelta: number;       // Net COI delta across ATM, ATM+Step, ATM-Step
  sentiment: string;           // Institutional interpretation
  pcrOi: number;               // Put-Call Ratio
  maxPain: number;             // Strike with maximum total buyer loss
  underlyingLtp: number;
  rows: OptionsChainRow[];
}

// ============================================================================
// 3. MULTI-TIMEFRAME (MTF) OHLCV & INDICATOR STATE
// ============================================================================

export interface Candle {
  time: number;                // UNIX timestamp in integer seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface IndicatorPoint {
  time: number;                // UNIX timestamp in integer seconds
  value: number;
}

export interface Structural15mFrame {
  candles: Candle[];
  vwapData: IndicatorPoint[];
  supertrendData: IndicatorPoint[];
  anchoredVwap: number;        // Latest session VWAP (₹)
  supertrend: number;          // Latest Supertrend band (₹)
  supertrendDirection: 1 | -1; // 1: Bullish, -1: Bearish
  dailyAtr: number;            // Daily structural ATR (pts)
  bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
}

export interface Execution3mFrame {
  candles: Candle[];
  ema9Data: IndicatorPoint[];
  ema21Data: IndicatorPoint[];
  ema50Data: IndicatorPoint[];
  rsiData: IndicatorPoint[];
  ema9: number;
  ema21: number;
  ema50: number;
  rsi14: number;
  squeezeOn: boolean;          // True if BB width < KC width (compression)
  squeezeFired: boolean;       // True if expanding outward (volatility firing)
  trigger: 'TRIGGER_LONG' | 'TRIGGER_SHORT' | 'WAIT';
}

export interface MTFState {
  symbol: string;
  spotPrice: number;
  frame15m: Structural15mFrame;
  frame3m: Execution3mFrame;
}

// ============================================================================
// 4. QUANT EXECUTION & 6-FACTOR CONFLUENCE STATE MACHINE
// ============================================================================

export type ConfluenceSignalType =
  | 'BULLISH_ENTRY'
  | 'BEARISH_ENTRY'
  | 'CONFLUENCE_WAIT'
  | 'CHOP_FILTER_ACTIVE';

export interface TradePlan {
  action: 'BUY_CALL' | 'BUY_PUT' | 'WAIT';
  recommendedStrike: string;   // e.g. "25050 CE"
  spotEntry: number;           // Underlying spot price at entry (₹)
  stopLoss: number;            // 1.5x ATR structural Stop-Loss (₹)
  stopDistancePts: number;     // Stop distance in underlying points
  target1: number;             // Target 1: 2.3x ATR
  target2: number;             // Target 2: 3.5x ATR Runner
  riskRewardRatio: string;     // e.g. "1:2.3"
  atrPts: number;
}

export interface ConfluenceGateState {
  signal: ConfluenceSignalType;
  signalLabel: string;         // Human-readable banner label
  score: number;               // Range: -6.0 (Max Bearish) to +6.0 (Max Bullish)
  bias15m: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  trigger3m: 'TRIGGER_LONG' | 'TRIGGER_SHORT' | 'WAIT';
  reasons: string[];           // Systematic confluence factor justifications
  tradePlan: TradePlan;
}

export type ExecutionState =
  | 'IDLE'
  | 'WAITING_FOR_CONFLUENCE'
  | 'EVALUATING_RISK'
  | 'ORDER_SUBMITTED'
  | 'POSITION_OPEN'
  | 'TRAILING_STOP'
  | 'TARGET_REACHED'
  | 'STOPPED_OUT'
  | 'GUARDRAIL_BLOCKED';

// ============================================================================
// 5. BROKER ORDER EXECUTION & AUDIT EVENT LOG
// ============================================================================

export interface OrderPayload {
  orderId: string;
  timestamp: string;
  instrument: string;
  strike: string;              // e.g. "25050 CE"
  orderType: 'MARKET' | 'LIMIT';
  action: 'BUY' | 'SELL';
  lots: number;
  quantity: number;
  entryPrice: number;
  stopLoss: number;
  target: number;
  mode: 'ACTIVE_EXECUTION' | 'STRICT_GATEKEEPER';
  maxRiskInr: number;
  estCostInr: number;
}

export interface OrderExecutionResult {
  orderId: string;
  success: boolean;
  status: 'FILLED' | 'REJECTED' | 'BLOCKED_BY_GUARDRAIL';
  fillPrice: number;
  fillTime: string;
  message: string;
  brokerageFee: number;
  statutoryTaxes: number;
}

export interface EventLogEntry {
  id: string;
  timestamp: string;           // "HH:MM:SS"
  category: 'ORDER' | 'CONFLUENCE' | 'RISK_GUARD' | 'TRAILING_SL' | 'SYSTEM';
  level: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
  title: string;
  details: string;
}

// ============================================================================
// 6. REACTIVE DYNAMIC RISK & POSITION SIZING
// ============================================================================

export interface RiskParameters {
  accountEquity: number;       // Portfolio Equity in INR (e.g. ₹1,000,000)
  riskPerTradePct: number;     // Allocated risk % (e.g. 1.0%)
  atrMultiplier: number;       // Stop multiplier (e.g. 1.5x)
  instrument: 'NIFTY' | 'BANKNIFTY' | 'SENSEX';
  lotSize: number;             // NIFTY: 65, BANKNIFTY: 30, SENSEX: 20
}

export interface RiskEvaluationResult {
  maxRiskInr: number;          // Equity * Risk%
  stopDistancePts: number;     // ATR * Multiplier
  riskPerLotInr: number;       // StopDistance * LotSize
  recommendedLots: number;     // Floor(MaxRisk / RiskPerLot)
  recommendedQuantity: number; // Lots * LotSize
  isSmallAccountBlocked: boolean; // True if 1 lot risk > MaxRisk
  guardrailStatus: 'SAFE' | 'WARNING' | 'BLOCKED';
  message: string;
}

// ============================================================================
// 7. OVERALL CONSOLIDATED ENGINE STATE
// ============================================================================

export interface DecodeXEngineState {
  timestamp: string;
  updatedAt: number;
  connectionStatus: string;
  latencyMs: number;
  source: string;
  instrument: string;
  expiry: string;
  spotPrice: number;
  change: number;
  changePct: number;
  open: number;
  high: number;
  low: number;
  tickCount: number;
  depth: L2Depth;
  optionsChain: OptionsChainState;
  mtf15m: Structural15mFrame;
  mtf3m: Execution3mFrame;
  confluence: ConfluenceGateState;
  executionState: ExecutionState;
  lastOrder?: OrderPayload;
  eventLogs: EventLogEntry[];
}

