# Zi Music Studio - Telegram bot (free, stdlib only)
# Runs inside the studio notebook (Colab/Kaggle) as a background thread:
# chat with @rahal_music_bot, send a prompt/genre, get tracks back in chat.
# Engine mode: calls the notebook's make_track()/run_queue() directly.
#
# Setup once per environment: add the bot token as a secret named
# ZI_BOT_TOKEN (Colab: key icon > Secrets; Kaggle: Add-ons > Secrets),
# then run the notebook's bot cell. First run prints a pairing code;
# the owner sends "/start <code>" in the bot chat to bind. Only the bound
# owner can use the bot - anyone else is refused (GPU hours are capped).

import hashlib, json, os, queue, random, re, subprocess, threading, time, urllib.request, urllib.parse, uuid

VERSION = "2026-11-28.5"

API = "https://api.telegram.org/bot{token}/{method}"
FILE_API = "https://api.telegram.org/file/bot{token}/{path}"
TG_LIMIT = 49 * 1024 * 1024  # bot upload practical limit

# GPU sharing guard: the bot renders in the same kernel as the notebook's own
# renders (Infra's FL queue), so a bot job must wait for the GPU to be free.
GPU_UTIL_LIMIT = 25        # percent; above this something is rendering
GPU_PROC_MB = 2000         # another process holding more than this is rendering
GPU_POLL_SEC = 30

GENRE_PRESETS = {
 "Melodic Techno": "120-124 bpm melodic techno, tight punchy kick, deep sub bass, emotional minor chord progression on a soft pluck, lush atmospheric pads, hypnotic arpeggio, distant reverb vocal chops, long DJ-friendly intro and outro, bittersweet 4am mood",
 "Indie Dance": "118-124 bpm indie dance, live-feel bass guitar groove, four-on-the-floor kick, funky guitar chops, analog synth stabs, warm claps, playful sun-soaked mood",
 "Peak Techno": "128 bpm peak-time techno, hard punchy kick, driving offbeat bass, hypnotic acid sequence, sharp hats, white-noise risers, relentless peak-hour club mood",
 "Afro House": "121-122 bpm deep afro house, smooth deep kick, warm sub, layered djembe and shaker groove, soulful chord stabs, flute-like lead, ocean-breeze pads",
 "Progressive": "122-126 bpm progressive house-techno, rolling bassline, crisp claps, slowly opening filter arpeggio, epic layered pads, festival riser, sunrise euphoria",
 "Downtempo": "100-105 bpm downtempo indie electronic, soft round kick, warm electric bass, dreamy washed guitars, mellow keys, vinyl texture, hazy nostalgic calm",
}
DURATIONS = [60, 120, 180, 240, 300, 330, 420, 600]
QUALITIES = [("high", "High (2 seeds, best pick)"), ("standard", "Standard"), ("fast", "Fast draft")]
AI_LABEL = "AI-generated music (ACE-Step 1.5, MIT licence). Label it AI-generated wherever you release it."

HELP = """Zi Music Studio bot - make tracks from chat.
/track - guided track builder (style, theme, length, vocals, quality)
/track <spec> - one-shot, e.g.: /track melodic techno, night drive, 330s, instrumental, high
/batch - send several tracks as JSON (list of specs), or paste after the command
/queue - what's rendering and what's waiting
/status - engine and session status
/library - latest releases (buttons to fetch)
/get <title> - send a track's MP3 + cover + info
/routenote <title> - send the RouteNote form text for a track
/jobs - import jobs saved by the Windows app (Drive zi_data/jobs)
/diag - build version and update counts (for debugging)
/cancel - cancel the current builder step
/help - this message
Every track is AI-generated and delivered with that label."""


