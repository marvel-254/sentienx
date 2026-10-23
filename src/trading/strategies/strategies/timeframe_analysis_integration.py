"""
Timeframe Analysis Integration with SENTIENX Trading System

Connects the advanced timeframe analysis to the main trading engine,
providing smart money analysis and setup identification for deriv pairs.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.timeframe_analysis import (
    TradeSetupEngine, TrendDirection, BreakoutType,
    SupplyDemandZone, FairValueGap, OrderBlock, TradeSetup
)


@dataclass
class TimeframeSignal:
    """Signal from timeframe analysis."""
    symbol: str
    timeframe: str
    signal_type: str  # 'setup', 'confirmation', 'warning', 'reversal'
    direction: str  # 'BUY', 'SELL', 'NEUTRAL'
    strength: float  # 0-1
    components: List[str] = field(default_factory=list)
    entry_zone: Tuple[float, float] = (0.0, 0.0)
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    confluence_score: float = 0.0


@dataclass
class DailyMarketAnalysis:
    """Complete daily analysis for a pair."""
    symbol: str
    date: datetime
    trend_direction: TrendDirection
    trend_strength: float
    setups: List[TradeSetup] = field(default_factory=list)
    supply_zones: List[SupplyDemandZone] = field(default_factory=list)
    demand_zones: List[SupplyDemandZone] = field(default_factory=list)
    fair_value_gaps: List[FairValueGap] = field(default_factory=list)
    order_blocks: List[OrderBlock] = field(default_factory=list)
    key_levels: Dict[str, float] = field(default_factory=dict)
    primary_direction: str = "NEUTRAL"
    risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    best_setup: Optional[TradeSetup] = None


class DailyAnalysisManager:
    """Manages daily timeframe analysis for deriv pairs."""
    
    MAJOR_PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF']
    
    def __init__(self):
        self.setup_engine = TradeSetupEngine()
        self.analyses: Dict[str, DailyMarketAnalysis] = {}
        self.last_update: Dict[str, datetime] = {}
    
    def analyze_pair(self, symbol: str, data_dict: Dict[str, pd.DataFrame]) -> DailyMarketAnalysis:
        """Perform complete analysis for a pair.
        
        Args:
            symbol: Trading pair symbol
            data_dict: Dictionary of timeframe -> DataFrame (15m, 1h, 4h, 1d)
            
        Returns:
            DailyMarketAnalysis with all components
        """
        if symbol not in self.MAJOR_PAIRS:
            raise ValueError(f"Pair {symbol} not in supported major pairs: {self.MAJOR_PAIRS}")
        
        # Get setups from engine
        setups = self.setup_engine.identify_setups(symbol, data_dict)
        
        # Extract components from daily data
        daily_data = data_dict.get('1d')
        if daily_data is None or len(daily_data) < 50:
            return DailyMarketAnalysis(
                symbol=symbol,
                date=datetime.now(),
                trend_direction=TrendDirection.NEUTRAL,
                trend_strength=0.0
            )
        
        # Analyze components
        zones = self.setup_engine.supply_demand.identify_zones(daily_data)
        gaps = self.setup_engine.fvg_detector.find_gaps(
            daily_data,
            self.setup_engine._calculate_atr(daily_data)
        )
        blocks = self.setup_engine.order_block_detector.find_blocks(daily_data)
        trend = self.setup_engine.trend_analyzer.analyze_trend(daily_data)
        
        # Determine primary direction
        if trend.direction in [TrendDirection.UP, TrendDirection.STRONG_UP]:
            primary = "BUY"
        elif trend.direction in [TrendDirection.DOWN, TrendDirection.STRONG_DOWN]:
            primary = "SELL"
        else:
            primary = "NEUTRAL"
        
        # Determine risk level based on volatility and imbalances
        atr = self.setup_engine._calculate_atr(daily_data)
        current_range = daily_data['high'].iloc[-1] - daily_data['low'].iloc[-1]
        volatility = current_range / atr
        
        if volatility > 1.5 or len([g for g in gaps if not g.filled]) > 3:
            risk = "HIGH"
        elif volatility < 0.7 and len(setups) < 2:
            risk = "LOW"
        else:
            risk = "MEDIUM"
        
        # Get key levels
        key_levels = {
            'pivot_high': trend.pivot_high,
            'pivot_low': trend.pivot_low,
            'resistance': daily_data['high'].tail(20).max(),
            'support': daily_data['low'].tail(20).min(),
            'atr': atr,
            'current_price': daily_data['close'].iloc[-1]
        }
        
        # Select best setup
        best_setup = setups[0] if setups else None
        
        analysis = DailyMarketAnalysis(
            symbol=symbol,
            date=datetime.now(),
            trend_direction=trend.direction,
            trend_strength=trend.strength,
            setups=setups,
            supply_zones=zones['supply'],
            demand_zones=zones['demand'],
            fair_value_gaps=gaps,
            order_blocks=blocks,
            key_levels=key_levels,
            primary_direction=primary,
            risk_level=risk,
            best_setup=best_setup
        )
        
        self.analyses[symbol] = analysis
        self.last_update[symbol] = datetime.now()
        
        return analysis
    
    def get_analysis(self, symbol: str) -> Optional[DailyMarketAnalysis]:
        """Retrieve cached analysis for a pair."""
        return self.analyses.get(symbol)
    
    def is_analysis_fresh(self, symbol: str, max_age_minutes: int = 60) -> bool:
        """Check if analysis is fresh."""
        if symbol not in self.last_update:
            return False
        
        age = (datetime.now() - self.last_update[symbol]).total_seconds() / 60
        return age < max_age_minutes
    
    def get_all_analyses(self) -> Dict[str, DailyMarketAnalysis]:
        """Get all current analyses."""
        return self.analyses.copy()


class TimeframeSignalGenerator:
    """Generates trading signals from timeframe analysis."""
    
    def __init__(self, analysis_manager: DailyAnalysisManager):
        self.manager = analysis_manager
        self.signals: Dict[str, List[TimeframeSignal]] = {}
    
    def generate_signals(self, symbol: str, data_dict: Dict[str, pd.DataFrame]) -> List[TimeframeSignal]:
        """Generate signals for a pair.
        
        Args:
            symbol: Trading pair symbol
            data_dict: Dictionary of timeframe -> DataFrame
            
        Returns:
            List of TimeframeSignal objects
        """
        signals = []
        
        # Get analysis
        analysis = self.manager.analyze_pair(symbol, data_dict)
        
        # Setup signals
        if analysis.best_setup:
            setup = analysis.best_setup
            signal = TimeframeSignal(
                symbol=symbol,
                timeframe='1d',
                signal_type='setup',
                direction=setup.direction,
                strength=min(setup.confluence_score, 1.0),
                components=setup.components,
                entry_zone=(setup.entry_price * 0.998, setup.entry_price * 1.002),
                stop_loss=setup.stop_loss,
                take_profit=setup.take_profit,
                reason=setup.reason,
                confluence_score=setup.confluence_score
            )
            signals.append(signal)
        
        # Confirmation signals from multiple timeframes
        if data_dict.get('4h') is not None:
            h4_signal = self._analyze_4h_confirmation(symbol, data_dict['4h'], analysis)
            if h4_signal:
                signals.append(h4_signal)
        
        if data_dict.get('1h') is not None:
            h1_signal = self._analyze_1h_entry(symbol, data_dict['1h'], analysis)
            if h1_signal:
                signals.append(h1_signal)
        
        # Warning signals
        if analysis.risk_level == "HIGH":
            warning = TimeframeSignal(
                symbol=symbol,
                timeframe='1d',
                signal_type='warning',
                direction='NEUTRAL',
                strength=0.7,
                reason='High volatility or multiple imbalances detected',
                components=['volatility_warning', 'imbalance_risk']
            )
            signals.append(warning)
        
        # Reversal signals
        reversals = self.manager.setup_engine.reversal_detector.detect_reversals(data_dict['1d'])
        if reversals:
            for rev in reversals:
                if rev.confirmation_strength > 0.7:
                    direction = 'BUY' if 'engulfing' in rev.pattern_type and analysis.trend_direction == TrendDirection.DOWN else 'SELL'
                    signal = TimeframeSignal(
                        symbol=symbol,
                        timeframe='1d',
                        signal_type='reversal',
                        direction=direction,
                        strength=rev.confirmation_strength,
                        components=[rev.pattern_type],
                        reason=f'{rev.pattern_type.upper()} reversal pattern detected'
                    )
                    signals.append(signal)
        
        self.signals[symbol] = signals
        return signals
    
    def _analyze_4h_confirmation(
        self,
        symbol: str,
        h4_data: pd.DataFrame,
        daily_analysis: DailyMarketAnalysis
    ) -> Optional[TimeframeSignal]:
        """Analyze 4h timeframe for confirmation."""
        if len(h4_data) < 50:
            return None
        
        # Get trend on 4h
        h4_trend = self.manager.setup_engine.trend_analyzer.analyze_trend(h4_data)
        
        # Check if 4h aligns with daily
        daily_direction = daily_analysis.primary_direction
        if daily_direction == "BUY" and h4_trend.direction in [TrendDirection.UP, TrendDirection.STRONG_UP]:
            return TimeframeSignal(
                symbol=symbol,
                timeframe='4h',
                signal_type='confirmation',
                direction='BUY',
                strength=0.7 + h4_trend.strength * 0.3,
                reason='4H trend confirms daily BUY bias',
                components=['trend_confirmation'],
                confluence_score=0.8
            )
        elif daily_direction == "SELL" and h4_trend.direction in [TrendDirection.DOWN, TrendDirection.STRONG_DOWN]:
            return TimeframeSignal(
                symbol=symbol,
                timeframe='4h',
                signal_type='confirmation',
                direction='SELL',
                strength=0.7 + h4_trend.strength * 0.3,
                reason='4H trend confirms daily SELL bias',
                components=['trend_confirmation'],
                confluence_score=0.8
            )
        
        return None
    
    def _analyze_1h_entry(
        self,
        symbol: str,
        h1_data: pd.DataFrame,
        daily_analysis: DailyMarketAnalysis
    ) -> Optional[TimeframeSignal]:
        """Analyze 1h timeframe for entry triggers."""
        if len(h1_data) < 50:
            return None
        
        # Get breakout on 1h
        h1_breakout = self.manager.setup_engine.breakout_detector.detect_breakout(h1_data)
        
        # Check if 1h breakout aligns with daily direction
        daily_direction = daily_analysis.primary_direction
        
        if (daily_direction == "BUY" and h1_breakout.breakout_type == BreakoutType.BULLISH) or \
           (daily_direction == "SELL" and h1_breakout.breakout_type == BreakoutType.BEARISH):
            
            return TimeframeSignal(
                symbol=symbol,
                timeframe='1h',
                signal_type='entry',
                direction=daily_direction,
                strength=h1_breakout.breakout_strength,
                reason=f'1H {daily_direction} breakout - Entry trigger',
                components=['breakout', 'entry_trigger'],
                confluence_score=0.75 + h1_breakout.breakout_strength * 0.2
            )
        
        return None
    
    def get_signals(self, symbol: str) -> List[TimeframeSignal]:
        """Retrieve cached signals for a pair."""
        return self.signals.get(symbol, [])


class SmartMoneyAnalyzer:
    """Analyzes smart money order flow and institutional activity."""
    
    def __init__(self):
        self.order_blocks: Dict[str, List[OrderBlock]] = {}
        self.liquidity_hunts: Dict[str, List[Tuple[float, datetime]]] = {}
    
    def identify_smart_money_moves(
        self,
        symbol: str,
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, any]:
        """Identify smart money patterns.
        
        Args:
            symbol: Trading pair symbol
            data_dict: Dictionary of timeframe -> DataFrame
            
        Returns:
            Dict with smart money analysis
        """
        daily_data = data_dict.get('1d')
        if daily_data is None:
            return {}
        
        engine = TradeSetupEngine()
        blocks = engine.order_block_detector.find_blocks(daily_data)
        gaps = engine.fvg_detector.find_gaps(daily_data, engine._calculate_atr(daily_data))
        
        # Identify liquidity hunt levels
        hunts = self._identify_liquidity_hunts(daily_data, blocks)
        
        # Find order block breakouts
        ob_breakouts = self._find_order_block_breakouts(daily_data, blocks)
        
        # Analyze institutional accumulation/distribution
        accum_dist = self._analyze_accumulation_distribution(daily_data)
        
        analysis = {
            'order_blocks': blocks,
            'fair_value_gaps': gaps,
            'liquidity_hunts': hunts,
            'ob_breakouts': ob_breakouts,
            'accumulation_distribution': accum_dist,
            'smart_money_confidence': self._calculate_sm_confidence(hunts, ob_breakouts)
        }
        
        return analysis
    
    def _identify_liquidity_hunts(
        self,
        data: pd.DataFrame,
        blocks: List[OrderBlock]
    ) -> List[Tuple[float, str, datetime]]:
        """Identify liquidity hunt levels."""
        hunts = []
        recent_data = data.tail(20)
        
        for block in blocks:
            # Check if price swept through block
            if block.block_type == 'buy':
                if recent_data['low'].min() < block.price_low:
                    hunts.append((block.price_low, 'buy_stop_hunt', recent_data.index[-1]))
            else:
                if recent_data['high'].max() > block.price_high:
                    hunts.append((block.price_high, 'sell_stop_hunt', recent_data.index[-1]))
        
        return hunts
    
    def _find_order_block_breakouts(
        self,
        data: pd.DataFrame,
        blocks: List[OrderBlock]
    ) -> List[Tuple[OrderBlock, str, float]]:
        """Find order block breakouts."""
        breakouts = []
        current_price = data['close'].iloc[-1]
        
        for block in blocks[-3:]:  # Last 3 blocks
            if block.block_type == 'buy' and current_price > block.price_high:
                breakouts.append((block, 'bullish_break', current_price))
            elif block.block_type == 'sell' and current_price < block.price_low:
                breakouts.append((block, 'bearish_break', current_price))
        
        return breakouts
    
    def _analyze_accumulation_distribution(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze accumulation/distribution pattern."""
        # Calculate A/D line
        close_diff = data['close'] - data['close'].shift(1)
        hl_range = data['high'] - data['low']
        
        hl_range = hl_range.replace(0, 1)  # Avoid division by zero
        adl = ((close_diff / hl_range) * data['volume']).cumsum()
        
        # Trend in A/D
        recent_ad = adl.tail(20)
        ad_trend = "up" if recent_ad.iloc[-1] > recent_ad.iloc[0] else "down"
        ad_strength = abs(recent_ad.iloc[-1] - recent_ad.iloc[0]) / recent_ad.mean() if recent_ad.mean() != 0 else 0
        
        return {
            'trend': ad_trend,
            'strength': min(abs(ad_strength), 1.0),
            'current_value': adl.iloc[-1],
            'divergence': self._check_price_ad_divergence(data, adl)
        }
    
    def _check_price_ad_divergence(self, price_data: pd.DataFrame, ad_line: pd.Series) -> bool:
        """Check for price/A&D divergence."""
        price_recent = price_data['close'].tail(10)
        ad_recent = ad_line.tail(10)
        
        price_up = price_recent.iloc[-1] > price_recent.iloc[0]
        ad_up = ad_recent.iloc[-1] > ad_recent.iloc[0]
        
        # Divergence if direction differs
        return price_up != ad_up
    
    def _calculate_sm_confidence(
        self,
        hunts: List,
        ob_breakouts: List
    ) -> float:
        """Calculate smart money confidence (0-1)."""
        score = 0.5
        score += len(hunts) * 0.1
        score += len(ob_breakouts) * 0.15
        return min(score, 1.0)


