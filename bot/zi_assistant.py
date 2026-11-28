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


FEEDBACK_VERBS = ("خلي ", "خلّي", "ضيف", "شيل", "غيّر", "غير ", "عدّل", "عدل ", "زوّد", "زود ", "بدّل", "بدل ",
                  "انقل", "نقّل", "المفروض", "اقتراح", "ملاحظة", "فيدباك", "feedback", "عايزك تغير", "عايزك تضيف")
FEEDBACK_NOUNS = ("زرار", "زراير", "الأزرار", "الازرار", "قايمة", "القائمة", "المينيو", "شاشة", "الشاشة",
                  "الواجهة", "اللينك", "مرجع", "المرجع", "البرومبت", "الرسالة", "الرد", "الشكل", "الصوت",
                  "التراك", "اللغة", "الخيارات", "الستايل")


def is_feedback(text):
    """A request to change how the bot looks or behaves, not a question about his tracks.

    A change word plus a screen word, or an explicit suggestion word. Questions about the
    project (missing, status, publishing) are never feedback.
    """
    q = (text or "").strip().lower()
    if len(q) < 8:
        return False
    if q.endswith(("؟", "?")) and intent_of(q) in ("missing", "next", "status", "dataset", "publish", "liked", "lora"):
        return False
    explicit = any(w in q for w in ("اقتراح", "ملاحظة", "فيدباك", "feedback"))
    verb = any(w in q for w in FEEDBACK_VERBS)
    noun = any(w in q for w in FEEDBACK_NOUNS)
    return explicit or (verb and noun)


FEEDBACK_REPLY = "وصّلتها للمطوّر \U0001f44c هتلاقيها في التعديلات الجاية."


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
    return ("ما وصلنيش كويس، ممكن تعيدها؟ أو دوس /menu وكل حاجة قدامك.\n"
            "وأقدر أجاوب على: اللي ناقص، اللي تعمله بعد كده، حالة الشغل، تراكات التدريب، "
            "اللي حفظته، والنشر.")


# ---------- optional: a free hosted model, when a key is present ----------
TONE = ("الأسلوب: اتكلم زي واحد مصري عادي من الشارع، عامية خالص، قصير ودافي، وهزار خفيف مسموح. "
        "ممنوع الفصحى والجمل الرسمية (زي: يسعدني، بالتأكيد، يمكنك، من فضلك، عزيزي، لا تتردد) وممنوع أي مصطلح تقني. "
        "ممنوع تبدأ بترحيب رسمي أو تختم بعرض مساعدة جاهز.\n"
        "أمثلة على الشكل المطلوب:\n"
        "- سأل: ازيك؟ ← رديت: تمام الحمد لله، إنت عامل إيه؟ جاهز نعمل حاجة حلوة؟\n"
        "- سأل: يعني إيه BPM؟ ← رديت: دي سرعة التراك، كام دقة في الدقيقة. ١٢٢ يعني ماشي معتدل كده، مناسب للرقص.\n"
        "- سأل: ينفع أعمل تراك هادي للسواقة بليل؟ ← رديت: طبعاً ينفع! قولي المود وأنا أظبطهولك، وغالباً هيطلع حلو.\n"
        "- سأل: مش عارف أبدأ منين ← رديت: ولا يهمك، قولي حاسس بإيه دلوقتي وأنا أطلعلك فكرة، من غير تعقيد.\n"
        "- سأل: التراك ده طلع وحش ← رديت: ولا يهمك، نجرب تاني. قولي إيه اللي مضايقك فيه، الإيقاع ولا الجو؟")

