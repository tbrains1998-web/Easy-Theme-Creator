"""Switch Windows to a theme by setting each part directly.

Opening a .theme file is not reliable (Windows can silently ignore it), so we
write the same settings to the current user's registry ourselves and tell
Windows to reload them. Nothing here needs admin rights.
"""
import ctypes
import winreg

import assets
import theme_core

HKCU = winreg.HKEY_CURRENT_USER
SPI_SETDESKWALLPAPER = 0x14
SPI_SETCURSORS = 0x57
SPIF_UPDATE_AND_SEND = 0x03
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x1A


def _set(path, name, value, kind=winreg.REG_SZ):
    with winreg.CreateKey(HKCU, path) as key:
        winreg.SetValueEx(key, name, 0, kind, value)


def _broadcast(area):
    ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, area,
                                             0x0002, 3000, ctypes.byref(ctypes.c_ulong()))


def wallpaper(path, style="10", tile="0"):
    """Set the desktop picture (style 10 = Fill). An empty path removes the picture
    (a plain background colour)."""
    _set(r"Control Panel\Desktop", "WallpaperStyle", style)
    _set(r"Control Panel\Desktop", "TileWallpaper", tile)
    if not ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path,
                                                      SPIF_UPDATE_AND_SEND):
        raise OSError("Windows would not set the wallpaper.")


def colors(accent, dark, color_bars):
    r, g, b = theme_core._rgb(accent)
    abgr = 0xFF000000 | (b << 16) | (g << 8) | r
    argb = 0xC4000000 | (r << 16) | (g << 8) | b
    light = 0 if dark else 1
    personalize = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    _set(personalize, "AppsUseLightTheme", light, winreg.REG_DWORD)
    _set(personalize, "SystemUsesLightTheme", light, winreg.REG_DWORD)
    _set(personalize, "ColorPrevalence", int(color_bars), winreg.REG_DWORD)
    accent_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"
    # Windows uses 8 shades of the accent, light to dark.
    shades = b""
    for f in (1.6, 1.4, 1.2, 1.0, 0.8, 0.6, 0.4, 0.3):
        shades += bytes(min(255, int(c * f)) for c in (r, g, b)) + b"\x00"
    _set(accent_key, "AccentPalette", shades, winreg.REG_BINARY)
    _set(accent_key, "AccentColorMenu", abgr, winreg.REG_DWORD)
    _set(accent_key, "StartColorMenu", abgr, winreg.REG_DWORD)
    dwm = r"Software\Microsoft\Windows\DWM"
    _set(dwm, "AccentColor", abgr, winreg.REG_DWORD)
    _set(dwm, "ColorizationColor", argb, winreg.REG_DWORD)
    _set(dwm, "ColorizationAfterglow", argb, winreg.REG_DWORD)
    _set(dwm, "ColorPrevalence", int(color_bars), winreg.REG_DWORD)
    _broadcast("ImmersiveColorSet")


def pointers(scheme_name, files):
    for key, path in files.items():
        _set(r"Control Panel\Cursors", key, path, winreg.REG_EXPAND_SZ)
    _set(r"Control Panel\Cursors", "", scheme_name)
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, SPIF_UPDATE_AND_SEND)


def icons(files):
    base = r"Software\Classes\CLSID\%s\DefaultIcon"
    # Desktop icon settings' own key wins over the one above once it exists.
    explorer = r"Software\Microsoft\Windows\CurrentVersion\Explorer\CLSID\%s\DefaultIcon"
    for kind, key in theme_core.ICON_KEYS.items():
        _set(base % key, "", files[kind] + ",0")
        _set(explorer % key, "", files[kind] + ",0")
    _set(base % theme_core.BIN_KEY, "", files["bin_empty"] + ",0")
    _set(base % theme_core.BIN_KEY, "Full", files["bin_full"] + ",0")
    _set(base % theme_core.BIN_KEY, "Empty", files["bin_empty"] + ",0")
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # refresh icons


def sounds(files):
    for app, event, snd in assets.SOUND_EVENTS:
        _set(r"AppEvents\Schemes\Apps\%s\%s\.Current" % (app, event), "", files[snd])
    _set(r"AppEvents\Schemes", "", ".Current")


def restart_explorer():
    """Restart Explorer so the taskbar and desktop pick up new colors and icons."""
    import subprocess
    hidden = subprocess.CREATE_NO_WINDOW
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], creationflags=hidden)
    subprocess.Popen(["explorer.exe"])


def apply(theme, accent, dark, color_bars):
    """Apply everything in `theme` (from theme_core.make_theme).

    Returns a list of parts that failed, as (part, error) pairs.
    """
    steps = [("Wallpaper", lambda: wallpaper(theme["wallpaper"])),
             ("Colors", lambda: colors(accent, dark, color_bars))]
    if theme["pointers"]:
        steps.append(("Mouse pointers", lambda: pointers(theme["name"], theme["pointers"])))
    if theme["icons"]:
        steps.append(("Desktop icons", lambda: icons(theme["icons"])))
    if theme["sounds"]:
        steps.append(("Sounds", lambda: sounds(theme["sounds"])))
    failed = []
    for part, step in steps:
        try:
            step()
        except Exception as e:  # keep going so one broken part doesn't stop the rest
            failed.append((part, str(e)))
    return failed


def colors_reload():
    """Tell Windows the color settings changed (used after Undo restores them)."""
    _broadcast("ImmersiveColorSet")


