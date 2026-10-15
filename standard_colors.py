"""Standard colours for chosen apps, through our own Windhawk mod.

Some programs set a few of their own colours (a white text box) and take the rest
from Windows; with the dark palette the halves stop matching and text turns
unreadable. The mod (installer\\windhawk-mod\\easy-theme-creator-standard-colors.wh.cpp)
gives every program on its list Windows' normal light colours and no window skin,
from the program's next start. This module keeps that list: the app's "Fix an app"
button lets the user click the window that looks wrong. windhawk_skips() tells when
that can't help because the mod never loads in the program (Windhawk leaves games
alone, and the mod stays out of anti-cheat games).
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import time
import winreg

import xaml_styles

MOD = "easy-theme-creator-standard-colors"
KEY = xaml_styles.MODS_KEY + "\\" + MOD + "\\Settings"
WINDHAWK_SETTINGS = r"SOFTWARE\Windhawk\Engine\Settings"

# Windhawk's built-in "Exclude well-known games" list (as in its 1.7.3 engine,
# Engine\1.7.3\64\windhawk.dll), in force while its setting InjectIntoGames is 0, the
# default: Windhawk doesn't inject into these programs at all, so no mod reaches them.
_GAME_FOLDERS = ("2K Games", "Activision", "Battle.net", "Bethesda Softworks", "Bethesda.net Launcher",
                 "Blizzard Entertainment", "EA Games", "EA", "EasyAntiCheat_EOS", "Electronic Arts",
                 "Epic Games", "GOG Galaxy", r"Google\Play Games", r"Google\Play Games Services",
                 "Grinding Gear Games", "Microsoft Games", "Origin Games", "Paradox Interactive", "Riot Games",
                 "Rockstar Games", "Square Enix", "Steam", "Ubisoft", "Valve", "Wargaming.net")
WINDHAWK_GAMES = "|".join([r"?:\Program Files%s\%s\*" % (x86, f) for f in _GAME_FOLDERS for x86 in ("", " (x86)")] +
                          [r"?:\Epic Games\*", r"?:\Games\*", r"?:\Riot Games\*",
                           r"?:\WindowsApps\Microsoft.MinecraftUWP_*\*", r"?:\WindowsApps\Microsoft.SunriseBaseGame_*\*",
                           r"*\steamapps\common\*"])
# ... and its "Exclude known incompatible programs" (InjectIntoIncompatiblePrograms 0).
WINDHAWK_INCOMPATIBLE = r"%ProgramFiles%\Oracle\VirtualBox\*|%ProgramFiles(X86)%\Oracle\VirtualBox\*"

# The mod's own anti-cheat rule (AntiCheatNearby in the .wh.cpp - keep the two the same):
# it doesn't load where one of these is in the program's folder or up to three folders up.
_ANTI_CHEAT_FILES = ("EasyAntiCheat", "EasyAntiCheat_EOS", "start_protected_game.exe", "BattlEye",
                     "EAAntiCheat.GameServiceLauncher.exe", "mhyprot2.sys", "mhyprot3.sys", "mhypbase.dll",
                     "GameGuard", "XIGNCODE", "AntiCheatExpert")
_ANTI_CHEAT_EXES = ("vgc.exe", "vgtray.exe")


def available():
    return xaml_styles.mod_installed(MOD)


def writable():
    return xaml_styles.writable(MOD)


def apps():
    """The programs on the list (executable names)."""
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, KEY) as k:
            i = 0
            while True:
                try:
                    v = winreg.QueryValueEx(k, "apps[%d]" % i)[0]
                except OSError:
                    break
                if not v:
                    break
                out.append(v)
                i += 1
    except OSError:
        pass
    return out


def _write(names):
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, KEY, 0,
                        winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
        i = 0
        while True:                                   # drop the old list first
            try:
                winreg.QueryValueEx(k, "apps[%d]" % i)
            except OSError:
                break
            winreg.DeleteValue(k, "apps[%d]" % i)
            i += 1
        for i, n in enumerate(names):
            winreg.SetValueEx(k, "apps[%d]" % i, 0, winreg.REG_SZ, n)
        winreg.SetValueEx(k, "apps[%d]" % len(names), 0, winreg.REG_SZ, "")   # end marker


def add(exe):
    names = apps()
    if exe.lower() not in (n.lower() for n in names):
        names.append(exe)
        _write(names)


def remove(exe):
    _write([n for n in apps() if n.lower() != exe.lower()])


def clear():
    if available() and writable() and apps():
        _write([])


def _values(key, names):
    """Those of `names` that exist under HKLM\\`key`."""
    out = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            for n in names:
                try:
                    out[n] = winreg.QueryValueEx(k, n)[0]
                except OSError:
                    pass
    except OSError:
        pass
    return out


def _matches(path, patterns):
    """Windhawk's process-list test: "|"-separated patterns, case-insensitive, * (also
    across folders) and ? wildcards, %VARIABLES% expanded; a pattern without a backslash
    is compared with the program's file name only."""
    name = path.rsplit("\\", 1)[-1]
    for p in (patterns or "").split("|"):
        p = re.sub(r"%([^%]+)%", lambda m: os.environ.get(m.group(1), m.group(0)), p.strip())
        if not p:
            continue
        rx = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in p)
        if re.fullmatch(rx, path if "\\" in p else name, re.IGNORECASE | re.DOTALL):
            return True
    return False


