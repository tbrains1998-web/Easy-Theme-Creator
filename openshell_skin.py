"""Armor skin for Open-Shell's Windows 7 Start menu, in the theme's accent color.

Built from the Midnight skin that ships with Open-Shell (so its shapes, slices and
glyphs stay exactly right): every picture is recolored - grey frames become dark
gunmetal with a red trim, selections glow in the accent, separators turn dim red -
and the skin script is switched from glass to solid with light text and accent links.
The result is a normal .skin7 file in Open-Shell's Skins folder.
"""
import ctypes
import ctypes.wintypes as wt
import io
import os
import re
import shutil
import struct

import numpy as np
from PIL import Image

OPEN_SHELL = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Open-Shell")
SKINS = os.path.join(OPEN_SHELL, "Skins")
BASE = os.path.join(SKINS, "Midnight.skin7")
NAME = "Easy Theme Armor"

# Midnight picture ids by role (see its script)
FRAMES = {1, 8, 13, 26, 27, 28, 41, 42, 43}          # menu bodies (glass / opaque / more glass)
SELECTIONS = {2, 3, 6, 10, 15, 16, 18, 19}             # highlighted items, split buttons, shutdown
SEARCH = {21, 40}
SEPARATORS = {11, 14, 17, 25, 30, 37}
USER_FRAMES = {12, 20}
SCROLL = {33, 34, 38, 39}
PAGERS = {22}


def available():
    return os.path.exists(BASE)


# ------------------------------------------------------------------ DIB helpers

def _dib_to_rgba(d):
    hs, w, h, _, bpp, comp = struct.unpack_from("<IiiHHI", d)
    clr = struct.unpack_from("<I", d, 32)[0]
    off = hs + (clr or (1 << bpp if bpp <= 8 else 0)) * 4 + (12 if comp == 3 and hs == 40 else 0)
    bottom_up, h = h > 0, abs(h)
    if bpp == 32:
        a = np.frombuffer(d, np.uint8, w * h * 4, off).reshape(h, w, 4)[..., [2, 1, 0, 3]]
    elif bpp == 24:
        stride = (w * 3 + 3) & ~3
        rows = np.frombuffer(d, np.uint8, stride * h, off).reshape(h, stride)[:, :w * 3]
        a = np.dstack([rows.reshape(h, w, 3)[..., ::-1], np.full((h, w), 255, np.uint8)])
    else:
        return None, bpp
    return (a[::-1] if bottom_up else a).astype(float) / 255, bpp


def _rgba_to_dib(a, bpp):
    a = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)[::-1]
    h, w = a.shape[:2]
    if bpp == 24:
        stride = (w * 3 + 3) & ~3
        rows = np.zeros((h, stride), np.uint8)
        rows[:, :w * 3] = a[..., [2, 1, 0]].reshape(h, w * 3)
        return struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, stride * h, 2835, 2835, 0, 0) + rows.tobytes()
    return struct.pack("<IiiHHIIiiII", 40, w, h, 1, 32, 0, w * h * 4, 2835, 2835, 0, 0) + \
        a[..., [2, 1, 0, 3]].tobytes()


# ------------------------------------------------------------------ recoloring

