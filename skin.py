"""Window skin: repaint Windows' own visual style (.msstyles) in the picture's colors.

Copies this PC's stock aero.msstyles, recolors its ~1,600 images and its color
table (frames, buttons, scrollbars, menus, Explorer bars, taskbar...), saves it
under %ProgramData%\\EasyThemeCreator\\skins\\<name>-<time>\\<name>\\ and switches
Windows to it.

Windows only loads a skin it did not sign itself when a theme patcher is
installed (SecureUxTheme). Where the skin lives matters: copies put in
C:\\Windows\\Resources\\Themes went missing after a restart, and skins inside the
user profile (AppData) fail with "path not found" (0x90070003).
"""
import ctypes
import ctypes.wintypes as wt
import io
import os
import shutil
import struct
import time
import winreg

import numpy as np
from PIL import Image

STOCK = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Resources", "Themes", "aero")
STOCK_STYLE = os.path.join(STOCK, "aero.msstyles")
# Windows refuses skins inside the user profile (AppData gives "path not found",
# 0x90070003) but loads them from ProgramData or another drive.
SKINS = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "EasyThemeCreator", "skins")
PATCHER_DLL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "SecureUxTheme4.dll")


def patcher_installed():
    return os.path.exists(PATCHER_DLL)


def patcher_needs_restart():
    """SecureUxTheme only takes effect after a restart. True when it was installed
    after Windows last started (then the skin would silently not show)."""
    if not patcher_installed():
        return False
    k32 = ctypes.windll.kernel32
    k32.GetTickCount64.restype = ctypes.c_ulonglong
    booted = time.time() - k32.GetTickCount64() / 1000
    # The DLL keeps its build date, so use when SecureUxTheme's uninstall entry was written.
    root = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as k:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    return False
                i += 1
                with winreg.OpenKey(k, sub) as e:
                    try:
                        if winreg.QueryValueEx(e, "DisplayName")[0] != "SecureUxTheme":
                            continue
                    except OSError:
                        continue
                    written = winreg.QueryInfoKey(e)[2] / 1e7 - 11644473600   # FILETIME -> unix
                    return written > booted + 60
    except OSError:
        return False


def current_style():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\ThemeManager") as k:
            return winreg.QueryValueEx(k, "DllName")[0]
    except OSError:
        return STOCK_STYLE


# ------------------------------------------------------------------ colors

def _hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    d = mx - mn
    m = d > 1e-6
    safe = np.where(m, d, 1)
    rc, gc, bc = (mx - r) / safe, (mx - g) / safe, (mx - b) / safe
    h = np.where(r == mx, bc - gc, np.where(g == mx, 2.0 + rc - bc, 4.0 + gc - rc))
    h = np.where(m, (h / 6.0) % 1.0, 0)
    s = np.where(mx > 1e-6, d / np.where(mx > 1e-6, mx, 1), 0)
    return h, s, mx


def _rgb(h, s, v):
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    out = np.zeros(h.shape + (3,))
    for k, (a, b, c) in enumerate([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]):
        sel = i == k
        out[sel, 0], out[sel, 1], out[sel, 2] = a[sel], b[sel], c[sel]
    return out


