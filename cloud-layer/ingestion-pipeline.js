/**
 * FareGuard - Cloud Ingestion & Streaming Pipeline
 * 
 * Implements a managed streaming pipeline that ingests simulated ticketing
 * and GPS events. Uses an in-process pub/sub system that mirrors the architecture
 * of cloud services (Kafka/Kinesis/Pub-Sub) for local development, with
 * documented deployment path to actual cloud services.
 * 
 * Features:
 * - Partitioned by route_id for horizontal scaling
 * - Schema validation at ingestion boundary
 * - Dead-letter queue for malformed events
 * - Batch flushing with configurable intervals
 * - Pipeline health monitoring
 */
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');
const { getDb } = require('../shared/database');
const logger = require('../shared/logger');
const config = require('../shared/config');

const log = logger.child({ service: 'ingestion-pipeline' });

// ============================================================
// Event Schema Validation
// ============================================================

const REQUIRED_FIELDS = [
  'event_id', 'trip_id', 'route_id', 'stop_id', 'event_timestamp',
  'boarding_count', 'ticket_count', 'expected_revenue', 'reported_revenue'
];

const VALID_PAYMENT_MODES = ['cash', 'upi', 'card', 'pass'];

function validateEvent(event) {
  const errors = [];

  for (const field of REQUIRED_FIELDS) {
    if (event[field] === undefined || event[field] === null) {
      errors.push(`Missing required field: ${field}`);
    }
  }

  if (event.boarding_count !== undefined && (typeof event.boarding_count !== 'number' || event.boarding_count < 0)) {
    errors.push('boarding_count must be a non-negative number');
  }

  if (event.ticket_count !== undefined && (typeof event.ticket_count !== 'number' || event.ticket_count < 0)) {
    errors.push('ticket_count must be a non-negative number');
  }

  if (event.payment_mode && !VALID_PAYMENT_MODES.includes(event.payment_mode)) {
    errors.push(`Invalid payment_mode: ${event.payment_mode}`);
  }

  if (event.event_timestamp && isNaN(Date.parse(event.event_timestamp))) {
    errors.push('Invalid event_timestamp format');
  }

  return { valid: errors.length === 0, errors };
}

// ============================================================
// Partition Manager (simulates Kafka-style partitioning)
// ============================================================

class PartitionManager {
  constructor(numPartitions = 8) {
    this.numPartitions = numPartitions;
    this.partitions = new Map();
    for (let i = 0; i < numPartitions; i++) {
      this.partitions.set(i, []);
    }
    this.offsets = new Map();
  }

  getPartition(routeId) {
    // Hash route_id to partition number for consistent routing
    let hash = 0;
    for (let i = 0; i < routeId.length; i++) {
      hash = ((hash << 5) - hash) + routeId.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash) % this.numPartitions;
  }

  enqueue(event) {
    const partition = this.getPartition(event.route_id);
    const buffer = this.partitions.get(partition);
    buffer.push({
      offset: (this.offsets.get(partition) || 0) + buffer.length,
      timestamp: Date.now(),
      data: event,
    });
  }

  drain(partition) {
    const buffer = this.partitions.get(partition);
    const events = [...buffer];
    const lastOffset = events.length > 0 ? events[events.length - 1].offset : 0;
    this.offsets.set(partition, lastOffset);
    this.partitions.set(partition, []);
    return events;
  }

  drainAll() {
    const all = [];
    for (let i = 0; i < this.numPartitions; i++) {
      all.push(...this.drain(i));
    }
    return all;
  }

  getTotalPending() {
    let total = 0;
    for (const [, buffer] of this.partitions) {
      total += buffer.length;
    }
    return total;
  }
}

// ============================================================
// Dead Letter Queue
// ============================================================

class DeadLetterQueue {
  constructor() {
    this.queue = [];
    this.dlqPath = config.streaming.deadLetterPath;
    if (!fs.existsSync(this.dlqPath)) {
      fs.mkdirSync(this.dlqPath, { recursive: true });
    }
  }

