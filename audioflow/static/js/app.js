/* ============================================================
   Voxarah Web — Frontend App
   Vanilla JS, no framework. All state lives server-side.
   ============================================================ */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const S = {
  results:       null,
  waveformPeaks: [],
  flags:         [],
  duration:      0,
  playingAudio:  null,   // HTMLAudioElement
  playInterval:  null,
  filename:      '',
  settings:      {},
  compareSlots:  [{}, {}, {}],
};

// ── WebSocket ─────────────────────────────────────────────────────────────────
let ws = null;
let wsRetry = 0;

function wsConnect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

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
      setDot('dot-ai',     msg.ai_online ? 'green pulse' : '');
      el('lbl-ai').textContent = msg.ai_online ? 'AI LIVE' : 'AI OFFLINE';
      setDot('dot-ffmpeg', msg.ffmpeg_ok  ? 'green' : 'red');
      if (msg.version) el('lbl-version').textContent = 'v' + msg.version;
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
      break;

    case 'ai_done':
      // full text already streamed via tokens
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
const el   = id => document.getElementById(id);
const qs   = (s, root=document) => root.querySelector(s);
const qsa  = (s, root=document) => [...root.querySelectorAll(s)];

function setDot(id, classes) {
  const d = el(id);
  d.className = 'status-dot ' + classes;
}

