"""Sci-fi lettering: Windows' icon, menu and status-bar fonts switched to Orbitron.

Orbitron (The League of Moveable Type, SIL Open Font License, files in fonts\\) is
installed for the current user only. The icon font is what Explorer uses for file
and folder names (and the navigation pane); menus and status bars use the others.
Title bars and dialog text keep Windows' font so everything stays readable.
Programs that are already open pick it up after a sign-out.
"""
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
    """Today's fonts as hex strings, for Undo."""
    m = _metrics()
    return {"icon": bytes(_icon_font()).hex(), "menu": bytes(m.lfMenuFont).hex(),
            "status": bytes(m.lfStatusFont).hex()}


def _face(lf, bold=False):
    lf.lfFaceName = FACE
    lf.lfWeight = 700 if bold else 500
    lf.lfQuality = 5                       # ClearType


def apply():
    install()
    lf = _icon_font()
    _face(lf)
    u32.SystemParametersInfoW(SPI_SETICONTITLELOGFONT, ctypes.sizeof(lf), ctypes.byref(lf), SPIF)
    m = _metrics()
    _face(m.lfMenuFont, bold=True)
    _face(m.lfStatusFont)
    u32.SystemParametersInfoW(SPI_SETNONCLIENTMETRICS, m.cbSize, ctypes.byref(m), SPIF)


def in_use():
    return _icon_font().lfFaceName == FACE


def restore(saved):
    """Put back the fonts current() returned."""
    if not saved:
        return
    lf = LOGFONTW.from_buffer_copy(bytes.fromhex(saved["icon"]))
    u32.SystemParametersInfoW(SPI_SETICONTITLELOGFONT, ctypes.sizeof(lf), ctypes.byref(lf), SPIF)
    m = _metrics()
    m.lfMenuFont = LOGFONTW.from_buffer_copy(bytes.fromhex(saved["menu"]))
    m.lfStatusFont = LOGFONTW.from_buffer_copy(bytes.fromhex(saved["status"]))
    u32.SystemParametersInfoW(SPI_SETNONCLIENTMETRICS, m.cbSize, ctypes.byref(m), SPIF)
