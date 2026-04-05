"""
Before / after scoring comparison for the realistic benchmark update.
Downloads pro narration (Art of War) and amateur speech (OSR),
scores both against all 6 profiles using OLD hardcoded and NEW measured values.
"""

import sys, os, math, struct, wave, subprocess, tempfile, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT    = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(ROOT, "samples")
FFMPEG  = os.path.join(SAMPLES, "ffmpeg.exe")
sys.path.insert(0, ROOT)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*", "Accept-Encoding": "identity",
}

def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        return True
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as f:
            f.write(r.read())
        return True
    except Exception as e:
        print(f"  DOWNLOAD FAILED: {e}")
        return False

# ── OLD profiles (hardcoded, before any changes) ────────────────────
OLD_PROFILES = {
    "Calm / Soothing": {
        "emoji": "🌙",
        "speech_rate_wpm": (100, 140), "pause_ratio": (0.20, 0.40),
        "energy_consistency": (0.70, 1.00), "dynamic_range_db": (4, 12),
        "max_long_pause_sec": 2.5, "stutter_tolerance": 0.02,
        "clarity_floor_db": -38,
    },
    "Energetic / Hype": {
        "emoji": "⚡",
        "speech_rate_wpm": (160, 210), "pause_ratio": (0.05, 0.18),
        "energy_consistency": (0.40, 0.80), "dynamic_range_db": (10, 22),
        "max_long_pause_sec": 0.6, "stutter_tolerance": 0.01,
        "clarity_floor_db": -32,
    },
    "Narrator / Documentary": {
        "emoji": "🎬",
        "speech_rate_wpm": (130, 160), "pause_ratio": (0.15, 0.30),
        "energy_consistency": (0.75, 0.95), "dynamic_range_db": (6, 14),
        "max_long_pause_sec": 1.5, "stutter_tolerance": 0.005,
        "clarity_floor_db": -36,
    },
    "Commercial / Salesy": {
        "emoji": "📣",
        "speech_rate_wpm": (140, 175), "pause_ratio": (0.10, 0.22),
        "energy_consistency": (0.60, 0.85), "dynamic_range_db": (8, 18),
        "max_long_pause_sec": 1.0, "stutter_tolerance": 0.01,
        "clarity_floor_db": -34,
    },
    "Character / Animation": {
        "emoji": "🎭",
        "speech_rate_wpm": (120, 190), "pause_ratio": (0.10, 0.30),
        "energy_consistency": (0.30, 0.75), "dynamic_range_db": (14, 28),
        "max_long_pause_sec": 1.2, "stutter_tolerance": 0.03,
        "clarity_floor_db": -35,
    },
    "Audiobook": {
        "emoji": "📚",
        "speech_rate_wpm": (140, 170), "pause_ratio": (0.15, 0.28),
        "energy_consistency": (0.80, 0.97), "dynamic_range_db": (5, 13),
        "max_long_pause_sec": 1.8, "stutter_tolerance": 0.003,
        "clarity_floor_db": -36,
    },
}

def _old_range_score(value, lo, hi):
    """OLD flat-top scorer."""
    if lo <= value <= hi:
        return 100
    elif value < lo:
        dist = (lo - value) / (lo + 1e-12)
        return max(0, int(100 - dist * 120))
    else:
        dist = (value - hi) / (hi + 1e-12)
        return max(0, int(100 - dist * 120))


def _new_range_score(value, lo, hi):
    """NEW bell-curve scorer."""
    mid = (lo + hi) / 2.0
    hw  = (hi - lo) / 2.0 + 1e-12
    z   = (value - mid) / hw
    return max(0, min(100, int(100 * math.exp(-0.5108 * z * z))))


