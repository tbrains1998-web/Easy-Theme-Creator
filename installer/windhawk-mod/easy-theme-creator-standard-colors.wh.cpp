// ==WindhawkMod==
// @id              easy-theme-creator-standard-colors
// @name            Easy Theme Creator - readable text
// @description     Dialog text follows the theme (light on dark, dark on light); programs on the list get Windows' normal light colours and no window skin
// @version         1.3
// @author          tbrains1998-web
// @github          https://github.com/tbrains1998-web/Easy-Theme-Creator
// @include         *
// @exclude         windhawk.exe
// @exclude         ?:\XboxGames\*
// @exclude         *\Battle.net\*
// @exclude         *\Blizzard Entertainment\*
// @exclude         *\Diablo IV\*
// @exclude         *\Call of Duty\*
// @exclude         *\Overwatch\*
// @exclude         *\World of Warcraft\*
// @exclude         *\Riot Games\*
// @exclude         *\Riot Vanguard\*
// @exclude         *\EA Games\*
// @exclude         *\Electronic Arts\*
// @exclude         *\Epic Games\*
// @exclude         *\Ubisoft Game Launcher\*
// @exclude         *\For Honor\*
// @exclude         *\Rockstar Games\*
// @exclude         *\Counter-Strike Global Offensive\*
// @exclude         *\FACEIT AC\*
// @exclude         *\EasyAntiCheat*\*
// @exclude         *\BattlEye\*
// @compilerOptions -lgdi32 -luxtheme
// ==/WindhawkMod==

