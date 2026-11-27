"""Zi Music Studio desktop app. Python 3.9+, standard library only (Pillow optional for covers, ffmpeg optional for MP3/WAV).
Run: python zi_app.py   -> opens http://127.0.0.1:8765
Data lives in ./zi_data (jobs, library, exports)."""
import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote, unquote

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("ZI_DATA", os.path.join(ROOT, "zi_data"))
JOBS, LIB, EXP = (os.path.join(DATA, d) for d in ("jobs", "library", "exports"))
for d in (JOBS, LIB, EXP):
    os.makedirs(d, exist_ok=True)
STATUS_SEED = os.path.join(ROOT, "status.json")
STATUS = os.path.join(DATA, "status.json")
if not os.path.exists(STATUS) and os.path.exists(STATUS_SEED):
    shutil.copy2(STATUS_SEED, STATUS)
AUDIO_EXT = (".wav", ".mp3", ".flac", ".m4a")
COVER_EXT = (".jpg", ".jpeg", ".png")
ARTIST = WRITER = "Rahal"

PRESETS = {
 "Melodic Techno 122": ("melodic progressive techno", 122, "Warm analog bassline, rolling kick, lush detuned pads, plucky arpeggio lead. Hopeful, late-night. Long intro, build, drop, breakdown, final drop, DJ-friendly outro."),
 "Melodic Techno 124": ("melodic progressive techno", 124, "Punchy kick, sidechained bass, hypnotic minor arpeggio, wide pads, subtle vocal chops. Euphoric but melancholic."),
 "Mid-tempo Techno 118": ("mid-tempo techno", 118, "Heavy rolling bass, dark textures, tight percussion, slow-burning tension."),
 "Afro-Dance Techno 124": ("Afro-dance techno", 124, "Hand percussion, deep bass, hypnotic chant-like hook, warm pads."),
 "Indie Dance 120": ("indie dance", 120, "Bright guitars-like plucks, groovy bass, live-feel drums, nostalgic mood."),
 "Deep House 120": ("deep house", 120, "Warm chords, soft kick, smooth bass, jazzy stabs, relaxed groove."),
 "Downtempo Indie 100": ("downtempo indie", 100, "Dreamy pads, soft beat, intimate mood, slow build."),
}

def now(): return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
def slug(s): return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:60] or "track"
def read_json(p, default=None):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return default
def write_json(p, o):
    with open(p, "w", encoding="utf-8") as f: json.dump(o, f, indent=2, ensure_ascii=False)

def load_status():
    st = read_json(STATUS) or read_json(STATUS_SEED) or {"updated": "", "items": []}
    return st

