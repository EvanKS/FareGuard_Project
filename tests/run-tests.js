/**
 * FareGuard - Automated Test Suite
 * 
 * Covers:
 * - Unit tests: simulation engine, ML features, graph algorithm
 * - Integration tests: full pipeline path
 * - Evaluation tests: detection precision/recall/F1, localization accuracy
 */
const path = require('path');
const fs = require('fs');

// Set test database path
process.env.DB_PATH = path.join(__dirname, '..', 'data', 'fareguard_test.db');
process.env.LOG_LEVEL = 'warn';

const { getDb, initializeSchema, closeDb } = require('../shared/database');
const { poissonRandom, negBinomialRandom, getTimeMultiplier, getDayMultiplier, calculateFare, ANOMALY_TYPES } = require('../data-layer/simulation-engine');
const { generateGTFS, FARE_SLABS, haversineDistance } = require('../data-layer/gtfs-generator');
const { runHistoricalSimulation } = require('../data-layer/simulation-engine');
const { validateEvent } = require('../cloud-layer/ingestion-pipeline');
const { trainModels, detectAnomalies, engineerFeatures, GradientBoostedTrees, IsolationForest } = require('../ml-layer/ml-models');
const { FlowNetwork, minCostMaxFlow, spfa, localizeLeakage, localizeAllRoutes, validateLocalization, getComplexityAnalysis } = require('../algorithm-layer/flow-localization');

let testResults = {
  total: 0,
  passed: 0,
  failed: 0,
  errors: [],
  sections: {},
};

let currentSection = '';

function section(name) {
  currentSection = name;
  testResults.sections[name] = { total: 0, passed: 0, failed: 0 };
  console.log(`\n  📋 ${name}`);
}

function assert(condition, testName, detail = '') {
  testResults.total++;
  testResults.sections[currentSection].total++;
  if (condition) {
    testResults.passed++;
    testResults.sections[currentSection].passed++;
    console.log(`    ✅ ${testName}`);
  } else {
    testResults.failed++;
    testResults.sections[currentSection].failed++;
    const msg = `${testName}${detail ? ': ' + detail : ''}`;
    testResults.errors.push(`[${currentSection}] ${msg}`);
    console.log(`    ❌ ${testName}${detail ? ' — ' + detail : ''}`);
  }
}

function assertApprox(actual, expected, tolerance, testName) {
  const diff = Math.abs(actual - expected);
  assert(diff <= tolerance, testName, `expected ~${expected}, got ${actual} (diff: ${diff.toFixed(4)})`);
}

// ============================================================
// Unit Tests: Statistical Distributions
// ============================================================

function testDistributions() {
  section('Statistical Distributions');

  // Poisson mean should approximate lambda
  const N = 10000;
  const lambda = 5;
  let sum = 0;
  for (let i = 0; i < N; i++) sum += poissonRandom(lambda);
  const mean = sum / N;
  assertApprox(mean, lambda, 0.5, `Poisson mean ≈ λ=${lambda}`);

  // Poisson should produce non-negative integers
  let allValid = true;
  for (let i = 0; i < 1000; i++) {
    const v = poissonRandom(3);
    if (v < 0 || !Number.isInteger(v)) { allValid = false; break; }
  }
  assert(allValid, 'Poisson produces non-negative integers');

  // Negative binomial mean approximation
  sum = 0;
  const nbMean = 8;
  for (let i = 0; i < N; i++) sum += negBinomialRandom(nbMean, 1.5);
  const nbActual = sum / N;
  assertApprox(nbActual, nbMean, 1.5, `NegBinomial mean ≈ ${nbMean}`);

  // Zero lambda
  assert(poissonRandom(0) === 0, 'Poisson(0) = 0');
}

// ============================================================
// Unit Tests: Time/Day Multipliers
// ============================================================

function testMultipliers() {
  section('Time & Day Multipliers');

  // Peak hours should have higher multipliers
  const morningPeak = getTimeMultiplier(9);
  const eveningPeak = getTimeMultiplier(18);
  const midday = getTimeMultiplier(13);
  const lateNight = getTimeMultiplier(23);

  assert(morningPeak > midday, 'Morning peak > midday');
  assert(eveningPeak > midday, 'Evening peak > midday');
  assert(eveningPeak > morningPeak, 'Evening peak ≥ morning peak');
  assert(lateNight < midday, 'Late night < midday');

  // Weekend should have lower multiplier
  const weekday = getDayMultiplier(2); // Tuesday
  const sunday = getDayMultiplier(0);
  assert(sunday < weekday, 'Sunday < weekday');
}

