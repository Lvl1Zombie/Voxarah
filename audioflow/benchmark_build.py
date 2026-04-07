"""
Voxarah Acoustic Benchmark Builder
===================================
Downloads public-domain LibriVox narration, extracts acoustic features,
computes real benchmark ranges, and compares them to the hardcoded profiles.

Phases:
  1. Download & convert LibriVox samples
  2. Extract acoustic features from each
  3. Compute benchmark ranges with padding
  4. Compare to current hardcoded profiles
  5. Test old vs new scoring on held-out samples
"""

import sys, os, math, wave, struct, subprocess, tempfile, urllib.request, textwrap, zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── paths ────────────────────────────────────────────────────────────
ROOT     = os.path.dirname(os.path.abspath(__file__))
SAMPLES  = os.path.join(ROOT, "samples")
FFMPEG   = os.path.join(SAMPLES, "ffmpeg.exe")
sys.path.insert(0, ROOT)

from core.analyzer import AudioAnalyzer, rms, db_to_linear, read_wav_mono
from core.settings import SettingsManager, DEFAULTS
from coaching.profiles import VOICE_PROFILES, score_recording, get_all_profiles

# ── download helpers ─────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
}

def download(url: str, dest: str) -> bool:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        print(f"    [cached] {os.path.basename(dest)}")
        return True
    try:
        print(f"    Downloading {os.path.basename(dest)} ...")
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"    -> {len(data)/1024:.0f} KB")
        return True
    except Exception as e:
        print(f"    FAILED: {e}")
        return False


def mp3_to_wav(mp3: str, wav: str) -> bool:
    """Convert MP3 to 16-bit mono 44100 Hz WAV using ffmpeg."""
    if os.path.exists(wav) and os.path.getsize(wav) > 10_000:
        print(f"    [cached] {os.path.basename(wav)}")
        return True
    try:
        subprocess.run(
            [FFMPEG, "-y", "-i", mp3, "-ac", "1", "-ar", "44100",
             "-sample_fmt", "s16", wav],
            check=True, capture_output=True, timeout=120,
        )
        print(f"    -> {os.path.basename(wav)}  "
              f"({os.path.getsize(wav)/1024/1024:.1f} MB)")
        return True
    except Exception as e:
        print(f"    CONVERSION FAILED: {e}")
        return False


