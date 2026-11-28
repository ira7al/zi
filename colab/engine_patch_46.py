# Engine patch for bot build .46: cover/remix + remaster. Paste into ONE new notebook cell and run it
# AFTER the engine cell (same kernel). It is safe to run twice. It does not touch the original tracks.
import inspect, shutil

_COVER_NOW = {}

def _cover_wrap_needed():
    try:
        return "audio_cover_strength" not in inspect.getsource(gen_candidates)
    except Exception:
        return True

if _cover_wrap_needed() and not globals().get("_GEN_WRAPPED_46"):
    _GEN_WRAPPED_46 = True
    _orig_gen_candidates = gen_candidates
    _orig_post = post

    def post(path, payload, *a, **k):          # adds the cover fields to the generation request only
        sp = _COVER_NOW.get("spec")
        if path == "/release_task" and sp and sp.get("task_type") == "cover" and sp.get("src_audio_path"):
            payload = dict(payload)
            payload["task_type"] = "cover"
            payload["src_audio_path"] = sp["src_audio_path"]
            payload["audio_cover_strength"] = float(sp.get("cover_strength") or 0.65)
        return _orig_post(path, payload, *a, **k)

    def gen_candidates(spec, quality="standard"):
        _COVER_NOW["spec"] = spec
        try:
            return _orig_gen_candidates(spec, quality)
        finally:
            _COVER_NOW.clear()

# --- .46: remix/cover and remaster of a saved track. Results are NEW releases, the original is untouched. ---
COVER_TASKS = True   # the bot shows the remix button only when this name exists

def master_file(path, out_wav=None):
    """Master any audio file with the release chain. Returns (wav path, report). report["verified"]
    is True only when the output measures at or below -0.9 dBTP and within 1 LU of -14 LUFS."""
    out_wav = out_wav or (os.path.splitext(path)[0] + "_remaster.wav")
    rep = master_audio(path, out_wav)
    try:
        ok = float(rep["out_tp"]) <= -0.9 and abs(float(rep["out_i"]) + 14.0) <= 1.0
    except Exception:
        ok = False
    rep["verified"] = bool(ok)
    return out_wav, rep

def remaster_release(src_folder, ts=None):
    """Re-master the saved FLAC of a release into a NEW release folder (title + ' (Remaster)')."""
    import shutil
    ts = ts or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    meta = json.load(open(src_folder + "/metadata.json")) if os.path.exists(src_folder + "/metadata.json") else {}
    flacs = sorted(f for f in os.listdir(src_folder) if f.lower().endswith(".flac"))
    if not flacs:
        raise RuntimeError("no FLAC in " + os.path.basename(src_folder))
    old_title = meta.get("title") or os.path.splitext(flacs[0])[0].replace("_", " ")
    title = old_title + " (Remaster)"
    folder = f"{OUT_ROOT}/{ts}_{slug(title)}"
    os.makedirs(folder, exist_ok=True)
    base = f"{folder}/{slug(title)}"
    wav, rep = master_file(f"{src_folder}/{flacs[0]}", base + ".wav")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",wav,"-sample_fmt","s16",base+".flac"],check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",wav,"-b:a","320k",base+"_320kbps.mp3"],check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",wav,"-b:a","128k",base+"_preview_128k.mp3"],check=True)
    for name in ("cover_3000x3000.jpg", "lyrics.txt"):
        if os.path.exists(f"{src_folder}/{name}"):
            shutil.copy2(f"{src_folder}/{name}", f"{folder}/{name}")
    if os.path.exists(src_folder + "/routenote_form.txt"):
        open(folder + "/routenote_form.txt", "w").write(open(src_folder + "/routenote_form.txt").read().replace(old_title, title))
    meta.update({"title": title, "created": ts, "remaster_of": os.path.basename(src_folder),
                 "mastering": rep, "actual_duration_sec": round(ffprobe_sec(wav), 1)})
    json.dump(meta, open(folder + "/metadata.json", "w"), indent=2, ensure_ascii=False)
    with open(OUT_ROOT + "/releases.csv", "a", newline="") as fh:
        csv.writer(fh).writerow([ts, title, meta.get("artist"), meta.get("genre"), meta.get("bpm"), meta.get("key"), folder])
    meta["storage"] = storage_routine(wav)
    json.dump(meta, open(folder + "/metadata.json", "w"), indent=2, ensure_ascii=False)
    return {"folder": folder, "base": base, "lyrics": "", "metas": {}, "title": title, "qc": {}, "mastering": rep}

