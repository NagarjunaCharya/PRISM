import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import pandas as pd
import numpy as np

from app.api.v1.sif import router as sif_router
from app.api.v1.prism import router as prism_router
from app.ml.sif_nlp import sif_engine
from app.ml.prism_engine import prism_engine

app = FastAPI()
app.include_router(sif_router, prefix="/api/v1/sif")
app.include_router(prism_router, prefix="/api/v1/prism")

client = TestClient(app)

# ----------------- SIF NLP TESTS ----------------- #

def test_sif_nlp_load():
    """Test that the NLP models load (or fallback to mock gracefully)."""
    sif_engine.load_models()
    assert sif_engine.is_loaded is True
    assert sif_engine.classifier is not None
    assert sif_engine.nlp is not None

def test_sif_endpoint():
    """Test the SIF inference endpoint with a high-risk narrative."""
    payload = {
        "incident_id": "INC-12345",
        "narrative": "A worker slipped and fell from the scaffold, hitting the ground hard."
    }
    response = client.post("/api/v1/sif/detect", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # We expect 'fall hazard' to be detected due to "fell from scaffold"
    assert "is_sif_precursor" in data
    if sif_engine.classifier == "MOCK":
        assert data["is_sif_precursor"] is True
        assert data["top_category"] == "fall hazard"
    
def test_sif_endpoint_low_risk():
    """Test the SIF inference endpoint with a low-risk narrative."""
    payload = {
        "incident_id": "INC-12346",
        "narrative": "A worker got a small paper cut while sorting documents in the office."
    }
    response = client.post("/api/v1/sif/detect", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    if sif_engine.classifier == "MOCK":
        assert data["is_sif_precursor"] is False

# ---------------- PRISM ENGINE TESTS ---------------- #

def test_prism_train_isolation_forest():
    """Test that IsolationForest trains successfully on mock data."""
    # Generate stable data (approx 5 incidents a day)
    historical_counts = np.random.normal(5, 1, 90).tolist()
    prism_engine.train_anomaly_detector(historical_counts)
    
    assert prism_engine.is_trained is True

def test_prism_detect_anomalies():
    """Test that PRISM correctly spots a huge spike in incidents."""
    # Ensure it's trained
    historical_counts = np.random.normal(5, 1, 90).tolist()
    prism_engine.train_anomaly_detector(historical_counts)
    
    # Normal days vs spike. Isolation forest contamination is 10%, so it will flag extremes.
    # To ensure 5 is normal, we must make sure it falls near the training mean of 5
    recent_counts = [5.0, 5.2, 4.8, 5.1, 25.0, 30.0] 
    anomalies = prism_engine.detect_anomalies(recent_counts)
    
    assert len(anomalies) == 6
    assert anomalies[0] is False # 5.0 should be normal
    assert anomalies[-1] is True # 30 is anomaly

def test_prism_forecast_endpoint():
    """Test that the PRISM forecasting endpoint returns valid horizons."""
    response = client.get("/api/v1/prism/forecast?horizons=30&horizons=60")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert "30d" in data["forecasts"]
    assert "60d" in data["forecasts"]
    assert "90d" not in data["forecasts"] # We only requested 30 and 60
    
    # Verify forecast structure
    assert "expected_daily_incidents" in data["forecasts"]["30d"]
    assert "confidence_lower" in data["forecasts"]["30d"]
    assert "trend_direction" in data["forecasts"]["30d"]
