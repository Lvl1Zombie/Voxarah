"""
Real-speech integration test for Audioflow.
Downloads a public-domain speech WAV, converts to 44100 Hz 16-bit mono,
then exercises the full analysis + coaching pipeline.
"""

import sys, os, struct, wave, math, tempfile, urllib.request

# Fix Windows console encoding for emoji characters
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 1  Download ──────────────────────────────────────────────────────
URL = "https://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0010_8k.wav"
RAW_PATH = os.path.join(tempfile.gettempdir(), "osr_raw.wav")
CONVERTED_PATH = os.path.join(tempfile.gettempdir(), "osr_44100.wav")
CLEANED_PATH = os.path.join(tempfile.gettempdir(), "osr_cleaned.wav")

print("=" * 65)
print("  AUDIOFLOW  —  Real Speech Integration Test")
print("=" * 65)

print(f"\n[1] Downloading {URL} ...")
req = urllib.request.Request(URL, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
})
with urllib.request.urlopen(req, timeout=30) as resp, open(RAW_PATH, "wb") as f:
    f.write(resp.read())
print(f"    Saved to {RAW_PATH}  ({os.path.getsize(RAW_PATH):,} bytes)")

# ── 2  Convert to 16-bit mono 44100 Hz ──────────────────────────────
print("\n[2] Converting to 16-bit mono 44100 Hz ...")

with wave.open(RAW_PATH, "rb") as src:
    n_ch = src.getnchannels()
    sw = src.getsampwidth()
    src_rate = src.getframerate()
    n_frames = src.getnframes()
    raw = src.readframes(n_frames)

print(f"    Source: {n_ch}ch, {sw * 8}-bit, {src_rate} Hz, {n_frames} frames")

# decode source samples → list[int] (mono)
if sw == 1:
    samples_raw = list(struct.unpack(f"<{len(raw)}B", raw))
    samples_raw = [(s - 128) * 256 for s in samples_raw]  # unsigned 8→signed 16 range
elif sw == 2:
    samples_raw = list(struct.unpack(f"<{len(raw) // 2}h", raw))
elif sw == 3:
    samples_raw = []
    for i in range(0, len(raw), 3):
        val = int.from_bytes(raw[i:i+3], "little", signed=True)
        samples_raw.append(val >> 8)  # scale 24→16
elif sw == 4:
    samples_raw = list(struct.unpack(f"<{len(raw) // 4}i", raw))
    samples_raw = [s >> 16 for s in samples_raw]
else:
    raise ValueError(f"Unsupported sample width: {sw}")

# mix to mono if stereo+
if n_ch > 1:
    mono = []
    for i in range(0, len(samples_raw), n_ch):
        mono.append(sum(samples_raw[i:i+n_ch]) // n_ch)
    samples_raw = mono

# resample src_rate → 44100 using linear interpolation
TGT_RATE = 44100
ratio = src_rate / TGT_RATE
n_out = int(len(samples_raw) / ratio)
resampled: list[int] = []
for i in range(n_out):
    pos = i * ratio
    idx = int(pos)
    frac = pos - idx
    s0 = samples_raw[min(idx, len(samples_raw) - 1)]
    s1 = samples_raw[min(idx + 1, len(samples_raw) - 1)]
    val = s0 + (s1 - s0) * frac
    resampled.append(max(-32768, min(32767, int(val))))

with wave.open(CONVERTED_PATH, "wb") as dst:
    dst.setnchannels(1)
    dst.setsampwidth(2)
    dst.setframerate(TGT_RATE)
    dst.writeframes(struct.pack(f"<{len(resampled)}h", *resampled))

print(f"    Output: 1ch, 16-bit, {TGT_RATE} Hz, {len(resampled)} frames")
print(f"    Saved to {CONVERTED_PATH}  ({os.path.getsize(CONVERTED_PATH):,} bytes)")

# ── 3  Analyze ───────────────────────────────────────────────────────
print("\n[3] Running AudioAnalyzer.analyze() ...")
from core.settings import SettingsManager
from core.analyzer import AudioAnalyzer, build_label_file, build_cleaned_wav

sm = SettingsManager()
analyzer = AudioAnalyzer(sm.analysis_settings())
results = analyzer.analyze(CONVERTED_PATH)

stats = results["stats"]
print(f"    Duration       : {results['duration']:.2f} s")
print(f"    Pause count    : {stats['pause_count']}")
print(f"    Stutter count  : {stats['stutter_count']}")
print(f"    Unclear count  : {stats['unclear_count']}")
print(f"    Time saved     : {stats['time_saved']:.2f} s")
print(f"    Total edits    : {len(results['all_edits'])}")

print("\n    First 10 edits:")
for i, e in enumerate(results["all_edits"][:10]):
    desc = e.get("desc", "")
    print(f"      {i+1:2d}. [{e['type']:>7s}]  {e['start']:6.2f}–{e['end']:6.2f}s  {desc}")

# ── 4  Coaching profiles ────────────────────────────────────────────
print("\n[4] Scoring against all coaching profiles ...")
from coaching.profiles import get_all_profiles, score_recording

profiles = get_all_profiles()
print(f"    {'Profile':<30s}  Score  Grade")
print(f"    {'-'*30}  -----  -----")
for p in profiles:
    r = score_recording(results, p)
    print(f"    {p:<30s}  {r['overall']:>5d}  {r['grade']:>5s}")

# ── 5  Coaching characters (1 per category) ─────────────────────────
print("\n[5] Scoring one character per category ...")
from coaching.characters import get_all_categories, get_category_characters, score_character

categories = get_all_categories()
print(f"    {'Character':<30s}  Score  Grade  Category")
print(f"    {'-'*30}  -----  -----  --------")
for cat in categories:
    chars = get_category_characters(cat)
    name = chars[0]
    r = score_character(results, name)
    print(f"    {name:<30s}  {r['overall']:>5d}  {r['grade']:>5s}  {cat}")

# ── 6  Audacity label file ──────────────────────────────────────────
print("\n[6] First 10 lines of Audacity label file:")
labels = build_label_file(results)
for i, line in enumerate(labels.strip().splitlines()[:10]):
    print(f"    {line}")

# ── 7  Cleaned WAV comparison ───────────────────────────────────────
print("\n[7] Building cleaned WAV and comparing sizes ...")
build_cleaned_wav(results, sm.analysis_settings(), CLEANED_PATH)

orig_size = os.path.getsize(CONVERTED_PATH)
clean_size = os.path.getsize(CLEANED_PATH)
diff = orig_size - clean_size
pct = (diff / orig_size) * 100 if orig_size else 0

print(f"    Original : {orig_size:>10,} bytes")
print(f"    Cleaned  : {clean_size:>10,} bytes")
print(f"    Saved    : {diff:>10,} bytes  ({pct:.1f}%)")

print("\n" + "=" * 65)
print("  ALL STEPS COMPLETED SUCCESSFULLY")
print("=" * 65)
