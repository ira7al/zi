"""Zi Music Studio desktop app. Python 3.9+, standard library only (Pillow optional for covers, ffmpeg optional for MP3/WAV).
Run: python zi_app.py   -> opens http://127.0.0.1:8765
Data lives in ./zi_data (jobs, library, exports)."""
import csv, datetime, json, os, random, re, shutil, subprocess, sys, threading, webbrowser, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

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

def scan_library():
    items = []
    for dp, _, fs in os.walk(LIB):
        for f in fs:
            if f.lower().endswith(AUDIO_EXT):
                p = os.path.join(dp, f); base = os.path.splitext(p)[0]
                meta = read_json(base + ".json", {}) or {}
                items.append({"id": os.path.relpath(p, LIB).replace(os.sep, "/"), "title": meta.get("title") or os.path.splitext(f)[0],
                              "genre": meta.get("genre", ""), "bpm": meta.get("bpm", ""), "size_mb": round(os.path.getsize(p)/1e6, 1),
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
    src = os.path.normpath(os.path.join(LIB, track_id))
    if not src.startswith(os.path.normpath(LIB)) or not os.path.isfile(src): raise ValueError("Track not found")
    meta = read_json(os.path.splitext(src)[0] + ".json", {}) or {}
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

HTML = r"""<!doctype html><meta charset=utf-8><title>Zi Music Studio</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>:root{--bg:#0e0f14;--card:#181a22;--ac:#7c5cff;--tx:#e8e8f0;--mut:#8b8fa3}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px system-ui,sans-serif}
header{padding:18px 28px;border-bottom:1px solid #23263a;font-size:20px;font-weight:700}header span{color:var(--ac)}
main{display:grid;grid-template-columns:420px 1fr;gap:20px;padding:20px 28px;max-width:1300px;margin:auto}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border-radius:14px;padding:18px;margin-bottom:20px}h2{margin:0 0 12px;font-size:16px}
label{display:block;color:var(--mut);font-size:12px;margin:10px 0 4px}
input,select,textarea{width:100%;background:#0e0f14;color:var(--tx);border:1px solid #2a2e45;border-radius:8px;padding:9px;font:inherit}
textarea{min-height:90px}button{background:var(--ac);color:#fff;border:0;border-radius:8px;padding:10px 16px;font:inherit;cursor:pointer;margin-top:12px}
button.sec{background:#2a2e45}.row{display:flex;gap:10px;align-items:center}.row>*{flex:1}
table{width:100%;border-collapse:collapse}td,th{padding:8px 6px;border-bottom:1px solid #23263a;text-align:left;font-size:13px}th{color:var(--mut);font-weight:500}
.tag{font-size:11px;padding:2px 8px;border-radius:10px;background:#2a2e45}#msg{color:#7cf0b0;margin:8px 0;min-height:18px}audio{width:100%;margin-top:8px}
nav{float:right}nav a{color:var(--mut);cursor:pointer;margin-left:16px;font-size:15px;font-weight:400}nav a.on{color:var(--tx);font-weight:700;border-bottom:2px solid var(--ac)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.tile{background:#12131b;border-radius:12px;padding:14px 16px;border:1px solid #23263a;cursor:pointer}
.tile:hover{border-color:var(--ac)}.tile h3{margin:0 0 8px;font-size:14px}.tile p{margin:8px 0 0;font-size:12px;color:var(--mut)}
.badge{font-size:11px;padding:2px 8px;border-radius:10px}
.b-live{background:#14452f;color:#7cf0b0}.b-progress{background:#4a3a12;color:#ffd97c}.b-done{background:#1c3a4a;color:#7cc7ff}.b-pending{background:#2a2e45;color:#8b8fa3}
.tile .grp{font-size:11px;color:#5a5e73;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px}.tile .open{color:var(--ac);font-size:12px;margin-top:8px}</style>
<header>Zi <span>Music Studio</span> &nbsp;<small style="color:var(--mut);font-weight:400">artist Rahal · AI-assisted · free</small><nav><a id=navS class=on onclick="showTab('studio')">Studio</a><a id=navD onclick="showTab('dash')">Dashboard</a></nav></header>
<main id=dash style="display:none;grid-template-columns:1fr"><div>
<div class=card><h2>Project dashboard &nbsp;<small id=supdated style="color:var(--mut);font-weight:400"></small></h2>
<small style="color:var(--mut)">Every page and asset of the project. Click a tile to open it and see how far it got.</small>
<div style="height:12px"></div><div class=tiles id=tiles></div></div>
<div class=card><h2>Edit status</h2>
<small style="color:var(--mut)">Live status is read from zi_data/status.json. The team updates it as work moves; you can also edit it here and save.</small>
<textarea id=sedit style="min-height:280px;font-family:monospace;font-size:12px;margin-top:10px"></textarea>
<button onclick=saveStatus()>Save status</button> <span id=smsg style="color:#7cf0b0"></span></div>
</div></main>
<main id=studio><div>
<div class=card><h2>1. New track</h2>
<label>Style preset</label><select id=preset></select>
<label>Title (optional)</label><input id=title>
<label>Length: <b id=lenv>5.5</b> min</label><input id=minutes type=range min=1 max=10 step=0.5 value=5.5 oninput="lenv.textContent=this.value">
<label><input type=checkbox id=instr checked style="width:auto" onchange="lyr.style.display=this.checked?'none':'block'"> Instrumental</label>
<div id=lyr style="display:none"><label>Lyrics</label><textarea id=lyrics placeholder="[Verse] ..."></textarea></div>
<label>Extra idea / mood (optional)</label><input id=idea placeholder="e.g. sunrise over the Red Sea">
<button onclick=mk()>Create generation job</button><div id=msg></div>
<small style="color:var(--mut)">Jobs are saved to zi_data/jobs. Load the .json in the Colab notebook to render, or copy the style prompt.</small></div>
<div class=card><h2>Import finished tracks</h2><label>Folder (e.g. your Google Drive sync folder Zi_Music)</label><input id=imp placeholder="C:\Users\you\Google Drive\Zi_Music">
<button class=sec onclick=im()>Import into library</button></div></div>
<div><div class=card><h2>Jobs</h2><table id=jobs></table></div>
<div class=card><h2>Library</h2><table id=lib></table><audio id=pl controls style="display:none"></audio></div></div></main>
<script>
const $=id=>document.getElementById(id),j=(u,o)=>fetch(u,o).then(r=>r.json());
const post=(u,b)=>j(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function load(){const p=await j('/api/presets');$('preset').innerHTML=p.map(x=>`<option>${esc(x)}</option>`).join('');refresh()}
async function refresh(){const jb=await j('/api/jobs');$('jobs').innerHTML='<tr><th>Title<th>Style<th>Length<th>Status</tr>'+jb.map(x=>`<tr><td>${esc(x.title)}<td>${esc(x.preset)}<td>${Math.round(x.seconds/60*10)/10} min<td><span class=tag>${esc(x.status)}</span></tr>`).join('');
const l=await j('/api/library');$('lib').innerHTML='<tr><th>Title<th>Genre<th>MB<th>Date<th></tr>'+l.map((x,i)=>`<tr><td>${esc(x.title)}<td>${esc(x.genre)}<td>${x.size_mb}<td>${x.date}<td><a href=# onclick="play(${i});return false">play</a> · <a href=# onclick="ex(${i});return false">RouteNote export</a></tr>`).join('');window.L=l}
async function mk(){try{const r=await post('/api/jobs',{preset:$('preset').value,title:$('title').value,minutes:$('minutes').value,instrumental:$('instr').checked,lyrics:$('lyrics').value,idea:$('idea').value});$('msg').textContent=r.error||('Saved job: '+r.title);refresh()}catch(e){$('msg').textContent=e}}
async function im(){const r=await post('/api/import',{folder:$('imp').value});$('msg').textContent=r.error||('Imported '+r.imported+' track(s)');refresh()}
function play(i){const a=$('pl');a.style.display='block';a.src='/audio/'+encodeURIComponent(L[i].id);a.play()}
async function ex(i){const r=await post('/api/export',{id:L[i].id,title:L[i].title,genre:L[i].genre});$('msg').textContent=r.error||('Exported: '+r.zip+(r.notes.length?' ('+r.notes.join(' ')+')':''))}
function showTab(t){if(history.replaceState)history.replaceState(null,'',t=='dash'?'#dashboard':'#');$('studio').style.display=t=='studio'?'grid':'none';$('dash').style.display=t=='dash'?'grid':'none';$('navS').className=t=='studio'?'on':'';$('navD').className=t=='dash'?'on':'';if(t=='dash')loadDash()}
const badge=s=>{const k=(s||'').toLowerCase();const c=k.indexOf('live')>=0?'b-live':k.indexOf('progress')>=0?'b-progress':k.indexOf('done')>=0?'b-done':'b-pending';return `<span class="badge ${c}">${esc(s||'')}</span>`}
async function loadDash(){const s=await j('/api/status');window.S=s;$('tiles').innerHTML=(s.items||[]).map(x=>`<div class=tile data-u="${esc(x.url||'')}" onclick="if(this.dataset.u)window.open(this.dataset.u,'_blank')"><div class=grp>${esc(x.group||'')}</div><h3>${esc(x.name)}</h3>${badge(x.status)}<p>${esc(x.note||'')}</p>${x.url?'<div class=open>open &nearr;</div>':''}</div>`).join('');$('supdated').textContent=s.updated?('last updated '+s.updated):'';$('sedit').value=JSON.stringify({project:s.project,updated:s.updated,items:s.items},null,2)}
async function saveStatus(){$('smsg').textContent='';try{const obj=JSON.parse($('sedit').value);const r=await post('/api/status',obj);$('smsg').textContent=r.error||'Saved';loadDash()}catch(e){$('smsg').textContent='Invalid JSON: '+e}}
load();if(location.hash=='#dashboard')showTab('dash')</script>"""

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
from urllib.parse import unquote

def main(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"Zi Music Studio on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv: threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
if __name__ == "__main__": main()
