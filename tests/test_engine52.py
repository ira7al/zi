import os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_patch(models):
    seen = []
    ns = {"MODELS": models, "MODEL_MAP": {"xl": "acestep-v15-xl"}, "post": lambda path, payload, *a, **k: seen.append((path, payload)) or {}}
    exec(open(os.path.join(ROOT, "colab", "engine_patch_52.py")).read(), ns)
    return ns, seen


class Patch52(unittest.TestCase):
    def test_turbo_steps_cut_and_guidance_dropped(self):
        ns, seen = run_patch(["acestep-v15-turbo"])
        ns["post"]("/release_task", {"model": "acestep-v15-turbo", "inference_steps": 14, "guidance_scale": 7.0,
                                      "thinking": True, "batch_size": 2})
        sent = seen[-1][1]
        self.assertEqual(sent["inference_steps"], 8)
        self.assertNotIn("guidance_scale", sent)
        self.assertIs(sent["use_cot_caption"], False)
        self.assertEqual(ns["ENGINE_USED"]["steps_asked"], 14)
        self.assertEqual(ns["ENGINE_USED"]["steps_used"], 8)

    def test_non_turbo_keeps_guidance_and_more_steps(self):
        ns, seen = run_patch(["acestep-v15-sft"])
        ns["post"]("/release_task", {"model": "acestep-v15-sft", "inference_steps": 30, "guidance_scale": 7.0})
        self.assertEqual(seen[-1][1]["inference_steps"], 30)
        self.assertEqual(seen[-1][1]["guidance_scale"], 7.0)

    def test_other_paths_untouched_and_run_twice(self):
        ns, seen = run_patch([])
        ns["post"]("/query_result", {"x": 1})
        self.assertEqual(seen[-1], ("/query_result", {"x": 1}))
        exec(open(os.path.join(ROOT, "colab", "engine_patch_52.py")).read(), ns)
        ns["post"]("/release_task", {"model": "acestep-v15-turbo", "inference_steps": 20})
        self.assertEqual(len(seen), 2)             # wrapped once, not twice

    def test_pick_model_prefers_xl_then_shift3(self):
        ns, _ = run_patch(["acestep-v15-turbo", "acestep-v15-turbo-shift3", "acestep-v15-xl-turbo"])
        self.assertEqual(ns["pick_model"]("high"), "acestep-v15-xl-turbo")
        self.assertEqual(ns["pick_model"]("standard"), "acestep-v15-turbo")
        self.assertEqual(ns["MODEL_MAP"]["xl"], "acestep-v15-xl-turbo")
        ns, _ = run_patch(["acestep-v15-turbo"])
        self.assertEqual(ns["pick_model"]("high"), "acestep-v15-turbo")
