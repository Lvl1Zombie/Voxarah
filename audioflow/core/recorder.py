"""
Voxarah — Recording Engine
Microphone recording using sounddevice (PortAudio).
"""

import wave
import threading
import time
import tempfile
from typing import Optional

try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_OK = True
except ImportError:
    SOUNDDEVICE_OK = False


SAMPLE_RATE = 44100
CHANNELS    = 1


class VoxRecorder:
    """Thread-safe microphone recorder. Call start() then stop() -> WAV path."""

    def __init__(self):
        self._recording   = False
        self._frames      = []
        self._start_time  = 0.0
        self._stream      = None
        self._lock        = threading.Lock()

    @property
    def available(self) -> bool:
        return SOUNDDEVICE_OK

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed_seconds(self) -> float:
        if not self._recording:
            return 0.0
        return time.monotonic() - self._start_time

    def start(self) -> bool:
        """Start capturing from the default input device. Returns True on success."""
        if not SOUNDDEVICE_OK or self._recording:
            return False

        self._frames      = []
        self._start_time  = time.monotonic()
        self._recording   = True

        def _callback(indata, frames, time_info, status):
            if self._recording:
                with self._lock:
                    self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                callback=_callback,
                blocksize=1024,
            )
            self._stream.start()
            return True
        except Exception:
            self._recording = False
            return False

    def stop(self) -> Optional[str]:
        """
        Stop recording. Saves audio to a temp WAV file and returns the path.
        Returns None if recording was empty or saving failed.
        """
        if not self._recording:
            return None

        self._recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            frames = list(self._frames)

        if not frames:
            return None

        try:
            audio = np.concatenate(frames, axis=0)
            path  = tempfile.mktemp(suffix=".wav")
            with wave.open(path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)          # 16-bit = 2 bytes
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio.tobytes())
            return path
        except Exception:
            return None
