import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb, zi_options as opt
from tests.test_voice import FakeTG


def flat(m): return [b.get("callback_data") for r in m["keyboard"] for b in r]


class Parse(unittest.TestCase):
    def test_edits(self):
        ch, _ = opt.parse_spec_edits("خليها ٤ دقايق بكلمات وبـ ١٢٠ BPM على A minor")
        self.assertEqual((ch["seconds"], ch["instrumental"], ch["bpm"], ch["key"]), (240, False, 120, "A minor"))
        ch, _ = opt.parse_spec_edits("من غير كلام")
        self.assertTrue(ch["instrumental"])
        ch, _ = opt.parse_spec_edits("العنوان Night Drive")
        self.assertEqual(ch["title"], "Night Drive")
        ch, _ = opt.parse_spec_edits("avoid trance stabs")
        self.assertEqual(ch["exclude"], "trance stabs")
        ch, _ = opt.parse_spec_edits("دقيقتين")
        self.assertEqual(ch["seconds"], 120)
        self.assertEqual(opt.parse_spec_edits("ازيك")[0], {})
        self.assertEqual(opt.parse_spec_edits("bpm 400")[0], {})

    def test_go_words(self):
        self.assertTrue(opt.is_go_word("يلا"))
        self.assertTrue(opt.is_go_word("ولّد!"))
        self.assertFalse(opt.is_go_word("ولد تراك تكنو هادي بليل"))

    def test_summary(self):
        line = opt.spec_summary({"genre": "melodic techno", "seconds": 240, "instrumental": True, "bpm": 122})
        self.assertTrue(line.startswith("هعمل:") and line.endswith("تمام؟"))
        self.assertIn("موسيقى بس", line); self.assertIn("4:00", line)


class Flow(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp()
        self.enq = []
        self.bot = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5; self.bot._launcher_sent = True
        self.bot._enqueue = lambda c, s: self.enq.append(dict(s))
        self.bot.builders[5] = {"step": "options", "spec": {"genre": "melodic techno", "seconds": 330,
                                                           "instrumental": True, "quality": "high", "idea": "dark arp"}}
        self.bot._show_options(5, self.bot.builders[5])

    def say(self, t): self.bot._handle({"message": {"chat": {"id": 5}, "text": t}})

    def test_only_generate_and_ask(self):
        self.assertEqual(sorted(flat(self.bot.tg.sent[-1])), ["ask", "go"])
        self.assertIn("هعمل:", self.bot.tg.sent[-1]["text"])

    def test_words_change_the_summary(self):
        self.say("خليها ٤ دقايق بكلمات")
        spec = self.bot.builders[5]["spec"]
        self.assertEqual((spec["seconds"], spec["instrumental"]), (240, False))
        self.assertIn("بكلمات", self.bot.tg.sent[-1]["text"]); self.assertIn("4:00", self.bot.tg.sent[-1]["text"])

    def test_unclear_is_polite(self):
        self.say("blah")
        self.assertIn("ما وصلنيش كويس", self.bot.tg.sent[-1]["text"])
        self.assertEqual(self.enq, [])

    def test_generate_button_starts_it(self):
        self.bot._callback(5, "go")
        self.assertEqual(len(self.enq), 1); self.assertNotIn(5, self.bot.builders)

    def test_spoken_go(self):
        self.say("يلا")
        self.assertEqual(len(self.enq), 1)


class AfterApproval(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp()
        d = os.path.join(t, "20261128-100000_Night_Drive"); os.makedirs(d)
        open(os.path.join(d, "metadata.json"), "w").write("{}")
        open(os.path.join(d, "a_320kbps.mp3"), "wb").write(b"x")
        self.bot = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5
        self.folder = d

    def test_before_approval_only_keep(self):
        self.bot._approve_menu(5, self.folder)
        f = flat(self.bot.tg.sent[-1])
        self.assertTrue(any(c.startswith("keep:") for c in f))
        for c in f:
            self.assertFalse(c.startswith(("art:", "vid:", "pub:", "pubmenu:")))

    def test_after_approval_art_video_publish(self):
        key = self.bot._lib_key(os.path.basename(self.folder))
        self.bot._callback(5, "keep:" + key)
        f = flat(self.bot.tg.sent[-1])
        for want in ("art:" + key, "vid:" + key, "pubmenu:" + key):
            self.assertIn(want, f)


if __name__ == "__main__":
    unittest.main()
