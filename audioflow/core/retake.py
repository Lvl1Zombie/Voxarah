"""
Voxarah — Retake Prompt Engine
Finds the worst region(s) of a recording and generates specific retake guidance.
"""

from typing import List, Dict

# Issue severity weights — how much each type hurts a take
_WEIGHTS = {
    'stutter':     3.0,
    'mouth_noise': 2.5,
    'unclear':     2.0,
    'breath':      1.5,
    'pause':       1.0,
}

# Human-readable labels for issue types
_LABELS = {
    'stutter':     'stutter',
    'mouth_noise': 'mouth noise',
    'unclear':     'unclear audio',
    'breath':      'audible breath',
    'pause':       'long pause',
}

_LABELS_PLURAL = {
    'stutter':     'stutters',
    'mouth_noise': 'mouth noises',
    'unclear':     'unclear sections',
    'breath':      'audible breaths',
    'pause':       'long pauses',
}


def find_retake_regions(results: dict, report: dict,
                        window_sec: float = 8.0,
                        top_n: int = 2) -> List[Dict]:
    """
    Analyse the recording and return up to `top_n` retake suggestions.

    Each suggestion is a dict:
        start       float  — region start in seconds
        end         float  — region end in seconds
        score       float  — weighted issue density (higher = worse)
        dominant    str    — most common issue type in this region
        counts      dict   — {issue_type: count} for all types in region
        reason      str    — plain-English coaching note
        label       str    — short label e.g. "0:14 – 0:22"

    Returns [] if the recording is clean enough to skip a retake.
    """
    overall = report.get("overall", 100)
    all_edits = results.get("all_edits", [])
    duration  = results.get("duration", 0.0)

    # Clean take — no retake needed
    if overall >= 88 or not all_edits or duration < 2.0:
        return []

    # ── Bucket edits into overlapping windows ────────────────────
    step = window_sec / 2.0
    windows = []
    t = 0.0
    while t < duration:
        w_end    = min(t + window_sec, duration)
        in_window = [e for e in all_edits
                     if e.get("start", 0) >= t and e.get("start", 0) < w_end]

        if in_window:
            # Weighted score for this window
            score = sum(_WEIGHTS.get(e.get("type", ""), 1.0) for e in in_window)
            # Count by type
            counts: Dict[str, int] = {}
            for e in in_window:
                etype = e.get("type", "unknown")
                counts[etype] = counts.get(etype, 0) + 1
            windows.append({
                "start":  t,
                "end":    w_end,
                "score":  score,
                "counts": counts,
            })
        t += step

    if not windows:
        return []

    # ── Pick top_n non-overlapping windows ────────────────────────
    windows.sort(key=lambda w: w["score"], reverse=True)
    selected = []
    for w in windows:
        # Skip if overlaps with an already-selected window
        overlap = any(
            not (w["end"] <= s["start"] or w["start"] >= s["end"])
            for s in selected
        )
        if not overlap:
            selected.append(w)
        if len(selected) >= top_n:
            break

    # ── Build human-readable retake suggestions ───────────────────
    suggestions = []
    for w in selected:
        counts  = w["counts"]
        dominant = max(counts, key=lambda k: counts[k] * _WEIGHTS.get(k, 1.0))
        total   = sum(counts.values())

        start_fmt = _fmt_time(w["start"])
        end_fmt   = _fmt_time(w["end"])
        label     = f"{start_fmt} – {end_fmt}"

        reason = _build_reason(dominant, counts, total, overall, report)

        suggestions.append({
            "start":    w["start"],
            "end":      w["end"],
            "score":    w["score"],
            "dominant": dominant,
            "counts":   counts,
            "reason":   reason,
            "label":    label,
        })

    return suggestions


def _build_reason(dominant: str, counts: Dict[str, int],
                  total: int, overall: int, report: dict) -> str:
    """Generate a specific, coach-voiced retake instruction."""
    dom_count = counts.get(dominant, 1)
    dom_label = (_LABELS_PLURAL[dominant] if dom_count > 1
                 else _LABELS[dominant]) if dominant in _LABELS else dominant

    # Build the issue list for the reason string
    parts = []
    for itype in ('stutter', 'mouth_noise', 'unclear', 'breath', 'pause'):
        n = counts.get(itype, 0)
        if n:
            lbl = _LABELS_PLURAL[itype] if n > 1 else _LABELS[itype]
            parts.append(f"{n} {lbl}")

    issues_str = ", ".join(parts) if parts else f"{total} issues"

    instructions = {
        'stutter': (
            "Slow down through this section. Take a breath before it, "
            "then speak each word with intention — don't rush to fill the silence."
        ),
        'mouth_noise': (
            "Sip water before re-recording this section. "
            "Open your mouth slightly between words and relax your jaw."
        ),
        'unclear': (
            "Over-articulate through this stretch — hit every consonant. "
            "It'll feel theatrical in the booth but sit perfectly on playback."
        ),
        'breath': (
            "Find your breath mark before this section starts, not during it. "
            "Take your full breath, then begin — don't inhale mid-line."
        ),
        'pause': (
            "The pauses here are breaking the momentum. "
            "Mark your breath points on the script and commit to the pacing."
        ),
    }

    instruction = instructions.get(dominant,
        "Re-record this section with fresh focus.")

    return f"{issues_str} in this stretch.  {instruction}"


def retake_summary(suggestions: List[Dict], overall: int) -> str:
    """
    One-line summary for the top of the retake guide.
    """
    if not suggestions:
        if overall >= 88:
            return "Strong take — no retake needed."
        return "Good take overall — minor issues only."

    if len(suggestions) == 1:
        s = suggestions[0]
        return (f"Focus your next take on {s['label']}. "
                f"That's where this recording loses the most points.")

    labels = " and ".join(s["label"] for s in suggestions)
    return (f"Two sections need attention: {labels}. "
            f"Fix those and your score jumps significantly.")


# ── Helpers ──────────────────────────────────────────────────────

def _fmt_time(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}:{s:02d}"
