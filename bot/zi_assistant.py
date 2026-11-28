"""The assistant inside the bot: it answers from the bot's real state.

There is no model and no key here. Every sentence it can say comes from a field
the bot already knows, so it cannot invent a feature, a number or a promise.
The wording is Egyptian Arabic because that is how he talks to it.

`answer()` takes a state dict (see `Bot._snapshot`) and returns short Arabic.
`context_block()` renders the same state as plain text, ready to hand to a free
hosted model later if a key is ever added - the wording is the only thing that
would change, never the facts.
"""
import os

# ---------- what the bot knows ----------
REQUIRED_DATASET = 50          # roughly how many of his own tracks the LoRA wants


def _tracks(n):
    """Egyptian Arabic for a count of tracks: one, or the plural."""
    n = int(n or 0)
    return "تراك واحد" if n == 1 else f"{n} تراكات"


def missing(state):
    """Everything that is not done yet, in the order it matters. Never invents."""
    out = []
    ds = state.get("dataset") or {}
    n = int(ds.get("count") or 0)
    if n < REQUIRED_DATASET:
        out.append(f"تراكات مستر درغام: {n} من حوالي {REQUIRED_DATASET} - محتاج كمان "
                   f"{REQUIRED_DATASET - n} علشان الموديل يتدرب كويس")
    if int(ds.get("unlabelled") or 0):
        out.append(f"{ds['unlabelled']} تراك لسه من غير تصنيف (فوكال / إنسترومنتال)")
    if not (state.get("publish") or {}).get("youtube"):
        out.append("توكن يوتيوب مش موجود، فالنشر على يوتيوب مقفول")
    if not state.get("lora"):
        out.append("موديل مستر درغام لسه مش متدرب")
    if not state.get("engine"):
        out.append("الرندر واقف: شغّل خلية الإنجين في النوتبوك، وبعدها خلية البوت")
    return out


def next_steps(state):
    """What to do next, most useful first. Only things the bot can actually see."""
    steps = []
    if not state.get("engine"):
        steps.append("الرندر مش شغال: شغّل خلية الإنجين في النوتبوك، وبعدها خلية البوت، وبعد كده /status")
        return steps
    ds = state.get("dataset") or {}
    n = int(ds.get("count") or 0)
    if int(ds.get("unlabelled") or 0):
        steps.append("افتح /dataset وحدّد الفوكال من الإنسترومنتال للتراكات اللي لسه")
    if n < REQUIRED_DATASET:
        steps.append(f"ابعت تراكاتك للبوت لحد ما توصل حوالي {REQUIRED_DATASET} (فاضل {REQUIRED_DATASET - n})")
    if not int(state.get("liked") or 0):
        steps.append("وانت بتولّد، دوس ⭐ تحت التراك اللي عاجبك - ده اللي هيتدرب عليه الموديل")
    if not (state.get("publish") or {}).get("youtube"):
        steps.append("لما تحب تنشر على يوتيوب، محتاج توكن يوتيوب (client id و secret من Google Cloud)")
    if not steps:
        steps.append("كل حاجة تمام. /track يبدأ تراك جديد، ولو عايز نفس الإعدادات دوس آخر زرار في /track")
    return steps


def status(state):
    ds = state.get("dataset") or {}
    pub = state.get("publish") or {}
    on = [name for name, ok in (("يوتيوب", pub.get("youtube")), ("انستجرام", pub.get("instagram")),
                                ("تيك توك", pub.get("tiktok")), ("تليجرام", pub.get("telegram"))) if ok]
    lines = ["بيترندر دلوقتي: " + (state.get("rendering") or "مفيش"),
             f"مستني في الطابور: {int(state.get('waiting') or 0)}"]
    lines.append(dataset_line(state))
    if ds:
        lines.append(f"منهم فوكال {ds.get('vocal', 0)} وإنسترومنتال {ds.get('instrumental', 0)}"
                     + (f"، و{ds['unlabelled']} لسه من غير تصنيف" if int(ds.get("unlabelled") or 0) else ""))
    lines.append(f"التراكات اللي حفظتها: {int(state.get('liked') or 0)}")
    lines.append("النشر متوصل على: " + ("، ".join(on) if on else "مفيش حاجة متوصلة"))
    lines.append("موديل مستر درغام: " + ("جاهز" if state.get("lora") else "لسه مش متدرب"))
    return "\n".join(lines)


