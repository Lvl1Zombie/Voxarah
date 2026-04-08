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

from core.settings        import SettingsManager
from core.analyzer        import AudioAnalyzer, build_cleaned_wav, build_label_file
from core.audacity_bridge import AudacityBridge
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

APP_VERSION = "2.0"


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
        self.bridge    = AudacityBridge(log_callback=self._log)
        self.ai_coach  = AICoach()
        self.voice     = VoiceEngine()
        self.updater   = Updater(current_version=APP_VERSION)
        self.results   = None
        self._wav_path = None

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

        if self.settings.get("audacity_auto_connect"):
            self.after(900, self._try_connect_silent)

        self.after(1200, self._check_ollama_status)
        self.after(1800, self._check_for_updates)

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

        # Right side
        right = tk.Frame(bar, bg=BLACK)
        right.pack(side="right", padx=14)

        self._conn_canvas = tk.Canvas(right, width=8, height=8,
                                       bg=BLACK, highlightthickness=0)
        self._conn_canvas.pack(side="left", padx=(0, 6))
        self._conn_dot = self._conn_canvas.create_oval(1, 1, 7, 7,
                                                        fill=EDGE_BRIGHT, outline="")

        self._conn_var = tk.StringVar(value="AUDACITY  OFFLINE")
        tk.Label(right, textvariable=self._conn_var,
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

    def _update_conn_indicator(self, connected):
        color = YELLOW if connected else EDGE_BRIGHT
        self._conn_canvas.itemconfig(self._conn_dot, fill=color)
        self._conn_var.set("AUDACITY  LIVE" if connected else "AUDACITY  OFFLINE")

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
            ("audacity", "  AUDACITY  "),
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
        self._tab_frames["audacity"] = tk.Frame(self._body, bg=CARBON_1)
        self._tab_frames["settings"] = tk.Frame(self._body, bg=CARBON_1)

        self._build_editor_tab()
        self._build_coaching_tab()
        self._build_audacity_tab()
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

        PrimaryButton(s1, "OPEN AUDIO FILE", command=self._open_file).pack(fill="x")

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
        for label, key in [("Detect Stutters", "detect_stutters"),
                            ("Flag Unclear",    "detect_unclear"),
                            ("Trim Pauses",     "detect_stutters")]:
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

        self._apply_btn = SecondaryButton(s4, "APPLY IN AUDACITY",
                                          command=self._apply_in_audacity)
        self._apply_btn.pack(fill="x")
        self._apply_btn.config(state="disabled", fg=TEXT_GHOST)

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=6)

        # Keep LamboProgress for status bar compatibility
        s5 = tk.Frame(left, bg=SURFACE)
        self._progress = LamboProgress(s5, bg=SURFACE)

        # ── Right panel ──
        right = tk.Frame(p, bg=CARBON_1)
        right.pack(side="left", fill="both", expand=True)

        # Stats row
        self._stat_defs = [
            ("pause_count",   "PAUSES TRIMMED", True),
            ("stutter_count", "STUTTERS",       False),
            ("unclear_count", "UNCLEAR",        False),
            ("time_saved",    "TIME SAVED",     False),
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

    def _draw_stat_cards(self):
        """Draw stat cards directly on Canvas — fonts always work on Canvas."""
        c = self._stats_canvas
        c.delete("all")
        W = c.winfo_width()
        H = 90
        if W < 20:
            c.after(100, self._draw_stat_cards)
            return

        card_w = (W - 3) // 4
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
            elif key in ("stutter_count", "unclear_count") and str(val) == "0":
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
        self._apply_btn.config(state="disabled")
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
        self._stat_values["pause_count"]   = str(stats["pause_count"])
        self._stat_values["stutter_count"] = str(stats["stutter_count"])
        self._stat_values["unclear_count"] = str(stats["unclear_count"])
        self._stat_values["time_saved"]    = f"{stats['time_saved']:.1f}s"
        self._draw_stat_cards()
        self._flag_tree.delete_all()

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
        self._apply_btn.config(state="normal", fg=YELLOW)

        if hasattr(self, "_coaching_manager"):
            self._coaching_manager.set_results(self.results)

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

    def _apply_in_audacity(self):
        if not self.results:
            messagebox.showwarning("No Results", "Run analysis first.")
            return
        if not self.bridge.connected:
            if not self.bridge.connect():
                messagebox.showerror("Not Connected",
                    "Could not connect to Audacity.\n\n"
                    "1. Audacity must be open\n"
                    "2. mod-script-pipe must be enabled\n"
                    "   (Edit → Preferences → Modules → mod-script-pipe → Enabled)\n"
                    "3. Restart Audacity after enabling")
                return
        self._apply_btn.config(state="disabled")

        def task():
            self.bridge.apply_edits_batch(
                self.results["all_edits"],
                self.settings.get("max_pause_duration"),
                progress_callback=lambda f: self._on_progress(f, "Applying in Audacity…"))
            self.after(0, lambda: self._apply_btn.config(state="normal"))
            self.after(0, lambda: self._set_status("Edits applied in Audacity"))

        threading.Thread(target=task, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # TAB 2 — COACHING
    # ══════════════════════════════════════════════════════════════

    def _build_coaching_tab(self):
        self._coaching_manager = CoachingTabManager(
            self._tab_frames["coaching"], self.settings,
            ai_coach=self.ai_coach, voice_engine=self.voice)

    # ══════════════════════════════════════════════════════════════
    # TAB 3 — AUDACITY
    # ══════════════════════════════════════════════════════════════

    def _build_audacity_tab(self):
        p = self._tab_frames["audacity"]

        left = tk.Frame(p, bg=SURFACE, width=320)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Frame(left, bg=EDGE, width=1).pack(side="right", fill="y")

        # Connection
        conn = tk.Frame(left, bg=SURFACE)
        conn.pack(fill="x", padx=SECTION_PAD, pady=(14, 0))
        SectionLabel(conn, "Connection", bg=SURFACE).pack(fill="x", pady=(0, 10))

        self._aud_status_var = tk.StringVar(value="OFFLINE")
        tk.Label(conn, textvariable=self._aud_status_var,
                 font=FONT_MONO_MED, fg=EDGE_BRIGHT, bg=SURFACE).pack(anchor="w", pady=(0,8))

        tk.Label(conn,
                 text="Enable in Audacity:\nEdit → Preferences → Modules\n→ mod-script-pipe → Enabled\n→ Restart Audacity",
                 font=FONT_MONO, fg=TEXT_GHOST, bg=SURFACE, justify="left").pack(anchor="w", pady=(0,10))

        PrimaryButton(conn, "CONNECT TO AUDACITY",
                      command=self._try_connect).pack(fill="x", pady=(0,6))
        SecondaryButton(conn, "DISCONNECT",
                        command=self._disconnect).pack(fill="x")

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=10)

        # Controls
        ctrl = tk.Frame(left, bg=SURFACE)
        ctrl.pack(fill="x", padx=SECTION_PAD)
        SectionLabel(ctrl, "Direct Controls", bg=SURFACE).pack(fill="x", pady=(0,10))

        for row_cmds in [
            [("Play",  self.bridge.play),  ("Stop",  self.bridge.stop),  ("Undo", self.bridge.undo)],
            [("Redo",  self.bridge.redo),  ("Fit Window", self.bridge.fit_in_window)],
        ]:
            row = tk.Frame(ctrl, bg=SURFACE)
            row.pack(fill="x", pady=(0,4))
            for txt, cmd in row_cmds:
                GhostButton(row, txt, cmd, bg=SURFACE).pack(side="left", padx=(0,4))

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=10)

        imp = tk.Frame(left, bg=SURFACE)
        imp.pack(fill="x", padx=SECTION_PAD)
        SecondaryButton(imp, "IMPORT LABELS TO AUDACITY",
                        command=self._import_labels).pack(fill="x", pady=(0,6))
        SecondaryButton(imp, "EXPORT FROM AUDACITY",
                        command=self._export_from_audacity).pack(fill="x")

        # Log
        right = tk.Frame(p, bg=CARBON_1)
        right.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(right, bg=CARBON_1, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="ACTIVITY LOG", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_1, padx=14).pack(side="left", fill="y")
        tk.Frame(hdr, bg=YELLOW, height=1).pack(side="bottom", fill="x")

        self._log_area = make_log_text(right, height=30)
        self._log_area.pack(fill="both", expand=True)

    def _try_connect(self):
        self._set_status("Connecting to Audacity…")
        ok = self.bridge.connect()
        self._update_conn_indicator(ok)
        self._aud_status_var.set("LIVE" if ok else "OFFLINE")
        if ok and self.results:
            self._apply_btn.config(state="normal")
        self._set_status("Connected" if ok else "Connection failed — is Audacity open?")

    def _try_connect_silent(self):
        ok = self.bridge.connect()
        self._update_conn_indicator(ok)
        if hasattr(self, "_aud_status_var"):
            self._aud_status_var.set("LIVE" if ok else "OFFLINE")

    def _disconnect(self):
        self.bridge.disconnect()
        self._update_conn_indicator(False)
        self._aud_status_var.set("OFFLINE")

    def _import_labels(self):
        if not self.results:
            messagebox.showwarning("No Results", "Run analysis first.")
            return
        if not self.bridge.connected:
            messagebox.showwarning("Not Connected", "Connect to Audacity first.")
            return
        tmp = tempfile.mktemp(suffix=".txt")
        with open(tmp, "w") as f:
            f.write(build_label_file(self.results))
        self.bridge.import_labels(tmp)
        self._log("Labels imported into Audacity")

    def _export_from_audacity(self):
        if not self.bridge.connected:
            messagebox.showwarning("Not Connected", "Connect to Audacity first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".wav",
                                             filetypes=[("WAV", "*.wav")])
        if path:
            self.bridge.export_wav(path)
            self._log(f"Export triggered: {os.path.basename(path)}")

    def _log(self, msg):
        def _do():
            if hasattr(self, "_log_area"):
                log_append(self._log_area, msg)
        try:
            self.after(0, _do)
        except Exception:
            print(msg)

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

        section("Audacity")
        row("Auto-connect on startup",       "audacity_auto_connect", "bool")
        row("Apply trims in Audacity",       "audacity_apply_trims",  "bool")
        row("Add label track for flags",     "audacity_add_labels",   "bool")
        row("Fit track in window after",     "audacity_fit_after",    "bool")

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
