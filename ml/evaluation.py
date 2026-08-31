"""
FareGuard Machine Learning Evaluation Engine

Evaluates ML anomaly detection performance strictly POST-INFERENCE against ground truth:
- Precision, Recall, F1-Score
- ROC-AUC, PR-AUC
- Confusion Matrix (TP, FP, TN, FN) and False Positive Rate
- Per-Anomaly-Type Performance Breakdown
- Per-Severity Performance Breakdown
"""

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ml.anomaly_detector import AnomalyDetectionResult

logger = logging.getLogger(__name__)


@dataclass
class AnomalyEvaluationMetrics:
    total_samples: int
    true_anomalies: int
    predicted_anomalies: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    roc_auc: float
    pr_auc: float
    per_type_recall: Dict[str, float]
    per_severity_recall: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "true_anomalies": self.true_anomalies,
            "predicted_anomalies": self.predicted_anomalies,
            "confusion_matrix": {
                "TP": self.true_positives,
                "FP": self.false_positives,
                "TN": self.true_negatives,
                "FN": self.false_negatives,
            },
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "per_type_recall": {k: round(v, 4) for k, v in self.per_type_recall.items()},
            "per_severity_recall": {k: round(v, 4) for k, v in self.per_severity_recall.items()},
        }


def evaluate_anomaly_detection(
    results: List[AnomalyDetectionResult],
    ground_truth_df: pd.DataFrame,
    all_trip_ids: List[str],
) -> AnomalyEvaluationMetrics:
    """
    Compares post-inference anomaly predictions against the ground-truth table.
    """
    # Normalize trip_ids to string
    gt_copy = ground_truth_df.copy()
    gt_copy["trip_id"] = gt_copy["trip_id"].astype(str)
    gt_map = gt_copy.set_index("trip_id").to_dict(orient="index")
    pred_map = {str(r.trip_id): r for r in results}

    y_true = []
    y_pred = []
    y_scores = []
    anomaly_types = []
    severities = []

    for raw_tid in all_trip_ids:
        tid = str(raw_tid)
        is_true_anom = tid in gt_map
        y_true.append(1 if is_true_anom else 0)

        pred_res = pred_map.get(tid)
        if pred_res:
            y_pred.append(1 if pred_res.is_anomaly else 0)
            y_scores.append(pred_res.anomaly_score)
        else:
            y_pred.append(0)
            y_scores.append(0.0)

        if is_true_anom:
            anomaly_types.append(str(gt_map[tid].get("anomaly_type", "UNKNOWN")))
            severities.append(str(gt_map[tid].get("severity", "MEDIUM")))
        else:
            anomaly_types.append("NORMAL")
            severities.append("NONE")


    y_t = np.array(y_true, dtype=int)
    y_p = np.array(y_pred, dtype=int)
    y_s = np.array(y_scores, dtype=float)

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_t, y_p, labels=[0, 1]).ravel()

    precision = float(precision_score(y_t, y_p, zero_division=0))
    recall = float(recall_score(y_t, y_p, zero_division=0))
    f1 = float(f1_score(y_t, y_p, zero_division=0))
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    # ROC & PR AUC
    try:
        roc_auc = float(roc_auc_score(y_t, y_s))
    except Exception:
        roc_auc = 0.5

    try:
        prec_curve, rec_curve, _ = precision_recall_curve(y_t, y_s)
        pr_auc = float(auc(rec_curve, prec_curve))
    except Exception:
        pr_auc = 0.0

    # Per Anomaly-Type Recall
    per_type = {}
    unique_types = set(anomaly_types) - {"NORMAL"}
    for atype in sorted(unique_types):
        mask = np.array([t == atype for t in anomaly_types])
        if np.sum(mask) > 0:
            per_type[atype] = float(np.mean(y_p[mask]))

    # Per Severity Recall
    per_sev = {}
    unique_sevs = set(severities) - {"NONE"}
    for sev in sorted(unique_sevs):
        mask = np.array([s == sev for s in severities])
        if np.sum(mask) > 0:
            per_sev[sev] = float(np.mean(y_p[mask]))

    return AnomalyEvaluationMetrics(
        total_samples=len(all_trip_ids),
        true_anomalies=int(np.sum(y_t)),
        predicted_anomalies=int(np.sum(y_p)),
        true_positives=int(tp),
        false_positives=int(fp),
        true_negatives=int(tn),
        false_negatives=int(fn),
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=fpr,
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        per_type_recall=per_type,
        per_severity_recall=per_sev,
    )
