<!-- METADATA: {"source_path": "backend/pipeline.py", "source_sha": "b203cd4025bfe6653971814fdaa3f9f139c0ef03", "extraction_quality": "full_ast", "model": "gpt-5-mini", "generated_at": "2026-11-25T12:32:09Z", "doc_type": "file"} -->
<details>
<summary>Documentation Metadata (click to expand)</summary>

```json
{
  "doc_type": "file_overview",
  "file_path": "backend/pipeline.py",
  "source_hash": "3ce5825667fbfadfe2ff49d79a757187fbae13bf67c4b764629bd0487aca26d4",
  "last_updated": "2026-11-25T12:31:39.639530+00:00",
  "git_sha": "b203cd4025bfe6653971814fdaa3f9f139c0ef03",
  "tokens_used": 4810,
  "complexity_score": 1,
  "estimated_review_time_minutes": 9,
  "external_dependencies": [
    "asyncio",
    "json",
    "math",
    "os",
    "shutil",
    "uuid",
    "typing",
    "httpx",
    "media",
    "storage",
    "connectors",
    "connectors.base"
  ]
}
```

</details>

[Documentation Home](../README.md) > [backend](./README.md) > **pipeline**

---

# pipeline.py

> **File:** `backend/pipeline.py`

![Complexity: Low](https://img.shields.io/badge/Complexity-Low-green) ![Review Time: 9min](https://img.shields.io/badge/Review_Time-9min-blue)

## 📑 Table of Contents


- [Overview](#overview)
- [Dependencies](#dependencies)
- [Architecture Notes](#architecture-notes)
- [Maintenance Notes](#maintenance-notes)
- [Functions and Classes](#functions-and-classes)

---

## Overview

This module coordinates an audio generation and packaging pipeline that produces multi-section musical pieces, stitches segments into a single master of at least 180 seconds, performs licence and model-spec checks, and prepares a RouteNote-compatible release package. It reads configuration and model presets from environment variables, divides target duration into segments, creates generation predictions against an external API (Replicate), polls and finalizes jobs, and assembles generated media and metadata into a release artifact using local media and storage helpers and connector metadata mappings.

The pipeline exposes a set of async operations for creating and waiting on generation jobs, finalizing results, and building the final release, as well as synchronous helpers for calculating segment counts and a public entry point to start generation. It integrates with external services via httpx and uses filesystem work directories, temporary storage, and utilities like uuid and shutil to manage artifacts during processing, while enforcing minimum track length and licence awareness based on model configuration.

## Dependencies

### External Dependencies

| Module | Usage |
| --- | --- |
| `asyncio` | import asyncio |
| `json` | import json |
| `math` | import math |
| `os` | import os |
| `shutil` | import shutil |
| `uuid` | import uuid |
| `typing` | from typing import Any |
| `httpx` | import httpx |
| `media` | import media |
| `storage` | import storage |
| `connectors` | from connectors import REGISTRY |
| `connectors.base` | from connectors.base import ReleaseMetadata |

## 📁 Directory

This file is part of the **backend** directory. View the [directory index](./README.md) to see all files in this module.

## Architecture Notes

- Extensive use of async functions for I/O-bound operations and job orchestration.
- Configuration and behaviour driven by environment variables and preset maps.
- Integration with external services/APIs (Replicate) via httpx and a connectors registry for release metadata.
- Filesystem and temporary artifact management using shutil, uuid, and a configurable work directory.
- Separation of responsibilities into small functions: prediction creation, polling, finalization, and release packaging.

## Maintenance Notes

- Compute how many generation segments are needed for a target duration (segments_needed).
- Create and submit generation predictions to the external model API (async _create_prediction) and provide a public entry to start a long-running generation process (async start_long_generation/public).
- Poll and wait for external jobs to complete, refresh job state, and finalize generation outputs into stitched masters (async wait_for_job, async refresh_job, async _finalize).
- Build a release package including media files and metadata suitable for connectors (async build_release) while performing licence and model checks.
- Manage environment-driven configuration such as model selection, segment length, extras, and working directory constants used throughout the pipeline.


---

## Constants

| Name | Type | Value |
| --- | --- | --- |
| `API` | — | `'https://api.replicate.com/v1'` |
| `TOKEN` | — | `os.getenv('REPLICATE_API_TOKEN', '')` |
| `MODEL` | — | `os.getenv('MUSIC_MODEL', 'stability-ai/stable-audio-2.5')` |
| `PRESETS` | — | `{'stability-ai/stable-audio-2.5': {'segment': 190, 'extra': {'steps': 8, 'cfg_scale': 1}}…` |
| `MODEL_COMMERCIAL` | — | `os.getenv('MODEL_LICENSE_COMMERCIAL', '0') == '1'` |
| `SEGMENT_SECONDS` | — | `int(os.getenv('SEGMENT_SECONDS', _preset.get('segment', 30)))` |
| `DURATION_KEY` | — | `os.getenv('MODEL_DURATION_KEY', 'duration')` |
| `EXTRA_INPUT` | — | `json.loads(os.environ['MODEL_EXTRA_INPUT']) if os.getenv('MODEL_EXTRA_INPUT') else _prese…` |
| `MIN_TRACK_SECONDS` | — | `180` |
| `FADE` | — | `2` |
| `WORK` | — | `os.getenv('WORK_DIR', os.path.join(os.path.dirname(__file__), 'data', 'work'))` |
| `LICENSE_MSG` | — | `'MusicGen weights are CC-BY-NC 4.0 (non-commercial). Switch MUSIC_MODEL to a commercially…` |
| `LICENSE_MSG` | — | `f"Commercial licence for '{MODEL}' is not confirmed. Verify its terms (for Stability AI m…` |
| `SECTIONS` | — | `['intro, sparse, establishing the main theme', 'building, adding layers and rhythm', 'mai…` |



---

## Functions and Classes


### _h

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def _h() -> dict:
```

#### Description

Internal helper function in the pipeline module whose job is to construct and return a dictionary used by the pipeline.

Being named with a leading underscore indicates it is intended for private/internal use within backend.pipeline.

#### Returns

**Type:** `dict`

—

#### Complexity

Not analyzed

---



### segments_needed

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def segments_needed(total: int) -> int:
```

#### Description

Determine how many segments are required for a given total count.

The function takes an integer total and returns the number of segments needed to cover or partition that total.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `total` | `int` | ✅ | — |

#### Returns

**Type:** `int`

—

#### Complexity

Not analyzed

---



### _create_prediction

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def _create_prediction(c: httpx.AsyncClient, prompt: str, seconds: int) -> dict:
```

#### Description

Asynchronously create a prediction using the provided HTTPX async client, sending the given text prompt and a time parameter in seconds to the remote service.

It performs the network call and returns the prediction result as a Python dictionary.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `c` | `httpx.AsyncClient` | ✅ | — |
| `prompt` | `str` | ✅ | — |
| `seconds` | `int` | ✅ | — |

#### Returns

**Type:** `dict`

—

#### Complexity

Not analyzed

---



### start_long_generation

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def start_long_generation(track_name: str, prompt: str, duration: int) -> dict[str, Any]:
```

#### Description

Asynchronously initiates a long-running generation process for a named track using the provided prompt and target duration.

It kicks off generation work (likely audio or content generation) associated with the given track_name and runs for the specified duration before returning status or result metadata.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `track_name` | `str` | ✅ | — |
| `prompt` | `str` | ✅ | — |
| `duration` | `int` | ✅ | — |

#### Returns

**Type:** `dict[str, Any]`

—

#### Complexity

Not analyzed

---



### public

![Type: Sync](https://img.shields.io/badge/Type-Sync-green)

#### Signature

```python
def public(job: dict) -> dict:
```

#### Description

Accepts a job represented as a dictionary and produces another dictionary based on that input.

The function likely transforms, filters, or prepares the job data for further use or exposure.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job` | `dict` | ✅ | — |

#### Returns

**Type:** `dict`

—

#### Complexity

Not analyzed

---



### refresh_job

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def refresh_job(job_id: str) -> dict[str, Any]:
```

#### Description

Asynchronously refreshes the state or metadata of a pipeline job identified by the given job_id, likely by fetching the latest information from storage or an external service and returning the updated job representation as a dictionary.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | ✅ | — |

#### Returns

**Type:** `dict[str, Any]`

—

#### Complexity

Not analyzed

---



### _finalize

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def _finalize(job: dict) -> dict:
```

#### Description

Asynchronously perform finalization steps for a pipeline job represented by the provided job dictionary, such as completing status updates, applying any final transformations or cleanup, and preparing the job record for return or storage.

It completes the job's processing lifecycle and ensures the job dict reflects the finalized state before being returned.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job` | `dict` | ✅ | — |

#### Returns

**Type:** `dict`

—

#### Complexity

Not analyzed

---



### wait_for_job

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def wait_for_job(job_id: str, poll: float = 8, timeout: float = 1800) -> dict[str, Any]:
```

#### Description

Asynchronously waits for the completion (or update) of a background job identified by job_id, polling at regular intervals and timing out if the job does not complete within the given timeout.

It returns the final job state as a dictionary when finished or when a terminal condition is reached.


job_id is the identifier of the job to monitor. poll and timeout are time intervals in seconds: poll controls how often the function checks the job status, and timeout is the maximum total wait time before giving up.

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | ✅ | — |
| `poll` = `8` | `float` | ❌ | — |
| `timeout` = `1800` | `float` | ❌ | — |

#### Returns

**Type:** `dict[str, Any]`

—

#### Complexity

Not analyzed

---



### build_release

![Type: Async](https://img.shields.io/badge/Type-Async-blue)

#### Signature

```python
async def build_release(job_id: str, meta: ReleaseMetadata, connector: str = 'routenote') -> dict[str, Any]:
```

#### Description

Asynchronously builds a release package for a given job using the provided release metadata and a specified distribution connector.

It orchestrates the creation of whatever payload or configuration is needed to push or prepare the release for the chosen connector (defaulting to 'routenote') and returns the assembled result as a dictionary.


meta is a ReleaseMetadata object containing the release-specific information (e.g., tracks, artists, assets, and release settings) required to construct the release package; connector selects which distribution or integration workflow to target (defaults to 'routenote').

#### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | ✅ | — |
| `meta` | `ReleaseMetadata` | ✅ | — |
| `connector` = `'routenote'` | `str` | ❌ | — |

#### Returns

**Type:** `dict[str, Any]`

—

#### Complexity

Not analyzed

---



---

## Navigation

**↑ Parent Directory:** [Go up](./README.md)

---

*This documentation was automatically generated by AI ([Woden DocBot](https://github.com/marketplace/ai-document-creator)) and may contain errors. It is the responsibility of the user to validate the accuracy and completeness of this documentation.*
