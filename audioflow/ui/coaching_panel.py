"""
Voxarah — Character Coaching UI
Custom tab system matching the main app — no ttk.Notebook.
Matte black + yellow. Consistent with Editor tab.
"""

import tkinter as tk
from coaching.characters import (
    score_character, get_all_categories, get_category_characters,
    CATEGORIES, CATEGORY_EMOJIS, CHARACTER_DB
)
from coaching.profiles import score_recording, get_all_profiles, get_profile_info
from core.history import save_session, load_history, build_record
from core.retake  import find_retake_regions, retake_summary
from ui.design import *

DIFF_COLORS = {
    'Beginner':     GREEN_OK,
    'Intermediate': YELLOW,
    'Advanced':     RED_FLAG,
}

def score_color(score):
    if score >= 80: return GREEN_OK
    if score >= 60: return YELLOW
    return RED_FLAG


def _sec_label(parent, text, bg=CARBON_1):
    """Uppercase mono section label with hairline."""
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", padx=0, pady=(8, 4))
    tk.Label(row, text=text.upper(), font=FONT_MONO, fg=TEXT_GHOST,
             bg=bg).pack(side="left", padx=(0, 8))
    tk.Frame(row, bg=EDGE, height=1).pack(side="left", fill="x", expand=True)
    return row


def _text_box(parent, height=5, fg_color=None, bg=CARBON_2):
    """Dark read-only text area with custom dark scrollbar."""
    from ui.components import DarkScrollbar
    wrap = tk.Frame(parent, bg=bg)
    wrap._is_text_box = True

    t = tk.Text(wrap, height=height, font=FONT_MONO_MED,
                bg=bg, fg=fg_color or TEXT,
                relief="flat", wrap="word", bd=0,
                insertbackground=YELLOW,
                selectbackground=YELLOW_SUBTLE,
                selectforeground=YELLOW,
                yscrollcommand=lambda *a: sb.set(*a))
    sb = DarkScrollbar(wrap, command=t.yview, bg=CARBON_1)

    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    t.config(state="disabled")

    # Proxy pack/grid/place so callers can do _text_box(...).pack(...)
    wrap.pack = wrap.pack
    # Forward .config, .get, .insert, .delete, .see to the inner Text
    for attr in ("config", "configure", "get", "insert", "delete", "see",
                 "index", "mark_set", "tag_add", "tag_config"):
        setattr(wrap, attr, getattr(t, attr))

    return wrap


class _DarkDropdown(tk.Frame):
    """Dark-themed dropdown replacing ttk.Combobox."""
    def __init__(self, parent, values, textvariable, on_select=None, width=26, **kw):
        bg = kw.pop("bg", CARBON_2)
        super().__init__(parent, bg=bg,
                         highlightthickness=1, highlightbackground=EDGE_BRIGHT, **kw)
        self._values    = values
        self._var       = textvariable
        self._on_select = on_select
        self._popup     = None

        self._lbl = tk.Label(self, textvariable=self._var,
                              font=FONT_BODY, fg=TEXT, bg=bg,
                              anchor="w", padx=8, width=width, cursor="hand2")
        self._lbl.pack(side="left", fill="both", expand=True)

        arrow = tk.Label(self, text="▾", font=("Segoe UI", 9), fg=TEXT_MUTED,
                          bg=bg, padx=6, cursor="hand2")
        arrow.pack(side="right")

        for w in (self, self._lbl, arrow):
            w.bind("<Button-1>", self._toggle)

    def _toggle(self, _=None):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
            self._popup = None
            return
        self._open()

    def _open(self):
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()

        pop = tk.Toplevel(self)
        pop.wm_overrideredirect(True)
        pop.geometry(f"{w}x{min(len(self._values)*26, 260)}+{x}+{y}")
        pop.configure(bg=CARBON_2)
        pop.attributes("-topmost", True)
        self._popup = pop

        canvas = tk.Canvas(pop, bg=CARBON_2, highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=CARBON_2)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        for val in self._values:
            row = tk.Label(inner, text=val, font=FONT_BODY,
                            fg=TEXT, bg=CARBON_2, anchor="w",
                            padx=10, pady=4, cursor="hand2")
            row.pack(fill="x")
            tk.Frame(inner, bg=EDGE, height=1).pack(fill="x")

            def _pick(e, v=val):
                self._var.set(v)
                pop.destroy()
                self._popup = None
                if self._on_select:
                    self._on_select(v)
            row.bind("<Button-1>", _pick)
            row.bind("<Enter>", lambda e, r=row: r.config(bg=CARBON_3))
            row.bind("<Leave>", lambda e, r=row: r.config(bg=CARBON_2))

        pop.bind("<FocusOut>", lambda e: pop.destroy())
        pop.focus_set()

    def get(self):
        return self._var.get()

    def set(self, v):
        self._var.set(v)


def _ghost_btn(parent, text, cmd, bg=CARBON_3):
    b = tk.Button(parent, text=text, command=cmd, relief="flat", cursor="hand2",
                  bg=bg, fg=TEXT_MUTED, font=FONT_BTN, padx=10, pady=5, bd=0,
                  activebackground=CARBON_4, activeforeground=TEXT)
    b.bind("<Enter>", lambda e: b.config(bg=CARBON_4, fg=TEXT))
    b.bind("<Leave>", lambda e: b.config(bg=bg, fg=TEXT_MUTED))
    return b


def _primary_btn(parent, text, cmd):
    from ui.components import PrimaryButton
    return PrimaryButton(parent, text, command=cmd)


# ─────────────────────────────────────────────────────────────────────────────

