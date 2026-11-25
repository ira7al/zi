"""Generate (multi-section) -> stitch to a >=180s master -> licence/spec checks -> RouteNote package."""
import asyncio
import json
import math
import os
import shutil
import uuid
from typing import Any

import httpx

import media
import storage
from connectors import REGISTRY
from connectors.base import ReleaseMetadata

API = "https://api.replicate.com/v1"
TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
MODEL = os.getenv("MUSIC_MODEL", "stability-ai/stable-audio-2.5")
# Per-model defaults taken from each model's published Replicate input schema.
#  stable-audio-2.5: prompt, duration (1-190 s), steps (4-8), cfg_scale (1-25), seed -> single audio URL
#  musicgen:        prompt, duration, output_format (about 30 s per call in practice)
PRESETS = {
    "stability-ai/stable-audio-2.5": {"segment": 190, "extra": {"steps": 8, "cfg_scale": 1}},
    "meta/musicgen": {"segment": 30, "extra": {"output_format": "wav"}},
}
_preset = PRESETS.get(MODEL, {})
# Operator must set this to 1 ONLY after verifying the model's licence allows commercial distribution.
MODEL_COMMERCIAL = os.getenv("MODEL_LICENSE_COMMERCIAL", "0") == "1"
SEGMENT_SECONDS = int(os.getenv("SEGMENT_SECONDS", _preset.get("segment", 30)))
DURATION_KEY = os.getenv("MODEL_DURATION_KEY", "duration")
EXTRA_INPUT = json.loads(os.environ["MODEL_EXTRA_INPUT"]) if os.getenv("MODEL_EXTRA_INPUT") else _preset.get("extra", {})
MIN_TRACK_SECONDS = 180
FADE = 2
WORK = os.getenv("WORK_DIR", os.path.join(os.path.dirname(__file__), "data", "work"))
if MODEL.startswith("meta/musicgen"):
    LICENSE_MSG = ("MusicGen weights are CC-BY-NC 4.0 (non-commercial). Switch MUSIC_MODEL to a commercially "
                   "licensed model before releasing.")
else:
    LICENSE_MSG = (f"Commercial licence for '{MODEL}' is not confirmed. Verify its terms (for Stability AI models: "
                   "registration with Stability AI and under US$1M total annual revenue, otherwise an Enterprise licence), "
                   "then set MODEL_LICENSE_COMMERCIAL=1.")
SECTIONS = ["intro, sparse, establishing the main theme", "building, adding layers and rhythm",
            "main section, full energy, memorable hook", "variation with a new melodic idea",
            "breakdown, stripped back and spacious", "final climax, full energy, main theme returns",
            "outro, resolving gently"]
_version: str | None = None
_locks: dict[str, asyncio.Lock] = {}


def _h() -> dict:
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def segments_needed(total: int) -> int:
    if total <= SEGMENT_SECONDS:  # e.g. Stable Audio 2.5: 180-190 s in ONE run, no stitching
        return 1
    return math.ceil((total + 3 - FADE) / (SEGMENT_SECONDS - FADE))


async def _create_prediction(c: httpx.AsyncClient, prompt: str, seconds: int) -> dict:
    global _version
    if _version is None:
        r = await c.get(f"{API}/models/{MODEL}", headers=_h())
        r.raise_for_status()
        _version = (r.json().get("latest_version") or {}).get("id") or ""
    body: dict[str, Any] = {"input": {"prompt": prompt, DURATION_KEY: seconds, **EXTRA_INPUT}}
    url = f"{API}/predictions" if _version else f"{API}/models/{MODEL}/predictions"
    if _version:
        body["version"] = _version
    r = await c.post(url, headers=_h(), json=body)
    if r.status_code >= 400:
        raise RuntimeError(str(r.json().get("detail", "Replicate request failed.")))
    return r.json()


async def start_long_generation(track_name: str, prompt: str, duration: int) -> dict[str, Any]:
    total = max(duration, MIN_TRACK_SECONDS)
    n = segments_needed(total)
    tail = "Instrumental only, no vocals, no singing, no spoken words."
    if n == 1:
        prompts = [(f"{prompt}. Full-length arrangement with intro, build, climax and outro. {tail}", total)]
    else:
        prompts = [(f"{prompt}. {SECTIONS[i % len(SECTIONS)]}. {tail}", SEGMENT_SECONDS) for i in range(n)]
    async with httpx.AsyncClient(timeout=60) as c:
        preds = await asyncio.gather(*[_create_prediction(c, pr, s) for pr, s in prompts])
    job = {"id": "long-" + uuid.uuid4().hex[:12], "track_name": track_name, "prompt": prompt,
           "duration": duration, "status": "starting",
           "segments": [{"id": p["id"], "status": p.get("status", "starting"),
                         "output": p.get("output"), "error": p.get("error")} for p in preds]}
    storage.put("jobs", job)
    return job


def public(job: dict) -> dict:
    segs = job.get("segments") or []
    return {"id": job["id"], "track_name": job.get("track_name"), "status": job.get("status"),
            "error": job.get("error"), "duration": job.get("duration"),
            "segments_total": len(segs), "segments_done": sum(s["status"] == "succeeded" for s in segs),
            "audio_url": f"/api/generations/{job['id']}/audio" if job.get("preview_path") else None}


