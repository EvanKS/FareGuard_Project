/**
 * FareGuard - Backend API Server
 * 
 * RESTful API providing access to all pipeline outputs:
 * - Route management and status
 * - Ridership vs revenue time series
 * - Anomaly detection results and review workflow
 * - Segment-level localization details
 * - Pipeline triggering and system health
 * 
 * Authentication: JWT-based role access (official/admin)
 * Security: Helmet headers, CORS, rate limiting, input validation
 */
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const { getDb, initializeSchema } = require('../shared/database');
const config = require('../shared/config');
const logger = require('../shared/logger');
const { getStreamingPipeline } = require('../cloud-layer/ingestion-pipeline');
const { detectAnomalies, loadModels } = require('../ml-layer/ml-models');
const { localizeLeakage, getComplexityAnalysis } = require('../algorithm-layer/flow-localization');
const { runFullPipeline } = require('../pipeline/run-pipeline');

const log = logger.child({ service: 'api-server' });
const app = express();

// ============================================================
// Middleware
// ============================================================

app.use(helmet({
  contentSecurityPolicy: false, // Allow inline scripts for dashboard
  crossOriginEmbedderPolicy: false,
}));

app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));

app.use(express.json({ limit: '10mb' }));

// Rate limiting
const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 500,
  message: { error: 'Too many requests, please try again later' },
});
app.use('/api/', apiLimiter);

// Request logging
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    log.debug(`${req.method} ${req.path} ${res.statusCode} ${Date.now() - start}ms`);
  });
  next();
});

// ============================================================
// Authentication Middleware
// ============================================================

function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    // Allow unauthenticated access in development mode
    if (config.server.env === 'development') {
      req.user = { user_id: 'dev-user', username: 'developer', role: 'admin' };
      return next();
    }
    return res.status(401).json({ error: 'Access token required' });
  }

  try {
    const decoded = jwt.verify(token, config.auth.jwtSecret);
    req.user = decoded;
    next();
  } catch (err) {
    return res.status(403).json({ error: 'Invalid or expired token' });
  }
}

function requireRole(role) {
  return (req, res, next) => {
    if (req.user.role !== role && req.user.role !== 'admin') {
      return res.status(403).json({ error: `Role '${role}' required` });
    }
    next();
  };
}

// ============================================================
// Auth Routes
// ============================================================

app.post('/api/auth/register', async (req, res) => {
  try {
    const { username, password, fullName, role } = req.body;
    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password required' });
    }

    const db = getDb();
    const existing = db.prepare('SELECT user_id FROM users WHERE username = ?').get(username);
    if (existing) {
      return res.status(409).json({ error: 'Username already exists' });
    }

    const passwordHash = await bcrypt.hash(password, 10);
    const userId = uuidv4();

    db.prepare(`
      INSERT INTO users (user_id, username, password_hash, role, full_name)
      VALUES (?, ?, ?, ?, ?)
    `).run(userId, username, passwordHash, role || 'official', fullName || username);

    res.status(201).json({ user_id: userId, username, role: role || 'official' });
  } catch (error) {
    log.error('Registration failed', { error: error.message });
    res.status(500).json({ error: 'Registration failed' });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password required' });
    }

    const db = getDb();
    const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const token = jwt.sign(
      { user_id: user.user_id, username: user.username, role: user.role },
      config.auth.jwtSecret,
      { expiresIn: config.auth.jwtExpiresIn }
    );

    res.json({ token, user: { user_id: user.user_id, username: user.username, role: user.role } });
  } catch (error) {
    log.error('Login failed', { error: error.message });
    res.status(500).json({ error: 'Login failed' });
  }
});

// ============================================================
// Route APIs
// ============================================================

app.get('/api/routes', authenticateToken, (req, res) => {
  try {
    const db = getDb();
    const routes = db.prepare(`
      SELECT r.*,
        (SELECT risk_level FROM route_leakage_scores 
         WHERE route_id = r.route_id ORDER BY sim_date DESC LIMIT 1) as latest_risk,
        (SELECT leakage_percentage FROM route_leakage_scores 
         WHERE route_id = r.route_id ORDER BY sim_date DESC LIMIT 1) as latest_leakage_pct,
        (SELECT leakage_amount FROM route_leakage_scores 
         WHERE route_id = r.route_id ORDER BY sim_date DESC LIMIT 1) as latest_leakage_amount,
        (SELECT COUNT(*) FROM detected_anomalies 
         WHERE route_id = r.route_id AND status = 'new') as pending_anomalies
      FROM routes r
      ORDER BY r.route_id
    `).all();

    res.json({ routes, total: routes.length });
  } catch (error) {
    log.error('Failed to fetch routes', { error: error.message });
    res.status(500).json({ error: 'Failed to fetch routes' });
  }
});

