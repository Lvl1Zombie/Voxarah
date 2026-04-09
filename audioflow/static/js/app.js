/* ============================================================
   Voxarah Web — Frontend App
   Vanilla JS, no framework. All state lives server-side.
   ============================================================ */

'use strict';

// ── Tauri compat ──────────────────────────────────────────────────────────────
// IN_TAURI is true when loaded inside the Tauri webview (tauri:// protocol).
// API_BASE / WS_HOST are set in boot() after VOXARAH_PORT is injected by Rust.
var IN_TAURI   = typeof window.__TAURI_INTERNALS__ !== 'undefined';
var FIXED_PORT = 47891;
var API_BASE   = IN_TAURI ? `http://localhost:${FIXED_PORT}` : '';
var WS_HOST    = IN_TAURI ? `localhost:${FIXED_PORT}` : location.host;

// ── State ─────────────────────────────────────────────────────────────────────
var S = {
  results:       null,
  waveformPeaks: [],
  flags:         [],
  duration:      0,
  playingAudio:  null,
  playInterval:  null,
  filename:      '',
  settings:      {},
  compareSlots:  [{}, {}, {}],
};

// ── WebSocket ─────────────────────────────────────────────────────────────────
var ws = null;
var wsRetry = 0;

function wsConnect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${WS_HOST}/ws`);

  ws.onopen = () => {
    wsRetry = 0;
    // keep-alive ping every 20 s
    ws._ping = setInterval(() => ws.readyState === 1 && ws.send('ping'), 20000);
  };

  ws.onmessage = e => {
    try { handleWS(JSON.parse(e.data)); } catch (_) {}
  };

  ws.onclose = () => {
    clearInterval(ws._ping);
    const delay = Math.min(1000 * 2 ** wsRetry, 16000);
    wsRetry++;
    setTimeout(wsConnect, delay);
  };
}

function handleWS(msg) {
  switch (msg.type) {

    case 'status':
      S.ai_online = !!msg.ai_online;
      setChip('chip-ai', msg.ai_online ? 'online' : 'offline',
              msg.ai_online ? 'AI LIVE' : 'AI OFFLINE');
      setChip('chip-ffmpeg', msg.ffmpeg_ok ? 'online' : 'offline',
              msg.ffmpeg_ok ? 'FFMPEG' : 'NO FFMPEG');
      if (msg.version) el('lbl-version').textContent = 'v' + msg.version;
      // Update status bar
      setSbStatus('sb-ai',     msg.ai_online,  msg.ai_online  ? 'AI LIVE'   : 'AI OFFLINE');
      setSbStatus('sb-ffmpeg', msg.ffmpeg_ok,  msg.ffmpeg_ok  ? 'FFMPEG'    : 'NO FFMPEG');
      if (msg.version) { const v = el('sb-version'); if (v) v.textContent = 'v' + msg.version; }
      break;

    case 'progress':
      showProgress(msg.fraction, msg.msg);
      break;

    case 'analysis_done':
      onAnalysisDone(msg.results);
      break;

    case 'analyzing':
      if (!msg.active) hideProgress();
      break;

    case 'error':
      toast(msg.msg, 'error');
      hideProgress();
      break;

    case 'ai_token':
      appendAI(msg.token);
      if (_charAiListening && _charAiOutput) {
        _charAiOutput.textContent += msg.token;
        _charAiOutput.scrollTop = _charAiOutput.scrollHeight;
      }
      break;

    case 'ai_done':
      if (_charAiListening) {
        _charAiListening = false;
        if (_charAiBtn)    { _charAiBtn.disabled = false; }
        if (_charAiCancel) { _charAiCancel.style.display = 'none'; }
      }
      el('btn-ai-coach').disabled = false;
      // Store initial AI response in chat history and show chat
      if (el('ai-output') && el('ai-output').textContent.trim()) {
        _chatHistory = [
          { role: 'assistant', content: el('ai-output').textContent.trim() }
        ];
        el('ai-chat-wrap').style.display = '';
        el('ai-chat-log').innerHTML = '';
      }
      break;

    case 'ai_chat_token':
      if (_chatCurrentBubble) {
        _chatCurrentBubble.textContent += msg.token;
        el('ai-chat-log').scrollTop = el('ai-chat-log').scrollHeight;
      }
      break;

    case 'ai_chat_done':
      if (_chatCurrentBubble) {
        _chatHistory.push({ role: 'assistant', content: _chatCurrentBubble.textContent });
        _chatCurrentBubble = null;
      }
      el('ai-chat-send').disabled = false;
      el('ai-chat-input').disabled = false;
      el('ai-chat-input').focus();
      break;

    case 'rec_timer':
      updateRecTimer(msg.seconds);
      break;

    case 'compare_progress':
      updateCompareStatus(msg.slot, msg.msg, 'yellow');
      break;

    case 'compare_done':
      onCompareDone(msg.slot, msg.report, msg.stats, msg.pitch_rating);
      break;

    case 'compare_error':
      updateCompareStatus(msg.slot, 'Error: ' + msg.msg, 'red');
      break;
  }
}

// ── DOM helpers ───────────────────────────────────────────────────────────────
// Use var so these are on window and accessible from inline onclick= attributes.
var el  = id => document.getElementById(id);
var qs  = (s, root=document) => root.querySelector(s);
var qsa = (s, root=document) => [...root.querySelectorAll(s)];

function setChip(id, state, label) {
  const chip = el(id);
  if (!chip) return;
  chip.className = 'status-chip' + (state ? ' ' + state : '');
  const span = chip.querySelector('span');
  if (span && label) span.textContent = label;
}

function setSbStatus(id, online, label) {
  const item = el(id);
  if (!item) return;
  item.className = 'sb-item ' + (online ? 'sb-ok' : '');
  const lbl = el(id + '-lbl');
  if (lbl && label) lbl.textContent = label;
}

function rangeUpdate(input, labelId, fmt) {
  el(labelId).textContent = fmt(+input.value);
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type='info', duration=4000) {
  const t = document.createElement('div');
  const cssType = type === 'error' ? 'toast-error' : type === 'success' ? 'toast-success' : '';
  t.className = `toast${cssType ? ' ' + cssType : ''}`;
  t.innerHTML = `<div class="toast-dot"></div><span>${msg}</span>`;
  el('toast-container').appendChild(t);
  setTimeout(() => {
    t.classList.add('hiding');
    setTimeout(() => t.remove(), 300);
  }, duration);
}

// ── Tab navigation ─────────────────────────────────────────────────────────────
function initTabs() {
  qsa('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
  qsa('.subtab-item').forEach(btn => {
    btn.addEventListener('click', () => switchSubtab(btn.dataset.subtab));
  });
}

function switchTab(key) {
  qsa('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.tab === key));
  qsa('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + key));
  if (key === 'history') loadHistory();
  if (key === 'compare') initCompare();
  if (key === 'coaching') initCoachingProfiles();
}

function switchSubtab(key) {
  qsa('.subtab-item').forEach(b => b.classList.toggle('active', b.dataset.subtab === key));
  qsa('.subtab-panel').forEach(p => p.classList.toggle('active', p.id === 'subtab-' + key));
  if (key === 'coaching-characters') loadCharacters();
}

// ── Settings load / save ───────────────────────────────────────────────────────
async function loadSettings() {
  const data = await apiFetch('/api/settings');
  if (!data) return;
  S.settings = data;

  // Sync sliders + toggles
  syncRange('sl-max-pause',  data.max_pause_duration,   'lbl-max-pause',  v=>v.toFixed(1)+'s');
  syncRange('sl-silence',    data.silence_threshold_db, 'lbl-silence',    v=>v.toFixed(0)+' dB');
  syncRange('sl-stutter',    data.stutter_window,       'lbl-stutter',    v=>v.toFixed(1)+'s');
  syncRange('set-silence-db', data.silence_threshold_db, 'set-silence-db-lbl', v=>v.toFixed(0)+' dB');
  syncRange('set-min-sil',   data.min_silence_duration, 'set-min-sil-lbl', v=>v.toFixed(2)+'s');
  syncRange('set-max-pause', data.max_pause_duration,   'set-max-pause-lbl', v=>v.toFixed(1)+'s');
  syncRange('set-stutter-w', data.stutter_window,       'set-stutter-w-lbl', v=>v.toFixed(1)+'s');

  syncToggle('tog-stutters',   data.detect_stutters);
  syncToggle('tog-unclear',    data.detect_unclear);
  syncToggle('tog-breaths',    data.detect_breaths);
  syncToggle('tog-mouth',      data.detect_mouth_noises);
  syncToggle('set-tog-stutters', data.detect_stutters);
  syncToggle('set-tog-unclear',  data.detect_unclear);
  syncToggle('set-tog-breaths',  data.detect_breaths);
  syncToggle('set-tog-mouth',    data.detect_mouth_noises);
  syncToggle('set-tog-tips',     data.show_coaching_tips);
  syncToggle('set-tog-auto',     data.auto_analyze_on_load);
}

function syncRange(id, val, labelId, fmt) {
  const inp = el(id);
  if (!inp || val == null) return;
  inp.value = val;
  if (labelId) el(labelId).textContent = fmt(+val);
}
function syncToggle(id, val) {
  const inp = el(id);
  if (inp) inp.checked = !!val;
}

async function saveSetting(key, value) {
  S.settings[key] = value;
  await apiFetch('/api/settings', 'POST', { [key]: value });
}

async function saveAllSettings() {
  const d = {
    silence_threshold_db:  +el('set-silence-db').value,
    min_silence_duration:  +el('set-min-sil').value,
    max_pause_duration:    +el('set-max-pause').value,
    stutter_window:        +el('set-stutter-w').value,
    detect_stutters:       el('set-tog-stutters').checked,
    detect_unclear:        el('set-tog-unclear').checked,
    detect_breaths:        el('set-tog-breaths').checked,
    detect_mouth_noises:   el('set-tog-mouth').checked,
    show_coaching_tips:    el('set-tog-tips').checked,
    auto_analyze_on_load:  el('set-tog-auto').checked,
    coaching_profile:      el('set-profile').value,
  };
  await apiFetch('/api/settings', 'POST', d);
  S.settings = { ...S.settings, ...d };
  // Sync editor sliders
  syncRange('sl-max-pause', d.max_pause_duration, 'lbl-max-pause', v=>v.toFixed(1)+'s');
  syncRange('sl-silence',   d.silence_threshold_db, 'lbl-silence',  v=>v.toFixed(0)+' dB');
  syncRange('sl-stutter',   d.stutter_window,      'lbl-stutter',  v=>v.toFixed(1)+'s');
  toast('Settings saved', 'success');
}

async function resetSettings() {
  if (!confirm('Reset all settings to defaults?')) return;
  const data = await apiFetch('/api/settings/reset', 'POST', {});
  S.settings = data;
  await loadSettings();
  toast('Settings reset', 'info');
}

// ── File upload / drop ────────────────────────────────────────────────────────
function initFileUpload() {
  const zone  = el('drop-zone');
  const input = el('file-input');

  input.addEventListener('change', () => {
    if (input.files[0]) uploadFile(input.files[0]);
  });

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
  });
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  toast(`Loading ${file.name}…`);
  try {
    const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');
    S.filename = data.filename;
    showFileLoaded(data.filename, data.size_mb);
    el('btn-analyze').disabled = false;
    toast(`${file.name} ready`, 'success');
    if (S.settings.auto_analyze_on_load) runAnalysis();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function showFileLoaded(name, sizeMb) {
  el('drop-zone').style.display = 'none';
  const fl = el('file-loaded');
  fl.style.display = 'flex';
  el('file-loaded-name').textContent = name;
  el('file-loaded-meta').textContent = `${sizeMb} MB`;
}

// ── Analysis ───────────────────────────────────────────────────────────────────
async function runAnalysis() {
  toast('Starting analysis…', 'info');
  const res = await apiFetch('/api/analyze', 'POST', {});
  if (!res) return;
  el('btn-analyze').disabled = true;
  el('progress-wrap').style.display = 'block';
  showProgress(0, 'Starting…');
}

function showProgress(fraction, msg) {
  el('progress-wrap').style.display = 'block';
  el('progress-msg').textContent  = msg || '';
  el('progress-pct').textContent  = Math.round(fraction * 100) + '%';
  el('progress-fill').style.width = (fraction * 100) + '%';
}
function hideProgress() {
  el('progress-fill').style.width = '100%';
  setTimeout(() => {
    el('progress-wrap').style.display = 'none';
    el('progress-fill').style.width   = '0%';
    el('btn-analyze').disabled = false;
  }, 800);
}

function onAnalysisDone(results) {
  S.results       = results;
  S.waveformPeaks = results.waveform_peaks || [];
  S.flags         = results.flags || [];
  S.duration      = results.duration || 1;

  // Stats
  const st = results.stats || {};
  el('stat-pause-count').textContent   = st.pause_count ?? '—';
  el('stat-stutter-count').textContent = st.stutter_count ?? '—';
  el('stat-unclear-count').textContent = st.unclear_count ?? '—';
  el('stat-breath-count').textContent  = st.breath_count ?? '—';
  el('stat-mouth-count').textContent   = st.mouth_noise_count ?? '—';
  const ts = st.time_saved ?? null;
  el('stat-time-saved').textContent    = ts != null ? ts.toFixed(1) + 's' : '—';

  // Color zero-counts green
  ['stat-stutter-count','stat-unclear-count','stat-breath-count','stat-mouth-count'].forEach(id => {
    el(id).style.color = el(id).textContent === '0' ? 'var(--green)' : '';
  });

  // Pitch badge
  const ps = results.pitch_stats || {};
  const ratingColors = { EXPRESSIVE: 'var(--green)', MODERATE: 'var(--yellow)', FLAT: 'var(--red)' };
  const badge = el('pitch-badge');
  badge.textContent = ps.rating ? `${ps.rating}  ±${Math.round(ps.std_hz||0)} Hz` : '';
  badge.style.color = ratingColors[ps.rating] || 'var(--text-3)';

  // Canvases
  drawWaveform();
  drawPitch(results.pitch_frames || [], ps, results.duration);

  // Issues table
  renderIssues(results.issues || []);
  el('issues-count').textContent = (results.issues || []).length;

  // Enable controls
  el('btn-play-orig').disabled  = false;
  el('btn-play-clean').disabled = false;
  el('btn-export-wav').disabled = false;
  el('btn-export-labels').disabled = false;
  el('btn-ai-coach').disabled   = false;

  // Auto-score coaching
  scoreRecording();
  toast('Analysis complete', 'success');

  // Reset source file panel so user can upload another file
  resetSourceFile();
}

function resetSourceFile() {
  el('drop-zone').style.display   = '';
  el('file-loaded').style.display = 'none';
  el('file-loaded-name').textContent = '';
  el('file-loaded-meta').textContent = '';
  el('btn-analyze').disabled = true;
  // Reset file input so the same file can be re-selected
  el('file-input').value = '';
  S.filename = '';
}

// ── Waveform canvas ────────────────────────────────────────────────────────────
function drawWaveform() {
  const cv = el('waveform-canvas');
  const ctx = cv.getContext('2d');
  const W = cv.parentElement.clientWidth;
  const H = 84;
  cv.width  = W;
  cv.height = H;

  ctx.fillStyle = '#1f1f2e';
  ctx.fillRect(0, 0, W, H);

  const mid = H / 2;
  const peaks = S.waveformPeaks;
  const flags = S.flags;

  // Region tints
  const tints = {
    pause:      'rgba(245,197,24,0.08)',
    stutter:    'rgba(247,106,138,0.10)',
    unclear:    'rgba(155,107,255,0.10)',
    breath:     'rgba(74,184,216,0.08)',
    mouth_noise:'rgba(245,166,35,0.08)',
  };
  const barColors = {
    pause:      '#F5C518',
    stutter:    '#f76a8a',
    unclear:    '#9b6bff',
    breath:     '#4ab8d8',
    mouth_noise:'#f5a623',
  };

  // Total samples count (approximated from peaks * step)
  const totalSamples = peaks.length > 0
    ? peaks.length * Math.max(1, Math.round((S.duration * 44100) / peaks.length))
    : 44100;

  flags.forEach(f => {
    const x1 = (f.start_sample / totalSamples) * W;
    const x2 = (f.end_sample   / totalSamples) * W;
    ctx.fillStyle = tints[f.type] || 'rgba(255,255,255,0.04)';
    ctx.fillRect(x1, 0, x2 - x1, H);
  });

  // Build flag pixel map
  const flagPx = {};
  flags.forEach(f => {
    const x1 = Math.floor((f.start_sample / totalSamples) * W);
    const x2 = Math.ceil( (f.end_sample   / totalSamples) * W);
    for (let x = x1; x < x2; x++) flagPx[x] = barColors[f.type] || '#7c5cff';
  });

  // Baseline
  ctx.strokeStyle = '#2a2a3a';
  ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(W, mid); ctx.stroke();

  // Bars
  const amp = (H - 16) / 2;
  if (peaks.length > 0) {
    const step = W / peaks.length;
    for (let i = 0; i < peaks.length; i++) {
      const x   = Math.floor(i * step);
      const bh  = Math.max(2, peaks[i] * amp);
      ctx.strokeStyle = flagPx[x] || (i < peaks.length * 0.33 ? '#2a2a3a' : '#353548');
      ctx.beginPath();
      ctx.moveTo(x, mid - bh);
      ctx.lineTo(x, mid + bh);
      ctx.stroke();
    }
  } else {
    ctx.strokeStyle = '#2a2a3a';
    for (let x = 0; x < W; x += 3) {
      ctx.beginPath(); ctx.moveTo(x, mid - 2); ctx.lineTo(x, mid + 2); ctx.stroke();
    }
  }
}

// ── Pitch canvas ───────────────────────────────────────────────────────────────
function drawPitch(frames, stats, duration) {
  const cv  = el('pitch-canvas');
  const ctx = cv.getContext('2d');
  const W   = cv.parentElement.clientWidth;
  const H   = 80;
  cv.width  = W;
  cv.height = H;

  ctx.fillStyle = '#1f1f2e';
  ctx.fillRect(0, 0, W, H);

  const F_MIN = 70, F_MAX = 500;
  const mt = 18, mb = 8;

  const hz2y = hz => {
    hz = Math.max(F_MIN, Math.min(F_MAX, hz));
    return mt + (1 - (hz - F_MIN) / (F_MAX - F_MIN)) * (H - mt - mb);
  };

  // Grid lines
  [100, 200, 300].forEach(hz => {
    const y = hz2y(hz);
    ctx.strokeStyle = '#2a2a3a';
    ctx.setLineDash([2, 4]);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle   = '#333350';
    ctx.font        = '9px JetBrains Mono, Consolas, monospace';
    ctx.textAlign   = 'right';
    ctx.fillText(hz + ' Hz', W - 4, y - 2);
  });

  const voiced = (frames || []).filter(f => f.voiced && f.freq > 0);
  const frameScores = stats.frame_scores || [];

  if (voiced.length < 2) {
    ctx.fillStyle = '#3a3a50';
    ctx.font      = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Analyze a recording to see pitch', W / 2, H / 2);
    return;
  }

  const scoreColor = s => {
    if (s >= 0.7)  return '#4caf50';
    if (s >= 0.35) return '#F5C518';
    return '#f76a8a';
  };

  let prevX = null, prevY = null;
  voiced.forEach((f, i) => {
    const x = (f.time / duration) * W;
    const y = hz2y(f.freq);
    const s = frameScores[i] ?? 0.5;
    if (prevX !== null) {
      ctx.strokeStyle = scoreColor(s);
      ctx.lineWidth   = 2;
      ctx.beginPath(); ctx.moveTo(prevX, prevY); ctx.lineTo(x, y); ctx.stroke();
    }
    prevX = x; prevY = y;
  });
}

function resizeCanvases() {
  if (S.waveformPeaks.length) drawWaveform();
  if (S.results?.pitch_frames) {
    drawPitch(S.results.pitch_frames, S.results.pitch_stats || {}, S.results.duration);
  }
}
window.addEventListener('resize', resizeCanvases);

// ── Issues table ───────────────────────────────────────────────────────────────
function renderIssues(issues) {
  const tbody = el('issues-body');
  if (!issues.length) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><div class="empty-state-icon">✅</div>No issues found</div></td></tr>`;
    return;
  }
  tbody.innerHTML = issues.map(r => {
    const sevClass = r.severity >= 3 ? 'severity-high' : r.severity >= 2 ? 'severity-medium' : 'severity-low';
    const sevLabel = r.severity >= 3 ? 'HIGH' : r.severity >= 2 ? 'MED' : 'LOW';
    return `<tr>
      <td><span class="issue-type">${r.type.replace('_',' ')}</span></td>
      <td class="text-mono text-muted text-xs">${r.time}</td>
      <td class="text-sm text-dim">${r.desc}</td>
      <td><span class="severity ${sevClass}">${sevLabel}</span></td>
    </tr>`;
  }).join('');
}