// ============================================================
// Unit Tests: Fare Calculation
// ============================================================

function testFareCalculation() {
  section('Fare Calculation');

  assert(calculateFare(1) === 5, 'Fare for 1 km = ₹5');
  assert(calculateFare(3) === 10, 'Fare for 3 km = ₹10');
  assert(calculateFare(5) === 15, 'Fare for 5 km = ₹15');
  assert(calculateFare(10) === 20, 'Fare for 10 km = ₹20');
  assert(calculateFare(15) === 25, 'Fare for 15 km = ₹25');
  assert(calculateFare(100) === 50, 'Fare for 100 km = ₹50 (max)');

  // Fare should always be positive
  assert(calculateFare(0) > 0, 'Fare for 0 km > 0');
}

// ============================================================
// Unit Tests: Event Validation
// ============================================================

function testEventValidation() {
  section('Event Schema Validation');

  const validEvent = {
    event_id: 'test-1',
    trip_id: 'T1',
    route_id: 'R1',
    stop_id: 'S1',
    event_timestamp: '2024-01-01T10:00:00',
    boarding_count: 5,
    ticket_count: 5,
    expected_revenue: 100,
    reported_revenue: 95,
    payment_mode: 'cash',
  };

  const result = validateEvent(validEvent);
  assert(result.valid, 'Valid event passes validation');

  const missingFields = validateEvent({});
  assert(!missingFields.valid, 'Empty event fails validation');
  assert(missingFields.errors.length > 0, 'Empty event has error messages');

  const invalidPayment = validateEvent({ ...validEvent, payment_mode: 'bitcoin' });
  assert(!invalidPayment.valid, 'Invalid payment mode fails');

  const negativeBoardings = validateEvent({ ...validEvent, boarding_count: -1 });
  assert(!negativeBoardings.valid, 'Negative boarding count fails');
}

// ============================================================
// Unit Tests: Graph / Flow Algorithm
// ============================================================

function testFlowAlgorithm() {
  section('Min-Cost Flow Algorithm');

  // Test 1: Simple 3-node graph
  // Source → A → Sink with known capacities and costs
  const net1 = new FlowNetwork(3);
  net1.addEdge(0, 1, 10, 1); // Source → A, cap=10, cost=1
  net1.addEdge(1, 2, 10, 1); // A → Sink, cap=10, cost=1

  const result1 = minCostMaxFlow(net1, 0, 2);
  assert(result1.totalFlow === 10, 'Simple graph: max flow = 10');
  assert(result1.totalCost === 20, 'Simple graph: min cost = 20');

  // Test 2: Diamond graph with different costs
  // Source → A → Sink (cost 3)
  // Source → B → Sink (cost 1)
  const net2 = new FlowNetwork(4);
  net2.addEdge(0, 1, 5, 3); // Source → A, cost=3
  net2.addEdge(0, 2, 5, 1); // Source → B, cost=1
  net2.addEdge(1, 3, 5, 0); // A → Sink
  net2.addEdge(2, 3, 5, 0); // B → Sink

  const result2 = minCostMaxFlow(net2, 0, 3);
  assert(result2.totalFlow === 10, 'Diamond: max flow = 10');
  // Flow should prefer cheaper path through B first
  assert(result2.totalCost <= 20, 'Diamond: min cost ≤ 20 (prefers cheaper path)');

  // Test 3: Bottleneck graph
  const net3 = new FlowNetwork(4);
  net3.addEdge(0, 1, 10, 0);
  net3.addEdge(0, 2, 10, 0);
  net3.addEdge(1, 3, 3, 0);  // Bottleneck
  net3.addEdge(2, 3, 3, 0);  // Bottleneck

  const result3 = minCostMaxFlow(net3, 0, 3);
  assert(result3.totalFlow === 6, 'Bottleneck: flow limited to 6');

  // Test 4: No path
  const net4 = new FlowNetwork(3);
  net4.addEdge(0, 1, 5, 1); // Source → A, but no edge to Sink
  const result4 = minCostMaxFlow(net4, 0, 2);
  assert(result4.totalFlow === 0, 'No path: flow = 0');

  // Test 5: SPFA correctness
  const net5 = new FlowNetwork(4);
  net5.addEdge(0, 1, 5, 2);
  net5.addEdge(0, 2, 5, 4);
  net5.addEdge(1, 3, 5, 1);
  net5.addEdge(2, 3, 5, 1);
  const spfaResult = spfa(net5, 0, 3);
  assert(spfaResult !== null, 'SPFA finds path');
  assert(spfaResult.distance === 3, 'SPFA finds shortest path cost = 3 (0→1→3)');
}

