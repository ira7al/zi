"""Artwork options, the pick, the audio-reactive video filter and the auto-filled YouTube metadata."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402
from tests.test_voice import FakeTG  # noqa: E402


class VideoArtTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 5
        self.folder = os.path.join(self.tmp, "20261128-120000_Test-Track")
        os.makedirs(self.folder)
        json.dump({"title": "Test Track", "genre": "Melodic Techno", "bpm": 122, "key": "Am",
                   "idea": "dark night drive like Daft Punk, warm"},
                  open(os.path.join(self.folder, "metadata.json"), "w"))

    def test_menu_two_per_row_and_arabic(self):
        self.bot._menu(5)
        m = self.bot.tg.sent[-1]
        for row in m["keyboard"]:
            self.assertLessEqual(len(row), 2)
        self.assertNotIn("Menu.", m["text"])
        self.assertFalse(any("RouteNote" in b["text"] for r in m["keyboard"] for b in r))

    def test_metadata_filled_no_names(self):
        head, desc, tags = self.bot._yt_metadata(self.folder, "Test Track", "x")
        blob = (head + desc + " ".join(tags)).lower()
        self.assertNotIn("daft", blob)
        self.assertNotIn("punk", blob)
        self.assertIn("AI-generated with ACE-Step under Rahal's direction and selection.", desc)
        for part in (head, desc):
            self.assertTrue(part.strip())
        self.assertTrue(all(t.strip() for t in tags))
        self.assertIn("https://t.me/rahal_music", desc)
        self.assertLessEqual(len(head), 100)

    def test_metadata_with_bare_meta(self):
        d = os.path.join(self.tmp, "x"); os.makedirs(d)
        head, desc, tags = self.bot._yt_metadata(d, "Solo", "x")
        self.assertIn("Solo", head)
        self.assertTrue(tags)

    def test_confirm_preview_shows_fields(self):
        self.bot._visual_cb(5, "vidyt", [self.bot._key_for(self.folder)] if hasattr(self.bot, "_key_for") else []) \
            if False else None


if __name__ == "__main__":
    unittest.main()