# ---------- intent matching ----------
INTENTS = (
    ("missing", ("ناقص", "محتاج", "مش موجود", "لسه", "missing", "need", "what do i", "عايز ايه")),
    ("next", ("أعمل ايه", "اعمل ايه", "أعمل إيه", "اعمل إيه", "الخطوة", "بعد كده", "next", "ابدأ", "أبدأ")),
    ("dataset", ("داتا", "dataset", "للتدريب", "التدريب", "تدريب", "تراكاتي", "بعتها", "training")),
    ("liked", ("liked", "المفضلة", "عجبني", "حفظت", "النجمة", "⭐")),
    ("publish", ("نشر", "انشر", "أنشر", "يوتيوب", "تيك توك", "انستا", "instagram", "publish", "youtube")),
    ("lora", ("لورا", "lora", "درغام", "دورغام", "dorgham", "الموديل", "model")),
    ("how", ("ازاي", "إزاي", "اشرح", "how", "طريقة")),
    ("status", ("الحالة", "حالة", "status", "الوضع", "شغال", "فين", "كام")),
    ("thanks", ("شكرا", "شكراً", "تسلم", "thanks")),
    ("greet", ("ازيك", "إزيك", "سلام", "هاي", "hi", "hello")),
)


def intent_of(question):
    """The intent behind the words: the longest keyword wins, then the earliest."""
    q = (question or "").lower()
    best, best_key = None, None
    for name, words in INTENTS:
        for w in words:
            i = q.find(w.lower())
            if i < 0:
                continue
            key = (-len(w), i)
            if best_key is None or key < best_key:
                best, best_key = name, key
    return best


def answer(question, state):
    """Short Egyptian Arabic, from the state only."""
    q = (question or "").strip()
    if not q:
        return ("أيوه؟ اسألني عن اللي ناقص، أو اللي تعمله بعد كده، أو حالة الشغل.\n"
                "مثال: \"إيه الناقص؟\" أو \"أعمل إيه بعد كده؟\"")
    it = intent_of(q)
    if it == "missing":
        miss = missing(state)
        if not miss:
            return "مفيش حاجة ناقصة دلوقتي. كل اللي البوت شايفه تمام."
        head = "اللي ناقص:" if len(miss) > 1 else "ناقص حاجة واحدة:"
        return head + "\n- " + "\n- ".join(miss[:6])
    if it == "next":
        return "الخطوة اللي بعدها:\n- " + "\n- ".join(next_steps(state)[:4])
    if it == "dataset":
        ds = state.get("dataset") or {}
        n = int(ds.get("count") or 0)
        left = max(0, REQUIRED_DATASET - n)
        return (f"عندك {n} تراك للتدريب: فوكال {ds.get('vocal', 0)}، "
                f"إنسترومنتال {ds.get('instrumental', 0)}، من غير تصنيف {ds.get('unlabelled', 0)}.\n"
                + (f"فاضل حوالي {left} لحد {REQUIRED_DATASET}." if left else "العدد كفاية، راجع التصنيف بس.")
                + "\n/dataset بيوريك الأسماء.")
    if it == "liked":
        n = int(state.get("liked") or 0)
        if n:
            return f"حفظت {_tracks(n)} في مجلد Liked.\n/liked بيوريك القائمة، وده اللي هيتدرب عليه الموديل."
        return "لسه محفظتش حاجة. دوس ⭐ تحت أي تراك عاجبك، وهيتحفظ في مجلد Liked."
    if it == "publish":
        pub = state.get("publish") or {}
        on = [name for name, ok in (("يوتيوب", pub.get("youtube")), ("انستجرام", pub.get("instagram")),
                                    ("تيك توك", pub.get("tiktok")), ("تليجرام", pub.get("telegram"))) if ok]
        if not on:
            return ("مفيش منصة متوصلة للنشر لسه. أول حاجة توكن يوتيوب (Google Cloud OAuth)، "
                    "وبعده الأزرار هتشتغل من تحت كل تراك.")
        return "النشر شغال على: " + "، ".join(on) + ".\nمن تحت كل تراك فيه أزرار النشر، والزرار بينشر مرة واحدة بس."
    if it == "lora":
        if state.get("lora"):
            return "موديل مستر درغام جاهز ومتاح كاختيار في الإعدادات."
        ds = state.get("dataset") or {}
        return (f"موديل مستر درغام لسه مش متدرب. محتاج تراكاتك: عندك {ds.get('count', 0)} دلوقتي "
                f"من حوالي {REQUIRED_DATASET}، والتراكات اللي بتدوس عليها ⭐ هي اللي بتتحفظ للتدريب.")
    if it == "status":
        return status(state)
    if it == "how":
        return ("من /track: تختار ستايل، أو تكتب البرومبت بنفسك، أو تديني ريفرنس "
                "(اسم تراك، لينك، اسكرين شوت، أو فويس) وأنا أطلع منه وصف الستايل.\n"
                "وبعدها الطول، فوكال ولا إنسترومنتال، والجودة. /menu فيه كل حاجة.")
    if it == "thanks":
        return "العفو. أي حاجة تحتاجها اسألني."
    if it == "greet":
        return ("أهلاً بيك. أنا مساعدك الشخصي.\n" + dataset_line(state)
                + "\nتحب أقولك إيه الناقص، ولا نبدأ تراك؟")
    # nothing matched: say what it can answer instead of guessing
    return ("مش متأكد إني فهمت السؤال. أقدر أجاوب على: اللي ناقص، اللي تعمله بعد كده، "
            "حالة الشغل، تراكات التدريب، اللي حفظته، النشر، وموديل مستر درغام.")