def _grade(score):
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def score_with(results, profile_name, profiles_dict, range_fn):
    """Score a recording using the given profiles and range function."""
    profile = profiles_dict[profile_name]
    samples  = results['samples']
    sr       = results['sample_rate']
    duration = results['duration']
    stats    = results['stats']
    silence_regions = results['silence_regions']
    scores = {}

    # 1. Pause Ratio
    total_silence = sum(r['end'] - r['start'] for r in silence_regions)
    pause_ratio = total_silence / max(1.0, duration)
    lo, hi = profile['pause_ratio']
    scores['pause_ratio'] = range_fn(pause_ratio, lo, hi)

    # 2. Stutters
    tol = profile['stutter_tolerance'] * duration
    scores['stutters'] = max(0, 100 - int(stats['stutter_count'] / max(1, tol + 1) * 100))

    # 3. Pause Length
    max_allowed = profile['max_long_pause_sec']
    worst_pause = max((p['duration'] for p in results['long_pauses']), default=0.0)
    if worst_pause <= max_allowed:
        scores['pause_length'] = 100
    else:
        over = (worst_pause - max_allowed) / max_allowed
        scores['pause_length'] = max(0, int(100 - over * 80))

    # 4. Energy Consistency
    frame_size = int(sr * 0.1)
    thresh = math.pow(10, profile['clarity_floor_db'] / 20.0)
    speech_levels = []
    for i in range(0, len(samples) - frame_size, frame_size):
        chunk = samples[i: i + frame_size]
        level = math.sqrt(sum(s*s for s in chunk) / len(chunk))
        if level > thresh:
            speech_levels.append(level)
    if len(speech_levels) > 4:
        mean_e = sum(speech_levels) / len(speech_levels)
        variance = sum((x - mean_e) ** 2 for x in speech_levels) / len(speech_levels)
        cv = math.sqrt(variance) / (mean_e + 1e-12)
        consistency = max(0.0, 1.0 - min(1.0, cv * 1.5))
        lo, hi = profile['energy_consistency']
        scores['consistency'] = range_fn(consistency, lo, hi)
    else:
        scores['consistency'] = 70

    # 5. Clarity
    scores['clarity'] = max(0, int(100 - stats['unclear_count']
                                   / max(1.0, duration / 10.0) * 40))

    weights = {'pause_ratio': 0.25, 'stutters': 0.30, 'pause_length': 0.20,
               'consistency': 0.15, 'clarity': 0.10}
    overall = int(sum(scores[k] * weights[k] for k in weights))
    return {'overall': overall, 'grade': _grade(overall), 'scores': scores}