// ── Playback ───────────────────────────────────────────────────────────────────
function playOriginal() { playAudio('/api/audio/original'); }
async function playCleaned() {
  toast('Preparing cleaned audio…');
  playAudio('/api/audio/cleaned');
}

async function playAudio(url) {
  stopAudio();
  try {
    const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
    const resp = await fetch(fullUrl);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);
    const audio = new Audio(blobUrl);
    S.playingAudio = audio;
    S._blobUrl = blobUrl;
    el('btn-stop').disabled = false;

    // 60fps playhead via requestAnimationFrame
    let rafId = null;
    function rafTick() {
      if (!S.playingAudio || audio.paused || audio.ended) return;
      const frac = audio.currentTime / (audio.duration || 1);
      el('timeline-fill').style.width = (frac * 100) + '%';
      el('playback-time').textContent = fmtTime(audio.currentTime) + ' / ' + fmtTime(audio.duration || 0);
      drawPlayhead(frac);
      rafId = requestAnimationFrame(rafTick);
    }
    audio.addEventListener('play', () => { rafId = requestAnimationFrame(rafTick); });
    audio.addEventListener('ended', () => {
      cancelAnimationFrame(rafId);
      el('btn-stop').disabled = true;
      el('timeline-fill').style.width = '0%';
      el('playback-time').textContent = '—';
      drawPlayhead(0);
      S.playingAudio = null;
      URL.revokeObjectURL(blobUrl);
      S._blobUrl = null;
    });
    audio.play().catch(e => toast('Playback error: ' + e.message, 'error'));
    S._rafId = rafId;
  } catch(e) {
    toast('Playback error: ' + e.message, 'error');
  }
}

