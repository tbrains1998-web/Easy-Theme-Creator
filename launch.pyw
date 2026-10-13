"""Start Easy Theme Creator without a console window. If something it needs is
missing, show a message box instead of failing silently."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)


def tell(text):
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, text, "Easy Theme Creator", 0x10)


missing = []
for module, package in (("PIL", "pillow"), ("numpy", "numpy"), ("pefile", "pefile")):
    try:
        __import__(module)
    except ImportError:
        missing.append(package)
if missing:
    tell("Some parts are missing: %s\n\nOpen a Command Prompt and run:\n"
         "python -m pip install %s" % (", ".join(missing), " ".join(missing)))
    sys.exit(1)

try:
    import runpy
    sys.argv = [os.path.join(HERE, "easy_theme_creator.py")] + sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name="__main__")
except Exception:
    log = os.path.join(os.environ.get("LOCALAPPDATA", HERE), "EasyThemeCreator", "error.txt")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    tell("Easy Theme Creator ran into a problem and had to close.\n\nDetails were saved to:\n" + log)
