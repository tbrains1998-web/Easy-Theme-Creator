"""Metal taskbar, Alien Start button and armor Explorer bars on Windows 11's own
taskbar and File Explorer, through two free Windhawk mods (by m417z, GPL-3.0):

  windows-11-taskbar-styler        taskbar background + Start button picture
  windows-11-file-explorer-styler  address row + command bar plates, red buttons

Both read their settings from Windhawk's registry when Explorer starts. The
pictures are drawn in the accent color into %ProgramData%\\EasyThemeCreator\\xaml
and the settings point at them. Windhawk keeps settings under HKLM; a one-time
admin step (the installer, or setup_access() here) lets normal users write just
these two mods' "Settings" keys, so Apply never needs an admin prompt.
"""
import ctypes
import glob
import os
import subprocess
import time
import winreg

import armor
import skin

FOLDER = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "EasyThemeCreator", "xaml")
TASKBAR_MOD = "windows-11-taskbar-styler"
EXPLORER_MOD = "windows-11-file-explorer-styler"
MODS_KEY = r"SOFTWARE\Windhawk\Engine\Mods"
MARK = "// Easy Theme Creator"           # first style constant: tells our settings apart

START = ("Taskbar.ExperienceToggleButton#LaunchListButton"
         "[AutomationProperties.AutomationId=StartButton] > Taskbar.TaskListButtonPanel")


def mod_installed(mod):
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MODS_KEY + "\\" + mod))
        return True
    except OSError:
        return False


def writable(mod):
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MODS_KEY + "\\" + mod + "\\Settings",
                                       0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE))
        return True
    except OSError:
        return False


def status(mod):
    """'ready' or the reason it can't be used yet."""
    import cpl_panes
    if not cpl_panes.windhawk_installed():
        return "Windhawk isn't installed"
    if not mod_installed(mod):
        name = "Windows 11 Taskbar Styler" if mod == TASKBAR_MOD else "Windows 11 File Explorer Styler"
        return 'install the "%s" mod in Windhawk' % name
    if not writable(mod):
        return "needs a one-time OK from an administrator"
    return "ready"


# Windhawk stores these keys with a permission list Windows calls "not canonical", so
# the usual AddAccessRule refuses it; adding the entry to the SDDL text works.
GRANT_PS = r"""
Start-Transcript (Join-Path $env:TEMP 'etc-windhawk-access.log') -Force | Out-Null
foreach ($k in $args) {
    if (-not (Test-Path $k)) { New-Item $k -Force | Out-Null }
    $a = Get-Acl $k
    if ($a.Sddl -notmatch '\(A;;(0x2001b|CCDCSWRPRC);;;BU\)') {     # Windows rewrites the mask
        $a.SetSecurityDescriptorSddlForm(($a.Sddl -replace '(D:[A-Z]*)', '$1(A;;0x2001b;;;BU)'))
        Set-Acl $k $a
    }
    "$k -> " + ((Get-Acl $k).Sddl -match '(0x2001b|CCDCSWRPRC);;;BU')
}
Stop-Transcript | Out-Null
"""


class _SEI(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("fMask", ctypes.c_ulong), ("hwnd", ctypes.c_void_p),
                ("lpVerb", ctypes.c_wchar_p), ("lpFile", ctypes.c_wchar_p),
                ("lpParameters", ctypes.c_wchar_p), ("lpDirectory", ctypes.c_wchar_p),
                ("nShow", ctypes.c_int), ("hInstApp", ctypes.c_void_p), ("lpIDList", ctypes.c_void_p),
                ("lpClass", ctypes.c_wchar_p), ("hkeyClass", ctypes.c_void_p),
                ("dwHotKey", ctypes.c_ulong), ("hIcon", ctypes.c_void_p), ("hProcess", ctypes.c_void_p)]


OUR_MODS = (TASKBAR_MOD, EXPLORER_MOD, "easy-theme-creator-standard-colors")


def setup_access(hwnd=None):
    """Once, with an admin prompt: let users write our mods' settings (only their
    "Settings" keys: set and read values). `hwnd` keeps the prompt in front."""
    mods = [m for m in OUR_MODS if mod_installed(m) and not writable(m)]
    if not mods:
        return
    script = os.path.join(os.environ.get("TEMP", FOLDER), "etc-windhawk-access.ps1")
    with open(script, "w", encoding="utf-8") as f:
        f.write(GRANT_PS)
    keys = " ".join('"HKLM:\\%s\\%s\\Settings"' % (MODS_KEY, m) for m in mods)   # -File keeps ' quotes
    sei = _SEI(cbSize=ctypes.sizeof(_SEI), fMask=0x40, hwnd=hwnd, lpVerb="runas",   # NOCLOSEPROCESS
               lpFile="powershell.exe", nShow=0,
               lpParameters='-NoProfile -ExecutionPolicy Bypass -File "%s" %s' % (script, keys))
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
        raise OSError("The administrator prompt was cancelled.")
    k32 = ctypes.windll.kernel32
    k32.WaitForSingleObject(ctypes.c_void_p(sei.hProcess), 120000)
    k32.CloseHandle(ctypes.c_void_p(sei.hProcess))
    if not all(writable(m) for m in mods):
        raise OSError("Windhawk's settings still can't be changed.")