class TG:
    def __init__(self, token):
        self.token = token
        self.thread_of = None      # callable(chat_id) -> message_thread_id or None

    def call(self, method, **fields):
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode({k: v for k, v in fields.items() if v is not None}).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read())
        if not out.get("ok"):
            raise RuntimeError(f"telegram {method} failed: {out.get('description')}")
        return out["result"]

    def _thread(self, chat_id):
        try:
            return self.thread_of(chat_id) if self.thread_of else None
        except Exception:
            return None

    def send(self, chat_id, text, keyboard=None):
        fields = {"chat_id": chat_id, "text": text[:4000], "message_thread_id": self._thread(chat_id)}
        if keyboard:
            fields["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
        return self.call("sendMessage", **fields)

    def _upload(self, method, chat_id, field, path, caption=None):
        boundary = uuid.uuid4().hex
        name = os.path.basename(path)
        with open(path, "rb") as fh:
            payload = fh.read()
        parts = []
        def head(extra, is_file=False):
            parts.append(f"--{boundary}\r\n".encode())
            if is_file:
                parts.append(f'Content-Disposition: form-data; name="{field}"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
            else:
                parts.append(f'Content-Disposition: form-data; name="{extra[0]}"\r\n\r\n{extra[1]}\r\n'.encode())
        head(("chat_id", str(chat_id)))
        th = self._thread(chat_id)
        if th:
            head(("message_thread_id", str(th)))
        if caption:
            head(("caption", caption[:1000]))
        head(None, is_file=True)
        parts.append(payload)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(parts)
        req = urllib.request.Request(API.format(token=self.token, method=method), data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=600) as r:
            out = json.loads(r.read())
        if not out.get("ok"):
            raise RuntimeError(f"telegram {method} failed: {out.get('description')}")
        return out["result"]

    def audio(self, chat_id, path, caption=None):
        return self._upload("sendAudio", chat_id, "audio", path, caption)

    def photo(self, chat_id, path, caption=None):
        return self._upload("sendPhoto", chat_id, "photo", path, caption)


class Bot:
    def __init__(self, token, out_root, work, make_track=None, run_queue=None):
        self.tg = TG(token)
        self.tg.thread_of = lambda cid: self.threads.get(cid)
        self.out_root = out_root
        self.work = work
        self.make_track = make_track
        self.run_queue = run_queue
        self.state_path = os.path.join(out_root, "zi_bot_state.json")
        self.owner_path = os.path.join(out_root, "zi_bot_owner.json")
        self.state = self._load(self.state_path, {"offset": 0})
        self.owner = self._load(self.owner_path, {}).get("chat_id")
        self.pair_code = None
        self.jobs = queue.Queue()
        self.threads = {}    # chat_id -> message_thread_id (topic chats)
        self.gpu_marker = os.environ.get("ZI_GPU_MARKER") or os.path.join(out_root, ".gpu_busy")
        self.gpu_poll = GPU_POLL_SEC
        self.queued = []     # titles waiting behind the current render
        self.current = None
        self.builders = {}   # chat_id -> dict of the guided /track flow
        self.stop = threading.Event()
        self.conflict_warned = False
        self.stats = {"message": 0, "callback": 0, "last": "nothing yet"}
        os.makedirs(out_root, exist_ok=True)

    @staticmethod
    def _load(path, default):
        try:
            return json.load(open(path))
        except Exception:
            return default

    def _save(self, path, obj):
        try:
            json.dump(obj, open(path, "w"))
        except Exception as e:
            print("bot state save failed:", e)

    # ---------- ownership ----------
    def ensure_pairing(self):
        if self.owner:
            print("Zi bot: owner bound, chat_id", self.owner)
            return
        self.pair_code = f"{random.randint(100000, 999999)}"
        print("=" * 50)
        print("Zi bot pairing code:", self.pair_code)
        print("Send this in Telegram to the bot:  /start", self.pair_code)
        print("=" * 50)

    def _is_owner(self, chat_id):
        return self.owner is not None and chat_id == self.owner

    # ---------- main loops ----------
    def start(self):
        self.ensure_pairing()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._poll, daemon=True).start()

    def _poll(self):
        while not self.stop.is_set():
            try:
                ups = self.tg.call("getUpdates", offset=self.state["offset"] + 1, timeout=30,
                                   allowed_updates=json.dumps(["message", "callback_query"]))
                for u in ups:
                    self.state["offset"] = u["update_id"]
                    self._save(self.state_path, self.state)
                    try:
                        self._handle(u)
                    except Exception as e:
                        print("bot handle error:", e)
            except Exception as e:
                msg = str(e)
                if "409" in msg or "Conflict" in msg or "terminated by other" in msg:
                    if not self.conflict_warned:
                        print("BOT CONFLICT: another instance is polling getUpdates for this token. "
                              "Stop it (ZI_BOT.stop.set() in an earlier cell, or restart the kernel) and start this one again.")
                        self.conflict_warned = True
                else:
                    print("bot poll error:", e)
                time.sleep(5)

    def _gpu_busy(self):
        """Why a render cannot start now, or None when the GPU looks free."""
        try:
            if self.gpu_marker and os.path.exists(self.gpu_marker):
                # a marker left behind by a crashed run must not block forever
                if time.time() - os.path.getmtime(self.gpu_marker) < 6 * 3600:
                    return "another render is holding the GPU"
        except Exception:
            pass
        try:
            procs = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                                    "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=15).stdout
            me = str(os.getpid())
            for line in procs.strip().splitlines():
                parts = [x.strip() for x in line.split(",")]
                if len(parts) < 2 or not parts[0].isdigit():
                    continue
                try:
                    mb = float(parts[1] or 0)
                except ValueError:
                    mb = 0
                if parts[0] != me and mb > GPU_PROC_MB:
                    return "another process is rendering"
            util = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu",
                                   "--format=csv,noheader,nounits"],
                                  capture_output=True, text=True, timeout=15).stdout
            vals = [int(v) for v in util.replace("\n", " ").split() if v.strip().isdigit()]
            if vals and max(vals) > GPU_UTIL_LIMIT:
                return "the GPU is busy"
        except Exception:
            return None
        return None

    def _mark_busy(self, on):
        try:
            if not self.gpu_marker:
                return
            if on:
                open(self.gpu_marker, "w").write(str(os.getpid()))
            elif os.path.exists(self.gpu_marker):
                os.remove(self.gpu_marker)
        except Exception as e:
            print("gpu marker failed:", e)

    def _wait_for_gpu(self, chat_id):
        """Hold the job until nothing else is rendering. Returns False if the bot stopped."""
        told = None
        while not self.stop.is_set():
            why = self._gpu_busy()
            if not why:
                if told:
                    self.tg.send(chat_id, "GPU is free, starting your render now.")
                return True
            if why != told:
                self.tg.send(chat_id, f"Waiting: {why}. Your track starts on its own as soon as it frees up, no need to resend.")
                told = why
            time.sleep(self.gpu_poll)
        return False

    def _worker(self):
        while not self.stop.is_set():
            try:
                job = self.jobs.get(timeout=1)
            except queue.Empty:
                continue
            chat_id, spec = job
            if spec.get("_thread"):
                self.threads[chat_id] = spec["_thread"]
            self.current = spec.get("title") or spec.get("name") or spec["genre"]
            try:
                if self.queued:
                    self.queued.pop(0)
            except Exception:
                pass
            if not self._wait_for_gpu(chat_id):
                break
            self.tg.send(chat_id, f"Rendering: {self.current} ({spec.get('seconds', 330)}s, {spec.get('quality', 'standard')}). A high-quality track takes 10-25 min on the free GPU - I will send it here when done.")
            try:
                self._mark_busy(True)
                r = self.make_track(spec, "Rahal", "Rahal")
                self._deliver(chat_id, r)
            except Exception as e:
                self.tg.send(chat_id, f"That track failed: {str(e)[:300]}. It stays out of the queue; send it again if you want a retry.")
            finally:
                self._mark_busy(False)
                self.current = None
                self.jobs.task_done()

    def _deliver(self, chat_id, r):
        base, folder, title = r["base"], r["folder"], r["title"]
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        mp3 = base + "_320kbps.mp3"
        if not os.path.exists(mp3) or os.path.getsize(mp3) > TG_LIMIT:
            mp3 = base + "_preview_128k.mp3"
        info = (f"{title} | {meta.get('genre','')} | BPM {meta.get('bpm')} | key {meta.get('key') or meta.get('keyscale')}"
                f" | {meta.get('actual_duration_sec','?')}s | QC {meta.get('qc_candidates',[{}])[0].get('score','?')}\n{AI_LABEL}")
        try:
            self.tg.photo(chat_id, os.path.join(folder, "cover_3000x3000.jpg"))
        except Exception as e:
            print("cover send failed:", e)
        self.tg.audio(chat_id, mp3, caption=info)
        self.tg.send(chat_id, "Saved in Drive: " + os.path.basename(folder) + " (WAV/FLAC/MP3, cover, lyrics, metadata, RouteNote form).")

    # ---------- update handling ----------
    def _handle(self, u):
        cb = u.get("callback_query")
        try:
            kind = "callback" if cb else "message"
            self.stats[kind] = self.stats.get(kind, 0) + 1
            self.stats["last"] = f"{kind} at {time.strftime('%H:%M:%S')}"
        except Exception:
            pass
        if cb:
            cmsg = cb.get("message") or {}
            chat_id = (cmsg.get("chat") or {}).get("id")
            if chat_id is None or not self._is_owner(chat_id):
                return
            if cmsg.get("message_thread_id"):
                self.threads[chat_id] = cmsg["message_thread_id"]
            # stop the button spinner even if the handler below fails
            try:
                self.tg.call("answerCallbackQuery", callback_query_id=cb["id"])
            except Exception as e:
                print("answerCallbackQuery failed:", e)
            try:
                self._callback(chat_id, cb["data"])
            except Exception as e:
                print("callback handler failed:", repr(e))
                try:
                    self.threads.pop(chat_id, None)
                    self.tg.send(chat_id, f"That step failed: {str(e)[:200]}")
                except Exception:
                    pass
            return
        msg = u.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        if chat_id is None:
            return
        if msg.get("message_thread_id"):
            self.threads[chat_id] = msg["message_thread_id"]
        text = (msg.get("text") or "").strip()
        doc = msg.get("document")
        if not self._is_owner(chat_id):
            if text.startswith("/start") and self.pair_code and text.endswith(self.pair_code):
                self.owner = chat_id
                self._save(self.owner_path, {"chat_id": chat_id})
                self.pair_code = None
                self.tg.send(chat_id, "Bound. This bot answers only you now.\n\n" + HELP)
            else:
                self.tg.send(chat_id, "This is a private studio bot.")
            return
        if doc and (doc.get("file_name") or "").endswith(".json"):
            self._batch_doc(chat_id, doc)
            return
        if not text:
            return
        if chat_id in self.builders and not text.startswith("/"):
            self._builder_text(chat_id, text)
            return
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower().split("@")[0]
        if cmd == "/start" or cmd == "/help":
            self.tg.send(chat_id, HELP)
        elif cmd == "/cancel":
            self.builders.pop(chat_id, None)
            self.tg.send(chat_id, "Cancelled.")
        elif cmd == "/track":
            self._track(chat_id, arg.strip())
        elif cmd == "/batch":
            self._batch_text(chat_id, arg.strip())
        elif cmd == "/queue":
            self._queue(chat_id)
        elif cmd == "/status":
            self._status(chat_id)
        elif cmd == "/library":
            self._library(chat_id)
        elif cmd == "/get":
            self._get(chat_id, arg.strip(), audio=True)
        elif cmd == "/cover":
            self._get(chat_id, arg.strip(), audio=False)
        elif cmd == "/routenote":
            self._routenote(chat_id, arg.strip())
        elif cmd == "/diag":
            self._diag(chat_id)
        elif cmd == "/jobs":
            self._jobs(chat_id)
        else:
            self.tg.send(chat_id, "Unknown command. /help lists them.")

    def _callback(self, chat_id, data):
        b = self.builders.get(chat_id)
        if data.startswith("lib:"):
            folder = self._lib_folder(data[4:])
            if not folder:
                self.tg.send(chat_id, "That release is not in this session's folder any more. /library lists the current ones.")
                return
            self._get(chat_id, folder, audio=True)
            return
        if not b and data in GENRE_PRESETS:
            # A tap can arrive after a session restart or on a second bot instance
            # that has no builder for this chat; start one instead of going dead.
            self.builders[chat_id] = {"step": "genre", "spec": {"lang": "en", "quality": "high",
                                                               "instrumental": True, "seconds": 330}}
            b = self.builders[chat_id]
        if not b:
            self.tg.send(chat_id, "That builder expired. /track starts a new one.")
            return
        step = b["step"]
        if step == "genre":
            b["spec"]["name"] = b["spec"]["genre"] = data
            b["spec"]["idea"] = GENRE_PRESETS[data] + ". Theme: "
            b["step"] = "theme"
            self.tg.send(chat_id, f"{data}. Theme or mood? (free text)")
        elif step == "seconds" and data.isdigit():
            b["spec"]["seconds"] = int(data)
            b["step"] = "instrumental"
            self.tg.send(chat_id, "Vocals?", keyboard=[[{"text": "Instrumental", "callback_data": "v:1"}, {"text": "With lyrics", "callback_data": "v:0"}]])
        elif step == "instrumental" and data.startswith("v:"):
            b["spec"]["instrumental"] = data == "v:1"
            b["step"] = "quality"
            self.tg.send(chat_id, "Quality?", keyboard=[[{"text": label, "callback_data": "q:" + q}] for q, label in QUALITIES])
        elif step == "quality" and data.startswith("q:"):
            b["spec"]["quality"] = data[2:]
            self._confirm(chat_id, b)
        elif step == "confirm":
            spec = b["spec"]
            self.builders.pop(chat_id, None)
            if data == "go":
                self._enqueue(chat_id, spec)
            else:
                self.tg.send(chat_id, "Cancelled.")

    def _builder_text(self, chat_id, text):
        b = self.builders[chat_id]
        if b["step"] == "theme":
            b["spec"]["idea"] = b["spec"]["idea"] + text
            b["step"] = "seconds"
            self.tg.send(chat_id, "Length?", keyboard=[[{"text": f"{d//60}:{d%60:02d}", "callback_data": str(d)} for d in DURATIONS[:4]], [{"text": f"{d//60}:{d%60:02d}", "callback_data": str(d)} for d in DURATIONS[4:]]])

    def _confirm(self, chat_id, b):
        b["step"] = "confirm"
        s = b["spec"]
        self.tg.send(chat_id,
            f"Ready: {s.get('genre')} | {s.get('seconds')}s | {'instrumental' if s.get('instrumental') else 'lyrics'} | {s.get('quality', 'standard')}"
            + (f" | title: {s['title']}" if s.get("title") else ""),
            keyboard=[[{"text": "Generate", "callback_data": "go"}, {"text": "Cancel", "callback_data": "no"}]])

    def _track(self, chat_id, arg):
        if arg:
            spec = self._parse_spec(arg)
            if spec:
                self._enqueue(chat_id, spec)
                return
        self.builders[chat_id] = {"step": "genre", "spec": {"lang": "en", "quality": "high", "instrumental": True, "seconds": 330}}
        self.tg.send(chat_id, "Style?", keyboard=[[{"text": g, "callback_data": g}] for g in GENRE_PRESETS])

    def _parse_spec(self, arg):
        # "melodic techno, night drive, 330s, instrumental, high, key Am, bpm 122, title X"
        parts = [p.strip() for p in arg.split(",") if p.strip()]
        if not parts:
            return None
        genre = parts[0]
        preset = GENRE_PRESETS.get(genre) or GENRE_PRESETS.get(genre.title())
        spec = {"name": genre, "genre": genre, "lang": "en", "quality": "standard",
                "instrumental": True, "seconds": 330,
                "idea": (preset or genre) + (". Theme: " + parts[1] if len(parts) > 1 else "")}
        for p in parts[1:]:
            m = re.match(r"^(\d+)\s*s(ec)?$", p.lower())
            if m: spec["seconds"] = max(60, min(600, int(m.group(1)))); continue
            low = p.lower()
            if low in ("high", "standard", "fast"): spec["quality"] = low; continue
            if "lyric" in low or "vocal" in low: spec["instrumental"] = False; continue
            if "instrumental" in low: spec["instrumental"] = True; continue
            mk = re.match(r"^key\s+(\S+)$", low)
            if mk: spec["key"] = mk.group(1); continue
            mb = re.match(r"^bpm\s+(\d+)$", low)
            if mb: spec["bpm"] = int(mb.group(1)); continue
            mt = re.match(r"^title\s+(.+)$", low)
            if mt: spec["title"] = mt.group(1); continue
            if p != parts[1] or len(parts) == 1:
                if ". Theme: " not in spec["idea"]:
                    spec["idea"] += ". Theme: " + p
        return spec

    def _enqueue(self, chat_id, spec):
        if not self.make_track:
            self.tg.send(chat_id, "No engine in this session. Run the notebook's engine cell first.")
            return
        spec.setdefault("seconds", 330)
        spec["seconds"] = max(60, min(600, int(spec["seconds"])))
        spec["_thread"] = self.threads.get(chat_id)
        self.jobs.put((chat_id, spec))
        self.queued.append(spec.get("title") or spec.get("name") or spec.get("genre") or "track")
        n = self.jobs.qsize()
        self.tg.send(chat_id, f"Queued: {spec.get('title') or spec.get('name') or spec['genre']} ({spec['seconds']}s, {spec.get('quality','standard')})." + (f" {n-1} ahead of it." if n > 1 and not self.current else ""))

    def _batch_text(self, chat_id, arg):
        if not arg:
            self.tg.send(chat_id, "Send the queue as JSON after /batch, or as a .json file. Each item: {\"title\":..., \"genre\":..., \"seconds\":..., \"instrumental\":true/false, \"quality\":\"high|standard|fast\", \"idea\":...}")
            return
        self._batch_load(chat_id, arg)

    def _batch_doc(self, chat_id, doc):
        try:
            f = self.tg.call("getFile", file_id=doc["file_id"])
            url = FILE_API.format(token=self.tg.token, path=f["file_path"])
            with urllib.request.urlopen(url, timeout=60) as r:
                self._batch_load(chat_id, r.read().decode())
        except Exception as e:
            self.tg.send(chat_id, f"Could not read that file: {str(e)[:200]}")

    def _batch_load(self, chat_id, raw):
        try:
            items = json.loads(raw)
            if isinstance(items, dict):
                items = [items]
            specs = [s for s in items if isinstance(s, dict) and (s.get("genre") or s.get("name"))]
            if not specs:
                raise ValueError("no valid specs")
        except Exception as e:
            self.tg.send(chat_id, f"That JSON did not parse into track specs: {str(e)[:200]}")
            return
        for s in specs:
            s.setdefault("idea", s.get("genre", ""))
            s.setdefault("lang", "en")
            self.jobs.put((chat_id, s))
            self.queued.append(s.get("title") or s.get("name") or s.get("genre") or "track")
        self.tg.send(chat_id, f"Batch queued: {len(specs)} track(s). They render back to back and land here as they finish.")

    def _status(self, chat_id):
        msg = []
        msg.append("Engine: ready" if self.make_track else "Engine: not loaded in this session (run the notebook's engine cell, then this bot cell)")
        msg.append("Rendering now: " + self.current if self.current else "Rendering now: nothing")
        msg.append(f"Waiting: {self.jobs.qsize()}")
        msg.append(f"Outputs save to: {self.out_root}")
        if self.out_root.startswith("/kaggle"):
            msg.append("Note: Kaggle keeps outputs in the notebook's Output section, not Drive. Save Version before the session ends.")
        msg.append("Owner: paired" if self.owner else "Owner: not paired yet")
        try:
            msg.append(f"Pollers in this process: {len(_bot_instances())}")
        except Exception:
            pass
        self.tg.send(chat_id, "\n".join(msg))

    def _queue(self, chat_id):
        q = list(self.queued)
        msg = ["Rendering now: " + (self.current or "nothing")]
        if q:
            msg.append(f"Waiting ({len(q)}):")
            for i, t in enumerate(q[:10], 1):
                msg.append(f"{i}. {t}")
            if len(q) > 10:
                msg.append(f"...and {len(q) - 10} more")
        else:
            msg.append("Nothing waiting. /track starts a new one.")
        self.tg.send(chat_id, "\n".join(msg))

    def _release_folders(self):
        """Folders in out_root that are real releases (skip _archive_wav, jobs, zi_data...)."""
        if not os.path.isdir(self.out_root):
            return []
        out = []
        for d in sorted(os.listdir(self.out_root), reverse=True):
            full = os.path.join(self.out_root, d)
            if not os.path.isdir(full) or d.startswith("_") or d in ("jobs", "zi_data"):
                continue
            try:
                names = os.listdir(full)
            except Exception:
                continue
            if "metadata.json" in names or any(n.endswith("_320kbps.mp3") for n in names):
                out.append(d)
        return out

    @staticmethod
    def _lib_key(folder):
        # Telegram caps callback_data at 64 bytes; a release folder name can reach 66.
        return hashlib.md5(folder.encode()).hexdigest()[:24]

    def _lib_folder(self, key):
        for d in self._release_folders():
            if self._lib_key(d) == key:
                return d
        return None

    def _diag(self, chat_id):
        lines = [f"build {VERSION}",
                 f"messages handled: {self.stats.get('message', 0)}",
                 f"callbacks handled: {self.stats.get('callback', 0)}",
                 f"last update: {self.stats.get('last', '?')}"]
        try:
            lines.append(f"pollers in this process: {len(_bot_instances())}")
        except Exception:
            pass
        lines.append(f"threads known: {len(self.threads)}")
        lines.append(f"outputs: {self.out_root}")
        self.tg.send(chat_id, "\n".join(lines))

    def _find_folder(self, needle):
        if not needle or not os.path.isdir(self.out_root):
            return None
        n = needle.lower().replace(" ", "_")
        cands = [d for d in sorted(os.listdir(self.out_root), reverse=True)
                 if os.path.isdir(os.path.join(self.out_root, d)) and not d.startswith("_")]
        for d in cands:
            if needle.lower() in d.lower().replace("_", " ") or n in d.lower():
                return os.path.join(self.out_root, d)
        return None

    def _library(self, chat_id):
        folders = self._release_folders()[:8]
        if not folders:
            self.tg.send(chat_id, "No releases yet in this session's folder. /track makes one; /status shows where they save.")
            return
        kb = [[{"text": re.sub(r"^\d{8}-\d{6}_", "", f).replace("_", " ")[:60], "callback_data": "lib:" + self._lib_key(f)}] for f in folders]
        self.tg.send(chat_id, "Latest releases (tap to fetch):", keyboard=kb)

    def _get(self, chat_id, needle, audio=True):
        folder = self._find_folder(needle)
        if not folder:
            self.tg.send(chat_id, "Nothing found for that. /library lists releases.")
            return
        title = re.sub(r"^\d{8}-\d{6}_", "", os.path.basename(folder)).replace("_", " ")
        base = None
        for f in os.listdir(folder):
            if f.endswith("_320kbps.mp3"):
                base = os.path.join(folder, f[:-len("_320kbps.mp3")])
        if not audio:
            cov = os.path.join(folder, "cover_3000x3000.jpg")
            if os.path.exists(cov):
                self.tg.photo(chat_id, cov, caption=title)
            else:
                self.tg.send(chat_id, "No cover in that folder.")
            return
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        r = {"base": base or os.path.join(folder, title.replace(" ", "_")),
             "folder": folder, "title": meta.get("title", title)}
        if base is None:
            self.tg.send(chat_id, "That folder has no MP3 yet.")
            return
        self._deliver(chat_id, r)

    def _routenote(self, chat_id, needle):
        folder = self._find_folder(needle)
        if not folder:
            self.tg.send(chat_id, "Nothing found for that. /library lists releases.")
            return
        p = os.path.join(folder, "routenote_form.txt")
        if not os.path.exists(p):
            self.tg.send(chat_id, "No RouteNote form text in that folder.")
            return
        self.tg.send(chat_id, open(p).read())

    def _jobs(self, chat_id):
        roots = [os.path.join(self.out_root, "jobs"),
                 os.path.join(os.path.dirname(self.out_root.rstrip("/")), "zi_data", "jobs")]
        found = []
        for r in roots:
            if not os.path.isdir(r):
                continue
            for fp in sorted(os.listdir(r)):
                if not fp.endswith(".json"):
                    continue
                try:
                    j = json.load(open(os.path.join(r, fp)))
                    if isinstance(j, dict) and (j.get("title") or j.get("name")):
                        found.append(j)
                except Exception:
                    pass
        if not found:
            self.tg.send(chat_id, "No app jobs found in Drive (looked in Zi_Music/jobs and zi_data/jobs).")
            return
        for j in found:
            j.setdefault("idea", j.get("genre", ""))
            j.setdefault("lang", "en")
            self.jobs.put((chat_id, j))
            self.queued.append(j.get("title") or j.get("name") or j.get("genre") or "track")
        self.tg.send(chat_id, f"Imported {len(found)} app job(s) into the queue.")


