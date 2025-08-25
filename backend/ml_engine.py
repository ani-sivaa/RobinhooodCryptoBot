import pandas as pd
import numpy as np
from sklearn.ensemble import VotingClassifier
from sklearn.neural_network import MLPClassifier
from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from typing import Dict, List, Tuple, Optional, Any
import logging
import joblib
from datetime import datetime

logger = logging.getLogger(__name__)

class EnsembleMLEngine:
    """
    Ensemble Machine Learning Engine following research paper recommendations
    Combines XGBoost and Neural Networks for robust trading decisions
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.xgb_model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            eval_metric='logloss'
        )
        self.nn_model = MLPClassifier(
            hidden_layer_sizes=(100, 50),
            max_iter=500,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1
        )
        self.ensemble = VotingClassifier(
            estimators=[
                ('xgb', self.xgb_model),
                ('nn', self.nn_model)
            ],
            voting='soft'
        )
        self.is_trained = False
        self.feature_columns = []
        self.last_training_time = None
    
    def prepare_features(self, market_data: pd.DataFrame, indicators: Dict[str, pd.Series]) -> pd.DataFrame:
        """Prepare feature matrix from market data and technical indicators"""
        features = pd.DataFrame(index=market_data.index)
        
        features['price'] = market_data['close']
        features['volume'] = market_data['volume']
        features['high'] = market_data['high']
        features['low'] = market_data['low']
        
        features['price_change'] = market_data['close'].pct_change()
        features['volume_change'] = market_data['volume'].pct_change()
        
        for name, indicator in indicators.items():
            if isinstance(indicator, pd.Series):
                features[name] = indicator
        
        for lag in [1, 2, 3, 5]:
            features[f'price_lag_{lag}'] = features['price'].shift(lag)
            features[f'rsi_lag_{lag}'] = features['rsi'].shift(lag) if 'rsi' in features.columns else np.nan
        
        features['price_volatility'] = features['price'].rolling(window=20).std()
        features['volume_ma'] = features['volume'].rolling(window=20).mean()
        
        return features.dropna()
    
    def create_labels(self, prices: pd.Series, threshold: float = 0.02) -> pd.Series:
        """Create trading labels based on future price movements"""
        future_returns = prices.shift(-1) / prices - 1
        
        labels = pd.Series(1, index=prices.index)  # Hold
        labels[future_returns > threshold] = 2     # Buy
        labels[future_returns < -threshold] = 0    # Sell
        
        return labels
    
    def train(self, features: pd.DataFrame, labels: pd.Series) -> Dict[str, Any]:
        """Train the ensemble model"""
        try:
            features = features.replace([np.inf, -np.inf], np.nan).dropna()
            labels = labels.loc[features.index]
            
            if len(features) < 100:
                raise ValueError("Insufficient data for training (minimum 100 samples required)")
            
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, test_size=0.2, random_state=42, stratify=labels
            )
            
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            self.ensemble.fit(X_train_scaled, y_train)
            
            y_pred = self.ensemble.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            self.is_trained = True
            self.feature_columns = features.columns.tolist()
            self.last_training_time = datetime.now()
            
            logger.info(f"Model trained successfully. Accuracy: {accuracy:.3f}")
            
            return {
                'accuracy': accuracy,
                'feature_importance': self._get_feature_importance(),
                'classification_report': classification_report(y_test, y_pred, output_dict=True)
            }
        
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def predict(self, features: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions with confidence scores"""
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        features = features[self.feature_columns].fillna(0)
        
        features_scaled = self.scaler.transform(features)
        
        predictions = self.ensemble.predict(features_scaled)
        probabilities = self.ensemble.predict_proba(features_scaled)
        
        return predictions, probabilities
    
    def predict_single(self, features: Dict[str, float]) -> Tuple[int, float]:
        """Make a single prediction"""
        feature_df = pd.DataFrame([features])
        predictions, probabilities = self.predict(feature_df)
        
        prediction = predictions[0]
        confidence = np.max(probabilities[0])
        
        return prediction, confidence
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from XGBoost model"""
        if hasattr(self.xgb_model, 'feature_importances_'):
            importance_dict = {}
            for i, importance in enumerate(self.xgb_model.feature_importances_):
                if i < len(self.feature_columns):
                    importance_dict[self.feature_columns[i]] = float(importance)
            return importance_dict
        return {}
    
    def save_model(self, filepath: str):
        """Save the trained model"""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        model_data = {
            'ensemble': self.ensemble,
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'last_training_time': self.last_training_time
        }
        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model"""
        try:
            model_data = joblib.load(filepath)
            self.ensemble = model_data['ensemble']
            self.scaler = model_data['scaler']
            self.feature_columns = model_data['feature_columns']
            self.last_training_time = model_data['last_training_time']
            self.is_trained = True
            logger.info(f"Model loaded from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def should_retrain(self, hours_threshold: int = 24) -> bool:
        """Check if model should be retrained based on time"""
        if not self.is_trained or not self.last_training_time:
            return True
        
        hours_since_training = (datetime.now() - self.last_training_time).total_seconds() / 3600
        return hours_since_training > hours_threshold