  add(event, errors) {
    const entry = {
      id: uuidv4(),
      timestamp: new Date().toISOString(),
      originalEvent: event,
      errors,
    };

    this.queue.push(entry);

    // Persist to dead-letter store
    try {
      const db = getDb();
      db.prepare(`
        INSERT INTO dead_letter_events (original_event, error_message, error_type)
        VALUES (?, ?, ?)
      `).run(
        JSON.stringify(event),
        errors.join('; '),
        'validation_error'
      );
    } catch (e) {
      log.error('Failed to persist dead letter event', { error: e.message });
    }

    log.warn('Event sent to dead-letter queue', {
      eventId: event?.event_id || 'unknown',
      errors,
    });
  }

  getCount() {
    return this.queue.length;
  }

  getRecent(limit = 10) {
    return this.queue.slice(-limit);
  }
}

// ============================================================
// Streaming Pipeline
// ============================================================

class StreamingPipeline {
  constructor() {
    this.partitionManager = new PartitionManager();
    this.deadLetterQueue = new DeadLetterQueue();
    this.subscribers = [];
    this.metrics = {
      totalIngested: 0,
      totalProcessed: 0,
      totalFailed: 0,
      totalDeadLettered: 0,
      startTime: Date.now(),
      lastFlushTime: null,
      avgProcessingTimeMs: 0,
    };
    this.flushInterval = null;
    this.running = false;
  }

  /**
   * Subscribe a handler to process events
   */
  subscribe(handler) {
    this.subscribers.push(handler);
    log.info('New subscriber registered', { totalSubscribers: this.subscribers.length });
  }

  /**
   * Ingest a single event into the pipeline
   */
  ingest(event) {
    const validation = validateEvent(event);

    if (!validation.valid) {
      this.deadLetterQueue.add(event, validation.errors);
      this.metrics.totalDeadLettered++;
      return { success: false, errors: validation.errors };
    }

    this.partitionManager.enqueue(event);
    this.metrics.totalIngested++;

    return { success: true };
  }

  /**
   * Ingest a batch of events
   */
  ingestBatch(events) {
    let succeeded = 0;
    let failed = 0;

    for (const event of events) {
      const result = this.ingest(event);
      if (result.success) succeeded++;
      else failed++;
    }

    log.debug(`Batch ingestion: ${succeeded} succeeded, ${failed} failed`);
    return { succeeded, failed };
  }

  /**
   * Flush pending events to subscribers
   */
  flush() {
    const startTime = Date.now();
    const events = this.partitionManager.drainAll();

    if (events.length === 0) return;

    for (const subscriber of this.subscribers) {
      try {
        for (const event of events) {
          subscriber(event.data);
        }
      } catch (error) {
        log.error('Subscriber processing error', { error: error.message });
        this.metrics.totalFailed += events.length;
      }
    }

    this.metrics.totalProcessed += events.length;
    this.metrics.lastFlushTime = Date.now();
    this.metrics.avgProcessingTimeMs =
      (this.metrics.avgProcessingTimeMs * 0.9) + ((Date.now() - startTime) * 0.1);

    log.debug(`Flushed ${events.length} events in ${Date.now() - startTime}ms`);
  }

  /**
   * Start the pipeline with periodic flushing
   */
  start() {
    if (this.running) return;

    this.running = true;
    this.flushInterval = setInterval(() => {
      this.flush();
      this.recordMetrics();
    }, config.streaming.flushIntervalMs);

    log.info('Streaming pipeline started', {
      flushIntervalMs: config.streaming.flushIntervalMs,
      batchSize: config.streaming.batchSize,
    });
  }

  /**
   * Stop the pipeline gracefully
   */
  stop() {
    if (!this.running) return;

    // Final flush
    this.flush();
    clearInterval(this.flushInterval);
    this.running = false;
    log.info('Streaming pipeline stopped', this.metrics);
  }