# ── main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from core.analyzer import AudioAnalyzer, write_wav_mono, read_wav_mono
    from core.settings import SettingsManager
    from coaching.profiles import VOICE_PROFILES

    print("=" * 80)
    print("  BEFORE / AFTER SCORING COMPARISON")
    print("=" * 80)

    # ── Prepare samples ──────────────────────────────────────────────
    sm = SettingsManager()
    analyzer = AudioAnalyzer(sm.analysis_settings())

    # Pro sample — Art of War ch 1-2 (first 120s)
    print("\n  Preparing PRO sample (Art of War, LibriVox) ...")
    pro_mp3 = os.path.join(SAMPLES, "artofwar.mp3")
    pro_wav = os.path.join(SAMPLES, "artofwar.wav")
    if not os.path.exists(pro_wav):
        download("https://archive.org/download/art_of_war_librivox/"
                 "art_of_war_01-02_sun_tzu.mp3", pro_mp3)
        subprocess.run([FFMPEG, "-y", "-i", pro_mp3, "-ac", "1", "-ar", "44100",
                        "-sample_fmt", "s16", pro_wav],
                       check=True, capture_output=True, timeout=120)

    # Cap at 120s
    samples_pro, sr = read_wav_mono(pro_wav)
    cap = int(min(len(samples_pro), 120 * sr))
    tmp_pro = os.path.join(tempfile.gettempdir(), "bench_pro.wav")
    write_wav_mono(tmp_pro, samples_pro[:cap], sr)
    results_pro = analyzer.analyze(tmp_pro)
    print(f"    Duration: {results_pro['duration']:.1f}s  "
          f"Stutters: {results_pro['stats']['stutter_count']}  "
          f"Unclear: {results_pro['stats']['unclear_count']}")

    # Amateur sample — OSR (full)
    print("\n  Preparing AMATEUR sample (OSR open speech) ...")
    amateur_raw = os.path.join(SAMPLES, "amateur_raw.wav")
    amateur_wav = os.path.join(SAMPLES, "amateur.wav")
    if not os.path.exists(amateur_wav):
        download("https://www.voiptroubleshooter.com/open_speech/"
                 "american/OSR_us_000_0010_8k.wav", amateur_raw)
        subprocess.run([FFMPEG, "-y", "-i", amateur_raw, "-ac", "1", "-ar", "44100",
                        "-sample_fmt", "s16", amateur_wav],
                       check=True, capture_output=True, timeout=60)
    results_am = analyzer.analyze(amateur_wav)
    print(f"    Duration: {results_am['duration']:.1f}s  "
          f"Stutters: {results_am['stats']['stutter_count']}  "
          f"Unclear: {results_am['stats']['unclear_count']}")

    # ── Score both against all profiles ──────────────────────────────
    profile_names = list(VOICE_PROFILES.keys())

    print("\n" + "=" * 80)
    print("  OVERALL SCORES — ALL PROFILES")
    print("=" * 80)
    print(f"\n  {'Profile':<28s}  {'PRO old':>8s} {'PRO new':>8s} {'delta':>6s}  "
          f"{'AM old':>8s} {'AM new':>8s} {'delta':>6s}  {'spread':>7s}")
    print("  " + "-" * 76)

    for pn in profile_names:
        po = score_with(results_pro, pn, OLD_PROFILES, _old_range_score)
        pn_ = score_with(results_pro, pn, VOICE_PROFILES, _new_range_score)
        ao = score_with(results_am, pn, OLD_PROFILES, _old_range_score)
        an_ = score_with(results_am, pn, VOICE_PROFILES, _new_range_score)

        d_pro = pn_['overall'] - po['overall']
        d_am  = an_['overall'] - ao['overall']
        spread = pn_['overall'] - an_['overall']

        print(f"  {pn:<28s}  "
              f"{po['overall']:>5d}/{po['grade']:<2s} "
              f"{pn_['overall']:>5d}/{pn_['grade']:<2s} "
              f"{d_pro:>+5d}  "
              f"{ao['overall']:>5d}/{ao['grade']:<2s} "
              f"{an_['overall']:>5d}/{an_['grade']:<2s} "
              f"{d_am:>+5d}  "
              f"{spread:>+6d}")

    # ── Detailed dimension breakdown ─────────────────────────────────
    for pn in ["Narrator / Documentary", "Audiobook"]:
        print(f"\n  Per-dimension: {pn}")
        print(f"  {'Dimension':<18s}  "
              f"{'PRO old':>8s} {'PRO new':>8s} {'d':>4s}  "
              f"{'AM old':>8s} {'AM new':>8s} {'d':>4s}")
        print("  " + "-" * 66)

        po = score_with(results_pro, pn, OLD_PROFILES, _old_range_score)
        pnew = score_with(results_pro, pn, VOICE_PROFILES, _new_range_score)
        ao = score_with(results_am, pn, OLD_PROFILES, _old_range_score)
        anew = score_with(results_am, pn, VOICE_PROFILES, _new_range_score)

        for dim in ["pause_ratio", "stutters", "pause_length", "consistency", "clarity"]:
            dp = pnew['scores'][dim] - po['scores'][dim]
            da = anew['scores'][dim] - ao['scores'][dim]
            print(f"  {dim:<18s}  "
                  f"{po['scores'][dim]:>8d} {pnew['scores'][dim]:>8d} {dp:>+4d}  "
                  f"{ao['scores'][dim]:>8d} {anew['scores'][dim]:>8d} {da:>+4d}")

        dp = pnew['overall'] - po['overall']
        da = anew['overall'] - ao['overall']
        print(f"  {'OVERALL':<18s}  "
              f"{po['overall']:>8d} {pnew['overall']:>8d} {dp:>+4d}  "
              f"{ao['overall']:>8d} {anew['overall']:>8d} {da:>+4d}")
        print("  " + "-" * 66)

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    pn_nar = score_with(results_pro, "Narrator / Documentary",
                         VOICE_PROFILES, _new_range_score)
    an_nar = score_with(results_am, "Narrator / Documentary",
                         VOICE_PROFILES, _new_range_score)
    spread = pn_nar['overall'] - an_nar['overall']

    print(f"  PRO Narrator score:    {pn_nar['overall']}/{pn_nar['grade']}")
    print(f"  Amateur Narrator score: {an_nar['overall']}/{an_nar['grade']}")
    print(f"  Spread (pro - amateur): {spread} points")

    if pn_nar['overall'] >= 80:
        print("  [OK] Pro scores B or higher on Narrator")
    else:
        print(f"  [!!] Pro scores {pn_nar['grade']} — below B target")

    if an_nar['overall'] <= 70:
        print("  [OK] Amateur scores C or below on Narrator")
    else:
        print(f"  [!!] Amateur scores {an_nar['grade']} — above C target")

    if spread >= 15:
        print(f"  [OK] Spread is {spread} points (>= 15 target)")
    else:
        print(f"  [!!] Spread is only {spread} points (< 15 target)")

    print("=" * 80)
