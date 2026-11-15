"""Build the Capy Plus sheet: original 9 rows (+dust on run rows), then
   smiling, crying, thinking, dancing, tinkering, juggling, munching, bird, onsen, sign, laptop,
   then the one-shot costume intros (*-hat, bird-in, yawn), then the desktop pointer rows
   (poked, held, falling, landing; top hat), then `waking` (poked mid-nap; yuzu). Order = pet.json stateRows.

   Every frame wears a tiny top hat (the body is shrunk a little to make headroom);
   pass --no-hat for the bare capybara. --season winter|halloween|summer swaps the default top
   hat (and its `top-hat` intro) for a seasonal one; capy_install points pet.json at that sheet.

   Usage (from the repo root):
     uv run --with pillow python tools/make_capy_plus.py tools/source/cache-capy.webp pet [--no-hat] [--season NAME]
   Writes OUT_DIR/spritesheet.webp (or spritesheet-NAME.webp); pet.json is hand-maintained."""
import functools, math, sys
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

W, H = 192, 208
argv = sys.argv[1:]
SEASON = argv.pop(argv.index("--season") + 1) if "--season" in argv else None
args = [a for a in argv if not a.startswith("--")]
HAT = "--no-hat" not in sys.argv
src = Image.open(args[0]).convert("RGBA")
out_dir = Path(args[1]); out_dir.mkdir(parents=True, exist_ok=True)


def cell(r, c):
    return src.crop((c * W, r * H, c * W + W, r * H + H))


def blank(im):
    return im.getchannel("A").getbbox() is None


def count(r):
    n = 0
    for c in range(8):
        if blank(cell(r, c)):
            break
        n += 1
    return n


def xform(im, dx=0.0, dy=0.0, sx=1.0, sy=1.0, rot=0.0):
    """Squash/stretch + rotate about bottom-centre, then shift."""
    cx, by = W / 2, H - 6
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    w, h = max(1, round(W * sx)), max(1, round(H * sy))
    s = im.resize((w, h), Image.BICUBIC)
    layer.alpha_composite(s, (round(cx - w / 2), round(by - h * (by / H))) if False else (round(cx - w / 2), round(by - (by / H) * h)))
    if rot:
        layer = layer.rotate(rot, resample=Image.BICUBIC, center=(cx, by))
    res = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    res.alpha_composite(layer, (round(dx), round(dy)))
    return res


SKIN = (222, 160, 92, 255)
INK = (28, 18, 14, 255)


def aa(draw_fn, scale=4):
    """Draw on a supersampled layer and downsample for smooth strokes."""
    big = Image.new("RGBA", (W * scale, H * scale), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(big), scale)
    return big.resize((W, H), Image.LANCZOS)


def star(d, x, y, r, col, s):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.3
        pts.append(((x + rr * math.cos(a)) * s, (y + rr * math.sin(a)) * s))
    d.polygon(pts, fill=col)


def heart(d, x, y, r, col, s):
    x, y, r = x * s, y * s, r * s
    d.ellipse([x - r, y - r * 0.9, x, y + r * 0.1], fill=col)
    d.ellipse([x, y - r * 0.9, x + r, y + r * 0.1], fill=col)
    d.polygon([(x - r, y - r * 0.3), (x + r, y - r * 0.3), (x, y + r * 1.0)], fill=col)


def zee(d, x, y, sz, col, s, outline=(40, 40, 70, 255)):
    x, y, sz = x * s, y * s, sz * s
    pts = [(x, y), (x + sz, y), (x, y + sz), (x + sz, y + sz)]
    for w, c in ((sz * 0.42, outline), (sz * 0.22, col)):
        d.line(pts, fill=c, width=int(w), joint="curve")
        for p in pts:
            d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=c)


# ---------------------------------------------------------------- run: dust
def fur(p):
    """Warm fur pixel: opaque, r>120, r>=g>=b, not near-white (outlines/eyes/highlights stay put)."""
    return p[3] > 200 and p[0] > 120 and p[0] >= p[1] >= p[2] and p[0] - p[2] > 40


@functools.cache
def fur_stats(r):
    px = [p for c in range(count(r)) for p in cell(r, c).getdata() if fur(p)]
    mean = [sum(p[k] for p in px) / len(px) for k in range(3)]
    return mean, [max(1.0, (sum((p[k] - mean[k]) ** 2 for p in px) / len(px)) ** 0.5) for k in range(3)]


def tone_match(im, r):
    """The source's run rows 1-2 have oranger fur than every other row: map their fur's per-channel mean/std onto row 0's."""
    (ms, ss), (mt, st) = fur_stats(r), fur_stats(0)
    lut = lambda k, v: max(0, min(255, round(mt[k] + (v - ms[k]) * st[k] / ss[k])))
    im.putdata([tuple(lut(k, p[k]) for k in range(3)) + (p[3],) if fur(p) else p for p in getattr(im, "get_flattened_data", im.getdata)()])
    return im


def _blobs(im, test, box):
    """4-connected components of pixels passing test(p) inside box → list of pixel lists."""
    px, seen, out = im.load(), set(), []
    x0, y0, x1, y1 = box
    for sy in range(y0, y1):
        for sx in range(x0, x1):
            if (sx, sy) in seen or not test(px[sx, sy]):
                continue
            comp, todo = [], [(sx, sy)]
            seen.add((sx, sy))
            while todo:
                x, y = todo.pop()
                comp.append((x, y))
                for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if x0 <= q[0] < x1 and y0 <= q[1] < y1 and q not in seen and test(px[q]):
                        seen.add(q)
                        todo.append(q)
            out.append(comp)
    return out


def _ring(im, comp):
    """The 4-neighbours just outside a component."""
    s, px = set(comp), im.load()
    return [px[q] for x, y in comp for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            if q not in s and 0 <= q[0] < W and 0 <= q[1] < H]


DARK = lambda p: p[3] > 200 and sum(p[:3]) < 250
SPOT = lambda p: p[3] > 200 and sum(p[:3]) >= 250 and p[0] < 200  # darker-brown fur marks (spots, muzzle)


def eye_centre(im):
    """Centre of the eye: the biggest dark blob inside the head that sits in light fur (not the outline or the nose)."""
    best = None
    for comp in _blobs(im, DARK, (0, 30, W, 110)):
        ring = _ring(im, comp)
        xs, ys = [x for x, _ in comp], [y for _, y in comp]
        if max(xs) - min(xs) < 12 or any(p[3] < 128 for p in ring) or sum(p[0] >= 200 for p in ring) < 0.05 * len(ring):  # the nose sits in the darker muzzle
            continue
        if best is None or len(comp) > len(best):
            best = comp
    assert best, "no eye found"
    return (min(x for x, _ in best) + max(x for x, _ in best)) // 2, (min(y for _, y in best) + max(y for _, y in best)) // 2  # ints: no rounding gaps


@functools.cache
def cheek_spots():
    """Idle frame 0's cheek spots (the diamond cluster below-behind the eye) as [(dx, dy, rgba)] from its eye centre."""
    im = cell(0, 0)
    ex, ey = eye_centre(im)
    box = (ex - 40, ey + 4, ex + 2, ey + 42)
    px = im.load()
    spots = [(x - ex, y - ey, px[x, y]) for comp in _blobs(im, SPOT, box) if len(comp) >= 20
             and all(p[3] > 200 and sum(p[:3]) >= 250 for p in _ring(im, comp)) for x, y in comp]
    assert len(spots) > 150, len(spots)
    return spots


def add_cheek_spots(im, facing):
    """Stamp idle's cheek spots behind the eye of a side-view run frame (mirrored when facing left), on light fur only."""
    ex, ey = eye_centre(im)
    px = im.load()
    for dx, dy, col in cheek_spots():
        x, y = ex + dx * facing, ey + dy
        p = px[x, y]
        if p[3] > 200 and p[0] >= 200 and fur(p):
            px[x, y] = col
    return im


