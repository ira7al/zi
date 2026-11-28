"""Shared track options: the one place the bot, the desktop app and the web app read
from when they build a job.

Nothing here talks to Telegram, the network or the engine. It turns a plain dict of
choices into (a) the prompt text the engine renders from, and (b) the payload fields
the ACE-Step server accepts. Every option carries a status:

  live        a real parameter reaches the engine
  text        it changes the prompt wording only (no engine dial exists for it)
  coming      not wired yet; the UI shows it disabled with the reason

ACE-Step 1.5 `/release_task` accepts: prompt, lyrics, thinking, use_format, batch_size,
audio_duration, bpm, key_scale, vocal_language, inference_steps, guidance_scale, seed.
There is no negative prompt, no weirdness dial, no LoRA and no reference-audio field in
the generation path, which is why those are marked the way they are.
"""
import re

# ---------- option definitions (the UI reads this) ----------
OPTIONS = [
    {"key": "prompt", "label": "Description prompt", "kind": "text", "status": "live",
     "note": "What the track is. Your own words, or written from an idea."},
    {"key": "instrumental", "label": "Instrumental", "kind": "toggle", "status": "live", "default": True},
    {"key": "lyrics", "label": "Lyrics", "kind": "text", "status": "live",
     "note": "Full lyrics with [Intro]/[Verse]/[Chorus] tags. Empty means auto."},
    {"key": "style_tags", "label": "Style tags", "kind": "text", "status": "live",
     "note": "Short tags appended to the prompt, e.g. 'analog, tape hiss, 90s'."},
    {"key": "exclude", "label": "Exclude styles", "kind": "text", "status": "text",
     "note": "No negative prompt in the engine, so this is written into the prompt as avoid phrasing."},
    {"key": "weirdness", "label": "Weirdness", "kind": "int", "min": 0, "max": 100, "status": "text",
     "note": "No engine dial: low keeps the club structure, high asks for unexpected turns, in words."},
    {"key": "style_influence", "label": "Style influence", "kind": "int", "min": 0, "max": 100,
     "status": "live", "note": "Maps to guidance_scale, 3.0 at 0 and 12.0 at 100."},
    {"key": "title", "label": "Title", "kind": "text", "status": "live"},
    {"key": "seconds", "label": "Duration", "kind": "int", "min": 10, "max": 600, "status": "live"},
    {"key": "bpm", "label": "BPM", "kind": "int", "min": 60, "max": 180, "status": "live"},
    {"key": "key", "label": "Key", "kind": "text", "status": "live", "note": "e.g. F# minor"},
    {"key": "steps", "label": "Steps", "kind": "int", "min": 4, "max": 60, "status": "live"},
    {"key": "seed", "label": "Seed", "kind": "int", "status": "live", "note": "Empty means random."},
    {"key": "model", "label": "Model", "kind": "choice", "status": "live",
     "choices": ["turbo", "turbo-shift3"], "note": "XL appears once it is on the box."},
    {"key": "reference_audio", "label": "Reference audio", "kind": "file", "status": "coming",
     "note": "The server only takes a reference for continuation, not style.",
     "note_ar": "السيرفر بياخد مرجع للاستكمال بس، مش للستايل."},
    {"key": "lora", "label": "LoRA", "kind": "choice", "status": "coming",
     "note": "Mr Dorgham adapter is not trained yet.",
     "note_ar": "موديل Mr Dorgham لسه متدرّبش."},
    {"key": "cover", "label": "Cover / repaint", "kind": "action", "status": "coming",
     "note": "No repaint endpoint in this build; continuation already runs automatically on short renders.",
     "note_ar": "مفيش إعادة رسم في النسخة دي؛ الاستكمال بيشتغل لوحده على التراكات القصيرة."},
]
OPTION_BY_KEY = {o["key"]: o for o in OPTIONS}


def status_of(key):
    return OPTION_BY_KEY.get(key, {}).get("status", "coming")


