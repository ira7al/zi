import os, sys, tempfile, time, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb, zi_assistant as za
from tests.test_voice import FakeTG


def pm(text=None, photo=False, caption=None, reply_photo=False):
    m = {"chat": {"id": 5}}
    if text: m["text"] = text
    if photo: m["photo"] = [{"file_id": "f1"}]
    if caption: m["caption"] = caption
    if reply_photo: m["reply_to_message"] = {"photo": [{"file_id": "f1"}]}
    return {"message": m}


class Combine(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.bot.tg = FakeTG(); self.bot.owner = 5; self.bot._launcher_sent = True
        self.asked = []
        self.bot._assistant = lambda c, q, **k: self.asked.append(q)
        self.bot._describe_photo = lambda p: "a settings screen with a red button"
        self.bot._reference_photo = lambda c, p: self.asked.append("REFPHOTO")
        self.bot._reference_link = lambda c, u: self.asked.append("REFLINK " + u)
        self.bot._llm = lambda: True

    def test_image_then_text_is_one_request(self):
        self.bot._handle(pm(photo=True))
        self.assertEqual(self.asked, [])
        self.assertIn("img:ref", [b["callback_data"] for r in self.bot.tg.sent[-1]["keyboard"] for b in r])
        self.bot._handle(pm("إيه الزرار الأحمر ده؟"))
        self.assertEqual(len(self.asked), 1)
        self.assertIn("red button", self.asked[0]); self.assertIn("الزرار الأحمر", self.asked[0])

    def test_text_then_image_within_window(self):
        self.bot._handle(pm("ايه الي في الصورة دي"))
        self.bot._assistant = lambda c, q, **k: self.asked.append(q)
        self.asked.clear()
        self.bot._handle(pm(photo=True))
        self.assertEqual(len(self.asked), 1); self.assertIn("red button", self.asked[0])

    def test_caption_and_reply_join(self):
        self.bot._handle(pm(photo=True, caption="شوف الشاشة دي"))
        self.assertIn("red button", self.asked[-1])
        self.bot._handle(pm("ده ايه", reply_photo=True))
        self.assertEqual(len(self.asked), 2)

    def test_reference_words_use_style_flow(self):
        self.bot._handle(pm(photo=True))
        self.bot._handle(pm("ده المرجع"))
        self.assertEqual(self.asked, ["REFPHOTO"])

    def test_link_with_instruction(self):
        self.bot._handle(pm("ده المرجع https://example.com/x"))
        self.assertEqual(self.asked, ["REFLINK https://example.com/x"])

    def test_link_after_instruction(self):
        self.bot._handle(pm("خد ده كمرجع للستايل"))
        self.asked.clear()
        self.bot._handle(pm("https://example.com/y"))
        self.assertEqual(self.asked, ["REFLINK https://example.com/y"])

    def test_stale_image_is_dropped(self):
        self.bot._handle(pm(photo=True))
        self.bot.pending[5]["ts"] -= 200
        self.bot._handle(pm("إيه ده؟"))
        self.assertEqual(self.asked, ["إيه ده؟"])

    def test_vision_failure_is_honest(self):
        self.bot._describe_photo = lambda p: None
        self.bot._handle(pm(photo=True, caption="إيه ده؟"))
        self.assertEqual(self.asked, [])
        self.assertIn("معرفتش أقرا الصورة", self.bot.tg.sent[-1]["text"])

    def test_drop_button(self):
        self.bot._handle(pm(photo=True))
        self.bot._callback(5, "img:drop")
        self.assertNotIn(5, self.bot.pending)


class Prompt(unittest.TestCase):
    def test_vision_prompt_passed(self):
        import json
        seen = {}
        class R:
            def read(s): return json.dumps({"choices": [{"message": {"content": "a phone screen"}}]}).encode()
            def __enter__(s): return s
            def __exit__(s, *a): return False
        def op(req, timeout=0):
            seen["b"] = req.data; return R()
        t, _ = za.read_image_groq(b"x" * 10, "K", opener=op, prompt="DESCRIBE_ME")
        self.assertEqual(t, "a phone screen"); self.assertIn(b"DESCRIBE_ME", seen["b"])


if __name__ == "__main__":
    unittest.main()