// ==WindhawkModReadme==
/*
# Easy Theme Creator - readable text

**Dialog text follows the theme.** On tab pages (a folder's Properties, most Control
Panel windows) Windows draws the labels in plain black whatever the theme says, so
on a dark theme they disappear. Where a page sets no text colour of its own, this
mod gives its labels the theme's text colour instead - but only where that reads
better on the page than the black would: light text on dark pages, dark text on
light ones (an installer's white page keeps its black text). The same goes for
checkbox, radio and tab names, which Windows draws black when the theme gives them
no colour. Anything with its own colour keeps it.

**Standard colours for chosen apps.** Some programs set a few of their own colours (a white text box, say) and take the
rest from Windows. With a dark theme those two halves stop matching and text becomes
unreadable. Put such a program on the list and, from its next start, it gets Windows'
normal light colours and draws its controls without the window skin - the way it was
designed - while everything else keeps the theme.

Easy Theme Creator fills this list for you ("Fix an app that looks wrong"); you can
also edit it here. Entries are executable names, e.g. `Notepad++.exe`.

**Stays out of games with anti-cheat.** Anti-cheat software can kick or ban a player
for code loaded into its game, so the mod never loads in the game folders excluded
above, in programs with an anti-cheat next to them (Easy Anti-Cheat, BattlEye and
others) or in services.
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
#include <vssym32.h>
#include <math.h>
#include <stddef.h>
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

// Made up front in Wh_ModInit (listed programs only), and made again when one is gone:
// unlike the system's own brushes ours can be deleted - by a stray DeleteObject, or by
// UnregisterClass when a window class used one as its background.
static HBRUSH volatile g_brush[31];

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

static HBRUSH StockBrush(int index) {
    HBRUSH b = g_brush[index];
    LOGBRUSH lb;
    if (b && GetObjectType(b) == OBJ_BRUSH && GetObjectW(b, sizeof(lb), &lb) == sizeof(lb) &&
        lb.lbStyle == BS_SOLID && lb.lbColor == g_stock[index]) {
        return b;                                       // still ours (or one just like it)
    }
    HBRUSH fresh = CreateSolidBrush(g_stock[index]);
    if (!fresh) {
        return GetSysColorBrush_orig(index);
    }
    // Two threads may notice at once: the first one's brush stays, the other is dropped unused.
    HBRUSH prev = (HBRUSH)InterlockedCompareExchangePointer((PVOID volatile*)&g_brush[index], fresh, b);
    if (prev != b) {
        DeleteObject(fresh);
        return prev;
    }
    return fresh;
}

static HBRUSH WINAPI GetSysColorBrush_hook(int index) {
    if (index >= 0 && index < 31 && index != 25) {
        return StockBrush(index);
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

// Readable text: dark surface -> light text, light surface -> dark text. Text gets the
// system text colour (light with a dark theme, black with a light one) only when that
// has the better contrast on what it is drawn over - WCAG relative luminance (0 = black,
// 1 = white) and contrast ratio (1 to 21).
static double Luminance(COLORREF c) {
    auto lin = [](int v) {
        double s = v / 255.0;
        return s <= 0.03928 ? s / 12.92 : pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * lin(GetRValue(c)) + 0.7152 * lin(GetGValue(c)) + 0.0722 * lin(GetBValue(c));
}

static double Contrast(double a, double b) {
    return a > b ? (a + 0.05) / (b + 0.05) : (b + 0.05) / (a + 0.05);
}

// Dialog text. A tab page's WM_CTLCOLOR* answer comes from uxtheme's page texture:
// it returns the tab-body brush and makes the text background transparent but sets no
// text colour, so labels draw in GDI's default black - unreadable on a dark page. When
// that is what happened (texture on, background just made transparent, text colour
// untouched), the label gets the system text colour if it reads better on that brush
// than the current one. Pages that set their own colours are left alone.
using DefDlgProc_t = LRESULT(WINAPI*)(HWND, UINT, WPARAM, LPARAM);
static DefDlgProc_t DefDlgProcW_orig;
static DefDlgProc_t DefDlgProcA_orig;

// How light a brush paints. A solid brush says so; a texture (the tab page's) is painted
// once into a small bitmap and averaged. The last few brushes are remembered per thread
// (with their bitmap, in case a handle is reused), so a page's labels cost one lookup
// each; a theme or system colour change forgets them.
struct BrushShade {
    HBRUSH brush;
    HANDLE pattern;
    LONG gen;
    double lum;
};
static thread_local BrushShade t_shades[4];
static thread_local unsigned t_nextShade;
static LONG volatile g_gen = 1;

static bool BrushLuminance(HBRUSH brush, double* lum) {
    LOGBRUSH lb;
    if (GetObjectType(brush) != OBJ_BRUSH || GetObjectW(brush, sizeof(lb), &lb) != sizeof(lb) ||
        lb.lbStyle == BS_NULL) {
        return false;
    }
    if (lb.lbStyle == BS_SOLID) {
        *lum = Luminance(lb.lbColor);
        return true;
    }
    LONG gen = g_gen;
    for (const BrushShade& s : t_shades) {
        if (s.brush == brush && s.pattern == (HANDLE)lb.lbHatch && s.gen == gen) {
            *lum = s.lum;
            return true;
        }
    }
    const int N = 8;
    BITMAPINFO bi = {};
    bi.bmiHeader.biSize = sizeof(bi.bmiHeader);
    bi.bmiHeader.biWidth = N;
    bi.bmiHeader.biHeight = -N;                         // top-down
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    void* bits = NULL;
    bool ok = false;
    HDC mem = CreateCompatibleDC(NULL);
    HBITMAP bmp = mem ? CreateDIBSection(mem, &bi, DIB_RGB_COLORS, &bits, NULL, 0) : NULL;
    if (bmp && bits) {
        HGDIOBJ old = SelectObject(mem, bmp);
        RECT rc = {0, 0, N, N};
        if (FillRect(mem, &rc, brush)) {
            GdiFlush();
            const DWORD* px = (const DWORD*)bits;       // 0x00RRGGBB
            double sum = 0;
            for (int i = 0; i < N * N; i++) {
                sum += Luminance(RGB((px[i] >> 16) & 0xFF, (px[i] >> 8) & 0xFF, px[i] & 0xFF));
            }
            *lum = sum / (N * N);
            ok = true;
        }
        SelectObject(mem, old);
    }
    if (bmp) {
        DeleteObject(bmp);
    }
    if (mem) {
        DeleteDC(mem);
    }
    if (ok) {
        t_shades[t_nextShade++ % 4] = {brush, (HANDLE)lb.lbHatch, gen, *lum};
    }
    return ok;
}

static LRESULT DialogText(DefDlgProc_t orig, HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_THEMECHANGED || msg == WM_SYSCOLORCHANGE) {
        InterlockedIncrement(&g_gen);
    }
    if (msg != WM_CTLCOLORSTATIC && msg != WM_CTLCOLORBTN && msg != WM_CTLCOLORDLG) {
        return orig(hwnd, msg, wp, lp);
    }
    HDC dc = (HDC)wp;
    COLORREF text = GetTextColor(dc);
    int mode = GetBkMode(dc);
    LRESULT r = orig(hwnd, msg, wp, lp);
    if (r && mode != TRANSPARENT && GetBkMode(dc) == TRANSPARENT && GetTextColor(dc) == text &&
        IsThemeDialogTextureEnabled(hwnd)) {
        COLORREF sys = GetSysColor(COLOR_BTNTEXT);
        double surface;
        // (a brush that can't be read keeps the earlier rule: the system text colour)
        if (!BrushLuminance((HBRUSH)r, &surface) ||
            Contrast(Luminance(sys), surface) > Contrast(Luminance(text), surface)) {
            SetTextColor(dc, sys);
        }
    }
    return r;
}

static LRESULT WINAPI DefDlgProcW_hook(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    return DialogText(DefDlgProcW_orig, hwnd, msg, wp, lp);
}

static LRESULT WINAPI DefDlgProcA_hook(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    return DialogText(DefDlgProcA_orig, hwnd, msg, wp, lp);
}

// Themed text. Checkbox and radio labels, tab names and the like are drawn with
// DrawThemeText, which uses the part's TEXTCOLOR - and plain black when the theme has
// none for that part (it ignores the DC's colour). Those parts get the system text
// colour instead when it reads better than black on what is already painted under
// the text. Callers that pass their own colour, parts the theme colours, size-only
// calls and greyed (disabled) text are left alone.
using DrawThemeTextEx_t = HRESULT(WINAPI*)(HTHEME, HDC, int, int, LPCWSTR, int, DWORD, LPRECT, const DTTOPTS*);
static DrawThemeTextEx_t DrawThemeTextEx_orig;
using DrawThemeText_t = HRESULT(WINAPI*)(HTHEME, HDC, int, int, LPCWSTR, int, DWORD, DWORD, LPCRECT);
static DrawThemeText_t DrawThemeText_orig;

// Set while a DrawThemeText we let through runs, in case uxtheme draws it through
// DrawThemeTextEx: it must come out exactly as uxtheme would draw it.
static thread_local bool t_untouched;

#define DTTOPTS_HAS(o, field) ((o)->dwSize >= offsetof(DTTOPTS, field) + sizeof((o)->field))

static bool HasColor(HTHEME theme, int part, int state, int prop) {
    COLORREF c;
    return SUCCEEDED(GetThemeColor(theme, part, state, prop, &c));
}

// How light the surface under a text rectangle is: a few points where glyphs are
// unlikely (its corners). Points outside the clip area, printer and metafile DCs can't
// be read; false when no point could.
static bool SurfaceLuminance(HDC dc, const RECT* rc, double* lum) {
    if (rc->right <= rc->left || rc->bottom <= rc->top || GetDeviceCaps(dc, TECHNOLOGY) != DT_RASDISPLAY) {
        return false;
    }
    const POINT pts[4] = {{rc->left, rc->top}, {rc->right - 1, rc->top},
                          {rc->left, rc->bottom - 1}, {rc->right - 1, rc->bottom - 1}};
    double sum = 0;
    int n = 0;
    for (const POINT& p : pts) {
        COLORREF c = GetPixel(dc, p.x, p.y);
        if (c != CLR_INVALID) {
            sum += Luminance(c);
            n++;
        }
    }
    if (!n) {
        return false;
    }
    *lum = sum / n;
    return true;
}

// The colour to draw a themed text in instead of uxtheme's black, if any.
static bool SystemTextColor(HTHEME theme, HDC dc, int part, int state, int prop, const RECT* rc, COLORREF* out) {
    if (!theme || !rc || HasColor(theme, part, state, TMT_TEXTCOLOR) ||
        (prop != TMT_TEXTCOLOR && HasColor(theme, part, state, prop))) {
        return false;
    }
    double surface;
    if (!SurfaceLuminance(dc, rc, &surface)) {
        return false;
    }
    COLORREF sys = GetSysColor(COLOR_BTNTEXT);
    if (Contrast(Luminance(sys), surface) <= Contrast(0.0, surface)) {
        return false;                                   // black reads better here
    }
    *out = sys;
    return true;
}

static HRESULT WINAPI DrawThemeTextEx_hook(HTHEME theme, HDC dc, int part, int state, LPCWSTR text,
                                           int len, DWORD flags, LPRECT rect, const DTTOPTS* opts) {
    DWORD of = opts && DTTOPTS_HAS(opts, dwFlags) ? opts->dwFlags : 0;
    if (!t_untouched && (!opts || DTTOPTS_HAS(opts, dwFlags)) && !(of & (DTT_TEXTCOLOR | DTT_CALCRECT)) &&
        !(flags & DT_CALCRECT)) {
        int st = (of & DTT_STATEID) && DTTOPTS_HAS(opts, iStateId) ? opts->iStateId : state;
        int prop = (of & DTT_COLORPROP) && DTTOPTS_HAS(opts, iColorPropId) ? opts->iColorPropId : TMT_TEXTCOLOR;
        COLORREF color;
        if (SystemTextColor(theme, dc, part, st, prop, rect, &color)) {
            DTTOPTS o = {};
            if (opts) {
                CopyMemory(&o, opts, opts->dwSize < sizeof(o) ? opts->dwSize : sizeof(o));
            }
            o.dwSize = sizeof(o);
            o.dwFlags = (o.dwFlags | DTT_TEXTCOLOR) & ~DTT_COLORPROP;
            o.crText = color;
            return DrawThemeTextEx_orig(theme, dc, part, state, text, len, flags, rect, &o);
        }
    }
    return DrawThemeTextEx_orig(theme, dc, part, state, text, len, flags, rect, opts);
}

static HRESULT WINAPI DrawThemeText_hook(HTHEME theme, HDC dc, int part, int state, LPCWSTR text,
                                         int len, DWORD flags, DWORD flags2, LPCRECT rect) {
    COLORREF color;
    if (DrawThemeTextEx_orig && !t_untouched && !flags2 && !(flags & DT_CALCRECT) &&
        SystemTextColor(theme, dc, part, state, TMT_TEXTCOLOR, rect, &color)) {
        DTTOPTS o = {};
        o.dwSize = sizeof(o);
        o.dwFlags = DTT_TEXTCOLOR;
        o.crText = color;
        RECT r = *rect;
        return DrawThemeTextEx_orig(theme, dc, part, state, text, len, flags, &r, &o);
    }
    bool was = t_untouched;
    t_untouched = true;
    HRESULT hr = DrawThemeText_orig(theme, dc, part, state, text, len, flags, flags2, rect);
    t_untouched = was;
    return hr;
}

// Anti-cheat software watches what is loaded into its game, and a foreign hook can get
// the player kicked or banned. Besides the game folders excluded above, the mod stays
// out of any program with an anti-cheat beside it: in its folder or up to three folders
// up (Unreal games keep it at the game's root, the exe in Binaries\Win64). One attribute
// lookup per name; Windows' own programs and network drives are not looked at.
// standard_colors.py repeats these lists for "Fix an app" - keep them the same.
static const PCWSTR g_antiCheatFiles[] = {
    L"EasyAntiCheat", L"EasyAntiCheat_EOS", L"start_protected_game.exe",    // Easy Anti-Cheat
    L"BattlEye",                                                             // BattlEye
    L"EAAntiCheat.GameServiceLauncher.exe",                                  // EA anti-cheat
    L"mhyprot2.sys", L"mhyprot3.sys", L"mhypbase.dll",                       // HoYoverse
    L"GameGuard", L"XIGNCODE", L"AntiCheatExpert",                           // nProtect, Wellbia, Tencent
};
static const PCWSTR g_antiCheatExes[] = {L"vgc.exe", L"vgtray.exe"};      // Riot Vanguard itself

static bool AntiCheatNearby(const WCHAR* exe) {
    const WCHAR* name = wcsrchr(exe, L'\\');
    if (!name || exe[0] == L'\\' || exe[1] != L':') {
        return false;                                   // network (\\server\...) or odd paths
    }
    for (PCWSTR n : g_antiCheatExes) {
        if (_wcsicmp(name + 1, n) == 0) {
            return true;
        }
    }
    WCHAR win[MAX_PATH];
    UINT w = GetWindowsDirectoryW(win, MAX_PATH);
    if (w && w < MAX_PATH && _wcsnicmp(exe, win, w) == 0 && exe[w] == L'\\') {
        return false;                                   // Windows' own programs
    }
    WCHAR root[] = {exe[0], L':', L'\\', 0};
    if (GetDriveTypeW(root) == DRIVE_REMOTE) {
        return false;
    }
    WCHAR dir[1024 + 64];
    size_t len = name - exe;                            // the program's folder, no trailing '\'
    if (len >= 1024) {
        return false;
    }
    wmemcpy(dir, exe, len);
    for (int level = 0; level < 4 && len > 2; level++) {   // len 2 = "C:", the drive root: stop
        for (PCWSTR n : g_antiCheatFiles) {
            size_t nl = wcslen(n);
            dir[len] = L'\\';
            wmemcpy(dir + len + 1, n, nl + 1);
            if (GetFileAttributesW(dir) != INVALID_FILE_ATTRIBUTES) {
                return true;
            }
        }
        while (len > 0 && dir[len - 1] != L'\\') {      // one folder up
            len--;
        }
        if (len > 0) {
            len--;
        }
    }
    return false;
}

static WCHAR g_exe[1024];                               // this program, from Wh_ModInit
static bool g_listed;                                   // on the list when the mod loaded

static bool ThisProcessIsListed() {
    const WCHAR* name = wcsrchr(g_exe, L'\\');
    if (!name) {
        return false;
    }
    name++;
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
    DWORD session = 0;
    if (ProcessIdToSessionId(GetCurrentProcessId(), &session) && session == 0) {
        return FALSE;                                   // a service: nobody sees its windows
    }
    HMODULE user32 = GetModuleHandleW(L"user32.dll");
    if (!user32) {
        return FALSE;                                   // no windows in this program: unload
    }
    DWORD n = GetModuleFileNameW(NULL, g_exe, ARRAYSIZE(g_exe));
    if (n == 0 || n >= ARRAYSIZE(g_exe)) {
        g_exe[0] = 0;
    } else if (AntiCheatNearby(g_exe)) {
        Wh_Log(L"anti-cheat next to this program: not loading");
        return FALSE;
    }
    g_listed = ThisProcessIsListed();
    Hook(user32, "DefDlgProcW", (void*)DefDlgProcW_hook, &DefDlgProcW_orig);
    Hook(user32, "DefDlgProcA", (void*)DefDlgProcA_hook, &DefDlgProcA_orig);
    HMODULE uxtheme = LoadLibraryW(L"uxtheme.dll");
    if (!uxtheme) {
        return TRUE;
    }
    if (!g_listed) {
        Hook(uxtheme, "DrawThemeTextEx", (void*)DrawThemeTextEx_hook, &DrawThemeTextEx_orig);
        Hook(uxtheme, "DrawThemeText", (void*)DrawThemeText_hook, &DrawThemeText_orig);
        return TRUE;
    }
    Wh_Log(L"standard colours for this program");
    for (int i = 0; i < 31; i++) {
        if (i != 25) {
            g_brush[i] = CreateSolidBrush(g_stock[i]);
        }
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
    // The stock-colour brushes are not deleted: the program may still paint with them
    // (a window class keeps its background brush), and Windows frees them at its exit.
}

BOOL Wh_ModSettingsChanged(BOOL* bReload) {
    *bReload = ThisProcessIsListed() != g_listed;       // only when this program joined or left the list
    return TRUE;
}
