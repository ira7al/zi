import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_assistant as za
from bot import zi_bot as zb
from tests.test_remix46 import make_bot

SHOT = ("البرومبت: A minimalist 3D abstract visual composition for a deep melodic techno track, "
        "glowing metallic rings and tubes with soft reflections, dark background, no text or logos.")
EN = SHOT.split(": ", 1)[1]


class Resp:
    def __init__(self, d): self.d = d
    def read(self): return json.dumps(self.d).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def groq_opener(content):
    def op(req, timeout=0):
        return Resp({"choices": [{"message": {"content": content}}]})
    return lambda o=None: op


class Helpers(unittest.TestCase):
    def test_label_stripped_and_english_detected(self):
        self.assertEqual(za.strip_prompt_label(SHOT), EN)
        self.assertTrue(za.is_probably_english(EN))
        self.assertFalse(za.is_probably_english("make a dark techno track يا باشا"))
        self.assertFalse(za.is_probably_english("Сделай мрачный техно трек"))

    def test_translate_parses_json_and_rejects_foreign(self):
        good = '{"lang":"Russian","english":"dark techno, 125 bpm"}'
        orig = za._opener
        try:
            za._opener = lambda o=None: (lambda req, timeout=0: Resp({"choices": [{"message": {"content": good}}]}))
            r = za.to_english_prompt("Сделай мрачный техно", "K")
            self.assertEqual(r["english"], "dark techno, 125 bpm")
            bad = '{"lang":"x","english":"тёмный"}'
            za._opener = lambda o=None: (lambda req, timeout=0: Resp({"choices": [{"message": {"content": bad}}]}))
            self.assertIsNone(za.to_english_prompt("x y", "K", tries=1))
        finally:
            za._opener = orig
        self.assertIsNone(za.to_english_prompt("hi", ""))


class Flow(unittest.TestCase):
    def test_english_with_label_passes_no_refusal(self):
        b = make_bot(())
        b.groq_key = ""
        r = b._english_text(5, SHOT)
        self.assertEqual(r[0], EN)
        self.assertFalse(any("بيفهم إنجليزي" in str(m) for m in b.tg.sent))

    def test_russian_goes_to_groq(self):
        b = make_bot(()); b.groq_key = "K"; b._llm = lambda: True
        orig = zb.ziassist.to_english_prompt
        zb.ziassist.to_english_prompt = lambda t, k, **kw: {"lang": "Russian", "english": "dark techno"}
        try:
            self.assertEqual(b._english_text(5, "Сделай мрачный техно"), ("dark techno", True))
        finally:
            zb.ziassist.to_english_prompt = orig

    def test_no_key_foreign_asks_politely(self):
        b = make_bot(()); b.groq_key = ""; b._llm = lambda: False
        self.assertIsNone(b._english_text(5, "Сделай мрачный техно"))
        self.assertTrue(b.tg.sent)

if __name__ == "__main__":
    unittest.main()
