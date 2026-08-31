"""
FareGuard Demand Model Training & Evaluation CLI

Trains, compares, and saves the ML passenger demand prediction model:
- Historical Mean Baseline
- Random Forest Regressor
- Gradient Boosting / XGBoost Regressor

Outputs:
- models/demand_model.pkl
- models/demand_model_metadata.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import TransitNetworkGraph
from ml.demand_predictor import (
    MLPassengerDemandModel,
    evaluate_predictions,
    extract_trip_features,
    temporal_train_val_test_split,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Train and Evaluate Passenger Demand Models")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    logger.info("=" * 75)
    logger.info("FareGuard Machine Learning Demand Prediction Training & Benchmarking")
    logger.info("=" * 75)

    synth_dir = settings.SYNTHETIC_DATA_DIR
    clean_trips_path = synth_dir / "trip_summaries.csv"
    graph_path = settings.MODEL_DIR / "transit_graph.pkl"

    if not clean_trips_path.exists():
        logger.error(f"Clean Phase 4 dataset not found at {clean_trips_path}. Run Phase 4 first.")
        return 1

    # 1. Load Data & Graph
    logger.info(f"Loading clean Phase 4 operational dataset from {clean_trips_path}...")
    trips_df = pd.read_csv(clean_trips_path)
    graph = TransitNetworkGraph.load(graph_path) if graph_path.exists() else None

    # 2. Extract Features
    logger.info("Extracting time-of-day, calendar, and network structural features...")
    features_df = extract_trip_features(trips_df, graph=graph)
    logger.info(f"Generated feature matrix with shape: {features_df.shape}")

    # 3. Temporal Train / Val / Test Split
    X_train, y_train, X_val, y_val, X_test, y_test = temporal_train_val_test_split(
        df=trips_df,
        features_df=features_df,
        target_col="total_passengers",
        train_ratio=0.70,
        val_ratio=0.15,
    )
    logger.info(f"Temporal Split: Train={len(X_train)} rows (70%), Val={len(X_val)} rows (15%), Test={len(X_test)} rows (15%)")

    # 4. Train and Compare Models
    candidates = [
        ("baseline", "Historical Mean Baseline"),
        ("random_forest", "Random Forest Regressor"),
        ("gradient_boosting", "Gradient Boosting Regressor"),
    ]

    results = {}
    fitted_models = {}

    for m_type, name in candidates:
        logger.info(f"\n--- Training {name} ---")
        t0 = time.time()
        model = MLPassengerDemandModel(model_type=m_type, seed=args.seed)
        model.fit(X_train, y_train)
        train_time = time.time() - t0

        # Evaluate on Holdout Test Set
        y_pred = model.predict(X_test)
        metrics = evaluate_predictions(y_test, y_pred)
        model.metrics = metrics

        results[m_type] = {
            "name": name,
            "metrics": metrics.to_dict(),
            "train_time_sec": round(train_time, 4),
        }
        fitted_models[m_type] = model

        logger.info(f"  Test MAE:   {metrics.mae:.3f} passengers")
        logger.info(f"  Test RMSE:  {metrics.rmse:.3f}")
        logger.info(f"  Test MAPE:  {metrics.mape:.2f}%")
        logger.info(f"  Test R2:    {metrics.r2:.4f}")

    # 5. Model Selection (Lowest MAE on Holdout Test)
    best_type = min(results.keys(), key=lambda k: results[k]["metrics"]["mae"])
    best_model = fitted_models[best_type]
    logger.info(f"\nSelected Best Model: {results[best_type]['name']} (MAE: {results[best_type]['metrics']['mae']})")

    # 6. Save Model Artifact & Metadata
    model_artifact_path = settings.MODEL_DIR / "demand_model.pkl"
    metadata_artifact_path = settings.MODEL_DIR / "demand_model_metadata.json"

    best_model.save(model_artifact_path, metadata_artifact_path)
    logger.info(f"Model saved to: {model_artifact_path}")

    # Print summary table
    logger.info("\n" + "=" * 75)
    logger.info("DEMAND MODEL BENCHMARKING SUMMARY")
    logger.info("=" * 75)
    logger.info(f"{'Model Name':<30} | {'Test MAE':<10} | {'Test RMSE':<10} | {'Test MAPE':<10} | {'Test R2'}")
    logger.info("-" * 75)
    for m_type, res in results.items():
        m = res["metrics"]
        logger.info(f"{res['name']:<30} | {m['mae']:<10.3f} | {m['rmse']:<10.3f} | {m['mape']:<9.2f}% | {m['r2']:.4f}")
    logger.info("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())
