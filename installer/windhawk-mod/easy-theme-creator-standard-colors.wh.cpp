// ==WindhawkMod==
// @id              easy-theme-creator-standard-colors
// @name            Easy Theme Creator - readable text
// @description     Dialog text follows the theme (light on dark, dark on light); programs on the list get Windows' normal light colours and no window skin
// @version         1.1
// @author          tbrains1998-web
// @github          https://github.com/tbrains1998-web/Easy-Theme-Creator
// @include         *
// @exclude         windhawk.exe
// @compilerOptions -lgdi32 -luxtheme
// ==/WindhawkMod==

// ==WindhawkModReadme==
/*
# Easy Theme Creator - readable text

**Dialog text follows the theme.** On tab pages (a folder's Properties, most Control
Panel windows) Windows draws the labels in plain black whatever the theme says, so
on a dark theme they disappear. Where a page sets no text colour of its own, this
mod gives its labels the theme's text colour instead: light on a dark theme, dark on
a light one. Pages that choose their own colours keep them.

**Standard colours for chosen apps.** Some programs set a few of their own colours (a white text box, say) and take the
rest from Windows. With a dark theme those two halves stop matching and text becomes
unreadable. Put such a program on the list and, from its next start, it gets Windows'
normal light colours and draws its controls without the window skin - the way it was
designed - while everything else keeps the theme.

Easy Theme Creator fills this list for you ("Fix an app that looks wrong"); you can
also edit it here. Entries are executable names, e.g. `Notepad++.exe`.
*/
// ==/WindhawkModReadme==

// ==WindhawkModSettings==
/*
- apps: [""]
  $name: Programs
  $description: Executable names (e.g. "Steam Controller Xbox Mode.exe"), one per entry
*/
// ==/WindhawkModSettings==

#include <windows.h>
#include <uxtheme.h>
#include <wchar.h>

// Windows' default light palette, by COLOR_* index.
static const COLORREF g_stock[31] = {
    RGB(200, 200, 200),  // 0  SCROLLBAR
    RGB(0, 0, 0),        // 1  BACKGROUND (desktop)
    RGB(153, 180, 209),  // 2  ACTIVECAPTION
    RGB(191, 205, 219),  // 3  INACTIVECAPTION
    RGB(240, 240, 240),  // 4  MENU
    RGB(255, 255, 255),  // 5  WINDOW
    RGB(100, 100, 100),  // 6  WINDOWFRAME
    RGB(0, 0, 0),        // 7  MENUTEXT
    RGB(0, 0, 0),        // 8  WINDOWTEXT
    RGB(0, 0, 0),        // 9  CAPTIONTEXT
    RGB(180, 180, 180),  // 10 ACTIVEBORDER
    RGB(244, 247, 252),  // 11 INACTIVEBORDER
    RGB(171, 171, 171),  // 12 APPWORKSPACE
    RGB(0, 120, 215),    // 13 HIGHLIGHT
    RGB(255, 255, 255),  // 14 HIGHLIGHTTEXT
    RGB(240, 240, 240),  // 15 BTNFACE
    RGB(160, 160, 160),  // 16 BTNSHADOW
    RGB(109, 109, 109),  // 17 GRAYTEXT
    RGB(0, 0, 0),        // 18 BTNTEXT
    RGB(0, 0, 0),        // 19 INACTIVECAPTIONTEXT
    RGB(255, 255, 255),  // 20 BTNHIGHLIGHT
    RGB(105, 105, 105),  // 21 3DDKSHADOW
    RGB(227, 227, 227),  // 22 3DLIGHT
    RGB(0, 0, 0),        // 23 INFOTEXT
    RGB(255, 255, 225),  // 24 INFOBK
    RGB(0, 0, 0),        // 25 (unused)
    RGB(0, 102, 204),    // 26 HOTLIGHT
    RGB(185, 209, 234),  // 27 GRADIENTACTIVECAPTION
    RGB(215, 228, 242),  // 28 GRADIENTINACTIVECAPTION
    RGB(0, 120, 215),    // 29 MENUHILIGHT
    RGB(240, 240, 240),  // 30 MENUBAR
};
static HBRUSH g_brush[31];

using GetSysColor_t = DWORD(WINAPI*)(int);
static GetSysColor_t GetSysColor_orig;
static DWORD WINAPI GetSysColor_hook(int index) {
    if (index >= 0 && index < 31 && index != 25) {
        return g_stock[index];
    }
    return GetSysColor_orig(index);
}

using GetSysColorBrush_t = HBRUSH(WINAPI*)(int);
static GetSysColorBrush_t GetSysColorBrush_orig;
static HBRUSH WINAPI GetSysColorBrush_hook(int index) {
    if (index >= 0 && index < 31 && index != 25) {
        if (!g_brush[index]) {
            g_brush[index] = CreateSolidBrush(g_stock[index]);
        }
        return g_brush[index];
    }
    return GetSysColorBrush_orig(index);
}

// No window skin in this process: with no theme data the common controls draw
// themselves the classic way, from the (now standard) system colours.
using OpenThemeData_t = HTHEME(WINAPI*)(HWND, LPCWSTR);
static OpenThemeData_t OpenThemeData_orig;
static HTHEME WINAPI OpenThemeData_hook(HWND, LPCWSTR) { return NULL; }

