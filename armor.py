"""Armor look for Explorer: riveted dark-metal plates with a red trim line for the
bars (address row, command bar, menu bar), red-glow button states, and a bottom
details panel with an alien-head emblem.

Windows stretches skin images between their sizing margins (left, right, top,
bottom). The stock bar images are tiny strips (3 px wide), so each plate is drawn
wider and gets new margins: the rivets sit in the corners that never stretch.
"""
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _brushed(w, h, seed):
    """Near-black brushed metal, darker toward the bottom, with fine horizontal streaks."""
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h)[:, None]
    L = 0.060 + 0.050 * np.exp(-((y - 0.25) / 0.35) ** 2)
    L = L + rng.normal(0, 1, (h, 1)) * 0.010 + rng.normal(0, 1, (h, w)) * 0.004
    rgb = np.repeat(L[..., None], 3, -1) * np.array([1.0, 1.0, 1.05])
    return np.clip(rgb, 0, 1)


def _rivet(rgb, cx, cy, r, accent):
    """A bold domed rivet: dark outline ring, bright specular spot top-left, darker
    underside with a red reflection, and a faint red glow around it."""
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    acc = np.asarray(accent)
    d = np.hypot(xx - cx, yy - cy)
    halo = np.clip(1 - (d - r) / (r * 0.9), 0, 1) * (d > r)       # red glow just outside
    rgb[:] = np.clip(rgb + (halo ** 2)[..., None] * acc * 0.35, 0, 1)
    disc = np.clip(r + 0.5 - d, 0, 1)
    spec = np.clip(1 - np.hypot(xx - (cx - r * 0.38), yy - (cy - r * 0.38)) / (r * 0.75), 0, 1)
    under = np.clip((yy - cy) / r, 0, 1)
    body = 0.22 + 0.70 * spec[..., None] ** 1.6 - 0.10 * under[..., None] + under[..., None] * acc * 0.30
    ring = np.clip(1 - abs(d - (r - 0.6)) / max(0.9, r * 0.16), 0, 1)[..., None]
    shade = body * (1 - ring * 0.85)
    rgb[:] = rgb * (1 - disc[..., None]) + np.clip(shade, 0, 1) * disc[..., None]


def plate(w, h, margins, accent, seed=1, trim=True, scale=1.0):
    """Riveted bar plate. `w, h, margins` describe the stock image being replaced
    (margins = left, right, top, bottom). Windows draws skin images at their pixel
    size whatever the display scaling, so `scale` (DPI / 96) sizes the art to match.
    Returns (RGBA image, new margins)."""
    acc = np.asarray(accent[:3], float) / 255
    k = max(1.0, scale)
    l, r, t, b = margins
    if w <= 16 or l + r >= w - 1:                  # stretched sideways: make room for rivets
        l = r = int(round(20 * k))
        W = l + r + 8
    else:
        W = w
    if h < 20 and t + b >= h - 1:                  # thin strip: give it some height
        t = b = int(round(13 * k))
        H = t + b + 4
    else:                                          # keep its proportions at the display scaling
        H = int(round(h * k))
        t, b = int(round(t * k)), int(round(b * k))
        if t + b >= H:
            t, b = (H - 1) // 2, H - 1 - (H - 1) // 2
    rgb = _brushed(W, H, seed)
    bevel = max(1, int(round(k)))
    rgb[:bevel] = np.clip(rgb[:bevel] + 0.20, 0, 1)            # bevel highlight
    rgb[bevel:2 * bevel] = np.clip(rgb[bevel:2 * bevel] + 0.07, 0, 1)
    rgb[:, :bevel] = np.clip(rgb[:, :bevel] + 0.05, 0, 1)
    rgb[:, -bevel:] = rgb[:, -bevel:] * 0.5
    if trim and H >= 6:
        line = max(1, int(round(1.6 * k)))                    # bright red line near the bottom
        y1 = H - bevel - line
        gl = min(int(round(6 * k)), y1)
        glow = np.linspace(0, 1, gl)[:, None] ** 2 * 0.25
        rgb[y1 - gl:y1] = np.clip(rgb[y1 - gl:y1] + glow[..., None] * acc, 0, 1)
        rgb[y1:y1 + line] = np.clip(acc * 0.95 + 0.05, 0, 1)
        rgb[y1 + line:] = np.clip(acc * 0.30, 0, 1)
    if W >= 40:
        rr = 4.2 * k
        ys = []
        if t >= 2 * rr + 2 * k:
            ys.append(min(t / 2, rr + 3.5 * k))
        if b >= 2 * rr + 6 * k:
            ys.append(H - b + (b - 4 * k) / 2)
        for y in ys:
            for x in (l / 2, W - r / 2 - 0.5):
                _rivet(rgb, x, y, rr, acc)
    a = np.dstack([rgb, np.ones((H, W))])
    return Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA"), (l, r, t, b)


