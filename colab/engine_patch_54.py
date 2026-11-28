# Engine patch for bot build .54: fall back when an XL generation fails. Paste into ONE new notebook cell and run it
# AFTER the engine cell and the .52 patch cell, same kernel. Safe to run twice. It changes nothing on disk.
#  1. The XL generation fails (out of memory, decode error, server crash): try XL once more in a light mode
#     (batch 1, language model off). If that fails too and the small turbo model is on the server, use it.
#  2. ENGINE_USED["fallback"] says what happened ("", "xl_light" or "turbo") and ENGINE_USED["model"] is the model
#     that made the track. The bot tells the user which model it was.
if "ENGINE_USED" not in globals():
    ENGINE_USED = {}
FALLBACK_54 = {"light": False}

if not globals().get("_POST_WRAPPED_54"):
    _POST_WRAPPED_54 = True
    _post_inner_54 = post

    def post(path, payload, *a, **k):
        if path == "/release_task" and isinstance(payload, dict) and FALLBACK_54["light"]:
            payload = dict(payload)
            payload["batch_size"] = 1
            payload["thinking"] = False
        return _post_inner_54(path, payload, *a, **k)

if not globals().get("_GC_WRAPPED_54"):
    _GC_WRAPPED_54 = True
    _gc_inner_54 = gen_candidates

    def gen_candidates(spec, quality="standard"):
        try:
            out = _gc_inner_54(spec, quality)
            ENGINE_USED["fallback"] = ""
            return out
        except Exception as e1:
            if "xl" not in str(ENGINE_USED.get("model", "")):
                raise
            print("  ! XL generation failed (" + repr(e1)[:200] + "), trying the light XL mode")
            FALLBACK_54["light"] = True
            try:
                out = _gc_inner_54(spec, quality)
                ENGINE_USED["fallback"] = "xl_light"
                return out
            except Exception as e2:
                if "acestep-v15-turbo" not in [str(m) for m in (MODELS or [])]:
                    raise
                print("  ! light XL failed too (" + repr(e2)[:200] + "), using the small turbo model")
                spec2 = dict(spec); spec2["model"] = "turbo"
                out = _gc_inner_54(spec2, quality)
                ENGINE_USED["fallback"] = "turbo"
                return out
            finally:
                FALLBACK_54["light"] = False
print("engine patch .54 ready (XL fallback). Models on the server:", list(MODELS or []))
