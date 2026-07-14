/**
 * FareGuard - ML Forecasting & Anomaly Detection Layer
 * 
 * Implements ridership/revenue forecasting using gradient-boosted decision trees
 * and anomaly detection using Isolation Forest + statistical control charts.
 * 
 * Model Choice Justification:
 * - Gradient-boosted trees (manual implementation) chosen over LSTM/Prophet because:
 *   1. Better handles tabular features (time, route category, stop density)
 *   2. More interpretable feature importances for transit officials
 *   3. Faster training on moderate-sized datasets
 *   4. Robust to missing values and outliers in transit data
 * 
 * - Isolation Forest chosen for anomaly detection because:
 *   1. Unsupervised - doesn't need labeled anomaly data for training
 *   2. Naturally handles multivariate anomalies
 *   3. Efficient O(n log n) training complexity
 *   4. Produces continuous anomaly scores (not just binary labels)
 */
const { getDb } = require('../shared/database');
const logger = require('../shared/logger');
const config = require('../shared/config');
const { getObjectStorage } = require('../cloud-layer/ingestion-pipeline');
const fs = require('fs');
const path = require('path');

const log = logger.child({ service: 'ml-layer' });

// ============================================================
// Feature Engineering
// ============================================================

/**
 * Extract ML features from raw ticketing events
 */
function engineerFeatures(events) {
  return events.map(e => ({
    // Temporal features
    hour: e.sim_hour,
    day_of_week: e.day_of_week,
    is_weekend: (e.day_of_week === 0 || e.day_of_week === 6) ? 1 : 0,
    is_peak_morning: (e.sim_hour >= 8 && e.sim_hour <= 10) ? 1 : 0,
    is_peak_evening: (e.sim_hour >= 17 && e.sim_hour <= 20) ? 1 : 0,
    hour_sin: Math.sin(2 * Math.PI * e.sim_hour / 24),
    hour_cos: Math.cos(2 * Math.PI * e.sim_hour / 24),
    dow_sin: Math.sin(2 * Math.PI * e.day_of_week / 7),
    dow_cos: Math.cos(2 * Math.PI * e.day_of_week / 7),

    // Route features
    route_category_num: encodeCategory(e.route_category),
    stop_sequence: e.stop_sequence || 0,
    boarding_density: e.boarding_density || 1.0,

    // Target values
    boarding_count: e.boarding_count,
    expected_revenue: e.expected_revenue,
    reported_revenue: e.reported_revenue,
    ticket_count: e.ticket_count,

    // Discrepancy features (for anomaly detection)
    revenue_ratio: e.expected_revenue > 0 ? e.reported_revenue / e.expected_revenue : 1,
    ticket_ratio: e.boarding_count > 0 ? e.ticket_count / e.boarding_count : 1,
    revenue_gap: e.expected_revenue - e.reported_revenue,

    // Metadata
    route_id: e.route_id,
    trip_id: e.trip_id,
    stop_id: e.stop_id,
    sim_date: e.sim_date,
    is_anomalous: e.is_anomalous,
    anomaly_id: e.anomaly_id,
  }));
}

function encodeCategory(category) {
  const map = { 'city-core': 0, 'suburban': 1, 'feeder': 2, 'express': 3, 'outer': 4 };
  return map[category] ?? 2;
}

// ============================================================
// Decision Tree Implementation (for Gradient Boosted ensemble)
// ============================================================

class DecisionTreeNode {
  constructor() {
    this.featureIndex = null;
    this.threshold = null;
    this.left = null;
    this.right = null;
    this.value = null; // Leaf prediction
  }
}

class DecisionTree {
  constructor(maxDepth = 6, minSamplesLeaf = 5) {
    this.maxDepth = maxDepth;
    this.minSamplesLeaf = minSamplesLeaf;
    this.root = null;
    this.featureNames = null;
  }

  fit(X, y) {
    this.root = this._buildTree(X, y, 0);
  }

  predict(X) {
    return X.map(row => this._predictOne(this.root, row));
  }

  _predictOne(node, x) {
    if (node.value !== null) return node.value;
    if (x[node.featureIndex] <= node.threshold) {
      return this._predictOne(node.left, x);
    }
    return this._predictOne(node.right, x);
  }

