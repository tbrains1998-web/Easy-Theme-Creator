"""Dark Control Panel side panes, through Windhawk's "Resource Redirect" mod.

Control Panel's left pane (and the home page panel) aren't drawn from the window
skin: shell32.dll's layout paints them with plain white pictures of its own
(bitmaps #633 and #635, `graphic(633, ...)` in the DUI markup), so no .msstyles
change can reach them. The Resource Redirect mod can make Explorer load those two
pictures from another file instead. We write that file (a tiny resource-only DLL
with dark versions) plus a theme.ini pointing at it; the mod's "Theme paths"
setting points at our folder once, and Explorer picks it up when it restarts.
Nothing in Windows itself is changed. Undo empties the theme.ini.
"""
import glob
import os
import struct
import time
import winreg

FOLDER = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "EasyThemeCreator", "redirect")
INI = os.path.join(FOLDER, "theme.ini")
MOD_ID = "icon-resource-redirect"
NAV_PANE, HOME_PANEL = 633, 635          # shell32.dll bitmaps (1x1 and 64x60, white)


# ------------------------------------------------------------------ the DLL

def _bitmap(w, h, rgb):
    """A 24-bit DIB as stored in an RT_BITMAP resource (no file header)."""
    row = bytes((rgb[2], rgb[1], rgb[0])) * w
    row += b"\0" * (-len(row) % 4)
    return struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(row) * h, 2835, 2835, 0, 0) + row * h


def _resource_dll(bitmaps, uifiles=None):
    """Smallest valid 64-bit DLL holding only resources: RT_BITMAP {id: dib bytes} and,
    optionally, "UIFILE" {id: utf-8 bytes} (Explorer's DirectUI layouts). Windows loads
    it as a data file only, so it carries no code."""
    uifiles = uifiles or {}
    types = [(2, bitmaps)] + ([("UIFILE", uifiles)] if uifiles else [])   # RT_BITMAP = 2
    items = [(ti, rid) for ti, (_, res) in enumerate(types) for rid in sorted(res)]
    n = len(items)
    type_dir = 16 + 8 * len(types)         # root dir + one entry per type
    name_dir_at, pos = [], type_dir        # one name dir per type
    for _, res in types:
        name_dir_at.append(pos)
        pos += 16 + 8 * len(res)
    lang_dirs = pos                        # one language dir (1 entry) per item
    entries = lang_dirs + 24 * n
    strings = entries + 16 * n             # the "UIFILE" type name, if any
    name_blob = b""
    if uifiles:
        name_blob = struct.pack("<H", 6) + "UIFILE".encode("utf-16le")
        name_blob += b"\0" * (-len(name_blob) % 8)
    data = strings + len(name_blob)
    rsrc_rva = 0x1000
    blob = bytearray(struct.pack("<IIHHHH", 0, 0, 0, 0, 1 if uifiles else 0, 1))   # root: named, numbered
    if uifiles:
        blob += struct.pack("<II", 0x80000000 | strings, 0x80000000 | name_dir_at[1])
    blob += struct.pack("<II", 2, 0x80000000 | name_dir_at[0])
    for ti, (_, res) in enumerate(types):
        blob += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(res))
        for rid in sorted(res):
            blob += struct.pack("<II", rid, 0x80000000 | (lang_dirs + 24 * items.index((ti, rid))))
    for i in range(n):
        blob += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 0, entries + 16 * i)
    payload, offsets = bytearray(), []
    for ti, rid in items:
        d = types[ti][1][rid]
        offsets.append(data + len(payload))
        payload += d + b"\0" * (-len(d) % 8)
    for (ti, rid), off in zip(items, offsets):
        blob += struct.pack("<IIII", rsrc_rva + off, len(types[ti][1][rid]), 0, 0)
    blob += name_blob + payload
    raw_size = len(blob) + (-len(blob) % 0x200)
    image_size = rsrc_rva + len(blob) + (-len(blob) % 0x1000)

    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 240, 0x2022)   # x64, 1 section, DLL
    opt = struct.pack("<HBBIIIII", 0x20B, 14, 0, 0, raw_size, 0, 0, rsrc_rva)
    opt += struct.pack("<QII", 0x180000000, 0x1000, 0x200)
    opt += struct.pack("<HHHHHHI", 6, 0, 0, 0, 6, 0, 0)
    opt += struct.pack("<IIIHH", image_size, 0x200, 0, 2, 0x0100)
    opt += struct.pack("<QQQQII", 0x100000, 0x1000, 0x100000, 0x1000, 0, 16)
    dirs = [(0, 0)] * 16
    dirs[2] = (rsrc_rva, len(blob))
    opt += b"".join(struct.pack("<II", *d) for d in dirs)
    section = struct.pack("<8sIIIIIIHHI", b".rsrc", len(blob), rsrc_rva, raw_size, 0x200,
                          0, 0, 0, 0, 0x40000040)
    dos = b"MZ" + b"\0" * 58 + struct.pack("<I", 0x40)
    head = dos + b"PE\0\0" + coff + opt + section
    return head + b"\0" * (0x200 - len(head)) + bytes(blob) + b"\0" * (raw_size - len(blob))


