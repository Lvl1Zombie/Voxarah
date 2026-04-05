"""
Voxarah — Audacity Bridge
Communicates with Audacity via mod-script-pipe (Windows named pipes).

REQUIREMENTS:
  1. Audacity must be open
  2. In Audacity: Edit → Preferences → Modules → Enable mod-script-pipe → Restart Audacity
"""

import os
import time
import threading
from typing import Optional, Callable

# Windows named pipe paths
PIPE_TO_AUDACITY   = "\\\\.\\pipe\\ToSrvPipe"
PIPE_FROM_AUDACITY = "\\\\.\\pipe\\FromSrvPipe"

EOL = "\r\n"


class AudacityBridge:
    def __init__(self, log_callback: Optional[Callable] = None):
        self._lock = threading.Lock()
        self._pipe_in  = None
        self._pipe_out = None
        self.connected = False
        self.log = log_callback or print

    # ── Connection ────────────────────────────────────────────────

    def connect(self) -> bool:
        """Open the named pipes. Returns True on success."""
        try:
            self._pipe_in  = open(PIPE_TO_AUDACITY,   'w')
            self._pipe_out = open(PIPE_FROM_AUDACITY,  'r')
            self.connected = True
            self.log("✅ Connected to Audacity")
            return True
        except FileNotFoundError:
            self.log(
                "❌ Cannot find Audacity pipe.\n"
                "   Make sure Audacity is open and mod-script-pipe is enabled.\n"
                "   Go to: Edit → Preferences → Modules → mod-script-pipe → Enabled → OK\n"
                "   Then fully restart Audacity."
            )
            self.connected = False
            return False
        except Exception as e:
            self.log(f"❌ Pipe error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        try:
            if self._pipe_in:  self._pipe_in.close()
            if self._pipe_out: self._pipe_out.close()
        except Exception:
            pass
        self.connected = False

    # ── Raw Command ───────────────────────────────────────────────

    def send(self, command: str) -> str:
        """Send a scripting command and return Audacity's response."""
        if not self.connected:
            return "NOT_CONNECTED"
        with self._lock:
            try:
                self._pipe_in.write(command + EOL)
                self._pipe_in.flush()
                response_lines = []
                while True:
                    line = self._pipe_out.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line == "BatchCommand finished: OK":
                        break
                    if line == "BatchCommand finished: Failed":
                        break
                    if line:
                        response_lines.append(line)
                return "\n".join(response_lines)
            except Exception as e:
                self.log(f"⚠️  Pipe send error: {e}")
                self.connected = False
                return f"ERROR: {e}"

    # ── Audacity Commands ─────────────────────────────────────────

    def get_info(self) -> str:
        return self.send("GetInfo: Type=Tracks")

    def select_time(self, start: float, end: float):
        self.send(f"SelectTime: Start={start:.4f} End={end:.4f} RelativeTo=ProjectStart")

    def select_all(self):
        self.send("SelectAll:")

    def zoom_to_selection(self):
        self.send("ZoomSel:")

    def delete_selection(self):
        self.send("Delete:")

    def silence_selection(self):
        self.send("Silence:")

    def add_label(self, start: float, end: float, text: str):
        """Add a label track label at the given time range."""
        self.select_time(start, end)
        # Add label at cursor
        self.send(f"AddLabel:")
        self.send(f"SetLabel: Label=0 Text=\"{text}\" Start={start:.4f} End={end:.4f}")

    def import_labels(self, filepath: str):
        """Import a label file into Audacity."""
        path = filepath.replace("\\", "/")
        self.send(f'ImportLabels: Filename="{path}"')

    def zoom_in(self):
        self.send("ZoomIn:")

    def zoom_out(self):
        self.send("ZoomOut:")

    def zoom_normal(self):
        self.send("Zoom: Factor=2")

    def fit_in_window(self):
        self.send("FitInWindow:")

    def play(self):
        self.send("Play:")

    def stop(self):
        self.send("Stop:")

    def undo(self):
        self.send("Undo:")

    def redo(self):
        self.send("Redo:")

    def export_wav(self, filepath: str):
        path = filepath.replace("\\", "/")
        self.send(f'Export2: Filename="{path}" NumChannels=1')

    # ── High-Level Edit Operations ────────────────────────────────

    def trim_silence(self, start: float, end: float, trim_to: float):
        """
        Replace a long silence [start, end] with a shorter silence of trim_to seconds.
        We select the excess portion and delete it.
        """
        excess_start = start + trim_to
        if excess_start >= end:
            return
        self.select_time(excess_start, end)
        self.delete_selection()
        self.log(f"   ✂️  Trimmed pause {start:.2f}s–{end:.2f}s → kept {trim_to:.1f}s")

    def highlight_for_review(self, start: float, end: float, label: str):
        """
        Add a label so the section is visible in Audacity for human review.
        Does NOT delete or alter the audio.
        """
        self.add_label(start, end, label)
        self.log(f"   🏷  Labeled {start:.2f}s–{end:.2f}s: {label}")

    def apply_edits_batch(self, edits: list, trim_to: float,
                          progress_callback: Optional[Callable] = None):
        """
        Apply a list of edit dicts to Audacity.
        edit dict keys: type ('pause'|'stutter'|'unclear'), start, end, desc
        Pauses are trimmed; stutters/unclear are labeled for review.
        """
        total = len(edits)
        self.log(f"\n🚀 Applying {total} edit(s) to Audacity...")

        # We must apply in REVERSE order so time offsets don't shift
        pauses  = sorted([e for e in edits if e['type'] == 'pause'],
                         key=lambda x: x['start'], reverse=True)
        flags   = [e for e in edits if e['type'] != 'pause']

        done = 0

        # Trim pauses first (reverse order to preserve timing)
        for edit in pauses:
            self.trim_silence(edit['start'], edit['end'], trim_to)
            done += 1
            if progress_callback:
                progress_callback(done / total)
            time.sleep(0.05)  # small delay so Audacity can keep up

        # Add labels for stutters / unclear
        for edit in flags:
            label_text = f"[{edit['type'].upper()}] {edit['desc']}"
            self.highlight_for_review(edit['start'], edit['end'], label_text)
            done += 1
            if progress_callback:
                progress_callback(done / total)
            time.sleep(0.05)

        self.fit_in_window()
        self.log(f"\n✅ All edits applied. Check your Audacity window.")
