"""The /track quick path: remember the last settings, offer them back, render again in one tap."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402
from bot import zi_options as opt  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"text": text, "keyboard": keyboard})
        return {"ok": True}

    def call(self, *a, **k):
        return {}

    def _note(self, *a, **k):
        pass


class QuickPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda spec, *a: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 9
        self.bot.gpu_marker = None
        self.bot._gpu_busy = lambda: None

    def text(self):
        return self.bot.tg.sent[-1]["text"]

    def keys(self):
        return [b["callback_data"] for row in (self.bot.tg.sent[-1].get("keyboard") or []) for b in row]

    def enqueue(self, **over):
        spec = {"genre": "melodic techno", "name": "melodic techno", "idea": "122 BPM melodic techno",
                "seconds": 300, "quality": "high", "instrumental": True}
        spec.update(over)
        self.bot._enqueue(9, spec)

    def test_no_quick_path_before_the_first_track(self):
        self.bot._track(9, "")
        self.assertNotIn("last", self.keys())

    def test_last_settings_come_back_as_one_button(self):
        self.enqueue()
        self.bot._track(9, "")
        self.assertIn("last", self.keys())
        self.assertIn("Last: melodic techno, 5:00, instrumental", " ".join(
            b["text"] for row in self.bot.tg.sent[-1]["keyboard"] for b in row))

    def test_one_tap_reopens_the_same_settings(self):
        self.enqueue()
        self.bot._callback(9, "last")
        self.assertIn("Ready: melodic techno | 300s | instrumental", self.text())
        self.assertIn("go", self.keys())

    def test_generate_from_the_quick_path_queues_the_same_track(self):
        self.enqueue()
        self.bot._callback(9, "last")
        self.bot._callback(9, "go")
        self.assertIn("اتحط في الطابور", self.text())
        queued = self.bot.jobs.get_nowait()[1]
        self.assertEqual(queued["seconds"], 300)
        self.assertEqual(queued["genre"], "melodic techno")

    def test_track_again_does_the_same(self):
        self.enqueue()
        self.bot._track(9, "again")
        self.assertIn("Ready: melodic techno", self.text())

    def test_nothing_saved_yet(self):
        self.bot._callback(9, "last")
        self.assertIn("مفيش إعدادات محفوظة لسه", self.text())


class VariantTests(unittest.TestCase):
    def test_twelve_different_prompts_from_one_idea(self):
        prompts = [opt.build_prompt("melodic techno, night drive", 330, v)["prompt"] for v in range(12)]
        self.assertEqual(len(set(prompts)), 12)
        for p in prompts:
            self.assertIn("Structure in bars", p)
            self.assertIn("122 BPM", p)
            self.assertFalse(opt.has_non_latin(p))


if __name__ == "__main__":
    unittest.main(verbosity=2)
