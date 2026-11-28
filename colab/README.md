# Zi Music Studio (free Colab notebook)

Generate full-length music tracks (up to 10 minutes, native) for free on Google Colab (T4 GPU) and save RouteNote-ready releases to your Google Drive. No paid API, no local GPU needed.

## Run steps
1. Open `Zi_Music_Studio.ipynb` in Google Colab (File > Upload notebook, or "Open in Colab" from GitHub).
2. Runtime > Change runtime type > **T4 GPU**.
3. Run **cell 1** (setup, 10-20 min first time). Allow the Google Drive mount when asked.
4. Run **cell 2** (engine).
5. Run **cell 3** (one track: style, theme, length 60-600 s, quality preset) or **cell 4** (batch queue: a week of tracks back to back, resumes after a disconnect).
6. Tracks are saved to `MyDrive/Zi_Music/`, each in a folder with WAV + FLAC + MP3 320k + MP3 128k preview, 3000x3000 cover, lyrics, `metadata.json` and `routenote_form.txt`.

## Quality presets
- **Fast:** 8 steps, no LM planning. Drafts.
- **Standard:** 8 steps + LM thinking.
- **High:** `acestep-v15-turbo-shift3` model when available, 14 steps, 2 seed candidates, automatic QC pick (clipping, silence, duration, spectrum).

## Mastering
Every track passes a free ffmpeg chain: high-pass, gentle EQ, glue compressor, stereo width, two-pass loudness normalize to -14 LUFS / -1 dBTP, safety limiter. The before/after loudness numbers are stored in `metadata.json`.

## Long tracks
The model renders up to 600 s natively, so 5-6 min tracks are one render. If a render returns short audio, the engine extends it with a continuation segment joined by a beat-aligned crossfade.

## AI music rules
- Label every release as AI-generated. Do not hide it.
- Do not imitate a real artist's voice or name artists in prompts.
- Check the model's licence allows commercial use before you release anything (ACE-Step 1.5 is MIT).
- Keep the prompt and settings used for each track (the notebook stores them in `metadata.json`).
- Earnings are not guaranteed.

## RouteNote prep
RouteNote has no upload API we use here, so upload by hand.
1. Audio: the folder's FLAC or WAV (44.1 kHz stereo 16-bit) or MP3 320k.
2. Cover art: `cover_3000x3000.jpg`.
3. Metadata: copy from `routenote_form.txt`.
4. Confirm you own or have licensed all parts of the track (lyrics included).
5. Check RouteNote's current AI-content policy before submitting.

## Bot (chat control from Telegram)
Cell 5 starts the bot. It downloads `bot/zi_bot.py`, stops any poller left by an earlier run, and calls `start_engine_bot(token, make_track, run_queue, out_root, work)` with the notebook's own engine functions. The token comes from a secret named `ZI_BOT_TOKEN` (Colab: key icon > Secrets, enable notebook access; Kaggle: Add-ons > Secrets). The first run prints a pairing code; send `/start <code>` to the bot to bind the owner. Only the bound owner can use it.

### Reload the bot on a pinned build
Re-running cell 5 always picks up `main`. To load a specific commit instead (a build that has not reached `main` yet, or going back to a known-good one), paste this as its own cell. Replace `SHA` with the commit, and run it only after the engine cells, because it reuses `make_track`, `run_queue`, `OUT_ROOT` and `WORK`.

