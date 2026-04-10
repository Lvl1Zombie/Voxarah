"""
Voxarah — Vocal Coaching Engine
Compares recordings against 6 professional voice style profiles and gives feedback.
"""

import math
import numpy as np
from typing import Dict, List, Tuple

try:
    from coaching.measured_benchmarks import MEASURED_PROFILES as _MEASURED
except ImportError:
    _MEASURED = {}

# Keys that measured_benchmarks calibrates — prefer those values when available
_CALIBRATED_KEYS = (
    "speech_rate_wpm", "pause_ratio", "energy_consistency",
    "dynamic_range_db", "max_long_pause_sec", "stutter_tolerance",
    "clarity_floor_db",
)


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
        "pitch_std_hz":        (6, 18),   # gentle, small pitch movement
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
        "pitch_std_hz":        (22, 60),  # big pitch swings needed
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
        "pitch_std_hz":        (12, 32),  # moderate natural variation
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
        "pitch_std_hz":        (16, 42),  # variation sells
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
        "pitch_std_hz":        (28, 80),  # maximum expressiveness
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
        "pitch_std_hz":        (12, 32),  # natural storytelling variation
        "tips": [
            "Consistency over hours is the hardest part — record in short sessions.",
            "Chapter breaks and paragraph pauses are separate from 'long pauses' — plan them.",
            "Any stutter breaks the listener's immersion; these all need re-records.",
        ]
    },
    "Children's Storyteller": {
        "description": "Warm, expressive, playful. Keeps young listeners engaged through vocal variety and clear pacing.",
        "emoji": "🧸",
        "speech_rate_wpm":     (100, 155),   # slower than adult — kids need processing time
        "pause_ratio":         (0.12, 0.35), # generous pauses — let imagination catch up
        "energy_consistency": (0.00, 0.25),  # variation is good — monotone loses kids fast
        "dynamic_range_db":   (18, 42),      # wide range for character voices and dramatic moments
        "max_long_pause_sec":  2.5,           # dramatic pauses are a storytelling tool
        "stutter_tolerance":   0.02,          # intentional character stumbles are fine
        "clarity_floor_db":   -40,
        "pitch_std_hz":        (24, 70),     # big pitch swings — wonder, suspense, excitement
        "tips": [
            "Slow down more than feels natural — children need extra time to visualize what they hear.",
            "Use pitch to signal characters: go higher for small/young characters, lower for big/scary ones.",
            "Pause before reveals and big moments — the anticipation is half the magic for kids.",
            "Vary your energy wildly between quiet suspense and big excited moments to hold attention.",
            "Smile on happy lines, whisper on secrets, get BIG on exciting moments — commit fully.",
            "Mouth noises and breaths are more forgivable here, but stutters break the story spell.",
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
    profile = dict(VOICE_PROFILES[profile_name])
    # Overlay calibrated benchmark values when available
    measured = _MEASURED.get(profile_name, {})
    for key in _CALIBRATED_KEYS:
        if key in measured:
            profile[key] = measured[key]

    samples  = results['samples']
    sr       = results['sample_rate']
    duration = results['duration']
    stats    = results['stats']
    silence_regions = results['silence_regions']

    scores   = {}
    feedback = []

    # ── 1. Pause Ratio / Pacing ───────────────────────────────────
    total_silence = sum(r['end'] - r['start'] for r in silence_regions)
    pause_ratio   = total_silence / max(1.0, duration)
    lo, hi        = profile['pause_ratio']
    scores['pause_ratio'] = _range_score(pause_ratio, lo, hi)

    if pause_ratio < lo:
        feedback.append(("⚡ Pacing",
            f"Only {pause_ratio*100:.0f}% of your recording is silence — you're rushing. "
            f"A {profile_name} read needs {lo*100:.0f}–{hi*100:.0f}% breathing room. "
            f"Listeners need white space to absorb what you're saying. Slow down and let the words land."))
    elif pause_ratio > hi:
        feedback.append(("⏸ Pacing",
            f"Silence is eating {pause_ratio*100:.0f}% of your recording — too much dead air. "
            f"The target for {profile_name} is {lo*100:.0f}–{hi*100:.0f}%. "
            f"Tighten the gaps between thoughts and keep the energy moving."))

    # ── 2. Stutters / Delivery ────────────────────────────────────
    tol = profile['stutter_tolerance'] * duration
    scores['stutters'] = max(0, 100 - int(stats['stutter_count'] / max(1, tol + 1) * 100))
    n_st = stats['stutter_count']
    if n_st > 0:
        per_min = n_st / max(1.0, duration / 60.0)
        feedback.append(("🔁 Delivery",
            f"{n_st} stutter{'s' if n_st > 1 else ''} detected ({per_min:.1f}/min). "
            f"Each one chips away at your authority and the listener's trust. "
            f"Mark these timestamps, re-read those lines cold, and punch in on the clean takes."))

    # ── 3. Long Pause Length ──────────────────────────────────────
    max_allowed = profile['max_long_pause_sec']
    worst_pause = max((p['duration'] for p in results['long_pauses']), default=0.0)
    if worst_pause <= max_allowed:
        scores['pause_length'] = 100
    else:
        over = (worst_pause - max_allowed) / max_allowed
        scores['pause_length'] = max(0, int(100 - over * 80))
        feedback.append(("⏳ Pauses",
            f"Your longest pause is {worst_pause:.1f}s — {profile_name} shouldn't exceed {max_allowed:.1f}s. "
            f"A pause that long signals you lost your place. "
            f"Prep your copy better and mark breath points before you hit record."))

    # ── 4. Energy Consistency ─────────────────────────────────────
    frame_size = int(sr * 0.1)
    thresh = math.pow(10, profile['clarity_floor_db'] / 20.0)
    arr = np.asarray(samples, dtype=np.float32)
    n   = (len(arr) // frame_size) * frame_size
    frame_rms     = np.sqrt(np.mean(arr[:n].reshape(-1, frame_size) ** 2, axis=1))
    speech_levels = frame_rms[frame_rms > thresh].tolist()

    if len(speech_levels) > 4:
        mean_e      = float(np.mean(speech_levels))
        cv          = float(np.std(speech_levels)) / (mean_e + 1e-12)
        consistency = max(0.0, 1.0 - min(1.0, cv * 1.5))

        # Detect where energy drops — compare first vs second half
        mid = len(speech_levels) // 2
        first_half  = float(np.mean(speech_levels[:mid]))  if mid > 0 else mean_e
        second_half = float(np.mean(speech_levels[mid:]))  if mid > 0 else mean_e
        drop_pct    = (first_half - second_half) / (first_half + 1e-12) * 100

        lo, hi = profile['energy_consistency']
        scores['consistency'] = _range_score(consistency, lo, hi)

        if consistency < lo:
            if drop_pct > 15:
                feedback.append(("📊 Energy",
                    f"Your energy drops {drop_pct:.0f}% in the second half of the recording. "
                    f"Listeners subconsciously check out when the voice fades — "
                    f"stay committed to the last word as hard as the first."))
            else:
                feedback.append(("📊 Energy",
                    f"Your volume is inconsistent throughout ({consistency*100:.0f}% steady). "
                    f"{profile_name} needs {lo*100:.0f}–{hi*100:.0f}% consistency. "
                    f"Work on diaphragm support — your breath is running out before your sentences do."))
        elif consistency > hi and hi < 0.80:
            feedback.append(("📊 Energy",
                f"Your delivery is too even ({consistency*100:.0f}% flat). "
                f"{profile_name} needs dynamic variation to hold attention. "
                f"Find the emotional peak of each sentence and lean into it."))
    else:
        scores['consistency'] = 70

    # ── 5. Clarity / Intelligibility ─────────────────────────────
    unclear_count = stats['unclear_count']
    unclear_frac  = unclear_count / max(1.0, duration / 10.0)
    scores['clarity'] = max(0, int(100 - unclear_frac * 40))

    if unclear_count > 0:
        feedback.append(("🔊 Clarity",
            f"{unclear_count} section{'s' if unclear_count > 1 else ''} dropped below intelligible level. "
            f"This is usually mic distance, room noise, or you trailing off at the end of lines. "
            f"Check your gain staging and stay on-axis with your mic throughout the take."))

    # ── 6. Pitch Variation ────────────────────────────────────────
    pitch_stats = results.get('pitch_stats', {})
    if pitch_stats and pitch_stats.get('mean_hz', 0) > 0:
        std_hz  = pitch_stats.get('std_hz', 0.0)
        rating  = pitch_stats.get('rating', '')
        lo, hi  = profile.get('pitch_std_hz', (12, 32))
        scores['pitch'] = _range_score(std_hz, lo, hi)

        if std_hz < lo * 0.75:
            feedback.append(("🎵 Pitch",
                f"Your pitch is very flat (±{std_hz:.0f} Hz). You're reading — not performing. "
                f"A {profile_name} needs at least ±{lo:.0f} Hz of movement to sound alive. "
                f"Find the stressed word in every sentence and let your pitch rise or fall into it."))
        elif std_hz < lo:
            feedback.append(("🎵 Pitch",
                f"Pitch variation is a little low (±{std_hz:.0f} Hz, target ±{lo:.0f}–{hi:.0f} Hz). "
                f"You're in the right direction — push slightly more into the emotional peaks."))
        elif std_hz > hi * 1.4:
            feedback.append(("🎵 Pitch",
                f"Your pitch swings widely (±{std_hz:.0f} Hz). "
                f"For {profile_name} that can sound erratic rather than expressive. "
                f"Channel the variation into key moments, not every word."))
    else:
        scores['pitch'] = 70   # no data — neutral score

    # ── 7. Breath Control ─────────────────────────────────────────
    n_br = stats.get('breath_count', 0)
    n_mn = stats.get('mouth_noise_count', 0)
    breath_per_min = n_br / max(1.0, duration / 60.0)

    if breath_per_min > 8:
        feedback.append(("💨 Breath",
            f"{n_br} audible breath{'s' if n_br > 1 else ''} detected "
            f"({breath_per_min:.0f}/min — above average). "
            f"Try breathing through your nose between takes, and record with a slight smile "
            f"to keep your airway open and quieter."))
    elif n_br > 0 and breath_per_min > 4:
        feedback.append(("💨 Breath",
            f"{n_br} audible breath{'s' if n_br > 1 else ''} picked up. "
            f"Not a dealbreaker, but clean these in post — "
            f"the Edited playback already attenuates them for you."))

    if n_mn > 2:
        feedback.append(("👄 Mouth Noise",
            f"{n_mn} mouth clicks or smacks detected. "
            f"Drink room-temperature water before recording and avoid dairy beforehand. "
            f"These are already attenuated in your Edited version."))

    # ── Overall Score ─────────────────────────────────────────────
    weights = {'pause_ratio': 0.20, 'stutters': 0.25, 'pause_length': 0.15,
               'consistency': 0.15, 'clarity': 0.10, 'pitch': 0.15}
    overall = int(sum(scores.get(k, 70) * weights[k] for k in weights))

    # ── Children's Storyteller — extra engagement checks ─────────
    if profile_name == "Children's Storyteller":
        # Kids lose interest fast with flat energy — penalise monotone more
        if pitch_stats and pitch_stats.get('std_hz', 0) < 20:
            feedback.append(("🧸 Engagement",
                f"Your pitch is quite flat (±{pitch_stats.get('std_hz',0):.0f} Hz) for a children's story. "
                f"Kids disengage quickly without vocal variety. Try exaggerating your character voices "
                f"and letting your pitch rise on exciting words and drop on serious ones."))
        # Flag if too fast for kids
        wpm = stats.get('wpm', 0)
        if wpm and wpm > 155:
            feedback.append(("🧸 Engagement",
                f"At {wpm:.0f} WPM you're speaking faster than most children can comfortably follow. "
                f"Children's stories land best at 100–155 WPM. Slow down and let each image form."))
        # Reward good variation
        if pitch_stats and pitch_stats.get('std_hz', 0) > 35:
            feedback.append(("🧸 Engagement",
                f"Great vocal variety (±{pitch_stats.get('std_hz',0):.0f} Hz)! "
                f"That level of expressiveness is exactly what keeps young listeners locked in."))

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
