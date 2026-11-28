import ast, json, os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb

AR = re.compile("[\u0600-\u06ff]")
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot", "zi_bot.py")


def literal_button_texts():
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            ks = [k.value if isinstance(k, ast.Constant) else None for k in n.keys]
            if "text" in ks and ("callback_data" in ks or "url" in ks):
                v = n.values[ks.index("text")]
                for c in ast.walk(v):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str) and AR.search(c.value):
                        out.add(c.value)
    return out


class Buttons(unittest.TestCase):
    def test_every_literal_label_is_english(self):
        texts = literal_button_texts()
        self.assertTrue(len(texts) > 30)
        bad = [t for t in texts if AR.search(zb.en_button(t))]
        # f-string pieces (like "ولّد: ") are covered by the dynamic tests below
        bad = [t for t in bad if t.strip() not in ("ولّد:", "ولّد: ")]
        self.assertEqual(bad, [])

    def test_tables(self):
        for _q, label in zb.QUALITIES:
            self.assertFalse(AR.search(zb.en_button(label)), label)
        for t, _c in zb.Bot.SUGGESTIONS:
            self.assertFalse(AR.search(zb.en_button(t)), t)
        for name, _v in zb.Bot.COVER_CLOSE:
            self.assertFalse(AR.search(zb.en_button("ولّد: " + name)), name)
        for code, v in zb.Bot.TWEAKS.items():
            for w in (("أقصر", "أطول") if v[0] == "seconds" else ("أبطأ", "أسرع") if v[0] == "bpm" else ("أقل", "أكتر")):
                self.assertFalse(AR.search(zb.en_button(v[5] + " " + w)), v[5] + w)

    def test_examples_and_passthrough(self):
        self.assertEqual(zb.en_button("\U0001f3b5 تراك جديد"), "\U0001f3b5 New Track")
        self.assertEqual(zb.en_button("\U0001f4da المكتبة"), "\U0001f4da Library")
        self.assertEqual(zb.en_button("Melodic Techno"), "Melodic Techno")
        self.assertEqual(zb.en_button("\u2b50 Night Drive"), "\u2b50 Night Drive")

    def test_keyboard_keeps_callbacks_and_urls(self):
        kb = [[{"text": "ولّد", "callback_data": "go"}, {"text": "الستوديو (الويب)", "url": "https://x"}]]
        out = zb.en_keyboard(kb)
        self.assertEqual(out[0][0]["callback_data"], "go")
        self.assertEqual(out[0][1]["url"], "https://x")
        self.assertEqual(out[0][0]["text"], "\u25b6\ufe0f Generate")
        self.assertEqual(kb[0][0]["text"], "ولّد")

    def test_telegram_payload_is_english(self):
        sent = {}
        t = zb.TG.__new__(zb.TG)
        t.thread_of = None
        t.call = lambda m, **f: sent.update(f) or {}
        t._note = lambda *a, **k: None
        t.send(1, "اختار", keyboard=[[{"text": "\U0001f4da المكتبة", "callback_data": "menu:library"}]])
        self.assertIn("Library", sent["reply_markup"])
        self.assertNotRegex(sent["reply_markup"], "[\u0600-\u06ff]")
