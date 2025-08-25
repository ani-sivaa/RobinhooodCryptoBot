import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import yfinance as yf
from datetime import datetime, timedelta
import logging
import sqlite3
import json
from robinhood_client import RobinhoodClient

logger = logging.getLogger(__name__)

class DataManager:
    """
    Data Manager for collecting and storing market data
    Uses Robinhood API for real-time data and yfinance for historical data
    """
    
    def __init__(self, robinhood_client: RobinhoodClient, db_path: str = "trading_data.db"):
        self.robinhood_client = robinhood_client
        self.db_path = db_path
        self.init_database()
        self.symbol_mapping = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'DOGE': 'DOGE-USD',
            'LTC': 'LTC-USD',
            'BCH': 'BCH-USD'
        }
    
    def init_database(self):
        """Initialize SQLite database for storing market data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                source TEXT,
                UNIQUE(symbol, timestamp, source)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_pairs (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                base_currency TEXT,
                quote_currency TEXT,
                min_order_size REAL,
                max_order_size REAL,
                price_increment REAL,
                quantity_increment REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_trading_pairs(self) -> List[Dict]:
        """Get available trading pairs from Robinhood"""
        try:
            pairs = self.robinhood_client.get_trading_pairs()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for pair in pairs:
                cursor.execute('''
                    INSERT OR REPLACE INTO trading_pairs 
                    (id, symbol, base_currency, quote_currency, min_order_size, max_order_size, price_increment, quantity_increment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pair.get('id'),
                    pair.get('symbol'),
                    pair.get('base_currency'),
                    pair.get('quote_currency'),
                    pair.get('min_order_size'),
                    pair.get('max_order_size'),
                    pair.get('price_increment'),
                    pair.get('quantity_increment')
                ))
            
            conn.commit()
            conn.close()
            
            return pairs
        
        except Exception as e:
            logger.error(f"Error fetching trading pairs: {e}")
            return []
    
    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices from Robinhood API"""
        try:
            trading_pairs = self.get_trading_pairs()
            pair_map = {pair['symbol']: pair['id'] for pair in trading_pairs}
            
            available_symbols = [s for s in symbols if s in pair_map]
            if not available_symbols:
                return {}
            
            pair_ids = [pair_map[symbol] for symbol in available_symbols]
            price_data = self.robinhood_client.get_best_bid_ask(pair_ids)
            
            prices = {}
            for i, symbol in enumerate(available_symbols):
                if i < len(price_data):
                    bid = float(price_data[i].get('best_bid_price', 0))
                    ask = float(price_data[i].get('best_ask_price', 0))
                    prices[symbol] = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
            
            return prices
        
        except Exception as e:
            logger.error(f"Error fetching current prices: {e}")
            return {}
    
    def get_historical_data(
        self, 
        symbol: str, 
        period: str = "3mo", 
        interval: str = "1h"
    ) -> pd.DataFrame:
        """Get historical data using yfinance as fallback"""
        try:
            df = self.get_stored_data(symbol, period)
            if not df.empty and len(df) > 50:
                return df
            
            yahoo_symbol = self.symbol_mapping.get(symbol, f"{symbol}-USD")
            ticker = yf.Ticker(yahoo_symbol)
            
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                logger.warning(f"No historical data found for {symbol}")
                return pd.DataFrame()
            
            hist.columns = [col.lower() for col in hist.columns]
            hist.reset_index(inplace=True)
            
            self.store_market_data(symbol, hist, "yfinance")
            
            return hist
        
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def store_market_data(self, symbol: str, data: pd.DataFrame, source: str):
        """Store market data in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            for _, row in data.iterrows():
                conn.execute('''
                    INSERT OR REPLACE INTO market_data 
                    (symbol, timestamp, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    row.get('datetime', row.name),
                    row.get('open'),
                    row.get('high'),
                    row.get('low'),
                    row.get('close'),
                    row.get('volume'),
                    source
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing market data: {e}")
    
    def get_stored_data(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """Get stored market data from database"""
        try:
            end_date = datetime.now()
            if period == "1mo":
                start_date = end_date - timedelta(days=30)
            elif period == "3mo":
                start_date = end_date - timedelta(days=90)
            elif period == "6mo":
                start_date = end_date - timedelta(days=180)
            elif period == "1y":
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date - timedelta(days=90)
            
            conn = sqlite3.connect(self.db_path)
            
            query = '''
                SELECT timestamp, open, high, low, close, volume
                FROM market_data 
                WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp
            '''
            
            df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
            conn.close()
            
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['timestamp'])
                df.set_index('datetime', inplace=True)
            
            return df
        
        except Exception as e:
            logger.error(f"Error retrieving stored data: {e}")
            return pd.DataFrame()
    
    def update_real_time_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """Update real-time market data"""
        try:
            current_prices = self.get_current_prices(symbols)
            
            current_time = datetime.now()
            market_data = {}
            
            for symbol, price in current_prices.items():
                market_data[symbol] = {
                    'timestamp': current_time,
                    'price': price,
                    'symbol': symbol
                }
                
                data_point = pd.DataFrame([{
                    'datetime': current_time,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': 0
                }])
                
                self.store_market_data(symbol, data_point, "robinhood_realtime")
            
            return market_data
        
        except Exception as e:
            logger.error(f"Error updating real-time data: {e}")
            return {}
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol"""
        prices = self.get_current_prices([symbol])
        return prices.get(symbol)
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data from database"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'DELETE FROM market_data WHERE timestamp < ?', 
                (cutoff_date,)
            )
            
            deleted_rows = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_rows} old data records")
        
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