class CoachingTabManager:
    def __init__(self, parent_frame, settings_manager, ai_coach=None, voice_engine=None):
        self.parent   = parent_frame
        self.settings = settings_manager
        self.results  = None
        self.ai_coach = ai_coach
        self.voice    = voice_engine
        self._build()

    def set_results(self, results, filename=None):
        self.results  = results
        self._filename = filename
        report = self._style_panel.refresh(results)
        if report and results:
            rec = build_record(filename or "", self._style_panel._profile_var.get(),
                               report, results)
            save_session(rec)
            if hasattr(self, "_history_panel"):
                self._history_panel.refresh()
        for cat, panel in self._char_panels.items():
            panel.mark_dirty()
            # If this category tab is currently active, refresh it now
            # rather than waiting for the user to switch away and back.
            if cat.lower() == self._active_sub:
                panel.refresh_if_dirty()

    def _build(self):
        p = self.parent

        # ── Custom sub-tab bar (matches main app exactly) ─────────
        tabbar = tk.Frame(p, bg=BLACK, height=36)
        tabbar.pack(fill="x", side="top")
        tabbar.pack_propagate(False)

        self._sub_btns   = {}
        self._sub_unders = {}
        self._sub_frames = {}
        self._active_sub = None

        all_tabs = [("style", f"  \U0001f399  Style  ")] + [
            (cat.lower(), f"  {CATEGORY_EMOJIS.get(cat, '')}  {cat}  ")
            for cat in get_all_categories()
        ] + [("history", "  \U0001f4c8  History  ")]

        for key, label in all_tabs:
            wrap = tk.Frame(tabbar, bg=BLACK)
            wrap.pack(side="left")
            btn = tk.Label(wrap, text=label, font=FONT_TAB,
                           fg=TEXT_DIM, bg=BLACK, cursor="hand2", pady=4)
            btn.pack(side="top")
            btn.bind("<Button-1>", lambda e, k=key: self._switch(k))
            self._sub_btns[key] = btn
            under = tk.Frame(wrap, bg=BLACK, height=2)
            under.pack(fill="x", side="bottom")
            self._sub_unders[key] = under

        tk.Frame(p, bg=EDGE, height=1).pack(fill="x")

        # ── Tab content frames ────────────────────────────────────
        body = tk.Frame(p, bg=CARBON_1)
        body.pack(fill="both", expand=True)

        # Style tab
        style_frame = tk.Frame(body, bg=CARBON_1)
        self._sub_frames["style"] = style_frame
        self._style_panel = StyleCoachingPanel(style_frame, self.settings,
                                               self.ai_coach, self.voice)
        self._char_panels = {}
        for cat in get_all_categories():
            key = cat.lower()
            f = tk.Frame(body, bg=CARBON_1)
            self._sub_frames[key] = f
            panel = CategoryPanel(f, cat, self.settings, lambda: self.results,
                                  self.ai_coach, self.voice)
            self._char_panels[cat] = panel

        # History tab
        history_frame = tk.Frame(body, bg=CARBON_1)
        self._sub_frames["history"] = history_frame
        self._history_panel = HistoryPanel(history_frame)

        self._switch("style")

    def _switch(self, key):
        if self._active_sub == key:
            return
        self._active_sub = key
        for k, btn in self._sub_btns.items():
            active = (k == key)
            btn.config(fg=YELLOW if active else TEXT_GHOST,
                       bg=CARBON_2 if active else BLACK)
            btn.master.config(bg=CARBON_2 if active else BLACK)
            self._sub_unders[k].config(bg=YELLOW if active else BLACK)

        for k, frame in self._sub_frames.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        # Refresh character panel when switched to
        for cat, panel in self._char_panels.items():
            if cat.lower() == key:
                panel.refresh_if_dirty()
                break

        if key == "history" and hasattr(self, "_history_panel"):
            self._history_panel.refresh()


# ─────────────────────────────────────────────────────────────────────────────
# StyleCoachingPanel
# ─────────────────────────────────────────────────────────────────────────────