# ---------- prompt building ----------
PROMPT_STYLES = {
    "melodic techno": {"label": "melodic techno", "bpm": 122, "key": "A minor",
        "mood": "bittersweet, late-night",
        "sound": "tight punchy kick, deep sub bass, emotional minor chord progression on a soft pluck, "
                 "lush atmospheric pads, hypnotic arpeggio, distant reverb vocal chops",
        "mix": "spacious mix, clean low mids, open top end"},
    "melodic house": {"label": "melodic house", "bpm": 124, "key": "F# major",
        "mood": "uplifting, emotional",
        "sound": "soft round kick, warm rolling bass, airy plucked lead, warm supersaw pads, gentle percussion",
        "mix": "polished club mix, crisp high end, clean low mids"},
    "progressive": {"label": "progressive house-techno", "bpm": 124, "key": "D minor",
        "mood": "patient, sunrise euphoria",
        "sound": "rolling bassline, crisp claps, slowly opening filter arpeggio, layered pads, festival riser",
        "mix": "wide stereo image, clean low mids, open top end"},
    "indie dance": {"label": "indie dance", "bpm": 120, "key": "E major",
        "mood": "playful, sun-soaked",
        "sound": "live-feel bass guitar groove, four-on-the-floor kick, funky guitar chops, analog synth stabs, warm claps",
        "mix": "warm analog mix, crisp high end"},
    "afro house": {"label": "deep afro house", "bpm": 122, "key": "G minor",
        "mood": "warm, hypnotic",
        "sound": "smooth deep kick, warm sub, layered djembe and shaker groove, soulful chord stabs, flute-like lead",
        "mix": "organic percussion up front, clean low mids"},
    "downtempo": {"label": "downtempo indie electronic", "bpm": 102, "key": "C major",
        "mood": "hazy, nostalgic",
        "sound": "soft round kick, warm electric bass, dreamy washed guitars, mellow keys, vinyl texture",
        "mix": "soft top end, warm low mids"},
    "peak techno": {"label": "peak-time techno", "bpm": 130, "key": "F minor",
        "mood": "relentless, peak-hour",
        "sound": "hard punchy kick, driving offbeat bass, hypnotic acid sequence, sharp hats, white-noise risers",
        "mix": "loud club mix, tight low end, crisp high end"},
}
STYLE_LOOKUP = [(("indie",), "indie dance"), (("afro",), "afro house"),
                (("downtempo", "ambient", "chill", "lofi", "lo-fi"), "downtempo"),
                (("progressive",), "progressive"), (("peak", "acid", "hard techno"), "peak techno"),
                (("melodic house",), "melodic house"), (("melodic techno", "techno"), "melodic techno"),
                (("house",), "melodic house")]
MOOD_VARIANTS = ["cinematic and patient", "hypnotic and driving", "warm and spacious"]
# a tap on "Another" should change the arrangement too, not only the adjectives
FOCUS_VARIANTS = ("the arpeggio carries the hook", "the bassline carries the groove",
                  "the pads carry the emotion", "the percussion carries the drive")
MIX_VARIANTS = ("spacious mix, clean low mids, open top end",
                "tight punchy mix, firm low end, airy top end",
                "warm analog mix, soft top end, wide stereo image")
BPM_RE = re.compile(r"\b(1[0-4]\d)\b")
KEY_RE = re.compile(r"\b(?:in\s+|key\s+(?:of\s+)?)([A-G][#b]?)\s*(minor|major|maj|m)?\b", re.I)
# A reference to a real act, label or song has no place in a prompt field. The old
# version cut everything up to the next comma, so "inspired by driving four-on-the-floor
# kick" lost a description that was never a name. Now a trigger phrase only removes a
# name-like span - capitalised words that are not music vocabulary - and when there is
# no name, the text is left exactly as he wrote it.
MUSIC_WORDS = {
    "melodic", "techno", "house", "dance", "indie", "afro", "downtempo", "ambient", "progressive",
    "trance", "disco", "funk", "soul", "jazz", "pop", "rock", "club", "track", "song", "beat",
    "drop", "kick", "bass", "bassline", "arpeggio", "arpeggios", "pad", "pads", "hat", "hats",
    "hi-hats", "structure", "bpm", "key", "minor", "major", "mood", "vibe", "style", "sound",
    "mix", "chorus", "verse", "intro", "outro", "build", "build-up", "breakdown", "groove",
    "percussion", "synth", "piano", "guitar", "vocal", "vocals", "male", "female", "driving",
    "punchy", "hypnotic", "emotional", "clean", "fresh", "dynamic", "crisp", "memorable",
    "warm", "dark", "deep", "soft", "hard", "peak", "late", "night", "summer", "analog",
    "four-on-the-floor", "rolling", "atmospheric", "cinematic", "uplifting", "energetic",
    "techno,", "the", "a", "an", "and", "with", "into", "like",
}

