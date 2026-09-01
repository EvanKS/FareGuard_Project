"""
FareGuard API - Auditor & Inspector Investigation Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.repository import FareGuardRepository
from database.schemas import (
    InvestigationActionEnum,
    InvestigationCreate,
    InvestigationResponse,
)

router = APIRouter(tags=["Investigations"])


@router.post(
    "/investigations/{alert_id}",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_investigation_action(
    alert_id: str,
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
):
    """
    Submits an operational auditor investigation action on an alert (e.g. CONFIRM_FOR_AUDIT, DISMISS, etc.).
    Automatically updates alert status and persists an immutable audit log trail.
    """
    repo = FareGuardRepository(db)
    alt = repo.get_alert(alert_id)
    if not alt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot investigate non-existent alert '{alert_id}'.",
        )

    inv = repo.create_investigation(
        alert_id=alert_id,
        action=payload.action.value,
        comment=payload.comment,
        investigator_id=payload.investigator_id or "inspector_demo",
    )
    return inv


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
def get_investigation_by_id(investigation_id: str, db: Session = Depends(get_db)):
    """Retrieves an investigation record by ID."""
    from database.models import InvestigationModel
    record = db.query(InvestigationModel).filter(InvestigationModel.investigation_id == investigation_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation with ID '{investigation_id}' not found.",
        )
    return record


@router.get("/investigations", response_model=List[InvestigationResponse])
def list_investigations(
    alert_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Lists recent operational investigation actions."""
    repo = FareGuardRepository(db)
    return repo.list_investigations(alert_id=alert_id, limit=limit)


@router.get("/investigations/alerts/{alert_id}/audit-log", response_model=List[dict])
def get_alert_audit_log(alert_id: str, db: Session = Depends(get_db)):
    """Retrieves the complete immutable audit trail for a specific alert."""
    repo = FareGuardRepository(db)
    alt = repo.get_alert(alert_id)
    if not alt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )
    audits = repo.list_audit_logs(entity_type="ALERT", entity_id=alert_id, limit=100)
    return [
        {
            "audit_id": a.audit_id,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "action": a.action,
            "actor": a.actor,
            "details": a.details,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in audits
    ]
