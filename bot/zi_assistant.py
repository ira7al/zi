"""The assistant inside the bot: it answers from the bot's real state.

There is no model and no key here. Every sentence it can say comes from a field
the bot already knows, so it cannot invent a feature, a number or a promise.
The wording is Egyptian Arabic because that is how he talks to it.

`answer()` takes a state dict (see `Bot._snapshot`) and returns short Arabic.
`context_block()` renders the same state as plain text, ready to hand to a free
hosted model later if a key is ever added - the wording is the only thing that
would change, never the facts.
"""

# ---------- what the bot knows ----------
REQUIRED_DATASET = 50          # roughly how many of his own tracks the LoRA wants


def _tracks(n):
    """Egyptian Arabic for a count of tracks: one, or the plural."""
    n = int(n or 0)
    return "تراك واحد" if n == 1 else f"{n} تراكات"


def missing(state):
    """Everything that is not done yet, in the order it matters. Never invents."""
    out = []
    if not state.get("engine"):
        out.append("الإنجين مش محمّل - شغّل خلية الإنجين في النوتبوك وبعدها خلية البوت")
    ds = state.get("dataset") or {}
    n = int(ds.get("count") or 0)
    if n < REQUIRED_DATASET:
        out.append(f"تراكات التدريب: {n} من حوالي {REQUIRED_DATASET}")
    if int(ds.get("unlabelled") or 0):
        out.append(f"{ds['unlabelled']} تراك لسه من غير تصنيف (فوكال / إنسترومنتال)")
    if not (state.get("publish") or {}).get("youtube"):
        out.append("توكن يوتيوب مش موجود، فالنشر على يوتيوب مقفول")
    if not state.get("lora"):
        out.append("موديل مستر درغام لسه مش متدرب")
    if not state.get("voice"):
        out.append("تحويل الصوت لكلام مش متاح على الجهاز ده")
    if not state.get("ocr"):
        out.append("قراءة الاسكرين شوت مش متاحة على الجهاز ده")
    return out


def next_steps(state):
    """What to do next, most useful first. Only things the bot can actually see."""
    steps = []
    if not state.get("engine"):
        steps.append("شغّل خلية الإنجين في النوتبوك، وبعدها خلية البوت، وبعد كده /status")
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
    lines = [f"النسخة {state.get('build', '?')}",
             "الإنجين: " + ("شغال" if state.get("engine") else "مش محمّل"),
             "بيترندر دلوقتي: " + (state.get("rendering") or "مفيش"),
             f"مستني في الطابور: {int(state.get('waiting') or 0)}"]
    if ds:
        lines.append(f"تراكات التدريب: {ds.get('count', 0)} (فوكال {ds.get('vocal', 0)} | "
                     f"إنسترومنتال {ds.get('instrumental', 0)} | من غير تصنيف {ds.get('unlabelled', 0)})")
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
        return "أهلاً. جاهز. تحب أعرفك إيه الناقص، ولا نبدأ تراك؟"
    # nothing matched: say what it can answer instead of guessing
    return ("مش متأكد إني فهمت السؤال. أقدر أجاوب على: اللي ناقص، اللي تعمله بعد كده، "
            "حالة الشغل، تراكات التدريب، اللي حفظته، النشر، وموديل مستر درغام.")


def context_block(state):
    """The same facts as plain text, for a hosted model later."""
    return "\n".join([
        "build: " + str(state.get("build")),
        "engine loaded: " + str(bool(state.get("engine"))),
        "rendering: " + str(state.get("rendering") or "nothing"),
        "waiting: " + str(int(state.get("waiting") or 0)),
        "dataset: " + str(state.get("dataset")),
        "liked: " + str(int(state.get("liked") or 0)),
        "publish: " + str(state.get("publish")),
        "lora trained: " + str(bool(state.get("lora"))),
        "voice: " + str(bool(state.get("voice"))),
        "ocr: " + str(bool(state.get("ocr"))),
        "missing: " + "; ".join(missing(state)) or "none",
    ])
