from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging
from .models import Trade, Portfolio, TradingStrategy, OrderSide
from .config import settings

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Risk Manager component - enforces strict rules to protect capital
    and prevent catastrophic losses as emphasized in the research report.
    """
    
    def __init__(self):
        self.daily_trades = []
        self.daily_loss = 0.0
        self.last_reset_date = datetime.now().date()
        
        self.max_loss_per_trade = settings.max_loss_per_trade  # 2%
        self.daily_loss_limit = settings.daily_loss_limit      # 10%
        self.trading_budget = settings.trading_budget          # $100
        
        self.max_trades_per_day = 20
        self.max_position_size = 0.15  # 15% of portfolio max
        self.min_trade_amount = 5.0    # Minimum $5 trade
        
    def validate_trade(
        self, 
        strategy: TradingStrategy, 
        portfolio: Portfolio,
        symbol: str,
        current_price: float
    ) -> Dict[str, any]:
        """
        Validates a trade against all risk management rules
        Returns: {
            "approved": bool,
            "reason": str,
            "adjusted_quantity": float,
            "stop_loss": float,
            "take_profit": float
        }
        """
        self._reset_daily_counters_if_needed()
        
        if settings.paper_trading_mode:
            logger.info("Paper trading mode - trade validation for simulation only")
        
        validation_result = {
            "approved": False,
            "reason": "",
            "adjusted_quantity": 0.0,
            "stop_loss": strategy.stop_loss,
            "take_profit": strategy.take_profit
        }
        
        if len(self.daily_trades) >= self.max_trades_per_day:
            validation_result["reason"] = f"Daily trade limit reached ({self.max_trades_per_day})"
            return validation_result
        
        if self.daily_loss >= (self.trading_budget * self.daily_loss_limit):
            validation_result["reason"] = f"Daily loss limit reached (${self.daily_loss:.2f})"
            return validation_result
        
        if strategy.confidence < 0.3:
            validation_result["reason"] = f"Strategy confidence too low ({strategy.confidence:.2f})"
            return validation_result
        
        available_cash = portfolio.available_cash
        max_trade_value = min(
            available_cash * self.max_position_size,
            self.trading_budget * self.max_loss_per_trade / self.max_loss_per_trade  # Max risk per trade
        )
        
        suggested_value = (strategy.suggested_quantity or 0.1) * portfolio.total_value
        trade_value = min(suggested_value, max_trade_value)
        
        if trade_value < self.min_trade_amount:
            validation_result["reason"] = f"Trade value too small (${trade_value:.2f} < ${self.min_trade_amount})"
            return validation_result
        
        adjusted_quantity = trade_value / current_price
        
        if strategy.signal.value == "buy" and trade_value > available_cash:
            validation_result["reason"] = f"Insufficient funds (need ${trade_value:.2f}, have ${available_cash:.2f})"
            return validation_result
        
        if strategy.signal.value == "sell":
            current_position = portfolio.positions.get(symbol, 0)
            if adjusted_quantity > current_position:
                adjusted_quantity = current_position
                if adjusted_quantity <= 0:
                    validation_result["reason"] = f"No {symbol} position to sell"
                    return validation_result
        
        if strategy.signal.value == "buy":
            if strategy.stop_loss and strategy.stop_loss >= current_price:
                validation_result["stop_loss"] = current_price * (1 - self.max_loss_per_trade)
                logger.warning(f"Adjusted stop loss from {strategy.stop_loss} to {validation_result['stop_loss']}")
            
            if strategy.take_profit and strategy.take_profit <= current_price:
                validation_result["take_profit"] = current_price * (1 + self.max_loss_per_trade * 2)
                logger.warning(f"Adjusted take profit from {strategy.take_profit} to {validation_result['take_profit']}")
        
        elif strategy.signal.value == "sell":
            if strategy.stop_loss and strategy.stop_loss <= current_price:
                validation_result["stop_loss"] = current_price * (1 + self.max_loss_per_trade)
                logger.warning(f"Adjusted stop loss from {strategy.stop_loss} to {validation_result['stop_loss']}")
            
            if strategy.take_profit and strategy.take_profit >= current_price:
                validation_result["take_profit"] = current_price * (1 - self.max_loss_per_trade * 2)
                logger.warning(f"Adjusted take profit from {strategy.take_profit} to {validation_result['take_profit']}")
        
        validation_result.update({
            "approved": True,
            "reason": "Trade approved",
            "adjusted_quantity": adjusted_quantity
        })
        
        logger.info(f"Trade validated: {symbol} {strategy.signal.value} {adjusted_quantity:.6f} @ ${current_price:.2f}")
        return validation_result
    
    def record_trade(self, trade: Trade, portfolio_value_before: float, portfolio_value_after: float):
        """Record a completed trade for risk tracking"""
        self._reset_daily_counters_if_needed()
        
        pnl = portfolio_value_after - portfolio_value_before
        
        trade_record = {
            "trade": trade,
            "pnl": pnl,
            "timestamp": datetime.now()
        }
        
        self.daily_trades.append(trade_record)
        
        if pnl < 0:
            self.daily_loss += abs(pnl)
        
        logger.info(f"Trade recorded: {trade.symbol} {trade.side.value} P&L: ${pnl:.2f}")
    
    def get_risk_metrics(self, portfolio: Portfolio) -> Dict[str, any]:
        """Get current risk metrics and limits"""
        self._reset_daily_counters_if_needed()
        
        return {
            "daily_trades_count": len(self.daily_trades),
            "daily_trades_limit": self.max_trades_per_day,
            "daily_loss": self.daily_loss,
            "daily_loss_limit": self.trading_budget * self.daily_loss_limit,
            "daily_loss_percentage": (self.daily_loss / self.trading_budget) * 100,
            "available_cash": portfolio.available_cash,
            "portfolio_value": portfolio.total_value,
            "max_trade_value": min(
                portfolio.available_cash * self.max_position_size,
                self.trading_budget * 0.1
            ),
            "risk_level": self._calculate_risk_level(portfolio),
            "trading_enabled": self._is_trading_enabled(portfolio)
        }
    
    def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Emergency stop all trading activities"""
        logger.critical(f"EMERGENCY STOP ACTIVATED: {reason}")
        
        self.daily_loss = self.trading_budget * self.daily_loss_limit
        
        return {
            "status": "emergency_stop_activated",
            "reason": reason,
            "timestamp": datetime.now(),
            "trading_disabled": True
        }
    
    def _reset_daily_counters_if_needed(self):
        """Reset daily counters if it's a new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_trades = []
            self.daily_loss = 0.0
            self.last_reset_date = current_date
            logger.info("Daily risk counters reset")
    
    def _calculate_risk_level(self, portfolio: Portfolio) -> str:
        """Calculate current risk level"""
        loss_percentage = (self.daily_loss / self.trading_budget) * 100
        
        if loss_percentage >= 8:  # 80% of daily limit
            return "HIGH"
        elif loss_percentage >= 5:  # 50% of daily limit
            return "MEDIUM"
        else:
            return "LOW"
    
    def _is_trading_enabled(self, portfolio: Portfolio) -> bool:
        """Check if trading should be enabled based on current risk metrics"""
        if len(self.daily_trades) >= self.max_trades_per_day:
            return False
        
        if self.daily_loss >= (self.trading_budget * self.daily_loss_limit):
            return False
        
        if portfolio.total_value < (self.trading_budget * 0.5):  # 50% of original budget
            return False
        
        return True