def glow_frames(img, count, accent):
    """Button state images (frames stacked vertically): keep the shape and alpha, turn
    the grey hover/pressed art into dark red metal with a brighter red edge."""
    acc = np.asarray(accent[:3], float) / 255
    a = np.asarray(img.convert("RGBA")).astype(float) / 255
    L = a[..., :3].mean(-1, keepdims=True)
    out = a.copy()
    out[..., :3] = np.clip(L * 0.35 + (L ** 0.8) * acc * 0.9, 0, 1)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


# ------------------------------------------------------------------ bottom panel

def _head(size, accent):
    """Alien head (no disc) on transparent: dark glossy skull, glowing slanted eyes."""
    S = size * 4
    k = S / 100
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pts = []
    for i in range(81):
        q = i / 80 * 2 * math.pi
        x, y = math.sin(q), -math.cos(q)
        wd = 40 if y < 0.1 else 40 * (1 - (y - 0.1) / 0.9 * 0.80)
        pts.append(((50 + wd * x) * k, (46 + 44 * y + (5 if y > 0 else 0) * y) * k))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    shade = Image.linear_gradient("L").resize((S, S)).point(lambda v: 70 - v * 60 // 255)
    skull = Image.merge("RGBA", (shade, shade, shade.point(lambda v: v + 4), mask))
    img.alpha_composite(skull)
    d = ImageDraw.Draw(img)
    d.polygon(pts, outline=(120, 120, 128, 255), width=max(1, int(1.2 * k)))
    hl = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hl).ellipse([24 * k, 6 * k, 76 * k, 34 * k], fill=38)
    img.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(hl, mask))
    neon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    n = ImageDraw.Draw(neon)
    col = tuple(int(min(255, c * 1.15 + 20)) for c in accent[:3]) + (255,)
    for sgn in (-1, 1):
        cx, cy = 50 + sgn * 17, 52
        eye = []
        for i in range(41):
            q = i / 40 * 2 * math.pi
            ex, ey = 15 * math.cos(q), 7 * math.sin(q)
            an = -sgn * math.radians(30)
            eye.append(((cx + ex * math.cos(an) - ey * math.sin(an)) * k,
                        (cy + ex * math.sin(an) + ey * math.cos(an)) * k))
        n.polygon(eye, fill=col)
    blur = neon.filter(ImageFilter.GaussianBlur(4 * k))
    img = Image.alpha_composite(img, ImageChops.add(blur, blur))
    img = Image.alpha_composite(img, neon)
    return img.resize((size, size), Image.LANCZOS)


def emblem_panel(accent, seed=7, scale=1.0):
    """Bottom details panel: metal plate with a red top edge, faint diagonal red
    slashes and the alien head in the bottom-right corner. The emblem sits wholly
    inside the right and bottom margins, so it never stretches.
    Returns (RGBA image, margins)."""
    acc = np.asarray(accent[:3], float) / 255
    k = max(1.0, scale)
    l, r, t, b = int(16 * k), int(140 * k), int(6 * k), int(88 * k)
    W, H = l + r + int(4 * k), int(96 * k)                  # narrow: the middle just stretches
    rgb = _brushed(W, H, seed) * 0.9
    e = max(1, int(round(k)))
    rgb[:e] = np.clip(acc * 0.85, 0, 1)                      # red line along the top
    rgb[e:2 * e] = np.clip(acc * 0.35, 0, 1)
    rgb[2 * e:3 * e] = np.clip(rgb[2 * e:3 * e] + 0.10, 0, 1)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    region = xx > W - r
    for off in (0, 22, 44):                                  # slashes behind the emblem
        band = np.clip(1 - abs((xx - (W - r + (30 + off) * k)) - (H - yy) * 0.6) / (4 * k), 0, 1) * region
        rgb += band[..., None] * acc * 0.18
    glow = np.exp(-(((xx - (W - 70 * k)) / (70 * k)) ** 2 + ((yy - 52 * k) / (38 * k)) ** 2)) * region
    rgb += glow[..., None] * acc * 0.20
    _rivet(rgb, 9 * k, 11 * k, 4.2 * k, acc)
    _rivet(rgb, 9 * k, H - 10 * k, 4.2 * k, acc)
    a = np.dstack([np.clip(rgb, 0, 1), np.ones((H, W))])
    img = Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA")
    head = _head(int(76 * k), accent)
    img.alpha_composite(head, (W - int(116 * k), H - int(88 * k)))
    return img, (l, r, t, b)


