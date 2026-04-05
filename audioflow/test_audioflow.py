"""
Audioflow headless test suite — no GUI windows opened.
Generates a synthetic WAV, exercises core + coaching modules,
and prints a PASS/FAIL summary.
"""

import sys, os, struct, wave, math, tempfile, traceback

# ── helpers ──────────────────────────────────────────────────────────
results_summary: list[tuple[str, bool, str]] = []   # (name, passed, detail)

def run_test(name, fn):
    """Run *fn*, catch exceptions, record result."""
    try:
        fn()
        results_summary.append((name, True, ""))
    except Exception as e:
        results_summary.append((name, False, f"{e}\n{traceback.format_exc()}"))

def print_summary():
    w = max(len(n) for n, _, _ in results_summary) + 2
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    passed = failed = 0
    for name, ok, detail in results_summary:
        tag = "PASS" if ok else "FAIL"
        symbol = "+" if ok else "X"
        print(f"  [{symbol}] {tag}  {name}")
        if not ok:
            for line in detail.strip().splitlines()[-3:]:
                print(f"           {line}")
        if ok:
            passed += 1
        else:
            failed += 1
    print("-" * 60)
    print(f"  {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    return failed == 0


# ── synthetic WAV generator ─────────────────────────────────────────
def make_test_wav(path: str,
                  duration: float = 2.0,
                  sr: int = 44100,
                  freq: float = 440.0):
    """
    Write a 16-bit mono WAV with tone + silence gaps.
    Layout (seconds):
        0.0 – 0.4   tone
        0.4 – 0.8   silence          (0.4 s gap)
        0.8 – 1.2   tone
        1.2 – 1.8   silence          (0.6 s gap — long pause)
        1.8 – 2.0   tone
    """
    n_samples = int(duration * sr)
    samples: list[int] = []
    for i in range(n_samples):
        t = i / sr
        # decide tone vs silence
        if t < 0.4 or 0.8 <= t < 1.2 or 1.8 <= t < 2.0:
            val = math.sin(2 * math.pi * freq * t) * 0.6
        else:
            val = 0.0
        samples.append(int(val * 32767))

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


# ── 1  imports ───────────────────────────────────────────────────────
def test_imports():
    import core.analyzer
    import core.settings
    import core.audacity_bridge
    # ui modules import tkinter; we must have a display-less fallback
    import ui.design
    import ui.components
    import coaching.profiles
    import coaching.characters


# ── 2  SettingsManager ───────────────────────────────────────────────
def test_settings():
    from core.settings import SettingsManager, DEFAULTS

    sm = SettingsManager()

    # defaults present
    for key in DEFAULTS:
        val = sm.get(key)
        assert val is not None, f"default missing for {key}"

    # get / set round-trip
    sm.set("silence_threshold_db", -35)
    assert sm.get("silence_threshold_db") == -35, "set/get mismatch"

    # analysis_settings keys
    expected_keys = {
        "silence_threshold_db", "min_silence_duration",
        "max_pause_duration", "stutter_window",
        "detect_stutters", "detect_unclear",
    }
    actual_keys = set(sm.analysis_settings().keys())
    assert actual_keys == expected_keys, (
        f"analysis_settings keys mismatch: {actual_keys} != {expected_keys}"
    )


# ── 3  AudioAnalyzer.analyze() ──────────────────────────────────────
_analysis_results: dict = {}   # shared with later tests

def test_analyzer():
    global _analysis_results
    from core.analyzer import AudioAnalyzer
    from core.settings import SettingsManager

    sm = SettingsManager()
    analyzer = AudioAnalyzer(sm.analysis_settings())

    wav_path = os.path.join(tempfile.gettempdir(), "audioflow_test.wav")
    make_test_wav(wav_path)

    res = analyzer.analyze(wav_path)
    _analysis_results = res

    required = {"duration", "all_edits", "stats", "samples", "sample_rate"}
    missing = required - set(res.keys())
    assert not missing, f"missing keys in results: {missing}"

    assert isinstance(res["duration"], (int, float)) and res["duration"] > 0
    assert isinstance(res["samples"], list) and len(res["samples"]) > 0
    assert res["sample_rate"] == 44100
    assert isinstance(res["all_edits"], list)
    assert isinstance(res["stats"], dict)

    stat_keys = {"duration", "pause_count", "stutter_count",
                 "unclear_count", "time_saved", "total_flags"}
    missing_stat = stat_keys - set(res["stats"].keys())
    assert not missing_stat, f"missing stat keys: {missing_stat}"


# ── 4  build_label_file ─────────────────────────────────────────────
def test_label_file():
    from core.analyzer import build_label_file
    assert _analysis_results, "analyzer test must run first"

    labels = build_label_file(_analysis_results)
    assert isinstance(labels, str)

    # If there are edits, each line should be tab-delimited with 3 fields
    if _analysis_results["all_edits"]:
        for line in labels.strip().splitlines():
            parts = line.split("\t")
            assert len(parts) == 3, f"bad label line: {line!r}"
            # first two fields should be numeric (start, end)
            float(parts[0])
            float(parts[1])


# ── 5  build_cleaned_wav ────────────────────────────────────────────
def test_cleaned_wav():
    from core.analyzer import build_cleaned_wav
    from core.settings import SettingsManager
    assert _analysis_results, "analyzer test must run first"

    sm = SettingsManager()
    out_path = os.path.join(tempfile.gettempdir(), "audioflow_cleaned.wav")

    build_cleaned_wav(_analysis_results, sm.analysis_settings(), out_path)

    assert os.path.isfile(out_path), "cleaned wav not written"
    with wave.open(out_path, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 0


# ── 6  coaching profiles ────────────────────────────────────────────
def test_coaching_profiles():
    from coaching.profiles import get_all_profiles, score_recording
    assert _analysis_results, "analyzer test must run first"

    profiles = get_all_profiles()
    assert isinstance(profiles, list) and len(profiles) > 0, "no profiles"

    for name in profiles:
        result = score_recording(_analysis_results, name)
        assert isinstance(result, dict), f"score_recording({name}) not dict"
        assert "overall" in result, f"missing 'overall' for {name}"
        assert "grade" in result, f"missing 'grade' for {name}"
        assert "scores" in result, f"missing 'scores' for {name}"


# ── 7  coaching characters ──────────────────────────────────────────
def test_coaching_characters():
    from coaching.characters import (
        get_all_categories, get_category_characters, score_character,
    )
    assert _analysis_results, "analyzer test must run first"

    categories = get_all_categories()
    assert isinstance(categories, list) and len(categories) > 0, "no categories"

    for cat in categories:
        chars = get_category_characters(cat)
        assert len(chars) > 0, f"no characters in category {cat}"
        # test at least the first character in each category
        name = chars[0]
        result = score_character(_analysis_results, name)
        assert isinstance(result, dict), f"score_character({name}) not dict"
        assert "error" not in result, f"error scoring {name}: {result.get('error')}"
        assert "overall" in result, f"missing 'overall' for {name}"
        assert "grade" in result, f"missing 'grade' for {name}"


# ── run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_test("1. All imports",          test_imports)
    run_test("2. SettingsManager",      test_settings)
    run_test("3. AudioAnalyzer",        test_analyzer)
    run_test("4. build_label_file",     test_label_file)
    run_test("5. build_cleaned_wav",    test_cleaned_wav)
    run_test("6. Coaching profiles",    test_coaching_profiles)
    run_test("7. Coaching characters",  test_coaching_characters)

    all_passed = print_summary()
    sys.exit(0 if all_passed else 1)
