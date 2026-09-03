from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any

from app.services.risk_scoring import risk_engine

router = APIRouter()

class RiskCalculationRequest(BaseModel):
    likelihood: float = Field(..., ge=0, le=10, description="Likelihood of recurrence (0-10)")
    severity: float = Field(..., ge=0, le=10, description="Potential severity (0-10)")
    exposure_frequency: float = Field(..., ge=0, le=10, description="Exposure frequency (0-10)")
    precursor_strength: float = Field(..., ge=0, le=10, description="SIF precursor strength (0-10)")

class RiskCalculationResponse(BaseModel):
    risk_score: float
    risk_level: str
    components: Dict[str, float]

@router.post("/calculate", response_model=RiskCalculationResponse)
def calculate_risk(request: RiskCalculationRequest):
    """
    Calculates the composite risk score (0-100) based on Likelihood, Severity, 
    Exposure Frequency, and Precursor Strength.
    """
    try:
        result = risk_engine.calculate_composite_score(
            likelihood=request.likelihood,
            severity=request.severity,
            exposure_freq=request.exposure_frequency,
            precursor_strength=request.precursor_strength
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk calculation failed: {str(e)}")
