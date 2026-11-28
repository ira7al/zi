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
Re-running cell 5 always picks up `main`. To load a specific commit instead (a build that has not reached `main` yet, or going back to a known-good one), paste this as its own cell. Replace `SHA` with the commit; the cell fetches all three bot files, and run it only after the engine cells, because it reuses `make_track`, `run_queue`, `OUT_ROOT` and `WORK`.

```python
# pinned bot reload - the correct start call is start_engine_bot(...), not start()
import os, sys, importlib.util, urllib.request
SHA = "PUT_COMMIT_SHA_HERE"
try:
    ZI_BOT.stop.set()
    print("Stopped the previous bot instance.")
except Exception:
    pass
# drop every cached copy of the bot's modules so the new files are the ones that run
for _m in ("zi_bot", "zi_options", "zi_assistant", "zi_voice", "zi_art"):
    sys.modules.pop(_m, None)
for _rel in ("bot/zi_bot.py", "bot/zi_options.py", "bot/zi_assistant.py", "bot/zi_voice.py", "bot/zi_art.py"):
    _src = f"https://api.github.com/repos/ira7al/zi/contents/{_rel}?ref={SHA}"
    _raw = f"https://raw.githubusercontent.com/ira7al/zi/{SHA}/{_rel}"
    try:
        _req = urllib.request.Request(_src, headers={"Accept": "application/vnd.github.raw", "User-Agent": "zi-notebook"})
        with urllib.request.urlopen(_req, timeout=60) as _r:
            _code = _r.read()
    except Exception as _e:
        print("API download failed (", _e, "), falling back to raw.githubusercontent.com")
        with urllib.request.urlopen(_raw, timeout=60) as _r:
            _code = _r.read()
    open(os.path.join(LOCAL_TMP, os.path.basename(_rel)), "wb").write(_code)
    print(os.path.basename(_rel), len(_code), "bytes")
_bot_path = os.path.join(LOCAL_TMP, "zi_bot.py")
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

## What the prompt screen tells him (build .24)

- A real artist or track name is taken out of the prompt field, and the screen says exactly what went and why, in Arabic and English: the removed words in quotes, then "real artist or track names never go in the prompt field; the description around the name is kept".
- A description after "inspired by" or "similar to" is not a name and stays: only a capitalised span that music vocabulary does not explain is removed.
- Nothing removed: a tick line instead.
- **Use as reference** turns the removed name into a style through the free lookup, so the name still does something useful.
- A link or a screenshot sent at either prompt step (write my own, or AI writes it) is a reference, not prompt text. YouTube, Spotify, SoundCloud and Apple Music pages are read through `og:title` as well as `<title>`.

## The free model behind the Assistant (build .22)

Add a secret named **ZI_LLM_KEY** (Kaggle: Add-ons > Secrets; Colab: key icon > Secrets with notebook access on) holding a free Gemini API key from Google AI Studio. Nothing else changes: the bot reads it itself, and without it the Assistant keeps answering from the bot's state exactly as in .21.

- Model: `gemini-3.1-flash-lite` by default, because a new free key answers 404 on `gemini-2.0-flash` and `gemini-2.5-flash` (retired for new keys). No env var is needed. `ZI_LLM_MODEL` still overrides it, and `ZI_VISION_MODEL` overrides the model used for screenshots (it defaults to the same one).
- Gemini 3 thinking: it is billed against `maxOutputTokens`, which used to return HTTP 200 with no text at all. Thinking is now off (`thinkingBudget: 0`), the budget is 1500, and a model that refuses that setting is retried once without it. Only the answer parts count; thought parts are skipped, and an empty answer falls back to the grounded replies instead of silence.
- Grounding: the request carries the same state block the rule-based answers use (build, engine, queue, dataset split, liked count, connected platforms, LoRA, voice/OCR). The system instruction tells the model to answer in Egyptian Arabic, short, from that state only, and to say it cannot see something rather than invent it.
- Rate limits and failures: a 429, a quota error, a broken response or a network blip all fall back to the grounded answers, so a tap never goes unanswered.
- The key never appears in a URL or in the logs: it travels in the `x-goog-api-key` header, and only an HTTP status code is ever printed. The state block carries no tokens or secrets.

Also fixed in .22: the notebook's bot cell and this reload cell now fetch `bot/zi_assistant.py` as well - .21 added the file, and a cell that fetched only two files would have failed to import the bot.

## The assistant (build .21)

Menu > Assistant, or `/ask <question>`, or `/ask` alone for a short chat (ends with `/end` or "خروج"). It answers in Egyptian Arabic, short, from the bot's own state: build, engine loaded or not, what is rendering, the queue, the training set count and split, how many tracks are liked, which platforms are really connected, whether the LoRA is trained, and whether voice and OCR are available on the box.

There is no model and no key in it. Every sentence comes from a field the bot already has, which is why it cannot invent a number or promise a feature. When it does not understand, it says so and lists what it can answer.

What it cannot do: free conversation. It is not a chatbot that discusses anything - it is a status and next-step assistant with intent matching. A hosted free-tier model would allow real conversation; that needs a key (through a vault link, never in chat) and would send the question plus a state summary to that provider. `zi_assistant.context_block()` already renders the facts for that, so adding it later changes the wording only.

## Menu and Studio under the message box (build .20)

Two buttons now sit under the message box in the bot chat:

- **Menu** opens the bot's menu (everything it can do, one tap each)
- **Studio** opens the Studio web app at https://ira7al.github.io/zi/ as a Mini App, the same URL the chat's menu button already used

They are sent when the owner binds the bot, on `/start`, `/help`, `/menu` and `/studio`. The Studio menu button in the corner is unchanged, so there are two ways in. Tapping Menu used to be read as a free-text idea; it opens the menu now.

## Reference: work out the style from something he already knows (build .19)

In the prompt step, **Reference** asks for what he has in mind. Any of these works:

- a track or artist name -> the free iTunes lookup returns its genre label, which picks one of the style profiles
- a link -> the page's title and description only; no audio is fetched from YouTube, Spotify or anywhere else
- a screenshot -> read with OCR (the setup cell installs pytesseract and tesseract, free and CPU only); without it the bot asks for the name as text
- a voice note -> the existing transcript path, so Egyptian Arabic works

Before anything is used the bot shows what it understood: style, mood, BPM range, key, instrumentation, and the prompt itself, with Use it / Edit / Another / New reference. The name is only used to choose the style - it is stripped from the prompt words - and no melody or lyrics are copied. If nothing can be worked out, it says so and asks for genre and BPM in words.

## Repeat the last settings (build .18)

`/track` opens with a button carrying the last settings used: style, length, instrumental or not. One tap shows the same Ready card and one more tap renders it again; `/track again` does the same from a message. The settings are saved on every queue, so they survive a kernel restart.

"Another" on a prompt preview now changes the arrangement as well as the mood: three moods, four focuses (arpeggio, bassline, pads, percussion) and three mixes, so twelve different prompts come out of one idea.

## What a long render and a failure look like now (build .17)

- A high-quality render sends one line every 5 minutes: still rendering, how long it has been, nothing to resend.
- A failure is three different messages, not one: the render failed (with the error and where the traceback is), the track rendered but sending it failed (with the folder on disk), or the engine returned nothing.
- One bad job cannot stop the queue. The bot says it is still running and the next job goes ahead.
- Telegram network blips are retried three times (timeout, connection reset, 429 with its retry_after, 5xx) instead of losing a track.

Prompt changes in the same build:

- The section map is worked out in bars from the BPM and the length picked, so a 5:30 track at 102 BPM is no longer described as a 6:54 arrangement.
- Instrumental prompts end the style line with "Instrumental, no vocals."; vocal prompts carry a vocal delivery line and the vocal language goes to the engine.
- A theme written in Arabic is not silently dropped: the bot asks for it in English, because the prompt field has to be English.

## Keeping a track ("this is the one")

Under every delivered track the publish menu has one star row: **⭐ This is the one**. A tap copies that release into `liked/<key>_<title>/` on the notebook machine - the 320 kbps MP3, the cover, the lyrics and metadata.json - and records it in `zi_bot_liked.json` next to the bot state. `/liked` lists the keepers with the date each was marked.

That folder is the LoRA set later: pick the ones you like in chat as you generate, and nothing else has to be sorted out afterwards. If the notebook restarted and the release folder is gone, the bot says so instead of silently doing nothing.

## Training set for the Mr Dorgham model

The bot now collects the training data. Send a track to the bot (audio file or voice note) and it is saved on the machine running the notebook:

- `dataset/mr-dorgham/` next to the notebook, original filename kept, `dataset/mr-dorgham/manifest.json` with the sha256 of every file.
- A file already in the set (same bytes) is refused, so re-sending does not duplicate. A repeat name becomes `name (2).mp3` - nothing is ever overwritten.
- After each save the bot asks **Vocal** or **Instrumental**. Vocal then offers optional lyrics: send them as a message, or as a `.txt` file; it is stored beside the track as `track.lyrics.txt`. Instrumental needs nothing more.
- Telegram caps bot downloads at 20 MB. A bigger file is refused with the size and what to do: send the MP3 instead, or upload the folder to Drive.
- `/dataset` (or Menu > Dataset) shows the running count, the vocal/instrumental split, and which files still need a label.

Labels and lyrics go into the same manifest, so the training step can read one file:

```json
{"files": {"<sha256>": {"name": "track.mp3", "size": 4833112, "added": "2026-11-28 11:20:00",
                        "kind": "vocal", "lyrics": "track.lyrics.txt"}}}
