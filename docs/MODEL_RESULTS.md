# FareGuard Experimental Results & Verification

## 1. Demand Prediction Benchmarks (Test Set)

| Model | MAE (passengers) | RMSE (passengers) | MAPE (%) | R² Score |
|---|:---:|:---:|:---:|:---:|
| Historical Mean Baseline | 16.85 | 21.42 | 28.3% | 0.5210 |
| **Random Forest Regressor** *(Production)* | **7.42** | **9.88** | **11.2%** | **0.8942** |
| Gradient Boosting Regressor | 7.96 | 10.31 | 12.1% | 0.8815 |

---

## 2. Revenue Anomaly Detection Benchmarks

| Metric | Clean-Reference Isolation Forest | Rule Baseline |
|---|:---:|:---:|
| **True Positives (TP)** | **29** | 22 |
| **False Positives (FP)** | **3** | 8 |
| **False Negatives (FN)** | **1** | 8 |
| **True Negatives (TN)** | **167** | 162 |
| **Precision** | **90.62%** | 73.33% |
| **Recall** | **96.67%** | 73.33% |
| **F1 Score** | **0.9355** | 0.7333 |
| **PR-AUC** | **0.9418** | N/A |
| **ROC-AUC** | **0.9845** | N/A |
| **False Positive Rate (FPR)** | **1.76%** | 4.71% |

---

## 3. Graph Localization Benchmarks

| Metric | Value | Meaning |
|---|:---:|---|
| **Conditional Exact Localization** | **55.00%** | Exact segment identified given detection |
| **Conditional Overlap Recall** | **95.00%** | Partial corridor overlap identified given detection |
| **End-to-End Overlap Recall** | **63.33%** | Unconditional localization recall across all anomalies |
| **Path Precision** | **73.33%** | Segment precision of localized subpaths |

---

## 4. Real-Time Streaming Performance

- **Throughput**: `> 1,500 events / sec` (Single-worker in-memory/Redis broker)
- **Average Latency**: `< 2.5 ms`
- **P95 Latency**: `< 5.0 ms`
- **DLQ Error Rate**: `0.00%` on valid transit streams
