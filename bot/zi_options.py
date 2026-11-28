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
import json
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


# ---------- settings from his words (voice or text), no option buttons ----------
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_GO_WORDS = ("ولد", "يلا", "ابدأ", "ابدا", "ابدأ بقى", "generate", "go", "نفذ", "ابدأ يلا")


def is_go_word(text):
    t = re.sub(r"[\u064b-\u0652]", "", (text or "").translate(_AR_DIGITS))
    t = re.sub(r"[\s!.،]+", " ", t).strip().lower()
    return len(t) <= 14 and t in _GO_WORDS


def parse_spec_edits(text, spec=None):
    """Read settings out of a free message. Returns (changes dict, short Arabic notes).

    Only things he clearly said are changed. Anything else is left alone.
    """
    t = (text or "").translate(_AR_DIGITS)
    low = t.lower()
    ch, notes = {}, []
    if re.search(r"\[(intro|verse|chorus|bridge|outro|pre-chorus)[^\]]*\]", low):
        ch["lyrics"] = t.strip()
        ch["instrumental"] = False
        notes.append("بكلمات (الكلمات اللي بعتها)")
    elif re.search(r"من غير (كلام|كلمات|غنا|غناء|صوت)|بدون (كلام|كلمات|غناء|صوت)|موسيقى بس|instrumental|no vocals", low):
        ch["instrumental"] = True
        notes.append("موسيقى بس")
    elif re.search(r"بكلام|بكلمات|بغنا|بصوت|مع (كلام|كلمات|غنا|صوت)|with lyrics|vocals?\b|lyrics", low):
        ch["instrumental"] = False
        notes.append("بكلمات")
    m = re.search(r"(?:bpm|بي بي ام|بي بي إم)\s*(?:على|=|:)?\s*(\d{2,3})|(\d{2,3})\s*(?:bpm|بي بي ام|بي بي إم|ضربة)", low)
    if m:
        v = int(m.group(1) or m.group(2))
        if 60 <= v <= 180:
            ch["bpm"] = v
            notes.append(f"{v} BPM")
    m = re.search(r"\b([a-g][#b]?)\s*(major|minor|maj|min)\b", low)
    if m:
        ch["key"] = m.group(1).upper() + " " + ("minor" if m.group(2).startswith("min") else "major")
        notes.append("مقام " + ch["key"])
    secs = None
    if re.search(r"دقيقتين|دقيقتان", low):
        secs = 120
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:دقيقة|دقايق|دقيقه|min|minutes?)", low)
        if m:
            secs = int(float(m.group(1)) * 60)
        else:
            m = re.search(r"(\d+)\s*(?:ثانية|ثانيه|sec|seconds?)", low)
            if m:
                secs = int(m.group(1))
    if secs:
        secs = max(60, min(600, secs))
        ch["seconds"] = secs
        notes.append(f"{secs // 60}:{secs % 60:02d} دقيقة")
    for key, pat, label in (("weirdness", r"(?:weirdness|غرابة)\s*(\d{1,3})", "الغرابة"),
                            ("style_influence", r"(?:style influence|تأثير الستايل)\s*(\d{1,3})", "تأثير الستايل"),
                            ("steps", r"(?:steps|خطوات)\s*(\d{1,2})", "الخطوات"),
                            ("seed", r"(?:seed|سيد)\s*(\d+)", "السيد")):
        m = re.search(pat, low)
        if m:
            v = int(m.group(1))
            if key in ("weirdness", "style_influence"):
                v = max(0, min(100, v))
            if key == "steps":
                v = max(4, min(60, v))
            ch[key] = v if not (key == "seed" and v == 0) else None
            notes.append(f"{label} {v}")
    if "weirdness" not in ch:
        if re.search(r"أغرب|اغرب|غريب أكتر|غريب اكتر|more weird", low):
            ch["weirdness"] = 70
            notes.append("أغرب شوية")
        elif re.search(r"مش غريب|أهدى|اهدى|عادي أكتر|عادي اكتر", low):
            ch["weirdness"] = 20
            notes.append("أهدى وأعادي")
    if re.search(r"shift ?3|شيفت", low):
        ch["model"] = "turbo-shift3"
        notes.append("موديل shift3")
    for key, pat, label in (("title", r"(?:العنوان|title|سميه|اسمه)\s*[:=]?\s*([A-Za-z0-9][A-Za-z0-9 '\-]{1,60})", "العنوان"),
                            ("style_tags", r"(?:تاجات|tags?)\s*[:=]?\s*([A-Za-z0-9][A-Za-z0-9 ,'\-]{2,120})", "تاجات"),
                            ("exclude", r"(?:avoid|exclude|تجنب|تجنّب|شيل)\s*[:=]?\s*([A-Za-z][A-Za-z0-9 ,'\-]{2,80})", "هتجنب")):
        m = re.search(pat, t, re.I)
        if m:
            ch[key] = m.group(1).strip(" ,.-")
            notes.append(f"{label}: {ch[key]}")
    return ch, notes


