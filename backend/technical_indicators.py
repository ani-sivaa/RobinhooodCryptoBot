import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import talib

class TechnicalIndicators:
    """
    Technical indicators implementation following research paper recommendations
    Includes RSI, MACD, Moving Averages, Bollinger Bands, ADX, and OBV
    """
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        return pd.Series(talib.RSI(prices.values, timeperiod=period), index=prices.index)
    
    @staticmethod
    def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Calculate MACD indicator"""
        macd, macd_signal, macd_histogram = talib.MACD(
            prices.values, 
            fastperiod=fast, 
            slowperiod=slow, 
            signalperiod=signal
        )
        
        return {
            'macd': pd.Series(macd, index=prices.index),
            'signal': pd.Series(macd_signal, index=prices.index),
            'histogram': pd.Series(macd_histogram, index=prices.index)
        }
    
    @staticmethod
    def calculate_moving_averages(prices: pd.Series, periods: List[int] = [20, 50]) -> Dict[str, pd.Series]:
        """Calculate Simple and Exponential Moving Averages"""
        mas = {}
        for period in periods:
            mas[f'sma_{period}'] = pd.Series(talib.SMA(prices.values, timeperiod=period), index=prices.index)
            mas[f'ema_{period}'] = pd.Series(talib.EMA(prices.values, timeperiod=period), index=prices.index)
        return mas
    
    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands"""
        upper, middle, lower = talib.BBANDS(
            prices.values, 
            timeperiod=period, 
            nbdevup=std_dev, 
            nbdevdn=std_dev
        )
        
        return {
            'bb_upper': pd.Series(upper, index=prices.index),
            'bb_middle': pd.Series(middle, index=prices.index),
            'bb_lower': pd.Series(lower, index=prices.index)
        }
    
    @staticmethod
    def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index"""
        return pd.Series(talib.ADX(high.values, low.values, close.values, timeperiod=period), index=close.index)
    
    @staticmethod
    def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate On-Balance Volume"""
        return pd.Series(talib.OBV(close.values, volume.values), index=close.index)
    
    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average True Range for volatility measurement"""
        return pd.Series(talib.ATR(high.values, low.values, close.values, timeperiod=period), index=close.index)
    
    @staticmethod
    def calculate_all_indicators(
        high: pd.Series, 
        low: pd.Series, 
        close: pd.Series, 
        volume: pd.Series
    ) -> Dict[str, pd.Series]:
        """Calculate all technical indicators for a complete feature set"""
        indicators = {}
        
        indicators['rsi'] = TechnicalIndicators.calculate_rsi(close)
        
        macd_data = TechnicalIndicators.calculate_macd(close)
        indicators.update(macd_data)
        
        ma_data = TechnicalIndicators.calculate_moving_averages(close)
        indicators.update(ma_data)
        
        bb_data = TechnicalIndicators.calculate_bollinger_bands(close)
        indicators.update(bb_data)
        
        indicators['adx'] = TechnicalIndicators.calculate_adx(high, low, close)
        
        indicators['obv'] = TechnicalIndicators.calculate_obv(close, volume)
        
        indicators['atr'] = TechnicalIndicators.calculate_atr(high, low, close)
        
        return indicators
    
    @staticmethod
    def generate_signals(indicators: Dict[str, pd.Series]) -> pd.Series:
        """Generate trading signals based on technical indicators"""
        signals = pd.Series(0, index=indicators['rsi'].index)
        
        rsi_oversold = indicators['rsi'] < 30
        rsi_overbought = indicators['rsi'] > 70
        
        macd_bullish = (indicators['macd'] > indicators['signal']) & (indicators['macd'].shift(1) <= indicators['signal'].shift(1))
        macd_bearish = (indicators['macd'] < indicators['signal']) & (indicators['macd'].shift(1) >= indicators['signal'].shift(1))
        
        ma_bullish = indicators['ema_12'] > indicators['ema_26']
        ma_bearish = indicators['ema_12'] < indicators['ema_26']
        
        buy_signals = rsi_oversold & macd_bullish & ma_bullish
        sell_signals = rsi_overbought & macd_bearish & ma_bearish
        
        signals[buy_signals] = 1
        signals[sell_signals] = -1
        
        return signals
