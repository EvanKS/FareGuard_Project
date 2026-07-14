/**
 * FareGuard - Full Pipeline Orchestrator
 * 
 * Orchestrates the entire end-to-end pipeline:
 * 1. GTFS data generation
 * 2. Historical simulation
 * 3. ML model training
 * 4. Anomaly detection
 * 5. Flow localization
 * 6. Route leakage scoring
 * 
 * Can be run as a single command to initialize the full system.
 */
const { initializeSchema, getDb } = require('../shared/database');
const logger = require('../shared/logger');
const config = require('../shared/config');
const { generateGTFS } = require('../data-layer/gtfs-generator');
const { runHistoricalSimulation } = require('../data-layer/simulation-engine');
const { trainModels, detectAnomalies, loadModels } = require('../ml-layer/ml-models');
const { localizeAllRoutes, validateLocalization } = require('../algorithm-layer/flow-localization');
const { getObjectStorage } = require('../cloud-layer/ingestion-pipeline');
const { v4: uuidv4 } = require('uuid');

const log = logger.child({ service: 'pipeline' });

/**
 * Run the complete pipeline end-to-end
 */
async function runFullPipeline() {
  const startTime = Date.now();
  log.info('=== Starting FareGuard Full Pipeline ===');

  const results = {
    phases: {},
    totalTimeMs: 0,
    success: true,
  };

  try {
    // Phase 1: Initialize database
    log.info('--- Phase 1: Database Initialization ---');
    let phaseStart = Date.now();
    initializeSchema();
    results.phases.dbInit = { timeMs: Date.now() - phaseStart, status: 'success' };

    // Phase 2: GTFS Data Generation
    log.info('--- Phase 2: GTFS Data Generation ---');
    phaseStart = Date.now();
    const gtfsStats = generateGTFS(config.simulation.routesSubset);
    results.phases.gtfs = {
      timeMs: Date.now() - phaseStart,
      status: 'success',
      stats: gtfsStats,
    };

    // Phase 3: Historical Simulation
    log.info('--- Phase 3: Historical Simulation ---');
    phaseStart = Date.now();
    const simStats = runHistoricalSimulation(
      config.simulation.days,
      config.simulation.anomalyRate
    );
    results.phases.simulation = {
      timeMs: Date.now() - phaseStart,
      status: 'success',
      stats: simStats,
    };

    // Phase 4: ML Model Training
    log.info('--- Phase 4: ML Model Training ---');
    phaseStart = Date.now();
    const mlResults = trainModels();
    results.phases.mlTraining = {
      timeMs: Date.now() - phaseStart,
      status: 'success',
      stats: mlResults,
    };

    // Phase 5: Anomaly Detection (on recent data)
    log.info('--- Phase 5: Anomaly Detection ---');
    phaseStart = Date.now();
    loadModels();

    const db = getDb();
    const recentDates = db.prepare(`
      SELECT DISTINCT sim_date FROM ticketing_events 
      ORDER BY sim_date DESC LIMIT 7
    `).all();

    let totalDetections = 0;
    for (const { sim_date } of recentDates) {
      const events = db.prepare(`
        SELECT te.*, r.route_category, s.boarding_density
        FROM ticketing_events te
        JOIN routes r ON te.route_id = r.route_id
        JOIN stops s ON te.stop_id = s.stop_id
        WHERE te.sim_date = ?
      `).all(sim_date);

      const detections = detectAnomalies(events);
      const flagged = detections.filter(d => d.is_flagged);

      // Store detected anomalies
      const insertDetection = db.prepare(`
        INSERT OR REPLACE INTO detected_anomalies
        (detection_id, anomaly_score, route_id, trip_id, stop_id, stop_sequence,
         segment_start_stop, segment_end_stop, time_window, sim_date,
         detection_type, expected_value, reported_value, discrepancy,
         matched_ground_truth_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
      `);

      const detectTransaction = db.transaction(() => {
        for (const d of flagged) {
          insertDetection.run(
            uuidv4(), d.anomaly_score, d.route_id, d.trip_id,
            d.stop_id, d.stop_sequence,
            d.stop_id, d.stop_id,
            `${d.hour}:00-${d.hour + 1}:00`, d.sim_date,
            'ml_ensemble', d.expected_revenue, d.reported_revenue,
            d.discrepancy, d.anomaly_id
          );
        }
      });

      detectTransaction();
      totalDetections += flagged.length;
    }

    results.phases.anomalyDetection = {
      timeMs: Date.now() - phaseStart,
      status: 'success',
      stats: { totalDetections, daysProcessed: recentDates.length },
    };

    // Phase 6: Flow Localization
    log.info('--- Phase 6: Flow Localization ---');
    phaseStart = Date.now();

    let totalLocalizations = 0;
    const localizationValidation = [];

    for (const { sim_date } of recentDates.slice(0, 3)) {
      try {
        const locResults = localizeAllRoutes(sim_date);
        totalLocalizations += Object.values(locResults).reduce((s, r) => s + r.length, 0);

        const validation = validateLocalization(sim_date, 5);
        localizationValidation.push({ date: sim_date, ...validation });
      } catch (e) {
        log.error(`Localization failed for ${sim_date}`, { error: e.message });
      }
    }

    results.phases.localization = {
      timeMs: Date.now() - phaseStart,
      status: 'success',
      stats: { totalLocalizations, validation: localizationValidation },
    };

    // Phase 7: Compute Route Leakage Scores
    log.info('--- Phase 7: Route Leakage Scoring ---');
    phaseStart = Date.now();
    computeRouteLeakageScores(db);
    results.phases.leakageScoring = {
      timeMs: Date.now() - phaseStart,
      status: 'success',
    };

  } catch (error) {
    log.error('Pipeline failed', { error: error.message, stack: error.stack });
    results.success = false;
    results.error = error.message;
  }

  results.totalTimeMs = Date.now() - startTime;
  log.info('=== FareGuard Pipeline Complete ===', {
    totalTimeMs: results.totalTimeMs,
    success: results.success,
  });

  // Save results to object storage
  try {
    const storage = getObjectStorage();
    storage.putObject('logs', `pipeline_run_${Date.now()}.json`, results);
  } catch (e) { /* non-critical */ }

  return results;
}

