"""Audio download/normalisation (ffmpeg) and procedural cover art (Pillow)."""
import hashlib
import math
import os
import subprocess




async def download(url: str, dest: str) -> str:
    import httpx
    root = os.path.dirname(dest)
    dest_real = os.path.realpath(dest)
    root_real = os.path.realpath(root)
    if os.path.commonpath((root_real, dest_real)) != root_real:
        raise ValueError("Download destination is outside the work directory.")
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
    return dest


def to_routenote_flac(src: str, dest: str) -> str:
    """RouteNote accepts FLAC at 44.1kHz; MusicGen outputs 32kHz so resample."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "44100",
                    "-ac", "2", "-sample_fmt", "s16", dest], check=True, timeout=120)
    return dest


def make_cover(title: str, artist: str, seed: str, dest: str, size: int = 3000) -> str:
    """Original generative art, 3000x3000 RGB JPG, text-light (store rules)."""
    from PIL import Image, ImageDraw, ImageFont
    h = hashlib.sha256(seed.encode()).digest()
    c1 = (h[0] // 3, h[1] // 3, 40 + h[2] // 2)
    c2 = (60 + h[3] // 2, 40 + h[4] // 3, 90 + h[5] // 2)
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(0, size):
        t = y / size
        row = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        for x in range(size):
            px[x, y] = row
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(7):
        r = int(size * (0.12 + 0.1 * i))
        cx = size // 2 + int(math.sin(h[6 + i]) * size * 0.1)
        cy = size // 2 + int(math.cos(h[10 + i]) * size * 0.1)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 40 + i * 12), width=14)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size // 14)
        small = ImageFont.truetype("DejaVuSans.ttf", size // 28)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((size // 12, size - size // 5), title[:40], fill=(255, 255, 255, 235), font=font)
    d.text((size // 12, size - size // 8), artist[:50], fill=(255, 255, 255, 190), font=small)
    img.save(dest, "JPEG", quality=92)
    return dest


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, timeout=900, capture_output=True)


def probe_seconds(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], check=True, capture_output=True, text=True, timeout=60)
    return float(out.stdout.strip())


def stitch(files: list[str], master: str, preview: str, fade: float = 2.0) -> None:
    """Crossfade segments into one 44.1kHz/16-bit stereo FLAC master + 192k MP3 preview."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in files:
        cmd += ["-i", f]
    parts = [f"[{i}:a]aresample=44100,aformat=sample_fmts=s16:channel_layouts=stereo[s{i}]"
             for i in range(len(files))]
    last = "s0"
    for i in range(1, len(files)):
        parts.append(f"[{last}][s{i}]acrossfade=d={fade}:c1=tri:c2=tri[x{i}]")
        last = f"x{i}"
    _run(cmd + ["-filter_complex", ";".join(parts), "-map", f"[{last}]", "-c:a", "flac", master])
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", master, "-codec:a", "libmp3lame", "-b:a", "192k", preview])
