"""Icons for Explorer's own places (This PC, Network, Home, Gallery, OneDrive) and
the drives, plus the stable folder all generated icons live in.

Places use per-user overrides in HKCU\\Software\\Classes\\CLSID\\{id}\\DefaultIcon,
drives use HKCU\\Software\\Classes\\Applications\\Explorer.exe\\Drives\\<letter>\\DefaultIcon.
Nothing machine-wide is changed. Icons must stay in one fixed place: Windows reads
them from disk every time, so a theme folder that gets cleaned up later leaves
default icons behind.
"""
import ctypes
import os
import shutil
import string
import time
import winreg

from PIL import Image

import alien_icons

ASSETS = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "EasyThemeCreator", "assets")
SIZES = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)]

PLACES = {
    "pc": "{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "network": "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}",
    "home": "{f874310e-b6b7-47dc-bc84-b9e6b38f5903}",
    "gallery": "{e88865ea-0e1c-4e20-9aa6-edcd0212c87c}",
    "onedrive": "{018D5C66-4533-4307-9B53-224DE2ED1FE6}",
}
# Windows' own user folders ignore the IconResource in their desktop.ini: their icon
# comes from the This PC entry's CLSID (new and older ids), which also covers the
# folder itself in the navigation pane and Home.
USER_FOLDERS = {
    "desktop": ["{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"],
    "documents": ["{d3162b92-9365-467a-956b-92703aca08af}", "{A8CDFF1C-4878-43be-B5FD-F8091C1C60D0}"],
    "downloads": ["{088e3905-0323-4b02-9826-5d99428e115f}", "{374DE290-123F-4565-9164-39C4925E467B}"],
    "music": ["{3dfdf296-dbec-4fb4-81d1-6a3438bcf4de}", "{1CF1260C-4DD0-4ebb-811F-33C572699FDE}"],
    "pictures": ["{24ad3ad4-a569-4530-98e1-ab02f9417aa8}", "{3ADD1653-EB32-4cb0-BBD7-DFA0ABB5ACCA}"],
    "videos": ["{f86fa3ab-70d2-4fc7-9c99-fcbf05467f3a}", "{A0953C92-50DC-43bf-BE83-3742FED03C9C}"],
}
PLACE_KEY = r"Software\Classes\CLSID\%s\DefaultIcon"
# Desktop icon settings' key. When it's set (a .theme file writes it) it wins over
# PLACE_KEY for This PC and Network, so both get the icon.
EXPLORER_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\CLSID\%s\DefaultIcon"
EXPLORER_PLACES = ("pc", "network")
DRIVE_KEY = r"Software\Classes\Applications\Explorer.exe\Drives\%s\DefaultIcon"


def new_assets_dir():
    path = os.path.join(ASSETS, str(int(time.time())))
    os.makedirs(path, exist_ok=True)
    return path


def cleanup(keep):
    """Remove older icon folders, keeping `keep` (the one in use)."""
    if not os.path.isdir(ASSETS):
        return
    for d in os.listdir(ASSETS):
        full = os.path.join(ASSETS, d)
        if os.path.normcase(full) != os.path.normcase(keep):
            shutil.rmtree(full, ignore_errors=True)


def fixed_drives():
    out = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if mask & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(letter + ":\\") == 3:
            out.append(letter)
    return out


def place_exists(guid):
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "CLSID\\" + guid))
        return True
    except OSError:
        return False


def registry_keys():
    """Every per-user key apply() may write (for the undo snapshot)."""
    return (["HKCU\\" + PLACE_KEY % g for g in PLACES.values()] +
            ["HKCU\\" + EXPLORER_KEY % PLACES[k] for k in EXPLORER_PLACES] +
            ["HKCU\\" + PLACE_KEY % g for ids in USER_FOLDERS.values() for g in ids] +
            ["HKCU\\" + DRIVE_KEY % d for d in fixed_drives()])


def make(folder, accent, dark):
    """Draw place and drive icons into `folder`. Returns {kind: path}."""
    painter = alien_icons.Painter(accent, dark, size=512)
    out = {}
    for kind in PLACES:
        path = os.path.join(folder, kind + ".ico")
        painter.icon(kind).resize((256, 256), Image.LANCZOS).save(path, sizes=SIZES)
        out[kind] = path
    path = os.path.join(folder, "drive.ico")
    alien_icons.drive_icon(painter).resize((256, 256), Image.LANCZOS).save(path, sizes=SIZES)
    out["drive"] = path
    return out


def _set_default(path, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_EXPAND_SZ, value)


def apply(icons, folder_icons=None):
    """`icons` from make(); `folder_icons` from folders.make_icons() for the user folders."""
    for kind, guid in PLACES.items():
        if kind in icons and place_exists(guid):
            _set_default(PLACE_KEY % guid, icons[kind] + ",0")
            if kind in EXPLORER_PLACES:
                _set_default(EXPLORER_KEY % guid, icons[kind] + ",0")
    for kind, ids in USER_FOLDERS.items():
        if kind in (folder_icons or {}):
            for guid in ids:
                if place_exists(guid):
                    _set_default(PLACE_KEY % guid, folder_icons[kind] + ",0")
    if "drive" in icons:
        for letter in fixed_drives():
            _set_default(DRIVE_KEY % letter, icons["drive"] + ",0")
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
