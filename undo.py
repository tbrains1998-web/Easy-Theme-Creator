"""Remember how Windows looked before the first Apply, and put it back.

The snapshot is taken once; applying more themes keeps it, so Undo always goes
back to how things were before Easy Theme Creator changed anything.
"""
import json
import os
import shutil
import subprocess
import time

HOME = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "EasyThemeCreator")
SNAP = os.path.join(HOME, "undo")
STATE = os.path.join(SNAP, "state.json")

# Everything windows_apply.py writes lives under these keys.
KEYS = [
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent",
    r"HKCU\Software\Microsoft\Windows\DWM",
    r"HKCU\Control Panel\Cursors",
    r"HKCU\AppEvents\Schemes",
]
ICON_CLSIDS = [
    "{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}",
    "{59031A47-3F72-44A7-89C5-5595FE6B30EE}",
    "{645FF040-5081-101B-9F08-00AA002F954E}",
]
HIDDEN = subprocess.CREATE_NO_WINDOW


def _reg(*args):
    return subprocess.run(["reg", *args], capture_output=True, creationflags=HIDDEN).returncode == 0


def has_snapshot():
    return os.path.exists(STATE)


def load():
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def save(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def take(skin_now, wallpaper_now, sab_backup_fn):
    """Save the current look (only if no snapshot exists yet). Returns the state dict."""
    if has_snapshot():
        return load()
    os.makedirs(SNAP, exist_ok=True)
    state = {"time": time.strftime("%Y-%m-%d %H:%M"), "skin": skin_now,
             "wallpaper": wallpaper_now, "regs": [], "missing": [], "folders": None,
             "startallback": None}
    for i, key in enumerate(KEYS + [r"HKCU\Software\Classes\CLSID\%s\DefaultIcon" % c for c in ICON_CLSIDS]):
        path = os.path.join(SNAP, "reg%02d.reg" % i)
        if _reg("export", key, path, "/y"):
            state["regs"].append(path)
        else:
            state["missing"].append(key)      # didn't exist before: delete it on undo
    if wallpaper_now and os.path.exists(wallpaper_now):
        copy = os.path.join(SNAP, "wallpaper" + os.path.splitext(wallpaper_now)[1])
        shutil.copyfile(wallpaper_now, copy)
        state["wallpaper_copy"] = copy
    state["wallpaper_style"] = wallpaper_style()
    state["startallback"] = sab_backup_fn(os.path.join(SNAP, "startallback.reg"))
    save(state)
    return state


def wallpaper_style():
    """[WallpaperStyle, TileWallpaper] as they are now (Fill, Fit, Center, Tile, Span...);
    Apply always sets Fill. None for a value that isn't there."""
    import winreg
    out = [None, None]
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as k:
            for i, n in enumerate(("WallpaperStyle", "TileWallpaper")):
                try:
                    out[i] = str(winreg.QueryValueEx(k, n)[0])
                except OSError:
                    pass
    except OSError:
        pass
    return out


def forget():
    shutil.rmtree(SNAP, ignore_errors=True)


def restore_registry(state):
    for key in state["missing"]:
        _reg("delete", key, "/f")
    for path in state["regs"]:
        _reg("import", path)


def remember(state, keys):
    """Add registry keys to an existing snapshot before they're first changed.
    Keys the snapshot already covers are left alone (their saved copy is older)."""
    original = KEYS + [r"HKCU\Software\Classes\CLSID\%s\DefaultIcon" % c for c in ICON_CLSIDS]
    seen = {k.lower() for k in state.setdefault("seen_keys", original)}
    keys = [k for k in keys if k.lower() not in seen]
    for key in keys:
        path = os.path.join(SNAP, "reg%02d.reg" % (len(state["regs"]) + len(state["missing"])))
        if _reg("export", key, path, "/y"):
            state["regs"].append(path)
        else:
            state["missing"].append(key)
        seen.add(key.lower())
    state["seen_keys"] = sorted(seen)
    save(state)