function stopAudio() {
  if (S._rafId) { cancelAnimationFrame(S._rafId); S._rafId = null; }
  if (S.playingAudio) {
    S.playingAudio.pause();
    S.playingAudio = null;
  }
  if (S._blobUrl) { URL.revokeObjectURL(S._blobUrl); S._blobUrl = null; }
  el('btn-stop').disabled = true;
  el('timeline-fill').style.width = '0%';
  el('playback-time').textContent = '—';
  drawPlayhead(0);
}

function seekAudio(e) {
  if (!S.playingAudio) return;
  const rect = el('timeline-track').getBoundingClientRect();
  const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  S.playingAudio.currentTime = frac * S.playingAudio.duration;
}

function drawPlayhead(frac) {
  ['waveform-canvas', 'pitch-canvas'].forEach(id => {
    const cv  = el(id);
    const ctx = cv.getContext('2d');
    // Re-draw full canvas, then overlay playhead
    if (id === 'waveform-canvas') drawWaveform();
    else if (S.results?.pitch_frames)
      drawPitch(S.results.pitch_frames, S.results.pitch_stats || {}, S.results.duration);
    const x = frac * cv.width;
    ctx.strokeStyle = '#F5C518';
    ctx.lineWidth   = 2;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, cv.height); ctx.stroke();
  });
}

