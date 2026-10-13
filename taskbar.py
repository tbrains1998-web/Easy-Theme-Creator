"""Taskbar and Start button through StartAllBack.

StartAllBack draws its taskbar from its own small visual style (the files in
%LOCALAPPDATA%\\StartAllBack\\Styles), not from the Windows skin, so the metal
taskbar is a copy of its Plain8 style with our own drawn background: near-black
gunmetal with a thin glowing accent line on top. The Start button is the
alien-head orb from start_orb.py, recolored to the accent.
"""
import ctypes
import ctypes.wintypes as wt
import io
import os
import shutil
import struct
import subprocess
import time
import winreg

import numpy as np
from PIL import Image, ImageDraw

SAB = os.path.join(os.environ.get("LOCALAPPDATA", ""), "StartAllBack")
STYLES = os.path.join(SAB, "Styles")
ORBS = os.path.join(SAB, "Orbs")
BASE_STYLE = os.path.join(STYLES, "Plain8.msstyles")
KEY = r"Software\StartIsBack"
HERE = os.path.dirname(os.path.abspath(__file__))
ORB_SOURCE = os.path.join(HERE, "orbs", "alien-orb-216.png")

# Taskbar background parts in Plain8 (TaskBar / TaskBand2): which edge the bar sits on.
# Images are 1 pixel thick profiles that get stretched along the bar.
BG_IMAGES = {576: "bottom", 578: "top", 577: "right", 579: "left"}


def available():
    return os.path.exists(BASE_STYLE)


def _set(name, value, kind=winreg.REG_SZ):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as k:
        winreg.SetValueEx(k, name, 0, kind, value)


def _mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def metal_profile(length, accent, edge):
    """Cross-section of the bar: black gunmetal, faint highlight, thin accent line
    on the side facing the screen (with a soft glow)."""
    L = length
    t = np.linspace(0, 1, L)
    base = 10 + 22 * np.exp(-((t - 0.18) / 0.22) ** 2) + 6 * (1 - t)      # dark metal with a sheen
    rows = np.stack([base, base, base * 1.05], -1)
    acc = np.array(accent[:3], float)
    glow = np.exp(-(np.arange(L) / 2.2))                                   # line + glow at the inner edge
    rows = rows * (1 - glow[:, None] * 0.9) + acc * glow[:, None] * 0.95
    rows[0] = acc * 0.85
    rows[1] = rows[1] * 0.5 + acc * 0.4
    rows[-1] = (4, 4, 5)
    arr = np.clip(rows, 0, 255).astype(np.uint8)
    col = np.dstack([arr[:, None, :], np.full((L, 1, 1), 255, np.uint8)])    # L x 1 RGBA
    img = Image.fromarray(col, "RGBA")
    if edge == "top":          # bar at the top: accent line on its bottom side
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    elif edge in ("left", "right"):
        img = img.transpose(Image.ROTATE_90)
        if edge == "left":
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def build_style(name, accent):
    """Write <name>.msstyles into StartAllBack's Styles folder. Returns its file name."""
    import pefile
    out_name = name + ".msstyles"
    dst = os.path.join(STYLES, out_name)
    tmp = dst + ".tmp"
    shutil.copyfile(BASE_STYLE, tmp)
    pe = pefile.PE(BASE_STYLE)
    sizes = {}
    for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if str(t.name) == "IMAGE":
            for e in t.directory.entries:
                if e.id in BG_IMAGES:
                    leaf = e.directory.entries[0]
                    data = pe.get_data(leaf.data.struct.OffsetToData, leaf.data.struct.Size)
                    sizes[e.id] = (leaf.id, Image.open(io.BytesIO(data)).size)
    pe.close()

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.BeginUpdateResourceW.restype = wt.HANDLE
    k32.BeginUpdateResourceW.argtypes = [wt.LPCWSTR, wt.BOOL]
    k32.UpdateResourceW.argtypes = [wt.HANDLE, wt.LPCWSTR, ctypes.c_void_p, wt.WORD,
                                    ctypes.c_void_p, wt.DWORD]
    k32.EndUpdateResourceW.argtypes = [wt.HANDLE, wt.BOOL]
    h = k32.BeginUpdateResourceW(tmp, False)
    if not h:
        raise OSError("Could not open the taskbar style for writing.")
    for iid, (lang, (w, hgt)) in sizes.items():
        edge = BG_IMAGES[iid]
        length = hgt if edge in ("bottom", "top") else w
        img = metal_profile(length, accent, edge)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        data = buf.getvalue()
        cbuf = ctypes.create_string_buffer(data, len(data))
        if not k32.UpdateResourceW(h, "IMAGE", ctypes.c_void_p(iid), lang, cbuf, len(data)):
            raise OSError("Could not write the taskbar style.")
    if not k32.EndUpdateResourceW(h, False):
        raise OSError("Could not save the taskbar style.")
    try:
        os.replace(tmp, dst)
    except OSError:                      # in use by the running taskbar: use a fresh name
        out_name = "%s-%d.msstyles" % (name, time.time())
        os.replace(tmp, os.path.join(STYLES, out_name))
    return out_name


