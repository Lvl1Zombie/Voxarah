"""
Voxarah — UI Components
Reusable widgets built in the Lamborghini design language.
All components share the same dark/yellow palette and sharp geometry.
"""

import tkinter as tk
from tkinter import ttk
from ui.design import *


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bind_hover(widget, normal_bg, hover_bg, *, fg=None, hover_fg=None):
    widget.bind("<Enter>",  lambda e: widget.config(bg=hover_bg,  **({"fg": hover_fg} if hover_fg else {})))
    widget.bind("<Leave>",  lambda e: widget.config(bg=normal_bg, **({"fg": fg}       if fg       else {})))


# ── Section Label ─────────────────────────────────────────────────────────────

class SectionLabel(tk.Frame):
    """Uppercase mono label with a hairline extending right."""
    def __init__(self, parent, text, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)
        tk.Label(self, text=text.upper(), font=FONT_MONO, fg=TEXT_GHOST,
                 bg=bg).pack(side="left", padx=(0, 8))
        tk.Frame(self, bg=EDGE, height=1).pack(side="left", fill="x", expand=True)


# ── Divider ───────────────────────────────────────────────────────────────────

def HDivider(parent, bg=SURFACE):
    return tk.Frame(parent, bg=EDGE, height=1)


# ── Primary Button ────────────────────────────────────────────────────────────

class PrimaryButton(tk.Button):
    """Yellow filled button — main CTA."""
    def __init__(self, parent, text, command=None, **kw):
        super().__init__(
            parent, text=text, command=command,
            bg=YELLOW, fg=BLACK,
            font=FONT_BTN_LG, relief="flat", bd=0,
            activebackground=YELLOW_DIM, activeforeground=BLACK,
            padx=14, pady=8, cursor="hand2", **kw
        )
        self.bind("<Enter>", lambda e: self.config(bg=YELLOW_DIM))
        self.bind("<Leave>", lambda e: self.config(bg=YELLOW))


# ── Secondary Button ──────────────────────────────────────────────────────────

class SecondaryButton(tk.Button):
    """Yellow-outlined ghost button."""
    def __init__(self, parent, text, command=None, **kw):
        super().__init__(
            parent, text=text, command=command,
            bg=SURFACE, fg=YELLOW,
            font=FONT_BTN, relief="flat", bd=1,
            highlightbackground=EDGE_BRIGHT, highlightthickness=1,
            activebackground=YELLOW_GLOW, activeforeground=YELLOW,
            padx=12, pady=6, cursor="hand2", **kw
        )
        self.bind("<Enter>", lambda e: self.config(bg=YELLOW_GLOW))
        self.bind("<Leave>", lambda e: self.config(bg=SURFACE))


# ── Ghost Button ──────────────────────────────────────────────────────────────