def keep_bars_black():
    """Accent color off on the taskbar and window title bars (they stay black)."""
    _set(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "ColorPrevalence", 0,
         winreg.REG_DWORD)
    _set(r"Software\Microsoft\Windows\DWM", "ColorPrevalence", 0, winreg.REG_DWORD)
    _broadcast("ImmersiveColorSet")


# Classic (Win32) system colors. Light-only screens such as Control Panel's header,
# Programs and Features and list headers paint with these, so a dark set makes
# them match. Text stays near-white on dark; the accent is used for highlights.
SYSCOLOR_IDS = {
    "Scrollbar": 0, "Background": 1, "ActiveTitle": 2, "InactiveTitle": 3, "Menu": 4,
    "Window": 5, "WindowFrame": 6, "MenuText": 7, "WindowText": 8, "TitleText": 9,
    "ActiveBorder": 10, "InactiveBorder": 11, "AppWorkspace": 12, "Hilight": 13,
    "HilightText": 14, "ButtonFace": 15, "ButtonShadow": 16, "GrayText": 17,
    "ButtonText": 18, "InactiveTitleText": 19, "ButtonHilight": 20, "ButtonDkShadow": 21,
    "ButtonLight": 22, "InfoText": 23, "InfoWindow": 24, "HotTrackingColor": 26,
    "GradientActiveTitle": 27, "GradientInactiveTitle": 28, "MenuHilight": 29, "MenuBar": 30,
}


def dark_palette(accent):
    """The dark classic-app palette as {system colour index: (r, g, b)} - what
    dark_syscolors() sets live, and what the skin's own colour table gets too."""
    return {SYSCOLOR_IDS[n]: rgb for n, rgb in _dark_colors(accent).items()}


def _dark_colors(accent):
    r, g, b = theme_core._rgb(accent)
    m = max(r, g, b) or 1
    bright = tuple(min(255, int(v / m * 255 * 0.75 + 255 * 0.29)) for v in (r, g, b))
    deep = tuple(int(v / m * 120) for v in (r, g, b))
    colors = {
        "Scrollbar": (30, 30, 34), "Background": (0, 0, 0), "ActiveTitle": (24, 24, 27),
        "InactiveTitle": (20, 20, 22), "Menu": (24, 24, 27), "Window": (18, 18, 20),
        "WindowFrame": (60, 60, 64), "MenuText": (230, 230, 230), "WindowText": (230, 230, 230),
        "TitleText": (230, 230, 230), "ActiveBorder": (40, 40, 44), "InactiveBorder": (30, 30, 34),
        "AppWorkspace": (14, 14, 16), "Hilight": deep, "HilightText": (255, 255, 255),
        "ButtonFace": (32, 32, 36), "ButtonShadow": (14, 14, 16), "GrayText": (138, 138, 138),
        "ButtonText": (230, 230, 230), "InactiveTitleText": (176, 176, 176),
        "ButtonHilight": (72, 72, 78), "ButtonDkShadow": (6, 6, 7), "ButtonLight": (52, 52, 56),
        "InfoText": (230, 230, 230), "InfoWindow": (28, 28, 32), "HotTrackingColor": bright,
        "GradientActiveTitle": (32, 32, 36), "GradientInactiveTitle": (24, 24, 27),
        "MenuHilight": deep, "MenuBar": (24, 24, 27),
    }
    return colors


def dark_syscolors(accent):
    colors = _dark_colors(accent)
    for name, (cr, cg, cb) in colors.items():
        _set(r"Control Panel\Colors", name, "%d %d %d" % (cr, cg, cb))
    ids = (ctypes.c_int * len(colors))(*[SYSCOLOR_IDS[n] for n in colors])
    vals = (ctypes.c_uint32 * len(colors))(*[c[0] | c[1] << 8 | c[2] << 16 for c in colors.values()])
    ctypes.windll.user32.SetSysColors(len(colors), ids, vals)     # live, for this session


def reload_syscolors():
    """After Undo restored the Control Panel Colors key, show those colors now."""
    import winreg
    names, vals = [], []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Colors") as k:
            for name, ident in SYSCOLOR_IDS.items():
                try:
                    r, g, b = (int(x) for x in winreg.QueryValueEx(k, name)[0].split())
                except (OSError, ValueError):
                    continue
                names.append(ident)
                vals.append(r | g << 8 | b << 16)
    except OSError:
        return
    if names:
        ctypes.windll.user32.SetSysColors(len(names), (ctypes.c_int * len(names))(*names),
                                          (ctypes.c_uint32 * len(vals))(*vals))


THEMES_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes"


def register_theme(theme_path, style_path=None):
    """Make Windows' "current theme" our .theme file, pointing at our skin.

    Windows re-applies the current theme file at times (e.g. when Settings >
    Personalization opens). If that file names another skin, ours is replaced by
    stock Aero, so the file must name the skin we switched to. Returns the old
    CurrentTheme value for undo."""
    if style_path:
        with open(theme_path, encoding="utf-16") as f:
            lines = f.read().splitlines()
        section = None
        for i, line in enumerate(lines):
            if line.startswith("["):
                section = line.strip().lower()
            elif section == "[visualstyles]" and line.lower().startswith("path="):
                lines[i] = "Path=" + style_path
        with open(theme_path, "w", encoding="utf-16") as f:
            f.write("\n".join(lines) + "\n")
    with winreg.CreateKey(HKCU, THEMES_KEY) as k:
        try:
            old = winreg.QueryValueEx(k, "CurrentTheme")[0]
        except OSError:
            old = None
        winreg.SetValueEx(k, "CurrentTheme", 0, winreg.REG_SZ, theme_path)
    return old


def restore_current_theme(old):
    if old:
        _set(THEMES_KEY, "CurrentTheme", old)
