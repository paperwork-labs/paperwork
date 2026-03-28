"""Slippage prediction ML model.

Predicts expected slippage based on order characteristics and market conditions.
Uses lightweight scikit-learn model to avoid heavy dependencies.
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

# Feature names for the model
FEATURE_NAMES = [
    "order_size_shares",
    "order_value_usd",
    "hour_of_day",
    "day_of_week",
    "is_buy",
    "is_market_order",
    "spread_at_order_pct",
    "atr_pct",
    "volume_ratio",  # Order size / avg daily volume
]


@dataclass
class SlippagePrediction:
    """Slippage prediction result."""
    predicted_slippage_pct: float
    predicted_slippage_dollars: float
    confidence: float
    recommended_limit_offset: float  # Suggested offset from current price
    features_used: Dict[str, float]


@dataclass
class TrainingResult:
    """Model training result."""
    samples_used: int
    r2_score: float
    mae: float
    feature_importances: Dict[str, float]
    trained_at: datetime


class SlippagePredictor:
    """Predicts execution slippage using ML.
    
    Features:
    - Order characteristics (size, type, side)
    - Market conditions (spread, ATR, volume)
    - Temporal features (hour, day of week)
    
    The model learns from historical filled orders to predict
    expected slippage for new orders.
    """
    
    MODEL_PATH = Path("data/models/slippage_predictor.pkl")
    
    def __init__(self, db: Session):
        self.db = db
        self._model = None
        self._scaler = None
        self._is_trained = False
    
    def predict(
        self,
        symbol: str,
        quantity: float,
        side: str,
        order_type: str = "market",
        current_price: Optional[float] = None,
        spread_pct: Optional[float] = None,
        atr_pct: Optional[float] = None,
        avg_daily_volume: Optional[float] = None,
    ) -> SlippagePrediction:
        """Predict expected slippage for an order.
        
        Args:
            symbol: Stock ticker
            quantity: Number of shares
            side: "buy" or "sell"
            order_type: "market" or "limit"
            current_price: Current stock price
            spread_pct: Current bid-ask spread as percentage
            atr_pct: ATR as percentage of price
            avg_daily_volume: Average daily volume
            
        Returns:
            SlippagePrediction with expected slippage and confidence
        """
        if not self._is_trained:
            self._load_model()
        
        # Build feature vector
        features = self._build_features(
            quantity=quantity,
            current_price=current_price,
            side=side,
            order_type=order_type,
            spread_pct=spread_pct,
            atr_pct=atr_pct,
            avg_daily_volume=avg_daily_volume,
        )
        
        feature_dict = dict(zip(FEATURE_NAMES, features))
        
        if not self._is_trained or self._model is None:
            # Return default prediction if model not trained
            default_slip = 0.05 if order_type == "market" else 0.02
            return SlippagePrediction(
                predicted_slippage_pct=default_slip,
                predicted_slippage_dollars=default_slip / 100 * (current_price or 100) * quantity,
                confidence=0.3,
                recommended_limit_offset=default_slip * 1.5,
                features_used=feature_dict,
            )
        
        # Scale features and predict
        try:
            X = np.array(features).reshape(1, -1)
            if self._scaler is not None:
                X = self._scaler.transform(X)
            
            predicted_pct = float(self._model.predict(X)[0])
            
            # Calculate dollars
            price = current_price or 100
            predicted_dollars = predicted_pct / 100 * price * quantity
            
            # Estimate confidence from model's performance
            confidence = min(0.9, max(0.4, 1 - abs(predicted_pct) / 2))
            
            # Recommend limit offset = predicted slippage + buffer
            buffer = 1.2 if side == "buy" else 1.0
            recommended_offset = abs(predicted_pct) * buffer
            
            return SlippagePrediction(
                predicted_slippage_pct=predicted_pct,
                predicted_slippage_dollars=predicted_dollars,
                confidence=confidence,
                recommended_limit_offset=recommended_offset,
                features_used=feature_dict,
            )
            
        except Exception as e:
            logger.warning("Slippage prediction failed: %s", e)
            return SlippagePrediction(
                predicted_slippage_pct=0.05,
                predicted_slippage_dollars=0.05 * (current_price or 100) * quantity / 100,
                confidence=0.2,
                recommended_limit_offset=0.1,
                features_used=feature_dict,
            )
    
    def train(
        self,
        min_samples: int = 50,
        days_lookback: int = 90,
    ) -> TrainingResult:
        """Train the slippage prediction model on historical data.
        
        Args:
            min_samples: Minimum orders required to train
            days_lookback: Days of history to use
            
        Returns:
            TrainingResult with model performance metrics
        """
        try:
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import r2_score, mean_absolute_error
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "SlippagePredictor.train() requires scikit-learn. "
                "Install with: pip install scikit-learn"
            ) from exc
        
        # Get training data
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        orders = (
            self.db.query(Order)
            .filter(
                Order.status == OrderStatus.FILLED.value,
                Order.filled_at >= cutoff,
                Order.slippage_pct.isnot(None),
                Order.decision_price.isnot(None),
            )
            .all()
        )
        
        if len(orders) < min_samples:
            logger.warning(
                "Insufficient data for training: %d samples (need %d)",
                len(orders),
                min_samples,
            )
            return TrainingResult(
                samples_used=len(orders),
                r2_score=0.0,
                mae=0.0,
                feature_importances={},
                trained_at=datetime.now(timezone.utc),
            )
        
        # Build training data
        X = []
        y = []
        
        for order in orders:
            features = self._extract_order_features(order)
            if features is not None:
                X.append(features)
                y.append(float(order.slippage_pct))
        
        if len(X) < min_samples:
            logger.warning("Not enough valid samples after feature extraction")
            return TrainingResult(
                samples_used=len(X),
                r2_score=0.0,
                mae=0.0,
                feature_importances={},
                trained_at=datetime.now(timezone.utc),
            )
        
        X = np.array(X)
        y = np.array(y)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        self._scaler = StandardScaler()
        X_train_scaled = self._scaler.fit_transform(X_train)
        X_test_scaled = self._scaler.transform(X_test)
        
        # Train model
        self._model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )
        self._model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self._model.predict(X_test_scaled)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        
        # Feature importances
        importances = dict(zip(FEATURE_NAMES, self._model.feature_importances_))
        
        self._is_trained = True
        
        # Save model
        self._save_model()
        
        logger.info(
            "Slippage model trained: %d samples, R²=%.3f, MAE=%.4f",
            len(X),
            r2,
            mae,
        )
        
        return TrainingResult(
            samples_used=len(X),
            r2_score=r2,
            mae=mae,
            feature_importances=importances,
            trained_at=datetime.now(timezone.utc),
        )
    
    def _build_features(
        self,
        quantity: float,
        current_price: Optional[float],
        side: str,
        order_type: str,
        spread_pct: Optional[float],
        atr_pct: Optional[float],
        avg_daily_volume: Optional[float],
    ) -> List[float]:
        """Build feature vector for prediction."""
        now = datetime.now(timezone.utc)
        price = current_price or 100.0
        
        return [
            float(quantity),  # order_size_shares
            float(quantity * price),  # order_value_usd
            float(now.hour),  # hour_of_day
            float(now.weekday()),  # day_of_week
            1.0 if side.lower() == "buy" else 0.0,  # is_buy
            1.0 if order_type.lower() == "market" else 0.0,  # is_market_order
            float(spread_pct or 0.1),  # spread_at_order_pct
            float(atr_pct or 2.0),  # atr_pct
            float(quantity / (avg_daily_volume or 1_000_000)),  # volume_ratio
        ]
    
    def _extract_order_features(self, order: Order) -> Optional[List[float]]:
        """Extract features from a historical order."""
        try:
            price = float(order.decision_price or order.filled_avg_price or 100)
            qty = float(order.quantity or 0)
            
            submitted = order.submitted_at or order.created_at
            if submitted is None:
                return None
            
            return [
                qty,  # order_size_shares
                qty * price,  # order_value_usd
                float(submitted.hour),  # hour_of_day
                float(submitted.weekday()),  # day_of_week
                1.0 if order.side == "buy" else 0.0,  # is_buy
                1.0 if order.order_type in ("market", "mkt") else 0.0,  # is_market_order
                float(order.spread_at_order or 0.1),  # spread_at_order_pct
                2.0,  # atr_pct (would need lookup, use default)
                0.001,  # volume_ratio (would need lookup, use default)
            ]
        except Exception as e:
            logger.debug("Failed to extract features from order %s: %s", order.id, e)
            return None
    
    def _save_model(self) -> None:
        """Save trained model to disk."""
        try:
            self.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.MODEL_PATH, "wb") as f:
                pickle.dump({
                    "model": self._model,
                    "scaler": self._scaler,
                    "trained_at": datetime.now(timezone.utc).isoformat(),
                }, f)
            logger.info("Slippage model saved to %s", self.MODEL_PATH)
        except Exception as e:
            logger.warning("Failed to save slippage model: %s", e)
    
    def _load_model(self) -> bool:
        """Load trained model from disk."""
        if not self.MODEL_PATH.exists():
            return False
        
        try:
            with open(self.MODEL_PATH, "rb") as f:
                data = pickle.load(f)
            
            self._model = data["model"]
            self._scaler = data["scaler"]
            self._is_trained = True
            logger.info("Slippage model loaded from %s", self.MODEL_PATH)
            return True
        except Exception as e:
            logger.warning("Failed to load slippage model: %s", e)
            return False


def get_slippage_prediction_dict(pred: SlippagePrediction) -> Dict[str, Any]:
    """Convert SlippagePrediction to dict for API response."""
    return {
        "predicted_slippage_pct": round(pred.predicted_slippage_pct, 4),
        "predicted_slippage_dollars": round(pred.predicted_slippage_dollars, 2),
        "confidence": round(pred.confidence, 2),
        "recommended_limit_offset": round(pred.recommended_limit_offset, 4),
        "features": pred.features_used,
    }
