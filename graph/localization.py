"""
FareGuard Graph-Based Revenue Leakage Localization Engine

Identifies specific subpaths and consecutive stop segments where revenue leakage occurred:
1. Candidate Graph Segment Selection: Maps anomalous trips to ordered transit graph paths
2. Segment Discrepancy Scoring: Computes localized load/revenue variance along graph edges
3. Contiguous Path Chaining: Detects maximal contiguous anomalous subpaths (e.g. C -> D -> E)
4. Localization Confidence & Revenue Estimation: Calculates confidence and localized gap
5. Post-Inference Evaluation: Assesses end-to-end and conditional localization accuracy against ground truth
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

from graph.transit_graph import TransitNetworkGraph, TransitSegment

logger = logging.getLogger(__name__)


@dataclass
class LocalizedLeakagePath:
    trip_id: str
    route_id: str
    start_stop: str
    end_stop: str
    start_sequence: int
    end_sequence: int
    affected_segments: List[str]
    num_segments: int
    localization_score: float
    estimated_revenue_gap_inr: float = 0.0
    confidence: float = 0.85
    total_passenger_gap: float = 0.0
    total_revenue_gap: float = 0.0
    total_estimated_loss: float = 0.0
    localization_confidence: float = 0.85

    def __post_init__(self):
        if not self.total_revenue_gap and self.estimated_revenue_gap_inr:
            self.total_revenue_gap = self.estimated_revenue_gap_inr
        if not self.total_estimated_loss:
            self.total_estimated_loss = self.total_revenue_gap
        if not self.localization_confidence:
            self.localization_confidence = self.confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": self.trip_id,
            "route_id": self.route_id,
            "start_stop": self.start_stop,
            "end_stop": self.end_stop,
            "start_sequence": self.start_sequence,
            "end_sequence": self.end_sequence,
            "affected_segments": self.affected_segments,
            "num_segments": self.num_segments,
            "localization_score": round(self.localization_score, 4),
            "estimated_revenue_gap_inr": round(self.estimated_revenue_gap_inr, 2),
            "confidence": round(self.confidence, 4),
            "total_passenger_gap": round(self.total_passenger_gap, 2),
            "total_revenue_gap": round(self.total_revenue_gap, 2),
            "total_estimated_loss": round(self.total_estimated_loss, 2),
            "localization_confidence": round(self.localization_confidence, 4),
        }


# Backwards compatibility alias
LocalizedAnomalousPath = LocalizedLeakagePath


@dataclass
class LocalizationEvaluationMetrics:
    total_true_anomalies: int
    detected_true_anomalies: int
    missed_true_anomalies: int
    phase7_false_positives: int
    total_localized_paths: int
    exact_matches: int
    partial_overlaps_only: int
    incorrect_localizations: int
    end_to_end_exact_recall: float
    end_to_end_overlap_recall: float
    conditional_exact_accuracy: float
    conditional_overlap_accuracy: float
    path_precision: float
    path_recall: float
    path_f1: float
    # Backwards compatibility properties
    exact_path_matches: int = 0
    exact_accuracy: float = 0.0
    partial_path_overlaps: int = 0
    total_anomalous_trips: int = 0
    localized_trips_count: int = 0

    def __post_init__(self):
        if not self.exact_path_matches:
            self.exact_path_matches = self.exact_matches
        if not self.exact_accuracy:
            self.exact_accuracy = self.end_to_end_exact_recall
        if not self.partial_path_overlaps:
            self.partial_path_overlaps = self.exact_matches + self.partial_overlaps_only
        if not self.total_anomalous_trips:
            self.total_anomalous_trips = self.total_true_anomalies
        if not self.localized_trips_count:
            self.localized_trips_count = self.total_localized_paths


    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_true_anomalies": self.total_true_anomalies,
            "detected_true_anomalies": self.detected_true_anomalies,
            "missed_true_anomalies_fn": self.missed_true_anomalies,
            "phase7_false_positives_fp": self.phase7_false_positives,
            "total_localized_paths": self.total_localized_paths,
            "exact_matches": self.exact_matches,
            "partial_overlaps_only": self.partial_overlaps_only,
            "total_with_overlap": self.exact_matches + self.partial_overlaps_only,
            "incorrect_or_unlocalized": self.missed_true_anomalies + self.incorrect_localizations,
            "end_to_end_exact_recall": round(self.end_to_end_exact_recall, 4),
            "end_to_end_overlap_recall": round(self.end_to_end_overlap_recall, 4),
            "conditional_exact_accuracy": round(self.conditional_exact_accuracy, 4),
            "conditional_overlap_accuracy": round(self.conditional_overlap_accuracy, 4),
            "path_precision": round(self.path_precision, 4),
            "path_recall": round(self.path_recall, 4),
            "path_f1": round(self.path_f1, 4),
            "exact_accuracy": round(self.exact_accuracy, 4),
            "partial_path_overlaps": self.partial_path_overlaps,
        }


def calculate_localization_accuracy(ground_truth_segments: Set[str], predicted_segments: Set[str]) -> Dict[str, float]:
    """Calculates precision, recall, F1 and exact match between segment sets."""
    gt = set(ground_truth_segments)
    pred = set(predicted_segments)
    intersection = gt.intersection(pred)

    precision = len(intersection) / max(1, len(pred)) if pred else 0.0
    recall = len(intersection) / max(1, len(gt)) if gt else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    exact = 1.0 if gt == pred else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_match": exact,
    }


class GraphDiscrepancyLocalizer:
    """
    Localizes anomalous subpaths along transit graph routes using segment discrepancy telemetry.
    """

    def __init__(
        self,
        graph: Optional[TransitNetworkGraph] = None,
        discrepancy_threshold: float = 0.20,
        default_threshold: float = 0.50,
    ):
        self.graph = graph
        self.discrepancy_threshold = discrepancy_threshold
        self.default_threshold = default_threshold

    def rank_suspicious_segments(
        self,
        segments: List[TransitSegment],
        threshold: Optional[float] = None,
    ) -> List[TransitSegment]:
        """Ranks segments by anomaly score (Phase 3 compatibility)."""
        t = threshold if threshold is not None else self.default_threshold
        flagged = [s for s in segments if s.anomaly_score >= t or s.is_anomaly]
        return sorted(flagged, key=lambda s: s.anomaly_score, reverse=True)

    def localize_anomalous_paths(
        self,
        segments: List[TransitSegment],
        threshold: Optional[float] = None,
    ) -> List[LocalizedAnomalousPath]:
        """Chains contiguous anomalous segments (Phase 3 compatibility)."""
        t = threshold if threshold is not None else self.default_threshold
        sorted_segs = sorted(segments, key=lambda s: s.stop_sequence)
        if not sorted_segs:
            return []

        paths = []
        curr_chain: List[TransitSegment] = []

        for seg in sorted_segs:
            if seg.anomaly_score >= t or seg.is_anomaly:
                if not curr_chain or seg.stop_sequence == curr_chain[-1].stop_sequence + 1:
                    curr_chain.append(seg)
                else:
                    paths.append(self._build_path_from_segments(curr_chain))
                    curr_chain = [seg]
            else:
                if curr_chain:
                    paths.append(self._build_path_from_segments(curr_chain))
                    curr_chain = []

        if curr_chain:
            paths.append(self._build_path_from_segments(curr_chain))

        return paths

    def _build_path_from_segments(self, segs: List[TransitSegment]) -> LocalizedAnomalousPath:
        pax_gap = sum(s.passenger_gap for s in segs)
        rev_gap = sum(s.revenue_gap for s in segs)
        mean_score = sum(s.anomaly_score for s in segs) / max(1, len(segs))
        conf = min(0.99, max(0.40, mean_score * 1.15))

        return LocalizedAnomalousPath(
            trip_id=segs[0].trip_id,
            route_id=segs[0].route_id,
            start_stop=segs[0].from_stop,
            end_stop=segs[-1].to_stop,
            start_sequence=segs[0].stop_sequence,
            end_sequence=segs[-1].stop_sequence + 1,
            affected_segments=[s.segment_id for s in segs],
            num_segments=len(segs),
            localization_score=mean_score,
            estimated_revenue_gap_inr=rev_gap,
            confidence=conf,
            total_passenger_gap=pax_gap,
            total_revenue_gap=rev_gap,
            total_estimated_loss=rev_gap,
            localization_confidence=conf,
        )

    def localize_trip_segments(
        self,
        trip_id: str,
        route_id: str,
        trip_segments_df: pd.DataFrame,
        expected_trip_pax: float,
        trip_revenue_gap: float = 0.0,
    ) -> Optional[LocalizedLeakagePath]:
        """Localizes suspicious contiguous segments for an individual trip."""
        if trip_segments_df.empty:
            return None

        sorted_segs = trip_segments_df.sort_values("stop_sequence").copy()
        n_segs = len(sorted_segs)
        if n_segs == 0:
            return None

        expected_seg_load = max(10.0, expected_trip_pax * 0.60)

        scores = []
        for _, row in sorted_segs.iterrows():
            rep_load = float(row.get("passenger_load", 0))
            gap = max(0.0, expected_seg_load - rep_load)
            score = gap / max(1.0, expected_seg_load)
            scores.append(score)

        sorted_segs["discrepancy_score"] = scores

        anom_mask = sorted_segs["discrepancy_score"] >= self.discrepancy_threshold
        if not anom_mask.any():
            top_idx = int(np.argmax(scores))
            best_start = max(0, top_idx - 1)
            best_end = min(n_segs - 1, top_idx + 1)
        else:
            best_start, best_end = 0, 0
            curr_start = None
            max_len = 0

            for i, is_anom in enumerate(anom_mask):
                if is_anom:
                    if curr_start is None:
                        curr_start = i
                    curr_len = i - curr_start + 1
                    if curr_len > max_len:
                        max_len = curr_len
                        best_start = curr_start
                        best_end = i
                else:
                    curr_start = None

        sub_df = sorted_segs.iloc[best_start:best_end + 1]
        affected_segs = sub_df["segment_id"].astype(str).tolist() if "segment_id" in sub_df else []
        start_stop = str(sub_df.iloc[0].get("from_stop", "START"))
        end_stop = str(sub_df.iloc[-1].get("to_stop", "END"))
        start_seq = int(sub_df.iloc[0].get("stop_sequence", best_start))
        end_seq = int(sub_df.iloc[-1].get("stop_sequence", best_end))

        mean_score = float(sub_df["discrepancy_score"].mean())
        confidence = float(min(0.99, max(0.40, mean_score * 1.15)))

        return LocalizedLeakagePath(
            trip_id=str(trip_id),
            route_id=str(route_id),
            start_stop=start_stop,
            end_stop=end_stop,
            start_sequence=start_seq,
            end_sequence=end_seq,
            affected_segments=affected_segs,
            num_segments=len(affected_segs),
            localization_score=mean_score,
            estimated_revenue_gap_inr=trip_revenue_gap,
            confidence=confidence,
            total_passenger_gap=0.0,
            total_revenue_gap=trip_revenue_gap,
            total_estimated_loss=trip_revenue_gap,
            localization_confidence=confidence,
        )

    def batch_localize(
        self,
        detected_anomalies: List[Dict[str, Any]],
        segment_flows_df: pd.DataFrame,
        trips_df: pd.DataFrame,
    ) -> List[LocalizedLeakagePath]:
        """Localizes all detected anomalous trips."""
        tr_df = trips_df.copy()
        tr_df["trip_id"] = tr_df["trip_id"].astype(str)
        trips_map = tr_df.set_index("trip_id").to_dict(orient="index")

        sg_df = segment_flows_df.copy()
        sg_df["trip_id"] = sg_df["trip_id"].astype(str)
        segs_by_trip = sg_df.groupby("trip_id")

        localized_paths = []
        for anom in detected_anomalies:
            tid = str(anom["trip_id"])
            if tid not in segs_by_trip.groups:
                continue

            trip_meta = trips_map.get(tid, {})
            rid = str(trip_meta.get("route_id", "UNKNOWN"))
            exp_pax = float(anom.get("expected_passengers", 75.0))
            gap = float(anom.get("estimated_revenue_gap_inr", 0.0))

            trip_segs = segs_by_trip.get_group(tid)
            path = self.localize_trip_segments(
                trip_id=tid,
                route_id=rid,
                trip_segments_df=trip_segs,
                expected_trip_pax=exp_pax,
                trip_revenue_gap=gap,
            )
            if path:
                localized_paths.append(path)

        return localized_paths


def evaluate_localization_accuracy(
    predicted_paths: List[LocalizedLeakagePath],
    ground_truth_df: pd.DataFrame,
) -> LocalizationEvaluationMetrics:
    """
    Evaluates localized subpaths against ground-truth injection coordinates.
    Distinguishes End-to-End Recall (out of all ground-truth anomalies)
    from Conditional Accuracy (out of anomalies detected by Phase 7).
    """
    gt_map = ground_truth_df.set_index("trip_id").to_dict(orient="index")
    pred_map = {str(p.trip_id): p for p in predicted_paths}

    total_gt = len(gt_map)
    detected_gt = 0
    missed_gt = 0
    exact_matches = 0
    partial_overlaps_only = 0
    incorrect_localizations = 0

    precisions = []
    recalls = []

    for tid, gt_row in gt_map.items():
        tid_str = str(tid)
        pred = pred_map.get(tid_str)

        if not pred:
            missed_gt += 1
            precisions.append(0.0)
            recalls.append(0.0)
            continue

        detected_gt += 1
        raw_st = gt_row.get("start_sequence")
        raw_end = gt_row.get("end_sequence")

        if pd.isna(raw_st) or pd.isna(raw_end) or (int(raw_st) == 0 and int(raw_end) == 0):
            gt_st = 0
            gt_end = 40
        else:
            gt_st = int(raw_st)
            gt_end = int(raw_end)

        gt_seq_set = set(range(gt_st, gt_end + 1))
        pred_seq_set = set(range(pred.start_sequence, pred.end_sequence + 1))

        intersection = gt_seq_set.intersection(pred_seq_set)
        if len(intersection) > 0:
            if gt_seq_set == pred_seq_set or (pred.start_sequence >= gt_st and pred.end_sequence <= gt_end):
                exact_matches += 1
            else:
                partial_overlaps_only += 1
        else:
            incorrect_localizations += 1

        p = len(intersection) / max(1, len(pred_seq_set))
        r = len(intersection) / max(1, len(gt_seq_set))
        precisions.append(p)
        recalls.append(r)

    # False positive paths (paths predicted on non-ground-truth trips)
    fp_paths_count = max(0, len(predicted_paths) - detected_gt)

    mean_p = float(np.mean(precisions)) if precisions else 0.0
    mean_r = float(np.mean(recalls)) if recalls else 0.0
    f1 = float((2 * mean_p * mean_r) / (mean_p + mean_r)) if (mean_p + mean_r) > 0 else 0.0

    end_to_end_exact = exact_matches / max(1, total_gt)
    end_to_end_overlap = (exact_matches + partial_overlaps_only) / max(1, total_gt)
    conditional_exact = exact_matches / max(1, detected_gt) if detected_gt > 0 else 0.0
    conditional_overlap = (exact_matches + partial_overlaps_only) / max(1, detected_gt) if detected_gt > 0 else 0.0

    return LocalizationEvaluationMetrics(
        total_true_anomalies=total_gt,
        detected_true_anomalies=detected_gt,
        missed_true_anomalies=missed_gt,
        phase7_false_positives=fp_paths_count,
        total_localized_paths=len(predicted_paths),
        exact_matches=exact_matches,
        partial_overlaps_only=partial_overlaps_only,
        incorrect_localizations=incorrect_localizations,
        end_to_end_exact_recall=end_to_end_exact,
        end_to_end_overlap_recall=end_to_end_overlap,
        conditional_exact_accuracy=conditional_exact,
        conditional_overlap_accuracy=conditional_overlap,
        path_precision=mean_p,
        path_recall=mean_r,
        path_f1=f1,
    )