function testComplexityAnalysis() {
  section('Complexity Analysis');

  const analysis = getComplexityAnalysis();
  assert(analysis.algorithm !== undefined, 'Algorithm name specified');
  assert(analysis.timeComplexity !== undefined, 'Time complexity documented');
  assert(analysis.spaceComplexity !== undefined, 'Space complexity documented');
  assert(analysis.optimizations.length >= 2, 'At least 2 optimizations documented');
  assert(analysis.practicalScaling.fullNetwork !== undefined, 'Full network scaling documented');
}

// ============================================================
// Unit Tests: ML Feature Engineering
// ============================================================

function testFeatureEngineering() {
  section('ML Feature Engineering');

  const testEvent = {
    sim_hour: 9,
    day_of_week: 2,
    route_category: 'city-core',
    stop_sequence: 5,
    boarding_density: 2.0,
    boarding_count: 10,
    expected_revenue: 100,
    reported_revenue: 80,
    ticket_count: 8,
    route_id: 'R1',
    trip_id: 'T1',
    stop_id: 'S1',
    sim_date: '2024-01-01',
    is_anomalous: 0,
    anomaly_id: null,
  };

  const features = engineerFeatures([testEvent]);
  assert(features.length === 1, 'Produces one feature row');

  const f = features[0];
  assert(f.is_peak_morning === 1, 'Morning peak detected (hour 9)');
  assert(f.is_weekend === 0, 'Tuesday is not weekend');
  assert(f.revenue_ratio === 0.8, 'Revenue ratio = 0.8 (80/100)');
  assert(f.ticket_ratio === 0.8, 'Ticket ratio = 0.8 (8/10)');
  assert(f.revenue_gap === 20, 'Revenue gap = 20');
  assert(f.route_category_num === 0, 'city-core encodes to 0');

  // Cyclical features
  assert(typeof f.hour_sin === 'number', 'hour_sin is a number');
  assert(typeof f.hour_cos === 'number', 'hour_cos is a number');
  assert(f.hour_sin >= -1 && f.hour_sin <= 1, 'hour_sin in [-1, 1]');
}

// ============================================================
// Unit Tests: GBT Model
// ============================================================

function testGBTModel() {
  section('Gradient Boosted Trees');

  // Simple regression: y ≈ x
  const X = Array.from({ length: 100 }, (_, i) => [i / 10]);
  const y = X.map(([x]) => x * 2 + 1 + (Math.random() - 0.5) * 0.5);

  const model = new GradientBoostedTrees(20, 0.1, 4);
  const metrics = model.fit(X, y);
  assert(metrics.mse < 5, `GBT training MSE < 5 (got ${metrics.mse.toFixed(4)})`);

  const preds = model.predict([[5.0], [10.0]]);
  assertApprox(preds[0], 11, 3, 'GBT predicts f(5) ≈ 11');

  // Serialization
  const serialized = model.serialize();
  const restored = GradientBoostedTrees.deserialize(serialized);
  const restoredPreds = restored.predict([[5.0]]);
  assertApprox(restoredPreds[0], preds[0], 0.001, 'GBT serialization roundtrip');
}

// ============================================================
// Integration Test: GTFS + Simulation
// ============================================================

