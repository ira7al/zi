import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))
import zi_options as o


class House(unittest.TestCase):
    def test_default_is_house_style(self):
        r = o.build_prompt("")
        self.assertEqual(r["style"], "house style")
        self.assertEqual(r["bpm"], 124)
        for w in ("round sidechained sub bass", "punchy dry kick", "offbeat open hats", "warm wide analog pads", "headroom"):
            self.assertIn(w, r["prompt"])

    def test_other_styles_share_traits(self):
        for idea in ("peak techno", "afro house", "indie dance", "downtempo"):
            r = o.build_prompt(idea)
            self.assertIn("warm polished master with headroom", r["prompt"], idea)
            self.assertNotEqual(r["style"], "house style", idea)

    def test_eastern_flavor_optional(self):
        self.assertIn("oud-like", o.build_prompt("eastern vibe")["prompt"])
        self.assertNotIn("oud-like", o.build_prompt("")["prompt"])

    def test_no_artist_names(self):
        self.assertNotIn("Spotify", o.build_prompt("")["prompt"])


if __name__ == "__main__":
    unittest.main()