def with_dust(r, facing):
    n = count(r)
    frames = []
    for i in range(n):
        spr = add_cheek_spots(tone_match(cell(r, i), r), facing) if r in (1, 2) else cell(r, i)
        bb = spr.getchannel("A").getbbox() or (60, 0, 130, 200)
        back = bb[0] + 8 if facing > 0 else bb[2] - 8

        def draw(d, s, i=i, back=back):
            for k in range(3):
                age = ((i / n) + k / 3) % 1
                cx = back - facing * (2 + age * 22)
                cy = 196 - age * 14
                rad = 7 + age * 11
                a = int(235 * (1 - age) ** 1.1)
                d.ellipse([(cx - rad) * s, (cy - rad) * s, (cx + rad) * s, (cy + rad) * s],
                          fill=(245, 232, 208, a), outline=(200, 170, 130, a // 2))
            for k in range(2):  # speed streaks
                y = 70 + k * 38 + (i * 7 % 11)
                x0 = back - facing * 6
                d.line([(x0 * s, y * s), ((x0 - facing * (26 + 10 * k)) * s, y * s)],
                       fill=(255, 255, 255, 110), width=2 * s)

        frames.append((aa(draw), spr, None))
    return frames


# ------------------------------------------------------------------- smile
def smile_face(base, bounce_t):
    def draw(d, s):
        # happy ^ ^ eyes over the originals
        for ex in (65, 129):
            d.ellipse([(ex - 11) * s, (47 - 11) * s, (ex + 11) * s, (47 + 11) * s], fill=SKIN)
            d.arc([(ex - 9) * s, (47 - 6) * s, (ex + 9) * s, (47 + 12) * s], 200, 340, fill=INK, width=int(3.2 * s))
        # rosy cheeks
        for cx in (50, 142):
            d.ellipse([(cx - 11) * s, 62 * s, (cx + 11) * s, 74 * s], fill=(236, 110, 100, 120))
        # big smile under the nose-Y
        d.arc([80 * s, 76 * s, 112 * s, 98 * s], 15, 165, fill=INK, width=int(3 * s))
    face = aa(draw)
    face_base = base.copy()
    face_base.alpha_composite(face)
    return face_base


def smiling():
    base = cell(9, 0)
    n = 6
    frames = []
    for i in range(n):
        t = i / n
        hop = abs(math.sin(math.pi * t * 2))  # two bounces per loop
        squash = 1 - 0.05 * (1 - hop)
        spr = xform(smile_face(base, t), dy=-12 * hop, sx=1 / squash ** 0.5, sy=squash,
                    rot=2.5 * math.sin(2 * math.pi * t))

        def draw(d, s, t=t):
            for k in range(4):
                age = (t + k / 4) % 1
                ang = k * math.pi / 2 + 0.6
                x = 96 + math.cos(ang) * (62 + age * 14)
                y = 70 + math.sin(ang) * (52 + age * 10) - age * 8
                a = int(255 * (1 - age ** 2))
                if k % 2 == 0:
                    star(d, x, y, 6 + 3 * (1 - age), (255, 236, 120, a), s)
                else:
                    heart(d, x, y, 5 + 2 * (1 - age), (255, 110, 140, a), s)
        frames.append((None, spr, aa(draw)))
    return frames


# ------------------------------------------------------------------ crying
def crying():
    base = cell(9, 0)
    n = 6
    frames = []
    for i in range(n):
        t = i / n
        wob = math.sin(2 * math.pi * t * 2)

        def face(d, s, t=t, wob=wob):
            for ex, dirn in ((65, 1), (129, -1)):
                d.ellipse([(ex - 11) * s, 36 * s, (ex + 11) * s, 58 * s], fill=SKIN)
                # squeezed ">" "<" eyes
                d.line([((ex - 7 * dirn) * s, 40 * s), ((ex + 6 * dirn) * s, 47 * s), ((ex - 7 * dirn) * s, 54 * s)],
                       fill=INK, width=int(3.2 * s), joint="curve")
            # wobbly open mouth
            mw = 7 + 2 * wob
            d.ellipse([(96 - mw) * s, 86 * s, (96 + mw) * s, (92 + 3 + wob * 1.5) * s], fill=INK)
            d.ellipse([(96 - mw * 0.55) * s, 91 * s, (96 + mw * 0.55) * s, (94 + wob) * s], fill=(200, 80, 80, 255))
            # tear streams + falling drops
            for ex, side in ((65, -1), (129, 1)):
                for k in range(2):
                    age = (t + k / 2) % 1
                    y = 52 + age * 120
                    x = ex + side * (4 + age * 9)
                    ln = 14 + 16 * (1 - age)
                    a = int(235 * (1 - age ** 3))
                    d.line([(ex * s + side * 4 * s, 56 * s), (x * s, y * s)], fill=(120, 200, 255, int(a * 0.8)), width=int(3 * s))
                    d.ellipse([(x - 3.5) * s, (y - 3.5) * s, (x + 3.5) * s, (y + 5) * s], fill=(150, 215, 255, a))
        shake = 2.2 * math.sin(2 * math.pi * t * 4)
        b2 = base.copy()
        b2.alpha_composite(aa(lambda d, s: face(d, s)))
        spr = xform(b2, dx=shake, sy=1 - 0.02 * (1 + wob), sx=1 + 0.01 * (1 + wob))
        frames.append((None, spr, None))
    return frames


# ------------------------------------------------- stationary activities
# Played while the agent works but the pet stays put (pet.json maps run/review here),
# so the running rows are only ever seen while it actually roams the window.
ORANGE = (247, 150, 40, 255)
LEAF = (90, 170, 70, 255)
NOTE = (60, 50, 120, 255)


def idle_base(i):
    n = count(0)
    return cell(0, i % n)


def note(d, x, y, sz, col, s, double=False):
    d.ellipse([(x - sz * 0.55) * s, (y - sz * 0.38) * s, (x + sz * 0.55) * s, (y + sz * 0.38) * s], fill=col)
    d.line([((x + sz * 0.45) * s, y * s), ((x + sz * 0.45) * s, (y - sz * 1.9) * s)], fill=col, width=int(2.4 * s))
    if double:
        x2 = x + sz * 1.5
        d.ellipse([(x2 - sz * 0.55) * s, (y - sz * 0.2 - sz * 0.38) * s, (x2 + sz * 0.55) * s, (y - sz * 0.2 + sz * 0.38) * s], fill=col)
        d.line([((x2 + sz * 0.45) * s, (y - sz * 0.2) * s), ((x2 + sz * 0.45) * s, (y - sz * 2.1) * s)], fill=col, width=int(2.4 * s))
        d.line([((x + sz * 0.45) * s, (y - sz * 1.9) * s), ((x2 + sz * 0.45) * s, (y - sz * 2.1) * s)], fill=col, width=int(4 * s))
    else:
        d.arc([((x + sz * 0.45) * s), (y - sz * 1.9) * s, (x + sz * 1.4) * s, (y - sz * 1.0) * s], 270, 90, fill=col, width=int(2.4 * s))


def gear(d, x, y, r, ang, col, s, teeth=8):
    pts = []
    for k in range(teeth * 2):
        a = ang + math.pi * k / teeth
        rr = r if k % 2 == 0 else r * 0.74
        for da in (-0.17, 0.17):
            pts.append(((x + rr * math.cos(a + da)) * s, (y + rr * math.sin(a + da)) * s))
    d.polygon(pts, fill=col, outline=INK, width=int(1.6 * s))
    d.ellipse([(x - r * 0.3) * s, (y - r * 0.3) * s, (x + r * 0.3) * s, (y + r * 0.3) * s], fill=(255, 250, 240, 255), outline=INK, width=int(1.4 * s))


def _font(px):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=px)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


# Coordinates below are in the FINAL frame: effects are not shrunk with the body
# (body ≈ x 29..163, head/hat on the right ≈ x 115..160, free space top-left).
def thinking():
    frames = []
    for i in range(6):
        t = i / 6
        spr = xform(idle_base(i), rot=4 * math.sin(2 * math.pi * t), dx=1.5 * math.sin(2 * math.pi * t))

        def draw(d, s, i=i, t=t):
            bob = 2 * math.sin(2 * math.pi * t)
            for x, y, r in ((106, 58, 4), (92, 50, 6)):
                d.ellipse([(x - r) * s, (y - r + bob) * s, (x + r) * s, (y + r + bob) * s], fill=(255, 255, 255, 255), outline=INK, width=int(2 * s))
            cx, cy = 50, 30 + bob
            puffs = ((-22, 4, 14), (-6, -6, 17), (14, -4, 15), (26, 6, 12), (4, 12, 15), (-16, 14, 12))
            for ox, oy, rr in puffs:
                d.ellipse([(cx + ox - rr) * s, (cy + oy - rr) * s, (cx + ox + rr) * s, (cy + oy + rr) * s], fill=INK)
            for ox, oy, rr in puffs:
                rr -= 2.2
                d.ellipse([(cx + ox - rr) * s, (cy + oy - rr) * s, (cx + ox + rr) * s, (cy + oy + rr) * s], fill=(255, 255, 255, 255))
            glyph = ["?", "?", "?!", "…", "?", "!"][i]
            f = _font(int(24 * s))
            w = d.textlength(glyph, font=f)
            d.text((cx * s - w / 2, (cy - 15) * s), glyph, fill=INK, font=f)
        frames.append((None, spr, aa(draw)))
    return frames


def dancing():
    frames = []
    cols = [(120, 70, 200, 255), (230, 70, 120, 255), (40, 150, 200, 255)]
    for i in range(6):
        t = i / 6
        sway = math.sin(2 * math.pi * t)
        hop = abs(math.sin(2 * math.pi * t))
        spr = xform(idle_base(i), rot=12 * sway, dx=6 * sway, dy=-10 * hop, sx=1 + 0.04 * (1 - hop), sy=1 - 0.05 * (1 - hop))

        def draw(d, s, t=t):
            for k in range(4):
                age = (t + k / 4) % 1
                side = -1 if k % 2 else 1
                x = 96 + side * (70 + age * 10) - (10 if side > 0 else -6)
                y = 110 - age * 92
                a = int(255 * min(1, (1 - age) * 2.2))
                c = cols[k % 3]
                note(d, x, y, 10, c[:3] + (a,), s, double=(k % 2 == 1))
            for k in range(5):
                x = 22 + k * 37
                tw = abs(math.sin(2 * math.pi * (t + k / 5)))
                star(d, x, 198, 4 + 4 * tw, (255, 205, 60, int(120 + 135 * tw)), s)
        frames.append((None, spr, aa(draw)))
    return frames


def tinkering():
    frames = []
    for i in range(6):
        t = i / 6
        spr = xform(idle_base(i), rot=-2 + 2 * math.sin(4 * math.pi * t))

        def draw(d, s, t=t, i=i):
            a = 2 * math.pi * t / 4
            gear(d, 34, 66, 22, a, (180, 186, 200, 255), s, teeth=9)
            gear(d, 66, 36, 14, -a * 22 / 14 + 0.25, (226, 178, 74, 255), s, teeth=6)
            if i % 2 == 0:
                for k in range(5):
                    ang = math.pi * (0.1 + k * 0.2) + t
                    x0, y0 = 52, 86
                    d.line([(x0 * s, y0 * s), ((x0 + 16 * math.cos(ang)) * s, (y0 + 16 * math.sin(ang)) * s)], fill=(255, 196, 40, 255), width=int(3 * s))
            dy = 3 * (i % 3)
            d.ellipse([164 * s, (52 + dy) * s, 173 * s, (64 + dy) * s], fill=(150, 215, 255, 255), outline=(50, 110, 170, 255), width=int(1.6 * s))
        frames.append((None, spr, aa(draw)))
    return frames


def juggling():
    frames = []
    for i in range(6):
        t = i / 6
        spr = xform(idle_base(i), dy=1.5 * math.sin(4 * math.pi * t))

        def draw(d, s, t=t):
            for k in range(3):
                ph = (t + k / 3) % 1
                x = 30 + 20 * math.cos(2 * math.pi * ph)
                y = 48 - 34 * math.sin(2 * math.pi * ph)
                r = 11
                d.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s], fill=ORANGE, outline=INK, width=int(2.2 * s))
                d.ellipse([(x - 4) * s, (y - 5) * s, (x - 0.5) * s, (y - 1.5) * s], fill=(255, 210, 140, 255))
                d.ellipse([(x - 1) * s, (y - r - 4) * s, (x + 6) * s, (y - r + 1.5) * s], fill=LEAF, outline=INK, width=int(1 * s))
        frames.append((None, spr, aa(draw)))
    return frames


# -------------------------------------------------------- idle variants
GRASS = (104, 182, 70, 255)
BIRD, BIRD_DK, BELLY = (104, 168, 236, 255), (60, 110, 190, 255), (255, 242, 214, 255)