SYSTEM = ("أنت المساعد الشخصي بتاع راهال، جوّه بوت Zi Music Studio. رد بالمصري، قصير - ٤ سطور كتير.\n"
          "لو عرّفت بنفسك قول: أنا مساعدك الشخصي. ممنوع تقول \"مساعد راهال\".\n"
          "أي سؤال معلومات عامة (موسيقى، إنتاج، مصطلحات زي LoRA أو BPM أو المقام، أو أي موضوع تاني) "
          "جاوب عليه مباشرة وبإيجاز من معرفتك، من غير ما تربطه بحالة البوت ومن غير ما تقول مش شايفه.\n"
          "تحت هتلاقي معلومات المشروع. استخدمها بس لو سأل عن المشروع نفسه: التراكات، الطابور، النشر، "
          "الحالة، أو إيه الناقص. ممنوع تذكر عدد تراكات مستر درغام أو المطلوب أو أي رقم من المعلومات دي "
          "لو السؤال مش عنها، وماتحطهاش في آخر الرد كملحوظة.\n"
          "في كلام المشروع بس: كل حقيقة لازم تكون من المعلومات اللي تحت، ولو حاجة مش فيها قول إنك مش شايفها. "
          "ما تخترعش أرقام ولا مميزات، وما تقولش إنك عملت حاجة، وما تقولش إن ميزة شغالة أو مفعّلة "
          "إلا لو مكتوبة في المعلومات. ماتكلمش عن أي مفاتيح أو أسرار.\n"
          "لو الكلام مش واضح أو شكله متلخبط (كلام الصوت ساعات بيتسمع غلط): قول بلُطف ودفا \"ما وصلنيش كويس، "
          "ممكن تعيدها؟\" وبعدها اعرض عليه /menu. ممنوع تقول \"مش فاهم\" أو \"مش فاهم الكلام ده\" أو أي رد جاف.\n"
          "ماتتكلمش عن الإنجين ولا المحرك ولا النوتبوك ولا OCR ولا الصوت ولا أي حاجة تقنية عن البوت نفسه. "
          "لو الرندر مش شغال وسأل قول له يشغّل خلية الإنجين وبس.\n"
          + TONE)

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
                          "معلومات المشروع (استخدمها بس لو سأل عن المشروع):\n" + context_block(state) +
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
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"
GROQ_FALLBACK_MODELS = ("qwen/qwen3.8-27b",)
GROQ_SYSTEM = SYSTEM


def groq_models(model=None):
    """ZI_GROQ_MODEL (or the argument) first, then the default, then the fallbacks. No repeats."""
    first = (model or os.environ.get("ZI_GROQ_MODEL") or "").strip()
    out = []
    for m in (first, GROQ_DEFAULT_MODEL) + tuple(GROQ_FALLBACK_MODELS):
        if m and m not in out:
            out.append(m)
    return out


def build_groq_request(question, state, model=None):
    """The exact body sent to Groq: system prompt, the real state, then the question."""
    name = (model or groq_models()[0]).strip()
    body = {"model": name,
            "messages": [{"role": "system", "content": GROQ_SYSTEM},
                         {"role": "user", "content": "معلومات المشروع (استخدمها بس لو سأل عن المشروع):\n" + context_block(state) +
                          "\n\nسؤاله: " + (question or "").strip()}],
            "temperature": 0.4, "max_tokens": 1200}
    if "gpt-oss" in name:
        body["reasoning_effort"] = "low"        # short thinking, so the answer fits the budget
    return body


def parse_groq(data):
    try:
        t = data["choices"][0]["message"]["content"]
    except Exception:
        return None
    return t.strip() if isinstance(t, str) and t.strip() else None


def ask_groq(question, state, key, model=None, opener=None, timeout=25, sleep=None, tries=3):
    """Groq chat call over the model list. None on any failure so Gemini and the grounded answers take over.

    429 is retried with a short backoff (Retry-After, capped at 6 s) and then the next model is tried;
    404 or any other HTTP error moves to the next model at once. The key goes in the
    Authorization header only and is never printed.
    """
    if not key:
        return None
    import json as _json
    import time as _t
    import urllib.error as _uerr
    import urllib.request as _req
    sleep = sleep or _t.sleep
    for name in groq_models(model):
        body = _json.dumps(build_groq_request(question, state, name)).encode()
        for attempt in range(tries):
            req = _req.Request(GROQ_URL, data=body, method="POST",
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + key,
                                        "User-Agent": "zi-studio-bot/1.0"})
            try:
                with (_opener(opener))(req, timeout=timeout) as r:
                    text = parse_groq(_json.loads(r.read()))
                if text:
                    return text
                break                                  # empty answer: next model
            except _uerr.HTTPError as e:
                print("groq HTTP", e.code, name)       # the code and model only, never the key
                if e.code == 429 and attempt + 1 < tries:
                    try:
                        wait = float((e.headers or {}).get("Retry-After") or 0)
                    except Exception:
                        wait = 0
                    sleep(min(max(wait, 1.5 * (attempt + 1)), 6))
                    continue
                break
            except Exception as e:
                print("groq failed:", type(e).__name__)
                break
    return None


GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_STT_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")
STT_HINT = "كلام مصري عن الموسيقى والتراكات والبرومبت والزراير."