class IntegratedTimeframeAnalyzer:
    """Main integration point for all timeframe analysis."""
    
    def __init__(self):
        self.analysis_manager = DailyAnalysisManager()
        self.signal_generator = TimeframeSignalGenerator(self.analysis_manager)
        self.smart_money = SmartMoneyAnalyzer()
    
    def analyze_all_pairs(self, data_dict: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, Dict]:
        """Analyze all major pairs.
        
        Args:
            data_dict: Dict of symbol -> (timeframe -> DataFrame)
            
        Returns:
            Dict with analysis for each pair
        """
        results = {}
        
        for symbol in DailyAnalysisManager.MAJOR_PAIRS:
            if symbol not in data_dict:
                continue
            
            pair_data = data_dict[symbol]
            
            # Generate signals
            signals = self.signal_generator.generate_signals(symbol, pair_data)
            
            # Get daily analysis
            analysis = self.analysis_manager.get_analysis(symbol)
            
            # Smart money analysis
            sm_analysis = self.smart_money.identify_smart_money_moves(symbol, pair_data)
            
            results[symbol] = {
                'signals': signals,
                'analysis': analysis,
                'smart_money': sm_analysis,
                'timestamp': datetime.now()
            }
        
        return results
    
    def get_best_setup(self) -> Optional[Tuple[str, TradeSetup]]:
        """Get the best trade setup across all pairs.
        
        Returns:
            Tuple of (symbol, TradeSetup) or None
        """
        best_setup = None
        best_score = 0.0
        best_symbol = None
        
        for symbol, analysis in self.analysis_manager.get_all_analyses().items():
            if analysis.best_setup and analysis.best_setup.confluence_score > best_score:
                best_score = analysis.best_setup.confluence_score
                best_setup = analysis.best_setup
                best_symbol = symbol
        
        return (best_symbol, best_setup) if best_setup else None
    
    def get_all_valid_setups(self, min_confluence: float = 0.65) -> List[Tuple[str, TradeSetup]]:
        """Get all valid setups meeting minimum confluence.
        
        Args:
            min_confluence: Minimum confluence score (0-1)
            
        Returns:
            List of (symbol, TradeSetup) tuples
        """
        setups = []
        
        for symbol, analysis in self.analysis_manager.get_all_analyses().items():
            for setup in analysis.setups:
                if setup.confluence_score >= min_confluence:
                    setups.append((symbol, setup))
        
        return sorted(setups, key=lambda x: x[1].confluence_score, reverse=True)


