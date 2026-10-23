"""
SENTIENX Data Processing Framework
Implementation of unified data processing for models and agents
"""

import numpy as np
import pandas as pd
from . import DataProcessor

class ForexProcessor(DataProcessor):
    """
    Data processor specifically designed for forex data
    
    Handles OHLCV data with technical indicators and preprocessing
    for forex trading models
    """
    
    def __init__(self, tickers, features, lookBack, forecast, interval="1d"):
        super().__init__(tickers, features, lookBack, forecast, interval)
        self.technical_indicators = {}
        self._loadForexData()
        self._calculateTechnicalIndicators()
    
    def _loadForexData(self):
        """Load forex data from database or files"""
        try:
            import sqlite3
            conn = sqlite3.connect('sentienx_trading.db')
            
            for ticker in self.tickers:
                query = """
                SELECT timestamp, open_price, high_price, low_price, close_price, volume
                FROM market_data 
                WHERE timestamp >= datetime('now', '-{} days')
                ORDER BY timestamp DESC
                LIMIT 1000
                """.format(self.lookBack + self.forecast)
                
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    self.tickerData[ticker] = df
            conn.close()
            
        except Exception as e:
            print(f"Warning: Could not load forex data: {e}")
            # Generate sample data for testing
            for ticker in self.tickers:
                dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq='D')
                np.random.seed(42)
                prices = np.cumsum(np.random.randn(100) * 0.01) + 1.1500
                
                df = pd.DataFrame({
                    'open': prices + np.random.randn(100) * 0.001,
                    'high': prices + np.abs(np.random.randn(100) * 0.002),
                    'low': prices - np.abs(np.random.randn(100) * 0.002),
                    'close': prices,
                    'volume': np.random.randint(1000, 10000, 100)
                }, index=dates)
                
                self.tickerData[ticker] = df
    
    def _calculateTechnicalIndicators(self):
        """Calculate technical indicators for all tickers"""
        for ticker, data in self.tickerData.items():
            df = data.copy()
            
            # Moving averages
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            ema_12 = df['close'].ewm(span=12).mean()
            ema_26 = df['close'].ewm(span=26).mean()
            df['macd'] = ema_12 - ema_26
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            # Price changes
            df['price_change'] = df['close'].pct_change()
            df['volatility'] = df['price_change'].rolling(window=20).std()
            
            # Store technical indicators
            self.technical_indicators[ticker] = df
    
    def inputProcessor(self, data, context):
        """
        Process forex data for model input
        
        Parameters
        ----------
        data : dict or pd.DataFrame
            Raw forex data
        context : dict
            Processing context
            
        Returns
        -------
        X : np.array
            Processed input features
        Y : np.array, optional
            Target values for training
        """
        if isinstance(data, dict):
            # Get data for specific ticker
            ticker = context.get('ticker', self.tickers[0])
            df = self.technical_indicators.get(ticker, data)
        else:
            df = data.copy()
        
        # Select features
        available_features = []
        for feature in self.features:
            if feature in df.columns:
                available_features.append(feature)
            elif feature.lower() in [col.lower() for col in df.columns]:
                # Case insensitive match
                col = next(col for col in df.columns if col.lower() == feature.lower())
                available_features.append(col)
        
        if not available_features:
            raise ValueError(f"None of the requested features {self.features} found in data")
        
        feature_df = df[available_features]
        
        # Handle missing values
        feature_df = feature_df.fillna(method='ffill').fillna(method='bfill')
        
        # Normalize features
        feature_columns = feature_df.select_dtypes(include=[np.number]).columns
        if len(feature_columns) > 0:
            feature_df[feature_columns] = (
                (feature_df[feature_columns] - feature_df[feature_columns].min()) /
                (feature_df[feature_columns].max() - feature_df[feature_columns].min())
            )
        
        if context.get("isTrain", False):
            # For training, create sequences and targets
            if 'close' in feature_df.columns:
                target = feature_df['close'].values
                
                # Create sequences
                sequences = []
                targets = []
                
                for i in range(len(feature_df) - self.lookBack - self.forecast):
                    seq = feature_df.iloc[i:i+self.lookBack][feature_columns].values
                    tgt = target[i+self.lookBack:i+self.lookBack+self.forecast]
                    sequences.append(seq)
                    targets.append(tgt)
                
                X = np.array(sequences)
                Y = np.array(targets)
                return X, Y
            else:
                return feature_df[feature_columns].values
        else:
            # For prediction/inference
            return feature_df[feature_columns].values
    
    def outputProcessor(self, modelOut, context):
        """
        Process model output for forex predictions
        
        Parameters
        ----------
        modelOut : np.array
            Raw model output
        context : dict
            Processing context
            
        Returns
        -------
        processed : np.array
            Processed predictions
        """
        if context.get("isTrain", False):
            # For training, return as-is
            return modelOut
        else:
            # For inference, ensure proper format
            if len(modelOut.shape) == 1:
                return modelOut.flatten()
            else:
                return modelOut
    
    def getTrainingData(self, validationSplit=0.7, shuffle=True, batchSize=64):
        """
        Prepare training data for forex models
        
        Parameters
        ----------
        validationSplit : float
            Training/validation split ratio
        shuffle : bool
            Whether to shuffle data
        batchSize : int
            Batch size for training
            
        Returns
        -------
        trainData : tuple
            Training data (X, Y)
        validData : tuple
            Validation data (X, Y)
        """
        all_X = []
        all_Y = []
        
        # Process each ticker
        for ticker in self.tickers:
            context = {"ticker": ticker, "isTrain": True}
            X, Y = self.inputProcessor(self.tickerData[ticker], context)
            
            if X is not None and Y is not None:
                all_X.append(X)
                all_Y.append(Y)
        
        if not all_X:
            raise ValueError("No valid training data generated")
        
        # Combine all ticker data
        X_combined = np.concatenate(all_X, axis=0)
        Y_combined = np.concatenate(all_Y, axis=0)
        
        # Split data
        indices = np.arange(len(X_combined))
        if shuffle:
            np.random.shuffle(indices)
        
        split_idx = int(len(X_combined) * validationSplit)
        
        train_indices = indices[:split_idx]
        valid_indices = indices[split_idx:]
        
        X_train = X_combined[train_indices]
        Y_train = Y_combined[train_indices]
        X_valid = X_combined[valid_indices]
        Y_valid = Y_combined[valid_indices]
        
        return (X_train, Y_train), (X_valid, Y_valid)

