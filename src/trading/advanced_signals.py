"""
Advanced Trading Signal Engine for KORA/SENTIENX
Implements multi-timeframe analysis, signal confirmation, anomaly detection, and custom strategies
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import deque
from enum import Enum

class SignalStrength(Enum):
    """Signal strength classification"""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4

class AnomalyType(Enum):
    """Types of market anomalies"""
    PRICE_SPIKE = "price_spike"
    VOLUME_SURGE = "volume_surge"
    VOLATILITY_EXPANSION = "volatility_expansion"
    UNUSUAL_MOMENTUM = "unusual_momentum"
    GAP = "gap"

class SignalConfirmation:
    """Multi-factor signal confirmation system"""
    
    def __init__(self, min_confirmation_factors: int = 3):
        self.min_confirmation_factors = min_confirmation_factors
        self.confirmation_factors = []
        
    def add_factor(self, factor_name: str, factor_value: float):
        """Add a confirmation factor (0-1 scale)"""
        self.confirmation_factors.append({
            'name': factor_name,
            'value': factor_value,
            'timestamp': datetime.now()
        })
    
    def get_confirmation_score(self) -> float:
        """Get overall confirmation score"""
        if not self.confirmation_factors:
            return 0.0
        
        avg_value = np.mean([f['value'] for f in self.confirmation_factors])
        factor_count = len(self.confirmation_factors)
        
        # Reward multiple confirmations
        count_bonus = min(factor_count / self.min_confirmation_factors, 1.5)
        
        return min(avg_value * count_bonus, 1.0)
    
    def is_confirmed(self) -> bool:
        """Check if signal is confirmed"""
        if len(self.confirmation_factors) < self.min_confirmation_factors:
            return False
        return self.get_confirmation_score() > 0.65
    
    def get_summary(self) -> Dict[str, Any]:
        """Get confirmation summary"""
        return {
            'factors': self.confirmation_factors,
            'confirmation_score': self.get_confirmation_score(),
            'is_confirmed': self.is_confirmed(),
            'factor_count': len(self.confirmation_factors)
        }

class AnomalyDetector:
    """Detect market anomalies using statistical methods"""
    
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.price_history = deque(maxlen=window_size)
        self.volume_history = deque(maxlen=window_size)
        self.volatility_history = deque(maxlen=window_size)
        self.anomalies = deque(maxlen=100)
        
    def add_candle(self, candle: Dict[str, float]):
        """Add OHLCV candle for analysis"""
        self.price_history.append({
            'open': candle.get('open', 0),
            'high': candle.get('high', 0),
            'low': candle.get('low', 0),
            'close': candle.get('close', 0)
        })
        self.volume_history.append(candle.get('volume', 0))
        
        # Calculate volatility (high-low range)
        if len(self.price_history) > 0:
            volatility = (candle.get('high', 0) - candle.get('low', 0)) / candle.get('close', 1)
            self.volatility_history.append(volatility)
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect all types of anomalies"""
        anomalies = []
        
        if len(self.price_history) < 5:
            return anomalies
        
        # Detect price spikes
        price_spike = self._detect_price_spike()
        if price_spike:
            anomalies.append(price_spike)
        
        # Detect volume surges
        volume_surge = self._detect_volume_surge()
        if volume_surge:
            anomalies.append(volume_surge)
        
        # Detect volatility changes
        vol_change = self._detect_volatility_change()
        if vol_change:
            anomalies.append(vol_change)
        
        # Detect gaps
        gap = self._detect_gap()
        if gap:
            anomalies.append(gap)
        
        # Store in history
        for anomaly in anomalies:
            self.anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_price_spike(self) -> Optional[Dict[str, Any]]:
        """Detect unusual price spike"""
        if len(self.price_history) < 5:
            return None
        
        closes = [p['close'] for p in self.price_history]
        recent = closes[-1]
        avg = np.mean(closes[:-1])
        std = np.std(closes[:-1])
        
        z_score = abs((recent - avg) / (std + 1e-8))
        
        if z_score > 3:  # 3 std deviations
            return {
                'type': AnomalyType.PRICE_SPIKE,
                'severity': min(z_score / 5, 1.0),
                'value': recent,
                'average': avg,
                'z_score': z_score,
                'timestamp': datetime.now()
            }
        
        return None
    
    def _detect_volume_surge(self) -> Optional[Dict[str, Any]]:
        """Detect unusual volume spike"""
        if len(self.volume_history) < 5:
            return None
        
        volumes = list(self.volume_history)
        recent = volumes[-1]
        avg = np.mean(volumes[:-1])
        
        if recent > avg * 2:  # Volume doubled
            severity = min((recent - avg) / avg / 2, 1.0)
            return {
                'type': AnomalyType.VOLUME_SURGE,
                'severity': severity,
                'current_volume': recent,
                'average_volume': avg,
                'multiplier': recent / (avg + 1e-8),
                'timestamp': datetime.now()
            }
        
        return None
    
    def _detect_volatility_change(self) -> Optional[Dict[str, Any]]:
        """Detect significant volatility changes"""
        if len(self.volatility_history) < 10:
            return None
        
        vols = list(self.volatility_history)
        recent_avg = np.mean(vols[-5:])
        historical_avg = np.mean(vols[:-5])
        
        ratio = recent_avg / (historical_avg + 1e-8)
        
        if ratio > 1.5 or ratio < 0.5:
            return {
                'type': AnomalyType.VOLATILITY_EXPANSION,
                'severity': abs(1 - ratio) / 2 if ratio > 1 else (ratio - 0.5),
                'current_volatility': recent_avg,
                'historical_volatility': historical_avg,
                'ratio': ratio,
                'expansion': ratio > 1,
                'timestamp': datetime.now()
            }
        
        return None
    
    def _detect_gap(self) -> Optional[Dict[str, Any]]:
        """Detect price gaps between candles"""
        if len(self.price_history) < 2:
            return None
        
        prev_close = self.price_history[-2]['close']
        current_open = self.price_history[-1]['open']
        
        gap = abs(current_open - prev_close) / prev_close
        
        if gap > 0.01:  # Gap > 1%
            return {
                'type': AnomalyType.GAP,
                'severity': min(gap, 0.05),
                'gap_size': gap,
                'direction': 'up' if current_open > prev_close else 'down',
                'previous_close': prev_close,
                'current_open': current_open,
                'timestamp': datetime.now()
            }
        
        return None
    
    def get_anomaly_summary(self) -> Dict[str, Any]:
        """Get summary of recent anomalies"""
        recent_anomalies = list(self.anomalies)[-20:]
        
        anomaly_counts = {}
        for anomaly in recent_anomalies:
            atype = anomaly['type'].value
            anomaly_counts[atype] = anomaly_counts.get(atype, 0) + 1
        
        return {
            'recent_count': len(recent_anomalies),
            'anomaly_types': anomaly_counts,
            'recent_anomalies': recent_anomalies,
            'is_anomalous': len(recent_anomalies) > 5
        }

