"""Web server: API + real-time HTML dashboard with multi-chart and diagnosis."""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

from config import Settings, get_settings
from engine import ElasticityEngine

logger = logging.getLogger(__name__)

app = Flask(__name__)
engine: ElasticityEngine = None  # type: ignore
_settings: Settings = None  # type: ignore


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CSS Intelligent Ops Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
.header { background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #475569; }
.header h1 { font-size: 22px; font-weight: 600; }
.header .status { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.dot { width: 10px; height: 10px; border-radius: 50%; animation: pulse 2s infinite; }
.dot.green { background: #22c55e; }
.dot.red { background: #ef4444; }
.dot.yellow { background: #eab308; }
.dot.gray { background: #6b7280; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px 30px; max-width: 1400px; margin: 0 auto; }
.card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }
.card h2 { font-size: 16px; font-weight: 500; color: #94a3b8; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px; }
.metric-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #334155; }
.metric-row:last-child { border-bottom: none; }
.metric-label { font-size: 13px; color: #94a3b8; }
.metric-value { font-size: 20px; font-weight: 700; }
.metric-value.danger { color: #ef4444; }
.metric-value.warning { color: #eab308; }
.metric-value.good { color: #22c55e; }
.progress-bar { width: 100%; height: 6px; background: #334155; border-radius: 3px; margin-top: 4px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
.progress-fill.danger { background: #ef4444; }
.progress-fill.warning { background: #eab308; }
.progress-fill.good { background: #22c55e; }
.full-width { grid-column: 1 / -1; }
canvas { width: 100% !important; height: 220px !important; }
.log-table { width: 100%; font-size: 13px; border-collapse: collapse; }
.log-table th { text-align: left; padding: 8px; color: #94a3b8; border-bottom: 1px solid #475569; }
.log-table td { padding: 8px; border-bottom: 1px solid #334155; }
.log-table .scale_out { color: #ef4444; }
.log-table .scale_in { color: #3b82f6; }
.log-table .hold { color: #22c55e; }
.log-container { max-height: 300px; overflow-y: auto; }
.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; }
.config-item { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; }
.config-key { color: #94a3b8; }
.config-val { color: #e2e8f0; font-weight: 600; }
/* Health card */
.health-card { text-align: center; }
.health-status { font-size: 28px; font-weight: 700; margin: 8px 0; }
.health-status.green { color: #22c55e; }
.health-status.yellow { color: #eab308; }
.health-status.red { color: #ef4444; }
.health-status.gray { color: #6b7280; }
.health-detail { font-size: 13px; color: #94a3b8; margin-top: 4px; }
/* Diagnosis panel */
.diagnosis-panel { margin-top: 12px; padding: 16px; border-radius: 8px; background: #0f172a; border: 1px solid #475569; }
.diagnosis-panel .root-cause { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.diagnosis-panel .severity { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.diagnosis-panel .severity.critical { background: #ef444433; color: #ef4444; }
.diagnosis-panel .severity.warning { background: #eab30833; color: #eab308; }
.diagnosis-panel .severity.info { background: #3b82f633; color: #3b82f6; }
.suggestion-list { list-style: none; padding: 0; margin-top: 8px; }
.suggestion-list li { padding: 4px 0; font-size: 13px; color: #cbd5e1; }
.suggestion-list li::before { content: "→ "; color: #3b82f6; }
.auto-fix { margin-top: 8px; font-size: 13px; }
.auto-fix button { margin-left: 8px; padding: 4px 12px; border-radius: 4px; border: 1px solid #3b82f6; background: #3b82f633; color: #3b82f6; cursor: pointer; font-size: 12px; }
.auto-fix button:hover { background: #3b82f655; }
/* Decision box */
.decision-box { padding: 16px; border-radius: 8px; margin-top: 12px; font-size: 15px; }
.decision-box.scale_out { background: #7f1d1d33; border: 1px solid #ef4444; }
.decision-box.scale_in { background: #1e3a5f33; border: 1px solid #3b82f6; }
.decision-box.hold { background: #1a2e1a33; border: 1px solid #22c55e; }
.decision-label { font-weight: 700; font-size: 18px; margin-bottom: 4px; }
.decision-reason { color: #94a3b8; font-size: 13px; }
/* Metric group */
.metric-group-title { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 8px 0 4px; padding-top: 8px; border-top: 1px solid #1e293b; }
</style>
</head>
<body>
<div class="header">
  <h1>CSS Intelligent Ops Dashboard</h1>
  <div class="status">
    <div class="dot green" id="statusDot"></div>
    <span id="statusText">Connecting...</span>
  </div>
</div>
<div class="container">

  <!-- Cluster Health -->
  <div class="card health-card">
    <h2>Cluster Health</h2>
    <div class="health-status green" id="healthStatus">HEALTHY</div>
    <div class="health-detail" id="healthDetail">--</div>
    <div id="diagnosisPanel"></div>
  </div>

  <!-- AI Decision -->
  <div class="card">
    <h2>AI Decision</h2>
    <div class="metric-row">
      <span class="metric-label">Decision</span>
      <span class="metric-value" id="aiDecision">--</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Delta</span>
      <span class="metric-value" style="font-size:18px" id="aiDelta">--</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Cooldown</span>
      <span class="metric-value" style="font-size:18px" id="aiCooldown">--</span>
    </div>
    <div class="decision-box hold" id="decisionBox">
      <div class="decision-label" id="decisionLabel">HOLD</div>
      <div class="decision-reason" id="decisionReason">Waiting for data...</div>
    </div>
  </div>

  <!-- Key Metrics Overview -->
  <div class="card full-width">
    <h2>Key Metrics</h2>
    <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:12px">
      <div>
        <div class="metric-label">CPU Avg</div>
        <div class="metric-value" id="mCpuAvg">--</div>
        <div class="progress-bar"><div class="progress-fill good" id="mCpuAvgBar" style="width:0%"></div></div>
      </div>
      <div>
        <div class="metric-label">CPU Max</div>
        <div class="metric-value" id="mCpuMax">--</div>
        <div class="progress-bar"><div class="progress-fill good" id="mCpuMaxBar" style="width:0%"></div></div>
      </div>
      <div>
        <div class="metric-label">Disk Usage</div>
        <div class="metric-value" id="mDisk">--</div>
        <div class="progress-bar"><div class="progress-fill good" id="mDiskBar" style="width:0%"></div></div>
      </div>
      <div>
        <div class="metric-label">JVM Heap Max</div>
        <div class="metric-value" id="mJvmHeap">--</div>
        <div class="progress-bar"><div class="progress-fill good" id="mJvmHeapBar" style="width:0%"></div></div>
      </div>
      <div>
        <div class="metric-label">Search Latency</div>
        <div class="metric-value" id="mSearchLat">--</div>
      </div>
      <div>
        <div class="metric-label">Indexing Latency</div>
        <div class="metric-value" id="mIndexLat">--</div>
      </div>
      <div>
        <div class="metric-label">Search QPS</div>
        <div class="metric-value" id="mSearchQps">--</div>
      </div>
      <div>
        <div class="metric-label">Indexing TPS</div>
        <div class="metric-value" id="mIndexTps">--</div>
      </div>
      <div>
        <div class="metric-label">TP Search Queue</div>
        <div class="metric-value" id="mTpSearchQ">--</div>
      </div>
      <div>
        <div class="metric-label">TP Write Queue</div>
        <div class="metric-value" id="mTpWriteQ">--</div>
      </div>
      <div>
        <div class="metric-label">Pending Tasks</div>
        <div class="metric-value" id="mPending">--</div>
      </div>
      <div>
        <div class="metric-label">Data Nodes</div>
        <div class="metric-value good" id="mNodes">--</div>
      </div>
    </div>
  </div>

  <!-- Chart 1: CPU & Load -->
  <div class="card">
    <h2>CPU & Load</h2>
    <canvas id="chartCpu"></canvas>
  </div>

  <!-- Chart 2: Disk -->
  <div class="card">
    <h2>Disk</h2>
    <canvas id="chartDisk"></canvas>
  </div>

  <!-- Chart 3: JVM Heap & GC -->
  <div class="card">
    <h2>JVM Heap & GC</h2>
    <canvas id="chartJvm"></canvas>
  </div>

  <!-- Chart 4: QPS & Latency -->
  <div class="card">
    <h2>QPS & Latency</h2>
    <canvas id="chartQps"></canvas>
  </div>

  <!-- Chart 5: Thread Pool -->
  <div class="card full-width">
    <h2>Thread Pool</h2>
    <canvas id="chartTp"></canvas>
  </div>

  <!-- History Log -->
  <div class="card full-width">
    <h2>Action History</h2>
    <div class="log-container">
      <table class="log-table">
        <thead><tr><th>Time</th><th>CPU%</th><th>Disk%</th><th>JVM%</th><th>Nodes</th><th>Health</th><th>Decision</th><th>Action</th><th>Reason</th></tr></thead>
        <tbody id="logBody"></tbody>
      </table>
    </div>
  </div>

  <!-- Config -->
  <div class="card full-width">
    <h2>Configuration</h2>
    <div class="config-grid" id="configGrid"></div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
const MAX_PTS = 60;
const labels = [];

// Chart data arrays
const cpuAvgData=[], cpuMaxData=[], loadData=[];
const diskUsageData=[], diskIoData=[];
const jvmHeapMaxData=[], jvmHeapAvgData=[], gcOldData=[];
const searchRateData=[], indexRateData=[], searchLatData=[], indexLatData=[];
const tpSearchQData=[], tpWriteQData=[], tpFmQData=[], tpRefreshQData=[], tpGenericQData=[], tpMgmtQData=[], pendingData=[];

const chartOpts = (yConf, extra) => ({
  responsive: true,
  scales: {
    y: { ...{ min: 0, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } }, ...yConf },
    x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', maxTicksLimit: 15 } }
  },
  plugins: { legend: { labels: { color: '#e2e8f0', boxWidth: 12, font: { size: 11 } } } },
  animation: { duration: 300 },
  ...extra
});

let chartCpu, chartDisk, chartJvm, chartQps, chartTp;

function initCharts() {
  chartCpu = new Chart(document.getElementById('chartCpu').getContext('2d'), {
    type: 'line',
    data: { labels, datasets: [
      { label: 'CPU Avg%', data: cpuAvgData, borderColor: '#ef4444', backgroundColor: '#ef444422', fill: true, tension: 0.3 },
      { label: 'CPU Max%', data: cpuMaxData, borderColor: '#f87171', backgroundColor: '#f8717122', fill: false, tension: 0.3, borderDash: [4,2] },
      { label: 'Load Avg', data: loadData, borderColor: '#a78bfa', yAxisID: 'y2', tension: 0.3 },
    ]},
    options: chartOpts({}, {
      scales: {
        y: { min: 0, max: 100, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
        y2: { position: 'right', min: 0, grid: { drawOnChartArea: false }, ticks: { color: '#a78bfa' } },
        x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', maxTicksLimit: 15 } }
      }
    })
  });

  chartDisk = new Chart(document.getElementById('chartDisk').getContext('2d'), {
    type: 'line',
    data: { labels, datasets: [
      { label: 'Disk Usage%', data: diskUsageData, borderColor: '#eab308', backgroundColor: '#eab30822', fill: true, tension: 0.3 },
      { label: 'Disk IO%', data: diskIoData, borderColor: '#fb923c', tension: 0.3 },
    ]},
    options: chartOpts({ max: 100 })
  });

  chartJvm = new Chart(document.getElementById('chartJvm').getContext('2d'), {
    type: 'line',
    data: { labels, datasets: [
      { label: 'Heap Max%', data: jvmHeapMaxData, borderColor: '#ef4444', backgroundColor: '#ef444422', fill: true, tension: 0.3 },
      { label: 'Heap Avg%', data: jvmHeapAvgData, borderColor: '#f87171', tension: 0.3, borderDash: [4,2] },
      { label: 'Old GC ms', data: gcOldData, borderColor: '#a78bfa', yAxisID: 'y2', tension: 0.3 },
    ]},
    options: chartOpts({}, {
      scales: {
        y: { min: 0, max: 100, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
        y2: { position: 'right', min: 0, grid: { drawOnChartArea: false }, ticks: { color: '#a78bfa' } },
        x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', maxTicksLimit: 15 } }
      }
    })
  });

  chartQps = new Chart(document.getElementById('chartQps').getContext('2d'), {
    type: 'line',
    data: { labels, datasets: [
      { label: 'Search QPS', data: searchRateData, borderColor: '#22c55e', tension: 0.3 },
      { label: 'Index TPS', data: indexRateData, borderColor: '#3b82f6', tension: 0.3 },
      { label: 'Search Lat ms', data: searchLatData, borderColor: '#ef4444', yAxisID: 'y2', tension: 0.3 },
      { label: 'Index Lat ms', data: indexLatData, borderColor: '#f87171', yAxisID: 'y2', tension: 0.3, borderDash: [4,2] },
    ]},
    options: chartOpts({}, {
      scales: {
        y: { min: 0, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
        y2: { position: 'right', min: 0, grid: { drawOnChartArea: false }, ticks: { color: '#ef4444' } },
        x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', maxTicksLimit: 15 } }
      }
    })
  });

  chartTp = new Chart(document.getElementById('chartTp').getContext('2d'), {
    type: 'line',
    data: { labels, datasets: [
      { label: 'Search Queue', data: tpSearchQData, borderColor: '#22c55e', tension: 0.3 },
      { label: 'Write Queue', data: tpWriteQData, borderColor: '#3b82f6', tension: 0.3 },
      { label: 'ForceMerge Queue', data: tpFmQData, borderColor: '#eab308', tension: 0.3 },
      { label: 'Refresh Queue', data: tpRefreshQData, borderColor: '#a78bfa', tension: 0.3 },
      { label: 'Generic Queue', data: tpGenericQData, borderColor: '#fb923c', tension: 0.3 },
      { label: 'Mgmt Queue', data: tpMgmtQData, borderColor: '#f472b6', tension: 0.3 },
      { label: 'Pending Tasks', data: pendingData, borderColor: '#ef4444', borderDash: [4,2], tension: 0.3 },
    ]},
    options: chartOpts({})
  });
}

function colorClass(val, warn, danger) {
  if (val >= danger) return 'danger';
  if (val >= warn) return 'warning';
  return 'good';
}

function fmt(v, d=1) { return v != null ? v.toFixed(d) : '--'; }
function formatTime(iso) { if (!iso) return '--'; return new Date(iso).toLocaleTimeString(); }

function pushData(arr, val) { arr.push(val); if (arr.length > MAX_PTS) arr.shift(); }

function updateDashboard(data) {
  const m = data.metrics || {};
  const d = data.decision || {};
  const h = data.health || {};
  const diag = data.diagnosis || {};

  // Status dot
  const dot = document.getElementById('statusDot');
  const hColor = h.ces_status?.color || 'green';
  dot.className = 'dot ' + hColor;
  document.getElementById('statusText').textContent = h.healthy ? 'Healthy' : 'Unhealthy';

  // Health card
  const hs = document.getElementById('healthStatus');
  hs.textContent = h.healthy ? 'HEALTHY' : (h.ces_status?.label || 'UNHEALTHY').toUpperCase();
  hs.className = 'health-status ' + hColor;
  let detail = '';
  if (h.api_status) detail += 'API: ' + h.api_status;
  if (h.unhealthy_nodes && h.unhealthy_nodes.length > 0) detail += ' | Unhealthy nodes: ' + h.unhealthy_nodes.length;
  document.getElementById('healthDetail').textContent = detail || 'All nodes running';

  // Diagnosis panel
  const dp = document.getElementById('diagnosisPanel');
  if (diag.root_cause) {
    let html = '<div class="diagnosis-panel">';
    html += '<div class="root-cause">' + diag.root_cause + '</div>';
    html += '<span class="severity ' + (diag.severity||'warning') + '">' + (diag.severity||'warning').toUpperCase() + '</span>';
    if (diag.suggestions && diag.suggestions.length > 0) {
      html += '<ul class="suggestion-list">';
      diag.suggestions.forEach(s => { html += '<li>' + s + '</li>'; });
      html += '</ul>';
    }
    if (diag.auto_fix_available) {
      html += '<div class="auto-fix">Auto-fix: ' + (diag.auto_fix_action||'') + ' <button onclick="executeFix()">Execute</button></div>';
    }
    html += '</div>';
    dp.innerHTML = html;
  } else {
    dp.innerHTML = '';
  }

  // Key metrics
  const cpu = m.cpu_avg || 0, cpuMax = m.cpu_max || 0, disk = m.disk_usage_pct || 0;
  const jvmH = m.jvm_heap_max || 0, sLat = m.search_latency || 0, iLat = m.indexing_latency || 0;
  const setM = (id, v, u) => { const el = document.getElementById(id); if(el) el.textContent = fmt(v) + (u||''); };
  const setBar = (id, v, w, d) => { const el = document.getElementById(id); if(el) { el.style.width = Math.min(v,100)+'%'; el.className = 'progress-fill ' + colorClass(v,w,d); } };

  setM('mCpuAvg', cpu, '%'); setBar('mCpuAvgBar', cpu, 60, 80);
  setM('mCpuMax', cpuMax, '%'); setBar('mCpuMaxBar', cpuMax, 60, 80);
  document.getElementById('mCpuAvg').className = 'metric-value ' + colorClass(cpu, 60, 80);
  document.getElementById('mCpuMax').className = 'metric-value ' + colorClass(cpuMax, 60, 80);

  setM('mDisk', disk, '%'); setBar('mDiskBar', disk, 70, 85);
  document.getElementById('mDisk').className = 'metric-value ' + colorClass(disk, 70, 85);

  setM('mJvmHeap', jvmH, '%'); setBar('mJvmHeapBar', jvmH, 75, 85);
  document.getElementById('mJvmHeap').className = 'metric-value ' + colorClass(jvmH, 75, 85);

  setM('mSearchLat', sLat, 'ms');
  document.getElementById('mSearchLat').className = 'metric-value ' + colorClass(sLat, 300, 500);
  setM('mIndexLat', iLat, 'ms');
  document.getElementById('mIndexLat').className = 'metric-value ' + colorClass(iLat, 150, 200);
  setM('mSearchQps', m.search_rate||0);
  setM('mIndexTps', m.indexing_rate||0);
  setM('mTpSearchQ', m.tp_search_queue||0);
  setM('mTpWriteQ', m.tp_write_queue||0);
  setM('mPending', m.pending_tasks||0);
  const st = data.state || {};
  setM('mNodes', st.current_nodes||0);

  // AI Decision
  const dec = d.decision || 'hold';
  document.getElementById('aiDecision').textContent = dec;
  document.getElementById('aiDelta').textContent = d.delta || 0;
  const cdSec = st.cooldown_remaining_seconds || 0;
  document.getElementById('aiCooldown').textContent = cdSec > 0 ? cdSec + 's' : 'none';
  const box = document.getElementById('decisionBox');
  box.className = 'decision-box ' + dec;
  document.getElementById('decisionLabel').textContent = dec.toUpperCase();
  document.getElementById('decisionReason').textContent = d.reason || '';

  // Charts
  const ts = formatTime(m.timestamp);
  if (labels.length === 0 || labels[labels.length-1] !== ts) {
    labels.push(ts);
    if (labels.length > MAX_PTS) labels.shift();

    pushData(cpuAvgData, cpu); pushData(cpuMaxData, cpuMax); pushData(loadData, m.load_avg_max||0);
    pushData(diskUsageData, disk); pushData(diskIoData, m.disk_io_util_max||0);
    pushData(jvmHeapMaxData, jvmH); pushData(jvmHeapAvgData, m.jvm_heap_avg||0); pushData(gcOldData, m.jvm_old_gc_time_avg||0);
    pushData(searchRateData, m.search_rate||0); pushData(indexRateData, m.indexing_rate||0);
    pushData(searchLatData, sLat); pushData(indexLatData, iLat);
    pushData(tpSearchQData, m.tp_search_queue||0); pushData(tpWriteQData, m.tp_write_queue||0);
    pushData(tpFmQData, m.tp_force_merge_queue||0); pushData(tpRefreshQData, m.tp_refresh_queue||0);
    pushData(tpGenericQData, m.tp_generic_queue||0); pushData(tpMgmtQData, m.tp_management_queue||0);
    pushData(pendingData, m.pending_tasks||0);

    chartCpu.update(); chartDisk.update(); chartJvm.update(); chartQps.update(); chartTp.update();
  }

  // History
  const history = data.history || [];
  const tbody = document.getElementById('logBody');
  tbody.innerHTML = '';
  for (let i = history.length - 1; i >= Math.max(0, history.length - 20); i--) {
    const r = history[i];
    const tr = document.createElement('tr');
    const hIcon = r.cluster_healthy ? '✓' : '✗';
    tr.innerHTML = '<td>' + formatTime(r.timestamp) + '</td>' +
      '<td>' + fmt(r.cpu_avg) + '</td>' +
      '<td>' + fmt(r.disk_usage_pct) + '</td>' +
      '<td>' + fmt(r.jvm_heap_max) + '</td>' +
      '<td>' + (r.current_nodes||'--') + '</td>' +
      '<td>' + hIcon + '</td>' +
      '<td class="' + (r.decision||'') + '">' + (r.decision||'--') + '</td>' +
      '<td class="' + (r.action||'') + '">' + (r.action||'--') + ' ' + (r.action_status||'') + '</td>' +
      '<td>' + (r.reason||'') + '</td>';
    tbody.appendChild(tr);
  }
}

function updateConfig(data) {
  const grid = document.getElementById('configGrid');
  grid.innerHTML = '';
  for (const [k, v] of Object.entries(data)) {
    grid.innerHTML += '<div class="config-item"><span class="config-key">' + k + '</span><span class="config-val">' + v + '</span></div>';
  }
}

async function executeFix() {
  try {
    const resp = await fetch('/api/fix/execute', { method: 'POST' });
    const data = await resp.json();
    alert('Fix result: ' + JSON.stringify(data));
  } catch(e) { alert('Fix failed: ' + e); }
}

async function poll() {
  try {
    const resp = await fetch('/api/status');
    const data = await resp.json();
    updateDashboard(data);
  } catch(e) {
    document.getElementById('statusDot').className = 'dot red';
    document.getElementById('statusText').textContent = 'Error';
  }
  try {
    const resp = await fetch('/api/config');
    const data = await resp.json();
    updateConfig(data);
  } catch(e) {}
}

initCharts();
setInterval(poll, 3000);
poll();
</script>
</body>
</html>"""


def create_app(settings: Settings, eng: ElasticityEngine):
    global engine, _settings
    engine = eng
    _settings = settings

    @app.route("/")
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/status")
    def api_status():
        now = datetime.now(timezone.utc)
        cd_remaining = 0
        if engine.cooldown_until and now < engine.cooldown_until:
            cd_remaining = int((engine.cooldown_until - now).total_seconds())

        health = engine.latest_health or {}
        diagnosis = engine.latest_diagnosis or {}

        return jsonify({
            "metrics": engine.latest_metrics,
            "decision": engine.latest_decision,
            "action_result": engine.latest_action_result,
            "health": health,
            "diagnosis": diagnosis,
            "state": {
                "current_nodes": engine.current_nodes,
                "last_action": engine.last_action,
                "last_action_time": engine.last_action_time.isoformat() if engine.last_action_time else None,
                "cooldown_remaining_seconds": cd_remaining,
                "scale_in_allowed": engine._can_scale_in(),
            },
            "history": engine.history[-60:],
        })

    @app.route("/api/config")
    def api_config():
        s = _settings
        return jsonify({
            "cluster_id": s.cluster_id,
            "cluster_name": s.cluster_name,
            "min_nodes": s.min_nodes,
            "max_nodes": s.max_nodes,
            "scale_out_step": s.scale_out_step,
            "scale_in_step": s.scale_in_step,
            "cpu_spike_threshold": s.cpu_spike_threshold,
            "disk_spike_threshold": s.disk_spike_threshold,
            "jvm_heap_spike_threshold": s.jvm_heap_spike_threshold,
            "search_latency_spike_threshold": s.search_latency_spike_threshold,
            "indexing_latency_spike_threshold": s.indexing_latency_spike_threshold,
            "thread_pool_queue_spike_threshold": s.thread_pool_queue_spike_threshold,
            "scale_out_cooldown_min": s.scale_out_cooldown_minutes,
            "scale_in_cooldown_min": s.scale_in_cooldown_minutes,
            "scale_in_delay_after_scale_out_min": s.scale_in_delay_after_scale_out_minutes,
            "check_interval_seconds": s.check_interval_seconds,
            "css_mutation_enabled": s.css_mutation_enabled,
            "ai_diagnose_enabled": s.ai_diagnose_enabled,
            "ai_auto_fix_enabled": s.ai_auto_fix_enabled,
        })

    @app.route("/api/diagnose", methods=["POST"])
    def api_diagnose():
        try:
            result = engine.trigger_diagnosis()
            return jsonify({"status": "ok", "diagnosis": result})
        except Exception as exc:
            logger.error("api_diagnose_failed: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.route("/api/fix/execute", methods=["POST"])
    def api_fix_execute():
        diagnosis = engine.latest_diagnosis or {}
        if not diagnosis.get("auto_fix_available"):
            return jsonify({"status": "skipped", "message": "No auto-fix available"})
        if not _settings.ai_auto_fix_enabled:
            return jsonify({"status": "skipped", "message": "AI_AUTO_FIX_ENABLED=false"})
        return jsonify({"status": "info", "message": "Auto-fix execution not yet implemented for this action: " + diagnosis.get("auto_fix_action", "")})

    return app


def start_background_loop(eng: ElasticityEngine, settings: Settings):
    """Run the elasticity check loop in a background thread."""
    def loop():
        import time
        while True:
            try:
                eng.run_once()
            except Exception as exc:
                logger.error("engine_loop_error: %s", exc)
            time.sleep(settings.check_interval_seconds)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
