import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class TradingBotMonitor:
    """
    Trading Bot Monitor for 24/7 operation
    Monitors bot health and automatically restarts if needed
    """
    
    def __init__(self, trading_bot):
        self.trading_bot = trading_bot
        self.last_successful_cycle = datetime.now()
        self.error_count = 0
        self.max_errors = 5
        self.restart_threshold = timedelta(minutes=30)
        self.monitoring = False

    async def start_monitoring(self):
        """Start the monitoring loop"""
        if self.monitoring:
            return
        
        self.monitoring = True
        logger.info("Starting trading bot monitoring")
        
        while self.monitoring:
            try:
                await self.monitor_health()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(60)

    async def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.monitoring = False
        logger.info("Stopping trading bot monitoring")

    async def monitor_health(self):
        """Monitor bot health and restart if needed"""
        if not self.trading_bot:
            return

        try:
            if self.trading_bot.is_running:
                time_since_success = datetime.now() - self.last_successful_cycle
                
                if time_since_success > self.restart_threshold:
                    logger.warning("Bot appears unresponsive, attempting restart")
                    await self.restart_bot()
                
                try:
                    account_info = await self.trading_bot.robinhood_client.get_account()
                    if account_info:
                        self.last_successful_cycle = datetime.now()
                        self.error_count = 0
                except Exception as e:
                    self.error_count += 1
                    logger.warning(f"API health check failed: {e}")
                    
                    if self.error_count >= self.max_errors:
                        logger.error("Too many API errors, attempting restart")
                        await self.restart_bot()
            
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")

    async def restart_bot(self):
        """Restart the trading bot"""
        try:
            logger.info("Attempting to restart trading bot")
            
            if self.trading_bot.is_running:
                await self.trading_bot.stop()
                await asyncio.sleep(5)
            
            result = await self.trading_bot.start()
            
            if result.get('status') == 'success':
                self.last_successful_cycle = datetime.now()
                self.error_count = 0
                logger.info("Bot restarted successfully")
            else:
                self.error_count += 1
                logger.error(f"Bot restart failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Bot restart failed: {e}")
            
            if self.error_count >= self.max_errors:
                logger.critical("Maximum restart attempts reached, manual intervention required")

    def update_last_successful_cycle(self):
        """Update the last successful cycle timestamp"""
        self.last_successful_cycle = datetime.now()
        self.error_count = 0
