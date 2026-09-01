# FareGuard Methodology and Scientific Formulations

## 1. Machine Learning Demand Prediction (Phase 6)

Passenger demand is modeled as an inductive regression task predicting total trip passenger volume $\hat{y}_i$:

$$\hat{y}_i = f(\mathbf{x}_i)$$

Where $\mathbf{x}_i \in \mathbb{R}^d$ includes:
- **Diurnal Temporal Encoding**: Departure hour, minute, morning peak indicator ($7:30 - 10:30$), evening peak indicator ($16:30 - 20:30$), midday indicator, night indicator.
- **Calendar Signals**: Day of week, weekend indicator.
- **Topological Route Features**: Number of stops, route length in km, average inter-stop distance, historical route service frequency.

### Temporal Cross-Validation
Strict chronological splitting (70% train, 15% validation, 15% test) guarantees zero future-data leakage across diurnal cycles.

---

## 2. Anomaly Detection Engine (Phase 7)

Anomalies are detected using an **Inductive Clean-Reference Isolation Forest**:
1. Fitted exclusively on nominal baseline operations $\mathcal{D}_{\text{clean}}$.
2. Feature vectors $\mathbf{z}_i$ capture multi-dimensional divergence:

$$\mathbf{z}_i = \left[ \hat{y}_i, y_i, (\hat{y}_i - y_i), \frac{y_i}{\max(1, \hat{y}_i)}, \hat{R}_i, R_i, (\hat{R}_i - R_i), \frac{R_i}{\max(1, \hat{R}_i)}, \Delta \bar{f}_i, \mathbb{I}(y_i = 0) \right]$$

---

## 3. Transit Graph Localization (Phase 8)

For anomalous trips, discrepancy localization isolates contiguous high-deficit corridor segments using cumulative deficit scoring:

$$S(u, v) = \sum_{e \in \text{path}(u, v)} \max(0, \hat{L}_e - L_e)$$

Where $\hat{L}_e$ is the expected segment passenger load and $L_e$ is the reported segment load.

---

## 4. Multi-Factor Risk Scoring Engine (Phase 9)

Continuous risk scores $r_i \in [0.0, 1.0]$ are formulated as a weighted combination of observable discrepancies:

$$r_i = w_{\text{anom}} s_i + w_{\text{pax}} \min\left(1, \frac{\max(0, \hat{y}_i - y_i)}{\hat{y}_i}\right) + w_{\text{rev}} \min\left(1, \frac{\max(0, \hat{R}_i - R_i)}{\hat{R}_i}\right) + w_{\text{loc}} c_{\text{loc}} + \delta_{\text{rep}}$$

Categorization:
- `NORMAL` ($0.00 \le r_i < 0.30$)
- `MONITOR` ($0.30 \le r_i < 0.60$)
- `SUSPICIOUS` ($0.60 \le r_i < 0.80$)
- `HIGH_RISK` ($0.80 \le r_i \le 1.00$)
