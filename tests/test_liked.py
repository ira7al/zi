"""The 'This is the one' button: keeps a delivered track in a Liked folder."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"chat_id": chat_id, "text": text, "keyboard": keyboard})
        return {"ok": True}

    def photo(self, *a, **k):
        return {}

    def audio(self, *a, **k):
        return {}

    def _upload(self, *a, **k):
        return {}

    def call(self, *a, **k):
        return {}

    def _note(self, *a, **k):
        pass


class LikedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp)
        self.bot.tg = FakeTG()
        self.bot.owner = 9
        self.folder = os.path.join(self.tmp, "night_drive_2026")
        os.makedirs(self.folder)
        for name in ("metadata.json", "Night_Drive_320kbps.mp3", "lyrics.txt", "cover_3000x3000.jpg"):
            open(os.path.join(self.folder, name), "wb").write(b"x")
        self.key = zb.Bot._lib_key(os.path.basename(self.folder))
        self.bot._publish_caption = lambda folder: ("Night Drive", "caption")

    def last(self):
        return self.bot.tg.sent[-1]["text"]

    def test_button_sits_under_the_delivered_track(self):
        self.bot._publish_menu(9, self.folder, "Night Drive")
        flat = [b["callback_data"] for row in self.bot.tg.sent[-1]["keyboard"] for b in row]
        self.assertIn(f"keep:{self.key}", flat)

    def test_keep_copies_the_track_and_confirms(self):
        self.bot._callback(9, f"keep:{self.key}")
        self.assertIn("Saved to Liked: Night Drive", self.last())
        self.assertIn("4 files", self.last())
        dest = os.path.join(self.tmp, "liked", f"{self.key}_Night_Drive")
        self.assertTrue(os.path.exists(os.path.join(dest, "Night_Drive_320kbps.mp3")))
        self.assertTrue(os.path.exists(os.path.join(dest, "lyrics.txt")))
        self.assertTrue(json.load(open(self.bot._liked_path()))["tracks"][self.key]["kept"])

    def test_second_tap_is_harmless(self):
        self.bot._callback(9, f"keep:{self.key}")
        self.bot._callback(9, f"keep:{self.key}")
        self.assertIn("Already in Liked", self.last())

    def test_folder_gone_from_a_restarted_notebook(self):
        os.rename(self.folder, self.folder + "_moved")
        self.bot._callback(9, f"keep:{self.key}")
        self.assertIn("not on this machine any more", self.last())

    def test_liked_lists_what_was_kept(self):
        self.bot._callback(9, f"keep:{self.key}")
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": "/liked"}})
        text = self.last()
        self.assertIn("Liked: 1 track(s)", text)
        self.assertIn("Night Drive", text)

    def test_liked_empty_state(self):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": "/liked"}})
        self.assertIn("Nothing liked yet", self.last())


if __name__ == "__main__":
    unittest.main(verbosity=2)