class MultiTimeframeAnalyzer:
    """Analyze signals across multiple timeframes"""
    
    def __init__(self):
        self.timeframe_signals = {}
        self.signal_history = deque(maxlen=500)
        
    def add_signal(self, timeframe: str, signal: str, confidence: float, indicators: Dict[str, float] = None):
        """Add signal from a specific timeframe"""
        record = {
            'timeframe': timeframe,
            'signal': signal,
            'confidence': confidence,
            'indicators': indicators or {},
            'timestamp': datetime.now()
        }
        
        if timeframe not in self.timeframe_signals:
            self.timeframe_signals[timeframe] = deque(maxlen=100)
        
        self.timeframe_signals[timeframe].append(record)
        self.signal_history.append(record)
    
    def get_consensus(self, required_timeframes: int = 2) -> Dict[str, Any]:
        """Get consensus signal across timeframes"""
        if len(self.timeframe_signals) < required_timeframes:
            return {
                'consensus': 'HOLD',
                'strength': SignalStrength.WEAK,
                'alignment': 0.0
            }
        
        signals = []
        confidences = []
        
        for timeframe, sig_list in self.timeframe_signals.items():
            if len(sig_list) > 0:
                latest = sig_list[-1]
                signals.append(latest['signal'])
                confidences.append(latest['confidence'])
        
        # Get majority signal
        if not signals:
            return {'consensus': 'HOLD', 'strength': SignalStrength.WEAK, 'alignment': 0.0}
        
        buy_count = signals.count('BUY')
        sell_count = signals.count('SELL')
        
        if buy_count > sell_count:
            consensus = 'BUY'
            alignment = buy_count / len(signals)
        elif sell_count > buy_count:
            consensus = 'SELL'
            alignment = sell_count / len(signals)
        else:
            consensus = 'HOLD'
            alignment = 0.5
        
        # Determine strength
        strength = self._alignment_to_strength(alignment)
        
        return {
            'consensus': consensus,
            'alignment': alignment,
            'strength': strength,
            'participating_timeframes': len(signals),
            'avg_confidence': np.mean(confidences),
            'timeframe_votes': {'BUY': buy_count, 'SELL': sell_count, 'HOLD': len(signals) - buy_count - sell_count}
        }
    
    def _alignment_to_strength(self, alignment: float) -> SignalStrength:
        """Convert alignment score to signal strength"""
        if alignment >= 0.9:
            return SignalStrength.VERY_STRONG
        elif alignment >= 0.75:
            return SignalStrength.STRONG
        elif alignment >= 0.6:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
    
    def get_divergences(self) -> List[Dict[str, Any]]:
        """Detect divergences between timeframes"""
        divergences = []
        
        timeframes = list(self.timeframe_signals.keys())
        for i, tf1 in enumerate(timeframes):
            for tf2 in timeframes[i+1:]:
                if len(self.timeframe_signals[tf1]) > 0 and len(self.timeframe_signals[tf2]) > 0:
                    sig1 = self.timeframe_signals[tf1][-1]['signal']
                    sig2 = self.timeframe_signals[tf2][-1]['signal']
                    
                    if sig1 != sig2 and sig1 != 'HOLD' and sig2 != 'HOLD':
                        divergences.append({
                            'timeframe_1': tf1,
                            'signal_1': sig1,
                            'timeframe_2': tf2,
                            'signal_2': sig2,
                            'timestamp': datetime.now()
                        })
        
        return divergences

