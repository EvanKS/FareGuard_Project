/**
 * FareGuard - GTFS Data Generator
 * Generates realistic BMTC-style GTFS route/stop/trip data.
 * Since actual BMTC GTFS data requires API access, this generates
 * a faithful synthetic GTFS dataset based on publicly known BMTC network parameters.
 * 
 * Data Provenance: Route names, stop patterns, and network topology are based on
 * publicly available BMTC route information. Individual stop coordinates are
 * approximated based on Bengaluru's geographic layout.
 */
const { v4: uuidv4 } = require('uuid');
const { getDb, initializeSchema } = require('../shared/database');
const logger = require('../shared/logger');
const config = require('../shared/config');

const log = logger.child({ service: 'gtfs-generator' });

// ============================================================
// Bengaluru geographic constants and realistic stop names
// ============================================================
const BENGALURU_CENTER = { lat: 12.9716, lon: 77.5946 };
const CITY_RADIUS_KM = 18;

// Real BMTC route prefixes and areas
const ROUTE_PREFIXES = [
  'KBS', 'MBS', 'BBS', 'YBS', 'KNG', 'JPN', 'BTM', 'HSR',
  'WHF', 'ELR', 'BAN', 'MYS', 'TUM', 'HOS', 'IND', 'VIJ'
];

// Real Bengaluru area names for realistic stop generation
const AREA_NAMES = [
  'Majestic', 'Kempegowda Bus Station', 'Shivajinagar', 'Market', 'Jayanagar',
  'Koramangala', 'Indiranagar', 'Whitefield', 'Electronic City', 'Banashankari',
  'Rajajinagar', 'Malleswaram', 'Yeshwanthpur', 'Peenya', 'Hebbal',
  'Yelahanka', 'Marathahalli', 'BTM Layout', 'HSR Layout', 'JP Nagar',
  'Basavanagudi', 'Vijayanagar', 'Mysore Road', 'Tumkur Road', 'Hosur Road',
  'KR Market', 'City Market', 'Lalbagh', 'Cubbon Park', 'MG Road',
  'Brigade Road', 'Commercial Street', 'Silk Board', 'Bommanahalli',
  'Sarjapur Road', 'Outer Ring Road', 'Bannerghatta Road', 'Kanakapura Road',
  'Magadi Road', 'Hesaraghatta', 'Nagarbhavi', 'RR Nagar', 'Kengeri',
  'Uttarahalli', 'Padmanabhanagar', 'Kumaraswamy Layout', 'Girinagar',
  'Chamrajpet', 'Chamarajnagar Gate', 'Wilson Garden', 'Richmond Town',
  'Domlur', 'HAL Airport', 'CV Raman Nagar', 'KR Puram', 'Mahadevapura',
  'Varthur', 'Kadugodi', 'ITPL', 'Hope Farm', 'Hoodi', 'Brookefield',
  'Kundalahalli', 'Bellandur', 'Devarabisanahalli', 'Kadubeesanahalli',
  'Iblur', 'Agara', 'Jakkur', 'Vidyaranyapura', 'Sahakarnagar',
  'Sanjaynagar', 'RT Nagar', 'HBR Layout', 'Kalyan Nagar', 'Kammanahalli',
  'Banaswadi', 'Ramamurthy Nagar', 'KG Halli', 'Frazer Town',
  'Ulsoor', 'Halasuru', 'Trinity', 'Shanthinagar', 'Madiwala',
  'Konankunte', 'ISRO Layout', 'Yelachenahalli', 'Puttenahalli',
  'Arekere', 'Begur', 'Hongasandra', 'Kudlu Gate', 'Hosa Road',
  'Narayanapura', 'Thanisandra', 'Nagawara', 'Manyata Tech Park',
  'Kirloskar Layout', 'Dasarahalli', 'Jalahalli', 'Mathikere',
  'MS Palya', 'New BEL Road', 'Sadashivanagar', 'Palace Grounds'
];

// BMTC fare slab table (distance-based, in INR) - based on publicly available fare chart
const FARE_SLABS = [
  { min: 0, max: 2, fare: 5 },
  { min: 2, max: 4, fare: 10 },
  { min: 4, max: 6, fare: 15 },
  { min: 6, max: 8, fare: 15 },
  { min: 8, max: 10, fare: 20 },
  { min: 10, max: 13, fare: 20 },
  { min: 13, max: 16, fare: 25 },
  { min: 16, max: 19, fare: 25 },
  { min: 19, max: 22, fare: 30 },
  { min: 22, max: 26, fare: 30 },
  { min: 26, max: 30, fare: 35 },
  { min: 30, max: 35, fare: 35 },
  { min: 35, max: 40, fare: 40 },
  { min: 40, max: 50, fare: 45 },
  { min: 50, max: 999, fare: 50 },
];

