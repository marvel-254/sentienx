"""
Advanced Trading Strategies for SENTIENX
Implements sophisticated technical analysis, ML-enhanced, and multi-asset strategies
"""

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from logger.log_writer import Logger
from ml_pipeline.neural_network import TradingNeuralNetwork
from common_types import Signal, StrategyResult, Position

class TradingStrategy:
    def __init__(self, name, logger=None):
        self.name = name
        self.logger = logger or Logger()

    def analyze(self, data):
        """Analyze market data and return trading signal"""
        raise NotImplementedError("Subclasses must implement analyze method")

    def calculate_indicators(self, data):
        """Calculate technical indicators needed for the strategy"""
        raise NotImplementedError("Subclasses must implement calculate_indicators method")

class TLS_Strategy(TradingStrategy):
    """Trend Line Strategy - Based on trend lines and momentum"""

    def __init__(self, logger=None, lookback_period=20, rsi_period=14, macd_fast=12, macd_slow=26, macd_signal=9):
        super().__init__("TLS_Strategy", logger)
        self.lookback_period = lookback_period
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.adx_period = 14  # ADX for trend strength
        self.atr_period = 14  # ATR for volatility
        self.stoch_period = 14  # Stochastic oscillator

    def calculate_indicators(self, data):
        """Calculate TLS strategy indicators"""
        df = data.copy()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        ema_fast = df['close'].ewm(span=self.macd_fast).mean()
        ema_slow = df['close'].ewm(span=self.macd_slow).mean()
        df['MACD'] = ema_fast - ema_slow
        df['MACD_signal'] = df['MACD'].ewm(span=self.macd_signal).mean()
        df['MACD_histogram'] = df['MACD'] - df['MACD_signal']

        # Moving Averages
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()

        # Bollinger Bands
        sma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        df['BB_upper'] = sma20 + (std20 * 2)
        df['BB_lower'] = sma20 - (std20 * 2)

        # Trend Direction (simplified)
        df['trend'] = np.where(df['SMA_20'] > df['SMA_50'], 1, -1)

        return df

    def analyze(self, data):
        """Generate trading signals based on TLS strategy"""
        if len(data) < 50:  # Need enough data for indicators
            return Signal.HOLD

        df = self.calculate_indicators(data)

        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        signal = Signal.HOLD

        # Trend following with momentum confirmation
        current_trend = latest['trend']

        # MACD crossover signals
        macd_cross_up = (prev['MACD'] < prev['MACD_signal']) and (latest['MACD'] > latest['MACD_signal'])
        macd_cross_down = (prev['MACD'] > prev['MACD_signal']) and (latest['MACD'] < latest['MACD_signal'])

        # RSI conditions
        rsi_oversold = latest['RSI'] < 30
        rsi_overbought = latest['RSI'] > 70

        # Bollinger Band conditions
        price_near_lower = latest['close'] < latest['BB_lower'] * 1.001
        price_near_upper = latest['close'] > latest['BB_upper'] * 0.999

        # Generate signals
        if current_trend > 0:  # Uptrend
            if macd_cross_up and rsi_oversold and price_near_lower:
                signal = Signal.BUY
        elif current_trend < 0:  # Downtrend
            if macd_cross_down and rsi_overbought and price_near_upper:
                signal = Signal.SELL

        # Additional confirmation: Price touching bands in trend direction
        if signal == Signal.BUY and price_near_lower:
            signal = Signal.BUY
        elif signal == Signal.SELL and price_near_upper:
            signal = Signal.SELL

        confidence = self._calculate_confidence(df)

        return {
            'signal': signal,
            'confidence': confidence,
            'indicators': {
                'trend': current_trend,
                'rsi': latest['RSI'],
                'macd': latest['MACD'],
                'macd_signal': latest['MACD_signal'],
                'bb_upper': latest['BB_upper'],
                'bb_lower': latest['BB_lower']
            }
        }

    def _calculate_confidence(self, df):
        """Calculate signal confidence based on indicator alignment"""
        latest = df.iloc[-1]

        confidence = 0.5  # Base confidence

        # Trend strength
        if abs(latest['SMA_20'] - latest['SMA_50']) > latest['close'] * 0.001:
            confidence += 0.1

        # RSI confirmation
        if (latest['RSI'] < 35) or (latest['RSI'] > 65):
            confidence += 0.1

        # MACD strength
        if abs(latest['MACD_histogram']) > abs(df['MACD_histogram'].tail(10).mean()):
            confidence += 0.1

        # Bollinger Band position
        bb_position = (latest['close'] - latest['BB_lower']) / (latest['BB_upper'] - latest['BB_lower'])
        if bb_position < 0.2 or bb_position > 0.8:
            confidence += 0.1

        return min(confidence, 0.95)  # Cap at 95%