function rangeUpdate(input, labelId, fmt) {
  el(labelId).textContent = fmt(+input.value);
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type='info', duration=4000) {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  el('toast-container').appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ── Tab navigation ─────────────────────────────────────────────────────────────
function initTabs() {
  qsa('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function switchTab(key) {
  qsa('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.tab === key));
  qsa('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + key));
  if (key === 'history') loadHistory();
  if (key === 'characters') loadCharacters();
  if (key === 'compare') initCompare();
  if (key === 'coaching') initCoachingProfiles();
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
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
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
    el(id).className = 'stat-value' + (el(id).textContent === '0' ? ' green' : '');
  });

  // Pitch badge
  const ps = results.pitch_stats || {};
  const ratingColors = { EXPRESSIVE: 'var(--green)', MODERATE: 'var(--yellow)', FLAT: 'var(--red)' };
  const badge = el('pitch-badge');
  badge.textContent = ps.rating ? `${ps.rating}  ±${Math.round(ps.std_hz||0)} Hz` : '';
  badge.style.color = ratingColors[ps.rating] || 'var(--text-muted)';

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
  const sevColors = { pause:'#F5C518', stutter:'#f76a8a', unclear:'#9b6bff', breath:'#4ab8d8', mouth_noise:'#f5a623' };
  tbody.innerHTML = issues.map(r => {
    const c   = sevColors[r.type] || '#666680';
    const bars = [1,2,3].map(n => `<div class="sev-bar" style="background:${n<=r.severity ? c : '#2a2a3a'}"></div>`).join('');
    return `<tr>
      <td><span class="flag-badge flag-${r.type}">${r.type.replace('_',' ')}</span></td>
      <td class="text-mono text-muted text-xs">${r.time}</td>
      <td class="text-sm text-dim">${r.desc}</td>
      <td><div class="sev-bars">${bars}</div></td>
    </tr>`;
  }).join('');
}

// ── Playback ───────────────────────────────────────────────────────────────────
function playOriginal() { playAudio('/api/audio/original'); }
async function playCleaned() {
  toast('Preparing cleaned audio…');
  playAudio('/api/audio/cleaned');
}

function playAudio(url) {
  stopAudio();
  const audio = new Audio(url);
  S.playingAudio = audio;
  el('btn-stop').disabled = false;

  audio.addEventListener('timeupdate', () => {
    const frac = audio.currentTime / (audio.duration || 1);
    el('timeline-fill').style.width = (frac * 100) + '%';
    el('playback-time').textContent = fmtTime(audio.currentTime) + ' / ' + fmtTime(audio.duration || 0);
    // Redraw playhead on canvases
    drawPlayhead(frac);
  });
  audio.addEventListener('ended', () => {
    el('btn-stop').disabled = true;
    el('timeline-fill').style.width = '0%';
    S.playingAudio = null;
  });
  audio.play().catch(e => toast('Playback error: ' + e.message, 'error'));
}

function stopAudio() {
  if (S.playingAudio) {
    S.playingAudio.pause();
    S.playingAudio = null;
  }
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
  window.location.href = '/api/export/wav';
}
function exportLabels() {
  window.location.href = '/api/export/labels';
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
      `<div class="tip-item"><span class="tip-bullet">›</span>${t}</div>`
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

async function getAICoaching() {
  el('ai-output').textContent = '';
  el('btn-ai-coach').disabled = true;
  const profile = el('coaching-profile')?.value || '';
  await apiFetch('/api/coaching/ai', 'POST', { profile });
}

function appendAI(token) {
  const box = el('ai-output');
  box.textContent += token;
  box.scrollTop = box.scrollHeight;
  el('btn-ai-coach').disabled = false;
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
  <div class="compare-col" id="cmp-col-${i}">
    <div class="compare-col-header">
      <span class="take-label">TAKE ${i + 1}</span>
      <span class="best-badge">BEST</span>
      <div class="grow"></div>
      <button class="btn btn-icon" title="Clear" onclick="clearTake(${i})">✕</button>
    </div>
    <div style="padding:12px">
      <label style="display:block;margin-bottom:8px">
        <input type="file" style="display:none" id="cmp-input-${i}"
               onchange="uploadTake(${i},this.files[0])" accept=".wav,.mp3,.m4a,.flac,.ogg">
        <button class="btn btn-ghost btn-sm btn-full"
                onclick="el('cmp-input-${i}').click()">Load File</button>
      </label>
      <div class="text-xs text-muted text-mono" id="cmp-fname-${i}" style="margin-bottom:4px"></div>
      <div class="text-xs text-muted" id="cmp-status-${i}"></div>
    </div>
    <div class="compare-score-big" id="cmp-score-${i}">—</div>
    <div class="compare-grade" id="cmp-grade-${i}"></div>
    <div style="padding:0 12px 8px">
      <button class="btn btn-yellow btn-sm btn-full" id="cmp-analyze-btn-${i}"
              onclick="analyzeTake(${i})" disabled>Analyze</button>
    </div>
    <div style="padding:0 12px 12px" id="cmp-dims-${i}"></div>
    <div style="padding:0 12px 12px;border-top:1px solid var(--border)" id="cmp-stats-${i}"></div>
  </div>`;
}

async function uploadTake(slot, file) {
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  toast(`Loading take ${slot+1}…`);
  try {
    const res = await fetch(`/api/compare/upload/${slot}`, { method: 'POST', body: fd });
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
                    : 'var(--text-muted)';
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
  scored.forEach(({ i }) => el(`cmp-col-${i}`).classList.toggle('best', i === best.i));
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
  el(`cmp-col-${slot}`).classList.remove('best');
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
async function loadCharacters() {
  const grid = el('characters-grid');
  if (_characters) return;
  _characters = await apiFetch('/api/characters');
  if (!_characters) return;
  grid.innerHTML = Object.entries(_characters).map(([name, data]) => {
    const emoji = name.split(' ')[0];
    const label = name.replace(/^\S+\s*/, '');
    const diffClass = { Beginner:'diff-beginner', Intermediate:'diff-intermediate', Advanced:'diff-advanced' }[data.difficulty] || '';
    return `<div class="character-card" onclick="showCharacter('${encodeURIComponent(name)}')">
      <div class="char-emoji">${emoji}</div>
      <div class="char-name">${label}</div>
      <div class="char-cat">${data.category}</div>
      <div class="char-diff ${diffClass}">${data.difficulty}</div>
    </div>`;
  }).join('');
}

function showCharacter(encodedName) {
  const name = decodeURIComponent(encodedName);
  const data = _characters[name];
  if (!data) return;
  el('char-modal-title').textContent = name;
  el('char-modal-cat').textContent   = `${data.category} · ${data.difficulty}`;
  el('char-modal-body').innerHTML = `
    <p class="text-sm text-dim" style="margin-bottom:16px">${data.description}</p>
    <div class="section-label">Vocal Qualities</div>
    <ul style="margin:0 0 16px;padding-left:16px">${(data.vocal_qualities||[]).map(q=>`<li class="text-sm text-dim" style="margin:3px 0">${q}</li>`).join('')}</ul>
    <div class="section-label">Pro Tips</div>
    <ul style="margin:0 0 16px;padding-left:16px">${(data.pro_tips||[]).map(t=>`<li class="text-sm text-dim" style="margin:3px 0">${t}</li>`).join('')}</ul>
    <div class="section-label">Common Mistakes</div>
    <ul style="margin:0 0 16px;padding-left:16px">${(data.common_mistakes||[]).map(m=>`<li class="text-sm text-dim" style="margin:3px 0">${m}</li>`).join('')}</ul>
    <div class="section-label">Known For</div>
    <div class="flex gap-2" style="flex-wrap:wrap">${(data.example_pros||[]).map(p=>`<span class="pill pill-muted">${p}</span>`).join('')}</div>`;
  el('char-modal').classList.remove('hidden');
}

function closeCharModal(e) {
  if (!e || e.target === el('char-modal')) el('char-modal').classList.add('hidden');
}

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  const records = await apiFetch('/api/history');
  const list    = el('history-list');
  if (!records || !records.length) {
    list.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📁</div>No history yet</div>`;
    return;
  }
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
    const res = await fetch(url, opts);
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

// ── Boot ──────────────────────────────────────────────────────────────────────
async function boot() {
  initTabs();
  initFileUpload();
  wsConnect();
  await loadSettings();
  await initCoachingProfiles();

  // Load initial status
  const status = await apiFetch('/api/status');
  if (status) {
    if (status.has_results) {
      // Server has results from a prior session load
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

document.addEventListener('DOMContentLoaded', boot);
