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
FONT_DISPLAY  = ("Segoe UI", 14, "bold")       # wordmark / big numbers
FONT_DISPLAY_SM = ("Segoe UI", 10, "bold")
FONT_TITLE    = ("Segoe UI", 11, "bold")
FONT_LABEL    = ("Segoe UI", 8, "bold")        # section labels
FONT_BODY     = ("Segoe UI", 10)
FONT_BODY_SB  = ("Segoe UI", 10, "bold")
FONT_SMALL    = ("Segoe UI", 9)
FONT_MONO     = ("Consolas", 8)                # readouts, timecodes
FONT_MONO_MED = ("Consolas", 9)
FONT_STAT     = ("Consolas", 20, "bold")       # big stat numbers
FONT_STAT_SM  = ("Consolas", 13, "bold")
FONT_BTN      = ("Segoe UI", 9, "bold")
FONT_BTN_LG   = ("Segoe UI", 10, "bold")
FONT_BADGE    = ("Consolas", 7, "bold")
FONT_TAB      = ("Segoe UI", 9, "bold")

# ── Dimensions ────────────────────────────────────────────────────────────────
TITLEBAR_H    = 40
TABBAR_H      = 34
LEFT_PANEL_W  = 248
BOTTOM_BAR_H  = 24
STAT_ROW_H    = 60
WAVEFORM_H    = 72
SECTION_PAD   = 14
ITEM_GAD      = 8