class MovingAverageCrossover(TradingStrategy):
    """Simple Moving Average Crossover Strategy"""

    def __init__(self, fast_period=10, slow_period=20, logger=None):
        super().__init__("MA_Crossover", logger)
        self.fast_period = fast_period
        self.slow_period = slow_period

    def calculate_indicators(self, data):
        df = data.copy()
        df['MA_fast'] = df['close'].rolling(window=self.fast_period).mean()
        df['MA_slow'] = df['close'].rolling(window=self.slow_period).mean()
        return df

    def analyze(self, data):
        if len(data) < self.slow_period:
            return Signal.HOLD

        df = self.calculate_indicators(data)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Crossover signals
        if (prev['MA_fast'] < prev['MA_slow']) and (latest['MA_fast'] > latest['MA_slow']):
            return Signal.BUY
        elif (prev['MA_fast'] > prev['MA_slow']) and (latest['MA_fast'] < latest['MA_slow']):
            return Signal.SELL

        return Signal.HOLD

class RSI_Divergence(TradingStrategy):
    """RSI Divergence Strategy"""

    def __init__(self, rsi_period=14, logger=None):
        super().__init__("RSI_Divergence", logger)
        self.rsi_period = rsi_period

    def calculate_indicators(self, data):
        df = data.copy()

        # RSI calculation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        return df

    def analyze(self, data):
        if len(data) < self.rsi_period + 10:
            return Signal.HOLD

        df = self.calculate_indicators(data)

        # Look for divergence in last 10 periods
        recent_prices = df['close'].tail(10)
        recent_rsi = df['RSI'].tail(10)

        # Simple divergence detection (price making lower low, RSI making higher low)
        price_trend = recent_prices.iloc[-1] < recent_prices.iloc[0]
        rsi_trend = recent_rsi.iloc[-1] > recent_rsi.iloc[0]

        if price_trend and rsi_trend and recent_rsi.iloc[-1] < 35:
            return Signal.BUY
        elif not price_trend and not rsi_trend and recent_rsi.iloc[-1] > 65:
            return Signal.SELL

        return Signal.HOLD

