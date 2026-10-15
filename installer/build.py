"""Build "Easy Theme Creator Setup.exe" on Windows.

    python installer\\build.py

Stages everything into installer\\stage and compiles installer\\setup.iss with Inno
Setup 6 (ISCC.exe). The installer carries:
  app\\      the app (Python files, icon, Alien Start orb, Orbitron font)
  python\\   a trimmed private copy of this PC's Python 3.12 with Tk, NumPy, Pillow, pefile
  deps\\     SecureUxTheme (MSI), Windhawk (setup) and the prebuilt Resource Redirect mod
  licenses\\ the licences of everything bundled
Everything is free: the taskbar, Start button and Explorer looks use Windhawk mods.
"""
import compileall
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import winreg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STAGE = os.path.join(HERE, "stage")
OUT = os.path.join(ROOT, "dist")
VERSION = "2.4"

APP_FILES = ["xaml_styles.py", "standard_colors.py", "openshell.py", "openshell_skin.py", "alien_icons.py", "armor.py", "assets.py", "cpl_panes.py", "easy_theme_creator.py",
             "folders.py", "launch.pyw", "layout.py", "premium.py", "preview.py", "scifont.py",
             "shell_icons.py", "skin.py", "taskbar.py", "theme_core.py", "undo.py",
             "windows_apply.py", "app.ico"]
APP_DIRS = {"fonts": ["Orbitron Medium.ttf", "Orbitron Bold.ttf", "Open Font License.markdown"],
            "orbs": ["alien-orb-216.png"]}

# Third-party installers (all free, open source), fetched from their official release
# pages into third-party\ when missing and checked against the SHA-256 they were
# verified with - a different file is refused, never bundled.
THIRD = os.path.join(ROOT, "third-party")
SECUREUXTHEME = (os.path.join(THIRD, "secureuxtheme", "SecureUxTheme_x64.msi"),
                 "af6ab67e0a283a0138b827b6731d5bb1f4ffc59e6d905f1c41567eb3305a9537",
                 "https://github.com/namazso/SecureUxTheme/releases/download/v4.0.0/SecureUxTheme_x64.msi")
OPENSHELL_EXE = (os.path.join(THIRD, "openshell", "OpenShellSetup_4_4_198.exe"),
                 "a4d2d4459de55b5e962ba2a14f7bb794170511649138173dfa72949837b48c3f",
                 "https://github.com/Open-Shell/Open-Shell-Menu/releases/download/v4.4.198/OpenShellSetup_4_4_198.exe")
OPENSHELL = (os.path.join(THIRD, "openshell", "OpenShellSetup64_4_4_198.msi"),      # extracted from the exe
             "e3f7f41fe718d01a80f2af7f8d6f6c50aded56e1ea80f85d83eab03ac0cdd493", None)
WINDHAWK = (os.path.join(THIRD, "windhawk", "windhawk_setup.exe"),
            "5116cc1703384aac88b8d7a3b57f172aea5da32b6df7355fb2f8247d23813c8f",
            "https://github.com/ramensoftware/windhawk/releases/download/v1.7.3/windhawk_setup.exe")
WH_DATA = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Windhawk")
MODS = ["icon-resource-redirect", "windows-11-taskbar-styler", "windows-11-file-explorer-styler"]

# Python: only what the app imports.
PY_SKIP_LIB = {"test", "idlelib", "ensurepip", "turtledemo", "lib2to3", "pydoc_data", "venv",
               "site-packages", "__pycache__"}
PY_PACKAGES = ["numpy", "numpy.libs", "PIL", "pefile.py", "peutils.py", "ordlookup"]
PY_DIST_INFO = ["numpy-*.dist-info", "pillow-*.dist-info", "pefile-*.dist-info"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "test"))
    else:
        shutil.copy2(src, dst)


