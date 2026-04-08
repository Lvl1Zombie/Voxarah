"""
Voxarah Profile Calibration Scraper
=====================================
Downloads LibriVox audio from archive.org for the 4 uncalibrated
voice profiles, extracts acoustic features, computes benchmark ranges,
and merges results into coaching/measured_benchmarks.py.

Profile → Content strategy:
  Calm / Soothing      → Poetry and philosophical prose (slow, even energy)
  Energetic / Hype     → Adventure fiction (fast, dynamic delivery)
  Commercial / Salesy  → Speeches and persuasive essays (confident, punchy)
  Character / Animation → Plays and multi-character fiction (expressive, varied)

Usage:
  python scrape_profiles.py                   # calibrate all 4 profiles
  python scrape_profiles.py calm energetic    # specific profiles only
  python scrape_profiles.py --list            # show available profile keys

Profile keys (any alias works):
  calm, soothing
  energetic, hype
  commercial, salesy
  character, animation
"""

import sys, os, math, json, wave, struct, subprocess, tempfile, shutil, zipfile
import urllib.request, urllib.parse, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT    = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(ROOT, "samples", "profile_calibration")
FFMPEG  = os.path.join(ROOT, "samples", "ffmpeg.exe")
sys.path.insert(0, ROOT)

import numpy as np
from core.analyzer import AudioAnalyzer, db_to_linear, read_wav_mono, write_wav_mono
from core.settings import SettingsManager


