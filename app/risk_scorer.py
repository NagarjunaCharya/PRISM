"""
Risk Scoring Engine
Calculates composite risk scores using the formula from REQ-3.
RiskScore = (Likelihood x 0.3 + Severity x 0.4 + ExposureFreq x 0.15 + PrecursorStrength x 0.15) x 10
"""
import numpy as np
import pandas as pd
from typing import Optional


# =============================================================================
# SEVERITY MAPPING TABLES
# =============================================================================

# Map OSHA nature codes to severity scores (0-10)
NATURE_SEVERITY = {
    # Fatal/critical
    "fatalities": 10, "death": 10,
    # Amputations
    "amputation": 9, "amputations": 9,
    # Burns
    "third degree": 8, "second degree": 6, "first degree": 3,
    "burn": 6,
    # Fractures
    "fracture": 7, "crush": 8, "concussion": 7,
    # Moderate
    "laceration": 5, "dislocation": 5, "puncture": 5,
    "sprain": 3, "strain": 3, "contusion": 3,
    # Mild
    "abrasion": 2, "bruise": 2, "soreness": 1,
}

# Event type likelihood mapping (0-10)
EVENT_LIKELIHOOD = {
    "fall": 8, "struck": 7, "caught": 8, "collapse": 9,
    "explosion": 9, "fire": 8, "electrocution": 9,
    "exposure": 6, "inhalation": 6, "contact": 5,
    "overexertion": 3, "repetitive": 2,
}

# SIF category to precursor strength mapping
SIF_PRECURSOR_STRENGTH = {
    "energy_release": 9.5,
    "caught_in_between": 9.2,
    "fall_hazard": 9.0,
    "struck_by": 8.8,
    "chemical_exposure": 8.5,
    None: 0.0,
}


