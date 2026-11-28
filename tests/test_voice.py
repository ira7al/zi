"""Voice notes: Arabic in, an English prompt out. Transcription is faked, no audio needed."""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402
from bot import zi_options as opt  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent, self.calls, self.uploads = [], [], []
        self.thread_of = None

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"chat_id": chat_id, "text": text, "keyboard": keyboard})
        return {"ok": True}

    def call(self, *a, **k):
        self.calls.append((a, k))
        return {"file_path": "voice/file_1.oga"}

    def audio(self, *a, **k):
        return {"ok": True}

    def photo(self, *a, **k):
        return {"ok": True}

    def _upload(self, *a, **k):
        return {"ok": True}

    def _note(self, *a, **k):
        pass


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 5
        self.bot._download_voice = lambda v: "/tmp/fake.oga"
        self.heard = None
        self.bot._transcribe = lambda p: self.heard

    def voice(self):
        self.bot._handle({"message": {"chat": {"id": 5, "type": "private"}, "from": {"id": 5},
                                      "voice": {"file_id": "abc", "file_unique_id": "u1"}}})

    def texts(self):
        return "\n".join(m["text"] for m in self.bot.tg.sent)

    def test_arabic_idea_becomes_an_english_prompt_draft(self):
        self.heard = "عايز تكنو غامق وحزين بالليل على البحر"
        self.voice()
        out = self.texts()
        self.assertIn("Heard: عايز تكنو", out)
        self.assertIn("In English: techno dark melancholic late-night sea", out)
        self.assertIn("Prompt (", out)          # the draft for approval
        self.assertIn("122 BPM melodic techno", out)
        self.assertIn("Theme: techno dark melancholic late-night sea", out)

    def test_english_voice_goes_straight_to_a_draft(self):
        self.heard = "afro house, warm sunset, 121 bpm"
        self.voice()
        out = self.texts()
        self.assertIn("Heard: afro house", out)
        self.assertNotIn("In English:", out)
        self.assertIn("121 BPM deep afro house", out)

    def test_voice_inside_the_ai_step_asks_for_approval(self):
        self.bot._track(5, "")
        self.bot._callback(5, "p:ai")
        self.heard = "ميلوديك تكنو حزين"
        self.voice()
        self.assertIn("Prompt (", self.texts())
        self.assertEqual(self.bot.builders[5]["step"], "ai_review")

    def test_no_transcription_says_what_to_install(self):
        self.heard = None
        self.voice()
        out = self.texts()
        self.assertIn("faster-whisper", out)
        self.assertIn("pip install", out)

    def test_arabic_without_music_words_asks_for_another_try(self):
        self.heard = "السلام عليكم ازيك عامل ايه"
        self.voice()
        self.assertIn("could not map any of it", self.texts())

    def test_lexicon_keeps_unknown_words_out_of_the_prompt(self):
        en, leftover = opt.to_english("عايز حاجة زي موسيقى الافلام")
        self.assertNotIn("موسيقى", en)
        self.assertIn("موسيقى", leftover)


if __name__ == "__main__":
    unittest.main(verbosity=2)