class GhostButton(tk.Button):
    """Subtle muted button for secondary actions."""
    def __init__(self, parent, text, command=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(
            parent, text=text, command=command,
            bg=bg, fg=TEXT_MUTED,
            font=FONT_SMALL, relief="flat", bd=0,
            activebackground=SURFACE3, activeforeground=TEXT_DIM,
            padx=8, pady=4, cursor="hand2", **kw
        )
        self.bind("<Enter>", lambda e: self.config(bg=SURFACE3, fg=TEXT_DIM))
        self.bind("<Leave>", lambda e: self.config(bg=bg, fg=TEXT_MUTED))


# ── Lambo Slider ──────────────────────────────────────────────────────────────

class LamboSlider(tk.Frame):
    """
    Custom slider with yellow fill, readout badge, and section label.
    value_fmt: callable that formats the float value for display.
    """
    def __init__(self, parent, label, key, from_, to, resolution,
                 value, value_fmt=str, on_change=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)
        self._fmt       = value_fmt
        self._on_change = on_change
        self._key       = key

        # Header row
        header = tk.Frame(self, bg=bg)
        header.pack(fill="x", pady=(0, 4))

        tk.Label(header, text=label.upper(), font=FONT_MONO, fg=TEXT_MUTED,
                 bg=bg).pack(side="left")

        self._val_var = tk.StringVar(value=value_fmt(value))
        self._readout = tk.Label(header, textvariable=self._val_var,
                                  font=FONT_MONO, fg=YELLOW,
                                  bg=YELLOW_SUBTLE, padx=6, pady=1)
        self._readout.pack(side="right")

        # Slider
        self._var = tk.DoubleVar(value=value)
        self._slider = tk.Scale(
            self, variable=self._var,
            from_=from_, to=to, resolution=resolution,
            orient="horizontal", showvalue=False,
            bg=bg, fg=YELLOW,
            troughcolor=EDGE, activebackground=YELLOW,
            highlightthickness=0, bd=0, sliderlength=12,
            command=self._changed
        )
        self._slider.pack(fill="x")

    def _changed(self, val):
        v = float(val)
        self._val_var.set(self._fmt(v))
        if self._on_change:
            self._on_change(self._key, v)

    def get(self):
        return self._var.get()

    def set(self, v):
        self._var.set(v)
        self._val_var.set(self._fmt(v))


# ── Lambo Toggle ─────────────────────────────────────────────────────────────

class LamboToggle(tk.Frame):
    """On/off toggle with yellow indicator when active."""
    def __init__(self, parent, label, key, value=True, on_change=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)
        self._key       = key
        self._on_change = on_change
        self._var       = tk.BooleanVar(value=value)

        tk.Label(self, text=label.upper(), font=FONT_MONO, fg=TEXT_MUTED,
                 bg=bg).pack(side="left")

        # Custom toggle canvas
        self._canvas = tk.Canvas(self, width=32, height=16, bg=bg,
                                  highlightthickness=0, cursor="hand2")
        self._canvas.pack(side="right")
        self._canvas.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self):
        c = self._canvas
        c.delete("all")
        on = self._var.get()
        track_col = YELLOW if on else EDGE_BRIGHT
        knob_col  = BLACK  if on else TEXT_GHOST
        # Track
        c.create_rectangle(0, 3, 32, 13, fill=track_col, outline="", tags="track")
        # Knob
        x = 22 if on else 2
        c.create_rectangle(x, 1, x + 10, 15, fill=knob_col if on else CARBON_5,
                            outline=track_col, width=1, tags="knob")
        # Yellow accent line top of knob when on
        if on:
            c.create_rectangle(x, 1, x + 10, 3, fill=YELLOW, outline="")

    def _toggle(self, _=None):
        self._var.set(not self._var.get())
        self._draw()
        if self._on_change:
            self._on_change(self._key, self._var.get())

    def get(self):
        return self._var.get()

    def set(self, v):
        self._var.set(v)
        self._draw()


# ── Stat Card ─────────────────────────────────────────────────────────────────

class StatCard(tk.Frame):
    """Big centered number + label. accent=True gives a yellow bottom border."""
    def __init__(self, parent, label, value="—", accent=False, **kw):
        bg = kw.pop("bg", CARBON_3)
        super().__init__(parent, bg=bg, **kw)
        self._bg = bg

        # Content frame
        inner = tk.Frame(self, bg=bg)
        inner.pack(fill="both", expand=True, padx=10, pady=8)

        self._val_var = tk.StringVar(value=value)
        tk.Label(inner, textvariable=self._val_var,
                 font=("Consolas", 22, "bold"),
                 fg=YELLOW if accent else TEXT,
                 bg=bg, anchor="center",
                 justify="center").pack(fill="x")

        tk.Label(inner, text=label.upper(),
                 font=("Consolas", 7),
                 fg=TEXT_GHOST,
                 bg=bg, anchor="center",
                 justify="center").pack(fill="x")

        # Yellow accent line at bottom of first card
        if accent:
            tk.Frame(self, bg=YELLOW, height=2).pack(fill="x", side="bottom")

    def set(self, v):
        self._val_var.set(str(v))


# ── Badge Label ───────────────────────────────────────────────────────────────

BADGE_STYLES = {
    "pause":   (YELLOW,    YELLOW_SUBTLE),
    "stutter": (RED_FLAG,  "#1f0810"),
    "unclear": (PURPLE_FLAG, "#0e0b1f"),
}

def BadgeLabel(parent, badge_type, bg=CARBON_3):
    fg, bg_badge = BADGE_STYLES.get(badge_type.lower(), (TEXT_MUTED, EDGE))
    lbl = tk.Label(parent, text=badge_type.upper(),
                   font=FONT_BADGE, fg=fg, bg=bg_badge,
                   padx=6, pady=2, relief="flat")
    return lbl


# ── Panel Frame ───────────────────────────────────────────────────────────────

