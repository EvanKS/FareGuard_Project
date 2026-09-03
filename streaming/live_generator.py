"""
FareGuard - Real-Time Background Streaming Simulation Engine

Simulates realistic, continuous ticketing events across BMTC bus routes,
executes real-time ML demand forecasting, clean-reference isolation anomaly
detection, graph localization, and multi-factor risk scoring, then persists
results to the database and streams events to the live queue.
"""

from __future__ import annotations

import datetime
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional

from database.connection import get_session_factory
from database.models import RouteModel, StopModel, TripModel
from database.services import FareGuardAnalyticsService
from streaming.consumer import StreamingConsumer
from streaming.event_schema import TransitEvent

logger = logging.getLogger("FareGuardLiveGenerator")

_SAMPLE_ROUTES = [
    {"route_id": "335E", "short_name": "335E", "from_stop": "Majestic Bus Station", "to_stop": "ITPL / Hope Farm", "fare_base": 30.0},
    {"route_id": "500D", "short_name": "500D", "from_stop": "Hebbal Flyover", "to_stop": "Silk Board Junction", "fare_base": 40.0},
    {"route_id": "201R", "short_name": "201R", "from_stop": "Shivajinagar Bus Station", "to_stop": "Banashankari TTMC", "fare_base": 25.0},
    {"route_id": "G4", "short_name": "G4", "from_stop": "Brigade Road", "to_stop": "Bannerghatta National Park", "fare_base": 35.0},
    {"route_id": "3447", "short_name": "244-C", "from_stop": "KR Market", "to_stop": "Kengeri Satellite Town", "fare_base": 22.0},
]

_PAYMENT_MODES = ["CASH", "CASH", "CASH", "UPI", "UPI", "SMART_CARD", "BMTC_PASS"]


