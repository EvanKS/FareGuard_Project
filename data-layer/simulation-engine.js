/**
 * FareGuard - Ridership & Revenue Simulation Engine
 * 
 * Core simulation module that generates realistic ticketing/revenue data
 * with configurable anomaly injection. This is the heart of the data layer.
 * 
 * Features:
 * - Baseline ridership with Poisson/negative-binomial distributions
 * - Time-of-day, day-of-week, and route-category multipliers
 * - Stop-level boarding density variation
 * - Real BMTC fare slab computation
 * - Anomaly injection: under-reporting, ghost trips, QR fraud, fare evasion clusters
 * - Historical batch mode and live-streaming mode
 */
const { v4: uuidv4 } = require('uuid');
const { getDb, initializeSchema } = require('../shared/database');
const logger = require('../shared/logger');
const config = require('../shared/config');
const { FARE_SLABS } = require('./gtfs-generator');

const log = logger.child({ service: 'simulation-engine' });

// ============================================================
// Statistical Distributions
// ============================================================

/**
 * Box-Muller transform for normal distribution
 */
function normalRandom(mean = 0, stddev = 1) {
  let u, v, s;
  do {
    u = Math.random() * 2 - 1;
    v = Math.random() * 2 - 1;
    s = u * u + v * v;
  } while (s >= 1 || s === 0);
  const mul = Math.sqrt(-2.0 * Math.log(s) / s);
  return mean + stddev * u * mul;
}

/**
 * Poisson random variable using Knuth's algorithm
 */
function poissonRandom(lambda) {
  if (lambda <= 0) return 0;
  if (lambda > 30) {
    // For large lambda, use normal approximation
    return Math.max(0, Math.round(normalRandom(lambda, Math.sqrt(lambda))));
  }
  const L = Math.exp(-lambda);
  let k = 0;
  let p = 1;
  do {
    k++;
    p *= Math.random();
  } while (p > L);
  return k - 1;
}

/**
 * Negative binomial random variable
 * Models over-dispersed count data (more realistic than Poisson for ridership)
 */
function negBinomialRandom(mean, dispersion = 1.5) {
  if (mean <= 0) return 0;
  // Gamma-Poisson mixture
  const r = mean / (dispersion - 1);
  const p = 1 / dispersion;
  // Generate gamma
  const shape = r;
  const scale = (1 - p) / p;
  let gamma;
  if (shape < 1) {
    gamma = gammaRandom(shape + 1, scale) * Math.pow(Math.random(), 1 / shape);
  } else {
    gamma = gammaRandom(shape, scale);
  }
  return poissonRandom(gamma);
}

/**
 * Gamma distribution random variable (Marsaglia and Tsang's method)
 */
function gammaRandom(shape, scale = 1) {
  if (shape < 1) {
    return gammaRandom(shape + 1, scale) * Math.pow(Math.random(), 1 / shape);
  }
  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);
  while (true) {
    let x, v;
    do {
      x = normalRandom();
      v = Math.pow(1 + c * x, 3);
    } while (v <= 0);
    const u = Math.random();
    if (u < 1 - 0.0331 * x * x * x * x) return d * v * scale;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v * scale;
  }
}

// ============================================================
// Time & Day Multipliers
// ============================================================

/**
 * Time-of-day ridership multiplier (peak hours have higher ridership)
 */
function getTimeMultiplier(hour) {
  // Morning peak: 8-10 AM
  if (hour >= 8 && hour <= 9) return 2.5;
  if (hour === 7 || hour === 10) return 1.8;
  // Evening peak: 6-8 PM
  if (hour >= 18 && hour <= 19) return 2.8;
  if (hour === 17 || hour === 20) return 1.9;
  // Midday moderate
  if (hour >= 11 && hour <= 16) return 1.2;
  // Early morning / late night
  if (hour < 6 || hour > 21) return 0.4;
  return 1.0;
}

/**
 * Day-of-week multiplier (0=Sunday, 6=Saturday)
 */
function getDayMultiplier(dayOfWeek) {
  const multipliers = {
    0: 0.55,  // Sunday - lowest
    1: 1.0,   // Monday
    2: 1.05,  // Tuesday
    3: 1.05,  // Wednesday
    4: 1.0,   // Thursday
    5: 0.95,  // Friday
    6: 0.7,   // Saturday
  };
  return multipliers[dayOfWeek] || 1.0;
}

/**
 * Route category base ridership (average boardings per stop per trip)
 */
function getCategoryBaseRidership(category) {
  const bases = {
    'city-core': 8,
    'suburban': 5,
    'feeder': 4,
    'express': 3,
    'outer': 2.5,
  };
  return bases[category] || 4;
}

