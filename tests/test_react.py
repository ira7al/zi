import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb, zi_assistant as za
from tests.test_voice import FakeTG


class Logic(unittest.TestCase):
    def test_code_rules(self):
        self.assertEqual(za.reaction_for("", "voice"), "\U0001f440")
        self.assertEqual(za.reaction_for("", "photo"), "\U0001f440")
        self.assertEqual(za.reaction_for("شكرا يا هندسة"), "\U0001f44d")
        self.assertEqual(za.reaction_for("ههههه دمك خفيف"), "\U0001f602")
        self.assertEqual(za.reaction_for("عاش"), "\U0001f525")
        self.assertEqual(za.reaction_for("بحبك"), "\u2764")
        self.assertIsNone(za.reaction_for("اعمل تراك تكنو هادي"))
        self.assertIsNone(za.reaction_for("/menu"))

    def test_tag_is_stripped_and_validated(self):
        self.assertEqual(za.split_reaction("تمام كده\n[[react:🔥]]"), ("تمام كده", "\U0001f525"))
        self.assertEqual(za.split_reaction("ok [[react:❤️]]"), ("ok", "\u2764"))
        self.assertEqual(za.split_reaction("ok [[react:💩]]"), ("ok", None))
        self.assertEqual(za.split_reaction("no tag"), ("no tag", None))

    def test_system_mentions_the_tag(self):
        self.assertIn("[[react:", za.SYSTEM)


class Bot(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5; self.bot._launcher_sent = True
        self.bot._assistant = lambda *a, **k: None

    def reactions(self):
        return [k for a, k in self.bot.tg.calls if a and a[0] == "setMessageReaction"]

    def test_voice_and_photo_always_get_eyes(self):
        self.bot._voice_prompt = lambda c, v: None
        for mid, key in ((1, "voice"), (2, "photo")):
            self.bot._handle({"message": {"chat": {"id": 5}, "message_id": mid, key: [{"file_id": "x"}] if key == "photo" else {"file_id": "x"}}})
        r = self.reactions()
        self.assertEqual([x["message_id"] for x in r], [1, 2])
        self.assertEqual(json.loads(r[0]["reaction"])[0]["emoji"], "\U0001f440")

    def test_casual_reaction_not_spammed(self):
        self.bot._handle({"message": {"chat": {"id": 5}, "message_id": 3, "text": "شكرا"}})
        self.bot._handle({"message": {"chat": {"id": 5}, "message_id": 4, "text": "ههههه"}})
        self.assertEqual([x["message_id"] for x in self.reactions()], [3])

    def test_work_text_gets_none(self):
        self.bot._handle({"message": {"chat": {"id": 5}, "message_id": 6, "text": "اعمل تراك"}})
        self.assertEqual(self.reactions(), [])

    def test_failure_never_raises(self):
        def boom(*a, **k): raise RuntimeError("x")
        self.bot.tg.call = boom
        self.assertFalse(self.bot._react(5, 9, "\U0001f525", always=True))


if __name__ == "__main__":
    unittest.main()