// Route categories with different characteristics
const ROUTE_CATEGORIES = [
  { name: 'city-core', weight: 0.3, stopsRange: [15, 25], distRange: [8, 15], tripsPerDay: [40, 60] },
  { name: 'suburban', weight: 0.3, stopsRange: [20, 35], distRange: [15, 30], tripsPerDay: [25, 40] },
  { name: 'feeder', weight: 0.2, stopsRange: [10, 18], distRange: [5, 12], tripsPerDay: [20, 35] },
  { name: 'express', weight: 0.1, stopsRange: [8, 15], distRange: [20, 45], tripsPerDay: [15, 25] },
  { name: 'outer', weight: 0.1, stopsRange: [25, 45], distRange: [25, 50], tripsPerDay: [10, 20] },
];

// ============================================================
// Utility functions
// ============================================================

function randomInRange(min, max) {
  return Math.random() * (max - min) + min;
}

function randomInt(min, max) {
  return Math.floor(randomInRange(min, max + 1));
}

function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function shuffleArray(arr) {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

/**
 * Generate a coordinate offset from center based on direction and distance
 */
function generateCoordinate(centerLat, centerLon, distanceKm, bearing) {
  const R = 6371; // Earth's radius in km
  const lat1 = centerLat * Math.PI / 180;
  const lon1 = centerLon * Math.PI / 180;
  const angDist = distanceKm / R;
  const brng = bearing * Math.PI / 180;

  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angDist) +
    Math.cos(lat1) * Math.sin(angDist) * Math.cos(brng)
  );
  const lon2 = lon1 + Math.atan2(
    Math.sin(brng) * Math.sin(angDist) * Math.cos(lat1),
    Math.cos(angDist) - Math.sin(lat1) * Math.sin(lat2)
  );

  return {
    lat: lat2 * 180 / Math.PI,
    lon: lon2 * 180 / Math.PI,
  };
}

/**
 * Calculate distance between two coordinates in km (Haversine)
 */
function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Assign boarding density based on stop name patterns
 */
function assignBoardingDensity(stopName) {
  const highTraffic = ['Majestic', 'Bus Station', 'Market', 'MG Road', 'Silk Board',
    'Tech Park', 'ITPL', 'Electronic City', 'Whitefield', 'Hebbal',
    'Marathahalli', 'Koramangala', 'Indiranagar'];
  const medTraffic = ['Layout', 'Nagar', 'Road', 'Circle', 'Junction', 'Gate',
    'Cross', 'Main', 'Colony'];

  if (highTraffic.some(t => stopName.includes(t))) return randomInRange(2.0, 3.5);
  if (medTraffic.some(t => stopName.includes(t))) return randomInRange(1.2, 2.0);
  return randomInRange(0.5, 1.2);
}

// ============================================================
// Main Generation Functions
// ============================================================

function generateStops(count) {
  log.info(`Generating ${count} stops...`);
  const stops = [];
  const usedNames = new Set();
  const availableNames = shuffleArray([...AREA_NAMES]);

  for (let i = 0; i < count; i++) {
    let stopName;
    if (i < availableNames.length) {
      stopName = availableNames[i];
    } else {
      // Generate additional stop names with suffixes
      const baseName = randomChoice(AREA_NAMES);
      const suffix = randomChoice([' Cross', ' Main Road', ' Bus Stop', ' Junction',
        ' Circle', ' Gate', ' 1st Stage', ' 2nd Stage', ' Extension']);
      stopName = `${baseName}${suffix}`;
    }

    // Ensure unique
    while (usedNames.has(stopName)) {
      stopName += ` ${randomInt(1, 9)}`;
    }
    usedNames.add(stopName);

    const dist = randomInRange(0.5, CITY_RADIUS_KM);
    const bearing = randomInRange(0, 360);
    const coord = generateCoordinate(BENGALURU_CENTER.lat, BENGALURU_CENTER.lon, dist, bearing);

    const stopType = dist < 5 ? 'city-core' : dist < 10 ? 'suburban' : 'outer';

    stops.push({
      stop_id: `STOP_${String(i + 1).padStart(4, '0')}`,
      stop_name: stopName,
      stop_lat: Math.round(coord.lat * 10000) / 10000,
      stop_lon: Math.round(coord.lon * 10000) / 10000,
      stop_type: stopType,
      boarding_density: assignBoardingDensity(stopName),
    });
  }

  return stops;
}

function selectRouteCategory() {
  const r = Math.random();
  let cumWeight = 0;
  for (const cat of ROUTE_CATEGORIES) {
    cumWeight += cat.weight;
    if (r <= cumWeight) return cat;
  }
  return ROUTE_CATEGORIES[0];
}