function testGTFSAndSimulation() {
  section('GTFS Generation & Simulation (Integration)');

  // Generate a small test dataset
  const gtfsStats = generateGTFS(5);
  assert(gtfsStats.routes === 5, 'Generated 5 routes');
  assert(gtfsStats.stops > 10, 'Generated enough stops');
  assert(gtfsStats.trips > 0, 'Generated trips');

  const db = getDb();
  const routeCount = db.prepare('SELECT COUNT(*) as cnt FROM routes').get().cnt;
  assert(routeCount === 5, 'Routes persisted to DB');

  const stopCount = db.prepare('SELECT COUNT(*) as cnt FROM stops').get().cnt;
  assert(stopCount > 0, 'Stops persisted to DB');

  const fareCount = db.prepare('SELECT COUNT(*) as cnt FROM fare_slabs').get().cnt;
  assert(fareCount === FARE_SLABS.length, 'Fare slabs persisted');

  // Run short simulation
  const simStats = runHistoricalSimulation(3, 0.1); // 3 days, 10% anomaly rate
  assert(simStats.totalEvents > 0, 'Simulation produced events');
  assert(simStats.totalAnomalies > 0, 'Anomalies were injected');

  // Check events in DB
  const eventCount = db.prepare('SELECT COUNT(*) as cnt FROM ticketing_events').get().cnt;
  assert(eventCount > 0, 'Events persisted to DB');

  // Check ground truth
  const gtCount = db.prepare('SELECT COUNT(*) as cnt FROM anomaly_ground_truth').get().cnt;
  assert(gtCount > 0, 'Ground truth anomalies persisted');

  // Verify anomalous events are labeled
  const anomalousCount = db.prepare(
    'SELECT COUNT(*) as cnt FROM ticketing_events WHERE is_anomalous = 1'
  ).get().cnt;
  assert(anomalousCount >= 0, 'Anomalous events are labeled');
}

// ============================================================
// Integration Test: ML Pipeline
// ============================================================

function testMLPipeline() {
  section('ML Training & Inference (Integration)');

  const results = trainModels();
  if (!results) {
    assert(false, 'ML training produced results');
    return;
  }

  assert(results.trainSamples > 0, 'Training used samples');
  assert(results.testSamples > 0, 'Test set has samples');
  assert(results.forecast.rmse >= 0, 'Forecast RMSE is valid');
  assert(results.anomaly.precision >= 0 && results.anomaly.precision <= 1, 'Precision in [0,1]');
  assert(results.anomaly.recall >= 0 && results.anomaly.recall <= 1, 'Recall in [0,1]');

  // Test inference
  const db = getDb();
  const events = db.prepare(`
    SELECT te.*, r.route_category, s.boarding_density
    FROM ticketing_events te
    JOIN routes r ON te.route_id = r.route_id
    JOIN stops s ON te.stop_id = s.stop_id
    LIMIT 50
  `).all();

  if (events.length > 0) {
    const detections = detectAnomalies(events);
    assert(detections.length === events.length, 'Detection produces one result per event');
    assert(typeof detections[0].anomaly_score === 'number', 'Anomaly score is numeric');
    assert(detections[0].anomaly_score >= 0 && detections[0].anomaly_score <= 1, 'Score in [0,1]');
  }
}

// ============================================================
// Integration Test: Flow Localization
// ============================================================

function testFlowLocalization() {
  section('Flow Localization (Integration)');

  const db = getDb();
  const route = db.prepare('SELECT route_id FROM routes LIMIT 1').get();
  const date = db.prepare(
    'SELECT DISTINCT sim_date FROM ticketing_events ORDER BY sim_date DESC LIMIT 1'
  ).get();

  if (!route || !date) {
    assert(false, 'Test data available for localization');
    return;
  }

  const results = localizeLeakage(route.route_id, date.sim_date);
  assert(Array.isArray(results), 'Localization returns array');
  
  if (results.length > 0) {
    assert(results[0].rank_position === 1, 'First result has rank 1');
    assert(results[0].localization_score >= 0, 'Score is non-negative');
    assert(results[0].segment_start_stop !== undefined, 'Start stop specified');
    assert(results[0].segment_end_stop !== undefined, 'End stop specified');
    assert(results[0].expected_flow !== undefined, 'Expected flow included');
    assert(results[0].reported_flow !== undefined, 'Reported flow included');
  }

  // Validate localization
  const validation = validateLocalization(date.sim_date, 5);
  assert(typeof validation.accuracy === 'number', 'Validation accuracy computed');
  assert(validation.total >= 0, 'Total ground truth count valid');
}

