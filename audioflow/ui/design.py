"""
Voxarah — Design System  v3
Lamborghini-inspired dark theme. Matte black + F5C518 yellow.
All colors, fonts, spacing, radii, and animation constants live here.
"""

# ── Brand Colors ───────────────────────────────────────────────────────────────
YELLOW        = "#F5C518"
YELLOW_DIM    = "#c49a10"
YELLOW_HOVER  = "#ddb015"     # button hover (between YELLOW and YELLOW_DIM)
YELLOW_GLOW   = "#2a2200"
YELLOW_SUBTLE = "#1a1600"

# ── Neutral Scale (true dark — not blue-shifted) ───────────────────────────────
BLACK         = "#080808"
CARBON_0      = "#0a0a0a"
CARBON_1      = "#0d0d0d"
CARBON_2      = "#111111"
CARBON_3      = "#161616"
CARBON_4      = "#1c1c1c"
CARBON_5      = "#222222"
CARBON_6      = "#2a2a2a"     # extra depth level

EDGE          = "#1e1e1e"
EDGE_MID      = "#252525"
EDGE_BRIGHT   = "#2a2a2a"

# ── Text ───────────────────────────────────────────────────────────────────────
TEXT          = "#e0e0e0"
TEXT_DIM      = "#aaaaaa"
TEXT_MUTED    = "#666666"
TEXT_GHOST    = "#333333"

# ── Semantic Aliases ───────────────────────────────────────────────────────────
BG            = CARBON_1
SURFACE       = CARBON_2
SURFACE2      = CARBON_3
SURFACE3      = CARBON_4
BORDER        = EDGE
BORDER2       = EDGE_BRIGHT
ACCENT        = YELLOW
MUTED         = TEXT_MUTED

# ── Flag / Status Colors ───────────────────────────────────────────────────────
YELLOW_TEXT   = "#F5C518"
RED_FLAG      = "#f76a8a"
PURPLE_FLAG   = "#7c6af7"
CYAN_FLAG     = "#4ab8d8"
ORANGE_FLAG   = "#f5a623"
GREEN_OK      = "#2a8a4a"

# ── Waveform Region Tints ──────────────────────────────────────────────────────
TINT_PAUSE       = "#2a2200"
TINT_STUTTER     = "#1a0a10"
TINT_UNCLEAR     = "#0e0b1f"
TINT_BREATH      = "#051218"
TINT_MOUTH_NOISE = "#1a1000"

# ── Status Bar ─────────────────────────────────────────────────────────────────
SEP_COLOR     = "#1a1a1a"

# ── Typography ─────────────────────────────────────────────────────────────────
FONT_DISPLAY    = ("Segoe UI", 16, "bold")
FONT_DISPLAY_SM = ("Segoe UI", 12, "bold")
FONT_TITLE      = ("Segoe UI", 13, "bold")
FONT_LABEL      = ("Segoe UI", 10, "bold")
FONT_BODY       = ("Segoe UI", 11)
FONT_BODY_SB    = ("Segoe UI", 11, "bold")
FONT_SMALL      = ("Segoe UI", 10)
FONT_MONO       = ("Consolas", 10)
FONT_MONO_MED   = ("Consolas", 11)
FONT_STAT       = ("Consolas", 24, "bold")
FONT_STAT_SM    = ("Consolas", 15, "bold")
FONT_BTN        = ("Segoe UI", 10, "bold")
FONT_BTN_LG     = ("Segoe UI", 11, "bold")
FONT_BADGE      = ("Consolas", 9, "bold")
FONT_TAB        = ("Segoe UI", 10, "bold")

# ── Spacing — 4-point grid ─────────────────────────────────────────────────────
SP_1 = 4
SP_2 = 8
SP_3 = 12
SP_4 = 16    # = SECTION_PAD
SP_5 = 24
SP_6 = 32

SECTION_PAD   = SP_4
ITEM_GAD      = SP_2 + SP_1   # 12

# ── Corner Radii ──────────────────────────────────────────────────────────────
R_SM  = 3    # small elements: badges, scrollbar thumbs
R_MD  = 5    # standard: buttons, cards
R_LG  = 8    # large: modals, panels

# ── Animation ─────────────────────────────────────────────────────────────────
ANIM_FAST  = 80    # ms — snappy feedback
ANIM_MED   = 150   # ms — standard hover transition
ANIM_SLOW  = 260   # ms — deliberate movement

# ── Layout ────────────────────────────────────────────────────────────────────
TITLEBAR_H    = 84
TABBAR_H      = 40
LEFT_PANEL_W  = 272
BOTTOM_BAR_H  = 40
STAT_ROW_H    = 72
WAVEFORM_H    = 84


# ── Color Utility ─────────────────────────────────────────────────────────────

def lerp_color(c1: str, c2: str, t: float) -> str:
    """Linear interpolation between two hex colors. t ∈ [0.0, 1.0]."""
    def _p(h):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r1, g1, b1 = _p(c1)
    r2, g2, b2 = _p(c2)
    clamp = lambda v: max(0, min(255, int(v)))
    return (f"#{clamp(r1 + (r2 - r1) * t):02x}"
            f"{clamp(g1 + (g2 - g1) * t):02x}"
            f"{clamp(b1 + (b2 - b1) * t):02x}")
