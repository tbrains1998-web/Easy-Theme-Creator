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


def _doubled(path):
    """Written by 2.1 or older (every line ending in \\r\\r\\n)."""
    with open(path, "rb") as f:
        head = f.read(65536)
    return b"\r\x00\r\x00" in head or b"\r\r" in head


ICON_LINES = ("iconresource=", "iconfile=", "iconindex=")


def _without_ours(lines):
    """The lines without icon settings that point into Easy Theme Creator's own folders
    (an IconIndex goes with its IconFile). Returns (lines, whether any went)."""
    import undo

    def ours(ln, keys):
        return ln.strip().lower().startswith(keys) and undo.is_ours(ln.split("=", 1)[1])
    our_file = any(ours(ln, "iconfile=") for ln in lines)
    out = [ln for ln in lines if not ours(ln, ("iconresource=", "iconfile="))
           and not (our_file and ln.strip().lower().startswith("iconindex="))]
    return out, len(out) != len(lines)


def _nothing_left(lines):
    """Only section names ([.ShellClassInfo]) left: Windows would have no desktop.ini."""
    return all(ln.strip().startswith("[") for ln in lines)


def _write_ini(folder, icon, backup_dir, log, on_backup=None):
    """Point the folder's desktop.ini at `icon`. With backup_dir, the desktop.ini as it is
    now is saved there first - without icons of ours, those never count as "before" -
    and the folder joins the undo log; without, it is in the log already."""
    ini = os.path.join(folder, "desktop.ini")
    lines = []
    if os.path.exists(ini):
        _attrs(ini, 0x80)
        lines = _read_lines(ini)
    if backup_dir is not None:
        saved = None
        before, changed = _without_ours(lines)
        if lines and not _nothing_left(before):
            saved = os.path.join(backup_dir, uuid.uuid4().hex + ".ini")
            if changed or os.path.getsize(ini) >= 65536 or _doubled(ini):
                _put_lines(saved, before)                    # a doubled one: back up its lines
            else:
                shutil.copyfile(ini, saved)
        log.append((folder, saved))
        if on_backup:
            on_backup()                                      # saved before anything changes
    lines = [ln for ln in lines if not ln.strip().lower().startswith(ICON_LINES)]
    if not any(ln.strip().lower() == "[.shellclassinfo]" for ln in lines):
        lines = ["[.ShellClassInfo]"] + lines
    i = next(n for n, ln in enumerate(lines) if ln.strip().lower() == "[.shellclassinfo]")
    lines.insert(i + 1, "IconResource=%s,0" % icon)
    _put_lines(ini, lines)
    _attrs(ini, 0x2 | 0x4)                                   # hidden + system
    attrs = ctypes.windll.kernel32.GetFileAttributesW(folder)
    _attrs(folder, attrs | 0x1)                              # read-only flag makes Explorer read it


def _same(folder):
    return os.path.normcase(os.path.abspath(folder))


def apply(icons, backup_dir, log=None, on_backup=None):
    """Put the icons on the special folders. `log` is the undo log so far [(folder, backup
    or None)]: folders in it keep their first backup; the others are backed up into
    backup_dir and added to it, and on_backup() runs right after each, before that
    folder changes. Returns the log."""
    os.makedirs(backup_dir, exist_ok=True)
    log = [] if log is None else log
    done = {_same(f) for f, _ in log}
    for kind, path in _known().items():
        if os.path.isdir(path) and kind in icons:
            new = _same(path) not in done
            _write_ini(path, icons[kind], backup_dir if new else None, log, on_backup)
    refresh()
    return log


def undo(log):
    """Each folder's desktop.ini back as it was before the first Apply, but never with icon
    settings of ours (a backup made while an older theme of ours was on holds them too):
    when nothing else is left, the folder gets no desktop.ini, as Windows had it. Without
    a backup, today's file only loses our icon (what Windows or the user added stays)."""
    problems = []
    for folder, saved in log:
        if not os.path.isdir(folder):
            continue                                         # the folder itself is gone
        try:
            _undo_folder(folder, saved)
        except OSError as e:
            problems.append("%s (%s)" % (folder, e))
    refresh()
    if problems:
        raise OSError("could not put back " + "; ".join(problems))


def _undo_folder(folder, saved):
    ini = os.path.join(folder, "desktop.ini")
    if os.path.exists(ini):
        _attrs(ini, 0x80)
    src = saved if saved and os.path.exists(saved) else (ini if os.path.exists(ini) else None)
    if src is None:
        return
    lines, changed = _without_ours(_read_lines(src))
    if _nothing_left(lines):
        if os.path.exists(ini):
            os.remove(ini)
        return
    if src != ini and not changed and os.path.getsize(src) < 65536 and not _doubled(src):
        shutil.copyfile(src, ini)
    elif src != ini or changed or _doubled(ini):
        _put_lines(ini, lines)                               # cleaned, or a doubled one from 2.1
    _attrs(ini, 0x2 | 0x4)


def refresh():
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