def _anti_cheat_near(path):
    """The mod's AntiCheatNearby(), for a program's full path."""
    folder, name = os.path.split(path)
    if path.startswith("\\") or path[1:2] != ":":
        return False                                   # network or odd paths: not looked at
    if name.lower() in _ANTI_CHEAT_EXES:
        return True
    windir = os.environ.get("SystemRoot", r"C:\Windows").rstrip("\\")
    if path.lower().startswith(windir.lower() + "\\"):
        return False                                   # Windows' own programs
    if ctypes.windll.kernel32.GetDriveTypeW(path[:2] + "\\") == 4:      # DRIVE_REMOTE
        return False
    for _ in range(4):
        if len(folder) <= 3:                           # "C:\" - the drive root isn't looked at
            break
        if any(os.path.exists(os.path.join(folder, n)) for n in _ANTI_CHEAT_FILES):
            return True
        folder = os.path.dirname(folder)
    return False


def skip_reason(path):
    """Why the mod never loads in the program at `path` (full path) - so putting it on
    the list can't help - or None when it does load there:
      "mod"       the mod stays out on purpose: anti-cheat games (its exclusion list, an
                  anti-cheat next to the program) and Windhawk itself
      "games"     Windhawk's own "Exclude well-known games" setting (on by default) skips
                  it: a game folder such as ?:/Games or steamapps/common, game launchers
      "windhawk"  Windhawk's process exclusion list, or its known incompatible programs"""
    if not path:
        return None
    mod = _values(xaml_styles.MODS_KEY + "\\" + MOD, ("Exclude", "ExcludeCustom", "IncludeExcludeCustomOnly"))
    excludes = mod.get("ExcludeCustom", "")
    if not mod.get("IncludeExcludeCustomOnly"):
        excludes += "|" + mod.get("Exclude", "")
    if _matches(path, excludes) or _anti_cheat_near(path):
        return "mod"
    wh = _values(WINDHAWK_SETTINGS, ("Include", "Exclude", "InjectIntoGames", "InjectIntoIncompatiblePrograms"))
    if _matches(path, wh.get("Include")):              # "inject even if they're excluded"
        return None
    if not wh.get("InjectIntoGames") and _matches(path, WINDHAWK_GAMES):
        return "games"
    if _matches(path, wh.get("Exclude")) or (
            not wh.get("InjectIntoIncompatiblePrograms") and _matches(path, WINDHAWK_INCOMPATIBLE)):
        return "windhawk"
    return None


def windhawk_skips(path):
    """True when the mod never loads in the program at `path`, so "Fix an app" can't
    help it (skip_reason() says why)."""
    return skip_reason(path) is not None


def pick_window(timeout=15, skip_pid=None):
    """Wait for a mouse click and return (exe name, window title, pid, full exe path)
    of the window under it; None when the time runs out or the click lands on a window
    of `skip_pid` (our own). The caller runs this in a thread."""
    u, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    while u.GetAsyncKeyState(0x01) & 0x8000:         # wait for the button to be up first
        time.sleep(0.05)
    end = time.time() + timeout
    while time.time() < end:
        if u.GetAsyncKeyState(0x01) & 0x8000:
            pt = wt.POINT()
            u.GetCursorPos(ctypes.byref(pt))
            hwnd = u.GetAncestor(u.WindowFromPoint(pt), 2)          # GA_ROOT
            pid = wt.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value or pid.value == skip_pid:
                return None
            h = k32.OpenProcess(0x1000, False, pid.value)           # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return None
            buf = ctypes.create_unicode_buffer(1024)
            size = wt.DWORD(1024)
            ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            k32.CloseHandle(h)
            if not ok:
                return None
            title = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(hwnd, title, 256)
            return os.path.basename(buf.value), title.value, pid.value, buf.value
        time.sleep(0.03)
    return None
