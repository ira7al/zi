"""The shared option model: statuses, prompt text, and the mapping onto engine fields."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot"))
import zi_options as opt


class OptionModelTests(unittest.TestCase):
    def test_every_option_has_a_status_and_a_note_when_not_live(self):
        for o in opt.OPTIONS:
            self.assertIn(o["status"], ("live", "text", "coming"), o["key"])
            if o["status"] != "live":
                self.assertTrue(o.get("note"), o["key"])

    def test_parity_items_are_live(self):
        for key in ("prompt", "instrumental", "lyrics", "style_tags", "title",
                    "seconds", "bpm", "key", "steps", "seed", "model"):
            self.assertEqual(opt.status_of(key), "live", key)

    def test_gaps_are_marked_coming(self):
        for key in ("reference_audio", "lora", "cover"):
            self.assertEqual(opt.status_of(key), "coming", key)

    def test_guidance_mapping_covers_the_range(self):
        self.assertEqual(opt.guidance_from_influence(0), 3.0)
        self.assertEqual(opt.guidance_from_influence(50), 7.5)
        self.assertEqual(opt.guidance_from_influence(100), 12.0)
        self.assertIsNone(opt.guidance_from_influence("x"))

    def test_engine_fields_for_an_instrumental(self):
        f = opt.engine_payload_fields({"instrumental": True, "bpm": 122, "key": "A minor", "steps": 14})
        self.assertEqual(f["lyrics"], "[inst]")
        self.assertTrue(f["instrumental"])
        self.assertEqual(f["key_scale"], "A minor")
        self.assertEqual(f["inference_steps"], 14)

    def test_engine_fields_for_own_lyrics(self):
        f = opt.engine_payload_fields({"instrumental": False, "lyrics": "[Verse] hi"})
        self.assertEqual(f["lyrics"], "[Verse] hi")
        self.assertFalse(f["instrumental"])

    def test_no_lyrics_and_not_instrumental_sends_no_lyrics_field(self):
        f = opt.engine_payload_fields({"instrumental": False, "lyrics": "  "})
        self.assertNotIn("lyrics", f)

    def test_seed_and_guidance_only_when_set(self):
        self.assertNotIn("seed", opt.engine_payload_fields({"seed": None}))
        self.assertNotIn("guidance_scale", opt.engine_payload_fields({}))
        self.assertEqual(opt.engine_payload_fields({"seed": 42})["seed"], 42)

    def test_controls_change_only_the_prompt(self):
        base = opt.normalize({"idea": "melodic techno", "exclude": "trance stabs",
                              "style_tags": "analog, tape", "weirdness": 10})
        self.assertIn("Avoid: trance stabs", base["idea"])
        self.assertIn("Style tags: analog, tape", base["idea"])
        self.assertIn("Familiar club structure", base["idea"])
        self.assertEqual(base["exclude"], "trance stabs")  # kept for the apps, not sent to the engine


if __name__ == "__main__":
    unittest.main(verbosity=2)
