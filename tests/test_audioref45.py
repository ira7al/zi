import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb, zi_options as opt
from tests.test_voice import FakeTG


def flat(m): return [b.get("callback_data") for r in m["keyboard"] for b in r]


def tone(bpm=124):
    import numpy as np
    sr = 22050; t = np.arange(sr * 30) / sr; y = np.zeros_like(t); beat = 60 / bpm
    for k in range(int(30 / beat)):
        i = int(k * beat * sr); n = int(0.08 * sr); y[i:i + n] += np.sin(2 * np.pi * 60 * t[:n]) * np.exp(-t[:n] * 40)
    for f in (220, 261.63, 329.63):
        y += 0.15 * np.sin(2 * np.pi * f * t)
    return y.astype("float32")


class Analyzer(unittest.TestCase):
    def test_tempo_and_key(self):
        r = opt.audio_analyze(None, samples=tone(124))
        self.assertLessEqual(abs(r["bpm"] - 124), 3)
        self.assertEqual(r["key"], "A minor")
        self.assertIn(opt.audio_style_for(r, opt.PROMPT_STYLES), ("melodic techno", "progressive"))
        line = opt.audio_describe(r)
        self.assertIn("BPM", line)

    def test_too_short_is_none(self):
        import numpy as np
        self.assertIsNone(opt.audio_analyze(None, samples=np.zeros(1000, dtype="float32")))


class Bot(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5; self.bot._launcher_sent = True
        self.bot._download_file = lambda fid: b"x"

    def audio(self):
        return {"message": {"chat": {"id": 5}, "audio": {"file_id": "a", "file_name": "Famous Artist - Hit.mp3",
                                                         "file_size": 1000}}}

    def test_button_only_when_it_works(self):
        with mock.patch.object(zb.opt, "audio_available", lambda: True):
            self.bot._track(5, "")
            self.assertIn("p:audio", flat(self.bot.tg.sent[-1]))
        with mock.patch.object(zb.opt, "audio_available", lambda: False):
            self.bot._track(5, "")
            self.assertNotIn("p:audio", flat(self.bot.tg.sent[-1]))

    def test_audio_becomes_a_style_reference_never_a_name(self):
        self.bot._track(5, ""); self.bot._callback(5, "p:audio")
        with mock.patch.object(zb.opt, "audio_analyze", lambda p: {"bpm": 122, "key": "A minor", "brightness_hz": 1200, "rms": 0.1}):
            self.bot._handle(self.audio())
        self.assertEqual(self.bot.builders[5]["own_ref"]["style"], "melodic techno")
        shown = " ".join(m["text"] for m in self.bot.tg.sent)
        self.assertNotIn("Famous", shown); self.assertNotIn("Hit", shown)
        self.assertFalse(os.path.exists(os.path.join(self.bot.work, "audio_reference.bin")))

    def test_audio_without_the_button_still_goes_to_the_dataset(self):
        hit = []
        self.bot._ds_intake = lambda c, m: hit.append(1)
        self.bot._handle(self.audio())
        self.assertEqual(hit, [1])

    def test_unreadable_audio_says_so(self):
        self.bot._track(5, ""); self.bot._callback(5, "p:audio")
        with mock.patch.object(zb.opt, "audio_analyze", lambda p: None):
            self.bot._handle(self.audio())
        self.assertIn("معرفتش أقرا", self.bot.tg.sent[-1]["text"])

    def test_oversize_is_refused(self):
        self.bot._track(5, ""); self.bot._callback(5, "p:audio")
        m = self.audio(); m["message"]["audio"]["file_size"] = 30 * 1024 * 1024
        self.bot._handle(m)
        self.assertIn("٢٠ ميجا", self.bot.tg.sent[-1]["text"])


class Lora(unittest.TestCase):
    def mk(self, adapters):
        t = tempfile.mkdtemp()
        def make_track(s): pass
        make_track.__globals__  # real globals of this module
        bot = zb.Bot("T", out_root=t, work=t, make_track=make_track)
        bot.tg = FakeTG(); bot.owner = 5
        bot._lora_names = lambda: adapters
        return bot

    def test_hidden_until_trained(self):
        b = self.mk([]); b._track(5, "")
        self.assertNotIn("lora:t", flat(b.tg.sent[-1]))

    def test_toggle_when_live(self):
        b = self.mk(["dorgham"]); b._track(5, "")
        self.assertIn("lora:t", flat(b.tg.sent[-1]))
        b._callback(5, "lora:t")
        self.assertEqual(b.builders[5]["spec"]["lora"], "dorgham")
        self.assertIn("شغال", str([x["text"] for r in b.tg.sent[-1]["keyboard"] for x in r]))
        b._callback(5, "lora:t")
        self.assertNotIn("lora", b.builders[5]["spec"])

    def test_survives_picking_a_style(self):
        b = self.mk(["dorgham"]); b._track(5, ""); b._callback(5, "lora:t")
        g = list(zb.GENRE_PRESETS)[0]
        b._callback(5, g)
        self.assertEqual(b.builders[5]["spec"]["lora"], "dorgham")


if __name__ == "__main__":
    unittest.main()