# ── feature extraction ───────────────────────────────────────────────
def extract_features(wav_path: str, label: str, max_seconds: float = 120.0) -> dict:
    """
    Extract acoustic features from a WAV file.
    Caps analysis at max_seconds to keep runtime manageable.
    """
    print(f"\n  Extracting features: {label}")
    samples, sr = read_wav_mono(wav_path)
    duration_full = len(samples) / sr
    # cap to max_seconds
    cap = int(min(len(samples), max_seconds * sr))
    samples = samples[:cap]
    duration = cap / sr
    print(f"    Full duration: {duration_full:.1f}s  |  Analyzing first {duration:.1f}s")

    sm = SettingsManager()
    settings = sm.analysis_settings()
    analyzer = AudioAnalyzer(settings)

    # Run core analysis on the capped samples by writing a temp WAV
    tmp_wav = os.path.join(tempfile.gettempdir(), "bench_tmp.wav")
    from core.analyzer import write_wav_mono
    write_wav_mono(tmp_wav, samples, sr)
    results = analyzer.analyze(tmp_wav)

    silence_regions = results["silence_regions"]
    stats = results["stats"]

    # --- pause_ratio ---
    total_silence = sum(r["end"] - r["start"] for r in silence_regions)
    pause_ratio = total_silence / max(1.0, duration)

    # --- speech_rate_wpm (estimate) ---
    # Count voiced segments separated by silences.  Each segment is roughly
    # a "breath group" of a few words.  We estimate WPM as:
    #   voiced_duration / average_word_duration(0.4s) / total_minutes
    voiced_duration = duration - total_silence
    estimated_words = voiced_duration / 0.4  # avg word ~0.4s in narration
    speech_rate_wpm = estimated_words / (duration / 60.0)

    # --- energy per 100ms frame (voiced only) ---
    frame_sec = 0.1
    frame_size = int(sr * frame_sec)
    silence_thresh = db_to_linear(settings.get("silence_threshold_db", -40))

    voiced_energies = []
    all_energies_db = []
    for i in range(0, len(samples) - frame_size, frame_size):
        chunk = samples[i : i + frame_size]
        e = rms(chunk)
        if e > 1e-10:
            all_energies_db.append(20 * math.log10(e + 1e-12))
        if e > silence_thresh:
            voiced_energies.append(e)

    # --- energy_consistency ---
    if len(voiced_energies) > 4:
        ve_mean = sum(voiced_energies) / len(voiced_energies)
        ve_var = sum((x - ve_mean) ** 2 for x in voiced_energies) / len(voiced_energies)
        ve_cv = math.sqrt(ve_var) / (ve_mean + 1e-12)
        energy_consistency = max(0.0, 1.0 - min(1.0, ve_cv * 1.5))
    else:
        energy_consistency = 0.5

    # --- dynamic_range_db ---
    if len(all_energies_db) > 10:
        all_energies_db.sort()
        p5 = all_energies_db[int(len(all_energies_db) * 0.05)]
        p95 = all_energies_db[int(len(all_energies_db) * 0.95)]
        dynamic_range_db = p95 - p5
    else:
        dynamic_range_db = 0.0

    # --- max_long_pause_sec ---
    if silence_regions:
        max_long_pause = max(r["duration"] for r in silence_regions)
    else:
        max_long_pause = 0.0

    # --- clarity_floor_db ---
    if len(voiced_energies) > 10:
        voiced_energies_sorted = sorted(voiced_energies)
        p10 = voiced_energies_sorted[int(len(voiced_energies_sorted) * 0.10)]
        clarity_floor_db = 20 * math.log10(p10 + 1e-12)
    else:
        clarity_floor_db = -40.0

    feats = {
        "label": label,
        "duration_analyzed": duration,
        "speech_rate_wpm": speech_rate_wpm,
        "pause_ratio": pause_ratio,
        "energy_consistency": energy_consistency,
        "dynamic_range_db": dynamic_range_db,
        "max_long_pause_sec": max_long_pause,
        "clarity_floor_db": clarity_floor_db,
        "stutter_count": stats["stutter_count"],
        "unclear_count": stats["unclear_count"],
    }

    # also store the raw results for scoring later
    feats["_results"] = results

    return feats


# ── pretty print helpers ─────────────────────────────────────────────
def hline(w=75):
    print("-" * w)

def print_features_table(all_feats: list[dict]):
    keys = [
        ("speech_rate_wpm",    "Speech Rate (WPM)", "{:.1f}"),
        ("pause_ratio",        "Pause Ratio",       "{:.3f}"),
        ("energy_consistency", "Energy Consistency", "{:.3f}"),
        ("dynamic_range_db",   "Dynamic Range (dB)", "{:.1f}"),
        ("max_long_pause_sec", "Max Pause (s)",     "{:.2f}"),
        ("clarity_floor_db",   "Clarity Floor (dB)", "{:.1f}"),
        ("stutter_count",      "Stutters",          "{:.0f}"),
        ("unclear_count",      "Unclear Sections",  "{:.0f}"),
    ]
    labels = [f["label"][:18] for f in all_feats]
    col_w = max(14, max(len(l) for l in labels) + 2)

    header = f"  {'Feature':<24s}" + "".join(f"{l:>{col_w}s}" for l in labels)
    print(header)
    hline(len(header))
    for key, name, fmt in keys:
        row = f"  {name:<24s}"
        for f in all_feats:
            row += f"{fmt.format(f[key]):>{col_w}s}"
        print(row)
    hline(len(header))


