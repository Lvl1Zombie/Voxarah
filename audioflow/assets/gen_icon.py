"""
Generate Voxarah icon based on the original hexagon + diamond design.
Scales the original 22x22 canvas drawing to high resolution.

Original design (from ui/app.py initial commit):
  pts = [(11,1),(21,6),(21,16),(11,21),(1,16),(1,6)]  # hexagon
  Vertical center line: (11,4) to (11,18)
  Internal V lines (left): (5,8)→(11,4), (5,14)→(11,18)
  Internal V lines (right): (17,8)→(11,4), (17,14)→(11,18)
"""
from PIL import Image, ImageDraw, ImageFilter
import io, os, struct

BLACK  = (8,   8,   8,   255)
YELLOW = (245, 197, 24,  255)
SHINE  = (255, 230, 120, 180)

ORIG = 22  # original canvas size

def scale(coord, s):
    return int(coord / ORIG * s)

def draw_master(s: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (s, s), BLACK)
    d = ImageDraw.Draw(img)

    # Outer border frame (matches gen_icon.py style)
    mg = int(s * 0.022)
    bw = max(2, int(s * 0.006))
    d.rectangle([mg, mg, s - mg - 1, s - mg - 1],
                outline=(245, 197, 24, 55), width=bw)

    # Corner accent ticks
    tk_len = int(s * 0.055)
    tw = max(2, int(s * 0.009))
    for cx, cy in [(mg, mg), (s - mg, mg), (mg, s - mg), (s - mg, s - mg)]:
        sx = 1 if cx == mg else -1
        sy = 1 if cy == mg else -1
        d.line([(cx, cy), (cx + sx * tk_len, cy)], fill=YELLOW, width=tw)
        d.line([(cx, cy), (cx, cy + sy * tk_len)], fill=YELLOW, width=tw)

    # Scale original hexagon points to new canvas
    orig_pts = [(11,1),(21,6),(21,16),(11,21),(1,16),(1,6)]
    hex_pts = [(scale(x, s), scale(y, s)) for x, y in orig_pts]

    # Glow layer
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.polygon(hex_pts, outline=(245, 197, 24, 60), fill=None, width=max(2, int(s * 0.008)))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(s * 0.015)))
    img = Image.alpha_composite(img, glow)

    d2 = ImageDraw.Draw(img)

    # Hexagon outline
    lw = max(3, int(s * 0.012))
    d2.polygon(hex_pts, outline=YELLOW, fill=None, width=lw)

    # Internal diamond/V lines
    # Top center: (11,4), Bottom center: (11,18)
    top    = (scale(11, s), scale(4,  s))
    bottom = (scale(11, s), scale(18, s))
    left_top    = (scale(5,  s), scale(8,  s))
    left_bot    = (scale(5,  s), scale(14, s))
    right_top   = (scale(17, s), scale(8,  s))
    right_bot   = (scale(17, s), scale(14, s))

    ilw = max(2, int(s * 0.008))

    # Vertical center line
    d2.line([top, bottom], fill=YELLOW, width=ilw)
    # Left upper: (5,8) → (11,4)
    d2.line([left_top, top], fill=YELLOW, width=ilw)
    # Left lower: (5,14) → (11,18)
    d2.line([left_bot, bottom], fill=YELLOW, width=ilw)
    # Right upper: (17,8) → (11,4)
    d2.line([right_top, top], fill=YELLOW, width=ilw)
    # Right lower: (17,14) → (11,18)
    d2.line([right_bot, bottom], fill=YELLOW, width=ilw)

    # Subtle shine on top hexagon edge
    sw = max(2, int(s * 0.004))
    d2.line([hex_pts[0], hex_pts[1]], fill=SHINE, width=sw)
    d2.line([hex_pts[5], hex_pts[0]], fill=SHINE, width=sw)

    return img


def write_ico(images: dict, path: str):
    sizes = sorted(images.keys())
    n = len(sizes)
    png_bufs = []
    for sz in sizes:
        buf = io.BytesIO()
        images[sz].save(buf, format="PNG", compress_level=6)
        png_bufs.append(buf.getvalue())

    header_sz = 6
    dir_sz = 16 * n
    offset = header_sz + dir_sz

    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, n))
        for i, sz in enumerate(sizes):
            w = sz if sz < 256 else 0
            h = sz if sz < 256 else 0
            data_size = len(png_bufs[i])
            f.write(struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, data_size, offset))
            offset += data_size
        for buf in png_bufs:
            f.write(buf)


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))

    master = draw_master(1024)

    # Write icon.ico
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = {sz: master.resize((sz, sz), Image.LANCZOS).convert("RGBA") for sz in sizes}
    ico_path = os.path.join(out_dir, "icon.ico")
    write_ico(images, ico_path)
    print(f"icon.ico -> {ico_path}")

    # Write logo_hd.png (512x512)
    hd = draw_master(512)
    hd_path = os.path.join(out_dir, "logo_hd.png")
    hd.save(hd_path, format="PNG", compress_level=6)
    print(f"logo_hd.png -> {hd_path}")
    print("Done. Same hexagon shape as original, high resolution.")
