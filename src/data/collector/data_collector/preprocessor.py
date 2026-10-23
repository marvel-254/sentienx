import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from scipy import stats
from data_collector.price_data import PriceData
from logger.log_writer import Logger

class DataPreprocessor:
    def __init__(self):
        self.price_data = PriceData()
        self.logger = Logger()
        self.scalers = {
            'standard': StandardScaler(),
            'minmax': MinMaxScaler(),
            'robust': RobustScaler()
        }
        self.active_scaler = 'robust'  # Robust to outliers

    def validate_data_quality(self, data):
        """Validate data quality and log issues"""
        issues = []

        # Check for missing values
        missing_pct = data.isnull().sum() / len(data) * 100
        if missing_pct.any() > 5:
            issues.append(f"High missing data: {missing_pct[missing_pct > 5]}")

        # Check for price anomalies
        if 'close' in data.columns:
            # Check for negative prices
            if (data['close'] <= 0).any():
                issues.append("Negative or zero prices detected")

            # Check for unrealistic price changes (>50% in a day)
            pct_change = data['close'].pct_change().abs()
            if (pct_change > 0.5).any():
                issues.append("Extreme price changes detected (>50%)")

        # Check for volume anomalies
        if 'volume' in data.columns:
            if (data['volume'] <= 0).any():
                issues.append("Zero or negative volume detected")

        if issues:
            for issue in issues:
                self.logger.log_message('WARNING', 'DATA_PREPROCESSOR', issue)

        return len(issues) == 0

    def handle_missing_data(self, data, method='interpolate'):
        """Handle missing data with multiple strategies"""
        df = data.copy()

        if method == 'interpolate':
            # Linear interpolation for prices
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].interpolate(method='linear', limit_direction='both')
        elif method == 'forward_fill':
            df = df.fillna(method='ffill')
        elif method == 'mean':
            df = df.fillna(df.mean())

        # Drop rows still with NaN if any
        df = df.dropna()

        return df

    def detect_and_handle_outliers(self, data, method='iqr', threshold=1.5):
        """Detect and handle outliers"""
        df = data.copy()

        if method == 'iqr':
            # IQR method for outlier detection
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    Q1 = df[col].quantile(0.25)
                    Q3 = df[col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - threshold * IQR
                    upper_bound = Q3 + threshold * IQR

                    # Cap outliers
                    df[col] = np.clip(df[col], lower_bound, upper_bound)

        elif method == 'zscore':
            # Z-score method
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                z_scores = np.abs(stats.zscore(df[col]))
                df = df[z_scores < 3]  # Remove outliers beyond 3 std dev

        return df

    def add_advanced_indicators(self, data):
        """Add advanced technical indicators"""
        df = data.copy()

        # Williams %R
        highest_high = df['high'].rolling(window=14).max()
        lowest_low = df['low'].rolling(window=14).min()
        df['Williams_R'] = -100 * ((highest_high - df['close']) / (highest_high - lowest_low))

        # Commodity Channel Index (CCI)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(window=20).mean()
        mad_tp = typical_price.rolling(window=20).apply(lambda x: np.mean(np.abs(x - x.mean())))
        df['CCI'] = (typical_price - sma_tp) / (0.015 * mad_tp)

        # Average True Range (ATR)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()

        # On Balance Volume (OBV)
        df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

        # Chaikin Money Flow (CMF)
        money_flow_multiplier = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        money_flow_volume = money_flow_multiplier * df['volume']
        df['CMF'] = money_flow_volume.rolling(window=21).sum() / df['volume'].rolling(window=21).sum()

        return df

    def calculate_moving_averages(self, data, periods=[5, 10, 20, 50]):
        """Calculate moving averages"""
        df = data.copy()
        for period in periods:
            df[f'SMA_{period}'] = df['close'].rolling(window=period).mean()
            df[f'EMA_{period}'] = df['close'].ewm(span=period).mean()
        return df

    def calculate_momentum_indicators(self, data):
        """Calculate momentum indicators"""
        df = data.copy()

        # RSI (Relative Strength Index)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD (Moving Average Convergence Divergence)
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_histogram'] = df['MACD'] - df['MACD_signal']

        # Stochastic Oscillator
        low_min = df['low'].rolling(window=14).min()
        high_max = df['high'].rolling(window=14).max()
        df['%K'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
        df['%D'] = df['%K'].rolling(window=3).mean()

        return df

    def calculate_volatility_indicators(self, data):
        """Calculate volatility indicators"""
        df = data.copy()

        # Bollinger Bands
        sma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        df['BB_upper'] = sma20 + (std20 * 2)
        df['BB_lower'] = sma20 - (std20 * 2)
        df['BB_middle'] = sma20

        # Average True Range (ATR)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()

        return df

    def calculate_volume_indicators(self, data):
        """Calculate volume-based indicators"""
        df = data.copy()

        # Volume Moving Average
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()

        # On-Balance Volume (OBV)
        df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

        # Volume Rate of Change
        df['Volume_ROC'] = df['volume'].pct_change(periods=12) * 100

        return df

    def add_technical_indicators(self, symbol):
        """Add comprehensive technical indicators with quality checks"""
        data = self.price_data.load_market_data(symbol)

        if data.empty:
            self.logger.log_message('WARNING', 'DATA_PREPROCESSOR', f"No data found for {symbol}")
            return pd.DataFrame()

        # Data quality validation
        if not self.validate_data_quality(data):
            self.logger.log_message('WARNING', 'DATA_PREPROCESSOR', f"Data quality issues detected for {symbol}")

        # Handle missing data
        data = self.handle_missing_data(data)

        # Handle outliers
        data = self.detect_and_handle_outliers(data)

        # Ensure data is sorted by timestamp
        if 'timestamp' in data.columns:
            data = data.sort_values('timestamp')

        # Calculate all indicators
        data = self.calculate_moving_averages(data)
        data = self.calculate_momentum_indicators(data)
        data = self.calculate_volatility_indicators(data)
        data = self.calculate_volume_indicators(data)
        data = self.add_advanced_indicators(data)

        # Fill any remaining NaN values
        data = data.fillna(method='bfill').fillna(method='ffill').fillna(0)

        # Save processed data
        processed_file = f'data/{symbol}_processed.json'
        data.to_json(processed_file, orient='records', date_format='iso')

        self.logger.log_message('INFO', 'DATA_PREPROCESSOR', f"Added {len(data.columns)-5} indicators to {symbol}")
        return data

    def prepare_ml_features(self, data, lookback=60, forecast_horizon=1, target_col='close'):
        """Prepare features for machine learning with enhanced preprocessing"""
        df = data.copy()

        # Remove NaN values
        df = df.dropna()

        # Create target variable (future price movement)
        if target_col == 'close':
            df['target'] = (df['close'].shift(-forecast_horizon) > df['close']).astype(int)
        else:
            df['target'] = df[target_col].shift(-forecast_horizon)

        # Select feature columns (exclude target and non-numeric)
        feature_cols = [col for col in df.columns if col not in ['timestamp', 'target'] and df[col].dtype in ['float64', 'int64']]

        # Ensure we have enough data
        if len(df) < lookback + forecast_horizon:
            self.logger.log_message('WARNING', 'DATA_PREPROCESSOR', 'Insufficient data for sequence creation')
            return np.array([]), np.array([]), []

        # Create sequences for time series prediction
        X, y = [], []
        for i in range(len(df) - lookback - forecast_horizon):
            X.append(df[feature_cols].iloc[i:i+lookback].values)
            y.append(df['target'].iloc[i+lookback])

        X = np.array(X)
        y = np.array(y)

        self.logger.log_message('INFO', 'DATA_PREPROCESSOR', f'Created {len(X)} sequences of length {lookback} with {len(feature_cols)} features')
        return X, y, feature_cols

    def normalize_features(self, X_train, X_test=None, method='robust'):
        """Normalize features with multiple scaling methods"""
        # Reshape for scaling (flatten time series)
        original_shape = X_train.shape
        X_train_reshaped = X_train.reshape(-1, X_train.shape[-1])

        # Get appropriate scaler
        scaler = self.scalers.get(method, self.scalers['robust'])

        # Fit and transform training data
        X_train_scaled = scaler.fit_transform(X_train_reshaped)
        X_train_scaled = X_train_scaled.reshape(original_shape)

        if X_test is not None:
            # Transform test data
            test_shape = X_test.shape
            X_test_reshaped = X_test.reshape(-1, X_test.shape[-1])
            X_test_scaled = scaler.transform(X_test_reshaped)
            X_test_scaled = X_test_scaled.reshape(test_shape)
            return X_train_scaled, X_test_scaled

        return X_train_scaled

if __name__ == "__main__":
    preprocessor = DataPreprocessor()

    # Generate sample data
    pd_obj = PriceData()
    data = pd_obj.generate_sample_data('EURUSD', days=30)

    # Add technical indicators
    processed_data = preprocessor.add_technical_indicators('EURUSD')
    print(f"Processed data shape: {processed_data.shape}")
    print("Columns:", list(processed_data.columns))

    # Prepare ML features
    X, y, feature_cols = preprocessor.prepare_ml_features(processed_data)
    print(f"ML features shape: {X.shape}, Target shape: {y.shape}")
    print(f"Features: {feature_cols}")