TRIGGERS = (r"in the style of", r"style of", r"similar(?:ly)?\s+(?:vibe\s+)?to", r"vibe of",
            r"sounds?\s+(?:a lot\s+)?like", r"inspired by", r"remix(?:ed)? of", r"cover(?:s)? of")

NAME_RE = re.compile(
    r"(?i:\b(?:" + "|".join(TRIGGERS) + r"))\s+"
    r"(?P<name>(?:[A-Z][\w'&.\-]*\s+){0,3}[A-Z][\w'&.\-]*)"
    r"(?P<tail>\s+(?:style|vibe|sound|type|kind|territory))?")
SIMPLE_RE = re.compile(r"(?i:\b(?:feat\.?|vs\.?|ft\.?))\s+"
                       r"(?P<name>(?:[A-Z][\w'&.\-]*\s+){0,3}[A-Z][\w'&.\-]*)")
DANGLING_RE = re.compile(r"(?i:\b(?:similar(?:ly)?\s+(?:vibe\s+)?to|in the style of|style of|"
                         r"vibe of|sounds?\s+like|inspired by|remix(?:ed)? of|cover(?:s)? of))"
                         r"\s*(?:style|vibe|sound|type|kind)?\b")


def name_from_span(span):
    """The name inside a removed span: 'similar vibe to Goom Gum style' -> 'Goom Gum'."""
    out = DANGLING_RE.sub(" ", span or "")
    out = re.sub(r"(?i)^\s*(?:feat\.?|ft\.?|vs\.?)\s+", "", out)
    out = re.sub(r"(?i)\b(style|vibe|sound|type|kind|territory)\b", " ", out)
    return re.sub(r"\s{2,}", " ", out).strip(" ,.;:-")


def looks_like_name(name):
    """A capitalised span that still carries at least one word music vocabulary does not explain."""
    words = [w for w in re.split(r"\s+", (name or "").strip()) if w]
    if not words:
        return False
    kept = [w for w in words if w.lower().strip(".,;:") not in MUSIC_WORDS]
    return bool(kept)


def clean_idea(text):
    """Drop a reference to a real act, label or song. Returns (text, removed spans).

    Only a name-like span goes, with its trigger phrase. A description after
    "inspired by" or "similar to" stays, because it was never a name.
    """
    removed, out = [], (text or "")

    def cut(m):
        if not looks_like_name(m.group("name")):
            return m.group(0)
        removed.append(m.group(0).strip())
        return " "

    out = NAME_RE.sub(cut, out)
    out = SIMPLE_RE.sub(cut, out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)          # no space left before punctuation
    out = re.sub(r",\s*,+", ", ", out)                 # and no doubled commas
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"^[,;:.\s]+|[,;:.\s]+$", "", out)
    return out.strip(), removed


ARABIC_RANGE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff]")


def has_non_latin(text):
    """True when the text carries a script the engine's English prompt should not hold."""
    return bool(ARABIC_RANGE.search(text or ""))


def _bars_for(seconds, bpm):
    """How many 4/4 bars fit in the requested length at this tempo."""
    try:
        bpm = int(bpm)
    except Exception:
        bpm = 122
    bpm = max(60, min(180, bpm))
    bar_seconds = 240.0 / bpm
    return max(8, int(round(float(seconds) / bar_seconds)))