class PanelSection(tk.Frame):
    """A section inside the left panel with a section label and content."""
    def __init__(self, parent, title=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)

        if title:
            lbl_row = tk.Frame(self, bg=bg)
            lbl_row.pack(fill="x", padx=SECTION_PAD, pady=(10, 6))
            SectionLabel(lbl_row, title, bg=bg).pack(fill="x")

        self.content = tk.Frame(self, bg=bg)
        self.content.pack(fill="x", padx=SECTION_PAD, pady=(0, 10))

    def add(self, widget, **pack_kw):
        widget.pack(in_=self.content, fill="x", **pack_kw)
        return widget


# ── Waveform Canvas ───────────────────────────────────────────────────────────

class WaveformCanvas(tk.Canvas):
    """
    Renders a waveform from a float sample list.
    Highlights stutter (red) and unclear (purple) zones from a flag list.
    """
    def __init__(self, parent, height=WAVEFORM_H, **kw):
        bg = kw.pop("bg", CARBON_2)
        super().__init__(parent, bg=bg, height=height,
                         highlightthickness=0, bd=0, **kw)
        self._samples = []
        self._flags   = []
        self._height  = height
        self.bind("<Configure>", lambda e: self._redraw())

    def load(self, samples, flags=None):
        self._samples = samples or []
        self._flags   = flags   or []
        # Delay redraw so canvas has been laid out and has a real width
        self.after(50, self._redraw)

    def _redraw(self):
        self.delete("all")
        W = self.winfo_width()
        H = self._height
        if W < 4:
            self.after(100, self._redraw)
            return

        # Always draw the baseline
        mid = H // 2
        self.create_line(0, mid, W, mid, fill=EDGE_BRIGHT, width=1)

        # Label
        self.create_text(8, 6, text="WAVEFORM", font=FONT_MONO,
                         fill=TEXT_GHOST, anchor="nw")

        if not self._samples:
            for x in range(0, W, 3):
                self.create_line(x, mid - 2, x, mid + 2,
                                 fill=EDGE_BRIGHT, width=1)
            return

        dur = len(self._samples)

        # ── Colored region backgrounds (drawn BEFORE waveform bars) ──────────
        _tint = {"pause": TINT_PAUSE, "stutter": TINT_STUTTER, "unclear": TINT_UNCLEAR}
        for f in self._flags:
            start_px = int(f["start_sample"] / dur * W) if "start_sample" in f else 0
            end_px   = int(f["end_sample"]   / dur * W) if "end_sample"   in f else W
            tint = _tint.get(f["type"], TINT_PAUSE)
            self.create_rectangle(start_px, 0, end_px, H,
                                  fill=tint, outline="")

        # Build flag pixel color map (for waveform bar coloring)
        flag_px = {}
        for f in self._flags:
            start_px = int(f["start_sample"] / dur * W) if "start_sample" in f else 0
            end_px   = int(f["end_sample"]   / dur * W) if "end_sample"   in f else W
            color = RED_FLAG if f["type"] == "stutter" else \
                    PURPLE_FLAG if f["type"] == "unclear" else YELLOW
            for px in range(start_px, end_px):
                flag_px[px] = color

        step = max(1, len(self._samples) // W)
        amp  = (H - 20) / 2

        for x in range(W):
            i = x * step
            chunk = self._samples[i: i + step]
            if not chunk:
                continue
            peak  = max(abs(s) for s in chunk)
            bar_h = max(2, int(peak * amp))
            color = flag_px.get(x, CARBON_5 if x < W * 0.33 else EDGE_BRIGHT)
            self.create_line(x, mid - bar_h, x, mid + bar_h,
                             fill=color, width=1)

        # Playhead
        px = int(W * 0.33)
        self.create_line(px, 0, px, H, fill=YELLOW, width=1)


# ── Dark Scrollbar (Canvas-based — Windows-proof) ────────────────────────────

class DarkScrollbar(tk.Canvas):
    """
    Custom dark scrollbar drawn on a Canvas.
    Windows ignores color settings on native scrollbars, so we draw our own.
    """
    THUMB_MIN = 20
    WIDTH = 8

    def __init__(self, parent, command=None, **kw):
        bg = kw.pop("bg", CARBON_1)
        super().__init__(parent, bg=bg, width=self.WIDTH,
                         highlightthickness=0, bd=0, **kw)
        self._command = command
        self._lo = 0.0
        self._hi = 1.0
        self._dragging = False
        self._drag_y = 0

        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, lo, hi):
        self._lo = float(lo)
        self._hi = float(hi)
        self._draw()

    def _draw(self):
        self.delete("all")
        H = self.winfo_height()
        if H < 4 or self._hi - self._lo >= 1.0:
            return
        thumb_h = max(self.THUMB_MIN, int((self._hi - self._lo) * H))
        thumb_y = int(self._lo * H)
        self.create_rectangle(2, thumb_y, self.WIDTH - 2, thumb_y + thumb_h,
                               fill=EDGE_BRIGHT, outline="")

    def _on_click(self, e):
        H = self.winfo_height()
        if H < 4:
            return
        thumb_h = max(self.THUMB_MIN, int((self._hi - self._lo) * H))
        thumb_y = int(self._lo * H)
        if thumb_y <= e.y <= thumb_y + thumb_h:
            self._dragging = True
            self._drag_y = e.y - thumb_y
        else:
            frac = e.y / H
            if self._command:
                self._command("moveto", str(frac))

    def _on_drag(self, e):
        if not self._dragging:
            return
        H = self.winfo_height()
        if H < 4:
            return
        frac = (e.y - self._drag_y) / H
        frac = max(0.0, min(1.0, frac))
        if self._command:
            self._command("moveto", str(frac))

    def _on_release(self, e):
        self._dragging = False


