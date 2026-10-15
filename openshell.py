"""Windows 7 Start menu through Open-Shell (free, MIT), in the armor skin.

Open-Shell's menu runs inside Explorer and keeps its settings in memory, so the
settings are written to the registry first and Open-Shell is restarted together
with Explorer (Apply restarts Explorer anyway). Skins must live in Open-Shell's own
Skins folder under Program Files; a one-time admin step creates our skin file there
and lets users overwrite it, after which every Apply just rewrites it.
"""
import ctypes
import os
import subprocess
import tempfile
import time
import winreg

import openshell_skin

EXE = os.path.join(openshell_skin.OPEN_SHELL, "StartMenu.exe")
SKIN_FILE = os.path.join(openshell_skin.SKINS, openshell_skin.NAME + ".skin7")
KEY = r"Software\OpenShell\StartMenu"
NAMES = ("MenuStyle", "SkinW7", "SkinVariationW7", "SkinOptionsW7", "EnableStartButton")   # what apply() writes
HIDDEN = subprocess.CREATE_NO_WINDOW


def available():
    return os.path.exists(EXE) and openshell_skin.available()


def _writable(path):
    try:
        with open(path, "r+b"):
            return True
    except OSError:
        return False


def setup_access(hwnd=None):
    """Once, with an admin prompt: create our skin file and let users replace it."""
    seed = os.path.join(tempfile.gettempdir(), "etc-armor.skin7")
    openshell_skin.build((200, 40, 40), seed)
    ps = ("Copy-Item -LiteralPath '{s}' -Destination '{d}' -Force; "
          "icacls '{d}' /grant '*S-1-5-32-545:M' | Out-Null").format(s=seed, d=SKIN_FILE)
    import xaml_styles                                   # reuses its elevated-launch helper
    sei = xaml_styles._SEI(cbSize=ctypes.sizeof(xaml_styles._SEI), fMask=0x40, hwnd=hwnd, lpVerb="runas",
                           lpFile="powershell.exe", nShow=0,
                           lpParameters='-NoProfile -ExecutionPolicy Bypass -Command "%s"' % ps)
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
        raise OSError("The administrator prompt was cancelled.")
    ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_void_p(sei.hProcess), 120000)
    ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(sei.hProcess))
    if not _writable(SKIN_FILE):
        raise OSError("The Start menu skin still can't be written.")


def _settings_snapshot():
    """Every value apply() writes, as [data, type], or None when it isn't set (also when
    Open-Shell has no settings yet - a fresh install), so undo knows to delete it."""
    out = dict.fromkeys(NAMES)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY + r"\Settings") as k:
            for n in NAMES:
                try:
                    out[n] = list(winreg.QueryValueEx(k, n))
                except OSError:
                    pass
    except OSError:
        pass
    return out


def _write_settings():
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY + r"\Settings") as k:
        winreg.SetValueEx(k, "MenuStyle", 0, winreg.REG_SZ, "Win7")
        winreg.SetValueEx(k, "SkinW7", 0, winreg.REG_SZ, openshell_skin.NAME)
        winreg.SetValueEx(k, "SkinVariationW7", 0, winreg.REG_SZ, "")
        winreg.SetValueEx(k, "SkinOptionsW7", 0, winreg.REG_MULTI_SZ,
                          ["USER_IMAGE=1", "SMALL_ICONS=0", "LARGE_FONT=0", "WHITE_SUBMENUS2=0"])
        winreg.SetValueEx(k, "EnableStartButton", 0, winreg.REG_DWORD, 0)   # the orb is the taskbar's
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as k:
        winreg.SetValueEx(k, "ShowedStyle2", 0, winreg.REG_DWORD, 1)        # no first-run dialog


def _running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq StartMenu.exe", "/NH"], capture_output=True,
                             text=True, creationflags=HIDDEN, timeout=15).stdout
    except subprocess.TimeoutExpired:
        return True                 # can't tell: assume it is still there
    return "startmenu.exe" in out.lower()


def stop():
    """Before Explorer restarts: stop Open-Shell so it re-reads settings on start.
    `-exit` only asks the running copy to quit, and it writes its own settings back
    as it goes - so wait until it is really gone before anyone writes settings."""
    if os.path.exists(EXE):
        try:
            subprocess.run([EXE, "-exit"], creationflags=HIDDEN, timeout=20)
        except subprocess.TimeoutExpired:
            pass                    # a hung copy (seen while Explorer was swamped): killed below
        for _ in range(40):
            if not _running():
                break
            time.sleep(0.25)
        else:
            # Still there: end it. Its unsaved in-memory settings are lost, which is fine -
            # Apply and Undo write the settings themselves right after this.
            subprocess.run(["taskkill", "/F", "/IM", "StartMenu.exe"], capture_output=True,
                           creationflags=HIDDEN, timeout=30)
            for _ in range(20):
                if not _running():
                    break
                time.sleep(0.25)
        time.sleep(1.0)


def start():
    """After Explorer is back."""
    if os.path.exists(EXE):
        subprocess.Popen([EXE, "-autorun"], creationflags=HIDDEN | subprocess.DETACHED_PROCESS,
                         cwd=os.path.dirname(EXE))   # not the app's folder: it stays running


def apply(accent, hwnd=None):
    """Rebuild the armor skin in `accent` and select it. Returns the old settings for undo."""
    before = _settings_snapshot()
    if not os.path.exists(SKIN_FILE) or not _writable(SKIN_FILE):
        setup_access(hwnd)
    # Users may only overwrite our one file there (not create files), so build it in
    # TEMP and copy the bytes over it.
    tmp = os.path.join(tempfile.gettempdir(), "etc-armor-new.skin7")
    openshell_skin.build(accent, tmp)
    with open(tmp, "rb") as f:
        data = f.read()
    for attempt in range(10):
        try:
            with open(SKIN_FILE, "wb") as f:
                f.write(data)
            break
        except OSError:                   # Open-Shell has it open this very moment
            if attempt == 9:
                raise
            time.sleep(0.5)
    os.remove(tmp)
    _write_settings()
    return before


def restore(before):
    """Put back the values apply() changed; one that wasn't set before is deleted.
    (Older snapshots taken before Open-Shell had any settings are an empty dict.)"""
    if before is None:
        return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY + r"\Settings") as k:
        for n in NAMES:
            v = before.get(n)
            if v is None:
                try:
                    winreg.DeleteValue(k, n)
                except OSError:
                    pass
            else:
                winreg.SetValueEx(k, n, 0, v[1], v[0])
