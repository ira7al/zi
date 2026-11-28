"""The optional free model: used when a key exists, never a reason for silence."""
import io, json, os, sys, tempfile, unittest, urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb          # noqa: E402
from bot import zi_assistant as za    # noqa: E402

STATE = {"build": "x", "engine": True, "rendering": None, "waiting": 0,
         "dataset": {"count": 4, "vocal": 2, "instrumental": 2, "unlabelled": 0},
         "liked": 1, "publish": {"youtube": False, "telegram": True},
         "lora": False, "voice": True, "ocr": True}
KEY = "AIza-not-a-real-key"


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append(text)
        return {"ok": True}

    def call(self, *a, **k):
        return {}

    def _note(self, *a, **k):
        pass


class LlmRequestTests(unittest.TestCase):
    def test_the_state_goes_in_and_the_key_stays_in_a_header(self):
        seen = {}

        def opener(req, timeout=None):
            seen["url"] = req.full_url
            seen["headers"] = {k.lower(): v for k, v in req.headers.items()}
            seen["body"] = json.loads(req.data)
            return FakeResp(json.dumps({"candidates": [{"content": {"parts": [{"text": "أهلاً"}]}}]}).encode())

        out = za.ask_llm("إيه الناقص", STATE, KEY, opener=opener)
        self.assertEqual(out, "أهلاً")
        self.assertNotIn(KEY, seen["url"])
        self.assertEqual(seen["headers"]["x-goog-api-key"], KEY)
        text = seen["body"]["contents"][0]["parts"][0]["text"]
        self.assertIn("مستر درغام", text)
        for jargon in ("ocr", "voice", "engine", "build"):
            self.assertNotIn(jargon, text.lower())
        self.assertIn("إيه الناقص", text)
        self.assertIn("بالمصري", seen["body"]["system_instruction"]["parts"][0]["text"])

    def test_no_secrets_in_the_state_block(self):
        block = za.context_block(STATE)
        self.assertNotIn(KEY, block)
        self.assertNotIn("token", block.lower())

    def test_no_key_means_no_call(self):
        called = []
        self.assertIsNone(za.ask_llm("سؤال", STATE, "", opener=lambda *a, **k: called.append(1)))
        self.assertEqual(called, [])

    def test_rate_limit_returns_none(self):
        err = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        self.assertIsNone(za.ask_llm("سؤال", STATE, KEY, opener=lambda *a, **k: (_ for _ in ()).throw(err)))

    def test_a_broken_response_returns_none(self):
        out = za.ask_llm("سؤال", STATE, KEY, opener=lambda *a, **k: FakeResp(b'{"candidates": []}'))
        self.assertIsNone(out)


class Gemini3Tests(unittest.TestCase):
    """gemini-3 thinking used to eat the whole token budget, so nothing came back."""

    def test_thinking_is_off_and_the_budget_is_generous(self):
        req = za.build_request("سؤال", STATE)
        gen = req["generationConfig"]
        self.assertEqual(gen["thinkingConfig"]["thinkingBudget"], 0)
        self.assertGreaterEqual(gen["maxOutputTokens"], 800)

    def test_the_default_model_is_the_one_that_answers(self):
        self.assertEqual(za.DEFAULT_MODEL, "gemini-3.1-flash-lite")
        self.assertEqual(za.VISION_MODEL, za.DEFAULT_MODEL)
        self.assertIn(za.DEFAULT_MODEL, za.GEMINI_URL.format(model=za.DEFAULT_MODEL))

    def test_thought_parts_are_not_the_answer(self):
        data = {"candidates": [{"content": {"parts": [
            {"text": "أفكر الأول", "thought": True},
            {"text": "أهلاً بيك"}]}}]}
        self.assertEqual(za.parse_response(data), "أهلاً بيك")

    def test_only_thoughts_means_no_answer(self):
        data = {"candidates": [{"content": {"parts": [{"text": "تفكير", "thought": True}]}}]}
        self.assertIsNone(za.parse_response(data))

    def test_an_empty_answer_is_none_so_the_fallback_speaks(self):
        data = {"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]}
        self.assertIsNone(za.parse_response(data))

    def test_a_model_that_refuses_thinking_is_retried_without_it(self):
        seen = []

        def opener(req, timeout=None):
            seen.append(json.loads(req.data))
            if len(seen) == 1:
                raise urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(b"{}"))
            return FakeResp(json.dumps({"candidates": [{"content": {"parts": [{"text": "تم"}]}}]}).encode())

        self.assertEqual(za.ask_llm("سؤال", STATE, KEY, opener=opener), "تم")
        self.assertIn("thinkingConfig", seen[0]["generationConfig"])
        self.assertNotIn("thinkingConfig", seen[1]["generationConfig"])

    def test_the_vision_call_uses_the_same_model(self):
        req = za.build_vision_request(b"jpeg")
        self.assertEqual(req["generationConfig"]["thinkingConfig"]["thinkingBudget"], 0)


class BotLlmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=None)
        self.bot.tg = FakeTG()
        self.bot.owner = 9

    def ask(self, q="إيه الناقص"):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "/ask " + q}})
        return self.bot.tg.sent[-1]

    def test_without_a_key_it_answers_from_the_state(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            self.bot._llm_ready = None
            self.bot._secret = lambda name: ""
            text = self.ask()
        self.assertIn("الإنجين", text)

    def test_with_a_key_the_model_answers(self):
        self.bot._llm_ready = True
        self.bot.llm_key = KEY
        self.bot.llm_model = "gemini-2.0-flash"
        with mock.patch.object(zb.ziassist, "ask_llm", lambda q, s, k, m: "رد من الموديل"):
            self.assertEqual(self.ask(), "رد من الموديل")

    def test_a_rate_limited_model_falls_back_to_the_grounded_answer(self):
        self.bot._llm_ready = True
        self.bot.llm_key = KEY
        with mock.patch.object(zb.ziassist, "ask_llm", lambda q, s, k, m: None):
            text = self.ask()
        self.assertIn("الإنجين", text)

    def test_the_key_is_never_printed_or_sent(self):
        out = io.StringIO()
        self.bot._llm_ready = True
        self.bot.llm_key = KEY
        with mock.patch("sys.stdout", out), mock.patch.object(zb.ziassist, "ask_llm", lambda *a, **k: None):
            self.ask()
        self.assertNotIn(KEY, out.getvalue())
        self.assertNotIn(KEY, "\n".join(self.bot.tg.sent))

    def test_the_key_comes_from_the_environment(self):
        with mock.patch.dict(os.environ, {"ZI_LLM_KEY": KEY, "ZI_LLM_MODEL": "gemini-2.5-flash"}):
            self.bot._llm_ready = None
            self.assertTrue(self.bot._llm())
            self.assertEqual(self.bot.llm_model, "gemini-2.5-flash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