// ============================================================
// Fare Computation
// ============================================================

/**
 * Calculate fare based on distance using BMTC fare slab table
 */
function calculateFare(distanceKm) {
  for (const slab of FARE_SLABS) {
    if (distanceKm >= slab.min && distanceKm < slab.max) {
      return slab.fare;
    }
  }
  return FARE_SLABS[FARE_SLABS.length - 1].fare; // Max fare
}

// ============================================================
// Anomaly Injection Module
// ============================================================

/**
 * Anomaly types and their injection logic
 */
const ANOMALY_TYPES = {
  UNDER_REPORTING: 'under_reporting',
  GHOST_TRIP: 'ghost_trip',
  QR_UPI_FRAUD: 'qr_upi_fraud',
  FARE_EVASION_CLUSTER: 'fare_evasion_cluster',
};

/**
 * Generate anomaly injection plan for a simulation run
 */
function generateAnomalyPlan(routes, simDays, anomalyRate) {
  const anomalies = [];
  const totalTrips = routes.reduce((sum, r) => {
    const tripCount = getDb().prepare(
      'SELECT COUNT(*) as cnt FROM trips WHERE route_id = ?'
    ).get(r.route_id).cnt;
    return sum + tripCount * simDays;
  }, 0);

  const numAnomalies = Math.round(totalTrips * anomalyRate);
  log.info(`Planning ${numAnomalies} anomalies across ${totalTrips} total trip-days (rate: ${anomalyRate})`);

  const typeDistribution = [
    { type: ANOMALY_TYPES.UNDER_REPORTING, weight: 0.35 },
    { type: ANOMALY_TYPES.GHOST_TRIP, weight: 0.15 },
    { type: ANOMALY_TYPES.QR_UPI_FRAUD, weight: 0.25 },
    { type: ANOMALY_TYPES.FARE_EVASION_CLUSTER, weight: 0.25 },
  ];

  for (let i = 0; i < numAnomalies; i++) {
    const route = routes[Math.floor(Math.random() * routes.length)];
    const day = Math.floor(Math.random() * simDays);

    // Select anomaly type based on distribution
    const r = Math.random();
    let cumWeight = 0;
    let selectedType = ANOMALY_TYPES.UNDER_REPORTING;
    for (const td of typeDistribution) {
      cumWeight += td.weight;
      if (r <= cumWeight) {
        selectedType = td.type;
        break;
      }
    }

    // Get route stops for segment selection
    const routeStops = getDb().prepare(`
      SELECT DISTINCT stop_id, stop_sequence, distance_from_start_km
      FROM stop_sequences 
      WHERE route_id = ?
      ORDER BY stop_sequence
      LIMIT 1
    `).get(route.route_id);

    const allStops = getDb().prepare(`
      SELECT DISTINCT s.stop_id, ss.stop_sequence, ss.distance_from_start_km
      FROM stop_sequences ss JOIN stops s ON ss.stop_id = s.stop_id
      WHERE ss.route_id = ?
      GROUP BY ss.stop_id
      ORDER BY MIN(ss.stop_sequence)
    `).all(route.route_id);

    if (allStops.length < 3) continue;

    // Select affected segment (contiguous subset of stops)
    const segStart = Math.floor(Math.random() * (allStops.length - 2));
    const segLen = Math.min(
      Math.floor(Math.random() * 6) + 2,
      allStops.length - segStart
    );
    const segEnd = segStart + segLen - 1;

    // Select time window
    const hourOptions = [7, 8, 9, 10, 14, 15, 17, 18, 19, 20];
    const startHour = hourOptions[Math.floor(Math.random() * hourOptions.length)];
    const endHour = Math.min(startHour + 2, 23);

    const severity = selectedType === ANOMALY_TYPES.GHOST_TRIP
      ? Math.random() * 0.3 + 0.7 // Ghost trips are severe (70-100%)
      : Math.random() * 0.5 + 0.2; // Others: 20-70% reduction

    const anomalyId = `ANOM_${String(i + 1).padStart(5, '0')}`;

    anomalies.push({
      anomaly_id: anomalyId,
      anomaly_type: selectedType,
      route_id: route.route_id,
      start_stop_id: allStops[segStart].stop_id,
      end_stop_id: allStops[segEnd].stop_id,
      start_stop_sequence: allStops[segStart].stop_sequence,
      end_stop_sequence: allStops[segEnd].stop_sequence,
      sim_day: day,
      time_window_start: `${String(startHour).padStart(2, '0')}:00`,
      time_window_end: `${String(endHour).padStart(2, '0')}:00`,
      severity: Math.round(severity * 100) / 100,
      magnitude: 0, // Will be computed during simulation
    });
  }

  return anomalies;
}

