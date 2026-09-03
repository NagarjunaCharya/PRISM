import pandas as pd
from typing import Dict, Any, List

class FairnessAuditor:
    """
    Fairness & Bias Mitigation Service.
    Calculates demographic parity and disparate impact ratios across protected groups
    (e.g., geographic regions, job roles) to ensure the AI doesn't unfairly penalize them.
    """
    def __init__(self):
        self.DISPARITY_THRESHOLD = 0.10 # 10% maximum allowed disparity

    def audit_geographic_parity(self, df: pd.DataFrame, risk_col: str = "risk_score") -> Dict[str, Any]:
        """
        Audits risk scores by State to ensure regional fairness.
        Returns disparate impact metrics and flags any states exceeding the threshold.
        """
        if df is None or len(df) == 0:
            return {"status": "no_data"}

        # Calculate average risk score globally
        global_mean = df[risk_col].mean()

        # Calculate average risk score by state
        state_means = df.groupby("State")[risk_col].mean().to_dict()

        disparities = []
        alerts = []

        for state, mean_score in state_means.items():
            # Calculate disparity ratio
            ratio = (mean_score - global_mean) / global_mean if global_mean > 0 else 0
            
            disparity_record = {
                "group": state,
                "mean_risk_score": round(mean_score, 2),
                "disparity_ratio": round(ratio, 4),
                "is_disproportionate": bool(abs(ratio) > self.DISPARITY_THRESHOLD)
            }
            disparities.append(disparity_record)
            
            if disparity_record["is_disproportionate"]:
                alerts.append({
                    "severity": "high",
                    "message": f"Fairness Alert: State '{state}' has a risk score disparity of {ratio*100:.1f}%, exceeding the 10% threshold."
                })

        return {
            "global_mean_risk": round(global_mean, 2),
            "disparity_threshold": self.DISPARITY_THRESHOLD,
            "group_metrics": sorted(disparities, key=lambda x: abs(x["disparity_ratio"]), reverse=True),
            "alerts": alerts,
            "status": "passed" if len(alerts) == 0 else "failed"
        }

fairness_auditor = FairnessAuditor()