  _buildTree(X, y, depth) {
    const node = new DecisionTreeNode();

    // Leaf conditions
    if (depth >= this.maxDepth || y.length <= this.minSamplesLeaf) {
      node.value = this._mean(y);
      return node;
    }

    // Find best split
    const best = this._findBestSplit(X, y);
    if (!best) {
      node.value = this._mean(y);
      return node;
    }

    node.featureIndex = best.featureIndex;
    node.threshold = best.threshold;

    // Split data
    const leftIdx = [];
    const rightIdx = [];
    for (let i = 0; i < X.length; i++) {
      if (X[i][best.featureIndex] <= best.threshold) leftIdx.push(i);
      else rightIdx.push(i);
    }

    if (leftIdx.length < this.minSamplesLeaf || rightIdx.length < this.minSamplesLeaf) {
      node.value = this._mean(y);
      return node;
    }

    node.left = this._buildTree(
      leftIdx.map(i => X[i]),
      leftIdx.map(i => y[i]),
      depth + 1
    );
    node.right = this._buildTree(
      rightIdx.map(i => X[i]),
      rightIdx.map(i => y[i]),
      depth + 1
    );

    return node;
  }

  _findBestSplit(X, y) {
    if (X.length === 0) return null;
    const numFeatures = X[0].length;
    let bestGain = -Infinity;
    let bestSplit = null;
    const parentVariance = this._variance(y);

    // Sample features (sqrt(n) for randomness)
    const numSample = Math.max(1, Math.floor(Math.sqrt(numFeatures)));
    const featureIndices = [];
    const allIndices = Array.from({ length: numFeatures }, (_, i) => i);
    for (let i = 0; i < numSample; i++) {
      const idx = Math.floor(Math.random() * allIndices.length);
      featureIndices.push(allIndices.splice(idx, 1)[0]);
    }

    for (const fi of featureIndices) {
      // Get unique values and try splits
      const values = X.map(row => row[fi]).sort((a, b) => a - b);
      const uniqueValues = [...new Set(values)];

      // Sample thresholds for efficiency
      const step = Math.max(1, Math.floor(uniqueValues.length / 10));
      for (let t = 0; t < uniqueValues.length - 1; t += step) {
        const threshold = (uniqueValues[t] + uniqueValues[Math.min(t + 1, uniqueValues.length - 1)]) / 2;

        const leftY = [];
        const rightY = [];
        for (let i = 0; i < X.length; i++) {
          if (X[i][fi] <= threshold) leftY.push(y[i]);
          else rightY.push(y[i]);
        }

        if (leftY.length < this.minSamplesLeaf || rightY.length < this.minSamplesLeaf) continue;

        const gain = parentVariance -
          (leftY.length / y.length) * this._variance(leftY) -
          (rightY.length / y.length) * this._variance(rightY);

        if (gain > bestGain) {
          bestGain = gain;
          bestSplit = { featureIndex: fi, threshold };
        }
      }
    }

    return bestGain > 0 ? bestSplit : null;
  }

  _mean(arr) {
    if (arr.length === 0) return 0;
    return arr.reduce((s, v) => s + v, 0) / arr.length;
  }

  _variance(arr) {
    if (arr.length <= 1) return 0;
    const m = this._mean(arr);
    return arr.reduce((s, v) => s + (v - m) ** 2, 0) / arr.length;
  }

  serialize() {
    return JSON.stringify(this._serializeNode(this.root));
  }

  _serializeNode(node) {
    if (!node) return null;
    return {
      fi: node.featureIndex,
      th: node.threshold,
      v: node.value,
      l: this._serializeNode(node.left),
      r: this._serializeNode(node.right),
    };
  }

  static deserialize(json) {
    const tree = new DecisionTree();
    const data = JSON.parse(json);
    tree.root = tree._deserializeNode(data);
    return tree;
  }

  _deserializeNode(data) {
    if (!data) return null;
    const node = new DecisionTreeNode();
    node.featureIndex = data.fi;
    node.threshold = data.th;
    node.value = data.v;
    node.left = this._deserializeNode(data.l);
    node.right = this._deserializeNode(data.r);
    return node;
  }
}

// ============================================================
// Gradient Boosted Trees Ensemble
// ============================================================

