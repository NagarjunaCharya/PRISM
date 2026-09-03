"""
SIIH2026 AI Safety Implementation System — Prototype
FastAPI backend serving PRISM analytics, SIF detection, and Risk Scoring.
"""
import os
import sys
import pandas as pd
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.sif_detector import detector, detect_sif
from app.prism_analytics import prism
from app.risk_scorer import risk_engine

# Import new production routers (Phases 2-5)
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.risk import router as risk_router
from app.api.v1.explanations import router as explanations_router
from app.api.v1.governance import router as governance_router
from app.api.v1.sif import router as sif_v2_router

# =============================================================================
# APP INITIALIZATION
# =============================================================================
app = FastAPI(
    title="SIIH2026 AI Safety System",
    description="AI-powered HSE management with PRISM analytics, SIF detection, and risk scoring",
    version="0.1.0-prototype",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register new production endpoints
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
# We use /v2 for the new risk and explanations so they don't conflict with prototype v1 endpoints in main.py
app.include_router(risk_router, prefix="/api/v2/risk", tags=["risk"])
app.include_router(explanations_router, prefix="/api/v2/explanations", tags=["explanations"])
app.include_router(governance_router, prefix="/api/v1/governance", tags=["governance"])
app.include_router(sif_v2_router, prefix="/api/v2/sif", tags=["sif"])

# Global data store
DATA = {
    "df": None,
    "sif_results": [],
    "sif_summary": {},
    "loading": True,
    "load_time": 0,
}

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "cleaned", "osha_incidents.csv"
)


# =============================================================================
# STARTUP — Load data and run engines
# =============================================================================
@app.on_event("startup")
async def startup():
    """Load data and initialize all engines on startup."""
    start = time.time()
    print("\n" + "=" * 70)
    print("SIIH2026 AI SAFETY SYSTEM — Starting up...")
    print("=" * 70)

    # Load cleaned OSHA data
    print("\n[1/4] Loading cleaned OSHA incident data...")
    df = pd.read_csv(DATA_PATH, low_memory=False)
    print(f"  Loaded {len(df):,} incidents")
    DATA["df"] = df

    # Run PRISM analytics
    print("\n[2/4] Initializing PRISM analytics...")
    prism.load_data(df)

    # Run SIF detection on sample (first 20K for speed, full dataset summary)
    print("\n[3/4] Running SIF precursor detection...")
    sample_size = min(len(df), 20000)
    narratives = df['Final Narrative'].head(sample_size).tolist()

    sif_results_raw = []
    for i, text in enumerate(narratives):
        result = detect_sif(text)
        sif_results_raw.append(result)
        if (i + 1) % 5000 == 0:
            print(f"  Processed {i+1:,}/{sample_size:,} narratives...")

    DATA["sif_results"] = sif_results_raw

    # SIF summary stats
    sif_count = sum(1 for r in sif_results_raw if r['is_sif_precursor'])
    critical_count = sum(1 for r in sif_results_raw if r['severity_level'] == 'critical')
    high_count = sum(1 for r in sif_results_raw if r['severity_level'] == 'high')
    fatal_count = sum(1 for r in sif_results_raw if r['is_fatal'])

    category_counts = {}
    for r in sif_results_raw:
        if r['top_category']:
            cat = r['top_category']
            category_counts[cat] = category_counts.get(cat, 0) + 1

    DATA["sif_summary"] = {
        "total_analyzed": sample_size,
        "sif_precursors_found": sif_count,
        "sif_percentage": round(sif_count / sample_size * 100, 1),
        "critical_count": critical_count,
        "high_count": high_count,
        "fatal_indicators": fatal_count,
        "by_category": dict(sorted(category_counts.items(), key=lambda x: -x[1])),
        "severity_distribution": {
            "critical": critical_count,
            "high": high_count,
            "moderate": sum(1 for r in sif_results_raw if r['severity_level'] == 'moderate'),
            "low": sum(1 for r in sif_results_raw if r['severity_level'] == 'low'),
        },
    }
    print(f"  SIF precursors found: {sif_count:,} ({sif_count/sample_size*100:.1f}%)")

    # Run risk scoring
    print("\n[4/4] Calculating risk scores...")
    scored_df = risk_engine.batch_score(df.head(sample_size), sif_results_raw)
    DATA["scored_df"] = scored_df

    elapsed = time.time() - start
    DATA["loading"] = False
    DATA["load_time"] = round(elapsed, 1)

    print(f"\n{'=' * 70}")
    print(f"STARTUP COMPLETE in {elapsed:.1f}s")
    print(f"{'=' * 70}")
    print(f"  Dashboard: http://localhost:8000")
    print(f"  API docs:  http://localhost:8000/docs")
    print(f"{'=' * 70}\n")