# ------------------------------------------------------------------ pictures

def _uri(path):
    return "file:///" + path.replace("\\", "/")


def _brush(path, stretch="Fill"):
    return '<ImageBrush Stretch="%s" ImageSource="%s" />' % (stretch, _uri(path))


def _screen_width():
    """Widest single monitor in real pixels: every monitor's taskbar stretches the
    same picture to its own width."""
    import ctypes.wintypes as wt
    u = ctypes.WinDLL("user32")                  # own copy: the restype below stays here
    old = None
    try:
        u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        old = u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))   # real pixels, not scaled
    except Exception:
        pass
    widths = []
    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

    def cb(hmon, hdc, rect, lp):
        widths.append(rect.contents.right - rect.contents.left)
        return True
    try:
        u.EnumDisplayMonitors(None, None, proc(cb), 0)
    finally:
        if old:                                  # the rest of Apply runs on this thread too
            u.SetThreadDpiAwarenessContext(ctypes.c_void_p(old))
    return max(widths + [1920])


def make_pictures(accent):
    """Draw the plates and the Start orb. Fresh file names each time, so Explorer
    never shows a cached old picture. Returns {name: path}."""
    import taskbar
    os.makedirs(FOLDER, exist_ok=True)
    k = skin.dpi_scale()
    stamp = int(time.time())
    W = _screen_width()
    pics = {
        "taskbar": armor.full_plate(min(W, 7680), int(48 * k), accent, k, line="top", rivets=False),
        "nav": armor.full_plate(2400, int(52 * k), accent, k, line="bottom", rivets=False, seed=21),
        "cmd": armor.full_plate(2400, int(48 * k), accent, k, line="bottom", rivets=False, seed=22),
    }
    orb = taskbar.orb_image(accent)                             # 3 states stacked: normal, hover, pressed
    for i, st in enumerate(("start", "start_hover", "start_pressed")):
        pics[st] = orb.crop((0, i * orb.width, orb.width, (i + 1) * orb.width))
    for st in ("running", "hover", "active", "pressed", "attention"):   # Windows 7-style task buttons
        pics["task_" + st] = armor.task_tile(st, accent, k)
    for st in ("normal", "hover", "pressed"):
        pics["desk_" + st] = armor.desktop_strip(st, accent, k)
    paths = {}
    for name, img in pics.items():
        paths[name] = os.path.join(FOLDER, "%s-%d.png" % (name, stamp))
        img.save(paths[name])
    for old in glob.glob(os.path.join(FOLDER, "*.png")):
        if old not in paths.values():
            try:
                os.remove(old)
            except OSError:
                pass
    return paths


# ------------------------------------------------------------------ settings

# Windows 7-style taskbar, built on the layout of the Taskbar Styler's own "Windows7"
# theme (by Sand216) but with our own local pictures, drawn at the display scaling.
TASK_BG = ("Grid#IconPanel@CommonStates > Windows.UI.Xaml.Controls.Border#BackgroundElement, "
           "Taskbar.TaskListLabeledButtonPanel@CommonStates > Windows.UI.Xaml.Controls.Border#BackgroundElement")
TASK_MULTI = ("Grid#IconPanel@CommonStates > Windows.UI.Xaml.Controls.Border#MultiWindowElement, "
              "Taskbar.TaskListLabeledButtonPanel@CommonStates > Windows.UI.Xaml.Controls.Border#MultiWindowElement")
TASK_RUN = ("Grid#IconPanel@RunningIndicatorStates > Windows.UI.Xaml.Controls.Border#BackgroundElement, "
            "Taskbar.TaskListLabeledButtonPanel@RunningIndicatorStates > Windows.UI.Xaml.Controls.Border#BackgroundElement")
DESKTOP = "Windows.UI.Xaml.Controls.Grid#ContainerGrid@ > Windows.UI.Xaml.Shapes.Rectangle#ShowDesktopPipe"
DESK_STACK = "SystemTray.Stack#ShowDesktopStack"


