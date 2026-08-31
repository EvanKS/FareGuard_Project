"""
FareGuard Operational Risk Scoring CLI Runner

Loads Phase 7 anomaly detection outputs and Phase 8 graph localization outputs,
executes Phase 9 multi-factor operational risk scoring, and persists structured results.
"""

import argparse
from dataclasses import asdict
import json
import logging
import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.localization import LocalizedLeakagePath
from graph.transit_graph import TransitNetworkGraph
from ml.anomaly_detector import IsolationForestAnomalyDetector, extract_anomaly_features
from ml.demand_predictor import MLPassengerDemandModel, extract_trip_features
from risk.risk_engine import RiskAssessment, RiskLevel, RiskScoringEngine, RiskThresholdsConfig, RiskWeightsConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="FareGuard Operational Risk Scoring Engine")
    parser.add_argument("--version", type=str, default="1.0.0", help="Risk model version")
    args = parser.parse_args()

    synth_dir = settings.SYNTHETIC_DATA_DIR
    anom_trips_path = synth_dir / "anomalous_trip_summaries.csv"
    loc_path = synth_dir / "localized_anomalies.csv"

    if not anom_trips_path.exists():
        logger.error(f"Input operational telemetry not found: {anom_trips_path}")
        return 1

    logger.info("=" * 75)
    logger.info("FareGuard Operational Risk Scoring Engine (Phase 9)")
    logger.info("=" * 75)

    trips_df = pd.read_csv(anom_trips_path)
    logger.info(f"Loaded {len(trips_df)} operational trips from {anom_trips_path}")

    # 1. Load ML models and graph
    demand_model = MLPassengerDemandModel.load(settings.MODEL_DIR / "demand_model.pkl")
    detector = IsolationForestAnomalyDetector.load(settings.MODEL_DIR / "anomaly_detector.pkl")
    graph = TransitNetworkGraph.load(settings.MODEL_DIR / "transit_graph.pkl") if (settings.MODEL_DIR / "transit_graph.pkl").exists() else None

    # 2. Run Phase 6 Demand & Phase 7 Anomaly Inference
    demand_feats = extract_trip_features(trips_df, graph=graph)
    expected_pax = demand_model.predict(demand_feats)
    anom_feats = extract_anomaly_features(trips_df, expected_pax, avg_fare_inr=12.03)
    trip_ids = trips_df["trip_id"].astype(str).tolist()

    detection_results = detector.predict(anom_feats, trip_ids)
    det_dicts = []
    for i, res in enumerate(detection_results):
        d = res.to_dict()
        d["expected_passengers"] = float(expected_pax[i])
        d["expected_revenue_inr"] = float(expected_pax[i] * 12.03)
        det_dicts.append(d)

    # 3. Load Phase 8 Localized Paths if available
    localized_paths = []
    if loc_path.exists():
        loc_df = pd.read_csv(loc_path)
        for _, r in loc_df.iterrows():
            localized_paths.append(
                LocalizedLeakagePath(
                    trip_id=str(r["trip_id"]),
                    route_id=str(r["route_id"]),
                    start_stop=str(r["start_stop"]),
                    end_stop=str(r["end_stop"]),
                    start_sequence=int(r["start_sequence"]),
                    end_sequence=int(r["end_sequence"]),
                    affected_segments=eval(str(r["affected_segments"])) if isinstance(r["affected_segments"], str) and r["affected_segments"].startswith("[") else [],
                    num_segments=int(r["num_segments"]),
                    localization_score=float(r["localization_score"]),
                    estimated_revenue_gap_inr=float(r["estimated_revenue_gap_inr"]),
                    confidence=float(r["confidence"]),
                )
            )

    # 4. Execute Multi-Factor Risk Scoring
    engine = RiskScoringEngine(version=args.version)
    assessments = engine.batch_evaluate_risk(trips_df, det_dicts, localized_paths)

    # 5. Persist Results
    risk_rows = [a.to_dict() for a in assessments]
    risk_df = pd.DataFrame(risk_rows)
    out_csv = synth_dir / "trip_risk_scores.csv"
    risk_df.to_csv(out_csv, index=False)
    logger.info(f"Saved {len(risk_df)} risk assessments to: {out_csv}")

    # Generate metadata report
    level_counts = risk_df["risk_level"].value_counts().to_dict()
    total_impact = risk_df["estimated_revenue_impact_inr"].sum()
    report = {
        "total_trips_assessed": len(risk_df),
        "risk_level_distribution": level_counts,
        "total_estimated_revenue_impact_inr": round(float(total_impact), 2),
        "mean_risk_score": round(float(risk_df["risk_score"].mean()), 4),
        "max_risk_score": round(float(risk_df["risk_score"].max()), 4),
        "min_risk_score": round(float(risk_df["risk_score"].min()), 4),
        "weights": asdict(engine.weights),
        "thresholds": asdict(engine.thresholds),
        "version": args.version,
    }

    report_path = settings.METADATA_DIR / "risk_scoring_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Saved risk scoring report to: {report_path}")

    # Summary Display
    logger.info("\n" + "=" * 75)
    logger.info("OPERATIONAL RISK SCORING SUMMARY")
    logger.info("=" * 75)
    for lvl in [RiskLevel.NORMAL.value, RiskLevel.MONITOR.value, RiskLevel.SUSPICIOUS.value, RiskLevel.HIGH_RISK.value]:
        cnt = level_counts.get(lvl, 0)
        pct = cnt / len(risk_df) * 100
        logger.info(f"  {lvl:<12}: {cnt:>4} trips ({pct:>5.1f}%)")
    logger.info("-" * 75)
    logger.info(f"Mean Risk Score:                {report['mean_risk_score']:.4f}")
    logger.info(f"Total Estimated Revenue Impact: ₹{total_impact:,.2f}")
    logger.info("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())
