# Zi Music Studio app (Windows, free)
1. Install Python 3.9+ (python.org). Optional: ffmpeg in PATH for WAV/320k MP3 export.
2. Double-click `run_windows.bat` (installs Pillow, opens http://127.0.0.1:8765).
3. Pick a preset, length, lyrics or instrumental -> "Create generation job" (saved in zi_data/jobs; render in the Colab notebook).
4. Import finished tracks from your Google Drive sync folder -> Library -> play -> "RouteNote export" (cover 3000x3000, WAV 44.1k, MP3 320k, metadata.csv, routenote_form.txt, zip; Artist/Writer Rahal, AI-disclosure flag).
Generation is not local: free local GPU-less generation is not practical, so Colab renders.