class MeanReversionStrategy(TradingStrategy):
    """Mean Reversion Strategy - Trades against extreme price movements"""

    def __init__(self, lookback=20, entry_threshold=2.0, exit_threshold=0.5, logger=None):
        super().__init__("Mean_Reversion", logger)
        self.lookback = lookback
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def calculate_indicators(self, data):
        df = data.copy()
        # Z-score for mean reversion
        df['mean'] = df['close'].rolling(window=self.lookback).mean()
        df['std'] = df['close'].rolling(window=self.lookback).std()
        df['z_score'] = (df['close'] - df['mean']) / df['std']

        # Bollinger Bands
        df['BB_upper'] = df['mean'] + (df['std'] * 2)
        df['BB_lower'] = df['mean'] - (df['std'] * 2)

        return df

    def analyze(self, data):
        if len(data) < self.lookback:
            return Signal.HOLD

        df = self.calculate_indicators(data)
        latest = df.iloc[-1]

        z_score = latest['z_score']

        # Entry signals
        if z_score < -self.entry_threshold:  # Price significantly below mean
            return StrategyResult(
                signal=Signal.BUY,
                confidence=min(abs(z_score) / 3.0, 0.95),
                strength=abs(z_score),
                indicators={'z_score': z_score, 'mean': latest['mean'], 'std': latest['std']},
                metadata={'strategy': 'mean_reversion', 'entry_threshold': self.entry_threshold},
                timestamp=pd.Timestamp.now()
            )
        elif z_score > self.entry_threshold:  # Price significantly above mean
            return StrategyResult(
                signal=Signal.SELL,
                confidence=min(abs(z_score) / 3.0, 0.95),
                strength=abs(z_score),
                indicators={'z_score': z_score, 'mean': latest['mean'], 'std': latest['std']},
                metadata={'strategy': 'mean_reversion', 'entry_threshold': self.entry_threshold},
                timestamp=pd.Timestamp.now()
            )

        return StrategyResult(
            signal=Signal.HOLD,
            confidence=0.5,
            strength=abs(z_score),
            indicators={'z_score': z_score},
            metadata={'strategy': 'mean_reversion'},
            timestamp=pd.Timestamp.now()
        )

class BreakoutStrategy(TradingStrategy):
    """Breakout Strategy - Trades on price breaking support/resistance levels"""

    def __init__(self, lookback=20, breakout_threshold=0.001, consolidation_period=10, logger=None):
        super().__init__("Breakout", logger)
        self.lookback = lookback
        self.breakout_threshold = breakout_threshold
        self.consolidation_period = consolidation_period

    def calculate_indicators(self, data):
        df = data.copy()

        # Support and resistance levels
        df['support'] = df['low'].rolling(window=self.lookback).min()
        df['resistance'] = df['high'].rolling(window=self.lookback).max()

        # Average True Range for volatility
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()

        # Consolidation detection (low volatility)
        df['volatility'] = df['ATR'] / df['close']
        df['is_consolidating'] = df['volatility'] < df['volatility'].rolling(window=self.consolidation_period).mean()

        return df

    def analyze(self, data):
        if len(data) < self.lookback:
            return Signal.HOLD

        df = self.calculate_indicators(data)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Check for breakouts
        breakout_up = (latest['close'] > latest['resistance'] * (1 + self.breakout_threshold) and
                      latest['is_consolidating'] and prev['close'] <= prev['resistance'])

        breakout_down = (latest['close'] < latest['support'] * (1 - self.breakout_threshold) and
                        latest['is_consolidating'] and prev['close'] >= prev['support'])

        if breakout_up:
            return StrategyResult(
                signal=Signal.BUY,
                confidence=0.8,
                strength=(latest['close'] - latest['resistance']) / latest['ATR'],
                indicators={'support': latest['support'], 'resistance': latest['resistance'], 'ATR': latest['ATR']},
                metadata={'strategy': 'breakout', 'direction': 'up'},
                timestamp=pd.Timestamp.now()
            )
        elif breakout_down:
            return StrategyResult(
                signal=Signal.SELL,
                confidence=0.8,
                strength=(latest['support'] - latest['close']) / latest['ATR'],
                indicators={'support': latest['support'], 'resistance': latest['resistance'], 'ATR': latest['ATR']},
                metadata={'strategy': 'breakout', 'direction': 'down'},
                timestamp=pd.Timestamp.now()
            )

        return StrategyResult(
            signal=Signal.HOLD,
            confidence=0.5,
            strength=0.0,
            indicators={'support': latest['support'], 'resistance': latest['resistance']},
            metadata={'strategy': 'breakout'},
            timestamp=pd.Timestamp.now()
        )

