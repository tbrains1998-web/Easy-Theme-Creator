"""Easy Theme Creator: pick a picture, and all of Windows changes to match it.

Changes (each can be switched off): window skin, folder icons, Explorer /
taskbar / Start layout, wallpaper, colors, desktop icons, mouse pointers and
sounds. Undo puts everything back the way it was before the first Apply.
"""
import ctypes
import ctypes.wintypes
import os
import subprocess
import sys
import queue
import shutil
import threading
import time

_tcl = os.path.join(sys.prefix, "tcl")
if os.path.isdir(_tcl):
    os.environ.setdefault("TCL_LIBRARY", os.path.join(_tcl, "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", os.path.join(_tcl, "tk8.6"))

import tkinter as tk  # noqa: E402
from tkinter import colorchooser, filedialog, messagebox, ttk  # noqa: E402

from PIL import Image, ImageTk  # noqa: E402

import cpl_panes  # noqa: E402
import openshell  # noqa: E402
import folders  # noqa: E402
import layout  # noqa: E402
import preview  # noqa: E402
import scifont  # noqa: E402
import shell_icons  # noqa: E402
import skin  # noqa: E402
import standard_colors  # noqa: E402
import taskbar  # noqa: E402
import theme_core  # noqa: E402
import undo  # noqa: E402
import windows_apply  # noqa: E402
import xaml_styles  # noqa: E402

THEMES_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                          "Microsoft", "Windows", "Themes")
HOME = undo.HOME
BG, PANEL, FG, DIM = "#16161a", "#24242b", "#f2f2f2", "#9a9aa5"
FONT = ("Segoe UI", 11)
BIG = ("Segoe UI", 15, "bold")


def current_wallpaper():
    buf = ctypes.create_unicode_buffer(520)
    ctypes.windll.user32.SystemParametersInfoW(0x73, 520, buf, 0)
    return buf.value


def restart_explorer(clear_icon_cache=True):
    """Restart Explorer. With clear_icon_cache, Windows' cached icon pictures are
    dropped while Explorer is stopped, so new folder / drive / place icons show
    instead of stale ones (the cache files are rebuilt automatically)."""
    import glob
    hidden = subprocess.CREATE_NO_WINDOW
    # Started from the Windows folder: Explorer keeps its start folder as long as it runs,
    # and the app's own folder could then never be removed by the uninstaller.
    neutral = os.environ.get("SystemRoot", r"C:\Windows")
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], creationflags=hidden,
                       capture_output=True, timeout=30)
        if clear_icon_cache:
            time.sleep(1)
            cache = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Explorer")
            for f in glob.glob(os.path.join(cache, "iconcache_*.db")) + \
                    [os.path.join(os.environ.get("LOCALAPPDATA", ""), "IconCache.db")]:
                try:
                    os.remove(f)
                except OSError:
                    pass                          # still locked by another process: skip it
    finally:
        subprocess.Popen(["explorer.exe"], cwd=neutral)       # whatever happened: a shell again
        try:
            subprocess.Popen(["ie4uinit.exe", "-show"], creationflags=hidden, cwd=neutral)
        except OSError:
            pass


def wait_for_taskbar(timeout=20):
    """Wait until Explorer's taskbar window exists again after a restart."""
    end = time.time() + timeout
    while time.time() < end:
        if ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None):
            time.sleep(2)
            return True
        time.sleep(0.5)
    return False


def _reg_value(path, name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def taskbar_snapshot():
    """Picture of the bottom of the main screen (where the taskbar is)."""
    from PIL import ImageGrab
    u = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    hwnd = u.FindWindowW("Shell_TrayWnd", None)
    if not hwnd or not u.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom), all_screens=True)


def verify(on, accent):
    """Read back what Apply should have left behind. Returns [(part, problem)]."""
    problems = []
    if on.get("taskbar") and xaml_styles.ours(xaml_styles.TASKBAR_MOD):
        if _reg_value(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "ColorPrevalence"):
            problems.append(("Taskbar", "Windows still paints the accent color on the taskbar"))
        shot = taskbar_snapshot()
        if shot is not None:
            import numpy as np
            a = np.asarray(shot.convert("RGB")).astype(int)
            body = a[a.shape[0] // 2:]                       # lower half, away from the top line
            near = (abs(body - np.array(accent)).sum(-1) < 60).mean()
            dark = (body.mean(-1) < 60).mean()
            if near > 0.5 or dark < 0.4:
                problems.append(("Taskbar", "the taskbar on screen doesn't look like the metal bar yet"))
    if on.get("colors") and _reg_value(r"Software\Microsoft\Windows\DWM", "ColorPrevalence"):
        problems.append(("Colors", "title bars are still painted in the accent color"))
    return problems


def work_area():
    """Usable screen area (taskbar excluded) in this window's pixels: (w, h, x, y)."""
    r = ctypes.wintypes.RECT()
    if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0):   # SPI_GETWORKAREA
        return r.right - r.left, r.bottom - r.top, r.left, r.top
    return 1280, 720, 0, 0


def _rgb(hex_color):
    return theme_core._rgb(hex_color)


