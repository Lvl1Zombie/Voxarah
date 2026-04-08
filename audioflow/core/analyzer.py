"""
Voxarah — Audio Analysis Engine
Detects silences, stutters, and unclear sections without modifying audio levels.
Uses numpy for vectorized RMS computation — typically 20–50x faster than pure Python.
"""

import math
import wave
import struct
import os
import tempfile
from typing import List, Dict, Tuple, Optional

import numpy as np


# ── Helpers ───────────────────────────────────────────────────────────────────

def db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def _hop_rms(arr: np.ndarray, hop: int) -> np.ndarray:
    """Return RMS of each non-overlapping hop window across arr (1-D float32)."""
    n = (len(arr) // hop) * hop
    return np.sqrt(np.mean(arr[:n].reshape(-1, hop) ** 2, axis=1))


def read_wav_mono(filepath: str, on_progress=None) -> Tuple[np.ndarray, int]:
    """
    Read a WAV file and return (samples_float32, sample_rate).
    on_progress(fraction) called periodically with 0.0–1.0 during load.
    """
    CHUNK_FRAMES = 44100  # ~1 second per chunk

    with wave.open(filepath, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth  = wf.getsampwidth()
        framerate  = wf.getframerate()
        n_frames   = wf.getnframes()

    frame_bytes = sampwidth * n_channels
    max_val     = float(2 ** (sampwidth * 8 - 1))

    chunks      = []
    frames_read = 0

    with wave.open(filepath, 'rb') as wf:
        while frames_read < n_frames:
            chunk_size = min(CHUNK_FRAMES, n_frames - frames_read)
            raw = wf.readframes(chunk_size)
            if not raw:
                break

            # Trim to complete frames
            raw = raw[:len(raw) - len(raw) % frame_bytes]
            if not raw:
                break

            if sampwidth == 1:
                data = np.frombuffer(raw, dtype=np.int8).astype(np.float32)
            elif sampwidth == 2:
                data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            elif sampwidth == 3:
                # 24-bit: no native numpy int24 — unpack 3 bytes per sample manually
                b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
                data = (b[:, 0].astype(np.int32)
                        | (b[:, 1].astype(np.int32) << 8)
                        | (b[:, 2].astype(np.int32) << 16))
                # Sign-extend 24-bit to 32-bit
                data = np.where(data >= 0x800000, data - 0x1000000, data)
                data = data.astype(np.float32)
            else:  # 32-bit
                data = np.frombuffer(raw, dtype=np.int32).astype(np.float32)

            data /= max_val

            if n_channels > 1:
                data = data.reshape(-1, n_channels).mean(axis=1)

            chunks.append(data)
            frames_read += len(data)

            if on_progress and n_frames > 0:
                on_progress(min(1.0, frames_read / n_frames))

    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32), framerate


def write_wav_mono(filepath: str, samples, sample_rate: int):
    """Write a mono float sample array/list to a 16-bit WAV file."""
    arr = np.asarray(samples, dtype=np.float32)
    clipped = np.clip(arr, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


# ── Core Analysis ─────────────────────────────────────────────────────────────

class AudioAnalyzer:

    def __init__(self, settings: dict):
        self.settings = settings

    # ── Silence / Pause Detection ──────────────────────────────────

    def find_silence_regions(self, samples, sr: int,
                             on_progress=None) -> List[Dict]:
        """
        Find all contiguous silent regions above a minimum duration.
        Returns list of {start, end, duration} in seconds.
        on_progress(fraction) called at ~1% boundaries.
        """
        thresh_db   = self.settings.get('silence_threshold_db', -40)
        min_dur     = self.settings.get('min_silence_duration', 0.15)
        thresh      = db_to_linear(thresh_db)
        hop_samples = max(1, int(sr * 0.01))  # 10 ms hops

        arr = np.asarray(samples, dtype=np.float32)

        # Vectorised RMS for every hop — single C-speed operation
        hop_rms = _hop_rms(arr, hop_samples)
        silent   = hop_rms < thresh

        if on_progress:
            on_progress(1.0)

        # Walk the boolean mask to collect contiguous silent runs
        regions   = []
        in_silence = False
        sil_start  = 0.0

        for idx, is_silent in enumerate(silent):
            t = idx * hop_samples / sr
            if is_silent and not in_silence:
                in_silence = True
                sil_start  = t
            elif not is_silent and in_silence:
                dur = t - sil_start
                if dur >= min_dur:
                    regions.append({'start': sil_start, 'end': t, 'duration': dur})
                in_silence = False

        if in_silence:
            sil_end = len(arr) / sr
            dur = sil_end - sil_start
            if dur >= min_dur:
                regions.append({'start': sil_start, 'end': sil_end, 'duration': dur})

        return regions

    def find_long_pauses(self, samples, sr: int) -> List[Dict]:
        """Return silence regions longer than max_pause_duration."""
        max_pause = self.settings.get('max_pause_duration', 1.0)
        return [r for r in self.find_silence_regions(samples, sr)
                if r['duration'] > max_pause]

    # ── Stutter Detection ──────────────────────────────────────────

    def detect_stutters(self, samples, sr: int,
                        on_progress=None) -> List[Dict]:
        """
        Detect likely stutters by finding clusters of micro-silence gaps
        whose intervening voiced bursts have similar energy (repetition).

        Algorithm:
         1. Compute 20 ms frame energies with numpy (vectorised).
         2. Extract micro-silence gaps (50–200 ms each).
         3. Merge gaps separated by noise-level bursts (< 40 ms).
         4. Cluster gaps separated by short voiced bursts (< 300 ms)
            within the stutter_window.
         5. Reject clusters where burst energies vary too much (CV > 0.40).
         6. Nearby detections within 0.25 s are merged.
        """
        window_sec     = self.settings.get('stutter_window', 0.8)
        frame_sec      = 0.02   # 20 ms
        frame_size     = max(1, int(sr * frame_sec))
        silence_thresh = db_to_linear(self.settings.get('silence_threshold_db', -40))

        arr = np.asarray(samples, dtype=np.float32)

        # ── step 1: vectorised per-frame RMS ────────────────────────
        frame_energy = _hop_rms(arr, frame_size)   # shape (n_frames,)

        if on_progress:
            on_progress(1.0)

        fe = frame_energy.tolist()   # plain list for the clustering logic below

        # ── step 2: micro-silence gaps (50–200 ms) ──────────────────
        raw_gaps: list[dict] = []
        in_gap    = False
        gap_start = 0
        for idx, e in enumerate(fe):
            if e <= silence_thresh:
                if not in_gap:
                    in_gap    = True
                    gap_start = idx
            else:
                if in_gap:
                    gap_dur = (idx - gap_start) * frame_sec
                    if 0.05 <= gap_dur <= 0.20:
                        raw_gaps.append({'start': gap_start * frame_sec,
                                         'end':   idx * frame_sec})
                    in_gap = False

        # ── step 3: merge gaps separated by noise bursts (< 40 ms) ──
        gaps: list[dict] = []
        for g in raw_gaps:
            if gaps and (g['start'] - gaps[-1]['end']) < 0.04:
                gaps[-1] = {'start': gaps[-1]['start'], 'end': g['end']}
            else:
                gaps.append(dict(g))
        gaps = [g for g in gaps if 0.05 <= (g['end'] - g['start']) <= 0.20]

        # ── step 4: cluster nearby gaps ──────────────────────────────
        stutters: list[dict] = []
        i = 0
        while i < len(gaps):
            cluster = [gaps[i]]
            j = i + 1
            while j < len(gaps):
                burst = gaps[j]['start'] - cluster[-1]['end']
                span  = gaps[j]['end']   - cluster[0]['start']
                if burst <= 0.3 and span <= window_sec:
                    cluster.append(gaps[j])
                    j += 1
                else:
                    break

            if len(cluster) >= 2:
                # ── step 5a: gap regularity ──────────────────────────
                gap_durs  = [g['end'] - g['start'] for g in cluster]
                gap_ratio = max(gap_durs) / (min(gap_durs) + 1e-12)
                if gap_ratio > 1.5:
                    i = j
                    continue

                # ── step 5b: burst energy similarity ─────────────────
                burst_energies: list[float] = []
                for k in range(len(cluster) - 1):
                    fi = int(cluster[k]['end']       / frame_sec)
                    fj = int(cluster[k + 1]['start'] / frame_sec)
                    if fi < fj:
                        burst_energies.append(float(np.mean(frame_energy[fi:fj])))

                is_stutter = True
                if len(burst_energies) >= 2:
                    be = np.array(burst_energies)
                    cv = float(np.std(be) / (np.mean(be) + 1e-12))
                    if cv > 0.40:
                        is_stutter = False
                elif len(burst_energies) == 1:
                    if burst_energies[0] < silence_thresh * 5:
                        is_stutter = False

                if is_stutter:
                    s = cluster[0]['start']
                    e = cluster[-1]['end']
                    if not stutters or (s - stutters[-1]['end']) > 0.25:
                        stutters.append({
                            'start': max(0.0, s - 0.05),
                            'end':   min(len(arr) / sr, e + 0.05),
                            'desc':  'Possible stutter / repeated sound',
                        })
                i = j
            else:
                i += 1

        return stutters

    # ── Breath Detection ──────────────────────────────────────────

    def detect_breaths(self, samples, sr: int,
                       on_progress=None) -> List[Dict]:
        """
        Detect audible inhales and exhales.

        A breath is a sustained, smooth low-energy event (80–400 ms) that:
        - Sits above the silence floor but below ~35% of mean speech RMS
        - Has a smooth energy envelope (peak/mean ratio < 3.0)
        - Occurs adjacent to a silence region (within 500 ms)
        """
        thresh_db  = self.settings.get('silence_threshold_db', -40)
        thresh     = db_to_linear(thresh_db)
        frame_sec  = 0.005                         # 5 ms hops
        frame_size = max(1, int(sr * frame_sec))

        arr       = np.asarray(samples, dtype=np.float32)
        frame_rms = _hop_rms(arr, frame_size)

        if on_progress:
            on_progress(1.0)

        voiced = frame_rms[frame_rms > thresh]
        if len(voiced) == 0:
            return []
        mean_speech  = float(np.mean(voiced))
        breath_ceil  = mean_speech * 0.42   # breaths below 42% of mean speech level

        in_zone   = (frame_rms > thresh) & (frame_rms < breath_ceil)
        sil_mask  = frame_rms < thresh

        candidates: list[dict] = []
        in_run, run_start = False, 0
        for idx, z in enumerate(in_zone):
            if z and not in_run:
                in_run, run_start = True, idx
            elif not z and in_run:
                dur = (idx - run_start) * frame_sec
                if 0.10 <= dur <= 0.55:    # 100 ms–550 ms
                    candidates.append({'s': run_start, 'e': idx,
                                       'start': run_start * frame_sec,
                                       'end':   idx * frame_sec})
                in_run = False

        look = int(0.5 / frame_sec)   # 500 ms in frames
        breaths: list[dict] = []
        for c in candidates:
            window = frame_rms[c['s']:c['e']]
            if len(window) == 0:
                continue
            peak = float(np.max(window))
            mean = float(np.mean(window))
            if peak / (mean + 1e-9) > 4.0:    # too spiky → not a breath
                continue
            before = sil_mask[max(0, c['s'] - look): c['s']]
            after  = sil_mask[c['e']: min(len(sil_mask), c['e'] + look)]
            if not (np.any(before) or np.any(after)):
                continue
            breaths.append({
                'start': c['start'],
                'end':   c['end'],
                'desc':  'Audible breath — consider removing or fading out',
            })
        return breaths

    # ── Mouth Noise Detection ──────────────────────────────────────

    def detect_mouth_noises(self, samples, sr: int,
                            on_progress=None) -> List[Dict]:
        """
        Detect clicks, lip smacks, and tongue noise.

        Mouth noises are very short (10–80 ms), sharp-onset transients
        (peak/mean > 1.8) that occur in or adjacent to silence regions.
        """
        thresh_db  = self.settings.get('silence_threshold_db', -40)
        thresh     = db_to_linear(thresh_db)
        frame_sec  = 0.005
        frame_size = max(1, int(sr * frame_sec))

        arr       = np.asarray(samples, dtype=np.float32)
        frame_rms = _hop_rms(arr, frame_size)

        if on_progress:
            on_progress(1.0)

        noise_floor = thresh * 1.5
        sil_mask    = frame_rms < thresh
        active      = frame_rms > noise_floor

        candidates: list[dict] = []
        in_run, run_start = False, 0
        for idx, a in enumerate(active):
            if a and not in_run:
                in_run, run_start = True, idx
            elif not a and in_run:
                dur = (idx - run_start) * frame_sec
                if 0.010 <= dur <= 0.080:
                    candidates.append({'s': run_start, 'e': idx,
                                       'start': run_start * frame_sec,
                                       'end':   idx * frame_sec})
                in_run = False

        look = int(0.2 / frame_sec)   # 200 ms in frames
        raw: list[dict] = []
        for c in candidates:
            window = frame_rms[c['s']:c['e']]
            if len(window) == 0:
                continue
            peak = float(np.max(window))
            mean = float(np.mean(window))
            if peak / (mean + 1e-9) < 1.8:    # too smooth → not a click
                continue
            before = sil_mask[max(0, c['s'] - look): c['s']]
            after  = sil_mask[c['e']: min(len(sil_mask), c['e'] + look)]
            if not (np.any(before) or np.any(after)):
                continue
            raw.append({'start': c['start'], 'end': c['end'],
                        'desc': 'Mouth noise (click / smack) — edit out'})

        # Merge events within 50 ms of each other
        merged: list[dict] = []
        for mn in raw:
            if merged and (mn['start'] - merged[-1]['end']) < 0.05:
                merged[-1]['end'] = mn['end']
            else:
                merged.append(dict(mn))
        return merged

    # ── Unclear Audio Detection ────────────────────────────────────

    def detect_unclear(self, samples, sr: int,
                       on_progress=None) -> List[Dict]:
        """
        Flag sections where audio energy is in the "mumble zone" —
        audible but significantly below average speech level.
        on_progress(fraction) called at ~1% boundaries.
        """
        thresh_db  = self.settings.get('silence_threshold_db', -40)
        frame_sec  = 0.1
        frame_size = max(1, int(sr * frame_sec))
        thresh     = db_to_linear(thresh_db)

        arr        = np.asarray(samples, dtype=np.float32)
        frame_rms  = _hop_rms(arr, frame_size)   # shape (n_frames,)

        # Mean speech level (frames above silence floor)
        voiced = frame_rms[frame_rms > thresh]
        if len(voiced) == 0:
            if on_progress:
                on_progress(1.0)
            return []

        mean_speech         = float(np.mean(voiced))
        unclear_thresh_low  = thresh * 1.2
        unclear_thresh_high = mean_speech * 0.45

        if on_progress:
            on_progress(1.0)

        # Walk frames to collect unclear runs
        unclear    = []
        in_unclear = False
        unc_start  = 0.0
        low_count  = 0

        for idx, level in enumerate(frame_rms):
            t          = idx * frame_size / sr
            is_unclear = unclear_thresh_low < level < unclear_thresh_high

            if is_unclear:
                if not in_unclear:
                    in_unclear = True
                    unc_start  = t
                    low_count  = 0
                low_count += 1
            else:
                if in_unclear and low_count >= 3:
                    unclear.append({
                        'start': unc_start,
                        'end':   t,
                        'desc':  'Audio may be too quiet or unclear — consider re-recording',
                    })
                in_unclear = False

        return unclear[:10]

    # ── Pitch Detection ───────────────────────────────────────────

    def detect_pitch(self, samples, sr: int,
                     on_progress=None) -> List[Dict]:
        """
        Detect fundamental frequency frame-by-frame via autocorrelation (FFT).
        Returns list of {time, freq, voiced} — freq=0 for unvoiced frames.

        Frame: 30 ms,  Hop: 10 ms,  Range: 70–500 Hz (covers all voice types).
        Voiced/unvoiced gated by energy AND autocorrelation confidence > 0.28.
        """
        frame_ms   = 30
        hop_ms     = 10
        f_min, f_max = 70, 500

        frame_size = max(1, int(sr * frame_ms / 1000))
        hop_size   = max(1, int(sr * hop_ms   / 1000))
        lag_min    = max(1, int(sr / f_max))
        lag_max    = int(sr / f_min)

        arr          = np.asarray(samples, dtype=np.float32)
        energy_floor = db_to_linear(self.settings.get('silence_threshold_db', -40)) * 2.5
        hann         = np.hanning(frame_size).astype(np.float32)

        n_frames = max(0, (len(arr) - frame_size) // hop_size)
        pitch_frames: list[dict] = []

        for i in range(n_frames):
            t     = i * hop_size / sr
            start = i * hop_size
            frame = arr[start: start + frame_size]

            # Energy gate
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if rms < energy_floor:
                pitch_frames.append({'time': t, 'freq': 0.0, 'voiced': False})
                continue

            # Autocorrelation via FFT (fast, no scipy needed)
            windowed = frame * hann
            n        = len(windowed)
            fft_r    = np.fft.rfft(windowed, n=2 * n)
            acf      = np.fft.irfft(fft_r * np.conj(fft_r))[:n].real

            if lag_max >= n or acf[0] < 1e-10:
                pitch_frames.append({'time': t, 'freq': 0.0, 'voiced': False})
                continue

            # Find best peak in voiced range
            search     = acf[lag_min: lag_max]
            peak_idx   = int(np.argmax(search))
            peak_lag   = peak_idx + lag_min
            confidence = acf[peak_lag] / acf[0]

            if confidence >= 0.28:
                pitch_frames.append({'time': t,
                                     'freq': float(sr / peak_lag),
                                     'voiced': True})
            else:
                pitch_frames.append({'time': t, 'freq': 0.0, 'voiced': False})

            if on_progress and n_frames > 0:
                on_progress((i + 1) / n_frames)

        if on_progress:
            on_progress(1.0)
        return pitch_frames

    # ── Full Analysis Run ──────────────────────────────────────────

    def analyze(self, filepath: str,
                progress_callback=None) -> Dict:
        """
        Full analysis pass. Returns a results dict with:
          - pauses, stutters, unclear, all_edits
          - duration, sample_rate
          - stats
        """
        def prog(pct, msg):
            if progress_callback:
                progress_callback(pct, msg)

        # Phase budget (must sum to 1.0):
        #   0.00–0.04  startup
        #   0.04–0.14  file read        (+0.10)
        #   0.14–0.30  silence scan     (+0.16)
        #   0.30–0.48  stutter scan     (+0.18)
        #   0.48–0.57  unclear scan     (+0.09)
        #   0.57–0.65  breath scan      (+0.08)
        #   0.65–0.72  mouth noise scan (+0.07)
        #   0.72–0.95  pitch scan       (+0.23)
        #   0.95–1.00  stats + done     (+0.05)

        def _make_prog(label, base, span):
            last = [-1]
            def _cb(fraction):
                overall = base + fraction * span
                pct = int(overall * 100)
                if pct != last[0]:
                    last[0] = pct
                    prog(overall, label)
            return _cb

        prog(0.04, "Reading audio file…")
        samples, sr = read_wav_mono(filepath,
                                    on_progress=_make_prog("Reading audio file…", 0.04, 0.10))
        duration = len(samples) / sr

        prog(0.14, "Detecting silences…")
        silence_regions = self.find_silence_regions(
            samples, sr,
            on_progress=_make_prog("Detecting silences…", 0.14, 0.16))

        long_pauses = [r for r in silence_regions
                       if r['duration'] > self.settings.get('max_pause_duration', 1.0)]
        pause_edits = [
            {
                'type':  'pause',
                'start': p['start'],
                'end':   p['end'],
                'desc':  f"Long pause ({p['duration']:.1f}s) → will trim to "
                         f"{self.settings.get('max_pause_duration', 1.0):.1f}s",
            }
            for p in long_pauses
        ]

        prog(0.30, "Scanning for stutters…")
        stutters = []
        if self.settings.get('detect_stutters', True):
            stutters = self.detect_stutters(
                samples, sr,
                on_progress=_make_prog("Scanning for stutters…", 0.30, 0.18))
            for s in stutters:
                s['type'] = 'stutter'

        prog(0.48, "Checking for unclear sections…")
        unclear = []
        if self.settings.get('detect_unclear', True):
            unclear = self.detect_unclear(
                samples, sr,
                on_progress=_make_prog("Checking for unclear sections…", 0.48, 0.09))
            for u in unclear:
                u['type'] = 'unclear'

        prog(0.57, "Scanning for breaths…")
        breaths = []
        if self.settings.get('detect_breaths', True):
            breaths = self.detect_breaths(
                samples, sr,
                on_progress=_make_prog("Scanning for breaths…", 0.57, 0.08))
            for b in breaths:
                b['type'] = 'breath'

        prog(0.65, "Scanning for mouth noises…")
        mouth_noises = []
        if self.settings.get('detect_mouth_noises', True):
            mouth_noises = self.detect_mouth_noises(
                samples, sr,
                on_progress=_make_prog("Scanning for mouth noises…", 0.65, 0.07))
            for m in mouth_noises:
                m['type'] = 'mouth_noise'

        prog(0.72, "Analyzing pitch…")
        pitch_frames = self.detect_pitch(
            samples, sr,
            on_progress=_make_prog("Analyzing pitch…", 0.72, 0.23))
        pitch_stats = _compute_pitch_stats(pitch_frames)

        prog(0.95, "Computing statistics…")

        max_pause  = self.settings.get('max_pause_duration', 1.0)
        time_saved = sum(max(0.0, p['duration'] - max_pause) for p in long_pauses)
        all_edits  = pause_edits + stutters + unclear + breaths + mouth_noises

        prog(1.0, "Analysis complete")

        return {
            'filepath':        filepath,
            'samples':         samples,
            'sample_rate':     sr,
            'duration':        duration,
            'silence_regions': silence_regions,
            'long_pauses':     long_pauses,
            'stutters':        stutters,
            'unclear':         unclear,
            'breaths':         breaths,
            'mouth_noises':    mouth_noises,
            'pitch_frames':    pitch_frames,
            'pitch_stats':     pitch_stats,
            'all_edits':       all_edits,
            'stats': {
                'duration':           duration,
                'pause_count':        len(long_pauses),
                'stutter_count':      len(stutters),
                'unclear_count':      len(unclear),
                'breath_count':       len(breaths),
                'mouth_noise_count':  len(mouth_noises),
                'time_saved':         time_saved,
                'total_flags':        len(stutters) + len(unclear) + len(breaths) + len(mouth_noises),
            },
        }


# ── Pitch Stats ──────────────────────────────────────────────────────────────

def _compute_pitch_stats(pitch_frames: list) -> dict:
    """
    Summarise pitch_frames into coaching-relevant metrics.
    Rating thresholds (std dev of Hz):
      EXPRESSIVE  ≥ 22 Hz  (~2.5 semitones at 150 Hz average)
      MODERATE    ≥ 10 Hz
      FLAT        <  10 Hz
    Also computes per-frame variance scores (0–1) for waveform coloring.
    """
    voiced = [f['freq'] for f in pitch_frames if f.get('voiced') and f['freq'] > 0]
    if len(voiced) < 10:
        return {'mean_hz': 0.0, 'range_hz': 0.0, 'std_hz': 0.0,
                'voiced_pct': 0.0, 'rating': 'NO DATA',
                'frame_scores': [0.0] * len(pitch_frames)}

    arr        = np.array(voiced, dtype=np.float32)
    mean_hz    = float(np.mean(arr))
    range_hz   = float(np.max(arr) - np.min(arr))
    std_hz     = float(np.std(arr))
    voiced_pct = len(voiced) / len(pitch_frames) * 100.0

    if std_hz >= 22:
        rating = 'EXPRESSIVE'
    elif std_hz >= 10:
        rating = 'MODERATE'
    else:
        rating = 'FLAT'

    # Rolling variance score per frame (window ±1 s worth of voiced frames)
    # Score 0 = flat, 1 = very expressive — used for coloring the contour
    window = 50   # ~50 voiced frames ≈ 1 s at 10 ms hop
    voiced_only = np.array([f['freq'] for f in pitch_frames
                             if f.get('voiced') and f['freq'] > 0], dtype=np.float32)
    scores_voiced: list[float] = []
    for i in range(len(voiced_only)):
        lo = max(0, i - window // 2)
        hi = min(len(voiced_only), i + window // 2 + 1)
        local_std = float(np.std(voiced_only[lo:hi]))
        scores_voiced.append(min(1.0, local_std / 22.0))

    vi = 0
    frame_scores: list[float] = []
    for f in pitch_frames:
        if f.get('voiced') and f['freq'] > 0:
            frame_scores.append(scores_voiced[vi])
            vi += 1
        else:
            frame_scores.append(0.0)

    return {
        'mean_hz':     mean_hz,
        'range_hz':    range_hz,
        'std_hz':      std_hz,
        'voiced_pct':  voiced_pct,
        'rating':      rating,
        'frame_scores': frame_scores,
    }


# ── Output: Cleaned Samples ──────────────────────────────────────────────────

def build_cleaned_samples(results: dict, settings: dict) -> Tuple[np.ndarray, int]:
    """
    Return (edited_samples_float32, sample_rate) with:
      - Long pauses trimmed to max_pause_duration
      - Breath regions silenced (10 ms fade in/out to avoid clicks)
      - Mouth noise regions silenced
    No disk I/O — used for in-app playback.
    """
    samples   = np.asarray(results['samples'], dtype=np.float32).copy()
    sr        = results['sample_rate']

    # ── Attenuate breaths and mouth noises in-place ───────────────
    def _attenuate_region(arr, start_s, end_s, sample_rate,
                          target_level=0.04, fade_ms=35):
        """
        Duck a region to target_level with smooth s-curve fades.
        target_level=0.04 (-28 dB) keeps room tone — sounds natural, not cut.
        fade_ms=35 ms long enough to avoid any click or syllable clip.
        Boundaries are inset by half the fade so speech edges are never touched.
        """
        inset = int(fade_ms * 0.5 * sample_rate / 1000)
        s = int(start_s * sample_rate) + inset
        e = int(end_s   * sample_rate) - inset
        s = max(0, s)
        e = min(len(arr), e)
        if s >= e:
            return
        fade = min(int(fade_ms * sample_rate / 1000), (e - s) // 2)
        if fade > 1:
            # s-curve via raised cosine for extra smoothness
            t = np.linspace(0.0, np.pi, fade)
            curve_down = 0.5 * (1.0 + np.cos(t))          # 1 → 0
            curve_up   = 0.5 * (1.0 - np.cos(t))          # 0 → 1
            arr[s: s + fade] *= curve_down * (1.0 - target_level) + target_level
            arr[e - fade: e] *= curve_up   * (1.0 - target_level) + target_level
        arr[s + fade: e - fade] *= target_level

    for region in results.get('breaths', []):
        _attenuate_region(samples, region['start'], region['end'], sr,
                          target_level=0.04, fade_ms=40)

    for region in results.get('mouth_noises', []):
        _attenuate_region(samples, region['start'], region['end'], sr,
                          target_level=0.02, fade_ms=20)

    # ── Trim long pauses ───────────────────────────────────────────
    pauses    = sorted(results['long_pauses'], key=lambda x: x['start'])
    max_pause = settings.get('max_pause_duration', 1.0)

    parts  = []
    cursor = 0
    for p in pauses:
        p_start  = int(p['start'] * sr)
        p_end    = int(p['end']   * sr)
        trim_end = p_start + int(max_pause * sr)
        parts.append(samples[cursor: p_start])
        parts.append(samples[p_start: trim_end])
        cursor = p_end
    parts.append(samples[cursor:])
    return (np.concatenate(parts) if parts else samples), sr


# ── Output: Cleaned WAV ───────────────────────────────────────────────────────

def build_cleaned_wav(results: dict, settings: dict, out_path: str):
    """
    Write a cleaned WAV with long pauses trimmed.
    Does NOT modify levels, noise, or anything else.
    """
    samples   = np.asarray(results['samples'], dtype=np.float32)
    sr        = results['sample_rate']
    pauses    = sorted(results['long_pauses'], key=lambda x: x['start'])
    max_pause = settings.get('max_pause_duration', 1.0)

    parts  = []
    cursor = 0

    for p in pauses:
        p_start  = int(p['start'] * sr)
        p_end    = int(p['end']   * sr)
        trim_end = p_start + int(max_pause * sr)

        parts.append(samples[cursor: p_start])   # audio before pause
        parts.append(samples[p_start: trim_end]) # trimmed pause
        cursor = p_end

    parts.append(samples[cursor:])
    out_samples = np.concatenate(parts) if parts else samples
    write_wav_mono(out_path, out_samples, sr)


# ── Output: Audacity Label File ───────────────────────────────────────────────

def build_label_file(results: dict) -> str:
    """
    Return Audacity-format label file content.
    Format: start\\tend\\tlabel
    """
    lines = []
    for edit in sorted(results['all_edits'], key=lambda x: x['start']):
        tag = {
            'pause':       '[PAUSE]',
            'stutter':     '[STUTTER]',
            'unclear':     '[UNCLEAR]',
            'breath':      '[BREATH]',
            'mouth_noise': '[MOUTH NOISE]',
        }.get(edit['type'], '[FLAG]')
        lines.append(f"{edit['start']:.3f}\t{edit['end']:.3f}\t{tag} {edit['desc']}")
    return "\n".join(lines)
