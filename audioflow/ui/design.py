"""
Voxarah — Design System
All colors, fonts, and style constants for the Lamborghini-inspired UI.
"""

# ── Colors ────────────────────────────────────────────────────────────────────
YELLOW        = "#F5C518"
YELLOW_DIM    = "#c49a10"
YELLOW_GLOW   = "#2a2200"
YELLOW_SUBTLE = "#1a1600"

BLACK         = "#080808"
CARBON_0      = "#0a0a0a"
CARBON_1      = "#0d0d0d"
CARBON_2      = "#111111"
CARBON_3      = "#161616"
CARBON_4      = "#1c1c1c"
CARBON_5      = "#222222"

EDGE          = "#1e1e1e"
EDGE_BRIGHT   = "#2a2a2a"
EDGE_MID      = "#252525"

TEXT          = "#e0e0e0"
TEXT_DIM      = "#aaaaaa"
TEXT_MUTED    = "#666666"
TEXT_GHOST    = "#333333"

YELLOW_TEXT   = "#F5C518"
RED_FLAG      = "#f76a8a"
PURPLE_FLAG   = "#7c6af7"
GREEN_OK      = "#2a8a4a"

# ── Semantic ──────────────────────────────────────────────────────────────────
BG            = CARBON_1
SURFACE       = CARBON_2
SURFACE2      = CARBON_3
SURFACE3      = CARBON_4
BORDER        = EDGE
BORDER2       = EDGE_BRIGHT
ACCENT        = YELLOW
MUTED         = TEXT_MUTED

# ── Fonts ─────────────────────────────────────────────────────────────────────
# Tkinter fallbacks — Orbitron not available natively, use closest equivalents
FONT_DISPLAY  = ("Segoe UI", 16, "bold")       # wordmark / big numbers
FONT_DISPLAY_SM = ("Segoe UI", 12, "bold")
FONT_TITLE    = ("Segoe UI", 13, "bold")
FONT_LABEL    = ("Segoe UI", 10, "bold")       # section labels
FONT_BODY     = ("Segoe UI", 11)
FONT_BODY_SB  = ("Segoe UI", 11, "bold")
FONT_SMALL    = ("Segoe UI", 10)
FONT_MONO     = ("Consolas", 10)               # readouts, timecodes
FONT_MONO_MED = ("Consolas", 11)
FONT_STAT     = ("Consolas", 24, "bold")       # big stat numbers
FONT_STAT_SM  = ("Consolas", 15, "bold")
FONT_BTN      = ("Segoe UI", 10, "bold")
FONT_BTN_LG   = ("Segoe UI", 11, "bold")
FONT_BADGE    = ("Consolas", 9, "bold")
FONT_TAB      = ("Segoe UI", 10, "bold")

# ── Waveform region tints ─────────────────────────────────────────────────────
TINT_PAUSE    = "#2a2200"   # dark yellow behind pause regions
TINT_STUTTER  = "#1a0a10"   # dark red behind stutter regions
TINT_UNCLEAR  = "#0e0b1f"   # dark purple behind unclear regions

# ── Status bar separator ──────────────────────────────────────────────────────
SEP_COLOR     = "#1a1a1a"

# ── Dimensions ────────────────────────────────────────────────────────────────
TITLEBAR_H    = 84
TABBAR_H      = 40
LEFT_PANEL_W  = 272
BOTTOM_BAR_H  = 28
STAT_ROW_H    = 72
WAVEFORM_H    = 84
SECTION_PAD   = 16
ITEM_GAD      = 10
