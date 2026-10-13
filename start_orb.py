"""Original alien-head Start button for StartAllBack: one PNG per size,
3 states stacked top to bottom (normal, hover, pressed). Mostly black, red glow."""
import math, sys, os
from PIL import Image, ImageDraw, ImageFilter, ImageChops

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
S = 512

def head(glow_level):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    k = S / 100
    disc = Image.new("L", (S, S), 0); ImageDraw.Draw(disc).ellipse([2*k, 2*k, 98*k, 98*k], fill=255)
    g = Image.linear_gradient("L").resize((S, S))
    metal = Image.composite(Image.new("RGBA", (S, S), (6, 6, 7, 255)), Image.new("RGBA", (S, S), (46, 46, 50, 255)), g)
    img.paste(metal, (0, 0), disc)
    d = ImageDraw.Draw(img)
    d.ellipse([2*k, 2*k, 98*k, 98*k], outline=(int(110 + 60*glow_level), 0, 0, 255), width=int(2.2*k))
    d.ellipse([7*k, 7*k, 93*k, 93*k], outline=(28, 28, 30, 255), width=int(1*k))
    pts = []
    for i in range(61):
        t = i / 60 * 2 * math.pi
        x = math.sin(t); y = -math.cos(t)
        w = 27 if y < 0.1 else 27 * (1 - (y - 0.1) / 0.9 * 0.78)
        pts.append(((50 + w * x) * k, (47 + 33 * y + (6 if y > 0 else 0) * y) * k))
    d.polygon(pts, fill=(14, 14, 16, 255), outline=(95, 95, 102, 255), width=int(1.2*k))
    neon = Image.new("RGBA", (S, S), (0, 0, 0, 0)); n = ImageDraw.Draw(neon)
    r = (int(190 + 65 * glow_level), int(10 + 30 * glow_level), int(10 + 20 * glow_level), 255)
    for sgn in (-1, 1):
        cx, cy = 50 + sgn * 12, 50
        eye = []
        for i in range(41):
            t = i / 40 * 2 * math.pi
            ex, ey = 11 * math.cos(t), 5.2 * math.sin(t)
            a = -sgn * math.radians(30)
            eye.append(((cx + ex * math.cos(a) - ey * math.sin(a)) * k, (cy + ex * math.sin(a) + ey * math.cos(a)) * k))
        n.polygon(eye, fill=r)
    blur = neon.filter(ImageFilter.GaussianBlur((2.5 + 2.5 * glow_level) * k))
    blur = ImageChops.add(blur, blur) if glow_level > 0.3 else blur
    img = Image.alpha_composite(img, blur.crop((0, 0, S, S)))
    img = Image.alpha_composite(img, neon)
    gl = Image.new("L", (S, S), 0); ImageDraw.Draw(gl).ellipse([22*k, 6*k, 78*k, 30*k], fill=30)
    gl = ImageChops.multiply(gl, disc)
    img.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), gl)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), disc))
    return img

states = [head(0.0), head(1.0), head(0.5)]
os.makedirs(OUT, exist_ok=True)
for size in (32, 40, 48, 54, 64, 216):
    strip = Image.new("RGBA", (size, size * 3), (0, 0, 0, 0))
    for i, st in enumerate(states):
        strip.paste(st.resize((size, size), Image.LANCZOS), (0, i * size))
    strip.save(os.path.join(OUT, f"alien-orb-{size}.png"))
prev = Image.new("RGBA", (3 * 200, 200), (18, 18, 20, 255))
for i, st in enumerate(states): prev.alpha_composite(st.resize((180, 180), Image.LANCZOS), (10 + i * 200, 10))
prev.save(os.path.join(OUT, "preview.png"))