```python
# pinned bot reload - the correct start call is start_engine_bot(...), not start()
import os, sys, importlib.util, urllib.request
SHA = "PUT_COMMIT_SHA_HERE"
API_SRC = f"https://api.github.com/repos/ira7al/zi/contents/bot/zi_bot.py?ref={SHA}"
RAW_SRC = f"https://raw.githubusercontent.com/ira7al/zi/{SHA}/bot/zi_bot.py"
try:
    ZI_BOT.stop.set()
    print("Stopped the previous bot instance.")
except Exception:
    pass
try:
    _req = urllib.request.Request(API_SRC, headers={"Accept": "application/vnd.github.raw", "User-Agent": "zi-notebook"})
    with urllib.request.urlopen(_req, timeout=60) as _r:
        _code = _r.read()
except Exception as _e:
    print("API download failed (", _e, "), falling back to raw.githubusercontent.com")
    with urllib.request.urlopen(RAW_SRC, timeout=60) as _r:
        _code = _r.read()
_bot_path = os.path.join(LOCAL_TMP, "zi_bot.py")
open(_bot_path, "wb").write(_code)
_spec = importlib.util.spec_from_file_location("zi_bot", _bot_path)
zi_bot = importlib.util.module_from_spec(_spec)
sys.modules["zi_bot"] = zi_bot
_spec.loader.exec_module(zi_bot)

_token = os.environ.get("ZI_BOT_TOKEN", "").strip()
if not _token:
    try:
        from google.colab import userdata
        _token = (userdata.get("ZI_BOT_TOKEN") or "").strip()
    except Exception:
        pass
if not _token:
    try:
        from kaggle_secrets import UserSecretsClient
        _token = (UserSecretsClient().get_secret("ZI_BOT_TOKEN") or "").strip()
    except Exception:
        pass
if not _token:
    raise SystemExit("Add the bot token as a secret named ZI_BOT_TOKEN first, then run this cell again.")
ZI_BOT = zi_bot.start_engine_bot(token=_token, make_track=make_track, run_queue=run_queue, out_root=OUT_ROOT, work=WORK)
print("build", zi_bot.VERSION)
```

`start_engine_bot` stops every poller in the process before it starts the new one. Two pollers fight over `getUpdates` (Telegram answers one consumer, the other gets 409s) and taps land on the dead one, so never start a second bot by hand.

## Publishing from the bot
After a track is delivered the bot shows the cover, the audio, a 9:16 video of the track, and a publish menu. Each button posts only the platform you tap, once, and each post carries the line "AI-generated with ACE-Step under Rahal's direction and selection."

| Button | What happens |
| --- | --- |
| Telegram channel | Posts to t.me/rahal_music with the bot token: the video if there is one, otherwise audio + cover. |
| YouTube | Uploads through the YouTube Data API (needs `youtube_token.json`, see below). Until it exists, the tap writes the post package and says why. |
| Instagram / TikTok | No API on our side yet: writes `publish_request_ig.json` / `publish_request_tt.json` into the release folder (caption, tags, files, approval time) for a one-pass manual post. |
| Facebook | Returns the caption and the file for manual posting. |
| All | Channel post plus the packages above. |

`/publish` reopens the menu for the last release, `/publish <title>` for a named one.

### youtube_token.json
The YouTube button reads a JSON file with three fields, from `OUT_ROOT` (normally `/kaggle/working/Zi_Music`) or `<OUT_ROOT>/../zi_data/`:

```json
{
  "client_id": "....apps.googleusercontent.com",
  "client_secret": "....",
  "refresh_token": "...."
}
```