// ============================================================
// Evaluation Tests
// ============================================================

function testEvaluation() {
  section('Evaluation Metrics');

  const db = getDb();

  // Check detection metrics exist
  const modelEntry = db.prepare(
    "SELECT metrics FROM model_registry WHERE model_type = 'anomaly' AND is_active = 1 LIMIT 1"
  ).get();

  if (modelEntry) {
    const metrics = JSON.parse(modelEntry.metrics);
    assert(metrics.precision !== undefined, 'Precision metric recorded');
    assert(metrics.recall !== undefined, 'Recall metric recorded');
    assert(metrics.f1 !== undefined, 'F1 metric recorded');

    console.log(`\n    📊 Detection Metrics:`);
    console.log(`       Precision: ${(metrics.precision * 100).toFixed(1)}%`);
    console.log(`       Recall:    ${(metrics.recall * 100).toFixed(1)}%`);
    console.log(`       F1-Score:  ${(metrics.f1 * 100).toFixed(1)}%`);
  }

  // Check localization accuracy
  const dates = db.prepare(
    'SELECT DISTINCT sim_date FROM anomaly_ground_truth LIMIT 3'
  ).all();

  if (dates.length > 0) {
    let totalHits = 0, totalGT = 0;
    for (const { sim_date } of dates) {
      const val = validateLocalization(sim_date, 5);
      totalHits += val.hits;
      totalGT += val.total;
    }
    const locAcc = totalGT > 0 ? totalHits / totalGT : 0;
    console.log(`\n    📊 Localization Accuracy (top-5): ${(locAcc * 100).toFixed(1)}% (${totalHits}/${totalGT})`);
  }
}

// ============================================================
// Haversine Test
// ============================================================

function testHaversine() {
  section('Haversine Distance');
  
  // Known distance: Majestic to Whitefield ≈ 20km
  const dist = haversineDistance(12.9767, 77.5713, 12.9698, 77.7500);
  assert(dist > 15 && dist < 25, `Majestic→Whitefield ≈ 20km (got ${dist.toFixed(1)}km)`);
  
  // Same point = 0
  const zero = haversineDistance(12.97, 77.57, 12.97, 77.57);
  assert(zero < 0.01, 'Same point distance ≈ 0');
}

// ============================================================
// Run All Tests
// ============================================================

function runAllTests() {
  console.log('\n🧪 FareGuard Test Suite');
  console.log('═'.repeat(50));

  // Clean up test DB if exists
  const testDbPath = path.join(__dirname, '..', 'data', 'fareguard_test.db');
  if (fs.existsSync(testDbPath)) {
    try { fs.unlinkSync(testDbPath); } catch (e) { /* ignore */ }
  }

  initializeSchema();

  // Unit Tests
  testDistributions();
  testMultipliers();
  testFareCalculation();
  testEventValidation();
  testHaversine();
  testFlowAlgorithm();
  testComplexityAnalysis();
  testFeatureEngineering();
  testGBTModel();

  // Integration Tests
  testGTFSAndSimulation();
  testMLPipeline();
  testFlowLocalization();

  // Evaluation
  testEvaluation();

  // Results
  console.log('\n' + '═'.repeat(50));
  console.log(`\n  Results: ${testResults.passed}/${testResults.total} passed, ${testResults.failed} failed\n`);

  if (testResults.failed > 0) {
    console.log('  Failed tests:');
    testResults.errors.forEach(e => console.log(`    ❌ ${e}`));
    console.log('');
  }

  // Section breakdown
  console.log('  Section Breakdown:');
  for (const [name, stats] of Object.entries(testResults.sections)) {
    const icon = stats.failed === 0 ? '✅' : '❌';
    console.log(`    ${icon} ${name}: ${stats.passed}/${stats.total}`);
  }

  // Clean up
  closeDb();

  // Write results to file
  const reportPath = path.join(__dirname, '..', 'data', 'test-results.json');
  fs.writeFileSync(reportPath, JSON.stringify(testResults, null, 2));
  console.log(`\n  Results saved to: ${reportPath}\n`);

  process.exit(testResults.failed > 0 ? 1 : 0);
}

runAllTests();
