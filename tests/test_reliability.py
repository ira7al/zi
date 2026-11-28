"""A bad track must never take the bot down, and every failure must say what happened."""
import os, sys, tempfile, threading, time, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []
        self.lock = threading.Lock()

    def send(self, chat_id, text, keyboard=None):
        with self.lock:
            self.sent.append(text)
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


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp)
        self.bot.tg = FakeTG()
        self.bot.owner = 9
        self.bot.gpu_marker = None
        self.bot._gpu_busy = lambda: None

    def texts(self):
        return "\n".join(self.bot.tg.sent)

    def test_engine_crash_is_reported_and_the_worker_keeps_going(self):
        calls = []

        def make_track(spec, *a):
            calls.append(spec.get("title"))
            raise RuntimeError("CUDA out of memory")

        self.bot.make_track = make_track
        self.bot.jobs.put((9, {"genre": "techno", "title": "one", "seconds": 60}))
        self.bot.jobs.put((9, {"genre": "techno", "title": "two", "seconds": 60}))
        th = threading.Thread(target=self.bot._worker, daemon=True)
        th.start()
        for _ in range(100):
            if len(calls) == 2:
                break
            time.sleep(0.02)
        self.bot.stop.set()
        th.join(timeout=3)
        self.assertEqual(calls, ["one", "two"])          # the second job still ran
        self.assertIn("CUDA out of memory", self.texts())
        self.assertIn("render_errors.log", os.listdir(self.tmp))

    def test_a_crash_outside_the_render_still_leaves_the_worker_alive(self):
        seen = []

        def boom(chat_id, spec):
            seen.append(spec.get("title"))
            raise ValueError("bad spec")

        self.bot._run_job = boom
        self.bot.jobs.put((9, {"genre": "x", "title": "a", "seconds": 60}))
        self.bot.jobs.put((9, {"genre": "x", "title": "b", "seconds": 60}))
        th = threading.Thread(target=self.bot._worker, daemon=True)
        th.start()
        for _ in range(100):
            if len(seen) == 2:
                break
            time.sleep(0.02)
        self.bot.stop.set()
        th.join(timeout=3)
        self.assertEqual(seen, ["a", "b"])
        self.assertIn("The bot is still running", self.texts())

    def test_engine_returning_nothing_is_a_plain_message(self):
        self.bot.make_track = lambda spec, *a: None
        self.bot.jobs.put((9, {"genre": "techno", "title": "empty", "seconds": 60}))
        th = threading.Thread(target=self.bot._worker, daemon=True)
        th.start()
        for _ in range(100):
            if "returned no track folder" in self.texts():
                break
            time.sleep(0.02)
        self.bot.stop.set()
        th.join(timeout=3)
        self.assertIn("returned no track folder", self.texts())

    def test_render_finished_but_no_audio_on_disk(self):
        folder = os.path.join(self.tmp, "night_drive")
        os.makedirs(folder)
        self.bot.make_track = lambda spec, *a: {"base": os.path.join(folder, "Night_Drive"),
                                                "folder": folder, "title": "Night Drive"}
        self.bot.jobs.put((9, {"genre": "techno", "title": "night", "seconds": 60}))
        th = threading.Thread(target=self.bot._worker, daemon=True)
        th.start()
        for _ in range(100):
            if "sending it to you failed" in self.texts():
                break
            time.sleep(0.02)
        self.bot.stop.set()
        th.join(timeout=3)
        self.assertIn("no audio in night_drive", self.texts())
        self.assertIn("Nothing was lost", self.texts())

    def test_a_long_render_says_it_is_still_alive(self):
        def slow(spec, *a):
            time.sleep(0.6)
            return None

        self.bot.make_track = slow
        self.bot.render_note_minutes = 0.002          # ~0.12 s, so the test is quick
        self.bot.current = "long"
        with self.assertRaises(RuntimeError):
            self.bot._render(9, {"genre": "techno", "title": "long"})
        self.assertIn("Still rendering long", self.texts())


if __name__ == "__main__":
    unittest.main(verbosity=2)