class StyleCoachingPanel:
    def __init__(self, parent, settings, ai_coach=None, voice_engine=None):
        self.parent   = parent
        self.settings = settings
        self.ai_coach = ai_coach
        self.voice    = voice_engine
        self.results  = None
        self._last_report = None
        self._build()

    def _build(self):
        p = self.parent
        BG = CARBON_1

        # ── Voice style selector row ──────────────────────────────
        top = tk.Frame(p, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(top, text="VOICE STYLE", font=FONT_MONO, fg=TEXT_GHOST,
                 bg=BG).pack(side="left", padx=(0, 8))

        self._profile_var = tk.StringVar(value=self.settings.get("coaching_profile"))
        cb = _DarkDropdown(top, values=get_all_profiles(),
                           textvariable=self._profile_var, width=26,
                           on_select=lambda v: self.refresh(self.results))
        cb.pack(side="left", padx=(0, 8))

        refresh_btn = tk.Button(top, text="REFRESH", font=FONT_BTN,
                                bg=CARBON_3, fg=TEXT_MUTED, relief="flat",
                                bd=0, padx=12, pady=4, cursor="hand2",
                                activebackground=CARBON_4, activeforeground=TEXT,
                                command=lambda: self.refresh(self.results))
        refresh_btn.pack(side="left")

        self._desc_var = tk.StringVar()
        tk.Label(p, textvariable=self._desc_var, font=FONT_SMALL, fg=TEXT_MUTED,
                 bg=BG, wraplength=820, justify="left", padx=16).pack(
                     fill="x", pady=(0, 8))

        # ── Score row ─────────────────────────────────────────────
        score_row = tk.Frame(p, bg=BG)
        score_row.pack(fill="x", padx=16, pady=(0, 8))

        # Big score box
        score_box = tk.Frame(score_row, bg=CARBON_2,
                              highlightthickness=1, highlightbackground=EDGE_BRIGHT)
        score_box.pack(side="left", padx=(0, 12), ipadx=16, ipady=10)
        tk.Label(score_box, text="OVERALL", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_2).pack(pady=(6, 0))
        self._score_var = tk.StringVar(value="\u2014")
        self._grade_var = tk.StringVar(value="")
        tk.Label(score_box, textvariable=self._score_var,
                 font=("Consolas", 30, "bold"), fg=YELLOW, bg=CARBON_2).pack()
        tk.Label(score_box, textvariable=self._grade_var,
                 font=("Consolas", 13, "bold"), fg=YELLOW_DIM, bg=CARBON_2).pack(pady=(0, 6))

        # Dimension bars
        dims_f = tk.Frame(score_row, bg=BG)
        dims_f.pack(side="left", fill="both", expand=True)
        self._dim_vars = {}
        for key, lbl in [("pause_ratio",  "Pacing"),
                          ("stutters",     "Delivery"),
                          ("pause_length", "Pause Length"),
                          ("consistency",  "Consistency"),
                          ("clarity",      "Clarity"),
                          ("pitch",        "Pitch")]:
            r = tk.Frame(dims_f, bg=BG)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=lbl.upper(), font=FONT_MONO, fg=TEXT_MUTED,
                     bg=BG, width=16, anchor="w").pack(side="left")
            track = tk.Frame(r, bg=EDGE_BRIGHT, height=6)
            track.pack(side="left", fill="x", expand=True, padx=(0, 8))
            track.pack_propagate(False)
            fill = tk.Frame(track, bg=YELLOW, height=6)
            fill.place(x=0, y=0, relheight=1, relwidth=0)
            slbl = tk.Label(r, text="\u2014", font=FONT_MONO, fg=TEXT_MUTED,
                             bg=BG, width=4)
            slbl.pack(side="left")
            self._dim_vars[key] = (fill, slbl)

        tk.Frame(p, bg=EDGE, height=1).pack(fill="x", padx=16, pady=(0, 4))

        # Feedback + Tips side by side
        mid = tk.Frame(p, bg=BG)
        mid.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        left_m = tk.Frame(mid, bg=BG)
        left_m.pack(side="left", fill="both", expand=True, padx=(0, 8))
        _sec_label(left_m, "Feedback", bg=BG)
        self._fb_text = _text_box(left_m, height=6, fg_color=TEXT, bg=CARBON_2)
        self._fb_text.pack(fill="both", expand=True)

        right_m = tk.Frame(mid, bg=BG)
        right_m.pack(side="left", fill="both", expand=True)
        _sec_label(right_m, "Style Tips", bg=BG)
        self._tips_text = _text_box(right_m, height=6, fg_color=YELLOW, bg=CARBON_2)
        self._tips_text.pack(fill="both", expand=True)

        tk.Frame(p, bg=YELLOW, height=1).pack(fill="x", padx=16, pady=(4, 0))

        # AI Coach section
        ai_hdr = tk.Frame(p, bg=BG)
        ai_hdr.pack(fill="x", padx=16, pady=(6, 2))
        tk.Label(ai_hdr, text="AI COACH", font=FONT_MONO,
                 fg=YELLOW, bg=BG).pack(side="left")
        self._ai_status_var = tk.StringVar(value="")
        tk.Label(ai_hdr, textvariable=self._ai_status_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BG).pack(side="right")

        self._ai_text = _text_box(p, height=5, fg_color=TEXT, bg=CARBON_2)
        self._ai_text.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        ai_btns = tk.Frame(p, bg=BG)
        ai_btns.pack(fill="x", padx=16, pady=(0, 10))
        _primary_btn(ai_btns, "GET AI COACHING", self._get_ai_coaching).pack(side="left", padx=(0, 6))
        _ghost_btn(ai_btns, "SPEAK", self._speak_coaching).pack(side="left", padx=(0, 4))
        _ghost_btn(ai_btns, "STOP",  self._stop_speaking).pack(side="left")

        self._refresh_desc()

    def _refresh_desc(self):
        name = self._profile_var.get()
        info = get_profile_info(name)
        self._desc_var.set(f"{info.get('emoji','')}  {info.get('description','')}")

    def refresh(self, results):
        self.results = results
        self._refresh_desc()
        if not results:
            return
        name   = self._profile_var.get()
        report = score_recording(results, name)
        self.settings.set("coaching_profile", name)

        self._score_var.set(str(report["overall"]))
        self._grade_var.set(report["grade"])

        for key, (bar, lbl) in self._dim_vars.items():
            s = report["scores"].get(key, 0)
            bar.place(relwidth=s / 100)
            bar.config(bg=score_color(s))
            lbl.config(text=str(s), fg=score_color(s))

        self._fb_text.config(state="normal")
        self._fb_text.delete("1.0", "end")
        for dim, msg in (report["feedback"] or []):
            self._fb_text.insert("end", f"  {dim}\n  {msg}\n\n")
        if not report["feedback"]:
            self._fb_text.insert("end", "  No major issues for this style.")
        self._fb_text.config(state="disabled")

        self._tips_text.config(state="normal")
        self._tips_text.delete("1.0", "end")
        for i, tip in enumerate(report["tips"], 1):
            self._tips_text.insert("end", f"  {i}. {tip}\n\n")
        self._tips_text.config(state="disabled")

        self._last_report = report
        self._refresh_retake(results, report)
        return report

    def _refresh_retake(self, results, report):
        """Update the Retake Guide with region-specific coaching."""
        for w in self._retake_regions_frame.winfo_children():
            w.destroy()

        suggestions = find_retake_regions(results, report)
        summary     = retake_summary(suggestions, report.get("overall", 0))
        self._retake_summary_var.set(summary)

        for s in suggestions:
            row = tk.Frame(self._retake_regions_frame, bg=CARBON_2)
            row.pack(fill="x", pady=(6, 0))

            # Time badge
            badge = tk.Label(row, text=s["label"],
                              font=("Consolas", 9, "bold"),
                              fg=BLACK, bg=YELLOW, padx=6, pady=2)
            badge.pack(side="left", anchor="n", pady=(2, 0))

            # Reason text
            tk.Label(row, text=s["reason"],
                     font=FONT_SMALL, fg=TEXT_MUTED, bg=CARBON_2,
                     anchor="w", justify="left", wraplength=620,
                     padx=8).pack(side="left", fill="x", expand=True)

    def _get_ai_coaching(self):
        if not self.ai_coach or not self._last_report:
            return
        self._ai_btn_ref.config(state="disabled")
        self._ai_text.config(state="normal")
        self._ai_text.delete("1.0", "end")
        self._ai_text.config(state="disabled")
        self._ai_status_var.set("THINKING...")
        name   = self._profile_var.get()
        report = self._last_report
        def on_token(t): self.parent.after(0, lambda tok=t: self._append_token(tok))
        def on_done(_):  self.parent.after(0, self._ai_done)
        self.ai_coach.get_coaching(
            name,
            {"overall": report["overall"], "grade": report["grade"], "scores": report["scores"]},
            report.get("feedback", []),
            on_token=on_token, on_done=on_done)

    def _append_token(self, t):
        self._ai_text.config(state="normal")
        self._ai_text.insert("end", t)
        self._ai_text.see("end")
        self._ai_text.config(state="disabled")

    def _ai_done(self):
        self._ai_btn_ref.config(state="normal")
        self._ai_status_var.set("READY")

    def _speak_coaching(self):
        if not self.voice: return
        text = self._ai_text.get("1.0", "end").strip()
        if not text: return
        self._ai_status_var.set("SPEAKING...")
        self.voice.set_status_callback(
            lambda sp: self.parent.after(0, lambda: self._ai_status_var.set(
                "SPEAKING..." if sp else "READY")))
        self.voice.speak(text)

    def _stop_speaking(self):
        if self.voice: self.voice.stop()
        self._ai_status_var.set("READY")

    def _build(self):
        # Wrapped so we can store button ref after creation
        p = self.parent
        BG = CARBON_1

        top = tk.Frame(p, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(top, text="VOICE STYLE", font=FONT_MONO, fg=TEXT_GHOST,
                 bg=BG).pack(side="left", padx=(0, 8))

        self._profile_var = tk.StringVar(value=self.settings.get("coaching_profile"))
        cb = _DarkDropdown(top, values=get_all_profiles(),
                           textvariable=self._profile_var, width=26,
                           on_select=lambda v: self.refresh(self.results))
        cb.pack(side="left", padx=(0, 8))
        refresh_btn = tk.Button(top, text="REFRESH", font=FONT_BTN,
                                bg=CARBON_3, fg=TEXT_MUTED, relief="flat",
                                bd=0, padx=12, pady=4, cursor="hand2",
                                activebackground=CARBON_4, activeforeground=TEXT,
                                command=lambda: self.refresh(self.results))
        refresh_btn.pack(side="left")

        self._desc_var = tk.StringVar()
        tk.Label(p, textvariable=self._desc_var, font=FONT_SMALL, fg=TEXT_MUTED,
                 bg=BG, wraplength=820, justify="left", padx=16).pack(fill="x", pady=(0, 8))

        score_row = tk.Frame(p, bg=BG)
        score_row.pack(fill="x", padx=16, pady=(0, 8))

        score_box = tk.Frame(score_row, bg=CARBON_2,
                              highlightthickness=1, highlightbackground=EDGE_BRIGHT)
        score_box.pack(side="left", padx=(0, 12), ipadx=16, ipady=10)
        tk.Label(score_box, text="OVERALL", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_2).pack(pady=(6, 0))
        self._score_var = tk.StringVar(value="\u2014")
        self._grade_var = tk.StringVar(value="")
        tk.Label(score_box, textvariable=self._score_var,
                 font=("Consolas", 30, "bold"), fg=YELLOW, bg=CARBON_2).pack()
        tk.Label(score_box, textvariable=self._grade_var,
                 font=("Consolas", 13, "bold"), fg=YELLOW_DIM, bg=CARBON_2).pack(pady=(0, 6))

        dims_f = tk.Frame(score_row, bg=BG)
        dims_f.pack(side="left", fill="both", expand=True)
        self._dim_vars = {}
        for key, lbl in [("pause_ratio",  "Pacing"),
                          ("stutters",     "Delivery"),
                          ("pause_length", "Pause Length"),
                          ("consistency",  "Consistency"),
                          ("clarity",      "Clarity"),
                          ("pitch",        "Pitch")]:
            r = tk.Frame(dims_f, bg=BG)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=lbl.upper(), font=FONT_MONO, fg=TEXT_MUTED,
                     bg=BG, width=16, anchor="w").pack(side="left")
            track = tk.Frame(r, bg=EDGE_BRIGHT, height=6)
            track.pack(side="left", fill="x", expand=True, padx=(0, 8))
            track.pack_propagate(False)
            fill = tk.Frame(track, bg=YELLOW, height=6)
            fill.place(x=0, y=0, relheight=1, relwidth=0)
            slbl = tk.Label(r, text="\u2014", font=FONT_MONO, fg=TEXT_MUTED, bg=BG, width=4)
            slbl.pack(side="left")
            self._dim_vars[key] = (fill, slbl)

        tk.Frame(p, bg=EDGE, height=1).pack(fill="x", padx=16, pady=(4, 4))

        mid = tk.Frame(p, bg=BG)
        mid.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        left_m = tk.Frame(mid, bg=BG)
        left_m.pack(side="left", fill="both", expand=True, padx=(0, 8))
        _sec_label(left_m, "Feedback", bg=BG)
        self._fb_text = _text_box(left_m, height=6, fg_color=TEXT, bg=CARBON_2)
        self._fb_text.pack(fill="both", expand=True)

        right_m = tk.Frame(mid, bg=BG)
        right_m.pack(side="left", fill="both", expand=True)
        _sec_label(right_m, "Style Tips", bg=BG)
        self._tips_text = _text_box(right_m, height=6, fg_color=YELLOW, bg=CARBON_2)
        self._tips_text.pack(fill="both", expand=True)

        # ── Retake Guide ──────────────────────────────────────────
        tk.Frame(p, bg=EDGE, height=1).pack(fill="x", padx=16, pady=(6, 0))

        retake_hdr = tk.Frame(p, bg=BG)
        retake_hdr.pack(fill="x", padx=16, pady=(6, 2))
        tk.Label(retake_hdr, text="\u27a9  RETAKE GUIDE", font=FONT_MONO,
                 fg=YELLOW, bg=BG).pack(side="left")

        self._retake_frame = tk.Frame(p, bg=CARBON_2,
                                       highlightthickness=1,
                                       highlightbackground=EDGE_BRIGHT)
        self._retake_frame.pack(fill="x", padx=16, pady=(0, 6))
        tk.Frame(self._retake_frame, bg=YELLOW, width=3).pack(side="left", fill="y")
        self._retake_inner = tk.Frame(self._retake_frame, bg=CARBON_2)
        self._retake_inner.pack(side="left", fill="both", expand=True,
                                 padx=10, pady=8)
        self._retake_summary_var = tk.StringVar(
            value="Analyze a recording to get retake guidance.")
        tk.Label(self._retake_inner, textvariable=self._retake_summary_var,
                 font=("Segoe UI", 10, "bold"), fg=TEXT,
                 bg=CARBON_2, anchor="w", wraplength=700,
                 justify="left").pack(fill="x")
        self._retake_regions_frame = tk.Frame(self._retake_inner, bg=CARBON_2)
        self._retake_regions_frame.pack(fill="x", pady=(4, 0))

        tk.Frame(p, bg=YELLOW, height=1).pack(fill="x", padx=16, pady=(4, 0))

        ai_hdr = tk.Frame(p, bg=BG)
        ai_hdr.pack(fill="x", padx=16, pady=(6, 2))
        tk.Label(ai_hdr, text="AI COACH", font=FONT_MONO, fg=YELLOW, bg=BG).pack(side="left")
        self._ai_status_var = tk.StringVar(value="")
        tk.Label(ai_hdr, textvariable=self._ai_status_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BG).pack(side="right")

        self._ai_text = _text_box(p, height=5, fg_color=TEXT, bg=CARBON_2)
        self._ai_text.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        ai_btns = tk.Frame(p, bg=BG)
        ai_btns.pack(fill="x", padx=16, pady=(0, 10))
        from ui.components import PrimaryButton
        self._ai_btn_ref = PrimaryButton(ai_btns, "GET AI COACHING", self._get_ai_coaching)
        self._ai_btn_ref.pack(side="left", padx=(0, 6))
        _ghost_btn(ai_btns, "SPEAK", self._speak_coaching).pack(side="left", padx=(0, 4))
        _ghost_btn(ai_btns, "STOP",  self._stop_speaking).pack(side="left")

        self._refresh_desc()


