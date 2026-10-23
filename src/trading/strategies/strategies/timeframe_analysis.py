"""
Advanced Timeframe Analysis Engine for SENTIENX Trading System

Focuses on supply/demand key levels, fair value gaps (FVG), order blocks,
liquidity analysis, trend direction, breakout confirmation, and reversals
for major deriv pairs (EURUSD, GBPUSD, USDJPY, AUDUSD, NZDUSD).

Advanced Concepts:
- Supply/Demand Zones: Identifies areas of buyer/seller concentration
- Fair Value Gaps (FVG): Unfilled price gaps indicating imbalance
- Order Blocks: Institutional accumulation/distribution blocks
- Liquidity Nodes: Key price levels where stops cluster
- Reversal Patterns: Trend reversal confirmation signals
- Multi-Timeframe Confluence: Signal strength across timeframes
- Smart Money: Order flow and institutional participation analysis
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
from enum import Enum
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class ZoneType(Enum):
    """Type of supply/demand zone."""
    SUPPLY = "supply"
    DEMAND = "demand"


class LevelType(Enum):
    """Type of price level."""
    SUPPORT = "support"
    RESISTANCE = "resistance"
    PIVOT = "pivot"
    FVG_UP = "fvg_up"
    FVG_DOWN = "fvg_down"
    ORDER_BLOCK_BUY = "order_block_buy"
    ORDER_BLOCK_SELL = "order_block_sell"
    LIQUIDITY_NODE = "liquidity_node"


class TrendDirection(Enum):
    """Trend direction classification."""
    STRONG_UP = "strong_up"
    UP = "up"
    WEAK_UP = "weak_up"
    NEUTRAL = "neutral"
    WEAK_DOWN = "weak_down"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


class BreakoutType(Enum):
    """Type of breakout detected."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    FALSE = "false"
    NONE = "none"


@dataclass
class SupplyDemandZone:
    """Supply/demand zone definition."""
    zone_type: ZoneType
    price_high: float
    price_low: float
    strength: float  # 0-1, based on touches and volume
    touches: int  # Number of times price touched zone
    created_timestamp: datetime
    last_touch: datetime
    volume_profile: float  # Relative volume in zone
    probability: float  # Probability of reversal (0-1)
    is_active: bool = True
    raw_strength: float = 0.0


@dataclass
class FairValueGap:
    """Fair value gap (FVG) definition."""
    gap_type: str  # 'up' or 'down'
    high_candle_high: float
    low_candle_low: float
    gap_high: float
    gap_low: float
    candles: List[Dict] = field(default_factory=list)
    created_timestamp: datetime = field(default_factory=datetime.now)
    filled: bool = False
    fill_price: Optional[float] = None
    mitigation_percentage: float = 0.0  # How much of gap is filled (0-1)
    severity: float = 0.0  # Gap size relative to ATR


@dataclass
class OrderBlock:
    """Order block (accumulation/distribution) definition."""
    block_type: str  # 'buy' or 'sell'
    price_high: float
    price_low: float
    candles_count: int
    volume_strength: float  # 0-1
    confirmed: bool
    break_candle: Optional[Dict] = None
    created_timestamp: datetime = field(default_factory=datetime.now)
    target_level: Optional[float] = None
    confirmation_type: str = ""  # 'break', 'retest', etc.


@dataclass
class LiquidityNode:
    """Liquidity node - where orders cluster."""
    price: float
    type: str  # 'buy_stops', 'sell_stops', 'round_level'
    strength: float  # 0-1
    touches: int
    last_interaction: datetime = field(default_factory=datetime.now)
    hunted: bool = False
    hunt_severity: float = 0.0


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    direction: TrendDirection
    strength: float  # 0-1
    pivot_high: float
    pivot_low: float
    higher_high: bool
    higher_low: bool
    lower_high: bool
    lower_low: bool
    slope: float  # Angle of trend
    atr_multiple: float  # Current range relative to ATR
    imbalance_count: int  # Number of imbalances (FVGs)


@dataclass
class BreakoutAnalysis:
    """Breakout analysis result."""
    breakout_type: BreakoutType
    breakout_level: float
    breakout_strength: float  # 0-1
    retest_occurred: bool
    retest_price: Optional[float] = None
    confirmation_bars: int = 0
    false_breakout_probability: float = 0.0
    target_level: Optional[float] = None


@dataclass
class ReversalPattern:
    """Reversal pattern detection."""
    pattern_type: str  # 'engulfing', 'pinbar', 'inside_bar', 'confluence'
    severity: float  # 0-1
    confirmation_strength: float  # 0-1
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    risk_reward_ratio: float = 0.0
    pattern_candles: int = 0


