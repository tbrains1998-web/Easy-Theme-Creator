"""Draw a mock-up of the desktop from the real theme parts: the generated folder
icons, the colors the window skin will actually use, and the chosen layout."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

import alien_icons
import skin

W, H = 760, 440
FOLDERS = [("Games", "saved-games"), ("Music", "music"), ("Pictures", "pictures"),
           ("Videos", "videos"), ("Downloads", "downloads"), ("Documents", "documents")]


def _mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def skin_colors(accent_hex, dark):
    """The colors the generated skin turns Windows' stock colors into."""
    p = skin.Painter(accent_hex)

    def run(rgb, mode):
        px = np.array([[rgb]], float) / 255
        return tuple(int(v) for v in (np.clip(p.paint(px, mode)[0, 0], 0, 1) * 255 + 0.5))
    if dark:
        win, bar, text = (25, 25, 25), (43, 43, 43), (240, 240, 240)
        win, bar = run(win, "dark"), run(bar, "dark")
    else:
        win, bar, text = (250, 250, 250), (238, 238, 238), (20, 20, 20)
    return {"win": win, "bar": bar, "text": text,
            "frame": run((235, 235, 235), "frame"),        # title bar art
            "select": run((0, 120, 212), "hue"),           # Windows blue -> accent
            "accent": run((0, 120, 212), "hue")}


def stock_colors(dark):
    if dark:
        return {"win": (25, 25, 25), "bar": (43, 43, 43), "text": (240, 240, 240),
                "frame": (32, 32, 32), "select": (0, 120, 212), "accent": (0, 120, 212)}
    return {"win": (250, 250, 250), "bar": (238, 238, 238), "text": (20, 20, 20),
            "frame": (243, 243, 243), "select": (0, 120, 212), "accent": (0, 120, 212)}


def folder_icons(accent, dark_color, px=72):
    """Small versions of the real generated Alien icons."""
    painter = alien_icons.Painter(accent, dark_color, size=256)
    return {kind: painter.icon(kind).resize((px, px), Image.LANCZOS) for _, kind in FOLDERS}


def plain_folder(px=72):
    ic = Image.new("RGBA", (px, px))
    d = ImageDraw.Draw(ic)
    d.rounded_rectangle([6, 12, 40, 26], 4, fill=(220, 170, 50, 255))
    d.rounded_rectangle([6, 18, px - 6, px - 10], 6, fill=(245, 200, 70, 255))
    return ic


