"""
Advanced Risk Management System for SENTIENX
Implements sophisticated risk controls, position sizing, and portfolio optimization
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from logger.log_writer import Logger
from common_types import StrategyResult, Signal

@dataclass
class RiskMetrics:
    """Comprehensive risk metrics for positions and portfolio"""
    var_95: float  # Value at Risk (95% confidence)
    var_99: float  # Value at Risk (99% confidence)
    expected_shortfall: float  # Expected shortfall (CVaR)
    max_drawdown: float  # Maximum drawdown
    sharpe_ratio: float  # Risk-adjusted returns
    sortino_ratio: float  # Downside risk-adjusted returns
    volatility: float  # Portfolio volatility
    beta: float  # Market beta
    correlation_matrix: np.ndarray  # Asset correlations

@dataclass
class PositionLimits:
    """Position size and risk limits"""
    max_position_size: float  # Maximum position size (% of portfolio)
    max_portfolio_risk: float  # Maximum portfolio VaR (%)
    max_drawdown_limit: float  # Maximum allowed drawdown (%)
    max_correlation: float  # Maximum correlation between positions
    min_diversification: int  # Minimum number of positions
    max_concentration: float  # Maximum concentration in single asset (%)

class RiskManager:
    """Advanced risk management system with multiple risk models"""

    def __init__(self, logger=None, initial_capital=10000):
        self.logger = logger or Logger()
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.portfolio = {}
        self.trade_history = []
        self.risk_limits = PositionLimits(
            max_position_size=0.1,  # 10% of portfolio
            max_portfolio_risk=0.05,  # 5% VaR limit
            max_drawdown_limit=0.2,  # 20% max drawdown
            max_correlation=0.7,  # Max 70% correlation
            min_diversification=3,  # At least 3 positions
            max_concentration=0.25  # Max 25% in single asset
        )

        # Risk models
        self.risk_models = {
            'historical': self._historical_var,
            'parametric': self._parametric_var,
            'monte_carlo': self._monte_carlo_var
        }

        self.active_risk_model = 'historical'

    def _historical_var(self, returns, confidence: float) -> float:
        """Historical Value at Risk"""
        return float(np.percentile(returns, (1 - confidence) * 100))

    def _parametric_var(self, returns, confidence: float) -> float:
        """Parametric Value at Risk (Normal distribution assumption)"""
        mean = returns.mean()
        std = returns.std()
        z_score = np.abs(np.percentile(np.random.normal(0, 1, 10000), (1 - confidence) * 100))
        return float(mean - z_score * std)

    def _monte_carlo_var(self, returns, confidence: float, simulations: int = 10000) -> float:
        """Monte Carlo Value at Risk"""
        mean = returns.mean()
        std = returns.std()

        # Simulate returns
        simulated_returns = np.random.normal(mean, std, simulations)
        return float(np.percentile(simulated_returns, (1 - confidence) * 100))

    def adjust_signal(self, signal: StrategyResult, portfolio: Dict) -> StrategyResult:
        """Adjust trading signal based on risk management rules"""
        if signal.signal == Signal.HOLD:
            return signal

        # Check portfolio risk limits
        if not self._check_portfolio_limits(signal, portfolio):
            self.logger.log_message('WARNING', 'RISK_MANAGER',
                                  f'Signal rejected due to portfolio limits: {signal.metadata}')
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=0.5,
                strength=0.0,
                indicators=signal.indicators,
                metadata={**signal.metadata, 'risk_rejection': 'portfolio_limits'},
                timestamp=pd.Timestamp.now()
            )

        # Calculate position size
        position_size = self.calculate_position_size(signal, portfolio)

        # Adjust confidence based on risk
        risk_adjusted_confidence = self._adjust_confidence_for_risk(signal, position_size)

        return StrategyResult(
            signal=signal.signal,
            confidence=risk_adjusted_confidence,
            strength=signal.strength,
            indicators={**signal.indicators, 'position_size': position_size},
            metadata={**signal.metadata, 'risk_adjusted': True, 'position_size': position_size},
            timestamp=signal.timestamp
        )

    def calculate_position_size(self, signal: StrategyResult, portfolio: Dict) -> float:
        """Calculate optimal position size using multiple methods"""

        # Kelly Criterion
        kelly_size = self._kelly_criterion(signal)

        # Fixed Fractional
        fixed_size = self._fixed_fractional(signal)

        # Risk Parity
        risk_parity_size = self._risk_parity_sizing(signal, portfolio)

        # Volatility-adjusted
        vol_adjusted_size = self._volatility_adjusted_sizing(signal)

        # Take the minimum of all sizing methods for conservatism
        position_size = min(kelly_size, fixed_size, risk_parity_size, vol_adjusted_size)

        # Apply position limits
        max_size = self.risk_limits.max_position_size * self.current_capital
        position_size = min(position_size, max_size)

        # Ensure minimum position size (avoid tiny positions)
        min_size = self.current_capital * 0.01  # 1% minimum
        position_size = max(position_size, min_size)

        return position_size

    def _kelly_criterion(self, signal: StrategyResult) -> float:
        """Kelly Criterion position sizing"""
        # Simplified Kelly: (bp - q) / b
        # where b = odds, p = win probability, q = loss probability

        win_prob = signal.confidence
        loss_prob = 1 - win_prob

        # Assume 2:1 reward-to-risk ratio for forex
        reward_to_risk = 2.0
        kelly_fraction = (win_prob * reward_to_risk - loss_prob) / reward_to_risk

        # Half-Kelly for conservatism
        kelly_fraction = max(0, kelly_fraction * 0.5)

        return kelly_fraction * self.current_capital

    def _fixed_fractional(self, signal: StrategyResult) -> float:
        """Fixed fractional position sizing"""
        # Risk 2% of capital per trade
        risk_per_trade = 0.02
        return risk_per_trade * self.current_capital

    def _risk_parity_sizing(self, signal: StrategyResult, portfolio: Dict) -> float:
        """Risk parity based position sizing"""
        # Equal risk contribution from each position

        num_positions = len(portfolio) + 1  # Include new position
        if num_positions == 0:
            return self.current_capital * 0.1

        # Assume equal volatility for simplicity
        risk_per_position = (self.risk_limits.max_portfolio_risk * self.current_capital) / num_positions
        return risk_per_position

    def _volatility_adjusted_sizing(self, signal: StrategyResult) -> float:
        """Volatility-adjusted position sizing"""
        # Reduce position size in high volatility periods
        # This would use ATR or realized volatility

        # Placeholder: assume moderate volatility
        volatility_factor = 1.0  # Scale based on market volatility

        base_size = self.current_capital * 0.05
        return base_size / volatility_factor

    def _check_portfolio_limits(self, signal: StrategyResult, portfolio: Dict) -> bool:
        """Check if signal complies with portfolio risk limits"""

        # Check diversification
        if len(portfolio) < self.risk_limits.min_diversification - 1:
            return True  # Allow building initial positions

        # Check concentration limit
        for symbol, position in portfolio.items():
            if position.get('size', 0) > self.risk_limits.max_concentration * self.current_capital:
                return False

        # Check correlation limits (simplified)
        # In practice, would check correlation with existing positions

        # Check drawdown limit
        current_drawdown = self._calculate_drawdown()
        if current_drawdown > self.risk_limits.max_drawdown_limit:
            return False

        return True

    def _adjust_confidence_for_risk(self, signal: StrategyResult, position_size: float) -> float:
        """Adjust signal confidence based on position size and risk"""
        # Reduce confidence for larger positions to be more conservative
        size_ratio = position_size / self.current_capital

        if size_ratio > 0.1:  # Large position
            confidence_penalty = 0.2
        elif size_ratio > 0.05:  # Medium position
            confidence_penalty = 0.1
        else:  # Small position
            confidence_penalty = 0.0

        adjusted_confidence = signal.confidence * (1 - confidence_penalty)
        return max(0.1, adjusted_confidence)  # Minimum confidence

    def calculate_portfolio_risk(self, portfolio: Dict, returns_data: pd.DataFrame) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics"""

        if returns_data.empty or len(returns_data.columns) == 0:
            return self._default_risk_metrics()

        # Calculate returns
        returns = returns_data.pct_change().dropna()

        if returns.empty:
            return self._default_risk_metrics()

        # Portfolio weights (simplified equal weight)
        weights = np.ones(len(returns.columns)) / len(returns.columns)

        # Portfolio returns
        portfolio_returns = returns.dot(weights)

        # VaR calculations using active risk model
        var_method = self.risk_models.get(self.active_risk_model, self._historical_var)
        var_95 = float(var_method(portfolio_returns, 0.95))
        var_99 = float(var_method(portfolio_returns, 0.99))
        expected_shortfall = float(self._calculate_expected_shortfall(portfolio_returns, 0.95))

        # Drawdown
        max_drawdown = float(self._calculate_max_drawdown(portfolio_returns))

        # Risk-adjusted ratios
        sharpe_ratio = float(self._calculate_sharpe_ratio(portfolio_returns))
        sortino_ratio = float(self._calculate_sortino_ratio(portfolio_returns))

        # Volatility and beta
        volatility = float(portfolio_returns.std() * np.sqrt(252))  # Annualized
        beta = float(self._calculate_beta(portfolio_returns, returns))

        # Correlation matrix
        correlation_matrix = returns.corr().values

        return RiskMetrics(
            var_95=float(var_95),
            var_99=float(var_99),
            expected_shortfall=float(expected_shortfall),
            max_drawdown=float(max_drawdown),
            sharpe_ratio=float(sharpe_ratio),
            sortino_ratio=float(sortino_ratio),
            volatility=volatility,
            beta=float(beta),
            correlation_matrix=correlation_matrix
        )

    def _calculate_var(self, returns, confidence: float) -> float:
        """Calculate Value at Risk"""
        return float(np.percentile(returns, (1 - confidence) * 100))

    def _calculate_expected_shortfall(self, returns, confidence: float) -> float:
        """Calculate Expected Shortfall (CVaR)"""
        var = self._calculate_var(returns, confidence)
        tail_losses = returns[returns <= var]
        return float(tail_losses.mean()) if len(tail_losses) > 0 else 0.0

    def _calculate_max_drawdown(self, returns) -> float:
        """Calculate maximum drawdown"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return float(drawdown.min())

    def _calculate_sharpe_ratio(self, returns, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
        if excess_returns.std() == 0:
            return 0.0
        return float(excess_returns.mean() / excess_returns.std() * np.sqrt(252))

    def _calculate_sortino_ratio(self, returns, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (downside risk only)"""
        excess_returns = returns - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        return float(excess_returns.mean() / downside_returns.std() * np.sqrt(252))

    def _calculate_beta(self, portfolio_returns, asset_returns) -> float:
        """Calculate portfolio beta"""
        market_returns = asset_returns.mean(axis=1)  # Equal-weighted market

        covariance = np.cov(portfolio_returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)

        if market_variance == 0:
            return 1.0
        return float(covariance / market_variance)

    def _calculate_drawdown(self) -> float:
        """Calculate current portfolio drawdown"""
        if not self.trade_history:
            return 0.0

        # Simplified drawdown calculation
        peak = self.initial_capital
        current_value = self.current_capital

        for trade in self.trade_history:
            if trade.get('pnl', 0) > 0:
                peak = max(peak, current_value)

        if peak == 0:
            return 0.0

        return (peak - current_value) / peak

    def _default_risk_metrics(self) -> RiskMetrics:
        """Return default risk metrics when data is unavailable"""
        return RiskMetrics(
            var_95=0.05,
            var_99=0.10,
            expected_shortfall=0.07,
            max_drawdown=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            volatility=0.20,
            beta=1.0,
            correlation_matrix=np.eye(1)
        )

    def update_portfolio(self, symbol: str, action: Signal, quantity: float, price: float):
        """Update portfolio after trade execution"""
        if action == Signal.BUY:
            if symbol not in self.portfolio:
                self.portfolio[symbol] = {'quantity': 0, 'avg_price': 0}

            # Update average price and quantity
            total_value = self.portfolio[symbol]['quantity'] * self.portfolio[symbol]['avg_price']
            new_total_value = total_value + quantity * price
            new_quantity = self.portfolio[symbol]['quantity'] + quantity

            self.portfolio[symbol]['quantity'] = new_quantity
            self.portfolio[symbol]['avg_price'] = new_total_value / new_quantity if new_quantity > 0 else 0

        elif action == Signal.SELL:
            if symbol in self.portfolio:
                self.portfolio[symbol]['quantity'] = max(0, self.portfolio[symbol]['quantity'] - quantity)

                # Remove position if quantity is zero
                if self.portfolio[symbol]['quantity'] == 0:
                    del self.portfolio[symbol]

    def stress_test_portfolio(self, portfolio: Dict, scenarios: List[Dict]) -> Dict:
        """Perform stress testing on portfolio"""
        results = {}

        for scenario in scenarios:
            scenario_name = scenario['name']
            shock_returns = scenario['returns']  # Dict of symbol -> return shock

            # Calculate portfolio P&L under scenario
            portfolio_pnl = 0
            for symbol, position in portfolio.items():
                shock = shock_returns.get(symbol, 0)
                position_value = position['quantity'] * position['avg_price']
                pnl = position_value * shock
                portfolio_pnl += pnl

            results[scenario_name] = {
                'pnl': portfolio_pnl,
                'return_pct': portfolio_pnl / self.current_capital,
                'breach_limits': abs(portfolio_pnl / self.current_capital) > self.risk_limits.max_portfolio_risk
            }

        return results

    def generate_risk_report(self) -> Dict:
        """Generate comprehensive risk report"""
        return {
            'portfolio_value': self.current_capital,
            'positions': self.portfolio,
            'total_positions': len(self.portfolio),
            'risk_limits': {
                'max_position_size': self.risk_limits.max_position_size,
                'max_portfolio_risk': self.risk_limits.max_portfolio_risk,
                'max_drawdown_limit': self.risk_limits.max_drawdown_limit,
                'max_concentration': self.risk_limits.max_concentration
            },
            'current_drawdown': self._calculate_drawdown(),
            'total_trades': len(self.trade_history),
            'generated_at': datetime.now().isoformat()
        }