function fmtTime(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1).padStart(4, '0');
  return `${m}:${s}`;
}

// ── Export ────────────────────────────────────────────────────────────────────
function exportWav() {
  window.location.href = `${API_BASE}/api/export/wav`;
}
function exportLabels() {
  window.location.href = `${API_BASE}/api/export/labels`;
}

// ── Recording ────────────────────────────────────────────────────────────────
async function startRec() {
  const res = await apiFetch('/api/record/start', 'POST', {});
  if (!res) return;
  el('btn-rec-start').style.display = 'none';
  el('btn-rec-stop').style.display  = 'inline-flex';
  el('rec-indicator').classList.add('active');
}

async function stopRec() {
  const res = await apiFetch('/api/record/stop', 'POST', {});
  if (!res) return;
  el('btn-rec-start').style.display = 'inline-flex';
  el('btn-rec-stop').style.display  = 'none';
  el('rec-indicator').classList.remove('active');
  showFileLoaded(res.filename, '—');
  el('btn-analyze').disabled = false;
  toast('Recording saved', 'success');
}

function updateRecTimer(sec) {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1).padStart(4, '0');
  el('rec-timer').textContent = `${m}:${s}`;
}

// ── Coaching ─────────────────────────────────────────────────────────────────
async function initCoachingProfiles() {
  if (el('coaching-profile').options.length > 1) return; // already loaded
  const profiles = await apiFetch('/api/profiles');
  if (!profiles) return;
  const defProfile = S.settings.coaching_profile || '';
  const selCoach   = el('coaching-profile');
  const selSet     = el('set-profile');
  const selCmp     = el('compare-profile');

  [selCoach, selSet, selCmp].forEach(sel => {
    if (!sel) return;
    sel.innerHTML = profiles.map(p =>
      `<option value="${p.name}" ${p.name===defProfile ? 'selected' : ''}>${p.emoji} ${p.name}</option>`
    ).join('');
  });

  selCoach.addEventListener('change', () => {
    const info = profiles.find(p => p.name === selCoach.value);
    el('profile-desc').textContent = info?.description || '';
    if (S.results) scoreRecording();
  });

  const info = profiles.find(p => p.name === defProfile);
  el('profile-desc').textContent = info?.description || '';
}

async function scoreRecording() {
  if (!S.results) return;
  const profile = el('coaching-profile')?.value || S.settings.coaching_profile;
  const data = await apiFetch('/api/coaching/score', 'POST', { profile });
  if (!data) return;

  const r = data.report;
  // Score hero
  const sc = r.overall;
  el('score-overall').textContent = sc;
  el('score-overall').style.color = scoreColor(sc);
  el('score-grade').textContent   = r.grade || '';

  // Dimension bars
  const dimLabels = {
    pause_ratio: 'Pacing', stutters: 'Delivery', pause_length: 'Pause Len',
    consistency: 'Consistency', clarity: 'Clarity', pitch: 'Pitch',
  };
  const dimBars = el('dim-bars');
  dimBars.innerHTML = Object.entries(r.scores || {}).map(([k, v]) => `
    <div class="dim-bar-row">
      <div class="dim-bar-label">${dimLabels[k] || k}</div>
      <div class="dim-bar-track">
        <div class="dim-bar-fill" id="dbf-${k}" style="width:${v}%;background:${scoreColor(v)}"></div>
      </div>
      <div class="dim-bar-val" style="color:${scoreColor(v)}">${v}</div>
    </div>`).join('');

  // Tips
  const tips = r.tips || [];
  const tipsEl = el('coaching-tips');
  if (tips.length) {
    tipsEl.innerHTML = tips.map(t =>
      `<div class="tip-card"><span class="tip-icon">›</span><span class="tip-text">${t}</span></div>`
    ).join('');
  } else {
    tipsEl.innerHTML = '<div class="text-muted text-sm">No tips available for this profile.</div>';
  }

  // Retake guide
  const retake = data.retake || {};
  el('retake-summary').textContent = retake.summary || 'Nothing to retake.';
  const regs = el('retake-regions');
  regs.innerHTML = (retake.suggestions || []).map(s => `
    <div class="retake-region">
      <div class="retake-time">${s.label}</div>
      <div class="retake-reason">${s.reason}</div>
    </div>`).join('');
}

function scoreColor(v) {
  if (v >= 80) return 'var(--green)';
  if (v >= 60) return 'var(--yellow)';
  return 'var(--red)';
}

var _chatHistory        = [];
var _chatCurrentBubble  = null;

async function getAICoaching() {
  el('ai-output').textContent = '';
  el('btn-ai-coach').disabled = true;
  // Reset chat
  _chatHistory = [];
  _chatCurrentBubble = null;
  el('ai-chat-wrap').style.display = 'none';
  el('ai-chat-log').innerHTML = '';
  const profile = el('coaching-profile')?.value || '';
  await apiFetch('/api/coaching/ai', 'POST', { profile });
}

function appendAI(token) {
  const box = el('ai-output');
  box.textContent += token;
  box.scrollTop = box.scrollHeight;
  el('btn-ai-coach').disabled = false;
}

async function sendChatMessage() {
  const input = el('ai-chat-input');
  const text  = input.value.trim();
  if (!text) return;

  // Add user message to UI
  appendChatBubble('user', text);
  input.value = '';
  el('ai-chat-send').disabled = true;
  input.disabled = true;

  // Add to history and send
  _chatHistory.push({ role: 'user', content: text });

  // Create empty AI bubble for streaming into
  _chatCurrentBubble = appendChatBubble('ai', '');

  await apiFetch('/api/coaching/ai/chat', 'POST', { messages: _chatHistory });
}