def spec_summary(spec):
    """One short Egyptian line of what will be made."""
    s = spec or {}
    secs = int(s.get("seconds") or 330)
    parts = [s.get("genre") or s.get("name") or "تراك",
             "موسيقى بس" if s.get("instrumental", True) else "بكلمات",
             f"{secs // 60}:{secs % 60:02d} دقيقة"]
    if s.get("bpm"):
        parts.append(f"{s['bpm']} BPM")
    if s.get("key"):
        parts.append("مقام " + str(s["key"]))
    if s.get("title"):
        parts.append("العنوان " + str(s["title"]))
    if s.get("style_tags"):
        parts.append("تاجات: " + str(s["style_tags"])[:60])
    if s.get("exclude"):
        parts.append("من غير: " + str(s["exclude"])[:50])
    if s.get("weirdness") not in (None, 50):
        parts.append(f"غرابة {s['weirdness']}")
    if s.get("style_influence") not in (None, 50):
        parts.append(f"تأثير الستايل {s['style_influence']}")
    return "هعمل: " + "، ".join(str(x) for x in parts) + ". تمام؟"


# ---------- style reference from an uploaded track (tempo, key, brightness only) ----------
# Needs ffmpeg and numpy. Never reads tags, file names or lyrics, so no artist or track name can
# reach a prompt. A rough style hint, not genre recognition.
_ASR = 22050
_AN_FFT = 2048
_AHOP = 512
_AMAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_AMIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_ANAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def audio_available():
    import shutil
    import subprocess  # noqa: F401
    if not shutil.which("ffmpeg"):
        return False
    try:
        import numpy  # noqa: F401
    except Exception:
        return False
    return True


def _audio_decode(path, seconds=90):
    import subprocess
    import numpy as np
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-t", str(seconds), "-ac", "1", "-ar", str(_ASR),
                          "-f", "f32le", "-"], capture_output=True, timeout=120, check=True).stdout
    return np.frombuffer(out, dtype=np.float32)


def audio_analyze(path, samples=None):
    """Returns {bpm, key, brightness_hz, rms} or None when the audio is too short or unreadable."""
    import numpy as np
    try:
        y = samples if samples is not None else _audio_decode(path)
    except Exception:
        return None
    if y is None or len(y) < _ASR * 8:
        return None
    y = y.astype(np.float64)
    n = 1 + (len(y) - _AN_FFT) // _AHOP
    idx = np.arange(_AN_FFT)[None, :] + _AHOP * np.arange(n)[:, None]
    mag = np.abs(np.fft.rfft(y[idx] * np.hanning(_AN_FFT)[None, :], axis=1))
    freqs = np.fft.rfftfreq(_AN_FFT, 1.0 / _ASR)
    # tempo: autocorrelation of the onset envelope
    logm = np.log1p(mag * 10)
    env = np.maximum(0, np.diff(logm, axis=0)).sum(axis=1)
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    fps = _ASR / _AHOP
    best, best_score = None, -1e18
    for bpm in np.arange(70.0, 176.0, 0.5):
        lag = 60.0 / bpm * fps
        lo, hi = int(lag), int(lag) + 1
        if hi >= len(ac):
            continue
        v = ac[lo] * (hi - lag) + ac[hi] * (lag - lo)
        # a mild pull toward 120 so half and double time do not win by accident
        score = v * np.exp(-0.5 * (np.log2(bpm / 120.0) / 0.9) ** 2)
        if score > best_score:
            best, best_score = bpm, score
    # key: pitch-class energy against major and minor profiles
    band = (freqs >= 65) & (freqs <= 2000)
    pc = np.zeros(12)
    midi = np.round(69 + 12 * np.log2(freqs[band] / 440.0)).astype(int) % 12
    energy = (mag[:, band] ** 2).sum(axis=0)
    for k in range(12):
        pc[k] = energy[midi == k].sum()
    best_key, best_r = None, -2
    for mode, prof in (("major", _AMAJ), ("minor", _AMIN)):
        for tonic in range(12):
            r = np.corrcoef(pc, np.roll(prof, tonic))[0, 1]
            if r > best_r:
                best_r, best_key = r, f"{_ANAMES[tonic]} {mode}"
    cent = float(((mag * freqs[None, :]).sum(axis=1) / (mag.sum(axis=1) + 1e-9)).mean())
    return {"bpm": int(round(best)), "key": best_key, "brightness_hz": int(cent),
            "rms": float(np.sqrt((y ** 2).mean()))}


def audio_describe(res):
    """One Egyptian line of what was heard. No names, nothing but the measurements."""
    br = res["brightness_hz"]
    tone = "دافي وغامق" if br < 1500 else ("متوازن" if br < 2800 else "مضيء وحاد")
    punch = "هادي" if res["rms"] < 0.05 else ("قوي" if res["rms"] > 0.15 else "متوسط القوة")
    return f"سمعت منه: سرعة حوالي {res['bpm']} BPM، مقام {res['key']}، الجو {tone} و{punch}."


