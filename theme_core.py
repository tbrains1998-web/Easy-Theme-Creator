"""Theme logic: find colors in a picture and write a Windows .theme file."""
import colorsys
import os
import re
import shutil
import time

from PIL import Image

import assets


def find_colors(image_path, count=6):
    """Return the main colors of a picture as hex strings, most common first."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((200, 200))
    small = img.quantize(colors=count * 3, method=Image.Quantize.FASTOCTREE, kmeans=3)
    palette = small.getpalette()
    picked = []
    for _, i in sorted(small.getcolors(), reverse=True):
        rgb = tuple(palette[i * 3:i * 3 + 3])
        # Skip colors that look almost the same as one we already have.
        if all(sum((a - b) ** 2 for a, b in zip(rgb, p)) > 40 ** 2 for p in picked):
            picked.append(rgb)
        if len(picked) == count:
            break
    return ["#%02x%02x%02x" % c for c in picked]


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def pick_accent(colors):
    """Pick the most colorful (and not too dark) color for buttons and borders."""
    def score(c):
        hue, light, sat = colorsys.rgb_to_hls(*(v / 255 for v in _rgb(c)))
        return sat * (1 - abs(light - 0.5) * 1.5)
    return max(colors, key=score)


def is_dark(image_path):
    """True if the picture is mostly dark, so dark mode fits it better."""
    img = Image.open(image_path).convert("L")
    img.thumbnail((100, 100))
    pixels = list(img.getdata())
    return sum(pixels) / len(pixels) < 128


def nice_name(image_path):
    """A short theme name from the picture's file name, or "My Theme" if it's gibberish."""
    stem = re.sub(r"[_\-.]+", " ", os.path.splitext(os.path.basename(image_path))[0]).strip()
    if re.fullmatch(r"[A-Za-z][A-Za-z ]{0,24}", stem):
        return stem.title()
    return "My Theme"


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*]', "", name).strip() or "My Theme"


def accent_rgba(hex_color):
    return _rgb(hex_color) + (255,)


ICON_KEYS = {
    "pc": "{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "network": "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}",
    "user": "{59031A47-3F72-44A7-89C5-5595FE6B30EE}",
}
BIN_KEY = "{645FF040-5081-101B-9F08-00AA002F954E}"


HEADER = "; Made with Easy Theme Creator"      # first line of every .theme we write


def theme_text(name, wallpaper_path, accent, dark, pointers=None, icons=None, sounds=None):
    r, g, b = _rgb(accent)
    mode = "Dark" if dark else "Light"
    text = f"""{HEADER}
[Theme]
DisplayName={name}
"""
    for kind, key in ICON_KEYS.items():
        if icons:
            text += f"\n[CLSID\\{key}\\DefaultIcon]\nDefaultValue={icons[kind]}\n"
    if icons:
        text += (f"\n[CLSID\\{BIN_KEY}\\DefaultIcon]\nFull={icons['bin_full']},0\n"
                 f"Empty={icons['bin_empty']},0\n")
    text += f"""
[Control Panel\\Desktop]
Wallpaper={wallpaper_path}
TileWallpaper=0
WallpaperStyle=10
"""
    if pointers:
        text += f"\n[Control Panel\\Cursors]\nDefaultValue={name}\n"
        text += "".join(f"{k}={p}\n" for k, p in pointers.items())
    if sounds:
        text += f"\n[Sounds]\nSchemeName={name}\n"
        for app, event, snd in assets.SOUND_EVENTS:
            text += (f"\n[AppEvents\\Schemes\\Apps\\{app}\\{event}\\.Current]\n"
                     f"DefaultValue={sounds[snd]}\n")
    text += f"""
[VisualStyles]
Path=%SystemRoot%\\resources\\themes\\Aero\\Aero.msstyles
ColorStyle=NormalColor
Size=NormalSize
AutoColorization=0
ColorizationColor=0XC4{r:02X}{g:02X}{b:02X}
SystemMode={mode}
AppMode={mode}

