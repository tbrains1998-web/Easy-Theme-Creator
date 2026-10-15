"""Run as a fresh program: open a folder's Properties sheet and ask its first page
which text colour it gives its labels (what a Static control gets from
WM_CTLCOLORSTATIC), and draw checkbox text the themed way. Prints
"<label colour> <system text colour> <page texture on> <checkbox ink>". With our Windhawk mod the two colours match; without it the
label colour stays at what the DC had (here a marker, #123456)."""
import ctypes
import ctypes.wintypes as wt
import os
import time

u32 = ctypes.WinDLL("user32")
g32 = ctypes.WinDLL("gdi32")
ux = ctypes.WinDLL("uxtheme")
sh = ctypes.WinDLL("shell32")
u32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SendMessageW.restype = ctypes.c_ssize_t
g32.CreateCompatibleDC.argtypes = [wt.HDC]
g32.CreateCompatibleDC.restype = wt.HDC
for f in (g32.GetTextColor, g32.GetBkMode):
    f.argtypes = [wt.HDC]
g32.SetTextColor.argtypes = [wt.HDC, wt.DWORD]
g32.SetBkMode.argtypes = [wt.HDC, ctypes.c_int]
ux.IsThemeDialogTextureEnabled.argtypes = [wt.HWND]
sh.SHObjectProperties.argtypes = [wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR]
ENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def cls(h):
    b = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(h, b, 64)
    return b.value


def rgb(c):
    return "#%02x%02x%02x" % (c & 255, c >> 8 & 255, c >> 16 & 255)


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
g32.SetTextColor(dc, 0x563412)                        # marker #123456
g32.SetBkMode(dc, 2)                                  # OPAQUE, as a fresh control DC
u32.SendMessageW(page, 0x0138, dc, label)             # WM_CTLCOLORSTATIC
label_colour = g32.GetTextColor(dc)

# Checkbox text the way the button draws it: DrawThemeText on its part (black when the
# theme gives the part no colour, unless our mod steps in). Most used ink colour wins.
ux.OpenThemeData.restype = ctypes.c_void_p
ux.OpenThemeData.argtypes = [wt.HWND, wt.LPCWSTR]
ux.DrawThemeText.argtypes = [ctypes.c_void_p, wt.HDC, ctypes.c_int, ctypes.c_int, wt.LPCWSTR, ctypes.c_int,
                             wt.DWORD, wt.DWORD, ctypes.POINTER(wt.RECT)]
u32.GetDC.restype = wt.HDC
u32.FillRect.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), ctypes.c_void_p]
g32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = ctypes.c_void_p
g32.SelectObject.argtypes = [wt.HDC, ctypes.c_void_p]
g32.GetPixel.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
g32.GetPixel.restype = wt.DWORD
g32.CreateSolidBrush.restype = ctypes.c_void_p
mdc = g32.CreateCompatibleDC(None)
g32.SelectObject(mdc, g32.CreateCompatibleBitmap(u32.GetDC(None), 200, 30))
area = wt.RECT(0, 0, 200, 30)
u32.FillRect(mdc, ctypes.byref(area), g32.CreateSolidBrush(0x808080))      # mid grey: any ink shows
g32.SetBkMode(mdc, 1)
ux.DrawThemeText(ux.OpenThemeData(None, "Button"), mdc, 3, 1, "MMMMMMMM", -1, 0x20, 0, ctypes.byref(area))
ink = {}
for x in range(120):
    for y in range(25):
        c = g32.GetPixel(mdc, x, y)
        if c != 0x808080:
            ink[c] = ink.get(c, 0) + 1
checkbox = max(ink, key=ink.get) if ink else 0x808080
print(rgb(label_colour), rgb(u32.GetSysColor(18)), int(bool(ux.IsThemeDialogTextureEnabled(page))), rgb(checkbox))
u32.PostMessageW(sheet, 0x0010, 0, 0)
time.sleep(0.5)
