"""
Breakout Identification and Prediction Module
Detects current breakouts and forecasts next potential breakout levels
Uses support/resistance, volatility, and momentum analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

@dataclass
class BreakoutLevel:
    """Represents a potential breakout level"""
    level: float
    type: str  # 'RESISTANCE' or 'SUPPORT'
    strength: float  # 0-100, how strong the level is
    touches: int  # How many times price touched this level
    confidence: float  # Forecast confidence 0-100
    time_to_breakout: Optional[int]  # Estimated candles until breakout
    direction: str  # 'UP' or 'DOWN'

@dataclass
class BreakoutPrediction:
    """Complete breakout prediction"""
    symbol: str
    current_price: float
    prediction_time: datetime
    upside_breakout: Optional[BreakoutLevel]
    downside_breakout: Optional[BreakoutLevel]
    next_resistance: float
    next_support: float
    volatility_score: float  # 0-100
    momentum_direction: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    probability_of_breakout: float  # 0-100 next 24h
    recommended_entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float

class BreakoutAnalyzer:
    """Analyzes and predicts market breakouts"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Path(__file__).parent / "sentienx_trading.db"
    
    def identify_support_resistance(self, data: pd.DataFrame, lookback: int = 50) -> Tuple[List[float], List[float]]:
        """
        Identify support and resistance levels using local extrema
        
        Args:
            data: OHLCV dataframe
            lookback: Number of candles to analyze
            
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        if len(data) < lookback:
            return [], []
        
        recent = data.tail(lookback).copy()
        
        # Find local highs and lows
        resistance_levels = []
        support_levels = []
        
        highs = recent['high'].values
        lows = recent['low'].values
        
        # Identify local extrema
        for i in range(1, len(highs) - 1):
            # Resistance: local high
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                resistance_levels.append(highs[i])
            
            # Support: local low
            if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                support_levels.append(lows[i])
        
        # Cluster similar levels (within 0.5%)
        resistance_levels = self._cluster_levels(resistance_levels)
        support_levels = self._cluster_levels(support_levels)
        
        # Sort
        resistance_levels = sorted(resistance_levels, reverse=True)
        support_levels = sorted(support_levels)
        
        return support_levels, resistance_levels
    
    def _cluster_levels(self, levels: List[float], threshold: float = 0.005) -> List[float]:
        """Cluster similar price levels"""
        if not levels:
            return []
        
        clustered = []
        levels = sorted(levels)
        
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            # Check if within threshold
            if abs(level - current_cluster[-1]) / current_cluster[-1] < threshold:
                current_cluster.append(level)
            else:
                # Save cluster average
                clustered.append(np.mean(current_cluster))
                current_cluster = [level]
        
        if current_cluster:
            clustered.append(np.mean(current_cluster))
        
        return clustered
    
    def calculate_volatility(self, data: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate volatility score (0-100)
        Higher = more volatile
        """
        if len(data) < period:
            return 50.0
        
        returns = data['close'].pct_change()
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized
        
        # Normalize to 0-100
        vol_score = min(100, max(0, volatility * 2))
        return vol_score
    
    def calculate_momentum(self, data: pd.DataFrame) -> Tuple[float, str]:
        """
        Calculate momentum and direction
        
        Returns:
            Tuple of (momentum_value, direction)
        """
        if len(data) < 14:
            return 50.0, 'NEUTRAL'
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        # MACD
        ema_12 = data['close'].ewm(span=12).mean()
        ema_26 = data['close'].ewm(span=26).mean()
        macd = ema_12 - ema_26
        current_macd = macd.iloc[-1]
        
        # Determine direction
        if current_rsi > 60 and current_macd > 0:
            direction = 'BULLISH'
            momentum = 70.0
        elif current_rsi < 40 and current_macd < 0:
            direction = 'BEARISH'
            momentum = 30.0
        else:
            direction = 'NEUTRAL'
            momentum = 50.0
        
        return momentum, direction
    
    def predict_next_breakout(self, symbol: str, data: pd.DataFrame) -> BreakoutPrediction:
        """
        Predict next potential breakout levels and direction
        
        Args:
            symbol: Trading pair symbol
            data: OHLCV dataframe
            
        Returns:
            BreakoutPrediction object
        """
        current_price = data['close'].iloc[-1]
        current_time = datetime.now()
        
        # Identify key levels
        support_levels, resistance_levels = self.identify_support_resistance(data)
        
        # Calculate metrics
        volatility = self.calculate_volatility(data)
        momentum_val, momentum_dir = self.calculate_momentum(data)
        
        # Find next key levels
        next_resistance = self._find_next_level(current_price, resistance_levels, direction='UP')
        next_support = self._find_next_level(current_price, support_levels, direction='DOWN')
        
        # Forecast breakout levels
        upside_breakout = self._forecast_breakout(
            current_price, next_resistance, volatility, momentum_dir, direction='UP'
        )
        downside_breakout = self._forecast_breakout(
            current_price, next_support, volatility, momentum_dir, direction='DOWN'
        )
        
        # Calculate probability
        probability = self._calculate_breakout_probability(volatility, momentum_val)
        
        # Calculate entry and targets
        entry, sl, tp1, tp2 = self._calculate_levels(
            current_price, upside_breakout, downside_breakout, momentum_dir
        )
        
        return BreakoutPrediction(
            symbol=symbol,
            current_price=current_price,
            prediction_time=current_time,
            upside_breakout=upside_breakout,
            downside_breakout=downside_breakout,
            next_resistance=next_resistance or current_price * 1.05,
            next_support=next_support or current_price * 0.95,
            volatility_score=volatility,
            momentum_direction=momentum_dir,
            probability_of_breakout=probability,
            recommended_entry=entry,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2
        )
    
    def _find_next_level(self, current: float, levels: List[float], direction: str) -> Optional[float]:
        """Find the next level in given direction"""
        if not levels:
            return None
        
        if direction == 'UP':
            candidates = [l for l in levels if l > current]
            return min(candidates) if candidates else None
        else:  # DOWN
            candidates = [l for l in levels if l < current]
            return max(candidates) if candidates else None
    
    def _forecast_breakout(self, current: float, level: Optional[float], 
                          volatility: float, momentum: str, direction: str) -> BreakoutLevel:
        """Forecast a potential breakout"""
        if level is None:
            level = current * (1.10 if direction == 'UP' else 0.90)
        
        # Calculate strength based on level distance
        distance = abs(level - current) / current
        strength = min(100, 50 + (distance * 500))  # More distance = stronger signal
        
        # Adjust strength by momentum
        if momentum == 'BULLISH' and direction == 'UP':
            strength = min(100, strength * 1.2)
        elif momentum == 'BEARISH' and direction == 'DOWN':
            strength = min(100, strength * 1.2)
        
        # Estimate time to breakout
        time_to_breakout = max(1, int(100 / (volatility + 10)))
        
        # Convert momentum to numerical value
        momentum_value = 70.0 if momentum == 'BULLISH' else 30.0 if momentum == 'BEARISH' else 50.0
        
        # Confidence based on momentum and volatility
        confidence = 50 + (momentum_value - 50) * 0.3 + (volatility / 100) * 20
        confidence = min(100, max(0, confidence))
        
        return BreakoutLevel(
            level=level,
            type='RESISTANCE' if direction == 'UP' else 'SUPPORT',
            strength=strength,
            touches=1,
            confidence=confidence,
            time_to_breakout=time_to_breakout,
            direction=direction
        )
    
    def _calculate_breakout_probability(self, volatility: float, momentum: float) -> float:
        """Calculate probability of breakout in next 24 hours"""
        # Higher volatility = higher chance of breakout
        # Higher momentum = higher chance of breakout
        prob = 30 + (volatility * 0.3) + (abs(momentum - 50) * 0.4)
        return min(100, max(0, prob))
    
    def _calculate_levels(self, current: float, upside: BreakoutLevel, 
                         downside: BreakoutLevel, momentum: str) -> Tuple[float, float, float, float]:
        """Calculate entry, stop loss, and take profit levels"""
        
        if momentum == 'BULLISH':
            # Long setup
            entry = current
            stop_loss = downside.level * 0.98
            take_profit_1 = upside.level * 1.02
            take_profit_2 = upside.level * 1.05
        else:
            # Short setup
            entry = current
            stop_loss = upside.level * 1.02
            take_profit_1 = downside.level * 0.98
            take_profit_2 = downside.level * 0.95
        
        return entry, stop_loss, take_profit_1, take_profit_2
    
    def detect_active_breakout(self, data: pd.DataFrame, lookback: int = 5) -> Dict:
        """
        Detect if a breakout is currently happening
        
        Returns:
            Dict with breakout details or empty if none detected
        """
        if len(data) < lookback + 10:
            return {}
        
        recent = data.tail(lookback)
        earlier = data.tail(lookback + 10).head(10)
        
        current_price = data['close'].iloc[-1]
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        earlier_high = earlier['high'].max()
        earlier_low = earlier['low'].min()
        
        # Upside breakout
        if recent_high > earlier_high * 1.02:
            return {
                'type': 'UPSIDE_BREAKOUT',
                'breakout_level': earlier_high,
                'current_price': current_price,
                'distance': (current_price - earlier_high) / earlier_high * 100,
                'strength': min(100, (recent_high - earlier_high) / earlier_high * 500)
            }
        
        # Downside breakout
        if recent_low < earlier_low * 0.98:
            return {
                'type': 'DOWNSIDE_BREAKOUT',
                'breakout_level': earlier_low,
                'current_price': current_price,
                'distance': (earlier_low - current_price) / earlier_low * 100,
                'strength': min(100, (earlier_low - recent_low) / earlier_low * 500)
            }
        
        return {}

