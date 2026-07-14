/**
 * FareGuard - Data Simulation Entry Point
 * Run this to generate GTFS data and historical simulation
 */
const { generateGTFS } = require('./gtfs-generator');
const { runHistoricalSimulation } = require('./simulation-engine');
const config = require('../shared/config');
const logger = require('../shared/logger');

const log = logger.child({ service: 'simulate' });

async function main() {
  console.log('\n🚌 FareGuard Data Generation');
  console.log('=' .repeat(50));

  // Step 1: Generate GTFS
  console.log('\n📍 Step 1: Generating GTFS route/stop/trip data...');
  const gtfsStats = generateGTFS(config.simulation.routesSubset);
  console.log(`   ✅ Generated ${gtfsStats.routes} routes, ${gtfsStats.stops} stops, ${gtfsStats.trips} trips`);

  // Step 2: Run historical simulation
  console.log(`\n📊 Step 2: Running ${config.simulation.days}-day historical simulation...`);
  console.log(`   Anomaly injection rate: ${(config.simulation.anomalyRate * 100).toFixed(0)}%`);
  const simStats = runHistoricalSimulation(config.simulation.days, config.simulation.anomalyRate);
  console.log(`   ✅ Generated ${simStats.totalEvents} ticketing events`);
  console.log(`   ✅ Injected ${simStats.totalAnomalies} anomalies:`);
  console.log(`      - Under-reporting: ${simStats.anomalyTypes.under_reporting}`);
  console.log(`      - Ghost trips: ${simStats.anomalyTypes.ghost_trip}`);
  console.log(`      - QR/UPI fraud: ${simStats.anomalyTypes.qr_upi_fraud}`);
  console.log(`      - Fare evasion clusters: ${simStats.anomalyTypes.fare_evasion_cluster}`);

  console.log('\n✅ Data generation complete!');
  console.log('   Next step: Run `npm run train` to train ML models');
}

main().catch(err => {
  console.error('Data generation failed:', err);
  process.exit(1);
});