# ── Flag List (pure tk — Windows-proof) ──────────────────────────────────────

class FlagList(tk.Frame):
    """
    Pure-tk scrollable flag list. No ttk — fully controllable on Windows.
    Columns: TYPE | TIME | DESCRIPTION | SEVERITY
    """
    ROW_H  = 28
    HDR_H  = 26
    SEV_W  = 80   # fixed width for severity column

    def __init__(self, parent, **kw):
        bg = kw.pop("bg", CARBON_1)
        super().__init__(parent, bg=bg, **kw)
        self._bg   = bg
        self._rows = []

        # Header
        hdr = tk.Frame(self, bg=CARBON_3, height=self.HDR_H)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=YELLOW, height=1).pack(side="bottom", fill="x")

        hdr_inner = tk.Frame(hdr, bg=CARBON_3)
        hdr_inner.pack(fill="both", expand=True)
        hdr_inner.columnconfigure(2, weight=1)

        tk.Label(hdr_inner, text="TYPE", font=FONT_MONO, fg=TEXT_GHOST,
                 bg=CARBON_3, anchor="w", padx=12, pady=4).grid(
                     row=0, column=0, sticky="w")
        tk.Label(hdr_inner, text="TIME", font=FONT_MONO, fg=TEXT_GHOST,
                 bg=CARBON_3, anchor="w", padx=12, pady=4).grid(
                     row=0, column=1, sticky="w")
        tk.Label(hdr_inner, text="DESCRIPTION", font=FONT_MONO, fg=TEXT_GHOST,
                 bg=CARBON_3, anchor="w", padx=12, pady=4).grid(
                     row=0, column=2, sticky="ew")
        tk.Label(hdr_inner, text="SEVERITY", font=FONT_MONO, fg=TEXT_GHOST,
                 bg=CARBON_3, anchor="w", padx=12, pady=4).grid(
                     row=0, column=3, sticky="e")

        # Scrollable body
        body_frame = tk.Frame(self, bg=bg)
        body_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(body_frame, bg=bg,
                                  highlightthickness=0, bd=0)
        self._scrollbar = DarkScrollbar(body_frame, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=bg)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, _=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._canvas_window, width=e.width)

    def _on_mousewheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def clear(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._rows = []

    def insert(self, flag_type, timecode, description, severity=1):
        idx    = len(self._rows)
        row_bg = CARBON_2 if idx % 2 == 0 else self._bg

        row = tk.Frame(self._inner, bg=row_bg, height=self.ROW_H)
        row.pack(fill="x")
        row.pack_propagate(False)

        # Hover effect
        def on_enter(e, r=row, rb=row_bg):
            r.config(bg=YELLOW_SUBTLE)
            for c in r.winfo_children():
                try: c.config(bg=YELLOW_SUBTLE)
                except Exception: pass
        def on_leave(e, r=row, rb=row_bg):
            r.config(bg=rb)
            for c in r.winfo_children():
                try: c.config(bg=rb)
                except Exception: pass
        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)

        # Type badge
        fg_type = {"pause": YELLOW, "stutter": RED_FLAG,
                   "unclear": PURPLE_FLAG}.get(flag_type.lower(), TEXT_MUTED)
        type_lbl = tk.Label(row, text=flag_type.upper(),
                             font=FONT_BADGE, fg=fg_type, bg=row_bg,
                             width=10, anchor="center", padx=4)
        type_lbl.pack(side="left")
        type_lbl.bind("<Enter>", on_enter)
        type_lbl.bind("<Leave>", on_leave)

        # Timecode
        time_lbl = tk.Label(row, text=timecode, font=FONT_MONO,
                             fg=TEXT_MUTED, bg=row_bg, width=10, anchor="center")
        time_lbl.pack(side="left")
        time_lbl.bind("<Enter>", on_enter)
        time_lbl.bind("<Leave>", on_leave)

        # Description
        desc_lbl = tk.Label(row, text=description, font=FONT_SMALL,
                             fg=TEXT_DIM, bg=row_bg, anchor="w", padx=8)
        desc_lbl.pack(side="left", fill="x", expand=True)
        desc_lbl.bind("<Enter>", on_enter)
        desc_lbl.bind("<Leave>", on_leave)

        # Severity mini bar chart (3 bars, 4px wide, 10px tall, 2px gap)
        sev_canvas = tk.Canvas(row, width=self.SEV_W, height=self.ROW_H,
                               bg=row_bg, highlightthickness=0)
        sev_canvas.pack(side="right", padx=(0, 12))
        sev_canvas.bind("<Enter>", on_enter)
        sev_canvas.bind("<Leave>", on_leave)

        bar_w, bar_h, gap = 4, 10, 3
        total_w = 3 * bar_w + 2 * gap
        start_x = (self.SEV_W - total_w) // 2
        y_top   = (self.ROW_H - bar_h) // 2
        for b in range(3):
            x = start_x + b * (bar_w + gap)
            filled = (b + 1) <= severity
            sev_canvas.create_rectangle(
                x, y_top, x + bar_w, y_top + bar_h,
                fill=fg_type if filled else "#1a1a1a", outline="")

        # Bottom hairline
        tk.Frame(self._inner, bg=EDGE, height=1).pack(fill="x")

        self._rows.append(row)

    def get_children(self):
        return self._rows

    def delete_all(self):
        self.clear()


