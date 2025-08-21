import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
from .models import MarketData, NewsItem, TechnicalIndicators
from .config import settings
import logging
from .error_logger import error_logger, ErrorType

logger = logging.getLogger(__name__)

class DataIngestor:
    """
    Data Ingestor component - fetches real-time and historical market data,
    news, and sentiment from various APIs as recommended in the research report.
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}
        self.cache_ttl = 60  # Cache for 60 seconds
        self._session_closed = False
    
    async def __aenter__(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
            self._session_closed = False
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Don't close session in context manager - keep it alive
        pass
    
    async def close(self):
        """Explicitly close the session when shutting down"""
        if self.session and not self.session.closed:
            await self.session.close()
            self._session_closed = True
    
    async def get_market_data(self, symbols: List[str]) -> List[MarketData]:
        """Fetch real-time market data from Robinhood API with CoinGecko fallback"""
        # Try Robinhood first, fallback to CoinGecko
        try:
            return await self._get_robinhood_data(symbols)
        except Exception as e:
            logger.warning(f"Robinhood API failed, falling back to CoinGecko: {e}")
            return await self._get_coingecko_data(symbols)
    
    async def _get_robinhood_data(self, symbols: List[str]) -> List[MarketData]:
        """Fetch data from Robinhood API"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
            self._session_closed = False
        
        market_data_list = []
        
        # Robinhood crypto symbol mapping
        symbol_mapping = {
            'bitcoin': 'BTC',
            'ethereum': 'ETH', 
            'cardano': 'ADA',
            'solana': 'SOL',
            'dogecoin': 'DOGE',
            'stellar': 'XLM',
            'polygon': 'MATIC'
        }
        
        headers = {
            'Authorization': f'Bearer {settings.robinhood_api_key}',
            'Content-Type': 'application/json'
        }
        
        for symbol in symbols:
            rh_symbol = symbol_mapping.get(symbol.lower(), symbol.upper())
            url = f"https://api.robinhood.com/marketdata/forex/historicals/{rh_symbol}USD/"
            params = {
                'interval': '5minute',
                'span': 'day',
                'bounds': 'extended'
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    historicals = data.get('results', [])
                    
                    if historicals:
                        # Get the most recent price data
                        latest = historicals[-1]
                        price = float(latest.get('close_price', 0))
                        volume = float(latest.get('volume', 0))
                        
                        # Calculate 24h change if we have enough data
                        change_24h = 0
                        if len(historicals) > 1:
                            prev_price = float(historicals[0].get('open_price', price))
                            if prev_price > 0:
                                change_24h = ((price - prev_price) / prev_price) * 100
                        
                        market_data_list.append(MarketData(
                            symbol=symbol.upper(),
                            price=price,
                            volume=volume,
                            change_24h=change_24h,
                            timestamp=datetime.now()
                        ))
                else:
                    logger.error(f"Failed to fetch {symbol} data: {response.status}")
        
        return market_data_list
        
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            error_logger.log_error(
                ErrorType.API_LIMIT,
                f"Robinhood API rate limit reached",
                {"error": str(e)},
                "high"
            )
        else:
            error_logger.log_error(
                ErrorType.DATA_ERROR,
                f"Error fetching market data from Robinhood: {e}",
                {"error": str(e)},
                "medium"
            )
        logger.error(f"Error fetching market data: {e}")
        return []
    
    async def _get_coingecko_data(self, symbols: List[str]) -> List[MarketData]:
        """Fallback method using CoinGecko API"""
        try:
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession()
                self._session_closed = False
            
            symbol_ids = ",".join([s.lower() for s in symbols])
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": symbol_ids,
                "vs_currencies": "usd",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    market_data = []
                    
                    for symbol in symbols:
                        symbol_lower = symbol.lower()
                        if symbol_lower in data:
                            coin_data = data[symbol_lower]
                            market_data.append(MarketData(
                                symbol=symbol.upper(),
                                price=coin_data.get("usd", 0),
                                volume=coin_data.get("usd_24h_vol", 0),
                                change_24h=coin_data.get("usd_24h_change", 0),
                                timestamp=datetime.now()
                            ))
                    
                    return market_data
                else:
                    logger.error(f"CoinGecko API failed: {response.status}")
                    return []
        
        except Exception as e:
            logger.error(f"CoinGecko fallback failed: {e}")
            return []
    
    async def get_crypto_news(self, symbols: List[str] = None, limit: int = 10) -> List[NewsItem]:
        """Fetch crypto news with sentiment analysis"""
        try:
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession()
                self._session_closed = False
            
            url = "https://newsdata.io/api/1/news"
            params = {
                "apikey": settings.newsdata_api_key or "demo_key",
                "category": "business",
                "q": "cryptocurrency OR bitcoin OR crypto",
                "language": "en",
                "size": limit
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    news_items = []
                    
                    for article in data.get("results", []):
                        sentiment = self._analyze_sentiment(article.get("title", "") + " " + article.get("description", ""))
                        
                        news_items.append(NewsItem(
                            title=article.get("title", ""),
                            content=article.get("description", ""),
                            source=article.get("source_id", ""),
                            sentiment=sentiment,
                            timestamp=datetime.fromisoformat(article.get("pubDate", datetime.now().isoformat())),
                            symbols=symbols or []
                        ))
                    
                    return news_items
                else:
                    logger.error(f"Failed to fetch news: {response.status}")
                    return []
        
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                error_logger.log_error(
                    ErrorType.API_LIMIT,
                    f"NewsData API rate limit reached",
                    {"error": str(e)},
                    "high"
                )
            else:
                error_logger.log_error(
                    ErrorType.DATA_ERROR,
                    f"Error fetching crypto news: {e}",
                    {"error": str(e)},
                    "medium"
                )
            logger.error(f"Error fetching news: {e}")
            return []
    
    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis based on keywords"""
        text_lower = text.lower()
        
        positive_words = ["bullish", "surge", "rally", "gain", "profit", "up", "rise", "positive", "growth"]
        negative_words = ["bearish", "crash", "fall", "loss", "down", "decline", "negative", "drop"]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    async def calculate_technical_indicators(self, symbol: str, period: int = 50) -> TechnicalIndicators:
        """Calculate technical indicators using historical data"""
        try:
            import yfinance as yf
            
            yahoo_symbol = f"{symbol}-USD"
            ticker = yf.Ticker(yahoo_symbol)
            
            hist = ticker.history(period="3mo")  # 3 months of data
            
            if hist.empty:
                logger.warning(f"No historical data found for {symbol}")
                return TechnicalIndicators(
                    symbol=symbol,
                    timestamp=datetime.now()
                )
            
            close_prices = hist['Close']
            
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            sma_20 = close_prices.rolling(window=20).mean()
            ema_12 = close_prices.ewm(span=12).mean()
            ema_26 = close_prices.ewm(span=26).mean()
            
            macd = ema_12 - ema_26
            macd_signal = macd.ewm(span=9).mean()
            
            return TechnicalIndicators(
                symbol=symbol,
                rsi=float(rsi.iloc[-1]) if not rsi.empty else None,
                macd=float(macd.iloc[-1]) if not macd.empty else None,
                macd_signal=float(macd_signal.iloc[-1]) if not macd_signal.empty else None,
                sma_20=float(sma_20.iloc[-1]) if not sma_20.empty else None,
                ema_12=float(ema_12.iloc[-1]) if not ema_12.empty else None,
                ema_26=float(ema_26.iloc[-1]) if not ema_26.empty else None,
                timestamp=datetime.now()
            )
        
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {e}")
            return TechnicalIndicators(
                symbol=symbol,
                timestamp=datetime.now()
            )
