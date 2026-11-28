import json, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb
from tests.test_voice import FakeTG

HAVE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe(path, stream):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", "stream=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True).stdout.strip()
    return float(out)


def make_bot():
    t = tempfile.mkdtemp()
    b = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
    b.tg = FakeTG(); b.owner = 5
    return b, t


class Youtube(unittest.TestCase):
    def test_confirm_has_three_privacy_choices_and_each_tap_is_explicit(self):
        b, t = make_bot()
        d = os.path.join(t, "20261128-120000_T"); os.makedirs(d)
        json.dump({"title": "T"}, open(os.path.join(d, "metadata.json"), "w"))
        key = b._lib_key(os.path.basename(d))
        b._visual_cb(5, "vidyt:" + key)
        kb = b.tg.sent[-1]["keyboard"]
        cbs = [x["callback_data"] for r in kb for x in r]
        self.assertEqual(cbs[:3], [f"vidytok:{key}", f"vidytok:{key}:u", f"vidytok:{key}:p"])
        self.assertTrue(all(len(c.encode()) <= 64 for c in cbs))
        self.assertIn("Public", kb[0][0]["text"])
        got = []
        b._youtube_upload = lambda f, ti, cap, privacy="public": got.append(privacy) or "https://youtu.be/x"
        for suffix in ("", ":u", ":p"):
            b._visual_cb(5, f"vidytok:{key}{suffix}")
        self.assertEqual(got, ["public", "unlisted", "private"])

    def test_upload_body_uses_the_chosen_privacy(self):
        b, t = make_bot()
        seen = {}
        class R:
            headers = {"Location": "http://u"}
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return b'{"id":"abc"}'
        def fake(req, timeout=0):
            if req.get_method() == "POST":
                seen["body"] = json.loads(req.data)
            return R()
        d = os.path.join(t, "f"); os.makedirs(d)
        v = os.path.join(d, "v.mp4"); open(v, "wb").write(b"x")
        b._yt_token = lambda: {"x": 1}; b._yt_access_token = lambda tok: "A"
        b._viz_path = lambda f: v
        orig = zb.urllib.request.urlopen
        zb.urllib.request.urlopen = fake
        try:
            b._youtube_upload(d, "T", "c", privacy="unlisted")
        finally:
            zb.urllib.request.urlopen = orig
        self.assertEqual(seen["body"]["status"]["privacyStatus"], "unlisted")


class Menu(unittest.TestCase):
    def test_main_menu_slim_and_more_holds_the_rest(self):
        b, _ = make_bot()
        b._menu(5)
        main = [x["callback_data"] for r in b.tg.sent[-1]["keyboard"] for x in r if "callback_data" in x]
        self.assertNotIn("menu:routenote", main); self.assertNotIn("menu:dataset", main)
        b._menu_step(5, "more")
        more = [x["callback_data"] for r in b.tg.sent[-1]["keyboard"] for x in r]
        self.assertIn("menu:routenote", more); self.assertIn("menu:dataset", more)

    def test_facebook_is_a_real_link(self):
        b, _ = make_bot()
        b._social(5)
        urls = [x.get("url") for r in b.tg.sent[-1]["keyboard"] for x in r]
        self.assertIn("https://www.facebook.com/profile.php?id=61597045319184", urls)


class Pwa(unittest.TestCase):
    def test_cache_name_bumped(self):
        sw = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "sw.js")).read()
        self.assertIn('"zi-studio-v2"', sw)
        self.assertNotIn('"zi-studio-v1"', sw)


@unittest.skipUnless(HAVE, "needs ffmpeg and ffprobe")
class VideoLength(unittest.TestCase):
    SECS = 310   # 5 min 10 s

    def setUp(self):
        self.b, self.t = make_bot()
        self.d = os.path.join(self.t, "20261128-120000_Long")
        os.makedirs(self.d)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={self.SECS}",
                        "-c:a", "libmp3lame", "-b:a", "128k", os.path.join(self.d, "Long_320kbps.mp3")], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=purple:s=600x600",
                        "-frames:v", "1", os.path.join(self.d, "cover_3000x3000.jpg")], check=True)
        self.audio = probe(os.path.join(self.d, "Long_320kbps.mp3"), "a:0")

    # The sandbox this runs in has one slow CPU, so the frame size is cut to 320x180 here. The length logic
    # (looped still, -shortest, aac) is the production command; only the picture size and filter differ.
    def test_plain_video_matches_audio_length(self):
        self.b._video_filter = lambda w, h: "[0:v]scale=320:180,format=yuv420p[out]"
        v = self.b._make_video(self.d, "16x9")
        self.assertTrue(v)
        print("plain video: audio %.2fs video %.2fs" % (self.audio, probe(v, "v:0")))
        self.assertGreater(self.audio, 300)
        self.assertAlmostEqual(probe(v, "v:0"), self.audio, delta=0.15)
        self.assertAlmostEqual(probe(v, "a:0"), self.audio, delta=0.15)

    def test_animated_video_matches_audio_length(self):
        self.b._viz_filter = lambda: "[0:v]scale=320:180,format=yuv420p[out]"
        v = self.b._make_viz(self.d)
        self.assertTrue(v)
        print("animated video: audio %.2fs video %.2fs" % (self.audio, probe(v, "v:0")))
        self.assertAlmostEqual(probe(v, "v:0"), self.audio, delta=0.15)
        self.assertAlmostEqual(probe(v, "a:0"), self.audio, delta=0.15)


if __name__ == "__main__":
    unittest.main()
