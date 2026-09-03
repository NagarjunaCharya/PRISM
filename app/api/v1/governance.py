from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import pandas as pd

from app.ml.fairness import fairness_auditor
from app.ml.drift_monitor import drift_monitor

router = APIRouter()

class FairnessResponse(BaseModel):
    global_mean_risk: float
    disparity_threshold: float
    group_metrics: List[Dict[str, Any]]
    alerts: List[Dict[str, str]]
    status: str

@router.get("/fairness-metrics", response_model=FairnessResponse)
def get_fairness_metrics():
    """
    Returns demographic parity and fairness metrics. 
    Audits the risk scores to ensure no geographic region is disproportionately penalized.
    """
    try:
        from app.main import DATA
        df = DATA.get("scored_df")
        if df is None:
            # Fallback for testing or before startup completes
            return {
                "global_mean_risk": 0.0,
                "disparity_threshold": 0.1,
                "group_metrics": [],
                "alerts": [],
                "status": "no_data"
            }
            
        result = fairness_auditor.audit_geographic_parity(df)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fairness audit failed: {str(e)}")


@router.get("/drift-metrics")
def get_drift_metrics():
    """
    Returns statistical drift metrics (proxy for Evidently AI).
    Monitors if recent risk scores diverge from the historical baseline.
    """
    from app.main import DATA
    df = DATA.get("scored_df")
    if df is None or df.empty:
        return {"status": "no_data"}
    try:
        return drift_monitor.detect_prediction_drift()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drift detection failed: {str(e)}")