function appendChatBubble(role, text) {
  const log   = el('ai-chat-log');
  const wrap  = document.createElement('div');
  wrap.className = `ai-chat-msg ${role}`;

  const label  = document.createElement('div');
  label.className = 'ai-chat-label';
  label.textContent = role === 'user' ? 'You' : 'AI Coach';

  const bubble = document.createElement('div');
  bubble.className = 'ai-chat-bubble';
  bubble.textContent = text;

  wrap.appendChild(label);
  wrap.appendChild(bubble);
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
  return bubble;
}

async function cancelAI() {
  await apiFetch('/api/coaching/ai/cancel', 'POST', {});
  el('btn-ai-coach').disabled = false;
}

// ── Compare ───────────────────────────────────────────────────────────────────
function initCompare() {
  const grid = el('compare-grid');
  if (grid.children.length > 0) return; // already built
  initCoachingProfiles();
  grid.innerHTML = [0, 1, 2].map(i => buildCompareCol(i)).join('');
}

function buildCompareCol(i) {
  return `
  <div class="card compare-col" id="cmp-col-${i}">
    <div class="compare-col-header">
      <span class="compare-col-title">TAKE ${i + 1}</span>
      <div class="grow"></div>
      <button class="btn btn-ghost btn-sm" style="padding:4px 8px;font-size:11px" title="Clear" onclick="clearTake(${i})">✕</button>
    </div>
    <label style="display:block;margin-bottom:var(--sp-2)">
      <input type="file" style="display:none" id="cmp-input-${i}"
             onchange="uploadTake(${i},this.files[0])" accept=".wav,.mp3,.m4a,.flac,.ogg">
      <button class="btn btn-ghost btn-sm btn-full"
              onclick="el('cmp-input-${i}').click()">Load File</button>
    </label>
    <div class="text-xs text-mono text-muted" id="cmp-fname-${i}" style="margin-bottom:var(--sp-1)"></div>
    <div class="text-xs text-muted" id="cmp-status-${i}" style="margin-bottom:var(--sp-3)"></div>
    <div class="compare-score-big" id="cmp-score-${i}">—</div>
    <div class="text-muted text-sm" id="cmp-grade-${i}" style="margin-bottom:var(--sp-3)"></div>
    <button class="btn btn-yellow btn-sm btn-full" id="cmp-analyze-btn-${i}"
            onclick="analyzeTake(${i})" disabled style="margin-bottom:var(--sp-4)">Analyze</button>
    <div id="cmp-dims-${i}"></div>
    <div id="cmp-stats-${i}" style="margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border)"></div>
  </div>`;
}

async function uploadTake(slot, file) {
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  toast(`Loading take ${slot+1}…`);
  try {
    const res = await fetch(`${API_BASE}/api/compare/upload/${slot}`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error((await res.json()).detail);
    el(`cmp-fname-${slot}`).textContent = file.name;
    el(`cmp-status-${slot}`).textContent = 'Ready';
    el(`cmp-analyze-btn-${slot}`).disabled = false;
    S.compareSlots[slot] = { filename: file.name };
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function analyzeTake(slot) {
  const profile = el('compare-profile')?.value || '';
  updateCompareStatus(slot, 'Analyzing…', 'yellow');
  el(`cmp-analyze-btn-${slot}`).disabled = true;
  await apiFetch(`/api/compare/analyze/${slot}?profile=${encodeURIComponent(profile)}`, 'POST', {});
}

function updateCompareStatus(slot, msg, color='muted') {
  const lbl = el(`cmp-status-${slot}`);
  if (lbl) {
    lbl.textContent = msg;
    lbl.style.color = color === 'yellow' ? 'var(--yellow)'
                    : color === 'red'    ? 'var(--red)'
                    : color === 'green'  ? 'var(--green)'
                    : 'var(--text-3)';
  }
}

function onCompareDone(slot, report, stats, pitchRating) {
  const sc = report.overall;
  el(`cmp-score-${slot}`).textContent = sc;
  el(`cmp-score-${slot}`).style.color = scoreColor(sc);
  el(`cmp-grade-${slot}`).textContent = report.grade || '';
  updateCompareStatus(slot, 'Done', 'green');
  el(`cmp-analyze-btn-${slot}`).disabled = false;

  // Dim bars
  const dimLabels = { pause_ratio:'Pacing', stutters:'Delivery', pause_length:'Pause',
                      consistency:'Consist.', clarity:'Clarity', pitch:'Pitch' };
  el(`cmp-dims-${slot}`).innerHTML = Object.entries(report.scores || {}).map(([k,v]) => `
    <div class="dim-bar-row" style="padding:3px 0">
      <div class="dim-bar-label" style="width:70px;font-size:10px">${dimLabels[k]||k}</div>
      <div class="dim-bar-track"><div class="dim-bar-fill" style="width:${v}%;background:${scoreColor(v)}"></div></div>
      <div class="dim-bar-val" style="color:${scoreColor(v)};font-size:10px">${v}</div>
    </div>`).join('');

  // Stats
  const stKeys = [['stutter_count','Stutters'],['breath_count','Breaths'],
                  ['mouth_noise_count','Mouth Noise'],['pause_count','Pauses']];
  el(`cmp-stats-${slot}`).innerHTML = `
    <div style="margin-top:10px">` +
    stKeys.map(([k,l]) => `
      <div class="flex justify-between text-xs" style="padding:3px 0">
        <span class="text-muted">${l}</span>
        <span class="text-mono bold" style="color:${(stats[k]||0)>0?'var(--yellow)':'var(--green)'}">
          ${stats[k] ?? '—'}
        </span>
      </div>`).join('') +
    `<div class="flex justify-between text-xs" style="padding:3px 0">
      <span class="text-muted">Pitch</span>
      <span class="text-mono bold">${pitchRating}</span>
    </div></div>`;

  S.compareSlots[slot].report = report;
  refreshComparisons();
}

function refreshComparisons() {
  const scored = S.compareSlots
    .map((s, i) => ({ i, r: s.report }))
    .filter(x => x.r);
  if (scored.length < 2) return;
  const best = scored.reduce((a,b) => b.r.overall > a.r.overall ? b : a);
  scored.forEach(({ i }) => el(`cmp-col-${i}`).classList.toggle('compare-best', i === best.i));
  const top = best.r;
  const topDims = Object.entries(top.scores || {})
    .sort((a,b)=>b[1]-a[1]).slice(0,2)
    .map(([k,v])=>`${k.replace('_',' ')} ${v}`).join(' · ');
  el('compare-banner').textContent =
    `● Take ${best.i+1} is your best — ${top.overall} overall   Strongest: ${topDims}`;
}

async function clearTake(slot) {
  await apiFetch(`/api/compare/${slot}`, 'DELETE');
  el(`cmp-fname-${slot}`).textContent   = '';
  el(`cmp-status-${slot}`).textContent  = '';
  el(`cmp-score-${slot}`).textContent   = '—';
  el(`cmp-score-${slot}`).style.color   = '';
  el(`cmp-grade-${slot}`).textContent   = '';
  el(`cmp-dims-${slot}`).innerHTML      = '';
  el(`cmp-stats-${slot}`).innerHTML     = '';
  el(`cmp-analyze-btn-${slot}`).disabled = true;
  el(`cmp-col-${slot}`).classList.remove('compare-best');
  S.compareSlots[slot] = {};
}

async function rescoreAll() {
  const profile = el('compare-profile')?.value || '';
  const results = await apiFetch('/api/compare/rescore', 'POST', { profile });
  if (!results) return;
  results.forEach(r => onCompareDone(r.slot, r.report, r.stats, r.pitch_rating));
}

// ── Characters ─────────────────────────────────────────────────────────────────
let _characters = null;
var _activeCharCat = 'All';

async function loadCharacters() {
  if (_characters) { renderCharacters(); return; }
  _characters = await apiFetch('/api/characters');
  if (!_characters) return;
  renderCharacters();
}

function renderCharacters() {
  const container = el('characters-grid');

  // Collect ordered unique categories
  const cats = ['All', ...new Set(Object.values(_characters).map(d => d.category))];

  // Category theme filter bar
  const filterBar = `<div class="char-filter-bar">${cats.map(c =>
    `<button class="char-filter-btn${c === _activeCharCat ? ' active' : ''}" data-cat="${c}">${c}</button>`
  ).join('')}</div>`;

  // Cards filtered by active category
  const entries = Object.entries(_characters).filter(([, d]) =>
    _activeCharCat === 'All' || d.category === _activeCharCat
  );

  const diffColor = { Beginner: 'var(--green)', Intermediate: 'var(--yellow)', Advanced: 'var(--red)' };
  const cards = `<div class="grid-auto">${entries.map(([name, data]) => {
    const emoji = name.split(' ')[0];
    const label = name.replace(/^\S+\s*/, '');
    const dc = diffColor[data.difficulty] || 'var(--text-3)';
    return `<div class="char-card" data-char="${encodeURIComponent(name)}">
      <span class="char-icon">${emoji}</span>
      <div class="char-name">${label}</div>
      <div class="char-cat">${data.category}</div>
      <div class="char-cat" style="margin-top:4px;color:${dc}">${data.difficulty}</div>
    </div>`;
  }).join('')}</div>`;

  container.innerHTML = filterBar + cards;

  // Wire filter buttons
  container.querySelectorAll('.char-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _activeCharCat = btn.dataset.cat;
      renderCharacters();
    });
  });

  // Wire card clicks
  container.querySelectorAll('.char-card').forEach(card => {
    card.addEventListener('click', () => showCharacter(card.dataset.char));
  });
}