def rms(chunk) -> float:
    a = np.asarray(chunk, dtype=np.float64)
    return float(np.sqrt(np.mean(a ** 2)))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, */*",
    "Accept-Encoding": "identity",
}

# ── Profile configuration ─────────────────────────────────────────────────────
# Each entry maps a short key to:
#   profile_name   : exact name used in VOICE_PROFILES / measured_benchmarks.py
#   search_queries : archive.org queries tried in order until n_samples collected
#   curated_ids    : known-good archive.org identifiers used as reliable fallback
#   n_samples      : target number of WAV files to collect for calibration

PROFILE_CONFIGS = {
    "calm": {
        "profile_name": "Calm / Soothing",
        "search_queries": [
            'collection:librivoxaudio poetry',
            'collection:librivoxaudio meditations',
            'collection:librivoxaudio sonnets',
        ],
        "curated_ids": [
            # Marcus Aurelius: slow, measured, philosophical (correct ID)
            "meditations_0708_librivox",
            # Whitman: poetry, calm pace
            "leaves_of_grass_librivox",
            # Dante: slow poetic delivery
            "divine_comedy_librivox",
            # Thomas à Kempis: quiet, contemplative
            "imitation_of_christ_librivox",
        ],
        "n_samples": 4,
        "description": (
            "Gentle, measured pace. Used for meditation, ASMR, wellness content."
        ),
        "emoji": "🌙",
        "tips": [
            "Speak slower than feels natural — listeners need time to absorb calm content.",
            "Avoid sudden energy spikes; keep your volume even throughout.",
            "Longer pauses (1–2s) are a feature, not a flaw, in soothing reads.",
        ],
    },
    "energetic": {
        "profile_name": "Energetic / Hype",
        "search_queries": [
            'collection:librivoxaudio adventure fiction',
            'collection:librivoxaudio treasure island',
            'collection:librivoxaudio sherlock holmes',
        ],
        "curated_ids": [
            # Conan Doyle: fast, energetic case delivery
            "adventures_holmes",
            # Stevenson: breathless adventure narration
            "treasure_island_ap_librivox",
            # H.G. Wells: dramatic pacing
            "timemachine_sjm_librivox",
            # Dumas: sweeping adventure chapters
            "countofmontecristo_1303_librivox",
        ],
        "n_samples": 4,
        "description": (
            "High energy, fast pace, punchy delivery. Promos, gaming, hype reels."
        ),
        "emoji": "⚡",
        "tips": [
            "Short, punchy sentences drive energy. Cut filler ruthlessly.",
            "Use dynamic contrast — build UP to key words, don't stay flat.",
            "Pauses longer than 0.5s kill momentum in hype reads.",
        ],
    },
    "commercial": {
        "profile_name": "Commercial / Salesy",
        "search_queries": [
            'collection:librivoxaudio speeches',
            'collection:librivoxaudio Carnegie public speaking',
            'collection:librivoxaudio oratory',
        ],
        "curated_ids": [
            # Conwell: famous motivational lecture, punchy persuasive tone
            "acres_of_diamonds_1008_librivox",
            # Lucas/Carnegie: textbook on persuasive speech delivery
            "art_public_speaking_1101_librivox",
            # Andrew Carnegie autobiography: confident, authoritative cadence
            "autobiography_carnegie_1212_librivox",
            # Empire of Business essays: direct business persuasion
            "empireofbusiness_2010_librivox",
        ],
        "n_samples": 4,
        "description": (
            "Warm, persuasive, confident. Ads, promos, product demos."
        ),
        "emoji": "📣",
        "tips": [
            "Smile while recording — it literally changes your vocal tone.",
            "Land hard on the brand name or call-to-action every time.",
            "Keep pauses short and intentional — silence feels like doubt in ads.",
        ],
    },
    "character": {
        "profile_name": "Character / Animation",
        "search_queries": [
            'collection:librivoxaudio dramatic reading',
            'collection:librivoxaudio plays Shakespeare',
            'collection:librivoxaudio Christmas Carol',
        ],
        "curated_ids": [
            # Dickens dramatic reading: full character voice cast
            "christmascarol_1104_librivox",
            # Carroll: iconic varied voices (already downloaded)
            "alice_in_wonderland_librivox",
            # Shakespeare: play format, distinct characters
            "romeo_and_juliet_librivox",
            # Conan Doyle: Holmes/Watson dynamic, expressive delivery
            "adventures_holmes",
        ],
        "n_samples": 4,
        "description": (
            "Expressive, varied, playful. Cartoons, games, audiodramas."
        ),
        "emoji": "🎭",
        "tips": [
            "Dynamic range is your superpower — use the full spectrum from whisper to shout.",
            "Commit fully to the character physicality even when just recording audio.",
            "Intentional stutters for a nervous character are fine — mark them as 'keep'.",
        ],
    },
}

PROFILE_KEY_MAP = {
    "calm": "calm", "soothing": "calm",
    "energetic": "energetic", "hype": "energetic",
    "commercial": "commercial", "salesy": "commercial",
    "character": "character", "animation": "character",
}


# ── Utilities ─────────────────────────────────────────────────────────────────

def hline(w=75):
    print("-" * w)


def download(url: str, dest: str, min_size: int = 10_000) -> bool:
    """Download url to dest. Returns True if file is ready (cached or freshly downloaded)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > min_size:
        print(f"    [cached] {os.path.basename(dest)}")
        return True
    try:
        print(f"    Downloading {os.path.basename(dest)} ...")
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"    -> {len(data) / 1024:.0f} KB")
        return True
    except Exception as e:
        print(f"    FAILED {url}: {e}")
        if os.path.exists(dest):
            os.remove(dest)
        return False


def fetch_json(url: str) -> dict | list | None:
    """Fetch JSON from url. Returns parsed object or None on failure."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"    [API error] {url}: {e}")
        return None


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
              f"({os.path.getsize(wav) / 1024 / 1024:.1f} MB)")
        return True
    except Exception as e:
        print(f"    CONVERSION FAILED: {e}")
        return False


# ── archive.org discovery ─────────────────────────────────────────────────────

def search_archive(query: str, rows: int = 20) -> list[str]:
    """
    Search archive.org for LibriVox audio items. Returns list of identifiers
    sorted by downloads descending.

    archive.org requires fl[] and sort[] as repeated params — urlencode with
    doseq handles this correctly.
    """
    params = urllib.parse.urlencode([
        ("q",        query),
        ("fl[]",     "identifier"),
        ("sort[]",   "downloads desc"),
        ("rows",     rows),
        ("output",   "json"),
    ])
    url = f"https://archive.org/advancedsearch.php?{params}"
    data = fetch_json(url)
    if not data:
        return []
    try:
        docs = data["response"]["docs"]
        return [d["identifier"] for d in docs if "identifier" in d]
    except (KeyError, TypeError):
        return []


def get_first_chapter_mp3_url(identifier: str, min_bytes: int = 500_000) -> str | None:
    """
    Query archive.org metadata for an item and return the URL of the
    best first-chapter MP3 file (>= min_bytes).

    Preference order:
      1. File whose name contains '01', '001', 'chapter1', 'ch01' etc.
      2. Any MP3 large enough to be a full chapter.
    """
    meta_url = f"https://archive.org/metadata/{identifier}"
    data = fetch_json(meta_url)
    if not data or "files" not in data:
        return None

    mp3_files = [
        f for f in data["files"]
        if f.get("format", "").lower() in ("mp3", "64kbps mp3", "128kbps mp3",
                                            "vbr mp3", "mp3 (192k)")
        and int(f.get("size", 0)) >= min_bytes
    ]

    if not mp3_files:
        return None

    # Prefer chapter-1-ish filenames
    chapter1_hints = ("_01", "_001", "01_", "001_", "chapter1", "ch01",
                      "-01", "-001", "part01", "track01", "01.")
    ranked = sorted(
        mp3_files,
        key=lambda f: (
            0 if any(h in f["name"].lower() for h in chapter1_hints) else 1,
            -int(f.get("size", 0)),   # bigger first within each tier
        )
    )

    best = ranked[0]
    return f"https://archive.org/download/{identifier}/{best['name']}"


# ── Sample collection ─────────────────────────────────────────────────────────

def collect_samples(config: dict, profile_key: str) -> list[tuple[str, str]]:
    """
    Download and convert audio for a profile. Returns list of (label, wav_path).

    Strategy:
      1. Try curated identifiers first (most reliable).
      2. Fill remaining slots with archive.org search results.
    """
    profile_dir = os.path.join(SAMPLES, profile_key)
    os.makedirs(profile_dir, exist_ok=True)

    n_needed   = config["n_samples"]
    ready_wavs = []               # (label, wav_path)
    tried_ids  = set()

    def _try_identifier(ident: str) -> bool:
        """Download + convert one identifier. Returns True on success."""
        if ident in tried_ids:
            return False
        tried_ids.add(ident)

        mp3_url = get_first_chapter_mp3_url(ident)
        if not mp3_url:
            print(f"    [skip] {ident} — no suitable MP3 found")
            return False

        filename = os.path.basename(urllib.parse.urlparse(mp3_url).path)
        label    = ident.replace("_librivox", "").replace("_", " ")[:24]
        mp3_path = os.path.join(profile_dir, filename)
        wav_path = mp3_path.replace(".mp3", ".wav")

        ok = download(mp3_url, mp3_path)
        if not ok:
            return False
        ok = mp3_to_wav(mp3_path, wav_path)
        if not ok:
            return False

        ready_wavs.append((label, wav_path))
        return True

    # 1 — curated identifiers
    print(f"\n  Trying curated identifiers ...")
    for ident in config["curated_ids"]:
        if len(ready_wavs) >= n_needed:
            break
        print(f"  • {ident}")
        _try_identifier(ident)
        time.sleep(0.5)   # polite pacing

    # 2 — archive.org search fallback
    if len(ready_wavs) < n_needed:
        print(f"\n  Searching archive.org for more samples ...")
        for query in config["search_queries"]:
            if len(ready_wavs) >= n_needed:
                break
            print(f"  Query: {query[:70]}")
            ids = search_archive(query, rows=15)
            for ident in ids:
                if len(ready_wavs) >= n_needed:
                    break
                if ident in tried_ids:
                    continue
                print(f"  • {ident}")
                _try_identifier(ident)
                time.sleep(0.5)

    print(f"\n  Collected {len(ready_wavs)}/{n_needed} samples for "
          f"{config['profile_name']}")
    return ready_wavs


# ── Feature extraction ────────────────────────────────────────────────────────

def extract_features(wav_path: str, label: str, max_seconds: float = 120.0) -> dict:
    """Extract acoustic features from a WAV file (capped at max_seconds)."""
    print(f"\n  Extracting features: {label}")
    samples, sr = read_wav_mono(wav_path)
    duration_full = len(samples) / sr
    cap     = int(min(len(samples), max_seconds * sr))
    samples = samples[:cap]
    duration = cap / sr
    print(f"    Duration: {duration_full:.1f}s  |  Analyzing first {duration:.1f}s")

    sm       = SettingsManager()
    settings = sm.analysis_settings()
    analyzer = AudioAnalyzer(settings)

    tmp_wav = os.path.join(tempfile.gettempdir(), "vox_bench_tmp.wav")
    write_wav_mono(tmp_wav, samples, sr)
    results = analyzer.analyze(tmp_wav)

    silence_regions = results["silence_regions"]
    stats           = results["stats"]

    # ── Pause ratio ──────────────────────────────────────────────────
    total_silence = sum(r["end"] - r["start"] for r in silence_regions)
    pause_ratio   = total_silence / max(1.0, duration)

    # ── Speech rate WPM ──────────────────────────────────────────────
    voiced_duration  = duration - total_silence
    estimated_words  = voiced_duration / 0.4        # avg word ~0.4s in narration
    speech_rate_wpm  = estimated_words / (duration / 60.0)

    # ── Energy features (100ms frames) ───────────────────────────────
    frame_sec   = 0.1
    frame_size  = int(sr * frame_sec)
    sil_thresh  = db_to_linear(settings.get("silence_threshold_db", -40))

    voiced_energies  = []
    all_energies_db  = []

    for i in range(0, len(samples) - frame_size, frame_size):
        chunk = samples[i: i + frame_size]
        e = rms(chunk)
        if e > 1e-10:
            all_energies_db.append(20 * math.log10(e + 1e-12))
        if e > sil_thresh:
            voiced_energies.append(e)

    # ── Energy consistency ────────────────────────────────────────────
    if len(voiced_energies) > 4:
        ve_mean = sum(voiced_energies) / len(voiced_energies)
        ve_var  = sum((x - ve_mean) ** 2 for x in voiced_energies) / len(voiced_energies)
        ve_cv   = math.sqrt(ve_var) / (ve_mean + 1e-12)
        energy_consistency = max(0.0, 1.0 - min(1.0, ve_cv * 1.5))
    else:
        energy_consistency = 0.5

    # ── Dynamic range ─────────────────────────────────────────────────
    if len(all_energies_db) > 10:
        all_energies_db.sort()
        p5  = all_energies_db[int(len(all_energies_db) * 0.05)]
        p95 = all_energies_db[int(len(all_energies_db) * 0.95)]
        dynamic_range_db = p95 - p5
    else:
        dynamic_range_db = 0.0

    # ── Max long pause ────────────────────────────────────────────────
    max_long_pause = (
        max(r["duration"] for r in silence_regions) if silence_regions else 0.0
    )

    # ── Clarity floor ─────────────────────────────────────────────────
    if len(voiced_energies) > 10:
        vs = sorted(voiced_energies)
        p10 = vs[int(len(vs) * 0.10)]
        clarity_floor_db = 20 * math.log10(p10 + 1e-12)
    else:
        clarity_floor_db = -40.0

    feats = {
        "label":              label,
        "duration_analyzed":  duration,
        "speech_rate_wpm":    speech_rate_wpm,
        "pause_ratio":        pause_ratio,
        "energy_consistency": energy_consistency,
        "dynamic_range_db":   dynamic_range_db,
        "max_long_pause_sec": max_long_pause,
        "clarity_floor_db":   clarity_floor_db,
        "stutter_count":      stats["stutter_count"],
        "unclear_count":      stats["unclear_count"],
        "_results":           results,
    }
    return feats


def compute_ranges(all_feats: list[dict], stutter_tol: float = 0.01) -> dict:
    """
    Compute padded benchmark ranges from a list of feature dicts.
    Each range is min*0.85 .. max*1.15 across samples.
    """
    def padded(vals, lo_f=0.85, hi_f=1.15):
        return (round(min(vals) * lo_f, 3), round(max(vals) * hi_f, 3))

    rates       = [f["speech_rate_wpm"]    for f in all_feats]
    pauses      = [f["pause_ratio"]        for f in all_feats]
    consistencies = [f["energy_consistency"] for f in all_feats]
    dyn_ranges  = [f["dynamic_range_db"]   for f in all_feats]
    max_pauses  = [f["max_long_pause_sec"] for f in all_feats]
    clf_dbs     = [f["clarity_floor_db"]   for f in all_feats]

    return {
        "speech_rate_wpm":    (round(min(rates)    * 0.85, 1),
                               round(max(rates)    * 1.15, 1)),
        "pause_ratio":        (round(min(pauses)   * 0.85, 3),
                               round(max(pauses)   * 1.15, 3)),
        "energy_consistency": (round(min(consistencies) * 0.85, 3),
                               round(max(consistencies) * 1.15, 3)),
        "dynamic_range_db":   (round(min(dyn_ranges) * 0.85, 1),
                               round(max(dyn_ranges) * 1.15, 1)),
        "max_long_pause_sec": round(max(max_pauses) * 1.15, 2),
        "clarity_floor_db":   round(min(clf_dbs)    * 1.15, 1),
        "stutter_tolerance":  stutter_tol,
    }


# ── Output generation ─────────────────────────────────────────────────────────

# stutter tolerance is different per profile — Character gets more leeway
STUTTER_TOLERANCE = {
    "calm":       0.015,   # some breathing allowed
    "energetic":  0.010,   # fast delivery, minor stumbles OK
    "commercial": 0.008,   # polished read expected
    "character":  0.030,   # intentional stutters are part of the craft
}


def format_profile_entry(profile_key: str, config: dict,
                          measured: dict, all_feats: list[dict]) -> str:
    """Return a Python dict-literal string for one profile entry."""
    name   = config["profile_name"]
    desc   = config["description"]
    emoji  = config["emoji"]
    tips   = config["tips"]
    labels = [f["label"] for f in all_feats]

    tip_lines = "\n".join(f'            "{t}",' for t in tips)
    cal_feat_lines = ""
    for f in all_feats:
        cal_feat_lines += f'            "{f["label"]}": {{\n'
        for k in ("speech_rate_wpm", "pause_ratio", "energy_consistency",
                  "dynamic_range_db", "max_long_pause_sec", "clarity_floor_db"):
            cal_feat_lines += f'                "{k}": {f[k]:.3f},\n'
        cal_feat_lines += '            },\n'

    m = measured
    return f'''    "{name}": {{
        "description": "{desc}",
        "emoji": "{emoji}",
        "speech_rate_wpm":     ({m["speech_rate_wpm"][0]:.1f}, {m["speech_rate_wpm"][1]:.1f}),
        "pause_ratio":         ({m["pause_ratio"][0]:.3f}, {m["pause_ratio"][1]:.3f}),
        "energy_consistency":  ({m["energy_consistency"][0]:.3f}, {m["energy_consistency"][1]:.3f}),
        "dynamic_range_db":    ({m["dynamic_range_db"][0]:.1f}, {m["dynamic_range_db"][1]:.1f}),
        "max_long_pause_sec":  {m["max_long_pause_sec"]:.2f},
        "stutter_tolerance":   {m["stutter_tolerance"]},
        "clarity_floor_db":    {m["clarity_floor_db"]:.1f},
        "tips": [
{tip_lines}
        ],
        "calibration_samples": {labels!r},
        "calibration_features": {{
{cal_feat_lines}        }},
    }},'''


def build_measured_benchmarks_content(all_profile_data: dict) -> str:
    """
    Build the full measured_benchmarks.py content from a dict of
    {profile_key: (config, measured, all_feats)}.

    Preserves existing Narrator / Documentary and Audiobook entries,
    and adds/updates the newly calibrated profiles.
    """
    # Read current file so we can preserve Narrator/Audiobook entries
    mb_path = os.path.join(ROOT, "coaching", "measured_benchmarks.py")
    narrator_block = ""
    audiobook_block = ""

    if os.path.exists(mb_path):
        # Re-generate from existing measured_benchmarks data
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("mb", mb_path)
            mb_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mb_mod)
            existing = getattr(mb_mod, "MEASURED_PROFILES", {})

            def _existing_entry(name: str) -> str:
                p = existing.get(name, {})
                if not p:
                    return ""
                tips = p.get("tips", [])
                tip_lines = "\n".join(f'            "{t}",' for t in tips)
                cal_feats = p.get("calibration_features", {})
                cal_lines = ""
                for lbl, feats in cal_feats.items():
                    cal_lines += f'            "{lbl}": {{\n'
                    for k in ("speech_rate_wpm", "pause_ratio", "energy_consistency",
                              "dynamic_range_db", "max_long_pause_sec", "clarity_floor_db"):
                        if k in feats:
                            cal_lines += f'                "{k}": {feats[k]:.3f},\n'
                    cal_lines += '            },\n'
                cal_samples = p.get("calibration_samples", [])
                return f'''    "{name}": {{
        "description": "{p.get("description", "")}",
        "emoji": "{p.get("emoji", "")}",
        "speech_rate_wpm":     ({p["speech_rate_wpm"][0]:.1f}, {p["speech_rate_wpm"][1]:.1f}),
        "pause_ratio":         ({p["pause_ratio"][0]:.3f}, {p["pause_ratio"][1]:.3f}),
        "energy_consistency":  ({p["energy_consistency"][0]:.3f}, {p["energy_consistency"][1]:.3f}),
        "dynamic_range_db":    ({p["dynamic_range_db"][0]:.1f}, {p["dynamic_range_db"][1]:.1f}),
        "max_long_pause_sec":  {p["max_long_pause_sec"]:.2f},
        "stutter_tolerance":   {p.get("stutter_tolerance", 0.005)},
        "clarity_floor_db":    {p["clarity_floor_db"]:.1f},
        "tips": [
{tip_lines}
        ],
        "calibration_samples": {cal_samples!r},
        "calibration_features": {{
{cal_lines}        }},
    }},'''

            narrator_block  = _existing_entry("Narrator / Documentary")
            audiobook_block = _existing_entry("Audiobook")
        except Exception as e:
            print(f"  [warn] Could not load existing measured_benchmarks.py: {e}")

    # Build new profile blocks
    new_blocks = {}
    calibrated_sources = {}
    for pkey, (config, measured, feats) in all_profile_data.items():
        new_blocks[config["profile_name"]] = format_profile_entry(
            pkey, config, measured, feats
        )
        calibrated_sources[pkey] = ", ".join(f["label"] for f in feats)

    # Assemble the ordered dict entries
    # Order: Narrator, Audiobook, Calm, Energetic, Commercial, Character
    ordered_blocks = []
    if narrator_block:
        ordered_blocks.append(narrator_block)
    if audiobook_block:
        ordered_blocks.append(audiobook_block)

    display_order = [
        "Calm / Soothing",
        "Energetic / Hype",
        "Commercial / Salesy",
        "Character / Animation",
    ]
    for name in display_order:
        if name in new_blocks:
            ordered_blocks.append(new_blocks[name])

    dict_body = "\n".join(ordered_blocks)

    sources_comment = "\n".join(
        f"#   {v}  →  {k}" for k, v in calibrated_sources.items()
    )

    return f'''"""
Voxarah — Measured Acoustic Benchmarks
========================================
Auto-generated by scrape_profiles.py from LibriVox public-domain audio.

Calibration sources:
{sources_comment}

Each benchmark range is min(samples)*0.85 .. max(samples)*1.15.
These provide realistic targets derived from actual professional recordings.
"""

from typing import Dict, List


MEASURED_PROFILES = {{
{dict_body}
}}


def get_measured_profile(name: str) -> Dict:
    """Return measured benchmark dict for a profile name, or empty dict."""
    return MEASURED_PROFILES.get(name, {{}})


def get_all_measured_profiles() -> List[str]:
    """Return list of measured profile names."""
    return list(MEASURED_PROFILES.keys())
'''


# ── ffmpeg bootstrap ──────────────────────────────────────────────────────────

def ensure_ffmpeg():
    """Download ffmpeg.exe if not already present in samples/."""
    if os.path.exists(FFMPEG):
        return
    os.makedirs(os.path.dirname(FFMPEG), exist_ok=True)
    print("  Downloading ffmpeg (one-time setup) ...")
    ffmpeg_zip = os.path.join(os.path.dirname(FFMPEG), "ffmpeg.zip")
    ok = download(
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        ffmpeg_zip, min_size=1_000_000,
    )
    if not ok:
        print("  ERROR: Failed to download ffmpeg. "
              "Place ffmpeg.exe manually at samples/ffmpeg.exe")
        sys.exit(1)
    try:
        with zipfile.ZipFile(ffmpeg_zip, "r") as z:
            for name in z.namelist():
                if name.endswith("bin/ffmpeg.exe"):
                    z.extract(name, os.path.dirname(FFMPEG))
                    extracted = os.path.join(os.path.dirname(FFMPEG), name)
                    shutil.move(extracted, FFMPEG)
                    # clean up extracted folder tree
                    top = os.path.join(os.path.dirname(FFMPEG),
                                       name.split("/")[0])
                    if os.path.isdir(top):
                        shutil.rmtree(top)
                    break
        os.remove(ffmpeg_zip)
        print("  ffmpeg ready.")
    except Exception as e:
        print(f"  ERROR extracting ffmpeg: {e}")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--list" in args:
        print("Available profile keys:")
        for k, v in PROFILE_KEY_MAP.items():
            cfg = PROFILE_CONFIGS[v]
            print(f"  {k:<14}  →  {cfg['profile_name']}")
        return

    # Resolve requested keys (default: all 4)
    if args:
        requested_keys = []
        for a in args:
            k = PROFILE_KEY_MAP.get(a.lower())
            if k and k not in requested_keys:
                requested_keys.append(k)
            elif k is None:
                print(f"  Unknown profile key: {a!r}  (run --list to see options)")
        if not requested_keys:
            print("No valid profiles specified.")
            return
    else:
        requested_keys = list(PROFILE_CONFIGS.keys())

    print("=" * 75)
    print("  VOXARAH PROFILE CALIBRATION SCRAPER")
    print("=" * 75)
    print(f"  Profiles to calibrate: {', '.join(requested_keys)}")

    ensure_ffmpeg()
    os.makedirs(SAMPLES, exist_ok=True)

    all_profile_data = {}   # profile_key -> (config, measured, feats)

    for pkey in requested_keys:
        config = PROFILE_CONFIGS[pkey]
        print(f"\n{'=' * 75}")
        print(f"  PROFILE: {config['profile_name']}")
        print("=" * 75)

        # ── Phase 1: Download ────────────────────────────────────────
        print("\n  Phase 1 — Downloading samples")
        hline()
        wav_pairs = collect_samples(config, pkey)

        if len(wav_pairs) < 2:
            print(f"  WARNING: Only {len(wav_pairs)} sample(s) collected "
                  f"(need ≥2). Skipping {pkey}.")
            continue

        # ── Phase 2: Extract features ────────────────────────────────
        print(f"\n  Phase 2 — Extracting features ({len(wav_pairs)} samples)")
        hline()
        all_feats = []
        for label, wav_path in wav_pairs:
            try:
                feats = extract_features(wav_path, label, max_seconds=120.0)
                all_feats.append(feats)
            except Exception as e:
                print(f"  [skip] {label}: {e}")

        if len(all_feats) < 2:
            print(f"  WARNING: Feature extraction failed for most samples. "
                  f"Skipping {pkey}.")
            continue

        # ── Phase 3: Compute ranges ──────────────────────────────────
        print(f"\n  Phase 3 — Computing benchmark ranges")
        hline()
        tol = STUTTER_TOLERANCE[pkey]
        measured = compute_ranges(all_feats, stutter_tol=tol)

        print(f"\n  {'Feature':<26s}  {'Low':>10s}  {'High':>10s}")
        hline(52)
        for key in ("speech_rate_wpm", "pause_ratio", "energy_consistency",
                    "dynamic_range_db"):
            lo, hi = measured[key]
            print(f"  {key:<26s}  {lo:>10.3f}  {hi:>10.3f}")
        print(f"  {'max_long_pause_sec':<26s}  {'—':>10s}  "
              f"{measured['max_long_pause_sec']:>10.2f}")
        print(f"  {'clarity_floor_db':<26s}  "
              f"{measured['clarity_floor_db']:>10.1f}  {'—':>10s}")
        print(f"  {'stutter_tolerance':<26s}  {'—':>10s}  "
              f"{measured['stutter_tolerance']:>10.3f}")
        hline(52)

        # Feature table
        print(f"\n  Feature Table:\n")
        labels   = [f["label"][:18] for f in all_feats]
        col_w    = max(14, max(len(l) for l in labels) + 2)
        header   = f"  {'Feature':<26s}" + "".join(f"{l:>{col_w}s}" for l in labels)
        print(header)
        hline(len(header))
        rows = [
            ("speech_rate_wpm",    "Speech Rate (WPM)",   "{:.1f}"),
            ("pause_ratio",        "Pause Ratio",          "{:.3f}"),
            ("energy_consistency", "Energy Consistency",   "{:.3f}"),
            ("dynamic_range_db",   "Dynamic Range (dB)",   "{:.1f}"),
            ("max_long_pause_sec", "Max Pause (s)",        "{:.2f}"),
            ("clarity_floor_db",   "Clarity Floor (dB)",   "{:.1f}"),
        ]
        for key, name, fmt in rows:
            row = f"  {name:<26s}"
            for f in all_feats:
                row += f"{fmt.format(f[key]):>{col_w}s}"
            print(row)
        hline(len(header))

        all_profile_data[pkey] = (config, measured, all_feats)

    if not all_profile_data:
        print("\n  No profiles were successfully calibrated.")
        return

    # ── Write measured_benchmarks.py ────────────────────────────────────────
    print(f"\n{'=' * 75}")
    print("  Writing coaching/measured_benchmarks.py")
    print("=" * 75)

    content  = build_measured_benchmarks_content(all_profile_data)
    mb_path  = os.path.join(ROOT, "coaching", "measured_benchmarks.py")

    # Backup existing file
    if os.path.exists(mb_path):
        backup = mb_path.replace(".py", "_backup.py")
        shutil.copy2(mb_path, backup)
        print(f"  Backed up existing file to: measured_benchmarks_backup.py")

    with open(mb_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  Written: {mb_path}")

    # ── Final summary ────────────────────────────────────────────────────────
    print(f"\n{'=' * 75}")
    print("  DONE")
    print("=" * 75)
    for pkey, (config, measured, feats) in all_profile_data.items():
        labels = ", ".join(f["label"] for f in feats)
        print(f"\n  {config['profile_name']}")
        print(f"    Samples      : {labels}")
        print(f"    WPM range    : {measured['speech_rate_wpm'][0]:.0f}–"
              f"{measured['speech_rate_wpm'][1]:.0f}")
        print(f"    Pause ratio  : {measured['pause_ratio'][0]:.3f}–"
              f"{measured['pause_ratio'][1]:.3f}")
        print(f"    Energy cons. : {measured['energy_consistency'][0]:.3f}–"
              f"{measured['energy_consistency'][1]:.3f}")
        print(f"    Dyn range    : {measured['dynamic_range_db'][0]:.1f}–"
              f"{measured['dynamic_range_db'][1]:.1f} dB")
    print()


if __name__ == "__main__":
    main()