# ======================== USAGE EXAMPLE ========================

if __name__ == '__main__':
    print("=" * 80)
    print("TIMEFRAME ANALYSIS INTEGRATION - EXAMPLE")
    print("=" * 80)
    
    # Create sample data for demonstration
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=200, freq='1d')
    
    sample_data = {
        'EURUSD': {
            '1d': pd.DataFrame({
                'open': 1.0800 + np.random.randn(200).cumsum() * 0.001,
                'high': 1.0850 + np.random.randn(200).cumsum() * 0.001,
                'low': 1.0750 + np.random.randn(200).cumsum() * 0.001,
                'close': 1.0800 + np.random.randn(200).cumsum() * 0.001,
                'volume': np.random.randint(50000, 100000, 200)
            }, index=dates)
        }
    }
    
    # Ensure realistic OHLC
    for symbol in sample_data:
        for tf in sample_data[symbol]:
            df = sample_data[symbol][tf]
            df['high'] = df[['open', 'high', 'close']].max(axis=1)
            df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    print("\n1. Testing Daily Analysis Manager...")
    manager = DailyAnalysisManager()
    analysis = manager.analyze_pair('EURUSD', sample_data['EURUSD'])
    print(f"   ✓ Trend: {analysis.trend_direction.value}, Strength: {analysis.trend_strength:.0%}")
    print(f"   ✓ Primary Direction: {analysis.primary_direction}, Risk: {analysis.risk_level}")
    print(f"   ✓ Setups Found: {len(analysis.setups)}")
    if analysis.best_setup:
        print(f"   ✓ Best Setup: {analysis.best_setup.direction} @ {analysis.best_setup.entry_price:.4f}")
    
    print("\n2. Testing Signal Generator...")
    gen = TimeframeSignalGenerator(manager)
    signals = gen.generate_signals('EURUSD', sample_data['EURUSD'])
    print(f"   ✓ Signals Generated: {len(signals)}")
    for sig in signals:
        print(f"     - {sig.signal_type.upper()}: {sig.direction}, Strength: {sig.strength:.0%}")
    
    print("\n3. Testing Smart Money Analyzer...")
    sm = SmartMoneyAnalyzer()
    sm_analysis = sm.identify_smart_money_moves('EURUSD', sample_data['EURUSD'])
    print(f"   ✓ Order Blocks: {len(sm_analysis.get('order_blocks', []))}")
    print(f"   ✓ Liquidity Hunts: {len(sm_analysis.get('liquidity_hunts', []))}")
    print(f"   ✓ SM Confidence: {sm_analysis.get('smart_money_confidence', 0):.0%}")
    
    print("\n" + "=" * 80)
    print("✅ INTEGRATION TESTS COMPLETED")
    print("=" * 80)