function showCharacter(encodedName) {
  const name = decodeURIComponent(encodedName);
  const data = _characters[name];
  if (!data) return;

  const diffColor = { Beginner: 'var(--green)', Intermediate: 'var(--yellow)', Advanced: 'var(--red)' };
  const dc = diffColor[data.difficulty] || 'var(--text-3)';

  // Compute match scores from analysis results if available
  const hasResults = !!S.results;
  const stats = S.results?.stats || {};
  const pitchStats = S.results?.pitch_stats || {};

  // Simple heuristic scores based on archetype traits vs recorded stats
  function clamp(v) { return Math.max(0, Math.min(100, Math.round(v))); }

  var matchScores = null;
  if (hasResults) {
    // Pacing: compare wpm to archetype expectations
    const wpm = stats.wpm || 0;
    const pauseRatio = stats.pause_ratio ?? 0.2;
    const pitchStd = pitchStats.std_hz || 0;
    const stutters = stats.stutter_count || 0;
    const mouths = stats.mouth_noise_count || 0;

    // Archetype-tuned targets
    const archetypeTargets = {
      wpm: { slow: 90, medium: 140, fast: 180 },
    };

    // Delivery: fewer stutters/mouth noises = better
    const delivery = clamp(100 - (stutters * 10) - (mouths * 5));

    // Pacing score — penalty for being far from archetype ideal
    // Slow archetypes (Wizard, Dragon, AI etc.) want low wpm
    const slowTypes = ['Wizard','Elf','Dragon','Ancient','Sage'];
    const fastTypes = ['Hype','Energetic','Comedic','Trickster'];
    const idealWpm = slowTypes.some(t => name.includes(t)) ? 100 :
                     fastTypes.some(t => name.includes(t)) ? 175 : 140;
    const pacing = clamp(100 - Math.abs(wpm - idealWpm) / 1.2);

    // Expressiveness: higher pitch std = more expressive
    const expression = clamp((pitchStd / 60) * 100);

    // Pause control
    const pauseControl = clamp(100 - Math.abs(pauseRatio - 0.18) * 300);

    // Clarity: no unclear sections
    const clarity = clamp(100 - (stats.unclear_count || 0) * 15);

    const overall = clamp((delivery + pacing + expression + pauseControl + clarity) / 5);

    matchScores = { overall, delivery, pacing, expression, pauseControl, clarity };
  }

  const scoreHtml = matchScores ? `
    <div class="char-score-hero">
      <div class="score-number" style="color:${scoreColor(matchScores.overall)}">${matchScores.overall}</div>
      <div class="score-grade">${matchScores.overall >= 80 ? 'Strong Match' : matchScores.overall >= 60 ? 'Developing' : 'Needs Work'}</div>
    </div>
    <div style="margin-bottom:var(--sp-5)">
      ${[['Delivery','delivery'],['Pacing','pacing'],['Expression','expression'],['Pause Control','pauseControl'],['Clarity','clarity']].map(([label,key]) => `
      <div class="dim-bar-row">
        <div class="dim-bar-label">${label}</div>
        <div class="dim-bar-track"><div class="dim-bar-fill" style="width:${matchScores[key]}%;background:${scoreColor(matchScores[key])}"></div></div>
        <div class="dim-bar-val" style="color:${scoreColor(matchScores[key])}">${matchScores[key]}</div>
      </div>`).join('')}
    </div>` : `
    <div class="banner" style="margin-bottom:var(--sp-5)">Analyze a recording to see your match score for this archetype.</div>`;

  const container = el('characters-grid');
  container.innerHTML = `
    <div class="char-detail-panel">
      <button class="char-back-btn" id="char-back-btn">← Back to Characters</button>

      <div class="char-detail-grid">
        <!-- Left: identity + score -->
        <div class="flex-col gap-4">
          <div class="card">
            <div style="display:flex;align-items:center;gap:var(--sp-4);margin-bottom:var(--sp-4)">
              <span style="font-size:40px">${name.split(' ')[0]}</span>
              <div>
                <div style="font-family:var(--font-display);font-size:18px;font-weight:700;color:var(--text)">${name.replace(/^\S+\s*/,'')}</div>
                <div style="font-family:var(--font-mono);font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-3);margin-top:4px">${data.category}</div>
                <div style="font-family:var(--font-mono);font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:${dc};margin-top:2px">${data.difficulty}</div>
              </div>
            </div>
            <p class="text-sm text-muted">${data.description}</p>
          </div>

          <div class="card">
            <div class="card-title" style="margin-bottom:var(--sp-3)">Match Score</div>
            ${scoreHtml}
          </div>

          <div class="card">
            <div class="card-title" style="margin-bottom:var(--sp-3)">Known For</div>
            <div style="display:flex;flex-wrap:wrap;gap:var(--sp-2)">${(data.example_pros||[]).map(p=>`<span class="pill pill-muted">${p}</span>`).join('')}</div>
          </div>

          <div class="card">
            <div class="card-title" style="margin-bottom:var(--sp-3)">Common Mistakes</div>
            ${(data.common_mistakes||[]).map(m=>`<div class="tip-card"><span class="tip-icon" style="color:var(--red)">✗</span><span class="tip-text">${m}</span></div>`).join('')}
          </div>
        </div>

        <!-- Right: coaching info -->
        <div class="flex-col gap-4">
          <div class="card">
            <div class="card-title" style="margin-bottom:var(--sp-3)">Vocal Qualities</div>
            ${(data.vocal_qualities||[]).map(q=>`<div class="tip-card"><span class="tip-icon">›</span><span class="tip-text">${q}</span></div>`).join('')}
          </div>

          <div class="card">
            <div class="card-title" style="margin-bottom:var(--sp-3)">Pro Tips</div>
            ${(data.pro_tips||[]).map(t=>`<div class="tip-card"><span class="tip-icon">›</span><span class="tip-text">${t}</span></div>`).join('')}
          </div>

          <div class="card">
            <div class="card-header">
              <div class="card-title">AI Coaching</div>
              <div class="flex gap-2">
                <button class="btn btn-primary btn-sm" id="char-ai-btn" ${!matchScores ? 'disabled title="Analyze a recording first"' : ''}>
                  ✨ Get AI Coaching
                </button>
                <button class="btn btn-ghost btn-sm" id="char-ai-cancel" style="display:none">Cancel</button>
              </div>
            </div>
            ${!matchScores ? '<p class="text-sm text-muted">Analyze a recording first to get character-specific AI coaching.</p>' : ''}
            <div class="log-box" id="char-ai-output" data-placeholder="AI coaching for ${name.replace(/^\S+\s*/,'')} will appear here..."></div>
          </div>
        </div>
      </div>
    </div>`;

  el('char-back-btn').addEventListener('click', () => renderCharacters());

  if (matchScores) {
    el('char-ai-btn').addEventListener('click', () => getCharacterAICoaching(name, data, matchScores));
    el('char-ai-cancel').addEventListener('click', () => {
      apiFetch('/api/coaching/ai/cancel', 'POST', {});
      el('char-ai-cancel').style.display = 'none';
      el('char-ai-btn').disabled = false;
    });
  }
}

