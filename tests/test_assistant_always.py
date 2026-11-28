"""The assistant is present all the way through: free text, hints, and next-step buttons."""
import os, sys, tempfile, types, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class AlwaysOnTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=None)
        self.bot.tg = types.SimpleNamespace(sent=[], calls=[])
        self.bot.tg.send = lambda chat_id, text, keyboard=None, reply=None: self.bot.tg.sent.append(
            {"text": text, "keyboard": keyboard})
        self.bot.tg.call = lambda *a, **k: self.bot.tg.calls.append((a, k)) or {}
        self.bot.tg._note = lambda *a, **k: None
        self.bot.owner = 9

    def say(self, text):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": text}})

    def last(self):
        return self.bot.tg.sent[-1]

    def test_free_text_is_a_question_not_a_track(self):
        self.say("ينفع أعمل حاجة زي كده؟")
        self.assertNotIn(9, self.bot.builders)
        self.assertIn("مش متأكد", self.last()["text"]) or self.assertIn("أقدر أجاوب", self.last()["text"])

    def test_the_answer_carries_two_or_three_next_steps(self):
        self.say("إيه الناقص؟")
        flat = [b["callback_data"] for row in self.last()["keyboard"] for b in row]
        self.assertIn("sug:missing", flat)
        self.assertIn("sug:next", flat)
        self.assertIn("sug:track", flat)

    def test_a_suggestion_tap_answers_or_starts_a_track(self):
        self.say("إيه الناقص؟")
        self.bot._callback(9, "sug:track")
        self.assertIn(9, self.bot.builders)
        self.assertIn("تراك جديد", self.last()["text"])

    def test_a_spoken_music_idea_still_starts_a_track(self):
        self.bot._download_voice = lambda v: os.path.join(self.tmp, "v.ogg")
        self.bot._transcribe = lambda p: "afro house, warm sunset, 121 bpm"
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "voice": {"file_id": "v1"}}})
        self.assertIn(9, self.bot.builders)
        self.assertIn("Prompt (", "\n".join(m["text"] for m in self.bot.tg.sent))

    def test_a_spoken_question_goes_to_the_assistant(self):
        self.bot._download_voice = lambda v: os.path.join(self.tmp, "v.ogg")
        self.bot._transcribe = lambda p: "what is still missing from my setup"
        self.bot._speak = lambda chat_id, text: True      # no TTS call in a test
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "voice": {"file_id": "v1"}}})
        self.assertNotIn(9, self.bot.builders)
        self.assertIn("اللي ناقص", "\n".join(m["text"] for m in self.bot.tg.sent))

    def test_the_main_screens_carry_the_hint_and_the_ask_button(self):
        self.bot._track(9, "")
        self.assertIn(zb.ASSIST_HINT, self.last()["text"])
        self.bot.builders[9]["step"] = "ai_review"
        self.bot.builders[9]["built"] = zb.build_prompt("melodic techno, dark", 240)
        self.bot._show_prompt(9, self.bot.builders[9])
        self.assertIn(zb.ASSIST_HINT, self.last()["text"])
        flat = [b["callback_data"] for row in self.last()["keyboard"] for b in row]
        self.assertIn("ask", flat)

    def test_the_options_and_ready_screens_carry_it_too(self):
        self.bot.builders[9] = {"step": "options", "spec": {"genre": "melodic techno", "seconds": 240,
                                                           "instrumental": True, "quality": "high"}}
        self.bot._show_options(9, self.bot.builders[9])
        self.assertIn(zb.ASSIST_HINT, self.last()["text"])
        self.bot._confirm(9, self.bot.builders[9])
        self.assertIn(zb.ASSIST_HINT, self.last()["text"])
        flat = [b["callback_data"] for row in self.last()["keyboard"] for b in row]
        self.assertIn("ask", flat)

    def test_ask_button_opens_the_assistant_chat(self):
        self.bot._callback(9, "ask")
        self.assertIn(9, self.bot.ask_mode)


if __name__ == "__main__":
    unittest.main(verbosity=2)
