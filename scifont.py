"""Sci-fi lettering: Windows' icon, menu and status-bar fonts switched to Orbitron.

Orbitron (The League of Moveable Type, SIL Open Font License, files in fonts\\) is
installed for the current user only. The icon font is what Explorer uses for file
and folder names (and the navigation pane); menus and status bars use the others.
Title bars and dialog text keep Windows' font so everything stays readable.
Programs that are already open pick it up after a sign-out.
"""
import contextlib
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import winreg

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {"Orbitron Medium (TrueType)": "Orbitron Medium.ttf",
         "Orbitron Bold (TrueType)": "Orbitron Bold.ttf"}
FACE = "Orbitron"
USER_FONTS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")
FONTS_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"

SPI_GETICONTITLELOGFONT, SPI_SETICONTITLELOGFONT = 0x1F, 0x22
SPI_GETNONCLIENTMETRICS, SPI_SETNONCLIENTMETRICS = 0x29, 0x2A
SPIF = 0x01 | 0x02                       # save to the profile + tell running programs
u32 = ctypes.windll.user32

# Windows hands these fonts out, and takes them, in the calling thread's pixels: at 250%
# a DPI-aware thread sees ~2.5x the heights an unaware one does. Snapshots taken in one
# and put back in the other brought fonts back far too big, so every read and write here
# happens in one fixed context: system-aware, the system DPI's real pixels, exactly as
# Windows keeps them (no rounding). Snapshots record it, with the DPI they were read at.
CONTEXT = "system-aware"
_SYSTEM_AWARE = -2                       # DPI_AWARENESS_CONTEXT_SYSTEM_AWARE
_U32 = []


def _user32():
    """Own copy of user32, so the restype set here doesn't change other modules' calls."""
    if not _U32:
        u = ctypes.WinDLL("user32")
        try:
            u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
            u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        except AttributeError:
            pass                         # Windows 10 before 1607
        _U32.append(u)
    return _U32[0]


@contextlib.contextmanager
def _fixed_dpi():
    """This thread in the system-aware DPI context for the `with` block, then back."""
    u = _user32()
    old = None
    try:
        old = u.SetThreadDpiAwarenessContext(ctypes.c_void_p(_SYSTEM_AWARE))
    except AttributeError:
        pass
    try:
        yield
    finally:
        if old:
            u.SetThreadDpiAwarenessContext(ctypes.c_void_p(old))


def _system_dpi():
    """The system DPI (240 at 250%). Inside _fixed_dpi() only: unaware threads are told 96."""
    try:
        dpi = _user32().GetDpiForSystem()
        if dpi:
            return dpi
    except AttributeError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics") as k:
            return int(winreg.QueryValueEx(k, "AppliedDPI")[0]) or 96
    except (OSError, ValueError):
        return 96


class LOGFONTW(ctypes.Structure):
    _fields_ = [("lfHeight", wt.LONG), ("lfWidth", wt.LONG), ("lfEscapement", wt.LONG),
                ("lfOrientation", wt.LONG), ("lfWeight", wt.LONG), ("lfItalic", wt.BYTE),
                ("lfUnderline", wt.BYTE), ("lfStrikeOut", wt.BYTE), ("lfCharSet", wt.BYTE),
                ("lfOutPrecision", wt.BYTE), ("lfClipPrecision", wt.BYTE), ("lfQuality", wt.BYTE),
                ("lfPitchAndFamily", wt.BYTE), ("lfFaceName", wt.WCHAR * 32)]


class NONCLIENTMETRICSW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("iBorderWidth", ctypes.c_int), ("iScrollWidth", ctypes.c_int),
                ("iScrollHeight", ctypes.c_int), ("iCaptionWidth", ctypes.c_int),
                ("iCaptionHeight", ctypes.c_int), ("lfCaptionFont", LOGFONTW),
                ("iSmCaptionWidth", ctypes.c_int), ("iSmCaptionHeight", ctypes.c_int),
                ("lfSmCaptionFont", LOGFONTW), ("iMenuWidth", ctypes.c_int),
                ("iMenuHeight", ctypes.c_int), ("lfMenuFont", LOGFONTW), ("lfStatusFont", LOGFONTW),
                ("lfMessageFont", LOGFONTW), ("iPaddedBorderWidth", ctypes.c_int)]


