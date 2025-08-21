from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel

from .trading_bot import TradingBot
from .models import StrategyConfig
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

trading_bot = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global trading_bot
    trading_bot = TradingBot()
    logger.info("Trading bot initialized")
    yield
    if trading_bot and trading_bot.is_running:
        await trading_bot.stop()
    logger.info("Trading bot stopped")

app = FastAPI(
    title="Robinhood Crypto Trading Bot API",
    description="API for automated cryptocurrency trading with Robinhood",
    version="1.0.0",
    lifespan=lifespan
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class StartBotRequest(BaseModel):
    symbols: Optional[List[str]] = None

class UpdateStrategyRequest(BaseModel):
    parameters: Optional[Dict] = None
    risk_limits: Optional[Dict] = None
    enabled: Optional[bool] = None
    name: Optional[str] = None

class ManualTradeRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    order_type: str = "market"

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/api/status")
async def get_bot_status():
    """Get current trading bot status and metrics"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        status = await trading_bot.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/start")
async def start_bot(request: StartBotRequest, background_tasks: BackgroundTasks):
    """Start the trading bot"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    if trading_bot.is_running:
        return {"status": "already_running", "message": "Trading bot is already running"}
    
    try:
        if request.symbols:
            trading_bot.update_symbols(request.symbols)
        
        background_tasks.add_task(trading_bot.start)
        
        return {
            "status": "starting",
            "message": "Trading bot is starting",
            "symbols": trading_bot.symbols,
            "paper_trading_mode": settings.paper_trading_mode
        }
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stop")
async def stop_bot():
    """Stop the trading bot"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        await trading_bot.stop()
        return {"status": "stopped", "message": "Trading bot stopped"}
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/emergency-stop")
async def emergency_stop(reason: str = "Manual emergency stop"):
    """Emergency stop the trading bot"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        result = await trading_bot.emergency_stop(reason)
        return result
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio information"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        portfolio = await trading_bot.execution_module.get_portfolio()
        return portfolio.dict()
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trades")
async def get_trade_history():
    """Get trade history"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        trades = await trading_bot.get_trade_history()
        return [trade.dict() for trade in trades]
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/strategy/update")
async def update_strategy(request: UpdateStrategyRequest):
    """Update trading strategy configuration"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        result = trading_bot.update_strategy_config(request.dict(exclude_unset=True))
        return result
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategy")
async def get_strategy_config():
    """Get current strategy configuration"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    return trading_bot.strategy_config.dict()

@app.post("/api/symbols/update")
async def update_symbols(symbols: List[str]):
    """Update the list of symbols to trade"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        result = trading_bot.update_symbols(symbols)
        return result
    except Exception as e:
        logger.error(f"Error updating symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/symbols")
async def get_symbols():
    """Get current trading symbols"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    return {"symbols": trading_bot.symbols}

@app.post("/api/trade/manual")
async def manual_trade(request: ManualTradeRequest):
    """Execute a manual trade"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        result = await trading_bot.manual_trade(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing manual trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market-data/{symbol}")
async def get_market_data(symbol: str):
    """Get current market data for a symbol"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        async with trading_bot.data_ingestor:
            market_data = await trading_bot.data_ingestor.get_market_data([symbol])
            if not market_data:
                raise HTTPException(status_code=404, detail=f"Market data not found for {symbol}")
            
            return market_data[0].dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news")
async def get_crypto_news(limit: int = 10):
    """Get latest crypto news"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        async with trading_bot.data_ingestor:
            news_items = await trading_bot.data_ingestor.get_crypto_news(
                symbols=trading_bot.symbols, 
                limit=limit
            )
            return [news.dict() for news in news_items]
    except Exception as e:
        logger.error(f"Error getting news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/{symbol}")
async def get_symbol_analysis(symbol: str):
    """Get latest analysis for a symbol"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    if symbol not in trading_bot.last_analysis:
        raise HTTPException(status_code=404, detail=f"No analysis found for {symbol}")
    
    analysis = trading_bot.last_analysis[symbol]
    return {
        "symbol": symbol,
        "market_data": analysis["market_data"].dict(),
        "technical_indicators": analysis["technical_indicators"].dict(),
        "strategy_result": analysis["strategy_result"].dict(),
        "timestamp": analysis["timestamp"].isoformat()
    }

@app.get("/api/risk-metrics")
async def get_risk_metrics():
    """Get current risk metrics"""
    if not trading_bot:
        raise HTTPException(status_code=500, detail="Trading bot not initialized")
    
    try:
        portfolio = await trading_bot.execution_module.get_portfolio()
        risk_metrics = trading_bot.risk_manager.get_risk_metrics(portfolio)
        return risk_metrics
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
