"""
FareGuard API - Simulation & Stream Control Endpoints
"""

from typing import Any, Dict
from fastapi import APIRouter

router = APIRouter(prefix="/simulation", tags=["Simulation Control"])

_sim_state = {
    "status": "STOPPED",
    "speed_multiplier": 1.0,
    "events_generated": 0,
}


@router.get("/status")
def get_simulation_status() -> Dict[str, Any]:
    """Returns the operational simulation engine status."""
    return _sim_state


@router.post("/start")
def start_simulation() -> Dict[str, Any]:
    """Starts simulated ticket generation feed on active routes without modifying clean baseline."""
    _sim_state["status"] = "RUNNING"
    return {"message": "Simulation started successfully.", "status": _sim_state["status"]}


@router.post("/stop")
def stop_simulation() -> Dict[str, Any]:
    """Stops the active simulation feed."""
    _sim_state["status"] = "STOPPED"
    return {"message": "Simulation stopped successfully.", "status": _sim_state["status"]}
