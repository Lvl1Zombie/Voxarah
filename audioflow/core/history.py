"""
Voxarah — Session History
Persists coaching scores across sessions so students can track improvement.
"""

import json
import os
from datetime import datetime
from typing import List, Dict

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".voxarah_history.json")
MAX_SESSIONS  = 200


def save_session(record: dict):
    """Append a session record. Keeps the last MAX_SESSIONS entries."""
    history = load_history()
    history.append(record)
    if len(history) > MAX_SESSIONS:
        history = history[-MAX_SESSIONS:]
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def load_history() -> List[Dict]:
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def build_record(filename: str, profile: str,
                 report: dict, results: dict) -> dict:
    """
    Build a history record from a completed analysis + coaching report.
    Call this right after score_recording() returns.
    """
    stats       = results.get("stats", {})
    pitch_stats = results.get("pitch_stats", {})
    return {
        "date":          datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filename":      os.path.basename(filename) if filename else "recording",
        "profile":       profile,
        "overall":       report.get("overall", 0),
        "grade":         report.get("grade", "—"),
        "duration":      round(results.get("duration", 0), 1),
        "scores":        dict(report.get("scores", {})),
        "stutter_count": stats.get("stutter_count", 0),
        "breath_count":  stats.get("breath_count", 0),
        "mouth_noise_count": stats.get("mouth_noise_count", 0),
        "pause_count":   stats.get("pause_count", 0),
        "pitch_rating":  pitch_stats.get("rating", ""),
        "pitch_std_hz":  round(pitch_stats.get("std_hz", 0.0), 1),
    }
