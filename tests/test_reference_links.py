"""A pasted link or a screenshot at either prompt step is a reference, not prompt text."""
import os, sys, tempfile, types, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402

PAGE = ('<html><head><title>Spotify</title>'
        '<meta property="og:title" content="Some Track - song by Some Artist">'
        '<meta property="og:description" content="melodic techno, 122 bpm, dark and driving">'
        '</head></html>')


class LinkAndPhotoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s, *a: None)
        self.bot.tg = types.SimpleNamespace(sent=[])
        self.bot.tg.send = lambda chat_id, text, keyboard=None, reply=None: self.bot.tg.sent.append(
            {"text": text, "keyboard": keyboard})
        self.bot.tg.call = lambda *a, **k: {}
        self.bot.tg._note = lambda *a, **k: None
        self.bot.owner = 9
        self.bot._http_text = lambda url, *a, **k: PAGE
        self.bot._itunes = lambda q: {"genre": "Techno", "artist": "Some Artist", "track": "Some Track"}
        self.bot._download_file = lambda fid: b"jpegbytes"

    def builder(self, step):
        self.bot.builders[9] = {"step": step,
                                "spec": {"genre": "melodic techno", "lang": "en", "seconds": 240,
                                         "quality": "high", "instrumental": True}}

    def send(self, **msg):
        msg.setdefault("chat", {"id": 9, "type": "private"})
        msg.setdefault("from", {"id": 9})
        self.bot._handle({"message": msg})

    def joined(self):
        return "\n".join(m["text"] for m in self.bot.tg.sent)

    def test_a_link_at_the_own_prompt_step_becomes_a_reference(self):
        self.builder("own_prompt")
        self.send(text="https://open.spotify.com/track/abc123")
        shown = self.joined()
        self.assertIn("قريت من اللينك: Some Track - song by Some Artist", shown)
        self.assertIn("فهمت من المرجع", shown)
        built = self.bot.builders[9]["built"]
        self.assertIn("melodic techno", built["prompt"])
        self.assertNotIn("Some Artist", built["prompt"])

    def test_a_link_at_the_ai_idea_step_becomes_a_reference(self):
        self.builder("ai_idea")
        self.send(text="https://soundcloud.com/someone/some-track")
        self.assertIn("فهمت من المرجع", self.joined())
        self.assertEqual(self.bot.builders[9]["step"], "ai_review")

    def test_a_youtube_link_uses_its_own_title(self):
        self.builder("own_prompt")
        asked = {}

        def fake(q):
            asked["q"] = q
            return {"genre": "Dance", "artist": "Some Artist", "track": "Some Track"}
        self.bot._itunes = fake
        self.bot._http_text = lambda url, *a, **k: (
            '<html><head><title>Some Track - Some Artist - YouTube</title>'
            '<meta name="description" content="melodic techno 124 bpm"></head></html>')
        self.send(text="https://www.youtube.com/watch?v=abc")
        self.assertEqual(asked["q"], "Some Track - Some Artist")

    def test_a_screenshot_at_the_own_prompt_step_is_a_reference(self):
        self.builder("own_prompt")
        fake = types.ModuleType("pytesseract")
        fake.image_to_string = lambda img: "Some Track\nSome Artist\n"
        pil = types.ModuleType("PIL")
        pil_image = types.ModuleType("PIL.Image")
        pil_image.open = lambda p: object()
        with mock.patch.dict(sys.modules, {"pytesseract": fake, "PIL": pil, "PIL.Image": pil_image}):
            self.send(photo=[{"file_id": "big"}])
        shown = self.joined()
        self.assertIn("قريت من الصورة", shown)
        self.assertIn("فهمت من المرجع", shown)

    def test_a_reference_derived_prompt_says_nothing_was_stripped(self):
        self.builder("own_prompt")
        self.send(text="https://www.youtube.com/watch?v=abc")
        shown = self.joined()
        self.assertNotIn("\u26a0\ufe0f", shown)          # nothing was taken from him
        self.assertIn("\u2705", shown)

    def test_a_plain_message_is_still_prompt_text(self):
        self.builder("own_prompt")
        self.send(text="melodic techno, punchy kick, 122 bpm, dark pads")
        self.assertNotIn("From the link", self.joined())
        self.assertIn("الخيارات.", self.joined())      # it went to the options screen, not a reference


if __name__ == "__main__":
    unittest.main(verbosity=2)