@dataclass
class TradeSetup:
    """Optimal trade setup identification."""
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str  # Why this setup is valid
    confluence_score: float  # 0-1, based on multiple factors
    components: List[str] = field(default_factory=list)  # What makes this setup (FVG, OB, etc)
    timeframe_confluence: Dict[str, float] = field(default_factory=dict)  # Scores per TF
    smart_money_signal: bool = False
    probability_estimate: float = 0.0
    expected_move_atr_multiple: float = 0.0


class SupplyDemandAnalyzer:
    """Analyzes supply/demand zones using price action and volume."""
    
    def __init__(self, lookback_periods: int = 100, min_touches: int = 2):
        self.lookback_periods = lookback_periods
        self.min_touches = min_touches
        self.zones: Dict[str, List[SupplyDemandZone]] = {'supply': [], 'demand': []}
        self.recent_prices = deque(maxlen=lookback_periods)
    
    def identify_zones(self, data: pd.DataFrame) -> Dict[str, List[SupplyDemandZone]]:
        """Identify supply/demand zones from OHLCV data.
        
        Args:
            data: DataFrame with OHLCV + Volume
            
        Returns:
            Dict with 'supply' and 'demand' lists
        """
        self.recent_prices.extend(data['close'].tail(self.lookback_periods).values)
        
        zones_supply = self._find_zones(data, ZoneType.SUPPLY)
        zones_demand = self._find_zones(data, ZoneType.DEMAND)
        
        self.zones = {'supply': zones_supply, 'demand': zones_demand}
        return self.zones
    
    def _find_zones(self, data: pd.DataFrame, zone_type: ZoneType) -> List[SupplyDemandZone]:
        """Find zones of specific type."""
        zones = []
        
        if zone_type == ZoneType.SUPPLY:
            # Find resistance clusters - where price reversed down
            pivots = self._find_swing_highs(data)
        else:
            # Find support clusters - where price reversed up
            pivots = self._find_swing_lows(data)
        
        # Group nearby pivots into zones
        for pivot_idx in pivots:
            if pivot_idx < 0 or pivot_idx >= len(data):
                continue
            
            pivot_price = data.iloc[pivot_idx]['high' if zone_type == ZoneType.SUPPLY else 'low']
            zone_range = pivot_price * 0.002  # 0.2% range
            
            # Find all touches in this zone
            touches = 0
            total_volume = 0
            first_touch = data.index[pivot_idx]
            last_touch = first_touch
            
            for i in range(pivot_idx, len(data)):
                close = data.iloc[i]['close']
                high = data.iloc[i]['high']
                low = data.iloc[i]['low']
                volume = data.iloc[i].get('volume', 0)
                
                if zone_type == ZoneType.SUPPLY:
                    if low <= pivot_price + zone_range and high >= pivot_price - zone_range:
                        touches += 1
                        total_volume += volume
                        last_touch = data.index[i]
                else:
                    if low <= pivot_price + zone_range and high >= pivot_price - zone_range:
                        touches += 1
                        total_volume += volume
                        last_touch = data.index[i]
            
            if touches >= self.min_touches:
                strength = min(touches / 10.0, 1.0)  # Normalize to 0-1
                zone = SupplyDemandZone(
                    zone_type=zone_type,
                    price_high=pivot_price + zone_range,
                    price_low=pivot_price - zone_range,
                    strength=strength,
                    touches=touches,
                    created_timestamp=first_touch,
                    last_touch=last_touch,
                    volume_profile=min(total_volume / data['volume'].mean() / 100, 1.0),
                    probability=min(touches / 5.0, 0.95)  # Higher with more touches
                )
                zones.append(zone)
        
        # Remove duplicate overlapping zones
        return self._deduplicate_zones(zones)
    
    def _find_swing_highs(self, data: pd.DataFrame, period: int = 5) -> List[int]:
        """Find swing high pivots."""
        pivots = []
        for i in range(period, len(data) - period):
            high = data.iloc[i]['high']
            if all(high >= data.iloc[j]['high'] for j in range(i - period, i + period + 1) if j != i):
                pivots.append(i)
        return pivots
    
    def _find_swing_lows(self, data: pd.DataFrame, period: int = 5) -> List[int]:
        """Find swing low pivots."""
        pivots = []
        for i in range(period, len(data) - period):
            low = data.iloc[i]['low']
            if all(low <= data.iloc[j]['low'] for j in range(i - period, i + period + 1) if j != i):
                pivots.append(i)
        return pivots
    
    def _deduplicate_zones(self, zones: List[SupplyDemandZone]) -> List[SupplyDemandZone]:
        """Remove overlapping duplicate zones."""
        if not zones:
            return []
        
        sorted_zones = sorted(zones, key=lambda z: z.strength, reverse=True)
        unique_zones = []
        
        for zone in sorted_zones:
            is_duplicate = False
            for existing in unique_zones:
                if self._zones_overlap(zone, existing):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_zones.append(zone)
        
        return unique_zones[:10]  # Keep top 10
    
    def _zones_overlap(self, zone1: SupplyDemandZone, zone2: SupplyDemandZone) -> bool:
        """Check if zones overlap."""
        return not (zone1.price_high < zone2.price_low or zone1.price_low > zone2.price_high)


