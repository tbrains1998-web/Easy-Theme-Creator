"""Remember how Windows looked before the first Apply, and put it back.

The snapshot is taken once; applying more themes keeps it, so Undo always goes
back to how things were before Easy Theme Creator changed anything.

What Easy Theme Creator made itself never counts as "before" (see is_ours()): a
snapshot taken while an older theme of ours was still on would otherwise bring that
theme back, pointing at files that are long gone. Such values are left out when the
snapshot is taken and again when it is put back, and Windows' own come back instead.
"""
import json
import os
import re
import shutil
import subprocess
import time
import winreg

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
FIRST_KEYS = KEYS + [r"HKCU\Software\Classes\CLSID\%s\DefaultIcon" % c for c in ICON_CLSIDS]   # take()'s
# Desktop icon settings' own keys, which win over the Classes ones once they exist: Desktop
# icons writes them for This PC, Network and the user's files (Apply remember()s them).
EXPLORER_ICON_KEYS = [r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\CLSID\%s\DefaultIcon" % c
                      for c in ICON_CLSIDS]
ICON_KEYS = FIRST_KEYS[len(KEYS):] + EXPLORER_ICON_KEYS
HIDDEN = subprocess.CREATE_NO_WINDOW


def _reg(*args):
    try:
        return subprocess.run(["reg", *args], capture_output=True, creationflags=HIDDEN,
                              timeout=120).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def has_snapshot():
    return os.path.exists(STATE)


def load():
    with open(STATE, encoding="utf-8") as f:
        return _clean_state(json.load(f))


def save(state):
    """Written to a new file that then replaces the old one in one step, so a crash (or a
    PC switched off) while saving never leaves a half snapshot Undo can't read."""
    os.makedirs(SNAP, exist_ok=True)
    tmp = STATE + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)


def drop_leftovers():
    """Up to 2.3 every Apply after the first backed up all folder settings again into
    undo\\folders-later, which nothing ever read (gigabytes with the doubled desktop.ini
    files): gone at the next start."""
    shutil.rmtree(os.path.join(SNAP, "folders-later"), ignore_errors=True)


def take(skin_now, wallpaper_now, sab_backup_fn):
    """Save the current look (only if no snapshot exists yet). Returns the state dict.
    Parts that are already ours (an older theme still on) are saved as Windows' own."""
    if has_snapshot():
        return load()
    os.makedirs(SNAP, exist_ok=True)
    state = _clean_state({"time": time.strftime("%Y-%m-%d %H:%M"), "skin": skin_now,
                          "wallpaper": wallpaper_now, "regs": [], "missing": [], "folders": None,
                          "startallback": None})
    for i, key in enumerate(FIRST_KEYS):
        path = os.path.join(SNAP, "reg%02d.reg" % i)
        if _reg("export", key, path, "/y") and _guard_export(path):
            state["regs"].append(path)
        else:
            state["missing"].append(key)      # didn't exist before (or was all ours): delete it on undo
    wp = state["wallpaper"]
    if wp and wp == wallpaper_now and os.path.exists(wp):      # the user's own picture
        copy = os.path.join(SNAP, "wallpaper" + os.path.splitext(wp)[1])
        shutil.copyfile(wp, copy)
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
    """Put the saved keys back, without anything of ours in them (see _clean). Returns
    [(part, problem)] for whatever Windows would not take back."""
    problems = []
    for key in state["missing"]:
        if _norm(key) == COLORS:              # never deleted: Windows' own colours instead
            import windows_apply
            windows_apply.default_syscolors()
        elif not _delete_key(key):
            problems.append(("Registry", "could not remove " + key))
    for path in state["regs"]:
        why = _restore_file(path)
        if why:
            problems.append(("Registry", why))
    return problems


def restore_colors(state):
    """Classic colours (Control Panel\\Colors) back as the snapshot has them - Windows' own
    when it holds our dark palette or never saved them - and shown at once. Returns
    [(part, problem)]."""
    import windows_apply
    problems = []
    path = next((p for p in state.get("regs", []) if _first_key(p) == COLORS), None)
    if path:
        why = _restore_file(path)
        if why:
            problems.append(("Classic apps", why))
    if not path or windows_apply.our_palette_live():
        windows_apply.default_syscolors()
    windows_apply.reload_syscolors()
    return problems