def drawn(base, fn):
    """A source frame with fn painted on (source coords, shrunk with the body)."""
    out = base.copy()
    out.alpha_composite(aa(fn))
    return out


def blade(d, x, y, ln, ang, s, w=2.4):
    """Tapered grass blade from (x, y); ang in degrees (0 = right, 90 = down)."""
    a = math.radians(ang)
    px, py = -math.sin(a) * w, math.cos(a) * w
    d.polygon([((x + px) * s, (y + py) * s), ((x + ln * math.cos(a)) * s, (y + ln * math.sin(a)) * s), ((x - px) * s, (y - py) * s)],
              fill=GRASS, outline=INK, width=int(1.2 * s))


def munching():
    frames = []
    for i in range(8):
        t = i / 8
        chew = 0.5 - 0.5 * math.cos(2 * math.pi * t)  # one slow chew per loop

        def face(d, s, t=t, chew=chew):
            d.ellipse([86 * s, 56 * s, 108 * s, 78 * s], fill=SKIN)  # happy ^ squint over the eye
            d.arc([87 * s, 63 * s, 105 * s, 81 * s], 200, 340, fill=INK, width=int(3.4 * s))
            d.ellipse([88 * s, 81 * s, 110 * s, 91 * s], fill=(236, 110, 100, 120))
            for k, (ang, ln) in enumerate(((8, 36), (34, 32), (-18, 26), (58, 26))):  # tuft in the mouth
                blade(d, 148, 90 + 3 * chew, ln * (1 - 0.15 * chew), ang + 9 * math.sin(2 * math.pi * t + k), s, 3.2)
        spr = xform(drawn(cell(0, 0), face), sy=1 - 0.018 * chew, rot=1.2 * chew)

        def tuft(d, s, t=t):
            for k in range(5):
                blade(d, 160 + 4 * k, 201, 14 + 6 * (k % 2), -120 + 15 * k + 6 * math.sin(2 * math.pi * t + k), s, 2.8)
        frames.append((None, spr, aa(tuft)))
    return frames


def birdie(d, s, x, y, tilt=0.0, beak=0.0, wing=0, sq=1.0, z=0.92):
    """Little bird standing at (x, y), facing right. wing: 0 folded, 1 up, -1 down."""
    P = lambda *pts: [((x + px * z) * s, (y + py * z) * s) for px, py in pts]
    E = lambda cx, cy, rx, ry: [(x + (cx - rx) * z) * s, (y + (cy - ry) * z) * s, (x + (cx + rx) * z) * s, (y + (cy + ry) * z) * s]
    o, by = int(1.4 * s), -2 - 6 * sq
    for lx in (-2, 2):
        d.line(P((lx, by + 4), (lx, 0)), fill=ORANGE, width=int(1.6 * s))
    d.polygon(P((-5, by), (-13, by - 5), (-12, by + 2)), fill=BIRD_DK, outline=INK, width=o)
    d.ellipse(E(0, by, 8, 6 * sq), fill=BIRD, outline=INK, width=o)
    d.ellipse(E(2.5, by + 2, 4, 3 * sq), fill=BELLY)
    hx, hy, a = 4, by - 6 * sq, math.radians(-tilt)
    for k, sign_ in ((1, -1), (-1, 1)):  # beak halves part when chirping
        b = a + sign_ * 0.35 * beak
        d.polygon(P((hx + 4 * math.cos(a - 0.5 * k), hy + 4 * math.sin(a - 0.5 * k)), (hx + 9 * math.cos(b), hy + 9 * math.sin(b)), (hx + 4 * math.cos(a), hy + 4 * math.sin(a))),
                  fill=ORANGE, outline=INK, width=int(1 * s))
    d.ellipse(E(hx, hy, 5, 5), fill=BIRD, outline=INK, width=o)
    ex, ey = hx + 2 * math.cos(a - 0.9), hy + 2 * math.sin(a - 0.9)
    d.ellipse(E(ex, ey, 1.2, 1.2), fill=INK)
    if wing:
        d.polygon(P((-4, by - 1), (3, by - 1), (-7, by - 11 * wing)), fill=BIRD_DK, outline=INK, width=o)
    else:
        d.ellipse(E(-2, by, 5, 3.2), fill=BIRD_DK, outline=INK, width=int(1 * s))


def bird():
    frames = []
    plan = [(0, 0, 0, 1), (16, 0, 0, 1), (16, 0, 0, 1), (-8, 1, 0, 1), (0, 0, 2, 1), (0, 0, 0, 0.82)]  # tilt, beak, hop, squash
    # the hat top sits ~22 px under the frame edge, so the bird is small and the hop is short
    for i, (tilt, beak, hop, sq) in enumerate(plan):
        body = idle_base(i)
        x, y = hat_tip(shrink(body))

        def draw(d, s, i=i, x=x, y=y, tilt=tilt, beak=beak, hop=hop, sq=sq):
            birdie(d, s, x, y + 1.5 - hop, tilt, beak, wing=1 if hop else 0, sq=sq)
            if i in (3, 4):
                note(d, x + 18 + 4 * (i - 3), y + 2 - 4 * (i - 3), 6, NOTE[:3] + (255 if i == 3 else 130,), s)
        frames.append((None, body, aa(draw)))
    return frames


def bird_in():
    """Costume intro for `bird`: it flaps in from the top-left and lands on the top hat."""
    frames = []
    for i, wing in enumerate((1, -1, 1, -1, 1, 0)):
        body = idle_base(i)
        x, y = hat_tip(shrink(body))
        e = 1 - (1 - min(1, i / 4)) ** 2
        bx, by = 34 + (x - 34) * e, 48 + (y + 1.5 - 48) * e - 6 * math.sin(math.pi * e)

        def draw(d, s, i=i, bx=bx, by=by, wing=wing):
            birdie(d, s, bx, by, tilt=10 if i < 4 else 0, wing=wing, sq=0.8 if i == 4 else 1)
            for k in range(2 if i < 4 else 0):  # speed lines
                d.line([(bx - 16) * s, (by - 9 + 5 * k) * s, (bx - 24) * s, (by - 7 + 5 * k) * s], fill=(255, 255, 255, 220), width=int(2 * s))
        frames.append(dress((None, body, aa(draw)), "top", i))
    return frames


# ---------------------------------------------------------------- sleep
WOOD, WOOD_DK, WATER = (206, 144, 82, 255), (150, 96, 52, 255), (150, 214, 236, 255)


TUB_X0, TUB_X1, TUB_YC = 24, 168, 150
TUB_BLUSH = lambda d, s: [d.ellipse([(cx - 10) * s, 96 * s, (cx + 10) * s, 106 * s], fill=(236, 110, 100, 120)) for cx in (60, 132)]


def onsen():
    """Dozing up to the chest in a round wooden hot-spring tub, a yuzu on its head."""
    base = drawn(cell(10, 0), TUB_BLUSH)
    frames = []
    for i in range(6):
        t = i / 6
        spr = xform(base, dy=4 + 1.6 * math.sin(2 * math.pi * t), rot=1.4 * math.sin(2 * math.pi * t + 1))
        frames.append((None, spr, tub(spr, t)))
    return frames


def tub(spr, t, zees=True):
    """The tub around source-scale body `spr`: back rim + water (only around the body), front, ripple, steam (+ z's)."""
    x0, x1, yc = TUB_X0, TUB_X1, TUB_YC
    rim = lambda d, s, inset, half=False, **kw: (d.chord if half else d.ellipse)(
        [(x0 + inset) * s, (yc - 10 + inset * 0.6) * s, (x1 - inset) * s, (yc + 10 - inset * 0.6) * s], *((0, 180) if half else ()), **kw)

    def back(d, s):
        rim(d, s, 0, fill=WOOD, outline=INK, width=_o(s))
        rim(d, s, 7, fill=(110, 180, 210, 255))
    layer = aa(back)  # back rim + water show only around the body
    layer.putalpha(ImageChops.darker(layer.getchannel("A"), ImageChops.invert(shrink(spr).getchannel("A"))))

    def front(d, s, t=t):
        d.polygon([(x0 * s, yc * s), (x1 * s, yc * s), ((x1 - 8) * s, 204 * s), ((x0 + 8) * s, 204 * s)], fill=WOOD, outline=INK, width=_o(s))
        for k in range(1, 8):  # staves
            x = x0 + (x1 - x0) * k / 8
            d.line([(x * s, (yc + 8) * s), ((x + (96 - x) * 0.1) * s, 203 * s)], fill=WOOD_DK, width=int(1.6 * s))
        for y in (172, 194):  # hoops
            inset = 8 * (y - yc) / (204 - yc)
            d.line([((x0 + inset) * s, y * s), ((x1 - inset) * s, y * s)], fill=(70, 60, 70, 255), width=int(4 * s))
        rim(d, s, 0, True, fill=WOOD, outline=INK, width=_o(s))
        rim(d, s, 7, True, fill=WATER)
        w = 2 * math.sin(2 * math.pi * t)
        d.arc([(46 - w) * s, (yc - 5) * s, (146 + w) * s, (yc + 6) * s], 10, 170, fill=(255, 255, 255, 220), width=int(2.4 * s))
        for k, (sx, top) in enumerate(((32, 70), (160, 74), (178, 108))):  # steam wisps
            age = (t + k / 3) % 1
            pts = [((sx + 5 * math.sin(6 * (yy / 40) + 2 * math.pi * age + k)) * s, (yc - 10 - age * 22 - yy) * s) for yy in range(0, int(yc - top - 30), 3)]
            d.line(pts, fill=(255, 255, 255, int(200 * (1 - age))), width=int(3.2 * s), joint="curve")
        for k in range(3 if zees else 0):
            age = (t + k / 3) % 1
            a = int(255 * min(1, age * 5) * (1 - age ** 3))
            zee(d, 124 + age * 36 + 5 * math.sin(age * 6 + k), 56 - age * 46, 9 + age * 11, (235, 240, 255, a), s, outline=(50, 50, 90, a))
    layer.alpha_composite(aa(front))
    return layer


