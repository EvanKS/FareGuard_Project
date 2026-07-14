/**
 * FareGuard - Database Module
 * Lightweight SQLite-compatible database using better-sqlite3.
 * Falls back to a JSON-file-based store if native module unavailable.
 */
const path = require('path');
const fs = require('fs');
const config = require('./config');
const logger = require('./logger');

const log = logger.child({ service: 'database' });

// Ensure data directory exists
const dbDir = path.dirname(config.database.path);
if (!fs.existsSync(dbDir)) {
  fs.mkdirSync(dbDir, { recursive: true });
}

let db = null;
let useNative = false;

// ============================================================
// Simple JSON-backed SQL-like store (no native deps required)
// ============================================================

class JsonStore {
  constructor(filePath) {
    this.filePath = filePath.replace('.db', '.json');
    this.tables = {};
    this.autoIncrements = {};
    this.dirty = false;
    this.saveTimer = null;

    // Load existing data
    if (fs.existsSync(this.filePath)) {
      try {
        const raw = fs.readFileSync(this.filePath, 'utf-8');
        const data = JSON.parse(raw);
        this.tables = data.tables || {};
        this.autoIncrements = data.autoIncrements || {};
      } catch (e) {
        this.tables = {};
        this.autoIncrements = {};
      }
    }
  }

  _ensureTable(name) {
    if (!this.tables[name]) {
      this.tables[name] = [];
    }
    return this.tables[name];
  }

  insert(table, row) {
    this._ensureTable(table);
    // Handle auto-increment id
    if (row.id === undefined || row.id === null) {
      if (!this.autoIncrements[table]) this.autoIncrements[table] = 0;
      this.autoIncrements[table]++;
      row.id = this.autoIncrements[table];
    }
    // Check unique constraint (by primary key)
    const pkField = this._getPrimaryKey(table);
    if (pkField && row[pkField] !== undefined) {
      if (!this._pkIndexes) this._pkIndexes = {};
      if (!this._pkIndexes[table]) {
        this._pkIndexes[table] = new Map();
        // build index if missing
        this.tables[table].forEach((r, idx) => {
          if (r[pkField] !== undefined) this._pkIndexes[table].set(r[pkField], idx);
        });
      }

      const existingIdx = this._pkIndexes[table].get(row[pkField]);
      if (existingIdx !== undefined) {
        this.tables[table][existingIdx] = { ...this.tables[table][existingIdx], ...row };
        this._markDirty();
        return;
      }
      
      // Not found, so add
      this.tables[table].push(row);
      this._pkIndexes[table].set(row[pkField], this.tables[table].length - 1);
    } else {
      this.tables[table].push(row);
    }
    this._markDirty();
  }

  _getPrimaryKey(table) {
    const pks = {
      routes: 'route_id', stops: 'stop_id', trips: 'trip_id',
      ticketing_events: 'event_id', anomaly_ground_truth: 'anomaly_id',
      detected_anomalies: 'detection_id', model_registry: 'model_id',
      users: 'user_id',
    };
    return pks[table] || null;
  }

  select(table, where = null, orderBy = null, limit = null, offset = 0) {
    let results = [...(this.tables[table] || [])];
    if (where) {
      results = results.filter(where);
    }
    if (orderBy) {
      results.sort(orderBy);
    }
    if (offset > 0) {
      results = results.slice(offset);
    }
    if (limit) {
      results = results.slice(0, limit);
    }
    return results;
  }

  update(table, where, updates) {
    const rows = this.tables[table] || [];
    let modified = 0;
    for (const row of rows) {
      if (where(row)) {
        Object.assign(row, updates);
        modified++;
      }
    }
    if (modified > 0) this._markDirty();
    return modified;
  }

  count(table, where = null) {
    if (!this.tables[table]) return 0;
    if (where) return this.tables[table].filter(where).length;
    return this.tables[table].length;
  }

  distinct(table, field, where = null) {
    let rows = this.tables[table] || [];
    if (where) rows = rows.filter(where);
    return [...new Set(rows.map(r => r[field]))];
  }

