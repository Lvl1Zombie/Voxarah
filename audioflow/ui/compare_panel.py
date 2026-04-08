"""
Voxarah — Multi-Take Comparison Panel
Side-by-side analysis of up to 3 takes. Shows which take wins per dimension.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog

from coaching.profiles import score_recording, get_all_profiles, get_profile_info
from ui.design import *
from ui.components import PrimaryButton, GhostButton

MAX_TAKES = 3

DIMS = [
    ("pause_ratio",  "Pacing"),
    ("stutters",     "Delivery"),
    ("pause_length", "Pause Length"),
    ("consistency",  "Consistency"),
    ("clarity",      "Clarity"),
    ("pitch",        "Pitch"),
]

STAT_KEYS = [
    ("stutter_count",     "Stutters"),
    ("breath_count",      "Breaths"),
    ("mouth_noise_count", "Mouth Noise"),
    ("pause_count",       "Pauses"),
]


def _score_color(s):
    if s >= 80: return GREEN_OK
    if s >= 60: return YELLOW
    return RED_FLAG


class CompareTakesPanel:
    def __init__(self, parent, settings_manager, ensure_wav_fn):
        self.parent      = parent
        self.settings    = settings_manager
        self._ensure_wav = ensure_wav_fn
        self._takes      = [{} for _ in range(MAX_TAKES)]   # each: path, results, report
        self._build()

    # ── Build ─────────────────────────────────────────────────────

    def _build(self):
        p  = self.parent
        BG = CARBON_1

        # ── Top bar: profile selector + compare button ────────────
        top = tk.Frame(p, bg=CARBON_2, height=48)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Frame(top, bg=YELLOW, width=3).pack(side="left", fill="y")

        tk.Label(top, text="VOICE STYLE", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_2, padx=12).pack(side="left")

        self._profile_var = tk.StringVar(
            value=self.settings.get("coaching_profile"))

        from ui.coaching_panel import _DarkDropdown
        _DarkDropdown(top, values=get_all_profiles(),
                      textvariable=self._profile_var,
                      on_select=self._on_profile_change,
                      width=24, bg=CARBON_2).pack(side="left", padx=(0, 12))

        self._compare_btn = GhostButton(
            top, "RE-SCORE", command=self._rescore_all, bg=CARBON_2)
        self._compare_btn.pack(side="left", pady=8)

        tk.Frame(top, bg=EDGE, height=1).pack(side="bottom", fill="x")

        # ── Summary banner (shown after all scored) ───────────────
        self._banner_frame = tk.Frame(p, bg=CARBON_2, height=36)
        self._banner_frame.pack(fill="x")
        self._banner_frame.pack_propagate(False)
        tk.Frame(self._banner_frame, bg=YELLOW, width=3).pack(side="left", fill="y")
        self._banner_var = tk.StringVar(value="Load 2–3 takes and analyze to compare.")
        tk.Label(self._banner_frame, textvariable=self._banner_var,
                 font=FONT_MONO, fg=TEXT_MUTED, bg=CARBON_2,
                 padx=12).pack(side="left", fill="y")

        tk.Frame(p, bg=EDGE, height=1).pack(fill="x")

        # ── Take columns ──────────────────────────────────────────
        cols_frame = tk.Frame(p, bg=BG)
        cols_frame.pack(fill="both", expand=True)

        self._col_widgets = []
        for i in range(MAX_TAKES):
            sep_needed = i > 0
            if sep_needed:
                tk.Frame(cols_frame, bg=EDGE, width=1).pack(
                    side="left", fill="y", pady=0)
            col = tk.Frame(cols_frame, bg=BG)
            col.pack(side="left", fill="both", expand=True)
            widgets = self._build_take_col(col, i)
            self._col_widgets.append(widgets)

    def _build_take_col(self, parent, idx):
        BG = CARBON_1
        w  = {}  # widget refs

        # Header
        hdr = tk.Frame(parent, bg=CARBON_2, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=CARBON_3 if idx == 0 else BLACK, width=3).pack(
            side="left", fill="y")

        hdr_inner = tk.Frame(hdr, bg=CARBON_2)
        hdr_inner.pack(side="left", fill="both", expand=True, padx=10, pady=6)
        tk.Label(hdr_inner, text=f"TAKE {idx + 1}", font=FONT_MONO,
                 fg=YELLOW, bg=CARBON_2).pack(side="left")
        w["best_badge"] = tk.Label(hdr_inner, text=" BEST ", font=FONT_BADGE,
                                    fg=BLACK, bg=GREEN_OK, padx=4)
        # Not packed yet — shown only when this take is overall winner

        # Load button row
        load_row = tk.Frame(parent, bg=BG)
        load_row.pack(fill="x", padx=10, pady=(8, 0))

        w["load_btn"] = GhostButton(
            load_row, "LOAD FILE", command=lambda i=idx: self._load_take(i),
            bg=CARBON_1)
        w["load_btn"].pack(side="left", fill="x", expand=True, padx=(0, 4))

        w["clear_btn"] = GhostButton(
            load_row, "✕", command=lambda i=idx: self._clear_take(i),
            bg=CARBON_1)
        w["clear_btn"].pack(side="left")

        # Filename + status
        w["filename_var"] = tk.StringVar(value="No file loaded")
        tk.Label(parent, textvariable=w["filename_var"],
                 font=("Consolas", 8), fg=TEXT_GHOST,
                 bg=BG, anchor="w", padx=10, wraplength=220,
                 justify="left").pack(fill="x", pady=(4, 0))

        w["status_var"] = tk.StringVar(value="")
        w["status_lbl"] = tk.Label(parent, textvariable=w["status_var"],
                                    font=FONT_MONO, fg=TEXT_MUTED,
                                    bg=BG, anchor="w", padx=10)
        w["status_lbl"].pack(fill="x")

        # Score box
        score_frame = tk.Frame(parent, bg=CARBON_2,
                                highlightthickness=1,
                                highlightbackground=EDGE_BRIGHT)
        score_frame.pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(score_frame, text="OVERALL", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_2).pack(pady=(6, 0))
        w["score_var"] = tk.StringVar(value="—")
        w["grade_var"] = tk.StringVar(value="")
        w["score_lbl"] = tk.Label(score_frame, textvariable=w["score_var"],
                                   font=("Consolas", 30, "bold"),
                                   fg=TEXT_GHOST, bg=CARBON_2)
        w["score_lbl"].pack()
        tk.Label(score_frame, textvariable=w["grade_var"],
                 font=("Consolas", 12, "bold"), fg=YELLOW_DIM,
                 bg=CARBON_2).pack(pady=(0, 4))

        # Analyze button (inside score frame, shown when file loaded)
        w["analyze_btn"] = PrimaryButton(
            score_frame, "ANALYZE",
            command=lambda i=idx: self._analyze_take(i))
        w["analyze_btn"].config(state="disabled")
        w["analyze_btn"].pack(pady=(0, 8), padx=10, fill="x")

        # Dimension bars
        tk.Frame(parent, bg=EDGE, height=1).pack(fill="x", padx=10, pady=(8, 0))
        dims_frame = tk.Frame(parent, bg=BG)
        dims_frame.pack(fill="x", padx=10, pady=4)
        w["dim_vars"] = {}
        for key, lbl_text in DIMS:
            r = tk.Frame(dims_frame, bg=BG)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=lbl_text.upper(), font=FONT_MONO,
                     fg=TEXT_MUTED, bg=BG, width=14, anchor="w").pack(side="left")
            track = tk.Frame(r, bg=EDGE_BRIGHT, height=5)
            track.pack(side="left", fill="x", expand=True, padx=(0, 4))
            track.pack_propagate(False)
            fill = tk.Frame(track, bg=YELLOW, height=5)
            fill.place(x=0, y=0, relheight=1, relwidth=0)
            val_lbl = tk.Label(r, text="—", font=FONT_MONO,
                                fg=TEXT_MUTED, bg=BG, width=3)
            val_lbl.pack(side="left")
            best_dot = tk.Label(r, text="●", font=("Consolas", 8),
                                 fg=BG, bg=BG)
            best_dot.pack(side="left", padx=2)
            w["dim_vars"][key] = (fill, val_lbl, best_dot)

        # Issue counts
        tk.Frame(parent, bg=EDGE, height=1).pack(fill="x", padx=10, pady=(6, 0))
        stats_frame = tk.Frame(parent, bg=BG)
        stats_frame.pack(fill="x", padx=10, pady=4)
        w["stat_vars"] = {}
        for key, lbl_text in STAT_KEYS:
            r = tk.Frame(stats_frame, bg=BG)
            r.pack(fill="x", pady=1)
            tk.Label(r, text=lbl_text, font=FONT_MONO,
                     fg=TEXT_MUTED, bg=BG, width=14, anchor="w").pack(side="left")
            val_lbl = tk.Label(r, text="—", font=("Consolas", 10, "bold"),
                                fg=TEXT_GHOST, bg=BG)
            val_lbl.pack(side="left")
            w["stat_vars"][key] = val_lbl

        # Pitch rating
        tk.Frame(parent, bg=EDGE, height=1).pack(fill="x", padx=10, pady=(4, 0))
        pitch_row = tk.Frame(parent, bg=BG)
        pitch_row.pack(fill="x", padx=10, pady=4)
        tk.Label(pitch_row, text="PITCH", font=FONT_MONO,
                 fg=TEXT_MUTED, bg=BG, width=14, anchor="w").pack(side="left")
        w["pitch_var"] = tk.StringVar(value="—")
        w["pitch_lbl"] = tk.Label(pitch_row, textvariable=w["pitch_var"],
                                   font=("Consolas", 10, "bold"),
                                   fg=TEXT_GHOST, bg=BG)
        w["pitch_lbl"].pack(side="left")

        return w

    # ── File loading ──────────────────────────────────────────────

    def _load_take(self, idx):
        path = filedialog.askopenfilename(
            title=f"Load Take {idx + 1}",
            filetypes=[("Audio Files", "*.wav *.mp3 *.m4a *.flac *.ogg"),
                       ("All Files", "*.*")])
        if not path:
            return
        self._takes[idx] = {"path": path, "results": None, "report": None}
        w = self._col_widgets[idx]
        w["filename_var"].set(os.path.basename(path))
        w["status_var"].set("Ready to analyze")
        w["status_lbl"].config(fg=TEXT_MUTED)
        w["analyze_btn"].config(state="normal")
        # Clear any previous score
        self._reset_col_display(idx)

    def _clear_take(self, idx):
        self._takes[idx] = {}
        w = self._col_widgets[idx]
        w["filename_var"].set("No file loaded")
        w["status_var"].set("")
        w["analyze_btn"].config(state="disabled")
        self._reset_col_display(idx)
        self._update_banner()

    def _reset_col_display(self, idx):
        w = self._col_widgets[idx]
        w["score_var"].set("—")
        w["grade_var"].set("")
        w["score_lbl"].config(fg=TEXT_GHOST)
        w["best_badge"].pack_forget()
        for key, (fill, val_lbl, dot) in w["dim_vars"].items():
            fill.place(relwidth=0)
            val_lbl.config(text="—", fg=TEXT_MUTED)
            dot.config(fg=CARBON_1)
        for key, lbl in w["stat_vars"].items():
            lbl.config(text="—", fg=TEXT_GHOST)
        w["pitch_var"].set("—")
        w["pitch_lbl"].config(fg=TEXT_GHOST)

    # ── Analysis ──────────────────────────────────────────────────

    def _analyze_take(self, idx):
        take = self._takes[idx]
        if not take.get("path"):
            return
        w = self._col_widgets[idx]
        w["analyze_btn"].config(state="disabled")
        w["status_var"].set("Analyzing...")
        w["status_lbl"].config(fg=YELLOW)

        def task():
            try:
                from core.analyzer import AudioAnalyzer
                wav = self._ensure_wav(take["path"])
                if not wav:
                    self.parent.after(0, lambda: self._take_error(idx, "Conversion failed"))
                    return
                analyzer = AudioAnalyzer(self.settings.analysis_settings())
                results  = analyzer.analyze(wav)
                profile  = self._profile_var.get()
                report   = score_recording(results, profile)
                take["results"] = results
                take["report"]  = report
                self.parent.after(0, lambda: self._show_take(idx))
            except Exception as e:
                self.parent.after(0, lambda: self._take_error(idx, str(e)))
            finally:
                self.parent.after(0,
                    lambda: w["analyze_btn"].config(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def _take_error(self, idx, msg):
        w = self._col_widgets[idx]
        w["status_var"].set(f"Error: {msg[:40]}")
        w["status_lbl"].config(fg=RED_FLAG)

    def _show_take(self, idx):
        take = self._takes[idx]
        report  = take.get("report")
        results = take.get("results")
        if not report:
            return

        w = self._col_widgets[idx]
        sc  = report["overall"]
        col = _score_color(sc)

        w["score_var"].set(str(sc))
        w["grade_var"].set(report.get("grade", ""))
        w["score_lbl"].config(fg=col)
        w["status_var"].set("Done")
        w["status_lbl"].config(fg=GREEN_OK)

        for key, (fill, val_lbl, dot) in w["dim_vars"].items():
            s = report["scores"].get(key, 0)
            fill.place(relwidth=s / 100)
            fill.config(bg=_score_color(s))
            val_lbl.config(text=str(s), fg=_score_color(s))

        if results:
            stats = results.get("stats", {})
            for key, lbl in w["stat_vars"].items():
                val = stats.get(key, 0)
                lbl.config(text=str(val),
                           fg=YELLOW if val > 0 else GREEN_OK)

            ps = results.get("pitch_stats", {})
            rating = ps.get("rating", "—")
            pitch_col = (GREEN_OK if rating == "EXPRESSIVE"
                         else YELLOW if rating == "MODERATE"
                         else RED_FLAG if rating == "FLAT"
                         else TEXT_GHOST)
            w["pitch_var"].set(rating)
            w["pitch_lbl"].config(fg=pitch_col)

        self._refresh_comparisons()

    def _rescore_all(self):
        """Re-score all loaded takes with the current profile."""
        profile = self._profile_var.get()
        for idx, take in enumerate(self._takes):
            if take.get("results"):
                take["report"] = score_recording(take["results"], profile)
                self._show_take(idx)

    def _on_profile_change(self, _=None):
        self._rescore_all()

    # ── Comparison highlighting ───────────────────────────────────

    def _refresh_comparisons(self):
        """Highlight winners per dimension and overall. Update banner."""
        scored = [(i, t) for i, t in enumerate(self._takes)
                  if t.get("report")]
        if len(scored) < 2:
            self._update_banner()
            return

        # Overall winner
        best_overall = max(scored, key=lambda x: x[1]["report"]["overall"])
        for i, _ in scored:
            w = self._col_widgets[i]
            if i == best_overall[0]:
                w["best_badge"].pack(side="right", padx=(6, 10))
            else:
                w["best_badge"].pack_forget()

        # Per-dimension: highlight best dot green, rest invisible
        for key, _ in DIMS:
            best_idx = max(scored,
                           key=lambda x: x[1]["report"]["scores"].get(key, 0))[0]
            for i, _ in scored:
                _, _, dot = self._col_widgets[i]["dim_vars"][key]
                dot.config(fg=GREEN_OK if i == best_idx else CARBON_1)

        self._update_banner(scored, best_overall)

    def _update_banner(self, scored=None, best_overall=None):
        if not scored or len(scored) < 2:
            self._banner_var.set(
                "Load 2–3 takes and analyze to compare.")
            return

        best_i, best_take = best_overall
        best_score = best_take["report"]["overall"]
        take_label = f"Take {best_i + 1}"

        # Find strongest dimensions for the winner
        report = best_take["report"]
        dim_scores = [(lbl, report["scores"].get(key, 0))
                      for key, lbl in DIMS]
        top_dims = sorted(dim_scores, key=lambda x: x[1], reverse=True)[:2]
        top_str  = " · ".join(f"{lbl} {sc}" for lbl, sc in top_dims)

        self._banner_var.set(
            f"  ● {take_label} is your best take — {best_score} overall     "
            f"Strongest in: {top_str}")
