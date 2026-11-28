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

import hashlib, json, os, queue, random, re, shutil, subprocess, threading, time, traceback, urllib.error, urllib.request, urllib.parse, uuid

VERSION = "2026-11-28.50"
OWNER_ID_DEFAULT = 7835590874      # Rahal's Telegram id, used only when no owner file exists
_WHISPER = None   # the CPU speech model, loaded the first time a voice note arrives

API = "https://api.telegram.org/bot{token}/{method}"
FILE_API = "https://api.telegram.org/file/bot{token}/{path}"
TG_LIMIT = 49 * 1024 * 1024  # bot upload practical limit
STUDIO_URL = "https://ira7al.github.io/zi/"   # the Studio web app (works on a phone)

# GPU sharing guard: the bot renders in the same kernel as the notebook's own
# renders (Infra's FL queue), so a bot job must wait for the GPU to be free.
GPU_UTIL_LIMIT = 25        # percent; above this something is rendering
GPU_PROC_MB = 2000         # another process holding more than this is rendering
GPU_POLL_SEC = 30

GENRE_PRESETS = {
 "Melodic Techno": "120-124 bpm melodic techno, tight punchy kick, deep sub bass, emotional minor chord progression on a soft pluck, lush atmospheric pads, hypnotic arpeggio, distant reverb بصوت chops, long DJ-friendly intro and outro, bittersweet 4am mood",
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

try:
    import zi_assistant as ziassist
except Exception:  # loaded by path from the notebook
    import importlib.util as _ilu2
    _as_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zi_assistant.py")
    _as_spec = _ilu2.spec_from_file_location("zi_assistant", _as_path)
    ziassist = _ilu2.module_from_spec(_as_spec)
    _as_spec.loader.exec_module(ziassist)

try:
    import zi_voice as voice
except Exception:  # loaded by path from the notebook
    import importlib.util as _ilu3
    _vo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zi_voice.py")
    _vo_spec = _ilu3.spec_from_file_location("zi_voice", _vo_path)
    voice = _ilu3.module_from_spec(_vo_spec)
    _vo_spec.loader.exec_module(voice)

try:
    import zi_art as art
except Exception:  # loaded by path from the notebook
    import importlib.util as _ilu4
    _ar_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zi_art.py")
    _ar_spec = _ilu4.spec_from_file_location("zi_art", _ar_path)
    art = _ilu4.module_from_spec(_ar_spec)
    _ar_spec.loader.exec_module(art)

build_prompt = opt.build_prompt
clean_idea = opt.clean_idea
has_non_latin = opt.has_non_latin
_structure = opt.structure
OPTIONS = opt.OPTIONS

# Keys the notebook's make_track reads. Different engine builds have used different
# names for the length, so the bot fills all of them with the same value.
REQUIRED_SPEC_KEYS = ("name", "genre", "idea", "lang", "instrumental", "seconds", "quality")
LENGTH_KEYS = ("seconds", "duration", "duration_sec", "target_sec")
# ---------- button labels are English; every message stays Egyptian Arabic ----------
BUTTON_EN = {
    "إيه الناقص؟": "\u2753 What's Missing", "أعمل إيه بعد كده؟": "\u27a1\ufe0f What's Next",
    "الحالة": "\U0001f4ca Status", "اعمل تراك": "\U0001f3b5 New Track", "تراك تاني": "\U0001f3b5 Another Track",
    "ترك جديد": "\U0001f3b5 New Track", "تراك جديد": "\U0001f3b5 New Track",
    "المكتبة": "\U0001f4da Library", "بروموبت من عندي": "\u270d\ufe0f Prompt + Reference",
    "برومبت من عندي": "\u270d\ufe0f Prompt + Reference", "الذكاء يكتبه": "\u2728 AI Writes It",
    "لينكات السوشيال": "\U0001f310 Social Links", "الدرغام": "\U0001f9ec Dorgham",
    "الدرغام: شغال \u2705": "\U0001f9ec Dorgham: On \u2705", "استخدم الدرغام": "\U0001f9ec Use Dorgham",
    "فورم RouteNote": "\U0001f9fe RouteNote Form", "حاجات تانية": "\u2699\ufe0f More",
    "الستوديو (الويب)": "\U0001f39b Studio", "ولّد": "\u25b6\ufe0f Generate", "اسألني": "\U0001f916 Ask Me",
    "إلغاء": "\u274c Cancel", "ارفع تراك/MP3 كمرجع": "\U0001f3a7 Upload Reference",
    "استخدمه كمرجع": "\U0001f50e Use as Reference", "استخدمه": "\u2705 Use It", "عدّل": "\u270f\ufe0f Edit",
    "واحد تاني": "\U0001f504 Another One", "مرجع جديد": "\U0001f50e New Reference",
    "أرت ورك للتراك": "\U0001f3a8 Cover Art", "غيّر الأرت ورك": "\U0001f3a8 Change Art", "أرت وورك للتراك": "\U0001f3a8 Cover Art", "أرتورك": "\U0001f3a8 Cover Art",
    "غيّر الأرت وورك": "\U0001f3a8 Change Art", "فيديو يوتيوب": "\U0001f3ac Video", "فيديو YouTube": "\U0001f3ac Video",
    "انشر": "\U0001f4e3 Publish", "ارفع على يوتيوب": "\u25b6\ufe0f Upload to YouTube",
    "أشكال تانية": "\U0001f504 More Options", "فيسبوك (يدوي)": "\U0001f4d8 Facebook (Manual)",
    "فيسبوك (هتتضاف)": "\U0001f4d8 Facebook (Soon)", "صفحة فيسبوك (هتتضاف)": "\U0001f4d8 Facebook Page (Soon)",
    "الكل": "\U0001f680 All", "دي التراك المطلوب": "\u2b50 Mark as The One",
    "ده التراك المطلوب": "\u2b50 Mark as The One", "القائمة": "\u2630 Menu",
    "ولّد تاني بالتعديل": "\u25b6\ufe0f Regenerate", "عدّل وولّد تاني": "\U0001f39b Tweak & Regenerate",
    "بصوت": "\U0001f3a4 With Vocals", "بكلمات": "\U0001f3a4 With Lyrics", "موسيقى بس": "\U0001f3b9 Instrumental",
    "ضيف كلمات": "\u270d\ufe0f Add Lyrics", "تخطّى": "Skip", "ستايل مرجع": "\U0001f50e Style Reference",
    "سيبها": "\u274c Drop It", "ريميكس/كفر": "\u267b\ufe0f Remix / Cover", "ريماستر": "\U0001f39a Remaster",
    "أيوه، ارفع": "\u2705 Yes, Upload", "لأ": "\u274c No", "تشخيص": "\U0001f6e0 Diagnostics",
    "المساعد": "\U0001f916 Assistant", "مساعدة": "\u2753 Help", "قناة تيليجرام": "\U0001f4e3 Telegram Channel",
    "عالية (نسختين، تختار الأحسن)": "High (2 takes, pick the best)", "عادية": "Standard", "مسودة سريعة": "Fast Draft",
    "ولّد: قريب من الأصلي": "\u25b6\ufe0f Close to Original", "ولّد: وسط": "\u25b6\ufe0f Medium",
    "ولّد: بعيد عنه": "\u25b6\ufe0f Far From It",
}
_TWEAK_EN = {"الغرابة": "Weirdness", "تأثير الستايل": "Style Influence", "الطول": "Length", "السرعة (BPM)": "Speed"}
_LESSMORE_EN = {"أقل": "Less", "أكتر": "More", "أقصر": "Shorter", "أطول": "Longer", "أبطأ": "Slower", "أسرع": "Faster"}
_AR = re.compile("[\u0600-\u06ff]")


def en_button(text):
    """English label for a button. Text with no Arabic (names, numbers, links) is returned as is."""
    if not text or not _AR.search(text):
        return text
    i = 0
    while i < len(text) and not text[i].isalnum():
        i += 1
    core = text[i:].strip()
    if core in BUTTON_EN:
        return BUTTON_EN[core]
    for lab, en in _TWEAK_EN.items():
        if core.startswith(lab + " "):
            word = core[len(lab) + 1:]
            if word in _LESSMORE_EN:
                w = _LESSMORE_EN[word]
                return f"{w} {en}" if w in ("Less", "More") else f"{en} {w}"
    return text


def en_keyboard(keyboard):
    """The same inline keyboard with every button label in English."""
    out = []
    for row in keyboard or []:
        out.append([dict(b, text=en_button(b.get("text"))) if isinstance(b, dict) else b for b in row])
    return out


QUALITIES = [("high", "عالية (نسختين، تختار الأحسن)"), ("standard", "عادية"), ("fast", "مسودة سريعة")]
ASSIST_HINT = "\U0001f916 محتاج حاجة؟ اكتب سؤالك هنا في أي وقت، أو دوس اسألني."
VISION_HINT = ("مش قادر أقرا الصورة دلوقتي، القراءة مش مدّية نتيجة. "
               "ابعت اسم التراك أو المغني بالكلام، أو فويس نوت، وأنا أطلع الستايل من غير ما أستخدم الاسم.")
AI_LABEL = "AI-generated music (ACE-Step 1.5, MIT licence). Label it AI-generated wherever you release it."

# ---------- publishing ----------
# The bot token administers the channel (that is how its photo and description were
# set), so the channel is the one platform that posts end to end from here.
CHANNEL = "@rahal_music"

# ---------- training dataset intake ----------
# Files the owner sends to train the LoRA land here, original names kept, deduped by hash.
DATASET_SUBDIR = os.path.join("dataset", "mr-dorgham")
DS_MAX_BYTES = 20 * 1024 * 1024      # Bot API getFile cap
DS_AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus",
                ".aiff", ".aif", ".wma"}
MOOD_WORDS = ("dark", "warm", "dreamy", "melancholic", "euphoric", "uplifting", "calm", "energetic",
              "driving", "hypnotic", "emotional", "cinematic", "nostalgic", "late-night", "sunset",
              "ocean", "groovy", "deep", "atmospheric", "chill", "epic", "romantic", "mysterious")
AI_LABEL_YT = "AI-generated with ACE-Step under Rahal's direction and selection."
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
          ("\U0001f4e3 \u0642\u0646\u0627\u0629 \u062a\u064a\u0644\u064a\u062c\u0631\u0627\u0645", "https://t.me/rahal_music"),
          ("\u2601\ufe0f SoundCloud (\u0627\u0644\u0628\u0631\u0648\u0641\u0627\u064a\u0644 \u0628\u0633)", "https://soundcloud.com/rahal-835976183")]

# One command only. Telegram's corner button can only open this list, never send a
# message, so the shortest path is: corner -> Menu -> the inline menu in the chat.
# Everything else is inside that menu, and /help still lists every command by name.
COMMANDS = [("menu", "\u0643\u0644 \u0627\u0644\u0623\u0632\u0631\u0627\u0631 - Menu")]

