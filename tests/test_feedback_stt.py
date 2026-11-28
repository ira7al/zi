"""Feedback notes, the friendly unclear-input rule, Groq transcription and the transcript log."""
import json, os, sys, tempfile, unittest
from unittest import mock
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_assistant as za  # noqa: E402
from bot import zi_bot as zb  # noqa: E402
from tests.test_voice import FakeTG  # noqa: E402


class Resp:
    def __init__(self, d): self.d = d
    def read(self): return json.dumps(self.d).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Feedback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 5

    def test_ui_change_asks_are_feedback(self):
        self.assertTrue(za.is_feedback("خلي زرار البرومبت زائد مرجع"))
        self.assertTrue(za.is_feedback("شيل الزرار ده من القايمة"))
        self.assertFalse(za.is_feedback("إيه الناقص؟"))
        self.assertFalse(za.is_feedback("يعني إيه LoRA؟"))
        self.assertFalse(za.is_feedback("ازيك"))

    def test_feedback_is_saved_and_acknowledged(self):
        self.bot._llm_ready = True
        self.bot._assistant(5, "خلي زرار البرومبت زائد مرجع")
        self.assertIn("وصّلتها للمطوّر", self.bot.tg.sent[-1]["text"])
        line = open(os.path.join(self.tmp, "feedback_notes.jsonl"), encoding="utf-8").read().strip()
        self.assertIn("زرار البرومبت", json.loads(line)["text"])

    def test_never_the_blunt_line(self):
        self.assertIn("ممنوع تقول", za.SYSTEM)
        self.assertNotIn("مش فاهم الكلام ده", za.answer("blah blah", {}))
        self.assertIn("ما وصلنيش كويس", za.SYSTEM)
        self.assertIn("ما وصلنيش كويس", za.answer("blah blah", {}))


class Stt(unittest.TestCase):
    def test_groq_stt_request_and_result(self):
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "v.oga")
        open(f, "wb").write(b"OggS" + b"x" * 500)
        seen = {}

        def opener(req, timeout=0):
            seen["auth"] = req.get_header("Authorization")
            seen["ct"] = req.get_header("Content-type")
            seen["body"] = req.data
            return Resp({"text": "عايز تراك تكنو"})
        text, problem = za.transcribe_groq(f, "KEY", opener=opener)
        self.assertEqual(text, "عايز تراك تكنو")
        self.assertEqual(seen["auth"], "Bearer KEY")
        self.assertTrue(seen["ct"].startswith("multipart/form-data; boundary="))
        self.assertIn(b"whisper-large-v3-turbo", seen["body"])
        self.assertIn(b'filename="v.ogg"', seen["body"])
        self.assertIn(b'name="language"', seen["body"])

    def test_falls_to_second_model_then_none(self):
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "v.ogg")
        open(f, "wb").write(b"x" * 100)

        def opener(req, timeout=0):
            raise urllib.error.HTTPError("u", 404, "x", {}, None)
        text, problem = za.transcribe_groq(f, "K", opener=opener, sleep=lambda s: None)
        self.assertIsNone(text)
        self.assertIn("404", problem)

    def test_bot_prefers_groq_then_local_and_logs(self):
        tmp = tempfile.mkdtemp()
        bot = zb.Bot("T", out_root=tmp, work=tmp, make_track=lambda s: None)
        bot._llm_ready = True
        bot.groq_key = "K"
        with mock.patch.object(zb.ziassist, "transcribe_groq", lambda *a, **k: ("من جروك", "")):
            self.assertEqual(bot._transcribe("/x.oga"), "من جروك")
        bot._transcribe_local = lambda p: "من المحلي"
        with mock.patch.object(zb.ziassist, "transcribe_groq", lambda *a, **k: (None, "429")):
            self.assertEqual(bot._transcribe("/x.oga"), "من المحلي")
        log = open(os.path.join(tmp, "transcripts.log"), encoding="utf-8").read()
        self.assertIn("groq\tمن جروك", log)
        self.assertIn("local\tمن المحلي", log)


if __name__ == "__main__":
    unittest.main()
