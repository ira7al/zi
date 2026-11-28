"""Dry run: the spec the Telegram bot builds must carry every key the engine reads.

The engine lives in the notebook (make_track), so the contract is pinned here:
REQUIRED_SPEC_KEYS plus the length under every name a build may use. If a future
engine change needs another key, add it here and to Bot._normalize_spec.
"""
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


def make_bot(seen):
    """Bot whose make_track behaves like the notebook: it reads spec["duration"]."""
    def fake_make_track(spec, artist, writer, ts=None):
        for key in zi_bot.REQUIRED_SPEC_KEYS + ("duration", "duration_sec"):
            if key not in spec:
                raise KeyError(key)
        seen.append(dict(spec))
        return {"base": "x", "folder": tempfile.mkdtemp(), "title": spec["name"]}

    root = tempfile.mkdtemp()
    bot = zi_bot.Bot(token="X", out_root=root, work=root, make_track=fake_make_track)
    bot.owner = 7
    bot.tg = Rec()
    bot.state = {"offset": 0}
    bot.gpu_poll = 0.01
    bot.gpu_marker = None
    return bot


def update(text):
    return {"update_id": 1, "message": {"chat": {"id": 7}, "text": text}}


def callback(data):
    return {"update_id": 2, "callback_query": {"id": "c1", "message": {"chat": {"id": 7}}, "data": data}}


class BotSpecTest(unittest.TestCase):
    def test_builder_flow_produces_a_complete_spec(self):
        seen = []
        bot = make_bot(seen)
        bot._handle(update("/track"))
        bot._handle(callback("Indie Dance"))
        bot._handle(update("kitchen light"))
        bot._handle(callback("180"))
        bot._handle(callback("v:0"))
        bot._handle(callback("q:fast"))
        bot._handle(callback("go"))
        job = bot.jobs.get_nowait()
        spec = bot._normalize_spec(job[1])
        for key in zi_bot.REQUIRED_SPEC_KEYS + zi_bot.LENGTH_KEYS:
            self.assertIn(key, spec, key)
        self.assertEqual(spec["seconds"], 180)
        self.assertEqual(spec["duration"], 180)
        self.assertEqual(spec["quality"], "fast")
        self.assertFalse(spec["instrumental"])
        bot._mark_busy = lambda on: None
        bot.jobs.put((7, spec))
        bot._worker_step = None
        # run one worker turn synchronously
        bot.current = spec["name"]
        r = bot.make_track(spec, "Rahal", "Rahal")
        self.assertTrue(r["title"])

    def test_one_shot_spec_gets_aliases(self):
        bot = make_bot([])
        spec = bot._parse_spec("melodic techno, night drive, 300s, instrumental, high")
        spec = bot._normalize_spec(spec)
        self.assertEqual(spec["duration"], 300)
        self.assertEqual(spec["duration_sec"], 300)
        self.assertIn("idea", spec)

    def test_batch_items_are_normalised(self):
        bot = make_bot([])
        raw = '[{"name": "Night Drive", "genre": "melodic techno", "duration": 240, "quality": "high"}]'
        bot._batch_load(7, raw)
        job = bot.jobs.get_nowait()
        spec = job[1]
        self.assertEqual(spec["seconds"], 240)
        for key in zi_bot.REQUIRED_SPEC_KEYS:
            self.assertIn(key, spec, key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
