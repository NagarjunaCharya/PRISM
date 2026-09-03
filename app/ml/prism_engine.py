import numpy as np
import pandas as pd
from typing import Dict, List, Any
from sklearn.ensemble import IsolationForest
import logging

logger = logging.getLogger(__name__)

class PRISMEngine:
    def __init__(self):
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.is_trained = False

    def train_anomaly_detector(self, daily_counts: List[float]):
        """Trains the Isolation Forest on historical daily incident counts."""
        if len(daily_counts) < 10:
            logger.warning("Not enough data to train Isolation Forest. Needs at least 10 data points.")
            return
            
        X = np.array(daily_counts).reshape(-1, 1)
        self.anomaly_detector.fit(X)
        self.is_trained = True
        logger.info("PRISM Isolation Forest trained successfully.")

    def detect_anomalies(self, recent_counts: List[float]) -> List[bool]:
        """Detects if recent daily counts are anomalous."""
        if not self.is_trained:
            return [False] * len(recent_counts)
            
        X = np.array(recent_counts).reshape(-1, 1)
        # Returns 1 for normal, -1 for anomaly
        predictions = self.anomaly_detector.predict(X)
        
        # Convert to boolean (True = Anomaly)
        return [pred == -1 for pred in predictions]

    def forecast_risk(self, historical_data: pd.DataFrame, horizons: List[int] = [30, 60, 90]) -> Dict[str, Any]:
        """
        Generates 30, 60, and 90 day forecasts.
        In a production environment, this would use Prophet. 
        For this prototype, we use a simple exponential smoothing proxy to avoid pystan build issues.
        """
        if len(historical_data) < 30:
            return {"error": "Insufficient historical data for forecasting."}
            
        # Ensure data is sorted by date
        df = historical_data.sort_values(by='date')
        counts = df['count'].values
        
        # Simple proxy for Prophet's trend component
        # We calculate a recent trend (last 30 days) vs overall average
        recent_avg = np.mean(counts[-30:])
        overall_avg = np.mean(counts)
        trend_factor = recent_avg / overall_avg if overall_avg > 0 else 1.0
        
        forecasts = {}
        for days in horizons:
            # Projected expected incidents per day
            projected_daily = recent_avg * (1 + ((trend_factor - 1) * (days / 365.0)))
            
            # Confidence intervals
            std_dev = np.std(counts)
            
            forecasts[f"{days}d"] = {
                "horizon_days": days,
                "expected_daily_incidents": round(projected_daily, 2),
                "confidence_lower": max(0, round(projected_daily - (1.96 * std_dev), 2)),
                "confidence_upper": round(projected_daily + (1.96 * std_dev), 2),
                "trend_direction": "increasing" if trend_factor > 1.05 else ("decreasing" if trend_factor < 0.95 else "stable")
            }
            
        return forecasts

prism_engine = PRISMEngine()