def yawn():
    """Costume intro for `onsen`: a big yawn + stretch in the top hat, then a POOF reveals the tub."""
    tub = dress(onsen()[0], "yuzu", 0)
    frames = []
    for i, o in enumerate((0, 0.45, 0.85, 1, 1, None, None, None)):
        def face(d, s, o=o):
            for ex, dirn in ((65, 1), (129, -1)):  # squeezed > < eyes
                d.ellipse([(ex - 11) * s, 36 * s, (ex + 11) * s, 58 * s], fill=SKIN)
                d.line([((ex - 7 * dirn) * s, 41 * s), ((ex + 6 * dirn) * s, 47 * s), ((ex - 7 * dirn) * s, 53 * s)], fill=INK, width=int(3.2 * s), joint="curve")
            rx, ry = 5 + 6 * o, 2 + 12 * o
            d.ellipse([(96 - rx) * s, (84 - ry) * s, (96 + rx) * s, (84 + ry) * s], fill=INK)
            d.ellipse([(96 - rx * 0.6) * s, (84 + ry * 0.2) * s, (96 + rx * 0.6) * s, (84 + ry * 0.85) * s], fill=(220, 90, 100, 255))
            if o >= 0.85:  # stretch ticks
                for side in (-1, 1):
                    for k in range(2):
                        x = 96 + side * (70 + 8 * k)
                        d.line([(x * s, (66 - 8 * k) * s), ((x + side * 8) * s, (58 - 8 * k) * s)], fill=INK, width=int(2.4 * s))
        if o is None:
            out = tub.copy()
        else:
            out = dress(xform(drawn(cell(9, 0), face) if o else cell(9, 0), sy=1 + 0.07 * o, sx=1 - 0.03 * o, rot=-3 * o), "top", i)
        pt = (None, None, None, None, 0.25, 0.5, 0.8, 1.0)[i]
        if pt:
            out.alpha_composite(poof(96, 132, pt, 1.9))
        frames.append(out)
    return frames


# --------------------------------------------------------- waiting / run
def sign():
    """Waiting for the user: holds up a bold "?" sign (reads at 0.45x)."""
    frames = []
    for i in range(6):
        t = i / 6
        lift = 5 * abs(math.sin(2 * math.pi * t))

        def board(d, s, lift=lift):
            d.line([(48 * s, 134 * s), (48 * s, (80 - lift) * s)], fill=INK, width=int(7 * s))
            d.line([(48 * s, 133 * s), (48 * s, (80 - lift) * s)], fill=WOOD, width=int(3.6 * s))
            d.rounded_rectangle([16 * s, (26 - lift) * s, 84 * s, (86 - lift) * s], radius=7 * s, fill=(255, 248, 226, 255), outline=INK, width=int(3 * s))
            f = _font(int(52 * s))
            l, tp, r, b = d.textbbox((0, 0), "?", font=f, stroke_width=int(2 * s))
            d.text((50 * s - (l + r) / 2, (56 - lift) * s - (tp + b) / 2), "?", font=f, fill=(222, 56, 48, 255), stroke_width=int(2 * s), stroke_fill=(222, 56, 48, 255))
            d.ellipse([40 * s, (122 - lift / 2) * s, 56 * s, (134 - lift / 2) * s], fill=SKIN, outline=INK, width=int(2.2 * s))  # paw
        frames.append((None, idle_base(i), aa(board).rotate(4 * math.sin(2 * math.pi * t), resample=Image.BICUBIC, center=(48, 134))))
    return frames


