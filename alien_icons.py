"""Alien-style folder icons in any color: an upright black glossy case with a
claw emblem, plus a 3D badge object per special folder (like the old Win7
Alienware pack). Only the theme's colors are used, never the picture itself.
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _scale(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _vivid(c):
    """Same hue, pushed to full brightness, so dark palette colors still glow."""
    m = max(c[:3]) or 1
    return _scale(c, 255 / m)


class Painter:
    def __init__(self, accent, dark=(10, 10, 12), size=512):
        self.S = size
        self.K = size / 256
        a = _vivid(accent)
        d = tuple(min(v, 60) for v in dark[:3])           # base stays dark whatever the palette
        self.c = {
            "glow": a,                                    # was (235, 18, 18)
            "side_top": _scale(a, 0.50), "side_bot": _scale(a, 0.17),
            "face_top": _mix((44, 44, 48), d, 0.35), "face_bot": _mix((8, 8, 9), d, 0.25),
            "strip": _mix((16, 16, 18), d, 0.3),
            "led": _scale(a, 0.82), "led_dim": _scale(a, 0.36),
            "rim": _scale(a, 0.62), "line": _scale(a, 0.66),
            "claw": _mix(a, (255, 255, 255), 0.08),
            "badge_top": _mix(a, (255, 255, 255), 0.15), "badge_bot": _scale(a, 0.6),
            "metal_top": _mix((80, 80, 86), d, 0.3), "metal_bot": (10, 10, 12),
            "edge": _scale(a, 0.82),
        }
        self._case = None

    # -------------------------------------------------------- helpers
    def P(self, pts):
        return [(x * self.K, y * self.K) for x, y in pts]

    def B(self, box):
        return [v * self.K for v in box]

    def new(self, mode="L"):
        return Image.new(mode, (self.S, self.S), 0 if mode == "L" else (0, 0, 0, 0))

    def vgrad(self, top, bot):
        g = Image.linear_gradient("L").resize((self.S, self.S))
        return Image.composite(Image.new("RGBA", (self.S, self.S), bot + (255,)),
                               Image.new("RGBA", (self.S, self.S), top + (255,)), g)

    def fill(self, mask, src):
        out = self.new("RGBA")
        out.paste(src, (0, 0), mask)
        return out

    def solid(self, c):
        return Image.new("RGBA", (self.S, self.S), c + (255,))

    def glow(self, layer, r, strength=2):
        a = layer.filter(ImageFilter.GaussianBlur(r * self.K))
        for _ in range(strength - 1):
            a = ImageChops.add(a, a)
        return a

    def edge(self, mask, w):
        big = mask.filter(ImageFilter.MaxFilter(int(w * self.K) | 1))
        return ImageChops.subtract(big, mask)

    def shadow(self, mask, off=4, r=5, a=200):
        m = mask.filter(ImageFilter.GaussianBlur(r * self.K)).point(lambda v: v * a // 255)
        sh = self.new("RGBA")
        sh.paste((0, 0, 0, 255), (int(off * self.K), int(off * self.K)), m)
        return sh

    def stack(self, *layers):
        img = self.new("RGBA")
        for layer in layers:
            img = Image.alpha_composite(img, layer)
        return img

    # -------------------------------------------------------- the case
    def case(self):
        if self._case is not None:
            return self._case
        c, P, B, K = self.c, self.P, self.B, self.K
        face, side = self.new(), self.new()
        ImageDraw.Draw(face).rounded_rectangle(B([34, 14, 184, 236]), int(10 * K), fill=255)
        ImageDraw.Draw(side).polygon(P([(184, 22), (210, 34), (210, 230), (184, 236)]), fill=255)
        gloss = self.new()
        ImageDraw.Draw(gloss).polygon(P([(34, 14), (150, 14), (34, 150)]), fill=60)
        gloss = ImageChops.multiply(gloss, face)
        img = self.stack(self.shadow(ImageChops.lighter(face, side), 5, 7),
                         self.fill(side, self.vgrad(c["side_top"], c["side_bot"])),
                         self.fill(face, self.vgrad(c["face_top"], c["face_bot"])),
                         self.fill(gloss, self.solid((255, 255, 255))))
        d = ImageDraw.Draw(img)
        d.rectangle(B([46, 26, 172, 48]), fill=c["strip"] + (255,))
        for i, x in enumerate(range(52, 168, 14)):
            d.rectangle(B([x, 32, x + 9, 42]), fill=(c["led"] if i % 3 else c["led_dim"]) + (255,))
        neon = self.new("RGBA")
        n = ImageDraw.Draw(neon)
        n.rounded_rectangle(B([34, 14, 184, 236]), int(10 * K), outline=c["rim"] + (255,), width=int(2 * K))
        n.line(P([(184, 22), (210, 34), (210, 230)]), fill=c["glow"] + (255,), width=int(3 * K))
        n.line(P([(38, 60), (180, 60)]), fill=c["line"] + (255,), width=int(2 * K))
        for i in range(3):                                # claw: three tapered blades
            ox = 70 + i * 26
            left, right = [], []
            for t in range(13):
                u = t / 12
                x = ox + 34 * (1 - u) ** 1.6 - 30 * u
                y = 76 + 140 * u
                w = (7 - i) * math.sin(math.pi * min(1, u * 1.15 + 0.05))
                left.append((x - w, y))
                right.append((x + w, y))
            n.polygon(P(left + right[::-1]), fill=c["claw"] + (255,))
        self._case = self.stack(img, self.glow(neon, 6), neon)
        return self._case

    # -------------------------------------------------------- badges
    def obj(self, draw):
        c = self.c
        M, R, Wt = self.new(), self.new(), self.new()
        draw(self, ImageDraw.Draw(M), ImageDraw.Draw(R), ImageDraw.Draw(Wt))
        allm = ImageChops.lighter(ImageChops.lighter(M, R), Wt)
        redl = self.fill(R, self.vgrad(c["badge_top"], c["badge_bot"]))
        return self.stack(self.shadow(allm, 4, 5, 230),
                          self.fill(M, self.vgrad(c["metal_top"], c["metal_bot"])),
                          self.fill(self.edge(M, 3), self.solid(c["edge"])),
                          self.glow(redl, 4), redl,
                          self.fill(Wt, self.solid((245, 245, 245))))

    def icon(self, kind=None):
        """RGBA image (size x size) for a folder kind (None = plain folder)."""
        fn = BADGES.get(kind)
        base = self.case()
        return base if fn is None else Image.alpha_composite(base, self.obj(fn))


# Badge shapes on a 256 grid. Each paints Metal (m), Accent (r) and White (w) masks.
def alien(s, m, r, w):
    P, B = s.P, s.B
    m.ellipse(B([118, 116, 228, 248]), fill=255)
    m.polygon(P([(130, 200), (173, 250), (216, 200)]), fill=255)
    r.polygon(P([(132, 176), (160, 170), (168, 202), (146, 200)]), fill=255)
    r.polygon(P([(214, 176), (186, 170), (178, 202), (200, 200)]), fill=255)
    w.ellipse(B([140, 126, 160, 136]), fill=255)


def monitor(s, m, r, w):
    P, B = s.P, s.B
    m.rectangle(B([110, 132, 244, 222]), fill=255)
    r.rectangle(B([120, 142, 234, 212]), fill=255)
    m.polygon(P([(162, 222), (192, 222), (204, 246), (150, 246)]), fill=255)
    w.polygon(P([(124, 146), (170, 146), (124, 186)]), fill=110)


def docs(s, m, r, w):
    P, B = s.P, s.B
    for i, c in enumerate((m, m, None)):
        x, y = 128 + i * 12, 118 + i * 10
        (c or w).polygon(P([(x, y), (x + 70, y), (x + 92, y + 22), (x + 92, y + 112), (x, y + 112)]), fill=255)
    for i in range(5):
        w.rectangle(B([166, 166 + i * 14, 236, 172 + i * 14]), fill=0)
        r.rectangle(B([166, 166 + i * 14, 236, 172 + i * 14]), fill=255)


def download(s, m, r, w):
    P, B, K = s.P, s.B, s.K
    r.rectangle(B([158, 112, 196, 176]), fill=255)
    r.polygon(P([(130, 172), (224, 172), (177, 222)]), fill=255)
    m.rounded_rectangle(B([116, 216, 240, 244]), int(6 * K), fill=255)
    w.rectangle(B([164, 116, 172, 168]), fill=150)


def star(s, m, r, w):
    pts = []
    for i in range(10):
        rr = 66 if i % 2 == 0 else 28
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((178 + rr * math.cos(a), 186 + rr * math.sin(a)))
    m.polygon(s.P(pts), fill=255)
    r.polygon(s.P([(178 + (x - 178) * .62, 186 + (y - 186) * .62) for x, y in pts]), fill=255)


def link(s, m, r, w):
    P = s.P
    m.polygon(P([(116, 236), (196, 156), (176, 136), (240, 120), (224, 184), (204, 164), (124, 244)]), fill=255)
    r.polygon(P([(132, 228), (200, 160), (190, 150), (226, 136), (216, 170), (206, 160), (138, 230)]), fill=255)


def headphones(s, m, r, w):
    P, B, K = s.P, s.B, s.K
    m.arc(B([118, 104, 238, 224]), 180, 360, fill=255, width=int(12 * K))
    m.line(P([(124, 164), (124, 196)]), fill=255, width=int(12 * K))
    m.line(P([(232, 164), (232, 196)]), fill=255, width=int(12 * K))
    for x in (106, 206):
        m.rounded_rectangle(B([x, 176, x + 44, 244]), int(14 * K), fill=255)
        r.rounded_rectangle(B([x + 8, 186, x + 36, 234]), int(10 * K), fill=255)
    w.ellipse(B([116, 188, 124, 204]), fill=200)


def camera(s, m, r, w):
    B, K = s.B, s.K
    m.rounded_rectangle(B([106, 148, 246, 240]), int(10 * K), fill=255)
    m.rectangle(B([146, 132, 196, 150]), fill=255)
    r.rectangle(B([212, 140, 236, 150]), fill=255)
    m.ellipse(B([140, 158, 218, 236]), fill=255)
    r.ellipse(B([152, 170, 206, 224]), fill=255)
    w.ellipse(B([162, 178, 176, 192]), fill=255)


def gamepad(s, m, r, w):
    B, K = s.B, s.K
    m.rounded_rectangle(B([104, 150, 248, 214]), int(30 * K), fill=255)
    m.ellipse(B([104, 176, 156, 246]), fill=255)
    m.ellipse(B([196, 176, 248, 246]), fill=255)
    r.rectangle(B([126, 176, 158, 186]), fill=255)
    r.rectangle(B([137, 165, 147, 197]), fill=255)
    for x, y in ((206, 166), (222, 180), (190, 180), (206, 194)):
        r.ellipse(B([x, y, x + 12, y + 12]), fill=255)
    w.ellipse(B([164, 172, 188, 184]), fill=180)


def magnifier(s, m, r, w):
    P, B, K = s.P, s.B, s.K
    m.line(P([(196, 200), (238, 242)]), fill=255, width=int(20 * K))
    m.ellipse(B([108, 112, 210, 214]), fill=255)
    r.ellipse(B([122, 126, 196, 200]), fill=255)
    w.chord(B([132, 134, 186, 188]), 200, 280, fill=200)


def film(s, m, r, w):
    P, B = s.P, s.B
    m.rectangle(B([108, 120, 244, 244]), fill=255)
    r.rectangle(B([130, 134, 222, 230]), fill=255)
    for y in range(126, 240, 18):
        w.rectangle(B([114, y, 124, y + 10]), fill=255)
        w.rectangle(B([228, y, 238, y + 10]), fill=255)
    w.polygon(P([(162, 162), (198, 182), (162, 202)]), fill=255)


def cube(s, m, r, w):
    P = s.P
    t, lft, rgt, c = (178, 112), (114, 146), (242, 146), (178, 180)
    w.polygon(P([t, rgt, c, lft]), fill=255)
    r.polygon(P([lft, c, (178, 248), (114, 214)]), fill=255)
    m.polygon(P([c, rgt, (242, 214), (178, 248)]), fill=255)


BADGES = {None: None, "folder": None, "desktop": monitor, "documents": docs, "downloads": download,
          "music": headphones, "pictures": camera, "videos": film, "favorites": star,
          "links": link, "saved-games": gamepad, "searches": magnifier, "contacts": alien,
          "3d-objects": cube}


# ---- shell places (This PC, Network, Home, Gallery, OneDrive) ----
def pc(s, m, r, w):
    P, B, K = s.P, s.B, s.K
    m.rounded_rectangle(B([104, 120, 248, 206]), int(6 * K), fill=255)
    r.rectangle(B([114, 130, 238, 196]), fill=255)
    w.polygon(P([(118, 134), (170, 134), (118, 170)]), fill=90)
    m.polygon(P([(160, 206), (192, 206), (200, 228), (152, 228)]), fill=255)
    m.rounded_rectangle(B([128, 226, 224, 240]), int(5 * K), fill=255)


def globe(s, m, r, w):
    B, K = s.B, s.K
    m.ellipse(B([108, 116, 244, 252]), fill=255)
    r.ellipse(B([118, 126, 234, 242]), fill=255)
    for box in ([150, 126, 202, 242], [118, 168, 234, 200]):
        w.ellipse(B(box), outline=200, width=int(4 * K))
    w.line(B([176, 126, 176, 242]), fill=200, width=int(4 * K))
    w.line(B([118, 184, 234, 184]), fill=200, width=int(4 * K))


def house(s, m, r, w):
    P, B = s.P, s.B
    m.polygon(P([(176, 108), (250, 170), (232, 170), (232, 244), (120, 244), (120, 170), (102, 170)]), fill=255)
    r.polygon(P([(176, 124), (220, 162), (220, 232), (132, 232), (132, 162)]), fill=255)
    m.rectangle(B([162, 194, 190, 244]), fill=255)
    w.rectangle(B([168, 200, 184, 240]), fill=80)


def gallery(s, m, r, w):
    P, B, K = s.P, s.B, s.K
    m.rounded_rectangle(B([120, 112, 248, 216]), int(6 * K), fill=255)       # back photo
    m.rounded_rectangle(B([104, 136, 232, 244]), int(6 * K), fill=255)       # front photo
    r.rectangle(B([114, 146, 222, 234]), fill=255)
    w.polygon(P([(120, 228), (156, 184), (178, 210), (194, 196), (218, 228)]), fill=210)
    w.ellipse(B([188, 156, 206, 174]), fill=230)


def cloud(s, m, r, w):
    B = s.B
    for box in ([104, 168, 172, 236], [140, 128, 222, 210], [184, 160, 248, 236], [124, 196, 230, 238]):
        m.ellipse(B(box), fill=255)
    for box in ([114, 178, 164, 228], [150, 138, 212, 200], [192, 170, 238, 228], [134, 200, 222, 230]):
        r.ellipse(B(box), fill=255)
    w.ellipse(B([162, 146, 186, 162]), fill=120)


BADGES.update({"pc": pc, "network": globe, "home": house, "gallery": gallery, "onedrive": cloud})


def drive_icon(painter):
    """A standalone drive icon: flat black metal drive body, vents, glowing accent light."""
    s, c = painter, painter.c
    P, B, K = s.P, s.B, s.K
    body = s.new()
    ImageDraw.Draw(body).rounded_rectangle(B([20, 92, 236, 186]), int(14 * K), fill=255)
    front = s.new()
    ImageDraw.Draw(front).rounded_rectangle(B([20, 150, 236, 186]), int(10 * K), fill=255)
    gloss = s.new()
    ImageDraw.Draw(gloss).rounded_rectangle(B([28, 98, 228, 122]), int(10 * K), fill=50)
    img = s.stack(s.shadow(body, 5, 7),
                  s.fill(body, s.vgrad(c["face_top"], c["face_bot"])),
                  s.fill(front, s.vgrad(c["metal_top"], c["metal_bot"])),
                  s.fill(gloss, s.solid((255, 255, 255))))
    d = ImageDraw.Draw(img)
    for i in range(10):                                         # vent slots
        x = 40 + i * 12
        d.rounded_rectangle(B([x, 160, x + 6, 176]), int(2 * K), fill=(6, 6, 7, 255))
    neon = s.new("RGBA")
    n = ImageDraw.Draw(neon)
    n.rounded_rectangle(B([20, 92, 236, 186]), int(14 * K), outline=c["rim"] + (255,), width=int(2 * K))
    n.ellipse(B([200, 160, 216, 176]), fill=c["glow"] + (255,))                  # activity light
    n.line(P([(34, 148), (222, 148)]), fill=c["line"] + (255,), width=int(2 * K))
    return s.stack(img, s.glow(neon, 5), neon)
