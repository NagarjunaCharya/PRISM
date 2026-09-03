import pytest
from hypothesis import given, strategies as st
from app.services.risk_scoring import risk_engine

class TestRiskScoringEngine:
    """Property-based tests for Risk Scoring Engine (REQ-3)"""

    @given(
        likelihood=st.floats(min_value=0.0, max_value=10.0),
        severity=st.floats(min_value=0.0, max_value=10.0),
        exposure=st.floats(min_value=0.0, max_value=10.0),
        precursor=st.floats(min_value=0.0, max_value=10.0)
    )
    def test_risk_score_bounds(self, likelihood, severity, exposure, precursor):
        """Property: Risk score must always be between 0 and 100"""
        result = risk_engine.calculate_composite_score(
            likelihood=likelihood,
            severity=severity,
            exposure_freq=exposure,
            precursor_strength=precursor
        )
        
        score = result["risk_score"]
        assert 0.0 <= score <= 100.0, f"Score out of bounds: {score}"

    @given(
        likelihood=st.floats(min_value=-100.0, max_value=0.0),
        severity=st.floats(min_value=10.0, max_value=100.0),
        exposure=st.floats(min_value=-5.0, max_value=15.0),
        precursor=st.floats(min_value=0.0, max_value=1000.0)
    )
    def test_risk_score_clamping(self, likelihood, severity, exposure, precursor):
        """Property: Input values outside [0, 10] are clamped, and the score remains valid."""
        result = risk_engine.calculate_composite_score(
            likelihood=likelihood,
            severity=severity,
            exposure_freq=exposure,
            precursor_strength=precursor
        )
        
        score = result["risk_score"]
        assert 0.0 <= score <= 100.0, f"Score out of bounds after clamping: {score}"

    def test_risk_levels(self):
        """Test the discrete risk level classifications"""
        # Critical test
        result = risk_engine.calculate_composite_score(10, 10, 10, 10)
        assert result["risk_level"] == "critical"
        assert result["risk_score"] == 100.0

        # Low test
        result = risk_engine.calculate_composite_score(0, 0, 0, 0)
        assert result["risk_level"] == "low"
        assert result["risk_score"] == 0.0

        # High test (say around 60)
        # base_score = 6.0 -> (0.3*6) + (0.4*6) + (0.15*6) + (0.15*6) = 1.8 + 2.4 + 0.9 + 0.9 = 6.0
        # final_score = 60.0
        result = risk_engine.calculate_composite_score(6, 6, 6, 6)
        assert result["risk_level"] == "high"
        assert result["risk_score"] == 60.0

        # Moderate test (say around 40)
        result = risk_engine.calculate_composite_score(4, 4, 4, 4)
        assert result["risk_level"] == "moderate"
        assert result["risk_score"] == 40.0