# ---------- optional: a free hosted model, when a key is present ----------
SYSTEM = ("أنت المساعد الشخصي بتاع راهال، جوّه بوت Zi Music Studio. رد بالمصري، قصير - ٤ سطور كتير.\n"
          "لو عرّفت بنفسك قول: أنا مساعدك الشخصي. ممنوع تقول \"مساعد راهال\".\n"
          "كل حقيقة في ردك لازم تكون من الحالة اللي تحت. لو الحاجة مش في الحالة قول إنك مش شايفها.\n"
          "ما تخترعش أرقام ولا مميزات، وما تقولش إنك عملت حاجة. ماتكلمش عن أي مفاتيح أو أسرار.\n"
          "ماتتكلمش عن الإنجين ولا المحرك ولا النوتبوك ولا OCR ولا الصوت ولا أي حاجة تقنية، "
          "وماتقولش إن ميزة شغالة أو مفعّلة. لو الرندر مش شغال قول له يشغّل خلية الإنجين وبس.\n"
          "لازم تذكر تراكات مستر درغام: كام تراك عنده دلوقتي، وكام فاضل لحد ما الموديل يتدرب كويس.")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# gemini-2.0-flash and 2.5-flash answer 404 for a new key (retired for new accounts).
# 3.1-flash-lite is the free model that answers, so it is the default and no env is
# needed; ZI_LLM_MODEL still overrides it.
DEFAULT_MODEL = os.environ.get("ZI_LLM_MODEL", "gemini-3.1-flash-lite").strip() or "gemini-3.1-flash-lite"


def build_request(question, state, model=None, thinking_budget=0):
    """The exact body sent to the free model: the state block, then the question.

    Gemini 3 models think before they answer and the thinking is billed against
    maxOutputTokens, which used to leave no text at all. So thinking is off by
    default (budget 0), the token budget is generous, and ask_llm retries without
    the thinking setting if a model refuses it.
    """
    gen = {"temperature": 0.4, "maxOutputTokens": 1500}
    if thinking_budget is not None:
        gen["thinkingConfig"] = {"thinkingBudget": int(thinking_budget)}
    return {"system_instruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text":
                          "الحالة الحقيقية للبوت:\n" + context_block(state) +
                          "\n\nسؤاله: " + (question or "").strip()}]}],
            "generationConfig": gen}