using OpenThemeDataEx_t = HTHEME(WINAPI*)(HWND, LPCWSTR, DWORD);
static OpenThemeDataEx_t OpenThemeDataEx_orig;
static HTHEME WINAPI OpenThemeDataEx_hook(HWND, LPCWSTR, DWORD) { return NULL; }

using OpenThemeDataForDpi_t = HTHEME(WINAPI*)(HWND, LPCWSTR, UINT);
static OpenThemeDataForDpi_t OpenThemeDataForDpi_orig;
static HTHEME WINAPI OpenThemeDataForDpi_hook(HWND, LPCWSTR, UINT) { return NULL; }

using IsThemeActive_t = BOOL(WINAPI*)();
static IsThemeActive_t IsThemeActive_orig;
static BOOL WINAPI IsThemeActive_hook() { return FALSE; }

using IsAppThemed_t = BOOL(WINAPI*)();
static IsAppThemed_t IsAppThemed_orig;
static BOOL WINAPI IsAppThemed_hook() { return FALSE; }

// Dialog text. A tab page's WM_CTLCOLOR* answer comes from uxtheme's page texture:
// it returns the tab-body brush and makes the text background transparent but sets no
// text colour, so labels draw in GDI's default black - unreadable on a dark page. When
// that is what happened (texture on, background just made transparent, text colour
// untouched), the label gets the system text colour, which the theme sets: light on a
// dark theme, black on a light one. Pages that set their own colours are left alone.
using DefDlgProc_t = LRESULT(WINAPI*)(HWND, UINT, WPARAM, LPARAM);
static DefDlgProc_t DefDlgProcW_orig;
static DefDlgProc_t DefDlgProcA_orig;

static LRESULT DialogText(DefDlgProc_t orig, HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg != WM_CTLCOLORSTATIC && msg != WM_CTLCOLORBTN && msg != WM_CTLCOLORDLG) {
        return orig(hwnd, msg, wp, lp);
    }
    HDC dc = (HDC)wp;
    COLORREF text = GetTextColor(dc);
    int mode = GetBkMode(dc);
    LRESULT r = orig(hwnd, msg, wp, lp);
    if (r && mode != TRANSPARENT && GetBkMode(dc) == TRANSPARENT && GetTextColor(dc) == text &&
        IsThemeDialogTextureEnabled(hwnd)) {
        SetTextColor(dc, GetSysColor(COLOR_BTNTEXT));
    }
    return r;
}

static LRESULT WINAPI DefDlgProcW_hook(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    return DialogText(DefDlgProcW_orig, hwnd, msg, wp, lp);
}

static LRESULT WINAPI DefDlgProcA_hook(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    return DialogText(DefDlgProcA_orig, hwnd, msg, wp, lp);
}

static bool ThisProcessIsListed() {
    WCHAR path[MAX_PATH];
    DWORD n = GetModuleFileNameW(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return false;
    }
    const WCHAR* name = wcsrchr(path, L'\\');
    name = name ? name + 1 : path;
    for (int i = 0;; i++) {
        PCWSTR entry = Wh_GetStringSetting(L"apps[%d]", i);
        bool empty = !entry || !*entry;
        bool hit = !empty && _wcsicmp(entry, name) == 0;
        Wh_FreeStringSetting(entry);
        if (empty) {
            return false;
        }
        if (hit) {
            return true;
        }
    }
}

template <typename T>
static void Hook(HMODULE module, PCSTR name, void* hook, T* original) {
    void* target = (void*)GetProcAddress(module, name);
    if (target) {
        Wh_SetFunctionHook(target, hook, (void**)original);
    }
}

BOOL Wh_ModInit() {
    HMODULE user32 = GetModuleHandleW(L"user32.dll");
    if (!user32) {
        return FALSE;                                   // no windows in this program: unload
    }
    Hook(user32, "DefDlgProcW", (void*)DefDlgProcW_hook, &DefDlgProcW_orig);
    Hook(user32, "DefDlgProcA", (void*)DefDlgProcA_hook, &DefDlgProcA_orig);
    if (!ThisProcessIsListed()) {
        return TRUE;
    }
    Wh_Log(L"standard colours for this program");
    HMODULE uxtheme = LoadLibraryW(L"uxtheme.dll");
    if (!uxtheme) {
        return TRUE;
    }
    Hook(user32, "GetSysColor", (void*)GetSysColor_hook, &GetSysColor_orig);
    Hook(user32, "GetSysColorBrush", (void*)GetSysColorBrush_hook, &GetSysColorBrush_orig);
    Hook(uxtheme, "OpenThemeData", (void*)OpenThemeData_hook, &OpenThemeData_orig);
    Hook(uxtheme, "OpenThemeDataEx", (void*)OpenThemeDataEx_hook, &OpenThemeDataEx_orig);
    Hook(uxtheme, "OpenThemeDataForDpi", (void*)OpenThemeDataForDpi_hook, &OpenThemeDataForDpi_orig);
    Hook(uxtheme, "IsThemeActive", (void*)IsThemeActive_hook, &IsThemeActive_orig);
    Hook(uxtheme, "IsAppThemed", (void*)IsAppThemed_hook, &IsAppThemed_orig);
    return TRUE;
}

void Wh_ModUninit() {
    for (int i = 0; i < 31; i++) {
        if (g_brush[i]) {
            DeleteObject(g_brush[i]);
            g_brush[i] = NULL;
        }
    }
}

BOOL Wh_ModSettingsChanged(BOOL* bReload) {
    *bReload = TRUE;                                    // the list changed: start over
    return TRUE;
}
