"""Windows 7 Start menu through Open-Shell (free, MIT), in the armor skin.

Open-Shell's menu runs inside Explorer and keeps its settings in memory, so the
settings are written to the registry first and Open-Shell is restarted together
with Explorer (Apply restarts Explorer anyway). Skins must live in Open-Shell's own
Skins folder under Program Files; a one-time admin step creates our skin file there
and lets users overwrite it, after which every Apply just rewrites it.
"""
import ctypes
import ctypes.wintypes as wt
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
STOP_SECONDS = 25                     # stop() waits at most this long before ending it


def available():
    return os.path.exists(EXE) and openshell_skin.available()


def _writable(path):
    try:
        with open(path, "r+b"):
            return True
    except OSError:
        return False


# The paths go in as script arguments, not inside the command text: a user name with an
# apostrophe (TEMP is in the profile) would end a quoted PowerShell string early.
SETUP_PS = r"""
param([string]$Seed, [string]$Dest)
Copy-Item -LiteralPath $Seed -Destination $Dest -Force
icacls $Dest /grant '*S-1-5-32-545:M' | Out-Null
"""


def setup_access(hwnd=None):
    """Once, with an admin prompt: create our skin file and let users replace it."""
    seed = os.path.join(tempfile.gettempdir(), "etc-armor.skin7")
    openshell_skin.build((200, 40, 40), seed)
    script = os.path.join(tempfile.gettempdir(), "etc-openshell-access.ps1")
    with open(script, "w", encoding="utf-8") as f:
        f.write(SETUP_PS)
    import xaml_styles                                   # reuses its elevated-launch helper
    sei = xaml_styles._SEI(cbSize=ctypes.sizeof(xaml_styles._SEI), fMask=0x40, hwnd=hwnd, lpVerb="runas",
                           lpFile="powershell.exe", nShow=0,
                           lpParameters='-NoProfile -ExecutionPolicy Bypass -File "%s" "%s" "%s"'
                                        % (script, seed, SKIN_FILE))
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


class _ProcessEntry(ctypes.Structure):          # PROCESSENTRY32W
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


_KERNEL32 = []


def _k32():
    if _KERNEL32:
        return _KERNEL32[0]
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)      # own copy: argtypes set here only
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(_ProcessEntry)]
    k32.ProcessIdToSessionId.argtypes = [wt.DWORD, ctypes.POINTER(wt.DWORD)]
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
    k32.CloseHandle.argtypes = [wt.HANDLE]
    _KERNEL32.append(k32)
    return k32


def _pids():
    """Process ids of the StartMenu.exe copies in this sign-in session, or None when the
    process list can't be read. (Read through a Toolhelp snapshot: tasklist's text output
    is in the console code page, which broke on German Windows.) Another account's copy
    can't be opened, so its session can't be read either: it isn't ours and is skipped."""
    k32 = _k32()
    snap = None
    for _ in range(3):                     # can fail with ERROR_BAD_LENGTH while processes start
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)                  # TH32CS_SNAPPROCESS
        if snap and snap != wt.HANDLE(-1).value:
            break
        snap = None
        time.sleep(0.05)
    if snap is None:
        return None
    try:
        mine, sid = wt.DWORD(), wt.DWORD()
        if not k32.ProcessIdToSessionId(os.getpid(), ctypes.byref(mine)):
            return None
        out = []
        entry = _ProcessEntry(dwSize=ctypes.sizeof(_ProcessEntry))
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == "startmenu.exe" and \
                    k32.ProcessIdToSessionId(entry.th32ProcessID, ctypes.byref(sid)) and sid.value == mine.value:
                out.append(entry.th32ProcessID)
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
        return out
    finally:
        k32.CloseHandle(snap)


def _running():
    pids = _pids()
    return pids is None or bool(pids)      # can't tell: assume it is still there


def _kill(pids):
    """End these StartMenu.exe processes (checking each is still StartMenu.exe, in case the
    id was reused). Direct API calls: no helper program that could hang too."""
    k32 = _k32()
    for pid in pids or ():
        h = k32.OpenProcess(0x0001 | 0x1000, False, pid)   # TERMINATE | QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            buf, n = ctypes.create_unicode_buffer(1024), wt.DWORD(1024)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) and \
                    os.path.basename(buf.value).lower() == "startmenu.exe":
                k32.TerminateProcess(h, 1)
        finally:
            k32.CloseHandle(h)


def stop():
    """Before Explorer restarts: stop Open-Shell so it re-reads settings on start.
    `-exit` only asks the running copy to quit, and it writes its own settings back
    as it goes - so wait until it is really gone before anyone writes settings.
    Never raises, and gives up after about STOP_SECONDS (a hung copy is ended)."""
    if not os.path.exists(EXE):
        return
    deadline = time.monotonic() + STOP_SECONDS
    try:
        try:
            subprocess.run([EXE, "-exit"], creationflags=HIDDEN, timeout=15)
        except (subprocess.TimeoutExpired, OSError):
            pass                    # a hung copy (seen while Explorer was swamped): ended below
        while _running() and time.monotonic() < deadline:
            time.sleep(0.25)
        if _running():
            # Still there: end it. Its unsaved in-memory settings are lost, which is fine -
            # Apply and Undo write the settings themselves right after this.
            _kill(_pids())
            end = time.monotonic() + 3
            while _running() and time.monotonic() < end:
                time.sleep(0.25)
        time.sleep(1.0)
    except Exception:
        pass                        # never let the Start menu stop Apply or Undo


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
    try:
        openshell_skin.build(accent, tmp)
        with open(tmp, "rb") as f:
            data = f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    for attempt in range(10):
        try:
            with open(SKIN_FILE, "wb") as f:
                f.write(data)
            break
        except OSError:                   # Open-Shell has it open this very moment
            if attempt == 9:
                raise
            time.sleep(0.5)
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
