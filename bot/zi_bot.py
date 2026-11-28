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

import hashlib, json, os, queue, random, re, subprocess, threading, time, traceback, urllib.request, urllib.parse, uuid

VERSION = "2026-11-28.14"

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

# ---------- shared option model ----------
# zi_options.py holds the option definitions, the prompt builder and the mapping onto
# real engine parameters. The desktop app and the web app read the same definitions, so
# the bot is not a separate implementation.
try:
    import zi_options as opt
except Exception:  # loaded by path from the notebook: add this file's folder
    import importlib.util as _ilu
    _opt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zi_options.py")
    _opt_spec = _ilu.spec_from_file_location("zi_options", _opt_path)
    opt = _ilu.module_from_spec(_opt_spec)
    _opt_spec.loader.exec_module(opt)

build_prompt = opt.build_prompt
clean_idea = opt.clean_idea
_structure = opt.structure
OPTIONS = opt.OPTIONS

# Keys the notebook's make_track reads. Different engine builds have used different
# names for the length, so the bot fills all of them with the same value.
REQUIRED_SPEC_KEYS = ("name", "genre", "idea", "lang", "instrumental", "seconds", "quality")
LENGTH_KEYS = ("seconds", "duration", "duration_sec", "target_sec")
QUALITIES = [("high", "High (2 seeds, best pick)"), ("standard", "Standard"), ("fast", "Fast draft")]
AI_LABEL = "AI-generated music (ACE-Step 1.5, MIT licence). Label it AI-generated wherever you release it."

# ---------- publishing ----------
# The bot token administers the channel (that is how its photo and description were
# set), so the channel is the one platform that posts end to end from here.
CHANNEL = "@rahal_music"
PUBLISH_AI = "AI-generated with ACE-Step under Rahal's direction and selection."
PUBLISH_TAGS = "#melodictechno #indiedance #progressivehouse #afrohouse"
PLATFORMS = [("yt", "YouTube"), ("ig", "Instagram"), ("tt", "TikTok"),
             ("tg", "Telegram channel"), ("fb", "Facebook")]
PLATFORM_LABEL = dict(PLATFORMS)

# Verified profile links only. Facebook is left out on purpose: its page URL was never
# confirmed, and a wrong link is worse than no button. Add it as one more tuple once the
# exact URL is verified.
SOCIAL = [("\u25b6\ufe0f YouTube", "https://www.youtube.com/@rahalofficialmusic"),
          ("\U0001f4f8 Instagram", "https://www.instagram.com/rahal.official.music/"),
          ("\U0001f3b5 TikTok", "https://www.tiktok.com/@rahalofficialmusic"),
          ("\U0001f4e3 Telegram channel", "https://t.me/rahal_music")]

COMMANDS = [("track", "make a track (guided builder)"),
            ("queue", "what is rendering and what is waiting"),
            ("status", "engine and session status"),
            ("library", "latest releases"),
            ("publish", "publish the last track"),
            ("social", "links to the profiles"),
            ("get", "send a track's audio, cover and video"),
            ("routenote", "RouteNote form text for a track"),
            ("batch", "send several tracks as JSON"),
            ("jobs", "import jobs saved by the Windows app"),
            ("diag", "build version and update counts"),
            ("help", "all commands")]

HELP = """Zi Music Studio bot - make tracks from chat.
/track - guided builder: pick a style, write your own prompt, or let it write one from your idea
/track <spec> - one-shot, e.g.: /track melodic techno, night drive, 330s, instrumental, high
/batch - send several tracks as JSON (list of specs), or paste after the command
/queue - what's rendering and what's waiting
/status - engine and session status
/library - latest releases (buttons to fetch)
/get <title> - send a track's MP3 + cover + info
/routenote <title> - send the RouteNote form text for a track
/publish [title] - post the last track (or the named one) to YouTube, Instagram, TikTok, the Telegram channel, Facebook
/social - links to the YouTube, Instagram, TikTok and Telegram channel profiles
/jobs - import jobs saved by the Windows app (Drive zi_data/jobs)
/diag - build version and update counts (for debugging)
/cancel - cancel the current builder step
/help - this message
Every track is AI-generated and delivered with that label."""


