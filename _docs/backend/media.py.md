<!-- METADATA: {"source_path": "backend/media.py", "source_sha": "64a257986acc0aa6fc26095e1b3c9f929232ba36", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-25T12:32:09Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "backend/media.py",
  "source_hash": "42179fc943e430092a9359f0739cdeff22e3a1d433bf7403380f8fbb211cc9de",
  "last_updated": "2026-11-25T12:31:32.505508+00:00",
  "git_sha": "64a257986acc0aa6fc26095e1b3c9f929232ba36",
  "tokens_used": 3240,
  "complexity_score": 1,
  "estimated_review_time_minutes": 5,
  "external_dependencies": [
    "hashlib",
    "math",
    "os",
    "subprocess",
    "httpx",
    "PIL"
  ]
}
```

</details>

[Documentation Home](../README.md) > [backend](./README.md) > **media**

---

# media.py

> **File:** `backend/media.py`

![Complexity: Low](https://img.shields.io/badge/Complexity-Low-green) ![Review Time: 5min](https://img.shields.io/badge/Review_Time-5min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module provides utilities for preparing audio and cover art assets for distribution. It includes asynchronous download support, ffmpeg-based audio processing and probing, sample-rate conversion tailored for a specific distributor, and an assembler that stitches together segments with crossfades and produces both a high-quality FLAC master and an MP3 preview. In addition, the module can generate original procedural cover art as a high-resolution JPG using Pillow, with text-light design suitable for store requirements.

The functions coordinate external tools and libraries: network fetching via an async download function, subprocess-driven ffmpeg invocations for resampling, normalization, duration probing and mixing, and Pillow routines to render 3000x3000 RGB artwork. Helper utilities encapsulate running shell commands and extracting segment durations to drive the stitching workflow.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `hashlib` | import hashlib |
| `math` | import math |
| `os` | import os |
| `subprocess` | import subprocess |
| `httpx` |     import httpx |
| `PIL` |     from PIL import Image, ImageDraw, ImageFont |

## 📁 Directory

This file is part of the **backend** directory. View the [directory index](./README.md) to see all files in this module.

## Architecture Notes

- Uses asynchronous HTTP fetching for downloads
- Drives external multimedia processing via subprocess (ffmpeg)
- Generates procedural images with Pillow (Image, ImageDraw, ImageFont)

## Maintenance Notes

- Asynchronously download remote resources needed for media processing.
- Invoke ffmpeg via subprocess to run conversions and normalization steps.
- Resample generated audio to 44.1 kHz/16-bit FLAC suitable for RouteNote distribution.
- Create procedural 3000x3000 RGB JPEG cover art with a text-light style using Pillow.
- Measure audio durations and stitch multiple segments into a single crossfaded FLAC master and a 192 kbps MP3 preview.


---

## Functions and Classes


### download

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def download(url: str, dest: str) -> str:
```

#### Description

Asynchronously downloads data from the given URL and saves it to the specified destination path.

It performs the network transfer and writes the retrieved content to the filesystem at `dest`.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `url` | `str` | ✅ | — |
| `dest` | `str` | ✅ | — |

#### Returns

**Type:** `str`

—

#### Complexity

Not analyzed

---



### to_routenote_flac

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def to_routenote_flac(src: str, dest: str) -> str:
```

#### Description

Resample a FLAC audio file produced at 32 kHz to the 44.1 kHz sample rate required by RouteNote, saving the result to the destination path.

Essentially converts or rewrites the source FLAC into a RouteNote-compatible FLAC at 44.1 kHz.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `src` | `str` | ✅ | — |
| `dest` | `str` | ✅ | — |

#### Returns

**Type:** `str`

—

#### Complexity

Not analyzed

---



### make_cover

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def make_cover(title: str, artist: str, seed: str, dest: str, size: int = 3000) -> str:
```

#### Description

Generate a piece of original generative artwork as a 3000x3000 RGB JPEG image following the project’s text-light store rules.

The function uses the provided title, artist and seed to produce the image and writes it to the given destination path.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `title` | `str` | ✅ | — |
| `artist` | `str` | ✅ | — |
| `seed` | `str` | ✅ | — |
| `dest` | `str` | ✅ | — |
| `size` = `3000` | `int` | ❌ | — |

#### Returns

**Type:** `str`

—

#### Complexity

Not analyzed

---



### _run

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def _run(cmd: list[str]) -> None:
```

#### Description

Execute a system command represented by a list of strings.

The function runs the provided command (likely by invoking a subprocess) and does not return a value.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `cmd` | `list[str]` | ✅ | — |

#### Complexity

Not analyzed

---



### probe_seconds

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def probe_seconds(path: str) -> float:
```

#### Description

Open and inspect the media file at the given filesystem path to determine its duration.

The function returns the length of the media in seconds as a floating point number.


A float giving the media duration in seconds.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `path` | `str` | ✅ | — |

#### Returns

**Type:** `float`

A float giving the media duration in seconds.

#### Complexity

Not analyzed

---



### stitch

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def stitch(files: list[str], master: str, preview: str, fade: float = 2.0) -> None:
```

#### Description

Take a list of audio segment files and crossfade them together, producing a final 44.1 kHz, 16-bit stereo FLAC master and a 192 kbps MP3 preview.

The function applies a specified fade length between segments when creating the stitched output.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `files` | `list[str]` | ✅ | — |
| `master` | `str` | ✅ | — |
| `preview` | `str` | ✅ | — |
| `fade` = `2.0` | `float` | ❌ | — |

#### Complexity

Not analyzed

---



---

## Navigation

**↑ Parent Directory:** [Go up](./README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*
