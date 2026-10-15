"""End-to-end self-test of an installed Easy Theme Creator (run inside Windows Sandbox).

Runs the real app code: Apply with a test picture, checks every part, takes
screenshots, then Undo and checks everything came back. Writes selftest.txt and
PNG screenshots to the results folder given as the first argument.
"""
import ctypes
import glob
import ctypes.wintypes as wt
import os
import runpy
import subprocess
import sys
import threading
import time
import traceback
import winreg

APP = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Easy Theme Creator", "app")
RES = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
sys.path.insert(0, APP)
os.chdir(APP)
log = open(os.path.join(RES, "selftest.txt"), "w", encoding="utf-8")
fails = []


def say(*a):
    print(*a, file=log, flush=True)


def check(name, ok, detail=""):
    say(("[OK  ] " if ok else "[FAIL] ") + name + ("" if ok or not detail else "   -- %s" % (detail,)))
    if not ok:
        fails.append(name)


def reg(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


HKCU, HKLM = winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE
ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
OS_KEY = r"Software\OpenShell\StartMenu\Settings"
TB = r"SOFTWARE\Windhawk\Engine\Mods\windows-11-taskbar-styler\Settings"
EX = r"SOFTWARE\Windhawk\Engine\Mods\windows-11-file-explorer-styler\Settings"
DESKTOP_CLSID = r"Software\Classes\CLSID\{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}\DefaultIcon"


def wallpaper():
    buf = ctypes.create_unicode_buffer(520)
    ctypes.windll.user32.SystemParametersInfoW(0x73, 520, buf, 0)
    return buf.value


def window_color():
    v = ctypes.windll.user32.GetSysColor(5)
    return (v & 255, v >> 8 & 255, v >> 16 & 255)


def state():
    return {"TaskbarAl": reg(HKCU, ADV, "TaskbarAl"),
            "SkinW7": reg(HKCU, OS_KEY, "SkinW7"),
            "MenuStyle": reg(HKCU, OS_KEY, "MenuStyle"),
            "StartButton": reg(HKCU, OS_KEY, "EnableStartButton"),
            "wallpaper_style": reg(HKCU, r"Control Panel\Desktop", "WallpaperStyle"),
            "tb_mark": reg(HKLM, TB, "styleConstants[0]"),
            "ex_mark": reg(HKLM, EX, "styleConstants[0]"),
            "desktop_icon": reg(HKCU, DESKTOP_CLSID, ""),
            "wallpaper": wallpaper(),
            "window_color": window_color(),
            "accent": reg(HKCU, r"Software\Microsoft\Windows\DWM", "AccentColor"),
            "theme": reg(HKCU, r"Software\Microsoft\Windows\CurrentVersion\Themes", "CurrentTheme")}


def shot(name, wait=0):
    from PIL import ImageGrab
    time.sleep(wait)
    try:
        ImageGrab.grab(all_screens=True).save(os.path.join(RES, name + ".png"))
    except OSError as e:            # Sandbox window minimized: no screen to photograph
        say("photo %s failed: %s" % (name, e))


def key(vk, up=False):
    ctypes.windll.user32.keybd_event(vk, 0, 2 if up else 0, 0)


def iter_windows(cls_name):
    """Top-level windows of a class."""
    u = ctypes.windll.user32
    found = []

    def cb(h, lp):
        buf = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, buf, 64)
        if buf.value == cls_name and u.IsWindowVisible(h):
            found.append(h)
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)(cb), 0)
    return iter(found)


def on_main(fn, timeout=120):
    """Run fn on the window's thread (through the app's own queue, which its main loop
    empties) and return its result - Tk may only be used from that thread."""
    done, out = threading.Event(), {}

    def run():
        try:
            out["v"] = fn()
        except Exception as e:
            out["e"] = e
        done.set()
    app.inbox.put(run)
    if not done.wait(timeout):
        raise TimeoutError("the window did not respond")
    if "e" in out:
        raise out["e"]
    return out.get("v")


def press(start, limit=600):
    """Press Apply / Undo like a user does: the work runs in the app's background thread
    while the window keeps running. Returns the seconds it took (None = still busy)."""
    t0 = time.time()
    start()
    while app.busy and time.time() - t0 < limit:
        time.sleep(0.2)
    time.sleep(0.5)
    return None if app.busy else time.time() - t0