It comes from a Google Cloud project with the YouTube Data API enabled, an OAuth client of type Desktop/Installed app, and one consent by the channel owner with the `https://www.googleapis.com/auth/youtube.upload` scope. The bot exchanges the refresh token for an access token at each upload, so the file does not expire. Uploads are public, category Music, `containsSyntheticMedia` set (YouTube's altered-content disclosure), and the description carries the AI wording plus tags.

The 9:16 video is used for the channel, reels and shorts; the YouTube button renders a 1280x720 version from the same cover on demand so the full track reads properly on YouTube.

## Bot build 2026-11-28.14: reload and engine patch

The bot now loads a second file (`bot/zi_options.py`), so a cell 5 that only fetches `zi_bot.py` fails. Use this cell instead; it pins the commit and fetches both.

```python
# pinned reload - build .14 (bot + its shared option model)
import os, sys, importlib.util, urllib.request
SHA = "aea7a75e14a0324f2ea7d9a0a4d146fc3995154c"
try:
    ZI_BOT.stop.set()
    print("Stopped the previous bot instance.")
except Exception:
    pass
for _rel in ("bot/zi_bot.py", "bot/zi_options.py"):
    _api = f"https://api.github.com/repos/ira7al/zi/contents/{_rel}?ref={SHA}"
    _raw = f"https://raw.githubusercontent.com/ira7al/zi/{SHA}/{_rel}"
    try:
        _req = urllib.request.Request(_api, headers={"Accept": "application/vnd.github.raw", "User-Agent": "zi-notebook"})
        with urllib.request.urlopen(_req, timeout=60) as _r:
            _code = _r.read()
    except Exception as _e:
        print("API download failed (", _e, "), falling back to raw")
        with urllib.request.urlopen(_raw, timeout=60) as _r:
            _code = _r.read()
    open(os.path.join(LOCAL_TMP, os.path.basename(_rel)), "wb").write(_code)
    print(os.path.basename(_rel), len(_code), "bytes")
_spec = importlib.util.spec_from_file_location("zi_bot", os.path.join(LOCAL_TMP, "zi_bot.py"))
zi_bot = importlib.util.module_from_spec(_spec)
sys.modules["zi_bot"] = zi_bot
_spec.loader.exec_module(zi_bot)
_token = os.environ.get("ZI_BOT_TOKEN", "").strip()
if not _token:
    try:
        from google.colab import userdata
        _token = (userdata.get("ZI_BOT_TOKEN") or "").strip()
    except Exception:
        pass
if not _token:
    try:
        from kaggle_secrets import UserSecretsClient
        _token = (UserSecretsClient().get_secret("ZI_BOT_TOKEN") or "").strip()
    except Exception:
        pass
if not _token:
    raise SystemExit("Add the bot token as a secret named ZI_BOT_TOKEN first.")
ZI_BOT = zi_bot.start_engine_bot(token=_token, make_track=make_track, run_queue=run_queue, out_root=OUT_ROOT, work=WORK)
print("build", zi_bot.VERSION)
```

### Engine cell: options, XL switch and LoRA hooks

The bot sends `steps`, `model`, `guidance_scale`, `seed` and `lyrics` in the spec. The engine cell in this repo already honours them; an older kernel ignores them and still renders. What changed inside `gen_candidates`:

```python
    _m = spec.get("model")
    if _m:
        _model = MODEL_MAP.get(_m, _m)
        if _model not in (MODELS or []) and _m == "xl":
            print(f"  ! {_model} is not on the box yet, falling back to turbo")
            _model = "acestep-v15-turbo"
    else:
        _model = pick_model(quality)
    payload = {"audio_format":"flac", "batch_size": q["candidates"], "thinking": q["thinking"],
               "inference_steps": int(spec.get("steps") or q["steps"]), "model": _model,
               "audio_duration": spec["seconds"],
               "use_random_seed": spec.get("seed") in (None, "", -1),
               "vocal_language": spec.get("lang","en")}
    if spec.get("bpm"): payload["bpm"] = spec["bpm"]
    if spec.get("key"): payload["key_scale"] = spec["key"]
    if spec.get("guidance_scale"): payload["guidance_scale"] = float(spec["guidance_scale"])
    _lora = spec.get("lora")
    if _lora and _lora in LORA_ADAPTERS:
        payload["lora_path"] = LORA_ADAPTERS[_lora]
    _lyrics = (spec.get("lyrics") or "").strip()
    if spec.get("instrumental"):
        payload.update({"prompt": spec["idea"], "lyrics": "[inst]", "instrumental": True})
    elif _lyrics:
        payload.update({"prompt": spec["idea"], "lyrics": _lyrics, "instrumental": False})
    else:
        payload.update({"sample_mode": True, "sample_query": spec["idea"]})
```

Above `pick_model()`:

```python
# XL switch and LoRA hooks. Fill LORA_ADAPTERS when an adapter lands, e.g.
# {"mr-dorgham": "/kaggle/working/adapters/mr-dorgham"}; the bot already sends the name.
MODEL_MAP = {"turbo": "acestep-v15-turbo", "turbo-shift3": "acestep-v15-turbo-shift3",
             "xl": "acestep-v15-xl"}
LORA_ADAPTERS = {}
```

Field meanings, from the ACE-Step 1.5 API reference: `guidance_scale` is CFG (default 7.0), `seed` is an int with -1 for random, `lyrics` is the full lyrics with `[inst]` for instrumental, `key_scale` takes values like `F# minor`. A vocal track with no lyrics still uses sample mode, so nothing that worked before changes.

For voice prompts, the setup cell can add `!pip install -q faster-whisper` (CPU, int8, base.en about 75 MB). The bot uses it only when a voice note arrives.
