"""
Generate Voxarah icon.ico — Lamborghini-inspired angular V mark.
- Renders at 1024x1024 master, LANCZOS-downscales to each size
- Writes the ICO file manually so every size is stored as lossless PNG
  (modern Windows handles PNG-in-ICO natively and it looks crisp at any DPI)
"""
from PIL import Image, ImageDraw, ImageFilter
import io, os, struct

# ── Palette ───────────────────────────────────────────────────────────────────
BLACK  = (8,   8,   8,   255)
YELLOW = (245, 197, 24,  255)
SHINE  = (255, 230, 120, 180)

# ── V polygon (coordinates as fractions of canvas size) ──────────────────────
V_FRACS = [
    (0.108, 0.148),   # top-left  outer  (angled cut)
    (0.392, 0.098),   # top-left  inner
    (0.478, 0.872),   # tip inner-left
    (0.500, 0.918),   # tip bottom point
    (0.522, 0.872),   # tip inner-right
    (0.608, 0.098),   # top-right inner
    (0.892, 0.148),   # top-right outer  (angled cut)
    (0.580, 0.888),   # outer bottom-right
    (0.500, 0.935),   # outer bottom tip
    (0.420, 0.888),   # outer bottom-left
]

def v_poly(s):
    return [(int(fx * s), int(fy * s)) for fx, fy in V_FRACS]


# ── Draw the master image ─────────────────────────────────────────────────────
def draw_master(s: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (s, s), BLACK)
    d   = ImageDraw.Draw(img)

    # Faint diagonal speed lines at corners
    for offset in range(0, 100, 28):
        c = (245, 197, 24, 16)
        d.line([(0, offset), (offset, 0)],         fill=c, width=1)
        d.line([(s, offset), (s - offset, 0)],     fill=c, width=1)
        d.line([(0, s - offset), (offset, s)],     fill=c, width=1)
        d.line([(s, s - offset), (s - offset, s)], fill=c, width=1)

    # Outer border frame
    mg = int(s * 0.022)
    bw = max(2, int(s * 0.006))
    d.rectangle([mg, mg, s - mg - 1, s - mg - 1],
                outline=(245, 197, 24, 55), width=bw)

    # Corner accent ticks
    tk = int(s * 0.055)
    tw = max(2, int(s * 0.009))
    for cx, cy in [(mg, mg), (s - mg, mg), (mg, s - mg), (s - mg, s - mg)]:
        sx = 1 if cx == mg else -1
        sy = 1 if cy == mg else -1
        d.line([(cx, cy), (cx + sx * tk, cy)], fill=YELLOW, width=tw)
        d.line([(cx, cy), (cx, cy + sy * tk)], fill=YELLOW, width=tw)

    # Glow layer (blurred V behind the sharp V)
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.polygon(v_poly(s), fill=(245, 197, 24, 85))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(s * 0.022)))
    img  = Image.alpha_composite(img, glow)

    # Sharp V fill
    d2 = ImageDraw.Draw(img)
    poly = v_poly(s)
    d2.polygon(poly, fill=YELLOW)

    # Metallic top-edge shine on both arms
    sw = max(2, int(s * 0.004))
    d2.line([poly[0], poly[1]], fill=SHINE, width=sw)
    d2.line([poly[5], poly[6]], fill=SHINE, width=sw)

    return img


# ── ICO writer — stores every size as lossless PNG ───────────────────────────
def write_ico(images: dict, path: str):
    """
    images: {size_int: PIL.Image (RGBA)}
    Stores every entry as PNG inside the ICO container.
    """
    sizes   = sorted(images.keys())
    n       = len(sizes)
    png_bufs = []
    for sz in sizes:
        buf = io.BytesIO()
        images[sz].save(buf, format="PNG", compress_level=6)
        png_bufs.append(buf.getvalue())

    header_sz = 6
    dir_sz    = 16 * n
    offset    = header_sz + dir_sz

    with open(path, "wb") as f:
        # ICO file header: reserved=0, type=1 (icon), count
        f.write(struct.pack("<HHH", 0, 1, n))

        # Directory entries
        for i, sz in enumerate(sizes):
            w = sz if sz < 256 else 0   # 0 means 256 in ICO spec
            h = sz if sz < 256 else 0
            data_size = len(png_bufs[i])
            # ICONDIRENTRY: width, height, colorCount, reserved,
            #               planes, bitCount, bytesInRes, imageOffset
            f.write(struct.pack("<BBBBHHII",
                                w, h, 0, 0, 1, 32, data_size, offset))
            offset += data_size

        # PNG image data
        for buf in png_bufs:
            f.write(buf)


# ── Entry point ───────────────────────────────────────────────────────────────
def make_ico(path: str):
    master = draw_master(1024)
    sizes  = [16, 24, 32, 48, 64, 128, 256]
    images = {}
    for sz in sizes:
        images[sz] = master.resize((sz, sz), Image.LANCZOS).convert("RGBA")
    write_ico(images, path)
    print(f"Icon written -> {path}  ({len(sizes)} sizes, all PNG-stored)")


def make_logo_hd(path: str, size: int = 512):
    """Save a standalone HD PNG for use as the in-app logo."""
    master = draw_master(size)
    master.save(path, format="PNG", compress_level=6)
    print(f"HD logo written -> {path}  ({size}×{size} PNG)")


if __name__ == "__main__":
    assets = os.path.dirname(os.path.abspath(__file__))
    make_ico(os.path.join(assets, "icon.ico"))
    make_logo_hd(os.path.join(assets, "logo_hd.png"), size=512)
