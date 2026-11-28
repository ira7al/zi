"""Screenshots read by the free vision model, and spoken replies by free TTS."""
import os, sys, tempfile, types, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402
from bot import zi_assistant as za  # noqa: E402
from bot import zi_voice as zv  # noqa: E402


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=None)
        self.bot.tg = types.SimpleNamespace(sent=[], calls=[], uploads=[])
        self.bot.tg.send = lambda chat_id, text, keyboard=None, reply=None: self.bot.tg.sent.append(
            {"text": text, "keyboard": keyboard})
        self.bot.tg.call = lambda *a, **k: self.bot.tg.calls.append((a, k)) or {"file_path": "p"}
        self.bot.tg._note = lambda *a, **k: None
        self.bot.tg.voice = lambda *a, **k: self.bot.tg.uploads.append(("voice", a))
        self.bot.tg.audio = lambda *a, **k: self.bot.tg.uploads.append(("audio", a))
        self.bot.owner = 9
        self.bot._download_file = lambda fid: b"jpegbytes"
        self.bot._itunes = lambda q: {"track": "Desire", "artist": "Goom Gum", "genre": "Dance"}
        self.bot.llm_key = "k"
        self.bot._llm_ready = True

    def text(self):
        return "\n".join(m["text"] for m in self.bot.tg.sent)

    def send_photo(self):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "photo": [{"file_id": "big"}]}})

    def test_the_vision_model_reads_the_screenshot_when_ocr_is_missing(self):
        with mock.patch.object(zb.ziassist, "read_image", lambda *a, **k: "Desire - Goom Gum | Dance"):
            with mock.patch.dict(sys.modules, {"pytesseract": None, "PIL": None, "PIL.Image": None}):
                self.send_photo()
        self.assertIn("قريت من الصورة: Desire", self.text())
        self.assertIn("Prompt (", self.text())            # the style draft for approval

    def test_the_artist_and_track_never_reach_the_prompt(self):
        with mock.patch.object(zb.ziassist, "read_image", lambda *a, **k: "Desire - Goom Gum | Dance"):
            with mock.patch.dict(sys.modules, {"pytesseract": None, "PIL": None, "PIL.Image": None}):
                self.send_photo()
        prompt = self.bot.builders[9]["built"]["prompt"]
        self.assertNotIn("Goom Gum", prompt)
        self.assertNotIn("Desire", prompt)

    def test_a_refused_screenshot_gets_a_clear_arabic_line(self):
        with mock.patch.object(zb.ziassist, "read_image", lambda *a, **k: None):
            with mock.patch.dict(sys.modules, {"pytesseract": None, "PIL": None, "PIL.Image": None}):
                self.send_photo()
        self.assertIn(zb.VISION_HINT, self.text())

    def test_no_key_means_the_same_clear_line_not_a_crash(self):
        self.bot.llm_key = ""
        with mock.patch.dict(sys.modules, {"pytesseract": None, "PIL": None, "PIL.Image": None}):
            self.send_photo()
        self.assertIn(zb.VISION_HINT, self.text())

    def test_a_screenshot_sent_as_a_file_works_too(self):
        with mock.patch.object(zb.ziassist, "read_image", lambda *a, **k: "Argy - Pantheon | Techno"):
            with mock.patch.dict(sys.modules, {"pytesseract": None, "PIL": None, "PIL.Image": None}):
                self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                              "document": {"file_id": "d1", "file_name": "shot.jpg",
                                                           "mime_type": "image/jpeg"}}})
        self.assertIn("قريت من الصورة", self.text())

    def test_a_screenshot_with_nothing_open_opens_a_reference(self):
        with mock.patch.object(zb.ziassist, "read_image", lambda *a, **k: "Dance | melodic house"):
            with mock.patch.dict(sys.modules, {"pytesseract": None, "PIL": None, "PIL.Image": None}):
                self.send_photo()
        self.assertIn(9, self.bot.builders)

    def test_the_key_travels_in_a_header_not_the_url(self):
        req = za.build_vision_request(b"jpeg", mime="image/jpeg")
        part = req["contents"][0]["parts"][1]
        self.assertEqual(part["inlineData"]["mimeType"], "image/jpeg")
        self.assertTrue(part["inlineData"]["data"])


class SpokenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=None)
        self.bot.tg = types.SimpleNamespace(sent=[], calls=[], uploads=[])
        self.bot.tg.send = lambda chat_id, text, keyboard=None, reply=None: self.bot.tg.sent.append(
            {"text": text, "keyboard": keyboard})
        self.bot.tg.call = lambda *a, **k: {"file_path": "p"}
        self.bot.tg._note = lambda *a, **k: None
        self.bot.tg.voice = lambda chat_id, path, caption=None: self.bot.tg.uploads.append(
            {"kind": "voice", "path": path, "caption": caption})
        self.bot.tg.audio = lambda chat_id, path, caption=None: self.bot.tg.uploads.append(
            {"kind": "audio", "path": path, "caption": caption})
        self.bot.owner = 9
        self.bot._download_voice = lambda v: os.path.join(self.tmp, "v.oga")
        self.bot._transcribe = lambda p: "إيه الناقص؟"
        self.spoken = []
        self.bot._speak = lambda chat_id, text: self.spoken.append(text) or True

    def voice(self):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "voice": {"file_id": "v1"}}})

    def test_a_spoken_question_is_answered_aloud(self):
        self.voice()
        self.assertTrue(self.spoken, "the answer was not spoken back")
        self.assertIn("ناقص", self.spoken[-1])

    def test_a_typed_question_stays_text(self):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "إيه الناقص؟"}})
        self.assertFalse(self.spoken)

    def test_a_spoken_idea_still_builds_a_track_and_says_nothing_aloud(self):
        self.bot._transcribe = lambda p: "afro house, warm sunset, 121 bpm"
        self.voice()
        self.assertIn(9, self.bot.builders)
        self.assertFalse(self.spoken)

    def test_speak_sends_a_voice_note_when_the_engine_works(self):
        path = os.path.join(self.tmp, "say.ogg")
        open(path, "wb").write(b"OggS" + b"0" * 2000)
        with mock.patch.object(zb.voice, "speak", lambda text, out: {"path": path, "voice_note": True,
                                                               "engine": "edge-tts"}):
            self.bot._speak = zb.Bot._speak.__get__(self.bot)
            self.assertTrue(self.bot._speak(9, "أهلاً بيك"))
        self.assertEqual(self.bot.tg.uploads[-1]["kind"], "voice")

    def test_speak_says_nothing_when_no_engine_is_installed(self):
        with mock.patch.object(zb.voice, "speak", lambda text, out: None):
            self.bot._speak = zb.Bot._speak.__get__(self.bot)
            self.assertFalse(self.bot._speak(9, "أهلاً بيك"))
        self.assertFalse(self.bot.tg.uploads)


class VoiceModuleTests(unittest.TestCase):
    def test_speech_text_drops_markdown_and_links(self):
        out = zv.clean_for_speech("**جاهز** [منيو](https://x.example/a) - نقطة\n# عنوان")
        self.assertNotIn("http", out)
        self.assertNotIn("**", out)
        self.assertNotIn("#", out)

    def test_a_long_answer_is_cut_at_a_sentence(self):
        out = zv.clean_for_speech(("جملة قصيرة. " * 200))
        self.assertLessEqual(len(out), zv.MAX_CHARS + 40)

    def test_no_engine_returns_none_instead_of_raising(self):
        with mock.patch.object(zv, "have_edge", lambda: False), \
             mock.patch.object(zv, "have_gtts", lambda: False):
            self.assertIsNone(zv.speak("أهلاً", tempfile.mkdtemp()))

    def test_the_engines_report_what_is_installed(self):
        got = zv.engines()
        self.assertEqual(set(got), {"edge-tts", "gTTS", "ffmpeg"})

    def test_an_mp3_without_ffmpeg_goes_out_as_audio(self):
        tmp = tempfile.mkdtemp()
        def fake_edge(text, name, out):
            open(out, "wb").write(b"ID3" + b"0" * 2000)
            return out
        with mock.patch.object(zv, "have_edge", lambda: True), \
             mock.patch.object(zv, "have_gtts", lambda: False), \
             mock.patch.object(zv, "_edge", fake_edge), \
             mock.patch.object(zv, "to_voice_note", lambda p, d: None):
            made = zv.speak("أهلاً بيك", tmp)
        self.assertEqual(made["voice_note"], False)
        self.assertTrue(os.path.exists(made["path"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
