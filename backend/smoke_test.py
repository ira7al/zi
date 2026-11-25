#!/usr/bin/env python3
"""One real 180 s generation against Replicate, with checks. Standard library only (+ ffprobe).

  export REPLICATE_API_TOKEN=r8_...        # your token, never commit it
  python smoke_test.py                      # uses MUSIC_MODEL or stability-ai/stable-audio-2.5

Cost: one prediction. Exit code 0 = all checks passed.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

API = os.getenv("REPLICATE_API_BASE", "https://api.replicate.com/v1")
TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
MODEL = os.getenv("MUSIC_MODEL", "stability-ai/stable-audio-2.5")
SECONDS = int(os.getenv("SMOKE_SECONDS", "180"))
INPUT = {"prompt": "Warm analog synth pad, soft pulsing bassline, gentle drums, uplifting instrumental "
                   "with intro, build, climax and outro. Instrumental only, no vocals.",
         "duration": SECONDS, "steps": 8, "cfg_scale": 1}


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"FAIL: HTTP {e.code} from {url}: {e.read()[:300].decode(errors='replace')}")


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))
    return ok


def main():
    if not TOKEN:
        sys.exit("Set REPLICATE_API_TOKEN first.")
    model = call("GET", f"{API}/models/{MODEL}")
    version = (model.get("latest_version") or {}).get("id")
    print(f"model={MODEL} version={version}\nlicense_url={model.get('license_url')} (read it before setting MODEL_LICENSE_COMMERCIAL=1)")
    body = {"input": INPUT}
    url = f"{API}/predictions" if version else f"{API}/models/{MODEL}/predictions"
    if version:
        body["version"] = version
    pred = call("POST", url, body)
    print("started", pred["id"])
    t0 = time.time()
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        if time.time() - t0 > 900:
            sys.exit("FAIL: timed out after 900 s")
        time.sleep(5)
        pred = call("GET", f"{API}/predictions/{pred['id']}")
        print(f"  {pred['status']} ({int(time.time() - t0)}s)")
    results = [check("status succeeded", pred["status"] == "succeeded", pred.get("error") or "")]
    if pred["status"] != "succeeded":
        sys.exit(1)
    out = pred["output"]
    out = out[0] if isinstance(out, list) else out
    results.append(check("output is a URL", isinstance(out, str) and out.startswith("http"), str(out)[:80]))
    os.makedirs("smoke", exist_ok=True)
    path = os.path.join("smoke", "out" + (os.path.splitext(out.split("?")[0])[1] or ".wav"))
    urllib.request.urlretrieve(out, path)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=sample_rate,channels",
                            "-of", "json", path], capture_output=True, text=True)
    info = json.loads(probe.stdout or "{}")
    secs = float((info.get("format") or {}).get("duration", 0))
    stream = (info.get("streams") or [{}])[0]
    results.append(check(f"length >= {SECONDS - 2}s (no stitching needed)", secs >= SECONDS - 2, f"{secs:.1f}s"))
    results.append(check("audio decodes", bool(stream), f"{stream.get('sample_rate')} Hz, {stream.get('channels')} ch"))
    print("predict_time:", (pred.get("metrics") or {}).get("predict_time"), "s | file:", path)
    print("\nALL CHECKS PASSED" if all(results) else "\nSOME CHECKS FAILED")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