def parse_response(data):
    """The answer text, whatever shape the model used.

    Gemini 3 can return thought parts (marked thought: true) next to the answer,
    and an empty part list when the budget ran out. Only the spoken parts count.
    """
    try:
        cand = (data.get("candidates") or [])[0]
    except Exception:
        return None
    if not isinstance(cand, dict):
        return None
    pieces = []
    content = cand.get("content") or {}
    for part in (content.get("parts") or []):
        if not isinstance(part, dict):
            continue
        if part.get("thought") or part.get("thoughtSignature"):
            continue                       # reasoning, not the answer
        t = part.get("text")
        if isinstance(t, str) and t.strip():
            pieces.append(t)
    text = "".join(pieces).strip()
    if not text and isinstance(cand.get("text"), str):
        text = cand["text"].strip()        # some shapes put it on the candidate
    return text or None


def ask_llm(question, state, key, model=None, opener=None, timeout=20):
    """One call to the free Gemini tier. None on any failure, so the caller falls back.

    The key travels in a header, never in the URL, and is never printed: a 429, a
    quota error or a network blip all come back as None and the grounded answers
    take over.
    """
    if not key:
        return None
    import json as _json
    import urllib.error as _uerr
    import urllib.request as _req
    model = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL

    def once(budget):
        body = _json.dumps(build_request(question, state, model, thinking_budget=budget)).encode()
        req = _req.Request(GEMINI_URL.format(model=model), data=body, method="POST",
                           headers={"Content-Type": "application/json", "x-goog-api-key": key})
        with (_opener(opener))(req, timeout=timeout) as r:
            return _json.loads(r.read())

    try:
        data = once(0)
    except _uerr.HTTPError as e:
        print("assistant llm HTTP", e.code)          # the code only, never the key
        if e.code != 400:
            return None
        try:
            data = once(None)                        # the model refused thinkingBudget
        except Exception as e2:
            print("assistant llm retry failed:", getattr(e2, "code", type(e2).__name__))
            return None
    except Exception as e:
        print("assistant llm failed:", type(e).__name__)
        return None
    return parse_response(data)


# ---------- optional: reading a screenshot with the same free key ----------
VISION_PROMPT = ("Read this screenshot and answer with one short line, no preamble: "
                 "what track is playing, who it is by, and any style, mood or tempo words on screen. "
                 "If it is not music, answer with the main words you can read. "
                 "If nothing is readable, answer exactly: nothing")