  aggregate(table, where, fields) {
    let rows = this.tables[table] || [];
    if (where) rows = rows.filter(where);
    const result = {};
    for (const [alias, fn] of Object.entries(fields)) {
      result[alias] = fn(rows);
    }
    return result;
  }

  groupBy(table, where, groupField, fields) {
    let rows = this.tables[table] || [];
    if (where) rows = rows.filter(where);
    const groups = {};
    for (const row of rows) {
      const key = row[groupField];
      if (!groups[key]) groups[key] = [];
      groups[key].push(row);
    }
    return Object.entries(groups).map(([key, groupRows]) => {
      const result = { [groupField]: key };
      for (const [alias, fn] of Object.entries(fields)) {
        result[alias] = fn(groupRows);
      }
      return result;
    });
  }

  _markDirty() {
    this.dirty = true;
    // Debounced save
    if (!this.saveTimer) {
      this.saveTimer = setTimeout(() => {
        this.save();
        this.saveTimer = null;
      }, 2000);
    }
  }

  save() {
    if (!this.dirty) return;
    try {
      const data = JSON.stringify({
        tables: this.tables,
        autoIncrements: this.autoIncrements,
      });
      fs.writeFileSync(this.filePath, data);
      this.dirty = false;
    } catch (e) {
      log.error('Failed to save database', { error: e.message });
    }
  }

  saveSync() {
    this.dirty = true;
    this.save();
  }

  close() {
    if (this.saveTimer) {
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
    }
    this.save();
  }
}

// ============================================================
// SQL-like Prepared Statement Wrapper over JsonStore
// ============================================================

class PreparedStatement {
  constructor(store, sql) {
    this.store = store;
    this.sql = sql.trim();
  }

  run(...params) {
    return this._execute(params, 'run');
  }

  get(...params) {
    const results = this._execute(params, 'get');
    return results;
  }

  all(...params) {
    return this._execute(params, 'all');
  }

  _resolveParams(params) {
    if (params.length === 1 && typeof params[0] === 'object' && !Array.isArray(params[0])) {
      return { type: 'named', values: params[0] };
    }
    return { type: 'positional', values: params };
  }

  _execute(params, mode) {
    const sql = this.sql;
    const { type, values } = this._resolveParams(params);

    // Parse SQL type
    const upperSql = sql.toUpperCase().trim();

    if (upperSql.startsWith('INSERT') || upperSql.startsWith('REPLACE')) {
      return this._handleInsert(sql, type, values);
    }
    if (upperSql.startsWith('UPDATE')) {
      return this._handleUpdate(sql, type, values);
    }
    if (upperSql.startsWith('SELECT')) {
      return this._handleSelect(sql, type, values, mode);
    }
    if (upperSql.startsWith('DELETE')) {
      return this._handleDelete(sql, type, values);
    }

    return mode === 'all' ? [] : undefined;
  }

  _handleInsert(sql, paramType, values) {
    // Parse: INSERT OR REPLACE INTO table (...) VALUES (...)
    const match = sql.match(/INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)/i);
    if (!match) return { changes: 0 };

    const table = match[1];
    const columns = match[2].split(',').map(c => c.trim().replace('@', '').replace('?', '').replace('$', ''));
    const valuePlaceholders = match[3].split(',').map(v => v.trim());

    const row = {};
    columns.forEach((col, i) => {
      if (paramType === 'named') {
        row[col] = values[col] !== undefined ? values[col] : values[`@${col}`] || null;
      } else {
        row[col] = values[i] !== undefined ? values[i] : null;
      }
    });

    // Add created_at if the table typically has it
    if (!row.created_at) {
      row.created_at = new Date().toISOString();
    }

