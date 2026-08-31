"""
FareGuard API - Models Registry & System Metrics Endpoints
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import ModelMetadataModel
from database.services import FareGuardAnalyticsService

router = APIRouter(tags=["Models & Metrics"])


@router.get("/models", response_model=List[Dict[str, Any]])
def get_model_registry(db: Session = Depends(get_db)):
    """Returns metadata, training parameters, and performance metrics for active models."""
    models = db.query(ModelMetadataModel).all()
    if not models:
        return [
            {
                "model_id": "MOD-P6-DEMAND",
                "model_name": "RandomForest Passenger Demand Regressor",
                "model_type": "DEMAND_FORECAST",
                "version": "1.0.0",
                "parameters": {"n_estimators": 100, "max_depth": 12},
                "metrics": {"test_rmse": 4.15, "test_mae": 2.92, "test_r2": 0.88},
                "active": True,
            },
            {
                "model_id": "MOD-P7-ISOLATION",
                "model_name": "Inductive Clean-Reference Isolation Forest",
                "model_type": "ANOMALY_DETECTOR",
                "version": "1.0.0",
                "parameters": {"n_estimators": 150, "contamination": 0.15},
                "metrics": {"precision": 0.3077, "recall": 0.6667, "f1_score": 0.4211},
                "active": True,
            },
        ]
    return [
        {
            "model_id": m.model_id,
            "model_name": m.model_name,
            "model_type": m.model_type,
            "version": m.version,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            "parameters": m.parameters,
            "metrics": m.metrics,
            "active": m.active,
        }
        for m in models
    ]


@router.get("/system/metrics", response_model=Dict[str, Any])
def get_system_metrics(db: Session = Depends(get_db)):
    """Returns detailed database table counts and operational health metrics."""
    service = FareGuardAnalyticsService(db)
    overview = service.get_overview_metrics()
    return {
        "status": "online",
        "database": "connected",
        "overview": overview,
    }
