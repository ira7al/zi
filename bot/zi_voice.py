"""Free text to speech for the bot's spoken replies.

No key, no account. edge-tts (Microsoft Edge's public voices) first, because it has a
real Egyptian Arabic voice and sounds like a person; gTTS second, as a plain fallback.
Both need internet, which the notebook has. When neither is installed, or the request
fails, speak() returns None and the bot sends text only - it never blocks a reply.

Telegram plays a real voice note only from OGG/Opus, so the mp3 is converted with
ffmpeg when ffmpeg is on the box; without it the mp3 goes out as an audio file.
"""
import asyncio
import os
import re
import shutil
import subprocess
import time

# Shakir is the male Egyptian voice; Salma is the female one, used if Shakir is gone.
VOICE = os.environ.get("ZI_TTS_VOICE", "ar-EG-ShakirNeural").strip() or "ar-EG-ShakirNeural"
FALLBACK_VOICES = ("ar-EG-ShakirNeural", "ar-EG-SalmaNeural", "ar-SA-HamedNeural")
MAX_CHARS = 700


def clean_for_speech(text):
    """Plain words for the ear: no markdown, no links, no button labels."""
    s = text or ""
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[*_`#>|]+", " ", s)
    s = re.sub(r"^\s*[-•]\s*", "", s, flags=re.M)
    s = re.sub(r"[\[\](){}]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > MAX_CHARS:
        cut = s[:MAX_CHARS]
        dot = max(cut.rfind("."), cut.rfind("؟"), cut.rfind("!"), cut.rfind("\n"))
        s = cut[:dot + 1] if dot > 120 else cut
    return s.strip()


def have_edge():
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


def have_gtts():
    try:
        from gtts import gTTS  # noqa: F401
        return True
    except Exception:
        return False


def have_ffmpeg():
    return bool(shutil.which("ffmpeg"))


def engines():
    """What is installed on this box, for /diag and for the honest install note."""
    return {"edge-tts": have_edge(), "gTTS": have_gtts(), "ffmpeg": have_ffmpeg()}


def _edge(text, voice, out):
    try:
        import edge_tts
    except Exception:
        return None
    async def run(name):
        com = edge_tts.Communicate(text, name)
        await com.save(out)
    for name in (voice,) + tuple(v for v in FALLBACK_VOICES if v != voice):
        try:
            asyncio.run(run(name))
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                return out
        except Exception as e:
            print("edge-tts", name, "failed:", type(e).__name__)
    return None


def _gtts(text, out):
    try:
        from gtts import gTTS
    except Exception:
        return None
    for tld in ("com.eg", "com"):
        try:
            gTTS(text=text, lang="ar", tld=tld).save(out)
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                return out
        except Exception as e:
            print("gTTS", tld, "failed:", type(e).__name__)
    return None


def to_voice_note(mp3, out_dir):
    """mp3 -> ogg/opus, which is the only thing Telegram shows as a voice note."""
    if not have_ffmpeg():
        return None
    ogg = os.path.splitext(mp3)[0] + ".ogg"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3,
                        "-c:a", "libopus", "-b:a", "48k", "-ar", "48000", "-ac", "1", ogg],
                       check=True, timeout=120)
        if os.path.exists(ogg) and os.path.getsize(ogg) > 1000:
            return ogg
    except Exception as e:
        print("ffmpeg failed:", type(e).__name__)
    return None


def speak(text, out_dir, voice=None):
    """Return {"path", "voice_note", "engine"} for the audio, or None if nothing worked."""
    words = clean_for_speech(text)
    if not words:
        return None
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + str(int(time.time() * 1000) % 1000)
    mp3 = os.path.join(out_dir, "say_" + stamp + ".mp3")
    made, engine = None, ""
    if have_edge():
        made = _edge(words, (voice or VOICE).strip() or VOICE, mp3)
        engine = "edge-tts" if made else ""
    if not made and have_gtts():
        made = _gtts(words, mp3)
        engine = "gTTS" if made else ""
    if not made:
        return None
    ogg = to_voice_note(made, out_dir)
    if ogg:
        try:
            os.remove(made)
        except Exception:
            pass
        return {"path": ogg, "voice_note": True, "engine": engine}
    return {"path": made, "voice_note": False, "engine": engine}
