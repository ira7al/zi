# Zi 0.05 — Music Studio addition

The existing RouteNote dashboard stays at `index.html`. The Music Studio is `music-studio.html`.

## Deploy the static website
The GitHub Actions workflow `.github/workflows/pages.yml` publishes the static site. In GitHub, open Settings → Pages and choose GitHub Actions.

After deployment:
- Dashboard: `https://inecloud313-prog.github.io/zi/`
- Music Studio: `https://inecloud313-prog.github.io/zi/music-studio.html`

## Deploy the backend separately
GitHub Pages cannot run Python/FastAPI. Deploy the `backend/` directory to a Python/Docker host. Set `REPLICATE_API_TOKEN` as a secret/environment variable on that host. Set `ALLOWED_ORIGINS=https://inecloud313-prog.github.io`.

The backend exposes `/api/health`, `POST /api/generations`, and `GET /api/generations/{job_id}`. In the Music Studio, enter the backend base URL. Never put your Replicate token in browser code or commit it to Git.

This first generation backend uses an in-memory job index, so its job list is not durable across restarts. Existing RouteNote dashboard telemetry remains demo data; this release does not publish releases to RouteNote.

## Phase 2 (0.02): RouteNote connector + release bot
RouteNote has **no public upload API**, so the connector builds a package that mirrors RouteNote's *Create New Release* form and passes its audio/artwork specs. You do one manual upload per release.

- `releases.html` – build a package from a generation job, download it, mark it submitted (stores the RouteNote URL/UPC).
- Package (`routenote-<id>.zip`): `release.json` (form values per step + AI disclosure), `tracks.csv`, `UPLOAD-STEPS.txt`, `artwork.jpg` (3000×3000 RGB), `audio/*.flac` (44.1 kHz; MusicGen outputs 32 kHz so it is resampled).
- Bot: `POST /api/bot/queue` with `{title, prompt, artist, genre}`; it generates, converts, packages and leaves a `ready` release. It never submits anything.
- Endpoints: `/api/releases` (GET/POST), `/api/releases/validate`, `/api/releases/{id}/package`, `/api/releases/{id}/submitted`, `/api/bot/queue`.
- Set `ADMIN_TOKEN` on the backend: spend/write endpoints then require `Authorization: Bearer <token>`.
- Jobs/releases persist in SQLite at `DB_PATH`; mount a volume at `/app/data` or they vanish on redeploy.
- Swap in a real API distributor later by implementing `Distributor.submit` in `backend/connectors/`.

## First live test (do this before queuing the bot)
`cd backend && export REPLICATE_API_TOKEN=... && python smoke_test.py` runs one real 180 s generation (one Replicate prediction), prints the model licence URL, and checks status, URL, length and decodability.

## 0.03 fixes
- **Length:** minimum 180 s. The backend generates several ~30 s sections in parallel (one Replicate run each, 7 for 180-198 s), crossfades them into a 44.1 kHz FLAC master and a 192k MP3 preview. Sections are separate generations, so listen before releasing. Packaging re-checks the real length.
- **Instrumental only:** vocal/lyric wording in prompts is rejected, every section prompt ends with "instrumental, no vocals", and non-instrumental tracks fail validation.
- **AI disclosure:** mandatory (validation fails without it) and written into `release.json` and `UPLOAD-STEPS.txt`. RouteNote excludes AI music from Content ID; that is their policy and cannot be changed here.
- **Licence gate / model (0.04):** default model is now `stability-ai/stable-audio-2.5` (inputs: prompt, duration 1-190, steps 4-8, cfg_scale, seed; single audio URL out), so a 180-190 s track is one generation. `meta/musicgen` is CC-BY-NC 4.0 (non-commercial). Packaging stays blocked until `MODEL_LICENSE_COMMERCIAL=1`. Before setting it: register with Stability AI, confirm total annual revenue (with affiliates) is under US$1M (else Enterprise licence), and read the licence/attribution terms yourself; the Replicate page links a repo LICENSE file that I could not open.
- **Docker:** ffmpeg/fonts verified at build, non-root user, healthcheck, `$PORT` support, `.dockerignore`, and `docker-compose.yml` with a persistent volume. Not built in the authoring sandbox; run `docker compose up --build`.