class GradientBoostedTrees {
  constructor(numTrees = 50, learningRate = 0.1, maxDepth = 5) {
    this.numTrees = numTrees;
    this.learningRate = learningRate;
    this.maxDepth = maxDepth;
    this.trees = [];
    this.basePrediction = 0;
  }

  fit(X, y) {
    log.info(`Training GBT: ${this.numTrees} trees, lr=${this.learningRate}, depth=${this.maxDepth}`);
    const startTime = Date.now();

    // Initial prediction is the mean
    this.basePrediction = y.reduce((s, v) => s + v, 0) / y.length;
    let predictions = new Array(y.length).fill(this.basePrediction);

    for (let t = 0; t < this.numTrees; t++) {
      // Compute residuals
      const residuals = y.map((yi, i) => yi - predictions[i]);

      // Fit tree to residuals
      const tree = new DecisionTree(this.maxDepth, 5);
      tree.fit(X, residuals);
      this.trees.push(tree);

      // Update predictions
      const treePreds = tree.predict(X);
      for (let i = 0; i < predictions.length; i++) {
        predictions[i] += this.learningRate * treePreds[i];
      }

      if ((t + 1) % 10 === 0) {
        const mse = y.reduce((s, yi, i) => s + (yi - predictions[i]) ** 2, 0) / y.length;
        log.debug(`Tree ${t + 1}/${this.numTrees}, MSE: ${mse.toFixed(4)}`);
      }
    }

    const trainTime = Date.now() - startTime;
    const finalMse = y.reduce((s, yi, i) => s + (yi - predictions[i]) ** 2, 0) / y.length;
    log.info(`GBT training complete in ${trainTime}ms, final MSE: ${finalMse.toFixed(4)}`);

    return { mse: finalMse, trainTimeMs: trainTime };
  }

  predict(X) {
    const predictions = new Array(X.length).fill(this.basePrediction);
    for (const tree of this.trees) {
      const treePreds = tree.predict(X);
      for (let i = 0; i < predictions.length; i++) {
        predictions[i] += this.learningRate * treePreds[i];
      }
    }
    return predictions;
  }

  serialize() {
    return JSON.stringify({
      numTrees: this.numTrees,
      learningRate: this.learningRate,
      maxDepth: this.maxDepth,
      basePrediction: this.basePrediction,
      trees: this.trees.map(t => t.serialize()),
    });
  }

  static deserialize(json) {
    const data = JSON.parse(json);
    const model = new GradientBoostedTrees(data.numTrees, data.learningRate, data.maxDepth);
    model.basePrediction = data.basePrediction;
    model.trees = data.trees.map(t => DecisionTree.deserialize(t));
    return model;
  }
}

// ============================================================
// Isolation Forest (Anomaly Detection)
// ============================================================

class IsolationTree {
  constructor(maxDepth = 10) {
    this.maxDepth = maxDepth;
    this.root = null;
  }

  fit(X) {
    this.root = this._buildTree(X, 0);
  }

  pathLength(x) {
    return this._pathLength(this.root, x, 0);
  }

  _buildTree(X, depth) {
    const node = { left: null, right: null, splitFeature: null, splitValue: null, size: X.length };

    if (depth >= this.maxDepth || X.length <= 1) {
      return node;
    }

    // Random feature and random split point
    const numFeatures = X[0].length;
    const featureIdx = Math.floor(Math.random() * numFeatures);
    const featureValues = X.map(row => row[featureIdx]);
    const minVal = Math.min(...featureValues);
    const maxVal = Math.max(...featureValues);

    if (minVal === maxVal) return node;

    const splitValue = minVal + Math.random() * (maxVal - minVal);
    node.splitFeature = featureIdx;
    node.splitValue = splitValue;

    const leftData = X.filter(row => row[featureIdx] < splitValue);
    const rightData = X.filter(row => row[featureIdx] >= splitValue);

    if (leftData.length > 0) node.left = this._buildTree(leftData, depth + 1);
    if (rightData.length > 0) node.right = this._buildTree(rightData, depth + 1);

    return node;
  }