class ML_Enhanced_Strategy(TradingStrategy):
    """Machine Learning Enhanced Strategy combining technical analysis with neural network predictions"""

    def __init__(self, logger=None, model_path='models/sentienx_model.json'):
        super().__init__("ML_Enhanced", logger)
        self.model_path = model_path
        self.ml_model = None
        self.technical_indicators = []

        # Initialize ML model
        try:
            self.ml_model = TradingNeuralNetwork.load_model(model_path)
        except:
            # Create default model if none exists
            self.ml_model = TradingNeuralNetwork(
                input_dim=50,  # Will be adjusted based on features
                hidden_layers=[64, 32, 16],
                output_dim=3,  # BUY, HOLD, SELL
                learning_rate=0.001
            )

    def calculate_indicators(self, data):
        df = data.copy()

        # Comprehensive technical indicators
        df['SMA_5'] = df['close'].rolling(window=5).mean()
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_signal'] = df['MACD'].ewm(span=9).mean()

        # Bollinger Bands
        sma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        df['BB_upper'] = sma20 + (std20 * 2)
        df['BB_lower'] = sma20 - (std20 * 2)

        # Stochastic
        low_min = df['low'].rolling(window=14).min()
        high_max = df['high'].rolling(window=14).max()
        df['%K'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
        df['%D'] = df['%K'].rolling(window=3).mean()

        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()

        self.technical_indicators = [col for col in df.columns if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]

        return df

    def prepare_ml_features(self, data, lookback=60):
        """Prepare features for ML model"""
        df = self.calculate_indicators(data)

        if len(df) < lookback:
            return None

        # Get latest sequence
        latest_data = df[self.technical_indicators].iloc[-lookback:].values

        # Normalize
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        normalized_features = scaler.fit_transform(latest_data)

        return normalized_features.flatten()

    def analyze(self, data):
        if len(data) < 60:  # Need enough data for indicators
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=0.5,
                strength=0.0,
                indicators={},
                metadata={'strategy': 'ml_enhanced', 'reason': 'insufficient_data'},
                timestamp=pd.Timestamp.now()
            )

        # Get technical analysis signal
        technical_result = self._technical_analysis(data)

        # Get ML prediction
        ml_features = self.prepare_ml_features(data)
        if ml_features is not None and self.ml_model.is_trained:
            ml_prediction = self.ml_model.predict(ml_features.reshape(1, -1))[0]
            ml_probabilities = self.ml_model.predict_proba(ml_features.reshape(1, -1))[0]

            # Combine signals
            combined_signal = self._combine_signals(technical_result, ml_prediction, ml_probabilities)
        else:
            combined_signal = technical_result

        return combined_signal

    def _technical_analysis(self, data):
        """Traditional technical analysis"""
        df = self.calculate_indicators(data)
        latest = df.iloc[-1]

        # Multi-factor signal generation
        signals = []

        # Trend signals
        if latest['SMA_5'] > latest['SMA_10'] > latest['SMA_20']:
            signals.append(('trend', Signal.BUY, 0.6))
        elif latest['SMA_5'] < latest['SMA_10'] < latest['SMA_20']:
            signals.append(('trend', Signal.SELL, 0.6))

        # RSI signals
        if latest['RSI'] < 30:
            signals.append(('rsi', Signal.BUY, 0.7))
        elif latest['RSI'] > 70:
            signals.append(('rsi', Signal.SELL, 0.7))

        # MACD signals
        if latest['MACD'] > latest['MACD_signal']:
            signals.append(('macd', Signal.BUY, 0.5))
        elif latest['MACD'] < latest['MACD_signal']:
            signals.append(('macd', Signal.SELL, 0.5))

        # Bollinger Band signals
        if latest['close'] < latest['BB_lower']:
            signals.append(('bb', Signal.BUY, 0.8))
        elif latest['close'] > latest['BB_upper']:
            signals.append(('bb', Signal.SELL, 0.8))

        # Consensus signal
        buy_signals = sum(1 for _, sig, _ in signals if sig == Signal.BUY)
        sell_signals = sum(1 for _, sig, _ in signals if sig == Signal.SELL)
        total_signals = len(signals)

        if buy_signals > sell_signals:
            signal = Signal.BUY
            confidence = min(buy_signals / total_signals, 0.9)
        elif sell_signals > buy_signals:
            signal = Signal.SELL
            confidence = min(sell_signals / total_signals, 0.9)
        else:
            signal = Signal.HOLD
            confidence = 0.5

        return StrategyResult(
            signal=signal,
            confidence=confidence,
            strength=max((buy_signals - sell_signals) / total_signals, 0),
            indicators={k: v for k, _, _ in signals},
            metadata={'strategy': 'technical', 'signal_components': signals},
            timestamp=pd.Timestamp.now()
        )

    def _combine_signals(self, technical_result, ml_prediction, ml_probabilities):
        """Combine technical and ML signals"""
        # ML prediction mapping: 0=SELL, 1=HOLD, 2=BUY
        ml_signal_map = {0: Signal.SELL, 1: Signal.HOLD, 2: Signal.BUY}
        ml_signal = ml_signal_map.get(ml_prediction, Signal.HOLD)
        ml_confidence = max(ml_probabilities)

        # Weighted combination
        technical_weight = 0.6
        ml_weight = 0.4

        combined_confidence = (technical_result.confidence * technical_weight +
                             ml_confidence * ml_weight)

        # Signal consensus
        if technical_result.signal == ml_signal:
            final_signal = technical_result.signal
            final_confidence = combined_confidence
        elif technical_result.confidence > 0.7:
            final_signal = technical_result.signal
            final_confidence = technical_result.confidence * 0.8
        elif ml_confidence > 0.7:
            final_signal = ml_signal
            final_confidence = ml_confidence * 0.8
        else:
            final_signal = Signal.HOLD
            final_confidence = 0.5

        return StrategyResult(
            signal=final_signal,
            confidence=final_confidence,
            strength=(technical_result.strength + ml_confidence) / 2,
            indicators={**technical_result.indicators, 'ml_prediction': ml_prediction},
            metadata={
                'strategy': 'ml_enhanced',
                'technical_signal': technical_result.signal,
                'ml_signal': ml_signal,
                'ml_probabilities': ml_probabilities.tolist()
            },
            timestamp=pd.Timestamp.now()
        )

