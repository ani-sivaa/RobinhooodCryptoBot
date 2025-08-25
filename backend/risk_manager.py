import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Risk Management System following research paper recommendations
    Implements ATR-based position sizing and volatility-aware stop losses
    """
    
    def __init__(
        self, 
        account_balance: float, 
        max_risk_per_trade: float = 0.02, 
        daily_loss_limit: float = 0.10,
        atr_multiplier: float = 2.0
    ):
        self.account_balance = account_balance
        self.max_risk_per_trade = max_risk_per_trade  # 2% per trade
        self.daily_loss_limit = daily_loss_limit      # 10% daily limit
        self.atr_multiplier = atr_multiplier          # ATR multiplier for stops
        self.daily_losses = 0.0
        self.daily_trades = 0
        self.last_reset_date = datetime.now().date()
        self.open_positions = {}
        self.trade_history = []
    
    def reset_daily_limits(self):
        """Reset daily limits if new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_losses = 0.0
            self.daily_trades = 0
            self.last_reset_date = current_date
            logger.info("Daily limits reset")
    
    def calculate_position_size(
        self, 
        entry_price: float, 
        stop_loss_price: float, 
        atr: float,
        min_trade_amount: float = 5.0
    ) -> float:
        """Calculate position size using ATR-based risk management"""
        self.reset_daily_limits()
        
        if self.daily_losses >= self.account_balance * self.daily_loss_limit:
            logger.warning("Daily loss limit reached")
            return 0.0
        
        risk_amount = self.account_balance * self.max_risk_per_trade
        
        stop_loss_distance = abs(entry_price - stop_loss_price)
        
        if stop_loss_distance < atr * 0.5:
            stop_loss_distance = atr * self.atr_multiplier
            logger.info(f"Using ATR-based stop loss distance: {stop_loss_distance}")
        
        if stop_loss_distance > 0:
            position_size = risk_amount / stop_loss_distance
        else:
            position_size = 0.0
        
        max_position_value = self.account_balance * 0.1  # Max 10% of account per trade
        position_value = position_size * entry_price
        
        if position_value > max_position_value:
            position_size = max_position_value / entry_price
        
        if position_value < min_trade_amount:
            if min_trade_amount <= max_position_value:
                position_size = min_trade_amount / entry_price
            else:
                position_size = 0.0
        
        return position_size
    
    def calculate_atr_stop_loss(
        self, 
        current_price: float, 
        atr: float, 
        side: str, 
        multiplier: Optional[float] = None
    ) -> float:
        """Calculate ATR-based stop loss"""
        if multiplier is None:
            multiplier = self.atr_multiplier
        
        if side.lower() == 'buy':
            return current_price - (atr * multiplier)
        else:
            return current_price + (atr * multiplier)
    
    def calculate_take_profit(
        self, 
        entry_price: float, 
        stop_loss_price: float, 
        side: str, 
        risk_reward_ratio: float = 2.0
    ) -> float:
        """Calculate take profit based on risk-reward ratio"""
        risk = abs(entry_price - stop_loss_price)
        reward = risk * risk_reward_ratio
        
        if side.lower() == 'buy':
            return entry_price + reward
        else:
            return entry_price - reward
    
    def validate_trade(
        self, 
        symbol: str, 
        side: str, 
        quantity: float, 
        price: float
    ) -> Tuple[bool, str]:
        """Validate if trade meets risk management criteria"""
        self.reset_daily_limits()
        
        if self.daily_losses >= self.account_balance * self.daily_loss_limit:
            return False, "Daily loss limit exceeded"
        
        position_value = quantity * price
        max_position_value = self.account_balance * 0.1
        
        if position_value > max_position_value:
            return False, f"Position size too large: {position_value} > {max_position_value}"
        
        if symbol in self.open_positions:
            return False, f"Already have open position in {symbol}"
        
        if position_value < 5.0:
            return False, f"Position size too small: {position_value} < 5.0"
        
        return True, "Trade validated"
    
    def record_trade(
        self, 
        symbol: str, 
        side: str, 
        quantity: float, 
        price: float, 
        trade_type: str = "open"
    ):
        """Record trade for risk tracking"""
        trade_record = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'value': quantity * price,
            'type': trade_type
        }
        
        self.trade_history.append(trade_record)
        
        if trade_type == "open":
            self.open_positions[symbol] = {
                'side': side,
                'quantity': quantity,
                'entry_price': price,
                'entry_time': datetime.now()
            }
            self.daily_trades += 1
        elif trade_type == "close" and symbol in self.open_positions:
            entry_price = self.open_positions[symbol]['entry_price']
            entry_side = self.open_positions[symbol]['side']
            
            if entry_side == 'buy':
                pnl = (price - entry_price) * quantity
            else:
                pnl = (entry_price - price) * quantity
            
            if pnl < 0:
                self.daily_losses += abs(pnl)
            
            del self.open_positions[symbol]
            
            logger.info(f"Trade closed: {symbol}, P&L: {pnl:.2f}")
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        self.reset_daily_limits()
        
        total_position_value = sum(
            pos['quantity'] * pos['entry_price'] 
            for pos in self.open_positions.values()
        )
        
        return {
            'account_balance': self.account_balance,
            'daily_losses': self.daily_losses,
            'daily_loss_limit': self.account_balance * self.daily_loss_limit,
            'daily_trades': self.daily_trades,
            'open_positions': len(self.open_positions),
            'total_position_value': total_position_value,
            'available_buying_power': self.account_balance - total_position_value,
            'risk_utilization': total_position_value / self.account_balance
        }
    
    def update_trailing_stop(
        self, 
        symbol: str, 
        current_price: float, 
        atr: float
    ) -> Optional[float]:
        """Update trailing stop loss for open position"""
        if symbol not in self.open_positions:
            return None
        
        position = self.open_positions[symbol]
        side = position['side']
        
        new_stop = self.calculate_atr_stop_loss(current_price, atr, side)
        
        if 'stop_loss' not in position:
            position['stop_loss'] = new_stop
            return new_stop
        
        current_stop = position['stop_loss']
        
        if side == 'buy' and new_stop > current_stop:
            position['stop_loss'] = new_stop
            return new_stop
        elif side == 'sell' and new_stop < current_stop:
            position['stop_loss'] = new_stop
            return new_stop
        
        return current_stop