class MultiTimeframeProcessor(DataProcessor):
    """
    Data processor for multiple timeframe analysis
    """
    
    def __init__(self, tickers, features, lookBack, forecast, timeframes=["1d", "4h", "1h"]):
        super().__init__(tickers, features, lookBack, forecast, "1d")
        self.timeframes = timeframes
        self.multi_timeframe_data = {}
        self._loadMultiTimeframeData()
    
    def _loadMultiTimeframeData(self):
        """Load data for multiple timeframes"""
        for ticker in self.tickers:
            self.multi_timeframe_data[ticker] = {}
            for tf in self.timeframes:
                # Simulate different timeframe data
                base_data = self.tickerData.get(ticker)
                if base_data is not None:
                    if tf == "1d":
                        self.multi_timeframe_data[ticker][tf] = base_data
                    elif tf == "4h":
                        # Resample to 4-hour data
                        self.multi_timeframe_data[ticker][tf] = base_data.resample('4H').agg({
                            'open': 'first', 'high': 'max', 'low': 'min', 
                            'close': 'last', 'volume': 'sum'
                        })
                    elif tf == "1h":
                        # Resample to 1-hour data
                        self.multi_timeframe_data[ticker][tf] = base_data.resample('1H').agg({
                            'open': 'first', 'high': 'max', 'low': 'min', 
                            'close': 'last', 'volume': 'sum'
                        })
    
    def inputProcessor(self, data, context):
        """Process multi-timeframe data"""
        ticker = context.get('ticker', self.tickers[0])
        timeframe = context.get('timeframe', '1d')
        
        df = self.multi_timeframe_data.get(ticker, {}).get(timeframe)
        if df is None:
            raise ValueError(f"No data available for {ticker} on {timeframe}")
        
        # Select features and create sequences
        feature_df = df[self.features].fillna(method='ffill')
        
        if context.get("isTrain", False):
            # Create sequences for training
            sequences = []
            targets = []
            
            for i in range(len(feature_df) - self.lookBack):
                seq = feature_df.iloc[i:i+self.lookBack].values
                sequences.append(seq)
            
            return np.array(sequences)
        else:
            # For prediction, return latest sequence
            if len(feature_df) >= self.lookBack:
                return feature_df.iloc[-self.lookBack:].values
            else:
                return feature_df.values
    
    def outputProcessor(self, modelOut, context):
        """Process multi-timeframe model output"""
        return modelOut

class ReinforcementProcessor(DataProcessor):
    """
    Data processor for reinforcement learning agents
    """
    
    def __init__(self, tickers, features, lookBack, interval="1d"):
        super().__init__(tickers, features, lookBack, 1, interval)
        self.price_history = []
        self.states = []
        self.actions = []
        self.rewards = []
    
    def inputProcessor(self, data, context):
        """Process data for RL agent state representation"""
        if isinstance(data, dict):
            ticker = context.get('ticker', self.tickers[0])
            df = self.tickerData.get(ticker, data)
        else:
            df = data
        
        # Create state representation for RL
        if 'close' in df.columns:
            price_changes = df['close'].pct_change().fillna(0)
            
            # Create state features
            state_features = []
            
            # Price position
            current_price = df['close'].iloc[-1] if len(df) > 0 else 0
            sma_20 = df['close'].rolling(20).mean().iloc[-1] if len(df) >= 20 else current_price
            price_position = (current_price - sma_20) / sma_20 if sma_20 != 0 else 0
            
            # Volatility
            volatility = df['close'].pct_change().rolling(20).std().iloc[-1] if len(df) >= 20 else 0
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)) if not (gain == 0 and loss == 0) else 50
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
            
            # Portfolio state
            holdings = len(getattr(self, 'orderBook', []))
            cash = getattr(self, 'money', 10000)
            
            state_features.extend([
                price_position,      # Price relative to SMA
                volatility,          # Recent volatility
                current_rsi,         # RSI indicator
                holdings / 10,     # Normalized holdings
                cash / 10000        # Normalized cash
            ])
            
            return np.array(state_features)
        
        return np.array([0, 0, 0, 0, 0, 0])  # Default state
    
    def outputProcessor(self, modelOut, context):
        """Process RL agent output to action"""
        return np.argmax(modelOut) if len(modelOut.shape) > 1 else modelOut
    
    def addExperience(self, state, action, reward, next_state):
        """Add experience to replay buffer"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
    
    def getReplayBuffer(self):
        """Get replay buffer for training"""
        return list(zip(self.states, self.actions, self.rewards))