def taskbar_settings(pics, metal=True, orb=True):
    styles = []
    if metal:
        def b(name):
            return _brush(pics[name])
        task = {"InactiveNormal": "task_running", "InactivePointerOver": "task_hover",
                "InactivePressed": "task_pressed", "ActiveNormal": "task_active",
                "ActivePointerOver": "task_active", "ActivePressed": "task_pressed",
                "MultiWindowNormal": "task_running", "MultiWindowActive": "task_active",
                "MultiWindowPointerOver": "task_hover", "MultiWindowPressed": "task_pressed",
                "RequestingAttention": "task_attention", "RequestingAttentionPointerOver": "task_attention",
                "RequestingAttentionPressed": "task_attention", "RequestingAttentionMulti": "task_attention",
                "RequestingAttentionMultiPointerOver": "task_attention",
                "RequestingAttentionMultiPressed": "task_attention"}
        styles += [
            ("Taskbar.TaskbarFrame > Grid#RootGrid > Taskbar.TaskbarBackground > Grid > Rectangle#BackgroundFill",
             ["Fill:=" + b("taskbar")]),
            ("Taskbar.TaskbarFrame > Grid#RootGrid > Taskbar.TaskbarBackground > Grid > Rectangle#BackgroundStroke",
             ["Visibility=Collapsed"]),
            (TASK_BG, ["Background@%s:=%s" % (st, b(img)) for st, img in task.items()] + ["BorderThickness=0"]),
            (TASK_MULTI, ["Background@%s:=%s" % (st, b(img)) for st, img in task.items()
                          if st.startswith(("MultiWindow", "RequestingAttentionMulti"))] + ["BorderThickness=0"]),
            (TASK_RUN, ["Opacity@NoRunningIndicator=0"]),          # pinned, not running: no tile
            ("Windows.UI.Xaml.Shapes.Rectangle#RunningIndicator", ["Visibility=Collapsed"]),
            ("Taskbar.TaskListButton", ["Margin=1,0,1,0"]),
            (DESKTOP, ["Fill@Normal:=" + b("desk_normal"), "Fill@PointerOver:=" + b("desk_hover"),
                       "Fill@Pressed:=" + b("desk_pressed"), "Width=15", "RadiusX=0", "RadiusY=0"]),
            (DESK_STACK, ["Width=15"]),
        ]
    if orb:
        orb_bg = START.replace("TaskListButtonPanel", "TaskListButtonPanel@CommonStates")
        o = {"InactiveNormal": "start", "InactivePointerOver": "start_hover", "InactivePressed": "start_pressed",
             "ActiveNormal": "start_pressed", "ActivePointerOver": "start_hover", "ActivePressed": "start_pressed"}
        styles += [(orb_bg + " > Grid > Border#BackgroundElement, " + orb_bg + " > Border#BackgroundElement",
                    ["Background@%s:=%s" % (st, _brush(pics[img], "Uniform")) for st, img in o.items()] +
                    ["BorderThickness=0"]),
                   (START + " > Grid > Microsoft.UI.Xaml.Controls.AnimatedVisualPlayer#Icon, " +
                    START + " > Microsoft.UI.Xaml.Controls.AnimatedVisualPlayer#Icon",
                    ["Visibility=Collapsed"]),
                   ("Taskbar.TaskListButtonPanel#ExperienceToggleButtonRootPanel",
                    ["Padding=0,0,0,0", "Margin=0,0,4,0"])]
    return styles


ADVANCED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"


