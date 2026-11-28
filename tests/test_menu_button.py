"""The Menu button under the message box opens the inline menu; the corner list stays short."""
import os, sys, tempfile, types, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class MenuButtonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=None)
        self.bot.tg = types.SimpleNamespace(sent=[], calls=[])
        self.bot.tg.send = lambda chat_id, text, keyboard=None, reply=None: self.bot.tg.sent.append(
            {"text": text, "keyboard": keyboard, "reply": reply})
        self.bot.tg.call = lambda *a, **k: self.bot.tg.calls.append((a, k)) or {}
        self.bot.tg._note = lambda *a, **k: None
        self.bot.owner = 9

    def say(self, text):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": text}})

    def test_the_keyboard_under_the_box_has_a_menu_button(self):
        kb = self.bot.launcher()
        self.assertTrue(kb["is_persistent"])
        labels = [b.get("text") for row in kb["keyboard"] for b in row]
        self.assertIn("Menu", labels)

    def test_the_menu_button_sends_the_inline_menu_into_the_chat(self):
        self.say("Menu")
        last = self.bot.tg.sent[-1]
        flat = [b["callback_data"] for row in last["keyboard"] for b in row]
        self.assertIn("menu:track", flat)
        self.assertIn("menu:library", flat)
        self.assertIn("menu:assistant", flat)

    def test_it_also_works_typed_with_the_old_label_or_in_arabic(self):
        for text in ("\u2630 Menu", "القائمة", "/menu"):
            self.say(text)
            flat = [b["callback_data"] for row in self.bot.tg.sent[-1]["keyboard"] for b in row]
            self.assertIn("menu:track", flat, text)

    def test_menu_does_not_go_to_the_assistant(self):
        self.say("Menu")
        self.assertNotIn("مش متأكد", self.bot.tg.sent[-1]["text"])
        self.assertIn("one tap", self.bot.tg.sent[-1]["text"])

    def test_the_corner_list_stays_short_and_starts_with_menu(self):
        self.bot._register_commands()
        call = [c for c in self.bot.tg.calls if c[0][0] == "setMyCommands"][-1]
        import json
        cmds = json.loads(call[1]["commands"])
        self.assertLessEqual(len(cmds), 8)
        self.assertEqual(cmds[0]["command"], "menu")

    def test_the_corner_button_is_still_asked_to_be_the_command_list(self):
        self.bot._register_commands()
        import json
        kinds = [json.loads(c[1]["menu_button"])["type"] for c in self.bot.tg.calls
                 if c[0][0] == "setChatMenuButton"]
        self.assertTrue(kinds and all(k == "commands" for k in kinds))


if __name__ == "__main__":
    unittest.main(verbosity=2)