class StrategyManager:
    """Advanced strategy manager with portfolio optimization and risk management"""

    def __init__(self, logger=None, risk_manager=None):
        self.logger = logger or Logger()
        self.strategies = {
            'tls': TLS_Strategy(logger),
            'ma_crossover': MovingAverageCrossover(logger),
            'rsi_divergence': RSI_Divergence(logger),
            'mean_reversion': MeanReversionStrategy(logger=logger),
            'breakout': BreakoutStrategy(logger=logger),
            'ml_enhanced': ML_Enhanced_Strategy(logger=logger)
        }
        self.active_strategy = 'ml_enhanced'  # Default to most advanced
        self.portfolio = {}
        self.risk_manager = risk_manager or RiskManager(logger=logger)
        self.performance_history = []

    def set_active_strategy(self, strategy_name):
        """Set the active trading strategy"""
        if strategy_name in self.strategies:
            self.active_strategy = strategy_name
            self.logger.log_message('INFO', 'STRATEGY_MANAGER', f'Active strategy set to: {strategy_name}')
            return True
        else:
            self.logger.log_message('ERROR', 'STRATEGY_MANAGER', f'Unknown strategy: {strategy_name}')
            return False

    def analyze_all_strategies(self, data):
        """Analyze market data with all strategies"""
        results = {}

        for name, strategy in self.strategies.items():
            try:
                result = strategy.analyze(data)
                # Handle both old Signal format and new StrategyResult format
                if isinstance(result, StrategyResult):
                    results[name] = result
                else:
                    # Convert old format to new
                    results[name] = StrategyResult(
                        signal=result,
                        confidence=0.5,
                        strength=0.5,
                        indicators={},
                        metadata={'strategy': name},
                        timestamp=pd.Timestamp.now()
                    )
            except Exception as e:
                self.logger.log_message('ERROR', 'STRATEGY_MANAGER', f'Error in strategy {name}: {str(e)}')
                results[name] = StrategyResult(
                    signal=Signal.HOLD,
                    confidence=0.5,
                    strength=0.0,
                    indicators={},
                    metadata={'strategy': name, 'error': str(e)},
                    timestamp=pd.Timestamp.now()
                )

        return results

    def get_strategy_signal(self, strategy_name, data):
        """Get signal from specific strategy"""
        if strategy_name not in self.strategies:
            return Signal.HOLD

        try:
            return self.strategies[strategy_name].analyze(data)
        except Exception as e:
            self.logger.log_message('ERROR', 'STRATEGY_MANAGER', f'Error in strategy {strategy_name}: {str(e)}')
            return Signal.HOLD

    def get_consensus_signal(self, data):
        """Get consensus signal from all strategies with confidence weighting"""
        results = self.analyze_all_strategies(data)

        buy_weight = 0
        sell_weight = 0
        hold_weight = 0

        for result in results.values():
            if isinstance(result, StrategyResult):
                weight = result.confidence * result.strength
                if result.signal == Signal.BUY:
                    buy_weight += weight
                elif result.signal == Signal.SELL:
                    sell_weight += weight
                else:
                    hold_weight += weight
            else:
                # Handle old format
                if result == Signal.BUY:
                    buy_weight += 0.5
                elif result == Signal.SELL:
                    sell_weight += 0.5
                else:
                    hold_weight += 0.5

        total_weight = buy_weight + sell_weight + hold_weight

        if total_weight == 0:
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=0.5,
                strength=0.0,
                indicators={},
                metadata={'strategy': 'consensus', 'method': 'weighted'},
                timestamp=pd.Timestamp.now()
            )

        # Normalize weights
        buy_pct = buy_weight / total_weight
        sell_pct = sell_weight / total_weight
        hold_pct = hold_weight / total_weight

        # Determine consensus
        if buy_pct > max(sell_pct, hold_pct):
            return StrategyResult(
                signal=Signal.BUY,
                confidence=buy_pct,
                strength=buy_pct - max(sell_pct, hold_pct),
                indicators={'buy_weight': buy_pct, 'sell_weight': sell_pct, 'hold_weight': hold_pct},
                metadata={'strategy': 'consensus', 'method': 'weighted', 'total_strategies': len(results)},
                timestamp=pd.Timestamp.now()
            )
        elif sell_pct > max(buy_pct, hold_pct):
            return StrategyResult(
                signal=Signal.SELL,
                confidence=sell_pct,
                strength=sell_pct - max(buy_pct, hold_pct),
                indicators={'buy_weight': buy_pct, 'sell_weight': sell_pct, 'hold_weight': hold_pct},
                metadata={'strategy': 'consensus', 'method': 'weighted', 'total_strategies': len(results)},
                timestamp=pd.Timestamp.now()
            )
        else:
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=hold_pct,
                strength=0.0,
                indicators={'buy_weight': buy_pct, 'sell_weight': sell_pct, 'hold_weight': hold_pct},
                metadata={'strategy': 'consensus', 'method': 'weighted', 'total_strategies': len(results)},
                timestamp=pd.Timestamp.now()
            )

    def analyze_active_strategy(self, data):
        """Analyze using the active strategy"""
        if self.active_strategy not in self.strategies:
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=0.5,
                strength=0.0,
                indicators={},
                metadata={'strategy': 'none', 'error': 'invalid_active_strategy'},
                timestamp=pd.Timestamp.now()
            )

        result = self.strategies[self.active_strategy].analyze(data)

        # Apply risk management if available
        if self.risk_manager and isinstance(result, StrategyResult):
            result = self.risk_manager.adjust_signal(result, self.portfolio)

        return result

    def optimize_strategy_parameters(self, strategy_name, historical_data, parameter_ranges):
        """Optimize strategy parameters using grid search"""
        if strategy_name not in self.strategies:
            return None

        best_params = None
        best_performance = -float('inf')

        # Simple grid search (can be enhanced with more sophisticated optimization)
        from itertools import product

        param_combinations = list(product(*parameter_ranges.values()))

        for params in param_combinations:
            param_dict = dict(zip(parameter_ranges.keys(), params))

            # Create strategy with these parameters
            if strategy_name == 'ma_crossover':
                strategy = MovingAverageCrossover(fast_period=param_dict['fast'], slow_period=param_dict['slow'])
            elif strategy_name == 'mean_reversion':
                strategy = MeanReversionStrategy(lookback=param_dict['lookback'], entry_threshold=param_dict['threshold'])
            else:
                continue

            # Evaluate performance on historical data
            performance = self._evaluate_strategy_performance(strategy, historical_data)

            if performance > best_performance:
                best_performance = performance
                best_params = param_dict

        return best_params, best_performance

    def _evaluate_strategy_performance(self, strategy, data, initial_capital=10000):
        """Evaluate strategy performance on historical data"""
        capital = initial_capital
        position = 0
        trades = []

        for i in range(50, len(data)):  # Start after indicator warm-up
            window_data = data.iloc[:i+1]
            signal = strategy.analyze(window_data)

            if isinstance(signal, StrategyResult):
                signal_val = signal.signal
            else:
                signal_val = signal

            current_price = data.iloc[i]['close']

            # Execute trades
            if signal_val == Signal.BUY and position == 0:
                position = capital / current_price
                capital = 0
                trades.append({'type': 'BUY', 'price': current_price, 'timestamp': data.iloc[i]['timestamp']})
            elif signal_val == Signal.SELL and position > 0:
                capital = position * current_price
                position = 0
                trades.append({'type': 'SELL', 'price': current_price, 'timestamp': data.iloc[i]['timestamp']})

        # Calculate final portfolio value
        final_value = capital + (position * data.iloc[-1]['close'])
        return_pct = (final_value - initial_capital) / initial_capital * 100

        return return_pct

    def get_portfolio_allocation(self, signals, total_capital=10000):
        """Calculate portfolio allocation based on strategy signals"""
        allocations = {}

        # Group signals by symbol
        symbol_signals = {}
        for symbol, signal in signals.items():
            if isinstance(signal, StrategyResult) and signal.signal != Signal.HOLD:
                symbol_signals[symbol] = signal

        if not symbol_signals:
            return allocations

        # Equal weight allocation for signals
        capital_per_signal = total_capital / len(symbol_signals)

        for symbol, signal in symbol_signals.items():
            # Risk-adjusted position sizing
            confidence_multiplier = signal.confidence
            position_size = capital_per_signal * confidence_multiplier

            allocations[symbol] = {
                'signal': signal.signal,
                'allocation': position_size,
                'confidence': signal.confidence,
                'strength': signal.strength
            }

        return allocations

    def update_performance_history(self, results):
        """Update strategy performance tracking"""
        self.performance_history.append({
            'timestamp': pd.Timestamp.now(),
            'results': results,
            'portfolio_value': sum(self.portfolio.values()) if self.portfolio else 0
        })

        # Keep only last 1000 entries
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]

if __name__ == "__main__":
    # Test strategies
    import pandas as pd
    import numpy as np

    # Generate test data
    dates = pd.date_range('2024-01-01', periods=100, freq='H')
    prices = 1.0850 + np.cumsum(np.random.normal(0, 0.001, 100))
    data = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices + 0.0005,
        'low': prices - 0.0005,
        'close': prices,
        'volume': np.random.randint(1000, 10000, 100)
    })

    # Test TLS strategy
    tls = TLS_Strategy()
    signal = tls.analyze(data)
    print(f"TLS Strategy signal: {signal}")

    # Test strategy manager
    manager = StrategyManager()
    consensus = manager.get_consensus_signal(data)
    print(f"Consensus signal: {consensus}")