/**
 * Check if a specific event falls within an anomaly's scope
 */
function findMatchingAnomaly(anomalies, routeId, simDay, hour, stopSequence) {
  return anomalies.find(a =>
    a.route_id === routeId &&
    a.sim_day === simDay &&
    hour >= parseInt(a.time_window_start) &&
    hour <= parseInt(a.time_window_end) &&
    stopSequence >= a.start_stop_sequence &&
    stopSequence <= a.end_stop_sequence
  );
}

/**
 * Apply anomaly effect to reported values
 */
function applyAnomaly(anomaly, expectedBoardings, expectedRevenue, paymentMode) {
  let reportedTickets = expectedBoardings;
  let reportedRevenue = expectedRevenue;

  switch (anomaly.anomaly_type) {
    case ANOMALY_TYPES.UNDER_REPORTING:
      // Conductor reports fewer tickets than actual boardings
      const reportFraction = 1 - anomaly.severity;
      reportedTickets = Math.round(expectedBoardings * reportFraction);
      reportedRevenue = expectedRevenue * reportFraction;
      break;

    case ANOMALY_TYPES.GHOST_TRIP:
      // Trip runs but near-zero tickets reported
      reportedTickets = Math.round(expectedBoardings * 0.05);
      reportedRevenue = expectedRevenue * 0.05;
      break;

    case ANOMALY_TYPES.QR_UPI_FRAUD:
      // Digital payments diverted - only affects UPI/card payments
      if (paymentMode === 'upi' || paymentMode === 'card') {
        reportedTickets = expectedBoardings; // Tickets appear sold
        reportedRevenue = expectedRevenue * (1 - anomaly.severity); // But revenue missing
      }
      break;

    case ANOMALY_TYPES.FARE_EVASION_CLUSTER:
      // Spike in unticketed boarding at specific stops
      reportedTickets = Math.round(expectedBoardings * (1 - anomaly.severity));
      reportedRevenue = expectedRevenue * (1 - anomaly.severity);
      break;
  }

  return {
    reportedTickets: Math.max(0, reportedTickets),
    reportedRevenue: Math.max(0, Math.round(reportedRevenue * 100) / 100),
  };
}

// ============================================================
// Main Simulation Engine
// ============================================================

/**
 * Generate a single day's worth of ticketing events for all routes
 */
