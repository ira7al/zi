"""The artist stripper: right span, and he always sees what went and why."""
import os, sys, tempfile, types, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb          # noqa: E402
from bot import zi_options as opt     # noqa: E402

HIS_PROMPT = ("Melodic techno and indie dance track inspired by driving four-on-the-floor kick, "
              "punchy rolling bassline, hypnotic synth arpeggios, and a memorable emotional hook, "
              "similar vibe to Goom Gum style, with fresh atmospheric pads, crisp hi-hats, and a "
              "dynamic build-up into a clean club drop, ~4:00 structure.")


class CleanTests(unittest.TestCase):
    def test_his_exact_prompt_loses_only_the_name(self):
        clean, removed = opt.clean_idea(HIS_PROMPT)
        self.assertEqual(removed, ["similar vibe to Goom Gum style"])
        self.assertIn("inspired by driving four-on-the-floor kick", clean)
        self.assertIn("punchy rolling bassline", clean)
        self.assertIn("~4:00 structure", clean)
        self.assertNotIn("Goom", clean)
        self.assertNotIn("Gum", clean)

    def test_a_descriptor_after_inspired_by_is_not_a_name(self):
        clean, removed = opt.clean_idea("techno inspired by punchy rolling bass and crisp hats")
        self.assertEqual(removed, [])
        self.assertEqual(clean, "techno inspired by punchy rolling bass and crisp hats")

    def test_real_names_are_still_removed(self):
        for text, span in (("techno in the style of Daft Punk, dark", "in the style of Daft Punk"),
                           ("deep house similar to Four Tet style, 120 bpm", "similar to Four Tet style"),
                           ("afro house feat. Some Singer, warm", "feat. Some Singer")):
            clean, removed = opt.clean_idea(text)
            self.assertEqual(removed, [span], text)
            self.assertNotIn(span.split()[-1], clean.replace("Daft", ""))

    def test_the_name_inside_a_span(self):
        self.assertEqual(opt.name_from_span("similar vibe to Goom Gum style"), "Goom Gum")
        self.assertEqual(opt.name_from_span("in the style of Daft Punk"), "Daft Punk")
        self.assertEqual(opt.name_from_span("feat. Some Singer"), "Some Singer")


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s, *a: None)
        self.tg = types.SimpleNamespace(sent=[])
        self.bot.tg = self.tg
        self.tg.send = lambda chat_id, text, keyboard=None, reply=None: self.tg.sent.append(
            {"text": text, "keyboard": keyboard})
        self.bot.owner = 9
        self.bot.builders[9] = {"step": "own_prompt",
                                "spec": {"genre": "melodic techno", "lang": "en", "seconds": 240,
                                         "quality": "high", "instrumental": True}}

    def send_prompt(self, text):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": text}})

    def joined(self):
        return "\n".join(m["text"] for m in self.tg.sent)

    def test_he_sees_the_removed_words_and_the_reason(self):
        self.send_prompt(HIS_PROMPT)
        note = next(m for m in self.tg.sent if "Removed from the prompt" in m["text"])
        self.assertIn('"similar vibe to Goom Gum style"', note["text"])
        self.assertIn("why", note["text"])
        self.assertIn("Real artist or track names never go in the prompt field", note["text"])
        self.assertTrue(note["text"].startswith("\u26a0\ufe0f"))
        flat = [b["callback_data"] for row in note["keyboard"] for b in row]
        self.assertIn("p:refname", flat)

    def test_the_options_screen_shows_the_cleaned_prompt(self):
        self.send_prompt(HIS_PROMPT)
        shown = [m for m in self.tg.sent if "Prompt:" in m["text"]][-1]["text"]
        self.assertIn("inspired by driving four-on-the-floor kick", shown)
        self.assertNotIn("Goom", shown)

    def test_nothing_removed_gets_a_tick(self):
        self.send_prompt("melodic techno, dark, punchy kick, 122 bpm")
        self.assertIn("\u2705", self.joined())
        self.assertNotIn("\u26a0\ufe0f", self.joined())

    def test_use_as_reference_turns_the_name_into_a_style(self):
        self.bot._itunes = lambda q: {"genre": "Dance", "artist": "Goom Gum", "track": "Desire"}
        self.send_prompt(HIS_PROMPT)
        self.bot._callback(9, "p:refname")
        shown = self.joined()
        self.assertIn("From your reference I understood", shown)
        self.assertIn("melodic house", self.bot.builders[9]["built"]["prompt"])
        self.assertNotIn("Goom", self.bot.builders[9]["built"]["prompt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
