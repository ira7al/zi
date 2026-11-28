"""Training-set intake: save, dedupe, label, lyrics, the 20 MB cap, and the status command."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent, self.calls = [], []
        self.thread_of = None

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"chat_id": chat_id, "text": text, "keyboard": keyboard})
        return {"ok": True}

    def call(self, *a, **k):
        self.calls.append((a, k))
        return {"file_path": "documents/file_1.mp3"}

    def audio(self, *a, **k):
        return {"ok": True}

    def photo(self, *a, **k):
        return {"ok": True}

    def _upload(self, *a, **k):
        return {"ok": True}

    def _note(self, *a, **k):
        pass


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 9
        self.payload = b"ID3fake-audio-bytes"
        self.bot._download_file = lambda fid: self.payload

    def upload(self, name="Track One.mp3", size=None, file_id="f1"):
        self.bot._handle({"message": {
            "chat": {"id": 9, "type": "private"}, "from": {"id": 9},
            "audio": {"file_id": file_id, "file_name": name,
                      "file_size": size if size is not None else len(self.payload)}}})

    def last(self):
        return self.bot.tg.sent[-1]

    def test_audio_is_saved_with_its_name_and_counted(self):
        self.upload()
        self.assertIn("Saved Track One.mp3", self.last()["text"])
        self.assertIn("1 received", self.last()["text"])
        self.assertTrue(os.path.exists(os.path.join(self.bot._dataset_dir(), "Track One.mp3")))
        self.assertEqual(sorted(b["callback_data"].split(":")[1] for b in self.last()["keyboard"][0]),
                         ["i", "v"])

    def test_second_upload_counts_up_and_duplicate_is_refused(self):
        self.upload("a.mp3", file_id="f1")
        self.payload = b"other-bytes"
        self.upload("b.mp3", file_id="f2")
        self.assertIn("2 received", self.last()["text"])
        self.payload = b"ID3fake-audio-bytes"          # same bytes as the first file
        self.upload("a-copy.mp3", file_id="f3")
        self.assertIn("Already have that one (a.mp3)", self.last()["text"])
        self.assertEqual(len(os.listdir(self.bot._dataset_dir())), 3)  # two audio files + manifest

    def test_same_name_never_overwrites(self):
        self.upload("same.mp3", file_id="f1")
        self.payload = b"different-bytes"
        self.upload("same.mp3", file_id="f2")
        self.assertTrue(os.path.exists(os.path.join(self.bot._dataset_dir(), "same (2).mp3")))

    def test_over_20mb_is_refused_with_what_to_do(self):
        self.upload("big.wav", size=30 * 1024 * 1024)
        text = self.last()["text"]
        self.assertIn("30.0 MB", text)
        self.assertIn("20 MB", text)
        self.assertIn("MP3", text)
        self.assertIn("Drive folder", text)
        self.assertEqual(os.listdir(self.bot._dataset_dir()), [])

    def test_label_then_lyrics(self):
        self.upload()
        short = next(iter(self.bot._ds_manifest()["files"]))[:10]
        self.bot._callback(9, f"ds:v:{short}")
        self.assertIn("Marked vocal", self.last()["text"])
        self.assertEqual(self.bot._ds_manifest()["files"][next(iter(self.bot._ds_manifest()["files"]))]["kind"], "vocal")
        self.bot._callback(9, f"ds:l:{short}")
        self.assertIn("Send the lyrics", self.last()["text"])
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "[Verse] under the sodium light"}})
        self.assertIn("Lyrics saved", self.last()["text"])
        entry = self.bot._ds_manifest()["files"][next(iter(self.bot._ds_manifest()["files"]))]
        self.assertTrue(entry["lyrics"].endswith(".lyrics.txt"))
        self.assertTrue(os.path.exists(os.path.join(self.bot._dataset_dir(), entry["lyrics"])))

    def test_instrumental_label_needs_no_lyrics(self):
        self.upload()
        short = next(iter(self.bot._ds_manifest()["files"]))[:10]
        self.bot._callback(9, f"ds:i:{short}")
        self.assertIn("Marked instrumental", self.last()["text"])
        self.assertNotIn("Lyrics", self.last()["text"])

    def test_dataset_status_counts_everything(self):
        self.upload("one.mp3", file_id="f1")
        short = next(iter(self.bot._ds_manifest()["files"]))[:10]
        self.bot._callback(9, f"ds:v:{short}")
        self.payload = b"second-file"
        self.upload("two.mp3", file_id="f2")
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9},
                                      "text": "/dataset"}})
        text = self.last()["text"]
        self.assertIn("2 files", text)
        self.assertIn("vocal 1", text)
        self.assertIn("not labelled 1", text)
        self.assertIn("two.mp3", text)          # named as waiting for a label

    def test_only_the_owner_can_upload(self):
        self.bot._handle({"message": {"chat": {"id": 77, "type": "private"}, "from": {"id": 77},
                                      "audio": {"file_id": "f9", "file_name": "x.mp3", "file_size": 10}}})
        self.assertIn("private studio bot", self.last()["text"])
        self.assertEqual(os.listdir(self.bot._dataset_dir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