def laptop():
    """Typing on a tiny laptop: screen glow, paws tapping, code bits floating up."""
    frames = []
    for i in range(6):
        t = i / 6
        spr = xform(idle_base(i), rot=1.5 * math.sin(4 * math.pi * t))

        def draw(d, s, i=i, t=t):
            for a in (-130, -105, -75, -50):  # screen glow rays over the lid
                r, l = math.radians(a), 12 + 4 * ((i + a // 25) % 2)
                d.line([((127 + 34 * math.cos(r)) * s, (126 + 12 * math.sin(r)) * s), ((127 + (34 + l) * math.cos(r)) * s, (126 + (12 + l) * math.sin(r)) * s)],
                       fill=(120, 220, 255, 230), width=int(2.4 * s))
            d.rounded_rectangle([92 * s, 118 * s, 162 * s, 164 * s], radius=5 * s, fill=(178, 186, 200, 255), outline=INK, width=_o(s))
            d.line([(97 * s, 120.5 * s), (157 * s, 120.5 * s)], fill=(150, 236, 255, 255), width=int(2 * s))
            d.ellipse([121 * s, 134 * s, 133 * s, 146 * s], fill=ORANGE, outline=INK, width=int(1.4 * s))  # logo
            d.ellipse([127 * s, 129 * s, 134 * s, 134 * s], fill=LEAF)
            d.polygon([(86 * s, 164 * s), (168 * s, 164 * s), (176 * s, 175 * s), (78 * s, 175 * s)], fill=(208, 214, 226, 255), outline=INK, width=int(2 * s))
            for k, px in enumerate((104, 148)):
                up = 5 * ((i + k) % 2)
                d.ellipse([(px - 8) * s, (161 - up) * s, (px + 8) * s, (171 - up) * s], fill=SKIN, outline=INK, width=int(2 * s))
                if not up:  # clack!
                    for a in (-150, -110, -70, -30):
                        r = math.radians(a)
                        d.line([((px + 11 * math.cos(r)) * s, (163 + 11 * math.sin(r)) * s), ((px + 17 * math.cos(r)) * s, (163 + 17 * math.sin(r)) * s)], fill=INK, width=int(2 * s))
            f = _font(int(13 * s))
            for k, g in enumerate(("</>", "{ }", "01", "=>")):
                age = (t + k / 4) % 1
                d.text(((22 + 14 * (k % 2)) * s, (118 - age * 78) * s), g, font=f, fill=(40, 120, 200, int(255 * min(1, (1 - age) * 2.5))), stroke_width=int(0.6 * s), stroke_fill=(40, 120, 200, int(255 * min(1, (1 - age) * 2.5))))
        frames.append((None, spr, aa(draw)))
    return frames


# ------------------------------------------------------------------- hat
SHRINK = 0.8 if HAT else 1.0  # headroom for the hat; everything shares one transform
HAT_INK = (34, 22, 18, 255)
HAT_FELT = (58, 52, 70, 255)
HAT_SHINE = (98, 92, 116, 255)
HAT_BAND = (208, 70, 60, 255)
HAT_TILT = -12  # degrees, jaunty


def shrink(im):
    return xform(im, sx=SHRINK, sy=SHRINK) if im is not None and SHRINK != 1.0 else im


def head_anchor(body):
    """(centre x, crown y, head width) from the top of the body's opaque silhouette."""
    alpha = body.getchannel("A")
    bb = alpha.getbbox()
    if not bb:
        return W / 2, H / 3, 80
    top = bb[1]
    px = alpha.load()
    band = range(top, min(H, top + int(22 * SHRINK)))
    cols = [x for x in range(bb[0], bb[2]) if any(px[x, y] > 128 for y in band)]
    x0, x1 = (cols[0], cols[-1]) if cols else (bb[0], bb[2])
    return (x0 + x1) / 2, top, x1 - x0


# One hat per mood. Each draws in local coords around (cx, base) = brim centre;
# the layer is then rotated by HAT_TILT about that point. `i` = frame index.
def _o(s):
    return int(2.6 * s)


def hat_top(d, s, cx, base, brim, i):
    crown_w, crown_h = brim * 0.64, brim * 0.62
    cl, cr, ct = (cx - crown_w / 2) * s, (cx + crown_w / 2) * s, (base - crown_h) * s
    d.rounded_rectangle([cl, ct, cr, base * s], radius=3 * s, fill=HAT_FELT, outline=HAT_INK, width=_o(s))
    d.rectangle([cl + _o(s), (base - crown_h * 0.34) * s, cr - _o(s), (base - crown_h * 0.12) * s], fill=HAT_BAND)
    d.rectangle([cl + 3.2 * s, ct + 4 * s, cl + 6.6 * s, (base - crown_h * 0.42) * s], fill=HAT_SHINE)
    d.rounded_rectangle([(cx - brim / 2) * s, (base - 3) * s, (cx + brim / 2) * s, (base + 4) * s],
                        radius=3.5 * s, fill=HAT_FELT, outline=HAT_INK, width=_o(s))


def hat_party(d, s, cx, base, brim, i):
    w, h = brim * 0.62, brim * 1.0
    tip = (cx, base - h)
    d.polygon([((cx - w / 2) * s, base * s), ((cx + w / 2) * s, base * s), (tip[0] * s, tip[1] * s)], fill=(236, 92, 150, 255), outline=HAT_INK, width=_o(s))
    for k, f in enumerate((0.25, 0.5, 0.75)):  # stripes
        y = base - h * f
        half = w / 2 * (1 - f)
        d.line([((cx - half + 1) * s, (y + 2) * s), ((cx + half - 1) * s, (y - 2) * s)], fill=(255, 226, 90, 255), width=int(3.4 * s))
    for k in range(3):  # confetti dots
        x, y = cx - w * 0.15 + k * w * 0.15, base - h * (0.12 + 0.3 * k)
        d.ellipse([(x - 1.6) * s, (y - 1.6) * s, (x + 1.6) * s, (y + 1.6) * s], fill=(90, 200, 240, 255))
    r = 5.5
    d.ellipse([(tip[0] - r) * s, (tip[1] - r) * s, (tip[0] + r) * s, (tip[1] + r) * s], fill=(255, 236, 120, 255), outline=HAT_INK, width=int(2 * s))
    d.rounded_rectangle([(cx - w / 2 - 2) * s, (base - 3) * s, (cx + w / 2 + 2) * s, (base + 3) * s], radius=3 * s, fill=(255, 255, 255, 255), outline=HAT_INK, width=int(2 * s))


def hat_umbrella(d, s, cx, base, brim, i):
    R = brim * 0.85
    top = base - brim * 0.95
    d.line([(cx * s, top * s), (cx * s, (base - 1) * s)], fill=HAT_INK, width=int(3 * s))
    box = [(cx - R) * s, (top - R * 0.55) * s, (cx + R) * s, (top + R * 0.55) * s]
    d.pieslice(box, 180, 360, fill=(226, 60, 60, 255), outline=HAT_INK, width=_o(s))
    for k in (1, 3):
        a0, a1 = 180 + k * 45, 180 + (k + 1) * 45
        d.pieslice(box, a0, a1, fill=(255, 250, 245, 255), outline=HAT_INK, width=int(2 * s))
    d.ellipse([(cx - 3) * s, (top - R * 0.55 - 5) * s, (cx + 3) * s, (top - R * 0.55 + 1) * s], fill=HAT_INK)
    d.rounded_rectangle([(cx - brim * 0.3) * s, (base - 3) * s, (cx + brim * 0.3) * s, (base + 3) * s], radius=3 * s, fill=(90, 90, 100, 255), outline=HAT_INK, width=int(2 * s))
    for k in range(2):  # drips off the rim
        x = cx + (-1 if k else 1) * R * 0.95
        y = top + 6 + ((i * 4 + k * 9) % 14)
        d.ellipse([(x - 2.4) * s, (y - 2.4) * s, (x + 2.4) * s, (y + 3.4) * s], fill=(150, 215, 255, 255))


def hat_mortarboard(d, s, cx, base, brim, i):
    cw, ch = brim * 0.58, brim * 0.3
    d.rounded_rectangle([(cx - cw / 2) * s, (base - ch) * s, (cx + cw / 2) * s, base * s], radius=3 * s, fill=(36, 36, 44, 255), outline=HAT_INK, width=_o(s))
    y = base - ch
    bw, bh = brim * 0.62, brim * 0.17
    d.polygon([((cx - bw) * s, y * s), (cx * s, (y - bh) * s), ((cx + bw) * s, y * s), (cx * s, (y + bh) * s)], fill=(48, 48, 58, 255), outline=HAT_INK, width=_o(s))
    sway = 2.5 * math.sin(2 * math.pi * i / 6)
    tx, ty = cx + bw * 0.8, y + 2
    d.line([(cx * s, y * s), (tx * s, ty * s), ((tx + sway) * s, (ty + 14) * s)], fill=(250, 200, 60, 255), width=int(2.6 * s))
    d.rounded_rectangle([(tx + sway - 3) * s, (ty + 12) * s, (tx + sway + 3) * s, (ty + 21) * s], radius=2 * s, fill=(250, 200, 60, 255), outline=HAT_INK, width=int(1.4 * s))
    d.ellipse([(cx - 2.5) * s, (y - 2.5) * s, (cx + 2.5) * s, (y + 2.5) * s], fill=(250, 200, 60, 255))


def hat_hard(d, s, cx, base, brim, i):
    R = brim * 0.42
    d.pieslice([(cx - R) * s, (base - R * 1.5) * s, (cx + R) * s, (base + R * 0.5) * s], 180, 360, fill=(255, 202, 40, 255), outline=HAT_INK, width=_o(s))
    d.line([(cx * s, (base - R * 0.95) * s), (cx * s, (base - 2) * s)], fill=(222, 160, 20, 255), width=int(5 * s))
    d.arc([(cx - R * 0.7) * s, (base - R * 1.3) * s, (cx - R * 0.1) * s, (base - R * 0.3) * s], 200, 260, fill=(255, 245, 190, 255), width=int(2.6 * s))
    d.rounded_rectangle([(cx - brim * 0.55) * s, (base - 3.5) * s, (cx + brim * 0.6) * s, (base + 3.5) * s], radius=3.5 * s, fill=(255, 202, 40, 255), outline=HAT_INK, width=_o(s))


def hat_cowboy(d, s, cx, base, brim, i):
    bw = brim * 0.78
    d.chord([(cx - bw) * s, (base - 12) * s, (cx + bw) * s, (base + 7) * s], 0, 180, fill=(84, 48, 28, 255), outline=HAT_INK, width=_o(s))
    cw, ch = brim * 0.48, brim * 0.5
    d.rounded_rectangle([(cx - cw / 2) * s, (base - ch) * s, (cx + cw / 2) * s, (base + 1) * s], radius=7 * s, fill=(104, 62, 36, 255), outline=HAT_INK, width=_o(s))
    d.line([((cx - 5) * s, (base - ch + 3) * s), (cx * s, (base - ch + 8) * s), ((cx + 5) * s, (base - ch + 3) * s)], fill=HAT_INK, width=int(2 * s))
    d.rectangle([(cx - cw / 2 + 2) * s, (base - 8) * s, (cx + cw / 2 - 2) * s, (base - 4) * s], fill=(214, 64, 56, 255))
    star(d, cx, base - 6, 3, (250, 210, 80, 255), s)
    # brim tips curled up
    for side in (-1, 1):
        d.ellipse([(cx + side * bw - 5) * s, (base - 10) * s, (cx + side * bw + 5) * s, (base - 1) * s], fill=(84, 48, 28, 255), outline=HAT_INK, width=int(2 * s))


def hat_propeller(d, s, cx, base, brim, i):
    R = brim * 0.4
    box = [(cx - R) * s, (base - R * 1.4) * s, (cx + R) * s, (base + R * 0.6) * s]
    d.pieslice(box, 180, 360, fill=(240, 70, 70, 255), outline=HAT_INK, width=_o(s))
    d.pieslice(box, 240, 300, fill=(60, 120, 230, 255))
    d.pieslice(box, 180, 210, fill=(250, 210, 60, 255))
    d.pieslice(box, 330, 360, fill=(250, 210, 60, 255))
    d.arc(box, 180, 360, fill=HAT_INK, width=_o(s))
    d.line([((cx - R) * s, base * s), ((cx + R) * s, base * s)], fill=HAT_INK, width=_o(s))
    top = base - R * 0.95
    d.line([(cx * s, top * s), (cx * s, (top - 7) * s)], fill=HAT_INK, width=int(2.4 * s))
    ang = math.pi * i / 3  # spin
    L = brim * 0.42
    span = abs(math.cos(ang))
    for side in (-1, 1):
        d.ellipse([(cx + side * L * span / 2 - L * span / 2 - 1.5) * s, (top - 11) * s, (cx + side * L * span / 2 + L * span / 2 + 1.5) * s, (top - 5) * s],
                  fill=(90, 200, 120, 255) if side < 0 else (60, 160, 230, 255), outline=HAT_INK, width=int(1.6 * s))
    d.ellipse([(cx - 2.5) * s, (top - 10) * s, (cx + 2.5) * s, (top - 5) * s], fill=(250, 210, 60, 255), outline=HAT_INK, width=int(1.2 * s))


def hat_yuzu(d, s, cx, base, brim, i):
    r = brim * 0.26
    y = base - r + 1
    d.ellipse([(cx - r * 1.1) * s, (y - r) * s, (cx + r * 1.1) * s, (y + r) * s], fill=(252, 196, 38, 255), outline=HAT_INK, width=_o(s))
    for ox, oy in ((-0.4, 0.3), (0.3, 0.45), (0.5, -0.1), (-0.1, 0.6)):  # peel dimples
        d.ellipse([(cx + ox * r - 0.9) * s, (y + oy * r - 0.9) * s, (cx + ox * r + 0.9) * s, (y + oy * r + 0.9) * s], fill=(222, 150, 30, 255))
    d.ellipse([(cx - r * 0.7) * s, (y - r * 0.6) * s, (cx - r * 0.2) * s, (y - r * 0.2) * s], fill=(255, 240, 170, 255))
    d.line([(cx * s, (y - r + 1) * s), ((cx + 1) * s, (y - r - 4) * s)], fill=HAT_INK, width=int(2 * s))
    d.chord([(cx + 1) * s, (y - r - 9) * s, (cx + 15) * s, (y - r - 1) * s], 0, 360, fill=LEAF, outline=HAT_INK, width=int(1.6 * s))


# Seasonal stand-ins for the top hat (see SEASON_HATS); kept no taller than it so the bird still fits.
def bezier(*pts, n=24):
    (x0, y0), (x1, y1), (x2, y2) = pts
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t * t * x2, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t * t * y2) for t in (k / n for k in range(n + 1))]


def hat_santa(d, s, cx, base, brim, i):
    b, sw = brim, 1.6 * math.sin(2 * math.pi * i / 6)  # the floppy tip sways
    tip = (cx + b * 0.5, base - b * 0.26 + sw)
    pts = bezier((cx - b * 0.38, base), (cx - b * 0.14, base - b * 0.9), (cx + b * 0.1, base - b * 0.62)) + \
        bezier((cx + b * 0.1, base - b * 0.62), (cx + b * 0.42, base - b * 0.46), tip) + [(cx + b * 0.38, base)]
    d.polygon([(x * s, y * s) for x, y in pts], fill=(214, 40, 48, 255), outline=HAT_INK, width=_o(s))
    d.line([((cx - b * 0.2) * s, (base - b * 0.14) * s), ((cx - b * 0.1) * s, (base - b * 0.5) * s)], fill=(250, 110, 110, 255), width=int(3 * s))
    r = b * 0.13
    d.ellipse([(tip[0] - r) * s, (tip[1] - r) * s, (tip[0] + r) * s, (tip[1] + r) * s], fill=(255, 255, 255, 255), outline=HAT_INK, width=int(2.2 * s))
    d.rounded_rectangle([(cx - b * 0.47) * s, (base - 6) * s, (cx + b * 0.47) * s, (base + 5) * s], radius=5 * s, fill=(255, 255, 255, 255), outline=HAT_INK, width=_o(s))


def hat_pumpkin(d, s, cx, base, brim, i):
    rx, ry = brim * 0.44, brim * 0.32
    cy = base - ry + 4
    d.line([(cx * s, (cy - ry + 2) * s), ((cx + 2) * s, (cy - ry - 7) * s)], fill=(92, 120, 40, 255), width=int(5.5 * s))  # stem
    d.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], fill=(244, 128, 30, 255), outline=HAT_INK, width=_o(s))
    for f in (0.5, 0.22):  # ribs
        d.ellipse([(cx - rx * f) * s, (cy - ry + 1) * s, (cx + rx * f) * s, (cy + ry - 1) * s], outline=(200, 88, 20, 255), width=int(1.8 * s))
    d.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], outline=HAT_INK, width=_o(s))
    glow, ey = (255, 214, 70, 255), cy - ry * 0.12
    for ex in (cx - rx * 0.42, cx + rx * 0.42):  # carved, candle-lit face
        d.polygon([((ex - 5) * s, (ey + 3) * s), ((ex + 5) * s, (ey + 3) * s), (ex * s, (ey - 5) * s)], fill=glow, outline=HAT_INK, width=int(1.6 * s))
    my, mw = cy + ry * 0.42, rx * 0.62
    d.polygon([((cx - mw + 2 * k * mw / 4) * s, (my - (3 if k % 2 else -2)) * s) for k in range(5)] +
              [((cx + mw - 2 * k * mw / 4) * s, (my + (4 if k % 2 == 0 else 1)) * s) for k in range(5)], fill=glow, outline=HAT_INK, width=int(1.6 * s))
    d.arc([(cx - rx * 0.75) * s, (cy - ry * 0.85) * s, (cx - rx * 0.1) * s, (cy - ry * 0.1) * s], 200, 250, fill=(255, 190, 110, 255), width=int(2.4 * s))


