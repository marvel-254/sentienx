"""
Common data structures for SENTIENX trading system
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
from enum import Enum
import pandas as pd

class Signal(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0

@dataclass
class StrategyResult:
    """Enhanced strategy result with detailed information"""
    signal: Signal
    confidence: float
    strength: float
    indicators: Dict
    metadata: Dict
    timestamp: pd.Timestamp

@dataclass
class Position:
    """Position tracking for strategy evaluation"""
    symbol: str
    side: Signal
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    timestamp: pd.Timestamp
    strategy: str