HELP = """بوت Zi Music Studio - اعمل تراكات من الشات.
دوس Menu في الركن، وبعدين Menu: كل حاجة بتوصلك في الشات كأزرار، والاستوديو كمان.
/menu - كل حاجة كأزرار (ابدأ من هنا)
/ask - اسأل المساعد إيه الناقص أو أعمل إيه بعد كده؛ /ask لوحدها بتفتح شات
/end - اقفل شات المساعد
/track - بناء التراك خطوة خطوة: اختار ستايل، أو اكتب البرومبت بنفسك، أو سيب الذكاء يكتبه من فكرتك،
         أو ابعت مرجع (اسم، لينك، سكرين شوت، فويس نوت) وأنا أطلّع الستايل
/track <spec> - تراك في خطوة، مثلاً: /track melodic techno, night drive, 330s, instrumental, high
/batch - ابعت كذا تراك JSON (قايمة), أو الصقها بعد الأمر
/queue - إيه اللي بيتعمل وإيه المستني
/status - حالة الجلسة
/library - آخر التراكات (أزرار تجيبها)
/get <العنوان> - ابعتلي MP3 التراك + الغلاف + المعلومات
/routenote <العنوان> - ابعتلي نص فورم RouteNote للتراك
/publish [العنوان] - انشر آخر تراك (أو اللي تسميه) على YouTube وInstagram وTikTok وقناة تيليجرام وفيسبوك
/studio - لينك الاستوديو
/social - لينكات البروفايلات
/liked - التراكات اللي علّمتها مفضّلة (مجموعة LoRA)
/dataset - حالة مجموعة التدريب (الملفات اللي اتبعتت لموديل Mr Dorgham)
/jobs - مهام اتحفظت من تطبيق ويندوز (درايف zi_data/jobs)
/diag - إصدار البوت وعدّادات التحديثات (للتشخيص)
/cancel - إلغاء خطوة البناء الحالية
/help - الرسالة دي
الصوت: ابعت فويس نوت والمساعد بيرد بالصوت؛ فكرة موسيقى بالكلام بتبدأ تراك.
السكرين شوت: ابعت سكرين شوت تراك والستايل بيتقرا منه - الاسم مبيدخلش البرومبت أبداً.
كل تراك مولّد بالذكاء الاصطناعي وبيتسلّم بالتصنيف ده."""


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
        # a notebook network blip must not lose a message or a track: retry the
        # transient failures (timeout, connection reset, 429, 5xx) a few times
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode({k: v for k, v in fields.items() if v is not None}).encode()
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data)
                with urllib.request.urlopen(req, timeout=90) as r:
                    out = json.loads(r.read())
                if not out.get("ok"):
                    desc = str(out.get("description") or "")
                    wait = int((out.get("parameters") or {}).get("retry_after") or 3)
                    last = RuntimeError(f"telegram {method} failed: {desc}")
                    if out.get("error_code") == 429 or "retry after" in desc.lower():
                        if attempt < 2:
                            time.sleep(min(wait, 30))
                            continue
                    raise last
                return out["result"]
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", "ignore")[:300]
                except Exception:
                    pass
                last = RuntimeError(f"telegram {method} failed: HTTP {e.code} {body}")
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise last
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        raise last if last else RuntimeError(f"telegram {method} failed")

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

    def send(self, chat_id, text, keyboard=None, reply=None):
        fields = {"chat_id": chat_id, "text": text[:4000], "message_thread_id": self._thread(chat_id)}
        if keyboard:
            fields["reply_markup"] = json.dumps({"inline_keyboard": en_keyboard(keyboard)})
        elif reply:
            fields["reply_markup"] = json.dumps(reply)
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

    def voice(self, chat_id, path, caption=None):
        return self._upload("sendVoice", chat_id, "voice", path, caption)


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
        self.users_path = os.path.join(out_root, "zi_users.json")
        self.users = self._load(self.users_path, {})
        if not isinstance(self.users, dict):
            self.users = {}
        self.sync_hashes = {}
        self.sync_dirty = bool(self.users)
        self.sync_lock = threading.Lock()
        self.sync_status = "not run yet"
        self.sync_wake = threading.Event()
        self.pair_code = None
        if self.owner is None:
            # the owner is known by Telegram id, so a wiped device needs no pairing code again
            try:
                oid = int(self._secret("ZI_OWNER_ID") or OWNER_ID_DEFAULT)
                self.owner = oid
                self._save(self.owner_path, {"chat_id": oid})
            except Exception:
                pass
        self.jobs = queue.Queue()
        self.threads = {}    # chat_id -> message_thread_id (topic chats)
        self.gpu_marker = os.environ.get("ZI_GPU_MARKER") or os.path.join(out_root, ".gpu_busy")
        self.gpu_poll = GPU_POLL_SEC
        self.queued = []     # titles waiting behind the current render
        self.current = None
        self.builders = {}   # chat_id -> dict of the guided /track flow
        self.cur_msg = {}    # chat_id -> id of the message being answered
        self.reacted = {}    # (chat_id, message_id) -> emoji already set
        self.last_react = 0.0
        self.heard_raw = {}  # chat_id -> (what the voice note said, time)
        self.remix = {}      # chat_id -> {'key','idea'} while a remix is being set up
        self.tweak = {}      # chat_id -> the settings he is adjusting for a second try
        self.last_enq = {}   # chat_id -> the settings of the last track sent to render
        self.pending = {}    # chat_id -> an image or link waiting for his instruction
        self.last_say = {}   # chat_id -> his latest text or voice, so an image right after joins it
        self.stop = threading.Event()
        self.conflict_warned = False
        self.stats = {"message": 0, "callback": 0, "last": "nothing yet"}
        self.ds_lyrics = {}   # chat_id -> sha of the file whose lyrics we are waiting for
        self.ask_mode = set()  # chats talking to the assistant
        self._launcher_sent = False
        self._llm_ready = None
        self.llm_key = ""
        self.groq_key = ""
        self.llm_model = ""
        self.render_note_minutes = 5   # how often a long render says it is still alive
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

    REMOVE_KB = {"remove_keyboard": True}
    MENU_NOTE = ("\u0634\u0644\u062a \u0627\u0644\u0623\u0632\u0631\u0627\u0631 \u0627\u0644\u0644\u064a \u062a\u062d\u062a \u0627\u0644\u0645\u0643\u062a\u0648\u0628\u0629. "
                 "\u0636\u063a\u0637 Menu \u0641\u064a \u0627\u0644\u0631\u0643\u0646 \u0641\u0648\u0642\u060c \u0648\u0628\u0639\u062f\u064a\u0646 \u0627\u062e\u062a\u0627\u0631 Menu "
                 "\u0645\u0646 \u0627\u0644\u0644\u0633\u062a\u0629 - \u0643\u0644 \u0627\u0644\u0623\u0632\u0631\u0627\u0631 \u0647\u062a\u062c\u064a\u0644\u0643 \u062c\u0648\u0651\u0647 \u0627\u0644\u0634\u0627\u062a.")

    def _launcher(self, chat_id, text=None):
        """No reply keyboard any more: clear the one already on his device, then show the menu."""
        try:
            self.tg.send(chat_id, text or self.MENU_NOTE, reply=self.REMOVE_KB)
        except Exception as e:
            print("could not remove the keyboard:", type(e).__name__)
        self._menu(chat_id)

    def _is_owner(self, chat_id):
        return self.owner is not None and chat_id == self.owner

    # ---------- main loops ----------
    def start(self):
        self.ensure_pairing()
        self._register_commands()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._poll, daemon=True).start()
        threading.Thread(target=self._sync_loop, daemon=True).start()

    # ---------- private user records ----------
    SYNC_EVERY = 1800

    def _data_conf(self):
        return (self._secret("ZI_DATA_REPO") or "ira7al/zi-private-data"), self._secret("ZI_DATA_TOKEN")

    def _track_user(self, frm):
        """Remember whoever opens the bot. Returns True the first time this person is seen."""
        try:
            prof = opt.user_from_update(frm)
            if not prof:
                return False
            now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            with self.sync_lock:
                is_new, changed = opt.note_user(self.users, prof, now, self._is_owner(prof["telegram_id"]))
                if changed:
                    self.sync_dirty = True
                    self._save(self.users_path, self.users)
            if is_new:
                self.sync_wake.set()
            return is_new
        except Exception as e:
            print("user record failed:", type(e).__name__)
            return False

    PHONE_KB = {"keyboard": [[{"text": "\U0001f4f1 Share My Number", "request_contact": True}]],
                "resize_keyboard": True, "one_time_keyboard": True}

    def _contact_shared(self, chat_id, msg):
        now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        with self.sync_lock:
            ok, why = opt.accept_contact(self.users, msg.get("from"), msg.get("contact"), now)
            if ok:
                self.sync_dirty = True
                self._save(self.users_path, self.users)
        if ok:
            self.sync_wake.set()
            self.tg.send(chat_id, "تمام، رقمك اتأكد من تيليجرام وتسجّل.", reply=self.REMOVE_KB)
        elif why == "not own number":
            self.tg.send(chat_id, "ده مش رقمك إنت. دوس الزرار عشان تشارك رقمك أنت.", reply=self.PHONE_KB)
        else:
            self.tg.send(chat_id, "ما وصلنيش كويس، ممكن تعيدها؟")

    def _sync_files(self):
        files = {}
        with self.sync_lock:
            for uid, prof in self.users.items():
                files[f"users/{uid}.json"] = json.dumps(opt.clean_profile(prof), ensure_ascii=False, indent=2, sort_keys=True)
        if self.owner:
            liked = self._liked().get("tracks", {})
            tracks = []
            for d in self._release_folders():
                meta = self._load(os.path.join(self.out_root, d, "metadata.json"), {})
                entry = liked.get(self._lib_key(d)) or {}
                extra = {"id": self._lib_key(d), "starred": bool(entry.get("kept"))}
                tracks.append(opt.clean_track(meta, extra))
            files[f"library/{self.owner}.json"] = json.dumps(
                {"owner_telegram_id": self.owner, "count": len(tracks), "tracks": tracks},
                ensure_ascii=False, indent=2, sort_keys=True)
        return files

    def _sync_once(self, force=False):
        repo, token = self._data_conf()
        if not token:
            self.sync_status = "saved on this device only (no ZI_DATA_TOKEN)"
            return False
        if not (self.sync_dirty or force):
            return True
        self.sync_dirty = False
        pushed, problems = opt.sync_private(repo, token, self._sync_files(), self.sync_hashes)
        if problems:
            self.sync_dirty = True
            self.sync_status = "failed: " + "; ".join(problems)[:150]
            print("private sync problem:", self.sync_status)
            return False
        self.sync_status = time.strftime("ok %H:%M:%S") + f" ({len(pushed)} files)"
        return True

    def _sync_loop(self):
        while not self.stop.is_set():
            try:
                self._sync_once(force=not self.sync_hashes)
            except Exception as e:
                print("private sync crashed:", type(e).__name__)
            self.sync_wake.wait(self.SYNC_EVERY)
            self.sync_wake.clear()

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
                        traceback.print_exc()
                        try:
                            cid = (((u.get("message") or {}).get("chat") or {}).get("id")
                                   or ((u.get("callback_query") or {}).get("message", {}).get("chat") or {}).get("id"))
                            if cid and self.owner and cid == self.owner:
                                self.tg.send(cid, f"الرسالة دي عملت مشكلة: {type(e).__name__}: {str(e)[:160]}. "
                                                  "البوت شغال، ابعتها تاني أو /status.")
                        except Exception:
                            pass
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
                    return "في تراك تاني شغال على الجهاز"
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
                    return "في عملية تانية شغالة"
            util = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu",
                                   "--format=csv,noheader,nounits"],
                                  capture_output=True, text=True, timeout=15).stdout
            vals = [int(v) for v in util.replace("\n", " ").split() if v.strip().isdigit()]
            if vals and max(vals) > GPU_UTIL_LIMIT:
                return "الجهاز مشغول"
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
                    self.tg.send(chat_id, "الجهاز فاضي، بدأت التراك دلوقتي.")
                return True
            if why != told:
                self.tg.send(chat_id, f"مستني: {why}. التراك هيبدأ لوحده أول ما الجهاز يفضى، مش محتاج تبعت تاني.")
                told = why
            time.sleep(self.gpu_poll)
        return False

    def _worker(self):
        while not self.stop.is_set():
            try:
                job = self.jobs.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self._run_job(*job)
            except Exception as e:
                # a bad job must never take the worker down with it
                print("job crashed:\n" + traceback.format_exc())
                try:
                    self.tg.send(job[0], f"الشغلانة وقفت: {type(e).__name__}: {str(e)[:200]}\n"
                                          "البوت شغال - ابعت /track تاني.")
                except Exception:
                    pass
            finally:
                self.current = None
                try:
                    self.jobs.task_done()
                except Exception:
                    pass

    def _run_job(self, chat_id, spec):
        if spec.get("_thread"):
            self.threads[chat_id] = spec["_thread"]
        self.current = spec.get("title") or spec.get("name") or spec.get("genre") or "track"
        try:
            if self.queued:
                self.queued.pop(0)
        except Exception:
            pass
        if not self._wait_for_gpu(chat_id):
            return
        self.tg.send(chat_id, f"بيتعمل دلوقتي: {self.current} ({spec.get('seconds', 330)} ثانية، {spec.get('quality', 'standard')}). التراك عالي الجودة بياخد من ١٠ لـ ٢٥ دقيقة على الجهاز المجاني - هبعتهولك هنا أول ما يخلص.")
        self._mark_busy(True)
        try:
            r = self._render(chat_id, spec)
        except Exception as e:
            tb = traceback.format_exc()
            print("render failed:\n" + tb)
            try:
                with open(os.path.join(self.out_root, "render_errors.log"), "a") as fh:
                    fh.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {self.current}\n{tb}")
            except Exception:
                pass
            last = tb.strip().splitlines()[-1] if tb.strip() else ""
            self.tg.send(chat_id, f"التراك فشل: {type(e).__name__}: {str(e)[:200]}\n"
                                  f"آخر سطر: {last[:200]}\n"
                                  "التفاصيل الكاملة في كونسول النوتبوك وفي render_errors.log.")
            return
        finally:
            self._mark_busy(False)
        try:
            self._deliver(chat_id, r)
        except Exception as e:
            tb = traceback.format_exc()
            print("delivery failed:\n" + tb)
            try:
                with open(os.path.join(self.out_root, "render_errors.log"), "a") as fh:
                    fh.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} delivery {self.current}\n{tb}")
            except Exception:
                pass
            folder = r.get("folder") if isinstance(r, dict) else None
            self.tg.send(chat_id, f"التراك اتعمل بس مقدرتش أبعتهولك: {type(e).__name__}: {str(e)[:200]}\n"
                                  + (f"موجود على الجهاز في {folder} - /library بيفتحه تاني.\n" if folder else "")
                                  + "مفيش حاجة ضاعت.")

    def _render(self, chat_id, spec):
        """Run make_track in its own thread so a long render can still say it is alive."""
        box = {}

        def run():
            try:
                box["r"] = self.make_track(spec, "Rahal", "Rahal")
            except BaseException as e:      # noqa: BLE001 - handed to the caller below
                box["err"] = e

        t = threading.Thread(target=run, daemon=True)
        t.start()
        started = time.time()
        step = (self.render_note_minutes or 0) * 60 or 20
        note_at = step
        while t.is_alive():
            t.join(timeout=min(step, 20))
            if t.is_alive() and note_at and time.time() - started >= note_at:
                mins = int((time.time() - started) // 60)
                try:
                    self.tg.send(chat_id, f"لسه بيتعمل {self.current}: عدّى {mins} دقيقة. شغال لوحده، مش محتاج تبعت حاجة.")
                except Exception as e:
                    print("heartbeat send failed:", repr(e))
                note_at += step
        if "err" in box:
            raise box["err"]
        r = box.get("r")
        if not isinstance(r, dict) or not r.get("folder"):
            raise RuntimeError("the engine finished but returned no track folder")
        return r

    def _deliver(self, chat_id, r):
        base, folder, title = r["base"], r["folder"], r["title"]
        if not os.path.isdir(folder):
            raise RuntimeError(f"the release folder is missing on disk: {folder}")
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        mp3 = base + "_320kbps.mp3"
        if not os.path.exists(mp3) or os.path.getsize(mp3) > TG_LIMIT:
            mp3 = base + "_preview_128k.mp3"
        if not os.path.exists(mp3):
            raise RuntimeError(f"no audio in {os.path.basename(folder)} (looked for the 320 kbps file and the 128 kbps preview)")
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
        self.tg.send(chat_id, "اتحفظ على درايف: " + os.path.basename(folder)
                              + " (WAV/FLAC/MP3 والغلاف والكلمات والمعلومات وفورم RouteNote).\n" + ASSIST_HINT,
                     keyboard=[[{"text": "\U0001f916 اسألني", "callback_data": "ask"},
                                {"text": "\U0001f3b5 تراك تاني", "callback_data": "sug:track"}]])
        try:
            self._approve_menu(chat_id, folder, title)
        except Exception as e:
            print("publish menu failed:", repr(e))

    # ---------- assistant ----------
    def _snapshot(self):
        """Everything the assistant is allowed to talk about, read from the bot itself."""
        files = self._ds_manifest()["files"]
        vocal = sum(1 for v in files.values() if v.get("kind") == "vocal")
        inst = sum(1 for v in files.values() if v.get("kind") == "instrumental")
        liked = sum(1 for v in self._liked()["tracks"].values() if v.get("kept"))
        try:
            yt = bool(self._yt_token())
        except Exception:
            yt = False
        lora = False
        try:
            glob = getattr(self.make_track, "__globals__", {}) or {}
            lora = bool(glob.get("LORA_ADAPTERS"))
        except Exception:
            pass

        def have(module):
            try:
                import importlib.util as _u
                return _u.find_spec(module) is not None
            except Exception:
                return False

        return {"build": VERSION, "engine": bool(self.make_track),
                "rendering": self.current, "waiting": self.jobs.qsize(),
                "dataset": {"count": len(files), "vocal": vocal, "instrumental": inst,
                            "unlabelled": max(0, len(files) - vocal - inst)},
                "liked": liked,
                "publish": {"youtube": yt, "telegram": bool(CHANNEL),
                            "instagram": False, "tiktok": False, "facebook": False},
                "lora": lora, "voice": have("faster_whisper"), "ocr": have("pytesseract")}

    def _secret(self, name):
        """A secret by name: environment first, then Colab or Kaggle secrets."""
        v = (os.environ.get(name) or "").strip()
        if v:
            return v
        try:
            from google.colab import userdata
            v = (userdata.get(name) or "").strip()
            if v:
                return v
        except Exception:
            pass
        try:
            from kaggle_secrets import UserSecretsClient
            v = (UserSecretsClient().get_secret(name) or "").strip()
            if v:
                return v
        except Exception:
            pass
        return ""

    def _llm(self):
        """True when a free model key is configured. The key itself is never printed."""
        if self._llm_ready is None:
            self.llm_key = self._secret("ZI_LLM_KEY")
            self.groq_key = self._secret("ZI_GROQ_KEY") or self._secret("GROQ_API_KEY")
            self.llm_model = (os.environ.get("ZI_LLM_MODEL") or ziassist.DEFAULT_MODEL).strip()
            self._llm_ready = True
            if self.groq_key:
                print("assistant: Groq on (" + (os.environ.get("ZI_GROQ_MODEL") or ziassist.GROQ_DEFAULT_MODEL) + ")")
            if self.llm_key:
                print("assistant: free model on (" + self.llm_model + ")")
        return bool(self.llm_key or self.groq_key)

    def _vision_text(self, path, mime="image/jpeg", prompt=None):
        """Read a screenshot: Groq first, Gemini second. None when both fail (the caller says so)."""
        if not self._llm():
            return None
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except Exception as e:
            print("vision read failed:", type(e).__name__)
            return None
        if len(data) > 6 * 1024 * 1024:
            return None
        problems = []
        if self.groq_key and hasattr(ziassist, "read_image_groq"):
            try:
                text, problem = ziassist.read_image_groq(data, self.groq_key, mime=mime, prompt=prompt)
            except Exception as e:
                print("groq vision call failed:", type(e).__name__)
                text, problem = None, type(e).__name__
            if text:
                self.vision_problem = ""
                return text
            problems.append(problem)
        if self.llm_key and hasattr(ziassist, "read_image_retry"):
            models = ziassist.vision_models(self.llm_key, extra=[self.llm_model])
            try:
                text, problem = ziassist.read_image_retry(data, self.llm_key, models=models, mime=mime)
            except Exception as e:
                print("vision call failed:", type(e).__name__)
                text, problem = None, type(e).__name__
            if text:
                self.vision_problem = ""
                return text
            problems.append(problem)
        self.vision_problem = "; ".join(p for p in problems if p)
        print("vision: nothing could read it (" + self.vision_problem + ")")
        return None

    SUGGESTIONS = (("\u2753 إيه الناقص؟", "sug:missing"),
                   ("\u27a1\ufe0f أعمل إيه بعد كده؟", "sug:next"),
                   ("\U0001f4ca الحالة", "sug:status"),
                   ("\U0001f3b5 اعمل تراك", "sug:track"))

    def _suggestion_kb(self, state=None):
        """Two or three next steps, never a wall of buttons."""
        rows = [[{"text": t, "callback_data": c} for t, c in self.SUGGESTIONS[:2]],
                [{"text": t, "callback_data": c} for t, c in self.SUGGESTIONS[2:]]]
        return rows

    @staticmethod
    def _looks_like_idea(text):
        low = (text or "").lower()
        if re.search(r"\b\d{2,3}\s*bpm\b", low) or "instrumental" in low or "lyrics" in low:
            return True
        return any(w in low for words, _ in opt.STYLE_LOOKUP for w in words)

    def _speak(self, chat_id, text):
        """Send the answer as a voice note too. False when there is no free TTS on the box."""
        try:
            made = voice.speak(text, self.work)
        except Exception as e:
            print("tts failed:", type(e).__name__)
            return False
        if not made:
            return False
        caption = re.sub(r"[*_`#]+", "", text).strip()[:200]
        try:
            if made.get("voice_note"):
                self.tg.voice(chat_id, made["path"], caption=caption)
            else:
                self.tg.audio(chat_id, made["path"], caption=caption)
            return True
        except Exception as e:
            print("voice send failed:", type(e).__name__)
            return False

    def _save_feedback(self, text):
        """A change request for the developer, kept as one JSON line. Returns True when saved."""
        try:
            with open(os.path.join(self.out_root, "feedback_notes.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "text": (text or "")[:1000],
                                     "build": VERSION}, ensure_ascii=False) + "\n")
            print("feedback note saved:", (text or "")[:120])
            return True
        except Exception as e:
            print("feedback note failed:", type(e).__name__)
            return False

    def _assistant(self, chat_id, question, suggest=False, spoken=False):
        if hasattr(ziassist, "is_feedback") and ziassist.is_feedback(question):
            self._save_feedback(question)
            self.tg.send(chat_id, ziassist.FEEDBACK_REPLY)
            return
        try:
            state = self._snapshot()
        except Exception as e:
            print("assistant snapshot failed:", repr(e))
            state = {"build": VERSION}
        text = None
        if self._llm():
            for provider in ("groq", "gemini"):
                try:
                    if provider == "groq" and self.groq_key:
                        text = ziassist.ask_groq(question, state, self.groq_key)
                    elif provider == "gemini" and self.llm_key:
                        text = ziassist.ask_llm(question, state, self.llm_key, self.llm_model)
                except Exception as e:             # never let the model path break the bot
                    print("assistant " + provider + " call failed:", type(e).__name__)
                    text = None
                if text and ziassist.has_jargon(text):
                    # it answered with technical status or the wrong intro: try the next one
                    print("assistant answer dropped: jargon (" + provider + ")")
                    text = None
                if text:
                    break
            if text and ziassist.has_jargon(text):
                # it answered with technical status or the wrong intro: use the grounded
                # answer instead, so he never reads a capability claim that is not live
                print("assistant answer dropped: jargon")
                text = None
        if not text:
            try:
                text = ziassist.answer(question, state)
            except Exception as e:
                print("assistant answer failed:", repr(e))
                text = "حصلت مشكلة وأنا بجهز الرد. جرب تاني، أو /status."
        if spoken and text.startswith("ما وصلنيش كويس"):
            text += "\n(سمعت: " + question.strip()[:200] + ")"
        text, tag = ziassist.split_reaction(text)
        if tag:
            self._react(chat_id, self.cur_msg.get(chat_id), tag)
        self.tg.send(chat_id, text, keyboard=self._suggestion_kb(state) if suggest else None)
        if spoken:
            self._speak(chat_id, text)

    def _ask(self, chat_id, arg):
        q = (arg or "").strip()
        if q:
            self._assistant(chat_id, q)
            return
        self.ask_mode.add(chat_id)
        state = self._snapshot()
        head = "أنا مساعدك الشخصي. اسألني بالعربي وأنا أجاوب من حالة الشغل نفسها.\n" \
               "أقدر أقولك: الناقص، اللي تعمله بعد كده، حالة الشغل، تراكات التدريب، اللي حفظته، النشر، والموديل.\n" \
               "اكتب \"خروج\" أو /end تقفل المحادثة."
        miss = ziassist.missing(state)
        if miss:
            head += "\n\nاللي ناقص دلوقتي:\n- " + "\n- ".join(miss[:5])
        self.tg.send(chat_id, head)

    # ---------- style reference ----------
    REF_HINT = ("ابعت المرجع: اسم تراك أو مغني، سكرين شوت، لينك، أو فويس نوت. "
                "بستخدمه بس عشان أطلّع الستايل - الاسم مبيدخلش البرومبت أبداً، "
                "ومبيتحمّلش أي صوت، ومفيش حاجة بتتنسخ من الأغنية نفسها.")

    def _http_text(self, url, limit=200000, timeout=8):
        req = urllib.request.Request(url, headers={"User-Agent": "zi-studio-bot/1.0 (+music studio)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(limit).decode("utf-8", "ignore")

    def _itunes(self, query):
        """Free iTunes lookup: the genre label and the name, nothing else."""
        q = (query or "").strip()[:120]
        if not q:
            return None
        for entity in ("song", "musicArtist"):
            try:
                url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
                    {"term": q, "entity": entity, "limit": 3})
                data = json.loads(self._http_text(url))
            except Exception as e:
                print("itunes lookup failed:", repr(e))
                continue
            for r in data.get("results") or []:
                genre = r.get("primaryGenreName")
                if genre:
                    return {"genre": genre, "artist": r.get("artistName"),
                            "track": r.get("trackName") or r.get("artistName")}
        return None

    def _reference_link(self, chat_id, url):
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        try:
            page = self._http_text(url)
        except Exception as e:
            self.tg.send(chat_id, f"معرفتش أفتح اللينك ده: {str(e)[:120]}\n"
                                  "ابعت اسم التراك كتابة بدله.")
            return
        # only the page's own title and description are used - never the audio
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()
        for pat in (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)'):
            m = re.search(pat, page, re.I)
            if m and m.group(1).strip() and len(m.group(1).strip()) > 2:
                title = m.group(1).strip()      # the page's own idea of its title wins
                break
        desc = ""
        for pat in (r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)'):
            m = re.search(pat, page, re.I)
            if m:
                desc = m.group(1).strip()
                break
        text = " ".join(x for x in (title, desc) if x)
        if not text.strip():
            self.tg.send(chat_id, "الصفحة دي مفيهاش عنوان أو وصف أشتغل عليه. "
                                  "ابعت اسم التراك كتابة بدله.")
            return
        self.tg.send(chat_id, "قريت من اللينك: " + title[:120])
        # the title identifies it; only the page's own description becomes prompt words
        q = title.split("|")[0].strip()
        q = re.sub(r"\s*-\s*(YouTube|Spotify|SoundCloud|Apple\s*Music|Deezer|Tidal|Bandcamp)\s*$", "",
                   q, flags=re.I).strip()
        self._reference_from(chat_id, query=q, words=desc[:400])

    def _reference_photo(self, chat_id, photo):
        try:
            data = self._download_file(photo["file_id"])
        except Exception as e:
            self.tg.send(chat_id, f"معرفتش أجيب السكرين شوت دي: {str(e)[:120]}")
            return
        path = os.path.join(self.work, "reference.jpg")
        try:
            with open(path, "wb") as fh:
                fh.write(data)
        except Exception as e:
            self.tg.send(chat_id, f"معرفتش أحفظ السكرين شوت دي: {str(e)[:120]}")
            return
        # the vision model reads layouts far better than OCR, so it goes first when there is a key
        text = (self._vision_text(path) or "") if self._llm() else ""
        if len(text) < 3:
            try:
                import pytesseract                  # noqa: PLC0415 - optional on this box
                from PIL import Image
                text = pytesseract.image_to_string(Image.open(path)) or ""
            except Exception as e:
                print("ocr unavailable:", repr(e))
            text = re.sub(r"\s+", " ", text).strip()
            # OCR on a busy screenshot is mostly noise: keep it only if it holds real words
            if len([w for w in re.findall(r"[A-Za-z\u0600-\u06FF]{3,}", text)]) < 2:
                text = ""
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 3:
            self.tg.send(chat_id, VISION_HINT)
            return
        self.tg.send(chat_id, "\u0642\u0631\u064a\u062a \u0645\u0646 \u0627\u0644\u0635\u0648\u0631\u0629: " + text[:160])
        self._reference_text(chat_id, text[:200])

    def _reference_text(self, chat_id, text):
        """A name, or words about the style: identify it if we can, then describe it."""
        raw = (text or "").strip()
        if len(raw) < 3:
            b = self.builders.get(chat_id)
            self.tg.send(chat_id, self.REF_HINT if b else "الجلسة دي انتهت. /track بيبدأ تراك جديد.")
            return
        self._reference_from(chat_id, query=raw, words=raw)

    def _reference_from(self, chat_id, query, words=""):
        b = self.builders.get(chat_id)
        if not b:
            self.tg.send(chat_id, "الجلسة دي انتهت. /track بيبدأ تراك جديد.")
            return
        clean, removed = clean_idea(words or "")
        found = self._itunes(query) if query else None
        if found:
            # the name was only there to find the style; it has no place in the prompt
            for name in (found.get("artist"), found.get("track")):
                if name and len(str(name)) > 1:
                    clean = re.sub(re.escape(str(name)), " ", clean, flags=re.I)
            clean = opt.DANGLING_RE.sub(" ", clean)
            clean = re.sub(r"[\s\-|,;]+", " ", clean).strip(" ,.;-|")
        hay = (clean + " " + (query or "")).lower()
        # words he typed that name a style beat a genre label from the lookup
        word_style = None
        if any(w in hay for words_, _ in opt.STYLE_LOOKUP for w in words_):
            word_style = opt.pick_style(clean or query)
        style = word_style or (opt.genre_to_style(found["genre"]) if found else None)
        if not style:
            self.tg.send(chat_id, "معرفتش أطلّع ستايل من ده. ابعت النوع والتمبو بالكلام - "
                                  "مثلاً 'melodic techno, 122 bpm, dark' - أو /cancel.")
            return
        theme = clean if clean and not opt.has_non_latin(clean) else ""
        if b.get("step") == "own_prompt":
            # his own prompt is coming: keep the style, never show a prompt of ours
            b["own_ref"] = {"style": style, "theme": theme}
            label = opt.PROMPT_STYLES.get(style, {}).get("label", style) if isinstance(style, str) else ""
            self.tg.send(chat_id, "خدت المرجع كستايل بس" + (f" ({label})" if label else "") +
                         ". ابعت البرومبت بتاعك دلوقتي وهستخدمهم مع بعض.")
            return
        built = build_prompt(theme, b["spec"].get("seconds", 330), 0,
                             instrumental=b["spec"].get("instrumental", True), style=style)
        heard = []
        if found:
            heard.append(f"{found.get('track') or ''} - {found.get('artist') or ''}".strip(" -"))
            heard.append(found.get("genre") or "")
        b["built"] = built
        b["ref_note"] = ("فهمت من المرجع: " + built["summary"]
                         + (f"\n(اتقرا من: {' / '.join(x for x in heard if x)})" if heard else ""))
        if removed:
            b["ref_note"] += "\nشلت الاسم من البرومبت: " + "; ".join(removed[:3])
        self._show_prompt(chat_id, b)

    # ---------- last settings ----------
    def _last_path(self):
        return os.path.join(self.out_root, "zi_bot_last.json")

    def _last_spec(self):
        d = self._load(self._last_path(), {})
        return d if isinstance(d, dict) and d.get("genre") else None

    def _remember(self, spec):
        keep = ("genre", "name", "idea", "seconds", "quality", "instrumental", "bpm", "key",
                "style_influence", "style_tags", "exclude", "weirdness", "steps", "lang")
        try:
            d = {k: spec.get(k) for k in keep if spec.get(k) not in (None, "")}
            self._save(self._last_path(), d)
        except Exception as e:
            print("could not remember the last settings:", repr(e))

    def _last_label(self, d):
        secs = int(d.get("seconds") or 330)
        kind = "instrumental" if d.get("instrumental", True) else "with lyrics"
        return f"\u267b\ufe0f Last: {d.get('genre')}, {secs // 60}:{secs % 60:02d}, {kind}"

    def _start_from_last(self, chat_id):
        d = self._last_spec()
        if not d:
            self.tg.send(chat_id, "مفيش إعدادات محفوظة لسه. /track بيعمل واحدة.")
            return
        spec = dict(d)
        self.builders[chat_id] = {"step": "confirm", "spec": spec}
        self._confirm(chat_id, self.builders[chat_id])

    # ---------- liked tracks ----------
    def _liked_path(self):
        return os.path.join(self.out_root, "zi_bot_liked.json")

    def _liked(self):
        d = self._load(self._liked_path(), {"tracks": {}})
        if not isinstance(d, dict) or not isinstance(d.get("tracks"), dict):
            d = {"tracks": {}}
        return d

    @staticmethod
    def _slug(text):
        return re.sub(r"[^A-Za-z0-9._-]+", "_", text or "").strip("_")[:40] or "track"

    def _keep(self, chat_id, key):
        name = self._lib_folder(key)
        folder = os.path.join(self.out_root, name) if name else None
        d = self._liked()
        entry = d["tracks"].get(key) or {}
        if entry.get("kept"):
            self.tg.send(chat_id, f"Already in Liked: {entry.get('title', 'that track')}")
            return
        if not folder:
            self.tg.send(chat_id, "التراك ده مش على الجهاز تاني (ممكن النوتبوك اتعمله ريستارت). "
                                  "دوس الزرار تحت تراك أحدث، أو /liked بيعرض اللي اتحفظ.")
            return
        try:
            title = self._publish_caption(folder)[0]
        except Exception:
            title = os.path.basename(folder)
        dest = os.path.join(self.out_root, "liked", f"{key}_{self._slug(title)}")
        os.makedirs(dest, exist_ok=True)
        copied = 0
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".mp3", ".wav", ".flac", ".json", ".txt", ".jpg", ".jpeg", ".png")):
                try:
                    shutil.copy2(os.path.join(folder, name), os.path.join(dest, name))
                    copied += 1
                except Exception as e:
                    print("liked copy failed:", name, repr(e))
        d["tracks"][key] = {"folder": folder, "title": title, "kept": True, "liked_dir": dest,
                            "when": time.strftime("%Y-%m-%d %H:%M:%S")}
        self._save(self._liked_path(), d)
        total = sum(1 for v in d["tracks"].values() if v.get("kept"))
        self.tg.send(chat_id, f"\u2b50 اتحفظ في المفضلة: {title}\n{dest}\n{copied} ملف. {total} تراك مفضّل. /liked بيعرضهم.\n"
                              "الخطوة الجاية: غلاف، فيديو، وبعدين نشر.",
                     keyboard=self._visual_kb(key))

    def _liked_cmd(self, chat_id):
        d = self._liked()
        kept = sorted((v.get("when", ""), v) for v in d["tracks"].values() if v.get("kept"))
        if not kept:
            self.tg.send(chat_id, "مفيش مفضّل لسه. دوس \u2b50 دُه التراك المطلوب تحت أي تراك وهيتحفظ لمجموعة LoRA.")
            return
        lines = [f"Liked: {len(kept)} track(s)"]
        for when, v in kept[-20:]:
            lines.append(f"- {v.get('title', '?')}  ({when})")
        lines.append("Folder: " + os.path.join(self.out_root, "liked"))
        self.tg.send(chat_id, "\n".join(lines))

    # ---------- training dataset ----------
    def _dataset_dir(self):
        d = os.path.join(self.out_root, DATASET_SUBDIR)
        os.makedirs(d, exist_ok=True)
        return d

    def _ds_path(self):
        return os.path.join(self._dataset_dir(), "manifest.json")

    def _ds_manifest(self):
        m = self._load(self._ds_path(), {"files": {}})
        if not isinstance(m, dict) or not isinstance(m.get("files"), dict):
            m = {"files": {}}
        return m

    def _ds_save(self, m):
        tmp = self._ds_path() + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(m, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self._ds_path())

    @staticmethod
    def _is_dataset_upload(msg):
        if msg.get("audio"):
            return True
        doc = msg.get("document") or {}
        name = (doc.get("file_name") or "").lower()
        mime = (doc.get("mime_type") or "").lower()
        return bool(doc) and (mime.startswith("audio/") or any(name.endswith(e) for e in DS_AUDIO_EXT))

    def _download_file(self, file_id):
        info = self.tg.call("getFile", file_id=file_id)
        url = FILE_API.format(token=self.tg.token, path=info["file_path"])
        with urllib.request.urlopen(url, timeout=300) as r:
            return r.read()

    def _ds_intake(self, chat_id, msg):
        f = msg.get("audio") or msg.get("document") or {}
        raw_name = (f.get("file_name") or f.get("title") or "").strip()
        if not raw_name:
            raw_name = f"track_{str(f.get('file_id'))[-10:]}"
        name = os.path.basename(raw_name.replace("\\", "/")) or "track"
        size = int(f.get("file_size") or 0)
        if size > DS_MAX_BYTES:
            self.tg.send(chat_id,
                         f"الملف ده {size / 1048576:.1f} ميجا، وتيليجرام بيسمح للبوت ينزّل لحد ٢٠ ميجا بس، "
                         "فمش هقدر أسحبه.\nابعته MP3 (غالباً أقل بكتير من ٢٠ ميجا)، أو حط الـ WAV "
                         "في فولدر على درايف وقولي أنهي فولدر.")
            return
        try:
            data = self._download_file(f["file_id"])
        except Exception as e:
            self.tg.send(chat_id, f"معرفتش أنزّل الملف ده: {str(e)[:200]}\n"
                                  "لو أكبر من ٢٠ ميجا ابعت MP3 أو فولدر درايف.")
            return
        sha = hashlib.sha256(data).hexdigest()
        m = self._ds_manifest()
        files = m["files"]
        if sha in files:
            self.tg.send(chat_id, f"الملف ده موجود عندي قبل كده ({files[sha]['name']}). {len(files)} في المجموعة.")
            return
        saved = name
        stem, ext = os.path.splitext(name)
        n = 2
        while os.path.exists(os.path.join(self._dataset_dir(), saved)):
            saved = f"{stem} ({n}){ext}"
            n += 1
        with open(os.path.join(self._dataset_dir(), saved), "wb") as fh:
            fh.write(data)
        files[sha] = {"name": saved, "size": len(data), "added": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "kind": None, "lyrics": None}
        self._ds_save(m)
        count = len(files)
        short = sha[:10]
        self.tg.send(chat_id, f"تمام، {saved} ({len(data) / 1048576:.1f} ميجا). اتحفظ {count} لحد دلوقتي.\n"
                              "بصوت ولا موسيقى بس؟",
                     keyboard=[[{"text": "\U0001f3a4 بصوت", "callback_data": f"ds:v:{short}"},
                                {"text": "\U0001f3b9 موسيقى بس", "callback_data": f"ds:i:{short}"}]])

    def _ds_find(self, short):
        for sha, v in self._ds_manifest()["files"].items():
            if sha.startswith(short):
                return sha, v
        return None, None

    def _ds_label(self, chat_id, short, kind):
        sha, v = self._ds_find(short)
        if not sha:
            self.tg.send(chat_id, "الملف ده مش في المجموعة تاني. /dataset بيعرض العدد.")
            return
        m = self._ds_manifest()
        m["files"][sha]["kind"] = kind
        self._ds_save(m)
        total = len(m["files"])
        if kind == "vocal":
            self.tg.send(chat_id, f"اتعلّم إنه بصوت. {total} في المجموعة.\nعايز تضيف الكلمات؟ ابعتها رسالة أو ملف .txt، "
                                  "أو تخطّى.",
                         keyboard=[[{"text": "\u270d\ufe0f ضيف كلمات", "callback_data": f"ds:l:{short}"},
                                    {"text": "تخطّى", "callback_data": f"ds:s:{short}"}]])
        else:
            self.tg.send(chat_id, f"اتعلّم إنه موسيقى بس. {total} في المجموعة.")

    def _ds_lyrics_wait(self, chat_id, short):
        sha, v = self._ds_find(short)
        if not sha:
            self.tg.send(chat_id, "الملف ده مش في المجموعة تاني.")
            return
        self.ds_lyrics[chat_id] = sha
        self.tg.send(chat_id, f"ابعت كلمات {v['name']} في رسالة واحدة أو ملف .txt.")

    def _ds_save_lyrics(self, chat_id, text=None, path=None):
        sha = self.ds_lyrics.pop(chat_id, None)
        if not sha:
            return False
        m = self._ds_manifest()
        entry = m["files"].get(sha)
        if not entry:
            self.tg.send(chat_id, "الملف ده مش في المجموعة تاني.")
            return True
        body = text
        if path:
            with open(path, "r", errors="replace") as fh:
                body = fh.read()
        body = (body or "").strip()
        if not body:
            self.tg.send(chat_id, "الكلمات فاضية، مفيش حاجة اتحفظت.")
            return True
        stem = os.path.splitext(entry["name"])[0]
        lp = os.path.join(self._dataset_dir(), stem + ".lyrics.txt")
        with open(lp, "w") as fh:
            fh.write(body + "\n")
        m["files"][sha]["lyrics"] = os.path.basename(lp)
        self._ds_save(m)
        self.tg.send(chat_id, f"الكلمات اتحفظت جنب {entry['name']}.")
        return True

    def _dataset(self, chat_id):
        files = self._ds_manifest()["files"]
        vocal = sum(1 for v in files.values() if v.get("kind") == "vocal")
        inst = sum(1 for v in files.values() if v.get("kind") == "instrumental")
        unlabelled = [v["name"] for v in files.values() if not v.get("kind")]
        lyrics = sum(1 for v in files.values() if v.get("lyrics"))
        total = sum(int(v.get("size") or 0) for v in files.values())
        lines = [f"مجموعة التدريب (mr-dorgham): {len(files)} ملف، {total / 1048576:.1f} MB",
                 f"بصوت {vocal} | موسيقى بس {inst} | من غير تصنيف {len(unlabelled)} | بكلمات {lyrics}",
                 f"الفولدر: {self._dataset_dir()}",
                 "ابعت ملفات صوت أو كلمات .txt في أي وقت. البوت مبيقدرش ينزّل أكتر من ٢٠ ميجا، "
                 "فابعت MP3 أو فولدر درايف للباقي."]
        if unlabelled:
            lines.append("مستني تصنيف: " + ", ".join(unlabelled[:8]) +
                         (f" and {len(unlabelled) - 8} more" if len(unlabelled) > 8 else ""))
        self.tg.send(chat_id, "\n".join(lines))

    # ---------- voice ----------
    def _download_voice(self, voice):
        f = self.tg.call("getFile", file_id=voice["file_id"])
        url = FILE_API.format(token=self.tg.token, path=f["file_path"])
        name = f"voice_{str(voice.get('file_unique_id') or voice['file_id'])[-16:]}.oga"
        path = os.path.join(self.out_root, name)
        with urllib.request.urlopen(url, timeout=180) as r, open(path, "wb") as fh:
            fh.write(r.read())
        return path

    def _log_transcript(self, engine, text):
        """One line per voice note, so a bad transcript can be debugged. No keys, no audio."""
        print("voice transcript (" + engine + "):", (text or "")[:300])
        try:
            with open(os.path.join(self.out_root, "transcripts.log"), "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\t" + engine + "\t" + (text or "").replace("\n", " ")[:500] + "\n")
        except Exception as e:
            print("transcript log failed:", type(e).__name__)

    def _transcribe(self, path):
        """Groq whisper first (much better on Egyptian Arabic), then the local model."""
        self._llm()
        if self.groq_key and hasattr(ziassist, "transcribe_groq"):
            try:
                text, problem = ziassist.transcribe_groq(path, self.groq_key)
            except Exception as e:
                text, problem = None, type(e).__name__
            if text:
                self._log_transcript("groq", text)
                return text
            print("groq transcription gave nothing (" + str(problem) + "), trying the local model")
        text = self._transcribe_local(path)
        if text:
            self._log_transcript("local", text)
        return text

    def _transcribe_local(self, path):
        """CPU speech to text. Multilingual, because he speaks Egyptian Arabic."""
        global _WHISPER
        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            print("transcription unavailable:", repr(e))
            return None
        try:
            if _WHISPER is None:
                for name in ("small", "base"):
                    try:
                        _WHISPER = WhisperModel(name, device="cpu", compute_type="int8")
                        print("whisper model:", name)
                        break
                    except Exception as e:
                        print("whisper", name, "failed:", repr(e))
                if _WHISPER is None:
                    return None
            segments, _info = _WHISPER.transcribe(path, vad_filter=True, beam_size=5)
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as e:
            print("transcribe failed:", repr(e))
            return None

    def _voice_prompt(self, chat_id, voice):
        try:
            path = self._download_voice(voice)
        except Exception as e:
            self.tg.send(chat_id, f"معرفتش أجيب الفويس نوت دي: {str(e)[:150]}")
            return None
        try:
            self.tg.call("sendChatAction", chat_id=chat_id, action="typing")
        except Exception:
            pass
        text = self._transcribe(path)
        if not text:
            self.tg.send(chat_id, "لسه مش قادر أحوّل الصوت لكلام على الجهاز ده. شغّل في النوتبوك "
                                  "`!pip install -q faster-whisper` وأعد تشغيل البوت وبعدين قول تاني. "
                                  "أو اكتب الفكرة.")
            return None
        self.heard_raw[chat_id] = (text, time.time())
        if opt.has_arabic(text) or ziassist.has_foreign_letters(text):
            r = ziassist.to_english_prompt(text, self.groq_key) if self.groq_key else None
            if r and r["english"] and not opt.has_arabic(text):
                return r["english"]
            if opt.has_arabic(text):
                english, leftover = opt.to_english(text)
                if english:
                    if leftover and r and r["english"]:
                        return r["english"]
                    if leftover:
                        self.tg.send(chat_id, "سمعت: " + text + "\nفهمت منها: " + english)
                    return english
                return text                    # no music words: a question, the assistant answers it
            if r and r["english"]:
                return r["english"]
        return text


    # ---------- remix / cover and remaster of a saved track ----------
    COVER_CLOSE = (("قريب من الأصلي", 0.8), ("وسط", 0.65), ("بعيد عنه", 0.4))

    def _engine_has(self, name):
        """A capability is live only when the engine cell defines it."""
        try:
            glob = getattr(self.make_track, "__globals__", {}) or {}
            return bool(glob.get(name))
        except Exception:
            return False

    def _folder_for(self, key):
        name = self._lib_folder(key)
        folder = os.path.join(self.out_root, name) if name else None
        return folder if folder and os.path.isdir(folder) else None

    def _remix_cb(self, chat_id, data):
        kind, _, rest = data.partition(":")
        key = rest.split(":")[0]
        folder = self._folder_for(key)
        if not folder:
            self.tg.send(chat_id, "التراك ده مش في فولدر الجلسة تاني. دوس المكتبة تاني.")
            return
        title = self._publish_caption(folder)[0]
        if kind == "rmt":
            self._remaster(chat_id, folder, title)
            return
        if not self._engine_has("COVER_TASKS"):
            self.tg.send(chat_id, "الريميكس لسه مش شغال على الجهاز ده.")
            return
        if kind == "rmx":
            self.remix[chat_id] = {"key": key, "idea": None}
            self.tg.send(chat_id, f"ريميكس لـ {title}. قولي عايزه يبقى إيه: النوع أو الجو، بصوتك أو كتابة "
                                  "(مثلاً: afro house دافي، أو lo-fi هادي). الأصل هيفضل زي ما هو والنتيجة تراك جديد.")
            return
        st = self.remix.get(chat_id)          # rmxs:<key>:<strength index>
        if not st or st.get("idea") is None or st["key"] != key:
            self.tg.send(chat_id, "الجلسة دي انتهت. دوس ريميكس من تحت التراك تاني.")
            return
        try:
            strength = self.COVER_CLOSE[int(rest.split(":")[1])][1]
        except Exception:
            strength = 0.65
        self.remix.pop(chat_id, None)
        self._enqueue(chat_id, self._cover_spec(folder, st["idea"], strength))
        self.tg.send(chat_id, "ماشي، بعمل الريميكس. هيظهر تراك جديد في المكتبة.")

    def _remix_text(self, chat_id, text):
        st = self.remix[chat_id]
        said = text
        raw = self.heard_raw.get(chat_id)
        if raw and time.time() - raw[1] < 10:
            said = raw[0]
        res = self._english_text(chat_id, said)
        if res is None:
            return
        idea, changed = res
        if not idea or len(idea.strip()) < 4:
            self.tg.send(chat_id, "ما وصلنيش كويس، ممكن تعيدها؟ قولي النوع أو الجو بكلمتين.")
            return
        if changed:
            self._say_english(chat_id, idea)
        clean, _removed = clean_idea(idea)
        st["idea"] = clean if len(clean) >= 4 else idea
        folder = self._folder_for(st["key"])
        title = self._publish_caption(folder)[0] if folder else "التراك"
        kb = [[{"text": f"ولّد: {self.COVER_CLOSE[0][0]}", "callback_data": f"rmxs:{st['key']}:0"},
               {"text": f"ولّد: {self.COVER_CLOSE[1][0]}", "callback_data": f"rmxs:{st['key']}:1"}],
              [{"text": f"ولّد: {self.COVER_CLOSE[2][0]}", "callback_data": f"rmxs:{st['key']}:2"}]]
        self.tg.send(chat_id, f"هعمل ريميكس لـ {title} بالستايل ده: {st['idea']}.\n"
                              "اختار قد إيه يقرّب من الأصلي وأبدأ (الأصل مش هيتغيّر):", keyboard=kb)

    def _cover_spec(self, folder, idea, strength):
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        flacs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".flac"))
        src = os.path.join(folder, flacs[0]) if flacs else None
        title = self._publish_caption(folder)[0]
        secs = int(min(600, max(60, float(meta.get("actual_duration_sec") or meta.get("target_duration_sec") or 180))))
        instrumental = bool(meta.get("instrumental", True))
        style = opt.pick_style(idea)
        built = build_prompt(idea, secs, 0, instrumental=instrumental, style=style)
        spec = {"task_type": "cover", "src_audio_path": src, "cover_strength": strength,
                "idea": built["prompt"], "genre": built["genre"], "name": built["genre"],
                "title": f"{title} (Remix)", "seconds": secs, "instrumental": instrumental,
                "quality": "high", "lang": meta.get("language") or "en",
                "bpm": built["bpm"], "key": built["key"]}
        if not instrumental:
            try:
                ly = open(os.path.join(folder, "lyrics.txt"), encoding="utf-8").read().strip()
                if ly and ly != "[Instrumental]":
                    spec["lyrics"] = ly
            except OSError:
                pass
        return spec

    def _remaster(self, chat_id, folder, title):
        fn = None
        try:
            fn = (getattr(self.make_track, "__globals__", {}) or {}).get("remaster_release")
        except Exception:
            pass
        if not fn:
            self.tg.send(chat_id, "الريماستر لسه مش شغال على الجهاز ده.")
            return
        self.tg.send(chat_id, f"بعمل ريماستر لـ {title}. دقيقة وراجعلك. الأصل هيفضل زي ما هو.")

        def work():
            try:
                r = fn(folder)
            except Exception as e:
                print("remaster failed:", repr(e))
                self.tg.send(chat_id, f"الريماستر فشل: {str(e)[:200]}")
                return
            rep = r.get("mastering") or {}
            if rep.get("verified") is False:
                self.tg.send(chat_id, f"الريماستر خلص بس القياس مش على الهدف (لاود {rep.get('out_i')} LUFS، "
                                      f"بيك {rep.get('out_tp')} dBTP). شوفه بنفسك قبل ما تنشر.")
            try:
                self._deliver(chat_id, r)
            except Exception as e:
                print("remaster delivery failed:", repr(e))
                self.tg.send(chat_id, f"الريماستر اتعمل بس التسليم فشل: {str(e)[:200]}")
        threading.Thread(target=work, daemon=True).start()

    # ---------- any language in, English prompt out ----------
    def _english_text(self, chat_id, text):
        """(english text, changed) for a prompt in any language, or None when it cannot be made English.

        English passes through unchanged and never waits on a model. Anything else goes to Groq to
        detect the language and translate; Arabic falls back to the local lexicon. The caller
        answers him in Egyptian either way.
        """
        t = ziassist.strip_prompt_label(text)
        if ziassist.is_probably_english(t):
            return t, t != (text or "").strip()
        if self.groq_key and self._llm():
            r = ziassist.to_english_prompt(t, self.groq_key)
            if r:
                return r["english"], r["english"].strip() != t
        if opt.has_arabic(t):
            english, _left = opt.to_english(t)
            if english:
                return english, True
        if not ziassist.has_foreign_letters(t):
            return t, t != (text or "").strip()      # Latin script, no model: pass it through
        self.tg.send(chat_id, "ما وصلنيش كويس، ممكن تعيدها؟ أو قولها بكلمات تانية.")
        return None

    def _say_english(self, chat_id, english):
        short = english if len(english) <= 220 else english[:217] + "..."
        self.tg.send(chat_id, "فهمتها كده بالإنجليزي: " + short)

    # ---------- reactions ----------
    def _react(self, chat_id, message_id, emoji, always=False):
        """Set one emoji reaction on his message. Never raises, never spams."""
        if not message_id or not emoji or (chat_id, message_id) in self.reacted:
            return False
        if not always and time.time() - self.last_react < 15:
            return False
        try:
            self.tg.call("setMessageReaction", chat_id=chat_id, message_id=message_id,
                         reaction=json.dumps([{"type": "emoji", "emoji": emoji}]))
        except Exception as e:
            print("reaction failed:", type(e).__name__)
            return False
        self.reacted[(chat_id, message_id)] = emoji
        if not always:
            self.last_react = time.time()
        return True

    # ---------- one request from several pieces ----------
    JOIN_SEC = 90

    def _fresh(self, ts):
        return ts is not None and time.time() - ts <= self.JOIN_SEC

    def _remember_say(self, chat_id, text):
        if text and not text.startswith("/"):
            self.last_say[chat_id] = {"text": text, "ts": time.time(), "used": False}

    def _recent_say(self, chat_id):
        d = self.last_say.get(chat_id)
        if d and not d["used"] and self._fresh(d["ts"]):
            return d
        return None

    def _hold(self, chat_id, kind, payload):
        self.pending[chat_id] = {"kind": kind, "payload": payload, "ts": time.time()}
        what = "الصورة" if kind == "photo" else "اللينك"
        self.tg.send(chat_id, f"استلمت {what}. قولي عايز إيه منها (اكتب أو ابعت فويس)، أو دوس:",
                     keyboard=[[{"text": "\U0001f50e ستايل مرجع", "callback_data": "img:ref"},
                                {"text": "\u274c سيبها", "callback_data": "img:drop"}]])

    def _take_pending(self, chat_id):
        d = self.pending.get(chat_id)
        if d and self._fresh(d["ts"]):
            self.pending.pop(chat_id, None)
            return d
        self.pending.pop(chat_id, None)
        return None

    def _combined(self, chat_id, kind, payload, instruction):
        """An image or link plus what he said about it: one request, one answer."""
        instruction = (instruction or "").strip()
        words = ziassist.strip_links(instruction) if kind == "link" else instruction
        step = (self.builders.get(chat_id) or {}).get("step")
        asks_ref = ziassist.is_reference_words(words) or (len(words) < 3 and kind in ("photo", "link"))
        if asks_ref or (step in self.PROMPT_STEPS and not self._looks_like_question(words)):
            if step not in self.PROMPT_STEPS:
                self.builders[chat_id] = {"step": "ref_wait",
                                          "spec": {"lang": "en", "quality": "high",
                                                   "instrumental": True, "seconds": 330}}
            self.tg.send(chat_id, "فهمت: ده مرجع للستايل بس. بقراه وأطلع منه الستايل.")
            if kind == "photo":
                self._reference_photo(chat_id, payload)
            else:
                self._reference_link(chat_id, payload)
            return
        if kind == "photo":
            what = self._describe_photo(payload)
            if not what:
                self.tg.send(chat_id, "معرفتش أقرا الصورة دلوقتي. قولي اللي فيها بكلمتين وأكمل معاك.")
                return
        else:
            what = self._page_title(payload)
            if not what:
                self.tg.send(chat_id, "معرفتش أفتح اللينك ده. قولي هو إيه وأكمل معاك.")
                return
        self._assistant(chat_id, ziassist.combine_question(words or instruction, what, "image" if kind == "photo" else "link"),
                        suggest=True)

    @staticmethod
    def _looks_like_question(text):
        return bool(re.search(r"[?\u061f]|^(ايه|إيه|ليه|ازاي|إزاي|هل|مين|فين|امتى|إمتى|عايز اعرف|فيها|ده ايه)", (text or "").strip()))

    def _describe_photo(self, photo):
        try:
            data = self._download_file(photo["file_id"])
            path = os.path.join(self.work, "combined.jpg")
            with open(path, "wb") as fh:
                fh.write(data)
        except Exception as e:
            print("combined image download failed:", type(e).__name__)
            return None
        if not self._llm():
            return None
        return self._vision_text(path, prompt=ziassist.DESCRIBE_PROMPT)

    def _page_title(self, url):
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        try:
            page = self._http_text(url)
        except Exception as e:
            print("combined link fetch failed:", type(e).__name__)
            return None
        for pat in (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                    r"<title[^>]*>(.*?)</title>"):
            m = re.search(pat, page, re.S | re.I)
            if m and m.group(1).strip():
                return re.sub(r"\s+", " ", m.group(1)).strip()[:200]
        return None

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
            self._track_user(cb.get("from"))
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
                    self.tg.send(chat_id, f"الخطوة دي فشلت: {str(e)[:200]}")
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
        first_time = self._track_user(msg.get("from"))
        if msg.get("contact"):
            self._contact_shared(chat_id, msg)
            return
        if not self._is_owner(chat_id):
            if text.startswith("/start") and self.pair_code and text.endswith(self.pair_code):
                self.owner = chat_id
                self._save(self.owner_path, {"chat_id": chat_id})
                self.pair_code = None
                self._track_user(msg.get("from"))
                self.tg.send(chat_id, "تمام. البوت ده بيرد عليك إنت بس دلوقتي.\n" + opt.USERS_NOTICE + "\n\n" + HELP)
                self._launcher(chat_id)
            else:
                if first_time:
                    self.tg.send(chat_id, "ده بوت استوديو خاص.\n" + opt.USERS_NOTICE +
                                 "\nلو عايز نتأكد إنك شخص حقيقي، شارك رقمك بالزرار تحت (اختياري).", reply=self.PHONE_KB)
                else:
                    self.tg.send(chat_id, "ده بوت استوديو خاص.")
            return
        if not self._launcher_sent:
            # after a restart or a cleared chat the buttons are gone until the bot
            # sends them once; do it on his first message, whatever it is
            self._launcher_sent = True
            self._launcher(chat_id)
        mid = msg.get("message_id")
        self.cur_msg[chat_id] = mid
        is_img = bool(msg.get("photo")) or str((doc or {}).get("mime_type") or "").startswith("image/")
        is_voice = bool(msg.get("voice") or msg.get("audio") or msg.get("video_note"))
        if is_img or is_voice:
            self._react(chat_id, mid, ziassist.reaction_for("", "photo" if is_img else "voice"), always=True)
        elif text and not text.startswith("/"):
            self._react(chat_id, mid, ziassist.reaction_for(text))
        if self._is_dataset_upload(msg):
            if self._audio_ref_wanted(chat_id):
                self._reference_audio(chat_id, msg)
            else:
                self._ds_intake(chat_id, msg)
            return
        photo = msg.get("photo")
        if not photo and doc and str(doc.get("mime_type") or "").startswith("image/"):
            photo = [doc]                       # a screenshot sent as a file, not as a photo
        if photo:
            caption = (msg.get("caption") or "").strip()
            said = self._recent_say(chat_id)
            if not caption and said:
                caption = said["text"]
                said["used"] = True
            if caption:
                self._combined(chat_id, "photo", photo[-1], caption)
                return
            step = (self.builders.get(chat_id) or {}).get("step")
            if step in self.PROMPT_STEPS:
                self._reference_photo(chat_id, photo[-1])
                return
            self._hold(chat_id, "photo", photo[-1])
            return
        if doc and (doc.get("file_name") or "").lower().endswith(".txt") and chat_id in self.ds_lyrics:
            try:
                data = self._download_file(doc["file_id"])
                tmp = os.path.join(self.out_root, "lyrics_upload.txt")
                with open(tmp, "wb") as fh:
                    fh.write(data)
                self._ds_save_lyrics(chat_id, path=tmp)
            except Exception as e:
                self.tg.send(chat_id, f"معرفتش أقرا ملف الـ txt ده: {str(e)[:150]}")
            return
        if doc and (doc.get("file_name") or "").endswith(".json"):
            self._batch_doc(chat_id, doc)
            return
        from_voice = False
        voice = msg.get("voice") or msg.get("audio") or msg.get("video_note")
        if voice and not text:
            text = self._voice_prompt(chat_id, voice)
            if not text:
                return
            from_voice = True
        if not text:
            return
        if not text.startswith("/"):
            rp = (msg.get("reply_to_message") or {}).get("photo")
            held = self._take_pending(chat_id)
            if rp:
                self._combined(chat_id, "photo", rp[-1], text)
                return
            if held:
                self._combined(chat_id, held["kind"], held["payload"], text)
                return
            link = re.search(r"(https?://\S+|www\.\S+)", text)
            step = (self.builders.get(chat_id) or {}).get("step")
            if link and step not in self.PROMPT_STEPS and chat_id not in self.ask_mode:
                rest = ziassist.strip_links(text)
                said = self._recent_say(chat_id)
                if len(rest) >= 3:
                    self._combined(chat_id, "link", link.group(1), rest)
                    return
                if said:
                    said["used"] = True
                    self._combined(chat_id, "link", link.group(1), said["text"])
                    return
                self._hold(chat_id, "link", link.group(1))
                return
            self._remember_say(chat_id, text)
        if chat_id in self.remix and not text.startswith("/") and self.remix[chat_id].get("idea") is None:
            self._remix_text(chat_id, text)
            return
        if chat_id in self.ds_lyrics and not text.startswith("/"):
            self._ds_save_lyrics(chat_id, text=text)
            return
        if chat_id in self.ask_mode and not text.startswith("/"):
            if text.strip().lower() in ("خروج", "إنهي", "انهي", "stop", "exit"):
                self.ask_mode.discard(chat_id)
                self.tg.send(chat_id, "قفلت المحادثة مع المساعد. /ask لو رجعت.")
                return
            self._assistant(chat_id, text, spoken=from_voice)
            return
        if chat_id in self.builders and not text.startswith("/"):
            self._builder_text(chat_id, text)
            return
        low = text.lower().strip()
        if low in ("menu", "\u2630 menu", "\u2630") or low.startswith("menu ") or low == "\u0627\u0644\u0642\u0627\u0626\u0645\u0629":
            self._menu(chat_id)
            return
        if low in ("studio", "\U0001f39b studio", "\U0001f39b") or low.startswith("studio "):
            self.tg.send(chat_id, "تطبيق الاستوديو: " + STUDIO_URL + "\nبيفتح جوّه تيليجرام لو التطبيق بيدعم، "
                                  "أو في المتصفح من اللينك ده.")
            return
        if not text.startswith("/"):
            # a spoken music idea still starts a track; anything else is a question for the
            # assistant, which offers the next steps as buttons
            if from_voice and self._looks_like_idea(text):
                self._track(chat_id, "")
                b = self.builders.get(chat_id)
                if b:
                    b["idea_seed"] = text
                    b["variant"] = 0
                    b["built"] = build_prompt(text, b["spec"].get("seconds", 330), 0,
                                              instrumental=b["spec"].get("instrumental", True))
                    self._show_prompt(chat_id, b)
                return
            self._assistant(chat_id, text, suggest=True, spoken=from_voice)
            return
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower().split("@")[0]
        if cmd == "/start" or cmd == "/help":
            self.tg.send(chat_id, HELP, keyboard=[[{"text": "\u2630 \u0627\u0644\u0642\u0627\u0626\u0645\u0629", "callback_data": "menu"}]])
            self._launcher(chat_id)
        elif cmd == "/menu":
            self._menu(chat_id)
        elif cmd == "/ask":
            self._ask(chat_id, arg)
        elif cmd == "/end":
            if chat_id in self.ask_mode:
                self.ask_mode.discard(chat_id)
                self.tg.send(chat_id, "قفلت المحادثة مع المساعد. /ask لو رجعت.")
            else:
                self.tg.send(chat_id, "مفيش محادثة مفتوحة. /ask يفتحها.")
        elif cmd == "/studio":
            self.tg.send(chat_id, "تطبيق الاستوديو: " + STUDIO_URL)
        elif cmd == "/cancel":
            self.builders.pop(chat_id, None)
            self.tg.send(chat_id, "اتلغى.")
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
        elif cmd == "/liked":
            self._liked_cmd(chat_id)
        elif cmd == "/dataset":
            self._dataset(chat_id)
        elif cmd == "/diag":
            self._diag(chat_id)
        elif cmd == "/jobs":
            self._jobs(chat_id)
        else:
            self.tg.send(chat_id, "الأمر ده مش معروف. /help بيعرض الأوامر.")

    def _callback(self, chat_id, data):
        b = self.builders.get(chat_id)
        if data == "social":
            self._social(chat_id)
            return
        if data.startswith("ov:"):
            if not b:
                self.tg.send(chat_id, "الجلسة دي انتهت. /track بيبدأ تراك جديد.")
                return
            _, key, val = data.split(":")
            try:
                b["spec"][key] = int(val)
            except Exception:
                pass
            self._show_options(chat_id, b)
            return
        if data.startswith("rmx:") or data.startswith("rmxs:") or data.startswith("rmt:"):
            self._remix_cb(chat_id, data)
            return
        if data == "lora:t":
            self._lora_toggle(chat_id)
            return
        if data.startswith("tw:"):
            self._tweak_cb(chat_id, data)
            return
        if data.startswith("keep:"):
            self._keep(chat_id, data.split(":", 1)[1])
            return
        if data.startswith(("art:", "artpick:", "vid:", "vidyt:", "vidytok:")):
            self._visual_cb(chat_id, data)
            return
        if data.startswith("ds:"):
            parts = data.split(":")
            act = parts[1] if len(parts) > 1 else ""
            short = parts[2] if len(parts) > 2 else ""
            if act == "v":
                self._ds_label(chat_id, short, "vocal")
            elif act == "i":
                self._ds_label(chat_id, short, "instrumental")
            elif act == "l":
                self._ds_lyrics_wait(chat_id, short)
            elif act == "s":
                self.tg.send(chat_id, "اتخطّى.")
            return
        if data == "last":
            self._start_from_last(chat_id)
            return
        if data == "ask":
            self._ask(chat_id, "")
            return
        if data.startswith("sug:"):
            what = data[4:]
            if what == "track":
                self._track(chat_id, "")
                return
            q = {"missing": "إيه الناقص؟", "next": "أعمل إيه بعد كده؟", "status": "الحالة"}.get(what, "الحالة")
            self._assistant(chat_id, q, suggest=True)
            return
        if data in ("img:ref", "img:drop"):
            held = self.pending.pop(chat_id, None)
            if not held:
                self.tg.send(chat_id, "مفيش حاجة مستنية. ابعتها تاني.")
            elif data == "img:drop":
                self.tg.send(chat_id, "تمام، سيبتها.")
            else:
                self._combined(chat_id, held["kind"], held["payload"], "مرجع")
            return
        if data == "menu":
            self._menu(chat_id)
            return
        if data == "social:fb":
            self.tg.send(chat_id, "\u0644\u064a\u0646\u0643 \u0635\u0641\u062d\u0629 \u0641\u064a\u0633\u0628\u0648\u0643 \u0644\u0633\u0647 \u0645\u0634 \u0645\u0636\u0627\u0641. \u0628\u0645\u062c\u0631\u062f \u0645\u0627 \u062a\u0628\u0639\u062a\u0647\u0648\u0644\u064a \u0647\u064a\u062a\u0636\u0627\u0641 \u0647\u0646\u0627.")
            return
        if data.startswith("menu:"):
            self._menu_step(chat_id, data[5:])
            return
        if data.startswith("o:"):
            if not b:
                self.tg.send(chat_id, "الجلسة دي انتهت. /track بيبدأ تراك جديد.")
                return
            self._option_step(chat_id, b, data[2:])
            return
        if data == "p:refname":
            if not b or not b.get("removed"):
                self.tg.send(chat_id, "مفيش اسم اتشال أستخدمه. /nothing was removed to use as a reference.")
                return
            name = opt.name_from_span(b["removed"][0])
            if not name:
                self.tg.send(chat_id, "مش لاقي اسم في اللي اتشال. جرب Reference واكتب الاسم بنفسك.")
                return
            self.tg.send(chat_id, f"بستخدم {name} كمرجع للستايل...")
            self._reference_from(chat_id, query=name, words="")
            return
        if data.startswith("p:"):
            if not b:
                self.tg.send(chat_id, "الجلسة دي انتهت. /track بيبدأ تراك جديد.")
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
                self.tg.send(chat_id, "التراك ده مش في فولدر الجلسة تاني. /library بيعرض الحاليين.")
                return
            self._get(chat_id, folder, audio=True)
            key = data[4:]
            kb = [[{"text": "\U0001f4e3 \u0627\u0646\u0634\u0631", "callback_data": "pubmenu:" + key}]]
            extra = []
            if self._engine_has("COVER_TASKS"):
                extra.append({"text": "\u267b\ufe0f ريميكس/كفر", "callback_data": "rmx:" + key})
            if self._engine_has("remaster_release"):
                extra.append({"text": "\U0001f39a ريماستر", "callback_data": "rmt:" + key})
            kb[0] += extra[:1]
            if len(extra) > 1:
                kb.append(extra[1:])
            kb.append([{"text": "\u2630 \u0627\u0644\u0642\u0627\u0626\u0645\u0629", "callback_data": "menu"}])
            self.tg.send(chat_id, "عايز تعمل إيه فيه؟", keyboard=kb)
            return
        if data.startswith("pubmenu:"):
            name = self._lib_folder(data[8:])
            folder = os.path.join(self.out_root, name) if name else None
            if not folder or not os.path.isdir(folder):
                self.tg.send(chat_id, "التراك ده مش في فولدر الجلسة تاني. دوس المكتبة تاني.")
                return
            self._publish_menu(chat_id, folder)
            return
        if data in GENRE_PRESETS:
            # Tapping a style always starts (or restarts) the builder, whatever step it was
            # on, or whether it was lost with a restarted kernel.
            keep_lora = ((self.builders.get(chat_id) or {}).get("spec") or {}).get("lora")
            self.builders[chat_id] = {"step": "genre", "spec": {"lang": "en", "quality": "high",
                                                               "instrumental": True, "seconds": 330}}
            if keep_lora:
                self.builders[chat_id]["spec"]["lora"] = keep_lora
            b = self.builders[chat_id]
        if not b:
            self.tg.send(chat_id, "الجلسة دي انتهت. /track بيبدأ تراك جديد.")
            return
        step = b["step"]
        if step == "genre":
            b["spec"]["name"] = b["spec"]["genre"] = data
            b["spec"]["idea"] = GENRE_PRESETS[data] + ". الفكرة: "
            b["step"] = "theme"
            self.tg.send(chat_id, f"{data}. الفكرة أو المود؟ (اكتب بحرية)")
        elif step == "seconds" and data.isdigit():
            b["spec"]["seconds"] = int(data)
            if b.pop("skip_vocals", False):
                b["step"] = "quality"
                self.tg.send(chat_id, "الجودة؟", keyboard=[[{"text": label, "callback_data": "q:" + q}] for q, label in QUALITIES])
                return
            if b.get("built") and b["spec"].get("idea") == b["built"].get("prompt"):
                # the generated prompt carries a structure map, so rebuild it for the
                # length he just picked instead of rendering 7 minutes off a 5:30 map
                b["built"] = build_prompt(b["idea_seed"], int(data), b.get("variant", 0), instrumental=b["spec"].get("instrumental", True))
                b["spec"]["idea"] = b["built"]["prompt"]
            b["step"] = "instrumental"
            self.tg.send(chat_id, "بصوت ولا موسيقى بس؟", keyboard=[[{"text": "موسيقى بس", "callback_data": "v:1"}, {"text": "بكلمات", "callback_data": "v:0"}]])
        elif step == "instrumental" and data.startswith("v:"):
            b["spec"]["instrumental"] = data == "v:1"
            b["step"] = "quality"
            self.tg.send(chat_id, "الجودة؟", keyboard=[[{"text": label, "callback_data": "q:" + q}] for q, label in QUALITIES])
        elif step == "quality" and data.startswith("q:"):
            b["spec"]["quality"] = data[2:]
            self._confirm(chat_id, b)
        elif step == "options" and data == "go":
            # the summary line was the confirmation: Generate starts it
            self.builders.pop(chat_id, None)
            self._enqueue(chat_id, b["spec"])
        elif step == "confirm":
            spec = b["spec"]
            self.builders.pop(chat_id, None)
            if data == "go":
                self._enqueue(chat_id, spec)
            else:
                self.tg.send(chat_id, "اتلغى.")
        else:
            hint = {"theme": "اكتب الفكرة أو المود في رسالة، أو دوس على ستايل تبدأ من الأول.",
                    "mode": "دوس على ستايل، أو بروموبت من عندي، أو الذكاء يكتبه - أو /cancel.",
                    "own_prompt": "ابعت البرومبت في رسالة واحدة، أو /cancel.",
                    "edit_prompt": "ابعت نسختك من البرومبت، أو /cancel.",
                    "ai_idea": "ابعت فكرة قصيرة: النوع، المود، الجو. من غير أسماء مغنيين.",
                    "options": "قول التعديل بصوتك أو كتابة، أو دوس ولّد لما يبقى تمام.",
                    "seconds": "اختار الطول من الأزرار اللي فوق.",
                    "instrumental": "اختار موسيقى بس أو بكلمات من فوق.",
                    "quality": "اختار الجودة من الأزرار اللي فوق."}.get(step, "/track starts a new one.")
            self.tg.send(chat_id, hint)

    def _show_options(self, chat_id, b):
        b["step"] = "options"
        s = b["spec"]
        prompt = (s.get("idea") or "").strip()
        kb = [[{"text": "\u25b6\ufe0f ولّد", "callback_data": "go"},
               {"text": "\U0001f916 اسألني", "callback_data": "ask"}]]
        self.tg.send(chat_id,
                     opt.spec_summary(s) + "\n\n"
                     f"البرومبت: {prompt[:900]}{'...' if len(prompt) > 900 else ''}\n\n"
                     "عايز تغيّر حاجة (الطول، BPM، المقام، بكلمات ولا موسيقى بس، العنوان...)؟ قولها بصوتك أو اكتبها. "
                     "ولو تمام دوس ولّد.\n\n" + ASSIST_HINT,
                     keyboard=kb)

    def _options_text(self, chat_id, b, text):
        """His words on the summary screen: change what he named, show the line again."""
        raw = self.heard_raw.get(chat_id)
        said = text
        if raw and time.time() - raw[1] < 10:
            said = raw[0] + " " + text
        if opt.is_go_word(said):
            self._callback(chat_id, "go")
            return
        ch, notes = opt.parse_spec_edits(said, b["spec"])
        if not ch:
            heard = (" (سمعت: " + raw[0][:150] + ")") if raw and time.time() - raw[1] < 10 else ""
            self.tg.send(chat_id, "ما وصلنيش كويس، ممكن تعيدها؟" + heard + " مثلاً: \"خليها ٤ دقايق\" أو \"بكلمات\" أو \"١٢٠ BPM\". "
                                  "أو دوس ولّد لو تمام.",
                         keyboard=[[{"text": "\u25b6\ufe0f ولّد", "callback_data": "go"},
                                    {"text": "\U0001f916 اسألني", "callback_data": "ask"}]])
            return
        spec = b["spec"]
        for k, v in ch.items():
            if v is None:
                spec.pop(k, None)
            else:
                spec[k] = v
        if ch.get("instrumental"):
            spec.pop("lyrics", None)
        self.tg.send(chat_id, "غيّرت: " + "، ".join(notes) + ".")
        self._show_options(chat_id, b)

    def _option_step(self, chat_id, b, code):
        spec = b["spec"]
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
            self.tg.send(chat_id, "الطول؟", keyboard=self._length_kb())
        else:
            asks = {"lyrics": "ابعت الكلمات مع تاجات [Intro]/[Verse]/[Chorus]. رسالة واحدة.",
                    "tags": "ابعت تاجات ستايل قصيرة، مثلاً 'analog, tape hiss, 90s'.",
                    "excl": "إيه اللي يتجنبه؟ هيتكتب في البرومبت كتجنّب.",
                    "title": "ابعت العنوان.",
                    "key": "ابعت المقام، مثلاً F# minor.",
                    "bpm": "ابعت الـ BPM (٦٠ - ١٨٠).",
                    "steps": "ابعت عدد الخطوات (٤ - ٦٠).",
                    "seed": "ابعت رقم السيد، أو 0 للعشوائي."}
            if code in asks:
                b["step"] = "opt:" + code
                self.tg.send(chat_id, asks[code])
            else:
                self._show_options(chat_id, b)

    def _length_kb(self):
        btns = [{"text": f"{d//60}:{d%60:02d}", "callback_data": str(d)} for d in DURATIONS]
        return [btns[i:i + 2] for i in range(0, len(btns), 2)]

    def _prompt_step(self, chat_id, b, code):
        if code == "ref":
            b["step"] = "ref_wait"
            self.tg.send(chat_id, self.REF_HINT)
        elif code == "audio":
            b["step"] = "own_prompt"
            b.pop("own_ref", None)
            b["want_audio_ref"] = True
            self.tg.send(chat_id, "ابعت التراك أو الـ MP3 اللي عايزه مرجع (لحد ٢٠ ميجا). "
                                  "باخد منه السرعة والمقام والجو كستايل بس، ومبقراش اسمه ولا أي بيانات فيه. "
                                  "بعدها ابعت البرومبت بتاعك.")
        elif code == "own":
            b["step"] = "own_prompt"
            b.pop("own_ref", None)
            b.pop("want_audio_ref", None)
            self.tg.send(chat_id, "ابعت البرومبت في رسالة واحدة. كل اللي محتاجه التراك يتكتب فيها: "
                                  "BPM، المقام، الصوت، الهيكل.\n"
                                  "أي اسم مغني أو تراك حقيقي بيتشال، وبوريك بالظبط إيه اللي اتشال وليه - "
                                  "والباقي زي ما كتبته.\n"
                                  "ولو عايز مرجع للستايل ابعت لينك أو سكرين شوت هنا (قبل البرومبت أو بعده) "
                                  "وهستخدمه مع البرومبت. الاسم مبيدخلش البرومبت أبداً.")
        elif code == "ai":
            b["step"] = "ai_idea"
            self.tg.send(chat_id, "قولي الفكرة في كلمتين: النوع، المود، أي إحساس عايزه. "
                                  "من غير أسماء مغنيين أو تراكات - أنا بكتب البرومبت الكامل من قواعد المكتبة.")
        elif code == "again" and b.get("idea_seed") is not None:
            b["variant"] = b.get("variant", 0) + 1
            b["built"] = build_prompt(b["idea_seed"], b["spec"].get("seconds", 330), b["variant"], instrumental=b["spec"].get("instrumental", True))
            self._show_prompt(chat_id, b)
        elif code == "edit":
            b["step"] = "edit_prompt"
            self.tg.send(chat_id, "ابعت نسختك من البرومبت في رسالة واحدة.")
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
            self.tg.send(chat_id, "دوس بروموبت من عندي أو الذكاء يكتبه، أو /cancel.")

    def _removal_block(self, removed):
        """A marker and the reason, in both languages, whenever something was taken out."""
        if not removed:
            return "\u2705 البرومبت زي ما هو، مفيش حاجة اتشالت.\n\u2705 Nothing removed - the prompt is your words as they are."
        lines = ["\u26a0\ufe0f شيلت من البرومبت / Removed from the prompt:"]
        for span in removed[:4]:
            lines.append(f'- "{span}"')
        lines.append("ليه / why: الأسماء الحقيقية لفنانين أو تراكات ممنوعة في خانة البرومبت. "
                     "الوصف اللي حوالين الاسم فضل زي ما هو.\n"
                     "Real artist or track names never go in the prompt field. The description around the name is kept.")
        return "\n".join(lines)

    def _show_prompt(self, chat_id, b):
        built = b["built"]
        b["step"] = "ai_review"
        note = ""
        if b.get("ref_note"):
            note = b["ref_note"] + "\n\n"
        note += self._removal_block(built.get("removed")) + "\n\n"
        b["removed"] = built.get("removed") or []
        kb = []
        if built.get("removed"):
            kb.append([{"text": "\U0001f50e استخدمه كمرجع", "callback_data": "p:refname"}])
        kb.append([{"text": "\u2705 استخدمه", "callback_data": "p:use"},
                   {"text": "\u270f\ufe0f عدّل", "callback_data": "p:edit"}])
        kb.append([{"text": "\U0001f504 واحد تاني", "callback_data": "p:again"},
                   {"text": "\U0001f50e مرجع جديد", "callback_data": "p:ref"}])
        kb.append([{"text": "\U0001f916 اسألني", "callback_data": "ask"}])
        self.tg.send(chat_id, f"{note}Prompt ({built['bpm']} BPM, {built['key']}, {built['genre']}):\n\n"
                              f"{built['prompt']}\n\n{ASSIST_HINT}", keyboard=kb)

    PROMPT_STEPS = ("mode", "genre", "theme", "own_prompt", "edit_prompt", "ai_idea", "ref_wait")

    def _builder_text(self, chat_id, text):
        b = self.builders[chat_id]
        link = re.search(r"(https?://\S+|www\.\S+)", text or "")
        if link and b["step"] in self.PROMPT_STEPS:
            # a link pasted while writing a prompt is a reference, not prompt text
            self._reference_link(chat_id, link.group(1))
            return
        if b["step"] == "ref_wait":
            m = re.search(r"(https?://\S+|www\.\S+)", text)
            if m:
                self._reference_link(chat_id, m.group(1))
            else:
                self._reference_text(chat_id, text)
            return
        if b["step"] in ("theme", "own_prompt", "edit_prompt", "ai_idea"):
            res = self._english_text(chat_id, text)
            if res is None:
                return
            text, changed = res
            if changed:
                self._say_english(chat_id, text)
        if b["step"] == "options":
            self._options_text(chat_id, b, text)
        elif b["step"] == "theme":
            b["spec"]["idea"] = b["spec"]["idea"] + text
            b["step"] = "seconds"
            self.tg.send(chat_id, "الطول؟", keyboard=self._length_kb())
        elif b["step"] in ("own_prompt", "edit_prompt"):
            clean, removed = clean_idea(text)
            if len(clean) < 8:
                self.tg.send(chat_id, "ده قصير أوي. ابعت البرومبت كامل تاني، أو /cancel.")
                return
            spec = b["spec"]
            spec["idea"] = clean
            ref = b.get("own_ref") if b["step"] == "own_prompt" else None
            ref_style = ref.get("style") if ref else None
            meta = build_prompt(clean, spec.get("seconds", 330), 0, instrumental=spec.get("instrumental", True),
                                style=ref_style if isinstance(ref_style, str) and ref_style in opt.PROMPT_STYLES else None)
            if ref and isinstance(ref_style, str) and ref_style in opt.PROMPT_STYLES:
                st = opt.PROMPT_STYLES[ref_style]
                words = ", ".join(x for x in (st.get("mood"), st.get("sound")) if x)
                if words and words.lower() not in clean.lower():
                    spec["idea"] = clean.rstrip(" .") + ". Style reference: " + words + "."
                spec.setdefault("genre", meta["genre"])
                self.tg.send(chat_id, "استخدمت المرجع مع البرومبت بتاعك (ستايل بس، من غير أي اسم).")
            spec["bpm"], spec["key"] = meta["bpm"], meta["key"]
            spec.setdefault("genre", meta["genre"])
            spec.setdefault("name", meta["genre"])
            b["removed"] = removed
            if removed:
                self.tg.send(chat_id, self._removal_block(removed),
                             keyboard=[[{"text": "\U0001f50e استخدمه كمرجع", "callback_data": "p:refname"}]])
            else:
                self.tg.send(chat_id, self._removal_block([]))
            self._show_options(chat_id, b)
        elif b["step"].startswith("opt:"):
            key = b["step"].split(":", 1)[1]
            key = {"excl": "exclude", "tags": "style_tags"}.get(key, key)
            spec = b["spec"]
            raw = (text or "").strip()
            if key in ("bpm", "steps", "seed"):
                if not raw.isdigit():
                    self.tg.send(chat_id, "ابعت رقم، أو /cancel.")
                    return
                spec[key] = int(raw) if not (key == "seed" and raw == "0") else None
            else:
                spec[key] = raw
            self._show_options(chat_id, b)
        elif b["step"] == "ai_idea":
            b["idea_seed"] = text
            b["variant"] = 0
            b["built"] = build_prompt(text, b["spec"].get("seconds", 330), 0, instrumental=b["spec"].get("instrumental", True))
            self._show_prompt(chat_id, b)

    def _confirm(self, chat_id, b):
        b["step"] = "confirm"
        s = b["spec"]
        prompt = s.get("idea") or ""
        tail = f"\n\nPrompt: {prompt[:900]}{'...' if len(prompt) > 900 else ''}" if prompt else ""
        self.tg.send(chat_id,
            f"Ready: {s.get('genre')} | {s.get('seconds')}s | "
            f"{'instrumental' if s.get('instrumental') else 'lyrics'} | {s.get('quality', 'standard')}"
            + (f" | العنوان: {s['title']}" if s.get("title") else "") + tail
            + "\n\n" + ASSIST_HINT,
            keyboard=[[{"text": "ولّد", "callback_data": "go"}, {"text": "إلغاء", "callback_data": "no"}],
                      [{"text": "\U0001f916 اسألني", "callback_data": "ask"}]])

    def _track(self, chat_id, arg):
        if arg and arg.strip().lower() in ("again", "last", "same"):
            self._start_from_last(chat_id)
            return
        if arg:
            spec = self._parse_spec(arg)
            if spec:
                self._enqueue(chat_id, spec)
                return
        self.builders[chat_id] = {"step": "mode", "spec": {"lang": "en", "quality": "high",
                                                           "instrumental": True, "seconds": 330}}
        self._track_menu(chat_id)

    def _lora_names(self):
        """Adapters that really exist on the engine side. Empty until Mr Dorgham is trained."""
        try:
            glob = getattr(self.make_track, "__globals__", {}) or {}
            return list((glob.get("LORA_ADAPTERS") or {}).keys())
        except Exception:
            return []

    def _track_menu(self, chat_id):
        b = self.builders.get(chat_id) or {}
        first = [{"text": "\u270d\ufe0f بروموبت من عندي", "callback_data": "p:own"}]
        if opt.audio_available():
            first.append({"text": "\U0001f3a7 ارفع تراك/MP3 كمرجع", "callback_data": "p:audio"})
        kb = [first]
        second = [{"text": "\u2728 الذكاء يكتبه", "callback_data": "p:ai"}]
        names = self._lora_names()
        if names:
            on = (b.get("spec") or {}).get("lora") in names
            second.append({"text": ("\U0001f9ec الدرغام: شغال \u2705" if on else "\U0001f9ec استخدم الدرغام"),
                           "callback_data": "lora:t"})
        kb.append(second)
        kb += [[{"text": g, "callback_data": g}] for g in GENRE_PRESETS]
        self.tg.send(chat_id, "تراك جديد. اختار ستايل، أو اكتب البرومبت بنفسك، "
                              "أو سيبني أكتبه من فكرة قصيرة.\n" + ASSIST_HINT, keyboard=kb)

    def _lora_toggle(self, chat_id):
        names = self._lora_names()
        b = self.builders.get(chat_id)
        if not names or not b:
            self.tg.send(chat_id, "الدرغام لسه مش جاهز. أول ما التدريب يخلص هيظهر الزرار.")
            return
        sp = b["spec"]
        if sp.get("lora") in names:
            sp.pop("lora", None)
        else:
            sp["lora"] = names[0]
        self._track_menu(chat_id)

    def _audio_ref_wanted(self, chat_id):
        b = self.builders.get(chat_id) or {}
        return bool(b.get("want_audio_ref")) and b.get("step") in self.PROMPT_STEPS

    def _reference_audio(self, chat_id, msg):
        f = msg.get("audio") or msg.get("document") or {}
        b = self.builders.get(chat_id)
        if int(f.get("file_size") or 0) > 20 * 1024 * 1024:
            self.tg.send(chat_id, "الملف أكبر من ٢٠ ميجا، تيليجرام مبيسمحش للبوت ينزّله. ابعت نسخة MP3 أصغر.")
            return
        try:
            data = self._download_file(f["file_id"])
        except Exception as e:
            self.tg.send(chat_id, f"معرفتش أنزّل الملف ده: {str(e)[:120]}")
            return
        path = os.path.join(self.work, "audio_reference.bin")   # the name he gave it is never used
        try:
            with open(path, "wb") as fh:
                fh.write(data)
            res = opt.audio_analyze(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        if not res:
            self.tg.send(chat_id, "معرفتش أقرا الملف ده كصوت (أو هو أقصر من ٨ ثواني). جرب MP3 تاني، أو ابعت لينك أو سكرين شوت.")
            return
        style = opt.audio_style_for(res, opt.PROMPT_STYLES)
        self.tg.send(chat_id, opt.audio_describe(res) + "\nباخده كستايل بس، مفيش اسم ولا حاجة من الأغنية بتدخل البرومبت.")
        b = self.builders.get(chat_id)
        b.pop("want_audio_ref", None)
        label = opt.PROMPT_STYLES[style].get("label", style)
        if b.get("step") == "own_prompt":
            b["own_ref"] = {"style": style, "theme": ""}
            self.tg.send(chat_id, f"خدت المرجع كستايل ({label}). ابعت البرومبت بتاعك دلوقتي وهستخدمهم مع بعض.")
            return
        built = build_prompt("", b["spec"].get("seconds", 330), 0,
                             instrumental=b["spec"].get("instrumental", True), style=style)
        b["built"] = built
        b["ref_note"] = "فهمت من المرجع: " + built["summary"]
        self._show_prompt(chat_id, b)

    def _parse_spec(self, arg):
        # "melodic techno, night drive, 330s, instrumental, high, key Am, bpm 122, title X"
        parts = [p.strip() for p in arg.split(",") if p.strip()]
        if not parts:
            return None
        genre = parts[0]
        preset = GENRE_PRESETS.get(genre) or GENRE_PRESETS.get(genre.title())
        spec = {"name": genre, "genre": genre, "lang": "en", "quality": "standard",
                "instrumental": True, "seconds": 330,
                "idea": (preset or genre) + (". الفكرة: " + parts[1] if len(parts) > 1 else "")}
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
                if ". الفكرة: " not in spec["idea"]:
                    spec["idea"] += ". الفكرة: " + p
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
            self.tg.send(chat_id, "مفيش موديل شغال في الجلسة دي. شغّل خلية الموديل في النوتبوك الأول.")
            return
        try:
            self.last_enq[chat_id] = {k: v for k, v in dict(spec).items() if not str(k).startswith("_")}
        except Exception:
            pass
        spec = self._normalize_spec(spec)
        self._remember(spec)
        spec["_thread"] = self.threads.get(chat_id)
        self.jobs.put((chat_id, spec))
        self.queued.append(spec.get("title") or spec.get("name") or spec.get("genre") or "track")
        n = self.jobs.qsize()
        self.tg.send(chat_id, f"اتحط في الطابور: {spec.get('title') or spec.get('name') or spec['genre']} ({spec['seconds']} ثانية، {spec.get('quality','standard')})." + (f" {n-1} قبله." if n > 1 and not self.current else ""))

    def _batch_text(self, chat_id, arg):
        if not arg:
            self.tg.send(chat_id, "ابعت القايمة JSON بعد /batch، أو كملف .json. كل عنصر: {\"title\":..., \"genre\":..., \"seconds\":..., \"instrumental\":true/false, \"quality\":\"high|standard|fast\", \"idea\":...}")
            return
        self._batch_load(chat_id, arg)

    def _batch_doc(self, chat_id, doc):
        try:
            f = self.tg.call("getFile", file_id=doc["file_id"])
            url = FILE_API.format(token=self.tg.token, path=f["file_path"])
            with urllib.request.urlopen(url, timeout=60) as r:
                self._batch_load(chat_id, r.read().decode())
        except Exception as e:
            self.tg.send(chat_id, f"معرفتش أقرا الملف ده: {str(e)[:200]}")

    def _batch_load(self, chat_id, raw):
        try:
            items = json.loads(raw)
            if isinstance(items, dict):
                items = [items]
            specs = [s for s in items if isinstance(s, dict) and (s.get("genre") or s.get("name"))]
            if not specs:
                raise ValueError("no valid specs")
        except Exception as e:
            self.tg.send(chat_id, f"الـ JSON ده معرفتش أفهمه كتراكات: {str(e)[:200]}")
            return
        for s in specs:
            s = self._normalize_spec(s)
            s.setdefault("idea", s.get("genre", ""))
            s.setdefault("lang", "en")
            self.jobs.put((chat_id, s))
            self.queued.append(s.get("title") or s.get("name") or s.get("genre") or "track")
        self.tg.send(chat_id, f"الطابور اتحط: {len(specs)} تراك في الطابور. هيتعملوا ورا بعض وهيوصلوا هنا أول بأول.")

    def _status(self, chat_id):
        """Plain Egyptian Arabic: what is happening now, what is waiting, and the one
        thing he has to do before the session ends. The technical lines live in /diag."""
        lines = []
        if self.current:
            lines.append("بيرندر دلوقتي: " + self.current)
        else:
            lines.append("مفيش حاجة بتترندر دلوقتي - البوت جاهز")
        waiting = self.jobs.qsize()
        lines.append("مستني في الطابور: " + ("مفيش" if not waiting else str(waiting)))
        if not self.make_track:
            lines.append("الرندر واقف لحد ما خلية الإنجين تشتغل في النوتبوك، وبعدها خلية البوت")
        if str(self.out_root).startswith("/kaggle"):
            lines.append("التراكات بتتحفظ في Output النوتبوك، فاعمل Save Version قبل ما الجلسة تقفل.")
        else:
            lines.append("التراكات بتتحفظ على Drive في مجلد Zi_Music.")
        try:
            state = self._snapshot()
            lines.append(ziassist.dataset_line(state))
        except Exception:
            pass
        self.tg.send(chat_id, "\n".join(lines))

    def _queue(self, chat_id):
        q = list(self.queued)
        msg = ["بيتعمل دلوقتي: " + (self.current or "nothing")]
        if q:
            msg.append(f"مستني ({len(q)}):")
            for i, t in enumerate(q[:10], 1):
                msg.append(f"{i}. {t}")
            if len(q) > 10:
                msg.append(f"...and {len(q) - 10} more")
        else:
            msg.append("مفيش حاجة مستنية. /track بيبدأ تراك جديد.")
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
                 f"users recorded: {len(self.users)}, private sync: {self.sync_status}",
                 f"messages handled: {self.stats.get('message', 0)}",
                 f"callbacks handled: {self.stats.get('callback', 0)}",
                 f"last update: {self.stats.get('last', '?')}"]
        try:
            lines.append(f"pollers in this process: {len(_bot_instances())}")
        except Exception:
            pass
        lines.append(f"threads known: {len(self.threads)}")
        lines.append(f"outputs: {self.out_root}")
        lines.append("engine: " + ("ready" if self.make_track else "not loaded"))
        lines.append("owner: " + ("paired" if self.owner else "not paired yet"))
        try:
            e = voice.engines()
            on = ", ".join(k for k, v in e.items() if v)
            lines.append("voice out: " + (on or "none - text only"))
        except Exception:
            pass
        self._llm()
        lines.append("screenshots: " + ("vision" if (self.llm_key or self.groq_key) else "no key"))
        lines.append("chat model: " + ("groq" if self.groq_key else "no groq key") + " / " + ("gemini" if self.llm_key else "no gemini key"))
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
        folders = self._release_folders()[:60]
        working = []
        if self.current:
            working.append("شغال دلوقتي: " + str(self.current)[:60])
        if self.jobs.qsize():
            working.append(f"مستني في الطابور: {self.jobs.qsize()}")
        if not folders:
            self.tg.send(chat_id, "المكتبة فاضية لسه. " + ("\n".join(working) + "\n" if working else "")
                         + "دوس تراك جديد وهتلاقي كل حاجة هنا.")
            return
        tracks = self._liked().get("tracks", {})
        kb = []
        for f in folders:
            key = self._lib_key(f)
            star = "\u2b50 " if (tracks.get(key) or {}).get("kept") else ""
            name = re.sub(r"^\d{8}-\d{6}_", "", f).replace("_", " ")
            kb.append([{"text": (star + name)[:60], "callback_data": "lib:" + key}])
        head = "المكتبة: كل تراكاتك هنا (\u2b50 = اللي اخترته). دوس على تراك يتفتح وتنشره من جواه."
        if working:
            head += "\n" + "\n".join(working)
        self.tg.send(chat_id, head, keyboard=kb)

    def _get(self, chat_id, needle, audio=True):
        folder = self._find_folder(needle)
        if not folder:
            self.tg.send(chat_id, "مفيش حاجة بالاسم ده. /library بيعرض التراكات.")
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
                self.tg.send(chat_id, "مفيش غلاف في الفولدر ده.")
            return
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        r = {"base": base or os.path.join(folder, title.replace(" ", "_")),
             "folder": folder, "title": meta.get("title", title)}
        if base is None:
            self.tg.send(chat_id, "الفولدر ده مفيهوش MP3 لسه.")
            return
        self._deliver(chat_id, r)

    def _routenote(self, chat_id, needle):
        folder = self._find_folder(needle)
        if not folder:
            self.tg.send(chat_id, "مفيش حاجة بالاسم ده. /library بيعرض التراكات.")
            return
        p = os.path.join(folder, "routenote_form.txt")
        if not os.path.exists(p):
            self.tg.send(chat_id, "مفيش نص فورم RouteNote في الفولدر ده.")
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

    # ---------- animated YouTube video and artwork ----------
    VIZ_SUFFIX = "_youtube_viz_16x9.mp4"

    @staticmethod
    def _viz_filter():
        # blurred, darkened cover as the backdrop; the cover whole in the middle; a live
        # waveform under it and spectrum bars rising from the bottom, both from the audio
        return ("[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
                "boxblur=30:3,eq=brightness=-0.12:saturation=1.3[bg];"
                "[0:v]scale=440:440,format=rgba[art];"
                "[1:a]asplit=2[a1][a2];"
                "[a1]showwaves=s=1280x110:mode=cline:rate=20:colors=0xE8D9FF@0.9,format=rgba[wv];"
                "[a2]showfreqs=s=1280x150:mode=bar:fscale=log:colors=0xB48CFF@0.8,format=rgba[fq];"
                "[bg][art]overlay=(W-w)/2:60:format=auto[b1];"
                "[b1][wv]overlay=0:H-h-170:format=auto[b2];"
                "[b2][fq]overlay=0:H-h:format=auto,format=yuv420p[out]")

    def _make_viz(self, folder):
        """Animated video as long as the track: audio-reactive, built from cover + audio."""
        audio = self._release_audio(folder)
        cover = os.path.join(folder, "cover_3000x3000.jpg")
        if not audio or not os.path.exists(cover):
            return None
        stem = os.path.basename(audio)
        for suffix in ("_320kbps.mp3", "_preview_128k.mp3"):
            if stem.endswith(suffix):
                stem = stem[:-len(suffix)]
        out = os.path.join(folder, stem + self.VIZ_SUFFIX)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
        args = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "20", "-i", cover,
                "-i", audio, "-filter_complex", self._viz_filter(),
                "-map", "[out]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                "-r", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out + ".part"]
        try:
            self._run_ffmpeg(args, timeout=3600)
            os.replace(out + ".part", out)
        except Exception as e:
            print("viz render failed:", type(e).__name__, str(e)[:120])
            try:
                os.remove(out + ".part")
            except Exception:
                pass
            return None
        return out if os.path.exists(out) and os.path.getsize(out) > 0 else None

    def _viz_path(self, folder):
        try:
            for n in os.listdir(folder):
                if n.endswith(self.VIZ_SUFFIX):
                    return os.path.join(folder, n)
        except Exception:
            pass
        return None

    @staticmethod
    def _visual_kb(key):
        return [[{"text": "\U0001f3a8 \u0623\u0631\u062a \u0648\u0631\u0643 \u0644\u0644\u062a\u0631\u0627\u0643", "callback_data": f"art:{key}"},
                 {"text": "\U0001f3ac \u0641\u064a\u062f\u064a\u0648 \u064a\u0648\u062a\u064a\u0648\u0628", "callback_data": f"vid:{key}"}],
                [{"text": "\U0001f4e3 \u0627\u0646\u0634\u0631", "callback_data": f"pubmenu:{key}"}]]

    def _mood_text(self, folder):
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        bits = [str(meta.get(k) or "") for k in ("genre", "idea", "prompt", "caption")]
        return " ".join(bits)[:600]

    def _visual_cb(self, chat_id, data):
        kind, _, rest = data.partition(":")
        parts = rest.split(":")
        key = parts[0]
        name = self._lib_folder(key)
        folder = os.path.join(self.out_root, name) if name else None
        if not folder:
            self.tg.send(chat_id, "\u0627\u0644\u062a\u0631\u0627\u0643 \u062f\u0647 \u0645\u0634 \u0645\u0648\u062c\u0648\u062f \u0639\u0644\u0649 \u0627\u0644\u062c\u0647\u0627\u0632 \u0627\u0644\u0644\u064a \u0634\u063a\u0627\u0644 \u062f\u0644\u0648\u0642\u062a\u064a. "
                                  "\u062f\u0648\u0633 \u0627\u0644\u0632\u0631\u0627\u0631 \u0645\u0646 \u062a\u062d\u062a \u062a\u0631\u0627\u0643 \u0623\u062d\u062f\u062b\u060c \u0623\u0648 /library.")
            return
        title = self._publish_caption(folder)[0]
        if kind == "art":
            self._art_options(chat_id, key, folder, more=(len(parts) > 1 and parts[1] == "more"))
        elif kind == "artpick":
            self._art_pick(chat_id, key, folder, int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0)
        elif kind == "vid":
            threading.Thread(target=self._video_job, args=(chat_id, key, folder, title), daemon=True).start()
        elif kind == "vidyt":
            head, desc, tags = self._yt_metadata(folder, title, self._publish_caption(folder)[1])
            self.tg.send(chat_id, "\u0643\u0644 \u062d\u0627\u062c\u0629 \u0627\u062a\u0645\u0644\u062a \u062a\u0644\u0642\u0627\u0626\u064a (public):\n\n" + head + "\n\n" + desc[:2500] +
                         "\n\nTags: " + ", ".join(tags[:12]) + "\n\n\u0645\u062a\u0623\u0643\u062f\u061f",
                         keyboard=[[{"text": "\u2705 \u0623\u064a\u0648\u0647\u060c \u0627\u0631\u0641\u0639", "callback_data": f"vidytok:{key}"},
                                    {"text": "\u274c \u0644\u0623", "callback_data": "menu"}]])
        elif kind == "vidytok":
            try:
                url = self._youtube_upload(folder, title, self._publish_caption(folder)[1])
                self.tg.send(chat_id, "YouTube: اتنشر - " + url)
            except Exception as e:
                self.tg.send(chat_id, "\u0645\u0627\u0642\u062f\u0631\u062a\u0634 \u0623\u0631\u0641\u0639 \u0639\u0644\u0649 \u064a\u0648\u062a\u064a\u0648\u0628: " + f"{type(e).__name__}: {str(e)[:160]}")

    def _video_job(self, chat_id, key, folder, title):
        self.tg.send(chat_id, "\u0628\u062c\u0647\u0632 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u0628\u0646\u0641\u0633 \u0637\u0648\u0644 \u0627\u0644\u062a\u0631\u0627\u0643 (\u0645\u0645\u0643\u0646 \u064a\u0627\u062e\u062f \u0645\u0646 \u0662 \u0644\u0640 \u0661\u0660 \u062f\u0642\u0627\u064a\u0642 \u062d\u0633\u0628 \u0627\u0644\u0637\u0648\u0644). \u0647\u0628\u0639\u062a\u0644\u0643 \u0644\u0645\u0627 \u064a\u062e\u0644\u0635.")
        vid = self._make_viz(folder)
        if not vid:
            self.tg.send(chat_id, "\u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u0645\u0627\u0627\u062a\u0639\u0645\u0644\u0634: \u0645\u0634 \u0644\u0627\u0642\u064a \u0643\u0627\u0641\u0631 \u0623\u0648 \u0635\u0648\u062a \u0641\u064a \u0627\u0644\u0645\u062c\u0644\u062f\u060c \u0623\u0648 \u062d\u0635\u0644\u062a \u0645\u0634\u0643\u0644\u0629 \u0641\u064a \u0627\u0644\u0631\u0646\u062f\u0631.")
            return
        mb = os.path.getsize(vid) / 1048576
        sent = False
        if os.path.getsize(vid) < TG_LIMIT:
            try:
                self.tg._upload("sendVideo", chat_id, "video", vid, caption=title)
                sent = True
            except Exception as e:
                print("viz send failed:", type(e).__name__)
        self.tg.send(chat_id, ("\u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u062c\u0627\u0647\u0632" if sent else f"\u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u062c\u0627\u0647\u0632 \u0648\u0645\u062d\u0641\u0648\u0638 ({mb:.0f} MB \u0643\u062a\u064a\u0631 \u0639\u0644\u0649 \u062a\u0644\u064a\u062c\u0631\u0627\u0645)")
                     + f": {os.path.basename(vid)}\n\u0647\u0648 \u0645\u062d\u0641\u0648\u0638 \u0641\u064a \u0645\u062c\u0644\u062f \u0627\u0644\u062a\u0631\u0627\u0643. \u0627\u0644\u0631\u0641\u0639 \u0639\u0644\u0649 \u064a\u0648\u062a\u064a\u0648\u0628 \u0645\u0634 \u0647\u064a\u062d\u0635\u0644 \u063a\u064a\u0631 \u0644\u0645\u0627 \u062a\u0636\u063a\u0637 \u0639\u0644\u0649 \u0627\u0644\u0632\u0631\u0627\u0631.",
                     keyboard=[[{"text": "\u25b6\ufe0f \u0627\u0631\u0641\u0639 \u0639\u0644\u0649 \u064a\u0648\u062a\u064a\u0648\u0628", "callback_data": f"vidyt:{key}"}],
                               [{"text": "\U0001f3a8 \u063a\u064a\u0651\u0631 \u0627\u0644\u0623\u0631\u062a \u0648\u0631\u0643", "callback_data": f"art:{key}"}]])

    def _art_dir(self, folder):
        d = os.path.join(folder, "_art_options")
        os.makedirs(d, exist_ok=True)
        return d

    def _art_options(self, chat_id, key, folder, more=False):
        text = self._mood_text(folder)
        seed_file = os.path.join(self._art_dir(folder), "seed.txt")
        try:
            seed = int(open(seed_file).read()) + (10 if more else 0) if os.path.exists(seed_file) else 0
        except Exception:
            seed = 0
        if not os.path.exists(seed_file) or more:
            seed = seed or (int(hashlib.md5(folder.encode()).hexdigest()[:6], 16) % 100000)
        open(seed_file, "w").write(str(seed))
        self.tg.send(chat_id, "\u0628\u0631\u0633\u0645 \u0623\u0631\u0628\u0639 \u0623\u0634\u0643\u0627\u0644 \u0639\u0644\u0649 \u0645\u0632\u0627\u062c \u0627\u0644\u062a\u0631\u0627\u0643...")
        try:
            opts = art.options(text, seed, 1500)
        except Exception as e:
            self.tg.send(chat_id, "\u0645\u0627\u0642\u062f\u0631\u062a\u0634 \u0623\u0631\u0633\u0645: " + f"{type(e).__name__}: {str(e)[:120]}")
            return
        d = self._art_dir(folder)
        for i, (look, sd, img) in enumerate(opts):
            path = os.path.join(d, f"opt{i}.jpg")
            img.save(path, quality=90)
            try:
                self.tg.photo(chat_id, path, caption=f"{i + 1}")
            except Exception as e:
                print("art send failed:", type(e).__name__)
        self.tg.send(chat_id, "\u0627\u062e\u062a\u0627\u0631 \u0627\u0644\u0634\u0643\u0644 \u0627\u0644\u0644\u064a \u0639\u0627\u062c\u0628\u0643. \u0647\u064a\u0628\u0642\u0649 \u0643\u0627\u0641\u0631 \u0627\u0644\u062a\u0631\u0627\u0643 \u0648\u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u0647\u064a\u062a\u0628\u0646\u064a \u0645\u0646\u0647.",
                     keyboard=[[{"text": str(i + 1), "callback_data": f"artpick:{key}:{i}"} for i in range(len(opts))],
                               [{"text": "\U0001f504 \u0623\u0634\u0643\u0627\u0644 \u062a\u0627\u0646\u064a\u0629", "callback_data": f"art:{key}:more"}]])

    def _art_pick(self, chat_id, key, folder, i):
        src = os.path.join(self._art_dir(folder), f"opt{i}.jpg")
        cover = os.path.join(folder, "cover_3000x3000.jpg")
        if not os.path.exists(src):
            self.tg.send(chat_id, "\u0627\u0644\u0634\u0643\u0644 \u062f\u0647 \u0645\u0634 \u0645\u0648\u062c\u0648\u062f\u060c \u062f\u0648\u0633 \u0623\u0631\u062a \u0648\u0631\u0643 \u062a\u0627\u0646\u064a.")
            return
        from PIL import Image
        keep = os.path.join(folder, "cover_original.jpg")
        if os.path.exists(cover) and not os.path.exists(keep):
            shutil.copy2(cover, keep)
        Image.open(src).convert("RGB").resize((3000, 3000), Image.LANCZOS).save(cover, quality=92)
        # a video built from the old cover would be stale
        for n in os.listdir(folder):
            if n.endswith(("_youtube_viz_16x9.mp4", "_youtube_16x9.mp4", "_reel_9x16.mp4")):
                try:
                    os.remove(os.path.join(folder, n))
                except Exception:
                    pass
        self.tg.send(chat_id, "\u0627\u062a\u0639\u0645\u0644 \u0643\u0627\u0641\u0631 \u0627\u0644\u062a\u0631\u0627\u0643 (\u0627\u0644\u0642\u062f\u064a\u0645 \u0645\u062d\u0641\u0648\u0638 \u0643\u0640 cover_original.jpg). \u0639\u0627\u064a\u0632 \u0623\u0639\u0645\u0644 \u0627\u0644\u0641\u064a\u062f\u064a\u0648\u061f",
                     keyboard=[[{"text": "\U0001f3ac \u0641\u064a\u062f\u064a\u0648 \u064a\u0648\u062a\u064a\u0648\u0628", "callback_data": f"vid:{key}"}]])

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

    @staticmethod
    def _mmss(sec):
        sec = int(sec)
        return f"{sec // 60}:{sec % 60:02d}"

    def _yt_metadata(self, folder, title, caption):
        """Everything YouTube asks for, filled in from the release: nothing to type.

        Names are cleaned out of every free-text field, so no real artist or track name
        can reach the title, description or tags.
        """
        meta = self._load(os.path.join(folder, "metadata.json"), {})
        genre = str(meta.get("genre") or "").strip()
        # free text can carry a real name, so the mood is only ever picked from a fixed
        # list of mood words, never copied from what he typed
        src = " ".join(str(meta.get(k) or "") for k in ("idea", "prompt", "caption")).lower()
        mood = ", ".join(w for w in MOOD_WORDS if re.search(r"\b" + w + r"\b", src))[:120]
        bpm, key = meta.get("bpm"), meta.get("key") or meta.get("keyscale")
        dur = meta.get("actual_duration_sec")
        head = f"{title} - Rahal"
        if genre:
            head += f" | {genre}"
        head = head[:100]
        lines = [f"{title} by Rahal.", "", AI_LABEL_YT, ""]
        facts = []
        if genre:
            facts.append(f"Genre: {genre}")
        if mood:
            facts.append(f"Mood: {mood}")
        if bpm:
            facts.append(f"Tempo: {bpm} BPM")
        if key:
            facts.append(f"Key: {key}")
        if dur:
            try:
                facts.append(f"Length: {self._mmss(float(dur))}")
            except Exception:
                pass
        lines += facts + [""]
        secs = meta.get("sections")
        if isinstance(secs, list) and len(secs) >= 3:
            ch = [f"{self._mmss(x.get('start', 0))} {x.get('name', '')}".strip() for x in secs
                  if isinstance(x, dict)]
            if ch and ch[0].startswith("0:00"):
                lines += ["Chapters:"] + ch + [""]
        lines += ["Credits:", "Music: Rahal (direction and selection), generated with ACE-Step 1.5 (MIT licence).",
                  "Visuals: made automatically from the track and its cover.", ""]
        lines += ["Follow Rahal:"] + [url for _n, url in SOCIAL] + [""]
        lines += [PUBLISH_TAGS]
        words = [w.strip().lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9 \-]+", genre.replace(",", " , ") + " , " + mood)]
        tags = []
        for t in ["Rahal", "AI generated music", "ACE-Step"] + words + PUBLISH_TAGS.replace("#", "").split():
            t = t.strip()
            if t and t.lower() not in [x.lower() for x in tags] and sum(len(x) + 1 for x in tags) + len(t) < 450:
                tags.append(t)
        return head, "\n".join(lines), tags

    def _youtube_upload(self, folder, title, caption):
        """Upload the 16:9 visual of a release to YouTube. Returns the watch URL."""
        tok = self._yt_token()
        if not tok:
            raise RuntimeError("لسه مفيش youtube_token.json (ربط جوجل كلاود لسه بيتظبط)")
        video = self._viz_path(folder) or self._make_video(folder, "16x9")
        if not video:
            raise RuntimeError("مفيش فيديو يترفع (مفيش غلاف أو صوت في فولدر التراك)")
        access = self._yt_access_token(tok)
        title, description, tags = self._yt_metadata(folder, title, caption)
        body = {"snippet": {"title": title[:100],
                            "description": description[:4900],
                            "tags": tags,
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

    def _menu(self, chat_id):
        def B(t, d):
            return {"text": t, "callback_data": d}
        kb = [[B("\U0001f3b5 \u062a\u0631\u0627\u0643 \u062c\u062f\u064a\u062f", "menu:track"), B("\U0001f4da \u0627\u0644\u0645\u0643\u062a\u0628\u0629", "menu:library")],
              [B("\u270d\ufe0f \u0628\u0631\u0648\u0645\u0628\u062a \u0645\u0646 \u0639\u0646\u062f\u064a", "menu:own"), B("\u2728 \u0627\u0644\u0630\u0643\u0627\u0621 \u064a\u0643\u062a\u0628\u0647", "menu:ai")],
              [B("\U0001f310 \u0644\u064a\u0646\u0643\u0627\u062a \u0627\u0644\u0633\u0648\u0634\u064a\u0627\u0644", "menu:social"), B("\U0001f9ec \u0627\u0644\u062f\u0631\u063a\u0627\u0645", "menu:dataset")],
              [B("\U0001f9fe \u0641\u0648\u0631\u0645 RouteNote", "menu:routenote"), B("\u2699\ufe0f \u062d\u0627\u062c\u0627\u062a \u062a\u0627\u0646\u064a\u0629", "menu:more")],
              [{"text": "\U0001f39b \u0627\u0644\u0633\u062a\u0648\u062f\u064a\u0648 (\u0627\u0644\u0648\u064a\u0628)", "url": STUDIO_URL}]]
        self.tg.send(chat_id, "\u0627\u0644\u0642\u0627\u0626\u0645\u0629. \u0643\u0644 \u062d\u0627\u062c\u0629 \u0627\u0644\u0628\u0648\u062a \u0628\u064a\u0639\u0645\u0644\u0647\u0627 \u0628\u0636\u063a\u0637\u0629 \u0645\u0646 \u0647\u0646\u0627.", keyboard=kb)

    def _menu_step(self, chat_id, what):
        if what == "track":
            self._track(chat_id, "")
        elif what == "own":
            self._track(chat_id, "")
            self._prompt_step(chat_id, self.builders[chat_id], "own")
        elif what == "ai":
            self._track(chat_id, "")
            self._prompt_step(chat_id, self.builders[chat_id], "ai")
        elif what == "library":
            self._library(chat_id)
        elif what == "more":
            self.tg.send(chat_id, "حاجات تانية:", keyboard=[
                [{"text": "\U0001f4ca \u0627\u0644\u062d\u0627\u0644\u0629", "callback_data": "menu:status"},
                 {"text": "\U0001f6e0 \u062a\u0634\u062e\u064a\u0635", "callback_data": "menu:diag"}],
                [{"text": "\U0001f916 \u0627\u0644\u0645\u0633\u0627\u0639\u062f", "callback_data": "menu:assistant"},
                 {"text": "\u2753 \u0645\u0633\u0627\u0639\u062f\u0629", "callback_data": "menu:help"}],
                [{"text": "\u2630 \u0627\u0644\u0642\u0627\u0626\u0645\u0629", "callback_data": "menu"}]])
        elif what == "publish":
            self._publish_cmd(chat_id, "")
        elif what == "social":
            self._social(chat_id)
        elif what == "assistant":
            self._ask(chat_id, "")
        elif what == "dataset":
            self._dataset(chat_id)
        elif what == "status":
            self._status(chat_id)
        elif what == "routenote":
            self.tg.send(chat_id, "أنهي تراك؟ /routenote <العنوان>")
        elif what == "diag":
            self._diag(chat_id)
        else:
            self.tg.send(chat_id, HELP, keyboard=[[{"text": "\u2630 \u0627\u0644\u0642\u0627\u0626\u0645\u0629", "callback_data": "menu"}]])

    def _social(self, chat_id):
        btns = [{"text": name, "url": url} for name, url in SOCIAL]
        btns.append({"text": "\U0001f4d8 \u0635\u0641\u062d\u0629 \u0641\u064a\u0633\u0628\u0648\u0643 (\u0647\u062a\u062a\u0636\u0627\u0641)", "callback_data": "social:fb"})
        kb = [btns[i:i + 2] for i in range(0, len(btns), 2)]
        self.tg.send(chat_id, "راهال في كل مكان:" if kb else
                     "مفيش لينكات بروفايل مؤكدة لسه.", keyboard=kb or None)

    def _register_commands(self):
        """Keep the Telegram command menu in step with the code."""
        try:
            self.tg.call("setMyCommands", commands=json.dumps(
                [{"command": c, "description": d} for c, d in COMMANDS]))
        except Exception as e:
            print("setMyCommands failed:", repr(e))
        # the corner button is the native Menu (the command list), not the Studio web app;
        # Studio stays inside the menu and on the keyboard, so one corner button serves both
        try:
            self.tg.call("setChatMenuButton", menu_button=json.dumps({"type": "commands"}))
        except Exception as e:
            print("setChatMenuButton failed:", repr(e))
        # a BotFather menu button can keep winning over the default, so set it for the
        # owner's own chat too: a per-chat button always applies
        if self.owner:
            try:
                self.tg.call("setChatMenuButton", chat_id=self.owner,
                             menu_button=json.dumps({"type": "commands"}))
            except Exception as e:
                print("setChatMenuButton (owner chat) failed:", repr(e))

    def _publish_menu(self, chat_id, folder, title=None):
        key = self._lib_key(os.path.basename(folder))
        title = title or self._publish_caption(folder)[0]
        kb = [[{"text": PLATFORM_LABEL[c], "callback_data": f"pub:{c}:{key}"} for c in ("yt", "ig")],
              [{"text": PLATFORM_LABEL[c], "callback_data": f"pub:{c}:{key}"} for c in ("tt", "tg")],
              [{"text": "\U0001f4d8 \u0641\u064a\u0633\u0628\u0648\u0643 (\u064a\u062f\u0648\u064a)", "callback_data": f"pub:fb:{key}"},
               {"text": "\U0001f680 \u0627\u0644\u0643\u0644", "callback_data": f"pub:all:{key}"}],
              [{"text": "\u2b50 \u062f\u0647 \u0627\u0644\u062a\u0631\u0627\u0643 \u0627\u0644\u0645\u0637\u0644\u0648\u0628", "callback_data": f"keep:{key}"}],
              [{"text": "\U0001f3a8 \u0623\u0631\u062a\u0648\u0631\u0643", "callback_data": f"art:{key}"},
               {"text": "\U0001f3ac \u0641\u064a\u062f\u064a\u0648 YouTube", "callback_data": f"vid:{key}"}],
              [{"text": "\u2630 \u0627\u0644\u0642\u0627\u0626\u0645\u0629", "callback_data": "menu"}]]
        self.tg.send(chat_id, f"عايز تنشر {title}؟\n"
                              "الضغطة بتنشر على المنصة اللي دست عليها بس، مرة واحدة.", keyboard=kb)

    def _approve_menu(self, chat_id, folder, title=None):
        """Right after a render: listen first. Cover, video and publishing come after he approves."""
        key = self._lib_key(os.path.basename(folder))
        title = title or self._publish_caption(folder)[0]
        self.tg.send(chat_id, f"{title} جاهز. اسمعه، ولو هو ده دوس \u2b50 وأطلعلك الغلاف والفيديو والنشر.",
                     keyboard=[[{"text": "\u2b50 \u062f\u0647 \u0627\u0644\u062a\u0631\u0627\u0643 \u0627\u0644\u0645\u0637\u0644\u0648\u0628", "callback_data": f"keep:{key}"}],
                               [{"text": "\U0001f39b عدّل وولّد تاني", "callback_data": "tw:open"},
                                {"text": "\U0001f3b5 تراك تاني", "callback_data": "sug:track"}]])

    # ---------- tweak after listening ----------
    TWEAKS = {  # code: (key, step, low, high, default, label, one-line explanation)
        "w": ("weirdness", 20, 0, 100, 50, "الغرابة",
              "كل ما زادت، التراك بيجرّب حاجات مفاجئة وأغرب. كل ما قلّت، بيمشي على المضمون."),
        "i": ("style_influence", 15, 0, 100, 50, "تأثير الستايل",
              "كل ما زاد، التراك بيمسك الستايل اللي كتبته أكتر. كل ما قلّ، بياخد حرية أكتر."),
        "s": ("seconds", 60, 60, 600, 330, "الطول", "بالدقايق، أقصر أو أطول."),
        "b": ("bpm", 4, 60, 180, None, "السرعة (BPM)", "أبطأ أو أسرع شوية."),
    }

    def _tweak_screen(self, chat_id):
        sp = self.tweak.get(chat_id)
        if not sp:
            self.tg.send(chat_id, "مفيش تراك أعدّله دلوقتي. دوس تراك جديد.")
            return
        lines = []
        for code, (key, step, lo, hi, dflt, label, why) in self.TWEAKS.items():
            if key == "bpm" and not sp.get("bpm"):
                continue
            cur = sp.get(key, dflt)
            shown = f"{int(cur) // 60}:{int(cur) % 60:02d}" if key == "seconds" else cur
            lines.append(f"{label} (دلوقتي {shown}): {why}")
        kb = []
        for code, (key, step, lo, hi, dflt, label, why) in self.TWEAKS.items():
            if key == "bpm" and not sp.get("bpm"):
                continue
            lessw, morew = ("أقصر", "أطول") if key == "seconds" else (("أبطأ", "أسرع") if key == "bpm" else ("أقل", "أكتر"))
            kb.append([{"text": f"{label} {lessw}", "callback_data": f"tw:{code}-"},
                       {"text": f"{label} {morew}", "callback_data": f"tw:{code}+"}])
        kb.append([{"text": "\u25b6\ufe0f ولّد تاني بالتعديل", "callback_data": "tw:go"}])
        self.tg.send(chat_id, "عدّل وقولي ولّد تاني:\n\n" + "\n".join(lines), keyboard=kb)

    def _tweak_cb(self, chat_id, data):
        code = data[3:]
        if code == "open":
            base = self.last_enq.get(chat_id) or self._last_spec()
            if not base:
                self.tg.send(chat_id, "مفيش تراك أعدّله دلوقتي. دوس تراك جديد.")
                return
            self.tweak[chat_id] = dict(base)
            self._tweak_screen(chat_id)
            return
        sp = self.tweak.get(chat_id)
        if not sp:
            self.tg.send(chat_id, "الجلسة دي انتهت. دوس عدّل وولّد تاني من تحت التراك.")
            return
        if code == "go":
            spec = dict(self.tweak.pop(chat_id))
            spec.pop("seed", None)      # a fresh take, not the same one again
            spec.pop("title", None)
            self.tg.send(chat_id, "ماشي، بولّد تاني بالتعديل.")
            self._enqueue(chat_id, spec)
            return
        t = self.TWEAKS.get(code[:1])
        if not t or code[1:] not in ("+", "-"):
            self._tweak_screen(chat_id)
            return
        key, step, lo, hi, dflt, label, why = t
        cur = sp.get(key, dflt)
        if cur is None:
            self._tweak_screen(chat_id)
            return
        sp[key] = max(lo, min(hi, int(cur) + (step if code[1] == "+" else -step)))
        self._tweak_screen(chat_id)

    def _publish_cmd(self, chat_id, arg):
        folder = self._find_folder(arg) if arg else self._last_release()
        if not folder:
            self.tg.send(chat_id, "مفيش حاجة بالاسم ده. /library بيعرض التراكات." if arg
                         else "مفيش تراك في فولدر الجلسة دي لسه. /track بيعمل واحد.")
            return
        self._publish_menu(chat_id, folder)

    def _publish_cb(self, chat_id, data):
        parts = data.split(":")
        code = parts[1] if len(parts) > 1 else ""
        key = parts[2] if len(parts) > 2 else ""
        name = self._lib_folder(key)
        folder = os.path.join(self.out_root, name) if name else None
        if not folder or not os.path.isdir(folder):
            self.tg.send(chat_id, "التراك ده مش في فولدر الجلسة تاني. /library بيعرض الحاليين.")
            return
        if code not in PLATFORM_LABEL and code != "all":
            self.tg.send(chat_id, "وجهة النشر مش معروفة. /publish بيفتح القائمة تاني.")
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
                    done.append(f"قناة تيليجرام: اتنشر ({how}) - https://t.me/rahal_music")
                elif p == "yt":
                    try:
                        url = self._youtube_upload(folder, title, caption)
                        done.append(f"YouTube: اتنشر - {url}")
                    except Exception as e:
                        package("yt")
                        done.append("YouTube: لسه مترفعش (" + f"{type(e).__name__}: {str(e)[:160]}" +
                                    "). ملف النشر جاهز في فولدر التراك باسم publish_request_yt.json، "
                                    "والزرار ده هيرفع فعلاً أول ما الربط يتظبط.")
                elif p == "fb":
                    done.append("فيسبوك: الكابشن تحت والملف جاهز. النشر يدوي بقرارك.")
                else:
                    package(p)
                    done.append(f"{PLATFORM_LABEL[p]}: مفيش طريقة نشر تلقائية، فجهزت ملف النشر "
                                f"(كابشن + ملفات) في فولدر التراك باسم publish_request_{p}.json "
                                "عشان تنشره يدوي مرة واحدة.")
            except Exception as e:
                failed.append(f"{PLATFORM_LABEL.get(p, p)} فشل: {type(e).__name__}: {str(e)[:200]}")
        msg = ["\n".join(done)] if done else []
        if failed:
            msg.append("\n".join(failed))
        if "fb" in targets:
            msg.append("كابشن فيسبوك:\n" + caption)
        self.tg.send(chat_id, "\n\n".join(msg) or "مفيش حاجة تتنشر.")

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
            self.tg.send(chat_id, "مفيش مهام من التطبيق على درايف (دورت في Zi_Music/jobs و zi_data/jobs).")
            return
        for j in found:
            j = self._normalize_spec(j)
            j.setdefault("idea", j.get("genre", ""))
            j.setdefault("lang", "en")
            self.jobs.put((chat_id, j))
            self.queued.append(j.get("title") or j.get("name") or j.get("genre") or "track")
        self.tg.send(chat_id, f"Imported {len(found)} مهمة من التطبيق اتضافت للطابور.")


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
    print(f"Stopped {stale} متابِع قديم؛ {len(still)} still alive before start.")
    if still:
        print("تحذير: متابِع قديم مقفلش. أعد تشغيل الكيرنل لو الأزرار وقفت تشتغل.")
    bot = Bot(token, out_root=out_root, work=work, make_track=make_track, run_queue=run_queue)
    bot.start()
    builtins._zi_bot_instance = bot
    print(f"بوت Zi شغال (إصدار {VERSION}). كلّم البوت في تيليجرام؛ /help بيعرض الأوامر.")
    try:
        print(f"عدد المتابعات الشغالة بعد التشغيل: {len(_bot_instances())} (١ يعني سليم)")
    except Exception:
        pass
    return bot