def stage_app():
    app = os.path.join(STAGE, "app")
    for f in APP_FILES:
        copy(os.path.join(ROOT, f), os.path.join(app, f))
    for d, files in APP_DIRS.items():
        for f in files:
            copy(os.path.join(ROOT, d, f), os.path.join(app, d, f))
    copy(os.path.join(HERE, "README.txt"), os.path.join(STAGE, "README.txt"))


def stage_python():
    base = sys.base_prefix
    py = os.path.join(STAGE, "python")
    for f in os.listdir(base):
        full = os.path.join(base, f)
        if os.path.isfile(full) and f.lower().endswith((".exe", ".dll")) and f.lower().startswith(
                ("python", "vcruntime")):
            copy(full, os.path.join(py, f))
    copy(os.path.join(base, "LICENSE.txt"), os.path.join(py, "LICENSE.txt"))
    copy(os.path.join(base, "DLLs"), os.path.join(py, "DLLs"))
    for name in os.listdir(os.path.join(base, "Lib")):
        if name not in PY_SKIP_LIB:
            copy(os.path.join(base, "Lib", name), os.path.join(py, "Lib", name))
    for sub in ("tcl8.6", "tk8.6"):
        copy(os.path.join(base, "tcl", sub), os.path.join(py, "tcl", sub))
    for junk in ("tcl/tk8.6/demos", "tcl/tcl8.6/tzdata", "Lib/tkinter/test"):
        shutil.rmtree(os.path.join(py, junk), ignore_errors=True)
    import numpy
    site = os.path.dirname(os.path.dirname(numpy.__file__))
    dst_site = os.path.join(py, "Lib", "site-packages")
    for name in PY_PACKAGES:
        if os.path.exists(os.path.join(site, name)):
            copy(os.path.join(site, name), os.path.join(dst_site, name))
    for pattern in PY_DIST_INFO:
        for d in glob.glob(os.path.join(site, pattern)):
            copy(d, os.path.join(dst_site, os.path.basename(d)))
    # Precompile so the app starts quickly (Program Files isn't writable for the cache).
    compileall.compile_dir(os.path.join(py, "Lib"), quiet=1, workers=0)
    compileall.compile_dir(os.path.join(STAGE, "app"), quiet=1)


def fetch(path, digest, url):
    """Download `url` to `path` unless a file with the right hash is already there."""
    if os.path.exists(path) and sha256(path) == digest:
        return
    if not url:
        raise SystemExit("Missing: " + path)
    import urllib.request
    print("downloading", url)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if sha256(tmp) != digest:
        os.remove(tmp)
        raise SystemExit("Downloaded file doesn't match the verified hash, refusing: " + url)
    os.replace(tmp, path)


def fetch_deps():
    fetch(*SECUREUXTHEME)
    fetch(*WINDHAWK)
    fetch(*OPENSHELL_EXE)
    if not (os.path.exists(OPENSHELL[0]) and sha256(OPENSHELL[0]) == OPENSHELL[1]):
        # Open-Shell's setup is a wrapper around two MSIs; its own switch unpacks the 64-bit one.
        subprocess.run([OPENSHELL_EXE[0], "extract64"], cwd=os.path.dirname(OPENSHELL_EXE[0]), check=True)
        if sha256(OPENSHELL[0]) != OPENSHELL[1]:
            raise SystemExit("The extracted Open-Shell MSI doesn't match the verified hash.")


