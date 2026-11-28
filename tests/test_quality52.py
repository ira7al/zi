import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb
from bot import zi_options as zo
from tests.test_remix46 import make_bot

SHOT = ("A minimalist 3D abstract visual composition, glowing metallic rings and tubes with soft reflections, "
        "dark background, studio lighting, no text or logos.")


class Visual(unittest.TestCase):
    def test_image_prompt_vs_music_prompt(self):
        self.assertTrue(zo.is_visual_text(SHOT))
        self.assertFalse(zo.is_visual_text("melodic techno, 124 bpm, glossy pads, deep sub bass, dark mood"))
        self.assertFalse(zo.is_visual_text("deep house with warm background pads"))

    def test_enqueue_never_sends_an_image_description(self):
        b = make_bot(())
        got = []
        b.make_track = lambda *a, **k: None
        b.jobs.put = lambda j: got.append(j)
        zb.Bot._enqueue(b, 5, {"genre": "indie dance", "idea": SHOT, "seconds": 330})
        spec = got[0][1]
        self.assertFalse(zo.is_visual_text(spec["idea"]))
        self.assertNotIn("3D", spec["idea"])

    def test_photo_that_is_artwork_is_not_a_reference(self):
        b = make_bot(())
        b.builders[5] = {"step": "ref_wait", "spec": {}}
        b._llm = lambda: True
        b._download_file = lambda fid: b"x"
        b._vision_text = lambda path, prompt=None: SHOT
        b._reference_photo(5, {"file_id": "f"})
        self.assertNotIn("built", b.builders[5])
        self.assertTrue(b.tg.sent)


class Speech(unittest.TestCase):
    def test_numbers_and_terms(self):
        ch, _ = zo.parse_spec_edits("خليها خمس دقايق بي بي إم مية وخمسة وعشرين مقام صبا")
        self.assertEqual((ch["bpm"], ch["seconds"]), (125, 300))
        self.assertIn("Saba", ch["maqam"])
        self.assertEqual(zo.parse_spec_edits("125 BPM A minor")[0]["key"], "A minor")
        self.assertEqual(zo.parse_spec_edits("لا مينور")[0]["key"], "A minor")
        self.assertEqual(zo.parse_spec_edits("صوت ست حلو")[0], {})

    def test_maqam_reaches_the_prompt(self):
        b = make_bot(())
        spec = b._normalize_spec({"genre": "melodic techno", "idea": "deep techno", "maqam": zo.MAQAM[0][2]})
        self.assertIn("maqam Saba", spec["idea"])
        spec = b._normalize_spec({"genre": "x", "idea": "deep techno", "exclude": "vocals", "style_tags": "oud"})
        self.assertIn("Avoid: vocals", spec["idea"])


class Redo(unittest.TestCase):
    def test_words(self):
        for t in ("the track is bad, make another one", "التراك وحش اعمل واحد تاني", "مش عاجبني"):
            self.assertTrue(zo.is_redo_words(t), t)
        self.assertFalse(zo.is_redo_words("make a melodic techno track"))

    def test_voice_redo_builds_a_summary_with_a_new_seed(self):
        b = make_bot(())
        b.last_enq[5] = {"genre": "indie dance", "idea": "indie dance, warm", "seconds": 330, "seed": 77,
                         "quality": "high", "instrumental": True, "bpm": 122}
        b._handle({"update_id": 1, "message": {"chat": {"id": 5}, "from": {"id": 5}, "text": "the track is bad, make another one"}})
        spec = b.builders[5]["spec"]
        self.assertNotIn("seed", spec)
        self.assertIn("Redo variation", spec["idea"])
        self.assertEqual(b.builders[5]["step"], "options")
        self.assertIn("مش عاجبك", b.tg.sent[0]["text"])

    def test_no_previous_track_falls_through(self):
        b = make_bot(())
        b._last_spec = lambda: None
        self.assertFalse(b._redo(5, "bad"))


class Trace(unittest.TestCase):
    def test_trace_has_text_and_route_but_no_tokens(self):
        b = make_bot(())
        b.trace("in", text="hello 123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx token abc")
        b.trace("in", text="key=" + "A" * 40)
        raw = open(os.path.join(b.out_root, "zi_bot_trace.jsonl")).read()
        self.assertIn("hello", raw)
        self.assertNotIn("AAFxxxx", raw)
        self.assertNotIn("A" * 40, raw)
        b.owner = 5
        b._handle({"update_id": 1, "message": {"chat": {"id": 5}, "from": {"id": 5}, "text": "/trace"}})
        self.assertIn("hello", b.tg.sent[-1]["text"])

    def test_models_never_requested_when_missing(self):
        b = make_bot(())
        spec = b._normalize_spec({"genre": "x", "idea": "deep techno", "model": "turbo-shift3"})
        self.assertNotIn("model", spec)
        b.make_track = lambda *a: None
        b.make_track.__globals__  # function globals exist
        self.assertEqual(b._models_available(), {"turbo"})