async function getCharacterAICoaching(charName, charData, matchScores) {
  const btn    = el('char-ai-btn');
  const cancel = el('char-ai-cancel');
  const output = el('char-ai-output');

  if (!S.ai_online) {
    output.textContent = 'AI is offline. Start Ollama and wait a moment for it to connect.';
    return;
  }

  btn.disabled = true;
  cancel.style.display = '';
  output.textContent = '';

  // Build scores payload in the format the backend expects
  const scores = {
    overall: matchScores.overall,
    grade:   matchScores.overall >= 90 ? 'S' : matchScores.overall >= 80 ? 'A' :
             matchScores.overall >= 70 ? 'B' : matchScores.overall >= 60 ? 'C' :
             matchScores.overall >= 50 ? 'D' : 'F',
    scores: {
      delivery:     matchScores.delivery,
      pacing:       matchScores.pacing,
      dynamic_range: matchScores.expression,
      pause_length: matchScores.pauseControl,
      clarity:      matchScores.clarity,
    }
  };

  const res = await apiFetch('/api/coaching/ai', 'POST', {
    profile:        charData.category || 'Character / Animation',
    scores,
    character_name: charName.replace(/^\S+\s*/, ''),
  });
  if (!res) {
    btn.disabled = false;
    cancel.style.display = 'none';
    return;
  }

  // Stream tokens via WebSocket (same mechanism as main coaching tab)
  // The backend streams via WS broadcast — listen for ai_token / ai_done
  _charAiListening = true;
  _charAiOutput    = output;
  _charAiBtn       = btn;
  _charAiCancel    = cancel;
}

var _charAiListening = false;
var _charAiOutput    = null;
var _charAiBtn       = null;
var _charAiCancel    = null;