def transcribe_groq(path, key, model=None, opener=None, timeout=60, sleep=None, tries=2):
    """Speech to text through Groq's whisper. Returns (text or None, problem).

    Multipart upload, Egyptian Arabic hinted, temperature 0. The key goes in the Authorization
    header and is never printed. Telegram voice notes are .oga; Groq wants .ogg, so only the
    uploaded filename changes.
    """
    if not key:
        return None, "no key"
    import json as _json
    import time as _t
    import uuid as _uuid
    import urllib.error as _uerr
    import urllib.request as _req
    sleep = sleep or _t.sleep
    try:
        with open(path, "rb") as fh:
            audio = fh.read()
    except Exception as e:
        return None, type(e).__name__
    if not audio or len(audio) > 24 * 1024 * 1024:
        return None, "audio size"
    name = os.path.basename(path)
    if name.lower().endswith(".oga"):
        name = name[:-4] + ".ogg"
    problem = "empty"
    for m in ([model] if model else list(GROQ_STT_MODELS)):
        boundary = "zi" + _uuid.uuid4().hex
        parts = []
        for k, v in (("model", m), ("language", "ar"), ("response_format", "json"),
                     ("temperature", "0"), ("prompt", STT_HINT)):
            parts.append(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + k + "\"\r\n\r\n" + v + "\r\n").encode("utf-8"))
        parts.append(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"" + name +
                      "\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode("utf-8"))
        parts.append(audio)
        parts.append(("\r\n--" + boundary + "--\r\n").encode("utf-8"))
        body = b"".join(parts)
        for attempt in range(tries):
            req = _req.Request(GROQ_STT_URL, data=body, method="POST",
                               headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                                        "Authorization": "Bearer " + key, "User-Agent": "zi-studio-bot/1.0"})
            try:
                with (_opener(opener))(req, timeout=timeout) as r:
                    data = _json.loads(r.read())
                text = (data.get("text") or "").strip() if isinstance(data, dict) else ""
                if text:
                    return text, ""
                problem = m + ": empty"
                break
            except _uerr.HTTPError as e:
                print("groq stt HTTP", e.code, m)               # the code and model only
                problem = m + ": " + str(e.code)
                if e.code == 429 and attempt + 1 < tries:
                    sleep(2 * (attempt + 1))
                    continue
                break
            except Exception as e:
                print("groq stt failed:", type(e).__name__)
                problem = m + ": " + type(e).__name__
                break
    return None, problem


GROQ_VISION_MODEL = "qwen/qwen3.8-27b"


def build_groq_vision_request(image_bytes, mime="image/jpeg", prompt=None, model=None):
    """OpenAI-style image_url part with a base64 data URL; max_completion_tokens, not max_tokens."""
    import base64 as _b64
    url = "data:" + (mime or "image/jpeg") + ";base64," + _b64.b64encode(image_bytes).decode()
    return {"model": (model or os.environ.get("ZI_GROQ_VISION_MODEL") or GROQ_VISION_MODEL).strip(),
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt or VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": url}}]}],
            "temperature": 0.1, "max_completion_tokens": 600}


def read_image_groq(image_bytes, key, model=None, mime="image/jpeg", opener=None, timeout=30,
                    sleep=None, tries=3):
    """One screenshot through Groq vision. Returns (text or None, problem).

    429 backs off (Retry-After, capped at 6 s). A normal User-Agent is sent, because the default
    Python one gets a Cloudflare 403 (code 1010). The key is never printed.
    """
    if not key or not image_bytes:
        return None, "no key or image"
    import json as _json
    import time as _t
    import urllib.error as _uerr
    import urllib.request as _req
    sleep = sleep or _t.sleep
    body = _json.dumps(build_groq_vision_request(image_bytes, mime, model=model)).encode()
    problem = "empty"
    for attempt in range(tries):
        req = _req.Request(GROQ_URL, data=body, method="POST",
                           headers={"Content-Type": "application/json", "Authorization": "Bearer " + key,
                                    "User-Agent": "zi-studio-bot/1.0"})
        try:
            with (_opener(opener))(req, timeout=timeout) as r:
                text = parse_groq(_json.loads(r.read()))
        except _uerr.HTTPError as e:
            print("groq vision HTTP", e.code)                 # the code only, never the key
            problem = "groq: " + str(e.code)
            if e.code == 429 and attempt + 1 < tries:
                try:
                    wait = float((e.headers or {}).get("Retry-After") or 0)
                except Exception:
                    wait = 0
                sleep(min(max(wait, 1.5 * (attempt + 1)), 6))
                continue
            return None, problem
        except Exception as e:
            print("groq vision failed:", type(e).__name__)
            return None, "groq: " + type(e).__name__
        if not text or text.strip().lower().strip(" .!") in ("nothing", "لا شيء"):
            return None, "groq: empty"
        return text.replace("\n", " ").strip()[:300], ""
    return None, problem


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
    import re as _re
    low = (text or "").lower()
    for w in JARGON:
        if w.isascii():
            # whole words only, so "rapid" or "capital" never trips "api"
            if _re.search(r"(?<![a-z])" + _re.escape(w) + r"(?![a-z])", low):
                return True
        elif w in low:
            return True
    return False


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
