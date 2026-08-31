"""
FareGuard API - Main FastAPI Application

Exposes REST API endpoints for transit network data, explainable alerts,
auditor investigations, historical analytics, live streaming, and system telemetry.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    alerts,
    analytics,
    investigations,
    live_stream,
    models_system,
    routes_trips,
    simulation,
)

app = FastAPI(
    title="FareGuard API",
    description=(
        "A Cloud-Native ML-Graph Framework for Real-Time Revenue Leakage "
        "Detection and Operational Monitoring in Public Bus Transit Systems"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Modular Routers
app.include_router(routes_trips.router)
app.include_router(alerts.router)
app.include_router(investigations.router)
app.include_router(analytics.router)
app.include_router(live_stream.router)
app.include_router(simulation.router)
app.include_router(models_system.router)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint to verify API is running."""
    return {
        "status": "healthy",
        "service": "FareGuard API",
        "version": "1.0.0",
    }


@app.get("/system/status", tags=["System"])
async def system_status():
    """Get overall system module status."""
    return {
        "api": "running",
        "version": "1.0.0",
        "modules": {
            "ingestion": "initialized",
            "graph": "initialized",
            "simulation": "initialized",
            "ml": "initialized",
            "streaming": "initialized",
            "risk": "initialized",
            "database": "initialized",
        },
    }