[MasterThemeSelector]
MTSM=RJSPBS
"""
    return text


def make_theme(name, image_path, accent, dark, out_dir,
               pointers=True, icons=True, sounds=True):
    """Build the whole theme in out_dir/<name>/.

    Returns a dict with the paths of everything made: "theme", "wallpaper",
    "pointers", "icons" and "sounds" (the last three are None when skipped).

    Besides the wallpaper and colors it can add mouse pointers, desktop icons
    and sounds, all drawn in the accent color.
    """
    name = safe_name(name)
    folder = os.path.abspath(os.path.join(out_dir, name))
    os.makedirs(folder, exist_ok=True)
    # Windows keeps the current theme's sounds, pointers and wallpaper open, so
    # each build gets a fresh folder instead of overwriting files in use.
    parts = os.path.join(folder, "parts-%d" % time.time_ns())
    os.makedirs(parts, exist_ok=True)
    # Older parts go only when nothing points at them any more: when this Apply leaves
    # the pointers, sounds or icons as they are, Windows still uses the old files.
    used = _used_paths()
    for old in os.listdir(folder):
        old = os.path.join(folder, old)
        if os.path.basename(old).startswith("parts-") and old != parts and not _in_use(old, used):
            shutil.rmtree(old, ignore_errors=True)  # whatever is still open stays
    _remove_old_themes(out_dir, folder, used)
    ext = os.path.splitext(image_path)[1].lower() or ".jpg"
    wallpaper = os.path.join(parts, "wallpaper" + ext)
    shutil.copyfile(image_path, wallpaper)
    color = accent_rgba(accent)
    p = assets.make_pointers(os.path.join(parts, "pointers"), color) if pointers else None
    i = assets.make_icons(os.path.join(parts, "icons"), color) if icons else None
    s = assets.make_sounds(os.path.join(parts, "sounds")) if sounds else None
    theme_path = os.path.join(folder, name + ".theme")
    with open(theme_path, "w", encoding="utf-16") as f:
        f.write(theme_text(name, wallpaper, accent, dark, p, i, s))
    return {"name": name, "theme": theme_path, "wallpaper": wallpaper,
            "pointers": p, "icons": i, "sounds": s}


# ------------------------------------------------------------------ old themes and parts

def _used_paths():
    """Every file this account's settings point at now that can lie in a theme folder:
    mouse pointers, sounds, desktop icons and the wallpaper (normalised for comparing)."""
    import winreg
    hkcu = winreg.HKEY_CURRENT_USER
    found = []

    def subkeys(path):
        names = []
        try:
            with winreg.OpenKey(hkcu, path) as k:
                while True:
                    try:
                        names.append(winreg.EnumKey(k, len(names)))
                    except OSError:
                        break
        except OSError:
            pass
        return names

    def values(path, only=None):
        try:
            with winreg.OpenKey(hkcu, path) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    if only is None or name.lower() == only:
                        found.extend(data if isinstance(data, list) else [data])
        except OSError:
            pass

    values(r"Control Panel\Cursors")
    values(r"Control Panel\Desktop", "wallpaper")
    for app in subkeys(r"AppEvents\Schemes\Apps"):
        for event in subkeys(r"AppEvents\Schemes\Apps" + "\\" + app):
            values(r"AppEvents\Schemes\Apps\%s\%s\.Current" % (app, event))
    for root in (r"Software\Classes\CLSID", r"Software\Microsoft\Windows\CurrentVersion\Explorer\CLSID"):
        for clsid in subkeys(root):
            values(root + "\\" + clsid + "\\DefaultIcon")
    return [os.path.normcase(os.path.expandvars(v)) for v in found if isinstance(v, str) and v]


def _in_use(folder, used):
    """True when one of the `used` paths lies inside `folder`."""
    inside = os.path.normcase(os.path.abspath(folder)) + os.sep
    return any(inside in v for v in used)


def _themes_in_use():
    """Windows' current theme file and the one Undo would put back, or None when that
    can't be read (then no theme folder is removed)."""
    import winreg
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes") as k:
            try:
                out.append(winreg.QueryValueEx(k, "CurrentTheme")[0])
            except FileNotFoundError:
                pass
        import undo
        if undo.has_snapshot():
            out.append(undo.load().get("current_theme_before") or "")
    except Exception:
        return None
    return [os.path.normcase(os.path.expandvars(p)) for p in out if isinstance(p, str) and p]


def _made_by_us(theme_file):
    try:
        with open(theme_file, "rb") as f:
            head = f.read(256)
    except OSError:
        return False
    text = head.decode("utf-16" if head[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8", "ignore")
    return text.lstrip("﻿").startswith(HEADER)


def _our_theme_folder(folder):
    """True for a folder holding only what make_theme writes: our .theme file(s) (with
    HEADER) and parts-* folders. Anything else in it and it isn't ours to delete."""
    try:
        names = os.listdir(folder)
    except OSError:
        return False
    themes = 0
    for n in names:
        p = os.path.join(folder, n)
        if n.startswith("parts-") and os.path.isdir(p):
            continue
        if n.lower().endswith(".theme") and os.path.isfile(p) and _made_by_us(p):
            themes += 1
            continue
        return False
    return themes > 0


def _remove_old_themes(out_dir, current, used):
    """Every picture name gets its own theme folder. Delete the other folders this app
    made, except the one holding Windows' current theme (or the theme Undo would put
    back) and any that a setting still points into. Folders without our header are
    never touched."""
    themes = _themes_in_use()
    if themes is None:
        return
    current = os.path.normcase(os.path.abspath(current))
    try:
        names = os.listdir(out_dir)
    except OSError:
        return
    for n in names:
        folder = os.path.join(out_dir, n)
        if os.path.normcase(os.path.abspath(folder)) == current or not os.path.isdir(folder):
            continue
        if _in_use(folder, themes) or _in_use(folder, used) or not _our_theme_folder(folder):
            continue
        shutil.rmtree(folder, ignore_errors=True)
