"""
Voxarah — Character Coaching UI
Sub-tab system: Style Coaching + 8 Character Categories
Each character tab has: selector, score panel, reference panel, feedback, tips

Lambo design: matte black + yellow. No purple, no softness.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

from coaching.characters import (
    score_character, get_all_categories, get_category_characters,
    CATEGORIES, CATEGORY_EMOJIS, CHARACTER_DB
)
from coaching.profiles import score_recording, get_all_profiles, get_profile_info
from ui.design import *

# ── Local helpers ─────────────────────────────────────────────────────────────

DIFF_COLORS = {
    'Beginner':     GREEN_OK,
    'Intermediate': YELLOW,
    'Advanced':     RED_FLAG,
}


def score_color(score):
    if score >= 80: return GREEN_OK
    if score >= 60: return YELLOW
    return RED_FLAG


def _coaching_btn(parent, text, cmd, bg_color=None):
    bg = bg_color or YELLOW
    fg = BLACK if bg == YELLOW else TEXT
    b = tk.Button(parent, text=text, command=cmd, relief='flat', cursor='hand2',
                  bg=bg, fg=fg, font=FONT_BTN, padx=10, pady=5, bd=0,
                  activebackground=YELLOW_DIM, activeforeground=BLACK)
    b.bind('<Enter>', lambda e: b.config(bg=YELLOW_DIM))
    b.bind('<Leave>', lambda e: b.config(bg=bg))
    return b


def _coaching_text(parent, height=5, fg_color=None):
    """ScrolledText matching the Lambo design."""
    t = scrolledtext.ScrolledText(parent, height=height, font=FONT_SMALL,
                                   bg=CARBON_3, fg=fg_color or TEXT,
                                   relief='flat', wrap='word', bd=0,
                                   insertbackground=YELLOW,
                                   selectbackground=YELLOW_SUBTLE,
                                   selectforeground=YELLOW)
    t.config(state='disabled')
    return t


def _section_header(parent, text):
    lbl = tk.Label(parent, text=text.upper(), font=FONT_MONO,
                   fg=TEXT_GHOST, bg=SURFACE, pady=3)
    lbl.pack(anchor='w')
    return lbl


# ─────────────────────────────────────────────────────────────────────────────
# CoachingTabManager — builds the full coaching notebook
# ─────────────────────────────────────────────────────────────────────────────

class CoachingTabManager:
    """
    Drop this into the main app's coaching tab frame.
    Call .set_results(results) when a new analysis is complete.
    """

    def __init__(self, parent_frame, settings_manager, ai_coach=None, voice_engine=None):
        self.parent   = parent_frame
        self.settings = settings_manager
        self.results  = None
        self.ai_coach = ai_coach
        self.voice    = voice_engine

        self._style_notebook()

    def set_results(self, results):
        self.results = results
        self._style_panel.refresh(results)
        for panel in self._char_panels.values():
            panel.mark_dirty()

    # ── Outer Notebook: Style | Fantasy | Sci-Fi | … ─────────────

    def _style_notebook(self):
        # Configure notebook style to match Lambo design
        style = ttk.Style()
        style.configure("Coaching.TNotebook",
                         background=CARBON_1, borderwidth=0, tabmargins=0)
        style.configure("Coaching.TNotebook.Tab",
                         background=BLACK, foreground=TEXT_GHOST,
                         padding=[14, 6], font=FONT_TAB, borderwidth=0)
        style.map("Coaching.TNotebook.Tab",
                  background=[("selected", CARBON_2)],
                  foreground=[("selected", YELLOW)])

        self.nb = ttk.Notebook(self.parent, style="Coaching.TNotebook")
        self.nb.pack(fill='both', expand=True)

        self._style_tab = tk.Frame(self.nb, bg=SURFACE)
        self.nb.add(self._style_tab, text='  \U0001f399 Style  ')
        self._style_panel = StyleCoachingPanel(self._style_tab, self.settings,
                                                self.ai_coach, self.voice)

        self._char_panels = {}

        for category in get_all_categories():
            emoji = CATEGORY_EMOJIS.get(category, '')
            tab_frame = tk.Frame(self.nb, bg=SURFACE)
            self.nb.add(tab_frame, text=f'  {emoji} {category}  ')
            panel = CategoryPanel(tab_frame, category, self.settings, self._get_results,
                                  self.ai_coach, self.voice)
            self._char_panels[category] = panel

        self.nb.bind('<<NotebookTabChanged>>', self._on_tab_change)

    def _get_results(self):
        return self.results

    def _on_tab_change(self, event):
        tab_id = self.nb.select()
        tab_text = self.nb.tab(tab_id, 'text').strip()
        for cat, panel in self._char_panels.items():
            if cat in tab_text:
                panel.refresh_if_dirty()
                break


# ─────────────────────────────────────────────────────────────────────────────
# StyleCoachingPanel — the original style coaching, now inside a sub-tab
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

        top = tk.Frame(p, bg=SURFACE)
        top.pack(fill='x', padx=14, pady=(12, 6))
        tk.Label(top, text="VOICE STYLE", font=FONT_MONO, fg=TEXT_GHOST,
                 bg=SURFACE).pack(side='left')
        self._profile_var = tk.StringVar(value=self.settings.get('coaching_profile'))

        cb = ttk.Combobox(top, textvariable=self._profile_var,
                          values=get_all_profiles(), width=28, state='readonly',
                          font=FONT_BODY)
        cb.pack(side='left', padx=8)
        cb.bind('<<ComboboxSelected>>', lambda e: self.refresh(self.results))
        _coaching_btn(top, 'REFRESH', lambda: self.refresh(self.results),
                      bg_color=CARBON_4).pack(side='left', padx=4)

        self._desc_var = tk.StringVar()
        tk.Label(p, textvariable=self._desc_var, font=FONT_SMALL, fg=TEXT_MUTED,
                 bg=SURFACE, wraplength=820, justify='left').pack(
                     fill='x', padx=14, pady=(0, 6))

        # Score area
        score_row = tk.Frame(p, bg=SURFACE)
        score_row.pack(fill='x', padx=14, pady=(0, 8))

        # Big score box
        self._big_frame = tk.Frame(score_row, bg=CARBON_3, padx=18, pady=10)
        self._big_frame.pack(side='left', padx=(0, 10))
        tk.Label(self._big_frame, text="OVERALL", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_3).pack()
        self._score_var = tk.StringVar(value='\u2014')
        self._grade_var = tk.StringVar(value='')
        tk.Label(self._big_frame, textvariable=self._score_var,
                 font=("Consolas", 30, "bold"), fg=YELLOW,
                 bg=CARBON_3).pack()
        tk.Label(self._big_frame, textvariable=self._grade_var,
                 font=("Consolas", 14, "bold"), fg=YELLOW_DIM,
                 bg=CARBON_3).pack()

        # Dimension bars
        dims_f = tk.Frame(score_row, bg=SURFACE)
        dims_f.pack(side='left', fill='both', expand=True)
        self._dim_vars = {}
        for key, lbl in [('pause_ratio', 'Pacing'), ('stutters', 'Delivery'),
                          ('pause_length', 'Pause Length'),
                          ('consistency', 'Consistency'), ('clarity', 'Clarity')]:
            r = tk.Frame(dims_f, bg=SURFACE)
            r.pack(fill='x', pady=2)
            tk.Label(r, text=lbl.upper(), font=FONT_MONO, fg=TEXT_MUTED,
                     bg=SURFACE, width=16, anchor='w').pack(side='left')
            bg_bar = tk.Frame(r, bg=EDGE, height=10, width=280)
            bg_bar.pack(side='left', padx=4)
            bg_bar.pack_propagate(False)
            fill = tk.Frame(bg_bar, bg=YELLOW, height=10, width=0)
            fill.place(x=0, y=0, relheight=1)
            slbl = tk.Label(r, text='\u2014', font=FONT_MONO, fg=TEXT_MUTED,
                             bg=SURFACE, width=4)
            slbl.pack(side='left', padx=4)
            self._dim_vars[key] = (fill, slbl)

        # Feedback
        _section_header(p, "Feedback")
        self._fb_text = _coaching_text(p, height=5, fg_color=TEXT)
        self._fb_text.pack(fill='both', expand=True, padx=14, pady=(0, 4))

        _section_header(p, "Style Tips")
        self._tips_text = _coaching_text(p, height=4, fg_color=YELLOW)
        self._tips_text.pack(fill='both', expand=True, padx=14, pady=(0, 6))

        # ── AI COACH Section ──────────────────────────────────
        tk.Frame(p, bg=YELLOW, height=1).pack(fill='x', padx=14, pady=(4, 0))
        ai_header = tk.Frame(p, bg=SURFACE)
        ai_header.pack(fill='x', padx=14, pady=(4, 2))
        tk.Label(ai_header, text="AI COACH", font=FONT_MONO,
                 fg=YELLOW, bg=SURFACE).pack(side='left')
        self._ai_status_var = tk.StringVar(value="")
        tk.Label(ai_header, textvariable=self._ai_status_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=SURFACE).pack(side='right')

        self._ai_text = _coaching_text(p, height=5, fg_color=TEXT)
        self._ai_text.pack(fill='both', expand=True, padx=14, pady=(0, 4))

        ai_btns = tk.Frame(p, bg=SURFACE)
        ai_btns.pack(fill='x', padx=14, pady=(0, 10))
        self._ai_btn = _coaching_btn(ai_btns, 'GET AI COACHING', self._get_ai_coaching)
        self._ai_btn.pack(side='left', padx=(0, 4))
        self._speak_btn = _coaching_btn(ai_btns, 'SPEAK', self._speak_coaching,
                                         bg_color=CARBON_4)
        self._speak_btn.pack(side='left', padx=(0, 4))
        self._stop_btn = _coaching_btn(ai_btns, 'STOP', self._stop_speaking,
                                        bg_color=CARBON_4)
        self._stop_btn.pack(side='left')

        self._refresh_desc()

    def _refresh_desc(self):
        name = self._profile_var.get()
        info = get_profile_info(name)
        self._desc_var.set(f"{info.get('emoji', '')}  {info.get('description', '')}")

    def refresh(self, results):
        self.results = results
        self._refresh_desc()
        if not results:
            return
        name   = self._profile_var.get()
        report = score_recording(results, name)
        self.settings.set('coaching_profile', name)

        self._score_var.set(str(report['overall']))
        self._grade_var.set(report['grade'])

        for key, (bar, lbl) in self._dim_vars.items():
            s = report['scores'].get(key, 0)
            bar.config(bg=score_color(s), width=int(s * 2.6))
            lbl.config(text=str(s), fg=score_color(s))

        self._fb_text.config(state='normal')
        self._fb_text.delete('1.0', 'end')
        if report['feedback']:
            for dim, msg in report['feedback']:
                self._fb_text.insert('end', f"  {dim}\n  {msg}\n\n")
        else:
            self._fb_text.insert('end', "  No major issues for this style.")
        self._fb_text.config(state='disabled')

        self._tips_text.config(state='normal')
        self._tips_text.delete('1.0', 'end')
        for i, tip in enumerate(report['tips'], 1):
            self._tips_text.insert('end', f"  {i}. {tip}\n\n")
        self._tips_text.config(state='disabled')

        self._last_report = report

    # ── AI Coach methods ──────────────────────────────────────

    def _get_ai_coaching(self):
        if not self.ai_coach or not self._last_report:
            return
        self._ai_btn.config(state='disabled')
        self._ai_text.config(state='normal')
        self._ai_text.delete('1.0', 'end')
        self._ai_text.config(state='disabled')
        self._ai_status_var.set("THINKING...")

        name = self._profile_var.get()
        report = self._last_report

        def on_token(token):
            self.parent.after(0, lambda t=token: self._append_ai_token(t))

        def on_done(full_text):
            self.parent.after(0, lambda: self._ai_done())

        self.ai_coach.get_coaching(
            name,
            {'overall': report['overall'], 'grade': report['grade'],
             'scores': report['scores']},
            report.get('feedback', []),
            on_token=on_token, on_done=on_done,
        )

    def _append_ai_token(self, token):
        self._ai_text.config(state='normal')
        self._ai_text.insert('end', token)
        self._ai_text.see('end')
        self._ai_text.config(state='disabled')

    def _ai_done(self):
        self._ai_btn.config(state='normal')
        self._ai_status_var.set("READY")

    def _speak_coaching(self):
        if not self.voice:
            return
        text = self._ai_text.get('1.0', 'end').strip()
        if not text:
            return
        self._ai_status_var.set("SPEAKING...")
        self.voice.set_status_callback(
            lambda speaking: self.parent.after(0, lambda: self._ai_status_var.set(
                "SPEAKING..." if speaking else "READY")))
        self.voice.speak(text)

    def _stop_speaking(self):
        if self.voice:
            self.voice.stop()
        self._ai_status_var.set("READY")


# ─────────────────────────────────────────────────────────────────────────────
# CategoryPanel — one tab per character category (Fantasy, Sci-Fi, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class CategoryPanel:
    def __init__(self, parent, category, settings, get_results_fn,
                 ai_coach=None, voice_engine=None):
        self.parent       = parent
        self.category     = category
        self.settings     = settings
        self.get_results  = get_results_fn
        self.ai_coach     = ai_coach
        self.voice        = voice_engine
        self._dirty       = True
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
        characters = get_category_characters(self.category)

        # Left: character selector list
        left = tk.Frame(p, bg=CARBON_3, width=200)
        left.pack(side='left', fill='y', padx=(10, 0), pady=10)
        left.pack_propagate(False)

        emoji = CATEGORY_EMOJIS.get(self.category, '')
        tk.Label(left, text=f"{emoji} {self.category}",
                 font=FONT_TITLE, fg=YELLOW, bg=CARBON_3, pady=10).pack(
                     fill='x', padx=10)
        tk.Frame(left, bg=YELLOW, height=1).pack(fill='x', padx=10, pady=(0, 6))

        self._selected_char = tk.StringVar(value=characters[0] if characters else '')
        self._char_buttons  = {}

        for char_name in characters:
            char_info = CHARACTER_DB.get(char_name, {})
            diff      = char_info.get('difficulty', 'Beginner')
            diff_col  = DIFF_COLORS.get(diff, TEXT_MUTED)

            btn_frame = tk.Frame(left, bg=CARBON_3, cursor='hand2')
            btn_frame.pack(fill='x', padx=6, pady=1)

            name_lbl = tk.Label(btn_frame, text=char_name, font=FONT_BODY,
                                 fg=TEXT, bg=CARBON_3, anchor='w',
                                 padx=10, pady=5)
            name_lbl.pack(side='left', fill='x', expand=True)

            diff_lbl = tk.Label(btn_frame, text=diff,
                                 font=("Consolas", 7, "bold"),
                                 fg=diff_col, bg=CARBON_3, padx=6)
            diff_lbl.pack(side='right')

            for w in (btn_frame, name_lbl, diff_lbl):
                w.bind('<Button-1>',
                       lambda e, cn=char_name: self._select_character(cn))
                w.bind('<Enter>',
                       lambda e, f=btn_frame: [
                           c.config(bg=CARBON_4)
                           for c in [f] + list(f.winfo_children())])
                w.bind('<Leave>',
                       lambda e, f=btn_frame, cn=char_name: [
                           c.config(bg=EDGE_BRIGHT if self._selected_char.get() == cn
                                    else CARBON_3)
                           for c in [f] + list(f.winfo_children())])

            self._char_buttons[char_name] = btn_frame

        # Right: scoring + reference panel
        right = tk.Frame(p, bg=SURFACE)
        right.pack(side='left', fill='both', expand=True, padx=10, pady=10)

        self._right = right
        self._build_character_panel(right)

        if characters:
            self._select_character(characters[0])

    def _select_character(self, char_name: str):
        old = self._selected_char.get()
        if old in self._char_buttons:
            for c in [self._char_buttons[old]] + list(self._char_buttons[old].winfo_children()):
                c.config(bg=CARBON_3)

        self._selected_char.set(char_name)
        if char_name in self._char_buttons:
            for c in [self._char_buttons[char_name]] + list(self._char_buttons[char_name].winfo_children()):
                c.config(bg=EDGE_BRIGHT)

        self._load_character_info(char_name)

        results = self.get_results()
        if results:
            self._score_character(char_name, results)

    def _build_character_panel(self, parent):
        p = parent

        # ── Header ───────────────────────────────────────────────
        header = tk.Frame(p, bg=SURFACE)
        header.pack(fill='x', pady=(0, 8))

        left_h = tk.Frame(header, bg=SURFACE)
        left_h.pack(side='left', fill='both', expand=True)

        self._char_title_var = tk.StringVar(value='Select a character')
        self._char_desc_var  = tk.StringVar()
        self._char_diff_var  = tk.StringVar()

        tk.Label(left_h, textvariable=self._char_title_var,
                 font=("Segoe UI", 12, "bold"), fg=YELLOW,
                 bg=SURFACE, anchor='w').pack(fill='x')
        tk.Label(left_h, textvariable=self._char_desc_var, font=FONT_SMALL,
                 fg=TEXT_MUTED, bg=SURFACE, anchor='w',
                 wraplength=420).pack(fill='x')

        diff_row = tk.Frame(left_h, bg=SURFACE)
        diff_row.pack(fill='x', pady=(2, 0))
        tk.Label(diff_row, text="DIFFICULTY", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=SURFACE).pack(side='left')
        self._diff_lbl = tk.Label(diff_row, textvariable=self._char_diff_var,
                                   font=("Consolas", 9, "bold"), bg=SURFACE)
        self._diff_lbl.pack(side='left', padx=4)

        # ── Score + Reference side by side ───────────────────────
        mid = tk.Frame(p, bg=SURFACE)
        mid.pack(fill='x', pady=(0, 8))

        # Score box
        score_box = tk.Frame(mid, bg=CARBON_3, padx=14, pady=10)
        score_box.pack(side='left', fill='y', padx=(0, 8))

        tk.Label(score_box, text="YOUR SCORE", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_3).pack()
        self._char_score_var = tk.StringVar(value='\u2014')
        self._char_grade_var = tk.StringVar(value='')
        tk.Label(score_box, textvariable=self._char_score_var,
                 font=("Consolas", 30, "bold"), fg=YELLOW,
                 bg=CARBON_3).pack()
        tk.Label(score_box, textvariable=self._char_grade_var,
                 font=("Consolas", 14, "bold"), fg=YELLOW_DIM,
                 bg=CARBON_3).pack()

        _coaching_btn(score_box, 'ANALYZE NOW', self._analyze_now,
                      bg_color=CARBON_4).pack(pady=(8, 0), fill='x')

        # Dimension bars
        dims_box = tk.Frame(mid, bg=SURFACE)
        dims_box.pack(side='left', fill='both', expand=True)
        self._char_dim_vars = {}
        dim_labels = [
            ('pause_ratio',   'PAUSE RATIO'),
            ('speech_rate',   'SPEECH RATE'),
            ('consistency',   'CONSISTENCY'),
            ('dynamic_range', 'DYNAMIC RANGE'),
            ('clarity',       'CLARITY'),
            ('stutters',      'DELIVERY'),
        ]
        for key, lbl_text in dim_labels:
            r = tk.Frame(dims_box, bg=SURFACE)
            r.pack(fill='x', pady=2)
            tk.Label(r, text=lbl_text, font=FONT_MONO, fg=TEXT_MUTED,
                     bg=SURFACE, width=15, anchor='w').pack(side='left')
            bg_bar = tk.Frame(r, bg=EDGE, height=10, width=250)
            bg_bar.pack(side='left', padx=4)
            bg_bar.pack_propagate(False)
            fill = tk.Frame(bg_bar, bg=YELLOW, height=10, width=0)
            fill.place(x=0, y=0, relheight=1)
            slbl = tk.Label(r, text='\u2014', font=FONT_MONO, fg=TEXT_MUTED,
                             bg=SURFACE, width=4)
            slbl.pack(side='left', padx=4)
            self._char_dim_vars[key] = (fill, slbl)

        # Reference box
        ref_box = tk.Frame(mid, bg=CARBON_3, padx=12, pady=10, width=220)
        ref_box.pack(side='left', fill='y', padx=(8, 0))
        ref_box.pack_propagate(False)
        tk.Label(ref_box, text="PRO REFERENCE", font=FONT_MONO,
                 fg=TEXT_GHOST, bg=CARBON_3).pack(anchor='w')
        tk.Label(ref_box, text="Sounds like:", font=FONT_SMALL,
                 fg=TEXT_MUTED, bg=CARBON_3).pack(anchor='w', pady=(4, 2))
        self._pros_var = tk.StringVar()
        tk.Label(ref_box, textvariable=self._pros_var,
                 font=("Segoe UI", 9, "italic"), fg=YELLOW,
                 bg=CARBON_3, wraplength=195,
                 justify='left').pack(anchor='w')
        tk.Label(ref_box, text="\nTarget sound:", font=FONT_SMALL,
                 fg=TEXT_MUTED, bg=CARBON_3).pack(anchor='w')
        self._ref_desc_text = tk.Text(ref_box, height=5, font=FONT_SMALL,
                                       bg=CARBON_3, fg=TEXT,
                                       relief='flat', wrap='word', bd=0)
        self._ref_desc_text.pack(fill='both', expand=True)
        self._ref_desc_text.config(state='disabled')

        # ── Bottom: Feedback + Tips + Common Mistakes ────────────
        bottom = tk.Frame(p, bg=SURFACE)
        bottom.pack(fill='both', expand=True)

        # Feedback
        left_b = tk.Frame(bottom, bg=SURFACE)
        left_b.pack(side='left', fill='both', expand=True, padx=(0, 6))

        _section_header(left_b, "Feedback")
        self._char_fb_text = _coaching_text(left_b, height=5, fg_color=TEXT)
        self._char_fb_text.pack(fill='both', expand=True)

        # Pro Tips
        right_b = tk.Frame(bottom, bg=SURFACE, width=280)
        right_b.pack(side='left', fill='both', expand=True)
        right_b.pack_propagate(False)

        _section_header(right_b, "Pro Tips")
        self._tips_text = _coaching_text(right_b, height=5, fg_color=YELLOW)
        self._tips_text.pack(fill='both', expand=True)

        # Common Mistakes
        _section_header(p, "Common Mistakes")
        self._mistakes_text = _coaching_text(p, height=3, fg_color=RED_FLAG)
        self._mistakes_text.pack(fill='x', pady=(0, 4))

        # ── AI COACH Section ──────────────────────────────────
        tk.Frame(p, bg=YELLOW, height=1).pack(fill='x', pady=(4, 0))
        ai_header = tk.Frame(p, bg=SURFACE)
        ai_header.pack(fill='x', pady=(4, 2))
        tk.Label(ai_header, text="AI COACH", font=FONT_MONO,
                 fg=YELLOW, bg=SURFACE).pack(side='left')
        self._ai_status_var = tk.StringVar(value="")
        tk.Label(ai_header, textvariable=self._ai_status_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=SURFACE).pack(side='right')

        self._ai_text = _coaching_text(p, height=4, fg_color=TEXT)
        self._ai_text.pack(fill='both', expand=True, pady=(0, 4))

        ai_btns = tk.Frame(p, bg=SURFACE)
        ai_btns.pack(fill='x', pady=(0, 8))
        self._ai_btn = _coaching_btn(ai_btns, 'GET AI COACHING', self._get_ai_coaching)
        self._ai_btn.pack(side='left', padx=(0, 4))
        self._speak_btn = _coaching_btn(ai_btns, 'SPEAK', self._speak_coaching,
                                         bg_color=CARBON_4)
        self._speak_btn.pack(side='left', padx=(0, 4))
        self._stop_btn = _coaching_btn(ai_btns, 'STOP', self._stop_speaking,
                                        bg_color=CARBON_4)
        self._stop_btn.pack(side='left')

    def _load_character_info(self, char_name: str):
        char = CHARACTER_DB.get(char_name, {})
        if not char:
            return

        self._char_title_var.set(char_name)
        self._char_desc_var.set(char.get('description', ''))
        diff = char.get('difficulty', 'Beginner')
        self._char_diff_var.set(diff)
        self._diff_lbl.config(fg=DIFF_COLORS.get(diff, TEXT_MUTED))
        self._pros_var.set('\n'.join(char.get('example_pros', [])))

        self._ref_desc_text.config(state='normal')
        self._ref_desc_text.delete('1.0', 'end')
        self._ref_desc_text.insert('end', char.get('reference_desc', ''))
        self._ref_desc_text.config(state='disabled')

        self._tips_text.config(state='normal')
        self._tips_text.delete('1.0', 'end')
        for i, tip in enumerate(char.get('pro_tips', []), 1):
            self._tips_text.insert('end', f"{i}. {tip}\n\n")
        self._tips_text.config(state='disabled')

        self._mistakes_text.config(state='normal')
        self._mistakes_text.delete('1.0', 'end')
        for m in char.get('common_mistakes', []):
            self._mistakes_text.insert('end', f"  {m}\n")
        self._mistakes_text.config(state='disabled')

        # Reset scores
        self._char_score_var.set('\u2014')
        self._char_grade_var.set('')
        for fill, lbl in self._char_dim_vars.values():
            fill.config(width=0)
            lbl.config(text='\u2014', fg=TEXT_MUTED)
        self._char_fb_text.config(state='normal')
        self._char_fb_text.delete('1.0', 'end')
        self._char_fb_text.insert('end',
            '  Run analysis to see your score for this character.')
        self._char_fb_text.config(state='disabled')

    def _score_character(self, char_name: str, results: dict):
        report = score_character(results, char_name)
        if 'error' in report:
            return

        self._char_score_var.set(str(report['overall']))
        self._char_grade_var.set(report['grade'])

        for key, (fill, lbl) in self._char_dim_vars.items():
            s = report['scores'].get(key, 50)
            fill.config(bg=score_color(s), width=int(s * 2.3))
            lbl.config(text=str(s), fg=score_color(s))

        self._char_fb_text.config(state='normal')
        self._char_fb_text.delete('1.0', 'end')
        if report['feedback']:
            for dim, msg in report['feedback']:
                self._char_fb_text.insert('end', f"  {dim}\n  {msg}\n\n")
        else:
            self._char_fb_text.insert('end',
                f"  Solid {char_name} delivery! Check the tips below to push further.")
        self._char_fb_text.config(state='disabled')

        self._last_report = report
        self._last_report['_char_name'] = char_name

    def _analyze_now(self):
        results = self.get_results()
        if not results:
            return
        char_name = self._selected_char.get()
        if char_name:
            self._score_character(char_name, results)

    def _refresh(self):
        results = self.get_results()
        if not results:
            return
        char_name = self._selected_char.get()
        if char_name:
            self._score_character(char_name, results)

    # ── AI Coach methods ──────────────────────────────────────

    def _get_ai_coaching(self):
        if not self.ai_coach or not self._last_report:
            return
        self._ai_btn.config(state='disabled')
        self._ai_text.config(state='normal')
        self._ai_text.delete('1.0', 'end')
        self._ai_text.config(state='disabled')
        self._ai_status_var.set("THINKING...")

        report = self._last_report
        char_name = report.get('_char_name', self._selected_char.get())
        profile = report.get('profile', self.category)

        def on_token(token):
            self.parent.after(0, lambda t=token: self._append_ai_token(t))

        def on_done(full_text):
            self.parent.after(0, lambda: self._ai_done())

        self.ai_coach.get_coaching(
            profile,
            {'overall': report['overall'], 'grade': report['grade'],
             'scores': report['scores']},
            report.get('feedback', []),
            character_name=char_name,
            on_token=on_token, on_done=on_done,
        )

    def _append_ai_token(self, token):
        self._ai_text.config(state='normal')
        self._ai_text.insert('end', token)
        self._ai_text.see('end')
        self._ai_text.config(state='disabled')

    def _ai_done(self):
        self._ai_btn.config(state='normal')
        self._ai_status_var.set("READY")

    def _speak_coaching(self):
        if not self.voice:
            return
        text = self._ai_text.get('1.0', 'end').strip()
        if not text:
            return
        self._ai_status_var.set("SPEAKING...")
        self.voice.set_status_callback(
            lambda speaking: self.parent.after(0, lambda: self._ai_status_var.set(
                "SPEAKING..." if speaking else "READY")))
        self.voice.speak(text)

    def _stop_speaking(self):
        if self.voice:
            self.voice.stop()
        self._ai_status_var.set("READY")
