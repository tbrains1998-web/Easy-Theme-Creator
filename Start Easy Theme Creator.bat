@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python is not installed. Get it from https://www.python.org/downloads/ ^(tick "Add to PATH"^). & pause & exit /b)
python -m pip install --quiet pillow numpy pefile
start "" pythonw launch.pyw