class AdvancedTradingSignalEngine:
    """Advanced signal generation engine combining multiple analysis methods"""
    
    def __init__(self):
        self.anomaly_detector = AnomalyDetector(window_size=50)
        self.mtf_analyzer = MultiTimeframeAnalyzer()
        self.active_signals = {}
        self.signal_history = deque(maxlen=1000)
        self.performance_tracker = {
            'correct_signals': 0,
            'total_signals': 0,
            'win_rate': 0.0
        }
    
    def analyze_with_confirmation(self, signal: str, confidence: float, 
                                 indicators: Dict[str, float] = None) -> Dict[str, Any]:
        """Analyze signal with multi-factor confirmation"""
        confirmation = SignalConfirmation(min_confirmation_factors=3)
        
        # Add technical confirmation
        if indicators:
            if indicators.get('rsi_extreme', False):
                confirmation.add_factor('RSI_Extreme', 0.8)
            
            if indicators.get('macd_divergence', False):
                confirmation.add_factor('MACD_Divergence', 0.7)
            
            if indicators.get('bb_breakout', False):
                confirmation.add_factor('BB_Breakout', 0.8)
            
            if indicators.get('momentum_aligned', False):
                confirmation.add_factor('Momentum_Aligned', 0.75)
            
            if indicators.get('volume_confirmed', False):
                confirmation.add_factor('Volume_Confirmed', 0.85)
        
        # Base confidence factor
        confirmation.add_factor('Base_Confidence', confidence)
        
        return {
            'signal': signal,
            'base_confidence': confidence,
            'confirmation': confirmation.get_summary(),
            'is_confirmed': confirmation.is_confirmed(),
            'final_strength': self._get_signal_strength(
                confidence, 
                confirmation.get_confirmation_score()
            ),
            'timestamp': datetime.now()
        }
    
    def _get_signal_strength(self, confidence: float, confirmation_score: float) -> SignalStrength:
        """Determine signal strength from confidence and confirmation"""
        combined_score = (confidence + confirmation_score) / 2
        
        if combined_score >= 0.85:
            return SignalStrength.VERY_STRONG
        elif combined_score >= 0.70:
            return SignalStrength.STRONG
        elif combined_score >= 0.55:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
    
    def add_candle_data(self, candle: Dict[str, float]):
        """Add OHLCV data for anomaly detection"""
        self.anomaly_detector.add_candle(candle)
    
    def generate_advanced_signal(self, symbol: str, base_signal: str, 
                               base_confidence: float,
                               indicators: Dict[str, float] = None) -> Dict[str, Any]:
        """Generate advanced trading signal with all analysis"""
        
        # Detect anomalies
        anomalies = self.anomaly_detector.detect_anomalies()
        anomaly_impact = self._calculate_anomaly_impact(anomalies, base_signal)
        
        # Apply anomaly adjustment
        adjusted_confidence = base_confidence * (1 - anomaly_impact * 0.3)
        
        # Get confirmation
        confirmed_analysis = self.analyze_with_confirmation(base_signal, adjusted_confidence, indicators)
        
        # Check for anomalies that contradict signal
        contradicting_anomalies = [a for a in anomalies if self._is_contradicting(a, base_signal)]
        
        # Final signal determination
        if contradicting_anomalies and adjusted_confidence < 0.60:
            final_signal = 'HOLD'
            reason = 'Market anomaly contradicts signal'
        else:
            final_signal = base_signal if confirmed_analysis['is_confirmed'] else 'HOLD'
            reason = 'Confirmed' if confirmed_analysis['is_confirmed'] else 'Insufficient confirmation'
        
        result = {
            'symbol': symbol,
            'signal': final_signal,
            'base_signal': base_signal,
            'confidence': adjusted_confidence,
            'strength': confirmed_analysis['final_strength'],
            'confirmation_summary': confirmed_analysis['confirmation'],
            'anomalies_detected': len(anomalies),
            'anomaly_types': [a['type'].value for a in anomalies],
            'reason': reason,
            'timestamp': datetime.now()
        }
        
        # Track performance
        self.signal_history.append(result)
        self.active_signals[symbol] = result
        self.performance_tracker['total_signals'] += 1
        
        return result
    
    def _calculate_anomaly_impact(self, anomalies: List[Dict], signal: str) -> float:
        """Calculate how much anomalies impact the signal"""
        if not anomalies:
            return 0.0
        
        total_severity = sum(a.get('severity', 0.5) for a in anomalies)
        return min(total_severity / len(anomalies), 1.0)
    
    def _is_contradicting(self, anomaly: Dict, signal: str) -> bool:
        """Check if anomaly contradicts the signal"""
        atype = anomaly['type']
        
        if atype == AnomalyType.PRICE_SPIKE:
            # Spike contradicts if moving opposite direction
            return anomaly.get('z_score', 0) > 3
        
        return False
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get comprehensive engine status"""
        return {
            'active_signals': len(self.active_signals),
            'total_signals_generated': self.performance_tracker['total_signals'],
            'performance': self.performance_tracker,
            'recent_signals': list(self.signal_history)[-10:],
            'anomaly_summary': self.anomaly_detector.get_anomaly_summary(),
            'mtf_consensus': self.mtf_analyzer.get_consensus(),
            'divergences': self.mtf_analyzer.get_divergences()
        }

# Convenience functions
def create_advanced_signal_engine() -> AdvancedTradingSignalEngine:
    """Factory function to create signal engine"""
    return AdvancedTradingSignalEngine()

if __name__ == "__main__":
    print("🎯 Advanced Trading Signal Engine Test\n")
    
    # Create engine
    engine = create_advanced_signal_engine()
    
    # Simulate candle data
    candles = [
        {'open': 1.1050, 'high': 1.1070, 'low': 1.1040, 'close': 1.1065, 'volume': 1000},
        {'open': 1.1065, 'high': 1.1080, 'low': 1.1060, 'close': 1.1075, 'volume': 1200},
        {'open': 1.1075, 'high': 1.1090, 'low': 1.1070, 'close': 1.1085, 'volume': 1100},
        {'open': 1.1085, 'high': 1.1200, 'low': 1.1080, 'close': 1.1150, 'volume': 3000},  # Volume spike
        {'open': 1.1150, 'high': 1.1160, 'low': 1.1140, 'close': 1.1155, 'volume': 900},
    ]
    
    print("📊 Adding candle data...")
    for i, candle in enumerate(candles):
        engine.add_candle_data(candle)
        print(f"   Candle {i+1}: {candle}")
    
    # Generate advanced signal
    print("\n🤖 Generating advanced signal...")
    indicators = {
        'rsi_extreme': True,
        'macd_divergence': False,
        'bb_breakout': True,
        'momentum_aligned': True,
        'volume_confirmed': True
    }
    
    result = engine.generate_advanced_signal(
        symbol='EURUSD',
        base_signal='BUY',
        base_confidence=0.78,
        indicators=indicators
    )
    
    print(f"\n📈 Signal Result:")
    for key, value in result.items():
        if key != 'confirmation_summary':
            print(f"   {key}: {value}")
    
    print(f"\n📋 Confirmation Details:")
    conf = result['confirmation_summary']
    for key, value in conf.items():
        print(f"   {key}: {value}")
    
    print(f"\n🎯 Engine Status:")
    status = engine.get_engine_status()
    print(f"   Active Signals: {status['active_signals']}")
    print(f"   Total Signals: {status['total_signals_generated']}")
    print(f"   Anomalies Detected: {status['anomaly_summary']['recent_count']}")
    print(f"   Divergences: {len(status['divergences'])}")
