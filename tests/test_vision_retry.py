"""Vision: model list, fallbacks, backoff. And edge-tts inside a running event loop."""
import asyncio, json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_assistant as za  # noqa: E402
from bot import zi_voice as zv  # noqa: E402


class Resp:
    def __init__(self, d): self.d = d
    def read(self): return json.dumps(self.d).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def http_error(code):
    import urllib.error
    return urllib.error.HTTPError("u", code, "x", {}, None)


class VisionRetry(unittest.TestCase):
    def setUp(self):
        za._models_cache.clear()

    def test_list_filters_to_content_models(self):
        data = {"models": [
            {"name": "models/gemini-3-flash-preview", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/gemini-2.5-flash-preview-tts", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemma-3", "supportedGenerationMethods": ["generateContent"]}]}
        got = za.list_models("k", opener=lambda req, timeout=0: Resp(data))
        self.assertEqual(got, ["gemini-3-flash-preview"])

    def test_env_model_first_then_fallbacks(self):
        with mock.patch.dict(os.environ, {"ZI_VISION_MODEL": "my-model, other"}):
            ms = za.vision_models(None)
        self.assertEqual(ms[:2], ["my-model", "other"])
        self.assertIn("gemini-flash-latest", ms)

    def test_retries_503_then_moves_on(self):
        calls = []

        def opener(req, timeout=0):
            calls.append(req.full_url)
            if "bad" in req.full_url:
                raise http_error(503)
            return Resp({"candidates": [{"content": {"parts": [{"text": "Some style words"}]}}]})
        slept = []
        text, problem = za.read_image_retry(b"img", "k", models=["bad", "good"], opener=opener, sleep=slept.append)
        self.assertEqual(text, "Some style words")
        self.assertEqual(len(slept), 1)
        self.assertEqual(sum("bad" in c for c in calls), 2)

    def test_all_fail_says_why(self):
        def opener(req, timeout=0):
            raise http_error(404)
        text, problem = za.read_image_retry(b"img", "k", models=["a", "b"], opener=opener, sleep=lambda s: None)
        self.assertIsNone(text)
        self.assertIn("404", problem)


class EdgeLoop(unittest.TestCase):
    def test_edge_uses_cli_even_inside_a_running_loop(self):
        out = os.path.join(tempfile.mkdtemp(), "a.mp3")

        def fake_cli(text, name, path):
            open(path, "wb").write(b"x" * 2000)

        async def inner():
            with mock.patch.object(zv, "_edge_cli", fake_cli):
                return zv._edge("hi", "ar-EG-ShakirNeural", out)
        try:
            import edge_tts  # noqa: F401
        except Exception:
            self.skipTest("edge_tts not installed here")
        self.assertEqual(asyncio.run(inner()), out)


if __name__ == "__main__":
    unittest.main()
