from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class TradingSignal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class MarketData(BaseModel):
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    change_24h: Optional[float] = None

class TechnicalIndicators(BaseModel):
    symbol: str
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    sma_20: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    timestamp: datetime

class NewsItem(BaseModel):
    title: str
    content: str
    source: str
    sentiment: Optional[str] = None  # positive, negative, neutral
    timestamp: datetime
    symbols: List[str] = []

class Trade(BaseModel):
    id: Optional[str] = None
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime
    filled_price: Optional[float] = None
    filled_quantity: Optional[float] = None

class Portfolio(BaseModel):
    total_value: float
    available_cash: float
    positions: Dict[str, float]  # symbol -> quantity
    daily_pnl: float
    total_pnl: float
    last_updated: datetime

class StrategyConfig(BaseModel):
    name: str
    enabled: bool = True
    parameters: Dict[str, Any] = {}
    risk_limits: Dict[str, float] = {}

class TradingStrategy(BaseModel):
    signal: TradingSignal
    confidence: float
    reasoning: str
    suggested_quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
