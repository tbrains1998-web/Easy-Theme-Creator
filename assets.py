"""Make the extra theme parts: mouse pointers, sounds and desktop icons."""
import math
import os
import struct
import wave

from PIL import Image, ImageDraw, ImageFilter

DARK = (14, 14, 18, 255)

# ---------------------------------------------------------------- pointers
# Shapes use a 32 x 32 grid. Each pointer: (file name, theme key, shape, hotspot).


def _rot(points, deg, cx=16, cy=16):
    a = math.radians(deg)
    return [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a),
             cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in points]


ARROW = [(3, 2), (3, 25), (9, 20), (13, 29), (17, 27), (13, 19), (21, 19)]
DOUBLE = [(3, 16), (9, 10), (9, 14), (23, 14), (23, 10), (29, 16),
          (23, 22), (23, 18), (9, 18), (9, 22)]
FOUR = [(16, 2), (21, 7), (18, 7), (18, 14), (25, 14), (25, 11), (30, 16), (25, 21),
        (25, 18), (18, 18), (18, 25), (21, 25), (16, 30), (11, 25), (14, 25), (14, 18),
        (7, 18), (7, 21), (2, 16), (7, 11), (7, 14), (14, 14), (14, 7), (11, 7)]
UP = [(16, 2), (25, 12), (19, 12), (19, 29), (13, 29), (13, 12), (7, 12)]
IBEAM = [(10, 3), (22, 3), (22, 6), (18, 6), (18, 26), (22, 26), (22, 29), (10, 29),
         (10, 26), (14, 26), (14, 6), (10, 6)]
HAND = [(12, 2), (16, 2), (16, 12), (24, 13), (26, 16), (25, 26), (21, 30), (12, 30),
        (6, 22), (6, 17), (9, 17), (12, 21)]
CROSS = [(14, 2), (18, 2), (18, 14), (30, 14), (30, 18), (18, 18), (18, 30), (14, 30),
         (14, 18), (2, 18), (2, 14), (14, 14)]

POINTERS = [
    ("arrow", "Arrow", [ARROW], (3, 2)),
    ("help", "Help", [ARROW, "help"], (3, 2)),
    ("working", "AppStarting", [ARROW, "ring_small"], (3, 2)),
    ("busy", "Wait", ["ring"], (16, 16)),
    ("cross", "Crosshair", [CROSS], (16, 16)),
    ("text", "IBeam", [IBEAM], (16, 16)),
    ("pen", "NWPen", [ARROW], (3, 2)),
    ("no", "No", ["no"], (16, 16)),
    ("size_ns", "SizeNS", [_rot(DOUBLE, 90)], (16, 16)),
    ("size_we", "SizeWE", [DOUBLE], (16, 16)),
    ("size_nwse", "SizeNWSE", [_rot(DOUBLE, 45)], (16, 16)),
    ("size_nesw", "SizeNESW", [_rot(DOUBLE, -45)], (16, 16)),
    ("move", "SizeAll", [FOUR], (16, 16)),
    ("up", "UpArrow", [UP], (16, 2)),
    ("link", "Hand", [HAND], (14, 2)),
]


def _draw_pointer(shapes, accent, px):
    """Draw one pointer at px x px with a soft glow in the accent color."""
    big = px * 4
    k = big / 32
    shape = Image.new("RGBA", (big, big))
    d = ImageDraw.Draw(shape)
    line = max(2, round(1.6 * k))
    for s in shapes:
        if s == "ring" or s == "ring_small":
            c, r = ((16, 16), 12) if s == "ring" else ((24, 24), 6)
            box = [(c[0] - r) * k, (c[1] - r) * k, (c[0] + r) * k, (c[1] + r) * k]
            d.ellipse(box, outline=DARK, width=round(r * 0.5 * k))
            d.arc(box, -90, 180, fill=accent, width=round(r * 0.5 * k))
        elif s == "no":
            box = [4 * k, 4 * k, 28 * k, 28 * k]
            d.ellipse(box, outline=accent, width=round(4 * k))
            d.line([(9 * k, 23 * k), (23 * k, 9 * k)], fill=accent, width=round(4 * k))
        elif s == "help":
            d.ellipse([19 * k, 2 * k, 31 * k, 14 * k], fill=DARK, outline=accent, width=line)
            d.arc([22.5 * k, 4.5 * k, 27.5 * k, 9.5 * k], 180, 90, fill=accent, width=line)
            d.ellipse([24.3 * k, 10.5 * k, 26.3 * k, 12.5 * k], fill=accent)
        else:
            d.polygon([(x * k, y * k) for x, y in s], fill=DARK, outline=accent, width=line)
    glow = Image.new("RGBA", (big, big), accent[:3] + (0,))
    glow.putalpha(shape.getchannel("A").filter(ImageFilter.GaussianBlur(1.2 * k)))
    out = Image.alpha_composite(glow, shape)
    return out.resize((px, px), Image.LANCZOS)


