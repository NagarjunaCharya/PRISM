import os
import sys
import pytest
from datetime import datetime

# Set testing environment variable BEFORE importing anything from app
os.environ["TESTING"] = "True"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Base, engine, SessionLocal
from app.db.models import IncidentReport, RiskScore, SIFDetection, RiskLevel
from app.sif_detector import detector
from app.risk_scorer import risk_engine

@pytest.fixture(scope="module")
def db_session():
    # Create the sqlite tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up database after tests
        Base.metadata.drop_all(bind=engine)

def test_full_pipeline_ingestion(db_session):
    """
    E2E Test to verify the ingestion of an OSHA narrative through the SIF 
    engine, Risk engine, and saving successfully into the relational database.
    """
    narrative = (
        "Worker was replacing a 480V energized electrical panel breaker without locking out "
        "the high voltage power source or applying LOTO. An arc flash explosion occurred, "
        "resulting in severe electrical burns and fatal hospitalization. The worker was using "
        "an uninsulated screwdriver near live wires."
    )
    
    # 1. Run SIF Detection
    from app.sif_detector import detect_sif
    sif_res_dict = detect_sif(narrative)
    
    assert sif_res_dict["is_sif_precursor"] is True
    assert sif_res_dict["top_category"] == "energy_release"
    
    # 2. Run Risk Scoring
    # Format fake data to match the DataFrame row the risk engine expects
    mock_row = {
        "State": "TX",
        "Amputation": 0.0,
        "Hospitalized": 1.0,
        "EventTitle": "Electrical arc flash"
    }
    
    risk_res = risk_engine.score_incident(mock_row, sif_res_dict)
    risk_level = risk_res["risk_level"]
    risk_score = risk_res["risk_score"]
    
    assert risk_level in ["high", "critical"]
    
    # 3. Save to Database
    # Create parent Incident
    incident = IncidentReport(
        external_id="OSHA-TEST-999",
        source_system="OSHA",
        occurred_at=datetime.utcnow(),
        employer="Test Electric Co",
        location="Houston, TX",
        state="TX",
        event_type="Electrical arc flash",
        nature_of_injury="Severe burns",
        narrative=narrative,
        hospitalized=True,
        amputation=False
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    
    # Create SIF record
    sif_record = SIFDetection(
        incident_id=incident.id,
        is_sif_precursor=sif_res_dict["is_sif_precursor"],
        overall_score=float(sif_res_dict["overall_score"]),
        top_category=sif_res_dict["top_category"],
        severity_level=sif_res_dict["severity_level"],
        is_hospitalization=True,
        extracted_entities=sif_res_dict.get("extracted_entities", {}),
        explanation=sif_res_dict.get("explanation", "")
    )
    db_session.add(sif_record)
    
    # Create Risk record
    risk_record = RiskScore(
        incident_id=incident.id,
        overall_score=float(risk_score),
        risk_level=RiskLevel(risk_level),
        likelihood_score=75.0, # Mock component
        severity_score=90.0,
        exposure_frequency=50.0,
        precursor_strength=float(sif_res_dict["overall_score"])
    )
    db_session.add(risk_record)
    
    db_session.commit()
    
    # 4. Query the Database to verify persistence
    saved_incident = db_session.query(IncidentReport).filter_by(external_id="OSHA-TEST-999").first()
    
    assert saved_incident is not None
    assert saved_incident.sif_detection is not None
    assert saved_incident.risk_score is not None
    
    assert saved_incident.sif_detection.is_sif_precursor is True
    assert saved_incident.risk_score.risk_level.value == risk_level
    
    print("\n[SUCCESS] Pipeline executed successfully. Records saved to database.")
