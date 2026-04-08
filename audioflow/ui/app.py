"""
Voxarah — Main Application
Full Lamborghini-inspired UI. Matte black + yellow. No softness.
"""

import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import tempfile
import shutil
import subprocess
import time

try:
    import sounddevice as _sd
    import numpy as _np
    _PLAYBACK_OK = True
except ImportError:
    _PLAYBACK_OK = False

from core.settings        import SettingsManager
from core.changelog       import CHANGELOG
from core.analyzer        import AudioAnalyzer, build_cleaned_wav, build_cleaned_samples, build_label_file
from core.recorder        import VoxRecorder
from core.ai_coach        import AICoach
from core.updater         import Updater
from core.voice           import VoiceEngine
from ui.design            import *
from ui.components        import (
    SectionLabel, HDivider, PrimaryButton, SecondaryButton, GhostButton,
    LamboSlider, LamboToggle, StatCard, BadgeLabel,
    WaveformCanvas, make_flag_tree, styled_scrollbar,
    make_notebook, make_log_text, log_append, LamboProgress, PanelSection
)
from ui.coaching_panel    import CoachingTabManager
from ui.compare_panel     import CompareTakesPanel

APP_VERSION = "2.1"


def fmt_time(sec):
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:04.1f}"


class AudioFlowApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Voxarah")
        self.configure(bg=BLACK)

        # Sync Tkinter's internal scaling to the actual monitor DPI so that
        # fonts and widgets render at native physical-pixel resolution instead
        # of being stretched/blurred by Windows' bitmap upscaling.
        self.update_idletasks()
        try:
            dpi = self.winfo_fpixels('1i')          # physical pixels per inch
            self.tk.call('tk', 'scaling', dpi / 72.0)
        except Exception:
            pass

        self.geometry("1160x760")
        self.minsize(960, 640)

        self.settings  = SettingsManager()
        self.recorder  = VoxRecorder()
        self._rec_temp_path = None
        self.ai_coach  = AICoach()
        self.voice     = VoiceEngine()
        self.updater   = Updater(current_version=APP_VERSION)
        self.results   = None
        self._wav_path = None

        # Playback state
        self._play_start_time  = 0.0
        self._play_duration    = 0.0
        self._play_active      = False
        self._cleaned_samples  = None   # cached after analysis

        self._build_titlebar()
        self._build_tabbar()
        self._build_body()
        self._build_status_bar()

        # Set window icon (title bar + taskbar)
        try:
            from PIL import Image, ImageTk
            _assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
            _ico_img = Image.open(os.path.join(_assets, "logo_hd.png")).convert("RGBA")
            _ico_photo = ImageTk.PhotoImage(_ico_img.resize((256, 256), Image.Resampling.LANCZOS))
            self.iconphoto(True, _ico_photo)
            self._icon_ref = _ico_photo  # prevent GC
        except Exception:
            pass

        # Force dark title bar on Windows 10/11
        self.after(50, self._set_dark_titlebar)

        self.after(1200, self._check_ollama_status)
        self.after(1800, self._check_for_updates)
        self.after(800,  self._check_patch_notes)

        # Thread-safe progress queue — background thread puts (fraction, msg),
        # main thread polls every 50 ms and updates the UI.
        self._progress_queue = queue.Queue()
        self._poll_progress()

    # ══════════════════════════════════════════════════════════════
    # TITLEBAR
    # ══════════════════════════════════════════════════════════════

    def _build_titlebar(self):
        # Top yellow racing stripe
        tk.Frame(self, bg=YELLOW, height=2).pack(fill="x", side="top")

        bar = tk.Frame(self, bg=BLACK, height=TITLEBAR_H)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        # Left yellow stripe
        tk.Frame(bar, bg=YELLOW, width=3).pack(side="left", fill="y")

        # Wordmark
        wm = tk.Frame(bar, bg=BLACK)
        wm.pack(side="left", padx=(14, 0))

        logo = tk.Canvas(wm, width=40, height=40, bg=BLACK, highlightthickness=0)
        logo.pack(side="left", padx=(0, 8))
        self._draw_logo(logo)

        tk.Label(wm, text="VOX",  font=("Segoe UI", 22, "bold"), fg=TEXT,   bg=BLACK, padx=0, bd=0).pack(side="left", padx=0)
        tk.Label(wm, text="A",    font=("Segoe UI", 22, "bold"), fg=YELLOW, bg=BLACK, padx=0, bd=0).pack(side="left", padx=0)
        tk.Label(wm, text="RAH",  font=("Segoe UI", 22, "bold"), fg=TEXT,   bg=BLACK, padx=0, bd=0).pack(side="left", padx=0)

        tk.Frame(bar, bg=EDGE, width=1).pack(side="left", fill="y", padx=14, pady=8)
        tk.Label(bar, text="VOICE PRODUCTION SUITE",
                 font=FONT_MONO, fg=TEXT, bg=BLACK).pack(side="left")


    def _draw_logo(self, canvas):
        try:
            from PIL import Image, ImageTk
            assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
            img = Image.open(os.path.join(assets_dir, "logo_hd.png")).convert("RGBA")
            img = img.resize((40, 40), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            canvas._logo_photo = photo  # prevent GC
            canvas.create_image(0, 0, anchor="nw", image=photo)
        except Exception:
            pass

    def _set_dark_titlebar(self):
        """Force dark title bar on Windows 10/11 via DWM API."""
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win10 20H1+)
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
            # Force a redraw so the title bar picks up the change
            self.withdraw()
            self.after(10, self.deiconify)
        except Exception:
            pass  # not on Windows or older Windows version

    # ══════════════════════════════════════════════════════════════
    # TAB BAR
    # ══════════════════════════════════════════════════════════════

    def _build_tabbar(self):
        bar = tk.Frame(self, bg=BLACK, height=TABBAR_H)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        self._tab_frames  = {}
        self._tab_btns    = {}
        self._tab_unders  = {}   # yellow underline frames
        self._active_tab  = None

        tabs = [
            ("editor",   "  EDITOR  "),
            ("coaching", "  COACHING  "),
            ("compare",  "  COMPARE  "),
            ("settings", "  SETTINGS  "),
        ]

        for key, label in tabs:
            wrap = tk.Frame(bar, bg=BLACK)
            wrap.pack(side="left")

            btn = tk.Label(wrap, text=label, font=FONT_TAB,
                           fg=TEXT_DIM, bg=BLACK, cursor="hand2", pady=6)
            btn.pack(side="top")
            btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            self._tab_btns[key] = btn

            under = tk.Frame(wrap, bg=BLACK, height=2)
            under.pack(fill="x", side="bottom")
            self._tab_unders[key] = under

        tk.Frame(bar, bg=EDGE, height=1).pack(side="bottom", fill="x")

    def _switch_tab(self, key):
        if self._active_tab == key:
            return
        self._active_tab = key
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.config(fg=YELLOW, bg=CARBON_2)
                self._tab_unders[k].config(bg=YELLOW)
                btn.master.config(bg=CARBON_2)
            else:
                btn.config(fg=TEXT_DIM, bg=BLACK)
                self._tab_unders[k].config(bg=BLACK)
                btn.master.config(bg=BLACK)
        for k, frame in self._tab_frames.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    # ══════════════════════════════════════════════════════════════
    # BODY
    # ══════════════════════════════════════════════════════════════

    def _build_body(self):
        self._body = tk.Frame(self, bg=CARBON_1)
        self._body.pack(fill="both", expand=True)

        self._tab_frames["editor"]   = tk.Frame(self._body, bg=CARBON_1)
        self._tab_frames["coaching"] = tk.Frame(self._body, bg=CARBON_1)
        self._tab_frames["compare"]  = tk.Frame(self._body, bg=CARBON_1)
        self._tab_frames["settings"] = tk.Frame(self._body, bg=CARBON_1)

        self._build_editor_tab()
        self._build_coaching_tab()
        self._build_compare_tab()
        self._build_settings_tab()

        self._switch_tab("editor")

    # ══════════════════════════════════════════════════════════════
    # STATUS BAR
    # ══════════════════════════════════════════════════════════════

    def _build_status_bar(self):
        tk.Frame(self, bg=EDGE, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg=BLACK, height=BOTTOM_BAR_H)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        def sep():
            tk.Frame(bar, bg=SEP_COLOR, width=1).pack(side="left", fill="y", pady=8)

        self._status_var = tk.StringVar(value="READY")
        tk.Label(bar, textvariable=self._status_var,
                 font=FONT_MONO, fg=TEXT, bg=BLACK).pack(side="left", padx=12)

        sep()
        self._format_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self._format_var,
                 font=FONT_MONO, fg=TEXT, bg=BLACK).pack(side="left", padx=12)

        # Right side — build right-to-left
        SecondaryButton(bar, "CHECK UPDATES", command=lambda: self._check_for_updates(forced=True)).pack(side="right", padx=(0, 12))

        tk.Frame(bar, bg=SEP_COLOR, width=1).pack(side="right", fill="y", pady=8)
        tk.Label(bar, text=f"VOXARAH  v{APP_VERSION}",
                 font=FONT_MONO, fg=TEXT, bg=BLACK).pack(side="right", padx=12)

        tk.Frame(bar, bg=SEP_COLOR, width=1).pack(side="right", fill="y", pady=8)
        ollama_frame = tk.Frame(bar, bg=BLACK)
        ollama_frame.pack(side="right", padx=12)
        self._ollama_canvas = tk.Canvas(ollama_frame, width=8, height=8,
                                         bg=BLACK, highlightthickness=0)
        self._ollama_canvas.pack(side="left", padx=(0, 4))
        self._ollama_dot = self._ollama_canvas.create_oval(1, 1, 7, 7,
                                                            fill=EDGE_BRIGHT, outline="")
        self._ollama_var = tk.StringVar(value="AI  OFFLINE")
        tk.Label(ollama_frame, textvariable=self._ollama_var,
                 font=FONT_MONO, fg=TEXT, bg=BLACK).pack(side="left")

        tk.Frame(bar, bg=SEP_COLOR, width=1).pack(side="right", fill="y", pady=8)
        self._ffmpeg_var = tk.StringVar(value="FFMPEG —")
        tk.Label(bar, textvariable=self._ffmpeg_var,
                 font=FONT_MONO, fg=TEXT, bg=BLACK).pack(side="right", padx=12)

    def _set_status(self, msg):
        self._status_var.set(msg.upper())
        self.update_idletasks()

    def _check_ollama_status(self):
        """Check Ollama availability in a background thread."""
        import threading
        def _check():
            online = self.ai_coach.check_status()
            self.after(0, lambda: self._update_ollama_indicator(online))
        threading.Thread(target=_check, daemon=True).start()

    def _update_ollama_indicator(self, online):
        color = YELLOW if online else EDGE_BRIGHT
        self._ollama_canvas.itemconfig(self._ollama_dot, fill=color)
        self._ollama_var.set("AI  LIVE" if online else "AI  OFFLINE")

    # ══════════════════════════════════════════════════════════════
    # TAB 1 — EDITOR
    # ══════════════════════════════════════════════════════════════

    def _build_editor_tab(self):
        p = self._tab_frames["editor"]

        # ── Left panel ──
        left = tk.Frame(p, bg=SURFACE, width=LEFT_PANEL_W)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Frame(left, bg=EDGE, width=1).pack(side="right", fill="y")

        def lsec(parent, title):
            f = tk.Frame(parent, bg=SURFACE)
            f.pack(fill="x", padx=SECTION_PAD, pady=(8, 0))
            SectionLabel(f, title, bg=SURFACE).pack(fill="x", pady=(0, 6))
            return f

        # ── File info panel ──
        s1 = lsec(left, "Source File")
        info_box = tk.Frame(s1, bg=CARBON_2,
                            highlightthickness=1, highlightbackground=EDGE_BRIGHT)
        info_box.pack(fill="x", pady=(0, 6))

        self._filepath_var = tk.StringVar(value="No file loaded")
        tk.Label(info_box, textvariable=self._filepath_var,
                 font=("Consolas", 10), fg=YELLOW, bg=CARBON_2,
                 anchor="w", padx=8, pady=4,
                 wraplength=200, justify="left").pack(fill="x")

        self._fileinfo_var = tk.StringVar(value="")
        tk.Label(info_box, textvariable=self._fileinfo_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=CARBON_2,
                 anchor="w", padx=8).pack(fill="x", pady=(0, 4))

        btn_row = tk.Frame(s1, bg=SURFACE)
        btn_row.pack(fill="x", pady=(0, 4))
        PrimaryButton(btn_row, "OPEN FILE",
                      command=self._open_file).pack(side="left", fill="x", expand=True, padx=(0, 4))
        SecondaryButton(btn_row, "● REC",
                        command=self._start_recording).pack(side="left", fill="x", expand=True)

        # Recording state — shown only while recording
        self._rec_state = tk.Frame(s1, bg=SURFACE)
        self._rec_timer_var = tk.StringVar(value="")
        tk.Label(self._rec_state, textvariable=self._rec_timer_var,
                 font=FONT_MONO_MED, fg=RED_FLAG, bg=SURFACE).pack(fill="x", pady=(0, 4))
        PrimaryButton(self._rec_state, "■  STOP RECORDING",
                      command=self._stop_recording).pack(fill="x")

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=6)

        # Sliders
        s2 = lsec(left, "Detection")
        self._sliders = {}
        for label, key, lo, hi, res, fmt in [
            ("Max Pause",         "max_pause_duration",   0.3, 3.0, 0.1, lambda v: f"{v:.1f}s"),
            ("Silence Threshold", "silence_threshold_db", -60, -20, 1,   lambda v: f"{int(v)} dB"),
            ("Stutter Window",    "stutter_window",       0.2, 2.0, 0.1, lambda v: f"{v:.1f}s"),
        ]:
            sl = LamboSlider(s2, label, key, lo, hi, res,
                             self.settings.get(key), fmt,
                             lambda k, v: self.settings.set(k, v), bg=SURFACE)
            sl.pack(fill="x", pady=(0, 8))
            self._sliders[key] = sl

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=4)

        # Toggles
        s3 = lsec(left, "Flags")
        self._toggles = {}
        for label, key in [("Detect Stutters",   "detect_stutters"),
                            ("Flag Unclear",      "detect_unclear"),
                            ("Detect Breaths",    "detect_breaths"),
                            ("Detect Mouth Noise","detect_mouth_noises"),
                            ("Trim Pauses",       "detect_stutters")]:
            tog = LamboToggle(s3, label, key,
                              value=bool(self.settings.get(key)),
                              on_change=lambda k, v: self.settings.set(k, v),
                              bg=SURFACE)
            tog.pack(fill="x", pady=2)

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=6)

        # Buttons
        s4 = tk.Frame(left, bg=SURFACE)
        s4.pack(fill="x", padx=SECTION_PAD)
        self._analyze_btn = PrimaryButton(s4, "ANALYZE RECORDING",
                                          command=self._run_analysis)
        self._analyze_btn.pack(fill="x", pady=(0, 6))

        # Progress bar — directly under Analyze button
        prog_frame = tk.Frame(s4, bg=SURFACE)
        prog_frame.pack(fill="x", pady=(0, 6))

        prog_header = tk.Frame(prog_frame, bg=SURFACE)
        prog_header.pack(fill="x", pady=(0, 3))
        self._progress_label = tk.Label(prog_header, text="", font=FONT_MONO,
                                         fg=TEXT_MUTED, bg=SURFACE, anchor="w")
        self._progress_label.pack(side="left")
        self._progress_pct = tk.Label(prog_header, text="", font=FONT_MONO,
                                       fg=YELLOW, bg=SURFACE, anchor="e")
        self._progress_pct.pack(side="right")

        track = tk.Frame(prog_frame, bg=EDGE_BRIGHT, height=6)
        track.pack(fill="x")
        track.pack_propagate(False)
        self._progress_fill = tk.Frame(track, bg=YELLOW, height=6)
        self._progress_fill.place(x=0, y=0, relheight=1, relwidth=0)

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=6)

        # Keep LamboProgress for status bar compatibility
        s5 = tk.Frame(left, bg=SURFACE)
        self._progress = LamboProgress(s5, bg=SURFACE)

        # ── Right panel ──
        right = tk.Frame(p, bg=CARBON_1)
        right.pack(side="left", fill="both", expand=True)

        # Stats row
        self._stat_defs = [
            ("pause_count",       "PAUSES TRIMMED", True),
            ("stutter_count",     "STUTTERS",       False),
            ("unclear_count",     "UNCLEAR",        False),
            ("breath_count",      "BREATHS",        False),
            ("mouth_noise_count", "MOUTH NOISE",    False),
            ("time_saved",        "TIME SAVED",     False),
        ]
        self._stat_values = {key: "—" for key, _, _ in self._stat_defs}

        self._stats_canvas = tk.Canvas(right, bg=CARBON_1, height=90,
                                        highlightthickness=0, bd=0)
        self._stats_canvas.pack(fill="x")
        self._stats_canvas.bind("<Configure>", lambda e: self._draw_stat_cards())
        self._stats_canvas.after(200, self._draw_stat_cards)
        tk.Frame(right, bg=YELLOW, height=1).pack(fill="x")

        # ── Timeline bar ──
        tl = tk.Frame(right, bg=CARBON_1, height=18)
        tl.pack(fill="x")
        tl.pack_propagate(False)

        self._tl_start_var = tk.StringVar(value="0:00")
        tk.Label(tl, textvariable=self._tl_start_var,
                 font=("Consolas", 8), fg=TEXT_GHOST, bg=CARBON_1,
                 padx=6).pack(side="left")

        self._tl_canvas = tk.Canvas(tl, bg=CARBON_1, height=18,
                                     highlightthickness=0, bd=0)
        self._tl_canvas.pack(side="left", fill="both", expand=True)
        self._tl_canvas.bind("<Configure>", lambda e: self._draw_timeline())
        self._tl_canvas.after(300, self._draw_timeline)

        self._tl_end_var = tk.StringVar(value="")
        tk.Label(tl, textvariable=self._tl_end_var,
                 font=("Consolas", 8), fg=TEXT_GHOST, bg=CARBON_1,
                 padx=6).pack(side="right")

        # Waveform
        wf_wrap = tk.Frame(right, bg=CARBON_2, height=WAVEFORM_H)
        wf_wrap.pack(fill="x")
        wf_wrap.pack_propagate(False)
        self._waveform = WaveformCanvas(wf_wrap, height=WAVEFORM_H, bg=CARBON_2)
        self._waveform.pack(fill="both", expand=True)
        self._waveform.after(200, self._waveform._redraw)
        tk.Frame(right, bg=EDGE, height=1).pack(fill="x")

        # ── Pitch strip ──
        self._pitch_canvas = tk.Canvas(right, bg=CARBON_2, height=72,
                                       highlightthickness=0, bd=0)
        self._pitch_canvas.pack(fill="x")
        self._pitch_canvas.bind("<Configure>", lambda e: self._draw_pitch())
        self._pitch_canvas.after(300, self._draw_pitch)
        tk.Frame(right, bg=EDGE, height=1).pack(fill="x")

        # ── Playback bar ──
        pb = tk.Frame(right, bg=CARBON_2, height=34)
        pb.pack(fill="x")
        pb.pack_propagate(False)

        self._play_orig_btn = GhostButton(pb, "▶  ORIGINAL",
                                          self._play_original, bg=CARBON_2)
        self._play_orig_btn.pack(side="left", padx=(8, 2), pady=4)

        tk.Frame(pb, bg=SEP_COLOR, width=1).pack(side="left", fill="y", pady=6)

        self._play_clean_btn = GhostButton(pb, "▶  EDITED",
                                           self._play_cleaned, bg=CARBON_2)
        self._play_clean_btn.pack(side="left", padx=(2, 2), pady=4)
        self._play_clean_btn.config(state="disabled")

        tk.Frame(pb, bg=SEP_COLOR, width=1).pack(side="left", fill="y", pady=6)

        self._play_stop_btn = GhostButton(pb, "■  STOP",
                                          self._stop_playback, bg=CARBON_2)
        self._play_stop_btn.pack(side="left", padx=(2, 8), pady=4)
        self._play_stop_btn.config(state="disabled")

        self._play_timer_var = tk.StringVar(value="")
        tk.Label(pb, textvariable=self._play_timer_var,
                 font=FONT_MONO, fg=TEXT_MUTED, bg=CARBON_2).pack(side="right", padx=12)

        tk.Frame(right, bg=EDGE, height=1).pack(fill="x")

        # ── Issues header bar ──
        issues_bar = tk.Frame(right, bg=CARBON_1, height=28)
        issues_bar.pack(fill="x")
        issues_bar.pack_propagate(False)

        tk.Label(issues_bar, text="ISSUES", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_1, padx=10).pack(side="left")

        self._issues_badge_var = tk.StringVar(value="0")
        self._issues_badge = tk.Label(issues_bar, textvariable=self._issues_badge_var,
                                       font=FONT_BADGE, fg=BLACK, bg=YELLOW,
                                       padx=8, pady=2)
        self._issues_badge.pack(side="left")

        tk.Frame(issues_bar, bg=SEP_COLOR, width=1).pack(side="right", fill="y", pady=4)
        GhostButton(issues_bar, "EXPORT WAV",    self._export_wav,    bg=CARBON_1).pack(side="right", padx=(0, 4))
        tk.Frame(issues_bar, bg=SEP_COLOR, width=1).pack(side="right", fill="y", pady=4)
        GhostButton(issues_bar, "EXPORT LABELS", self._export_labels, bg=CARBON_1).pack(side="right", padx=(0, 4))

        # Flag list
        fc = tk.Frame(right, bg=CARBON_1)
        fc.pack(fill="both", expand=True)
        self._flag_tree = make_flag_tree(fc, bg=CARBON_1)
        self._flag_tree.pack(fill="both", expand=True)

    def _draw_pitch(self):
        c = self._pitch_canvas
        c.delete("all")
        W = c.winfo_width()
        H = 72
        if W < 20:
            c.after(100, self._draw_pitch)
            return

        c.create_rectangle(0, 0, W, H, fill=CARBON_2, outline="")
        c.create_text(8, 6, text="PITCH", font=FONT_MONO, fill=TEXT_GHOST, anchor="nw")

        if not self.results or 'pitch_frames' not in self.results:
            c.create_text(W // 2, H // 2, text="Analyze a recording to see pitch",
                          font=FONT_MONO, fill=TEXT_GHOST, anchor="center")
            return

        frames   = self.results['pitch_frames']
        stats    = self.results.get('pitch_stats', {})
        duration = self.results['duration']
        rating   = stats.get('rating', '')

        # Rating badge — top right
        rating_color = {"EXPRESSIVE": GREEN_OK,
                        "MODERATE":   YELLOW,
                        "FLAT":       RED_FLAG}.get(rating, TEXT_GHOST)
        std_hz = stats.get('std_hz', 0.0)
        badge  = f"{rating}  ±{std_hz:.0f} Hz" if rating not in ('NO DATA', '') else rating
        c.create_text(W - 10, 6, text=badge, font=FONT_MONO,
                      fill=rating_color, anchor="ne")

        voiced = [(f['time'], f['freq'], s)
                  for f, s in zip(frames, stats.get('frame_scores', []))
                  if f.get('voiced') and f['freq'] > 0]
        if len(voiced) < 2:
            c.create_text(W // 2, H // 2, text="No voiced audio detected",
                          font=FONT_MONO, fill=TEXT_GHOST, anchor="center")
            return

        # Y mapping: pitch 70–500 Hz → canvas top–bottom (with margins)
        F_MIN, F_MAX = 70, 500
        margin_top, margin_bot = 18, 8

        def hz_to_y(hz):
            hz = max(F_MIN, min(F_MAX, hz))
            return int(margin_top + (1.0 - (hz - F_MIN) / (F_MAX - F_MIN))
                       * (H - margin_top - margin_bot))

        # Playhead (drawn first so contour renders on top)
        ph_x = int(W * self._playhead_frac) if hasattr(self, '_playhead_frac') else 0
        c.create_line(ph_x, 0, ph_x, H, fill=YELLOW, width=2, tags="pitch_playhead")

        # Draw faint horizontal grid lines at 100, 200, 300 Hz
        for grid_hz in (100, 200, 300):
            gy = hz_to_y(grid_hz)
            c.create_line(0, gy, W, gy, fill=EDGE_BRIGHT, width=1, dash=(2, 4))
            c.create_text(W - 4, gy - 1, text=f"{grid_hz}", font=("Consolas", 7),
                          fill="#333333", anchor="e")

        # Color helper: score 0→1 maps red → yellow → green
        def score_color(score):
            if score >= 0.7:   return "#4caf50"   # green  — expressive
            elif score >= 0.35: return YELLOW
            else:               return RED_FLAG    # flat

        # Draw connected line segments, colored by per-frame score
        prev_x = prev_y = None
        for time, freq, score in voiced:
            x = int(time / duration * W)
            y = hz_to_y(freq)
            if prev_x is not None:
                c.create_line(prev_x, prev_y, x, y,
                              fill=score_color(score), width=2)
            prev_x, prev_y = x, y

    def _draw_stat_cards(self):
        """Draw stat cards directly on Canvas — fonts always work on Canvas."""
        c = self._stats_canvas
        c.delete("all")
        W = c.winfo_width()
        H = 90
        if W < 20:
            c.after(100, self._draw_stat_cards)
            return

        n_cards = len(self._stat_defs)
        card_w = (W - (n_cards - 1)) // n_cards
        gap = 1

        for i, (key, label, accent) in enumerate(self._stat_defs):
            x = i * (card_w + gap)
            # Card background
            c.create_rectangle(x, 0, x + card_w, H,
                               fill=CARBON_3, outline="")
            # Yellow accent line on first card
            if accent:
                c.create_rectangle(x, H - 2, x + card_w, H,
                                   fill=YELLOW, outline="")

            # Big number — green when zero on stutter/unclear, yellow on first card
            val = self._stat_values.get(key, "—")
            if accent:
                fg = YELLOW
            elif key in ("stutter_count", "unclear_count",
                         "breath_count", "mouth_noise_count") and str(val) == "0":
                fg = GREEN_OK
            else:
                fg = TEXT
            c.create_text(x + card_w // 2, 32,
                          text=str(val),
                          font=("Consolas", 26, "bold"),
                          fill=fg, anchor="center")

            # Label below
            c.create_text(x + card_w // 2, 68,
                          text=label,
                          font=("Consolas", 7),
                          fill="#444444", anchor="center")

    # ── Editor logic ──────────────────────────────────────────────

    def _draw_timeline(self):
        c = self._tl_canvas
        c.delete("all")
        W = c.winfo_width()
        H = 18
        if W < 4:
            return
        # Track background
        track_y = H // 2
        c.create_rectangle(0, track_y - 1, W, track_y + 1,
                            fill=CARBON_3, outline="")
        # Yellow fill up to playhead (33% default)
        playhead = getattr(self, "_playhead_frac", 0.33)
        fill_w = int(W * playhead)
        if fill_w > 0:
            c.create_rectangle(0, track_y - 1, fill_w, track_y + 1,
                                fill=YELLOW, outline="")
        # Diamond playhead
        px = fill_w
        d = 4
        c.create_polygon(px, track_y - d, px + d, track_y,
                         px, track_y + d, px - d, track_y,
                         fill=YELLOW, outline="")

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open Audio File",
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.ogg *.flac"), ("All", "*.*")])
        if not path:
            return
        self._wav_path = path
        fname = os.path.basename(path)
        self._filepath_var.set(fname)
        self._set_status(f"Loaded: {fname}")
        self.results = None
        self._cleaned_samples = None
        self._stop_playback()
        if _PLAYBACK_OK:
            self._play_clean_btn.config(state="disabled")
        self._clear_results()
        try:
            kb   = os.path.getsize(path) / 1024
            size = f"{kb/1024:.1f}MB" if kb > 1024 else f"{int(kb)}KB"
            ext  = os.path.splitext(path)[1].upper().lstrip(".")
            self._fileinfo_var.set(f"{ext}  {size}")
            self._format_var.set(f"{ext}  {size}")
            # Check ffmpeg availability
            ffmpeg = self._find_ffmpeg()
            self._ffmpeg_var.set("FFMPEG OK" if ffmpeg else "FFMPEG —")
        except Exception:
            pass

    def _clear_results(self):
        for key in self._stat_values:
            self._stat_values[key] = "—"
        self._draw_stat_cards()
        self._draw_pitch()
        self._flag_tree.delete_all()
        self._waveform.load([], [])
        self._issues_badge_var.set("0")
        self._tl_end_var.set("")
        self._playhead_frac = 0.33
        self._draw_timeline()
        self._progress_fill.place(relwidth=0)
        self._progress_label.config(text="")
        self._progress_pct.config(text="")

    def _run_analysis(self):
        if not self._wav_path:
            messagebox.showwarning("No File", "Open an audio file first.")
            return
        wav = self._ensure_wav(self._wav_path)
        if not wav:
            return
        self._analyze_btn.config(state="disabled")
        self._clear_results()
        self._progress.reset()

        def task():
            try:
                analyzer = AudioAnalyzer(self.settings.analysis_settings())
                self.results = analyzer.analyze(wav, progress_callback=self._on_progress)
                self.after(0, self._show_results)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self._analyze_btn.config(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def _find_ffmpeg(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            shutil.which("ffmpeg"),
            os.path.join(project_root, "samples", "ffmpeg.exe"),
            os.path.join(project_root, "ffmpeg", "ffmpeg.exe"),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def _ensure_wav(self, path):
        if path.lower().endswith(".wav"):
            return path

        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            messagebox.showerror(
                "FFmpeg Not Found",
                "FFmpeg is required to convert non-WAV audio files.\n"
                "Please install FFmpeg or place ffmpeg.exe in the project samples/ folder."
            )
            return None

        out = tempfile.mktemp(suffix=".wav")
        try:
            result = subprocess.run(
                [ffmpeg, "-y", "-i", path, out, "-loglevel", "quiet"],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and os.path.exists(out):
                return out
            self._log(f"FFmpeg conversion failed: {result.stderr.strip() or result.stdout.strip()}")
            messagebox.showerror(
                "FFmpeg Conversion Failed",
                "Failed to convert the selected audio file to WAV."
            )
            return None
        except Exception as e:
            self._log(f"FFmpeg conversion error: {e}")
            messagebox.showerror("FFmpeg Error", str(e))
            return None

    def _poll_progress(self):
        """Drain the progress queue on the main thread every 50 ms."""
        try:
            while True:
                fraction, msg = self._progress_queue.get_nowait()
                self._update_progress(fraction, msg)
        except queue.Empty:
            pass
        self.after(50, self._poll_progress)

    def _on_progress(self, fraction, msg):
        self._progress_queue.put((fraction, msg))

    def _update_progress(self, fraction, msg):
        self._progress_fill.place(relwidth=max(0.0, min(1.0, fraction)))
        self._progress_label.config(text=msg.upper())
        pct = int(fraction * 100)
        self._progress_pct.config(text=f"{pct}%" if fraction > 0 else "")
        self._progress.set(fraction, msg)
        self._set_status(msg)

    def _check_for_updates(self, forced=False):
        if not getattr(sys, "frozen", False):
            if forced:
                messagebox.showinfo("Update Check", "Auto-update is only available from the built executable.")
            return

        self._set_status("Checking for updates…")

        def task():
            try:
                info = self.updater.check_for_update()
                if info["available"]:
                    self.after(0, lambda: self._prompt_update(info))
                else:
                    if forced:
                        self.after(0, lambda: self._show_update_dialog(
                            "UP TO DATE",
                            f"You're running the latest version ({APP_VERSION}).",
                            show_update_btn=False
                        ))
                    self.after(0, lambda: self._set_status("Voxarah is up to date"))
            except Exception as e:
                if forced:
                    self.after(0, lambda: messagebox.showerror("Update Error", str(e)))
                self.after(0, lambda: self._set_status("Update check failed"))

        threading.Thread(target=task, daemon=True).start()

    def _prompt_update(self, info):
        version = info.get("version", "?")
        notes   = info.get("notes", "").strip()
        url     = info.get("url")
        body    = f"Version {version} is available.\n\n{notes}" if notes else f"Version {version} is available."
        self._show_update_dialog(
            f"UPDATE  AVAILABLE  —  v{version}",
            body,
            show_update_btn=True,
            on_update=lambda: (
                self._set_status(f"Downloading update {version}…"),
                threading.Thread(target=self._download_and_install, args=(url,), daemon=True).start()
            )
        )

    def _show_update_dialog(self, title: str, body: str, show_update_btn=True, on_update=None):
        dlg = tk.Toplevel(self)
        dlg.title("Voxarah Update")
        dlg.configure(bg=BLACK)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus_set()

        # Yellow top stripe
        tk.Frame(dlg, bg=YELLOW, height=2).pack(fill="x")

        # Header bar
        header = tk.Frame(dlg, bg=BLACK, height=36)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Frame(header, bg=YELLOW, width=3).pack(side="left", fill="y")
        tk.Label(header, text=title, font=FONT_DISPLAY_SM,
                 fg=YELLOW, bg=BLACK, padx=14).pack(side="left", fill="y")

        # Divider
        tk.Frame(dlg, bg=EDGE, height=1).pack(fill="x")

        # Body text
        body_frame = tk.Frame(dlg, bg=CARBON_2, padx=20, pady=16)
        body_frame.pack(fill="x")
        tk.Label(body_frame, text=body, font=FONT_BODY, fg=TEXT, bg=CARBON_2,
                 wraplength=340, justify="left").pack(anchor="w")

        # Button row
        btn_row = tk.Frame(dlg, bg=BLACK, pady=12, padx=14)
        btn_row.pack(fill="x")

        if show_update_btn:
            def do_update():
                dlg.destroy()
                if on_update:
                    on_update()

            PrimaryButton(btn_row, "UPDATE NOW", command=do_update).pack(side="left", padx=(0, 8))
            GhostButton(btn_row, "LATER",
                        command=lambda: (dlg.destroy(), self._set_status("Update postponed"))
                        ).pack(side="left")
        else:
            PrimaryButton(btn_row, "OK", command=dlg.destroy).pack(side="left")

        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        x = self.winfo_x() + (self.winfo_width()  - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dlg.geometry(f"+{x}+{y}")

    def _download_and_install(self, url):
        try:
            downloaded = self.updater.download_update(url)
            self.after(0, lambda: self._show_update_dialog(
                "UPDATE READY",
                "The update has been downloaded.\nVoxarah will restart to finish installing.",
                show_update_btn=False
            ))
            self.updater.install_update(downloaded)
            self.after(0, self.quit)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Update Error", str(e)))
            self.after(0, lambda: self._set_status("Update failed"))

    def _show_results(self):
        if not self.results:
            return
        stats = self.results["stats"]
        self._stat_values["pause_count"]       = str(stats["pause_count"])
        self._stat_values["stutter_count"]     = str(stats["stutter_count"])
        self._stat_values["unclear_count"]     = str(stats["unclear_count"])
        self._stat_values["breath_count"]      = str(stats["breath_count"])
        self._stat_values["mouth_noise_count"] = str(stats["mouth_noise_count"])
        self._stat_values["time_saved"]        = f"{stats['time_saved']:.1f}s"
        self._draw_stat_cards()
        self._draw_pitch()
        self._flag_tree.delete_all()

        # Cache cleaned samples and enable the CLEANED playback button
        self._cleaned_samples = None   # invalidate stale cache
        if _PLAYBACK_OK:
            self._play_clean_btn.config(state="normal")
            self._play_orig_btn.config(state="normal")

        sr       = self.results["sample_rate"]
        n_samples = len(self.results["samples"])
        duration  = n_samples / sr if sr else 0

        # Update timeline duration label and redraw
        self._tl_end_var.set(fmt_time(duration))
        self._fileinfo_var.set(
            self._fileinfo_var.get().split("  ")[0] + f"  {fmt_time(duration)}"
            if self._fileinfo_var.get() else fmt_time(duration))
        self._draw_timeline()

        flag_samples = []
        for edit in self.results["all_edits"]:
            # Compute severity
            ftype = edit["type"]
            if ftype == "pause":
                dur = edit["end"] - edit["start"]
                sev = 3 if dur > 2.0 else 2 if dur > 1.5 else 1
            else:
                sev = 1
            self._flag_tree.insert(edit["type"], fmt_time(edit["start"]),
                                   edit["desc"], severity=sev)
            flag_samples.append({
                "type":         edit["type"],
                "start_sample": int(edit["start"] * sr),
                "end_sample":   int(edit["end"]   * sr),
            })

        # Update issues badge
        n = len(self.results["all_edits"])
        self._issues_badge_var.set(str(n))

        self._waveform.load(self.results["samples"], flag_samples)
        self._update_progress(1.0, "Analysis complete")
        n_issues = len(self.results["all_edits"])
        self._set_status(f"Done — {n_issues} issues found")

        if hasattr(self, "_coaching_manager"):
            self._coaching_manager.set_results(self.results, self._wav_path)

    # ── Playback ──────────────────────────────────────────────────

    def _play_original(self):
        if not self.results or not _PLAYBACK_OK:
            return
        samples = _np.asarray(self.results['samples'], dtype=_np.float32)
        sr      = self.results['sample_rate']
        self._start_playback(samples, sr)

    def _play_cleaned(self):
        if not self.results or not _PLAYBACK_OK:
            return
        try:
            if self._cleaned_samples is None:
                self._cleaned_samples, _ = build_cleaned_samples(
                    self.results, self.settings.analysis_settings())
            sr  = self.results['sample_rate']
            n_b = len(self.results.get('breaths', []))
            n_m = len(self.results.get('mouth_noises', []))
            n_p = len(self.results.get('long_pauses', []))
            parts = []
            if n_b: parts.append(f"{n_b} breath{'s' if n_b > 1 else ''}")
            if n_m: parts.append(f"{n_m} mouth noise{'s' if n_m > 1 else ''}")
            if n_p: parts.append(f"{n_p} pause{'s' if n_p > 1 else ''} trimmed")
            summary = "Edited: " + (", ".join(parts) if parts else "no changes — recording is clean")
            self._set_status(summary)
            audio = _np.ascontiguousarray(self._cleaned_samples, dtype=_np.float32)
            self._start_playback(audio, sr)
        except Exception as e:
            messagebox.showerror("Playback Error", str(e))

    def _start_playback(self, samples, sr):
        _sd.stop()
        _sd.play(samples, samplerate=sr)
        self._play_start_time = time.monotonic()
        self._play_duration   = len(samples) / sr
        self._play_active     = True
        self._play_stop_btn.config(state="normal")
        self._play_timer_var.set("0:00.0")
        self._playback_tick()

    def _move_playheads(self, fraction: float):
        self._waveform.set_playhead(fraction)
        W = self._pitch_canvas.winfo_width()
        H = 72
        px = int(W * fraction)
        existing = self._pitch_canvas.find_withtag("pitch_playhead")
        if existing:
            self._pitch_canvas.coords(existing[0], px, 0, px, H)
        else:
            self._pitch_canvas.create_line(px, 0, px, H,
                                           fill=YELLOW, width=2, tags="pitch_playhead")

    def _stop_playback(self):
        if _PLAYBACK_OK:
            _sd.stop()
        self._play_active = False
        if hasattr(self, "_play_stop_btn"):
            self._play_stop_btn.config(state="disabled")
        if hasattr(self, "_play_timer_var"):
            self._play_timer_var.set("")
        if hasattr(self, "_waveform"):
            self._move_playheads(0.0)

    def _playback_tick(self):
        if not self._play_active:
            return
        elapsed = time.monotonic() - self._play_start_time
        if elapsed >= self._play_duration or not _sd.get_stream().active:
            self._move_playheads(1.0)
            self._stop_playback()
            return
        frac = elapsed / self._play_duration
        self._move_playheads(frac)
        m = int(elapsed // 60)
        s = elapsed % 60
        dm = int(self._play_duration // 60)
        ds = self._play_duration % 60
        self._play_timer_var.set(f"{m}:{s:04.1f}  /  {dm}:{ds:04.1f}")
        self.after(30, self._playback_tick)

    def _export_wav(self):
        if not self.results:
            messagebox.showwarning("No Results", "Run analysis first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".wav",
                                             filetypes=[("WAV", "*.wav")])
        if path:
            try:
                build_cleaned_wav(self.results, self.settings.analysis_settings(), path)
                self._set_status(f"Exported: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def _export_labels(self):
        if not self.results:
            messagebox.showwarning("No Results", "Run analysis first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Audacity Labels", "*.txt")])
        if path:
            try:
                with open(path, "w") as f:
                    f.write(build_label_file(self.results))
                self._set_status(f"Labels: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))


    # ══════════════════════════════════════════════════════════════
    # TAB 2 — COACHING
    # ══════════════════════════════════════════════════════════════

    def _build_coaching_tab(self):
        self._coaching_manager = CoachingTabManager(
            self._tab_frames["coaching"], self.settings,
            ai_coach=self.ai_coach, voice_engine=self.voice)

    # ══════════════════════════════════════════════════════════════
    # TAB 3 — COMPARE
    # ══════════════════════════════════════════════════════════════

    def _build_compare_tab(self):
        self._compare_panel = CompareTakesPanel(
            self._tab_frames["compare"], self.settings,
            ensure_wav_fn=self._ensure_wav)

    # ══════════════════════════════════════════════════════════════
    # TAB 4 — SETTINGS
    # ══════════════════════════════════════════════════════════════

    def _build_settings_tab(self):
        p = self._tab_frames["settings"]

        canvas = tk.Canvas(p, bg=CARBON_1, highlightthickness=0)
        vsb    = styled_scrollbar(p, command=canvas.yview)
        frame  = tk.Frame(canvas, bg=CARBON_1)
        frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def section(title):
            f = tk.Frame(frame, bg=CARBON_1)
            f.pack(fill="x", padx=24, pady=(18,4))
            SectionLabel(f, title, bg=CARBON_1).pack(fill="x")

        def row(label_text, key, wtype, **kw):
            f = tk.Frame(frame, bg=CARBON_2)
            f.pack(fill="x", padx=24, pady=1)
            tk.Label(f, text=label_text, font=FONT_BODY, fg=TEXT_DIM,
                     bg=CARBON_2, width=34, anchor="w",
                     pady=8, padx=12).pack(side="left")

            if wtype in ("float", "int"):
                var = tk.DoubleVar(value=self.settings.get(key)) if wtype == "float" \
                      else tk.IntVar(value=self.settings.get(key))
                e = tk.Entry(f, textvariable=var, font=FONT_MONO_MED,
                             width=10, bg=CARBON_4, fg=YELLOW,
                             insertbackground=YELLOW, relief="flat",
                             highlightbackground=EDGE, highlightthickness=1)
                e.pack(side="right", padx=12, pady=6)
                cast = float if wtype == "float" else int
                e.bind("<FocusOut>", lambda ev, k=key, v=var, c=cast: self.settings.set(k, c(v.get() or 0)))

            elif wtype == "bool":
                LamboToggle(f, "", key,
                            value=self.settings.get(key),
                            on_change=lambda k, v: self.settings.set(k, v),
                            bg=CARBON_2).pack(side="right", padx=12, pady=8)

            elif wtype == "choice":
                var = tk.StringVar(value=self.settings.get(key))
                cb = ttk.Combobox(f, textvariable=var, values=kw.get("choices",[]),
                                   state="readonly", width=22, font=FONT_BODY)
                cb.pack(side="right", padx=12, pady=6)
                cb.bind("<<ComboboxSelected>>",
                        lambda ev, k=key, v=var: self.settings.set(k, v.get()))

            elif wtype == "string":
                var = tk.StringVar(value=self.settings.get(key) or "")
                e = tk.Entry(f, textvariable=var, font=FONT_MONO_MED,
                             width=36, bg=CARBON_4, fg=YELLOW,
                             insertbackground=YELLOW, relief="flat",
                             highlightbackground=EDGE, highlightthickness=1)
                e.pack(side="right", padx=12, pady=6)
                e.bind("<FocusOut>", lambda ev, k=key, v=var: self.settings.set(k, v.get().strip()))

            elif wtype == "color":
                current = self.settings.get(key) or "#e0e0e0"
                var = tk.StringVar(value=current)

                swatch = tk.Frame(f, width=22, height=22, bg=current,
                                  highlightthickness=1, highlightbackground=EDGE_BRIGHT,
                                  cursor="hand2")
                swatch.pack(side="right", padx=(6, 12), pady=8)

                hex_entry = tk.Entry(f, textvariable=var, font=FONT_MONO,
                                     width=10, bg=CARBON_4, fg=YELLOW,
                                     insertbackground=YELLOW, relief="flat",
                                     highlightbackground=EDGE, highlightthickness=1)
                hex_entry.pack(side="right", padx=(0, 4), pady=8)

                def _pick_color(k=key, v=var, sw=swatch):
                    from tkinter import colorchooser
                    result = colorchooser.askcolor(color=v.get(), title="Pick Text Color")
                    if result and result[1]:
                        v.set(result[1])
                        sw.config(bg=result[1])
                        self.settings.set(k, result[1])

                def _hex_changed(ev, k=key, v=var, sw=swatch):
                    val = v.get().strip()
                    if len(val) == 7 and val.startswith("#"):
                        try:
                            sw.config(bg=val)
                            self.settings.set(k, val)
                        except Exception:
                            pass

                swatch.bind("<Button-1>", lambda e, fn=_pick_color: fn())
                hex_entry.bind("<FocusOut>", _hex_changed)
                hex_entry.bind("<Return>",   _hex_changed)

        from coaching.profiles import get_all_profiles

        section("Analysis")
        row("Silence Threshold (dB)",       "silence_threshold_db",  "int")
        row("Min Silence Duration (s)",      "min_silence_duration",  "float")
        row("Max Pause Duration (s)",        "max_pause_duration",    "float")
        row("Stutter Window (s)",            "stutter_window",        "float")
        row("Detect Stutters",               "detect_stutters",       "bool")
        row("Detect Unclear Audio",          "detect_unclear",        "bool")
        row("Detect Breaths",                "detect_breaths",        "bool")
        row("Detect Mouth Noises",           "detect_mouth_noises",   "bool")

        section("Coaching")
        row("Default Voice Profile",         "coaching_profile",      "choice",
            choices=get_all_profiles())
        row("Show coaching tips",            "show_coaching_tips",    "bool")

        section("Interface")
        row("Log verbosity",                 "log_verbosity",         "choice",
            choices=["quiet", "normal", "verbose"])
        row("Auto-analyze on load",          "auto_analyze_on_load",  "bool")
        row("Primary Text Color",            "ui_text_color",         "color")

        section("Updates")
        row("Auto-check for updates",       "auto_update_check",     "bool")
        row("Update manifest URL",          "update_manifest_url",   "string")

        btn_row = tk.Frame(frame, bg=CARBON_1)
        btn_row.pack(fill="x", padx=24, pady=20)
        PrimaryButton(btn_row, "SAVE SETTINGS",
                      command=self._save_settings).pack(side="left", padx=(0,8))
        SecondaryButton(btn_row, "RESET DEFAULTS",
                        command=self._reset_settings).pack(side="left")
        SecondaryButton(btn_row, "WHAT'S NEW",
                        command=self._show_patch_notes).pack(side="right")

    def _save_settings(self):
        self.settings.save()
        self._apply_text_color()
        self._set_status("Settings saved")
        messagebox.showinfo("Saved", "Settings saved.")

    def _apply_text_color(self):
        """Apply ui_text_color to all TEXT-colored labels app-wide."""
        color = self.settings.get("ui_text_color") or TEXT
        self._propagate_text_color(self, color)

    def _propagate_text_color(self, widget, color):
        try:
            # Only recolor labels/buttons that were originally TEXT-colored
            if widget.cget("fg") in ("#e0e0e0", TEXT):
                widget.config(fg=color)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._propagate_text_color(child, color)

    def _reset_settings(self):
        if messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            self.settings.reset_to_defaults()
            self._set_status("Settings reset")

    # ── Patch Notes ───────────────────────────────────────────────

    def _check_patch_notes(self):
        """Auto-show patch notes once when a new version is first launched."""
        last_seen = self.settings.get("last_seen_version", "")
        if last_seen != APP_VERSION:
            self.settings.set("last_seen_version", APP_VERSION)
            self.settings.save()
            self._show_patch_notes(highlight_version=APP_VERSION)

    def _show_patch_notes(self, highlight_version=None):
        """Open the patch notes modal."""
        win = tk.Toplevel(self)
        win.title("What's New — Voxarah")
        win.configure(bg=BLACK)
        win.resizable(False, False)
        win.grab_set()

        # Size and center
        W, H = 620, 560
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - W) // 2
        y = self.winfo_y() + (self.winfo_height() - H) // 2
        win.geometry(f"{W}x{H}+{x}+{y}")

        # Title bar stripe
        tk.Frame(win, bg=YELLOW, height=2).pack(fill="x")

        hdr = tk.Frame(win, bg=BLACK, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=YELLOW, width=3).pack(side="left", fill="y")
        tk.Label(hdr, text="WHAT'S NEW", font=("Segoe UI", 14, "bold"),
                 fg=TEXT, bg=BLACK, padx=16).pack(side="left")
        tk.Label(hdr, text=f"VOXARAH  v{APP_VERSION}",
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BLACK,
                 padx=12).pack(side="right")

        tk.Frame(win, bg=EDGE, height=1).pack(fill="x")

        # Scrollable content
        from ui.components import DarkScrollbar
        body_wrap = tk.Frame(win, bg=CARBON_1)
        body_wrap.pack(fill="both", expand=True)

        canvas = tk.Canvas(body_wrap, bg=CARBON_1, highlightthickness=0)
        sb = DarkScrollbar(body_wrap, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=CARBON_1)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))

        # Mouse wheel scroll
        def _scroll(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Render changelog entries
        for entry in CHANGELOG:
            ver   = entry["version"]
            is_new = (ver == highlight_version or
                      (highlight_version is None and ver == CHANGELOG[0]["version"]))

            # Version header
            ver_hdr = tk.Frame(inner, bg=CARBON_2)
            ver_hdr.pack(fill="x", padx=16, pady=(14, 0))
            tk.Frame(ver_hdr, bg=YELLOW if is_new else EDGE_BRIGHT,
                     width=3).pack(side="left", fill="y")

            hdr_inner = tk.Frame(ver_hdr, bg=CARBON_2)
            hdr_inner.pack(side="left", fill="both", expand=True,
                           padx=12, pady=8)
            ver_row = tk.Frame(hdr_inner, bg=CARBON_2)
            ver_row.pack(fill="x")
            tk.Label(ver_row, text=f"v{ver}", font=("Consolas", 13, "bold"),
                     fg=YELLOW if is_new else TEXT_DIM,
                     bg=CARBON_2).pack(side="left")
            if is_new:
                tk.Label(ver_row, text=" NEW ", font=FONT_BADGE,
                         fg=BLACK, bg=YELLOW, padx=4).pack(side="left", padx=(8, 0))
            tk.Label(ver_row, text=entry.get("date", ""),
                     font=FONT_MONO, fg=TEXT_GHOST,
                     bg=CARBON_2).pack(side="right")

            # Feature list
            feat_frame = tk.Frame(inner, bg=CARBON_1)
            feat_frame.pack(fill="x", padx=16, pady=(0, 4))

            for title, desc in entry["features"]:
                row_f = tk.Frame(feat_frame, bg=CARBON_1)
                row_f.pack(fill="x", pady=4)

                # Yellow bullet
                tk.Label(row_f, text="▸", font=("Consolas", 10),
                         fg=YELLOW if is_new else TEXT_GHOST,
                         bg=CARBON_1).pack(side="left", anchor="n",
                                           padx=(8, 0), pady=3)

                text_col = tk.Frame(row_f, bg=CARBON_1)
                text_col.pack(side="left", fill="x", expand=True,
                              padx=(6, 16))
                tk.Label(text_col, text=title,
                         font=("Segoe UI", 10, "bold"),
                         fg=TEXT if is_new else TEXT_DIM,
                         bg=CARBON_1, anchor="w").pack(fill="x")
                tk.Label(text_col, text=desc,
                         font=FONT_SMALL, fg=TEXT_MUTED,
                         bg=CARBON_1, anchor="w", justify="left",
                         wraplength=520).pack(fill="x")

            tk.Frame(inner, bg=EDGE, height=1).pack(fill="x", padx=16,
                                                      pady=(6, 0))

        # Close button
        tk.Frame(win, bg=EDGE, height=1).pack(fill="x", side="bottom")
        btn_bar = tk.Frame(win, bg=BLACK, height=44)
        btn_bar.pack(fill="x", side="bottom")
        btn_bar.pack_propagate(False)
        PrimaryButton(btn_bar, "CLOSE",
                      command=win.destroy).pack(side="right", padx=12, pady=6)

    def _log(self, msg):
        print(msg)

    # ══════════════════════════════════════════════════════════════
    # RECORDER
    # ══════════════════════════════════════════════════════════════

    def _start_recording(self):
        if not self.recorder.available:
            messagebox.showerror("No Audio Device",
                "sounddevice is not available.\nInstall it with: pip install sounddevice")
            return
        if not self.recorder.start():
            messagebox.showerror("Recording Failed",
                "Could not start recording.\nCheck your microphone and audio device.")
            return
        self._filepath_var.set("\u25cf RECORDING...")
        self._fileinfo_var.set("")
        self._rec_state.pack(fill="x", pady=(4, 0))
        self._rec_tick()

    def _rec_tick(self):
        if not self.recorder.is_recording:
            return
        elapsed = self.recorder.elapsed_seconds
        m = int(elapsed // 60)
        s = elapsed % 60
        self._rec_timer_var.set(f"\u25cf REC  {m}:{s:04.1f}")
        self.after(100, self._rec_tick)

    def _stop_recording(self):
        path = self.recorder.stop()
        self._rec_state.pack_forget()
        self._rec_timer_var.set("")
        if not path:
            self._filepath_var.set("No file loaded")
            self._set_status("Recording failed or was empty")
            return
        if self._rec_temp_path and os.path.exists(self._rec_temp_path):
            try:
                os.remove(self._rec_temp_path)
            except Exception:
                pass
        self._rec_temp_path = path
        self._wav_path      = path
        self._filepath_var.set("recorded_take.wav")
        self._set_status("Recording captured — ready to analyze")
        self.results = None
        self._clear_results()
        try:
            kb   = os.path.getsize(path) / 1024
            size = f"{kb/1024:.1f}MB" if kb > 1024 else f"{int(kb)}KB"
            self._fileinfo_var.set(f"WAV  {size}")
            self._format_var.set(f"WAV  {size}")
            ffmpeg = self._find_ffmpeg()
            self._ffmpeg_var.set("FFMPEG OK" if ffmpeg else "FFMPEG \u2014")
        except Exception:
            pass