app.get('/api/routes/:routeId', authenticateToken, (req, res) => {
  try {
    const db = getDb();
    const route = db.prepare('SELECT * FROM routes WHERE route_id = ?').get(req.params.routeId);
    if (!route) return res.status(404).json({ error: 'Route not found' });

    // Get stops
    const stops = db.prepare(`
      SELECT DISTINCT ss.stop_id, ss.stop_sequence, ss.distance_from_start_km, 
             s.stop_name, s.stop_lat, s.stop_lon, s.boarding_density
      FROM stop_sequences ss
      JOIN stops s ON ss.stop_id = s.stop_id
      WHERE ss.route_id = ?
      GROUP BY ss.stop_id
      ORDER BY MIN(ss.stop_sequence)
    `).all(req.params.routeId);

    // Get leakage scores
    const leakageScores = db.prepare(`
      SELECT * FROM route_leakage_scores
      WHERE route_id = ?
      ORDER BY sim_date DESC LIMIT 30
    `).all(req.params.routeId);

    res.json({ route, stops, leakageScores });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch route details' });
  }
});

// ============================================================
// Time Series APIs
// ============================================================

app.get('/api/routes/:routeId/timeseries', authenticateToken, (req, res) => {
  try {
    const db = getDb();
    const { startDate, endDate } = req.query;

    let query = `
      SELECT sim_date, sim_hour,
        SUM(expected_revenue) as expected_revenue,
        SUM(reported_revenue) as reported_revenue,
        SUM(boarding_count) as total_boardings,
        SUM(ticket_count) as total_tickets,
        SUM(CASE WHEN is_anomalous = 1 THEN 1 ELSE 0 END) as anomaly_events
      FROM ticketing_events
      WHERE route_id = ?
    `;
    const params = [req.params.routeId];

    if (startDate) {
      query += ' AND sim_date >= ?';
      params.push(startDate);
    }
    if (endDate) {
      query += ' AND sim_date <= ?';
      params.push(endDate);
    }

    query += ' GROUP BY sim_date, sim_hour ORDER BY sim_date, sim_hour';

    const data = db.prepare(query).all(...params);
    res.json({ timeseries: data, routeId: req.params.routeId });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch time series' });
  }
});

// ============================================================
// Anomaly APIs
// ============================================================

app.get('/api/anomalies', authenticateToken, (req, res) => {
  try {
    const db = getDb();
    const { status, routeId, minScore, limit, offset, sortBy } = req.query;

    let query = 'SELECT * FROM detected_anomalies WHERE 1=1';
    const params = [];

    if (status) {
      query += ' AND status = ?';
      params.push(status);
    }
    if (routeId) {
      query += ' AND route_id = ?';
      params.push(routeId);
    }
    if (minScore) {
      query += ' AND anomaly_score >= ?';
      params.push(parseFloat(minScore));
    }

    const sortField = sortBy === 'date' ? 'sim_date DESC' : 'anomaly_score DESC';
    query += ` ORDER BY ${sortField}`;
    query += ` LIMIT ? OFFSET ?`;
    params.push(parseInt(limit || '50'), parseInt(offset || '0'));

    const anomalies = db.prepare(query).all(...params);
    const totalCount = db.prepare(
      `SELECT COUNT(*) as cnt FROM detected_anomalies WHERE 1=1${status ? ' AND status = \'' + status + '\'' : ''}`
    ).get().cnt;

    res.json({ anomalies, total: totalCount });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch anomalies' });
  }
});

app.get('/api/anomalies/:detectionId', authenticateToken, (req, res) => {
  try {
    const db = getDb();
    const anomaly = db.prepare(
      'SELECT * FROM detected_anomalies WHERE detection_id = ?'
    ).get(req.params.detectionId);

    if (!anomaly) return res.status(404).json({ error: 'Anomaly not found' });

    // Get localization details
    const localization = db.prepare(`
      SELECT * FROM flow_localization_results
      WHERE route_id = ? AND sim_date = ?
      ORDER BY localization_score DESC LIMIT 20
    `).all(anomaly.route_id, anomaly.sim_date);

    res.json({ anomaly, localization });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch anomaly details' });
  }
});