def _icon_font():
    lf = LOGFONTW()
    u32.SystemParametersInfoW(SPI_GETICONTITLELOGFONT, ctypes.sizeof(lf), ctypes.byref(lf), 0)
    return lf


def _metrics():
    m = NONCLIENTMETRICSW()
    m.cbSize = ctypes.sizeof(m)
    u32.SystemParametersInfoW(SPI_GETNONCLIENTMETRICS, m.cbSize, ctypes.byref(m), 0)
    return m


def install():
    """Copy the font files into the user's font folder and register them."""
    os.makedirs(USER_FONTS, exist_ok=True)
    gdi = ctypes.windll.gdi32
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, FONTS_KEY) as k:
        for name, fn in FILES.items():
            src, dst = os.path.join(HERE, "fonts", fn), os.path.join(USER_FONTS, fn)
            if not os.path.exists(src):
                raise OSError("The font file %s is missing from the app folder." % fn)
            if not os.path.exists(dst):
                shutil.copyfile(src, dst)
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, dst)
            gdi.AddFontResourceW(dst)
    u32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 0x0002, 2000, None)   # WM_FONTCHANGE


def current():
    """Today's fonts as hex strings, for Undo, with the DPI context and system DPI they
    were read in (restore() scales them when the display scaling changed since)."""
    with _fixed_dpi():
        m = _metrics()
        return {"icon": bytes(_icon_font()).hex(), "menu": bytes(m.lfMenuFont).hex(),
                "status": bytes(m.lfStatusFont).hex(), "context": CONTEXT, "dpi": _system_dpi()}


def _face(lf, bold=False):
    lf.lfFaceName = FACE
    lf.lfWeight = 700 if bold else 500
    lf.lfQuality = 5                       # ClearType


def apply():
    install()
    with _fixed_dpi():
        lf = _icon_font()
        _face(lf)
        u32.SystemParametersInfoW(SPI_SETICONTITLELOGFONT, ctypes.sizeof(lf), ctypes.byref(lf), SPIF)
        m = _metrics()
        _face(m.lfMenuFont, bold=True)
        _face(m.lfStatusFont)
        u32.SystemParametersInfoW(SPI_SETNONCLIENTMETRICS, m.cbSize, ctypes.byref(m), SPIF)


def in_use():
    with _fixed_dpi():
        return _icon_font().lfFaceName == FACE


def _scale(lf, num, den):
    lf.lfHeight = int(round(lf.lfHeight * num / den))
    lf.lfWidth = int(round(lf.lfWidth * num / den))


def _old_snapshot_dpi(fonts, dpi):
    """The DPI a snapshot of 2.3 or older was read at. They don't say: Apply's thread was
    unaware (96-DPI pixels) or, after measuring the screens, DPI-aware (real pixels).
    Apply keeps the heights, so today's fonts tell: saved ~ today's = real pixels (dpi),
    saved ~ today's x 96 / dpi = 96-DPI pixels."""
    if dpi == 96:
        return dpi
    m = _metrics()
    now = {"icon": _icon_font(), "menu": m.lfMenuFont, "status": m.lfStatusFont}
    real = small = 0.0
    for k, lf in fonts.items():
        s, c = abs(lf.lfHeight), abs(now[k].lfHeight)
        if s and c:
            real += abs(s - c) / c
            small += abs(s - c * 96 / dpi) / c
    return 96 if small < real else dpi


def restore(saved):
    """Put back the fonts current() returned (also older snapshots that don't say how
    they were read: see _old_snapshot_dpi)."""
    if not saved:
        return
    with _fixed_dpi():
        fonts = {k: LOGFONTW.from_buffer_copy(bytes.fromhex(saved[k])) for k in ("icon", "menu", "status")}
        dpi = _system_dpi()
        then = (saved.get("dpi") or dpi) if saved.get("context") == CONTEXT else _old_snapshot_dpi(fonts, dpi)
        if then != dpi:                  # read at another scaling: same size on screen
            for lf in fonts.values():
                _scale(lf, dpi, then)
        lf = fonts["icon"]
        u32.SystemParametersInfoW(SPI_SETICONTITLELOGFONT, ctypes.sizeof(lf), ctypes.byref(lf), SPIF)
        m = _metrics()
        m.lfMenuFont = fonts["menu"]
        m.lfStatusFont = fonts["status"]
        u32.SystemParametersInfoW(SPI_SETNONCLIENTMETRICS, m.cbSize, ctypes.byref(m), SPIF)
