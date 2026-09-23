"""
FareGuard Database Initialization & Seed Script

Initializes all database tables and populates base routes, stops, trips,
risk scores, and alerts from verified project data layers.
"""

import ast
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from database.connection import create_db_engine, get_session_factory, init_db, reset_db
from database.models import (
    AlertModel,
    ModelMetadataModel,
    RiskScoreModel,
    RouteModel,
    StopModel,
    TicketEventModel,
    TripModel,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_database(db: Session, max_routes: int = 500, max_stops: int = 1000, max_trips: int = 2000):
    """Populates database with structured GTFS metadata and Phase 9/10 operational results."""
    logger.info("--- 1. Seeding Transit Network (Routes, Stops, Trips) ---")

    # Load Routes
    routes_csv = settings.PROCESSED_DATA_DIR / "routes.csv"
    if routes_csv.exists():
        routes_df = pd.read_csv(routes_csv, dtype=str).head(max_routes)
        route_objs = [
            RouteModel(
                route_id=str(row["route_id"]),
                route_short_name=str(row.get("route_short_name", row["route_id"])),
                route_long_name=str(row.get("route_long_name", "")),
                route_type=int(row.get("route_type", 3)),
            )
            for _, row in routes_df.iterrows()
        ]
        db.bulk_save_objects(route_objs)
        db.commit()
        logger.info(f"Inserted {len(route_objs)} routes into database.")

    # Load Stops
    stops_csv = settings.PROCESSED_DATA_DIR / "stops.csv"
    if stops_csv.exists():
        stops_df = pd.read_csv(stops_csv, dtype={"stop_id": str}).head(max_stops)
        stop_objs = [
            StopModel(
                stop_id=str(row["stop_id"]),
                stop_name=str(row.get("stop_name", f"Stop {row['stop_id']}")),
                stop_lat=float(row["stop_lat"]),
                stop_lon=float(row["stop_lon"]),
            )
            for _, row in stops_df.iterrows()
        ]
        db.bulk_save_objects(stop_objs)
        db.commit()
        logger.info(f"Inserted {len(stop_objs)} stops into database.")

    # Load Trips
    trips_csv = settings.PROCESSED_DATA_DIR / "trips.csv"
    if trips_csv.exists():
        trips_df = pd.read_csv(trips_csv, dtype=str).head(max_trips)
        # Filter trips whose routes exist
        valid_route_ids = set(r.route_id for r in db.query(RouteModel.route_id).all())
        valid_trips = trips_df[trips_df["route_id"].isin(valid_route_ids)]

        trip_objs = [
            TripModel(
                trip_id=str(row["trip_id"]),
                route_id=str(row["route_id"]),
                service_id=str(row.get("service_id", "1")),
                direction_id=int(row.get("direction_id", 0)),
            )
            for _, row in valid_trips.iterrows()
        ]
        db.bulk_save_objects(trip_objs)
        db.commit()
        logger.info(f"Inserted {len(trip_objs)} trips into database.")

    logger.info("--- 2. Seeding Risk Scores (Phase 9) ---")
    risk_csv = settings.SYNTHETIC_DATA_DIR / "trip_risk_scores.csv"
    if risk_csv.exists():
        risk_df = pd.read_csv(risk_csv)
        # Ensure parent routes and trips exist
        existing_routes = set(r.route_id for r in db.query(RouteModel.route_id).all())
        existing_trips = set(t.trip_id for t in db.query(TripModel.trip_id).all())

        risk_objs = []
        for idx, row in risk_df.iterrows():
            r_id = str(row["route_id"])
            t_id = str(row["trip_id"])
            if r_id not in existing_routes:
                r_obj = RouteModel(route_id=r_id, route_short_name=r_id, route_long_name=f"Route {r_id}")
                db.add(r_obj)
                existing_routes.add(r_id)
            if t_id not in existing_trips:
                t_obj = TripModel(trip_id=t_id, route_id=r_id)
                db.add(t_obj)
                existing_trips.add(t_id)

            db.commit()

            factors = ast.literal_eval(row["risk_factors"]) if isinstance(row.get("risk_factors"), str) else row.get("risk_factors", {})
            reasons = ast.literal_eval(row["risk_reasons"]) if isinstance(row.get("risk_reasons"), str) else row.get("risk_reasons", [])

            risk_objs.append(
                RiskScoreModel(
                    risk_id=f"RSK-{idx+1:05d}",
                    trip_id=t_id,
                    route_id=r_id,
                    service_date=str(row.get("service_date", "2026-08-31")),
                    risk_score=float(row["risk_score"]),
                    risk_level=str(row["risk_level"]),
                    estimated_revenue_impact_inr=float(row.get("estimated_revenue_impact_inr", 0.0)),
                    risk_factors=factors,
                    risk_reasons=reasons,
                    engine_version="1.0.0",
                )
            )
        db.bulk_save_objects(risk_objs)
        db.commit()
        logger.info(f"Inserted {len(risk_objs)} risk score records.")

    logger.info("--- 3. Seeding Generated Alerts (Phase 10) ---")
    alerts_csv = settings.SYNTHETIC_DATA_DIR / "generated_alerts.csv"
    if alerts_csv.exists():
        alerts_df = pd.read_csv(alerts_csv)
        alert_objs = []
        for _, row in alerts_df.iterrows():
            findings = ast.literal_eval(row["key_findings"]) if isinstance(row.get("key_findings"), str) else row.get("key_findings", [])
            evidence = ast.literal_eval(row["evidence"]) if isinstance(row.get("evidence"), str) else row.get("evidence", {})

            alert_objs.append(
                AlertModel(
                    alert_id=str(row["alert_id"]),
                    timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                    route_id=str(row["route_id"]),
                    trip_id=str(row["trip_id"]),
                    risk_level=str(row["risk_level"]),
                    risk_score=float(row["risk_score"]),
                    alert_title=str(row["alert_title"]),
                    summary=str(row["summary"]),
                    key_findings=findings,
                    evidence=evidence,
                    affected_route=str(row.get("affected_route", row["route_id"])),
                    affected_trip=str(row.get("affected_trip", row["trip_id"])),
                    affected_segment=str(row.get("affected_segment")) if pd.notna(row.get("affected_segment")) else None,
                    estimated_revenue_impact_inr=float(row.get("estimated_revenue_impact_inr", 0.0)),
                    confidence=float(row.get("confidence", 0.0)),
                    recommended_action=str(row.get("recommended_action", "")),
                    dominant_explanation_type=str(row.get("dominant_explanation_type", "NOMINAL")),
                    status=str(row.get("status", "OPEN")),
                    version="1.0.0",
                )
            )
        db.bulk_save_objects(alert_objs)
        db.commit()
        logger.info(f"Inserted {len(alert_objs)} alert records.")

    # Seed ticket events (Phase 4 / Phase 11 telemetry)
    tickets_csv = settings.SYNTHETIC_DATA_DIR / "tickets.csv"
    if tickets_csv.exists():
        logger.info("--- 4. Seeding Ticket Events Telemetry ---")
        tkt_df = pd.read_csv(tickets_csv).head(2000)
        existing_routes = set(r.route_id for r in db.query(RouteModel.route_id).all())
        existing_trips = set(t.trip_id for t in db.query(TripModel.trip_id).all())
        existing_stops = set(s.stop_id for s in db.query(StopModel.stop_id).all())

        event_objs = []
        for idx, row in tkt_df.iterrows():
            r_id = str(row["route_id"])
            t_id = str(row["trip_id"])
            s_id = str(row.get("origin_stop_id", ""))

            if r_id not in existing_routes:
                db.add(RouteModel(route_id=r_id, route_short_name=r_id, route_long_name=f"Route {r_id}"))
                existing_routes.add(r_id)
            if t_id not in existing_trips:
                db.add(TripModel(trip_id=t_id, route_id=r_id))
                existing_trips.add(t_id)
            if s_id and s_id not in existing_stops:
                db.add(StopModel(stop_id=s_id, stop_name=str(row.get("origin_stop_name", s_id)), stop_lat=12.9716, stop_lon=77.5946))
                existing_stops.add(s_id)

            t_val = row.get("timestamp")
            t_dt = pd.to_datetime(t_val).to_pydatetime() if pd.notna(t_val) else datetime.now(timezone.utc)

            event_objs.append(
                TicketEventModel(
                    event_id=str(row.get("ticket_id", f"EVT-{idx+1:06d}")),
                    timestamp=t_dt,
                    service_date=str(t_val)[:10] if pd.notna(t_val) else "2026-08-31",
                    route_id=r_id,
                    trip_id=t_id,
                    stop_id=s_id if s_id in existing_stops else None,
                    passenger_count=int(row.get("passenger_count", 1)),
                    fare_amount=float(row.get("total_amount_inr", row.get("fare_inr", 15.0))),
                    payment_mode=str(row.get("payment_mode", "CASH")).upper(),
                    device_id=f"ETM-{r_id}-01",
                    is_synthetic=True,
                )
            )

        db.commit()
        db.bulk_save_objects(event_objs)
        db.commit()
        logger.info(f"Inserted {len(event_objs)} ticket events.")

    # Seed model metadata
    model_entries = [
        ModelMetadataModel(
            model_id="MOD-P6-DEMAND",
            model_name="RandomForest Passenger Demand Regressor",
            model_type="DEMAND_FORECAST",
            version="1.0.0",
            parameters={"n_estimators": 100, "max_depth": 12, "random_state": 42},
            metrics={"test_rmse": 4.15, "test_mae": 2.92, "test_r2": 0.88},
            active=True,
        ),
        ModelMetadataModel(
            model_id="MOD-P7-ISOLATION",
            model_name="Inductive Clean-Reference Isolation Forest",
            model_type="ANOMALY_DETECTOR",
            version="1.0.0",
            parameters={"n_estimators": 150, "contamination": 0.15, "random_state": 42},
            metrics={"precision": 0.3077, "recall": 0.6667, "f1_score": 0.4211},
            active=True,
        ),
    ]
    db.bulk_save_objects(model_entries)
    db.commit()
    logger.info(f"Inserted {len(model_entries)} model metadata records.")


def main():
    logger.info("=" * 60)
    logger.info("FAREGUARD - DATABASE INITIALIZATION")
    logger.info("=" * 60)

    # Reset and initialize tables
    reset_db()
    SessionFactory = get_session_factory()
    db = SessionFactory()

    try:
        seed_database(db)
        logger.info("\n--- DATABASE SUMMARY ---")
        for model in [RouteModel, StopModel, TripModel, RiskScoreModel, AlertModel, ModelMetadataModel]:
            count = db.query(func.count(model.__table__.primary_key.columns.values()[0])).scalar()
            logger.info(f"Table '{model.__tablename__}': {count:,} rows")
        logger.info("Database initialized successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
