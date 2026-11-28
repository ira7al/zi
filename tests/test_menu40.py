import os, sys, unittest, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb
from tests.test_voice import FakeTG


def flat(m): return [b.get("callback_data") for r in m["keyboard"] for b in r]
def texts(m): return [b["text"] for r in m["keyboard"] for b in r]


class Menu40(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = os.path.join(self.tmp, "20261128-100000_Night_Drive")
        os.makedirs(d)
        open(os.path.join(d, "metadata.json"), "w").write("{}")
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5

    def test_main_menu_shape(self):
        self.bot._menu(5)
        m = self.bot.tg.sent[-1]
        self.assertNotIn("menu:publish", flat(m))
        for gone in ("menu:status", "menu:diag", "menu:help", "menu:assistant"):
            self.assertNotIn(gone, flat(m))
        self.assertIn("menu:more", flat(m))
        self.assertTrue(any("الدرغام" in t for t in texts(m)))
        self.assertFalse(any("الداتا" in t for t in texts(m)))

    def test_more_holds_the_four(self):
        self.bot._callback(5, "menu:more")
        self.assertEqual({"menu:status", "menu:diag", "menu:assistant", "menu:help"} - set(flat(self.bot.tg.sent[-1])), set())

    def test_library_track_has_publish(self):
        self.bot._callback(5, "menu:library")
        cb = [c for c in flat(self.bot.tg.sent[-1]) if c.startswith("lib:")]
        self.assertEqual(len(cb), 1)
        self.bot._callback(5, cb[0])
        last = self.bot.tg.sent[-1]
        pm = [c for c in flat(last) if c.startswith("pubmenu:")]
        self.assertEqual(len(pm), 1)
        self.bot._callback(5, pm[0])
        self.assertTrue(any(c.startswith("pub:yt:") for c in flat(self.bot.tg.sent[-1])))


if __name__ == "__main__":
    unittest.main()