  _pathLength(node, x, depth) {
    if (!node || (!node.left && !node.right)) {
      return depth + this._c(node ? node.size : 1);
    }

    if (x[node.splitFeature] < node.splitValue) {
      return this._pathLength(node.left, x, depth + 1);
    }
    return this._pathLength(node.right, x, depth + 1);
  }

  // Average path length of unsuccessful search in BST
  _c(n) {
    if (n <= 1) return 0;
    if (n === 2) return 1;
    return 2 * (Math.log(n - 1) + 0.5772156649) - (2 * (n - 1) / n);
  }
}

class IsolationForest {
  constructor(numTrees = 100, sampleSize = 256, contamination = 0.05) {
    this.numTrees = numTrees;
    this.sampleSize = sampleSize;
    this.contamination = contamination;
    this.trees = [];
    this.threshold = 0;
  }

  fit(X) {
    log.info(`Training Isolation Forest: ${this.numTrees} trees, sample size ${this.sampleSize}`);
    const startTime = Date.now();

    const maxDepth = Math.ceil(Math.log2(this.sampleSize));

    for (let i = 0; i < this.numTrees; i++) {
      // Subsample
      const sample = [];
      const n = Math.min(this.sampleSize, X.length);
      const indices = new Set();
      while (indices.size < n) {
        indices.add(Math.floor(Math.random() * X.length));
      }
      indices.forEach(idx => sample.push(X[idx]));

      const tree = new IsolationTree(maxDepth);
      tree.fit(sample);
      this.trees.push(tree);
    }

    // Compute scores and set threshold
    const scores = this.scoreAll(X);
    scores.sort((a, b) => b - a);
    const thresholdIdx = Math.floor(scores.length * this.contamination);
    this.threshold = scores[thresholdIdx] || 0.5;

    log.info(`Isolation Forest trained in ${Date.now() - startTime}ms, threshold: ${this.threshold.toFixed(4)}`);
  }

  score(x) {
    if (this.trees.length === 0) return 0;
    const avgPathLength = this.trees.reduce((s, t) => s + t.pathLength(x), 0) / this.trees.length;
    const c = this.trees[0]._c(this.sampleSize);
    return Math.pow(2, -avgPathLength / c);
  }

  scoreAll(X) {
    return X.map(x => this.score(x));
  }

  predict(X) {
    return this.scoreAll(X).map(s => s >= this.threshold ? 1 : 0);
  }

  serialize() {
    return JSON.stringify({
      numTrees: this.numTrees,
      sampleSize: this.sampleSize,
      contamination: this.contamination,
      threshold: this.threshold,
    });
  }
}

// ============================================================
// Statistical Control Chart (Seasonal ESD baseline)
// ============================================================

class StatisticalDetector {
  constructor(windowSize = 7, numStdDev = 2.5) {
    this.windowSize = windowSize;
    this.numStdDev = numStdDev;
    this.routeBaselines = new Map();
  }

  /**
   * Compute baselines from historical data
   */
  computeBaselines(events) {
    const grouped = new Map();

    for (const e of events) {
      const key = `${e.route_id}_${e.sim_hour}_${e.day_of_week}`;
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(e.expected_revenue);
    }

    for (const [key, values] of grouped) {
      const mean = values.reduce((s, v) => s + v, 0) / values.length;
      const stddev = Math.sqrt(
        values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length
      );
      this.routeBaselines.set(key, { mean, stddev, count: values.length });
    }

    log.info(`Computed baselines for ${this.routeBaselines.size} route-hour-day combinations`);
  }

  /**
   * Score an event against its baseline
   */
  scoreEvent(event) {
    const key = `${event.route_id}_${event.sim_hour}_${event.day_of_week}`;
    const baseline = this.routeBaselines.get(key);

    if (!baseline || baseline.stddev === 0) {
      return { score: 0, zScore: 0, isAnomaly: false };
    }

    const discrepancy = event.expected_revenue - event.reported_revenue;
    const zScore = discrepancy / baseline.stddev;
    const isAnomaly = Math.abs(zScore) > this.numStdDev;

    return {
      score: Math.min(1, Math.abs(zScore) / (this.numStdDev * 2)),
      zScore,
      isAnomaly,
    };
  }
}

// ============================================================
// Model Training Pipeline
// ============================================================