# ------------------------------------------------------------------ scrollbars

def _frames(img, count):
    """Split a vertical strip of `count` state frames."""
    w, h = img.size
    fh = h // count
    return [img.crop((0, i * fh, w, (i + 1) * fh)) for i in range(count)]


def _strip(frames):
    w, fh = frames[0].size
    out = Image.new("RGBA", (w, fh * len(frames)))
    for i, f in enumerate(frames):
        out.paste(f, (0, i * fh))
    return out


# Scrollbar thumb states: normal, hot (thumb hovered), pressed, disabled, hover (bar hovered)
_THUMB_GLOW = [0.55, 0.9, 1.0, 0.0, 0.7]


def scroll_thumb(img, count, accent, vertical):
    """Gunmetal thumb with a red rim, brighter red when hovered or dragged. Windows
    ships one thumb image per display scaling, so each keeps its size and its rounded
    shape (alpha); only the colors are redrawn. Returns the new strip."""
    acc = np.asarray(accent[:3], float) / 255
    frames = []
    for i, f in enumerate(_frames(img, count)):
        g = _THUMB_GLOW[i] if i < len(_THUMB_GLOW) else 0.55
        a = np.asarray(f.convert("RGBA")).astype(float) / 255
        h, w = a.shape[:2]
        across = w if vertical else h
        u = np.linspace(-1, 1, across)
        u = u[None, :] if vertical else u[:, None]
        k = max(1.0, across / 17)                            # this image's scaling
        cyl = 0.05 + 0.13 * (1 - u ** 2) + 0.04 * (u < -0.3)  # dark gunmetal cylinder
        rgb = np.repeat((cyl * np.ones((h, w)))[..., None], 3, -1) * np.array([1.0, 1.0, 1.06])
        solid = a[..., 3] > 0.5
        # rim: opaque pixels near the shape's edge across the thumb
        dist = (1 - np.abs(u)) * across / 2 * np.ones((h, w))
        rim = np.clip(1 - (dist - 1.2 * k) / (1.2 * k), 0, 1) * solid
        if g > 0:
            rgb = rgb * (1 - rim[..., None]) + rim[..., None] * acc * (0.45 + 0.55 * g)
            rgb = np.clip(rgb + g * 0.025 * acc, 0, 1)
        else:                                                # disabled: plain dark grey
            rgb = rgb * 0.7
        a[..., :3] = np.clip(rgb, 0, 1)
        frames.append(Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA"))
    return _strip(frames)


def scroll_track(img, count, accent):
    """Near-black track with a thin dark-red line on its outer edge (same size)."""
    acc = np.asarray(accent[:3], float) / 255
    frames = []
    for i, f in enumerate(_frames(img, count)):
        a = np.asarray(f.convert("RGBA")).astype(float) / 255
        a[..., :3] = 0.045 + (0.02 if i in (1, 2) else 0)
        a[..., 3] = 1
        if a.shape[1] > 1:                                    # vertical track: left edge column
            a[:, 0, :3] = acc * 0.40
        else:                                                 # horizontal track: top row
            a[0, :, :3] = acc * 0.40
        frames.append(Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA"))
    return _strip(frames)


def red_glyphs(img, accent):
    """Arrow buttons: light glyph pixels turn bright accent, the rest stays dark."""
    acc = np.asarray(accent[:3], float) / 255
    bright = np.clip(acc * 0.92 + 0.12, 0, 1)
    a = np.asarray(img.convert("RGBA")).astype(float) / 255
    L = a[..., :3].mean(-1, keepdims=True)
    vis = a[..., 3] > 0.5
    if vis.any() and L[vis].mean() > 0.5:                     # light art: dark glyph on light
        L = 1 - L
    if vis.mean() < 0.5:                                      # glyph on transparent: all of it
        t = np.ones_like(L)
    else:
        bg = np.median(L[vis])                                # the button's own background
        t = np.clip((L - bg - 0.06) / 0.22, 0, 1)             # glyph = clearly lighter than it
    a[..., :3] = np.clip((0.04 + L * 0.20) * (1 - t) + bright * t, 0, 1)
    return Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA")


# ------------------------------------------------------------------ Windows 11 (XAML) bars

def full_plate(W, H, accent, scale=1.0, line="top", rivets=True, seed=11):
    """A whole bar drawn at its final size, for Windhawk's XAML stylers (their image
    brushes stretch the full picture, there are no sizing margins). `line` puts the
    red trim on the edge facing the screen; rivets sit near both ends."""
    acc = np.asarray(accent[:3], float) / 255
    k = max(1.0, scale)
    rgb = _brushed(W, H, seed)
    e = max(1, int(round(k)))
    lw = max(1, int(round(1.6 * k)))
    gl = min(int(round(7 * k)), H // 2)
    glow = (np.linspace(1, 0, gl) ** 2 * 0.28)[:, None, None] * acc
    if line == "top":
        rgb[:gl] = np.clip(rgb[:gl] + glow, 0, 1)
        rgb[:lw] = np.clip(acc * 0.95 + 0.05, 0, 1)
        rgb[lw:lw + e] = np.clip(acc * 0.35, 0, 1)
        rgb[-e:] = 0.02
    else:
        rgb[-gl:] = np.clip(rgb[-gl:] + glow[::-1], 0, 1)
        rgb[-lw:] = np.clip(acc * 0.95 + 0.05, 0, 1)
        rgb[-lw - e:-lw] = np.clip(acc * 0.35, 0, 1)
        rgb[:e] = np.clip(rgb[:e] + 0.18, 0, 1)                # bevel highlight on top
    if rivets and W > 60 * k:
        rr = min(4.2 * k, H * 0.16)
        for x in (12 * k, W - 12 * k - 1):
            for y in ((H * 0.32, H * 0.72) if H > 8 * rr else (H / 2,)):
                _rivet(rgb, x, y, rr, acc)
    a = np.dstack([np.clip(rgb, 0, 1), np.ones((H, W))])
    return Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA")


def task_tile(state, accent, scale=1.0, w=56, h=42):
    """Windows 7-style taskbar button background (one per state), drawn at the display
    scaling: rounded gunmetal tile with a red rim that brightens with the state.
    states: running, hover, active, pressed, attention."""
    acc = np.asarray(accent[:3], float) / 255
    k = max(1.0, scale)
    W, H = int(w * k), int(h * k)
    glow, body, alpha = {"running": (0.25, 0.10, 0.55), "hover": (0.65, 0.16, 0.80),
                         "active": (0.85, 0.20, 0.92), "pressed": (1.0, 0.12, 0.95),
                         "attention": (1.0, 0.15, 0.95)}[state]
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    r = 4 * k
    dx = np.maximum(np.maximum(r - xx, xx - (W - 1 - r)), 0)
    dy = np.maximum(np.maximum(r - yy, yy - (H - 1 - r)), 0)
    inside = np.clip(r + 0.5 - np.hypot(dx, dy), 0, 1)                 # rounded corners
    edge = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy))
    rim = np.clip(1 - edge / (1.6 * k), 0, 1)
    y = yy / H
    base = body * (1.25 - 0.6 * y) + 0.10 * np.exp(-((y - 0.12) / 0.12) ** 2)   # top sheen
    rgb = np.repeat(base[..., None], 3, -1) + acc * (0.42 if state == "attention" else 0.04)
    rgb = rgb * (1 - rim[..., None]) + rim[..., None] * acc * glow
    under = np.exp(-((y - 1) / 0.18) ** 2)[..., None] * acc * glow * 0.45    # red glow from below
    rgb = np.clip(rgb + under, 0, 1)
    a = np.dstack([rgb, inside * alpha])
    return Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA")


def desktop_strip(state, accent, scale=1.0, w=15, h=48):
    """'Show desktop' strip at the right end of the taskbar."""
    acc = np.asarray(accent[:3], float) / 255
    k = max(1.0, scale)
    W, H = int(w * k), int(h * k)
    lvl = {"normal": 0.08, "hover": 0.20, "pressed": 0.12}[state]
    rgb = np.ones((H, W, 3)) * lvl
    rgb[:, :max(1, int(k))] = acc * (0.5 if state == "normal" else 0.95)   # red divider line
    if state != "normal":
        rgb[:, int(k):] += acc * 0.15
    a = np.dstack([np.clip(rgb, 0, 1), np.full((H, W), 0.9)])
    return Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA")