def log_error():
    """Note the error being handled (with its traceback) in error.txt next to the undo
    snapshot - the app runs without a console."""
    import traceback
    try:
        os.makedirs(HOME, exist_ok=True)
        with open(os.path.join(HOME, "error.txt"), "a", encoding="utf-8") as f:
            f.write("%s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), traceback.format_exc()))
    except OSError:
        pass


class App:
    def __init__(self, root):
        self.root = root
        root.title("Easy Theme Creator")
        root.configure(bg=BG)
        icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
        if os.path.exists(icon):
            root.iconbitmap(icon)
        self.picture = None
        self.image_path = None
        self.colors = []
        self.accent = "#d82c2c"
        self.dark = tk.BooleanVar(value=True)
        self.look = tk.StringVar(value="Keep")
        self.parts = {}
        self.busy = False
        self._notes = []                # side remarks for the status line when Apply / Undo end
        self.inbox = queue.Queue()      # background work hands results to the window here
        root.protocol("WM_DELETE_WINDOW", self.close)

        # Fit the screen: the window opens at a size that fits the usable screen area
        # (taskbar excluded, at any display scaling), small screens get a compact layout,
        # the switches wrap and stay pinned to the bottom, and the preview takes the rest.
        work_w, work_h, work_x, work_y = work_area()
        self.compact = work_h < 820 or work_w < 1150
        big = (BIG[0], 12 if self.compact else BIG[1], "bold")
        font = (FONT[0], 10 if self.compact else FONT[1])
        pad = 10 if self.compact else 16
        self.font = font

        top = tk.Frame(root, bg=BG)
        top.pack(side="top", fill="x", padx=pad, pady=(pad - 2, 4))
        self.pick_btn = tk.Button(top, text="🖼  Pick a picture", font=big, bg="#3a3a46", fg=FG,
                                  activebackground="#50505e", relief="flat", padx=14 if self.compact else 18,
                                  pady=6 if self.compact else 8, command=self.pick_picture)
        self.pick_btn.pack(side="left")
        # Apply / Undo are packed before the swatches, so they keep their room on narrow windows.
        right = tk.Frame(top, bg=BG)
        right.pack(side="right")
        self.apply_btn = tk.Button(right, text="✔  Apply", font=big, bg="#2d7d46", fg="white",
                                   activebackground="#3a9a58", relief="flat", padx=22 if self.compact else 30,
                                   pady=6 if self.compact else 8, command=self.apply_now)
        self.apply_btn.pack(side="left")
        self.undo_btn = tk.Button(right, text="↩  Undo", font=big, bg="#7d2d2d", fg="white",
                                  activebackground="#9a3a3a", relief="flat", padx=18 if self.compact else 24,
                                  pady=6 if self.compact else 8, command=self.undo_now)
        self.undo_btn.pack(side="left", padx=(8, 12))
        if standard_colors.available():        # a program that mixes its own and Windows' colours
            tk.Button(right, text="🩹 Fix an app", font=font, bg=PANEL, fg=FG, activebackground="#3a3a46",
                      activeforeground=FG, relief="flat", padx=10, pady=4,
                      command=self.fix_app).pack(side="left", padx=(0, 12))
        tk.Checkbutton(right, text="🌙 Dark", variable=self.dark, command=self.refresh, font=font,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG).pack(side="left")
        if self.compact:                     # colors get their own row on small screens
            self.swatches = tk.Frame(root, bg=BG)
            self.swatches.pack(side="top", anchor="w", padx=pad, pady=(2, 0))
        else:
            self.swatches = tk.Frame(top, bg=BG)
            self.swatches.pack(side="left", padx=20)

        self.status = tk.Label(root, text="", font=font, bg=BG, fg=DIM)
        self.status.pack(side="top", fill="x", padx=pad + 2)
        # Moving bar while Apply / Undo work (they can take a minute): shown only when busy.
        bar_style = ttk.Style(root)
        bar_style.theme_use("clam")
        bar_style.configure("Busy.Horizontal.TProgressbar", troughcolor=PANEL, background="#d82c2c",
                            bordercolor=BG, lightcolor="#d82c2c", darkcolor="#d82c2c")
        self.busy_bar = ttk.Progressbar(root, mode="indeterminate", length=420,
                                        style="Busy.Horizontal.TProgressbar")

        # Bottom first (pack order): the switches always stay visible.
        tk.Frame(root, bg=BG, height=pad).pack(side="bottom")
        self.chips = tk.Frame(root, bg=BG)
        self.chips.pack(side="bottom", fill="x", padx=pad - 4)
        tk.Label(root, text="Change", font=font, bg=BG, fg=DIM).pack(side="bottom", anchor="w",
                                                                     padx=pad + 2, pady=(6, 0))
        options = [("🪟 Windows", "skin"), ("⚙ Metal buttons", "premium"), ("▬ Metal taskbar", "taskbar"),
                   ("👽 Alien Start", "orb"), ("🪟 Win7 Start menu", "startmenu"),
                   ("🌑 Dark classic apps", "syscolors"), ("🛡 Armor Explorer", "armor"),
                   ("🔤 Sci-fi font", "font"), ("📁 Folders", "folders"), ("🏞 Wallpaper", "wallpaper"),
                   ("🎨 Colors", "colors"), ("🖥 Desktop icons", "icons"),
                   ("🖱 Mouse", "pointers"), ("🔊 Sounds", "sounds")]
        self.chip_widgets = []
        for label, key in options:
            var = tk.BooleanVar(value=key not in ("sounds", "font"))   # font: all of Windows, opt-in
            if key in ("skin", "premium") and not skin.patcher_installed():
                var.set(False)
            if key == "startmenu" and not openshell.available():
                continue                                   # needs Open-Shell
            self.parts[key] = var
            self.chip_widgets.append(tk.Checkbutton(
                self.chips, text=label, variable=var, command=self.refresh, font=font,
                bg=PANEL, fg=FG, selectcolor="#2d6d46", activebackground=PANEL, activeforeground=FG,
                indicatoron=False, padx=10 if self.compact else 12, pady=4 if self.compact else 6,
                relief="flat", offrelief="flat", bd=0))
        self.chip_cols = 0
        self.chips.bind("<Configure>", lambda e: self.flow_chips(e.width))

        # The preview takes whatever room is left and is redrawn to fit it.
        self.preview_box = tk.Frame(root, bg=BG)
        self.preview_box.pack(side="top", fill="both", expand=True, padx=pad, pady=(4, 0))
        self.updating = tk.Label(self.preview_box, text="", font=font, bg=BG, fg=DIM)
        self.updating.pack(side="bottom")
        self.canvas = tk.Label(self.preview_box, bg=PANEL, fg=DIM, font=("Segoe UI", 14))
        self.canvas.pack(side="top", expand=True)
        self.preview_size = (560, 324)
        self._resize_job = None
        self.preview_box.bind("<Configure>", self.preview_box_resized)

        self.looks = tk.Frame(root, bg=BG)      # layout cards are gone (they were StartAllBack's)
        self.look_cards = {}

        # Open at a size that fits the screen, centered on the usable area.
        win_w = min(1100, work_w - 40)
        win_h = min(800, work_h - 60)
        root.geometry("%dx%d+%d+%d" % (win_w, win_h, work_x + (work_w - win_w) // 2,
                                       work_y + max(0, (work_h - win_h - 30) // 2)))
        root.minsize(min(640, work_w - 20), min(520, work_h - 40))
        self.update_undo()
        self.dark_title_bar()
        self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())   # for admin prompts
        self.poll()
        self.refresh()

    def flow_chips(self, width):
        """Lay the switches out in as many equal columns as fit, wrapping onto new rows."""
        if not self.chip_widgets or width < 50:
            return
        widest = max(w.winfo_reqwidth() for w in self.chip_widgets) + 8
        cols = max(1, min(len(self.chip_widgets), width // widest))
        if cols == self.chip_cols:
            return
        self.chip_cols = cols
        for c in range(len(self.chip_widgets)):
            self.chips.grid_columnconfigure(c, weight=1 if c < cols else 0, uniform="chip" if c < cols else "")
        for i, w in enumerate(self.chip_widgets):
            w.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="we")

    def preview_box_resized(self, event):
        """Fit the preview (760 x 440 mock-up) into the room it has; redraw when it changed."""
        avail_w = max(160, event.width - 8)
        avail_h = max(90, event.height - self.updating.winfo_reqheight() - 8)
        scale = min(avail_w / 760, avail_h / 440, 1.0)
        size = (int(760 * scale), int(440 * scale))
        if abs(size[0] - self.preview_size[0]) < 12:
            return
        self.preview_size = size
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(250, self.refresh)

    def dark_title_bar(self):
        """Dark window title bar to match the app (Windows 10 2004+ / 11)."""
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            on = ctypes.c_int(1)
            for attr in (20, 19):          # DWMWA_USE_IMMERSIVE_DARK_MODE (new, then old id)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), 4) == 0:
                    break
        except Exception:
            pass

    # ------------------------------------------------------------ picking

    def pick_picture(self, path=None):
        path = path or filedialog.askopenfilename(
            filetypes=[("Pictures", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if not path:
            return
        self.image_path = path
        self.picture = Image.open(path)
        self.picture.load()
        self.colors = theme_core.find_colors(path)
        self.accent = theme_core.pick_accent(self.colors)
        self.dark.set(theme_core.is_dark(path))
        self.draw_swatches()
        self.refresh()

    def dark_color(self):
        return min((_rgb(c) for c in self.colors), key=sum) if self.colors else (20, 20, 24)

    def draw_swatches(self):
        for w in self.swatches.winfo_children():
            w.destroy()
        for i, c in enumerate(self.colors):
            chosen = c == self.accent
            box = tk.Label(self.swatches, bg=c, width=4, height=2, cursor="hand2",
                           highlightthickness=4 if chosen else 0, highlightbackground="white")
            box.pack(side="left", padx=4)
            box.bind("<Button-1>", lambda e, c=c: self.choose(c))
            box.bind("<Button-3>", lambda e, i=i: self.change(i))

    def choose(self, color):
        self.accent = color
        self.draw_swatches()
        self.refresh()

    def change(self, i):
        new = colorchooser.askcolor(self.colors[i])[1]
        if new:
            if self.accent == self.colors[i]:
                self.accent = new
            self.colors[i] = new
            self.choose(self.accent)

    def pick_look(self, name):
        self.look.set(name)
        self.mark_look()
        self.refresh()

    def mark_look(self):
        for name, (border, pic, cap) in self.look_cards.items():
            chosen = name == self.look.get()
            border.config(bg=self.accent if chosen else BG)
            cap.config(bg=self.accent if chosen else PANEL, fg="white" if chosen else FG,
                       font=(FONT[0], FONT[1], "bold") if chosen else FONT)

    # ------------------------------------------------------------ live preview

    def poll(self):
        """Run what background threads queued (Tk may only be touched from here). One that
        fails is noted in error.txt; the others still run and polling always goes on."""
        try:
            while True:
                try:
                    fn = self.inbox.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn()
                except Exception:
                    log_error()
        finally:
            try:
                self.root.after(50, self.poll)
            except tk.TclError:
                pass                         # the window is gone

    def close(self):
        """The window's close button. Apply and Undo run in a background thread that ends
        with the app, so closing half way would leave Windows half changed: not while busy."""
        if self.busy:
            messagebox.showinfo("Easy Theme Creator", "Please wait a moment - Windows is still being "
                                "changed.\nYou can close the window when it's done.", parent=self.root)
            return
        self.root.destroy()

    def later(self, fn):
        self.inbox.put(fn)

    def refresh(self):
        """Re-render the preview (in the background) from the real theme parts."""
        self.render_id = getattr(self, "render_id", 0) + 1
        job = self.render_id
        self.updating.config(text="\u23f3 updating\u2026")
        settings = dict(accent=self.accent, dark=self.dark.get(), look=self.look.get(),
                        on={k: v.get() for k, v in self.parts.items()},
                        picture=self.picture, dark_color=self.dark_color(), size=self.preview_size)
        threading.Thread(target=self._render, args=(job, settings), daemon=True).start()

    def _background(self, s):
        if s["picture"] is not None and s["on"]["wallpaper"]:
            return s["picture"]
        if not hasattr(self, "_wall"):
            try:
                self._wall = Image.open(current_wallpaper())
                self._wall.load()
            except Exception:
                self._wall = Image.linear_gradient("L").resize((760, 440)).convert("RGB")
        return self._wall

    def _render(self, job, s):
        try:
            on, acc = s["on"], _rgb(s["accent"])
            bg = self._background(s)
            if s["picture"] is None:            # nothing chosen yet: show Windows as it is
                colors = preview.stock_colors(s["dark"])
                icons, tb = None, None
            else:
                colors = preview.skin_colors(s["accent"], s["dark"]) if on["skin"] \
                    else preview.stock_colors(s["dark"])
                if on["colors"] and not on["skin"]:
                    colors["accent"] = colors["select"] = acc
                key = (s["accent"], s["dark_color"])
                if on["folders"]:
                    if getattr(self, "_icons_key", None) != key:
                        self._icons = preview.folder_icons(acc, s["dark_color"])
                        self._icons_key = key
                    icons = self._icons
                else:
                    icons = None
                tb = "metal" if on.get("taskbar") else (preview._mix((14, 14, 16), acc, 0.08) if on["colors"] else None)
            if job != self.render_id:
                return
            look = "Modern" if s["look"] == "Keep" else s["look"]
            prem = s["picture"] is not None and on["skin"] and on["premium"]
            orb = s["picture"] is not None and on.get("orb")
            big = preview.mockup(bg, colors, look, icons, tb, prem, orb).resize(s["size"], Image.LANCZOS)
            thumbs = {}
            for name in self.look_cards:
                lk = "Modern" if name == "Keep" else name
                thumbs[name] = preview.mockup(bg, colors, lk, icons, tb, prem, orb).resize((150, 87), Image.LANCZOS)
            if job == self.render_id:
                self.later(lambda: self._show(job, big, thumbs))
        except Exception as e:
            msg = str(e)
            self.later(lambda: self.updating.config(text="preview problem: " + msg))

    def _show(self, job, big, thumbs):
        if job != self.render_id:
            return
        self.photo = ImageTk.PhotoImage(big)
        self.canvas.config(image=self.photo, text="")
        self.card_photos = {}
        for name, img in thumbs.items():
            self.card_photos[name] = ImageTk.PhotoImage(img)
            self.look_cards[name][1].config(image=self.card_photos[name], width=150, height=87)
        self.mark_look()
        self.updating.config(text="" if self.picture is not None else "\U0001f446 Pick a picture to start")

    # ------------------------------------------------------------ apply / undo

    def say(self, text):
        self.later(lambda: self.status.config(text=text))

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.apply_btn, self.undo_btn, self.pick_btn):
            b.config(state=state)
        self.root.config(cursor="watch" if busy else "")
        if busy:
            self.busy_bar.configure(style="Busy.Horizontal.TProgressbar")
            ttk.Style(self.root).configure("Busy.Horizontal.TProgressbar", background=self.accent,
                                           lightcolor=self.accent, darkcolor=self.accent)
            self.busy_bar.pack(after=self.status, pady=(2, 4))
            self.busy_bar.start(12)
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()

    # ------------------------------------------------------------ fix an app

    def fix_app(self):
        """Programs that keep Windows' standard colours: show the list, add one by
        clicking its window, or remove one. Each change counts from the program's
        next start."""
        win = tk.Toplevel(self.root)
        win.title("Fix an app that looks wrong")
        win.configure(bg=BG)
        win.transient(self.root)
        tk.Label(win, text="Some programs set a few colours themselves and take the rest from Windows,\n"
                           "so a dark theme can make their text unreadable. Programs on this list get\n"
                           "Windows' normal colours instead, from the next time they start.",
                 font=self.font, bg=BG, fg=FG, justify="left").pack(anchor="w", padx=16, pady=(14, 8))
        box = tk.Listbox(win, font=self.font, bg=PANEL, fg=FG, selectbackground=self.accent,
                         selectforeground="white", relief="flat", height=8, width=48)
        box.pack(fill="both", expand=True, padx=16)
        note = tk.Label(win, text="", font=self.font, bg=BG, fg=DIM)
        note.pack(anchor="w", padx=16, pady=(6, 0))
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x", padx=16, pady=12)

        def refresh():
            box.delete(0, "end")
            for n in standard_colors.apps():
                box.insert("end", n)

        def picked(result):
            try:
                if not win.winfo_exists():            # closed while the user was picking
                    return
            except tk.TclError:
                return
            pick_btn.config(state="normal")
            if not result:
                note.config(text="No window picked.")
                return
            exe, title, _pid, path = (tuple(result) + (None,))[:4]    # path: the program's full path
            skips = getattr(standard_colors, "windhawk_skips", None)
            try:
                skipped = bool(path and skips and skips(path))
            except Exception:
                skipped = False
            if skipped:
                note.config(text="Not added: Windhawk leaves %s alone." % exe)
                messagebox.showinfo("Fix an app", "Windhawk is set to leave programs in game folders alone, "
                                    'so "Fix an app" can\'t reach "%s" (%s).\n\nIt was not added to the list.'
                                    % (title or exe, exe), parent=win)
                return
            if not messagebox.askyesno("Fix an app", 'Give "%s" (%s) Windows\' standard colours?\n\n'
                                       "It looks normal again the next time it starts." % (title or exe, exe),
                                       parent=win):
                note.config(text="")
                return
            try:
                if not standard_colors.writable():
                    note.config(text="Windows will ask once for permission…")
                    xaml_styles.setup_access(self.hwnd)
                standard_colors.add(exe)
            except Exception as e:
                messagebox.showwarning("Fix an app", str(e), parent=win)
                return
            refresh()
            note.config(text="Added. Close %s and open it again." % exe)

        def pick():
            pick_btn.config(state="disabled")
            note.config(text="Click the window that looks wrong (you have 15 seconds)…")
            win.update_idletasks()
            threading.Thread(target=lambda: self.later(
                lambda r=standard_colors.pick_window(15, os.getpid()): picked(r)), daemon=True).start()

        def drop():
            sel = box.curselection()
            if not sel:
                return
            exe = box.get(sel[0])
            try:
                if not standard_colors.writable():
                    xaml_styles.setup_access(self.hwnd)
                standard_colors.remove(exe)
            except Exception as e:
                messagebox.showwarning("Fix an app", str(e), parent=win)
                return
            refresh()
            note.config(text="Removed. %s gets the theme again the next time it starts." % exe)

        pick_btn = tk.Button(row, text="➕ Click a window to add it", font=self.font, bg="#2d7d46", fg="white",
                             activebackground="#3a9a58", relief="flat", padx=10, pady=4, command=pick)
        pick_btn.pack(side="left")
        tk.Button(row, text="Remove", font=self.font, bg=PANEL, fg=FG, activebackground="#3a3a46",
                  activeforeground=FG, relief="flat", padx=10, pady=4, command=drop).pack(side="left", padx=8)
        tk.Button(row, text="Close", font=self.font, bg=PANEL, fg=FG, activebackground="#3a3a46",
                  activeforeground=FG, relief="flat", padx=10, pady=4, command=win.destroy).pack(side="right")
        refresh()
        try:
            self.dark_title_bar_for(win)
        except Exception:
            pass

    def dark_title_bar_for(self, win):
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        on = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), 4) == 0:
                break

    def update_undo(self):
        self.undo_btn.config(state="normal" if undo.has_snapshot() and not self.busy else "disabled")

    def apply_now(self):
        if self.picture is None:
            self.status.config(text="👆 Pick a picture first")
            return
        # Everything the user chose, read once here on the window's thread: Apply runs in
        # the background, and a colour or switch changed meanwhile must not mix in half way.
        choice = {"on": {k: v.get() for k, v in self.parts.items()}, "accent": self.accent,
                  "dark": self.dark.get(), "dark_color": self.dark_color(),
                  "image_path": self.image_path, "look": self.look.get()}
        self.set_busy(True)
        threading.Thread(target=self._apply, args=(choice,), daemon=True).start()

    def _apply(self, choice):
        on, accent, dark = choice["on"], choice["accent"], choice["dark"]
        acc, dark_color = _rgb(accent), choice["dark_color"]
        failed, notes = [], []
        font_changed = False
        skin_later = None
        loaded = []                                   # skins this Apply switched Windows to
        state = {}

        def load_skin(style):
            before = skin.current_style()
            skin.use(style)
            loaded.append(style)
            # older skins of ours go; `previous` lets the one that was on go too when it
            # still lies in the pre-2.4 folder layout (never Undo's own target)
            skin.cleanup([style, state.get("skin")], previous=[before, state.get("stale_skin")])
            # keep Windows' "current theme" on this skin, or Settings puts Aero back
            if "current_theme_before" not in state:
                now = windows_apply.current_theme()
                state["current_theme_before"] = None if undo.theme_is_ours(now) else now
                undo.save(state)
            windows_apply.register_theme(theme["theme"], style)

        def drop_stray_skins():
            # a build or load that failed must not leave its 2-5 MB folder behind
            try:
                skin.cleanup([skin.current_style(), state.get("skin")] + loaded)
            except Exception:
                pass

        try:
            self.say("Saving your current look…")
            state = undo.take(skin.current_style(), current_wallpaper(),
                              layout.backup if layout.available() else (lambda p: None))
            # icon keys Desktop icons / Folders write (Desktop icon settings' own ones too)
            undo.remember(state, undo.EXPLORER_ICON_KEYS + shell_icons.registry_keys())
            name = theme_core.safe_name(theme_core.nice_name(choice["image_path"]))
            accent_rgba = acc + (255,)
            # "Dark classic apps" needs Windows' own dark designs of the classic controls in
            # the stock skin; without them the dark palette means light text on light boxes.
            classic = bool(on.get("syscolors")) and dark
            if classic and hasattr(skin, "supports_classic_dark"):
                try:
                    if not skin.supports_classic_dark():
                        classic = False
                        notes.append("(Dark classic apps left out: this Windows has no dark "
                                     "designs for classic controls.)")
                except Exception:
                    pass

            self.say("Making the theme…")
            theme = theme_core.make_theme(name, choice["image_path"], accent, dark,
                                          THEMES_DIR, pointers=on["pointers"],
                                          icons=on["icons"], sounds=on["sounds"])
            steps = []
            if on["wallpaper"]:
                steps.append(("Wallpaper", lambda: windows_apply.wallpaper(theme["wallpaper"])))
            if on["colors"]:
                # accent only as thin highlights: title bars and taskbar stay black
                steps.append(("Colors", lambda: windows_apply.colors(accent, dark, False)))
            if theme["pointers"]:
                steps.append(("Mouse", lambda: windows_apply.pointers(theme["name"], theme["pointers"])))
            if theme["icons"]:
                steps.append(("Desktop icons", lambda: windows_apply.icons(theme["icons"])))
            if theme["sounds"]:
                steps.append(("Sounds", lambda: windows_apply.sounds(theme["sounds"])))
            for part, step in steps:
                self.say("Changing %s…" % part.lower())
                try:
                    step()
                except Exception as e:
                    failed.append((part, str(e)))

            if on["skin"] and skin.patcher_needs_restart():
                failed.append(("Windows", "restart your PC once so the window skin can load "
                                          "(SecureUxTheme was just installed), then press Apply again"))
            elif on["skin"]:
                self.say("Painting the windows…")
                try:
                    style = skin.build(name.replace(" ", ""), accent,
                                       art="premium" if on["premium"] else "color",
                                       dark=dark,
                                       armor=bool(on.get("armor")) and dark,
                                       classic_dark=classic)
                    try:
                        load_skin(style)
                    except OSError as e:
                        # The first skin after a fresh sign-in can be refused (0x9007000E)
                        # until the rest of Apply (dark mode, colours, Explorer restart) is
                        # done - a second Apply always took it. So: once more at the end.
                        if "0x9007000E" not in str(e):
                            raise
                        skin_later = style
                except Exception as e:
                    failed.append(("Windows", str(e)))
                    drop_stray_skins()

            if on["folders"]:
                self.say("Drawing folder and drive icons…")
                try:
                    # one fixed folder for every generated icon (theme folders get cleaned up)
                    assets = shell_icons.new_assets_dir()
                    icons = folders.make_icons(assets, accent_rgba, dark_color)
                    # Folders the snapshot doesn't have yet are backed up into it (and the
                    # snapshot saved) right before they change; the others keep their first
                    # backup. So Undo covers every folder ever themed, with one backup each.
                    state["folders"] = state.get("folders") or []
                    folders.apply(icons, os.path.join(undo.SNAP, "folders"), state["folders"],
                                  on_backup=lambda: undo.save(state))
                    undo.remember(state, shell_icons.registry_keys())
                    shell_icons.apply(shell_icons.make(assets, accent_rgba, dark_color), icons)
                    shell_icons.cleanup(assets)
                except Exception as e:
                    failed.append(("Folders", str(e)))

            # Layout first: StartAllBack's ready-made looks reset its taskbar style and Start button.
            look = choice["look"]
            if look != "Keep":
                self.say("Changing the layout…")
                try:
                    state.setdefault("look_before", "Modern")
                    state["layout_changed"] = True
                    undo.save(state)
                    layout.set_look(look)
                except Exception as e:
                    failed.append(("Layout", str(e)))
            # Taskbar, Start button and Explorer bars: Windhawk's free XAML stylers read
            # their settings when Explorer restarts below.
            if on.get("taskbar") or on.get("orb") or on.get("armor") or xaml_styles.ours(xaml_styles.TASKBAR_MOD) \
                    or xaml_styles.ours(xaml_styles.EXPLORER_MOD):
                self.say("Dressing the taskbar and Explorer…")
                try:
                    # The user's own styler settings, once, before our first styles replace them.
                    if "xaml_before" not in state and hasattr(xaml_styles, "settings_snapshot"):
                        state["xaml_before"] = xaml_styles.settings_snapshot()
                    state["xaml"] = True
                    undo.save(state)
                    mods = [m for m in (xaml_styles.TASKBAR_MOD, xaml_styles.EXPLORER_MOD)
                            if xaml_styles.mod_installed(m) and not xaml_styles.writable(m)]
                    if mods:
                        self.say("Windows will ask once for permission to change Windhawk's styles…")
                        xaml_styles.setup_access(self.hwnd)
                    failed += xaml_styles.apply(acc, metal=on.get("taskbar"), orb=on.get("orb"),
                                                explorer=bool(on.get("armor")) and dark)
                    if on.get("taskbar"):
                        if "taskbar_align_before" not in state:
                            state["taskbar_align_before"] = _reg_value(xaml_styles.ADVANCED, "TaskbarAl")
                        state["taskbar_aligned"] = True
                        undo.save(state)
                        xaml_styles.left_align()              # Windows 7: icons on the left
                except Exception as e:
                    failed.append(("Taskbar", str(e)))
            if on.get("font"):
                self.say("Changing the font…")
                try:
                    if "fonts_before" not in state and not scifont.in_use():
                        state["fonts_before"] = scifont.current()
                        undo.save(state)
                    scifont.apply()
                    font_changed = True
                except Exception as e:
                    failed.append(("Sci-fi font", str(e)))
            elif state.get("fonts_before") and scifont.in_use():
                try:
                    scifont.restore(state["fonts_before"])
                    del state["fonts_before"]
                    undo.save(state)
                except Exception as e:
                    failed.append(("Sci-fi font", str(e)))
            # Control Panel's side panes are pictures inside shell32, not part of the skin;
            # Windhawk's Resource Redirect swaps them when Explorer restarts below.
            # With Armor Explorer the same swap also serves Explorer's folder layouts with
            # Windows' details pane along the bottom (Windows 7 style), where the skin's
            # emblem panel is painted.
            bottom = bool(on.get("armor")) and dark
            try:
                if (on.get("syscolors") and dark) or bottom:
                    state["cpl_panes"] = True
                    undo.save(state)
                    cpl_panes.apply(details_bottom=bottom)
                    if bottom:                         # the panel shows with "Details pane" on
                        undo.remember(state, [cpl_panes.DETAILS_KEY_FULL])
                        cpl_panes.show_details_pane()
                else:
                    cpl_panes.undo()
            except Exception as e:
                failed.append(("Control Panel side pane", str(e)))
            # Windows 7 Start menu (Open-Shell, armor skin): it keeps settings in memory and
            # writes them back when it exits, so it is stopped first and started again with
            # the new Explorer - always, also when a step in between goes wrong.
            shell_stopped = openshell.available()
            if shell_stopped:
                try:
                    openshell.stop()
                except Exception as e:
                    failed.append(("Start menu", str(e)))
            try:
                if shell_stopped and on.get("startmenu"):
                    self.say("Dressing the Start menu…")
                    try:
                        snapshot = getattr(openshell, "_settings_snapshot", None)
                        if "openshell_before" not in state and snapshot:
                            state["openshell_before"] = undo.clean_openshell(snapshot())
                            undo.save(state)
                        before = openshell.apply(acc, self.hwnd)
                        state.setdefault("openshell_before", undo.clean_openshell(before))
                    except Exception as e:
                        failed.append(("Start menu", str(e)))
                undo.save(state)
                self.say("Refreshing the screen…")
                restart_explorer()
                wait_for_taskbar()
            finally:
                if shell_stopped:
                    try:
                        openshell.start()
                    except Exception as e:
                        failed.append(("Start menu", str(e)))

            if on["colors"]:
                try:
                    windows_apply.keep_bars_black()     # accent only as thin highlights
                except Exception as e:
                    failed.append(("Colors", str(e)))
            if classic:
                try:
                    undo.remember(state, [r"HKCU\Control Panel\Colors"])
                    windows_apply.dark_syscolors(accent)
                except Exception as e:
                    failed.append(("Classic apps", str(e)))
            else:
                # Dark classic colours left from an earlier Apply would stay with this look
                # (and the readable-text mod draws dialog text in them: light on light).
                try:
                    if windows_apply.our_palette_live():
                        failed += undo.restore_colors(state)
                except Exception as e:
                    failed.append(("Classic apps", str(e)))

            if skin_later:
                self.say("Painting the windows (second try)…")
                try:
                    load_skin(skin.fresh_copy(skin_later))     # cleanup drops the refused copy
                    undo.save(state)
                except Exception as e:
                    failed.append(("Windows", str(e)))
                    drop_stray_skins()

            self.say("Checking the result…")
            time.sleep(2)
            failed += verify(on, acc)
        except Exception as e:
            failed.append(("Theme", str(e)))
        done = "✔ Done! Your new theme is on."
        if font_changed:
            done += " Sign out and back in to see the new font everywhere."
        self._notes = notes
        self.later(lambda: self._done(failed, done))

    def undo_now(self):
        if not undo.has_snapshot():
            return
        self.set_busy(True)
        threading.Thread(target=self._undo, daemon=True).start()

    def _undo(self):
        # Every step runs on its own, so one that fails doesn't keep the rest (or Explorer's
        # restart) from happening; the snapshot stays until a run without any problem.
        # Nothing of ours ever comes back from the snapshot (undo.is_ours): Windows' own
        # skin, icons, sounds, pointers and colours take the place of such values.
        failed, notes = [], []
        try:
            state = undo.load()
            self.say("Putting your old look back…")
            failed += undo.restore_registry(state)
            try:
                # icon keys this snapshot doesn't cover (older ones): our icons out, Windows' back
                undo.heal_live(undo.ICON_KEYS + shell_icons.registry_keys())
            except Exception as e:
                failed.append(("Icons", str(e)))
            try:
                if windows_apply.our_palette_live():   # dark colours the snapshot never saved
                    windows_apply.default_syscolors()
                windows_apply.colors_reload()
                windows_apply.reload_syscolors()
            except Exception as e:
                failed.append(("Classic apps", str(e)))
            # The original picture if it is still there; otherwise the snapshot's copy, moved
            # out of the snapshot folder first (that folder is deleted after a good Undo).
            # "" = there was no picture (a plain colour). The old Fill / Fit / Tile comes back too.
            # (One of ours was replaced by Windows' own picture when the snapshot was read.)
            try:
                wp, copy = state.get("wallpaper"), state.get("wallpaper_copy")
                style, tile = state.get("wallpaper_style") or (None, None)
                if not (wp and os.path.exists(wp)) and copy and os.path.exists(copy):
                    wp = os.path.join(HOME, "restored-wallpaper" + os.path.splitext(copy)[1])
                    shutil.copyfile(copy, wp)
                if wp == "" or (wp and os.path.exists(wp)):
                    windows_apply.wallpaper(wp, style or "10", tile or "0")
            except Exception as e:
                failed.append(("Wallpaper", str(e)))
            ctypes.windll.user32.SystemParametersInfoW(0x57, 0, None, 3)   # reload pointers
            try:
                # Windows' "current theme" (Settings re-applies it): the old one, or Windows'
                # own when that was ours or is gone, so our skin can't come back from there.
                before = state.get("current_theme_before")
                if "current_theme_before" in state or undo.theme_is_ours(windows_apply.current_theme()):
                    if not (before and os.path.exists(os.path.expandvars(before))):
                        before = windows_apply.stock_theme()
                    windows_apply.restore_current_theme(before)
            except Exception as e:
                failed.append(("Windows", str(e)))
            try:
                old = state.get("skin")
                if old and os.path.exists(old) and not undo.is_ours(old):
                    skin.use(old)
                else:
                    skin.use_stock()                   # Windows' own aero
            except Exception as e:
                failed.append(("Windows", str(e)))
            if state.get("folders"):
                try:
                    folders.undo(state["folders"])
                except Exception as e:
                    failed.append(("Folders", str(e)))
            if state.get("layout_changed") or state.get("startallback_changed"):
                # StartAllBack era (1.x): its layout only comes back while StartAllBack is
                # installed. It is gone on most PCs now, which must not stop Undo for good.
                if not layout.available():
                    notes.append("(StartAllBack is gone, so its old layout was skipped.)")
                else:
                    try:
                        layout.restore(state.get("startallback"),
                                       state.get("look_before") if state.get("layout_changed") else None)
                    except Exception as e:
                        notes.append("(StartAllBack's old layout was skipped: %s)" % e)
            try:
                cpl_panes.undo()
            except Exception as e:
                failed.append(("Control Panel side pane", str(e)))
            if state.get("xaml"):
                try:
                    if state.get("taskbar_aligned"):
                        xaml_styles.restore_align(state.get("taskbar_align_before"))
                except Exception as e:
                    failed.append(("Taskbar", str(e)))
                try:
                    # the user's own styler settings from before Apply, where there were any
                    saved = state.get("xaml_before")
                    if saved and hasattr(xaml_styles, "restore_settings"):
                        xaml_styles.restore_settings(saved)
                except Exception as e:
                    failed.append(("Taskbar", str(e)))
                try:
                    xaml_styles.remove()                # whatever of ours is still there
                except Exception as e:
                    failed.append(("Taskbar", str(e)))
            if state.get("armor_explorer"):
                try:
                    layout.armor_explorer_undo(state.get("menus_before"))
                except Exception as e:
                    failed.append(("Armor Explorer", str(e)))
            if state.get("fonts_before"):
                try:
                    scifont.restore(state["fonts_before"])
                except Exception as e:
                    failed.append(("Sci-fi font", str(e)))
            # The "Fix an app" list stays: it is the user's own list, not part of the theme.
            shell_stopped = openshell.available()
            if shell_stopped:
                try:
                    openshell.stop()                   # it saves its settings on exit
                except Exception as e:
                    failed.append(("Start menu", str(e)))
            try:
                restart_explorer()
                # Only now, with Explorer (and the Open-Shell code inside it) gone, nothing can
                # write Open-Shell's in-memory settings back over the old ones.
                if "openshell_before" in state:
                    try:
                        openshell.restore(state["openshell_before"])
                    except Exception as e:
                        failed.append(("Start menu", str(e)))
            finally:
                if shell_stopped:                      # the Start menu comes back whatever happened
                    try:
                        wait_for_taskbar()
                        openshell.start()
                    except Exception as e:
                        failed.append(("Start menu", str(e)))
            if not failed:
                undo.forget()
        except Exception as e:
            failed.append(("Undo", str(e)))
        self._notes = notes
        self.later(lambda: self._done(failed, "↩ Your old look is back."))

    def _done(self, failed, ok_text):
        notes, self._notes = self._notes, []
        extra = (" " + " ".join(notes)) if notes else ""
        self.set_busy(False)
        self.update_undo()
        if failed:
            self.status.config(text="⚠ Some parts didn't change" + extra)
            messagebox.showwarning("Easy Theme Creator",
                                   "\n".join("• %s: %s" % f for f in failed))
        else:
            self.status.config(text=ok_text + extra)


def undo_silently():
    """`--undo`: put the old look back without showing the window (used by the
    uninstaller). Exit code 0 when there was nothing to undo or it worked."""
    if not undo.has_snapshot():
        return 0
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    # Undo's own callbacks run right away; the preview thread's are dropped (Tk may only
    # be used from this thread, and there is no window to draw into).
    app.later = lambda fn: fn() if threading.current_thread() is threading.main_thread() else None
    result = []
    app._done = lambda failed, ok: result.extend(failed)
    app._undo()
    root.destroy()
    return 1 if result else 0


def forget_open_after_restart():
    """Setup asks Windows (RunOnce) to open the app once after the restart SecureUxTheme
    needs. Explorer also runs RunOnce when it restarts (Apply does that), so once the
    app is open, by any route, the request is dropped - no surprise second window."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
                            0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, "EasyThemeCreator")
    except OSError:
        pass


if __name__ == "__main__":
    forget_open_after_restart()
    undo.drop_leftovers()                      # 2.3 and older: backups nothing ever read
    if "--undo" in sys.argv:
        sys.exit(undo_silently())
    root = tk.Tk()
    app = App(root)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):     # "Open with" / drag onto the app
        root.after(100, lambda: app.pick_picture(sys.argv[1]))
    root.mainloop()