def hat_sun(d, s, cx, base, brim, i):
    straw, straw_dk = (240, 206, 120, 255), (196, 150, 70, 255)
    bw, cw, ch = brim * 0.74, brim * 0.34, brim * 0.5
    d.ellipse([(cx - bw) * s, (base - 7) * s, (cx + bw) * s, (base + 7) * s], fill=straw, outline=HAT_INK, width=_o(s))  # wide brim
    for k in (0.55, 0.8):  # weave rings
        d.ellipse([(cx - bw * k) * s, (base - 7 * k) * s, (cx + bw * k) * s, (base + 7 * k) * s], outline=straw_dk, width=int(1.4 * s))
    d.rounded_rectangle([(cx - cw) * s, (base - ch) * s, (cx + cw) * s, (base + 1) * s], radius=8 * s, fill=straw, outline=HAT_INK, width=_o(s))
    d.rectangle([(cx - cw + 1.5) * s, (base - ch * 0.26) * s, (cx + cw - 1.5) * s, (base - 1) * s], fill=(40, 170, 190, 255))  # ribbon
    gy = base - ch * 0.5  # sunglasses pushed up on the crown
    for gx in (cx - cw * 0.48, cx + cw * 0.48):
        d.rounded_rectangle([(gx - 6.5) * s, (gy - 4.5) * s, (gx + 6.5) * s, (gy + 4.5) * s], radius=4 * s, fill=(30, 30, 40, 255), outline=HAT_INK, width=int(2 * s))
        d.line([((gx - 4) * s, (gy - 2) * s), ((gx - 1) * s, (gy - 3.4) * s)], fill=(200, 230, 255, 255), width=int(1.6 * s))
    d.line([((cx - 2) * s, (gy - 2) * s), ((cx + 2) * s, (gy - 2) * s)], fill=HAT_INK, width=int(2.4 * s))
    star(d, cx + cw + 3, base - 6, 5, (255, 120, 150, 255), s)  # flower


HATS = {"top": hat_top, "party": hat_party, "umbrella": hat_umbrella, "mortarboard": hat_mortarboard, "hard": hat_hard,
        "cowboy": hat_cowboy, "propeller": hat_propeller, "yuzu": hat_yuzu,
        "santa": hat_santa, "pumpkin": hat_pumpkin, "sun": hat_sun}
SEASON_HATS = {"winter": "santa", "halloween": "pumpkin", "summer": "sun"}
PERCH = {"top": (0, 0.62), "santa": (0.08, 0.64), "pumpkin": (-0.16, 0.54), "sun": (0, 0.52)}  # bird spot: (dx, height) × brim
TOP = SEASON_HATS[SEASON] if SEASON else "top"
HATS["top"] = HATS[TOP]  # the default look (stock rows, munching, sign, bird, top-hat intro)


def hat_geom(body):
    """(centre x, brim y, brim width) of the hat on this (shrunk) body."""
    cx, top, hw = head_anchor(body)
    bb = body.getchannel("A").getbbox() or (0, 0, W, H)
    brim = max(42, min(58, (bb[2] - bb[0]) * 0.36))  # size from the whole body: side views have a narrow crown
    return cx, top + brim * 0.16, brim


def hat_tip(body):
    """Where the bird perches on the tilted default hat (top of the crown)."""
    cx, base, brim = hat_geom(body)
    a, (dx, h) = math.radians(-HAT_TILT), (brim * f for f in PERCH[TOP])
    return cx + dx * math.cos(a) + h * math.sin(a), base + dx * math.sin(a) - h * math.cos(a)


def hat_layer(body, kind, i, drop=0.0, squash=1.0, alpha=1.0, tilt=0.0, dx=0.0, geom=None):
    cx, base, brim = geom or hat_geom(body)
    base -= drop
    cx += dx

    def draw(d, s):
        HATS[kind](d, s, cx, base, brim, i)
    layer = aa(draw)
    if squash != 1.0:
        layer = xform(layer.crop((0, 0, W, H)), sx=1 / squash, sy=squash, dy=(base - (H - 6)) * (1 - squash))
    layer = layer.rotate(HAT_TILT + tilt, resample=Image.BICUBIC, center=(cx, base))
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    return layer


def poof(cx, cy, t, size=1.0):
    """Comic smoke puff + sparkles around (cx, cy); t in [0,1] grows then fades."""
    def draw(d, s):
        a = int(255 * (1 - max(0, t - 0.55) / 0.45)) if t > 0.55 else 255
        grow = (0.55 + 0.75 * min(1, t / 0.5)) * size
        for k, (ox, oy, r) in enumerate(((-16, 2, 13), (0, -8, 16), (16, 2, 13), (-8, 10, 12), (9, 11, 12), (0, 0, 14))):
            rr = r * grow
            x, y = cx + ox * grow, cy + oy * grow
            d.ellipse([(x - rr) * s, (y - rr) * s, (x + rr) * s, (y + rr) * s], fill=(80, 80, 90, a))
        for k, (ox, oy, r) in enumerate(((-16, 2, 13), (0, -8, 16), (16, 2, 13), (-8, 10, 12), (9, 11, 12), (0, 0, 14))):
            rr = r * grow - 2.4
            x, y = cx + ox * grow, cy + oy * grow
            d.ellipse([(x - rr) * s, (y - rr) * s, (x + rr) * s, (y + rr) * s], fill=(250, 250, 252, a))
        for k in range(5):
            ang = k * 2 * math.pi / 5 + t * 2
            rad = (22 + 18 * t) * size
            star(d, cx + rad * math.cos(ang), cy + rad * math.sin(ang) * 0.8, (4 + 2 * (1 - t)) * size ** 0.5, (255, 214, 70, a), s)
    return aa(draw)


def hat_intro(kind):
    """Once-only costume change: POOF hides the old hat, the new one drops in and squashes."""
    frames = []
    plan = [  # (poof t or None, hat drop px or None, squash)
        (0.15, None, 1.0), (0.45, None, 1.0), (0.75, 40, 1.0), (1.0, 18, 1.0), (None, 0, 0.82), (None, 0, 1.0)]
    for i, (pt, drop, sq) in enumerate(plan):
        body = shrink(idle_base(i))
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.alpha_composite(body)
        cx, top, hw = head_anchor(body)
        if drop is not None:
            out.alpha_composite(hat_layer(body, kind, i, drop=drop, squash=sq))
        if pt is not None:
            out.alpha_composite(poof(cx, top + 4, pt))
        frames.append(out)
    return frames


def dress(frame, kind="top", i=0):
    """(under, body, over) → one frame: shared shrink, the row's hat on the body, effects on top."""
    if not isinstance(frame, tuple):
        frame = (None, frame, None)
    under, body, over = shrink(frame[0]), shrink(frame[1]), frame[2]
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for layer in (under, body, hat_layer(body, kind, i) if HAT else None, over):
        if layer is not None:
            out.alpha_composite(layer)
    return out


# ------------------------------------------------------------ interactions
# Desktop pointer states: poke (clicked), held (dragged), fall, land. Built from the front-facing
# frame on a padded canvas, so dangling/spread limbs never clip before the body is placed in the
# final frame, and each row composes its own hat (it lifts off while falling, lands back on impact).
PAD = 48
FUR, PAW = (221, 161, 86, 255), (174, 110, 56, 255)
EYES = ((65, 47), (129, 47))


class Pen:
    """ImageDraw in frame coords (offset by o) on an s× supersampled canvas."""
    def __init__(self, d, s, o=0):
        self.d, self.s, self.o = d, s, o

    def p(self, x, y):
        return ((x + self.o) * self.s, (y + self.o) * self.s)

    def ell(self, cx, cy, rx, ry=None, fill=None, ink=0.0):
        ry = rx if ry is None else ry
        self.d.ellipse([*self.p(cx - rx, cy - ry), *self.p(cx + rx, cy + ry)], fill=fill, outline=INK if ink else None, width=int(ink * self.s))

    def line(self, pts, fill, w):
        self.d.line([self.p(*q) for q in pts], fill=fill, width=int(w * self.s), joint="curve")
        for q in (pts[0], pts[-1]):  # round caps
            self.ell(*q, w / 2, fill=fill)

    def poly(self, pts, fill, ink=0.0):
        self.d.polygon([self.p(*q) for q in pts], fill=fill, outline=INK if ink else None, width=int(ink * self.s))

    def arc(self, cx, cy, rx, ry, a0, a1, fill, w):
        self.d.arc([*self.p(cx - rx, cy - ry), *self.p(cx + rx, cy + ry)], a0, a1, fill=fill, width=int(w * self.s))


def canvas(fn, size, o=0, scale=4):
    big = Image.new("RGBA", (size[0] * scale, size[1] * scale), (0, 0, 0, 0))
    fn(Pen(ImageDraw.Draw(big), scale, o))
    return big.resize(size, Image.LANCZOS)


def front(under=None, face=None):
    """Front-facing source frame on a padded canvas: limbs `under` the body, face edits on top."""
    size = (W + 2 * PAD, H + 2 * PAD)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    if under:
        out.alpha_composite(canvas(under, size, PAD))
    out.alpha_composite(cell(9, 0), (PAD, PAD))
    if face:
        out.alpha_composite(canvas(face, size, PAD))
    return out


def place(im, sc=SHRINK, sx=1.0, sy=1.0, rot=0.0, anchor=(96, 202), at=(96, 202)):
    """Scale a padded source image so source point `anchor` lands on frame point `at`, rotated about it."""
    kx, ky = sc * sx, sc * sy
    s = im.resize((max(1, round(im.width * kx)), max(1, round(im.height * ky))), Image.BICUBIC)
    big = Image.new("RGBA", (3 * W, 3 * H), (0, 0, 0, 0))
    big.alpha_composite(s, (round(W + at[0] - (anchor[0] + PAD) * kx), round(H + at[1] - (anchor[1] + PAD) * ky)))
    if rot:
        big = big.rotate(rot, resample=Image.BICUBIC, center=(W + at[0], H + at[1]))
    bb = big.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    assert bb[0] > W and bb[1] > H and bb[2] < 2 * W and bb[3] < 2 * H, ("body clips", bb)
    return big.crop((W, H, 2 * W, 2 * H))