  /**
   * Record pipeline health metrics
   */
  recordMetrics() {
    try {
      const db = getDb();
      const insert = db.prepare(`
        INSERT INTO pipeline_metrics (metric_name, metric_value, metric_unit, service)
        VALUES (?, ?, ?, ?)
      `);

      insert.run('ingestion_total', this.metrics.totalIngested, 'count', 'ingestion');
      insert.run('processing_total', this.metrics.totalProcessed, 'count', 'ingestion');
      insert.run('dead_letter_total', this.metrics.totalDeadLettered, 'count', 'ingestion');
      insert.run('pending_events', this.partitionManager.getTotalPending(), 'count', 'ingestion');
      insert.run('avg_processing_time', this.metrics.avgProcessingTimeMs, 'ms', 'ingestion');
    } catch (e) {
      // Metrics recording should not crash the pipeline
      log.warn('Failed to record pipeline metrics', { error: e.message });
    }
  }

  getMetrics() {
    return {
      ...this.metrics,
      pendingEvents: this.partitionManager.getTotalPending(),
      deadLetterCount: this.deadLetterQueue.getCount(),
      uptimeMs: Date.now() - this.metrics.startTime,
      running: this.running,
    };
  }
}

// ============================================================
// Object Storage Manager (S3-compatible abstraction)
// ============================================================

class ObjectStorageManager {
  constructor() {
    this.basePath = path.join(path.dirname(config.database.path), 'object-storage');
    this.ensureBuckets();
  }

  ensureBuckets() {
    const buckets = ['raw-data', 'models', 'training-data', 'logs', 'exports'];
    for (const bucket of buckets) {
      const p = path.join(this.basePath, bucket);
      if (!fs.existsSync(p)) {
        fs.mkdirSync(p, { recursive: true });
      }
    }
  }

  /**
   * Store an object (file) in a bucket
   */
  putObject(bucket, key, data) {
    const filePath = path.join(this.basePath, bucket, key);
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const content = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    fs.writeFileSync(filePath, content);

    log.debug(`Stored object: ${bucket}/${key}`, { size: content.length });
    return { bucket, key, size: content.length };
  }

  /**
   * Retrieve an object from a bucket
   */
  getObject(bucket, key) {
    const filePath = path.join(this.basePath, bucket, key);
    if (!fs.existsSync(filePath)) {
      return null;
    }
    return fs.readFileSync(filePath, 'utf-8');
  }

  /**
   * List objects in a bucket
   */
  listObjects(bucket, prefix = '') {
    const dir = path.join(this.basePath, bucket, prefix);
    if (!fs.existsSync(dir)) return [];

    const items = [];
    const scanDir = (d, rel) => {
      const entries = fs.readdirSync(d, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(d, entry.name);
        const relPath = path.join(rel, entry.name).replace(/\\/g, '/');
        if (entry.isDirectory()) {
          scanDir(fullPath, relPath);
        } else {
          const stat = fs.statSync(fullPath);
          items.push({
            key: relPath,
            size: stat.size,
            lastModified: stat.mtime.toISOString(),
          });
        }
      }
    };

    scanDir(dir, prefix);
    return items;
  }

  /**
   * Delete an object
   */
  deleteObject(bucket, key) {
    const filePath = path.join(this.basePath, bucket, key);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      return true;
    }
    return false;
  }
}

// Singleton instances
let pipeline = null;
let objectStorage = null;

function getStreamingPipeline() {
  if (!pipeline) {
    pipeline = new StreamingPipeline();
  }
  return pipeline;
}

function getObjectStorage() {
  if (!objectStorage) {
    objectStorage = new ObjectStorageManager();
  }
  return objectStorage;
}

module.exports = {
  StreamingPipeline,
  ObjectStorageManager,
  PartitionManager,
  DeadLetterQueue,
  getStreamingPipeline,
  getObjectStorage,
  validateEvent,
};
