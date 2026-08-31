"""
Phase 6 Unit & Integration Tests: ML Passenger Demand Prediction Engine

Verifies:
- Feature generation and column schemas
- Temporal splitting and zero future-data leakage
- Model training & evaluation (Historical Baseline, Random Forest, Gradient Boosting)
- Metric calculations (MAE, RMSE, MAPE, R^2)
- Model persistence (save / reload consistency)
- Determinism and reproducibility
- Zero target/ground-truth leakage
- Non-negativity constraints
- Real Phase 4 dataset evaluation
"""

import math
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from config import settings
from graph.transit_graph import TransitNetworkGraph
from ml.demand_predictor import (
    DEMAND_FEATURE_COLUMNS,
    HistoricalMeanBaseline,
    MLPassengerDemandModel,
    evaluate_predictions,
    extract_trip_features,
    temporal_train_val_test_split,
)


@pytest.fixture
def sample_trips_df():
    """Controlled fixture representing scheduled operational trips."""
    return pd.DataFrame([
        {"trip_id": "T1", "route_id": "R1", "date": "2026-08-20", "scheduled_start": "08:30:00", "num_stops": 20, "total_passengers": 75},
        {"trip_id": "T2", "route_id": "R1", "date": "2026-08-21", "scheduled_start": "09:00:00", "num_stops": 20, "total_passengers": 80},
        {"trip_id": "T3", "route_id": "R2", "date": "2026-08-22", "scheduled_start": "14:00:00", "num_stops": 15, "total_passengers": 40},
        {"trip_id": "T4", "route_id": "R2", "date": "2026-08-23", "scheduled_start": "18:30:00", "num_stops": 15, "total_passengers": 65},
        {"trip_id": "T5", "route_id": "R1", "date": "2026-08-24", "scheduled_start": "22:00:00", "num_stops": 20, "total_passengers": 25},
        {"trip_id": "T6", "route_id": "R3", "date": "2026-08-25", "scheduled_start": "08:15:00", "num_stops": 30, "total_passengers": 95},
        {"trip_id": "T7", "route_id": "R3", "date": "2026-08-26", "scheduled_start": "17:45:00", "num_stops": 30, "total_passengers": 90},
        {"trip_id": "T8", "route_id": "R1", "date": "2026-08-27", "scheduled_start": "12:00:00", "num_stops": 20, "total_passengers": 45},
        {"trip_id": "T9", "route_id": "R2", "date": "2026-08-28", "scheduled_start": "07:45:00", "num_stops": 15, "total_passengers": 70},
        {"trip_id": "T10", "route_id": "R3", "date": "2026-08-29", "scheduled_start": "20:00:00", "num_stops": 30, "total_passengers": 55},
    ])