def compose(i, body, over=None, under=None, anchor=None, kind="top", **hat):
    """under + body + hat (geometry from the limb-less `anchor` body, constant brim) + over."""
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for layer in (under, body):
        if layer is not None:
            out.alpha_composite(layer)
    if HAT:
        cx, base, _ = hat_geom(anchor or body)
        h = hat_layer(body, kind, i, geom=(cx, base, BRIM), **hat)
        assert (h.getchannel("A").getbbox() or (1, 1))[1] > 0, "hat clips the top edge"
        out.alpha_composite(h)
    if over is not None:
        out.alpha_composite(over)
    return out


# face kit (source coords, front frame)
def erase_eyes(p):
    for ex, ey in EYES:
        p.ell(ex, ey, 12, fill=SKIN)


def eyes_squeeze(p):
    erase_eyes(p)
    for (ex, ey), k in zip(EYES, (1, -1)):
        p.line([(ex - 7 * k, ey - 7), (ex + 6 * k, ey), (ex - 7 * k, ey + 7)], INK, 3.6)


def eyes_happy(p):
    erase_eyes(p)
    for ex, ey in EYES:
        p.arc(ex, ey + 3, 9, 9, 200, 340, INK, 3.6)


def eyes_wide(p, look=0.0):
    erase_eyes(p)
    for ex, ey in EYES:
        p.ell(ex, ey, 10.5, fill=(255, 255, 255, 255), ink=2.8)
        p.ell(ex + look, ey + 1, 4.6, fill=INK)
        p.ell(ex + look - 1.8, ey - 1.2, 1.6, fill=(255, 255, 255, 255))


def eyes_dizzy(p, ph):
    erase_eyes(p)
    for (ex, ey), k in zip(EYES, (1, -1)):
        pts = [(ex + k * 0.85 * a * math.cos(a + ph), ey + 0.85 * a * math.sin(a + ph)) for a in (j * 0.35 for j in range(1, 34))]
        p.line(pts, INK, 2.6)


def mouth_o(p, r=6.0, y=86):
    p.ell(96, y, r * 0.85, r, fill=INK)
    p.ell(96, y + r * 0.35, r * 0.5, r * 0.45, fill=(210, 84, 92, 255))


def smile(p):
    p.arc(96, 80, 13, 9, 20, 160, INK, 3.2)


def blush(p, a=130):
    for cx in (50, 142):
        p.ell(cx, 66, 11, 6, fill=(236, 110, 100, a))


def drop_(p, x, y, r, a=255):
    p.poly([(x, y - r * 2.2), (x - r, y), (x + r, y)], (150, 215, 255, a))
    p.ell(x, y, r, fill=(150, 215, 255, a), ink=0)
    p.arc(x, y, r, r, 0, 180, (50, 110, 170, a), 1.4)
    p.ell(x - r * 0.35, y - r * 0.2, r * 0.3, fill=(255, 255, 255, a))


def limb(p, a, b, w=26, paw=15):
    """Stubby fur leg/arm a→b in the source's thick ink outline, ending in a round dark-brown paw like the sitting feet."""
    p.line([a, b], INK, w + 8)
    p.line([a, b], FUR, w)
    p.ell(*b, paw + 4, paw * 0.86 + 4, fill=INK)
    p.ell(*b, paw, paw * 0.86, fill=PAW)
    p.arc(b[0], b[1] - paw * 0.2, paw * 0.6, paw * 0.4, 200, 300, (200, 136, 76, 255), 2.4)  # soft top-light


def bang(p, x, y, sz, a=255, rot=0.0):
    """Bold red '!' with an ink outline (drawn as shapes, so it reads at 0.45x)."""
    c, r = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    R = lambda dx, dy: (x + dx * c - dy * r, y + dx * r + dy * c)
    red, ink = (230, 52, 48, a), INK[:3] + (a,)
    for col, g in ((ink, 2.2), (red, 0)):
        p.poly([R(-sz * 0.32 - g, -sz - g), R(sz * 0.32 + g, -sz - g), R(sz * 0.14 + g * 0.6, sz * 0.25 + g), R(-sz * 0.14 - g * 0.6, sz * 0.25 + g)], col)
        p.ell(*R(0, sz * 0.62), sz * 0.19 + g, fill=col)


def ostar(p, x, y, r, a=255):
    for col, rr in ((INK[:3] + (a,), r + 2.2), ((255, 214, 60, a), r)):
        p.poly([(x + (rr if k % 2 == 0 else rr * 0.42) * math.cos(math.pi / 5 * k - math.pi / 2),
                 y + (rr if k % 2 == 0 else rr * 0.42) * math.sin(math.pi / 5 * k - math.pi / 2)) for k in range(10)], col)


def oheart(p, x, y, r, a=255):
    d, s = p.d, p.s
    heart(d, x, y + 0.6, r + 2.2, INK[:3] + (a,), s)
    heart(d, x, y, r, (255, 96, 132, a), s)
    p.ell(x - r * 0.45, y - r * 0.45, r * 0.22, fill=(255, 220, 228, a))


def puff(p, x, y, r, a):
    p.ell(x, y, r, r * 0.8, fill=(245, 232, 208, a))
    p.arc(x, y, r, r * 0.8, 160, 380, (190, 160, 120, a), 1.6)


BRIM = hat_geom(shrink(cell(9, 0)))[2] if HAT else 0


def poked():
    """Click: squash + startled > < with a '!', then ^ ^ and hearts drifting up (one-shot)."""
    plan = [  # squash sy, hop px, startled?
        (0.82, 0, True), (1.07, -9, True), (0.95, 0, False), (1.03, -5, False), (1.0, 0, False), (1.0, 0, False)]
    frames = []
    for i, (sy, hop, startled) in enumerate(plan):
        def face(p, startled=startled):
            if startled:
                eyes_squeeze(p)
                mouth_o(p, 5.5)
            else:
                eyes_happy(p)
                blush(p, 150)
                smile(p)
        body = place(front(face=face), sx=1 / sy ** 0.6, sy=sy, at=(96, 202 + hop))

        def fx(p, i=i, startled=startled):
            if i < 3:
                bang(p, 34, 54 - 4 * min(i, 1), 13 + 4 * min(i, 1), a=255 if i < 2 else 120, rot=-12)
            if startled:  # surprise ticks around the head
                for k, ang in enumerate((-160, -135, -45, -20)):
                    a, r0 = math.radians(ang), 64 + 6 * i
                    p.line([(96 + r0 * math.cos(a), 112 + r0 * 0.9 * math.sin(a)), (96 + (r0 + 10) * math.cos(a), 112 + (r0 + 10) * 0.9 * math.sin(a))], INK, 2.6)
            for k, (x0, side) in enumerate(((38, -1), (160, 1), (150, 1))):
                age = (i - 2 - k * 0.8) / 3.2
                if 0 <= age <= 1:
                    oheart(p, x0 + side * 6 * math.sin(age * 5), 92 - age * 62, 6 + 2 * (1 - age), int(255 * min(1, (1 - age) * 2.5)))
        frames.append(compose(i, body, canvas(fx, (W, H)), anchor=body))
    return frames


def held():
    """Dragged: dangling by the scruff, swinging, surprised face, sweat drop (loop)."""
    frames = []
    for i in range(6):
        t = i / 6
        sw = math.sin(2 * math.pi * t)

        def face(p, t=t):
            eyes_wide(p, look=1.5 * math.sin(2 * math.pi * t))
            mouth_o(p, 4.5, 88)
            drop_(p, 160, 46 + 3 * (i % 3), 7.5)
        kw = dict(sc=0.7, sx=0.95, sy=1.05, rot=5 * sw, anchor=(96, 14), at=(96, 40))
        body = place(front(face=face), **kw)

        def fx(p, sw=sw):
            for side in (-1, 1):  # swing arcs beside the body
                p.arc(96 + side * 62 - 8 * sw, 130, 10, 26, 150 if side < 0 else -30, 210 if side < 0 else 30, INK[:3] + (170,), 2.4)
        frames.append(compose(i, body, canvas(fx, (W, H)), anchor=place(front(), **kw), tilt=0.6 * 5 * sw))
    return frames


def falling():
    """Released mid-air: limbs spread, wide eyes, speed lines rushing up, the hat lifting and wobbling (loop)."""
    frames = []
    for i in range(6):
        t = i / 6
        wob = math.sin(2 * math.pi * t)

        def limbs(p, wob=wob):
            for side, (sxp, syp) in ((-1, (46, 116)), (1, (146, 116))):  # arms up and out
                limb(p, (sxp, syp), (96 + side * 80, 80 - 6 * side * wob), 24, 13)
            for side in (-1, 1):  # legs kicked out
                limb(p, (96 + side * 46, 182), (96 + side * 78, 198 + 5 * side * wob))

        def face(p):
            for x in (56, 138):  # paws are up in the air now: fur over the ones on the box
                p.ell(x, 146, 15, 17, fill=FUR)
            eyes_wide(p)
            mouth_o(p, 7.5, 87)
        kw = dict(sc=0.74, rot=3 * wob, anchor=(96, 110), at=(96, 126))
        body = place(front(limbs, face), **kw)
        anchor = place(front(), **kw)

        def fx(p, t=t):
            for k, (x, y0, ln) in enumerate(((16, 166, 34), (28, 78, 26), (172, 170, 30), (180, 90, 36))):
                y = y0 - ((t + k * 0.37) % 1) * 30
                p.line([(x, y), (x, y - ln)], (96, 128, 186, 230), 3.4)
            cx = hat_geom(anchor)[0]
            for side in (-1, 1):  # "it's coming off!" ticks between head and hat
                p.line([(cx + side * 12, 56), (cx + side * 17, 48)], INK[:3] + (200,), 2.2)
        frames.append(compose(i, body, canvas(fx, (W, H)), anchor=anchor, drop=16 + 3 * wob, tilt=12 * wob, dx=3 * wob))
    return frames