def remember(state, keys):
    """Add registry keys to an existing snapshot before they're first changed.
    Keys the snapshot already covers are left alone (their saved copy is older)."""
    seen = {k.lower() for k in state.setdefault("seen_keys", FIRST_KEYS)}
    for key in keys:
        if key.lower() in seen:
            continue
        path = os.path.join(SNAP, "reg%02d.reg" % (len(state["regs"]) + len(state["missing"])))
        if _reg("export", key, path, "/y") and _guard_export(path):
            state["regs"].append(path)
        else:
            state["missing"].append(key)
        seen.add(key.lower())
    state["seen_keys"] = sorted(seen)
    save(state)


def heal_live(keys):
    """Our icons out of these per-user ...\\DefaultIcon keys as they are now, whatever the
    snapshot holds (older snapshots don't cover every key Apply writes), so Windows' own
    icon shows again. A key left empty is deleted."""
    for key in keys:
        if not _norm(key).endswith("\\defaulticon"):
            continue
        root, sub = _root(key)
        try:
            k = winreg.OpenKey(root, sub, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            continue
        with k:
            values = _values(k)
            ours = [n for n, data, _ in values if isinstance(data, str) and is_ours(data)]
            for n in ours:
                winreg.DeleteValue(k, n)
            empty = len(ours) == len(values) and not winreg.QueryInfoKey(k)[0]
        if ours and empty:
            winreg.DeleteKey(root, sub)


# ------------------------------------------------------------------ what is ours

# A theme's pictures, sounds and pointers: ...\Microsoft\Windows\Themes\<name>\parts-<n>\.
_PARTS = re.compile(r"\\microsoft\\windows\\themes\\[^\\]+\\parts-\d", re.I)
THEME_MARK = "made with easy theme creator"    # theme_core.HEADER (Windows' Custom.theme copies it)


def _our_folders():
    """%ProgramData%\\EasyThemeCreator (skins = skin.SKINS, icons, Explorer pictures,
    redirect files), in lower case with a closing backslash."""
    out = {os.path.join(os.environ.get("ProgramData") or r"C:\ProgramData", "EasyThemeCreator"),
           r"C:\ProgramData\EasyThemeCreator"}
    try:
        import skin
        out.add(skin.SKINS)
    except Exception:
        pass
    return [os.path.normcase(p).rstrip("\\") + "\\" for p in out]


def is_ours(value):
    """True when `value` - a path, "path,index", or text holding one - points into what
    Easy Theme Creator made: anything under %ProgramData%\\EasyThemeCreator (skin.SKINS
    included) or a theme's parts-* folder under %LOCALAPPDATA%\\Microsoft\\Windows\\Themes."""
    if not isinstance(value, str) or not value.strip():
        return False
    v = os.path.normcase(os.path.expandvars(value.strip().strip('"')))
    return any(f in v for f in _our_folders()) or bool(_PARTS.search(v))


def theme_is_ours(path):
    """True for a .theme file of ours, or one pointing at our skin, pictures or sounds
    (Windows writes its Custom.theme from the theme in use). Settings would put such a
    theme back while it is Windows' "current theme"."""
    if not path:
        return False
    if is_ours(path):
        return True
    try:
        with open(os.path.expandvars(path), "rb") as f:
            data = f.read(1 << 20)
    except OSError:
        return False
    text = data.decode("utf-16", "replace") if data[:2] in (b"\xff\xfe", b"\xfe\xff") \
        else data.decode("mbcs", "replace")
    return THEME_MARK in text[:200].lower() or \
        any(is_ours(ln.split("=", 1)[1]) for ln in text.splitlines() if "=" in ln)


def clean_openshell(before):
    """Open-Shell's settings as saved before, without our own Start menu skin: one saved
    while it was on would select it again (Open-Shell takes its default skin instead)."""
    try:
        import openshell_skin
        name = openshell_skin.NAME
    except Exception:
        name = "Easy Theme Armor"
    skin_w7 = (before or {}).get("SkinW7")
    if skin_w7 and str(skin_w7[0]).strip().lower() == name.lower():
        before = dict(before, SkinW7=None, SkinVariationW7=None, SkinOptionsW7=None)
    return before


def _clean_state(state):
    """The snapshot's own values (skin, wallpaper, Windows' current theme, Start menu skin)
    without anything of ours; registry keys and folders are cleaned as they are saved and
    put back. Returns `state`."""
    import skin
    import windows_apply
    # Taken while a theme of ours was on? Then the taskbar alignment and Start menu style
    # it saved are ours too (they can't be told apart from a user's own), so Undo gives
    # Windows' defaults for them. Remembered, as the signs are cleaned away below.
    try:
        import openshell_skin
        our_menu = openshell_skin.NAME.lower()
    except Exception:
        our_menu = "easy theme armor"
    skin_w7 = (state.get("openshell_before") or {}).get("SkinW7")
    if is_ours(state.get("skin")) or is_ours(state.get("wallpaper")) or \
            theme_is_ours(state.get("current_theme_before")) or \
            (skin_w7 and str(skin_w7[0]).strip().lower() == our_menu):
        state["themed_snapshot"] = True
    if state.get("themed_snapshot"):
        if "taskbar_align_before" in state:
            state["taskbar_align_before"] = None        # centred, as Windows comes
        if state.get("openshell_before"):
            state["openshell_before"] = {n: None for n in state["openshell_before"]}   # Open-Shell's own
    if not state.get("skin") or is_ours(state["skin"]):
        if state.get("skin"):                  # ours, maybe still on: Apply may delete it later
            state["stale_skin"] = state["skin"]   # (skin.cleanup's `previous`), Undo never uses it
        state["skin"] = skin.STOCK_STYLE
    if is_ours(state.get("wallpaper")):
        state["wallpaper"] = windows_apply.stock_wallpaper()
        state.pop("wallpaper_copy", None)
    if theme_is_ours(state.get("current_theme_before")):
        state["current_theme_before"] = None            # Undo picks Windows' own theme
    if state.get("openshell_before"):
        state["openshell_before"] = clean_openshell(state["openshell_before"])
    return state


# ------------------------------------------------------------------ saved registry keys

CURSORS = r"hkey_current_user\control panel\cursors"
COLORS = r"hkey_current_user\control panel\colors"
SOUNDS = r"hkey_current_user\appevents\schemes"
# Control Panel\Cursors value names, in the order Windows' pointer schemes list their files.
CURSOR_ORDER = ("Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No", "SizeNS",
                "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person")
_SHORT = {"hkcu": "hkey_current_user", "hklm": "hkey_local_machine", "hku": "hkey_users",
          "hkcr": "hkey_classes_root"}
_HIVES = {"hkey_current_user": winreg.HKEY_CURRENT_USER, "hkey_local_machine": winreg.HKEY_LOCAL_MACHINE,
          "hkey_users": winreg.HKEY_USERS, "hkey_classes_root": winreg.HKEY_CLASSES_ROOT}


def _norm(key):
    """A key path in lower case with the long root name (HKCU\\... -> hkey_current_user\\...)."""
    head, _, rest = key.strip().lower().partition("\\")
    return _SHORT.get(head, head) + ("\\" + rest if rest else "")


def _root(key):
    """(winreg root, sub key) of a key path."""
    head, _, rest = key.strip().partition("\\")
    hive = _HIVES.get(_SHORT.get(head.lower(), head.lower()))
    if hive is None:
        raise OSError("unknown registry root in " + key)
    return hive, rest


def _values(k):
    out, i = [], 0
    while True:
        try:
            out.append(winreg.EnumValue(k, i))          # (name, data, type)
        except OSError:
            return out
        i += 1


def _exists(key):
    try:
        winreg.CloseKey(winreg.OpenKey(*_root(key)))
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return True                                   # there, but can't be opened


def _delete_key(key):
    """Delete a key and everything under it. True when it is gone (or never was there)."""
    _reg("delete", key, "/f")
    return not _exists(key)


def _delete_value(key, name):
    root, sub = _root(key)
    try:
        with winreg.OpenKey(root, sub, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
    except FileNotFoundError:
        pass                                          # already gone


def _read_reg(path):
    """A .reg file (as `reg export` writes it) as [{"key", "delete", "values"}]: "delete"
    for a [-key], "values" a list of [name, data] - name "" is the default value (@), data
    the text after "=" with continuation lines joined ("-" = delete that value).
    Raises ValueError for anything it doesn't understand."""
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("mbcs")
    model, section, pending = [], None, ""
    for line in text.splitlines():
        s = (pending + line.strip()) if pending else line.strip()
        pending = ""
        if s.endswith("\\") and not s.startswith("["):        # hex data goes on
            pending = s[:-1]
            continue
        if s.startswith("[") and s.endswith("]"):
            name = s[1:-1]
            section = {"key": name.lstrip("-"), "delete": name.startswith("-"), "values": []}
            model.append(section)
        elif section is not None and (s.startswith("@=") or s.startswith('"')):
            section["values"].append(list(_split_value(s)))
        elif s and not s.startswith(";") and not s.lower().startswith(("windows registry editor", "regedit")):
            raise ValueError("unexpected line in %s: %r" % (os.path.basename(path), s[:40]))
    if pending:
        raise ValueError("%s ends in the middle of a value" % os.path.basename(path))
    return model


def _split_value(s):
    if s.startswith("@="):
        return "", s[2:]
    i, name = 1, []
    while i < len(s) and s[i] != '"':
        if s[i] == "\\" and i + 1 < len(s):
            i += 1
        name.append(s[i])
        i += 1
    if s[i + 1:i + 2] != "=":
        raise ValueError("unreadable value line %r" % s[:40])
    return "".join(name), s[i + 2:]


def _text_of(data):
    """The text of a string value (REG_SZ "...", or REG_EXPAND_SZ / MULTI_SZ in hex), else None."""
    if len(data) >= 2 and data[0] == data[-1] == '"':
        return re.sub(r"\\(.)", r"\1", data[1:-1])
    m = re.match(r"hex\((1|2|7)\):(.*)$", data, re.I)
    if not m:
        return None
    try:
        b = bytes(int(x, 16) for x in m.group(2).replace(" ", "").split(",") if x)
    except ValueError:
        return None
    return b.decode("utf-16-le", "replace").replace("\0", "\n").strip("\n")


def _sz(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def _expand_sz(text):
    return "hex(2):" + ",".join("%02x" % b for b in (text + "\0").encode("utf-16-le"))


def _value_line(name, data):
    """One value as reg.exe writes it (long hex data wrapped over lines ending in "\\")."""
    head = "@=" if name == "" else '"%s"=' % name.replace("\\", "\\\\").replace('"', '\\"')
    m = re.match(r"(hex(?:\([0-9a-f]+\))?:)(.*)$", data, re.I)
    if not m or len(head) + len(data) <= 80:
        return head + data
    parts = m.group(2).split(",")
    lines, cur = [], head + m.group(1)
    for i, p in enumerate(parts):
        piece = p + ("," if i < len(parts) - 1 else "")
        if len(cur) + len(piece) > 78:
            lines.append(cur + "\\")
            cur = "  "
        cur += piece
    return "\r\n".join(lines + [cur])


def _write_reg(path, model):
    out = ["Windows Registry Editor Version 5.00", ""]
    for s in model:
        out.append("[%s%s]" % ("-" if s["delete"] else "", s["key"]))
        out += [_value_line(n, d) for n, d in s["values"]]
        out.append("")
    with open(path, "wb") as f:
        f.write(b"\xff\xfe" + "\r\n".join(out + [""]).encode("utf-16-le"))


def _first_key(path):
    try:
        model = _read_reg(path)
    except (OSError, UnicodeError, ValueError):
        return None
    return _norm(model[0]["key"]) if model else None


def _cursor_defaults():
    """Windows' default pointers by value name (lower case): its "Windows Aero" scheme (what
    Mouse settings call Windows Default), else the default user's; "" = that scheme's name."""
    out = {}
    try:
        with winreg.OpenKey(winreg.HKEY_USERS, r".DEFAULT\Control Panel\Cursors") as k:
            for name, data, _ in _values(k):
                if isinstance(data, str) and not is_ours(data):
                    out[name.lower()] = data
    except OSError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Control Panel\Cursors\Schemes") as k:
            files = winreg.QueryValueEx(k, "Windows Aero")[0].split(",")
        out.update((n.lower(), f) for n, f in zip(CURSOR_ORDER, files))
    except OSError:
        pass
    return out


def _default_sound(section):
    """An event's .Default sound (Windows' own for it), as .reg data; no sound without one."""
    for name, data in (section or {}).get("values", ()):
        if name == "" and data != "-" and not is_ours(_text_of(data)):
            return data
    return '""'


def _default_sounds_only(by_key):
    """True when every event's .Current sound is its .Default one again."""
    for key, s in by_key.items():
        if key.startswith(SOUNDS + "\\apps\\") and key.endswith("\\.current"):
            now = next((d for n, d in s["values"] if n == ""), '""')
            then = _default_sound(by_key.get(key[:-len(".current")] + ".default"))
            if (_text_of(now) or "").lower() != (_text_of(then) or "").lower():
                return False
    return True


def _clean_colors(values):
    """Our dark classic palette -> Windows' default colours (any other colours stay)."""
    import windows_apply
    if not windows_apply.is_our_palette({n: _text_of(d) for n, d in values}):
        return False
    default = {n.lower(): c for n, c in windows_apply.default_colors().items()}
    for v in values:
        if v[0].lower() in default:
            v[1] = _sz(default[v[0].lower()])
    return True


def _clean(model):
    """Take Easy Theme Creator's own values out of a parsed .reg file (see _read_reg) and
    put Windows' own in their place. Returns True when anything changed.
      ...\\DefaultIcon         our icon deleted; a key left empty is deleted (Windows' icon)
      AppEvents ...\\.Current  the event's own Windows sound (its .Default)
      Control Panel\\Cursors   Windows' default pointers (and scheme)
      Control Panel\\Colors    our dark palette -> Windows' default colours
      anything else of ours   deleted"""
    changed = sounds = pointers = False
    by_key = {_norm(s["key"]): s for s in model}
    cursors = None
    for s in model:
        if s["delete"]:
            continue
        key, hit = _norm(s["key"]), False
        if key == COLORS:
            changed |= _clean_colors(s["values"])
            continue
        for v in s["values"]:
            if not is_ours(_text_of(v[1])):
                continue
            hit = True
            if key == CURSORS and v[0]:
                if cursors is None:
                    cursors = _cursor_defaults()
                v[1], pointers = _expand_sz(cursors.get(v[0].lower(), "")), True
            elif key.startswith(SOUNDS + "\\apps\\") and key.endswith("\\.current") and not v[0]:
                v[1], sounds = _default_sound(by_key.get(key[:-len(".current")] + ".default")), True
            else:
                v[1] = "-"
        if hit and key.endswith("\\defaulticon") and all(v[1] == "-" for v in s["values"]):
            s["delete"], s["values"] = True, []
        changed |= hit
    if pointers:                     # our scheme name went with our pointers
        for v in by_key[CURSORS]["values"]:
            if not v[0]:
                v[1] = _sz(cursors.get("", ""))
            elif v[0].lower() == "scheme source":
                v[1] = "dword:00000002"                 # a Windows scheme
    if sounds and SOUNDS in by_key and _default_sounds_only(by_key):
        for v in by_key[SOUNDS]["values"]:
            if not v[0] and (_text_of(v[1]) or "").lower() == ".current":
                v[1] = '".Default"'                     # "Windows Default" again
    return changed


def _guard_export(path):
    """Right after `reg export`: our own values out of the saved copy (see _clean), so they
    never count as "before". False when nothing of the key is left (Undo deletes it then)."""
    try:
        model = _read_reg(path)
        if not _clean(model):
            return True
    except (OSError, UnicodeError, ValueError):
        return True                                   # keep the export as it is
    if model and all(s["delete"] for s in model):
        try:
            os.remove(path)
        except OSError:
            pass
        return False
    _write_reg(path, model)
    return True


def _restore_file(path):
    """Import one saved key, cleaned of our own values first (snapshots of 2.3 and older
    weren't). Returns what went wrong, or None."""
    name = os.path.basename(path)
    if not os.path.exists(path):
        return "the saved copy %s is missing" % name
    try:
        model = _read_reg(path)
        changed = _clean(model)
    except (OSError, UnicodeError, ValueError):
        return None if _reg("import", path) else "Windows would not take back " + name
    keep = [s for s in model if not s["delete"]]
    gone_keys = [s["key"] for s in model if s["delete"]]
    gone_values = [(s["key"], n) for s in keep for n, d in s["values"] if d == "-"]
    src = path
    if changed or gone_keys or gone_values:          # deletions are done here, not by reg.exe
        for s in keep:
            s["values"] = [v for v in s["values"] if v[1] != "-"]
        src = os.path.join(SNAP, "restore-now.reg")
        _write_reg(src, keep)
    try:
        if keep and not _reg("import", src):
            return "Windows would not take back %s (%s)" % (keep[0]["key"], name)
    finally:
        if src != path:
            try:
                os.remove(src)
            except OSError:
                pass
    for key in gone_keys:
        if not _delete_key(key):
            return "could not remove " + key
    for key, n in gone_values:
        try:
            _delete_value(key, n)
        except OSError as e:
            return "could not remove %s from %s (%s)" % (n or "(default)", key, e)
    return None
