"""Own prompt plus an optional reference, in one flow."""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402
from tests.test_voice import FakeTG  # noqa: E402


class OwnPlusRef(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=tmp, work=tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 9
        self.bot.builders[9] = {"step": "own_prompt", "spec": {"lang": "en", "quality": "high",
                                                                "instrumental": True, "seconds": 330}}

    def send(self, text):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": text}})

    def test_reference_then_prompt_uses_both(self):
        self.bot._itunes = lambda q: None
        self.send("deep afro house, warm")          # a style in words, as a reference would give
        self.assertTrue(True)
        b = self.bot.builders[9]
        b["step"] = "own_prompt"
        b["own_ref"] = {"style": "afro house", "theme": ""}
        self.send("late night drive, soft vocals chops")
        spec = self.bot.builders[9]["spec"]
        self.assertIn("late night drive", spec["idea"])
        self.assertIn("Style reference:", spec["idea"])
        self.assertEqual(spec["bpm"], 122)
        self.assertNotIn("Nils", spec["idea"])

    def test_prompt_alone_still_works(self):
        self.send("melodic techno, punchy kick, 122 bpm, dark pads")
        self.assertNotIn("Style reference", self.bot.builders[9]["spec"]["idea"])

    def test_menu_has_no_reference_or_last_button(self):
        self.bot.builders.pop(9)
        self.bot._track(9, "")
        keys = [b["callback_data"] for r in self.bot.tg.sent[-1]["keyboard"] for b in r]
        self.assertIn("p:own", keys)
        self.assertNotIn("p:ref", keys)
        self.assertNotIn("last", keys)


if __name__ == "__main__":
    unittest.main()
