from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import os
import logging
from datetime import datetime
import asyncio
from dotenv import load_dotenv

load_dotenv()

from trading_bot import TradingBot
from monitoring import TradingBotMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Robinhood Crypto Trading Bot",
    description="Cryptocurrency trading bot using official Robinhood API with technical analysis and ML",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

trading_bot: Optional[TradingBot] = None
bot_monitor: Optional[TradingBotMonitor] = None

class BotStartRequest(BaseModel):
    symbols: Optional[List[str]] = ['BTC', 'ETH', 'DOGE', 'LTC']
    account_balance: Optional[float] = 100.0

class ManualTradeRequest(BaseModel):
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    order_type: str = "market"

class StrategyUpdateRequest(BaseModel):
    confidence_threshold: Optional[float] = None
    signal_strength_threshold: Optional[float] = None
    symbols: Optional[List[str]] = None


@app.get("/")
async def root():
    return {"message": "Robinhood Crypto Trading Bot API", "status": "running"}

@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(),
        "bot_running": trading_bot.is_running if trading_bot else False,
        "api_connected": False
    }
    
    if trading_bot:
        try:
            account_info = await trading_bot.robinhood_client.get_account()
            health_status["api_connected"] = bool(account_info)
        except:
            health_status["api_connected"] = False
    
    return health_status

@app.post("/api/bot/start")
async def start_bot(request: BotStartRequest):
    """Start the trading bot"""
    global trading_bot
    
    try:
        api_key = os.getenv("ROBINHOOD_API_KEY")
        private_key = os.getenv("ROBINHOOD_PRIVATE_KEY")
        
        if not api_key or not private_key:
            raise HTTPException(
                status_code=400, 
                detail="Robinhood API credentials not configured"
            )
        
        trading_bot = TradingBot(
            api_key=api_key,
            private_key=private_key,
            account_balance=request.account_balance,
            symbols=request.symbols
        )
        
        result = await trading_bot.start()
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        
        global bot_monitor
        if not bot_monitor:
            bot_monitor = TradingBotMonitor(trading_bot)
            asyncio.create_task(bot_monitor.start_monitoring())
        
        return result
    
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot/stop")
async def stop_bot():
    """Stop the trading bot"""
    global trading_bot
    
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        result = await trading_bot.stop()
        
        global bot_monitor
        if bot_monitor:
            await bot_monitor.stop_monitoring()
            bot_monitor = None
        
        return result
    
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bot/status")
async def get_bot_status():
    """Get current bot status"""
    if not trading_bot:
        return {"is_running": False, "message": "Bot not initialized"}
    
    try:
        return trading_bot.get_status()
    
    except Exception as e:
        logger.error(f"Failed to get bot status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot/execute-cycle")
async def execute_trading_cycle():
    """Execute one trading cycle"""
    if not trading_bot or not trading_bot.is_running:
        raise HTTPException(status_code=400, detail="Bot is not running")
    
    try:
        result = await trading_bot.execute_trading_cycle()
        
        if bot_monitor and result.get('status') == 'success':
            bot_monitor.update_last_successful_cycle()
        
        return result
    
    except Exception as e:
        logger.error(f"Trading cycle failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio information"""
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        return trading_bot.get_portfolio()
    
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trades")
async def get_trade_history(limit: int = 50):
    """Get trade history"""
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        return trading_bot.get_trade_history(limit)
    
    except Exception as e:
        logger.error(f"Failed to get trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trade/manual")
async def execute_manual_trade(request: ManualTradeRequest):
    """Execute a manual trade"""
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        result = await trading_bot.manual_trade(
            symbol=request.symbol,
            side=request.side,
            amount=request.amount,
            order_type=request.order_type
        )
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        
        return result
    
    except Exception as e:
        logger.error(f"Manual trade failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/strategy/update")
async def update_strategy(request: StrategyUpdateRequest):
    """Update strategy parameters"""
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        parameters = {}
        if request.confidence_threshold is not None:
            parameters['confidence_threshold'] = request.confidence_threshold
        if request.signal_strength_threshold is not None:
            parameters['signal_strength_threshold'] = request.signal_strength_threshold
        if request.symbols is not None:
            parameters['symbols'] = request.symbols
        
        trading_bot.strategy_engine.update_strategy_parameters(parameters)
        
        return {"status": "success", "message": "Strategy parameters updated"}
    
    except Exception as e:
        logger.error(f"Failed to update strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/model/train")
async def train_model():
    """Train or retrain the ML model"""
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        result = trading_bot.strategy_engine.train_ml_model()
        return result
    
    except Exception as e:
        logger.error(f"Model training failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/{symbol}")
async def get_market_analysis(symbol: str):
    """Get market analysis for a symbol"""
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        analysis = trading_bot.strategy_engine.analyze_market(symbol)
        return analysis
    
    except Exception as e:
        logger.error(f"Market analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/signals")
async def get_trading_signals():
    """Get current trading signals"""
    if not trading_bot:
        raise HTTPException(status_code=400, detail="Bot is not initialized")
    
    try:
        signals = trading_bot.strategy_engine.get_trading_signals()
        return {"signals": signals}
    
    except Exception as e:
        logger.error(f"Failed to get trading signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_trading_cycles():
    """Background task to run trading cycles"""
    while True:
        try:
            if trading_bot and trading_bot.is_running:
                await trading_bot.execute_trading_cycle()
            await asyncio.sleep(180)  # Run every 3 minutes
        except Exception as e:
            logger.error(f"Background trading cycle error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error

@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    logger.info("Starting Robinhood Crypto Trading Bot API")
    asyncio.create_task(run_trading_cycles())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