function prepareTrainingData(splitRatio = 0.8) {
  const db = getDb();

  log.info('Preparing training data...');

  // Get all events with route info, using time-based split
  const allDates = db.prepare(
    'SELECT DISTINCT sim_date FROM ticketing_events ORDER BY sim_date'
  ).all().map(r => r.sim_date);

  const splitIdx = Math.floor(allDates.length * splitRatio);
  const trainDates = allDates.slice(0, splitIdx);
  const testDates = allDates.slice(splitIdx);

  log.info(`Train dates: ${trainDates.length}, Test dates: ${testDates.length}`);

  const getEvents = (dates) => {
    if (dates.length === 0) return [];
    const placeholders = dates.map(() => '?').join(',');
    return db.prepare(`
      SELECT te.*, r.route_category, s.boarding_density
      FROM ticketing_events te
      JOIN routes r ON te.route_id = r.route_id
      JOIN stops s ON te.stop_id = s.stop_id
      WHERE te.sim_date IN (${placeholders})
      ORDER BY te.event_timestamp
    `).all(...dates);
  };

  const trainEvents = getEvents(trainDates);
  const testEvents = getEvents(testDates);

  log.info(`Train events: ${trainEvents.length}, Test events: ${testEvents.length}`);

  const trainFeatures = engineerFeatures(trainEvents);
  const testFeatures = engineerFeatures(testEvents);

  return { trainFeatures, testFeatures, trainDates, testDates };
}

/**
 * Extract numeric feature matrix from feature objects
 */
function toMatrix(features, featureNames) {
  return features.map(f => featureNames.map(name => f[name] || 0));
}

const FORECAST_FEATURES = [
  'hour', 'day_of_week', 'is_weekend', 'is_peak_morning', 'is_peak_evening',
  'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos',
  'route_category_num', 'stop_sequence', 'boarding_density'
];

const ANOMALY_FEATURES = [
  'revenue_ratio', 'ticket_ratio', 'revenue_gap',
  'hour', 'is_peak_morning', 'is_peak_evening',
  'route_category_num', 'boarding_density'
];

/**
 * Train all models
 */
