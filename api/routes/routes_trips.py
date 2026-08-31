"""
FareGuard API - Routes and Trips Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import RouteModel, TripModel
from database.repository import FareGuardRepository
from database.schemas import RouteSchema, TripSchema

router = APIRouter(tags=["Transit Network"])


@router.get("/routes", response_model=List[RouteSchema])
def get_routes(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieves paginated list of monitored BMTC transit routes."""
    repo = FareGuardRepository(db)
    return repo.list_routes(limit=limit, offset=offset)


@router.get("/routes/{route_id}", response_model=RouteSchema)
def get_route_by_id(route_id: str, db: Session = Depends(get_db)):
    """Retrieves specific BMTC route metadata by route ID."""
    repo = FareGuardRepository(db)
    route = repo.get_route(route_id)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route with ID '{route_id}' not found.",
        )
    return route


@router.get("/trips/{trip_id}", response_model=TripSchema)
def get_trip_by_id(trip_id: str, db: Session = Depends(get_db)):
    """Retrieves scheduled trip information by trip ID."""
    repo = FareGuardRepository(db)
    trip = repo.get_trip(trip_id)
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trip with ID '{trip_id}' not found.",
        )
    return trip
