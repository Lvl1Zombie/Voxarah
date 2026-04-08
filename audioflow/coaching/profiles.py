"""
Voxarah — Vocal Coaching Engine
Compares recordings against 6 professional voice style profiles and gives feedback.
"""

import math
import numpy as np
from typing import Dict, List, Tuple


# ── Style Profiles ────────────────────────────────────────────────────────────
# Each profile defines target acoustic benchmarks:
#   - speech_rate_wpm     : target words per minute (estimated from syllable density)
#   - pause_ratio         : fraction of total time that is silence (ideal range)
#   - energy_consistency  : how steady the RMS level should be (0=wildly varied, 1=flat)
#   - dynamic_range_db    : ideal dB difference between quiet and loud moments
#   - max_long_pause_sec  : acceptable longest single pause
#   - stutter_tolerance   : fraction of flagged stutter regions that's still OK
#   - clarity_floor_db    : minimum average level for speech segments
#   - description         : shown in UI

VOICE_PROFILES = {
    "Calm / Soothing": {
        "description": "Gentle, measured pace. Used for meditation, ASMR, wellness content.",
        "emoji": "🌙",
        "speech_rate_wpm":     (85, 135),
        "pause_ratio":         (0.15, 0.35),
        "energy_consistency": (0.15, 0.40),
        "dynamic_range_db":   (8, 25),
        "max_long_pause_sec":  3.0,
        "stutter_tolerance":   0.02,
        "clarity_floor_db":   -42,
        "tips": [
            "Speak slower than feels natural — listeners need time to absorb calm content.",
            "Avoid sudden energy spikes; keep your volume even throughout.",
            "Longer pauses (1–2s) are a feature, not a flaw, in soothing reads.",
        ]
    },
    "Energetic / Hype": {
        "description": "High energy, fast pace, punchy delivery. Promos, gaming, hype reels.",
        "emoji": "⚡",
        "speech_rate_wpm":     (155, 210),
        "pause_ratio":         (0.02, 0.15),
        "energy_consistency": (0.05, 0.25),
        "dynamic_range_db":   (15, 40),
        "max_long_pause_sec":  0.8,
        "stutter_tolerance":   0.01,
        "clarity_floor_db":   -38,
        "tips": [
            "Short, punchy sentences drive energy. Cut filler ruthlessly.",
            "Use dynamic contrast — build UP to key words, don't stay flat.",
            "Pauses longer than 0.5s kill momentum in hype reads.",
        ]
    },
    "Narrator / Documentary": {
        "description": "Authoritative, clear, even-paced. Nature docs, explainers, journalism.",
        "emoji": "🎬",
        "speech_rate_wpm":     (100, 175),
        "pause_ratio":         (0.05, 0.25),
        "energy_consistency": (0.03, 0.30),
        "dynamic_range_db":   (11, 36),
        "max_long_pause_sec":  2.0,
        "stutter_tolerance":   0.005,
        "clarity_floor_db":   -42,
        "tips": [
            "Narration tolerates zero stutters — re-record any hesitations.",
            "Consistency is king: listeners trust a steady, reliable voice.",
            "Emphasize subject words; verbs and prepositions can stay soft.",
        ]
    },
    "Commercial / Salesy": {
        "description": "Warm, persuasive, confident. Ads, promos, product demos.",
        "emoji": "📣",
        "speech_rate_wpm":     (130, 180),
        "pause_ratio":         (0.05, 0.20),
        "energy_consistency": (0.08, 0.30),
        "dynamic_range_db":   (12, 32),
        "max_long_pause_sec":  1.2,
        "stutter_tolerance":   0.01,
        "clarity_floor_db":   -40,
        "tips": [
            "Smile while recording — it literally changes your vocal tone.",
            "Land hard on the brand name or call-to-action every time.",
            "Keep pauses short and intentional — silence feels like doubt in ads.",
        ]
    },
    "Character / Animation": {
        "description": "Expressive, varied, playful. Cartoons, games, audiodramas.",
        "emoji": "🎭",
        "speech_rate_wpm":     (90, 200),    # wide range — character dependent
        "pause_ratio":         (0.05, 0.30),
        "energy_consistency": (0.00, 0.20),  # variation is good here
        "dynamic_range_db":   (20, 45),
        "max_long_pause_sec":  1.5,
        "stutter_tolerance":   0.03,          # some stutters are character choices
        "clarity_floor_db":   -42,
        "tips": [
            "Dynamic range is your superpower — use the full spectrum from whisper to shout.",
            "Commit fully to the character physicality even when just recording audio.",
            "Intentional stutters for a nervous character are fine — mark them as 'keep'.",
        ]
    },
    "Audiobook": {
        "description": "Clear, warm, immersive. Long-form narration for books and podcasts.",
        "emoji": "📚",
        "speech_rate_wpm":     (100, 175),
        "pause_ratio":         (0.05, 0.25),
        "energy_consistency": (0.03, 0.30),
        "dynamic_range_db":   (10, 35),
        "max_long_pause_sec":  2.0,
        "stutter_tolerance":   0.003,         # near zero — listeners will notice
        "clarity_floor_db":   -42,
        "tips": [
            "Consistency over hours is the hardest part — record in short sessions.",
            "Chapter breaks and paragraph pauses are separate from 'long pauses' — plan them.",
            "Any stutter breaks the listener's immersion; these all need re-records.",
        ]
    }
}


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_recording(results: dict, profile_name: str) -> Dict:
    """
    Score a recording against a voice profile.
    Returns a dict with per-dimension scores (0–100) and coaching feedback.
    """
    if profile_name not in VOICE_PROFILES:
        profile_name = "Narrator / Documentary"
    profile = VOICE_PROFILES[profile_name]

    samples  = results['samples']
    sr       = results['sample_rate']
    duration = results['duration']
    stats    = results['stats']
    silence_regions = results['silence_regions']

    scores   = {}
    feedback = []

    # ── 1. Pause Ratio ────────────────────────────────────────────
    total_silence = sum(r['end'] - r['start'] for r in silence_regions)
    pause_ratio   = total_silence / max(1.0, duration)
    lo, hi        = profile['pause_ratio']
    scores['pause_ratio'] = _range_score(pause_ratio, lo, hi)

    if pause_ratio < lo:
        feedback.append(("⚡ Pacing", f"You have very little silence ({pause_ratio*100:.0f}%). "
                         f"For {profile_name}, aim for {lo*100:.0f}–{hi*100:.0f}% breathing room."))
    elif pause_ratio > hi:
        feedback.append(("⏸ Pacing", f"Too much silence ({pause_ratio*100:.0f}% of your recording). "
                         f"Target is {lo*100:.0f}–{hi*100:.0f}%. Tighten your delivery."))

    # ── 2. Stutter Rate ───────────────────────────────────────────
    stutter_rate = stats['stutter_count'] / max(1.0, duration / 60.0)  # per minute
    tol = profile['stutter_tolerance'] * duration
    scores['stutters'] = max(0, 100 - int(stats['stutter_count'] / max(1, tol + 1) * 100))
    if stats['stutter_count'] > 0:
        feedback.append(("🔁 Delivery", f"{stats['stutter_count']} stutter(s) detected. "
                         f"{profile_name} style tolerates very few — these should be re-recorded."))

    # ── 3. Long Pause Length ──────────────────────────────────────
    max_allowed = profile['max_long_pause_sec']
    worst_pause = max((p['duration'] for p in results['long_pauses']), default=0.0)
    if worst_pause <= max_allowed:
        scores['pause_length'] = 100
    else:
        over = (worst_pause - max_allowed) / max_allowed
        scores['pause_length'] = max(0, int(100 - over * 80))
        feedback.append(("⏳ Pauses", f"Longest pause is {worst_pause:.1f}s. "
                         f"For {profile_name}, aim to keep them under {max_allowed:.1f}s."))

    # ── 4. Energy Consistency ─────────────────────────────────────
    frame_size = int(sr * 0.1)
    thresh = math.pow(10, profile['clarity_floor_db'] / 20.0)
    arr = np.asarray(samples, dtype=np.float32)
    n   = (len(arr) // frame_size) * frame_size
    frame_rms    = np.sqrt(np.mean(arr[:n].reshape(-1, frame_size) ** 2, axis=1))
    speech_levels = frame_rms[frame_rms > thresh].tolist()

    if len(speech_levels) > 4:
        mean_e    = float(np.mean(speech_levels))
        cv        = float(np.std(speech_levels)) / (mean_e + 1e-12)
        consistency = max(0.0, 1.0 - min(1.0, cv * 1.5))

        lo, hi = profile['energy_consistency']
        scores['consistency'] = _range_score(consistency, lo, hi)

        if consistency < lo:
            feedback.append(("📊 Energy", f"Your energy level varies too much ({consistency*100:.0f}% consistency). "
                             f"{profile_name} reads need {lo*100:.0f}–{hi*100:.0f}% consistency."))
        elif consistency > hi and hi < 0.80:
            feedback.append(("📊 Energy", f"Your delivery is very flat ({consistency*100:.0f}% consistency). "
                             f"{profile_name} style benefits from more dynamic variation."))
    else:
        scores['consistency'] = 70

    # ── 5. Clarity / Intelligibility ─────────────────────────────
    clarity_floor = math.pow(10, profile['clarity_floor_db'] / 20.0)
    unclear_count = stats['unclear_count']
    unclear_frac  = unclear_count / max(1.0, duration / 10.0)  # per 10s
    scores['clarity'] = max(0, int(100 - unclear_frac * 40))

    if unclear_count > 0:
        feedback.append(("🔊 Clarity", f"{unclear_count} section(s) may be too quiet or unclear. "
                         f"Check your mic distance and consider re-recording these sections."))

    # ── Overall Score ─────────────────────────────────────────────
    weights = {'pause_ratio': 0.25, 'stutters': 0.30, 'pause_length': 0.20,
               'consistency': 0.15, 'clarity': 0.10}
    overall = int(sum(scores[k] * weights[k] for k in weights))

    # ── Style Match Tips ──────────────────────────────────────────
    tips = profile['tips']

    return {
        'profile':  profile_name,
        'overall':  overall,
        'scores':   scores,
        'feedback': feedback,
        'tips':     tips,
        'grade':    _grade(overall),
        'profile_desc': profile['description'],
        'profile_emoji': profile['emoji'],
    }


def _range_score(value: float, lo: float, hi: float) -> int:
    """
    Bell-curve score: 100 at the midpoint of [lo, hi], tapering to 60
    at the edges, and continuing to drop outside the range.

    Uses a Gaussian:  score = 100 * exp(-k * ((value - mid) / hw)^2)
    where k = -ln(0.6) ≈ 0.5108  so that score(lo) = score(hi) = 60.
    """
    mid = (lo + hi) / 2.0
    hw  = (hi - lo) / 2.0 + 1e-12          # half-width; avoid /0
    k   = 0.5108                             # -ln(0.6)
    z   = (value - mid) / hw
    return max(0, min(100, int(100 * math.exp(-k * z * z))))


def _grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def get_all_profiles() -> List[str]:
    return list(VOICE_PROFILES.keys())


def get_profile_info(name: str) -> Dict:
    return VOICE_PROFILES.get(name, {})