async def refresh_job(job_id: str) -> dict[str, Any]:
    job = storage.get("jobs", job_id)
    if not job:
        raise KeyError(job_id)
    if job["status"] in ("succeeded", "failed", "canceled"):
        return job
    segs = job.get("segments") or []
    async with httpx.AsyncClient(timeout=30) as c:
        for s in segs:
            if s["status"] in ("succeeded", "failed", "canceled"):
                continue
            r = await c.get(f"{API}/predictions/{s['id']}", headers=_h())
            r.raise_for_status()
            d = r.json()
            s.update(status=d.get("status"), output=d.get("output"), error=d.get("error"))
    job["segments"] = segs
    bad = [s for s in segs if s["status"] in ("failed", "canceled")]
    if bad:
        job.update(status="failed", error=bad[0].get("error") or "A section failed to generate.")
    elif segs and all(s["status"] == "succeeded" for s in segs):
        storage.put("jobs", job)
        return await _finalize(job)
    else:
        job["status"] = "processing"
    storage.put("jobs", job)
    return job


async def _finalize(job: dict) -> dict:
    async with _locks.setdefault(job["id"], asyncio.Lock()):
        cur = storage.get("jobs", job["id"]) or job
        if cur.get("status") == "succeeded" and cur.get("audio_path"):
            return cur
        try:
            d = os.path.join(WORK, "jobs", job["id"])
            os.makedirs(d, exist_ok=True)
            files = []
            for i, s in enumerate(job["segments"]):
                out = s["output"]
                url = out[0] if isinstance(out, list) else out
                ext = os.path.splitext(url.split("?")[0])[1] or ".wav"
                files.append(await media.download(url, os.path.join(d, f"seg{i:02d}{ext}")))
            master, preview = os.path.join(d, "master.flac"), os.path.join(d, "preview.mp3")
            await asyncio.to_thread(media.stitch, files, master, preview, FADE)
            secs = await asyncio.to_thread(media.probe_seconds, master)
            job.update(status="succeeded", audio_path=master, preview_path=preview, duration=int(secs), error=None)
        except Exception as e:
            job.update(status="failed", error=f"Could not assemble audio: {e}"[:300])
        storage.put("jobs", job)
        return job


async def wait_for_job(job_id: str, poll: float = 8, timeout: float = 1800) -> dict[str, Any]:
    waited = 0.0
    while waited < timeout:
        job = await refresh_job(job_id)
        if job["status"] in ("succeeded", "failed", "canceled"):
            return job
        await asyncio.sleep(poll)
        waited += poll
    raise TimeoutError("Generation timed out.")


async def build_release(job_id: str, meta: ReleaseMetadata, connector: str = "routenote") -> dict[str, Any]:
    job = storage.get("jobs", job_id)
    if not job or job.get("status") != "succeeded" or not job.get("audio_path"):
        raise ValueError("Generation job must be succeeded before building a release.")
    conn = REGISTRY[connector]
    if f"Model: {MODEL}" not in meta.ai_disclosure:
        meta = meta.model_copy(update={"ai_disclosure": f"{meta.ai_disclosure} Model: {MODEL}."})
    report = conn.validate(meta)
    secs = await asyncio.to_thread(media.probe_seconds, job["audio_path"])
    if secs < MIN_TRACK_SECONDS:
        report.errors.append(f"Track is {secs:.0f}s; minimum is {MIN_TRACK_SECONDS}s.")
    if not MODEL_COMMERCIAL:
        report.errors.append(LICENSE_MSG)
    report.ok = not report.errors
    release_id = uuid.uuid4().hex[:12]
    base = {"id": release_id, "job_id": job_id, "metadata": meta.model_dump(mode="json")}
    if not report.ok:
        storage.put("releases", {**base, "status": "invalid", "error": "; ".join(report.errors)})
        return {**storage.get("releases", release_id), "validation": report.model_dump()}
    d = os.path.join(WORK, release_id)
    os.makedirs(d, exist_ok=True)
    track = sorted(meta.tracks, key=lambda t: t.track_number)[0]
    safe = "".join(ch if ch.isalnum() else "-" for ch in track.title)[:40].strip("-") or "track"
    flac = os.path.join(d, f"01-{safe}.flac")
    shutil.copy(job["audio_path"], flac)
    art = await asyncio.to_thread(media.make_cover, meta.title, meta.primary_artist, job_id, os.path.join(d, "artwork.jpg"))
    prov = {"model": MODEL, "commercial_licence_confirmed_by_operator": MODEL_COMMERCIAL,
            "sections": len(job.get("segments") or []), "crossfade_seconds": FADE,
            "length_seconds": round(secs, 1), "assembly": ("single generation" if len(job.get("segments") or []) == 1 else "sections generated separately and crossfaded")}
    pkg = await asyncio.to_thread(conn.build_package, release_id, meta, [flac], art, os.path.join(WORK, "packages"), prov)
    storage.put("releases", {**base, "status": "ready", "package_path": pkg})
    return {**storage.get("releases", release_id), "validation": report.model_dump()}
