"""The assistant: Arabic answers from the bot's real state, and nothing else."""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb          # noqa: E402
from bot import zi_assistant as za    # noqa: E402


class FakeTG:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, keyboard=None, reply=None):
        self.sent.append({"text": text, "keyboard": keyboard, "reply": reply})
        return {"ok": True}

    def call(self, *a, **k):
        return {}

    def _note(self, *a, **k):
        pass


EMPTY = {"build": "x", "engine": False, "rendering": None, "waiting": 0,
         "dataset": {"count": 0, "vocal": 0, "instrumental": 0, "unlabelled": 0},
         "liked": 0, "publish": {"youtube": False, "telegram": False},
         "lora": False, "voice": False, "ocr": False}

READY = {"build": "2026-11-28.21", "engine": True, "rendering": "Night Drive", "waiting": 2,
         "dataset": {"count": 12, "vocal": 7, "instrumental": 4, "unlabelled": 1},
         "liked": 3, "publish": {"youtube": True, "telegram": True},
         "lora": False, "voice": True, "ocr": True}


class AnswerTests(unittest.TestCase):
    def test_what_is_missing_lists_only_real_gaps(self):
        text = za.answer("ايه الناقص؟", READY)
        self.assertIn("تراكات مستر درغام: 12", text)
        self.assertIn("1 تراك لسه من غير تصنيف", text)
        self.assertIn("مستر درغام", text)
        self.assertNotIn("يوتيوب مش موجود", text)      # it is connected in this state
        self.assertNotIn("الإنجين مش محمّل", text)

    def test_nothing_missing_says_so(self):
        state = dict(READY, dataset={"count": 50, "vocal": 30, "instrumental": 20, "unlabelled": 0},
                     lora=True)
        self.assertIn("مفيش حاجة ناقصة", za.answer("إيه الناقص", state))

    def test_next_step_starts_with_the_engine_when_it_is_not_loaded(self):
        text = za.answer("أعمل ايه بعد كده؟", EMPTY)
        self.assertIn("خلية الإنجين", text)

    def test_next_step_counts_what_is_left(self):
        text = za.answer("اعمل ايه", READY)
        self.assertIn("فاضل 38", text)

    def test_dataset_question_uses_the_manifest_numbers(self):
        text = za.answer("عندي كام تراك للتدريب؟", READY)
        self.assertIn("عندك 12 تراك", text)
        self.assertIn("فوكال 7", text)

    def test_liked_question(self):
        self.assertIn("حفظت 3", za.answer("اللي عجبني", READY))
        self.assertIn("لسه محفظتش", za.answer("المفضلة", EMPTY))

    def test_publish_question_is_honest_about_what_posts(self):
        self.assertIn("يوتيوب", za.answer("النشر", READY))
        self.assertIn("مفيش منصة متوصلة", za.answer("النشر", EMPTY))

    def test_lora_question(self):
        self.assertIn("لسه مش متدرب", za.answer("موديل درغام", READY))
        self.assertIn("جاهز", za.answer("الموديل", dict(READY, lora=True)))

    def test_an_unknown_question_does_not_guess(self):
        text = za.answer("طب إيه رأيك في البحر؟", READY)
        self.assertIn("ما وصلنيش كويس", text)
        self.assertIn("ناقص", text)

    def test_status_reads_like_a_status(self):
        text = za.answer("الحالة", READY)
        self.assertIn("بيترندر دلوقتي: Night Drive", text)
        self.assertIn("مستني في الطابور: 2", text)

    def test_no_numbers_are_invented(self):
        text = za.answer("الحالة", EMPTY)
        self.assertIn("مستني في الطابور: 0", text)
        self.assertNotIn("50 (", text)


class PlainLanguageTests(unittest.TestCase):
    """No technical status in his face, no wrong intro, and the Dorgham count stays."""

    def test_the_status_answer_has_no_technical_words(self):
        text = za.status(READY)
        for word in ("الإنجين", "OCR", "الصوت", "النسخة", "build", "engine"):
            self.assertNotIn(word, text)
        self.assertIn("بيترندر دلوقتي", text)

    def test_the_status_answer_always_carries_the_dorgham_count(self):
        self.assertIn("تراكات مستر درغام", za.status(READY))
        self.assertIn("فاضل", za.status(READY))

    def test_the_intro_is_personal_not_his_name(self):
        text = za.answer("ازيك", READY)
        self.assertIn("أنا مساعدك الشخصي", text)
        self.assertNotIn("مساعد راهال", text)

    def test_zero_tracks_reads_like_a_sentence(self):
        text = za.dataset_line(dict(READY, dataset={"count": 0}))
        self.assertIn("لسه معندوش تراكات", text)
        self.assertIn("50", text)

    def test_a_model_answer_that_claims_a_capability_is_dropped(self):
        self.assertTrue(za.has_jargon("المحرك شغال والـ OCR والصوت مفعلين"))
        self.assertTrue(za.has_jargon("أنا مساعد راهال"))
        self.assertFalse(za.has_jargon("عندك 7 تراكات، وفاضل 43 للموديل"))


class BotWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=None)
        self.bot.tg = FakeTG()
        self.bot.owner = 9

    def say(self, text):
        self.bot._handle({"message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": text}})

    def test_status_is_plain_arabic_and_points_at_saving(self):
        self.bot._status(9)
        text = self.bot.tg.sent[-1]["text"]
        for word in ("Engine", "Rendering", "Waiting", "Outputs", "Pollers", "Owner"):
            self.assertNotIn(word, text)
        self.assertIn("طابور", text)
        self.assertTrue("Save Version" in text or "Drive" in text)

    def test_the_technical_lines_are_in_diag(self):
        self.bot._diag(9)
        text = self.bot.tg.sent[-1]["text"]
        self.assertIn("engine:", text)
        self.assertIn("pollers", text)

    def test_ask_with_a_question_answers_once(self):
        self.say("/ask ايه الناقص")
        self.assertIn("الرندر واقف", self.bot.tg.sent[-1]["text"])
        self.assertNotIn(9, self.bot.ask_mode)

    def test_ask_alone_opens_a_chat_and_free_text_answers(self):
        self.say("/ask")
        self.assertIn(9, self.bot.ask_mode)
        self.assertIn("مساعدك الشخصي", self.bot.tg.sent[-1]["text"])
        self.say("اعمل ايه")
        self.assertIn("خلية الإنجين", self.bot.tg.sent[-1]["text"])
        self.assertNotIn(9, self.bot.builders)       # it did not start a track

    def test_end_closes_the_chat(self):
        self.say("/ask")
        self.say("/end")
        self.assertNotIn(9, self.bot.ask_mode)
        self.assertIn("قفلت المحادثة", self.bot.tg.sent[-1]["text"])

    def test_the_word_for_leaving_closes_it(self):
        self.say("/ask")
        self.say("خروج")
        self.assertNotIn(9, self.bot.ask_mode)

    def test_menu_button_opens_the_assistant(self):
        self.bot._callback(9, "menu:assistant")
        self.assertIn(9, self.bot.ask_mode)

    def test_snapshot_reads_the_real_state(self):
        st = self.bot._snapshot()
        self.assertEqual(st["build"], zb.VERSION)
        self.assertFalse(st["engine"])
        self.assertEqual(st["dataset"]["count"], 0)
        self.assertIn("publish", st)


if __name__ == "__main__":
    unittest.main(verbosity=2)
