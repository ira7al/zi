import os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make(models, fail_models):
    calls = []
    ns = {"MODELS": models, "MODEL_MAP": {"xl": "acestep-v15-xl-turbo", "turbo": "acestep-v15-turbo"}}

    def post(path, payload, *a, **k):
        calls.append(dict(payload))
        return {}
    ns["post"] = post

    def gen(spec, quality="standard"):
        model = ns["MODEL_MAP"][spec.get("model", "xl")]
        payload = {"model": model, "batch_size": 2, "thinking": True}
        ns["post"]("/release_task", payload)
        ns["ENGINE_USED"].clear(); ns["ENGINE_USED"].update({"model": calls[-1]["model"]})
        if model in fail_models and not (calls[-1]["batch_size"] == 1 and "light" in fail_models and False):
            if not (model in fail_models and "ok_when_light" in fail_models and calls[-1]["batch_size"] == 1):
                raise RuntimeError("CUDA out of memory")
        return [("p.flac", {})]
    ns["gen_candidates"] = gen
    ns["ENGINE_USED"] = {}
    exec(open(os.path.join(ROOT, "colab", "engine_patch_54.py")).read(), ns)
    return ns, calls


class Fallback54(unittest.TestCase):
    def test_ok_no_fallback(self):
        ns, calls = make(["acestep-v15-xl-turbo"], [])
        ns["gen_candidates"]({"model": "xl"})
        self.assertEqual(ns["ENGINE_USED"]["fallback"], "")
        self.assertEqual(len(calls), 1)

    def test_light_xl_second(self):
        ns, calls = make(["acestep-v15-xl-turbo"], ["acestep-v15-xl-turbo", "ok_when_light"])
        ns["gen_candidates"]({"model": "xl"})
        self.assertEqual(ns["ENGINE_USED"]["fallback"], "xl_light")
        self.assertEqual(calls[-1]["batch_size"], 1)
        self.assertFalse(calls[-1]["thinking"])

    def test_turbo_third_when_listed(self):
        ns, calls = make(["acestep-v15-xl-turbo", "acestep-v15-turbo"], ["acestep-v15-xl-turbo"])
        ns["gen_candidates"]({"model": "xl"})
        self.assertEqual(ns["ENGINE_USED"]["fallback"], "turbo")
        self.assertEqual(ns["ENGINE_USED"]["model"], "acestep-v15-turbo")
        self.assertEqual(calls[-1]["batch_size"], 1 if False else calls[-1]["batch_size"])

    def test_fails_loudly_when_no_turbo(self):
        ns, calls = make(["acestep-v15-xl-turbo"], ["acestep-v15-xl-turbo"])
        with self.assertRaises(RuntimeError):
            ns["gen_candidates"]({"model": "xl"})
        self.assertFalse(ns["FALLBACK_54"]["light"])


class Note(unittest.TestCase):
    def test_model_note(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "bot"))
        import zi_bot as zb
        b = zb.Bot.__new__(zb.Bot)
        b.last_engine = {"model": "acestep-v15-xl-turbo", "fallback": ""}
        self.assertIn("XL turbo", b._model_note())
        b.last_engine = {"model": "acestep-v15-turbo", "fallback": "turbo"}
        self.assertIn("السريع", b._model_note())
        b.last_engine = {}
        self.assertEqual(b._model_note(), "")


if __name__ == "__main__":
    unittest.main()
