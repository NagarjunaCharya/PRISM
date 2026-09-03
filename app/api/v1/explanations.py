from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

from app.ml.explainability import xai_service

router = APIRouter()

class ExplanationRequest(BaseModel):
    prediction_type: str = "risk_score" # "risk_score" or "anomaly"
    components: Dict[str, float]

class ExplanationResponse(BaseModel):
    top_factors: List[Dict[str, Any]]
    model_confidence: str = "high"
    explanation_type: str = "SHAP Proxy (Deterministic)"

@router.post("/generate", response_model=ExplanationResponse)
def generate_explanation(request: ExplanationRequest):
    """
    Generates plain-language explanations and contributing factor rankings 
    for AI predictions to satisfy Human Oversight requirements.
    """
    try:
        if request.prediction_type == "risk_score":
            factors = xai_service.generate_risk_explanation(request.components)
        else:
            raise HTTPException(status_code=400, detail="Unsupported prediction type for explanations")
            
        return {
            "top_factors": factors,
            "model_confidence": "high",
            "explanation_type": "SHAP Proxy"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")