def save_status(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
        raise ValueError("status.json must be an object with an items list")
    obj["updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    write_json(STATUS, obj)
    return obj

def make_job(d):
    pre = d.get("preset") or "Melodic Techno 122"
    genre, bpm, desc = PRESETS.get(pre, PRESETS["Melodic Techno 122"])
    minutes = max(1.0, min(10.0, float(d.get("minutes") or 5.5)))
    instr = bool(d.get("instrumental", True))
    lyrics = "[Instrumental]" if instr else (d.get("lyrics") or "").strip()
    if not instr and not lyrics: raise ValueError("Add lyrics or tick Instrumental")
    title = (d.get("title") or "").strip() or f"{genre.title()} {now()[4:8]}"
    job = {"id": now() + "-" + slug(title)[:20], "title": title, "preset": pre, "genre": genre, "bpm": bpm,
           "style_prompt": f"{bpm} BPM {genre}. {desc} {d.get('idea','').strip()}".strip(),
           "seconds": int(minutes * 60), "instrumental": instr, "lyrics": lyrics,
           "artist": ARTIST, "writer": WRITER, "status": "queued", "ai_generated": True}
    write_json(os.path.join(JOBS, job["id"] + ".json"), job)
    return job

def list_jobs():
    out = [read_json(os.path.join(JOBS, f)) for f in sorted(os.listdir(JOBS), reverse=True) if f.endswith(".json")]
    return [j for j in out if j]

def find_cover(p):
    base = os.path.splitext(p)[0]
    for e in COVER_EXT:
        if os.path.isfile(base + e): return base + e
    d = os.path.dirname(p)
    for n in ("cover", "folder", "front"):
        for e in COVER_EXT:
            c = os.path.join(d, n + e)
            if os.path.isfile(c): return c
    return None

def scan_library():
    items = []
    for dp, _, fs in os.walk(LIB):
        for f in fs:
            if f.lower().endswith(AUDIO_EXT):
                p = os.path.join(dp, f); base = os.path.splitext(p)[0]
                meta = read_json(base + ".json", {}) or {}
                items.append({"id": os.path.relpath(p, LIB).replace(os.sep, "/"), "title": meta.get("title") or os.path.splitext(f)[0],
                              "genre": meta.get("genre", ""), "bpm": meta.get("bpm", ""), "size_mb": round(os.path.getsize(p)/1e6, 1),
                              "cover": bool(find_cover(p)),
                              "date": datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")})
    return sorted(items, key=lambda x: x["date"], reverse=True)

def import_folder(src):
    if not os.path.isdir(src): raise ValueError("Folder not found: " + src)
    n = 0
    for dp, _, fs in os.walk(src):
        for f in fs:
            if f.lower().endswith(AUDIO_EXT + (".json",)):
                dst = os.path.join(LIB, f)
                if not os.path.exists(dst): shutil.copy2(os.path.join(dp, f), dst); n += f.lower().endswith(AUDIO_EXT)
    return n

def make_cover(path, title, seed):
    try: from PIL import Image, ImageDraw
    except ImportError: return False
    rnd = random.Random(seed); S = 3000
    c1 = tuple(rnd.randint(0, 80) for _ in range(3)); c2 = tuple(rnd.randint(80, 255) for _ in range(3))
    img = Image.new("RGB", (S, S)); px = ImageDraw.Draw(img)
    for y in range(S):
        t = y / S; px.line([(0, y), (S, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    ov = ImageDraw.Draw(img, "RGBA")
    for _ in range(14):
        r = rnd.randint(200, 1100); x, y = rnd.randint(0, S), rnd.randint(0, S)
        ov.ellipse([x-r, y-r, x+r, y+r], outline=tuple(rnd.randint(80, 255) for _ in range(3)) + (110,), width=rnd.randint(6, 30))
    img.save(path, quality=95); return True

def export_release(track_id, title, genre, language="Instrumental", explicit="No"):
    known = [it["id"] for it in scan_library()]
    if track_id not in known: raise ValueError("Track not found")
    src = os.path.normpath(os.path.join(LIB, track_id))
    if src.startswith(os.path.normpath(LIB)) and os.path.isfile(src):
        meta_p = os.path.normpath(os.path.splitext(src)[0] + ".json")
        meta = read_json(meta_p, {}) if meta_p.startswith(os.path.normpath(LIB)) else {}
        title = title or meta.get("title") or os.path.splitext(os.path.basename(src))[0]
        genre = genre or meta.get("genre") or "Electronic"
        out = os.path.join(EXP, now() + "-" + slug(title)); os.makedirs(out)
        ff = shutil.which("ffmpeg"); notes = []
        if ff:
            subprocess.run([ff, "-y", "-i", src, "-ar", "44100", "-sample_fmt", "s16", os.path.join(out, slug(title) + ".wav")], capture_output=True)
            subprocess.run([ff, "-y", "-i", src, "-b:a", "320k", "-ar", "44100", os.path.join(out, slug(title) + ".mp3")], capture_output=True)
        else:
            shutil.copy2(src, out); notes.append("ffmpeg not found: original audio copied, convert to 44.1 kHz WAV/320k MP3 yourself (install ffmpeg to automate).")
        if not make_cover(os.path.join(out, "cover_3000x3000.jpg"), title, title):
            notes.append("Pillow missing: run 'pip install pillow' for the 3000x3000 cover, or add your own.")
        row = {"Title": title, "Artist": ARTIST, "Writer": WRITER, "Genre": genre, "Language": language, "Explicit": explicit,
               "AI generated": "Yes (AI-assisted, disclose per RouteNote policy)", "Release date": ""}
        with open(os.path.join(out, "metadata.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row)); w.writeheader(); w.writerow(row)
        with open(os.path.join(out, "routenote_form.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(f"{k}: {v}" for k, v in row.items()) + "\n\nUpload by hand at routenote.com. Check RouteNote's current AI-content policy first.\n" + "\n".join(notes) + "\n")
        z = out + ".zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in os.listdir(out): zf.write(os.path.join(out, fn), fn)
        return {"folder": out, "zip": z, "notes": notes}
    else:
        raise ValueError("Track not found")


HTML = r"""<!doctype html>
<html lang="en" dir="ltr" data-theme="dark">
<head>
<meta charset="utf-8">
<title>Zi Music Studio</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Zi Music Studio - Rahal's AI-assisted music studio">
<style>
:root{
  --bg:#0b0d13;--card:#141824;--card2:#0f1219;--line:#232a3d;
  --tx:#eef0f8;--mut:#a2a8c4;--ac:#7c5cff;--ac2:#00d4ff;
  --good:#34d399;--warn:#fbbf24;--info:#38bdf8;--bad:#f87171;
  --shadow:0 8px 24px rgba(0,0,0,.35);color-scheme:dark;
}
[data-theme=light]{
  --bg:#f2f4fa;--card:#ffffff;--card2:#f6f8fd;--line:#e2e7f3;
  --tx:#181b28;--mut:#5c6478;--shadow:0 8px 24px rgba(23,27,60,.08);color-scheme:light;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Tahoma,sans-serif;min-height:100vh}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(900px 500px at 85% -10%,rgba(124,92,255,.14),transparent 60%),radial-gradient(700px 420px at 0% 0%,rgba(0,212,255,.08),transparent 55%)}
[dir=rtl] body::before{background:radial-gradient(900px 500px at 15% -10%,rgba(124,92,255,.14),transparent 60%),radial-gradient(700px 420px at 100% 0%,rgba(0,212,255,.08),transparent 55%)}
a{color:var(--ac2)}
button{font:inherit;cursor:pointer}
:focus-visible{outline:2px solid var(--ac2);outline-offset:2px;border-radius:6px}
.skip{position:absolute;inset-inline-start:8px;top:-48px;background:var(--ac);color:#fff;padding:8px 14px;border-radius:8px;z-index:50;transition:top .15s}
.skip:focus{top:8px}

/* ---------- header ---------- */
header{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:12px 22px;background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:baseline;gap:10px;font-size:20px;font-weight:800;letter-spacing:.2px}
.brand .logo{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--ac),var(--ac2));display:grid;place-items:center;color:#fff;font-size:18px;box-shadow:var(--shadow)}
.brand b{background:linear-gradient(90deg,var(--ac),var(--ac2));-webkit-background-clip:text;background-clip:text;color:transparent}
.brand small{color:var(--mut);font-weight:400;font-size:12px}
nav.tabs{display:flex;gap:4px;background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:4px;margin-inline-start:auto}
nav.tabs button{border:0;background:transparent;color:var(--mut);padding:7px 16px;border-radius:9px;font-weight:600;display:flex;gap:7px;align-items:center}
nav.tabs button.on{background:linear-gradient(135deg,var(--ac),#5b8cff);color:#fff;box-shadow:0 2px 10px rgba(124,92,255,.4)}
nav.tabs svg{width:15px;height:15px}
.hdrbtn{border:1px solid var(--line);background:var(--card2);color:var(--mut);border-radius:10px;padding:7px 11px;font-weight:700;display:flex;align-items:center;gap:6px}
.hdrbtn:hover{color:var(--tx);border-color:var(--ac)}
.hdrbtn svg{width:15px;height:15px}

/* ---------- layout ---------- */
.wrap{max-width:1240px;margin:auto;padding:22px;position:relative;z-index:1}
.view{display:none}
.view.on{display:block}
.grid2{display:grid;grid-template-columns:400px 1fr;gap:20px;align-items:start}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:20px;box-shadow:var(--shadow)}
.card h2{margin:0 0 6px;font-size:17px;display:flex;align-items:center;gap:9px}
.card h2 .ic{width:27px;height:27px;border-radius:8px;background:color-mix(in srgb,var(--ac) 20%,transparent);display:grid;place-items:center;color:var(--ac)}.card h2 .ic svg{width:15px;height:15px}
.sub{color:var(--mut);font-size:12.5px;margin:0 0 12px}
label{display:block;color:var(--mut);font-size:12px;font-weight:600;margin:12px 0 5px}
input,select,textarea{width:100%;background:var(--card2);color:var(--tx);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font:inherit}
input:focus,select:focus,textarea:focus{border-color:var(--ac);outline:none}
textarea{min-height:90px;resize:vertical}
input[type=range]{accent-color:var(--ac);padding:0}
input[type=checkbox]{width:auto;accent-color:var(--ac);transform:scale(1.15)}
.check{display:flex;align-items:center;gap:8px;margin:12px 0 0;color:var(--tx);font-size:14px;font-weight:400}
.btn{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,var(--ac),#5b8cff);color:#fff;border:0;border-radius:10px;padding:11px 18px;font-weight:700;margin-top:14px;box-shadow:0 3px 12px rgba(124,92,255,.35)}
.btn:hover{filter:brightness(1.08)}
.btn.sec{background:var(--card2);color:var(--tx);border:1px solid var(--line);box-shadow:none}
.btn.sec:hover{border-color:var(--ac)}
#msg{margin:10px 0 0;min-height:20px;font-size:13.5px;color:var(--good)}
#msg.err{color:var(--bad)}

/* ---------- tables ---------- */
.twrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
table{width:100%;border-collapse:collapse;min-width:520px}
td,th{padding:10px 12px;border-bottom:1px solid var(--line);text-align:start;font-size:13.5px}
th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;background:var(--card2)}
tr:last-child td{border-bottom:0}
tbody tr:hover{background:color-mix(in srgb,var(--ac) 6%,transparent)}
.tag{font-size:11.5px;padding:3px 10px;border-radius:20px;background:var(--card2);border:1px solid var(--line);color:var(--mut);white-space:nowrap}
.t-queued{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 40%,transparent)}
.t-rendered,.t-done{color:var(--good);border-color:color-mix(in srgb,var(--good) 40%,transparent)}

/* ---------- library ---------- */
.tracks{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:16px}
.trk{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--shadow);display:flex;flex-direction:column;transition:transform .15s,border-color .15s}
.trk:hover{transform:translateY(-3px);border-color:var(--ac)}
.cov{position:relative;aspect-ratio:1;display:grid;place-items:center;color:rgba(255,255,255,.92);font-size:34px;font-weight:800;text-shadow:0 2px 10px rgba(0,0,0,.4);background-size:cover;background-position:center}
.cov .playb{position:absolute;inset-inline-end:10px;bottom:10px;width:42px;height:42px;border-radius:50%;border:0;background:linear-gradient(135deg,var(--ac),#5b8cff);color:#fff;display:grid;place-items:center;box-shadow:0 4px 14px rgba(0,0,0,.45);opacity:0;transform:scale(.85);transition:opacity .15s,transform .15s}
.trk:hover .playb,.trk:focus-within .playb{opacity:1;transform:scale(1)}
.cov .playb svg{width:17px;height:17px}
.trk .inf{padding:11px 13px;display:flex;flex-direction:column;gap:3px;flex:1}
.trk .tt{font-weight:700;font-size:13.5px;line-height:1.3}
.trk .mt{color:var(--mut);font-size:11.5px}
.trk .act{display:flex;gap:8px;padding:0 13px 12px}
.trk .act button{flex:1;border:1px solid var(--line);background:var(--card2);color:var(--mut);border-radius:9px;padding:7px 6px;font-size:12px;font-weight:600;line-height:1.25;overflow-wrap:anywhere}
.trk .act button:hover{color:var(--tx);border-color:var(--ac)}
.trk.playing{border-color:var(--ac);box-shadow:0 0 0 1px var(--ac),var(--shadow)}
.empty{color:var(--mut);text-align:center;padding:40px 10px;border:1px dashed var(--line);border-radius:14px;font-size:14px}

/* ---------- dashboard ---------- */
.ovstats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin:14px 0}
.stat{background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.stat b{font-size:24px;display:block;line-height:1.1}
.stat span{color:var(--mut);font-size:11.5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.stat.s-live b{color:var(--good)}.stat.s-progress b{color:var(--warn)}.stat.s-done b{color:var(--info)}.stat.s-pending b{color:var(--mut)}
.bigbar{height:12px;background:var(--card2);border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-top:4px}
.bigbar i{display:block;height:100%;border-radius:8px;background:linear-gradient(90deg,var(--ac),var(--ac2));transition:width .6s ease}
.ovlabel{display:flex;justify-content:space-between;color:var(--mut);font-size:12px;margin:12px 0 5px;font-weight:600}
.liveind{display:inline-flex;align-items:center;gap:6px;color:var(--good);font-size:11.5px;font-weight:700}
.liveind i{width:8px;height:8px;border-radius:50%;background:var(--good);animation:pulse 1.8s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(265px,1fr));gap:14px;margin-top:14px}
.tile{display:block;background:var(--card2);border:1px solid var(--line);border-radius:13px;padding:14px 16px;color:inherit;text-decoration:none;transition:border-color .15s,transform .15s}
.tile:hover{border-color:var(--ac);transform:translateY(-2px)}
.tile .grp{display:flex;align-items:center;gap:8px;font-size:10.5px;color:var(--mut);margin-bottom:7px;text-transform:uppercase;letter-spacing:.6px;font-weight:700}
.tile .grp .gic{width:22px;height:22px;border-radius:7px;background:color-mix(in srgb,var(--ac) 16%,transparent);display:grid;place-items:center;font-size:12px}
.tile h3{margin:0 0 7px;font-size:14.5px}
.tile .en{font-size:11px;color:var(--mut);margin:-3px 0 6px}
.tile p{margin:8px 0 0;font-size:12.5px;color:var(--mut);line-height:1.5}
.tile .openbtn{position:relative;display:inline-flex;align-items:center;gap:7px;margin-top:11px;padding:6px 0;padding-inline:13px 7px;border-radius:99px;font-size:12px;font-weight:800;color:#fff;background:linear-gradient(135deg,var(--ac),var(--ac2));box-shadow:0 2px 10px rgba(124,92,255,.35);overflow:hidden;transition:transform .18s,box-shadow .28s,filter .18s;animation:obglow 2.8s ease-in-out infinite}
.tile .openbtn .ob-tx{position:relative;z-index:1;letter-spacing:.2px}
.tile .openbtn .ob-ic{position:relative;z-index:1;width:20px;height:20px;border-radius:50%;background:rgba(255,255,255,.22);display:grid;place-items:center;overflow:hidden;transition:background .22s}
.tile .openbtn .ob-ic svg{position:absolute;width:11px;height:11px;transition:transform .32s cubic-bezier(.3,1.35,.5,1)}
.tile .openbtn .ob-ic svg.ob-b{transform:translate(-160%,160%)}
.tile .openbtn::before{content:"";position:absolute;inset:0;background:linear-gradient(115deg,transparent 32%,rgba(255,255,255,.55) 50%,transparent 68%);transform:translateX(-130%);pointer-events:none}
.tile:hover .openbtn,.tile:focus-visible .openbtn{transform:translateY(-1px) scale(1.05);filter:saturate(1.15);box-shadow:0 4px 20px rgba(124,92,255,.65),0 0 16px rgba(0,212,255,.4);animation-play-state:paused}
.tile:hover .openbtn::before,.tile:focus-visible .openbtn::before{animation:obsheen .9s ease forwards}
.tile:hover .openbtn .ob-ic,.tile:focus-visible .openbtn .ob-ic{background:rgba(255,255,255,.34)}
.tile:hover .openbtn .ob-ic svg.ob-a,.tile:focus-visible .openbtn .ob-ic svg.ob-a{transform:translate(160%,-160%)}
.tile:hover .openbtn .ob-ic svg.ob-b,.tile:focus-visible .openbtn .ob-ic svg.ob-b{transform:translate(0,0)}
[dir=rtl] .tile .openbtn .ob-ic svg.ob-b{transform:translate(160%,160%)}
[dir=rtl] .tile .openbtn .ob-ic svg path{transform:scaleX(-1);transform-box:fill-box;transform-origin:center}
[dir=rtl] .tile:hover .openbtn .ob-ic svg.ob-a,[dir=rtl] .tile:focus-visible .openbtn .ob-ic svg.ob-a{transform:translate(-160%,-160%)}
.tile:active .openbtn{transform:scale(.93);box-shadow:0 1px 6px rgba(124,92,255,.4)}
@keyframes obsheen{to{transform:translateX(130%)}}
@keyframes obglow{0%,100%{box-shadow:0 2px 10px rgba(124,92,255,.35)}50%{box-shadow:0 3px 16px rgba(0,212,255,.55)}}
.pbar{height:5px;background:var(--line);border-radius:4px;overflow:hidden;margin-top:11px}
.pbar i{display:block;height:100%;border-radius:4px}
.pb-live i{background:var(--good);width:100%}.pb-done i{background:var(--info);width:100%}
.pb-progress i{background:var(--warn);width:50%}.pb-block i{background:var(--bad);width:22%}.pb-pending i{background:var(--mut);width:8%}
.badge{font-size:11px;padding:3px 10px;border-radius:20px;font-weight:700;white-space:nowrap}
.b-live{background:color-mix(in srgb,var(--good) 16%,transparent);color:var(--good)}
.b-progress{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}
.b-done{background:color-mix(in srgb,var(--info) 16%,transparent);color:var(--info)}
.b-pending{background:var(--card);color:var(--mut);border:1px solid var(--line)}
.b-block{background:color-mix(in srgb,var(--bad) 16%,transparent);color:var(--bad)}
.chip{display:inline-block;background:var(--card);border:1px solid var(--line);color:var(--mut);font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;margin:8px 6px 0 0;text-decoration:none}
.chip:hover{border-color:var(--ac);color:var(--tx)}
.sechead{margin:26px 0 4px;font-size:16px;font-weight:800;display:flex;align-items:center;gap:9px}
.secintro{color:var(--mut);font-size:13px;margin:0 0 4px}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px;min-height:280px;direction:ltr;text-align:left}

/* ---------- player ---------- */
#player{position:fixed;inset-inline:0;bottom:0;z-index:30;display:none;background:color-mix(in srgb,var(--card) 92%,transparent);backdrop-filter:blur(14px);border-top:1px solid var(--line);padding:10px 16px calc(10px + env(safe-area-inset-bottom))}
#player.on{display:block}
.pwrap{max-width:1240px;margin:auto;display:grid;grid-template-columns:auto auto 1fr auto;gap:14px;align-items:center;direction:ltr}
.pcov{width:52px;height:52px;border-radius:10px;background-size:cover;background-position:center;display:grid;place-items:center;color:#fff;font-weight:800;box-shadow:var(--shadow)}
.pmeta{min-width:0}
.pmeta .pt{font-weight:700;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px}
.pmeta .ps{color:var(--mut);font-size:11px}
.pctl{display:flex;gap:6px}
.pctl button{width:38px;height:38px;border-radius:50%;border:1px solid var(--line);background:var(--card2);color:var(--tx);display:grid;place-items:center}
.pctl button:hover{border-color:var(--ac)}
.pctl .main{background:linear-gradient(135deg,var(--ac),#5b8cff);border:0;color:#fff;width:44px;height:44px}
.pctl svg{width:16px;height:16px}
.pwave{display:flex;align-items:center;gap:10px;min-width:0}
#wave{flex:1;height:52px;cursor:pointer;min-width:80px}
.ptime{font-size:11px;color:var(--mut);font-variant-numeric:tabular-nums;white-space:nowrap}
body.playing .wrap{padding-bottom:96px}

/* ---------- responsive ---------- */
@media(max-width:920px){.grid2{grid-template-columns:1fr}.brand small{display:none}}
@media(max-width:640px){
  header{padding:10px 12px;gap:8px}
  nav.tabs{order:3;width:100%;margin:0}
  nav.tabs button{flex:1;justify-content:center;padding:8px 6px;font-size:13px}
  .wrap{padding:14px 12px}
  .tracks{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:11px}.trk .act{flex-direction:column}
  .tiles{grid-template-columns:1fr}
  .pwrap{grid-template-columns:auto 1fr auto;gap:10px}
  .pmeta{display:none}
  table{min-width:460px}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<a class="skip" href="#main" data-i18n="skip">Skip to content</a>
<canvas id="stars" aria-hidden="true"></canvas>
<div class="orb o1" aria-hidden="true"></div><div class="orb o2" aria-hidden="true"></div>
<style>
/* ============ FX layer ============ */
#stars{position:fixed;inset:0;z-index:0;pointer-events:none}
.orb{position:fixed;border-radius:50%;filter:blur(80px);opacity:.4;pointer-events:none;z-index:0}
.o1{width:420px;height:420px;background:radial-gradient(circle,#7c5cff,transparent 65%);top:-140px;inset-inline-end:-120px;animation:drift1 26s ease-in-out infinite alternate}
.o2{width:360px;height:360px;background:radial-gradient(circle,#00d4ff,transparent 65%);bottom:-140px;inset-inline-start:-120px;animation:drift2 32s ease-in-out infinite alternate}
@keyframes drift1{to{transform:translate(-90px,120px) scale(1.15)}}
@keyframes drift2{to{transform:translate(110px,-100px) scale(1.1)}}
.card,.tile,.trk,.stat,#player,header{backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
.card{background:color-mix(in srgb,var(--card) 74%,transparent)}
.tile,.stat{background:color-mix(in srgb,var(--card2) 68%,transparent)}
.trk{background:color-mix(in srgb,var(--card) 78%,transparent)}
.card,.tile,.trk{border-color:color-mix(in srgb,var(--ac) 14%,var(--line))}
.tilt{position:relative;transform-style:preserve-3d;will-change:transform;transition:transform .2s ease,border-color .15s,box-shadow .2s}
.tilt::after{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;opacity:0;transition:opacity .25s;
  background:radial-gradient(340px circle at var(--gx,50%) var(--gy,50%),rgba(255,255,255,.16),transparent 46%)}
.tilt:hover::after{opacity:1}
.tile,.trk{overflow:hidden}
.view.on{animation:vin .42s cubic-bezier(.22,.9,.3,1) both}
@keyframes vin{from{opacity:0;transform:translateX(30px) scale(.985);filter:blur(3px)}to{opacity:1;transform:none;filter:none}}
[dir=rtl] .view.on{animation-name:vinr}
@keyframes vinr{from{opacity:0;transform:translateX(-30px) scale(.985);filter:blur(3px)}to{opacity:1;transform:none;filter:none}}
button{position:relative;overflow:hidden}
.ripple{position:absolute;border-radius:50%;background:rgba(255,255,255,.4);transform:scale(0);animation:rip .55s ease-out forwards;pointer-events:none;mix-blend-mode:screen}
@keyframes rip{to{transform:scale(3.4);opacity:0}}
.spin{display:none;width:15px;height:15px;border:2px solid rgba(255,255,255,.45);border-top-color:#fff;border-radius:50%;animation:rot .7s linear infinite}
.btn.loading .spin{display:inline-block}
.btn.loading{pointer-events:none;filter:saturate(.7)}
@keyframes rot{to{transform:rotate(360deg)}}
.logo.spinonce{animation:logospin .65s cubic-bezier(.3,1.4,.5,1)}
@keyframes logospin{0%{transform:rotate(0) scale(1)}45%{transform:rotate(200deg) scale(1.25)}100%{transform:rotate(360deg) scale(1)}}
.skel{border-radius:12px;min-height:150px;background:linear-gradient(90deg,var(--card2) 25%,color-mix(in srgb,var(--card2) 35%,var(--line)) 50%,var(--card2) 75%);background-size:220% 100%;animation:shim 1.15s linear infinite}
@keyframes shim{to{background-position:-220% 0}}
.skelrow{height:46px;min-height:46px;margin-bottom:8px}
#player{box-shadow:0 -8px 40px rgba(124,92,255,calc(.12 + var(--pg,0)*.3))}
#player::before{content:"";position:absolute;inset-inline:0;top:-34px;height:34px;pointer-events:none;
  background:linear-gradient(to top,rgba(124,92,255,calc(var(--pg,0)*.5)),transparent)}
.pctl .main{box-shadow:0 0 calc(12px + var(--pg,0)*22px) rgba(124,92,255,calc(.45 + var(--pg,0)*.4));transition:box-shadow .1s}
.eq{position:absolute;inset-inline-start:10px;bottom:12px;display:none;gap:3px;align-items:flex-end;height:26px}
.eq i{width:4px;border-radius:2px;background:linear-gradient(to top,var(--ac2),#fff);height:15%;box-shadow:0 0 6px rgba(0,212,255,.7)}
.trk.playing .eq{display:flex}
.brand .logo{box-shadow:0 0 18px rgba(124,92,255,.55)}
.sechead .sic{width:24px;height:24px;color:var(--ac);filter:drop-shadow(0 0 8px rgba(124,92,255,.6))}.sechead .sic svg{width:100%;height:100%}
.glowline{height:2px;border:0;margin:0 0 16px;background:linear-gradient(90deg,transparent,var(--ac),var(--ac2),transparent);opacity:.6}
@media(prefers-reduced-motion:reduce){.orb{display:none}#stars{display:none}.view.on{animation:none}.tilt{transition:none}}
</style>
<header>
  <div class="brand"><span class="logo" id="logo" aria-hidden="true">&#9835;</span><span>Zi <b>Music Studio</b></span><small data-i18n="tagline">artist Rahal &middot; AI-assisted &middot; free</small></div>
  <nav class="tabs" aria-label="Main">
    <button id="navS" class="on" data-view="studio" aria-current="page"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/></svg><span data-i18n="studio">Studio</span></button>
    <button id="navL" data-view="library"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg><span data-i18n="library">Library</span></button>
    <button id="navD" data-view="dashboard"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg><span data-i18n="dashboard">Dashboard</span></button>
  </nav>
  <button class="hdrbtn" id="themeBtn" aria-label="Toggle dark / light"><svg id="themeIco" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></button>
  <button class="hdrbtn" id="langBtn" aria-label="Switch language">EN</button>
</header>
<div class="wrap" id="main">
  <section class="view on" id="view-studio" aria-label="Studio">
    <div class="grid2">
      <div>
        <div class="card">
          <h2><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/></svg></span><span data-i18n="newtrack">New track</span></h2>
          <hr class="glowline">
          <label for="preset" data-i18n="preset">Style preset</label><select id="preset"></select>
          <label for="title" data-i18n="title">Title (optional)</label><input id="title">
          <label for="minutes"><span data-i18n="length">Length</span>: <b id="lenv">5.5</b> <span data-i18n="min">min</span></label>
          <input id="minutes" type="range" min="1" max="10" step="0.5" value="5.5">
          <div class="check"><input type="checkbox" id="instr" checked><label for="instr" style="margin:0" data-i18n="instr">Instrumental (no lyrics)</label></div>
          <div id="lyr" style="display:none"><label for="lyrics" data-i18n="lyrics">Lyrics</label><textarea id="lyrics" placeholder="[Verse] ..."></textarea></div>
          <label for="idea" data-i18n="idea">Extra idea / mood (optional)</label><input id="idea" data-i18n-ph="ideaph" placeholder="e.g. sunrise over the Red Sea">
          <button class="btn" id="mkBtn"><span class="spin" aria-hidden="true"></span><span data-i18n="create">Create generation job</span></button>
          <div id="msg" role="status" aria-live="polite"></div>
          <p class="sub" style="margin-top:12px" data-i18n="jobnote">Jobs are saved to zi_data/jobs. Load the .json in the Colab notebook to render, or copy the style prompt.</p>
        </div>
        <div class="card">
          <h2><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M6 11l6 6 6-6M4 21h16"/></svg></span><span data-i18n="import">Import finished tracks</span></h2>
          <label for="imp" data-i18n="folder">Folder (e.g. your Google Drive sync folder Zi_Music)</label>
          <input id="imp" placeholder="C:\Users\you\Google Drive\Zi_Music">
          <button class="btn sec" id="imBtn"><span class="spin" aria-hidden="true"></span><span data-i18n="importbtn">Import into library</span></button>
        </div>
      </div>
      <div class="card">
        <h2><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/></svg></span><span data-i18n="jobs">Jobs</span></h2>
        <div class="twrap"><table id="jobs" aria-label="Generation jobs"></table></div>
      </div>
    </div>
  </section>
  <section class="view" id="view-library" aria-label="Library">
    <div class="card">
      <h2><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></span><span data-i18n="library">Library</span>&nbsp;<span class="liveind" style="color:var(--mut);font-weight:600"><i style="background:var(--ac2);animation:none"></i><span id="libcount"></span></span></h2>
      <p class="sub" data-i18n="libnote">Rendered tracks. Click a cover to play with the live visualizer, or export a RouteNote release pack.</p>
      <div class="tracks" id="tracksGrid"></div>
    </div>
  </section>
  <section class="view" id="view-dashboard" aria-label="Dashboard">
    <div class="card">
      <h2><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/></svg></span><span data-i18n="overview">Project overview</span>&nbsp;<span class="liveind"><i></i><span data-i18n="live">live</span></span></h2>
      <p class="sub"><span data-i18n="ovnote">Every page and asset of the project, auto-refreshed from zi_data/status.json.</span> <span id="supdated"></span></p>
      <div class="ovstats" id="ovstats"></div>
      <div class="ovlabel"><span data-i18n="overall">Overall progress</span><span id="ovpct"></span></div>
      <div class="bigbar"><i id="ovbar" style="width:0"></i></div>
      <div class="tiles" id="tiles"></div>
      <div id="sections"></div>
    </div>
    <div class="card">
      <h2><span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3l4 4L8 20l-5 1 1-5z"/></svg></span><span data-i18n="editstatus">Edit status</span></h2>
      <p class="sub" data-i18n="editnote">Live status is read from zi_data/status.json. The team updates it as work moves; you can also edit it here and save.</p>
      <textarea id="sedit" class="mono" aria-label="status.json editor"></textarea>
      <button class="btn sec" id="svBtn"><span class="spin" aria-hidden="true"></span><span data-i18n="save">Save status</span></button>
      <span id="smsg" style="color:var(--good);margin-inline-start:10px" role="status"></span>
    </div>
  </section>
</div>
<div id="player" role="region" aria-label="Player">
  <div class="pwrap">
    <div class="pcov" id="pcov" aria-hidden="true">&#9835;</div>
    <div class="pmeta"><div class="pt" id="pt"></div><div class="ps" id="ps"></div></div>
    <div class="pctl">
      <button id="pprev" aria-label="Previous track"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h2v14H6zM20 5v14L9 12z"/></svg></button>
      <button id="pplay" class="main" aria-label="Play / pause"><svg id="pplayIco" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>
      <button id="pnext" aria-label="Next track"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 5h2v14h-2zM4 5v14l11-7z"/></svg></button>
    </div>
    <div class="pwave">
      <span class="ptime" id="tcur">0:00</span>
      <canvas id="wave" aria-label="Waveform seek bar" role="slider" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" tabindex="0"></canvas>
      <span class="ptime" id="ttot">0:00</span>
      <button id="pclose" class="hdrbtn" aria-label="Close player" style="padding:6px 9px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
    </div>
  </div>
  <audio id="au" crossorigin="anonymous"></audio>
</div>
<style>
.pburst{position:fixed;z-index:60;font-size:19px;pointer-events:none;animation:pop .9s cubic-bezier(.2,.7,.3,1) forwards;filter:drop-shadow(0 2px 6px rgba(0,0,0,.3))}
@keyframes pop{0%{transform:translate(-50%,-50%) scale(.3);opacity:1}75%{opacity:1}100%{transform:translate(calc(-50% + var(--dx)),calc(-50% + var(--dy))) scale(1.2) rotate(var(--rr));opacity:0}}
@media(prefers-reduced-motion:reduce){.pburst{display:none}}
</style>
<script>
"use strict";
const $=id=>document.getElementById(id);
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const j=(u,o)=>fetch(u,o).then(r=>r.json());
const post=(u,b)=>j(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hash=s=>{let h=0;for(const c of String(s))h=(h*31+c.charCodeAt(0))>>>0;return h};
let LANG=localStorage.getItem('zi-lang')||'en';
const T={
en:{skip:"Skip to content",tagline:"artist Rahal \u00b7 AI-assisted \u00b7 free",studio:"Studio",library:"Library",dashboard:"Dashboard",
newtrack:"New track",preset:"Style preset",title:"Title (optional)",length:"Length",min:"min",instr:"Instrumental (no lyrics)",lyrics:"Lyrics",
idea:"Extra idea / mood (optional)",ideaph:"e.g. sunrise over the Red Sea",create:"Create generation job",
jobnote:"Jobs are saved to zi_data/jobs. Load the .json in the Colab notebook to render, or copy the style prompt.",
import:"Import finished tracks",folder:"Folder (e.g. your Google Drive sync folder Zi_Music)",importbtn:"Import into library",jobs:"Jobs",
libnote:"Rendered tracks. Click a cover to play with the live visualizer, or export a RouteNote release pack.",
overview:"Project overview",live:"live",ovnote:"Every page and asset of the project, auto-refreshed from zi_data/status.json.",
overall:"Overall progress",editstatus:"Edit status",editnote:"Live status is read from zi_data/status.json. The team updates it as work moves; you can also edit it here and save.",
save:"Save status",play:"Play",export:"RouteNote export",notracks:"No tracks yet. Create a job in the Studio or import a folder.",
nojobs:"No jobs yet.",th_title:"Title",th_style:"Style",th_length:"Length",th_status:"Status",savedjob:"Saved job: ",imported:"Imported ",
tracksuffix:" track(s)",exported:"Exported: ",open:"open",updated:"last updated ",s_live:"Live",s_progress:"In progress",s_done:"Done",s_pending:"Pending",
loading:"Loading...",min2:"min",invalid:"Invalid JSON: ",saved:"Saved",tracksN:"tracks"},
ar:{skip:"\u062a\u062e\u0637\u064a \u0644\u0644\u0645\u062d\u062a\u0648\u0649",tagline:"\u0627\u0644\u0641\u0646\u0627\u0646 \u0631\u062d\u0627\u0644 \u00b7 \u0628\u0627\u0644\u0630\u0643\u0627\u0621 \u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a \u00b7 \u0645\u062c\u0627\u0646\u064a",
studio:"\u0627\u0644\u0633\u062a\u0648\u062f\u064a\u0648",library:"\u0627\u0644\u0645\u0643\u062a\u0628\u0629",dashboard:"\u0644\u0648\u062d\u0629 \u0627\u0644\u0645\u062a\u0627\u0628\u0639\u0629",
newtrack:"\u062a\u0631\u0627\u0643 \u062c\u062f\u064a\u062f",preset:"\u0627\u0644\u0633\u062a\u0627\u064a\u0644 \u0627\u0644\u062c\u0627\u0647\u0632",title:"\u0627\u0644\u0627\u0633\u0645 (\u0627\u062e\u062a\u064a\u0627\u0631\u064a)",
length:"\u0627\u0644\u0645\u062f\u0629",min:"\u062f\u0642\u064a\u0642\u0629",instr:"\u0645\u0648\u0633\u064a\u0642\u0649 \u0628\u0633 (\u0645\u0646 \u063a\u064a\u0631 \u0643\u0644\u0645\u0627\u062a)",lyrics:"\u0627\u0644\u0643\u0644\u0645\u0627\u062a",
idea:"\u0641\u0643\u0631\u0629 \u0623\u0648 \u0645\u0648\u062f \u0625\u0636\u0627\u0641\u064a (\u0627\u062e\u062a\u064a\u0627\u0631\u064a)",ideaph:"\u0645\u062b\u0627\u0644: \u0634\u0631\u0648\u0642 \u0627\u0644\u0634\u0645\u0633 \u0639\u0644\u0649 \u0627\u0644\u0628\u062d\u0631 \u0627\u0644\u0623\u062d\u0645\u0631",
create:"\u0627\u0639\u0645\u0644 \u062c\u0648\u0628 \u062a\u0648\u0644\u064a\u062f",
jobnote:"\u0627\u0644\u062c\u0648\u0628\u0632 \u0628\u062a\u062a\u062d\u0641\u0638 \u0641\u064a zi_data/jobs. \u0627\u0641\u062a\u062d \u0645\u0644\u0641 .json \u0641\u064a \u0646\u0648\u062a \u0628\u0648\u0643 Colab \u0639\u0634\u0627\u0646 \u064a\u062a\u0631\u0646\u062f\u0631\u060c \u0623\u0648 \u0627\u0646\u0633\u062e \u0627\u0644\u0628\u0631\u0648\u0645\u0628\u062a.",
import:"\u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0627\u0644\u062a\u0631\u0627\u0643\u0627\u062a \u0627\u0644\u062c\u0627\u0647\u0632\u0629",
folder:"\u0627\u0644\u0641\u0648\u0644\u062f\u0631 (\u0645\u062b\u0627\u0644: \u0641\u0648\u0644\u062f\u0631 \u062c\u0648\u062c\u0644 \u062f\u0631\u0627\u064a\u0641 Zi_Music \u0627\u0644\u0645\u062a\u0632\u0627\u0645\u0646)",
importbtn:"\u0627\u0633\u062a\u0648\u0631\u062f \u0644\u0644\u0645\u0643\u062a\u0628\u0629",jobs:"\u0627\u0644\u062c\u0648\u0628\u0632",
libnote:"\u0627\u0644\u062a\u0631\u0627\u0643\u0627\u062a \u0627\u0644\u0645\u062a\u0631\u0646\u062f\u0631\u0629. \u062f\u0648\u0633 \u0639\u0644\u0649 \u0627\u0644\u063a\u0644\u0627\u0641 \u0644\u0644\u062a\u0634\u063a\u064a\u0644 \u0645\u0639 \u0627\u0644\u0641\u064a\u062c\u0648\u0627\u0644\u0627\u064a\u0632\u0631\u060c \u0623\u0648 \u0635\u062f\u0651\u0631 \u062d\u0632\u0645\u0629 \u0631\u064a\u0644\u064a\u0632 \u0644\u0640 RouteNote.",
overview:"\u0646\u0638\u0631\u0629 \u0639\u0627\u0645\u0629 \u0639\u0644\u0649 \u0627\u0644\u0645\u0634\u0631\u0648\u0639",live:"\u0645\u0628\u0627\u0634\u0631",
ovnote:"\u0643\u0644 \u0635\u0641\u062d\u0629 \u0648\u0623\u0635\u0644 \u0641\u064a \u0627\u0644\u0645\u0634\u0631\u0648\u0639\u060c \u0628\u062a\u062a\u062d\u062f\u062b \u062a\u0644\u0642\u0627\u0626\u064a\u0627\u064b \u0645\u0646 zi_data/status.json.",
overall:"\u0627\u0644\u062a\u0642\u062f\u0645 \u0627\u0644\u0643\u0644\u064a",editstatus:"\u062a\u0639\u062f\u064a\u0644 \u0627\u0644\u062d\u0627\u0644\u0629",
editnote:"\u0627\u0644\u062d\u0627\u0644\u0629 \u0628\u062a\u062a\u0642\u0631\u064a \u0645\u0646 zi_data/status.json. \u0627\u0644\u0641\u0631\u064a\u0642 \u0628\u064a\u062d\u062f\u062b\u0647\u0627 \u0645\u0639 \u0627\u0644\u0634\u063a\u0644\u060c \u0648\u062a\u0642\u062f\u0631 \u062a\u0639\u062f\u0644\u0647\u0627 \u0645\u0646 \u0647\u0646\u0627 \u0648\u062a\u062d\u0641\u0638.",
save:"\u0627\u062d\u0641\u0638 \u0627\u0644\u062d\u0627\u0644\u0629",play:"\u062a\u0634\u063a\u064a\u0644",export:"\u062a\u0635\u062f\u064a\u0631 RouteNote",
notracks:"\u0644\u0633\u0647 \u0645\u0641\u064a\u0634 \u062a\u0631\u0627\u0643\u0627\u062a. \u0627\u0639\u0645\u0644 \u062c\u0648\u0628 \u0645\u0646 \u0627\u0644\u0633\u062a\u0648\u062f\u064a\u0648 \u0623\u0648 \u0627\u0633\u062a\u0648\u0631\u062f \u0641\u0648\u0644\u062f\u0631.",
nojobs:"\u0645\u0641\u064a\u0634 \u062c\u0648\u0628\u0632 \u0644\u0633\u0647.",th_title:"\u0627\u0644\u0627\u0633\u0645",th_style:"\u0627\u0644\u0633\u062a\u0627\u064a\u0644",th_length:"\u0627\u0644\u0645\u062f\u0629",th_status:"\u0627\u0644\u062d\u0627\u0644\u0629",
savedjob:"\u0627\u062a\u062d\u0641\u0638 \u0627\u0644\u062c\u0648\u0628: ",imported:"\u0627\u062a\u0633\u062a\u0648\u0631\u062f ",tracksuffix:" \u062a\u0631\u0627\u0643",exported:"\u0627\u062a\u0635\u062f\u0651\u0631: ",
open:"\u0627\u0641\u062a\u062d",updated:"\u0622\u062e\u0631 \u062a\u062d\u062f\u064a\u062b ",s_live:"\u0634\u063a\u0627\u0644",s_progress:"\u0642\u064a\u062f \u0627\u0644\u062a\u0646\u0641\u064a\u0630",s_done:"\u062e\u0644\u0635\u0627\u0646",s_pending:"\u0644\u0633\u0647",
loading:"\u0628\u064a\u062d\u0645\u0644...",min2:"\u062f",invalid:"JSON \u063a\u064a\u0631 \u0635\u0627\u0644\u062d: ",saved:"\u0627\u062a\u062d\u0641\u0638",tracksN:"\u062a\u0631\u0627\u0643"}
};
const t=k=>(T[LANG]&&T[LANG][k])||T.en[k]||k;
function applyI18n(){
  document.documentElement.lang=LANG;
  document.documentElement.dir=LANG=='ar'?'rtl':'ltr';
  document.querySelectorAll('[data-i18n]').forEach(e=>e.textContent=t(e.dataset.i18n));
  document.querySelectorAll('[data-i18n-ph]').forEach(e=>e.placeholder=t(e.dataset.i18nPh));
  $('langBtn').textContent=LANG=='ar'?'EN':'\u0639';
}
let THEME=localStorage.getItem('zi-theme')||'dark';
const SUN='<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON='<path d="M20 13.5A8 8 0 1 1 10.5 4a6.5 6.5 0 0 0 9.5 9.5z"/>';
function applyTheme(){document.documentElement.dataset.theme=THEME;$('themeIco').innerHTML=THEME=='dark'?SUN:MOON}
$('themeBtn').onclick=e=>{THEME=THEME=='dark'?'light':'dark';localStorage.setItem('zi-theme',THEME);applyTheme();burst(e.clientX,e.clientY,THEME=='dark'?['\u{1f319}','\u2728']:['\u2600\ufe0f','\u2728'],8)};
$('langBtn').onclick=e=>{LANG=LANG=='ar'?'en':'ar';localStorage.setItem('zi-lang',LANG);applyI18n();refreshAll();burst(e.clientX,e.clientY,['\u{1f310}','\u2728'],8)};

/* ---- ripple + emoji bursts ---- */
document.addEventListener('pointerdown',e=>{
  const b=e.target.closest('button');if(!b||RM)return;
  const r=b.getBoundingClientRect(),s=document.createElement('span');
  s.className='ripple';const d=Math.max(r.width,r.height);
  s.style.cssText=`width:${d}px;height:${d}px;left:${e.clientX-r.left-d/2}px;top:${e.clientY-r.top-d/2}px`;
  b.appendChild(s);setTimeout(()=>s.remove(),600);
});
function burst(x,y,set,n){
  if(RM)return;n=n||12;
  for(let i=0;i<n;i++){
    const s=document.createElement('span');s.className='pburst';
    s.textContent=set[Math.floor(Math.random()*set.length)];
    const a=Math.random()*Math.PI*2,d=50+Math.random()*90;
    s.style.left=x+'px';s.style.top=y+'px';
    s.style.setProperty('--dx',Math.cos(a)*d+'px');
    s.style.setProperty('--dy',(Math.sin(a)*d-40)+'px');
    s.style.setProperty('--rr',(Math.random()*140-70)+'deg');
    document.body.appendChild(s);setTimeout(()=>s.remove(),950);
  }
}
function burstAt(el,set,n){const r=el.getBoundingClientRect();burst(r.left+r.width/2,r.top+r.height/2,set,n)}

/* ---- 3D tilt + glare ---- */
const HOVER=!matchMedia('(hover: none)').matches;
function tilt(el){
  if(RM||!HOVER)return;el.classList.add('tilt');
  el.addEventListener('pointermove',e=>{
    const r=el.getBoundingClientRect(),x=(e.clientX-r.left)/r.width,y=(e.clientY-r.top)/r.height;
    el.style.setProperty('--gx',(x*100)+'%');el.style.setProperty('--gy',(y*100)+'%');
    el.style.transform=`perspective(750px) rotateX(${(0.5-y)*8}deg) rotateY(${(x-0.5)*10}deg) translateY(-2px)`;
  });
  el.addEventListener('pointerleave',()=>{el.style.transform=''});
}

/* ---- tabs / view transitions ---- */
function showTab(v){
  ['studio','library','dashboard'].forEach(k=>{
    $('view-'+k).classList.toggle('on',k==v);
    const b=$('nav'+k[0].toUpperCase());
    b.classList.toggle('on',k==v);
    if(k==v)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');
  });
  if(history.replaceState)history.replaceState(null,'',v=='studio'?'#':'#'+v);
  const lg=$('logo');lg.classList.remove('spinonce');void lg.offsetWidth;if(!RM)lg.classList.add('spinonce');
  if(v=='dashboard')loadDash();
  if(v=='library')renderLib();
}
document.querySelectorAll('nav.tabs button').forEach(b=>b.onclick=()=>showTab(b.dataset.view));
/* ---------- data rendering ---------- */
const fmtMin=s=>{const m=Math.round(s/60*10)/10;return m+' '+t('min')};
async function refreshJobs(){
  const jb=await j('/api/jobs');
  $('jobs').innerHTML='<thead><tr><th>'+t('th_title')+'<th>'+t('th_style')+'<th>'+t('th_length')+'<th>'+t('th_status')+'</thead><tbody>'
    +(jb.length?jb.map(x=>`<tr><td>${esc(x.title)}<td>${esc(x.preset)}<td>${fmtMin(x.seconds)}<td><span class="tag t-${esc((x.status||'').toLowerCase())}">${esc(x.status)}</span></tr>`).join(''):'<tr><td colspan="4" style="color:var(--mut)">'+t('nojobs')+'</td></tr>')+'</tbody>';
}
const gradFor=s=>{const h=hash(s),a=h%360,b=(a+40+h%80)%360;return `linear-gradient(135deg,hsl(${a} 72% 44%),hsl(${b} 82% 30%))`};
const initFor=s=>String(s||'?').trim().split(/\s+/).slice(0,2).map(w=>w[0]||'').join('').toUpperCase();
async function renderLib(){
  if(!window.L)$('tracksGrid').innerHTML='<div class="skel"></div>'.repeat(6);
  const l=await j('/api/library');window.L=l;
  $('libcount').textContent=l.length+' '+t('tracksN');
  if(!l.length){$('tracksGrid').innerHTML=`<div class="empty">${t('notracks')}</div>`;return}
  $('tracksGrid').innerHTML=l.map((x,i)=>{
    const cov=x.cover?`background-image:url('/cover/${encodeURIComponent(x.id)}');background-size:cover;background-position:center`:`background:${gradFor(x.title)}`;
    return `<div class="trk" data-i="${i}">
    <div class="cov" style="${cov}">${x.cover?'':esc(initFor(x.title))}
      <button class="playb" data-play="${i}" aria-label="${t('play')}: ${esc(x.title)}"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>
      <div class="eq" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div></div>
    <div class="inf"><div class="tt">${esc(x.title)}</div><div class="mt">${esc(x.genre||'')}${x.bpm?' \u00b7 '+x.bpm+' BPM':''}</div><div class="mt">${x.size_mb} MB \u00b7 ${esc(x.date)}</div></div>
    <div class="act"><button data-play="${i}">\u25b6 ${t('play')}</button><button data-ex="${i}">\u21aa ${t('export')}</button></div></div>`}).join('');
  document.querySelectorAll('#tracksGrid .trk').forEach(tilt);
  document.querySelectorAll('[data-play]').forEach(b=>b.onclick=e=>{playTrack(+b.dataset.play);burst(e.clientX,e.clientY,['\u{1f3b5}','\u{1f3b6}','\u2728'],8)});
  document.querySelectorAll('[data-ex]').forEach(b=>b.onclick=ex);
}
const GICON={"App & code":"\u{1f4bb}","Music":"\u{1f3b5}","Socials":"\u{1f4e3}","Team tools":"\u{1f6e0}\ufe0f","Distribution":"\u{1f680}","Plans":"\u{1f5fa}\ufe0f"};
const gicon=g=>GICON[g]||'\u{1f4cc}';
const sclass=s=>{const k=(s||'').toLowerCase();return k.includes('live')?'live':k.includes('progress')?'progress':k.includes('done')?'done':k.includes('block')?'block':'pending'};
const badge=s=>{const c=sclass(s);return `<span class="badge b-${c}">${esc(s||'')}</span>`};
const badgeK=(k,tx)=>{const c=k=='ready'?'live':k=='setup_needed'?'progress':k=='blocked_legal'?'block':k=='done'?'done':'pending';return `<span class="badge b-${c}">${esc(tx||'')}</span>`};
const pbar=s=>`<div class="pbar pb-${sclass(s)}"><i></i></div>`;
async function loadDash(quiet){
  if(!window.S||!quiet){$('tiles').innerHTML='<div class="skel"></div>'.repeat(6)}
  const s=await j('/api/status');window.S=s;
  const items=s.items||[];
  const cnt={live:0,progress:0,done:0,pending:0};
  items.forEach(x=>{const c=sclass(x.status);cnt[c=='block'?'pending':c]++});
  const pct=items.length?Math.round(items.reduce((a,x)=>({live:100,done:100,progress:50,block:20,pending:8})[sclass(x.status)]+a,0)/items.length):0;
  $('ovstats').innerHTML=['live','progress','done','pending'].map(k=>`<div class="stat s-${k}"><b>${cnt[k]}</b><span>${t('s_'+k)}</span></div>`).join('');
  $('ovpct').textContent=pct+'%';$('ovbar').style.width=pct+'%';
  $('supdated').textContent=s.updated?('\u00b7 '+t('updated')+s.updated):'';
  const tile=x=>`<a class="tile" ${x.url?`href="${esc(x.url)}" target="_blank" rel="noopener"`:''}>
    <div class="grp"><span class="gic">${gicon(x.group)}</span>${esc(x.group||'')}</div>
    <h3>${esc(x.name)}</h3>${badge(x.status)}${pbar(x.status)}
    <p>${esc(x.note||'')}</p>${x.url?`<span class="openbtn"><span class="ob-tx">${t('open')}</span><span class="ob-ic"><svg class='ob-a' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><path d='M7 17L17 7M9 7h8v8'/></svg><svg class='ob-b' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><path d='M7 17L17 7M9 7h8v8'/></svg></span></span>`:''}</a>`;
  $('tiles').innerHTML=items.map(tile).join('');
  $('sections').innerHTML=(s.sections||[]).map(sec=>`<div class="sechead"><span class="sic"><svg viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot;><circle cx=&quot;12&quot; cy=&quot;12&quot; r=&quot;8.5&quot;/><path d=&quot;M12 7.5v9M9.2 9.4c0-1.1 1.2-1.9 2.8-1.9s2.8.8 2.8 1.9c0 2.6-5.6 1.6-5.6 4.2 0 1.1 1.2 1.9 2.8 1.9s2.8-.8 2.8-1.9&quot;/></svg></span>${esc(sec.title||'')}</div>
    <p class="secintro">${esc(sec.intro||'')}</p><div class="tiles">${(sec.tiles||[]).map(x=>`<a class="tile" ${x.url?`href="${esc(x.url)}" target="_blank" rel="noopener"`:''}>
    <h3>${esc(x.name||'')}</h3>${x.name_en?`<div class="en">${esc(x.name_en)}</div>`:''}<div style="margin-top:6px">${badgeK(x.status_key,x.status)}</div>${pbar(x.status_key=='ready'?'live':x.status_key=='blocked_legal'?'blocked':x.status_key=='setup_needed'?'in progress':'')}
    <p>${esc(x.note||'')}</p><div>${(x.links||[]).map(lk=>`<span class="chip" data-link="${esc(lk.url)}">${esc(lk.label)} \u2197</span>`).join('')}</div>
    ${x.url?`<span class="openbtn"><span class="ob-tx">${t('open')}</span><span class="ob-ic"><svg class='ob-a' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><path d='M7 17L17 7M9 7h8v8'/></svg><svg class='ob-b' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><path d='M7 17L17 7M9 7h8v8'/></svg></span></span>`:''}</a>`).join('')}</div>`).join('');
  document.querySelectorAll('#tiles .tile,#sections .tile').forEach(tilt);
  document.querySelectorAll('.chip').forEach(c=>c.onclick=e=>{e.preventDefault();e.stopPropagation();window.open(c.dataset.link,'_blank','noopener')});
  $('sedit').value=JSON.stringify({project:s.project,updated:s.updated,items:s.items,sections:s.sections},null,2);
}
function withLoad(btn,fn){return async e=>{btn.classList.add('loading');try{await fn(e)}finally{btn.classList.remove('loading')}}}
const msg=(s,err)=>{const m=$('msg');m.textContent=s;m.className=err?'err':''};
$('mkBtn').onclick=withLoad($('mkBtn'),async e=>{
  try{const r=await post('/api/jobs',{preset:$('preset').value,title:$('title').value,minutes:$('minutes').value,instrumental:$('instr').checked,lyrics:$('lyrics').value,idea:$('idea').value});
  if(r.error){msg(r.error,1);return}msg(t('savedjob')+r.title);burstAt($('mkBtn'),['\u{1f389}','\u2728','\u{1f49c}','\u{1f3b5}'],14);refreshJobs()}catch(err){msg(String(err),1)}
});
$('imBtn').onclick=withLoad($('imBtn'),async e=>{
  const r=await post('/api/import',{folder:$('imp').value});
  if(r.error){msg(r.error,1);return}msg(t('imported')+r.imported+t('tracksuffix'));burstAt($('imBtn'),['\u{1f4e5}','\u{1f49c}','\u2728'],12);renderLib();
});
async function ex(e){
  const i=+e.currentTarget.dataset.ex;
  const r=await post('/api/export',{id:L[i].id,title:L[i].title,genre:L[i].genre});
  if(r.error){alert(r.error);return}
  burst(e.clientX,e.clientY,['\u{1f680}','\u{1f4e6}','\u2728'],12);
  alert(t('exported')+r.zip+(r.notes&&r.notes.length?'\n'+r.notes.join('\n'):''));
}
$('svBtn').onclick=withLoad($('svBtn'),async()=>{
  $('smsg').textContent='';
  try{const obj=JSON.parse($('sedit').value);const r=await post('/api/status',obj);
    if(r.error){$('smsg').textContent=r.error;$('smsg').style.color='var(--bad)';return}
    $('smsg').style.color='var(--good)';$('smsg').textContent=t('saved');burstAt($('svBtn'),['\u{1f48b}','\u{1f618}','\u2728'],12);loadDash(true);
  }catch(err){$('smsg').style.color='var(--bad)';$('smsg').textContent=t('invalid')+err}
});
async function refreshAll(){refreshJobs();renderLib();if($('view-dashboard').classList.contains('on'))loadDash(true)}
setInterval(()=>{if(document.hidden)return;if($('view-dashboard').classList.contains('on'))loadDash(true);if($('view-studio').classList.contains('on'))refreshJobs()},45000);
/* ---------- player + visualizer ---------- */
const au=$('au'),wave=$('wave'),wctx=wave.getContext('2d');
let cur=-1,peaks=null,actx=null,analyser=null,freq=null;
const ICO_PLAY='<path d="M8 5v14l11-7z"/>',ICO_PAUSE='<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>';
function ensureCtx(){if(actx)return;actx=new(window.AudioContext||window.webkitAudioContext)();
  analyser=actx.createAnalyser();analyser.fftSize=256;freq=new Uint8Array(analyser.frequencyBinCount);
  const src=actx.createMediaElementSource(au);src.connect(analyser);analyser.connect(actx.destination)}
const fmtT=s=>{if(!isFinite(s))return'0:00';s=Math.floor(s);return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
async function playTrack(i){
  if(!window.L||!L.length)return;cur=i;const x=L[i];
  document.body.classList.add('playing');$('player').classList.add('on');
  $('pt').textContent=x.title;$('ps').textContent=(x.genre||'')+(x.bpm?' \u00b7 '+x.bpm+' BPM':'');
  const cov=$('pcov');
  if(x.cover){cov.style.background=`url('/cover/${encodeURIComponent(x.id)}') center/cover`;cov.textContent=''}
  else{cov.style.background=gradFor(x.title);cov.textContent=initFor(x.title)}
  document.querySelectorAll('.trk.playing').forEach(e=>e.classList.remove('playing'));
  const card=document.querySelector(`.trk[data-i="${i}"]`);if(card)card.classList.add('playing');
  peaks=null;
  au.src='/audio/'+encodeURIComponent(x.id);
  try{ensureCtx();await actx.resume();await au.play()}catch(e){}
  try{const buf=await(await fetch(au.src)).arrayBuffer();const ab=await actx.decodeAudioData(buf);
    const ch=ab.getChannelData(0),N=240,st=Math.floor(ch.length/N),pk=new Float32Array(N);
    for(let k=0;k<N;k++){let m=0;for(let s2=k*st;s2<(k+1)*st;s2+=Math.max(1,st>>6))m=Math.max(m,Math.abs(ch[s2]));pk[k]=m}
    peaks=pk}catch(e){peaks=null}
}
au.addEventListener('play',()=>$('pplayIco').innerHTML=ICO_PAUSE);
au.addEventListener('pause',()=>$('pplayIco').innerHTML=ICO_PLAY);
au.addEventListener('ended',()=>playTrack((cur+1)%L.length));
$('pplay').onclick=()=>{if(cur<0&&window.L&&L.length)return playTrack(0);au.paused?au.play():au.pause()};
$('pnext').onclick=()=>playTrack((cur+1)%L.length);
$('pprev').onclick=()=>playTrack((cur-1+L.length)%L.length);
$('pclose').onclick=()=>{au.pause();$('player').classList.remove('on');document.body.classList.remove('playing');cur=-1;
  document.querySelectorAll('.trk.playing').forEach(e=>e.classList.remove('playing'))};
function seekAt(clientX){const r=wave.getBoundingClientRect();const f=Math.min(1,Math.max(0,(clientX-r.left)/r.width));
  if(isFinite(au.duration))au.currentTime=f*au.duration}
wave.addEventListener('pointerdown',e=>seekAt(e.clientX));
wave.addEventListener('keydown',e=>{if(e.key=='ArrowRight')au.currentTime+=5;if(e.key=='ArrowLeft')au.currentTime-=5});
function sizeCanvas(c){const d=Math.min(2,devicePixelRatio||1),w=c.clientWidth,h=c.clientHeight;
  if(c.width!=w*d||c.height!=h*d){c.width=w*d;c.height=h*d;c.getContext('2d').setTransform(d,0,0,d,0,0)}}
function drawWave(ts){
  if(!$('player').classList.contains('on'))return;
  sizeCanvas(wave);const w=wave.clientWidth,h=wave.clientHeight;wctx.clearRect(0,0,w,h);
  const dur=au.duration,prog=isFinite(dur)&&dur?au.currentTime/dur:0;
  const mid=h/2,N=120,bw=w/N;
  const pk=k=>peaks?peaks[Math.floor(k/N*peaks.length)]:(.35+.3*Math.sin(k*.35+hash($('pt').textContent)));
  for(let k=0;k<N;k++){
    const v=Math.min(1,pk(k)),bh=Math.max(2,v*h*.86),x=k*bw;
    wctx.fillStyle=k/N<prog?'rgba(124,92,255,.9)':'rgba(124,140,200,.28)';
    wctx.fillRect(x+1,mid-bh/2,Math.max(1,bw-2),bh);
  }
  if(analyser&&!au.paused&&!RM){
    analyser.getByteFrequencyData(freq);
    wctx.beginPath();let bass=0;
    for(let b=0;b<8;b++)bass+=freq[b];bass=bass/8/255;
    $('player').style.setProperty('--pg',bass.toFixed(2));
    const pts=64;
    for(let i2=0;i2<=pts;i2++){
      const v=freq[Math.floor(i2/pts*freq.length*.72)]/255;
      const x=i2/pts*w,y=mid-(v-.28)*h*.95;
      i2?wctx.lineTo(x,y):wctx.moveTo(x,y);
    }
    wctx.strokeStyle='rgba(0,212,255,.95)';wctx.lineWidth=2.2;
    wctx.shadowColor='rgba(0,212,255,.8)';wctx.shadowBlur=10;wctx.stroke();wctx.shadowBlur=0;
    const eq=document.querySelector('.trk.playing .eq');
    if(eq){const bars=eq.children;for(let b=0;b<bars.length;b++){const v=freq[2+b*6]/255;bars[b].style.height=(12+v*88)+'%'}}
  }else if(!RM&&!au.paused){
    wctx.beginPath();
    for(let i2=0;i2<=60;i2++){const x=i2/60*w,y=mid+Math.sin(i2*.4+ts/300)*4;i2?wctx.lineTo(x,y):wctx.moveTo(x,y)}
    wctx.strokeStyle='rgba(0,212,255,.5)';wctx.lineWidth=1.6;wctx.stroke();
  }else{$('player').style.setProperty('--pg','0')}
  $('tcur').textContent=fmtT(au.currentTime);$('ttot').textContent=fmtT(au.duration);
  wave.setAttribute('aria-valuenow',Math.round(prog*100));
}
/* ---------- starfield ---------- */
const sc=$('stars'),sctx=sc.getContext('2d');let stars=[],shoot=null,nextShoot=0;
function starInit(){sizeCanvas(sc);const w=sc.clientWidth,h=sc.clientHeight,n=Math.min(170,Math.floor(w*h/9000));
  stars=Array.from({length:n},()=>({x:Math.random()*w,y:Math.random()*h,r:.4+Math.random()*1.5,p:Math.random()*6.28,s:.06+Math.random()*.22,hue:Math.random()<.14}))}
function drawStars(ts){
  if(RM)return;sizeCanvas(sc);const w=sc.clientWidth,h=sc.clientHeight;sctx.clearRect(0,0,w,h);
  for(const st of stars){
    st.y+=st.s;st.x-=st.s*.35;if(st.y>h+2){st.y=-2;st.x=Math.random()*w}if(st.x<-2)st.x=w+2;
    const a=.35+.55*Math.abs(Math.sin(ts/900+st.p));
    sctx.fillStyle=st.hue?`rgba(0,212,255,${a})`:`rgba(220,225,255,${a})`;
    sctx.beginPath();sctx.arc(st.x,st.y,st.r,0,6.28);sctx.fill();
  }
  if(!shoot&&ts>nextShoot){shoot={x:Math.random()*w*.7+w*.2,y:Math.random()*h*.3,life:1};
    nextShoot=ts+3500+Math.random()*5000}
  if(shoot){shoot.x-=9;shoot.y+=5;shoot.life-=.022;
    if(shoot.life<=0)shoot=null;else{const g=sctx.createLinearGradient(shoot.x,shoot.y,shoot.x+70,shoot.y-40);
    g.addColorStop(0,`rgba(180,200,255,${shoot.life*.9})`);g.addColorStop(1,'rgba(180,200,255,0)');
    sctx.strokeStyle=g;sctx.lineWidth=1.8;sctx.beginPath();sctx.moveTo(shoot.x,shoot.y);sctx.lineTo(shoot.x+70,shoot.y-40);sctx.stroke()}}
}
function loop(ts){if(!document.hidden){drawStars(ts);drawWave(ts)}requestAnimationFrame(loop)}
addEventListener('resize',starInit);
/* ---------- init ---------- */
applyTheme();applyI18n();
$('minutes').oninput=()=>$('lenv').textContent=$('minutes').value;
$('instr').onchange=()=>$('lyr').style.display=$('instr').checked?'none':'block';
(async()=>{const p=await j('/api/presets');$('preset').innerHTML=p.map(x=>`<option>${esc(x)}</option>`).join('');
  refreshJobs();renderLib();starInit();requestAnimationFrame(loop);
  const v=location.hash.replace('#','');
  if(v=='library'||v=='dashboard')showTab(v)})();
</script>
</body>
</html>
"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/": return self.send(200, HTML, "text/html; charset=utf-8")
        if p == "/api/presets": return self.send(200, list(PRESETS))
        if p == "/api/jobs": return self.send(200, list_jobs())
        if p == "/api/library": return self.send(200, scan_library())
        if p == "/api/status": return self.send(200, load_status())
        if p.startswith("/audio/"):
            f = os.path.normpath(os.path.join(LIB, unquote(p[7:])))
            if f.startswith(os.path.normpath(LIB)) and os.path.isfile(f):
                ct = "audio/mpeg" if f.endswith(".mp3") else "audio/wav" if f.endswith(".wav") else "application/octet-stream"
                return self.send(200, open(f, "rb").read(), ct)
        if p.startswith("/cover/"):
            f = os.path.normpath(os.path.join(LIB, unquote(p[7:])))
            if f.startswith(os.path.normpath(LIB)):
                c = find_cover(f)
                if c:
                    return self.send(200, open(c, "rb").read(), "image/png" if c.endswith(".png") else "image/jpeg")
            return self.send(404, {"error": "no cover"})
        self.send(404, {"error": "not found"})
    def do_POST(self):
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}"); p = urlparse(self.path).path
            if p == "/api/jobs": return self.send(200, make_job(d))
            if p == "/api/import": return self.send(200, {"imported": import_folder(d.get("folder", ""))})
            if p == "/api/export": return self.send(200, export_release(d["id"], d.get("title", ""), d.get("genre", "")))
            if p == "/api/status": return self.send(200, save_status(d))
            self.send(404, {"error": "not found"})
        except Exception as e: self.send(400, {"error": str(e)})

def main(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"Zi Music Studio on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv: threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
if __name__ == "__main__": main()
 
