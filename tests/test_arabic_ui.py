"""Menus: Arabic labels, never more than two buttons per row."""
import os, re, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402
from tests.test_voice import FakeTG  # noqa: E402


class ArabicUI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bot = zb.Bot("T", out_root=self.tmp, work=self.tmp, make_track=lambda s: None)
        self.bot.tg = FakeTG()
        self.bot.owner = 5

    def rows_ok(self, kb):
        for row in kb or []:
            self.assertLessEqual(len(row), 2, row)

    def test_menu_social_length_quality_rows(self):
        self.bot._menu(5)
        self.bot._social(5)
        self.rows_ok(self.bot.tg.sent[-2]["keyboard"])
        self.rows_ok(self.bot.tg.sent[-1]["keyboard"])
        self.rows_ok(self.bot._length_kb())

    def test_help_and_menu_are_arabic(self):
        self.assertTrue(re.search(r"[\u0600-\u06FF]", zb.HELP))
        self.bot._menu(5)
        for row in self.bot.tg.sent[-1]["keyboard"]:
            for b in row:
                self.assertTrue(re.search(r"[\u0600-\u06FF]", b["text"]), b["text"])


if __name__ == "__main__":
    unittest.main()
