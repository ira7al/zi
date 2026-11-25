# Zi 0.05

- `index.html` – operations dashboard (demo telemetry)
- `music-studio.html` – MusicGen studio (needs the backend)
- `releases.html` – RouteNote release packager + bot queue (phase 2)
- `backend/` – FastAPI service that calls Replicate server-side

## Run locally
Frontend: `python -m http.server 8080` → http://localhost:8080
Backend:
```bash
cd backend && pip install -r requirements.txt
export REPLICATE_API_TOKEN=... ALLOWED_ORIGINS=http://localhost:8080
uvicorn main:app --port 8000
```
Then enter `http://localhost:8000` as the Backend URL in the Studio.

Docker: `docker build -t zi-backend backend && docker run -p 8000:8000 -e REPLICATE_API_TOKEN=... -e ALLOWED_ORIGINS=https://inecloud313-prog.github.io zi-backend`

Deploy site: Settings → Pages → GitHub Actions. See README-ADDENDUM.md for hosting notes.

## 0.05 changes
- **Studio fixed to match the backend:** the old single-file Studio sent 5-30 s tracks and a "Vocal direction" field, so every request was rejected (backend needs 180-300 s and instrumental prompts). Now 180-300 s, instrument picker, prompt limit lowered to 800 so the added brief text fits the backend's 1000-char cap.
- **Admin token field** in the Studio (sent as `Authorization: Bearer`), needed when `ADMIN_TOKEN` is set.
- **Resilient polling:** a few network blips no longer abandon a paid job, and an unfinished job resumes after a page reload.
- **Readable errors** for FastAPI validation failures; clear messages for missing token, ffmpeg or provider key from `/api/health`.
- `single-file-app.html` now contains the same Studio as `music-studio.html`.

## Deploy on Render (0.05)
`render.yaml` defines two services: `zi-backend` (Docker, persistent 5 GB disk, health check `/api/health`) and `zi-site` (static frontend).
1. Push this repo to GitHub (see README-ADDENDUM.md).
2. Render dashboard → **New → Blueprint** → choose the repo → **Apply**.
3. When prompted, enter `REPLICATE_API_TOKEN` and `ALLOWED_ORIGINS` (your `zi-site` URL, plus your GitHub Pages URL if you use it, comma-separated).
4. Open `zi-backend` → Environment, copy the generated `ADMIN_TOKEN`.
5. Open your `zi-site` URL → Music Studio. Backend URL = your `zi-backend` URL; paste the admin token.
6. Check `https://<zi-backend>.onrender.com/api/health` shows `provider_configured: true` and `ffmpeg: true`.
Notes: the disk needs a paid plan (`starter`); free instances sleep and lose data. Generation is paid by Replicate per run. Packaging stays blocked until you verify the model licence and set `MODEL_LICENSE_COMMERCIAL=1`.
