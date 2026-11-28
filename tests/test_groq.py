"""Groq first, Gemini second, grounded answers last. Nothing real is called."""
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


def err(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


OK = {"choices": [{"message": {"content": " رد من جروك "}}]}


class GroqTests(unittest.TestCase):
    def test_request_shape_and_header(self):
        seen = {}

        def opener(req, timeout=0):
            seen["url"], seen["auth"] = req.full_url, req.get_header("Authorization")
            seen["body"] = json.loads(req.data)
            return Resp(OK)
        out = za.ask_groq("إيه الناقص؟", {"build": "x"}, "SECRET", opener=opener)
        self.assertEqual(out, "رد من جروك")
        self.assertEqual(seen["url"], "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer SECRET")
        self.assertEqual(seen["body"]["model"], "openai/gpt-oss-120b")
        self.assertNotIn("SECRET", seen["url"])
        self.assertEqual(seen["body"]["messages"][0]["role"], "system")

    def test_model_env_override(self):
        with mock.patch.dict(os.environ, {"ZI_GROQ_MODEL": "other-model"}):
            self.assertEqual(za.build_groq_request("q", {})["model"], "other-model")

    def test_429_backs_off_then_works(self):
        n = []

        def opener(req, timeout=0):
            n.append(1)
            if len(n) < 3:
                raise err(429)
            return Resp(OK)
        slept = []
        self.assertEqual(za.ask_groq("q", {}, "k", opener=opener, sleep=slept.append), "رد من جروك")
        self.assertEqual(len(slept), 2)

    def test_404_moves_to_the_fallback_model(self):
        tried = []

        def opener(req, timeout=0):
            m = json.loads(req.data)["model"]
            tried.append(m)
            if m == "openai/gpt-oss-120b":
                raise err(404)
            return Resp(OK)
        self.assertEqual(za.ask_groq("q", {}, "k", opener=opener, sleep=lambda s: None), "رد من جروك")
        self.assertEqual(tried, ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"])

    def test_allam_never_used(self):
        self.assertFalse(any("allam" in m for m in za.groq_models()))

    def test_429_forever_falls_through_and_key_not_printed(self):
        def opener(req, timeout=0):
            raise err(429)
        import io
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            self.assertIsNone(za.ask_groq("q", {}, "TOPSECRET", opener=opener, sleep=lambda s: None))
        self.assertNotIn("TOPSECRET", buf.getvalue())


class OrderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=tmp, work=tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 5
        self.bot._llm_ready = True
        self.bot.llm_key, self.bot.groq_key, self.bot.llm_model = "g", "q", "m"

    def run_q(self, groq, gem):
        with mock.patch.object(zb.ziassist, "ask_groq", lambda *a, **k: groq), \
             mock.patch.object(zb.ziassist, "ask_llm", lambda *a, **k: gem):
            self.bot._assistant(5, "ازيك")
        return self.bot.tg.sent[-1]["text"]

    def test_groq_wins(self):
        self.assertEqual(self.run_q("من جروك", "من جيميني"), "من جروك")

    def test_gemini_when_groq_fails(self):
        self.assertEqual(self.run_q(None, "من جيميني"), "من جيميني")

    def test_grounded_when_both_fail(self):
        t = self.run_q(None, None)
        self.assertTrue(t)
        self.assertNotIn("جيميني", t)


if __name__ == "__main__":
    unittest.main()