def _interp(L, stops):
    """Map grey level L (0..1) through [(level, rgb), ...] stops."""
    xs = np.array([s[0] for s in stops])
    out = np.zeros(L.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(L, xs, [s[1][c] for s in stops])
    return out


def _paint(a, role, acc):
    rgb, alpha = a[..., :3], a[..., 3:]
    L = rgb.mean(-1)
    dark, metal, edge = np.array([0.03, 0.03, 0.035]), np.array([0.085, 0.085, 0.10]), np.array([0.04, 0.04, 0.045])
    if role == "frame":            # 30 edge, 58 shadow, 84 body, 145 outer bevel, 169 inner bevel
        new = _interp(L, [(0, dark), (30 / 255, dark), (58 / 255, edge), (84 / 255, metal),
                          (120 / 255, metal * 1.4), (145 / 255, acc * 0.95), (169 / 255, acc * 0.55),
                          (1, acc * 0.7 + 0.2)])
    elif role == "search":
        new = _interp(L, [(0, dark), (84 / 255, dark * 1.6), (145 / 255, acc * 0.6), (1, acc * 0.8)])
    elif role == "selection":      # dark translucent fill -> deep accent, light rim -> bright accent
        new = _interp(L, [(0, acc * 0.22), (0.5, acc * 0.55), (1, np.clip(acc * 0.9 + 0.15, 0, 1))])
    elif role == "separator":
        new = np.broadcast_to(acc * 0.45, rgb.shape)
    elif role == "user":           # 0 inside, 78 frame body, 116 frame light
        new = _interp(L, [(0, dark), (78 / 255, metal * 1.3), (116 / 255, acc * 0.85), (1, acc)])
    elif role == "scroll":
        new = _interp(L, [(0, dark), (0.35, metal), (0.6, acc * 0.55), (1, acc * 0.9)])
    elif role == "pager":
        new = _interp(L, [(0, dark), (0.5, metal * 1.5), (1, acc * 0.7)])
    else:
        return a
    out = a.copy()
    out[..., :3] = new
    return out


def _role(rid):
    for role, ids in (("frame", FRAMES), ("selection", SELECTIONS), ("search", SEARCH),
                      ("separator", SEPARATORS), ("user", USER_FRAMES), ("scroll", SCROLL),
                      ("pager", PAGERS)):
        if rid in ids:
            return role
    return None


# ------------------------------------------------------------------ script

def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


def _script(text, acc255):
    """Midnight's script, made solid (no glass) and recolored."""
    link = tuple(min(255, int(v * 0.85 + 60)) for v in acc255)
    head = tuple(min(255, int(v * 0.9 + 40)) for v in acc255)
    lines = []
    skip = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            # glass variants are gone: the opaque pictures are the base now
            skip = s in ("[OPAQUE]", "[TRANSPARENT_MORE]", "[DISABLE_MASK]")
        if skip:
            continue
        if s.startswith("OPTION ") and any(k in s for k in ("RADIOGROUP", "OPAQUE", "TRANSPARENT", "DISABLE_MASK")):
            continue
        lines.append(line)
    t = "\n".join(lines)
    reps = {
        r"^About=.*$": "About=Armor skin by Easy Theme Creator (based on Open-Shell's Midnight skin)",
        r"^Main_opacity=.*$": "Main_opacity=region",
        r"^Main2_opacity=.*$": "Main2_opacity=region",
        r"^Main_bitmap=.*$": "Main_bitmap=26",
        r"^Main_bitmap_search=.*$": "Main_bitmap_search=27",
        r"^Main_bitmap_jump=.*$": "Main_bitmap_jump=28",
        r"^Scrollbar_button=.*$": "Scrollbar_button=38",
        r"^Scrollbar_thumb=.*$": "Scrollbar_thumb=38",
        r"^Scrollbar_background=.*$": "Scrollbar_background=39",
        r"^Search_background=.*$": "Search_background=40",
        r"^(\w+_mask)=#100000$": r"\1=0",                 # no glass color blended in
        r"^Main_background=.*$": "Main_background=#16161A",
        r"^Programs_background=.*$": "Programs_background=#16161A",
        r"^Submenu_background=#545454$": "Submenu_background=#18181C",
        r"^Search_text_background=.*$": "Search_text_background=#0A0A0C",
        r"^Main_text_color=.*$": "Main_text_color=#E6E6E6,#FFFFFF,#7F7F7F,#7F7F7F",
        r"^Main2_text_color=.*$": "Main2_text_color=%s,#FFFFFF,#7F7F7F,#7F7F7F" % _hex(link),
        r"^Programs_text_color=.*$": "Programs_text_color=#E6E6E6,#FFFFFF,#7F7F7F,#7F7F7F",
        r"^Submenu_text_color=#FFFFFF.*$": "Submenu_text_color=#E6E6E6,#FFFFFF,#7F7F7F,#7F7F7F",
        r"^List_separator_text_color=.*$": "List_separator_text_color=%s,%s" % (_hex(head), _hex(head)),
        r"^List_separator_split_text_color=.*$": "List_separator_split_text_color=%s,%s" % (_hex(head), _hex(head)),
        r"^Submenu_separator_text_color=.*$": "Submenu_separator_text_color=%s" % _hex(head),
    }
    for pat, rep in reps.items():
        t = re.sub(pat, rep, t, flags=re.M)
    return t


# ------------------------------------------------------------------ build

def build(accent, out_path):
    """Write the armor .skin7 for `accent` (r, g, b) to out_path."""
    import pefile
    acc255 = tuple(int(v) for v in accent[:3])
    acc = np.array(acc255, float) / 255
    pe = pefile.PE(BASE)
    resources = []
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        tid = str(t.name) if t.name else t.id
        for e in t.directory.entries:
            for leaf in e.directory.entries:
                resources.append((tid, e.id, leaf.id,
                                  pe.get_data(leaf.data.struct.OffsetToData, leaf.data.struct.Size)))
    pe.close()
    tmp = out_path + ".tmp"
    shutil.copyfile(BASE, tmp)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.BeginUpdateResourceW.restype = wt.HANDLE
    k32.BeginUpdateResourceW.argtypes = [wt.LPCWSTR, wt.BOOL]
    k32.UpdateResourceW.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.WORD, ctypes.c_void_p, wt.DWORD]
    k32.EndUpdateResourceW.argtypes = [wt.HANDLE, wt.BOOL]
    h = k32.BeginUpdateResourceW(tmp, False)
    if not h:
        raise OSError("Could not open the Start menu skin for writing.")

    def put(kind, rid, lang, data):
        kind_arg = ctypes.c_void_p(kind) if isinstance(kind, int) else ctypes.cast(ctypes.c_wchar_p(kind), ctypes.c_void_p)
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        if not k32.UpdateResourceW(h, kind_arg, ctypes.c_void_p(rid), lang, buf, len(data)):
            raise OSError("Could not write the Start menu skin (%d)." % ctypes.get_last_error())

    for tid, rid, lang, data in resources:
        if tid == "SKIN":
            wide = data[1:2] == b"\x00" or data[:2] == b"\xff\xfe"
            raw = (data.decode("utf-16le") if wide else data.decode("cp1252")).lstrip("\ufeff")
            text = _script(raw, acc255)          # same encoding as Midnight's own script
            put("SKIN", rid, lang, (b"\xff\xfe" + text.encode("utf-16le")) if wide else text.encode("cp1252"))
        elif tid == 2 and _role(rid):
            a, bpp = _dib_to_rgba(data)
            if a is not None:
                put(2, rid, lang, _rgba_to_dib(_paint(a, _role(rid), acc), bpp))
    if not k32.EndUpdateResourceW(h, False):
        raise OSError("Could not save the Start menu skin.")
    os.replace(tmp, out_path)
    return out_path


def preview_sheet(skin_path, out_png):
    """Contact sheet of the recolored pictures (for checking by eye)."""
    import pefile
    pe = pefile.PE(skin_path)
    tiles = []
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if t.id == 2:
            for e in t.directory.entries:
                leaf = e.directory.entries[0]
                a, _ = _dib_to_rgba(pe.get_data(leaf.data.struct.OffsetToData, leaf.data.struct.Size))
                if a is not None and _role(e.id):
                    tiles.append(Image.fromarray((a * 255).astype(np.uint8), "RGBA"))
    W = sum(t.width * 3 + 10 for t in tiles) + 10
    sheet = Image.new("RGBA", (W, 260), (40, 40, 44, 255))
    x = 10
    for t in tiles:
        sheet.alpha_composite(t.resize((t.width * 3, t.height * 3), Image.NEAREST), (x, 10))
        x += t.width * 3 + 10
    sheet.save(out_png)
