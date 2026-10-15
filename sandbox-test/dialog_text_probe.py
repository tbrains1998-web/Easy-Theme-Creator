"""Run as a fresh program: open a folder's Properties sheet and check that its text
can be read, the way Windows draws it:
- the colour the first page gives its labels (what a Static control gets from
  WM_CTLCOLORSTATIC) and the page surface that brush paints;
- checkbox text drawn the themed way (DrawThemeText) on a dark and on a white surface.
Prints one JSON line. Our Windhawk mod should make every text/surface pair readable:
light text on dark surfaces, dark text on light ones."""
import ctypes
import ctypes.wintypes as wt
import json
import os
import time

u32 = ctypes.WinDLL("user32")
g32 = ctypes.WinDLL("gdi32")
ux = ctypes.WinDLL("uxtheme")
sh = ctypes.WinDLL("shell32")
u32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SendMessageW.restype = ctypes.c_ssize_t
u32.GetDC.restype = wt.HDC
u32.FillRect.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), ctypes.c_void_p]
g32.CreateCompatibleDC.argtypes = [wt.HDC]
g32.CreateCompatibleDC.restype = wt.HDC
g32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = ctypes.c_void_p
g32.SelectObject.argtypes = [wt.HDC, ctypes.c_void_p]
g32.CreateSolidBrush.restype = ctypes.c_void_p
g32.GetPixel.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
g32.GetPixel.restype = wt.DWORD
for f in (g32.GetTextColor, g32.GetBkMode):
    f.argtypes = [wt.HDC]
g32.SetTextColor.argtypes = [wt.HDC, wt.DWORD]
g32.SetBkMode.argtypes = [wt.HDC, ctypes.c_int]
ux.IsThemeDialogTextureEnabled.argtypes = [wt.HWND]
ux.OpenThemeData.restype = ctypes.c_void_p
ux.OpenThemeData.argtypes = [wt.HWND, wt.LPCWSTR]
ux.DrawThemeText.argtypes = [ctypes.c_void_p, wt.HDC, ctypes.c_int, ctypes.c_int, wt.LPCWSTR, ctypes.c_int,
                             wt.DWORD, wt.DWORD, ctypes.POINTER(wt.RECT)]
sh.SHObjectProperties.argtypes = [wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR]
ENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def cls(h):
    b = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(h, b, 64)
    return b.value


def rgb(c):
    return "#%02x%02x%02x" % (c & 255, c >> 8 & 255, c >> 16 & 255)


def canvas(w=200, h=30):
    dc = g32.CreateCompatibleDC(None)
    g32.SelectObject(dc, g32.CreateCompatibleBitmap(u32.GetDC(None), w, h))
    return dc


def surface(brush):
    """The average colour a brush paints."""
    dc = canvas(16, 16)
    u32.FillRect(dc, ctypes.byref(wt.RECT(0, 0, 16, 16)), brush)
    px = [g32.GetPixel(dc, x, y) for x in range(0, 16, 3) for y in range(0, 16, 3)]
    return sum(p & 255 for p in px) // len(px) | (sum(p >> 8 & 255 for p in px) // len(px)) << 8 | \
        (sum(p >> 16 & 255 for p in px) // len(px)) << 16


def checkbox_ink(background):
    """Most used ink colour of checkbox text drawn the themed way on `background`."""
    dc = canvas()
    area = wt.RECT(0, 0, 200, 30)
    u32.FillRect(dc, ctypes.byref(area), g32.CreateSolidBrush(background))
    g32.SetBkMode(dc, 1)
    ux.DrawThemeText(ux.OpenThemeData(None, "Button"), dc, 3, 1, "MMMMMMMM", -1, 0x20, 0, ctypes.byref(area))
    ink = {}
    for x in range(120):
        for y in range(25):
            c = g32.GetPixel(dc, x, y)
            if c != background:
                ink[c] = ink.get(c, 0) + 1
    return max(ink, key=ink.get) if ink else background


sh.SHObjectProperties(None, 2, os.environ.get("SystemRoot", r"C:\Windows"), None)
me, sheet = os.getpid(), None
for _ in range(150):
    found = []

    def top(h, _):
        p = wt.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == me and cls(h) == "#32770" and u32.IsWindowVisible(h):
            found.append(h)
        return True
    u32.EnumWindows(ENUM(top), 0)
    if found:
        sheet = found[0]
        break
    time.sleep(0.1)
time.sleep(1.5)
kids = []
u32.EnumChildWindows(sheet, ENUM(lambda h, _: kids.append(h) or True), 0)
page = next(h for h in kids if cls(h) == "#32770")
label = next(h for h in kids if cls(h) == "Static" and u32.GetParent(h) == page)
dc = g32.CreateCompatibleDC(None)
g32.SetTextColor(dc, 0)                               # a fresh control DC: black, opaque
g32.SetBkMode(dc, 2)
brush = u32.SendMessageW(page, 0x0138, dc, label)     # WM_CTLCOLORSTATIC
result = {"label": rgb(g32.GetTextColor(dc)), "page": rgb(surface(brush)) if brush else None,
          "texture": bool(ux.IsThemeDialogTextureEnabled(page)), "system_text": rgb(u32.GetSysColor(18)),
          "checkbox_on_dark": rgb(checkbox_ink(0x242020)), "checkbox_on_white": rgb(checkbox_ink(0xFFFFFF))}
print(json.dumps(result))
u32.PostMessageW(sheet, 0x0010, 0, 0)
time.sleep(0.5)