# share of the track each section takes, in order
SECTIONS = (("intro", 0.12), ("build", 0.08), ("drop", 0.22), ("breakdown", 0.18),
            ("build", 0.08), ("second drop", 0.22), ("outro", 0.10))


def structure(seconds, bpm=122):
    """A section map in bars that adds up to the length asked for, not a fixed 176 bars."""
    total = _bars_for(seconds, bpm)
    counts = []
    for i, (name, share) in enumerate(SECTIONS):
        counts.append(max(4, int(round(total * share / 4.0)) * 4))
    diff = total - sum(counts)
    if diff:
        # give the remainder to the second drop (or take it from there), in whole bars
        counts[5] = max(4, counts[5] + diff)
    parts = []
    for (name, _), n in zip(SECTIONS, counts):
        parts.append(f"{name} {n}")
    text = ", ".join(parts) + f" bars (about {sum(counts)} bars at {bpm} BPM)"
    if seconds > 360:
        text += ", slow intro, long outro, same key and tempo throughout, no abrupt stops"
    return text


# what the free iTunes lookup returns (primaryGenreName) -> one of our style profiles
GENRE_STYLE = (("dance", "melodic house"), ("house", "melodic house"), ("techno", "melodic techno"),
               ("electronic", "melodic techno"), ("ambient", "downtempo"), ("downtempo", "downtempo"),
               ("alternative", "indie dance"), ("indie", "indie dance"), ("rock", "indie dance"),
               ("pop", "melodic house"), ("world", "afro house"), ("afro", "afro house"),
               ("hip-hop", "downtempo"), ("r&b", "downtempo"), ("soul", "downtempo"),
               ("jazz", "downtempo"), ("classical", "downtempo"))


def genre_to_style(genre):
    """Map a reference's genre label onto a style profile. None when it says nothing useful."""
    low = (genre or "").lower()
    for key, style in GENRE_STYLE:
        if key in low:
            return style
    return None


def pick_style(idea):
    """The style he named first wins: 'melodic techno and indie dance' is melodic techno."""
    low = (idea or "").lower()
    best, best_key = None, None
    for words, name in STYLE_LOOKUP:
        for w in words:
            i = low.find(w)
            if i < 0:
                continue
            key = (i, -len(w))
            if best_key is None or key < best_key:
                best, best_key = name, key
    return best or "melodic techno"


VOCAL_LINE = ("Lead vocal: close-miked male baritone, clear diction, sits just behind the drop, "
              "doubled in the chorus")