def get_breakout_analysis(symbol: str, data: pd.DataFrame = None) -> Dict:
    """Convenience function to get breakout analysis"""
    analyzer = BreakoutAnalyzer()
    
    if data is None:
        # Load from database
        try:
            conn = sqlite3.connect(str(analyzer.db_path))
            query = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM trading_history
                WHERE symbol = ? AND status = 'closed'
                ORDER BY timestamp DESC
                LIMIT 100
            """
            df = pd.read_sql_query(query, conn, params=(symbol,))
            conn.close()
            data = df.iloc[::-1].reset_index(drop=True)
        except:
            return {'error': 'Could not load data'}
    
    # Get prediction
    prediction = analyzer.predict_next_breakout(symbol, data)
    
    # Detect active breakout
    active_breakout = analyzer.detect_active_breakout(data)
    
    return {
        'symbol': symbol,
        'prediction': prediction,
        'active_breakout': active_breakout,
        'next_resistance': prediction.next_resistance,
        'next_support': prediction.next_support,
        'upside_target': prediction.upside_breakout.level if prediction.upside_breakout else None,
        'downside_target': prediction.downside_breakout.level if prediction.downside_breakout else None,
        'volatility': prediction.volatility_score,
        'momentum': prediction.momentum_direction,
        'breakout_probability': prediction.probability_of_breakout,
        'recommended_entry': prediction.recommended_entry,
        'stop_loss': prediction.stop_loss,
        'take_profit_1': prediction.take_profit_1,
        'take_profit_2': prediction.take_profit_2
    }
