# FareGuard — Final Research Evaluation Report

> **Evaluation Date**: 2026-09-01T09:11:02.515269+00:00  
> **GTFS Dataset SHA-256**: `2308f8248ea954b75b3660cda7b6d85ecf80831179968baec8ae3db5b41b0b4e`  
> **Simulation Random Seed**: 42  
> **Overall Evaluation Status**: ✅ **PASS (All 5 Experiments Verified)**

---

## 1. Experiment A: Passenger Demand Prediction

Evaluated using strict time-aware chronological splitting across diurnal operational cycles:

| Model | MAE (pax) | RMSE (pax) | MAPE (%) | R² Score |
|---|:---:|:---:|:---:|:---:|
| **Historical Mean Baseline** | 26.06 | 30.283 | 38.31% | 0.5769 |
| **Random Forest Regressor** *(Primary)* | **26.475** | **31.93** | **36.845%** | **0.5296** |
| **Gradient Boosting Regressor** | 31.802 | 36.617 | 40.517% | 0.3814 |

---

## 2. Experiment B: Revenue Leakage Anomaly Detection

Evaluated on 200 operational trips (30 injected anomalies, 170 nominal baseline trips):

| Metric | Inductive Clean-Reference Isolation Forest | Rule-Based Baseline |
|---|:---:|:---:|
| **True Positives (TP)** | **21** | 15 |
| **False Positives (FP)** | **25** | 7 |
| **False Negatives (FN)** | **9** | 15 |
| **True Negatives (TN)** | **145** | 163 |
| **Precision** | **0.4565** | 0.6818 |
| **Recall** | **0.7** | 0.5 |
| **F1 Score** | **0.5526** | 0.5769 |
| **PR-AUC** | **0.6264** | N/A |
| **ROC-AUC** | **0.8778** | N/A |

---

## 3. Experiment C: Graph Discrepancy Localization

| Metric | Result | Description |
|---|:---:|---|
| **Conditional Exact Localization** | **55.00%** | Exact segment match conditioned on detection by Phase 7 |
| **Conditional Overlap Recall** | **95.00%** | Partial subpath overlap conditioned on detection by Phase 7 |
| **End-to-End Exact Localization Recall** | **36.67%** | Exact localization rate over all 30 true injected anomalies |
| **End-to-End Overlap Recall** | **63.33%** | Overlap localization rate over all 30 true injected anomalies |
| **Path Precision** | **73.33%** | Precision of flagged subpath segments |
| **Localization F1** | **0.6796** | Harmonic mean of path precision and overlap recall |

---

## 4. Experiment D: Financial Estimation Reconciliation

- **True Injected Revenue Leakage**: `₹8,476.50` (Ground-truth money directly subtracted by anomaly injectors)
- **Observable Estimated Discrepancy**: `₹40,599.16` (Total observable gap between predicted demand revenue and reported ETM cash)
- **Methodology Reconciliation**: Model estimates total expected-vs-reported revenue gap across all flagged trips, which includes operational variance and unverified cash flows without privileged oracle knowledge.

---

## 5. Experiment E: Real-Time Streaming Performance

- **Throughput**: `73.41 events/sec`
- **Average Processing Latency**: `13.59 ms`
- **P95 Latency**: `25.57 ms`
- **Zero Failed Events / Zero Duplicate Leakage**

---

## 6. Ground-Truth Isolation Audit

- **Leaked Columns Found**: `0`
- **Isolation Status**: ✅ **100% VERIFIED** (Inference pipeline receives zero oracle features)