def _bot_instances():
    """Every Bot instance that still has a polling thread in this process, whatever version created it."""
    seen = []
    for t in threading.enumerate():
        obj = getattr(getattr(t, "_target", None), "__self__", None)
        if obj is None or obj in seen:
            continue
        if obj.__class__.__name__ != "Bot" or not hasattr(obj, "stop"):
            continue
        if not t.is_alive():
            continue
        seen.append(obj)
    return seen


def stop_other_bots(keep=None, timeout=40):
    """Stop stale pollers left by earlier runs (any version), then wait for them to exit."""
    others = [b for b in _bot_instances() if b is not keep]
    for b in others:
        try:
            b.stop.set()
        except Exception:
            pass
    if others:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not [b for b in others if b in _bot_instances()]:
                break
            time.sleep(1)
    return len(others)


def start_engine_bot(token, make_track, run_queue, out_root, work):
    """Start the bot inside the studio notebook (engine cells already run)."""
    # The previous instance is parked on builtins so it survives importlib.reload
    # (cell 5 reloads this module). Re-running the cell must not leave a second
    # poller on getUpdates: Telegram answers one consumer, the other gets 409s.
    import builtins
    prev = getattr(builtins, "_zi_bot_instance", None)
    if prev is not None:
        try:
            prev.stop.set()
        except Exception:
            pass
    stale = stop_other_bots(keep=prev)
    if prev is not None or stale:
        print(f"Stopped {stale} stale poller(s) from earlier runs; starting a fresh one.")
    bot = Bot(token, out_root=out_root, work=work, make_track=make_track, run_queue=run_queue)
    bot.start()
    builtins._zi_bot_instance = bot
    print(f"Zi Telegram bot running (build {VERSION}). Chat with the bot in Telegram; /help lists commands.")
    try:
        print(f"Pollers in this process after start: {len(_bot_instances())} (1 is healthy)")
    except Exception:
        pass
    return bot
