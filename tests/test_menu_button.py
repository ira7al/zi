"""The corner Menu: one command, which posts the whole inline menu into the chat."""
import json, os, sys, tempfile, types, unittest

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

    def test_the_command_list_is_one_entry_called_menu(self):
        self.assertEqual([c for c, _ in zb.COMMANDS], ["menu"])

    def test_the_corner_button_opens_that_one_item_list(self):
        self.bot._register_commands()
        call = [c for c in self.bot.tg.calls if c[0][0] == "setMyCommands"][-1]
        self.assertEqual([c["command"] for c in json.loads(call[1]["commands"])], ["menu"])
        kinds = [json.loads(c[1]["menu_button"])["type"] for c in self.bot.tg.calls
                 if c[0][0] == "setChatMenuButton"]
        self.assertTrue(kinds and all(k == "commands" for k in kinds))

    def test_menu_posts_every_action_as_buttons(self):
        self.say("/menu")
        flat = [b.get("callback_data") for row in self.bot.tg.sent[-1]["keyboard"] for b in row]
        for want in ("menu:track", "menu:own", "menu:ai", "menu:library",
                     "menu:social", "menu:more"):
            self.assertIn(want, flat)
        self.assertNotIn("menu:dataset", flat)      # Dorgham and RouteNote sit under More since .51
        self.assertNotIn("menu:routenote", flat)

    def test_it_also_works_typed_in_arabic(self):
        for text in ("Menu", "\u2630 Menu", "القائمة"):
            self.say(text)
            flat = [b.get("callback_data") for row in self.bot.tg.sent[-1]["keyboard"] for b in row]
            self.assertIn("menu:track", flat, text)

    def test_menu_does_not_go_to_the_assistant(self):
        self.say("Menu")
        self.assertIn("\u0628\u0636\u063a\u0637\u0629", self.bot.tg.sent[-1]["text"])
        self.assertNotIn("مش متأكد", self.bot.tg.sent[-1]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