# ─────────────────────────────────────────────────────────────────────────────
# CategoryPanel
# ─────────────────────────────────────────────────────────────────────────────

class CategoryPanel:
    def __init__(self, parent, category, settings, get_results_fn,
                 ai_coach=None, voice_engine=None):
        self.parent      = parent
        self.category    = category
        self.settings    = settings
        self.get_results = get_results_fn
        self.ai_coach    = ai_coach
        self.voice       = voice_engine
        self._dirty      = True
        self._last_report = None
        self._build()

    def mark_dirty(self):
        self._dirty = True

    def refresh_if_dirty(self):
        if self._dirty:
            self._refresh()
            self._dirty = False

    def _build(self):
        p = self.parent
        BG = CARBON_1
        characters = get_category_characters(self.category)

        # ── Left: character list ──────────────────────────────────
        left = tk.Frame(p, bg=CARBON_2, width=200)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Frame(left, bg=EDGE, width=1).pack(side="right", fill="y")

        emoji = CATEGORY_EMOJIS.get(self.category, "")
        tk.Label(left, text=f"{emoji}  {self.category.upper()}",
                 font=FONT_MONO, fg=YELLOW, bg=CARBON_2,
                 padx=12, pady=10, anchor="w").pack(fill="x")
        tk.Frame(left, bg=YELLOW, height=1).pack(fill="x")

        self._selected_char = tk.StringVar(value=characters[0] if characters else "")
        self._char_buttons  = {}

        for char_name in characters:
            diff     = CHARACTER_DB.get(char_name, {}).get("difficulty", "Beginner")
            diff_col = DIFF_COLORS.get(diff, TEXT_MUTED)
            row = tk.Frame(left, bg=CARBON_2, cursor="hand2")
            row.pack(fill="x")
            tk.Frame(left, bg=EDGE, height=1).pack(fill="x")

            name_lbl = tk.Label(row, text=char_name, font=FONT_BODY,
                                 fg=TEXT, bg=CARBON_2, anchor="w",
                                 padx=12, pady=6)
            name_lbl.pack(side="left", fill="x", expand=True)
            diff_lbl = tk.Label(row, text=diff, font=("Consolas", 7, "bold"),
                                 fg=diff_col, bg=CARBON_2, padx=8)
            diff_lbl.pack(side="right")

            def _enter(e, r=row):
                for w in [r] + list(r.winfo_children()): w.config(bg=CARBON_3)
            def _leave(e, r=row, cn=char_name):
                col = CARBON_3 if self._selected_char.get() == cn else CARBON_2
                for w in [r] + list(r.winfo_children()): w.config(bg=col)
            def _click(e, cn=char_name): self._select(cn)
            for w in [row, name_lbl, diff_lbl]:
                w.bind("<Enter>",    _enter)
                w.bind("<Leave>",    _leave)
                w.bind("<Button-1>", _click)
            self._char_buttons[char_name] = row

        # ── Right: detail panel ───────────────────────────────────
        right = tk.Frame(p, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=0)
        self._right = right
        self._build_detail(right)

        if characters:
            self._select(characters[0])

    def _select(self, char_name):
        old = self._selected_char.get()
        if old in self._char_buttons:
            for w in [self._char_buttons[old]] + list(self._char_buttons[old].winfo_children()):
                w.config(bg=CARBON_2)
        self._selected_char.set(char_name)
        if char_name in self._char_buttons:
            for w in [self._char_buttons[char_name]] + list(self._char_buttons[char_name].winfo_children()):
                w.config(bg=CARBON_3)
        self._load_char_info(char_name)
        results = self.get_results()
        if results:
            self._score_char(char_name, results)

    def _build_detail(self, p):
        BG = CARBON_1

        # Header
        hdr = tk.Frame(p, bg=CARBON_2, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=YELLOW, width=3).pack(side="left", fill="y")
        hdr_inner = tk.Frame(hdr, bg=CARBON_2)
        hdr_inner.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        self._char_title_var = tk.StringVar(value="Select a character")
        self._char_desc_var  = tk.StringVar()
        self._char_diff_var  = tk.StringVar()
        tk.Label(hdr_inner, textvariable=self._char_title_var,
                 font=("Segoe UI", 12, "bold"), fg=YELLOW,
                 bg=CARBON_2, anchor="w").pack(fill="x")
        diff_row = tk.Frame(hdr_inner, bg=CARBON_2)
        diff_row.pack(fill="x")
        tk.Label(diff_row, textvariable=self._char_desc_var, font=FONT_SMALL,
                 fg=TEXT_MUTED, bg=CARBON_2, anchor="w").pack(side="left")
        self._diff_lbl = tk.Label(diff_row, textvariable=self._char_diff_var,
                                   font=("Consolas", 8, "bold"), bg=CARBON_2, padx=6)
        self._diff_lbl.pack(side="right")

        # Score + dims + reference
        mid = tk.Frame(p, bg=BG)
        mid.pack(fill="x", padx=16, pady=10)

        # Score box
        score_box = tk.Frame(mid, bg=CARBON_2,
                              highlightthickness=1, highlightbackground=EDGE_BRIGHT)
        score_box.pack(side="left", padx=(0, 12), ipadx=14, ipady=8)
        tk.Label(score_box, text="YOUR SCORE", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_2).pack(pady=(6, 0))
        self._char_score_var = tk.StringVar(value="\u2014")
        self._char_grade_var = tk.StringVar(value="")
        tk.Label(score_box, textvariable=self._char_score_var,
                 font=("Consolas", 30, "bold"), fg=YELLOW, bg=CARBON_2).pack()
        tk.Label(score_box, textvariable=self._char_grade_var,
                 font=("Consolas", 13, "bold"), fg=YELLOW_DIM, bg=CARBON_2).pack()
        analyze_btn = tk.Button(score_box, text="ANALYZE NOW", font=FONT_BTN,
                                bg=CARBON_3, fg=TEXT_MUTED, relief="flat",
                                bd=0, padx=10, pady=4, cursor="hand2",
                                activebackground=CARBON_4, activeforeground=TEXT,
                                command=self._analyze_now)
        analyze_btn.pack(pady=(8, 6), fill="x", padx=6)

        # Dimension bars
        dims_f = tk.Frame(mid, bg=BG)
        dims_f.pack(side="left", fill="both", expand=True)
        self._char_dim_vars = {}
        for key, lbl_text in [("pause_ratio",   "PAUSE RATIO"),
                               ("speech_rate",   "SPEECH RATE"),
                               ("consistency",   "CONSISTENCY"),
                               ("dynamic_range", "DYNAMIC RANGE"),
                               ("clarity",       "CLARITY"),
                               ("stutters",      "DELIVERY")]:
            r = tk.Frame(dims_f, bg=BG)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=lbl_text, font=FONT_MONO, fg=TEXT_MUTED,
                     bg=BG, width=15, anchor="w").pack(side="left")
            track = tk.Frame(r, bg=EDGE_BRIGHT, height=6)
            track.pack(side="left", fill="x", expand=True, padx=(0, 8))
            track.pack_propagate(False)
            fill = tk.Frame(track, bg=YELLOW, height=6)
            fill.place(x=0, y=0, relheight=1, relwidth=0)
            slbl = tk.Label(r, text="\u2014", font=FONT_MONO,
                             fg=TEXT_MUTED, bg=BG, width=4)
            slbl.pack(side="left")
            self._char_dim_vars[key] = (fill, slbl)

        # Reference box
        ref_box = tk.Frame(mid, bg=CARBON_2, width=210,
                            highlightthickness=1, highlightbackground=EDGE_BRIGHT)
        ref_box.pack(side="left", fill="y", padx=(12, 0), ipadx=10, ipady=8)
        ref_box.pack_propagate(False)
        tk.Label(ref_box, text="PRO REFERENCE", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_2).pack(anchor="w", pady=(4, 2))
        tk.Frame(ref_box, bg=EDGE, height=1).pack(fill="x", pady=(0, 4))
        tk.Label(ref_box, text="Sounds like:", font=FONT_SMALL,
                 fg=TEXT_MUTED, bg=CARBON_2).pack(anchor="w")
        self._pros_var = tk.StringVar()
        tk.Label(ref_box, textvariable=self._pros_var,
                 font=("Segoe UI", 9, "italic"), fg=YELLOW,
                 bg=CARBON_2, wraplength=185, justify="left").pack(anchor="w")
        tk.Label(ref_box, text="Target sound:", font=FONT_SMALL,
                 fg=TEXT_MUTED, bg=CARBON_2).pack(anchor="w", pady=(4, 2))
        self._ref_text = tk.Text(ref_box, height=4, font=FONT_SMALL,
                                  bg=CARBON_2, fg=TEXT, relief="flat",
                                  wrap="word", bd=0)
        self._ref_text.pack(fill="both", expand=True)
        self._ref_text.config(state="disabled")

        tk.Frame(p, bg=EDGE, height=1).pack(fill="x", padx=16, pady=(0, 4))

        # Feedback + Tips
        bottom = tk.Frame(p, bg=BG)
        bottom.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        left_b = tk.Frame(bottom, bg=BG)
        left_b.pack(side="left", fill="both", expand=True, padx=(0, 8))
        _sec_label(left_b, "Feedback", bg=BG)
        self._char_fb_text = _text_box(left_b, height=5, fg_color=TEXT, bg=CARBON_2)
        self._char_fb_text.pack(fill="both", expand=True)

        right_b = tk.Frame(bottom, bg=BG)
        right_b.pack(side="left", fill="both", expand=True)
        _sec_label(right_b, "Pro Tips", bg=BG)
        self._tips_text = _text_box(right_b, height=5, fg_color=YELLOW, bg=CARBON_2)
        self._tips_text.pack(fill="both", expand=True)

        _sec_label(p, "Common Mistakes", bg=BG).pack(fill="x", padx=16)
        self._mistakes_text = _text_box(p, height=3, fg_color=RED_FLAG, bg=CARBON_2)
        self._mistakes_text.pack(fill="x", padx=16, pady=(0, 4))

        tk.Frame(p, bg=YELLOW, height=1).pack(fill="x", padx=16, pady=(4, 0))

        ai_hdr = tk.Frame(p, bg=BG)
        ai_hdr.pack(fill="x", padx=16, pady=(6, 2))
        tk.Label(ai_hdr, text="AI COACH", font=FONT_MONO, fg=YELLOW, bg=BG).pack(side="left")
        self._ai_status_var = tk.StringVar(value="")
        tk.Label(ai_hdr, textvariable=self._ai_status_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BG).pack(side="right")

        self._ai_text = _text_box(p, height=4, fg_color=TEXT, bg=CARBON_2)
        self._ai_text.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        ai_btns = tk.Frame(p, bg=BG)
        ai_btns.pack(fill="x", padx=16, pady=(0, 10))
        from ui.components import PrimaryButton
        self._ai_btn_ref = PrimaryButton(ai_btns, "GET AI COACHING", self._get_ai_coaching)
        self._ai_btn_ref.pack(side="left", padx=(0, 6))
        _ghost_btn(ai_btns, "SPEAK", self._speak_coaching).pack(side="left", padx=(0, 4))
        _ghost_btn(ai_btns, "STOP",  self._stop_speaking).pack(side="left")

    def _load_char_info(self, char_name):
        char = CHARACTER_DB.get(char_name, {})
        if not char: return
        self._char_title_var.set(char_name)
        self._char_desc_var.set(char.get("description", ""))
        diff = char.get("difficulty", "Beginner")
        self._char_diff_var.set(diff)
        self._diff_lbl.config(fg=DIFF_COLORS.get(diff, TEXT_MUTED))
        self._pros_var.set("\n".join(char.get("example_pros", [])))

        self._ref_text.config(state="normal")
        self._ref_text.delete("1.0", "end")
        self._ref_text.insert("end", char.get("reference_desc", ""))
        self._ref_text.config(state="disabled")

        self._tips_text.config(state="normal")
        self._tips_text.delete("1.0", "end")
        for i, tip in enumerate(char.get("pro_tips", []), 1):
            self._tips_text.insert("end", f"  {i}. {tip}\n\n")
        self._tips_text.config(state="disabled")

        self._mistakes_text.config(state="normal")
        self._mistakes_text.delete("1.0", "end")
        for m in char.get("common_mistakes", []):
            self._mistakes_text.insert("end", f"  \u2022 {m}\n")
        self._mistakes_text.config(state="disabled")

        self._char_score_var.set("\u2014")
        self._char_grade_var.set("")
        for fill, lbl in self._char_dim_vars.values():
            fill.place(relwidth=0)
            lbl.config(text="\u2014", fg=TEXT_MUTED)
        self._char_fb_text.config(state="normal")
        self._char_fb_text.delete("1.0", "end")
        self._char_fb_text.insert("end", "  Run analysis to see your score.")
        self._char_fb_text.config(state="disabled")

    def _score_char(self, char_name, results):
        report = score_character(results, char_name)
        if "error" in report: return
        self._char_score_var.set(str(report["overall"]))
        self._char_grade_var.set(report["grade"])
        for key, (fill, lbl) in self._char_dim_vars.items():
            s = report["scores"].get(key, 50)
            fill.place(relwidth=s / 100)
            fill.config(bg=score_color(s))
            lbl.config(text=str(s), fg=score_color(s))
        self._char_fb_text.config(state="normal")
        self._char_fb_text.delete("1.0", "end")
        for dim, msg in (report["feedback"] or []):
            self._char_fb_text.insert("end", f"  {dim}\n  {msg}\n\n")
        if not report["feedback"]:
            self._char_fb_text.insert("end", f"  Solid {char_name} delivery!")
        self._char_fb_text.config(state="disabled")
        self._last_report = report
        self._last_report["_char_name"] = char_name

    def _analyze_now(self):
        results = self.get_results()
        if results:
            self._score_char(self._selected_char.get(), results)

    def _refresh(self):
        results = self.get_results()
        if results:
            self._score_char(self._selected_char.get(), results)

    def _get_ai_coaching(self):
        if not self.ai_coach or not self._last_report: return
        self._ai_btn_ref.config(state="disabled")
        self._ai_text.config(state="normal")
        self._ai_text.delete("1.0", "end")
        self._ai_text.config(state="disabled")
        self._ai_status_var.set("THINKING...")
        report    = self._last_report
        char_name = report.get("_char_name", self._selected_char.get())
        def on_token(t): self.parent.after(0, lambda tok=t: self._append_token(tok))
        def on_done(_):  self.parent.after(0, self._ai_done)
        self.ai_coach.get_coaching(
            report.get("profile", self.category),
            {"overall": report["overall"], "grade": report["grade"], "scores": report["scores"]},
            report.get("feedback", []),
            character_name=char_name, on_token=on_token, on_done=on_done)

    def _append_token(self, t):
        self._ai_text.config(state="normal")
        self._ai_text.insert("end", t)
        self._ai_text.see("end")
        self._ai_text.config(state="disabled")

    def _ai_done(self):
        self._ai_btn_ref.config(state="normal")
        self._ai_status_var.set("READY")

    def _speak_coaching(self):
        if not self.voice: return
        text = self._ai_text.get("1.0", "end").strip()
        if not text: return
        self._ai_status_var.set("SPEAKING...")
        self.voice.set_status_callback(
            lambda sp: self.parent.after(0, lambda: self._ai_status_var.set(
                "SPEAKING..." if sp else "READY")))
        self.voice.speak(text)

    def _stop_speaking(self):
        if self.voice: self.voice.stop()
        self._ai_status_var.set("READY")


