"""Folder icons in the picture's style, and putting them on the user's folders.

Icons are the Alien style (black glossy case, claw emblem, 3D badge per
special folder) drawn in the theme's accent and dark colors. Icons are set through each folder's hidden
desktop.ini, the normal Windows way; the old desktop.ini is backed up for undo.
"""
import ctypes
import os
import shutil
import uuid

from PIL import Image



def _known():
    up = os.environ.get("USERPROFILE", os.path.expanduser("~"))

    def shell(csidl_guid, fallback):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                return os.path.expandvars(winreg.QueryValueEx(k, csidl_guid)[0])
        except OSError:
            return os.path.join(up, fallback)
    return {
        "desktop": shell("Desktop", "Desktop"),
        "documents": shell("Personal", "Documents"),
        "downloads": shell("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
        "music": shell("My Music", "Music"),
        "pictures": shell("My Pictures", "Pictures"),
        "videos": shell("My Video", "Videos"),
        "favorites": os.path.join(up, "Favorites"),
        "saved-games": os.path.join(up, "Saved Games"),
        "contacts": os.path.join(up, "Contacts"),
        "links": os.path.join(up, "Links"),
        "searches": os.path.join(up, "Searches"),
    }


# ------------------------------------------------------------------ drawing

def make_icons(folder, accent, dark):
    """Write folder.ico and one Alien-style icon per special folder, in the theme's
    colors (the picture itself is never pasted in). Returns {kind: path}."""
    import alien_icons
    os.makedirs(folder, exist_ok=True)
    painter = alien_icons.Painter(accent, dark, size=512)
    out = {}
    for kind in ["folder"] + list(_known()):
        path = os.path.join(folder, kind + ".ico")
        painter.icon(kind).resize((256, 256), Image.LANCZOS).save(
            path, sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)])
        out[kind] = path
    return out


# ------------------------------------------------------------------ applying

def _attrs(path, value):
    ctypes.windll.kernel32.SetFileAttributesW(path, value)


def _read_lines(path):
    """The non-blank lines of a desktop.ini. Up to 2.1 every Apply doubled the file
    (text-mode writing turned each \\r\\n into \\r\\r\\n, read back as an extra blank
    line), up to gigabytes that kept Explorer busy for good: those are read in pieces."""
    with open(path, "rb") as f:
        head = f.read(2)
        if head not in (b"\xff\xfe", b"\xfe\xff"):
            text = (head + f.read()).decode("mbcs", "replace")
            return [ln for ln in text.splitlines() if ln.strip()]
        enc = "utf-16-le" if head == b"\xff\xfe" else "utf-16-be"
        lines, carry = [], ""
        while True:
            chunk = f.read(16 << 20)                         # even size: whole UTF-16 units
            if not chunk:
                break
            parts = (carry + chunk.decode(enc, "replace")).replace("\r", "\n").split("\n")
            carry = parts.pop()
            lines += [p for p in parts if p.strip()]
        return lines + ([carry] if carry.strip() else [])


def _put_lines(path, lines):
    with open(path, "w", encoding="utf-16", newline="") as f:   # newline="": no \r\r\n
        f.write("\r\n".join(lines) + "\r\n")


def _write_ini(folder, icon, backup_dir, log):
    ini = os.path.join(folder, "desktop.ini")
    saved = None
    lines = []
    if os.path.exists(ini):
        _attrs(ini, 0x80)
        lines = _read_lines(ini)
        saved = os.path.join(backup_dir, uuid.uuid4().hex + ".ini")
        if os.path.getsize(ini) < 65536:
            shutil.copyfile(ini, saved)
        else:
            _put_lines(saved, lines)                         # a doubled one: back up its lines
        lines = [ln for ln in lines
                 if not ln.strip().lower().startswith(("iconresource=", "iconfile=", "iconindex="))]
    log.append((folder, saved))
    if not any(ln.strip().lower() == "[.shellclassinfo]" for ln in lines):
        lines = ["[.ShellClassInfo]"] + lines
    i = next(n for n, ln in enumerate(lines) if ln.strip().lower() == "[.shellclassinfo]")
    lines.insert(i + 1, "IconResource=%s,0" % icon)
    _put_lines(ini, lines)
    _attrs(ini, 0x2 | 0x4)                                   # hidden + system
    attrs = ctypes.windll.kernel32.GetFileAttributesW(folder)
    _attrs(folder, attrs | 0x1)                              # read-only flag makes Explorer read it


def apply(icons, backup_dir):
    """Put the icons on the special folders. Returns the undo log [(folder, backup or None)]."""
    os.makedirs(backup_dir, exist_ok=True)
    log = []
    for kind, path in _known().items():
        if os.path.isdir(path) and kind in icons:
            _write_ini(path, icons[kind], backup_dir, log)
    refresh()
    return log


def undo(log):
    for folder, saved in log:
        ini = os.path.join(folder, "desktop.ini")
        if os.path.exists(ini):
            _attrs(ini, 0x80)
        if saved and os.path.exists(saved):
            if os.path.getsize(saved) < 65536:
                shutil.copyfile(saved, ini)
            else:
                _put_lines(ini, _read_lines(saved))         # a doubled backup from 2.1 or older
            _attrs(ini, 0x2 | 0x4)
        elif os.path.exists(ini):
            os.remove(ini)
    refresh()


def refresh():
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