class FairValueGapDetector:
    """Detects fair value gaps (FVGs) and imbalances."""
    
    def __init__(self, min_gap_size_atr: float = 0.3):
        self.min_gap_size_atr = min_gap_size_atr
        self.gaps: List[FairValueGap] = []
    
    def find_gaps(self, data: pd.DataFrame, atr: float) -> List[FairValueGap]:
        """Find fair value gaps (unfilled candle gaps).
        
        Args:
            data: OHLCV DataFrame
            atr: Average true range
            
        Returns:
            List of FairValueGap objects
        """
        self.gaps = []
        
        for i in range(2, len(data)):
            prev_prev_high = data.iloc[i-2]['high']
            prev_prev_low = data.iloc[i-2]['low']
            prev_high = data.iloc[i-1]['high']
            prev_low = data.iloc[i-1]['low']
            curr_high = data.iloc[i]['high']
            curr_low = data.iloc[i]['low']
            
            # Bullish FVG (gap up)
            if prev_low > prev_prev_high and curr_low > prev_low:
                gap_size = prev_low - prev_prev_high
                if gap_size >= self.min_gap_size_atr * atr:
                    gap = FairValueGap(
                        gap_type='up',
                        high_candle_high=prev_prev_high,
                        low_candle_low=prev_low,
                        gap_high=prev_low,
                        gap_low=prev_prev_high,
                        candles=[
                            data.iloc[i-2].to_dict(),
                            data.iloc[i-1].to_dict()
                        ],
                        created_timestamp=data.index[i],
                        severity=gap_size / atr
                    )
                    self.gaps.append(gap)
            
            # Bearish FVG (gap down)
            if prev_high < prev_prev_low and curr_high < prev_high:
                gap_size = prev_prev_low - prev_high
                if gap_size >= self.min_gap_size_atr * atr:
                    gap = FairValueGap(
                        gap_type='down',
                        high_candle_high=prev_prev_low,
                        low_candle_low=prev_high,
                        gap_high=prev_prev_low,
                        gap_low=prev_high,
                        candles=[
                            data.iloc[i-2].to_dict(),
                            data.iloc[i-1].to_dict()
                        ],
                        created_timestamp=data.index[i],
                        severity=gap_size / atr
                    )
                    self.gaps.append(gap)
        
        # Update mitigation for existing gaps
        self._update_gap_mitigation(data)
        
        return self.gaps
    
    def _update_gap_mitigation(self, data: pd.DataFrame):
        """Update how much each gap has been filled."""
        current_price = data.iloc[-1]['close']
        
        for gap in self.gaps:
            if gap.filled:
                continue
            
            if gap.gap_type == 'up':
                # Gap from low to high
                if current_price <= gap.gap_low:
                    gap.filled = True
                    gap.fill_price = current_price
                gap.mitigation_percentage = max(0, (gap.gap_low - current_price) / (gap.gap_low - gap.gap_high))
            else:
                # Gap from high to low
                if current_price >= gap.gap_high:
                    gap.filled = True
                    gap.fill_price = current_price
                gap.mitigation_percentage = max(0, (current_price - gap.gap_high) / (gap.gap_low - gap.gap_high))


class OrderBlockDetector:
    """Detects order blocks (accumulation/distribution areas)."""
    
    def __init__(self, min_candles: int = 3):
        self.min_candles = min_candles
        self.blocks: List[OrderBlock] = []
    
    def find_blocks(self, data: pd.DataFrame) -> List[OrderBlock]:
        """Find order blocks (strong accumulation/distribution).
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            List of OrderBlock objects
        """
        self.blocks = []
        
        # Find bullish order blocks (accumulation)
        bullish_blocks = self._find_bullish_blocks(data)
        
        # Find bearish order blocks (distribution)
        bearish_blocks = self._find_bearish_blocks(data)
        
        self.blocks = bullish_blocks + bearish_blocks
        
        return sorted(self.blocks, key=lambda b: b.created_timestamp)
    
    def _find_bullish_blocks(self, data: pd.DataFrame) -> List[OrderBlock]:
        """Find bullish order blocks (strong buying, lower closes)."""
        blocks = []
        
        for i in range(self.min_candles, len(data)):
            window = data.iloc[i-self.min_candles:i+1]
            
            # Bullish block: multiple candles with lower closes (accumulation)
            closes_descending = all(
                window.iloc[j]['close'] > window.iloc[j+1]['close'] 
                for j in range(len(window)-1)
            )
            
            # Check volume strength
            avg_volume = window['volume'].mean()
            above_avg = all(window['volume'] > avg_volume * 0.8)
            
            if closes_descending and above_avg:
                block = OrderBlock(
                    block_type='buy',
                    price_high=window['high'].max(),
                    price_low=window['low'].min(),
                    candles_count=len(window),
                    volume_strength=min(window['volume'].mean() / data['volume'].mean(), 1.0),
                    confirmed=False,
                    created_timestamp=data.index[i-self.min_candles]
                )
                blocks.append(block)
        
        return blocks
    
    def _find_bearish_blocks(self, data: pd.DataFrame) -> List[OrderBlock]:
        """Find bearish order blocks (strong selling, higher closes)."""
        blocks = []
        
        for i in range(self.min_candles, len(data)):
            window = data.iloc[i-self.min_candles:i+1]
            
            # Bearish block: multiple candles with higher closes (distribution)
            closes_ascending = all(
                window.iloc[j]['close'] < window.iloc[j+1]['close'] 
                for j in range(len(window)-1)
            )
            
            # Check volume strength
            avg_volume = window['volume'].mean()
            above_avg = all(window['volume'] > avg_volume * 0.8)
            
            if closes_ascending and above_avg:
                block = OrderBlock(
                    block_type='sell',
                    price_high=window['high'].max(),
                    price_low=window['low'].min(),
                    candles_count=len(window),
                    volume_strength=min(window['volume'].mean() / data['volume'].mean(), 1.0),
                    confirmed=False,
                    created_timestamp=data.index[i-self.min_candles]
                )
                blocks.append(block)
        
        return blocks


