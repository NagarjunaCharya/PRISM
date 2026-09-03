import math
from typing import Dict, Any

class RiskScoringEngine:
    def __init__(self):
        # Weights as per REQ-3
        self.W_LIKELIHOOD = 0.3
        self.W_SEVERITY = 0.4
        self.W_EXPOSURE = 0.15
        self.W_PRECURSOR = 0.15

    def calculate_composite_score(self, likelihood: float, severity: float, exposure_freq: float, precursor_strength: float) -> Dict[str, Any]:
        """
        Calculates the composite risk score.
        All inputs should be normalized between 0 and 10.
        Output is a dict containing the final score (0-100) and the risk level.
        """
        # Ensure bounds for inputs
        l = max(0.0, min(10.0, likelihood))
        s = max(0.0, min(10.0, severity))
        e = max(0.0, min(10.0, exposure_freq))
        p = max(0.0, min(10.0, precursor_strength))

        # Core REQ-3 Formula
        base_score = (l * self.W_LIKELIHOOD) + (s * self.W_SEVERITY) + (e * self.W_EXPOSURE) + (p * self.W_PRECURSOR)
        
        # Scale to 0-100 and round
        final_score = round(base_score * 10, 2)
        
        # Determine classification level
        if final_score <= 30.0:
            level = "low"
        elif final_score <= 50.0:
            level = "moderate"
        elif final_score <= 70.0:
            level = "high"
        else:
            level = "critical"
            
        return {
            "risk_score": final_score,
            "risk_level": level,
            "components": {
                "likelihood_contribution": round(l * self.W_LIKELIHOOD * 10, 2),
                "severity_contribution": round(s * self.W_SEVERITY * 10, 2),
                "exposure_contribution": round(e * self.W_EXPOSURE * 10, 2),
                "precursor_contribution": round(p * self.W_PRECURSOR * 10, 2)
            }
        }

risk_engine = RiskScoringEngine()
