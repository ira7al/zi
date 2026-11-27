# Zi Music Studio

Free AI music generation: full-length tracks (up to 10 minutes, native) on a free Google Colab T4 GPU, saved to Google Drive as RouteNote-ready releases. No paid API, no card.

## Components
- `colab/Zi_Music_Studio.ipynb` - the studio notebook (engine, one-track studio, batch queue). See `colab/README.md`.
- `app/` - optional Windows companion app: builds generation jobs locally, imports finished tracks from Drive, exports RouteNote packs. See `app/README.md`.

## Run
1. Open `colab/Zi_Music_Studio.ipynb` in Google Colab (File > Upload notebook).
2. Runtime > Change runtime type > **T4 GPU**.
3. Run **cell 1** (setup), then **cell 2** (engine), then **cell 3** (one track) or **cell 4** (batch queue).

The notebook checks on every run whether it matches this repo and tells you when to refresh your copy.

## Legacy
The earlier hosted prototype (Replicate backend + web dashboard) was removed; see git history.
 
