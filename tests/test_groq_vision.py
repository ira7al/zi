"""Vision through Groq first, Gemini second, honest failure last. Nothing real is called."""
import json, os, sys, tempfile, unittest
from unittest import mock
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_assistant as za  # noqa: E402
from bot import zi_bot as zb  # noqa: E402


class Resp:
    def __init__(self, d): self.d = d
    def read(self): return json.dumps(self.d).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def err(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


OK = {"choices": [{"message": {"content": "melodic techno, 122 bpm"}}]}


class GroqVision(unittest.TestCase):
    def test_request_shape(self):
        seen = {}

        def opener(req, timeout=0):
            seen["b"] = json.loads(req.data)
            seen["ua"] = req.get_header("User-agent")
            seen["auth"] = req.get_header("Authorization")
            return Resp(OK)
        text, problem = za.read_image_groq(b"\xff\xd8img", "K", opener=opener)
        self.assertEqual(text, "melodic techno, 122 bpm")
        b = seen["b"]
        self.assertEqual(b["model"], "qwen/qwen3.8-27b")
        self.assertIn("max_completion_tokens", b)
        self.assertNotIn("max_tokens", b)
        parts = b["messages"][0]["content"]
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertTrue(seen["ua"] and "python" not in seen["ua"].lower())
        self.assertEqual(seen["auth"], "Bearer K")

    def test_429_retries_then_fails_honestly(self):
        def opener(req, timeout=0):
            raise err(429)
        slept = []
        text, problem = za.read_image_groq(b"x", "K", opener=opener, sleep=slept.append)
        self.assertIsNone(text)
        self.assertIn("429", problem)
        self.assertEqual(len(slept), 2)

    def test_prompt_has_no_names(self):
        self.assertNotRegex(za.VISION_PROMPT.lower(), r"daft|drake|beyonc")


class Order(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s: None)
        self.bot._llm_ready = True
        self.bot.llm_key, self.bot.groq_key, self.bot.llm_model = "g", "q", "m"
        self.img = os.path.join(self.tmp, "i.jpg")
        open(self.img, "wb").write(b"x" * 100)

    def test_groq_first(self):
        with mock.patch.object(zb.ziassist, "read_image_groq", lambda *a, **k: ("from groq", "")), \
             mock.patch.object(zb.ziassist, "read_image_retry", lambda *a, **k: ("from gemini", "")):
            self.assertEqual(self.bot._vision_text(self.img), "from groq")

    def test_gemini_second(self):
        with mock.patch.object(zb.ziassist, "read_image_groq", lambda *a, **k: (None, "groq: 503")), \
             mock.patch.object(zb.ziassist, "read_image_retry", lambda *a, **k: ("from gemini", "")):
            self.assertEqual(self.bot._vision_text(self.img), "from gemini")

    def test_both_fail_returns_none(self):
        with mock.patch.object(zb.ziassist, "read_image_groq", lambda *a, **k: (None, "groq: 503")), \
             mock.patch.object(zb.ziassist, "read_image_retry", lambda *a, **k: (None, "m: 404")):
            self.assertIsNone(self.bot._vision_text(self.img))
            self.assertIn("groq: 503", self.bot.vision_problem)

    def test_groq_only_key_works(self):
        self.bot.llm_key = ""
        with mock.patch.object(zb.ziassist, "read_image_groq", lambda *a, **k: ("from groq", "")):
            self.assertEqual(self.bot._vision_text(self.img), "from groq")


if __name__ == "__main__":
    unittest.main()
