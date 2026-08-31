"""
FareGuard API - Operational Alerts Endpoints
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.repository import FareGuardRepository
from database.schemas import AlertListResponse, AlertResponse, AlertStatusEnum, RiskLevelEnum

router = APIRouter(tags=["Alerts"])


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    route_id: Optional[str] = Query(default=None),
    trip_id: Optional[str] = Query(default=None),
    risk_level: Optional[RiskLevelEnum] = Query(default=None),
    status_filter: Optional[AlertStatusEnum] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Retrieves a paginated list of explainable operational alerts with multi-dimensional filtering.
    """
    repo = FareGuardRepository(db)
    offset = (page - 1) * page_size
    alerts, total = repo.list_alerts(
        route_id=route_id,
        trip_id=trip_id,
        risk_level=risk_level.value if risk_level else None,
        status=status_filter.value if status_filter else None,
        limit=page_size,
        offset=offset,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "alerts": alerts,
    }


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
def get_alert_by_id(alert_id: str, db: Session = Depends(get_db)):
    """Retrieves full explainable alert evidence and key findings by alert ID."""
    repo = FareGuardRepository(db)
    alt = repo.get_alert(alert_id)
    if not alt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )
    return alt
