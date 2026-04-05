"""
Before / after comparison for the stutter detection fix.

Test A — Real speech WAV (should have ~0 false-positive stutters)
Test B — Synthetic WAV with intentional stutters + long pause
"""

import sys, os, struct, wave, math, tempfile, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TMP = tempfile.gettempdir()
REAL_RAW   = os.path.join(TMP, "osr_raw.wav")
REAL_WAV   = os.path.join(TMP, "osr_44100.wav")
SYNTH_WAV  = os.path.join(TMP, "stutter_synth.wav")

SR = 44100

# ── helpers ──────────────────────────────────────────────────────────

def download_and_convert():
    """Download the real speech WAV, convert 8 kHz → 44100 Hz."""
    URL = ("https://www.voiptroubleshooter.com/open_speech/"
           "american/OSR_us_000_0010_8k.wav")
    print(f"  Downloading {URL} ...")
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=30) as resp, \
         open(REAL_RAW, "wb") as f:
        f.write(resp.read())

    with wave.open(REAL_RAW, "rb") as src:
        sw = src.getsampwidth()
        src_rate = src.getframerate()
        n_frames = src.getnframes()
        raw = src.readframes(n_frames)

    samples_raw = list(struct.unpack(f"<{len(raw) // sw}h", raw))

    # linear-interpolation resample → 44100
    ratio = src_rate / SR
    n_out = int(len(samples_raw) / ratio)
    resampled = []
    for i in range(n_out):
        pos = i * ratio
        idx = int(pos)
        frac = pos - idx
        s0 = samples_raw[min(idx, len(samples_raw) - 1)]
        s1 = samples_raw[min(idx + 1, len(samples_raw) - 1)]
        resampled.append(max(-32768, min(32767, int(s0 + (s1 - s0) * frac))))

    with wave.open(REAL_WAV, "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(SR)
        dst.writeframes(struct.pack(f"<{len(resampled)}h", *resampled))
    print(f"  Converted → {REAL_WAV}  "
          f"({len(resampled)} frames, {len(resampled)/SR:.1f}s)")


def make_synth_wav():
    """
    10-second synthetic WAV with two intentional stutter regions
    and one long pause.

    Timeline:
      0.0 – 2.0  clean tone (200 Hz)
      2.0 – 2.1  silence   ┐
      2.1 – 2.3  tone      │ stutter pattern 1
      2.3 – 2.4  silence   │
      2.4 – 2.6  tone      ┘
      2.6 – 4.0  clean tone
      4.0 – 6.5  silence   ← long pause (2.5 s)
      6.5 – 8.0  clean tone
      8.0 – 8.1  silence   ┐
      8.1 – 8.2  tone      │ stutter pattern 2
      8.2 – 8.3  silence   │
      8.3 – 8.4  tone      ┘
      8.4 –10.0  clean tone
    """
    dur = 10.0
    freq = 200.0
    n = int(dur * SR)
    samples = []

    # intervals where audio is a tone (everything else is silence)
    tone_intervals = [
        (0.0, 2.0), (2.1, 2.3), (2.4, 2.6), (2.6, 4.0),
        (6.5, 8.0), (8.1, 8.2), (8.3, 8.4), (8.4, 10.0),
    ]

    for i in range(n):
        t = i / SR
        is_tone = any(lo <= t < hi for lo, hi in tone_intervals)
        if is_tone:
            val = math.sin(2 * math.pi * freq * t) * 0.6
        else:
            val = 0.0
        samples.append(int(val * 32767))

    with wave.open(SYNTH_WAV, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    print(f"  Generated → {SYNTH_WAV}  ({len(samples)} frames, {dur}s)")


# ── OLD algorithm (copy-pasted from original code) ───────────────────

def detect_stutters_OLD(analyzer, samples, sr):
    """The original algorithm before the fix (for comparison)."""
    window_sec  = analyzer.settings.get('stutter_window', 0.8)
    frame_sec   = 0.04
    frame_size  = int(sr * frame_sec)
    hop_size    = frame_size // 2

    from core.analyzer import rms, db_to_linear

    frames = []
    for i in range(0, len(samples) - frame_size, hop_size):
        chunk = samples[i: i + frame_size]
        frames.append({'t': i / sr, 'e': rms(chunk)})

    lookback = max(1, int(window_sec / frame_sec))
    stutters = []
    MIN_ENERGY = db_to_linear(-50)

    for i in range(lookback, len(frames) - 2):
        if frames[i]['e'] < MIN_ENERGY:
            continue
        matches = 0
        for k in range(1, min(6, lookback) + 1):
            prev = frames[i - k]['e']
            curr = frames[i]['e']
            avg  = (prev + curr) / 2.0 + 1e-12
            if abs(prev - curr) / avg < 0.12:       # OLD threshold
                matches += 1
        if matches >= 4:                             # OLD count
            t = frames[i]['t']
            if not stutters or (t - stutters[-1]['end']) > 0.4:  # OLD gap
                stutters.append({
                    'start': max(0.0, t - 0.15),
                    'end':   min(len(samples) / sr, t + 0.35),
                    'desc':  'Possible stutter / repeated sound'
                })
    return stutters


# ── run analysis with both algorithms ────────────────────────────────

def run_comparison(label, wav_path):
    from core.settings import SettingsManager
    from core.analyzer import AudioAnalyzer, read_wav_mono

    sm = SettingsManager()
    settings = sm.analysis_settings()
    analyzer = AudioAnalyzer(settings)

    samples, sr = read_wav_mono(wav_path)

    old_stutters = detect_stutters_OLD(analyzer, samples, sr)
    new_results  = analyzer.analyze(wav_path)

    new_stutters = new_results['stutters']
    stats = new_results['stats']

    print(f"\n{'=' * 65}")
    print(f"  {label}")
    print(f"  File: {wav_path}")
    print(f"  Duration: {new_results['duration']:.2f}s")
    print(f"{'=' * 65}")
    print(f"\n  STUTTER COMPARISON:")
    print(f"    OLD algorithm : {len(old_stutters)} stutters")
    print(f"    NEW algorithm : {len(new_stutters)} stutters")
    delta = len(old_stutters) - len(new_stutters)
    if delta > 0:
        print(f"    Reduction     : {delta} fewer  ({delta/max(1,len(old_stutters))*100:.0f}% drop)")
    elif delta < 0:
        print(f"    Increase      : {-delta} more")
    else:
        print(f"    No change")

    print(f"\n  FULL NEW RESULTS:")
    print(f"    Pause count   : {stats['pause_count']}")
    print(f"    Stutter count : {stats['stutter_count']}")
    print(f"    Unclear count : {stats['unclear_count']}")
    print(f"    Time saved    : {stats['time_saved']:.2f}s")

    if new_results['all_edits']:
        print(f"\n  ALL EDITS ({len(new_results['all_edits'])}):")
        for i, e in enumerate(new_results['all_edits']):
            print(f"    {i+1:2d}. [{e['type']:>7s}]  "
                  f"{e['start']:6.2f} – {e['end']:6.2f}s  {e['desc']}")
    else:
        print(f"\n  ALL EDITS: (none)")


# ── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("  STUTTER FIX — Before / After Comparison")
    print("=" * 65)

    print("\n[Prep] Downloading & converting real speech WAV ...")
    download_and_convert()

    print("\n[Prep] Generating synthetic stutter WAV ...")
    make_synth_wav()

    run_comparison("TEST A — Real Speech (goal: ~0 false positives)", REAL_WAV)
    run_comparison("TEST B — Synthetic Stutters + Long Pause", SYNTH_WAV)

    print(f"\n{'=' * 65}")
    print("  DONE")
    print("=" * 65)