# ── Phase 3: compute benchmark ranges ───────────────────────────────
def compute_ranges(all_feats: list[dict]) -> dict:
    """
    For each feature, take min*0.85 .. max*1.15 across samples.
    Returns dict with same keys as VOICE_PROFILES benchmarks.
    """
    def padded(vals, lo_factor=0.85, hi_factor=1.15):
        lo = min(vals) * lo_factor
        hi = max(vals) * hi_factor
        return (lo, hi)

    rates = [f["speech_rate_wpm"] for f in all_feats]
    pauses = [f["pause_ratio"] for f in all_feats]
    consistencies = [f["energy_consistency"] for f in all_feats]
    dyn_ranges = [f["dynamic_range_db"] for f in all_feats]
    max_pauses = [f["max_long_pause_sec"] for f in all_feats]
    clarity_floors = [f["clarity_floor_db"] for f in all_feats]

    return {
        "speech_rate_wpm":     (round(min(rates) * 0.85, 1),
                                round(max(rates) * 1.15, 1)),
        "pause_ratio":         (round(min(pauses) * 0.85, 3),
                                round(max(pauses) * 1.15, 3)),
        "energy_consistency":  (round(min(consistencies) * 0.85, 3),
                                round(max(consistencies) * 1.15, 3)),
        "dynamic_range_db":    (round(min(dyn_ranges) * 0.85, 1),
                                round(max(dyn_ranges) * 1.15, 1)),
        "max_long_pause_sec":  round(max(max_pauses) * 1.15, 2),
        "clarity_floor_db":    round(min(clarity_floors) * 1.15, 1),
        # keep generous stutter tolerance for narration
        "stutter_tolerance":   0.005,
    }


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    os.makedirs(SAMPLES, exist_ok=True)

    # Download ffmpeg if not present
    if not os.path.exists(FFMPEG):
        print("  Downloading ffmpeg...")
        ffmpeg_zip = os.path.join(SAMPLES, "ffmpeg.zip")
        if download("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", ffmpeg_zip):
            try:
                with zipfile.ZipFile(ffmpeg_zip, 'r') as zip_ref:
                    # Extract ffmpeg.exe from the bin folder
                    for file in zip_ref.namelist():
                        if file.endswith('bin/ffmpeg.exe'):
                            zip_ref.extract(file, SAMPLES)
                            extracted_path = os.path.join(SAMPLES, file)
                            os.rename(extracted_path, FFMPEG)
                            # Remove the extracted folder
                            import shutil
                            shutil.rmtree(os.path.dirname(extracted_path))
                            break
                os.remove(ffmpeg_zip)
                print("  ffmpeg downloaded successfully.")
            except Exception as e:
                print(f"  Failed to extract ffmpeg: {e}")
        else:
            print("  Failed to download ffmpeg. Please download manually to samples/ffmpeg.exe")

    print("=" * 75)
    print("  VOXARAH ACOUSTIC BENCHMARK BUILDER")
    print("=" * 75)

    # ── PHASE 1: Download ────────────────────────────────────────────
    print("\n" + "=" * 75)
    print("  PHASE 1 — Download Public Domain Voice Samples")
    print("=" * 75)

    CALIBRATION_SOURCES = [
        ("artofwar",
         "https://archive.org/download/art_of_war_librivox/"
         "art_of_war_01-02_sun_tzu.mp3"),
        ("janeeyre",
         "https://archive.org/download/jane_eyre_ver03_0809_librivox/"
         "janeeyre_01_bronte.mp3"),
        ("alice",
         "https://archive.org/download/alice_in_wonderland_librivox/"
         "wonderland_ch_01.mp3"),
    ]

    # extra test sample (NOT used for calibration)
    TEST_PRO_SOURCE = (
        "janeeyre2",
        "https://archive.org/download/jane_eyre_ver03_0809_librivox/"
        "janeeyre_02_bronte.mp3",
    )

    AMATEUR_URL = ("https://www.voiptroubleshooter.com/open_speech/"
                   "american/OSR_us_000_0010_8k.wav")

    downloaded_wavs = []

    for name, url in CALIBRATION_SOURCES:
        mp3_path = os.path.join(SAMPLES, f"{name}.mp3")
        wav_path = os.path.join(SAMPLES, f"{name}.wav")
        ok = download(url, mp3_path)
        if ok:
            ok = mp3_to_wav(mp3_path, wav_path)
        if ok:
            downloaded_wavs.append((name, wav_path))

    print(f"\n  Successfully prepared {len(downloaded_wavs)}/{len(CALIBRATION_SOURCES)}"
          f" calibration samples")

    if len(downloaded_wavs) < 2:
        print("  ERROR: Need at least 2 calibration samples. Aborting.")
        sys.exit(1)

    # ── PHASE 2: Extract features ────────────────────────────────────
    print("\n" + "=" * 75)
    print("  PHASE 2 — Extract Acoustic Features")
    print("=" * 75)

    all_feats = []
    for name, wav_path in downloaded_wavs:
        feats = extract_features(wav_path, name, max_seconds=120.0)
        all_feats.append(feats)

    print("\n  Feature Table (calibration samples):\n")
    print_features_table(all_feats)

    # ── PHASE 3: Compute benchmark ranges ────────────────────────────
    print("\n" + "=" * 75)
    print("  PHASE 3 — Compute Benchmark Ranges")
    print("=" * 75)

    measured = compute_ranges(all_feats)

    print(f"\n  {'Feature':<26s}  {'Low':>10s}  {'High':>10s}")
    hline(52)
    for key in ["speech_rate_wpm", "pause_ratio", "energy_consistency",
                "dynamic_range_db"]:
        lo, hi = measured[key]
        print(f"  {key:<26s}  {lo:>10.2f}  {hi:>10.2f}")
    print(f"  {'max_long_pause_sec':<26s}  {'—':>10s}  {measured['max_long_pause_sec']:>10.2f}")
    print(f"  {'clarity_floor_db':<26s}  {measured['clarity_floor_db']:>10.1f}  {'—':>10s}")
    print(f"  {'stutter_tolerance':<26s}  {'—':>10s}  {measured['stutter_tolerance']:>10.3f}")
    hline(52)

    # ── PHASE 4: Compare to hardcoded ────────────────────────────────
    print("\n" + "=" * 75)
    print("  PHASE 4 — Compare Measured vs Hardcoded Benchmarks")
    print("=" * 75)

    for profile_name in ["Narrator / Documentary", "Audiobook"]:
        hc = VOICE_PROFILES[profile_name]
        print(f"\n  Profile: {profile_name}")
        print(f"  {'Feature':<26s}  {'Hardcoded':>18s}  {'Measured':>18s}  {'Delta':>12s}")
        hline(78)

        for key in ["speech_rate_wpm", "pause_ratio", "energy_consistency",
                     "dynamic_range_db"]:
            hc_lo, hc_hi = hc[key]
            ms_lo, ms_hi = measured[key]
            d_lo = ms_lo - hc_lo
            d_hi = ms_hi - hc_hi
            hc_str = f"{hc_lo:.2f} – {hc_hi:.2f}"
            ms_str = f"{ms_lo:.2f} – {ms_hi:.2f}"
            d_str = f"{d_lo:+.2f} / {d_hi:+.2f}"
            print(f"  {key:<26s}  {hc_str:>18s}  {ms_str:>18s}  {d_str:>12s}")

        # scalar features
        hc_max_pause = hc["max_long_pause_sec"]
        ms_max_pause = measured["max_long_pause_sec"]
        d_mp = ms_max_pause - hc_max_pause
        print(f"  {'max_long_pause_sec':<26s}  {'<= ' + str(hc_max_pause):>18s}  "
              f"{'<= ' + f'{ms_max_pause:.2f}':>18s}  {d_mp:>+12.2f}")

        hc_cf = hc["clarity_floor_db"]
        ms_cf = measured["clarity_floor_db"]
        d_cf = ms_cf - hc_cf
        print(f"  {'clarity_floor_db':<26s}  {'>= ' + str(hc_cf):>18s}  "
              f"{'>= ' + f'{ms_cf:.1f}':>18s}  {d_cf:>+12.1f}")

        hc_st = hc["stutter_tolerance"]
        ms_st = measured["stutter_tolerance"]
        print(f"  {'stutter_tolerance':<26s}  {'<= ' + str(hc_st):>18s}  "
              f"{'<= ' + str(ms_st):>18s}  {'same':>12s}")

        hline(78)

    # ── Write measured_benchmarks.py ─────────────────────────────────
    print("\n  Writing coaching/measured_benchmarks.py ...")

    sample_names = ", ".join(f["label"] for f in all_feats)
    mb_content = f'''"""
Voxarah — Measured Acoustic Benchmarks
========================================
Auto-generated by benchmark_build.py from real LibriVox narration samples.

Calibration samples: {sample_names}
Each benchmark range is min(samples)*0.85 .. max(samples)*1.15.

These provide realistic targets derived from actual professional
public-domain audiobook/narration recordings.
"""

from typing import Dict, List


MEASURED_PROFILES = {{
    "Narrator / Documentary": {{
        "description": "Authoritative, clear, even-paced. Benchmarked from LibriVox narration.",
        "emoji": "🎬",
        "speech_rate_wpm":     ({measured['speech_rate_wpm'][0]:.1f}, {measured['speech_rate_wpm'][1]:.1f}),
        "pause_ratio":         ({measured['pause_ratio'][0]:.3f}, {measured['pause_ratio'][1]:.3f}),
        "energy_consistency":  ({measured['energy_consistency'][0]:.3f}, {measured['energy_consistency'][1]:.3f}),
        "dynamic_range_db":    ({measured['dynamic_range_db'][0]:.1f}, {measured['dynamic_range_db'][1]:.1f}),
        "max_long_pause_sec":  {measured['max_long_pause_sec']:.2f},
        "stutter_tolerance":   {measured['stutter_tolerance']},
        "clarity_floor_db":    {measured['clarity_floor_db']:.1f},
        "tips": [
            "Narration tolerates zero stutters — re-record any hesitations.",
            "Consistency is king: listeners trust a steady, reliable voice.",
            "Emphasize subject words; verbs and prepositions can stay soft.",
        ],
        "calibration_samples": {[f['label'] for f in all_feats]!r},
        "calibration_features": {{
'''
    for f in all_feats:
        mb_content += f'            "{f["label"]}": {{\n'
        for k in ["speech_rate_wpm", "pause_ratio", "energy_consistency",
                   "dynamic_range_db", "max_long_pause_sec", "clarity_floor_db"]:
            mb_content += f'                "{k}": {f[k]:.3f},\n'
        mb_content += f'            }},\n'
    mb_content += f'''        }},
    }},
    "Audiobook": {{
        "description": "Clear, warm, immersive. Benchmarked from LibriVox audiobook chapters.",
        "emoji": "📚",
        "speech_rate_wpm":     ({measured['speech_rate_wpm'][0]:.1f}, {measured['speech_rate_wpm'][1]:.1f}),
        "pause_ratio":         ({measured['pause_ratio'][0]:.3f}, {measured['pause_ratio'][1]:.3f}),
        "energy_consistency":  ({measured['energy_consistency'][0]:.3f}, {measured['energy_consistency'][1]:.3f}),
        "dynamic_range_db":    ({measured['dynamic_range_db'][0]:.1f}, {measured['dynamic_range_db'][1]:.1f}),
        "max_long_pause_sec":  {measured['max_long_pause_sec']:.2f},
        "stutter_tolerance":   0.003,
        "clarity_floor_db":    {measured['clarity_floor_db']:.1f},
        "tips": [
            "Consistency over hours is the hardest part — record in short sessions.",
            "Chapter breaks and paragraph pauses are separate from 'long pauses' — plan them.",
            "Any stutter breaks the listener's immersion; these all need re-records.",
        ],
        "calibration_samples": {[f['label'] for f in all_feats]!r},
    }},
}}


def get_measured_profile(name: str) -> Dict:
    """Return measured benchmark dict for a profile name, or empty dict."""
    return MEASURED_PROFILES.get(name, {{}})


def get_all_measured_profiles() -> List[str]:
    """Return list of measured profile names."""
    return list(MEASURED_PROFILES.keys())
'''

    mb_path = os.path.join(ROOT, "coaching", "measured_benchmarks.py")
    with open(mb_path, "w", encoding="utf-8") as f:
        f.write(mb_content)
    print(f"  Written: {mb_path}")

    # ── PHASE 5: Test old vs new ─────────────────────────────────────
    print("\n" + "=" * 75)
    print("  PHASE 5 — Test Old vs New Scoring")
    print("=" * 75)

    # Import the scoring function — we'll create a custom scorer
    # that uses MEASURED_PROFILES instead of VOICE_PROFILES
    from coaching.profiles import _range_score, _grade

    def score_with_benchmarks(results: dict, profile_name: str,
                               profiles_dict: dict) -> dict:
        """Score using an arbitrary profiles dict (old or measured)."""
        profile = profiles_dict[profile_name]
        samples  = results['samples']
        sr       = results['sample_rate']
        duration = results['duration']
        stats    = results['stats']
        silence_regions = results['silence_regions']

        scores = {}
        # 1. Pause Ratio
        total_silence = sum(r['end'] - r['start'] for r in silence_regions)
        pause_ratio   = total_silence / max(1.0, duration)
        lo, hi = profile['pause_ratio']
        scores['pause_ratio'] = _range_score(pause_ratio, lo, hi)

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
            scores['consistency'] = _range_score(consistency, lo, hi)
        else:
            scores['consistency'] = 70

        # 5. Clarity
        unclear_count = stats['unclear_count']
        unclear_frac  = unclear_count / max(1.0, duration / 10.0)
        scores['clarity'] = max(0, int(100 - unclear_frac * 40))

        weights = {'pause_ratio': 0.25, 'stutters': 0.30, 'pause_length': 0.20,
                   'consistency': 0.15, 'clarity': 0.10}
        overall = int(sum(scores[k] * weights[k] for k in weights))

        return {
            'profile': profile_name,
            'overall': overall,
            'scores': scores,
            'grade': _grade(overall),
        }

    # 5a. Download held-out pro sample
    print("\n  Downloading held-out pro sample (Pride & Prejudice) ...")
    pro_name, pro_url = TEST_PRO_SOURCE
    pro_mp3 = os.path.join(SAMPLES, f"{pro_name}.mp3")
    pro_wav = os.path.join(SAMPLES, f"{pro_name}.wav")
    download(pro_url, pro_mp3)
    mp3_to_wav(pro_mp3, pro_wav)

    # 5b. Download amateur sample
    print("\n  Downloading amateur sample (OSR open speech) ...")
    amateur_raw = os.path.join(SAMPLES, "amateur_raw.wav")
    amateur_wav = os.path.join(SAMPLES, "amateur.wav")
    download(AMATEUR_URL, amateur_raw)
    # Convert 8kHz -> 44100Hz
    if not (os.path.exists(amateur_wav) and os.path.getsize(amateur_wav) > 10_000):
        subprocess.run(
            [FFMPEG, "-y", "-i", amateur_raw, "-ac", "1", "-ar", "44100",
             "-sample_fmt", "s16", amateur_wav],
            check=True, capture_output=True, timeout=60,
        )
    print(f"    -> {os.path.basename(amateur_wav)}")

    # 5c. Extract features and run both scorers
    pro_feats = extract_features(pro_wav, "pride (pro, held-out)", max_seconds=120.0)
    amateur_feats = extract_features(amateur_wav, "amateur (OSR)", max_seconds=60.0)

    # load MEASURED_PROFILES
    from coaching.measured_benchmarks import MEASURED_PROFILES

    test_samples = [
        ("Pro (Pride & Prejudice)", pro_feats),
        ("Amateur (OSR Speech)", amateur_feats),
    ]

    for profile_name in ["Narrator / Documentary", "Audiobook"]:
        print(f"\n  Profile: {profile_name}")
        print(f"  {'Sample':<30s}  {'Old Score':>10s}  {'Old Grade':>10s}  "
              f"{'New Score':>10s}  {'New Grade':>10s}  {'Delta':>8s}")
        hline(82)

        for label, feats in test_samples:
            results = feats["_results"]
            old = score_with_benchmarks(results, profile_name, VOICE_PROFILES)
            new = score_with_benchmarks(results, profile_name, MEASURED_PROFILES)
            delta = new["overall"] - old["overall"]
            sign = "+" if delta > 0 else ""
            print(f"  {label:<30s}  {old['overall']:>10d}  {old['grade']:>10s}  "
                  f"{new['overall']:>10d}  {new['grade']:>10s}  {sign}{delta:>7d}")

        hline(82)

    # 5d. Detailed per-dimension comparison for the pro sample
    print("\n  Per-dimension breakdown (Pro sample, Narrator / Documentary):")
    print(f"  {'Dimension':<18s}  {'Old':>6s}  {'New':>6s}  {'Delta':>7s}")
    hline(45)
    old_pro = score_with_benchmarks(pro_feats["_results"], "Narrator / Documentary",
                                     VOICE_PROFILES)
    new_pro = score_with_benchmarks(pro_feats["_results"], "Narrator / Documentary",
                                     MEASURED_PROFILES)
    for dim in ["pause_ratio", "stutters", "pause_length", "consistency", "clarity"]:
        o = old_pro["scores"][dim]
        n = new_pro["scores"][dim]
        d = n - o
        s = "+" if d > 0 else ""
        print(f"  {dim:<18s}  {o:>6d}  {n:>6d}  {s}{d:>6d}")
    print(f"  {'OVERALL':<18s}  {old_pro['overall']:>6d}  {new_pro['overall']:>6d}  "
          f"{'+'if new_pro['overall']-old_pro['overall']>0 else ''}"
          f"{new_pro['overall']-old_pro['overall']:>6d}")
    hline(45)

    # ── FINAL SUMMARY ────────────────────────────────────────────────
    print("\n" + "=" * 75)
    print("  FINAL SUMMARY")
    print("=" * 75)
    print(f"""
  Calibration samples : {', '.join(f['label'] for f in all_feats)}
  Test samples        : Pride & Prejudice (pro), OSR (amateur)

  Key findings:""")

    # Summarize major differences
    for key in ["speech_rate_wpm", "pause_ratio", "energy_consistency",
                "dynamic_range_db"]:
        hc = VOICE_PROFILES["Narrator / Documentary"][key]
        ms = measured[key]
        print(f"    {key}:")
        print(f"      Hardcoded: {hc[0]:.2f} – {hc[1]:.2f}")
        print(f"      Measured:  {ms[0]:.2f} – {ms[1]:.2f}")

    hc_mp = VOICE_PROFILES["Narrator / Documentary"]["max_long_pause_sec"]
    print(f"    max_long_pause_sec:")
    print(f"      Hardcoded: <= {hc_mp}")
    print(f"      Measured:  <= {measured['max_long_pause_sec']:.2f}")

    hc_cf = VOICE_PROFILES["Narrator / Documentary"]["clarity_floor_db"]
    print(f"    clarity_floor_db:")
    print(f"      Hardcoded: >= {hc_cf}")
    print(f"      Measured:  >= {measured['clarity_floor_db']:.1f}")

    print("\n" + "=" * 75)
    print("  DONE — measured_benchmarks.py written to coaching/")
    print("=" * 75)