def build_prompt(idea, seconds=330, variant=0, instrumental=True, style=None):
    """A full ACE-Step prompt from a short idea, following the library's rules.

    `style` forces one of PROMPT_STYLES; the reference path uses it when a lookup
    has already worked out the style and the words alone would not.
    """
    clean, removed = clean_idea(idea or "")
    if has_non_latin(clean):
        # the engine reads an English prompt; a theme in another script only dilutes it
        removed = removed + ["a theme written in another script"]
        clean = ARABIC_RANGE.sub(" ", clean)
        clean = re.sub(r"\s{2,}", " ", clean).strip(" ,.;-")
    low = clean.lower()
    style = style if style in PROMPT_STYLES else pick_style(clean)
    prof = PROMPT_STYLES[style]
    m = BPM_RE.search(clean)
    bpm = int(m.group(1)) if m else prof["bpm"]
    km = KEY_RE.search(clean)
    if km:
        mode = (km.group(2) or "").lower()
        mode = "minor" if mode in ("m", "minor") else "major" if mode in ("major", "maj") else prof["key"].split()[-1]
        key = f"{km.group(1)} {mode}"
    else:
        key = prof["key"]
    dark = any(w in low for w in ("dark", "melancholy", "melancholic", "moody", "night", "sad", "deep"))
    mood = ("dark, " + prof["mood"]) if dark else prof["mood"]
    focus = None
    mix = prof["mix"]
    if variant:
        mood = MOOD_VARIANTS[variant % len(MOOD_VARIANTS)] + ", " + mood
        focus = FOCUS_VARIANTS[(variant // len(MOOD_VARIANTS)) % len(FOCUS_VARIANTS)]
        mix = MIX_VARIANTS[variant % len(MIX_VARIANTS)]
    theme = clean.strip().rstrip(".")
    voice = ("Instrumental, no vocals." if instrumental else VOCAL_LINE + ".")
    prompt = (f"{bpm} BPM {prof['label']}, {mood}, {key}, {prof['sound']}"
              + (f", {focus}" if focus else "") + f". "
              f"{voice} Structure in bars: {structure(seconds, bpm)}. {mix[0].upper() + mix[1:]}."
              + (f" Theme: {theme}." if theme else ""))
    sounds = [x.strip() for x in prof["sound"].split(",") if x.strip()][:3]
    summary = (f"{prof['label']}, {mood}, about {bpm} BPM ({bpm - 3}-{bpm + 3}), {key}, "
               f"{'instrumental' if instrumental else 'with vocals'}, "
               f"{', '.join(sounds)}")
    return {"prompt": prompt, "bpm": bpm, "key": key, "genre": prof["label"],
            "removed": removed, "style": style, "summary": summary}


# ---------- the text-level controls ----------
def apply_controls(prompt, spec):
    """Exclude, weirdness and style tags: wording only, appended to the prompt."""
    out = (prompt or "").strip().rstrip(".")
    tags = (spec.get("style_tags") or "").strip()
    if tags:
        out += f". Style tags: {tags}"
    excl = (spec.get("exclude") or "").strip()
    if excl:
        out += f". Avoid: {excl}"
    w = spec.get("weirdness")
    if isinstance(w, int):
        if w >= 70:
            out += ". Unexpected harmonic turns, unusual textures, experimental sound design"
        elif w <= 30:
            out += ". Familiar club structure, nothing experimental"
    return out + "."


def guidance_from_influence(value):
    """Style influence 0-100 -> guidance_scale 3.0-12.0 (the engine's real CFG dial)."""
    try:
        v = max(0, min(100, int(value)))
    except Exception:
        return None
    return round(3.0 + (v / 100.0) * 9.0, 1)


def engine_payload_fields(spec):
    """The subset of a spec that goes straight into /release_task."""
    out = {}
    if spec.get("bpm"):
        out["bpm"] = int(spec["bpm"])
    if spec.get("key"):
        out["key_scale"] = str(spec["key"])
    if spec.get("steps"):
        out["inference_steps"] = int(spec["steps"])
    if spec.get("seed") not in (None, "", -1):
        out["seed"] = int(spec["seed"])
    g = spec.get("guidance_scale")
    if g in (None, "") and spec.get("style_influence") is not None:
        g = guidance_from_influence(spec["style_influence"])
    if g not in (None, ""):
        out["guidance_scale"] = float(g)
    if spec.get("instrumental"):
        out["lyrics"] = "[inst]"
        out["instrumental"] = True
    else:
        out["instrumental"] = False
        if (spec.get("lyrics") or "").strip():
            out["lyrics"] = spec["lyrics"]
        lang = (spec.get("vocal_language") or spec.get("lang") or "en")
        if isinstance(lang, str) and lang.strip():
            out["vocal_language"] = lang.strip()[:8]
    return out


def normalize(spec):
    """A spec that both the bot and the apps can hand to the engine."""
    s = dict(spec or {})
    s.setdefault("lang", "en")
    s.setdefault("seconds", 330)
    s.setdefault("instrumental", True)
    if s.get("prompt") and not s.get("idea"):
        s["idea"] = s["prompt"]
    if s.get("idea"):
        s["idea"] = apply_controls(s["idea"], s)
    s.setdefault("genre", pick_style(s.get("idea", "")))
    s.setdefault("name", s["genre"])
    s.update(engine_payload_fields(s))
    return s

# ---------- Arabic (Egyptian) idea -> English prompt ----------
# He speaks Egyptian Arabic. The engine wants English prompt text, so a voice idea is
# translated with this lexicon: music vocabulary first, then the leftover Arabic is
# dropped from the prompt and reported back instead of being sent to the model.
AR_LEXICON = [
    ("ميلوديك تكنو", "melodic techno"), ("تكنو", "techno"), ("هاوس", "house"),
    ("بروجريسيف", "progressive"), ("افرو هاوس", "afro house"), ("أفرو", "afro"),
    ("اندي دانس", "indie dance"), ("إندي", "indie"), ("داون تيمبو", "downtempo"),
    ("هدوء", "calm"), ("هادي", "calm"), ("هادية", "calm"), ("غامق", "dark"),
    ("مظلم", "dark"), ("حزين", "melancholic"), ("حزينة", "melancholic"),
    ("مبسوط", "uplifting"), ("فرحان", "uplifting"), ("متفائل", "hopeful"),
    ("مشمس", "sunny"), ("دافي", "warm"), ("دافئ", "warm"), ("بارد", "cold"),
    ("ليلي", "late-night"), ("بالليل", "late-night"), ("الفجر", "sunrise"),
    ("الشروق", "sunrise"), ("الغروب", "sunset"), ("بحر", "sea"), ("البحر", "sea"),
    ("صحرا", "desert"), ("الصحرا", "desert"), ("جبل", "mountain"), ("سفر", "travel"),
    ("طريق", "drive"), ("سواقة", "drive"), ("عربية", "car"), ("رقص", "dance"),
    ("نادي", "club"), ("كلوب", "club"), ("حفلة", "party"), ("مهرجان", "festival"),
    ("سريع", "fast"), ("بطيء", "slow"), ("بطيئة", "slow"), ("قوي", "hard-hitting"),
    ("ناعم", "soft"), ("عميق", "deep"), ("واسع", "wide"), ("دافئ الصوت", "warm tone"),
    ("بيانو", "piano"), ("جيتار", "guitar"), ("كمان", "violin"), ("ناي", "flute"),
    ("طبول", "drums"), ("ايقاع", "percussion"), ("باص", "bass"), ("أرابيسك", "arabic scale"),
    ("شرقي", "middle-eastern"), ("مصري", "egyptian"), ("عود", "oud"),
    ("صوت ست", "female vocal"), ("صوت راجل", "male vocal"), ("كورال", "choir"),
    ("من غير غنا", "instrumental"), ("انسترومنتال", "instrumental"),
    ("حنين", "nostalgic"), ("ذكريات", "nostalgic"), ("وحدة", "lonely"),
    ("امل", "hope"), ("طاقة", "energy"), ("هدوء الليل", "quiet night"),
]


def has_arabic(text):
    return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))