function trainModels() {
  log.info('Starting model training pipeline...');
  const startTime = Date.now();

  const { trainFeatures, testFeatures } = prepareTrainingData(0.8);

  if (trainFeatures.length === 0) {
    log.error('No training data available');
    return null;
  }

  // ---- Ridership Forecasting Model ----
  log.info('Training ridership forecasting model...');
  const forecastX = toMatrix(trainFeatures, FORECAST_FEATURES);
  const forecastY = trainFeatures.map(f => f.boarding_count);

  const forecastModel = new GradientBoostedTrees(30, 0.1, 5);
  const forecastMetrics = forecastModel.fit(forecastX, forecastY);

  // Evaluate on test set
  const testForecastX = toMatrix(testFeatures, FORECAST_FEATURES);
  const testForecastY = testFeatures.map(f => f.boarding_count);
  const forecastPreds = forecastModel.predict(testForecastX);

  const forecastMSE = testForecastY.reduce((s, y, i) =>
    s + (y - forecastPreds[i]) ** 2, 0) / testForecastY.length;
  const forecastRMSE = Math.sqrt(forecastMSE);
  const forecastMAE = testForecastY.reduce((s, y, i) =>
    s + Math.abs(y - forecastPreds[i]), 0) / testForecastY.length;

  log.info(`Forecast model - Test RMSE: ${forecastRMSE.toFixed(4)}, MAE: ${forecastMAE.toFixed(4)}`);

  // ---- Revenue Forecasting Model ----
  log.info('Training revenue forecasting model...');
  const revenueY = trainFeatures.map(f => f.expected_revenue);
  const revenueModel = new GradientBoostedTrees(30, 0.1, 5);
  revenueModel.fit(forecastX, revenueY);

  // ---- Anomaly Detection: Isolation Forest ----
  log.info('Training anomaly detection model (Isolation Forest)...');
  const normalFeatures = trainFeatures.filter(f => !f.is_anomalous);
  const anomalyX = toMatrix(normalFeatures, ANOMALY_FEATURES);
  const iforest = new IsolationForest(50, Math.min(256, anomalyX.length), 0.05);
  iforest.fit(anomalyX);

  // ---- Statistical Baseline Detector ----
  log.info('Computing statistical baselines...');
  const statDetector = new StatisticalDetector(7, 2.5);
  statDetector.computeBaselines(trainFeatures);

  // ---- Evaluate Anomaly Detection ----
  const testAnomalyX = toMatrix(testFeatures, ANOMALY_FEATURES);
  const anomalyScores = iforest.scoreAll(testAnomalyX);
  const anomalyPreds = anomalyScores.map(s => s >= iforest.threshold ? 1 : 0);
  const trueLabels = testFeatures.map(f => f.is_anomalous ? 1 : 0);

  let tp = 0, fp = 0, tn = 0, fn = 0;
  for (let i = 0; i < trueLabels.length; i++) {
    if (anomalyPreds[i] === 1 && trueLabels[i] === 1) tp++;
    else if (anomalyPreds[i] === 1 && trueLabels[i] === 0) fp++;
    else if (anomalyPreds[i] === 0 && trueLabels[i] === 0) tn++;
    else fn++;
  }

  const precision = tp / (tp + fp) || 0;
  const recall = tp / (tp + fn) || 0;
  const f1 = 2 * precision * recall / (precision + recall) || 0;

  log.info(`Anomaly Detection - Precision: ${precision.toFixed(4)}, Recall: ${recall.toFixed(4)}, F1: ${f1.toFixed(4)}`);

  // ---- Save Models ----
  const modelDir = config.ml.modelPath;
  if (!fs.existsSync(modelDir)) {
    fs.mkdirSync(modelDir, { recursive: true });
  }

  const modelVersion = Date.now();
  const forecastModelPath = path.join(modelDir, `forecast_v${modelVersion}.json`);
  const revenueModelPath = path.join(modelDir, `revenue_v${modelVersion}.json`);
  const anomalyModelPath = path.join(modelDir, `anomaly_v${modelVersion}.json`);

  fs.writeFileSync(forecastModelPath, forecastModel.serialize());
  fs.writeFileSync(revenueModelPath, revenueModel.serialize());
  fs.writeFileSync(anomalyModelPath, iforest.serialize());

  // Register in model registry
  const db = getDb();
  const insertModel = db.prepare(`
    INSERT OR REPLACE INTO model_registry 
    (model_id, model_type, version, metrics, model_path, is_active)
    VALUES (?, ?, ?, ?, ?, 1)
  `);

  const metricsObj = {
    forecast: { rmse: forecastRMSE, mae: forecastMAE },
    anomaly: { precision, recall, f1, tp, fp, tn, fn },
  };

  insertModel.run(`forecast_v${modelVersion}`, 'forecast', modelVersion,
    JSON.stringify(metricsObj.forecast), forecastModelPath);
  insertModel.run(`revenue_v${modelVersion}`, 'revenue', modelVersion,
    JSON.stringify(metricsObj.forecast), revenueModelPath);
  insertModel.run(`anomaly_v${modelVersion}`, 'anomaly', modelVersion,
    JSON.stringify(metricsObj.anomaly), anomalyModelPath);

  // Save to object storage
  try {
    const storage = getObjectStorage();
    storage.putObject('models', `forecast_v${modelVersion}.json`, forecastModel.serialize());
    storage.putObject('models', `revenue_v${modelVersion}.json`, revenueModel.serialize());
    storage.putObject('models', `anomaly_v${modelVersion}.json`, iforest.serialize());
  } catch (e) {
    log.warn('Could not save to object storage', { error: e.message });
  }

  const totalTime = Date.now() - startTime;
  const results = {
    modelVersion,
    trainSamples: trainFeatures.length,
    testSamples: testFeatures.length,
    forecast: { rmse: forecastRMSE, mae: forecastMAE },
    anomaly: { precision, recall, f1, tp, fp, tn, fn },
    totalTimeMs: totalTime,
  };

  log.info('Model training pipeline complete', results);

  // Save evaluation report
  try {
    const storage = getObjectStorage();
    storage.putObject('training-data', `evaluation_v${modelVersion}.json`, results);
  } catch (e) { /* non-critical */ }

  return results;
}

// ============================================================
// Inference Functions
// ============================================================

let loadedForecastModel = null;
let loadedRevenueModel = null;
let loadedAnomalyModel = null;
let loadedStatDetector = null;