def landing():
    """Touchdown: squash, dust, the hat drops back on, dizzy stars, then a recovery bounce (one-shot)."""
    plan = [  # squash sy, hop, face, hat drop, hat squash, dust age, stars alpha
        (0.72, 0, "squeeze", 30, 1.0, 0.0, 0), (0.8, 0, "squeeze", 6, 0.8, 0.25, 0), (1.05, -4, "dizzy", 0, 1.0, 0.5, 0.6),
        (0.97, 0, "dizzy", 0, 1.0, 0.75, 1), (1.0, 0, "dizzy", 0, 1.0, 1.0, 1), (1.0, 0, "dizzy", 0, 1.0, None, 1),
        (1.04, -10, "happy", 0, 1.0, None, 0.4), (0.97, 0, "happy", 0, 0.92, None, 0)]
    frames = []
    for i, (sy, hop, mood, hdrop, hsq, dust, star_a) in enumerate(plan):
        def face(p, mood=mood):
            if mood == "squeeze":
                eyes_squeeze(p)
                mouth_o(p, 6, 87)
            elif mood == "dizzy":
                eyes_dizzy(p, i * 1.3)
                p.arc(96, 92, 9, 4, 200, 340, INK, 3)  # wobbly mouth
                p.arc(96, 86, 9, 4, 20, 160, INK, 3)
            else:
                eyes_happy(p)
                blush(p)
                smile(p)
        rot = (4, -4)[i % 2] if mood == "dizzy" and i > 2 else 0
        body = place(front(face=face), sx=1 / sy ** 0.7, sy=sy, rot=rot, at=(96, 202 + hop))

        def stars(p, back, i=i, star_a=star_a):  # orbit the hat: the far half passes behind it
            for k in range(3 if star_a else 0):
                ang = 2 * math.pi * (k / 3 + i / 8 * 1.5)
                if (math.sin(ang) < 0) == back:
                    ostar(p, 96 + 58 * math.cos(ang), 46 + 13 * math.sin(ang), 6 + 1.5 * math.sin(ang), int(255 * star_a))

        def fx(p, i=i, dust=dust):
            stars(p, False)
            if dust is not None:
                for side in (-1, 1):
                    for k in range(3):
                        e = min(1, dust + k * 0.12)
                        puff(p, 96 + side * (44 + 26 * e + 8 * k), 196 - 8 * e - 5 * k, 8 + 6 * e - 2 * k, int(240 * (1 - e ** 1.6)))
            if i == 0:
                for side in (-1, 1):  # impact lines
                    for k in range(3):
                        y = 182 + k * 8
                        p.line([(96 + side * 70, y), (96 + side * (80 + 3 * k), y - 4 + 4 * k)], INK, 2.6)
        frames.append(compose(i, body, canvas(fx, (W, H)), canvas(lambda p: stars(p, True), (W, H)), drop=hdrop, squash=hsq))
    return frames


# Poked while dozing in the tub (pet.json `wake`): the yuzu costume's one-shot wake-up.
TUB_FUR = (227, 164, 91, 255)
TUB_EYES = ((68, 85), (130, 85))  # the closed-eye arcs of source row 10


def tub_eyes(p, mood):
    for (ex, ey), k in zip(TUB_EYES, (1, -1)):  # k: +1 = left eye (its inner side is +x)
        p.ell(ex, ey + 1, 12.5, 9, fill=TUB_FUR)
        if mood == "squeeze":
            p.line([(ex - 7 * k, ey - 6), (ex + 6 * k, ey), (ex - 7 * k, ey + 6)], INK, 3.6)
            continue
        p.ell(ex, ey, 9.5, fill=(255, 255, 255, 255), ink=2.8)
        if mood == "wide":  # tiny startled pupils
            p.ell(ex, ey + 0.5, 3.4, fill=INK)
        else:  # grumpy: pupils low, a flat lid sloping down to the nose
            p.ell(ex + 1.5 * k, ey + 3, 4.6, fill=INK)
            lid = [(ex - 11 * k, ey - 4), (ex + 11 * k, ey + 1.5)]
            p.poly([lid[0], lid[1], (ex + 11 * k, ey - 13), (ex - 11 * k, ey - 13)], TUB_FUR)
            p.line(lid, INK, 3.6)


def anger(p, x, y, sz, a=255):
    """Comic 'cross-popping vein' mark (💢): four red brackets bowing in to the centre."""
    for q in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        cx, cy = x + q[0] * sz * 1.05, y + q[1] * sz * 1.05
        ang = math.degrees(math.atan2(-q[1], -q[0]))
        p.arc(cx, cy, sz * 0.85, sz * 0.85, ang - 34, ang + 34, (150, 20, 24, a), 6.4)
        p.arc(cx, cy, sz * 0.85, sz * 0.85, ang - 30, ang + 30, (240, 56, 52, a), 3.8)


def yuzu_air(cx, base, brim, i, dx, lift, spin):
    """The yuzu off the head, spinning about its own middle."""
    layer = aa(lambda d, s: hat_yuzu(d, s, cx + dx, base - lift, brim, i))
    return layer.rotate(HAT_TILT - spin, resample=Image.BICUBIC, center=(cx + dx, base - lift - brim * 0.26))


def waking():
    """Eyes snap open with a splash, the yuzu pops off and bounces back on, then a grumpy half-lidded glare 💢 (one-shot)."""
    plan = [  # body dy, sy, rot, eyes, yuzu (dx, lift, spin) or on-head squash, splash age, '!' alpha, 💢 size, huff age
        (-6, 1.05, -2, "wide", (2, 12, 40), 0.0, 255, 0, None), (-8, 1.03, 2, "wide", (5, 20, 130), 0.3, 255, 0, None),
        (0, 0.97, 0, "wide", (6, 24, 220), 0.55, 150, 0, None), (5, 0.95, 0, "squeeze", (3, 10, 320), 0.8, 0, 0, None),
        (4, 1.0, 0, "grumpy", 0.72, 1.0, 0, 9, None), (4, 1.0, 0, "grumpy", (0, 5, 355), None, 0, 13, 0.1),
        (4, 1.0, 0, "grumpy", 1.0, None, 0, 11.5, 0.55), (4, 1.0, 0, "grumpy", 1.0, None, 0, 12, None)]
    frames = []
    for i, (dy, sy, rot, eyes, yz, splash, bang_a, mark, huff) in enumerate(plan):
        body = cell(10, 0).copy()
        # hide the source frame's held box, which would peek above the water as the body jolts up
        body.alpha_composite(canvas(lambda p: p.poly([(54, 150), (60, 128), (136, 128), (142, 150)], TUB_FUR), (W, H)))
        body.alpha_composite(aa(TUB_BLUSH))
        body.alpha_composite(canvas(lambda p, eyes=eyes: tub_eyes(p, eyes), (W, H)))
        spr = xform(body, dy=dy, sx=1 / sy ** 0.5, sy=sy, rot=rot)
        sb = shrink(spr)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.alpha_composite(sb)
        if HAT:
            cx, base, brim = hat_geom(sb)
            out.alpha_composite(yuzu_air(cx, base, brim, i, *yz) if isinstance(yz, tuple) else hat_layer(sb, "yuzu", i, squash=yz))
        out.alpha_composite(tub(spr, i / 8, zees=False))

        def fx(p, i=i, splash=splash, bang_a=bang_a, mark=mark, huff=huff):
            if bang_a:
                bang(p, 36, 64 - 3 * min(i, 1), 14 + 3 * min(i, 1), a=bang_a, rot=-12)
            if splash is not None:  # droplets arc out of the tub and fall back past the rim
                for side in (-1, 1):
                    for j in range(3):
                        e = min(1.0, splash + 0.08 * j)
                        x = 96 + side * (30 + 14 * j + (8 + 4 * j) * 1.4 * e)
                        y = TUB_YC - 4 - (52 - 8 * j) * e + (62 - 4 * j) * e * e
                        drop_(p, x, y, 4.2 - 0.6 * j, int(255 * (1 - e ** 3)))
                if splash >= 0.5:  # rings on the water
                    e = (splash - 0.5) * 2
                    p.arc(96, TUB_YC, 44 + 16 * e, 5 + 2 * e, 15, 165, (255, 255, 255, int(230 * (1 - 0.6 * e))), 2.2)
            if i == 4:  # the yuzu lands back on: tiny impact ticks
                for k in (-1, 0, 1):
                    p.line([(124 + 14 * k, 26 - 3 * abs(k)), (124 + 18 * k, 19 - 4 * abs(k))], INK, 2.2)
            if mark:
                anger(p, 150, 66, mark)
            if huff is not None:  # a grumpy huff of steam out of both sides
                for side in (-1, 1):
                    for k in range(2):
                        r, a = 7 + 5 * huff - 1.5 * k, int(245 * (1 - huff ** 2))
                        x, y = 96 + side * (56 + 14 * huff + 11 * k), 122 - 6 * huff - 5 * k
                        p.ell(x, y, r, r * 0.8, fill=(255, 255, 255, a))
                        p.arc(x, y, r, r * 0.8, 0, 360, (150, 160, 175, a), 1.4)
        out.alpha_composite(canvas(fx, (W, H)))
        bb = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        assert bb[0] > 0 and bb[1] > 0 and bb[2] < W and bb[3] < H, ("waking clips", i, bb)
        frames.append(out)
    return frames


# ---------------------------------------------------------------- assemble
# Row order = pet.json stateRows. Hats per row; the *-hat rows are the costume intros.
ROW_HATS = ["top"] * 9 + ["party", "umbrella", "mortarboard", "cowboy", "hard", "propeller", "top", "top", "yuzu", "top", "top"]
INTROS = ["top", "party", "umbrella", "mortarboard", "hard", "cowboy", "propeller"]

rows = [[cell(r, c) for c in range(count(r))] for r in range(9)]
rows[1] = with_dust(1, +1)
rows[2] = with_dust(2, -1)
rows[7] = with_dust(7, +1)
rows += [smiling(), crying(), thinking(), dancing(), tinkering(), juggling(), munching(), bird(), onsen(), sign(), laptop()]
rows = [[dress(f, ROW_HATS[r] if HAT else "top", i) for i, f in enumerate(row)] for r, row in enumerate(rows)]
if HAT:
    rows += [hat_intro(k) for k in INTROS] + [bird_in(), yawn()]
rows += [poked(), held(), falling(), landing(), waking()]  # already dressed (own hat handling)

sheet = Image.new("RGBA", (W * 8, H * len(rows)), (0, 0, 0, 0))
for r, fr in enumerate(rows):
    for c, f in enumerate(fr[:8]):
        sheet.paste(f, (c * W, r * H))
sheet.save(out_dir / (f"spritesheet-{SEASON}.webp" if SEASON else "spritesheet.webp"), lossless=True, quality=100, method=6)
print("rows", len(rows), "frames", [len(r) for r in rows], sheet.size)
