import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
from .data_ingestor import DataIngestor
from .strategy_engine import StrategyEngine
from .risk_manager import RiskManager
from .execution_module import ExecutionModule
from .models import TradingSignal, OrderType, OrderSide, StrategyConfig
from .config import settings

logger = logging.getLogger(__name__)

class TradingBot:
    """
    Main Trading Bot orchestrator that coordinates all components
    following the modular architecture from the research report.
    """
    
    def __init__(self):
        self.data_ingestor = DataIngestor()
        self.strategy_engine = StrategyEngine()
        self.risk_manager = RiskManager()
        self.execution_module = ExecutionModule()
        
        self.is_running = False
        self.symbols = ["dogecoin", "cardano", "stellar", "polygon"]  # Cheaper crypto symbols for testing
        self.strategy_config = StrategyConfig(
            name="combined",
            enabled=True,
            parameters={
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "macd_threshold": 0.001,
                "confidence_threshold": 0.6
            },
            risk_limits={
                "max_position_size": 0.1,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.05
            }
        )
        
        self.loop_interval = 30  # seconds between analysis cycles
        self.last_analysis = {}
    
    async def start(self):
        """Start the trading bot"""
        if self.is_running:
            logger.warning("Trading bot is already running")
            return
        
        self.is_running = True
        logger.info("Starting trading bot...")
        
        try:
            async with self.data_ingestor, self.execution_module:
                while self.is_running:
                    await self._trading_cycle()
                    await asyncio.sleep(self.loop_interval)
        
        except Exception as e:
            logger.error(f"Trading bot error: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the trading bot"""
        logger.info("Stopping trading bot...")
        self.is_running = False
        # Close data ingestor session
        await self.data_ingestor.close()
    
    async def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Emergency stop with risk manager intervention"""
        logger.critical(f"EMERGENCY STOP: {reason}")
        await self.stop()
        return self.risk_manager.emergency_stop(reason)
    
    async def _trading_cycle(self):
        """Execute one complete trading cycle"""
        try:
            logger.info("Starting trading cycle...")
            
            market_data_list = await self.data_ingestor.get_market_data(self.symbols)
            news_items = await self.data_ingestor.get_crypto_news(self.symbols, limit=10)
            
            portfolio = await self.execution_module.get_portfolio()
            
            risk_metrics = self.risk_manager.get_risk_metrics(portfolio)
            if not risk_metrics["trading_enabled"]:
                logger.warning(f"Trading disabled: {risk_metrics}")
                return
            
            for market_data in market_data_list:
                await self._analyze_and_trade_symbol(market_data, news_items, portfolio)
            
            logger.info("Trading cycle completed")
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
    
    async def _analyze_and_trade_symbol(self, market_data, news_items, portfolio):
        """Analyze and potentially trade a single symbol"""
        try:
            symbol = market_data.symbol
            
            technical_indicators = await self.data_ingestor.calculate_technical_indicators(symbol)
            
            strategy_result = self.strategy_engine.analyze_market(
                market_data=market_data,
                technical_indicators=technical_indicators,
                news_items=news_items,
                strategy_config=self.strategy_config
            )
            
            self.last_analysis[symbol] = {
                "market_data": market_data,
                "technical_indicators": technical_indicators,
                "strategy_result": strategy_result,
                "timestamp": datetime.now()
            }
            
            if strategy_result.signal == TradingSignal.HOLD:
                logger.info(f"{symbol}: HOLD signal - {strategy_result.reasoning}")
                return
            
            validation = self.risk_manager.validate_trade(
                strategy=strategy_result,
                portfolio=portfolio,
                symbol=symbol,
                current_price=market_data.price
            )
            
            if not validation["approved"]:
                logger.warning(f"{symbol}: Trade rejected - {validation['reason']}")
                return
            
            portfolio_value_before = portfolio.total_value
            
            order_side = OrderSide.BUY if strategy_result.signal == TradingSignal.BUY else OrderSide.SELL
            
            trade = await self.execution_module.place_order(
                symbol=symbol,
                side=order_side,
                order_type=OrderType.MARKET,
                quantity=validation["adjusted_quantity"],
                price=market_data.price
            )
            
            portfolio_after = await self.execution_module.get_portfolio()
            self.risk_manager.record_trade(
                trade=trade,
                portfolio_value_before=portfolio_value_before,
                portfolio_value_after=portfolio_after.total_value
            )
            
            logger.info(f"Trade executed: {trade.symbol} {trade.side.value} {trade.quantity} @ ${trade.filled_price}")
            
        except Exception as e:
            logger.error(f"Error analyzing {market_data.symbol}: {e}")
    
    async def get_status(self) -> Dict:
        """Get current bot status and metrics"""
        portfolio = await self.execution_module.get_portfolio()
        risk_metrics = self.risk_manager.get_risk_metrics(portfolio)
        
        return {
            "is_running": self.is_running,
            "paper_trading_mode": settings.paper_trading_mode,
            "portfolio": portfolio.dict(),
            "risk_metrics": risk_metrics,
            "strategy_config": self.strategy_config.dict(),
            "symbols": self.symbols,
            "last_analysis": {
                symbol: {
                    "signal": analysis["strategy_result"].signal.value,
                    "confidence": analysis["strategy_result"].confidence,
                    "reasoning": analysis["strategy_result"].reasoning,
                    "price": analysis["market_data"].price,
                    "timestamp": analysis["timestamp"].isoformat()
                }
                for symbol, analysis in self.last_analysis.items()
            }
        }
    
    def update_strategy_config(self, new_config: Dict):
        """Update strategy configuration in real-time"""
        try:
            if "parameters" in new_config:
                self.strategy_config.parameters.update(new_config["parameters"])
            
            if "risk_limits" in new_config:
                self.strategy_config.risk_limits.update(new_config["risk_limits"])
            
            if "enabled" in new_config:
                self.strategy_config.enabled = new_config["enabled"]
            
            if "name" in new_config:
                self.strategy_config.name = new_config["name"]
            
            logger.info(f"Strategy configuration updated: {self.strategy_config.dict()}")
            return {"status": "success", "config": self.strategy_config.dict()}
            
        except Exception as e:
            logger.error(f"Error updating strategy config: {e}")
            return {"status": "error", "message": str(e)}
    
    def update_symbols(self, new_symbols: List[str]):
        """Update the list of symbols to trade"""
        self.symbols = new_symbols
        logger.info(f"Trading symbols updated: {self.symbols}")
        return {"status": "success", "symbols": self.symbols}
    
    async def get_trade_history(self):
        """Get trade history"""
        return self.execution_module.get_trade_history()
    
    async def manual_trade(self, symbol: str, side: str, quantity: float, order_type: str = "market"):
        """Execute a manual trade"""
        try:
            portfolio = await self.execution_module.get_portfolio()
            
            market_data_list = await self.data_ingestor.get_market_data([symbol])
            if not market_data_list:
                return {"status": "error", "message": f"Could not fetch market data for {symbol}"}
            
            market_data = market_data_list[0]
            
            from .models import TradingStrategy, TradingSignal
            manual_strategy = TradingStrategy(
                signal=TradingSignal.BUY if side.lower() == "buy" else TradingSignal.SELL,
                confidence=1.0,  # Manual trades have full confidence
                reasoning="Manual trade",
                suggested_quantity=quantity
            )
            
            validation = self.risk_manager.validate_trade(
                strategy=manual_strategy,
                portfolio=portfolio,
                symbol=symbol,
                current_price=market_data.price
            )
            
            if not validation["approved"]:
                return {"status": "error", "message": validation["reason"]}
            
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            order_type_enum = OrderType.MARKET if order_type.lower() == "market" else OrderType.LIMIT
            
            trade = await self.execution_module.place_order(
                symbol=symbol,
                side=order_side,
                order_type=order_type_enum,
                quantity=validation["adjusted_quantity"],
                price=market_data.price
            )
            
            return {
                "status": "success",
                "trade": trade.dict(),
                "message": f"Manual trade executed: {trade.side.value} {trade.quantity} {trade.symbol}"
            }
            
        except Exception as e:
            logger.error(f"Error executing manual trade: {e}")
            return {"status": "error", "message": str(e)}
