import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb
from tests.test_voice import FakeTG


def flat(m): return [b.get("callback_data") for r in m["keyboard"] for b in r]


class Tweak(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp()
        d = os.path.join(t, "20261128-100000_Night_Drive"); os.makedirs(d)
        open(os.path.join(d, "metadata.json"), "w").write("{}")
        self.bot = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5
        self.folder = d
        self.jobs = []
        self.bot.make_track = lambda s: None
        self.bot._normalize_spec = lambda s: dict(s)

    def test_listen_first_then_tweak_button_only_after_render(self):
        self.bot._approve_menu(5, self.folder)
        self.assertIn("tw:open", flat(self.bot.tg.sent[-1]))

    def test_screen_has_explained_more_less_buttons(self):
        self.bot.last_enq[5] = {"genre": "techno", "seconds": 330, "bpm": 122, "idea": "x", "seed": 7, "title": "T"}
        self.bot._callback(5, "tw:open")
        m = self.bot.tg.sent[-1]
        f = flat(m)
        for want in ("tw:w-", "tw:w+", "tw:i-", "tw:i+", "tw:s-", "tw:s+", "tw:b-", "tw:b+", "tw:go"):
            self.assertIn(want, f)
        self.assertIn("مفاجئة", m["text"]); self.assertIn("الستايل", m["text"])

    def test_steps_clamp_and_go_resends_fresh(self):
        self.bot.last_enq[5] = {"genre": "techno", "seconds": 330, "bpm": 122, "idea": "x", "seed": 7, "title": "T"}
        self.bot._callback(5, "tw:open")
        for _ in range(5):
            self.bot._callback(5, "tw:w+")
        self.bot._callback(5, "tw:i-"); self.bot._callback(5, "tw:s+"); self.bot._callback(5, "tw:b+")
        sent = []
        self.bot._enqueue = lambda c, s: sent.append(s)
        self.bot._callback(5, "tw:go")
        s = sent[0]
        self.assertEqual((s["weirdness"], s["style_influence"], s["seconds"], s["bpm"]), (100, 35, 390, 126))
        self.assertNotIn("seed", s); self.assertNotIn("title", s)
        self.assertEqual(s["idea"], "x")

    def test_enqueue_remembers_raw_spec(self):
        self.bot._enqueue(5, {"genre": "g", "idea": "i", "seconds": 120})
        self.assertEqual(self.bot.last_enq[5]["idea"], "i")

    def test_no_coming_soon_anywhere(self):
        src = open(os.path.join(os.path.dirname(zb.__file__), "zi_bot.py"), encoding="utf-8").read()
        for w in ("قريباً", "قريبا", '"coming:'):
            self.assertNotIn(w, src)


if __name__ == "__main__":
    unittest.main()


class Quiet(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5
        self.bot._download_voice = lambda v: "/x.oga"
        self.bot._transcribe = lambda p: "عايز تكنو غامق"

    def test_no_echo_but_typing_indicator(self):
        out = self.bot._voice_prompt(5, {"file_id": "v"})
        self.assertTrue(out)
        self.assertEqual([m["text"] for m in self.bot.tg.sent], [])
        self.assertTrue(any(a and a[0] == "sendChatAction" for a, k in self.bot.tg.calls))
        self.assertEqual(self.bot.heard_raw[5][0], "عايز تكنو غامق")

    def test_unsure_voice_shows_what_was_heard(self):
        self.bot._llm = lambda: False
        sent = []
        self.bot.tg.send = lambda c, t, keyboard=None, reply=None: sent.append(t)
        self.bot._speak = lambda c, t: None
        self.bot._assistant(5, "blah blah", spoken=True)
        self.assertIn("سمعت: blah blah", sent[-1])