class LiveStreamGenerator:
    """Thread-safe background transit stream generator and anomaly injector."""

    _instance: Optional[LiveStreamGenerator] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.is_running: bool = False
        self.events_generated: int = 0
        self.anomalies_injected: int = 0
        self.speed_multiplier: float = 1.0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._consumer = StreamingConsumer()
        self._anomaly_spike_requested = False
        self._init_master_data()

    @classmethod
    def get_instance(cls) -> LiveStreamGenerator:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _init_master_data(self) -> None:
        """Ensures reference routes, trips, and stops exist in the database."""
        try:
            Session = get_session_factory()
            db = Session()
            try:
                for r in _SAMPLE_ROUTES:
                    route_id = r["route_id"]
                    if not db.query(RouteModel).filter(RouteModel.route_id == route_id).first():
                        db.add(RouteModel(
                            route_id=route_id,
                            route_short_name=r["short_name"],
                            route_long_name=f"{r['from_stop']} - {r['to_stop']}",
                        ))
                    trip_id = f"TRIP-{route_id}-LIVE"
                    if not db.query(TripModel).filter(TripModel.trip_id == trip_id).first():
                        db.add(TripModel(trip_id=trip_id, route_id=route_id, direction_id=0))

                    for s_name, lat, lon in [
                        (r["from_stop"], 12.9716, 77.5946),
                        (r["to_stop"], 12.9565, 77.6745),
                    ]:
                        if not db.query(StopModel).filter(StopModel.stop_id == s_name).first():
                            db.add(StopModel(stop_id=s_name, stop_name=s_name, stop_lat=lat, stop_lon=lon))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not pre-seed reference routes for streaming: {e}")

    def start(self, speed: float = 1.0) -> Dict[str, Any]:
        with self._lock:
            if self.is_running:
                return self.get_status()
            self.speed_multiplier = max(0.2, min(10.0, speed))
            self.is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("Live stream generator started.")
            return self.get_status()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self.is_running:
                return self.get_status()
            self.is_running = False
            self._stop_event.set()
            logger.info("Live stream generator stopped.")
            return self.get_status()

    def inject_anomaly_spike(self) -> Dict[str, Any]:
        """Queues an acute revenue deficit or passenger under-reporting event."""
        self._anomaly_spike_requested = True
        return {"status": "queued", "message": "Anomaly spike will be emitted on next ticketing cycle."}

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "RUNNING" if self.is_running else "STOPPED",
            "speed_multiplier": self.speed_multiplier,
            "events_generated": self.events_generated,
            "anomalies_injected": self.anomalies_injected,
            "broker_mode": "in_memory_resilient_queue",
        }

    def generate_single_event(self, force_anomaly: bool = False) -> Dict[str, Any]:
        """Generates, scores through ML intelligence chain, and persists one event."""
        route_meta = random.choice(_SAMPLE_ROUTES)
        route_id = route_meta["route_id"]
        trip_id = f"TRIP-{route_id}-LIVE"
        now = datetime.datetime.now(datetime.timezone.utc)
        service_date = now.strftime("%Y-%m-%d")

        is_anomaly = force_anomaly or (random.random() < 0.15)
        if is_anomaly:
            # Acute revenue or passenger discrepancy
            passenger_count = random.choice([0, 1])
            fare_amount = round(random.uniform(5.0, 15.0), 2)
            self.anomalies_injected += 1
        else:
            passenger_count = random.randint(2, 6)
            fare_amount = round(passenger_count * route_meta["fare_base"] * random.uniform(0.9, 1.1), 2)

        event_id = f"EVT-BMTC-{int(now.timestamp())}-{random.randint(100, 999)}"
        payment_mode = random.choice(_PAYMENT_MODES)
        device_id = f"ETM-{route_id}-{random.randint(1, 4):02d}"

        te = TransitEvent(
            event_id=event_id,
            timestamp=now.isoformat(),
            route_id=route_id,
            trip_id=trip_id,
            bus_id=f"KA-01-F-{random.randint(1000, 9999)}",
            from_stop=route_meta["from_stop"],
            to_stop=route_meta["to_stop"],
            passenger_count=passenger_count,
            fare=fare_amount / max(1, passenger_count),
            revenue=fare_amount,
            payment_mode=payment_mode,
            synthetic_flag=True,
        )

        # Run through end-to-end ML intelligence chain
        proc_res = self._consumer.process_event(te)

        # Build alert record if flagged as anomalous or high risk
        alert_dict = None
        if proc_res.is_anomaly or proc_res.risk_level in ["SUSPICIOUS", "HIGH_RISK"]:
            gap = max(0.0, proc_res.expected_revenue_inr - proc_res.reported_revenue_inr)
            import uuid
            alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
            alert_dict = {
                "alert_id": alert_id,
                "timestamp": now.isoformat(),
                "route_id": route_id,
                "trip_id": trip_id,
                "risk_level": proc_res.risk_level,
                "risk_score": proc_res.risk_score,
                "alert_title": proc_res.explanation_title or f"Passenger Volume Deficit on {route_meta['short_name']}",
                "summary": proc_res.explanation_summary or f"Reported {passenger_count} passengers vs expected {int(proc_res.expected_passengers)} passengers.",
                "affected_route": route_id,
                "affected_trip": trip_id,
                "affected_segment": f"{route_meta['from_stop']} -> {route_meta['to_stop']}",
                "estimated_revenue_impact_inr": round(gap, 2),
                "confidence": round(random.uniform(0.85, 0.96), 2),
                "recommended_action": proc_res.recommended_action or "Dispatch route inspector to cross-check conductor manifest.",
                "dominant_explanation_type": "PASSENGER_UNDERREPORTING" if is_anomaly else "NOMINAL",
                "evidence": {
                    "expected_passengers": round(proc_res.expected_passengers, 1),
                    "reported_passengers": float(passenger_count),
                    "passenger_gap": round(max(0.0, proc_res.expected_passengers - passenger_count), 1),
                    "expected_revenue": round(proc_res.expected_revenue_inr, 2),
                    "reported_revenue": float(fare_amount),
                    "observable_discrepancy": round(gap, 2),
                },
                "status": "OPEN",
            }

        # Persist event and alert to database
        try:
            Session = get_session_factory()
            db = Session()
            try:
                service = FareGuardAnalyticsService(db)
                event_dict = {
                    "event_id": event_id,
                    "timestamp": now,
                    "service_date": service_date,
                    "route_id": route_id,
                    "trip_id": trip_id,
                    "stop_id": route_meta["from_stop"],
                    "passenger_count": passenger_count,
                    "fare_amount": fare_amount,
                    "payment_mode": payment_mode,
                    "device_id": device_id,
                    "is_synthetic": True,
                }
                res_dict = {
                    "risk_score": proc_res.risk_score,
                    "risk_level": proc_res.risk_level,
                    "anomaly_score": proc_res.anomaly_score,
                    "is_anomaly": proc_res.is_anomaly,
                    "processing_latency_ms": proc_res.latency_ms,
                    "alert": alert_dict,
                }
                service.persist_streaming_result(event_dict, res_dict)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to persist live event {event_id}: {e}")

        self.events_generated += 1
        return {
            "event_id": event_id,
            "route_id": route_id,
            "route_short_name": route_meta["short_name"],
            "trip_id": trip_id,
            "passenger_count": passenger_count,
            "fare_amount": fare_amount,
            "risk_score": round(proc_res.risk_score, 2),
            "risk_level": proc_res.risk_level,
            "is_anomaly": proc_res.is_anomaly,
            "alert_id": alert_dict["alert_id"] if alert_dict else None,
            "timestamp": now.isoformat(),
        }

    def _run_loop(self) -> None:
        """Continuous background event streaming loop."""
        while not self._stop_event.is_set():
            force = False
            if self._anomaly_spike_requested:
                force = True
                self._anomaly_spike_requested = False

            try:
                self.generate_single_event(force_anomaly=force)
            except Exception as e:
                logger.error(f"Error in live stream generation cycle: {e}")

            # Base interval: ~1.0s divided by speed multiplier
            sleep_time = max(0.1, 1.0 / self.speed_multiplier)
            self._stop_event.wait(timeout=sleep_time)
