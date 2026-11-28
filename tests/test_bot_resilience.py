"""Dry run: spec compatibility, GPU guard and failure reporting."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))
import zi_bot  # noqa: E402


class Rec:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append(text)
        return {}

    def photo(self, *a, **k):
        pass

    def audio(self, *a, **k):
        pass

    def call(self, *a, **k):
        return True

    def _note(self, *a, **k):
        pass

    def _thread(self, chat_id):
        return None


def make_bot(make_track=None):
    root = tempfile.mkdtemp()
    bot = zi_bot.Bot(token="X", out_root=root, work=root, make_track=make_track)
    bot.owner = 7
    bot.tg = Rec()
    bot.state = {"offset": 0}
    bot.gpu_poll = 0.01
    bot.gpu_marker = None
    return bot


class SpecCompatTest(unittest.TestCase):
    def test_unknown_length_key_falls_back_to_seconds(self):
        bot = make_bot()
        spec = bot._normalize_spec({"genre": "techno", "seconds": 200})
        self.assertIsInstance(spec, zi_bot.SpecDict)
        self.assertEqual(spec["duration"], 200)
        self.assertEqual(spec["render_duration"], 200)
        self.assertIn("render_duration", spec.missing)

    def test_unknown_key_returns_none_and_is_recorded(self):
        bot = make_bot()
        spec = bot._normalize_spec({"genre": "techno", "seconds": 120})
        self.assertIsNone(spec["something_new"])
        self.assertIn("something_new", spec.missing)


class GpuGuardTest(unittest.TestCase):
    def test_engine_process_detection(self):
        self.assertFalse(zi_bot.Bot._is_engine_process(str(os.getpid())))
        self.assertFalse(zi_bot.Bot._is_engine_process("999999"))
        real_open = open
        def fake_open(path, *a, **k):
            if path == "/proc/424242/cmdline":
                import io
                return io.BytesIO(b"python3\x00-m\x00acestep\x00api_server\x00")
            return real_open(path, *a, **k)
        import builtins
        builtins.open = fake_open
        try:
            self.assertTrue(zi_bot.Bot._is_engine_process("424242"))
        finally:
            builtins.open = real_open


class FailureReportingTest(unittest.TestCase):
    def test_failed_render_reports_type_and_message(self):
        def boom(spec, a, b, ts=None):
            raise KeyError("duration")
        bot = make_bot(boom)
        try:
            bot.make_track(bot._normalize_spec({"genre": "techno", "seconds": 120}), "Rahal", "Rahal")
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:200]}"
        self.assertIn("KeyError", msg)
        self.assertIn("duration", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
