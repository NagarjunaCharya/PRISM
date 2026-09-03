from fastapi import APIRouter, Query
from typing import Dict, Any, List
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

from app.ml.prism_engine import prism_engine

router = APIRouter()

def get_mock_historical_data() -> pd.DataFrame:
    """Generates 90 days of mock historical incident data for PRISM."""
    dates = [datetime.utcnow() - timedelta(days=i) for i in range(90, 0, -1)]
    # Create a baseline of 5 incidents per day, with some noise
    counts = np.random.normal(loc=5.0, scale=1.5, size=90)
    # Add a recent spike to show an increasing trend
    counts[-10:] += 3
    counts = [max(0, int(c)) for c in counts]
    
    return pd.DataFrame({"date": dates, "count": counts})

@router.get("/forecast")
def get_risk_forecast(
    horizons: List[int] = Query([30, 60, 90], description="Days to forecast")
) -> Dict[str, Any]:
    """
    Generates a predictive risk forecast for the specified horizons.
    """
    # Fetch historical data (Mocked for DB independence in prototype)
    historical_data = get_mock_historical_data()
    
    # Generate forecast
    forecast = prism_engine.forecast_risk(historical_data, horizons)
    
    return {
        "status": "success",
        "model": "Prophet (Proxy)",
        "forecasts": forecast
    }

@router.post("/anomalies/detect")
def detect_current_anomalies(
    recent_counts: List[float]
) -> Dict[str, Any]:
    """
    Checks an array of recent daily counts against the Isolation Forest to detect anomalies.
    """
    # Train if not trained
    if not prism_engine.is_trained:
        hist_df = get_mock_historical_data()
        prism_engine.train_anomaly_detector(hist_df['count'].tolist())
        
    results = prism_engine.detect_anomalies(recent_counts)
    
    return {
        "status": "success",
        "model": "IsolationForest",
        "anomalies_detected": results
    }
