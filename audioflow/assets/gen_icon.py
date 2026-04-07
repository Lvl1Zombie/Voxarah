"""
Generate Voxarah logo_hd.png and icon.ico — Hex Shield design.
Pointy-top hexagon, double-headed arrow, 4 dots. #F5C518 on #080808.
"""
import math, io, os, struct
from PIL import Image, ImageDraw

BLACK      = (8,   8,   8,   255)
YELLOW     = (245, 197, 24,  255)
YELLOW_DIM = (245, 197, 24,  150)   # inner hex: same hue, ~60% opacity


def draw_hex_shield(size: int) -> Image.Image:
    """Render the Hex Shield at `size` x `size`, transparent background."""
    # 4x supersampling for clean anti-aliased edges
    SS = 4
    S  = size * SS
    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = cy = S / 2

    # All radii/positions expressed as fraction of size, then scaled to S
    def px(frac):
        return frac * S

    def hex_pts(r_frac):
        """Pointy-top hexagon, radius as fraction of S."""
        pts = []
        for i in range(6):
            a = math.radians(-90 + i * 60)
            pts.append((cx + px(r_frac) * math.cos(a),
                        cy + px(r_frac) * math.sin(a)))
        return pts

    # Stroke widths in supersampled pixels (divide by SS to get display px)
    lw_outer = max(SS, round(0.020 * S))   # ~1.0 display px
    lw_inner = max(SS, round(0.012 * S))   # ~0.6 display px
    shaft_w  = max(SS, round(0.012 * S))   # ~0.6 display px
    dot_r    = max(SS, round(0.020 * S))   # ~1.0 display px radius

    # ── Outer hexagon ────────────────────────────────────────────────────
    draw.polygon(hex_pts(0.420), outline=YELLOW,     fill=None, width=lw_outer)

    # ── Inner hexagon ────────────────────────────────────────────────────
    draw.polygon(hex_pts(0.300), outline=YELLOW_DIM, fill=None, width=lw_inner)

    # ── Double-headed arrow ──────────────────────────────────────────────
    tip_top_y    = cx - px(0.350)   # tip of top arrow
    tip_bot_y    = cx + px(0.350)   # tip of bottom arrow
    base_top_y   = cx - px(0.195)   # base of top arrowhead
    base_bot_y   = cx + px(0.195)   # base of bottom arrowhead
    arrow_hw     = px(0.072)        # half-width of arrowhead (narrower/sharper)

    draw.line([(cx, base_top_y), (cx, base_bot_y)], fill=YELLOW, width=shaft_w)
    draw.polygon([(cx, tip_top_y), (cx - arrow_hw, base_top_y), (cx + arrow_hw, base_top_y)], fill=YELLOW)
    draw.polygon([(cx, tip_bot_y), (cx - arrow_hw, base_bot_y), (cx + arrow_hw, base_bot_y)], fill=YELLOW)

    # ── Four dots ────────────────────────────────────────────────────────
    for fx, fy in [(0.125, 0.420), (0.875, 0.420), (0.125, 0.580), (0.875, 0.580)]:
        x, y = px(fx), px(fy)
        draw.ellipse([(x - dot_r, y - dot_r), (x + dot_r, y + dot_r)], fill=YELLOW)

    # Downsample 4x → display size
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def write_ico(frames: dict, path: str):
    sizes = sorted(frames.keys())
    png_bufs = []
    for sz in sizes:
        buf = io.BytesIO()
        frames[sz].save(buf, format="PNG", compress_level=6)
        png_bufs.append(buf.getvalue())
    offset = 6 + 16 * len(sizes)
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(sizes)))
        for i, sz in enumerate(sizes):
            w = sz if sz < 256 else 0
            h = sz if sz < 256 else 0
            f.write(struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png_bufs[i]), offset))
            offset += len(png_bufs[i])
        for buf in png_bufs:
            f.write(buf)


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # logo_hd.png — black background, used by app.py for OS title bar icon
    # and displayed in the title bar via PIL resize
    hd = Image.new("RGBA", (512, 512), BLACK)
    hd.alpha_composite(draw_hex_shield(512))
    hd_path = os.path.join(out_dir, "logo_hd.png")
    hd.save(hd_path, "PNG")
    print(f"logo_hd.png -> {hd_path}")

    # icon.ico — black background
    sizes  = [16, 32, 48, 64, 128, 256]
    frames = {}
    for sz in sizes:
        bg = Image.new("RGBA", (sz, sz), BLACK)
        bg.alpha_composite(draw_hex_shield(sz))
        frames[sz] = bg
    ico_path = os.path.join(out_dir, "icon.ico")
    write_ico(frames, ico_path)
    print(f"icon.ico    -> {ico_path}")
    print("Done.")