function simulateDay(simDate, dayIndex, routes, anomalies, db) {
  const dayOfWeek = new Date(simDate).getDay();
  const dayMult = getDayMultiplier(dayOfWeek);
  const events = [];

  const insertEvent = db.prepare(`
    INSERT OR REPLACE INTO ticketing_events 
    (event_id, trip_id, route_id, stop_id, stop_sequence, event_timestamp,
     sim_date, sim_hour, day_of_week, boarding_count, alighting_count,
     ticket_count, payment_mode, expected_revenue, reported_revenue,
     is_anomalous, anomaly_id)
    VALUES (@event_id, @trip_id, @route_id, @stop_id, @stop_sequence,
     @event_timestamp, @sim_date, @sim_hour, @day_of_week, @boarding_count,
     @alighting_count, @ticket_count, @payment_mode, @expected_revenue,
     @reported_revenue, @is_anomalous, @anomaly_id)
  `);

  for (const route of routes) {
    const baseRidership = getCategoryBaseRidership(route.route_category);

    // Get all trips for this route
    const trips = db.prepare(
      'SELECT * FROM trips WHERE route_id = ?'
    ).all(route.route_id);

    // Get stop sequence for this route (from first trip)
    if (trips.length === 0) continue;
    const stopSeqs = db.prepare(`
      SELECT ss.*, s.boarding_density 
      FROM stop_sequences ss 
      JOIN stops s ON ss.stop_id = s.stop_id 
      WHERE ss.trip_id = ?
      ORDER BY ss.stop_sequence
    `).all(trips[0].trip_id);

    for (const trip of trips) {
      // Parse trip start hour
      const startHour = parseInt(trip.scheduled_start.split(':')[0]);
      const timeMult = getTimeMultiplier(startHour);

      // Track passengers on bus for alighting calculation
      let passengersOnBus = 0;

      for (const stopSeq of stopSeqs) {
        const stopDensity = stopSeq.boarding_density || 1.0;
        const lambda = baseRidership * timeMult * dayMult * stopDensity;

        // Generate boarding count using negative binomial
        const boardings = negBinomialRandom(lambda, 1.5);

        // Alighting: fraction of passengers on bus get off
        // More get off near end of route
        const routeProgress = stopSeq.stop_sequence / stopSeqs.length;
        const alightingRate = 0.05 + routeProgress * 0.3;
        const alightings = Math.min(
          passengersOnBus,
          poissonRandom(passengersOnBus * alightingRate)
        );

        passengersOnBus = passengersOnBus - alightings + boardings;

        // Payment mode distribution
        const paymentRoll = Math.random();
        let paymentMode;
        if (paymentRoll < 0.45) paymentMode = 'cash';
        else if (paymentRoll < 0.75) paymentMode = 'upi';
        else if (paymentRoll < 0.90) paymentMode = 'card';
        else paymentMode = 'pass';

        // Calculate fare based on average trip distance for this stop
        const avgTripDist = stopSeq.distance_from_start_km || 2;
        const fare = calculateFare(Math.min(avgTripDist, 5 + Math.random() * 10));
        const expectedRevenue = boardings * fare;

        // Check for anomaly
        const matchingAnomaly = findMatchingAnomaly(
          anomalies, route.route_id, dayIndex, startHour, stopSeq.stop_sequence
        );

        let reportedTickets = boardings;
        let reportedRevenue = expectedRevenue;
        let isAnomalous = 0;
        let anomalyId = null;

        if (matchingAnomaly) {
          const result = applyAnomaly(matchingAnomaly, boardings, expectedRevenue, paymentMode);
          reportedTickets = result.reportedTickets;
          reportedRevenue = result.reportedRevenue;
          isAnomalous = 1;
          anomalyId = matchingAnomaly.anomaly_id;

          // Track magnitude for ground truth
          matchingAnomaly.magnitude += (expectedRevenue - reportedRevenue);
        } else {
          // Normal small variance (±5% noise in reported values)
          const noise = 1 + (Math.random() - 0.5) * 0.1;
          reportedRevenue = Math.round(expectedRevenue * noise * 100) / 100;
        }

        const eventHour = startHour + Math.floor(stopSeq.stop_sequence * 2 / stopSeqs.length);

        const event = {
          event_id: uuidv4(),
          trip_id: trip.trip_id,
          route_id: route.route_id,
          stop_id: stopSeq.stop_id,
          stop_sequence: stopSeq.stop_sequence,
          event_timestamp: `${simDate}T${String(Math.min(eventHour, 23)).padStart(2, '0')}:${String(Math.floor(Math.random() * 60)).padStart(2, '0')}:00`,
          sim_date: simDate,
          sim_hour: Math.min(eventHour, 23),
          day_of_week: dayOfWeek,
          boarding_count: boardings,
          alighting_count: alightings,
          ticket_count: reportedTickets,
          payment_mode: paymentMode,
          expected_revenue: Math.round(expectedRevenue * 100) / 100,
          reported_revenue: reportedRevenue,
          is_anomalous: isAnomalous,
          anomaly_id: anomalyId,
        };

        insertEvent.run(event);
        events.push(event);
      }
    }
  }

  return events;
}

/**
 * Run the full historical simulation (batch mode)
 */