def orb_image(accent):
    """The alien orb strip (3 states) with its red glow turned into the accent color."""
    img = Image.open(ORB_SOURCE).convert("RGBA")
    a = np.asarray(img).astype(np.float64)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    redness = np.clip((r - np.maximum(g, b)) / 255.0, 0, 1)        # how much of a pixel is the red glow
    grey = np.minimum(np.minimum(r, g), b)
    acc = np.array(accent[:3], float)
    peak = max(acc.max(), 1)
    tint = acc / peak * 255
    new = grey[..., None] + redness[..., None] * tint
    a[..., :3] = np.clip(new, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def install_orb(name, accent):
    os.makedirs(ORBS, exist_ok=True)
    path = os.path.join(ORBS, "%s-orb-%d.png" % (name, time.time()))
    orb_image(accent).save(path)
    for old in os.listdir(ORBS):                     # keep the folder tidy: drop our older orbs
        if old.startswith(name + "-orb-") and os.path.join(ORBS, old) != path:
            try:
                os.remove(os.path.join(ORBS, old))
            except OSError:
                pass
    return path


def apply(name, accent, metal=True, orb=True):
    """Use the metal taskbar and/or the alien Start button. Explorer must restart after."""
    style = None
    if metal and available():
        style = build_style(name, accent)
        _set("TaskbarStyle", style)          # the taskbar's style (AlterStyle is the Start menu's)
        _set("AlterStyle", style)
        # Windows' "accent color on taskbar" paints over any style, so switch it off
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            winreg.SetValueEx(k, "ColorPrevalence", 0, winreg.REG_DWORD, 0)
    if orb and os.path.exists(ORB_SOURCE):
        _set("OrbBitmap", install_orb(name, accent))
    use_in_startallback(style or "Plain8.msstyles")


# ---------------------------------------------------------------- telling StartAllBack
# Writing the registry is not enough: StartAllBack only reloads its taskbar style
# when it's picked in its settings window. So we pick it there (window kept hidden):
# set the "Visual style" dropdowns and send the same change notice a click would.

CB_GETCOUNT, CB_GETLBTEXT, CB_GETLBTEXTLEN, CB_SETCURSEL = 0x146, 0x148, 0x149, 0x14E
CBN_SELCHANGE, WM_COMMAND = 1, 0x111


def _items(hwnd):
    u = ctypes.windll.user32
    out = []
    for i in range(u.SendMessageW(hwnd, CB_GETCOUNT, 0, 0)):
        n = u.SendMessageW(hwnd, CB_GETLBTEXTLEN, i, 0)
        buf = ctypes.create_unicode_buffer(n + 1)
        u.SendMessageW(hwnd, CB_GETLBTEXT, i, buf)
        out.append(buf.value)
    return out


def _pick(hwnd, index):
    u = ctypes.windll.user32
    u.SendMessageW(hwnd, CB_SETCURSEL, index, 0)
    ident = u.GetDlgCtrlID(hwnd)
    u.SendMessageW(u.GetParent(hwnd), WM_COMMAND, (CBN_SELCHANGE << 16) | (ident & 0xFFFF), hwnd)


def use_in_startallback(style_file):
    """Select our style in StartAllBack's own settings so the taskbar redraws now."""
    import layout
    label = os.path.splitext(style_file)[0]
    u = ctypes.windll.user32
    top = layout._settings_window()
    if top:
        u.PostMessageW(top, layout.WM_CLOSE, 0, 0)
        time.sleep(1)
    subprocess.Popen([layout.SAB_CFG])
    for _ in range(50):
        time.sleep(0.2)
        top = layout._settings_window()
        if top:
            break
    if not top:
        raise OSError("StartAllBack settings did not open.")
    u.ShowWindow(top, 0)
    try:
        combos = []
        cb = layout.EnumProc(lambda h, _: combos.append(h) or True)
        u.EnumChildWindows(top, cb, 0)
        done = 0
        for h in combos:
            items = _items(h)
            if label in items and "Plain8" in items:          # a "Visual style" dropdown
                other = 0 if items[0] != label else 1
                _pick(h, other)                                # change away and back, so it reloads
                time.sleep(0.3)
                _pick(h, items.index(label))
                done += 1
        if not done:
            raise OSError("Could not find StartAllBack's style setting.")
        time.sleep(1.5)
    finally:
        u.PostMessageW(top, layout.WM_CLOSE, 0, 0)