class TrendAnalyzer:
    """Analyzes trend direction, strength, and structure."""
    
    def __init__(self, rsi_period: int = 14, atr_period: int = 14):
        self.rsi_period = rsi_period
        self.atr_period = atr_period
    
    def analyze_trend(self, data: pd.DataFrame) -> TrendAnalysis:
        """Analyze trend direction and strength.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            TrendAnalysis object
        """
        # Calculate trend structure
        pivot_high = data['high'].tail(10).max()
        pivot_low = data['low'].tail(10).min()
        
        # Check for higher highs/lows (uptrend) or lower highs/lows (downtrend)
        recent_high = data['high'].iloc[-1]
        recent_low = data['low'].iloc[-1]
        prev_high = data['high'].iloc[-10] if len(data) > 10 else recent_high
        prev_low = data['low'].iloc[-10] if len(data) > 10 else recent_low
        
        higher_high = recent_high > prev_high
        higher_low = recent_low > prev_low
        lower_high = recent_high < prev_high
        lower_low = recent_low < prev_low
        
        # Determine trend direction
        if higher_high and higher_low:
            direction = TrendDirection.UP
        elif lower_high and lower_low:
            direction = TrendDirection.DOWN
        else:
            direction = TrendDirection.NEUTRAL
        
        # Calculate RSI for strength
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Calculate strength (0-1)
        if direction == TrendDirection.UP:
            strength = min(rsi.iloc[-1] / 100, 1.0)
            if rsi.iloc[-1] > 70:
                direction = TrendDirection.STRONG_UP
            elif rsi.iloc[-1] > 50:
                direction = TrendDirection.WEAK_UP
        elif direction == TrendDirection.DOWN:
            strength = min((100 - rsi.iloc[-1]) / 100, 1.0)
            if rsi.iloc[-1] < 30:
                direction = TrendDirection.STRONG_DOWN
            elif rsi.iloc[-1] < 50:
                direction = TrendDirection.WEAK_DOWN
        else:
            strength = 0.5
        
        # Calculate ATR multiple (volatility measure)
        atr = self._calculate_atr(data)
        current_range = data['high'].iloc[-1] - data['low'].iloc[-1]
        atr_multiple = current_range / atr if atr > 0 else 1.0
        
        # Count imbalances (FVGs)
        gap_detector = FairValueGapDetector()
        gaps = gap_detector.find_gaps(data, atr)
        
        return TrendAnalysis(
            direction=direction,
            strength=min(strength, 1.0),
            pivot_high=pivot_high,
            pivot_low=pivot_low,
            higher_high=higher_high,
            higher_low=higher_low,
            lower_high=lower_high,
            lower_low=lower_low,
            slope=self._calculate_slope(data),
            atr_multiple=atr_multiple,
            imbalance_count=len([g for g in gaps if not g.filled])
        )
    
    def _calculate_atr(self, data: pd.DataFrame) -> float:
        """Calculate average true range."""
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift())
        low_close = abs(data['low'] - data['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_period).mean().iloc[-1]
        return atr if not pd.isna(atr) else 0.01
    
    def _calculate_slope(self, data: pd.DataFrame) -> float:
        """Calculate trend slope (angle)."""
        closes = data['close'].tail(20).values
        if len(closes) < 2:
            return 0.0
        x = np.arange(len(closes))
        y = closes
        slope = (y[-1] - y[0]) / len(closes)
        return slope


class BreakoutDetector:
    """Detects breakout levels and confirms breakouts."""
    
    def __init__(self, breakout_bars: int = 20, confirmation_bars: int = 2):
        self.breakout_bars = breakout_bars
        self.confirmation_bars = confirmation_bars
    
    def detect_breakout(self, data: pd.DataFrame) -> BreakoutAnalysis:
        """Detect breakout and determine validity.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            BreakoutAnalysis object
        """
        if len(data) < self.breakout_bars:
            return BreakoutAnalysis(
                breakout_type=BreakoutType.NONE,
                breakout_level=0.0,
                breakout_strength=0.0
            )
        
        recent_data = data.tail(self.breakout_bars + self.confirmation_bars)
        
        # Find highest high and lowest low
        highest_high = recent_data['high'].iloc[:-self.confirmation_bars].max()
        lowest_low = recent_data['low'].iloc[:-self.confirmation_bars].min()
        
        current_close = data.iloc[-1]['close']
        current_high = data.iloc[-1]['high']
        current_low = data.iloc[-1]['low']
        
        # Check for breakout
        breakout_type = BreakoutType.NONE
        breakout_level = 0.0
        strength = 0.0
        
        # Bullish breakout
        if current_high > highest_high:
            breakout_type = BreakoutType.BULLISH
            breakout_level = highest_high
            strength = (current_high - highest_high) / (highest_high * 0.01)  # As percentage
        
        # Bearish breakout
        elif current_low < lowest_low:
            breakout_type = BreakoutType.BEARISH
            breakout_level = lowest_low
            strength = (lowest_low - current_low) / (lowest_low * 0.01)
        
        # Check for retest
        retest_occurred = False
        retest_price = None
        
        if len(data) > self.confirmation_bars + 1:
            for i in range(-self.confirmation_bars, 0):
                if breakout_type == BreakoutType.BULLISH:
                    if data.iloc[i]['low'] <= breakout_level:
                        retest_occurred = True
                        retest_price = data.iloc[i]['low']
                elif breakout_type == BreakoutType.BEARISH:
                    if data.iloc[i]['high'] >= breakout_level:
                        retest_occurred = True
                        retest_price = data.iloc[i]['high']
        
        return BreakoutAnalysis(
            breakout_type=breakout_type,
            breakout_level=breakout_level,
            breakout_strength=min(strength / 10, 1.0),
            retest_occurred=retest_occurred,
            retest_price=retest_price,
            confirmation_bars=self.confirmation_bars,
            false_breakout_probability=self._estimate_false_breakout_prob(data, breakout_type)
        )
    
    def _estimate_false_breakout_prob(self, data: pd.DataFrame, breakout_type: BreakoutType) -> float:
        """Estimate probability of false breakout."""
        if breakout_type == BreakoutType.NONE:
            return 0.0
        
        # Check momentum
        momentum = (data.iloc[-1]['close'] - data.iloc[-5]['close']) / data.iloc[-5]['close']
        
        # Check volume confirmation
        recent_volume = data['volume'].tail(3).mean()
        avg_volume = data['volume'].tail(20).mean()
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
        
        # If low volume breakout, higher false prob
        if volume_ratio < 1.0:
            return 0.6
        elif volume_ratio < 1.2:
            return 0.4
        else:
            return 0.2


class ReversalDetector:
    """Detects reversal patterns and confluence signals."""
    
    def detect_reversals(self, data: pd.DataFrame) -> List[ReversalPattern]:
        """Detect reversal patterns.
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            List of ReversalPattern objects
        """
        patterns = []
        
        # Engulfing pattern
        engulfing = self._detect_engulfing(data)
        if engulfing:
            patterns.append(engulfing)
        
        # Pin bar pattern
        pin_bar = self._detect_pin_bar(data)
        if pin_bar:
            patterns.append(pin_bar)
        
        # Inside bar pattern
        inside_bar = self._detect_inside_bar(data)
        if inside_bar:
            patterns.append(inside_bar)
        
        return patterns
    
    def _detect_engulfing(self, data: pd.DataFrame) -> Optional[ReversalPattern]:
        """Detect engulfing pattern."""
        if len(data) < 2:
            return None
        
        prev = data.iloc[-2]
        curr = data.iloc[-1]
        
        bullish_engulfing = (
            prev['close'] < prev['open'] and
            curr['close'] > curr['open'] and
            curr['low'] < prev['low'] and
            curr['high'] > prev['high']
        )
        
        bearish_engulfing = (
            prev['close'] > prev['open'] and
            curr['close'] < curr['open'] and
            curr['high'] > prev['high'] and
            curr['low'] < prev['low']
        )
        
        if bullish_engulfing or bearish_engulfing:
            return ReversalPattern(
                pattern_type='engulfing',
                severity=0.8,
                confirmation_strength=0.7,
                pattern_candles=2
            )
        
        return None
    
    def _detect_pin_bar(self, data: pd.DataFrame) -> Optional[ReversalPattern]:
        """Detect pin bar pattern."""
        if len(data) < 1:
            return None
        
        curr = data.iloc[-1]
        body = abs(curr['close'] - curr['open'])
        total_range = curr['high'] - curr['low']
        
        if total_range > 0:
            body_ratio = body / total_range
            
            # Pin bar: small body, long wick, closes away from wick
            if body_ratio < 0.3 and total_range > body * 2:
                return ReversalPattern(
                    pattern_type='pinbar',
                    severity=0.7,
                    confirmation_strength=0.65,
                    pattern_candles=1
                )
        
        return None
    
    def _detect_inside_bar(self, data: pd.DataFrame) -> Optional[ReversalPattern]:
        """Detect inside bar pattern."""
        if len(data) < 2:
            return None
        
        prev = data.iloc[-2]
        curr = data.iloc[-1]
        
        # Inside bar: current bar high < prev high AND current bar low > prev low
        inside_bar = curr['high'] < prev['high'] and curr['low'] > prev['low']
        
        if inside_bar:
            return ReversalPattern(
                pattern_type='inside_bar',
                severity=0.5,
                confirmation_strength=0.5,
                pattern_candles=2
            )
        
        return None


class MultiTimeframeConfluence:
    """Aggregates signals across multiple timeframes."""
    
    def __init__(self, timeframes: List[str] = None):
        self.timeframes = timeframes or ['15m', '1h', '4h', '1d']
        self.signals: Dict[str, Any] = {}
    
    def analyze_confluence(
        self,
        data_dict: Dict[str, pd.DataFrame],
        supply_demand: SupplyDemandAnalyzer,
        trend_analyzer: TrendAnalyzer,
        breakout_detector: BreakoutDetector,
        reversal_detector: ReversalDetector
    ) -> Dict[str, float]:
        """Analyze confluence across timeframes.
        
        Args:
            data_dict: Dict of timeframe -> DataFrame
            Other analyzers: Various analysis components
            
        Returns:
            Dict with confluence scores per timeframe
        """
        confluence_scores = {}
        
        for tf in self.timeframes:
            if tf not in data_dict:
                continue
            
            data = data_dict[tf]
            score = 0.0
            factors = []
            
            # Trend alignment
            trend = trend_analyzer.analyze_trend(data)
            if trend.direction != TrendDirection.NEUTRAL:
                score += 0.25
                factors.append(f"Trend: {trend.direction.value}")
            
            # Breakout confirmation
            breakout = breakout_detector.detect_breakout(data)
            if breakout.breakout_type != BreakoutType.NONE:
                score += 0.25
                factors.append(f"Breakout: {breakout.breakout_type.value}")
            
            # Supply/Demand
            zones = supply_demand.identify_zones(data)
            if zones['supply'] or zones['demand']:
                score += 0.2
                factors.append(f"Zones: {len(zones['supply'])} S / {len(zones['demand'])} D")
            
            # Reversals
            reversals = reversal_detector.detect_reversals(data)
            if reversals:
                score += 0.15
                factors.append(f"Reversals: {len(reversals)}")
            
            confluence_scores[tf] = min(score, 1.0)
            self.signals[tf] = {
                'score': score,
                'factors': factors,
                'trend': trend,
                'breakout': breakout,
                'zones': zones,
                'reversals': reversals
            }
        
        return confluence_scores


class TradeSetupEngine:
    """Identifies optimal trade setups based on all analysis."""
    
    MAJOR_PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF']
    
    def __init__(self):
        self.supply_demand = SupplyDemandAnalyzer()
        self.fvg_detector = FairValueGapDetector()
        self.order_block_detector = OrderBlockDetector()
        self.trend_analyzer = TrendAnalyzer()
        self.breakout_detector = BreakoutDetector()
        self.reversal_detector = ReversalDetector()
        self.confluence = MultiTimeframeConfluence()
    
    def identify_setups(
        self,
        symbol: str,
        data_dict: Dict[str, pd.DataFrame]
    ) -> List[TradeSetup]:
        """Identify trade setups from multi-timeframe analysis.
        
        Args:
            symbol: Trading pair symbol
            data_dict: Dict of timeframe -> DataFrame
            
        Returns:
            List of TradeSetup objects (sorted by confluence score)
        """
        setups = []
        
        # Use daily data as base for setup
        if '1d' not in data_dict:
            return setups
        
        daily_data = data_dict['1d']
        if len(daily_data) < 50:
            return setups
        
        # Analyze daily chart
        zones = self.supply_demand.identify_zones(daily_data)
        gaps = self.fvg_detector.find_gaps(daily_data, self._calculate_atr(daily_data))
        blocks = self.order_block_detector.find_blocks(daily_data)
        trend = self.trend_analyzer.analyze_trend(daily_data)
        breakout = self.breakout_detector.detect_breakout(daily_data)
        reversals = self.reversal_detector.detect_reversals(daily_data)
        
        # Get multi-timeframe confluence
        confluence_scores = self.confluence.analyze_confluence(
            data_dict,
            self.supply_demand,
            self.trend_analyzer,
            self.breakout_detector,
            self.reversal_detector
        )
        
        # Create setups based on identified patterns
        
        # Setup 1: Breakout with confluence
        if breakout.breakout_type != BreakoutType.NONE:
            direction = 'BUY' if breakout.breakout_type == BreakoutType.BULLISH else 'SELL'
            entry = breakout.breakout_level
            
            # Set stop loss at recent swing
            if direction == 'BUY':
                stop_loss = daily_data['low'].tail(20).min()
                tp_target = daily_data['high'].iloc[-1] + (daily_data['high'].iloc[-1] - stop_loss)
            else:
                stop_loss = daily_data['high'].tail(20).max()
                tp_target = daily_data['low'].iloc[-1] - (stop_loss - daily_data['low'].iloc[-1])
            
            setup = TradeSetup(
                symbol=symbol,
                direction=direction,
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=tp_target,
                reason=f"Breakout confirmation with {breakout.breakout_strength:.0%} strength",
                confluence_score=sum(confluence_scores.values()) / len(confluence_scores) if confluence_scores else 0.5,
                components=['breakout', 'confluence'],
                timeframe_confluence=confluence_scores
            )
            setups.append(setup)
        
        # Setup 2: Fair Value Gap reversal
        active_gaps = [g for g in gaps if not g.filled and g.mitigation_percentage < 0.7]
        if active_gaps:
            largest_gap = max(active_gaps, key=lambda g: g.severity)
            
            direction = 'BUY' if largest_gap.gap_type == 'up' else 'SELL'
            entry = largest_gap.gap_low if direction == 'BUY' else largest_gap.gap_high
            
            setup = TradeSetup(
                symbol=symbol,
                direction=direction,
                entry_price=entry,
                stop_loss=entry + (entry - largest_gap.gap_high) * 1.5 if direction == 'BUY' else entry - (largest_gap.gap_low - entry) * 1.5,
                take_profit=largest_gap.gap_high if direction == 'BUY' else largest_gap.gap_low,
                reason=f"FVG mitigation - {largest_gap.gap_type} gap at {largest_gap.severity:.2f}x ATR",
                confluence_score=0.6 + (largest_gap.severity * 0.05),
                components=['fvg', 'imbalance']
            )
            setups.append(setup)
        
        # Setup 3: Supply/Demand Zone with trend
        if trend.direction in [TrendDirection.UP, TrendDirection.STRONG_UP]:
            # Look for demand zone
            if zones['demand']:
                best_zone = max(zones['demand'], key=lambda z: z.strength)
                entry = best_zone.price_high
                stop_loss = best_zone.price_low * 0.995
                tp_target = entry + (entry - stop_loss) * 2
                
                setup = TradeSetup(
                    symbol=symbol,
                    direction='BUY',
                    entry_price=entry,
                    stop_loss=stop_loss,
                    take_profit=tp_target,
                    reason=f"Demand zone in {trend.direction.value} trend - {best_zone.strength:.0%} strength",
                    confluence_score=0.65 + trend.strength * 0.2,
                    components=['demand_zone', 'trend', 'confluence']
                )
                setups.append(setup)
        
        elif trend.direction in [TrendDirection.DOWN, TrendDirection.STRONG_DOWN]:
            # Look for supply zone
            if zones['supply']:
                best_zone = max(zones['supply'], key=lambda z: z.strength)
                entry = best_zone.price_low
                stop_loss = best_zone.price_high * 1.005
                tp_target = entry - (stop_loss - entry) * 2
                
                setup = TradeSetup(
                    symbol=symbol,
                    direction='SELL',
                    entry_price=entry,
                    stop_loss=stop_loss,
                    take_profit=tp_target,
                    reason=f"Supply zone in {trend.direction.value} trend - {best_zone.strength:.0%} strength",
                    confluence_score=0.65 + trend.strength * 0.2,
                    components=['supply_zone', 'trend', 'confluence']
                )
                setups.append(setup)
        
        # Setup 4: Order Block with reversal
        if blocks and reversals:
            for block in blocks[-2:]:  # Last 2 blocks
                for reversal in reversals:
                    entry = block.price_high if block.block_type == 'buy' else block.price_low
                    direction = 'BUY' if block.block_type == 'buy' else 'SELL'
                    
                    if direction == 'BUY':
                        stop_loss = block.price_low
                        tp_target = entry + (entry - stop_loss) * 1.5
                    else:
                        stop_loss = block.price_high
                        tp_target = entry - (stop_loss - entry) * 1.5
                    
                    setup = TradeSetup(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry,
                        stop_loss=stop_loss,
                        take_profit=tp_target,
                        reason=f"Order block {block.block_type} + {reversal.pattern_type} pattern",
                        confluence_score=0.7 + reversal.confirmation_strength * 0.2,
                        components=['order_block', 'reversal']
                    )
                    setups.append(setup)
        
        # Calculate risk/reward and probability
        for setup in setups:
            setup.risk_reward_ratio = abs(setup.take_profit - setup.entry_price) / abs(setup.entry_price - setup.stop_loss) if setup.entry_price != setup.stop_loss else 0
            setup.probability_estimate = setup.confluence_score * 0.9
            setup.expected_move_atr_multiple = abs(setup.take_profit - setup.entry_price) / self._calculate_atr(daily_data)
        
        # Sort by confluence score
        return sorted(setups, key=lambda s: s.confluence_score, reverse=True)
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR."""
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift())
        low_close = abs(data['low'] - data['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        return atr if not pd.isna(atr) else 0.01


# ======================== TEST SECTION ========================

if __name__ == '__main__':
    print("=" * 80)
    print("ADVANCED TIMEFRAME ANALYSIS ENGINE - TEST SUITE")
    print("=" * 80)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    data = pd.DataFrame({
        'open': 1.0800 + np.random.randn(200).cumsum() * 0.001,
        'high': 1.0850 + np.random.randn(200).cumsum() * 0.001,
        'low': 1.0750 + np.random.randn(200).cumsum() * 0.001,
        'close': 1.0800 + np.random.randn(200).cumsum() * 0.001,
        'volume': np.random.randint(1000, 5000, 200)
    }, index=dates)
    
    # Ensure realistic OHLC
    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)
    
    print("\n1. Testing Supply/Demand Analyzer...")
    sd_analyzer = SupplyDemandAnalyzer()
    zones = sd_analyzer.identify_zones(data)
    print(f"   ✓ Found {len(zones['supply'])} supply zones, {len(zones['demand'])} demand zones")
    for zone in zones['demand'][:2]:
        print(f"     - Demand: {zone.price_low:.4f}-{zone.price_high:.4f}, Strength: {zone.strength:.2%}, Touches: {zone.touches}")
    
    print("\n2. Testing Fair Value Gap Detector...")
    fvg_detector = FairValueGapDetector()
    gaps = fvg_detector.find_gaps(data, 0.01)
    print(f"   ✓ Found {len(gaps)} fair value gaps")
    for gap in gaps[:2]:
        print(f"     - {gap.gap_type.upper()}: {gap.gap_low:.4f}-{gap.gap_high:.4f}, Severity: {gap.severity:.2f}x ATR")
    
    print("\n3. Testing Order Block Detector...")
    ob_detector = OrderBlockDetector()
    blocks = ob_detector.find_blocks(data)
    print(f"   ✓ Found {len(blocks)} order blocks")
    for block in blocks[:2]:
        print(f"     - {block.block_type.upper()}: {block.price_low:.4f}-{block.price_high:.4f}, Volume: {block.volume_strength:.0%}")
    
    print("\n4. Testing Trend Analyzer...")
    trend_analyzer = TrendAnalyzer()
    trend = trend_analyzer.analyze_trend(data)
    print(f"   ✓ Trend: {trend.direction.value}, Strength: {trend.strength:.0%}")
    print(f"     Higher High: {trend.higher_high}, Higher Low: {trend.higher_low}")
    print(f"     Imbalances: {trend.imbalance_count}")
    
    print("\n5. Testing Breakout Detector...")
    breakout_detector = BreakoutDetector()
    breakout = breakout_detector.detect_breakout(data)
    print(f"   ✓ Breakout: {breakout.breakout_type.value}, Strength: {breakout.breakout_strength:.0%}")
    print(f"     Retest: {breakout.retest_occurred}, False Prob: {breakout.false_breakout_probability:.0%}")
    
    print("\n6. Testing Reversal Detector...")
    reversal_detector = ReversalDetector()
    reversals = reversal_detector.detect_reversals(data)
    print(f"   ✓ Found {len(reversals)} reversal patterns")
    for rev in reversals:
        print(f"     - {rev.pattern_type.upper()}: Severity {rev.severity:.0%}, Confirmation {rev.confirmation_strength:.0%}")
    
    print("\n7. Testing Trade Setup Engine...")
    engine = TradeSetupEngine()
    data_dict = {'1d': data}
    setups = engine.identify_setups('EURUSD', data_dict)
    print(f"   ✓ Identified {len(setups)} trade setups")
    for i, setup in enumerate(setups, 1):
        print(f"     Setup {i}: {setup.direction} @ {setup.entry_price:.4f}")
        print(f"       SL: {setup.stop_loss:.4f}, TP: {setup.take_profit:.4f}")
        print(f"       R:R: {setup.risk_reward_ratio:.2f}, Confluence: {setup.confluence_score:.0%}")
        print(f"       Components: {', '.join(setup.components)}")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 80)
