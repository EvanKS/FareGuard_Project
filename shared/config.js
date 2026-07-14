/**
 * FareGuard - Shared Configuration Module
 * Loads environment variables and provides typed configuration access.
 */
const path = require('path');
const dotenv = require('dotenv');

// Load .env from project root
dotenv.config({ path: path.join(__dirname, '..', '.env') });

const config = {
  server: {
    port: parseInt(process.env.PORT || '3000', 10),
    host: process.env.HOST || 'localhost',
    env: process.env.NODE_ENV || 'development',
  },
  auth: {
    jwtSecret: process.env.JWT_SECRET || 'fareguard-default-secret',
    jwtExpiresIn: process.env.JWT_EXPIRES_IN || '24h',
  },
  database: {
    path: path.resolve(process.env.DB_PATH || './data/fareguard.db'),
  },
  cloudStorage: {
    endpoint: process.env.CLOUD_STORAGE_ENDPOINT || '',
    bucket: process.env.CLOUD_STORAGE_BUCKET || 'fareguard-data',
    accessKey: process.env.CLOUD_STORAGE_ACCESS_KEY || '',
    secretKey: process.env.CLOUD_STORAGE_SECRET_KEY || '',
  },
  simulation: {
    days: parseInt(process.env.SIM_DAYS || '90', 10),
    routesSubset: parseInt(process.env.SIM_ROUTES_SUBSET || '50', 10),
    anomalyRate: parseFloat(process.env.SIM_ANOMALY_RATE || '0.05'),
    timeAcceleration: parseInt(process.env.SIM_TIME_ACCELERATION || '100', 10),
  },
  ml: {
    modelPath: path.resolve(process.env.ML_MODEL_PATH || './models'),
    retrainIntervalHours: parseInt(process.env.ML_RETRAIN_INTERVAL_HOURS || '24', 10),
  },
  logging: {
    level: process.env.LOG_LEVEL || 'info',
    file: path.resolve(process.env.LOG_FILE || './logs/fareguard.log'),
  },
  streaming: {
    batchSize: parseInt(process.env.STREAM_BATCH_SIZE || '100', 10),
    flushIntervalMs: parseInt(process.env.STREAM_FLUSH_INTERVAL_MS || '5000', 10),
    deadLetterPath: path.resolve(process.env.DEAD_LETTER_PATH || './data/dead-letter'),
  },
  monitoring: {
    enabled: process.env.MONITOR_ENABLED === 'true',
    intervalMs: parseInt(process.env.MONITOR_INTERVAL_MS || '60000', 10),
  },
};

module.exports = config;