    this.store.insert(table, row);
    return { changes: 1 };
  }

  _handleUpdate(sql, paramType, values) {
    // Parse: UPDATE table SET col=? WHERE col=?
    const tableMatch = sql.match(/UPDATE\s+(\w+)\s+SET/i);
    if (!tableMatch) return { changes: 0 };

    const table = tableMatch[1];
    
    // Extract SET and WHERE parts
    const setPart = sql.match(/SET\s+(.*?)(?:\s+WHERE|$)/i);
    const wherePart = sql.match(/WHERE\s+(.*?)$/i);

    if (!setPart) return { changes: 0 };

    // Build update object (simplified - handles basic cases)
    const updates = {};
    const setAssignments = setPart[1].split(',');
    let paramIdx = 0;

    for (const assignment of setAssignments) {
      const [colPart] = assignment.split('=').map(s => s.trim());
      const col = colPart.replace(/\s/g, '');
      if (col === "datetime('now')") continue;
      if (paramType === 'positional') {
        updates[col] = values[paramIdx++];
      }
    }

    // Build where filter
    let whereFilter = () => true;
    if (wherePart) {
      const whereCol = wherePart[1].match(/(\w+)\s*=\s*\?/)?.[1];
      if (whereCol && paramType === 'positional') {
        const whereVal = values[paramIdx];
        whereFilter = (row) => row[whereCol] === whereVal;
      }
    }

    const modified = this.store.update(table, whereFilter, updates);
    return { changes: modified };
  }

  _handleSelect(sql, paramType, values, mode) {
    // Parse the FROM table
    const fromMatch = sql.match(/FROM\s+(\w+)/i);
    if (!fromMatch) return mode === 'all' ? [] : undefined;

    const table = fromMatch[1];

    // Check for COUNT(*)
    const isCount = /SELECT\s+COUNT\s*\(\s*\*\s*\)/i.test(sql);

    // Parse WHERE conditions
    let whereFilter = null;
    const whereMatch = sql.match(/WHERE\s+(.+?)(?:\s+GROUP|\s+ORDER|\s+LIMIT|$)/i);

    if (whereMatch) {
      whereFilter = this._buildWhereFilter(whereMatch[1], paramType, values);
    }

    // Parse ORDER BY
    let sortFn = null;
    const orderMatch = sql.match(/ORDER\s+BY\s+([\w.]+)\s*(ASC|DESC)?/i);
    if (orderMatch) {
      const orderCol = orderMatch[1].replace(/\w+\./, ''); // Remove table prefix
      const desc = orderMatch[2]?.toUpperCase() === 'DESC';
      sortFn = (a, b) => {
        const va = a[orderCol] ?? '';
        const vb = b[orderCol] ?? '';
        return desc ? (vb > va ? 1 : vb < va ? -1 : 0) : (va > vb ? 1 : va < vb ? -1 : 0);
      };
    }

    // Parse LIMIT
    let limit = null;
    let offset = 0;
    const limitMatch = sql.match(/LIMIT\s+(\d+|\?)/i);
    if (limitMatch) {
      limit = limitMatch[1] === '?' ? values[this._countPlaceholdersBefore(sql, limitMatch.index, paramType, values)] : parseInt(limitMatch[1]);
    }
    const offsetMatch = sql.match(/OFFSET\s+(\d+|\?)/i);
    if (offsetMatch) {
      offset = offsetMatch[1] === '?' ? values[this._countPlaceholdersBefore(sql, offsetMatch.index, paramType, values)] : parseInt(offsetMatch[1]);
    }

    // Handle JOINs - merge tables
    let results;
    const joinMatches = [...sql.matchAll(/JOIN\s+(\w+)\s+(\w+)?\s*ON\s+(\w+\.?\w+)\s*=\s*(\w+\.?\w+)/gi)];
    
    if (joinMatches.length > 0) {
      results = this._handleJoins(table, joinMatches, whereFilter, sortFn, limit, offset);
    } else {
      results = this.store.select(table, whereFilter, sortFn, limit, offset);
    }

    if (isCount) {
      const counted = whereFilter ? this.store.count(table, whereFilter) : this.store.count(table);
      return mode === 'all' ? [{ cnt: counted }] : { cnt: counted };
    }

    // Handle DISTINCT
    if (/SELECT\s+DISTINCT/i.test(sql)) {
      const distinctCol = sql.match(/DISTINCT\s+(?:\w+\.)?(\w+)/i)?.[1] || sql.match(/DISTINCT\s+(\w+)/i)?.[1];
      if (distinctCol) {
        const seen = new Set();
        results = results.filter(r => {
          const val = r[distinctCol];
          if (seen.has(val)) return false;
          seen.add(val);
          return true;
        });
      }
    }

    // Handle SUM/COALESCE aggregates
    if (/SELECT.*(?:SUM|COALESCE|COUNT\s*\()/i.test(sql) && !isCount) {
      return this._handleAggregateSelect(sql, table, whereFilter, mode, results);
    }

    // Handle subqueries in SELECT (simplified - return what we have)
    if (mode === 'get') {
      return results[0] || undefined;
    }
    return results;
  }

  _handleAggregateSelect(sql, table, whereFilter, mode, rows) {
    // Parse aggregate functions
    const result = {};
    
    // Match SUM patterns
    const sumMatches = [...sql.matchAll(/(?:COALESCE\s*\(\s*)?SUM\s*\(\s*(?:\w+\.)?(\w+)\s*\)\s*(?:,\s*0\s*\))?\s*(?:as\s+)?(\w+)?/gi)];
    for (const match of sumMatches) {
      const field = match[1];
      const alias = match[2] || `sum_${field}`;
      result[alias] = rows.reduce((s, r) => s + (r[field] || 0), 0);
    }

    // Match COUNT patterns  
    const countMatches = [...sql.matchAll(/COUNT\s*\(\s*\*\s*\)\s+(?:as\s+)?(\w+)/gi)];
    for (const match of countMatches) {
      result[match[1]] = rows.length;
    }

    // Match CASE/SUM for conditional counts
    const caseMatches = [...sql.matchAll(/SUM\s*\(\s*CASE\s+WHEN\s+(\w+)\s*=\s*(\d+|'[^']*')\s+THEN\s+1\s+ELSE\s+0\s+END\s*\)\s+(?:as\s+)?(\w+)/gi)];
    for (const match of caseMatches) {
      const field = match[1];
      let val = match[2];
      if (val.startsWith("'")) val = val.slice(1, -1);
      else val = parseInt(val);
      const alias = match[3];
      result[alias] = rows.filter(r => r[field] == val).length;
    }

    // COUNT(DISTINCT ...)
    const distinctCountMatches = [...sql.matchAll(/COUNT\s*\(\s*DISTINCT\s+(?:\w+\.)?(\w+)\s*\)\s+(?:as\s+)?(\w+)/gi)];
    for (const match of distinctCountMatches) {
      result[match[2]] = new Set(rows.map(r => r[match[1]])).size;
    }

    if (Object.keys(result).length === 0) {
      // Fallback: return rows
      return mode === 'get' ? rows[0] : rows;
    }

    return mode === 'all' ? [result] : result;
  }

  _handleJoins(mainTable, joinMatches, whereFilter, sortFn, limit, offset) {
    let results = [...(this.store.tables[mainTable] || [])];

    for (const joinMatch of joinMatches) {
      const joinTable = joinMatch[1];
      const joinAlias = joinMatch[2] || joinTable;
      const leftField = joinMatch[3].split('.').pop();
      const rightField = joinMatch[4].split('.').pop();

      const joinRows = this.store.tables[joinTable] || [];
      const joinIndex = {};
      for (const jr of joinRows) {
        const key = jr[rightField] ?? jr[leftField];
        if (!joinIndex[key]) joinIndex[key] = jr;
      }

      results = results.map(r => {
        const joinKey = r[leftField] ?? r[rightField];
        const joinRow = joinIndex[joinKey];
        return joinRow ? { ...r, ...joinRow } : r;
      });
    }

    if (whereFilter) results = results.filter(whereFilter);
    if (sortFn) results.sort(sortFn);
    if (offset > 0) results = results.slice(offset);
    if (limit) results = results.slice(0, limit);

    return results;
  }

  _buildWhereFilter(whereStr, paramType, values) {
    // Handle simple conditions: col = ? AND col2 = ?
    const conditions = whereStr.split(/\s+AND\s+/i);
    let paramIdx = 0;

    const filters = [];
    for (const cond of conditions) {
      const trimmed = cond.trim();
      if (trimmed === '1=1') continue;

      // col = ?
      let match = trimmed.match(/(?:\w+\.)?(\w+)\s*=\s*\?/);
      if (match) {
        const col = match[1];
        const val = values[paramIdx++];
        filters.push(row => row[col] == val);
        continue;
      }

      // col >= ?
      match = trimmed.match(/(?:\w+\.)?(\w+)\s*>=\s*\?/);
      if (match) {
        const col = match[1];
        const val = values[paramIdx++];
        filters.push(row => (row[col] ?? 0) >= val);
        continue;
      }

      // col < ?
      match = trimmed.match(/(?:\w+\.)?(\w+)\s*<\s*\?/);
      if (match) {
        const col = match[1];
        const val = values[paramIdx++];
        filters.push(row => (row[col] ?? 0) < val);
        continue;
      }

      // col <= ?
      match = trimmed.match(/(?:\w+\.)?(\w+)\s*<=\s*\?/);
      if (match) {
        const col = match[1];
        const val = values[paramIdx++];
        filters.push(row => (row[col] ?? 0) <= val);
        continue;
      }

      // col = 'value'
      match = trimmed.match(/(?:\w+\.)?(\w+)\s*=\s*'([^']*)'/);
      if (match) {
        const col = match[1];
        const val = match[2];
        filters.push(row => row[col] == val);
        continue;
      }

      // col IN (?,?,...)
      match = trimmed.match(/(?:\w+\.)?(\w+)\s+IN\s*\(/i);
      if (match) {
        const col = match[1];
        const numPlaceholders = (trimmed.match(/\?/g) || []).length;
        const inValues = values.slice(paramIdx, paramIdx + numPlaceholders);
        paramIdx += numPlaceholders;
        filters.push(row => inValues.includes(row[col]));
        continue;
      }

      // col IS NOT NULL
      match = trimmed.match(/(?:\w+\.)?(\w+)\s+IS\s+NOT\s+NULL/i);
      if (match) {
        filters.push(row => row[match[1]] != null);
        continue;
      }
    }

    if (filters.length === 0) return null;
    return (row) => filters.every(f => f(row));
  }

  _countPlaceholdersBefore(sql, pos, paramType, values) {
    const before = sql.substring(0, pos);
    return (before.match(/\?/g) || []).length;
  }

  _handleDelete(sql, paramType, values) {
    const tableMatch = sql.match(/FROM\s+(\w+)/i);
    if (!tableMatch) return { changes: 0 };
    const table = tableMatch[1];
    const whereMatch = sql.match(/WHERE\s+(.+?)$/i);
    if (!whereMatch) {
      const count = (this.store.tables[table] || []).length;
      this.store.tables[table] = [];
      return { changes: count };
    }
    const filter = this._buildWhereFilter(whereMatch[1], paramType, values);
    const before = (this.store.tables[table] || []).length;
    this.store.tables[table] = (this.store.tables[table] || []).filter(r => !filter(r));
    return { changes: before - this.store.tables[table].length };
  }
}

// ============================================================
// Database Wrapper (compatible API)
// ============================================================

class DatabaseAPIWrapper {
  constructor(store) {
    this.store = store;
  }

  prepare(sql) {
    return new PreparedStatement(this.store, sql);
  }

  exec(sql) {
    // Execute raw SQL (for schema creation - handled by store)
    // Schema is implicit in JsonStore
  }

  pragma(str) {
    // No-op for JSON store
  }

  transaction(fn) {
    return (...args) => {
      try {
        const result = fn(...args);
        this.store.saveSync();
        return result;
      } catch (e) {
        throw e;
      }
    };
  }

  close() {
    this.store.close();
  }
}

// ============================================================
// Public API
// ============================================================

function getDb() {
  if (!db) {
    const store = new JsonStore(config.database.path);
    db = new DatabaseAPIWrapper(store);
    log.info('Database connection established (JSON store)', { path: config.database.path });
  }
  return db;
}

function initializeSchema() {
  getDb(); // Ensure DB is created
  log.info('Database schema initialized (JSON store)');
}

function closeDb() {
  if (db) {
    db.store.save();
    db = null;
    log.info('Database connection closed');
  }
}

module.exports = { getDb, initializeSchema, closeDb };
