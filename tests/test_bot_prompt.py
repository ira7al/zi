"""The two prompt paths: your own prompt, and a prompt the bot writes from an idea.

Rule-based builder checked against the Prompt Library rules (BPM and key stated, sound
and mix descriptors, structure map in bars, theme last, no real artist or track names).
No network: from the repo root, python3 tests/test_bot_prompt.py
"""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []
        self.uploads = []
        self.log = []
        self.calls = []
        self.thread_of = None

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"chat_id": chat_id, "text": text, "keyboard": keyboard})
        return {"ok": True}

    def audio(self, chat_id, path, caption=None):
        return {"ok": True}

    def photo(self, chat_id, path, caption=None):
        return {"ok": True}

    def _upload(self, *a, **k):
        return {"ok": True}

    def _note(self, *a, **k):
        pass

    def call(self, *a, **k):
        self.calls.append((a, k))
        return {"ok": True}


def buttons(msg):
    return [b.get("callback_data", "") for row in (msg["keyboard"] or []) for b in row]


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda spec: spec)
        self.bot.tg = FakeTG()
        self.bot.owner = 7
        self.chat = 7

    def msg(self, text):
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat}, "text": text}})

    def tap(self, data):
        self.bot._callback(self.chat, data)

    # ---- the builder itself ----
    def test_prompt_has_the_library_shape(self):
        p = zb.build_prompt("dark melodic techno for a night drive", 330)
        self.assertIn("122 BPM", p["prompt"])
        self.assertIn("G minor", p["prompt"])
        self.assertIn("Structure in bars:", p["prompt"])
        self.assertIn("clean low mids", p["prompt"])
        self.assertIn("Theme: dark melodic techno for a night drive", p["prompt"])
        self.assertEqual(p["bpm"], 122)
        self.assertTrue(p["prompt"].endswith("."))

    def test_bpm_and_key_from_the_idea_win(self):
        p = zb.build_prompt("indie dance, 118 bpm, in F# major, sunny", 240)
        self.assertEqual(p["bpm"], 118)
        self.assertEqual(p["key"], "F# major")
        self.assertIn("indie dance", p["prompt"])

    def test_long_tracks_get_the_long_form_suffix(self):
        short = zb.build_prompt("techno", 180)["prompt"]
        long = zb.build_prompt("techno", 420)["prompt"]
        self.assertNotIn("long outro", short)
        self.assertIn("long outro", long)

    def test_real_artist_references_are_removed(self):
        p = zb.build_prompt("melodic techno in the style of Some Famous DJ, dark, 124 bpm", 330)
        self.assertNotIn("Some Famous DJ", p["prompt"])
        self.assertIn("in the style of", " ".join(p["removed"]).lower())

    def test_another_gives_a_different_prompt(self):
        a = zb.build_prompt("melodic techno", 330, 0)["prompt"]
        b = zb.build_prompt("melodic techno", 330, 1)["prompt"]
        self.assertNotEqual(a, b)
        self.assertIn("hypnotic and driving", b)

    # ---- the flow ----
    def test_track_offers_style_own_and_ai(self):
        self.msg("/track")
        data = buttons(self.bot.tg.sent[-1])
        self.assertIn("p:own", data)
        self.assertIn("p:ai", data)
        self.assertIn("Melodic Techno", data)

    def test_own_prompt_path_reaches_the_confirm(self):
        self.msg("/track")
        self.tap("p:own")
        self.assertIn("ابعت البرومبت", self.bot.tg.sent[-1]["text"])
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat},
                                      "text": "124 BPM melodic house, uplifting, F# major, airy pluck, long intro"}})
        self.assertIn("هعمل:", self.bot.tg.sent[-1]["text"])
        self.assertEqual(sorted(buttons(self.bot.tg.sent[-1])), ["ask", "go"])
        text = self.bot.tg.sent[-1]["text"]
        self.assertIn("124 BPM melodic house", text)
        spec = self.bot.builders[self.chat]["spec"]
        self.assertIn("124 BPM melodic house", spec["idea"])
        self.assertEqual(spec["bpm"], 124)
        self.assertEqual(spec["key"], "F# major")

    def test_ai_path_shows_the_prompt_then_use_then_length(self):
        self.msg("/track")
        self.tap("p:ai")
        self.assertIn("قولي الفكرة", self.bot.tg.sent[-1]["text"])
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat},
                                      "text": "something dark and hypnotic for a late drive"}})
        shown = self.bot.tg.sent[-1]
        self.assertIn("124 BPM", shown["text"])
        self.assertIn("Structure in bars", shown["text"])
        self.assertEqual(sorted(buttons(shown)), ["ask", "p:again", "p:edit", "p:ref", "p:use"])
        self.tap("p:again")
        self.assertNotEqual(self.bot.tg.sent[-1]["text"], shown["text"])
        self.tap("p:use")
        self.assertIn("هعمل:", self.bot.tg.sent[-1]["text"])
        self.tap("o:sec")
        self.assertIn("الطول؟", self.bot.tg.sent[-1]["text"])
        self.tap("330")
        self.tap("v:1")
        self.tap("q:high")
        spec = self.bot.builders[self.chat]["spec"]
        self.assertIn("Structure in bars", spec["idea"])
        self.assertEqual(spec["bpm"], 124)

    def test_edit_replaces_the_generated_prompt(self):
        self.msg("/track")
        self.tap("p:ai")
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat}, "text": "afro house sunset"}})
        self.tap("p:edit")
        self.assertIn("نسختك", self.bot.tg.sent[-1]["text"])
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat},
                                      "text": "121 BPM deep afro house, warm, G minor, djembe groove, long intro"}})
        spec = self.bot.builders[self.chat]["spec"]
        self.assertEqual(spec["idea"], "121 BPM deep afro house, warm, G minor, djembe groove, long intro")

    # ---- the options screen ----
    def _to_options(self):
        self.msg("/track")
        self.tap("p:own")
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat},
                                      "text": "124 BPM melodic techno, dark, A minor, tight kick, hypnotic arp"}})

    def test_options_screen_is_just_generate_and_ask(self):
        self._to_options()
        self.assertEqual(sorted(buttons(self.bot.tg.sent[-1])), ["ask", "go"])

    def test_exclude_and_weirdness_reach_the_prompt(self):
        self._to_options()
        self.tap("o:excl")
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat}, "text": "trance stabs"}})
        self.tap("ov:weirdness:100")
        spec = self.bot.builders[self.chat]["spec"]
        norm = zb.opt.normalize(dict(spec))
        self.assertIn("Avoid: trance stabs", norm["idea"])
        self.assertIn("Unexpected harmonic turns", norm["idea"])

    def test_style_influence_maps_to_guidance_scale(self):
        self._to_options()
        self.tap("ov:style_influence:100")
        norm = zb.opt.normalize(dict(self.bot.builders[self.chat]["spec"]))
        self.assertEqual(norm["guidance_scale"], 12.0)
        self.tap("ov:style_influence:0")
        norm = zb.opt.normalize(dict(self.bot.builders[self.chat]["spec"]))
        self.assertEqual(norm["guidance_scale"], 3.0)

    def test_lyrics_and_seed_are_collected(self):
        self._to_options()
        self.tap("o:instr")           # off
        self.tap("o:lyrics")
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat},
                                      "text": "[Intro]\n[Verse] under the sodium light\n[Chorus] drive"}})
        self.tap("o:seed")
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat}, "text": "4242"}})
        spec = self.bot.builders[self.chat]["spec"]
        self.assertFalse(spec["instrumental"])
        norm = zb.opt.normalize(dict(spec))
        self.assertEqual(norm["seed"], 4242)
        self.assertIn("[Chorus]", norm["lyrics"])
        self.assertFalse(norm["instrumental"])

    def test_model_button_cycles(self):
        self.bot._models_available = lambda: {"turbo", "turbo-shift3"}
        self._to_options()
        self.tap("o:model")
        self.assertEqual(self.bot.builders[self.chat]["spec"]["model"], "turbo-shift3")
        self.tap("o:model")
        self.assertEqual(self.bot.builders[self.chat]["spec"]["model"], "turbo")

    # ---- the Menu button ----
    def test_menu_lists_every_action(self):
        self.msg("/menu")
        data = buttons(self.bot.tg.sent[-1])
        for want in ("menu:track", "menu:own", "menu:ai", "menu:library",
                     "menu:social", "menu:more"):
            self.assertIn(want, data)
        self.assertNotIn("menu:routenote", data)

    def test_menu_own_prompt_goes_straight_to_the_prompt_question(self):
        self.bot._callback(self.chat, "menu:own")
        self.assertIn("ابعت البرومبت", self.bot.tg.sent[-1]["text"])

    def test_menu_ai_asks_for_the_idea(self):
        self.bot._callback(self.chat, "menu:ai")
        self.assertIn("قولي الفكرة", self.bot.tg.sent[-1]["text"])

    def test_start_shows_the_inline_menu_and_no_reply_keyboard(self):
        self.msg("/start")
        found = [m for m in self.bot.tg.sent if m.get("keyboard")]
        self.assertTrue(found)
        self.assertIn("menu:track", buttons(found[0]))
        self.assertFalse([m for m in self.bot.tg.sent
                          if m.get("reply") and "keyboard" in m["reply"]])

    def test_prompt_tap_without_a_builder_does_not_crash(self):
        self.tap("p:own")
        self.assertIn("/track", self.bot.tg.sent[-1]["text"])

    def test_empty_prompt_after_cleaning_is_refused(self):
        self.msg("/track")
        self.tap("p:own")
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat},
                                      "text": "in the style of Some Famous DJ"}})
        self.assertIn("قصير أوي", self.bot.tg.sent[-1]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