app.patch('/api/anomalies/:detectionId/status', authenticateToken, (req, res) => {
  try {
    const { status, notes } = req.body;
    const validStatuses = ['new', 'reviewed', 'confirmed', 'dismissed'];
    if (!validStatuses.includes(status)) {
      return res.status(400).json({ error: `Invalid status. Must be one of: ${validStatuses.join(', ')}` });
    }

    const db = getDb();
    db.prepare(`
      UPDATE detected_anomalies 
      SET status = ?, reviewed_by = ?, reviewed_at = datetime('now'), notes = ?
      WHERE detection_id = ?
    `).run(status, req.user.username, notes || null, req.params.detectionId);

    res.json({ success: true, status });
  } catch (error) {
    res.status(500).json({ error: 'Failed to update anomaly status' });
  }
});

// ============================================================
// Localization APIs
// ============================================================

app.get('/api/localization/:routeId', authenticateToken, (req, res) => {
  try {
    const db = getDb();
    const { simDate } = req.query;

    let query = `
      SELECT flr.*, 
        s1.stop_name as start_stop_name, s2.stop_name as end_stop_name,
        s1.stop_lat as start_lat, s1.stop_lon as start_lon,
        s2.stop_lat as end_lat, s2.stop_lon as end_lon
      FROM flow_localization_results flr
      LEFT JOIN stops s1 ON flr.segment_start_stop = s1.stop_id
      LEFT JOIN stops s2 ON flr.segment_end_stop = s2.stop_id
      WHERE flr.route_id = ?
    `;
    const params = [req.params.routeId];

    if (simDate) {
      query += ' AND flr.sim_date = ?';
      params.push(simDate);
    } else {
      query += ' AND flr.sim_date = (SELECT MAX(sim_date) FROM flow_localization_results WHERE route_id = ?)';
      params.push(req.params.routeId);
    }

    query += ' ORDER BY flr.localization_score DESC LIMIT 50';

    const results = db.prepare(query).all(...params);
    res.json({ localization: results, routeId: req.params.routeId });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch localization data' });
  }
});

// ============================================================
// Dashboard Summary APIs
// ============================================================

app.get('/api/dashboard/summary', authenticateToken, (req, res) => {
  try {
    const db = getDb();

    const routeCount = db.prepare('SELECT COUNT(*) as cnt FROM routes').get().cnt;
    const totalAnomalies = db.prepare(
      "SELECT COUNT(*) as cnt FROM detected_anomalies WHERE status = 'new'"
    ).get().cnt;

    const revenueStats = db.prepare(`
      SELECT 
        SUM(expected_revenue) as total_expected,
        SUM(reported_revenue) as total_reported,
        COUNT(DISTINCT sim_date) as days_covered,
        COUNT(DISTINCT route_id) as routes_with_data
      FROM ticketing_events
      WHERE sim_date >= date('now', '-7 days')
    `).get();

    const riskDistribution = db.prepare(`
      SELECT risk_level, COUNT(*) as cnt 
      FROM (
        SELECT route_id, risk_level 
        FROM route_leakage_scores 
        WHERE sim_date = (SELECT MAX(sim_date) FROM route_leakage_scores)
        GROUP BY route_id
      )
      GROUP BY risk_level
    `).all();

    const anomalyByType = db.prepare(`
      SELECT detection_type, COUNT(*) as cnt 
      FROM detected_anomalies 
      GROUP BY detection_type
    `).all();

    const recentAnomalies = db.prepare(`
      SELECT da.*, r.route_short_name
      FROM detected_anomalies da
      LEFT JOIN routes r ON da.route_id = r.route_id
      ORDER BY da.anomaly_score DESC LIMIT 10
    `).all();

    // Get leakage trend (last 30 days)
    const leakageTrend = db.prepare(`
      SELECT sim_date,
        SUM(expected_revenue) as expected,
        SUM(reported_revenue) as reported,
        SUM(leakage_amount) as leakage
      FROM route_leakage_scores
      GROUP BY sim_date
      ORDER BY sim_date DESC LIMIT 30
    `).all();

    res.json({
      overview: {
        totalRoutes: routeCount,
        pendingAnomalies: totalAnomalies,
        totalExpectedRevenue: revenueStats?.total_expected || 0,
        totalReportedRevenue: revenueStats?.total_reported || 0,
        totalLeakage: (revenueStats?.total_expected || 0) - (revenueStats?.total_reported || 0),
        daysCovered: revenueStats?.days_covered || 0,
      },
      riskDistribution,
      anomalyByType,
      recentAnomalies,
      leakageTrend: leakageTrend.reverse(),
    });
  } catch (error) {
    log.error('Dashboard summary failed', { error: error.message });
    res.status(500).json({ error: 'Failed to generate dashboard summary' });
  }
});

// ============================================================
// Pipeline Control APIs
// ============================================================