try:
    from PIL import Image
    pic = os.path.join(RES, "test-picture.png")       # dark picture with a strong red
    img = Image.radial_gradient("L").resize((1920, 1080)).point(lambda v: 255 - v)
    Image.merge("RGB", (img, img.point(lambda v: v // 6), img.point(lambda v: v // 6))).save(pic)

    # a user whose wallpaper is set to "Fit" (Apply switches it to Fill; Undo must bring Fit back)
    with winreg.CreateKey(HKCU, r"Control Panel\Desktop") as k:
        winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, "6")
    before = state()
    say("before:", before)
    g = runpy.run_path(os.path.join(APP, "easy_theme_creator.py"), run_name="selftest")
    g["forget_open_after_restart"]()                 # what a real start of the app does
    check("Setup's open-after-restart request dropped once the app runs",
          reg(HKCU, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "EasyThemeCreator") is None)
    warnings = []
    g["messagebox"].showwarning = lambda title, msg, **k: warnings.append(msg)
    import tkinter as tk
    root = tk.Tk()
    app = g["App"](root)
    problems = []                                    # the app's own list of parts that failed
    real_done = app._done
    app._done = lambda failed, ok: (problems.extend(failed), real_done(failed, ok))
    app.pick_picture(pic)
except Exception:
    say("CRASH:\n" + traceback.format_exc())
    fails.append("crash")


def body():
  try:
    time.sleep(3)                                    # preview drawn
    say("accent picked:", app.accent, " chips:", on_main(lambda: {k: v.get() for k, v in app.parts.items()}),
        " compact:", app.compact, " window:", on_main(lambda: (root.winfo_width(), root.winfo_height())))

    # ---------------------------------------------------------- Apply
    def apply_and_shoot():                           # the busy bar should show while it works
        on_main(app.apply_now)
        time.sleep(1.5)
        check("busy bar shows while Apply works", app.busy and on_main(app.busy_bar.winfo_ismapped))
        shot("0-applying")
    took = press(apply_and_shoot)
    say("Apply took %s; status: %r" % ("%.1fs" % took if took else "too long", on_main(lambda: app.status.cget("text"))))
    say("problems:", problems)
    check("Apply finished (window back to normal)", took is not None and not on_main(app.busy_bar.winfo_ismapped))
    shot("0-app-after-apply")
    import skin
    restart_pending = skin.patcher_needs_restart()   # SecureUxTheme installed without a restart since
    unexpected = [p for p in problems if not (restart_pending and p[0] == "Windows" and "restart" in p[1])]
    check("Apply finished without unexpected problems", not unexpected, unexpected)
    expected = ["restart"] if restart_pending else []
    after = state()
    say("after:", after)
    check("wallpaper changed", after["wallpaper"] != before["wallpaper"] and os.path.exists(after["wallpaper"]), after["wallpaper"])
    check("wallpaper set to Fill", after["wallpaper_style"] == "10", after["wallpaper_style"])
    check("accent color set", after["accent"] is not None and after["accent"] != before["accent"], after["accent"])
    check("dark classic colors", max(after["window_color"]) < 60, after["window_color"])
    check("taskbar icons left-aligned", after["TaskbarAl"] == 0, after["TaskbarAl"])
    check("taskbar styler has our styles", after["tb_mark"] == "// Easy Theme Creator", after["tb_mark"])
    check("explorer styler has our styles", after["ex_mark"] == "// Easy Theme Creator", after["ex_mark"])
    import xaml_styles
    pngs = [f for f in os.listdir(xaml_styles.FOLDER) if f.endswith(".png")] if os.path.isdir(xaml_styles.FOLDER) else []
    check("taskbar/explorer pictures written", len(pngs) >= 10, len(pngs))
    check("Open-Shell uses the armor skin", after["SkinW7"] == "Easy Theme Armor" and after["MenuStyle"] == "Win7", (after["SkinW7"], after["MenuStyle"]))
    check("Open-Shell's own Start button off (the orb is the taskbar's)", after["StartButton"] == 0, after["StartButton"])
    import openshell
    age = time.time() - os.path.getmtime(openshell.SKIN_FILE) if os.path.exists(openshell.SKIN_FILE) else 1e9
    check("armor skin rebuilt in the accent", age < 600, "%.0fs old" % age)
    check("Open-Shell running", b"StartMenu.exe" in subprocess.run(["tasklist"], capture_output=True).stdout)
    check("desktop folder icon overridden", bool(after["desktop_icon"]) and os.path.exists(after["desktop_icon"].rsplit(",", 1)[0]), after["desktop_icon"])
    # up to 2.1 each Apply doubled every desktop.ini (\r\r\n, read back as blank lines)
    dini = os.path.join(os.environ["USERPROFILE"], "Desktop", "desktop.ini")
    draw = open(dini, "rb").read() if os.path.exists(dini) else b""
    dtext = draw.decode("utf-16", "replace") if draw[:2] == b"\xff\xfe" else draw.decode("mbcs", "replace")
    check("desktop.ini written cleanly (no doubling)", draw and "\r\r" not in dtext and "\r\n\r\n" not in dtext
          and len(draw) < 4096, (len(draw), dtext[:120]))
    import cpl_panes
    ini = open(cpl_panes.INI, encoding="utf-16").read() if os.path.exists(cpl_panes.INI) else ""
    check("Control Panel pane redirect written", "shell32.dll=" in ini, ini.strip())
    if "restart" not in expected:
        check("window skin active", "EasyThemeCreator" in (reg(HKCU, r"Software\Microsoft\Windows\CurrentVersion\ThemeManager", "DllName") or ""))
        check("Windows' current theme is ours", "My Theme" in (after["theme"] or "") or "EasyTheme" in (after["theme"] or ""), after["theme"])

    # ---------------------------------------------------------- fix an app (standard colours mod)
    import standard_colors
    check("standard-colours mod installed", standard_colors.available())
    probe = ("import tkinter as tk; r = tk.Tk(); r.withdraw(); "
             "print(' '.join('#%02x%02x%02x' % tuple(v // 257 for v in r.winfo_rgb(n)) for n in ('SystemWindow', 'SystemWindowText')))")
    py = os.path.join(os.path.dirname(APP), "python", "python.exe")

    def probe_colors():                              # what a freshly started program sees
        return subprocess.run([py, "-c", probe], capture_output=True, text=True, timeout=60).stdout.strip()
    themed = probe_colors()
    say("new program sees (themed):", themed)
    check("dark palette reaches new programs", themed.startswith("#121214"), themed)
    standard_colors.add("python.exe")
    check("app added to the fixed list", "python.exe" in standard_colors.apps(), standard_colors.apps())
    fixed = probe_colors()
    say("new program sees (on the list):", fixed)
    check("listed program gets Windows' standard colours", fixed == "#ffffff #000000", fixed)
    standard_colors.remove("python.exe")
    check("app removed from the fixed list", "python.exe" not in standard_colors.apps())

    # ---------------------------------------------------------- screenshots
    on_main(root.withdraw)                           # the test window must not cover the screen
    shot("1-desktop", wait=6)
    subprocess.Popen(["explorer.exe", "shell:MyComputerFolder"])
    shot("2-explorer", wait=5)
    # a folder with files, alone on screen: Armor Explorer adds Windows 7's details panel
    # along the bottom (it shows once Explorer's details pane is on, like Windows 7)
    subprocess.run(["taskkill", "/f", "/fi", "WINDOWTITLE eq Deze pc*"], capture_output=True)
    for h in list(iter_windows("CabinetWClass")):
        ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)          # WM_CLOSE
    time.sleep(2)
    import cpl_panes
    folder = os.path.join(os.environ["SystemRoot"], "Web", "Wallpaper")
    subprocess.Popen(["explorer.exe", folder])
    time.sleep(5)
    u = ctypes.windll.user32
    hwnd = next(iter_windows("CabinetWClass"), None)
    if hwnd:
        u.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        key(0x28); key(0x28, True)                   # Down: select a file so the panel fills
        time.sleep(1)
    shot("2b-explorer-folder", wait=1)
    say("DetailsContainer (set by Apply):", reg(HKCU, cpl_panes.DETAILS_KEY, "DetailsContainer"))
    check("folder layouts with bottom details pane in the redirect DLL",
          b'atom(PreviewContainer)' in open(max(glob.glob(os.path.join(cpl_panes.FOLDER, "shell32-panes-*.dll")),
                                            key=os.path.getmtime), "rb").read())
    check("Resource Redirect redirects all resources (needed for the layouts)",
          reg(HKLM, r"SOFTWARE\Windhawk\Engine\Mods\icon-resource-redirect\Settings", "allResourceRedirect") == 1)
    # where did Explorer put the panel? Every child window of the folder window, by class.
    try:
        rects = {}

        def cb(h, lp):
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(h, cls, 64)
            r = wt.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if r.right > r.left and r.bottom > r.top:
                rects.setdefault(cls.value, []).append((r.left, r.top, r.right, r.bottom))
            return True
        u.EnumChildWindows(hwnd, ctypes.WINFUNCTYPE(ctypes.c_int, wt.HWND, wt.LPARAM)(cb), 0)
        say("explorer child windows:", rects)
        view = rects.get("SHELLDLL_DefView", [None])[0]
        host = rects.get("DUIViewWndClassName", [None])[0]     # the panel is drawn in here
        # the file view ends well above the host's bottom edge: the panel (~90 px) + status bar
        gap = (host[3] - view[3]) if (view and host) else 0
        say("gap under the file view: %d px" % gap)
        check("Windows 7 details panel along the bottom (file view ends > 60 px above)", gap > 60, gap)
        check("Windows 11 right pane gone", "DetailsPaneHwndHostClass" not in rects)
    except Exception as e:
        say("pane position check failed:", e)
    key(0x1B); key(0x1B, True)
    subprocess.Popen(["control.exe", "appwiz.cpl"])
    shot("3-control-panel", wait=5)
    if os.path.exists(openshell.EXE):                # Open-Shell's own switch opens its menu
        subprocess.Popen([openshell.EXE, "-toggle"])
    else:
        key(0x5B); key(0x5B, True)                   # Windows key -> Start menu
    shot("4-start-menu", wait=3)
    key(0x1B); key(0x1B, True)

    # ---------------------------------------------------------- Undo
    problems.clear()
    took = press(lambda: on_main(app.undo_now))
    say("undo took %s; status: %r  problems: %s" % ("%.1fs" % took if took else "too long",
                                                   on_main(lambda: app.status.cget("text")), problems))
    restored = state()
    say("restored:", restored)
    check("Undo finished without problems", took is not None and not problems, problems)
    for k in ("TaskbarAl", "SkinW7", "MenuStyle", "StartButton", "desktop_icon", "wallpaper",
              "wallpaper_style", "window_color", "accent"):
        check("Undo restored " + k, restored[k] == before[k], (before[k], restored[k]))
    check("Undo removed taskbar styles", restored["tb_mark"] != "// Easy Theme Creator", restored["tb_mark"])
    check("Undo removed explorer styles", restored["ex_mark"] != "// Easy Theme Creator", restored["ex_mark"])
    shot("5-after-undo", wait=6)

    # ---------------------------------------------------------- left on for the uninstaller
    # Friends usually uninstall with the theme still on: Apply again and leave it, so the
    # uninstaller's own Undo (launch.pyw --undo) has to put the old look back (auto-test checks).
    problems.clear()
    took = press(lambda: on_main(app.apply_now))
    unexpected = [p for p in problems if not (restart_pending and p[0] == "Windows" and "restart" in p[1])]
    check("second Apply, left on for the uninstall test", took is not None and not unexpected, unexpected)
  except Exception:
    say("CRASH:\n" + traceback.format_exc())
    fails.append("crash")
  finally:
    app.inbox.put(root.quit)                         # ends mainloop() below


if not fails:
    try:
        # The app runs its real main loop (its background threads need it); the test steps
        # run in their own thread and touch the window only through on_main().
        root.after(500, threading.Thread(target=body, daemon=True).start)
        root.mainloop()
        root.destroy()
    except Exception:
        say("CRASH:\n" + traceback.format_exc())
        fails.append("crash")
say("RESULT:", "ALL PASSED" if not fails else "%d FAILED: %s" % (len(fails), fails))
log.close()
