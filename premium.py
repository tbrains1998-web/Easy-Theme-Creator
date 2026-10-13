"""'Premium' skin art: our own drawn gunmetal armor-plate caption buttons with a
neon glow, in the theme's accent color. Replaces pieces of the window-frame
atlas (the DWMWindow STREAM image) that Windows 11 draws the min / max / close
buttons from. Everything here is drawn from scratch.
"""
import io

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# DWMWindow parts (atlas rectangles) and what they are. Each holds 4 states
# stacked vertically: normal, hover, pressed, inactive.
BUTTON_BG = [3, 4, 5, 6, 88, 89, 90, 91]       # min / max / help backgrounds
CLOSE_BG = [7, 8, 9, 10]                        # close button backgrounds
GLYPHS_LIGHT = list(range(11, 31)) + [38, 39, 40, 41]
GLYPHS_DARK = list(range(64, 88))
SCALE = 4                                       # draw big, shrink for smooth edges


def _scale(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def plate(w, h, accent, state, close=False):
    """One caption button: chamfered dark metal plate, bevel, neon edge.
    state: 0 normal, 1 hover, 2 pressed, 3 inactive."""
    W, H, k = w * SCALE, h * SCALE, SCALE
    img = Image.new("RGBA", (W, H))
    cut = 4 * k
    pad = 1 * k
    shape = [(pad + cut, pad), (W - pad - cut, pad), (W - pad, pad + cut), (W - pad, H - pad - cut),
             (W - pad - cut, H - pad), (pad + cut, H - pad), (pad, H - pad - cut), (pad, pad + cut)]
    mask = Image.new("L", (W, H))
    ImageDraw.Draw(mask).polygon(shape, fill=255)

    base_top, base_bot = (58, 58, 64), (14, 14, 16)
    if close:
        base_top, base_bot = _mix(base_top, accent, 0.45), _mix(base_bot, accent, 0.30)
    if state == 1:
        base_top, base_bot = _mix(base_top, accent, 0.35), _mix(base_bot, accent, 0.25)
    elif state == 2:
        base_top, base_bot = _scale(base_bot, 1.2), _mix(base_top, accent, 0.25)
    elif state == 3:
        base_top, base_bot = _scale(base_top, 0.7), _scale(base_bot, 0.8)
    g = Image.linear_gradient("L").resize((W, H))
    body = Image.composite(Image.new("RGBA", (W, H), base_bot + (255,)),
                           Image.new("RGBA", (W, H), base_top + (255,)), g)
    # brushed-metal streaks
    streak = Image.effect_noise((W, 1), 40).resize((W, H)).convert("L")
    body = Image.composite(body, Image.new("RGBA", (W, H), (0, 0, 0, 255)), streak.point(lambda v: 225 + v // 8))
    img.paste(body, (0, 0), mask)

    d = ImageDraw.Draw(img)
    hi = (150, 150, 158, 255) if state != 3 else (90, 90, 96, 255)
    d.line(shape[7:] + shape[:3], fill=hi, width=max(1, k // 2))                  # top-left bevel
    d.line(shape[3:7], fill=(0, 0, 0, 255), width=k)                                # bottom shadow
    glow_strength = {0: 0.55, 1: 1.0, 2: 0.8, 3: 0.2}[state] * (1.0 if not close else 1.15)
    neon = Image.new("RGBA", (W, H))
    nd = ImageDraw.Draw(neon)
    edge_col = _scale(accent, min(1.0, 0.5 + glow_strength * 0.6)) + (int(255 * min(1, glow_strength)),)
    nd.line([(pad + cut + k, H - pad - 2 * k), (W - pad - cut - k, H - pad - 2 * k)], fill=edge_col, width=k)
    if state in (1, 2) or close:
        nd.line(shape + [shape[0]], fill=edge_col, width=k)
    blur = neon.filter(ImageFilter.GaussianBlur(2 * k))
    img = Image.alpha_composite(img, blur)
    img = Image.alpha_composite(img, neon)
    return img.resize((w, h), Image.LANCZOS)


def glyph_tint(crop, accent, dark_mode):
    """Caption glyphs (x, box, line, ?): accent-tinted with a soft glow."""
    a = crop.getchannel("A")
    col = _mix(accent, (255, 255, 255), 0.55) if dark_mode else _mix(accent, (255, 255, 255), 0.35)
    solid = Image.new("RGBA", crop.size, col + (0,))
    solid.putalpha(a)
    glow = Image.new("RGBA", crop.size, accent[:3] + (0,))
    glow.putalpha(a.filter(ImageFilter.GaussianBlur(1.2)).point(lambda v: min(255, v * 2)))
    return Image.alpha_composite(glow, solid)


def paint_atlas(atlas_png, rects, accent):
    """atlas_png: bytes of the DWMWindow atlas. rects: {part: (l, t, r, b)}. Returns new PNG bytes."""
    atlas = Image.open(io.BytesIO(atlas_png)).convert("RGBA")
    clear = Image.new("RGBA", atlas.size)

    def put(part, img):
        l, t, r, b = rects[part]
        atlas.paste(clear.crop((l, t, r, b)), (l, t))
        atlas.paste(img, (l, t))

    for part in BUTTON_BG + CLOSE_BG:
        if part not in rects:
            continue
        l, t, r, b = rects[part]
        w, h = r - l, b - t
        sh = h // 4
        strip = Image.new("RGBA", (w, h))
        for s in range(4):
            strip.paste(plate(w, sh, accent, s, close=part in CLOSE_BG), (0, s * sh))
        put(part, strip)
    for part in GLYPHS_LIGHT + GLYPHS_DARK:
        if part not in rects:
            continue
        l, t, r, b = rects[part]
        put(part, glyph_tint(atlas.crop((l, t, r, b)), accent, part in GLYPHS_DARK))
    out = io.BytesIO()
    atlas.save(out, "PNG")
    return out.getvalue()


def preview_buttons(accent):
    """Small sheet of the four button states for min/max and close (for checking)."""
    sheet = Image.new("RGBA", (4 * 60 + 10, 2 * 34 + 10), (20, 20, 22, 255))
    for s in range(4):
        sheet.alpha_composite(plate(51, 22, accent, s).resize((51 * 1, 22 * 1)), (5 + s * 60, 5))
        sheet.alpha_composite(plate(51, 22, accent, s, close=True), (5 + s * 60, 39))
    return sheet
