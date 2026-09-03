import pytest
import pandas as pd
from app.ml.fairness import fairness_auditor

def test_fairness_auditor_perfect_parity():
    """Test that perfectly balanced risk scores result in no alerts."""
    # Create synthetic dataset with identical mean risk scores across states
    data = {
        "State": ["TX", "TX", "CA", "CA", "NY", "NY"],
        "risk_score": [50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
    }
    df = pd.DataFrame(data)
    
    result = fairness_auditor.audit_geographic_parity(df)
    
    assert result["status"] == "passed"
    assert len(result["alerts"]) == 0
    assert result["global_mean_risk"] == 50.0

def test_fairness_auditor_disparity_detected():
    """Test that a state with artificially high risk scores triggers a fairness alert."""
    # TX has much higher average risk (80) than CA and NY (40)
    data = {
        "State": ["TX", "TX", "CA", "CA", "NY", "NY"],
        "risk_score": [80.0, 80.0, 40.0, 40.0, 40.0, 40.0]
    }
    df = pd.DataFrame(data)
    
    result = fairness_auditor.audit_geographic_parity(df)
    
    assert result["status"] == "failed"
    assert len(result["alerts"]) >= 1
    
    # TX should have a large positive disparity ratio
    tx_metrics = next(g for g in result["group_metrics"] if g["group"] == "TX")
    assert tx_metrics["is_disproportionate"] == True
    assert tx_metrics["disparity_ratio"] > 0.10

def test_fairness_auditor_empty_data():
    """Test behavior with empty dataset."""
    df = pd.DataFrame(columns=["State", "risk_score"])
    result = fairness_auditor.audit_geographic_parity(df)
    
    assert result["status"] == "no_data"
