"""The prompt has to fit the length he picked, say whether there are vocals, and stay English."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_options as opt  # noqa: E402


def bars_of(prompt):
    return int(prompt.split("about ")[1].split(" bars")[0])


class PromptQualityTests(unittest.TestCase):
    def test_structure_fits_the_length_at_any_tempo(self):
        for seconds, bpm in ((120, 122), (180, 130), (330, 122), (330, 102), (420, 124), (600, 100)):
            built = opt.build_prompt(f"{bpm} bpm techno", seconds)
            bars = bars_of(built["prompt"])
            real = bars * 240.0 / bpm
            self.assertLess(abs(real - seconds), max(6, seconds * 0.03),
                            f"{seconds}s at {bpm} bpm came out as {real:.0f}s")

    def test_bpm_in_the_idea_sets_the_tempo_and_the_bars(self):
        built = opt.build_prompt("102 bpm downtempo, hazy", 330)
        self.assertEqual(built["bpm"], 102)
        self.assertIn("102 BPM", built["prompt"])
        self.assertLess(abs(bars_of(built["prompt"]) * 240 / 102 - 330), 8)

    def test_instrumental_says_so_and_vocal_gets_a_voice(self):
        inst = opt.build_prompt("melodic techno, night drive", 330, 0, instrumental=True)["prompt"]
        vox = opt.build_prompt("melodic techno, night drive", 330, 0, instrumental=False)["prompt"]
        self.assertIn("Instrumental, no vocals", inst)
        self.assertNotIn("Lead vocal", inst)
        self.assertIn("Lead vocal", vox)
        self.assertNotIn("Instrumental, no vocals", vox)

    def test_vocal_language_reaches_the_engine(self):
        f = opt.engine_payload_fields({"instrumental": False, "lyrics": "[Verse] hi", "lang": "ar"})
        self.assertEqual(f["vocal_language"], "ar")
        self.assertFalse(f["instrumental"])
        self.assertEqual(f["lyrics"], "[Verse] hi")
        i = opt.engine_payload_fields({"instrumental": True})
        self.assertEqual(i["lyrics"], "[inst]")
        self.assertNotIn("vocal_language", i)

    def test_an_arabic_theme_stays_out_of_the_english_prompt(self):
        built = opt.build_prompt("حبيبي الليل طويل, techno", 330)
        self.assertFalse(opt.has_non_latin(built["prompt"]))
        self.assertIn("another script", " ".join(built["removed"]))

    def test_artist_references_are_still_stripped(self):
        built = opt.build_prompt("techno in the style of Some Famous DJ, dark", 330)
        self.assertNotIn("Some Famous DJ", built["prompt"])
        self.assertTrue(built["removed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