def make_flag_tree(parent, bg=CARBON_1):
    """Return a FlagList — pure tk, no ttk heading overrides."""
    return FlagList(parent, bg=bg)


# ── Styled Scrollbar ──────────────────────────────────────────────────────────

def styled_scrollbar(parent, orient="vertical", command=None):
    """Return a dark scrollbar that matches the Voxarah design."""
    return DarkScrollbar(parent, command=command)


# ── Notebook (tabs) ───────────────────────────────────────────────────────────

def make_notebook(parent):
    """Return a ttk.Notebook styled to match the Voxarah design."""
    style = ttk.Style()
    style.configure("Voxarah.TNotebook",
        background=CARBON_1, borderwidth=0, tabmargins=0)
    style.configure("Voxarah.TNotebook.Tab",
        background=BLACK, foreground=TEXT_GHOST,
        padding=[18, 8],
        font=FONT_TAB, borderwidth=0)
    style.map("Voxarah.TNotebook.Tab",
        background=[("selected", CARBON_2)],
        foreground=[("selected", YELLOW)])
    nb = ttk.Notebook(parent, style="Voxarah.TNotebook")
    return nb


# ── ScrolledText (log area) ───────────────────────────────────────────────────

def make_log_text(parent, height=10):
    from tkinter.scrolledtext import ScrolledText
    t = ScrolledText(parent, height=height,
                     font=FONT_MONO_MED,
                     bg=CARBON_1, fg=YELLOW, insertbackground=YELLOW,
                     relief="flat", wrap="word", bd=0,
                     selectbackground=YELLOW_SUBTLE,
                     selectforeground=YELLOW)
    t.config(state="disabled")
    return t


def log_append(widget, msg):
    widget.config(state="normal")
    widget.insert("end", msg + "\n")
    widget.see("end")
    widget.config(state="disabled")


# ── Progress Bar ──────────────────────────────────────────────────────────────

class LamboProgress(tk.Frame):
    """Thin yellow progress bar with mono label."""
    def __init__(self, parent, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)

        self._label_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._label_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=bg).pack(anchor="w", pady=(0,3))

        track = tk.Frame(self, bg=EDGE, height=2)
        track.pack(fill="x")
        track.pack_propagate(False)

        self._fill = tk.Frame(track, bg=YELLOW, height=2)
        self._fill.place(x=0, y=0, relheight=1, relwidth=0)

    def set(self, fraction, label=""):
        self._fill.place(relwidth=max(0.0, min(1.0, fraction)))
        if label:
            self._label_var.set(label.upper())

    def reset(self):
        self._fill.place(relwidth=0)
        self._label_var.set("")
