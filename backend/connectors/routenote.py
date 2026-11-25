"""RouteNote connector.

RouteNote offers no public upload API, so this builds a package that mirrors
RouteNote's own "Create New Release" form field-for-field (Release Data -> Album Details -> Add Audio -> Artwork) and pre-validates RouteNote's specs.
"""
from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from datetime import date, timedelta

from .base import Distributor, ReleaseMetadata, ValidationReport


class RouteNoteConnector(Distributor):
    name = "routenote"
    UPLOAD_URL = "https://routenote.com/"  # log in -> Distribution -> Create New Release

    def validate(self, m: ReleaseMetadata) -> ValidationReport:
        e: list[str] = []
        w: list[str] = []
        if not m.primary_artist.strip():
            e.append("Primary artist is required.")
        if not (m.c_line.strip() and m.p_line.strip()):
            e.append("Copyright (C) and phonogram (P) lines are required, e.g. '2026 Zi'.")
        if m.release_type == "single" and len(m.tracks) != 1:
            e.append("A single must contain exactly 1 track.")
        if m.release_type == "ep" and not (2 <= len(m.tracks) <= 6):
            e.append("An EP should contain 2-6 tracks.")
        if m.release_type == "album" and len(m.tracks) < 5:
            e.append("An album should contain at least 5 tracks.")
        nums = sorted(t.track_number for t in m.tracks)
        if nums != list(range(1, len(m.tracks) + 1)):
            e.append("Track numbers must run 1..N with no gaps or duplicates.")
        if m.release_date and m.release_date < date.today() + timedelta(days=14):
            w.append("RouteNote needs a Sales Start Date at least 2 weeks away; pick a later date or leave blank for ASAP.")
        # AI disclosure is mandatory: this pipeline only produces AI audio.
        if not m.ai_generated:
            e.append("This audio is AI-generated; ai_generated must be true. Do not distribute it as human-made.")
        if not m.ai_disclosure.strip():
            e.append("An AI disclosure statement is required.")
        w.append("RouteNote excludes AI-generated music from Content ID (and some stores, e.g. Korean stores). "
                 "Do not expect YouTube Content ID income from this release.")
        if any(not t.instrumental for t in m.tracks):
            e.append("All tracks must be instrumental: the model cannot sing real lyrics.")
        return ValidationReport(ok=not e, errors=e, warnings=w)

    def build_package(self, release_id, meta, audio_paths, artwork_path, out_dir, provenance=None) -> str:
        os.makedirs(out_dir, exist_ok=True)
        today = date.today().isoformat()
        form = {
            "step_1_release_data": {
                "UPC": meta.upc or "(leave blank: RouteNote generates one free)",
                "Release Title": meta.title,
                "Originally Released": (meta.original_release_date or date.today()).isoformat(),
                "Sales Start Date": meta.release_date.isoformat() if meta.release_date else "(blank = as soon as approved)",
                "Explicit Content": meta.explicit,
            },
            "step_2_album_details": {
                "Primary Artist": meta.primary_artist, "Label": meta.label,
                "Genre": meta.genre, "Secondary Genre": meta.secondary_genre,
                "Language": meta.language, "Copyright (C)": meta.c_line, "Phonogram (P)": meta.p_line,
            },
            "step_3_tracks": [
                {"Track No.": t.track_number, "Title": t.title, "Artist": t.artist,
                 "Explicit": t.explicit, "Instrumental": t.instrumental, "Language": t.language,
                 "ISRC": t.isrc or "(leave blank: RouteNote assigns)", "Composer": t.composer, "Lyricist": t.lyricist,
                 "File": os.path.basename(p)}
                for t, p in zip(sorted(meta.tracks, key=lambda x: x.track_number), audio_paths)
            ],
            "step_4_artwork": {"File": "artwork.jpg", "Spec": "3000x3000 px, JPG, RGB, <25MB"},
            "ai_disclosure": {"ai_generated": meta.ai_generated, "statement": meta.ai_disclosure, "prompt": meta.prompt},
            "provenance": provenance or {},
            "generated": today, "release_id": release_id,
        }
        csv_buf = io.StringIO()
        wr = csv.writer(csv_buf)
        wr.writerow(["track_no", "title", "artist", "explicit", "instrumental", "language", "isrc", "file"])
        for t in form["step_3_tracks"]:
            wr.writerow([t["Track No."], t["Title"], t["Artist"], t["Explicit"], t["Instrumental"],
                         t["Language"], t["ISRC"], t["File"]])
        steps = (
            f"Upload to RouteNote ({self.UPLOAD_URL})\n"
            "1. Log in -> Distribution -> Create New Release.\n"
            "2. Release Data: copy values from release.json step_1.\n"
            "3. Album Details: step_2 values.\n"
            "4. Add Audio: upload the files in /audio (FLAC 44.1kHz, or MP3 320kbps/44.1kHz), then tracks.csv fields.\n"
            "   Mark every track as Instrumental (no lyrics).\n"
            "5. Add Artwork: artwork.jpg.\n"
            "   AI DISCLOSURE: declare this release as AI-generated wherever RouteNote asks (see release.json ai_disclosure).\n"
            "   RouteNote excludes AI-generated music from Content ID; do not expect Content ID income.\n"
            "6. Accept the Artist/Label Agreement, submit to moderation.\n"
            "7. Copy the release URL/UPC back into the Releases page ('Mark submitted').\n"
        )
        path = os.path.join(out_dir, f"routenote-{release_id}.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("release.json", json.dumps(form, indent=2, default=str))
            z.writestr("tracks.csv", csv_buf.getvalue())
            z.writestr("UPLOAD-STEPS.txt", steps)
            z.write(artwork_path, "artwork.jpg")
            for p in audio_paths:
                z.write(p, "audio/" + os.path.basename(p))
        return path
