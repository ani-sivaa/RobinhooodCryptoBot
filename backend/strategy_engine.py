import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from technical_indicators import TechnicalIndicators
from ml_engine import EnsembleMLEngine
from risk_manager import RiskManager
from data_manager import DataManager

logger = logging.getLogger(__name__)

class StrategyEngine:
    """
    Trading Strategy Engine combining technical analysis with ML predictions
    Follows research paper recommendations for ensemble approach
    """
    
    def __init__(
        self, 
        data_manager: DataManager,
        risk_manager: RiskManager,
        ml_engine: EnsembleMLEngine,
        symbols: List[str] = ['BTC', 'ETH']
    ):
        self.data_manager = data_manager
        self.risk_manager = risk_manager
        self.ml_engine = ml_engine
        self.symbols = symbols
        self.active_signals = {}
        self.last_analysis_time = {}
        self.min_analysis_interval = 180  # 3 minutes
        
        self.confidence_threshold = 0.55
        self.signal_strength_threshold = 0.6
        self.lookback_period = 50
        
    def analyze_market(self, symbol: str) -> Dict[str, Any]:
        """Perform comprehensive market analysis for a symbol"""
        try:
            if self._should_skip_analysis(symbol):
                return self.active_signals.get(symbol, {})
            
            historical_data = self.data_manager.get_historical_data(symbol, period="3mo", interval="1h")
            
            if historical_data.empty or len(historical_data) < self.lookback_period:
                logger.warning(f"Insufficient data for {symbol}")
                return {}
            
            indicators = TechnicalIndicators.calculate_all_indicators(
                historical_data['high'],
                historical_data['low'],
                historical_data['close'],
                historical_data['volume']
            )
            
            technical_signals = TechnicalIndicators.generate_signals(indicators)
            
            features = self.ml_engine.prepare_features(historical_data, indicators)
            
            ml_signal = 1  # Default to hold
            ml_confidence = 0.5
            
            if self.ml_engine.is_trained and not features.empty:
                try:
                    latest_features = features.iloc[-1:].to_dict('records')[0]
                    ml_signal, ml_confidence = self.ml_engine.predict_single(latest_features)
                except Exception as e:
                    logger.warning(f"ML prediction failed for {symbol}: {e}")
            
            analysis_result = self._combine_signals(
                symbol, 
                technical_signals.iloc[-1] if not technical_signals.empty else 0,
                ml_signal,
                ml_confidence,
                indicators,
                historical_data.iloc[-1] if not historical_data.empty else None
            )
            
            self.active_signals[symbol] = analysis_result
            self.last_analysis_time[symbol] = datetime.now()
            
            return analysis_result
        
        except Exception as e:
            logger.error(f"Error analyzing market for {symbol}: {e}")
            return {}
    
    def _should_skip_analysis(self, symbol: str) -> bool:
        """Check if analysis should be skipped based on timing"""
        if symbol not in self.last_analysis_time:
            return False
        
        time_since_last = datetime.now() - self.last_analysis_time[symbol]
        return time_since_last.total_seconds() < self.min_analysis_interval
    
    def _combine_signals(
        self, 
        symbol: str,
        technical_signal: int,
        ml_signal: int,
        ml_confidence: float,
        indicators: Dict[str, pd.Series],
        latest_data: Optional[pd.Series]
    ) -> Dict[str, Any]:
        """Combine technical and ML signals into trading decision"""
        
        signal_weights = {
            'technical': 0.3,
            'ml': 0.7
        }
        
        weighted_signal = (
            technical_signal * signal_weights['technical'] + 
            ml_signal * signal_weights['ml']
        )
        
        if weighted_signal >= 1.2 and ml_confidence >= self.confidence_threshold:
            action = 'buy'
            strength = min(weighted_signal - 0.8, 1.0) * ml_confidence
        elif weighted_signal <= 0.8 and ml_confidence >= self.confidence_threshold:
            action = 'sell'
            strength = (1.2 - weighted_signal) * ml_confidence
        else:
            action = 'hold'
            strength = 0.0
        
        current_price = self.data_manager.get_latest_price(symbol)
        if current_price is None and latest_data is not None:
            current_price = latest_data['close']
        
        atr = indicators['atr'].iloc[-1] if 'atr' in indicators and not indicators['atr'].empty else 0
        
        risk_metrics = {}
        if current_price and atr > 0:
            if action == 'buy':
                stop_loss = self.risk_manager.calculate_atr_stop_loss(current_price, atr, 'buy')
                take_profit = self.risk_manager.calculate_take_profit(current_price, stop_loss, 'buy')
                position_size = self.risk_manager.calculate_position_size(current_price, stop_loss, atr)
            elif action == 'sell':
                stop_loss = self.risk_manager.calculate_atr_stop_loss(current_price, atr, 'sell')
                take_profit = self.risk_manager.calculate_take_profit(current_price, stop_loss, 'sell')
                position_size = self.risk_manager.calculate_position_size(current_price, stop_loss, atr)
            else:
                stop_loss = take_profit = position_size = 0
            
            risk_metrics = {
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'atr': atr
            }
        
        return {
            'symbol': symbol,
            'action': action,
            'strength': strength,
            'confidence': ml_confidence,
            'technical_signal': technical_signal,
            'ml_signal': ml_signal,
            'current_price': current_price,
            'timestamp': datetime.now(),
            'risk_metrics': risk_metrics,
            'indicators': {
                'rsi': indicators['rsi'].iloc[-1] if 'rsi' in indicators and not indicators['rsi'].empty else None,
                'macd': indicators['macd'].iloc[-1] if 'macd' in indicators and not indicators['macd'].empty else None,
                'macd_signal': indicators['signal'].iloc[-1] if 'signal' in indicators and not indicators['signal'].empty else None,
                'sma_20': indicators['sma_20'].iloc[-1] if 'sma_20' in indicators and not indicators['sma_20'].empty else None,
                'ema_12': indicators['ema_12'].iloc[-1] if 'ema_12' in indicators and not indicators['ema_12'].empty else None
            }
        }
    
    def get_trading_signals(self) -> List[Dict[str, Any]]:
        """Get trading signals for all symbols"""
        signals = []
        
        for symbol in self.symbols:
            signal = self.analyze_market(symbol)
            if signal and signal.get('action') != 'hold' and signal.get('strength', 0) >= self.signal_strength_threshold:
                signals.append(signal)
        
        signals.sort(key=lambda x: x.get('strength', 0), reverse=True)
        
        return signals
    
    def should_execute_trade(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """Determine if a trade should be executed based on signal and risk management"""
        if not signal or signal.get('action') == 'hold':
            return False, "No actionable signal"
        
        if signal.get('strength', 0) < self.signal_strength_threshold:
            return False, f"Signal strength too low: {signal.get('strength', 0)}"
        
        if signal.get('confidence', 0) < self.confidence_threshold:
            return False, f"Confidence too low: {signal.get('confidence', 0)}"
        
        symbol = signal['symbol']
        action = signal['action']
        current_price = signal.get('current_price', 0)
        position_size = signal.get('risk_metrics', {}).get('position_size', 0)
        
        if current_price <= 0 or position_size <= 0:
            return False, "Invalid price or position size"
        
        side = 'buy' if action == 'buy' else 'sell'
        is_valid, reason = self.risk_manager.validate_trade(symbol, side, position_size, current_price)
        
        return is_valid, reason
    
    def train_ml_model(self, retrain_hours: int = 24) -> Dict[str, Any]:
        """Train or retrain the ML model"""
        try:
            if not self.ml_engine.should_retrain(retrain_hours):
                return {'status': 'skipped', 'reason': 'Model recently trained'}
            
            logger.info("Starting ML model training...")
            
            all_features = []
            all_labels = []
            
            for symbol in self.symbols:
                historical_data = self.data_manager.get_historical_data(symbol, period="6mo", interval="1h")
                
                if historical_data.empty or len(historical_data) < 100:
                    continue
                
                indicators = TechnicalIndicators.calculate_all_indicators(
                    historical_data['high'],
                    historical_data['low'],
                    historical_data['close'],
                    historical_data['volume']
                )
                
                features = self.ml_engine.prepare_features(historical_data, indicators)
                
                labels = self.ml_engine.create_labels(historical_data['close'])
                
                common_index = features.index.intersection(labels.index)
                if len(common_index) > 50:
                    all_features.append(features.loc[common_index])
                    all_labels.append(labels.loc[common_index])
            
            if not all_features:
                return {'status': 'failed', 'reason': 'No training data available'}
            
            combined_features = pd.concat(all_features, ignore_index=True)
            combined_labels = pd.concat(all_labels, ignore_index=True)
            
            training_results = self.ml_engine.train(combined_features, combined_labels)
            
            logger.info(f"Model training completed. Accuracy: {training_results.get('accuracy', 0):.3f}")
            
            return {
                'status': 'success',
                'training_results': training_results,
                'training_samples': len(combined_features)
            }
        
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return {'status': 'failed', 'reason': str(e)}
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get current strategy status and metrics"""
        return {
            'symbols': self.symbols,
            'ml_model_trained': self.ml_engine.is_trained,
            'last_training_time': self.ml_engine.last_training_time,
            'active_signals': len(self.active_signals),
            'confidence_threshold': self.confidence_threshold,
            'signal_strength_threshold': self.signal_strength_threshold,
            'risk_metrics': self.risk_manager.get_risk_metrics()
        }
    
    def update_strategy_parameters(self, parameters: Dict[str, Any]):
        """Update strategy parameters"""
        if 'confidence_threshold' in parameters:
            self.confidence_threshold = max(0.1, min(0.9, parameters['confidence_threshold']))
        
        if 'signal_strength_threshold' in parameters:
            self.signal_strength_threshold = max(0.1, min(1.0, parameters['signal_strength_threshold']))
        
        if 'symbols' in parameters:
            self.symbols = parameters['symbols']
        
        logger.info(f"Strategy parameters updated: {parameters}")
