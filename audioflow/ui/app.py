"""
Voxarah — Main Application
Full Lamborghini-inspired UI. Matte black + yellow. No softness.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import os
import tempfile

from core.settings        import SettingsManager
from core.analyzer        import AudioAnalyzer, build_cleaned_wav, build_label_file
from core.audacity_bridge import AudacityBridge
from core.ai_coach        import AICoach
from core.voice           import VoiceEngine
from ui.design            import *
from ui.components        import (
    SectionLabel, HDivider, PrimaryButton, SecondaryButton, GhostButton,
    LamboSlider, LamboToggle, StatCard, BadgeLabel,
    WaveformCanvas, make_flag_tree, styled_scrollbar,
    make_notebook, make_log_text, log_append, LamboProgress, PanelSection
)
from ui.coaching_panel    import CoachingTabManager


def fmt_time(sec):
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:04.1f}"


class AudioFlowApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Voxarah")
        self.geometry("1060x680")
        self.minsize(900, 600)
        self.configure(bg=BLACK)

        self.settings  = SettingsManager()
        self.bridge    = AudacityBridge(log_callback=self._log)
        self.ai_coach  = AICoach()
        self.voice     = VoiceEngine()
        self.results   = None
        self._wav_path = None

        self._build_titlebar()
        self._build_tabbar()
        self._build_body()
        self._build_status_bar()

        # Force dark title bar on Windows 10/11
        self.after(50, self._set_dark_titlebar)

        if self.settings.get("audacity_auto_connect"):
            self.after(900, self._try_connect_silent)

        self.after(1200, self._check_ollama_status)

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

        logo = tk.Canvas(wm, width=22, height=22, bg=BLACK, highlightthickness=0)
        logo.pack(side="left", padx=(0, 8))
        self._draw_logo(logo)

        tk.Label(wm, text="VOX",  font=("Segoe UI", 13, "bold"), fg=TEXT,   bg=BLACK, padx=0, bd=0).pack(side="left", padx=0)
        tk.Label(wm, text="A",    font=("Segoe UI", 13, "bold"), fg=YELLOW, bg=BLACK, padx=0, bd=0).pack(side="left", padx=0)
        tk.Label(wm, text="RAH",  font=("Segoe UI", 13, "bold"), fg=TEXT,   bg=BLACK, padx=0, bd=0).pack(side="left", padx=0)

        tk.Frame(bar, bg=EDGE, width=1).pack(side="left", fill="y", padx=14, pady=8)
        tk.Label(bar, text="VOICE PRODUCTION SUITE",
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BLACK).pack(side="left")

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
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BLACK).pack(side="left")

    def _draw_logo(self, canvas):
        pts = [(11,1),(21,6),(21,16),(11,21),(1,16),(1,6)]
        flat = [c for pt in pts for c in pt]
        canvas.create_polygon(flat, outline=YELLOW, fill="", width=1)
        canvas.create_line(11, 4, 11, 18, fill=YELLOW, width=1)
        for x in (5, 17):
            canvas.create_line(x, 8,  11, 4,  fill=YELLOW, width=1)
            canvas.create_line(x, 14, 11, 18, fill=YELLOW, width=1)

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
        self._active_tab  = None

        tabs = [
            ("editor",   "  EDITOR  "),
            ("coaching", "  COACHING  "),
            ("audacity", "  AUDACITY  "),
            ("settings", "  SETTINGS  "),
        ]

        for key, label in tabs:
            btn = tk.Label(bar, text=label, font=FONT_TAB,
                           fg=TEXT_GHOST, bg=BLACK, cursor="hand2", pady=0)
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            self._tab_btns[key] = btn

        tk.Frame(bar, bg=EDGE, height=1).pack(side="bottom", fill="x")

    def _switch_tab(self, key):
        if self._active_tab == key:
            return
        self._active_tab = key
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.config(fg=YELLOW, bg=CARBON_2)
            else:
                btn.config(fg=TEXT_GHOST, bg=BLACK)
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

        self._status_var = tk.StringVar(value="READY")
        tk.Label(bar, textvariable=self._status_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BLACK).pack(side="left", padx=12)

        # Ollama status indicator
        ollama_frame = tk.Frame(bar, bg=BLACK)
        ollama_frame.pack(side="right", padx=(0, 12))
        self._ollama_canvas = tk.Canvas(ollama_frame, width=8, height=8,
                                         bg=BLACK, highlightthickness=0)
        self._ollama_canvas.pack(side="left", padx=(0, 4))
        self._ollama_dot = self._ollama_canvas.create_oval(1, 1, 7, 7,
                                                            fill=EDGE_BRIGHT, outline="")
        self._ollama_var = tk.StringVar(value="AI  OFFLINE")
        tk.Label(ollama_frame, textvariable=self._ollama_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BLACK).pack(side="left")

        self._format_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self._format_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BLACK).pack(side="right", padx=12)
        tk.Label(bar, text="VOXARAH  v2.0",
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BLACK).pack(side="right", padx=12)

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
            f.pack(fill="x", padx=SECTION_PAD, pady=(12, 0))
            SectionLabel(f, title, bg=SURFACE).pack(fill="x", pady=(0, 8))
            return f

        # File
        s1 = lsec(left, "Source File")
        self._filepath_var = tk.StringVar(value="No file loaded")
        tk.Label(s1, textvariable=self._filepath_var, font=FONT_MONO_MED,
                 fg=YELLOW, bg=SURFACE, anchor="w",
                 wraplength=208, justify="left").pack(fill="x", pady=(0,6))
        PrimaryButton(s1, "OPEN AUDIO FILE", command=self._open_file).pack(fill="x")

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=10)

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
            sl.pack(fill="x", pady=(0, 10))
            self._sliders[key] = sl

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=4)

        # Toggles
        s3 = lsec(left, "Flags")
        self._toggles = {}
        for label, key in [("Detect Stutters", "detect_stutters"),
                            ("Flag Unclear",    "detect_unclear"),
                            ("Trim Pauses",     "detect_stutters")]:
            real_key = key
            tog = LamboToggle(s3, label, real_key,
                              value=bool(self.settings.get(real_key)),
                              on_change=lambda k, v: self.settings.set(k, v),
                              bg=SURFACE)
            tog.pack(fill="x", pady=3)

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=8)

        # Buttons
        s4 = tk.Frame(left, bg=SURFACE)
        s4.pack(fill="x", padx=SECTION_PAD)
        self._analyze_btn = PrimaryButton(s4, "ANALYZE RECORDING",
                                          command=self._run_analysis)
        self._analyze_btn.pack(fill="x", pady=(0, 6))
        self._apply_btn = SecondaryButton(s4, "APPLY IN AUDACITY",
                                          command=self._apply_in_audacity)
        self._apply_btn.pack(fill="x")
        self._apply_btn.config(state="disabled", fg=TEXT_GHOST)

        tk.Frame(left, bg=EDGE, height=1).pack(fill="x", pady=8)

        # Progress
        s5 = tk.Frame(left, bg=SURFACE)
        s5.pack(fill="x", padx=SECTION_PAD)
        self._progress = LamboProgress(s5, bg=SURFACE)
        self._progress.pack(fill="x")

        # Export (bottom of left panel)
        exp_row = tk.Frame(left, bg=SURFACE)
        exp_row.pack(fill="x", padx=SECTION_PAD, side="bottom", pady=10)
        GhostButton(exp_row, "Export WAV",    self._export_wav,    bg=SURFACE).pack(side="left")
        GhostButton(exp_row, "Export Labels", self._export_labels, bg=SURFACE).pack(side="left", padx=(6,0))

        # ── Right panel ──
        right = tk.Frame(p, bg=CARBON_1)
        right.pack(side="left", fill="both", expand=True)

        # Stats row — Canvas-drawn for guaranteed font rendering on Windows
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

        # Waveform — fixed height, always visible
        wf_wrap = tk.Frame(right, bg=CARBON_2, height=WAVEFORM_H)
        wf_wrap.pack(fill="x")
        wf_wrap.pack_propagate(False)
        self._waveform = WaveformCanvas(wf_wrap, height=WAVEFORM_H, bg=CARBON_2)
        self._waveform.pack(fill="both", expand=True)
        self._waveform.after(200, self._waveform._redraw)
        tk.Frame(right, bg=EDGE, height=1).pack(fill="x")

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

            # Big number — Consolas 26 bold, guaranteed to render
            val = self._stat_values.get(key, "—")
            fg = YELLOW if accent else "#e0e0e0"
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

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open Audio File",
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.ogg *.flac"), ("All", "*.*")])
        if not path:
            return
        self._wav_path = path
        self._filepath_var.set(os.path.basename(path))
        self._set_status(f"Loaded: {os.path.basename(path)}")
        self.results = None
        self._apply_btn.config(state="disabled")
        self._clear_results()
        try:
            kb = os.path.getsize(path) / 1024
            size = f"{kb/1024:.1f}MB" if kb > 1024 else f"{int(kb)}KB"
            self._format_var.set(os.path.splitext(path)[1].upper().lstrip(".") + f"  {size}")
        except Exception:
            pass

    def _clear_results(self):
        for key in self._stat_values:
            self._stat_values[key] = "—"
        self._draw_stat_cards()
        self._flag_tree.delete_all()
        self._waveform.load([], [])

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

    def _ensure_wav(self, path):
        if path.lower().endswith(".wav"):
            return path
        out = tempfile.mktemp(suffix=".wav")
        if os.system(f'ffmpeg -y -i "{path}" "{out}" -loglevel quiet') == 0:
            return out
        self._log("ffmpeg not found — WAV files work without it.")
        return path

    def _on_progress(self, fraction, msg):
        self.after(0, lambda: self._progress.set(fraction, msg))
        self.after(0, lambda: self._set_status(msg))

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

        sr = self.results["sample_rate"]
        flag_samples = []
        for edit in self.results["all_edits"]:
            self._flag_tree.insert(
                edit["type"], fmt_time(edit["start"]), edit["desc"])
            flag_samples.append({
                "type":         edit["type"],
                "start_sample": int(edit["start"] * sr),
                "end_sample":   int(edit["end"]   * sr),
            })

        self._waveform.load(self.results["samples"], flag_samples)
        self._progress.set(1.0, "Analysis complete")
        self._set_status(f"Done — {len(self.results['all_edits'])} issues found")
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

        hdr = tk.Frame(right, bg=CARBON_2, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="ACTIVITY LOG", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_2).pack(side="left", padx=14, pady=6)

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

        btn_row = tk.Frame(frame, bg=CARBON_1)
        btn_row.pack(fill="x", padx=24, pady=20)
        PrimaryButton(btn_row, "SAVE SETTINGS",
                      command=self._save_settings).pack(side="left", padx=(0,8))
        SecondaryButton(btn_row, "RESET DEFAULTS",
                        command=self._reset_settings).pack(side="left")

    def _save_settings(self):
        self.settings.save()
        self._set_status("Settings saved")
        messagebox.showinfo("Saved", "Settings saved.")

    def _reset_settings(self):
        if messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            self.settings.reset_to_defaults()
            self._set_status("Settings reset")