VISION_MODEL = (os.environ.get("ZI_VISION_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"
# tried after ZI_VISION_MODEL (a comma list is fine) and before anything the key's own list adds
VISION_FALLBACKS = ("gemini-3-flash-preview", "gemini-flash-latest", "gemini-flash-lite-latest",
                    "gemini-2.5-flash", "gemini-3.1-flash-lite")
_SKIP = ("embedding", "tts", "image", "imagen", "veo", "robotics", "aqa", "live", "audio", "computer", "thinking-exp")
_models_cache = {}


def list_models(key, opener=None, timeout=20):
    """Models this key can call with generateContent, newest flash first. [] when the list is unreachable."""
    if key in _models_cache:
        return _models_cache[key]
    import json as _json
    import urllib.request as _req
    out = []
    try:
        req = _req.Request(MODELS_URL, headers={"x-goog-api-key": key})
        with (_opener(opener))(req, timeout=timeout) as r:
            data = _json.loads(r.read())
        for m in data.get("models", []):
            name = (m.get("name") or "").split("/")[-1]
            if (name.startswith("gemini") and "generateContent" in (m.get("supportedGenerationMethods") or [])
                    and not any(w in name for w in _SKIP)):
                out.append(name)
    except Exception as e:
        print("model list failed:", type(e).__name__)
        return []
    out.sort(key=lambda n: (0 if "flash" in n and "lite" not in n else 1 if "flash" in n else 2,
                            0 if "preview" not in n and "exp" not in n else 1, n), reverse=False)
    _models_cache[key] = out
    return out


def vision_models(key=None, extra=(), opener=None):
    """Ordered, de-duplicated model ids to try for an image."""
    env = [m.strip() for m in (os.environ.get("ZI_VISION_MODEL") or "").split(",") if m.strip()]
    order = list(env) + [m for m in extra if m] + list(VISION_FALLBACKS)
    if key:
        live = list_models(key, opener=opener)
        if live:
            order = [m for m in order if m in live or m in env] + [m for m in live if m not in order][:4]
    seen, out = set(), []
    for m in order:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def read_image_retry(image_bytes, key, models=None, mime="image/jpeg", opener=None, sleep=None, tries=2):
    """Try each model, backing off on 429/5xx. Returns (text or None, last_problem)."""
    import time as _t
    sleep = sleep or _t.sleep
    problem = "no model answered"
    for model in (models or vision_models(key, opener=opener)):
        for attempt in range(tries):
            res = read_image(image_bytes, key, model=model, mime=mime, opener=opener, detail=True)
            if isinstance(res, str) and res:
                return res, ""
            res = res if isinstance(res, dict) else {}
            if res.get("text"):
                return res["text"], ""
            code = res.get("code")
            problem = f"{model}: {code or res.get('error') or 'empty'}"
            if code in (429, 500, 502, 503, 504) and attempt + 1 < tries:
                sleep(2 * (attempt + 1))
                continue
            break
    return None, problem


def build_vision_request(image_bytes, mime="image/jpeg", prompt=None):
    """The exact body sent for a screenshot: the image inline, base64, and a short ask."""
    import base64 as _b64
    return {"contents": [{"role": "user", "parts": [
                {"text": prompt or VISION_PROMPT},
                {"inlineData": {"mimeType": mime or "image/jpeg",
                                "data": _b64.b64encode(image_bytes).decode()}}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 600,
                                 "thinkingConfig": {"thinkingBudget": 0}}}


def read_image(image_bytes, key, model=None, mime="image/jpeg", opener=None, timeout=30, detail=False):
    """One vision call. None on any failure, so the bot can say so in plain words.

    The key goes in a header, never the URL, and never gets printed.
    """
    def fail(code=None, error=None):
        return {"text": None, "code": code, "error": error} if detail else None
    if not key or not image_bytes:
        return fail(error="no key or image")
    import json as _json
    import urllib.error as _uerr
    import urllib.request as _req
    body = _json.dumps(build_vision_request(image_bytes, mime)).encode()
    req = _req.Request(GEMINI_URL.format(model=(model or VISION_MODEL)), data=body, method="POST",
                       headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with (_opener(opener))(req, timeout=timeout) as r:
            data = _json.loads(r.read())
    except _uerr.HTTPError as e:
        print("vision HTTP", e.code, model or VISION_MODEL)      # the code only, never the key
        return fail(code=e.code)
    except Exception as e:
        print("vision failed:", type(e).__name__)
        return fail(error=type(e).__name__)
    text = parse_response(data)
    if not text or text.strip().lower().strip(" .!") in ("nothing", "لا شيء"):
        return fail(error="empty")
    text = text.strip().replace("\n", " ")[:300]
    return {"text": text, "code": None, "error": None} if detail else text


# ---------- Groq (OpenAI-compatible, free plan): tried before Gemini ----------
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
GROQ_SYSTEM = ("أنت المساعد الشخصي للمستخدم. ردّ بالمصري، قصير ومباشر، وبناءً على حالة البوت الحقيقية "
               "اللي هتتبعتلك بس. متخترعش حاجة مش موجودة في الحالة. ") + SYSTEM


def build_groq_request(question, state, model=None):
    """The exact body sent to Groq: system prompt, the real state, then the question."""
    return {"model": (model or os.environ.get("ZI_GROQ_MODEL") or GROQ_DEFAULT_MODEL).strip(),
            "messages": [{"role": "system", "content": GROQ_SYSTEM},
                         {"role": "user", "content": "الحالة الحقيقية للبوت:\n" + context_block(state) +
                          "\n\nسؤاله: " + (question or "").strip()}],
            "temperature": 0.4, "max_tokens": 700}


def parse_groq(data):
    try:
        t = data["choices"][0]["message"]["content"]
    except Exception:
        return None
    return t.strip() if isinstance(t, str) and t.strip() else None


def ask_groq(question, state, key, model=None, opener=None, timeout=25, sleep=None, tries=3):
    """One Groq chat call. None on any failure so Gemini and then the grounded answers take over.

    429 is retried with a short backoff (Retry-After, capped at 6 s), then it falls through.
    The key goes in the Authorization header only and is never printed.
    """
    if not key:
        return None
    import json as _json
    import time as _t
    import urllib.error as _uerr
    import urllib.request as _req
    sleep = sleep or _t.sleep
    body = _json.dumps(build_groq_request(question, state, model)).encode()
    for attempt in range(tries):
        req = _req.Request(GROQ_URL, data=body, method="POST",
                           headers={"Content-Type": "application/json", "Authorization": "Bearer " + key,
                                    "User-Agent": "zi-studio-bot/1.0"})
        try:
            with (_opener(opener))(req, timeout=timeout) as r:
                return parse_groq(_json.loads(r.read()))
        except _uerr.HTTPError as e:
            print("groq HTTP", e.code)                 # the code only, never the key
            if e.code == 429 and attempt + 1 < tries:
                try:
                    wait = float((e.headers or {}).get("Retry-After") or 0)
                except Exception:
                    wait = 0
                sleep(min(max(wait, 1.5 * (attempt + 1)), 6))
                continue
            return None
        except Exception as e:
            print("groq failed:", type(e).__name__)
            return None
    return None


def _opener(opener):
    if opener is not None:
        return opener
    import urllib.request as _req
    return _req.urlopen


# words that must never reach him: technical status, and the wrong name for the assistant
JARGON = ("ocr", "الإنجين", "الانجين", "المحرك", "محرك", "النوتبوك", "نوتبوك", "kernel",
          "tesseract", "whisper", "ffmpeg", "edge-tts", "gtts", "gemini", "api",
          "مساعد راهال", "النسخة", "build", "مفعّلين", "مفعلين", "مفعّلة", "مفعلة")


def has_jargon(text):
    """True when a model answer slipped into technical status or the wrong intro."""
    low = (text or "").lower()
    return any(w in low for w in JARGON)


def dataset_line(state):
    """His own tracks for the Mr Dorgham model, and how many are still needed."""
    ds = state.get("dataset") or {}
    n = int(ds.get("count") or 0)
    left = max(0, REQUIRED_DATASET - n)
    if not n:
        return (f"تراكات مستر درغام: لسه معندوش تراكات للتدريب، ومحتاج حوالي "
                f"{REQUIRED_DATASET} علشان الموديل يتدرب كويس")
    if left:
        return (f"تراكات مستر درغام: عنده {_tracks(n)} لحد دلوقتي، وفاضل حوالي {left} "
                f"لحد {REQUIRED_DATASET} علشان الموديل يتدرب كويس")
    return f"تراكات مستر درغام: عنده {_tracks(n)}، والعدد كفاية للتدريب"


def user_block(state):
    """What he can act on, in his words. No build number, no engine, no OCR, no voice.

    The model is not told what the box can do, so it cannot claim a capability that
    is not live; and the assistant never reports technical status he did not ask for.
    """
    pub = state.get("publish") or {}
    on = [name for name, ok in (("يوتيوب", pub.get("youtube")), ("انستجرام", pub.get("instagram")),
                                ("تيك توك", pub.get("tiktok")), ("تليجرام", pub.get("telegram"))) if ok]
    lines = [dataset_line(state),
             "التراكات اللي حفظها: " + str(int(state.get("liked") or 0)),
             "بيترندر دلوقتي: " + str(state.get("rendering") or "مفيش"),
             "مستني في الطابور: " + str(int(state.get("waiting") or 0)),
             "النشر متوصل على: " + ("، ".join(on) if on else "مفيش"),
             "موديل مستر درغام: " + ("متوصل كاختيار في الإعدادات" if state.get("lora")
                                     else "لسه مش متدرب، محتاج تراكاته الأول")]
    if not state.get("engine"):
        lines.append("الرندر واقف دلوقتي: محتاج يشغّل خلية الإنجين في النوتبوك")
    return "\n".join(lines)


def context_block(state):
    """Kept for the older callers and for tests: the same user-facing facts."""
    return user_block(state)