function runHistoricalSimulation(numDays = 90, anomalyRate = 0.05) {
  log.info(`Starting historical simulation: ${numDays} days, anomaly rate: ${anomalyRate}`);

  const db = getDb();

  // Get all routes
  const routes = db.prepare('SELECT * FROM routes').all();
  if (routes.length === 0) {
    log.error('No routes found. Run GTFS generation first.');
    return;
  }

  log.info(`Simulating for ${routes.length} routes`);

  // Generate anomaly plan
  const anomalies = generateAnomalyPlan(routes, numDays, anomalyRate);
  log.info(`Generated ${anomalies.length} anomaly injection plans`);

  // Store anomaly ground truth
  const insertAnomaly = db.prepare(`
    INSERT OR REPLACE INTO anomaly_ground_truth 
    (anomaly_id, anomaly_type, route_id, start_stop_id, end_stop_id,
     start_stop_sequence, end_stop_sequence, time_window_start, time_window_end,
     sim_date, severity, magnitude, description)
    VALUES (@anomaly_id, @anomaly_type, @route_id, @start_stop_id, @end_stop_id,
     @start_stop_sequence, @end_stop_sequence, @time_window_start, @time_window_end,
     @sim_date, @severity, @magnitude, @description)
  `);

  // Generate dates starting from 90 days ago
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - numDays);

  const batchSize = 5; // Process 5 days at a time in transactions
  let totalEvents = 0;

  for (let d = 0; d < numDays; d += batchSize) {
    const batchEnd = Math.min(d + batchSize, numDays);

    const batchTransaction = db.transaction(() => {
      for (let day = d; day < batchEnd; day++) {
        const simDate = new Date(startDate);
        simDate.setDate(startDate.getDate() + day);
        const dateStr = simDate.toISOString().split('T')[0];

        const dayEvents = simulateDay(dateStr, day, routes, anomalies, db);
        totalEvents += dayEvents.length;

        if (day % 10 === 0) {
          log.info(`Simulated day ${day + 1}/${numDays} (${dateStr}): ${dayEvents.length} events`);
        }
      }
    });

    batchTransaction();
  }

  // Persist anomaly ground truth with computed magnitudes
  const anomalyTransaction = db.transaction(() => {
    for (const anomaly of anomalies) {
      const simDate = new Date(startDate);
      simDate.setDate(startDate.getDate() + anomaly.sim_day);

      insertAnomaly.run({
        anomaly_id: anomaly.anomaly_id,
        anomaly_type: anomaly.anomaly_type,
        route_id: anomaly.route_id,
        start_stop_id: anomaly.start_stop_id,
        end_stop_id: anomaly.end_stop_id,
        start_stop_sequence: anomaly.start_stop_sequence,
        end_stop_sequence: anomaly.end_stop_sequence,
        time_window_start: anomaly.time_window_start,
        time_window_end: anomaly.time_window_end,
        sim_date: simDate.toISOString().split('T')[0],
        severity: anomaly.severity,
        magnitude: Math.round((anomaly.magnitude || 0) * 100) / 100,
        description: `${anomaly.anomaly_type} on route ${anomaly.route_id}, stops ${anomaly.start_stop_sequence}-${anomaly.end_stop_sequence}`,
      });
    }
  });

  anomalyTransaction();

  const stats = {
    totalEvents,
    totalDays: numDays,
    totalAnomalies: anomalies.length,
    anomalyTypes: {
      under_reporting: anomalies.filter(a => a.anomaly_type === ANOMALY_TYPES.UNDER_REPORTING).length,
      ghost_trip: anomalies.filter(a => a.anomaly_type === ANOMALY_TYPES.GHOST_TRIP).length,
      qr_upi_fraud: anomalies.filter(a => a.anomaly_type === ANOMALY_TYPES.QR_UPI_FRAUD).length,
      fare_evasion_cluster: anomalies.filter(a => a.anomaly_type === ANOMALY_TYPES.FARE_EVASION_CLUSTER).length,
    },
  };

  log.info('Historical simulation complete', stats);
  return stats;
}

// ============================================================
// Live Streaming Mode
// ============================================================

/**
 * Emit events in real-time with configurable acceleration for demo
 */
function startLiveStream(accelerationFactor = 100, callback = null) {
  log.info(`Starting live stream mode (${accelerationFactor}x acceleration)`);

  const db = getDb();
  const routes = db.prepare('SELECT * FROM routes').all();
  const today = new Date().toISOString().split('T')[0];
  const anomalies = generateAnomalyPlan(routes, 1, config.simulation.anomalyRate);

  let running = true;
  let eventCount = 0;

  const emit = () => {
    if (!running) return;

    const currentHour = new Date().getHours();
    // Pick a random route and generate an event
    const route = routes[Math.floor(Math.random() * routes.length)];
    const trips = db.prepare(
      'SELECT * FROM trips WHERE route_id = ? LIMIT 1'
    ).all(route.route_id);

    if (trips.length > 0) {
      const events = simulateDay(today, 0, [route], anomalies, db);
      eventCount += events.length;

      if (callback) {
        events.forEach(e => callback(e));
      }
    }
  };

  const interval = setInterval(emit, 60000 / accelerationFactor);

  return {
    stop: () => {
      running = false;
      clearInterval(interval);
      log.info(`Live stream stopped. Emitted ${eventCount} events`);
    },
    getStats: () => ({ eventCount, running }),
  };
}

// Run directly
if (require.main === module) {
  const numDays = config.simulation.days;
  const anomalyRate = config.simulation.anomalyRate;
  runHistoricalSimulation(numDays, anomalyRate);
}

module.exports = {
  runHistoricalSimulation,
  startLiveStream,
  simulateDay,
  calculateFare,
  ANOMALY_TYPES,
  poissonRandom,
  negBinomialRandom,
  getTimeMultiplier,
  getDayMultiplier,
};
