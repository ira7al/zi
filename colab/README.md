# Zi Music Studio (free Colab notebook)

Generate full-length music tracks (up to 10 minutes, native) for free on Google Colab (T4 GPU) and save RouteNote-ready releases to your Google Drive. No paid API, no local GPU needed.

## Run steps
1. Open `Zi_Music_Studio.ipynb` in Google Colab (File > Upload notebook, or "Open in Colab" from GitHub).
2. Runtime > Change runtime type > **T4 GPU**.
3. Run **cell 1** (setup, 10-20 min first time). Allow the Google Drive mount when asked.
4. Run **cell 2** (engine).
5. Run **cell 3** (one track: style, theme, length 60-600 s, quality preset) or **cell 4** (batch queue: a week of tracks back to back, resumes after a disconnect).
6. Tracks are saved to `MyDrive/Zi_Music/`, each in a folder with WAV + FLAC + MP3 320k + MP3 128k preview, 3000x3000 cover, lyrics, `metadata.json` and `routenote_form.txt`.

## Quality presets
- **Fast:** 8 steps, no LM planning. Drafts.
- **Standard:** 8 steps + LM thinking.
- **High:** `acestep-v15-turbo-shift3` model when available, 14 steps, 2 seed candidates, automatic QC pick (clipping, silence, duration, spectrum).

## Mastering
Every track passes a free ffmpeg chain: high-pass, gentle EQ, glue compressor, stereo width, two-pass loudness normalize to -14 LUFS / -1 dBTP, safety limiter. The before/after loudness numbers are stored in `metadata.json`.

## Long tracks
The model renders up to 600 s natively, so 5-6 min tracks are one render. If a render returns short audio, the engine extends it with a continuation segment joined by a beat-aligned crossfade.

## AI music rules
- Label every release as AI-generated. Do not hide it.
- Do not imitate a real artist's voice or name artists in prompts.
- Check the model's licence allows commercial use before you release anything (ACE-Step 1.5 is MIT).
- Keep the prompt and settings used for each track (the notebook stores them in `metadata.json`).
- Earnings are not guaranteed.

## RouteNote prep
RouteNote has no upload API we use here, so upload by hand.
1. Audio: the folder's FLAC or WAV (44.1 kHz stereo 16-bit) or MP3 320k.
2. Cover art: `cover_3000x3000.jpg`.
3. Metadata: copy from `routenote_form.txt`.
4. Confirm you own or have licensed all parts of the track (lyrics included).
5. Check RouteNote's current AI-content policy before submitting.