function loadModels() {
  const db = getDb();

  // Load latest active models
  const forecastEntry = db.prepare(
    "SELECT * FROM model_registry WHERE model_type = 'forecast' AND is_active = 1 ORDER BY version DESC LIMIT 1"
  ).get();

  const revenueEntry = db.prepare(
    "SELECT * FROM model_registry WHERE model_type = 'revenue' AND is_active = 1 ORDER BY version DESC LIMIT 1"
  ).get();

  const anomalyEntry = db.prepare(
    "SELECT * FROM model_registry WHERE model_type = 'anomaly' AND is_active = 1 ORDER BY version DESC LIMIT 1"
  ).get();

  if (forecastEntry && fs.existsSync(forecastEntry.model_path)) {
    const data = fs.readFileSync(forecastEntry.model_path, 'utf-8');
    loadedForecastModel = GradientBoostedTrees.deserialize(data);
    log.info(`Loaded forecast model v${forecastEntry.version}`);
  }

  if (revenueEntry && fs.existsSync(revenueEntry.model_path)) {
    const data = fs.readFileSync(revenueEntry.model_path, 'utf-8');
    loadedRevenueModel = GradientBoostedTrees.deserialize(data);
    log.info(`Loaded revenue model v${revenueEntry.version}`);
  }

  // For isolation forest, we need to retrain since tree structure isn't serialized
  // Use statistical detector as primary anomaly scorer instead
  loadedStatDetector = new StatisticalDetector(7, 2.5);
  const events = db.prepare(`
    SELECT te.*, r.route_category, s.boarding_density
    FROM ticketing_events te
    JOIN routes r ON te.route_id = r.route_id
    JOIN stops s ON te.stop_id = s.stop_id
    WHERE te.is_anomalous = 0
    ORDER BY RANDOM()
    LIMIT 50000
  `).all();

  if (events.length > 0) {
    const features = engineerFeatures(events);
    loadedStatDetector.computeBaselines(features);
  }

  log.info('All models loaded for inference');
}

/**
 * Run inference on a batch of events to detect anomalies
 */
function detectAnomalies(events) {
  if (!loadedStatDetector) {
    loadModels();
  }

  const features = engineerFeatures(events);
  const results = [];

  for (const f of features) {
    const statResult = loadedStatDetector.scoreEvent(f);

    // Combine with simple ratio-based scoring
    const revenueDiscrepancy = f.expected_revenue > 0
      ? (f.expected_revenue - f.reported_revenue) / f.expected_revenue
      : 0;
    const ticketDiscrepancy = f.boarding_count > 0
      ? (f.boarding_count - f.ticket_count) / f.boarding_count
      : 0;

    // Weighted ensemble score
    const ensembleScore = Math.min(1, Math.max(0,
      statResult.score * 0.4 +
      Math.abs(revenueDiscrepancy) * 0.35 +
      Math.abs(ticketDiscrepancy) * 0.25
    ));

    results.push({
      route_id: f.route_id,
      trip_id: f.trip_id,
      stop_id: f.stop_id,
      stop_sequence: f.stop_sequence,
      sim_date: f.sim_date,
      hour: f.hour,
      anomaly_score: Math.round(ensembleScore * 10000) / 10000,
      expected_revenue: f.expected_revenue,
      reported_revenue: f.reported_revenue,
      discrepancy: Math.round((f.expected_revenue - f.reported_revenue) * 100) / 100,
      z_score: Math.round(statResult.zScore * 100) / 100,
      is_flagged: ensembleScore > 0.3,
      boarding_count: f.boarding_count,
      ticket_count: f.ticket_count,
      is_ground_truth_anomaly: f.is_anomalous,
      anomaly_id: f.anomaly_id,
    });
  }

  return results;
}

// Run directly
if (require.main === module) {
  const results = trainModels();
  if (results) {
    console.log('\n=== Training Results ===');
    console.log(JSON.stringify(results, null, 2));
  }
}

module.exports = {
  trainModels,
  loadModels,
  detectAnomalies,
  engineerFeatures,
  GradientBoostedTrees,
  IsolationForest,
  StatisticalDetector,
  FORECAST_FEATURES,
  ANOMALY_FEATURES,
};