class RiskScoringEngine:
    """
    Composite risk scoring engine per REQ-3.
    Combines likelihood, severity, exposure frequency, and SIF precursor strength.
    """

    def __init__(self):
        self.risk_data = None
        self._is_loaded = False

    def calculate_score(
        self,
        likelihood: float,
        severity: float,
        exposure_freq: float,
        precursor_strength: float,
    ) -> dict:
        """
        Calculate risk score using the defined formula.
        All inputs should be on 0-10 scale.
        Returns dict with score, level, and component breakdown.
        """
        raw = (
            likelihood * 0.3
            + severity * 0.4
            + exposure_freq * 0.15
            + precursor_strength * 0.15
        ) * 10

        score = round(min(max(raw, 0), 100), 1)

        if score >= 71:
            level = "critical"
        elif score >= 51:
            level = "high"
        elif score >= 31:
            level = "moderate"
        else:
            level = "low"

        return {
            "risk_score": score,
            "risk_level": level,
            "components": {
                "likelihood": {"value": round(likelihood, 2), "weight": 0.3, "contribution": round(likelihood * 0.3 * 10, 1)},
                "severity": {"value": round(severity, 2), "weight": 0.4, "contribution": round(severity * 0.4 * 10, 1)},
                "exposure_frequency": {"value": round(exposure_freq, 2), "weight": 0.15, "contribution": round(exposure_freq * 0.15 * 10, 1)},
                "precursor_strength": {"value": round(precursor_strength, 2), "weight": 0.15, "contribution": round(precursor_strength * 0.15 * 10, 1)},
            },
            "requires_human_review": score > 70,
        }

    def score_incident(self, row: dict, sif_result: Optional[dict] = None) -> dict:
        """Score a single incident using its data fields and SIF detection result."""
        # 1. Severity from injury nature
        severity = 3.0  # default moderate
        nature_title = str(row.get('NatureTitle', '')).lower()
        for keyword, sev_score in NATURE_SEVERITY.items():
            if keyword in nature_title:
                severity = max(severity, sev_score)
                break

        # Boost for hospitalization/amputation/eye loss
        if row.get('Hospitalized', 0) > 0:
            severity = max(severity, 7.0)
        if row.get('Amputation', 0) > 0:
            severity = max(severity, 9.0)
        if row.get('Loss of Eye', 0) > 0:
            severity = max(severity, 8.5)

        # 2. Likelihood from event type
        likelihood = 4.0  # default
        event_title = str(row.get('EventTitle', '')).lower()
        for keyword, lik_score in EVENT_LIKELIHOOD.items():
            if keyword in event_title:
                likelihood = max(likelihood, lik_score)
                break

        # 3. Exposure frequency (proxy from state incident density)
        exposure_freq = 5.0  # default moderate

        # 4. Precursor strength from SIF detection
        precursor_strength = 0.0
        if sif_result:
            top_cat = sif_result.get('top_category')
            precursor_strength = SIF_PRECURSOR_STRENGTH.get(top_cat, 0.0)
            # Scale by SIF overall score
            sif_score = sif_result.get('overall_score', 0)
            precursor_strength = precursor_strength * (sif_score / 100.0)

        return self.calculate_score(likelihood, severity, exposure_freq, precursor_strength)

    def batch_score(self, df: pd.DataFrame, sif_results: list = None) -> pd.DataFrame:
        """Score all incidents in a dataframe."""
        scores = []
        levels = []
        likelihood_vals = []
        severity_vals = []
        precursor_vals = []

        for i, row in df.iterrows():
            sif_result = sif_results[i] if sif_results and i < len(sif_results) else None
            result = self.score_incident(row.to_dict(), sif_result)
            scores.append(result['risk_score'])
            levels.append(result['risk_level'])
            likelihood_vals.append(result['components']['likelihood']['value'])
            severity_vals.append(result['components']['severity']['value'])
            precursor_vals.append(result['components']['precursor_strength']['value'])

        df = df.copy()
        df['risk_score'] = scores
        df['risk_level'] = levels
        df['likelihood'] = likelihood_vals
        df['severity'] = severity_vals
        df['precursor_strength'] = precursor_vals

        self.risk_data = df
        self._is_loaded = True
        return df

    def get_rankings(self, limit: int = 20) -> list:
        """Get top-N risks ranked by score (REQ-3)."""
        if not self._is_loaded:
            return []

        top = self.risk_data.nlargest(limit, 'risk_score')

        # Secondary sort by date (recency) for tied scores
        top = top.sort_values(
            ['risk_score', 'EventDate'],
            ascending=[False, False]
        )

        results = []
        for rank, (_, row) in enumerate(top.iterrows(), 1):
            results.append({
                "rank": rank,
                "incident_id": int(row.get('ID', 0)),
                "risk_score": float(row['risk_score']),
                "risk_level": row['risk_level'],
                "event_date": str(row.get('EventDate', '')),
                "employer": str(row.get('Employer', ''))[:60],
                "state": str(row.get('State', '')),
                "city": str(row.get('City', '')),
                "event_type": str(row.get('EventTitle', ''))[:80],
                "nature": str(row.get('NatureTitle', ''))[:60],
                "narrative": str(row.get('Final Narrative', ''))[:200],
                "hospitalized": bool(row.get('Hospitalized', 0) > 0),
                "amputation": bool(row.get('Amputation', 0) > 0),
                "requires_review": float(row['risk_score']) > 70,
            })

        return results

    def get_distribution(self) -> dict:
        """Get risk score distribution."""
        if not self._is_loaded:
            return {}

        scores = self.risk_data['risk_score']
        levels = self.risk_data['risk_level'].value_counts().to_dict()

        return {
            "total_scored": len(scores),
            "mean_score": round(float(scores.mean()), 1),
            "median_score": round(float(scores.median()), 1),
            "std_score": round(float(scores.std()), 1),
            "min_score": round(float(scores.min()), 1),
            "max_score": round(float(scores.max()), 1),
            "level_counts": levels,
            "histogram": {
                "bins": ["0-10", "11-20", "21-30", "31-40", "41-50",
                         "51-60", "61-70", "71-80", "81-90", "91-100"],
                "counts": [
                    int(((scores >= lo) & (scores <= hi)).sum())
                    for lo, hi in [(0,10),(11,20),(21,30),(31,40),(41,50),
                                   (51,60),(61,70),(71,80),(81,90),(91,100)]
                ],
            },
            "requiring_human_review": int((self.risk_data['risk_level'] == 'critical').sum()),
        }

    def get_heatmap(self) -> dict:
        """Get risk heatmap by state and event category."""
        if not self._is_loaded:
            return {}

        # By state
        by_state = self.risk_data.groupby('State').agg(
            avg_risk=('risk_score', 'mean'),
            max_risk=('risk_score', 'max'),
            incident_count=('ID', 'size'),
            critical_count=('risk_level', lambda x: (x == 'critical').sum()),
            high_count=('risk_level', lambda x: (x == 'high').sum()),
        ).reset_index().sort_values('avg_risk', ascending=False).head(20)

        return {
            "by_state": by_state.round(1).to_dict('records'),
        }


# Module-level instance
risk_engine = RiskScoringEngine()
