"""No reply keyboard: the Menu in the corner posts the inline menu, and Studio lives in it."""
import os, sys, tempfile, types, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class LauncherTests(unittest.TestCase):
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

    def menus(self):
        return [m for m in self.bot.tg.sent if m.get("keyboard")]

    def test_nothing_puts_a_keyboard_under_the_message_box(self):
        self.say("/start")
        self.say("ازيك")
        self.say("/menu")
        for m in self.bot.tg.sent:
            self.assertFalse(m.get("reply") and "keyboard" in (m["reply"] or {}),
                             "a reply keyboard was sent: %r" % (m["reply"],))

    def test_the_keyboard_already_on_his_device_is_removed(self):
        self.say("/start")
        removed = [m for m in self.bot.tg.sent if (m.get("reply") or {}).get("remove_keyboard")]
        self.assertTrue(removed, "the old keyboard was never removed")

    def test_start_posts_the_inline_menu(self):
        self.say("/start")
        flat = [b.get("callback_data") for row in self.menus()[-1]["keyboard"] for b in row]
        self.assertIn("menu:track", flat)
        self.assertIn("menu:library", flat)

    def test_tapping_menu_opens_the_menu_and_not_a_track_builder(self):
        self.say("Menu")
        self.assertNotIn(9, self.bot.builders)
        flat = [b.get("callback_data") for row in self.menus()[-1]["keyboard"] for b in row]
        self.assertIn("menu:track", flat)

    def test_the_menu_button_is_not_an_idea(self):
        self.say("menu")
        self.assertNotIn(9, self.bot.builders)

    def test_the_first_message_after_a_restart_brings_the_menu_back(self):
        def menu_count():
            return len([m for m in self.bot.tg.sent
                        if any(b.get("callback_data") == "menu:track"
                               for row in (m.get("keyboard") or []) for b in row)])
        self.say("ايه الناقص")
        self.assertEqual(menu_count(), 1, "the menu was not restored on the first message")
        self.say("تاني")
        self.assertEqual(menu_count(), 1)     # once, not on every message

    def test_studio_is_inside_the_inline_menu(self):
        self.say("/menu")
        urls = [b.get("url") for row in self.menus()[-1]["keyboard"] for b in row]
        self.assertIn(zb.STUDIO_URL, urls)
        self.assertEqual(zb.STUDIO_URL, "https://ira7al.github.io/zi/")

    def test_the_studio_command_still_gives_the_link(self):
        self.say("/studio")
        self.assertIn(zb.STUDIO_URL, self.bot.tg.sent[-1]["text"])

    def test_binding_sends_the_menu(self):
        self.bot.owner = None
        self.bot.pair_code = "123456"
        self.say("/start 123456")
        self.assertEqual(self.bot.owner, 9)
        self.assertTrue(self.menus())


if __name__ == "__main__":
    unittest.main(verbosity=2)
