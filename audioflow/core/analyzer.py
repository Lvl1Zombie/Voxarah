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
        #   0.00–0.05  startup
        #   0.05–0.20  file read        (+0.15)
        #   0.20–0.50  silence scan     (+0.30)
        #   0.50–0.80  stutter scan     (+0.30)
        #   0.80–0.95  unclear scan     (+0.15)
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

        prog(0.05, "Reading audio file…")
        samples, sr = read_wav_mono(filepath,
                                    on_progress=_make_prog("Reading audio file…", 0.05, 0.15))
        duration = len(samples) / sr

        prog(0.20, "Detecting silences…")
        silence_regions = self.find_silence_regions(
            samples, sr,
            on_progress=_make_prog("Detecting silences…", 0.20, 0.30))

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

        prog(0.50, "Scanning for stutters…")
        stutters = []
        if self.settings.get('detect_stutters', True):
            stutters = self.detect_stutters(
                samples, sr,
                on_progress=_make_prog("Scanning for stutters…", 0.50, 0.30))
            for s in stutters:
                s['type'] = 'stutter'

        prog(0.80, "Checking for unclear sections…")
        unclear = []
        if self.settings.get('detect_unclear', True):
            unclear = self.detect_unclear(
                samples, sr,
                on_progress=_make_prog("Checking for unclear sections…", 0.80, 0.15))
            for u in unclear:
                u['type'] = 'unclear'

        prog(0.95, "Computing statistics…")

        max_pause  = self.settings.get('max_pause_duration', 1.0)
        time_saved = sum(max(0.0, p['duration'] - max_pause) for p in long_pauses)
        all_edits  = pause_edits + stutters + unclear

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
            'all_edits':       all_edits,
            'stats': {
                'duration':      duration,
                'pause_count':   len(long_pauses),
                'stutter_count': len(stutters),
                'unclear_count': len(unclear),
                'time_saved':    time_saved,
                'total_flags':   len(stutters) + len(unclear),
            },
        }


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
            'pause':   '[PAUSE]',
            'stutter': '[STUTTER]',
            'unclear': '[UNCLEAR]',
        }.get(edit['type'], '[FLAG]')
        lines.append(f"{edit['start']:.3f}\t{edit['end']:.3f}\t{tag} {edit['desc']}")
    return "\n".join(lines)