def left_align():
    """Taskbar icons on the left, like Windows 7. Returns the old value for undo."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ADVANCED) as k:
        try:
            old = winreg.QueryValueEx(k, "TaskbarAl")[0]
        except OSError:
            old = None
        winreg.SetValueEx(k, "TaskbarAl", 0, winreg.REG_DWORD, 0)
    return old


def restore_align(old):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ADVANCED) as k:
        if old is None:
            try:
                winreg.DeleteValue(k, "TaskbarAl")
            except OSError:
                pass
        else:
            winreg.SetValueEx(k, "TaskbarAl", 0, winreg.REG_DWORD, old)


def explorer_settings(pics):
    accent = '<SolidColorBrush Color="{ThemeResource SystemAccentColorLight1}" />'
    return [("Grid#NavigationBarControlGrid", ["Background:=" + _brush(pics["nav"])]),
            ("FileExplorerExtensions.CommandBarControl_Wave1 > Grid, Grid#CommandBarControlRootGrid",
             ["Background:=" + _brush(pics["cmd"])]),
            ("CommandBar#FileExplorerCommandBar", ["Background=Transparent"]),
            ("AppBarButton", ["Foreground:=" + accent]),
            ("AppBarToggleButton", ["Foreground:=" + accent])]


def _write(mod, styles):
    """Replace the mod's settings with ours (or with nothing, for undo). A user's own
    styles there are kept for Undo by settings_snapshot(), taken before the first Apply."""
    path = MODS_KEY + "\\" + mod + "\\Settings"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                        winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
        names = []
        i = 0
        while True:
            try:
                names.append(winreg.EnumValue(k, i)[0])
            except OSError:
                break
            i += 1
        for n in names:
            if n.startswith(("controlStyles[", "styleConstants[", "themeResourceVariables[")):
                winreg.DeleteValue(k, n)
        winreg.SetValueEx(k, "theme", 0, winreg.REG_SZ, "")
        winreg.SetValueEx(k, "styleConstants[0]", 0, winreg.REG_SZ, MARK if styles else "")
        winreg.SetValueEx(k, "themeResourceVariables[0]", 0, winreg.REG_SZ, "")
        for i, (target, lines) in enumerate(styles or [("", [""])]):
            winreg.SetValueEx(k, "controlStyles[%d].target" % i, 0, winreg.REG_SZ, target)
            for j, line in enumerate(lines):
                winreg.SetValueEx(k, "controlStyles[%d].styles[%d]" % (i, j), 0, winreg.REG_SZ, line)


def apply(accent, metal=True, orb=True, explorer=True):
    """Use the pictures on the taskbar / Start button / Explorer. Takes effect when
    Explorer restarts. Returns [(part, problem)] for parts that couldn't be set."""
    problems = []
    pics = make_pictures(accent)
    for mod, wanted, styles in ((TASKBAR_MOD, metal or orb, lambda: taskbar_settings(pics, metal, orb)),
                                (EXPLORER_MOD, explorer, lambda: explorer_settings(pics))):
        if not wanted:
            # Switched off: take back only our own styles; styles the user made stay.
            if ours(mod) and writable(mod):
                _write(mod, [])
            continue
        why = status(mod)
        if why != "ready":
            problems.append(("Taskbar" if mod == TASKBAR_MOD else "Armor Explorer", why))
            continue
        _write(mod, styles())
    return problems


def ours(mod):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MODS_KEY + "\\" + mod + "\\Settings") as k:
            return winreg.QueryValueEx(k, "styleConstants[0]")[0] == MARK
    except OSError:
        return False


# ------------------------------------------------------------------ the user's own styles

STYLER_MODS = (TASKBAR_MOD, EXPLORER_MOD)
_STYLE_VALUES = ("theme", "controlStyles[", "styleConstants[", "themeResourceVariables[")


def _values(k):
    out, i = [], 0
    while True:
        try:
            out.append(winreg.EnumValue(k, i))          # (name, data, type)
        except OSError:
            return out
        i += 1


def _cleared(mod):
    """True when the mod holds no styles at all (what _write(mod, []) leaves)."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MODS_KEY + "\\" + mod + "\\Settings") as k:
            return all(data in ("", None) for name, data, _ in _values(k) if name.startswith(_STYLE_VALUES))
    except OSError:
        return False


def settings_snapshot():
    """The user's own settings of the styler mods, for Undo: {mod: [[name, type, data], ...]}
    with every value of the mod's Settings key (binary data as {"hex": ...}, so it can go
    in the JSON undo state). Mods that already hold our styles, or aren't installed, are
    left out - so take it once, before the first Apply changes anything."""
    out = {}
    for mod in STYLER_MODS:
        if not mod_installed(mod) or ours(mod):
            continue
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MODS_KEY + "\\" + mod + "\\Settings") as k:
                values = _values(k)
        except OSError:
            values = []                                  # no settings yet: Undo leaves none
        out[mod] = [[name, kind, {"hex": data.hex()} if isinstance(data, bytes) else data]
                    for name, data, kind in values]
    return out


def restore_settings(snapshot):
    """Undo: write back the settings settings_snapshot() saved, exactly (values we added
    are removed). Only where our styles - or the empty settings we leave when switched
    off - are still there, so styles the user made in Windhawk since then are kept."""
    failed = []
    for mod, values in (snapshot or {}).items():
        if mod not in STYLER_MODS or not (ours(mod) or _cleared(mod)) or not writable(mod):
            continue
        path = MODS_KEY + "\\" + mod + "\\Settings"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
                saved = {name for name, _, _ in values}
                for name, _, _ in _values(k):
                    if name not in saved:
                        winreg.DeleteValue(k, name)
                for name, kind, data in values:
                    if isinstance(data, dict):
                        data = bytes.fromhex(data.get("hex", ""))
                    winreg.SetValueEx(k, name, 0, kind, data)
        except (OSError, TypeError, ValueError) as e:     # one mod failing doesn't stop the other
            failed.append("%s (%s)" % (mod, e))
    if failed:
        raise OSError("Windhawk styles not put back: " + ", ".join(failed))


def remove():
    """Undo: clear our styles so the taskbar and Explorer look like stock again."""
    for mod in (TASKBAR_MOD, EXPLORER_MOD):
        if ours(mod) and writable(mod):
            _write(mod, [])