def audio_style_for(res, styles):
    """Nearest style profile by tempo, with the same mode (major/minor) preferred."""
    minor = "minor" in (res.get("key") or "")
    best, best_cost = None, 1e9
    for name, st in styles.items():
        cost = abs(float(st.get("bpm") or 120) - res["bpm"])
        if ("minor" in str(st.get("key", ""))) != minor:
            cost += 6
        if cost < best_cost:
            best, best_cost = name, cost
    return best


# ---------- private user records (build .49) ----------
# Profile basics of whoever opens the bot, plus the owner's library metadata, go to a PRIVATE GitHub repo.
# Only whitelisted fields are ever written, so a token or a path cannot leak into it.
USERS_NOTICE = "بنسجّل رقم تيليجرام واسمك وتاريخ دخولك وبيانات استخدامك في مكان خاص بصاحب البوت بس."
PROFILE_FIELDS = ("telegram_id", "username", "name", "language_code", "first_seen", "last_seen", "is_owner", "role", "plan")
TRACK_FIELDS = ("title", "genre", "prompt", "caption", "bpm", "key", "language", "instrumental",
                "actual_duration_sec", "quality", "seed", "created", "kept", "when")


def user_from_update(frm):
    """Profile basics from a Telegram `from` object; None when there is no id."""
    if not isinstance(frm, dict) or frm.get("id") is None:
        return None
    name = " ".join(x for x in (frm.get("first_name"), frm.get("last_name")) if x).strip()
    return {"telegram_id": frm["id"], "username": frm.get("username") or "", "name": name,
            "language_code": frm.get("language_code") or ""}


def note_user(users, prof, now, is_owner=False):
    """Add or refresh one profile in the dict. Returns (is_new, changed)."""
    if not prof:
        return False, False
    key = str(prof["telegram_id"])
    cur = users.get(key)
    if cur is None:
        users[key] = dict(prof, first_seen=now, last_seen=now, is_owner=bool(is_owner),
                          role="admin" if is_owner else "user", plan="owner" if is_owner else "free")
        return True, True
    changed = False
    if "plan" not in cur or "role" not in cur:      # records written before plans existed
        cur["role"] = "admin" if (is_owner or cur.get("is_owner")) else "user"
        cur["plan"] = "owner" if (is_owner or cur.get("is_owner")) else "free"
        changed = True
    for f in ("username", "name", "language_code"):
        if prof.get(f) and cur.get(f) != prof[f]:
            cur[f] = prof[f]
            changed = True
    if is_owner and not cur.get("is_owner"):
        cur["is_owner"] = True
        cur["role"], cur["plan"] = "admin", "owner"
        changed = True
    cur["last_seen"] = now          # kept in memory, written with the next change
    return False, changed


def clean_profile(p):
    return {k: p.get(k) for k in PROFILE_FIELDS if k in p}


def clean_track(meta, extra=None):
    out = {k: meta.get(k) for k in TRACK_FIELDS if isinstance(meta, dict) and meta.get(k) not in (None, "")}
    for k, v in (extra or {}).items():
        out[k] = v
    return out


def github_put(repo, token, path, content_bytes, message, opener=None, timeout=30):
    """Create or update one file through the contents API. Returns (ok, problem). The token goes in a header only."""
    import base64
    import urllib.error as _uerr
    import urllib.request as _req
    op = opener or _req.urlopen
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    hdr = {"Authorization": "Bearer " + token, "User-Agent": "zi-studio-bot/1.0",
           "Accept": "application/vnd.github+json"}
    sha = None
    try:
        with op(_req.Request(url, headers=hdr), timeout=timeout) as r:
            sha = json.loads(r.read()).get("sha")
    except _uerr.HTTPError as e:
        if e.code != 404:
            return False, "HTTP " + str(e.code)
    except Exception as e:
        return False, type(e).__name__
    body = {"message": message, "content": base64.b64encode(content_bytes).decode()}
    if sha:
        body["sha"] = sha
    try:
        req = _req.Request(url, data=json.dumps(body).encode(), method="PUT",
                           headers=dict(hdr, **{"Content-Type": "application/json"}))
        with op(req, timeout=timeout) as r:
            r.read()
        return True, ""
    except _uerr.HTTPError as e:
        return False, "HTTP " + str(e.code)
    except Exception as e:
        return False, type(e).__name__


def sync_private(repo, token, files, last_hashes, opener=None):
    """Push {path: text} files whose content changed since last_hashes. Returns (pushed, problems)."""
    import hashlib
    pushed, problems = [], []
    if not repo or not token:
        return pushed, ["no repo or token"]
    for path, text in sorted(files.items()):
        h = hashlib.md5(text.encode("utf-8")).hexdigest()
        if last_hashes.get(path) == h:
            continue
        ok, why = github_put(repo, token, path, text.encode("utf-8"), "sync " + path, opener=opener)
        if ok:
            last_hashes[path] = h
            pushed.append(path)
        else:
            problems.append(path + ": " + why)
    return pushed, problems
