from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class XAIProxyService:
    """
    Proxy Explainable AI (XAI) service.
    In a full production cluster, this uses SHAP (Shapley Additive exPlanations) 
    and LIME to calculate marginal feature contributions. 
    For the prototype, it deterministically calculates the heaviest mathematical weights
    from the Risk/PRISM engines and maps them to human-readable explanations.
    """
    
    def generate_risk_explanation(self, risk_components: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Converts raw risk formula components into top contributing factors for the UI.
        """
        # Map raw component names to UI-friendly labels and descriptions
        factor_map = {
            "severity_contribution": {
                "label": "Potential Severity",
                "desc": "The incident had a high potential for severe injury or fatality."
            },
            "likelihood_contribution": {
                "label": "Likelihood of Recurrence",
                "desc": "The mathematical probability of this specific event happening again is elevated."
            },
            "exposure_contribution": {
                "label": "Exposure Frequency",
                "desc": "Workers are frequently exposed to this specific hazard."
            },
            "precursor_contribution": {
                "label": "SIF Precursor Strength",
                "desc": "The NLP model detected strong language indicating a Serious Injury or Fatality precursor."
            }
        }
        
        # Sort components by their mathematical contribution value (highest first)
        sorted_factors = sorted(risk_components.items(), key=lambda x: x[1], reverse=True)
        
        explanations = []
        for key, value in sorted_factors:
            if value > 0 and key in factor_map:
                # Calculate relative percentage
                total = sum(risk_components.values())
                percentage = (value / total) * 100 if total > 0 else 0
                
                explanations.append({
                    "factor": factor_map[key]["label"],
                    "description": factor_map[key]["desc"],
                    "contribution_score": round(value, 2),
                    "relative_impact_pct": round(percentage, 1)
                })
                
        return explanations

xai_service = XAIProxyService()
