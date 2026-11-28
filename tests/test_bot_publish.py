"""Publish buttons and the richer delivery: menu, channel post, video render,
YouTube upload path, packages for the platforms with no API yet, manual Facebook.

No network and no Telegram: the bot's TG client is a recorder, and ffmpeg is faked.
From the repo root: python3 tests/test_bot_publish.py
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []
        self.uploads = []
        self.log = []
        self.calls = []
        self.thread_of = None

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"chat_id": chat_id, "text": text, "keyboard": keyboard})
        return {"ok": True}

    def audio(self, chat_id, path, caption=None):
        self.uploads.append(("sendAudio", chat_id, path, caption))
        return {"ok": True}

    def photo(self, chat_id, path, caption=None):
        self.uploads.append(("sendPhoto", chat_id, path, caption))
        return {"ok": True}

    def _upload(self, method, chat_id, field, path, caption=None):
        self.uploads.append((method, chat_id, path, caption))
        return {"ok": True}

    def _note(self, *a, **k):
        pass

    def call(self, *a, **k):
        self.calls.append((a, k))
        return {"ok": True}


def make_release(root, name="20261128-120000_Night-Drive", video=None, audio=True):
    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, "Night-Drive")
    if audio:
        with open(base + "_320kbps.mp3", "wb") as fh:
            fh.write(b"ID3fake")
    with open(os.path.join(folder, "cover_3000x3000.jpg"), "wb") as fh:
        fh.write(b"\xff\xd8fake")
    with open(os.path.join(folder, "metadata.json"), "w") as fh:
        json.dump({"title": "Night Drive", "genre": "Melodic Techno", "bpm": 122, "key": "Am"}, fh)
    if video:
        with open(os.path.join(folder, video), "wb") as fh:
            fh.write(b"\x00fake")
    return folder


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("TEST-TOKEN", out_root=self.tmp, work=self.tmp)
        self.bot.tg = FakeTG()
        self.chat = 4242
        self.ffmpeg_calls = []
        # ffmpeg is not part of the test: record the command and drop a file where it asked
        def fake_ffmpeg(args, timeout=0):
            self.ffmpeg_calls.append(args)
            with open(args[-1], "wb") as fh:
                fh.write(b"\x00fakevideo")
        self.bot._run_ffmpeg = fake_ffmpeg

    def _key(self, folder):
        return self.bot._lib_key(os.path.basename(folder))

    # ---- the menu ----
    def test_menu_has_every_platform_and_all(self):
        folder = make_release(self.tmp)
        self.bot._publish_menu(self.chat, folder)
        kb = self.bot.tg.sent[-1]["keyboard"]
        data = [b["callback_data"] for row in kb for b in row]
        for code in ("yt", "ig", "tt", "tg", "fb", "all"):
            self.assertTrue(any(d.startswith("pub:%s:" % code) for d in data), code)
        for d in data:
            self.assertLessEqual(len(d.encode()), 64)  # Telegram's callback_data cap
        self.assertIn("Night Drive", self.bot.tg.sent[-1]["text"])

    # ---- delivery ----
    def test_delivery_shows_cover_audio_video_then_the_menu(self):
        folder = make_release(self.tmp)
        self.bot._deliver(self.chat, {"base": os.path.join(folder, "Night-Drive"),
                                      "folder": folder, "title": "Night Drive"})
        kinds = [u[0] for u in self.bot.tg.uploads]
        self.assertEqual(kinds, ["sendPhoto", "sendAudio", "sendVideo"])
        self.assertTrue(self.bot.tg.uploads[2][2].endswith("_reel_9x16.mp4"))
        self.assertIn("Publish Night Drive?", self.bot.tg.sent[-1]["text"])
        self.assertTrue(self.bot.tg.sent[-1]["keyboard"])

    def test_delivery_survives_ffmpeg_being_unavailable(self):
        folder = make_release(self.tmp)

        def no_ffmpeg(args, timeout=0):
            raise FileNotFoundError("ffmpeg")
        self.bot._run_ffmpeg = no_ffmpeg
        self.bot._deliver(self.chat, {"base": os.path.join(folder, "Night-Drive"),
                                      "folder": folder, "title": "Night Drive"})
        kinds = [u[0] for u in self.bot.tg.uploads]
        self.assertEqual(kinds, ["sendPhoto", "sendAudio"])
        self.assertIn("Publish Night Drive?", self.bot.tg.sent[-1]["text"])

    # ---- the video render ----
    def test_video_render_is_vertical_and_reuses_an_existing_file(self):
        folder = make_release(self.tmp)
        out = self.bot._make_video(folder, "9x16")
        self.assertTrue(out.endswith("_reel_9x16.mp4"))
        args = self.ffmpeg_calls[-1]
        self.assertIn("720:1280", " ".join(args))
        self.assertIn("boxblur", " ".join(args))  # the square cover is not cropped away
        again = self.bot._make_video(folder, "9x16")
        self.assertEqual(out, again)
        self.assertEqual(len(self.ffmpeg_calls), 1)

    def test_video_render_makes_a_wide_one_for_youtube(self):
        folder = make_release(self.tmp)
        out = self.bot._make_video(folder, "16x9")
        self.assertTrue(out.endswith("_youtube_16x9.mp4"))
        self.assertIn("1280:720", " ".join(self.ffmpeg_calls[-1]))

    # ---- the taps ----
    def test_channel_tap_posts_audio_and_cover_with_ai_wording(self):
        folder = make_release(self.tmp)
        self.bot._publish_cb(self.chat, "pub:tg:" + self._key(folder))
        self.assertEqual([u[0] for u in self.bot.tg.uploads], ["sendPhoto", "sendAudio"])
        self.assertTrue(all(u[1] == zb.CHANNEL for u in self.bot.tg.uploads))
        self.assertIn(zb.PUBLISH_AI, self.bot.tg.uploads[-1][3])
        self.assertIn("posted", self.bot.tg.sent[-1]["text"])
        self.assertFalse([f for f in os.listdir(folder) if f.startswith("publish_request_")])

    def test_channel_tap_prefers_the_video(self):
        folder = make_release(self.tmp, video="Night-Drive_reel_9x16.mp4")
        self.bot._publish_cb(self.chat, "pub:tg:" + self._key(folder))
        self.assertEqual(self.bot.tg.uploads[0][0], "sendVideo")
        self.assertIn(zb.PUBLISH_AI, self.bot.tg.uploads[0][3])

    def test_platform_without_api_writes_a_package_and_posts_nothing(self):
        folder = make_release(self.tmp)
        self.bot._publish_cb(self.chat, "pub:tt:" + self._key(folder))
        self.assertEqual(self.bot.tg.uploads, [])
        req = json.load(open(os.path.join(folder, "publish_request_tt.json")))
        self.assertEqual(req["platform"], "tt")
        self.assertIn(zb.PUBLISH_AI, req["caption"])
        self.assertEqual(req["approved_by"], "owner tap in Telegram")
        self.assertTrue(req["files"])
        self.assertIn("no posting API", self.bot.tg.sent[-1]["text"])

    def test_youtube_tap_without_the_oauth_client_packages_and_says_why(self):
        folder = make_release(self.tmp)
        self.bot._publish_cb(self.chat, "pub:yt:" + self._key(folder))
        self.assertEqual(self.bot.tg.uploads, [])
        self.assertTrue(os.path.exists(os.path.join(folder, "publish_request_yt.json")))
        text = self.bot.tg.sent[-1]["text"]
        self.assertIn("not uploaded yet", text)
        self.assertIn("youtube_token.json", text)

    def test_youtube_tap_uploads_when_the_client_exists(self):
        folder = make_release(self.tmp)
        self.bot._youtube_upload = lambda f, t, c: "https://youtu.be/TESTID"
        self.bot._publish_cb(self.chat, "pub:yt:" + self._key(folder))
        self.assertIn("https://youtu.be/TESTID", self.bot.tg.sent[-1]["text"])
        self.assertFalse(os.path.exists(os.path.join(folder, "publish_request_yt.json")))

    def test_facebook_gives_him_the_caption_and_does_not_post(self):
        folder = make_release(self.tmp)
        self.bot._publish_cb(self.chat, "pub:fb:" + self._key(folder))
        self.assertEqual(self.bot.tg.uploads, [])
        text = self.bot.tg.sent[-1]["text"]
        self.assertIn("Facebook caption:", text)
        self.assertIn(zb.PUBLISH_AI, text)
        self.assertFalse([f for f in os.listdir(folder) if f.startswith("publish_request_")])

    def test_all_posts_the_channel_and_packages_the_rest(self):
        folder = make_release(self.tmp, video="Night-Drive_reel_9x16.mp4")
        self.bot._youtube_upload = lambda f, t, c: "https://youtu.be/TESTID"
        self.bot._publish_cb(self.chat, "pub:all:" + self._key(folder))
        self.assertEqual([u[1] for u in self.bot.tg.uploads], [zb.CHANNEL])
        self.assertTrue("https://youtu.be/TESTID" in self.bot.tg.sent[-1]["text"])
        for p in ("ig", "tt"):
            self.assertTrue(os.path.exists(os.path.join(folder, "publish_request_%s.json" % p)), p)
        self.assertIn("Facebook caption:", self.bot.tg.sent[-1]["text"])

    # ---- social links ----
    def test_social_buttons_are_the_verified_profiles(self):
        self.bot._social(self.chat)
        kb = self.bot.tg.sent[-1]["keyboard"]
        urls = [b["url"] for row in kb for b in row]
        self.assertEqual(urls, [u for _, u in zb.SOCIAL])
        for u in urls:
            self.assertTrue(u.startswith("https://"), u)
        self.assertIn("youtube.com/@rahalofficialmusic", " ".join(urls))
        self.assertIn("instagram.com/rahal.official.music", " ".join(urls))
        self.assertIn("tiktok.com/@rahalofficialmusic", " ".join(urls))
        self.assertIn("t.me/rahal_music", " ".join(urls))

    def test_social_button_works_without_a_builder(self):
        self.bot._callback(self.chat, "social")
        self.assertIn("Rahal everywhere", self.bot.tg.sent[-1]["text"])
        self.assertTrue(self.bot.tg.sent[-1]["keyboard"])

    def test_start_offers_the_menu_button(self):
        self.bot.owner = self.chat  # /start is owner-only
        self.bot._handle({"message": {"chat": {"id": self.chat, "type": "private"},
                                      "from": {"id": self.chat}, "text": "/start"}})
        boards = [m for m in self.bot.tg.sent if m.get("keyboard")]
        self.assertTrue(boards)
        self.assertEqual(boards[0]["keyboard"][0][0]["callback_data"], "menu")

    def test_commands_are_registered_on_start(self):
        self.bot._register_commands()
        called = [c[0][0] for c in self.bot.tg.calls]
        self.assertIn("setMyCommands", called)
        self.assertIn("setChatMenuButton", called)
        set_cmds = [c for c in self.bot.tg.calls if c[0][0] == "setMyCommands"][-1]
        cmds = [c["command"] for c in json.loads(set_cmds[1]["commands"])]
        self.assertIn("help", cmds)
        # the corner list stays short: the rest live in /help and in the inline menu
        self.assertLessEqual(len(cmds), 8)

    def test_stale_release_key_does_not_crash(self):
        self.bot._publish_cb(self.chat, "pub:tg:deadbeefdeadbeefdeadbeef")
        self.assertEqual(self.bot.tg.uploads, [])
        self.assertIn("/library", self.bot.tg.sent[-1]["text"])

    def test_publish_command_opens_the_menu_for_the_last_release(self):
        make_release(self.tmp, name="20261128-100000_Old")
        newest = make_release(self.tmp, name="20261128-120000_New")
        self.bot._publish_cmd(self.chat, "")
        kb = self.bot.tg.sent[-1]["keyboard"]
        keys = {b["callback_data"].split(":")[2] for row in kb for b in row
                if b["callback_data"].startswith("pub:")}
        self.assertEqual(keys, {self._key(newest)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
