"""The Reference button: a name, a link, a screenshot or a voice note become a style description."""
import json, os, sys, tempfile, types, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"text": text, "keyboard": keyboard})
        return {"ok": True}

    def call(self, *a, **k):
        return {}

    def _note(self, *a, **k):
        pass


FOUND = {"genre": "Electronic", "artist": "Nils Frahm", "track": "Says"}


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s, *a: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 9
        self.bot._itunes = lambda q: None
        self.bot._track(9, "")

    def text(self):
        return self.bot.tg.sent[-1]["text"]

    def keys(self):
        return [b["callback_data"] for row in (self.bot.tg.sent[-1].get("keyboard") or []) for b in row]

    def enter_ref(self):
        self.bot._callback(9, "p:ref")
        self.assertIn("ابعت المرجع", self.text())
        self.assertEqual(self.bot.builders[9]["step"], "ref_wait")

    def test_reference_button_sits_in_the_prompt_step(self):
        # the separate reference button is gone: it lives inside the own-prompt flow
        self.assertNotIn("p:ref", self.keys())
        self.enter_ref()

    def test_a_name_gives_a_style_and_no_name_in_the_prompt(self):
        self.bot._itunes = lambda q: FOUND
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "Nils Frahm, sad piano"}})
        shown = self.text()
        self.assertIn("فهمت من المرجع:", shown)
        self.assertIn("Says - Nils Frahm", shown)          # he can check what was read
        built = self.bot.builders[9]["built"]
        self.assertNotIn("Nils Frahm", built["prompt"])
        self.assertNotIn("Says", built["prompt"])
        self.assertIn("melodic techno", built["prompt"])   # Electronic -> melodic techno

    def test_use_it_carries_the_derived_prompt_into_the_spec(self):
        self.bot._itunes = lambda q: FOUND
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "Nils Frahm"}})
        self.bot._callback(9, "p:use")
        spec = self.bot.builders[9]["spec"]
        self.assertEqual(spec["idea"], self.bot.builders[9]["built"]["prompt"])
        self.assertNotIn("Nils Frahm", spec["idea"])

    def test_an_unknown_reference_asks_for_words(self):
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "zzz qqq"}})
        self.assertIn("معرفتش أطلّع ستايل", self.text())
        self.assertEqual(self.bot.builders[9]["step"], "ref_wait")

    def test_his_own_style_words_are_enough_without_a_lookup(self):
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "afro house, 118 bpm, warm percussion"}})
        self.assertIn("فهمت من المرجع:", self.text())
        self.assertIn("afro house", self.bot.builders[9]["built"]["prompt"])

    def test_a_link_uses_the_page_title_only(self):
        html = ('<html><head><title>Some Track - Some Artist | Spotify</title>'
                '<meta property="og:description" content="melodic techno, 122 bpm, dark and driving"></head></html>')
        self.bot._http_text = lambda url, *a, **k: html
        self.bot._itunes = lambda q: {"genre": "Techno", "artist": "Some Artist", "track": "Some Track"}
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "https://open.example.com/track/123"}})
        self.assertIn("قريت من اللينك: Some Track - Some Artist", self.bot.tg.sent[-2]["text"])
        built = self.bot.builders[9]["built"]
        self.assertNotIn("Some Artist", built["prompt"])

    def test_a_youtube_title_drops_the_site_suffix(self):
        html = ('<html><head><title>Some Track - Some Artist - YouTube</title>'
                '<meta name="description" content="melodic techno 124 bpm"></head></html>')
        self.bot._http_text = lambda url, *a, **k: html
        asked = {}

        def fake(q):
            asked["q"] = q
            return {"genre": "Dance", "artist": "Some Artist", "track": "Some Track"}
        self.bot._itunes = fake
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "https://www.youtube.com/watch?v=abc"}})
        self.assertEqual(asked["q"], "Some Track - Some Artist")
        self.assertIn("فهمت من المرجع:", self.text())

    def test_his_words_beat_the_genre_label(self):
        self.bot._itunes = lambda q: {"genre": "Dance", "artist": "A", "track": "B"}
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "afro house, warm percussion"}})
        self.assertIn("afro house", self.bot.builders[9]["built"]["prompt"])

    def test_a_link_that_will_not_open_says_so(self):
        def boom(*a, **k):
            raise OSError("connection reset")
        self.bot._http_text = boom
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "https://open.example.com/track/123"}})
        self.assertIn("معرفتش أفتح اللينك", self.text())

    def test_a_screenshot_without_ocr_or_vision_asks_for_text(self):
        self.bot._download_file = lambda fid: b"jpegbytes"
        self.enter_ref()
        with mock.patch.dict(sys.modules, {"pytesseract": None, "PIL": None, "PIL.Image": None}):
            self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                          "photo": [{"file_id": "small"}, {"file_id": "big"}]}})
        self.assertIn("مش قادر أقرا الصورة", self.text())

    def test_a_screenshot_with_ocr_flows_into_the_style(self):
        self.bot._download_file = lambda fid: b"jpegbytes"
        self.bot._itunes = lambda q: FOUND
        fake = types.ModuleType("pytesseract")
        fake.image_to_string = lambda img: "Nils Frahm\nSays\n"
        pil = types.ModuleType("PIL")
        pil_image = types.ModuleType("PIL.Image")
        pil_image.open = lambda p: object()
        self.enter_ref()
        with mock.patch.dict(sys.modules, {"pytesseract": fake, "PIL": pil, "PIL.Image": pil_image}):
            self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                          "photo": [{"file_id": "big"}]}})
        self.assertIn("قريت من الصورة: Nils Frahm Says", self.bot.tg.sent[-2]["text"])
        self.assertIn("فهمت من المرجع:", self.text())

    def test_a_voice_note_reference_uses_the_transcript(self):
        self.bot._itunes = lambda q: None
        self.bot._download_voice = lambda v: os.path.join(self.tmp, "v.ogg")
        self.bot._transcribe = lambda p: "afro house, warm percussion"
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "voice": {"file_id": "v1"}}})
        self.assertIn("فهمت من المرجع:", self.text())

    def test_an_artist_name_never_survives_into_the_prompt(self):
        self.bot._itunes = lambda q: None
        self.enter_ref()
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "melodic techno in the style of Daft Punk, dark"}})
        built = self.bot.builders[9]["built"]
        self.assertNotIn("Daft Punk", built["prompt"])
        self.assertIn("شلت الاسم من البرومبت", self.text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
