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
     "note": "The server only takes a reference for continuation, not style."},
    {"key": "lora", "label": "LoRA", "kind": "choice", "status": "coming",
     "note": "Mr Dorgham adapter is not trained yet."},
    {"key": "cover", "label": "Cover / repaint", "kind": "action", "status": "coming",
     "note": "No repaint endpoint in this build; continuation already runs automatically on short renders."},
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
BPM_RE = re.compile(r"\b(1[0-4]\d)\b")
KEY_RE = re.compile(r"\b(?:in\s+|key\s+(?:of\s+)?)([A-G][#b]?)\s*(minor|major|maj|m)?\b", re.I)
# a reference to a real act, label or song has no place in a prompt field
BANNED_PATTERNS = [re.compile(p, re.I) for p in (
    r"in the style of[^,.;]*", r"sounds? (?:a lot )?like[^,.;]*", r"similar to[^,.;]*",
    r"inspired by[^,.;]*", r"cover(?:s)? of[^,.;]*", r"remix of[^,.;]*",
    r"\bfeat\.?[^,.;]*", r"\bvs\.?\s[^,.;]*")]


def clean_idea(text):
    """Drop anything that names a real act, label or song. Returns (text, removed)."""
    removed, out = [], text or ""
    for rx in BANNED_PATTERNS:
        removed += [m.strip() for m in rx.findall(out)]
        out = rx.sub(" ", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" ,.;-")
    return out, removed


def structure(seconds):
    if seconds <= 180:
        return "intro 16, build 8, drop 24, breakdown 16, second drop 24, outro 8 bars"
    base = "intro 32, build 16, drop 32, breakdown 32, build 16, second drop 32, outro 16 bars"
    if seconds > 360:
        base += ", slow intro, long outro, same key and tempo throughout, no abrupt stops"
    return base


def pick_style(idea):
    low = (idea or "").lower()
    for words, name in STYLE_LOOKUP:
        if any(w in low for w in words):
            return name
    return "melodic techno"


def build_prompt(idea, seconds=330, variant=0):
    """A full ACE-Step prompt from a short idea, following the library's rules."""
    clean, removed = clean_idea(idea or "")
    low = clean.lower()
    style = pick_style(clean)
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
    if variant:
        mood = MOOD_VARIANTS[variant % len(MOOD_VARIANTS)] + ", " + mood
    theme = clean.strip().rstrip(".")
    prompt = (f"{bpm} BPM {prof['label']}, {mood}, {key}, {prof['sound']}. "
              f"Structure in bars: {structure(seconds)}. {prof['mix'][0].upper() + prof['mix'][1:]}."
              + (f" Theme: {theme}." if theme else ""))
    return {"prompt": prompt, "bpm": bpm, "key": key, "genre": prof["label"],
            "removed": removed, "style": style}


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
    elif (spec.get("lyrics") or "").strip():
        out["lyrics"] = spec["lyrics"]
        out["instrumental"] = False
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