/**
 * Compute aggregated leakage scores per route
 */
function computeRouteLeakageScores(db) {
  const routeDates = db.prepare(`
    SELECT DISTINCT route_id, sim_date 
    FROM ticketing_events 
    ORDER BY sim_date DESC
    LIMIT 5000
  `).all();

  const insertScore = db.prepare(`
    INSERT OR REPLACE INTO route_leakage_scores
    (route_id, sim_date, time_window, expected_revenue, reported_revenue,
     leakage_amount, leakage_percentage, risk_level, anomaly_count)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const grouped = new Map();
  for (const rd of routeDates) {
    const key = `${rd.route_id}_${rd.sim_date}`;
    if (!grouped.has(key)) grouped.set(key, rd);
  }

  const transaction = db.transaction(() => {
    for (const [, rd] of grouped) {
      const agg = db.prepare(`
        SELECT 
          COALESCE(SUM(expected_revenue), 0) as total_expected,
          COALESCE(SUM(reported_revenue), 0) as total_reported,
          SUM(CASE WHEN is_anomalous = 1 THEN 1 ELSE 0 END) as anomaly_count
        FROM ticketing_events
        WHERE route_id = ? AND sim_date = ?
      `).get(rd.route_id, rd.sim_date);

      const leakage = agg.total_expected - agg.total_reported;
      const leakagePct = agg.total_expected > 0 ? (leakage / agg.total_expected) * 100 : 0;

      let riskLevel = 'low';
      if (leakagePct > 15) riskLevel = 'critical';
      else if (leakagePct > 8) riskLevel = 'high';
      else if (leakagePct > 3) riskLevel = 'medium';

      insertScore.run(
        rd.route_id, rd.sim_date, 'full_day',
        agg.total_expected, agg.total_reported,
        Math.round(leakage * 100) / 100,
        Math.round(leakagePct * 100) / 100,
        riskLevel, agg.anomaly_count
      );
    }
  });

  transaction();
  log.info(`Computed leakage scores for ${grouped.size} route-date combinations`);
}

// Run directly
if (require.main === module) {
  runFullPipeline().then(results => {
    console.log('\n=== Pipeline Results ===');
    console.log(JSON.stringify(results, null, 2));
    process.exit(results.success ? 0 : 1);
  });
}

module.exports = { runFullPipeline, computeRouteLeakageScores };