# =============================================================================
# DASHBOARD
# =============================================================================
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard."""
    template_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "dashboard.html"
    )
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
    return HTMLResponse(content=html)


# =============================================================================
# API ENDPOINTS
# =============================================================================

# --- Stats ---
@app.get("/api/v1/stats")
async def get_stats():
    """Summary KPIs for the dashboard."""
    if DATA["loading"]:
        return {"status": "loading"}

    stats = prism.get_stats()
    stats["sif_summary"] = DATA["sif_summary"]
    stats["risk_distribution"] = risk_engine.get_distribution()
    stats["load_time_seconds"] = DATA["load_time"]
    return stats


# --- PRISM Analytics ---
@app.get("/api/v1/prism/trends")
async def get_trends(granularity: str = Query("monthly", enum=["daily", "weekly", "monthly"])):
    """Time-series incident trends."""
    return prism.get_trends(granularity)


@app.get("/api/v1/prism/anomalies")
async def get_anomalies(limit: int = Query(50, ge=1, le=200), model: str = Query('v4.2')):
    """Detected anomalies (Isolation Forest)."""
    return prism.get_anomalies(limit, model)


@app.get("/api/v1/prism/forecast")
async def get_forecast():
    """30/60/90 day risk forecasts."""
    return prism.get_forecasts()


# --- SIF Detection ---
class SIFDetectRequest(BaseModel):
    text: str

@app.post("/api/v1/sif/detect")
async def sif_detect(req: SIFDetectRequest):
    """Run SIF precursor detection on input text."""
    result = detect_sif(req.text)
    return result


@app.get("/api/v1/sif/summary")
async def sif_summary():
    """Pre-computed SIF detection summary."""
    return DATA.get("sif_summary", {})


# --- Risk Scoring ---
@app.get("/api/v1/risk/rankings")
async def get_rankings(limit: int = Query(20, ge=1, le=100)):
    """Top-N risk rankings."""
    return {"rankings": risk_engine.get_rankings(limit)}


@app.get("/api/v1/risk/distribution")
async def get_distribution():
    """Risk score distribution."""
    return risk_engine.get_distribution()


@app.get("/api/v1/risk/heatmap")
async def get_heatmap():
    """Risk heatmap by state."""
    return risk_engine.get_heatmap()


# --- Incidents ---
@app.get("/api/v1/incidents")
async def get_incidents(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=5, le=100),
    state: Optional[str] = None,
    risk_level: Optional[str] = None,
    search: Optional[str] = None,
):
    """Paginated incident list with risk scores."""
    if DATA.get("scored_df") is None:
        return {"incidents": [], "total": 0}

    df = DATA["scored_df"].copy()

    # Filters
    if state:
        df = df[df['State'].str.upper() == state.upper()]
    if risk_level:
        df = df[df['risk_level'] == risk_level.lower()]
    if search:
        mask = df['Final Narrative'].str.contains(search, case=False, na=False)
        df = df[mask]

    total = len(df)
    df = df.sort_values('risk_score', ascending=False)

    start = (page - 1) * per_page
    end = start + per_page
    page_df = df.iloc[start:end]

    incidents = []
    for _, row in page_df.iterrows():
        incidents.append({
            "id": int(row.get('ID', 0)),
            "event_date": str(row.get('EventDate', '')),
            "employer": str(row.get('Employer', ''))[:60],
            "state": str(row.get('State', '')),
            "city": str(row.get('City', '')),
            "risk_score": float(row.get('risk_score', 0)),
            "risk_level": str(row.get('risk_level', '')),
            "event_type": str(row.get('EventTitle', ''))[:80],
            "nature": str(row.get('NatureTitle', ''))[:60],
            "narrative": str(row.get('Final Narrative', ''))[:300],
            "hospitalized": bool(row.get('Hospitalized', 0) > 0),
            "amputation": bool(row.get('Amputation', 0) > 0),
        })

    return {
        "incidents": incidents,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


# =============================================================================
# HEALTH CHECK
# =============================================================================
@app.get("/health")
async def health():
    return {
        "status": "healthy" if not DATA["loading"] else "loading",
        "incidents_loaded": len(DATA["df"]) if DATA["df"] is not None else 0,
        "load_time": DATA["load_time"],
    }
