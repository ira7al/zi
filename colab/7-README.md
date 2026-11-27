# Zi Music Studio (free Colab notebook)

Generate full music tracks for free on Google Colab (T4 GPU) and save them to your Google Drive. No paid API, no local GPU needed.

## Run steps
1. Open `Zi_Music_Studio.ipynb` in Google Colab (File > Upload notebook, or "Open in Colab" from GitHub).
2. Runtime > Change runtime type > **T4 GPU**.
3. Run **cell 1** (setup). Wait for "Ready". Allow the Google Drive mount when asked.
4. Run the Studio cell. Pick a style preset, BPM (120, 124 or 128), lyrics (English or instrumental) and length.
5. Press **Generate**. Do not interrupt the cell while it runs.
6. Tracks are saved to `MyDrive/Zi_Music/`.

## Speed notes
- The free T4 is slow on the first run. A 60 s track can take 10+ minutes.
- If generation stalls, set `ACESTEP_INIT_LLM=false` in cell 1. The notebook then writes caption and lyrics itself and only the diffusion model runs.
- Start with short tracks (60 s), then go longer.

## Styles
Presets: melodic progressive techno, indie dance, mid-tempo techno, Afro-dance techno. Presets describe the sound (tempo, instruments, mood). Do not put artist names in prompts.

## AI music rules
- Label every release as AI-generated. Do not hide it.
- Do not imitate a real artist's voice or name artists in prompts.
- Check the model's licence allows commercial use before you release anything.
- Keep the prompt and settings used for each track.
- Earnings are not guaranteed.

## RouteNote prep
RouteNote has no upload API we use here, so upload by hand.
1. Export WAV (16-bit, 44.1 kHz) or high-bitrate MP3 from Drive.
2. Cover art: 3000x3000 px JPG/PNG, no text that claims another artist.
3. Metadata: title, artist name, genre, language, explicit flag, AI-generated disclosure.
4. Confirm you own or have licensed all parts of the track (lyrics included).
5. Check RouteNote's current AI-content policy before submitting.