AR_STOPWORDS = {"عايز", "عاوز", "عايزة", "و", "على", "ال", "في", "من", "مع", "يكون",
                "حاجة", "زي", "كده", "شوية", "كمان", "أوي", "جدا", "يعني", "بس", "او",
                "أو", "دا", "ده", "دي", "عشان", "مثل", "كدا"}


def to_english(text):
    """Egyptian Arabic idea -> English words, plus what could not be translated."""
    out, used = text or "", []
    for ar, en in AR_LEXICON:
        if " " in ar:                      # a phrase: plain substring is safe
            if ar in out:
                out = out.replace(ar, " " + en + " ")
                used.append(en)
        else:                              # a single word must stand alone, so that
            # "عامل" (doing) never matches "امل" (hope)
            # allow the Arabic prefixes that glue onto words: و (and), ال (the), ب, ل, ف, ك
            pat = (r"(?<![\u0600-\u06ff])[والفبك]{0,2}" + re.escape(ar)
                   + r"(?![\u0600-\u06ff])")
            if re.search(pat, out):
                out = re.sub(pat, " " + en + " ", out)
                used.append(en)
    leftover = [w for w in re.findall(r"[\u0600-\u06ff]+", out) if w not in AR_STOPWORDS]
    out = re.sub(r"[\u0600-\u06ff]+", " ", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" ,.;-")
    return out, leftover