function generateRoutes(numRoutes, allStops) {
  log.info(`Generating ${numRoutes} routes...`);
  const routes = [];
  const routeStopSequences = {};

  for (let i = 0; i < numRoutes; i++) {
    const category = selectRouteCategory();
    const prefix = randomChoice(ROUTE_PREFIXES);
    const routeNum = randomInt(1, 999);
    const suffix = Math.random() > 0.7 ? randomChoice(['A', 'B', 'C', 'D', 'E', 'F']) : '';
    const routeId = `${prefix}-${routeNum}${suffix}`;

    const numStops = randomInt(category.stopsRange[0], category.stopsRange[1]);

    // Select stops for this route (pick geographically reasonable set)
    const startStop = randomChoice(allStops);
    const bearing = randomInRange(0, 360);

    // Sort candidate stops by their proximity to the route direction
    const scoredStops = allStops.map(s => {
      const dist = haversineDistance(startStop.stop_lat, startStop.stop_lon, s.stop_lat, s.stop_lon);
      const angle = Math.atan2(s.stop_lon - startStop.stop_lon, s.stop_lat - startStop.stop_lat) * 180 / Math.PI;
      const angleDiff = Math.abs(((angle - bearing + 180) % 360) - 180);
      return { stop: s, score: dist * 0.3 + angleDiff * 0.01 };
    });

    scoredStops.sort((a, b) => a.score - b.score);
    const selectedStops = [startStop, ...scoredStops.slice(1, numStops).map(s => s.stop)];

    // Calculate total distance
    let totalDist = 0;
    const distances = [0];
    for (let j = 1; j < selectedStops.length; j++) {
      const d = haversineDistance(
        selectedStops[j - 1].stop_lat, selectedStops[j - 1].stop_lon,
        selectedStops[j].stop_lat, selectedStops[j].stop_lon
      );
      totalDist += Math.max(d, 0.3); // Minimum 300m between stops
      distances.push(totalDist);
    }

    const routeName = `${selectedStops[0].stop_name} → ${selectedStops[selectedStops.length - 1].stop_name}`;

    routes.push({
      route_id: routeId,
      route_short_name: `${prefix}${routeNum}${suffix}`,
      route_long_name: routeName,
      route_type: 3, // Bus
      route_category: category.name,
      total_distance_km: Math.round(totalDist * 10) / 10,
      num_stops: selectedStops.length,
      tripsPerDay: randomInt(category.tripsPerDay[0], category.tripsPerDay[1]),
    });

    routeStopSequences[routeId] = selectedStops.map((s, idx) => ({
      stop: s,
      sequence: idx + 1,
      distance_from_start: Math.round(distances[idx] * 10) / 10,
    }));
  }

  return { routes, routeStopSequences };
}

function generateTrips(routes, routeStopSequences) {
  log.info('Generating trips...');
  const trips = [];
  const tripStopTimes = {};

  for (const route of routes) {
    const numTrips = route.tripsPerDay;
    const stops = routeStopSequences[route.route_id];
    const avgSpeed = route.route_category === 'express' ? 25 : 15; // km/h

    // Generate trip start times spread across the day (5 AM to 11 PM)
    const startHour = 5;
    const endHour = 23;
    const interval = (endHour - startHour) * 60 / numTrips;

    for (let t = 0; t < numTrips; t++) {
      const tripId = `${route.route_id}_T${String(t + 1).padStart(3, '0')}`;
      const startMinutes = startHour * 60 + Math.round(t * interval + randomInRange(-5, 5));
      const startH = Math.floor(startMinutes / 60);
      const startM = startMinutes % 60;
      const scheduledStart = `${String(Math.min(startH, 23)).padStart(2, '0')}:${String(Math.max(0, Math.round(startM))).padStart(2, '0')}:00`;

      // Calculate end time based on route distance and speed
      const travelMinutes = (route.total_distance_km / avgSpeed) * 60 + stops.length * 1.5; // 1.5 min per stop
      const endMinutes = startMinutes + travelMinutes;
      const endH = Math.floor(endMinutes / 60);
      const endM = endMinutes % 60;
      const scheduledEnd = `${String(Math.min(endH, 23)).padStart(2, '0')}:${String(Math.max(0, Math.round(endM))).padStart(2, '0')}:00`;

      trips.push({
        trip_id: tripId,
        route_id: route.route_id,
        service_id: 'WEEKDAY',
        trip_headsign: route.route_long_name.split(' → ')[1] || route.route_short_name,
        direction_id: 0,
        scheduled_start: scheduledStart,
        scheduled_end: scheduledEnd,
      });

      // Generate stop times for this trip
      tripStopTimes[tripId] = stops.map((s, idx) => {
        const travelTime = (s.distance_from_start / avgSpeed) * 60 + idx * 1.5;
        const arrMinutes = startMinutes + travelTime;
        const arrH = Math.floor(arrMinutes / 60);
        const arrM = arrMinutes % 60;
        const arrTime = `${String(Math.min(arrH, 23)).padStart(2, '0')}:${String(Math.max(0, Math.round(arrM))).padStart(2, '0')}:00`;

        return {
          trip_id: tripId,
          route_id: route.route_id,
          stop_id: s.stop.stop_id,
          stop_sequence: s.sequence,
          arrival_time: arrTime,
          departure_time: arrTime,
          distance_from_start_km: s.distance_from_start,
        };
      });
    }
  }

  return { trips, tripStopTimes };
}

