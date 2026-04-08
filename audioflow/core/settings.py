"""
Voxarah — Settings Manager
Persists all user settings to a local JSON file.
"""

import json
import os

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".voxarah_settings.json")

DEFAULTS = {
    # ── Analysis Settings ──────────────────────────────────────────
    "silence_threshold_db":    -40,     # dB below which is "silence"
    "min_silence_duration":    0.15,    # seconds — ignore very brief dips
    "max_pause_duration":      1.0,     # seconds — trim pauses longer than this
    "stutter_window":          0.8,     # seconds — look-back window for stutter detection
    "detect_stutters":         True,
    "detect_unclear":          True,
    "detect_breaths":          True,
    "detect_mouth_noises":     True,

    # ── Coaching Settings ──────────────────────────────────────────
    "coaching_profile":        "Narrator / Documentary",
    "show_coaching_tips":      True,

    # ── UI Settings ───────────────────────────────────────────────
    "theme":                   "dark",
    "log_verbosity":           "normal",  # "quiet" | "normal" | "verbose"
    "auto_analyze_on_load":    False,
    "ui_text_color":           "#e0e0e0",  # primary text color

    # ── Update Settings ────────────────────────────────────────────
    "auto_update_check":       True,
    "update_manifest_url":     "",
    "last_seen_version":       "",
}


class SettingsManager:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                # Merge saved over defaults (so new keys always appear)
                self._data.update(saved)
        except Exception:
            pass  # silently fall back to defaults

    def save(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Warning: could not save settings: {e}")

    def get(self, key, fallback=None):
        return self._data.get(key, DEFAULTS.get(key, fallback))

    def set(self, key, value):
        self._data[key] = value

    def set_many(self, updates: dict):
        self._data.update(updates)

    def reset_to_defaults(self):
        self._data = dict(DEFAULTS)
        self.save()

    def as_dict(self) -> dict:
        return dict(self._data)

    def analysis_settings(self) -> dict:
        keys = [
            "silence_threshold_db", "min_silence_duration",
            "max_pause_duration", "stutter_window",
            "detect_stutters", "detect_unclear",
            "detect_breaths", "detect_mouth_noises"
        ]
        return {k: self.get(k) for k in keys}