def mockup(background, colors, look="Modern", icons=None, taskbar_accent=None, premium=False, orb=False):
    """background: PIL image. colors: from skin_colors()/stock_colors().
    look: Modern | Classic | Retro. icons: {kind: image} or None for plain folders."""
    c = colors
    acc, text = c["accent"], c["text"]
    img = ImageOps.fit(background.convert("RGB"), (W, H), Image.LANCZOS).convert("RGBA")

    x0, y0, x1, y1 = 70, 30, 690, 362
    sh = Image.new("RGBA", (W, H))
    ImageDraw.Draw(sh).rounded_rectangle([x0 + 6, y0 + 10, x1 + 6, y1 + 10], 12, fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    radius = 10 if look == "Modern" else 3
    d.rounded_rectangle([x0, y0, x1, y1], radius, fill=c["win"] + (255,), outline=acc + (255,), width=2)
    d.rounded_rectangle([x0 + 2, y0 + 2, x1 - 2, y0 + 30], radius, fill=c["frame"] + (255,))
    if premium:                                   # our drawn armor-plate caption buttons
        import premium as prem
        for i in range(3):
            plate = prem.plate(28, 22, acc, 1 if i == 0 else 0, close=i == 0)
            img.alpha_composite(plate, (x1 - 34 - i * 30, y0 + 5))
        d = ImageDraw.Draw(img)
    for i, sym in enumerate("xo-"):
        cx, cy = x1 - 20 - i * 30, y0 + 16
        if sym == "x":
            d.line([(cx - 5, cy - 5), (cx + 5, cy + 5)], fill=text, width=2)
            d.line([(cx - 5, cy + 5), (cx + 5, cy - 5)], fill=text, width=2)
        elif sym == "o":
            d.rectangle([cx - 5, cy - 5, cx + 5, cy + 5], outline=text, width=2)
        else:
            d.line([(cx - 5, cy), (cx + 5, cy)], fill=text, width=2)
    d.text((x0 + 14, y0 + 9), "Documents", fill=text)

    ty = y0 + 34
    d.rectangle([x0 + 2, ty, x1 - 2, ty + 26], fill=c["bar"] + (255,))
    for i, (dx, sym) in enumerate(((14, "<"), (38, ">"), (62, "^"))):
        x = x0 + dx
        if sym == "<":
            d.polygon([(x, ty + 13), (x + 9, ty + 7), (x + 9, ty + 19)], fill=text)
        elif sym == ">":
            d.polygon([(x + 9, ty + 13), (x, ty + 7), (x, ty + 19)], fill=_mix(text, c["bar"], 0.5))
        else:
            d.polygon([(x + 5, ty + 6), (x, ty + 18), (x + 10, ty + 18)], fill=text)
    d.rounded_rectangle([x0 + 90, ty + 4, x1 - 160, ty + 22], 6, fill=c["win"] + (255,))
    d.text((x0 + 100, ty + 7), "This PC  >  Documents", fill=text)
    d.rounded_rectangle([x1 - 150, ty + 4, x1 - 10, ty + 22], 6, fill=c["win"] + (255,))
    d.text((x1 - 140, ty + 7), "Search", fill=_mix(text, c["win"], 0.45))
    ty += 28

    if look == "Classic":                       # Windows 10 ribbon
        for i, t in enumerate(("File", "Home", "Share", "View")):
            d.rectangle([x0 + 4 + i * 56, ty, x0 + 56 + i * 56, ty + 18],
                        fill=(acc if i == 0 else c["bar"]) + (255,))
            d.text((x0 + 16 + i * 56, ty + 3), t, fill=(255, 255, 255) if i == 0 else text)
        d.rectangle([x0 + 2, ty + 18, x1 - 2, ty + 64], fill=c["bar"] + (255,))
        for i, t in enumerate(("Copy", "Paste", "Cut", "Move", "Delete", "Rename", "New")):
            bx = x0 + 12 + i * 64
            d.rounded_rectangle([bx + 10, ty + 23, bx + 34, ty + 45], 3, outline=acc + (255,), width=2)
            d.text((bx + 6, ty + 49), t, fill=text)
        ty += 68
    elif look == "Retro":                       # Windows 7 simple bar
        d.rectangle([x0 + 2, ty, x1 - 2, ty + 22], fill=c["bar"] + (255,))
        for i, t in enumerate(("Organize  v", "Share with  v", "New folder")):
            d.text((x0 + 12 + i * 100, ty + 5), t, fill=text)
        ty += 24
    else:                                       # Windows 11 command bar
        d.rectangle([x0 + 2, ty, x1 - 2, ty + 28], fill=c["bar"] + (255,))
        d.rounded_rectangle([x0 + 10, ty + 4, x0 + 74, ty + 24], 6, fill=acc + (255,))
        d.text((x0 + 22, ty + 8), "+ New", fill=(255, 255, 255))
        for i in range(6):
            d.rounded_rectangle([x0 + 88 + i * 30, ty + 7, x0 + 106 + i * 30, ty + 21], 3,
                                outline=_mix(text, c["bar"], 0.45), width=2)
        d.text((x0 + 290, ty + 8), "Sort v    View v    ...", fill=text)
        ty += 30

    bottom = y1 - (26 if look == "Retro" else 2)
    d.rectangle([x0 + 2, ty, x0 + 124, bottom], fill=_mix(c["win"], c["bar"], 0.5) + (255,))
    for i, t in enumerate(("Desktop", "Downloads", "Documents", "Pictures", "Music", "This PC")):
        if i == 2:
            d.rounded_rectangle([x0 + 6, ty + 6 + i * 22, x0 + 120, ty + 24 + i * 22], 4,
                                fill=_mix(c["win"], c["select"], 0.5) + (255,))
        d.text((x0 + 16, ty + 10 + i * 22), t, fill=text)

    for i, (label, kind) in enumerate(FOLDERS):
        gx, gy = x0 + 146 + (i % 4) * 128, ty + 10 + (i // 4) * 100
        ic = icons[kind] if icons else plain_folder()
        img.alpha_composite(ic, (gx + 14, gy))
        d.text((gx + 50 - len(label) * 3, gy + 76), label, fill=text)
    if look == "Retro":
        d.rectangle([x0 + 2, y1 - 26, x1 - 2, y1 - 2], fill=c["bar"] + (255,))
        d.text((x0 + 14, y1 - 19), "6 items", fill=text)

    # taskbar: Modern = centered icons; Classic = left with square Start; Retro = round orb
    if taskbar_accent == "metal":               # the real drawn metal profile, stretched
        import taskbar as tbmod
        bar = tbmod.metal_profile(40, acc, "bottom").resize((W, 40))
        img.alpha_composite(bar, (0, H - 40))
        d = ImageDraw.Draw(img)
        tb = (12, 12, 14)
    else:
        tb = taskbar_accent or (14, 14, 16)
        d.rectangle([0, H - 40, W, H], fill=tb + (235,))
    n = 7
    if orb:                                     # alien-head Start button
        import taskbar as tbmod
        strip = tbmod.orb_image(acc)
        o = strip.crop((0, 0, strip.width, strip.width)).resize((38, 38), Image.LANCZOS)
        sx = W // 2 - n * 20 if look == "Modern" else 64
        img.alpha_composite(o, ((sx - 44) if look == "Modern" else 8, H - 39))
        d = ImageDraw.Draw(img)
    elif look == "Modern":
        sx = W // 2 - n * 20
        d.rounded_rectangle([sx - 36, H - 33, sx - 10, H - 9], 6, fill=acc + (255,))
    elif look == "Classic":
        sx = 56
        d.rectangle([6, H - 36, 40, H - 4], fill=acc + (255,))
    else:
        sx = 64
        d.ellipse([8, H - 39, 48, H - 1], fill=acc + (255,), outline=(255, 255, 255, 200), width=2)
    for i in range(n):
        cx = sx + i * 40
        d.rounded_rectangle([cx, H - 32, cx + 24, H - 10], 5, fill=_mix(tb, (210, 210, 210), 0.55) + (255,))
        if i == 1:
            d.line([(cx + 4, H - 4), (cx + 20, H - 4)], fill=acc + (255,), width=3)
    d.text((W - 60, H - 26), "16:40", fill=(240, 240, 240))
    return img


# ------------------------------------------------------------------ armor Explorer

def _nine(img, m, W, H):
    """Stretch a skin image to W x H the way Windows does (sizing margins l, r, t, b)."""
    l, r, t, b = m
    w, h = img.size
    if H < t + b:                                   # too short: Windows scales the margins down
        k = H / (t + b)
        t, b = int(t * k), H - int(t * k)
        img = img.resize((w, max(1, int(h * k))), Image.LANCZOS)
        w, h = img.size
        t, b = min(t, h), min(b, h - min(t, h))
    out = Image.new("RGBA", (W, H))
    for sx0, sx1, dx0, dx1 in ((0, l, 0, l), (l, w - r, l, W - r), (w - r, w, W - r, W)):
        for sy0, sy1, dy0, dy1 in ((0, t, 0, t), (t, h - b, t, H - b), (h - b, h, H - b, H)):
            if sx1 > sx0 and sy1 > sy0 and dx1 > dx0 and dy1 > dy0:
                out.paste(img.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR),
                          (dx0, dy0))
    return out


def explorer_armor(accent_hex, dark_color, sci_font=True, size=(900, 600)):
    """A File Explorer window with the armor look, drawn from the same plates,
    emblem panel, icons and font the theme installs."""
    import os
    from PIL import ImageFont
    import armor
    acc = tuple(int(accent_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    red = skin.Painter(accent_hex).text_accent()
    here = os.path.dirname(os.path.abspath(__file__))

    def font(px, bold=False):
        if sci_font:
            try:
                return ImageFont.truetype(os.path.join(here, "fonts", "Orbitron %s.ttf" % ("Bold" if bold else "Medium")), px)
            except OSError:
                pass
        return ImageFont.truetype("segoeuib.ttf" if bold else "segoeui.ttf", px)

    W, H = size
    win = Image.new("RGBA", (W, H), (16, 16, 18, 255))
    d = ImageDraw.Draw(win)
    d.rectangle([0, 0, W - 1, 30], fill=(10, 10, 12, 255))                       # title bar
    d.text((12, 7), "This PC", font=font(13), fill=(225, 225, 225))
    for i, ch in enumerate(("—", "□", "✕")):
        d.text((W - 118 + i * 40, 6), ch, font=ImageFont.truetype("seguisym.ttf", 15), fill=(200, 200, 200))
    nav, m = armor.plate(3, 25, (1, 1, 9, 15), acc, seed=3)                       # address row
    win.alpha_composite(_nine(nav, m, W, 46), (0, 31))
    d.rounded_rectangle([96, 39, W - 250, 66], 4, fill=(8, 8, 9, 255), outline=(70, 24, 24, 255))
    d.text((108, 45), "›  This PC", font=font(13), fill=(230, 230, 230))
    d.rounded_rectangle([W - 236, 39, W - 14, 66], 4, fill=(8, 8, 9, 255), outline=(70, 24, 24, 255))
    d.text((W - 224, 45), "Search This PC", font=font(12), fill=(120, 120, 120))
    for i, ch in enumerate(("←", "→")):
        d.ellipse([12 + i * 38, 40, 40 + i * 38, 68], fill=(30, 10, 10, 255), outline=red)
        d.text((19 + i * 38, 42), ch, font=ImageFont.truetype("seguisym.ttf", 17), fill=(240, 240, 240))
    menu, m = armor.plate(5, 5, (2, 2, 2, 2), acc, seed=4)                         # menu bar
    win.alpha_composite(_nine(menu, m, W, 30), (0, 77))
    x = 14
    for word in ("File", "Edit", "View", "Tools", "Help"):
        d.text((x, 84), word, font=font(13, True), fill=red)
        x += int(d.textlength(word, font=font(13, True))) + 26
    cmd, m = armor.plate(3, 7, (1, 1, 3, 3), acc, seed=5)                          # command bar
    win.alpha_composite(_nine(cmd, m, W, 40), (0, 107))
    x = 16
    for word in ("Organize ▾", "System properties", "Uninstall a program", "Map network drive"):
        d.text((x, 118), word.replace(" ▾", ""), font=font(13, True), fill=red)
        x += int(d.textlength(word.replace(" ▾", ""), font=font(13, True)))
        if "▾" in word:
            d.text((x + 4, 116), "▾", font=ImageFont.truetype("seguisym.ttf", 14), fill=red)
            x += 14
        x += 30
    top, bottom = 147, H - 100
    d.rectangle([0, top, 230, bottom], fill=(14, 14, 16, 255))                     # navigation pane
    d.line([230, top, 230, bottom], fill=(40, 40, 44, 255))
    icons = folder_icons(acc, dark_color, px=22)
    y = top + 14
    for label, kind in [("Desktop", "documents"), ("Downloads", "downloads"), ("Documents", "documents"),
                        ("Pictures", "pictures"), ("Music", "music"), ("Videos", "videos")]:
        win.alpha_composite(icons.get(kind, icons["documents"]), (22, y))
        d.text((54, y + 3), label, font=font(13), fill=(225, 225, 225))
        y += 34
    d.text((54, y + 14), "This PC", font=font(13), fill=(255, 255, 255))
    d.rectangle([14, y + 8, 222, y + 38], outline=red)
    big = folder_icons(acc, dark_color, px=84)
    for i, (label, kind) in enumerate(FOLDERS):
        cx, cy = 262 + (i % 4) * 152, top + 18 + (i // 4) * 150
        win.alpha_composite(big[kind], (cx + 20, cy))
        tw = d.textlength(label, font=font(13))
        d.text((cx + 62 - tw / 2, cy + 92), label, font=font(13), fill=(225, 225, 225))
    panel, m = armor.emblem_panel(acc)                                              # details panel
    win.alpha_composite(_nine(panel, m, W, H - bottom), (0, bottom))
    win.alpha_composite(big["saved-games"].resize((64, 64), Image.LANCZOS), (22, bottom + 18))
    d.text((104, bottom + 26), "6 items", font=font(15, True), fill=(235, 235, 235))
    d.text((104, bottom + 52), "Alien Red theme", font=font(12), fill=(150, 150, 150))
    d.rectangle([0, 0, W - 1, H - 1], outline=(90, 20, 20, 255))
    return win