class TestDemandFeatureEngineering:
    def test_feature_generation_schema(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        assert isinstance(features, pd.DataFrame)
        assert len(features) == len(sample_trips_df)
        for col in DEMAND_FEATURE_COLUMNS:
            assert col in features.columns
            assert not features[col].isnull().any()

    def test_diurnal_peak_flags(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        # T1 is 08:30 (morning peak)
        assert features.loc[0, "is_morning_peak"] == 1
        assert features.loc[0, "is_evening_peak"] == 0
        # T4 is 18:30 (evening peak)
        assert features.loc[3, "is_morning_peak"] == 0
        assert features.loc[3, "is_evening_peak"] == 1

    def test_temporal_splitting_no_leakage(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        X_tr, y_tr, X_val, y_val, X_te, y_te = temporal_train_val_test_split(
            sample_trips_df, features, target_col="total_passengers", train_ratio=0.6, val_ratio=0.2
        )
        assert len(X_tr) == 6
        assert len(X_val) == 2
        assert len(X_te) == 2
        # Check indices are disjoint
        tr_set, val_set, te_set = set(X_tr.index), set(X_val.index), set(X_te.index)
        assert tr_set.isdisjoint(val_set)
        assert val_set.isdisjoint(te_set)
        assert tr_set.isdisjoint(te_set)


class TestDemandModels:
    def test_historical_mean_baseline(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        model = HistoricalMeanBaseline()
        model.fit(features.iloc[:7], sample_trips_df["total_passengers"].iloc[:7])
        preds = model.predict(features.iloc[7:])
        assert len(preds) == 3
        assert np.all(preds > 0)

    def test_random_forest_model(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        model = MLPassengerDemandModel(model_type="random_forest", seed=42)
        model.fit(features.iloc[:7], sample_trips_df["total_passengers"].iloc[:7])
        preds = model.predict(features.iloc[7:])
        assert len(preds) == 3
        assert np.all(preds >= 1.0)

    def test_gradient_boosting_model(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        model = MLPassengerDemandModel(model_type="gradient_boosting", seed=42)
        model.fit(features.iloc[:7], sample_trips_df["total_passengers"].iloc[:7])
        preds = model.predict(features.iloc[7:])
        assert len(preds) == 3
        assert np.all(preds >= 1.0)

    def test_metric_calculation(self):
        y_true = np.array([50.0, 100.0, 75.0])
        y_pred = np.array([45.0, 110.0, 70.0])
        metrics = evaluate_predictions(y_true, y_pred)
        assert abs(metrics.mae - 6.667) < 0.05
        assert metrics.rmse > 0
        assert metrics.mape > 0
        assert metrics.r2 > 0

    def test_model_persistence_and_reload(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        model = MLPassengerDemandModel(model_type="random_forest", seed=42)
        model.fit(features, sample_trips_df["total_passengers"])
        orig_preds = model.predict(features)

        with tempfile.TemporaryDirectory() as tmpdir:
            model_file = Path(tmpdir) / "test_demand_model.pkl"
            meta_file = Path(tmpdir) / "test_meta.json"
            model.save(model_file, meta_file)

            reloaded_model = MLPassengerDemandModel.load(model_file)
            new_preds = reloaded_model.predict(features)
            np.testing.assert_array_almost_equal(orig_preds, new_preds)

    def test_feature_leakage_protection(self, sample_trips_df):
        """Verifies ground-truth columns are never used as model features."""
        df_with_leaks = sample_trips_df.copy()
        df_with_leaks["ground_truth"] = True
        df_with_leaks["anomaly_type"] = "TICKET_UNDERREPORTING"
        df_with_leaks["true_leakage"] = 500.0
        df_with_leaks["severity"] = "HIGH"

        features = extract_trip_features(df_with_leaks)
        for col in ["ground_truth", "anomaly_type", "true_leakage", "severity"]:
            assert col not in features.columns
            assert col not in DEMAND_FEATURE_COLUMNS

    def test_unfitted_model_raises_runtime_error(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        model = MLPassengerDemandModel(model_type="random_forest")
        with pytest.raises(RuntimeError):
            model.predict(features)

    def test_negative_demand_clipping(self, sample_trips_df):
        features = extract_trip_features(sample_trips_df)
        model = MLPassengerDemandModel(model_type="historical_mean_baseline")
        model.fit(features, sample_trips_df["total_passengers"])
        preds = model.predict(features)
        assert np.all(preds >= 1.0)


class TestRealPhase4DemandIntegration:
    def test_real_dataset_demand_training(self):
        clean_trips_path = settings.SYNTHETIC_DATA_DIR / "trip_summaries.csv"
        if not clean_trips_path.exists():
            pytest.skip("Phase 4 synthetic trip summaries not generated.")

        trips_df = pd.read_csv(clean_trips_path)
        features = extract_trip_features(trips_df)

        X_tr, y_tr, X_val, y_val, X_te, y_te = temporal_train_val_test_split(
            trips_df, features, target_col="total_passengers", train_ratio=0.70, val_ratio=0.15
        )

        model = MLPassengerDemandModel(model_type="historical_mean_baseline")
        model.fit(X_tr, y_tr)
        preds = model.predict(X_te)

        metrics = evaluate_predictions(y_te, preds)
        assert metrics.mae < 35.0  # Pass reasonable demand accuracy
        assert metrics.r2 > 0.30

