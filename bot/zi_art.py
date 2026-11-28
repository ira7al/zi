"""Free procedural cover art, matched to a track's mood. No model, no key, no names.

Four looks (aurora, rings, horizon, dust) are drawn with numpy and PIL from a palette
chosen by the genre and mood words. The seed makes each pick repeatable. Text is never
drawn on the art, so nothing in it can name an artist.
"""
import colorsys
import random
import re

PALETTES = (
    (("techno", "dark", "night", "club", "industrial"), [(0.72, 0.8, 0.12), (0.80, 0.9, 0.45), (0.55, 0.7, 0.9)]),
    (("house", "sunset", "warm", "afro", "summer", "tropical"), [(0.02, 0.85, 0.35), (0.09, 0.8, 0.95), (0.93, 0.7, 0.7)]),
    (("ambient", "calm", "dream", "ocean", "sea", "chill", "piano"), [(0.55, 0.6, 0.18), (0.50, 0.5, 0.75), (0.62, 0.4, 0.95)]),
    (("synth", "retro", "neon", "wave", "disco", "dance"), [(0.83, 0.9, 0.3), (0.5, 0.9, 0.95), (0.95, 0.85, 0.95)]),
    (("sad", "melanchol", "rain", "lonely", "blue"), [(0.6, 0.5, 0.15), (0.58, 0.6, 0.55), (0.7, 0.3, 0.85)]),
    (("epic", "cinematic", "gold", "orchestral", "heroic"), [(0.08, 0.7, 0.14), (0.11, 0.85, 0.85), (0.05, 0.6, 1.0)]),
)
DEFAULT = [(0.68, 0.7, 0.14), (0.75, 0.75, 0.6), (0.52, 0.6, 0.95)]
LOOKS = ("aurora", "rings", "horizon", "dust")


def palette_for(text):
    low = (text or "").lower()
    for words, cols in PALETTES:
        if any(w in low for w in words):
            return cols
    return DEFAULT


def _rgb(hsv):
    r, g, b = colorsys.hsv_to_rgb(*hsv)
    return (r, g, b)


def _blend(np, base, col, mask, k=1.0):
    m = np.clip(mask, 0, 1)[..., None] * k
    return base * (1 - m) + np.array(col)[None, None, :] * m


def render(look, text, seed, size=1500):
    """One image (PIL) for the look, palette from the text, repeatable for a seed."""
    import numpy as np
    from PIL import Image, ImageFilter
    rnd = random.Random(seed)
    cols = [_rgb(c) for c in palette_for(text)]
    dark, mid, light = cols
    n = size
    y, x = np.mgrid[0:n, 0:n].astype("float32") / n
    img = np.zeros((n, n, 3), "float32") + np.array(dark)[None, None, :]
    img += (y[..., None] * 0.35) * np.array(mid)[None, None, :] * 0.5
    if look == "aurora":
        for i in range(5):
            ph, fr, am = rnd.random() * 6, 1.5 + rnd.random() * 2.5, 0.06 + rnd.random() * 0.07
            cy = 0.25 + i * 0.13 + rnd.random() * 0.05
            band = np.exp(-(((y - cy) - am * np.sin(fr * 6.28 * x + ph)) ** 2) / (2 * 0.035 ** 2))
            img = _blend(np, img, cols[(i % 2) + 1], band, 0.55)
    elif look == "rings":
        cx, cy = 0.5 + (rnd.random() - 0.5) * 0.2, 0.5 + (rnd.random() - 0.5) * 0.2
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        for k in range(14):
            rad = 0.06 + k * 0.045
            ring = np.exp(-((r - rad) ** 2) / (2 * (0.004 + 0.0008 * k) ** 2))
            img = _blend(np, img, cols[1 + (k % 2)], ring, 0.8 - k * 0.04)
        img = _blend(np, img, light, np.exp(-(r ** 2) / (2 * 0.06 ** 2)), 0.9)
    elif look == "horizon":
        hz = 0.58
        sun = np.exp(-(((x - 0.5) ** 2) + ((y - 0.42) ** 2)) / (2 * 0.13 ** 2))
        disc = (np.sqrt((x - 0.5) ** 2 + (y - 0.42) ** 2) < 0.17).astype("float32")
        stripes = (np.sin(y * 150) > -0.2 + (y - 0.42) * 4).astype("float32")
        img = _blend(np, img, cols[1], sun, 0.5)
        img = _blend(np, img, light, disc * stripes, 0.95)
        floor = (y > hz).astype("float32")
        gridl = ((np.abs(np.sin((x - 0.5) * 40 / np.maximum(y - hz, 0.02))) > 0.985) |
                 (np.abs(np.sin(1 / np.maximum(y - hz, 0.02) * 3)) > 0.985)).astype("float32")
        img = _blend(np, img, dark, floor, 0.85)
        img = _blend(np, img, cols[1], gridl * floor, 0.7)
    else:  # dust
        img = _blend(np, img, cols[1], np.exp(-((x - 0.3) ** 2 + (y - 0.6) ** 2) / 0.08), 0.35)
        base = Image.fromarray((np.clip(img, 0, 1) * 255).astype("uint8"))
        from PIL import ImageDraw
        glow = Image.new("RGB", (n, n), (0, 0, 0))
        d = ImageDraw.Draw(glow)
        for _ in range(420):
            px, py = rnd.random() * n, rnd.random() * n
            rad = rnd.choice((2, 3, 4, 6, 10)) * n / 1500
            c = tuple(int(255 * v) for v in rnd.choice(cols[1:]))
            d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=c)
        glow = glow.filter(ImageFilter.GaussianBlur(3 * n / 1500))
        a = np.asarray(base).astype("float32") / 255
        b = np.asarray(glow).astype("float32") / 255
        img = np.clip(a + b * 1.2, 0, 1)
    # soft vignette + fine grain so it looks printed, not flat
    v = 1 - 0.55 * (((x - 0.5) ** 2 + (y - 0.5) ** 2) * 2.2)
    img = np.clip(img * v[..., None], 0, 1)
    grain = (np.random.default_rng(seed).normal(0, 0.012, img.shape)).astype("float32")
    img = np.clip(img + grain, 0, 1)
    return Image.fromarray((img * 255).astype("uint8"))


def options(text, base_seed=0, size=1500):
    """Four (look, seed, image) choices, one per look."""
    return [(look, base_seed + i, render(look, text, base_seed + i, size)) for i, look in enumerate(LOOKS)]
