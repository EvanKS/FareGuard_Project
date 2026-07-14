/**
 * FareGuard - ML Training Entry Point
 */
const { trainModels } = require('./ml-models');
const logger = require('../shared/logger');

async function main() {
  console.log('\n🧠 FareGuard ML Training Pipeline');
  console.log('=' .repeat(50));

  console.log('\nTraining forecasting and anomaly detection models...');
  const results = trainModels();

  if (results) {
    console.log('\n✅ Training Complete!');
    console.log(`   Train samples: ${results.trainSamples}`);
    console.log(`   Test samples: ${results.testSamples}`);
    console.log(`\n   Forecasting Model:`);
    console.log(`     RMSE: ${results.forecast.rmse.toFixed(4)}`);
    console.log(`     MAE:  ${results.forecast.mae.toFixed(4)}`);
    console.log(`\n   Anomaly Detection:`);
    console.log(`     Precision: ${(results.anomaly.precision * 100).toFixed(1)}%`);
    console.log(`     Recall:    ${(results.anomaly.recall * 100).toFixed(1)}%`);
    console.log(`     F1-Score:  ${(results.anomaly.f1 * 100).toFixed(1)}%`);
    console.log(`     TP: ${results.anomaly.tp}, FP: ${results.anomaly.fp}, TN: ${results.anomaly.tn}, FN: ${results.anomaly.fn}`);
    console.log(`\n   Training time: ${(results.totalTimeMs / 1000).toFixed(1)}s`);
    console.log('\n   Next step: Run `npm start` to launch the dashboard');
  } else {
    console.error('\n❌ Training failed. Ensure simulation data exists first.');
  }
}

main().catch(err => {
  console.error('Training failed:', err);
  process.exit(1);
});