# ------------------------------------------------------------------ bottom details pane

# Explorer's folder layouts (shell32 UIFILE 3-6, 19-21: generic, music, photo, documents
# and the library variants). Windows 11 still carries Windows 7's bottom details panel
# (thumbnail left, name and properties right, drag handle on top) in its "search-only
# library" layout, UIFILE 15. That block, grafted into the normal folder layouts, is
# served instead of Windows' own; Windows 11's right-hand details pane stays as it is.
# (Simply moving <DetailsContainer/> to the bottom gave an empty strip.)
LAYOUT_IDS = (3, 4, 5, 6, 19, 20, 21)
PANEL_SOURCE = 15
PANEL_START, PANEL_END = '<TemplateBackground id="atom(PreviewContainer)"', "</TemplateBackground>"
STATUS = '<StatusBarModule ModuleID="StatusBarModule" layoutpos="bottom" layout="filllayout()"/>'
RIGHT_PANE = '<DetailsContainer layoutpos="right"/>'   # Windows 11's own pane: left out, so
#                                                       "Details pane" shows only the bottom one
DETAILS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Modules\GlobalSettings\DetailsContainer"
DETAILS_KEY_FULL = "HKCU\\" + DETAILS_KEY               # as `reg export` wants it (for Undo)


def show_details_pane():
    """Switch Explorer's "Details pane" on (View > Show > Details pane), which is what
    makes the bottom panel appear. Stored by Explorer as a 16-byte value: first dword 1 =
    shown, second dword 2 = the details pane (1 = the preview pane)."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, DETAILS_KEY) as k:
        winreg.SetValueEx(k, "DetailsContainer", 0, winreg.REG_BINARY, struct.pack("<IIII", 1, 2, 0, 0))


def bottom_layouts():
    """{id: utf-8 bytes}: Windows' own folder layouts with the Windows 7 bottom panel added.
    Read from this PC's shell32 so they always match the installed Windows; when the
    expected pieces aren't there, nothing is returned (Explorer stays as Windows made it)."""
    import ctypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.LoadLibraryExW.restype = ctypes.c_void_p
    k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    k32.FindResourceW.restype = ctypes.c_void_p
    k32.FindResourceW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p]
    k32.LoadResource.restype = ctypes.c_void_p
    k32.LoadResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.LockResource.restype = ctypes.c_void_p
    k32.LockResource.argtypes = [ctypes.c_void_p]
    k32.SizeofResource.restype = ctypes.c_uint32
    k32.SizeofResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.FreeLibrary.argtypes = [ctypes.c_void_p]
    out = {}
    mun = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SystemResources", "shell32.dll.mun")
    h = k32.LoadLibraryExW(mun, None, 0x22)          # as a data file, no code runs
    if not h:
        return out
    def uifile(rid):
        r = k32.FindResourceW(h, ctypes.c_void_p(rid), "UIFILE")
        if not r:
            return ""
        size = k32.SizeofResource(h, r)
        return ctypes.string_at(k32.LockResource(k32.LoadResource(h, r)), size).decode("utf-8", "replace")

    try:
        src = uifile(PANEL_SOURCE)
        a, b = src.find(PANEL_START), src.find(PANEL_END)
        if a < 0 or b < a:
            return out
        panel = src[a:b + len(PANEL_END)]            # the whole PreviewContainer block
        for rid in LAYOUT_IDS:
            text = uifile(rid)
            # the panel goes right after the status bar line (both layoutpos="bottom":
            # the status bar stays lowest, the panel sits above it)
            if text.count(STATUS) == 1 and PANEL_START not in text:
                text = text.replace(STATUS, STATUS + "\r\n" + panel)
                out[rid] = text.replace(RIGHT_PANE + "\r\n", "").replace(RIGHT_PANE, "").encode("utf-8")
    finally:
        k32.FreeLibrary(h)
    return out


