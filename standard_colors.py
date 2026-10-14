"""Standard colours for chosen apps, through our own Windhawk mod.

Some programs set a few of their own colours (a white text box) and take the rest
from Windows; with the dark palette the halves stop matching and text turns
unreadable. The mod (installer\\windhawk-mod\\easy-theme-creator-standard-colors.wh.cpp)
gives every program on its list Windows' normal light colours and no window skin,
from the program's next start. This module keeps that list: the app's "Fix an app"
button lets the user click the window that looks wrong.
"""
import ctypes
import ctypes.wintypes as wt
import os
import time
import winreg

import xaml_styles

MOD = "easy-theme-creator-standard-colors"
KEY = xaml_styles.MODS_KEY + "\\" + MOD + "\\Settings"


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


def pick_window(timeout=15, skip_pid=None):
    """Wait for a mouse click and return (exe name, window title, pid) of the window
    under it; None when the time runs out or the click lands on a window of `skip_pid`
    (our own). The caller runs this in a thread."""
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
            return os.path.basename(buf.value), title.value, pid.value
        time.sleep(0.03)
    return None