class SpecDict(dict):
    """Spec passed to the engine. A missing key returns a sensible default and is
    recorded, so an engine build that reads an unexpected key neither crashes the
    render nor hides what it wanted."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.missing = []

    def __missing__(self, key):
        try:
            self.missing.append(key)
            print(f"engine asked for a spec key the bot did not send: {key!r}")
        except Exception:
            pass
        k = str(key).lower()
        if "dur" in k or "sec" in k:
            return self.get("seconds", 330)
        if k in ("bpm",):
            return 122
        if k in ("lang", "vocal_language"):
            return self.get("lang", "en")
        if "lyric" in k:
            return ""
        if "prompt" in k or "idea" in k or "style" in k:
            return self.get("idea", "")
        if "title" in k or "name" in k:
            return self.get("name") or self.get("genre") or "track"
        return None


class TG:
    def __init__(self, token):
        self.token = token
        self.thread_of = None      # callable(chat_id) -> message_thread_id or None
        self.log = []              # last sends: (time, text, ok|error)

    def call(self, method, **fields):
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode({k: v for k, v in fields.items() if v is not None}).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read())
        if not out.get("ok"):
            raise RuntimeError(f"telegram {method} failed: {out.get('description')}")
        return out["result"]

    def _note(self, what, ok, err=None):
        try:
            self.log.append((time.strftime("%H:%M:%S"), (what or "")[:60],
                             "ok" if ok else ("ERR " + str(err)[:90])))
            del self.log[:-20]
        except Exception:
            pass

    def _thread(self, chat_id):
        try:
            return self.thread_of(chat_id) if self.thread_of else None
        except Exception:
            return None

    def send(self, chat_id, text, keyboard=None):
        fields = {"chat_id": chat_id, "text": text[:4000], "message_thread_id": self._thread(chat_id)}
        if keyboard:
            fields["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
        try:
            r = self.call("sendMessage", **fields)
            self._note(text, True)
            return r
        except Exception as e:
            self._note(text, False, e)
            msg = str(e).lower()
            if fields.get("message_thread_id") and ("thread" in msg or "topic" in msg):
                # the topic is gone or the bot cannot post there: say it in the chat itself
                fields.pop("message_thread_id", None)
                try:
                    r = self.call("sendMessage", **fields)
                    self._note("(no thread) " + text, True)
                    return r
                except Exception as e2:
                    self._note("(no thread) " + text, False, e2)
            raise

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
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                out = json.loads(r.read())
            if not out.get("ok"):
                raise RuntimeError(f"telegram {method} failed: {out.get('description')}")
            self._note(method + " " + name, True)
            return out["result"]
        except Exception as e:
            self._note(method + " " + name, False, e)
            raise

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
        self._register_commands()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._poll, daemon=True).start()

    def _poll(self):
        import builtins
        lock = getattr(builtins, "_zi_bot_poll_lock", None)
        if lock is None:
            lock = threading.Lock()
            builtins._zi_bot_poll_lock = lock
        if not lock.acquire(blocking=False):
            print("Another bot instance is already polling in this process; this one will not poll.")
            return
        try:
            self._poll_loop()
        finally:
            try:
                lock.release()
            except Exception:
                pass

    def _poll_loop(self):
        while not self.stop.is_set():
            try:
                ups = self.tg.call("getUpdates", offset=self.state["offset"] + 1, timeout=10,
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

    @staticmethod
    def _is_engine_process(pid):
        """True for the ACE-Step API server, which keeps the model on the GPU all the time."""
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore").lower()
        except Exception:
            return False
        return ("acestep" in cmd) or ("ace-step" in cmd) or ("ace_step" in cmd)

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
                if parts[0] == me or self._is_engine_process(parts[0]):
                    continue
                if mb > GPU_PROC_MB:
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
                tb = traceback.format_exc()
                print("render failed:\n" + tb)
                try:
                    with open(os.path.join(self.out_root, "render_errors.log"), "a") as fh:
                        fh.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {self.current}\n{tb}")
                except Exception:
                    pass
                last = tb.strip().splitlines()[-1] if tb.strip() else ""
                self.tg.send(chat_id, f"That track failed: {type(e).__name__}: {str(e)[:200]}\n"
                                      f"Last line: {last[:200]}\n"
                                      "Full traceback is in the notebook console and in render_errors.log.")
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
        try:
            vid = self._make_video(folder)
            if vid and os.path.getsize(vid) < TG_LIMIT:
                self.tg._upload("sendVideo", chat_id, "video", vid, caption=title)
        except Exception as e:
            print("video step failed:", repr(e))
        self.tg.send(chat_id, "Saved in Drive: " + os.path.basename(folder) + " (WAV/FLAC/MP3, cover, lyrics, metadata, RouteNote form).")
        try:
            self._publish_menu(chat_id, folder, title)
        except Exception as e:
            print("publish menu failed:", repr(e))

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
            if chat_id is None:
                # some updates omit the message; in a private chat the sender id is the
                # chat id, so fall back to it instead of dropping the tap
                chat_id = (cb.get("from") or {}).get("id")
            try:
                self.stats["last_cb_raw"] = json.dumps(cb, ensure_ascii=False)[:700]
            except Exception:
                pass
            try:
                self.tg._note(f"cb chat={chat_id} thread={cmsg.get('message_thread_id')} owner={self._is_owner(chat_id)} has_msg={bool(cmsg)}", True)
            except Exception:
                pass
            if chat_id is None or not self._is_owner(chat_id):
                print("callback rejected:", "no chat id" if chat_id is None else f"not owner ({chat_id} != {self.owner})")
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
                traceback.print_exc()
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
            self.tg.send(chat_id, HELP, keyboard=[[{"text": "\U0001f310 Social links", "callback_data": "social"}]])
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
        elif cmd == "/publish":
            self._publish_cmd(chat_id, arg.strip())
        elif cmd == "/social":
            self._social(chat_id)
        elif cmd == "/diag":
            self._diag(chat_id)
        elif cmd == "/jobs":
            self._jobs(chat_id)
        else:
            self.tg.send(chat_id, "Unknown command. /help lists them.")

    def _callback(self, chat_id, data):
        b = self.builders.get(chat_id)
        if data == "social":
            self._social(chat_id)
            return
        if data.startswith("ov:"):
            if not b:
                self.tg.send(chat_id, "That builder expired. /track starts a new one.")
                return
            _, key, val = data.split(":")
            try:
                b["spec"][key] = int(val)
            except Exception:
                pass
            self._show_options(chat_id, b)
            return
        if data.startswith("o:"):
            if not b:
                self.tg.send(chat_id, "That builder expired. /track starts a new one.")
                return
            self._option_step(chat_id, b, data[2:])
            return
        if data.startswith("p:"):
            if not b:
                self.tg.send(chat_id, "That builder expired. /track starts a new one.")
                return
            self._prompt_step(chat_id, b, data[2:])
            return
        if data.startswith("pub:"):
            # a publish tap is an approval for that one post, so it must never
            # depend on a builder still being alive
            self._publish_cb(chat_id, data)
            return
        if data.startswith("lib:"):
            folder = self._lib_folder(data[4:])
            if not folder:
                self.tg.send(chat_id, "That release is not in this session's folder any more. /library lists the current ones.")
                return
            self._get(chat_id, folder, audio=True)
            return
        if data in GENRE_PRESETS:
            # Tapping a style always starts (or restarts) the builder, whatever step it was
            # on, or whether it was lost with a restarted kernel.
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
            if b.pop("skip_vocals", False):
                b["step"] = "quality"
                self.tg.send(chat_id, "Quality?", keyboard=[[{"text": label, "callback_data": "q:" + q}] for q, label in QUALITIES])
                return
            if b.get("built") and b["spec"].get("idea") == b["built"].get("prompt"):
                # the generated prompt carries a structure map, so rebuild it for the
                # length he just picked instead of rendering 7 minutes off a 5:30 map
                b["built"] = build_prompt(b["idea_seed"], int(data), b.get("variant", 0))
                b["spec"]["idea"] = b["built"]["prompt"]
            b["step"] = "instrumental"
            self.tg.send(chat_id, "Vocals?", keyboard=[[{"text": "Instrumental", "callback_data": "v:1"}, {"text": "With lyrics", "callback_data": "v:0"}]])
        elif step == "instrumental" and data.startswith("v:"):
            b["spec"]["instrumental"] = data == "v:1"
            b["step"] = "quality"
            self.tg.send(chat_id, "Quality?", keyboard=[[{"text": label, "callback_data": "q:" + q}] for q, label in QUALITIES])
        elif step == "quality" and data.startswith("q:"):
            b["spec"]["quality"] = data[2:]
            self._confirm(chat_id, b)
        elif step == "options" and data == "go":
            self._confirm(chat_id, b)
        elif step == "confirm":
            spec = b["spec"]
            self.builders.pop(chat_id, None)
            if data == "go":
                self._enqueue(chat_id, spec)
            else:
                self.tg.send(chat_id, "Cancelled.")
        else:
            hint = {"theme": "Type the theme or mood as a message, or tap a style to start over.",
                    "mode": "Tap a style, My own prompt, or AI writes it - or /cancel.",
                    "own_prompt": "Send the prompt as one message, or /cancel.",
                    "edit_prompt": "Send your version of the prompt, or /cancel.",
                    "ai_idea": "Send a short idea: genre, mood, vibe. No artist names.",
                    "options": "Tap a button above, or Generate when it reads right.",
                    "seconds": "Pick a length from the buttons above.",
                    "instrumental": "Pick Instrumental or With lyrics above.",
                    "quality": "Pick a quality from the buttons above."}.get(step, "/track starts a new one.")
            self.tg.send(chat_id, hint)

    def _options_kb(self, spec):
        seed = spec.get("seed")
        seed_txt = "random" if seed in (None, "") else str(seed)
        return [
            [{"text": ("Instrumental: on" if spec.get("instrumental") else "Instrumental: off"), "callback_data": "o:instr"},
             {"text": ("Lyrics" + (" (set)" if (spec.get("lyrics") or "").strip() else "")), "callback_data": "o:lyrics"}],
            [{"text": "Style tags", "callback_data": "o:tags"}, {"text": "Exclude styles", "callback_data": "o:excl"}],
            [{"text": f"Weirdness {spec.get('weirdness', 50)}", "callback_data": "o:weird"},
             {"text": f"Style influence {spec.get('style_influence', 50)}", "callback_data": "o:infl"}],
            [{"text": f"BPM {spec.get('bpm') or '-'}", "callback_data": "o:bpm"},
             {"text": f"Key {spec.get('key') or '-'}", "callback_data": "o:key"}],
            [{"text": f"Title {spec.get('title') or '-'}", "callback_data": "o:title"},
             {"text": f"Steps {spec.get('steps') or 'auto'}", "callback_data": "o:steps"}],
            [{"text": f"Seed {seed_txt}", "callback_data": "o:seed"},
             {"text": f"Model {spec.get('model') or 'turbo'}", "callback_data": "o:model"}],
            [{"text": "Reference audio (coming)", "callback_data": "o:coming:reference_audio"},
             {"text": "LoRA (coming)", "callback_data": "o:coming:lora"}],
            [{"text": "Cover / repaint (coming)", "callback_data": "o:coming:cover"}],
            [{"text": f"Length {spec.get('seconds', 330)}s", "callback_data": "o:sec"},
             {"text": "\u25b6\ufe0f Generate", "callback_data": "go"}],
        ]

    def _show_options(self, chat_id, b):
        b["step"] = "options"
        s = b["spec"]
        prompt = (s.get("idea") or "").strip()
        self.tg.send(chat_id,
                     "Options. Everything here is a button; tap Generate when it reads right.\n\n"
                     f"Prompt: {prompt[:240]}{'...' if len(prompt) > 240 else ''}",
                     keyboard=self._options_kb(s))

    def _option_step(self, chat_id, b, code):
        spec = b["spec"]
        if code.startswith("coming:"):
            key = code.split(":", 1)[1]
            note = next((o.get("note", "") for o in OPTIONS if o["key"] == key), "")
            self.tg.send(chat_id, f"That one is not wired yet: {note}")
            return
        if code == "instr":
            spec["instrumental"] = not spec.get("instrumental", True)
            if spec["instrumental"]:
                spec.pop("lyrics", None)
            self._show_options(chat_id, b)
        elif code in ("weird", "infl"):
            key = "weirdness" if code == "weird" else "style_influence"
            cur = spec.get(key, 50)
            vals = [0, 30, 50, 70, 100]
            self.tg.send(chat_id, f"{key.replace('_', ' ').title()} now {cur} (0-100):",
                         keyboard=[[{"text": str(v), "callback_data": f"ov:{key}:{v}"} for v in vals]])
        elif code == "model":
            order = ["turbo", "turbo-shift3"]
            cur = spec.get("model") or "turbo"
            spec["model"] = order[(order.index(cur) + 1) % len(order)] if cur in order else "turbo"
            self._show_options(chat_id, b)
        elif code == "sec":
            b["step"] = "seconds"
            b["skip_vocals"] = True   # instrumental/lyrics are already set on this screen
            self.tg.send(chat_id, "Length?", keyboard=self._length_kb())
        else:
            asks = {"lyrics": "Send the lyrics, with [Intro]/[Verse]/[Chorus] tags. One message.",
                    "tags": "Send short style tags, e.g. 'analog, tape hiss, 90s'.",
                    "excl": "What should it avoid? Written into the prompt as avoid phrasing.",
                    "title": "Send the title.",
                    "key": "Send the key, e.g. F# minor.",
                    "bpm": "Send the BPM (60-180).",
                    "steps": "Send the diffusion steps (4-60).",
                    "seed": "Send a seed number, or 0 for random."}
            if code in asks:
                b["step"] = "opt:" + code
                self.tg.send(chat_id, asks[code])
            else:
                self._show_options(chat_id, b)

    def _length_kb(self):
        return [[{"text": f"{d//60}:{d%60:02d}", "callback_data": str(d)} for d in DURATIONS[:4]],
                [{"text": f"{d//60}:{d%60:02d}", "callback_data": str(d)} for d in DURATIONS[4:]]]

    def _prompt_step(self, chat_id, b, code):
        if code == "own":
            b["step"] = "own_prompt"
            self.tg.send(chat_id, "Send the prompt as one message. Anything the engine needs goes in it: "
                                  "BPM, key, sound, structure. A reference to a real artist or track gets removed.")
        elif code == "ai":
            b["step"] = "ai_idea"
            self.tg.send(chat_id, "Give me the idea in a few words: genre, mood, anything it should feel like. "
                                  "No artist or track names - I build the full prompt from the library rules.")
        elif code == "again" and b.get("idea_seed") is not None:
            b["variant"] = b.get("variant", 0) + 1
            b["built"] = build_prompt(b["idea_seed"], b["spec"].get("seconds", 330), b["variant"])
            self._show_prompt(chat_id, b)
        elif code == "edit":
            b["step"] = "edit_prompt"
            self.tg.send(chat_id, "Send your version of the prompt as one message.")
        elif code == "use" and b.get("built"):
            built = b["built"]
            spec = b["spec"]
            spec["idea"] = built["prompt"]
            spec["bpm"] = built["bpm"]
            spec["key"] = built["key"]
            spec["genre"] = built["genre"]
            spec["name"] = built["genre"]
            self._show_options(chat_id, b)
        else:
            self.tg.send(chat_id, "Tap My own prompt or AI writes it, or /cancel.")

    def _show_prompt(self, chat_id, b):
        built = b["built"]
        b["step"] = "ai_review"
        note = ""
        if built.get("removed"):
            note = "\n\nRemoved a reference to a real artist or track: " + "; ".join(built["removed"][:3])
        self.tg.send(chat_id, f"Prompt ({built['bpm']} BPM, {built['key']}, {built['genre']}):\n\n"
                              f"{built['prompt']}{note}",
                     keyboard=[[{"text": "\u2705 Use it", "callback_data": "p:use"},
                                {"text": "\u270f\ufe0f Edit", "callback_data": "p:edit"}],
                               [{"text": "\U0001f504 Another", "callback_data": "p:again"}]])

    def _builder_text(self, chat_id, text):
        b = self.builders[chat_id]
        if b["step"] == "theme":
            b["spec"]["idea"] = b["spec"]["idea"] + text
            b["step"] = "seconds"
            self.tg.send(chat_id, "Length?", keyboard=self._length_kb())
        elif b["step"] in ("own_prompt", "edit_prompt"):
            clean, removed = clean_idea(text)
            if len(clean) < 8:
                self.tg.send(chat_id, "That is too short to render from. Send the full prompt again, or /cancel.")
                return
            spec = b["spec"]
            spec["idea"] = clean
            meta = build_prompt(clean, spec.get("seconds", 330))
            spec["bpm"], spec["key"] = meta["bpm"], meta["key"]
            spec.setdefault("genre", meta["genre"])
            spec.setdefault("name", meta["genre"])
            if removed:
                self.tg.send(chat_id, "Removed a reference to a real artist or track: " + "; ".join(removed[:3]))
            self._show_options(chat_id, b)
        elif b["step"].startswith("opt:"):
            key = b["step"].split(":", 1)[1]
            key = {"excl": "exclude", "tags": "style_tags"}.get(key, key)
            spec = b["spec"]
            raw = (text or "").strip()
            if key in ("bpm", "steps", "seed"):
                if not raw.isdigit():
                    self.tg.send(chat_id, "Send a number, or /cancel.")
                    return
                spec[key] = int(raw) if not (key == "seed" and raw == "0") else None
            else:
                spec[key] = raw
            self._show_options(chat_id, b)
        elif b["step"] == "ai_idea":
            b["idea_seed"] = text
            b["variant"] = 0
            b["built"] = build_prompt(text, b["spec"].get("seconds", 330), 0)
            self._show_prompt(chat_id, b)

    def _confirm(self, chat_id, b):
        b["step"] = "confirm"
        s = b["spec"]
        prompt = s.get("idea") or ""
        tail = f"\n\nPrompt: {prompt[:300]}{'...' if len(prompt) > 300 else ''}" if prompt else ""
        self.tg.send(chat_id,
            f"Ready: {s.get('genre')} | {s.get('seconds')}s | {'instrumental' if s.get('instrumental') else 'lyrics'} | {s.get('quality', 'standard')}"
            + (f" | title: {s['title']}" if s.get("title") else "") + tail,
            keyboard=[[{"text": "Generate", "callback_data": "go"}, {"text": "Cancel", "callback_data": "no"}]])

    def _track(self, chat_id, arg):
        if arg:
            spec = self._parse_spec(arg)
            if spec:
                self._enqueue(chat_id, spec)
                return
        self.builders[chat_id] = {"step": "mode", "spec": {"lang": "en", "quality": "high",
                                                           "instrumental": True, "seconds": 330}}
        genres = list(GENRE_PRESETS)
        kb = [[{"text": "\u270d\ufe0f My own prompt", "callback_data": "p:own"},
               {"text": "\u2728 AI writes it", "callback_data": "p:ai"}]]
        kb += [[{"text": g, "callback_data": g}] for g in genres]
        self.tg.send(chat_id, "New track. Pick a style, write the prompt yourself, "
                              "or let me write it from a short idea.", keyboard=kb)

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

    def _normalize_spec(self, spec):
        """Fill the keys the engine reads, including the length under every name it may use."""
        if not isinstance(spec, dict):
            return spec
        raw = None
        for k in LENGTH_KEYS:
            if spec.get(k) not in (None, ""):
                raw = spec[k]
                break
        try:
            secs = int(float(raw))
        except Exception:
            secs = 330
        secs = max(60, min(600, secs))
        for k in LENGTH_KEYS:
            spec[k] = secs
        genre = spec.get("genre") or spec.get("name") or "melodic techno"
        spec["genre"] = genre
        spec["name"] = spec.get("name") or spec.get("title") or genre
        spec["idea"] = spec.get("idea") or genre
        spec["lang"] = spec.get("lang") or "en"
        spec["instrumental"] = bool(spec.get("instrumental", True))
        q = str(spec.get("quality") or "standard").lower()
        spec["quality"] = q if q in ("fast", "standard", "high") else "standard"
        # the shared option model turns the choices into what the engine reads: the
        # text-level controls go into the prompt, style influence into guidance_scale,
        # lyrics and seed into their payload fields
        try:
            merged = opt.normalize(spec)
            merged.update({k: v for k, v in spec.items() if v not in (None, "")})
            spec = merged
        except Exception as e:
            print("options normalize skipped:", repr(e))
        if not isinstance(spec, SpecDict):
            spec = SpecDict(spec)
        return spec

    def _enqueue(self, chat_id, spec):
        if not self.make_track:
            self.tg.send(chat_id, "No engine in this session. Run the notebook's engine cell first.")
            return
        spec = self._normalize_spec(spec)
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
            s = self._normalize_spec(s)
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
        try:
            raw = self.stats.get("last_cb_raw")
            if raw:
                lines.append("last callback: " + raw[:400])
        except Exception:
            pass
        try:
            for t, what, ok in self.tg.log[-4:]:
                lines.append(f"send {t} {ok}: {what}")
        except Exception:
            pass
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

    # ---------- publishing ----------
    def _run_ffmpeg(self, args, timeout=1800):
        subprocess.run(args, check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    @staticmethod
    def _video_filter(w, h):
        # the cover art stays whole and centred, with a blurred copy filling the frame,
        # so a square 3000x3000 cover survives both 9:16 and 16:9 without cropping text
        return (f"[0:v]split=2[v1][v2];"
                f"[v1]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=40:5[bg];"
                f"[v2]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[out]")

    def _make_video(self, folder, kind="9x16"):
        """Visual for a track: the cover art with the mastered audio under it.

        A still frame compresses to almost nothing, so a 5-minute track stays far
        below Telegram's upload limit. Returns the path, or None when there is
        nothing to build from or ffmpeg is unavailable.
        """
        w, h = (720, 1280) if kind == "9x16" else (1280, 720)
        want = "_reel_9x16.mp4" if kind == "9x16" else "_youtube_16x9.mp4"
        if kind == "9x16":
            existing = self._release_video(folder)
            if existing and existing.endswith(want):
                return existing
        audio = self._release_audio(folder)
        cover = os.path.join(folder, "cover_3000x3000.jpg")
        if not audio or not os.path.exists(cover):
            return None
        stem = os.path.basename(audio)
        for suffix in ("_320kbps.mp3", "_preview_128k.mp3"):
            if stem.endswith(suffix):
                stem = stem[:-len(suffix)]
        out = os.path.join(folder, stem + want)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
        args = ["ffmpeg", "-y", "-loglevel", "error",
                "-loop", "1", "-i", cover, "-i", audio,
                "-filter_complex", self._video_filter(w, h),
                "-map", "[out]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "30",
                "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
        try:
            self._run_ffmpeg(args)
        except Exception as e:
            print("video render failed:", repr(e))
            return None
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
        return None

    # ---------- YouTube (Data API, needs the OAuth client) ----------
    def _yt_token(self):
        """The OAuth client + refresh token, once the Google Cloud task leaves them here."""
        for p in (os.path.join(self.out_root, "youtube_token.json"),
                  os.path.join(os.path.dirname(self.out_root.rstrip("/")), "zi_data", "youtube_token.json")):
            if os.path.exists(p):
                try:
                    with open(p) as fh:
                        tok = json.load(fh)
                    if tok.get("client_id") and tok.get("client_secret") and tok.get("refresh_token"):
                        return tok
                except Exception as e:
                    print("youtube_token.json unreadable:", repr(e))
        return None

    def _yt_access_token(self, tok):
        data = urllib.parse.urlencode({"client_id": tok["client_id"], "client_secret": tok["client_secret"],
                                       "refresh_token": tok["refresh_token"],
                                       "grant_type": "refresh_token"}).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["access_token"]

    def _youtube_upload(self, folder, title, caption):
        """Upload the 16:9 visual of a release to YouTube. Returns the watch URL."""
        tok = self._yt_token()
        if not tok:
            raise RuntimeError("no youtube_token.json yet (the Google Cloud OAuth client is still being set up)")
        video = self._make_video(folder, "16x9")
        if not video:
            raise RuntimeError("no video to upload (no cover or audio in the release folder)")
        access = self._yt_access_token(tok)
        body = {"snippet": {"title": title[:100],
                            "description": caption + "\n\nMade with ACE-Step 1.5 (MIT licence).",
                            "tags": PUBLISH_TAGS.replace("#", "").split(),
                            "categoryId": "10"},
                "status": {"privacyStatus": "public",
                           "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": True}}
        req = urllib.request.Request(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + access,
                     "Content-Type": "application/json; charset=UTF-8",
                     "X-Upload-Content-Type": "video/mp4",
                     "X-Upload-Content-Length": str(os.path.getsize(video))})
        with urllib.request.urlopen(req, timeout=120) as r:
            loc = r.headers.get("Location")
        if not loc:
            raise RuntimeError("YouTube returned no upload URL")
        with open(video, "rb") as fh:
            payload = fh.read()
        req2 = urllib.request.Request(loc, data=payload, method="PUT",
                                      headers={"Content-Type": "video/mp4",
                                               "Content-Length": str(len(payload))})
        with urllib.request.urlopen(req2, timeout=3600) as r:
            out = json.loads(r.read())
        if not out.get("id"):
            raise RuntimeError("YouTube upload returned no video id: " + json.dumps(out)[:200])
        return "https://youtu.be/" + out["id"]

    def _last_release(self):
        folders = self._release_folders()
        return os.path.join(self.out_root, folders[0]) if folders else None

    def _release_video(self, folder):
        """A video for this release if one was rendered, 9:16 first (reels/shorts)."""
        try:
            vids = [f for f in os.listdir(folder) if f.lower().endswith((".mp4", ".mov"))]
        except Exception:
            return None
        if not vids:
            return None
        return os.path.join(folder, sorted(vids, key=lambda n: (0 if "9x16" in n.lower() else
                                                               1 if "16x9" in n.lower() else 2, n))[0])

    def _release_audio(self, folder):
        try:
            names = os.listdir(folder)
        except Exception:
            return None
        for suffix in ("_320kbps.mp3", "_preview_128k.mp3"):
            for n in names:
                if n.endswith(suffix):
                    return os.path.join(folder, n)
        return None

    def _publish_caption(self, folder):
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        title = (meta.get("title") or re.sub(r"^\d{8}-\d{6}_", "",
                 os.path.basename(folder)).replace("_", " ")).strip()
        line = f"{title} - Rahal. {PUBLISH_AI}"
        return title, line, line + "\n\n" + PUBLISH_TAGS

    def _social(self, chat_id):
        kb = [[{"text": name, "url": url}] for name, url in SOCIAL]
        self.tg.send(chat_id, "Rahal everywhere:" if kb else
                     "No verified profile links yet.", keyboard=kb or None)

    def _register_commands(self):
        """Keep the Telegram command menu in step with the code."""
        try:
            self.tg.call("setMyCommands", commands=json.dumps(
                [{"command": c, "description": d} for c, d in COMMANDS]))
        except Exception as e:
            print("setMyCommands failed:", repr(e))

    def _publish_menu(self, chat_id, folder, title=None):
        key = self._lib_key(os.path.basename(folder))
        title = title or self._publish_caption(folder)[0]
        kb = [[{"text": PLATFORM_LABEL[c], "callback_data": f"pub:{c}:{key}"} for c in ("yt", "ig")],
              [{"text": PLATFORM_LABEL[c], "callback_data": f"pub:{c}:{key}"} for c in ("tt", "tg")],
              [{"text": "Facebook (manual)", "callback_data": f"pub:fb:{key}"},
               {"text": "All", "callback_data": f"pub:all:{key}"}]]
        self.tg.send(chat_id, f"Publish {title}?\n"
                              "A tap posts only the platform you tap, once.", keyboard=kb)

    def _publish_cmd(self, chat_id, arg):
        folder = self._find_folder(arg) if arg else self._last_release()
        if not folder:
            self.tg.send(chat_id, "Nothing found for that. /library lists releases." if arg
                         else "No release in this session's folder yet. /track makes one.")
            return
        self._publish_menu(chat_id, folder)

    def _publish_cb(self, chat_id, data):
        parts = data.split(":")
        code = parts[1] if len(parts) > 1 else ""
        key = parts[2] if len(parts) > 2 else ""
        name = self._lib_folder(key)
        folder = os.path.join(self.out_root, name) if name else None
        if not folder or not os.path.isdir(folder):
            self.tg.send(chat_id, "That release is not in this session's folder any more. /library lists the current ones.")
            return
        if code not in PLATFORM_LABEL and code != "all":
            self.tg.send(chat_id, "Unknown publish target. /publish reopens the menu.")
            return
        self._publish(chat_id, code, folder)

    def _publish(self, chat_id, code, folder):
        title, line, caption = self._publish_caption(folder)
        video = self._release_video(folder)
        audio = self._release_audio(folder)
        cover = os.path.join(folder, "cover_3000x3000.jpg")
        cover = cover if os.path.exists(cover) else None
        print(f"publish {code} {title} ({time.strftime('%H:%M:%S')})")

        def to_channel():
            if video and os.path.getsize(video) < TG_LIMIT:
                self.tg._upload("sendVideo", CHANNEL, "video", video, caption=caption)
                return "video"
            if not audio:
                raise RuntimeError("no audio or video file in the release folder")
            if cover:
                try:
                    self.tg.photo(CHANNEL, cover, caption=title)
                except Exception as e:
                    print("channel cover failed:", repr(e))
            self.tg.audio(CHANNEL, audio, caption=caption)
            return "audio + cover"

        def package(platform):
            req = {"platform": platform, "title": title, "caption": caption,
                   "ai_wording": PUBLISH_AI, "tags": PUBLISH_TAGS, "folder": folder,
                   "files": [p for p in (video, audio, cover) if p],
                   "approved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "approved_by": "owner tap in Telegram",
                   "status": "packaged - post by hand or by the posting agent"}
            path = os.path.join(folder, f"publish_request_{platform}.json")
            with open(path, "w") as fh:
                json.dump(req, fh, indent=2)
            return path

        targets = list(PLATFORM_LABEL) if code == "all" else [code]
        done, failed = [], []
        for p in targets:
            try:
                if p == "tg":
                    how = to_channel()
                    done.append(f"Telegram channel: posted ({how}) - https://t.me/rahal_music")
                elif p == "yt":
                    try:
                        url = self._youtube_upload(folder, title, caption)
                        done.append(f"YouTube: posted - {url}")
                    except Exception as e:
                        package("yt")
                        done.append("YouTube: not uploaded yet (" + f"{type(e).__name__}: {str(e)[:160]}" +
                                    "). The post package is in the release folder as publish_request_yt.json, "
                                    "and this button uploads for real once the OAuth client is in place.")
                elif p == "fb":
                    done.append("Facebook: caption below, file ready. Posting stays manual by your call.")
                else:
                    package(p)
                    done.append(f"{PLATFORM_LABEL[p]}: no posting API on our side, so I wrote the post "
                                f"package (caption + files) into the release folder as publish_request_{p}.json "
                                "for a one-pass manual post.")
            except Exception as e:
                failed.append(f"{PLATFORM_LABEL.get(p, p)} failed: {type(e).__name__}: {str(e)[:200]}")
        msg = ["\n".join(done)] if done else []
        if failed:
            msg.append("\n".join(failed))
        if "fb" in targets:
            msg.append("Facebook caption:\n" + caption)
        self.tg.send(chat_id, "\n\n".join(msg) or "Nothing to publish.")

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
            j = self._normalize_spec(j)
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
    # Stop every poller in this process and wait for them to exit before the new one
    # starts: two pollers fight over getUpdates (409) and taps land on the old one.
    stale = stop_other_bots(keep=None)
    still = _bot_instances()
    print(f"Stopped {stale} previous poller(s); {len(still)} still alive before start.")
    if still:
        print("WARNING: a previous poller did not stop. Restart the kernel if callbacks stop arriving.")
    bot = Bot(token, out_root=out_root, work=work, make_track=make_track, run_queue=run_queue)
    bot.start()
    builtins._zi_bot_instance = bot
    print(f"Zi Telegram bot running (build {VERSION}). Chat with the bot in Telegram; /help lists commands.")
    try:
        print(f"Pollers in this process after start: {len(_bot_instances())} (1 is healthy)")
    except Exception:
        pass
    return bot
