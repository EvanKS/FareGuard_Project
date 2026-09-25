"""
FareGuard API - Simulation & Stream Control Endpoints
"""

from typing import Any, Dict
from fastapi import APIRouter, Query
from streaming.live_generator import LiveStreamGenerator

router = APIRouter(prefix="/simulation", tags=["Simulation Control"])


@router.get("/status")
def get_simulation_status() -> Dict[str, Any]:
    """Returns the operational simulation engine status."""
    gen = LiveStreamGenerator.get_instance()
    return gen.get_status()


@router.post("/start")
def start_simulation(speed: float = Query(default=1.0, ge=0.1, le=10.0)) -> Dict[str, Any]:
    """Starts simulated ticket generation feed on active routes without modifying clean baseline."""
    gen = LiveStreamGenerator.get_instance()
    status = gen.start(speed=speed)
    return {"message": "Simulation started successfully.", "status": status["status"], "details": status}


@router.post("/stop")
def stop_simulation() -> Dict[str, Any]:
    """Stops the active simulation feed."""
    gen = LiveStreamGenerator.get_instance()
    status = gen.stop()
    return {"message": "Simulation stopped successfully.", "status": status["status"], "details": status}


@router.post("/inject-anomaly")
def inject_anomaly() -> Dict[str, Any]:
    """Queues an acute revenue/passenger discrepancy spike into the active stream."""
    gen = LiveStreamGenerator.get_instance()
    return gen.inject_anomaly_spike()


@router.post("/step")
def step_simulation() -> Dict[str, Any]:
    """Generates a single immediate transaction through the ML pipeline."""
    gen = LiveStreamGenerator.get_instance()
    return gen.generate_single_event()
