"""
FareGuard Alert Explanation CLI Runner

Loads Phase 9 operational risk scores, generates faithful natural language explanations,
evidence tables, and neutral recommended actions, and persists structured alert records.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from explainability.alert_schema import AlertRecord, AlertStatus, ExplanationType
from explainability.explainer import AlertExplanationEngine
from risk.risk_engine import RiskLevel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="FareGuard Explainable AI / Alert Explanation Engine")
    parser.add_argument("--version", type=str, default="1.0.0", help="Explainer engine version")
    args = parser.parse_args()

    synth_dir = settings.SYNTHETIC_DATA_DIR
    risk_csv = synth_dir / "trip_risk_scores.csv"
    anom_trips_path = synth_dir / "anomalous_trip_summaries.csv"

    if not risk_csv.exists():
        logger.error(f"Risk assessments not found: {risk_csv}")
        return 1

    logger.info("=" * 75)
    logger.info("FareGuard Explainable AI / Alert Explanation Engine (Phase 10)")
    logger.info("=" * 75)

    risk_df = pd.read_csv(risk_csv)
    trips_df = pd.read_csv(anom_trips_path) if anom_trips_path.exists() else None
    logger.info(f"Loaded {len(risk_df)} risk assessments from {risk_csv}")

    trip_row_map = {}
    if trips_df is not None:
        for _, r in trips_df.iterrows():
            trip_row_map[str(r["trip_id"])] = r

    engine = AlertExplanationEngine(version=args.version)
    alerts: list[AlertRecord] = []

    for _, row in risk_df.iterrows():
        tid = str(row["trip_id"])
        rid = str(row["route_id"])
        r_score = float(row["risk_score"])
        r_level = RiskLevel(str(row["risk_level"]))
        impact = float(row["estimated_revenue_impact_inr"])
        loc_conf = float(row["localization_confidence"])
        subpath = str(row["affected_subpath"]) if pd.notna(row.get("affected_subpath")) else None

        t_row = trip_row_map.get(tid, {})
        rep_pax = float(t_row.get("total_passengers", 50.0)) if hasattr(t_row, "get") else 50.0
        rep_rev = float(t_row.get("total_revenue_inr", 600.0)) if hasattr(t_row, "get") else 600.0
        exp_rev = rep_rev + impact
        exp_pax = rep_pax + (impact / 12.03)

        factors = eval(str(row.get("risk_factors", "{}"))) if isinstance(row.get("risk_factors"), str) else {}
        anom_score = float(factors.get("anomaly_score_factor", 0.0))

        alert = engine.explain_trip(
            trip_id=tid,
            route_id=rid,
            expected_passengers=exp_pax,
            reported_passengers=rep_pax,
            expected_revenue_inr=exp_rev,
            reported_revenue_inr=rep_rev,
            risk_score=r_score,
            risk_level=r_level,
            anomaly_score=anom_score,
            localization_confidence=loc_conf,
            localized_subpath=subpath,
            is_repeated_pattern="recurrent" in str(row.get("risk_reasons", "")),
        )
        alerts.append(alert)

    # Persist alert records
    alert_rows = [a.to_dict() for a in alerts]
    alerts_df = pd.DataFrame(alert_rows)
    out_csv = synth_dir / "generated_alerts.csv"
    alerts_df.to_csv(out_csv, index=False)
    logger.info(f"Saved {len(alerts_df)} alerts to: {out_csv}")

    # Generate metadata report
    type_counts = alerts_df["dominant_explanation_type"].value_counts().to_dict()
    level_counts = alerts_df["risk_level"].value_counts().to_dict()
    report = {
        "total_alerts_generated": len(alerts_df),
        "dominant_explanation_types": type_counts,
        "risk_level_distribution": level_counts,
        "mean_confidence": round(float(alerts_df["confidence"].mean()), 4),
        "total_revenue_impact_explained_inr": round(float(alerts_df["estimated_revenue_impact_inr"].sum()), 2),
        "version": args.version,
    }

    report_path = settings.METADATA_DIR / "alert_explanation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Saved alert explanation report to: {report_path}")

    # Summary Display
    logger.info("\n" + "=" * 75)
    logger.info("ALERT EXPLANATION ENGINE SUMMARY")
    logger.info("=" * 75)
    for exp_t, cnt in type_counts.items():
        pct = cnt / len(alerts_df) * 100
        logger.info(f"  {exp_t:<26}: {cnt:>4} alerts ({pct:>5.1f}%)")
    logger.info("-" * 75)
    logger.info(f"Mean Explanation Confidence:    {report['mean_confidence']:.4f}")
    logger.info(f"Total Revenue Impact Explained: ₹{report['total_revenue_impact_explained_inr']:,.2f}")
    logger.info("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())