def stage_deps():
    deps = os.path.join(STAGE, "deps")
    fetch_deps()
    for path, digest, _ in (SECUREUXTHEME, WINDHAWK, OPENSHELL):
        if sha256(path) != digest:
            raise SystemExit("Hash mismatch, refusing to bundle: " + path)
        copy(path, os.path.join(deps, os.path.basename(path)))
    mod = os.path.join(deps, "windhawk-mod")
    for mod_id in MODS:
        if not os.path.exists(os.path.join(WH_DATA, "ModsSource", mod_id + ".wh.cpp")):
            raise SystemExit("Install the %s mod in Windhawk first (it is copied from there)." % mod_id)
        copy(os.path.join(WH_DATA, "ModsSource", mod_id + ".wh.cpp"), os.path.join(mod, mod_id + ".wh.cpp"))
    # Each mod's DLL as Windhawk has it registered here (an update can leave the old,
    # still loaded DLL behind next to it); the name carries the mod's version.
    dlls = {m: registered_dll(m) for m in MODS}
    for arch in ("32", "64"):
        src = os.path.join(WH_DATA, "Engine", "Mods", arch)
        files = [f for f in os.listdir(src) if f in ("libc++.whl", "libunwind.whl", "windhawk-mod-shim.dll") or any(
                 f == dlls[m] or (not dlls[m] and f.startswith(m + "_") and f.endswith(".dll")) for m in MODS)]
        for f in files:
            copy(os.path.join(src, f), os.path.join(mod, arch, f))
    our_dll = build_our_mod(mod)
    check_mod_files(mod)
    copy(os.path.join(HERE, "setup-windhawk-mod.ps1"), os.path.join(deps, "setup-windhawk-mod.ps1"))
    return our_dll


def registered_dll(mod_id):
    """The DLL Windhawk loads for an installed mod (its LibraryFileName), or None."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Windhawk\Engine\Mods" + "\\" + mod_id, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "LibraryFileName")[0] or None
    except OSError:
        return None


def mod_version(path):
    """The @version in a mod's ==WindhawkMod== header."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("// ==/WindhawkMod=="):
                break
            m = re.match(r"//\s*@version\s+(\S+)", line)
            if m:
                return m.group(1)
    raise SystemExit("No @version in " + path)


def check_mod_files(mod_dir):
    """setup-windhawk-mod.ps1 registers the one DLL it finds per mod and takes the mod's
    version from its name, so: exactly one DLL per mod and architecture it is built for
    (64-bit always, ours 32-bit too), the same name in both, and that name's version is
    the one in the mod's source."""
    for mod_id in MODS + [OUR_MOD]:
        found = {}
        for arch in ("32", "64"):
            folder = os.path.join(mod_dir, arch)
            names = [f for f in (os.listdir(folder) if os.path.isdir(folder) else [])
                     if f.startswith(mod_id + "_") and f.lower().endswith(".dll")]
            if len(names) > 1:
                raise SystemExit("More than one %s-bit DLL staged for %s: %s" % (arch, mod_id, names))
            if names:
                found[arch] = names[0]
        for arch in (("32", "64") if mod_id == OUR_MOD else ("64",)):
            if arch not in found:
                raise SystemExit("No %s-bit DLL staged for %s." % (arch, mod_id))
        if len(set(found.values())) != 1:
            raise SystemExit("The %s DLLs have different names: %s" % (mod_id, found))
        version = mod_version(os.path.join(mod_dir, mod_id + ".wh.cpp"))
        if not found["64"].startswith("%s_%s_" % (mod_id, version)):
            raise SystemExit("%s doesn't match its source's @version %s." % (found["64"], version))


OUR_MOD = "easy-theme-creator-standard-colors"
OUR_MOD_SRC = os.path.join(HERE, "windhawk-mod", OUR_MOD + ".wh.cpp")
WH_ROOT = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Windhawk")
MOD_FLAGS = ["-std=c++23", "-DUNICODE", "-D_UNICODE", "-DWINVER=0x0A00", "-D_WIN32_WINNT=0x0A00",
             "-D_WIN32_IE=0x0A00", "-DNTDDI_VERSION=0x0A000008", "-D__USE_MINGW_ANSI_STDIO=0", "-DWH_MOD",
             "-include", "windhawk_api.h", "-Wno-pragma-pack", "-Wno-pragma-system-header-outside-header",
             "-O2", "-shared", "-nostdlib++"]
MOD_LIBS = ["-luser32", "-lgdi32", "-luxtheme"]