# ------------------------------------------------------------------ Windhawk

def windhawk_installed():
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for path in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Windhawk",
                     r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Windhawk"):
            try:
                winreg.OpenKey(root, path).Close()
                return True
            except OSError:
                pass
    return os.path.exists(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                                       "Windhawk", "windhawk.exe"))


def _mod_settings():
    """The Resource Redirect mod's settings key, or None if the mod isn't installed."""
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for path in (r"Software\Windhawk\Engine\Mods\%s\Settings" % MOD_ID,
                     r"Software\WOW6432Node\Windhawk\Engine\Mods\%s\Settings" % MOD_ID):
            try:
                return winreg.OpenKey(root, path)
            except OSError:
                pass
    return None


def status():
    """'ready', or a short reason the panes can't be darkened yet."""
    if not windhawk_installed():
        return "Windhawk isn't installed"
    key = _mod_settings()
    if key is None:
        return "the Resource Redirect mod isn't installed in Windhawk"
    with key:
        i = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, i)
            except OSError:
                break
            if name.startswith("themePaths[") and os.path.normcase(str(value).rstrip("\\/")) in (
                    os.path.normcase(FOLDER), os.path.normcase(INI)):
                return "ready"
            i += 1
    return 'in Windhawk, add "%s" to Resource Redirect > Settings > Theme paths' % FOLDER


# ------------------------------------------------------------------ apply / undo

def _write_ini(lines):
    os.makedirs(FOLDER, exist_ok=True)
    with open(INI, "w", encoding="utf-16") as f:          # GetPrivateProfileSection reads UTF-16
        f.write("[redirections]\n" + "".join(l + "\n" for l in lines))


def apply(nav=(24, 24, 27), panel=(16, 16, 18), details_bottom=False):
    """Write the dark pictures (and, with details_bottom, the folder layouts with the
    details pane along the bottom) and point the mod at them. Takes effect when Explorer
    restarts. Raises OSError (with a reason) if Windhawk isn't set up for it."""
    why = status()
    os.makedirs(FOLDER, exist_ok=True)
    # Explorer keeps the DLL open while it runs, so each Apply writes a new one.
    dll = os.path.join(FOLDER, "shell32-panes-%d.dll" % time.time())
    with open(dll, "wb") as f:
        f.write(_resource_dll({NAV_PANE: _bitmap(1, 1, nav), HOME_PANEL: _bitmap(64, 60, panel)},
                              bottom_layouts() if details_bottom else None))
    _write_ini([r"%SystemRoot%\System32\shell32.dll=" + os.path.basename(dll)])
    cleanup(keep=dll)
    if why != "ready":
        raise OSError(why)


def undo():
    if os.path.exists(INI):
        _write_ini([])
    cleanup()


def cleanup(keep=None):
    for f in glob.glob(os.path.join(FOLDER, "shell32-panes-*.dll")):
        if keep is None or os.path.normcase(f) != os.path.normcase(keep):
            try:
                os.remove(f)
            except OSError:
                pass                      # still open in Explorer: removed next time
