"""Explorer, taskbar and Start menu layout, through StartAllBack (if installed).

StartAllBack keeps its Explorer style inside Explorer, not in the registry, so
we press one of its own ready-made looks in its settings window (hidden from
view) and back up its registry settings for undo.
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import time

SAB_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "StartAllBack")
SAB_CFG = os.path.join(SAB_DIR, "StartAllBackCfg.exe")
SAB_KEY = r"HKCU\Software\StartIsBack"

# name shown in our app -> button text in StartAllBack, and what it looks like
LOOKS = {
    "Modern": ("Proper 11", "Windows 11 look: round Start menu, new Explorer bar"),
    "Classic": ("Kinda 10", "Windows 10 look: square Start menu, Explorer ribbon"),
    "Retro": ("Remastered 7", "Windows 7 look: glass Start menu, simple Explorer"),
}

user32 = ctypes.windll.user32
BM_CLICK, WM_CLOSE = 0x00F5, 0x0010
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def available():
    return os.path.exists(SAB_CFG)


def _text(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def _settings_window():
    found = []

    def cb(h, _):
        if _text(h) == "StartAllBack configuration":
            found.append(h)
        return True
    user32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else None


def _button(top, label):
    found = []

    def cb(h, _):
        if _text(h) == label:
            found.append(h)
        return True
    user32.EnumChildWindows(top, EnumProc(cb), 0)
    return found[0] if found else None


def set_look(name):
    """Switch to one of LOOKS. Raises OSError if StartAllBack isn't there or won't respond."""
    if not available():
        raise OSError("StartAllBack is not installed.")
    label = LOOKS[name][0]
    top = _settings_window()
    if top:                                   # it only runs once; start fresh on its Welcome page
        user32.PostMessageW(top, WM_CLOSE, 0, 0)
        time.sleep(1)
    subprocess.Popen([SAB_CFG])
    top = None
    for _ in range(50):
        time.sleep(0.2)
        top = _settings_window()
        if top:
            break
    if not top:
        raise OSError("StartAllBack settings did not open.")
    user32.ShowWindow(top, 0)                       # keep it out of sight
    try:
        btn = _button(top, label)
        if not btn:
            raise OSError("Could not find the '%s' look in StartAllBack." % label)
        user32.SendMessageW(btn, BM_CLICK, 0, 0)
        time.sleep(1.5)
    finally:
        user32.PostMessageW(top, WM_CLOSE, 0, 0)


def backup(path):
    subprocess.run(["reg", "export", SAB_KEY, path, "/y"], capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    return path if os.path.exists(path) else None


def restore(path, look):
    """Undo: go back to `look`, then put StartAllBack's saved settings back."""
    if look:
        set_look(look)
    if path and os.path.exists(path):
        subprocess.run(["reg", "import", path], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)


# ------------------------------------------------------------------ armor Explorer

ADVANCED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"


def armor_explorer():
    """Windows 7 command bar, details panel at the bottom and an always-visible menu
    bar (the armor skin dresses all three). StartAllBack reads these when Explorer
    restarts. Returns the old AlwaysShowMenus value for undo (None = wasn't set)."""
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\StartIsBack") as k:
        winreg.SetValueEx(k, "FrameStyle", 0, winreg.REG_DWORD, 2)      # 0 Win11, 1 ribbon, 2 Win7
        winreg.SetValueEx(k, "BottomDetails", 0, winreg.REG_DWORD, 1)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ADVANCED) as k:
        try:
            old = winreg.QueryValueEx(k, "AlwaysShowMenus")[0]
        except OSError:
            old = None
        winreg.SetValueEx(k, "AlwaysShowMenus", 0, winreg.REG_DWORD, 1)
    return old


def armor_explorer_undo(old_menus):
    """Menu bar setting back (StartAllBack's own values come back with its backup)."""
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ADVANCED) as k:
        if old_menus is None:
            try:
                winreg.DeleteValue(k, "AlwaysShowMenus")
            except OSError:
                pass
        else:
            winreg.SetValueEx(k, "AlwaysShowMenus", 0, winreg.REG_DWORD, old_menus)
