"""The two buttons under the message box: Menu for the bot, Studio for the web app."""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"text": text, "keyboard": keyboard, "reply": reply})
        return {"ok": True}

    def call(self, *a, **k):
        return {}

    def _note(self, *a, **k):
        pass


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s, *a: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 9

    def say(self, text):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": text}})

    def keyboards(self):
        return [m for m in self.bot.tg.sent if m.get("reply")]

    def test_start_puts_two_buttons_under_the_box(self):
        self.say("/start")
        boards = self.keyboards()
        self.assertTrue(boards, "no persistent keyboard was sent")
        rows = boards[-1]["reply"]["keyboard"]
        self.assertEqual([b["text"] for b in rows[0]], ["\u2630 Menu", "\U0001f39b Studio"])
        self.assertEqual(rows[0][1]["web_app"]["url"], zb.STUDIO_URL)
        self.assertTrue(boards[-1]["reply"]["is_persistent"])

    def test_the_studio_button_points_at_the_live_app(self):
        self.assertEqual(zb.STUDIO_URL, "https://ira7al.github.io/zi/")
        self.assertEqual(zb.Bot.launcher()["keyboard"][0][1]["web_app"], {"url": zb.STUDIO_URL})

    def test_tapping_menu_opens_the_menu_and_not_a_track_builder(self):
        self.say("\u2630 Menu")
        self.assertIn(9, [9])                      # nothing crashed
        self.assertNotIn(9, self.bot.builders)
        flat = [b["callback_data"] for m in self.bot.tg.sent if m.get("keyboard")
                for row in m["keyboard"] for b in row]
        self.assertIn("menu:track", flat)

    def test_tapping_studio_gives_the_link_when_the_client_cannot_open_it(self):
        self.say("\U0001f39b Studio")
        joined = "\n".join(m["text"] for m in self.bot.tg.sent)
        self.assertIn(zb.STUDIO_URL, joined)

    def test_studio_command(self):
        self.say("/studio")
        self.assertIn(zb.STUDIO_URL, self.bot.tg.sent[-2]["text"])

    def test_menu_as_plain_text_is_not_an_idea(self):
        self.say("menu")
        self.assertNotIn(9, self.bot.builders)

    def test_binding_sends_the_buttons(self):
        self.bot.owner = None
        self.bot.pair_code = "123456"
        self.say("/start 123456")
        self.assertEqual(self.bot.owner, 9)
        self.assertTrue(self.keyboards())

    def test_the_first_message_after_a_restart_brings_the_buttons_back(self):
        # a fresh process, chat cleared: any message from him restores the keyboard once
        self.say("ايه الناقص")
        boards = self.keyboards()
        self.assertEqual(len(boards), 1)
        self.assertEqual([b["text"] for b in boards[0]["reply"]["keyboard"][0]],
                         ["\u2630 Menu", "\U0001f39b Studio"])
        self.say("تاني")
        self.assertEqual(len(self.keyboards()), 1)     # only once, not every message

    def test_the_old_inline_menu_button_still_works(self):
        self.say("/help")
        flat = [b["callback_data"] for m in self.bot.tg.sent if m.get("keyboard")
                for row in m["keyboard"] for b in row]
        self.assertIn("menu", flat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
