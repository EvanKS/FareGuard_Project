/**
 * FareGuard - Frontend Dashboard Application
 * 
 * Single-page application that communicates with the backend API
 * to display route status, anomalies, localization, and system health.
 */

const API_BASE = '/api';
let currentView = 'dashboard';
let allRoutes = [];
let dashboardData = null;

// ============================================================
// API Communication
// ============================================================

async function api(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  try {
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Request failed' }));
      throw new Error(err.error || `HTTP ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`API error (${endpoint}):`, error);
    throw error;
  }
}

// ============================================================
// Navigation
// ============================================================

function switchView(viewName) {
  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Show target view
  const viewEl = document.getElementById(`view-${viewName}`);
  const navEl = document.getElementById(`nav-${viewName}`);
  if (viewEl) viewEl.classList.add('active');
  if (navEl) navEl.classList.add('active');

  currentView = viewName;

  // Load data for view
  switch (viewName) {
    case 'dashboard': refreshDashboard(); break;
    case 'routes': loadRoutes(); break;
    case 'anomalies': loadAnomalies(); break;
    case 'localization': loadLocalizationRoutes(); break;
    case 'timeseries': loadTimeSeriesRoutes(); break;
    case 'monitoring': loadMonitoring(); break;
  }
}

// Setup navigation
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const view = item.getAttribute('data-view');
    if (view) switchView(view);
  });
});

// ============================================================
// Dashboard
// ============================================================

async function refreshDashboard() {
  try {
    dashboardData = await api('/dashboard/summary');
    renderDashboard(dashboardData);
  } catch (error) {
    console.error('Failed to load dashboard:', error);
  }
}

function renderDashboard(data) {
  const { overview, riskDistribution, recentAnomalies, leakageTrend } = data;

  // KPI Cards
  document.getElementById('kpi-routes').textContent = overview.totalRoutes.toLocaleString();
  document.getElementById('kpi-leakage').textContent = `₹${formatCurrency(overview.totalLeakage)}`;
  document.getElementById('kpi-anomalies').textContent = overview.pendingAnomalies.toLocaleString();

  const collectionRate = overview.totalExpectedRevenue > 0
    ? ((overview.totalReportedRevenue / overview.totalExpectedRevenue) * 100).toFixed(1)
    : '—';
  document.getElementById('kpi-collection').textContent = `${collectionRate}%`;

  // Update anomaly badge
  document.getElementById('anomaly-badge').textContent = overview.pendingAnomalies;

  // Revenue Trend Chart
  renderRevenueChart(leakageTrend);

  // Risk Distribution
  renderRiskChart(riskDistribution);

  // Recent Anomalies Table
  renderAnomalyTable(recentAnomalies, 'recent-anomalies-table');
}

function formatCurrency(amount) {
  if (Math.abs(amount) >= 100000) return (amount / 100000).toFixed(1) + 'L';
  if (Math.abs(amount) >= 1000) return (amount / 1000).toFixed(1) + 'K';
  return amount.toFixed(0);
}

// ============================================================
// Canvas-based Chart Rendering
// ============================================================

function renderRevenueChart(data) {
  const container = document.getElementById('revenue-chart');
  if (!data || data.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>No trend data available</p></div>';
    return;
  }

  const canvas = document.createElement('canvas');
  canvas.width = container.clientWidth * 2;
  canvas.height = 440;
  canvas.style.width = '100%';
  canvas.style.height = '220px';
  container.innerHTML = '';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const padding = { top: 30, right: 30, bottom: 50, left: 80 };
  const chartW = W - padding.left - padding.right;
  const chartH = H - padding.top - padding.bottom;

  // Data ranges
  const maxVal = Math.max(...data.map(d => Math.max(d.expected || 0, d.reported || 0)));
  const yScale = maxVal > 0 ? chartH / (maxVal * 1.1) : 1;
  const xStep = data.length > 1 ? chartW / (data.length - 1) : chartW;

  // Background
  ctx.fillStyle = 'rgba(17, 24, 39, 0.5)';
  ctx.fillRect(0, 0, W, H);

  // Grid lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (chartH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(W - padding.right, y);
    ctx.stroke();

    // Y-axis labels
    const val = maxVal * 1.1 * (1 - i / 4);
    ctx.fillStyle = '#64748b';
    ctx.font = '20px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`₹${formatCurrency(val)}`, padding.left - 10, y + 6);
  }

  // X-axis labels (show every nth)
  ctx.fillStyle = '#64748b';
  ctx.font = '18px Inter, sans-serif';
  ctx.textAlign = 'center';
  const labelStep = Math.max(1, Math.floor(data.length / 8));
  data.forEach((d, i) => {
    if (i % labelStep === 0) {
      const x = padding.left + i * xStep;
      const dateLabel = d.sim_date ? d.sim_date.substring(5) : `D${i}`;
      ctx.fillText(dateLabel, x, H - padding.bottom + 25);
    }
  });

  // Draw area fills
  function drawArea(values, color) {
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + chartH);
    values.forEach((val, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + chartH - (val * yScale);
      ctx.lineTo(x, y);
    });
    ctx.lineTo(padding.left + (values.length - 1) * xStep, padding.top + chartH);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  drawArea(data.map(d => d.expected || 0), 'rgba(99, 102, 241, 0.15)');
  drawArea(data.map(d => d.reported || 0), 'rgba(16, 185, 129, 0.15)');

  // Draw lines
  function drawLine(values, color, lineWidth = 3) {
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineJoin = 'round';
    values.forEach((val, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + chartH - (val * yScale);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  drawLine(data.map(d => d.expected || 0), '#6366f1');
  drawLine(data.map(d => d.reported || 0), '#10b981');

  // Leakage fill between lines
  ctx.beginPath();
  data.forEach((d, i) => {
    const x = padding.left + i * xStep;
    const y = padding.top + chartH - ((d.expected || 0) * yScale);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  for (let i = data.length - 1; i >= 0; i--) {
    const x = padding.left + i * xStep;
    const y = padding.top + chartH - ((data[i].reported || 0) * yScale);
    ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = 'rgba(239, 68, 68, 0.1)';
  ctx.fill();

  // Legend below container
  const legendHTML = `
    <div class="ts-legend">
      <div class="ts-legend-item"><div class="ts-legend-dot" style="background:#6366f1"></div>Expected Revenue</div>
      <div class="ts-legend-item"><div class="ts-legend-dot" style="background:#10b981"></div>Reported Revenue</div>
      <div class="ts-legend-item"><div class="ts-legend-dot" style="background:rgba(239,68,68,0.5)"></div>Revenue Gap (Leakage)</div>
    </div>
  `;
  const existingLegend = container.parentElement.querySelector('.ts-legend');
  if (existingLegend) existingLegend.remove();
  container.insertAdjacentHTML('afterend', legendHTML);
}

function renderRiskChart(distribution) {
  const container = document.getElementById('risk-chart');
  if (!distribution || distribution.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>No risk data</p></div>';
    return;
  }

  const total = distribution.reduce((s, d) => s + d.cnt, 0);
  const colors = {
    critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e'
  };
  const labels = {
    critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low'
  };

  let html = '<div style="display:flex;flex-direction:column;gap:0.75rem;padding:0.5rem 0;">';

  const orderedLevels = ['critical', 'high', 'medium', 'low'];
  for (const level of orderedLevels) {
    const item = distribution.find(d => d.risk_level === level);
    const count = item ? item.cnt : 0;
    const pct = total > 0 ? (count / total * 100).toFixed(0) : 0;

    html += `
      <div style="display:flex;align-items:center;gap:0.75rem;">
        <span style="width:60px;font-size:0.75rem;color:${colors[level]};font-weight:600;">${labels[level]}</span>
        <div style="flex:1;height:24px;background:rgba(255,255,255,0.03);border-radius:4px;overflow:hidden;">
          <div style="width:${pct}%;height:100%;background:${colors[level]};border-radius:4px;transition:width 0.5s ease;opacity:0.8;"></div>
        </div>
        <span style="font-family:'JetBrains Mono';font-size:0.8rem;color:var(--text-secondary);min-width:50px;text-align:right;">${count} (${pct}%)</span>
      </div>
    `;
  }

  html += '</div>';
  container.innerHTML = html;
}

// ============================================================
// Anomaly Table Rendering
// ============================================================

function renderAnomalyTable(anomalies, containerId) {
  const container = document.getElementById(containerId);
  if (!anomalies || anomalies.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>No anomalies found</p></div>';
    return;
  }

  let html = `
    <table>
      <thead>
        <tr>
          <th>Score</th>
          <th>Route</th>
          <th>Date</th>
          <th>Expected</th>
          <th>Reported</th>
          <th>Gap</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
  `;

  for (const a of anomalies) {
    const scoreColor = a.anomaly_score > 0.7 ? '#ef4444' : a.anomaly_score > 0.4 ? '#f59e0b' : '#22c55e';
    html += `
      <tr class="clickable" onclick="showAnomalyDetail('${a.detection_id}')">
        <td>
          <div class="score-bar">
            <span class="score-value" style="color:${scoreColor}">${(a.anomaly_score * 100).toFixed(0)}%</span>
            <div class="score-track"><div class="score-fill" style="width:${a.anomaly_score * 100}%"></div></div>
          </div>
        </td>
        <td style="font-weight:600;color:var(--text-primary);">${a.route_short_name || a.route_id}</td>
        <td>${a.sim_date || '—'}</td>
        <td style="font-family:var(--font-mono);">₹${(a.expected_value || 0).toFixed(0)}</td>
        <td style="font-family:var(--font-mono);">₹${(a.reported_value || 0).toFixed(0)}</td>
        <td style="font-family:var(--font-mono);color:var(--color-danger);">₹${(a.discrepancy || 0).toFixed(0)}</td>
        <td><span class="status-badge status-${a.status}">${a.status}</span></td>
        <td>
          <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation(); showAnomalyDetail('${a.detection_id}')">View</button>
        </td>
      </tr>
    `;
  }

  html += '</tbody></table>';
  container.innerHTML = html;
}

// ============================================================
// Routes View
// ============================================================

async function loadRoutes() {
  try {
    const data = await api('/routes');
    allRoutes = data.routes;
    renderRoutes(allRoutes);
    populateRouteSelectors(allRoutes);
  } catch (error) {
    console.error('Failed to load routes:', error);
  }
}

function renderRoutes(routes) {
  const grid = document.getElementById('routes-grid');
  if (!routes || routes.length === 0) {
    grid.innerHTML = '<div class="empty-state"><h3>No routes found</h3></div>';
    return;
  }

  grid.innerHTML = routes.map(r => {
    const risk = r.latest_risk || 'low';
    const leakagePct = (r.latest_leakage_pct || 0).toFixed(1);
    const leakageAmt = r.latest_leakage_amount || 0;

    return `
      <div class="route-card risk-${risk}-card" onclick="viewRouteDetail('${r.route_id}')">
        <div class="route-card-header">
          <div>
            <div class="route-card-name">${r.route_short_name}</div>
            <div class="route-card-id">${r.route_id}</div>
          </div>
          <span class="risk-badge risk-${risk}">${risk}</span>
        </div>
        <div class="route-card-meta">
          <span>🛑 ${r.num_stops} stops</span>
          <span>📏 ${r.total_distance_km} km</span>
          <span>📂 ${r.route_category}</span>
        </div>
        <div class="route-card-stats">
          <div class="route-stat">
            <span class="route-stat-value" style="color:${risk === 'critical' || risk === 'high' ? 'var(--color-danger)' : 'var(--text-primary)'}">
              ${leakagePct}%
            </span>
            <span class="route-stat-label">Leakage Rate</span>
          </div>
          <div class="route-stat">
            <span class="route-stat-value">₹${formatCurrency(leakageAmt)}</span>
            <span class="route-stat-label">Est. Leakage</span>
          </div>
          <div class="route-stat">
            <span class="route-stat-value">${r.pending_anomalies || 0}</span>
            <span class="route-stat-label">Pending Alerts</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function filterRoutes() {
  const search = document.getElementById('route-search').value.toLowerCase();
  const riskFilter = document.getElementById('route-risk-filter').value;

  let filtered = allRoutes;
  if (search) {
    filtered = filtered.filter(r =>
      r.route_id.toLowerCase().includes(search) ||
      r.route_short_name.toLowerCase().includes(search) ||
      r.route_long_name.toLowerCase().includes(search)
    );
  }
  if (riskFilter) {
    filtered = filtered.filter(r => (r.latest_risk || 'low') === riskFilter);
  }
  renderRoutes(filtered);
}

function viewRouteDetail(routeId) {
  // Switch to time series view for this route
  switchView('timeseries');
  setTimeout(() => {
    document.getElementById('ts-route-select').value = routeId;
    loadTimeSeries();
  }, 100);
}

function populateRouteSelectors(routes) {
  const selectors = ['loc-route-select', 'ts-route-select'];
  for (const id of selectors) {
    const select = document.getElementById(id);
    if (!select) continue;
    const currentVal = select.value;
    select.innerHTML = '<option value="">Select Route</option>' +
      routes.map(r => `<option value="${r.route_id}">${r.route_short_name} — ${r.route_long_name.substring(0, 40)}</option>`).join('');
    if (currentVal) select.value = currentVal;
  }
}

// ============================================================
// Anomalies View
// ============================================================

async function loadAnomalies() {
  try {
    const status = document.getElementById('anomaly-status-filter')?.value || '';
    const sortBy = document.getElementById('anomaly-sort')?.value || 'score';
    const params = new URLSearchParams({ limit: '50', offset: '0', sortBy });
    if (status) params.set('status', status);

    const data = await api(`/anomalies?${params}`);
    renderAnomalyTable(data.anomalies, 'anomalies-table');
  } catch (error) {
    console.error('Failed to load anomalies:', error);
  }
}

async function showAnomalyDetail(detectionId) {
  try {
    const data = await api(`/anomalies/${detectionId}`);
    const { anomaly, localization } = data;

    document.getElementById('modal-title').textContent = `Anomaly: ${anomaly.route_id}`;

    let bodyHTML = `
      <div class="detail-grid">
        <div class="detail-item">
          <span class="detail-label">Route</span>
          <span class="detail-value">${anomaly.route_id}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Date</span>
          <span class="detail-value">${anomaly.sim_date || '—'}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Anomaly Score</span>
          <span class="detail-value" style="color:${anomaly.anomaly_score > 0.7 ? '#ef4444' : '#f59e0b'}">${(anomaly.anomaly_score * 100).toFixed(1)}%</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Status</span>
          <span class="status-badge status-${anomaly.status}">${anomaly.status}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Expected Revenue</span>
          <span class="detail-value">₹${(anomaly.expected_value || 0).toFixed(2)}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Reported Revenue</span>
          <span class="detail-value">₹${(anomaly.reported_value || 0).toFixed(2)}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Revenue Gap</span>
          <span class="detail-value" style="color:var(--color-danger)">₹${(anomaly.discrepancy || 0).toFixed(2)}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Time Window</span>
          <span class="detail-value">${anomaly.time_window || '—'}</span>
        </div>
      </div>
    `;

    if (localization && localization.length > 0) {
      bodyHTML += '<h4 style="margin-bottom:0.75rem;color:var(--text-secondary);">🎯 Segment Localization (Top 5)</h4>';
      bodyHTML += '<div style="display:flex;flex-direction:column;gap:0.5rem;">';
      for (const loc of localization.slice(0, 5)) {
        const scorePct = (loc.localization_score * 100).toFixed(1);
        bodyHTML += `
          <div style="background:var(--bg-glass);border:1px solid var(--border-primary);border-radius:var(--radius-sm);padding:0.75rem;display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-weight:600;font-size:0.8rem;">${loc.start_stop_name || loc.segment_start_stop} → ${loc.end_stop_name || loc.segment_end_stop}</div>
              <div style="font-size:0.7rem;color:var(--text-tertiary);">${loc.time_window}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-family:var(--font-mono);font-weight:600;color:${parseFloat(scorePct) > 50 ? '#ef4444' : '#f59e0b'};">${scorePct}%</div>
              <div style="font-size:0.65rem;color:var(--text-muted);">Gap: ₹${(loc.flow_discrepancy || 0).toFixed(0)}</div>
            </div>
          </div>
        `;
      }
      bodyHTML += '</div>';
    }

    document.getElementById('modal-body').innerHTML = bodyHTML;

    // Footer with action buttons
    document.getElementById('modal-footer').innerHTML = `
      <button class="btn btn-ghost" onclick="updateAnomalyStatus('${detectionId}', 'dismissed')">Dismiss</button>
      <button class="btn btn-warning" onclick="updateAnomalyStatus('${detectionId}', 'reviewed')">Mark Reviewed</button>
      <button class="btn btn-success" onclick="updateAnomalyStatus('${detectionId}', 'confirmed')">Confirm</button>
    `;

    document.getElementById('modal-overlay').classList.add('active');
  } catch (error) {
    console.error('Failed to load anomaly detail:', error);
  }
}

async function updateAnomalyStatus(detectionId, status) {
  try {
    await api(`/anomalies/${detectionId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    closeModal();
    loadAnomalies();
    refreshDashboard();
  } catch (error) {
    console.error('Failed to update status:', error);
  }
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
}

// ============================================================
// Localization View
// ============================================================

async function loadLocalizationRoutes() {
  if (allRoutes.length === 0) {
    try {
      const data = await api('/routes');
      allRoutes = data.routes;
    } catch (e) { /* ignore */ }
  }
  populateRouteSelectors(allRoutes);
}

async function loadLocalization() {
  const routeId = document.getElementById('loc-route-select').value;
  if (!routeId) return;

  const container = document.getElementById('localization-content');
  container.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Running flow analysis...</p></div>';

  try {
    const data = await api(`/localization/${routeId}`);
    renderLocalization(data.localization, routeId);
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><h3>Error loading localization</h3><p>${error.message}</p></div>`;
  }
}

function renderLocalization(segments, routeId) {
  const container = document.getElementById('localization-content');
  if (!segments || segments.length === 0) {
    container.innerHTML = '<div class="empty-state"><h3>No localization data</h3><p>Run the pipeline to generate segment-level analysis.</p></div>';
    return;
  }

  let html = `
    <div style="margin-bottom:1rem;">
      <span class="sim-badge">📡 Simulated Flow Analysis</span>
      <span style="margin-left:0.5rem;font-size:0.8rem;color:var(--text-tertiary);">
        Segments ranked by min-cost flow localization score — higher score = more likely leakage location
      </span>
    </div>
    <div class="segment-list">
  `;

  for (const seg of segments.slice(0, 20)) {
    const scorePct = (seg.localization_score * 100).toFixed(1);
    const isTop3 = seg.rank_position <= 3;
    const scoreColor = seg.localization_score > 0.5 ? '#ef4444' : seg.localization_score > 0.25 ? '#f59e0b' : '#22c55e';

    html += `
      <div class="segment-card">
        <div class="segment-rank ${isTop3 ? 'top-3' : ''}">#${seg.rank_position}</div>
        <div class="segment-info">
          <div class="segment-stops">${seg.start_stop_name || seg.segment_start_stop} → ${seg.end_stop_name || seg.segment_end_stop}</div>
          <div class="segment-time">🕐 ${seg.time_window} | Stops ${seg.segment_start_seq}–${seg.segment_end_seq}</div>
        </div>
        <div class="segment-metrics">
          <div>
            <div class="segment-metric-value" style="color:${scoreColor}">${scorePct}%</div>
            <div class="segment-metric-label">Score</div>
          </div>
          <div>
            <div class="segment-metric-value">₹${(seg.expected_flow || 0).toFixed(0)}</div>
            <div class="segment-metric-label">Expected</div>
          </div>
          <div>
            <div class="segment-metric-value" style="color:var(--color-danger)">₹${(seg.flow_discrepancy || 0).toFixed(0)}</div>
            <div class="segment-metric-label">Gap</div>
          </div>
        </div>
      </div>
    `;
  }

  html += '</div>';
  container.innerHTML = html;
}

// ============================================================
// Time Series View
// ============================================================

async function loadTimeSeriesRoutes() {
  if (allRoutes.length === 0) {
    try {
      const data = await api('/routes');
      allRoutes = data.routes;
    } catch (e) { /* ignore */ }
  }
  populateRouteSelectors(allRoutes);
}

async function loadTimeSeries() {
  const routeId = document.getElementById('ts-route-select').value;
  if (!routeId) return;

  const container = document.getElementById('timeseries-content');
  container.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Loading time series...</p></div>';

  try {
    const data = await api(`/routes/${routeId}/timeseries`);
    renderTimeSeries(data.timeseries, routeId);
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${error.message}</p></div>`;
  }
}

function renderTimeSeries(timeseries, routeId) {
  const container = document.getElementById('timeseries-content');
  if (!timeseries || timeseries.length === 0) {
    container.innerHTML = '<div class="empty-state"><h3>No time series data</h3></div>';
    return;
  }

  // Aggregate by date
  const byDate = {};
  for (const t of timeseries) {
    if (!byDate[t.sim_date]) {
      byDate[t.sim_date] = { expected: 0, reported: 0, boardings: 0, tickets: 0, anomalies: 0 };
    }
    byDate[t.sim_date].expected += t.expected_revenue;
    byDate[t.sim_date].reported += t.reported_revenue;
    byDate[t.sim_date].boardings += t.total_boardings;
    byDate[t.sim_date].tickets += t.total_tickets;
    byDate[t.sim_date].anomalies += t.anomaly_events;
  }

  const dates = Object.keys(byDate).sort();
  const chartData = dates.map(d => ({
    sim_date: d,
    expected: byDate[d].expected,
    reported: byDate[d].reported,
    anomalies: byDate[d].anomalies,
  }));

  let html = `
    <div style="margin-bottom:1rem;">
      <span class="sim-badge">📡 Simulated Revenue Data</span>
    </div>
    <div class="chart-card">
      <h3>Expected vs Reported Revenue — Route ${routeId}</h3>
      <div class="chart-container" id="ts-chart-container" style="height:300px;"></div>
    </div>
    <div class="kpi-grid" style="margin-top:1rem;">
      <div class="kpi-card">
        <div class="kpi-icon">📊</div>
        <div class="kpi-content">
          <span class="kpi-value">${dates.length}</span>
          <span class="kpi-label">Days of Data</span>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">💰</div>
        <div class="kpi-content">
          <span class="kpi-value">₹${formatCurrency(chartData.reduce((s, d) => s + d.expected, 0))}</span>
          <span class="kpi-label">Total Expected</span>
        </div>
      </div>
      <div class="kpi-card kpi-highlight">
        <div class="kpi-icon">📉</div>
        <div class="kpi-content">
          <span class="kpi-value">₹${formatCurrency(chartData.reduce((s, d) => s + (d.expected - d.reported), 0))}</span>
          <span class="kpi-label">Total Leakage</span>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon">⚠️</div>
        <div class="kpi-content">
          <span class="kpi-value">${chartData.reduce((s, d) => s + d.anomalies, 0)}</span>
          <span class="kpi-label">Anomaly Events</span>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = html;

  // Render chart after DOM update
  setTimeout(() => {
    const chartContainer = document.getElementById('ts-chart-container');
    if (chartContainer) {
      renderTimeSeriesChart(chartData, chartContainer);
    }
  }, 50);
}

function renderTimeSeriesChart(data, container) {
  const canvas = document.createElement('canvas');
  canvas.width = container.clientWidth * 2;
  canvas.height = 600;
  canvas.style.width = '100%';
  canvas.style.height = '300px';
  container.innerHTML = '';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const padding = { top: 30, right: 30, bottom: 60, left: 80 };
  const chartW = W - padding.left - padding.right;
  const chartH = H - padding.top - padding.bottom;

  const maxVal = Math.max(...data.map(d => Math.max(d.expected, d.reported)));
  const yScale = maxVal > 0 ? chartH / (maxVal * 1.1) : 1;
  const xStep = data.length > 1 ? chartW / (data.length - 1) : chartW;

  ctx.fillStyle = 'rgba(17, 24, 39, 0.3)';
  ctx.fillRect(0, 0, W, H);

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) {
    const y = padding.top + (chartH / 5) * i;
    ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(W - padding.right, y); ctx.stroke();
    const val = maxVal * 1.1 * (1 - i / 5);
    ctx.fillStyle = '#64748b'; ctx.font = '20px Inter'; ctx.textAlign = 'right';
    ctx.fillText(`₹${formatCurrency(val)}`, padding.left - 10, y + 6);
  }

  // Lines
  function drawLine(values, color) {
    ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.lineJoin = 'round';
    values.forEach((v, i) => {
      const x = padding.left + i * xStep;
      const y = padding.top + chartH - v * yScale;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  drawLine(data.map(d => d.expected), '#6366f1');
  drawLine(data.map(d => d.reported), '#10b981');

  // Anomaly dots
  data.forEach((d, i) => {
    if (d.anomalies > 0) {
      const x = padding.left + i * xStep;
      const y = padding.top + chartH - d.reported * yScale;
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(239, 68, 68, 0.8)';
      ctx.fill();
      ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 2; ctx.stroke();
    }
  });

  // X labels
  const step = Math.max(1, Math.floor(data.length / 10));
  ctx.fillStyle = '#64748b'; ctx.font = '18px Inter'; ctx.textAlign = 'center';
  data.forEach((d, i) => {
    if (i % step === 0) {
      ctx.fillText(d.sim_date.substring(5), padding.left + i * xStep, H - padding.bottom + 30);
    }
  });
}

// ============================================================
// Monitoring View
// ============================================================

async function loadMonitoring() {
  try {
    const data = await api('/monitoring/metrics');

    document.getElementById('mon-pipeline-status').textContent =
      data.pipeline?.running ? '🟢 Running' : '⚪ Idle';
    document.getElementById('mon-events-ingested').textContent =
      (data.pipeline?.totalIngested || 0).toLocaleString();
    document.getElementById('mon-dead-letters').textContent =
      (data.deadLetterCount || 0).toLocaleString();
    document.getElementById('mon-active-models').textContent =
      (data.activeModels?.length || 0).toString();

    // Models table
    const modelsContainer = document.getElementById('models-table');
    if (data.activeModels && data.activeModels.length > 0) {
      let html = '<table><thead><tr><th>Model</th><th>Type</th><th>Version</th><th>Trained At</th><th>Metrics</th></tr></thead><tbody>';
      for (const m of data.activeModels) {
        const metrics = m.metrics ? JSON.parse(m.metrics) : {};
        html += `<tr>
          <td style="font-weight:600;color:var(--text-primary)">${m.model_id}</td>
          <td>${m.model_type}</td>
          <td style="font-family:var(--font-mono)">${m.version}</td>
          <td>${m.trained_at || '—'}</td>
          <td style="font-family:var(--font-mono);font-size:0.7rem">${JSON.stringify(metrics).substring(0, 60)}...</td>
        </tr>`;
      }
      html += '</tbody></table>';
      modelsContainer.innerHTML = html;
    }
  } catch (error) {
    console.error('Failed to load monitoring:', error);
  }
}

// ============================================================
// Initialization
// ============================================================

async function init() {
  console.log('🚌 FareGuard Dashboard initializing...');

  // Load dashboard data
  try {
    await refreshDashboard();
  } catch (e) {
    console.warn('Dashboard data not yet available - run the pipeline first');
  }

  // Load routes for selectors
  try {
    const data = await api('/routes');
    allRoutes = data.routes || [];
    populateRouteSelectors(allRoutes);
  } catch (e) {
    console.warn('Routes not yet available');
  }

  // Auto-refresh every 30 seconds
  setInterval(() => {
    if (currentView === 'dashboard') refreshDashboard();
  }, 30000);
}

// Keyboard shortcut
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});

// Start
init();