# ─────────────────────────────────────────────────────────────────────────────
# HistoryPanel
# ─────────────────────────────────────────────────────────────────────────────

class HistoryPanel:
    def __init__(self, parent):
        self.parent   = parent
        self._history = []
        self._build()
        self.refresh()

    def refresh(self):
        self._history = load_history()
        self._render()

    # ── Build ─────────────────────────────────────────────────────

    def _build(self):
        p  = self.parent
        BG = CARBON_1

        # Summary strip
        strip = tk.Frame(p, bg=CARBON_2, height=44)
        strip.pack(fill="x")
        strip.pack_propagate(False)
        tk.Frame(strip, bg=YELLOW, width=3).pack(side="left", fill="y")

        self._best_var   = tk.StringVar(value="BEST  —")
        self._latest_var = tk.StringVar(value="LATEST  —")
        self._trend_var  = tk.StringVar(value="TREND  —")
        self._trend_lbl  = None

        for var in (self._best_var, self._latest_var):
            tk.Label(strip, textvariable=var, font=FONT_MONO,
                     fg=TEXT, bg=CARBON_2, padx=20).pack(side="left")
            tk.Frame(strip, bg=EDGE, width=1).pack(side="left", fill="y", pady=6)

        self._trend_lbl = tk.Label(strip, textvariable=self._trend_var,
                                    font=("Consolas", 13, "bold"),
                                    fg=YELLOW, bg=CARBON_2, padx=20)
        self._trend_lbl.pack(side="left")

        tk.Frame(p, bg=EDGE, height=1).pack(fill="x")

        # Body: list left + chart right
        body = tk.Frame(p, bg=BG)
        body.pack(fill="both", expand=True)

        # Left — session list
        left = tk.Frame(body, bg=CARBON_2, width=290)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Frame(left, bg=EDGE, width=1).pack(side="right", fill="y")

        tk.Label(left, text="SESSIONS", font=FONT_MONO,
                 fg=YELLOW, bg=CARBON_2, padx=12, pady=8,
                 anchor="w").pack(fill="x")
        tk.Frame(left, bg=YELLOW, height=1).pack(fill="x")

        from ui.components import DarkScrollbar
        list_wrap = tk.Frame(left, bg=CARBON_2)
        list_wrap.pack(fill="both", expand=True)

        self._list_canvas = tk.Canvas(list_wrap, bg=CARBON_2, highlightthickness=0)
        sb = DarkScrollbar(list_wrap, command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._list_canvas.pack(side="left", fill="both", expand=True)

        self._list_inner = tk.Frame(self._list_canvas, bg=CARBON_2)
        self._list_win = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind("<Configure>", self._on_list_resize)
        self._list_canvas.bind("<Configure>",
                               lambda e: self._list_canvas.itemconfig(
                                   self._list_win, width=e.width))

        # Right — chart area
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=16, pady=12)

        tk.Label(right, text="OVERALL SCORE TREND", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=BG, anchor="w").pack(fill="x", pady=(0, 6))

        self._chart = tk.Canvas(right, bg=CARBON_2, highlightthickness=1,
                                 highlightbackground=EDGE_BRIGHT)
        self._chart.pack(fill="both", expand=True)
        self._chart.bind("<Configure>", lambda e: self._draw_chart())

        tk.Label(right, text="DIMENSIONS — LAST 10 SESSIONS",
                 font=FONT_MONO, fg=TEXT_GHOST, bg=BG,
                 anchor="w").pack(fill="x", pady=(10, 4))

        self._spark_frame = tk.Frame(right, bg=BG)
        self._spark_frame.pack(fill="x")

    def _on_list_resize(self, _=None):
        self._list_canvas.configure(
            scrollregion=self._list_canvas.bbox("all"))

    # ── Render ────────────────────────────────────────────────────

    def _render(self):
        h = self._history

        if not h:
            self._best_var.set("BEST  —")
            self._latest_var.set("LATEST  —")
            self._trend_var.set("TREND  —")
            if self._trend_lbl:
                self._trend_lbl.config(fg=TEXT_GHOST)
        else:
            best   = max(s["overall"] for s in h)
            latest = h[-1]
            if len(h) >= 2:
                delta = h[-1]["overall"] - h[-2]["overall"]
                arrow, col = ("↑", GREEN_OK) if delta > 0 else \
                             ("↓", RED_FLAG) if delta < 0 else ("→", YELLOW)
            else:
                arrow, col = ("→", YELLOW)
            self._best_var.set(f"BEST  {best}")
            self._latest_var.set(f"LATEST  {latest['overall']}  {latest['grade']}")
            self._trend_var.set(f"{arrow}")
            if self._trend_lbl:
                self._trend_lbl.config(fg=col)

        for w in self._list_inner.winfo_children():
            w.destroy()

        for rec in reversed(h):
            self._add_row(rec)

        self._on_list_resize()
        self._draw_chart()
        self._draw_sparklines()

    def _add_row(self, rec):
        sc  = rec.get("overall", 0)
        col = score_color(sc)

        row = tk.Frame(self._list_inner, bg=CARBON_2, cursor="hand2")
        row.pack(fill="x")

        accent = tk.Frame(row, bg=col, width=3)
        accent.pack(side="left", fill="y")

        inner = tk.Frame(row, bg=CARBON_2)
        inner.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=5)

        tk.Label(inner, text=rec.get("date", ""), font=("Consolas", 8),
                 fg=TEXT_GHOST, bg=CARBON_2, anchor="w").pack(fill="x")
        tk.Label(inner, text=rec.get("filename", ""), font=FONT_BODY,
                 fg=TEXT, bg=CARBON_2, anchor="w").pack(fill="x")
        tk.Label(inner, text=rec.get("profile", ""), font=("Consolas", 8),
                 fg=TEXT_MUTED, bg=CARBON_2, anchor="w").pack(fill="x")

        score_lbl = tk.Label(row, text=f"{sc}\n{rec.get('grade', '')}",
                              font=("Consolas", 10, "bold"), fg=col,
                              bg=CARBON_2, padx=10, justify="center")
        score_lbl.pack(side="right", pady=5)

        tk.Frame(self._list_inner, bg=EDGE, height=1).pack(fill="x")

        for w in [row, inner, accent, score_lbl]:
            w.bind("<Enter>", lambda e, r=row: self._hover(r, True))
            w.bind("<Leave>", lambda e, r=row: self._hover(r, False))

    def _hover(self, row, entering):
        bg = CARBON_3 if entering else CARBON_2
        for w in [row] + list(row.winfo_children()):
            try:
                w.config(bg=bg)
                for c in w.winfo_children():
                    c.config(bg=bg)
            except Exception:
                pass

    # ── Chart ─────────────────────────────────────────────────────

    def _draw_chart(self):
        c = self._chart
        c.delete("all")
        c.update_idletasks()
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 10 or H < 10:
            return

        PAD_L, PAD_R = 36, 16
        PAD_T, PAD_B = 14, 26

        h = self._history[-50:]

        def y_of(score):
            return PAD_T + (100 - score) / 100 * (H - PAD_T - PAD_B)

        c.create_rectangle(PAD_L, PAD_T, W - PAD_R, H - PAD_B,
                            fill=CARBON_2, outline="")
        c.create_rectangle(PAD_L, y_of(80), W - PAD_R, y_of(0),
                            fill="#0a1a0a", outline="")
        c.create_rectangle(PAD_L, y_of(60), W - PAD_R, y_of(0),
                            fill="#111500", outline="")

        for score in (0, 60, 80, 100):
            y = y_of(score)
            c.create_line(PAD_L, y, W - PAD_R, y,
                          fill=EDGE_BRIGHT, dash=(4, 4))
            c.create_text(PAD_L - 4, y, text=str(score),
                          font=("Consolas", 7), fill=TEXT_GHOST, anchor="e")

        if not h:
            c.create_text(W // 2, H // 2,
                          text="Analyze a recording to begin tracking.",
                          font=FONT_MONO, fill=TEXT_GHOST, justify="center")
            return

        n = len(h)
        def x_of(i):
            if n == 1:
                return (PAD_L + W - PAD_R) / 2
            return PAD_L + i / (n - 1) * (W - PAD_L - PAD_R)

        pts = [(x_of(i), y_of(rec["overall"])) for i, rec in enumerate(h)]

        for i in range(len(pts) - 1):
            col = score_color(h[i + 1]["overall"])
            c.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                          fill=col, width=2)

        for i, (x, y) in enumerate(pts):
            col = score_color(h[i]["overall"])
            c.create_oval(x - 3, y - 3, x + 3, y + 3,
                          fill=col, outline=BLACK)

        c.create_text(PAD_L, H - PAD_B + 10,
                      text=h[0]["date"][:10],
                      font=("Consolas", 7), fill=TEXT_GHOST, anchor="w")
        if n > 1:
            c.create_text(W - PAD_R, H - PAD_B + 10,
                          text=h[-1]["date"][:10],
                          font=("Consolas", 7), fill=TEXT_GHOST, anchor="e")

    # ── Sparklines ────────────────────────────────────────────────

    def _draw_sparklines(self):
        for w in self._spark_frame.winfo_children():
            w.destroy()

        h = self._history[-10:]
        if not h:
            return

        dims = [("pause_ratio", "Pacing"), ("stutters", "Delivery"),
                ("pause_length", "Pause"), ("consistency", "Consist."),
                ("clarity", "Clarity"), ("pitch", "Pitch")]

        for key, lbl in dims:
            scores = [rec.get("scores", {}).get(key, 0) for rec in h]
            if not any(scores):
                continue

            col_frame = tk.Frame(self._spark_frame, bg=CARBON_1)
            col_frame.pack(side="left", fill="x", expand=True, padx=3)

            cv = tk.Canvas(col_frame, bg=CARBON_2, height=32,
                           highlightthickness=0)
            cv.pack(fill="x")

            def draw(cv=cv, scores=scores):
                cv.update_idletasks()
                W2 = cv.winfo_width()
                H2 = cv.winfo_height()
                if W2 < 4 or H2 < 4:
                    return
                cv.delete("all")
                n = len(scores)
                if n == 1:
                    x = W2 / 2
                    y = H2 / 2
                    cv.create_oval(x - 2, y - 2, x + 2, y + 2,
                                   fill=score_color(scores[0]), outline="")
                else:
                    pts2 = []
                    for i, s in enumerate(scores):
                        x = i / (n - 1) * W2
                        y = H2 - max(s, 1) / 100 * H2
                        pts2.append((x, y))
                    col = score_color(scores[-1])
                    for i in range(len(pts2) - 1):
                        cv.create_line(pts2[i][0], pts2[i][1],
                                       pts2[i + 1][0], pts2[i + 1][1],
                                       fill=col, width=1)

            cv.bind("<Configure>", lambda e, d=draw: d())
            cv.after(50, draw)

            latest = scores[-1] if scores else 0
            tk.Label(col_frame, text=f"{lbl}  {latest}",
                     font=("Consolas", 7), fg=score_color(latest),
                     bg=CARBON_1, anchor="w").pack(fill="x")