```

Nothing in this feature generates music or touches the GPU.

## Bot build 2026-11-28.52: music quality

- Image or cover-art text is never used as a music idea any more. A visual description is replaced by a genre prompt, and a pasted image prompt is refused.
- Fix: style tags, avoid list, weirdness and maqam were dropped before reaching the prompt. They now arrive.
- "This is bad / make another" (text or voice) goes to a redo: new seed, previous prompt adjusted, then the usual summary and Generate button. Nothing generates by itself.
- Speech parsing: Egyptian number words next to tempo or time words, more BPM spellings, maqam names (Saba and others), solfege keys. The speech hint sent to whisper is a neutral vocabulary list.
- Models the box does not have are dropped from the spec and from the model button.
- Trace log `zi_bot_trace.jsonl` (no tokens, no audio), owner command `/trace` shows the last 20 lines.
- Engine patch cell (paste after the engine cell): caps turbo at 8 steps, drops guidance for turbo, prefers the XL turbo model if listed, records the engine used.

```python
exec(urllib.request.urlopen("https://raw.githubusercontent.com/ira7al/zi/e7454280d3eb7374689b959c9c7f1999f04b2f42/colab/engine_patch_52.py").read().decode())
```

## Bot build 2026-11-28.51: QC fixes

- YouTube confirm step offers Public, Unlisted or Private. Each button is its own explicit tap, so nothing uploads without one. Public is the first button, as before.
- The Studio page's service worker cache is now `zi-studio-v2` and it clears old caches, so installed phones pick up updates. It is still only a launcher.
- Dorgham and RouteNote Form moved under More. The main menu keeps New Track, Library, Prompt + Reference, AI Writes It, Social Links, More and Studio.
- Facebook is a real link button in Social Links (and in YouTube descriptions).
- Fix: the animated YouTube video always failed to render, because ffmpeg could not pick an output format for the temporary `.part` file. Both videos are also cut to the audio length (they ran 0.5 s long before). A new test builds a 5 min 10 s track and checks with ffprobe that video and audio lengths match within 0.15 s.

## Bot build 2026-11-28.50: verified phone

- A stranger's first message gets a Share My Number button (Telegram's request_contact). The number is accepted only when the contact's user id equals the sender's id, so Telegram has verified it and nobody can submit someone else's. It is stored as phone, phone_verified and phone_verified_at in the private record. It is optional.
- SMS and WhatsApp codes cost money per message, so they are not built. `PHONE_PROOF` in `bot/zi_options.py` holds empty slots for them.
- The notice in the bot and the privacy page now mention the phone number.

## Bot build 2026-11-28.49: private user records

- Everyone who opens the bot is recorded: Telegram id, username, name, language, first and last seen, role (admin or user) and plan (free by default, owner for Rahal; room for paid plans later, no payments built). The owner's library metadata (title, style, settings, starred) is recorded too. Only listed fields are written, so no token or file path can reach the records.
- Records go to the PRIVATE repo `ira7al/zi-private-data` (`users/<id>.json`, `library/<owner id>.json`) on first login and then every 30 minutes when something changed. The bot needs a secret named `ZI_DATA_TOKEN` (a token that can write to that one repo). Without it the records stay on the device and `/diag` says so. `ZI_DATA_REPO` can override the repo name.
- Rahal (id 7835590874) is the owner by default when no owner file exists, so a wiped device needs no pairing code. An existing owner file always wins. `ZI_OWNER_ID` overrides the default.
- A one-line notice is in the pairing message and in the first reply to a stranger. The privacy page now says what is stored.

## Bot build 2026-11-28.48: English buttons

- Every button label is English, short, with an emoji (New Track, Library, Prompt + Reference, AI Writes It, Social Links, Dorgham, RouteNote Form, More, Studio, Generate, Ask Me, Publish, Remix / Cover, Remaster, Tweak & Regenerate, Cover Art, Video, Mark as The One, Another Track). All bot messages stay Egyptian Arabic.
- The labels are mapped in one place (`BUTTON_EN` and `en_keyboard` in `bot/zi_bot.py`) when a keyboard is sent. A test checks that no button text in the source stays Arabic.

## Bot build 2026-11-28.47: any language in, English prompt out

- Prompts and voice notes in any language (Arabic, English, Russian, German and others) work. Groq (gpt-oss-120b, then qwen) detects the language and writes a clean English music prompt, style only, no real artist or track names. The bot shows it in one short line, then continues.
- English input passes through unchanged and never waits on a model. A pasted "البرومبت:" or "Prompt (...)" label is stripped first. That label was why the English prompt in the screenshot got the "write it in English" reply: the Arabic word tripped the script check.
- The "write it in English" refusal is gone. With no Groq key, Arabic falls back to the local word list. Other scripts get a polite "ما وصلنيش كويس، ممكن تعيدها؟".
- Voice: whisper-large-v3-turbo with the language auto-detected, nothing forced.

## Bot build 2026-11-28.46: remix/cover and remaster in the library

Beside "📣 انشر" under each library track: "♻️ ريميكس/كفر" and "🎚 ريماستر". Each button appears only when the engine cell defines it (`COVER_TASKS` and `remaster_release`), so until the patch below runs, nothing new shows.

**Engine patch (run once, in a new cell after the engine cell, same kernel):**

```python
import urllib.request
exec(urllib.request.urlopen("https://raw.githubusercontent.com/ira7al/zi/d5c60c10d1c49589b90592eed43ec067af2d9d5d/colab/engine_patch_46.py").read().decode())
print("cover:", COVER_TASKS, "| remaster:", callable(remaster_release))
```

What the patch does:
- Cover: when a spec has `task_type: "cover"`, the generation request gets `task_type="cover"`, `src_audio_path` (the saved FLAC) and `audio_cover_strength` (0.8 close, 0.65 default, 0.4 far). The rest of the render path is unchanged. The result is a new release titled "<title> (Remix)".
- Remaster: `master_file(path)` runs `master_audio` and sets `verified` only when the output is at or below -0.9 dBTP and within 1 LU of -14 LUFS. `remaster_release(folder)` writes a new release "<title> (Remaster)" (FLAC, MP3 320, preview, cover, lyrics, metadata with `remaster_of`). The original folder is never changed. The bot tells him if the measurement is off target.
- The same edit is already in `colab/Zi_Music_Studio.ipynb` for fresh runs.

Not verified without a live render: the cover request against the real server, and cover at 10 minutes. The remaster function was run for real on a synthetic FLAC (output -14.05 LUFS, a new folder, the original untouched).

Reload with the pinned cell below.

## Bot build 2026-11-28.45: audio reference and the Dorgham toggle

- New-track menu: "🎧 ارفع تراك/MP3 كمرجع" sits beside "برومبت من عندي". He sends a track (up to 20 MB), the bot measures tempo, key and brightness with ffmpeg and numpy, picks the nearest style, and uses it with his own prompt. Style only: tags, file names and lyrics are never read, and the file is deleted right after. It is a rough hint, not genre recognition. The button shows only when ffmpeg and numpy exist.
- "🧬 استخدم الدرغام" toggle beside the style buttons. It shows only when `LORA_ADAPTERS` in the engine cell has an adapter (empty today, so hidden). It sets `spec["lora"]`, which the engine cell already turns into `lora_path`.
- Not added, because the engine cannot do them yet: cover/repaint, remix, remaster from a saved track. See the report for what is missing.

Reload with the pinned cell below.

## Bot build 2026-11-28.44: tweak after listening, silent voice

- After a render: "🎛 عدّل وولّد تاني" opens أكتر / أقل buttons with a one-line Arabic explanation each: الغرابة, تأثير الستايل, الطول, السرعة (BPM). "ولّد تاني بالتعديل" renders a fresh take (new seed, same prompt). Not shown before generating.
- No "coming soon" buttons anywhere (صوت مرجعي, كفر, LoRA are gone).
- Voice notes are no longer echoed. The bot shows a typing indicator, then acts. The heard text appears only when it is unsure ("ما وصلنيش كويس ... سمعت: ..."). Transcripts stay in `transcripts.log`.

Reload with the pinned cell below.

## Bot build 2026-11-28.43: no option grid, settings from his words

- Under the prompt there are only "ولّد" and "اسألني". The bot shows one line, "هعمل: ... تمام؟" (genre, music only or lyrics, length, BPM, key, title, tags). Generate starts the track.
- He changes settings by voice or text: "خليها ٤ دقايق", "بكلمات", "من غير كلام", "١٢٠ BPM", "A minor", "العنوان X", "avoid X", "weirdness 70", "steps", "seed". Unclear words get "ما وصلنيش كويس". A short "يلا" or "ولّد" starts it. Defaults are unchanged (instrumental).
- After a render only "⭐ ده التراك المطلوب" shows. After he approves: 🎨 غلاف, 🎬 فيديو, 📣 انشر (publishing still needs its own confirm tap).

Reload with the pinned cell below.

## Bot build 2026-11-28.42: reactions and playful tone

- Every voice note or photo he sends gets a 👀 reaction. Casual chat gets a fitting one by code rules (thanks 👍, laughing 😂, win 🔥, love ❤), at most one every 15 seconds. Work messages get none.
- The model can add one reaction with a [[react:X]] tag (👍 ❤ 🔥 😂 👀 🎉 🤔 only). The tag is stripped from the text.
- Tone: street Egyptian, light teasing and emoji, actionable answers stay short and correct.

Reload with the pinned cell below.

## Bot build 2026-11-28.41: image, link and words as one request

- An image or link plus text or voice (either order, within 90 seconds, a caption, or a reply to the image) is handled as one request. The bot looks at the image (Groq vision, then Gemini), reads what he said, and answers once.
- Reference words (مرجع, ستايل, زي ده...) make it a style-only reference for the prompt flow. A lone image or link waits with buttons "ستايل مرجع" and "سيبها".
- If the image cannot be read, the bot says so and asks what is in it. Nothing is claimed that did not run.

Reload with the pinned cell below.

## Bot build 2026-11-28.40: menu rework

- المكتبة holds every track (made ones, with the running job and queue shown on top). Opening a track sends it with a "انشر" button that starts the publish flow (artwork, video, metadata, confirm tap) for that track.
- "انشر آخر تراك" is gone from the main menu. "الداتا سيت" is now "الدرغام".
- "⚙️ حاجات تانية" holds الحالة, تشخيص, المساعد, مساعدة.

Reload with the pinned cell below.

## Bot build 2026-11-28.39: own prompt plus reference, feedback, Groq whisper

- New-track menu: "برومبت من عندي" now takes an optional reference (link or screenshot, before or after the prompt) and uses both together, style only, no names. The separate "مرجع" button and the "Last" row are gone.
- Change requests ("خلي الزرار...") are saved to `feedback_notes.jsonl` in the output folder and answered with "وصّلتها للمطوّر". Read them with `cat <out_root>/feedback_notes.jsonl`.
- Unclear or garbled input gets "ما وصلنيش كويس، ممكن تعيدها؟" and the menu, never a blunt line.
- Voice notes: Groq `whisper-large-v3-turbo` first (then `whisper-large-v3`), then the local model with beam 5. Every transcript is logged to `transcripts.log` in the output folder and the console. The "سمعتك:" echo stays.

Reload with the pinned cell below.

## Bot build 2026-11-28.38: vision through Groq

Screenshots: Groq `qwen/qwen3.8-27b` first (same Groq key as chat; override with `ZI_GROQ_VISION_MODEL`), then Gemini, then a plain Arabic message that the picture could not be read. Sent as an OpenAI-style `image_url` data URL with `max_completion_tokens` and a normal User-Agent. 429 backs off twice. The vision prompt names nobody. Groq limits (per org): 30 requests/min, 1000/day. Reload with the pinned cell below.

## Bot build 2026-11-28.37: assistant prompt and tone

The assistant now answers general questions (music terms, LoRA, BPM, anything) directly and briefly. Project facts (Mr Dorgham count, queue, publishing) only appear when he asks about the project. The tone is street Egyptian with five short examples in the prompt; formal and MSA phrasing and technical words are banned. The jargon filter now matches whole words, so ordinary words like "rapid" are no longer dropped. Same prompt feeds Groq and Gemini. Reload with the pinned cell below.

## Bot build 2026-11-28.36: Groq model fix

Groq default is now `openai/gpt-oss-120b`; on 404 or another HTTP error the next model is tried (`qwen/qwen3.8-27b`), `ZI_GROQ_MODEL` still goes first. Then Gemini, then the grounded answers. Screenshots stay Gemini-only and say plainly when they cannot be read. Reload with the pinned cell below.

## Bot build 2026-11-28.35: Groq for the assistant

Answer order: Groq (OpenAI-compatible, free plan), then Gemini, then the grounded rule-based answers. Key: Kaggle/Colab secret `GROQ_API_KEY` (or env `ZI_GROQ_KEY`). Model: `openai/gpt-oss-120b`, override with `ZI_GROQ_MODEL`. A 429 is retried with a short backoff, then it falls through. The key is only sent in the Authorization header and never printed. `/diag` shows whether each key is present. Reload with the pinned cell below.

## Bot build 2026-11-28.34: Arabic everywhere

Every screen, button, status, error and help line the user sees is Egyptian Arabic now (proper names such as YouTube, RouteNote, LoRA and Mr Dorgham stay). All keyboards use at most two buttons per row, so labels are never cut off. Prompt text sent to the engine stays English by design. Reload with the pinned cell below.

## Bot build 2026-11-28.33: voice, vision, reload

- Voice: edge-tts now runs as its own process (private event loop thread as backup), so it works inside Jupyter and the Egyptian voice is used before gTTS.
- Vision: models tried in order: `ZI_VISION_MODEL` (comma list ok), then known fallbacks, then whatever the key's own model list offers for images. 429 and 5xx are retried with backoff. If none can read the picture, the bot says so plainly; OCR text is kept only if it holds real words.
- Reload cell clears the cached bot modules first, so an old assistant module cannot stay in memory. Reload with the cell below (pinned to the build .33 commit).

## Bot build 2026-11-28.32: video, artwork, auto-filled YouTube

Reload with the pinned cell below (it now also fetches `bot/zi_art.py`). Nothing new to install: numpy and Pillow come with Colab and Kaggle, and ffmpeg needs `showwaves` and `showfreqs` (standard builds have them).

- After "This is the one", two buttons: Artwork (four procedural looks matched to the track's mood, pick one, "more" for another set; it replaces the cover) and YouTube video (audio-reactive, same length as the track, cover as the centrepiece).
- Rendering takes roughly the track length. Telegram only receives videos under its size limit; a bigger one is saved in the release folder.
- Upload to YouTube sits behind its own confirm button and shows the auto-filled title, description, tags, credits, links and the AI wording. Nothing to type; no artist or track names reach the text.
- Menus use two buttons per row in Egyptian Arabic; Social links adds SoundCloud (profile only). The Facebook Page link is not in the repo yet.

## Bot build 2026-11-28.31: reload and engine patch

The bot loads three files (`bot/zi_bot.py`, `bot/zi_options.py`, `bot/zi_assistant.py`), so a cell that only fetches `zi_bot.py` fails. Use this cell instead; it pins the commit and fetches all three.

What .25 changes for whoever is testing:

- Typed text with nothing open goes to the assistant and gets an answer plus two or three next-step buttons. A spoken idea still starts a track; a spoken question goes to the assistant.
- A one-line hint and an "اسألني" button sit on the track menu, the prompt preview, the options screen, the ready card and the message after delivery.
- No keyboard under the message box any more. The bot sends `remove_keyboard` once so the old Menu and Studio buttons disappear from his device, and Studio is now a button inside the inline menu.
- The corner button is the only Menu. Telegram's Bot API cannot make it send a message (it can only open the command list, open a web app, or do nothing), so the command list is a single entry, `Menu`: corner -> Menu -> every action arrives in the chat as inline buttons. That is two taps, and it is the shortest the platform allows; the only one-tap option is a reply keyboard, which he asked to remove.
- `/status` is plain Egyptian Arabic: what is rendering or idle, how many are waiting, where the tracks are saved before the session ends, and the Mr Dorgham track count. Engine, owner, poller and path lines moved to `/diag`.
- The assistant introduces itself as مساعدك الشخصي, never "مساعد راهال", and no answer mentions the engine, OCR or voice. A model answer that does is replaced by the grounded answer, so it cannot claim a capability that is not live on the box.
- Every status and greeting carries the Mr Dorgham count and how many tracks are still needed.
- A screenshot (as a photo or as an image file) is read by the free vision model with the key already in `ZI_LLM_KEY` when OCR is missing. Only the style reaches the prompt; the artist and track name are stripped and the removed words are shown. If the model refuses or the daily limit is gone, he gets a plain Arabic line asking for the name or a voice note.
- A voice note is answered out loud: edge-tts with the Egyptian voice `ar-EG-ShakirNeural`, then gTTS `ar`/`co.eg`, and ffmpeg turns the mp3 into a real voice note. With none of them the answer is text only. A spoken question goes to the assistant; a spoken music idea still starts a track.
- Installs needed on the box (both free, small, no key): `pip install -q edge-tts gTTS`. ffmpeg is already on Colab and Kaggle; without it the reply arrives as an audio file instead of a voice note. The setup cell in the notebook now installs both.
- `/diag` prints which voice engines are on the box and whether screenshots have a key.

```python
# pinned reload - build .52 (bot + options + assistant + voice + art)
import os, sys, importlib.util, urllib.request
SHA = "e7454280d3eb7374689b959c9c7f1999f04b2f42"
try:
    ZI_BOT.stop.set()
    print("Stopped the previous bot instance.")
except Exception:
    pass
# drop every cached copy of the bot's modules so the new files are the ones that run
for _m in ("zi_bot", "zi_options", "zi_assistant", "zi_voice", "zi_art"):
    sys.modules.pop(_m, None)
for _rel in ("bot/zi_bot.py", "bot/zi_options.py", "bot/zi_assistant.py", "bot/zi_voice.py", "bot/zi_art.py"):
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

Voice prompts: the setup cell installs `faster-whisper` (CPU, int8, multilingual). The bot loads `small` (or `base` if that fails) the first time a voice note arrives and keeps it warm, so a render is never slowed. Arabic is mapped to English prompt words through the lexicon in `bot/zi_options.py`, and both the heard text and the English are echoed back before anything renders.