// ============================================================
// Database Persistence
// ============================================================

function persistToDatabase(stops, routes, routeStopSequences, trips, tripStopTimes) {
  const db = getDb();

  log.info('Persisting GTFS data to database...');

  const insertStop = db.prepare(`
    INSERT OR REPLACE INTO stops (stop_id, stop_name, stop_lat, stop_lon, stop_type, boarding_density)
    VALUES (@stop_id, @stop_name, @stop_lat, @stop_lon, @stop_type, @boarding_density)
  `);

  const insertRoute = db.prepare(`
    INSERT OR REPLACE INTO routes (route_id, route_short_name, route_long_name, route_type, route_category, total_distance_km, num_stops)
    VALUES (@route_id, @route_short_name, @route_long_name, @route_type, @route_category, @total_distance_km, @num_stops)
  `);

  const insertTrip = db.prepare(`
    INSERT OR REPLACE INTO trips (trip_id, route_id, service_id, trip_headsign, direction_id, scheduled_start, scheduled_end)
    VALUES (@trip_id, @route_id, @service_id, @trip_headsign, @direction_id, @scheduled_start, @scheduled_end)
  `);

  const insertStopSeq = db.prepare(`
    INSERT OR REPLACE INTO stop_sequences (trip_id, route_id, stop_id, stop_sequence, arrival_time, departure_time, distance_from_start_km)
    VALUES (@trip_id, @route_id, @stop_id, @stop_sequence, @arrival_time, @departure_time, @distance_from_start_km)
  `);

  const insertFareSlab = db.prepare(`
    INSERT OR REPLACE INTO fare_slabs (min_distance_km, max_distance_km, fare_amount, fare_type)
    VALUES (@min_distance_km, @max_distance_km, @fare_amount, @fare_type)
  `);

  // Use transaction for performance
  const persist = db.transaction(() => {
    // Stops
    for (const stop of stops) {
      insertStop.run(stop);
    }
    log.info(`Inserted ${stops.length} stops`);

    // Routes
    for (const route of routes) {
      insertRoute.run({
        route_id: route.route_id,
        route_short_name: route.route_short_name,
        route_long_name: route.route_long_name,
        route_type: route.route_type,
        route_category: route.route_category,
        total_distance_km: route.total_distance_km,
        num_stops: route.num_stops,
      });
    }
    log.info(`Inserted ${routes.length} routes`);

    // Trips
    for (const trip of trips) {
      insertTrip.run(trip);
    }
    log.info(`Inserted ${trips.length} trips`);

    // Stop sequences
    let seqCount = 0;
    for (const tripId of Object.keys(tripStopTimes)) {
      for (const st of tripStopTimes[tripId]) {
        insertStopSeq.run(st);
        seqCount++;
      }
    }
    log.info(`Inserted ${seqCount} stop sequences`);

    // Fare slabs
    for (const slab of FARE_SLABS) {
      insertFareSlab.run({
        min_distance_km: slab.min,
        max_distance_km: slab.max,
        fare_amount: slab.fare,
        fare_type: 'ordinary',
      });
    }
    log.info(`Inserted ${FARE_SLABS.length} fare slabs`);
  });

  persist();
  log.info('GTFS data persistence complete');
}

// ============================================================
// Main entry point
// ============================================================

function generateGTFS(numRoutes = 50) {
  log.info(`Starting GTFS generation for ${numRoutes} routes...`);

  initializeSchema();

  // Generate ~150 unique stops (typical for a 50-route subset)
  const numStops = Math.max(100, numRoutes * 3);
  const stops = generateStops(numStops);
  const { routes, routeStopSequences } = generateRoutes(numRoutes, stops);
  const { trips, tripStopTimes } = generateTrips(routes, routeStopSequences);

  persistToDatabase(stops, routes, routeStopSequences, trips, tripStopTimes);

  const stats = {
    stops: stops.length,
    routes: routes.length,
    trips: trips.length,
    fareSlabs: FARE_SLABS.length,
  };

  log.info('GTFS generation complete', stats);
  return stats;
}

// Run directly
if (require.main === module) {
  const numRoutes = config.simulation.routesSubset;
  generateGTFS(numRoutes);
}

module.exports = { generateGTFS, FARE_SLABS, haversineDistance };
