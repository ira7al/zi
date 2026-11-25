"""Autonomous release bot: pulls briefs from the queue, generates, packages a draft release.
It never submits to RouteNote; a human uploads the package (RouteNote has no API)."""
import asyncio
import logging
import uuid
from datetime import date

import pipeline
import storage
from connectors.base import ReleaseMetadata, TrackMetadata

log = logging.getLogger("bot")


def brief_to_metadata(b: dict) -> ReleaseMetadata:
    year = date.today().year
    artist = b.get("artist") or "Zi"
    return ReleaseMetadata(
        title=b["title"], primary_artist=artist, genre=b.get("genre", "Electronic"),
        label=b.get("label", "Zi"), c_line=f"{year} {b.get('label', 'Zi')}",
        p_line=f"{year} {b.get('label', 'Zi')}", prompt=b["prompt"],
        tracks=[TrackMetadata(title=b["title"], artist=artist)])


def enqueue(brief: dict) -> dict:
    item = {"id": uuid.uuid4().hex[:12], "brief": brief, "status": "queued"}
    storage.put("queue", item)
    return storage.get("queue", item["id"])


async def process(item: dict) -> None:
    b = item["brief"]
    try:
        storage.put("queue", {"id": item["id"], "status": "generating"})
        job = await pipeline.start_long_generation(b["title"], b["prompt"], int(b.get("duration", 190)))
        storage.put("queue", {"id": item["id"], "job_id": job["id"]})
        job = await pipeline.wait_for_job(job["id"])
        if job["status"] != "succeeded":
            raise RuntimeError(job.get("error") or f"Generation {job['status']}.")
        storage.put("queue", {"id": item["id"], "status": "packaging"})
        rel = await pipeline.build_release(job["id"], brief_to_metadata(b))
        ok = rel["status"] == "ready"
        storage.put("queue", {"id": item["id"], "status": "done" if ok else "needs_attention",
                              "release_id": rel["id"], "error": None if ok else rel.get("error")})
    except Exception as e:  # keep the loop alive
        log.exception("bot item failed")
        storage.put("queue", {"id": item["id"], "status": "failed", "error": str(e)[:300]})


async def run_forever(interval: float = 10) -> None:
    while True:
        queued = storage.list_("queue", "WHERE status='queued'", limit=1)
        if queued:
            await process(queued[0])
        else:
            await asyncio.sleep(interval)