app.post('/api/pipeline/run', authenticateToken, requireRole('admin'), async (req, res) => {
  try {
    res.json({ message: 'Pipeline started', status: 'running' });
    // Run asynchronously
    runFullPipeline().then(results => {
      log.info('Pipeline completed via API trigger', { success: results.success });
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to start pipeline' });
  }
});

app.post('/api/pipeline/detect', authenticateToken, async (req, res) => {
  try {
    const { routeId, simDate } = req.body;
    const db = getDb();

    const events = db.prepare(`
      SELECT te.*, r.route_category, s.boarding_density
      FROM ticketing_events te
      JOIN routes r ON te.route_id = r.route_id
      JOIN stops s ON te.stop_id = s.stop_id
      WHERE te.route_id = ? AND te.sim_date = ?
    `).all(routeId, simDate);

    const detections = detectAnomalies(events);
    res.json({ detections: detections.filter(d => d.is_flagged), total: detections.length });
  } catch (error) {
    res.status(500).json({ error: 'Detection failed' });
  }
});

app.post('/api/pipeline/localize', authenticateToken, async (req, res) => {
  try {
    const { routeId, simDate } = req.body;
    const results = localizeLeakage(routeId, simDate);
    res.json({ localization: results });
  } catch (error) {
    res.status(500).json({ error: 'Localization failed' });
  }
});

// ============================================================
// System Health / Monitoring APIs
// ============================================================

app.get('/api/health', (req, res) => {
  try {
    const db = getDb();
    db.prepare('SELECT 1').get();
    res.json({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      version: '1.0.0',
      uptime: process.uptime(),
    });
  } catch (error) {
    res.status(503).json({ status: 'unhealthy', error: error.message });
  }
});

app.get('/api/monitoring/metrics', authenticateToken, (req, res) => {
  try {
    const db = getDb();
    const pipeline = getStreamingPipeline();

    const recentMetrics = db.prepare(`
      SELECT * FROM pipeline_metrics 
      ORDER BY recorded_at DESC LIMIT 100
    `).all();

    const deadLetterCount = db.prepare(
      'SELECT COUNT(*) as cnt FROM dead_letter_events'
    ).get().cnt;

    const modelInfo = db.prepare(`
      SELECT * FROM model_registry WHERE is_active = 1
    `).all();

    res.json({
      pipeline: pipeline.getMetrics(),
      recentMetrics,
      deadLetterCount,
      activeModels: modelInfo,
      system: {
        memoryUsage: process.memoryUsage(),
        uptime: process.uptime(),
      },
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch metrics' });
  }
});

// Algorithm complexity analysis endpoint
app.get('/api/algorithm/complexity', authenticateToken, (req, res) => {
  res.json(getComplexityAnalysis());
});

// ============================================================
// Serve Frontend (Static Files)
// ============================================================

app.use(express.static(path.join(__dirname, '..', 'frontend')));

// SPA fallback
app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({ error: 'API endpoint not found' });
  }
  res.sendFile(path.join(__dirname, '..', 'frontend', 'index.html'));
});

// ============================================================
// Error Handler
// ============================================================

app.use((err, req, res, next) => {
  log.error('Unhandled error', { error: err.message, stack: err.stack });
  res.status(500).json({ error: 'Internal server error' });
});

// ============================================================
// Server Startup
// ============================================================

function startServer() {
  initializeSchema();

  // Create default admin user if none exists
  const db = getDb();
  const adminExists = db.prepare("SELECT user_id FROM users WHERE role = 'admin'").get();
  if (!adminExists) {
    const hash = bcrypt.hashSync('admin123', 10);
    db.prepare(`
      INSERT INTO users (user_id, username, password_hash, role, full_name)
      VALUES (?, 'admin', ?, 'admin', 'System Administrator')
    `).run(uuidv4(), hash);

    const officialHash = bcrypt.hashSync('official123', 10);
    db.prepare(`
      INSERT INTO users (user_id, username, password_hash, role, full_name)
      VALUES (?, 'transit_official', ?, 'official', 'Transit Official')
    `).run(uuidv4(), officialHash);

    log.info('Default users created: admin/admin123, transit_official/official123');
  }

  // Try to load ML models
  try {
    loadModels();
  } catch (e) {
    log.warn('ML models not yet available - run pipeline first');
  }

  const server = app.listen(config.server.port, () => {
    log.info(`FareGuard API server running on http://${config.server.host}:${config.server.port}`);
    console.log(`\n  🚌 FareGuard Dashboard: http://localhost:${config.server.port}`);
    console.log(`  📡 API Base URL: http://localhost:${config.server.port}/api`);
    console.log(`  🔑 Default login: admin / admin123\n`);
  });

  return server;
}

if (require.main === module) {
  startServer();
}

module.exports = { app, startServer };
