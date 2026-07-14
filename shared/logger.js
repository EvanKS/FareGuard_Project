/**
 * FareGuard - Structured Logger
 * Provides structured, leveled logging with context tracing.
 */
const fs = require('fs');
const path = require('path');
const config = require('./config');

const LEVELS = { error: 0, warn: 1, info: 2, debug: 3 };
const currentLevel = LEVELS[config.logging.level] ?? LEVELS.info;

// Ensure log directory exists
const logDir = path.dirname(config.logging.file);
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

let logStream;
try {
  logStream = fs.createWriteStream(config.logging.file, { flags: 'a' });
} catch {
  // Fallback if file can't be opened
  logStream = null;
}

function formatLog(level, message, context = {}) {
  return JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    message,
    ...context,
    service: context.service || 'fareguard',
  });
}

function log(level, message, context = {}) {
  if (LEVELS[level] > currentLevel) return;

  const formatted = formatLog(level, message, context);

  // Console output
  if (level === 'error') {
    console.error(formatted);
  } else if (level === 'warn') {
    console.warn(formatted);
  } else {
    console.log(formatted);
  }

  // File output
  if (logStream) {
    logStream.write(formatted + '\n');
  }
}

const logger = {
  error: (msg, ctx) => log('error', msg, ctx),
  warn: (msg, ctx) => log('warn', msg, ctx),
  info: (msg, ctx) => log('info', msg, ctx),
  debug: (msg, ctx) => log('debug', msg, ctx),
  child: (defaultCtx) => ({
    error: (msg, ctx) => log('error', msg, { ...defaultCtx, ...ctx }),
    warn: (msg, ctx) => log('warn', msg, { ...defaultCtx, ...ctx }),
    info: (msg, ctx) => log('info', msg, { ...defaultCtx, ...ctx }),
    debug: (msg, ctx) => log('debug', msg, { ...defaultCtx, ...ctx }),
  }),
};

module.exports = logger;