def our_mod_dll():
    """Our mod's DLL name, Windhawk-style <id>_<version>_<build>.dll: the version is the
    source's @version, the build number comes from the source and the compile flags. So
    every change gets a new file (setup copies only files that aren't there yet - an old
    one may be loaded) and setup can tell from the registered name that it must update."""
    with open(OUR_MOD_SRC, "rb") as f:
        src = f.read().replace(b"\r\n", b"\n")
    h = hashlib.sha256(src + "\0".join(MOD_FLAGS + MOD_LIBS).encode()).hexdigest()
    return "%s_%s_%d.dll" % (OUR_MOD, mod_version(OUR_MOD_SRC), 100000 + int(h[:12], 16) % 900000)


def build_our_mod(mod_dir):
    """Compile our own Windhawk mod (readable text + standard colours for chosen apps) for
    64- and 32-bit programs with Windhawk's bundled clang, the way Windhawk itself does.
    Returns the DLL's name."""
    clang = os.path.join(WH_ROOT, "Compiler", "bin", "clang++.exe")
    engine = glob.glob(os.path.join(WH_ROOT, "Engine", "*", "64", "windhawk.dll"))
    if not os.path.exists(clang) or not engine:
        raise SystemExit("Windhawk (with its compiler) must be installed to build the mod.")
    engine_dir = os.path.dirname(os.path.dirname(engine[-1]))
    dll = our_mod_dll()
    copy(OUR_MOD_SRC, os.path.join(mod_dir, OUR_MOD + ".wh.cpp"))
    for arch, target in (("64", "x86_64-w64-mingw32"), ("32", "i686-w64-mingw32")):
        out = os.path.join(mod_dir, arch, dll)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cmd = ([clang, "-target", target] + MOD_FLAGS +
               ["-I", os.path.join(WH_ROOT, "Compiler", "include"), "-o", out, "-x", "c++", OUR_MOD_SRC,
                "-x", "none", os.path.join(engine_dir, arch, "windhawk.dll")] + MOD_LIBS)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("Mod compile failed (%s):\n%s" % (arch, r.stderr[-2000:]))
    return dll


def stage_licenses():
    lic = os.path.join(STAGE, "licenses")
    os.makedirs(lic, exist_ok=True)
    for f in glob.glob(os.path.join(HERE, "licenses", "*")):
        copy(f, os.path.join(lic, os.path.basename(f)))
    copy(os.path.join(sys.base_prefix, "LICENSE.txt"), os.path.join(lic, "Python-LICENSE.txt"))
    copy(os.path.join(ROOT, "fonts", "Open Font License.markdown"), os.path.join(lic, "Orbitron-OFL.md"))


def main():
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    print("staging app...")
    stage_app()
    print("staging Python...")
    stage_python()
    print("staging SecureUxTheme, Windhawk and the mod...")
    our_dll = stage_deps()
    stage_licenses()
    iscc = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe")
    if not os.path.exists(iscc):
        iscc = shutil.which("ISCC") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    print("compiling installer...")
    # Inno's final resource update on the output file kept failing in dist\ (error 32,
    # file in use - antivirus or a folder share holding it), so compile in TEMP and copy.
    import tempfile
    tmp_out = os.path.join(tempfile.gettempdir(), "etc-installer-out")
    shutil.rmtree(tmp_out, ignore_errors=True)
    r = subprocess.run([iscc, "/Q", "/DStage=" + STAGE, "/DOutDir=" + tmp_out, "/DAppVersion=" + VERSION,
                        "/DOurModDll=" + our_dll, os.path.join(HERE, "setup.iss")])
    if r.returncode:
        raise SystemExit("Inno Setup failed (exit %d)." % r.returncode)
    shutil.copyfile(os.path.join(tmp_out, "Easy Theme Creator Setup.exe"),
                    os.path.join(OUT, "Easy Theme Creator Setup.exe"))
    shutil.rmtree(tmp_out, ignore_errors=True)
    exe = os.path.join(OUT, "Easy Theme Creator Setup.exe")
    print("built %s (%.1f MB)" % (exe, os.path.getsize(exe) / 1e6))


if __name__ == "__main__":
    main()