function closeCharModal(e) {
  if (!e || e.target === el('char-modal')) el('char-modal').classList.add('hidden');
}

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  const records = await apiFetch('/api/history');
  const list    = el('history-list');
  if (!records || !records.length) {
    list.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📁</div>No history yet</div>`;
    el('history-chart-wrap').style.display = 'none';
    return;
  }

  // Chart uses chronological order (oldest first)
  const chrono = [...records].reverse();
  renderHistoryChart(chrono);

  // List shows newest first (records is already reversed from API)
  list.innerHTML = records.slice(0, 60).map(r => {
    const sc = r.overall ?? r.report?.overall ?? '—';
    return `<div class="history-row">
      <div class="history-score" style="color:${scoreColor(+sc)}">${sc}</div>
      <div class="history-meta">
        <div class="history-file">${r.filename || '—'}</div>
        <div class="history-details">${r.profile || ''} · ${r.date || r.timestamp || ''}</div>
      </div>
      <div class="history-grade">${r.grade || r.report?.grade || ''}</div>
    </div>`;
  }).join('');
}

function renderHistoryChart(records) {
  const wrap = el('history-chart-wrap');
  if (!records || records.length < 2) { wrap.style.display = 'none'; return; }
  wrap.style.display = '';

  const cv  = el('history-canvas');
  const PAD = { top: 16, right: 20, bottom: 28, left: 38 };

  function draw() {
    const W = cv.parentElement.clientWidth - PAD.left - PAD.right;
    const H = 160;
    cv.width  = cv.parentElement.clientWidth;
    cv.height = H + PAD.top + PAD.bottom;
    const ctx = cv.getContext('2d');
    ctx.clearRect(0, 0, cv.width, cv.height);

    const scores = records.map(r => +(r.overall ?? 0));
    const minS   = Math.max(0,   Math.min(...scores) - 10);
    const maxS   = Math.min(100, Math.max(...scores) + 10);

    // Map score → y pixel
    function gy(s) { return PAD.top + H - ((s - minS) / (maxS - minS)) * H; }
    // Map index → x pixel
    function gx(i) { return PAD.left + (i / (records.length - 1)) * W; }

    // Grid lines
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth   = 1;
    [25, 50, 75, 100].forEach(v => {
      if (v < minS || v > maxS) return;
      const y = gy(v);
      ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + W, y); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.textAlign = 'right';
      ctx.fillText(v, PAD.left - 6, y + 3);
    });
    ctx.restore();

    // Build point coords
    const pts = scores.map((s, i) => ({ x: gx(i), y: gy(s), s, r: records[i] }));

    // Filled area under curve
    const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + H);
    grad.addColorStop(0,   'rgba(245,197,24,0.22)');
    grad.addColorStop(1,   'rgba(245,197,24,0.01)');
    ctx.beginPath();
    ctx.moveTo(pts[0].x, PAD.top + H);
    ctx.lineTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) {
      const cp1x = (pts[i-1].x + pts[i].x) / 2;
      ctx.bezierCurveTo(cp1x, pts[i-1].y, cp1x, pts[i].y, pts[i].x, pts[i].y);
    }
    ctx.lineTo(pts[pts.length-1].x, PAD.top + H);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.save();
    ctx.strokeStyle = '#F5C518';
    ctx.lineWidth   = 2;
    ctx.lineJoin    = 'round';
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) {
      const cp1x = (pts[i-1].x + pts[i].x) / 2;
      ctx.bezierCurveTo(cp1x, pts[i-1].y, cp1x, pts[i].y, pts[i].x, pts[i].y);
    }
    ctx.stroke();
    ctx.restore();

    // Dots
    pts.forEach((p, i) => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, i === pts.length - 1 ? 5 : 3, 0, Math.PI * 2);
      ctx.fillStyle   = i === pts.length - 1 ? '#F5C518' : '#1c1c1c';
      ctx.strokeStyle = '#F5C518';
      ctx.lineWidth   = 2;
      ctx.fill();
      ctx.stroke();
    });

    // X-axis date labels (first, last, and evenly spaced if enough room)
    ctx.fillStyle = 'rgba(255,255,255,0.25)';
    ctx.font = '9px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    const labelIdxs = new Set([0, records.length - 1]);
    if (records.length > 4) {
      const mid = Math.floor(records.length / 2);
      labelIdxs.add(mid);
    }
    labelIdxs.forEach(i => {
      const label = (records[i].date || '').slice(0, 10);
      ctx.fillText(label, pts[i].x, PAD.top + H + 16);
    });

    // Store pts for hover
    cv._pts = pts;
  }

  draw();
  window.addEventListener('resize', draw);

  // Trend badge
  const scores = records.map(r => +(r.overall ?? 0));
  const first5avg = scores.slice(0, Math.min(5, scores.length)).reduce((a,b) => a+b,0) / Math.min(5, scores.length);
  const last5avg  = scores.slice(-Math.min(5, scores.length)).reduce((a,b) => a+b,0) / Math.min(5, scores.length);
  const diff = last5avg - first5avg;
  const badge = el('history-trend-badge');
  if (diff > 2) {
    badge.textContent = `↑ +${diff.toFixed(1)} pts improving`;
    badge.className = 'history-trend-badge';
  } else if (diff < -2) {
    badge.textContent = `↓ ${diff.toFixed(1)} pts declining`;
    badge.className = 'history-trend-badge down';
  } else {
    badge.textContent = '→ holding steady';
    badge.className = 'history-trend-badge flat';
  }

  // Hover tooltip
  const tooltip = el('history-chart-tooltip');
  cv.addEventListener('mousemove', e => {
    const pts = cv._pts;
    if (!pts) return;
    const rect = cv.getBoundingClientRect();
    const mx   = e.clientX - rect.left;
    // Find nearest point
    let nearest = null, minDist = Infinity;
    pts.forEach(p => {
      const d = Math.abs(p.x - mx);
      if (d < minDist) { minDist = d; nearest = p; }
    });
    if (!nearest || minDist > 60) { tooltip.classList.remove('visible'); return; }
    el('tip-score').textContent = nearest.s + (nearest.r.grade ? '  ' + nearest.r.grade : '');
    el('tip-score').style.color = scoreColor(nearest.s);
    el('tip-meta').textContent  = (nearest.r.date || '') + (nearest.r.filename ? ' · ' + nearest.r.filename : '');
    tooltip.style.left = nearest.x + 'px';
    tooltip.style.top  = nearest.y + 'px';
    tooltip.classList.add('visible');
  });
  cv.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
}

// ── Feedback ──────────────────────────────────────────────────────────────────
function openFeedback() {
  el('feedback-modal').classList.remove('hidden');
  el('feedback-text').focus();
}
function closeFeedback(e) {
  if (!e || e.target === el('feedback-modal')) el('feedback-modal').classList.add('hidden');
}
async function sendFeedback() {
  const msg = el('feedback-text').value.trim();
  if (!msg) { el('feedback-status').textContent = 'Please write something first.'; return; }
  el('btn-send-feedback').disabled = true;
  el('feedback-status').textContent = 'Sending…';
  const res = await apiFetch('/api/feedback', 'POST', { message: msg });
  if (res) {
    el('feedback-status').textContent = 'Sent! Thank you.';
    setTimeout(() => closeFeedback(), 1800);
  } else {
    el('feedback-status').textContent = 'Failed. Check your connection.';
    el('btn-send-feedback').disabled = false;
  }
}

// ── API helper ────────────────────────────────────────────────────────────────
async function apiFetch(url, method='GET', body=null) {
  try {
    const opts = { method, headers: {} };
    if (body !== null) {
      opts.body = JSON.stringify(body);
      opts.headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(`${API_BASE}${url}`, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      toast(err.detail || `Error ${res.status}`, 'error');
      return null;
    }
    if (res.status === 204) return {};
    return await res.json();
  } catch (e) {
    toast('Network error: ' + e.message, 'error');
    return null;
  }
}

// ── Tauri window controls ─────────────────────────────────────────────────────
function _tauriWin() {
  // Tauri v2 — try window module first, then webviewWindow fallback
  if (window.__TAURI__?.window?.getCurrentWindow)
    return window.__TAURI__.window.getCurrentWindow();
  if (window.__TAURI__?.webviewWindow?.getCurrentWebviewWindow)
    return window.__TAURI__.webviewWindow.getCurrentWebviewWindow();
  return null;
}
function titlebarMinimize() {
  const w = _tauriWin();
  if (w) w.minimize().catch(() => {});
}
function titlebarMaximize() {
  const w = _tauriWin();
  if (w) w.toggleMaximize().catch(() => {});
}
function titlebarClose() {
  const w = _tauriWin();
  if (w) w.close().catch(() => {});
}

function openUpdates() {
  showToast('Update check coming soon.', 'info');
}

// ── Backend health check (Tauri sidecar startup) ──────────────────────────────
async function waitForBackend(maxMs = 30000) {
  const msgEl = document.getElementById('boot-msg');
  const start  = Date.now();
  while (Date.now() - start < maxMs) {
    try {
      const r = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(1500) });
      if (r.ok) return true;
    } catch (_) {}
    const elapsed = Math.round((Date.now() - start) / 1000);
    if (msgEl) msgEl.textContent = `Starting Voxarah… ${elapsed}s`;
    await new Promise(r => setTimeout(r, 600));
  }
  if (msgEl) msgEl.textContent = 'Backend failed to start. Please restart the app.';
  return false;
}

// ── Boot ──────────────────────────────────────────────────────────────────────
async function boot() {
  // Tauri mode: mark body class + wait for Python sidecar to be ready
  if (IN_TAURI) {
    document.documentElement.classList.add('tauri-mode');

    const overlay = document.getElementById('boot-overlay');
    const ready   = await waitForBackend();
    if (!ready) { toast('Backend failed to start', 'error'); return; }
    toast(`Backend ready on port ${FIXED_PORT}`, 'success');
    if (overlay) {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.4s';
      setTimeout(() => { overlay.style.display = 'none'; }, 420);
    }
    // Show the native window now that UI is ready (window starts hidden in tauri.conf.json)
    if (window.__TAURI__) window.__TAURI__.window.getCurrentWindow().show();
  }

  initTabs();
  initFileUpload();
  initButtons();
  wsConnect();
  await loadSettings();
  await initCoachingProfiles();

  // Load initial status
  const status = await apiFetch('/api/status');
  if (status) {
    if (status.filename) {
      // File was loaded in a previous session — re-enable button
      showFileLoaded(status.filename, '—');
      el('btn-analyze').disabled = false;
    }
    if (status.has_results) {
      const results = await apiFetch('/api/results');
      if (results) onAnalysisDone(results);
    }
  }

  // Draw empty canvases
  requestAnimationFrame(() => {
    drawWaveform();
    drawPitch([], {}, 1);
  });
}

function initButtons() {
  el('btn-analyze').addEventListener('click', runAnalysis);
  el('btn-play-orig').addEventListener('click', playOriginal);
  el('btn-play-clean').addEventListener('click', playCleaned);
  el('btn-stop').addEventListener('click', stopAudio);
  el('timeline-track').addEventListener('click', seekAudio);
  el('btn-rec-start').addEventListener('click', startRec);
  el('btn-rec-stop').addEventListener('click', stopRec);
  el('btn-export-labels').addEventListener('click', exportLabels);
  el('btn-export-wav').addEventListener('click', exportWav);
  el('btn-ai-coach').addEventListener('click', getAICoaching);
  el('btn-send-feedback').addEventListener('click', sendFeedback);
  el('ai-chat-send').addEventListener('click', sendChatMessage);
  el('ai-chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
  });
}

document.addEventListener('DOMContentLoaded', boot);
