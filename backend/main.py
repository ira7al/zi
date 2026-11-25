import asyncio
import os
import re
import shutil
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

import bot
import pipeline
import storage
from connectors import REGISTRY
from connectors.base import ReleaseMetadata, check_instrumental

REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
BOT_ENABLED = os.getenv("BOT_ENABLED", "1") == "1"
JOB_ID = r"^[A-Za-z0-9_-]{4,64}$"


def require_admin(authorization: str = Header(default="")):
    """Write endpoints spend Replicate credits; protect them when ADMIN_TOKEN is set."""
    if ADMIN_TOKEN and authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=401, detail="Missing or invalid admin token.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.init()
    task = asyncio.create_task(bot.run_forever()) if BOT_ENABLED and REPLICATE_TOKEN else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Zi API", version="0.05", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class GenerationRequest(BaseModel):
    track_name: str = Field(default="Untitled track", max_length=80)
    prompt: str = Field(min_length=3, max_length=1000)
    duration: int = Field(default=190, ge=pipeline.MIN_TRACK_SECONDS, le=300)

    @field_validator("prompt")
    @classmethod
    def _no_vocals(cls, v: str) -> str:
        return check_instrumental(v)


class ReleaseRequest(BaseModel):
    job_id: str = Field(pattern=JOB_ID)
    connector: str = "routenote"
    metadata: ReleaseMetadata


class SubmitMark(BaseModel):
    routenote_ref: str = Field(min_length=1, max_length=300, description="Release URL or UPC from RouteNote")


class BotBrief(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=3, max_length=1000)
    artist: str = Field(default="Zi", max_length=120)
    genre: str = "Electronic"
    label: str = "Zi"
    duration: int = Field(default=190, ge=pipeline.MIN_TRACK_SECONDS, le=300)

    @field_validator("prompt")
    @classmethod
    def _no_vocals(cls, v: str) -> str:
        return check_instrumental(v)


@app.get("/")
async def root():
    return {"name": "Zi API", "version": "0.05", "docs": "/docs"}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "provider_configured": bool(REPLICATE_TOKEN),
        "auth_required": bool(ADMIN_TOKEN),
        "bot": BOT_ENABLED,
        "connectors": list(REGISTRY),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "model": pipeline.MODEL,
        "license_commercial_confirmed": pipeline.MODEL_COMMERCIAL,
        "min_track_seconds": pipeline.MIN_TRACK_SECONDS,
    }


@app.post("/api/generations")
async def create_generation(request: GenerationRequest, _: None = Depends(require_admin)):
    if not REPLICATE_TOKEN:
        raise HTTPException(status_code=503, detail="Backend is missing REPLICATE_API_TOKEN.")
    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=503, detail="ffmpeg is not installed on the backend.")
    try:
        job = await pipeline.start_long_generation(request.track_name, request.prompt, request.duration)
    except (httpx.HTTPError, RuntimeError) as e:
        raise HTTPException(status_code=502, detail=f"Could not start generation: {e}")
    return pipeline.public(job)


@app.get("/api/generations/{job_id}")
async def get_generation(job_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job id.")
    try:
        return pipeline.public(await pipeline.refresh_job(job_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not retrieve generation status from Replicate.")


@app.get("/api/generations/{job_id}/audio")
async def get_audio(job_id: str):
    job = storage.get("jobs", job_id) if re.fullmatch(r"[A-Za-z0-9_-]{4,64}", job_id) else None
    path = (job or {}).get("preview_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Audio not available.")
    return FileResponse(path, media_type="audio/mpeg", filename=f"{job_id}.mp3")


@app.post("/api/releases/validate")
async def validate_release(req: ReleaseRequest):
    if req.connector not in REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown connector.")
    return REGISTRY[req.connector].validate(req.metadata)


@app.post("/api/releases")
async def create_release(req: ReleaseRequest, _: None = Depends(require_admin)):
    if req.connector not in REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown connector.")
    try:
        return await pipeline.build_release(req.job_id, req.metadata, req.connector)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (httpx.HTTPError, OSError) as e:
        raise HTTPException(status_code=502, detail=f"Could not prepare release files: {e}")


@app.get("/api/releases")
async def list_releases():
    return storage.list_("releases")


@app.get("/api/releases/{release_id}")
async def get_release(release_id: str):
    rel = storage.get("releases", release_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Release not found.")
    return rel


@app.get("/api/releases/{release_id}/package")
async def download_package(release_id: str, _: None = Depends(require_admin)):
    rel = storage.get("releases", release_id)
    if not rel or not rel.get("package_path") or not os.path.exists(rel["package_path"]):
        raise HTTPException(status_code=404, detail="Package not available.")
    return FileResponse(rel["package_path"], media_type="application/zip",
                        filename=os.path.basename(rel["package_path"]))


@app.post("/api/releases/{release_id}/submitted")
async def mark_submitted(release_id: str, body: SubmitMark, _: None = Depends(require_admin)):
    if not storage.get("releases", release_id):
        raise HTTPException(status_code=404, detail="Release not found.")
    storage.put("releases", {"id": release_id, "status": "submitted", "routenote_ref": body.routenote_ref})
    return storage.get("releases", release_id)


@app.post("/api/bot/queue")
async def bot_enqueue(brief: BotBrief, _: None = Depends(require_admin)):
    return bot.enqueue(brief.model_dump())


@app.get("/api/bot/queue")
async def bot_queue():
    return storage.list_("queue")
