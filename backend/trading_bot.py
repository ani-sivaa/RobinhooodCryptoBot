import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from robinhood_client import RobinhoodClient
from data_manager import DataManager
from risk_manager import RiskManager
from ml_engine import EnsembleMLEngine
from strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)

class TradingBot:
    """
    Main Trading Bot class that orchestrates all components
    Implements the complete trading system following research paper recommendations
    """
    
    def __init__(
        self, 
        api_key: str, 
        private_key: str, 
        account_balance: float = 100.0,
        symbols: List[str] = ['BTC', 'ETH']
    ):
        self.robinhood_client = RobinhoodClient(api_key, private_key)
        self.data_manager = DataManager(self.robinhood_client)
        self.risk_manager = RiskManager(account_balance)
        self.ml_engine = EnsembleMLEngine()
        self.strategy_engine = StrategyEngine(
            self.data_manager, 
            self.risk_manager, 
            self.ml_engine, 
            symbols
        )
        
        self.is_running = False
        self.last_trade_time = {}
        self.trade_history = []
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0
        }
        
        self.min_trade_interval = 300  # 5 minutes between trades for same symbol
        self.max_trades_per_day = 10
        self.auto_train_interval = 24  # hours
        
    async def start(self) -> Dict[str, Any]:
        """Start the trading bot"""
        try:
            logger.info("Starting trading bot...")
            
            account_info = await self._validate_connection()
            if not account_info:
                return {'status': 'error', 'message': 'Failed to connect to Robinhood API'}
            
            trading_pairs = self.data_manager.get_trading_pairs()
            if not trading_pairs:
                return {'status': 'error', 'message': 'No trading pairs available'}
            
            if not self.ml_engine.is_trained:
                training_result = self.strategy_engine.train_ml_model()
                logger.info(f"Initial model training: {training_result}")
            
            self.is_running = True
            logger.info("Trading bot started successfully")
            
            return {
                'status': 'success',
                'message': 'Trading bot started',
                'account_info': account_info,
                'trading_pairs': len(trading_pairs)
            }
        
        except Exception as e:
            logger.error(f"Failed to start trading bot: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def stop(self) -> Dict[str, Any]:
        """Stop the trading bot"""
        try:
            logger.info("Stopping trading bot...")
            self.is_running = False
            
            await self._cancel_open_orders()
            
            logger.info("Trading bot stopped")
            return {'status': 'success', 'message': 'Trading bot stopped'}
        
        except Exception as e:
            logger.error(f"Error stopping trading bot: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _validate_connection(self) -> Optional[Dict]:
        """Validate connection to Robinhood API"""
        try:
            account_info = self.robinhood_client.get_account()
            return account_info
        except Exception as e:
            logger.error(f"API connection validation failed: {e}")
            return None
    
    async def execute_trading_cycle(self) -> Dict[str, Any]:
        """Execute one complete trading cycle"""
        if not self.is_running:
            return {'status': 'stopped', 'message': 'Bot is not running'}
        
        try:
            self.data_manager.update_real_time_data(self.strategy_engine.symbols)
            
            signals = self.strategy_engine.get_trading_signals()
            
            executed_trades = []
            
            for signal in signals:
                should_execute, reason = self.strategy_engine.should_execute_trade(signal)
                
                if should_execute:
                    if self._can_trade_symbol(signal['symbol']):
                        trade_result = await self._execute_trade(signal)
                        if trade_result['status'] == 'success':
                            executed_trades.append(trade_result)
                            self.last_trade_time[signal['symbol']] = datetime.now()
                
            await self._update_trailing_stops()
            
            if self.ml_engine.should_retrain(self.auto_train_interval):
                training_result = self.strategy_engine.train_ml_model()
                logger.info(f"Auto-retraining result: {training_result}")
            
            return {
                'status': 'success',
                'signals_analyzed': len(signals),
                'trades_executed': len(executed_trades),
                'executed_trades': executed_trades
            }
        
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _can_trade_symbol(self, symbol: str) -> bool:
        """Check if we can trade a symbol based on timing constraints"""
        if symbol not in self.last_trade_time:
            return True
        
        time_since_last = datetime.now() - self.last_trade_time[symbol]
        return time_since_last.total_seconds() >= self.min_trade_interval
    
    async def _execute_trade(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade based on signal"""
        try:
            symbol = signal['symbol']
            action = signal['action']
            risk_metrics = signal.get('risk_metrics', {})
            current_price = signal.get('current_price', 0)
            
            position_size = risk_metrics.get('position_size', 0)
            quote_amount = position_size * current_price
            
            if quote_amount < 5.0:
                return {'status': 'skipped', 'reason': 'Trade amount too small'}
            
            side = 'buy' if action == 'buy' else 'sell'
            order_result = self.robinhood_client.create_market_order(symbol, side, quote_amount)
            
            trade_record = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'side': side,
                'quantity': position_size,
                'price': current_price,
                'quote_amount': quote_amount,
                'order_id': order_result.get('id'),
                'signal_strength': signal.get('strength', 0),
                'confidence': signal.get('confidence', 0)
            }
            
            self.trade_history.append(trade_record)
            self.risk_manager.record_trade(symbol, side, position_size, current_price, "open")
            
            stop_loss_price = risk_metrics.get('stop_loss')
            if stop_loss_price:
                try:
                    stop_side = 'sell' if side == 'buy' else 'buy'
                    self.robinhood_client.create_stop_loss_order(
                        symbol, stop_side, position_size, stop_loss_price
                    )
                except Exception as e:
                    logger.warning(f"Failed to place stop loss: {e}")
            
            logger.info(f"Trade executed: {symbol} {side} {position_size} @ {current_price}")
            
            return {
                'status': 'success',
                'trade': trade_record,
                'order_result': order_result
            }
        
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _update_trailing_stops(self):
        """Update trailing stops for open positions"""
        try:
            for symbol in self.risk_manager.open_positions:
                current_price = self.data_manager.get_latest_price(symbol)
                if current_price:
                    historical_data = self.data_manager.get_historical_data(symbol, period="1mo")
                    if not historical_data.empty:
                        from technical_indicators import TechnicalIndicators
                        atr = TechnicalIndicators.calculate_atr(
                            historical_data['high'],
                            historical_data['low'],
                            historical_data['close']
                        ).iloc[-1]
                        
                        new_stop = self.risk_manager.update_trailing_stop(symbol, current_price, atr)
                        if new_stop:
                            logger.info(f"Updated trailing stop for {symbol}: {new_stop}")
        
        except Exception as e:
            logger.error(f"Error updating trailing stops: {e}")
    
    async def _cancel_open_orders(self):
        """Cancel all open orders"""
        try:
            orders = self.robinhood_client.get_orders(limit=50)
            for order in orders:
                if order.get('state') == 'open':
                    self.robinhood_client.cancel_order(order['id'])
                    logger.info(f"Cancelled order: {order['id']}")
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return {
            'is_running': self.is_running,
            'symbols': self.strategy_engine.symbols,
            'last_trade_times': self.last_trade_time,
            'total_trades': len(self.trade_history),
            'open_positions': len(self.risk_manager.open_positions),
            'performance_metrics': self.performance_metrics,
            'risk_metrics': self.risk_manager.get_risk_metrics(),
            'strategy_status': self.strategy_engine.get_strategy_status()
        }
    
    def get_portfolio(self) -> Dict[str, Any]:
        """Get current portfolio information"""
        try:
            account_info = self.robinhood_client.get_account()
            holdings = self.robinhood_client.get_holdings()
            
            portfolio = {
                'account_info': account_info,
                'holdings': holdings,
                'risk_metrics': self.risk_manager.get_risk_metrics(),
                'performance': self.performance_metrics
            }
            
            return portfolio
        
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return {}
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history"""
        return self.trade_history[-limit:] if self.trade_history else []
    
    async def manual_trade(
        self, 
        symbol: str, 
        side: str, 
        amount: float, 
        order_type: str = "market"
    ) -> Dict[str, Any]:
        """Execute a manual trade"""
        try:
            current_price = self.data_manager.get_latest_price(symbol)
            if not current_price:
                return {'status': 'error', 'message': 'Unable to get current price'}
            
            quantity = amount / current_price
            is_valid, reason = self.risk_manager.validate_trade(symbol, side, quantity, current_price)
            
            if not is_valid:
                return {'status': 'error', 'message': reason}
            
            if order_type == "market":
                order_result = self.robinhood_client.create_market_order(symbol, side, amount)
            else:
                return {'status': 'error', 'message': 'Only market orders supported for manual trades'}
            
            trade_record = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': current_price,
                'quote_amount': amount,
                'order_id': order_result.get('id'),
                'type': 'manual'
            }
            
            self.trade_history.append(trade_record)
            self.risk_manager.record_trade(symbol, side, quantity, current_price, "open")
            
            return {
                'status': 'success',
                'trade': trade_record,
                'order_result': order_result
            }
        
        except Exception as e:
            logger.error(f"Manual trade failed: {e}")
            return {'status': 'error', 'message': str(e)}
