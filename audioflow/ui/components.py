"""
Voxarah — UI Components  v3
Production-quality widgets built on Canvas for pixel-perfect rendering.
No system widget look. Smooth hover animations via color interpolation.
All public APIs are backward-compatible with v2.
"""

import tkinter as tk
from tkinter import ttk
from ui.design import *


# ── Color Utilities ───────────────────────────────────────────────────────────

def _h2rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb2h(r, g, b):
    c = lambda v: max(0, min(255, int(v)))
    return f"#{c(r):02x}{c(g):02x}{c(b):02x}"


def _lerp(c1, c2, t):
    r1, g1, b1 = _h2rgb(c1)
    r2, g2, b2 = _h2rgb(c2)
    return _rgb2h(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


# ── Rounded Rectangle (Canvas helper) ────────────────────────────────────────

def _rrect(canvas, x1, y1, x2, y2, r=4, **kw):
    """
    Draw a rounded rectangle using a smooth polygon.
    smooth=True on a 8-point polygon approximates quarter-circle corners.
    """
    pts = [
        x1 + r, y1,     x2 - r, y1,
        x2,     y1 + r, x2,     y2 - r,
        x2 - r, y2,     x1 + r, y2,
        x1,     y2 - r, x1,     y1 + r,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ── Tooltip ───────────────────────────────────────────────────────────────────

class Tooltip:
    """
    Lightweight hover tooltip. Appears 500 ms after mouse enters the widget.
    Usage:  Tooltip(some_widget, "Helpful hint text")
    """
    _DELAY = 500  # ms before appearing

    def __init__(self, widget, text):
        self._w    = widget
        self._text = text
        self._job  = None
        self._win  = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")

    def _enter(self, e):
        self._job = self._w.after(self._DELAY, self._show)

    def _leave(self, e):
        if self._job:
            self._w.after_cancel(self._job)
            self._job = None
        self._hide()

    def _show(self):
        if self._win:
            return
        x = self._w.winfo_rootx() + self._w.winfo_width() // 2
        y = self._w.winfo_rooty() + self._w.winfo_height() + 6
        self._win = tk.Toplevel(self._w, bg=CARBON_4)
        self._win.wm_overrideredirect(True)
        self._win.wm_geometry(f"+{x}+{y}")
        tk.Frame(self._win, bg=YELLOW, height=1).pack(fill="x")
        tk.Label(self._win, text=self._text, font=FONT_MONO,
                 fg=TEXT_DIM, bg=CARBON_4, padx=10, pady=5).pack()

    def _hide(self):
        if self._win:
            self._win.destroy()
            self._win = None


# ── Canvas Button Base ────────────────────────────────────────────────────────

class _Btn(tk.Canvas):
    """
    Canvas-based button with rounded corners and smooth hover animation.
    Subclass this to create concrete button styles.
    All tk.Button-specific kwargs are consumed and ignored.
    """
    _STEPS = 8    # animation frames
    _FRAME = 14   # ms per frame  (~70 fps)

    # Legacy tk.Button kwargs we silently absorb
    _LEGACY = frozenset({
        "activebackground", "activeforeground", "relief", "bd",
        "highlightbackground", "highlightthickness",
    })

    def __init__(self, parent, text, command=None,
                 fill_n=SURFACE,    fill_h=SURFACE3,
                 fg_n=TEXT,         fg_h=TEXT,
                 bdr_n=None,        bdr_h=None,
                 btn_h=36, radius=R_MD, font=FONT_BTN_LG, **kw):

        for k in self._LEGACY | {"padx", "pady"}:
            kw.pop(k, None)

        try:
            parent_bg = parent.cget("bg")
        except Exception:
            parent_bg = BLACK

        super().__init__(parent, height=btn_h, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2", **kw)

        self._text   = text
        self._cmd    = command
        self._fn     = fill_n
        self._fh     = fill_h
        self._fgn    = fg_n
        self._fgh    = fg_h
        self._bn     = bdr_n if bdr_n else fill_n
        self._bh     = bdr_h if bdr_h else fill_h
        self._r      = radius
        self._font   = font
        # Current animated values
        self._cf     = fill_n
        self._cfg    = fg_n
        self._cb     = self._bn
        self._dis    = False
        self._aj     = None   # pending after() job

        self.bind("<Configure>",       self._draw)
        self.bind("<Enter>",           self._enter)
        self.bind("<Leave>",           self._leave)
        self.bind("<Button-1>",        self._press)
        self.bind("<ButtonRelease-1>", self._release)

    # ── Drawing ──────────────────────────────────────────────────────────────

    def _draw(self, e=None):
        self.delete("all")
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 4 or H < 4:
            return
        _rrect(self, 1, 1, W - 1, H - 1, r=self._r,
               fill=self._cf, outline=self._cb, width=1)
        self.create_text(W // 2, H // 2, text=self._text,
                         font=self._font, fill=self._cfg, anchor="center")

    # ── Animation ────────────────────────────────────────────────────────────

    def _anim(self, f0, f1, fg0, fg1, b0, b1):
        if self._aj:
            self.after_cancel(self._aj)
            self._aj = None
        n = self._STEPS

        def step(i):
            if i > n:
                self._cf, self._cfg, self._cb = f1, fg1, b1
                self._draw()
                return
            t = i / n
            self._cf  = _lerp(f0, f1, t)
            self._cfg = _lerp(fg0, fg1, t)
            self._cb  = _lerp(b0, b1, t)
            self._draw()
            self._aj = self.after(self._FRAME, lambda: step(i + 1))

        step(1)

    # ── Events ───────────────────────────────────────────────────────────────

    def _enter(self, e):
        if self._dis:
            return
        self._anim(self._cf, self._fh, self._cfg, self._fgh, self._cb, self._bh)

    def _leave(self, e):
        if self._dis:
            return
        self._anim(self._cf, self._fn, self._cfg, self._fgn, self._cb, self._bn)

    def _press(self, e):
        pass

    def _release(self, e):
        if self._dis:
            return
        if self._cmd:
            W, H = self.winfo_width(), self.winfo_height()
            if 0 <= e.x <= W and 0 <= e.y <= H:
                self._cmd()

    # ── Public API ───────────────────────────────────────────────────────────

    def config(self, **kw):
        for k in self._LEGACY:
            kw.pop(k, None)
        state = kw.pop("state", None)
        if state == "disabled":
            self._dis = True
            self._cf, self._cfg, self._cb = CARBON_3, TEXT_GHOST, CARBON_3
            super().configure(cursor="")
            self._draw()
        elif state in ("normal", "active"):
            self._dis = False
            self._cf, self._cfg, self._cb = self._fn, self._fgn, self._bn
            super().configure(cursor="hand2")
            self._draw()
        if "text" in kw:
            self._text = kw.pop("text")
            self._draw()
        if "command" in kw:
            self._cmd = kw.pop("command")
        if kw:
            super().configure(**kw)

    configure = config


# ── Primary Button ────────────────────────────────────────────────────────────

class PrimaryButton(_Btn):
    """Yellow filled — main call-to-action."""

    def __init__(self, parent, text, command=None, **kw):
        kw.pop("bg", None)
        super().__init__(
            parent, text, command,
            fill_n=YELLOW,      fill_h=YELLOW_HOVER,
            fg_n=BLACK,         fg_h=BLACK,
            bdr_n=YELLOW,       bdr_h=YELLOW_HOVER,
            btn_h=36, radius=R_MD, font=FONT_BTN_LG, **kw,
        )


# ── Secondary Button ──────────────────────────────────────────────────────────

class SecondaryButton(_Btn):
    """Yellow-outlined ghost — secondary action."""

    def __init__(self, parent, text, command=None, **kw):
        kw.pop("bg", None)
        super().__init__(
            parent, text, command,
            fill_n=SURFACE,      fill_h=YELLOW_GLOW,
            fg_n=YELLOW,         fg_h=YELLOW,
            bdr_n=EDGE_BRIGHT,   bdr_h=YELLOW,
            btn_h=32, radius=R_MD, font=FONT_BTN, **kw,
        )


# ── Ghost Button ──────────────────────────────────────────────────────────────

class GhostButton(_Btn):
    """Muted ghost — tertiary / tool / playback actions."""

    def __init__(self, parent, text, command=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(
            parent, text, command,
            fill_n=bg,          fill_h=CARBON_5,
            fg_n=TEXT_MUTED,    fg_h=TEXT_DIM,
            bdr_n=bg,           bdr_h=bg,
            btn_h=28, radius=R_SM, font=FONT_SMALL, **kw,
        )


# ── Section Label ─────────────────────────────────────────────────────────────

class SectionLabel(tk.Frame):
    """Left accent bar + uppercase mono label + faint hairline extending right."""

    def __init__(self, parent, text, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)
        # Accent bar
        tk.Frame(self, bg=YELLOW, width=2).pack(side="left", fill="y",
                                                 padx=(0, 8))
        tk.Label(self, text=text.upper(), font=FONT_MONO,
                 fg=TEXT_MUTED, bg=bg).pack(side="left")
        # Hairline right
        tk.Frame(self, bg=EDGE_MID, height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0))


# ── Divider ───────────────────────────────────────────────────────────────────

def HDivider(parent, bg=SURFACE):
    return tk.Frame(parent, bg=EDGE, height=1)


# ── Lambo Slider (custom Canvas — no tk.Scale) ───────────────────────────────

class LamboSlider(tk.Frame):
    """
    Fully custom slider: Canvas track + fill + animated thumb.
    Replaces tk.Scale — no system widget appearance on any platform.
    """
    _TH   = 22   # thumb height (px)
    _TW   = 12   # thumb width  (px)
    _TKHT = 4    # track height (px)
    _CH   = 30   # canvas height

    def __init__(self, parent, label, key, from_, to, resolution,
                 value, value_fmt=str, on_change=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)
        self._from = float(from_)
        self._to   = float(to)
        self._res  = float(resolution)
        self._fmt  = value_fmt
        self._cb   = on_change
        self._key  = key
        self._bg   = bg
        self._var  = tk.DoubleVar(value=float(value))
        self._drag = False

        # ── Header: label + value badge ──
        hdr = tk.Frame(self, bg=bg)
        hdr.pack(fill="x", pady=(0, 3))
        tk.Label(hdr, text=label.upper(), font=FONT_MONO,
                 fg=TEXT_MUTED, bg=bg).pack(side="left")
        self._val_var = tk.StringVar(value=value_fmt(float(value)))
        self._badge = tk.Label(hdr, textvariable=self._val_var,
                               font=FONT_MONO, fg=YELLOW,
                               bg=YELLOW_SUBTLE, padx=6, pady=1)
        self._badge.pack(side="right")

        # ── Canvas slider ──
        self._c = tk.Canvas(self, bg=bg, height=self._CH,
                            highlightthickness=0, bd=0,
                            cursor="sb_h_double_arrow")
        self._c.pack(fill="x")
        self._c.bind("<Configure>",       self._redraw)
        self._c.bind("<Button-1>",        self._click)
        self._c.bind("<B1-Motion>",       self._drag_move)
        self._c.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", False))

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _margin(self):
        return self._TW // 2 + 3

    def _val_to_x(self, v, W):
        m = self._margin()
        return m + int((v - self._from) / (self._to - self._from) * (W - 2 * m))

    def _x_to_val(self, x, W):
        m = self._margin()
        frac = (x - m) / max(1, W - 2 * m)
        frac = max(0.0, min(1.0, frac))
        raw  = self._from + frac * (self._to - self._from)
        steps = round((raw - self._from) / self._res)
        v    = self._from + steps * self._res
        return round(max(self._from, min(self._to, v)), 8)

    def _redraw(self, e=None):
        c  = self._c
        c.delete("all")
        W  = c.winfo_width()
        H  = self._CH
        if W < 12:
            return
        v  = self._var.get()
        tx = self._val_to_x(v, W)
        my = H // 2
        m  = self._margin()

        # Track (full, dark)
        _rrect(c, m, my - 2, W - m, my + 2, r=2,
               fill=EDGE_BRIGHT, outline="")

        # Fill bar (left of thumb, yellow)
        if tx > m:
            _rrect(c, m, my - 2, tx, my + 2, r=2,
                   fill=YELLOW, outline="")

        # Thumb body
        tx1, tx2 = tx - self._TW // 2, tx + self._TW // 2
        ty1, ty2 = my - self._TH // 2, my + self._TH // 2
        _rrect(c, tx1, ty1, tx2, ty2, r=3, fill=YELLOW, outline="")

        # Thumb grip lines (3 dark horizontal lines)
        for dy in (-3, 0, 3):
            c.create_line(tx1 + 3, my + dy, tx2 - 3, my + dy,
                          fill=CARBON_2, width=1)

    def _click(self, e):
        self._drag = True
        self._set_from_x(e.x)

    def _drag_move(self, e):
        if self._drag:
            self._set_from_x(e.x)

    def _set_from_x(self, x):
        v = self._x_to_val(x, self._c.winfo_width())
        self._var.set(v)
        self._val_var.set(self._fmt(v))
        self._redraw()
        if self._cb:
            self._cb(self._key, v)

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self):
        return self._var.get()

    def set(self, v):
        self._var.set(float(v))
        self._val_var.set(self._fmt(float(v)))
        self._c.after_idle(self._redraw)


# ── Lambo Toggle (animated) ───────────────────────────────────────────────────

class LamboToggle(tk.Frame):
    """
    Canvas-based on/off toggle with smooth knob animation.
    Knob slides left↔right over ~120 ms. Track color lerps grey ↔ yellow.
    """
    _W   = 46   # track width
    _H   = 22   # track height
    _KW  = 18   # knob width
    _N   = 8    # animation steps
    _T   = 14   # ms per step

    def __init__(self, parent, label, key, value=True, on_change=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)
        self._key  = key
        self._cb   = on_change
        self._var  = tk.BooleanVar(value=value)
        self._bg   = bg
        self._aj   = None
        # Float knob position
        self._kx   = float(self._W - self._KW - 2) if value else 2.0

        tk.Label(self, text=label.upper(), font=FONT_MONO,
                 fg=TEXT_MUTED, bg=bg).pack(side="left")

        self._c = tk.Canvas(self, width=self._W, height=self._H,
                             bg=bg, highlightthickness=0, cursor="hand2")
        self._c.pack(side="right")
        self._c.bind("<Button-1>", self._toggle)
        self._draw_at(self._kx)

    def _draw_at(self, kx):
        c  = self._c
        c.delete("all")
        W, H = self._W, self._H
        # Interpolate track color based on knob position
        t_norm  = (kx - 2) / max(1, W - self._KW - 4)
        t_norm  = max(0.0, min(1.0, t_norm))
        track   = _lerp(EDGE_BRIGHT, YELLOW, t_norm)
        # Track
        _rrect(c, 0, 3, W, H - 3, r=4, fill=track, outline="")
        # Knob
        k = int(kx)
        knob_fill    = BLACK  if self._var.get() else CARBON_4
        knob_outline = YELLOW if self._var.get() else EDGE_BRIGHT
        _rrect(c, k, 1, k + self._KW, H - 1, r=4,
               fill=knob_fill, outline=knob_outline, width=1)
        # Yellow accent on top of knob when on
        if t_norm > 0.5:
            c.create_line(k + 4, 4, k + self._KW - 4, 4,
                          fill=YELLOW, width=2)

    def _toggle(self, _=None):
        new_val = not self._var.get()
        self._var.set(new_val)
        target  = float(self._W - self._KW - 2) if new_val else 2.0
        start   = self._kx
        if self._aj:
            self.after_cancel(self._aj)
        n  = self._N
        dx = (target - start) / n

        def step(i):
            if i > n:
                self._kx = target
                self._draw_at(target)
                return
            self._kx = start + dx * i
            self._draw_at(self._kx)
            self._aj = self.after(self._T, lambda: step(i + 1))

        step(1)
        if self._cb:
            self._cb(self._key, new_val)

    def get(self):
        return self._var.get()

    def set(self, v):
        self._var.set(bool(v))
        self._kx = float(self._W - self._KW - 2) if v else 2.0
        self._draw_at(self._kx)


# ── Stat Card ─────────────────────────────────────────────────────────────────

class StatCard(tk.Frame):
    """
    Big number + small label. accent=True puts a YELLOW top stripe.
    Used inside the stats canvas row in the editor.
    """

    def __init__(self, parent, label, value="—", accent=False, **kw):
        bg = kw.pop("bg", CARBON_3)
        super().__init__(parent, bg=bg, **kw)
        self._bg = bg

        # Top accent stripe
        if accent:
            tk.Frame(self, bg=YELLOW, height=2).pack(fill="x", side="top")

        inner = tk.Frame(self, bg=bg)
        inner.pack(fill="both", expand=True, padx=10, pady=(6, 7))

        self._val_var = tk.StringVar(value=value)
        tk.Label(inner, textvariable=self._val_var,
                 font=("Consolas", 22, "bold"),
                 fg=YELLOW if accent else TEXT,
                 bg=bg, anchor="center").pack(fill="x")

        tk.Label(inner, text=label.upper(),
                 font=("Consolas", 7),
                 fg=TEXT_GHOST, bg=bg, anchor="center").pack(fill="x")

    def set(self, v):
        self._val_var.set(str(v))


# ── Badge Label ───────────────────────────────────────────────────────────────

BADGE_STYLES = {
    "pause":      (YELLOW,       YELLOW_SUBTLE),
    "stutter":    (RED_FLAG,     "#1f0810"),
    "unclear":    (PURPLE_FLAG,  "#0e0b1f"),
    "breath":     (CYAN_FLAG,    "#041015"),
    "mouth_noise":(ORANGE_FLAG,  "#1a1000"),
}


def BadgeLabel(parent, badge_type, bg=CARBON_3):
    fg, bg_badge = BADGE_STYLES.get(badge_type.lower(), (TEXT_MUTED, EDGE))
    return tk.Label(parent, text=badge_type.upper(),
                    font=FONT_BADGE, fg=fg, bg=bg_badge,
                    padx=6, pady=2, relief="flat")


# ── Panel Section ─────────────────────────────────────────────────────────────

class PanelSection(tk.Frame):
    """A section inside a panel: optional SectionLabel header + content frame."""

    def __init__(self, parent, title=None, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)

        if title:
            hdr = tk.Frame(self, bg=bg)
            hdr.pack(fill="x", padx=SECTION_PAD, pady=(10, 6))
            SectionLabel(hdr, title, bg=bg).pack(fill="x")

        self.content = tk.Frame(self, bg=bg)
        self.content.pack(fill="x", padx=SECTION_PAD, pady=(0, 10))

    def add(self, widget, **pack_kw):
        widget.pack(in_=self.content, fill="x", **pack_kw)
        return widget


# ── Waveform Canvas ───────────────────────────────────────────────────────────

class WaveformCanvas(tk.Canvas):
    """
    Renders an audio waveform from a float sample array.
    Colored region tints for every flag type.
    Supports a moveable yellow playhead.
    """

    def __init__(self, parent, height=WAVEFORM_H, **kw):
        bg = kw.pop("bg", CARBON_2)
        super().__init__(parent, bg=bg, height=height,
                         highlightthickness=0, bd=0, **kw)
        self._samples       = []
        self._flags         = []
        self._height        = height
        self._playhead_frac = 0.0
        self.bind("<Configure>", lambda e: self._redraw())

    def load(self, samples, flags=None):
        self._samples = samples if samples is not None else []
        self._flags   = flags   if flags   is not None else []
        self._playhead_frac = 0.0
        self.after(50, self._redraw)

    def set_playhead(self, fraction: float):
        self._playhead_frac = max(0.0, min(1.0, fraction))
        W = self.winfo_width()
        H = self._height
        px = int(W * self._playhead_frac)
        existing = self.find_withtag("playhead")
        if existing:
            self.coords(existing[0], px, 0, px, H)
        else:
            self.create_line(px, 0, px, H, fill=YELLOW, width=2,
                             tags="playhead")

    def _redraw(self):
        self.delete("all")
        W = self.winfo_width()
        H = self._height
        if W < 4:
            self.after(100, self._redraw)
            return

        mid = H // 2
        self.create_line(0, mid, W, mid, fill=EDGE_MID, width=1)
        self.create_text(8, 5, text="WAVEFORM", font=FONT_MONO,
                         fill=TEXT_GHOST, anchor="nw")

        if not self._samples:
            # Empty state: faint tick marks
            for x in range(0, W, 3):
                self.create_line(x, mid - 2, x, mid + 2,
                                 fill=EDGE_MID, width=1)
            px = int(W * self._playhead_frac)
            self.create_line(px, 0, px, H, fill=YELLOW, width=2,
                             tags="playhead")
            return

        dur = len(self._samples)
        _tint = {
            "pause":      TINT_PAUSE,
            "stutter":    TINT_STUTTER,
            "unclear":    TINT_UNCLEAR,
            "breath":     TINT_BREATH,
            "mouth_noise":TINT_MOUTH_NOISE,
        }
        for f in self._flags:
            s_px = int(f.get("start_sample", 0)       / dur * W)
            e_px = int(f.get("end_sample",   dur)      / dur * W)
            self.create_rectangle(s_px, 0, e_px, H,
                                  fill=_tint.get(f["type"], TINT_PAUSE),
                                  outline="")

        flag_px = {}
        _col = {
            "stutter":    RED_FLAG,
            "unclear":    PURPLE_FLAG,
            "breath":     CYAN_FLAG,
            "mouth_noise":ORANGE_FLAG,
        }
        for f in self._flags:
            s_px = int(f.get("start_sample", 0)  / dur * W)
            e_px = int(f.get("end_sample",   dur) / dur * W)
            color = _col.get(f["type"], YELLOW)
            for px in range(s_px, e_px):
                flag_px[px] = color

        step = max(1, dur // W)
        amp  = (H - 20) / 2

        import numpy as np
        for x in range(W):
            i     = x * step
            chunk = self._samples[i: i + step]
            if len(chunk) == 0:
                continue
            peak  = float(np.max(np.abs(chunk)))
            bar_h = max(2, int(peak * amp))
            color = flag_px.get(x, CARBON_5 if x < W * 0.33 else EDGE_BRIGHT)
            self.create_line(x, mid - bar_h, x, mid + bar_h,
                             fill=color, width=1)

        px = int(W * self._playhead_frac)
        self.create_line(px, 0, px, H, fill=YELLOW, width=2,
                         tags="playhead")


# ── Dark Scrollbar ────────────────────────────────────────────────────────────

class DarkScrollbar(tk.Canvas):
    """
    Canvas-rendered scrollbar. Windows ignores native scrollbar colors,
    so we draw our own. 8 px wide, rounded thumb, subtly visible.
    """
    THUMB_MIN = 24
    WIDTH     = 8

    def __init__(self, parent, command=None, **kw):
        bg = kw.pop("bg", CARBON_1)
        super().__init__(parent, bg=bg, width=self.WIDTH,
                         highlightthickness=0, bd=0, **kw)
        self._command  = command
        self._lo       = 0.0
        self._hi       = 1.0
        self._dragging = False
        self._drag_y   = 0

        self.bind("<Button-1>",        self._on_click)
        self.bind("<B1-Motion>",       self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>",       lambda e: self._draw())

    def set(self, lo, hi):
        self._lo = float(lo)
        self._hi = float(hi)
        self._draw()

    def _draw(self):
        self.delete("all")
        H = self.winfo_height()
        if H < 4 or self._hi - self._lo >= 1.0:
            return
        W       = self.WIDTH
        thumb_h = max(self.THUMB_MIN, int((self._hi - self._lo) * H))
        thumb_y = int(self._lo * H)
        # Track line
        self.create_line(W // 2, 0, W // 2, H, fill=EDGE, width=1)
        # Rounded thumb
        _rrect(self, 1, thumb_y, W - 1, thumb_y + thumb_h,
               r=R_SM, fill=CARBON_6, outline="")

    def _on_click(self, e):
        H = self.winfo_height()
        if H < 4:
            return
        thumb_h = max(self.THUMB_MIN, int((self._hi - self._lo) * H))
        thumb_y = int(self._lo * H)
        if thumb_y <= e.y <= thumb_y + thumb_h:
            self._dragging = True
            self._drag_y   = e.y - thumb_y
        elif self._command:
            self._command("moveto", str(e.y / H))

    def _on_drag(self, e):
        if not self._dragging:
            return
        H = self.winfo_height()
        if H < 4:
            return
        frac = max(0.0, min(1.0, (e.y - self._drag_y) / H))
        if self._command:
            self._command("moveto", str(frac))

    def _on_release(self, e):
        self._dragging = False


# ── Flag List ─────────────────────────────────────────────────────────────────

_FLAG_COLORS = {
    "pause":      YELLOW,
    "stutter":    RED_FLAG,
    "unclear":    PURPLE_FLAG,
    "breath":     CYAN_FLAG,
    "mouth_noise":ORANGE_FLAG,
}


class FlagList(tk.Frame):
    """
    Pure-Tk scrollable issue table. No ttk — fully styleable on Windows.
    Columns: TYPE | TIME | DESCRIPTION | SEVERITY
    """
    ROW_H = 30
    HDR_H = 28

    def __init__(self, parent, **kw):
        bg = kw.pop("bg", CARBON_1)
        super().__init__(parent, bg=bg, **kw)
        self._bg   = bg
        self._rows = []

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=CARBON_3, height=self.HDR_H)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=YELLOW, height=1).pack(side="bottom", fill="x")

        hdr_inner = tk.Frame(hdr, bg=CARBON_3)
        hdr_inner.pack(fill="both", expand=True)
        hdr_inner.columnconfigure(2, weight=1)

        for col, label in enumerate(("TYPE", "TIME", "DESCRIPTION", "SEVERITY")):
            anchor = "w" if col < 3 else "e"
            tk.Label(hdr_inner, text=label, font=FONT_MONO,
                     fg=TEXT_GHOST, bg=CARBON_3,
                     anchor=anchor, padx=12, pady=0).grid(
                row=0, column=col,
                sticky="ew" if col == 2 else ("w" if col < 3 else "e"))

        # ── Scrollable body ───────────────────────────────────────────────────
        body = tk.Frame(self, bg=bg)
        body.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(body, bg=bg,
                                  highlightthickness=0, bd=0)
        self._scrollbar = DarkScrollbar(body, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=bg)
        self._win   = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_cfg)
        self._canvas.bind("<Configure>", self._on_canvas_cfg)
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _on_inner_cfg(self, _=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_cfg(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def _on_wheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def clear(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._rows = []

    def insert(self, flag_type, timecode, description, severity=1):
        idx    = len(self._rows)
        row_bg = CARBON_2 if idx % 2 == 0 else self._bg
        fg_type = _FLAG_COLORS.get(flag_type.lower(), TEXT_MUTED)

        row = tk.Frame(self._inner, bg=row_bg, height=self.ROW_H)
        row.pack(fill="x")
        row.pack_propagate(False)

        # Animated hover via color lerp
        def _set_bg(widget, color):
            widget.config(bg=color)
            for child in widget.winfo_children():
                try:
                    child.config(bg=color)
                except Exception:
                    pass

        _hover_jobs = [None]

        def _hover_anim(target, step=0, n=6):
            if _hover_jobs[0]:
                row.after_cancel(_hover_jobs[0])
            start = _lerp(row_bg, YELLOW_SUBTLE, step / max(n, 1)) \
                    if target == YELLOW_SUBTLE else \
                    _lerp(YELLOW_SUBTLE, row_bg, step / max(n, 1))
            _set_bg(row, start)
            if step < n:
                _hover_jobs[0] = row.after(
                    12, lambda: _hover_anim(target, step + 1, n))

        row.bind("<Enter>", lambda e: _hover_anim(YELLOW_SUBTLE))
        row.bind("<Leave>", lambda e: _hover_anim(row_bg))

        # Left color bar (2px, flag color)
        bar = tk.Frame(row, bg=fg_type, width=2)
        bar.pack(side="left", fill="y")
        bar.bind("<Enter>", lambda e: _hover_anim(YELLOW_SUBTLE))
        bar.bind("<Leave>", lambda e: _hover_anim(row_bg))

        # Type badge
        type_lbl = tk.Label(row, text=flag_type.upper(),
                             font=FONT_BADGE, fg=fg_type, bg=row_bg,
                             width=10, anchor="center", padx=4)
        type_lbl.pack(side="left")
        type_lbl.bind("<Enter>", lambda e: _hover_anim(YELLOW_SUBTLE))
        type_lbl.bind("<Leave>", lambda e: _hover_anim(row_bg))

        # Timecode
        time_lbl = tk.Label(row, text=timecode, font=FONT_MONO,
                             fg=TEXT_MUTED, bg=row_bg, width=10, anchor="center")
        time_lbl.pack(side="left")
        time_lbl.bind("<Enter>", lambda e: _hover_anim(YELLOW_SUBTLE))
        time_lbl.bind("<Leave>", lambda e: _hover_anim(row_bg))

        # Description
        desc_lbl = tk.Label(row, text=description, font=FONT_SMALL,
                             fg=TEXT_DIM, bg=row_bg, anchor="w", padx=8)
        desc_lbl.pack(side="left", fill="x", expand=True)
        desc_lbl.bind("<Enter>", lambda e: _hover_anim(YELLOW_SUBTLE))
        desc_lbl.bind("<Leave>", lambda e: _hover_anim(row_bg))

        # Severity — canvas mini bar chart
        sev_c = tk.Canvas(row, width=56, height=self.ROW_H,
                          bg=row_bg, highlightthickness=0)
        sev_c.pack(side="right", padx=(0, 12))
        sev_c.bind("<Enter>", lambda e: _hover_anim(YELLOW_SUBTLE))
        sev_c.bind("<Leave>", lambda e: _hover_anim(row_bg))

        bw, bh, gap = 4, 10, 3
        total_w = 3 * bw + 2 * gap
        sx = (56 - total_w) // 2
        sy = (self.ROW_H - bh) // 2
        for b in range(3):
            x = sx + b * (bw + gap)
            fill = fg_type if (b + 1) <= severity else EDGE_MID
            sev_c.create_rectangle(x, sy, x + bw, sy + bh, fill=fill, outline="")

        # Row separator
        tk.Frame(self._inner, bg=EDGE, height=1).pack(fill="x")
        self._rows.append(row)

    def get_children(self):
        return self._rows

    def delete_all(self):
        self.clear()


# ── Factories ─────────────────────────────────────────────────────────────────

def make_flag_tree(parent, bg=CARBON_1):
    return FlagList(parent, bg=bg)


def styled_scrollbar(parent, orient="vertical", command=None):
    return DarkScrollbar(parent, command=command)


# ── Notebook (styled ttk) ─────────────────────────────────────────────────────

def make_notebook(parent):
    """Return a ttk.Notebook styled to match the Voxarah design."""
    style = ttk.Style()
    style.configure("Voxarah.TNotebook",
                    background=CARBON_1, borderwidth=0, tabmargins=0)
    style.configure("Voxarah.TNotebook.Tab",
                    background=BLACK, foreground=TEXT_GHOST,
                    padding=[18, 8], font=FONT_TAB, borderwidth=0)
    style.map("Voxarah.TNotebook.Tab",
              background=[("selected", CARBON_2)],
              foreground=[("selected", YELLOW)])
    return ttk.Notebook(parent, style="Voxarah.TNotebook")


# ── Log Text ──────────────────────────────────────────────────────────────────

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


# ── Progress Bar (animated) ───────────────────────────────────────────────────

class LamboProgress(tk.Frame):
    """
    Thin animated progress bar with mono label.
    Smoothly animates fill fraction changes.
    """
    _STEPS = 10
    _FRAME = 16

    def __init__(self, parent, **kw):
        bg = kw.pop("bg", SURFACE)
        super().__init__(parent, bg=bg, **kw)
        self._bg      = bg
        self._target  = 0.0
        self._current = 0.0
        self._aj      = None

        self._label_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._label_var,
                 font=FONT_MONO, fg=TEXT_GHOST, bg=bg).pack(anchor="w",
                                                              pady=(0, 3))
        track = tk.Frame(self, bg=EDGE_MID, height=3)
        track.pack(fill="x")
        track.pack_propagate(False)

        self._fill = tk.Frame(track, bg=YELLOW, height=3)
        self._fill.place(x=0, y=0, relheight=1, relwidth=0)

    def set(self, fraction, label=""):
        self._target = max(0.0, min(1.0, fraction))
        if label:
            self._label_var.set(label.upper())
        self._animate()

    def _animate(self):
        if self._aj:
            self.after_cancel(self._aj)
        start  = self._current
        target = self._target
        n      = self._STEPS

        def step(i):
            if i > n:
                self._current = target
                self._fill.place(relwidth=target)
                return
            self._current = start + (target - start) * (i / n)
            self._fill.place(relwidth=self._current)
            self._aj = self.after(self._FRAME, lambda: step(i + 1))

        step(1)

    def reset(self):
        self._target  = 0.0
        self._current = 0.0
        if self._aj:
            self.after_cancel(self._aj)
            self._aj = None
        self._fill.place(relwidth=0)
        self._label_var.set("")
