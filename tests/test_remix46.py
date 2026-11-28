import json, os, sys, tempfile, unittest, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb
from tests.test_voice import FakeTG


def flat(m): return [b.get("callback_data") for r in m["keyboard"] for b in r]


def make_bot(engine_names=()):
    t = tempfile.mkdtemp()
    d = os.path.join(t, "20261128-100000_Night_Drive"); os.makedirs(d)
    json.dump({"title": "Night Drive", "instrumental": True, "actual_duration_sec": 200.4, "language": "en"},
              open(os.path.join(d, "metadata.json"), "w"))
    open(os.path.join(d, "Night_Drive.flac"), "wb").write(b"x")
    open(os.path.join(d, "Night_Drive_320kbps.mp3"), "wb").write(b"x")
    ns = {}
    def make_track(s): pass
    bot = zb.Bot("T", out_root=t, work=t, make_track=make_track)
    bot.tg = FakeTG(); bot.owner = 5; bot._launcher_sent = True
    bot._engine_has = lambda n: n in engine_names
    bot._get = lambda *a, **k: None
    bot.q = []
    bot._enqueue = lambda c, s: bot.q.append(s)
    bot.key = bot._lib_key(os.path.basename(d)); bot.folder = d
    return bot


class Gating(unittest.TestCase):
    def test_no_buttons_until_the_engine_has_them(self):
        b = make_bot(()); b._callback(5, "lib:" + b.key)
        f = flat(b.tg.sent[-1])
        self.assertFalse(any(c.startswith(("rmx:", "rmt:")) for c in f))
        self.assertIn("pubmenu:" + b.key, f)

    def test_both_buttons_beside_publish(self):
        b = make_bot(("COVER_TASKS", "remaster_release")); b._callback(5, "lib:" + b.key)
        f = flat(b.tg.sent[-1])
        self.assertIn("rmx:" + b.key, f); self.assertIn("rmt:" + b.key, f)
        for row in b.tg.sent[-1]["keyboard"]:
            self.assertLessEqual(len(row), 2)

    def test_only_remaster_when_only_that_is_live(self):
        b = make_bot(("remaster_release",)); b._callback(5, "lib:" + b.key)
        f = flat(b.tg.sent[-1])
        self.assertIn("rmt:" + b.key, f); self.assertNotIn("rmx:" + b.key, f)


class Remix(unittest.TestCase):
    def test_flow_makes_a_new_cover_spec(self):
        b = make_bot(("COVER_TASKS",))
        b._callback(5, "rmx:" + b.key)
        self.assertIn("الأصل هيفضل", b.tg.sent[-1]["text"])
        b._handle({"message": {"chat": {"id": 5}, "text": "warm afro house"}})
        f = flat(b.tg.sent[-1])
        self.assertEqual([c for c in f], [f"rmxs:{b.key}:0", f"rmxs:{b.key}:1", f"rmxs:{b.key}:2"])
        self.assertEqual(b.q, [])
        b._callback(5, f"rmxs:{b.key}:2")
        s = b.q[0]
        self.assertEqual(s["task_type"], "cover")
        self.assertTrue(s["src_audio_path"].endswith("Night_Drive.flac"))
        self.assertEqual(s["cover_strength"], 0.4)
        self.assertEqual(s["title"], "Night Drive (Remix)")
        self.assertEqual(s["seconds"], 200)
        self.assertIn("afro house", s["idea"].lower())
        self.assertTrue(os.path.exists(os.path.join(b.folder, "Night_Drive.flac")))   # original untouched

    def test_arabic_idea_is_translated(self):
        b = make_bot(("COVER_TASKS",)); b._callback(5, "rmx:" + b.key)
        b._handle({"message": {"chat": {"id": 5}, "text": "هاوس دافي"}})
        self.assertIn("house", b.tg.sent[-1]["text"].lower())

    def test_unusable_idea_asks_again(self):
        b = make_bot(("COVER_TASKS",)); b._callback(5, "rmx:" + b.key)
        b._handle({"message": {"chat": {"id": 5}, "text": "يا عم"}})
        self.assertIn("ما وصلنيش كويس", b.tg.sent[-1]["text"])
        self.assertIsNone(b.remix[5]["idea"])

    def test_close_and_default_strengths(self):
        b = make_bot(("COVER_TASKS",))
        for idx, want in ((0, 0.8), (1, 0.65)):
            b.q.clear(); b._callback(5, "rmx:" + b.key)
            b._handle({"message": {"chat": {"id": 5}, "text": "deep house"}})
            b._callback(5, f"rmxs:{b.key}:{idx}")
            self.assertEqual(b.q[0]["cover_strength"], want)


class Remaster(unittest.TestCase):
    def test_runs_engine_function_and_delivers_new_release(self):
        b = make_bot(("remaster_release",))
        calls, delivered = [], []
        def fn(folder):
            calls.append(folder); return {"folder": "/n", "base": "/n/x", "title": "Night Drive (Remaster)",
                                          "mastering": {"verified": True}}
        b.make_track = type("F", (), {"__globals__": {"remaster_release": fn}})()
        b._deliver = lambda c, r: delivered.append(r)
        b._callback(5, "rmt:" + b.key)
        for _ in range(50):
            if delivered: break
            time.sleep(0.05)
        self.assertEqual(calls, [b.folder]); self.assertEqual(delivered[0]["title"], "Night Drive (Remaster)")

    def test_unverified_loudness_is_reported(self):
        b = make_bot(("remaster_release",))
        def fn(folder):
            return {"folder": "/n", "base": "/n/x", "title": "T", "mastering": {"verified": False, "out_i": "-9", "out_tp": "1"}}
        b.make_track = type("F", (), {"__globals__": {"remaster_release": fn}})()
        done = []
        b._deliver = lambda c, r: done.append(1)
        b._callback(5, "rmt:" + b.key)
        for _ in range(50):
            if done: break
            time.sleep(0.05)
        self.assertTrue(any("مش على الهدف" in m["text"] for m in b.tg.sent))


if __name__ == "__main__":
    unittest.main()


class PatchFile(unittest.TestCase):
    def test_engine_patch_cell_compiles_and_defines_the_names(self):
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "colab", "engine_patch_46.py")
        src = open(p, encoding="utf-8").read()
        compile(src, p, "exec")
        for name in ("COVER_TASKS", "def master_file", "def remaster_release", "audio_cover_strength"):
            self.assertIn(name, src)
