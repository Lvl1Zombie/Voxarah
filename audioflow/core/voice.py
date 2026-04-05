"""
Voxarah — Voice Engine
Text-to-speech using Windows SAPI / OneCore voices.
Targets Microsoft Ava (Natural) for high-quality AI coaching voice.

Requires: pyttsx3  (pip install pyttsx3)
Fallback: No speech if pyttsx3 or voices unavailable.
"""

import threading
from typing import Optional, Callable

try:
    import pyttsx3
    PYTTSX3_OK = True
except ImportError:
    PYTTSX3_OK = False


# ── Voice configuration ───────────────────────────────────────────────────────

# Preferred voices in priority order.
# "Natural" voices are the high-quality OneCore neural voices on Win10/11.
PREFERRED_VOICES = [
    "Ava (Natural)",       # Best quality — Windows 11
    "Ava",                 # Standard Ava
    "Jenny (Natural)",     # Alternative natural voice
    "Aria (Natural)",      # Another natural option
    "Zira",                # Classic Windows voice (always available)
]

DEFAULT_RATE = 170   # words per minute — slightly slower than default for coaching
DEFAULT_VOLUME = 0.9


class VoiceEngine:
    """
    Manages text-to-speech for coaching feedback.
    Runs speech in a background thread so the UI never blocks.
    """

    def __init__(self):
        self._engine = None
        self._voice_name = None
        self._available = False
        self._speaking = False
        self._lock = threading.Lock()
        self._thread = None

        self._init_engine()

    def _init_engine(self):
        """Initialize pyttsx3 and select the best available voice."""
        if not PYTTSX3_OK:
            return

        try:
            self._engine = pyttsx3.init("sapi5")
            self._engine.setProperty("rate", DEFAULT_RATE)
            self._engine.setProperty("volume", DEFAULT_VOLUME)

            voices = self._engine.getProperty("voices")
            voice_map = {}
            for v in voices:
                voice_map[v.name] = v.id
                # Also match partial names
                for part in v.name.split(" - "):
                    voice_map[part.strip()] = v.id

            # Pick the best available voice
            for pref in PREFERRED_VOICES:
                for name, vid in voice_map.items():
                    if pref.lower() in name.lower():
                        self._engine.setProperty("voice", vid)
                        self._voice_name = name
                        self._available = True
                        return

            # Fall back to first available voice
            if voices:
                self._engine.setProperty("voice", voices[0].id)
                self._voice_name = voices[0].name
                self._available = True

        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def voice_name(self) -> str:
        return self._voice_name or "None"

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def get_available_voices(self) -> list:
        """Return list of all available voice names."""
        if not self._engine:
            return []
        try:
            voices = self._engine.getProperty("voices")
            return [v.name for v in voices]
        except Exception:
            return []

    def set_voice(self, name: str) -> bool:
        """Set voice by partial name match. Returns True if found."""
        if not self._engine:
            return False
        try:
            voices = self._engine.getProperty("voices")
            for v in voices:
                if name.lower() in v.name.lower():
                    self._engine.setProperty("voice", v.id)
                    self._voice_name = v.name
                    return True
            return False
        except Exception:
            return False

    def set_rate(self, wpm: int):
        """Set speech rate in words per minute."""
        if self._engine:
            self._engine.setProperty("rate", wpm)

    def set_volume(self, vol: float):
        """Set volume 0.0 - 1.0."""
        if self._engine:
            self._engine.setProperty("volume", max(0.0, min(1.0, vol)))

    def speak(self, text: str, done_callback: Optional[Callable] = None):
        """
        Speak text in a background thread.
        done_callback() is called when speech finishes.
        """
        if not self._available or self._speaking:
            if done_callback:
                done_callback()
            return

        def _run():
            self._speaking = True
            try:
                # pyttsx3 needs its own engine per thread on Windows
                engine = pyttsx3.init("sapi5")
                engine.setProperty("rate", self._engine.getProperty("rate"))
                engine.setProperty("volume", self._engine.getProperty("volume"))

                # Copy voice setting
                if self._voice_name:
                    for v in engine.getProperty("voices"):
                        if self._voice_name.lower() in v.name.lower():
                            engine.setProperty("voice", v.id)
                            break

                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception:
                pass
            finally:
                self._speaking = False
                if done_callback:
                    done_callback()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop current speech."""
        self._speaking = False
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    def speak_coaching(self, text: str, done_callback: Optional[Callable] = None):
        """
        Speak coaching text with natural pauses.
        Strips any markdown-like formatting before speaking.
        """
        # Clean up text for speech
        clean = text
        clean = clean.replace("**", "")
        clean = clean.replace("*", "")
        clean = clean.replace("#", "")
        clean = clean.replace("- ", "")
        clean = clean.replace("•", "")

        # Add natural pauses at paragraph breaks
        clean = clean.replace("\n\n", " ... ")
        clean = clean.replace("\n", " ")

        # Remove any bracketed error messages
        import re
        clean = re.sub(r'\[.*?\]', '', clean)
        clean = clean.strip()

        if clean:
            self.speak(clean, done_callback)
        elif done_callback:
            done_callback()