def _write_cur(path, images, hotspot):
    """Save RGBA images as a Windows .cur file (classic bitmap format)."""
    blobs = []
    for img in images:
        w, h = img.size
        header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
        rows = [img.crop((0, y, w, y + 1)).tobytes("raw", "BGRA") for y in range(h - 1, -1, -1)]
        mask = b"\x00" * (((w + 31) // 32) * 4 * h)
        blobs.append(header + b"".join(rows) + mask)
    out = struct.pack("<HHH", 0, 2, len(images))
    offset = 6 + 16 * len(images)
    for img, blob in zip(images, blobs):
        w, h = img.size
        hx, hy = round(hotspot[0] * w / 32), round(hotspot[1] * h / 32)
        out += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, hx, hy, len(blob), offset)
        offset += len(blob)
    with open(path, "wb") as f:
        f.write(out + b"".join(blobs))


def make_pointers(folder, accent):
    """Write all .cur files. Returns {theme key: file path}."""
    os.makedirs(folder, exist_ok=True)
    result = {}
    for name, key, shapes, hot in POINTERS:
        path = os.path.join(folder, name + ".cur")
        _write_cur(path, [_draw_pointer(shapes, accent, s) for s in (32, 48, 64)], hot)
        result[key] = path
    return result


# ------------------------------------------------------------------- icons

def _tile(accent, size=512):
    """Dark rounded tile with a glowing accent edge."""
    img = Image.new("RGBA", (size, size))
    glow = Image.new("RGBA", (size, size), accent[:3] + (0,))
    edge = Image.new("L", (size, size))
    ImageDraw.Draw(edge).rounded_rectangle([40, 40, size - 40, size - 40], 90,
                                           outline=255, width=24)
    glow.putalpha(edge.filter(ImageFilter.GaussianBlur(18)))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, size - 40, size - 40], 90, fill=(20, 20, 26, 255),
                        outline=accent, width=10)
    return img, d


def _icon_image(kind, accent):
    img, d = _tile(accent)
    w = 22
    if kind == "pc":
        d.rounded_rectangle([120, 130, 392, 320], 18, outline=accent, width=w)
        d.line([(256, 320), (256, 375)], fill=accent, width=w)
        d.line([(180, 385), (332, 385)], fill=accent, width=w)
    elif kind in ("bin_empty", "bin_full"):
        d.line([(140, 165), (372, 165)], fill=accent, width=w)
        d.rectangle([220, 125, 292, 165], outline=accent, width=w)
        d.polygon([(165, 190), (347, 190), (325, 395), (187, 395)], outline=accent, width=w)
        if kind == "bin_full":
            for x in (215, 256, 297):
                d.line([(x, 225), (x, 360)], fill=accent, width=14)
    elif kind == "network":
        d.ellipse([126, 126, 386, 386], outline=accent, width=w)
        d.ellipse([196, 126, 316, 386], outline=accent, width=w // 2 + 4)
        d.line([(126, 256), (386, 256)], fill=accent, width=w // 2 + 4)
    elif kind == "user":
        d.polygon([(120, 160), (220, 160), (245, 190), (392, 190), (392, 370), (120, 370)],
                  outline=accent, width=w)
        d.line([(120, 225), (392, 225)], fill=accent, width=w // 2 + 4)
    return img


ICONS = ["pc", "bin_empty", "bin_full", "network", "user"]


def make_icons(folder, accent):
    """Write .ico files for the desktop icons. Returns {kind: file path}."""
    os.makedirs(folder, exist_ok=True)
    result = {}
    for kind in ICONS:
        path = os.path.join(folder, kind + ".ico")
        _icon_image(kind, accent).resize((256, 256), Image.LANCZOS).save(
            path, sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
        result[kind] = path
    return result


# ------------------------------------------------------------------ sounds
# Short techy tones: each is a list of (start Hz, end Hz, seconds).

SOUNDS = {
    "startup": [(440, 440, .12), (554, 554, .12), (659, 659, .12), (880, 1320, .45)],
    "notify": [(988, 988, .09), (1319, 1319, .22)],
    "default": [(880, 660, .14)],
    "warning": [(660, 660, .12), (660, 660, .18)],
    "error": [(330, 300, .16), (220, 180, .3)],
    "plug_in": [(500, 1000, .16)],
    "unplug": [(1000, 500, .16)],
}

# Which Windows events use which sound: (app, event, our sound)
SOUND_EVENTS = [
    (".Default", ".Default", "default"),
    (".Default", "SystemAsterisk", "notify"),
    (".Default", "SystemNotification", "notify"),
    (".Default", "Notification.Default", "notify"),
    (".Default", "SystemExclamation", "warning"),
    (".Default", "SystemHand", "error"),
    (".Default", "DeviceConnect", "plug_in"),
    (".Default", "DeviceDisconnect", "unplug"),
    (".Default", "WindowsLogon", "startup"),
]


def _tone(notes, rate=44100):
    samples = []
    for f0, f1, secs in notes:
        n = int(rate * secs)
        phase = 0.0
        for i in range(n):
            t = i / n
            phase += 2 * math.pi * (f0 + (f1 - f0) * t) / rate
            env = min(1.0, i / (rate * .005)) * (1 - t) ** 2
            v = math.sin(phase) * .7 + math.sin(phase * 2) * .2 + math.sin(phase * 3) * .1
            samples.append(int(v * env * 0.6 * 32767))
    return struct.pack("<%dh" % len(samples), *samples)


def make_sounds(folder):
    """Write .wav files. Returns {sound name: file path}."""
    os.makedirs(folder, exist_ok=True)
    result = {}
    for name, notes in SOUNDS.items():
        path = os.path.join(folder, name + ".wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(_tone(notes))
        result[name] = path
    return result


# ----------------------------------------------------------------- preview

def preview(accent, width=520):
    """A small picture showing some pointers and icons, for the app window."""
    picks = ["arrow", "link", "busy", "text", "move", "no"]
    items = [_draw_pointer(p[2], accent, 48) for p in POINTERS if p[0] in picks]
    items += [_icon_image(k, accent).resize((48, 48), Image.LANCZOS) for k in ICONS]
    img = Image.new("RGBA", (width, 64), (40, 40, 48, 255))
    step = width // len(items)
    for i, it in enumerate(items):
        img.alpha_composite(it, (i * step + (step - 48) // 2, 8))
    return img
