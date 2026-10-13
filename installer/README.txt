EASY THEME CREATOR 2.0
======================

Pick a picture and all of Windows changes to match it: window skin, title-bar
buttons, taskbar, Start button, Explorer, folder and drive icons, Control Panel,
scrollbars, wallpaper, colors, mouse pointers, desktop icons and (optionally)
sounds and a sci-fi font. Everything comes in the picture's own colors.

WHAT THIS SETUP INSTALLS
------------------------
* Easy Theme Creator itself (with its own private copy of Python, so you
  don't need to install anything else).
* SecureUxTheme (free, open source, by namazso) - Windows only loads its own
  built-in skins; this lets it load the skin the app makes. Needed for the
  "Windows", "Metal buttons" and "Armor Explorer" options.
* Windhawk (free, open source, by Ramen Software / m417z) with three of its
  mods, all used only inside Explorer:
    - Windows 11 Taskbar Styler: the metal taskbar and the Alien Start button
    - Windows 11 File Explorer Styler: armor plates and red buttons in Explorer
    - Resource Redirect: turns Control Panel's white side pane dark
* Open-Shell (free, open source) - only its Start menu part: the Windows 7
  Start menu, dressed in the app's own "armor" skin.
Everything is free - no trials, nothing to buy.

You can untick any of the helpers on the next pages.

HOW TO USE
----------
1. If SecureUxTheme was just installed, restart your PC first.
2. Open Easy Theme Creator and click "Pick a picture".
3. Click the color you like best (right-click a color to change it).
4. Switch off anything you don't want changed (green = on).
5. Click "Apply" at the top. Your screen blinks while Explorer restarts.
6. Changed your mind? Click "Undo" - it puts back exactly how Windows looked
   before the first Apply.

"Sci-fi font" changes the font for file names, menus and the status bar in all
of Windows, so it is off by default. After applying it, sign out and back in.

GOOD TO KNOW
------------
* Windows may say "Windows protected your PC" because this setup isn't signed.
  Click "More info", then "Run anyway".
* Some antivirus programs flag theme patchers like SecureUxTheme. It's the
  well-known open-source tool from github.com/namazso/SecureUxTheme.
* The setup makes a System Restore point first, if you leave that ticked.
* Uninstall from Settings > Apps. It puts your old Windows look back first
  (just like pressing "Undo"). SecureUxTheme, Windhawk and Open-Shell stay
  installed; remove them from Settings > Apps too if you want them gone.
* Windows 11, 64-bit. (On Windows 10 everything works except the taskbar,
  Start button and Explorer looks, which need Windows 11.)

CREDITS AND LICENSES
--------------------
The "licenses" folder next to the app has every license. In short:
* SecureUxTheme - LGPL-2.1 - https://github.com/namazso/SecureUxTheme
* Windhawk - GPL-3.0 - https://github.com/ramensoftware/windhawk
* Windhawk mods (Resource Redirect, Windows 11 Taskbar Styler, Windows 11
  File Explorer Styler) - GPL-3.0 - https://github.com/ramensoftware/windhawk-mods
  (their source code is installed with them, in C:\ProgramData\Windhawk\ModsSource)
* Open-Shell - MIT - https://github.com/Open-Shell/Open-Shell-Menu (the armor
  skin is made from its Midnight skin)
* Orbitron font - SIL Open Font License - The League of Moveable Type
* Python - PSF License; NumPy - BSD; Pillow - MIT-CMU; pefile - MIT
