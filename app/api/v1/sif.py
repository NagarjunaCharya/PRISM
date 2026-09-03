from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from app.ml.sif_nlp import sif_engine

router = APIRouter()

class IncidentNarrative(BaseModel):
    incident_id: str
    narrative: str = Field(..., min_length=10, description="The textual description of the incident.")

class SIFResult(BaseModel):
    is_sif_precursor: bool
    overall_score: float
    top_category: Optional[str] = None
    extracted_entities: Dict[str, list]
    severity_level: str

@router.post("/detect", response_model=SIFResult)
def detect_sif_precursor(incident: IncidentNarrative):
    """
    Analyzes an incident narrative to extract entities and detect Serious Injury or Fatality (SIF) precursors.
    """
    if not sif_engine.is_loaded:
        sif_engine.load_models()
        
    try:
        result = sif_engine.detect_sif_precursors(incident.narrative)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