class Painter:
    """Recolors pixels: Windows' blue/green accents become the accent color,
    dark-mode art gets a dark tint of it, window frames go dark with a glow."""

    def __init__(self, accent_hex, strength=1.0):
        acc = np.array([int(accent_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], float) / 255
        self.dir = acc / max(acc.max(), 1e-6)       # brightest channel = 1
        self.hue = float(_hsv(acc[None, :])[0][0])
        self.strength = strength

    def paint(self, rgb, mode):
        h, s, v = _hsv(rgb)
        accent = (s > 0.18) & (h > 70 / 360) & (h < 290 / 360)
        out = rgb.copy()
        if accent.any():
            new = _rgb(np.full(h.shape, self.hue), np.clip(s * 1.1, 0, 1), np.clip(v * 0.95, 0, 1))
            if mode == "invert":           # links on a now-black page: bright accent
                new = np.clip(new * 0.6 + 0.4 * np.maximum(new, 0.85), 0, 1)
            out[accent] = new[accent]
        grey = ~accent
        L = out.mean(-1)
        if mode == "dark":
            k = 0.12 * self.strength * (1 - L)       # faint cast, none at white (text stays readable)
            tint = L[..., None] * ((1 - k)[..., None] + k[..., None] * self.dir * 1.6)
            tint = tint * (0.78 + 0.22 * L)[..., None]   # mostly black: darks get darker
            out[grey] = np.clip(tint, 0, 1)[grey]
        elif mode in ("invert", "track"):   # light-only art (Control Panel, light progress bars): white -> near black
            nl = np.where(L > 0.5, 0.05 + (1 - L) * 0.18, 0.88 - L * 0.4)
            if mode == "track":              # mid-grey like Windows' dark bar, so it shows on dark pages
                nl = 0.30 - L * 0.12
            tint = nl[..., None] * (0.96 + self.dir * 0.05)
            out[grey] = np.clip(tint, 0, 1)[grey]
        elif mode == "frame":
            nl = 0.04 + (1 - L) * 0.22
            tint = nl[..., None] * (0.8 + self.dir * 0.45)
            out[grey] = np.clip(tint, 0, 1)[grey]
        return out

    def metal(self, a):
        """Brushed gunmetal: dark grey with a soft sheen near the top, fine horizontal
        streaks (rows vary, so stretching keeps the brushed look) and a thin accent
        line on the bottom edge."""
        h, w = a.shape[:2]
        y = np.linspace(0, 1, h)[:, None]
        rng = np.random.default_rng(h * 131 + w)
        streak = rng.normal(0, 1, (h, 1)) * 0.012 + rng.normal(0, 1, (h, w)) * 0.004
        L = 0.075 + 0.085 * np.exp(-((y - 0.2) / 0.3) ** 2) + streak
        rgb = np.clip(np.repeat(L[..., None], 3, -1) * np.array([1.0, 1.0, 1.06]), 0, 1)
        if h >= 8:
            rgb[-1] = np.clip(self.dir * 0.55, 0, 1)
            rgb[0] = np.clip(rgb[0] + 0.08, 0, 1)            # bevel highlight on top
        a[..., :3] = rgb
        return a

    def png(self, data, mode):
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        a = np.asarray(im).astype(np.float64) / 255
        if mode == "metal":
            solid = (a[..., 3] > 0.8).mean() > 0.8
            if solid and min(a.shape[:2]) >= 1 and max(a.shape[:2]) >= 6:
                a = self.metal(a.copy())
                b = io.BytesIO()
                Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(b, "PNG")
                return b.getvalue()
            # glyphs (arrows, dividers): dark ones must turn light to show on the metal
            vis = a[..., 3] > 0.3
            mode = "invert" if vis.any() and a[..., :3][vis].mean() < 0.5 else "dark"
        a[..., :3] = self.paint(a[..., :3], mode)
        b = io.BytesIO()
        Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(b, "PNG")
        return b.getvalue()

    def text_accent(self):
        """Saturated accent that still reads on near-black (e.g. #FF4E4E for red)."""
        return tuple(int(v) for v in np.clip(self.dir * 235 + 30, 0, 255))

    def readable(self, val, prop, state):
        """Colors for light-only screens made dark: backgrounds dark gunmetal, body text
        near-white, secondary text light grey, links/titles bright accent. Never dark text."""
        r, g, b = val & 255, (val >> 8) & 255, (val >> 16) & 255
        L = (r + g + b) / 765
        sat = (max(r, g, b) - min(r, g, b)) / 255
        if prop in FILL_PROPS:
            return (val & 0xFF000000) | _ref((24, 24, 27) if prop == 3810 else (16, 16, 18))
        if prop in BORDER_PROPS:
            return (val & 0xFF000000) | _ref((60, 60, 64))
        acc = np.clip(self.dir * 255, 0, 255)
        bright = tuple(int(v) for v in np.clip(acc * 0.75 + 255 * 0.29, 0, 255))   # e.g. #FF4A4A
        if state == 4:                                    # disabled
            return (val & 0xFF000000) | _ref((138, 138, 138))
        if sat > 0.25:                                    # links and titles
            hot = state in (2, 3)
            return (val & 0xFF000000) | _ref(tuple(min(255, int(v * (1.15 if hot else 1))) for v in bright))
        if L < 0.45 or L > 0.75:                          # main text (dark or already light)
            return (val & 0xFF000000) | _ref((230, 230, 230))
        return (val & 0xFF000000) | _ref((176, 176, 176))

    def colorref(self, val, mode="hue"):
        px = np.array([[val & 255, (val >> 8) & 255, (val >> 16) & 255]], float) / 255
        o = (np.clip(self.paint(px, "invert" if mode == "invert" else "hue")[0], 0, 1) * 255 + 0.5).astype(int)
        return (val & 0xFF000000) | int(o[0]) | int(o[1]) << 8 | int(o[2]) << 16


# Bars that get brushed-gunmetal backgrounds: column headers, toolbars, command bars,
# status bars. Only solid background images are textured; glyphs keep their art.
METAL = {"header", "itemsview::header", "itemsviewaccessible::header", "darkmode_itemsview::header",
         "darkmode_itemsviewaccessible::header", "darkmode_darktheme::header", "rebar",
         "darkmode_darktheme::rebar", "toolbar", "darkmode_darktheme::toolbar", "commandmodule",
         "darkmode::commandmodule", "explorer::commandmodule", "darkmode_explorer::commandmodule",
         "cplcommandmodule::commandmodule", "status", "darkmode_darktheme::status",
         "explorerstatusbar", "navigation", "darkmode::navigation"}

# Light-only classes that ignore dark mode (classic Control Panel and its command bar).
LIGHT_ONLY = {"controlpanelstyle", "controlpanel", "uisubsetfooter::controlpanel",
              "explorer::controlpanel", "cplcommandmodule::commandmodule", "commandmodule",
              "explorer::commandmodule",
              # light file/program lists (Control Panel's Programs and Features uses these)
              "itemsview", "explorer::itemsview", "itemsview::listview", "listview",
              "explorer::listview",
              "previewpane"}      # the bottom details panel's text (its background is the emblem art)


FILL_PROPS = {3802, 3810, 3811, 3812, 3821}      # FILLCOLOR, gradients, FILLCOLORHINT
BORDER_PROPS = {3801, 3822}                       # BORDERCOLOR, BORDERCOLORHINT

# Light progress bars. Explorer draws This PC's drive-space bars with these even in
# dark mode, so their light grey track turns dark; the filled part keeps the accent.
TRACK = {"progress"}


# Armor look (armor.py): riveted plates for Explorer's bars, red-glow command buttons,
# and the bottom details panel with the emblem. Keys are (class, part, state).
ARMOR_BARS = {("darkmodenavbar::rebar", 0, 0), ("navbar::rebar", 0, 0), ("darkmode_darktheme::rebar", 0, 0),
              ("darkmode::commandmodule", 1, 0), ("commandmodule", 1, 0),
              ("cplcommandmodule::commandmodule", 1, 0), ("explorermenu::toolbar", 0, 0)}
ARMOR_PANEL = {("darkmode::previewpane", 1, 1), ("previewpane", 1, 1)}
ARMOR_GLOW = {(c, p, 0) for c in ("darkmode::commandmodule", "commandmodule", "darkmode_explorer::commandmodule")
              for p in (3, 4, 5)}
# Scrollbars in dark metal with red (Explorer's dark ones, dark apps', and classic apps').
ARMOR_SCROLL = {"darkmode_explorer::scrollbar", "darkmode_darktheme::scrollbar", "scrollbar"}


# Windows refuses a whole skin (0x9007000E, out of memory) when one image is too big.
# Its own largest image is 120 x 480, so generated art stays within that many pixels.
MAX_IMAGE_PIXELS = 57600


def fit_image(img, margins):
    """Shrink `img` (and its sizing margins) to at most MAX_IMAGE_PIXELS."""
    w, h = img.size
    if w * h <= MAX_IMAGE_PIXELS:
        return img, margins
    f = (MAX_IMAGE_PIXELS / (w * h)) ** 0.5
    W, H = max(1, int(w * f)), max(1, int(h * f))
    l, r, t, b = (int(m * f) for m in margins)
    return img.resize((W, H), Image.LANCZOS), (min(l, W - 1), min(r, W - 1 - min(l, W - 1)),
                                               min(t, H - 1), min(b, H - 1 - min(t, H - 1)))


def dpi_scale():
    """Display scaling as a factor (2.5 at 250%). Windows draws skin images at their own
    pixel size whatever the scaling, so the armor art is drawn this much bigger."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics") as k:
            return max(1.0, min(3.0, winreg.QueryValueEx(k, "AppliedDPI")[0] / 96))
    except OSError:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96)


# Bright accent text: command bar buttons ("Organize") and Explorer's menu bar words.
ARMOR_TEXT = {"darkmode::commandmodule", "commandmodule", "darkmode_explorer::commandmodule",
              "explorer::commandmodule", "cplcommandmodule::commandmodule", "explorermenu::toolbar"}


def _ref(rgb):
    return rgb[0] | rgb[1] << 8 | rgb[2] << 16


def _mode(cls, dark=True):
    c = cls.lower()
    if dark and c in METAL:
        return "metal"
    if dark and c in LIGHT_ONLY:
        return "invert"
    if dark and c in TRACK:
        return "track"
    if c == "window" or c.endswith("::window"):
        return "frame"
    if "dark" in c or c.startswith("taskbar") or c.startswith("startpanel"):
        return "dark"
    return "hue"


# ------------------------------------------------------------------ build

def build(name, accent_hex, progress=None, art="color", dark=True, armor=False):
    """Make a skin folder and return the path of its .msstyles.
    art: "color" repaints Windows' own art; "premium" also swaps in our own
    drawn armor-plate caption buttons (see premium.py).
    armor: riveted Explorer bars, red buttons and the emblem panel (see armor.py)."""
    import pefile
    # Windows only finds a skin whose folder has the same name as the file
    # (Themes\aero\aero.msstyles), so each build gets its own outer folder.
    folder = os.path.join(SKINS, "%s-%d" % (name, time.time()), name)
    os.makedirs(os.path.join(folder, "en-US"), exist_ok=True)
    style = os.path.join(folder, name + ".msstyles")
    shutil.copyfile(STOCK_STYLE, style)
    for lang in os.listdir(STOCK):          # language files must be named after the skin
        mui = os.path.join(STOCK, lang, "aero.msstyles.mui")
        try:
            if os.path.isfile(mui):
                os.makedirs(os.path.join(folder, lang), exist_ok=True)
                shutil.copyfile(mui, os.path.join(folder, lang, name + ".msstyles.mui"))
        except OSError:
            pass                            # a language folder Windows lists but can't open
    # File by file: some Windows installs list language folders under Shell that can't
    # be opened (seen on Dutch Windows: Shell\NormalColor\nl-NL), which made copytree fail.
    for root, dirs, files in os.walk(os.path.join(STOCK, "Shell"), onerror=lambda e: None):
        rel = os.path.relpath(root, STOCK)
        for fn in files:
            try:
                os.makedirs(os.path.join(folder, rel), exist_ok=True)
                shutil.copyfile(os.path.join(root, fn), os.path.join(folder, rel, fn))
            except OSError:
                pass

    pe = pefile.PE(STOCK_STYLE)

    def entries(kind):
        for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if str(t.name) == kind:
                for e in t.directory.entries:
                    for leaf in e.directory.entries:
                        yield e, leaf, pe.get_data(leaf.data.struct.OffsetToData, leaf.data.struct.Size)

    e, leaf, raw = next(entries("VARIANT"))
    variant_id = (str(e.name), leaf.id)
    table = bytearray(raw)
    names = [x for x in next(entries("CMAP"))[2].decode("utf-16le").split("\x00") if x]
    images = [(e.id, leaf.id, d) for e, leaf, d in entries("IMAGE")]
    streams = {e.id: (leaf.id, d) for e, leaf, d in entries("STREAM")}
    pe.close()

    # Property records: 8 ints (name, type, class, part, state, inline value, 0, size) + data.
    painter = Painter(accent_hex, strength=1.0)
    image_mode, rank, off = {}, {"hue": 0, "dark": 1, "frame": 2, "track": 3, "invert": 3, "metal": 4}, 0
    atlas_rects, atlas_id = {}, None
    image_at, margins_at, image_refs = {}, {}, {}        # (class, part, state) -> record offset
    count_at, arrow_ids, thumb_ids = {}, set(), {}
    while off + 32 <= len(table):
        prop, kind, cls, part, state, inline, _, size = struct.unpack_from("<8i", table, off)
        cname = names[cls] if 0 <= cls < len(names) else ""
        key = (cname.lower(), part, state)
        if prop == 3601 and kind == 205 and size >= 16:
            margins_at[key] = off
        if prop == 2401 and kind == 202 and not inline and size >= 4:      # IMAGECOUNT
            count_at[key] = struct.unpack_from("<i", table, off + 32)[0]
        if kind == 206 and inline and key[0] in ARMOR_SCROLL and part == 1:  # arrows, every DPI
            arrow_ids.add(inline)
        if kind == 206 and inline and key[0] in ARMOR_SCROLL and part in (2, 3):   # thumbs, every DPI
            thumb_ids[inline] = key
        if kind == 206 and inline:                       # image reference
            if prop == 3001:
                image_at[key] = (off, inline)
            image_refs.setdefault(inline, set()).add(key)
            m = _mode(cname, dark)
            if rank[m] >= rank[image_mode.get(inline, "hue")]:
                image_mode[inline] = m
        elif cname == "DWMWindow" and kind == 209 and size >= 16:   # window-frame atlas piece
            atlas_rects[struct.unpack_from("<i", table, off + 12)[0]] = struct.unpack_from("<4i", table, off + 32)
        elif cname == "DWMWindow" and kind == 213:
            atlas_id = inline or struct.unpack_from("<i", table, off + 32)[0]
        elif kind == 204 and not inline and size >= 4:   # color
            val = struct.unpack_from("<I", table, off + 32)[0]
            m = _mode(cname, dark)
            dark_ui = m in ("invert", "metal") or (m == "track" and part in (0, 1, 2))   # track, not fill
            new = painter.readable(val, prop, state) if dark_ui                 else painter.colorref(val, m)
            if armor and key[0] in ARMOR_TEXT and prop == 3803:
                new = (val & 0xFF000000) | _ref((120, 120, 120) if state in (4, 6)   # disabled
                                                else painter.text_accent())
            struct.pack_into("<I", table, off + 32, new)
        off = (off + 32 + (0 if inline else size) + 7) & ~7

    replaced, added = {}, []                     # image id -> new PNG; new (id, lang, PNG)
    if armor:
        import armor as armor_art
        acc = tuple(int(accent_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        by_id = {iid: (lang, data) for iid, lang, data in images}
        next_id = max(by_id) + 1
        k = dpi_scale()
        # every address-row variant (maximized, inactive...) shares the navbar plate
        targets = ARMOR_BARS | ARMOR_PANEL | {k for k in image_at if k[0].endswith("navbar::rebar") and k[1] == 0}
        for key in sorted(ARMOR_GLOW):              # same size: repaint in place
            if key in image_at and image_at[key][1] in by_id:
                iid = image_at[key][1]
                im = Image.open(io.BytesIO(by_id[iid][1]))
                b = io.BytesIO()
                armor_art.glow_frames(im, 1, acc).save(b, "PNG")
                replaced[iid] = b.getvalue()
        for key in sorted(targets):                 # new size and sizing margins
            if key not in image_at or key not in margins_at or image_at[key][1] not in by_id:
                continue
            img_off, iid = image_at[key]
            lang, data = by_id[iid]
            w, h = Image.open(io.BytesIO(data)).size
            moff = margins_at[key]
            old_m = struct.unpack_from("<4i", table, moff + 32)
            if key in ARMOR_PANEL:
                art_img, new_m = armor_art.emblem_panel(acc, scale=min(k, 2.0))
            else:
                art_img, new_m = armor_art.plate(w, h, old_m, acc, seed=len(added) + 3, scale=k)
            art_img, new_m = fit_image(art_img, new_m)
            b = io.BytesIO()
            art_img.save(b, "PNG")
            if image_refs.get(iid, set()) - targets:   # shared with other parts: use a new image
                added.append((next_id, lang, b.getvalue()))
                struct.pack_into("<i", table, img_off + 20, next_id)
                next_id += 1
            else:
                replaced[iid] = b.getvalue()
            struct.pack_into("<4i", table, moff + 32, *new_m)

        def png(im):
            b = io.BytesIO()
            im.save(b, "PNG")
            return b.getvalue()

        for iid in arrow_ids:                       # arrow buttons: red glyphs, same size
            if iid in by_id:
                replaced[iid] = png(armor_art.red_glyphs(Image.open(io.BytesIO(by_id[iid][1])), acc))
        for iid, key in thumb_ids.items():           # thumbs: one image per scaling, same size
            count = count_at.get(key, 1)
            if iid in by_id and count > 1:
                im = Image.open(io.BytesIO(by_id[iid][1]))
                if im.size[1] % count == 0:
                    replaced[iid] = png(armor_art.scroll_thumb(im, count, acc, vertical=key[1] == 3))
        for key in sorted(image_at):                # tracks: same size
            if key[0] in ARMOR_SCROLL and key[1] in (4, 5, 6, 7) and image_at[key][1] in by_id:
                iid = image_at[key][1]
                count = count_at.get(key, 1)
                im = Image.open(io.BytesIO(by_id[iid][1]))
                if im.size[1] % count == 0:
                    replaced[iid] = png(armor_art.scroll_track(im, count, acc))

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.BeginUpdateResourceW.restype = wt.HANDLE
    k32.BeginUpdateResourceW.argtypes = [wt.LPCWSTR, wt.BOOL]
    k32.UpdateResourceW.argtypes = [wt.HANDLE, wt.LPCWSTR, ctypes.c_void_p, wt.WORD,
                                    ctypes.c_void_p, wt.DWORD]
    k32.EndUpdateResourceW.argtypes = [wt.HANDLE, wt.BOOL]
    h = k32.BeginUpdateResourceW(style, False)
    if not h:
        raise OSError("Could not open the skin file for writing.")

    def put(kind, res_name, lang, data):
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        name_arg = ctypes.c_void_p(res_name) if isinstance(res_name, int) else \
            ctypes.cast(ctypes.c_wchar_p(res_name), ctypes.c_void_p)
        if not k32.UpdateResourceW(h, kind, name_arg, lang, buf, len(data)):
            raise OSError("Could not write the skin (%d)." % ctypes.get_last_error())

    for n, (iid, lang, data) in enumerate(images):
        if iid in replaced:
            data = replaced[iid]
        else:
            try:
                data = painter.png(data, image_mode.get(iid, "hue"))
            except Exception:
                pass                              # keep anything that isn't a PNG
        put("IMAGE", iid, lang, data)
    for iid, lang, data in added:
        put("IMAGE", iid, lang, data)
        if progress and n % 100 == 0:
            progress(n / len(images))
    if art == "premium" and atlas_id in streams:
        import premium
        lang, png = streams[atlas_id]
        acc = tuple(int(accent_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        put("STREAM", atlas_id, lang, premium.paint_atlas(png, atlas_rects, acc))
    put("VARIANT", variant_id[0], variant_id[1], table)
    if not k32.EndUpdateResourceW(h, False):
        raise OSError("Could not save the skin.")
    return style


# ------------------------------------------------------------------ switch

def use(style_path):
    """Switch Windows to a skin. Raises OSError if Windows refuses it."""
    ux = ctypes.WinDLL("uxtheme")
    set_style = ux[65]          # SetSystemVisualStyle(path, color, size, flags)
    set_style.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
    set_style.restype = ctypes.c_long
    # Right after signing in Windows can refuse the first skin (0x9007000E) and then keeps
    # refusing that same path: Apply retries a fresh_copy() at its end.
    hr = set_style(style_path, "NormalColor", "NormalSize", 0) & 0xFFFFFFFF
    if hr:
        raise OSError("Windows would not load the skin (code 0x%08X)." % hr)


def fresh_copy(style_path):
    """The same skin under a new folder. After a refused load Windows keeps refusing that
    path, while the identical skin from another folder loads (a second Apply showed it)."""
    inner = os.path.dirname(style_path)                 # ...\Name-123\Name\Name.msstyles
    outer = os.path.dirname(inner)
    new_outer = "%s-retry%d" % (outer, int(time.time() * 1000) % 100000)
    shutil.copytree(outer, new_outer)
    return os.path.join(new_outer, os.path.basename(inner), os.path.basename(style_path))


def use_stock():
    use(STOCK_STYLE)


def cleanup(keep):
    """Delete old skins except the ones in use (`keep`: list of .msstyles paths)."""
    if not os.path.isdir(SKINS):
        return
    keep = {os.path.normcase(os.path.dirname(os.path.dirname(p))) for p in keep if p}
    for d in os.listdir(SKINS):
        full = os.path.join(SKINS, d)
        if os.path.normcase(full) not in keep:
            shutil.rmtree(full, ignore_errors=True)
