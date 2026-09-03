from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class RiskLevel(enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

class UserRole(enum.Enum):
    ADMIN = "admin"
    SAFETY_MANAGER = "safety_manager"
    ANALYST = "analyst"
    VIEWER = "viewer"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    reviews = relationship("HumanReview", back_populates="reviewer")

class IncidentReport(Base):
    __tablename__ = "incident_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(50), unique=True, index=True) # OSHA ID, Pipeline Seg, etc.
    source_system = Column(String(50)) # OSHA, Pipeline, WellBore
    occurred_at = Column(DateTime, index=True)
    employer = Column(String(255))
    location = Column(String(255))
    state = Column(String(50), index=True)
    event_type = Column(String(255))
    nature_of_injury = Column(String(255))
    narrative = Column(Text)
    hospitalized = Column(Boolean, default=False)
    amputation = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    risk_score = relationship("RiskScore", back_populates="incident", uselist=False)
    sif_detection = relationship("SIFDetection", back_populates="incident", uselist=False)

class RiskScore(Base):
    __tablename__ = "risk_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incident_reports.id"), unique=True)
    overall_score = Column(Float, index=True)
    risk_level = Column(Enum(RiskLevel), index=True)
    likelihood_score = Column(Float)
    severity_score = Column(Float)
    exposure_frequency = Column(Float)
    precursor_strength = Column(Float)
    calculated_at = Column(DateTime, default=datetime.utcnow)
    
    incident = relationship("IncidentReport", back_populates="risk_score")
    review = relationship("HumanReview", back_populates="risk_score", uselist=False)

class SIFDetection(Base):
    __tablename__ = "sif_detections"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incident_reports.id"), unique=True)
    is_sif_precursor = Column(Boolean, default=False, index=True)
    overall_score = Column(Float)
    top_category = Column(String(50))
    severity_level = Column(String(50))
    is_fatal = Column(Boolean, default=False)
    is_hospitalization = Column(Boolean, default=False)
    extracted_entities = Column(JSON) # JSON object of equipment, hazards, etc.
    explanation = Column(Text)
    detected_at = Column(DateTime, default=datetime.utcnow)
    
    incident = relationship("IncidentReport", back_populates="sif_detection")

class PRISMForecast(Base):
    __tablename__ = "prism_forecasts"
    
    # TimescaleDB hypertable candidate
    id = Column(Integer, primary_key=True, index=True)
    forecast_date = Column(DateTime, index=True, nullable=False)
    horizon_days = Column(Integer)
    expected_incidents = Column(Float)
    confidence_lower = Column(Float)
    confidence_upper = Column(Float)
    trend_direction = Column(String(20))
    generated_at = Column(DateTime, default=datetime.utcnow)

class PRISMRiskMetric(Base):
    __tablename__ = "prism_risk_metrics"
    
    # TimescaleDB hypertable candidate
    id = Column(Integer, primary_key=True, index=True)
    metric_date = Column(DateTime, index=True, nullable=False)
    daily_count = Column(Integer)
    rolling_7d = Column(Float)
    rolling_30d = Column(Float)
    is_anomaly = Column(Boolean, default=False, index=True)
    anomaly_score = Column(Float)
    deviation_pct = Column(Float)

class HumanReview(Base):
    __tablename__ = "human_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    risk_score_id = Column(Integer, ForeignKey("risk_scores.id"), unique=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(50)) # Pending, Approved, Overridden
    adjusted_score = Column(Float, nullable=True)
    comments = Column(Text)
    reviewed_at = Column(DateTime, default=datetime.utcnow)
    
    risk_score = relationship("RiskScore", back_populates="review")
    reviewer = relationship("User", back_populates="reviews")

class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100)) # e.g., 'SIF_NLP_BERT', 'PRISM_IsoForest'
    version = Column(String(50))
    trained_at = Column(DateTime)
    deployed_at = Column(DateTime, default=datetime.utcnow)
    metrics = Column(JSON) # e.g., {'f1': 0.92, 'precision': 0.91}
    is_active = Column(Boolean, default=False)

class AlertConfiguration(Base):
    __tablename__ = "alert_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    metric_type = Column(String(50)) # e.g., 'anomaly', 'sif_critical'
    threshold_value = Column(Float)
    notification_channels = Column(JSON) # e.g., ['email', 'slack']
    is_active = Column(Boolean, default=True)

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    configuration_id = Column(Integer, ForeignKey("alert_configurations.id"))
    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    severity = Column(String(50))
    message = Column(Text)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    
    configuration = relationship("AlertConfiguration")
