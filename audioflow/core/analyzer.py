"""
Voxarah — Audio Analysis Engine
Detects silences, stutters, and unclear sections without modifying audio levels.
"""

import math
import wave
import struct
import os
import tempfile
from typing import List, Dict, Tuple, Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)

def rms(samples: list) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))

def read_wav_mono(filepath: str) -> Tuple[list, int]:
    """Read a WAV file and return (samples_float, sample_rate)."""
    with wave.open(filepath, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth  = wf.getsampwidth()
        framerate  = wf.getframerate()
        n_frames   = wf.getnframes()
        raw        = wf.readframes(n_frames)

    fmt = {1: 'b', 2: 'h', 4: 'i'}.get(sampwidth, 'h')
    all_samples = struct.unpack(f"<{len(raw) // sampwidth}{fmt}", raw)

    # Mix down to mono
    if n_channels > 1:
        samples = [
            sum(all_samples[i:i + n_channels]) / n_channels
            for i in range(0, len(all_samples), n_channels)
        ]
    else:
        samples = list(all_samples)

    # Normalize to float [-1, 1]
    max_val = float(2 ** (sampwidth * 8 - 1))
    samples = [s / max_val for s in samples]
    return samples, framerate


def write_wav_mono(filepath: str, samples: list, sample_rate: int):
    """Write a mono float sample list to a 16-bit WAV file."""
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        clipped = [max(-1.0, min(1.0, s)) for s in samples]
        packed = struct.pack(f"<{len(clipped)}h",
                             *[int(s * 32767) for s in clipped])
        wf.writeframes(packed)


# ── Core Analysis ─────────────────────────────────────────────────────────────

class AudioAnalyzer:

    def __init__(self, settings: dict):
        self.settings = settings

    # ── Silence / Pause Detection ──────────────────────────────────

    def find_silence_regions(self, samples: list, sr: int) -> List[Dict]:
        """
        Find all contiguous silent regions above a minimum duration.
        Returns list of {start, end, duration} in seconds.
        """
        thresh_db   = self.settings.get('silence_threshold_db', -40)
        min_dur     = self.settings.get('min_silence_duration', 0.15)
        thresh      = db_to_linear(thresh_db)
        hop_samples = max(1, int(sr * 0.01))   # 10ms hops

        regions = []
        in_silence = False
        sil_start  = 0.0

        for i in range(0, len(samples), hop_samples):
            chunk = samples[i: i + hop_samples]
            level = rms(chunk)

            if level < thresh:
                if not in_silence:
                    in_silence = True
                    sil_start  = i / sr
            else:
                if in_silence:
                    sil_end = i / sr
                    dur = sil_end - sil_start
                    if dur >= min_dur:
                        regions.append({'start': sil_start, 'end': sil_end, 'duration': dur})
                    in_silence = False

        if in_silence:
            sil_end = len(samples) / sr
            dur = sil_end - sil_start
            if dur >= min_dur:
                regions.append({'start': sil_start, 'end': sil_end, 'duration': dur})

        return regions

    def find_long_pauses(self, samples: list, sr: int) -> List[Dict]:
        """Return silence regions longer than max_pause_duration."""
        max_pause = self.settings.get('max_pause_duration', 1.0)
        all_silences = self.find_silence_regions(samples, sr)
        return [r for r in all_silences if r['duration'] > max_pause]

    # ── Stutter Detection ──────────────────────────────────────────

    def detect_stutters(self, samples: list, sr: int) -> List[Dict]:
        """
        Detect likely stutters by finding clusters of micro-silence gaps
        whose intervening voiced bursts have similar energy (repetition).

        Algorithm:
         1. Classify 20 ms frames as voiced / silent.
         2. Extract micro-silence gaps (50–200 ms each).
         3. Merge gaps separated by noise-level bursts (< 40 ms).
         4. Cluster gaps separated by short voiced bursts (< 300 ms)
            within the stutter_window.
         5. Reject clusters where the voiced bursts between gaps have
            dissimilar energy — real stutters repeat the same sound so
            burst energies are similar; natural speech varies.
         6. Nearby detections within 0.25 s are merged.
        """
        window_sec  = self.settings.get('stutter_window', 0.8)
        frame_sec   = 0.02          # 20 ms frames
        frame_size  = int(sr * frame_sec)

        if frame_size < 1:
            return []

        silence_thresh = db_to_linear(self.settings.get('silence_threshold_db', -40))

        # ── step 1: per-frame energy + voiced flag ───────────────────
        frame_energy: list[float] = []
        for i in range(0, len(samples) - frame_size, frame_size):
            frame_energy.append(rms(samples[i: i + frame_size]))

        # ── step 2: extract micro-silence gaps (50–200 ms) ──────────
        raw_gaps: list[dict] = []
        in_gap = False
        gap_start = 0
        for idx, e in enumerate(frame_energy):
            if e <= silence_thresh:
                if not in_gap:
                    in_gap = True
                    gap_start = idx
            else:
                if in_gap:
                    gap_dur = (idx - gap_start) * frame_sec
                    if 0.05 <= gap_dur <= 0.20:
                        raw_gaps.append({
                            'start': gap_start * frame_sec,
                            'end':   idx * frame_sec,
                        })
                    in_gap = False

        # ── step 3: merge gaps separated by noise bursts (< 40 ms) ──
        gaps: list[dict] = []
        for g in raw_gaps:
            if gaps and (g['start'] - gaps[-1]['end']) < 0.04:
                gaps[-1] = {'start': gaps[-1]['start'], 'end': g['end']}
            else:
                gaps.append(dict(g))
        # re-filter after merge
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
                # Real stutters have evenly-timed gaps; natural word
                # boundaries are irregular.  Reject if max/min > 1.5.
                gap_durs = [g['end'] - g['start'] for g in cluster]
                gap_ratio = max(gap_durs) / (min(gap_durs) + 1e-12)
                if gap_ratio > 1.5:
                    i = j
                    continue

                # ── step 5b: burst energy analysis ───────────────────
                burst_energies: list[float] = []
                for k in range(len(cluster) - 1):
                    b_start = cluster[k]['end']
                    b_end   = cluster[k + 1]['start']
                    fi = int(b_start / frame_sec)
                    fj = int(b_end   / frame_sec)
                    if fi < fj:
                        burst_energies.append(
                            sum(frame_energy[fi:fj]) / (fj - fi))

                is_stutter = True
                if len(burst_energies) >= 2:
                    # Multiple bursts: check energy similarity (CV).
                    be_mean = sum(burst_energies) / len(burst_energies)
                    be_var  = (sum((e - be_mean) ** 2
                                   for e in burst_energies)
                               / len(burst_energies))
                    be_cv   = math.sqrt(be_var) / (be_mean + 1e-12)
                    if be_cv > 0.40:
                        is_stutter = False
                elif len(burst_energies) == 1:
                    # Single burst (2-gap cluster): require a clear
                    # on-off contrast — burst must be well above
                    # the silence floor.  Natural speech micro-pauses
                    # often have barely-above-threshold bursts.
                    if burst_energies[0] < silence_thresh * 5:
                        is_stutter = False

                if is_stutter:
                    s = cluster[0]['start']
                    e = cluster[-1]['end']
                    if not stutters or (s - stutters[-1]['end']) > 0.25:
                        stutters.append({
                            'start': max(0.0, s - 0.05),
                            'end':   min(len(samples) / sr, e + 0.05),
                            'desc':  'Possible stutter / repeated sound',
                        })
                i = j
            else:
                i += 1

        return stutters

    # ── Unclear Audio Detection ────────────────────────────────────

    def detect_unclear(self, samples: list, sr: int) -> List[Dict]:
        """
        Flag sections where audio energy is in the "mumble zone" —
        audible but significantly below average speech level.
        """
        thresh_db   = self.settings.get('silence_threshold_db', -40)
        frame_sec   = 0.1
        frame_size  = int(sr * frame_sec)
        thresh      = db_to_linear(thresh_db)

        # Compute overall mean speech energy (excluding silence)
        speech_levels = []
        for i in range(0, len(samples) - frame_size, frame_size):
            level = rms(samples[i: i + frame_size])
            if level > thresh:
                speech_levels.append(level)

        if not speech_levels:
            return []

        mean_speech = sum(speech_levels) / len(speech_levels)
        unclear_thresh_low  = thresh * 1.2
        unclear_thresh_high = mean_speech * 0.45

        unclear = []
        in_unclear = False
        unc_start  = 0.0
        low_count  = 0

        for i in range(0, len(samples) - frame_size, frame_size):
            level = rms(samples[i: i + frame_size])
            t = i / sr

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
                        'desc':  'Audio may be too quiet or unclear — consider re-recording'
                    })
                in_unclear = False

        return unclear[:10]  # cap to avoid false-positive floods

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

        prog(0.05, "Reading audio file…")
        samples, sr = read_wav_mono(filepath)
        duration = len(samples) / sr

        prog(0.20, "Detecting silences…")
        silence_regions = self.find_silence_regions(samples, sr)

        prog(0.40, "Finding long pauses…")
        long_pauses = self.find_long_pauses(samples, sr)
        pause_edits = [
            {
                'type':  'pause',
                'start': p['start'],
                'end':   p['end'],
                'desc':  f"Long pause ({p['duration']:.1f}s) → will trim to "
                         f"{self.settings.get('max_pause_duration', 1.0):.1f}s"
            }
            for p in long_pauses
        ]

        prog(0.60, "Scanning for stutters…")
        stutters = []
        if self.settings.get('detect_stutters', True):
            stutters = self.detect_stutters(samples, sr)
            for s in stutters:
                s['type'] = 'stutter'

        prog(0.78, "Checking for unclear sections…")
        unclear = []
        if self.settings.get('detect_unclear', True):
            unclear = self.detect_unclear(samples, sr)
            for u in unclear:
                u['type'] = 'unclear'

        prog(0.90, "Computing statistics…")

        max_pause = self.settings.get('max_pause_duration', 1.0)
        time_saved = sum(max(0.0, p['duration'] - max_pause) for p in long_pauses)
        all_edits = pause_edits + stutters + unclear

        prog(1.0, "Analysis complete")

        return {
            'filepath':   filepath,
            'samples':    samples,
            'sample_rate': sr,
            'duration':   duration,
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
            }
        }


# ── Output: Cleaned WAV ───────────────────────────────────────────────────────

def build_cleaned_wav(results: dict, settings: dict, out_path: str):
    """
    Write a cleaned WAV with long pauses trimmed.
    Does NOT modify levels, noise, or anything else.
    """
    samples = results['samples']
    sr      = results['sample_rate']
    pauses  = sorted(results['long_pauses'], key=lambda x: x['start'])
    max_pause = settings.get('max_pause_duration', 1.0)

    out_samples = []
    cursor = 0

    for p in pauses:
        p_start = int(p['start'] * sr)
        p_end   = int(p['end']   * sr)
        trim_end = p_start + int(max_pause * sr)

        out_samples.extend(samples[cursor: p_start])   # keep audio before
        out_samples.extend(samples[p_start: trim_end]) # keep trimmed pause
        cursor = p_end

    out_samples.extend(samples[cursor:])  # keep remainder
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
