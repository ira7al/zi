# Engine patch for bot build .52: honest settings. Paste into ONE new notebook cell and run it AFTER the engine
# cell (and after the .46 patch cell if you use it), same kernel. Safe to run twice. It changes nothing on disk.
#  - Turbo models run exactly 8 steps and ignore guidance: a request for more steps is cut to 8 and the
#    guidance_scale field is not sent. What was really used is kept in ENGINE_USED (the bot logs it).
#  - The language model is told to keep our caption (use_cot_caption false) instead of rewriting it.
#  - pick_model prefers the XL turbo model for High quality when the server lists it, then shift3, then turbo.
#  - MODEL_MAP["xl"] points at the real XL names (acestep-v15-xl-turbo, -sft, -base).
ENGINE_USED = {}
TURBO_STEPS = 8

def _steps_cap(model):
    return TURBO_STEPS if "turbo" in (model or "") else 50

if not globals().get("_POST_WRAPPED_52"):
    _POST_WRAPPED_52 = True
    _post_inner_52 = post

    def post(path, payload, *a, **k):
        if path == "/release_task" and isinstance(payload, dict):
            payload = dict(payload)
            model = str(payload.get("model") or "")
            asked = payload.get("inference_steps")
            cap = _steps_cap(model)
            if asked and int(asked) > cap:
                payload["inference_steps"] = cap
            if "turbo" in model:
                payload.pop("guidance_scale", None)       # distilled: guidance is fixed, so no dial is offered
            if payload.get("thinking") and "use_cot_caption" not in payload:
                payload["use_cot_caption"] = False        # keep our caption, do not let the LM rewrite it
            ENGINE_USED.clear()
            ENGINE_USED.update({"model": model, "steps_asked": asked, "steps_used": payload.get("inference_steps"),
                                "guidance_sent": payload.get("guidance_scale"), "thinking": payload.get("thinking"),
                                "batch": payload.get("batch_size"), "task": payload.get("task_type") or "text2music"})
        return _post_inner_52(path, payload, *a, **k)

def pick_model(quality="standard"):
    have = [str(m) for m in (MODELS or [])]
    if quality == "high":
        for pref in ("acestep-v15-xl-turbo", "acestep-v15-turbo-shift3"):
            if pref in have:
                return pref
    return "acestep-v15-turbo"

try:
    MODEL_MAP["xl"] = next((m for m in (MODELS or []) if "xl-turbo" in str(m)), "acestep-v15-xl-turbo")
except Exception:
    pass
print("engine patch .52 ready. Models on the server:", list(MODELS or []))
