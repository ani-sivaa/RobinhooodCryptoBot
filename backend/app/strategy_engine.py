from typing import List, Dict, Optional
from datetime import datetime
import logging
from .models import (
    MarketData, TechnicalIndicators, NewsItem, TradingSignal, 
    TradingStrategy, StrategyConfig
)

logger = logging.getLogger(__name__)

class StrategyEngine:
    """
    Strategy Engine component - applies trading rules to ingested data
    to generate buy/sell signals based on research report recommendations.
    """
    
    def __init__(self):
        self.strategies = {
            "momentum_rsi_macd": self._momentum_rsi_macd_strategy,
            "news_sentiment": self._news_sentiment_strategy,
            "combined": self._combined_strategy
        }
        self.default_config = StrategyConfig(
            name="momentum_rsi_macd",
            enabled=True,
            parameters={
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "macd_threshold": 0.001,
                "confidence_threshold": 0.6
            },
            risk_limits={
                "max_position_size": 0.1,  # 10% of portfolio
                "stop_loss_pct": 0.02,     # 2% stop loss
                "take_profit_pct": 0.05    # 5% take profit
            }
        )
    
    def analyze_market(
        self, 
        market_data: MarketData,
        technical_indicators: TechnicalIndicators,
        news_items: List[NewsItem] = None,
        strategy_config: StrategyConfig = None
    ) -> TradingStrategy:
        """
        Main analysis function that combines multiple strategies
        """
        config = strategy_config or self.default_config
        
        if config.name in self.strategies:
            return self.strategies[config.name](
                market_data, technical_indicators, news_items, config
            )
        else:
            logger.warning(f"Unknown strategy: {config.name}")
            return TradingStrategy(
                signal=TradingSignal.HOLD,
                confidence=0.0,
                reasoning="Unknown strategy"
            )
    
    def _momentum_rsi_macd_strategy(
        self,
        market_data: MarketData,
        technical_indicators: TechnicalIndicators,
        news_items: List[NewsItem],
        config: StrategyConfig
    ) -> TradingStrategy:
        """
        Momentum trading strategy using RSI and MACD as recommended in research report
        """
        params = config.parameters
        rsi_oversold = params.get("rsi_oversold", 30)
        rsi_overbought = params.get("rsi_overbought", 70)
        macd_threshold = params.get("macd_threshold", 0.001)
        
        signals = []
        reasoning_parts = []
        
        if technical_indicators.rsi is not None:
            if technical_indicators.rsi < rsi_oversold:
                signals.append("buy")
                reasoning_parts.append(f"RSI oversold ({technical_indicators.rsi:.2f})")
            elif technical_indicators.rsi > rsi_overbought:
                signals.append("sell")
                reasoning_parts.append(f"RSI overbought ({technical_indicators.rsi:.2f})")
            else:
                reasoning_parts.append(f"RSI neutral ({technical_indicators.rsi:.2f})")
        
        if (technical_indicators.macd is not None and 
            technical_indicators.macd_signal is not None):
            
            macd_diff = technical_indicators.macd - technical_indicators.macd_signal
            
            if macd_diff > macd_threshold:
                signals.append("buy")
                reasoning_parts.append("MACD bullish crossover")
            elif macd_diff < -macd_threshold:
                signals.append("sell")
                reasoning_parts.append("MACD bearish crossover")
            else:
                reasoning_parts.append("MACD neutral")
        
        if market_data.change_24h is not None:
            if market_data.change_24h > 5:  # Strong positive momentum
                signals.append("buy")
                reasoning_parts.append(f"Strong 24h momentum (+{market_data.change_24h:.2f}%)")
            elif market_data.change_24h < -5:  # Strong negative momentum
                signals.append("sell")
                reasoning_parts.append(f"Strong 24h decline ({market_data.change_24h:.2f}%)")
        
        buy_signals = signals.count("buy")
        sell_signals = signals.count("sell")
        
        if buy_signals > sell_signals and buy_signals >= 2:
            final_signal = TradingSignal.BUY
            confidence = min(0.9, 0.3 + (buy_signals * 0.2))
        elif sell_signals > buy_signals and sell_signals >= 2:
            final_signal = TradingSignal.SELL
            confidence = min(0.9, 0.3 + (sell_signals * 0.2))
        else:
            final_signal = TradingSignal.HOLD
            confidence = 0.1
        
        risk_limits = config.risk_limits
        max_position = risk_limits.get("max_position_size", 0.1)
        suggested_quantity = max_position * confidence if final_signal != TradingSignal.HOLD else 0
        
        stop_loss = None
        take_profit = None
        
        if final_signal == TradingSignal.BUY:
            stop_loss_pct = risk_limits.get("stop_loss_pct", 0.02)
            take_profit_pct = risk_limits.get("take_profit_pct", 0.05)
            stop_loss = market_data.price * (1 - stop_loss_pct)
            take_profit = market_data.price * (1 + take_profit_pct)
        elif final_signal == TradingSignal.SELL:
            stop_loss_pct = risk_limits.get("stop_loss_pct", 0.02)
            take_profit_pct = risk_limits.get("take_profit_pct", 0.05)
            stop_loss = market_data.price * (1 + stop_loss_pct)
            take_profit = market_data.price * (1 - take_profit_pct)
        
        return TradingStrategy(
            signal=final_signal,
            confidence=confidence,
            reasoning="; ".join(reasoning_parts),
            suggested_quantity=suggested_quantity,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    def _news_sentiment_strategy(
        self,
        market_data: MarketData,
        technical_indicators: TechnicalIndicators,
        news_items: List[NewsItem],
        config: StrategyConfig
    ) -> TradingStrategy:
        """
        News sentiment-based strategy
        """
        if not news_items:
            return TradingStrategy(
                signal=TradingSignal.HOLD,
                confidence=0.0,
                reasoning="No news data available"
            )
        
        positive_count = sum(1 for item in news_items if item.sentiment == "positive")
        negative_count = sum(1 for item in news_items if item.sentiment == "negative")
        total_count = len(news_items)
        
        if total_count == 0:
            return TradingStrategy(
                signal=TradingSignal.HOLD,
                confidence=0.0,
                reasoning="No sentiment data available"
            )
        
        positive_ratio = positive_count / total_count
        negative_ratio = negative_count / total_count
        
        if positive_ratio > 0.6:
            signal = TradingSignal.BUY
            confidence = min(0.8, positive_ratio)
            reasoning = f"Positive news sentiment ({positive_ratio:.1%})"
        elif negative_ratio > 0.6:
            signal = TradingSignal.SELL
            confidence = min(0.8, negative_ratio)
            reasoning = f"Negative news sentiment ({negative_ratio:.1%})"
        else:
            signal = TradingSignal.HOLD
            confidence = 0.2
            reasoning = f"Mixed news sentiment (pos: {positive_ratio:.1%}, neg: {negative_ratio:.1%})"
        
        return TradingStrategy(
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            suggested_quantity=0.05 * confidence if signal != TradingSignal.HOLD else 0
        )
    
    def _combined_strategy(
        self,
        market_data: MarketData,
        technical_indicators: TechnicalIndicators,
        news_items: List[NewsItem],
        config: StrategyConfig
    ) -> TradingStrategy:
        """
        Combined strategy that weighs technical and sentiment analysis
        """
        momentum_result = self._momentum_rsi_macd_strategy(
            market_data, technical_indicators, news_items, config
        )
        
        sentiment_result = self._news_sentiment_strategy(
            market_data, technical_indicators, news_items, config
        )
        
        technical_weight = 0.7
        sentiment_weight = 0.3
        
        momentum_score = 0
        sentiment_score = 0
        
        if momentum_result.signal == TradingSignal.BUY:
            momentum_score = momentum_result.confidence
        elif momentum_result.signal == TradingSignal.SELL:
            momentum_score = -momentum_result.confidence
        
        if sentiment_result.signal == TradingSignal.BUY:
            sentiment_score = sentiment_result.confidence
        elif sentiment_result.signal == TradingSignal.SELL:
            sentiment_score = -sentiment_result.confidence
        
        combined_score = (momentum_score * technical_weight + 
                         sentiment_score * sentiment_weight)
        
        if combined_score > 0.3:
            final_signal = TradingSignal.BUY
            confidence = min(0.9, abs(combined_score))
        elif combined_score < -0.3:
            final_signal = TradingSignal.SELL
            confidence = min(0.9, abs(combined_score))
        else:
            final_signal = TradingSignal.HOLD
            confidence = 0.1
        
        reasoning = f"Combined: {momentum_result.reasoning} | {sentiment_result.reasoning}"
        
        return TradingStrategy(
            signal=final_signal,
            confidence=confidence,
            reasoning=reasoning,
            suggested_quantity=0.1 * confidence if final_signal != TradingSignal.HOLD else 0,
            stop_loss=momentum_result.stop_loss,
            take_profit=momentum_result.take_profit
        )
